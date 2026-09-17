"""ltfj_atc_notes_cleanup.py testleri.

ATC Notes'un kendisi (olusturma/okuma) DOGRUDAN tarayicidan Firebase
Realtime Database REST API'sine yapilir - bu modul SADECE 48 saati dolmus
notlari storage'dan fiilen silen arka plan gorevini test eder. firebase_admin
paketi bu ortamda kurulu degil (production'da sadece GitHub Actions
workflow'unda kurulu) - bu yuzden sys.modules'e SAHTE firebase_admin/
credentials/db modulleri enjekte ediyoruz (modul ici import'lar bunlari
lazy/fonksiyon-ici yapildigi icin bu calisir, bkz. ltfj_atc_notes_cleanup.
_uygulama_al/expired_atc_notes_cleanup)."""
import json
import sys
import types
from unittest.mock import MagicMock

import pytest

import ltfj_atc_notes_cleanup as temizlik

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


def _ortam_ayarla(monkeypatch, sa_json=SAHTE_SA_JSON, db_url="https://ornek.firebasedatabase.app"):
    if sa_json is None:
        monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT", raising=False)
    else:
        monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT", sa_json)
    if db_url is None:
        monkeypatch.delenv("FIREBASE_DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("FIREBASE_DATABASE_URL", db_url)


# --------------------------------------------------------- yapilandirma
def test_yapilandirilmis_mi_ikisi_de_varsa_true(monkeypatch):
    _ortam_ayarla(monkeypatch)
    assert temizlik.yapilandirilmis_mi() is True


def test_yapilandirilmis_mi_service_account_yoksa_false(monkeypatch):
    _ortam_ayarla(monkeypatch, sa_json=None)
    assert temizlik.yapilandirilmis_mi() is False


def test_yapilandirilmis_mi_database_url_yoksa_false(monkeypatch):
    _ortam_ayarla(monkeypatch, db_url=None)
    assert temizlik.yapilandirilmis_mi() is False


def test_cleanup_service_account_tanimsizsa_hata(monkeypatch, sahte_firebase):
    _ortam_ayarla(monkeypatch, sa_json=None)
    with pytest.raises(temizlik.AtcNotesTemizlikHatasi):
        temizlik.expired_atc_notes_cleanup()


def test_cleanup_database_url_tanimsizsa_hata(monkeypatch, sahte_firebase):
    _ortam_ayarla(monkeypatch, db_url=None)
    with pytest.raises(temizlik.AtcNotesTemizlikHatasi):
        temizlik.expired_atc_notes_cleanup()


def test_cleanup_bozuk_service_account_json_hata(monkeypatch, sahte_firebase):
    _ortam_ayarla(monkeypatch, sa_json="{gecersiz-json")
    with pytest.raises(temizlik.AtcNotesTemizlikHatasi):
        temizlik.expired_atc_notes_cleanup()


# ------------------------------------------------------------- silme
def test_cleanup_suresi_dolmus_notu_siler(monkeypatch, sahte_firebase):
    _ortam_ayarla(monkeypatch)
    simdi_ms = 1_000_000_000_000
    dolmus_created_at = simdi_ms - temizlik.NOT_YASAM_SURESI_SANIYE * 1000
    sahte_firebase.get.return_value = {"n1": {"author": "Ahmet", "text": "eski not",
                                               "created_at": dolmus_created_at}}

    silinen = temizlik.expired_atc_notes_cleanup(simdi_ms)

    assert silinen == 1
    sahte_firebase.child.assert_called_once_with("n1")
    sahte_firebase.child.return_value.delete.assert_called_once()


def test_cleanup_dolmamis_notu_silmez(monkeypatch, sahte_firebase):
    _ortam_ayarla(monkeypatch)
    simdi_ms = 1_000_000_000_000
    yeni_created_at = simdi_ms - 3600_000  # 1 saat once - dolmadi
    sahte_firebase.get.return_value = {"n1": {"author": "Ahmet", "text": "yeni not",
                                               "created_at": yeni_created_at}}

    silinen = temizlik.expired_atc_notes_cleanup(simdi_ms)

    assert silinen == 0
    sahte_firebase.child.assert_not_called()


def test_cleanup_esik_siniri_tam_48_saatte_silinir(monkeypatch, sahte_firebase):
    """created_at + 48s TAM simdiye esitse (>=) silinmeli - sinirda bir
    not sessizce 'henuz dolmadi' sayilip sonsuza kadar birikmemeli."""
    simdi_ms = 1_000_000_000_000
    tam_esik = simdi_ms - temizlik.NOT_YASAM_SURESI_SANIYE * 1000
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.return_value = {"n1": {"created_at": tam_esik}}

    assert temizlik.expired_atc_notes_cleanup(simdi_ms) == 1


def test_cleanup_esikten_1ms_once_silinmez(monkeypatch, sahte_firebase):
    simdi_ms = 1_000_000_000_000
    esik_oncesi = simdi_ms - temizlik.NOT_YASAM_SURESI_SANIYE * 1000 + 1
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.return_value = {"n1": {"created_at": esik_oncesi}}

    assert temizlik.expired_atc_notes_cleanup(simdi_ms) == 0


def test_cleanup_birden_fazla_notta_sadece_dolanlar_silinir(monkeypatch, sahte_firebase):
    """Birden fazla not oluşturulduğunda eski (hala gecerli) notlar
    kaybolmamali - sadece GERCEKTEN dolmus olanlar silinir."""
    simdi_ms = 1_000_000_000_000
    dolmus = simdi_ms - temizlik.NOT_YASAM_SURESI_SANIYE * 1000 - 1000
    gecerli = simdi_ms - 1000
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.return_value = {
        "eski": {"created_at": dolmus},
        "yeni": {"created_at": gecerli},
    }

    silinen = temizlik.expired_atc_notes_cleanup(simdi_ms)

    assert silinen == 1
    sahte_firebase.child.assert_called_once_with("eski")


def test_cleanup_bos_veritabaninda_crash_etmez(monkeypatch, sahte_firebase):
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.return_value = None
    assert temizlik.expired_atc_notes_cleanup() == 0


def test_cleanup_bozuk_kayit_atlanir_crash_etmez(monkeypatch, sahte_firebase):
    """created_at eksik/gecersiz tipte olan bir kayit (bozuk veri) programi
    CRASH ETTIRMEMELI - sessizce atlanir (silinmez, bir sonraki
    calistirmada tekrar denenir)."""
    simdi_ms = 1_000_000_000_000
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.return_value = {
        "bozuk1": {"author": "x"},                       # created_at yok
        "bozuk2": {"created_at": "bir-metin-degil"},      # yanlis tip
        "bozuk3": "dict bile degil",
    }

    assert temizlik.expired_atc_notes_cleanup(simdi_ms) == 0
    sahte_firebase.child.assert_not_called()


def test_cleanup_idempotent_ikinci_calistirmada_tekrar_hata_vermez(monkeypatch, sahte_firebase):
    """Cleanup ayni verilerle ust uste cagrilsa da hata vermemeli - ilk
    calistirmada silinenler ikinci calistirmada zaten yok sayilir."""
    simdi_ms = 1_000_000_000_000
    dolmus = simdi_ms - temizlik.NOT_YASAM_SURESI_SANIYE * 1000 - 1000
    _ortam_ayarla(monkeypatch)

    sahte_firebase.get.return_value = {"n1": {"created_at": dolmus}}
    assert temizlik.expired_atc_notes_cleanup(simdi_ms) == 1

    sahte_firebase.get.return_value = {}  # n1 artik silinmis
    assert temizlik.expired_atc_notes_cleanup(simdi_ms) == 0


def test_cleanup_okuma_hatasinda_ozel_exception_firlatir(monkeypatch, sahte_firebase):
    _ortam_ayarla(monkeypatch)
    sahte_firebase.get.side_effect = RuntimeError("bağlantı koptu")
    with pytest.raises(temizlik.AtcNotesTemizlikHatasi):
        temizlik.expired_atc_notes_cleanup()
