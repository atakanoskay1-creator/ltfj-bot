"""sis_modeli/kalibrasyon.py testleri.

En kritik test: izotonik_uydur() cikan bloklarin p'ye gore MONOTON ARTAN
olmasi - PAVA'nin butun amaci bu (kalibrasyon_tablosu() de bunu miras alir).

NOT: bu modul, holdout'ta AP'yi kotulestirdigi (0.184->0.173) icin
PRODUKSIYONA ALINMADI (bkz. sis_modeli/README.md, "Kalibrasyon denendi ve
reddedildi"). Testler yine de saf fonksiyonlarin DOGRU calistigini
dogruluyor - kod ileride farkli bir kalibrasyon yaklasimi icin yeniden
kullanilabilir."""
from sis_modeli import kalibrasyon as kal


def test_izotonik_uydur_monoton_artan_bloklar_uretiyor():
    """Ham skorla ters orantili (kucuk p, buyuk gercek oran) bir veri
    setinde bile cikan bloklarin kalibre degeri MONOTON ARTAN olmali -
    PAVA'nin tanimi geregi."""
    ciftler = [(0.1, 1), (0.1, 1), (0.2, 0), (0.2, 0), (0.3, 1), (0.4, 0)]
    bloklar = kal.izotonik_uydur(ciftler)
    degerler = [b["kalibre"] for b in bloklar]
    assert degerler == sorted(degerler)


def test_izotonik_uydur_zaten_monotonsa_degistirmiyor():
    ciftler = [(0.1, 0), (0.1, 0), (0.2, 0), (0.2, 1), (0.3, 1), (0.3, 1)]
    bloklar = kal.izotonik_uydur(ciftler)
    # zaten monoton oldugu icin her nokta kendi blogu olmali (birlesme yok)
    assert [b["kalibre"] for b in bloklar] == [0.0, 0.5, 1.0]


def test_kalibrasyon_tablosu_son_sinir_none():
    bloklar = kal.izotonik_uydur([(0.1, 0), (0.5, 1)])
    tablo = kal.kalibrasyon_tablosu(bloklar)
    assert tablo[-1][0] is None


def test_kalibre_uygula_dogru_blogu_buluyor():
    tablo = [(0.15, 0.05), (0.35, 0.30), (None, 0.60)]
    assert kal.kalibre_uygula(0.05, tablo) == 0.05
    assert kal.kalibre_uygula(0.20, tablo) == 0.30
    assert kal.kalibre_uygula(0.99, tablo) == 0.60


def test_kalibre_uygula_bos_tabloda_hata_vermez_degil_ic_ic_son_deger():
    tablo = [(None, 0.42)]
    assert kal.kalibre_uygula(0.0, tablo) == 0.42
    assert kal.kalibre_uygula(1.0, tablo) == 0.42
