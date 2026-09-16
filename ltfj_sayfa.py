#!/usr/bin/env python3
"""
GitHub Pages icin canli durum sayfasi uretir.

Bot her calistiginda index.html'i yeniden yazar, workflow onu repoya commit eder,
GitHub Pages yayinlar. Ek altyapi yok. Sayfa tek dosya - harici CSS/JS yok.
"""

import html
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ltfj_analiz import metar_coz, ozet_satiri, uyarilar
from ltfj_ayarlar import YEREL_TZ
from ltfj_pist import RENK_SIMGE, havacilik_notlari
from ltfj_rasat import taf_bicimle

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
</style>
</head>
<body>
<div class="sar">
<header>
  <h1>{icao} · İstanbul Sabiha Gökçen</h1>
  <div class="alt">Kaynak: MGM · Son güncelleme {guncelleme}</div>
</header>
{govde}
<footer>
  Bu sayfa otomatik üretilir. Operasyonel kullanım için resmî kaynaklara başvurun.
  Renk rozetleri (BLU/WHT/GRN/YLO/AMB/RED) resmî bir ICAO CAT I/II/III kategorisi
  değil, bu botun kendi durum seviyesidir. "Meteorolojik tercih" bir ATC pist
  ataması değildir.
</footer>
</div>
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


def _kart(rapor: dict) -> str:
    tip = rapor["tip"]
    cozum = metar_coz(rapor["metin"]) if tip in ("METAR", "SPECI") else None
    notlar = (havacilik_notlari(cozum, rapor["metin"], rapor.get("zaman"))
              if cozum else None)

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

    if cozum:
        dikkat = uyarilar(cozum)
        if notlar["ws"]:
            dikkat.insert(0, "Rüzgâr kesmesi: " + ", ".join(notlar["ws"]))
        if dikkat:
            p.append(f'<div class="dikkat"><b>Dikkat</b> · '
                     f'{html.escape(" · ".join(dikkat))}</div>')

        p.append(f'<div class="ozet">{html.escape(ozet_satiri(cozum))}</div>')

        satirlar = []
        pistler = [x for x in notlar["pistler"] if not x.startswith("(")]
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

        p.append('<div><a class="panel-link" href="panel.html">🛫 ATC Panelinde aç →</a></div>')

    govde = taf_bicimle(rapor["metin"]) if tip == "TAF" else rapor["metin"]
    p.append(f"<pre>{html.escape(govde)}</pre></div>")
    return "".join(p)


def sayfa_yaz(raporlar: list, gecmis: list, hedef: Path):
    simdi = datetime.now(timezone.utc).astimezone(YEREL_TZ)
    sira = {"SPECI": 0, "METAR": 1, "TAF": 2}
    sirali = sorted(raporlar, key=lambda r: (sira.get(r["tip"], 9),
                                             -(r["zaman"].timestamp()
                                               if r.get("zaman") else 0)))
    govde = (_trend_bolumu(gecmis)
             + ("".join(_kart(r) for r in sirali) or "<div class='kart'>Rapor yok.</div>"))
    icao = raporlar[0].get("icao", "LTFJ") if raporlar else "LTFJ"

    hedef.write_text(
        SABLON.format(icao=html.escape(icao), govde=govde,
                      guncelleme=f"{simdi:%d.%m.%Y %H:%M} yerel"),
        encoding="utf-8")
    print(f"  web sayfası yazıldı: {hedef.name}")
