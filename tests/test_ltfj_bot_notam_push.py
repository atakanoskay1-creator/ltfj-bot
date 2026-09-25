"""ltfj_bot.py::notam_senkronize - yeni NOTAM push tetikleyicisi testleri.

En kritik test: gecmis BOŞSA (ilk senkronizasyon - o an aktif olan HER
NOTAM teknik olarak "yeni") HİÇBİR push gönderilmemeli - aksi halde ilk
çalıştırmada aktif NOTAM sayısı kadar bildirim patlardı (ltfj_bot'un kendi
METAR tarafındaki "ilk_calisma" ilkesiyle aynı)."""
import sys
import types
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

import ltfj_bot as bot
import ltfj_notam_client as notam_client


@pytest.fixture
def sahte_notam_ortami(monkeypatch):
    monkeypatch.setattr(notam_client, "api_anahtari_var_mi", lambda: True)

    fake_push = types.ModuleType("ltfj_push")
    fake_push.yapilandirilmis_mi = MagicMock(return_value=True)
    fake_push.gonder = MagicMock(return_value={"gonderildi": 1, "silindi": 0, "hata": 0})
    monkeypatch.setitem(sys.modules, "ltfj_push", fake_push)
    return fake_push


def _kayit(nid, number="A0001/26", text="Örnek NOTAM metni"):
    return {"id": nid, "number": number, "text": text, "status": "active",
           "record_updated_at": "2026-09-20T00:00:00Z"}


def test_ilk_senkronizasyonda_hic_push_gonderilmiyor(monkeypatch, sahte_notam_ortami):
    monkeypatch.setattr(bot.ltfj_notam, "yururlukteki_ve_yaklasan_notamlar",
                        lambda loc: [_kayit("n1"), _kayit("n2")])
    state = {}   # notam_gecmisi yok - bu bir ilk senkronizasyon

    bot.notam_senkronize(state)

    sahte_notam_ortami.gonder.assert_not_called()
    assert set(state["notam_gecmisi"]) == {"n1", "n2"}


def test_ikinci_senkronizasyonda_yeni_notam_push_atiyor(monkeypatch, sahte_notam_ortami):
    monkeypatch.setattr(bot.ltfj_notam, "yururlukteki_ve_yaklasan_notamlar",
                        lambda loc: [_kayit("n1"), _kayit("n2", number="A0002/26")])
    eski_zaman = "2026-09-19T00:00:00+00:00"
    state = {"notam_gecmisi": {"n1": {**_kayit("n1"), "first_seen": eski_zaman,
                                       "last_seen": eski_zaman, "last_active": eski_zaman}},
             "notam_son_senkron": eski_zaman}

    bot.notam_senkronize(state)

    sahte_notam_ortami.gonder.assert_called_once()
    args, kwargs = sahte_notam_ortami.gonder.call_args
    assert "A0002/26" in args[1]      # govde
    assert kwargs.get("etiket") == "NOTAM"


def test_mevcut_notam_tekrar_push_atmiyor(monkeypatch, sahte_notam_ortami):
    """Zaten gorulmus (gecmiste olan) bir NOTAM her senkronizasyonda tekrar
    tekrar bildirim ATMAMALI - sadece GERCEKTEN yeni id'ler icin gonderilir."""
    eski_zaman = "2026-09-19T00:00:00+00:00"
    monkeypatch.setattr(bot.ltfj_notam, "yururlukteki_ve_yaklasan_notamlar",
                        lambda loc: [_kayit("n1")])
    state = {"notam_gecmisi": {"n1": {**_kayit("n1"), "first_seen": eski_zaman,
                                       "last_seen": eski_zaman, "last_active": eski_zaman}},
             "notam_son_senkron": eski_zaman}

    bot.notam_senkronize(state)

    sahte_notam_ortami.gonder.assert_not_called()


def test_notam_push_govde_number_ve_metni_iceriyor():
    govde = bot._notam_push_govde({"number": "A0001/26", "text": "Pist kapalı"})
    assert "A0001/26" in govde and "Pist kapalı" in govde


def test_notam_push_govde_alanlar_eksikse_genel_metin():
    assert bot._notam_push_govde({}) == "Yeni bir NOTAM yayınlandı."
