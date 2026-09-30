"""Canli guncelleme: sayfa yeniden yuklenmeden yeni veri (12_canli.js).

Kullanici istedi: "sayfaya bir guncelleme geldiginde sayfayi guncellemesem
bile bilgi guncellenebilir mi". Tarayicidaki davranis Playwright ile
olculdu (eski sayfa acikken sunucudaki dosya degistirildi: yukleme sayisi
1 kaldi, degerler, VFR, ozet serit ve ruzgar oku yenilendi; yazilan LVO
girdisi, acik <details>, kaydirma konumu korundu). Bu testler sozlesmeyi
kaynak metni uzerinden kilitler.
"""
import re
from pathlib import Path

import ltfj_sayfa as s

KAYNAK = Path("sayfa_kaynak")
CANLI = (KAYNAK / "12_canli.js").read_text(encoding="utf-8")


def _sayfa(tmp_path):
    from datetime import datetime, timezone
    hedef = tmp_path / "i.html"
    s.sayfa_yaz([{"tip": "METAR", "icao": "LTFJ", "zaman": datetime.now(timezone.utc),
                  "metin": "LTFJ 241720Z 06015KT 9999 FEW030 12/08 Q1008"}], [], hedef)
    return hedef.read_text(encoding="utf-8")


def _bolgeler():
    blok = CANLI.split("var BOLGELER = [")[1].split("];")[0]
    return re.findall(r'"([^"]+)"', blok)


def test_betik_sayfada_ve_hareketten_sonra(tmp_path):
    html = _sayfa(tmp_path)
    assert "window.ltfjCanliUygula = function" in html
    assert html.index("window.ltfjHareketKarsilastir = karsilastir") < \
        html.index("window.ltfjCanliUygula = function")


def test_her_bolge_uretilen_sayfada_VAR(tmp_path):
    """Bir bolge secicisi sayfada hic yoksa o bolge sessizce hic
    guncellenmez - sablonla secici birbirinden kopmasin."""
    html = _sayfa(tmp_path)
    for secici in _bolgeler():
        if secici.startswith("#"):
            assert f'id="{secici[1:]}"' in html, secici
        else:
            sinif = secici.split(".")[-1]
            assert re.search(rf'class="([^"]* )?{sinif}( [^"]*)?"', html), secici


def test_kabuk_ve_kullanici_girdileri_bolge_DEGIL():
    """Sekme cubugu, LVO formu, NOTAM filtreleri ve ATC Notes istemcinin
    kendi durumunu tasir - yerinde degisim onlara dokunmamali."""
    for yasak in ("#panel-lvo", "#panel-notam", ".sekme-cubugu", "#atc-panel-ortu",
                  "body", ".sar", "#vfr-panel-ortu"):
        assert yasak not in _bolgeler(), yasak


def test_yapi_uyusmazsa_yerinde_guncelleme_YOK():
    assert "if (!a !== !b) { return \"yukle\"; }" in CANLI


def test_ayni_uretim_ise_hicbir_sey_degismez():
    assert 'kaynakA.innerHTML === kaynakB.innerHTML) { return "ayni"; }' in CANLI


def test_kullanici_yazarken_ya_da_pencere_acikken_bekler():
    assert "/^(INPUT|TEXTAREA|SELECT)$/.test(odak.tagName)" in CANLI
    assert '.modal-ortu' in CANLI
    assert 'return "bekle"' in CANLI
    # bekleme, degisiklikten ONCE karar veriliyor
    assert CANLI.index('return "bekle"') < CANLI.index("eski.innerHTML = yeni.innerHTML")


def test_acik_bolumler_korunuyor():
    assert "var detay = detayDurumu(eski);" in CANLI
    assert "detayGeriYukle(eski, detay);" in CANLI
    # geri yuklemenin tetikledigi toggle, "acildi" animasyonu oynatmasin
    assert "window.ltfjToggleSustur()" in CANLI


def test_bolgeye_bagli_isler_yeniden_calisiyor():
    for f in ("ltfjBaslikTazele", "ltfjGrafikIpucuKur", "ltfjNotamYenile",
              "ltfjLvoNotamYenile"):
        assert f"window.{f}" in CANLI, f
    assert "window.ltfjHareketKarsilastir(true)" in CANLI


def test_grafik_ipucu_ikinci_kez_baglanmiyor():
    js = (KAYNAK / "10_grafik_ipucu.js").read_text(encoding="utf-8")
    assert 'if (kutu.getAttribute("data-ipucu-bagli")) return;' in js
    assert "window.ltfjGrafikIpucuKur = kur;" in js


def test_yeniden_yazilan_dugmeler_olay_yetkilendirmesiyle_calisiyor():
    """VFR paneli ve sis modeli dugmesi bolgelerin icinde: dogrudan bagli
    dinleyiciler degisimde kaybolurdu."""
    for dosya, dugme in (("08_vfr.js", "#vfr-panel-kapat"),
                         ("09_sis_baglanti.js", "#sis-model-diyagram-btn")):
        js = (KAYNAK / dosya).read_text(encoding="utf-8")
        assert 'document.addEventListener("click"' in js, dosya
        assert f'e.target.closest("{dugme}")' in js, dosya


def test_canli_betik_zamanlayici_ve_ag_istegi_yapmiyor():
    """Ag istegini baslik betigi yapiyor (tek yerde, HEAD ile); bu betik
    yalnizca verilen metni uygular."""
    yurutulen = "\n".join(l for l in CANLI.splitlines() if not l.strip().startswith("//"))
    for yasak in ("fetch(", "setInterval", "XMLHttpRequest", "location.reload"):
        assert yasak not in yurutulen, yasak
