"""Trend grafiklerindeki imlec/dokunma balonu testleri.

Balon TAMAMEN statik uretilir: nokta koordinatlari + okunabilir metinler
sayfa yazilirken data-noktalar niteligine gomulur, istemci tarafinda
hicbir fetch() yapilmaz."""
import html as html_mod
import json
from datetime import datetime, timedelta, timezone

import ltfj_sayfa as s

SIMDI = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
METAR = {"tip": "METAR", "icao": "LTFJ", "zaman": SIMDI,
         "metin": "LTFJ 171200Z 06009KT 9999 SCT050 21/14 Q1016 NOSIG"}


def _gecmis(degerler):
    return [{"zaman": (SIMDI - timedelta(minutes=(len(degerler) - 1 - i) * 60)).isoformat(),
             "ruzgar_hiz": v, "tavan": 3000, "qnh": 1016, "sicaklik": 20}
            for i, v in enumerate(degerler)]


def _sayfa(tmp_path, degerler=(5, 9, 12, 7)):
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([METAR], _gecmis(degerler), hedef, {}, "")
    return hedef.read_text(encoding="utf-8")


def test_svg_cizgi_tek_noktada_none_doner():
    assert s._svg_cizgi([(SIMDI, 5)], "#fff") is None


def test_svg_cizgi_svg_ve_oranlari_birlikte_doner():
    noktalar = [(SIMDI - timedelta(hours=2), 5), (SIMDI - timedelta(hours=1), 9), (SIMDI, 7)]
    sonuc = s._svg_cizgi(noktalar, "#3b82f6")
    assert sonuc is not None
    svg, oranlar = sonuc
    assert svg.startswith("<svg")
    assert len(oranlar) == len(noktalar)
    for x, y in oranlar:
        assert 0.0 <= x <= 1.0
        assert 0.0 <= y <= 1.0


def test_oranlar_zamanla_artan_sirada():
    noktalar = [(SIMDI - timedelta(hours=3), 5), (SIMDI - timedelta(hours=1), 9), (SIMDI, 7)]
    _, oranlar = s._svg_cizgi(noktalar, "#fff")
    xler = [x for x, _ in oranlar]
    assert xler == sorted(xler)


def test_grafik_kutusunda_balon_ogeleri_var(tmp_path):
    html = _sayfa(tmp_path)
    assert 'class="grafik-kutu"' in html
    assert 'class="grafik-sarmal"' in html
    assert 'class="grafik-imlec" hidden' in html
    assert 'class="grafik-nokta" hidden' in html
    assert 'class="grafik-balon" hidden' in html


def test_nokta_verisi_saat_ve_degeri_tasiyor(tmp_path):
    """data-noktalar her nokta icin oran (x/y) + saat (s) + birimli deger (d)
    tasimali; sayi kadar nokta olmali."""
    html = _sayfa(tmp_path, degerler=(5, 9, 12, 7))
    basla = html.index('data-noktalar="') + len('data-noktalar="')
    ham = html[basla:html.index('"', basla)]
    noktalar = json.loads(html_mod.unescape(ham))
    assert len(noktalar) == 4
    for n in noktalar:
        assert set(n) == {"x", "y", "s", "d"}
        assert 0.0 <= n["x"] <= 1.0 and 0.0 <= n["y"] <= 1.0
        assert len(n["s"]) == 5 and n["s"][2] == ":"     # HH:MM
    assert [n["d"] for n in noktalar] == ["5 kt", "9 kt", "12 kt", "7 kt"]


def test_balon_scripti_var_ve_fetch_yapmiyor(tmp_path):
    """Balon tamamen statik veriden calisir - script'inde hicbir fetch()
    olmamali (yorum satirlari haric tutulur)."""
    html = _sayfa(tmp_path)
    assert 'querySelectorAll(".grafik-kutu")' in html
    idx = html.index('querySelectorAll(".grafik-kutu")')
    blok = html[idx:html.index("</script>", idx)]
    yurutulen = "\n".join(satir for satir in blok.splitlines()
                          if not satir.strip().startswith("//"))
    assert "fetch(" not in yurutulen


def test_dokunmatik_icin_pointer_olaylari_bagli(tmp_path):
    """Fare ve dokunmatik ayni kod yolundan yonetilir (Pointer Events);
    dikey sayfa kaydirma bozulmasin diye touch-action:pan-y olmali."""
    html = _sayfa(tmp_path)
    for olay in ("pointerenter", "pointermove", "pointerdown",
                 "pointerleave", "pointerup", "pointercancel"):
        assert f'addEventListener("{olay}"' in html
    assert "touch-action:pan-y" in html


def test_gecmis_yoksa_grafik_bolumu_hic_cikmaz(tmp_path):
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([METAR], [], hedef, {}, "")
    html = hedef.read_text(encoding="utf-8")
    assert 'class="grafik-kutu"' not in html
