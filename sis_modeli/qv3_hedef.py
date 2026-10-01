#!/usr/bin/env python3
"""QV3 hedefi: onumuzdeki 3 saatte LVO Hazirlik Safhasi'na gecilecek mi?

Hazirlik sarti (TL.007 madde 6.2.a): RVR < 800 m VEYA bulut tabani (tavan)
CAT II seviyesine, 200 ft altina iner. Egitim arsivi (veri/ltfj_ozellik.csv.gz)
RVR tasimadigi icin RVR ayri dosyadan (veri/ltfj_rvr.csv.gz, veri_cek_rvr.py)
`zaman` uzerinden birlestirilir. 2011 satirlari buyuk olcude LTBA oldugu icin
egitim 2012'den baslar (README "Veri kalitesi" (0)).

QV3 CANLIYA BAGLANMAZ - yalnizca karsilastirma icin (QV3_RAPOR.md).

Kullanim (repo kokunden):
    python -m sis_modeli.qv3_hedef
"""

import csv
import gzip
from collections import Counter

from sis_modeli import hedef
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku

ILK_YIL = 2012
RVR_ESIK_M = 800
TAVAN_ESIK_FT = 200
RVR_DOSYA = "sis_modeli/veri/ltfj_rvr.csv.gz"


def hazirlik_mi(rvr_min, tavan) -> int:
    if rvr_min is not None and rvr_min < RVR_ESIK_M:
        return 1
    if tavan is not None and tavan < TAVAN_ESIK_FT:
        return 1
    return 0


def _sayi(deger):
    if deger is None or deger == "":
        return None
    return int(deger)


def rvr_birlestir(satirlar: list, rvr_satirlari: list) -> list:
    """Her satira rvr_06, rvr_24, rvr_min ekler (eslesmeyen: None)."""
    rvr = {r["zaman"]: r for r in rvr_satirlari}
    for s in satirlar:
        r = rvr.get(s["zaman"], {})
        s["rvr_06"] = _sayi(r.get("rvr_06"))
        s["rvr_24"] = _sayi(r.get("rvr_24"))
        s["rvr_min"] = _sayi(r.get("rvr_min"))
    return satirlar


def etiketle(satirlar: list) -> list:
    for s in satirlar:
        s["hazirlik"] = hazirlik_mi(s["rvr_min"], s["tavan"])
    return satirlar


def veri_hazirla(ozellik_satirlari: list, rvr_satirlari: list) -> list:
    """2012+, RVR birlesik, etiketli; o an hazirlik YOKKEN olan anlar
    (onset evreni) - `hedef` = sonraki 3 saatte hazirlik."""
    satirlar = [s for s in ozellik_satirlari if int(s["zaman"][:4]) >= ILK_YIL]
    etiketle(rvr_birlestir(satirlar, rvr_satirlari))
    kayitlar = hedef.hazirla(satirlar, etiket="hazirlik")
    return hedef.onset_adaylari(kayitlar, etiket="hazirlik")


def rvr_oku(yol: str = RVR_DOSYA) -> list:
    with gzip.open(yol, "rt", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    aday = veri_hazirla(veri_oku(VARSAYILAN_VERI), rvr_oku())
    print(f"Onset evreni: {len(aday)} an, {sum(r['hedef'] for r in aday)} pozitif")
    yillik = Counter(r["dt"].year for r in aday if r["hedef"])
    for yil in sorted(yillik):
        print(f"  {yil}: {yillik[yil]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
