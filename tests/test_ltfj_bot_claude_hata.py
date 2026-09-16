"""F3: claude_yorum() Claude'dan gecerli ama beklenmeyen bicimde bir yanit
gelirse (orn. {"content": null}) cokmemeli - sadece yorumu yok saymali.

Onceden sadece requests.RequestException yakalaniyordu; r.json() sonrasi
beklenmeyen sekil (None, dict-olmayan eleman, gecersiz JSON) TypeError/
AttributeError/ValueError olarak sizip claude_yorum()'u ve onu cagiran
durum_mesaji_kur()/main() akisini tamamen cokertiyordu (state_yaz() hic
calismiyor, web/panel guncellenmiyordu). Bu testler her durumda
claude_yorum()'un None dondurdugunu ve calismanin devam ettigini dogrular."""
from unittest.mock import patch

import ltfj_bot as b

_TAF = {"tip": "TAF", "duzeltme": None, "id": 1, "zaman": None,
        "metin": "TAF LTFJ 161100Z 1612/1712 06010KT 9999 SCT025"}


def _sahte_post(json_deger=None, json_hata=None):
    class R:
        def raise_for_status(self):
            pass

        def json(self):
            if json_hata is not None:
                raise json_hata
            return json_deger

    def fake_post(url, headers=None, json=None, timeout=None):
        return R()

    return fake_post


def test_content_null_ise_cokmez_none_doner(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    fake_post = _sahte_post(json_deger={"content": None})
    with patch("requests.post", fake_post):
        assert b.claude_yorum(_TAF, cozum=None) is None


def test_content_icinde_dict_olmayan_eleman_cokmez_none_doner(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    fake_post = _sahte_post(json_deger={"content": ["dict-olmayan-eleman"]})
    with patch("requests.post", fake_post):
        assert b.claude_yorum(_TAF, cozum=None) is None


def test_gecersiz_json_cokmez_none_doner(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    fake_post = _sahte_post(json_hata=ValueError("Expecting value: line 1 column 1"))
    with patch("requests.post", fake_post):
        assert b.claude_yorum(_TAF, cozum=None) is None


def test_content_anahtari_hic_yoksa_zaten_sorunsuz(monkeypatch):
    """Regresyon: .get("content", []) varsayilan degeri sayesinde bu durum
    zaten cokmuyordu - degisiklik bunu bozmamali."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    fake_post = _sahte_post(json_deger={})
    with patch("requests.post", fake_post):
        assert b.claude_yorum(_TAF, cozum=None) is None


def test_gecerli_yanit_hala_calisir(monkeypatch):
    """Genis exception yakalamanin normal basarili yolu bozmadigini
    dogrular."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    fake_post = _sahte_post(json_deger={"content": [{"text": "Merhaba, hava sakin."}]})
    with patch("requests.post", fake_post):
        assert b.claude_yorum(_TAF, cozum=None) == "Merhaba, hava sakin."
