"""Sayfanin yazi tipi (IBM Plex Sans/Mono) sozlesmesi.

En kritik iki test:
(1) Bildirilen her woff2 dosyasi DEPODA GERCEKTEN VAR - yoksa sayfa
    hata vermez, sessizce sistem fontuna duser ve kimse fark etmez.
(2) Sayfa fonts.googleapis.com'a istek ATMAZ - dosyalar kendi
    depomuzdan servis edilir. Sebep: sayfa havalimani agindan
    aciliyor, ucuncu taraf CDN engellenebilir.
"""
import re
from pathlib import Path

import ltfj_sayfa as s

KOK = Path(__file__).resolve().parent.parent


def _sayfa(tmp_path) -> str:
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([], [], hedef)
    return hedef.read_text(encoding="utf-8")


def _aralik_coz(aralik: str) -> list:
    """"U+0100-02BA, U+0131" -> [(0x100, 0x2BA), (0x131, 0x131)]"""
    cikti = []
    for parca in aralik.split(","):
        p = parca.strip().removeprefix("U+")
        if "-" in p:
            bas, son = p.split("-")
            cikti.append((int(bas, 16), int(son, 16)))
        else:
            cikti.append((int(p, 16), int(p, 16)))
    return cikti


def _kapsiyor(aralik: str, karakter: str) -> bool:
    kod = ord(karakter)
    return any(bas <= kod <= son for bas, son in _aralik_coz(aralik))


# --------------------------------------------------- dosyalar gercekten var
def test_bildirilen_her_dosya_depoda_var():
    """Sessiz bozulma korumasi: @font-face var ama dosya yoksa tarayici
    hic sikayet etmez, yedek yiginla cizer."""
    for _, dosya, _, _ in s.YAZITIPI_DOSYALARI:
        yol = KOK / s.YAZITIPI_KLASORU / dosya
        assert yol.exists(), f"eksik yazi tipi dosyasi: {yol}"
        assert yol.stat().st_size > 5000, f"supheli kucuk dosya: {yol}"


def test_dosyalar_gercekten_woff2():
    """Yarim inmis/HTML hata sayfasi olarak kaydedilmis bir dosya
    commit edilmesin - woff2 sihirli imzasi 'wOF2'."""
    for _, dosya, _, _ in s.YAZITIPI_DOSYALARI:
        bas = (KOK / s.YAZITIPI_KLASORU / dosya).read_bytes()[:4]
        assert bas == b"wOF2", f"{dosya}: woff2 degil ({bas!r})"


def test_klasorde_bildirilmemis_dosya_kalmamis():
    """Ters yon: yazitipi/ icinde @font-face'i olmayan dosya varsa ya
    unutulmus ya da olu agirlik."""
    diskte = {y.name for y in (KOK / s.YAZITIPI_KLASORU).glob("*.woff2")}
    bildirilen = {d for _, d, _, _ in s.YAZITIPI_DOSYALARI}
    assert diskte == bildirilen



def test_ofl_lisansi_fontlarla_birlikte_duruyor():
    """SIL OFL, yazi tipini YENIDEN DAGITIRKEN lisans metninin de
    birlikte dagitilmasini sart kosar - fontlari depoya koyduk, lisans
    da yanlarinda durmali."""
    lisans = KOK / s.YAZITIPI_KLASORU / "LICENSE.txt"
    assert lisans.exists()
    metin = lisans.read_text(encoding="utf-8")
    assert "SIL Open Font License" in metin
    assert "IBM Corp" in metin


# ------------------------------------------------------- ucuncu taraf yok
def test_sayfa_google_fonts_e_istek_atmiyor(tmp_path):
    html = _sayfa(tmp_path)
    assert "fonts.googleapis.com" not in html
    assert "fonts.gstatic.com" not in html


def test_font_yollari_goreceli(tmp_path):
    """index.html depo kokunde, yazitipi/ onun yaninda - mutlak yol
    (ornegin /yazitipi/...) proje alt dizinde yayinlanirsa kirilir."""
    html = _sayfa(tmp_path)
    for yol in re.findall(r'src:url\("([^"]+)"\)', html):
        assert yol.startswith(s.YAZITIPI_KLASORU + "/"), yol


# ----------------------------------------------------------- Turkce kapsam
def test_turkce_harfler_bildirilen_araliklarda():
    """Turkce latin alt kumesine SIGMAZ - g-breve/s-cedilla/I latin-ext'te.
    Ikisi de gomulu olmazsa sayfa yari Plex yari sistem fontu gorunur."""
    sans = [a for aile, _, _, a in s.YAZITIPI_DOSYALARI if aile == "IBM Plex Sans"]
    assert len(sans) == 2, "Plex Sans icin latin + latin-ext ikisi de olmali"
    for harf in "ğĞşŞıİçÇöÖüÜâÂ":
        assert any(_kapsiyor(a, harf) for a in sans), f"kapsanmayan harf: {harf}"


def test_mono_da_turkce_kapsiyor():
    mono = [a for aile, _, _, a in s.YAZITIPI_DOSYALARI if aile == "IBM Plex Mono"]
    for harf in "ğşıİ":
        assert any(_kapsiyor(a, harf) for a in mono), harf


# ------------------------------------------------------------- davranis
def test_font_display_swap(tmp_path):
    """Operasyonel sayfada "yazi hic yok" hali "yazi biraz sonra
    degisti" halinden cok daha kotu - swap sart."""
    html = _sayfa(tmp_path)
    assert html.count("font-display:swap") == len(s.YAZITIPI_DOSYALARI)


def test_yedek_yigin_duruyor(tmp_path):
    """Plex inmezse sayfa okunmaz olmasin - sistem fontu yedekte."""
    html = _sayfa(tmp_path)
    assert '"IBM Plex Sans",ui-sans-serif,system-ui' in html
    assert '"IBM Plex Mono",ui-monospace' in html


def test_sans_degisken_ara_agirliklari_tasiyor(tmp_path):
    """Sayfa font-weight:650'yi 20'den fazla yerde kullaniyor; statik
    400/700 ile bunlar yuvarlanirdi."""
    html = _sayfa(tmp_path)
    assert "font-weight:400 700" in html
    assert "font-weight:650" in html


# ------------------------------------------------------ tek kaynak (mono)
def test_mono_yigini_tek_yerde_tanimli(tmp_path):
    """Ayni mono yigini eskiden 6 ayri kuralda KOPYALANMISTI - biri
    guncellenip otekiler unutulabilirdi (bu projede daha once oldu)."""
    html = _sayfa(tmp_path)
    assert html.count("--mono:") == 1
    assert "font-family:ui-monospace,SFMono-Regular" not in html
    assert html.count("font-family:var(--mono)") >= 5
