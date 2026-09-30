"""Sayfa hareketi (motion): yalnizca BILGI tasiyan, tek seferlik hareket.

Tarayicidaki davranis Playwright ile olculdu (bkz. PR aciklamasi); bu
testler sozlesmeyi uretilen HTML/CSS/JS metni uzerinden kilitler:
  - hero olculeri ve pist diyagrami okumalari karsilastirma icin
    data-olcu / data-bant tasiyor;
  - ruzgar oku kuzeye cizilip grupla donduruluyor ve geometri eski
    (dogrudan koordinatli) cizimle BIREBIR ayni;
  - her vurgu tek seferlik; surekli dongu yalnizca eski tazelik nabzi;
  - prefers-reduced-motion'da JS hicbir animasyon baslatmiyor;
  - sayilar sayarak (ara degerlerle) degismiyor.
"""
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

import ltfj_sayfa as s

SIMDI = datetime.now(timezone.utc)
KAYNAK = Path("sayfa_kaynak")


def _sayfa(tmp_path, metin="LTFJ 241720Z 06015KT 0600 FG VV002 12/11 Q1008"):
    hedef = tmp_path / "i.html"
    s.sayfa_yaz([{"tip": "METAR", "icao": "LTFJ", "zaman": SIMDI, "metin": metin}], [], hedef)
    return hedef.read_text(encoding="utf-8")


# ================================================================ HTML
def test_hero_olculeri_karsilastirma_icin_isaretli(tmp_path):
    html = _sayfa(tmp_path)
    for anahtar in ("gorus", "tavan", "_ruzgar", "_spread"):
        assert f'data-olcu="{anahtar}"' in html, anahtar
    # bant da tasiniyor: 600 m esik alti, VV002 sinirli
    assert 'data-olcu="gorus" data-bant="uyari"' in html
    assert 'data-olcu="pd-bas"' in html and 'data-olcu="pd-yan"' in html


@pytest.mark.parametrize("yon", [0, 60, 135, 240, 350])
def test_ruzgar_oku_grupla_donuyor_geometri_BIREBIR_ayni(tmp_path, yon):
    html = _sayfa(tmp_path, f"LTFJ 241720Z {yon:03d}15KT 9999 FEW030 12/08 Q1008")
    g = re.search(r'<g class="pd-ok-g" data-yon="(\d+)" transform="rotate\((\d+) 60 60\)">'
                  r'<line class="pd-ok" x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)"',
                  html)
    assert g, "ok grubu yok"
    assert int(g.group(1)) == int(g.group(2)) == yon
    x1, y1, x2, y2 = map(float, g.group(3, 4, 5, 6))
    assert x1 == x2 == 60.0                              # kuzeye cizilmis

    # Donmus uclar = eski cizimin _nokta(yon, r) koordinatlari
    def dondur(x, y):
        a = math.radians(yon)
        dx, dy = x - 60, y - 60
        return (60 + dx * math.cos(a) - dy * math.sin(a),
                60 + dx * math.sin(a) + dy * math.cos(a))

    def nokta(r):
        a = math.radians(yon)
        return (60 + r * math.sin(a), 60 - r * math.cos(a))

    for (x, y), r in (((x1, y1), 38 * 1.16), ((x2, y2), 38 * 0.76)):
        dx, dy = dondur(x, y)
        ex, ey = nokta(r)
        assert abs(dx - ex) < 0.06 and abs(dy - ey) < 0.06


def test_hareket_betigi_sayfada(tmp_path):
    html = _sayfa(tmp_path)
    assert "ltfj-son-gozlem" in html and "olcu-degisti" in html and "esik-girdi" in html


# ================================================================== JS
HAREKET = (KAYNAK / "11_hareket.js").read_text(encoding="utf-8")
NOTAM = (KAYNAK / "03_notam.js").read_text(encoding="utf-8")
BASLIK = (KAYNAK / "02_baslik_tazelik.js").read_text(encoding="utf-8")
CSS = (KAYNAK / "stil.css").read_text(encoding="utf-8")


def test_hareket_azaltma_tercihinde_JS_animasyon_baslatmiyor():
    assert 'matchMedia("(prefers-reduced-motion: reduce)")' in HAREKET
    assert "if (azalt || !el) { return; }" in HAREKET        # tekSefer
    assert "okG && !azalt" in HAREKET                         # ruzgar oku
    assert "prefers-reduced-motion: reduce" in NOTAM          # yeni NOTAM


def test_esik_vurgusu_sonlu_tekrar():
    """Daha guclu ama SONLU: esik cercevesi uc kez atar ve durur."""
    assert "animation:ltfj-esik-uyari 1100ms ease-out 3;" in CSS
    assert "animation:ltfj-esik-dikkat 1100ms ease-out 3;" in CSS


def test_onceki_deger_rozeti_gercek_onceki_okuma_ve_kendini_kaldiriyor():
    """Degisen olcunun yaninda ONCEKI gozlenen deger kisa sure durur;
    ara deger uretilmez, rozet animasyon bitince DOM'dan kalkar."""
    assert 'document.createTextNode("önce " + eskiDeger)' in HAREKET
    assert 'r.addEventListener("animationend"' in HAREKET
    # karsilastirmaya rozet metni karismaz
    assert 'querySelectorAll(".olcu-onceki")' in HAREKET
    assert "position:absolute" in CSS.split(".olcu-onceki {")[1].split("}")[0]


def test_yeni_gozlem_duyurusu_ekran_okuyucuya_da_soyleniyor():
    assert 'k.setAttribute("role", "status")' in HAREKET
    assert '"Yeni gözlem · " + zulu(gozlem)' in HAREKET
    assert 'k.addEventListener("click", kapat)' in HAREKET


def test_kiyas_canli_guncellemeden_sonra_da_cagrilabilir():
    assert "window.ltfjHareketKarsilastir = karsilastir;" in HAREKET
    assert "karsilastir(false);" in HAREKET


def test_ayni_gozlem_yeniden_yuklenince_hicbir_sey_hareket_etmez():
    assert "onceki.gozlem === gozlem) { return; }" in HAREKET
    # ilk ziyaret de karsilastirma yapmaz
    assert "if (!onceki || !onceki.gozlem" in HAREKET


def test_localStorage_hatasi_sayfayi_bozmaz():
    for satir in ("try { onceki = JSON.parse(localStorage.getItem(ANAHTAR)",
                  "try { localStorage.setItem(ANAHTAR"):
        assert satir in HAREKET


def test_ruzgar_oku_kisa_yoldan_donuyor():
    """350 -> 010 dogru donus +20 derece; -340 degil."""
    assert "((simdiki.yon - onceki.yon) % 360 + 540) % 360 - 180" in HAREKET
    for eski, yeni, beklenen in ((350, 10, 20), (10, 350, -20), (60, 90, 30), (0, 180, -180)):
        assert ((yeni - eski) % 360 + 540) % 360 - 180 == beklenen


def test_sayilar_sayarak_degismiyor():
    """Ara degerlerle sayan bir animasyon gercekte olmayan okumalar
    gosterirdi: metin icerigi hic zamanlayiciyla yazilmiyor."""
    assert "textContent =" not in HAREKET
    assert "requestAnimationFrame" not in HAREKET and "setInterval" not in HAREKET


def test_yeni_NOTAM_vurgusu_yalnizca_ilk_cizimde():
    assert "yeniIdler = {};          // vurgu yalnizca ILK cizimde" in NOTAM
    assert "v.son_senkron ? yeniNotamlariBelirle" in NOTAM


def test_durum_rozeti_yalnizca_GECISTE_halka_alir():
    assert 'var degisti = sinif !== oncekiSinif && sinif !== "taze";' in BASLIK


def test_detay_acilisi_yukleme_sirasindaki_toggle_dalgasini_yok_sayar():
    assert "togglHazir" in HAREKET and 'addEventListener("load"' in HAREKET


# ================================================================= CSS
def test_surekli_dongu_yalnizca_eski_tazelik_nabzi():
    sonsuz = re.findall(r"animation:([^;]*infinite[^;]*);", CSS)
    assert len(sonsuz) == 1 and "ltfj-nabiz" in sonsuz[0]


def test_yeni_animasyonlar_tek_seferlik_ve_yerlesim_kaydirmiyor():
    blok = CSS.split("---- HAREKET ----")[1]
    adlar = ("ltfj-degisti", "ltfj-esik-dikkat", "ltfj-esik-uyari", "ltfj-rozet",
             "ltfj-belir", "ltfj-notam-yeni", "ltfj-onceki", "ltfj-duyuru-gir")
    for ad in adlar:
        assert f"@keyframes {ad}" in blok, ad
    # yalnizca opaklik / renk / golge / transform - yerlesim ozelligi yok
    kareler = re.findall(r"@keyframes[^{]+\{(?:[^{}]*\{[^}]*\})+", blok)
    assert len(kareler) == len(adlar)
    for yasak in ("width", "height", "margin", "padding", "top:", "left:", "font-size"):
        assert not any(yasak in k for k in kareler), yasak


def test_hareket_azaltma_genel_kurali_duruyor():
    assert "@media (prefers-reduced-motion: reduce)" in CSS
    assert "animation-duration:.01ms !important" in CSS


def test_yukseklik_animasyonu_yalnizca_destekleyen_tarayicida():
    assert "@supports (interpolate-size: allow-keywords)" in CSS
    blok = CSS.split("@supports (interpolate-size: allow-keywords)")[1][:400]
    assert "details::details-content" in blok
