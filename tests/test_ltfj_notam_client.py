"""ltfj_notam_client.py testleri: NOTAC API HTTP katmani.

Bu modul BILEREK sadece HTTP/hata siniflandirmasini test ediyor - NOTAC'in
gercek yanit alan (field) isimleri henuz dogrulanmadigi icin (kullanicidan
gercek bir ornek yanit bekleniyor) bu testler ham JSON'un OLDUGU GIBI
dondugunu dogruluyor, belirli alan adlarini varsaymiyor."""
from unittest.mock import MagicMock, patch

import pytest
import requests

import ltfj_notam_client as nc


def _sahte_yanit(status_code, json_deger=None, text="", json_hata=None):
    yanit = MagicMock()
    yanit.status_code = status_code
    yanit.text = text
    if json_hata is not None:
        yanit.json.side_effect = json_hata
    else:
        yanit.json.return_value = json_deger
    return yanit


# --------------------------------------------------------------- api anahtari
def test_api_anahtari_yoksa_yetki_hatasi(monkeypatch):
    monkeypatch.delenv("NOTAC_API_KEY", raising=False)
    with pytest.raises(nc.NotamYetkiHatasi):
        nc.notam_getir("LTFJ")


def test_api_anahtari_var_mi_dogru_bildiriyor(monkeypatch):
    monkeypatch.delenv("NOTAC_API_KEY", raising=False)
    assert nc.api_anahtari_var_mi() is False
    monkeypatch.setenv("NOTAC_API_KEY", "lb_" + "a" * 40)
    assert nc.api_anahtari_var_mi() is True


# ------------------------------------------------------------------- basarili
def test_basarili_yanit_ham_json_olarak_donuyor(monkeypatch):
    """Alan isimlerini VARSAYMIYORUZ - sadece requests.get'in donduregu
    json()'un aynen (yorumlanmadan) geri geldigini dogruluyor."""
    monkeypatch.setenv("NOTAC_API_KEY", "lb_" + "a" * 40)
    ham_veri = {"herhangi_bir_alan": "herhangi_bir_deger", "liste": [1, 2, 3]}
    yanit = _sahte_yanit(200, json_deger=ham_veri)
    with patch("requests.get", return_value=yanit) as mock_get:
        sonuc = nc.notam_getir("LTFJ")
    assert sonuc == ham_veri
    # Endpoint ve parametreler kullanicidan dogrulanan semaya uygun mu?
    args, kwargs = mock_get.call_args
    assert args[0] == "https://notac.aero/api/v1/notam/"
    assert kwargs["params"] == {"location": "LTFJ"}
    assert kwargs["headers"]["Authorization"] == "Bearer lb_" + "a" * 40
    assert kwargs["timeout"] == nc.VARSAYILAN_TIMEOUT


def test_farkli_lokasyon_parametreye_yansir(monkeypatch):
    monkeypatch.setenv("NOTAC_API_KEY", "lb_" + "a" * 40)
    yanit = _sahte_yanit(200, json_deger={})
    with patch("requests.get", return_value=yanit) as mock_get:
        nc.notam_getir("LTBA")
    assert mock_get.call_args.kwargs["params"] == {"location": "LTBA"}


# -------------------------------------------------------------- yetki hatasi
def test_401_yetki_hatasi_firlatir(monkeypatch):
    monkeypatch.setenv("NOTAC_API_KEY", "lb_" + "a" * 40)
    yanit = _sahte_yanit(401, text='{"detail": "Token has been revoked.", "code": "token_revoked"}')
    with patch("requests.get", return_value=yanit):
        with pytest.raises(nc.NotamYetkiHatasi, match="token_revoked"):
            nc.notam_getir("LTFJ")


# ------------------------------------------------------------------- timeout
def test_timeout_gecici_ag_hatasi_firlatir(monkeypatch):
    monkeypatch.setenv("NOTAC_API_KEY", "lb_" + "a" * 40)
    with patch("requests.get", side_effect=requests.Timeout("zaman aşımı")):
        with pytest.raises(nc.NotamAgHatasi):
            nc.notam_getir("LTFJ")


def test_baglanti_hatasi_gecici_ag_hatasi_firlatir(monkeypatch):
    monkeypatch.setenv("NOTAC_API_KEY", "lb_" + "a" * 40)
    with patch("requests.get", side_effect=requests.ConnectionError("koptu")):
        with pytest.raises(nc.NotamAgHatasi):
            nc.notam_getir("LTFJ")


# --------------------------------------------------------------- http hatasi
def test_500_ayiklama_hatasi_firlatir(monkeypatch):
    monkeypatch.setenv("NOTAC_API_KEY", "lb_" + "a" * 40)
    yanit = _sahte_yanit(500, text="Internal Server Error")
    with patch("requests.get", return_value=yanit):
        with pytest.raises(nc.NotamAyiklamaHatasi):
            nc.notam_getir("LTFJ")


def test_404_ayiklama_hatasi_firlatir(monkeypatch):
    monkeypatch.setenv("NOTAC_API_KEY", "lb_" + "a" * 40)
    yanit = _sahte_yanit(404, text="Not Found")
    with patch("requests.get", return_value=yanit):
        with pytest.raises(nc.NotamAyiklamaHatasi):
            nc.notam_getir("LTFJ")


# ---------------------------------------------------------- gecersiz json
def test_gecersiz_json_ayiklama_hatasi_firlatir(monkeypatch):
    monkeypatch.setenv("NOTAC_API_KEY", "lb_" + "a" * 40)
    yanit = _sahte_yanit(200, json_hata=ValueError("Expecting value"), text="not json")
    with patch("requests.get", return_value=yanit):
        with pytest.raises(nc.NotamAyiklamaHatasi):
            nc.notam_getir("LTFJ")


# -------------------------------------------------------- guvenlik: log/expose
def test_api_anahtari_hata_mesajlarinda_gorunmez(monkeypatch):
    """Authorization header'i / API anahtarinin kendisi hicbir exception
    mesajinda gorunmemeli (loglara sizmasin)."""
    gizli_anahtar = "lb_" + "b" * 40
    monkeypatch.setenv("NOTAC_API_KEY", gizli_anahtar)
    yanit = _sahte_yanit(401, text="yetkisiz")
    with patch("requests.get", return_value=yanit):
        with pytest.raises(nc.NotamYetkiHatasi) as hata:
            nc.notam_getir("LTFJ")
    assert gizli_anahtar not in str(hata.value)

    with patch("requests.get", side_effect=requests.ConnectionError("koptu")):
        with pytest.raises(nc.NotamAgHatasi) as hata2:
            nc.notam_getir("LTFJ")
    assert gizli_anahtar not in str(hata2.value)
