"""push_testi.py testleri.

En kritik ayrım: "abone yok" ve "abone var ama gönderilemedi" durumları
BAŞARI SAYILMAMALI (çıkış kodu 1) - aksi halde Actions adımı yeşil yanar,
kullanıcı bildirimlerin çalıştığını sanır. Zaten bu projede tam olarak bu
tür sessiz bir başarı yanılgısı yaşandı (bkz. ltfj_bot._push_gonder_guvenli).
"""
import sys
import types
from unittest.mock import MagicMock

import pytest

import push_testi


@pytest.fixture
def sahte_push(monkeypatch):
    fake = types.ModuleType("ltfj_push")
    fake.yapilandirilmis_mi = MagicMock(return_value=True)
    fake.gonder = MagicMock(
        return_value={"abone": 2, "gonderildi": 2, "silindi": 0, "hata": 0})

    class _Hata(Exception):
        pass

    fake.PushGonderimHatasi = _Hata
    monkeypatch.setitem(sys.modules, "ltfj_push", fake)
    monkeypatch.setattr(push_testi, "ltfj_push", fake)
    return fake


def test_basarili_gonderimde_sifir_doner(sahte_push):
    assert push_testi.main() == 0


def test_abone_yoksa_basarisiz_sayilir(sahte_push, capsys):
    sahte_push.gonder.return_value = {
        "abone": 0, "gonderildi": 0, "silindi": 0, "hata": 0}
    assert push_testi.main() == 1
    assert "Kayıtlı abone YOK" in capsys.readouterr().err


def test_abone_var_ama_hic_gonderilemediyse_basarisiz_sayilir(sahte_push, capsys):
    sahte_push.gonder.return_value = {
        "abone": 3, "gonderildi": 0, "silindi": 1, "hata": 2}
    assert push_testi.main() == 1
    assert "gönderilemedi" in capsys.readouterr().err


def test_yapilandirilmamissa_gonderim_denenmez(sahte_push):
    sahte_push.yapilandirilmis_mi.return_value = False
    assert push_testi.main() == 1
    sahte_push.gonder.assert_not_called()


def test_push_kapaliysa_gonderim_denenmez(sahte_push, monkeypatch):
    monkeypatch.setattr(push_testi, "ayar",
                        lambda *yol, varsayilan=None: False if yol[:2] == ("push", "aktif")
                        else varsayilan)
    assert push_testi.main() == 1
    sahte_push.gonder.assert_not_called()


def test_gonderim_hatasi_yakalaniyor(sahte_push):
    sahte_push.gonder.side_effect = sahte_push.PushGonderimHatasi("Firebase okunamadı")
    assert push_testi.main() == 1


def test_govde_bunun_bir_test_oldugunu_acikca_soyluyor():
    """Kontrolörün ekranına düşen bir bildirim, gerçek bir hava durumu
    uyarısıyla KARIŞTIRILMAMALI."""
    assert "test" in push_testi.GOVDE.lower()
    assert "gerçek bir hava durumu uyarısı değildir" in push_testi.GOVDE


def test_ana_akisa_dokunmuyor():
    """push_testi.py METAR/TAF akışından TAMAMEN bağımsız olmalı - state
    okumaz/yazmaz, Telegram'a mesaj atmaz, ltfj_bot'u import etmez."""
    import ast
    from pathlib import Path

    kok = Path(__file__).resolve().parent.parent
    agac = ast.parse((kok / "push_testi.py").read_text(encoding="utf-8"))
    adlar = set()
    for node in ast.walk(agac):
        if isinstance(node, ast.Import):
            adlar.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            adlar.add(node.module.split(".")[0])
    assert adlar == {"sys", "ltfj_push", "ltfj_ayarlar"}
