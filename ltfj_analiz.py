#!/usr/bin/env python3
"""
METAR/SPECI cozumleme, iki rapor arasi fark bulma ve esik uyarilari.

Ham bulten -> sozluk -> (a) onceki raporla fark  (b) dikkat gerektiren durumlar
Harici kutuphane yok.
"""

import math
import re

from ltfj_ayarlar import esik

# LTFJ pist ekseni, GERCEK yon (AIP AD 2.12: 06L/06R 064.10°, 24R/24L 244.12°).
# Yan ruzgar buyuklugu iki yon icin de ayni oldugundan tek deger yetiyor.
# Pist basi bazinda ayrintili tablo ltfj_pist.PISTLER icinde.
PIST_YONU = 64.10

# --- esikler ---------------------------------------------------------------
GORUS_DUSUK = esik("gorus_dusuk")            # metre
GORUS_COK_DUSUK = esik("gorus_cok_dusuk")    # metre
TAVAN_DUSUK = esik("tavan_dusuk")            # ft
TAVAN_COK_DUSUK = esik("tavan_cok_dusuk")    # ft
RUZGAR_KUVVETLI = esik("ruzgar_kuvvetli")    # kt
HAMLE_KUVVETLI = esik("hamle_kuvvetli")      # kt
YAN_RUZGAR_YUKSEK = esik("yan_ruzgar_dikkat")  # kt

# --- desenler --------------------------------------------------------------
RE_RUZGAR = re.compile(r"^(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?(KT|MPS)$")
RE_DEGISKEN = re.compile(r"^(\d{3})V(\d{3})$")
RE_GORUS = re.compile(r"^(\d{4})$")
RE_BULUT = re.compile(r"^(FEW|SCT|BKN|OVC|VV)(\d{3}|///)(CB|TCU)?$")
RE_SICAKLIK = re.compile(r"^(M?\d{2})/(M?\d{2})$")
RE_BASINC = re.compile(r"^([QA])(\d{4})$")

# Hava olayi kodlari (WMO 4678)
SIDDET = {"-": "hafif ", "+": "kuvvetli ", "VC": "civarda "}
TANIMLAYICI = {
    "MI": "alçak ", "BC": "parça parça ", "PR": "kısmi ", "DR": "savrulan ",
    "BL": "sürüklenen ", "SH": "sağanak ", "TS": "gök gürültülü ", "FZ": "donan ",
}
OLAY = {
    "DZ": "çiseleme", "RA": "yağmur", "SN": "kar", "SG": "kar tanesi",
    "IC": "buz kristali", "PL": "buz yağmuru", "GR": "dolu", "GS": "ufak dolu",
    "UP": "bilinmeyen yağış", "BR": "puslu", "FG": "sis", "FU": "duman",
    "VA": "volkanik kül", "DU": "toz", "SA": "kum", "HZ": "is",
    "PY": "serpinti", "SQ": "ani fırtına", "PO": "toz hortumu",
    "FC": "hortum", "SS": "kum fırtınası", "DS": "toz fırtınası",
}
RE_HAVA = re.compile(
    r"^(-|\+|VC)?((?:MI|BC|PR|DR|BL|SH|TS|FZ)*)((?:DZ|RA|SN|SG|IC|PL|GR|GS|UP|"
    r"BR|FG|FU|VA|DU|SA|HZ|PY|SQ|PO|FC|SS|DS)+)$"
)

TAVAN_KATMANLARI = ("BKN", "OVC", "VV")


def _hava_turkce(token: str) -> str:
    m = RE_HAVA.match(token)
    if not m:
        return token
    siddet, tanim, olaylar = m.groups()
    metin = SIDDET.get(siddet or "", "")
    for i in range(0, len(tanim), 2):
        metin += TANIMLAYICI.get(tanim[i:i + 2], "")
    parcalar = [OLAY.get(olaylar[i:i + 2], olaylar[i:i + 2])
                for i in range(0, len(olaylar), 2)]
    return (metin + " ".join(parcalar)).strip()


def metar_coz(metin: str) -> dict:
    """Ham METAR/SPECI metnini sozluge cevirir. Anlasilmayan alan None kalir."""
    tokenlar = metin.split()
    if "RMK" in tokenlar:                       # RMK sonrasi bize lazim degil
        tokenlar = tokenlar[:tokenlar.index("RMK")]

    nosig = "NOSIG" in tokenlar
    # Egilim grubu (TEMPO/BECMG) GELECEGI anlatir - mevcut durumla karistirmayalim.
    # Ornek: "... BKN003 TEMPO 0400 +TSRA" -> +TSRA su an degil, beklenen.
    for isaret in ("NOSIG", "BECMG", "TEMPO"):
        if isaret in tokenlar:
            tokenlar = tokenlar[:tokenlar.index(isaret)]

    d = {
        "ruzgar_yon": None, "ruzgar_hiz": None, "ruzgar_hamle": None,
        "degisken": None, "gorus": None, "cavok": False,
        "bulutlar": [], "tavan": None, "hava": [],
        "sicaklik": None, "cig_noktasi": None, "qnh": None,
        "nosig": nosig,
    }

    for t in tokenlar:
        if t == "CAVOK":
            d["cavok"] = True
            d["gorus"] = 10000
            continue

        m = RE_RUZGAR.match(t)
        if m and d["ruzgar_hiz"] is None:
            yon, hiz, hamle, birim = m.groups()
            carpan = 1.94384 if birim == "MPS" else 1.0     # m/s -> kt
            d["ruzgar_yon"] = None if yon == "VRB" else int(yon)
            d["ruzgar_hiz"] = round(int(hiz) * carpan)
            d["ruzgar_hamle"] = round(int(hamle) * carpan) if hamle else None
            continue

        m = RE_DEGISKEN.match(t)
        if m:
            d["degisken"] = (int(m.group(1)), int(m.group(2)))
            continue

        m = RE_GORUS.match(t)
        if m and d["gorus"] is None:
            d["gorus"] = int(m.group(1))
            continue

        m = RE_BULUT.match(t)
        if m:
            ortu, taban, tur = m.groups()
            ft = None if taban == "///" else int(taban) * 100
            d["bulutlar"].append({"ortu": ortu, "ft": ft, "tur": tur})
            if ortu in TAVAN_KATMANLARI and ft is not None:
                d["tavan"] = ft if d["tavan"] is None else min(d["tavan"], ft)
            continue

        if t in ("NSC", "NCD", "SKC", "CLR"):
            continue

        m = RE_SICAKLIK.match(t)
        if m:
            d["sicaklik"] = int(m.group(1).replace("M", "-"))
            d["cig_noktasi"] = int(m.group(2).replace("M", "-"))
            continue

        m = RE_BASINC.match(t)
        if m:
            tip, deger = m.groups()
            d["qnh"] = int(deger) if tip == "Q" else round(int(deger) / 100 * 33.8639)
            continue

        if RE_HAVA.match(t) and t not in ("NOSIG",):
            d["hava"].append(t)

    return d


def yan_ruzgar(yon, hiz, pist=PIST_YONU):
    """Pist eksenine dik ruzgar bileseni (kt). Yon yoksa None."""
    if yon is None or hiz is None:
        return None
    return abs(hiz * math.sin(math.radians(yon - pist)))


# --------------------------------------------------------------- uyarilar ---
def uyarilar(d: dict) -> list[str]:
    """Dikkat cekmesi gereken durumlar. Bos liste = sikinti yok."""
    u = []
    hava_metni = " ".join(d["hava"])

    if "TS" in hava_metni:
        u.append("Gök gürültülü fırtına")
    if "FZ" in hava_metni:
        u.append("Donan yağış — buzlanma")
    if "FC" in hava_metni:
        u.append("Hortum bildirildi")
    if re.search(r"\bGR\b|GR$", hava_metni):
        u.append("Dolu")
    if "SN" in hava_metni or "SG" in hava_metni:
        u.append("Kar yağışı")

    g = d["gorus"]
    if g is not None:
        if g < GORUS_COK_DUSUK:
            u.append(f"Görüş çok düşük: {g} m")
        elif g < GORUS_DUSUK:
            u.append(f"Görüş düşük: {g} m")

    t = d["tavan"]
    if t is not None:
        if t < TAVAN_COK_DUSUK:
            u.append(f"Tavan çok alçak: {t} ft")
        elif t < TAVAN_DUSUK:
            u.append(f"Tavan alçak: {t} ft")

    hiz, hamle = d["ruzgar_hiz"], d["ruzgar_hamle"]
    if hamle and hamle >= HAMLE_KUVVETLI:
        u.append(f"Kuvvetli hamle: {hamle} kt")
    elif hiz and hiz >= RUZGAR_KUVVETLI:
        u.append(f"Kuvvetli rüzgâr: {hiz} kt")

    yr = yan_ruzgar(d["ruzgar_yon"], max(hiz or 0, d["ruzgar_hamle"] or 0))
    if yr is not None and yr >= YAN_RUZGAR_YUKSEK:
        u.append(f"Yan rüzgâr ~{yr:.0f} kt (06/24)")

    return u


# ------------------------------------------------------------------ fark ---
def _ruzgar_yazi(d):
    if d["ruzgar_hiz"] is None:
        return "?"
    yon = f'{d["ruzgar_yon"]:03d}°' if d["ruzgar_yon"] is not None else "değişken"
    s = f'{yon} {d["ruzgar_hiz"]}kt'
    if d["ruzgar_hamle"]:
        s += f' (hamle {d["ruzgar_hamle"]})'
    return s


def _gorus_yazi(d):
    if d["cavok"]:
        return "CAVOK"
    if d["gorus"] is None:
        return "?"
    return "10+ km" if d["gorus"] >= 9999 else f'{d["gorus"]} m'


def _tavan_yazi(d):
    return "yok" if d["tavan"] is None else f'{d["tavan"]} ft'


def _hava_yazi(d):
    return ", ".join(_hava_turkce(t) for t in d["hava"]) if d["hava"] else "yok"


def fark_bul(onceki: str, simdiki: str) -> list[str]:
    """Iki METAR arasinda anlamli degisiklikler. Bos liste = kayda deger fark yok."""
    if not onceki:
        return []
    a, b = metar_coz(onceki), metar_coz(simdiki)
    farklar = []

    # Ruzgar: yonde 30 dereceden fazla veya hizda 5 kt'dan fazla oynama
    yon_fark = (a["ruzgar_yon"] is not None and b["ruzgar_yon"] is not None
                and abs((b["ruzgar_yon"] - a["ruzgar_yon"] + 180) % 360 - 180) >= 30)
    hiz_fark = (a["ruzgar_hiz"] is not None and b["ruzgar_hiz"] is not None
                and abs(b["ruzgar_hiz"] - a["ruzgar_hiz"]) >= 5)
    hamle_fark = bool(a["ruzgar_hamle"]) != bool(b["ruzgar_hamle"])
    if yon_fark or hiz_fark or hamle_fark:
        farklar.append(f"Rüzgâr: {_ruzgar_yazi(a)} → {_ruzgar_yazi(b)}")

    # Gorus: bir esigi gectiyse ya da %30'dan fazla degistiyse
    ga, gb = a["gorus"], b["gorus"]
    if ga is not None and gb is not None and ga != gb:
        esik_atladi = any((ga < e) != (gb < e) for e in (800, 1500, 3000, 5000))
        if esik_atladi or abs(gb - ga) / max(ga, 1) > 0.3:
            farklar.append(f"Görüş: {_gorus_yazi(a)} → {_gorus_yazi(b)}")

    # Tavan: varligi degistiyse ya da 500 ft'den fazla oynadiysa
    ta, tb = a["tavan"], b["tavan"]
    if (ta is None) != (tb is None) or (ta and tb and abs(tb - ta) >= 500):
        farklar.append(f"Tavan: {_tavan_yazi(a)} → {_tavan_yazi(b)}")

    # Hava olayi: yeni basladi / bitti / degisti
    if set(a["hava"]) != set(b["hava"]):
        farklar.append(f"Hava: {_hava_yazi(a)} → {_hava_yazi(b)}")

    # QNH: 2 hPa ve uzeri
    if a["qnh"] and b["qnh"] and abs(b["qnh"] - a["qnh"]) >= 2:
        farklar.append(f'QNH: {a["qnh"]} → {b["qnh"]} hPa')

    return farklar


def cozum_dokumu(d: dict) -> str:
    """Cozumlenmis METAR'i satir satir yazar. Claude'a ham bulten yerine bunu
    veriyoruz - kendi ayikladigi seyi yanlis okuyamasin diye."""
    s = [f"Rüzgâr: {_ruzgar_yazi(d)}"]
    if d["degisken"]:
        s.append(f'  yön {d["degisken"][0]}° ile {d["degisken"][1]}° arasında oynuyor')
    yr = yan_ruzgar(d["ruzgar_yon"], max(d["ruzgar_hiz"] or 0, d["ruzgar_hamle"] or 0))
    if yr is not None:
        s.append(f"  06/24 pistine göre yan rüzgâr bileşeni: {yr:.0f} kt")

    s.append(f"Görüş: {_gorus_yazi(d)}")
    s.append(f"Hava olayı: {_hava_yazi(d)}")

    if d["bulutlar"]:
        katmanlar = []
        ad = {"FEW": "az bulutlu (1-2/8)", "SCT": "parçalı (3-4/8)",
              "BKN": "çok bulutlu (5-7/8)", "OVC": "kapalı (8/8)",
              "VV": "dikey görüş"}
        for b in d["bulutlar"]:
            ft = f'{b["ft"]} ft' if b["ft"] is not None else "? ft"
            tur = {"CB": " (kümülonimbus — fırtına bulutu)",
                   "TCU": " (gelişen kule bulut)"}.get(b["tur"] or "", "")
            katmanlar.append(f'{ad.get(b["ortu"], b["ortu"])} {ft}{tur}')
        s.append("Bulutlar: " + "; ".join(katmanlar))
        if d["tavan"]:
            s.append(f'  Tavan (ilk 5/8+ katman): {d["tavan"]} ft')
    else:
        s.append("Bulutlar: bildirilmemiş")

    if d["sicaklik"] is not None:
        nem_farki = d["sicaklik"] - d["cig_noktasi"]
        s.append(f'Sıcaklık: {d["sicaklik"]}°C, çiğ noktası {d["cig_noktasi"]}°C '
                 f'(aralık {nem_farki}°C{", nem çok yüksek" if nem_farki <= 2 else ""})')
    if d["qnh"]:
        s.append(f'QNH: {d["qnh"]} hPa')
    if d["nosig"]:
        s.append("Eğilim: NOSIG — önümüzdeki 2 saatte önemli değişiklik beklenmiyor")

    return "\n".join(s)


def ozet_satiri(d: dict) -> str:
    """Tek satirlik durum ozeti - Claude yorumu kapaliyken de bir seyler yazsin."""
    p = [f'Rüzgâr {_ruzgar_yazi(d)}', f'görüş {_gorus_yazi(d)}']
    if d["tavan"]:
        p.append(f'tavan {d["tavan"]} ft')
    if d["hava"]:
        p.append(_hava_yazi(d))
    if d["sicaklik"] is not None:
        p.append(f'{d["sicaklik"]}°C')
    if d["qnh"]:
        p.append(f'QNH {d["qnh"]}')
    return " · ".join(p)
