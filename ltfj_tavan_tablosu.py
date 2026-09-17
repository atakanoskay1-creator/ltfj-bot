#!/usr/bin/env python3
"""LTFJ dusuk bulut tabani icin DONDURULMUS kosullu olasilik tablosu.

Egitim laboratuvari sis_modeli/ altindadir; buraya yalnizca dondurulmus
CIKTI tasinir (izolasyon sozlesmesi - bkz. sis_modeli/README.md). Bu modul
hicbir sey import etmez: saf veri + aritmetik.

HEDEF: su an bulut tabani 500 ft'in ALTINDA DEGILKEN,
onumuzdeki 3 saat icinde altina dusecek mi?

NEDEN MODEL DEGIL TABLO: LVO icin asil onemli esikte (CAT II, <200 ft)
18 yilda yalnizca ~61 bagimsiz olay var - lojistik regresyon icin kabul
edilen 150 olay tabaninin altinda. Olay sayisi yeten <500 ft esiginde
tablo kuruldu.

OKUMA BIRIMI "KAT", MUTLAK YUZDE DEGIL. Bu bir tercih degil olcum sonucu:
gelistirme (2017-2023) tablosu holdout'ta (2024-2026) sinandiginda hucre
katlarinin log korelasyonu 0.986 (SIRALAMA aynen tasiniyor) ama kat
oranlarinin medyani 2.27 (SEVIYE tasinmiyor). Gelistirmede %9.8 ogrenilen
bir hucre holdout'ta %14.0 gerceklesti. Yuzde yayinlamak, olculmus 2.3
katlik hatayi kesin bir sayi gibi sunmak olurdu.

Buradaki tablo, dogrulama bittikten SONRA rejim penceresinin tamamiyla
(2017-2026) yeniden kestirildi: 167189 an, 1704 pozitif,
329 ayri gun.

BANT SINIRLARI A PRIORI - projenin kendi esikleri (LVO 550 m, sis 1000 m,
VFR 5000 m, CAVOK; spread icin istatistik.SPREAD_KOVALARI). Otomatik
quantile bantlama gorusu 8 bilgilendirici banttan 3'e dusuruyordu
(gozlemlerin %87'si 9999-10000 m'de yigili).

Resmi bir tahmin DEGILDIR; TAF'in yerine gecmez.
"""

HEDEF_TAVAN_FT = 500
HEDEF_UFUK_SAAT = 3
KAYNAK_DONEM = "2017–2026"

# Uzun donem taban oran - "kat"in paydasi.
TABAN_ORAN = 0.010192058089946108

SPREAD_BANTLARI = [1, 2, 3, 5, 8]      # °C
GORUS_BANTLARI = [550, 1000, 5000, 9999]       # m

# Bu sayinin altinda gozlemi olan hucrede tahmin INCE sayilir ve not bunu
# acikca soyler (woe.KOVA_MIN_GOZLEM'in yarisi).
INCE_GOZLEM_SINIRI = 100

# (spread_bandi, gorus_bandi) -> (n, pozitif, kat, kat_alt, kat_ust)
# kat_alt/kat_ust: GUN BAZINDA blok bootstrap %5-95. Satir bazinda
# orneklense aralik sahte sekilde daralirdi - bir dusuk tavan olayi
# ~6 satir uretiyor.
TABLO = {
    (0, 0): (73, 16, 6.482966173107019, 3.981221693385955, 9.405523234202109),
    (0, 1): (82, 21, 8.015701478373789, 5.306134614609651, 10.680328008992696),
    (0, 2): (1213, 195, 13.681913668849617, 11.347990213531235, 16.16666902030094),
    (0, 3): (1504, 116, 6.7966025810575506, 5.026615410893855, 8.626911640874376),
    (0, 4): (3006, 85, 2.663701459118613, 1.8299320079475254, 3.7749540606653693),
    (1, 0): (28, 13, 6.471504097685529, 3.2478363399827908, 9.674644176948254),
    (1, 1): (52, 12, 5.465822714062152, 2.9480163481589012, 8.09692629949612),
    (1, 2): (2325, 265, 10.376489796867011, 8.514522169904268, 12.509095542771641),
    (1, 3): (4576, 240, 4.972308726732253, 4.0996836389497915, 5.938424475123888),
    (1, 4): (11692, 286, 2.3764770058855205, 2.0049904266248766, 2.8251907543072963),
    (2, 0): (2, 1, 1.4758198531120719, 0.9069027105912729, 2.4930222223381153),
    (2, 1): (6, 2, 1.9234525274625096, 0.963836811264423, 3.2941935391348887),
    (2, 2): (822, 38, 3.8438289554679677, 2.225049987047502, 5.756844365272118),
    (2, 3): (3226, 70, 2.063074349972182, 1.540776616158041, 2.642236031063155),
    (2, 4): (20105, 222, 1.0825740208302264, 0.8902059170186133, 1.282212235437789),
    (3, 0): (1, 0, 0.9950248756218905, 0.89647243702533, 1.1066880421038805),
    (3, 1): (1, 0, 0.9950248756218905, 0.8959004908170742, 1.11076048168895),
    (3, 2): (343, 9, 1.994549710787747, 0.7546559920919382, 3.6080426855068044),
    (3, 3): (1983, 15, 0.7657966811404386, 0.36423195145882903, 1.2375537279627793),
    (3, 4): (32891, 73, 0.22249069396484272, 0.16126187745158904, 0.29655700026424575),
    (4, 2): (78, 1, 1.0723583105346708, 0.661961724678808, 1.8003304518038368),
    (4, 3): (977, 2, 0.33664504728740613, 0.16258792765810698, 0.5418885924102207),
    (4, 4): (35255, 21, 0.06375483900441146, 0.03655725954050233, 0.09791804824100143),
    (5, 2): (11, 0, 0.947867298578199, 0.8546726336357261, 1.0640899029586952),
    (5, 3): (344, 0, 0.3676470588235294, 0.3102656408154858, 0.44935058937472366),
    (5, 4): (46593, 1, 0.006370944592751874, 0.0038672786236004326, 0.010658058866478618),
}


def _bant(deger, sinirlar):
    if deger is None:
        return None
    for i, s in enumerate(sinirlar):
        if deger < s:
            return i
    return len(sinirlar)


def _aralik_metni(i, sinirlar, birim):
    alt = None if i == 0 else sinirlar[i - 1]
    ust = None if i == len(sinirlar) else sinirlar[i]
    if alt is None:
        return f"{ust:g} {birim} altı"
    if ust is None:
        return f"{alt:g} {birim} üstü"
    return f"{alt:g}–{ust:g} {birim}"


def kat(spread=None, gorus=None):
    """Mevcut spread (°C) ve gorus (m) icin hucre bilgisi.

    Deger eksikse veya hucre tabloda yoksa None doner - uydurma yapilmaz.
    """
    a, b = _bant(spread, SPREAD_BANTLARI), _bant(gorus, GORUS_BANTLARI)
    if a is None or b is None:
        return None
    hucre = TABLO.get((a, b))
    if hucre is None:
        return None
    n, pozitif, deger, alt, ust = hucre
    return {
        "kat": deger, "alt": alt, "ust": ust, "n": n, "pozitif": pozitif,
        "ince": n < INCE_GOZLEM_SINIRI,
        "spread_araligi": _aralik_metni(a, SPREAD_BANTLARI, "°C"),
        "gorus_araligi": _aralik_metni(b, GORUS_BANTLARI, "m"),
    }
