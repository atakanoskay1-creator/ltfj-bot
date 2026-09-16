"""NOTAM senkronizasyonu METAR'dan bagimsiz, seyrek araliklarla calisan
ayri bir katman (bkz. ltfj_bot.py::notam_senkronize/_notam_senkron_gerekli_mi).
Bu testler SADECE bu gating/senkron mantigini dogruluyor - METAR akisina
hic dokunmuyor (main() cagrilmiyor)."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import ltfj_bot as b
import ltfj_notam


def _sahte_ayar(notam_ayarlari):
    def sahte(*yol, varsayilan=None):
        if yol and yol[0] == "notam":
            d = notam_ayarlari
            for k in yol[1:]:
                if not isinstance(d, dict) or k not in d:
                    return varsayilan
                d = d[k]
            return d
        return varsayilan
    return sahte


def test_notam_kapaliysa_senkron_atlanir(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": False}))
    monkeypatch.setattr(b.notam_client, "api_anahtari_var_mi", lambda: True)
    assert b._notam_senkron_gerekli_mi({}) is False


def test_api_anahtari_yoksa_senkron_atlanir(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": True}))
    monkeypatch.setattr(b.notam_client, "api_anahtari_var_mi", lambda: False)
    assert b._notam_senkron_gerekli_mi({}) is False


def test_ilk_calismada_notam_son_senkron_yoksa_senkron_gerekir(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": True}))
    monkeypatch.setattr(b.notam_client, "api_anahtari_var_mi", lambda: True)
    assert b._notam_senkron_gerekli_mi({"notam_son_senkron": None}) is True


def test_arali_dolmadiysa_senkron_atlanir(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": True, "senkron_araligi_saat": 6}))
    monkeypatch.setattr(b.notam_client, "api_anahtari_var_mi", lambda: True)
    son = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
    assert b._notam_senkron_gerekli_mi({"notam_son_senkron": son}) is False


def test_arali_dolduysa_senkron_gerekir(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": True, "senkron_araligi_saat": 6}))
    monkeypatch.setattr(b.notam_client, "api_anahtari_var_mi", lambda: True)
    son = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat(timespec="seconds")
    assert b._notam_senkron_gerekli_mi({"notam_son_senkron": son}) is True


def test_bozuk_zaman_damgasi_senkron_gerektirir(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": True}))
    monkeypatch.setattr(b.notam_client, "api_anahtari_var_mi", lambda: True)
    assert b._notam_senkron_gerekli_mi({"notam_son_senkron": "gecersiz-tarih"}) is True


def test_senkronize_gerekmiyorsa_state_degismez(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": False}))
    state = {"notam_gecmisi": {"x": 1}, "notam_son_senkron": "eski"}
    with patch.object(ltfj_notam, "aktif_notamlari_getir") as sahte_getir:
        b.notam_senkronize(state)
    sahte_getir.assert_not_called()
    assert state == {"notam_gecmisi": {"x": 1}, "notam_son_senkron": "eski"}


def test_senkronize_basarili_gecmisi_ve_zamani_gunceller(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": True, "location": "LTFJ"}))
    monkeypatch.setattr(b.notam_client, "api_anahtari_var_mi", lambda: True)
    state = {"notam_gecmisi": {}, "notam_son_senkron": None}
    aktif_kayit = {"id": "abc-123", "record_updated_at": "2026-09-16T10:00:00+00:00"}
    with patch.object(ltfj_notam, "aktif_notamlari_getir", return_value=[aktif_kayit]) as sahte_getir:
        b.notam_senkronize(state)
    sahte_getir.assert_called_once_with("LTFJ")
    assert "abc-123" in state["notam_gecmisi"]
    assert state["notam_son_senkron"] is not None


def test_senkronize_ag_hatasinda_gecmisi_bozmaz(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": True, "location": "LTFJ"}))
    monkeypatch.setattr(b.notam_client, "api_anahtari_var_mi", lambda: True)
    eski_gecmis = {"onceden-gorulmus": {"first_seen": "t1", "last_seen": "t1"}}
    state = {"notam_gecmisi": dict(eski_gecmis), "notam_son_senkron": None}
    with patch.object(ltfj_notam, "aktif_notamlari_getir",
                       side_effect=ltfj_notam.NotamServisHatasi("NOTAC erişilemedi")):
        b.notam_senkronize(state)
    # NOTAC basarisiz oldugunda daha once cekilmis NOTAM gecmisi SILINMEZ,
    # sadece bu turdaki senkronizasyon atlanir (notam_son_senkron ilerlemez).
    assert state["notam_gecmisi"] == eski_gecmis
    assert state["notam_son_senkron"] is None
