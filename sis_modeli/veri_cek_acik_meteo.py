#!/usr/bin/env python3
"""LTFJ icin Open-Meteo tarihsel reanalysis (ERA5) verisini ceker.

VERI KAYNAGI: Open-Meteo Historical Weather API (archive-api.open-meteo.com),
ECMWF ERA5/ERA5-Land reanalysis tabanli, saatlik, 1940'tan itibaren, API
anahtari GEREKTIRMEZ, ticari olmayan kullanim icin ucretsizdir.
https://open-meteo.com/en/docs/historical-weather-api

NEDEN: IEM ASOS arsivinden (veri_cek.py) TAMAMEN BAGIMSIZ ikinci bir kaynak.
Iki farkli amaca hizmet eder:
  1) Yeni fiziksel oznitelikler - ozellikle basinc seviyesi (925/850 hPa)
     sicaklik/nem alanlari, klasik radyasyon sisi tahmininde kullanilan
     ALCAK SEVIYE INVERSIYON gucunun turetilmesini saglar (yuzey sicakligi
     ile 850hPa sicakligi arasindaki fark ne kadar buyukse inversiyon o
     kadar guclu, radyasyon sisi riski o kadar yuksek).
  2) Capraz dogrulama - IEM'den BAGIMSIZ oldugu icin, 2021-2023 ciy noktasi
     kusuru gibi sensor kaymalarini gelecekte otomatik yakalamaya yardimci
     olabilir (bkz. veri_kalitesi.py).

ONEMLI KISIT: bu veri SADECE EGITIM/ANALIZ icindir. Donmuş runtime
modulleri (ltfj_sis_olasilik*.py, ltfj_tavan_tablosu.py) bu modulu ASLA
import etmez - izolasyon sozlesmesi (sis_modeli/README.md) burada da
gecerlidir. Canli tahmin hala yalnizca METAR'dan turetilen ozniteliklerle
calisir; bu ek dis API bagimliligi RUNTIME'A tasinmaz - sadece anlamli bir
katki KANITLANIRSA ayri bir karar olarak degerlendirilecek.

KOORDINAT: LTFJ (Istanbul Sabiha Gokcen Uluslararasi Havalimani) resmi
referans noktasi ~40.8986 K, 29.3092 D. ERA5 grid cozunurlugu ~25-31 km
oldugu icin birkac yuz metrelik olasi hata sonucu etkilemez.

DOGRULANAMADI (bu ortamdan): bu betigin canli cekimi bu sandbox'ta test
EDILEMEDI - agin egress proxy'si open-meteo.com'u engelliyor (veri_cek.py
de zaten ayni sekilde SADECE GitHub Actions'ta calisir, yerelde degil).
Asagidaki degisken adlari (HOURLY_YUZEY / HOURLY_BASINC) Open-Meteo'nun
belgelenmis API sozlesmesine dayanir ama GERCEK cekim ilk kez GitHub
Actions'ta calistirildiginda dogrulanmali. Bir degisken adi yanlissa veya
API beklenmedik bir govde donduruyorsa bu betik SESSIZCE BOS SUTUN URETMEZ -
acik bir AcikMeteoHatasi firlatir (bkz. _yil_indir).

Kullanim:
    python -m sis_modeli.veri_cek_acik_meteo --baslangic 2003 --bitis 2026
"""

import argparse
import csv
import gzip
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

API_URL = "https://archive-api.open-meteo.com/v1/archive"
LTFJ_ENLEM = 40.8986
LTFJ_BOYLAM = 29.3092

# Basinc seviyeleri: 925/850 hPa, alcak seviye inversiyon gucu icin klasik
# radyasyon sisi tahmin degiskenleri (bkz. modul dokumantasyonu).
BASINC_SEVIYELERI = (925, 850)

HOURLY_YUZEY = (
    "temperature_2m", "dew_point_2m", "relative_humidity_2m",
    "surface_pressure", "pressure_msl",
    "cloud_cover", "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high",
    "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
)
HOURLY_BASINC = tuple(
    f"{degisken}_{seviye}hPa"
    for seviye in BASINC_SEVIYELERI
    for degisken in ("temperature", "relative_humidity",
                     "wind_speed", "wind_direction")
)
HOURLY_TUMU = HOURLY_YUZEY + HOURLY_BASINC

VARSAYILAN_CIKTI = (Path(__file__).resolve().parent / "veri"
                    / "acik_meteo_ltfj.csv.gz")
ZAMAN_ASIMI = 60
DENEME = 4
GERI_CEKILME = 5


class AcikMeteoHatasi(Exception):
    pass


def _yil_indir(yil: int, oturum: requests.Session) -> dict:
    """Bir yilin saatlik reanalysis verisini {degisken: [deger, ...]} olarak
    dondurur.

    Open-Meteo hatali istekte HTTP 400 + {"error": true, "reason": "..."}
    govdesi dondurur - bu yuzden once JSON govdesi okunur, hata anahtari
    kontrol edilir, ANCAK SONRA raise_for_status() cagrilir (govdesiz bir
    502/503 gibi durumlar icin). Beklenen degiskenlerden biri yanitta
    yoksa (yanlis ad, API degisikligi) sessizce atlanmaz - acik hata verir."""
    parametreler = {
        "latitude": LTFJ_ENLEM, "longitude": LTFJ_BOYLAM,
        "start_date": f"{yil}-01-01", "end_date": f"{yil}-12-31",
        "hourly": ",".join(HOURLY_TUMU),
        "timezone": "UTC",
    }
    son_hata = None
    for deneme in range(DENEME):
        try:
            c = oturum.get(API_URL, params=parametreler, timeout=ZAMAN_ASIMI)
            try:
                veri = c.json()
            except ValueError:
                c.raise_for_status()
                raise AcikMeteoHatasi(
                    f"{yil}: yanit JSON degil (HTTP {c.status_code})")
            if isinstance(veri, dict) and veri.get("error"):
                raise AcikMeteoHatasi(
                    f"{yil}: Open-Meteo hata dondurdu - {veri.get('reason')}")
            c.raise_for_status()
            saatlik = veri.get("hourly")
            if not saatlik or "time" not in saatlik:
                raise AcikMeteoHatasi(f"{yil}: yanit 'hourly.time' icermiyor")
            eksik = [d for d in HOURLY_TUMU if d not in saatlik]
            if eksik:
                raise AcikMeteoHatasi(
                    f"{yil}: API yanitinda beklenen degiskenler yok: {eksik} "
                    "- HOURLY_YUZEY/HOURLY_BASINC adlari Open-Meteo'nun "
                    "guncel API'siyle dogrulanmali")
            return saatlik
        except requests.RequestException as e:
            son_hata = e
            if deneme < DENEME - 1:
                bekle = GERI_CEKILME * (2 ** deneme)
                print(f"  {yil}: ag hatasi ({e}), {bekle} sn sonra yeniden...",
                      file=sys.stderr)
                time.sleep(bekle)
    raise AcikMeteoHatasi(f"{yil} icin veri alinamadi: {son_hata}")


def arsivi_uret(baslangic: int, bitis: int, cikti: Path) -> dict:
    """Yillari sirayla indirir, TEK bir gzip CSV'ye satir satir yazar.

    Sutunlar: zaman + HOURLY_TUMU. 'zaman' formati veri_cek.py'nin kendi
    ozellik ciktisiyla AYNI (Open-Meteo timezone=UTC ile %Y-%m-%dT%H:%M
    dondurur) - ileride birlestirme (join) modulu string esitligiyle
    hizalayabilsin diye."""
    cikti.parent.mkdir(parents=True, exist_ok=True)
    sutunlar = ("zaman",) + HOURLY_TUMU
    toplam = 0

    with gzip.open(cikti, "wt", encoding="utf-8", newline="") as f:
        yazici = csv.DictWriter(f, fieldnames=list(sutunlar))
        yazici.writeheader()
        with requests.Session() as oturum:
            for yil in range(baslangic, bitis + 1):
                saatlik = _yil_indir(yil, oturum)
                zamanlar = saatlik["time"]
                for i, zaman in enumerate(zamanlar):
                    satir = {"zaman": zaman}
                    satir.update({d: saatlik[d][i] for d in HOURLY_TUMU})
                    yazici.writerow(satir)
                toplam += len(zamanlar)
                print(f"  {yil}: {len(zamanlar)} saatlik gozlem")

    return {"gozlem": toplam, "dosya": str(cikti)}


def main(argv=None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--baslangic", type=int, default=2003)
    ayristirici.add_argument("--bitis", type=int,
                             default=datetime.now(timezone.utc).year)
    ayristirici.add_argument("--cikti", type=Path, default=VARSAYILAN_CIKTI)
    a = ayristirici.parse_args(argv)

    print(f"Open-Meteo (LTFJ {LTFJ_ENLEM},{LTFJ_BOYLAM}): "
          f"{a.baslangic}-{a.bitis}")
    try:
        ozet = arsivi_uret(a.baslangic, a.bitis, a.cikti)
    except AcikMeteoHatasi as e:
        print(f"HATA: {e}", file=sys.stderr)
        return 1

    boyut = Path(ozet["dosya"]).stat().st_size / 1_048_576
    print(f"\nToplam {ozet['gozlem']} saatlik gozlem yazildi ({boyut:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
