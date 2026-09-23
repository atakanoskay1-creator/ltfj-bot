"""ltfj_push.py testleri.

ltfj_atc_notes_cleanup.py ile AYNI desen: firebase_admin bu ortamda kurulu
degil, sys.modules'e SAHTE firebase_admin/credentials/db VE pywebpush
modulleri enjekte ediyoruz (modul ici import'lar lazy/fonksiyon-ici
yapildigi icin bu calisir).

En kritik test: 404/410 donen bir abonelik Firebase'den FIILEN silinir,
diger hatalar (gecici ag sorunu vb.) SILINMEZ - bir sonraki gonderimde
tekrar denenmeli. Tek bir abonenin basarisiz olmasi digerlerine gonderimi
ENGELLEMEMELI."""
import json
import sys
import types
from unittest.mock import MagicMock

import pytest

import ltfj_push as push

SAHTE_SA_JSON = json.dumps({"type": "service_account", "project_id": "ornek"})


@pytest.fixture
def sahte_firebase(monkeypatch):
    fake_admin = types.ModuleType("firebase_admin")
    fake_admin._apps = []
    fake_admin.get_app = MagicMock(return_value="app")
    fake_admin.initialize_app = MagicMock(return_value="app")

    fake_credentials = types.ModuleType("firebase_admin.credentials")
    fake_credentials.Certificate = MagicMock(return_value="cred")
    fake_admin.credentials = fake_credentials

    fake_db = types.ModuleType("firebase_admin.db")
    ref_mock = MagicMock()
    fake_db.reference = MagicMock(return_value=ref_mock)
    fake_admin.db = fake_db

    monkeypatch.setitem(sys.modules, "firebase_admin", fake_admin)
    monkeypatch.setitem(sys.modules, "firebase_admin.credentials", fake_credentials)
    monkeypatch.setitem(sys.modules, "firebase_admin.db", fake_db)
    return ref_mock


class _SahteWebPushException(Exception):
    def __init__(self, mesaj="hata", response=None):
        super().__init__(mesaj)
        self.response = response


class _SahteYanit:
    def __init__(self, status_code):
        self.status_code = status_code


@pytest.fixture
def sahte_pywebpush(monkeypatch):
    fake_pywebpush = types.ModuleType("pywebpush")
    fake_pywebpush.webpush = MagicMock()
    fake_pywebpush.WebPushException = _SahteWebPushException
    monkeypatch.setitem(sys.modules, "pywebpush", fake_pywebpush)
    return fake_pywebpush


def _ortam_ayarla(monkeypatch, sa_json=SAHTE_SA_JSON,
                  db_url="https://ornek.firebasedatabase.app", vapid_key="ornek-ozel-anahtar"):
    for ad, deger in (("FIREBASE_SERVICE_ACCOUNT", sa_json),
                      ("FIREBASE_DATABASE_URL", db_url),
                      ("VAPID_PRIVATE_KEY", vapid_key)):
        if deger is None:
            monkeypatch.delenv(ad, raising=False)
        else:
            monkeypatch.setenv(ad, deger)


ABONELIK = {"endpoint": "https://push.ornek.com/1", "keys": {"p256dh": "x", "auth": "y"}}


# --------------------------------------------------------- yapilandirma
def test_yapilandirilmis_mi_ucu_de_varsa_true(monkeypatch):
    _ortam_ayarla(monkeypatch)
    assert push.yapilandirilmis_mi() is True


@pytest.mark.parametrize("eksik", ["FIREBASE_SERVICE_ACCOUNT", "FIREBASE_DATABASE_URL", "VAPID_PRIVATE_KEY"])
def test_yapilandirilmis_mi_biri_eksikse_false(monkeypatch, eksik):
    kwargs = {"sa_json": SAHTE_SA_JSON, "db_url": "https://x", "vapid_key": "k"}
    anahtar = {"FIREBASE_SERVICE_ACCOUNT": "sa_json", "FIREBASE_DATABASE_URL": "db_url",
              "VAPID_PRIVATE_KEY": "vapid_key"}[eksik]
    kwargs[anahtar] = None
    _ortam_ayarla(monkeypatch, **kwargs)
    assert push.yapilandirilmis_mi() is False


def test_gonder_yapilandirilmamissa_hata(monkeypatch, sahte_firebase, sahte_pywebpush):
    _ortam_ayarla(monkeypatch, vapid_key=None)
    with pytest.raises(push.PushGonderimHatasi):
        push.gonder("Başlık", "Gövde", "mailto:x@x.com")


# -------------------------------------------------------------- govde
def test_govde_kur_sw_js_alanlariyla_eslesiyor():
    veri = json.loads(push.govde_kur("Başlık", "Gövde", "etiket-x", "./sayfa"))
    assert veri == {"baslik": "Başlık", "govde": "Gövde", "etiket": "etiket-x", "url": "./sayfa"}


# -------------------------------------------------------------- gonder
def test_gonder_tum_abonelere_basariyla_gonderir(monkeypatch, sahte_firebase, sahte_pywebpush):
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.return_value = {"a1": ABONELIK, "a2": ABONELIK}

    sonuc = push.gonder("Başlık", "Gövde", "mailto:x@x.com")

    assert {k: sonuc[k] for k in ("abone", "gonderildi", "silindi", "hata")} == {"abone": 2, "gonderildi": 2, "silindi": 0, "hata": 0}
    assert sahte_pywebpush.webpush.call_count == 2


def test_gonder_404_donen_abonelik_silinir(monkeypatch, sahte_firebase, sahte_pywebpush):
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.return_value = {"a1": ABONELIK}
    sahte_pywebpush.webpush.side_effect = _SahteWebPushException(response=_SahteYanit(404))

    sonuc = push.gonder("Başlık", "Gövde", "mailto:x@x.com")

    assert {k: sonuc[k] for k in ("abone", "gonderildi", "silindi", "hata")} == {"abone": 1, "gonderildi": 0, "silindi": 1, "hata": 0}
    sahte_firebase.child.assert_called_once_with("a1")
    sahte_firebase.child.return_value.delete.assert_called_once()


def test_gonder_410_donen_abonelik_de_silinir(monkeypatch, sahte_firebase, sahte_pywebpush):
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.return_value = {"a1": ABONELIK}
    sahte_pywebpush.webpush.side_effect = _SahteWebPushException(response=_SahteYanit(410))

    sonuc = push.gonder("Başlık", "Gövde", "mailto:x@x.com")

    assert sonuc["silindi"] == 1


def test_gonder_gecici_hata_silmez_sadece_sayar(monkeypatch, sahte_firebase, sahte_pywebpush):
    """500 gibi gecici bir sunucu hatasi abonelik GECERSIZ demek degildir -
    silinmemeli, bir sonraki gonderimde tekrar denenmeli."""
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.return_value = {"a1": ABONELIK}
    sahte_pywebpush.webpush.side_effect = _SahteWebPushException(response=_SahteYanit(500))

    sonuc = push.gonder("Başlık", "Gövde", "mailto:x@x.com")

    assert {k: sonuc[k] for k in ("abone", "gonderildi", "silindi", "hata")} == {"abone": 1, "gonderildi": 0, "silindi": 0, "hata": 1}
    sahte_firebase.child.assert_not_called()


def test_gonder_bir_abone_basarisiz_digerlerini_engellemiyor(monkeypatch, sahte_firebase, sahte_pywebpush):
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.return_value = {"a1": ABONELIK, "a2": ABONELIK}
    sahte_pywebpush.webpush.side_effect = [
        _SahteWebPushException(response=_SahteYanit(500)), None,
    ]

    sonuc = push.gonder("Başlık", "Gövde", "mailto:x@x.com")

    assert {k: sonuc[k] for k in ("abone", "gonderildi", "silindi", "hata")} == {"abone": 2, "gonderildi": 1, "silindi": 0, "hata": 1}


def test_gonder_bozuk_kayit_atlanir_crash_etmez(monkeypatch, sahte_firebase, sahte_pywebpush):
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.return_value = {
        "bozuk1": {"endpoint": "x"},         # keys yok
        "bozuk2": "dict bile değil",
        "iyi": ABONELIK,
    }

    sonuc = push.gonder("Başlık", "Gövde", "mailto:x@x.com")

    assert {k: sonuc[k] for k in ("abone", "gonderildi", "silindi", "hata")} == {"abone": 3, "gonderildi": 1, "silindi": 0, "hata": 0}


def test_gonder_bos_abonelik_listesinde_crash_etmez(monkeypatch, sahte_firebase, sahte_pywebpush):
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.return_value = None

    sonuc = push.gonder("Başlık", "Gövde", "mailto:x@x.com")
    assert {k: sonuc[k] for k in ("abone", "gonderildi", "silindi", "hata")} == {
        "abone": 0, "gonderildi": 0, "silindi": 0, "hata": 0}


def test_gonder_okuma_hatasinda_ozel_exception_firlatir(monkeypatch, sahte_firebase, sahte_pywebpush):
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.side_effect = RuntimeError("bağlantı koptu")
    with pytest.raises(push.PushGonderimHatasi):
        push.gonder("Başlık", "Gövde", "mailto:x@x.com")


# ================================================== hata SEBEPLERI yuzeye cikar
# KUSUR: eskiden yalnizca hata SAYISI donuyordu. "2 abone, 0 gonderildi,
# 2 hata" logu VAPID anahtari yanlis mi, ag mi cokmus, abonelik mi bayat
# ayirt ettirmiyordu - bu oturumda bir sessiz push hatasini teshis etmek
# tam da bu yuzden uzun surmustu.
def test_basarili_gonderimde_sebep_listesi_bos(monkeypatch, sahte_firebase, sahte_pywebpush):
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.return_value = {"a1": ABONELIK, "a2": ABONELIK}
    assert push.gonder("Başlık", "Gövde", "mailto:x@x.com")["sebepler"] == []


def test_hata_sebebi_metniyle_birlikte_donuyor(monkeypatch, sahte_firebase, sahte_pywebpush):
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.return_value = {"a1": ABONELIK}
    sahte_pywebpush.webpush.side_effect = RuntimeError("ag kopuk")

    sonuc = push.gonder("Başlık", "Gövde", "mailto:x@x.com")

    assert sonuc["hata"] == 1
    assert len(sonuc["sebepler"]) == 1
    assert "ag kopuk" in sonuc["sebepler"][0]
    assert "RuntimeError" in sonuc["sebepler"][0]


def test_webpush_hatasinda_HTTP_KODU_sebepte_geciyor(monkeypatch, sahte_firebase, sahte_pywebpush):
    """Kod olmadan "WebPush hatasi" demek teshis ettirmiyor - 500 mu,
    403 mu (VAPID yanlis) ayirt edilebilmeli."""
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.return_value = {"a1": ABONELIK}
    sahte_pywebpush.webpush.side_effect = _SahteWebPushException(response=_SahteYanit(403))

    sonuc = push.gonder("Başlık", "Gövde", "mailto:x@x.com")

    assert sonuc["hata"] == 1
    assert "403" in sonuc["sebepler"][0]


def test_ayni_sebep_TEKRARLANMIYOR(monkeypatch, sahte_firebase, sahte_pywebpush):
    """500 abonenin hepsi ayni sebepten duserse log 500 satir olmamali."""
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.return_value = {"a1": ABONELIK, "a2": ABONELIK, "a3": ABONELIK}
    sahte_pywebpush.webpush.side_effect = RuntimeError("ayni sebep")

    sonuc = push.gonder("Başlık", "Gövde", "mailto:x@x.com")

    assert sonuc["hata"] == 3
    assert len(sonuc["sebepler"]) == 1


def test_farkli_sebepler_ayri_ayri_toplaniyor(monkeypatch, sahte_firebase, sahte_pywebpush):
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.return_value = {"a1": ABONELIK, "a2": ABONELIK}
    sahte_pywebpush.webpush.side_effect = [RuntimeError("birinci"), ValueError("ikinci")]

    sonuc = push.gonder("Başlık", "Gövde", "mailto:x@x.com")

    assert len(sonuc["sebepler"]) == 2


def test_silinen_abonelik_sebep_uretmiyor(monkeypatch, sahte_firebase, sahte_pywebpush):
    """404/410 bir HATA degil, beklenen temizlik - sebep listesini
    kirletmemeli."""
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.return_value = {"a1": ABONELIK}
    sahte_pywebpush.webpush.side_effect = _SahteWebPushException(response=_SahteYanit(410))

    sonuc = push.gonder("Başlık", "Gövde", "mailto:x@x.com")

    assert sonuc["silindi"] == 1
    assert sonuc["sebepler"] == []
