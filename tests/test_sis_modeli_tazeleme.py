"""sis_modeli/tazeleme.py - HOLDOUT TAZELEME denemesi testleri.

Bu betik AYRI TUTULUR (canliya baglanmaz); en kritik test genisletilmis_
foldlar()'in bolme.foldlar()'in guvenlik kelepcesini SADECE kendi, acikca
adlandirilmis fonksiyonunda ve BILEREK atladigini, bolme.py'ye dokunmadigini
dogrulamaktir."""
from sis_modeli import bolme
from sis_modeli.tazeleme import GENISLETILMIS_TEST_YILLARI, genisletilmis_foldlar


def test_normal_foldlar_degismeden_korunuyor():
    """Yeni fold'lar EKLENIYOR, mevcut (holdout'a dokunmayan) fold'lar
    degismiyor."""
    normal = bolme.foldlar()
    genis = genisletilmis_foldlar()
    assert genis[:len(normal)] == normal


def test_ekstra_foldlar_holdout_yillarini_sirayla_test_yapiyor():
    normal = bolme.foldlar()
    ekstra = genisletilmis_foldlar()[len(normal):]
    assert [test for _, test in ekstra] == [(y,) for y in GENISLETILMIS_TEST_YILLARI]


def test_ekstra_foldlar_genisleyen_pencere():
    """Her ekstra fold KENDINDEN ONCEKI TUM yillarla egitiliyor - bir onceki
    holdout yili da dahil (2026'nin egitimi 2025'i icerir)."""
    normal = bolme.foldlar()
    ekstra = genisletilmis_foldlar()[len(normal):]
    for egitim_yillari, test_yillari in ekstra:
        assert max(egitim_yillari) == min(test_yillari) - 1
        assert min(egitim_yillari) == bolme.ILK_YIL


def test_ekstra_foldlar_gelecege_sizmiyor():
    for egitim_yillari, test_yillari in genisletilmis_foldlar():
        assert max(egitim_yillari) < min(test_yillari)
