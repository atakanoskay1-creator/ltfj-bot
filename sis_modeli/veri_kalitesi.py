#!/usr/bin/env python3
"""Arsiv kusurlari: teshis + dondurulmus sis modeli icin A/B karsilastirmasi.

BULUNAN KUSUR - 2021-2023 CIY NOKTASI:
LTFJ arsivinde 2021-2023 arasi spread (= sicaklik - ciy noktasi) sistematik
olarak DUSUK bildiriliyor. Kanit:

  1) spread = 0 (T = Td) orani %0.6-2.8'den %5.9-12.7'ye ciktiktan sonra
     2024'te %0.6'ya donuyor.
  2) Bu kayitlarin %52'si CAVOK - doymus havada 10 km gorus fiziksel bir
     celiskidir (temiz donemlerde %21 ve %11).
  3) 2022'de HAZIRAN-AGUSTOS dahil her ay gozlemlerin %7-24'u doymus hava
     bildiriyor. 2025'te ayni oran %0-2 ve yalnizca kis aylarinda.
  4) Ay-eslenmis ortalama spread, komsu donemlerin ortalamasindan
     +0.83 °C dusuk - ve bu fark 12 ayin 11'inde ayni yonde.
  5) Hicbir donemde NEGATIF spread yok: bildirim zinciri Td'yi T'de
     kirpiyor. Yuksek yanli bir Td sensoru, tam da 0'da boyle bir sivri
     uretir.

MEKANIK SONUC: kusur spread = 0 ile SINIRLI DEGIL. Td butun donem boyunca
yuksek yanli oldugu icin o yillardaki TUM spread degerleri kirli. Bu yuzden
"spread = 0 olan satirlari at" yanlis bir duzeltmedir; ustelik etiketle
iliskili bir degiskene gore secim yapmak (ornegin "spread=0 VE CAVOK olanlari
at") gercek sis olaylarini da silip modeli tehlikeli yonde saldirganlastirir.
Kirpma bilgiyi geri donulmez sekilde yok ettigi icin yanlilik duzeltilemez de.

Geriye tek durust secenek kaliyor: o yillari EGITIMDEN CIKARMAK. Bedeli
kucuk degil - 255 bagimsiz sisli gunun 56'si (%22) orada.

ONCEDEN ILAN EDILEN KARAR KURALI (sonuclara BAKILMADAN yazildi):
  A = mevcut model (2011-2023 ile egitilmis)
  B = temiz model (2021-2023 disarida)
  Birincil olcu: holdout (2024-2026) uzerinde Average Precision.
  B YALNIZCA su durumda dondurulur: gun bazli ESLESTIRILMIS blok
  bootstrap'te (AP_B - AP_A) farkinin %5'lik dilimi SIFIRIN USTUNDE.
  Aksi halde A korunur ve kusur belgelenmekle yetinilir.

DIKKAT: bu, holdout'un IKINCI kullanimidir (ilki modelin kendi
degerlendirmesiydi). Tek bir ikili karsilastirma icin aciliyor ve sonucu
buna gore tartilmalidir - holdout ne kadar cok acilirsa o kadar asinir.

Kullanim:
    python -m sis_modeli.veri_kalitesi            # teshis
    python -m sis_modeli.veri_kalitesi --ab       # A/B (holdout acar)
"""

import argparse
from collections import Counter

# Ciy noktasi bildirimi guvenilmez olan yillar (yukaridaki kanitlar).
CIY_KUSURLU_YILLAR = (2021, 2022, 2023)


def ciy_temiz(kayitlar: list, yillar=CIY_KUSURLU_YILLAR) -> list:
    """Ciy noktasi kusurlu yillari cikarir.

    Yil bazinda suzer - satir bazinda DEGIL. Satir bazinda (ornegin
    'spread=0 olanlari at') suzmek, etiketle iliskili bir degiskene gore
    secim yapmak olurdu ve gercek sis olaylarini da silerdi."""
    disari = set(yillar)
    return [r for r in kayitlar if int(str(r["zaman"])[:4]) not in disari]


def spread_imzasi(kayitlar: list, donemler) -> list:
    """Donem basina spread=0 orani, bunlarin CAVOK payi ve ortalama spread.

    Kusurun teshis edildigi olcu budur; karar surecinin kendisi kodda
    kalsin diye fonksiyon olarak duruyor."""
    cikti = []
    for ad, yillar in donemler:
        s = [r for r in kayitlar if int(str(r["zaman"])[:4]) in yillar]
        sp = [r["spread"] for r in s if r.get("spread") is not None]
        if not sp:
            continue
        sifir = [r for r in s if r.get("spread") == 0 and r.get("gorus") is not None]
        cavok = sum(1 for r in sifir if r["gorus"] >= 9999)
        cikti.append({
            "donem": ad, "n": len(s),
            "sifir_orani": sum(1 for x in sp if x == 0) / len(sp),
            "cavok_payi": cavok / len(sifir) if sifir else 0.0,
            "ortalama_spread": sum(sp) / len(sp),
            "negatif": sum(1 for x in sp if x < 0),
        })
    return cikti


def ay_eslenmis_sapma(kayitlar: list, kusurlu=CIY_KUSURLU_YILLAR) -> list:
    """Ay bazinda: komsu donemlerin ortalama spread'i - kusurlu donemin.

    Ay eslemesi sart: mevsim kompozisyonu farkliysa ham ortalama farki
    kusur sanilabilir."""
    kusurlu = set(kusurlu)
    cikti = []
    for ay in range(1, 13):
        a = [r["spread"] for r in kayitlar
             if r.get("ay") == ay and r.get("spread") is not None]
        if not a:
            continue
        k = [r["spread"] for r in kayitlar if r.get("ay") == ay
             and r.get("spread") is not None
             and int(str(r["zaman"])[:4]) in kusurlu]
        t = [r["spread"] for r in kayitlar if r.get("ay") == ay
             and r.get("spread") is not None
             and int(str(r["zaman"])[:4]) not in kusurlu]
        if not k or not t:
            continue
        cikti.append({"ay": ay, "kusurlu": sum(k) / len(k),
                      "temiz": sum(t) / len(t),
                      "sapma": sum(t) / len(t) - sum(k) / len(k)})
    return cikti


def eslesmis_fark_araligi(kayitlar: list, a_tahmin: list, b_tahmin: list,
                          gercek: list, olcu, tekrar: int = 400,
                          tohum: int = 0) -> tuple:
    """(B - A) farkinin gun bazli ESLESTIRILMIS blok bootstrap %5-95 araligi.

    Eslestirilmis olmasi onemli: ayni yeniden orneklenmis gunlerde iki model
    de puanlanir, boylece ortak gun-gurultusu farkta sadelesir. Ayri ayri
    hesaplanan iki aralik bu sadelesmeyi kaciracagi icin farki gereginden
    belirsiz gosterirdi."""
    import random
    from collections import defaultdict

    gun_indeks = defaultdict(list)
    for i, r in enumerate(kayitlar):
        gun_indeks[r["gun"]].append(i)
    gunler = list(gun_indeks)
    if not gunler:
        return (0.0, 0.0)

    rastgele = random.Random(tohum)
    farklar = []
    for _ in range(tekrar):
        idx = []
        for _ in gunler:
            idx.extend(gun_indeks[rastgele.choice(gunler)])
        y = [gercek[i] for i in idx]
        if not any(y):
            continue
        farklar.append(olcu([b_tahmin[i] for i in idx], y)
                       - olcu([a_tahmin[i] for i in idx], y))
    if not farklar:
        return (0.0, 0.0)
    farklar.sort()
    return (farklar[int(0.05 * len(farklar))],
            farklar[min(int(0.95 * len(farklar)), len(farklar) - 1)])


def _teshis(ham: list) -> None:
    donemler = (("2011-2020", set(range(2011, 2021))),
                ("2021-2023", set(range(2021, 2024))),
                ("2024-2026", set(range(2024, 2027))))
    print("=== Çiy noktası imzası ===")
    print(f"  {'dönem':<12}{'n':>8}{'spread=0':>10}{'bunlar CAVOK':>14}"
          f"{'ort. spread':>13}{'negatif':>9}")
    for s in spread_imzasi(ham, donemler):
        print(f"  {s['donem']:<12}{s['n']:>8}{100*s['sifir_orani']:>9.2f}%"
              f"{100*s['cavok_payi']:>13.1f}%{s['ortalama_spread']:>13.2f}"
              f"{s['negatif']:>9}")

    print("\n=== Ay eşlenmiş spread sapması (temiz − kusurlu) ===")
    sapmalar = ay_eslenmis_sapma(ham)
    print("  " + " ".join(f"{s['ay']:>5}" for s in sapmalar))
    print("  " + " ".join(f"{s['sapma']:>+5.2f}" for s in sapmalar))
    ort = sum(s["sapma"] for s in sapmalar) / len(sapmalar)
    ayni_yon = sum(1 for s in sapmalar if s["sapma"] > 0)
    print(f"  ortalama {ort:+.2f} °C, {ayni_yon}/{len(sapmalar)} ay aynı yönde")

    print("\n=== Dışlamanın bedeli ===")
    for ad, yillar in donemler[:2]:
        s = [r for r in ham if int(str(r["zaman"])[:4]) in yillar]
        gun = len({str(r["zaman"])[:10] for r in s if r.get("sis")})
        print(f"  {ad}: {len(s):>7} gözlem, "
              f"{sum(1 for r in s if r.get('sis')):>4} sisli gözlem, "
              f"{gun:>4} ayrı sisli gün")


def _ab(ham: list) -> int:
    from sis_modeli import bolme, degerlendir, hedef, model
    from sis_modeli.egit import ALANLAR

    aday = hedef.onset_adaylari(hedef.hazirla(ham))
    egitim_a = bolme.gelistirme(aday)
    egitim_b = ciy_temiz(egitim_a)
    test = bolme.holdout(aday)
    gercek = [bool(r["hedef"]) for r in test]

    print("=== A/B: çiy noktası kusurlu yılları dışlamak modeli düzeltiyor mu? ===")
    print("ÖNCEDEN İLAN EDİLEN KURAL: B yalnızca eşleştirilmiş blok bootstrap'te")
    print("(AP_B − AP_A) farkının %5'lik dilimi sıfırın üstündeyse dondurulur.\n")
    print(f"A eğitim (2011-2023): {len(egitim_a):>7} an, "
          f"{sum(r['hedef'] for r in egitim_a):>4} pozitif, "
          f"{len({r['gun'] for r in egitim_a if r['hedef']}):>3} ayrı gün")
    print(f"B eğitim (kusurlusuz): {len(egitim_b):>6} an, "
          f"{sum(r['hedef'] for r in egitim_b):>4} pozitif, "
          f"{len({r['gun'] for r in egitim_b if r['hedef']}):>3} ayrı gün")
    print(f"HOLDOUT (2024-2026):  {len(test):>7} an, {sum(gercek):>4} pozitif\n")

    tahmin = {}
    for ad, egitim in (("A (mevcut)", egitim_a), ("B (temiz)", egitim_b)):
        katsayilar, tablolar, l2 = model.egit_secerek(egitim, ALANLAR)
        tahmin[ad] = [model.olasilik(katsayilar, r, tablolar) for r in test]
        print(f"{ad}: seçilen L2 = {l2:.0f}")
    iklim = model.iklim_baseline(egitim_a)
    iklim_t = [model.iklim_tahmin(iklim, r) for r in test]

    print(f"\n{'model':<14}{'Brier×10⁴':>11}{'BSS':>8}{'AP':>8}{'AP %5–%95':>18}")
    for ad, p in tahmin.items():
        alt, ust = degerlendir.blok_guven_araligi(
            test, p, gercek, degerlendir.ortalama_kesinlik)
        print(f"{ad:<14}{1e4*degerlendir.brier(p, gercek):>11.2f}"
              f"{degerlendir.brier_skill(p, gercek, iklim_t):>8.3f}"
              f"{degerlendir.ortalama_kesinlik(p, gercek):>8.3f}"
              f"{f'{alt:.3f} – {ust:.3f}':>18}")

    alt, ust = eslesmis_fark_araligi(test, tahmin["A (mevcut)"],
                                     tahmin["B (temiz)"], gercek,
                                     degerlendir.ortalama_kesinlik)
    fark = (degerlendir.ortalama_kesinlik(tahmin["B (temiz)"], gercek)
            - degerlendir.ortalama_kesinlik(tahmin["A (mevcut)"], gercek))
    print(f"\nAP farkı (B − A): {fark:+.3f}   eşleştirilmiş %5–%95: "
          f"{alt:+.3f} – {ust:+.3f}")
    if alt > 0:
        print("KARAR: kural sağlandı → B dondurulur.")
    else:
        print("KARAR: kural SAĞLANMADI → A korunur, kusur belgelenir.")
        print("       (Dışlamanın getirdiği temizlik, kaybedilen %22 olayı"
              " telafi etmiyor.)")
    return 0


def main(argv=None) -> int:
    from pathlib import Path

    from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku

    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    a.add_argument("--ab", action="store_true",
                   help="A/B karsilastirmasi - HOLDOUT ACAR")
    secenek = a.parse_args(argv)

    ham = [r for r in veri_oku(secenek.veri) if str(r["zaman"])[:4] >= "2011"]
    _teshis(ham)
    return _ab(ham) if secenek.ab else 0


if __name__ == "__main__":
    raise SystemExit(main())
