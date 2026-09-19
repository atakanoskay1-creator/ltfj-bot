#!/usr/bin/env python3
"""DONDURULMUS istatistiksel sis olasiligi modeli - calisma ani tarafi.

Bu modul sis_modeli/ alt projesinde egitilmis lojistik regresyonun SONUCUNU
tasir: katsayilar + WoE tablolari (saf statik veri) ve saf aritmetikten
ibaret bir puanlayici. Calisma aninda scikit-learn/numpy GEREKMEZ.

IZOLASYON: bot sis_modeli/'ni import ETMEZ (bkz. sis_modeli/README.md).
Alt proje bir egitim laboratuvaridir; buraya yalnizca DONDURULMUS CIKTI
tasinir. Katsayilari guncellemek icin sis_modeli yeniden egitilip bu
dosyadaki sayilar yenilenir.

NE YAPAR: "su an sis yokken, onumuzdeki 3 saat icinde gorusun 1000 m'nin
altina dusme olasiligi" tahmini uretir.

NE YAPMAZ: operasyonel karar vermez, resmi tahmin degildir, TAF'in yerine
gecmez ve ltfj_pist.sis_riski()'nin YERINE GECMEZ - ayri bir gostergedir.

DOGRULAMA (bkz. PR #31, #32):
  - Yuruyen pencere (2015-2023): AP 0.210, iklime gore BSS 0.119
  - Nihai holdout (2024-2026, hic gorulmemis): AP 0.184, BSS 0.092
  - Karsilastirma (holdout): sureklilik AP 0.132, iklim 0.013
  - Kalibrasyon yuksek ucta temkinli: %35 dendiginde gerceklesme %63
  - Guven araliklari ortusuyor; kanit iki degerlendirmenin tutarliligindan
    geliyor, tek bir olcumden degil.

EGITIM VERISI: LTFJ METAR arsivi 2011-2023 (IEM ASOS), onset evreni.
"""

import math

SABIT_TERIM = -4.653635228753809

KATSAYILAR = {
    'gorus': 0.6139640243075414,
    'ruzgar_kuzey': 0.21241872305705586,
    'saat': 0.2434175089161382,
    'spread': 0.470302867198085,
    'spread_egilim_3': 0.03795451293532045,
}

# (ust_sinir, woe) - ust_sinir None ise 've uzeri'
WOE_TABLOLARI = {
    'gorus': (
        (1600, 4.59383696023939),
        (2200, 3.689063062886815),
        (2800, 3.2406797818712354),
        (3400, 2.489302915314483),
        (4000, 2.163566003423147),
        (4600, 1.7965968830489876),
        (6000, 1.3971762500026284),
        (9000, 0.783173123389669),
        (9999, 0.05803473107456074),
        (10000, -1.0959219437307177),
        (None, -1.14151088134398),
    ),
    'ruzgar_kuzey': (
        (-3.939231012048832, -2.4507899317817095),
        (-0.520944533000791, -1.0797336019986807),
        (2.5711504387461575, 0.3038314334345849),
        (4.698463103929543, 0.7171307659083498),
        (6.894399988070802, 0.34423099382225714),
        (8.660254037844387, -0.06982147747959891),
        (11.276311449430901, -0.37198679549826663),
        (None, 0.13362283092332836),
    ),
    'saat': (
        (3, 0.9751425613990721),
        (6, 0.011755491827373812),
        (9, -0.662193534900827),
        (12, -1.1744577315085742),
        (15, -1.1451101004967803),
        (18, -1.103133896567002),
        (20, -0.35394751747731173),
        (None, 0.6140205068590998),
    ),
    'spread': (
        (1, 2.2852582042100806),
        (2, 1.3566450174846298),
        (3, 0.1829008393905851),
        (5, -1.22168515168629),
        (6, -2.2398938775698785),
        (8, -2.9583768933143495),
        (11, -3.498176901313347),
        (None, -4.555227383350011),
    ),
    'spread_egilim_3': (
        (-3, -0.8113058871586248),
        (-2, -0.1501209662030458),
        (-1, 0.24963783096610628),
        (0, 0.6271245431537282),
        (1, 0.5185184156121115),
        (3, -0.7124424739435888),
        (None, -2.3253331198413365),
    ),
}

EGITIM_L2 = 1000.0
EGITIM_AN_SAYISI = 224825
EGITIM_POZITIF = 1702

# Egitim verisindeki uzun donem taban oran (~%0.76) - ciplak bir yuzdenin
# "yuksek mi dusuk mu" oldugunu anlamak icin baglam saglar (bkz. ltfj_sayfa
# _sis_olasiligi_html - "normalden kac kat" karsilastirmasi bunun uzerinden
# hesaplanir, aynen ltfj_tavan_tablosu'ndaki "kat" mantigi gibi).
TABAN_ORAN = EGITIM_POZITIF / EGITIM_AN_SAYISI

# Model bu esigin altina dusme olasiligini tahmin eder (ICAO sis tanimi).
HEDEF_GORUS_M = 1000
HEDEF_UFUK_SAAT = 3


def _woe(alan: str, deger) -> float:
    """Ham degeri ait oldugu kovanin WoE'sine cevirir.

    Deger yoksa 0.0 doner - yani 'bilgi yok, taban orandan sapma yok'.
    Ozellikle spread_egilim_3 ilk calistirmalarda eksik olabilir (gecmiste
    cig noktasi birikmemisse); olculdu, etkisi ihmal edilebilir (holdout
    AP degismiyor, en buyuk tahmin farki 0.58 puan)."""
    if deger is None:
        return 0.0
    tablo = WOE_TABLOLARI.get(alan)
    if not tablo:
        return 0.0
    for ust, woe in tablo:
        if ust is None or deger < ust:
            return woe
    return tablo[-1][1]


def olasilik(spread=None, gorus=None, saat=None, ruzgar_kuzey=None,
             spread_egilim_3=None) -> float | None:
    """0-1 arasi olasilik. Spread veya gorus yoksa None doner - bu ikisi
    olmadan anlamli bir tahmin uretilemez (ablasyonda gorus tek basina
    AP'nin %80'ini tasiyordu)."""
    if spread is None or gorus is None:
        return None
    z = SABIT_TERIM
    for alan, deger in (("spread", spread), ("gorus", gorus), ("saat", saat),
                        ("ruzgar_kuzey", ruzgar_kuzey),
                        ("spread_egilim_3", spread_egilim_3)):
        z += KATSAYILAR[alan] * _woe(alan, deger)
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


def ruzgar_kuzey_bileseni(yon, hiz) -> float | None:
    """Ruzgar yonu daireseldir (350 ile 010 arasi 340 degil 20); model ham
    dereceyi degil kuzey bilesenini kullanir."""
    if yon is None or hiz is None:
        return None
    return hiz * math.cos(math.radians(yon))
