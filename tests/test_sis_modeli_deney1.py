"""deney1: V2a/V2b/V2c uygulamasi ve degerlendirme prosedurunun kilitleri.

Bu testler Deney 1 sonuclari GORULMEDEN yazildi. Protokol 1.0 §7-§9'un
birebir uygulamasini ve sizinti kilidini (test fold'u degisince egitim
artefaktlari degismez) garanti eder."""
import math
import random
from datetime import datetime, timedelta

import pytest

from sis_modeli import deney1 as d
from sis_modeli import hedef, model, v1_benchmark, v2_cozucu, v2_evren


# ------------------------------------------------------------ sabitler ---
def test_dondurulmus_sabitler():
    assert d.INCE_BANT == (1000, 1500, 3000, 5000, 8000, 9999)
    assert d.ANLIK_BANT == (3000, 5000, 9999)
    assert d.EGILIM_SINIFLARI == ("iyilesen_sabit", "1_bant", "2+_bant")
    assert d.DSPREAD_KOVALARI == ("<=-2", "-1", "0", "+1", ">=+2")
    assert (d.YETERLI_SATIR, d.YETERLI_POZ, d.YETERLI_OLAY) == (500, 10, 5)
    assert d.DUZELTME == 0.5
    assert d.ORTAK == ["ruzgar_kuzey", "saat", "spread", "spread_egilim_3"]
    assert d.VARYANTLAR == {"V2a": ("gv60",), "V2b": ("gv60", "dspread_1sa"),
                            "V2c": ("gv60", "dspread_1sa", "egilim120")}
    assert d.GECIKMELER == {"V2a": (60,), "V2b": (60,), "V2c": (60, 120)}
    assert d.BOOTSTRAP_TEKRAR == 2000
    assert d.BIRINCIL_ALFA == pytest.approx(0.05 / 3)
    assert (d.KORUMA_ALFA, d.KORUMA_YAKALAMA, d.KORUMA_SURE_DK) == (0.05, -0.05, -30.0)
    assert d.BANT_ESIGI == pytest.approx(5 * 1702 / 224825)


def test_V2_V1_ile_ayni_ortak_degiskenler_ve_ayni_lambda_izgarasi():
    assert sorted(d.ORTAK + ["gorus"]) == sorted(v1_benchmark.ALANLAR)
    assert model.L2_ADAYLARI == (0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0)
    assert v1_benchmark.ESITLIK_TOLERANSI == 1e-4


# --------------------------------------------------------- degiskenler ---
@pytest.mark.parametrize("g,i", [(999, 0), (1000, 1), (1499, 1), (1500, 2), (2999, 2),
                                 (3000, 3), (4999, 3), (5000, 4), (7999, 4), (8000, 5),
                                 (9998, 5), (9999, 6), (10000, 6)])
def test_ince_indeks(g, i):
    assert d.ince_indeks(g) == i


@pytest.mark.parametrize("g,b", [(1000, 0), (2999, 0), (3000, 1), (4999, 1), (5000, 2),
                                 (9998, 2), (9999, 3), (10000, 3)])
def test_anlik_bant(g, b):
    assert d.anlik_bant(g) == b


def test_egilim_sinifi():
    assert d.egilim(5000, 5000) == "iyilesen_sabit"
    assert d.egilim(9999, 4000) == "iyilesen_sabit"
    assert d.egilim(8000, 9999) == "1_bant"
    assert d.egilim(4000, 9999) == "2+_bant"
    assert d.egilim(1200, 1600) == "1_bant"


@pytest.mark.parametrize("dd,k", [(-5, "<=-2"), (-2, "<=-2"), (-1, "-1"), (0, "0"),
                                  (1, "+1"), (2, ">=+2"), (7, ">=+2")])
def test_dspread_kovasi(dd, k):
    assert d.dspread_kovasi(dd) == k


T0 = datetime(2020, 1, 5, 3, 20)


def _k(dt, gorus=9999, spread=4, sis=0, hedef_=False):
    return {"dt": dt, "gorus": gorus, "spread": spread, "sis": sis, "hedef": hedef_}


def test_gecikme_TAM_zaman_en_yakin_yok():
    kay = [_k(T0 - timedelta(minutes=50), 3000), _k(T0 - timedelta(minutes=120), 4000), _k(T0)]
    on = [kay[-1]]
    d.gecikmeleri_ekle(kay, on)
    assert on[0]["_g60"] is None           # t-50 var ama kullanilmaz
    assert on[0]["_g120"] == 4000
    assert not d.uygun(on[0], "V2a") and not d.uygun(on[0], "V2c")


def test_uygunluk_varyanta_gore():
    r = {"gorus": 5000, "spread": 2, "_g60": 6000, "_s60": 3, "_g120": None}
    assert d.uygun(r, "V2a") and d.uygun(r, "V2b") and not d.uygun(r, "V2c")
    r["_s60"] = None
    assert d.uygun(r, "V2a") and not d.uygun(r, "V2b")


def test_geri_donus_V1_tahmini_seyrek_WoE_sifir_degil():
    """Gecikme eksik satirda hibrit tahmin TAM OLARAK V1 tahminidir; uygun
    satirda V2 modeli kullanilir (yetersiz kova WoE=0 olsa bile)."""
    t = {"ortak": {}, "v1_gorus": None,
         "gv60": {(b, e): ("bant", 0.0) for b in range(4) for e in d.EGILIM_SINIFLARI},
         "dspread_1sa": {k: 0.0 for k in d.DSPREAD_KOVALARI}}
    v2 = {"katsayilar": [-2.0, 0, 0, 0, 0, 0, 0], "tablolar": t}
    T = [{"gorus": 5000, "spread": 2, "_g60": 6000, "_s60": 2, "_g120": 1},
         {"gorus": 5000, "spread": 2, "_g60": None, "_s60": None, "_g120": None}]
    p, kul = d.hibrit_tahmin(T, v2, [0.123, 0.456], "V2b")
    assert kul == [True, False]
    assert p[1] == 0.456
    assert p[0] == pytest.approx(1 / (1 + math.exp(2.0)))


# ----------------------------------------------------- tablo kurallari ---
def _E(hucreler, n_olay_basina=1):
    """hucreler: [(gorus_t, gorus_60, s, s60, n, poz)] -> (E, egitim_tam).
    Her pozitif satir kendi bagimsiz olayina aittir (olaylar >3 sa arali)."""
    E, tam = [], []
    t = datetime(2012, 1, 1, 0, 20)
    for g, g60, sp, s60, n, poz in hucreler:
        for i in range(n):
            t += timedelta(hours=8)
            y = i < poz
            r = {"dt": t, "gorus": g, "spread": sp, "_g60": g60, "_s60": s60, "_g120": g60,
                 "hedef": y, "sis": 0, "saat": t.hour, "ay": t.month,
                 "ruzgar_kuzey": 1.0, "spread_egilim_3": 0}
            E.append(r)
            tam.append(r)
            if y:
                tam.append({"dt": t + timedelta(minutes=30), "sis": 1, "gorus": 500,
                            "hedef": False})
    tam.sort(key=lambda r: r["dt"])
    return E, tam


def test_gv60_hiyerarsi_hucre_bant_v1gorus(monkeypatch):
    monkeypatch.setattr(d, "YETERLI_SATIR", 20)
    monkeypatch.setattr(d, "YETERLI_POZ", 3)
    monkeypatch.setattr(d, "YETERLI_OLAY", 3)
    E, tam = _E([
        (2000, 2000, 1, 1, 30, 5),    # bant 0, sabit: hucre yeterli
        (2000, 9999, 1, 1, 10, 2),    # bant 0, 2+ bant dusus: hucre yetersiz, bant yeterli
        (6000, 6000, 3, 3, 10, 1),    # bant 2: hucre de bant da yetersiz
        (9999, 9999, 5, 5, 200, 0),
    ])
    t = d.tablolar_kur(E, tam, "V2a")
    H_poz = sum(r["hedef"] for r in E)
    H_neg = len(E) - H_poz
    k, w = t["gv60"][(0, "iyilesen_sabit")]
    assert k == "hucre" and w == pytest.approx(d.woe(5, 25, H_poz, H_neg, 12))
    k, w = t["gv60"][(0, "2+_bant")]
    assert k == "bant" and w == pytest.approx(d.woe(7, 33, H_poz, H_neg, 4))
    assert t["gv60"][(2, "iyilesen_sabit")] == ("v1_gorus", None)
    # komsu bantla birlestirme yok: bant 1'de hic satir yok -> v1_gorus
    assert t["gv60"][(1, "1_bant")] == ("v1_gorus", None)


def test_gv60_son_geri_donus_fold_V1_gorus_WoE_si_production_degil(monkeypatch):
    import ltfj_sis_olasilik
    E, tam = _E([(6000, 6000, 3, 3, 10, 1), (9999, 9999, 5, 5, 300, 3)])
    t = d.tablolar_kur(E, tam, "V2a")
    fold_v1 = model.woe_tablolari(E, v1_benchmark.ALANLAR)["gorus"]
    assert t["v1_gorus"] == fold_v1
    r = dict(E[0])
    x = d.desen(r, t, "V2a")
    assert x[len(d.ORTAK)] == pytest.approx(model._woe_degeri(fold_v1, 6000))
    # production tablolarina referans yok
    import inspect
    assert "ltfj_sis_olasilik" not in inspect.getsource(d.tablolar_kur)
    assert "ltfj_sis_olasilik" not in inspect.getsource(d.desen)


def test_tek_boyutlu_yetersiz_kova_sifir_birlestirme_yok(monkeypatch):
    monkeypatch.setattr(d, "YETERLI_SATIR", 20)
    monkeypatch.setattr(d, "YETERLI_POZ", 3)
    monkeypatch.setattr(d, "YETERLI_OLAY", 3)
    # dspread: -1 kovasi yeterli, -2 ve 0 yetersiz (komsuya katilmaz)
    E, tam = _E([(5000, 5000, 2, 3, 30, 5),     # d=-1
                 (5000, 5000, 2, 5, 5, 1),      # d=-3 -> <=-2
                 (5000, 5000, 2, 2, 5, 1)])     # d=0
    t = d.tablolar_kur(E, tam, "V2b")
    H_poz = sum(r["hedef"] for r in E)
    H_neg = len(E) - H_poz
    assert t["dspread_1sa"]["-1"] == pytest.approx(d.woe(5, 25, H_poz, H_neg, 5))
    assert t["dspread_1sa"]["<=-2"] == 0.0
    assert t["dspread_1sa"]["0"] == 0.0
    assert t["dspread_1sa"]["+1"] == 0.0 and t["dspread_1sa"][">=+2"] == 0.0


def test_yeterlilik_olay_sayisi_egitim_bolutlemesinden():
    """Ayni olaya ait birden cok pozitif satir tek olay sayilir."""
    E, tam = [], []
    t = datetime(2012, 3, 1, 0, 20)
    for i in range(6):                         # 6 pozitif satir, penceresi ayni olaya
        r = {"dt": t + timedelta(minutes=30 * i), "gorus": 2000, "spread": 1, "_g60": 2000,
             "_s60": 1, "_g120": 2000, "hedef": True, "sis": 0}
        E.append(r), tam.append(r)
    for i in range(6, 9):                      # olay gozlemleri (tek olay)
        tam.append({"dt": t + timedelta(minutes=30 * i), "sis": 1, "hedef": False, "gorus": 400})
    at = d.olay_atamalari(tam, E)
    assert len(at) == 6 and set(at.values()) == {0}


# --------------------------------------------------------- bootstrap ---
def test_dll_bootstrap_ayni_tahmin_sifir_ve_gun_blogu():
    R = [{"dt": datetime(2020, 1, 1, h, 20)} for h in range(10)]
    p = [0.1] * 10
    y = [True] + [False] * 9
    ornek = d.dll_bootstrap(R, p, p, y, tekrar=50)
    assert all(v == 0 for v in ornek)
    # tek meteorolojik gun (00-09 UTC ayni gun): her tekrar ayni -> sabit
    ornek = d.dll_bootstrap(R, p, [0.2] * 10, y, tekrar=50)
    assert len(set(round(v, 12) for v in ornek)) == 1


def test_alt_sinir_yuzdelik():
    ornek = list(range(2000))
    assert d.alt_sinir(ornek, 0.05 / 3) == 33
    assert d.alt_sinir(ornek, 0.05) == 100


def test_olay_bootstrap_ayni_ise_sifir():
    y = [{"yakalandi": True, "sure_dk": 60.0}, {"yakalandi": False, "sure_dk": 0.0}]
    fy, fs, fm = d.olay_bootstrap(y, y, tekrar=30)
    assert all(v == 0 for v in fy + fs + fm)


def test_medyan():
    assert d._medyan([3, 1, 2]) == 2
    assert d._medyan([1, 2, 3, 4]) == 2.5
    assert d._medyan([]) == 0.0


# ------------------------------------------------ sizinti kilidi (§7.5) ---
def _sentetik_ham(yillar, tohum=0):
    r = random.Random(tohum)
    out = []
    for y in yillar:
        for gun in range(0, 360, 9):
            bas = datetime(y, 1, 1, 0, 20) + timedelta(days=gun)
            sisli = r.random() < 0.35
            for s in range(48):
                dt = bas + timedelta(minutes=30 * s)
                if r.random() < 0.02:
                    continue                          # eksik gozlem
                if sisli and 6 <= s <= 12:
                    g, sp = r.choice([300, 600, 900]), 0
                elif sisli and 2 <= s < 6:
                    g, sp = r.choice([1200, 2000, 4000, 6000]), 1
                else:
                    g, sp = r.choice([4000, 7000, 9999, 9999]), r.choice([2, 3, 5, 8])
                out.append({"zaman": dt.strftime("%Y-%m-%dT%H:%M"), "ay": dt.month,
                            "saat": dt.hour, "sicaklik": 10, "cig_noktasi": 10 - sp,
                            "spread": sp, "ruzgar_hiz": r.choice([0, 2, 5, 9]),
                            "ruzgar_yon": r.choice([0, 90, 180, 270]), "gorus": g,
                            "tavan": None, "qnh": 1015, "hava": "FG" if g < 1000 else "",
                            "sis_kodu": int(g < 1000), "sis": int(g < 1000), "lvo": 0})
    return out


def _veri():
    kay = v2_evren.gelistirme_kayitlari(_sentetik_ham(range(2011, 2019)), ilk_yil=2011)
    on = hedef.onset_adaylari(kay)
    d.gecikmeleri_ekle(kay, on)
    return kay, on


def _boz_test(kay, yillar):
    for r in kay:
        if r["dt"].year in yillar:
            r["hedef"] = not r["hedef"]
            r["sis"] = 1 - r["sis"]
            r["gorus"] = 700 if r["gorus"] > 5000 else 9999
            r["spread"] = (r["spread"] or 0) + 3
    on = hedef.onset_adaylari(kay)
    d.gecikmeleri_ekle(kay, on)
    return on


def _ozet_v2(x):
    return (x["ic"]["havuz_ll"], x["ic"]["secilen"], x["ic"]["bloklar"], x["katsayilar"],
            x["tablolar"]["gv60"], x["tablolar"]["ortak"], x["tablolar"]["v1_gorus"],
            x["tablolar"]["sayim"], x["tablolar"].get("dspread_1sa"),
            x["tablolar"].get("egilim120"), x["egitim_uygun"])


@pytest.mark.parametrize("varyant", ["V2a", "V2b", "V2c"])
def test_sizinti_test_foldu_degisince_V2_egitim_artefaktlari_degismez(monkeypatch, varyant):
    monkeypatch.setattr(d, "YETERLI_SATIR", 50)
    monkeypatch.setattr(d, "YETERLI_POZ", 3)
    monkeypatch.setattr(d, "YETERLI_OLAY", 2)
    kay, on = _veri()
    once = d.fold_egit(kay, on, 2017, varyant)
    kaynaklar = {k for k, _ in once["tablolar"]["gv60"].values()}
    assert kaynaklar & {"hucre", "bant"}              # hiyerarsi gercekten calisiyor
    on2 = _boz_test(kay, (2017, 2018))
    sonra = d.fold_egit(kay, on2, 2017, varyant)
    assert _ozet_v2(once) == _ozet_v2(sonra)


def test_sizinti_test_foldu_degisince_V1_referansi_degismez():
    kay, on = _veri()
    once = v1_benchmark.fold_calistir(kay, on, (2017, 2018))
    on2 = _boz_test(kay, (2017, 2018))
    sonra = v1_benchmark.fold_calistir(kay, on2, (2017, 2018))
    for k in ("ic", "katsayilar", "tablolar", "egitim", "egitim_poz", "egitim_olay"):
        assert once[k] == sonra[k], k


def test_V2_lambdasi_kendi_ic_dogrulamasindan(monkeypatch):
    """V2'nin lambda'si V1'in secimine baglanmaz: kendi havuz LL'sine l2_sec."""
    kay, on = _veri()
    x = d.fold_egit(kay, on, 2017, "V2a")
    assert set(x["ic"]["havuz_ll"]) == set(model.L2_ADAYLARI)
    assert x["ic"]["secilen"] == v1_benchmark.l2_sec(x["ic"]["havuz_ll"])
    assert [b["yil"] for b in x["ic"]["bloklar"]] == [2014, 2015, 2016]


def test_V2_varsayilan_cozucu_sonumlu_newton():
    import inspect
    assert inspect.signature(d.fold_egit).parameters["cozucu"].default is v2_cozucu.egit
    assert inspect.signature(d.ic_dogrulama).parameters["cozucu"].default is v2_cozucu.egit


def test_olay_bolutlemesi_yalniz_egitim_yillarini_gorur(monkeypatch):
    kay, on = _veri()
    goren = []
    gercek = d.olay_atamalari

    def kayit(egitim_tam, satirlar):
        goren.append(max(r["dt"].year for r in egitim_tam))
        return gercek(egitim_tam, satirlar)

    monkeypatch.setattr(d, "olay_atamalari", kayit)
    d.fold_egit(kay, on, 2017, "V2a")
    assert goren and max(goren) <= 2016
