#!/usr/bin/env python3
"""
LVO (Dusuk Gorus Operasyonlari) icin STATIK dokuman referans verisi.

Kaynak: "SABIHA GOKCEN HAVALIMANI DUSUK GORUS OPERASYONLARI TALIMATI"
(Dok.No: TL.007, Rev.No: REV.1, Rev.Tarihi: 16.08.2024) - kullanicinin
yukledigi PDF'den DOGRUDAN alinmis bolum/madde referanslariyla.

BU MODUL BIR KARAR MOTORU DEGILDIR. Asagidaki degerler SADECE dokumanin
kendi metninde yazan referans esikleri/tablolarini tasir - hicbir
fonksiyon bu degerleri METAR/AWOS/NOTAM/ATIS verisiyle KARSILASTIRMAZ,
"LVO aktif", "CAT II kullanilabilir" gibi bir sonuc URETMEZ. Web katmani
(ltfj_sayfa.py) bu veriyi oldugu gibi, "DOCUMENT REFERENCE ONLY" etiketiyle
gosterir. Guncel operasyonel minima icin daima AIP/ATIS/AWOS ve resmi
yayinlar esas alinmalidir - bu dokumanin kendisi de ayni uyariyi tasir
(bkz. 6.1.a: "Bu dokumandaki degerler referans degerler olup, pistlerin
yaklasma kategorisine iliskin guncel yayinlar takip edilmelidir.").
"""

DOKUMAN = {
    "baslik": "Sabiha Gökçen Havalimanı Düşük Görüş Operasyonları Talimatı",
    "dok_no": "TL.007",
    "rev_no": "REV.1",
    "rev_tarihi": "16.08.2024",
    "etiket": "DOCUMENT REFERENCE ONLY",
}

# 6.1.a Tablo-1 - pist yaklasma kategorileri ve dokumanda verilen referans
# RVR araliklari (metre). "-" o pist icin ilgili operasyon tanimlanmamis
# demektir (dokumanda oldugu gibi aynen tasinir, bos deger UYDURULMAZ).
PIST_TABLOSU = [
    {"pist": "06R", "kategori": "CAT II", "inis_rvr": "550–300", "kalkis_rvr": "400–125",
     "aciklama": "CAT II iniş ve LVTO kalkış"},
    {"pist": "24L", "kategori": "CAT I", "inis_rvr": "—", "kalkis_rvr": "—", "aciklama": ""},
    {"pist": "06L", "kategori": "CAT I", "inis_rvr": "—", "kalkis_rvr": "—", "aciklama": ""},
    {"pist": "24R", "kategori": "CAT I", "inis_rvr": "—", "kalkis_rvr": "400–125",
     "aciklama": "Sadece LVTO kalkış"},
]

# 6.1.ee - dokumanin kendi ifadesiyle RVR "kullanim limitleri" (safha
# baslangic esikleri). Dahil/haric sinirlar SADECE dokumanda acikca
# yazildigi yerlerde (6.2.a, 6.3.1.a, 6.3.2.b) aynen kullanilir; 6.1.ee'nin
# kendisi sadece "X metre altinda" diyor, ayrica bir ust sinir vermiyor.
RVR_ESIKLERI = [
    {
        "esik_altinda_m": 800,
        "safha": "LVO Hazırlık Safhası",
        "kaynak_madde": "6.1.ee, 6.2.a",
        "not": "550 ≤ Hazırlık Safhası < 800 (madde 6.2.a)",
    },
    {
        "esik_altinda_m": 550,
        "safha": "LVO İniş Operasyonları Safhası (CAT II, sadece 06R)",
        "kaynak_madde": "6.1.ee, 6.3.1.a",
        "not": "300 ≤ Uygulama Safhası < 550 (madde 6.3.1.a)",
    },
    {
        "esik_altinda_m": 400,
        "safha": "LVO Kalkış Operasyonları Safhası (LVTO, 06R ve 24R)",
        "kaynak_madde": "6.1.ee, 6.3.2.b",
        "not": "125 ≤ Uygulama Safhası < 400 (madde 6.3.2.b)",
    },
    {
        "esik_altinda_m": 350,
        "safha": "Tanımlanmış alanlarda zorunlu Follow-me uygulama safhası",
        "kaynak_madde": "6.1.ee",
        "not": "",
    },
]

# 3. TANIMLAR'daki CAT I / CAT II tanim esikleri (DH ile birlikte) - RVR
# TEK BASINA degil, DH ile BIRLIKTE degerlendirilen resmi tanimlar.
KATEGORI_TANIMLARI = [
    {"kategori": "CAT I", "rvr": "RVR ≥ 550 m", "dh": "DH ≥ 60 m (200 ft)"},
    {"kategori": "CAT II", "rvr": "300 m ≤ RVR < 550 m", "dh": "30 m (100 ft) ≤ DH < 60 m (200 ft)"},
]

# Dokumanin kendi uyarilari - referans panelinde AYNEN gosterilecek notlar.
UYARI_NOTLARI = [
    "\"Hazırlık Safhası\"nın başlatıldığı 800 m RVR değeri ile CAT I "
    "operasyonları limiti olan 800 m Görüş değeri karıştırılmamalıdır (madde 6.1.ee).",
    "06R pisti için CAT II operasyonları uygulanmaya/planlanmaya başladığında "
    "LVTO sadece 06R pistinden yapılır; 06R iniş için planlanırken 24R'den "
    "LVTO yapılmaz (madde 6.3.2.e).",
    "06L ve 24L pistleri düşük görüş kalkış operasyonlarında (LVTO) kullanılmaz (madde 6.3.2.d).",
]

BILGI_UYARISI = (
    "Bilgi amaçlıdır. Operasyonel karar yerine geçmez. Güncel AIP, ATIS, "
    "AWOS ve resmî yayınlar kontrol edilmelidir."
)
