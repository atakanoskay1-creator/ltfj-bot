"""sis_modeli.sis_iklim: ay/saat/ruzgar sayimi ve donmus tablo.

Sayfa bu sayilari "arsivden sayildi" diye gosteriyor - uydurma ya da
yanlis sayim dogrudan kullaniciya gider. Sentetik veriyle her sayim
elle dogrulanabilir; donmus tablonun ic tutarliligi ayrica kilitli."""
import runpy
from datetime import datetime, timedelta

import pytest

import ltfj_sis_iklim_tablo as T
from sis_modeli import sis_iklim as si

T0 = datetime(2020, 2, 10, 2, 0)          # yerel 05:00


def _s(dt, yon=40, hiz=5, sis=False, lvo=False, degisken=False):
    return {"yerel": dt, "yil": dt.year, "yon": yon, "hiz": hiz,
            "degisken": degisken, "sis": sis, "lvo": lvo}


# ------------------------------------------------------------ sektor
@pytest.mark.parametrize("yon,hiz,beklenen", [
    (0, 5, "K"), (22, 5, "K"), (23, 5, "KD"), (45, 5, "KD"), (90, 5, "D"),
    (180, 5, "G"), (225, 5, "GB"), (337, 5, "KB"), (338, 5, "K"),
    (225, 2, "sakin"), (None, 6, "degisken"),
])
def test_sektor(yon, hiz, beklenen):
    assert si.sektor(_s(T0, yon=yon, hiz=hiz)) == beklenen


def test_hiz_yoksa_sektor_yok():
    assert si.sektor(_s(T0, hiz=None)) is None


@pytest.mark.parametrize("yon,hiz,beklenen", [
    (140, 5, True), (250, 5, True), (139, 5, False), (251, 5, False),
    (200, 2, False),                       # sakin guneyli sayilmaz
])
def test_guneyli(yon, hiz, beklenen):
    assert si.guneyli(_s(T0, yon=yon, hiz=hiz)) is beklenen


# ------------------------------------------------------------ olaylar
def test_olay_gruplamasi_ve_suresi():
    a = [_s(T0 + timedelta(minutes=30 * i), sis=True) for i in range(4)]
    b = [_s(T0 + timedelta(hours=5), sis=True)]
    ev = si.olaylar(a + b)
    assert [len(e) for e in ev] == [4, 1]
    assert si.olay_suresi_saat(ev[0]) == 2.0     # 1.5 sa aralik + 0.5 izgara
    assert si.olay_suresi_saat(ev[1]) == 0.5


def test_bir_rapor_eksik_olay_bolunmez_iki_eksik_bolunur():
    ev = si.olaylar([_s(T0, sis=True), _s(T0 + timedelta(minutes=60), sis=True),
                     _s(T0 + timedelta(minutes=130), sis=True)])
    assert [len(e) for e in ev] == [2, 1]


# ------------------------------------------------------------ hesapla
def _veri():
    """10 gozlem Subat 05:00'te (4 sisli, KD), 10 gozlem Temmuz 15:00'te
    (sis yok, GB). Beklenenler elle hesaplanabilir."""
    v = []
    for i in range(10):
        v.append(_s(datetime(2020, 2, 10 + i, 5, 0), yon=45, sis=i < 4, lvo=i < 2))
        v.append(_s(datetime(2020, 7, 10 + i, 15, 0), yon=225))
    return v


def test_ay_orani_ve_sisli_gun():
    r = si.hesapla(_veri())
    sub = r["aylar"][1]
    assert sub == {"ay": 2, "sisli_gun": 4, "lvo_gozlem": 2,
                   "oran_yuzde": 40.0, "pay_yuzde": 100.0}
    assert r["aylar"][6]["oran_yuzde"] == 0.0 and r["aylar"][6]["sisli_gun"] == 0


def test_saat_orani():
    r = si.hesapla(_veri())
    assert r["saatler"][5]["oran_yuzde"] == 40.0
    assert r["saatler"][15]["oran_yuzde"] == 0.0


def test_ruzgar_KATI_pay_bolu_genel_pay():
    """KD: sisin %100'u, gozlemlerin %50'si -> kat 2. GB: sisin %0'i."""
    r = {x["sektor"]: x for x in si.hesapla(_veri())["ruzgar"]}
    assert r["KD"]["sis_pay_yuzde"] == 100.0 and r["KD"]["genel_pay_yuzde"] == 50.0
    assert r["KD"]["kat"] == 2.0
    assert r["GB"]["kat"] == 0.0


def test_guneyli_olay_UZUNLUK_ve_LVO_ayrimi():
    v = [_s(T0 + timedelta(minutes=30 * i), yon=200, sis=True, lvo=True) for i in range(8)]
    v += [_s(T0 + timedelta(days=3), yon=45, sis=True)]
    r = si.hesapla(v)
    assert r["guney"]["olay"] == 1 and r["guney"]["sure_medyan_sa"] == 4.0
    assert r["guney"]["lvo_yuzde"] == 100
    assert r["diger"]["olay"] == 1 and r["diger"]["lvo_yuzde"] == 0


def test_sis_yoksa_bos_sonuc():
    assert si.hesapla([_s(T0)])["sis_gozlem"] == 0


def test_seyrek_yil_kapsam_disi():
    v = [_s(datetime(2003, 1, 1, 0, 0))] + [
        _s(datetime(2012, 1, 1) + timedelta(minutes=30 * i)) for i in range(si.ASGARI_YILLIK_KAYIT)]
    kalan, ilk, son = si.kapsama_indir(v)
    assert (ilk, son) == (2012, 2012) and len(kalan) == si.ASGARI_YILLIK_KAYIT


def test_dondur_GIDIS_DONUS(tmp_path):
    r = si.hesapla(_veri())
    yol = tmp_path / "tablo.py"
    si.dondur(r, 2020, 2020, yol)
    g = runpy.run_path(str(yol))
    assert g["AYLAR"] == r["aylar"] and g["SAATLER"] == r["saatler"]
    assert g["RUZGAR"] == r["ruzgar"] and g["GUNEY"] == r["guney"]
    assert g["SIS_GOZLEM"] == 4 and g["KAPSAM_ILK_YIL"] == 2020


# ------------------------------------------------ donmus tablo tutarliligi
def test_donmus_tablo_TAM():
    assert [a["ay"] for a in T.AYLAR] == list(range(1, 13))
    assert [s["saat"] for s in T.SAATLER] == list(range(24))
    assert T.SIS_GOZLEM > 0 and T.GOZLEM > T.SIS_GOZLEM


@pytest.mark.parametrize("liste,alan", [("AYLAR", "pay_yuzde"), ("SAATLER", "pay_yuzde"),
                                        ("RUZGAR", "sis_pay_yuzde")])
def test_donmus_paylar_YUZE_YAKIN(liste, alan):
    # yuvarlama + RUZGAR'da VRB haric -> tam 100 olmayabilir
    assert 99.0 <= sum(x[alan] for x in getattr(T, liste)) <= 100.6


def test_donmus_lvo_toplami_tutarli():
    assert sum(a["lvo_gozlem"] for a in T.AYLAR) == T.LVO_GOZLEM
