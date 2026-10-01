#!/usr/bin/env python3
"""Omerli tarafindan nem tasinmasi: KD ruzgari x dusuk spread x gece/sabah.
Salt okuma.

Soru: meydanin kuzeyindeki Omerli Baraji'ndan gelen nemli hava 24 pist
basina sis tasiyor mu? Ayri bir nem olcumu olmadigi icin LTFJ METAR'indan
dolayli bir gosterge kurulur: gece/sabah (20-04 UTC), o an sis yokken,
spread ve ruzgar yonune/hizina gore sonraki 3 saatte sis VEYA parcali sis
(BCFG/PRFG/MIFG/VCFG) olasiligi.

Kullanim (repo kokunden):
    python -m sis_modeli.omerli_advek
"""

import csv
import gzip
import re
from collections import Counter
from datetime import datetime

from sis_modeli.sis_oncul import gelecekte_sis

VERI = "sis_modeli/veri/ltfj_ozellik.csv.gz"
KD_YON = (0, 60)              # derece; 360 de dahil
KD_HIZ_KT = (3, 10)           # hafif KD; <3 sakin, >10 karistirir
# 2021-2023 cig noktasi kusuru spread'i kucultuyor (SIS_EGILIMI.md)
KUSURLU_YILLAR = ("2021", "2022", "2023")


def olay_mi(satir: dict) -> bool:
    """Sis (model hedefi) veya parcali sis kodu."""
    return satir["sis"] == "1" or bool(re.search(r"(BC|PR|MI|VC)FG", satir["hava"] or ""))


def gece_sabah_mi(saat_utc: int) -> bool:
    """20-04 UTC (yerel 23-07): olusum penceresi."""
    return saat_utc >= 20 or saat_utc <= 4


def ruzgar_sinifi(yon: float, hiz: float) -> str:
    if hiz < KD_HIZ_KT[0]:
        return "sakin"
    if KD_YON[0] <= yon <= KD_YON[1] or yon == 360:
        return "K-KD 3-10 kt" if hiz <= KD_HIZ_KT[1] else "K-KD >10 kt"
    return "diger"


def spread_sinifi(spread: float) -> str:
    return "<=1" if spread <= 1 else "2-3" if spread <= 3 else ">3"


def _sayi(metin):
    try:
        return float(metin)
    except (TypeError, ValueError):
        return None


def tablo(satirlar: list, yil_suzgeci=None) -> dict:
    """{(spread, ruzgar): (n, yuzde)}. Gelecek, TUM satirlar uzerinden
    hesaplanir; yil_suzgeci yalnizca sayilan satirlari secer."""
    zamanlar = [datetime.fromisoformat(s["zaman"]) for s in satirlar]
    olay = [olay_mi(s) for s in satirlar]
    gelecek = gelecekte_sis(zamanlar, olay)
    say, poz = Counter(), Counter()
    for i, s in enumerate(satirlar):
        if olay[i] or not gece_sabah_mi(int(s["saat"])):
            continue
        if yil_suzgeci and not yil_suzgeci(s["zaman"][:4]):
            continue
        yon, hiz, spread = _sayi(s["ruzgar_yon"]), _sayi(s["ruzgar_hiz"]), _sayi(s["spread"])
        if yon is None or hiz is None or spread is None:
            continue
        k = (spread_sinifi(spread), ruzgar_sinifi(yon, hiz))
        say[k] += 1
        poz[k] += gelecek[i]
    return {k: (say[k], round(100 * poz[k] / say[k], 1)) for k in sorted(say)}


def main() -> int:
    with gzip.open(VERI, "rt", encoding="utf-8") as f:
        satirlar = [s for s in csv.DictReader(f) if "2012" <= s["zaman"][:4] <= "2025"]
    for baslik, suzgec in (("2012-2025", None),
                           ("2021-2023 hariç", lambda y: y not in KUSURLU_YILLAR),
                           ("yalnız 2024-2025", lambda y: y in ("2024", "2025"))):
        print(f"\n{baslik}: gece/sabah (20-04 UTC), olay yokken, 3 saatte sis/parçalı sis")
        print(f"  {'spread':<8}{'rüzgâr':<14}{'n':>7}{'%':>8}")
        for (sp, rz), (n, yuzde) in tablo(satirlar, suzgec).items():
            print(f"  {sp:<8}{rz:<14}{n:>7}{yuzde:>8.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
