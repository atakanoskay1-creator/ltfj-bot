"""sis_modeli/tavan_tablo.py testleri.

En kritik test: sis_olasilik (dondurulmus Model A'nin cikisi) artik
ADAY_CIFTLER icinde bir EKSEN olarak var - tablo_kur/tahmin bunu diger
degiskenler gibi genel olarak isleyebilmeli, ozel bir dal gerekmemeli."""
from sis_modeli.tavan_tablo import ADAY_CIFTLER, tablo_kur, tahmin


def _kayit(sis_olasilik, tavan_ozellik, hedef, gun="2024-01-01"):
    return {"sis_olasilik": sis_olasilik, "tavan_ozellik": tavan_ozellik,
           "hedef": hedef, "gun": gun}


def test_sis_olasilik_aday_ciftlerde_hub_olarak_var():
    """spread'in ADAY_CIFTLER'daki orijinal esleri (gorus, tavan_ozellik,
    saat, ruzgar_kuzey) simdi sis_olasilik icin de ayni simetride var mi?"""
    spread_esleri = {b for a, b in ADAY_CIFTLER if a == "spread"}
    sis_esleri = {b for a, b in ADAY_CIFTLER if a == "sis_olasilik"}
    assert spread_esleri <= sis_esleri | {"gorus"}   # gorus ayrica var
    assert ("sis_olasilik", "tavan_ozellik") in ADAY_CIFTLER


def test_tablo_kur_sis_olasilik_eksenini_genel_olarak_isliyor():
    egitim = ([_kayit(0.01, 2000, False) for _ in range(50)]
             + [_kayit(0.2, 800, True) for _ in range(50)])
    tablo = tablo_kur(egitim, "sis_olasilik", "tavan_ozellik")
    assert tablo["alan_a"] == "sis_olasilik" and tablo["alan_b"] == "tavan_ozellik"
    # Yuksek sis_olasilik + dusuk tavan hucresi, dusuk sis_olasilik + yuksek
    # tavan hucresinden daha yuksek olasilik vermeli.
    yuksek_risk = tahmin(tablo, {"sis_olasilik": 0.2, "tavan_ozellik": 800})
    dusuk_risk = tahmin(tablo, {"sis_olasilik": 0.01, "tavan_ozellik": 2000})
    assert yuksek_risk > dusuk_risk


def test_tahmin_tabloda_olmayan_hucrede_taban_dondurur():
    egitim = [_kayit(0.01, 2000, False), _kayit(0.01, 2000, True)]
    tablo = tablo_kur(egitim, "sis_olasilik", "tavan_ozellik")
    # asiri uc bir deger - a priori bantlarin disinda bile olsa (veri yok
    # hucresi) crash etmemeli, taban dondurmeli.
    p = tahmin(tablo, {"sis_olasilik": None, "tavan_ozellik": None})
    assert p == tablo["taban"]
