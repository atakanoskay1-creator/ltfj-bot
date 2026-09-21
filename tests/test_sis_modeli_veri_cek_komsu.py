"""sis_modeli/veri_cek_komsu.py testleri.

Bu betik veri_cek.arsivi_uret'i DOGRUDAN yeniden kullanir - ag/ayristirma
mantigi zaten o tarafta test edilir (varsa). Burada sadece dogru
istasyon/dosya adiyla cagrildigini ve coklu istasyonda birinin hatasinin
NASIL raporlandigini dogrulariz."""
from pathlib import Path
from unittest.mock import patch

import pytest

import sis_modeli.veri_cek_komsu as vk
from sis_modeli.veri_cek import VeriCekmeHatasi


def test_cikti_yolu_istasyon_koduna_gore_isimlendirir():
    yol = vk.cikti_yolu("LTFM", Path("/tmp/veri"))
    assert yol == Path("/tmp/veri/komsu_ltfm_ozellik.csv.gz")


def test_main_her_istasyon_icin_arsivi_uret_cagirir(tmp_path):
    dosya = tmp_path / "x.csv.gz"
    dosya.write_bytes(b"")

    with patch("sis_modeli.veri_cek_komsu.arsivi_uret") as mock_uret:
        mock_uret.return_value = {"gozlem": 10, "dosya": str(dosya),
                                  "sis": 1, "lvo": 0, "atlanan": {}}
        kod = vk.main(["--istasyonlar", "LTFM", "LTBA",
                       "--baslangic", "2020", "--bitis", "2021",
                       "--dizin", str(tmp_path)])

    assert kod == 0
    assert mock_uret.call_count == 2
    cagrilar = [c.args for c in mock_uret.call_args_list]
    assert cagrilar[0] == (2020, 2021, vk.cikti_yolu("LTFM", tmp_path), "LTFM")
    assert cagrilar[1] == (2020, 2021, vk.cikti_yolu("LTBA", tmp_path), "LTBA")


def test_main_hata_durumunda_1_donuyor_ve_diger_istasyonlara_gecmiyor(tmp_path):
    with patch("sis_modeli.veri_cek_komsu.arsivi_uret",
              side_effect=VeriCekmeHatasi("kalici hata")) as mock_uret:
        kod = vk.main(["--istasyonlar", "LTFM", "LTBA",
                       "--baslangic", "2020", "--bitis", "2020",
                       "--dizin", str(tmp_path)])

    assert kod == 1
    assert mock_uret.call_count == 1   # LTFM'de durdu, LTBA'ya gecmedi


def test_varsayilan_istasyon_ltfm():
    assert vk.VARSAYILAN_ISTASYONLAR == ("LTFM",)
