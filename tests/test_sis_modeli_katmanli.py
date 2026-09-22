"""Katmanli (mevsim/saat) model deneyi - Yabra ve ark. (2026) tekrari.

EN KRITIK TEST: katman sinirlari YALNIZCA egitim verisinden turetilmeli.
Tum veriden turetmek, test yillarinin iklimini egitime sizdirirdi ve
katmanli yaklasimi haksiz yere iyi gosterirdi.
"""
from datetime import datetime, timedelta, timezone

import pytest

from sis_modeli import katmanli_deney as kd


def _kayit(dt, hedef=False):
    return {"dt": dt, "gun": dt.strftime("%Y-%m-%d"), "hedef": hedef}


# ------------------------------------------------- katman sinirlari
def test_yuksek_kova_taban_oranin_ustundekileri_seciyor():
    """Ocak sisli, Temmuz sissiz -> yalnizca ocak 'yuksek' olmali."""
    kayitlar = ([_kayit(datetime(2015, 1, d, 3), hedef=d <= 20) for d in range(1, 29)]
                + [_kayit(datetime(2015, 7, d, 3), hedef=False) for d in range(1, 29)])
    yuksek = kd._yuksek_kova(kayitlar, kd.KATMANLAR["mevsim"])
    assert yuksek == {1}


def test_yuksek_kova_saat_dongusunu_yakaliyor():
    kayitlar = ([_kayit(datetime(2015, 1, 5, 3) + timedelta(days=i), hedef=i < 10)
                 for i in range(20)]
                + [_kayit(datetime(2015, 1, 5, 15) + timedelta(days=i), hedef=False)
                   for i in range(20)])
    yuksek = kd._yuksek_kova(kayitlar, kd.KATMANLAR["saat"])
    assert 3 in yuksek and 15 not in yuksek


def test_hic_pozitif_yoksa_hicbir_kova_yuksek_degil():
    kayitlar = [_kayit(datetime(2015, m, 5, 3)) for m in range(1, 13)]
    assert kd._yuksek_kova(kayitlar, kd.KATMANLAR["mevsim"]) == set()


def test_bos_egitimde_cokmuyor():
    assert kd._yuksek_kova([], kd.KATMANLAR["mevsim"]) == set()


def test_katman_etiketi_iki_degerden_birini_veriyor():
    r = _kayit(datetime(2015, 1, 5, 3))
    assert kd._katman_etiketi(r, kd.KATMANLAR["mevsim"], {1}) == "yuksek"
    assert kd._katman_etiketi(r, kd.KATMANLAR["mevsim"], {7}) == "dusuk"


# ----------------------------------------------------- sozlesmeler
def test_tek_konfigurasyonunun_anahtari_yok():
    """'tek' (havuz) modelinde katmanlama OLMAMALI - referans budur."""
    assert kd.KATMANLAR["tek"] is None


def test_uc_konfigurasyon_var():
    assert set(kd.KATMANLAR) == {"tek", "mevsim", "saat"}


def test_min_pozitif_esigi_anlamli():
    """5 pozitifle egitilmis bir WoE tablosu gurultudur; esik bunu
    engellemeli ve katmanli yaklasimi haksiz yere kotu gostermemeli."""
    assert kd.KATMAN_MIN_POZITIF >= 20


def test_ufuklar_makalenin_iddiasini_sinayacak_sekilde_secilmis():
    """Yabra ve ark.: kazanc >=2 saatte var, 1 saatte YOK. 1 saati
    disarida birakmak iddiayi sinanamaz hale getirirdi."""
    assert 1.0 in kd.UFUKLAR_SAAT
    assert 2.0 in kd.UFUKLAR_SAAT


# ------------------------------------------------------- olculer
def test_lss_ve_ap_lift_iklim_referansini_ornekten_kuruyor():
    """Sabit bir referans, orneklemin taban orani oynadikca beceriyi
    yapay olarak oynatirdi (bootstrap replikalarinda kritik)."""
    y = [True] * 5 + [False] * 95
    t = [0.5 if v else 0.01 for v in y]
    assert kd._lss(t, y) > 0
    assert kd._ap_lift(t, y) > 1


def test_hic_pozitif_yoksa_ap_lift_sifir():
    assert kd._ap_lift([0.1] * 10, [False] * 10) == 0.0


def test_etiket_bicimi():
    assert kd._etiket(0.5) == "30dk"
    assert kd._etiket(2.0) == "2h"


# ------------------------------------------------- sizinti korumasi
def test_katman_sinirlari_test_verisini_GORMUYOR():
    """EN KRITIK TEST: _yuksek_kova yalnizca kendisine verilen listeyi
    kullanir. calistir() ona SADECE egitim dilimini verir - bu testi
    kirmak icin birinin calistir()'da gelistirme'yi gecmesi gerekir."""
    import inspect
    kaynak = inspect.getsource(kd.calistir)
    assert "_yuksek_kova(egitim," in kaynak
    assert "_yuksek_kova(gelistirme" not in kaynak
    assert "_yuksek_kova(test" not in kaynak


def test_havuz_modeli_her_zaman_egitiliyor():
    """Bir katmanda yeterli pozitif yoksa havuza dusulur; havuz her
    fold'da hazir olmali."""
    import inspect
    kaynak = inspect.getsource(kd.calistir)
    assert "havuz = model.egit_secerek(egitim, ALANLAR)" in kaynak


def test_geri_dusme_sayiliyor():
    """Sessizce havuza dusup 'katmanli model' demek yaniltici olurdu -
    kac kez dusuldugu raporlaniyor."""
    import inspect
    assert 'geri_dusme' in inspect.getsource(kd.calistir)
