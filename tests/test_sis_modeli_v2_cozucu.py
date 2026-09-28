"""v2_cozucu: sonumlu Newton - §15 cozucu duzeltmesinin kilitleri.

Kilitlenen invariant'lar:
  1) sabitler (YAKINSAMA, MAKS_ITER, ASGARI_ADIM) sonuclara bakilmadan
     belirlenen degerlerde;
  2) kabul edilen HER adimda cezali amac fonksiyonu kotulesmez;
  3) eski IRLS'in duzgun yakinsadigi referans fit'lerde ayni optimum;
  4) V1 benchmark'inin duzeltme oncesi calismasinda Yakinsamadi veren
     dort fit (lambda 0,1 / 1 / 10 / 100) artik yakinsar;
  5) gercekten basarisiz fit yine TekilSistem / Yakinsamadi'ya duser.
"""
import math
from datetime import datetime

import pytest

from sis_modeli import bolme, hedef, model, v2_cozucu, v2_evren
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku
from sis_modeli.v1_benchmark import ALANLAR


def test_sabitler_kilitli():
    assert v2_cozucu.YAKINSAMA == 1e-7
    assert v2_cozucu.AZALIM_GORELI == 1e-12
    assert v2_cozucu.MAKS_ITER == 100
    assert v2_cozucu.ASGARI_ADIM == 2.0 ** -30


def _sentetik(tohum=0, n_desen=60):
    import random
    r = random.Random(tohum)
    d, t, p = [], [], []
    for _ in range(n_desen):
        x = (r.uniform(-2, 2), r.uniform(-1, 1), r.choice([-0.5, 0.0, 0.5]))
        n = r.randint(20, 400)
        eta = -4 + 1.2 * x[0] + 0.6 * x[1] - 0.3 * x[2]
        pr = 1 / (1 + math.exp(-eta))
        k = sum(1 for _ in range(n) if r.random() < pr)
        d.append(x), t.append(n), p.append(k)
    return d, t, p


@pytest.mark.parametrize("l2", [0.1, 1.0, 10.0, 100.0])
def test_amac_kabul_edilen_hic_bir_adimda_kotulesmez(l2):
    d, t, p = _sentetik()
    iz = []
    v2_cozucu.egit(d, t, p, l2=l2, iz=iz)
    amaclar = [x["amac"] for x in iz]
    assert all(b <= a for a, b in zip(amaclar, amaclar[1:]))
    assert len(iz) >= 2


def test_sentetikte_eski_IRLS_ile_ayni_optimum():
    d, t, p = _sentetik(tohum=3)
    for l2 in (0.1, 1.0, 100.0):
        eski = model.egit(d, t, p, l2=l2)
        yeni = v2_cozucu.egit(d, t, p, l2=l2)
        assert max(abs(a - b) for a, b in zip(eski, yeni)) < 1e-6


def test_deterministik():
    d, t, p = _sentetik(tohum=5)
    assert v2_cozucu.egit(d, t, p, l2=1.0) == v2_cozucu.egit(d, t, p, l2=1.0)


def test_ayrisma_cezasizsa_basarisiz():
    """l2 = 0 ve tam ayrisma: sonlu optimum yok. Katsayilar buyudukce
    agirliklar sifira gider; cozucu Yakinsamadi ya da TekilSistem ile durur,
    sessizce katsayi dondurmez."""
    d = [(-1.0,), (-0.5,), (0.5,), (1.0,)]
    t = [50, 50, 50, 50]
    p = [0, 0, 50, 50]
    with pytest.raises((model.Yakinsamadi, model.TekilSistem)):
        v2_cozucu.egit(d, t, p, l2=0.0)


def test_maks_iter_asilirsa_yakinsamadi(monkeypatch):
    d, t, p = _sentetik(tohum=7)
    monkeypatch.setattr(v2_cozucu, "MAKS_ITER", 1)
    with pytest.raises(model.Yakinsamadi):
        v2_cozucu.egit(d, t, p, l2=1.0)


def test_tekil_hessian_TekilSistem():
    """l2 = 0 ve hep sifir bir sutun: Hessian tekil -> TekilSistem."""
    d = [(0.3, 0.0), (-0.2, 0.0), (0.1, 0.0)]
    with pytest.raises(model.TekilSistem):
        v2_cozucu.egit(d, [100, 100, 100], [5, 3, 4], l2=0.0)


def test_bos_girdi():
    assert v2_cozucu.egit([], [], [], l2=1.0) == [0.0]


# ------------------------------------------------ gercek veri (arsiv) ---
@pytest.fixture(scope="module")
def onset():
    if not VARSAYILAN_VERI.exists():
        pytest.skip("arsiv yok")
    return hedef.onset_adaylari(v2_evren.gelistirme_kayitlari(veri_oku(VARSAYILAN_VERI)))


def _desenler(onset, yil):
    E = bolme.embargo_penceresi([r for r in onset if r["dt"].year < yil], yil)
    tab = model.woe_tablolari(E, ALANLAR)
    return model.desenlere_topla(E, tab)


# Duzeltme oncesi calismada eski IRLS'in Yakinsamadi verdigi fit'ler
# (V2_V1_BENCHMARK_RAPORU.md): (ic blok yili, lambda)
SORUNLU = ((2016, 0.1), (2016, 1.0), (2019, 10.0), (2022, 100.0))
# Eski IRLS'in yakinsadigi referans fit'ler
REFERANS = ((2014, 0.1), (2016, 100.0), (2019, 100.0), (2022, 1000.0))


def test_sorunlu_fitler_eski_IRLS_iraksar_yeni_cozucu_yakinsar(onset):
    for yil, l2 in SORUNLU:
        d, t, p = _desenler(onset, yil)
        with pytest.raises(model.Yakinsamadi):
            model.egit(d, t, p, l2=l2)
        iz = []
        beta = v2_cozucu.egit(d, t, p, l2=l2, iz=iz)
        assert all(math.isfinite(b) for b in beta)
        assert -8 < beta[0] < -2                      # olagan olcek (taban ~%0,7)
        assert max(abs(b) for b in beta[1:]) < 5
        amaclar = [x["amac"] for x in iz]
        assert all(b <= a for a, b in zip(amaclar, amaclar[1:]))


def test_referans_fitlerde_eski_IRLS_ile_ayni_optimum(onset):
    for yil, l2 in REFERANS:
        d, t, p = _desenler(onset, yil)
        eski = model.egit(d, t, p, l2=l2)
        yeni = v2_cozucu.egit(d, t, p, l2=l2)
        assert max(abs(a - b) for a, b in zip(eski, yeni)) < 1e-5, (yil, l2)
