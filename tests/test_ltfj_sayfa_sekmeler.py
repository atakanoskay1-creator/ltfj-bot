"""Yatay sekme çubuğu: Durum / Beklenti / İstatistik / LVO / NOTAM.

KARAR (kullanıcı): bölümler alt alta katlanır başlıklardı, sayfa çok
uzuyordu. Kullanıcı SOL kenarda dikey sekme istedi; ölçüldü ve yatay
seçildi — içerik sütunu telefonda ~360px ve dikey bir ray yatay genişliği
KALICI olarak yer (~%25). Yatay çubuk dikey yerden bir kez ödün verir.

EN KRİTİK ÜÇ ŞEY:
  1) ÖLÜ SEKME OLMAMALI - bir düğmenin işaret ettiği panel yoksa sekmeye
     basınca sayfa boşalır ve bunu kimse fark etmez.
  2) JS YOKSA SAYFA BOZULMAMALI - havalimanı ağında betik engellenebilir;
     o zaman sayfa eski "hepsi alt alta" hâline düşmeli, BOŞ değil.
  3) ROZET SEKMEDE KALMALI - panel gizliyken yeni NOTAM'ı veya yüksek sis
     olasılığını fark etmenin tek yolu çubuk.
"""
import re
from datetime import datetime, timedelta, timezone

import ltfj_sayfa as s

SIMDI = datetime.now(timezone.utc)
METAR = "LTFJ 172120Z 01003KT 1500 BR SCT008 06/06 Q1020"
ANAHTARLAR = ("durum", "beklenti", "istatistik", "lvo", "notam")


def _sayfa(tmp_path, tahmin=None) -> str:
    hedef = tmp_path / "index.html"
    rapor = {"tip": "METAR", "metin": METAR, "zaman": SIMDI, "icao": "LTFJ"}
    gecmis = [{"zaman": (SIMDI - timedelta(hours=h)).isoformat(),
               "ruzgar_hiz": 3, "tavan": 600, "qnh": 1020,
               "sicaklik": 6, "cig_noktasi": 6 - h * 0.3} for h in range(7, -1, -1)]
    s.sayfa_yaz([rapor], gecmis, hedef, saatlik_tahmin=tahmin or [])
    return hedef.read_text(encoding="utf-8")


# ----------------------------------------------- 1) ölü sekme olmamalı
def test_her_sekmenin_paneli_VAR(tmp_path):
    """Düğme olmayan bir panele işaret ederse sekmeye basınca sayfa
    boşalır - ve bu sessizce olur."""
    html = _sayfa(tmp_path)
    for hedef in re.findall(r'<button[^>]*aria-controls="([^"]+)"', html):
        assert f'id="{hedef}"' in html, f"{hedef} paneli yok - ölü sekme"


def test_her_panelin_sekmesi_VAR(tmp_path):
    """Sekmesi olmayan bir panel JS'li tarayıcıda ASLA görünmez."""
    html = _sayfa(tmp_path)
    for pid in re.findall(r'id="(panel-[a-z]+)"', html):
        assert f'aria-controls="{pid}"' in html, f"{pid} paneline sekme yok"


def test_bes_sekme_ve_bes_panel(tmp_path):
    html = _sayfa(tmp_path)
    for a in ANAHTARLAR:
        assert f'id="sekme-{a}"' in html, a
        assert f'id="panel-{a}"' in html, a
    assert len(re.findall(r'class="sekme"', html)) == len(ANAHTARLAR)


def test_her_sekme_icin_GORUNURLUK_kurali_var(tmp_path):
    """Görünürlüğü CSS yapıyor. Kuralı eksik bir sekme, seçilince hiçbir
    panel açmaz - düğme çalışır ama ekran boş kalır."""
    html = _sayfa(tmp_path)
    for a in ANAHTARLAR:
        assert f'.js[data-sekme="{a}"]' in html, a


def test_acilista_durum_sekmesi_secili(tmp_path):
    html = _sayfa(tmp_path)
    dugme = re.search(r'<button[^>]*id="sekme-durum"[^>]*>', html).group(0)
    assert 'aria-selected="true"' in dugme
    for a in ("beklenti", "istatistik", "lvo", "notam"):
        d = re.search(rf'<button[^>]*id="sekme-{a}"[^>]*>', html).group(0)
        assert 'aria-selected="false"' in d, a


# ------------------------------------- 2) JS yoksa sayfa bozulmamalı
def test_paneller_HTML_de_gizli_DEGIL(tmp_path):
    """Gizleme YALNIZCA .js sınıfıyla devreye girer. HTML'de `hidden`
    yazsaydı betiksiz tarayıcıda sayfa tamamen boş açılırdı."""
    html = _sayfa(tmp_path)
    for panel in re.findall(r'<div class="sekme-panel"[^>]*>', html):
        assert "hidden" not in panel, panel


def test_cubuk_JS_YOKKEN_cizilmiyor(tmp_path):
    """JS yoksa tüm paneller zaten alt alta görünür; çubuk da görünseydi
    hiçbir şey yapmayan beş düğme olurdu."""
    html = _sayfa(tmp_path)
    kural = html.split(".sekme-cubugu {")[1].split("}")[0]
    assert "display:none" in kural
    assert ".js .sekme-cubugu {" in html


def test_gizleme_kurali_JS_sinifina_BAGLI(tmp_path):
    html = _sayfa(tmp_path)
    assert ".js .sekme-panel {" in html
    # Kosulsuz bir gizleme kurali olmamali
    assert re.search(r"(?<!\.js )\.sekme-panel \{\{?\s*display:none", html) is None


def test_js_sinifi_BODY_den_once_ekleniyor(tmp_path):
    """Sonradan eklenirse açılışta tüm paneller bir kare görünüp kaybolur
    (flash). Betik <head> içinde ve <body>'den ÖNCE olmalı."""
    html = _sayfa(tmp_path)
    yer = html.index('className += " js"')
    # Capa olarak </head> secildi: sayfada TEK kez gecer. "<body>" gecmez,
    # cunku o dize aciklama metinlerinin icinde de gorunebiliyor - bu tam
    # olarak testin ilk surumunu yanlis yere baglayan seydi.
    assert html.count("</head>") == 1
    assert yer < html.index("</head>")


def test_localStorage_okumasi_TRY_ile_sarili(tmp_path):
    """Gizli sekmede localStorage erişimi istisna atabilir; atarsa açılış
    betiği ölür ve .js sınıfı eklenmediği için sayfa JS'siz moda düşer."""
    html = _sayfa(tmp_path)
    blok = html.split('className += " js"')[1].split("</script>")[0]
    assert "try {" in blok and "catch" in blok


def test_gecersiz_kayitli_sekme_REDDEDILIYOR(tmp_path):
    """localStorage elle kurcalanabilir; bilinmeyen bir değer hiçbir CSS
    kuralıyla eşleşmez ve sayfa tamamen boş açılırdı."""
    html = _sayfa(tmp_path)
    blok = html.split('className += " js"')[1].split("</script>")[0]
    assert "indexOf(v)" in blok
    for a in ANAHTARLAR:
        assert f'"{a}"' in blok, a


# ------------------------------------------------- 3) rozetler sekmede
def test_notam_rozeti_SEKMEDE_ve_id_korunmus(tmp_path):
    """Aktif NOTAM sayısı istemcide Firebase'den geliyor ve mevcut JS onu
    id ile buluyor. Rozet sekmeye taşındı ama id AYNI kalmalı, yoksa sayı
    hiç yazılmaz ve kimse fark etmez."""
    html = _sayfa(tmp_path)
    dugme = re.search(r'<button[^>]*id="sekme-notam".*?</button>', html, re.S).group(0)
    assert 'id="notam-aktif-sayi"' in dugme
    assert html.count('id="notam-aktif-sayi"') == 1     # tek kopya


def test_bos_rozet_gizleniyor(tmp_path):
    """NOTAM sayısı gelene kadar rozet boş; boş bir baloncuk çirkin ve
    yanıltıcı olurdu."""
    assert ".sekme-rozet:empty {" in _sayfa(tmp_path)


# --------------------------------------------------- erişilebilirlik
def test_tablist_rolleri_dogru(tmp_path):
    html = _sayfa(tmp_path)
    assert 'role="tablist"' in html
    assert len(re.findall(r'role="tab"', html)) == len(ANAHTARLAR)
    assert len(re.findall(r'role="tabpanel"', html)) == len(ANAHTARLAR)
    for a in ANAHTARLAR:
        panel = re.search(rf'<div class="sekme-panel" id="panel-{a}"[^>]*>',
                          html, re.S).group(0)
        assert f'aria-labelledby="sekme-{a}"' in panel, a


def test_ok_tuslariyla_gezinme_var(tmp_path):
    html = _sayfa(tmp_path)
    assert "ArrowRight" in html and "ArrowLeft" in html


def test_dokunma_hedefi_en_az_40px(tmp_path):
    """Eldivenli/hareket hâlindeki kullanım - depo zaten bu kuralı
    gözetiyor (bkz. dokunma hedefi çalışması)."""
    kural = _sayfa(tmp_path).split(".sekme {")[1].split("}")[0]
    yuk = int(re.search(r"min-height:(\d+)px", kural).group(1))
    assert yuk >= 40


# ------------------------------------ eski mekanizmalar temizlendi mi
def test_bolumler_sekme_ICINDE_ayrica_katlanmiyor(tmp_path):
    """Sekmeye basıp bir de başlığı açmak iki tıklama olurdu."""
    html = _sayfa(tmp_path, tahmin=[])
    for a in ("beklenti", "istatistik"):
        panel = html.split(f'id="panel-{a}"')[1].split('class="sekme-panel"')[0]
        assert "<details" not in panel, a


def test_seritte_ve_cubukta_TEK_yapiskan_katman(tmp_path):
    html = _sayfa(tmp_path)
    assert html.index('class="yapiskan-ust"') < html.index('class="sekme-cubugu"')
