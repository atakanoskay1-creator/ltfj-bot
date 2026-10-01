"""sis_modeli/qv3_model.py ve qv3_egit.py - aday degiskenler, 0/1 WoE,
L2 yedegi, ileri secim (sentetik veri, gercek arsiv okunmaz)."""
import random
from datetime import datetime, timedelta

import pytest

from sis_modeli import model, qv3_egit, qv3_model as q


def _k(dt, **alanlar):
    r = {"dt": dt, "hava": "", "ruzgar_yon": None, "ruzgar_hiz": None, "spread": None,
         "rvr_min": None, "rvr_24": None, "rvr_06": None, "tavan": None, "gorus": None}
    r.update(alanlar)
    return r


def test_aday_ekle_turetilmis_alanlar():
    t0 = datetime(2015, 1, 1, 3, 20)
    K = [_k(t0, gorus=4000),
         _k(t0 + timedelta(hours=1), hava="BCFG BR", ruzgar_yon=40, ruzgar_hiz=5, spread=0,
            rvr_min=450, rvr_24=450, tavan=100, gorus=1500),
         _k(t0 + timedelta(hours=2), hava="-SHRA", ruzgar_yon=200, ruzgar_hiz=12, spread=3)]
    q.aday_ekle(K)
    alanlar = ("parcali_sis", "br", "yagis", "kd_hafif", "kd_nemli",
               "rvr_min_d", "rvr_24_d", "rvr_06_d", "tavan_d", "gorus_egilim_1")
    assert [tuple(r[a] for a in alanlar) for r in K] == [
        (0, 0, 0, None, None, 2000, 2000, 2000, 20000, None),
        (1, 1, 0, 1, 1, 450, 450, 2000, 100, -2500),
        (0, 0, 1, 0, 0, 2000, 2000, 2000, 20000, None),
    ]


@pytest.mark.parametrize("spread,saat,gorus,hiz,beklenen", [
    (0, 3, 2000, 2, (1, 0, 0)),       # bant 0, gece, gorus<3000, sakin
    (1, 12, 5000, 5, (0, 1, 1)),      # bant 0, gunduz, orta gorus, 3-10 kt
    (2, 22, 9999, 12, (3, 5, 5)),     # bant 1, gece, gorus>=9999, >10 kt
    (3, 6, 9999, 0, (5, 8, 6)),       # bant 2
    (7, 13, 1000, 4, (6, 9, 10)),     # bant 3
    (None, 3, 2000, 2, (None, None, None)),
])
def test_etkilesim_kodlari(spread, saat, gorus, hiz, beklenen):
    r = q.etkilesim_ekle([{"spread": spread, "saat": saat, "gorus": gorus, "ruzgar_hiz": hiz}])[0]
    assert (r["spread_x_gece"], r["spread_x_gorus"], r["spread_x_ruzgar"]) == beklenen


def test_etkilesim_kategorileri_kendi_kovasinda():
    E = [{"spread_x_gece": k, "hedef": k == 1 and i % 4 == 0}
         for k in range(8) for i in range(400)]
    tablo = q.woe_tablolari(E, ["spread_x_gece"])["spread_x_gece"]
    assert len(tablo) == 8 and max(tablo, key=lambda t: t["woe"])["kova"] == 1


def test_ikili_alan_iki_kovada_kalir():
    """Esit frekansli kovalama nadir 0/1 degiskeni tek kovaya dusururdu."""
    E = ([{"parcali_sis": 1, "hedef": i % 3 == 0} for i in range(300)]
         + [{"parcali_sis": 0, "hedef": i % 50 == 0} for i in range(3000)])
    tablo = q.woe_tablolari(E, ["parcali_sis"])["parcali_sis"]
    assert [k["n"] for k in tablo] == [3000, 300]
    assert tablo[1]["woe"] > 0 > tablo[0]["woe"]


def test_yakinsamazsa_daha_guclu_l2(monkeypatch):
    denenen = []

    def egit(d, t, p, l2):
        denenen.append(l2)
        if l2 < 1000:
            raise model.Yakinsamadi("x")
        return [0.0]

    monkeypatch.setattr(model, "egit", egit)
    assert q._egit_yedekli([(0.0,)], [1], [0], 10.0) == ([0.0], 1000.0)
    assert denenen == [10.0, 100.0, 1000.0]


def _sentetik(n_yil=3, n=2500, tohum=7):
    """gorus hedefi belirliyor, saat gurultu."""
    rnd = random.Random(tohum)
    K = []
    for yil in range(2015, 2015 + n_yil):
        for i in range(n):
            gorus = rnd.choice((800, 3000, 9999))
            olasilik = {800: 0.4, 3000: 0.05, 9999: 0.002}[gorus]
            K.append({"dt": datetime(yil, 1, 1) + timedelta(minutes=30 * i),
                      "gorus": gorus, "saat": rnd.randrange(24),
                      "hedef": rnd.random() < olasilik})
    return K


def test_ileri_secim_bilgili_degiskeni_alir_gurultuyu_almaz():
    sonuc = q.ileri_secim(_sentetik(), adaylar=("gorus", "saat"))
    assert sonuc["secilen"] == ["gorus"]
    assert dict(sonuc["iv"])["gorus"] > dict(sonuc["iv"])["saat"]


def test_ileri_secim_dogrulama_yili_secilebilir():
    sonuc = q.ileri_secim(_sentetik(), adaylar=("gorus", "saat"), dogrulama_yili=2015)
    assert sonuc["secilen"] == ["gorus"]


def test_kararli_secim_her_yili_sirayla_dogrulama_yapar():
    sonuc = q.kararli_secim(_sentetik(), adaylar=("gorus", "saat"))
    assert sonuc["kosu"] == 3
    assert sonuc["secilen"] == ["gorus"]
    assert sonuc["siklik"]["gorus"] == 1.0
    assert sonuc["siklik"].get("saat", 0) < q.KARARLILIK_ESIGI


@pytest.mark.parametrize("gorus,bant", [
    (None, None), (500, 0), (1000, 1), (1999, 1), (4000, 3), (9998, 4), (9999, 5), (10000, 5),
])
def test_gorus_bandi(gorus, bant):
    assert qv3_egit.gorus_bandi(gorus) == bant


def test_gorus_iklimi_bant_oranlari():
    E = ([{"gorus": 500, "hedef": True}] * 8 + [{"gorus": 500, "hedef": False}] * 2
         + [{"gorus": 9999, "hedef": False}] * 90)
    m = qv3_egit.gorus_iklimi(E)
    assert qv3_egit.gorus_iklimi_tahmin(m, {"gorus": 700}) > 0.6
    assert qv3_egit.gorus_iklimi_tahmin(m, {"gorus": 9999}) < 0.01
    assert qv3_egit.gorus_iklimi_tahmin(m, {"gorus": 3000}) == m[1]


def test_holdout_acilmaz():
    kaynak = open("sis_modeli/qv3_egit.py", encoding="utf-8").read()
    assert "bolme.gelistirme(aday)" in kaynak and "bolme.holdout" not in kaynak
