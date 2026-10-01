"""sis_modeli/veri_cek_rvr.py - pist ucu bazli RVR cikarimi (ag YOK)."""
import csv
import gzip

import pytest

from sis_modeli import veri_cek_rvr as vr


@pytest.mark.parametrize("metin,beklenen", [
    ("LTFJ 010350Z 03004KT 9999 R24L/0450N R24R/0600U R06R/P2000 BCFG 08/07 Q1020",
     {"rvr_06": 2000, "rvr_24": 450, "rvr_min": 450,
      "rvr_ham": "R24L/0450N R24R/0600U R06R/P2000"}),
    ("LTFJ 120350Z 03004KT 0150 R06/M0050 R24/0600V1000U FG VV001 07/07 Q1020",
     {"rvr_06": 50, "rvr_24": 600, "rvr_min": 50, "rvr_ham": "R06/M0050 R24/0600V1000U"}),
    ("LTFJ 010350Z 03004KT 9999 NSC 08/04 Q1020 NOSIG",
     {"rvr_06": None, "rvr_24": None, "rvr_min": None, "rvr_ham": ""}),
    # trend/RMK'daki grup sayilmaz
    ("LTFJ 010350Z 03004KT 3000 BR 08/07 Q1020 TEMPO 0400 R24L/0300 FG",
     {"rvr_06": None, "rvr_24": None, "rvr_min": None, "rvr_ham": ""}),
])
def test_rvr_cikar(metin, beklenen):
    assert vr.rvr_cikar(metin) == beklenen


def test_satirlari_coz_istasyon_ds3505_ve_tekrar():
    ham = ("station,valid,metar\n"
           "LTFJ,2015-01-10 03:20,LTFJ 100320Z 03004KT 0500 R24/0450N FG 05/05 Q1020\n"
           "LTFJ,2015-01-10 03:20,LTFJ 100320Z 03004KT 0500 R24/0400N FG 05/05 Q1020\n"
           "LTFJ,2011-03-01 10:20,LTBA 011020Z 03004KT 9999 FEW030 10/02 Q1020\n"
           "LTFJ,2007-01-01 00:00,LTFJ 010000Z AUTO 00000KT 7SM IEM_DS3505\n"
           "LTFJ,2015-01-10 03:50,LTFJ 100350Z 03004KT 9999 NSC 06/05 Q1020\n")
    satirlar, atlanan = vr.satirlari_coz(ham)
    assert [(s["zaman"], s["rvr_min"]) for s in satirlar] == \
        [("2015-01-10T03:20", 450), ("2015-01-10T03:50", None)]
    assert atlanan == {"ayni zaman tekrar": 1, "baska istasyon (LTBA)": 1,
                       "IEM_DS3505 (ISD'den yeniden kurulmus)": 1}


def test_arsivi_uret_bos_rvr_alanlarini_bos_yazar(monkeypatch, tmp_path):
    ham = ("station,valid,metar\n"
           "LTFJ,2015-01-10 03:20,LTFJ 100320Z 03004KT 0500 R24/0450N FG 05/05 Q1020\n"
           "LTFJ,2015-01-10 03:50,LTFJ 100350Z 03004KT 9999 NSC 06/05 Q1020\n")
    monkeypatch.setattr(vr, "_yil_indir", lambda yil, oturum, istasyon: ham)
    cikti = tmp_path / "rvr.csv.gz"
    ozet = vr.arsivi_uret(2015, 2015, cikti)
    assert ozet == {"gozlem": 2, "rvrli": 1, "alti800": 1, "atlanan": 0}

    with gzip.open(cikti, "rt", encoding="utf-8") as f:
        satirlar = list(csv.DictReader(f))
    assert satirlar[1] == {"zaman": "2015-01-10T03:50", "rvr_06": "", "rvr_24": "",
                           "rvr_min": "", "rvr_ham": ""}
