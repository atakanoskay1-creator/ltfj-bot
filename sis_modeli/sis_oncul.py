#!/usr/bin/env python3
"""Gorusu dusuren NEDEN (parcali sis / yagis / yalniz BR / HZ), ayni gorus
bandinda sonraki 3 saatte sis olasiligini nasil degistiriyor? Salt okuma.

Soru: BR (pus) cok sik raporlaniyor - modelin zaten kullandigi gorus
degiskeninin OTESINDE bilgi tasiyor mu? Ayni gorus bandindaki satirlar,
o an sis yokken, gorusu dusuren nedene gore ayrilir.

Kullanim (repo kokunden):
    python -m sis_modeli.sis_oncul
"""

import csv
import gzip
import re
from collections import Counter
from datetime import datetime, timedelta

VERI = "sis_modeli/veri/ltfj_ozellik.csv.gz"
UFUK = timedelta(hours=3)
BANTLAR = ((1000, 3000, "1000-2999"), (3000, 5000, "3000-4999"))


def neden(hava: str) -> str:
    """Gorusu dusuren baskin neden; oncelik sirasi parcali sis > yagis > BR > HZ."""
    t = (hava or "").split()
    if any(re.search(r"(BC|PR|MI|VC)FG", k) for k in t):
        return "parcali sis"
    if any(re.search(r"(RA|DZ|SN|SH|TS)", k) for k in t):
        return "yagis"
    if any(k.lstrip("+-") == "BR" for k in t):
        return "yalniz BR"
    if any(k in ("HZ", "FU", "DU") for k in t):
        return "HZ/FU/DU"
    return "kod yok"


def gelecekte_sis(zamanlar: list, sis: list, ufuk=UFUK) -> list[bool]:
    """Her satir icin (t, t+ufuk] icinde sis satiri var mi (zamanlar sirali)."""
    out, n = [], len(zamanlar)
    for i in range(n):
        k, var = i + 1, False
        while k < n and zamanlar[k] - zamanlar[i] <= ufuk:
            if sis[k]:
                var = True
                break
            k += 1
        out.append(var)
    return out


def tablo(satirlar: list) -> dict:
    """{(bant, neden): (n, yuzde)} - yalnizca o an sis olmayan satirlar."""
    zamanlar = [datetime.fromisoformat(s["zaman"]) for s in satirlar]
    sis = [s["sis"] == "1" for s in satirlar]
    gelecek = gelecekte_sis(zamanlar, sis)
    say, poz = Counter(), Counter()
    for i, s in enumerate(satirlar):
        if sis[i]:
            continue
        g = float(s["gorus"])
        bant = next((ad for alt, ust, ad in BANTLAR if alt <= g < ust), None)
        if bant is None:
            continue
        k = (bant, neden(s["hava"]))
        say[k] += 1
        poz[k] += gelecek[i]
    return {k: (say[k], round(100 * poz[k] / say[k], 1)) for k in sorted(say)}


def main() -> int:
    with gzip.open(VERI, "rt", encoding="utf-8") as f:
        satirlar = [s for s in csv.DictReader(f) if "2012" <= s["zaman"][:4] <= "2025"]
    print("Sis yokken, sonraki 3 saatte sis olasılığı (2012-2025):")
    print(f"  {'görüş':<11}{'neden':<14}{'n':>7}{'%':>8}")
    for (bant, ned), (n, yuzde) in tablo(satirlar).items():
        print(f"  {bant:<11}{ned:<14}{n:>7}{yuzde:>8.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
