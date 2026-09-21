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

ILK CALISTIRMADAN OGRENILDI (2026-09-21, GitHub Actions): degisken adlari
(HOURLY_YUZEY / HOURLY_BASINC) DOGRU - 12 yil sorunsuz cekildi. Asil sorun
Open-Meteo'nun ANONIM/anahtarsiz erisimde uyguladigi DAKIKALIK istek limiti
("Minutely API request limit exceeded") - art arda, beklemeden atilan yil
basi istekler bu limite hizla carpiyor. Cozum: yillari TEK TEK degil
YIL_PARCA'lik gruplar halinde (istek sayisini azaltir) ve istekler arasinda
ISTEKLER_ARASI_BEKLEME kadar bekleyerek cekmek; ayrica hiz limiti govdesi
(HTTP 200 + {"error":true,"reason":"...limit exceeded..."}) diger kalici
hatalardan (yanlis parametre adi gibi) AYRI ele alinir - o TEK durumda
retry edilir, digerlerinde hemen ve acik sekilde basarisiz olunur.

IKINCI CALISTIRMADAN OGRENILDI (2026-09-21, ayni gun): hiz limiti duzeltmesi
calisti, ama ICINDE BULUNULAN (henuz bitmemis) yili iceren son dilim "yanlis
end_date" hatasi verdi - kod her dilimin bitisini korukorune "{yil}-12-31"
olarak istiyordu, ama Open-Meteo gelecekteki bir tarihi (henuz yasanmamis
31 Aralik) kabul etmiyor, en fazla BUGUNE kadar veri veriyor. Duzeltme:
istenen end_date artik min(yil sonu, bugun) ile sinirlaniyor.

UCUNCU BULGU (2026-09-21, veri_birlestir.py taramasinda): basinc seviyesi
(HOURLY_BASINC / 925-850hPa) sutunlari BASARIYLA cekildi (API hata vermedi,
tum yillar sorunsuz indi) ama TUM 208 bin satirda BOS (None/'') geldi.
Yuzey alanlari (HOURLY_YUZEY) gercek deger tasiyor - sorun sadece basinc
seviyesi. Demek ki archive-api.open-meteo.com uc noktasi bu parametre
adlarini SESSIZCE kabul edip veri DONDURMUYOR - muhtemelen tarihsel arsiv
uc noktasi basinc seviyesi cikisini hic desteklemiyor (Forecast API'de
olabilir). SONUC: alcak seviye inversiyon gucu fikri BU KAYNAKLA
calismiyor; koddaki HOURLY_BASINC/BASINC_SEVIYELERI kasitli olarak
SILINMEDI (basinc seviyesi baska bir uc nokta/kaynaktan denenmek istenirse
diye), ama tavan_dis_kaynak_tarama.py'deki inversiyon adaylari bu yuzden
hep "kova kurulamadi" veriyor - bu bir BUG DEGIL.

Kullanim:
    python -m sis_modeli.veri_cek_acik_meteo --baslangic 2003 --bitis 2026
"""

import argparse
import csv
import gzip
import sys
import time
from datetime import date, datetime, timezone
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
ZAMAN_ASIMI = 120          # cok yillik tek istek IEM'inkinden daha buyuk olabilir
DENEME = 4
GERI_CEKILME = 5           # gecici ag hatalarinda (5, 10, 20, 40 sn)
HIZ_LIMIT_BEKLEME = 65     # Open-Meteo "try again in one minute" dedigi icin
ISTEKLER_ARASI_BEKLEME = 3 # basarili istekler arasinda - limite hic carpmamak icin
YIL_PARCA = 6              # kac yillik dilimler halinde cekilecek - istek sayisini azaltir

# Open-Meteo'nun hiz limiti govdesinde kullandigi, tanidigimiz ifadeler.
# Bu KALICI bir hata degil (yanlis parametre adi gibi) - RETRY EDILMELI.
_HIZ_LIMIT_IFADELERI = ("limit exceeded", "rate limit")


class AcikMeteoHatasi(Exception):
    pass


def _donem_indir(baslangic_yil: int, bitis_yil: int,
                 oturum: requests.Session) -> dict:
    """Bir yil ARALIGININ saatlik reanalysis verisini
    {degisken: [deger, ...]} olarak dondurur.

    Open-Meteo hatali istekte HTTP 200/400 + {"error": true, "reason": "..."}
    govdesi dondurur - bu yuzden once JSON govdesi okunur, hata anahtari
    kontrol edilir, ANCAK SONRA raise_for_status() cagrilir (govdesiz bir
    502/503 gibi durumlar icin). Hiz limiti govdesi RETRY EDILIR (gecici);
    beklenen degiskenlerden biri yanitta yoksa (yanlis ad, API degisikligi)
    sessizce atlanmaz - o KALICI kabul edilip acik hata verir."""
    etiket = f"{baslangic_yil}-{bitis_yil}"
    # Icinde bulunulan (henuz bitmemis) yil icin 31 Aralik'i istemek API'yi
    # reddettirir - Open-Meteo en fazla BUGUNE kadar veri verir. Ilk gercek
    # calistirmada (2026-09-21) tam olarak bu hatayla karsilasildi: "end_date
    # is out of allowed range ... to 2026-09-21".
    bitis_tarihi = min(date(bitis_yil, 12, 31), datetime.now(timezone.utc).date())
    parametreler = {
        "latitude": LTFJ_ENLEM, "longitude": LTFJ_BOYLAM,
        "start_date": f"{baslangic_yil}-01-01",
        "end_date": bitis_tarihi.isoformat(),
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
                    f"{etiket}: yanit JSON degil (HTTP {c.status_code})")
            if isinstance(veri, dict) and veri.get("error"):
                neden = str(veri.get("reason") or "")
                if any(ifade in neden.lower() for ifade in _HIZ_LIMIT_IFADELERI):
                    son_hata = neden
                    if deneme < DENEME - 1:
                        print(f"  {etiket}: hiz limiti ({neden}), "
                              f"{HIZ_LIMIT_BEKLEME} sn sonra yeniden...",
                              file=sys.stderr)
                        time.sleep(HIZ_LIMIT_BEKLEME)
                    continue
                raise AcikMeteoHatasi(
                    f"{etiket}: Open-Meteo hata dondurdu - {veri.get('reason')}")
            c.raise_for_status()
            saatlik = veri.get("hourly")
            if not saatlik or "time" not in saatlik:
                raise AcikMeteoHatasi(f"{etiket}: yanit 'hourly.time' icermiyor")
            eksik = [d for d in HOURLY_TUMU if d not in saatlik]
            if eksik:
                raise AcikMeteoHatasi(
                    f"{etiket}: API yanitinda beklenen degiskenler yok: {eksik} "
                    "- HOURLY_YUZEY/HOURLY_BASINC adlari Open-Meteo'nun "
                    "guncel API'siyle dogrulanmali")
            return saatlik
        except requests.RequestException as e:
            son_hata = e
            if deneme < DENEME - 1:
                bekle = GERI_CEKILME * (2 ** deneme)
                print(f"  {etiket}: ag hatasi ({e}), {bekle} sn sonra yeniden...",
                      file=sys.stderr)
                time.sleep(bekle)
    raise AcikMeteoHatasi(f"{etiket} icin veri alinamadi: {son_hata}")


def arsivi_uret(baslangic: int, bitis: int, cikti: Path,
                yil_parca: int = YIL_PARCA) -> dict:
    """Yillari YIL_PARCA'lik dilimler halinde indirir, TEK bir gzip CSV'ye
    satir satir yazar. Dilimler arasinda ISTEKLER_ARASI_BEKLEME kadar
    beklenir - amac Open-Meteo'nun dakikalik istek limitine hic carpmamak.

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
            yil = baslangic
            ilk_istek = True
            while yil <= bitis:
                if not ilk_istek:
                    time.sleep(ISTEKLER_ARASI_BEKLEME)
                ilk_istek = False

                parca_bitis = min(yil + yil_parca - 1, bitis)
                saatlik = _donem_indir(yil, parca_bitis, oturum)
                zamanlar = saatlik["time"]
                for i, zaman in enumerate(zamanlar):
                    satir = {"zaman": zaman}
                    satir.update({d: saatlik[d][i] for d in HOURLY_TUMU})
                    yazici.writerow(satir)
                toplam += len(zamanlar)
                print(f"  {yil}-{parca_bitis}: {len(zamanlar)} saatlik gozlem")
                yil = parca_bitis + 1

    return {"gozlem": toplam, "dosya": str(cikti)}


def main(argv=None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--baslangic", type=int, default=2003)
    ayristirici.add_argument("--bitis", type=int,
                             default=datetime.now(timezone.utc).year)
    ayristirici.add_argument("--cikti", type=Path, default=VARSAYILAN_CIKTI)
    ayristirici.add_argument("--yil-parca", type=int, default=YIL_PARCA,
                             help="kac yillik dilimler halinde cekilecek")
    a = ayristirici.parse_args(argv)

    print(f"Open-Meteo (LTFJ {LTFJ_ENLEM},{LTFJ_BOYLAM}): "
          f"{a.baslangic}-{a.bitis}")
    try:
        ozet = arsivi_uret(a.baslangic, a.bitis, a.cikti, a.yil_parca)
    except AcikMeteoHatasi as e:
        print(f"HATA: {e}", file=sys.stderr)
        return 1

    boyut = Path(ozet["dosya"]).stat().st_size / 1_048_576
    print(f"\nToplam {ozet['gozlem']} saatlik gozlem yazildi ({boyut:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
