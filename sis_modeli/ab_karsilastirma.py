#!/usr/bin/env python3
"""Model A (görüşlü, dondurulmuş ltfj_sis_olasilik) vs Model B (görüşsüz,
sis_modeli/olusum_egit) - HOLDOUT (2024-2026) üzerinde üç soru:

1. Lead-time gain: B, A'dan kaç dakika önce eşiği geçiyor?
2. Conditional value: A aynı bandındayken B düşük/orta/yüksek olduğunda
   gerçek sis oluşma oranı nasıl değişiyor?
3. Event detection: B'nin eşiği geçtiği bağımsız olay oranı (event-level
   recall) - olusum_holdout_degerlendir.py ile AYNI yöntem/veri, çapraz
   kontrol için burada da hesaplanıyor.

NOT (dürüstlük): holdout (2024-2026) hem Model A hem Model B için DAHA ÖNCE
ayrı ayrı açılmıştı (TEK ATIŞ raporlandı). Bu betik o sonuçları DEĞİŞTİRMEZ/
yeniden ayarlamaz - sadece İKİ ZATEN DONDURULMUŞ modelin tahminlerini AYNI
holdout satırları üzerinde EŞLEŞTİRİP yeni, tanımlayıcı (descriptive) bir
çapraz analiz yapar. Hiçbir model burada yeniden eğitilmez/ayarlanmaz -
Model B'nin katsayıları, olusum_holdout_degerlendir.py'deki AYNI eğitim
kümesi ve yöntemle (embargo'lu tam gelişme dönemi, egit_secerek) yeniden
üretilir; bu deterministik bir tekrar-hesaplama, yeni bir "atış" değil.

Kullanım:
    python -m sis_modeli.ab_karsilastirma
"""
import sys
from datetime import timedelta
from pathlib import Path

from sis_modeli import bolme, degerlendir, hedef, model, olay_degerlendirme
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku
from sis_modeli.olusum_egit import ALANLAR, hava_sutunu_ekle

import ltfj_sis_olasilik as model_a

ESIKLER = (0.05, 0.10)
LEAD_TIME_ESIGI = 0.05
# Modelin KENDİ ufku 3 saat (hedef.UFUK_SAAT) - bunun ötesindeki bir "eşik
# geçişi" aslında YAKLAŞAN olayı değil, o noktanın KENDİ 3 saatlik
# penceresini tahmin ediyor demektir; 6 saate kadar bakmak sahte/erken
# sinyal üretebilir. İki pencereyi de raporluyoruz (3s = tasarım ufkuyla
# tutarlı birincil, 6s = daha geniş keşif).
BAKIS_PENCERELERI = (3.0, 6.0)
ADIM_DK = 30
A_BANTLARI = [(0, 0.01), (0.01, 0.02), (0.02, 0.05), (0.05, 0.10),
             (0.10, 0.20), (0.20, 1.01)]
# A'nın kendisi zaten yuksek dedigi bolge - asil operasyonel soru burada:
# "A %12 derken B'ye bakmanin bir anlami var mi?" (bkz. README, kullanicinin
# takip talebi).
A_YUKSEK_BANTLARI = [(0.05, 0.10), (0.10, 0.20), (0.20, 1.01)]
INCE_SINIR = 30
GUN_INCE_SINIR = 5   # bu kadardan az AYRI GUN varsa oran/CI guvenilmez sayilir


def model_a_tahmin(r: dict) -> float | None:
    """Model A'nın (dondurulmuş, görüşlü) tahminini arşiv satırından üretir.
    Eksik sıcaklık/çiy noktasında None döner (model zaten None döndürür)."""
    sicaklik, cig = r.get("sicaklik"), r.get("cig_noktasi")
    if sicaklik is None or cig is None:
        return None
    return model_a.olasilik(
        spread=sicaklik - cig, gorus=r.get("gorus"), saat=r.get("saat"),
        ruzgar_kuzey=r.get("ruzgar_kuzey"), spread_egilim_3=r.get("spread_egilim_3"))


def _ilk_esik_zamani(baslangic, tahmin_map: dict, esik: float, n_adim: int):
    """Onset'ten geriye tarar (en uzaktan en yakına); EN ERKEN eşik geçişini
    döner - bulunamazsa None."""
    for k in range(n_adim, 0, -1):
        t = baslangic - timedelta(minutes=ADIM_DK * k)
        p = tahmin_map.get(t)
        if p is not None and p >= esik:
            return t
    return None


def lead_time_analizi(olaylar: list, tahmin_a: dict, tahmin_b: dict,
                      esik: float = LEAD_TIME_ESIGI,
                      pencereler=BAKIS_PENCERELERI) -> dict:
    """Her bakış penceresi için: kaç olayda sadece A/sadece B/ikisi de sinyal
    verdi, ve ikisi de verdiğinde B'nin A'ya göre lead-time farkı (dakika,
    + = B daha erken)."""
    sonuc = {}
    for bakis_saat in pencereler:
        n_adim = int(round(bakis_saat * 60 / ADIM_DK))
        farklar = []
        sayac = {"ikisi_de_yok": 0, "sadece_a": 0, "sadece_b": 0, "ikisi_de_var": 0}
        for o in olaylar:
            ta = _ilk_esik_zamani(o["baslangic"], tahmin_a, esik, n_adim)
            tb = _ilk_esik_zamani(o["baslangic"], tahmin_b, esik, n_adim)
            if ta is None and tb is None:
                sayac["ikisi_de_yok"] += 1
            elif ta is None:
                sayac["sadece_b"] += 1
            elif tb is None:
                sayac["sadece_a"] += 1
            else:
                sayac["ikisi_de_var"] += 1
                lead_a = (o["baslangic"] - ta).total_seconds() / 60
                lead_b = (o["baslangic"] - tb).total_seconds() / 60
                farklar.append(lead_b - lead_a)
        farklar.sort()
        n = len(farklar)
        sonuc[bakis_saat] = {
            **sayac, "farklar": farklar,
            "ortalama": sum(farklar) / n if n else None,
            "medyan": (farklar[n // 2] if n % 2
                      else (farklar[n // 2 - 1] + farklar[n // 2]) / 2) if n else None,
        }
    return sonuc


def kosullu_deger_tertil(ortak_dt: list, tahmin_a: dict, tahmin_b: dict,
                         yer: dict, bantlar=A_BANTLARI) -> list:
    """Her A bandını KENDİ İÇİNDE B'ye göre üç eşit parçaya (tertil) böler -
    global bir B eşiği kullanmaz, çünkü A ve B ilişkili (aynı atmosferik
    girdileri paylaşıyorlar) ve global bölünme üst bantlarda boş hücre
    üretir (bkz. README - bu betiğin geliştirilme geçmişi)."""
    cikti = []
    for alt, ust in bantlar:
        grup_tum = [dt for dt in ortak_dt if alt <= tahmin_a[dt] < ust]
        if not grup_tum:
            continue
        siral = sorted(grup_tum, key=lambda dt: tahmin_b[dt])
        n_tum = len(siral)
        s1, s2 = round(n_tum / 3), round(2 * n_tum / 3)
        kesimler = {"düşük": siral[:s1], "orta": siral[s1:s2], "yüksek": siral[s2:]}
        satir = {"bant": (alt, ust), "kesimler": {}}
        for etiket, grup in kesimler.items():
            n = len(grup)
            poz = sum(1 for dt in grup if yer[dt]["hedef"])
            satir["kesimler"][etiket] = {
                "n": n, "poz": poz, "oran": poz / n if n else None,
                "b_min": tahmin_b[grup[0]] if grup else None,
                "b_max": tahmin_b[grup[-1]] if grup else None,
            }
        oranlar = [satir["kesimler"][e]["oran"] for e in ("düşük", "orta", "yüksek")]
        satir["monoton"] = all(a is not None and b is not None and a <= b
                               for a, b in zip(oranlar, oranlar[1:]))
        cikti.append(satir)
    return cikti


def _oran_ci(dtler: list, yer: dict, tekrar: int = 400) -> dict:
    """Bir grubun gerceklesme orani + GUN bazinda blok bootstrap %5-95
    araligi (degerlendir.blok_guven_araligi). 'tahminler' argumani metrik
    tarafindan kullanilmiyor (olcu sadece gercekleri kullaniyor) - imza
    uyumu icin sifir listesi veriliyor."""
    n = len(dtler)
    if n == 0:
        return {"n": 0, "poz": 0, "oran": None, "ci": (None, None), "gun_sayisi": 0}
    kayitlar_alt = [yer[dt] for dt in dtler]
    gercekler = [bool(yer[dt]["hedef"]) for dt in dtler]
    poz = sum(gercekler)
    ci = degerlendir.blok_guven_araligi(
        kayitlar_alt, [0.0] * n, gercekler,
        lambda p, y: sum(y) / len(y) if y else 0.0, tekrar=tekrar)
    return {"n": n, "poz": poz, "oran": poz / n, "ci": ci,
           "gun_sayisi": len({r["gun"] for r in kayitlar_alt})}


def derinlemesine_a_yuksek(ortak_dt: list, tahmin_a: dict, tahmin_b: dict,
                           yer: dict, bantlar=A_YUKSEK_BANTLARI) -> list:
    """A >= %5 bolgesinde, her bandi KENDI ICINDE B'ye gore tertile ayirir
    ve HER tertil icin gun-bazli blok bootstrap CI hesaplar (naif satir-
    bazli bir anlamlilik testi ayni sis olayinin ardisik satirlarini
    bagimsiz sayardi - bu yuzden CI mutlaka GUN bazinda).

    Ayrica B'nin bant ICINDE tek basina ayristirma gucunu (AP) ve o
    bandin taban oranini (sabit tahmin) karsilastirir - "B, A'nin bu
    bandinda yeni bilgi mi tasiyor yoksa A'yi mi tekrarliyor" sorusunun
    dogrudan cevabi."""
    cikti = []
    for alt, ust in bantlar:
        grup_tum = [dt for dt in ortak_dt if alt <= tahmin_a[dt] < ust]
        satir = {"bant": (alt, ust), "n_tum": len(grup_tum)}
        if not grup_tum:
            cikti.append(satir)
            continue

        taban_oran = sum(1 for dt in grup_tum if yer[dt]["hedef"]) / len(grup_tum)
        tahmin_b_listesi = [tahmin_b[dt] for dt in grup_tum]
        gercek_listesi = [bool(yer[dt]["hedef"]) for dt in grup_tum]
        satir["taban_oran"] = taban_oran
        satir["b_ap"] = degerlendir.ortalama_kesinlik(tahmin_b_listesi, gercek_listesi)
        satir["b_ap_taban"] = taban_oran   # sabit-tahmin AP'si = taban oran (nadir olayda)

        siral = sorted(grup_tum, key=lambda dt: tahmin_b[dt])
        n_tum = len(siral)
        s1, s2 = round(n_tum / 3), round(2 * n_tum / 3)
        kesimler = {"düşük": siral[:s1], "orta": siral[s1:s2], "yüksek": siral[s2:]}
        satir["kesimler"] = {}
        for etiket, grup in kesimler.items():
            bilgi = _oran_ci(grup, yer)
            bilgi["b_min"] = tahmin_b[grup[0]] if grup else None
            bilgi["b_max"] = tahmin_b[grup[-1]] if grup else None
            satir["kesimler"][etiket] = bilgi
        cikti.append(satir)
    return cikti


def yillik_kararlilik(ortak_dt: list, tahmin_a: dict, tahmin_b: dict, yer: dict,
                      bantlar=A_YUKSEK_BANTLARI, yillar=(2024, 2025, 2026)) -> list:
    """AYNI (tum-donem) tertil kesim noktalarini kullanarak, her bandi
    YIL bazinda kirar - 'iliski her yil ayni yonde mi' sorusu icin. Kesim
    noktalari yil basina YENIDEN hesaplanmiyor (o kadar az veriyle kesim
    noktasinin kendisi anlamsizlasirdi); sadece HANGI yila dustugu
    raporlaniyor."""
    cikti = []
    for alt, ust in bantlar:
        grup_tum = [dt for dt in ortak_dt if alt <= tahmin_a[dt] < ust]
        if not grup_tum:
            cikti.append({"bant": (alt, ust), "yillar": {}})
            continue
        siral = sorted(grup_tum, key=lambda dt: tahmin_b[dt])
        n_tum = len(siral)
        s1, s2 = round(n_tum / 3), round(2 * n_tum / 3)
        kesimler = {"düşük": siral[:s1], "orta": siral[s1:s2], "yüksek": siral[s2:]}
        yil_satiri = {}
        for yil in yillar:
            yil_satiri[yil] = {}
            for etiket, grup in kesimler.items():
                grup_yil = [dt for dt in grup if yer[dt]["dt"].year == yil]
                yil_satiri[yil][etiket] = _oran_ci(grup_yil, yer, tekrar=100)
        cikti.append({"bant": (alt, ust), "yillar": yil_satiri})
    return cikti


def main() -> int:
    if not VARSAYILAN_VERI.exists():
        print(f"HATA: {VARSAYILAN_VERI} yok.", file=sys.stderr)
        return 1

    ham = [r for r in veri_oku(VARSAYILAN_VERI) if r["zaman"][:4] >= str(bolme.ILK_YIL)]
    kayitlar = hava_sutunu_ekle(hedef.hazirla(ham))
    aday = hedef.onset_adaylari(kayitlar)

    gelistirme = bolme.gelistirme(aday)
    egitim_b = bolme.embargo_penceresi(gelistirme, min(bolme.HOLDOUT_YILLARI))
    test = bolme.holdout(aday)
    print(f"Eğitim (B için, sınır embargolu): {len(egitim_b)} an")
    print(f"HOLDOUT: {len(test)} an, {sum(r['hedef'] for r in test)} pozitif\n")

    katsayilar_b, tablolar_b, l2_b = model.egit_secerek(egitim_b, ALANLAR)
    print(f"Model B seçilen L2: {l2_b:.0f}\n")

    tahmin_a, tahmin_b = {}, {}
    eksik_a = 0
    for r in test:
        tahmin_b[r["dt"]] = model.olasilik(katsayilar_b, r, tablolar_b)
        pa = model_a_tahmin(r)
        if pa is None:
            eksik_a += 1
            continue
        tahmin_a[r["dt"]] = pa
    print(f"Model A eksik tahmin (spread/görüş yok): {eksik_a} / {len(test)}\n")

    yer = {r["dt"]: r for r in kayitlar}
    olaylar = [o for o in olay_degerlendirme.bagimsiz_olaylar(kayitlar)
              if o["baslangic"].year in bolme.HOLDOUT_YILLARI]

    # ------------------------------------------------------------- soru 3
    temsilciler = olay_degerlendirme.olay_temsilci_satirlari(kayitlar, olaylar)
    print(f"=== 3) EVENT DETECTION (holdout, {len(olaylar)} bağımsız olay) ===")
    print(f"{'model':<10}{'eşik':>6}{'toplam':>8}{'yakalanan':>11}{'duyarlılık':>12}")
    for ad, tmap in (("Model A", tahmin_a), ("Model B", tahmin_b)):
        for e in olay_degerlendirme.olay_bazli_esik_tablosu(temsilciler, tmap, ESIKLER):
            print(f"{ad:<10}{100*e['esik']:>5.0f}%{e['toplam_olay']:>8}"
                  f"{e['yakalanan']:>11}{100*e['duyarlilik']:>11.1f}%")
    print()

    # ------------------------------------------------------------- soru 1
    print(f"=== 1) LEAD-TIME GAIN (eşik ≥%{100*LEAD_TIME_ESIGI:g}) ===")
    lt = lead_time_analizi(olaylar, tahmin_a, tahmin_b)
    for bakis_saat, s in lt.items():
        etiket_pencere = ("tasarım ufkuyla tutarlı" if bakis_saat == min(BAKIS_PENCERELERI)
                          else "geniş keşif")
        print(f"\n-- Bakış penceresi: {bakis_saat:g} saat ({etiket_pencere}) --")
        print(f"  İkisi de sinyal vermedi: {s['ikisi_de_yok']}   "
              f"Sadece A: {s['sadece_a']}   Sadece B: {s['sadece_b']}   "
              f"İkisi de var: {s['ikisi_de_var']}")
        if s["farklar"]:
            f = s["farklar"]
            print(f"  B'nin A'ya göre lead-time farkı (dakika, +: B daha erken): "
                  f"ortalama={s['ortalama']:+.1f}, medyan={s['medyan']:+.1f}, "
                  f"min={f[0]:+.0f}, max={f[-1]:+.0f} (n={len(f)})")
    print()

    # ------------------------------------------------------------- soru 2
    print("=== 2) CONDITIONAL VALUE - BANT-İÇİ TERTİL (düşük/orta/yüksek) ===\n")
    ortak_dt = [dt for dt in tahmin_a if dt in tahmin_b]
    tertiller = kosullu_deger_tertil(ortak_dt, tahmin_a, tahmin_b, yer)
    print(f"{'A bandı':<14}{'B tertili':<10}{'B aralığı':<20}{'n':>7}{'poz':>6}{'oran':>9}")
    for satir in tertiller:
        alt, ust = satir["bant"]
        bant_etiket = f"%{100*alt:g}-{100*ust:g}"
        for etiket in ("düşük", "orta", "yüksek"):
            k = satir["kesimler"][etiket]
            aralik = (f"%{100*k['b_min']:.2f}–{100*k['b_max']:.2f}"
                     if k["b_min"] is not None else "–")
            oran_str = f"{100*k['oran']:.1f}%" if k["oran"] is not None else "–"
            print(f"{bant_etiket:<14}{etiket:<10}{aralik:<20}{k['n']:>7}"
                  f"{k['poz']:>6}{oran_str:>9}"
                  + ("  ⚠ ince" if 0 < k["n"] < INCE_SINIR else ""))
        print(f"{'':<14}{'-> monoton artan mı?':<30}"
              f"{'evet' if satir['monoton'] else 'HAYIR':>12}")
        print()

    # ------------------------------------------------------ soru 4 (derin)
    print("=== 4) A ≥%5 DERİNLEMESİNE (gün-bazlı blok bootstrap CI ile) ===\n")
    derin = derinlemesine_a_yuksek(ortak_dt, tahmin_a, tahmin_b, yer)
    for satir in derin:
        alt, ust = satir["bant"]
        bant_etiket = f"%{100*alt:g}-{100*ust:g}"
        if satir["n_tum"] == 0:
            print(f"{bant_etiket}: veri yok\n")
            continue
        print(f"-- A bandı {bant_etiket}  (n={satir['n_tum']}, taban oran="
              f"%{100*satir['taban_oran']:.1f}, B'nin bant-içi AP'si="
              f"{satir['b_ap']:.3f} vs sabit-tahmin AP'si {satir['b_ap_taban']:.3f}) --")
        print(f"{'B tertili':<10}{'B aralığı':<18}{'n':>6}{'gün':>5}{'poz':>6}"
              f"{'oran':>9}{'  %5–95 CI':<16}")
        for etiket in ("düşük", "orta", "yüksek"):
            k = satir["kesimler"][etiket]
            if k["n"] == 0:
                print(f"{etiket:<10}{'–':<18}{0:>6}")
                continue
            aralik = f"%{100*k['b_min']:.2f}–{100*k['b_max']:.2f}"
            alt_ci, ust_ci = k["ci"]
            ci_str = f"{100*alt_ci:.1f}–{100*ust_ci:.1f}%"
            ince = k["gun_sayisi"] < GUN_INCE_SINIR
            print(f"{etiket:<10}{aralik:<18}{k['n']:>6}{k['gun_sayisi']:>5}"
                  f"{k['poz']:>6}{100*k['oran']:>8.1f}%  {ci_str:<16}"
                  + ("  ⚠ az gün" if ince else ""))
        dusuk_ci = satir["kesimler"]["düşük"]["ci"]
        yuksek_ci = satir["kesimler"]["yüksek"]["ci"]
        if None not in dusuk_ci and None not in yuksek_ci:
            ortusuyor = not (yuksek_ci[0] > dusuk_ci[1] or dusuk_ci[0] > yuksek_ci[1])
            print(f"  düşük vs yüksek CI: {'ÖRTÜŞÜYOR (anlamlı fark YOK)' if ortusuyor else 'AYRIŞIYOR (fark muhtemelen gerçek)'}")
        print()

    # ------------------------------------------------------ soru 6 (yıllık)
    print("=== 5) YILLIK KARARLILIK (aynı kesim noktaları, yıl bazında kırılım) ===\n")
    yillik = yillik_kararlilik(ortak_dt, tahmin_a, tahmin_b, yer)
    for satir in yillik:
        alt, ust = satir["bant"]
        bant_etiket = f"%{100*alt:g}-{100*ust:g}"
        if not satir["yillar"]:
            print(f"{bant_etiket}: veri yok\n")
            continue
        print(f"-- A bandı {bant_etiket} --")
        print(f"{'yıl':<6}{'düşük':>16}{'orta':>16}{'yüksek':>16}")
        for yil, gruplar in satir["yillar"].items():
            hucreler = []
            for etiket in ("düşük", "orta", "yüksek"):
                k = gruplar[etiket]
                if k["n"] == 0:
                    hucreler.append("n=0")
                else:
                    hucreler.append(f"%{100*k['oran']:.0f} (n={k['n']},gün={k['gun_sayisi']})")
            print(f"{yil:<6}{hucreler[0]:>16}{hucreler[1]:>16}{hucreler[2]:>16}")
        print()
    print("NOT: yıl başına ayrı gün sayıları çok küçükse (⚠ az gün eşiği: "
         f"{GUN_INCE_SINIR}) bu kırılım yön hakkında GÜVENİLİR bir sonuç "
         "vermez - bu durumda dürüstçe 'veri yetersiz' denmeli, sahte bir "
         "'her yıl aynı yönde' iddiası kurulmamalı.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
