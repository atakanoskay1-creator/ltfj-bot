#!/usr/bin/env python3
"""
ayarlar.json yukleyicisi.

Dosya yoksa ya da bozuksa varsayilanlarla devam eder - bot bir ayar dosyasi
yuzunden durmaz. Eksik anahtarlar varsayilandan tamamlanir, yani ayarlar.json'a
sadece degistirmek istedigin satiri yazman yeter.
"""

import json
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
DOSYA = KLASOR / "ayarlar.json"

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
