"""Trend grafiklerindeki imlec/dokunma balonu testleri.

Balon TAMAMEN statik uretilir: nokta koordinatlari + okunabilir metinler
sayfa yazilirken data-noktalar niteligine gomulur, istemci tarafinda
hicbir fetch() yapilmaz."""
import html as html_mod
import re
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


def _grafik_basi(html: str, baslik: str) -> int:
    """Grafigin BASLIK MARKUP'ini bulur, metni ilk gectigi yeri degil.

    Duz html.index("Bulut tavani") kirilgandi: sayfaya ayni metni tasiyan
    bir title="..." eklenince (ust ozet seridi) bu testler grafigi degil
    o seridi buluyordu."""
    im = f'<div class="grafik-baslik"><span>{baslik}</span>'
    i = html.index(im)
    return i


def test_son_kayitta_deger_yoksa_raporlanmiyor_etiketi_cikar(tmp_path):
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([METAR], _en_son_yok_gecmisi(), hedef, {}, "")
    html = hedef.read_text(encoding="utf-8")
    i = _grafik_basi(html, "Bulut tavanı")
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
    i = _grafik_basi(html, "Bulut tavanı")
    svg = html[i:html.index("</svg>", i)]
    assert 'fill="none" stroke="currentColor" stroke-width="2"/>' in svg  # ici bos daire
    assert 'class="grafik-sinir"' in svg   # olcumun bittigi yer


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

    i = _grafik_basi(html, "Bulut tavanı")
    blok = html[i:html.index("grafik-durum-notu", i)]
    eksen_son = blok.rsplit('<span>', 1)[-1].split("</span>")[0]

    notu = html[html.index("Son ölçüm: 3000 ft", i):]
    son_olcum_saati = notu.split("· ")[1].split(" yerel")[0]

    assert eksen_son != son_olcum_saati


def test_olcumsuz_aralik_BOS_birakiliyor_cizgi_devam_ETMIYOR(tmp_path):
    """KARAR DEGISTI. Eskiden son gercek olcumden sag kenara kadar, son
    degerin HIZASINDA yatay kesikli bir cizgi ciziliyordu. Kullanici bunu
    "deger surüyor" diye okuyordu ("tavan 3000 ft'te sabit"), oysa o
    olcumden beri tavan hic raporlanmadi - yani cizgi OLMAYAN bir veriyi
    cizmis oluyordu.

    Artik o aralik BOS: sinir cizgisi + veri olmadigini gosteren soluk
    bir alan, sag kenara kadar."""
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([METAR], _en_son_yok_gecmisi(), hedef, {}, "")
    html = hedef.read_text(encoding="utf-8")
    i = _grafik_basi(html, "Bulut tavanı")
    svg = html[i:html.index("</svg>", i)]

    m = re.search(r'<rect class="grafik-bosluk" x="([\d.]+)" y="0" width="([\d.]+)"', svg)
    assert m, "bos aralik cizilmemis"
    x, gen = float(m.group(1)), float(m.group(2))
    assert x + gen > 590   # genislik=600, kenar payi 4px -> sag kenar ~596

    # Veri cizgisi bos alanin BASLADIGI yerde bitmeli, icine girmemeli.
    cizgi = re.search(r'<path d="(M[^"]+)" fill="none"', svg).group(1)
    son_x = float(cizgi.split("L")[-1].split(",")[0])
    assert abs(son_x - x) < 0.5, (son_x, x)


# ------------------------------------- "raporlanmiyor" mu, "tavan yok" mu?
# Kullanici raporu: tavan raporlanmadiginda grafik bunu "dusuk degerin
# devami" gibi gosteriyordu. Cizim tarafi yukarida duzeltildi; burasi
# KELIMEYI dogruluyor - "bilgi gelmiyor" ile "ortada tavan yok" ayni sey
# degil ve ikisini karistirmak operasyonel olarak yaniltici.
def _eslesen_gecmis(tavan_son=None):
    """Son kaydin ZAMANI METAR ile ayni - sayfa ancak o zaman rapordan
    cikardigi cumleyi grafige yazar."""
    return [
        {"zaman": (SIMDI - timedelta(hours=2)).isoformat(),
         "ruzgar_hiz": 5, "tavan": 3500, "qnh": 1016, "sicaklik": 20},
        {"zaman": (SIMDI - timedelta(hours=1)).isoformat(),
         "ruzgar_hiz": 5, "tavan": 3000, "qnh": 1016, "sicaklik": 20},
        {"zaman": SIMDI.isoformat(),
         "ruzgar_hiz": 9, "tavan": tavan_son, "qnh": 1020, "sicaklik": 22},
    ]


def _tavan_rozeti(tmp_path, metin, gecmis=None) -> str:
    hedef = tmp_path / "index.html"
    rapor = {"tip": "METAR", "icao": "LTFJ", "zaman": SIMDI, "metin": metin}
    s.sayfa_yaz([rapor], gecmis if gecmis is not None else _eslesen_gecmis(),
                hedef, {}, "")
    html = hedef.read_text(encoding="utf-8")
    i = _grafik_basi(html, "Bulut tavanı")
    return html[i:i + 900]


def test_katman_okundu_ve_hicbiri_5_8_degilse_TAVAN_YOK_deniyor(tmp_path):
    """SCT050 okunmus: tavan en alcak 5/8+ katmanin tabanidir, oyle bir
    katman yoksa tavan TANIM GEREGI yoktur. Bu bir cikarim degil."""
    blok = _tavan_rozeti(tmp_path, "LTFJ 171200Z 06009KT 9999 SCT050 21/14 Q1016")
    assert ">tavan yok<" in blok
    assert "raporlanmıyor" not in blok


def test_NSC_de_TAVAN_YOK(tmp_path):
    """NSC/NCD/SKC/CLR "bulut grubu gelmedi" degil, "bulut yok" der."""
    blok = _tavan_rozeti(tmp_path, "LTFJ 171200Z 06009KT 9999 NSC 21/14 Q1016")
    assert ">tavan yok<" in blok


def test_BKN_yuksekligi_bilinmiyorsa_TAVAN_YOK_DENMEZ(tmp_path):
    """BKN/// : tavan VARDIR, yalnizca yuksekligi bildirilmemistir.
    Burada "tavan yok" demek yanlis bir operasyonel ifade olurdu."""
    blok = _tavan_rozeti(tmp_path, "LTFJ 171200Z 06009KT 9999 BKN/// 21/14 Q1016")
    assert ">yükseklik bildirilmedi<" in blok
    assert "tavan yok" not in blok


def test_BOZUK_raporda_notr_kelimede_kaliniyor(tmp_path):
    """Kirpilmis/bozuk bir raporda da bulut listesi BOS kalir. Listenin
    bos olmasi tek basina "tavan yok" demek degil - olumlu bir isaret
    (okunmus bir katman ya da NSC/CAVOK) yoksa notr kelime kullanilir."""
    blok = _tavan_rozeti(tmp_path, "LTFJ 171200Z /////KT //// // Q////")
    assert "raporlanmıyor" in blok
    assert "tavan yok" not in blok


def test_gecmisin_son_kaydi_BASKA_bir_gozlemse_rapordan_cumle_TASINMAZ(tmp_path):
    """Grafikteki "raporlanmiyor", olcum gecmisinin son kaydina bakar;
    "tavan yok" ise GUNCEL RAPORDAN cikarilir. Bu ikisi ayni gozlem
    degilse, rapordan gelen cumle baska bir gozlemin uzerine yazilmis
    olurdu."""
    baska = _eslesen_gecmis()
    baska[-1]["zaman"] = (SIMDI + timedelta(minutes=30)).isoformat()
    blok = _tavan_rozeti(tmp_path, "LTFJ 171200Z 06009KT 9999 SCT050 21/14 Q1016",
                         gecmis=baska)
    assert "raporlanmıyor" in blok
    assert "tavan yok" not in blok


def test_tavan_yoklugu_kurali():
    assert s._tavan_yoklugu({"bulutlar": [{"ortu": "SCT", "ft": 5000}]}) == "yok"
    assert s._tavan_yoklugu({"bulutlar": [], "bulut_yok": True}) == "yok"
    assert s._tavan_yoklugu({"bulutlar": [], "cavok": True}) == "yok"
    assert s._tavan_yoklugu({"bulutlar": []}) is None          # olumlu isaret yok
    assert s._tavan_yoklugu({"bulutlar": [{"ortu": "BKN", "ft": None}]}) == "yukseklik_yok"
    assert s._tavan_yoklugu({"bulutlar": [{"ortu": "BKN", "ft": 800}]}) is None
    assert s._tavan_yoklugu(None) is None
