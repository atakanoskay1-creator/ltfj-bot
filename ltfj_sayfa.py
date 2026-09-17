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
  header {{ margin-bottom:20px; }}
  h1 {{ font-size:1.5rem; margin:0 0 4px; letter-spacing:-.02em; }}
  .alt {{ color:var(--soluk); font-size:.875rem; }}
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
  .grafik {{ width:100%; height:64px; display:block; }}
  .grafik-eksen {{ display:flex; justify-content:space-between;
                    font-size:.72rem; color:var(--soluk); margin-top:2px; }}

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
    flex:1 1 140px; padding:8px 10px; border-radius:8px; border:1px solid var(--cizgi);
    background:var(--bg); color:var(--metin); font-size:.85rem;
  }}
  .notam-arama button {{
    padding:8px 14px; border-radius:8px; border:none; background:var(--vurgu);
    color:var(--bg); font-weight:650; font-size:.85rem; cursor:pointer;
  }}
  .notam-arama-not {{ color:var(--soluk); font-size:.78rem; margin:-8px 0 12px; }}

  .atc-not-ekle-btn {{
    margin-left:auto; padding:6px 12px; border-radius:8px; border:none;
    background:var(--vurgu); color:var(--bg); font-weight:650; font-size:.82rem;
    cursor:pointer;
  }}
  .atc-not-kalan {{ color:var(--soluk); font-size:.72rem; margin-top:6px; }}
  .modal-ortu {{
    position:fixed; inset:0; background:rgba(0,0,0,.55); display:flex;
    align-items:center; justify-content:center; padding:16px; z-index:50;
  }}
  .modal-ortu[hidden] {{ display:none; }}
  .modal-kutu {{
    background:var(--kart); border:1px solid var(--cizgi); border-radius:14px;
    padding:20px; max-width:420px; width:100%;
  }}
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
</style>
</head>
<body>
<div class="sar">
<header>
  <h1>{icao} · İstanbul Sabiha Gökçen</h1>
  <div class="alt">Kaynak: MGM/METAR · Son güncelleme {guncelleme}</div>
</header>
{govde}

<div class="bolum-baslik">NOTAM — Bilgi Amaçlı</div>
<div class="notam-uyari">
  ⚠️ Bilgi amaçlıdır. Operasyon öncesi güncel resmî NOTAM/PIB kontrol edilmelidir.
  Kaynak: NOTAC (FAA NOTAM Management System tabanlı üçüncü taraf servis) —
  resmî bir Türk/EUROCONTROL NOTAM kaynağı değildir. Bu bölüm hiçbir operasyonel
  öneri üretmez; aşağıdaki meteorolojik analiz bu veriden bağımsızdır.
</div>

<div class="kart">
  <div class="basrow"><span class="tip">Aktif NOTAM'lar</span>
    <span class="zaman" id="notam-senkron-zamani"></span></div>
  <div id="notam-aktif-liste"><div class="notam-bos">Yükleniyor…</div></div>
</div>

<div class="kart">
  <div class="basrow"><span class="tip">NOTAM Geçmişi / Arama</span></div>
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
    </select>
    <button type="button" id="notam-ara-btn">Ara</button>
  </div>
  <div id="notam-arama-sonuc"><div class="notam-bos">Yükleniyor…</div></div>
</div>

<div class="bolum-baslik">ATC Notes — Durumsal Farkındalık</div>
<div class="notam-uyari">
  ⚠️ Bu bölüm ATC tarafından paylaşılan geçici durumsal farkındalık notlarıdır.
  Resmî NOTAM veya operasyonel talimat değildir; NOTAM/METAR/pist analiziyle
  hiçbir bağlantısı yoktur. Kimlik doğrulaması yapılmaz — isim yazan kişi
  tarafından girilir. Her not oluşturulduktan tam 48 saat sonra otomatik
  olarak silinir.
</div>

<div class="kart">
  <div class="basrow"><span class="tip">ATC Notes</span>
    <button type="button" id="atc-not-ekle-btn" class="atc-not-ekle-btn">+ NOT EKLE</button></div>
  <div id="atc-notes-liste"><div class="notam-bos">Yükleniyor…</div></div>
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
<footer>
  Bu sayfa otomatik üretilir. Operasyonel kullanım için resmî kaynaklara başvurun.
  Renk rozetleri (BLU/WHT/GRN/YLO/AMB/RED) resmî bir ICAO CAT I/II/III kategorisi
  değil, bu botun kendi durum seviyesidir. "Meteorolojik tercih" bir ATC pist
  ataması değildir. NOTAM bölümü NOTAC kaynaklıdır, resmî NOTAM/PIB'in yerine
  geçmez. ATC Notes bölümü kimlik doğrulaması olmayan, paylaşımlı ve geçici
  (48 saat) bir not panosudur; resmî bir bilgi kaynağı değildir.
</footer>
</div>
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
  var senkronEl = document.getElementById("notam-senkron-zamani");
  var sonucEl = document.getElementById("notam-arama-sonuc");
  var durumSelectEl = document.getElementById("notam-durum");

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
    return (
      '<div class="notam-kart">' +
      '<div class="notam-ust"><span class="notam-no">' + esc(n.number || "—") + "</span>" +
      kategori + etiketler + pistler +
      '<span class="notam-durum">' + esc(n.status || "") + "</span></div>" +
      ozet +
      "<details><summary style=\\"cursor:pointer; font-size:.82rem; color:var(--soluk);\\">Ham NOTAM metni</summary>" +
      '<div class="notam-metin">' + esc(n.text || "") + "</div></details>" +
      '<div class="notam-kaynak">Kaynak: NOTAC · geçerlilik: ' +
      esc(n.effective_start || "—") + " → " + esc(n.effective_end || "—") + "</div>" +
      "</div>"
    );
  }}

  function aktifGoster() {{
    if (!veri) return;
    senkronEl.textContent = veri.son_senkron
      ? "son senkron " + veri.son_senkron.replace("T", " ").slice(0, 16)
      : "henüz senkronize edilmedi";
    if (!veri.son_senkron) {{
      aktifEl.innerHTML = '<div class="notam-bos">NOTAM verisi şu anda alınamıyor.</div>';
    }} else if (!veri.aktif.length) {{
      aktifEl.innerHTML = '<div class="notam-bos">Aktif NOTAM bulunmuyor.</div>';
    }} else {{
      aktifEl.innerHTML = veri.aktif.map(notamKarti).join("");
    }}
  }}

  function durumSecenekleriDoldur() {{
    var gorulen = {{}};
    (veri.gecmis || []).forEach(function (n) {{ if (n.status) gorulen[n.status] = true; }});
    Object.keys(gorulen).sort().forEach(function (d) {{
      var o = document.createElement("option");
      o.value = d; o.textContent = d;
      durumSelectEl.appendChild(o);
    }});
  }}

  function aramaCalistir() {{
    if (!veri) return;
    var q = document.getElementById("notam-q").value.trim().toLowerCase();
    var ts = document.getElementById("notam-tarih-baslangic").value;
    var te = document.getElementById("notam-tarih-bitis").value;
    var durum = durumSelectEl.value;

    var sonuclar = (veri.gecmis || []).filter(function (n) {{
      if (durum && n.status !== durum) return false;
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
        aktifGoster();
        durumSecenekleriDoldur();
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

  document.getElementById("notam-ara-btn").addEventListener("click", aramaCalistir);
  document.getElementById("notam-q").addEventListener("keydown", function (e) {{
    if (e.key === "Enter") aramaCalistir();
  }});
  veriYukle();
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

  document.getElementById("atc-not-ekle-btn").addEventListener("click", modalAc);
  document.getElementById("atc-not-iptal").addEventListener("click", modalKapat);
  kaydetBtn.addEventListener("click", notKaydet);
  modalEl.addEventListener("click", function (e) {{ if (e.target === modalEl) modalKapat(); }});

  veriYukle();
  setInterval(veriYukle, POLL_ARALIGI_MS);
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


def _svg_cizgi(noktalar: list, renk: str, genislik=600, yukseklik=64) -> str | None:
    if len(noktalar) < 2:
        return None
    degerler = [v for _, v in noktalar]
    v_min, v_max = min(degerler), max(degerler)
    if v_min == v_max:
        v_min, v_max = v_min - 1, v_max + 1
    pad = (v_max - v_min) * 0.15
    v_min, v_max = v_min - pad, v_max + pad

    t0, t1 = noktalar[0][0], noktalar[-1][0]
    t_araligi = (t1 - t0).total_seconds() or 1

    def x(z):
        return 4 + (genislik - 8) * ((z - t0).total_seconds() / t_araligi)

    def y(v):
        return yukseklik - 4 - (yukseklik - 8) * ((v - v_min) / (v_max - v_min))

    yol = " ".join(f'{"M" if i == 0 else "L"}{x(z):.1f},{y(v):.1f}'
                    for i, (z, v) in enumerate(noktalar))
    son_x, son_y = x(noktalar[-1][0]), y(noktalar[-1][1])

    return (f'<svg viewBox="0 0 {genislik} {yukseklik}" class="grafik" '
            f'preserveAspectRatio="none">'
            f'<path d="{yol}" fill="none" stroke="{renk}" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="{son_x:.1f}" cy="{son_y:.1f}" r="3" fill="{renk}"/>'
            f'</svg>')


def _grafik_blogu(alan: str, baslik: str, birim: str, renk: str,
                   gecmis: list, simdi: datetime) -> str:
    noktalar = _grafik_verisi(gecmis, alan, simdi)
    svg = _svg_cizgi(noktalar, renk)
    if not svg:
        return ""
    son_deger = noktalar[-1][1]
    baslangic = noktalar[0][0].astimezone(YEREL_TZ)
    bitis = noktalar[-1][0].astimezone(YEREL_TZ)
    return (
        f'<div><div class="grafik-baslik"><span>{html.escape(baslik)}</span>'
        f'<span class="grafik-son">{son_deger:.0f} {html.escape(birim)}</span></div>'
        f'{svg}'
        f'<div class="grafik-eksen"><span>{baslangic:%H:%M}</span>'
        f'<span>{bitis:%H:%M}</span></div></div>'
    )


def _trend_bolumu(gecmis: list) -> str:
    if not gecmis:
        return ""
    simdi = datetime.now(timezone.utc)
    bloklar = [_grafik_blogu(alan, baslik, birim, renk, gecmis, simdi)
               for alan, baslik, birim, renk in GRAFIKLER]
    bloklar = [b for b in bloklar if b]
    if not bloklar:
        return ""
    return (f'<div class="kart"><div class="grafik-ust">Trend</div>'
            f'<div class="grafik-grid">{"".join(bloklar)}</div></div>')


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
        p.append('<div class="yorum"><div class="yorum-etiket">'
                  '🤖 Genel değerlendirme (yapay zekâ özeti — esas kaynak ham rapordur)</div>'
                  f'{_yorum_html(yorum)}</div>')

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
        if notlar["sis"]:
            satirlar.append(("Sis riski", notlar["sis"].split(":", 1)[-1].strip()))
        for g in notlar["gorus_op"]:
            satirlar.append(("Görüş operasyonu", g))

        if satirlar:
            p.append("<table>" + "".join(
                f"<tr><td>{html.escape(a)}</td><td>{html.escape(b)}</td></tr>"
                for a, b in satirlar) + "</table>")
        if pist_kaynagi:
            p.append(f'<div class="pist-kaynak">✈️ {html.escape(pist_kaynagi)}</div>')

        p.append('<div><a class="panel-link" href="panel.html">🛫 ATC Panelinde aç →</a></div>')

    govde = taf_bicimle(rapor["metin"]) if tip == "TAF" else rapor["metin"]
    p.append(f"<pre>{html.escape(govde)}</pre></div>")
    return "".join(p)


def sayfa_yaz(raporlar: list, gecmis: list, hedef: Path, yorum_onbellegi: dict | None = None,
              atc_notes_db_url: str = ""):
    """yorum_onbellegi: state["yorum_onbellegi"] (ham rapor metni -> Claude
    yorumu/cevirisi) - Telegram ile PAYLASILAN onbellek, burada okunur,
    YENIDEN hesaplanmaz. Verilmezse (ornegin eski cagiran kod) kartlar
    sadece deterministik (Claude'suz) bilgiyi gosterir - hicbir sekilde
    hata vermez.

    atc_notes_db_url: ayarlar.json::atc_notes.database_url - Firebase'in
    KENDI tasarimi geregi GIZLI DEGIL (bkz. ltfj_ayarlar.py), sayfa
    icine oldugu gibi gomulur. Bos ise ATC Notes bolumu "yapilandirilmamis"
    mesaji gosterir."""
    simdi = datetime.now(timezone.utc).astimezone(YEREL_TZ)
    sira = {"SPECI": 0, "METAR": 1, "TAF": 2}
    sirali = sorted(raporlar, key=lambda r: (sira.get(r["tip"], 9),
                                             -(r["zaman"].timestamp()
                                               if r.get("zaman") else 0)))
    govde = (_trend_bolumu(gecmis)
             + ("".join(_kart(r, yorum_onbellegi) for r in sirali)
                or "<div class='kart'>Rapor yok.</div>"))
    icao = raporlar[0].get("icao", "LTFJ") if raporlar else "LTFJ"

    hedef.write_text(
        SABLON.format(icao=html.escape(icao), govde=govde,
                      guncelleme=f"{simdi:%d.%m.%Y %H:%M} yerel",
                      atc_notes_db_url=json.dumps(atc_notes_db_url or "")),
        encoding="utf-8")
    print(f"  web sayfası yazıldı: {hedef.name}")
