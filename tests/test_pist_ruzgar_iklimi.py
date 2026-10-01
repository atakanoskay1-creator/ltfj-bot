"""sis_modeli/pist_ruzgar_iklimi.py (yerel Qwen ajanı, #125)."""
import pytest

import sis_modeli.pist_ruzgar_iklimi as p

@pytest.mark.parametrize("yon,hiz,pist_yonu,beklenen", [
    (60, 10, 240, (-10.0, 0.0)),
    (330, 10, 240, (0.0, 10.0)),
    (30, 20, 244.12, (-16.56, 11.22)),
    (244.12, 8, 244.12, (8.0, 0.0)),
])
def test_pist_bilesenleri(yon, hiz, pist_yonu, beklenen):
    bas, yan = p.pist_bilesenleri(yon, hiz, pist_yonu)
    assert bas == pytest.approx(beklenen[0], abs=0.01)
    assert yan == pytest.approx(beklenen[1], abs=0.01)

@pytest.mark.parametrize("yon,hiz,beklenen", [
    (None, 2, "sakin"),
    (None, 6, "degisken"),
    (60, 10, "24_kuyruk"),
    (240, 10, "06_kuyruk"),
    (150, 10, "serbest"),
    (64, 5, "serbest"),
    (64, 6, "24_kuyruk"),
])
def test_sinif(yon, hiz, beklenen):
    assert p.sinif(yon, hiz) == beklenen

def test_ozet():
    S = [
        {"ay": "1", "ruzgar_yon": "60", "ruzgar_hiz": "10"},
        {"ay": "1", "ruzgar_yon": "240", "ruzgar_hiz": "10"},
        {"ay": "1", "ruzgar_yon": "", "ruzgar_hiz": "2"},
        {"ay": "1", "ruzgar_yon": "", "ruzgar_hiz": "7"},
        {"ay": "2", "ruzgar_yon": "150", "ruzgar_hiz": "10"},
        {"ay": "2", "ruzgar_yon": "60", "ruzgar_hiz": ""}
    ]
    
    beklenen = {
        1: {"n": 4, "sakin": 25.0, "degisken": 25.0, "24_kuyruk": 25.0, "06_kuyruk": 25.0, "serbest": 0.0},
        2: {"n": 1, "sakin": 0.0, "degisken": 0.0, "24_kuyruk": 0.0, "06_kuyruk": 0.0, "serbest": 100.0}
    }
    
    sonuc = p.ozet(S, "ay")
    assert sonuc == beklenen
