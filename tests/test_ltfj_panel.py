"""ltfj_panel.py (ATC panel veri ureticisi) testleri.

Daha once bu dosya icin hic test yoktu ve _pist_verisi() kendi ayri
per-pist ruzgar kaynagi mantigini tutuyordu - Telegram tarafinda F2 olarak
duzeltilen "RMK kismen raporlandiginda diger pistler kayboluyor" hatasi
ATC panelinde HALA yasiyordu. Bu testler artik panelin de ortak
pist_ruzgar_kaynagi()'ni kullandigini ve RMK'da gecmeyen pistlerin
kaybolmadigini dogruluyor.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ornekler as o
from ltfj_analiz import metar_coz
from ltfj_panel import _pist_verisi


def test_pist_verisi_rmk_kismiyken_eksik_pist_kaybolmaz():
    """PIST_RUZGARI_RMK'da sadece 06R/24L/24R var, 06L yok. Eskiden
    _pist_verisi() 'olculenler varsa SADECE onlar' mantigiyla 06L'i hic
    listelemiyordu."""
    d = metar_coz(o.PIST_RUZGARI_RMK)
    veri = _pist_verisi(d, o.PIST_RUZGARI_RMK)
    pistler = {p["pist"] for p in veri["pistler"]}
    assert pistler == {"06L", "06R", "24L", "24R"}


def test_pist_verisi_kaynak_pist_bazinda_dogru():
    d = metar_coz(o.PIST_RUZGARI_RMK)
    veri = _pist_verisi(d, o.PIST_RUZGARI_RMK)
    kaynaklar = {p["pist"]: p["kaynak"] for p in veri["pistler"]}
    assert kaynaklar["06L"] == "alan rüzgârından"
    assert kaynaklar["06R"] == "AD 2.15 anemometreleri"
    assert kaynaklar["24L"] == "AD 2.15 anemometreleri"
    assert kaynaklar["24R"] == "AD 2.15 anemometreleri"


def test_pist_verisi_rmk_yoksa_hepsi_alan_ruzgarindan():
    d = metar_coz(o.NORMAL)
    veri = _pist_verisi(d, o.NORMAL)
    assert all(p["kaynak"] == "alan rüzgârından" for p in veri["pistler"])
    assert {p["pist"] for p in veri["pistler"]} == {"06L", "06R", "24L", "24R"}


def test_pist_verisi_hamle_ayri_alanda_tasinir():
    """FIRTINA: 25022G35KT - steady 22, hamle 35. Panel SVG/etiket
    katmaninin steady ve hamle bilesenini ayirt edebilmesi icin ikisi de
    ayri alanlarda (bas/bas_hamle) donmeli - onceden max() ile tek sayiya
    indirgeniyordu, hangisinin steady hangisinin hamle oldugu kayboluyordu."""
    d = metar_coz(o.FIRTINA)
    veri = _pist_verisi(d, o.FIRTINA)
    p = next(p for p in veri["pistler"] if p["pist"] == "06L")
    assert p["bas_hamle"] is not None
    assert abs(p["bas_hamle"]) > abs(p["bas"])


def test_pist_verisi_degisken_bayragi_tasinir():
    """RMK'daki RWY24R 36007KT 340V080 - degisken yon grubu var. Panelin
    bunu 'kesin' bir bas/yan sayisiymis gibi degil, degisken oldugunu
    bilerek gostermesi icin bayrak tasinmali."""
    d = metar_coz(o.PIST_RUZGARI_RMK)
    veri = _pist_verisi(d, o.PIST_RUZGARI_RMK)
    p = next(p for p in veri["pistler"] if p["pist"] == "24R")
    assert p["degisken"] is True
    p_sabit = next(p for p in veri["pistler"] if p["pist"] == "06R")
    assert p_sabit["degisken"] is False
