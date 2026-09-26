# -*- coding: utf-8 -*-
"""METAR/TAF gruplarını TEK TEK Türkçeye çevirir.

NEDEN AYRI MODÜL: ``ltfj_analiz.metar_coz`` raporu ÖZETLER - görüş kaç
metre, tavan kaç ft, rüzgâr ne. Buradaki iş farklı: raporu SATIR SATIR
açmak, yani "hangi token ne diyor". İkisi aynı ham metni okur ama farklı
soruya cevap verir; birini ötekinin içine sıkıştırmak ikisini de bozardı.

TEK KAYNAK: desenler (RE_RUZGAR, RE_BULUT, ...) ve Türkçe sözlükler
(OLAY, SIDDET, TANIMLAYICI) ``ltfj_analiz``'ten İTHAL EDİLİR, kopyalanmaz.
Aynı kodun iki yerde farklı Türkçe karşılık üretmesi - ör. METAR'da
"sağanak yağmur", TAF'ta "yağmur sağanağı" - okuyanda "bunlar farklı
şeyler mi?" sorusu doğurur.

UYDURMA YOK: çözülemeyen token ``cozuldu=False`` ile İŞARETLENİR ve ham
hâliyle gösterilir. Tahmin edilmez, sessizce atılmaz. Bir kodun ne
anlama geldiğini bilmiyorsak bunu söylemek, yanlış söylemekten de
göstermemekten de iyidir.
"""
from __future__ import annotations

import re

from ltfj_analiz import (
    RE_BASINC, RE_BULUT, RE_DEGISKEN, RE_GORUS, RE_HAVA, RE_RUZGAR,
    RE_SICAKLIK, _hava_turkce, tokenla,
)

# --- sabitler --------------------------------------------------------------

# 16 değil 8 yön: METAR yönü 10 derece çözünürlükte verir ve
# "kuzey-kuzeydoğu" gibi bir ayrıntı okuyana hiçbir şey katmaz.
YONLER = ("kuzey", "kuzeydoğu", "doğu", "güneydoğu",
          "güney", "güneybatı", "batı", "kuzeybatı")

ORTU = {
    "FEW": "az bulutlu (1–2/8)", "SCT": "parçalı (3–4/8)",
    "BKN": "çok bulutlu (5–7/8)", "OVC": "kapalı (8/8)",
    "VV": "dikey görüş",
}
BULUT_TURU = {"CB": "kümülonimbus", "TCU": "kule kümülüs"}
BULUT_YOK = {
    "NSC": "Önemli bulut yok",
    "NCD": "Bulut saptanmadı (otomatik istasyon)",
    "SKC": "Gökyüzü açık",
    "CLR": "3600 m altında bulut yok",
}
YONLU = {"N": "kuzeyde", "NE": "kuzeydoğuda", "E": "doğuda",
         "SE": "güneydoğuda", "S": "güneyde", "SW": "güneybatıda",
         "W": "batıda", "NW": "kuzeybatıda"}
EGILIM = {"U": "yükseliyor", "D": "düşüyor", "N": "değişmiyor"}

# Tek kelimelik, bağlamsız gruplar. (başlık, açıklama).
BASIT = {
    "METAR": ("Rapor türü", "Düzenli hava gözlem raporu"),
    "SPECI": ("Rapor türü", "Özel gözlem — koşullar eşik değiştirdiği için yayımlandı"),
    "TAF": ("Rapor türü", "Meydan tahmini"),
    "AUTO": ("Kaynak", "Otomatik istasyon — insan gözlemi yok"),
    "COR": ("Düzeltme", "Önceki raporun düzeltilmiş hâli"),
    "AMD": ("Düzeltme", "Tahminin güncellenmiş hâli"),
    "CNL": ("İptal", "Tahmin iptal edildi"),
    "NIL": ("Veri yok", "Rapor yayımlanmadı"),
    "CAVOK": ("Görüş ve bulut", "CAVOK — görüş 10 km ve üzeri, 5000 ft "
              "altında (ve en yüksek sektör irtifasının altında) bulut yok, "
              "önemli hava olayı yok"),
    "NOSIG": ("Eğilim", "Önümüzdeki iki saatte önemli değişiklik beklenmiyor"),
    "NSW": ("Hava olayı", "Önemli hava olayı beklenmiyor"),
    "RMK": ("Notlar", "Bu noktadan sonrası ulusal ek bilgidir (RMK)"),
}

# TAF değişiklik grupları. TEMPO/BECMG METAR'ın da sonunda gelebilir.
DEGISIM = {
    "BECMG": "Tedricen değişiyor",
    "TEMPO": "Geçici olarak",
    "INTER": "Aralıklı olarak",
    "PROB30": "%30 olasılıkla",
    "PROB40": "%40 olasılıkla",
}

# --- desenler (yalnızca bu modüle ait olanlar) ------------------------------

RE_ZAMAN = re.compile(r"^(\d{2})(\d{2})(\d{2})Z$")
RE_PENCERE = re.compile(r"^(\d{2})(\d{2})/(\d{2})(\d{2})$")
RE_FM = re.compile(r"^FM(\d{2})(\d{2})(\d{2})$")
RE_RVR = re.compile(
    r"^R(\d{2}[LCR]?)/([PM]?)(\d{3,4})(?:V([PM]?)(\d{3,4}))?(FT)?([UDN])?$")
RE_YONLU_GORUS = re.compile(r"^(\d{4})(NE|NW|SE|SW|N|S|E|W)$")
RE_ICAO = re.compile(r"^[A-Z]{4}$")
RE_RECENT = re.compile(r"^RE(.+)$")


def yon_adi(derece: int) -> str:
    """Dereceyi 8 ana yöne çevirir. 350° ve 10° ikisi de 'kuzey'."""
    return YONLER[int((derece % 360) / 45 + 0.5) % 8]


# Sayıya gelen 3. tekil iyelik eki, sayının OKUNUŞUNA göre değişir:
# "ayın 25'i" ama "ayın 26'sı", "27'si", "23'ü", "29'u". Tek bir "'i"
# kullanmak metnin yarısını bozuyordu. Ek SON OKUNAN KELİMEYE bakar,
# o yüzden 11-19 birler basamağının, 21-29 de öyle; 10/20/30 kendine
# özgü (on-u, yirmi-si, otuz-u).
IYELIK_EKI = {1: "i", 2: "si", 3: "ü", 4: "ü", 5: "i", 6: "sı",
              7: "si", 8: "i", 9: "u", 10: "u", 20: "si", 30: "u"}


def gun_eki(gun: int) -> str:
    """'ayın {gun}{ek}' için doğru iyelik eki (1-31)."""
    if gun in (10, 20, 30):
        return IYELIK_EKI[gun]
    return IYELIK_EKI[gun % 10 or 10]


def _gun_saat(gun: str, saat: str, dakika: str | None = None) -> str:
    """'ayın 26'sı saat 14:50 UTC'.

    METAR/TAF ay ve yıl TAŞIMAZ. Burada da uydurulmaz - yalnızca raporda
    yazan gün ve saat söylenir."""
    dk = "00" if dakika is None else dakika
    g = int(gun)
    return f"ayın {g}'{gun_eki(g)} saat {saat}:{dk} UTC"


def _satir(token: str, ad: str, aciklama: str) -> dict:
    return {"token": token, "ad": ad, "aciklama": aciklama, "cozuldu": True}


def _cozulemedi(token: str) -> dict:
    return {"token": token, "ad": "", "aciklama": "", "cozuldu": False}


# --- tekil grup çözümleyici ------------------------------------------------

def grup_coz(token: str, *, ilk_icao: bool = False) -> dict:
    """Tek bir METAR/TAF grubunu çözer.

    ``ilk_icao``: raporun BAŞINDAKİ dört harfli kod istasyondur. Bayrak
    olmadan 'CAVOK' gibi dört harfli her şey istasyon sanılırdı; bayrakla
    da raporun ortasındaki bir kod yanlışlıkla istasyon olmaz."""
    if token in BASIT:
        ad, aciklama = BASIT[token]
        return _satir(token, ad, aciklama)

    if token in BULUT_YOK:
        return _satir(token, "Bulut", BULUT_YOK[token])

    if token in DEGISIM:
        return _satir(token, "Değişim", DEGISIM[token])

    if ilk_icao and RE_ICAO.match(token):
        return _satir(token, "İstasyon", "Havalimanı ICAO kodu")

    m = RE_ZAMAN.match(token)
    if m:
        gun, saat, dakika = m.groups()
        return _satir(token, "Zaman", f"Yayım zamanı — {_gun_saat(gun, saat, dakika)}")

    m = RE_PENCERE.match(token)
    if m:
        g1, s1, g2, s2 = m.groups()
        return _satir(token, "Geçerlilik",
                      f"{_gun_saat(g1, s1)} – {_gun_saat(g2, s2)}")

    m = RE_FM.match(token)
    if m:
        gun, saat, dakika = m.groups()
        return _satir(token, "Değişim", f"{_gun_saat(gun, saat, dakika)} itibarıyla")

    m = RE_RUZGAR.match(token)
    if m:
        yon, hiz, hamle, birim = m.groups()
        birim_adi = "m/s" if birim == "MPS" else "kt"
        if yon == "VRB":
            metin = f"Değişken yönlü, {int(hiz)} {birim_adi}"
        else:
            metin = f"{int(yon):03d}° ({yon_adi(int(yon))}) yönünden {int(hiz)} {birim_adi}"
        if hamle:
            metin += f", {int(hamle)} {birim_adi} hamleli"
        return _satir(token, "Rüzgâr", metin)

    m = RE_DEGISKEN.match(token)
    if m:
        a, b = m.groups()
        return _satir(token, "Rüzgâr yönü",
                      f"{int(a):03d}° ile {int(b):03d}° arasında değişken")

    m = RE_RVR.match(token)
    if m:
        pist, on_ek, deger, on_ek2, deger2, ayak, egilim = m.groups()
        birim = "ft" if ayak else "m"
        def _d(oe, dg):
            if oe == "P":
                return f"{int(dg)} {birim} üzerinde"
            if oe == "M":
                return f"{int(dg)} {birim} altında"
            return f"{int(dg)} {birim}"
        metin = f"Pist {pist} görüş menzili {_d(on_ek, deger)}"
        if deger2:
            metin += f", {_d(on_ek2, deger2)} arasında değişken"
        if egilim:
            metin += f" ({EGILIM[egilim]})"
        return _satir(token, "RVR", metin)

    m = RE_YONLU_GORUS.match(token)
    if m:
        deger, yon = m.groups()
        return _satir(token, "Yönlü görüş",
                      f"{YONLU[yon].capitalize()} {int(deger)} m")

    m = RE_GORUS.match(token)
    if m:
        deger = int(m.group(1))
        if deger >= 9999:
            return _satir(token, "Görüş", "10 km ve üzeri")
        if deger == 0:
            return _satir(token, "Görüş", "50 m'den az")
        return _satir(token, "Görüş", f"{deger} m")

    m = RE_BULUT.match(token)
    if m:
        ortu, taban, tur = m.groups()
        ad = ORTU.get(ortu, ortu)
        if taban == "///":
            yukseklik = "yüksekliği ölçülemedi"
        elif ortu == "VV":
            return _satir(token, "Dikey görüş", f"{int(taban) * 100} ft")
        else:
            yukseklik = f"{int(taban) * 100} ft"
        metin = f"{ad.capitalize()}, {yukseklik}"
        if tur:
            metin += f" — {BULUT_TURU[tur]}"
        return _satir(token, "Bulut", metin)

    m = RE_SICAKLIK.match(token)
    if m:
        sic = int(m.group(1).replace("M", "-"))
        cig = int(m.group(2).replace("M", "-"))
        return _satir(token, "Sıcaklık",
                      f"{sic} °C, çiy noktası {cig} °C — spread {sic - cig} °C")

    m = RE_BASINC.match(token)
    if m:
        tip, deger = m.groups()
        if tip == "Q":
            return _satir(token, "Basınç", f"QNH {int(deger)} hPa")
        return _satir(token, "Basınç",
                      f"QNH {int(deger) / 100:.2f} inHg "
                      f"({round(int(deger) / 100 * 33.8639)} hPa)")

    m = RE_RECENT.match(token)
    if m and RE_HAVA.match(m.group(1)):
        return _satir(token, "Yakın geçmiş",
                      f"Gözlemden önce: {_hava_turkce(m.group(1))}")

    if RE_HAVA.match(token):
        return _satir(token, "Hava olayı", _hava_turkce(token).capitalize())

    return _cozulemedi(token)


# --- rapor düzeyi ----------------------------------------------------------

def metar_satirlari(metin: str) -> list[dict]:
    """METAR/SPECI'yi satır satır çözer.

    RMK'DAN SONRASI TEK SATIR: ulusal ek bilgidir, uluslararası bir
    sözlüğü yoktur ve LTFJ'de pist anemometrelerini taşır. Onu
    ``ltfj_pist`` zaten ayrı okuyor; burada tek tek çözmeye çalışmak
    uydurmaya davet olurdu."""
    tokenlar = tokenla(metin)
    satirlar: list[dict] = []
    icao_bekleniyor = True
    for i, t in enumerate(tokenlar):
        if t == "RMK":
            kalan = " ".join(tokenlar[i + 1:])
            ad, aciklama = BASIT["RMK"]
            satirlar.append(_satir(kalan or t, ad, aciklama))
            break
        satirlar.append(grup_coz(t, ilk_icao=icao_bekleniyor))
        if icao_bekleniyor and RE_ICAO.match(t) and t not in BASIT:
            icao_bekleniyor = False
        elif t not in ("METAR", "SPECI", "TAF", "COR", "AMD"):
            icao_bekleniyor = False
    return satirlar


def taf_bolumleri(metin: str) -> list[dict]:
    """TAF'ı DEĞİŞİM GRUPLARINA böler.

    Döner: [{"baslik", "pencere", "satirlar": [...]}]. İlk bölümün
    başlığı "Tahminin başlangıcı"dır; sonrakiler BECMG/TEMPO/PROB..
    gruplarıdır. PROB30 TEMPO gibi BİRLEŞİK başlıklar tek bölümdür -
    ikiye bölmek "%30 olasılıkla" ve "geçici olarak" diye birbirinden
    kopuk iki satır üretirdi."""
    tokenlar = tokenla(metin)
    bolumler: list[dict] = []
    simdiki = {"baslik": "Tahminin başlangıcı", "pencere": "", "satirlar": []}
    icao_bekleniyor = True
    i = 0
    while i < len(tokenlar):
        t = tokenlar[i]
        yeni_baslik = None
        if t in DEGISIM:
            parcalar = [DEGISIM[t]]
            i += 1
            # PROB30 TEMPO / PROB40 INTER gibi birlesik basliklar
            while i < len(tokenlar) and tokenlar[i] in DEGISIM:
                parcalar.append(DEGISIM[tokenlar[i]].lower())
                i += 1
            yeni_baslik = ", ".join(parcalar)
        elif RE_FM.match(t):
            m = RE_FM.match(t)
            yeni_baslik = f"{_gun_saat(*m.groups())} itibarıyla"
            i += 1

        if yeni_baslik is not None:
            bolumler.append(simdiki)
            pencere = ""
            if i < len(tokenlar) and RE_PENCERE.match(tokenlar[i]):
                pencere = grup_coz(tokenlar[i])["aciklama"]
                i += 1
            simdiki = {"baslik": yeni_baslik, "pencere": pencere, "satirlar": []}
            continue

        satir = grup_coz(t, ilk_icao=icao_bekleniyor)
        # Gecerlilik penceresi BASLIK bilgisidir, satir degil.
        # KOSUL "satirlar bos mu" DEGIL: TAF'in gecerliligi (2518/2618)
        # TAF/LTFJ/251640Z'den SONRA gelir, yani ilk bolumun satir
        # listesi o noktada zaten dolu. O kosulla pencere hicbir zaman
        # dolmuyordu ve gecerlilik siradan bir satir olarak listeye
        # dusuyordu - ilk bolum penceresiz, satirlar ise bir fazla.
        if satir["ad"] == "Geçerlilik" and not simdiki["pencere"]:
            simdiki["pencere"] = satir["aciklama"]
        else:
            simdiki["satirlar"].append(satir)
        if icao_bekleniyor and RE_ICAO.match(t) and t not in BASIT:
            icao_bekleniyor = False
        elif t not in ("TAF", "COR", "AMD"):
            icao_bekleniyor = False
        i += 1

    bolumler.append(simdiki)
    return [b for b in bolumler if b["satirlar"] or b["pencere"]]


def cozulemeyenler(satirlar: list[dict]) -> list[str]:
    """Çözülemeyen token'lar - sayfada 'çözümlenemeyenler' bölümü için."""
    return [s["token"] for s in satirlar if not s["cozuldu"]]
