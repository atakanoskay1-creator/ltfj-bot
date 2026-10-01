#!/usr/bin/env python3
"""DONDURULMUS çok değişkenli tavan<500ft modeli - dış kaynak DESTEKLİ,
GERİ DÜŞMELİ (fallback) çalışma anı tarafı.

sis_modeli/tavan_dis_kaynak_model.py'de HOLDOUT'TA DOĞRULANDI (bkz.
sis_modeli/README.md "Çok değişkenli model" bölümü): acik_meteo_nem_2m
(Open-Meteo bağıl nem) ve komsu_tavan_ozellik (LTFM canlı tavanı) TEMEL
modele eklendiğinde holdout AP'si 0.114 → 0.136 (~%19 görece artış,
eşleştirilmiş %5–%95: +0.000 – +0.043).

İKİ KATSAYI KÜMESİ TAŞINIR:
  TEMEL  - spread, görüş, tavan_özellik, saat, rüzgâr_kuzey, sis_olasılık
           (HER ZAMAN hesaplanabilir - METAR + dondurulmuş sis modelinden
           geliyor; dış kaynak yoksa/bayatsa kullanılan GERİ DÜŞME modeli)
  GENİŞ  - TEMEL + acik_meteo_nem_2m + komsu_tavan_ozellik
           (dış kaynak TAZE ve MEVCUTSA kullanılır - bkz. ltfj_dis_kaynak_cache.py)

GERİ DÜŞME TASARIMI KASITLI: canlı tahmin ASLA dış kaynağa sert bağımlı
olmaz - ltfj_dis_kaynak_cache.oku() bayat/eksik derse (API çökmüş, hız
limiti, vs.) sessizce TEMEL'e düşer, hata vermez, tahmin üretmeyi
BIRAKMAZ.

DÜRÜST UYARI - sis_olasılık'ın GENİŞ modeldeki katsayısı NEGATİF
(-0.079, TEMEL modelde +0.093): VIF taraması sis_olasılık (14.29) ve
spread'in (11.00) güçlü kolineer olduğunu göstermişti (bkz. sis_modeli/
README.md). nem+komşu tavanı eklenince regresyon ağırlığı spread'e kayıyor,
sis_olasılık bir SUPRESÖR (düzeltici) rolüne geçiyor - tanilama.
isaret_kontrolu'nün "sağlıklı modelde her katsayı pozitiftir" kuralını
ihlal ediyor. Bu YENİ bir hata DEĞİL, bilinen bir kolinerlik semptomu;
AGREGE holdout performansı (AP/BSS) yine de gerçek ve doğrulanmış - ama
GENİŞ model TEMEL kadar temiz yorumlanamaz, aşırı/alışılmadık girdi
kombinasyonlarında sezgiye aykırı davranabilir. Şeffaflık için burada
açıkça not edildi, gizlenmedi.

İZOLASYON: bu modül sis_modeli/'ni import ETMEZ - katsayılar + WoE
tabloları saf statik veri, çalışma anında sadece `math` gerekir.

EĞİTİM VERİSİ: LTFJ METAR arşivi, rejim penceresi 2017+, geliştirme dönemi
(2024-2026 HARİÇ - ltfj_sis_olasilik.py ile AYNI disiplin, holdout
dönemine dondurma SIRASINDA bile dokunulmadı). n=120333, pozitif=1186.
"""

import math

HEDEF_TAVAN_FT = 500
HEDEF_UFUK_SAAT = 3

EGITIM_AN_SAYISI = 120333
EGITIM_POZITIF = 1186
TABAN_ORAN = EGITIM_POZITIF / EGITIM_AN_SAYISI

# --------------------------------------------------------------- TEMEL
SABIT_TERIM_TEMEL = -4.6140299800777145

KATSAYILAR_TEMEL = {
    'gorus': 0.5685551030009702,
    'ruzgar_kuzey': 0.25658868874664886,
    'saat': 0.4674646664273218,
    'sis_olasilik': 0.09329267489137186,
    'spread': 0.5834943046482444,
    'tavan_ozellik': 0.06951729838760297,
}

WOE_TABLOLARI_TEMEL = {
    'gorus': (
        (1700, 3.627080706768031),
        (2500, 2.9903001841643815),
        (3300, 2.506240502126233),
        (4100, 2.269714573578396),
        (4900, 1.9937368042584052),
        (9999, 1.162201218849612),
        (10000, -0.7393959222184785),
        (None, -1.4324566129701677),
    ),
    'ruzgar_kuzey': (
        (-3.939231012048832, -2.1849474535067643),
        (-2.9391523179536475e-15, -0.8297306204927383),
        (2.5000000000000004, 0.19122921788100541),
        (4.596266658713868, 0.5536288358651045),
        (6.5778483455013586, 0.3069667019534284),
        (8.500000000000002, 0.0969269079390655),
        (11.258330249197703, 0.018143758628034398),
        (None, 0.03674799687684029),
    ),
    'saat': (
        (3, 0.8796879533771292),
        (6, -0.11925277333405711),
        (9, -1.1502694807705747),
        (12, -1.7424697743754187),
        (15, -0.866063946389122),
        (18, -0.6127229908564079),
        (20, -0.16660039713927208),
        (None, 0.7334284296977074),
    ),
    'sis_olasilik': (
        (0.00045284662451456286, -5.705077749879151),
        (0.0007442639709085887, -5.699810719901676),
        (0.00114638595084781, -3.7636791360926396),
        (0.002039603903361573, -3.1401948862004705),
        (0.003213255851920412, -2.4078434921116316),
        (0.006255812532391672, -0.5480554292262053),
        (0.012511766365562633, 0.3472604529489709),
        (None, 1.814451524842869),
    ),
    'spread': (
        (1, 2.045243746969643),
        (2, 1.337767077258059),
        (3, 0.07147186097705004),
        (4, -1.4927405586477978),
        (6, -2.4913941086235525),
        (8, -3.5939414917343346),
        (10, -5.484980058926292),
        (None, -5.959659913866122),
    ),
    'tavan_ozellik': (
        (3000, 1.0967416641679872),
        (8000, -0.1499350072699657),
        (12000, -0.9523477240548575),
        (99999, 0.46509048608059106),
        (None, -0.2700447801177893),
    ),
}

# ---------------------------------------------------------------- GENİŞ
SABIT_TERIM_GENIS = -4.690575830995403

KATSAYILAR_GENIS = {
    'acik_meteo_nem_2m': 0.252724313523876,
    'gorus': 0.6184798163705699,
    'komsu_tavan_ozellik': 0.4496158494599322,
    'ruzgar_kuzey': 0.33502114852800047,
    'saat': 0.4957837009449184,
    'sis_olasilik': -0.07894070959692545,
    'spread': 0.594193726538002,
    'tavan_ozellik': 0.0074746550930769795,
}

WOE_TABLOLARI_GENIS = {
    'acik_meteo_nem_2m': (
        (54, -5.610581814409717),
        (63, -4.1413903193204415),
        (70, -2.187252033525863),
        (76, -1.162655257593475),
        (81, -0.5295498832017593),
        (86, -0.14782572056449786),
        (91, 0.37381107478163095),
        (None, 1.4501234621885453),
    ),
    'gorus': (
        (1700, 3.627080706768031),
        (2500, 2.9903001841643815),
        (3300, 2.506240502126233),
        (4100, 2.269714573578396),
        (4900, 1.9937368042584052),
        (9999, 1.162201218849612),
        (10000, -0.7393959222184785),
        (None, -1.4324566129701677),
    ),
    'komsu_tavan_ozellik': (
        (1000, 1.6452946215780264),
        (2200, 0.4306488801796193),
        (2300, -0.6055999760384453),
        (2500, 0.0035746088632718194),
        (3000, -1.0229412494964478),
        (8000, -2.7631907855901168),
        (10000, -1.524870027848908),
        (None, -2.3376736406483705),
    ),
    'ruzgar_kuzey': (
        (-3.939231012048832, -2.1849474535067643),
        (-2.9391523179536475e-15, -0.8297306204927383),
        (2.5000000000000004, 0.19122921788100541),
        (4.596266658713868, 0.5536288358651045),
        (6.5778483455013586, 0.3069667019534284),
        (8.500000000000002, 0.0969269079390655),
        (11.258330249197703, 0.018143758628034398),
        (None, 0.03674799687684029),
    ),
    'saat': (
        (3, 0.8796879533771292),
        (6, -0.11925277333405711),
        (9, -1.1502694807705747),
        (12, -1.7424697743754187),
        (15, -0.866063946389122),
        (18, -0.6127229908564079),
        (20, -0.16660039713927208),
        (None, 0.7334284296977074),
    ),
    'sis_olasilik': (
        (0.00045284662451456286, -5.705077749879151),
        (0.0007442639709085887, -5.699810719901676),
        (0.00114638595084781, -3.7636791360926396),
        (0.002039603903361573, -3.1401948862004705),
        (0.003213255851920412, -2.4078434921116316),
        (0.006255812532391672, -0.5480554292262053),
        (0.012511766365562633, 0.3472604529489709),
        (None, 1.814451524842869),
    ),
    'spread': (
        (1, 2.045243746969643),
        (2, 1.337767077258059),
        (3, 0.07147186097705004),
        (4, -1.4927405586477978),
        (6, -2.4913941086235525),
        (8, -3.5939414917343346),
        (10, -5.484980058926292),
        (None, -5.959659913866122),
    ),
    'tavan_ozellik': (
        (3000, 1.0967416641679872),
        (8000, -0.1499350072699657),
        (12000, -0.9523477240548575),
        (99999, 0.46509048608059106),
        (None, -0.2700447801177893),
    ),
}


def _woe(tablo: dict, alan: str, deger) -> float:
    """Ham değeri ait olduğu kovanın WoE'sine çevirir. Değer yoksa 0.0
    döner - 'bilgi yok, taban orandan sapma yok' (ltfj_sis_olasilik ile
    AYNI disiplin)."""
    if deger is None:
        return 0.0
    kovalar = tablo.get(alan)
    if not kovalar:
        return 0.0
    for ust, woe in kovalar:
        if ust is None or deger < ust:
            return woe
    return kovalar[-1][1]


def olasilik(spread=None, gorus=None, tavan_ozellik=None, saat=None,
             ruzgar_kuzey=None, sis_olasilik=None,
             acik_meteo_nem_2m=None, komsu_tavan_ozellik=None) -> float | None:
    """0-1 arası olasılık.

    TEMEL alanların (spread, görüş, tavan_özellik, saat, rüzgâr_kuzey,
    sis_olasılık) HERHANGİ BİRİ eksikse None döner - bunlar olmadan anlamlı
    bir tahmin üretilemez. acik_meteo_nem_2m ve komsu_tavan_ozellik
    OPSİYONELDİR: ikisi de doluysa GENİŞ model, değilse TEMEL model
    (fallback) kullanılır - ASLA hata vermez, sessizce daha az bilgiyle
    devam eder."""
    temel_degerler = {
        "spread": spread, "gorus": gorus, "tavan_ozellik": tavan_ozellik,
        "saat": saat, "ruzgar_kuzey": ruzgar_kuzey, "sis_olasilik": sis_olasilik,
    }
    if any(v is None for v in temel_degerler.values()):
        return None

    if acik_meteo_nem_2m is not None and komsu_tavan_ozellik is not None:
        sabit, katsayilar, tablo = SABIT_TERIM_GENIS, KATSAYILAR_GENIS, WOE_TABLOLARI_GENIS
        degerler = dict(temel_degerler, acik_meteo_nem_2m=acik_meteo_nem_2m,
                        komsu_tavan_ozellik=komsu_tavan_ozellik)
    else:
        sabit, katsayilar, tablo = SABIT_TERIM_TEMEL, KATSAYILAR_TEMEL, WOE_TABLOLARI_TEMEL
        degerler = temel_degerler

    z = sabit
    for alan, deger in degerler.items():
        z += katsayilar[alan] * _woe(tablo, alan, deger)
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
