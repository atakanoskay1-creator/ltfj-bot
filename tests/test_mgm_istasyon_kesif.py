"""mgm_istasyon_kesif.py - ag gerektirmeyen yardimcilar."""
import pytest

import mgm_istasyon_kesif as k


def test_mesafe_ve_yon_ltfj_omerli():
    # Omerli LTFJ'nin kuzey-kuzeydogusunda, ~17 km
    assert 15 < k.mesafe_km(k.LTFJ, k.OMERLI) < 19
    assert 10 < k.yon_derece(k.LTFJ, k.OMERLI) < 30


@pytest.mark.parametrize("kayit,beklenen", [
    ({"enlem": "41.0", "boylam": "29.4"}, (41.0, 29.4)),
    ({"lat": 41.1, "lon": 29.3}, (41.1, 29.3)),
    ({"ad": "x"}, None),
    ({"enlem": "", "boylam": "29"}, None),
])
def test_koordinatli(kayit, beklenen):
    assert k.koordinatli(kayit) == beklenen


def test_kayitlar():
    assert k.kayitlar([{"a": 1}, 3]) == [{"a": 1}]
    assert k.kayitlar({"a": 1}) == [{"a": 1}]
    assert k.kayitlar(None) == []
