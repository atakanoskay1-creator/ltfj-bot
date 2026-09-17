#!/usr/bin/env python3
"""LTFJ METAR arsivini IEM'den ceker ve TURETILMIS ozellik dosyasi uretir.

HAM ARSIV REPOYA YAZILMAZ: satirlar indirilirken aninda ayristirilir ve
sadece modele giren alanlar sikistirilmis bir CSV'ye (veri/ltfj_ozellik.csv.gz)
eklenir. Boylece repo kucuk kalir ve egitim/analiz adimlari AG ERISIMI
OLMADAN tekrarlanabilir olur.

Ag erisimi gerektirdigi icin bu betik GitHub Actions'ta calisir
(.github/workflows/sis-veri.yml, elle tetiklenir).

Kullanim:
    python -m sis_modeli.veri_cek --baslangic 2003 --bitis 2026
"""

import argparse
import csv
import gzip
import io
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

from sis_modeli.ozellik import (LVO_GORUS_M, SIS_GORUS_M, SUTUNLAR,
                                atlama_nedeni, ozellik_cikar)

IEM_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
ISTASYON = "LTFJ"
VARSAYILAN_CIKTI = Path(__file__).resolve().parent / "veri" / "ltfj_ozellik.csv.gz"

ZAMAN_ASIMI = 180          # saniye - bir yillik arsiv buyuk olabilir
DENEME = 4                 # ustel geri cekilmeli yeniden deneme
GERI_CEKILME = 5           # saniye (5, 10, 20, 40)


class VeriCekmeHatasi(Exception):
    pass


def _yil_indir(yil: int, oturum: requests.Session) -> str:
    """Bir yilin ham METAR CSV'sini dondurur. Gecici ag hatalarinda ustel
    geri cekilmeyle yeniden dener; kalici hatada VeriCekmeHatasi firlatir."""
    parametreler = {
        "station": ISTASYON,
        "data": "metar",
        "year1": yil, "month1": 1, "day1": 1,
        "year2": yil + 1, "month2": 1, "day2": 1,
        "tz": "Etc/UTC",
        "format": "onlycomma",
        "latlon": "no",
        "missing": "M",
        "trace": "T",
        "direct": "no",
        "report_type": ["3", "4"],     # 3: rutin METAR, 4: SPECI
    }
    son_hata = None
    for deneme in range(DENEME):
        try:
            c = oturum.get(IEM_URL, params=parametreler, timeout=ZAMAN_ASIMI)
            c.raise_for_status()
            return c.text
        except requests.RequestException as e:
            son_hata = e
            if deneme < DENEME - 1:
                bekle = GERI_CEKILME * (2 ** deneme)
                print(f"  {yil}: ag hatasi ({e}), {bekle} sn sonra yeniden...",
                      file=sys.stderr)
                time.sleep(bekle)
    raise VeriCekmeHatasi(f"{yil} icin arsiv alinamadi: {son_hata}")


def _satirlari_coz(ham_csv: str) -> tuple[list, Counter]:
    """IEM CSV'sini ozellik satirlarina cevirir. (satirlar, atlama_sayaci)
    doner - atlama sayaci NEDEN bazinda kirilimlidir, cunku tek bir toplam
    sayi veri kalitesi sorununu gizler.

    IEM ciktisi 'station,valid,metar' sutunlarini tasir; valid UTC'dir
    (istekte tz=Etc/UTC verildi)."""
    okuyucu = csv.DictReader(io.StringIO(ham_csv))
    satirlar, atlanan = [], Counter()
    for kayit in okuyucu:
        metin = (kayit.get("metar") or "").strip()
        ham_zaman = (kayit.get("valid") or "").strip()
        if not metin or not ham_zaman:
            atlanan["metar/zaman bos"] += 1
            continue
        try:
            zaman = datetime.strptime(ham_zaman, "%Y-%m-%d %H:%M").replace(
                tzinfo=timezone.utc)
        except ValueError:
            atlanan["zaman ayristirilamadi"] += 1
            continue
        ozellik = ozellik_cikar(metin, zaman)
        if ozellik is None:
            atlanan[atlama_nedeni(metin) or "bilinmeyen"] += 1
            continue
        satirlar.append(ozellik)
    return satirlar, atlanan


def arsivi_uret(baslangic: int, bitis: int, cikti: Path) -> dict:
    """Yillari sirayla indirir, ayristirir ve tek bir gzip CSV'ye yazar.
    Ozet istatistik sozlugu dondurur."""
    cikti.parent.mkdir(parents=True, exist_ok=True)
    toplam, sis_sayisi, lvo_sayisi = 0, 0, 0
    atlanan_toplam = Counter()

    with gzip.open(cikti, "wt", encoding="utf-8", newline="") as f:
        yazici = csv.DictWriter(f, fieldnames=list(SUTUNLAR))
        yazici.writeheader()
        with requests.Session() as oturum:
            for yil in range(baslangic, bitis + 1):
                ham = _yil_indir(yil, oturum)
                satirlar, atlanan = _satirlari_coz(ham)
                for s in satirlar:
                    yazici.writerow(s)
                toplam += len(satirlar)
                atlanan_toplam.update(atlanan)
                sis_sayisi += sum(s["sis"] for s in satirlar)
                lvo_sayisi += sum(s["lvo"] for s in satirlar)
                print(f"  {yil}: {len(satirlar)} gozlem "
                      f"(sis {sum(s['sis'] for s in satirlar)}, "
                      f"lvo {sum(s['lvo'] for s in satirlar)}, "
                      f"atlanan {sum(atlanan.values())})")

    return {"gozlem": toplam, "atlanan": atlanan_toplam,
            "sis": sis_sayisi, "lvo": lvo_sayisi, "dosya": str(cikti)}


def main(argv=None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--baslangic", type=int, default=2003)
    ayristirici.add_argument("--bitis", type=int,
                             default=datetime.now(timezone.utc).year)
    ayristirici.add_argument("--cikti", type=Path, default=VARSAYILAN_CIKTI)
    a = ayristirici.parse_args(argv)

    print(f"{ISTASYON} arsivi: {a.baslangic}-{a.bitis}")
    try:
        ozet = arsivi_uret(a.baslangic, a.bitis, a.cikti)
    except VeriCekmeHatasi as e:
        print(f"HATA: {e}", file=sys.stderr)
        return 1

    boyut = Path(ozet["dosya"]).stat().st_size / 1_048_576
    print(f"\nToplam {ozet['gozlem']} gozlem yazildi ({boyut:.1f} MB)")
    print(f"  sis (gorus<{SIS_GORUS_M} m veya FG): {ozet['sis']}")
    print(f"  LVO seviyesi (gorus<{LVO_GORUS_M} m): {ozet['lvo']}")
    atlanan = ozet["atlanan"]
    print(f"  atlanan: {sum(atlanan.values())}")
    for neden, sayi in atlanan.most_common():
        print(f"    - {neden}: {sayi}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
