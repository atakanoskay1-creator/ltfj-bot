"""sis_modeli/sis_egilimi.py - sayimlarin tanimi (sentetik veri, gercek
arsiv okunmaz)."""
from sis_modeli import sis_egilimi as e


def _m(zaman, saat, gorus="9999", spread="5", ruzgar="10", hava="", sis="0", lvo="0"):
    return {"zaman": zaman, "saat": str(saat), "gorus": gorus, "spread": spread,
            "ruzgar_hiz": ruzgar, "hava": hava, "sis": sis, "lvo": lvo}


def test_gece_tanimi():
    assert [s for s in range(24) if e.gece_mi(s)] == [0, 1, 2, 3, 4, 5, 6, 20, 21, 22, 23]


def test_ltfj_yillik_gun_ve_elverisli_sayimi():
    satirlar = [
        # ayni gun iki sisli satir -> TEK sisli gun; biri LVO
        _m("2015-01-10T03:20", 3, gorus="400", spread="0", ruzgar="2",
           hava="FG", sis="1", lvo="1"),
        _m("2015-01-10T03:50", 3, gorus="800", spread="1", ruzgar="4", hava="FG", sis="1"),
        # elverisli ama sis yok (pus)
        _m("2015-01-11T22:20", 22, gorus="3000", spread="1", ruzgar="3", hava="BR"),
        # gunduz - elverisli sayilmaz
        _m("2015-01-11T12:20", 12, gorus="900", spread="0", ruzgar="2"),
        # ruzgar fazla - elverisli sayilmaz
        _m("2015-01-12T02:20", 2, spread="0", ruzgar="5"),
        _m("2016-02-01T02:20", 2, gorus="", spread="", ruzgar=""),
    ]
    sonuc = e.ltfj_yillik(satirlar)
    assert sonuc["2015"] == {"n": 5, "sisli_gun": 1, "lvo_gun": 1, "g1000": 3,
                             "g5000": 4, "br": 1, "elverisli": 3,
                             "elverisli_sis_yuzde": 66.7}
    assert sonuc["2016"]["elverisli"] == 0 and sonuc["2016"]["elverisli_sis_yuzde"] is None


def test_era5_yillik_yalnizca_sis_mevsimi_geceleri():
    def r(zaman, rh, ruzgar):
        return {"zaman": zaman, "relative_humidity_2m": rh, "wind_speed_10m": ruzgar}
    satirlar = [
        r("2010-01-05T02:00", "96", "5"),    # sayilir, sakin
        r("2010-01-05T03:00", "95", "9"),    # sayilir, ruzgarli
        r("2010-01-05T04:00", "80", "2"),    # sayilir, nem dusuk
        r("2010-01-05T12:00", "99", "1"),    # gunduz - sayilmaz
        r("2010-07-05T02:00", "99", "1"),    # yaz - sayilmaz
        r("2010-01-06T02:00", "", "1"),      # bos nem - sayilmaz
    ]
    assert e.era5_yillik(satirlar) == {"2010": {"n": 3, "ort_rh": 90.3,
                                                "rh95": 2, "rh95_sakin": 1}}
