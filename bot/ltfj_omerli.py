#!/usr/bin/env python3
"""Omerli tarafi MGM otomatik istasyonlari - ILERIYE DONUK, ekleme-yalnizca kayit.

NEDEN VAR: meydanin kuzeyindeki Omerli Baraji'ndan sabah suruklenen sis
24 pist baslarini kapatiyor (sis_modeli/README.md "Parcali sis, 24 pist
basi ve RVR" ve "Omerli'den nem tasinmasi"). Baraj tarafinin nemi icin
MGM'de iki istasyon var (mgm_istasyon_kesif, PR #133 ile olculdu):

  18736  PENDIK/OMERLI BARAJI  LTFJ'den 12.5 km, yon 13°  sicaklik, nem
  18397  CEKMEKOY/OMERLI       LTFJ'den 20.1 km, yon 4°   + ruzgar, basinc

MGM'nin `sondurumlar` ucu YALNIZCA anlik degeri veriyor, arsivi yok. Bu
yuzden bot her kosuda bu degeri omerli_gozlem.csv'ye ekler; bir sis
mevsimi biriktikten sonra V3'te aday degisken olarak denenir. Bot ve
model bu dosyayi OKUMAZ - yalnizca birikir (izleme doneminde model
degismez).

KURALLAR
  - Anahtar (10 dakikalik dilim, ist_no): ayni dilimde ILK yakalanan kalir,
    sonraki kosular satiri DEGISTIRMEZ (gozlem arsivi/tahmin gunlugu ile
    ayni kural). Bot ~4 dakikada bir calistigi icin dilim basina en fazla
    bir satir: 2 istasyon x 144 = gunde ~290 satir, yilda ~8 MB duz metin.
  - MGM'nin -9999 "veri yok" degeri bos yazilir. Cig noktasi MGM'den
    gelmiyor; sicaklik + bagil nemden (Magnus) hesaplanir.
  - veriZamani simdiden BAYAT_DK'dan eskiyse istasyon donmus sayilir,
    kaydedilmez.
  - FAIL-OPEN: ag/ayristirma hatasi stderr'e yazilir, cikis kodu 0; bot
    akisi hicbir kosulda etkilenmez (is akisinda ayrica
    continue-on-error).

Kullanim (repo kokunden):
    python bot/ltfj_omerli.py                          # cek + ekle
    python bot/ltfj_omerli.py --birlestir-bizim DOSYA  # push cakismasi
"""

import argparse
import csv
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

SERVIS = "https://servis.mgm.gov.tr/web/sondurumlar"
BASLIK = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Origin": "https://www.mgm.gov.tr",
    "Referer": "https://www.mgm.gov.tr/",
    "Accept": "application/json, text/plain, */*",
}
ISTASYONLAR = {18736: "PENDIK/OMERLI BARAJI", 18397: "CEKMEKOY/OMERLI"}
VARSAYILAN_DOSYA = Path("omerli_gozlem.csv")
SUTUNLAR = ["zaman", "ist_no", "sicaklik", "nem", "ciy", "ruzgar_yon",
            "ruzgar_hiz_kmh", "basinc", "kayit_zamani"]
DILIM_DK = 10
BAYAT_DK = 90
ZAMAN_ASIMI_SN = 8
YOK = -9999


def _deger(v):
    """MGM sayisi; -9999 / bos / sayi-olmayan -> None."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f <= YOK or math.isnan(f) else f


def ciy_noktasi(sicaklik, nem):
    """Magnus (a=17.62, b=243.12 C); girdi eksikse None."""
    if sicaklik is None or nem is None or not 0 < nem <= 100:
        return None
    g = math.log(nem / 100) + 17.62 * sicaklik / (243.12 + sicaklik)
    return round(243.12 * g / (17.62 - g), 1)


def _dt(s):
    try:
        z = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return z if z.tzinfo else z.replace(tzinfo=timezone.utc)


def dilim(z: datetime) -> str:
    """UTC, 10 dakikaya asagi yuvarlanmis 'YYYY-MM-DDTHH:MM'."""
    z = z.astimezone(timezone.utc)
    return z.replace(minute=z.minute - z.minute % DILIM_DK, second=0,
                     microsecond=0).strftime("%Y-%m-%dT%H:%M")


def satir_kur(kayit: dict, simdi: datetime) -> dict | None:
    """sondurumlar kaydindan CSV satiri; zaman yok/bayatsa None."""
    z = _dt(kayit.get("veriZamani"))
    if z is None or simdi - z > timedelta(minutes=BAYAT_DK):
        return None
    sicaklik, nem = _deger(kayit.get("sicaklik")), _deger(kayit.get("nem"))
    if sicaklik is None and nem is None:
        return None
    hiz, basinc = _deger(kayit.get("ruzgarHiz")), _deger(kayit.get("aktuelBasinc"))
    yon = _deger(kayit.get("ruzgarYon"))
    return {
        "zaman": dilim(z), "ist_no": str(kayit.get("istNo")),
        "sicaklik": sicaklik, "nem": nem, "ciy": ciy_noktasi(sicaklik, nem),
        "ruzgar_yon": None if yon is None else int(round(yon)),
        "ruzgar_hiz_kmh": None if hiz is None else round(hiz, 1),
        "basinc": basinc,
        "kayit_zamani": simdi.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _anahtar(s: dict) -> tuple:
    return (s.get("zaman"), str(s.get("ist_no")))


def oku(dosya: Path = VARSAYILAN_DOSYA) -> list[dict]:
    dosya = Path(dosya)
    if not dosya.exists():
        return []
    with dosya.open("r", encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def yaz(satirlar: list, dosya: Path = VARSAYILAN_DOSYA) -> None:
    sirali = sorted(satirlar, key=lambda s: (s.get("zaman") or "", str(s.get("ist_no"))))
    with Path(dosya).open("w", encoding="utf-8", newline="") as f:
        y = csv.DictWriter(f, fieldnames=SUTUNLAR, extrasaction="ignore")
        y.writeheader()
        for s in sirali:
            y.writerow({k: ("" if s.get(k) is None else s.get(k)) for k in SUTUNLAR})


def birlestir(a: list, b: list) -> list:
    """Ayni anahtarda ONCE KAYDEDILEN kalir (simetrik, idempotent)."""
    secilen = {}
    for s in list(a) + list(b):
        k, eski = _anahtar(s), secilen.get(_anahtar(s))
        if eski is None or (s.get("kayit_zamani") or "", tuple(str(s.get(c) or "") for c in SUTUNLAR)) < \
                (eski.get("kayit_zamani") or "", tuple(str(eski.get(c) or "") for c in SUTUNLAR)):
            secilen[k] = s
    return list(secilen.values())


def ekle(yeni: list, dosya: Path = VARSAYILAN_DOSYA) -> int:
    """Yeni satirlari ekler; zaten olan anahtara DOKUNMAZ. Eklenen sayi."""
    mevcut = oku(dosya)
    var = {_anahtar(s) for s in mevcut}
    eklenecek = [s for s in yeni if _anahtar(s) not in var]
    if eklenecek:
        yaz(mevcut + eklenecek, dosya)
    return len(eklenecek)


def cek(ist_no: int, oturum=requests) -> dict | None:
    r = oturum.get(SERVIS, params={"istno": ist_no}, headers=BASLIK, timeout=ZAMAN_ASIMI_SN)
    r.raise_for_status()
    veri = r.json()
    if isinstance(veri, list):
        veri = veri[0] if veri else None
    return veri if isinstance(veri, dict) else None


def kosu(dosya: Path = VARSAYILAN_DOSYA, simdi: datetime | None = None, oturum=requests) -> int:
    """Her istasyonu ayri dener; biri dusse digeri yine kaydedilir."""
    simdi = simdi or datetime.now(timezone.utc)
    satirlar = []
    for ist_no, ad in ISTASYONLAR.items():
        try:
            kayit = cek(ist_no, oturum)
            satir = satir_kur(kayit, simdi) if kayit else None
        except Exception as e:  # fail-open: bot akisi etkilenmez
            print(f"[uyarı] Ömerli {ist_no} ({ad}) alınamadı: {type(e).__name__}: {e}",
                  file=sys.stderr)
            continue
        if satir is None:
            print(f"[uyarı] Ömerli {ist_no} ({ad}): veri yok ya da bayat", file=sys.stderr)
            continue
        satirlar.append(satir)
    n = ekle(satirlar, dosya) if satirlar else 0
    print(f"Ömerli kaydı: {len(satirlar)} istasyon okundu, {n} yeni satır")
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dosya", default=str(VARSAYILAN_DOSYA))
    ap.add_argument("--birlestir-bizim", metavar="DOSYA",
                    help="push cakismasi: bizim kaydi diskteki ile birlestir")
    a = ap.parse_args(argv)
    try:
        if a.birlestir_bizim:
            sonuc = birlestir(oku(Path(a.dosya)), oku(Path(a.birlestir_bizim)))
            yaz(sonuc, Path(a.dosya))
            print(f"Ömerli kaydı birleştirildi: {len(sonuc)} satır")
        else:
            kosu(Path(a.dosya))
    except Exception as e:  # fail-open
        print(f"[uyarı] Ömerli kaydı atlandı: {type(e).__name__}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
