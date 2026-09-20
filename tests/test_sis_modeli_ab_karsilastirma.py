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


# --------------------------------------------- soru 4/5/6: derinlemesine A>=%5
def _cok_gunluk_sentetik(n_gun=40, baslangic_yil=2024):
    """Her GUN ayri bir 'gun' etiketi tasiyan, A hep ayni bantta (%5-10),
    B artan, gercek deger sadece ust yaride pozitif olan sentetik veri -
    gun-blok bootstrap'in CALISTIGINI (n_gun >= GUN_INCE_SINIR) dogrulamak
    icin yeterli gun cesitliligi saglar."""
    tahmin_a, tahmin_b, yer = {}, {}, {}
    taban = datetime(baslangic_yil, 3, 1, tzinfo=timezone.utc)
    for i in range(n_gun):
        dt = taban + timedelta(days=i, hours=6)
        tahmin_a[dt] = 0.07                    # hep %5-10 bandinda
        tahmin_b[dt] = i / n_gun
        yer[dt] = {"hedef": i >= n_gun // 2, "gun": dt.strftime("%Y-%m-%d"), "dt": dt}
    return tahmin_a, tahmin_b, yer


def test_oran_ci_bos_grupta_none_doner():
    bilgi = ab._oran_ci([], {})
    assert bilgi["n"] == 0 and bilgi["oran"] is None


def test_oran_ci_gun_sayisini_doguru_sayiyor():
    _, _, yer = _cok_gunluk_sentetik(n_gun=10)
    dtler = list(yer)
    bilgi = ab._oran_ci(dtler, yer, tekrar=20)
    assert bilgi["gun_sayisi"] == 10          # her satir ayri bir gunde
    assert bilgi["n"] == 10
    assert bilgi["ci"][0] <= bilgi["oran"] <= bilgi["ci"][1] or bilgi["ci"] == (0.0, 0.0)


def test_derinlemesine_a_yuksek_tek_bantta_ci_hesapliyor():
    tahmin_a, tahmin_b, yer = _cok_gunluk_sentetik(n_gun=60)
    ortak_dt = list(tahmin_a)
    sonuc = ab.derinlemesine_a_yuksek(ortak_dt, tahmin_a, tahmin_b, yer,
                                      bantlar=[(0.05, 0.10)])
    assert len(sonuc) == 1
    satir = sonuc[0]
    assert satir["n_tum"] == 60
    # B ile gercek deger burada TASARIM GEREGI iliskili (ust yari pozitif) -
    # yuksek tertilin orani dusukten acikca buyuk olmali.
    assert (satir["kesimler"]["yüksek"]["oran"]
            > satir["kesimler"]["düşük"]["oran"])
    for etiket in ("düşük", "orta", "yüksek"):
        assert satir["kesimler"][etiket]["ci"][0] is not None


def test_yillik_kararlilik_ayni_kesim_noktalarini_yillara_bolerek_kullaniyor():
    tahmin_a, tahmin_b, yer = _cok_gunluk_sentetik(n_gun=30, baslangic_yil=2024)
    # bir kismini 2025'e tasi
    for i, dt in enumerate(list(yer)):
        if i % 2 == 0:
            yeni_dt = dt.replace(year=2025)
            yer[yeni_dt] = {**yer[dt], "dt": yeni_dt}
            tahmin_a[yeni_dt] = tahmin_a.pop(dt)
            tahmin_b[yeni_dt] = tahmin_b.pop(dt)
            del yer[dt]
    ortak_dt = list(tahmin_a)
    sonuc = ab.yillik_kararlilik(ortak_dt, tahmin_a, tahmin_b, yer,
                                 bantlar=[(0.05, 0.10)], yillar=(2024, 2025))
    assert len(sonuc) == 1
    yillar = sonuc[0]["yillar"]
    assert set(yillar) == {2024, 2025}
    toplam_n = sum(yillar[y][e]["n"] for y in yillar for e in ("düşük", "orta", "yüksek"))
    assert toplam_n == 30
