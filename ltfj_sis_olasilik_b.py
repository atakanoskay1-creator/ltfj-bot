#!/usr/bin/env python3
"""DONDURULMUS gorussuz sis olusum modeli (Model B) - calisma ani tarafi.

Bu modul sis_modeli/ alt projesinde egitilmis IKINCI lojistik regresyonun
SONUCUNU tasir - "Model A" (ltfj_sis_olasilik) ile AYNI hedefi (onumuzdeki
3 saatte gorus < 1000 m) tahmin eder ama GORUS'U (ve turevlerini) HIC
GORMEDEN, sadece atmosferik degiskenlerle (spread, sicaklik, ruzgar, saat).

NEDEN AYRI BIR MODUL, NEDEN A'YA KARISTIRILMADI: sis_modeli/ab_karsilastirma.py
ile olculdu - B'nin ham olasiligini A'ya 6. ozellik olarak eklemek (stacking)
A'nin walk-forward AP'sini DEGISTIRMIYOR (0.210->0.209). Ama AYNI iki BAGIMSIZ
donemde (holdout VE gelisme donemi walk-forward disi-katlanmis) A COK DUSUK
dedigi bantlarda (< %2) B'nin KENDI ic sirlamasi (tertil) gercek, buyuk
orneklemli ve gun-bazli CI ile dogrulanmis bir ayrim tasiyor (orn. %0-1
bandinda B dusuk->orta->yuksek: %0.03->%0.05->%0.37, CI'lar ortusmuyor).
Yani B'nin degeri bir "daha iyi tek sayi" degil, A zaten sakin derken
ikincil bir INCE AYIRT edicidir - o yuzden ayri, kucuk bir gosterge olarak
tutuluyor (bkz. sis_modeli/README.md, "A ≥%5 derinlemesine" ve
"Model A vs Model B" bolumleri).

NE YAPMAZ: A'nin (%2 ve uzerinde) YERINE GECMEZ - o bantlarda A/B arasinda
istatistiksel olarak anlamli bir fark BULUNAMADI (CI'lar ortusuyor, yon
yillar arasi tutarsiz), bu yuzden `tertil()` A_UST_SINIR'in ustunde HICBIR
SEY DONMEZ. Resmi bir tahmin degildir, TAF'in yerine gecmez.

EGITIM VERISI: LTFJ METAR arsivi 2011-2023 (onset evreni, A ile AYNI
donem/satirlar - sadece A'nin ayrica kullandigi 'gorus' burada YOK).
"""

import math

SABIT_TERIM = -4.647863005548685

KATSAYILAR = {
    'ruzgar_kuzey': 0.18578640105087602,
    'saat': 0.1915706988139972,
    'sicaklik': 0.30384846988690994,
    'spread': 0.6760251556341195,
    'spread_egilim_3': 0.03388434950234361,
}

# (ust_sinir, woe) - ust_sinir None ise 've uzeri'. ruzgar_kuzey/saat/spread/
# spread_egilim_3 tablolari Model A'nInkiyle AYNI (ayni satirlar + ayni
# hedef uzerinde tek-degiskenli WoE - hangi modelde kullanildiklarindan
# bagimsizdir); sicaklik SADECE bu modelde var.
WOE_TABLOLARI = {
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
    'sicaklik': (
        (6, 1.3613432818724829),
        (9, 0.17438567729337717),
        (13, -0.13024454230837143),
        (16, -0.4554032987030389),
        (19, -0.5647794549861158),
        (22, -0.20291343925233468),
        (25, -0.3733793880496458),
        (None, -3.068633504723999),
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

HEDEF_GORUS_M = 1000
HEDEF_UFUK_SAAT = 3

# A (ltfj_sis_olasilik) bu esigin USTUNDEYSE gosterge HICBIR SEY DONMEZ -
# ab_karsilastirma.py'de A>=%5 bantlarinda B'nin katkisina dair GUVENILIR
# bir kanit BULUNAMADI (gun-bazli CI'lar ortusuyor, yon yillar arasi
# tutarsiz - bkz. sis_modeli/README.md "A ≥%5 derinlemesine").
A_UST_SINIR = 0.02

# Dondurulmus tertil sinirlari: A bandina gore B'nin HAM olasiliginin
# 33/67. yuzdelikleri (2011-2023 gelisme donemi, NIHAI - tum donemle
# egitilmis - A ve B modelleriyle olculdu). Sadece A<%2 icin tanimli.
TERTIL_SINIRLARI = (
    ((0.0, 0.01), (0.00070, 0.00327)),
    ((0.01, 0.02), (0.02305, 0.02971)),
)


def _woe(alan: str, deger) -> float:
    if deger is None:
        return 0.0
    tablo = WOE_TABLOLARI.get(alan)
    if not tablo:
        return 0.0
    for ust, woe in tablo:
        if ust is None or deger < ust:
            return woe
    return tablo[-1][1]


def olasilik(spread=None, sicaklik=None, saat=None, ruzgar_kuzey=None,
            spread_egilim_3=None) -> float | None:
    """0-1 arasi olasilik. spread yoksa None doner (A'nin gorus/spread
    kosuluyla ayni ruh - bu ikisi olmadan model taban orandan sapamaz)."""
    if spread is None:
        return None
    z = SABIT_TERIM
    for alan, deger in (("spread", spread), ("sicaklik", sicaklik),
                        ("saat", saat), ("ruzgar_kuzey", ruzgar_kuzey),
                        ("spread_egilim_3", spread_egilim_3)):
        z += KATSAYILAR[alan] * _woe(alan, deger)
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


def ruzgar_kuzey_bileseni(yon, hiz) -> float | None:
    if yon is None or hiz is None:
        return None
    return hiz * math.cos(math.radians(yon))


def tertil(a_olasilik: float | None, b_olasilik: float | None) -> str | None:
    """A COK DUSUKKEN (< A_UST_SINIR) B'nin o bant icindeki KENDI sirasina
    gore 'düşük'/'orta'/'yüksek' doner. A_UST_SINIR ve uzerinde (veya
    herhangi bir deger eksikse) None doner - orada gosterge YOK, cunku
    bu araligin disinda B'nin katkisina dair kanit bulunamadi."""
    if a_olasilik is None or b_olasilik is None or a_olasilik >= A_UST_SINIR:
        return None
    for (alt, ust), (s1, s2) in TERTIL_SINIRLARI:
        if alt <= a_olasilik < ust:
            if b_olasilik < s1:
                return "düşük"
            if b_olasilik < s2:
                return "orta"
            return "yüksek"
    return None
