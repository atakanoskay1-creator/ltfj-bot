"""sis_modeli/tavan_dis_kaynak_model.py testleri.

EN KRİTİK test: wf_karsilastir()'in EŞLEŞTİRİLMİŞ karşılaştırma için
kritik garantisi - bir fold'da HERHANGİ BİR spesifikasyon (IRLS)
yakınsamazsa, o fold TÜM spesifikasyonlar için atlanmalı. Aksi halde
eslesmis_fark_araligi'ye giden iki tahmin listesi FARKLI fold kümelerinden
gelir ve indeks bazlı eşleştirme SESSİZCE YANLIŞ hizalanır - gerçekten
yaşanan bir riskti (bkz. modül dokümantasyonu)."""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

import sis_modeli.tavan_dis_kaynak_model as tdkm
from sis_modeli import model as model_mod


def _kayitlar_uret(yillar=(2017, 2018, 2019, 2020)):
    kayitlar = []
    for yil in yillar:
        for g in range(3):
            dt = datetime(yil, 1, 1) + timedelta(days=g)
            kayitlar.append({"dt": dt, "gun": dt.strftime("%Y-%m-%d"),
                             "hedef": g == 0, "x": 1.0, "y": 1.0})
    return kayitlar


def test_wf_karsilastir_bir_spesifikasyon_yakinsamazsa_fold_tum_spesifikasyonlarda_atlanir():
    cagri_sayisi = {"A": 0, "B": 0}

    def sahte_egit_secerek(eg, alanlar, **kwargs):
        ad = "B" if alanlar == ["y"] else "A"
        cagri_sayisi[ad] += 1
        if ad == "B" and cagri_sayisi[ad] == 2:
            raise model_mod.Yakinsamadi("test: yakınsamadı")
        return ([0.0], {}, 1.0)

    def sahte_olasilik(katsayilar, kayit, tablolar):
        return 0.5

    gelistirme = _kayitlar_uret()
    with patch.object(tdkm.model, "egit_secerek", sahte_egit_secerek), \
            patch.object(tdkm.model, "olasilik", sahte_olasilik):
        sonuc = tdkm.wf_karsilastir(gelistirme, [("A", ["x"]), ("B", ["y"])])

    assert sonuc["atlanan"] == [(2020,)]
    # fold2 (test=2020) İKİ spesifikasyon için de dışarıda - yalnızca
    # fold1'in (test=2019) kayıtları kalmalı.
    n = len(sonuc["gercek"])
    assert n > 0
    assert len(sonuc["kayitlar"]) == n
    assert len(sonuc["spesifikasyon"]["A"]["tahmin"]) == n
    assert len(sonuc["spesifikasyon"]["B"]["tahmin"]) == n
    assert all(r["dt"].year == 2019 for r in sonuc["kayitlar"])


def test_wf_karsilastir_hicbir_seyi_atlamiyorsa_tum_foldlar_kullanilir():
    def sahte_egit_secerek(eg, alanlar, **kwargs):
        return ([0.0], {}, 1.0)

    def sahte_olasilik(katsayilar, kayit, tablolar):
        return 0.3

    gelistirme = _kayitlar_uret()
    with patch.object(tdkm.model, "egit_secerek", sahte_egit_secerek), \
            patch.object(tdkm.model, "olasilik", sahte_olasilik):
        sonuc = tdkm.wf_karsilastir(gelistirme, [("A", ["x"])])

    assert sonuc["atlanan"] == []
    assert {r["dt"].year for r in sonuc["kayitlar"]} == {2019, 2020}


def test_spesifikasyonlar_temel_ve_dis_kaynagin_birlesimi():
    d = dict(tdkm.SPESIFIKASYONLAR)
    assert d["TEMEL"] == tdkm.TEMEL
    assert set(d["TEMEL + ikisi"]) == set(tdkm.TEMEL) | set(tdkm.DIS_KAYNAK)
    assert set(d["TEMEL + nem"]) == set(tdkm.TEMEL) | {"acik_meteo_nem_2m"}
    assert set(d["TEMEL + komşu tavan"]) == set(tdkm.TEMEL) | {"komsu_tavan_ozellik"}


def test_hazirla_zinciri_dogru_sirayla_cagirir(tmp_path):
    veri_yolu = tmp_path / "x.csv.gz"
    veri_yolu.write_bytes(b"")

    with patch.object(tdkm, "veri_oku", return_value="ham") as mock_oku, \
            patch.object(tdkm.tavan, "hazirla", return_value="tavan_hazir") as mock_tavan, \
            patch.object(tdkm, "sis_olasiligi_ekle", return_value="sis_eklendi") as mock_sis, \
            patch.object(tdkm, "dis_kaynak_ekle", return_value="son") as mock_dis:
        sonuc = tdkm.hazirla(veri_yolu, 500)

    assert sonuc == "son"
    mock_oku.assert_called_once_with(veri_yolu)
    mock_tavan.assert_called_once_with("ham", esik_ft=500)
    mock_sis.assert_called_once_with("tavan_hazir")
    mock_dis.assert_called_once_with("sis_eklendi")


def test_main_veri_yoksa_hata_ile_cikar(tmp_path, capsys):
    kod = tdkm.main(["--veri", str(tmp_path / "yok.csv.gz")])
    assert kod == 1
    assert "yok" in capsys.readouterr().err.lower()
