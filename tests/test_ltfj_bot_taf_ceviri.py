"""TAF'lar da METAR gibi Claude ile Turkce'ye cevriliyor mu, ve bu ceviri
sabitlenmis 'su an' mesajinda (durum_mesaji_kur) gorunuyor mu?

Onceden durum_mesaji_kur() TAF'i sadece ham metin olarak gosteriyordu,
ceviri sadece TAF ayri bir bildirim olarak gonderildiginde devreye
giriyordu. Bu testler o bosluk kapatilirken eklendi."""
from unittest.mock import patch

import ltfj_bot as b


def _sahte_claude(metin="Genel: Hava genel olarak açık ve sakin.\n- 12/17Z rüzgâr batıdan hafif esiyor."):
    cagri_sayaci = {"n": 0}

    def fake_post(url, headers=None, json=None, timeout=None):
        cagri_sayaci["n"] += 1

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"content": [{"text": metin}]}
        return R()

    return fake_post, cagri_sayaci


def test_taf_cevirisi_durum_mesajinda_gorunur(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    fake_post, sayac = _sahte_claude()
    taf = {"tip": "TAF", "duzeltme": None, "id": 1, "zaman": None,
           "metin": "TAF LTFJ 161100Z 1612/1712 06010KT 9999 SCT025"}

    with patch("requests.post", fake_post):
        state = b.state_oku()
        mesaj = b.durum_mesaji_kur([taf], state)

    assert "<b>Genel:</b> Hava genel olarak açık" in mesaj
    assert "TAF LTFJ 161100Z" in mesaj   # ham bulten hala gosteriliyor
    assert sayac["n"] == 1


def test_taf_cevirisi_onbelleklenir_tekrar_sorulmaz(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    fake_post, sayac = _sahte_claude()
    taf = {"tip": "TAF", "duzeltme": None, "id": 1, "zaman": None,
           "metin": "TAF LTFJ 161100Z 1612/1712 06010KT 9999 SCT025"}

    with patch("requests.post", fake_post):
        state = b.state_oku()
        b.durum_mesaji_kur([taf], state)
        b.durum_mesaji_kur([taf], state)   # ayni TAF, ikinci cagri

    assert sayac["n"] == 1


def test_taf_sablonu_dikkat_satiri_istemiyor():
    """Kullanicinin acik istegi: TAF cevirisi yorum/degerlendirme
    icermemeli. Sablon Claude'a boyle bir satir uretmemesini soyluyor -
    'Dikkat:' etiketi artik sablonda yok."""
    assert "Dikkat:" not in b.TAF_SABLONU
    assert "yorumunu" in b.TAF_SABLONU or "ÇEVİRİ" in b.TAF_SABLONU


def test_taf_yoksa_hata_vermez(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    state = b.state_oku()
    mesaj = b.durum_mesaji_kur([], state)
    assert "TAF" not in mesaj
