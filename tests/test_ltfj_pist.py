"""ltfj_pist.py testleri: pist bilesenleri, RVR, renk durumu, PRS, LVTO/CAT.

Tum boundary/deger beklentileri once gercek kodun ciktisina bakilarak
(varsayimla degil) dogrulandiktan sonra buraya yazildi.
"""
import pytest

import ornekler as o
from ltfj_analiz import metar_coz
from ltfj_pist import (
    bilesenler,
    en_dusuk_rvr,
    gorus_operasyonu,
    kuyruk_asanlar,
    kuyruk_limiti,
    pist_raporu,
    pist_ruzgarlari,
    prs_askida,
    renk_durumu,
    rvr_gruplari,
    rvr_kayitlari,
    tercih_edilen_pist,
)


# --------------------------------------------------------------- bilesenler
def test_tam_bas_ruzgarinda_kuyruk_sifir_crosswind_sifir():
    bas, yan, _ = bilesenler(64.10, 15, 64.10)
    assert bas == pytest.approx(15, abs=1e-9)
    assert yan == pytest.approx(0, abs=1e-9)


def test_tam_kuyruk_ruzgarinda_bas_negatif():
    bas, yan, _ = bilesenler(244.10, 15, 64.10)
    assert bas == pytest.approx(-15, abs=1e-9)
    assert yan == pytest.approx(0, abs=1e-9)


def test_tam_yan_ruzgarinda_bas_sifir():
    bas, yan, taraf = bilesenler(64.10 + 90, 15, 64.10)
    assert bas == pytest.approx(0, abs=1e-9)
    assert yan == pytest.approx(15, abs=1e-9)


def test_bilesenler_yon_veya_hiz_yoksa_none():
    assert bilesenler(None, 10, 64.10) == (None, None, None)
    assert bilesenler(60, None, 64.10) == (None, None, None)


@pytest.mark.parametrize("yon,taraf_beklenen", [(64.10 + 30, "sağdan"), (64.10 - 30, "soldan")])
def test_yan_ruzgar_tarafi(yon, taraf_beklenen):
    _, _, taraf = bilesenler(yon, 10, 64.10)
    assert taraf == taraf_beklenen


# --------------------------------------------------------------- pist secimi
def test_tercih_edilen_pist_field_metar_fallback():
    """RMK yoksa alan METAR ruzgarina dusuluyor. 06L ve 06R AYNI eksende
    (64.10) oldugundan alan-ruzgari senaryosunda skorlari esit olur; kod
    TERCIHLI_PISTLER tuple sirasina gore (06L,24R,06R,24L) ilk gorduguyle
    esitligi bozuyor - bu test o emergent davranisi sabitliyor."""
    d = metar_coz(o.NORMAL)  # 060/10, RMK yok
    assert tercih_edilen_pist(d, o.NORMAL) == "06L"


def test_tercih_edilen_pist_kuvvetli_kuyruk_senaryosu():
    metin = "METAR LTFJ 161250Z 24025KT 9999 SCT025 18/12 Q1015 NOSIG"
    d = metar_coz(metin)
    assert tercih_edilen_pist(d, metin) == "24R"


def test_tercih_edilen_pist_rmk_varsa_rmk_kullanilir():
    d = metar_coz(o.PIST_RUZGARI_RMK)
    secim = tercih_edilen_pist(d, o.PIST_RUZGARI_RMK)
    assert secim in ("06R", "24L", "24R")  # RMK'da bildirilen pistlerden biri


def test_kuyruk_asanlar_normal_ruzgarda_bos():
    d = metar_coz(o.NORMAL)
    assert kuyruk_asanlar(d, o.NORMAL) == []


def test_kuyruk_asanlar_kuvvetli_kuyrukta_dolar():
    metin = "METAR LTFJ 161250Z 24025KT 9999 SCT025 18/12 Q1015 NOSIG"
    d = metar_coz(metin)
    # 244 yonunden 25kt ruzgar -> 06L/06R pistlerinde ~25kt kuyruk, kuru limit
    # 10kt'yi asiyor.
    assert kuyruk_asanlar(d, metin) == ["06L", "06R"]


# ------------------------------------------------------------ kuyruk_limiti
def test_kuyruk_limiti_yagis_varsa_islak_5kt():
    d = metar_coz(o.YAGMUR)
    limit, gerekce = kuyruk_limiti(d)
    assert limit == 5 and "ıslak" in gerekce


def test_kuyruk_limiti_yagis_yoksa_kuru_10kt():
    d = metar_coz(o.NORMAL)
    limit, gerekce = kuyruk_limiti(d)
    assert limit == 10 and "kuru" in gerekce


# ------------------------------------------------------------------ RMK yok
def test_pist_ruzgarlari_rmk_yoksa_bos_liste():
    assert pist_ruzgarlari(o.NORMAL) == []


def test_pist_ruzgarlari_rmk_varsa_parse_edilir():
    kayitlar = pist_ruzgarlari(o.PIST_RUZGARI_RMK)
    pistler = {k["pist"] for k in kayitlar}
    assert pistler == {"24R", "06R", "24L"}


# --------------------------------------------------------------- pist_raporu
def test_pist_raporu_golden_alan_ruzgari():
    """_pist_ruzgar_kaynagi() yardimcisina refactor edilmeden ONCEKI
    pist_raporu() ciktisiyla birebir karsilastirilarak dogrulandi (git
    stash ile once/sonra diff alindi, fark yoktu). Bu test o davranisi
    kalici olarak sabitliyor."""
    d = metar_coz(o.NORMAL)  # 060/10, RMK yok -> alan ruzgarina dusuluyor
    assert pist_raporu(d, o.NORMAL) == [
        "06L: baş 10 kt, yan 1 kt soldan",
        "06R: baş 10 kt, yan 1 kt soldan",
        "24L: KUYRUK 10 kt, yan 1 kt sağdan",
        "24R: KUYRUK 10 kt, yan 1 kt sağdan",
        "(alan rüzgârından; kuyruk limiti 10 kt — kuru pist)",
    ]


def test_pist_raporu_golden_rmk_anemometreleri():
    d = metar_coz(o.PIST_RUZGARI_RMK)
    assert pist_raporu(d, o.PIST_RUZGARI_RMK) == [
        "06R: baş 4 kt, yan 6 kt soldan",
        "24L: KUYRUK 5 kt, yan 3 kt sağdan",
        "24R: KUYRUK 3 kt, yan 6 kt sağdan",
        "(AD 2.15 anemometreleri; kuyruk limiti 5 kt — ıslak/kirli pist varsayımı)",
    ]


def test_pist_raporu_golden_kuyruk_limit_asimi_isaretlenir():
    d = metar_coz(o.FIRTINA)
    satirlar = pist_raporu(d, o.FIRTINA)
    assert any("PRS limiti" in s and "aşıldı" in s for s in satirlar)


def test_pist_raporu_degisken_ruzgarda_bilesen_hesaplanamaz_mesaji():
    d = metar_coz(o.DEGISKEN_RUZGAR)
    satirlar = pist_raporu(d, o.DEGISKEN_RUZGAR)
    assert all("bileşen hesaplanamıyor" in s for s in satirlar[:4])


# ------------------------------------------------------------------- RVR
def test_rvr_kayitlari_tekli():
    kayitlar = rvr_kayitlari(o.RVR_TEK)
    assert kayitlar == [{"pist": "06R", "deger": 550, "on_ek": "", "ust": None, "egilim": "N"}]


def test_rvr_kayitlari_p_m_onekleri():
    kayitlar = rvr_kayitlari(o.RVR_PM)
    onekler = {k["pist"]: k["on_ek"] for k in kayitlar}
    assert onekler == {"06R": "M", "24L": "P"}


def test_rvr_kayitlari_degisken():
    kayitlar = rvr_kayitlari(o.RVR_DEGISKEN)
    assert kayitlar[0]["ust"] == 800 and kayitlar[0]["egilim"] == "U"


def test_rvr_gruplari_metin_bicimi():
    assert rvr_gruplari(o.RVR_TEK) == ["06R: 550 m, sabit"]
    assert rvr_gruplari(o.RVR_DEGISKEN) == ["06R: 400 m – 800 m arası değişken, yükseliyor"]


def test_en_dusuk_rvr_rvr_yoksa_none():
    assert en_dusuk_rvr(o.NORMAL) is None


def test_en_dusuk_rvr_birden_fazla_pistin_minimumu():
    assert en_dusuk_rvr(o.RVR_PM) == 350  # min(350, 2000)


# ------------------------------------------------------------- LVTO / CAT
@pytest.mark.parametrize("rvr_deger,lvto_beklenir,cat1_beklenir", [
    (399, True, True), (400, False, True), (401, False, True),
    (549, False, True), (550, False, False), (551, False, False),
])
def test_gorus_operasyonu_rvr_siniri(rvr_deger, lvto_beklenir, cat1_beklenir):
    metin = f"METAR LTFJ 161250Z 06005KT 9999 R06R/{rvr_deger:04d}N FEW030 18/12 Q1015"
    d = metar_coz(metin)
    notlar = gorus_operasyonu(d, metin)
    assert any("LVTO" in n for n in notlar) == lvto_beklenir
    assert any("CAT I" in n for n in notlar) == cat1_beklenir


def test_gorus_operasyonu_rvr_yoksa_gorus_kullanilir():
    metin = "METAR LTFJ 161250Z 06005KT 0300 FG VV001 05/05 Q1020"
    d = metar_coz(metin)
    notlar = gorus_operasyonu(d, metin)
    assert any("CAT I" in n for n in notlar)  # 300m < 550 tipik esik


# ------------------------------------------------------------------- PRS
def test_prs_askida_firtinada_birden_fazla_sebep():
    d = metar_coz(o.FIRTINA)
    sebepler = prs_askida(d, o.FIRTINA)
    assert "gök gürültülü fırtına" in sebepler
    assert "şiddetli yağış" in sebepler


def test_prs_askida_ruzgar_kesmesinde():
    d = metar_coz(o.RUZGAR_KESMESI)
    sebepler = prs_askida(d, o.RUZGAR_KESMESI)
    assert any("rüzgâr kesmesi" in s for s in sebepler)


def test_prs_askida_normalde_bos():
    d = metar_coz(o.NORMAL)
    assert prs_askida(d, o.NORMAL) == []


# --------------------------------------------------------------- renk durumu
@pytest.mark.parametrize("tavan,gorus,beklenen_kod", [
    (2500, 8000, "BLU"), (2499, 8000, "WHT"), (2500, 7999, "WHT"),
    (1500, 5000, "WHT"), (1499, 5000, "GRN"),
    (700, 3700, "GRN"), (699, 3700, "YLO"),
    (300, 1600, "YLO"), (299, 1600, "AMB"),
    (200, 800, "AMB"), (199, 799, "RED"),
])
def test_renk_durumu_bant_sinirlari(tavan, gorus, beklenen_kod):
    kod, _ = renk_durumu({"tavan": tavan, "gorus": gorus})
    assert kod == beklenen_kod


def test_renk_durumu_tavan_yoksa_sinirsiz_sayilir():
    """EDGE CASE (rapor D bolumu): tavan=None -> kod tavani 99999 kabul
    ediyor, yani sadece gorus bandi belirleyici oluyor. Mevcut davranisi
    belgeliyoruz."""
    kod, _ = renk_durumu({"tavan": None, "gorus": 9000})
    assert kod == "BLU"


def test_renk_durumu_ikisi_de_yoksa_none():
    assert renk_durumu({"tavan": None, "gorus": None}) is None
