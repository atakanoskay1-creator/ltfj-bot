#!/usr/bin/env python3
"""Parcali sis (BCFG/PRFG/MIFG/VCFG) anlarinda pist uclarindaki RVR - salt okuma.

SORU: Omerli Baraji tarafindan (KD) sabah suruklenen sis meydanin tamamini
kaplamadan 24 pist baslarini kapatiyor mu? METAR'daki genel gorus yuksek
kalirken 24'e inen trafik icin RVR LVO seviyesine dusuyor mu?

Egitim arsivi (veri/ltfj_ozellik.csv.gz) RVR saklamiyor; bu betik IEM'den
ELLE indirilmis ham CSV'yi okur (metar sutunu olan, ornegin data=all ya da
data=metar). Yalnizca METAR metnindeki ICAO kodu LTFJ olan satirlar
sayilir (IEM 2011'de LTBA dondurdu - bkz. README "Veri kalitesi" (0)) ve
IEM_DS3505 yeniden kurulmus satirlar atlanir. Trend/RMK kismi sayilmaz.

Sayilar METAR degil RVR GRUBUDUR (bir raporda birden fazla pist grubu olur).

Kullanim (repo kokunden):
    python -m sis_modeli.rvr_pist asos.csv
"""

import csv
import re
import sys
from collections import Counter

PARCALI = re.compile(r"(?<![A-Z])(BC|PR|MI|VC)FG\b")
TAM_FG = re.compile(r"(?<![A-Z])[-+]?FG\b")
RVR = re.compile(r"(?<![A-Z0-9])R(\d{2})[LRC]?/([PM]?)(\d{4})")
SON = re.compile(r"\s(RMK|BECMG|TEMPO|NOSIG)\b")
SINIFLAR = ("<550", "550-1499", ">=1500")


def govde(metin: str) -> str:
    """METAR'in gozlem kismi (trend ve RMK haric)."""
    return SON.split(metin)[0]


def parcali_sis_mi(metin: str) -> bool:
    """Gozlem kisminda parcali sis var, alani kaplayan FG yok."""
    g = govde(metin)
    return bool(PARCALI.search(g)) and not TAM_FG.search(PARCALI.sub("", g))


def rvr_sinifi(isaret: str, deger: int) -> str:
    """P (ustu) degeri her zaman >=1500 sayilir; M (alti) degerin altinda."""
    if isaret != "P" and deger < 550:
        return "<550"
    if isaret != "P" and deger < 1500:
        return "550-1499"
    return ">=1500"


def rvr_gruplari(metin: str) -> list[tuple[str, str]]:
    """[(pist_ucu, sinif)] - pist_ucu '06' ya da '24' (L/R ayirmadan)."""
    return [(pist, rvr_sinifi(isaret, int(deger)))
            for pist, isaret, deger in RVR.findall(govde(metin))]


def say(satirlar, istasyon: str = "LTFJ") -> tuple[int, Counter]:
    """(parcali sis METAR sayisi, {'R24 <550': n, ..., 'RVR grubu yok': n})"""
    n, sonuc = 0, Counter()
    for x in satirlar:
        metin = (x.get("metar") or "").strip()
        m = re.search(r"\b(LT[A-Z]{2})\b", metin)
        if not m or m.group(1) != istasyon or "IEM_DS3505" in metin:
            continue
        if not parcali_sis_mi(metin):
            continue
        n += 1
        gruplar = rvr_gruplari(metin)
        if not gruplar:
            sonuc["RVR grubu yok"] += 1
        for pist, sinif in gruplar:
            sonuc[f"R{pist} {sinif}"] += 1
    return n, sonuc


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("Kullanim: python -m sis_modeli.rvr_pist <iem_ham.csv>", file=sys.stderr)
        return 1
    with open(argv[0], encoding="utf-8") as f:
        n, sonuc = say(csv.DictReader(f))
    print(f"parçalı sis METAR'ı: {n}")
    for k, v in sorted(sonuc.items()):
        print(f"  {k:<20}{v:>6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
