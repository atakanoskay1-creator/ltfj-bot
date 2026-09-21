"""ltfj_bot.py - Web Push tetikleme mantığı testleri.

En kritik testler:
(1) renk_kotulesti_mi TEK YONLU - iyilesmede (RED->GRN) False donmeli,
    renk_onemli_mi'nin (Telegram, iki yonlu) aksine.
(2) push_tetiklenmeli_mi SADECE SPECI/TAF/duzeltme/renk-kotulesmesinde True -
    rutin METAR ve 'dikkat' (Telegram'da var, kullanıcı Push için istemedi)
    HİÇBİR ZAMAN tetiklemez."""
import sys
import types
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

import ltfj_bot as bot


# ------------------------------------------------------------- renk_kotulesti_mi
def test_renk_kotulesti_mi_gercek_kotulesmede_true():
    assert bot.renk_kotulesti_mi("GRN", "AMB") is True


def test_renk_kotulesti_mi_iyilesmede_false():
    """renk_onemli_mi (Telegram) bunu True dondurur - push farklı davranmalı."""
    assert bot.renk_kotulesti_mi("RED", "GRN") is False
    assert bot.renk_onemli_mi("RED", "GRN") is True   # karşılaştırma için


def test_renk_kotulesti_mi_iyi_bant_ici_oynamada_false():
    assert bot.renk_kotulesti_mi("BLU", "WHT") is False


def test_renk_kotulesti_mi_kotu_banttan_daha_kotuye_true():
    assert bot.renk_kotulesti_mi("YLO", "RED") is True


def test_renk_kotulesti_mi_ayni_renkte_false():
    assert bot.renk_kotulesti_mi("AMB", "AMB") is False


def test_renk_kotulesti_mi_eksik_veride_false():
    assert bot.renk_kotulesti_mi(None, "RED") is False
    assert bot.renk_kotulesti_mi("GRN", None) is False


# ------------------------------------------------------------- push_tetiklenmeli_mi
def _rapor(tip="METAR", duzeltme=None):
    return {"tip": tip, "duzeltme": duzeltme, "zaman": None, "metin": "LTFJ ÖRNEK METİN"}


def test_push_speci_tetikler():
    assert bot.push_tetiklenmeli_mi(_rapor("SPECI"), False) is True


def test_push_taf_tetikler():
    assert bot.push_tetiklenmeli_mi(_rapor("TAF"), False) is True


def test_push_duzeltme_tetikler():
    assert bot.push_tetiklenmeli_mi(_rapor("METAR", duzeltme="AMD"), False) is True


def test_push_renk_kotulesmesi_tetikler():
    assert bot.push_tetiklenmeli_mi(_rapor("METAR"), True) is True


def test_push_rutin_metar_tetiklemez():
    assert bot.push_tetiklenmeli_mi(_rapor("METAR"), False) is False


# --------------------------------------------------------------- icerik
def test_push_baslik_duzeltmede_ozel_simge_ve_etiket():
    assert bot._push_baslik(_rapor("METAR", duzeltme="AMD")) == "✏️ LTFJ METAR (DÜZELTME)"
    assert bot._push_baslik(_rapor("METAR", duzeltme="COR")) == "✏️ LTFJ METAR (DÜZELTİLMİŞ)"


def test_push_baslik_speci_kendi_simgesini_kullanir():
    assert bot._push_baslik(_rapor("SPECI")).startswith("⚠️")


def test_push_govde_taf_icin_sabit_metin():
    rapor = {"tip": "TAF", "zaman": None}
    assert bot._push_govde(rapor, None, None) == "Yeni TAF yayınlandı"


def test_push_govde_renk_bilgisi_iceriyor():
    rapor = {"tip": "METAR", "zaman": None}
    govde = bot._push_govde(rapor, None, ("RED", "Kapalı"))
    assert "RED" in govde and "Kapalı" in govde


# ------------------------------------------------------- push_bildirimi_gonder
@pytest.fixture
def sahte_ltfj_push(monkeypatch):
    fake = types.ModuleType("ltfj_push")
    fake.yapilandirilmis_mi = MagicMock(return_value=True)
    fake.gonder = MagicMock(return_value={"gonderildi": 1, "silindi": 0, "hata": 0})
    monkeypatch.setitem(sys.modules, "ltfj_push", fake)
    return fake


def test_push_bildirimi_gonder_yapilandirilmamissa_cagirmiyor(monkeypatch, sahte_ltfj_push):
    sahte_ltfj_push.yapilandirilmis_mi.return_value = False
    bot.push_bildirimi_gonder(_rapor("SPECI"), None, None)
    sahte_ltfj_push.gonder.assert_not_called()


def test_push_bildirimi_gonder_dogru_parametrelerle_cagiriyor(monkeypatch, sahte_ltfj_push):
    rapor = {"tip": "SPECI", "zaman": datetime(2026, 9, 17, 21, 20, tzinfo=timezone.utc),
             "duzeltme": None}
    bot.push_bildirimi_gonder(rapor, None, None)
    sahte_ltfj_push.gonder.assert_called_once()
    args, kwargs = sahte_ltfj_push.gonder.call_args
    assert args[0] == "⚠️ LTFJ SPECI"
    assert kwargs.get("etiket") == "SPECI"


def test_push_bildirimi_gonder_hata_asla_yukselmiyor(monkeypatch, sahte_ltfj_push):
    """Push gonderiminde HERHANGI bir hata METAR/TAF akisini asla bozmamali."""
    sahte_ltfj_push.gonder.side_effect = RuntimeError("ağ hatası")
    bot.push_bildirimi_gonder(_rapor("SPECI"), None, None)  # exception fırlatmamalı
