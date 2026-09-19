"""sis_modeli/ab_karsilastirma.py testleri.

En kritik iki test:
(1) lead_time_analizi() dogru isaretle (+: B daha erken) fark hesapliyor,
(2) kosullu_deger_tertil() global degil BANT-ICI bolunuyor - A ve B
    iliskili oldugu icin global bolunme ust bantlarda bos hucre uretirdi
    (bkz. README'deki gelistirme notu)."""
from datetime import datetime, timedelta, timezone

from sis_modeli import ab_karsilastirma as ab

T0 = datetime(2024, 1, 15, 6, 0, tzinfo=timezone.utc)


def test_ilk_esik_zamani_en_erken_gecisi_buluyor():
    """Esik birden fazla adimda geciliyorsa EN ERKEN (en uzak) zaman donmeli."""
    tahmin_map = {
        T0 - timedelta(minutes=90): 0.02,
        T0 - timedelta(minutes=60): 0.06,   # ilk gecis burada
        T0 - timedelta(minutes=30): 0.09,
    }
    t = ab._ilk_esik_zamani(T0, tahmin_map, esik=0.05, n_adim=3)
    assert t == T0 - timedelta(minutes=60)


def test_ilk_esik_zamani_hic_gecmezse_none():
    tahmin_map = {T0 - timedelta(minutes=30): 0.01}
    assert ab._ilk_esik_zamani(T0, tahmin_map, esik=0.05, n_adim=6) is None


def test_lead_time_analizi_pozitif_fark_b_daha_erken():
    """B, A'dan 30 dk once esigi geciyorsa fark +30 olmali."""
    olay = {"baslangic": T0}
    tahmin_a = {T0 - timedelta(minutes=30): 0.06}
    tahmin_b = {T0 - timedelta(minutes=60): 0.06}
    sonuc = ab.lead_time_analizi([olay], tahmin_a, tahmin_b, esik=0.05,
                                 pencereler=(3.0,))
    s = sonuc[3.0]
    assert s["ikisi_de_var"] == 1
    assert s["farklar"] == [30.0]
    assert s["ortalama"] == 30.0


def test_lead_time_analizi_sadece_a_sinyal_verirse_sayaca_gider():
    olay = {"baslangic": T0}
    tahmin_a = {T0 - timedelta(minutes=30): 0.06}
    tahmin_b = {T0 - timedelta(minutes=30): 0.01}   # esigi gecmiyor
    sonuc = ab.lead_time_analizi([olay], tahmin_a, tahmin_b, esik=0.05,
                                 pencereler=(3.0,))
    s = sonuc[3.0]
    assert s["sadece_a"] == 1 and s["ikisi_de_var"] == 0
    assert s["farklar"] == []


def _sentetik_kayitlar(n_dusuk_a=30, n_yuksek_a=30, poz_oran_dusuk_b=0.0,
                       poz_oran_yuksek_b=0.5):
    """A dusuk bandinda B dusuk/yuksek gruplarinin gercek oranlari FARKLI
    olacak sekilde sentetik veri - monoton bir tertil deseni test eder."""
    tahmin_a, tahmin_b, yer = {}, {}, {}
    dt = T0
    for i in range(n_dusuk_a):
        dt += timedelta(minutes=30)
        tahmin_a[dt] = 0.005          # hepsi ayni A bandinda (%0-1)
        tahmin_b[dt] = i / n_dusuk_a  # 0'dan 1'e artan B - alt yariya dusuk oran
        hedef = i >= n_dusuk_a // 2   # ust yaridaki (B yuksek) kayitlar pozitif
        yer[dt] = {"hedef": hedef}
    return tahmin_a, tahmin_b, yer


def test_kosullu_deger_tertil_bant_ici_bolunuyor_ve_monoton_yakaliyor():
    tahmin_a, tahmin_b, yer = _sentetik_kayitlar()
    ortak_dt = list(tahmin_a)
    sonuc = ab.kosullu_deger_tertil(ortak_dt, tahmin_a, tahmin_b, yer,
                                    bantlar=[(0, 0.01)])
    assert len(sonuc) == 1
    satir = sonuc[0]
    assert satir["monoton"] is True
    # ust tertil (en yuksek B) en yuksek gerceklesme oranini tasimali
    assert (satir["kesimler"]["yüksek"]["oran"]
            >= satir["kesimler"]["düşük"]["oran"])


def test_kosullu_deger_tertil_bos_bant_atlaniyor():
    """A bandinda hic veri yoksa o bant ciktida hic gorunmemeli (bos hucre
    uretilmemeli - global bolunmenin dustugu tuzak)."""
    tahmin_a, tahmin_b, yer = _sentetik_kayitlar()
    ortak_dt = list(tahmin_a)
    sonuc = ab.kosullu_deger_tertil(ortak_dt, tahmin_a, tahmin_b, yer,
                                    bantlar=[(0, 0.01), (0.5, 1.01)])
    bantlar_donen = [s["bant"] for s in sonuc]
    assert (0.5, 1.01) not in bantlar_donen


def test_model_a_tahmin_eksik_veride_none():
    assert ab.model_a_tahmin({"sicaklik": None, "cig_noktasi": 5}) is None
    assert ab.model_a_tahmin({"sicaklik": 10, "cig_noktasi": None}) is None
