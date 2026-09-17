#!/usr/bin/env python3
"""Turetilmis ozellik dosyasindan KESIF istatistikleri uretir.

Model kurmadan ONCE cevaplanmasi gereken soru: elde yeterince pozitif ornek
var mi, ve sis LTFJ'de gercekten hangi ay/saat/spread araliginda yogunlasiyor?
Bu betik AG ERISIMI GEREKTIRMEZ - veri_cek.py'nin urettigi dosyayi okur.

Bagimlilik yok (pandas/numpy dahil): saf standart kutuphane, boylece hem
burada hem CI'da ek kurulum olmadan calisir.

Kullanim:
    python -m sis_modeli.istatistik [--veri sis_modeli/veri/ltfj_ozellik.csv.gz]
"""

import argparse
import csv
import gzip
import sys
from collections import Counter
from pathlib import Path

from sis_modeli.ozellik import LVO_GORUS_M, SIS_GORUS_M

VARSAYILAN_VERI = Path(__file__).resolve().parent / "veri" / "ltfj_ozellik.csv.gz"

AY_ADI = ("Oca", "Şub", "Mar", "Nis", "May", "Haz",
          "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara")
# Spread (sicaklik - cig noktasi) kovalari, °C. Sis olusumunda en gucli tekil
# gosterge budur: 0'a yaklastikca hava doymus demektir.
SPREAD_KOVALARI = ((0, 1), (1, 2), (2, 3), (3, 5), (5, 8), (8, 999))


SAYISAL_ALANLAR = ("ay", "saat", "sicaklik", "cig_noktasi", "spread",
                   "ruzgar_hiz", "ruzgar_yon", "gorus", "tavan", "qnh",
                   "sis_kodu", "sis", "lvo")


def _sayi(ham):
    """Bos/bozuk alan analizi COKERTMEMELI: 375 bin satirlik bir arsivde tek
    bir beklenmedik deger butun raporu dusurmesin diye None'a duseriz."""
    if ham in (None, ""):
        return None
    try:
        return int(ham)
    except ValueError:
        pass
    try:
        return float(ham)
    except ValueError:
        return None


def veri_oku(yol: Path) -> list[dict]:
    """gzip CSV'yi okur; sayisal alanlari uygun tipe cevirir, bos/bozuk
    olanlari None birakir."""
    with gzip.open(yol, "rt", encoding="utf-8", newline="") as f:
        satirlar = list(csv.DictReader(f))

    for s in satirlar:
        for alan in SAYISAL_ALANLAR:
            s[alan] = _sayi(s.get(alan))
    return satirlar


def _oran_tablosu(satirlar: list[dict], anahtar, etiket: str) -> list[tuple]:
    """anahtar(satir) -> kova esleyen bir fonksiyon icin (kova, toplam,
    pozitif, yuzde) listesi dondurur."""
    toplam, pozitif = Counter(), Counter()
    for s in satirlar:
        kova = anahtar(s)
        if kova is None:
            continue
        toplam[kova] += 1
        pozitif[kova] += s[etiket] or 0
    return [(k, toplam[k], pozitif[k], 100 * pozitif[k] / toplam[k])
            for k in sorted(toplam)]


def _spread_kovasi(s: dict):
    if s["spread"] is None:
        return None
    for alt, ust in SPREAD_KOVALARI:
        if alt <= s["spread"] < ust:
            return (alt, ust)
    return None


def _yazdir(baslik: str, satirlar: list[tuple], bicim=str):
    print(f"\n{baslik}")
    print(f"  {'kova':<10} {'gözlem':>8} {'pozitif':>8} {'oran':>7}")
    for kova, toplam, poz, yuzde in satirlar:
        print(f"  {bicim(kova):<10} {toplam:>8} {poz:>8} {yuzde:>6.2f}%")


def rapor(satirlar: list[dict]) -> None:
    n = len(satirlar)
    sis = sum(s["sis"] or 0 for s in satirlar)
    lvo = sum(s["lvo"] or 0 for s in satirlar)
    yillar = sorted({s["zaman"][:4] for s in satirlar})

    print(f"Gözlem sayısı: {n}")
    print(f"Kapsanan yıllar: {yillar[0]}–{yillar[-1]} ({len(yillar)} yıl)")
    print(f"Sis (görüş<{SIS_GORUS_M} m veya FG): {sis} (%{100*sis/n:.2f})")
    print(f"LVO seviyesi (görüş<{LVO_GORUS_M} m): {lvo} (%{100*lvo/n:.2f})")
    print(f"\nModel kurulabilirliği: sis için {sis}, LVO için {lvo} pozitif örnek.")
    if lvo < 200:
        print("  UYARI: LVO pozitif örneği 200'ün altında - bu etiket için"
              " ayrı bir model yerine sadece olasılık tablosu uygun olur.")

    _yazdir("Aya göre sis oranı:",
            _oran_tablosu(satirlar, lambda s: s["ay"], "sis"),
            lambda k: AY_ADI[k - 1])
    _yazdir("UTC saate göre sis oranı:",
            _oran_tablosu(satirlar, lambda s: s["saat"], "sis"),
            lambda k: f"{k:02d}Z")
    _yazdir("Spread'e göre sis oranı (°C):",
            _oran_tablosu(satirlar, _spread_kovasi, "sis"),
            lambda k: f"{k[0]}–{k[1] if k[1] < 999 else '∞'}")
    _yazdir("Rüzgâr hızına göre sis oranı (kt):",
            _oran_tablosu(satirlar,
                          lambda s: None if s["ruzgar_hiz"] is None
                          else min(s["ruzgar_hiz"] // 3 * 3, 15), "sis"),
            lambda k: f"{k}–{k+2}" if k < 15 else "15+")


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    secenek = a.parse_args(argv)

    if not secenek.veri.exists():
        print(f"HATA: {secenek.veri} yok. Önce veri_cek.py çalıştırılmalı "
              "(GitHub Actions: 'Sis modeli verisi' workflow'u).", file=sys.stderr)
        return 1

    satirlar = veri_oku(secenek.veri)
    if not satirlar:
        print("HATA: veri dosyası boş.", file=sys.stderr)
        return 1
    rapor(satirlar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
