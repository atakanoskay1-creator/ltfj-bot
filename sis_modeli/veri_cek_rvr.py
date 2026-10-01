#!/usr/bin/env python3
"""LTFJ METAR arsivinden pist ucu bazli RVR'i ceker - AYRI bir veri dosyasi.

NEDEN: LVO Hazirlik Safhasi (TL.007 madde 6.2.a) RVR < 800 m ya da bulut
tabaninin CAT II seviyesine (200 ft alti) inmesiyle baslar. Egitim arsivi
(veri/ltfj_ozellik.csv.gz) gorus ve tavani tasiyor ama RVR'i SAKLAMIYOR;
Omerli senaryosunda (genel gorus yuksek, 24 basinda RVR dusuk) asil sinyal
RVR'da (README "Parcali sis, 24 pist basi ve RVR").

ltfj_ozellik.csv.gz DEGISMEZ (dondurulmus). Bu betik ayni IEM kaynagindan,
ayni istasyon korumasiyla (metindeki ICAO LTFJ olmali, IEM_DS3505 atilir)
yalnizca RVR sutunlarini uretir; iki dosya `zaman` uzerinden birlesir.

SUTUNLAR
  zaman    "YYYY-MM-DDTHH:MM" UTC (ltfj_ozellik ile ayni bicim)
  rvr_06   06 ucundaki (06, 06L, 06R) en dusuk RVR, metre
  rvr_24   24 ucundaki (24, 24L, 24R) en dusuk RVR, metre
  rvr_min  tum gruplarin en dusugu
  rvr_ham  gozlem kismindaki RVR gruplari, oldugu gibi (L/R ayrimi icin)
Gozlemde RVR grubu yoksa RVR alanlari bos kalir (RVR yalnizca gorus ya da
RVR 1500 m altindayken raporlanir). Degisken RVR'da (0600V1000) alt deger,
M/P onekinde sayi alinir (M0050 -> 50, P2000 -> 2000). Trend ve RMK
sayilmaz. Ayni zaman iki kez gelirse ilki kalir.

Ag erisimi gerektirir; GitHub Actions'ta calisir (sis-veri-rvr.yml).

Kullanim (repo kokunden):
    python -m sis_modeli.veri_cek_rvr --baslangic 2012 --bitis 2026
"""

import argparse
import csv
import gzip
import io
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

from sis_modeli.rvr_pist import govde
from sis_modeli.veri_cek import (IEM_YENIDEN_KURULMUS, ISTASYON, VeriCekmeHatasi,
                                 _yil_indir, metar_istasyonu)

VARSAYILAN_CIKTI = Path(__file__).resolve().parent / "veri" / "ltfj_rvr.csv.gz"
SUTUNLAR = ("zaman", "rvr_06", "rvr_24", "rvr_min", "rvr_ham")
RVR_GRUBU = re.compile(r"(?<![A-Z0-9])R(\d{2})([LRC]?)/([PM]?)(\d{4})\S*")


def rvr_cikar(metin: str) -> dict:
    """METAR metninden {rvr_06, rvr_24, rvr_min, rvr_ham}; grup yoksa None'lar."""
    uclar, gruplar = {}, []
    for m in RVR_GRUBU.finditer(govde(metin)):
        uc, deger = m.group(1), int(m.group(4))
        gruplar.append(m.group(0))
        uclar[uc] = min(deger, uclar.get(uc, deger))
    return {
        "rvr_06": uclar.get("06"),
        "rvr_24": uclar.get("24"),
        "rvr_min": min(uclar.values()) if uclar else None,
        "rvr_ham": " ".join(gruplar),
    }


def satirlari_coz(ham_csv: str, istasyon: str = ISTASYON) -> tuple[list, Counter]:
    """IEM CSV'sinden RVR satirlari ve atlama sayaci (veri_cek ile ayni korumalar)."""
    satirlar, atlanan, gorulen = [], Counter(), set()
    for kayit in csv.DictReader(io.StringIO(ham_csv)):
        metin = (kayit.get("metar") or "").strip()
        ham_zaman = (kayit.get("valid") or "").strip()
        if not metin or not ham_zaman:
            atlanan["metar/zaman bos"] += 1
            continue
        if IEM_YENIDEN_KURULMUS in metin:
            atlanan["IEM_DS3505 (ISD'den yeniden kurulmus)"] += 1
            continue
        if metar_istasyonu(metin) != istasyon:
            atlanan[f"baska istasyon ({metar_istasyonu(metin) or '?'})"] += 1
            continue
        try:
            zaman = datetime.strptime(ham_zaman, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            atlanan["zaman ayristirilamadi"] += 1
            continue
        anahtar = zaman.strftime("%Y-%m-%dT%H:%M")
        if anahtar in gorulen:
            atlanan["ayni zaman tekrar"] += 1
            continue
        gorulen.add(anahtar)
        satirlar.append({"zaman": anahtar, **rvr_cikar(metin)})
    return satirlar, atlanan


def arsivi_uret(baslangic: int, bitis: int, cikti: Path, istasyon: str = ISTASYON) -> dict:
    cikti.parent.mkdir(parents=True, exist_ok=True)
    ozet = Counter()
    with gzip.open(cikti, "wt", encoding="utf-8", newline="") as f:
        yazici = csv.DictWriter(f, fieldnames=list(SUTUNLAR))
        yazici.writeheader()
        with requests.Session() as oturum:
            for yil in range(baslangic, bitis + 1):
                satirlar, atlanan = satirlari_coz(_yil_indir(yil, oturum, istasyon), istasyon)
                for s in satirlar:
                    yazici.writerow({k: "" if s[k] is None else s[k] for k in SUTUNLAR})
                rvrli = [s for s in satirlar if s["rvr_min"] is not None]
                alti800 = sum(s["rvr_min"] < 800 for s in rvrli)
                ozet.update(gozlem=len(satirlar), rvrli=len(rvrli), alti800=alti800,
                            atlanan=sum(atlanan.values()))
                print(f"  {yil}: {len(satirlar)} gozlem, RVR'li {len(rvrli)}, "
                      f"RVR<800 {alti800}, atlanan {sum(atlanan.values())} {dict(atlanan)}")
    return dict(ozet)


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--baslangic", type=int, default=2012)
    a.add_argument("--bitis", type=int, default=datetime.now(timezone.utc).year)
    a.add_argument("--cikti", type=Path, default=VARSAYILAN_CIKTI)
    s = a.parse_args(argv)
    print(f"{ISTASYON} RVR arsivi: {s.baslangic}-{s.bitis}")
    try:
        ozet = arsivi_uret(s.baslangic, s.bitis, s.cikti)
    except VeriCekmeHatasi as e:
        print(f"HATA: {e}", file=sys.stderr)
        return 1
    print(f"\nToplam {ozet.get('gozlem', 0)} gozlem, RVR'li {ozet.get('rvrli', 0)}, "
          f"RVR<800 {ozet.get('alti800', 0)} -> {s.cikti}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
