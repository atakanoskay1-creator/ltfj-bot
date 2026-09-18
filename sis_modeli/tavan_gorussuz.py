#!/usr/bin/env python3
"""Tavan icin GORUSSUZ iki model: (A) sureklilik, (B) olusum.

TL.007 madde 6.2.a/6.3.1.a: bulut tabani RVR'dan (gorusten) BAGIMSIZ bir LVO
tetikleyicisidir. Su ana kadar kurulan HICBIR tavan calismasi gercekten
gorussuz degildi - `tavan_tablo.py`'nin kazanan cifti `spread x gorus`.

Bu betik iki FARKLI gorussuz soru sorar (ikisi de gorus KULLANMAZ):

  Model A (sureklilik): mevcut tavan OKUMASI + atmosferik degiskenlerle,
    onumuzdeki 3 saatte tavan<500ft olur mu? (`ltfj_sis_olasilik`in tavan
    icin karsiligi - suan tavan da bir predictor)
  Model B (olusum): ne mevcut tavan NE gorus - yalnizca atmosferik
    degiskenlerle (spread, sicaklik, ruzgar, saat) tavan cokmesi onceden
    haber verilebiliyor mu? (`sis_modeli.olusum_egit`in tavan icin karsiligi)

Iki model DOGRUDAN karsilastirilip siralanmiyor - farkli sorulara cevap
veriyorlar, aynen sis_modeli.olusum_egit'teki gibi.

REJIM: `tavan.REJIM_ILK_YIL` (2017+) - erken donem dusuk tavan eksik
bildirimi nedeniyle (bkz. sis_modeli/README.md).

OLAY SAYISI - gorussuz sis modelinden (Model B, sis) FAZLA, olculdu:

    hedef (2017+ rejim)     gelistirme   holdout
    sis                        128          33
    tavan<500ft                182          81

Bu, event-level guven araliklarinin daha dar, tespit oranlarinin daha
guvenilir cikacagi anlamina gelir.

METODOLOJI ZINCIRI: sis_modeli.olusum_egit ile AYNI disiplin - degisken
tarama -> coklu dogrusallik -> walk-forward ablasyon -> (--holdout ile)
dokunulmamis nihai holdout. YASAK ALANLAR calisma zamaninda denetlenir.

Kullanim:
    python -m sis_modeli.tavan_gorussuz                 # tarama + walk-forward
    python -m sis_modeli.tavan_gorussuz --embargo-kapat
    python -m sis_modeli.tavan_gorussuz --holdout        # TEK ATIS
"""

import argparse
import sys
from pathlib import Path

from sis_modeli import (bolme, degerlendir, hedef, model, olay_degerlendirme,
                        olusum_alanlar, tanilama, tavan, woe)
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku
from sis_modeli.tavan_tablo import _ic_foldlar

ETIKET = "tavan_dusuk"

# Aday havuzu: gorussuz sis modeliyle (olusum_egit) AYNI atmosferik
# degiskenler - `tavan_ozellik` ayri tutuluyor (yalnizca Model A'da izinli).
ADAYLAR_ATMOSFERIK = list(olusum_alanlar.ADAYLAR)

# Model B icin ek yasak: tavan'in KENDISI - onu eklemek sureklilik olurdu,
# olusum degil. `dogrula_b()` bunu calisma zamaninda denetler.
YASAKLI_B = tuple(olusum_alanlar.YASAKLI) + ("tavan", "tavan_ozellik")

# Ablasyon (GERCEKTEN OLCULDU - gelistirme (2017-2023) icinde yuruyen
# pencere, embargo acik, holdout kapali):
#
#   MODEL B (olusum, tavan_ozellik YOK)                    AP       BSS
#   spread+trend3+ruzgar_kuzey+saat (4)  <-- SECILEN      0.0602   0.0248
#   + sicaklik (5)                                        0.0405   0.0142  (sicaklik ZARARLI)
#   + ay yerine (5)                                       0.0393   0.0156  (ay ZARARLI)
#   + sicaklik + ay (6)                                   0.0397   0.0157
#   + ruzgar_dogu da (6)                                  0.0466   0.0191
#   + spread_egilim_1 de (5)                              0.0535   0.0205
#   yalniz spread+saat (2)                                0.0622   0.0190  (AP hafif yuksek, BSS dusuk)
#
# DIKKAT - sis hedefinin TERSI: orada sicaklik EKLENMEDEN model iklimden
# kotuydu, burada sicaklik EKLENINCE BSS %43 dusuyor. Ayni degisken iki
# farkli hedefte zit yonde davranabiliyor - bu yuzden "sis icin ise yaradi,
# tavan icin de yarar" varsayimi YAPILMADI, tarama YENIDEN yapildi.
#
#   MODEL A (sureklilik, tavan_ozellik DAHIL)              AP       BSS
#   spread+trend3+ruzgar_kuzey+saat+tavan (5)             0.0591   0.0177
#   + sicaklik (6)                                        0.0510   0.0125
#   + ay yerine (6)                                       0.0403   0.0160
#   + sicaklik + ay (7)                                   0.0493   0.0159
#   + ruzgar_dogu da (7)                                  0.0532   0.0143
#   + spread_egilim_1 de (6)  <-- SECILEN                 0.0676   0.0205
#   yalniz spread+saat+tavan (3)                          0.0565   0.0192
#
# Model A'da spread_egilim_1 VE spread_egilim_3'un BIRLIKTE kullanilmasi
# (kisa+uzun vadeli egilim) hem AP hem BSS'te en iyi sonucu veriyor - mevcut
# tavan okumasiyla (sureklilik) birlestiginde kisa vadeli degisim hizi ek
# bilgi tasiyor; Model B'de (sureklilik YOK) ayni ekleme zarar vermisti.
ALANLAR_B = ["spread", "spread_egilim_3", "ruzgar_kuzey", "saat"]
ALANLAR_A = ["spread", "spread_egilim_1", "spread_egilim_3", "ruzgar_kuzey",
            "saat", "tavan_ozellik"]


def dogrula_b(alanlar: list) -> None:
    celisen = [a for a in alanlar if a in YASAKLI_B]
    if celisen:
        raise ValueError(
            f"Model B (tavan olusumu) icin YASAKLI alan(lar): {celisen} - "
            f"tavan'in kendisi sureklilik olur, olusum degil.")


# ------------------------------------------------------ veri hazirlama
def hazirla_tum(ham: list) -> list:
    """`tavan.hazirla()`'nin ic adimlarini tekrarlar ama ONSET FILTRESI
    UYGULAMADAN tum (pozitif dahil) kayitlari dondurur - bagimsiz olay
    tanimlama icin gerekli (tavan.hazirla() yalnizca onset adaylarini
    dondurdugu icin olay siniri kayboluyor)."""
    pencere = tavan.rejim_penceresi(ham)
    etiketli = tavan.etiketle(pencere)
    kayitlar = hedef.hazirla(etiketli, etiket=ETIKET)
    for r in kayitlar:
        r["tavan_ozellik"] = tavan.tavan_ft(r)
        r["sis_yakinligi"] = olusum_alanlar.sis_yakinligi(r.get("hava") or "")
    return kayitlar


def onset_kumesi(kayitlar_tum: list) -> list:
    return hedef.onset_adaylari(kayitlar_tum, etiket=ETIKET)


# ------------------------------------------------------------ tarama
def tarama_bas(gelistirme: list, alanlar: list) -> None:
    print(f"{'değişken':<18}{'IV':>8}{'%5–%95':>18}{'mono':>7}{'PSI':>8}  yorum")
    yillar = sorted({r["dt"].year for r in gelistirme})
    orta = yillar[len(yillar) // 2]
    ilk = [r for r in gelistirme if r["dt"].year < orta]
    son = [r for r in gelistirme if r["dt"].year >= orta]
    for alan in alanlar:
        t = woe.kova_tablosu(gelistirme, alan, "hedef")
        if not t:
            print(f"{alan:<18}{'—':>8}   (kova kurulamadı)")
            continue
        sinirlar = [k["ust"] for k in t[:-1]]
        deger = woe.iv(t)
        alt, ust = woe.iv_guven_araligi(gelistirme, alan, "hedef", "gun",
                                        list(sinirlar), tekrar=150)
        p = woe.psi(ilk, son, alan, list(sinirlar)) if ilk and son else 0.0
        print(f"{alan:<18}{deger:>8.3f}{f'{alt:.3f} – {ust:.3f}':>18}"
              f"{'evet' if woe.monoton_mu(t) else 'hayır':>7}{p:>8.3f}"
              f"  {woe.iv_yorumla(deger)}"
              f"{'  ** KAYIYOR' if p > 0.25 else ''}")


def vif_bas(gelistirme: list, alanlar: list) -> None:
    tablolar = model.woe_tablolari(gelistirme, alanlar)
    adlar, _ = tanilama.korelasyon_matrisi(gelistirme, tablolar)
    vifler = tanilama.vif(gelistirme, tablolar)
    print(f"  {'değişken':<18}{'VIF':>8}")
    for ad in adlar:
        uyari = "  ** DİKKAT" if vifler[ad] > tanilama.VIF_DIKKAT else ""
        print(f"  {ad:<18}{vifler[ad]:>8.2f}{uyari}")


# --------------------------------------------------------- walk-forward
def wf_olc(gelistirme: list, alanlar: list, embargo: bool = True) -> dict:
    """Gelistirme donemi ICINDE (`_ic_foldlar`) yuruyen pencere; embargo
    varsayilan acik (bkz. bolme.embargo_penceresi)."""
    yillar = sorted({r["dt"].year for r in gelistirme})
    gercek, tahmin = [], []
    tahmin_map = {}
    for eg_yillari, test_yillari in _ic_foldlar(yillar):
        eg = bolme.ayir(gelistirme, eg_yillari)
        if embargo:
            eg = bolme.embargo_penceresi(eg, min(test_yillari))
        te = bolme.ayir(gelistirme, test_yillari)
        if not te or not any(r["hedef"] for r in te):
            continue
        katsayilar, tablolar, _l2 = model.egit_secerek(eg, alanlar)
        for r in te:
            p = model.olasilik(katsayilar, r, tablolar)
            gercek.append(bool(r["hedef"]))
            tahmin.append(p)
            tahmin_map[r["dt"]] = p
    taban = sum(gercek) / len(gercek) if gercek else 0.0
    iklim = [taban] * len(gercek)
    return {
        "n": len(gercek), "poz": sum(gercek),
        "brier": degerlendir.brier(tahmin, gercek),
        "bss": degerlendir.brier_skill(tahmin, gercek, iklim),
        "ap": degerlendir.ortalama_kesinlik(tahmin, gercek),
        "tahmin_map": tahmin_map,
    }


def _skor_yazdir(baslik: str, sonuc: dict) -> None:
    print(f"{baslik:<40}n={sonuc['n']:>7}  poz={sonuc['poz']:>4}  "
          f"Brier×10⁴={1e4*sonuc['brier']:>7.2f}  BSS={sonuc['bss']:>7.3f}  "
          f"AP={sonuc['ap']:>7.3f}")


def karsilastir(egitim: list, test: list, alanlar: list) -> tuple:
    """(gercek, {yontem: tahmin}) - model + iklim + basit kural (spread+
    ruzgar, gorussuz, model.py'den yeniden kullanilan)."""
    katsayilar, tablolar, l2 = model.egit_secerek(egitim, alanlar)
    taban = sum(r["hedef"] for r in egitim) / max(len(egitim), 1)
    gercek = [bool(r["hedef"]) for r in test]
    return gercek, {
        "model": [model.olasilik(katsayilar, r, tablolar) for r in test],
        "iklim": [taban] * len(test),
        "basit kural (spread+rüzgâr)": [model.basit_kural_baseline(r) for r in test],
    }, l2


def _karsilastirma_bas(baslik: str, gercek: list, tahminler: dict) -> None:
    iklim = tahminler["iklim"]
    print(f"\n{baslik}")
    print(f"  {'yöntem':<28}{'Brier×10⁴':>11}{'BSS':>8}{'AP':>8}")
    for ad, p in tahminler.items():
        print(f"  {ad:<28}{1e4*degerlendir.brier(p, gercek):>11.2f}"
              f"{degerlendir.brier_skill(p, gercek, iklim):>8.3f}"
              f"{degerlendir.ortalama_kesinlik(p, gercek):>8.3f}")


def _event_level_bas(baslik: str, kayitlar_tum: list, yillar: tuple,
                     tahmin_map: dict) -> None:
    olaylar = [o for o in olay_degerlendirme.bagimsiz_olaylar(kayitlar_tum, etiket=ETIKET)
              if o["baslangic"].year in yillar]
    temsilciler = olay_degerlendirme.olay_temsilci_satirlari(
        kayitlar_tum, olaylar, etiket=ETIKET)
    print(f"\n{baslik} ({len(olaylar)} bağımsız olay)")
    print(f"  {'eşik':>6}{'olay':>7}{'yakalanan':>11}{'duyarlılık':>12}{'%5–%95':>16}")
    for e in olay_degerlendirme.olay_bazli_esik_tablosu(temsilciler, tahmin_map):
        alt, ust = olay_degerlendirme.olay_bazli_guven_araligi(
            temsilciler, tahmin_map, e["esik"], tekrar=150)
        print(f"  {100*e['esik']:>5.0f}%{e['toplam_olay']:>7}{e['yakalanan']:>11}"
              f"{100*e['duyarlilik']:>11.1f}%{f'{100*alt:.1f}–{100*ust:.1f}%':>16}")


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    a.add_argument("--embargo-kapat", action="store_true")
    a.add_argument("--holdout", action="store_true", help="TEK ATIŞ")
    secenek = a.parse_args(argv)
    if not secenek.veri.exists():
        print(f"HATA: {secenek.veri} yok.", file=sys.stderr)
        return 1

    dogrula_b(ALANLAR_B)

    ham = veri_oku(secenek.veri)
    kayitlar_tum = hazirla_tum(ham)
    aday = onset_kumesi(kayitlar_tum)
    gelistirme = bolme.gelistirme(aday)

    print(f"Tavan (görüşsüz), rejim {tavan.REJIM_ILK_YIL}+")
    print(f"Geliştirme onset evreni: {len(gelistirme)} an, "
          f"{sum(r['hedef'] for r in gelistirme)} pozitif, "
          f"{len({r['gun'] for r in gelistirme if r['hedef']})} ayrı gün\n")

    print("=== 1) Değişken tarama (atmosferik + tavan_ozellik) ===")
    tarama_bas(gelistirme, ADAYLAR_ATMOSFERIK + ["tavan_ozellik"])

    print(f"\n=== 2) Çoklu doğrusal bağlantı ===")
    print(f"Model A (süreklilik) — {ALANLAR_A}")
    vif_bas(gelistirme, ALANLAR_A)
    print(f"Model B (oluşum) — {ALANLAR_B}")
    vif_bas(gelistirme, ALANLAR_B)

    yillar = sorted({r["dt"].year for r in gelistirme})
    embargo = not secenek.embargo_kapat

    for etiket_model, alanlar in (("Model A (süreklilik)", ALANLAR_A),
                                  ("Model B (oluşum)", ALANLAR_B)):
        print(f"\n=== 3) Walk-forward — {etiket_model} ===")
        print(f"Değişkenler: {', '.join(alanlar)}")
        birikmis_gercek, birikmis_tahmin = [], {}
        tahmin_map_toplu = {}
        for eg_yillari, test_yillari in _ic_foldlar(yillar):
            eg = bolme.ayir(gelistirme, eg_yillari)
            if embargo:
                eg = bolme.embargo_penceresi(eg, min(test_yillari))
            te = bolme.ayir(gelistirme, test_yillari)
            if not te or not any(r["hedef"] for r in te):
                continue
            gercek, tahminler, l2 = karsilastir(eg, te, alanlar)
            birikmis_gercek.extend(gercek)
            for ad, p in tahminler.items():
                birikmis_tahmin.setdefault(ad, []).extend(p)
            for r, p in zip(te, tahminler["model"]):
                tahmin_map_toplu[r["dt"]] = p
        _karsilastirma_bas(
            f"Birikmiş ({len(birikmis_gercek)} an, {sum(birikmis_gercek)} pozitif):",
            birikmis_gercek, birikmis_tahmin)
        _event_level_bas(f"Event-level (gelişt. içi, {etiket_model})",
                         kayitlar_tum, tuple(y for y in yillar), tahmin_map_toplu)

    if not secenek.holdout:
        print("\n(Holdout açılmadı. Açmak için: --holdout)")
        return 0

    print("\n" + "=" * 70)
    print("=== 4) NİHAİ HOLDOUT (2024-2026) — TEK ATIŞ ===")
    print("=" * 70)
    egitim_tum = bolme.embargo_penceresi(gelistirme, min(bolme.HOLDOUT_YILLARI)) \
        if embargo else gelistirme
    test_hol = bolme.holdout(aday)
    if not test_hol:
        print("HATA: holdout boş.", file=sys.stderr)
        return 1
    print(f"Eğitim: {len(egitim_tum)} an, {sum(r['hedef'] for r in egitim_tum)} pozitif")
    print(f"HOLDOUT: {len(test_hol)} an, {sum(r['hedef'] for r in test_hol)} pozitif "
          f"(taban oran %{100*sum(r['hedef'] for r in test_hol)/len(test_hol):.2f})")

    for etiket_model, alanlar in (("Model A (süreklilik)", ALANLAR_A),
                                  ("Model B (oluşum)", ALANLAR_B)):
        print(f"\n--- {etiket_model} — {', '.join(alanlar)} ---")
        gercek, tahminler, l2 = karsilastir(egitim_tum, test_hol, alanlar)
        print(f"Seçilen L2: {l2:.0f}")
        print(f"  {'yöntem':<28}{'Brier×10⁴':>11}{'BSS':>8}{'AP':>8}{'AP %5–%95':>18}")
        for ad, p in tahminler.items():
            alt, ust = degerlendir.blok_guven_araligi(test_hol, p, gercek,
                                                      degerlendir.ortalama_kesinlik)
            print(f"  {ad:<28}{1e4*degerlendir.brier(p, gercek):>11.2f}"
                  f"{degerlendir.brier_skill(p, gercek, tahminler['iklim']):>8.3f}"
                  f"{degerlendir.ortalama_kesinlik(p, gercek):>8.3f}"
                  f"{f'{alt:.3f} – {ust:.3f}':>18}")
        tahmin_map_hol = {r["dt"]: p for r, p in zip(test_hol, tahminler["model"])}
        _event_level_bas(f"Event-level (holdout, {etiket_model})",
                         kayitlar_tum, bolme.HOLDOUT_YILLARI, tahmin_map_hol)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
