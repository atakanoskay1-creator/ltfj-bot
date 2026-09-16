#!/usr/bin/env python3
"""
ATC panel (panel.html) icin yapilandirilmis veri ureticisi.

panel.html tamamen istemci tarafinda calisan, statik, tek dosyalik bir
sayfadir - Python tarafinda uretilmez. Bunun yerine bot her calistiginda
panel_veri.json'u yeniden yazar, panel.html bunu fetch() ile okuyup
widget'lari render eder. Boylece ayni cozumleme/hesaplama kodu (metar_coz,
havacilik_notlari, pist bilesenleri) hem Telegram mesajlari hem de bu panel
icin tek yerden, tek dogru kaynaktan besleniyor.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from ltfj_analiz import metar_coz, ozet_satiri, uyarilar
from ltfj_pist import (
    PISTLER,
    TERCIHLI_PISTLER,
    bilesenler,
    havacilik_notlari,
    kuyruk_limiti,
    pist_ruzgarlari,
)


def _pist_verisi(cozum: dict, metin: str) -> dict:
    """Pist basi ruzgar bilesenlerini SAYISAL olarak dondurur (panel.html
    kendi SVG okunu ve etiketlerini bunlardan cizer - onceden bicimlenmis
    metin degil)."""
    olculenler = pist_ruzgarlari(metin)
    limit, limit_gerekce = kuyruk_limiti(cozum)

    if olculenler:
        kaynak = [(o["pist"], o["yon"], max(o["hiz"] or 0, o["hamle"] or 0))
                  for o in olculenler]
        kaynak_tipi = "anemometre"
    else:
        hiz = max(cozum["ruzgar_hiz"] or 0, cozum["ruzgar_hamle"] or 0)
        kaynak = [(p, cozum["ruzgar_yon"], hiz) for p in TERCIHLI_PISTLER]
        kaynak_tipi = "alan_ruzgari"

    pistler = []
    for pist, yon, hiz in kaynak:
        yonu = PISTLER.get(pist, {}).get("yon")
        if yonu is None or yon is None:
            continue
        bas, yan, taraf = bilesenler(yon, hiz, yonu)
        if bas is None:
            continue
        pistler.append({
            "pist": pist,
            "yon_gercek": yonu,
            "bas": round(bas, 1),
            "yan": round(yan, 1),
            "yan_taraf": taraf,
            "kuyruk": bas < 0,
            "kuyruk_asildi": bool(bas < 0 and abs(bas) > limit),
        })

    return {
        "pistler": sorted(pistler, key=lambda p: p["pist"]),
        "kaynak": kaynak_tipi,
        "kuyruk_limiti": limit,
        "kuyruk_gerekce": limit_gerekce,
    }


def _metar_json(rapor: dict) -> dict:
    cozum = metar_coz(rapor["metin"])
    notlar = havacilik_notlari(cozum, rapor["metin"], rapor.get("zaman"))
    dikkat = uyarilar(cozum)
    if notlar["ws"]:
        dikkat.insert(0, "RÜZGÂR KESMESİ: " + ", ".join(notlar["ws"]))
    pist_verisi = _pist_verisi(cozum, rapor["metin"])

    return {
        "tip": rapor["tip"],
        "duzeltme": rapor.get("duzeltme"),
        "zaman": rapor["zaman"].isoformat(timespec="seconds") if rapor.get("zaman") else None,
        "metin": rapor["metin"],
        "ruzgar": {
            "yon": cozum["ruzgar_yon"], "hiz": cozum["ruzgar_hiz"],
            "hamle": cozum["ruzgar_hamle"], "degisken": cozum["degisken"],
        },
        "gorus": cozum["gorus"], "cavok": cozum["cavok"], "tavan": cozum["tavan"],
        "hava": cozum["hava"], "sicaklik": cozum["sicaklik"],
        "cig_noktasi": cozum["cig_noktasi"], "qnh": cozum["qnh"],
        "nosig": cozum["nosig"],
        "renk": list(notlar["renk"]) if notlar["renk"] else None,
        "dikkat": dikkat,
        "pistler": pist_verisi["pistler"],
        "pist_kaynagi": pist_verisi["kaynak"],
        "kuyruk_limiti": pist_verisi["kuyruk_limiti"],
        "kuyruk_gerekce": pist_verisi["kuyruk_gerekce"],
        "tercih_pist": notlar["tercih"],
        "rvr": notlar["rvr"], "prs": notlar["prs"], "gorus_op": notlar["gorus_op"],
        "trend": notlar["trend"], "sis_riski": notlar["sis"],
        "ozet": ozet_satiri(cozum),
    }


def panel_verisi_yaz(raporlar: list, gecmis: list, hedef: Path):
    metar = next((r for r in raporlar if r["tip"] in ("METAR", "SPECI")), None)
    taf = next((r for r in raporlar if r["tip"] == "TAF"), None)
    simdi = datetime.now(timezone.utc)

    veri = {
        "istasyon": (raporlar[0].get("icao") if raporlar else None) or "LTFJ",
        "uretildi": simdi.isoformat(timespec="seconds"),
        "metar": _metar_json(metar) if metar else None,
        "taf": ({
            "zaman": taf["zaman"].isoformat(timespec="seconds") if taf.get("zaman") else None,
            "metin": taf["metin"],
        } if taf else None),
        "gecmis": gecmis,
    }

    hedef.write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  panel verisi yazıldı: {hedef.name}")
