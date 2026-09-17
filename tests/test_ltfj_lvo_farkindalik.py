"""ltfj_lvo_farkindalik.py testleri - METAR/TAF/AWOS degerlerinin dokumanin
kendi esikleriyle karsilastirilip GAYRI RESMI, hedge'li notlara cevrilmesi.
Hicbir zaman "LVO aktif/CAT II kullanilabilir/LVTO yapilabilir" gibi kesin
bir ifade uretilmemeli - her not "... olabilir. Resmi bir tespit degildir."
ile bitmeli."""
import ltfj_lvo_farkindalik as fark


def test_esik_dokumandaki_cat_ii_araliginin_ust_siniri():
    assert fark.CEILING_FARKINDALIK_ESIGI_FT == 200


def test_metar_tavan_yuksekse_not_uretilmez():
    assert fark.metar_tavan_notu({"gorus": 9999, "tavan": 5000}) is None


def test_metar_tavan_yoksa_not_uretilmez():
    assert fark.metar_tavan_notu({"gorus": 9999, "tavan": None}) is None


def test_metar_cozum_yoksa_not_uretilmez():
    assert fark.metar_tavan_notu(None) is None


def test_metar_tavan_dusukse_hedgeli_not_uretilir():
    not_ = fark.metar_tavan_notu({"gorus": 3000, "tavan": 100})
    assert not_ is not None
    assert "100 ft" in not_
    assert "oluşabilir. Resmî bir tespit değildir." in not_
    # kesin/resmi bir ifade ICERMEMELI
    assert "LVO aktif" not in not_
    assert "CAT II kullanılabilir" not in not_


def test_metar_tavan_esik_degerinin_kendisi_not_uretmez():
    """200 ft esigin KENDISI notu tetiklememeli (< kullanilir, <= degil)."""
    assert fark.metar_tavan_notu({"gorus": 9999, "tavan": 200}) is None


def test_taf_tavan_dusukse_not_uretilir():
    not_ = fark.taf_tavan_notu(150)
    assert not_ is not None
    assert "150 ft" in not_
    assert "TAF" in not_
    assert "oluşabilir. Resmî bir tespit değildir." in not_


def test_taf_tavan_yuksekse_veya_yoksa_not_uretilmez():
    assert fark.taf_tavan_notu(5000) is None
    assert fark.taf_tavan_notu(None) is None


def test_rvr_esik_ustundeyse_not_uretilmez():
    assert fark.rvr_notu("06R", "TDZ", 900) is None


def test_rvr_dusukse_en_derin_esikle_not_uretilir():
    """RVR=450 -> 800 ve 550 esiklerinin ALTINDA ama 400'un DEGIL; en derin
    (en kucuk) gecilen esik olan 550 kullanilmali."""
    not_ = fark.rvr_notu("06R", "TDZ", 450)
    assert not_ is not None
    assert "550 m eşiğinin" in not_
    assert "400 m eşiğinin" not in not_
    assert "06R TDZ" in not_
    assert "450 m" in not_
    assert "oluşabilir. Resmî bir tespit değildir." in not_


def test_rvr_cok_dusukse_en_derin_350_esigi_kullanilir():
    not_ = fark.rvr_notu("24R", "STOP-END", 100)
    assert "350 m eşiğinin" in not_
