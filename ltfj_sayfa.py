#!/usr/bin/env python3
"""
GitHub Pages icin canli durum sayfasi uretir.

Bot her calistiginda index.html'i yeniden yazar, workflow onu repoya commit eder,
GitHub Pages yayinlar. Ek altyapi yok. Sayfa tek dosya - harici CSS/JS yok.
"""

import html
import math
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ltfj_lvo_farkindalik as farkindalik
import ltfj_notam
import ltfj_lvo_referans as lvo
import ltfj_gorus_gecis_tablo as gecis_tablo
import ltfj_sis_iklim_tablo as sis_iklim
import ltfj_sis_olasilik as sis_olasilik
import ltfj_sis_olasilik_b as sis_olasilik_b
import ltfj_vfr as vfr
from ltfj_analiz import (TAVAN_KATMANLARI, metar_coz, ozet_satiri,
                         uyarilar)
# Sis kodlari alanin KENDI tanimiyla ayni yerde dursun - bu oturumda
# kopyalanmis bir sabit (NOTAM gecerlilik karari) iki yerde ayni hatayi
# tasidi, tekrarlamayalim. ltfj_rasat zaten import edildigi icin ek bir
# agir bagimlilik gelmiyor.
from ltfj_dis_kaynak_cache import SIS_KODLARI
from ltfj_ayarlar import (GOZLEM_BEKLENEN_DK, GOZLEM_TAZE_DK,
                          SESSIZLIK_SAAT, YEREL_TZ, notam_bayat_saat)
import ltfj_pist as pist
from ltfj_pist import havacilik_notlari
import ltfj_cozumle as cozumle
from ltfj_rasat import taf_bicimle

# ltfj_bot.py::ETIKET/_yorumu_bicimle ile AYNI etiket kumesi - ama bu web'e
# ozel bir bicimlendirici (Telegram HTML "\n" ile, web "<br>" ile ayrilir).
# Burada YENI bir Claude cagrisi YAPILMAZ - sadece state.yorum_onbellegi'nde
# (Telegram icin) zaten hesaplanmis metin okunur (bkz. _kart/sayfa_yaz).
_ETIKET = re.compile(r"^(Rüzgâr|Görüş|Gökyüzü|Uçuşa etkisi|Genel|Dikkat)\s*:\s*(.+)$")

# RENK_KODU (BLU/WHT/GRN/YLO/AMB/RED -> hex) BURADAN KALDIRILDI.
# Sebep: o kodlar botun KENDI urettigi bir ciddiyet olcegiydi ve sayfanin
# dip notu her seferinde "resmi bir ICAO CAT I/II/III kategorisi degildir"
# diye uyarmak zorunda kaliyordu. Bir gosterge, var olmak icin kendi
# aleyhine bir dipnota ihtiyac duyuyorsa yanlis gostergedir. Sayfanin
# tepesinde artik VFR/IFR var: uydurma degil, ICAO Annex 2 Tablo 3-1
# esikleri (bkz. ltfj_vfr) ve ZATEN hesaplanan bir deger.
#
# ESIKLER (ltfj_pist.RENK_DURUMLARI) YERINDE DURUYOR ve dusuk gorus/tavan
# sayisini hala vurguluyor (bkz. _olcu_bandi) - kalkan sey OLCEGIN ADI,
# olcegin kendisi degil. Telegram tarafi da degismedi: RENK_SIMGE ve
# renk_durumu orada calismaya devam ediyor.

def _gunes_iso(an: datetime) -> tuple[str, str]:
    """LTFJ gun dogumu/batimi, ISO damga olarak (yoksa bos dize).

    HESAP KOPYALANMADI: ltfj_pist._gunes_saatleri() zaten var ve
    sis_riski() de onu kullaniyor - iki ayri gunes hesabi olsaydi
    sayfanin "gece" dedigi an ile sis notunun "gece" dedigi an
    ayrisabilirdi."""
    try:
        sonuc = pist._gunes_saatleri(an)
    except Exception:
        return "", ""
    if not sonuc:
        return "", ""
    dogus, batim = sonuc
    return dogus.isoformat(), batim.isoformat()


def _zaman_metni(an: datetime, tarihli: bool = False) -> str:
    """TEK ZAMAN KURALI: UTC esas, yerel parantez icinde.

    Olculdu: sayfada BES ayri bicim vardi -
        19:20Z · 23.09 19:20Z · 23.09.2026 23:07 · 23:07 yerel · 231920Z
    ve dordu ayni ilk ekranda goruluyordu. Havacilikta zaman UTC
    konusulur; yerel saat gerekli ama ikincil ve her seferinde farkli
    yazilinca okuyucu her defasinda yeniden yorumluyor.

    HAM METAR DAMGASINA (231920Z) DOKUNULMUYOR - o rapor metninin
    kendisi, bizim bicimimiz degil.
    """
    utc = an.astimezone(timezone.utc)
    yerel = an.astimezone(YEREL_TZ)
    on = f"{utc:%d.%m} " if tarihli else ""
    return f"{on}{utc:%H:%M}Z ({yerel:%H:%M} yerel)"


# ---------------------------------------------------------------- ikonlar
# Brief: arayuzde emoji YOK. Emoji platforma gore bambaska cizilir, boyu
# yazi tipiyle uyusmaz ve ekran okuyucu onlari yuksek sesle okur.
#
# RENK_SIMGE (ltfj_pist) BURAYA DAHIL DEGIL: o Telegram mesajlarinin
# simgesi ve orada emoji DOGRU ortam - Telegram'da SVG yok.
IKONLAR = {
    "zil":    '<path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/>'
              '<path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
    "yenile": '<path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 3v6h-6"/>',
    "uyari":  '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h16.9a2 2 0 0 0 1.7-3'
              'L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "kapat":  '<path d="M18 6 6 18M6 6l12 12"/>',
    "ucak":   '<path d="M17.8 19.2 16 11l3.5-3.5a2.1 2.1 0 0 0-3-3L13 8 4.8 6.2'
              'a1 1 0 0 0-.9 1.7l5.6 3.4-2.3 2.3-2.4-.5a1 1 0 0 0-.9 1.6l2.6 2.6'
              ' 2.6 2.6a1 1 0 0 0 1.6-.9l-.5-2.4 2.3-2.3 3.4 5.6a1 1 0 0 0 1.7-.9z"/>',
    "yapayzeka": '<rect x="4" y="8" width="16" height="12" rx="2"/>'
              '<path d="M12 8V4M8 14h.01M16 14h.01M9 18h6"/>',
    "zil-kapali": '<path d="M8.7 3.7A6 6 0 0 1 18 8c0 2.4.4 4.2 1 5.5"/>'
              '<path d="M16.8 16.8H3s3-2 3-9a6 6 0 0 1 .5-2.4"/>'
              '<path d="M13.7 21a2 2 0 0 1-3.4 0"/><path d="M2 2l20 20"/>',
    # Sekme ikonlari - YALNIZCA genis ekran rayinda cizilir (telefonda
    # cubuk zaten tam kapasitede, olculdu: 326/326px).
    "sekme-durum": '<rect x="3" y="3" width="7" height="9" rx="1"/>'
              '<rect x="14" y="3" width="7" height="5" rx="1"/>'
              '<rect x="14" y="12" width="7" height="9" rx="1"/>'
              '<rect x="3" y="16" width="7" height="5" rx="1"/>',
    "sekme-beklenti": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "sekme-istatistik": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "sekme-lvo": '<path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6z"/>'
              '<circle cx="12" cy="12" r="2.5"/>',
    "sekme-notam": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>'
              '<path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/>',
    "not":    '<path d="M9 3h6a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V4'
              'a1 1 0 0 1 1-1z"/><path d="M16 4h2a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H6'
              'a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M8 11h8M8 15h5"/>',
    "sis":    '<path d="M3 8h13M6 12h15M3 16h11M8 20h11"/>',
    "nokta":  '<circle cx="12" cy="12" r="5"/>',
}


def ikon(ad: str, sinif: str = "ikon") -> str:
    """Inline SVG. Sayfa tek dosya ve dis bagimlilik tasimiyor; ikon
    fontu ya da sprite dosyasi havalimani aginda engellenebilirdi."""
    return (f'<svg class="{sinif}" viewBox="0 0 24 24" aria-hidden="true" '
            f'focusable="false">{IKONLAR[ad]}</svg>')


GRAFIK_PENCERE_SAAT = 6
GRAFIK_MIN_NOKTA = 2      # cizgi cizmek icin en az bu kadar nokta lazim
GRAFIK_YEDEK_NOKTA = 12   # pencere yeterli veri vermezse en fazla bu kadar eski kayit gosterilir
# RENKLER KALDIRILDI - hepsi artik --marka. Onceki degerler
# (#3b82f6 / #22c55e / #eab308 / #ef4444) DURUM RENKLERININ AYNISIYDI:
# BLU, GRN, YLO ve RED. Yani sayfa renksiz degildi, renk butcesini SERI
# KIMLIGINE harciyordu - yesil bir tavan cizgisi "iyi", kirmizi bir
# sicaklik cizgisi "kotu" gibi okunuyordu, oysa ikisi de sadece birer
# seri. Dort grafigin her biri TEK SERI ve kendi basligini tasiyor
# ("Rüzgâr", "Bulut tavanı", ...), yani kimligi baslik veriyor; hue'ya
# gerek yok. (dataviz rehberi: "Status colors are reserved ... never
# reused for series".)
GRAFIKLER = (
    ("ruzgar_hiz", "Rüzgâr", "kt"),
    ("tavan", "Bulut tavanı", "ft"),
    ("qnh", "QNH", "hPa"),
    ("sicaklik", "Sıcaklık", "°C"),
)

# --------------------------------------------------------------- yazı tipi
# IBM Plex Sans/Mono, GitHub Pages'ten KENDİ deposundan servis edilir -
# fonts.googleapis.com'a istek YOK. Sebep: sayfa havalimanı ağından
# açılıyor; üçüncü taraf CDN engellenirse yazı tipi sessizce sistem
# fontuna düşerdi. Dosyalar yazitipi/ klasöründe (toplam ~130 KB) ve
# bot tarafından YENIDEN URETILMEZ, depoda statik dururlar.
#
# Sans DEGISKEN (400..700): sayfada 20 yerde geçen font-weight:650 gibi
# ara ağırlıklar tam olarak o ağırlıkta çizilir, yuvarlanmaz.
# Mono statiktir (400/600) - IBM Plex Mono'nun değişken sürümü Google
# Fonts'ta yok; 650 isteyen iki yer 600'e yuvarlanır, fark edilmez.
#
# Türkçe latin alt kümesine SIGMAZ: ğ/ş/İ latin-ext'te, ı latin'de.
# İkisi de gömülü. Δ/▶/⟳ ve emoji hiçbirinde yok, tarayıcı onları
# karakter bazında sistem fontuna düşürür - beklenen davranış.
YAZITIPI_KLASORU = "yazitipi"
_LATIN = ("U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, "
          "U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, "
          "U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD")
_LATIN_EXT = ("U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, "
              "U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, "
              "U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, "
              "U+2113, U+2C60-2C7F, U+A720-A7FF")

# (aile adı, dosya adı, font-weight, unicode-range)
YAZITIPI_DOSYALARI = (
    ("IBM Plex Sans", "plex-sans-latin-400-700.woff2", "400 700", _LATIN),
    ("IBM Plex Sans", "plex-sans-latin-ext-400-700.woff2", "400 700", _LATIN_EXT),
    ("IBM Plex Mono", "plex-mono-latin-400.woff2", "400", _LATIN),
    ("IBM Plex Mono", "plex-mono-latin-ext-400.woff2", "400", _LATIN_EXT),
    ("IBM Plex Mono", "plex-mono-latin-600.woff2", "600", _LATIN),
    ("IBM Plex Mono", "plex-mono-latin-ext-600.woff2", "600", _LATIN_EXT),
)

# font-display:swap - yazı tipi inene kadar sayfa BOŞ beklemez, sistem
# fontuyla çizilir sonra değişir. Operasyonel bir sayfada "yazı yok"
# hali "yazı biraz sonra değişti" halinden çok daha kötü.
YAZITIPI_CSS = "\n".join(
    f'  @font-face {{ font-family:"{aile}"; font-style:normal;\n'
    f'    font-weight:{agirlik}; font-display:swap;\n'
    f'    src:url("{YAZITIPI_KLASORU}/{dosya}") format("woff2");\n'
    f"    unicode-range:{aralik}; }}"
    for aile, dosya, agirlik, aralik in YAZITIPI_DOSYALARI)


# ============================================================ VARLIKLAR ===
# CSS ve JS ARTIK BU DOSYADA DEGIL: sayfa_kaynak/ altinda duz .css/.js.
#
# Neden: SABLON bir str.format() sablonu ve icindeki 2800 satirlik CSS/JS
# o yuzden format sozdizimine tabiydi. Bu oturumda yasanan sayfa
# hatalarinin cogu dogrudan buradan geldi:
#   - "{ikon_kapat}" sayfaya OLDUGU GIBI basildi (format degerlerin icine
#     girmez),
#   - JS regex'indeki \b, SABLON ham dize olmadigi icin gercek BACKSPACE
#     karakterine donustu ve regex hic eslesmedi,
#   - her suslu parantez ikilenmek zorundaydi ({{ }}), tek bir unutulan
#     cift tum sayfayi KeyError ile dusuruyordu,
#   - CSS/JS icindeki yorumlar Python kaynagiyla karisiyor, hangisinin
#     tarayiciya indigi kaynaktan okunmuyordu.
# Ayri dosyada CSS/JS DUZ yazilir: ikileme yok, kacis yok, editor
# sozdizimi renklendirmesi var. Python degerleri @@ad@@ isaretiyle
# girer - CSS/JS'te dogal olarak gecmeyen, tek anlamli bir isaret.
#
# ESDEGERLIK: bu ayrim yapilirken uretilen sayfa, saat dondurularak
# gercek state'ten once/sonra URETILDI ve BAYT BAYT AYNI cikti.
VARLIK_KLASORU = Path(__file__).resolve().parent / "sayfa_kaynak"
STIL_DOSYASI = "stil.css"
# (SABLON'daki yer tutucu, dosya) - SIRA ONEMLI DEGIL, her betik kendi
# yer tutucusuna gider; sayfadaki sira SABLON'daki yerlerinden gelir.
BETIK_DOSYALARI = (
    ("betik_kabuk_js_sinifi", "01_kabuk_js_sinifi.js"),
    ("betik_baslik_tazelik", "02_baslik_tazelik.js"),
    ("betik_notam", "03_notam.js"),
    ("betik_lvo", "04_lvo.js"),
    ("betik_atc_notes", "05_atc_notes.js"),
    ("betik_push", "06_push.js"),
    ("betik_otomatik_yenileme", "07_otomatik_yenileme.js"),
    ("betik_vfr", "08_vfr.js"),
    ("betik_sis_baglanti", "09_sis_baglanti.js"),
    ("betik_grafik_ipucu", "10_grafik_ipucu.js"),
)
VARLIK_YER_TUTUCU = re.compile(r"@@(\w+)@@")


def _varlik_oku(ad: str) -> str:
    return (VARLIK_KLASORU / ad).read_text(encoding="utf-8")


def _varlik_doldur(metin: str, degerler: dict) -> str:
    """@@ad@@ isaretlerini degerlerle doldurur.

    Bilinmeyen bir ad KeyError verir - sessizce "@@ad@@" birakip sayfaya
    basmaktansa uretimin durmasi dogru (bkz. {ikon_kapat} olayi)."""
    return VARLIK_YER_TUTUCU.sub(lambda m: str(degerler[m.group(1)]), metin)


def _sablonu_doldur(degerler: dict) -> str:
    """SABLON'u doldurur: once CSS/JS varliklari kendi degerleriyle, sonra
    iskelet. Varlik metni format'a DEGER olarak gider - format degerlerin
    icine girmedigi icin CSS/JS'teki { } artik hicbir sey ifade etmez."""
    varliklar = {"stil": _varlik_doldur(_varlik_oku(STIL_DOSYASI), degerler)}
    for yer, dosya in BETIK_DOSYALARI:
        varliklar[yer] = _varlik_doldur(_varlik_oku(dosya), degerler)
    return SABLON.format(**degerler, **varliklar)


SABLON = """<!DOCTYPE html>
<html lang="tr" data-gun-dogumu="{gun_dogumu}" data-gun-batimi="{gun_batimi}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{icao} · Hava Durumu</title>
<meta name="description" content="{icao} anlık METAR ve TAF">
<style>{stil}</style>
<script>{betik_kabuk_js_sinifi}</script>
</head>
<body>
<div class="sar">
<header>
  <div class="header-metin">
    <h1><span class="ust-kod">{icao}</span><span class="ust-ad">İstanbul Sabiha Gökçen</span></h1>
  </div>
  <div class="header-butonlar">
    <!-- Ikon ve metin AYRI: JS yalnizca metni degistirir. textContent
         dugmenin tamamini ezseydi SVG ikon da silinirdi. -->
    <button type="button" class="yenile" id="bildirim-izin-btn" hidden>
      <span id="bildirim-ikon">{ikon_zil}</span><span class="btn-metin"
      id="bildirim-metin">Bildirimler</span></button>
    <button type="button" class="yenile" id="sayfa-yenile-btn">
      {ikon_yenile}<span class="btn-metin">Yenile</span></button>
  </div>
</header>
<!-- DURUM BANDI - sayfanin TEK birincil metrigi.
     Ucus kurali (VFR/IFR) sayfanin tek birincil metrigi. Eskiden
     burada botun kendi urettigi bir ciddiyet olcegi vardi ve dip notu
     her seferinde "resmi bir kategori degildir" diye kendini
     yalanliyordu; yerini ICAO Annex 2 Tablo 3-1 esiklerinden gelen,
     sayfada ZATEN hesaplanan bir deger aldi. Renk TEK TASIYICI DEGIL -
     nokta renginin yaninda harfler ve tam cumle de duruyor.
     Tazelik gostergesi SUNUCUDA degil ISTEMCIDE hesaplanir: sayfa
     saatlerce acik kalabiliyor ve sunucuda yazilan "canli" etiketi
     zamanla yalan olurdu. data-gozlem en yeni METAR/SPECI zamani. -->
<div class="durum-bandi">
{durum_kodu_html}
  <div class="durum-sag">
    <span class="ust-durum" id="ust-durum" data-gozlem="{son_gozlem_iso}"
          role="status"></span>
    <span class="ust-saat" id="ust-saat" title="Eşgüdümlü Evrensel Zaman"></span>
    <!-- Gun/gece: sis penceresi gece-sabah oldugu icin bu BILGI,
         dekor degil. Metni JS dolduruyor (sayfa acik kalabilir). -->
    <span class="ust-faz" id="ust-faz"></span>
  </div>
</div>
<!-- Veri tazeligi seridi: hangi kaynak ne kadar eski. Brief'in istedigi
     "DATA STATUS" bolumunun sikistirilmis hali - dekoratif bir "LIVE"
     etiketi yerine OLCULEN yaslar. -->
<!-- SU AN blogu: dort ana olcu, sayfanin tepesinde ve KART DISINDA.
     Ayni dort olcu eskiden hem burada (serit) hem de METAR kartinin
     icinde (hero) vardi - ikisi ayni ekranda, farkli bicimlerde. Artik
     tek yerde ve tek bicimde (bkz. _olcu). Serit KALDIRILMADI: hero
     kaydirinca ekrandan cikiyor, serit yapiskan. Ikisi ayni anda
     gorunmesin diye serit yalnizca hero ekrandan CIKINCA aciliyor
     (asagidaki IntersectionObserver). JS yoksa ikisi de gorunur -
     eski davranis, bilgi kaybi yok. -->
<div class="su-an" id="su-an">{hero_html}</div>
<div class="veri-serit">
  <span class="veri-oge"><b>METAR</b><time id="veri-metar"
        data-zaman="{son_gozlem_iso}"></time></span>
  <span class="veri-oge"><b>TAF</b><time id="veri-taf"
        data-zaman="{son_taf_iso}"></time></span>
  <span class="veri-oge"><b>NOTAM</b><span id="veri-notam">—</span></span>
  <span class="veri-oge veri-kaynak">MGM · sayfa {guncelleme}</span>
</div>
<div class="yapiskan-ust">
{ozet_serit_html}
{sekme_cubugu_html}
</div>

<div class="sekme-panel" id="panel-durum" role="tabpanel"
     aria-labelledby="sekme-durum">
{govde}
</div>

<div class="sekme-panel" id="panel-beklenti" role="tabpanel"
     aria-labelledby="sekme-beklenti">
{beklenti_html}
</div>

<div class="sekme-panel" id="panel-istatistik" role="tabpanel"
     aria-labelledby="sekme-istatistik">
{istatistik_html}
</div>

<div class="sekme-panel" id="panel-lvo" role="tabpanel"
     aria-labelledby="sekme-lvo">
<div class="kart">
  <div id="lvo-govde">
    <div class="notam-uyari">
      {ikon_uyari}Bilgi amaçlıdır. Operasyonel karar yerine geçmez. Güncel AIP, ATIS, AWOS
      ve resmî yayınlar kontrol edilmelidir.
    </div>

    <!-- SIRA OPERASYONELDEN REFERANSA. Olculdu: statik dokuman referansi
         3838 bayt, farkindalik notlari 198 bayt - yani referans 19 KAT
         buyuk ve operasyonel olani asagi itiyordu (panel 1556px). Simdi
         once "su an ne oluyor", sonra "kural neydi". -->
    <div class="lvo-alt-baslik">A) Farkındalık Notları
      <span class="lvo-provenance">METAR/TAF/AWOS</span></div>
{lvo_farkindalik_html}

    <div class="lvo-alt-baslik">B) AWOS RVR
      <span class="lvo-provenance">MANUAL AWOS</span></div>
    <div id="lvo-awos-liste"><div class="notam-bos">Yükleniyor…</div></div>
    <div class="lvo-form">
      <div class="lvo-form-alan">
        <label for="lvo-awos-pist">Runway</label>
        <select id="lvo-awos-pist"><option value="06R">06R</option><option value="24R">24R</option></select>
      </div>
      <div class="lvo-form-alan">
        <label for="lvo-awos-tdz">TDZ (m)</label>
        <input type="number" id="lvo-awos-tdz" min="0" max="9999" inputmode="numeric">
      </div>
      <div class="lvo-form-alan">
        <label for="lvo-awos-mid">MID (m)</label>
        <input type="number" id="lvo-awos-mid" min="0" max="9999" inputmode="numeric">
      </div>
      <div class="lvo-form-alan">
        <label for="lvo-awos-end">STOP-END (m)</label>
        <input type="number" id="lvo-awos-end" min="0" max="9999" inputmode="numeric">
      </div>
      <button type="button" id="lvo-awos-kaydet">SAVE AWOS RVR</button>
      <button type="button" id="lvo-awos-temizle" class="lvo-awos-temizle">CLEAR</button>
    </div>
    <div id="lvo-awos-hata" class="lvo-hata"></div>

    <div class="lvo-alt-baslik">C) LVO Related NOTAM
      <span class="lvo-provenance">NOTAM</span></div>
    <div id="lvo-notam-liste"><div class="notam-bos">Yükleniyor…</div></div>

{lvo_referans_html}
  </div>
</div>
</div>

<!-- NOTAM: aktif liste + gecmis aramasi + kaynak uyarisi. Uyari EN ALTTA:
     her acilista once okunan degil, gerektiginde basvurulan bir not.
     Disindaki <details> KALDIRILDI - artik bir sekme paneli; sekmeye
     basip bir de basligi acmak iki tiklama olurdu. Aktif sayi rozeti
     sekme dugmesine TASINDI (ayni id), cunku panel kapaliyken yeni
     NOTAM'i fark etmenin tek yolu o. -->
<div class="sekme-panel" id="panel-notam" role="tabpanel"
     aria-labelledby="sekme-notam">
<div class="kart">
  <!-- DIS BASLIK KALDIRILDI: "NOTAM" sekme dugmesinin kendi adiydi ve
       hemen altinda "Aktif NOTAM'lar" geliyordu. Senkron zamani (tek
       gercek bilgi) asil bolum basligina TASINDI - id ayni kaldigi icin
       onu dolduran JS'e dokunulmadi. -->
  <div class="alt-bolum">
    <div class="basrow"><span class="tip">Aktif NOTAM'lar</span>
      <span class="zaman" id="notam-senkron-zamani"></span></div>
    <!-- UYARI BURADA, BIR KEZ. Eskiden her kartin ozet cumlesinin
         sonunda parantez icinde tekrarlaniyordu; 28 kartlik bir
         listede 28 kez yaziliyor ve okunmasi gereken cumleyi
         bastiriyordu. Bir kez soylenmesi yetiyor, kaybolmuyor. -->
    <div class="notam-not">Düz metin özetler NOTAC tarafından otomatik
      üretilir ve hata içerebilir — bağlayıcı olan, her kartın altındaki
      ham NOTAM metnidir.</div>
    <div class="notam-arama" id="notam-aktif-filtre">
      <input type="text" id="notam-aktif-q" placeholder="Numara, pist, anahtar kelime…">
      <!-- SIRALAMA. notac'ta "Most critical first" var; onun kritiklik
           siralamasi KENDI modeli ve bize gelen alanlarda karsiligi
           YOK (45 kayitta rank/score benzeri hicbir alan bulunmadi).
           Uydurma bir ciddiyet siralamasi yazmak, bu sayfadan daha
           yeni sokulen renk olceginin aynisi olurdu. Onun yerine
           ADI NE YAPTIGINI SOYLEYEN secenekler: "Kapanislar once"
           NOTAM'in KENDI soyledigine bakar (ICAO Q kodu kosul harfleri
           "LC" = closed, ya da NOTAC'in "closure" etiketi), bir
           onem sirasi uretmez. -->
      <select id="notam-aktif-siralama" aria-label="Sıralama">
        <option value="kapanis">Kapanışlar önce</option>
        <option value="bitis">Bitişi yakın önce</option>
        <option value="yeni">En yeni önce</option>
        <option value="numara">Numaraya göre</option>
      </select>
      <select id="notam-aktif-eleman"><option value="">Tüm elemanlar</option></select>
      <button type="button" id="notam-aktif-temizle">Temizle</button>
    </div>
    <!-- KATEGORI CIPLERI, sayaclariyla. Eskiden bir <select> idi: kac
         pist NOTAM'i oldugunu gormek icin acip saymak gerekiyordu.
         notac'taki gibi sayilar cipin uzerinde - dagilim tek bakista.
         SIFIR SAYILI KATEGORI CIZILMEZ: notac tum sozlugunu bildigi
         icin "Navaid 0" yazabiliyor, biz NOTAC'in kategori sozlugunun
         tamamini bilmiyoruz; olmayan bir kategoriyi 0 ile listelemek
         "bu havalimaninda hic olmaz" gibi okunurdu. -->
    <div class="notam-cipler" id="notam-aktif-kategori"
         role="group" aria-label="Kategori süzgeci"></div>
    <div id="notam-aktif-liste"><div class="notam-bos">Yükleniyor…</div></div>
  </div>

  <!-- YAKLASAN: yururluge girmemis NOTAM'lar. Bolum SADECE boyle bir
       kayit varken cizilir - surekli duran bos bir baslik, "yaklasan
       yok" ile "veri gelmiyor" arasindaki farki silerdi. -->
  <div class="alt-bolum" id="notam-yaklasan-bolum" hidden>
    <div class="basrow"><span class="tip">Yaklaşan NOTAM'lar</span>
      <span class="zaman">henüz yürürlükte değil</span></div>
    <div id="notam-yaklasan-liste"></div>
  </div>

  <div class="alt-bolum">
    <details class="kat">
    <summary>Geçmiş / Arama <span class="kat-rozet" id="notam-gecmis-sayi"></span></summary>
    <div class="notam-arama-not">
      Bu arama yalnızca botun bugüne kadar yerel olarak gördüğü NOTAM'ları
      kapsar — NOTAC'ın kendi tam arşivi değildir.
    </div>
    <div class="notam-arama">
      <input type="text" id="notam-q" placeholder="Numara, pist, anahtar kelime…">
      <input type="date" id="notam-tarih-baslangic">
      <input type="date" id="notam-tarih-bitis">
      <select id="notam-durum">
        <option value="">Tüm durumlar</option>
        <option value="yururlukte">Yürürlükte</option>
        <option value="doldu">Süresi dolmuş</option>
        <option value="baslamadi">Henüz başlamamış</option>
        <option value="iptal">İptal edilmiş</option>
      </select>
      <button type="button" id="notam-arama-temizle">Temizle</button>
    </div>
    <div id="notam-arama-sonuc"><div class="notam-bos">Yükleniyor…</div></div>
    </details>
  </div>

  <div class="notam-uyari">
    {ikon_uyari}Bilgi amaçlıdır. Operasyon öncesi güncel resmî NOTAM/PIB kontrol edilmelidir.
    Kaynak: NOTAC (FAA NOTAM Management System tabanlı üçüncü taraf servis) —
    resmî bir Türk/EUROCONTROL NOTAM kaynağı değildir. Bu bölüm hiçbir operasyonel
    öneri üretmez; sayfadaki meteorolojik analiz bu veriden bağımsızdır.
  </div>
</div>
</div>

<!-- ATC Notes artik sayfa akisinda degil - sag altta sabit FAB'la acilan
     yuzen bir panel (bkz. asagidaki .atc-fab/.atc-panel-ortu). -->
<button type="button" id="atc-fab" class="atc-fab" aria-label="ATC Notes'u aç" title="ATC Notes">
  {ikon_not}<span id="atc-fab-rozet" class="atc-fab-rozet" hidden>0</span>
</button>

<div id="atc-panel-ortu" class="atc-panel-ortu" hidden>
  <div class="atc-panel">
    <div class="atc-panel-ust">
      <span class="tip">ATC Notes</span>
      <button type="button" id="atc-not-ekle-btn" class="atc-not-ekle-btn">+ NOT EKLE</button>
      <button type="button" id="atc-panel-kapat" class="atc-panel-kapat" aria-label="Kapat">{ikon_kapat}</button>
    </div>
    <div class="atc-panel-govde">
      <div class="notam-uyari">
        {ikon_uyari}Bu bölüm ATC tarafından paylaşılan geçici durumsal farkındalık
        notlarıdır. Resmî NOTAM veya operasyonel talimat değildir; NOTAM/
        METAR/pist analiziyle hiçbir bağlantısı yoktur. Kimlik doğrulaması
        yapılmaz — isim yazan kişi tarafından girilir. Her not
        oluşturulduktan tam 48 saat sonra otomatik olarak silinir.
      </div>
      <div id="atc-notes-liste"><div class="notam-bos">Yükleniyor…</div></div>
    </div>
  </div>
</div>

<div id="atc-not-modal" class="modal-ortu" hidden>
  <div class="modal-kutu">
    <h3>Yeni ATC Notu</h3>
    <label for="atc-not-yazan">Adınız</label>
    <input type="text" id="atc-not-yazan" maxlength="100" placeholder="Örn. Ahmet">
    <label for="atc-not-metin">Not</label>
    <textarea id="atc-not-metin" maxlength="1000" rows="4"
              placeholder="Örn. Apron 2 tarafında araç hareketliliği arttı."></textarea>
    <div id="atc-not-hata" class="modal-hata"></div>
    <div class="modal-butonlar">
      <button type="button" id="atc-not-iptal">İptal</button>
      <button type="button" id="atc-not-kaydet">Kaydet</button>
    </div>
  </div>
</div>

{vfr_html}
<footer>
  <!-- Uyari metni SILINMEDI, KATLANDI. Her ekranda acik duran 8 satirlik
       gri blok sayfanin en uzun tek metniydi ve ilk okumadan sonra sifir
       bilgi tasiyordu; ama iceriden biri "bu resmi mi?" diye sordugunda
       elde olmasi sart. details ile ikisi de saglaniyor - ozet satiri
       kapsamin VAR oldugunu soyluyor, ayrinti bir dokunus uzakta. -->
  <details class="kapsam">
  <summary>Kapsam ve sınırlar</summary>
  <div class="kapsam-govde">
  Bu sayfa otomatik üretilir. Operasyonel kullanım için resmî kaynaklara başvurun.
  Sayfanın üstündeki VFR/IFR göstergesi son METAR/SPECI'nin görüş ve tavan
  değerlerini ICAO Annex 2 Tablo 3-1 eşikleriyle karşılaştıran bilgilendirici
  bir göstergedir; resmî bir VFR/IFR tespiti değildir. METAR ve TAF
  çözümlemeleri otomatiktir — bağlayıcı olan ham metindir, her kartın altında
  duruyor. "Meteorolojik tercih" bir ATC pist ataması değildir. NOTAM bölümü NOTAC kaynaklıdır, resmî NOTAM/PIB'in yerine
  geçmez. ATC Notes bölümü kimlik doğrulaması olmayan, paylaşımlı ve geçici
  (48 saat) bir not panosudur; resmî bir bilgi kaynağı değildir. VFR sekmesi
  son METAR/SPECI'nin görüş/tavan değerlerini ICAO Annex 2 eşikleriyle
  karşılaştıran bilgilendirici bir göstergedir; resmî VFR/IFR tespiti değildir.
  </div>
  </details>
</footer>
</div>
<script>{betik_baslik_tazelik}</script>
<script>{betik_notam}</script>
<script>{betik_lvo}</script>
<script>{betik_atc_notes}</script>
<script>{betik_push}</script>
<script>{betik_otomatik_yenileme}</script>
<script>{betik_vfr}</script>
<script>{betik_sis_baglanti}</script>
<script>{betik_grafik_ipucu}</script>
</body>
</html>
"""


def _gecmis_noktalari(gecmis: list, alan: str, sinir: datetime | None) -> list:
    noktalar = []
    for g in gecmis:
        try:
            z = datetime.fromisoformat(g["zaman"])
        except (KeyError, ValueError, TypeError):
            continue
        if sinir is not None and z < sinir:
            continue
        v = g.get(alan)
        if v is not None:
            noktalar.append((z, v))
    noktalar.sort(key=lambda n: n[0])
    return noktalar


def _grafik_verisi(gecmis: list, alan: str, simdi: datetime) -> list:
    """Son GRAFIK_PENCERE_SAAT icindeki noktalari dondurur. Bot yeni devreye
    girdiginde ya da veri akisinda bosluk varsa pencere yeterli nokta
    vermeyebilir - o durumda elde ne varsa (en fazla GRAFIK_YEDEK_NOKTA kadar
    eski kayit) gosteriyoruz, boylece grafik hemen gorunur ve veri biriktikce
    kendiliginden gercek 6 saatlik pencereye sikisir."""
    sinir = simdi - timedelta(hours=GRAFIK_PENCERE_SAAT)
    noktalar = _gecmis_noktalari(gecmis, alan, sinir)
    if len(noktalar) >= GRAFIK_MIN_NOKTA:
        return noktalar
    return _gecmis_noktalari(gecmis, alan, None)[-GRAFIK_YEDEK_NOKTA:]


def _dikey_olcek(degerler: list) -> tuple[float, float]:
    """Grafigin dusey ekseni. TEK KAYNAK: hem cizgi hem esik etiketi
    ayni olcegi kullanmak zorunda, yoksa etiket cizginin uzerine
    oturmaz."""
    v_min, v_max = min(degerler), max(degerler)
    if v_min == v_max:
        v_min, v_max = v_min - 1, v_max + 1
    pad = (v_max - v_min) * 0.15
    return v_min - pad, v_max + pad


def _esik_orani(degerler: list, esik: float | None,
                yukseklik: int = 64) -> float | None:
    """Esigin cizim kutusundaki DUSEY ORANI (0 = ust kenar, 1 = alt) -
    cizilen araliga dusmuyorsa None.

    Etiket SVG <text> DEGIL, ustune konumlanan HTML: SVG
    preserveAspectRatio="none" ile esnedigi icin icindeki yazi hem
    kuculuyor hem yatayda eziliyordu (olculdu: 600 birimlik kutu ~326
    px'e siginca 11 px'lik yazi ~6 px'e dusuyor). Oran burada
    hesaplanip yuzde olarak HTML'e veriliyor."""
    if esik is None or not degerler:
        return None
    v_min, v_max = _dikey_olcek(degerler)
    if not v_min <= esik <= v_max:
        return None
    y = yukseklik - 4 - (yukseklik - 8) * ((esik - v_min) / (v_max - v_min))
    return y / yukseklik


def _svg_cizgi(noktalar: list, renk: str, raporlanmiyor: bool = False,
               guncel_zaman: datetime | None = None,
               genislik=600, yukseklik=64,
               esik: float | None = None) -> tuple | None:
    """(svg, oranlar) dondurur. oranlar: her nokta icin (x, y) - SVG kutusuna
    gore 0-1 arasi ORAN. SVG preserveAspectRatio="none" ile esnedigi icin bu
    oranlar istemcide dogrudan piksele cevrilebilir (bkz. grafik balonu
    script'i) - viewBox birimlerini JS'e tasimaya gerek kalmaz.

    raporlanmiyor + guncel_zaman: SON kayitta bu alan artik raporlanmiyorsa
    (ornegin tavan - gokyuzu acildigi icin BKN/OVC katmani yok), zaman ekseni
    son GERCEK olcume degil guncel_zaman'a (en son METAR/SPECI'nin zamanina)
    kadar uzatilir; son gercek noktadan bu kenara kadar KESIKLI, ICI BOS bir
    "veri yok" cizgisi cizilir. Boylece eksenin sag ucu da (bkz. _grafik_blogu
    'bitis' etiketi) hala eski olcum saatinde ('04:50' gibi) takili
    KALMAZ - "su an"a kadar geldigini ama deger tasimadigini gosterir."""
    if len(noktalar) < 2:
        return None
    degerler = [v for _, v in noktalar]
    v_min, v_max = _dikey_olcek(degerler)

    t0 = noktalar[0][0]
    t1 = noktalar[-1][0]
    uzatildi = bool(raporlanmiyor and guncel_zaman and guncel_zaman > t1)
    if uzatildi:
        t1 = guncel_zaman
    t_araligi = (t1 - t0).total_seconds() or 1

    def x(z):
        return 4 + (genislik - 8) * ((z - t0).total_seconds() / t_araligi)

    def y(v):
        return yukseklik - 4 - (yukseklik - 8) * ((v - v_min) / (v_max - v_min))

    yol = " ".join(f'{"M" if i == 0 else "L"}{x(z):.1f},{y(v):.1f}'
                    for i, (z, v) in enumerate(noktalar))
    son_x, son_y = x(noktalar[-1][0]), y(noktalar[-1][1])

    # ESIK CIZGISI - yalnizca CIZILEN ARALIGA DUSUYORSA. Dusmeyeni
    # zorla gostermek y eksenini esnetirdi, yani veriyi carpitirdi;
    # ekseni bozmaktansa cizgiyi hic cizmemek dogru.
    esik_svg = ""
    esik_oran = _esik_orani(degerler, esik, yukseklik)
    if esik_oran is not None:
        ey = esik_oran * yukseklik
        esik_svg = (
            f'<line class="grafik-esik" x1="4" y1="{ey:.1f}" '
            f'x2="{genislik - 4}" y2="{ey:.1f}"/>')

    # GRADYAN DOLGU - cizginin altini kapatir. Dekoratif degil: cizginin
    # HANGI TARAFININ "asagi" oldugunu gosterir ve kucuk yukseklikte
    # egilimin yonunu okumayi kolaylastirir. Kimlik yine cizgide.
    kimlik = f"gd{abs(hash((genislik, yukseklik, len(noktalar)))) % 100000}"
    dolgu_yolu = (yol + f" L{son_x:.1f},{yukseklik} L{x(noktalar[0][0]):.1f},"
                        f"{yukseklik} Z")
    dolgu = (f'<defs><linearGradient id="{kimlik}" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0%" stop-color="{renk}" stop-opacity=".22"/>'
             f'<stop offset="100%" stop-color="{renk}" stop-opacity="0"/>'
             f'</linearGradient></defs>'
             f'<path d="{dolgu_yolu}" fill="url(#{kimlik})" stroke="none"/>')

    oranlar = [(x(z) / genislik, y(v) / yukseklik) for z, v in noktalar]

    bosluk_svg = ""
    if uzatildi:
        kenar_x = x(t1)
        # CIZGI DEVAM ETMIYOR. Ilk surumde son olcumun HIZASINDA yatay
        # kesikli bir cizgi ciziliyordu; bu, degerin surdugu izlenimini
        # veriyordu - "tavan 3500 ft'te sabit" diye okunuyordu, oysa o
        # olcumden beri tavan hic raporlanmadi. Artik o zaman araligi
        # BOS: sinir cizgisiyle ayrilmis, icinde veri olmayan bir alan.
        bosluk_svg = (
            f'<rect class="grafik-bosluk" x="{son_x:.1f}" y="0" '
            f'width="{max(0.0, kenar_x - son_x):.1f}" height="{yukseklik}"/>'
            f'<line class="grafik-sinir" x1="{son_x:.1f}" y1="0" '
            f'x2="{son_x:.1f}" y2="{yukseklik}"/>')
        nokta_svg = (f'<circle cx="{son_x:.1f}" cy="{son_y:.1f}" r="4" '
                     f'fill="none" stroke="{renk}" stroke-width="2"/>')
    else:
        nokta_svg = f'<circle cx="{son_x:.1f}" cy="{son_y:.1f}" r="3" fill="{renk}"/>'

    svg = (f'<svg viewBox="0 0 {genislik} {yukseklik}" class="grafik" '
           f'preserveAspectRatio="none">'
           f"{dolgu}{bosluk_svg}{esik_svg}"
           f'<path d="{yol}" fill="none" stroke="{renk}" stroke-width="2" '
           f'stroke-linejoin="round" stroke-linecap="round"/>'
           f'{nokta_svg}</svg>')
    return svg, oranlar


def _en_son_kayit(gecmis: list) -> dict | None:
    """gecmis icindeki ZAMANA gore en yeni kaydi dondurur (liste zaten
    genelde kronolojik ama garanti degil - ayristirma sirasinda bozuk
    'zaman' alani olan kayitlar atlanir)."""
    en_son, en_son_zaman = None, None
    for g in gecmis:
        try:
            z = datetime.fromisoformat(g["zaman"])
        except (KeyError, ValueError, TypeError):
            continue
        if en_son_zaman is None or z > en_son_zaman:
            en_son, en_son_zaman = g, z
    return en_son


def _grafik_blogu(alan: str, baslik: str, birim: str,
                   gecmis: list, simdi: datetime, guncel: dict | None,
                   yokluk: str | None = None) -> str:
    noktalar = _grafik_verisi(gecmis, alan, simdi)
    # guncel: gecmis'teki EN YENI kayit (zamana gore, tipi ne olursa olsun).
    # Bu kayitta alan yoksa/None ise ("tavan" icin tipik ornek: gokyuzu
    # acik, BKN/OVC katmani yok) grafik en son ne zaman GERCEKTEN olculdugu
    # ile "su an raporlanmiyor" durumunu AYRI gostermeli - aksi halde
    # kullanici eski son_deger'i (ornegin "3000 ft") sanki hala guncelmis
    # gibi okur (bkz. bug raporu: tavan grafigi eski BKN olcumunde donmus
    # gorunuyordu, oysa gokyuzu o zamandan beri acikti).
    raporlanmiyor = guncel is not None and guncel.get(alan) is None
    guncel_zaman = None
    if guncel is not None:
        try:
            guncel_zaman = datetime.fromisoformat(guncel["zaman"])
        except (KeyError, ValueError, TypeError):
            guncel_zaman = None
    # TAVAN icin RED esigi: RENK_DURUMLARI'nin son satirinin altina
    # dusmek RED demek. Tablodan geliyor, uydurulmuyor. Diger alanlarin
    # (ruzgar/QNH/sicaklik) boyle tek degiskenli bir esigi YOK, o yuzden
    # onlara cizgi cizilmiyor.
    esik = pist.RENK_DURUMLARI[-1][1] if alan == "tavan" else None
    cizim = _svg_cizgi(noktalar, "currentColor", raporlanmiyor=raporlanmiyor,
                       esik=esik, guncel_zaman=guncel_zaman)
    if not cizim:
        return ""
    svg, oranlar = cizim
    son_deger = noktalar[-1][1]
    baslangic = noktalar[0][0].astimezone(YEREL_TZ)
    # raporlanmiyor iken eksenin sag ucu SON GERCEK olcume degil, en son
    # METAR/SPECI'nin zamanina (guncel_zaman) kadar uzatilir - aksi halde
    # "bitis" etiketi eski olcum saatinde ('04:50' gibi) takili kalirdi.
    bitis_zaman = (guncel_zaman if (raporlanmiyor and guncel_zaman
                                    and guncel_zaman > noktalar[-1][0])
                   else noktalar[-1][0])
    bitis = bitis_zaman.astimezone(YEREL_TZ)

    # Imlecin/parmagin altindaki noktayi bulabilmek icin nokta koordinatlari
    # ve okunabilir metinleri data- niteligine gomulur (istemcide ayrica bir
    # istek YAPILMAZ - sayfa zaten statik uretiliyor).
    nokta_verisi = [
        {"x": round(xo, 4), "y": round(yo, 4),
         "s": f"{z.astimezone(YEREL_TZ):%H:%M}", "d": f"{v:.0f} {birim}"}
        for (xo, yo), (z, v) in zip(oranlar, noktalar)
    ]

    if raporlanmiyor:
        # "raporlanmiyor" ile "yok" AYNI SEY DEGIL ve kullanici icin fark
        # buyuk: birincisi "bilgi gelmiyor", ikincisi "ortada tavan yok".
        # Hangisi oldugunu SOYLEYEBILIYORSAK soyluyoruz (bkz.
        # _tavan_yoklugu); soyleyemiyorsak notr kelimede kaliyoruz.
        if yokluk == "yok":
            rozet, kuyruk = "tavan yok", "o zamandan beri 5/8+ katman (BKN/OVC/VV) yok"
        elif yokluk == "yukseklik_yok":
            rozet, kuyruk = ("yükseklik bildirilmedi",
                             "katman var ama yüksekliği bildirilmedi (BKN///)")
        else:
            rozet, kuyruk = "raporlanmıyor", "o zamandan beri raporlanmıyor"
        son_etiket = f'<span class="grafik-son grafik-son-yok">{rozet}</span>'
        durum_notu = (
            f'<div class="grafik-durum-notu">Son ölçüm: {son_deger:.0f} '
            f'{html.escape(birim)} · {_zaman_metni(noktalar[-1][0])} — {kuyruk}.'
            f'</div>'
        )
    else:
        son_etiket = f'<span class="grafik-son">{son_deger:.0f} {html.escape(birim)}</span>'
        durum_notu = ""

    # ESIK ETIKETI - cizginin USTUNDE, SOL kenarda. Sag uc "su anki deger"
    # noktasinin yeri; etiketi oraya koymak (ilk surum) yaziyi cizginin
    # uzerine bindiriyordu (ekran goruntusuyle gorundu).
    esik_oran = _esik_orani([v for _, v in noktalar], esik)
    esik_etiketi = ""
    if esik_oran is not None:
        esik_etiketi = (f'<span class="grafik-esik-ad" '
                        f'style="top:{esik_oran * 100:.1f}%">RED '
                        f'{esik:.0f} {html.escape(birim)}</span>')

    return (
        f'<div class="grafik-kutu" '
        f'data-noktalar="{html.escape(json.dumps(nokta_verisi, ensure_ascii=False))}">'
        f'<div class="grafik-baslik"><span>{html.escape(baslik)}</span>'
        f'{son_etiket}</div>'
        f'<div class="grafik-sarmal">{svg}{esik_etiketi}'
        f'<div class="grafik-imlec" hidden></div>'
        f'<div class="grafik-nokta" hidden></div>'
        f'<div class="grafik-balon" hidden></div></div>'
        f'<div class="grafik-eksen"><span>{baslangic:%H:%M}</span>'
        f'<span>{bitis:%H:%M}</span></div>{durum_notu}</div>'
    )


def _ayni_gozlem(kayit: dict | None, zaman: datetime | None) -> bool:
    """Olcum gecmisindeki kayit ile guncel raporun AYNI gozlem olup
    olmadigi (dakika hassasiyetinde)."""
    if kayit is None or zaman is None:
        return False
    try:
        k = datetime.fromisoformat(kayit["zaman"])
    except (KeyError, ValueError, TypeError):
        return False
    return abs((k - zaman).total_seconds()) <= 60


def _trend_bolumu(gecmis: list, tavan_yoklugu: str | None = None,
                  gozlem_zamani: datetime | None = None) -> str:
    if not gecmis:
        return ""
    simdi = datetime.now(timezone.utc)
    guncel = _en_son_kayit(gecmis)
    # tavan_yoklugu GUNCEL RAPORDAN cikarildi; grafikteki "raporlanmiyor"
    # ise olcum gecmisinin EN SON KAYDINA bakiyor. Normalde ayni gozlem,
    # ama ayni degillerse (gecmis bir tur geride kalmissa) rapordan gelen
    # cumleyi baska bir gozlemin uzerine yazmis olurduk - o yuzden
    # eslesmiyorsa notr kelimeye donuluyor.
    if tavan_yoklugu and not _ayni_gozlem(guncel, gozlem_zamani):
        tavan_yoklugu = None
    bloklar = [_grafik_blogu(alan, baslik, birim, gecmis, simdi, guncel,
                             tavan_yoklugu if alan == "tavan" else None)
               for alan, baslik, birim in GRAFIKLER]
    bloklar = [b for b in bloklar if b]
    if not bloklar:
        return ""
    # Katli gelir - 563 px'lik dort grafik, "su an ne oluyor" sorusunun
    # cevabi degil; bakmak isteyince aciliyor. Basliktaki rozet, kapaliyken
    # de son degerleri gosterir ki bolum UNUTULMASIN.
    # Rozet SADECE degerler - basliklari da yazinca uc satira tasiyordu ve
    # ozet rozeti okunabilirligini kaybediyordu. Hemen altindaki grafikler
    # zaten hangi degerin ne oldugunu adiyla yaziyor.
    # ROZET ARTIK SAYI DEGIL, SAYIM. Eskiden kapali baslik "1kt · 1020hPa
    # · 13°C" yaziyordu ve bu bolum METAR kartinin USTUNDEYDI. Kotu havada
    # sonuc su oluyordu:
    #     Trend · son 6 saat   1kt · 1020hPa · 13°C   <- 6 SAATLIK GECMIS
    #     METAR                090°/12G22 · Q1008     <- SU AN
    # Ust satir alttakiyle CELISIYOR ve daha yukarida duruyordu; "Trend"
    # kelimesi disinda bunun gecmis oldugunu soyleyen hicbir sey yoktu.
    # Simdi rozet yalnizca kac olcum oldugunu soyluyor - guncel deger
    # sanilabilecek hicbir sayi yok.
    n = len([g for g in gecmis if g.get("zaman")])
    rozet = (f'<span class="kat-rozet">{len(bloklar)} grafik · {n} ölçüm</span>'
             if n else "")
    return ('<div class="kart"><details class="kat kat-kart">'
            f'<summary>Geçmiş eğilim · son 6 saat {rozet}</summary>'
            f'<div class="grafik-grid">{"".join(bloklar)}</div>'
            "</details></div>")


def _lvo_dokuman_referans_html() -> str:
    """LVO REFERENCE panelinin A) DOCUMENT REFERENCE bolumu - TAMAMEN
    ltfj_lvo_referans.py'deki STATIK veriden uretilir, calisma zamani
    verisine (METAR/NOTAM/AWOS/ATIS) HICBIR bagimliligi yoktur. Bu
    fonksiyon hicbir karsilastirma/karar YAPMAZ, sadece dokuman metnini
    tabloya/listeye dokup HTML'e cevirir."""
    pist_satirlari = "".join(
        f"<tr><td>{html.escape(p['pist'])}</td><td>{html.escape(p['kategori'])}</td>"
        f"<td>{html.escape(p['inis_rvr'])}</td><td>{html.escape(p['kalkis_rvr'])}</td>"
        f"<td>{html.escape(p['aciklama'])}</td></tr>"
        for p in lvo.PIST_TABLOSU
    )
    esik_satirlari = "".join(
        '<div class="lvo-esik-satir"><span>RVR &lt; '
        f'<span class="lvo-esik-deger">{e["esik_altinda_m"]} m</span> — '
        f'{html.escape(e["safha"])}'
        f'<span class="lvo-esik-kaynak">{html.escape(e["kaynak_madde"])}'
        + (f' · {html.escape(e["not"])}' if e["not"] else "")
        + "</span></span></div>"
        for e in lvo.RVR_ESIKLERI
    )
    kategori_satirlari = "".join(
        f"<tr><td>{html.escape(k['kategori'])}</td><td>{html.escape(k['rvr'])}</td>"
        f"<td>{html.escape(k['dh'])}</td></tr>"
        for k in lvo.KATEGORI_TANIMLARI
    )
    bulut_satirlari = "".join(
        '<div class="lvo-esik-satir"><span>'
        f'{html.escape(b["safha"])} — {html.escape(b["esik"])}'
        f'<span class="lvo-esik-kaynak">{html.escape(b["kaynak_madde"])}</span>'
        "</span></div>"
        for b in lvo.BULUT_TABANI_ESIKLERI
    )
    not_maddeleri = "".join(f"<li>{html.escape(n)}</li>" for n in lvo.UYARI_NOTLARI)

    return (
        # KATLANIR, VARSAYILAN KAPALI. Bu 3838 baytlik STATIK bir
        # dokuman ozeti - her acilista okunan degil, gerektiginde
        # basvurulan bir sey. Acikken panelin %90'ini kapliyor ve
        # operasyonel kisimlari (farkindalik notlari, AWOS durumu)
        # ekrandan itiyordu.
        #
        # BU, #67'DE KALDIRILAN AC/KAPA'NIN GERI DONUSU DEGIL: o,
        # LVO panelinin TAMAMINI gizliyordu ve sekmeyle mukerrerdi.
        # Buradaki yalnizca panelin ICINDEKI statik referansi katliyor -
        # sekme "LVO'yu goster", bu "kural metnini goster".
        '<details class="kat kat-lvo-referans"><summary>'
        'D) Doküman Referansı '
        f'<span class="lvo-provenance">{html.escape(lvo.DOKUMAN["etiket"])}</span>'
        '</summary>'
        f'<div style="font-size:var(--f2);">{html.escape(lvo.DOKUMAN["baslik"])}<br>'
        f'<b>{html.escape(lvo.DOKUMAN["dok_no"])} {html.escape(lvo.DOKUMAN["rev_no"])} — '
        f'{html.escape(lvo.DOKUMAN["rev_tarihi"])}</b></div>'
        '<table class="lvo-tablo"><thead><tr><th>Pist</th><th>Kategori</th>'
        "<th>İniş RVR (m)</th><th>Kalkış RVR (m)</th><th>Açıklama</th></tr></thead>"
        f"<tbody>{pist_satirlari}</tbody></table>"
        '<table class="lvo-tablo"><thead><tr><th>Kategori</th><th>RVR</th><th>DH</th></tr></thead>'
        f"<tbody>{kategori_satirlari}</tbody></table>"
        '<div style="font-size:var(--f2);font-weight:600;margin-top:.4rem;">'
        "RVR eşikleri (madde 6.1.ee)</div>"
        f'<div class="lvo-esik-liste">{esik_satirlari}</div>'
        '<div style="font-size:var(--f2);font-weight:600;margin-top:.4rem;">'
        "Bulut tabanı (ceiling) eşikleri — RVR'dan bağımsız, paralel tetikleyici</div>"
        f'<div class="lvo-esik-liste">{bulut_satirlari}</div>'
        f'<div style="font-size:var(--f2);margin-top:.4rem;">{html.escape(lvo.BULUT_PILOT_RAPORU_ISTISNASI)}</div>'
        f'<ul class="lvo-not-listesi">{not_maddeleri}</ul>'
        "</details>"
    )


def _spread_egilimi(gecmis: list, simdi: datetime, saat: int = 3) -> float | None:
    """Son 'saat' saatteki spread (sicaklik - cig noktasi) degisimi.

    Eski gecmis kayitlarinda cig_noktasi YOKTUR (alan sonradan eklendi);
    o durumda None doner ve model bu ozellik olmadan calisir - olculdu,
    holdout AP degismiyor."""
    if not gecmis:
        return None

    def spread(g):
        s, c = g.get("sicaklik"), g.get("cig_noktasi")
        return None if s is None or c is None else s - c

    simdiki, hedef_zaman = None, simdi - timedelta(hours=saat)
    en_yakin, en_kucuk_fark = None, timedelta(minutes=45)
    for g in gecmis:
        try:
            z = datetime.fromisoformat(g["zaman"])
        except (KeyError, ValueError, TypeError):
            continue
        if spread(g) is None:
            continue
        if simdiki is None or z > simdiki[0]:
            simdiki = (z, spread(g))
        fark = abs(z - hedef_zaman)
        if fark < en_kucuk_fark:
            en_yakin, en_kucuk_fark = spread(g), fark
    if simdiki is None or en_yakin is None:
        return None
    return simdiki[1] - en_yakin


def _sis_olasiligi_hesapla(guncel_cozum: dict | None, gecmis: list,
                           simdi: datetime) -> float | None:
    """sis_olasilik.olasilik()'i hesaplamak icin gerekli tum turetilmis
    girdileri (ruzgar bileseni, spread, saat, egilim) toplar - hem sis
    kartinda (_sis_olasiligi_html) hem LVO farkindalik panelindeki dis
    kaynak notunda (farkindalik.tavan_dis_kaynak_notu, AYNI METAR anindan
    TUTARLI bir deger kullansin diye) YENIDEN kullanilir."""
    if not guncel_cozum:
        return None
    ruzgar_k = sis_olasilik.ruzgar_kuzey_bileseni(
        guncel_cozum.get("ruzgar_yon"), guncel_cozum.get("ruzgar_hiz"))
    sicaklik, cig = guncel_cozum.get("sicaklik"), guncel_cozum.get("cig_noktasi")
    return sis_olasilik.olasilik(
        spread=None if sicaklik is None or cig is None else sicaklik - cig,
        gorus=guncel_cozum.get("gorus"),
        saat=simdi.astimezone(timezone.utc).hour,
        ruzgar_kuzey=ruzgar_k,
        spread_egilim_3=_spread_egilimi(gecmis, simdi))


def _sis_olasilik_rozeti(guncel_cozum: dict | None, gecmis: list,
                         simdi: datetime) -> str:
    """Sekme çubuğundaki kısa olasılık rozeti - kartın kendisiyle AYNI
    hesabı kullanır (ayrı bir sayı üretmez).

    TAM SAYIYA yuvarlanır, kart ise ondalığı gösterir. Sebep iki yönlü:
    (1) bir sekme rozetinde "%27.8" sahte hassasiyettir - rozet "bakmalı
    mıyım?" sorusunu yanıtlar, kesin değeri panel verir; (2) ondalık
    basamak 360px'te çubuğu taşırıyor ve NOTAM sekmesini kesiyordu."""
    p = _sis_olasiligi_hesapla(guncel_cozum, gecmis, simdi)
    return "" if p is None else f"{p * 100:.0f}"


def _sis_olasiligi_html(guncel_cozum: dict | None, gecmis: list,
                        simdi: datetime) -> str:
    """Dusuk gorus (< 1000 m) olasiligi karti (tarihsel adi: sis olasiligi).

    Hedef ozellik.py'deki etiket: gorus < 1000 m VEYA alani kaplayan FG -
    kar kaynakli dusuk gorus da dahil. Teknik adi "LTFJ dusuk gorus/FG olayi".

    ltfj_pist.sis_riski()'nin YERINE GECMEZ - ayri, bagimsiz bir gostergedir.
    Katsayilar dondurulmus modelden gelir (bkz. ltfj_sis_olasilik)."""
    if not guncel_cozum:
        return ""
    p = _sis_olasiligi_hesapla(guncel_cozum, gecmis, simdi)
    if p is None:
        return ""
    ruzgar_k = sis_olasilik.ruzgar_kuzey_bileseni(
        guncel_cozum.get("ruzgar_yon"), guncel_cozum.get("ruzgar_hiz"))
    sicaklik, cig = guncel_cozum.get("sicaklik"), guncel_cozum.get("cig_noktasi")

    yuzde = f"{100 * p:.0f}" if p >= 0.01 else f"{100 * p:.1f}"
    # Ciplak bir yuzde ("%3" gibi) tek basina "bu yuksek mi dusuk mu"
    # sorusuna cevap vermiyor - taban orana (egitim verisindeki uzun donem
    # ortalama) gore kac kat oldugunu da gosteriyoruz. Bant sinirlari (2x,
    # 5x) olcume bakilarak SONRADAN degil, ONCEDEN (a priori) secildi -
    # ltfj_lvo_farkindalik.TAVAN_KAT_ESIGI'deki ayni disiplin.
    kat = p / sis_olasilik.TABAN_ORAN
    if kat < 2:
        bant_sinif, bant_metin = "dusuk", "düşük"
    elif kat < 5:
        bant_sinif, bant_metin = "orta", "orta"
    else:
        bant_sinif, bant_metin = "yuksek", "yüksek"
    taban_yuzde = f"{100 * sis_olasilik.TABAN_ORAN:.1f}"
    # "kat" 1'e yakinken ("X kat yuksek/dusuk" 1 veya 0 gibi anlamsiz bir
    # sayiya yuvarlanabilir) duz "kac kat" yerine "bu seviyeye yakin"
    # denir; belirgin sekilde altindaysa TERS oran ("kac kat dusuk")
    # gosterilir - "0 kat dusuk" gibi anlamsiz bir ifade cikmasin diye.
    if kat >= 1.5:
        kiyas_ifade = f"şu an bundan yaklaşık {kat:.0f} kat yüksek"
    elif kat <= 0.67:
        kiyas_ifade = f"şu an bundan yaklaşık {1 / kat:.0f} kat düşük"
    else:
        kiyas_ifade = "şu an bu seviyeye yakın"

    # A cok dusukken (< A_UST_SINIR) gorussuz Model B'nin o bant icindeki
    # KENDI sirasi (dusuk/orta/yuksek) ayrica gosterilir - ab_karsilastirma.py
    # ile olculdu: bu aralikta B'nin ayrimi gercek (buyuk orneklem, gun-bazli
    # CI'lar ortusmuyor), ama A>=%2 iken kanit yok, o yuzden orada HICBIR
    # SEY gosterilmez (bkz. ltfj_sis_olasilik_b.A_UST_SINIR).
    p_b = sis_olasilik_b.olasilik(
        spread=None if sicaklik is None or cig is None else sicaklik - cig,
        sicaklik=sicaklik,
        saat=simdi.astimezone(timezone.utc).hour,
        ruzgar_kuzey=ruzgar_k,
        spread_egilim_3=_spread_egilimi(gecmis, simdi))
    b_tertil = sis_olasilik_b.tertil(p, p_b)
    ek_gosterge_html = ""
    if b_tertil is not None:
        b_sinif = {"düşük": "dusuk", "orta": "orta", "yüksek": "yuksek"}[b_tertil]
        ek_gosterge_html = (
            '<div class="sis-olasilik-ek">Düşük görüş eğilimi: '
            f'<span class="sis-olasilik-bant {b_sinif}">{b_tertil}</span>'
            '<div class="sis-olasilik-ek-not">Görüş henüz düşmemiş olsa da, '
            'mevcut nem, rüzgâr ve sıcaklık koşullarının görüş düşüşüne ne '
            'kadar uygun olduğunu gösterir. Resmî bir tahmin değildir, '
            'sadece ek bir ipucudur.</div></div>'
        )

    return (
        '<div class="alt-bolum sis-olasilik">'
        '<div class="basrow"><span class="tip">Düşük görüş (&lt; 1000 m) olasılığı</span>'
        '<span class="lvo-provenance">İSTATİSTİKSEL</span></div>'
        '<div class="sis-olasilik-ust">'
        f'<span class="sis-olasilik-deger">%{yuzde}</span>'
        f'<span class="sis-olasilik-bant {bant_sinif}">{bant_metin}</span>'
        '</div>'
        # Hedef "gorus < 1000 m VEYA alani kaplayan FG" (ozellik.py) - gorusu
        # dusuren olayin cinsine bakilmaz, kar da dahil. Karttaki adla
        # birlikte bu cumle modelin GERCEK hedefini anlatir.
        f'<div class="sis-olasilik-alt">Önümüzdeki {sis_olasilik.HEDEF_UFUK_SAAT} saat '
        f'içinde görüşün {sis_olasilik.HEDEF_GORUS_M} m altına düşmesi veya '
        'meydanı kaplayan sis (FG) bildirilmesi olasılığı. Kaynağı sis, '
        'parçalı sis ya da kar olabilir.</div>'
        f'<div class="sis-olasilik-kiyas">Normalde bu oran ortalama %{taban_yuzde} '
        f'civarındadır — {kiyas_ifade}.</div>'
        f'{ek_gosterge_html}'
        '<div class="sis-olasilik-not">LTFJ\'nin 2011–2023 METAR arşivinden '
        'öğrenilmiş istatistiksel bir tahmindir; resmî tahmin değildir ve '
        'TAF\'ın yerine geçmez.</div>'
        '<button type="button" id="sis-model-diyagram-btn" '
        'class="sis-olasilik-diyagram-btn">İki modelin bağlantısını gör</button>'
        '</div>'
        '<div id="sis-model-modal" class="modal-ortu" hidden>'
        '<div class="modal-kutu modal-kutu-genis">'
        '<h3>Karttaki olasılık ve ek gösterge nasıl bağlantılı?</h3>'
        '<img src="sis_model_baglantisi.png" loading="lazy" '
        'alt="Canlı Model A ile dondurulmuş ek gösterge Model B\'nin girdi, çıktı ve birbirine bağlandığı yeri '
        'gösteren diyagram">'
        '<div class="modal-butonlar">'
        '<button type="button" id="sis-model-modal-kapat">Kapat</button>'
        '</div></div></div>'
    )


def _lvo_farkindalik_html(guncel_cozum: dict | None, taf_tavan: int | None,
                          gecmis: list, simdi: datetime) -> str:
    # gecmis/simdi artik KULLANILMIYOR (istatistik notlari tasindi) ama
    # imza korunuyor: cagiran taraf tek yerde ve degistirmek bu PR'in
    # kapsamini gereksiz genisletirdi.
    """LVO REFERENCE panelinin basindaki 'Farkindalik Notlari' alt bolumu -
    METAR (guncel_cozum) ve TAF'in (taf_tavan) KENDI gorus/tavan degerlerini
    ltfj_lvo_farkindalik ile GAYRI RESMI, hedge'li notlara cevirir. AWOS RVR
    tabanli notlar BURADA YOK - o veri sadece Firebase'de (istemci
    tarafinda) var; JS tarafinda (LVO script'i, ayni RVR_ESIKLERI JSON'unu
    kullanarak) AYRICA uretilip #lvo-fark-rvr-liste'ye eklenir.

    Ucuncu not (tavan_istatistik_notu) esik karsilastirmasi DEGIL, arsivden
    ogrenilmis GORELI bir orandir - kat cinsinden, cunku tablonun seviyesi
    donemler arasi kayiyor (bkz. ltfj_tavan_tablosu). Dorduncu not
    (tavan_dis_kaynak_notu) AYNI dilde ama cok degiskenli, dis kaynak
    destekli (holdout'ta dogrulanmis) modelden gelir - gecmis/simdi, sis
    olasiligini (sis kartiyla AYNI hesap - bkz. _sis_olasiligi_hesapla)
    turetmek icin gerekli."""
    # ISTATISTIK NOTLARI BURADAN TASINDI (bkz. _istatistik_html):
    # tavan_istatistik_notu ve tavan_dis_kaynak_notu arsivden ogrenilmis
    # GORELI oranlar; bu panel ise ESIK KARSILASTIRMASI yapiyor (METAR/TAF
    # degeri su esigin altinda mi). Iki farkli soru ayni listede durunca
    # "bu bir olcum mu, istatistik mi" ayrimi kayboluyordu. Artik tum
    # arsiv-tabanli istatistik tek bir "İstatistik" basligi altinda.
    notlar = [n for n in (farkindalik.metar_tavan_notu(guncel_cozum),
                          farkindalik.taf_tavan_notu(taf_tavan)) if n]
    sabit_html = "".join(f"<li>{html.escape(n)}</li>" for n in notlar)
    return (
        f'<ul class="lvo-not-listesi" id="lvo-fark-metar-taf">{sabit_html}</ul>'
        '<ul class="lvo-not-listesi" id="lvo-fark-rvr-liste"></ul>'
        '<div class="notam-bos" id="lvo-fark-bos">Şu an için dikkat çeken bir eşik yok.</div>'
    )


def _vfr_sekmesi_html(guncel_cozum: dict | None) -> str:
    """Sayfa kenarindaki kucuk VFR gosterge sekmesi - EN SON METAR/SPECI'nin
    zaten cozulmus (metar_coz) gorus/tavan degerlerini ltfj_vfr.vfr_degerlendir()
    ile karsilastirip yesil/kirmizi/bilinmiyor olarak gosterir; tiklaninca
    sebepleri listeleyen kucuk bir panel acilir (bkz. ltfj_vfr.py basindaki
    not - bu, kullanicinin acikca istedigi TEK otomatik karsilastirmadir)."""
    if guncel_cozum is None:
        sonuc = {"vfr": None, "sebepler": ["Son METAR/SPECI bulunamadı — değerlendirme yapılamıyor."]}
    else:
        sonuc = vfr.vfr_degerlendir(guncel_cozum)

    if sonuc["vfr"] is True:
        sinif, nokta, baslik = "vfr-yesil", "yesil", "VFR şartları sağlanıyor"
    elif sonuc["vfr"] is False:
        sinif, nokta, baslik = "vfr-kirmizi", "kirmizi", "VFR şartları sağlanmıyor"
    else:
        sinif, nokta, baslik = "vfr-bilinmiyor", "bilinmiyor", "VFR değerlendirilemiyor"

    sebep_html = "".join(f"<li>{html.escape(s)}</li>" for s in sonuc["sebepler"]) or (
        "<li>Görüş ve tavan eşiklerin üzerinde.</li>")

    return (
        f'<button type="button" id="vfr-sekme" class="vfr-sekme {sinif}" '
        f'aria-label="VFR durumu" title="{html.escape(baslik)}">VFR</button>'
        '<div id="vfr-panel-ortu" class="vfr-panel-ortu" hidden>'
        '<div class="vfr-panel">'
        '<div class="vfr-panel-ust">'
        f'<h3><span class="vfr-nokta {nokta}"></span>{html.escape(baslik)}</h3>'
        # f-STRING OLMAK ZORUNDA: bu satir duz string oldugu icin
        # {ikon_kapat} sayfaya OLDUGU GIBI basiliyordu - VFR panelini
        # acan kullanici kapatma ikonu yerine "{ikon_kapat}" yazisi
        # goruyordu. Sayfa govdesi .format() ile kuruluyor ama format
        # DEGERLERIN ICINE GIRMEZ, bu HTML de bir deger olarak
        # gecirildigi icin yer tutucu hic doldurulmuyordu.
        f'<button type="button" id="vfr-panel-kapat" class="atc-panel-kapat" '
        f'aria-label="Kapat">{ikon("kapat")}</button>'
        '</div>'
        f'<ul>{sebep_html}</ul>'
        f'<div class="vfr-esik">Eşik: görüş ≥ {vfr.VFR_GORUS_ESIGI_M} m, '
        f'tavan ≥ {vfr.VFR_TAVAN_ESIGI_FT} ft (ICAO Annex 2, Tablo 3-1 — FL100 altı, '
        'CTR/TMA). Bilgi amaçlıdır, resmî VFR/IFR tespiti yerine geçmez.</div>'
        '</div></div>'
    )


def _yorum_html(yorum: str) -> str:
    """Claude'un state.yorum_onbellegi'nde (Telegram ile PAYLAŞILAN onbellek)
    zaten hesaplanmış metnini web icin bicimlendirir - burada YENI bir
    Claude cagrisi YAPILMAZ, sadece mevcut metin okunur."""
    satirlar = []
    for satir in yorum.splitlines():
        satir = satir.strip()
        if not satir:
            continue
        kacis = html.escape(satir)
        m = _ETIKET.match(kacis)
        if m:
            satirlar.append(f"<b>{m.group(1)}:</b> {m.group(2)}")
        elif kacis.startswith("-"):
            satirlar.append("•" + kacis[1:])
        else:
            satirlar.append(kacis)
    return "<br>".join(satirlar)


# --------------------------------------------------- mevcut kosullar karti
# Once bu dort deger duz gri bir CUMLEYE gomuluydu:
#   "Rüzgâr 060° 5kt · görüş 400 m · tavan 200 ft · sis · 13°C · QNH 1019"
# Orada GORUS 400 m (havalimanini kapatan sayi) ile QNH 1019 (rutin bilgi)
# ayni punto ve ayni gri tondaydi. Kontrolor once bu dorde bakiyor.
# Birim artik burada DEGIL _olcu()'de: "10+ km" ile "300 m" ayni alanda
# farkli birim tasiyor, sabit bir birim dizesi bunu anlatamiyordu.
HERO_ALANLAR = (
    ("GÖRÜŞ",  "gorus",   "gorus"),
    ("TAVAN",  "tavan",   "tavan"),
    ("RÜZGÂR", "_ruzgar", "ruzgar_hiz"),
    ("SPREAD", "_spread", "_spread"),
)


def _kivilcim(gecmis: list, alan: str, simdi: datetime) -> str:
    """Metrik altindaki kucuk egilim cizgisi.

    Veri yoksa BOS doner - uydurmaz. gorus alani olcum_gecmisi'ne yeni
    eklendi, o yuzden pencere dolana kadar gorus cizgisi bos kalir."""
    if not alan or not gecmis:
        return ""
    if alan == "_spread":
        gecmis = [dict(g, _spread=round(g["sicaklik"] - g["cig_noktasi"], 1))
                  for g in gecmis
                  if g.get("sicaklik") is not None and g.get("cig_noktasi") is not None]
    noktalar = _grafik_verisi(gecmis, alan, simdi)
    if len(noktalar) < GRAFIK_MIN_NOKTA:
        return ""
    sonuc = _svg_cizgi(noktalar, "currentColor", genislik=100, yukseklik=20)
    if not sonuc:
        return ""
    svg = sonuc[0] if isinstance(sonuc, tuple) else sonuc
    return svg.replace("<svg ", '<svg class="hero-kivilcim" aria-hidden="true" ', 1)


def _tavan_yoklugu(cozum: dict | None) -> str | None:
    """Tavan SAYISI yokken bunun ne demek oldugunu soyleyebiliyor muyuz?

    "yok"            - METAR'da hic BKN/OVC/VV katmani yok. Bu bir tahmin
                       degil, tavanin TANIMI: tavan en alcak 5/8+ katmanin
                       tabanidir; katman yoksa tavan da yoktur.
    "yukseklik_yok"  - Katman VAR ama yuksekligi bildirilmemis (BKN///).
                       Burada "tavan yok" demek YANLIS bir operasyonel
                       ifade olurdu: tavan vardir, yuksekligi bilinmiyor.
    None             - Soyleyemiyoruz (cozum yok, ya da "bulutlar"
                       anahtari hic gelmemis - yani bulut gruplarini
                       gormemisiz demektir; bos LISTE ise gordugumuz ve
                       katman olmadigi anlamina gelir).
    """
    if cozum is None:
        return None
    bulutlar = cozum.get("bulutlar") or []
    katmanlar = [b for b in bulutlar if b.get("ortu") in TAVAN_KATMANLARI]
    if katmanlar:
        # Katman var: sayisi yoksa yuksekligi bildirilmemistir (BKN///).
        return "yukseklik_yok" if all(b.get("ft") is None for b in katmanlar) else None
    # OLUMLU BIR ISARET SART. Bulut grubunun listede olmamasi tek basina
    # "tavan yok" demek DEGIL - bozuk/kirpilmis bir raporda da liste bos
    # kalir (ornek: "LTFJ 231420Z /////KT //// // Q////"). Bu yuzden ya
    # gercekten okunmus bir katman (FEW/SCT) ya da "bulut yok" diyen bir
    # kod (NSC/NCD/SKC/CLR, CAVOK) aranıyor.
    if bulutlar or cozum.get("bulut_yok") or cozum.get("cavok"):
        return "yok"
    return None


def _olcu(cozum: dict, anahtar: str) -> tuple[str, str]:
    """Dort ana olcunun (deger, birim) bicimi - TEK KAYNAK.

    NEDEN TEK KAYNAK: hero ile ozet serit ayni dort olcuyu AYRI AYRI
    biciimlendiriyordu ve ikisi ayni ekranda, 374 piksel arayla,
    BIRBIRINDEN FARKLI konusuyordu:

        olcu    serit          hero
        gorus   "10+ km"       "9999 m"
        tavan   "tavan yok"    "— ft"
        ruzgar  "VRB/1"        "VRB/1 kt"
        spread  "Δ3°"          "3.0 °C"

    Hangisinin dogru oldugu okuyucuya birakilmisti. "9999" zaten
    METAR'in "10 km ve ustu" kodudur; serit onu ceviriyor, hero
    cevirmeden basiyordu.

    Insan dili SECILDI: ham METAR zaten kartin icinde duruyor, burasi
    okunmak icin. "—" yerine "bildirilmedi": 24px'lik bir tire kalin
    yatay bir cubuk olarak ciziliyor ve "ustu cizilmis deger" gibi
    okunuyordu - yokluk ile sifir ayirt edilemiyordu."""
    if anahtar == "gorus":
        m = cozum.get("gorus")
        if m is None:
            return "bildirilmedi", ""
        if m >= 9999:
            return "10+", "km"
        return (f"{m / 1000:g}", "km") if m >= 1000 else (f"{m:g}", "m")
    if anahtar == "tavan":
        t = cozum.get("tavan")
        if t is not None:
            return (f"{t:g}", "ft")
        # "bildirilmedi" ile "yok" AYNI SEY DEGIL. METAR'da hic BKN/OVC
        # katmani yoksa tavan tanim geregi YOKTUR; bunu "bildirilmedi"
        # diye yazmak, bilgi eksikligi varmis gibi okutuyordu. Ama
        # katman varken yuksekligi bildirilmemisse (BKN///) "yok" demek
        # yanlis olur - o durumda "bildirilmedi" dogru kelime.
        return ("yok", "") if _tavan_yoklugu(cozum) == "yok" else ("bildirilmedi", "")
    if anahtar == "_ruzgar":
        yon, hiz = cozum.get("ruzgar_yon"), cozum.get("ruzgar_hiz")
        if hiz is None:
            return "bildirilmedi", ""
        temel = f"{yon:03d}°/{hiz}" if yon is not None else f"VRB/{hiz}"
        # HAMLE HERO'YA GIRIYOR. Oncesinde yalnizca serit ve ham metin
        # tasiyordu: METAR "09012G22KT" iken sayfadaki EN BUYUK yazi
        # "090°/12 kt" diyordu. 12 kt ile 22 kt arasindaki fark bir pist
        # tercihini degistirebilir; ruzgarin operasyonel olarak daha
        # belirleyici yarisi en buyuk yazidan dusurulmustu.
        hamle = cozum.get("ruzgar_hamle")
        return (temel + (f"G{hamle}" if hamle else ""), "kt")
    if anahtar == "_spread":
        t, c = cozum.get("sicaklik"), cozum.get("cig_noktasi")
        return ("bildirilmedi", "") if None in (t, c) else (f"{t - c:.1f}", "°C")
    v = cozum.get(anahtar)
    return ("bildirilmedi", "") if v is None else (f"{v:g}", "")


def _hero_deger(cozum: dict, anahtar: str) -> str:
    """Geriye uyumluluk: eski cagiranlar icin tek dize."""
    deger, birim = _olcu(cozum, anahtar)
    return f"{deger} {birim}".strip()


def _olcu_bant_kodu(cozum: dict, anahtar: str) -> str | None:
    """Tek bir olcunun renk bandi KODU ("BLU".."RED") - ya da None.

    ltfj_pist.RENK_DURUMLARI'nin AYNI satirlari, yalnizca tek degiskene
    uygulanarak: gorus icin gorus sutunu, tavan icin tavan sutunu. Sayfa
    KENDI esigini tanimlamiyor."""
    if anahtar == "gorus":
        v, sutun = cozum.get("gorus"), 2
    elif anahtar == "tavan":
        v, sutun = cozum.get("tavan"), 1
    else:
        return None
    if v is None:
        return None
    for kod, min_tavan, min_gorus in pist.RENK_DURUMLARI:
        if v >= (min_tavan if sutun == 1 else min_gorus):
            return kod
    return "RED"


# BANT GÖSTERGESİ (_bant_gostergesi_html, BANT_SIRASI) KALDIRILDI.
# Altı kutuluk o şerit değerin BLU..RED ölçeğinde nerede durduğunu
# gösteriyordu ve yanında kodun adını yazıyordu. Ölçeğin adı gidince
# geriye efsanesi olmayan altı kutu kalırdı - okuyana hiçbir şey
# söylemeyen bir süs. Eşiğe ne kadar kaldığı bilgisi ise sayının
# kendi vurgusunda (bkz. _olcu_bandi) duruyor.


def _olcu_bandi(cozum: dict, anahtar: str) -> str:
    """Tek bir olcunun renk bandi - YENI ESIK UYDURULMUYOR.

    ltfj_pist.RENK_DURUMLARI'nin AYNISI kullaniliyor, yalnizca tek
    degiskene uygulanarak: gorus icin gorus sutunu, tavan icin tavan
    sutunu. Yani sayfa "kendi esigini" tanimlamiyor; Telegram'in ve
    rozetin kullandigi tablonun ayni satirlarina bakiyor.

    NEDEN GEREKLI (olculdu): RED durumunda hero'nun dort sayisi BLU
    durumuyla birebir ayni biciimde ciziliyordu - 28px, ayni siyah,
    ayni agirlik. "300 m" ile "9999 m" gorsel olarak ayirt
    edilemiyordu; sinyalin tamami sayilarin ETRAFINDAKI rozette ve
    kutudaydi. Goz once rakama gider.

    Doner: "" (vurgu yok) | "dikkat" | "uyari"."""
    kod = _olcu_bant_kodu(cozum, anahtar)
    if kod is None:
        return ""
    if kod == "RED":
        return "uyari"
    return "dikkat" if kod in ("YLO", "AMB") else ""


def _hero_html(cozum: dict, gecmis: list, simdi: datetime) -> str:
    hucreler = []
    for etiket, anahtar, trend in HERO_ALANLAR:
        deger, birim = _olcu(cozum, anahtar)
        kiv = _kivilcim(gecmis, trend, simdi)
        band = _olcu_bandi(cozum, anahtar)
        # RENK TEK TASIYICI DEGIL: bandla birlikte etiketin yanina metin
        # bir isaret de giriyor. Renk korlugunde, tek renkli baskida ve
        # gunes altinda renk tek basina guvenilmez.
        band_isareti = ("" if not band else
                        f'<span class="hero-band-etiket">'
                        f'{"eşik altı" if band == "uyari" else "sınırlı"}</span>')
        # "bildirilmedi" bir SAYI DEGIL: 28px'te sayfanin en buyuk yazisi
        # oluyordu ve yoklugu, olculen bir degerden daha baskin gosteriyordu.
        sinif = "hero-deger" + (" hero-deger-metin" if not birim else "")
        if band:
            sinif += f" hero-{band}"
        hucreler.append(
            f'<div class="hero-oge{" hero-oge-" + band if band else ""}">'
            f'<div class="hero-etiket">{etiket}'
            f'{band_isareti}</div>'
            f'<div class="{sinif}">{html.escape(deger)}'
            + (f'<span class="hero-birim">{birim}</span>' if birim else "")
            + '</div>'
            + (kiv or '<div class="hero-yok">eğilim verisi yok</div>') + "</div>")
    return '<div class="hero">' + "".join(hucreler) + "</div>"


def _cozum_satirlari_html(satirlar: list[dict]) -> str:
    """Çözülmüş grupları token → anlam satırları olarak çizer.

    Çözülemeyen gruplar ATILMAZ: ham hâliyle, "çözümlenemedi" etiketiyle
    kalırlar. Okuyanın gördüğü liste raporun TAMAMI olmalı - eksik bir
    liste, tam sanıldığı için ham metinden daha tehlikelidir."""
    parcalar = []
    for sat in satirlar:
        jeton = f'<code class="jeton">{html.escape(sat["token"])}</code>'
        # RMK SATIRI DİK DİZİLİR. Ötekilerde jeton kısa bir koddur
        # ("04008KT") ve sabit genişlikli bir sütunda durur; RMK'nın
        # jetonu ise METAR'ın tüm kuyruğunu taşıyor. Aynı yatay düzene
        # sokunca o uzun metin dar sütuna sıkışıp satır satır kırılıyor,
        # yanındaki açıklama da tek kelimelik bir şeride düşüyordu.
        if sat["ad"] == "Notlar":
            parcalar.append(
                f'<div class="coz-satir coz-dik">'
                f'<div class="coz-metin"><b>{html.escape(sat["ad"])}</b>'
                f'<span>{html.escape(sat["aciklama"])}</span></div>'
                f'<code class="jeton jeton-genis">'
                f'{html.escape(sat["token"])}</code></div>')
            continue
        if sat["cozuldu"]:
            parcalar.append(
                f'<div class="coz-satir">{jeton}'
                f'<div class="coz-metin"><b>{html.escape(sat["ad"])}</b>'
                f'<span>{html.escape(sat["aciklama"])}</span></div></div>')
        else:
            parcalar.append(
                f'<div class="coz-satir coz-bilinmiyor">{jeton}'
                f'<div class="coz-metin"><span>çözümlenemedi — '
                f'ham hâliyle gösteriliyor</span></div></div>')
    return "".join(parcalar)


def _metar_cozum_html(metin: str) -> str:
    """METAR/SPECI'nin satır satır Türkçe karşılığı."""
    satirlar = cozumle.metar_satirlari(metin)
    if not satirlar:
        return ""
    return ('<div class="cozum"><div class="coz-bas">Gözlem</div>'
            + _cozum_satirlari_html(satirlar) + "</div>")


def _taf_cozum_html(metin: str) -> str:
    """TAF'ın değişim gruplarına bölünmüş Türkçe karşılığı.

    Her grup KENDİ başlığı ve geçerlilik penceresiyle gelir; "PROB30
    TEMPO" gibi birleşik başlıklar tek parçadır (bkz. ltfj_cozumle)."""
    bolumler = cozumle.taf_bolumleri(metin)
    if not bolumler:
        return ""
    # TAF ÇÖZÜMLEMESİ VARSAYILAN OLARAK KATLI, METAR'INKİ AÇIK.
    # İkisi aynı değil: METAR "şu an ne var" - bir bakışta okunur ve
    # kısadır. TAF ise 24 saatlik bir tahmin, beş-altı değişim grubu,
    # ölçülen 2000+ piksel. Açık bıraktığımızda sayfanın en uzun bloğu
    # oluyor ve altındaki her şeyi (geçmiş eğilim, dipnot) ekrandan
    # itiyordu. Kapalı başlıyor ama BAŞLIK KAÇ GRUP olduğunu söylüyor -
    # yani katlanmış şeyin ne olduğu görünüyor, "aç da gör" değil.
    grup_sayisi = len(bolumler)
    parcalar = ['<details class="cozum cozum-kat"><summary>'
                f'Çözümleme · {grup_sayisi} grup</summary>']
    for b in bolumler:
        parcalar.append(
            f'<div class="coz-grup"><span class="coz-etiket">'
            f'{html.escape(b["baslik"])}</span>'
            + (f'<span class="coz-pencere">{html.escape(b["pencere"])}</span>'
               if b["pencere"] else "") + "</div>")
        parcalar.append(_cozum_satirlari_html(b["satirlar"]))
    return "".join(parcalar) + "</details>"


def _pist_diyagrami_html(cozum: dict, metin: str, tercih: str | None) -> str:
    """Pist ekseni + ruzgar oku + bilesen okumasi.

    NEDEN: bu bilgi sayfada zaten VARDI ama duz metin olarak -
    "Pist 06L  020° 2 kt". Kontrolorun kafasinda yaptigi geometriyi
    (ruzgar pistin neresinden geliyor, ne kadari bas, ne kadari yan)
    ekran yapmiyordu. ltfj_panel/panel.html'de bir ruzgar vektoru zaten
    vardi ama ANA SAYFADA yoktu.

    HICBIR HESAP KOPYALANMADI - VE YENI BIR KARAR CAGRISI DA YOK.
    Tercih edilen pist DISARIDAN geliyor: havacilik_notlari() onu zaten
    hesapliyor (notlar["tercih"]) ve sayfa da, Telegram da ayni degeri
    kullaniyor. Burada yeniden hesaplamak, ayni METAR icin iki farkli
    cevap riski dogururdu; ustelik tests/test_ltfj_sayfa_lvo.py'deki
    koruma da bunu dogru sekilde engelledi.

    Pist eksenleri ltfj_ayarlar'dan, per-pist ruzgar kaynagi
    pist_ruzgar_kaynagi()'ndan (pist_raporu ve ltfj_panel de ayni
    fonksiyondan besleniyor), bilesenler bilesenler()'den geliyor.

    UYDURMA YOK: ruzgar yonu bilinmiyorsa (VRB) ok CIZILMEZ, yonsuzluk
    yazilir. Tercih edilen pist bir ATC atamasi DEGIL - fonksiyonun
    kendi aciklamasindaki uyari burada da tekrarlanir."""
    if not cozum or not tercih or tercih not in pist.PISTLER:
        return ""
    pist_yonu = pist.PISTLER[tercih]["yon"]

    # Bu pistin KENDI ruzgar kaynagi (RMK anemometresi varsa o).
    kaynak = next((x for x in pist.pist_ruzgar_kaynagi(cozum, metin)
                   if x["pist"] == tercih), None)
    if not kaynak:
        return ""
    yon, hiz = kaynak["yon"], kaynak["hiz_sabit"]
    bas, yan, taraf = pist.bilesenler(yon, hiz, pist_yonu)

    # Kucultuldu (180x144 -> 150x120) ki telefonda okuma YAN YANA kalsin;
    # 390px'te blok alt alta dusuyordu. 1:1 cizim korunuyor.
    MERKEZ_X, MERKEZ_Y, YARICAP = 60.0, 60.0, 38.0

    def _nokta(kerteriz: float, uzaklik: float) -> tuple[float, float]:
        """Pusula kerterizini SVG koordinatina cevirir (kuzey YUKARI)."""
        a = math.radians(kerteriz)
        return (MERKEZ_X + uzaklik * math.sin(a),
                MERKEZ_Y - uzaklik * math.cos(a))

    # Pist seridi: eksen boyunca iki uc. SVG'de 0 derece SAGA bakar,
    # pusulada 0 derece YUKARI - fark cikarilarak donduruluyor.
    x1, y1 = _nokta(pist_yonu, YARICAP * 0.80)
    x2, y2 = _nokta(pist_yonu + 180, YARICAP * 0.80)
    yakin_ad = tercih[:2]                       # "06L" -> "06"
    uzak_ad = "24" if yakin_ad == "06" else "06"
    # UC ADLARI PISTIN USTUNDE - gercekte de pist numarasi asfalta
    # yazilidir. Eksenin yaninda dururken ruzgar okuyla cakisiyorlardi
    # (bas ruzgari en sik durum, ok tam oradan geliyor); serit uzerinde
    # cakisma yapisal olarak imkansiz cunku ok seride girmeden duruyor.
    # Her iki ad da SOLDAN SAGA okunacak sekilde donduruluyor.
    e1x, e1y = _nokta(pist_yonu, YARICAP * 0.52)
    e2x, e2y = _nokta(pist_yonu + 180, YARICAP * 0.52)
    # Eksen acisi +-90 araligina indirgenir ki iki numara da SOLDAN SAGA
    # okunsun. (Gercek pistte numaralar birbirine gore terstir - her biri
    # kendi yaklasma yonunden okunur - ama 11 piksellik bir diyagramda
    # okunurluk gercekciligin onune geciyor.)
    donme = pist_yonu - 90
    while donme > 90:
        donme -= 180
    while donme < -90:
        donme += 180
    d1 = d2 = donme

    ok = ""
    if yon is not None and hiz:
        # Ruzgar GELDIGI yonden merkeze dogru cizilir (meteorolojik yon).
        # Ok SERIDE GIRMEDEN duruyor (serit yarim uzunlugu .80 yaricap,
        # numaralar .52'de) - boylece hicbir ruzgar yonunde cakismaz.
        kx, ky = _nokta(yon, YARICAP * 1.16)
        ix, iy = _nokta(yon, YARICAP * 0.76)
        ok = (f'<line class="pd-ok" x1="{kx:.1f}" y1="{ky:.1f}" '
              f'x2="{ix:.1f}" y2="{iy:.1f}" marker-end="url(#pd-uc)"/>')

    baslik = (f"Rüzgâr {yon:03d}°/{hiz} kt" if yon is not None and hiz is not None
              else "Rüzgâr yönü değişken")
    svg = (
        f'<svg class="pd-svg" viewBox="0 0 120 120" role="img" '
        f'aria-label="{html.escape(baslik)}, pist {html.escape(tercih)}">'
        '<defs><marker id="pd-uc" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="5" markerHeight="5" orient="auto-start-reverse">'
        '<path d="M0 0 L10 5 L0 10 z" fill="currentColor"/></marker></defs>'
        f'<circle class="pd-halka" cx="{MERKEZ_X}" cy="{MERKEZ_Y}" r="{YARICAP}"/>'
        f'<line class="pd-pist" x1="{x1:.1f}" y1="{y1:.1f}" '
        f'x2="{x2:.1f}" y2="{y2:.1f}"/>'
        f'<text class="pd-uc-ad pd-uc-tercih" x="{e1x:.1f}" y="{e1y:.1f}" '
        f'transform="rotate({d1:.1f} {e1x:.1f} {e1y:.1f})">{yakin_ad}</text>'
        f'<text class="pd-uc-ad" x="{e2x:.1f}" y="{e2y:.1f}" '
        f'transform="rotate({d2:.1f} {e2x:.1f} {e2y:.1f})">{uzak_ad}</text>'
        f'<text class="pd-kuzey" x="{MERKEZ_X}" y="{MERKEZ_Y - YARICAP - 6:.1f}">K</text>'
        f"{ok}</svg>")

    if bas is None:
        okuma = '<div class="pd-satir">Rüzgâr yönü değişken — bileşen hesaplanamıyor</div>'
    else:
        limit, _ = pist.kuyruk_limiti(cozum)
        kuyruk = bas < 0
        bas_sinif = " pd-asan" if kuyruk and abs(bas) > limit else ""
        okuma = (
            f'<div class="pd-satir{bas_sinif}">'
            f'<span class="pd-etiket">{"kuyruk" if kuyruk else "baş"}</span>'
            f'<b>{abs(bas):.0f}</b> kt</div>'
            f'<div class="pd-satir"><span class="pd-etiket">yan</span>'
            f'<b>{yan:.0f}</b> kt{f" {taraf}" if taraf else ""}</div>')
        if kuyruk and abs(bas) > limit:
            okuma += (f'<div class="pd-not">kuyruk limiti {limit} kt '
                      f'(AD 2.20 K) aşılıyor</div>')

    return ('<div class="pist-diyagram">'
            f'{svg}<div class="pd-okuma">'
            f'<div class="pd-pist-ad">{html.escape(tercih)}</div>{okuma}'
            '<div class="pd-not">rüzgâra göre hesaplanmış tercih — '
            'aktif pisti ATC belirler</div>'
            '</div></div>')


def _ikincil_satir(cozum: dict) -> str:
    """Hero'da OLMAYAN alanlar: hava kodu, sicaklik/ciy, QNH.

    ozet_satiri() CAGRILMIYOR cunku o TELEGRAM'in ozeti ve gorus/tavan/
    ruzgari da iceriyor - burada hero zaten onlari buyuk buyuk gosteriyor,
    ayni sayiyi 100 piksel arayla iki kez yazmak dagiciklik olurdu.
    ozet_satiri'na DOKUNULMADI; Telegram'da aynen kaliyor."""
    p = []
    if cozum.get("hava"):
        p.append(" ".join(cozum["hava"]))
    t, c = cozum.get("sicaklik"), cozum.get("cig_noktasi")
    if t is not None:
        p.append(f"{t}°C" + (f" / çiy {c}°C" if c is not None else ""))
    if cozum.get("qnh"):
        p.append(f'QNH {cozum["qnh"]}')
    return " · ".join(p)


def _kart(rapor: dict, yorum_onbellegi: dict | None = None,
          gecmis: list | None = None, simdi: datetime | None = None) -> str:
    tip = rapor["tip"]
    cozum = metar_coz(rapor["metin"]) if tip in ("METAR", "SPECI") else None
    notlar = (havacilik_notlari(cozum, rapor["metin"], rapor.get("zaman"))
              if cozum else None)
    yorum = (yorum_onbellegi or {}).get(rapor["metin"])

    ad = tip + (f' {rapor["duzeltme"]}' if rapor.get("duzeltme") else "")
    if rapor.get("zaman"):
        zaman = _zaman_metni(rapor["zaman"], tarihli=True)
    else:
        zaman = ""

    # RENK ROZETI ("BLU · çok iyi") ve SOL KENAR RENGI KALDIRILDI.
    # İkisi de ltfj_pist.renk_durumu()'nun ürettiği, bota ÖZGÜ bir
    # ciddiyet ölçeğini gösteriyordu; rozetin title'ı her seferinde
    # "resmî ICAO CAT I/II/III kategorisi değildir" diye kendini
    # yalanlamak zorundaydı. Sayfanın durum sinyali artık tepedeki
    # VFR/IFR bandı (bkz. _vfr_bandi_html) - ICAO Annex 2 Tablo 3-1.
    # notlar["renk"] HESAPLANMAYA DEVAM EDİYOR: Telegram tarafı
    # kullanıyor, sayfa yalnızca GÖSTERMİYOR.
    p = [f'<div class="kart"><div class="basrow">'
         f'<span class="tip">{html.escape(ad)}</span>'
         f'<span class="zaman">{html.escape(zaman)}</span></div>']

    if yorum:
        # Yorum KATLI gelir: METAR/TAF kartlari sayfanin %43'unu kapliyordu
        # (1175 + 970 px) ve sismenin sebebi cok paragrafli bu metindi.
        # Kontrolor once rakamlara bakiyor - ozet satiri, dikkat uyarilari
        # ve pist rüzgârlari ACIK kaliyor, sadece duz anlatim katlaniyor.
        p.append('<details class="kat"><summary>'
                 + ikon("yapayzeka")
                 + ' Genel değerlendirme (yapay zekâ özeti — esas kaynak ham rapordur)'
                   '</summary>'
                 f'<div class="yorum">{_yorum_html(yorum)}</div></details>')

    if cozum:
        dikkat = uyarilar(cozum)
        if notlar["ws"]:
            dikkat.insert(0, "Rüzgâr kesmesi: " + ", ".join(notlar["ws"]))
        if dikkat:
            p.append(f'<div class="dikkat"><b>Dikkat</b> · '
                     f'{html.escape(" · ".join(dikkat))}</div>')

        # HERO ARTIK BURADA DEGIL, SAYFANIN TEPESINDE (bkz. sayfa_yaz).
        # Olculdu: 390px telefonda hero y=609'da basliyordu - ilk ekranin
        # %72'si asagida. Ustunde sirasiyla baslik, dugmeler, ozet serit,
        # sekme cubugu ve kartin kendi basligi/yapay zeka ozeti vardi.
        # Yani sayfanin EN BUYUK dort sayisi, en gec gorulen seylerdendi.
        ikincil = _ikincil_satir(cozum)
        if ikincil:
            p.append(f'<div class="ozet-ikincil">{html.escape(ikincil)}</div>')

        diyagram = _pist_diyagrami_html(cozum, rapor["metin"],
                                        notlar.get("tercih"))
        if diyagram:
            p.append(diyagram)

        satirlar = []
        ham_pistler = notlar["pistler"]
        pistler = [x for x in ham_pistler if not x.startswith("(")]
        # "(...)" satiri hangi pistin GERCEK AD 2.15 anemometre verisinden,
        # hangisinin (o pist icin RMK'da veri yoksa) alan METAR ruzgarindan
        # HESAPLANDIGINI belirtir - Telegram/ATC panel bunu zaten gosteriyor;
        # burada da SESSIZCE ATILMAMASI gerekiyor, yoksa dört pist de esit
        # kesinlikte olcumus gibi yanlis bir izlenim verir.
        pist_kaynagi = next((x.strip("() ") for x in ham_pistler if x.startswith("(")), None)
        for x in pistler:
            pist, _, deger = x.partition(":")
            satirlar.append((f"Pist {pist}", deger.strip()))
        if notlar["tercih"]:
            satirlar.append(("Meteorolojik tercih", notlar["tercih"]))
        if notlar["rvr"]:
            satirlar.append(("Pist görüş menzili", "; ".join(notlar["rvr"])))
        if notlar["trend"]:
            satirlar.append(("Eğilim", notlar["trend"]))
        # "Sis riski" satiri KASITLI OLARAK kaldirildi: sezgisel bir METAR
        # tabanli ifadeydi ve sayfada ayrica HOLDOUT'TA DOGRULANMIS
        # "İstatistiksel sis olasılığı" karti var - iki ayri sis ifadesi yan
        # yana durunca hangisine guvenilecegi belirsizlesiyordu.
        # notlar["sis"] Telegram tarafinda kullanilmaya devam ediyor.
        for g in notlar["gorus_op"]:
            satirlar.append(("Görüş operasyonu", g))

        if satirlar:
            p.append("<table>" + "".join(
                f"<tr><td>{html.escape(a)}</td><td>{html.escape(b)}</td></tr>"
                for a, b in satirlar) + "</table>")
        if pist_kaynagi:
            p.append(f'<div class="pist-kaynak">{ikon("ucak")} {html.escape(pist_kaynagi)}</div>')

    # ÇÖZÜMLEME ÖNCE, HAM METİN SONRA VE KATLANIR. Ham METAR/TAF
    # sayfadan KALKMADI - kaynak metin her zaman erişilebilir olmalı,
    # çözümleyici de yanılabilir. Ama artık varsayılan görünüm o değil:
    # ekranda önce ne dediği, isteyene ne yazdığı var.
    p.append(_taf_cozum_html(rapor["metin"]) if tip == "TAF"
             else _metar_cozum_html(rapor["metin"]))
    govde = taf_bicimle(rapor["metin"]) if tip == "TAF" else rapor["metin"]
    p.append('<details class="ham-kat"><summary>Ham metin</summary>'
             f"<pre>{html.escape(govde)}</pre></details></div>")
    return "".join(p)


# Bundan eski bir tahminde yaş satırda AÇIKÇA yazılır. Altındaki yaşlar
# için yazmıyoruz: önbellek zaten sık sık bu aralıkta ve her seferinde
# "18 dk önce" yazmak bilgi değil gürültü olurdu.
TAHMIN_YAS_UYARI_DK = 90


def _saatlik_tahmin_html(satirlar: list, yas_dk: float | None = None) -> str:
    """Önümüzdeki saatlerin MODEL tahmini (Open-Meteo) - TAF DEĞİLDİR.

    Bilinçli olarak yorum/uyarı üretmiyor, sadece ham eğilimi gösteriyor:
    bu veriyle geriye dönük dürüst bir doğrulama yapılamadı (bkz.
    ltfj_dis_kaynak_cache modül açıklaması), dolayısıyla ondan bir karar
    sinyali türetmek sayfanın geri kalanındaki disipline aykırı olurdu.

    Spread (sıcaklık - çiy noktası) başa konuyor: bu projedeki tüm
    tavan/sis çalışmalarında en güçlü öncü gösterge oydu.

    yas_dk: tahminin kaç dakika önce çekildiği (bkz.
    ltfj_dis_kaynak_cache.tahmin_yasi_dk). Verilmezse yaş yazılmaz -
    eski çağrılar aynen çalışır."""
    if not satirlar:
        return ""

    def _yerel_saat(iso: str) -> str:
        try:
            an = datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return "—"
        return f"{an.astimezone(YEREL_TZ):%H:%M}"

    def _sayi(deger, birim="", basamak=0):
        if deger is None:
            return "—"
        return f"{deger:.{basamak}f}{birim}"

    # Yaş neden gösteriliyor: GitHub zamanlanmış koşuları düşürdüğü için
    # önbellek bazen saatlerce yenilenmiyor. Şeridi gizlemek yerine (eskiden
    # öyleydi, "bazen var bazen yok" şikâyetine yol açtı) kaç saatlik bir
    # model çıktısına bakıldığı yazılıyor - karar okuyanın.
    yas_rozeti = ""
    if yas_dk is not None and yas_dk >= TAHMIN_YAS_UYARI_DK:
        if yas_dk < 120:
            metin = f"{yas_dk / 60:.1f} saat önceki model çıktısı"
        else:
            metin = f"{yas_dk / 60:.0f} saat önceki model çıktısı"
        yas_rozeti = f'<span class="tahmin-yas">{html.escape(metin)}</span>'

    # NEDEN TABLO, neden ayri <div> kolonlari DEGIL:
    #
    # Onceki surumde her saat kendi <div>'iydi ve iki satir KOSULLUYDU -
    # sis isareti (weather_code) ve sinir tabakasi yuksekligi (deneysel
    # alan, Open-Meteo bazen hic dondurmuyor). Sonuc tarayicida olculdu:
    # sisli bir kolonda gorus 489px'te, komsu kolonlarda 468px'teydi -
    # yani "gorus" satirini yatay tararken sisli saatin gorusu,
    # komsularinin RUZGAR satirinin hizasina dusuyordu. BLH'si olmayan
    # kolon ise en alt satiri hic cizmiyordu. Bir meteoroloji seridinde
    # bu yanlis okutur.
    #
    # Tablo bunu YAPISAL olarak cozer: satir bir <tr>, hangi hucre bos
    # olursa olsun hiza bozulmaz. Ustelik satir basliklari <th scope="row">
    # olunca ekran okuyucu her sayiyi adiyla okur - eskiden hangi sayinin
    # ne oldugu yalnizca ALTTAKI DUZ METINDE yaziyordu.
    def _hucre(deger, sinif=""):
        icerik = "&mdash;" if deger is None else html.escape(str(deger))
        c = f' class="{sinif}"' if sinif else ""
        return f"<td{c}>{icerik}</td>"

    basliklar = []
    satir_verisi = {ad: [] for ad in
                    ("spread", "gorus", "ruzgar", "bulut", "blh")}
    for satir in satirlar:
        sic, cig = satir.get("temperature_2m"), satir.get("dew_point_2m")
        spread = None if sic is None or cig is None else sic - cig
        gorus_m = satir.get("visibility")
        # Open-Meteo görüşü METRE verir; 10 km ve üstünü METAR'daki gibi
        # "10+" olarak kısaltıyoruz - aradaki her 100 metreyi göstermek
        # olmayan bir hassasiyet ima ederdi.
        if gorus_m is None:
            gorus = None
        elif gorus_m >= 10000:
            gorus = "10+"
        else:
            gorus = f"{gorus_m / 1000:.1f}"
        # weather_code ve boundary_layer_height DENEYSEL alanlar: Open-Meteo
        # kabul etmezse onbellekte hic olmazlar (bkz. ltfj_dis_kaynak_cache.
        # HOURLY_DENEYSEL). Yoklugunda hucre "—" olur, satir KAYBOLMAZ.
        sisli = satir.get("weather_code") in SIS_KODLARI
        sinif = "tahmin-sisli" if sisli else ""
        sis_isareti = ('<div class="tahmin-sis" title="Model bu saatte sis '
                       'bekliyor (WMO kodu)">' + ikon("sis") + " sis</div>"
                       ) if sisli else ""
        bas_sinif = f' class="{sinif}"' if sinif else ""
        basliklar.append(
            f'<th scope="col"{bas_sinif}><span class="tahmin-saat">'
            f'{html.escape(_yerel_saat(satir.get("saat", "")))}</span>'
            f"{sis_isareti}</th>")
        satir_verisi["spread"].append(
            (None if spread is None else f"{spread:.1f}", sinif))
        satir_verisi["gorus"].append((gorus, sinif))
        # RUZGAR BIRIM DONUSUMU: Open-Meteo'ya wind_speed_unit
        # GONDERILMIYOR, yani varsayilan km/SAAT donuyor. Sayfa "km/s"
        # yaziyordu - hem Turkce'de kilometre/saniye okunur hem de
        # sayfanin geri kalani (METAR, ozet serit, hero) KNOT. Yan yana
        # duran iki ruzgar sayisindan biri km/h digeri kt olursa ~2 kat
        # yanlis okunur. Cevirip kt yaziyoruz; deger UYDURULMUYOR, ayni
        # olcunun birimi degisiyor (1 kt = 1.852 km/h).
        kmh = satir.get("wind_speed_10m")
        satir_verisi["ruzgar"].append(
            (None if kmh is None else f"{kmh / 1.852:.0f}", sinif))
        bulut = satir.get("cloud_cover_low")
        satir_verisi["bulut"].append(
            (None if bulut is None else f"{bulut:.0f}", sinif))
        blh = satir.get("boundary_layer_height")
        satir_verisi["blh"].append(
            (None if blh is None else f"{blh:.0f}", sinif))

    # Birimler SATIR BASLIGINDA, her hucrede DEGIL: 360px'te birimli
    # hucreler tabloyu tasiriyordu, ustelik ayni birim 12 kez tekrar
    # ediyordu. Ayni yaklasim gecis tablosunda da kullanilmisti.
    SATIR_TANIMLARI = (
        ("spread", "spread", "°C",
         "Sıcaklık − çiy noktası; düştükçe sis riski artar"),
        ("gorus", "görüş", "km", "Model görüşü; 10+ = 10 km ve üstü"),
        ("ruzgar", "rüzgâr", "kt",
         "10 m rüzgârı; Open-Meteo'nun km/sa değerinden çevrildi"),
        ("bulut", "alçak bulut", "%", "Düşük seviye bulut örtüsü oranı"),
        ("blh", "sınır tabakası", "m",
         "Sınır tabakası yüksekliği; alçaldıkça radyasyon sisine elverişli"),
    )
    govde = []
    for anahtar, etiket, birim, aciklama in SATIR_TANIMLARI:
        hucre_listesi = satir_verisi[anahtar]
        # Alan HIC gelmemisse (deneysel alan reddedilmis) satiri bosuna
        # cizmiyoruz - ama TEK bir saatte bile varsa satir kaliyor ve
        # eksikler "—" oluyor. Fark onemli: "bu alan yok" ile "bu saatte
        # yok" ayri seyler.
        if all(d is None for d, _ in hucre_listesi):
            continue
        vurgu = ' class="tahmin-vurgu"' if anahtar == "spread" else ""
        govde.append(
            f'<tr{vurgu}><th scope="row" title="{html.escape(aciklama)}">'
            f'{etiket}<span class="tahmin-birim">{birim}</span></th>'
            + "".join(_hucre(d, sinif) for d, sinif in hucre_listesi)
            + "</tr>")

    return (
        '<div class="alt-bolum">'
        '<div class="basrow"><span class="tip">Önümüzdeki saatler</span>'
        '<span class="zaman">Open-Meteo model tahmini</span>' + yas_rozeti + '</div>'
        '<div class="tahmin-uyari">Bu bir <strong>model tahminidir, TAF değildir</strong> — '
        "resmî havacılık tahmini yerine geçmez, operasyonel karar için TAF ve "
        "resmî kaynaklar esastır. Eğilimi görmek için konulmuştur.</div>"
        '<div class="tahmin-kaydir"><table class="tahmin-tablo">'
        '<thead><tr><th></th>' + "".join(basliklar) + "</tr></thead>"
        "<tbody>" + "".join(govde) + "</tbody></table></div>"
        '<div class="tahmin-aciklama">Saatler yereldir. "sis" işareti, modelin '
        "o saat için sis kodu (WMO 45/48) verdiğini gösterir. Eksik değer "
        "<b>&mdash;</b> ile yazılır, satır gizlenmez.</div>"
        "</div>")


SEKMELER = (
    ("durum",      "Durum",      ""),
    ("beklenti",   "Beklenti",   ""),
    ("istatistik", "İstatistik", ""),
    ("lvo",        "LVO",        ""),
    # NOTAM rozeti SUNUCUDA doldurulamaz: aktif sayi Firebase'den istemci
    # tarafinda geliyor. Bos <span> birakiliyor, mevcut JS ayni id'yi
    # (notam-aktif-sayi) bulup yaziyor - boylece rozet mantigi tek yerde
    # kaliyor. :empty CSS kurali dolana kadar onu gizler.
    ("notam",      "NOTAM",      '<span class="sekme-rozet" id="notam-aktif-sayi"></span>'),
)


def _sekme_cubugu_html(sis_yuzde: str = "") -> str:
    """Yatay sekme çubuğu.

    ROZETLER BURADA, çünkü sekme içeriği GİZLİYOR: panel kapalıyken bir
    şeyin değiştiğini (yeni NOTAM, yüksek sis olasılığı) fark etmenin tek
    yolu çubuğun kendisi. Eskiden bu bilgi katlanır başlığın üstündeydi ve
    kaydırırken göz ucuyla görülüyordu."""
    parcalar = []
    for anahtar, etiket, rozet in SEKMELER:
        if anahtar == "istatistik" and sis_yuzde:
            rozet = (f'<span class="sekme-rozet">%{html.escape(sis_yuzde)}</span>')
        secili = "true" if anahtar == "durum" else "false"
        parcalar.append(
            f'<button type="button" class="sekme" role="tab" id="sekme-{anahtar}"'
            f' data-sekme="{anahtar}" aria-controls="panel-{anahtar}"'
            f' aria-selected="{secili}">'
            f'{ikon("sekme-" + anahtar, "ikon sekme-ikon")}{etiket}{rozet}</button>')
    return ('<nav class="sekme-cubugu" role="tablist" '
            'aria-label="Sayfa bölümleri">' + "".join(parcalar) + "</nav>")


def _vfr_bandi_html(cozum: dict | None) -> str:
    """Sayfanın tepesindeki uçuş kuralı göstergesi: VFR / IFR.

    BURADA ESKİDEN BLU/WHT/GRN/YLO/AMB/RED VARDI. O ölçek bota özgüydü
    ve gösterildiği her yerde "resmî bir ICAO CAT I/II/III kategorisi
    değildir" diye bir dipnotla dengelenmek zorundaydı. VFR/IFR ise
    uydurma değil: ICAO Annex 2 Tablo 3-1 eşikleri, ve bu hesap sayfada
    ZATEN vardı (kenardaki VFR sekmesi). Yani yeni bir yargı katmanı
    EKLENMEDİ, var olan yargı katmanı uydurma olanın yerine geçti.

    Renk tek taşıyıcı değil: nokta rengiyle birlikte "VFR"/"IFR" harfleri
    ve altındaki tam cümle aynı bilgiyi metinle de veriyor.

    Çözüm yoksa boş döner - blok çizilmez, uydurulmaz."""
    if cozum is None:
        return ""
    sonuc = vfr.vfr_degerlendir(cozum)
    if sonuc["vfr"] is True:
        kod, nokta, alt = "VFR", "yesil", "VFR şartları sağlanıyor"
    elif sonuc["vfr"] is False:
        # "IFR" DEMEK, "VFR DEĞİL" demekten daha kısa ve kulede okunan
        # dil bu - ama altındaki cümle neyin ölçüldüğünü açıkça yazıyor,
        # çünkü bu bir IFR TESPİTİ değil, VFR eşiklerinin karşılanmaması.
        kod, nokta, alt = "IFR", "kirmizi", "VFR şartları sağlanmıyor"
    else:
        kod, nokta, alt = "—", "bilinmiyor", "Görüş bilgisi yok — değerlendirilemiyor"
    return (
        '  <div class="durum-blok">\n'
        f'    <span class="vfr-nokta {nokta}" aria-hidden="true"></span>\n'
        f'    <span class="durum-kod">{kod}</span>\n'
        '    <span class="durum-ad">'
        f'<span class="durum-ad-metin">{html.escape(alt)}</span>'
        '<span class="durum-kaynak">ICAO Annex 2, Tablo 3-1 — bilgi amaçlı</span>'
        '</span>\n  </div>')


def _ozet_serit_html(cozum: dict | None, notlar: dict | None) -> str:
    """Sayfanın üstünde YAPIŞKAN duran tek satırlık durum özeti.

    Amaç: "şu an bir sıkıntı var mı?" sorusunu SIFIR kaydırmayla
    yanıtlamak. Kartlar katlandıktan sonra sayfa 2.4 ekrana indi ama
    bu satır kaydırırken de görünür kaldığı için cevap her an elde.

    Değerler ham METAR'dan gelir - yorum/tahmin YOK. Eksik alan "—"
    olur; satır hiç çizilmemektense eksik çizilir, çünkü yokluğu da
    bilgidir (ör. tavan bildirilmiyor)."""
    if not cozum:
        return ""

    # Degerler _olcu()'den: hero ile serit ayni dort olcuyu ayri ayri
    # bicimlendirdigi surece ayni ekranda birbirinden farkli konusuyordu
    # (bkz. _olcu aciklamasi). Artik tek kaynak.
    def _kisa(anahtar, on=""):
        deger, birim = _olcu(cozum, anahtar)
        if deger == "bildirilmedi":
            # BURADA ESKIDEN tavan icin KOSULSUZ "tavan yok" yaziliyordu.
            # Ama "sayi gelmedi" ile "tavan yok" ayni sey degil: bozuk ya
            # da kirpilmis bir raporda da sayi gelmez ve serit, ortada
            # tavan olmadigini SOYLEMIS olurdu. Artik bu ayrimi _olcu
            # yapiyor (bkz. _tavan_yoklugu); buraya dusen sey gercekten
            # "bilmiyoruz" demek.
            return "—"
        if anahtar == "tavan" and deger == "yok":
            # Seritte GORUNUR ETIKET yok (sadece title), o yuzden deger
            # kendini anlatmak zorunda. Hero'da ustunde "TAVAN" yaziyor,
            # orada sade "yok" dogru okunuyor.
            return "tavan yok"
        # Spread'de birim YAZILMIYOR: "Δ" zaten farki anlatiyor ve
        # serit dar ekranda tek satirda kalmali.
        if on:
            return on + deger + "°"
        return deger + (f" {birim}" if birim else "")

    # (deger, tooltip) - serit kisa olmak zorunda, ne olduklari
    # title'da duruyor; ekran okuyucu da bunu okur.
    ogeler = [
        (_kisa("gorus"), "Görüş"),
        (_kisa("tavan"), "Bulut tavanı"),
        (_kisa("_ruzgar"), "Rüzgâr (yön/hız, G=hamle)"),
        (_kisa("_spread", "Δ"), "Spread (sıcaklık − çiy noktası)"),
    ]
    return ('<div class="ozet-serit" id="ozet-serit">'
            + "".join(f'<span class="ozet-oge" title="{html.escape(t)}">'
                      f"{html.escape(d)}</span>" for d, t in ogeler)
            + "</div>")


def _beklenti_html(tahmin_html: str) -> str:
    """Open-Meteo saatlik tahmin şeridi.

    İSTATİSTİKSEL SİS OLASILIĞI BURADAN TAŞINDI (bkz. _istatistik_html):
    ikisi de "birazdan ne olacak" sorusuna bakıyordu ama biri MODEL
    TAHMİNİ, öteki ARŞİV İSTATİSTİĞİ. Aynı başlık altında durunca
    kaynakları karışıyordu; sayfa zaten "bu tahmin mi, ölçüm mü, istatistik
    mi" ayrımını her yerde titizlikle koruyor."""
    # <details> SARMALI YOK: bu artik bir sekme paneli. Sekmeye basip bir
    # de basligi acmak iki tiklama olurdu.
    #
    # TAHMIN YOKSA BOS DONMUYORUZ. Bu bolum KATLANIR bir baslikken bos
    # donmek dogruydu - baslik hic cizilmezdi. Sekme olunca ayni davranis
    # BOS BIR SEKME uretti: kullanici "Beklenti"ye basiyor ve hicbir sey
    # gormuyor, aciklama da yok. Sekme cubukta duruyor cunku sekme listesi
    # sabit; o yuzden panel NEDEN bos oldugunu SOYLEMELI.
    govde = tahmin_html or (
        '<div class="notam-bos">Model tahmini şu an yok. Dış kaynak '
        'önbelleği (Open-Meteo) güncellenmemiş olabilir; bot bir sonraki '
        'koşuda yeniden dener.</div>')
    # DIS BASLIK YOK. Eskiden burada "Beklenti · önümüzdeki saatler"
    # yaziyordu ve HEMEN altinda _saatlik_tahmin_html'in kendi basligi
    # ("Önümüzdeki saatler · Open-Meteo model tahmini") geliyordu - ayni
    # sey ust uste uc kez. Sekme dugmesi paneli zaten "Beklenti" diye
    # adlandiriyor; kaynak bilgisini ic baslik tasiyor.
    return f'<div class="kart">{govde}</div>'


def _gecis_tablosu_html() -> str:
    """Arşivden öğrenilmiş görüş geçiş süreleri (DONDURULMUŞ tablo).

    Operasyonel soru: "görüş 5000'in altına düştü, eşiğe ne kadar var?"
    Bu bir TAHMİN DEĞİL - geçmişte ne olduğunun sayımı.

    En önemli sayı medyan değil HIZLI KUYRUK: olayların önemli bir
    kısmında geçiş bir saatten kısa sürmüş. Medyanı tek başına göstermek
    yanıltıcı olurdu, o yüzden %10/%25/medyan birlikte veriliyor."""
    t = gecis_tablo
    if not t.DUSME["n"]:
        return ""

    # Birim HER HUCREDE degil BASLIKTA: 390px'te "0.5 sa" iki satira
    # kiriliyordu ve tablo okunmaz hale geliyordu. Esik de ikinci satira
    # alindi, yoksa ilk sutun tabloyu eziyor.
    def _satir(ad, esik, o, aciklama):
        return (f'<tr><th scope="row" title="{html.escape(aciklama)}">{ad}'
                f'<span class="gecis-esik">{esik}</span></th>'
                f'<td>{o["p10"]:g}</td><td>{o["p25"]:g}</td>'
                f'<td><b>{o["medyan"]:g}</b></td><td>{o["p75"]:g}</td>'
                f'<td class="gecis-n">{o["n"]}</td></tr>')

    return (
        '<div class="alt-bolum">'
        '<div class="basrow"><span class="tip">Görüş geçiş süreleri</span>'
        f'<span class="zaman">{t.KAPSAM_ILK_YIL}–{t.KAPSAM_SON_YIL} arşivi · '
        f'{t.OLAY_SAYISI} sis olayı</span></div>'
        '<table class="gecis-tablo">'
        '<caption class="gecis-caption">süreler <b>saat</b> cinsinden</caption>'
        '<thead><tr><th></th>'
        '<th title="olayların %10&apos;unda bu kadar veya daha kısa">%10</th>'
        '<th>%25</th><th>medyan</th><th>%75</th><th>n</th></tr></thead><tbody>'
        + _satir("Düşme", f"{t.ESIK_VMC_M}→{t.ESIK_SVFR_M} m",
                 t.DUSME, "Görüşün VMC eşiğinden özel VFR alt sınırına inme süresi")
        + _satir("Toparlanma", f"{t.ESIK_SIS_M}→{t.ESIK_VMC_M} m",
                 t.TOPARLANMA, "Sis eşiğinden VMC'ye dönme süresi")
        + '</tbody></table>'
        '<div class="sis-olasilik-not">Geçmiş sis olaylarının SAYIMIDIR, '
        'tahmin değildir. Süreler 30 dakikalık gözlem ızgarasına yuvarlıdır '
        '— <b>"0.5 sa" aslında "yarım saat veya daha kısa"</b> demektir, '
        'gerçek en hızlı geçişler bu veriyle görülemeyecek kadar hızlı '
        'olabilir. Olay tanımı Tardif &amp; Rasmussen (2007).</div>'
        "</div>")


AY_KISA = ("Oca", "Şub", "Mar", "Nis", "May", "Haz",
           "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara")
AY_UZUN = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
           "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")
SEKTOR_ADI = {"sakin": "Sakin (≤2 kt)", "K": "Kuzey", "KD": "Kuzeydoğu",
              "D": "Doğu", "GD": "Güneydoğu", "G": "Güney",
              "GB": "Güneybatı", "B": "Batı", "KB": "Kuzeybatı"}


def _yuzde(x: float) -> str:
    """Türkçe ondalık: %1,25."""
    return "%" + f"{x:g}".replace(".", ",")


def _yuzde1(x: float) -> str:
    """Tablo sütununda hizalı: her zaman tek ondalık (%3 değil %3,0)."""
    return "%" + f"{x:.1f}".replace(".", ",")


def _iklim_seridi(etiketler, degerler, basliklar, ozet: str,
                  etiket_adimi: int = 1) -> str:
    """Tek serili çubuk şeridi (ay ya da saat). Lejant yok - tek seri,
    başlığı bölüm adı taşıyor. Yalnızca EN YÜKSEK çubuk değeriyle
    etiketleniyor; her çubuğa sayı yazmak şeridi okunmaz yapardı. Her
    çubuğun değeri title'da, şeridin özeti aria-label'da."""
    tepe = max(degerler) or 1
    i_tepe = degerler.index(max(degerler))
    hucreler = []
    for i, (etiket, deger, baslik) in enumerate(zip(etiketler, degerler, basliklar)):
        yukseklik = max(2, round(100 * deger / tepe))
        tepe_etiketi = (f'<span class="iklim-tepe">{_yuzde(deger)}</span>'
                        if i == i_tepe else "")
        alt = html.escape(etiket) if i % etiket_adimi == 0 else ""
        hucreler.append(
            f'<div class="iklim-hucre" title="{html.escape(baslik)}">'
            f'<div class="iklim-kolon">{tepe_etiketi}'
            f'<div class="iklim-cubuk"'
            f' style="height:{yukseklik}%"></div></div>'
            f'<span class="iklim-etiket">{alt}</span></div>')
    return (f'<div class="iklim-serit" role="img" aria-label="{html.escape(ozet)}"'
            f' style="--n:{len(degerler)}">{"".join(hucreler)}</div>')


def _kod_bilesimi_metni(bilesim) -> str:
    """[("FG", 664), ("SN", 237), ...] -> "FG 664 · SN 237 · ..."."""
    return " · ".join(f"{ad.replace('diger', 'diğer')} {n}" for ad, n in bilesim)


def _sis_iklim_html() -> str:
    """Arşivden SAYILMIŞ düşük görüş/FG olayı iklimbilimi: ay, saat, rüzgâr
    (DONDURULMUŞ). Sayılan, Model A'nın hedefiyle aynı olay gözlemi (görüş
    < 1000 m VEYA alanı kaplayan FG; kar dahil) - "sis" adları tarihsel.

    Tahmin değil, geçmişin sayımı - _gecis_tablosu_html ile aynı cins.
    Rüzgârda ham pay yerine KAT gösteriliyor: LTFJ'de en sık rüzgâr zaten
    kuzeydoğu, "sisin çoğu KD'de" bu yüzden kendiliğinden doğru olur ve
    bir şey söylemez. Kat, o rüzgârda sisin normale göre ne kadar sık
    görüldüğünü söyler."""
    t = sis_iklim
    if not t.SIS_GOZLEM:
        return ""
    aylar = sorted(t.AYLAR, key=lambda a: a["ay"])
    ilk3 = sorted(aylar, key=lambda a: -a["oran_yuzde"])[:3]
    ay_ozet = ", ".join(f'{AY_UZUN[a["ay"] - 1]} {_yuzde(a["oran_yuzde"])}' for a in ilk3)
    ay_seridi = _iklim_seridi(
        AY_KISA, [a["oran_yuzde"] for a in aylar],
        [f'{AY_UZUN[a["ay"] - 1]}: gözlemlerin {_yuzde(a["oran_yuzde"])}\'i sisli · '
         f'{a["sisli_gun"]} sisli gün' for a in aylar],
        f"Aylara göre sisli gözlem oranı. En yüksek: {ay_ozet}.")

    saatler = sorted(t.SAATLER, key=lambda s: s["saat"])
    tepe_saat = max(saatler, key=lambda s: s["oran_yuzde"])
    sabah = sum(s["pay_yuzde"] for s in saatler if 4 <= s["saat"] <= 7)
    saat_seridi = _iklim_seridi(
        [f'{s["saat"]:02d}' for s in saatler], [s["oran_yuzde"] for s in saatler],
        [f'{s["saat"]:02d}:00: gözlemlerin {_yuzde(s["oran_yuzde"])}\'i sisli'
         for s in saatler],
        f'Yerel saate göre sisli gözlem oranı. Zirve {tepe_saat["saat"]:02d}:00.',
        etiket_adimi=3)

    satirlar = "".join(
        f'<tr><th scope="row">{SEKTOR_ADI[r["sektor"]]}</th>'
        f'<td>{_yuzde1(r["sis_pay_yuzde"])}</td>'
        f'<td class="gecis-n">{_yuzde1(r["genel_pay_yuzde"])}</td>'
        f'<td><b>{str(r["kat"]).replace(".", ",")}×</b></td></tr>'
        for r in t.RUZGAR)
    g, d = t.GUNEY, t.DIGER
    g_aylar = [a for a in g["aylar"]]
    kis = (f'{AY_UZUN[min(a for a in g_aylar if a >= 9) - 1]}–'
           f'{AY_UZUN[max(a for a in g_aylar if a <= 6) - 1]}'
           if any(a >= 9 for a in g_aylar) and any(a <= 6 for a in g_aylar) else "")
    return (
        '<div class="alt-bolum">'
        '<div class="basrow"><span class="tip">Düşük görüş/FG ne zaman görülüyor</span>'
        f'<span class="zaman">{t.KAPSAM_ILK_YIL}–{t.KAPSAM_SON_YIL} arşivi · '
        f'{t.SIS_GOZLEM} olay gözlemi</span></div>'
        '<div class="iklim-baslik">Aylar <span>gözlemlerin olay oranı</span></div>'
        f"{ay_seridi}"
        f'<div class="iklim-ozet">En yoğun aylar: {html.escape(ay_ozet)}.</div>'
        '<div class="iklim-baslik">Saat <span>yerel · gözlemlerin olay oranı</span></div>'
        f"{saat_seridi}"
        f'<div class="iklim-ozet">Olay gözlemlerinin {_yuzde(round(sabah))}\'i '
        '04:00–07:59 arasında; öğleden sonra ve akşam nadir.</div>'
        '<table class="gecis-tablo iklim-ruzgar">'
        '<caption class="gecis-caption">Rüzgâr · <b>kat</b> = olay sırasındaki pay / '
        'genel pay (1\'in üstü: o rüzgârda olay normalden sık)</caption>'
        '<thead><tr><th></th><th>olay sırasında</th><th>genelde</th><th>kat</th></tr>'
        f'</thead><tbody>{satirlar}</tbody></table>'
        f'<div class="iklim-ozet">Olay sırasında rüzgâr medyanı {t.HIZ_MEDYAN_KT} kt.</div>'
        '<div class="iklim-baslik">Güneyli rüzgârda (140–250°)</div>'
        f'<div class="iklim-ozet">Nadir ama en ağır tip: {g["sisli_gun"]} olaylı gün, '
        f'olay gözlemlerinin {_yuzde(g["pay_yuzde"])}\'i'
        + (f', yalnızca {kis} döneminde' if kis else "")
        + f'. Olay süresi medyanı <b>{g["sure_medyan_sa"]:g} sa</b> (diğer olaylarda '
        f'{d["sure_medyan_sa"]:g} sa); olay gözlemlerinin <b>{_yuzde(g["lvo_yuzde"])}\'i '
        f'550 m altında</b> (diğerlerinde {_yuzde(d["lvo_yuzde"])}).</div>'
        '<div class="sis-olasilik-not">Geçmişin SAYIMIDIR, tahmin değildir. '
        'Olay gözlemi: görüş &lt; 1000 m <b>veya</b> meydanı kaplayan FG — '
        'karttaki olasılığın hedefiyle aynı. Görüşü düşüren olayın cinsine '
        f'bakılmaz; hava kodları: {html.escape(_kod_bilesimi_metni(t.KOD_BILESIMI))}. '
        'Arşivde SPECI yok (30 dk ızgara) — kısa ve keskin olaylar eksik '
        'sayılmış olabilir.</div>'
        "</div>")


def _tavan_istatistik_notlari(guncel_cozum: dict | None, gecmis: list,
                              simdi: datetime) -> list:
    """LVO farkındalık panelinden TAŞINAN iki istatistik notu.

    İkisi de eşik karşılaştırması değil, arşivden öğrenilmiş GÖRELİ oran
    ("ortalamaya göre kaç kat"). Hesap aynen korundu - yalnızca sayfadaki
    yeri değişti."""
    saat_utc = simdi.astimezone(timezone.utc).hour
    sis_p = _sis_olasiligi_hesapla(guncel_cozum, gecmis, simdi)
    return [n for n in (farkindalik.tavan_istatistik_notu(guncel_cozum),
                        farkindalik.tavan_dis_kaynak_notu(
                            guncel_cozum, sis_p, saat_utc)) if n]


def _istatistik_html(sis_html: str, notlar: list) -> str:
    """ARŞİVDEN ÖĞRENİLMİŞ her şey TEK başlık altında.

    Neden ayrı bir bölüm: sayfa "bu ölçüm mü, tahmin mi, istatistik mi"
    ayrımını her yerde koruyor ama istatistikler üç ayrı yere dağılmıştı -
    sis olasılığı "Beklenti"de, tavan oranları LVO farkındalık notlarında,
    geçiş süreleri hiç yoktu. Üçü de aynı cinsten (arşivden öğrenilmiş,
    göreli, resmî tahmin değil) ve artık aynı yerde.

    LVO panelinde KALAN notlar eşik karşılaştırmasıdır (METAR/TAF değeri
    şu eşiğin altında mı) - onlar ölçüm, bunlar istatistik."""
    gecis_html = _gecis_tablosu_html()
    iklim_html = _sis_iklim_html()
    not_html = ("".join(f"<li>{html.escape(n)}</li>" for n in notlar)
                if notlar else "")
    if not (sis_html or gecis_html or iklim_html or not_html):
        return ""
    tavan_bolumu = (
        '<div class="alt-bolum"><div class="basrow">'
        '<span class="tip">Tavan istatistiği</span></div>'
        f'<ul class="lvo-not-listesi">{not_html}</ul></div>') if not_html else ""
    # Rozet (sis %) artik SEKME DUGMESINDE (bkz. _sekme_cubugu_html):
    # panel kapaliyken gorulmesi gereken tek sey o.
    # DIS BASLIK YOK (bkz. _beklenti_html'deki ayni gerekce): sekme
    # "İstatistik" diyor, hemen altinda "İstatistiksel sis olasılığı"
    # geliyordu. "arşivden" ibaresi de kayip degil - uc alt bolumun
    # UCU DE kendi kapsamini yaziyor ("2011–2026 arşivi", "LTFJ'nin
    # 2011–2023 METAR arşivinden...").
    return ('<div class="kart">'
            f"{sis_html}{tavan_bolumu}{gecis_html}{iklim_html}"
            "</div>")


def sayfa_yaz(raporlar: list, gecmis: list, hedef: Path, yorum_onbellegi: dict | None = None,
              atc_notes_db_url: str = "", push_vapid_public_key: str = "",
              saatlik_tahmin: list | None = None,
              tahmin_yas_dk: float | None = None):
    """yorum_onbellegi: state["yorum_onbellegi"] (ham rapor metni -> Claude
    yorumu/cevirisi) - Telegram ile PAYLASILAN onbellek, burada okunur,
    YENIDEN hesaplanmaz. Verilmezse (ornegin eski cagiran kod) kartlar
    sadece deterministik (Claude'suz) bilgiyi gosterir - hicbir sekilde
    hata vermez.

    atc_notes_db_url: ayarlar.json::atc_notes.database_url - Firebase'in
    KENDI tasarimi geregi GIZLI DEGIL (bkz. ltfj_ayarlar.py), sayfa
    icine oldugu gibi gomulur. Bos ise ATC Notes bolumu "yapilandirilmamis"
    mesaji gosterir.

    push_vapid_public_key: ayarlar.json::push.vapid_public_key - ozel
    anahtarin (VAPID_PRIVATE_KEY, GH secret) esi, GIZLI DEGIL, istemci
    tarafinda applicationServerKey olarak aynen gomulur. Bos ise "Bildirimler"
    butonu hic gosterilmez (bkz. bildirim-izin-btn script'i)."""
    simdi = datetime.now(timezone.utc).astimezone(YEREL_TZ)
    # METAR/SPECI SADECE zamana gore siralanir - tipi ne olursa olsun en
    # yeni rapor en basta olur. Eskiden SPECI her zaman METAR'dan once
    # geliyordu (sabit tip sirasi); bu, saatler once yayinlanmis eski bir
    # SPECI'nin cok daha yeni bir METAR'in ONUNE gecip "guncel_rapor"
    # olarak secilmesine yol aciyordu - LVO farkindalik notlari, VFR
    # sekmesi ve istatistiksel sis olasiligi karti o zaman eski SPECI'nin
    # gorus/tavan degerleriyle hesaplaniyordu. TAF bir gozlem degil,
    # gelecek donem tahmini oldugu icin obs raporlariyla zaman bazinda
    # kiyaslanmiyor - listede hep en sonda durur.
    sirali = sorted(raporlar, key=lambda r: (
        r["tip"] == "TAF",
        -(r["zaman"].timestamp() if r.get("zaman") else 0)))
    # SIRA: once GUNCEL raporlar, sonra GECMIS egilim. Trend bolumu
    # eskiden en ustteydi, yani 6 saatlik gecmis su anki gozlemden once
    # okunuyordu.
    # GUNCEL RAPOR GOVDEDEN ONCE cozuluyor: trend bolumu, tavan sayisi
    # yokken "tavan yok" mu yoksa "raporlanmiyor" mu yazacagini buna
    # bakarak seciyor (bkz. _tavan_yoklugu).
    guncel_rapor = next((r for r in sirali if r["tip"] in ("METAR", "SPECI")), None)
    guncel_cozum = metar_coz(guncel_rapor["metin"]) if guncel_rapor else None

    govde = (("".join(_kart(r, yorum_onbellegi, gecmis, simdi) for r in sirali)
              or "<div class='kart'>Rapor yok.</div>")
             + _trend_bolumu(gecmis, _tavan_yoklugu(guncel_cozum),
                             guncel_rapor.get("zaman") if guncel_rapor else None))
    icao = raporlar[0].get("icao", "LTFJ") if raporlar else "LTFJ"
    # Ust seritteki renk rozeti kartlarla AYNI hesaptan gelsin diye
    # havacilik_notlari burada bir kez daha cagriliyor (saf fonksiyon,
    # ag/dosya erisimi yok); rozetin karttakinden sessizce sapmamasi icin.
    guncel_notlar = (havacilik_notlari(guncel_cozum, guncel_rapor["metin"],
                                       guncel_rapor.get("zaman"))
                     if guncel_cozum else None)
    guncel_taf_rapor = next((r for r in sirali if r["tip"] == "TAF"), None)
    taf_tavan = (farkindalik.taf_en_dusuk_tavan_ft(guncel_taf_rapor["metin"])
                 if guncel_taf_rapor else None)

    hedef.write_text(
        _sablonu_doldur(dict(icao=html.escape(icao), govde=govde,
                      yazitipi_css=YAZITIPI_CSS,
                      ikon_zil=ikon("zil"), ikon_yenile=ikon("yenile"),
                      ikon_uyari=ikon("uyari", "ikon ikon-uyari"),
                      ikon_kapat=ikon("kapat"), ikon_not=ikon("not", "ikon ikon-fab"),
                      # JS icine DIZE olarak gomulecek - json.dumps dogru
                      # kacislari yapar, elle tirnak kapatmaya calismayiz.
                      ikon_zil_js=json.dumps(ikon("zil")),
                      ikon_zil_kapali_js=json.dumps(ikon("zil-kapali")),
                      gozlem_taze_dk=GOZLEM_TAZE_DK,
                      notam_bayat_saat=notam_bayat_saat(),
                      # LTFJ icin GERCEK gun dogumu/batimi
                      # (ltfj_pist._gunes_saatleri). Gun/gece karari
                      # ISTEMCIDE veriliyor - sayfa acik kalabiliyor.
                      gun_dogumu=_gunes_iso(simdi)[0],
                      gun_batimi=_gunes_iso(simdi)[1],
                      gozlem_beklenen_dk=GOZLEM_BEKLENEN_DK,
                      sessizlik_saat=SESSIZLIK_SAAT,
                      # Basliktaki durum gostergesi ve yas seridi BU iki
                      # damgaya gore ISTEMCIDE hesaplanir. Zaman yoksa bos
                      # dize gider ve JS "VERI YOK" gosterir - uydurma bir
                      # zaman yazmaktansa bilinmedigini soylemek dogru.
                      son_gozlem_iso=(guncel_rapor["zaman"].isoformat()
                                      if guncel_rapor and guncel_rapor.get("zaman") else ""),
                      son_taf_iso=(guncel_taf_rapor["zaman"].isoformat()
                                   if guncel_taf_rapor and guncel_taf_rapor.get("zaman") else ""),
                      guncelleme=_zaman_metni(simdi, tarihli=True),
                      atc_notes_db_url=json.dumps(atc_notes_db_url or ""),
                      push_vapid_public_key=json.dumps(push_vapid_public_key or ""),
                      ozet_serit_html=_ozet_serit_html(
                          guncel_cozum, guncel_notlar),
                      durum_kodu_html=_vfr_bandi_html(guncel_cozum),
                      # Hero artik kartin degil SAYFANIN ogesi: guncel
                      # cozumden bir kez uretilip tepeye konuyor.
                      hero_html=(_hero_html(guncel_cozum, gecmis, simdi)
                                 if guncel_cozum else ""),
                      lvo_referans_html=_lvo_dokuman_referans_html(),
                      lvo_farkindalik_html=_lvo_farkindalik_html(
                          guncel_cozum, taf_tavan, gecmis, simdi),
                      beklenti_html=_beklenti_html(
                          _saatlik_tahmin_html(saatlik_tahmin or [],
                                               yas_dk=tahmin_yas_dk)),
                      istatistik_html=_istatistik_html(
                          _sis_olasiligi_html(guncel_cozum, gecmis, simdi),
                          _tavan_istatistik_notlari(guncel_cozum, gecmis, simdi)),
                      sekme_cubugu_html=_sekme_cubugu_html(
                          _sis_olasilik_rozeti(guncel_cozum, gecmis, simdi)),
                      rvr_esikleri_json=json.dumps(lvo.RVR_ESIKLERI, ensure_ascii=False),
                      lvo_q_konulari_json=json.dumps(list(ltfj_notam.LVO_Q_KONULARI)),
                      vfr_html=_vfr_sekmesi_html(guncel_cozum))),
        encoding="utf-8")
    print(f"  web sayfası yazıldı: {hedef.name}")
