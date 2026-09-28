"""v2_evren: V2 gelistirme evreni - §3 izgara filtresi (Deney 0 B10).

Filtre hedef.hazirla'dan ve olay bolutlemesinden ONCE uygulanmali; izgara
disi (SPECI) kayit ne tahmin satiri ne de gelistirme olayi olmamali, ama
izgara satirlarinin Y'si degismemeli."""
from datetime import datetime, timedelta

from sis_modeli import hedef, v2_evren
from sis_modeli.olay_degerlendirme import bagimsiz_olaylar

T0 = datetime(2022, 10, 31, 20, 20)


def _k(dt, gorus=9999, sis=0):
    return {"zaman": dt.strftime("%Y-%m-%dT%H:%M"), "gorus": gorus, "spread": 3,
            "sis": sis, "hava": "", "sis_kodu": 0}


def _senaryo():
    """20:20-06:50 izgara (sis yok) + 22:56 ve 23:01 SPECI; 23:01 olay
    gozlemi (B10'daki 2022-10-31 vakasinin iskeleti)."""
    satirlar = [_k(T0 + timedelta(minutes=30 * i)) for i in range(22)]
    satirlar += [_k(datetime(2022, 10, 31, 22, 56), 3200),
                 _k(datetime(2022, 10, 31, 23, 1), 900, sis=1)]
    return satirlar


def test_izgara_disi():
    assert not v2_evren.izgara_disi(datetime(2022, 1, 1, 0, 20))
    assert not v2_evren.izgara_disi(datetime(2022, 1, 1, 0, 50))
    assert v2_evren.izgara_disi(datetime(2022, 1, 1, 23, 1))
    assert v2_evren.izgara_disi(datetime(2022, 1, 1, 8, 0))


def test_izgara_kayitlari_girdiyi_degistirmez():
    s = _senaryo()
    n = len(s)
    f = v2_evren.izgara_kayitlari(s)
    assert len(f) == 22 and len(s) == n


def test_speci_tahmin_satiri_olmaz():
    k = v2_evren.gelistirme_kayitlari(_senaryo(), ilk_yil=2011)
    onset = hedef.onset_adaylari(k)
    assert all(r["dt"].minute in (20, 50) for r in onset)
    assert len(onset) == 22


def test_speci_gelistirme_olayi_olmaz_ama_eski_yolda_olurdu():
    eski = hedef.hazirla(_senaryo())
    assert len(bagimsiz_olaylar(eski)) == 1                      # sizinti
    yeni = v2_evren.gelistirme_kayitlari(_senaryo(), ilk_yil=2011)
    assert v2_evren.gelistirme_olaylari(yeni) == []


def test_izgara_satirlarinin_Y_si_ve_egilimleri_degismez():
    eski = {r["dt"]: r for r in hedef.hazirla(_senaryo())}
    for r in v2_evren.gelistirme_kayitlari(_senaryo(), ilk_yil=2011):
        e = eski[r["dt"]]
        assert r["hedef"] == e["hedef"]
        assert r["spread_egilim_1"] == e["spread_egilim_1"]
        assert r["spread_egilim_3"] == e["spread_egilim_3"]


def test_ilk_yil_filtresi():
    s = [_k(datetime(2010, 12, 31, 23, 50)), _k(datetime(2011, 1, 1, 0, 20))]
    k = v2_evren.gelistirme_kayitlari(s)
    assert [r["zaman"] for r in k] == ["2011-01-01T00:20"]
