#!/usr/bin/env python3
"""Dış kaynak (Open-Meteo bağıl nem + komşu istasyon LTFM tavanı) için
GEVŞEK BAĞLI önbellekleyici.

NEDEN AYRI BİR BETİK: sis_modeli/tavan_dis_kaynak_model.py holdout'ta
doğruladı (bkz. sis_modeli/README.md) ki bu iki değişken tavan<500ft
tahminine gerçek katkı sağlıyor - ama canlıda doğrudan kullanmak, ana bot
döngüsünü (ltfj_bot.py, 15 dakikada bir, 5 DAKİKALIK SERT ZAMAN BÜTÇESİ,
bkz. .github/workflows/ltfj.yml) Open-Meteo/MGM'e bağımlı hale getirir.
Bugün tam da bu tür kaynaklarda hız limiti ve gecikme YAŞANDI (bkz.
sis_modeli/veri_cek_acik_meteo.py'nin commit geçmişi) - ana botu buna
DOĞRUDAN bağlamak riskli.

TASARIM - GEVŞEK BAĞLILIK:
  1. Bu betik AYRI, kendi zamanlamasında çalışır - ltfj.yml'nin 15 dk'lık
     döngüsüyle SENKRONİZE DEĞİL, ayrı bir GitHub Actions workflow'u
     (dis-kaynak-onbellek.yml).
  2. Sonucu küçük bir JSON dosyasına (dis_kaynak_cache.json) YAZAR - diğer
     durum dosyaları (ltfj_state.json, panel_veri.json) gibi repoya
     commit edilir.
  3. Ana bot (ileride bağlanırsa) bu dosyayı OKUR - yerel, ağsız,
     milisaniyeler sürer - Open-Meteo/MGM'e ASLA doğrudan bağlanmaz.
  4. BAYATLIK KONTROLÜ: oku() her alanın YAŞINI ayrı ayrı kontrol eder;
     ESIK_DK'dan eskiyse (veya hiç yoksa) o alan İÇİN None döner - "bu
     dış veri kullanılamıyor" sinyali. Çağıran taraf bunu TEMEL'e (dış
     kaynaksız model) düşmenin işareti olarak kullanmalı.
  5. KISMİ HATA TOLERANSI: iki kaynaktan biri başarısız olursa, diğerinin
     YENİ değeri yine de yazılır; başarısız olanın ESKİ değeri (kendi
     zaman damgasıyla) korunur - TEK kaynağın çökmesi diğerini kirletmez.

CANLI VERİ KAYNAĞI SEÇİMİ: Open-Meteo'nun eğitimde kullanılan tarihsel
ARŞİV API'si (archive-api.open-meteo.com) burada KULLANILMAZ - o uç nokta
gecikmeli/geçici (ERA5T tipi) veri döndürebilir. Bunun yerine gerçek
zamanlı FORECAST API'sinin (api.open-meteo.com) "current" bloğu kullanılır.

ÖNBELLEĞİN İKİ AYRI TÜKETİCİSİ VAR:
  * oku()        - model girdileri (acik_meteo_nem_2m, komsu_tavan_ozellik).
                   ltfj_lvo_farkindalik.py bunları dondurulmuş modele verir;
                   bayatsa None döner ve model TEMEL'e düşer.
  * tahmin_oku() - saatlik model tahmini, SADECE sayfada gösterilir.
                   Hiçbir modele girdi DEĞİLDİR ve TAF'ın yerine geçmez -
                   geriye dönük dürüst test edilemediği için (Open-Meteo'nun
                   Previous Runs arşivi 2024'ten başlıyor, holdout
                   penceremizle çakışıyor) tahmine dayalı bir özellik
                   eğitilmedi; bu blok bilgi amaçlıdır.

Kullanım:
    python -m ltfj_dis_kaynak_cache             # çek + yaz (ağ gerekir)
    python -m ltfj_dis_kaynak_cache --oku        # sadece mevcut önbelleği oku
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

import ltfj_rasat
from ltfj_analiz import metar_coz

VARSAYILAN_DOSYA = Path(__file__).resolve().parent / "dis_kaynak_cache.json"

# Bundan eskiyse alan "dış veri yok" sayılır - onbellek yazma cadence'i
# (varsayılan 20 dk, dis-kaynak-onbellek.yml) + birkaç deneme payı.
ESIK_DK = 45

# Saatlik tahminin bayatlık eşiği AYRI ve daha uzun: "şu anki nem" 45
# dakikada anlamını yitirir, ama 12 saatlik bir tahmin 2 saat önce
# çekilmiş olsa da hâlâ kullanılabilir (yalnızca ilk saatleri geçmişte
# kalır, onları zaten ayıklıyoruz). Model girdileriyle AYNI eşiğe
# bağlamak, kullanılabilir bir tahmini gereksiz yere çöpe atardı.
# ÖLÇÜLDÜ, tahmin edilmedi: cron ":3,23,43" (20 dk) ayarlı ama GitHub
# zamanlanmış koşuları düşürüyor - 26 saatte 78 yerine 6 planlı koşu
# gerçekleşti, aralıklar 2-6 saat (hepsi BAŞARILI; çekme kodu sağlam).
# 180 dk eşik bu gerçek kadansın altındaydı, bu yüzden şerit zamanın
# önemli bir kısmında kayboluyordu ("bazen görünüyor bazen görünmüyor").
#
# Sert eşiğin zaten sınırlı bir işi var: aşağıdaki ayıklama geçmiş
# saatleri kendiliğinden atıyor, yani bayat tahmin GİDEREK KISALIYOR ve
# son satırı da geçince şerit kendiliğinden kayboluyor. Eşik yalnızca
# "çok daha eski bir model çevriminden gelmiş" durumu keser.
TAHMIN_ESIK_DK = 360

# Kaç saat ileriye bakılacağı. 12 saat, bir vardiyayı ve sis için kritik
# gece/sabah penceresini kapsar; daha uzunu sayfada okunabilirliği bozar.
TAHMIN_SAAT = 12

# Sis/tavan açısından anlamlı olanlar: spread (sıcaklık - çiy noktası) bu
# projedeki en güçlü öncü göstergeydi (bkz. sis_modeli/README.md), görüş
# ve düşük bulut ise sonucun kendisine en yakın alanlar.
HOURLY_ALANLAR = (
    "temperature_2m", "dew_point_2m", "relative_humidity_2m",
    "wind_speed_10m", "wind_direction_10m", "cloud_cover_low", "visibility",
)

# BU ALANLARIN bu uç noktada kabul edildiği DOĞRULANAMADI (Open-Meteo
# dokümanı bu ortamdan okunamıyor; boundary_layer_height dokümanlarda
# ECMWF uç noktasına atfediliyor). Open-Meteo GEÇERSİZ bir alan görünce
# isteğin TAMAMINI hata ile döndürür - yani bunları çekirdek listeye
# koymak, hâlihazırda çalışan şeridi tamamen kaybettirebilirdi.
#
# Bu yüzden önce çekirdek + deneysel isteniyor; Open-Meteo reddederse
# SADECE çekirdekle bir kez daha deneniyor. Hangi alanların düştüğü loga
# yazılıyor, böylece sessizce eksik veriyle yaşamıyoruz.
#   weather_code           - WMO kodu; 45 = sis, 48 = kırağılı sis
#   boundary_layer_height  - sığ sınır tabakası + hafif rüzgâr + yüksek nem
#                            radyasyon sisinin fizik imzası
HOURLY_DENEYSEL = ("weather_code", "boundary_layer_height")

# WMO hava kodlarından sis olanlar (bkz. weather_code).
SIS_KODLARI = (45, 48)

LTFJ_ENLEM, LTFJ_BOYLAM = 40.8986, 29.3092
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"   # FORECAST - arşiv DEĞİL
KOMSU_ICAO = "LTFM"

# Canlı döngüde kısa tutulur - ana botun bütçesini yemesin diye DEĞİL
# (bu betik ayrı çalışır) ama kendi workflow'unun da asılı kalmaması için.
ZAMAN_ASIMI = 15


class OnbellekHatasi(Exception):
    pass


def _acik_meteo_nem_cek() -> float:
    parametreler = {"latitude": LTFJ_ENLEM, "longitude": LTFJ_BOYLAM,
                    "current": "relative_humidity_2m", "timezone": "UTC"}
    c = requests.get(OPEN_METEO_URL, params=parametreler, timeout=ZAMAN_ASIMI)
    try:
        veri = c.json()
    except ValueError:
        c.raise_for_status()
        raise OnbellekHatasi(f"Open-Meteo: yanıt JSON değil (HTTP {c.status_code})")
    if isinstance(veri, dict) and veri.get("error"):
        raise OnbellekHatasi(f"Open-Meteo hata döndürdü - {veri.get('reason')}")
    c.raise_for_status()
    nem = veri.get("current", {}).get("relative_humidity_2m")
    if nem is None:
        raise OnbellekHatasi("Open-Meteo yanıtında 'current.relative_humidity_2m' yok")
    return nem


def _hourly_iste(alanlar: tuple) -> tuple[dict, tuple]:
    """Open-Meteo saatlik bloğunu ister; (yanıt, istenen alanlar) döner.

    Hata gövdesini OnbellekHatasi'na çevirir - çağıran taraf bunu
    "bu alan listesi kabul edilmedi" sinyali olarak kullanır."""
    parametreler = {
        "latitude": LTFJ_ENLEM, "longitude": LTFJ_BOYLAM,
        "hourly": ",".join(alanlar), "timezone": "UTC",
        "forecast_days": 2,
    }
    c = requests.get(OPEN_METEO_URL, params=parametreler, timeout=ZAMAN_ASIMI)
    try:
        veri = c.json()
    except ValueError:
        c.raise_for_status()
        raise OnbellekHatasi(f"Open-Meteo: yanıt JSON değil (HTTP {c.status_code})")
    if isinstance(veri, dict) and veri.get("error"):
        raise OnbellekHatasi(f"Open-Meteo hata döndürdü - {veri.get('reason')}")
    c.raise_for_status()
    return veri, alanlar


def _saatlik_tahmin_cek() -> list[dict]:
    """Önümüzdeki TAHMIN_SAAT saatin model tahmini.

    DİKKAT - bu bir MODEL tahminidir, TAF DEĞİLDİR: resmî havacılık
    tahmini yerine geçmez, sayfada da açıkça öyle etiketlenir. Amaç
    eğilimi görmek (spread daralıyor mu, nem yükseliyor mu), kesin bir
    değer okumak değil.

    Open-Meteo saatlik bloğu GEÇMİŞ saatleri de döndürür (günün başından
    itibaren); şu andan öncekiler ayıklanır."""
    # Once cekirdek + deneysel; Open-Meteo deneysel alanlardan birini
    # tanimazsa TUM istegi reddeder, o yuzden SADECE cekirdekle bir kez
    # daha deneniyor (bkz. HOURLY_DENEYSEL).
    try:
        veri, alanlar = _hourly_iste(HOURLY_ALANLAR + HOURLY_DENEYSEL)
    except OnbellekHatasi as e:
        print(f"[uyarı] Open-Meteo deneysel alanları ({', '.join(HOURLY_DENEYSEL)}) "
              f"kabul etmedi, onlarsız deneniyor: {e}", file=sys.stderr)
        veri, alanlar = _hourly_iste(HOURLY_ALANLAR)

    saatlik = veri.get("hourly") or {}
    zamanlar = saatlik.get("time") or []
    if not zamanlar:
        raise OnbellekHatasi("Open-Meteo yanıtında 'hourly.time' yok")

    simdi = datetime.now(timezone.utc)
    satirlar = []
    for i, zaman_str in enumerate(zamanlar):
        try:
            zaman = datetime.fromisoformat(zaman_str).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if zaman < simdi:
            continue
        satir = {"saat": zaman_str}
        for alan in alanlar:
            dizi = saatlik.get(alan) or []
            satir[alan] = dizi[i] if i < len(dizi) else None
        satirlar.append(satir)
        if len(satirlar) >= TAHMIN_SAAT:
            break

    if not satirlar:
        raise OnbellekHatasi("Open-Meteo yanıtında ileriye dönük saat yok")
    return satirlar


def _komsu_tavan_cek() -> float | None:
    """None dönebilir - bu HATA değil, komşu istasyonda şu an tavan
    bildirilmiyor demektir (CAVOK/SKC), tavan_ft'nin 'veri yok' durumuyla
    aynı anlamda. Kaynağa ULAŞILAMAMASI ayrı, RasatHatasi olarak yükselir."""
    raporlar = ltfj_rasat.raporlari_cek(icao=KOMSU_ICAO, timeout=ZAMAN_ASIMI)
    metar = next((r for r in raporlar if r["tip"] in ("METAR", "SPECI")), None)
    if metar is None:
        raise OnbellekHatasi(f"{KOMSU_ICAO} için METAR/SPECI raporu dönmedi")
    d = metar_coz(metar["metin"])
    return d.get("tavan")


def _oku_ham(dosya: Path) -> dict:
    if not dosya.exists():
        return {}
    try:
        return json.loads(dosya.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def guncelle(dosya: Path = VARSAYILAN_DOSYA) -> dict:
    """İki kaynağı BAĞIMSIZ dener; biri başarısız olursa diğerini
    etkilemez, eski değer (kendi zaman damgasıyla) korunur."""
    onbellek = _oku_ham(dosya)
    simdi = datetime.now(timezone.utc).isoformat()

    try:
        onbellek["acik_meteo_nem_2m"] = _acik_meteo_nem_cek()
        onbellek["acik_meteo_guncelleme"] = simdi
    except (requests.RequestException, OnbellekHatasi) as e:
        print(f"[uyarı] Open-Meteo güncellenemedi, eski değer korunuyor: {e}",
              file=sys.stderr)

    try:
        onbellek["komsu_tavan_ozellik"] = _komsu_tavan_cek()
        onbellek["komsu_guncelleme"] = simdi
    except (ltfj_rasat.RasatHatasi, OnbellekHatasi) as e:
        print(f"[uyarı] {KOMSU_ICAO} güncellenemedi, eski değer korunuyor: {e}",
              file=sys.stderr)

    # Üçüncü kaynak, diğer ikisinden BAĞIMSIZ: çökerse nem/komşu tavanı
    # etkilenmez (ve tersi). Ayrı try bloğu tam olarak bunun için.
    try:
        onbellek["saatlik_tahmin"] = _saatlik_tahmin_cek()
        onbellek["saatlik_tahmin_guncelleme"] = simdi
    except (requests.RequestException, OnbellekHatasi) as e:
        print(f"[uyarı] Saatlik tahmin güncellenemedi, eski değer korunuyor: {e}",
              file=sys.stderr)

    dosya.write_text(json.dumps(onbellek, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    return onbellek


def oku(dosya: Path = VARSAYILAN_DOSYA, esik_dk: float = ESIK_DK) -> dict:
    """Önbellekten OKUR - ağa çıkmaz. Her alan kendi yaşına göre AYRI
    değerlendirilir: bayatsa (veya hiç yoksa) None döner - 'bu dış veri
    kullanılamıyor, TEMEL'e düş' sinyali."""
    ham = _oku_ham(dosya)
    simdi = datetime.now(timezone.utc)
    sonuc = {}
    for alan, zaman_alani in (("acik_meteo_nem_2m", "acik_meteo_guncelleme"),
                              ("komsu_tavan_ozellik", "komsu_guncelleme")):
        deger, zaman_str = ham.get(alan), ham.get(zaman_alani)
        if deger is None and alan not in ham:
            sonuc[alan] = None
            continue
        if zaman_str is None:
            sonuc[alan] = None
            continue
        try:
            zaman = datetime.fromisoformat(zaman_str)
        except ValueError:
            sonuc[alan] = None
            continue
        yas_dk = (simdi - zaman).total_seconds() / 60
        sonuc[alan] = deger if yas_dk <= esik_dk else None
    return sonuc


def tahmin_yasi_dk(dosya: Path = VARSAYILAN_DOSYA) -> float | None:
    """Saatlik tahminin KAÇ DAKİKA ÖNCE çekildiği; yoksa None.

    tahmin_oku()'dan ayrı: sayfa, tahmini gösterirken yaşını da
    yazabilsin diye. Değer gösterilip gösterilmemesi sayfanın kararı;
    burada yalnızca ölçülür."""
    ham = _oku_ham(dosya)
    zaman_str = ham.get("saatlik_tahmin_guncelleme")
    if not zaman_str:
        return None
    try:
        zaman = datetime.fromisoformat(zaman_str)
    except ValueError:
        return None
    if zaman.tzinfo is None:
        zaman = zaman.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - zaman).total_seconds() / 60


def tahmin_oku(dosya: Path = VARSAYILAN_DOSYA,
               esik_dk: float = TAHMIN_ESIK_DK) -> list[dict]:
    """Saatlik tahmini okur; yoksa/bayatsa BOŞ liste döner (None değil -
    çağıran taraf doğrudan döngüye sokabilsin).

    oku()'dan AYRI tutulmasının iki sebebi var: (1) bayatlık eşiği farklı
    (bkz. TAHMIN_ESIK_DK), (2) oku()'nun çıktısı dondurulmuş modele girdi
    olarak gidiyor (ltfj_lvo_farkindalik) - oraya alan eklemek o sözleşmeyi
    kirletirdi.

    Önbellek yazıldığı andan beri geçen saatler AYIKLANIR: 40 dk önce
    yazılmış bir tahminin ilk satırı artık geçmişte kalmış olabilir."""
    ham = _oku_ham(dosya)
    satirlar = ham.get("saatlik_tahmin")
    zaman_str = ham.get("saatlik_tahmin_guncelleme")
    if not isinstance(satirlar, list) or not satirlar or not zaman_str:
        return []
    try:
        zaman = datetime.fromisoformat(zaman_str)
    except ValueError:
        return []
    simdi = datetime.now(timezone.utc)
    if (simdi - zaman).total_seconds() / 60 > esik_dk:
        return []

    taze = []
    for satir in satirlar:
        if not isinstance(satir, dict):
            continue
        try:
            an = datetime.fromisoformat(satir.get("saat", "")).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
        if an >= simdi:
            taze.append(satir)
    return taze


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--dosya", type=Path, default=VARSAYILAN_DOSYA)
    a.add_argument("--esik-dk", type=float, default=ESIK_DK)
    a.add_argument("--oku", action="store_true",
                   help="ağa çıkma, sadece mevcut önbelleği oku ve yazdır")
    secenek = a.parse_args(argv)

    if secenek.oku:
        sonuc = oku(secenek.dosya, secenek.esik_dk)
    else:
        sonuc = guncelle(secenek.dosya)
        sonuc = oku(secenek.dosya, secenek.esik_dk)   # bayatlık filtresinden geçmiş hali göster

    for alan, deger in sonuc.items():
        etiket = "kullanılamıyor (bayat/yok)" if deger is None else str(deger)
        print(f"  {alan:<24}{etiket}")

    tahmin = tahmin_oku(secenek.dosya)
    if not tahmin:
        print("  saatlik_tahmin         kullanılamıyor (bayat/yok)")
    else:
        print(f"  saatlik_tahmin          {len(tahmin)} saat")
        for satir in tahmin:
            sic, cig = satir.get("temperature_2m"), satir.get("dew_point_2m")
            spread = None if sic is None or cig is None else round(sic - cig, 1)
            print(f"    {satir.get('saat')}  T={sic}  Td={cig}  spread={spread}"
                  f"  görüş={satir.get('visibility')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
