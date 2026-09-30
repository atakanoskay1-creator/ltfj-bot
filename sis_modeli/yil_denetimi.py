#!/usr/bin/env python3
"""2011'de olay baslangici neden yalnizca 2? Salt okuma denetimi.

veri/ltfj_ozellik.csv.gz arsivini yil yil tarar ve veri kalitesi
kusurlarini (eksik satir, etiket/etiket-kodu uyumsuzlugu, gorus tavan
degeri, hava kodu eksikligi) tablo halinde basar. Model egitmez, dosya
yazmaz; yalnizca okur ve basar.

Kullanim (repo kokunden):
    python sis_modeli/yil_denetimi.py
"""

import csv
import gzip

VERI = "sis_modeli/veri/ltfj_ozellik.csv.gz"
YILLAR = range(2010, 2025)


def sayi_metin(metin):
    """Metni sayiya cevirir; bos ya da gecersiz deger icin None dondurur."""
    if metin is None:
        return None
    metin = metin.strip()
    if not metin:
        return None
    try:
        return int(metin)
    except ValueError:
        try:
            return float(metin)
        except ValueError:
            return None


def yuzde(kismi, tam):
    return 100.0 * kismi / tam if tam else 0.0


def ana():
    yil = {
        y: {
            "satir": 0, "sis1": 0, "sis_kodu1": 0,
            "g_1000": 0, "g_5000": 0, "g_9999": 0,
            "hava_dolu": 0, "fg": 0, "br": 0,
            "min_gorus": None,
        }
        for y in YILLAR
    }

    with gzip.open(VERI, "rt", encoding="utf-8", newline="") as dosya:
        for satir in csv.DictReader(dosya):
            y = int(satir["zaman"][:4])
            if y not in yil:
                continue
            s = yil[y]
            s["satir"] += 1
            if satir["sis"].strip() == "1":
                s["sis1"] += 1
            if satir["sis_kodu"].strip() == "1":
                s["sis_kodu1"] += 1
            g = sayi_metin(satir["gorus"])
            if g is not None:
                if g < 1000:
                    s["g_1000"] += 1
                if g < 5000:
                    s["g_5000"] += 1
                if g >= 9999:
                    s["g_9999"] += 1
                if s["min_gorus"] is None or g < s["min_gorus"]:
                    s["min_gorus"] = g
            hava = (satir["hava"] or "").strip()
            if hava:
                s["hava_dolu"] += 1
                if "FG" in hava.split():
                    s["fg"] += 1
                if "BR" in hava.split():
                    s["br"] += 1

    baslik = [
        "yil", "satir", "sis1", "sis_kodu1", "g_1000", "g_5000",
        "g_9999_%", "hava_dolu_%", "FG", "BR", "min_gorus",
    ]
    satirlar = []
    for y in YILLAR:
        s = yil[y]
        satirlar.append([
            y, s["satir"], s["sis1"], s["sis_kodu1"], s["g_1000"], s["g_5000"],
            "%.1f" % yuzde(s["g_9999"], s["satir"]),
            "%.1f" % yuzde(s["hava_dolu"], s["satir"]),
            s["fg"], s["br"], s["min_gorus"],
        ])

    genislikler = [
        max(len(str(satir[i])) for satir in [baslik] + satirlar)
        for i in range(len(baslik))
    ]
    for satir in [baslik] + satirlar:
        print("  ".join(
            str(h).rjust(genislikler[i]) for i, h in enumerate(satir)
        ))


if __name__ == "__main__":
    ana()
