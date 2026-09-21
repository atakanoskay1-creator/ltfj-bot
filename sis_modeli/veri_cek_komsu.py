#!/usr/bin/env python3
"""Komsu istasyonlarin METAR arsivini IEM'den ceker.

LTFJ'nin kendi arsivi (veri_cek.py) ile AYNI mekanizma - IEM ASOS'tan sadece
farkli bir ICAO kodu icin cekilir, sutun semasi (ozellik.SUTUNLAR) aynidir.
Ikinci bir ayristirici YAZILMAZ; veri_cek.arsivi_uret dogrudan yeniden
kullanilir (istasyon parametreli).

AMAC: sis/dusuk tavan bolgesel yayilir. Komsu istasyonda birkac saat once
gorulen dusuk gorus/tavan, LTFJ icin bir ONCU (mekansal) sinyal olabilir -
bu HENUZ dogrulanmamis bir aday, sadece veri toplama asamasidir.

Her istasyon icin AYRI bir dosyaya yazilir (komsu_<icao>_ozellik.csv.gz) -
LTFJ'nin kendi ltfj_ozellik.csv.gz'i ile KARISTIRILMAZ. Birlestirme/hizalama
(zaman damgasina gore en yakin gozlem eslestirme) ayri bir modulun isi
olacak - bu betik sadece HAM cekim yapar.

Ag erisimi gerektirdigi icin GitHub Actions'ta calisir.

Kullanim:
    python -m sis_modeli.veri_cek_komsu --baslangic 2003 --bitis 2026
    python -m sis_modeli.veri_cek_komsu --istasyonlar LTFM LTBA
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from sis_modeli.veri_cek import VeriCekmeHatasi, arsivi_uret

# LTFM: Istanbul Havalimani - LTFJ'ye (Sabiha Gokcen) en yakin buyuk trafikli
# komsu, Bogaz'in Avrupa yakasinda, ~35 km kuzeybati. Baska komsu eklemek
# icin --istasyonlar ile CLI'dan gecilebilir, koda dokunmak gerekmez.
VARSAYILAN_ISTASYONLAR = ("LTFM",)
VARSAYILAN_DIZIN = Path(__file__).resolve().parent / "veri"


def cikti_yolu(istasyon: str, dizin: Path = VARSAYILAN_DIZIN) -> Path:
    return dizin / f"komsu_{istasyon.lower()}_ozellik.csv.gz"


def main(argv=None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--istasyonlar", nargs="+",
                             default=list(VARSAYILAN_ISTASYONLAR))
    ayristirici.add_argument("--baslangic", type=int, default=2003)
    ayristirici.add_argument("--bitis", type=int,
                             default=datetime.now(timezone.utc).year)
    ayristirici.add_argument("--dizin", type=Path, default=VARSAYILAN_DIZIN)
    a = ayristirici.parse_args(argv)

    for istasyon in a.istasyonlar:
        cikti = cikti_yolu(istasyon, a.dizin)
        print(f"{istasyon} arsivi: {a.baslangic}-{a.bitis}")
        try:
            ozet = arsivi_uret(a.baslangic, a.bitis, cikti, istasyon)
        except VeriCekmeHatasi as e:
            print(f"HATA ({istasyon}): {e}", file=sys.stderr)
            return 1

        boyut = Path(ozet["dosya"]).stat().st_size / 1_048_576
        print(f"  {ozet['gozlem']} gozlem yazildi ({boyut:.1f} MB), "
              f"sis {ozet['sis']}, lvo {ozet['lvo']}, "
              f"atlanan {sum(ozet['atlanan'].values())}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
