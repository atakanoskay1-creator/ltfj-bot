"""Uygulama kabuğu: başlık, veri tazeliği, SVG ikon sistemi.

EN KRİTİK ÜÇÜ:
  1) "CANLI" YALAN SÖYLEYEMEZ. Durum sunucuda değil İSTEMCİDE hesaplanır -
     sayfa bir vardiya boyunca açık kalabiliyor ve sunucuda yazılan bir
     etiket bir saat sonra yanlış olurdu.
  2) EŞİK TEK KAYNAKTAN. Kesinti eşiği botun Telegram alarmıyla AYNI
     sabitten gelir; sayfa "canlı" derken Telegram "kesinti" diyemez.
  3) ARAYÜZDE EMOJİ YOK - ama RENK_SIMGE Telegram'da KALIR.
"""
import re
from datetime import datetime, timedelta, timezone

import ltfj_ayarlar
import ltfj_sayfa as s


def _sayfa(tmp_path, gozlem_yasi_dk=5) -> str:
    hedef = tmp_path / "index.html"
    simdi = datetime.now(timezone.utc) - timedelta(minutes=gozlem_yasi_dk)
    raporlar = [
        {"tip": "METAR", "zaman": simdi, "icao": "LTFJ",
         "metin": "LTFJ 231420Z 06005KT 9999 FEW023 15/13 Q1019 NOSIG"},
        {"tip": "TAF", "zaman": simdi - timedelta(minutes=40), "icao": "LTFJ",
         "metin": "TAF LTFJ 231400Z 2315/2415 06005KT 9999 FEW025"},
    ]
    gecmis = [{"zaman": (simdi - timedelta(minutes=30 * i)).isoformat(),
               "tavan": 2300, "ruzgar_hiz": 4, "qnh": 1019,
               "sicaklik": 15.0, "cig_noktasi": 13.0} for i in range(8, -1, -1)]
    s.sayfa_yaz(raporlar, gecmis, hedef)
    return hedef.read_text(encoding="utf-8")


# ------------------------------------------- 1) "CANLI" yalan söyleyemez
def test_durum_SUNUCUDA_yazilmiyor(tmp_path):
    """Sunucu "CANLI" yazsaydı sayfa bir saat açık kalınca yalan olurdu.
    HTML boş bir kap taşır; metni JS doldurur."""
    html = _sayfa(tmp_path)
    m = re.search(r'<span class="ust-durum" id="ust-durum"[^>]*>(.*?)</span>',
                  html, re.S)
    assert m is not None, "durum kabı yok"
    assert m.group(1).strip() == "", f"sunucu metin yazmış: {m.group(1)!r}"


def test_gozlem_zamani_ISO_olarak_gomuluyor(tmp_path):
    """JS yaşı bu damgadan hesaplıyor; biçim ayrıştırılabilir olmalı."""
    html = _sayfa(tmp_path)
    m = re.search(r'id="ust-durum" data-gozlem="([^"]*)"', html)
    assert m and datetime.fromisoformat(m.group(1))


def test_gozlem_YOKSA_uydurma_zaman_yazilmiyor(tmp_path):
    """Zaman bilinmiyorsa boş dize gider ve JS "VERİ YOK" gösterir -
    uydurma bir damga yazmaktansa bilinmediğini söylemek doğru."""
    hedef = tmp_path / "i.html"
    s.sayfa_yaz([{"tip": "METAR", "zaman": None, "icao": "LTFJ",
                  "metin": "LTFJ 231420Z 06005KT 9999 15/13 Q1019"}], [], hedef)
    html = hedef.read_text(encoding="utf-8")
    assert 'data-gozlem=""' in html


def test_uc_durum_esigi_de_JS_te_var(tmp_path):
    html = _sayfa(tmp_path)
    for metin in ("CANLI", "GECİKMELİ", "VERİ KESİNTİSİ", "VERİ YOK"):
        assert f'"{metin}"' in html, metin


# ------------------------------------------- 2) eşik tek kaynaktan
def test_kesinti_esigi_BOTUN_esigiyle_AYNI(tmp_path):
    """ltfj_ayarlar.SESSIZLIK_SAAT'i bot Telegram alarmı için kullanıyor.
    Sayfa başka bir sayı kullansaydı, sayfa "canlı" derken Telegram
    "kesinti" diyebilirdi."""
    html = _sayfa(tmp_path)
    m = re.search(r"var KESINTI_DK = (\d+) \* 60;", html)
    assert m, "kesinti eşiği JS'te yok"
    assert int(m.group(1)) == ltfj_ayarlar.SESSIZLIK_SAAT


def test_tazelik_esigi_ayarlardan_geliyor(tmp_path):
    html = _sayfa(tmp_path)
    m = re.search(r"var TAZE_DK = (\d+);", html)
    assert m and int(m.group(1)) == ltfj_ayarlar.GOZLEM_TAZE_DK


def test_tazelik_esigi_METAR_kadansindan_BUYUK(tmp_path):
    """METAR 30 dk kadansında + ~5 dk MGM gecikmesi. Eşik bunun altında
    olsaydı normal çalışan bir sistem sürekli "gecikmeli" görünürdü."""
    assert ltfj_ayarlar.GOZLEM_TAZE_DK > 35
    assert ltfj_ayarlar.GOZLEM_TAZE_DK < ltfj_ayarlar.SESSIZLIK_SAAT * 60


# ------------------------------------------- 3) emoji yok, SVG var
EMOJI_ARALIGI = re.compile(
    # U+2300-23FF DE DAHIL: ilk surum bu blogu atlamis ve canli
    # sayfadaki "\u23f3" (kum saati) gozden kacmisti. Tipografik
    # oklar (U+2192) ve eksi (U+2212) EMOJI DEGIL, disarida.
    r"[\U0001F000-\U0001FAFF\u2300-\u23FF\u2600-\u26FF"
    r"\u2700-\u27BF\u2B00-\u2BFF\uFE0F]")


def _emoji_bul(html: str) -> set:
    govde = html.split("</style>")[1]
    govde = re.sub(r"<!--.*?-->", "", govde, flags=re.S)
    return set(EMOJI_ARALIGI.findall(govde))


def test_sayfada_EMOJI_yok(tmp_path):
    """Emoji platforma göre bambaşka çizilir, boyu yazı tipiyle uyuşmaz
    ve ekran okuyucu onları yüksek sesle okur."""
    assert not _emoji_bul(_sayfa(tmp_path))


def test_SIS_TAHMINI_yolunda_da_emoji_yok(tmp_path):
    """KAPSAMA BOŞLUĞU KAPATILDI: ilk sürüm yalnızca varsayılan fikstürün
    ürettiğini tarıyordu. Tahmin şeridindeki sis işareti (WMO 45/48) o
    yolda çiziliyor ve canlı sayfada emoji olarak kalmıştı - testler
    yeşilken. Artık o dal da taranıyor."""
    from datetime import datetime as dt
    hedef = tmp_path / "i.html"
    ilk = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(
        minute=0, second=0, microsecond=0)
    tahmin = [{"saat": ilk.strftime("%Y-%m-%dT%H:%M"), "temperature_2m": 8,
               "dew_point_2m": 8, "visibility": 300, "wind_speed_10m": 2,
               "cloud_cover_low": 95, "weather_code": 45,
               "boundary_layer_height": 120}]
    s.sayfa_yaz([{"tip": "METAR", "zaman": datetime.now(timezone.utc),
                  "icao": "LTFJ",
                  "metin": "LTFJ 231420Z 00000KT 0300 FG VV001 08/08 Q1019"}],
                [], hedef, saatlik_tahmin=tahmin, tahmin_yas_dk=10)
    html = hedef.read_text(encoding="utf-8")
    # ETIKETI arıyoruz, sınıf adını değil: ".tahmin-sis" ayrıca CSS
    # kuralında geçiyor ve bu guard'ın ilk sürümü ona takılıyordu -
    # yani işaret hiç çizilmese bile test boşa yeşil dönerdi.
    assert '<div class="tahmin-sis"' in html, "sis işareti çizilmemiş"
    assert not _emoji_bul(html)


def test_RENK_SIMGE_TELEGRAM_tarafinda_KALIYOR():
    """Telegram'da SVG yok - orada emoji DOĞRU ortam. Bu yüzden
    ltfj_pist.RENK_SIMGE silinmedi, yalnızca web kullanımı kaldırıldı."""
    from ltfj_pist import RENK_SIMGE
    assert set(RENK_SIMGE) == {"BLU", "WHT", "GRN", "YLO", "AMB", "RED"}
    # KULLANIMA bakiyoruz, metne degil: aciklama satirlari bu adi anmakta
    # serbest ve testin ilk surumu tam da kendi yorumuma takilmisti.
    import ast
    kok = ast.parse(open("ltfj_sayfa.py", encoding="utf-8").read())
    adlar = {d.id for d in ast.walk(kok) if isinstance(d, ast.Name)}
    adlar |= {a.name for d in ast.walk(kok) if isinstance(d, ast.ImportFrom)
              for a in d.names}
    assert "RENK_SIMGE" not in adlar, "web sayfasi hâlâ RENK_SIMGE kullaniyor"
    bot = ast.parse(open("ltfj_bot.py", encoding="utf-8").read())
    bot_adlar = {d.id for d in ast.walk(bot) if isinstance(d, ast.Name)}
    assert "RENK_SIMGE" in bot_adlar, "Telegram tarafindan da dusmus"


def test_ikonlar_currentColor_kullaniyor(tmp_path):
    """Sabit renk verilseydi ikon koyu temada ya da uyarı renginde
    yanlış çizilirdi."""
    css = _sayfa(tmp_path).split(".ikon {")[1].split("}")[0]
    assert "stroke:currentColor" in css


def test_ikonlar_ekran_okuyucudan_GIZLI(tmp_path):
    """İkon dekoratif; yanındaki metin zaten anlamı taşıyor."""
    html = _sayfa(tmp_path)
    for svg in re.findall(r"<svg class=\"ikon[^\"]*\"[^>]*>", html):
        assert 'aria-hidden="true"' in svg, svg


def test_ikon_SATIR_ICI_dis_dosya_DEGIL(tmp_path):
    """Sayfa tek dosya ve dış bağımlılık taşımıyor - ikon fontu ya da
    sprite havalimanı ağında engellenebilirdi."""
    html = _sayfa(tmp_path)
    assert "<svg" in html
    assert "<use " not in html
    assert not re.search(r'<link[^>]*icon[^>]*stylesheet', html)


# ------------------------------------------- ikon/metin ayrimi
def test_bildirim_dugmesinde_ikon_ve_metin_AYRI(tmp_path):
    """JS metni değiştiriyor. Tek düğüm olsaydı textContent SVG'yi de
    silerdi - ikon ilk tıklamada kaybolurdu."""
    html = _sayfa(tmp_path)
    assert 'id="bildirim-ikon"' in html and 'id="bildirim-metin"' in html
    assert "btn.textContent" not in html


def test_ray_ikonu_TELEFONDA_gizli(tmp_path):
    """Ölçüldü: çubuk 360px'te tam kapasitede (326/326px). İkon eklemek
    NOTAM sekmesini keserdi."""
    html = _sayfa(tmp_path)
    once = html.split("@media (min-width:1024px)")[0]
    assert ".sekme-ikon { display:none; }" in once
    genis = html.split("@media (min-width:1024px)")[1].split("\n  }")[0]
    assert ".sekme-ikon" in genis and "display:block" in genis


# ------------------------------------------- goreli sure sirasi
def test_goreli_sure_yardimcisi_TUKETICIDEN_once_tanimli(tmp_path):
    """Tanım tüketiciden sonra gelirse başlık sessizce yedek biçime
    ("120 dk önce") düşer - "2 sa önce" yerine. Bu gerçekten oldu."""
    html = _sayfa(tmp_path)
    assert html.index("window.ltfjGecenSure = function") < html.index("var TAZE_DK")
