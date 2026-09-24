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
import ltfj_lvo_referans as lvo
import ltfj_gorus_gecis_tablo as gecis_tablo
import ltfj_sis_olasilik as sis_olasilik
import ltfj_sis_olasilik_b as sis_olasilik_b
import ltfj_vfr as vfr
from ltfj_analiz import metar_coz, ozet_satiri, uyarilar
# Sis kodlari alanin KENDI tanimiyla ayni yerde dursun - bu oturumda
# kopyalanmis bir sabit (NOTAM gecerlilik karari) iki yerde ayni hatayi
# tasidi, tekrarlamayalim. ltfj_rasat zaten import edildigi icin ek bir
# agir bagimlilik gelmiyor.
from ltfj_dis_kaynak_cache import SIS_KODLARI
from ltfj_ayarlar import (GOZLEM_BEKLENEN_DK, GOZLEM_TAZE_DK,
                          SESSIZLIK_SAAT, YEREL_TZ)
import ltfj_pist as pist
from ltfj_pist import havacilik_notlari
from ltfj_rasat import taf_bicimle

# ltfj_bot.py::ETIKET/_yorumu_bicimle ile AYNI etiket kumesi - ama bu web'e
# ozel bir bicimlendirici (Telegram HTML "\n" ile, web "<br>" ile ayrilir).
# Burada YENI bir Claude cagrisi YAPILMAZ - sadece state.yorum_onbellegi'nde
# (Telegram icin) zaten hesaplanmis metin okunur (bkz. _kart/sayfa_yaz).
_ETIKET = re.compile(r"^(Rüzgâr|Görüş|Gökyüzü|Uçuşa etkisi|Genel|Dikkat)\s*:\s*(.+)$")

RENK_KODU = {
    "BLU": "#3b82f6", "WHT": "#94a3b8", "GRN": "#22c55e",
    "YLO": "#eab308", "AMB": "#f97316", "RED": "#ef4444",
}

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


SABLON = """<!DOCTYPE html>
<html lang="tr" data-gun-dogumu="{gun_dogumu}" data-gun-batimi="{gun_batimi}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{icao} · Hava Durumu</title>
<meta name="description" content="{icao} anlık METAR ve TAF">
<style>
{yazitipi_css}
  /* ===================== TASARIM SISTEMI =====================
     TEK KAYNAK. Once her anlamsal renk sayfaya DAGILMIS sabit hex olarak
     duruyordu: ornegin "dikkat" tonu (#b45309 acik / #fbbf24 koyu) UC AYRI
     kuralda, her biri ayrica iki koyu tema blogunda tekrarlanmisti - dokuz
     yer. Birini guncelleyip otekileri unutmak an meselesiydi.

     KATMANLAR: zemin -> panel -> kart -> etkilesim. Her katman bir ustune
     gore hafifce ayrisir; koyu temada saf siyah ve asiri kontrast YOK.

     ANLAMSAL RENKLER durum anlatir, dekorasyon degildir. "-zemin" varyanti
     rozet/kutu arka plani, duz olani metin/kenarlik icindir.

     NOT: RENK_KODU (BLU/WHT/GRN/YLO/AMB/RED) BURAYA TASINMADI - o bir
     HAVACILIK DURUM KODU, arayuz rengi degil; Telegram tarafiyla ayni
     kavrami paylasiyor ve tema degistirince degismemeli. */
  :root {{
    /* Mono yigini eskiden 6 ayri yerde KOPYALANMISTI - biri guncellenip
       otekiler unutulabilirdi. Tek kaynak. */
    --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;

    /* yuzey katmanlari */
    /* #f8fafc -> #eef2f7: kartlar (beyaz) zeminden daha net
       ayrissin. Kontrast metin/zemin oranlarini DUSURMEZ -
       metin kart uzerinde duruyor, zemin degismedi. */
    --bg:#eef2f7; --panel:#e6ecf3; --kart:#ffffff; --etkilesim:#e6ecf3;
    --cizgi:#e2e8f0; --kod-bg:#f1f5f9;
    /* metin */
    --metin:#0f172a; --soluk:#64748b; --sessiz:#94a3b8; --vurgu:#0f172a;
    /* anlamsal - durum anlatir */
    /* Metin tonlari OLCULEREK secildi - WCAG AA (4.5:1), kendi "-zemin"
       tonlarinin uzerinde. Onceki degerler (#16a34a / #dc2626) acik temada
       2.89:1 ve 3.97:1 veriyordu, yani AA'nin altindaydi. */
    /* FAB yuzeyi: acik temada koyu disk, koyu temada YUKSELTILMIS
       YUZEY. Tek kural (--vurgu/--bg) kullanilinca koyu temada FAB
       neredeyse beyaz oluyordu (olculen bagil parlaklik 0.853, hero
       0.023 - 37 kat). Gece karartilmis bir kulede ekranin en parlak
       nesnesi "not ekle" dugmesi olmamali. */
    /* MARKA TONU - ANLAM TASIMAZ. Grafik cizgisi, secili sekme
       gostergesi ve odak halkasi icin; durum ASLA bu tonla
       anlatilmaz. Mor secildi cunku durum hue'lari (kirmizi 15,
       turuncu 30, sari 50, yesil 140, mavi 250 derece) arasindaki
       EN GENIS bosluk orada. Olculdu (OKLab ΔE, rehberin
       normal-gorus tabani 15): en yakin durum rengine 15.8;
       kontrast acik yuzeyde 8.98, koyuda 7.24 (cizgi icin
       gereken 3:1'in cok ustunde). */
    --marka:#5b21b6;
    --fab-zemin:#0f172a; --fab-metin:#f8fafc; --fab-cizgi:transparent;
    /* Kart golgesi: acik temada kagit degil KONSOL hissi icin.
       Koyu temada golge yok - siyah uzerine golge gorunmez ve
       parlaklik eklemek gece kullanimini bozardi; orada derinlik
       yuzey basamaklarindan (--bg < --panel < --kart) geliyor. */
    --golge:0 1px 2px rgba(15,23,42,.04), 0 2px 8px rgba(15,23,42,.05);
    --golge-yukari:0 2px 4px rgba(15,23,42,.05), 0 6px 20px rgba(15,23,42,.07);
    --iyi:#166534;    --iyi-zemin:#22c55e26;    --iyi-dolu:#22c55e;
    --dikkat:#b45309; --dikkat-zemin:#f59e0b26; --dikkat-dolu:#f59e0b;
    --uyari:#ef4444;  --uyari-zemin:#ef444426;  --uyari-metin:#b91c1c;
    --bilgi:#2563eb;  --bilgi-zemin:#3b82f626;
    /* TIPOGRAFI OLCEGI - 6 ADIM.
       Olculdu: tek telefon ekraninda 17 FARKLI punto vardi ve 11'i
       9.9-14.1px arasina sikismisti; o araliktaki farki goz zaten
       ayirt etmiyor, yani 11 ayri karar sifir hiyerarsi kazanci
       veriyordu. Asil sorun ustteki bosluktu: 16.8px ile 24px arasinda
       HICBIR SEY yoktu, yani sayfada sadece uc gercek katman vardi -
       "hero", "baslik" ve "geri kalan her sey". Ikincil ama onemli bir
       seyi (hamle, QNH, pist ruzgari) vurgulamak icin elde arac yoktu.
       f4/f5 tam o boslugu dolduruyor. */
    --f1:.6875rem;   /* 11px - birim, etiket, dipnot           */
    --f2:.8125rem;   /* 13px - ikincil govde, tablo, rozet     */
    --f3:.9375rem;   /* 15px - govde                           */
    --f4:1.125rem;   /* 18px - bolum basligi, h1               */
    --f5:1.375rem;   /* 22px - vurgu (dar ekranda hero)        */
    --f6:1.75rem;    /* 28px - hero                            */
    /* olcek */
    --r1:8px; --r2:12px; --r3:16px;
  }}
  /* Koyu tema iki yerde tanimli olmak ZORUNDA: biri sistem tercihi, oteki
     elle secim (data-theme). Ikisi ayni listeyi tasir - listeyi TOKEN'a
     indirgemenin asil kazanci da bu: artik tek satir kopyalaniyor. */
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg:#0b1220; --panel:#0f1729; --kart:#111a2e; --etkilesim:#1e2a44;
      --cizgi:#1e2a44; --kod-bg:#0a1120;
      --metin:#e8eefc; --soluk:#8fa0bf; --sessiz:#64748b; --vurgu:#e8eefc;
      --iyi:#4ade80; --dikkat:#fbbf24; --uyari-metin:#f87171;
      --bilgi:#60a5fa;
      --marka:#b39ddb;
      --fab-zemin:#1e2a44; --fab-metin:#e8eefc; --fab-cizgi:#31405f;
      --golge:none; --golge-yukari:none;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg:#0b1220; --panel:#0f1729; --kart:#111a2e; --etkilesim:#1e2a44;
    --cizgi:#1e2a44; --kod-bg:#0a1120;
    --metin:#e8eefc; --soluk:#8fa0bf; --sessiz:#64748b; --vurgu:#e8eefc;
    --iyi:#4ade80; --dikkat:#fbbf24; --uyari-metin:#f87171;
    --bilgi:#60a5fa;
    --marka:#b39ddb;
    --fab-zemin:#1e2a44; --fab-metin:#e8eefc; --fab-cizgi:#31405f;
    --golge:none; --golge-yukari:none;
  }}
  /* Hareket azaltma tercihi: isletim sisteminde acan kullanici icin tum
     gecis ve animasyonlar durur. Sayfa islevini KAYBETMEZ - donen ok yine
     doner, sadece aninda. */
  @media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{
      animation-duration:.01ms !important; animation-iteration-count:1 !important;
      transition-duration:.01ms !important; scroll-behavior:auto !important;
    }}
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; background:var(--bg); color:var(--metin);
    /* 1.55 -> 1.62: sayfadaki uzun Turkce uyari paragraflari icin
       gozu dinlendiren asil degisiklik satir araligi. */
    /* Govde punto'su da OLCEKTEN. 16px birakilinca acikca boyut
       verilmeyen ogeler olcek disina dusuyordu (olculdu: 2 oge). rem
       koke gore hesaplandigi icin bunu degistirmek --fN degerlerini
       ETKILEMEZ, yalnizca mirasla gelen metni hizalar. */
    font:var(--f3)/1.62 "IBM Plex Sans",ui-sans-serif,system-ui,-apple-system,
         "Segoe UI",Roboto,sans-serif;
    -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
    padding:24px 16px 48px;
  }}
  .sar {{ max-width:680px; margin:0 auto; }}
  header {{
    margin-bottom:20px; display:flex; align-items:flex-start;
    justify-content:space-between; gap:12px;
  }}
  .header-metin {{ min-width:0; }}
  /* Ö4: 1.5rem (24px) iken hero sayilariyla (24px w650) AYNI boydaydi.
     Istasyon kodu SABIT bilgi - ilk saniyeden sonra sifir bilgi tasir;
     dort olcumle ayni gorsel agirlikta olmasi icin sebep yok. 18px
     teyit icin fazlasiyla yeterli ve olcegin (Ö5) bir adimi. */
  h1 {{ font-size:var(--f4); margin:0 0 4px; letter-spacing:-.01em; }}
  .alt {{ color:var(--soluk); font-size:var(--f3); }}
  button.yenile {{
    flex-shrink:0; background:var(--kod-bg); border:1px solid var(--cizgi);
    color:var(--soluk); border-radius:8px; padding:8px 12px; font:inherit;
    font-size:var(--f2); font-weight:650; cursor:pointer; white-space:nowrap;
  }}
  button.yenile:hover {{ color:var(--metin); border-color:var(--vurgu); }}
  button.yenile:disabled {{ opacity:.6; cursor:default; }}
  .header-butonlar {{ display:flex; gap:8px; flex-shrink:0; }}
  @media (max-width:480px) {{
    header {{ flex-wrap:wrap; }}
    .header-metin {{ flex:1 1 100%; }}
    /* VFR SEKMESININ OLUGUNU AYIR. Sekme position:fixed, sag kenarda
       ve 29px genis; bu kirilimin altinda dugmeler ikinci satira inip
       tam sekmenin dikey bandina (96-144px) denk geliyordu. Olculdu:
       390px'te "Yenile"nin sag 13px'i sekmenin altinda kaliyordu -
       yani dugmenin o seridine basan parmak Yenile'yi degil VFR
       panelini aciyordu. 481px ve ustunde dugmeler ust satirda kaldigi
       icin (y=24-63) dikey ortusme zaten yok; bu yuzden dolgu SADECE
       burada. */
    .header-butonlar {{
      flex:1 1 100%; justify-content:flex-end; padding-right:34px;
    }}
    button.yenile {{ padding:8px 10px; font-size:var(--f2); }}
  }}
  /* YAPISKAN UST = ozet serit + sekme cubugu, TEK sticky blok.
     Ikisini ayri ayri yapiskan yapmak, sekme cubuguna "serit ne kadar
     yuksek?" diye bir top: degeri uydurmayi gerektirirdi; serit dar
     ekranda satir kaydirdigi icin o sayi sabit DEGIL. Tek sarmal bu
     sorunu tamamen ortadan kaldiriyor.
     z-index kasitli olarak 40: sayfa icerigiNIN ustunde, ama sabit
     kapli katmanlarin (VFR sekmesi 58, ATC modali 65) ALTINDA. */
  /* SU AN blogu - hero'nun yeni evi. Kart icinde degil, sayfanin
     tepesinde; kenarlik kartlarla ayni dilde ama baslik satiri yok
     (sekme cubugu ve baslik zaten baglami veriyor). */
  .su-an {{ margin:10px 0 0; }}
  .su-an .hero {{ margin:0; }}
  /* Serit, hero gorunurken GIZLI. .js sinifi <head>'de ekleniyor, yani
     JS varsa serit hic cizilmeden basliyor - acilista yanip sonme yok.
     JS yoksa kural hic uygulanmaz ve ikisi de gorunur kalir. */
  .js .ozet-serit {{ display:none; }}
  .js .yapiskan-ust.serit-acik .ozet-serit {{ display:flex; }}
  .yapiskan-ust {{
    position:sticky; top:0; z-index:40;
    background:var(--bg); margin:0 0 16px; padding-top:2px;
  }}
  .ozet-serit {{
    display:flex; align-items:center; gap:8px; flex-wrap:wrap;
    margin:0; padding:9px 12px;
    background:var(--kart); border:1px solid var(--cizgi); border-radius:12px;
    font-size:var(--f2); font-variant-numeric:tabular-nums;
  }}
  /* Renk kodu rozeti kart rozetiyle AYNI gorunsun (.rozet ile ayni
     yazi rengi) - iki farkli gorsel dil ayni seyi anlatmasin. */
  .ozet-renk {{
    padding:2px 8px; border-radius:999px; color:#fff;
    font-weight:700; font-size:var(--f2); letter-spacing:.02em;
  }}
  .ozet-oge {{ color:var(--metin); white-space:nowrap; }}
  /* Ayirici nokta: ogeler arasinda, ilkinden once DEGIL. */
  .ozet-oge + .ozet-oge::before {{ content:"·"; color:var(--soluk); margin-right:8px; }}
  @media (max-width:480px) {{
    .ozet-serit {{ font-size:var(--f2); gap:6px; padding:8px 10px; }}
    .ozet-oge + .ozet-oge::before {{ margin-right:6px; }}
  }}

  /* ---- SEKME CUBUGU ----------------------------------------------------
     Bolumler (Durum/Beklenti/Istatistik/LVO/NOTAM) eskiden alt alta
     katlanir basliklardi; sayfa cok uzuyordu. YATAY sekme secildi, dikey
     ray DEGIL: icerik sutunu telefonda ~360px ve soldaki bir ray yatay
     genisligi KALICI olarak yerdi (~%25). Yatay cubuk dikey yerden bir
     kez odun verir, yataydan hic.

     ROZET SART: sekme icerigi GIZLIYOR. NOTAM sayfadayken kaydirirken
     goz ucuyla goruluyordu; sekmenin arkasina girince yeni NOTAM'i fark
     etmenin tek yolu cubuktaki rozet kalir. */
  .sekme-cubugu {{
    display:none;                      /* JS yoksa hic cizilmez - asagi bak */
    gap:2px; margin-top:8px; padding:3px;
    background:var(--kod-bg); border:1px solid var(--cizgi); border-radius:12px;
    overflow-x:auto; scrollbar-width:none; -webkit-overflow-scrolling:touch;
  }}
  .sekme-cubugu::-webkit-scrollbar {{ display:none; }}
  .js .sekme-cubugu {{ display:flex; }}
  .sekme {{
    flex:1 0 auto; min-height:40px; padding:7px 12px;
    background:none; border:0; border-radius:9px; cursor:pointer;
    color:var(--soluk); font:inherit; font-size:var(--f2); font-weight:600;
    white-space:nowrap; display:flex; align-items:center; gap:6px;
    justify-content:center;
  }}
  .sekme[aria-selected="true"] {{
    background:var(--kart); color:var(--metin);
    box-shadow:0 1px 3px rgba(0,0,0,.12);
  }}
  .sekme:focus-visible {{ outline:2px solid var(--metin); outline-offset:-2px; }}
  /* Sekme rozeti: kart rozetiyle AYNI gorsel dil, daha kucuk. */
  .sekme-rozet {{
    font-size:var(--f1); font-weight:700; padding:1px 6px; border-radius:999px;
    background:var(--cizgi); color:var(--metin); font-variant-numeric:tabular-nums;
  }}
  .sekme-rozet:empty {{ display:none; }}
  /* Telefon cubugunda ikon YOK: olculdu, cubuk 360px'te tam kapasitede
     (326/326px) ve ikon eklemek NOTAM'i keserdi. DOM'da duruyor ama
     display:none oldugu icin yer kaplamiyor; rayda aciliyor. */
  .sekme-ikon {{ display:none; }}
  /* Rozet noktasi: rozetin kendi arka plani zaten renk kodu, nokta
     beyaz kalir - iki farkli renk ust uste binmez. */
  .ikon-fab {{ width:22px; height:22px; }}
  .rozet-nokta {{ width:.55em; height:.55em; stroke-width:0; fill:currentColor;
                  margin-right:5px; opacity:.85; }}
  @media (max-width:480px) {{
    /* 360px'te bes sekme + rozetler cubugu tasiriyordu ve NOTAM kismen
       kesiliyordu. Yatay dolgu ve rozet en cok yeri yiyen ikisi. */
    .sekme {{ font-size:var(--f2); padding:7px 4px; gap:3px; }}
    .sekme-rozet {{ font-size:var(--f1); padding:1px 4px; }}
    .sekme-cubugu {{ gap:1px; padding:2px; }}
  }}

  /* JS YOKSA SAYFA BOZULMAZ: paneller varsayilan olarak GORUNUR ve cubuk
     cizilmez, yani sayfa eski "hepsi alt alta" haline duser. Gizleme
     yalnizca .js sinifi varken devreye girer; o sinifi <head>'deki satir
     ici betik body cizilmeden once ekledigi icin acilista titreme olmaz. */
  /* ---- GENIS EKRANDA SOL RAY -------------------------------------------
     Icerik sutunu 680px'te ortalanir; 1024px ustunde SOLDA 172-380px
     ZATEN BOS alan kalir (olculdu). Ray oraya konunca icerik sutunu
     HIC DARALMAZ - telefonda ray yatay genisligi yerdi, burada yemiyor.
     Bu yuzden ayni <nav> HTML'i, yalnizca CSS ile dikeye donuyor.

     left hesabi: sutunun sol kenari 50% - 340px. Ray onun 16px soluna,
     genisligi 140px -> 50% - 340 - 16 - 140 = 50% - 496px. 1024px'te
     ekranin solunda 16px bosluk kalir, daha genisinde acilir. */
  @media (min-width:1024px) {{
    .js .sekme-cubugu {{
      position:fixed; top:104px; left:calc(50% - 496px);
      width:140px; z-index:40; margin-top:0;   /* top: ne diyorsa o olsun */
      flex-direction:column; gap:2px; padding:4px;
      overflow:visible;          /* dikeyde bes oge hep sigar */
    }}
    .sekme {{
      flex:0 0 auto; justify-content:flex-start; text-align:left;
      padding:9px 10px; gap:9px;
    }}
    /* Rayda 140px var - ikon burada hem siger hem tarama hizini artirir. */
    .sekme-ikon {{ display:block; width:15px; height:15px; opacity:.85; }}
    .sekme[aria-selected="true"] .sekme-ikon {{ opacity:1; }}
    /* Rozet satirin SONUNA yaslansin - etiketler farkli uzunlukta ve
       rozetler hizasiz dururdu. */
    .sekme-rozet {{ margin-left:auto; }}
    /* Ray akistan ciktigi icin yapiskan blokta yalnizca ozet serit kalir;
       altindaki bosluk artik gereksiz. */
    .yapiskan-ust {{ padding-bottom:0; }}
  }}

  /* ---- IKONLAR ---- currentColor: ikon metnin rengini alir, yani her
     tema ve her durum renginde kendiliginden dogru cizilir. */
  .ikon {{
    width:1em; height:1em; flex:0 0 auto; vertical-align:-.125em;
    stroke:currentColor; fill:none; stroke-width:1.9;
    stroke-linecap:round; stroke-linejoin:round;
  }}
  button .ikon {{ margin-right:5px; }}
  /* Uyari kutularinda ikon metne YAPISIK ciziliyordu ("!Bilgi amaclidir").
     button disinda hicbir kural bosluk vermiyordu. Renk de burada: uyari
     kutusunun ikonu govde metniyle ayni griye boyaniyordu. */
  .ikon-uyari {{ margin-right:7px; color:var(--dikkat); vertical-align:-.16em; }}

  /* ---- UYGULAMA BASLIGI ---- */
  h1 {{ display:flex; align-items:baseline; gap:9px; flex-wrap:wrap; }}
  .ust-kod {{ font-weight:700; letter-spacing:.03em; }}
  .ust-ad {{ font-size:.72em; font-weight:500; color:var(--soluk); }}
  .ust-durum-sat {{ display:flex; align-items:center; gap:12px; margin-top:5px; }}
  .ust-durum {{
    display:inline-flex; align-items:center; gap:6px;
    font-size:var(--f1); font-weight:700; letter-spacing:.09em; color:var(--soluk);
  }}
  .ust-durum .ikon {{ width:.72em; height:.72em; stroke-width:0; fill:currentColor; }}
  .ust-durum.taze {{ color:var(--iyi); }}
  .ust-durum.gecikmeli {{ color:var(--dikkat); }}
  .ust-durum.kesinti {{ color:var(--uyari-metin); }}
  /* Yanip sonme YALNIZCA taze durumda ve YAVAS: surekli hareket
     operasyonel bir ekranda dikkat dagitir. Hareket azaltma tercihinde
     (yukarida) kendiliginden durur. */
  .ust-durum.taze .ikon {{ animation:ltfj-nabiz 2.6s ease-in-out infinite; }}
  @keyframes ltfj-nabiz {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:.35; }} }}
  .ust-saat {{
    font-family:var(--mono); font-size:var(--f2); color:var(--metin);
    font-variant-numeric:tabular-nums;
  }}
  .ust-saat:empty {{ display:none; }}

  /* ---- VERI TAZELIGI SERIDI ---- */
  .veri-serit {{
    display:flex; flex-wrap:wrap; gap:6px 16px; margin:0 0 16px;
    padding:8px 12px; background:var(--panel); border:1px solid var(--cizgi);
    border-radius:var(--r1); font-family:var(--mono); font-size:var(--f1);
    color:var(--sessiz);
  }}
  .veri-oge {{ display:inline-flex; align-items:center; gap:6px; white-space:nowrap; }}
  .veri-oge b {{ font-weight:400; color:var(--soluk); letter-spacing:.05em; }}
  .veri-oge time {{ color:var(--metin); }}
  .veri-oge.bayat time, .veri-oge.bayat span {{ color:var(--dikkat); }}
  .veri-kaynak {{ margin-left:auto; }}
  @media (max-width:480px) {{
    .veri-serit {{ font-size:var(--f1); gap:4px 12px; }}
    .veri-kaynak {{ margin-left:0; flex-basis:100%; }}
  }}

  /* ---- MEVCUT KOSULLAR (hero) ----
     Telefonda 2x2, >=560px'te tek sirada dort. 1px bosluklar arka plan
     renginden geliyor - ayrik kenarlik yerine tek izgara cizgisi. */
  .hero {{
    display:grid; grid-template-columns:repeat(2,1fr); gap:1px;
    background:var(--cizgi); border:1px solid var(--cizgi);
    border-radius:var(--r1); overflow:hidden; margin:10px 0 12px;
  }}
  @media (min-width:560px) {{ .hero {{ grid-template-columns:repeat(4,1fr); }} }}
  .hero-oge {{ background:var(--kart); padding:10px 12px 8px; color:var(--soluk); }}
  /* Ö6: 9.9px + --sessiz = ACIK temada 2.56:1, koyuda 3.64:1 - ikisi de
     AA'nin (4.5) altinda. Bunlar sayfadaki EN BUYUK dort sayinin ne
     oldugunu soyleyen etiketler; gunes altinda rakam gorunup etiketi
     gorunmuyordu. --soluk ile acikta 4.76:1, koyuda 6.56:1. */
  .hero-etiket {{
    font-size:var(--f1); font-weight:700; letter-spacing:.08em;
    text-transform:uppercase; color:var(--soluk);
  }}
  .hero-deger {{
    font-size:var(--f6); font-weight:650; line-height:1.15; margin-top:2px;
    font-variant-numeric:tabular-nums; color:var(--metin);
  }}
  /* Esik asiminda SAYININ KENDISI degisiyor (bkz. _olcu_bandi).
     Renk TEK BASINA tasiyici degil: yanindaki "sınırlı"/"eşik altı"
     etiketi ayni bilgiyi metinle de veriyor. */
  .hero-deger.hero-dikkat {{ color:var(--dikkat); }}
  .hero-deger.hero-uyari  {{ color:var(--uyari-metin); font-weight:750; }}
  .hero-band-etiket {{
    margin-left:6px; font-size:var(--f1); font-weight:700;
    letter-spacing:.02em; text-transform:none; color:var(--dikkat);
  }}
  /* Band sinifi HUCREDE de duruyor; :has() gerekmiyor. */
  .hero-oge-uyari .hero-band-etiket {{ color:var(--uyari-metin); }}
  /* "bildirilmedi" bir SAYI degil - hero puntosunda sayfanin en buyuk
     yazisi oluyor ve yoklugu olculmus bir degerden baskin gosteriyordu. */
  .hero-deger-metin {{ font-size:var(--f3); font-weight:600; color:var(--soluk); }}
  /* Grafik cizgileri MARKA tonunda - durum rengi DEGIL (bkz.
     GRAFIKLER aciklamasi). currentColor ile miras aliniyor. */
  .grafik {{ color:var(--marka); }}
  .grafik-esik {{
    stroke:var(--soluk); stroke-width:1; stroke-dasharray:4,4; opacity:.7;
  }}
  /* HTML - SVG <text> DEGIL: grafik SVG'si preserveAspectRatio="none"
     ile esniyor, icindeki yazi hem kuculuyor hem yatayda eziliyordu.
     Konum, cizgiyle AYNI olcekten (bkz. _esik_orani) yuzde olarak
     geliyor; zemin cipi altindaki dolguyu kesip yaziyi okunur birakiyor. */
  .grafik-esik-ad {{
    position:absolute; left:0; transform:translateY(-100%);
    font-size:var(--f1); font-family:var(--mono); color:var(--soluk);
    background:var(--kart); padding:0 .3em; border-radius:3px;
    pointer-events:none; white-space:nowrap;
  }}
  /* Kivilcim (hero) de ayni tonda - ama oradaki SVG 100x20, esik cizgisi
     o boyutta okunmaz, o yuzden yalnizca cizgi + dolgu. */
  .hero-kivilcim {{ color:var(--marka); }}
  /* Gun/gece baglami - sis penceresi gece-sabah oldugu icin BILGI. */
  .ust-faz {{
    font-size:var(--f1); color:var(--soluk); letter-spacing:.02em;
    white-space:nowrap;
  }}
  /* BANT GOSTERGESI - degerin BLU..RED bandinda NEREDE durdugu.
     Kutular kotuden iyiye (solda RED) dizilir; dolu kutu bulundugu
     bandi gosterir. Renk TEK TASIYICI DEGIL: konum + kod metni. */
  .bant {{
    display:flex; align-items:center; gap:2px; margin-top:6px;
  }}
  .bant-kutu {{
    flex:1 1 0; height:3px; border-radius:2px; background:var(--cizgi);
  }}
  .bant-aktif {{ background:var(--soluk); }}
  .bant-dikkat .bant-aktif {{ background:var(--dikkat); }}
  .bant-uyari .bant-aktif {{ background:var(--uyari-metin); }}
  .bant-kod {{
    flex:0 0 auto; margin-left:5px; font-family:var(--mono);
    font-size:var(--f1); font-weight:700; color:var(--soluk);
    letter-spacing:.02em;
  }}
  .bant-dikkat .bant-kod {{ color:var(--dikkat); }}
  .bant-uyari .bant-kod {{ color:var(--uyari-metin); }}

  /* PIST DIYAGRAMI - pist ekseni + ruzgar oku + bilesen okumasi.
     Renkler NOTR: bu bir durum gostergesi degil, bir GEOMETRI. Tek
     istisna kuyruk limiti asimi, o da metinle birlikte. */
  .pist-diyagram {{
    display:flex; align-items:center; gap:14px; flex-wrap:wrap;
    margin:12px 0; padding:10px 12px;
    background:var(--kod-bg); border:1px solid var(--cizgi);
    border-radius:var(--r2);
  }}
  /* 1:1 CIZILIYOR. Onceden viewBox 180 birim 132px'e sigdiriliyordu
     (olcek .73) ve 11 birimlik uc adlari ekranda 8.1px'e dusuyordu -
     sayfadaki en kucuk yazinin da altinda. Tipografi testi bunu
     yakaladi. Simdi birim = piksel, yazilar olcekten geliyor. */
  .pd-svg {{
    width:120px; height:120px; max-width:100%; flex:0 0 auto;
    color:var(--metin);
  }}
  .pd-halka {{ fill:none; stroke:var(--cizgi); stroke-width:1; }}
  .pd-pist {{
    stroke:var(--soluk); stroke-width:13; stroke-linecap:butt; opacity:.75;
  }}
  .pd-uc-ad {{
    /* Serit uzerinde duruyorlar - serit rengiyle degil ZEMINLE
       kontrast yapmalilar. */
    font-family:var(--mono); font-size:var(--f1); font-weight:700;
    fill:var(--kart); text-anchor:middle; dominant-baseline:middle;
  }}
  .pd-uc-tercih {{ fill:var(--kart); }}
  .pd-kuzey {{
    /* Pusula kuzeyi: boyutla degil OPAKLIKLA geri cekiliyor ki
       olcegin disina cikmasin. */
    font-size:var(--f1); font-weight:700; fill:var(--sessiz); opacity:.8;
    text-anchor:middle; dominant-baseline:middle;
  }}
  .pd-ok {{ stroke:currentColor; stroke-width:2.4; stroke-linecap:round; }}
  .pd-okuma {{ flex:1 1 120px; min-width:0; }}
  .pd-pist-ad {{
    font-family:var(--mono); font-weight:700; font-size:var(--f4);
    line-height:1.2;
  }}
  .pd-satir {{
    font-size:var(--f2); color:var(--metin); display:flex;
    align-items:baseline; gap:6px; margin-top:2px;
  }}
  .pd-satir b {{ font-family:var(--mono); font-size:var(--f3); }}
  .pd-etiket {{
    font-size:var(--f1); color:var(--soluk); text-transform:uppercase;
    letter-spacing:.06em; min-width:42px;
  }}
  /* Limit asimi: renk TEK TASIYICI degil, altinda metin de var. */
  .pd-satir.pd-asan b, .pd-satir.pd-asan {{ color:var(--uyari-metin); }}
  .pd-not {{ font-size:var(--f1); color:var(--soluk); margin-top:4px; }}

  .hero-birim {{
    font-size:var(--f1); font-weight:500; color:var(--soluk); margin-left:3px;
  }}
  /* currentColor: kivilcim .hero-oge'nin soluk rengini alir, yani her
     temada kendiliginden dogru tonda cizilir. */
  .hero-kivilcim {{ display:block; margin-top:4px; height:20px; width:100%; }}
  .hero-yok {{
    margin-top:4px; height:20px; font-size:var(--f1); color:var(--sessiz);
    display:flex; align-items:center;
  }}
  .ozet-ikincil {{ font-size:var(--f2); color:var(--soluk); margin:0 0 10px; }}
  /* Durum rengi kartin sol kenarinda - liste taranirken once goze carpar. */
  .kart.kart-durum {{ border-left:3px solid var(--durum-renk, var(--cizgi)); }}
  @media (max-width:480px) {{
    .hero-deger {{ font-size:var(--f5); }}
    .hero-oge {{ padding:9px 10px 7px; }}
  }}

  .js .sekme-panel {{ display:none; }}
  .js[data-sekme="durum"]      #panel-durum,
  .js[data-sekme="beklenti"]   #panel-beklenti,
  .js[data-sekme="istatistik"] #panel-istatistik,
  .js[data-sekme="lvo"]        #panel-lvo,
  .js[data-sekme="notam"]      #panel-notam {{ display:block; }}
  .kart {{
    background:var(--kart); border:1px solid var(--cizgi); border-radius:14px;
    padding:18px; margin-bottom:16px; box-shadow:var(--golge);
  }}
  /* "SU AN" blogu sayfanin en onemli ogesi - yuzey hiyerarsisinde de
     en ustte dursun. */
  .su-an .hero {{ box-shadow:var(--golge-yukari); }}
  .basrow {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap;
             margin-bottom:12px; }}
  .tip {{ font-weight:650; font-size:var(--f4); }}
  .zaman {{ color:var(--soluk); font-size:var(--f2); }}
  .rozet {{
    margin-left:auto; padding:3px 10px; border-radius:999px;
    font-size:var(--f2); font-weight:650; color:#fff; white-space:nowrap;
  }}
  .dikkat {{
    background:rgba(239,68,68,.12); border:1px solid rgba(239,68,68,.35);
    border-radius:10px; padding:10px 12px; margin:12px 0; font-size:var(--f3);
  }}
  .ozet {{ color:var(--soluk); font-size:var(--f3); margin:10px 0; }}
  .yorum {{
    background:var(--kod-bg); border:1px solid var(--cizgi); border-radius:10px;
    padding:10px 12px; margin:12px 0; font-size:var(--f3); line-height:1.6;
  }}
  .yorum-etiket {{ color:var(--soluk); font-size:var(--f1); margin-bottom:4px; }}
  .pist-kaynak {{ color:var(--soluk); font-size:var(--f2); margin-top:6px; }}
  table {{ width:100%; border-collapse:collapse; font-size:var(--f3); margin-top:10px; }}
  td {{ padding:7px 0; border-bottom:1px solid var(--cizgi); }}
  td:first-child {{ color:var(--soluk); width:42%; }}
  tr:last-child td {{ border-bottom:none; }}
  pre {{
    background:var(--kod-bg); border:1px solid var(--cizgi); border-radius:10px;
    padding:12px; overflow-x:auto; font-size:var(--f2); line-height:1.5;
    font-family:var(--mono); margin:12px 0 0;
    white-space:pre-wrap; word-break:break-word;
  }}
  /* SOLA YASLI, ortalanmis DEGIL: buradaki yasal uyari telefonda 15+
     satir suruyor ve ortalanmis uzun metinde her satirin sol kenari
     farkli yerden basliyor - goz her satirbasi icin yeniden hizalanmak
     zorunda kaliyor. Kisa bir imza satiri ortalanabilirdi; bu paragraf
     degil. (Sayfadaki tek diger text-align:center, tahmin seridindeki
     tek kelimelik hucreler - orada dogru tercih.) */
  footer {{
    color:var(--soluk); font-size:var(--f2); margin-top:28px;
    text-align:left; text-wrap:pretty;
  }}
  a {{ color:inherit; }}
  .panel-link {{
    display:inline-block; margin-top:12px; padding:7px 14px; border-radius:8px;
    background:var(--vurgu); color:var(--bg); text-decoration:none;
    font-size:var(--f2); font-weight:650;
  }}
  .grafik-ust {{ font-weight:650; margin-bottom:12px; font-size:var(--f3); }}
  .grafik-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:18px 20px; }}
  @media (max-width:480px) {{ .grafik-grid {{ grid-template-columns:1fr; }} }}
  .grafik-baslik {{ display:flex; justify-content:space-between; align-items:baseline;
                     font-size:var(--f2); color:var(--soluk); margin-bottom:4px; }}
  .grafik-son {{ color:var(--metin); font-weight:650; }}
  .grafik-son-yok {{ color:var(--soluk); font-weight:600; font-style:italic; }}
  .grafik {{ width:100%; height:64px; display:block; }}
  .grafik-eksen {{ display:flex; justify-content:space-between;
                    font-size:var(--f1); color:var(--soluk); margin-top:2px; }}
  .grafik-durum-notu {{ font-size:var(--f1); color:var(--soluk); margin-top:4px;
                          font-style:italic; }}
  /* Imlec/parmak altindaki noktanin saat+degerini gosteren balon. Dokunmatik
     cihazda dikey sayfa kaydirma bozulmasin diye touch-action:pan-y - yatay
     surukleme grafigi tarar, dikey kaydirma normal calisir. */
  .grafik-sarmal {{ position:relative; touch-action:pan-y; }}
  .grafik-imlec {{
    position:absolute; top:0; bottom:0; width:1px; background:var(--soluk);
    opacity:.55; pointer-events:none;
  }}
  .grafik-nokta {{
    position:absolute; width:9px; height:9px; border-radius:999px;
    background:var(--metin); border:2px solid var(--kart);
    transform:translate(-50%,-50%); pointer-events:none;
  }}
  .grafik-balon {{
    position:absolute; top:0;
    background:var(--kart); border:1px solid var(--cizgi); border-radius:7px;
    padding:3px 8px; font-size:var(--f2); font-weight:600; white-space:nowrap;
    color:var(--metin); pointer-events:none; z-index:3;
    box-shadow:0 2px 10px rgba(0,0,0,.35);
  }}
  .grafik-imlec[hidden], .grafik-nokta[hidden], .grafik-balon[hidden] {{ display:none; }}

  .sis-olasilik-ust {{ display:flex; align-items:baseline; gap:10px; margin:6px 0 2px; }}
  .sis-olasilik-deger {{
    font-size:var(--f6); font-weight:700; line-height:1.1;
  }}
  .sis-olasilik-bant {{
    font-size:var(--f2); font-weight:650; padding:2px 9px; border-radius:999px;
    text-transform:uppercase; letter-spacing:.03em;
  }}
  .sis-olasilik-bant.dusuk {{ background:var(--iyi-zemin); color:var(--iyi); }}
  .sis-olasilik-bant.orta {{ background:#f9731626; color:#ea580c; }}
  .sis-olasilik-bant.yuksek {{ background:var(--uyari-zemin); color:var(--uyari-metin); }}
  .gecis-tablo {{ width:100%; border-collapse:collapse; font-size:var(--f2);
                  margin-top:8px; font-variant-numeric:tabular-nums; }}
  .gecis-tablo th, .gecis-tablo td {{ padding:6px 4px; text-align:right;
                                      border-bottom:1px solid var(--cizgi); }}
  .gecis-tablo thead th {{ color:var(--soluk); font-weight:650; font-size:var(--f2); }}
  /* Satir basligi SOLA yasli - sayilar saga, etiket sola; karisik
     hizalama tabloyu okunmaz yapardi. */
  .gecis-tablo tbody th {{ text-align:left; font-weight:600; }}
  /* Son satirin alt cizgisi: th iki satirli (etiket + esik) oldugu icin
     td'lerden uzun ciziliyor ve tablonun altinda SADECE ilk sutun
     genisliginde kopuk bir cizgi kaliyordu. Alt kenarlik son satirda
     tamamen kalkiyor - tablonun sonunu zaten bosluk belirtiyor. */
  .gecis-tablo tbody tr:last-child th,
  .gecis-tablo tbody tr:last-child td {{ border-bottom:0; }}
  .gecis-n {{ color:var(--soluk); }}
  .gecis-caption {{ caption-side:top; text-align:left; color:var(--soluk);
                    font-size:var(--f1); padding-bottom:2px; }}
  .gecis-esik {{ display:block; font-weight:400; font-size:var(--f1);
                 color:var(--soluk); }}
  .sis-olasilik-alt {{ font-size:var(--f2); color:var(--soluk); }}
  .sis-olasilik-kiyas {{ font-size:var(--f2); color:var(--soluk); margin-top:6px; }}
  .sis-olasilik-ek {{
    font-size:var(--f2); color:var(--soluk); margin-top:10px; padding-top:8px;
    border-top:1px dashed var(--cizgi);
  }}
  .sis-olasilik-ek .sis-olasilik-bant {{ margin-left:4px; }}
  .sis-olasilik-ek-not {{ font-size:var(--f1); color:var(--soluk); margin-top:4px; }}
  .sis-olasilik-not {{
    font-size:var(--f2); color:var(--soluk); margin-top:10px; line-height:1.5;
    border-top:1px solid var(--cizgi); padding-top:8px;
  }}
  .sis-olasilik-diyagram-btn {{
    margin-top:10px; background:none; border:1px solid var(--cizgi);
    color:var(--vurgu); font-size:var(--f2); font-weight:650; padding:6px 12px;
    border-radius:8px; cursor:pointer;
  }}
  .sis-olasilik-diyagram-btn:hover {{ background:var(--kod-bg); }}

  /* Katlanabilir bolum - LVO/Aktif NOTAM'daki ok'lu baslikla AYNI gorunumu
     verir ama JS gerektirmez (<details> yerlisi). Sayfa 5.9 ekran
     kaydirmaya ulasmisti; METAR/TAF yorumlari, trend grafikleri ve NOTAM
     arama formu varsayilan olarak katlandi - hicbiri SILINMEDI, bir
     dokunusla aciliyor. */
  .kat {{ margin-top:10px; }}
  /* Flex DEGIL: baslik metni uzun rozetle yan yana gelince flex ogesi
     daralip baslik uc satira kiriliyordu. Normal akis +
     mutlak konumlu ok, metnin dogal sarmasina izin verir. */
  .kat > summary {{
    cursor:pointer; user-select:none; list-style:none;
    position:relative; padding-right:20px;
    font-size:var(--f2); color:var(--soluk);
  }}
  .kat > summary::-webkit-details-marker {{ display:none; }}
  .kat > summary::after {{
    content:"▶"; font-size:var(--f1); position:absolute; right:0; top:.2em;
    transition:transform .15s ease; display:inline-block;
  }}
  .kat[open] > summary::after {{ transform:rotate(90deg); }}
  .kat > summary:hover {{ color:var(--metin); }}
  .kat-rozet {{
    font-family:var(--mono); font-size:var(--f2);
    color:var(--metin); font-weight:600; margin-left:8px;
  }}
  /* Kart basligi olarak kullanilan katlanabilir summary - .basrow ile ayni
     tipografi (Trend / NOTAM Geçmişi gibi bolum basliklari icin). */
  .kat-kart > summary {{ font-size:var(--f4); color:var(--metin); font-weight:650; }}
  /* Bir katlanir kartin icindeki alt bolumler - araya ince cizgi girsin ki
     saatlik tahmin ile olasilik karti ayri ayri okunabilsin (eskiden ayri
     kartlardi). Bolum adlari burada YAZILMIYOR: testler bu adlarin sayfada
     bulunup bulunmadigina bakiyor, CSS yorumu yanlis pozitif uretirdi. */
  .alt-bolum {{ padding-top:12px; }}
  .alt-bolum + .alt-bolum {{ margin-top:12px; border-top:1px solid var(--cizgi); }}
  .kat-kart > summary::after {{ font-size:var(--f1); color:var(--soluk); }}

  /* Önümüzdeki saatler şeridi - dar ekranda yatay kaydirilir, dikey
     kaydirmayi bolmesin diye sabit yukseklikli hucreler. */
  .tahmin-uyari {{
    background:rgba(234,179,8,.12); border:1px solid rgba(234,179,8,.4);
    border-radius:10px; padding:8px 10px; margin:8px 0 12px; font-size:var(--f2);
  }}
  /* Tahminin yasi - sadece TAHMIN_YAS_UYARI_DK'yi gecince cizilir.
     Uyari rengi DEGIL: bayat tahmin bir hata degil, sadece bir baglam. */
  .tahmin-yas {{
    margin-left:auto; font-size:var(--f1); color:var(--soluk);
    border:1px solid var(--cizgi); border-radius:999px; padding:2px 8px;
    white-space:nowrap;
  }}
  /* Tahmin TABLOSU. Eskiden her saat bagimsiz bir <div> kolonuydu ve
     kosullu satirlar (sis isareti, sinir tabakasi) satirlari yatayda
     KAYDIRIYORDU - olcum ve gerekce icin bkz. _saatlik_tahmin_html.
     Tablo hizayi yapisal olarak garanti eder. */
  .tahmin-kaydir {{ overflow-x:auto; -webkit-overflow-scrolling:touch; }}
  .tahmin-tablo {{
    border-collapse:collapse; font-variant-numeric:tabular-nums;
    min-width:100%;
  }}
  /* Yatay dolgu OLCULDU: 9px'te tablo 659px cikiyor ve icerik sutunu
     642px oldugu icin son saat 17px kirpiliyordu (masaustunde bile
     kaydirma cubugu). 7px'te dogal genislik 642'nin altina iniyor,
     min-width:100% de kalani sutunlara dagitiyor. Telefonda (320px)
     hala kayar - 10 saatlik serit icin dogru davranis; satir basligi
     yapiskan oldugu icin okunur kaliyor. */
  .tahmin-tablo th, .tahmin-tablo td {{
    padding:5px 7px; text-align:right; white-space:nowrap;
    border-bottom:1px solid var(--cizgi);
  }}
  .tahmin-tablo tbody tr:last-child th,
  .tahmin-tablo tbody tr:last-child td {{ border-bottom:0; }}
  .tahmin-tablo thead th {{ text-align:center; vertical-align:bottom; }}
  /* BASLIK SATIRININ SOL KOSESI de yapiskan olmali. Yoksa tablo yatay
     kayarken satir basliklari (asagida) kayan saatleri maskeliyor ama
     BASLIK SATIRI maskelemiyor: 390px'te 297px kaydirildiginda sol ust
     kosede "02:00"in kuyrugu ("00") gorunuyordu. z-index satir
     basliklarindan (1) BUYUK, cunku bu hucre hem yatay hem dikey
     komsulari ortmeli. */
  .tahmin-tablo thead th:first-child {{
    position:sticky; left:0; z-index:2; background:var(--kart);
  }}
  /* Satir basligi YAPISKAN: telefonda tablo yatay kayarken "bu sayi
     neydi" bilgisi ekrandan cikmasin. Kolon 12 saat uzunlugunda. */
  .tahmin-tablo th[scope="row"] {{
    position:sticky; left:0; z-index:1; background:var(--kart);
    text-align:left; font-weight:600; font-size:var(--f2); color:var(--soluk);
    border-right:1px solid var(--cizgi);
    /* width:1% -> tarayici bu sutunu ICERIGE gore daraltir. Olmadan
       min-width:100%'ten artan bosluğun tamamini ilk sutun yutuyor ve
       saat kolonlari sağa sıkışıyordu. */
    width:1%; padding-right:14px;
  }}
  .tahmin-birim {{
    display:inline-block; margin-left:5px; font-weight:400;
    font-size:var(--f1); opacity:.75;
  }}
  .tahmin-saat {{ font-size:var(--f2); font-weight:650; font-family:var(--mono); }}
  /* Spread en guclu onculer gostergeydi (bkz. sis_modeli/README.md) -
     tabloda da one cikiyor. */
  .tahmin-vurgu td {{ font-size:var(--f3); font-weight:700; color:var(--metin); }}
  .tahmin-tablo td {{ font-size:var(--f2); color:var(--metin); }}
  /* Modelin sis kodu verdigi saat: TUM kolon hafifce boyanir, basligina
     simge+metin gelir. Renk TEK BASINA tasiyici degil - renk korlugunde
     ve tek renkli baskida da "sis" yazisi okunur. */
  .tahmin-sisli {{ background:rgba(234,179,8,.12); }}
  .tahmin-sis {{
    font-size:var(--f1); font-weight:700; color:var(--dikkat);
    margin-top:2px; display:flex; align-items:center; gap:3px;
    justify-content:center;
  }}
  .tahmin-aciklama {{ font-size:var(--f1); color:var(--soluk); margin-top:8px; }}

  .bolum-baslik {{ font-weight:650; font-size:var(--f4); margin:28px 0 12px; }}
  /* Bayat senkron uyarisi - kirmizi DEGIL: liste hala dogru olabilir,
     sadece dogrulanmamis. Kirmizi "yanlis" ima ederdi. */
  .notam-senkron-bayat {{ color:var(--dikkat); font-weight:650; }}
  .notam-uyari {{
    background:rgba(234,179,8,.12); border:1px solid rgba(234,179,8,.4);
    border-radius:10px; padding:10px 12px; margin-bottom:14px; font-size:var(--f2);
  }}
  .notam-kart {{
    border-bottom:1px solid var(--cizgi); padding:12px 0;
  }}
  .notam-kart:last-child {{ border-bottom:none; }}
  .notam-ust {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap;
                margin-bottom:6px; }}
  .notam-no {{ font-weight:650; font-family:var(--mono); }}
  .notam-etiket {{
    padding:2px 8px; border-radius:999px; font-size:var(--f1); font-weight:600;
    background:var(--kod-bg); border:1px solid var(--cizgi); color:var(--soluk);
  }}
  .notam-durum {{ font-size:var(--f2); color:var(--soluk); margin-left:auto; }}
  /* Suresi dolmus / henuz baslamamis NOTAM'in durum etiketi - soluk griden
     ayrilsin ki arama sonuclarinda yururlukte olanla karistirilmasin. */
  .notam-durum-gecmis {{ color:var(--dikkat); font-weight:600; }}
  .notam-aktif-nokta {{
    display:inline-block; width:8px; height:8px; border-radius:999px;
    background:var(--iyi-dolu); box-shadow:0 0 0 2px var(--iyi-zemin); flex-shrink:0;
  }}
  .notam-aktif-baslik {{ cursor:pointer; user-select:none; }}
  .notam-aktif-sayi {{
    color:var(--soluk); font-size:var(--f2); margin-left:auto; margin-right:4px;
  }}
  .notam-ok {{
    font-size:var(--f1); color:var(--soluk); transition:transform .15s ease;
    display:inline-block;
  }}
  .notam-ok.acik {{ transform:rotate(90deg); }}
  .notam-ozet {{ font-size:var(--f3); margin:4px 0; }}
  .notam-metin {{
    background:var(--kod-bg); border:1px solid var(--cizgi); border-radius:8px;
    padding:10px; font-size:var(--f2); line-height:1.5; margin-top:6px;
    font-family:var(--mono); white-space:pre-wrap;
    word-break:break-word;
  }}
  .notam-kaynak {{ font-size:var(--f1); color:var(--soluk); margin-top:6px; }}
  .notam-bos {{ color:var(--soluk); font-size:var(--f3); padding:8px 0; }}
  .notam-arama {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px; }}
  .notam-arama input, .notam-arama select {{
    /* min-width:0 olmadan flex ogesi kendi icerik genisliginin altina
       inemez - dar telefonlarda select'in etiketi kirpiliyordu. */
    flex:1 1 140px; min-width:0; padding:8px 10px; border-radius:8px;
    border:1px solid var(--cizgi);
    background:var(--bg); color:var(--metin); font-size:var(--f2);
  }}
  /* SESSIZ dugme. Eskiden dolu koyu zeminliydi ve NOTAM panelindeki tek
     dolu dugme oydu - yani gozun ilk gittigi yer "filtreyi temizle"
     oluyordu, listenin kendisi degil. Eylem tersine cevrilebilir ve
     ikincil; cerceveli bicim hiyerarsiyi duzeltiyor. Dokunma hedefi
     ayni kaliyor (dikey dolgu degismedi). */
  .notam-arama button {{
    padding:8px 14px; border-radius:8px; border:1px solid var(--cizgi);
    background:transparent; color:var(--soluk); font-weight:600;
    font-size:var(--f2); cursor:pointer;
  }}
  .notam-arama button:hover {{ background:var(--etkilesim); color:var(--metin); }}
  .notam-arama-not {{ color:var(--soluk); font-size:var(--f2); margin:-8px 0 12px; }}

  /* LVO REFERENCE - METAR/NOTAM/ATC Notes'tan gorsel olarak ayri, saf
     bilgi/referans paneli. Hicbir karar uretmez (bkz. ltfj_lvo_referans.py). */
  .lvo-alt-baslik {{
    font-weight:650; font-size:var(--f3); margin:18px 0 8px; display:flex;
    align-items:center; gap:8px;
  }}
  .lvo-alt-baslik:first-child {{ margin-top:0; }}
  .lvo-provenance {{
    display:inline-block; padding:2px 8px; border-radius:999px; font-size:var(--f1);
    font-weight:700; letter-spacing:.02em; background:var(--kod-bg);
    border:1px solid var(--cizgi); color:var(--soluk);
  }}
  .lvo-tablo {{ width:100%; border-collapse:collapse; font-size:var(--f2); margin:6px 0 10px; }}
  .lvo-tablo th, .lvo-tablo td {{
    padding:6px 8px; border-bottom:1px solid var(--cizgi); text-align:left;
    width:auto;
  }}
  .lvo-tablo th {{ color:var(--soluk); font-weight:600; font-size:var(--f1); }}
  .lvo-esik-liste {{ font-size:var(--f2); margin:4px 0 12px; }}
  .lvo-esik-satir {{
    display:flex; justify-content:space-between; gap:10px; padding:6px 0;
    border-bottom:1px solid var(--cizgi);
  }}
  .lvo-esik-satir:last-child {{ border-bottom:none; }}
  .lvo-esik-deger {{ font-weight:650; font-family:var(--mono); }}
  .lvo-not-listesi {{ font-size:var(--f2); color:var(--soluk); margin:8px 0 0; padding-left:18px; }}
  .lvo-not-listesi li {{ margin-bottom:4px; }}
  .lvo-awos-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:10px; }}
  .lvo-awos-kart {{
    border:1px solid var(--cizgi); border-radius:10px; padding:10px 12px; background:var(--kod-bg);
  }}
  .lvo-awos-pist {{ font-weight:650; margin-bottom:6px; }}
  .lvo-awos-deger {{ display:flex; justify-content:space-between; font-size:var(--f2); padding:3px 0; }}
  .lvo-awos-alt {{ font-size:var(--f1); color:var(--soluk); margin-top:6px; }}
  .lvo-stale {{
    color:var(--uyari); font-weight:700; margin-left:6px;
  }}
  .lvo-form {{ display:flex; flex-wrap:wrap; gap:8px; margin:10px 0; align-items:flex-end; }}
  .lvo-form label {{ display:block; font-size:var(--f1); color:var(--soluk); margin-bottom:3px; }}
  .lvo-form input, .lvo-form select {{
    padding:8px 10px; border-radius:8px; border:1px solid var(--cizgi);
    background:var(--bg); color:var(--metin); font-size:var(--f2); width:100%; box-sizing:border-box;
  }}
  .lvo-form-alan {{ flex:1 1 100px; }}
  .lvo-form button {{
    padding:8px 14px; border-radius:8px; border:none; background:var(--vurgu);
    color:var(--bg); font-weight:650; font-size:var(--f2); cursor:pointer; flex-shrink:0;
  }}
  /* Temizleme YIKICI ve PAYLASILAN veriyi siler - kaydet butonuyla ayni
     agirlikta durmasin diye ikincil (cerceveli) gorunum. */
  .lvo-form button.lvo-awos-temizle {{
    background:transparent; color:var(--soluk); border:1px solid var(--cizgi);
  }}
  .lvo-form button.lvo-awos-temizle:hover {{ color:var(--uyari); border-color:var(--uyari); }}
  .lvo-hata {{ color:var(--uyari); font-size:var(--f2); margin-top:6px; min-height:1.1em; }}
  .lvo-esik-kaynak {{ font-size:var(--f1); color:var(--soluk); display:block; margin-top:2px; }}

  .atc-not-ekle-btn {{
    margin-left:auto; padding:6px 12px; border-radius:8px; border:none;
    background:var(--vurgu); color:var(--bg); font-weight:650; font-size:var(--f2);
    cursor:pointer;
  }}
  .atc-not-kalan {{ color:var(--soluk); font-size:var(--f1); margin-top:6px; }}

  /* ATC Notes artik sayfa akisinda degil - sag altta sabit duran bir
     dugmeyle (FAB) acilan yuzen bir panel. Telefonda alttan yukari kayan
     "bottom sheet", genis ekranda dugmenin ustunde sabit bir kart. */
  .atc-fab {{
    position:fixed; right:16px;
    bottom:calc(16px + env(safe-area-inset-bottom, 0px));
    width:56px; height:56px; border-radius:999px;
    /* Dokunma hedefi 56px KALIYOR - degisen yalnizca yuzey. Koyu temada
       kenarlik veriliyor cunku zemin artik sayfayla yakin degerde ve
       dugmenin sinirinin gorunmesi gerekiyor. */
    border:1px solid var(--fab-cizgi);
    background:var(--fab-zemin); color:var(--fab-metin); font-size:var(--f5);
    box-shadow:0 4px 16px rgba(0,0,0,.3); cursor:pointer; z-index:60;
    display:flex; align-items:center; justify-content:center;
  }}
  .atc-fab-rozet {{
    position:absolute; top:-2px; right:-2px; min-width:20px; height:20px;
    padding:0 5px; border-radius:999px; background:var(--uyari); color:#fff;
    font-size:var(--f1); font-weight:700; display:flex; align-items:center;
    justify-content:center; border:2px solid var(--bg);
  }}
  .atc-fab-rozet[hidden] {{ display:none; }}
  .atc-panel-ortu {{
    position:fixed; inset:0; background:rgba(0,0,0,.55); z-index:55;
    display:flex; align-items:flex-end; justify-content:center;
  }}
  .atc-panel-ortu[hidden] {{ display:none; }}
  .atc-panel {{
    background:var(--kart); border:1px solid var(--cizgi);
    border-radius:16px 16px 0 0; width:100%; max-width:480px;
    max-height:min(78vh, 640px); display:flex; flex-direction:column;
    padding-bottom:env(safe-area-inset-bottom, 0px);
  }}
  .atc-panel-ust {{
    display:flex; align-items:center; gap:10px; padding:16px 16px 10px;
    border-bottom:1px solid var(--cizgi); flex-shrink:0;
  }}
  .atc-panel-ust .tip {{ font-weight:650; font-size:var(--f4); }}
  .atc-panel-kapat {{
    width:32px; height:32px; border-radius:999px; border:none; flex-shrink:0;
    background:var(--kod-bg); color:var(--metin); font-size:var(--f4); cursor:pointer;
    display:flex; align-items:center; justify-content:center;
  }}
  .atc-panel-govde {{ overflow-y:auto; padding:14px 16px 20px; -webkit-overflow-scrolling:touch; }}
  .atc-panel .notam-uyari {{ margin-top:0; }}
  @media (min-width:640px) {{
    .atc-panel-ortu {{ align-items:flex-end; justify-content:flex-end; padding:0 16px; }}
    .atc-panel {{
      margin-bottom:calc(84px + env(safe-area-inset-bottom, 0px));
      border-radius:16px; box-shadow:0 8px 32px rgba(0,0,0,.35);
      max-height:min(70vh, 600px);
    }}
  }}
  .modal-ortu {{
    position:fixed; inset:0; background:rgba(0,0,0,.55); display:flex;
    align-items:center; justify-content:center; padding:16px; z-index:65;
  }}
  .modal-ortu[hidden] {{ display:none; }}
  .modal-kutu {{
    background:var(--kart); border:1px solid var(--cizgi); border-radius:14px;
    padding:20px; max-width:420px; width:100%;
  }}
  .modal-kutu-genis {{ max-width:820px; max-height:90vh; overflow:auto; }}
  .modal-kutu-genis img {{ width:100%; height:auto; border-radius:8px; display:block; }}
  .modal-kutu h3 {{ margin:0 0 4px; font-size:var(--f4); }}
  .modal-kutu label {{ display:block; font-size:var(--f2); color:var(--soluk); margin:12px 0 4px; }}
  .modal-kutu input, .modal-kutu textarea {{
    width:100%; padding:8px 10px; border-radius:8px; border:1px solid var(--cizgi);
    background:var(--bg); color:var(--metin); font-size:var(--f3); font-family:inherit;
    box-sizing:border-box; resize:vertical;
  }}
  .modal-hata {{ color:var(--uyari); font-size:var(--f2); margin-top:8px; min-height:1.1em; }}
  .modal-butonlar {{ display:flex; gap:8px; justify-content:flex-end; margin-top:14px; }}
  .modal-butonlar button {{
    padding:8px 16px; border-radius:8px; border:none; font-weight:650; font-size:var(--f2);
    cursor:pointer;
  }}
  #atc-not-kaydet {{ background:var(--vurgu); color:var(--bg); }}
  #atc-not-iptal {{ background:var(--kod-bg); color:var(--metin); border:1px solid var(--cizgi); }}
  #atc-not-kaydet:disabled {{ opacity:.6; cursor:default; }}

  /* Sayfa kenarinda kucuk VFR gosterge sekmesi - EN SON METAR/SPECI'nin
     gorus/tavaninin VFR esikleriyle karsilastirilmis sonucunu yesil/kirmizi
     gosterir, tiklaninca sebepleri acan kucuk bir panel acilir. */
  .vfr-sekme {{
    position:fixed; top:96px; right:0; z-index:58; border:none;
    padding:10px 7px; border-radius:10px 0 0 10px; color:#fff;
    font-weight:700; font-size:var(--f2); letter-spacing:.05em; cursor:pointer;
    writing-mode:vertical-rl; text-orientation:mixed;
    box-shadow:0 2px 10px rgba(0,0,0,.3);
  }}
  /* Zeminler KOYULASTIRILDI. Olculen: beyaz yazi uzerinde
     #22c55e = 2.28:1 (sayfadaki EN DUSUK kontrast, hem de emniyetle
     en ilgili gostergede), #ef4444 = 3.76:1. Ikisi de AA'nin (4.5)
     altindaydi. Ton korundu, yalnizca deger dusuruldu:
       #15803d = 5.02:1   #b91c1c = 6.47:1   #475569 = 7.58:1
     .vfr-nokta renkleri DEGISMEDI: onlar kart zemininde duran kucuk
     daireler, uzerlerinde yazi yok - metin kontrasti kurali onlara
     uygulanmaz. */
  .vfr-sekme.vfr-yesil {{ background:#15803d; }}
  .vfr-sekme.vfr-kirmizi {{ background:#b91c1c; }}
  .vfr-sekme.vfr-bilinmiyor {{ background:#475569; }}
  .vfr-panel-ortu {{
    position:fixed; inset:0; background:rgba(0,0,0,.55); z-index:62;
    display:flex; align-items:flex-start; justify-content:flex-end; padding:16px;
  }}
  .vfr-panel-ortu[hidden] {{ display:none; }}
  .vfr-panel {{
    background:var(--kart); border:1px solid var(--cizgi); border-radius:14px;
    max-width:340px; width:100%; padding:16px; margin-top:80px;
    box-shadow:0 8px 32px rgba(0,0,0,.35);
  }}
  .vfr-panel-ust {{ display:flex; align-items:center; gap:10px; }}
  .vfr-panel-ust h3 {{ margin:0; font-size:var(--f4); display:flex; align-items:center; gap:8px; flex:1; }}
  .vfr-nokta {{ width:10px; height:10px; border-radius:999px; display:inline-block; flex-shrink:0; }}
  .vfr-nokta.yesil {{ background:#22c55e; }}
  .vfr-nokta.kirmizi {{ background:#ef4444; }}
  .vfr-nokta.bilinmiyor {{ background:#64748b; }}
  .vfr-panel ul {{ margin:10px 0 0; padding-left:18px; font-size:var(--f2); }}
  .vfr-panel .vfr-esik {{ color:var(--soluk); font-size:var(--f1); margin-top:10px; }}
</style>
<script>
  /* SATIR ICI ve GOVDE CIZILMEDEN ONCE olmak ZORUNDA: paneller varsayilan
     gorunur durumda cizilir (JS'siz tarayici icin). .js sinifini burada
     eklemezsek acilista tum paneller bir kare gorunup sonra kaybolur.
     Kayitli sekme de burada okunur ki dogru panel ILK karede acik olsun. */
  (function () {{
    var k = document.documentElement;
    k.className += " js";
    var gecerli = ["durum", "beklenti", "istatistik", "lvo", "notam"];
    var s = "durum";
    try {{
      var v = localStorage.getItem("ltfj-sekme");
      if (gecerli.indexOf(v) !== -1) {{ s = v; }}
    }} catch (e) {{}}          /* gizli sekmede localStorage atabilir */
    k.setAttribute("data-sekme", s);

    /* GECE = KOYU TEMA. Gun dogumu/batimi LTFJ icin GERCEKTEN
       hesaplanmis (ltfj_pist._gunes_saatleri); uydurma bir "aksam
       oldu" tahmini degil. Kullanicinin ACIK tercihi (data-theme)
       varsa ona DOKUNULMAZ - bu yuzden yalnizca oznitelik yokken
       yaziliyor. Karar ISTEMCIDE veriliyor cunku sayfa bir vardiya
       boyunca acik kalabiliyor; sunucuda gomulu bir "gunduz" etiketi
       saat 21:00'de yalan olurdu. */
    try {{
      var dogus = Date.parse(k.getAttribute("data-gun-dogumu") || "");
      var batim = Date.parse(k.getAttribute("data-gun-batimi") || "");
      if (!isNaN(dogus) && !isNaN(batim) && !k.getAttribute("data-theme")) {{
        var t = Date.now();
        k.setAttribute("data-faz", (t >= dogus && t < batim) ? "gunduz" : "gece");
        if (t < dogus || t >= batim) {{ k.setAttribute("data-theme", "dark"); }}
      }}
    }} catch (e) {{}}
  }})();
</script>
</head>
<body>
<div class="sar">
<header>
  <div class="header-metin">
    <h1><span class="ust-kod">{icao}</span><span class="ust-ad">İstanbul Sabiha Gökçen</span></h1>
    <!-- Durum gostergesi SUNUCUDA degil ISTEMCIDE hesaplanir: sayfa
         saatlerce acik kalabiliyor ve sunucuda yazilan "canli" etiketi
         zamanla yalan olurdu. data-gozlem en yeni METAR/SPECI zamani. -->
    <div class="ust-durum-sat">
      <span class="ust-durum" id="ust-durum" data-gozlem="{son_gozlem_iso}"
            role="status"></span>
      <span class="ust-saat" id="ust-saat" title="Eşgüdümlü Evrensel Zaman"></span>
      <!-- Gun/gece: sis penceresi gece-sabah oldugu icin bu BILGI,
           dekor degil. Metni JS dolduruyor (sayfa acik kalabilir). -->
      <span class="ust-faz" id="ust-faz"></span>
    </div>
  </div>
  <div class="header-butonlar">
    <!-- Ikon ve metin AYRI: JS yalnizca metni degistirir. textContent
         dugmenin tamamini ezseydi SVG ikon da silinirdi. -->
    <button type="button" class="yenile" id="bildirim-izin-btn" hidden>
      <span id="bildirim-ikon">{ikon_zil}</span><span id="bildirim-metin">Bildirimler</span></button>
    <button type="button" class="yenile" id="sayfa-yenile-btn">
      {ikon_yenile}Yenile</button>
  </div>
</header>
<!-- Veri tazeligi seridi: hangi kaynak ne kadar eski. Brief'in istedigi
     "DATA STATUS" bolumunun sikistirilmis hali - dekoratif bir "LIVE"
     etiketi yerine OLCULEN yaslar. -->
<div class="veri-serit">
  <span class="veri-oge"><b>METAR</b><time id="veri-metar"
        data-zaman="{son_gozlem_iso}"></time></span>
  <span class="veri-oge"><b>TAF</b><time id="veri-taf"
        data-zaman="{son_taf_iso}"></time></span>
  <span class="veri-oge"><b>NOTAM</b><span id="veri-notam">—</span></span>
  <span class="veri-oge veri-kaynak">MGM · sayfa {guncelleme}</span>
</div>
<!-- SU AN blogu: dort ana olcu, sayfanin tepesinde ve KART DISINDA.
     Ayni dort olcu eskiden hem burada (serit) hem de METAR kartinin
     icinde (hero) vardi - ikisi ayni ekranda, farkli bicimlerde. Artik
     tek yerde ve tek bicimde (bkz. _olcu). Serit KALDIRILMADI: hero
     kaydirinca ekrandan cikiyor, serit yapiskan. Ikisi ayni anda
     gorunmesin diye serit yalnizca hero ekrandan CIKINCA aciliyor
     (asagidaki IntersectionObserver). JS yoksa ikisi de gorunur -
     eski davranis, bilgi kaybi yok. -->
<div class="su-an" id="su-an">{hero_html}</div>
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
    <div class="notam-arama" id="notam-aktif-filtre">
      <input type="text" id="notam-aktif-q" placeholder="Numara, pist, anahtar kelime…">
      <select id="notam-aktif-kategori"><option value="">Tüm kategoriler</option></select>
      <select id="notam-aktif-eleman"><option value="">Tüm elemanlar</option></select>
      <button type="button" id="notam-aktif-temizle">Temizle</button>
    </div>
    <div id="notam-aktif-liste"><div class="notam-bos">Yükleniyor…</div></div>
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
  Bu sayfa otomatik üretilir. Operasyonel kullanım için resmî kaynaklara başvurun.
  Renk rozetleri (BLU/WHT/GRN/YLO/AMB/RED) resmî bir ICAO CAT I/II/III kategorisi
  değil, bu botun kendi durum seviyesidir. "Meteorolojik tercih" bir ATC pist
  ataması değildir. NOTAM bölümü NOTAC kaynaklıdır, resmî NOTAM/PIB'in yerine
  geçmez. ATC Notes bölümü kimlik doğrulaması olmayan, paylaşımlı ve geçici
  (48 saat) bir not panosudur; resmî bir bilgi kaynağı değildir. VFR sekmesi
  son METAR/SPECI'nin görüş/tavan değerlerini ICAO Annex 2 eşikleriyle
  karşılaştıran bilgilendirici bir göstergedir; resmî VFR/IFR tespiti değildir.
</footer>
</div>
<script>
// ---- ORTAK: goreli sure yazimi -------------------------------------------
// BURADA, cunku ilk tuketicisi hemen asagidaki baslik betigi. Eskiden bu
// fonksiyon NOTAM blogunun icinde, baslik betiginden SONRA tanimliydi ve
// baslik sessizce yedek bicime ("120 dk once") dusuyordu - "2 sa once"
// yerine. Tanim tuketiciden once gelmeli.
//
// GORECELI yaziyoruz cunku sayfadaki saatler yerel, veri UTC: "16:00'da"
// hangi saat dilimi oldugu soylenmeden yaniltici, "6 sa once" degil.
// SU AN blogu ekrandan cikinca yapiskan seridi ac. Ikisi ayni dort
// olcuyu gosteriyor; ayni anda ikisini birden cizmek, ayni sayiyi
// 374 piksel arayla iki kez yazmak demekti (bkz. _olcu).
// IntersectionObserver yoksa (cok eski tarayici) serit HEP acik kalir -
// bilgi kaybi degil, yalnizca tekrar.
(function () {{
  var suAn = document.getElementById("su-an");
  var sarmal = document.querySelector(".yapiskan-ust");
  if (!sarmal) return;
  if (!suAn || !("IntersectionObserver" in window)) {{
    sarmal.classList.add("serit-acik");
    return;
  }}
  new IntersectionObserver(function (girisler) {{
    girisler.forEach(function (g) {{
      sarmal.classList.toggle("serit-acik", !g.isIntersecting);
    }});
  }}, {{threshold: 0}}).observe(suAn);
}})();

window.ltfjGecenSure = function (ms) {{
  if (ms == null || isNaN(ms) || ms < 0) return "az önce";
  var dk = Math.floor(ms / 60000);
  if (dk < 1) return "az önce";
  if (dk < 60) return dk + " dk önce";
  var sa = Math.floor(dk / 60);
  if (sa < 24) return sa + " sa önce";
  return Math.floor(sa / 24) + " gün önce";
}};

// ---- UYGULAMA BASLIGI: UTC saat + veri tazeligi ---------------------------
// SUNUCUDA hesaplanamaz: sayfa bir vardiya boyunca acik kalabiliyor ve
// sunucuda yazilan "canli" etiketi bir saat sonra yalan olurdu. Butun
// yaslandirma burada, tarayicinin saatine gore yapiliyor.
//
// ESIKLER PYTHON TARAFINDAN GELIYOR (ltfj_ayarlar): GOZLEM_TAZE_DK ve
// SESSIZLIK_SAAT. Ikincisini bot Telegram alarmi icin de kullaniyor -
// sayfa "canli" derken Telegram "kesinti" diyemesin.
(function () {{
  var BEKLENEN_DK = {gozlem_beklenen_dk};
  var TAZE_DK = {gozlem_taze_dk};
  var KESINTI_DK = {sessizlik_saat} * 60;
  var durumEl = document.getElementById("ust-durum");
  var saatEl = document.getElementById("ust-saat");

  function yasDk(iso) {{
    if (!iso) {{ return null; }}
    var t = Date.parse(iso);
    return isNaN(t) ? null : (Date.now() - t) / 60000;
  }}

  function ikonNokta() {{
    return '<svg class="ikon" viewBox="0 0 24 24" aria-hidden="true">'
         + '<circle cx="12" cy="12" r="5"/></svg>';
  }}

  // ACIK SEKME BAYATLIGI - kullanici bildirdi (iPad'de sayfa acik).
  //
  // Gozlem damgasi (data-gozlem) HTML'e GOMULU; yas her 15 saniyede
  // ISTEMCIDE yeniden hesaplaniyor. Sayfa kendini yenilemedigi icin
  // sekme acik durdukca yas buyuyor, SUNUCUDAKI veri taze olsa bile.
  //
  // Olculdu - sayfayi 12:00'de acinca:
  //   12:20  sekmede 12:00 gozlemi, rozet CANLI  (gercek guncel 12:20)
  //   12:45  sekmede 12:00 gozlemi, rozet CANLI  (gercek guncel 12:20)
  //   12:51  yas 51 dk -> "1 GOZLEM KACTI"
  // Yani once 45 DAKIKALIK BIR METAR "CANLI" diye gosteriliyor (sessiz
  // ve yanlis), sonra da yanlis alarm veriliyor. Ikisi de kotu.
  //
  // COZUM: kadansa yakin araliklarla SUNUCUYA BAK, ama YALNIZCA GOZLEM
  // DEGISTIYSE yeniden yukle. Kor bir zamanlayiciyla her N dakikada
  // yeniden yuklemek, degismemis veri icin kullanicinin yazdigi LVO RVR
  // degerlerini bosuna silerdi (sekme secimi localStorage'da, o kaliyor).
  var KONTROL_MS = 300000;            // 5 dk - METAR kadansinin altinda
  var kontrolBekliyor = false;

  function yenilemeGuvenli() {{
    // Kullanici YAZIYORSA yeniden yukleme: LVO RVR girdileri kalici
    // degil, silinirdi.
    var odak = document.activeElement;
    if (odak && /^(INPUT|TEXTAREA|SELECT)$/.test(odak.tagName)) {{ return false; }}
    // Acik bir panel/modal varken de yukleme - kullanici onun icinde.
    var ortuler = document.querySelectorAll(".atc-panel-ortu, .vfr-panel-ortu");
    for (var i = 0; i < ortuler.length; i++) {{
      if (!ortuler[i].hasAttribute("hidden")) {{ return false; }}
    }}
    return true;
  }}

  function yeniVeriVarMi() {{
    if (kontrolBekliyor || document.hidden || !window.fetch) {{ return; }}
    var simdikiGozlem = durumEl ? durumEl.getAttribute("data-gozlem") : null;
    if (!simdikiGozlem) {{ return; }}
    kontrolBekliyor = true;
    fetch(window.location.pathname + "?_=" + Date.now(), {{cache: "no-store"}})
      .then(function (y) {{ return y.ok ? y.text() : null; }})
      .then(function (metin) {{
        kontrolBekliyor = false;
        if (!metin) {{ return; }}
        var m = metin.match(/id="ust-durum" data-gozlem="([^"]*)"/);
        // Damga AYNIYSA yeniden yukleme yok: bayatlik gercek, rozet
        // onu durustce zaten soyluyor.
        if (!m || m[1] === simdikiGozlem || !m[1]) {{ return; }}
        if (!yenilemeGuvenli()) {{ return; }}
        window.location.replace(window.location.pathname + "?_=" + Date.now());
      }})
      .catch(function () {{ kontrolBekliyor = false; }});   // cevrimdisi: sessiz
  }}

  function durumTazele() {{
    if (saatEl) {{
      var d = new Date();
      saatEl.textContent =
        String(d.getUTCHours()).padStart(2, "0") + ":" +
        String(d.getUTCMinutes()).padStart(2, "0") + "Z";
    }}
    if (!durumEl) {{ return; }}
    var gozlem = durumEl.getAttribute("data-gozlem");
    var dk = yasDk(gozlem);
    var sinif, metin;
    if (dk === null) {{ sinif = "kesinti"; metin = "VERİ YOK"; }}
    else if (dk <= BEKLENEN_DK) {{ sinif = "taze"; metin = "CANLI"; }}
    // BESINCI DURUM. Dort durum varken 35-70 dk arasi "CANLI" kutusunun
    // icindeydi: METAR 49 dakikalikken rozet CANLI diyordu. Oysa kadans
    // 30 dk + ~5 dk gecikme, yani o aralik "bir gozlem kacti" demek.
    // Kacirilmis bir gozlem hata degil (MGM gecikebilir) ama CANLI da
    // degil - okuyanin bilmesi gereken bir sey.
    else if (dk <= TAZE_DK) {{ sinif = "gecikmeli"; metin = "1 GÖZLEM KAÇTI"; }}
    else if (dk <= KESINTI_DK) {{ sinif = "gecikmeli"; metin = "GECİKMELİ"; }}
    else {{ sinif = "kesinti"; metin = "VERİ KESİNTİSİ"; }}
    durumEl.className = "ust-durum " + sinif;
    durumEl.innerHTML = ikonNokta() + metin;
    // Renk TEK BASINA durum anlatmaz - ekran okuyucu icin metin de var.
    durumEl.setAttribute("aria-label", "Veri durumu: " + metin);
  }}

  function yaslariTazele() {{
    var oge = document.querySelectorAll(".veri-oge time[data-zaman]");
    Array.prototype.forEach.call(oge, function (t) {{
      var dk = yasDk(t.getAttribute("data-zaman"));
      if (dk === null) {{ t.textContent = "—"; return; }}
      t.textContent = window.ltfjGecenSure
        ? window.ltfjGecenSure(dk * 60000)
        : Math.round(dk) + " dk önce";
      t.parentNode.classList.toggle("bayat", dk > KESINTI_DK);
    }});
  }}

  function fazTazele() {{
    var el = document.getElementById("ust-faz");
    var k = document.documentElement;
    if (!el) {{ return; }}
    var dogus = Date.parse(k.getAttribute("data-gun-dogumu") || "");
    var batim = Date.parse(k.getAttribute("data-gun-batimi") || "");
    if (isNaN(dogus) || isNaN(batim)) {{ el.textContent = ""; return; }}
    var t = Date.now();
    var gunduz = (t >= dogus && t < batim);
    // Siradaki gecis: gunduzsek batim, gecesek dogus.
    var sirada = new Date(gunduz ? batim : dogus);
    function ikili(n) {{ return String(n).padStart(2, "0"); }}
    var saat = ikili(sirada.getUTCHours()) + ":" + ikili(sirada.getUTCMinutes()) + "Z";
    el.textContent = (gunduz ? "gündüz · batım " : "gece · doğuş ") + saat;
    el.setAttribute("title", gunduz
      ? "Gün batımı " + saat + " (LTFJ için hesaplanmış)"
      : "Gün doğumu " + saat + " (LTFJ için hesaplanmış) — sis penceresi");
  }}

  function hepsi() {{ durumTazele(); yaslariTazele(); fazTazele(); }}
  hepsi();
  // Kadans kontrolu: 5 dakikada bir sunucuya bak. Sekme arkada iken
  // atlaniyor (pil), one gelince hemen bir kez bakiliyor.
  setInterval(yeniVeriVarMi, KONTROL_MS);
  // 15 sn: dakika degisimini kacirmayacak kadar sik, saniye saymayacak
  // kadar seyrek - surekli hareket operasyonel ekranda gurultudur.
  setInterval(hepsi, 15000);
  document.addEventListener("visibilitychange", function () {{
    if (!document.hidden) {{ hepsi(); yeniVeriVarMi(); }}
  }});
}})();

// ---- SEKME GECISI --------------------------------------------------------
// Gorunurlugu CSS yapiyor (html[data-sekme=...]), JS degil. Sebep: acilista
// dogru panelin ILK karede acik olmasi gerekiyor ve bunu <head>'deki satir
// ici betik hallediyor. Burada yalnizca durumu DEGISTIRIYORUZ; iki yerde
// iki ayri gizleme mantigi olsaydi biri otekinden sapardi.
(function () {{
  var cubuk = document.querySelector(".sekme-cubugu");
  if (!cubuk) {{ return; }}
  var dugmeler = Array.prototype.slice.call(cubuk.querySelectorAll(".sekme"));

  function sec(anahtar, odakla) {{
    document.documentElement.setAttribute("data-sekme", anahtar);
    dugmeler.forEach(function (d) {{
      var bu = d.getAttribute("data-sekme") === anahtar;
      d.setAttribute("aria-selected", String(bu));
      // Klavyeyle gezinirken Tab tek seferde cubugu gecsin diye secili
      // olmayanlar sekme sirasindan cikarilir (WAI-ARIA tablist deseni).
      d.tabIndex = bu ? 0 : -1;
      if (bu && odakla) {{ d.focus(); }}
      // Cubuk tasiyorsa secili sekme gorunur olsun: NOTAM'dayken sayfayi
      // yeniden acinca o sekme cubugun disinda kalabiliyordu.
      // scrollIntoView DEGIL - o, yapiskan cubugu tasidigi icin SAYFAYI da
      // kaydiriyor; yalnizca cubugun kendi scrollLeft'ini oynatiyoruz.
      if (bu) {{
        var sol = d.offsetLeft, sag = sol + d.offsetWidth;
        if (sol < cubuk.scrollLeft) {{ cubuk.scrollLeft = sol - 4; }}
        else if (sag > cubuk.scrollLeft + cubuk.clientWidth) {{
          cubuk.scrollLeft = sag - cubuk.clientWidth + 4;
        }}
      }}
    }});
    try {{ localStorage.setItem("ltfj-sekme", anahtar); }} catch (e) {{}}
  }}

  dugmeler.forEach(function (d, i) {{
    d.addEventListener("click", function () {{
      sec(d.getAttribute("data-sekme"), false);
    }});
    d.addEventListener("keydown", function (e) {{
      var yon = e.key === "ArrowRight" ? 1 : (e.key === "ArrowLeft" ? -1 : 0);
      if (!yon) {{ return; }}
      e.preventDefault();
      var j = (i + yon + dugmeler.length) % dugmeler.length;
      sec(dugmeler[j].getAttribute("data-sekme"), true);
    }});
  }});

  // <head> betiginin sectigi sekmeyi dugme durumlariyla hizala: o betik
  // yalnizca data-sekme yaziyor, aria-selected hep "durum"da kaliyordu.
  var acik = document.documentElement.getAttribute("data-sekme") || "durum";
  sec(acik, false);
}})();

// NOTAM'in SU ANKI gecerliligi - HEM "Aktif NOTAM'lar"/arama bolumu HEM DE
// LVO panelindeki NOTAM listesi bunu kullanir. TEK yerde durmasinin sebebi
// somut: ayni "aktif mi?" karari iki ayri script'te kopyalanmisti ve
// kopyalarin ikisi de ayni hatayi tasiyordu.
//
// Kritik: kayitlardaki `status` alani NOTAC'tan en son GORULDUGU andaki
// degerdir ve DONUKTUR - suresi dolmus bir NOTAM yerel gecmiste sonsuza
// dek "active" yazar. Bu yuzden suresi bitmis NOTAM'lar aktif gorunuyordu.
// Tarih penceresini her cizimde YENIDEN hesapliyoruz; sayfa saatlerce
// acik kalsa bile etiket kendiliginden dogruya doner.
//
// NOTAC'in kendi status'u yine de belirleyici: "cancelled"/"withdrawn"
// gibi bir deger tarih penceresinden BAGIMSIZ olarak gecerlidir (iptal
// edilmis bir NOTAM tarihi gecmemis olsa da yururlukte degildir).
// effective_end bos olan NOTAM kalicidir (ornegin G4445/14), suresi dolmaz.
window.ltfjNotamGecerlilik = function (n) {{
  "use strict";
  var simdi = Date.now();
  if (n.status && n.status !== "active") {{
    return {{durum: "diger", etiket: n.status, vurgula: true}};
  }}
  var bas = n.effective_start ? Date.parse(n.effective_start) : NaN;
  var bit = n.effective_end ? Date.parse(n.effective_end) : NaN;
  if (!isNaN(bit) && bit < simdi) {{
    return {{durum: "doldu", etiket: "süresi doldu", vurgula: true}};
  }}
  if (!isNaN(bas) && bas > simdi) {{
    return {{durum: "baslamadi", etiket: "henüz başlamadı", vurgula: true}};
  }}
  if (!n.status) {{
    return {{durum: "bilinmiyor", etiket: "", vurgula: false}};
  }}
  // "yururlukte" yazmak bilgi tasimiyordu - Aktif NOTAM listesindeki HER
  // kart zaten yururlukte. Yerine kontrolorun gercekten merak ettigi sey:
  // ne kadar kaldi. effective_end bos olan NOTAM kalici, "süresiz".
  return {{
    durum: "yururlukte",
    etiket: isNaN(bit) ? "süresiz" : window.ltfjKalanSure(bit - simdi),
    vurgula: false,
  }};
}};

// Milisaniye farkini kisa, okunur bir kalan sureye cevirir. Mutlak saat
// yerine GORECELI sure yaziyoruz: sayfada saatler yerel, NOTAM verisi UTC -
// "16:00'da bitiyor" hangi saat dilimi oldugu belirtilmeden yaniltici olur,
// "6 sa kaldı" ise saat diliminden bagimsiz dogru.
// Senkron araligi ayarlarda 6 saat (notam.senkron_araligi_saat). Iki
// katini gecmisse bir senkron kacmis demektir - bayat sayiyoruz.
var NOTAM_BAYAT_MS = 12 * 3600 * 1000;

window.ltfjKalanSure = function (ms) {{
  "use strict";
  var dk = Math.floor(ms / 60000);
  if (dk < 1) return "birazdan bitiyor";
  if (dk < 60) return dk + " dk kaldı";
  var saat = Math.floor(dk / 60);
  if (saat < 48) return saat + " sa kaldı";
  return Math.floor(saat / 24) + " gün kaldı";
}};
</script>
<script>
(function () {{
  "use strict";
  function esc(s) {{
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {{
      return {{"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}}[c];
    }});
  }}

  var veri = null;
  var aktifEl = document.getElementById("notam-aktif-liste");
  var aktifQEl = document.getElementById("notam-aktif-q");
  var aktifKategoriEl = document.getElementById("notam-aktif-kategori");
  var aktifElemanEl = document.getElementById("notam-aktif-eleman");
  var aktifSayiEl = document.getElementById("notam-aktif-sayi");
  var senkronEl = document.getElementById("notam-senkron-zamani");
  var sonucEl = document.getElementById("notam-arama-sonuc");
  var durumSelectEl = document.getElementById("notam-durum");

  var gecerlilik = window.ltfjNotamGecerlilik;

  function notamKarti(n) {{
    var etiketler = (n.tags || []).map(function (t) {{
      return '<span class="notam-etiket">' + esc(t) + "</span>";
    }}).join("");
    var kategori = n.category_etiketi
      ? '<span class="notam-etiket">' + esc(n.category_etiketi) + "</span>" : "";
    var pistler = (n.affected_elements || []).map(function (e) {{
      return e.ref ? '<span class="notam-etiket">' + esc(e.ref) + "</span>" : "";
    }}).join("");
    var ozet = n.reading_short
      ? '<div class="notam-ozet">' + esc(n.reading_short) +
        ' <span style="color:var(--soluk); font-size:var(--f2);">(NOTAC otomatik özeti — hata içerebilir)</span></div>'
      : "";
    var g = gecerlilik(n);
    // Yesil nokta SADECE su anda gercekten yururlukte olan NOTAM'a konur.
    var aktifNoktasi = g.durum === "yururlukte"
      ? '<span class="notam-aktif-nokta" title="Şu anda yürürlükte"></span>' : "";
    return (
      '<div class="notam-kart">' +
      '<div class="notam-ust">' + aktifNoktasi +
      '<span class="notam-no">' + esc(n.number || "—") + "</span>" +
      kategori + etiketler + pistler +
      '<span class="notam-durum' + (g.vurgula ? " notam-durum-gecmis" : "") + '">' +
      esc(g.etiket) + "</span></div>" +
      ozet +
      "<details><summary style=\\"cursor:pointer; font-size:var(--f2); color:var(--soluk);\\">Ham NOTAM metni</summary>" +
      '<div class="notam-metin">' + esc(n.text || "") + "</div></details>" +
      '<div class="notam-kaynak">Kaynak: NOTAC · geçerlilik: ' +
      esc(n.effective_start || "—") + " → " + esc(n.effective_end || "—") + "</div>" +
      "</div>"
    );
  }}

  // Aktif listeye giren kayitlar: NOTAC'in son senkronda dondurduklerinden
  // suresi GERCEKTEN dolmamis olanlar. Senkron bayatlarsa (NOTAC erisilemez)
  // aradan gecen surede suresi biten bir NOTAM burada kalmaya devam
  // ederdi - tarih kontrolu bunu da kapatiyor.
  function yururluktekiler() {{
    return (veri.aktif || []).filter(function (n) {{
      return gecerlilik(n).durum === "yururlukte";
    }}).sort(function (a, b) {{
      return (a.number || "").localeCompare(b.number || "");
    }});
  }}

  function aktifFiltrele(liste) {{
    var q = aktifQEl.value.trim().toLowerCase();
    var kat = aktifKategoriEl.value;
    var eleman = aktifElemanEl.value;
    return liste.filter(function (n) {{
      if (kat && n.category_etiketi !== kat) return false;
      if (eleman) {{
        var refler = (n.affected_elements || []).map(function (e) {{ return e.ref; }});
        if (refler.indexOf(eleman) === -1) return false;
      }}
      if (q) {{
        var alanlar = [n.number, n.text, n.reading_short, n.reading_long]
          .concat(n.tags || [])
          .concat((n.affected_elements || []).map(function (e) {{ return e.ref; }}))
          .filter(Boolean).join(" ").toLowerCase();
        if (alanlar.indexOf(q) === -1) return false;
      }}
      return true;
    }});
  }}

  function aktifGoster() {{
    if (!veri) return;
    // Ham UTC damgasi ("2026-09-22 19:51") GOSTERILMIYOR: sayfadaki diger
    // saatler YEREL, bu ise UTC idi ve etiketsizdi - hangi saat dilimi
    // oldugu belirtilmeden yaniltici. Ayni gerekce NOTAM kalan suresinde
    // de goreceli bicimi sectirmisti (bkz. window.ltfjKalanSure).
    //
    // Ayrica bayatlik artik GORUNUR: NOTAC gunlerce erisilemezse liste
    // sessizce eskiyordu, kucuk gri bir tarihten bunu cikarmak
    // kullanicinin isi degil.
    senkronEl.classList.remove("notam-senkron-bayat");
    if (!veri.son_senkron) {{
      senkronEl.textContent = "henüz senkronize edilmedi";
    }} else {{
      var yasMs = Date.now() - new Date(veri.son_senkron).getTime();
      senkronEl.textContent = isNaN(yasMs)
        ? "senkron zamanı okunamadı"
        : window.ltfjGecenSure(yasMs) + " senkronize edildi";
      if (yasMs > NOTAM_BAYAT_MS) {{
        senkronEl.classList.add("notam-senkron-bayat");
        // Emoji DEGIL duz metin: burasi textContent, SVG konulamaz.
        // Renk zaten .notam-senkron-bayat ile veriliyor; metin ikinci
        // isaret, yani durum renge TEK BASINA bagli degil.
        senkronEl.textContent += " · liste eski olabilir";
      }}
    }}

    if (!veri.son_senkron) {{
      aktifSayiEl.textContent = "";
      aktifEl.innerHTML = '<div class="notam-bos">NOTAM verisi şu anda alınamıyor.</div>';
      return;
    }}

    var tumu = yururluktekiler();
    var gosterilecek = aktifFiltrele(tumu);

    aktifSayiEl.textContent = !tumu.length
      ? "aktif yok"
      : (gosterilecek.length === tumu.length
          ? tumu.length + " aktif"
          : gosterilecek.length + " / " + tumu.length + " aktif");

    if (!tumu.length) {{
      aktifEl.innerHTML = '<div class="notam-bos">Aktif NOTAM bulunmuyor.</div>';
    }} else if (!gosterilecek.length) {{
      aktifEl.innerHTML = '<div class="notam-bos">Filtreye uyan aktif NOTAM yok.</div>';
    }} else {{
      aktifEl.innerHTML = gosterilecek.map(notamKarti).join("");
    }}
  }}

  // Filtre secenekleri SADECE yururlukteki NOTAM'larda gercekten bulunan
  // degerlerden uretilir - bos sonuc veren secenek listelenmez.
  function aktifFiltreSecenekleriDoldur() {{
    var liste = yururluktekiler();
    function doldur(el, degerler) {{
      var secili = el.value;
      while (el.options.length > 1) el.remove(1);
      degerler.sort().forEach(function (d) {{
        var o = document.createElement("option");
        o.value = d; o.textContent = d;
        el.appendChild(o);
      }});
      // Veri yenilenince kullanicinin secimi hala gecerliyse KORUNUR.
      el.value = degerler.indexOf(secili) !== -1 ? secili : "";
    }}
    var kategoriler = {{}}, elemanlar = {{}};
    liste.forEach(function (n) {{
      if (n.category_etiketi) kategoriler[n.category_etiketi] = true;
      (n.affected_elements || []).forEach(function (e) {{
        if (e.ref) elemanlar[e.ref] = true;
      }});
    }});
    doldur(aktifKategoriEl, Object.keys(kategoriler));
    doldur(aktifElemanEl, Object.keys(elemanlar));
  }}

  function aramaCalistir() {{
    if (!veri) return;
    var q = document.getElementById("notam-q").value.trim().toLowerCase();
    var ts = document.getElementById("notam-tarih-baslangic").value;
    var te = document.getElementById("notam-tarih-bitis").value;
    var durum = durumSelectEl.value;

    // Hicbir kriter girilmediyse TUM gecmisi dokmuyoruz - bu bilincli bir
    // tercih: "gecmis" NOTAC'in arsivi degil, sadece botun gordukleri;
    // istenmeden karsiya dokulmesi yaniltici olur.
    if (!q && !ts && !te && !durum) {{
      sonucEl.innerHTML = '<div class="notam-bos">Aramak için yukarıdaki '
        + "alanlardan birini doldurun.</div>";
      return;
    }}

    var sonuclar = (veri.gecmis || []).filter(function (n) {{
      // Kayittaki donuk `status` yerine HESAPLANAN gecerlilik - kartta
      // gorunen etiketle birebir ayni olsun.
      if (durum && gecerlilik(n).durum !== durum) return false;
      if (q) {{
        var alanlar = [n.number, n.text, n.reading_short, n.reading_long]
          .concat(n.tags || [])
          .concat((n.affected_elements || []).map(function (e) {{ return e.ref; }}))
          .filter(Boolean).join(" ").toLowerCase();
        if (alanlar.indexOf(q) === -1) return false;
      }}
      if (ts && n.effective_end && n.effective_end < ts) return false;
      if (te && n.effective_start && n.effective_start > te) return false;
      return true;
    }});

    sonucEl.innerHTML = sonuclar.length
      ? sonuclar.map(notamKarti).join("")
      : '<div class="notam-bos">Sonuç bulunamadı.</div>';
  }}

  function veriYukle() {{
    fetch("notam_veri.json?_=" + Date.now(), {{cache: "no-store"}})
      .then(function (r) {{ if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }})
      .then(function (v) {{
        veri = v;
        aktifFiltreSecenekleriDoldur();
        aktifGoster();
        // Bolum katli geldigi icin basliktaki sayac, icinde ne kadar kayit
        // oldugunu acmadan gosterir.
        var gecmisSayiEl = document.getElementById("notam-gecmis-sayi");
        if (gecmisSayiEl) {{
          var adet = (veri.gecmis || []).length;
          gecmisSayiEl.textContent = adet ? adet + " kayıt" : "";
        }}
        // Kriter girilmemisse aramaCalistir zaten ipucu metnini basar.
        aramaCalistir();
      }})
      .catch(function (err) {{
        var mesaj = '<div class="notam-bos">NOTAM verisi şu anda alınamıyor.</div>';
        aktifEl.innerHTML = mesaj;
        sonucEl.innerHTML = mesaj;
        senkronEl.textContent = "";
        console.error("[notam] veri yüklenemedi:", err);
      }});
  }}

  // Ac/kapa artik <details> ile yapiliyor (bkz. NOTAM karti) - eskiden
  // burada elle yazilmis bir ok/aria-expanded yonetimi vardi, kalktikca
  // ayni isi tarayicinin yerlisi goruyor.
  // Filtre satirindaki tiklamalar paneli KAPATMAMALI - basligin disinda
  // olmasina ragmen govde baslikla ayni kartta, kullanici yanlislikla
  // katlamasin.
  aktifQEl.addEventListener("input", aktifGoster);
  aktifKategoriEl.addEventListener("change", aktifGoster);
  aktifElemanEl.addEventListener("change", aktifGoster);
  document.getElementById("notam-aktif-temizle").addEventListener("click", function () {{
    aktifQEl.value = "";
    aktifKategoriEl.value = "";
    aktifElemanEl.value = "";
    aktifGoster();
  }});

  // Aktif liste filtreleriyle AYNI davranis: yazdikca/sectikce suzuluyor,
  // ayri bir "Ara" adimi yok. Gecmis birkac yuz kayitla sinirli oldugu icin
  // her tusta yeniden cizmek sorun degil.
  document.getElementById("notam-q").addEventListener("input", aramaCalistir);
  document.getElementById("notam-tarih-baslangic").addEventListener("change", aramaCalistir);
  document.getElementById("notam-tarih-bitis").addEventListener("change", aramaCalistir);
  durumSelectEl.addEventListener("change", aramaCalistir);
  document.getElementById("notam-arama-temizle").addEventListener("click", function () {{
    document.getElementById("notam-q").value = "";
    document.getElementById("notam-tarih-baslangic").value = "";
    document.getElementById("notam-tarih-bitis").value = "";
    durumSelectEl.value = "";
    aramaCalistir();
  }});
  veriYukle();
}})();
</script>
<script>
(function () {{
  "use strict";
  // LVO REFERENCE paneli - METAR/NOTAM/ATC Notes'tan TAMAMEN bağımsız bir
  // bilgi katmanı, yukarıdaki hiçbir script'le değişken/durum PAYLAŞMAZ.
  // Bu script SADECE mevcut bilgileri (AWOS RVR manuel girişi, LVO ile
  // ilişkili NOTAM'lar, Farkındalık Notları) provenance ve zaman damgasıyla
  // GÖSTERİR - hiçbir operasyonel karar (LVO aktif mi, CAT II kullanılabilir
  // mi, hangi pist kullanılmalı) ÜRETMEZ. Farkındalık Notları GAYRİ RESMİ,
  // hedge'li ("... olabilir. Resmî bir tespit değildir.") metinlerdir - bkz.
  // ltfj_lvo_farkindalik.py. AWOS değerleri asla METAR'dan türetilmez,
  // sadece kullanıcının manuel girdiği değerlerdir. Okuma/yazma ATC Notes
  // ile AYNI Firebase veritabanına, farklı path'e (awos_rvr) yapılır - ayrı
  // bir proje/kurulum gerekmez.
  var DB_URL = {atc_notes_db_url};
  var RVR_ESIKLERI = {rvr_esikleri_json};   // ltfj_lvo_referans.RVR_ESIKLERI ile AYNI kaynak
  var STALE_ESIK_DK = 30;   // SADECE veri tazeliği göstergesi - operasyonel bir minima DEĞİL
  var AWOS_PISTLER = ["06R", "24R"];
  var AWOS_POZISYONLAR = ["TDZ", "MID", "STOP-END"];
  var LVO_NOTAM_ANAHTAR_KELIMELER = [
    "runway", "rwy", "ils", "localizer", "glide", "approach light", "yaklaşma işık",
    "runway light", "pist ışık", "taxiway", "taksi yolu", "stop bar", "rvr", "awos",
    "atis", "low visibility", "düşük görüş", "aerodrome equipment", "havalimanı ekipman",
  ];

  var awosListeEl = document.getElementById("lvo-awos-liste");
  var notamListeEl = document.getElementById("lvo-notam-liste");
  var awosHataEl = document.getElementById("lvo-awos-hata");
  var awosKaydetBtn = document.getElementById("lvo-awos-kaydet");
  var sonAwosGonderim = 0;

  // LVO ac/kapa mantigi KALDIRILDI: panel artik bir sekme paneli, gorunur
  // olup olmadigini sekme cubugu belirliyor. Ayri bir ac/kapa, sekmeye
  // bastiktan sonra bir de basliga basmak demekti.
  var farkRvrListeEl = document.getElementById("lvo-fark-rvr-liste");
  var farkBosEl = document.getElementById("lvo-fark-bos");

  function tabanUrl(yol) {{
    var taban = DB_URL;
    while (taban.length && taban.charAt(taban.length - 1) === "/") {{
      taban = taban.slice(0, -1);
    }}
    return taban + "/" + yol + ".json";
  }}

  function yasGoster(ms) {{
    var dk = Math.floor((Date.now() - ms) / 60000);
    if (dk < 1) return "az önce";
    if (dk < 60) return dk + " dk önce";
    var saat = Math.floor(dk / 60), kalanDk = dk % 60;
    return saat + " sa " + kalanDk + " dk önce";
  }}

  // -------------------------------------------------------------- AWOS
  function awosGoster(kayitlar) {{
    if (!DB_URL) {{
      awosListeEl.textContent = "AWOS RVR: NOT AVAILABLE";
      farkindalikRvrGuncelle({{}});
      return;
    }}
    var enSon = {{}};
    Object.keys(kayitlar || {{}}).forEach(function (id) {{
      var k = kayitlar[id];
      if (!k || typeof k.entered_at !== "number") return;
      var anahtar = k.runway + "|" + k.position;
      if (!enSon[anahtar] || k.entered_at > enSon[anahtar].entered_at) enSon[anahtar] = k;
    }});

    var verilerVarMi = false;
    var grid = document.createElement("div");
    grid.className = "lvo-awos-grid";

    AWOS_PISTLER.forEach(function (pist) {{
      var kart = document.createElement("div");
      kart.className = "lvo-awos-kart";
      var baslik = document.createElement("div");
      baslik.className = "lvo-awos-pist";
      baslik.textContent = pist;
      kart.appendChild(baslik);

      var pistteVeriVar = false;
      var enYeniZaman = 0;
      AWOS_POZISYONLAR.forEach(function (poz) {{
        var kayit = enSon[pist + "|" + poz];
        var satir = document.createElement("div");
        satir.className = "lvo-awos-deger";
        var etiket = document.createElement("span");
        etiket.textContent = poz;
        satir.appendChild(etiket);
        var deger = document.createElement("span");
        if (kayit) {{
          pistteVeriVar = true;
          verilerVarMi = true;
          if (kayit.entered_at > enYeniZaman) enYeniZaman = kayit.entered_at;
          deger.textContent = kayit.value + " " + kayit.unit;
          if ((Date.now() - kayit.entered_at) > STALE_ESIK_DK * 60000) {{
            var staleEl = document.createElement("span");
            staleEl.className = "lvo-stale";
            staleEl.textContent = "STALE";
            deger.appendChild(staleEl);
          }}
        }} else {{
          deger.textContent = "—";
        }}
        satir.appendChild(deger);
        kart.appendChild(satir);
      }});

      if (pistteVeriVar) {{
        var alt = document.createElement("div");
        alt.className = "lvo-awos-alt";
        alt.textContent = "MANUAL AWOS · " + yasGoster(enYeniZaman);
        kart.appendChild(alt);
      }}
      grid.appendChild(kart);
    }});

    awosListeEl.innerHTML = "";
    if (!verilerVarMi) {{
      awosListeEl.textContent = "AWOS RVR: NOT AVAILABLE";
    }} else {{
      awosListeEl.appendChild(grid);
    }}

    farkindalikRvrGuncelle(enSon);
  }}

  // Manuel AWOS RVR degerlerini (gercek olcum) dokumanin kendi esikleriyle
  // (RVR_ESIKLERI - ltfj_lvo_farkindalik.rvr_notu() ile AYNI mantik) GAYRI
  // RESMI, hedge'li notlara cevirir; "LVO aktif/CAT II kullanilabilir" gibi
  // kesin bir ifade URETMEZ.
  function rvrFarkindalikNotu(pist, pozisyon, degerM) {{
    var enDerin = null;
    RVR_ESIKLERI.forEach(function (e) {{
      if (degerM < e.esik_altinda_m && (!enDerin || e.esik_altinda_m < enDerin.esik_altinda_m)) {{
        enDerin = e;
      }}
    }});
    if (!enDerin) return null;
    return pist + " " + pozisyon + " AWOS RVR " + degerM + " m — dokümanın " +
      enDerin.esik_altinda_m + " m eşiğinin (" + enDerin.safha + ") altında. " +
      "LVO şartları oluşabilir. Resmî bir tespit değildir.";
  }}

  function farkindalikRvrGuncelle(enSonAwos) {{
    farkRvrListeEl.innerHTML = "";
    Object.keys(enSonAwos || {{}}).sort().forEach(function (anahtar) {{
      var k = enSonAwos[anahtar];
      var not_ = rvrFarkindalikNotu(k.runway, k.position, k.value);
      if (!not_) return;
      var li = document.createElement("li");
      li.textContent = not_;
      farkRvrListeEl.appendChild(li);
    }});
    var toplamNot = document.querySelectorAll("#lvo-fark-metar-taf li, #lvo-fark-rvr-liste li").length;
    farkBosEl.hidden = toplamNot > 0;
  }}

  function awosYukle() {{
    if (!DB_URL) {{ awosGoster({{}}); return; }}
    fetch(tabanUrl("awos_rvr") + "?_=" + Date.now())
      .then(function (r) {{ if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }})
      .then(awosGoster)
      .catch(function (err) {{
        awosListeEl.textContent = "AWOS RVR: NOT AVAILABLE";
        console.error("[lvo] awos okuma hatası:", err);
      }});
  }}

  // Secili pistin TUM AWOS RVR kayitlarini siler. Tek tek degil hepsi,
  // cunku gosterim her pist|pozisyon icin EN YENI kaydi seciyor - sadece
  // sonuncuyu silmek bir oncekini geri getirirdi.
  //
  // Firebase kurali silmeye izin verir ama UZERINE YAZMAYA izin vermez
  // (bkz. firebase-rules.json awos_rvr: "!data.exists() || !newData.exists()").
  // Kurallarin guncel hali yayinlanmamissa istek 401/403 doner ve bunu
  // sessizce yutmuyoruz - kullaniciya soyluyoruz.
  document.getElementById("lvo-awos-temizle").addEventListener("click", function () {{
    awosHataEl.textContent = "";
    if (!DB_URL) {{ awosHataEl.textContent = "LVO paneli şu anda yapılandırılmamış."; return; }}
    var pist = document.getElementById("lvo-awos-pist").value;
    // Paylasilan operasyonel veri siliniyor - once onay.
    if (!window.confirm(pist + " pistinin girilmiş AWOS RVR değerleri silinecek. Onaylıyor musunuz?")) return;

    var btn = document.getElementById("lvo-awos-temizle");
    btn.disabled = true;
    fetch(tabanUrl("awos_rvr") + "?_=" + Date.now())
      .then(function (r) {{ if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }})
      .then(function (kayitlar) {{
        var idler = Object.keys(kayitlar || {{}}).filter(function (id) {{
          return kayitlar[id] && kayitlar[id].runway === pist;
        }});
        if (!idler.length) {{
          awosHataEl.textContent = pist + " için silinecek kayıt yok.";
          return null;
        }}
        return Promise.all(idler.map(function (id) {{
          // tabanUrl() sonuna ".json" EKLER - kaydin yolunu ona parametre
          // olarak vermek gerekir. Birlestirerek yazmak
          // ".../awos_rvr.json/<id>.json" gibi gecersiz bir URL uretiyordu.
          return fetch(tabanUrl("awos_rvr/" + encodeURIComponent(id)),
                       {{method: "DELETE"}})
            .then(function (r) {{
              if (!r.ok) throw new Error("HTTP " + r.status);
            }});
        }}));
      }})
      .then(function (sonuc) {{ if (sonuc) awosYukle(); }})
      .catch(function (err) {{
        // Hata metni SEBEBI tasisin: ilk surumde sadece "kurallar silmeye
        // izin veriyor mu?" yaziyordu ve asil sorun (bozuk URL) teshis
        // edilemiyordu. 401/403 kural, 400/404 yol sorununu isaret eder.
        awosHataEl.textContent = "AWOS RVR temizlenemedi (" + err.message + ")."
          + " 401/403 ise Firebase kuralları silmeye izin vermiyor demektir.";
        console.error("[lvo] awos temizleme hatası:", err);
      }})
      .finally(function () {{ btn.disabled = false; }});
  }});

  document.getElementById("lvo-awos-kaydet").addEventListener("click", function () {{
    awosHataEl.textContent = "";
    if (!DB_URL) {{ awosHataEl.textContent = "LVO paneli şu anda yapılandırılmamış."; return; }}
    if (Date.now() - sonAwosGonderim < 3000) return;

    var pist = document.getElementById("lvo-awos-pist").value;
    var alanlar = [
      {{poz: "TDZ", el: document.getElementById("lvo-awos-tdz")}},
      {{poz: "MID", el: document.getElementById("lvo-awos-mid")}},
      {{poz: "STOP-END", el: document.getElementById("lvo-awos-end")}},
    ];
    var gonderilecekler = [];
    for (var i = 0; i < alanlar.length; i++) {{
      var ham = alanlar[i].el.value.trim();
      if (ham === "") continue;
      var sayi = Number(ham);
      if (!isFinite(sayi) || sayi < 0 || sayi > 9999) {{
        awosHataEl.textContent = alanlar[i].poz + " değeri 0-9999 arası bir sayı olmalı.";
        return;
      }}
      gonderilecekler.push({{position: alanlar[i].poz, value: sayi}});
    }}
    if (!gonderilecekler.length) {{
      awosHataEl.textContent = "En az bir RVR değeri girin.";
      return;
    }}

    awosKaydetBtn.disabled = true;
    Promise.all(gonderilecekler.map(function (g) {{
      return fetch(tabanUrl("awos_rvr"), {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{
          runway: pist, position: g.position, value: g.value, unit: "m",
          entered_at: {{".sv": "timestamp"}}, source: "MANUAL AWOS",
        }}),
      }}).then(function (r) {{ if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }});
    }}))
      .then(function () {{
        sonAwosGonderim = Date.now();
        alanlar.forEach(function (a) {{ a.el.value = ""; }});
        awosYukle();
      }})
      .catch(function (err) {{
        awosHataEl.textContent = "AWOS RVR kaydedilemedi, tekrar deneyin.";
        console.error("[lvo] awos yazma hatası:", err);
      }})
      .finally(function () {{ awosKaydetBtn.disabled = false; }});
  }});

  // ------------------------------------------------------- LVO-ilişkili NOTAM
  function notamKarti(n) {{
    var kart = document.createElement("div");
    kart.className = "notam-kart";
    var ust = document.createElement("div");
    ust.className = "notam-ust";
    if (window.ltfjNotamGecerlilik(n).durum === "yururlukte") {{
      var nokta = document.createElement("span");
      nokta.className = "notam-aktif-nokta";
      nokta.title = "Şu anda yürürlükte";
      ust.appendChild(nokta);
    }}
    var no = document.createElement("span");
    no.className = "notam-no";
    no.textContent = n.number || "—";
    ust.appendChild(no);
    kart.appendChild(ust);
    var metin = document.createElement("div");
    metin.className = "notam-ozet";
    metin.textContent = n.reading_short || n.text || "";
    kart.appendChild(metin);
    return kart;
  }}

  function notamLvoIliskiliMi(n) {{
    var alanlar = [n.text, n.reading_short, n.reading_long, n.category_etiketi]
      .concat(n.tags || [])
      .filter(Boolean).join(" ").toLowerCase();
    return LVO_NOTAM_ANAHTAR_KELIMELER.some(function (kw) {{ return alanlar.indexOf(kw) !== -1; }});
  }}

  function notamYukle() {{
    fetch("notam_veri.json?_=" + Date.now(), {{cache: "no-store"}})
      .then(function (r) {{ if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }})
      .then(function (v) {{
        // Suresi dolmus bir NOTAM burada aktifmis gibi gorunmemeli - LVO
        // panelinde bu, olmayan bir kisitlamayi varmis gibi gostermek olur.
        var aktif = ((v && v.aktif) || []).filter(function (n) {{
          return window.ltfjNotamGecerlilik(n).durum === "yururlukte";
        }});
        var iliskili = aktif.filter(notamLvoIliskiliMi);
        notamListeEl.innerHTML = "";
        if (!iliskili.length) {{
          notamListeEl.textContent = "No LVO-related NOTAM in local cache";
        }} else {{
          iliskili.forEach(function (n) {{ notamListeEl.appendChild(notamKarti(n)); }});
        }}
      }})
      .catch(function (err) {{
        notamListeEl.textContent = "No LVO-related NOTAM in local cache";
        console.error("[lvo] notam okuma hatası:", err);
      }});
  }}

  awosYukle();
  notamYukle();
  setInterval(function () {{ awosYukle(); }}, 45000);
}})();
</script>
<script>
(function () {{
  "use strict";
  // ATC Notes, NOTAM/METAR'dan TAMAMEN ayrı, bağımsız bir modül - bu script
  // yukarıdaki NOTAM script'iyle hiçbir değişken/durum PAYLAŞMAZ. Okuma/
  // yazma doğrudan Firebase Realtime Database REST API'sine fetch() ile
  // yapılır (ayrı bir SDK/CDN gerekmez). Güvenlik (uzunluk limitleri,
  // "created_at" alanının GERÇEKTEN sunucu saati olması) Firebase Realtime
  // Database Rules ile sağlanır (bkz. firebase-rules.json) - bu script
  // sadece kullanıcı deneyimi için AYRICA istemci tarafında da doğrular,
  // ama gerçek güvenlik sınırı sunucu (Rules) tarafındadır.
  var DB_URL = {atc_notes_db_url};
  var YASAM_SURESI_MS = 48 * 3600 * 1000;
  var POLL_ARALIGI_MS = 45000;
  var AUTHOR_MAKS = 100;
  var TEXT_MAKS = 1000;

  var listeEl = document.getElementById("atc-notes-liste");
  var modalEl = document.getElementById("atc-not-modal");
  var yazanEl = document.getElementById("atc-not-yazan");
  var metinEl = document.getElementById("atc-not-metin");
  var hataEl = document.getElementById("atc-not-hata");
  var kaydetBtn = document.getElementById("atc-not-kaydet");
  var fabEl = document.getElementById("atc-fab");
  var fabRozetEl = document.getElementById("atc-fab-rozet");
  var panelOrtuEl = document.getElementById("atc-panel-ortu");
  var sonGonderimZamani = 0;

  function tabanUrl() {{
    var taban = DB_URL;
    while (taban.length && taban.charAt(taban.length - 1) === "/") {{
      taban = taban.slice(0, -1);
    }}
    return taban + "/atc_notes.json";
  }}

  function notKarti(veri) {{
    var kart = document.createElement("div");
    kart.className = "notam-kart";

    var ust = document.createElement("div");
    ust.className = "notam-ust";
    var yazan = document.createElement("span");
    yazan.className = "notam-no";
    yazan.textContent = veri.author || "?";
    ust.appendChild(yazan);
    var zamanEl = document.createElement("span");
    zamanEl.className = "notam-durum";
    var d = new Date(veri.created_at);
    zamanEl.textContent = d.toISOString().slice(0, 16).replace("T", " ") + " UTC";
    ust.appendChild(zamanEl);
    kart.appendChild(ust);

    var metin = document.createElement("div");
    metin.className = "notam-ozet";
    metin.textContent = veri.text || "";
    kart.appendChild(metin);

    var kalanMs = veri.created_at + YASAM_SURESI_MS - Date.now();
    var kalanSaat = Math.max(0, Math.round(kalanMs / 3600000));
    var kalan = document.createElement("div");
    kalan.className = "atc-not-kalan";
    // Emoji DEGIL duz metin: burasi textContent, SVG konulamaz.
    kalan.textContent = "yaklaşık " + kalanSaat + " saat sonra otomatik silinecek";
    kart.appendChild(kalan);

    return kart;
  }}

  function listeyiGoster(kayitlar) {{
    var simdi = Date.now();
    var gecerliler = [];
    Object.keys(kayitlar || {{}}).forEach(function (id) {{
      var n = kayitlar[id];
      if (!n || typeof n.created_at !== "number") return;
      if (simdi - n.created_at >= YASAM_SURESI_MS) return;   // suresi dolmus - gosterme
      gecerliler.push(n);
    }});
    gecerliler.sort(function (a, b) {{ return b.created_at - a.created_at; }});

    fabRozetEl.textContent = gecerliler.length > 99 ? "99+" : String(gecerliler.length);
    fabRozetEl.hidden = gecerliler.length === 0;

    listeEl.innerHTML = "";
    if (!gecerliler.length) {{
      listeEl.textContent = "Aktif not yok.";
      return;
    }}
    gecerliler.forEach(function (n) {{ listeEl.appendChild(notKarti(n)); }});
  }}

  function veriYukle() {{
    if (!DB_URL) {{
      listeEl.textContent = "ATC Notes şu anda yapılandırılmamış.";
      return;
    }}
    fetch(tabanUrl() + "?_=" + Date.now())
      .then(function (r) {{ if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }})
      .then(listeyiGoster)
      .catch(function (err) {{
        listeEl.textContent = "ATC Notes şu anda yüklenemiyor.";
        console.error("[atc-notes] okuma hatası:", err);
      }});
  }}

  function panelAc() {{
    panelOrtuEl.hidden = false;
    veriYukle();
  }}

  function panelKapat() {{
    panelOrtuEl.hidden = true;
  }}

  function modalAc() {{
    yazanEl.value = "";
    metinEl.value = "";
    hataEl.textContent = "";
    modalEl.hidden = false;
    yazanEl.focus();
  }}

  function modalKapat() {{
    modalEl.hidden = true;
  }}

  function notKaydet() {{
    var yazan = yazanEl.value.trim();
    var metin = metinEl.value.trim();

    if (!DB_URL) {{ hataEl.textContent = "ATC Notes şu anda yapılandırılmamış."; return; }}
    if (!yazan) {{ hataEl.textContent = "Adınızı girin."; return; }}
    if (yazan.length > AUTHOR_MAKS) {{ hataEl.textContent = "Ad en fazla " + AUTHOR_MAKS + " karakter olabilir."; return; }}
    if (!metin) {{ hataEl.textContent = "Not boş olamaz."; return; }}
    if (metin.length > TEXT_MAKS) {{ hataEl.textContent = "Not en fazla " + TEXT_MAKS + " karakter olabilir."; return; }}
    // basit debounce - art arda hizli gonderimi onler (gercek rate limit
    // sunucu tarafinda yok, bu sadece yanlislikla cift tiklama/spam icin)
    if (Date.now() - sonGonderimZamani < 3000) {{ return; }}

    hataEl.textContent = "";
    kaydetBtn.disabled = true;
    fetch(tabanUrl(), {{
      method: "POST",
      headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify({{author: yazan, text: metin, created_at: {{".sv": "timestamp"}}}}),
    }})
      .then(function (r) {{ if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }})
      .then(function () {{
        sonGonderimZamani = Date.now();
        modalKapat();
        veriYukle();
      }})
      .catch(function (err) {{
        hataEl.textContent = "Not kaydedilemedi, tekrar deneyin.";
        console.error("[atc-notes] yazma hatası:", err);
      }})
      .finally(function () {{ kaydetBtn.disabled = false; }});
  }}

  fabEl.addEventListener("click", panelAc);
  document.getElementById("atc-panel-kapat").addEventListener("click", panelKapat);
  panelOrtuEl.addEventListener("click", function (e) {{ if (e.target === panelOrtuEl) panelKapat(); }});

  document.getElementById("atc-not-ekle-btn").addEventListener("click", modalAc);
  document.getElementById("atc-not-iptal").addEventListener("click", modalKapat);
  kaydetBtn.addEventListener("click", notKaydet);
  modalEl.addEventListener("click", function (e) {{ if (e.target === modalEl) modalKapat(); }});

  // Rozet (badge) sayisi icin arka planda da veri cekilir - panel kapaliyken
  // bile FAB uzerindeki aktif-not sayisi guncel kalsin diye.
  veriYukle();
  setInterval(veriYukle, POLL_ARALIGI_MS);
}})();
</script>
<script>
(function () {{
  "use strict";
  // Web Push (tarayici bildirimleri) - SPECI/TAF/duzeltme/renk kotulesmesi
  // ve yeni NOTAM icin (bkz. ltfj_push.py). Abonelik ATC Notes ile AYNI
  // Firebase Realtime Database'e, "push_abonelikler" path'ine, DOGRUDAN
  // fetch() ile yazilir - ayri bir SDK/CDN gerekmez. VAPID_PUBLIC_KEY GIZLI
  // DEGIL (bkz. ltfj_ayarlar.py::push); bos ise buton hic gosterilmez.
  var VAPID_PUBLIC_KEY = {push_vapid_public_key};
  var DB_URL = {atc_notes_db_url};
  var btn = document.getElementById("bildirim-izin-btn");
  if (!btn || !VAPID_PUBLIC_KEY) return;

  function destekleniyor_mu() {{
    return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  }}

  function tabanUrl() {{
    var taban = DB_URL;
    while (taban.length && taban.charAt(taban.length - 1) === "/") {{
      taban = taban.slice(0, -1);
    }}
    return taban + "/push_abonelikler";
  }}

  function urlBase64ToUint8Array(base64String) {{
    var dolgu = "=".repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + dolgu).replace(/-/g, "+").replace(/_/g, "/");
    var ham = atob(base64);
    var dizi = new Uint8Array(ham.length);
    for (var i = 0; i < ham.length; i++) dizi[i] = ham.charCodeAt(i);
    return dizi;
  }}

  // Guvenlik icin degil - sadece "ayni endpoint hep ayni anahtara yazsin"
  // (yeniden abone olma cakisma/yinelenen kayit uretmesin) icin senkron,
  // basit bir hash. crypto.subtle.digest promise dondurdugu icin burada
  // gereksiz karmasiklik katardi.
  function idUret(endpoint) {{
    var h = 2166136261;
    for (var i = 0; i < endpoint.length; i++) {{
      h ^= endpoint.charCodeAt(i);
      h = (h * 16777619) >>> 0;
    }}
    return "p" + h.toString(16) + endpoint.length;
  }}

  // Ikon ve metin ayri dugum: yalnizca metin degisir, SVG yerinde kalir.
  var ZIL = {ikon_zil_js};
  var ZIL_KAPALI = {ikon_zil_kapali_js};
  var btnIkon = document.getElementById("bildirim-ikon");
  var btnMetin = document.getElementById("bildirim-metin");

  function durumGoster(durum) {{
    btn.hidden = false;
    var DURUMLAR = {{
      "acik":          ["Bildirimler açık",            false, ZIL],
      "reddedildi":    ["İzin verilmedi",              true,  ZIL_KAPALI],
      "beklemede":     ["…",                           true,  ZIL],
      "hata":          ["Bildirimler (tekrar dene)",   false, ZIL],
      "varsayilan":    ["Bildirimlere izin ver",       false, ZIL]
    }};
    if (durum === "desteklenmiyor") {{ btn.hidden = true; return; }}
    var d = DURUMLAR[durum] || DURUMLAR["varsayilan"];
    if (btnMetin) {{ btnMetin.textContent = d[0]; }}
    if (btnIkon) {{ btnIkon.innerHTML = d[2]; }}
    btn.disabled = d[1];
  }}

  // Tarayicidaki abonelik TEK BASINA yetmez - sunucu (ltfj_push.py) SADECE
  // Firebase'deki kayitlara gonderir. fetch() HTTP 401/403'te REDDETMEZ, bu
  // yuzden yanit.ok ACIKCA kontrol edilir: aksi halde kurallar yazmayi
  // engellese bile buton "Bildirimler acik" der, kullanici abone oldugunu
  // sanir ama sunucuda hicbir kayit olmaz (21.09.2026 TAF'inda bu oldu).
  function abonelikKaydet(sub) {{
    var veri = sub.toJSON();
    if (!DB_URL) return Promise.reject(new Error("DB_URL tanımlı değil"));
    return fetch(tabanUrl() + "/" + idUret(veri.endpoint) + ".json", {{
      method: "PUT",
      headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify({{
        endpoint: veri.endpoint, keys: veri.keys,
        created_at: {{".sv": "timestamp"}},
      }}),
    }}).then(function (yanit) {{
      if (!yanit.ok) {{
        throw new Error("abonelik sunucuya kaydedilemedi: HTTP " + yanit.status +
                        " (Firebase kuralları push_abonelikler yazmaya izin veriyor mu?)");
      }}
      return yanit;
    }});
  }}

  function aboneOl() {{
    if (Notification.permission === "denied") {{ durumGoster("reddedildi"); return; }}
    durumGoster("beklemede");
    navigator.serviceWorker.register("sw.js").then(function () {{
      // subscribe() aktif (activate asamasini gecmis) bir servis calisani
      // ister - register()'in dondurdugu kayit "installing" durumunda
      // olabilir, bu yuzden hazir olana kadar bekleyen .ready kullanilir.
      return navigator.serviceWorker.ready;
    }}).then(function (kayit) {{
      return Notification.requestPermission().then(function (izin) {{
        if (izin !== "granted") {{ durumGoster("reddedildi"); throw new Error("izin verilmedi"); }}
        return kayit.pushManager.getSubscription().then(function (mevcut) {{
          return mevcut || kayit.pushManager.subscribe({{
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
          }});
        }});
      }});
    }}).then(function (sub) {{
      return abonelikKaydet(sub).then(function () {{ durumGoster("acik"); }});
    }}).catch(function (err) {{
      console.error("[push] abone olma hatası:", err);
      if (Notification.permission !== "denied") durumGoster("hata");
    }});
  }}

  function baslangicDurumu() {{
    if (!destekleniyor_mu()) {{ durumGoster("desteklenmiyor"); return; }}
    if (Notification.permission === "denied") {{ durumGoster("reddedildi"); return; }}
    navigator.serviceWorker.getRegistration().then(function (kayit) {{
      return kayit ? kayit.pushManager.getSubscription() : null;
    }}).then(function (sub) {{
      durumGoster(sub ? "acik" : "kapali");
    }}).catch(function () {{ durumGoster("kapali"); }});
  }}

  btn.addEventListener("click", aboneOl);
  baslangicDurumu();
}})();
</script>
<script>
(function () {{
  "use strict";
  // Sayfanin METAR/TAF/pist govdesi bot her calistiginda YENIDEN uretilen
  // statik bir dosyadir (canli bir fetch() ile guncellenmez) - "Yenile"
  // butonu bu yuzden butun sayfayi, tarayici onbellegini atlayacak sekilde
  // (cache-buster query param) yeniden yukler; boylece NOTAM/ATC Notes
  // bolumleri de en guncel notam_veri.json/Firebase verisiyle acilir.
  document.getElementById("sayfa-yenile-btn").addEventListener("click", function () {{
    window.location.href = window.location.pathname + "?_=" + Date.now();
  }});
}})();
</script>
<script>
(function () {{
  "use strict";
  // VFR sekmesi/paneli TAMAMEN statik render edilir (bkz. ltfj_vfr.py) -
  // burada sadece acma/kapama var, hicbir fetch() yapilmaz.
  var sekme = document.getElementById("vfr-sekme");
  var ortu = document.getElementById("vfr-panel-ortu");
  var kapat = document.getElementById("vfr-panel-kapat");
  if (!sekme || !ortu) return;
  sekme.addEventListener("click", function () {{ ortu.hidden = false; }});
  if (kapat) kapat.addEventListener("click", function () {{ ortu.hidden = true; }});
  ortu.addEventListener("click", function (e) {{ if (e.target === ortu) ortu.hidden = true; }});
}})();
</script>
<script>
(function () {{
  "use strict";
  // Istatistiksel sis olasiligi kartindaki "Iki modelin baglantisini gor"
  // butonu - statik bir PNG'yi (sis_model_baglantisi.png) modalda gosterir,
  // hicbir fetch() yapilmaz.
  var btn = document.getElementById("sis-model-diyagram-btn");
  var ortu = document.getElementById("sis-model-modal");
  var kapat = document.getElementById("sis-model-modal-kapat");
  if (!btn || !ortu) return;
  btn.addEventListener("click", function () {{ ortu.hidden = false; }});
  if (kapat) kapat.addEventListener("click", function () {{ ortu.hidden = true; }});
  ortu.addEventListener("click", function (e) {{ if (e.target === ortu) ortu.hidden = true; }});
}})();
</script>
<script>
(function () {{
  "use strict";
  // Trend grafiklerinde imlecin/parmagin altindaki noktanin saatini ve
  // degerini gosterir. Fare: uzerine gelince gorunur, ayrilinca kaybolur.
  // Dokunmatik: basili tutup surukledikce gosterir, parmak kalkinca kaybolur.
  // Nokta verisi sayfa uretilirken data-noktalar'a gomulu - hicbir fetch()
  // yapilmaz (bkz. ltfj_sayfa._grafik_blogu).
  var kutular = document.querySelectorAll(".grafik-kutu");
  Array.prototype.forEach.call(kutular, function (kutu) {{
    var noktalar;
    try {{
      noktalar = JSON.parse(kutu.getAttribute("data-noktalar") || "[]");
    }} catch (e) {{
      return;
    }}
    if (!noktalar.length) return;

    var sarmal = kutu.querySelector(".grafik-sarmal");
    var imlec = kutu.querySelector(".grafik-imlec");
    var nokta = kutu.querySelector(".grafik-nokta");
    var balon = kutu.querySelector(".grafik-balon");
    if (!sarmal || !imlec || !nokta || !balon) return;
    var basili = false;

    function gizle() {{
      basili = false;
      imlec.hidden = true;
      nokta.hidden = true;
      balon.hidden = true;
    }}

    function goster(olay) {{
      var alan = sarmal.getBoundingClientRect();
      if (!alan.width) return;
      var oran = (olay.clientX - alan.left) / alan.width;
      var enYakin = noktalar[0], enKisa = Infinity;
      for (var i = 0; i < noktalar.length; i++) {{
        var uzaklik = Math.abs(noktalar[i].x - oran);
        if (uzaklik < enKisa) {{ enKisa = uzaklik; enYakin = noktalar[i]; }}
      }}
      var px = enYakin.x * alan.width;
      imlec.style.left = px + "px";
      nokta.style.left = px + "px";
      nokta.style.top = (enYakin.y * alan.height) + "px";
      balon.textContent = enYakin.s + " · " + enYakin.d;
      imlec.hidden = false;
      nokta.hidden = false;
      balon.hidden = false;
      // balon grafik kutusunun ICINDE kalsin: yatayda kenarlarda kirpilmasin,
      // dikeyde noktanin TERS tarafina gecsin (noktayi ve baslik satirini
      // kapatmasin).
      var genislik = balon.offsetWidth;
      balon.style.left = Math.max(0, Math.min(px - genislik / 2, alan.width - genislik)) + "px";
      balon.style.top = (enYakin.y < 0.5 ? alan.height - balon.offsetHeight : 0) + "px";
    }}

    sarmal.addEventListener("pointerenter", function (e) {{
      if (e.pointerType === "mouse") goster(e);
    }});
    sarmal.addEventListener("pointermove", function (e) {{
      if (e.pointerType === "mouse" || basili) goster(e);
    }});
    sarmal.addEventListener("pointerdown", function (e) {{
      if (e.pointerType !== "mouse") {{ basili = true; goster(e); }}
    }});
    sarmal.addEventListener("pointerleave", gizle);
    sarmal.addEventListener("pointerup", function (e) {{
      if (e.pointerType !== "mouse") gizle();
    }});
    sarmal.addEventListener("pointercancel", gizle);
  }});
}})();
</script>
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

    if uzatildi:
        kenar_x = x(t1)
        ek_yol = (f'<path d="M{son_x:.1f},{son_y:.1f} L{kenar_x:.1f},{son_y:.1f}" '
                  f'fill="none" stroke="{renk}" stroke-width="2" '
                  f'stroke-linecap="round" stroke-dasharray="5,4"/>')
        nokta_svg = (f'<circle cx="{son_x:.1f}" cy="{son_y:.1f}" r="4" '
                     f'fill="none" stroke="{renk}" stroke-width="2"/>' + ek_yol)
    else:
        nokta_svg = f'<circle cx="{son_x:.1f}" cy="{son_y:.1f}" r="3" fill="{renk}"/>'

    svg = (f'<svg viewBox="0 0 {genislik} {yukseklik}" class="grafik" '
           f'preserveAspectRatio="none">'
           f"{dolgu}{esik_svg}"
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
                   gecmis: list, simdi: datetime, guncel: dict | None) -> str:
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
        son_etiket = '<span class="grafik-son grafik-son-yok">raporlanmıyor</span>'
        durum_notu = (
            f'<div class="grafik-durum-notu">Son ölçüm: {son_deger:.0f} '
            f'{html.escape(birim)} · {_zaman_metni(noktalar[-1][0])} — o zamandan '
            f'beri raporlanmıyor.</div>'
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


def _trend_bolumu(gecmis: list) -> str:
    if not gecmis:
        return ""
    simdi = datetime.now(timezone.utc)
    guncel = _en_son_kayit(gecmis)
    bloklar = [_grafik_blogu(alan, baslik, birim, gecmis, simdi, guncel)
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
    """Istatistiksel sis olasiligi karti.

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
            '<div class="sis-olasilik-ek">Sis eğilimi: '
            f'<span class="sis-olasilik-bant {b_sinif}">{b_tertil}</span>'
            '<div class="sis-olasilik-ek-not">Görüş henüz düşmemiş olsa da, '
            'mevcut nem, rüzgâr ve sıcaklık koşullarının sis oluşumuna ne '
            'kadar uygun olduğunu gösterir. Resmî bir tahmin değildir, '
            'sadece ek bir ipucudur.</div></div>'
        )

    return (
        '<div class="alt-bolum sis-olasilik">'
        '<div class="basrow"><span class="tip">İstatistiksel sis olasılığı</span>'
        '<span class="lvo-provenance">İSTATİSTİKSEL</span></div>'
        '<div class="sis-olasilik-ust">'
        f'<span class="sis-olasilik-deger">%{yuzde}</span>'
        f'<span class="sis-olasilik-bant {bant_sinif}">{bant_metin}</span>'
        '</div>'
        f'<div class="sis-olasilik-alt">Önümüzdeki {sis_olasilik.HEDEF_UFUK_SAAT} saat '
        f'içinde görüşün {sis_olasilik.HEDEF_GORUS_M} m altına düşme olasılığı</div>'
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
        '<h3>Model A ve Model B nasıl bağlantılı?</h3>'
        '<img src="sis_model_baglantisi.png" loading="lazy" '
        'alt="Model A ve Model B\'nin girdi, çıktı ve birbirine bağlandığı yeri '
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
        '<button type="button" id="vfr-panel-kapat" class="atc-panel-kapat" aria-label="Kapat">{ikon_kapat}</button>'
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
        return ("bildirilmedi", "") if t is None else (f"{t:g}", "ft")
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


# Iyiden kotuye - gosterge bunu TERS cizer (kotu solda) ki "asagi
# dogru bozuluyor" okumasi soldan saga olsun.
BANT_SIRASI = tuple(k for k, _, _ in pist.RENK_DURUMLARI) + ("RED",)


def _bant_gostergesi_html(cozum: dict, anahtar: str) -> str:
    """Degerin BLU..RED bandinda NEREDE durdugunu KONUMLA gosterir.

    NEDEN: renk tek tasiyici olmasin. Esik asimi zaten sayiyi boyuyor
    (bkz. _olcu_bandi) ama renk korlugunde, tek renkli baskida ve gunes
    altinda renk zayif bir kanal. Konum her kosulda okunur.

    Ayrica "bir sonraki esige ne kadar var" sorusunu cevapliyor - sayi
    tek basina bunu soylemiyor.

    UYDURMA YOK: bantlar ltfj_pist.RENK_DURUMLARI'nin kendisi; ara deger
    interpolasyonu YAPILMIYOR, yalnizca hangi bantta oldugu isaretleniyor."""
    kod = _olcu_bant_kodu(cozum, anahtar)
    if kod is None:
        return ""
    band = _olcu_bandi(cozum, anahtar)
    sinif = f" bant-{band}" if band else ""
    kutular = []
    for b in BANT_SIRASI[::-1]:                 # kotuden iyiye: RED -> BLU
        aktif = " bant-aktif" if b == kod else ""
        kutular.append(f'<span class="bant-kutu{aktif}"></span>')
    ad = {"gorus": "Görüş", "tavan": "Tavan"}.get(anahtar, anahtar)
    return (f'<div class="bant{sinif}" role="img" '
            f'aria-label="{ad} durum bandı: {kod}" '
            f'title="{ad} bandı: {kod} — ölçek ltfj_pist.RENK_DURUMLARI">'
            + "".join(kutular)
            + f'<span class="bant-kod">{kod}</span></div>')


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
            + _bant_gostergesi_html(cozum, anahtar)
            + (kiv or '<div class="hero-yok">eğilim verisi yok</div>') + "</div>")
    return '<div class="hero">' + "".join(hucreler) + "</div>"


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

    rozet = ""
    if notlar and notlar["renk"]:
        kod, aciklama = notlar["renk"]
        # title tooltip: bu resmi bir ICAO CAT I/II/III kategorisi degil,
        # botun kendi durum seviyesi - etiket ltfj_pist.RENK_ETIKETI'den
        # (notlar["renk_etiketi"]) geliyor, burada ayrica sabit metin
        # olarak YAZMIYORUZ ki diger ekranlarla (Telegram, ATC panel)
        # sessizce farklilasmasin.
        rozet = (f'<span class="rozet" title="{html.escape(notlar["renk_etiketi"])} — '
                 f'resmî ICAO CAT I/II/III kategorisi değildir" '
                 f'style="background:{RENK_KODU.get(kod, "#64748b")}">'
                 # RENK_SIMGE (emoji daire) YERINE SVG: rozet zaten renk
                 # kodunun kendi rengini arka plan olarak tasiyor, emoji
                 # daire uzerine binen ikinci bir renk katmaniydi ve
                 # platformdan platforma bambaska ciziliyordu. RENK_SIMGE
                 # Telegram tarafinda KALIYOR - orada SVG yok.
                 f'{ikon("nokta", "ikon rozet-nokta")}{kod} · '
                 f'{html.escape(aciklama)}</span>')

    # Sol kenarda durum rengi: rozet kaliyor ama kart listesini taramak
    # anliklasiyor. Renk TEK BASINA anlam tasimiyor - rozet metni de var.
    kenar = ""
    if notlar and notlar["renk"]:
        kenar = (f' kart-durum" style="--durum-renk:'
                 f'{RENK_KODU.get(notlar["renk"][0], "#64748b")}')
    p = [f'<div class="kart{kenar}"><div class="basrow">'
         f'<span class="tip">{html.escape(ad)}</span>'
         f'<span class="zaman">{html.escape(zaman)}</span>{rozet}</div>']

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

    govde = taf_bicimle(rapor["metin"]) if tip == "TAF" else rapor["metin"]
    p.append(f"<pre>{html.escape(govde)}</pre></div>")
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
            return {"tavan": "tavan yok"}.get(anahtar, "—")
        # Spread'de birim YAZILMIYOR: "Δ" zaten farki anlatiyor ve
        # serit dar ekranda tek satirda kalmali.
        if on:
            return on + deger + "°"
        return deger + (f" {birim}" if birim else "")

    rozet = ""
    if notlar and notlar.get("renk"):
        kod, _ = notlar["renk"]
        rozet = (f'<span class="ozet-renk" style="background:'
                 f'{RENK_KODU.get(kod, "#64748b")}">{html.escape(kod)}</span>')

    # (deger, tooltip) - serit kisa olmak zorunda, ne olduklari
    # title'da duruyor; ekran okuyucu da bunu okur.
    ogeler = [
        (_kisa("gorus"), "Görüş"),
        (_kisa("tavan"), "Bulut tavanı"),
        (_kisa("_ruzgar"), "Rüzgâr (yön/hız, G=hamle)"),
        (_kisa("_spread", "Δ"), "Spread (sıcaklık − çiy noktası)"),
    ]
    return ('<div class="ozet-serit" id="ozet-serit">' + rozet
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
    not_html = ("".join(f"<li>{html.escape(n)}</li>" for n in notlar)
                if notlar else "")
    if not (sis_html or gecis_html or not_html):
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
            f"{sis_html}{tavan_bolumu}{gecis_html}"
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
    govde = (("".join(_kart(r, yorum_onbellegi, gecmis, simdi) for r in sirali)
              or "<div class='kart'>Rapor yok.</div>")
             + _trend_bolumu(gecmis))
    icao = raporlar[0].get("icao", "LTFJ") if raporlar else "LTFJ"

    guncel_rapor = next((r for r in sirali if r["tip"] in ("METAR", "SPECI")), None)
    guncel_cozum = metar_coz(guncel_rapor["metin"]) if guncel_rapor else None
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
        SABLON.format(icao=html.escape(icao), govde=govde,
                      yazitipi_css=YAZITIPI_CSS,
                      ikon_zil=ikon("zil"), ikon_yenile=ikon("yenile"),
                      ikon_uyari=ikon("uyari", "ikon ikon-uyari"),
                      ikon_kapat=ikon("kapat"), ikon_not=ikon("not", "ikon ikon-fab"),
                      # JS icine DIZE olarak gomulecek - json.dumps dogru
                      # kacislari yapar, elle tirnak kapatmaya calismayiz.
                      ikon_zil_js=json.dumps(ikon("zil")),
                      ikon_zil_kapali_js=json.dumps(ikon("zil-kapali")),
                      gozlem_taze_dk=GOZLEM_TAZE_DK,
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
                      vfr_html=_vfr_sekmesi_html(guncel_cozum)),
        encoding="utf-8")
    print(f"  web sayfası yazıldı: {hedef.name}")
