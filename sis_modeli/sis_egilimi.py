#!/usr/bin/env python3
"""Sis sikligi yillar icinde dustu mu? Gercek mi, kayit kaynakli mi?
Salt okuma denetimi.

LTFJ'de sisli gun sayisi 2012-2017'de ~24/yil iken 2023-2025'te 9/yil.
Bu betik dususu UC bagimsiz kaynakla karsilastirir:

  1) LTFJ METAR arsivi (veri/ltfj_ozellik.csv.gz): sisli/LVO gun, dusuk
     gorus satirlari, pus (BR) ve "sise elverisli" gece kosullari
     (spread <= 1 C, ruzgar <= 4 kt) icinde gorusun 1000 m altina inme payi.
  2) ERA5 yeniden analizi (veri/acik_meteo_ltfj.csv.gz): istasyon
     sensorunden BAGIMSIZ; sis mevsimi (Eki-Nis) gece bagil nemi.
  3) LTFM METAR arsivi (veri/komsu_ltfm_ozellik.csv.gz, 2019+): komsu
     istasyonda ayni yillarda dusus var mi.

Model egitmez, dosya yazmaz; yalnizca okur ve basar. Bulgu notu:
sis_modeli/SIS_EGILIMI.md.

Kullanim (repo kokunden):
    python -m sis_modeli.sis_egilimi
"""

import csv
import gzip
from collections import defaultdict

LTFJ = "sis_modeli/veri/ltfj_ozellik.csv.gz"
ERA5 = "sis_modeli/veri/acik_meteo_ltfj.csv.gz"
LTFM = "sis_modeli/veri/komsu_ltfm_ozellik.csv.gz"

# "Sise elverisli" gece: doymaya yakin ve sakin. Esikler bilincli olarak
# kaba - amac model degil, yillar arasi KARSILASTIRMA icin sabit bir olcu.
ELVERISLI_SPREAD_C = 1
ELVERISLI_RUZGAR_KT = 4
ERA5_RH_ESIK = 95             # %
ERA5_RUZGAR_KMH = 7           # Open-Meteo ruzgari km/h (~4 kt)
SIS_MEVSIMI = (10, 11, 12, 1, 2, 3, 4)


def _sayi(metin):
    try:
        return float(metin)
    except (TypeError, ValueError):
        return None


def gece_mi(saat_utc: int) -> bool:
    """20-06 UTC (yerel 23-09): radyasyon sisinin olustugu ve kalktigi saatler."""
    return saat_utc <= 6 or saat_utc >= 20


def ltfj_yillik(satirlar) -> dict:
    """METAR arsivi satirlarindan yil bazli sayimlar (ltfj_ozellik.csv
    bicimi; LTFM dosyasi da ayni bicimde)."""
    gunler = defaultdict(lambda: {"sis": set(), "lvo": set()})
    say = defaultdict(lambda: defaultdict(int))
    for s in satirlar:
        yil, gun = s["zaman"][:4], s["zaman"][:10]
        gorus, spread, ruzgar = _sayi(s["gorus"]), _sayi(s["spread"]), _sayi(s["ruzgar_hiz"])
        k = say[yil]
        k["n"] += 1
        if s["sis"] == "1":
            gunler[yil]["sis"].add(gun)
        if s["lvo"] == "1":
            gunler[yil]["lvo"].add(gun)
        if gorus is not None and gorus < 1000:
            k["g1000"] += 1
        if gorus is not None and gorus < 5000:
            k["g5000"] += 1
        if "BR" in (s.get("hava") or ""):
            k["br"] += 1
        if (spread is not None and ruzgar is not None and gece_mi(int(s["saat"]))
                and spread <= ELVERISLI_SPREAD_C and ruzgar <= ELVERISLI_RUZGAR_KT):
            k["elverisli"] += 1
            if gorus is not None and gorus < 1000:
                k["elverisli_sis"] += 1
    out = {}
    for yil in sorted(say):
        k = say[yil]
        out[yil] = {
            "n": k["n"],
            "sisli_gun": len(gunler[yil]["sis"]),
            "lvo_gun": len(gunler[yil]["lvo"]),
            "g1000": k["g1000"], "g5000": k["g5000"], "br": k["br"],
            "elverisli": k["elverisli"],
            "elverisli_sis_yuzde": (round(100 * k["elverisli_sis"] / k["elverisli"], 1)
                                    if k["elverisli"] else None),
        }
    return out


def era5_yillik(satirlar) -> dict:
    """Sis mevsimi (Eki-Nis) gece saatlerinde ERA5 bagil nemi."""
    say = defaultdict(lambda: defaultdict(float))
    for s in satirlar:
        zaman = s["zaman"]
        ay, saat = int(zaman[5:7]), int(zaman[11:13])
        rh, ruzgar = _sayi(s["relative_humidity_2m"]), _sayi(s["wind_speed_10m"])
        if ay not in SIS_MEVSIMI or not gece_mi(saat) or rh is None:
            continue
        k = say[zaman[:4]]
        k["n"] += 1
        k["rh_toplam"] += rh
        if rh >= ERA5_RH_ESIK:
            k["rh95"] += 1
            if ruzgar is not None and ruzgar <= ERA5_RUZGAR_KMH:
                k["rh95_sakin"] += 1
    return {yil: {"n": int(k["n"]), "ort_rh": round(k["rh_toplam"] / k["n"], 1),
                  "rh95": int(k["rh95"]), "rh95_sakin": int(k["rh95_sakin"])}
            for yil, k in sorted(say.items())}


def _oku(yol, ilk, son):
    with gzip.open(yol, "rt", encoding="utf-8") as f:
        return [s for s in csv.DictReader(f) if ilk <= s["zaman"][:4] <= son]


def main() -> int:
    print("=== 1) LTFJ METAR (2011-2025) ===")
    print(f"{'yıl':<6}{'satır':>7}{'sisli gün':>11}{'LVO gün':>9}{'g<1000':>8}"
          f"{'g<5000':>8}{'BR':>6}{'elverişli':>11}{'→g<1000 %':>11}")
    for yil, k in ltfj_yillik(_oku(LTFJ, "2011", "2025")).items():
        oran = "" if k["elverisli_sis_yuzde"] is None else f"{k['elverisli_sis_yuzde']:.1f}"
        print(f"{yil:<6}{k['n']:>7}{k['sisli_gun']:>11}{k['lvo_gun']:>9}{k['g1000']:>8}"
              f"{k['g5000']:>8}{k['br']:>6}{k['elverisli']:>11}{oran:>11}")
    print("  elverişli = gece (20-06 UTC), spread <= 1 °C, rüzgâr <= 4 kt")
    print("  NOT: 2021-2023 çiy noktası kusuru spread'i küçültüyor - elverişli sayısı şişkin.")

    print("\n=== 2) ERA5 - sis mevsimi (Eki-Nis) geceleri (2005-2025) ===")
    print(f"{'yıl':<6}{'ort. RH %':>10}{'RH>=95 saat':>13}{'+ rüzgâr<=7 km/h':>18}")
    for yil, k in era5_yillik(_oku(ERA5, "2005", "2025")).items():
        print(f"{yil:<6}{k['ort_rh']:>10.1f}{k['rh95']:>13}{k['rh95_sakin']:>18}")

    print("\n=== 3) LTFM METAR (2019-2025) ===")
    print(f"{'yıl':<6}{'sisli gün':>11}{'g<5000':>8}")
    for yil, k in ltfj_yillik(_oku(LTFM, "2019", "2025")).items():
        print(f"{yil:<6}{k['sisli_gun']:>11}{k['g5000']:>8}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
