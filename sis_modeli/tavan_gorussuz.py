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


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    a.add_argument("--embargo-kapat", action="store_true")
    a.add_argument("--holdout", action="store_true", help="TEK ATIŞ")
    secenek = a.parse_args(argv)
    if not secenek.veri.exists():
        print(f"HATA: {secenek.veri} yok.", file=sys.stderr)
        return 1

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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
