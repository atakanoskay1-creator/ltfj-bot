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
    bilesenler,
    havacilik_notlari,
    kuyruk_limiti,
    pist_ruzgar_kaynagi,
)


def _pist_verisi(cozum: dict, metin: str) -> dict:
    """Pist basi ruzgar bilesenlerini SAYISAL olarak dondurur (panel.html
    kendi SVG okunu ve etiketlerini bunlardan cizer - onceden bicimlenmis
    metin degil).

    pist_ruzgar_kaynagi() ile AYNI ortak per-pist kaynak modelini kullanir.
    Onceden bu fonksiyon kendi kopyasini (RMK varsa TUM pistleri RMK'dan,
    yoksa hepsini alan ruzgarindan) tutuyordu - RMK KISMEN raporlandiginda
    (F2 sinifinda bir hata) ATC panelinde de pistler sessizce kayboluyordu,
    Telegram tarafinda F2 duzeltmesi bu dosyaya hic yansimamisti."""
    kaynaklar = pist_ruzgar_kaynagi(cozum, metin)
    limit, limit_gerekce = kuyruk_limiti(cozum)

    pistler = []
    for k in kaynaklar:
        pist, yon = k["pist"], k["yon"]
        yonu = PISTLER.get(pist, {}).get("yon")
        if yonu is None or yon is None:
            continue
        hiz_sabit, hiz_hamle = k["hiz_sabit"], k["hiz_hamle"]
        bas, yan, taraf = bilesenler(yon, hiz_sabit, yonu)
        if bas is None:
            continue
        hamleli = hiz_hamle is not None and hiz_hamle > (hiz_sabit or 0)
        bas_g = yan_g = None
        if hamleli:
            bas_g, yan_g, _ = bilesenler(yon, hiz_hamle, yonu)
        bas_worst = bas_g if bas_g is not None else bas

        pistler.append({
            "pist": pist,
            "yon_gercek": yonu,
            "bas": round(bas, 1),
            "yan": round(yan, 1),
            "yan_taraf": taraf,
            "bas_hamle": round(bas_g, 1) if bas_g is not None else None,
            "yan_hamle": round(yan_g, 1) if yan_g is not None else None,
            "degisken": bool(k["degisken"]),
            "kaynak": k["kaynak"],
            "kuyruk": bas < 0,
            "kuyruk_asildi": bool(bas_worst < 0 and abs(bas_worst) > limit),
        })

    return {
        "pistler": sorted(pistler, key=lambda p: p["pist"]),
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
