"""Renk rozeti (BLU/WHT/GRN/YLO/AMB/RED) etiketi TEK kaynaktan
(ltfj_pist.RENK_ETIKETI) gelmeli - Telegram, web sayfasi ve ATC paneli
kendi ayri sabit metin kopyalarini tutarsa zamanla birbirinden sessizce
sapabilir. Nitekim bu tam olarak oldu: Telegram ve panel.html "LTFJ Bot
seviyesi" (kelime eksik) yaziyordu, web sayfasi ve panelin baska bir
yeri ise "LTFJ Bot durum seviyesi" - kullanici ATC panelinde bunu fark
edip bildirdi. Bu testler etiketin her tuketicide AYNI oldugunu sabitler."""
import re
from pathlib import Path

import ornekler as o
import ltfj_bot as b
from ltfj_analiz import metar_coz
from ltfj_panel import _metar_json
from ltfj_pist import RENK_ETIKETI, havacilik_notlari


def test_renk_etiketi_sabit_deger():
    assert RENK_ETIKETI == "LTFJ Bot durum seviyesi"


def test_havacilik_notlari_renk_etiketi_canonical_ile_ayni():
    d = metar_coz(o.NORMAL)
    n = havacilik_notlari(d, o.NORMAL, None)
    assert n["renk_etiketi"] == RENK_ETIKETI


def test_telegram_baslik_canonical_etiketi_kullanir():
    d = metar_coz(o.NORMAL)
    rapor = {"tip": "METAR", "duzeltme": None, "id": 1, "zaman": None, "metin": o.NORMAL}
    notlar = havacilik_notlari(d, o.NORMAL, None)
    baslik = b.baslik_kur(rapor, notlar)
    assert RENK_ETIKETI in baslik
    assert "LTFJ Bot seviyesi" not in baslik   # eksik kelimeli eski hatali metin


def test_ltfj_sayfa_rozeti_canonical_etiketi_kullanir():
    import ltfj_sayfa as s
    rapor = {"tip": "METAR", "duzeltme": None, "zaman": None, "metin": o.NORMAL, "icao": "LTFJ"}
    kart = s._kart(rapor)
    assert RENK_ETIKETI in kart


def test_panel_json_renk_etiketi_alanini_tasir():
    rapor = {"tip": "METAR", "duzeltme": None, "zaman": None, "metin": o.NORMAL}
    veri = _metar_json(rapor)
    assert veri["renk_etiketi"] == RENK_ETIKETI


def test_panel_html_hardcoded_eksik_etiket_icermez():
    """panel.html'nin JS'i artik sabit 'LTFJ Bot seviyesi' (kelime eksik)
    metni YAZMAMALI - renk_etiketi alanindan okumali. Yedek (fallback)
    deger olarak dogru/tam ibare kullanilmasi serbest."""
    panel_html_yolu = Path(__file__).resolve().parent.parent / "panel.html"
    panel_html = panel_html_yolu.read_text(encoding="utf-8")
    # Sadece JS icindeki DEĞİŞKEN olmayan, tam olarak "LTFJ Bot seviyesi"
    # (arkasindan 'durum' gelmeyen) hardcoded string kalmamali.
    assert not re.search(r'"LTFJ Bot seviyesi ', panel_html)
    assert "renk_etiketi" in panel_html
