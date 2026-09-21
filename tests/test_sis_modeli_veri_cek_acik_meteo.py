"""sis_modeli/veri_cek_acik_meteo.py testleri.

En kritik test: API'nin beklenen degiskenlerden birini DONDURMEDIGI durum
sessizce bos sutun URETMEMELI - acik bir AcikMeteoHatasi firlatmali. Bu
betigin ag sozlesmesi bu ortamdan canli dogrulanamadigi icin (egress proxy
open-meteo.com'u engelliyor), "yanlis param adi -> acik hata" davranisi
GitHub Actions'ta ilk calistirmada sorunu hemen yuzeye cikarmak icin sart."""
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


# --------------------------------------------------------- _yil_indir
def test_yil_indir_basarili_tum_degiskenleri_dondurur():
    oturum = MagicMock()
    oturum.get.return_value = _SahteYanit({"hourly": _saatlik_ornek()})

    saatlik = ak._yil_indir(2003, oturum)

    assert saatlik["time"] == ["2003-01-01T00:00", "2003-01-01T01:00"]
    for v in ak.HOURLY_TUMU:
        assert v in saatlik


def test_yil_indir_api_hata_govdesi_hemen_basarisiz_retry_edilmez():
    """Open-Meteo hatali istekte HTTP 200/400 + {"error":true,...} dondurebilir
    - bu, ayni istek tekrar aynen basarisiz olacagi icin RETRY EDILMEMELI."""
    oturum = MagicMock()
    oturum.get.return_value = _SahteYanit(
        {"error": True, "reason": "Invalid parameter hourly"})

    with pytest.raises(ak.AcikMeteoHatasi, match="Invalid parameter"):
        ak._yil_indir(2003, oturum)
    assert oturum.get.call_count == 1


def test_yil_indir_hourly_alani_yoksa_hata():
    oturum = MagicMock()
    oturum.get.return_value = _SahteYanit({"latitude": 40.9})

    with pytest.raises(ak.AcikMeteoHatasi, match="hourly"):
        ak._yil_indir(2003, oturum)


def test_yil_indir_eksik_degisken_sessizce_atlanmiyor_acik_hata_veriyor():
    saatlik = _saatlik_ornek()
    del saatlik["temperature_2m"]
    oturum = MagicMock()
    oturum.get.return_value = _SahteYanit({"hourly": saatlik})

    with pytest.raises(ak.AcikMeteoHatasi, match="temperature_2m"):
        ak._yil_indir(2003, oturum)


def test_yil_indir_baglanti_hatasi_deneme_sayisi_kadar_retry_edilir():
    oturum = MagicMock()
    oturum.get.side_effect = requests.ConnectionError("kopuk")

    with pytest.raises(ak.AcikMeteoHatasi):
        ak._yil_indir(2003, oturum)
    assert oturum.get.call_count == ak.DENEME


def test_yil_indir_5xx_jsonsuz_govde_retry_edilip_sonunda_hata_verir():
    oturum = MagicMock()
    oturum.get.return_value = _SahteYanit(status_code=503, json_error=True)

    with pytest.raises(ak.AcikMeteoHatasi):
        ak._yil_indir(2003, oturum)
    assert oturum.get.call_count == ak.DENEME


def test_yil_indir_gecici_hatadan_sonra_basarili_olursa_sonuc_donulur():
    basarili = _SahteYanit({"hourly": _saatlik_ornek()})
    oturum = MagicMock()
    oturum.get.side_effect = [requests.Timeout("zaman asimi"), basarili]

    saatlik = ak._yil_indir(2003, oturum)
    assert saatlik["time"] == ["2003-01-01T00:00", "2003-01-01T01:00"]


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
        ozet = ak.arsivi_uret(2003, 2004, cikti)

    assert ozet["gozlem"] == 5
    with gzip.open(cikti, "rt", newline="") as f:
        satirlar = list(csv.DictReader(f))
    assert len(satirlar) == 5
    assert satirlar[0]["zaman"] == "2003-01-01T00:00"
    assert satirlar[0]["temperature_2m"] == "0.0"
    assert set(satirlar[0]) == {"zaman"} | set(ak.HOURLY_TUMU)


def test_arsivi_uret_hata_yukseltilir_kismi_dosya_kalabilir(tmp_path):
    oturum = MagicMock()
    oturum.get.return_value = _SahteYanit({"error": True, "reason": "kota"})
    oturum.__enter__.return_value = oturum
    oturum.__exit__.return_value = False

    with patch.object(ak.requests, "Session", return_value=oturum):
        with pytest.raises(ak.AcikMeteoHatasi, match="kota"):
            ak.arsivi_uret(2003, 2003, tmp_path / "x.csv.gz")
