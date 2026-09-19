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
    """Zaman damgalari GERCEK 'simdi'ye gore uretilir: _grafik_verisi() son
    GRAFIK_PENCERE_SAAT'lik pencereyi datetime.now()'a gore suzdugu icin sabit
    tarihli fixture saat ilerledikce pencereden duser (testi zamana bagimli
    kilardi)."""
    simdi = datetime.now(timezone.utc)
    return [{"zaman": (simdi - timedelta(minutes=(len(degerler) - 1 - i) * 30)).isoformat(),
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


# --------------------------------------------------- "raporlanmiyor" durumu
# Bug raporu: gokyuzu acildiginda (BKN/OVC katmani yok) tavan grafigi son
# GERCEK olcumde (ornegin saatler once) donmus gorunuyordu ve kullanici bunu
# "guncel deger" saniyordu. Grafik artik bu durumu hem basliktaki etiketle
# hem de son segmenti kesikli/ici bos cizerek ayirt ediyor.
def _en_son_yok_gecmisi():
    """Son kayitta tavan None, ondan onceki iki kayitta gercek deger var -
    _svg_cizgi'nin cizgi cizebilmesi icin en az 2 non-null nokta gerekir."""
    simdi = datetime.now(timezone.utc)
    return [
        {"zaman": (simdi - timedelta(hours=3)).isoformat(),
         "ruzgar_hiz": 5, "tavan": 3500, "qnh": 1016, "sicaklik": 20},
        {"zaman": (simdi - timedelta(hours=2)).isoformat(),
         "ruzgar_hiz": 5, "tavan": 3000, "qnh": 1016, "sicaklik": 20},
        {"zaman": simdi.isoformat(),
         "ruzgar_hiz": 9, "tavan": None, "qnh": 1020, "sicaklik": 22},
    ]


def test_son_kayitta_deger_yoksa_raporlanmiyor_etiketi_cikar(tmp_path):
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([METAR], _en_son_yok_gecmisi(), hedef, {}, "")
    html = hedef.read_text(encoding="utf-8")
    i = html.index("Bulut tavanı")
    blok = html[i:i + 700]
    assert 'class="grafik-son grafik-son-yok">raporlanmıyor<' in blok
    assert "3000 ft" not in blok.split("grafik-durum-notu")[0]  # baslikta DEGIL


def test_son_kayitta_deger_yoksa_durum_notu_son_bilinen_degeri_gosterir(tmp_path):
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([METAR], _en_son_yok_gecmisi(), hedef, {}, "")
    html = hedef.read_text(encoding="utf-8")
    assert "Son ölçüm: 3000 ft" in html
    assert "raporlanmıyor" in html.split("Son ölçüm: 3000 ft")[1][:60]


def test_son_kayitta_deger_yoksa_son_nokta_ici_bos_cizilir(tmp_path):
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([METAR], _en_son_yok_gecmisi(), hedef, {}, "")
    html = hedef.read_text(encoding="utf-8")
    i = html.index("Bulut tavanı")
    svg = html[i:html.index("</svg>", i)]
    assert 'fill="none" stroke="#22c55e" stroke-width="2"/>' in svg  # ici bos daire
    assert "stroke-dasharray" in svg


def test_son_kayitta_deger_varsa_raporlanmiyor_etiketi_cikmaz(tmp_path):
    """Regresyon: normal (guncel) durumda eski davranis aynen korunmali.
    (CSS kurali her zaman <style> icinde tanimli olabilir - burada sinifin
    bir elemente UYGULANIP uygulanmadigina bakiyoruz.)"""
    html = _sayfa(tmp_path)
    assert 'class="grafik-son grafik-son-yok"' not in html
    assert "raporlanmıyor" not in html
    assert 'class="grafik-durum-notu"' not in html


def test_son_kayitta_deger_yoksa_eksen_ucu_eski_olcumde_takili_kalmiyor(tmp_path):
    """Bug raporu: eksenin SAG UCU (bitis etiketi) eski son-gercek-olcum
    saatinde ('04:50' gibi) donup kalıyordu. Artik en son METAR/SPECI'nin
    (guncel kayit) zamanina kadar uzatilmali - bu ikisi arasinda 2 saat
    fark var, bu yuzden gosterilen saatler AYNI OLMAMALI."""
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([METAR], _en_son_yok_gecmisi(), hedef, {}, "")
    html = hedef.read_text(encoding="utf-8")

    i = html.index("Bulut tavanı")
    blok = html[i:html.index("grafik-durum-notu", i)]
    eksen_son = blok.rsplit('<span>', 1)[-1].split("</span>")[0]

    notu = html[html.index("Son ölçüm: 3000 ft", i):]
    son_olcum_saati = notu.split("· ")[1].split(" yerel")[0]

    assert eksen_son != son_olcum_saati


def test_son_kayitta_deger_yoksa_kesikli_cizgi_sag_kenara_kadar_uzaniyor(tmp_path):
    """Kesikli 'raporlanmiyor' cizgisi son gercek noktadan grafigin SAG
    KENARINA (guncel zamana) kadar uzanmali, ortada bir yerde kesilmemeli."""
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([METAR], _en_son_yok_gecmisi(), hedef, {}, "")
    html = hedef.read_text(encoding="utf-8")
    i = html.index("Bulut tavanı")
    svg = html[i:html.index("</svg>", i)]

    j = svg.index("stroke-dasharray")
    kesikli_path = svg[svg.rindex("<path", 0, j):svg.index("/>", j)]
    kenar_x = float(kesikli_path.split("L")[-1].split(",")[0])
    assert kenar_x > 590   # genislik=600, kenar payi 4px -> sag kenar ~596
