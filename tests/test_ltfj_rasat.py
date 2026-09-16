"""ltfj_rasat.py::_sayfayi_getir() HTTP hata siniflandirmasi testleri.

P3: gecici hatalar (timeout, baglanti, 5xx) retry edilmeli; kalici istemci
hatalari (4xx) HEMEN basarisiz olmali - ayni istek tekrar ayni sonucu
verir, DENEME dongusunun bekleme surelerini (5, 10 sn) bosuna tuketmenin
anlami yok. time.sleep() her testte mock'lanir, gercekten beklemeyiz."""
from unittest.mock import MagicMock, patch

import pytest
import requests

import ltfj_rasat as r


def _sahte_yanit(status_code, reason="Hata"):
    yanit = MagicMock()
    yanit.status_code = status_code
    yanit.reason = reason
    if status_code >= 400:
        yanit.raise_for_status.side_effect = requests.HTTPError(
            f"{status_code} {reason}", response=yanit)
    else:
        yanit.raise_for_status.side_effect = None
    return yanit


def test_basarili_istek_ilk_denemede_doner():
    yanit = _sahte_yanit(200)
    with patch("requests.get", return_value=yanit) as mock_get, \
            patch("time.sleep") as mock_sleep:
        sonuc = r._sayfayi_getir([("stations", "LTFJ")], 30)
    assert sonuc is yanit
    assert mock_get.call_count == 1
    mock_sleep.assert_not_called()


def test_4xx_hemen_basarisiz_retry_edilmez():
    yanit = _sahte_yanit(404, "Not Found")
    with patch("requests.get", return_value=yanit) as mock_get, \
            patch("time.sleep") as mock_sleep:
        with pytest.raises(r.AgHatasi, match="404"):
            r._sayfayi_getir([("stations", "LTFJ")], 30)
    assert mock_get.call_count == 1   # TEK deneme - retry edilmedi
    mock_sleep.assert_not_called()    # bekleme suresi hic tuketilmedi


def test_5xx_deneme_sayisi_kadar_retry_edilir():
    yanit = _sahte_yanit(503, "Service Unavailable")
    with patch("requests.get", return_value=yanit) as mock_get, \
            patch("time.sleep") as mock_sleep:
        with pytest.raises(r.AgHatasi):
            r._sayfayi_getir([("stations", "LTFJ")], 30)
    assert mock_get.call_count == r.DENEME
    assert mock_sleep.call_count == r.DENEME - 1


def test_baglanti_hatasi_retry_edilir():
    with patch("requests.get", side_effect=requests.ConnectionError("kopuk")) as mock_get, \
            patch("time.sleep") as mock_sleep:
        with pytest.raises(r.AgHatasi):
            r._sayfayi_getir([("stations", "LTFJ")], 30)
    assert mock_get.call_count == r.DENEME
    assert mock_sleep.call_count == r.DENEME - 1


def test_gecici_hatadan_sonra_basarili_olursa_sonuc_donulur():
    basarili = _sahte_yanit(200)
    with patch("requests.get", side_effect=[requests.Timeout("zaman asimi"), basarili]) as mock_get, \
            patch("time.sleep") as mock_sleep:
        sonuc = r._sayfayi_getir([("stations", "LTFJ")], 30)
    assert sonuc is basarili
    assert mock_get.call_count == 2
    assert mock_sleep.call_count == 1
