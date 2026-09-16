#!/usr/bin/env python3
"""
Pist bazli ruzgar bilesenleri, RVR / WS / RE gruplari, renk durumu, sis riski,
tercihli pist sistemi (PRS) ve dusuk gorus kalkis (LVTO) kontrolu.

Sabitler LTFJ AIP AD 2'den alinmistir (AIRAC AMDT 07/26):
  AD 2.2   Yukseklik 312 FT, referans sicaklik 28°C, MAG VAR 6.1°E (2025)
  AD 2.11  Inis tahmini TREND, yayin araligi 1/2 saat
  AD 2.12  Pist GERCEK yonleri: 06L/06R 064.10°, 24R/24L 244.12°
  AD 2.13  Deklare mesafeler (LDA)
  AD 2.15  Anemometreler THR'den 220 M mesafede - RMK'daki pist ruzgarlari bunlardan
  AD 2.19  ILS kategorileri: 06R CAT II, digerleri CAT I
  AD 2.20K Tercihli pist sistemi ve arka ruzgar limitleri
  AD 2.20S LVTO: RVR 400 M altinda yururluge girer, sadece 06R

ONEMLI: METAR ruzgari GERCEK kuzeye gore verilir; pist NUMARASI manyetiktir.
(06 numarasi = 064.10° gercek - 6.1° sapma = 058° manyetik.) Bilesen hesabinda
gercek yonu kullaniyoruz - aksi halde 6 derecelik sistematik hata olusur.
"""

import math
import re
from datetime import datetime, timedelta, timezone

from ltfj_ayarlar import PIST_EKSENI_06, PIST_EKSENI_24
from ltfj_ayarlar import esik as _esik

# --- LTFJ sabitleri (AIP AD 2) ---------------------------------------------
# Yon degerleri ltfj_ayarlar.PIST_EKSENI_06/24'ten geliyor (ltfj_analiz.py
# ile TEK ortak kaynak - bkz. oradaki PIST_YONU aciklamasi).
PISTLER = {
    "06L": {"yon": PIST_EKSENI_06, "lda": 2910, "ils": "CAT I"},
    "24R": {"yon": PIST_EKSENI_24, "lda": 3000, "ils": "CAT I"},
    "06R": {"yon": PIST_EKSENI_06, "lda": 3540, "ils": "CAT II"},
    "24L": {"yon": PIST_EKSENI_24, "lda": 3540, "ils": "CAT I"},
}
TERCIHLI_PISTLER = ("06L", "24R", "06R", "24L")     # AD 2.20 K

ENLEM, BOYLAM = 40.8983, 29.3092      # ARP 405354N 0291833E
YUKSEKLIK_FT = 312                    # AD 2.2
MAG_VAR = 6.1                         # °E, 2025

# AD 2.20 K - tercihli pist sisteminde azami arka ruzgar bileseni
KUYRUK_LIMIT_KURU = 10                # RWYCC 6/6/6
KUYRUK_LIMIT_ISLAK = 5                # herhangi bir ucte RWYCC <= 5
YAN_RUZGAR_DIKKAT = _esik("yan_ruzgar_dikkat")  # dikkat esigi, operasyonel sinir degil

LVTO_RVR = 400                        # AD 2.20 S - metre
CAT1_TIPIK_RVR = 550                  # Tipik CAT I degeri; kesin minimum yaklasma
                                      # kartindadir, AIP AD 2 metninde yok.

# Pist yuzeyini islak sayacagimiz hava olaylari
ISLAK_YAPAN = ("RA", "SN", "DZ", "SG", "PL", "GR", "GS", "UP")

# --- desenler --------------------------------------------------------------
RE_PIST_RUZGAR = re.compile(
    r"RWY(\d{2}[LCR]?)\s+(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?(KT|MPS)"
    r"(?:\s+(\d{3})V(\d{3}))?"
)
RE_RVR = re.compile(
    r"\bR(\d{2}[LCR]?)/([PM]?)(\d{4})(?:V([PM]?)(\d{4}))?([UDN])?\b"
)
RE_WS = re.compile(r"\bWS\s+(ALL\s+RWY|RWY\d{2}[LCR]?)")
RE_SON_HAVA = re.compile(r"\bRE([A-Z]{2,6})\b")
RE_TREND = re.compile(r"\b(BECMG|TEMPO)\b(.*)$")

RVR_EGILIM = {"U": "yükseliyor", "D": "düşüyor", "N": "sabit"}


# ------------------------------------------------------- pist ruzgarlari ---
def pist_ruzgarlari(metin: str) -> list[dict]:
    """RMK bolumundeki pist basi ruzgarlarini ayiklar (AD 2.15: THR'den 220 M)."""
    if "RMK" not in metin:
        return []
    out = []
    for m in RE_PIST_RUZGAR.finditer(metin[metin.index("RMK"):]):
        pist, yon, hiz, hamle, birim, v1, v2 = m.groups()
        carpan = 1.94384 if birim == "MPS" else 1.0
        out.append({
            "pist": pist,
            "yon": None if yon == "VRB" else int(yon),
            "hiz": round(int(hiz) * carpan),
            "hamle": round(int(hamle) * carpan) if hamle else None,
            "degisken": (int(v1), int(v2)) if v1 else None,
        })
    return out


def bilesenler(yon, hiz, pist_yonu):
    """(bas_ruzgari, yan_ruzgar, yan_taraf). bas_ruzgari negatifse kuyruk ruzgaridir."""
    if yon is None or hiz is None:
        return None, None, None
    aci = math.radians(yon - pist_yonu)
    return hiz * math.cos(aci), abs(hiz * math.sin(aci)), \
        ("sağdan" if math.sin(aci) >= 0 else "soldan")


def _pist_yonu(pist: str) -> float | None:
    if pist in PISTLER:
        return PISTLER[pist]["yon"]
    # Bilinmeyen pist: numarasi manyetik kabul edilir, gercek yone cevrilir
    try:
        return (int(pist[:2]) * 10 + MAG_VAR) % 360
    except ValueError:
        return None


def kuyruk_limiti(cozum: dict) -> tuple[int, str]:
    """AD 2.20 K: kuru pistte 10 kt, RWYCC dusukse 5 kt.
    RWYCC METAR'da yok - yagis varsa pisti islak kabul ediyoruz."""
    hava = " ".join(cozum.get("hava") or [])
    islak = any(k in hava for k in ISLAK_YAPAN)
    return ((KUYRUK_LIMIT_ISLAK, "ıslak/kirli pist varsayımı") if islak
            else (KUYRUK_LIMIT_KURU, "kuru pist"))


def _pist_ruzgar_kaynagi(cozum: dict, metin: str) -> list[dict]:
    """Her pist basi icin ayri ayri ruzgar kaynagi secer: RMK'da o pist icin
    olculen anemometre verisi (AD 2.15) varsa onu, yoksa o pist icin tek
    tek alan METAR ruzgarina duser. Hiz her zaman max(sabit, hamle) -
    PRS/kuyruk-limiti karsilastirmalari en kotu (hamleli) durumu esas alir.

    ONEMLI (F2 duzeltmesi): RMK KISMEN raporlandiginda (ornegin sadece
    RWY06R ve RWY24L bildirilmis) onceki surum RMK'da GECMEYEN pistleri
    (06L, 24R) tamamen atliyordu - sanki o pistler icin veri yokmus gibi.
    Artik her pist BAGIMSIZ olarak degerlendiriliyor: RMK'da varsa
    anemometre, yoksa alan METAR ruzgarina duser. Boylece hicbir pist
    sessizce kayip gitmez.

    NOT: tercih_edilen_pist() KASITLI olarak farkli bir mantik kullanir
    (hamlesiz sabit ruzgar, eksik veride None'u oldugu gibi birakir) - bu
    yardimciyi kullanmiyor, davranisini degistirmemek icin ayri birakildi."""
    olculenler = {o["pist"]: o for o in pist_ruzgarlari(metin)}
    alan_hiz = max(cozum["ruzgar_hiz"] or 0, cozum["ruzgar_hamle"] or 0)
    alan_yon = cozum["ruzgar_yon"]

    kaynaklar = []
    for pist in TERCIHLI_PISTLER:
        o = olculenler.get(pist)
        if o:
            kaynaklar.append({
                "pist": pist, "yon": o["yon"],
                "hiz": max(o["hiz"] or 0, o["hamle"] or 0),
                "kaynak": "AD 2.15 anemometreleri",
            })
        else:
            kaynaklar.append({
                "pist": pist, "yon": alan_yon, "hiz": alan_hiz,
                "kaynak": "alan rüzgârından",
            })
    return kaynaklar


def pist_raporu(cozum: dict, metin: str) -> list[str]:
    """Her pist basi icin okunakli bilesen satiri."""
    kaynaklar = _pist_ruzgar_kaynagi(cozum, metin)
    limit, limit_gerekce = kuyruk_limiti(cozum)

    satirlar = []
    kaynak_gruplari: dict[str, list[str]] = {}
    for k in sorted(kaynaklar, key=lambda k: k["pist"]):
        pist, yon, hiz = k["pist"], k["yon"], k["hiz"]
        yonu = _pist_yonu(pist)
        if yonu is None:
            continue
        kaynak_gruplari.setdefault(k["kaynak"], []).append(pist)

        bas, yan, taraf = bilesenler(yon, hiz, yonu)
        if bas is None:
            satirlar.append(f"{pist}: rüzgâr değişken, bileşen hesaplanamıyor")
            continue

        if bas >= 0:
            uzun = f"baş {bas:.0f} kt"
        else:
            uzun = f"KUYRUK {abs(bas):.0f} kt"
            if abs(bas) > limit:
                uzun += f" (PRS limiti {limit} kt aşıldı)"

        yanlama = f"yan {yan:.0f} kt {taraf}"
        if yan >= YAN_RUZGAR_DIKKAT:
            yanlama += " (yüksek)"

        satirlar.append(f"{pist}: {uzun}, {yanlama}")

    if satirlar:
        if len(kaynak_gruplari) == 1:
            etiket = next(iter(kaynak_gruplari))
        else:
            etiket = "; ".join(
                f"{', '.join(pistler)}: {kaynak}"
                for kaynak, pistler in kaynak_gruplari.items()
            )
        satirlar.append(f"({etiket}; kuyruk limiti {limit} kt — {limit_gerekce})")
    return satirlar


def tercih_edilen_pist(cozum: dict, metin: str) -> str | None:
    """En cok bas ruzgari alan pist basi."""
    olculenler = pist_ruzgarlari(metin)
    adaylar = ([(o["pist"], o["yon"], o["hiz"]) for o in olculenler] or
               [(p, cozum["ruzgar_yon"], cozum["ruzgar_hiz"]) for p in TERCIHLI_PISTLER])

    en_iyi, en_iyi_bas = None, None
    for pist, yon, hiz in adaylar:
        yonu = _pist_yonu(pist)
        if yonu is None:
            continue
        bas, _, _ = bilesenler(yon, hiz, yonu)
        if bas is not None and (en_iyi_bas is None or bas > en_iyi_bas):
            en_iyi, en_iyi_bas = pist, bas
    return en_iyi


def kuyruk_asanlar(cozum: dict, metin: str) -> list[str]:
    """PRS arka ruzgar limitini asan pist baslari."""
    limit, _ = kuyruk_limiti(cozum)
    adaylar = _pist_ruzgar_kaynagi(cozum, metin)

    asanlar = []
    for k in adaylar:
        pist, yon, hiz = k["pist"], k["yon"], k["hiz"]
        yonu = _pist_yonu(pist)
        if yonu is None:
            continue
        bas, _, _ = bilesenler(yon, hiz, yonu)
        if bas is not None and bas < 0 and abs(bas) > limit:
            asanlar.append(pist)
    return sorted(asanlar)


# -------------------------------------------------------- RVR / WS / RE ---
def rvr_kayitlari(metin: str) -> list[dict]:
    govde = metin.split("RMK")[0]
    out = []
    for m in RE_RVR.finditer(govde):
        pist, on_ek, deger, v_ek, v_deger, egilim = m.groups()
        out.append({
            "pist": pist,
            "deger": int(deger),
            "on_ek": on_ek or "",
            "ust": int(v_deger) if v_deger else None,
            "ust_on_ek": v_ek or "",
            "egilim": egilim,
        })
    return out


_RVR_ONEK_METNI = {"P": "en az ", "M": "en fazla "}


def rvr_gruplari(metin: str) -> list[str]:
    out = []
    for r in rvr_kayitlari(metin):
        s = f'{r["pist"]}: '
        s += _RVR_ONEK_METNI.get(r["on_ek"], "")
        s += f'{r["deger"]} m'
        if r["ust"]:
            s += (f' – {_RVR_ONEK_METNI.get(r["ust_on_ek"], "")}'
                  f'{r["ust"]} m arası değişken')
        if r["egilim"]:
            s += f', {RVR_EGILIM[r["egilim"]]}'
        out.append(s)
    return out


def _en_dusuk_rvr_kaydi(metin: str) -> dict | None:
    """en_dusuk_rvr()'daki minimum degeri tasiyan RVR kaydinin tamamini
    dondurur (P/M onekine erismek icin - gorus_operasyonu() esik
    karsilastirmasinda kullanir)."""
    kayitlar = rvr_kayitlari(metin)
    return min(kayitlar, key=lambda r: r["deger"], default=None)


def en_dusuk_rvr(metin: str) -> int | None:
    kayit = _en_dusuk_rvr_kaydi(metin)
    return kayit["deger"] if kayit else None


def ruzgar_kesmesi(metin: str) -> list[str]:
    govde = metin.split("RMK")[0]
    return ["tüm pistlerde" if "ALL" in m.group(1)
            else m.group(1).replace("RWY", "pist ")
            for m in RE_WS.finditer(govde)]


def son_hava(metin: str) -> list[str]:
    from ltfj_analiz import _hava_turkce
    govde = metin.split("RMK")[0]
    return [_hava_turkce(m.group(1)) for m in RE_SON_HAVA.finditer(govde)]


def metar_trendi(metin: str) -> str | None:
    govde = metin.split("RMK")[0]
    m = RE_TREND.search(govde)
    if not m:
        return None
    tur = "Kademeli geçiş" if m.group(1) == "BECMG" else "Geçici"
    kalan = " ".join(m.group(2).split())
    return f"{tur}: {kalan}" if kalan else tur


# ------------------------------------------------- LVTO ve CAT durumu ---
def gorus_operasyonu(cozum: dict, metin: str) -> list[str]:
    """Dusuk gorus kalkis usulleri ve ILS kategorisi acisindan durum."""
    notlar = []
    kayit = _en_dusuk_rvr_kaydi(metin)
    rvr = kayit["deger"] if kayit else None
    gorus = cozum.get("gorus")
    olcut = rvr if rvr is not None else gorus

    if olcut is None:
        return notlar

    if rvr is not None and rvr < LVTO_RVR:
        notlar.append(
            f"LVTO yürürlükte (RVR {rvr} m < {LVTO_RVR} m) — "
            f"düşük görüş kalkışları sadece 06R'den (AD 2.20 S)"
        )
    if olcut < CAT1_TIPIK_RVR:
        notlar.append(
            f"Tipik CAT I eşiği olan {CAT1_TIPIK_RVR} m altında; "
            f"06R tek CAT II pisti (AD 2.19). Kesin minimumlar yaklaşma kartında."
        )
    if kayit and kayit["on_ek"] == "M":
        notlar.append(
            f"R{kayit['pist']} RVR değeri 'M' önekiyle raporlandı — gerçek "
            f"değer {rvr} m'den daha düşük olabilir (ICAO Annex 3: sensörün "
            f"ölçebildiği en düşük değer)."
        )
    return notlar


def prs_askida(cozum: dict, metin: str) -> list[str]:
    """AD 2.20 K-3: tercihli pist sisteminin uygulanamayacagi durumlar."""
    sebepler = []
    hava = " ".join(cozum.get("hava") or [])

    if "TS" in hava:
        sebepler.append("gök gürültülü fırtına")
    if hava.startswith("+") or " +" in f" {hava}":
        sebepler.append("şiddetli yağış")
    if ruzgar_kesmesi(metin):
        sebepler.append("rüzgâr kesmesi bildirimi")
    asanlar = kuyruk_asanlar(cozum, metin)
    if asanlar:
        limit, _ = kuyruk_limiti(cozum)
        sebepler.append(f"{', '.join(asanlar)} için arka rüzgâr {limit} kt üstü")
    rvr = en_dusuk_rvr(metin)
    if rvr is not None and rvr < LVTO_RVR:
        sebepler.append("düşük görüş operasyonları")
    return sebepler


# ---------------------------------------------------------- renk durumu ---
RENK_DURUMLARI = [
    ("BLU", 2500, 8000),
    ("WHT", 1500, 5000),
    ("GRN", 700, 3700),
    ("YLO", 300, 1600),
    ("AMB", 200, 800),
]
RENK_SIMGE = {"BLU": "🔵", "WHT": "⚪", "GRN": "🟢",
              "YLO": "🟡", "AMB": "🟠", "RED": "🔴"}
RENK_ACIKLAMA = {
    "BLU": "çok iyi", "WHT": "iyi", "GRN": "kabul edilebilir",
    "YLO": "sınırlı", "AMB": "çok sınırlı", "RED": "minimumların altında",
}


def renk_durumu(cozum: dict) -> tuple[str, str] | None:
    gorus, tavan = cozum.get("gorus"), cozum.get("tavan")
    if gorus is None and tavan is None:
        return None
    t = tavan if tavan is not None else 99999
    g = gorus if gorus is not None else 99999
    for kod, min_tavan, min_gorus in RENK_DURUMLARI:
        if t >= min_tavan and g >= min_gorus:
            return kod, RENK_ACIKLAMA[kod]
    return "RED", RENK_ACIKLAMA["RED"]


# ------------------------------------------------------------ sis riski ---
def _gunes_saatleri(gun: datetime) -> tuple[datetime, datetime] | None:
    """LTFJ'de gun dogumu ve batimi (UTC)."""
    try:
        # Gun sayisini saat diliminden bagimsiz almak icin ogle vaktini kullaniyoruz
        tarih = gun.astimezone(timezone.utc).replace(
            hour=12, minute=0, second=0, microsecond=0)
        j2000 = (tarih - datetime(2000, 1, 1, 12, tzinfo=timezone.utc)).days
        n = j2000 + 0.0008 - BOYLAM / 360
        M = math.radians((357.5291 + 0.98560028 * n) % 360)
        C = 1.9148 * math.sin(M) + 0.02 * math.sin(2 * M) + 0.0003 * math.sin(3 * M)
        lam = math.radians((math.degrees(M) + C + 180 + 102.9372) % 360)
        gecis = 2451545.0 + n + 0.0053 * math.sin(M) - 0.0069 * math.sin(2 * lam)

        sin_d = math.sin(lam) * math.sin(math.radians(23.44))
        d = math.asin(sin_d)
        p = math.radians(ENLEM)
        cos_w = ((math.sin(math.radians(-0.833)) - math.sin(p) * sin_d)
                 / (math.cos(p) * math.cos(d)))
        if not -1 <= cos_w <= 1:
            return None
        w = math.degrees(math.acos(cos_w))

        def jd_to_dt(jd):
            return (datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
                    + timedelta(days=jd - 2451545.0))

        return jd_to_dt(gecis - w / 360), jd_to_dt(gecis + w / 360)
    except (ValueError, ZeroDivisionError):
        return None


def sis_riski(cozum: dict, zaman: datetime | None) -> str | None:
    """Sis henuz yokken olusma riskini onden haber verir."""
    if cozum.get("sicaklik") is None or cozum.get("cig_noktasi") is None:
        return None
    if any(k in " ".join(cozum.get("hava", [])) for k in ("FG", "BR")):
        return None

    aralik = cozum["sicaklik"] - cozum["cig_noktasi"]
    ruzgar = cozum.get("ruzgar_hiz") or 0
    if aralik > 3 or ruzgar > 8:
        return None

    gece = False
    if zaman:
        saatler = _gunes_saatleri(zaman)
        if saatler:
            dogus, batis = saatler
            gece = zaman >= batis or zaman <= dogus + timedelta(hours=1)

    if aralik <= 2 and ruzgar <= 5:
        seviye = "yüksek" if gece else "orta"
    else:
        seviye = "orta" if gece else "düşük"
    if seviye == "düşük":
        return None

    return (f"Sis oluşma riski {seviye}: sıcaklık–çiğ noktası aralığı {aralik}°C, "
            f"rüzgâr {ruzgar} kt" + (", gece şartları" if gece else ""))


# ------------------------------------------------------- toplu derleme ---
def havacilik_notlari(cozum: dict, metin: str, zaman: datetime | None) -> dict:
    return {
        "renk": renk_durumu(cozum),
        "pistler": pist_raporu(cozum, metin),
        "tercih": tercih_edilen_pist(cozum, metin),
        "rvr": rvr_gruplari(metin),
        "ws": ruzgar_kesmesi(metin),
        "son_hava": son_hava(metin),
        "trend": metar_trendi(metin),
        "sis": sis_riski(cozum, zaman),
        "gorus_op": gorus_operasyonu(cozum, metin),
        "prs": prs_askida(cozum, metin),
    }
