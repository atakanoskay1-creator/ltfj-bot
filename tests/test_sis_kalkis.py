"""sis_modeli/sis_kalkis.py - gun dogumuna gore sis kalkisi (sentetik veri)."""
from datetime import datetime, timedelta

import pytest

from sis_modeli import sis_kalkis as sk


@pytest.mark.parametrize("an,alt,ust", [
    # Istanbul: 21 Haziran ~05:32, 21 Aralik ~08:25 yerel (UTC+3)
    (datetime(2024, 6, 21, 12, 0), datetime(2024, 6, 21, 2, 25), datetime(2024, 6, 21, 2, 40)),
    (datetime(2024, 12, 21, 3, 0), datetime(2024, 12, 21, 5, 18), datetime(2024, 12, 21, 5, 33)),
])
def test_gun_dogumu_utc(an, alt, ust):
    assert alt <= sk.gun_dogumu(an) <= ust


def _izgara(bas, gorusler):
    return [{"dt": bas + timedelta(minutes=30 * i), "gorus": float(g), "hava": ""}
            for i, g in enumerate(gorusler)]


def test_gun_dogumunda_suren_sisin_kalkis_gecikmesi():
    # 2024-12-21 gun dogumu ~05:25 UTC. Sis 02:20-06:50, 07:20de kalkiyor.
    satirlar = _izgara(datetime(2024, 12, 21, 1, 50),
                       [3000, 500, 400, 300, 300, 400, 500, 600, 700, 800, 900, 1500, 4000])
    olay = {"sis_bas_i": 1, "sis_son_i": 10, "yagisli": False}
    k = sk.kalkis_kayitlari(satirlar, [olay])
    assert len(k) == 1
    assert k[0]["kalkis"] == datetime(2024, 12, 21, 7, 20)
    dogum = sk.gun_dogumu(datetime(2024, 12, 21, 7, 0))
    assert k[0]["gecikme_dk"] == round((datetime(2024, 12, 21, 7, 20) - dogum).total_seconds() / 60)


def test_gun_dogumundan_once_kalkan_ve_delikli_olay_disarida():
    # gun dogumundan (~05:25) once biten sis -> evren disi
    erken = _izgara(datetime(2024, 12, 21, 0, 20), [500, 400, 400, 500, 3000])
    assert sk.kalkis_kayitlari(erken, [{"sis_bas_i": 0, "sis_son_i": 3, "yagisli": False}]) == []
    # son sis gozleminden sonra 2 saatlik delik -> kalkis olculemez
    delikli = _izgara(datetime(2024, 12, 21, 4, 20), [500, 400, 400, 500])
    delikli.append({"dt": datetime(2024, 12, 21, 7, 50), "gorus": 3000.0, "hava": ""})
    assert sk.kalkis_kayitlari(delikli, [{"sis_bas_i": 0, "sis_son_i": 3, "yagisli": False}]) == []


def test_kalkmis_payi():
    assert sk.kalkmis_payi([30, 60, 61, 150, 240]) == {1: 40.0, 2: 60.0, 3: 80.0, 4: 100.0}
    assert sk.kalkmis_payi([]) == {1: None, 2: None, 3: None, 4: None}
