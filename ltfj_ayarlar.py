#!/usr/bin/env python3
"""
ayarlar.json yukleyicisi.

Dosya yoksa ya da bozuksa varsayilanlarla devam eder - bot bir ayar dosyasi
yuzunden durmaz. Eksik anahtarlar varsayilandan tamamlanir, yani ayarlar.json'a
sadece degistirmek istedigin satiri yazman yeter.
"""

import json
from pathlib import Path
from zoneinfo import ZoneInfo

KLASOR = Path(__file__).resolve().parent
DOSYA = KLASOR / "ayarlar.json"

# LTFJ Turkiye'de, "yerel saat" her zaman Europe/Istanbul demektir. Bunu
# python'un `datetime.astimezone()` (argumansiz) cagrisina birakmak,
# sonucu calisma ortaminin (OS/konteyner) TZ ayarina baglar - sessiz
# saatler gibi karar mantigi bu sekilde ortam degisince fark edilmeden
# kayabilir. Tum modul bu SABIT uzerinden "yerel" hesaplasin diye burada.
YEREL_TZ = ZoneInfo("Europe/Istanbul")

# LTFJ pist ekseni GERCEK yonleri (AIP AD 2.12, AIRAC AMDT 07/26). Hem
# ltfj_analiz.py (yan_ruzgar - Telegram ozet mesajindaki crosswind) hem de
# ltfj_pist.py (PISTLER - pist basi bazinda bas/kuyruk/yan bilesenleri) bu
# TEK degerden besleniyor. Ikisi ayri ayri "64.10"/"244.12" hardcode etseydi,
# gelecekte bir AIRAC guncellemesinde biri degisip digeri unutulursa iki
# hesap sessizce birbirinden sapardi.
PIST_EKSENI_06 = 64.10
PIST_EKSENI_24 = 244.12

VARSAYILAN = {
    "istasyon": "LTFJ",
    "esikler": {
        "gorus_dusuk": 1500,
        "gorus_cok_dusuk": 800,
        "tavan_dusuk": 500,
        "tavan_cok_dusuk": 200,
        "ruzgar_kuvvetli": 25,
        "hamle_kuvvetli": 30,
        "yan_ruzgar_dikkat": 15,
    },
    "bildirim": {
        "sabit_mesaj": True,
        "rutin_metar": "gizle",          # gizle | sessiz | gonder
        "bildir": {
            "speci": True,
            "taf": True,
            "duzeltme": True,
            "dikkat": True,
            "renk_degisimi": True,
        },
        "sessiz_saatler": {"aktif": False, "baslangic": "23:00", "bitis": "07:00"},
    },
    "mesaj": {"bicim": "kisa", "ham_bulten": True, "claude_yorum": True},
    "web_sayfasi": True,
    "atc_paneli": True,
    "notam": {
        # NOTAC entegrasyonu tamamen opsiyonel - NOTAC_API_KEY ortam
        # degiskeni tanimli degilse zaten sessizce devre disi kalir
        # (bkz. ltfj_notam_client.api_anahtari_var_mi()); "aktif": False
        # anahtar tanimli olsa bile ozelligi kapatmak icin ayrica bir anahtar.
        "aktif": True,
        # NOTAM METAR kadar sik degismiyor - varsayilan olarak 6 saatte bir
        # senkronize ediyoruz (API kredisini gereksiz tuketmemek icin).
        "senkron_araligi_saat": 6,
        "location": "LTFJ",
    },
}


def _birlestir(varsayilan: dict, gelen: dict) -> dict:
    """Ic ice sozlukleri varsayilanla tamamlar. '_' ile baslayan anahtarlar
    aciklama satiridir, yok sayilir."""
    sonuc = dict(varsayilan)
    for k, v in (gelen or {}).items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and isinstance(sonuc.get(k), dict):
            sonuc[k] = _birlestir(sonuc[k], v)
        else:
            sonuc[k] = v
    return sonuc


def yukle() -> dict:
    try:
        gelen = json.loads(DOSYA.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(VARSAYILAN)
    return _birlestir(VARSAYILAN, gelen)


AYARLAR = yukle()


def esik(ad: str):
    return AYARLAR["esikler"].get(ad, VARSAYILAN["esikler"].get(ad))


def ayar(*yol, varsayilan=None):
    """ayar('bildirim', 'rutin_metar') -> 'gizle'"""
    d = AYARLAR
    for k in yol:
        if not isinstance(d, dict) or k not in d:
            return varsayilan
        d = d[k]
    return d
