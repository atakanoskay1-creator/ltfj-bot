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

KAPSAM - BU BETİK HENÜZ CANLI TAHMİNE BAĞLANMADI. Önbellek yazılıyor ama
hiçbir yerde OKUNMUYOR (ltfj_bot.py/ltfj_sayfa.py bu dosyayı henüz import
etmiyor) - bağlama, istatistiksel doğrulamadan AYRI ve SONRAKİ bir karar
(bkz. sis_modeli/README.md "KRİTİK MİMARİ FARK" notu).

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
