#!/usr/bin/env python3
"""Tarihsel LTFJ METAR satirlarindan sis/dusuk gorus modeli icin OZELLIK cikarir.

Bu modul sis_modeli/ alt projesinin parcasidir; CALISMA ANINDAKI BOT bunu
IMPORT ETMEZ (bkz. sis_modeli/README.md - izolasyon sozlesmesi). METAR
ayristirmasi icin projenin zaten test edilmis ayristiricisi
(ltfj_analiz.metar_coz) YENIDEN KULLANILIR - ikinci bir ayristirici yazilmaz.

metar_coz() BECMG/TEMPO/NOSIG sonrasini atar; tarihsel GOZLEM analizinde
istedigimiz de tam olarak budur (o gruplar egilim tahminidir, gozlem degil).
"""

from datetime import datetime

from ltfj_analiz import RE_HAVA, metar_coz

# Etiket esikleri. LVO degeri projenin kendi LVO referansiyla (TL.007 madde
# 6.1.ee, "550 M RVR altinda LVO inis operasyonlari safhasi") ayni sayidir -
# burada RVR degil GORUS olcusuyle, cunku tarihsel arsivde surekli RVR yok.
SIS_GORUS_M = 1000        # ICAO: sis = gorus < 1000 m
LVO_GORUS_M = 550

# CSV sutun sirasi - veri_cek.py ve istatistik.py bu listeyi kullanir.
SUTUNLAR = (
    "zaman", "ay", "saat", "sicaklik", "cig_noktasi", "spread",
    "ruzgar_hiz", "ruzgar_yon", "gorus", "tavan", "qnh", "hava", "sis_kodu",
    "sis", "lvo",
)


# FG'yi ALANI KAPLAYAN sis olmaktan cikaran tanimlayicilar:
#   MI (alcak)      - sis tabakasi goz seviyesinin altinda, gorus >= 1000 m
#   BC (parca parca)- meydanin bazi yerlerinde, istasyon gorusu yuksek kalabilir
#   PR (kismi)      - meydanin bir bolumunu kapliyor
# VC (civarda) ise siddet alanindan gelir ve zaten alanda degil demektir.
#
# BC/PR'nin disarida birakilmasi gercek arsiv verisiyle DOGRULANDI: bunlar
# dahilken yaz aylarindaki "FG" kayitlarinin medyan gorusu 2500 m cikiyordu
# (haziranda %33'u 5000 m ustu) - yani sis olmayan kayitlar etiketleniyordu.
SIS_DISI_TANIMLAYICILAR = ("MI", "BC", "PR")


def _sis_kodu_var(hava: list) -> bool:
    """Hava kodlarinda ALANI KAPLAYAN sis var mi?"""
    for token in hava:
        m = RE_HAVA.match(token)
        if not m:
            continue
        siddet, tanimlayici, olay = m.groups()
        if "FG" not in olay:
            continue
        if siddet == "VC":
            continue
        if any(t in (tanimlayici or "") for t in SIS_DISI_TANIMLAYICILAR):
            continue
        return True
    return False


def atlama_nedeni(metin: str) -> str | None:
    """Satir neden kullanilamiyor? Kullanilabiliyorsa None doner.

    Ayri bir fonksiyon, cunku "53.145 satir atlandi" gibi OPAK bir sayi
    veri kalitesi sorununu gizler - nedeni bilmek arsivin kendisinde mi
    yoksa ayristiricida mi sorun oldugunu soyler."""
    d = metar_coz(metin)
    if d["sicaklik"] is None or d["cig_noktasi"] is None:
        return "sicaklik/cig yok"
    if d["gorus"] is None:
        return "gorus yok"
    return None


def ozellik_cikar(metin: str, zaman: datetime) -> dict | None:
    """Bir METAR metnini + gozlem zamanini ozellik sozlugune cevirir.

    zaman ayri parametre: METAR metni sadece gun/saat/dakika tasir (DDHHMMZ),
    ay/yil bilgisi arsiv kaydinin kendisinden gelir.

    Sicaklik, cig noktasi veya gorus okunamayan satirlar icin None doner -
    bunlar olmadan ne ozellik (spread) ne de etiket uretilebilir.
    """
    d = metar_coz(metin)
    sicaklik, cig, gorus = d["sicaklik"], d["cig_noktasi"], d["gorus"]
    if sicaklik is None or cig is None or gorus is None:
        return None

    sis_kodu = _sis_kodu_var(d["hava"])
    return {
        "zaman": zaman.strftime("%Y-%m-%dT%H:%M"),
        "ay": zaman.month,
        "saat": zaman.hour,
        "sicaklik": sicaklik,
        "cig_noktasi": cig,
        "spread": sicaklik - cig,
        "ruzgar_hiz": d["ruzgar_hiz"],
        "ruzgar_yon": d["ruzgar_yon"],
        "gorus": gorus,
        "tavan": d["tavan"],
        "qnh": d["qnh"],
        # Ham hava kodlari da saklanir: etiket TANIMI ileride degisirse
        # (ornegin BC/PR disarida birakma karari) 20 yillik arsivi yeniden
        # indirmeden yeni etiket turetilebilsin.
        "hava": " ".join(d["hava"]),
        "sis_kodu": int(sis_kodu),
        # Etiketler: gorus esigi VEYA alanda sis kodu. Gorus tek basina
        # yetmez cunku CAVOK disi bazi raporlarda sis kodu varken gorus
        # yuvarlanmis olabilir; sis kodu tek basina da yetmez cunku bazi
        # istasyonlar kodu atlayip sadece gorusu dusurur.
        "sis": int(gorus < SIS_GORUS_M or sis_kodu),
        "lvo": int(gorus < LVO_GORUS_M),
    }
