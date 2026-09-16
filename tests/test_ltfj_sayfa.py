"""ltfj_sayfa.py::sayfa_yaz/_kart testleri.

Bug raporu: kullanıcı web sayfasında bir pistin (06L) rüzgâr bileşenlerinin
diğerleriyle (06R/24L/24R) AYNI kesinlikte gösterildiğini, oysa 06L için
RMK'da ayrı bir anemometre kaydı OLMADIĞINI (alan METAR rüzgarından
hesaplandığını) fark edemediğini bildirdi. Kaynak (bkz. ltfj_pist.pist_
raporu()'nun "(...)" satırı) Telegram/ATC panelinde zaten gösteriliyordu,
web sayfası bunu sessizce filtreliyordu - asıl hata buydu.

Ayrıca: TAF için web sayfasında hiçbir açıklayıcı/çevrilmiş bilgi yoktu -
Telegram'ın zaten önbelleklediği Claude yorumu (state.yorum_onbellegi) web
sayfasına hiç aktarılmıyordu."""
from datetime import datetime, timezone

import ltfj_sayfa as s

SPECI_KISMI_RMK = {
    "tip": "SPECI",
    "metin": (
        "SPECI LTFJ 160348Z 04008KT 9999 -SHRA BKN035 BKN080 18/15 Q1016 "
        "NOSIG RMK RWY24R 02007KT RWY06R 03008KT RWY24L 03007KT"
    ),
    "zaman": datetime(2026, 9, 16, 3, 48, tzinfo=timezone.utc),
    "icao": "LTFJ",
}

TAF_ORNEK = {
    "tip": "TAF",
    "metin": "TAF LTFJ 161100Z 1612/1712 06010KT 9999 SCT025",
    "zaman": datetime(2026, 9, 16, 11, 0, tzinfo=timezone.utc),
    "icao": "LTFJ",
}


def test_pist_kaynagi_satiri_web_sayfasinda_gorunur(tmp_path):
    """06L icin RMK'da ayri anemometre kaydi yok - 'alan rüzgârından'
    ibaresi (kaynak satiri) artik SESSIZCE filtrelenmemeli."""
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([SPECI_KISMI_RMK], [], hedef)
    html = hedef.read_text(encoding="utf-8")
    assert "alan rüzgârından" in html
    assert "AD 2.15 anemometreleri" in html


def test_pist_kaynagi_satiri_pist_tablosunda_tekrar_etmez(tmp_path):
    """Kaynak notu ayri bir satir olarak gorunmeli, pist satirlarinin
    kendisi '(' ile baslayan cop metin icermemeli."""
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([SPECI_KISMI_RMK], [], hedef)
    html = hedef.read_text(encoding="utf-8")
    assert "<td>(" not in html


def test_yorum_onbellegi_verilmezse_sayfa_hata_vermez(tmp_path):
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([SPECI_KISMI_RMK, TAF_ORNEK], [], hedef)
    html = hedef.read_text(encoding="utf-8")
    assert "SPECI" in html and "TAF" in html
    assert 'class="yorum"' not in html


def test_metar_speci_yorumu_web_sayfasinda_gosterilir(tmp_path):
    yorum = "Rüzgâr: 040 derece yönden 8 knot, hafif.\nGörüş: 10 km üzeri, rahat."
    onbellek = {SPECI_KISMI_RMK["metin"]: yorum}
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([SPECI_KISMI_RMK], [], hedef, onbellek)
    html = hedef.read_text(encoding="utf-8")
    assert "<b>Rüzgâr:</b> 040 derece yönden 8 knot, hafif." in html


def test_taf_yorumu_web_sayfasinda_gosterilir():
    """Ana hata: TAF icin web sayfasinda hicbir aciklayici bilgi yoktu -
    artik state.yorum_onbellegi'nden (Telegram ile PAYLASILAN onbellek)
    okunan yorum TAF kartinda da gorunmeli."""
    import tempfile
    from pathlib import Path

    yorum = "Genel: Hava genel olarak açık ve sakin.\n- 16/17Z rüzgâr batıdan hafif esiyor."
    onbellek = {TAF_ORNEK["metin"]: yorum}
    with tempfile.TemporaryDirectory() as d:
        hedef = Path(d) / "index.html"
        s.sayfa_yaz([TAF_ORNEK], [], hedef, onbellek)
        html = hedef.read_text(encoding="utf-8")
    assert "<b>Genel:</b> Hava genel olarak açık ve sakin." in html
    assert "•" in html  # "- ..." satırı bullet'a çevrilir


def test_yorum_onbellek_anahtari_baska_rapora_sizmaz():
    """onbellek baska bir raporun ham metnini iceriyorsa bu raporun
    kartina KARISMAMALI (anahtar tam metin esitligiyle calisiyor)."""
    import tempfile
    from pathlib import Path

    onbellek = {"BASKA BIR METAR METNI": "Genel: alakasız yorum."}
    with tempfile.TemporaryDirectory() as d:
        hedef = Path(d) / "index.html"
        s.sayfa_yaz([TAF_ORNEK], [], hedef, onbellek)
        html = hedef.read_text(encoding="utf-8")
    assert "alakasız" not in html
