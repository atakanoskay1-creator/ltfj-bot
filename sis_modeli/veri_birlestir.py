#!/usr/bin/env python3
"""LTFJ ana arşivini ek veri kaynaklarıyla (komşu istasyon, Open-Meteo) zaman
damgasına göre EN YAKIN gözlem eşleştirmesiyle birleştirir.

SADECE EĞİTİM/ANALİZ içindir. Donmuş runtime modülleri (ltfj_sis_olasilik*.py,
ltfj_tavan_tablosu.py) bunu ASLA import etmez - izolasyon sözleşmesi
(sis_modeli/README.md) burada da geçerlidir. Çıktı ayrı bir dosyaya
YAZILMAZ - kaynak dosyalar zaten repoda, tarama/model kodu gerektiğinde
bu modülü çağırıp yeniden birleştirir.

TOLERANS: her kaynağın kendi örnekleme aralığına göre ayrı bir eşleştirme
penceresi vardır - LTFM METAR gibi düzensiz aralıklı (tipik ~30dk), Open-Meteo
tam saatte sabit ızgara. Pencere dışında eşleşme yoksa alan None kalır -
sessizce çok uzak bir gözlem eşlenmez, "veri yok" olarak bırakılır.
"""

import bisect
import csv
import gzip
from datetime import datetime
from pathlib import Path

VERI_DIZINI = Path(__file__).resolve().parent / "veri"
VARSAYILAN_KOMSU = VERI_DIZINI / "komsu_ltfm_ozellik.csv.gz"
VARSAYILAN_ACIK_METEO = VERI_DIZINI / "acik_meteo_ltfj.csv.gz"

# LTFM METAR düzensiz aralıklı (tipik ~30dk, bazen daha seyrek) - 45dk payı
# tek bir komşu gözlemi kaçırmamak için, ama iki gözlem arası boşluğu
# (tipik ~1-3 saat, SPECI'siz dönemlerde) yanlış eşlemeyecek kadar dar.
KOMSU_TOLERANS_DK = 45
# Open-Meteo tam saatte sabit ızgara - +-30dk her zaman en yakın saati
# kapsar, birkaç dakikalık pay bırakıldı.
ACIK_METEO_TOLERANS_DK = 35

KOMSU_ONEK = "komsu_ltfm_"
ACIK_METEO_ONEK = "acik_meteo_"


def _sayiya_cevir(ham):
    """CSV'den gelen her deger string'dir - istatistik.py::_sayi ile AYNI
    disiplinle sayiya cevirir, cevrilemeyeni (orn. 'zaman' disindaki metin
    alanlar) oldugu gibi birakir, bos olani None yapar."""
    if ham in (None, ""):
        return None
    try:
        return int(ham)
    except (ValueError, TypeError):
        pass
    try:
        return float(ham)
    except (ValueError, TypeError):
        return ham


def _kaynagi_oku(yol: Path) -> list[dict]:
    with gzip.open(yol, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _zaman_indeksi(kayitlar: list[dict]) -> tuple[list[datetime], list[dict]]:
    """(sıralı zaman listesi, aynı sırada kayıt listesi) döner - bisect ile
    en yakın komşuyu O(log n) bulabilmek için."""
    ciftler = sorted(
        ((datetime.fromisoformat(r["zaman"]), r) for r in kayitlar),
        key=lambda cift: cift[0])
    if not ciftler:
        return [], []
    zamanlar, siraliKayitlar = zip(*ciftler)
    return list(zamanlar), list(siraliKayitlar)


def _en_yakini_bul(hedef_dt: datetime, zamanlar: list[datetime],
                   kayitlar: list[dict], tolerans_dk: float) -> dict | None:
    """zamanlar SIRALI olmalı. Tolerans dışında eşleşme yoksa None."""
    if not zamanlar:
        return None
    i = bisect.bisect_left(zamanlar, hedef_dt)
    adaylar = [j for j in (i - 1, i) if 0 <= j < len(zamanlar)]
    if not adaylar:
        return None
    en_yakin = min(adaylar,
                   key=lambda j: abs((zamanlar[j] - hedef_dt).total_seconds()))
    fark_dk = abs((zamanlar[en_yakin] - hedef_dt).total_seconds()) / 60
    if fark_dk > tolerans_dk:
        return None
    return kayitlar[en_yakin]


def zenginlestir(ltfj_kayitlari: list[dict], komsu_yol: Path = VARSAYILAN_KOMSU,
                 acik_meteo_yol: Path = VARSAYILAN_ACIK_METEO) -> list[dict]:
    """Her LTFJ kaydına en yakın komşu istasyon (komsu_ltfm_*) ve Open-Meteo
    (acik_meteo_*) alanlarını önekli olarak ekler. Kaynak dosya yoksa veya
    tolerans dışında eşleşme bulunamazsa o kaydın alanları None kalır -
    çökmez. Kopya döner, girdiyi değiştirmez."""
    komsu_ham = _kaynagi_oku(komsu_yol) if komsu_yol.exists() else []
    acik_meteo_ham = _kaynagi_oku(acik_meteo_yol) if acik_meteo_yol.exists() else []
    komsu_zamanlar, komsu_kayitlar = _zaman_indeksi(komsu_ham)
    am_zamanlar, am_kayitlar = _zaman_indeksi(acik_meteo_ham)

    komsu_alanlari = list(komsu_ham[0].keys()) if komsu_ham else []
    am_alanlari = list(acik_meteo_ham[0].keys()) if acik_meteo_ham else []

    cikti = []
    for r in ltfj_kayitlari:
        y = dict(r)
        dt = r.get("dt") if isinstance(r.get("dt"), datetime) \
            else datetime.fromisoformat(r["zaman"])

        k = _en_yakini_bul(dt, komsu_zamanlar, komsu_kayitlar, KOMSU_TOLERANS_DK)
        for alan in komsu_alanlari:
            if alan == "zaman":
                continue
            y[f"{KOMSU_ONEK}{alan}"] = _sayiya_cevir(k[alan]) if k else None

        a = _en_yakini_bul(dt, am_zamanlar, am_kayitlar, ACIK_METEO_TOLERANS_DK)
        for alan in am_alanlari:
            if alan == "zaman":
                continue
            y[f"{ACIK_METEO_ONEK}{alan}"] = _sayiya_cevir(a[alan]) if a else None

        cikti.append(y)
    return cikti


def turet(kayitlar: list[dict]) -> list[dict]:
    """zenginlestir() çıktısından FİZİKSEL ANLAMLI türetilmiş adaylar üretir -
    ham birleşim sütunlarının kendisi değil, meteorologların kullandığı
    bileşik göstergeler.

    ALÇAK SEVİYE İNVERSİYON GÜCÜ: yüzey sıcaklığı (2m) eksi yükseklikteki
    sıcaklık (925/850 hPa, ~750-1500 m). Normal (inversiyonsuz) atmosferde
    sıcaklık yükseldikçe DÜŞER, yani bu fark POZİTİFTİR. İnversiyon varsa
    (yüzey soğuk, üstte daha sıcak hava - klasik radyasyon sisi ortamı:
    soğuk sakin gece, düşey karışım yok, nem yüzeyde birikir) fark KÜÇÜLÜR
    hatta NEGATİFE döner. Yani düşük/negatif değer güçlü inversiyona işaret
    eder - WoE taraması yönü (monotonluk) buna göre yorumlanmalı, işaretin
    kendisi taramanın sonucunu etkilemez."""
    cikti = []
    for r in kayitlar:
        y = dict(r)
        t2m = r.get("acik_meteo_temperature_2m")
        t925 = r.get("acik_meteo_temperature_925hPa")
        t850 = r.get("acik_meteo_temperature_850hPa")
        y["inversiyon_925"] = (t2m - t925) if (t2m is not None and t925 is not None) else None
        y["inversiyon_850"] = (t2m - t850) if (t2m is not None and t850 is not None) else None
        y["acik_meteo_nem_2m"] = r.get("acik_meteo_relative_humidity_2m")
        y["acik_meteo_ruzgar_10m"] = r.get("acik_meteo_wind_speed_10m")
        y["acik_meteo_bulut_alcak"] = r.get("acik_meteo_cloud_cover_low")
        y["komsu_sis_var"] = r.get("komsu_ltfm_sis")
        y["komsu_lvo_var"] = r.get("komsu_ltfm_lvo")
        y["komsu_tavan_ozellik"] = r.get("komsu_ltfm_tavan")
        y["komsu_gorus"] = r.get("komsu_ltfm_gorus")
        cikti.append(y)
    return cikti
