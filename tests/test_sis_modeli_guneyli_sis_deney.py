"""guneyli_sis_deney: kalibrasyon orani, olay gruplamasi, olay-oncesi tepe.

Deneyin karari bu fonksiyonlara dayaniyor; yanlis bir oran ya da yanlis
gruplama "model hafife aliyor/almiyor" sonucunu tersine cevirebilir."""
from datetime import datetime, timedelta

import pytest

from sis_modeli import guneyli_sis_deney as d

T0 = datetime(2020, 2, 10, 3, 0)


@pytest.mark.parametrize("yon,hiz,beklenen", [
    (140, 5, True), (250, 5, True), (139, 5, False), (251, 5, False),
    (200, 2, False), (None, 5, False), (200, None, False),
])
def test_guneyli(yon, hiz, beklenen):
    assert d.guneyli({"ruzgar_yon": yon, "ruzgar_hiz": hiz}) is beklenen


def test_kalibrasyon_orani():
    # ortalama tahmin %10, gerceklesen %20 -> 2 (hafife alma)
    assert d.kalibrasyon_orani([0.1] * 10, [1, 1] + [0] * 8) == pytest.approx(2.0)
    assert d.kalibrasyon_orani([0.5] * 4, [1, 0, 0, 0]) == pytest.approx(0.5)
    assert d.kalibrasyon_orani([], []) == 0.0
    assert d.kalibrasyon_orani([0.0, 0.0], [0, 1]) == 0.0


def test_blok_aralik_GUN_bazinda_ve_orani_kapsiyor():
    k = [{"gun": f"2020-01-{g:02d}"} for g in range(1, 21) for _ in range(5)]
    p = [0.1] * 100
    y = [1 if i % 10 == 0 else 0 for i in range(100)]
    alt, ust = d.blok_aralik(k, p, y)
    assert alt <= d.kalibrasyon_orani(p, y) <= ust


def test_blok_aralik_GUN_butun_olarak_orneklenir():
    """Tek gun varsa her tekrar ayni gunu BUTUN olarak ceker - oran sabit.
    Satir bazinda (ya da gun disinda bir anahtarla) orneklense degisirdi."""
    k = [{"gun": "2020-01-01"}] * 4
    assert d.blok_aralik(k, [0.25, 0.75, 0.25, 0.75], [1, 0, 1, 0]) == (1.0, 1.0)


def _r(dt, sis, yon=40, hiz=5):
    return {"dt": dt, "sis": sis, "ruzgar_yon": yon, "ruzgar_hiz": hiz}


def test_olaylar_gruplama_ve_COGUNLUK_kurali():
    k = ([_r(T0 + timedelta(minutes=30 * i), 1, yon=200) for i in range(3)]
         + [_r(T0 + timedelta(minutes=90), 1, yon=40)]
         + [_r(T0 + timedelta(hours=6), 1, yon=200),
            _r(T0 + timedelta(hours=6, minutes=30), 1, yon=40)]
         + [_r(T0 + timedelta(hours=9), 0)])
    ol = d.olaylar(k)
    assert ol == [(T0, True), (T0 + timedelta(hours=6), False)]   # 3/4 guneyli; 1/2 degil


def test_olay_oncesi_tepe_YALNIZCA_onceki_3_saat():
    bas = T0 + timedelta(hours=4)
    tz = {bas - timedelta(hours=3): 0.2,           # dahil (sinirda)
          bas - timedelta(minutes=30): 0.1,
          bas - timedelta(hours=3, minutes=30): 0.9,   # pencere disi
          bas: 0.8}                                     # baslangic ani disi
    assert d.olay_oncesi_tepe([(bas, True)], tz) == [(0.2, True)]


def test_onunde_tahmin_olmayan_olay_ATLANIR():
    assert d.olay_oncesi_tepe([(T0, False)], {}) == []


def test_bant_esikleri_SAYFADAKIYLE_ayni():
    """Sayfa 2x taban = 'orta', 5x taban = 'yuksek' diyor."""
    import ltfj_sis_olasilik as so
    assert d.BANT_ESIKLERI == (2 * so.TABAN_ORAN, 5 * so.TABAN_ORAN)
