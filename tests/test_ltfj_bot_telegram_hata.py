"""telegram_duzenle()/telegram_sabitle() Telegram'dan ag hatasi alirsa
(orn. requests.exceptions.ReadTimeout) cokmemeli - [uyarı] basip kosuyu
devam ettirmeli.

Onceden sadece RuntimeError yakalaniyordu; Telegram zaman asimi
requests.exceptions.ReadTimeout olarak main()'e kadar sizip kosuyu exit 1
ile dusuruyordu (state_yaz() hic calismiyor, web/panel guncellenmiyordu).
Bu testler _tg'yi monkeypatch ile ReadTimeout firlatmaya zorlayarak
telegram_duzenle()'in False dondurdugunu, telegram_sabitle()'in ise
cokmedigini dogrular."""
import requests

import ltfj_bot as b


def _zaman_asimi_firlatan(token, yontem, **veri):
    raise requests.exceptions.ReadTimeout(
        "HTTPSConnectionPool(host='api.telegram.org'): read timed out (20)")


def test_duzenle_zaman_asiminda_false_doner_cokmez(monkeypatch, capsys):
    monkeypatch.setattr(b, "_tg", _zaman_asimi_firlatan)
    assert b.telegram_duzenle("tok", "chat", 123, "metin") is False
    assert "[uyarı]" in capsys.readouterr().err


def test_sabitle_zaman_asiminda_cokmez(monkeypatch, capsys):
    monkeypatch.setattr(b, "_tg", _zaman_asimi_firlatan)
    b.telegram_sabitle("tok", "chat", 123)
    assert "[uyarı]" in capsys.readouterr().err


def test_duzenle_not_modified_hala_true(monkeypatch):
    """Regresyon: RuntimeError('... not modified ...') yolu degismemeli -
    icerik ayniysa Telegram hata doner, bu bir sorun degil."""
    def fake_tg(token, yontem, **veri):
        raise RuntimeError("Telegram editMessageText reddetti: "
                           "Message is not modified")
    monkeypatch.setattr(b, "_tg", fake_tg)
    assert b.telegram_duzenle("tok", "chat", 123, "metin") is True


def test_duzenle_basarida_true_doner(monkeypatch):
    """Genis exception yakalamanin normal basarili yolu bozmadigini
    dogrular."""
    monkeypatch.setattr(b, "_tg", lambda token, yontem, **veri: {"message_id": 123})
    assert b.telegram_duzenle("tok", "chat", 123, "metin") is True
