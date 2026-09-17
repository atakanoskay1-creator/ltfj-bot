"""ltfj_vfr.py testleri - METAR gorus/tavaninin VFR esikleriyle
karsilastirilmasi (ICAO Annex 2 Table 3-1, FL100 alti)."""
import ltfj_vfr as vfr


def test_esikler_dokumandaki_degerlerle_eslesiyor():
    assert vfr.VFR_GORUS_ESIGI_M == 5000
    assert vfr.VFR_TAVAN_ESIGI_FT == 1500


def test_gorus_ve_tavan_esik_ustunde_vfr_true():
    sonuc = vfr.vfr_degerlendir({"gorus": 9999, "tavan": 5000})
    assert sonuc["vfr"] is True
    assert sonuc["sebepler"] == []


def test_tavan_yok_ve_gorus_iyi_vfr_true():
    """tavan None -> anlamli bir BKN/OVC/VV katmani yok, iyi durum sayilir."""
    sonuc = vfr.vfr_degerlendir({"gorus": 9999, "tavan": None})
    assert sonuc["vfr"] is True


def test_gorus_dusuk_vfr_false_sebep_iceriyor():
    sonuc = vfr.vfr_degerlendir({"gorus": 3000, "tavan": 5000})
    assert sonuc["vfr"] is False
    assert any("Görüş" in s and "3000" in s for s in sonuc["sebepler"])


def test_tavan_dusuk_vfr_false_sebep_iceriyor():
    sonuc = vfr.vfr_degerlendir({"gorus": 9999, "tavan": 800})
    assert sonuc["vfr"] is False
    assert any("Tavan" in s and "800" in s for s in sonuc["sebepler"])


def test_ikisi_de_dusukse_iki_sebep_de_var():
    sonuc = vfr.vfr_degerlendir({"gorus": 1000, "tavan": 200})
    assert sonuc["vfr"] is False
    assert len(sonuc["sebepler"]) == 2


def test_esik_deger_tam_ustunde_degil_esittir_vfr_true():
    """5000 m ve 1500 ft esik degerlerinin KENDISI VFR sayilmali (< kullanilir, <= degil)."""
    sonuc = vfr.vfr_degerlendir({"gorus": 5000, "tavan": 1500})
    assert sonuc["vfr"] is True


def test_gorus_yok_vfr_none_donuyor():
    sonuc = vfr.vfr_degerlendir({"gorus": None, "tavan": 5000})
    assert sonuc["vfr"] is None
    assert len(sonuc["sebepler"]) == 1
