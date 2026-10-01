#!/usr/bin/env python3
"""MGM otomatik istasyonlari: Omerli Baraji cevresinde istasyon var mi,
anlik nem/sicaklik duzenli cekilebiliyor mu? KESIF - SALT OKUNUR.

NEDEN VAR: Omerli tarafindan sabah suruklenen sis 24 pist baslarini
kapatiyor (sis_modeli/README.md "Parcali sis, 24 pist basi ve RVR").
Baraj tarafinin nemini olcen bir istasyon varsa ileriye donuk kaydedip
V3'te aday degisken yapmak istiyoruz. Bu betik yalnizca OLCER:

  1) mgm.gov.tr web sitesinin kullandigi servis uclarindan Istanbul
     istasyon/merkez listesini almayi DENER (uc adi ve alanlar
     VARSAYILMAZ - ne donerse ham olarak kaydedilir, ozetlenir),
  2) koordinati olan kayitlari Omerli merkezine uzakliga gore siralar
     ve LTFJ'den yonunu verir,
  3) en yakin birkac istasyon icin "son durum" ucunu DENER ve donen
     alan adlarini/degerleri basar.

Hicbir kalici veriyi degistirmez: stdout, $GITHUB_STEP_SUMMARY ve
--ham-dizin (Actions'ta gecici dizin, artifact) disina yazmaz.

Calistirma (GitHub Actions, "MGM istasyon keşif" is akisi):
    python mgm_istasyon_kesif.py --ham-dizin "$RUNNER_TEMP/mgm_istasyon"
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

import requests

SERVIS = "https://servis.mgm.gov.tr/web"
BASLIK = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Origin": "https://www.mgm.gov.tr",
    "Referer": "https://www.mgm.gov.tr/",
    "Accept": "application/json, text/plain, */*",
}
# Denenecek liste uclari - HANGISININ calistigi bilinmiyor, olculecek.
LISTE_UCLARI = [
    ("istasyonlar/ilAdDetay", {"il": "İstanbul"}),
    ("merkezler/ililcesi", {"il": "İstanbul"}),
    ("merkezler", {"il": "İstanbul"}),
]
SON_DURUM_UCU = "sondurumlar"
LTFJ = (40.8983, 29.3092)
OMERLI = (41.05, 29.38)       # baraj golunun yaklasik ortasi (kaba; haritada dogrulanmali)
YAKIN_KM = 20
EN_YAKIN_N = 8


def mesafe_km(a, b) -> float:
    """Iki (enlem, boylam) arasi buyuk daire uzakligi."""
    e1, b1, e2, b2 = map(math.radians, (*a, *b))
    h = math.sin((e2 - e1) / 2) ** 2 + math.cos(e1) * math.cos(e2) * math.sin((b2 - b1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def yon_derece(a, b) -> float:
    """a'dan b'ye ilk yon (0 = kuzey, saat yonunde)."""
    e1, b1, e2, b2 = map(math.radians, (*a, *b))
    y = math.sin(b2 - b1) * math.cos(e2)
    x = math.cos(e1) * math.sin(e2) - math.sin(e1) * math.cos(e2) * math.cos(b2 - b1)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def kayitlar(veri) -> list:
    """Yanit liste ya da tek sozluk olabilir; sozluk listesine indir."""
    if isinstance(veri, list):
        return [x for x in veri if isinstance(x, dict)]
    return [veri] if isinstance(veri, dict) else []


def koordinatli(kayit: dict):
    """Koordinat alani adini VARSAYMADAN dener: enlem/boylam, lat/lon vb."""
    for e_ad, b_ad in (("enlem", "boylam"), ("lat", "lon"), ("latitude", "longitude")):
        try:
            return float(kayit[e_ad]), float(kayit[b_ad])
        except (KeyError, TypeError, ValueError):
            continue
    return None


def _get(uc, params, ham_dizin, ad):
    try:
        r = requests.get(f"{SERVIS}/{uc}", params=params, headers=BASLIK, timeout=(10, 30))
    except requests.RequestException as e:
        return {"uc": uc, "hata": f"{e.__class__.__name__}: {e}"}, None
    meta = {"uc": uc, "url": r.url, "http": r.status_code, "bayt": len(r.content),
            "tur": r.headers.get("content-type")}
    if ham_dizin:
        (ham_dizin / f"{ad}.txt").write_bytes(r.content)
    try:
        return meta, r.json()
    except ValueError:
        return meta, None


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--ham-dizin", type=Path)
    s = a.parse_args(argv)
    if s.ham_dizin:
        s.ham_dizin.mkdir(parents=True, exist_ok=True)
    rapor = ["# MGM istasyon keşfi (salt okunur)", ""]

    istasyonlar = []
    for i, (uc, params) in enumerate(LISTE_UCLARI):
        meta, veri = _get(uc, params, s.ham_dizin, f"liste_{i}")
        k = kayitlar(veri)
        alanlar = sorted(k[0].keys()) if k else []
        rapor.append(f"- `{meta.get('url', uc)}` → HTTP {meta.get('http')} · "
                     f"{meta.get('bayt')} bayt · {len(k)} kayıt · hata: {meta.get('hata', '-')}")
        if alanlar:
            rapor.append(f"  - alanlar: `{alanlar}`")
        for x in k:
            koor = koordinatli(x)
            if koor:
                istasyonlar.append((x, koor, uc))

    rapor += ["", f"## Ömerli merkezine (≈{OMERLI}, KABA) {YAKIN_KM} km içindekiler", ""]
    yakin = sorted(((mesafe_km(OMERLI, koor), x, koor, uc) for x, koor, uc in istasyonlar),
                   key=lambda t: t[0])
    yakin = [t for t in yakin if t[0] <= YAKIN_KM]
    gorulen = set()
    for km, x, koor, uc in yakin:
        anahtar = json.dumps(x, sort_keys=True, ensure_ascii=False)
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        ozet = {k: v for k, v in x.items() if not isinstance(v, (list, dict))}
        rapor.append(f"- {km:.1f} km · LTFJ'den {mesafe_km(LTFJ, koor):.1f} km, "
                     f"yön {yon_derece(LTFJ, koor):.0f}° · `{uc}` · `{ozet}`")
    if not yakin:
        rapor.append("- (koordinatlı kayıt bulunamadı ya da hiçbiri yakın değil)")

    rapor += ["", "## Son durum denemesi (en yakın kayıtlar)", ""]
    denenen = 0
    for km, x, koor, uc in yakin:
        istno = next((x[k] for k in ("istNo", "sondurumIstNo", "istno", "merkezId")
                      if x.get(k) not in (None, "")), None)
        if istno is None or denenen >= EN_YAKIN_N:
            continue
        denenen += 1
        meta, veri = _get(SON_DURUM_UCU, {"istno": istno}, s.ham_dizin, f"sondurum_{istno}")
        k = kayitlar(veri)
        rapor.append(f"- istno={istno} ({km:.1f} km) → HTTP {meta.get('http')} · "
                     f"{len(k)} kayıt · hata: {meta.get('hata', '-')}")
        if k:
            rapor.append(f"  - `{ {a: b for a, b in k[0].items() if not isinstance(b, (list, dict))} }`")

    metin = "\n".join(rapor)
    print(metin)
    ozet_yolu = os.environ.get("GITHUB_STEP_SUMMARY")
    if ozet_yolu:
        with open(ozet_yolu, "a", encoding="utf-8") as f:
            f.write(metin + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
