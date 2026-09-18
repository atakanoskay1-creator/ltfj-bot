"""Walk-forward bolme, lojistik regresyon ve degerlendirme testleri.

En kritik iki test:
(1) Fold'lar GELECEGE sizmiyor ve nihai holdout hic acilmiyor,
(2) Tekil sistem SESSIZCE sifir dondurmuyor - onceki surumde donduruyordu ve
    model sabit tahmin uretip AP'si taban orana esitleniyordu; bu 'modelleme
    sonucu' sanilip yanlis yoruma yol acti (bkz. model.TekilSistem)."""
from datetime import datetime, timedelta, timezone

import pytest

from sis_modeli import bolme, degerlendir, model


def _kayit(yil, ay=1, gun=15, saat=3, **ek):
    dt = datetime(yil, ay, gun, saat, tzinfo=timezone.utc)
    r = {"dt": dt, "gun": dt.strftime("%Y-%m-%d"), "ay": ay, "saat": saat,
         "spread": 1.0, "gorus": 5000, "hedef": False}
    r.update(ek)
    return r


# ------------------------------------------------------------------ bolme
def test_foldlar_egitim_her_zaman_testten_once():
    """Sizinti testi: hicbir fold'un egitim yili, test yilina esit veya ondan
    sonra olamaz."""
    for egitim, test in bolme.foldlar():
        assert max(egitim) < min(test), (egitim, test)


def test_foldlar_genisleyen_pencere():
    """Her fold bir oncekinin egitim donemini kapsamali - o tarihte gercekten
    elde olacak veriyle egitilmis olsun."""
    f = bolme.foldlar()
    for (onceki_eg, _), (sonraki_eg, _) in zip(f, f[1:]):
        assert set(onceki_eg) <= set(sonraki_eg)


def test_hicbir_fold_holdout_yilina_dokunmuyor():
    for egitim, test in bolme.foldlar():
        assert not (set(egitim) | set(test)) & set(bolme.HOLDOUT_YILLARI)


def test_gelistirme_ve_holdout_ayrik():
    kayitlar = [_kayit(y) for y in range(2011, 2027)]
    g = {r["dt"].year for r in bolme.gelistirme(kayitlar)}
    h = {r["dt"].year for r in bolme.holdout(kayitlar)}
    assert not g & h
    assert h == set(bolme.HOLDOUT_YILLARI)


# ------------------------------------------------------------------ model
def test_tekil_sistem_sessizce_sifir_dondurmuyor():
    """Regresyon: eskiden [0,0,...] donuyordu ve model sabit tahmin uretiyordu."""
    with pytest.raises(model.TekilSistem):
        model._coz([[0.0, 0.0], [0.0, 0.0]], [1.0, 1.0])


def test_coz_basit_sistemi_dogru_cozuyor():
    x = model._coz([[2.0, 0.0], [0.0, 4.0]], [4.0, 8.0])
    assert abs(x[0] - 2.0) < 1e-9 and abs(x[1] - 2.0) < 1e-9


def test_egit_ayrik_sinyali_ogreniyor():
    """WoE deseni yuksek olan desende pozitif oran yuksekse katsayi pozitif
    olmali."""
    desenler = [(-1.0,), (1.0,)]
    beta = model.egit(desenler, [1000, 1000], [10, 300], l2=1.0)
    assert beta[1] > 0
    p_dusuk = 1 / (1 + pow(2.718281828, -(beta[0] + beta[1] * -1.0)))
    p_yuksek = 1 / (1 + pow(2.718281828, -(beta[0] + beta[1] * 1.0)))
    assert p_yuksek > p_dusuk


def test_egit_bos_veride_cokmez():
    assert model.egit([], [], []) == [0.0]


def test_l2_secimi_yalnizca_egitim_verisini_kullaniyor():
    """egit_secerek() ic dogrulamayi EGITIM doneminin son yilindan ayirmali;
    disaridan test verisi almamali."""
    # Kova basina en az woe.KOVA_MIN_GOZLEM kayit olmali, yoksa sinyal kovasi
    # komsusuna katilir ve WoE ayrimi kaybolur.
    egitim = []
    for yil in (2012, 2013):
        egitim += [_kayit(yil, spread=0.5, hedef=(i % 3 == 0)) for i in range(600)]
        egitim += [_kayit(yil, spread=8.0) for _ in range(1200)]
    beta, tablolar, l2 = model.egit_secerek(egitim, ["spread"])
    assert l2 in model.L2_ADAYLARI
    assert "spread" in tablolar
    sisli = model.olasilik(beta, _kayit(2014, spread=0.5), tablolar)
    acik = model.olasilik(beta, _kayit(2014, spread=8.0), tablolar)
    assert sisli > acik


def test_basit_kural_baseline_mevcut_sezgisel_yontemi_temsil_ediyor():
    assert model.basit_kural_baseline({"spread": 0.5, "ruzgar_hiz": 3}) > 0.2
    assert model.basit_kural_baseline({"spread": 10.0, "ruzgar_hiz": 3}) < 0.01


# ----------------------------------------------------------- degerlendirme
def test_brier_mukemmel_tahminde_sifir():
    assert degerlendir.brier([1.0, 0.0, 1.0], [True, False, True]) == 0.0


def test_brier_skill_referansla_ayniysa_sifir():
    t = [0.1, 0.2, 0.3]
    y = [False, True, False]
    assert abs(degerlendir.brier_skill(t, y, t)) < 1e-12


def test_brier_skill_referanstan_kotuyse_negatif():
    y = [True, False, False, False]
    iyi = [0.9, 0.1, 0.1, 0.1]
    kotu = [0.1, 0.9, 0.9, 0.9]
    assert degerlendir.brier_skill(kotu, y, iyi) < 0


def test_ortalama_kesinlik_mukemmel_siralamada_bir():
    assert degerlendir.ortalama_kesinlik([0.9, 0.8, 0.1, 0.05],
                                         [True, True, False, False]) == 1.0


def test_ortalama_kesinlik_pozitif_yoksa_sifir():
    assert degerlendir.ortalama_kesinlik([0.5, 0.5], [False, False]) == 0.0


def test_guvenilirlik_kalibre_modelde_ortusuyor():
    tahminler = [0.1] * 100 + [0.5] * 100
    gercekler = [i < 10 for i in range(100)] + [i < 50 for i in range(100)]
    t = degerlendir.guvenilirlik(tahminler, gercekler)
    for kova in t:
        assert abs(kova["ortalama_tahmin"] - kova["gerceklesen"]) < 0.02


def test_esik_tablosu_kesinlik_duyarlilik_hesabi():
    tahminler = [0.9, 0.6, 0.3, 0.05]
    gercekler = [True, False, True, False]
    satir = next(e for e in degerlendir.esik_tablosu(tahminler, gercekler,
                                                     esikler=(0.5,)))
    assert satir["alarm"] == 2 and satir["dogru"] == 1
    assert abs(satir["kesinlik"] - 0.5) < 1e-9
    assert abs(satir["duyarlilik"] - 0.5) < 1e-9


def test_blok_guven_araligi_gun_bazinda_orneklyor():
    kayitlar = [{"gun": f"2024-01-{i//10+1:02d}"} for i in range(100)]
    tahminler = [0.3] * 100
    gercekler = [i % 4 == 0 for i in range(100)]
    alt, ust = degerlendir.blok_guven_araligi(kayitlar, tahminler, gercekler,
                                              degerlendir.brier, tekrar=50)
    assert alt <= degerlendir.brier(tahminler, gercekler) <= ust


def test_l2_izgarasi_notr_ve_a_priori():
    """Izgara sonuclara BAKILMADAN secilmis log-ondalik bir aralik olmali.

    Onceki surumde izgara, manuel bir taramanin walk-forward TEST sonuclari
    gorulduKTEN SONRA daraltilmisti; secim temizken arama uzayi degerlendirme
    verisinden etkilenmisti (ikinci dereceden sizinti). Olculdu: notr izgara
    ayni sonucu veriyor - yine de itiraza yer birakmamak icin notr tutuluyor."""
    assert model.L2_ADAYLARI == (0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0)
    # her ardisik aday tam bir ondalik basamak uzakta (elle secilmemis)
    for a, b in zip(model.L2_ADAYLARI, model.L2_ADAYLARI[1:]):
        assert abs(b / a - 10.0) < 1e-9


# --------------------------------------------------------- log_loss/roc_auc
def test_log_loss_mukemmel_tahminde_sifira_yakin():
    assert degerlendir.log_loss([0.999999999, 0.000000001], [True, False]) < 1e-6


def test_log_loss_rastgele_yarimda_ln2():
    import math
    assert abs(degerlendir.log_loss([0.5] * 4, [True, False, True, False])
              - math.log(2)) < 1e-9


def test_log_loss_yanlis_emin_tahmini_agir_cezalandiriyor():
    """Brier'den fark: kareli hata sinirlidir (<=1), log-kayip sinirsizdir."""
    kotu_logloss = degerlendir.log_loss([0.001], [True])
    kotu_brier = degerlendir.brier([0.001], [True])
    assert kotu_logloss > 5 * kotu_brier


def test_roc_auc_mukemmel_siralamada_bir():
    assert degerlendir.roc_auc([0.9, 0.8, 0.2, 0.1],
                               [True, True, False, False]) == 1.0


def test_roc_auc_ters_siralamada_sifir():
    assert degerlendir.roc_auc([0.1, 0.2, 0.8, 0.9],
                               [True, True, False, False]) == 0.0


def test_roc_auc_esit_skorlarda_yarim():
    assert degerlendir.roc_auc([0.5] * 4, [True, False, True, False]) == 0.5


def test_roc_auc_tek_sinifli_veride_notr_donuyor():
    """Yalniz pozitif veya yalniz negatif varsa AUC tanimsizdir; coksmemeli."""
    assert degerlendir.roc_auc([0.1, 0.9], [True, True]) == 0.5
    assert degerlendir.roc_auc([0.1, 0.9], [False, False]) == 0.5
