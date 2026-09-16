"""Regresyon testi (rapor E.2): ltfj_analiz.PIST_YONU ve
ltfj_pist.PISTLER'daki yonler artik ltfj_ayarlar.PIST_EKSENI_06/24 TEK
kaynagindan geliyor. Bu test, birinin ileride tekrar ayri ayri hardcode
edilip digerinden sessizce sapmasini engeller."""
from ltfj_analiz import PIST_YONU
from ltfj_ayarlar import PIST_EKSENI_06, PIST_EKSENI_24
from ltfj_pist import PISTLER


def test_ltfj_analiz_pist_yonu_ortak_kaynaktan():
    assert PIST_YONU == PIST_EKSENI_06


def test_pistler_sozlugu_ortak_kaynaktan():
    assert PISTLER["06L"]["yon"] == PIST_EKSENI_06
    assert PISTLER["06R"]["yon"] == PIST_EKSENI_06
    assert PISTLER["24L"]["yon"] == PIST_EKSENI_24
    assert PISTLER["24R"]["yon"] == PIST_EKSENI_24


def test_analiz_ve_pist_modulleri_ayni_degeri_kullanir():
    assert PIST_YONU == PISTLER["06L"]["yon"] == PISTLER["06R"]["yon"]
