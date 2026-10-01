"""sis_modeli/sis_oncul.py - gorusu dusuren neden ve 3 saatlik sis olasiligi."""
from datetime import datetime, timedelta

import pytest

from sis_modeli import sis_oncul as so


@pytest.mark.parametrize("hava,beklenen", [
    ("BCFG BR", "parcali sis"), ("PRFG", "parcali sis"), ("-RA BR", "yagis"),
    ("-SHRA", "yagis"), ("BR", "yalniz BR"), ("HZ", "HZ/FU/DU"), ("", "kod yok"),
])
def test_neden(hava, beklenen):
    assert so.neden(hava) == beklenen


def test_gelecekte_sis_ufuk_ucu_dahil():
    t0 = datetime(2015, 1, 1, 3, 20)
    z = [t0 + timedelta(minutes=30 * i) for i in range(8)]
    sis = [False] * 6 + [True, False]                     # 06:20'de sis
    assert so.gelecekte_sis(z, sis) == [True, True, True, True, True, True, False, False]


def test_tablo_ayni_bantta_nedene_gore():
    def s(saat, gorus, hava, sis="0"):
        return {"zaman": f"2015-01-01T{saat}", "gorus": gorus, "hava": hava, "sis": sis}
    satirlar = [s("03:20", "2000", "BCFG"), s("03:50", "2000", "BR"),
                s("04:20", "500", "FG", "1"), s("09:20", "2500", "BR"), s("09:50", "9999", "")]
    assert so.tablo(satirlar) == {("1000-2999", "parcali sis"): (1, 100.0),
                                  ("1000-2999", "yalniz BR"): (2, 50.0)}
