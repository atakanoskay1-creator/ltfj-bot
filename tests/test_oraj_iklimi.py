import pytest
from datetime import datetime
import sis_modeli.oraj_iklimi as o

S = [{"zaman": "2015-06-01T12:20", "ay": "6", "saat": "12", "hava": "TSRA"},
     {"zaman": "2015-06-01T12:50", "ay": "6", "saat": "12", "hava": "-TSRA"},
     {"zaman": "2015-06-02T15:20", "ay": "6", "saat": "15", "hava": "VCTS"},
     {"zaman": "2015-07-03T15:20", "ay": "7", "saat": "15", "hava": "+TSRAGR"},
     {"zaman": "2015-07-03T16:20", "ay": "7", "saat": "16", "hava": "-RA"}]

@pytest.mark.parametrize("hava,beklenen,beklenen_yakin", [
    ("TSRA", True, True),
    ("-TSRA BR", True, True),
    ("+TSRAGR", True, True),
    ("VCTS", False, True),
    ("VCTS RA", False, True),
    ("TS", True, True),
    ("-SHRA BR", False, False),
    ("", False, False),
    (None, False, False),
    ("FG", False, False),
])
def test_oraj_mi(hava, beklenen, beklenen_yakin):
    assert o.oraj_mi(hava) == beklenen
    assert o.oraj_mi(hava, yakin_dahil=True) == beklenen_yakin

def test_aylik_gun_sayisi():
    assert o.aylik_gun_sayisi(S) == {6: 1, 7: 1}

def test_saatlik_dagilim():
    assert o.saatlik_dagilim(S) == {12: 66.7, 15: 33.3}
    assert o.saatlik_dagilim([]) == {}

@pytest.mark.parametrize("zamanlar,beklenen", [
    ([datetime(2015,6,1,12,20), datetime(2015,6,1,12,50), datetime(2015,6,1,13,20), datetime(2015,6,1,15,0), datetime(2015,6,2,9,0)], [60, 0, 0]),
    ([datetime(2015,6,2,9,0), datetime(2015,6,1,15,0), datetime(2015,6,1,13,20), datetime(2015,6,1,12,50), datetime(2015,6,1,12,20)], [60, 0, 0]),
    ([], []),
    ([datetime(2015,6,1,12,20)], [0]),
])
def test_olay_sureleri(zamanlar, beklenen):
    assert o.olay_sureleri(zamanlar) == beklenen
