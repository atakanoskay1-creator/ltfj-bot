"""deney0_veri_denetimi: Deney 0'in sayim tanimlari (V2_PROTOKOL.md §4).

Deney 0 raporu bu fonksiyonlara dayaniyor; yanlis bir tam-zaman eslemesi ya
da yanlis bir meteorolojik gun siniri kapsama ve eksiklik oranlarini
sessizce degistirirdi."""
import ast
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from sis_modeli import deney0_veri_denetimi as d
from sis_modeli import hedef

T0 = datetime(2020, 2, 10, 3, 20)


def _kayit(dt, gorus=9999, spread=5, sis=0, hava=""):
    return {"zaman": dt.strftime("%Y-%m-%dT%H:%M"), "gorus": gorus, "spread": spread,
            "sis": sis, "hava": hava, "sis_kodu": 0}


def _izgara(n, bas=T0, atla=()):
    return [_kayit(bas + timedelta(minutes=30 * i)) for i in range(n) if i not in atla]


def _hazir(satirlar):
    k = hedef.hazirla(satirlar)
    return k, {r["dt"]: i for i, r in enumerate(k)}


@pytest.mark.parametrize("dt,beklenen", [
    (datetime(2020, 1, 1, 0, 20), False), (datetime(2020, 1, 1, 0, 50), False),
    (datetime(2020, 1, 1, 0, 21), True), (datetime(2020, 1, 1, 0, 0), True),
    (datetime(2020, 1, 1, 0, 20, 30), True),
])
def test_izgara_disi(dt, beklenen):
    assert d.izgara_disi(dt) is beklenen


def test_meteo_gun_12_UTC_sinirinda_doner():
    assert d.meteo_gun(datetime(2020, 1, 2, 11, 50)) == "2020-01-01"
    assert d.meteo_gun(datetime(2020, 1, 2, 12, 20)) == "2020-01-02"
    assert d.meteo_gun(datetime(2020, 1, 1, 0, 20)) == "2019-12-31"


def test_gecikme_TAM_zaman_en_yakin_gozlem_kullanilmaz():
    # t-60 slotu (indeks 0) yok; t-50'de bir gozlem olsa bile eksik sayilir
    satirlar = _izgara(3, atla=(0,))
    satirlar.append(_kayit(T0 + timedelta(minutes=10)))
    k, yer = _hazir(satirlar)
    t = T0 + timedelta(minutes=60)
    assert d.gecikme_durumu(yer, k, t, 60) == "zaman_yok"
    assert d.gecikme_durumu(yer, k, t, 30) == "var"


def test_gecikme_alan_bos_ayri_sayilir():
    satirlar = _izgara(3)
    satirlar[0]["gorus"] = None
    k, yer = _hazir(satirlar)
    t = T0 + timedelta(minutes=60)
    assert d.gecikme_durumu(yer, k, t, 60, ("gorus",)) == "alan_bos"
    assert d.gecikme_durumu(yer, k, t, 60, ("spread",)) == "var"


def test_ufuk_slotlari_eksik_adimi_sayar_ve_hazirla_onu_negatif_birakir():
    """Olay YALNIZCA eksik slotta olsaydi hazirla Y=0 yazar - denetimin
    'etiketi dogrulanamayan satir' dedigi durum tam budur."""
    satirlar = _izgara(8, atla=(3,))           # t+90 slotu yok
    k, yer = _hazir(satirlar)
    assert len(d.ufuk_slotlari(yer, T0)) == 5
    assert len(d.ufuk_slotlari(yer, T0 + timedelta(minutes=30))) == 5
    assert k[0]["hedef"] is False


def test_ufuk_slotlari_tam_ufuk():
    k, yer = _hazir(_izgara(8))
    assert len(d.ufuk_slotlari(yer, T0)) == hedef.ADIM_SAYISI == 6


def test_olay_ata_sinirlar_dahil():
    o = [{"baslangic": T0, "bitis": T0 + timedelta(hours=1)},
         {"baslangic": T0 + timedelta(hours=6), "bitis": T0 + timedelta(hours=6)}]
    assert d.olay_ata(o, T0) == 0
    assert d.olay_ata(o, T0 + timedelta(hours=1)) == 0
    assert d.olay_ata(o, T0 + timedelta(hours=2)) is None
    assert d.olay_ata(o, T0 + timedelta(hours=6)) == 1
    assert d.olay_ata(o, T0 - timedelta(minutes=30)) is None
    assert d.olay_ata([], T0) is None


def test_oran():
    assert d.oran(2, 100, 1, 100) == pytest.approx(2.0)
    assert d.oran(0, 100, 1, 100) == 0.0
    assert d.oran(1, 0, 1, 100) is None
    assert d.oran(1, 100, 0, 100) is None


def test_bootstrap_tek_gun_butun_orneklenir():
    """Tek gun varsa her tekrar ayni gunu cekmeli: aralik = nokta."""
    bs = d.gun_bootstrap({"g1": {"tümü": (2, 10, 5, 100)}}, tekrar=50)
    nokta, alt, ust, gecerli = bs["tümü"]
    assert nokta == alt == ust == pytest.approx((2 / 10) / (5 / 100))
    assert gecerli == 50


def test_bootstrap_araligi_noktayi_kapsar_ve_tekrarlanabilir():
    gunluk = {f"g{i}": {"tümü": (i % 2, 3, 1 + i % 3, 40)} for i in range(30)}
    a = d.gun_bootstrap(gunluk, tekrar=200, tohum=1)
    b = d.gun_bootstrap(gunluk, tekrar=200, tohum=1)
    assert a == b
    nokta, alt, ust, _ = a["tümü"]
    assert alt <= nokta <= ust


def test_s41_durumu():
    assert d.s41_durumu(0, 0.0, 0.0, 0.0).startswith("dejenere")
    assert d.s41_durumu(5, 2.0, 1.2, 3.0) == "KAYDA GEÇER"
    assert d.s41_durumu(5, 2.0, 0.9, 3.0) == ""        # aralik 1'i kapsiyor
    assert d.s41_durumu(5, 1.2, 1.05, 1.3) == ""       # bant icinde
    assert d.s41_durumu(5, 0.5, 0.3, 0.7) == "KAYDA GEÇER"
    assert d.s41_durumu(5, None, None, None) == ""


def test_sn_ve_fg_ailesi():
    assert d.sn_var({"hava": "-SHSN"}) and d.sn_var({"hava": "SG"}) and d.sn_var({"hava": "PL"})
    assert not d.sn_var({"hava": "BR"}) and not d.sn_var({"hava": None})
    assert d.fg_ailesi({"hava": "BCFG", "sis_kodu": 0})
    assert d.fg_ailesi({"hava": "FG", "sis_kodu": 1})
    assert not d.fg_ailesi({"hava": "BR", "sis_kodu": 0})


def test_slot_komsuluk_gruplar():
    satirlar = _izgara(6, atla=(1, 4))
    satirlar[2]["sis"], satirlar[2]["gorus"] = 1, 500     # indeks 2 -> T0+60
    k, yer = _hazir(satirlar)
    c = d.slot_komsuluk(k, yer)
    # slot 1 (T0+30) eksik, komsusu T0+60 olay -> "komsuda olay gozlemi"
    assert c[("komşuda olay gözlemi", False)] == 1
    # slot 4 (T0+120) eksik, komsulari >=5000
    assert c[("komşu görüş ≥ 5000", False)] == 1
    assert sum(c.values()) == 6


def test_betik_model_egitmez_ve_performans_olcmez():
    """Deney 0 sinirlari: model/egitim/degerlendirme modulleri ICE
    ALINMAZ (protokol: Deney 0'da model performansina bakilmaz)."""
    kaynak = Path(d.__file__).read_text(encoding="utf-8")
    agac = ast.parse(kaynak)
    alinan = set()
    for n in ast.walk(agac):
        if isinstance(n, ast.ImportFrom):
            alinan.add(n.module or "")
            alinan.update(a.name for a in n.names)
        elif isinstance(n, ast.Import):
            alinan.update(a.name for a in n.names)
    yasak = {"model", "egit", "degerlendir", "woe", "kalibrasyon",
             "ltfj_sis_olasilik", "ltfj_sis_olasilik_b"}
    assert not (alinan & yasak), alinan & yasak
