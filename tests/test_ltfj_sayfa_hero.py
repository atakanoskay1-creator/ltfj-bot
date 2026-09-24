"""Mevcut Koşullar kartı: dört ölçüm + eğilim çizgileri.

NEDEN: bu dört değer önce düz gri bir CÜMLEYE gömülüydü —
  "Rüzgâr 060° 5kt · görüş 400 m · tavan 200 ft · sis · 13°C · QNH 1019"
Orada GÖRÜŞ 400 m (havalimanını kapatan sayı) ile QNH 1019 (rutin bilgi)
aynı puntoda ve aynı gri tondaydı.

EN KRİTİK ÜÇÜ:
  1) AYNI SAYI İKİ KEZ YAZILMASIN - hero ile ikincil satır kesişmemeli.
  2) EĞİLİM UYDURULMASIN - veri yoksa çizgi yok, "yok" yazar.
  3) TELEGRAM'IN ÖZETİ BOZULMASIN - ozet_satiri() sayfaya göre
     değiştirilmedi, sayfa kendi ikincil satırını kuruyor.
"""
import re
from datetime import datetime, timedelta, timezone

import ltfj_sayfa as s
from ltfj_analiz import metar_coz

SIMDI = datetime.now(timezone.utc)
METAR = "LTFJ 231420Z 06005KT 0400 FG VV002 13/13 Q1019 NOSIG"


def _gecmis(n=12, gorus=True):
    g = []
    for i in range(n - 1, -1, -1):
        kayit = {"zaman": (SIMDI - timedelta(minutes=30 * i)).isoformat(),
                 "tavan": 200 + i * 40, "ruzgar_hiz": 4, "qnh": 1019,
                 "sicaklik": 13.0 + i * 0.2, "cig_noktasi": 13.0 + i * 0.1}
        if gorus:
            kayit["gorus"] = 400 + i * 220
        g.append(kayit)
    return g


def _sayfa(tmp_path, gecmis=None, metin=METAR) -> str:
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([{"tip": "METAR", "zaman": SIMDI, "icao": "LTFJ", "metin": metin}],
                _gecmis() if gecmis is None else gecmis, hedef)
    return hedef.read_text(encoding="utf-8")


def _kivilcim_sayisi(html: str) -> int:
    """SVG ETIKETINI sayar, sinif adini degil: ".hero-kivilcim" ayrica CSS
    kuralinda geciyor ve testin ilk surumu tam da ona takilmisti."""
    return len(re.findall(r'<svg class="hero-kivilcim"', html))


def _govde(html: str) -> str:
    return html.split("</style>")[1]


def _hero(html: str) -> dict:
    """Hero hucrelerini (etiket -> deger) cikarir.

    BIRIM ARTIK ZORUNLU DEGIL: "bildirilmedi" gibi degerlerin birimi yok
    ve <span class="hero-birim"> hic basilmiyor. Bu yardimcinin ilk
    surumu <span> bekliyordu, o yuzden birimsiz hucreler sessizce
    SOZLUKTEN DUSUYORDU - test KeyError ile degil, eksik veriyle
    yaniliyordu."""
    blok = html.split('<div class="hero">')[1].split("</div></div>")[0]
    # Birim <span>'i DISARIDA birakiliyor: testler ciplak degeri
    # karsilastiriyor ("400", "400m" degil).
    # SINIF LISTESI ARTIK DEGISKEN: esik asiminda "hero-deger hero-uyari",
    # birimsiz degerde "hero-deger hero-deger-metin" oluyor. Sabit
    # class="hero-deger" bekleyen surum, tam da vurgulanan hucreleri
    # sessizce atliyordu.
    # Etikette de band isareti ("eşik altı") olabilir - o da ayiklaniyor.
    return {re.sub(r"<[^>]+>.*", "", etiket).strip():
            deger.split("<span")[0].strip()
            for etiket, deger in re.findall(
                r'<div class="hero-etiket">(.*?)</div>'
                r'<div class="hero-deger[^"]*">(.*?)</div>', blok, re.S)}


# ------------------------------------------- 1) aynı sayı iki kez değil
def test_ikincil_satir_hero_alanlarini_TEKRARLAMIYOR(tmp_path):
    """Aynı sayıyı 100 piksel arayla iki kez yazmak dağınıklıktır."""
    html = _sayfa(tmp_path)
    m = re.search(r'<div class="ozet-ikincil">([^<]*)</div>', html)
    assert m, "ikincil satır yok"
    ikincil = m.group(1)
    for yasak in ("görüş", "Rüzgâr", "tavan"):
        assert yasak not in ikincil, f"{yasak} hem hero'da hem ikincilde: {ikincil}"


def test_ikincil_satir_hero_da_OLMAYANLARI_gosteriyor(tmp_path):
    """Hava kodu, çiy noktası ve QNH hero'da yok - kaybolmamalılar."""
    m = re.search(r'<div class="ozet-ikincil">([^<]*)</div>', _sayfa(tmp_path))
    ikincil = m.group(1)
    assert "FG" in ikincil and "QNH 1019" in ikincil and "çiy" in ikincil


def test_TELEGRAM_ozeti_DEGISMEDI():
    """ozet_satiri() Telegram'ın özeti; sayfa için değiştirilseydi
    Telegram mesajından görüş/rüzgâr düşerdi."""
    from ltfj_analiz import ozet_satiri
    metin = ozet_satiri(metar_coz("LTFJ 231420Z 06005KT 0400 FG VV002 13/13 Q1019"))
    for beklenen in ("Rüzgâr", "görüş", "QNH"):
        assert beklenen in metin, f"{beklenen} Telegram özetinden düşmüş: {metin}"


# ------------------------------------------- 2) eğilim uydurulmuyor
def test_gecmis_YOKSA_egilim_cizgisi_CIZILMIYOR(tmp_path):
    html = _sayfa(tmp_path, gecmis=[])
    assert _kivilcim_sayisi(html) == 0
    assert _govde(html).count("eğilim verisi yok") == len(s.HERO_ALANLAR)


def test_gorus_gecmiste_YOKSA_yalnizca_o_cizgi_bos(tmp_path):
    """gorus alanı olcum_gecmisi'ne YENİ eklendi. Eski kayıtlarda yok;
    o zaman yalnızca görüş çizgisi boş kalmalı, ötekiler çizilmeli."""
    html = _sayfa(tmp_path, gecmis=_gecmis(gorus=False))
    assert _govde(html).count("eğilim verisi yok") == 1
    assert _kivilcim_sayisi(html) == len(s.HERO_ALANLAR) - 1


def test_gorus_gecmiste_VARSA_cizgi_ciziliyor(tmp_path):
    html = _sayfa(tmp_path)
    assert "eğilim verisi yok" not in _govde(html)
    assert _kivilcim_sayisi(html) == len(s.HERO_ALANLAR)


def test_bot_olcum_gecmisine_GORUS_yaziyor():
    """Çizginin veri kaynağı. Bu alan düşerse görüş eğilimi sessizce
    kaybolur ve kimse fark etmez."""
    import ast
    kok = ast.parse(open("ltfj_bot.py", encoding="utf-8").read())
    fonk = next(d for d in ast.walk(kok)
                if isinstance(d, ast.FunctionDef)
                and d.name == "olcum_gecmisini_guncelle")
    anahtarlar = {k.value for d in ast.walk(fonk) if isinstance(d, ast.Dict)
                  for k in d.keys if isinstance(k, ast.Constant)}
    assert "gorus" in anahtarlar, "olcum_gecmisi görüşü saklamıyor"


# ------------------------------------------- 3) değerler doğru
def test_dort_olcum_de_var(tmp_path):
    h = _hero(_sayfa(tmp_path))
    assert set(h) == {"GÖRÜŞ", "TAVAN", "RÜZGÂR", "SPREAD"}


def test_degerler_METARDAN_geliyor(tmp_path):
    h = _hero(_sayfa(tmp_path))
    assert h["GÖRÜŞ"] == "400" and h["TAVAN"] == "200"
    assert h["RÜZGÂR"] == "060°/5" and h["SPREAD"] == "0.0"


def test_degisken_ruzgar_VRB_yaziliyor(tmp_path):
    h = _hero(_sayfa(tmp_path, metin="LTFJ 231420Z VRB03KT 9999 15/10 Q1019"))
    assert h["RÜZGÂR"] == "VRB/3"


def test_eksik_alan_BILDIRILMEDI_oluyor_cokmuyor(tmp_path):
    """KARAR DEGISTI: eskiden "—" basiliyordu. 24px w650'de tire KALIN
    YATAY BIR CUBUK olarak ciziliyor ve "ustu cizilmis deger" ya da eksi
    isareti gibi okunuyordu - yani "bilgi yok" ile "deger sifir/negatif"
    gorsel olarak ayirt edilemiyordu. Serit zaten "tavan yok" diyordu."""
    h = _hero(_sayfa(tmp_path, metin="LTFJ 231420Z /////KT //// // Q////"))
    assert "bildirilmedi" in h.values(), h


def test_tavan_yoksa_BILDIRILMEDI(tmp_path):
    h = _hero(_sayfa(tmp_path, metin="LTFJ 231420Z 06005KT 9999 15/10 Q1019"))
    assert h["TAVAN"] == "bildirilmedi"


# ------------------------------------------- görsel sözleşme
def test_kivilcim_currentColor_kullaniyor(tmp_path):
    """Sabit renk verilseydi koyu temada yanlış tonda çizilirdi.

    ÇAPA DARALTILDI: kıvılcım SVG'sine gradyan dolgu eklendi ve o
    `<path ... stroke="none">` ile BAŞLIYOR - testin ilk sürümü ilk
    stroke'u arıyordu, yani dolgunun "none"ını okuyup kırılıyordu.
    Artık ÇİZGİ path'i aranıyor (stroke-width="2" olan)."""
    html = _sayfa(tmp_path)
    svg = re.search(r'<svg class="hero-kivilcim".*?</svg>', html, re.S)
    assert svg, "kıvılcım svg yok"
    # ÇİZGİ path'i: stroke-width="2" olan. Gradyan dolgusu
    # stroke="none" ile geliyor ve SVG'de ondan ÖNCE duruyor.
    m = re.search(r'stroke="([^"]*)" stroke-width="2"', svg.group(0))
    assert m and m.group(1) == "currentColor", m.group(1) if m else "cizgi yok"
    # Dolgunun da marka tonundan geldiğini doğrula (sabit renk değil):
    assert 'stop-color="currentColor"' in svg.group(0)


def test_kivilcim_ekran_okuyucudan_gizli(tmp_path):
    for svg in re.findall(r'<svg class="hero-kivilcim"[^>]*>', _sayfa(tmp_path)):
        assert 'aria-hidden="true"' in svg


def test_durum_rengi_kartin_SOL_kenarinda(tmp_path):
    html = _sayfa(tmp_path)
    assert "kart-durum" in html and "--durum-renk:" in html
    kural = html.split(".kart.kart-durum {")[1].split("}")[0]
    assert "border-left" in kural


def test_durum_rengi_TEK_BASINA_anlam_tasimiyor(tmp_path):
    """Renk körlüğü: kenar rengi tek işaret olsaydı durum okunamazdı.
    Rozet metni (BLU/RED gibi) kartta kalmalı."""
    html = _sayfa(tmp_path)
    assert 'class="rozet"' in html


def test_telefonda_2x2_genis_ekranda_4lu(tmp_path):
    html = _sayfa(tmp_path)
    # Capa TAM KURAL: ".hero {" artik ".su-an .hero {" kuralina da
    # uyuyor ve testin ilk surumu onun govdesini okuyordu. Bu projede
    # bu tuzaga birkac kez dusuldu - kural: capayi benzersiz yap.
    taban = html.split("\n  .hero {")[1].split("}")[0]
    assert "repeat(2,1fr)" in taban
    genis = html.split("@media (min-width:560px)")[1].split("}")[0]
    assert "repeat(4,1fr)" in genis


def test_tavan_KANITLI_olarak_yoksa_YOK_yaziyor(tmp_path):
    """SCT050 okunmus: tavan en alcak 5/8+ katmanin tabanidir, oyle bir
    katman yoksa tavan TANIM GEREGI yoktur. Bunu "bildirilmedi" diye
    yazmak, bilgi eksikligi varmis gibi okutuyordu.

    Hero'da degerin USTUNDE zaten "TAVAN" etiketi var, o yuzden burada
    sade "yok" yeterli; etiketi olmayan ozet seritte "tavan yok" yaziyor
    (bkz. test_ltfj_sayfa_ozet_serit.py)."""
    h = _hero(_sayfa(tmp_path, metin="LTFJ 231420Z 06005KT 9999 SCT050 15/10 Q1019"))
    assert h["TAVAN"] == "yok"


def test_tavan_BKN_yuksekligi_bilinmiyorsa_YOK_DENMEZ(tmp_path):
    """BKN/// : tavan VARDIR, yalnizca yuksekligi bildirilmemistir."""
    h = _hero(_sayfa(tmp_path, metin="LTFJ 231420Z 06005KT 9999 BKN/// 15/10 Q1019"))
    assert h["TAVAN"] == "bildirilmedi"
