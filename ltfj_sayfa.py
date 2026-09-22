#!/usr/bin/env python3
"""
GitHub Pages icin canli durum sayfasi uretir.

Bot her calistiginda index.html'i yeniden yazar, workflow onu repoya commit eder,
GitHub Pages yayinlar. Ek altyapi yok. Sayfa tek dosya - harici CSS/JS yok.
"""

import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ltfj_lvo_farkindalik as farkindalik
import ltfj_lvo_referans as lvo
import ltfj_sis_olasilik as sis_olasilik
import ltfj_sis_olasilik_b as sis_olasilik_b
import ltfj_vfr as vfr
from ltfj_analiz import metar_coz, ozet_satiri, uyarilar
from ltfj_ayarlar import YEREL_TZ
from ltfj_pist import RENK_SIMGE, havacilik_notlari
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

GRAFIK_PENCERE_SAAT = 6
GRAFIK_MIN_NOKTA = 2      # cizgi cizmek icin en az bu kadar nokta lazim
GRAFIK_YEDEK_NOKTA = 12   # pencere yeterli veri vermezse en fazla bu kadar eski kayit gosterilir
GRAFIKLER = (
    ("ruzgar_hiz", "Rüzgâr", "kt", "#3b82f6"),
    ("tavan", "Bulut tavanı", "ft", "#22c55e"),
    ("qnh", "QNH", "hPa", "#eab308"),
    ("sicaklik", "Sıcaklık", "°C", "#ef4444"),
)

SABLON = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{icao} · Hava Durumu</title>
<meta name="description" content="{icao} anlık METAR ve TAF">
<style>
  :root {{
    --bg:#f8fafc; --kart:#ffffff; --metin:#0f172a; --soluk:#64748b;
    --cizgi:#e2e8f0; --vurgu:#0f172a; --kod-bg:#f1f5f9;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg:#0b1220; --kart:#111a2e; --metin:#e8eefc; --soluk:#8fa0bf;
      --cizgi:#1e2a44; --vurgu:#e8eefc; --kod-bg:#0a1120;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg:#0b1220; --kart:#111a2e; --metin:#e8eefc; --soluk:#8fa0bf;
    --cizgi:#1e2a44; --vurgu:#e8eefc; --kod-bg:#0a1120;
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; background:var(--bg); color:var(--metin);
    font:16px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
    padding:24px 16px 48px;
  }}
  .sar {{ max-width:680px; margin:0 auto; }}
  header {{
    margin-bottom:20px; display:flex; align-items:flex-start;
    justify-content:space-between; gap:12px;
  }}
  .header-metin {{ min-width:0; }}
  h1 {{ font-size:1.5rem; margin:0 0 4px; letter-spacing:-.02em; }}
  .alt {{ color:var(--soluk); font-size:.875rem; }}
  button.yenile {{
    flex-shrink:0; background:var(--kod-bg); border:1px solid var(--cizgi);
    color:var(--soluk); border-radius:8px; padding:8px 12px; font:inherit;
    font-size:.82rem; font-weight:650; cursor:pointer; white-space:nowrap;
  }}
  button.yenile:hover {{ color:var(--metin); border-color:var(--vurgu); }}
  button.yenile:disabled {{ opacity:.6; cursor:default; }}
  .header-butonlar {{ display:flex; gap:8px; flex-shrink:0; }}
  @media (max-width:480px) {{
    header {{ flex-wrap:wrap; }}
    .header-metin {{ flex:1 1 100%; }}
    .header-butonlar {{ flex:1 1 100%; justify-content:flex-end; }}
    button.yenile {{ padding:8px 10px; font-size:.78rem; }}
  }}
  .kart {{
    background:var(--kart); border:1px solid var(--cizgi); border-radius:14px;
    padding:18px; margin-bottom:16px;
  }}
  .basrow {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap;
             margin-bottom:12px; }}
  .tip {{ font-weight:650; font-size:1.05rem; }}
  .zaman {{ color:var(--soluk); font-size:.85rem; }}
  .rozet {{
    margin-left:auto; padding:3px 10px; border-radius:999px;
    font-size:.78rem; font-weight:650; color:#fff; white-space:nowrap;
  }}
  .dikkat {{
    background:rgba(239,68,68,.12); border:1px solid rgba(239,68,68,.35);
    border-radius:10px; padding:10px 12px; margin:12px 0; font-size:.9rem;
  }}
  .ozet {{ color:var(--soluk); font-size:.92rem; margin:10px 0; }}
  .yorum {{
    background:var(--kod-bg); border:1px solid var(--cizgi); border-radius:10px;
    padding:10px 12px; margin:12px 0; font-size:.88rem; line-height:1.6;
  }}
  .yorum-etiket {{ color:var(--soluk); font-size:.72rem; margin-bottom:4px; }}
  .pist-kaynak {{ color:var(--soluk); font-size:.78rem; margin-top:6px; }}
  table {{ width:100%; border-collapse:collapse; font-size:.88rem; margin-top:10px; }}
  td {{ padding:7px 0; border-bottom:1px solid var(--cizgi); }}
  td:first-child {{ color:var(--soluk); width:42%; }}
  tr:last-child td {{ border-bottom:none; }}
  pre {{
    background:var(--kod-bg); border:1px solid var(--cizgi); border-radius:10px;
    padding:12px; overflow-x:auto; font-size:.8rem; line-height:1.5;
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace; margin:12px 0 0;
    white-space:pre-wrap; word-break:break-word;
  }}
  footer {{ color:var(--soluk); font-size:.8rem; text-align:center; margin-top:28px; }}
  a {{ color:inherit; }}
  .panel-link {{
    display:inline-block; margin-top:12px; padding:7px 14px; border-radius:8px;
    background:var(--vurgu); color:var(--bg); text-decoration:none;
    font-size:.82rem; font-weight:650;
  }}
  .grafik-ust {{ font-weight:650; margin-bottom:12px; font-size:.95rem; }}
  .grafik-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:18px 20px; }}
  @media (max-width:480px) {{ .grafik-grid {{ grid-template-columns:1fr; }} }}
  .grafik-baslik {{ display:flex; justify-content:space-between; align-items:baseline;
                     font-size:.85rem; color:var(--soluk); margin-bottom:4px; }}
  .grafik-son {{ color:var(--metin); font-weight:650; }}
  .grafik-son-yok {{ color:var(--soluk); font-weight:600; font-style:italic; }}
  .grafik {{ width:100%; height:64px; display:block; }}
  .grafik-eksen {{ display:flex; justify-content:space-between;
                    font-size:.72rem; color:var(--soluk); margin-top:2px; }}
  .grafik-durum-notu {{ font-size:.72rem; color:var(--soluk); margin-top:4px;
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
    padding:3px 8px; font-size:.74rem; font-weight:600; white-space:nowrap;
    color:var(--metin); pointer-events:none; z-index:3;
    box-shadow:0 2px 10px rgba(0,0,0,.35);
  }}
  .grafik-imlec[hidden], .grafik-nokta[hidden], .grafik-balon[hidden] {{ display:none; }}

  .sis-olasilik-ust {{ display:flex; align-items:baseline; gap:10px; margin:6px 0 2px; }}
  .sis-olasilik-deger {{
    font-size:2.2rem; font-weight:700; line-height:1.1;
  }}
  .sis-olasilik-bant {{
    font-size:.74rem; font-weight:650; padding:2px 9px; border-radius:999px;
    text-transform:uppercase; letter-spacing:.03em;
  }}
  .sis-olasilik-bant.dusuk {{ background:#22c55e26; color:#16a34a; }}
  .sis-olasilik-bant.orta {{ background:#f9731626; color:#ea580c; }}
  .sis-olasilik-bant.yuksek {{ background:#ef444426; color:#dc2626; }}
  .sis-olasilik-alt {{ font-size:.85rem; color:var(--soluk); }}
  .sis-olasilik-kiyas {{ font-size:.8rem; color:var(--soluk); margin-top:6px; }}
  .sis-olasilik-ek {{
    font-size:.8rem; color:var(--soluk); margin-top:10px; padding-top:8px;
    border-top:1px dashed var(--cizgi);
  }}
  .sis-olasilik-ek .sis-olasilik-bant {{ margin-left:4px; }}
  .sis-olasilik-ek-not {{ font-size:.72rem; color:var(--soluk); margin-top:4px; }}
  .sis-olasilik-not {{
    font-size:.74rem; color:var(--soluk); margin-top:10px; line-height:1.5;
    border-top:1px solid var(--cizgi); padding-top:8px;
  }}
  .sis-olasilik-diyagram-btn {{
    margin-top:10px; background:none; border:1px solid var(--cizgi);
    color:var(--vurgu); font-size:.78rem; font-weight:650; padding:6px 12px;
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
     daralip "Trend · son 6 saat" uc satira kiriliyordu. Normal akis +
     mutlak konumlu ok, metnin dogal sarmasina izin verir. */
  .kat > summary {{
    cursor:pointer; user-select:none; list-style:none;
    position:relative; padding-right:20px;
    font-size:.82rem; color:var(--soluk);
  }}
  .kat > summary::-webkit-details-marker {{ display:none; }}
  .kat > summary::after {{
    content:"▶"; font-size:.7rem; position:absolute; right:0; top:.2em;
    transition:transform .15s ease; display:inline-block;
  }}
  .kat[open] > summary::after {{ transform:rotate(90deg); }}
  .kat > summary:hover {{ color:var(--metin); }}
  .kat-rozet {{
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.75rem;
    color:var(--metin); font-weight:600; margin-left:8px;
  }}
  /* Kart basligi olarak kullanilan katlanabilir summary - .basrow ile ayni
     tipografi (Trend / NOTAM Geçmişi gibi bolum basliklari icin). */
  .kat-kart > summary {{ font-size:1rem; color:var(--metin); font-weight:650; }}
  /* Bir katlanir kartin icindeki alt bolumler - araya ince cizgi girsin ki
     saatlik tahmin ile olasilik karti ayri ayri okunabilsin (eskiden ayri
     kartlardi). Bolum adlari burada YAZILMIYOR: testler bu adlarin sayfada
     bulunup bulunmadigina bakiyor, CSS yorumu yanlis pozitif uretirdi. */
  .alt-bolum {{ padding-top:12px; }}
  .alt-bolum + .alt-bolum {{ margin-top:12px; border-top:1px solid var(--cizgi); }}
  .kat-kart > summary::after {{ font-size:.7rem; color:var(--soluk); }}

  /* Önümüzdeki saatler şeridi - dar ekranda yatay kaydirilir, dikey
     kaydirmayi bolmesin diye sabit yukseklikli hucreler. */
  .tahmin-uyari {{
    background:rgba(234,179,8,.12); border:1px solid rgba(234,179,8,.4);
    border-radius:10px; padding:8px 10px; margin:8px 0 12px; font-size:.8rem;
  }}
  .tahmin-serit {{
    display:flex; gap:6px; overflow-x:auto; padding-bottom:6px;
    -webkit-overflow-scrolling:touch;
  }}
  .tahmin-hucre {{
    flex:0 0 auto; min-width:66px; text-align:center; padding:8px 6px;
    border:1px solid var(--cizgi); border-radius:10px; background:var(--kod-bg);
  }}
  .tahmin-saat {{
    font-size:.78rem; font-weight:650; margin-bottom:4px;
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  }}
  .tahmin-spread {{ font-size:1.05rem; font-weight:700; margin-bottom:4px; }}
  .tahmin-satir {{ font-size:.72rem; color:var(--soluk); line-height:1.5; }}
  .tahmin-aciklama {{ font-size:.72rem; color:var(--soluk); margin-top:8px; }}

  .bolum-baslik {{ font-weight:650; font-size:1.05rem; margin:28px 0 12px; }}
  .notam-uyari {{
    background:rgba(234,179,8,.12); border:1px solid rgba(234,179,8,.4);
    border-radius:10px; padding:10px 12px; margin-bottom:14px; font-size:.85rem;
  }}
  .notam-kart {{
    border-bottom:1px solid var(--cizgi); padding:12px 0;
  }}
  .notam-kart:last-child {{ border-bottom:none; }}
  .notam-ust {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap;
                margin-bottom:6px; }}
  .notam-no {{ font-weight:650; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
  .notam-etiket {{
    padding:2px 8px; border-radius:999px; font-size:.72rem; font-weight:600;
    background:var(--kod-bg); border:1px solid var(--cizgi); color:var(--soluk);
  }}
  .notam-durum {{ font-size:.75rem; color:var(--soluk); margin-left:auto; }}
  /* Suresi dolmus / henuz baslamamis NOTAM'in durum etiketi - soluk griden
     ayrilsin ki arama sonuclarinda yururlukte olanla karistirilmasin. */
  .notam-durum-gecmis {{ color:#b45309; font-weight:600; }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) .notam-durum-gecmis {{ color:#fbbf24; }}
  }}
  :root[data-theme="dark"] .notam-durum-gecmis {{ color:#fbbf24; }}
  .notam-aktif-nokta {{
    display:inline-block; width:8px; height:8px; border-radius:999px;
    background:#22c55e; box-shadow:0 0 0 2px rgba(34,197,94,.25); flex-shrink:0;
  }}
  .notam-aktif-baslik {{ cursor:pointer; user-select:none; }}
  .notam-aktif-sayi {{
    color:var(--soluk); font-size:.82rem; margin-left:auto; margin-right:4px;
  }}
  .notam-ok {{
    font-size:.7rem; color:var(--soluk); transition:transform .15s ease;
    display:inline-block;
  }}
  .notam-ok.acik {{ transform:rotate(90deg); }}
  .notam-ozet {{ font-size:.88rem; margin:4px 0; }}
  .notam-metin {{
    background:var(--kod-bg); border:1px solid var(--cizgi); border-radius:8px;
    padding:10px; font-size:.78rem; line-height:1.5; margin-top:6px;
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace; white-space:pre-wrap;
    word-break:break-word;
  }}
  .notam-kaynak {{ font-size:.72rem; color:var(--soluk); margin-top:6px; }}
  .notam-bos {{ color:var(--soluk); font-size:.88rem; padding:8px 0; }}
  .notam-arama {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px; }}
  .notam-arama input, .notam-arama select {{
    /* min-width:0 olmadan flex ogesi kendi icerik genisliginin altina
       inemez - dar telefonlarda select'in etiketi kirpiliyordu. */
    flex:1 1 140px; min-width:0; padding:8px 10px; border-radius:8px;
    border:1px solid var(--cizgi);
    background:var(--bg); color:var(--metin); font-size:.85rem;
  }}
  .notam-arama button {{
    padding:8px 14px; border-radius:8px; border:none; background:var(--vurgu);
    color:var(--bg); font-weight:650; font-size:.85rem; cursor:pointer;
  }}
  .notam-arama-not {{ color:var(--soluk); font-size:.78rem; margin:-8px 0 12px; }}

  /* LVO REFERENCE - METAR/NOTAM/ATC Notes'tan gorsel olarak ayri, saf
     bilgi/referans paneli. Hicbir karar uretmez (bkz. ltfj_lvo_referans.py). */
  .lvo-alt-baslik {{
    font-weight:650; font-size:.92rem; margin:18px 0 8px; display:flex;
    align-items:center; gap:8px;
  }}
  .lvo-alt-baslik:first-child {{ margin-top:0; }}
  .lvo-provenance {{
    display:inline-block; padding:2px 8px; border-radius:999px; font-size:.68rem;
    font-weight:700; letter-spacing:.02em; background:var(--kod-bg);
    border:1px solid var(--cizgi); color:var(--soluk);
  }}
  .lvo-tablo {{ width:100%; border-collapse:collapse; font-size:.82rem; margin:6px 0 10px; }}
  .lvo-tablo th, .lvo-tablo td {{
    padding:6px 8px; border-bottom:1px solid var(--cizgi); text-align:left;
    width:auto;
  }}
  .lvo-tablo th {{ color:var(--soluk); font-weight:600; font-size:.72rem; }}
  .lvo-esik-liste {{ font-size:.85rem; margin:4px 0 12px; }}
  .lvo-esik-satir {{
    display:flex; justify-content:space-between; gap:10px; padding:6px 0;
    border-bottom:1px solid var(--cizgi);
  }}
  .lvo-esik-satir:last-child {{ border-bottom:none; }}
  .lvo-esik-deger {{ font-weight:650; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
  .lvo-not-listesi {{ font-size:.78rem; color:var(--soluk); margin:8px 0 0; padding-left:18px; }}
  .lvo-not-listesi li {{ margin-bottom:4px; }}
  .lvo-awos-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:10px; }}
  .lvo-awos-kart {{
    border:1px solid var(--cizgi); border-radius:10px; padding:10px 12px; background:var(--kod-bg);
  }}
  .lvo-awos-pist {{ font-weight:650; margin-bottom:6px; }}
  .lvo-awos-deger {{ display:flex; justify-content:space-between; font-size:.85rem; padding:3px 0; }}
  .lvo-awos-alt {{ font-size:.72rem; color:var(--soluk); margin-top:6px; }}
  .lvo-stale {{
    color:#ef4444; font-weight:700; margin-left:6px;
  }}
  .lvo-form {{ display:flex; flex-wrap:wrap; gap:8px; margin:10px 0; align-items:flex-end; }}
  .lvo-form label {{ display:block; font-size:.72rem; color:var(--soluk); margin-bottom:3px; }}
  .lvo-form input, .lvo-form select {{
    padding:8px 10px; border-radius:8px; border:1px solid var(--cizgi);
    background:var(--bg); color:var(--metin); font-size:.85rem; width:100%; box-sizing:border-box;
  }}
  .lvo-form-alan {{ flex:1 1 100px; }}
  .lvo-form button {{
    padding:8px 14px; border-radius:8px; border:none; background:var(--vurgu);
    color:var(--bg); font-weight:650; font-size:.85rem; cursor:pointer; flex-shrink:0;
  }}
  /* Temizleme YIKICI ve PAYLASILAN veriyi siler - kaydet butonuyla ayni
     agirlikta durmasin diye ikincil (cerceveli) gorunum. */
  .lvo-form button.lvo-awos-temizle {{
    background:transparent; color:var(--soluk); border:1px solid var(--cizgi);
  }}
  .lvo-form button.lvo-awos-temizle:hover {{ color:#ef4444; border-color:#ef4444; }}
  .lvo-hata {{ color:#ef4444; font-size:.8rem; margin-top:6px; min-height:1.1em; }}
  .lvo-esik-kaynak {{ font-size:.72rem; color:var(--soluk); display:block; margin-top:2px; }}

  .atc-not-ekle-btn {{
    margin-left:auto; padding:6px 12px; border-radius:8px; border:none;
    background:var(--vurgu); color:var(--bg); font-weight:650; font-size:.82rem;
    cursor:pointer;
  }}
  .atc-not-kalan {{ color:var(--soluk); font-size:.72rem; margin-top:6px; }}

  /* ATC Notes artik sayfa akisinda degil - sag altta sabit duran bir
     dugmeyle (FAB) acilan yuzen bir panel. Telefonda alttan yukari kayan
     "bottom sheet", genis ekranda dugmenin ustunde sabit bir kart. */
  .atc-fab {{
    position:fixed; right:16px;
    bottom:calc(16px + env(safe-area-inset-bottom, 0px));
    width:56px; height:56px; border-radius:999px; border:none;
    background:var(--vurgu); color:var(--bg); font-size:1.4rem;
    box-shadow:0 4px 16px rgba(0,0,0,.3); cursor:pointer; z-index:60;
    display:flex; align-items:center; justify-content:center;
  }}
  .atc-fab-rozet {{
    position:absolute; top:-2px; right:-2px; min-width:20px; height:20px;
    padding:0 5px; border-radius:999px; background:#ef4444; color:#fff;
    font-size:.68rem; font-weight:700; display:flex; align-items:center;
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
  .atc-panel-ust .tip {{ font-weight:650; font-size:1.05rem; }}
  .atc-panel-kapat {{
    width:32px; height:32px; border-radius:999px; border:none; flex-shrink:0;
    background:var(--kod-bg); color:var(--metin); font-size:1.1rem; cursor:pointer;
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
  .modal-kutu h3 {{ margin:0 0 4px; font-size:1.05rem; }}
  .modal-kutu label {{ display:block; font-size:.82rem; color:var(--soluk); margin:12px 0 4px; }}
  .modal-kutu input, .modal-kutu textarea {{
    width:100%; padding:8px 10px; border-radius:8px; border:1px solid var(--cizgi);
    background:var(--bg); color:var(--metin); font-size:.9rem; font-family:inherit;
    box-sizing:border-box; resize:vertical;
  }}
  .modal-hata {{ color:#ef4444; font-size:.8rem; margin-top:8px; min-height:1.1em; }}
  .modal-butonlar {{ display:flex; gap:8px; justify-content:flex-end; margin-top:14px; }}
  .modal-butonlar button {{
    padding:8px 16px; border-radius:8px; border:none; font-weight:650; font-size:.85rem;
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
    font-weight:700; font-size:.8rem; letter-spacing:.05em; cursor:pointer;
    writing-mode:vertical-rl; text-orientation:mixed;
    box-shadow:0 2px 10px rgba(0,0,0,.3);
  }}
  .vfr-sekme.vfr-yesil {{ background:#22c55e; }}
  .vfr-sekme.vfr-kirmizi {{ background:#ef4444; }}
  .vfr-sekme.vfr-bilinmiyor {{ background:#64748b; }}
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
  .vfr-panel-ust h3 {{ margin:0; font-size:1rem; display:flex; align-items:center; gap:8px; flex:1; }}
  .vfr-nokta {{ width:10px; height:10px; border-radius:999px; display:inline-block; flex-shrink:0; }}
  .vfr-nokta.yesil {{ background:#22c55e; }}
  .vfr-nokta.kirmizi {{ background:#ef4444; }}
  .vfr-nokta.bilinmiyor {{ background:#64748b; }}
  .vfr-panel ul {{ margin:10px 0 0; padding-left:18px; font-size:.85rem; }}
  .vfr-panel .vfr-esik {{ color:var(--soluk); font-size:.72rem; margin-top:10px; }}
</style>
</head>
<body>
<div class="sar">
<header>
  <div class="header-metin">
    <h1>{icao} · İstanbul Sabiha Gökçen</h1>
    <div class="alt">Kaynak: MGM/METAR · Son güncelleme {guncelleme}</div>
  </div>
  <div class="header-butonlar">
    <button type="button" class="yenile" id="bildirim-izin-btn" hidden>🔔 Bildirimler</button>
    <button type="button" class="yenile" id="sayfa-yenile-btn">⟳ Yenile</button>
  </div>
</header>
{govde}
{beklenti_html}

<div class="kart">
  <div class="basrow notam-aktif-baslik" id="lvo-baslik" role="button" tabindex="0"
       aria-expanded="false">
    <span class="tip">LVO REFERENCE</span>
    <span class="notam-ok" id="lvo-ok">▶</span>
  </div>
  <div id="lvo-govde" hidden>
    <div class="notam-uyari">
      ⚠️ Bilgi amaçlıdır. Operasyonel karar yerine geçmez. Güncel AIP, ATIS, AWOS
      ve resmî yayınlar kontrol edilmelidir.
    </div>

    <div class="lvo-alt-baslik">Farkındalık Notları
      <span class="lvo-provenance">METAR/TAF/AWOS</span></div>
{lvo_farkindalik_html}

{lvo_referans_html}

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
  </div>
</div>


<!-- TEK "NOTAM" basligi: aktif liste + gecmis aramasi + kaynak uyarisi.
     Eskiden ucu de ayri ayri sayfada duruyordu (bolum basligi + sari uyari
     kutusu + iki kart). Uyari EN ALTTA: her acilista once okunan degil,
     gerektiginde basvurulan bir not. -->
<div class="kart">
  <details class="kat kat-kart">
  <summary>NOTAM
    <span class="kat-rozet" id="notam-aktif-sayi"></span>
    <span class="zaman" id="notam-senkron-zamani"></span>
  </summary>

  <div class="alt-bolum">
    <div class="basrow"><span class="tip">Aktif NOTAM'lar</span></div>
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
    ⚠️ Bilgi amaçlıdır. Operasyon öncesi güncel resmî NOTAM/PIB kontrol edilmelidir.
    Kaynak: NOTAC (FAA NOTAM Management System tabanlı üçüncü taraf servis) —
    resmî bir Türk/EUROCONTROL NOTAM kaynağı değildir. Bu bölüm hiçbir operasyonel
    öneri üretmez; sayfadaki meteorolojik analiz bu veriden bağımsızdır.
  </div>
  </details>
</div>

<!-- ATC Notes artik sayfa akisinda degil - sag altta sabit FAB'la acilan
     yuzen bir panel (bkz. asagidaki .atc-fab/.atc-panel-ortu). -->
<button type="button" id="atc-fab" class="atc-fab" aria-label="ATC Notes'u aç" title="ATC Notes">
  📋<span id="atc-fab-rozet" class="atc-fab-rozet" hidden>0</span>
</button>

<div id="atc-panel-ortu" class="atc-panel-ortu" hidden>
  <div class="atc-panel">
    <div class="atc-panel-ust">
      <span class="tip">ATC Notes</span>
      <button type="button" id="atc-not-ekle-btn" class="atc-not-ekle-btn">+ NOT EKLE</button>
      <button type="button" id="atc-panel-kapat" class="atc-panel-kapat" aria-label="Kapat">✕</button>
    </div>
    <div class="atc-panel-govde">
      <div class="notam-uyari">
        ⚠️ Bu bölüm ATC tarafından paylaşılan geçici durumsal farkındalık
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
        ' <span style="color:var(--soluk); font-size:.75rem;">(NOTAC otomatik özeti — hata içerebilir)</span></div>'
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
      "<details><summary style=\\"cursor:pointer; font-size:.82rem; color:var(--soluk);\\">Ham NOTAM metni</summary>" +
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
    senkronEl.textContent = veri.son_senkron
      ? "son senkron " + veri.son_senkron.replace("T", " ").slice(0, 16)
      : "henüz senkronize edilmedi";

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

  var lvoBaslikEl = document.getElementById("lvo-baslik");
  var lvoGovdeEl = document.getElementById("lvo-govde");
  var lvoOkEl = document.getElementById("lvo-ok");
  var farkRvrListeEl = document.getElementById("lvo-fark-rvr-liste");
  var farkBosEl = document.getElementById("lvo-fark-bos");
  var lvoAcikMi = false;

  function lvoPaneliAcKapat() {{
    lvoAcikMi = !lvoAcikMi;
    lvoGovdeEl.hidden = !lvoAcikMi;
    lvoBaslikEl.setAttribute("aria-expanded", String(lvoAcikMi));
    lvoOkEl.textContent = lvoAcikMi ? "▼" : "▶";
    lvoOkEl.classList.toggle("acik", lvoAcikMi);
  }}
  lvoBaslikEl.addEventListener("click", lvoPaneliAcKapat);
  lvoBaslikEl.addEventListener("keydown", function (e) {{
    if (e.key === "Enter" || e.key === " ") {{ e.preventDefault(); lvoPaneliAcKapat(); }}
  }});

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
          return fetch(tabanUrl("awos_rvr") + "/" + encodeURIComponent(id) + ".json",
                       {{method: "DELETE"}})
            .then(function (r) {{
              if (!r.ok) throw new Error("HTTP " + r.status);
            }});
        }}));
      }})
      .then(function (sonuc) {{ if (sonuc) awosYukle(); }})
      .catch(function (err) {{
        awosHataEl.textContent = "AWOS RVR temizlenemedi (Firebase kuralları "
          + "silmeye izin veriyor mu?), tekrar deneyin.";
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
    kalan.textContent = "⏳ yaklaşık " + kalanSaat + " saat sonra otomatik silinecek";
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

  function durumGoster(durum) {{
    btn.hidden = false;
    if (durum === "acik") {{
      btn.textContent = "🔔 Bildirimler açık";
      btn.disabled = false;
    }} else if (durum === "reddedildi") {{
      btn.textContent = "🔕 İzin verilmedi";
      btn.disabled = true;
    }} else if (durum === "beklemede") {{
      btn.textContent = "…";
      btn.disabled = true;
    }} else if (durum === "hata") {{
      btn.textContent = "🔔 Bildirimler (tekrar dene)";
      btn.disabled = false;
    }} else if (durum === "desteklenmiyor") {{
      btn.hidden = true;
    }} else {{
      btn.textContent = "🔔 Bildirimlere izin ver";
      btn.disabled = false;
    }}
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


def _svg_cizgi(noktalar: list, renk: str, raporlanmiyor: bool = False,
               guncel_zaman: datetime | None = None,
               genislik=600, yukseklik=64) -> tuple | None:
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
    v_min, v_max = min(degerler), max(degerler)
    if v_min == v_max:
        v_min, v_max = v_min - 1, v_max + 1
    pad = (v_max - v_min) * 0.15
    v_min, v_max = v_min - pad, v_max + pad

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


def _grafik_blogu(alan: str, baslik: str, birim: str, renk: str,
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
    cizim = _svg_cizgi(noktalar, renk, raporlanmiyor=raporlanmiyor,
                       guncel_zaman=guncel_zaman)
    if not cizim:
        return ""
    svg, oranlar = cizim
    son_deger = noktalar[-1][1]
    son_zaman_yerel = noktalar[-1][0].astimezone(YEREL_TZ)
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
            f'{html.escape(birim)} · {son_zaman_yerel:%H:%M} yerel — o zamandan '
            f'beri raporlanmıyor.</div>'
        )
    else:
        son_etiket = f'<span class="grafik-son">{son_deger:.0f} {html.escape(birim)}</span>'
        durum_notu = ""

    return (
        f'<div class="grafik-kutu" '
        f'data-noktalar="{html.escape(json.dumps(nokta_verisi, ensure_ascii=False))}">'
        f'<div class="grafik-baslik"><span>{html.escape(baslik)}</span>'
        f'{son_etiket}</div>'
        f'<div class="grafik-sarmal">{svg}'
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
    bloklar = [_grafik_blogu(alan, baslik, birim, renk, gecmis, simdi, guncel)
               for alan, baslik, birim, renk in GRAFIKLER]
    bloklar = [b for b in bloklar if b]
    if not bloklar:
        return ""
    # Katli gelir - 563 px'lik dort grafik, "su an ne oluyor" sorusunun
    # cevabi degil; bakmak isteyince aciliyor. Basliktaki rozet, kapaliyken
    # de son degerleri gosterir ki bolum UNUTULMASIN.
    # Rozet SADECE degerler - basliklari da yazinca uc satira tasiyordu ve
    # ozet rozeti okunabilirligini kaybediyordu. Hemen altindaki grafikler
    # zaten hangi degerin ne oldugunu adiyla yaziyor.
    ozet = " · ".join(
        f"{guncel[alan]:g}{birim}"
        for alan, _, birim, _ in GRAFIKLER
        if guncel and guncel.get(alan) is not None)
    rozet = f'<span class="kat-rozet">{html.escape(ozet)}</span>' if ozet else ""
    return ('<div class="kart"><details class="kat kat-kart">'
            f'<summary>Trend · son 6 saat {rozet}</summary>'
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
        '<div class="lvo-alt-baslik">A) Document Reference '
        f'<span class="lvo-provenance">{html.escape(lvo.DOKUMAN["etiket"])}</span></div>'
        f'<div style="font-size:.85rem;">{html.escape(lvo.DOKUMAN["baslik"])}<br>'
        f'<b>{html.escape(lvo.DOKUMAN["dok_no"])} {html.escape(lvo.DOKUMAN["rev_no"])} — '
        f'{html.escape(lvo.DOKUMAN["rev_tarihi"])}</b></div>'
        '<table class="lvo-tablo"><thead><tr><th>Pist</th><th>Kategori</th>'
        "<th>İniş RVR (m)</th><th>Kalkış RVR (m)</th><th>Açıklama</th></tr></thead>"
        f"<tbody>{pist_satirlari}</tbody></table>"
        '<table class="lvo-tablo"><thead><tr><th>Kategori</th><th>RVR</th><th>DH</th></tr></thead>'
        f"<tbody>{kategori_satirlari}</tbody></table>"
        '<div style="font-size:.8rem;font-weight:600;margin-top:.4rem;">'
        "RVR eşikleri (madde 6.1.ee)</div>"
        f'<div class="lvo-esik-liste">{esik_satirlari}</div>'
        '<div style="font-size:.8rem;font-weight:600;margin-top:.4rem;">'
        "Bulut tabanı (ceiling) eşikleri — RVR'dan bağımsız, paralel tetikleyici</div>"
        f'<div class="lvo-esik-liste">{bulut_satirlari}</div>'
        f'<div style="font-size:.8rem;margin-top:.4rem;">{html.escape(lvo.BULUT_PILOT_RAPORU_ISTISNASI)}</div>'
        f'<ul class="lvo-not-listesi">{not_maddeleri}</ul>'
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
    """Katlanmış "Beklenti" başlığında görünen kısa olasılık rozeti -
    kartın kendisiyle AYNI hesabı kullanır (ayrı bir sayı üretmez)."""
    p = _sis_olasiligi_hesapla(guncel_cozum, gecmis, simdi)
    return "" if p is None else f"{p * 100:.1f}"


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
    sis_p = _sis_olasiligi_hesapla(guncel_cozum, gecmis, simdi)
    saat_utc = simdi.astimezone(timezone.utc).hour
    notlar = [n for n in (farkindalik.metar_tavan_notu(guncel_cozum),
                          farkindalik.taf_tavan_notu(taf_tavan),
                          farkindalik.tavan_istatistik_notu(guncel_cozum),
                          farkindalik.tavan_dis_kaynak_notu(
                              guncel_cozum, sis_p, saat_utc)) if n]
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
        '<button type="button" id="vfr-panel-kapat" class="atc-panel-kapat" aria-label="Kapat">✕</button>'
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


def _kart(rapor: dict, yorum_onbellegi: dict | None = None) -> str:
    tip = rapor["tip"]
    cozum = metar_coz(rapor["metin"]) if tip in ("METAR", "SPECI") else None
    notlar = (havacilik_notlari(cozum, rapor["metin"], rapor.get("zaman"))
              if cozum else None)
    yorum = (yorum_onbellegi or {}).get(rapor["metin"])

    ad = tip + (f' {rapor["duzeltme"]}' if rapor.get("duzeltme") else "")
    if rapor.get("zaman"):
        yerel = rapor["zaman"].astimezone(YEREL_TZ)
        zaman = f'{rapor["zaman"]:%d.%m %H:%M}Z · {yerel:%H:%M} yerel'
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
                 f'{RENK_SIMGE.get(kod, "")} {kod} · {html.escape(aciklama)}</span>')

    p = [f'<div class="kart"><div class="basrow">'
         f'<span class="tip">{html.escape(ad)}</span>'
         f'<span class="zaman">{html.escape(zaman)}</span>{rozet}</div>']

    if yorum:
        # Yorum KATLI gelir: METAR/TAF kartlari sayfanin %43'unu kapliyordu
        # (1175 + 970 px) ve sismenin sebebi cok paragrafli bu metindi.
        # Kontrolor once rakamlara bakiyor - ozet satiri, dikkat uyarilari
        # ve pist rüzgârlari ACIK kaliyor, sadece duz anlatim katlaniyor.
        p.append('<details class="kat"><summary>'
                 '🤖 Genel değerlendirme (yapay zekâ özeti — esas kaynak ham rapordur)'
                 '</summary>'
                 f'<div class="yorum">{_yorum_html(yorum)}</div></details>')

    if cozum:
        dikkat = uyarilar(cozum)
        if notlar["ws"]:
            dikkat.insert(0, "Rüzgâr kesmesi: " + ", ".join(notlar["ws"]))
        if dikkat:
            p.append(f'<div class="dikkat"><b>Dikkat</b> · '
                     f'{html.escape(" · ".join(dikkat))}</div>')

        p.append(f'<div class="ozet">{html.escape(ozet_satiri(cozum))}</div>')

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
            p.append(f'<div class="pist-kaynak">✈️ {html.escape(pist_kaynagi)}</div>')

    govde = taf_bicimle(rapor["metin"]) if tip == "TAF" else rapor["metin"]
    p.append(f"<pre>{html.escape(govde)}</pre></div>")
    return "".join(p)


def _saatlik_tahmin_html(satirlar: list) -> str:
    """Önümüzdeki saatlerin MODEL tahmini (Open-Meteo) - TAF DEĞİLDİR.

    Bilinçli olarak yorum/uyarı üretmiyor, sadece ham eğilimi gösteriyor:
    bu veriyle geriye dönük dürüst bir doğrulama yapılamadı (bkz.
    ltfj_dis_kaynak_cache modül açıklaması), dolayısıyla ondan bir karar
    sinyali türetmek sayfanın geri kalanındaki disipline aykırı olurdu.

    Spread (sıcaklık - çiy noktası) başa konuyor: bu projedeki tüm
    tavan/sis çalışmalarında en güçlü öncü gösterge oydu."""
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

    hucreler = []
    for s in satirlar:
        sic, cig = s.get("temperature_2m"), s.get("dew_point_2m")
        spread = None if sic is None or cig is None else sic - cig
        gorus_m = s.get("visibility")
        # Open-Meteo görüşü METRE verir; 10 km ve üstünü METAR'daki gibi
        # "10+" olarak kısaltıyoruz - aradaki her 100 metreyi göstermek
        # olmayan bir hassasiyet ima ederdi.
        if gorus_m is None:
            gorus = "—"
        elif gorus_m >= 10000:
            gorus = "10+ km"
        else:
            gorus = f"{gorus_m / 1000:.1f} km"
        hucreler.append(
            '<div class="tahmin-hucre">'
            f'<div class="tahmin-saat">{html.escape(_yerel_saat(s.get("saat", "")))}</div>'
            f'<div class="tahmin-spread">{_sayi(spread, "°", 1)}</div>'
            f'<div class="tahmin-satir">{html.escape(gorus)}</div>'
            f'<div class="tahmin-satir">{_sayi(s.get("wind_speed_10m"), " km/s")}</div>'
            f'<div class="tahmin-satir">{_sayi(s.get("cloud_cover_low"), "%")}</div>'
            "</div>")

    return (
        '<div class="alt-bolum">'
        '<div class="basrow"><span class="tip">Önümüzdeki saatler</span>'
        '<span class="zaman">Open-Meteo model tahmini</span></div>'
        '<div class="tahmin-uyari">Bu bir <strong>model tahminidir, TAF değildir</strong> — '
        "resmî havacılık tahmini yerine geçmez, operasyonel karar için TAF ve "
        "resmî kaynaklar esastır. Eğilimi görmek için konulmuştur.</div>"
        '<div class="tahmin-serit">' + "".join(hucreler) + "</div>"
        '<div class="tahmin-aciklama">Satırlar: saat (yerel) · '
        "<strong>spread</strong> (sıcaklık − çiy noktası, düştükçe sis riski artar) · "
        "görüş · rüzgâr · düşük bulut oranı.</div>"
        "</div>")


def _beklenti_html(tahmin_html: str, sis_html: str, sis_yuzde: str = "") -> str:
    """"Önümüzdeki saatler" ve "İstatistiksel sis olasılığı" TEK katlanır
    başlık altında - ikisi de "birazdan ne olacak" sorusunu yanıtlıyor,
    ayrı iki kart olarak durmaları sayfayı gereksiz böluyordu.

    Rozet kapalıyken de olasılığı gösterir; bölüm unutulmasın diye."""
    if not tahmin_html and not sis_html:
        return ""
    rozet = (f'<span class="kat-rozet">sis %{html.escape(sis_yuzde)}</span>'
             if sis_yuzde else "")
    return ('<div class="kart"><details class="kat kat-kart">'
            f'<summary>Beklenti · önümüzdeki saatler {rozet}</summary>'
            f"{tahmin_html}{sis_html}"
            "</details></div>")


def sayfa_yaz(raporlar: list, gecmis: list, hedef: Path, yorum_onbellegi: dict | None = None,
              atc_notes_db_url: str = "", push_vapid_public_key: str = "",
              saatlik_tahmin: list | None = None):
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
    govde = (_trend_bolumu(gecmis)
             + ("".join(_kart(r, yorum_onbellegi) for r in sirali)
                or "<div class='kart'>Rapor yok.</div>"))
    icao = raporlar[0].get("icao", "LTFJ") if raporlar else "LTFJ"

    guncel_rapor = next((r for r in sirali if r["tip"] in ("METAR", "SPECI")), None)
    guncel_cozum = metar_coz(guncel_rapor["metin"]) if guncel_rapor else None
    guncel_taf_rapor = next((r for r in sirali if r["tip"] == "TAF"), None)
    taf_tavan = (farkindalik.taf_en_dusuk_tavan_ft(guncel_taf_rapor["metin"])
                 if guncel_taf_rapor else None)

    hedef.write_text(
        SABLON.format(icao=html.escape(icao), govde=govde,
                      guncelleme=f"{simdi:%d.%m.%Y %H:%M} yerel",
                      atc_notes_db_url=json.dumps(atc_notes_db_url or ""),
                      push_vapid_public_key=json.dumps(push_vapid_public_key or ""),
                      lvo_referans_html=_lvo_dokuman_referans_html(),
                      lvo_farkindalik_html=_lvo_farkindalik_html(
                          guncel_cozum, taf_tavan, gecmis, simdi),
                      beklenti_html=_beklenti_html(
                          _saatlik_tahmin_html(saatlik_tahmin or []),
                          _sis_olasiligi_html(guncel_cozum, gecmis, simdi),
                          _sis_olasilik_rozeti(guncel_cozum, gecmis, simdi)),
                      rvr_esikleri_json=json.dumps(lvo.RVR_ESIKLERI, ensure_ascii=False),
                      vfr_html=_vfr_sekmesi_html(guncel_cozum)),
        encoding="utf-8")
    print(f"  web sayfası yazıldı: {hedef.name}")
