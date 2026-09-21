"""sis_modeli/veri_cek_acik_meteo.py testleri.

En kritik iki test:
1) API'nin beklenen degiskenlerden birini DONDURMEDIGI durum sessizce bos
   sutun URETMEMELI - acik bir AcikMeteoHatasi firlatmali.
2) Open-Meteo'nun DAKIKALIK istek limiti govdesi ("...limit exceeded...")
   KALICI bir hata gibi hemen basarisiz OLMAMALI - bu, ilk gercek calistirmada
   (2026-09-21) gercekten yasanan bir arizaydi (bkz. modul dokumantasyonu);
   retry edilmeli, diger (yanlis parametre gibi) kalici hatalardan AYRI ele
   alinmali."""
import csv
import gzip
from unittest.mock import MagicMock, patch

import pytest
import requests

import sis_modeli.veri_cek_acik_meteo as ak


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


def _saatlik_ornek(n=2, baslangic_saat=0):
    zamanlar = [f"2003-01-01T{baslangic_saat + i:02d}:00" for i in range(n)]
    d = {"time": zamanlar}
    for v in ak.HOURLY_TUMU:
        d[v] = [float(i) for i in range(n)]
    return d


@pytest.fixture(autouse=True)
def _uyumasin(monkeypatch):
    monkeypatch.setattr(ak.time, "sleep", lambda s: None)


# --------------------------------------------------------- _donem_indir
def test_donem_indir_basarili_tum_degiskenleri_dondurur():
    oturum = MagicMock()
    oturum.get.return_value = _SahteYanit({"hourly": _saatlik_ornek()})

    saatlik = ak._donem_indir(2003, 2003, oturum)

    assert saatlik["time"] == ["2003-01-01T00:00", "2003-01-01T01:00"]
    for v in ak.HOURLY_TUMU:
        assert v in saatlik


def test_donem_indir_hiz_limiti_retry_edilir_sonunda_basarili_olur():
    """Ilk gercek calistirmada (2026-09-21) tam olarak bu govde donmustu:
    'Minutely API request limit exceeded...'. Bu KALICI degil, RETRY
    edilmeli - yanlis parametre adi gibi hemen basarisiz OLMAMALI."""
    hiz_limiti = _SahteYanit(
        {"error": True,
         "reason": "Minutely API request limit exceeded. Please try again "
                   "in one minute."})
    basarili = _SahteYanit({"hourly": _saatlik_ornek()})
    oturum = MagicMock()
    oturum.get.side_effect = [hiz_limiti, basarili]

    saatlik = ak._donem_indir(2003, 2003, oturum)
    assert saatlik["time"] == ["2003-01-01T00:00", "2003-01-01T01:00"]
    assert oturum.get.call_count == 2


def test_donem_indir_hiz_limiti_surekliyse_deneme_sayisi_kadar_retry_sonra_hata():
    oturum = MagicMock()
    oturum.get.return_value = _SahteYanit(
        {"error": True, "reason": "Hourly API request limit exceeded."})

    with pytest.raises(ak.AcikMeteoHatasi, match="limit exceeded"):
        ak._donem_indir(2003, 2003, oturum)
    assert oturum.get.call_count == ak.DENEME


def test_donem_indir_api_hata_govdesi_hiz_limiti_disinda_hemen_basarisiz():
    """Yanlis parametre adi gibi KALICI bir hata retry edilmemeli - ayni
    istek tekrar aynen basarisiz olur, denemeleri bosa harcamanin anlami
    yok (yanlis parametre hicbir zaman kendiliginden duzelmez)."""
    oturum = MagicMock()
    oturum.get.return_value = _SahteYanit(
        {"error": True, "reason": "Invalid parameter hourly"})

    with pytest.raises(ak.AcikMeteoHatasi, match="Invalid parameter"):
        ak._donem_indir(2003, 2003, oturum)
    assert oturum.get.call_count == 1


def test_donem_indir_hourly_alani_yoksa_hata():
    oturum = MagicMock()
    oturum.get.return_value = _SahteYanit({"latitude": 40.9})

    with pytest.raises(ak.AcikMeteoHatasi, match="hourly"):
        ak._donem_indir(2003, 2003, oturum)


def test_donem_indir_eksik_degisken_sessizce_atlanmiyor_acik_hata_veriyor():
    saatlik = _saatlik_ornek()
    del saatlik["temperature_2m"]
    oturum = MagicMock()
    oturum.get.return_value = _SahteYanit({"hourly": saatlik})

    with pytest.raises(ak.AcikMeteoHatasi, match="temperature_2m"):
        ak._donem_indir(2003, 2003, oturum)


def test_donem_indir_baglanti_hatasi_deneme_sayisi_kadar_retry_edilir():
    oturum = MagicMock()
    oturum.get.side_effect = requests.ConnectionError("kopuk")

    with pytest.raises(ak.AcikMeteoHatasi):
        ak._donem_indir(2003, 2003, oturum)
    assert oturum.get.call_count == ak.DENEME


def test_donem_indir_5xx_jsonsuz_govde_retry_edilip_sonunda_hata_verir():
    oturum = MagicMock()
    oturum.get.return_value = _SahteYanit(status_code=503, json_error=True)

    with pytest.raises(ak.AcikMeteoHatasi):
        ak._donem_indir(2003, 2003, oturum)
    assert oturum.get.call_count == ak.DENEME


def test_donem_indir_aralik_parametreleri_dogru_gonderilir():
    oturum = MagicMock()
    oturum.get.return_value = _SahteYanit({"hourly": _saatlik_ornek()})

    ak._donem_indir(2010, 2015, oturum)

    _, kwargs = oturum.get.call_args
    assert kwargs["params"]["start_date"] == "2010-01-01"
    assert kwargs["params"]["end_date"] == "2015-12-31"


# --------------------------------------------------------- arsivi_uret
def test_arsivi_uret_coklu_yili_tek_csvye_yazar(tmp_path):
    yillik = {2003: _saatlik_ornek(2), 2004: _saatlik_ornek(3)}

    def sahte_get(url, params=None, timeout=None):
        yil = int(params["start_date"][:4])
        return _SahteYanit({"hourly": yillik[yil]})

    oturum = MagicMock()
    oturum.get.side_effect = sahte_get
    oturum.__enter__.return_value = oturum
    oturum.__exit__.return_value = False

    with patch.object(ak.requests, "Session", return_value=oturum):
        cikti = tmp_path / "acik_meteo.csv.gz"
        ozet = ak.arsivi_uret(2003, 2004, cikti, yil_parca=1)

    assert ozet["gozlem"] == 5
    with gzip.open(cikti, "rt", newline="") as f:
        satirlar = list(csv.DictReader(f))
    assert len(satirlar) == 5
    assert satirlar[0]["zaman"] == "2003-01-01T00:00"
    assert satirlar[0]["temperature_2m"] == "0.0"
    assert set(satirlar[0]) == {"zaman"} | set(ak.HOURLY_TUMU)


def test_arsivi_uret_yil_parca_istek_sayisini_azaltir(tmp_path):
    """4 yillik araligi 2'lik dilimlerle cekmek TEK bir istekte 2 yili
    birden almali - 4 ayri istek degil, 2 istek."""
    oturum = MagicMock()
    oturum.get.return_value = _SahteYanit({"hourly": _saatlik_ornek(2)})
    oturum.__enter__.return_value = oturum
    oturum.__exit__.return_value = False

    with patch.object(ak.requests, "Session", return_value=oturum):
        ak.arsivi_uret(2003, 2006, tmp_path / "x.csv.gz", yil_parca=2)

    assert oturum.get.call_count == 2
    ilk_parametreler = oturum.get.call_args_list[0].kwargs["params"]
    assert ilk_parametreler["start_date"] == "2003-01-01"
    assert ilk_parametreler["end_date"] == "2004-12-31"


def test_arsivi_uret_dilimler_arasi_bekler_ama_ilk_istekten_once_beklemez(tmp_path):
    oturum = MagicMock()
    oturum.get.return_value = _SahteYanit({"hourly": _saatlik_ornek(2)})
    oturum.__enter__.return_value = oturum
    oturum.__exit__.return_value = False

    with patch.object(ak, "time") as sahte_time, \
            patch.object(ak.requests, "Session", return_value=oturum):
        ak.arsivi_uret(2003, 2006, tmp_path / "x.csv.gz", yil_parca=2)

    sahte_time.sleep.assert_called_once_with(ak.ISTEKLER_ARASI_BEKLEME)


def test_arsivi_uret_hata_yukseltilir(tmp_path):
    oturum = MagicMock()
    oturum.get.return_value = _SahteYanit(
        {"error": True, "reason": "Invalid parameter hourly"})
    oturum.__enter__.return_value = oturum
    oturum.__exit__.return_value = False

    with patch.object(ak.requests, "Session", return_value=oturum):
        with pytest.raises(ak.AcikMeteoHatasi, match="Invalid parameter"):
            ak.arsivi_uret(2003, 2003, tmp_path / "x.csv.gz", yil_parca=1)
