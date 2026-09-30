import pytest
import ltfj_bot as b

def test_notam_zaman_damgasi_iso_z():
    assert b._notam_zaman_damgasi("2026-10-01T05:30:00Z") == "01.10 05:30Z (08:30 yerel)"

def test_notam_zaman_damgasi_gece_yarisi():
    assert b._notam_zaman_damgasi("2026-10-01T22:15:00+00:00") == "01.10 22:15Z (01:15 yerel)"

@pytest.mark.parametrize("girdi", [None, "", "tarih-degil"])
def test_notam_zaman_damgasi_gecersiz(girdi):
    assert b._notam_zaman_damgasi(girdi) == ""
