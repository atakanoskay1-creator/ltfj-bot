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
            patch.object(dkc, "_saatlik_tahmin_cek", return_value=[]), \
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
            patch.object(dkc, "_saatlik_tahmin_cek", return_value=[]), \
            patch.object(dkc, "_komsu_tavan_cek", return_value=2200):
        dkc.guncelle(dosya)

    veri = json.loads(dosya.read_text())
    assert veri["acik_meteo_nem_2m"] == 75          # eski deger korundu
    assert veri["komsu_tavan_ozellik"] == 2200        # yeni deger yazildi


def test_guncelle_komsu_kaynagi_ulasilamazsa_diger_yazilir(tmp_path):
    dosya = tmp_path / "cache.json"
    with patch.object(dkc, "_acik_meteo_nem_cek", return_value=60), \
            patch.object(dkc, "_saatlik_tahmin_cek", return_value=[]), \
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


# ============================================================ saatlik tahmin
# Bu blok SADECE sayfada gosterilir, hicbir modele girdi degildir - ama
# onbellek sozlesmesi ayni: kendi basina cokerse digerlerini kirletmemeli.
def _saatlik_yanit(saat_sayisi=14, baslangic_saat_once=2):
    """Open-Meteo'nun hourly blogunu taklit eder. Kasitli olarak GECMIS
    saatlerle baslar - API gunun basindan itibaren dondurur, ayiklanmali."""
    ilk = (datetime.now(timezone.utc) - timedelta(hours=baslangic_saat_once)
           ).replace(minute=0, second=0, microsecond=0)
    zamanlar = [(ilk + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M")
                for i in range(saat_sayisi)]
    hourly = {"time": zamanlar}
    for alan in dkc.HOURLY_ALANLAR:
        hourly[alan] = list(range(saat_sayisi))
    return _SahteYanit({"hourly": hourly})


def test_saatlik_tahmin_cek_gecmis_saatleri_ayikliyor():
    with patch.object(dkc.requests, "get", return_value=_saatlik_yanit()):
        satirlar = dkc._saatlik_tahmin_cek()
    simdi = datetime.now(timezone.utc)
    assert satirlar
    for s in satirlar:
        an = datetime.fromisoformat(s["saat"]).replace(tzinfo=timezone.utc)
        assert an >= simdi


def test_saatlik_tahmin_cek_tahmin_saat_kadariyla_sinirli():
    with patch.object(dkc.requests, "get",
                      return_value=_saatlik_yanit(saat_sayisi=48)):
        assert len(dkc._saatlik_tahmin_cek()) == dkc.TAHMIN_SAAT


def test_saatlik_tahmin_cek_istenen_alanlari_tasiyor():
    with patch.object(dkc.requests, "get", return_value=_saatlik_yanit()):
        satir = dkc._saatlik_tahmin_cek()[0]
    for alan in dkc.HOURLY_ALANLAR:
        assert alan in satir, alan


def test_saatlik_tahmin_cek_hata_govdesi_yukseltir():
    yanit = _SahteYanit({"error": True, "reason": "kota"})
    with patch.object(dkc.requests, "get", return_value=yanit):
        with pytest.raises(dkc.OnbellekHatasi):
            dkc._saatlik_tahmin_cek()


def test_saatlik_tahmin_cek_hourly_yoksa_yukseltir():
    with patch.object(dkc.requests, "get", return_value=_SahteYanit({})):
        with pytest.raises(dkc.OnbellekHatasi):
            dkc._saatlik_tahmin_cek()


def test_saatlik_tahmin_cek_hepsi_gecmisse_yukseltir():
    """Ileriye donuk tek saat yoksa bos liste yazmaktansa hata yukseltip
    ESKI tahmini korumak daha dogru."""
    yanit = _saatlik_yanit(saat_sayisi=2, baslangic_saat_once=10)
    with patch.object(dkc.requests, "get", return_value=yanit):
        with pytest.raises(dkc.OnbellekHatasi):
            dkc._saatlik_tahmin_cek()


def test_guncelle_tahmin_cokerse_diger_ikisi_yazilir(tmp_path):
    dosya = tmp_path / "cache.json"
    with patch.object(dkc, "_acik_meteo_nem_cek", return_value=88), \
            patch.object(dkc, "_komsu_tavan_cek", return_value=900), \
            patch.object(dkc, "_saatlik_tahmin_cek",
                         side_effect=dkc.OnbellekHatasi("tahmin çöktü")):
        dkc.guncelle(dosya)
    veri = json.loads(dosya.read_text())
    assert veri["acik_meteo_nem_2m"] == 88
    assert veri["komsu_tavan_ozellik"] == 900
    assert "saatlik_tahmin" not in veri


def test_guncelle_nem_cokerse_tahmin_yine_yazilir(tmp_path):
    dosya = tmp_path / "cache.json"
    satirlar = [{"saat": "2026-01-01T00:00", "temperature_2m": 5}]
    with patch.object(dkc, "_acik_meteo_nem_cek",
                      side_effect=dkc.OnbellekHatasi("çöktü")), \
            patch.object(dkc, "_komsu_tavan_cek", return_value=1200), \
            patch.object(dkc, "_saatlik_tahmin_cek", return_value=satirlar):
        dkc.guncelle(dosya)
    veri = json.loads(dosya.read_text())
    assert veri["saatlik_tahmin"] == satirlar


# ------------------------------------------------------------- tahmin_oku
def _ileri_satir(saat_sonra):
    an = (datetime.now(timezone.utc) + timedelta(hours=saat_sonra)
          ).replace(minute=0, second=0, microsecond=0)
    return {"saat": an.strftime("%Y-%m-%dT%H:%M"), "temperature_2m": 10}


def test_tahmin_oku_taze_tahmini_dondurur(tmp_path):
    dosya = tmp_path / "cache.json"
    dosya.write_text(json.dumps({
        "saatlik_tahmin": [_ileri_satir(1), _ileri_satir(2)],
        "saatlik_tahmin_guncelleme": _zaman(dk_once=10),
    }))
    assert len(dkc.tahmin_oku(dosya)) == 2


def test_tahmin_oku_bayatsa_bos_liste(tmp_path):
    dosya = tmp_path / "cache.json"
    dosya.write_text(json.dumps({
        "saatlik_tahmin": [_ileri_satir(1)],
        "saatlik_tahmin_guncelleme": _zaman(dk_once=dkc.TAHMIN_ESIK_DK + 30),
    }))
    assert dkc.tahmin_oku(dosya) == []


def test_tahmin_oku_gecmis_saatleri_ayikliyor(tmp_path):
    """40 dk once yazilmis bir tahminin ilk satiri artik gecmiste olabilir."""
    dosya = tmp_path / "cache.json"
    dosya.write_text(json.dumps({
        "saatlik_tahmin": [_ileri_satir(-3), _ileri_satir(-1), _ileri_satir(2)],
        "saatlik_tahmin_guncelleme": _zaman(dk_once=40),
    }))
    assert len(dkc.tahmin_oku(dosya)) == 1


def test_tahmin_oku_dosya_yoksa_bos_liste(tmp_path):
    assert dkc.tahmin_oku(tmp_path / "yok.json") == []


def test_tahmin_oku_bozuk_kayitlarda_cokmez(tmp_path):
    dosya = tmp_path / "cache.json"
    dosya.write_text(json.dumps({
        "saatlik_tahmin": ["dict degil", {"saat": "bozuk"}, _ileri_satir(1)],
        "saatlik_tahmin_guncelleme": _zaman(dk_once=5),
    }))
    assert len(dkc.tahmin_oku(dosya)) == 1


def test_tahmin_oku_esigi_oku_dan_daha_gevsek():
    """12 saatlik bir tahmin, 'şu anki nem' kadar hizli bayatlamaz."""
    assert dkc.TAHMIN_ESIK_DK > dkc.ESIK_DK


def test_oku_sozlesmesi_tahminle_kirlenmedi(tmp_path):
    """oku()'nun ciktisi dondurulmus modele girdi olarak gidiyor - oraya
    tahmin alani SIZMAMALI."""
    dosya = tmp_path / "cache.json"
    dosya.write_text(json.dumps({
        "acik_meteo_nem_2m": 80, "acik_meteo_guncelleme": _zaman(dk_once=5),
        "komsu_tavan_ozellik": 1000, "komsu_guncelleme": _zaman(dk_once=5),
        "saatlik_tahmin": [_ileri_satir(1)],
        "saatlik_tahmin_guncelleme": _zaman(dk_once=5),
    }))
    assert set(dkc.oku(dosya)) == {"acik_meteo_nem_2m", "komsu_tavan_ozellik"}


# ------------------------------------------- deneysel alanlar / geri dusme
def test_deneysel_alanlar_kabul_edilirse_isteniyor():
    yakalanan = {}

    def sahte_get(url, params=None, timeout=None):
        yakalanan["hourly"] = params["hourly"]
        return _saatlik_yanit()

    with patch.object(dkc.requests, "get", side_effect=sahte_get):
        dkc._saatlik_tahmin_cek()
    for alan in dkc.HOURLY_DENEYSEL:
        assert alan in yakalanan["hourly"], alan


def test_deneysel_alan_reddedilirse_cekirdekle_tekrar_deneniyor():
    """KRİTİK: Open-Meteo geçersiz bir alan görünce isteğin TAMAMINI
    reddeder. Bu durumda şerit tamamen kaybolmamalı - deneysel alanlar
    düşürülüp bir kez daha denenmeli."""
    cagrilar = []

    def sahte_get(url, params=None, timeout=None):
        cagrilar.append(params["hourly"])
        if "boundary_layer_height" in params["hourly"]:
            return _SahteYanit({"error": True, "reason": "Cannot initialize ..."})
        return _saatlik_yanit()

    with patch.object(dkc.requests, "get", side_effect=sahte_get):
        satirlar = dkc._saatlik_tahmin_cek()

    assert len(cagrilar) == 2
    assert "boundary_layer_height" not in cagrilar[1]
    assert satirlar                      # serit yine uretildi
    assert "weather_code" not in satirlar[0]


def test_cekirdek_de_reddedilirse_hata_yukseliyor():
    """Geri düşme SONSUZ değil - çekirdek de başarısızsa eski tahmin
    korunmalı (guncelle() bunu yakalayıp eski değeri bırakıyor)."""
    yanit = _SahteYanit({"error": True, "reason": "kota"})
    with patch.object(dkc.requests, "get", return_value=yanit):
        with pytest.raises(dkc.OnbellekHatasi):
            dkc._saatlik_tahmin_cek()
