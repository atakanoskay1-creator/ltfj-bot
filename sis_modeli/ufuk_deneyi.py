#!/usr/bin/env python3
"""Model B icin cok-ufuklu (lead-time) deneyi: 30dk / 1h / 2h / 3h.

SORU: "Gorusu kullanmadan sis olusumu ne kadar onceden tahmin edilebiliyor?"

Eger 3 saatlik ufuk zayif ama 30-60 dakikada atmosferik sinyal anlamliysa
bu BASARISIZLIK degil, onemli bir bilimsel sonuctur (bkz. arastirma raporu
Bolum 15) - spread doymus havada saatlerce ayni kalabilir ("seviye" bilgisi)
ama "NE ZAMAN" sorusu kisa ufuklarda daha kolay cevaplanabilir.

Her ufuk kendi WALK-FORWARD dongusunu KENDI BASINA calistirir (hedef.hazirla
her ufuk icin ayri cagrilir) - holdout HICBIR ufukta acilmaz; bu betik
yalnizca gelistirme donemini (2011-2023) kullanir.

Kullanim:
    python -m sis_modeli.ufuk_deneyi
"""

import argparse
from pathlib import Path

from sis_modeli import bolme, degerlendir, hedef, model, olay_degerlendirme
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku
from sis_modeli.olusum_egit import ALANLAR, hava_sutunu_ekle

UFUKLAR_SAAT = (0.5, 1.0, 2.0, 3.0)


def _etiket(ufuk: float) -> str:
    return f"{int(round(ufuk * 60))}dk" if ufuk < 1 else f"{ufuk:g}h"


def calistir(ham: list, ufuk_saat: float, alanlar: list = ALANLAR,
            embargo: bool = True) -> dict:
    """Tek bir ufuk icin walk-forward calistirir; satir-duzeyi VE
    event-duzeyi (olay basina TEK tahmin) sonuclari birlikte doner."""
    kayitlar = hava_sutunu_ekle(hedef.hazirla(ham, ufuk_saat=ufuk_saat))
    aday = hedef.onset_adaylari(kayitlar)
    gelistirme = bolme.gelistirme(aday)

    gercek, tahmin, saatler, gunler = [], [], [], []
    tahmin_map = {}
    for eg_yillari, test_yillari in bolme.foldlar():
        egitim = (bolme.ayir_embargolu(gelistirme, eg_yillari, sonraki_yil=min(test_yillari))
                  if embargo else bolme.ayir(gelistirme, eg_yillari))
        test = bolme.ayir(gelistirme, test_yillari)
        if not test or not any(r["hedef"] for r in test):
            continue
        katsayilar, tablolar, _l2 = model.egit_secerek(egitim, alanlar)
        for r in test:
            p = model.olasilik(katsayilar, r, tablolar)
            gercek.append(bool(r["hedef"]))
            tahmin.append(p)
            saatler.append(r["dt"].hour)
            gunler.append(r["gun"])
            tahmin_map[r["dt"]] = p

    taban = sum(gercek) / len(gercek) if gercek else 0.0
    iklim = [taban] * len(gercek)
    # Saate KOSULLU iklim: duz taban orandan daha zor bir referans.
    # Modelin degiskenleri arasinda `saat` de var; duz orana gore olculen
    # beceri "gunluk dongusu ogrenildi"yi atmosferik beceri gibi
    # gosterebilir (bkz. degerlendir.kosullu_iklim).
    iklim_saat = degerlendir.kosullu_iklim(saatler, gercek)

    # Event-level: TUM (onset-filtresiz) kayitlardan bagimsiz olaylari bul,
    # holdout yillarindakileri disarida birak (gelistirme evreniyle tutarli).
    olaylar = [o for o in olay_degerlendirme.bagimsiz_olaylar(kayitlar)
              if o["baslangic"].year not in bolme.HOLDOUT_YILLARI]
    temsilciler = olay_degerlendirme.olay_temsilci_satirlari(
        kayitlar, olaylar, ufuk_saat=ufuk_saat)
    olay_esikleri = olay_degerlendirme.olay_bazli_esik_tablosu(temsilciler, tahmin_map)

    return {
        "n": len(gercek), "poz": sum(gercek),
        "brier": degerlendir.brier(tahmin, gercek),
        "bss": degerlendir.brier_skill(tahmin, gercek, iklim),
        "ap": degerlendir.ortalama_kesinlik(tahmin, gercek),
        "log_loss": degerlendir.log_loss(tahmin, gercek) if gercek else 0.0,
        "lss": degerlendir.log_skill(tahmin, gercek, iklim),
        "lss_saat": degerlendir.log_skill(tahmin, gercek, iklim_saat),
        "roc_auc": degerlendir.roc_auc(tahmin, gercek),
        "olay_sayisi": sum(1 for t in temsilciler if t["temsilci"] is not None),
        "olay_esikleri": olay_esikleri,
        # Esli bootstrap icin ham satirlar (gun = blok anahtari).
        "satirlar": (gunler, tahmin, gercek),
    }


def _lss_olcusu(tahminler, gercekler):
    """Iklim referansi HER REPLIKANIN KENDI orneginden kurulur - sabit
    bir referans kullanmak, orneklemin taban orani oynadikca beceriyi
    yapay olarak oynatirdi."""
    n = len(gercekler) or 1
    taban = sum(1 for y in gercekler if y) / n
    return degerlendir.log_skill(tahminler, gercekler, [taban] * len(gercekler))


def _ap_lift_olcusu(tahminler, gercekler):
    """AP / taban oran. Ham AP ufuk genisledikce OLAY SIKLASTIGI icin
    de yukselir; rastgele siniflandiricinin AP'si taban orana esittir,
    bu yuzden adil kiyas icin bolunur."""
    n = len(gercekler) or 1
    taban = sum(1 for y in gercekler if y) / n
    if taban <= 0:
        return 0.0
    return degerlendir.ortalama_kesinlik(tahminler, gercekler) / taban


def _bootstrap_yaz(sonuclar: dict, tekrar: int) -> None:
    seriler = {_etiket(u): s["satirlar"] for u, s in sonuclar.items()}
    for baslik, olcu in (("LSS", _lss_olcusu), ("AP/taban", _ap_lift_olcusu)):
        araliklar, farklar = degerlendir.esli_blok_guven_araligi(
            seriler, olcu, tekrar=tekrar)
        print(f"\n{baslik} — gün-blok EŞLİ bootstrap ({tekrar} tekrar, %5–%95)")
        for u, s in sonuclar.items():
            ad = _etiket(u)
            alt, ust = araliklar[ad]
            print(f"  {ad:<6}{olcu(s['satirlar'][1], s['satirlar'][2]):>8.3f}"
                  f"   [{alt:>6.3f}, {ust:>6.3f}]")
        print(f"  farklar (a − b; aralık 0'ı İÇERİYORSA fark gürültüden "
              f"ayırt edilemez):")
        for (a, b), (alt, ust, orta, oran) in farklar.items():
            karar = "belirsiz" if alt <= 0 <= ust else "AYIRT EDİLİR"
            print(f"    {a:>5} − {b:<5} {orta:>7.3f}  "
                  f"[{alt:>6.3f}, {ust:>6.3f}]  a>b: %{100*oran:>5.1f}  {karar}")


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    a.add_argument("--bootstrap", type=int, default=0, metavar="TEKRAR",
                   help="gun-blok ESLI bootstrap; ufuklar AYNI gun "
                        "orneginde kiyaslanir (onerilen: 200)")
    secenek = a.parse_args(argv)
    if not secenek.veri.exists():
        import sys
        print(f"HATA: {secenek.veri} yok.", file=sys.stderr)
        return 1

    ham = [r for r in veri_oku(secenek.veri) if r["zaman"][:4] >= str(bolme.ILK_YIL)]

    print("Model B — çoklu ufuk (lead-time) deneyi (holdout AÇILMADI)")
    print(f"Değişkenler: {', '.join(ALANLAR)}\n")
    print(f"{'ufuk':>8}{'n':>9}{'poz':>6}{'olay':>7}{'Brier×10⁴':>11}"
          f"{'BSS':>8}{'AP':>8}{'LogLoss':>9}{'LSS':>8}{'LSS|saat':>10}"
          f"{'ROC-AUC':>9}")
    sonuclar = {}
    for ufuk in UFUKLAR_SAAT:
        s = calistir(ham, ufuk)
        sonuclar[ufuk] = s
        print(f"{_etiket(ufuk):>8}{s['n']:>9}{s['poz']:>6}{s['olay_sayisi']:>7}"
              f"{1e4*s['brier']:>11.2f}{s['bss']:>8.3f}{s['ap']:>8.3f}"
              f"{s['log_loss']:>9.3f}{s['lss']:>8.3f}{s['lss_saat']:>10.3f}"
              f"{s['roc_auc']:>9.3f}")

    if secenek.bootstrap:
        _bootstrap_yaz(sonuclar, secenek.bootstrap)

    esikler = sonuclar[UFUKLAR_SAAT[0]]["olay_esikleri"]
    baslik_esikleri = [f">=%{100 * e['esik']:g}" for e in esikler]
    print("\nEvent-level duyarlılık (eşik geçtikten SONRA gerçekleşen bağımsız olay oranı):")
    print(f"  {'ufuk':<8}" + "".join(f"{b:>10}" for b in baslik_esikleri))
    for ufuk, s in sonuclar.items():
        satir = f"  {_etiket(ufuk):<8}"
        for kova in s["olay_esikleri"]:
            satir += f"{100 * kova['duyarlilik']:>9.1f}%"
        print(satir)

    print("\n  (paydalar — geçerli/temsilcili bağımsız olay sayısı, ufuk arttıkça büyür):")
    for ufuk, s in sonuclar.items():
        toplam = s["olay_esikleri"][0]["toplam_olay"] if s["olay_esikleri"] else 0
        print(f"    {_etiket(ufuk):<8}{toplam} olay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
