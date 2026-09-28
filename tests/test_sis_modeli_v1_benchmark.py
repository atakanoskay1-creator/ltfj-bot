"""v1_benchmark: protokol 1.0 §5-§6 prosedurunun kilitleri.

Bu testler benchmark sonuclari GORULMEDEN yazildi; prosedurun protokolden
sapmamasini (L2 esitlik kurali, ic bloklar, ambargo, havuzlama, olay
yakalama) garanti eder."""
from datetime import datetime, timedelta

import pytest

from sis_modeli import model
from sis_modeli import v1_benchmark as b


def test_ic_bloklar_en_az_uc_yil_sonra_baslar():
    assert b.ic_bloklar(2017) == [2014, 2015, 2016]
    assert b.ic_bloklar(2015) == [2014]
    assert b.ic_bloklar(2025) == list(range(2014, 2025))


def test_l2_sec_en_kucuk_LL():
    assert b.l2_sec({0.1: 0.05, 1.0: 0.04, 10.0: 0.045}) == 1.0


def test_l2_sec_tolerans_icindekilerden_EN_BUYUGU():
    ll = {0.1: 0.04000, 1.0: 0.04005, 10.0: 0.04010, 100.0: 0.04011}
    # en iyi 0.04000; 10 (fark 1e-4) esit, 100 (fark 1.1e-4) degil
    assert b.l2_sec(ll) == 10.0


def test_l2_sec_elenenleri_atlar_ve_hic_yoksa_basarisiz():
    assert b.l2_sec({0.1: None, 1.0: 0.05, 10.0: None}) == 1.0
    with pytest.raises(b.SpesifikasyonBasarisiz):
        b.l2_sec({0.1: None, 1.0: None})


def test_tolerans_ve_izgara_protokolle_ayni():
    assert b.ESITLIK_TOLERANSI == 1e-4
    assert model.L2_ADAYLARI == (0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0)
    assert b.BIRINCIL_FOLDLAR == ((2017, 2018), (2019, 2020), (2021, 2022),
                                  (2023, 2024), (2025, 2026))
    assert b.ALANLAR == ["spread", "spread_egilim_3", "saat", "ruzgar_kuzey", "gorus"]


def test_bant_esigi_dondurulmus_V1_taban_oraninin_5_kati():
    assert b.BANT_ESIGI == pytest.approx(5 * 1702 / 224825)


def test_olcutler_havuz_fold_ortalamasi_degil():
    """Havuzlanmis LL, satir sayisiyla agirlikli birlesimdir."""
    a = b.olcutler([0.5] * 2, [True, False], [0.5] * 2)
    c = b.olcutler([0.1] * 8, [False] * 8, [0.5] * 8)
    h = b.olcutler([0.5] * 2 + [0.1] * 8, [True, False] + [False] * 8, [0.5] * 10)
    assert h["ll"] == pytest.approx((2 * a["ll"] + 8 * c["ll"]) / 10)
    assert h["ll"] != pytest.approx((a["ll"] + c["ll"]) / 2)
    assert h["lss"] == pytest.approx(1 - h["ll"] / h["ll_iklim"])


def test_olay_yakalama_penceresi_ve_sure():
    t0 = datetime(2020, 1, 1, 6, 20)
    olay = [{"baslangic": t0, "bitis": t0}]
    tz = {t0 - timedelta(minutes=180): 0.5,     # pencere siniri: dahil
          t0 - timedelta(minutes=30): 0.01,
          t0: 0.9}                               # baslangic ani: haric
    x = b.olay_yakalama(olay, tz, esik=0.04)[0]
    assert x["yakalandi"] and x["sure_dk"] == 180 and x["satir"] == 2
    tz = {t0 - timedelta(minutes=181): 0.5, t0 - timedelta(minutes=30): 0.01}
    x = b.olay_yakalama(olay, tz, esik=0.04)[0]
    assert not x["yakalandi"] and x["sure_dk"] == 0 and x["satir"] == 1
    assert b.olay_yakalama(olay, {}, esik=0.04)[0]["satir"] == 0


def _sentetik(yillar):
    """Her yil icin gunluk 2 satir; spread<=1 olanlarin bir kismi pozitif."""
    import random
    r = random.Random(0)
    out = []
    for y in yillar:
        for g in range(0, 360, 3):
            for s in (2, 14):
                dt = datetime(y, 1, 1, s, 20) + timedelta(days=g)
                sp = r.choice([0, 1, 2, 3, 5, 8])
                out.append({"dt": dt, "ay": dt.month, "saat": dt.hour, "spread": sp,
                            "spread_egilim_3": r.choice([-2, 0, 1]),
                            "ruzgar_kuzey": r.uniform(-5, 5),
                            "gorus": r.choice([2000, 6000, 9999]),
                            "hedef": sp <= 1 and r.random() < 0.3,
                            "hedef_ufuk_saat": 3})
    return out


def test_ic_dogrulama_bloklari_ambargolu_genisleyen_pencere():
    E = _sentetik(range(2011, 2017))
    ic = b.ic_dogrulama(E, 2017, adaylar=(1.0, 100.0))
    assert [x["yil"] for x in ic["bloklar"]] == [2014, 2015, 2016]
    for x in ic["bloklar"]:
        beklenen = sum(1 for r in E if r["dt"].year < x["yil"]
                       and not (datetime(x["yil"], 1, 1) - timedelta(hours=3)
                                <= r["dt"] < datetime(x["yil"], 1, 1)))
        assert x["ic_egitim"] == beklenen
        assert x["dogrulama"] == sum(1 for r in E if r["dt"].year == x["yil"])
    assert ic["secilen"] in (1.0, 100.0)
    assert set(ic["havuz_ll"]) == {1.0, 100.0}


def test_ic_dogrulama_yakinsamayan_L2_elenir(monkeypatch):
    E = _sentetik(range(2011, 2016))
    gercek_egit = model.egit

    def sahte(d, t, p, l2=1.0):
        if l2 == 0.1:
            raise model.Yakinsamadi("test")
        return gercek_egit(d, t, p, l2=l2)

    monkeypatch.setattr(model, "egit", sahte)
    ic = b.ic_dogrulama(E, 2016, adaylar=(0.1, 10.0))
    assert ic["havuz_ll"][0.1] is None and "Yakinsamadi" in ic["elenen"][0.1]
    assert ic["secilen"] == 10.0
