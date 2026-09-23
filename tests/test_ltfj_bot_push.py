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
    fake.gonder = MagicMock(
        return_value={"abone": 1, "gonderildi": 1, "silindi": 0, "hata": 0})
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


# --------------------------------------------- sessiz basarisizlik OLMAMALI
# 21.09.2026: TAF Telegram'a gitti ama push logda HIC gorunmedi - eski kod
# sadece gonderildi/silindi > 0 ise yazdirirdi, bu yuzden "abone yok",
# "hepsi hata verdi" ve "push hic denenmedi" AYIRT EDILEMIYORDU. Asagidaki
# testler her durumun loga DUSTUGUNU garanti eder.
def test_abone_yoksa_log_bunu_acikca_soyluyor(capsys, sahte_ltfj_push):
    sahte_ltfj_push.gonder.return_value = {
        "abone": 0, "gonderildi": 0, "silindi": 0, "hata": 0}
    bot.push_bildirimi_gonder(_rapor("TAF"), None, None)
    cikti = capsys.readouterr().out
    assert "push [TAF]" in cikti
    assert "abone YOK" in cikti


def test_abone_var_ama_hepsi_hata_verirse_log_hatayi_gosteriyor(capsys, sahte_ltfj_push):
    """En sinsi durum: abonelikler duruyor ama her gonderim patliyor.
    Eskiden bu TAMAMEN sessizdi (gonderildi=0, silindi=0)."""
    sahte_ltfj_push.gonder.return_value = {
        "abone": 3, "gonderildi": 0, "silindi": 0, "hata": 3}
    bot.push_bildirimi_gonder(_rapor("TAF"), None, None)
    cikti = capsys.readouterr().out
    assert "3 abone" in cikti and "0 gönderildi" in cikti and "3 hata" in cikti


def test_yapilandirilmamissa_sebebi_loga_yaziliyor(capsys, sahte_ltfj_push):
    sahte_ltfj_push.yapilandirilmis_mi.return_value = False
    bot.push_bildirimi_gonder(_rapor("TAF"), None, None)
    cikti = capsys.readouterr().out
    assert "atlandı" in cikti and "VAPID_PRIVATE_KEY" in cikti


def test_push_kapaliysa_sebebi_loga_yaziliyor(capsys, monkeypatch, sahte_ltfj_push):
    monkeypatch.setattr(bot, "ayar",
                        lambda *a, **k: False if a[:2] == ("push", "aktif") else k.get("varsayilan"))
    bot.push_bildirimi_gonder(_rapor("TAF"), None, None)
    cikti = capsys.readouterr().out
    assert "atlandı" in cikti and "aktif" in cikti
    sahte_ltfj_push.gonder.assert_not_called()


# ============================== Telegram çökünce push ATLANMAMALI (regresyon)
# GERCEK KUSUR: Telegram hatasi 'continue' ile donguyu atliyordu ve push da
# onunla birlikte atlaniyordu - yani push'un EN COK gerektigi anda (Telegram
# cokmus, geriye tek kanal kalmis) hic denenmiyordu. Koddaki aciklama
# "Telegram basarisiz olsa da dener" deyip parantez icinde kendi kendini
# yalanliyordu.
#
# NOT: bu testler AST ile yazildi, metin aramasiyla DEGIL. Ilk yazilislarinda
# duz metin arayan surum, ACIKLAMA SATIRINDA gecen kelimeyi kodla karistirdi
# (bu oturumda ucuncu kez ayni tuzak).
import ast
import inspect

import ltfj_bot


def _main_agaci():
    return ast.parse(inspect.getsource(ltfj_bot.main))


def _satir(agac, kosul) -> int:
    for n in ast.walk(agac):
        if kosul(n):
            return n.lineno
    return -1


def test_telegram_HATA_BLOGUNDA_continue_YOK():
    """EN KRITIK REGRESYON TESTI: iki bildirim kanali bagimsiz olmali.

    Dogru kosul, "push'tan sonra bir continue var mi" DEGIL (bu her zaman
    dogru, cunku yeniden deneme continue'su zaten orada duruyor) - ilk
    yazilisim tam da bu yuzden kusuru geri koydugumda YESIL kaldi.
    Asil kosul: Telegram'in except blogunun ICINDE continue olmamali,
    cunku oradaki bir continue push'u da atlatir."""
    for n in ast.walk(_main_agaci()):
        if not isinstance(n, ast.ExceptHandler):
            continue
        govde = ast.dump(ast.Module(body=n.body, type_ignores=[]))
        if "GÖNDERİLEMEDİ" not in govde:
            continue
        assert "Continue" not in govde, (
            "Telegram hata blogunda 'continue' var - push da atlanir, "
            "yani push'un EN COK gerektigi anda (Telegram cokmus) "
            "hic denenmez. Kusur geri gelmis.")
        return
    raise AssertionError("Telegram hata blogu bulunamadi - test guncellenmeli")


def test_push_cagrisi_gercekten_var():
    """Yukaridaki test tek basina, push cagrisi SILINSE de yesil kalirdi."""
    assert any(isinstance(n, ast.Call)
               and getattr(n.func, "id", "") == "push_bildirimi_gonder"
               for n in ast.walk(_main_agaci()))


def test_yeniden_deneme_semantigi_KORUNUYOR():
    """Telegram basarisizsa rapor 'gonderilen'e girmemeli ki sonraki
    kosuda tekrar denensin - 'continue' bu yuzden duruyor."""
    agac = _main_agaci()
    devam = [n for n in ast.walk(agac) if isinstance(n, ast.Continue)]
    assert devam, "'continue' kaldirilmis - yeniden deneme semantigi kaybolur"
    ekleme = _satir(agac, lambda n: isinstance(n, ast.Call)
                    and getattr(n.func, "attr", "") == "add"
                    and getattr(n.func.value, "id", "") == "gorulen")
    assert ekleme > max(d.lineno for d in devam if d.lineno < ekleme)


def test_push_izi_telegramdan_AYRI():
    """Push 'gonderilen'e baglanmis olsaydi Telegram yeniden denenirken
    push da ikinci kez giderdi - ayni uyari iki kez."""
    assert "push_gonderilen" in ltfj_bot.state_oku()
    ana = inspect.getsource(ltfj_bot.main)
    assert "push_gonderilen" in ana


def test_push_izi_budaniyor():
    """Liste sonsuza kadar buyumemeli."""
    agac = _main_agaci()
    atamalar = [n for n in ast.walk(agac) if isinstance(n, ast.Assign)]
    hedefler = [ast.unparse(t) for a in atamalar for t in a.targets]
    assert 'state[\'push_gonderilen\']' in hedefler or \
           'state["push_gonderilen"]' in hedefler
