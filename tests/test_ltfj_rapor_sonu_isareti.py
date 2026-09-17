"""Rapor sonu isareti '=' token'a yapisik geldiginde SON ALAN kaybolmamali.

Bu gercek bir hataydi: '=' standart METAR/TAF bitis isaretidir ve son
token'a YAPISIK gelir ('... Q1021=' / '... VV002='). Duz metin.split()
ile o token hicbir deseni tutmuyor ve SESSIZCE dusuyordu - METAR sondaki
QNH'siz, TAF ise en dusuk tavanini kaybetmis olarak cozuluyordu.

MGM'nin observationText alani '=' tasimadigi icin canli akista
gorunmuyordu; resmi bultenlerden gelen (ve elle yapistirilan) raporlar ise
'=' ile biter. Yani hata gizliydi, yok degildi.
"""
import ltfj_lvo_farkindalik as f
import ltfj_pist as pist
from ltfj_analiz import metar_coz, tokenla


def test_tokenla_yapisik_esittiri_atiyor():
    assert tokenla("A B C=") == ["A", "B", "C"]
    assert tokenla("A B = C") == ["A", "B", "C"]      # ayri duran '=' de dusmeli
    assert tokenla("A  B   C") == ["A", "B", "C"]     # bosluk normalize


def test_tokenla_ortadaki_veriyi_bozmuyor():
    """'=' yalnizca SONDAN kirpilir; token icindeki karakterler korunur."""
    assert tokenla("18005KT 9999 BKN002 Q1021") == ["18005KT", "9999", "BKN002", "Q1021"]


# ----------------------------------------------------------------- METAR
def test_metar_son_alan_qnh_kaybolmuyor():
    assert metar_coz("LTFJ 172120Z 01003KT 0400 FG 07/07 Q1021=")["qnh"] == 1021


def test_metar_son_alan_tavan_kaybolmuyor():
    d = metar_coz("LTFJ 172120Z 01003KT 0400 FG 07/07 Q1021 BKN002=")
    assert d["tavan"] == 200


def test_metar_esitsiz_hali_ayni_sonucu_veriyor():
    """Duzeltme davranisi degistirmemeli - yalnizca kaybi onlemeli."""
    esitli = "LTFJ 172120Z 01003KT 0400 FG 07/07 Q1021 BKN002="
    assert metar_coz(esitli) == metar_coz(esitli.rstrip("="))


def test_metar_cavok_ve_nosig_ile_esitli():
    d = metar_coz("METAR LTFJ 171120Z 18005KT CAVOK 22/14 Q1015 NOSIG=")
    assert d["cavok"] and d["nosig"] and d["qnh"] == 1015


# ------------------------------------------------------------------- TAF
def test_taf_son_token_tavan_kaybolmuyor():
    taf = ("TAF LTFJ 171700Z 1718/1818 02005KT 9999 SCT030 "
           "TEMPO 1722/1804 0300 FG VV001=")
    assert f.taf_en_dusuk_tavan_ft(taf) == 100


def test_taf_notu_son_token_tavanla_ciksin():
    taf = "TAF LTFJ 171700Z 1718/1818 02005KT 9999 SCT030 TEMPO 1722/1804 0300 FG VV001="
    assert f.taf_tavan_notu(f.taf_en_dusuk_tavan_ft(taf)) is not None


def test_taf_ortadaki_tavan_hala_bulunuyor():
    """Regresyon: duzeltme, zaten calisan yolu bozmamali."""
    taf = ("TAF LTFJ 171700Z 1718/1818 02005KT 0300 FG VV001 "
           "BECMG 1809/1812 6000 SCT020=")
    assert f.taf_en_dusuk_tavan_ft(taf) == 100


# ----------------------------------------------------------------- trend
def test_trend_metninde_esittir_gorunmuyor():
    t = pist.metar_trendi("LTFJ 172120Z 01003KT 9999 SCT030 07/05 Q1021 TEMPO 0400 FG=")
    assert t == "Geçici: 0400 FG"


def test_trend_esitsiz_hali_ayni():
    a = pist.metar_trendi("LTFJ 172120Z 01003KT 9999 SCT030 07/05 Q1021 TEMPO 0400 FG=")
    b = pist.metar_trendi("LTFJ 172120Z 01003KT 9999 SCT030 07/05 Q1021 TEMPO 0400 FG")
    assert a == b
