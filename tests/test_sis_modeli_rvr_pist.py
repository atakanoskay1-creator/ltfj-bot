"""sis_modeli/rvr_pist.py - parcali sis anlarinda pist uclarindaki RVR."""
import pytest

from sis_modeli import rvr_pist as rp


@pytest.mark.parametrize("metin,beklenen", [
    ("LTFJ 010350Z 03004KT 9999 R24L/0450 R24R/0600 R06R/P2000 BCFG 08/07 Q1020", True),
    ("LTFJ 010350Z 03004KT 6000 PRFG BR 08/07 Q1020", True),
    ("LTFJ 010350Z 03004KT 0300 R24L/0350 FG VV002 07/07 Q1020", False),
    ("LTFJ 010350Z 03004KT 0800 BCFG FG 07/07 Q1020", False),
    ("LTFJ 010350Z 03004KT 9999 BR 08/07 Q1020 TEMPO 2000 BCFG", False),
    ("LTFJ 010350Z 03004KT 9999 NSC 08/04 Q1020 RMK BCFG E", False),
])
def test_parcali_sis_mi(metin, beklenen):
    assert rp.parcali_sis_mi(metin) == beklenen


@pytest.mark.parametrize("isaret,deger,beklenen", [
    ("", 450, "<550"), ("M", 50, "<550"), ("", 550, "550-1499"),
    ("", 1400, "550-1499"), ("", 1500, ">=1500"), ("P", 400, ">=1500"),
])
def test_rvr_sinifi(isaret, deger, beklenen):
    assert rp.rvr_sinifi(isaret, deger) == beklenen


def test_say_pist_uclari_istasyon_ve_rmk():
    satirlar = [
        {"metar": "LTFJ 010350Z 03004KT 9999 R24L/0450 R24R/0600 R06R/P2000 BCFG 08/07 Q1020 NOSIG"},
        {"metar": "LTFJ 010420Z 03004KT 9999 PRFG 08/07 Q1020"},
        {"metar": "LTBA 010350Z 03004KT 9999 R23/0300 BCFG 08/07 Q1020"},
        {"metar": "LTFJ 010450Z 03004KT 0300 R24L/0350 FG VV002 07/07 Q1020"},
        {"metar": "LTFJ 010520Z AUTO 03004KT 7SM 08/07 A3012 RMK IEM_DS3505"},
    ]
    n, sonuc = rp.say(satirlar)
    assert n == 2
    assert sonuc == {"R24 <550": 1, "R24 550-1499": 1, "R06 >=1500": 1, "RVR grubu yok": 1}
