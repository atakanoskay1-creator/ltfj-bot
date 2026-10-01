"""sis_modeli/qv3_hedef.py - LVO Hazirlik hedefi (sentetik veri)."""
import pytest

import sis_modeli.qv3_hedef as h


@pytest.mark.parametrize("rvr_min,tavan,beklenen", [
    (750, None, 1), (799, 3000, 1), (800, None, 0), (1500, 3000, 0),
    (None, 100, 1), (None, 199, 1), (None, 200, 0), (None, None, 0),
])
def test_hazirlik_mi(rvr_min, tavan, beklenen):
    assert h.hazirlik_mi(rvr_min, tavan) == beklenen


def test_rvr_birlestir():
    S = [{"zaman": "2015-01-10T03:20"}, {"zaman": "2015-01-10T03:50"}, {"zaman": "2015-01-10T04:20"}]
    R = [{"zaman": "2015-01-10T03:20", "rvr_06": "", "rvr_24": "450", "rvr_min": "450"},
         {"zaman": "2015-01-10T03:50", "rvr_06": "", "rvr_24": "", "rvr_min": ""}]
    sonuc = h.rvr_birlestir(S, R)
    assert sonuc is S
    assert [(s["rvr_06"], s["rvr_24"], s["rvr_min"]) for s in S] == \
        [(None, 450, 450), (None, None, None), (None, None, None)]


def test_etiketle():
    S = [{"rvr_min": 450, "tavan": None}, {"rvr_min": None, "tavan": 100},
         {"rvr_min": 1200, "tavan": 3000}]
    assert [s["hazirlik"] for s in h.etiketle(S)] == [1, 1, 0]


def _satir(zaman, tavan=None):
    return {"zaman": zaman, "spread": 2, "qnh": 1015, "ruzgar_hiz": 5, "ruzgar_yon": 30,
            "tavan": tavan}


def test_veri_hazirla_2012_oncesi_atilir_ve_hedef_3_saat():
    S = [_satir("2011-12-31T23:50"),
         _satir("2012-01-01T00:20"), _satir("2012-01-01T00:50"),
         _satir("2012-01-01T01:20"), _satir("2012-01-01T01:50", tavan=100),
         _satir("2012-01-01T02:20"), _satir("2012-01-01T05:20")]
    R = [{"zaman": "2012-01-01T01:20", "rvr_06": "", "rvr_24": "700", "rvr_min": "700"}]
    aday = h.veri_hazirla(S, R)
    assert [(r["zaman"], r["hedef"]) for r in aday] == [
        ("2012-01-01T00:20", True), ("2012-01-01T00:50", True),
        ("2012-01-01T02:20", False), ("2012-01-01T05:20", False)]
