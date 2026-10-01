"""sis_modeli/omerli_advek.py - KD ruzgari x spread gostergesi (sentetik veri)."""
import pytest

from sis_modeli import omerli_advek as oa


@pytest.mark.parametrize("yon,hiz,beklenen", [
    (30, 6, "K-KD 3-10 kt"), (360, 3, "K-KD 3-10 kt"), (60, 10, "K-KD 3-10 kt"),
    (40, 14, "K-KD >10 kt"), (90, 6, "diger"), (240, 8, "diger"), (30, 2, "sakin"),
])
def test_ruzgar_sinifi(yon, hiz, beklenen):
    assert oa.ruzgar_sinifi(yon, hiz) == beklenen


@pytest.mark.parametrize("satir,beklenen", [
    ({"sis": "1", "hava": "FG"}, True), ({"sis": "0", "hava": "BCFG BR"}, True),
    ({"sis": "0", "hava": "PRFG"}, True), ({"sis": "0", "hava": "BR"}, False),
    ({"sis": "0", "hava": ""}, False),
])
def test_olay_mi(satir, beklenen):
    assert oa.olay_mi(satir) is beklenen


def test_tablo_gece_olay_yokken_ve_yil_suzgeci():
    def s(zaman, yon, hiz, spread, hava="", sis="0"):
        return {"zaman": zaman, "saat": zaman[11:13], "ruzgar_yon": str(yon),
                "ruzgar_hiz": str(hiz), "spread": str(spread), "hava": hava, "sis": sis}
    satirlar = [
        s("2015-01-01T02:20", 30, 5, 1),               # KD, 03:20'de parcali sis -> poz
        s("2015-01-01T02:50", 200, 5, 0),              # diger, poz
        s("2015-01-01T03:20", 30, 5, 0, hava="BCFG"),  # olay -> sayilmaz
        s("2015-01-01T12:20", 30, 5, 1),               # gunduz -> sayilmaz
        s("2015-01-02T21:20", 30, 5, 3),               # KD, sp 2-3, olay yok -> neg
        s("2022-01-03T01:20", 30, 5, 0),               # kusurlu yil
    ]
    assert oa.tablo(satirlar) == {("2-3", "K-KD 3-10 kt"): (1, 0.0),
                                  ("<=1", "K-KD 3-10 kt"): (2, 50.0),
                                  ("<=1", "diger"): (1, 100.0)}
    haric = oa.tablo(satirlar, lambda y: y not in oa.KUSURLU_YILLAR)
    assert haric[("<=1", "K-KD 3-10 kt")] == (1, 100.0)
