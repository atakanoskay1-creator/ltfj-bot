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

VERI TABANLI TASNIF (bu modulun ciktisini tuketen katmanlar icin):
  GOZLEMLENEN   dogrudan METAR/RMK/RVR/WS metninden okunan (yon, hiz, RVR
                degeri, hava olayi...).
  HESAPLANAN    GOZLEMLENEN'den deterministik matematikle turetilen (bas/
                kuyruk/yan ruzgar bileseni, en dusuk RVR...).
  CIKARSANAN    dogrudan veride olmayip METAR'da bulunmayan bir alan (ornegin
                RWYCC) icin konservatif varsayimla doldurulan deger (ornegin
                yagis varsa "islak pist" kabulu). Bu fonksiyonlarin cogu bunu
                donus degerinin yaninda acik gerekce metniyle belirtir
                (ornegin kuyruk_limiti()'nin ikinci elemani); resmi bir AIP/
                operator limiti degildir.
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
    """RMK bolumundeki pist basi ruzgarlarini ayiklar (AD 2.15: THR'den 220 M).
    GOZLEMLENEN veri - dogrudan RMK metninden okunur."""
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
    """(bas_ruzgari, yan_ruzgar, yan_taraf). bas_ruzgari negatifse kuyruk
    ruzgaridir. HESAPLANAN - GOZLEMLENEN yon/hizdan deterministik turetilir."""
    if yon is None or hiz is None:
        return None, None, None
    aci = math.radians(yon - pist_yonu)
    return hiz * math.cos(aci), abs(hiz * math.sin(aci)), \
        ("sağdan" if math.sin(aci) >= 0 else "soldan")


def bilesenler_araligi(yon1: int, yon2: int, hiz, pist_yonu: float) -> dict | None:
    """Degisken ruzgar yonu (METAR'da ör. '020V090' grubu) icin pist
    bilesenlerinin ALABILECEGI degeri tek bir sayi yerine bir ARALIK olarak
    verir. HESAPLANAN - ama girdisi (yon araligi) zaten belirsiz oldugundan
    cikti da belirsizligi acikca tasir; tek bir "kesin" sayi UYDURULMAZ.

    METAR'daki degisken yon grubu, ruzgarin gozlemlenen sure icinde SAAT
    YONUNDE yon1'den yon2'ye kadar taradigi ark'i belirtir (ICAO Annex 3).
    Analitik turev yerine 1 derecelik adimlarla sayisal tarama yapiyoruz -
    METAR zaten yon bilgisini 10 derece cozunurlukte veriyor, bu yeterli
    hassasiyette ve kod olarak cok daha basit/dogrulanabilir."""
    if hiz is None or yon1 is None or yon2 is None:
        return None
    ark = []
    y = yon1 % 360
    hedef = yon2 % 360
    for _ in range(361):
        ark.append(y)
        if y == hedef:
            break
        y = (y + 1) % 360
    bas_degerleri, yan_degerleri = [], []
    for yon in ark:
        bas, yan, _ = bilesenler(yon, hiz, pist_yonu)
        bas_degerleri.append(bas)
        yan_degerleri.append(yan)
    return {
        "bas_min": min(bas_degerleri), "bas_max": max(bas_degerleri),
        "yan_max": max(yan_degerleri),
    }


def _aralik_metni(aralik: dict) -> str:
    bas_min, bas_max, yan_max = aralik["bas_min"], aralik["bas_max"], aralik["yan_max"]
    if bas_min >= 0:
        bas_metni = f"baş {bas_min:.0f}–{bas_max:.0f} kt"
    elif bas_max <= 0:
        bas_metni = f"KUYRUK {abs(bas_max):.0f}–{abs(bas_min):.0f} kt"
    else:
        bas_metni = f"KUYRUK azami {abs(bas_min):.0f} kt – baş azami {bas_max:.0f} kt"
    return f"{bas_metni}, yan azami {yan_max:.0f} kt"


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
    CIKARSANAN: RWYCC METAR'da yok - yagis varsa pisti islak kabul ediyoruz.
    Bu resmi bir RWYCC raporu DEGIL, konservatif bir tahmindir (gerekce
    metni bunu aciklar)."""
    hava = " ".join(cozum.get("hava") or [])
    islak = any(k in hava for k in ISLAK_YAPAN)
    return ((KUYRUK_LIMIT_ISLAK,
              "CIKARSANAN varsayım — RWYCC bildirilmedi, yağış nedeniyle "
              "ıslak/kirli pist kabul edildi") if islak
            else (KUYRUK_LIMIT_KURU,
              "CIKARSANAN varsayım — RWYCC bildirilmedi, yağış yok, kuru pist kabul edildi"))


def pist_ruzgar_kaynagi(cozum: dict, metin: str) -> list[dict]:
    """TEK ortak (canonical) per-pist ruzgar kaynagi modeli. pist_raporu(),
    tercih_edilen_pist(), kuyruk_asanlar() VE ltfj_panel.py BURADAN besleniyor
    - ayni METAR icin farkli tuketicilerin farkli sonuca varmasini onlemek
    icin tek bir fonksiyon var.

    Her pist icin RMK'da (AD 2.15 anemometreleri) o pist adina GOZLEMLENEN
    veri varsa onu, yoksa alan METAR ruzgarina TEK TEK duser - bir pistin
    RMK'da bulunmayisi diger pistlerin de atlanmasina yol acmaz (bu, F2
    olarak duzeltilen sinifta bir hataydi ve ayni desen onceden
    tercih_edilen_pist() ve ltfj_panel.py::_pist_verisi() icinde AYRI AYRI
    tekrarlanmisti - artik hepsi bu fonksiyona indirgeniyor).

    Sabit (hiz_sabit) ve hamle (hiz_hamle) degerleri AYRI tasinir - hangi
    tuketicinin "worst case" (PRS/kuyruk limiti) mi yoksa "sakin ruzgar"
    (tercih_edilen_pist) mi istedigine kendisi karar versin; burada
    onceden max() alip tek sayiya indirgemek bu ayrimi kaybederdi."""
    olculenler = {o["pist"]: o for o in pist_ruzgarlari(metin)}
    kaynaklar = []
    for pist in TERCIHLI_PISTLER:
        o = olculenler.get(pist)
        if o:
            kaynaklar.append({
                "pist": pist, "yon": o["yon"],
                "hiz_sabit": o["hiz"], "hiz_hamle": o["hamle"],
                "degisken": o["degisken"],
                "kaynak": "AD 2.15 anemometreleri",
            })
        else:
            kaynaklar.append({
                "pist": pist, "yon": cozum["ruzgar_yon"],
                "hiz_sabit": cozum["ruzgar_hiz"], "hiz_hamle": cozum["ruzgar_hamle"],
                "degisken": cozum.get("degisken"),
                "kaynak": "alan rüzgârından",
            })
    return kaynaklar


def _hiz_worst(k: dict) -> int:
    return max(k["hiz_sabit"] or 0, k["hiz_hamle"] or 0)


def pist_raporu(cozum: dict, metin: str) -> list[str]:
    """Her pist basi icin GOZLEMLENEN ham ruzgar (yon/hiz/hamle/degisken
    aralik) - METAR/RMK'da NE YAZILIYSA (pist_ruzgar_kaynagi() uzerinden)
    AYNEN o gosterilir, runway eksenine gore bas/kuyruk/yan bilesenine
    (trigonometrik donusum) CEVRILMEZ.

    ONCEDEN bu fonksiyon HESAPLANAN bilesenleri gosteriyordu (ornegin RMK
    '24L 03007KT' -> 'KUYRUK 6 kt, yan 4 kt'). Kullanici (2026-09-17) bunun
    METAR'da yazanla uyusmuyor gibi gorundugunu bildirdi - ham deger 030/7
    iken satirda 6/4 gibi FARKLI sayilarin cikmasi kafa karistirdi. Netlestirme
    sorusunda "sadece METAR/SPECI'de yazan ham degeri goster, donusum
    yapilmasin" secildi. Bilesen hesabi (bilesenler()) SILINMEDI - hala
    tercih_edilen_pist() ve kuyruk_asanlar() icinde KULLANILIYOR (onlarin
    ciktisi zaten bir pist kodu/liste, ham sayi degil - o yuzden ayni
    karisikliga yol acmiyor); PRS arka ruzgar limiti asimi da BURADA artik
    pist basina degil, footer'da ayri bir liste olarak gosteriliyor."""
    kaynaklar = pist_ruzgar_kaynagi(cozum, metin)
    limit, limit_gerekce = kuyruk_limiti(cozum)

    satirlar = []
    kaynak_gruplari: dict[str, list[str]] = {}
    for k in sorted(kaynaklar, key=lambda k: k["pist"]):
        pist = k["pist"]
        if _pist_yonu(pist) is None:
            continue
        kaynak_gruplari.setdefault(k["kaynak"], []).append(pist)

        yon, hiz, hamle, degisken = k["yon"], k["hiz_sabit"], k["hiz_hamle"], k["degisken"]

        if yon is None:
            yon_metni = "değişken yön"
        elif degisken:
            yon_metni = f"{yon:03d}° (değişken {degisken[0]:03d}°–{degisken[1]:03d}°)"
        else:
            yon_metni = f"{yon:03d}°"

        if hiz is None:
            satirlar.append(f"{pist}: {yon_metni}, rüzgâr hızı bildirilmedi")
            continue

        hiz_metni = f"{hiz} kt"
        if hamle is not None and hamle > hiz:
            hiz_metni += f" (hamle {hamle} kt)"

        satirlar.append(f"{pist}: {yon_metni} {hiz_metni}")

    asanlar = kuyruk_asanlar(cozum, metin)
    if satirlar:
        if len(kaynak_gruplari) == 1:
            etiket = next(iter(kaynak_gruplari))
        else:
            etiket = "; ".join(
                f"{', '.join(pistler)}: {kaynak}"
                for kaynak, pistler in kaynak_gruplari.items()
            )
        ek = f"kuyruk limiti {limit} kt — {limit_gerekce}"
        if asanlar:
            ek = f"PRS arka rüzgâr limitini aşan pist(ler) (hesaplanan): {', '.join(asanlar)}; {ek}"
        satirlar.append(f"({etiket}; {ek})")
    return satirlar


def tercih_edilen_pist(cozum: dict, metin: str) -> str | None:
    """Meteorolojik baş rüzgârı tercihi: en çok baş rüzgârı alan pist başı.

    ÖNEMLİ: Bu bir ATC 'runway-in-use' ataması DEĞİLDİR - program NOTAM,
    pist kapanışı, trafik akışı, yaklaşma prosedürü, SID/STAR veya ATC
    koordinasyonunu bilmez. Sadece rüzgâr bileşenlerine göre HESAPLANMIŞ bir
    tercihtir; aktif pisti ATC belirler (AIP AD 2.20 K).

    Sabit (hamlesiz) rüzgâr kullanılır - geçici bir hamle tercih kararını
    sallamamalı. pist_ruzgar_kaynagi() ile AYNI per-pist kaynak modelini
    kullanır (RMK'da olmayan pist artık burada da atlanmıyor - önceden bu
    fonksiyon RMK varsa SADECE RMK'daki pistleri değerlendiriyordu, F2 ile
    aynı sınıfta ayrı bir hataydı)."""
    kaynaklar = pist_ruzgar_kaynagi(cozum, metin)

    en_iyi, en_iyi_bas = None, None
    for k in kaynaklar:
        yonu = _pist_yonu(k["pist"])
        if yonu is None:
            continue
        bas, _, _ = bilesenler(k["yon"], k["hiz_sabit"], yonu)
        if bas is not None and (en_iyi_bas is None or bas > en_iyi_bas):
            en_iyi, en_iyi_bas = k["pist"], bas
    return en_iyi


def kuyruk_asanlar(cozum: dict, metin: str) -> list[str]:
    """PRS arka ruzgar limitini asan pist baslari. Worst-case (hamleli)
    hiz kullanilir - limit asimi kontrolu en kotu senaryoyu esas almali."""
    limit, _ = kuyruk_limiti(cozum)
    kaynaklar = pist_ruzgar_kaynagi(cozum, metin)

    asanlar = []
    for k in kaynaklar:
        yonu = _pist_yonu(k["pist"])
        if yonu is None:
            continue
        bas, _, _ = bilesenler(k["yon"], _hiz_worst(k), yonu)
        if bas is not None and bas < 0 and abs(bas) > limit:
            asanlar.append(k["pist"])
    return sorted(asanlar)


# -------------------------------------------------------- RVR / WS / RE ---
def rvr_kayitlari(metin: str) -> list[dict]:
    """GOZLEMLENEN. on_ek/ust_on_ek P (bu değer veya üzeri) ya da M (bu
    değer veya altı) niteleyicilerini taşır (ICAO Annex 3) - sadece
    görüntüleme için değil, esik_karsilastir() bunları asıl karşılaştırmada
    kullanır."""
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
    """en_dusuk_rvr()'daki minimum degeri tasiyan RVR kaydinin TAMAMINI
    (pist kimligi + P/M niteligi dahil) dondurur. Coklu pist RVR'si
    raporlandiginda 'en dusuk' rakami hangi pistin oldugu bilgisi olmadan
    ATC acisindan anlamsizdir (bkz. modul basi VERI TABANLI TASNIF notu)."""
    kayitlar = rvr_kayitlari(metin)
    return min(kayitlar, key=lambda r: r["deger"], default=None)


def en_dusuk_rvr(metin: str) -> int | None:
    kayit = _en_dusuk_rvr_kaydi(metin)
    return kayit["deger"] if kayit else None


def esik_karsilastir(deger: int, on_ek: str, esik: int) -> str:
    """Bir RVR (veya baska P/M nitelikli) degerin bir esikten KESIN olarak
    altinda olup olmadigini ICAO Annex 3 P/M anlamlariyla belirler:

      P<deger>  -> gercek deger BU DEGER YA DA UZERINDEDIR (ust sinir yok)
      M<deger>  -> gercek deger BU DEGER YA DA ALTINDADIR (alt sinir yok)
      (oneksiz) -> deger kesindir

    Donus: "evet" (kesinlikle esigin altinda), "hayir" (kesinlikle esik ya
    da uzerinde), "belirsiz" (P/M niteligi nedeniyle KESIN cevap verilemez -
    ornegin M0600 ile 550 esigi: gercek deger 0-600 arasinda herhangi bir
    sey olabilir, 550'nin altinda mi ustunde mi bilinmiyor).

    Boylece nitelikli bir deger asla sessizce "tam sayiymis gibi" kesin
    esik karsilastirmasina sokulmuyor - kullanicinin '...basitçe 1500 olarak
    kabul edip rvr<1500 seklinde degerlendirmek yanlis olabilir' uyarisinin
    karsiligi budur."""
    if on_ek == "P":
        return "hayir" if deger >= esik else "belirsiz"
    if on_ek == "M":
        return "evet" if deger < esik else "belirsiz"
    return "evet" if deger < esik else "hayir"


# ------------------------------------------------- LVTO ve CAT durumu ---
def gorus_operasyonu(cozum: dict, metin: str) -> list[str]:
    """Dusuk gorus kalkis usulleri ve ILS kategorisi acisindan durum.
    HESAPLANAN + P/M nitelikli RVR'de gerektiginde acikca BELIRSIZ ciktisi
    (bkz. esik_karsilastir)."""
    notlar = []
    kayit = _en_dusuk_rvr_kaydi(metin)
    gorus = cozum.get("gorus")

    if kayit is not None:
        pist_etiketi = f"R{kayit['pist']} "
        deger_metni = f'{_RVR_ONEK_METNI.get(kayit["on_ek"], "")}{kayit["deger"]} m'

        lvto = esik_karsilastir(kayit["deger"], kayit["on_ek"], LVTO_RVR)
        if lvto == "evet":
            notlar.append(
                f"LVTO yürürlükte ({pist_etiketi}RVR {deger_metni} < {LVTO_RVR} m) — "
                f"düşük görüş kalkışları sadece 06R'den (AD 2.20 S)"
            )
        elif lvto == "belirsiz":
            notlar.append(
                f"LVTO durumu belirsiz — {pist_etiketi}RVR {deger_metni} olarak "
                f"raporlandı, gerçek değer {LVTO_RVR} m eşiğinin altında olabilir "
                f"(ICAO Annex 3 'M' niteliği: sensörün ölçebildiği en düşük değer)"
            )

        cat1 = esik_karsilastir(kayit["deger"], kayit["on_ek"], CAT1_TIPIK_RVR)
        if cat1 == "evet":
            notlar.append(
                f"{pist_etiketi}RVR {deger_metni}, tipik CAT I eşiği olan "
                f"{CAT1_TIPIK_RVR} m altında; 06R tek CAT II pisti (AD 2.19). "
                f"Kesin minimumlar yaklaşma kartında."
            )
        elif cat1 == "belirsiz":
            notlar.append(
                f"CAT I durumu belirsiz — {pist_etiketi}RVR {deger_metni} olarak "
                f"raporlandı, gerçek değer {CAT1_TIPIK_RVR} m tipik eşiğin "
                f"altında olabilir (ICAO Annex 3 'M' niteliği)"
            )
    elif gorus is not None:
        # RVR hic raporlanmamis - gorus mesafesi tek gozlemlenen olcu.
        # LVTO tanimi AIP'de ozel olarak RVR'ye bagli (AD 2.20 S), bu yuzden
        # gorus mesafesiyle LVTO iddia edilmez - sadece CAT I kiyasi yapilir.
        if gorus < CAT1_TIPIK_RVR:
            notlar.append(
                f"Görüş {gorus} m, tipik CAT I eşiği olan {CAT1_TIPIK_RVR} m "
                f"altında (RVR raporlanmadı, görüş mesafesi kullanıldı); "
                f"06R tek CAT II pisti (AD 2.19). Kesin minimumlar yaklaşma kartında."
            )

    return notlar


def prs_askida(cozum: dict, metin: str) -> list[str]:
    """AD 2.20 K-3: METAR verisine göre tercihli pist sisteminin (PRS)
    uygulanmasını kısıtlayan meteorolojik koşullar. Bu fonksiyon resmi bir
    ATC PRS iptal kararı DEĞİL, METAR'a dayalı bir HESAPLANAN göstergedir -
    gerçek karar ATC'nindir (AD 2.20 K madde 2-3)."""
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

    kayit = _en_dusuk_rvr_kaydi(metin)
    if kayit is not None:
        durum = esik_karsilastir(kayit["deger"], kayit["on_ek"], LVTO_RVR)
        if durum == "evet":
            sebepler.append(f"düşük görüş operasyonları (R{kayit['pist']} RVR)")
        elif durum == "belirsiz":
            sebepler.append(
                f"düşük görüş operasyonları olabilir — R{kayit['pist']} RVR "
                f"'{kayit['on_ek']}{kayit['deger']:04d}' niteliğiyle belirsiz"
            )
    return sebepler


# ---------------------------------------------------------- renk durumu ---
# UYARI: Bu renkler resmi CAT I/II/III yaklasma minimumlari veya baska bir
# resmi havacilik kategorisi DEGILDIR. LTFJ Bot'a ozgu, gorus/tavan
# bandlarina gore hesaplanan bir "durum seviyesi/onem derecesi"
# gostergesidir - tuketici katmanlar (Telegram/web/panel) bunu boyle
# etiketlemelidir.
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
RENK_ETIKETI = "LTFJ Bot durum seviyesi"  # resmi CAT I/II/III degil - bkz. yukarisi


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
    """Sis henuz yokken olusma riskini onden haber verir. CIKARSANAN /
    sezgisel yontem - resmi bir tahmin (forecast) DEGILDIR, sadece dewpoint
    spread + ruzgar + gece/gunduz'e dayali bir METAR-tabanli gosterge.
    Donen metin bunu acikca belirtir."""
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

    # NOT: cagiran taraflarin bir kismi (ltfj_bot.py, ltfj_sayfa.py) bu
    # metni ilk ':' isaretinden BOLUP sadece sonrasini gosteriyor (etiket
    # zaten "Sis" diye ayrica basiliyor) - bu yuzden seviye VE sezgisel
    # yontem uyarisi bilerek ':' isaretinden SONRAYA konuyor, yoksa sessizce
    # kaybolurlardi.
    return (f"Sis oluşum göstergesi: {seviye} (METAR tabanlı sezgisel yöntem, "
            f"resmi tahmin değil) — sıcaklık–çiğ noktası aralığı {aralik}°C, "
            f"rüzgâr {ruzgar} kt" + (", gece şartları" if gece else ""))


# ------------------------------------------------------- toplu derleme ---
def havacilik_notlari(cozum: dict, metin: str, zaman: datetime | None) -> dict:
    """Tek bir METAR icin TUM havacilik turevlerini tasiyan ortak sonuc -
    Telegram, web sayfasi, ATC paneli ve Claude istemi BURADAN beslenir ki
    ayni METAR icin farkli ekranlarda farkli hesap ortaya cikmasin.

    "varsayimlar": bu METAR icin fiilen devrede olan CIKARSANAN (inferred)
    bilgilerin duz metin listesi - RWYCC bildirilmedigi icin yapilan
    kuyruk-limiti varsayimi, sis olusum heuristigi vb. Boylece bu bilgiler
    tek bir yerden toplanip (ornegin ATC panelinde ayri bir "ASSUMPTIONS"
    bolumu olarak, ya da Claude istemine ek baglam olarak) gosterilebilir -
    OBSERVED/CALCULATED degerlerle ayni satirda kaybolup gitmezler."""
    _, limit_gerekce = kuyruk_limiti(cozum)
    sis = sis_riski(cozum, zaman)

    varsayimlar = [limit_gerekce]
    if sis:
        varsayimlar.append(sis)

    return {
        "renk": renk_durumu(cozum),
        "renk_etiketi": RENK_ETIKETI,
        "pistler": pist_raporu(cozum, metin),
        "tercih": tercih_edilen_pist(cozum, metin),
        "rvr": rvr_gruplari(metin),
        "ws": ruzgar_kesmesi(metin),
        "son_hava": son_hava(metin),
        "trend": metar_trendi(metin),
        "sis": sis,
        "gorus_op": gorus_operasyonu(cozum, metin),
        "prs": prs_askida(cozum, metin),
        "varsayimlar": varsayimlar,
    }


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
