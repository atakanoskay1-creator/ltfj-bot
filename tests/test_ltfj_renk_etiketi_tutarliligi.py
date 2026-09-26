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


def test_ltfj_sayfa_RENK_KODUNU_GOSTERMIYOR():
    """SÖZLEŞME TERSİNE ÇEVRİLDİ. Eskiden bu test sayfadaki renk
    rozetinin Telegram ile AYNI etiketi kullandığını doğruluyordu.
    Artık sayfa o ölçeği hiç göstermiyor: BLU/WHT/GRN/YLO/AMB/RED bota
    özgü bir ciddiyet ölçeğiydi ve gösterildiği her yerde "resmî bir
    ICAO CAT kategorisi değildir" diye kendini yalanlamak zorundaydı.
    Sayfanın durum göstergesi artık VFR/IFR (ICAO Annex 2, Tablo 3-1).

    TELEGRAM TARAFI DEĞİŞMEDİ - orada ölçek çalışmaya devam ediyor.
    Bu test ikisini birden kilitliyor: sayfada YOK, Telegram'da VAR."""
    from datetime import datetime, timezone
    from pathlib import Path as _P
    import tempfile
    from ltfj_sayfa import sayfa_yaz

    metin = "METAR LTFJ 161250Z 06010KT 9999 SCT025 BKN040 18/12 Q1015 NOSIG"
    with tempfile.TemporaryDirectory() as d:
        hedef = _P(d) / "i.html"
        sayfa_yaz([{"tip": "METAR", "icao": "LTFJ", "metin": metin,
                    "zaman": datetime(2026, 9, 16, 12, 50, tzinfo=timezone.utc)}],
                  [], hedef, {}, "", "")
        sayfa = hedef.read_text(encoding="utf-8")

    for kod in ("BLU", "WHT", "GRN", "YLO", "AMB"):
        assert kod not in sayfa, f"renk kodu {kod} hala sayfada"
    # "RED" bir alt dize olarak masum kelimelerde gecebilir; kendi
    # basina bir rozet/kod olarak gecmemeli.
    assert ">RED<" not in sayfa and "RED ·" not in sayfa
    assert RENK_ETIKETI not in sayfa, "renk olceginin etiketi hala sayfada"

    # Telegram tarafi AYNEN duruyor.
    import ltfj_pist
    assert ltfj_pist.renk_durumu({"gorus": 500, "tavan": 200})[0] in (
        "BLU", "WHT", "GRN", "YLO", "AMB", "RED")
    assert set(ltfj_pist.RENK_SIMGE) == {"BLU", "WHT", "GRN", "YLO", "AMB", "RED"}

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
