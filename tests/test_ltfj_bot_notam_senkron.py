"""NOTAM senkronizasyonu METAR'dan bagimsiz, seyrek araliklarla calisan
ayri bir katman (bkz. ltfj_bot.py::notam_senkronize/_notam_senkron_gerekli_mi).
Bu testler SADECE bu gating/senkron mantigini dogruluyor - METAR akisina
hic dokunmuyor (main() cagrilmiyor)."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest


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


def _aralik(monkeypatch, saat):
    """Aralik artik `ayar()`tan DEGIL notam_senkron_araligi_saat()'ten
    geliyor (tek kaynak). _sahte_ayar ile "senkron_araligi_saat": 6
    yazmak bu yuzden ARTIK HICBIR SEY YAPMIYOR - o iki test gercek
    ayarlar.json degeriyle (3 saat) calisip tesadufen yesil kaliyordu.
    Fikstur dogru yere baglandi."""
    monkeypatch.setattr(b, "notam_senkron_araligi_saat", lambda: saat)


def test_arali_dolmadiysa_senkron_atlanir(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": True}))
    monkeypatch.setattr(b.notam_client, "api_anahtari_var_mi", lambda: True)
    _aralik(monkeypatch, 6)
    son = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
    assert b._notam_senkron_gerekli_mi({"notam_son_senkron": son}) is False


def test_arali_dolduysa_senkron_gerekir(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": True}))
    monkeypatch.setattr(b.notam_client, "api_anahtari_var_mi", lambda: True)
    _aralik(monkeypatch, 6)
    son = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat(timespec="seconds")
    assert b._notam_senkron_gerekli_mi({"notam_son_senkron": son}) is True


def test_gating_ARALIGI_TAKIP_EDIYOR(monkeypatch):
    """Ayni yas, iki farkli aralik -> iki farkli karar. Sabit bir 6
    kalsaydi bu test 3 saatlik ayarda yanlis cevap verirdi."""
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": True}))
    monkeypatch.setattr(b.notam_client, "api_anahtari_var_mi", lambda: True)
    son = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat(timespec="seconds")

    _aralik(monkeypatch, 6)
    assert b._notam_senkron_gerekli_mi({"notam_son_senkron": son}) is False
    _aralik(monkeypatch, 3)
    assert b._notam_senkron_gerekli_mi({"notam_son_senkron": son}) is True


def test_bozuk_zaman_damgasi_senkron_gerektirir(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": True}))
    monkeypatch.setattr(b.notam_client, "api_anahtari_var_mi", lambda: True)
    assert b._notam_senkron_gerekli_mi({"notam_son_senkron": "gecersiz-tarih"}) is True


def test_senkronize_gerekmiyorsa_state_degismez(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": False}))
    state = {"notam_gecmisi": {"x": 1}, "notam_son_senkron": "eski"}
    with patch.object(ltfj_notam, "yururlukteki_ve_yaklasan_notamlar") as sahte_getir:
        b.notam_senkronize(state)
    sahte_getir.assert_not_called()
    assert state == {"notam_gecmisi": {"x": 1}, "notam_son_senkron": "eski"}


def test_senkronize_basarili_gecmisi_ve_zamani_gunceller(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": True, "location": "LTFJ"}))
    monkeypatch.setattr(b.notam_client, "api_anahtari_var_mi", lambda: True)
    state = {"notam_gecmisi": {}, "notam_son_senkron": None}
    aktif_kayit = {"id": "abc-123", "record_updated_at": "2026-09-16T10:00:00+00:00"}
    with patch.object(ltfj_notam, "yururlukteki_ve_yaklasan_notamlar", return_value=[aktif_kayit]) as sahte_getir:
        b.notam_senkronize(state)
    # Yerel gecmis ONBELLEK olarak geciliyor: tam orijinal NOTAM metni
    # ("raw") NOTAM basina bir detay istegi demek, degismemis kayitlar
    # icin tekrar cekilmemeli (bkz. ltfj_notam.ham_metinleri_ekle).
    sahte_getir.assert_called_once_with("LTFJ", {})
    assert "abc-123" in state["notam_gecmisi"]
    assert state["notam_son_senkron"] is not None


def test_senkronize_ag_hatasinda_gecmisi_bozmaz(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": True, "location": "LTFJ"}))
    monkeypatch.setattr(b.notam_client, "api_anahtari_var_mi", lambda: True)
    eski_gecmis = {"onceden-gorulmus": {"first_seen": "t1", "last_seen": "t1"}}
    state = {"notam_gecmisi": dict(eski_gecmis), "notam_son_senkron": None}
    with patch.object(ltfj_notam, "yururlukteki_ve_yaklasan_notamlar",
                       side_effect=ltfj_notam.NotamServisHatasi("NOTAC erişilemedi")):
        b.notam_senkronize(state)
    # NOTAC basarisiz oldugunda daha once cekilmis NOTAM gecmisi SILINMEZ,
    # sadece bu turdaki senkronizasyon atlanir (notam_son_senkron ilerlemez).
    assert state["notam_gecmisi"] == eski_gecmis
    assert state["notam_son_senkron"] is None


# ------------------------------------------- elle zorlanan senkron
# Süre kapısı koşunun NASIL başladığına bakmıyordu, yani elle
# tetiklenen bir koşu da atlanıyordu: "az önce NOTAM yayımlandı, şimdi
# çek" demenin yolu yoktu. İş akışındaki kutu bu ortam değişkenini
# ayarlıyor (bkz. .github/workflows/ltfj.yml).
def test_zorlama_SURE_KAPISINI_atliyor(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": True}))
    monkeypatch.setattr(b.notam_client, "api_anahtari_var_mi", lambda: True)
    _aralik(monkeypatch, 3)
    son = datetime.now(timezone.utc).isoformat(timespec="seconds")   # AZ ÖNCE

    monkeypatch.delenv("NOTAM_ZORLA_SENKRON", raising=False)
    assert b._notam_senkron_gerekli_mi({"notam_son_senkron": son}) is False

    monkeypatch.setenv("NOTAM_ZORLA_SENKRON", "true")
    assert b._notam_senkron_gerekli_mi({"notam_son_senkron": son}) is True


@pytest.mark.parametrize("deger,beklenen", [
    ("true", True), ("True", True), ("TRUE", True), ("1", True),
    ("yes", True), ("evet", True), ("on", True), ("  true  ", True),
    ("false", False), ("False", False), ("0", False), ("", False),
    ("hayir", False), ("null", False),
])
def test_zorlama_bayragi_DIZE_olarak_dogru_okunuyor(monkeypatch, deger, beklenen):
    """EN KRİTİK AYRINTI. GitHub Actions boolean girdiyi "true"/"false"
    DİZESİ olarak veriyor; zamanlanmış koşularda ise hiç vermiyor (boş
    dize). Düz bool() yanlış olurdu: bool("false") -> True, yani kutu
    işaretlenmemişken de zorlama devreye girer ve her elle koşuda
    NOTAC'a gidilirdi."""
    monkeypatch.setenv("NOTAM_ZORLA_SENKRON", deger)
    assert b._cevre_bayragi("NOTAM_ZORLA_SENKRON") is beklenen


def test_zorlama_OZELLIK_KAPALIYKEN_calismiyor(monkeypatch):
    """Zorlama bir BEKLEMEYİ atlıyor, bir ÖNKOŞULU değil."""
    monkeypatch.setenv("NOTAM_ZORLA_SENKRON", "true")
    monkeypatch.setattr(b.notam_client, "api_anahtari_var_mi", lambda: True)
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": False}))
    assert b._notam_senkron_gerekli_mi({}) is False


def test_zorlama_API_ANAHTARI_YOKKEN_calismiyor(monkeypatch):
    """Anahtarsız istek atmak anlamsız - zorlamak da düzeltmez."""
    monkeypatch.setenv("NOTAM_ZORLA_SENKRON", "true")
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": True}))
    monkeypatch.setattr(b.notam_client, "api_anahtari_var_mi", lambda: False)
    assert b._notam_senkron_gerekli_mi({}) is False


def test_is_akisi_kutuyu_ortam_degiskenine_BAGLIYOR():
    """Kod tarafı hazır olup iş akışı bağlanmasaydı kutu hiçbir şey
    yapmazdı - sessizce."""
    import yaml
    from pathlib import Path
    d = yaml.safe_load(Path(".github/workflows/ltfj.yml").read_text(encoding="utf-8"))
    tetik = d[True] if True in d else d["on"]
    assert "notam_zorla" in tetik["workflow_dispatch"]["inputs"]
    assert tetik["workflow_dispatch"]["inputs"]["notam_zorla"]["default"] is False
    assert d["jobs"]["bildir"]["env"]["NOTAM_ZORLA_SENKRON"] == "${{ inputs.notam_zorla }}"
