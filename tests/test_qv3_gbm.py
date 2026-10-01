"""sis_modeli/qv3_gbm.py - saf Python GBM (sentetik veri, gercek arsiv okunmaz)."""
import random
from datetime import datetime, timedelta

import pytest

from sis_modeli import degerlendir, qv3_gbm as G


@pytest.mark.parametrize("deger,beklenen", [
    (None, 0), (0, 1), (4.9, 1), (5, 2), (9.9, 2), (10, 3), (99, 3),
])
def test_kova_eksik_ayri_ve_esik_sag_kapali(deger, beklenen):
    assert G.kova(deger, [5, 10]) == beklenen


def test_sinirlar_tekil_ve_sirali():
    K = [{"x": v} for v in [1] * 50 + [2] * 30 + [3] * 20] + [{"x": None}] * 10
    esikler = G.sinirlar_kur(K, ["x"])["x"]
    assert esikler == sorted(set(esikler)) and set(esikler) <= {1, 2, 3}


def _etkilesim(n=6000, tohum=3):
    """Hedef yalnizca a=1 VE b=1 iken yuksek: toplamsal degil, etkilesim."""
    rnd = random.Random(tohum)
    K = []
    for i in range(n):
        a, b, c = rnd.random() < 0.5, rnd.random() < 0.5, rnd.random() < 0.5
        K.append({"dt": datetime(2015, 1, 1) + timedelta(minutes=30 * i),
                  "a": int(a), "b": int(b), "c": int(c),
                  "hedef": rnd.random() < (0.3 if a and b else 0.005)})
    return K


def test_gbm_etkilesimi_ogrenir_ve_gurultuyu_kullanmaz(monkeypatch):
    monkeypatch.setattr(G, "NEG_ORAN", 1.0)
    K = _etkilesim()
    m = G.egit(K, ["a", "b", "c"], agac_sayisi=30)
    p11 = G.olasilik(m, {"a": 1, "b": 1, "c": 0})
    p10 = G.olasilik(m, {"a": 1, "b": 0, "c": 0})
    p01 = G.olasilik(m, {"a": 0, "b": 1, "c": 0})
    assert p11 > 0.2 and p10 < 0.03 and p01 < 0.03
    onem = dict(G.onem(m))
    assert onem["a"] + onem["b"] > 0.9 and onem.get("c", 0) < 0.1


def test_negatif_orneklem_agirlikli_olasiliklari_korur():
    K = _etkilesim(n=20000)
    m = G.egit(K, ["a", "b", "c"], agac_sayisi=40)
    p = [G.olasilik(m, r) for r in K]
    gercek_oran = sum(r["hedef"] for r in K) / len(K)
    assert abs(sum(p) / len(p) - gercek_oran) < 0.01
    assert degerlendir.roc_auc(p, [bool(r["hedef"]) for r in K]) > 0.85


def test_agac_sayisi_ic_dogrulamada_secilir():
    K = _etkilesim(n=8000)
    for i, r in enumerate(K):
        r["dt"] = datetime(2015 + (i * 2) // len(K), 1, 1) + timedelta(minutes=i)
    m, n = G.egit_secerek(K, ["a", "b", "c"])
    assert n % G.KONTROL_ARALIGI == 0 and 0 < n <= G.MAKS_AGAC
    assert len(m["agaclar"]) == n


def test_holdout_acilmaz():
    kaynak = open("sis_modeli/qv3_gbm.py", encoding="utf-8").read()
    assert "bolme.gelistirme(aday)" in kaynak and "bolme.holdout" not in kaynak
