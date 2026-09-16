#!/usr/bin/env python3
"""
LTFJ (Sabiha Gokcen) METAR / SPECI / TAF  -  rasat.mgm.gov.tr

Sayfa Next.js. Veri HTML icindeki <script id="__NEXT_DATA__"> etiketinde JSON olarak
geliyor. Biz o JSON'u cekip ayikliyoruz. Ekstra kutuphane yok, sadece requests.

Kurulum:  pip install requests
Calistir: python ltfj_rasat.py
"""

import json
import re
import sys
import time
from datetime import datetime, timezone

import requests

BASE = "https://rasat.mgm.gov.tr/result"
ICAO = "LTFJ"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Referer": "https://rasat.mgm.gov.tr/",
}

# obsType: 1 = METAR/SPECI grubu, 2 = TAF grubu.  hours: 0 = son (anlik) rapor
# Ornek: /result?stations=LTFJ&obsType=1&obsType=2&hours=0
EK_PARAMS = [("obsType", "1"), ("obsType", "2"), ("hours", "0")]

NEXT_DATA = re.compile(
    r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S | re.I
)


def raporlari_cek(icao: str = ICAO, timeout: int = 25) -> list[dict]:
    """
    Istasyonun son raporlarini dondurur. Her eleman:
      {'tip': 'METAR', 'zaman': datetime(UTC), 'metin': 'METAR LTFJ ...'}
    En yeni ilk sirada.
    """
    params = [("stations", icao)] + EK_PARAMS
    r = requests.get(BASE, params=params, headers=HEADERS, timeout=timeout)
    r.raise_for_status()

    m = NEXT_DATA.search(r.text)
    if not m:
        raise RuntimeError("__NEXT_DATA__ bulunamadi - sayfa yapisi degismis olabilir.")

    data = json.loads(m.group(1))

    if "--debug" in sys.argv:
        with open("next_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        pp = data.get("props", {}).get("pageProps", {})
        print("[debug] istenen URL :", r.url)
        print("[debug] pageProps   :", list(pp.keys()))
        print("[debug] query       :", data.get("query"))
        print("[debug] selectedObj :", pp.get("selectedObj"))
        print("[debug] response    :", len(pp.get("response") or []), "kayit")
        print("[debug] next_data.json yazildi\n")

    response = data["props"]["pageProps"].get("response") or []

    out = []
    for blok in response:
        if (blok.get("istInfo") or {}).get("icao", "").upper() != icao.upper():
            continue
        for kayit in (blok.get("dataLast") or []):
            metin = (kayit.get("observationText") or "").strip()
            if not metin:
                continue
            out.append({
                "id": kayit.get("id"),                     # MGM'nin kayit numarasi
                "tip": metin.split()[0].upper(),           # METAR / SPECI / TAF
                "zaman": _zaman(kayit.get("observationTimeNormal")),
                "metin": " ".join(metin.split()),
            })
    out.sort(key=lambda d: d["zaman"] or datetime.min.replace(tzinfo=timezone.utc),
             reverse=True)
    return out


def _zaman(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def taf_bicimle(taf: str) -> str:
    """TAF'i degisim gruplarindan bolerek okunakli yazar."""
    return re.sub(r"\s(?=(FM\d|BECMG|TEMPO|PROB\d))", "\n    ", taf)


def main():
    try:
        raporlar = raporlari_cek()
    except requests.RequestException as e:
        sys.exit(f"Siteye ulasilamadi: {e}")
    except Exception as e:
        sys.exit(f"Ayiklama hatasi: {e}")

    if not raporlar:
        print(f"{ICAO} icin rapor donmedi.")
        return

    for r in raporlar:
        if r["zaman"]:
            yerel = r["zaman"].astimezone()
            damga = f'{r["zaman"]:%d.%m %H:%M}Z  ({yerel:%H:%M} yerel)'
        else:
            damga = "zaman yok"
        print(f'== {r["tip"]} == {damga}')
        print(taf_bicimle(r["metin"]) if r["tip"] == "TAF" else r["metin"])
        print()


if __name__ == "__main__":
    main()