"""ltfj_dis_kaynak_cache.py testleri.

En kritik iki test:
1) KISMİ HATA TOLERANSI - iki kaynaktan biri başarısız olursa diğerinin
   YENİ değeri yine de yazılmalı, başarısız olanın ESKİ değeri korunmalı.
2) BAYATLIK KONTROLÜ - oku() her alanı AYRI AYRI değerlendirmeli; biri
   taze biri bayat olabilir, ikisi birbirini etkilememeli."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

import ltfj_dis_kaynak_cache as dkc
import ltfj_rasat


class _SahteYanit:
    def __init__(self, json_data=None, status_code=200, json_error=False):
        self.status_code = status_code
        self._json_data = json_data
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("gecerli JSON degil")
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} hata", response=self)


ORNEK_METAR = "METAR LTFM 211050Z 18005KT 8000 BKN030 18/14 Q1013 NOSIG="


def _zaman(dk_once=0):
    return (datetime.now(timezone.utc) - timedelta(minutes=dk_once)).isoformat()


# --------------------------------------------------------- _acik_meteo_nem_cek
def test_acik_meteo_nem_cek_basarili():
    yanit = _SahteYanit({"current": {"relative_humidity_2m": 87}})
    with patch.object(dkc.requests, "get", return_value=yanit):
        assert dkc._acik_meteo_nem_cek() == 87


def test_acik_meteo_nem_cek_hata_govdesi_yukseltir():
    yanit = _SahteYanit({"error": True, "reason": "kota"})
    with patch.object(dkc.requests, "get", return_value=yanit):
        with pytest.raises(dkc.OnbellekHatasi, match="kota"):
            dkc._acik_meteo_nem_cek()


def test_acik_meteo_nem_cek_alan_eksikse_yukseltir():
    yanit = _SahteYanit({"current": {}})
    with patch.object(dkc.requests, "get", return_value=yanit):
        with pytest.raises(dkc.OnbellekHatasi):
            dkc._acik_meteo_nem_cek()


def test_acik_meteo_nem_cek_baglanti_hatasinda_requestexception_yukselir():
    with patch.object(dkc.requests, "get", side_effect=requests.ConnectionError("kopuk")):
        with pytest.raises(requests.RequestException):
            dkc._acik_meteo_nem_cek()


# --------------------------------------------------------- _komsu_tavan_cek
def test_komsu_tavan_cek_basarili():
    with patch.object(ltfj_rasat, "raporlari_cek", return_value=[
        {"tip": "METAR", "metin": ORNEK_METAR}]):
        tavan = dkc._komsu_tavan_cek()
    assert tavan == 3000   # BKN030 -> 3000 ft (BKN/OVC/VV tavan sayilir, SCT sayilmaz)


def test_komsu_tavan_cek_metar_yoksa_yukseltir():
    with patch.object(ltfj_rasat, "raporlari_cek", return_value=[
        {"tip": "TAF", "metin": "TAF LTFM ..."}]):
        with pytest.raises(dkc.OnbellekHatasi):
            dkc._komsu_tavan_cek()


def test_komsu_tavan_cek_ulasilamazsa_rasathatasi_yukselir():
    with patch.object(ltfj_rasat, "raporlari_cek",
                      side_effect=ltfj_rasat.AgHatasi("ulaşılamadı")):
        with pytest.raises(ltfj_rasat.RasatHatasi):
            dkc._komsu_tavan_cek()


# --------------------------------------------------------------- guncelle
def test_guncelle_ikisi_de_basarili_ikisini_de_yazar(tmp_path):
    dosya = tmp_path / "cache.json"
    with patch.object(dkc, "_acik_meteo_nem_cek", return_value=91), \
            patch.object(dkc, "_komsu_tavan_cek", return_value=1500):
        dkc.guncelle(dosya)

    veri = json.loads(dosya.read_text())
    assert veri["acik_meteo_nem_2m"] == 91
    assert veri["komsu_tavan_ozellik"] == 1500
    assert "acik_meteo_guncelleme" in veri and "komsu_guncelleme" in veri


def test_guncelle_bir_kaynak_basarisizsa_digerini_kirletmez(tmp_path):
    """KRİTİK: Open-Meteo çökse bile komşu istasyon güncellenmeli VE
    Open-Meteo'nun ESKİ değeri (varsa) korunmalı - komple çökmemeli."""
    dosya = tmp_path / "cache.json"
    dosya.write_text(json.dumps({
        "acik_meteo_nem_2m": 75, "acik_meteo_guncelleme": _zaman(dk_once=10),
    }))

    with patch.object(dkc, "_acik_meteo_nem_cek",
                      side_effect=dkc.OnbellekHatasi("Open-Meteo çöktü")), \
            patch.object(dkc, "_komsu_tavan_cek", return_value=2200):
        dkc.guncelle(dosya)

    veri = json.loads(dosya.read_text())
    assert veri["acik_meteo_nem_2m"] == 75          # eski deger korundu
    assert veri["komsu_tavan_ozellik"] == 2200        # yeni deger yazildi


def test_guncelle_komsu_kaynagi_ulasilamazsa_diger_yazilir(tmp_path):
    dosya = tmp_path / "cache.json"
    with patch.object(dkc, "_acik_meteo_nem_cek", return_value=60), \
            patch.object(dkc, "_komsu_tavan_cek",
                        side_effect=ltfj_rasat.AgHatasi("MGM cevap vermedi")):
        dkc.guncelle(dosya)

    veri = json.loads(dosya.read_text())
    assert veri["acik_meteo_nem_2m"] == 60
    assert "komsu_tavan_ozellik" not in veri


# ------------------------------------------------------------------- oku
def test_oku_taze_degerleri_dondurur(tmp_path):
    dosya = tmp_path / "cache.json"
    dosya.write_text(json.dumps({
        "acik_meteo_nem_2m": 88, "acik_meteo_guncelleme": _zaman(dk_once=5),
        "komsu_tavan_ozellik": 1000, "komsu_guncelleme": _zaman(dk_once=5),
    }))
    sonuc = dkc.oku(dosya)
    assert sonuc == {"acik_meteo_nem_2m": 88, "komsu_tavan_ozellik": 1000}


def test_oku_bayat_alani_none_dondurur_taze_alani_etkilemez(tmp_path):
    """KRİTİK: bir alan bayat, diğeri taze olabilir - birbirini kirletmemeli."""
    dosya = tmp_path / "cache.json"
    dosya.write_text(json.dumps({
        "acik_meteo_nem_2m": 88, "acik_meteo_guncelleme": _zaman(dk_once=5),
        "komsu_tavan_ozellik": 1000, "komsu_guncelleme": _zaman(dk_once=120),
    }))
    sonuc = dkc.oku(dosya, esik_dk=45)
    assert sonuc == {"acik_meteo_nem_2m": 88, "komsu_tavan_ozellik": None}


def test_oku_dosya_yoksa_ikisi_de_none(tmp_path):
    sonuc = dkc.oku(tmp_path / "yok.json")
    assert sonuc == {"acik_meteo_nem_2m": None, "komsu_tavan_ozellik": None}


def test_oku_bozuk_zaman_damgasi_cokmez_none_doner(tmp_path):
    dosya = tmp_path / "cache.json"
    dosya.write_text(json.dumps({
        "acik_meteo_nem_2m": 50, "acik_meteo_guncelleme": "bozuk-tarih",
    }))
    sonuc = dkc.oku(dosya)
    assert sonuc["acik_meteo_nem_2m"] is None


def test_oku_deger_null_yazilmissa_none_doner(tmp_path):
    """komşu tavanı gerçekten None olabilir (CAVOK) - bu bir hata değil,
    ama oku() yine de None döndürmeli (tabloda 'veri yok' bandına düşsün)."""
    dosya = tmp_path / "cache.json"
    dosya.write_text(json.dumps({
        "komsu_tavan_ozellik": None, "komsu_guncelleme": _zaman(dk_once=1),
    }))
    sonuc = dkc.oku(dosya)
    assert sonuc["komsu_tavan_ozellik"] is None


# ------------------------------------------------------------------ main
def test_main_oku_bayragi_aga_cikmaz(tmp_path):
    dosya = tmp_path / "cache.json"
    with patch.object(dkc, "guncelle") as mock_guncelle:
        kod = dkc.main(["--dosya", str(dosya), "--oku"])
    assert kod == 0
    mock_guncelle.assert_not_called()
