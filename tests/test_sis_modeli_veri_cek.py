"""sis_modeli/veri_cek.py - IEM satirlarinin istasyon ve kaynak kontrolu.

Olculdu (01.10.2026): IEM station=LTFJ istegine 2011 icin LTBA METAR'lari
dondurdu ('station' sutunu yine LTFJ); 2005-2008 ise NCEI ISD'den yeniden
kurulmus (IEM_DS3505) satirlardi. Ornek satirlar kullanicinin indirdigi
gercek IEM ciktisindan."""
import pytest

from sis_modeli import veri_cek as vc

BASLIK = "station,valid,metar\n"


@pytest.mark.parametrize("metin,beklenen", [
    ("LTFJ 010020Z 04007KT 9999 FEW030 08/06 Q1012", "LTFJ"),
    ("METAR LTFJ 010020Z 04007KT 9999 08/06 Q1012", "LTFJ"),
    ("SPECI LTFJ 290429Z 03010KT 2200 BR 15/14 Q1017", "LTFJ"),
    ("COR LTFJ 290750Z 03011KT 9999 BKN025 19/17 Q1019", "LTFJ"),
    ("LTBA 312050Z 32015KT 7000 -SHRA FEW007 07/07 Q1009", "LTBA"),
    ("", None),
    ("010020Z 04007KT", None),
])
def test_metar_istasyonu(metin, beklenen):
    assert vc.metar_istasyonu(metin) == beklenen


def test_baska_istasyon_ve_yeniden_kurulmus_satirlar_atilir():
    ham = BASLIK + "\n".join([
        "LTFJ,2011-12-31 20:50,LTBA 312050Z 32015KT 7000 -SHRA FEW007 SCT025 BKN080 07/07 Q1009 BECMG 03012KT",
        "LTFJ,2005-01-01 00:20,LTFJ 010020Z AUTO 04007KT 7SM 08/06 A3012 RMK T00800060 IEM_DS3505",
        "LTFJ,2012-01-01 00:20,LTFJ 010020Z 04007KT 9999 FEW030 08/06 Q1012 NOSIG",
        "LTFJ,2012-01-01 00:26,SPECI LTFJ 010026Z 04007KT 0800 FG VV002 06/06 Q1012",
    ]) + "\n"
    satirlar, atlanan = vc._satirlari_coz(ham, "LTFJ")
    assert [s["zaman"] for s in satirlar] == ["2012-01-01T00:20", "2012-01-01T00:26"]
    assert atlanan == {"baska istasyon (LTBA)": 1,
                       "IEM_DS3505 (ISD'den yeniden kurulmus)": 1}


def test_komsu_istasyon_kendi_kodunu_kabul_eder():
    ham = BASLIK + "LTFM,2020-01-01 00:20,LTFM 010020Z 04007KT 9999 FEW030 08/06 Q1012\n"
    satirlar, atlanan = vc._satirlari_coz(ham, "LTFM")
    assert len(satirlar) == 1 and not atlanan
    assert vc._satirlari_coz(ham, "LTFJ")[1] == {"baska istasyon (LTFM)": 1}
