#!/usr/bin/env python3
"""QV3 GOLGE MODU: LVO Hazirlik Safhasi'na 3 saat icinde gecis olasiligi.

NE YAPAR: her yeni RUTIN METAR icin dondurulmus QV3 GBM modelinin
(sis_modeli/veri/qv3_donmus.json - holdout 2024-2026'da test edilen model,
bkz. sis_modeli/QV3_RAPOR.md) olasiligini hesaplar ve sonuc belli OLMADAN
lvo_hazirlik_gunlugu.csv'ye ekler.

NE YAPMAZ: sayfaya, panele, Telegram'a, bildirime HICBIR SEY yazmaz. Bot
akisini etkilemez (fail-open). Amac: sis mevsiminde canli tahminleri
gerceklesenle karsilastirip sayfaya alinip alinmayacagina karar vermek.

HEDEF (TL.007 madde 6.2.a): RVR < 800 m VEYA tavan < 200 ft. O an sart
varsa model uygulanmaz (egitim "o an sart yokken" anlarla yapildi), satir
durum=hazirlik_suruyor ile yazilir.

EGITIMLE BIREBIR AYNI GIRDI: bot sis_modeli'ni import etmez (izolasyon),
bu yuzden girdi hesabi ve agac tahmini burada yeniden yazildi; esitlik
tests/test_ltfj_lvo_hazirlik.py'de egitim hattinin (ozellik_cikar ->
hedef.hazirla -> qv3_model.aday_ekle -> qv3_gbm) kendisiyle sinanir.
  - Anlik degerler METAR metninden metar_coz ile (egitimdeki ayristirici).
  - Egilimler (1 sa / 3 sa once) gozlem_arsivi.csv'deki RUTIN METAR'dan,
    tam dakika eslesmesiyle - egitimdeki 30 dakikalik izgara gibi.
  - Yalnizca rutin METAR'lar degerlendirilir: egitim arsivinde SPECI yok.
"""

import argparse
import csv
import json
import math
import re
import sys
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ltfj_analiz import metar_coz

KLASOR = Path(__file__).resolve().parent.parent   # repo koku (modul bot/ altinda)
MODEL_DOSYASI = KLASOR / "sis_modeli" / "veri" / "qv3_donmus.json"
ARSIV_DOSYASI = KLASOR / "gozlem_arsivi.csv"
DOSYA_ADI = "lvo_hazirlik_gunlugu.csv"
VARSAYILAN_DOSYA = KLASOR / DOSYA_ADI

RVR_ESIK_M = 800
TAVAN_ESIK_FT = 200
RVR_YOK_M = 2000          # sis_modeli/qv3_model.py ile AYNI
TAVAN_YOK_FT = 20000

SUTUNLAR = ("gozlem_zaman", "kayit_zamani", "durum", "olasilik", "ham",
            "gorus", "rvr_min", "tavan", "spread", "eksik_girdi", "model")

_RVR = re.compile(r"(?<![A-Z0-9])R(\d{2})([LRC]?)/([PM]?)(\d{4})\S*")
_SON = re.compile(r"\s(RMK|BECMG|TEMPO|NOSIG)\b")
_PARCALI = re.compile(r"(BC|PR|MI|VC)FG")
_YAGIS = re.compile(r"(RA|DZ|SN|SG|PL|GR|GS|UP)")


# ---------------------------------------------------------------- girdi ---
def rvr_cikar(metin: str) -> dict:
    """sis_modeli/veri_cek_rvr.rvr_cikar ile ayni: gozlem kismindaki RVR
    gruplari, uc bazinda en dusuk (M/P onekinde sayi)."""
    uclar = {}
    for m in _RVR.finditer(_SON.split(metin)[0]):
        uc, deger = m.group(1), int(m.group(4))
        uclar[uc] = min(deger, uclar.get(uc, deger))
    return {"rvr_06": uclar.get("06"), "rvr_24": uclar.get("24"),
            "rvr_min": min(uclar.values()) if uclar else None}


def _sayi(v):
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def _gecmis_dizini(arsiv: list) -> dict:
    """{zaman: (gorus, spread, ruzgar_hiz, qnh)} - yalnizca rutin METAR ve
    egitimdeki gibi sicaklik/cig/gorus tam olanlar (ozellik_cikar eksik
    olani hic satir yapmiyordu)."""
    dizin = {}
    for s in arsiv:
        if s.get("tip") != "METAR":
            continue
        z = _zaman(s.get("zaman"))
        sic, cig, gor = _sayi(s.get("sicaklik")), _sayi(s.get("cig_noktasi")), _sayi(s.get("gorus"))
        if z is None or sic is None or cig is None or gor is None:
            continue
        dizin[z] = {"gorus": gor, "spread": sic - cig,
                    "ruzgar_hiz": _sayi(s.get("ruzgar_hiz")), "qnh": _sayi(s.get("qnh"))}
    return dizin


def _zaman(v) -> datetime | None:
    if isinstance(v, datetime):
        z = v
    else:
        try:
            z = datetime.fromisoformat(str(v))
        except (TypeError, ValueError):
            return None
    z = z if z.tzinfo else z.replace(tzinfo=timezone.utc)
    return z.astimezone(timezone.utc).replace(second=0, microsecond=0)


def ozellikler(metin: str, zaman: datetime, arsiv: list) -> dict | None:
    """Egitimdeki satirin aynisi: ozellik_cikar + hedef.hazirla egilimleri +
    qv3_model.aday_ekle. sicaklik/cig/gorus eksikse None (egitimde de satir
    yoktu)."""
    d = metar_coz(metin)
    sic, cig, gorus = d.get("sicaklik"), d.get("cig_noktasi"), d.get("gorus")
    if sic is None or cig is None or gorus is None:
        return None
    z = _zaman(zaman)
    gecmis = _gecmis_dizini(arsiv)
    yon, hiz, qnh = d.get("ruzgar_yon"), d.get("ruzgar_hiz"), d.get("qnh")
    spread = sic - cig
    simdi = {"gorus": gorus, "spread": spread, "ruzgar_hiz": hiz, "qnh": qnh}

    def egilim(saat, alan):
        o = gecmis.get(z - timedelta(hours=saat))
        if o is None or o[alan] is None or simdi[alan] is None:
            return None
        return simdi[alan] - o[alan]

    hava = list(d.get("hava") or [])
    rvr = rvr_cikar(metin)
    tavan = d.get("tavan")
    kd = None if yon is None or hiz is None else int(3 <= hiz <= 10 and (0 <= yon <= 60 or yon == 360))
    r = {
        "gorus": gorus, "gorus_egilim_1": egilim(1, "gorus"),
        "rvr_min": rvr["rvr_min"], "tavan": tavan,
        "rvr_min_d": RVR_YOK_M if rvr["rvr_min"] is None else rvr["rvr_min"],
        "rvr_24_d": RVR_YOK_M if rvr["rvr_24"] is None else rvr["rvr_24"],
        "rvr_06_d": RVR_YOK_M if rvr["rvr_06"] is None else rvr["rvr_06"],
        "tavan_d": TAVAN_YOK_FT if tavan is None else tavan,
        "spread": spread, "spread_egilim_1": egilim(1, "spread"),
        "spread_egilim_3": egilim(3, "spread"), "sicaklik": sic,
        "ruzgar_hiz": hiz,
        "ruzgar_kuzey": None if yon is None or hiz is None else hiz * math.cos(math.radians(yon)),
        "ruzgar_dogu": None if yon is None or hiz is None else hiz * math.sin(math.radians(yon)),
        "ruzgar_egilim_1": egilim(1, "ruzgar_hiz"), "qnh_egilim_3": egilim(3, "qnh"),
        "saat": z.hour, "ay": z.month,
        "parcali_sis": int(any(_PARCALI.search(k) for k in hava)),
        "br": int(any(k.lstrip("+-") == "BR" for k in hava)),
        "yagis": int(any(_YAGIS.search(k) for k in hava)),
        "kd_hafif": kd,
        "kd_nemli": None if kd is None else int(kd == 1 and spread <= 1),
    }
    return r


def hazirlik_mi(rvr_min, tavan) -> bool:
    return ((rvr_min is not None and rvr_min < RVR_ESIK_M)
            or (tavan is not None and tavan < TAVAN_ESIK_FT))


# --------------------------------------------------------------- model ---
def model_oku(yol: Path = MODEL_DOSYASI) -> dict:
    """Dondurulmus dosyanin yalnizca GBM bolumu."""
    return json.loads(Path(yol).read_text(encoding="utf-8"))["gbm"]


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


def _kova(deger, esikler) -> int:
    return 0 if deger is None else 1 + bisect_right(esikler, deger)


def olasilik(gbm: dict, ozellik: dict) -> tuple:
    """(kalibre, ham) - qv3_gbm.olasilik + platt_uygula ile ayni."""
    m = gbm["model"]
    kv = [_kova(ozellik.get(a), m["sinirlar"][a]) for a in m["alanlar"]]
    f = m["f0"]
    for agac in m["agaclar"]:
        while "alan" in agac:
            agac = agac["sol"] if kv[agac["alan"]] <= agac["kova"] else agac["sag"]
        f += agac["deger"]
    ham = _sigmoid(f)
    p = min(max(ham, 1e-6), 1 - 1e-6)
    a, b = gbm["platt"]
    return _sigmoid(a * math.log(p / (1 - p)) + b), ham


def model_etiketi(gbm: dict) -> str:
    return f"qv3-gbm-{gbm['agac']}agac-platt{gbm['platt'][0]:.3f}/{gbm['platt'][1]:+.3f}"


# --------------------------------------------------------------- gunluk ---
def tahmin(rapor: dict, arsiv: list, gbm: dict) -> dict | None:
    """Rutin METAR icin gunluk satiri; uygulanamazsa None."""
    if rapor.get("tip") != "METAR" or not rapor.get("zaman"):
        return None
    z = _zaman(rapor["zaman"])
    o = ozellikler(rapor["metin"], z, arsiv)
    if o is None:
        return None
    satir = {"gozlem_zaman": z.isoformat(), "gorus": o["gorus"],
             "rvr_min": "" if o["rvr_min"] is None else o["rvr_min"],
             "tavan": "" if o["tavan"] is None else o["tavan"],
             "spread": o["spread"], "model": model_etiketi(gbm),
             "eksik_girdi": sum(1 for a in gbm["model"]["alanlar"] if o.get(a) is None)}
    if hazirlik_mi(o["rvr_min"], o["tavan"]):
        return {**satir, "durum": "hazirlik_suruyor", "olasilik": "", "ham": ""}
    p, ham = olasilik(gbm, o)
    return {**satir, "durum": "onset", "olasilik": f"{p:.6f}", "ham": f"{ham:.6f}"}


def oku(dosya: Path = VARSAYILAN_DOSYA) -> list[dict]:
    dosya = Path(dosya)
    if not dosya.exists():
        return []
    with dosya.open("r", encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def yaz(satirlar: list, dosya: Path = VARSAYILAN_DOSYA) -> None:
    with Path(dosya).open("w", encoding="utf-8", newline="") as f:
        y = csv.DictWriter(f, fieldnames=SUTUNLAR, extrasaction="ignore")
        y.writeheader()
        for s in sorted(satirlar, key=lambda s: s.get("gozlem_zaman") or ""):
            y.writerow({k: ("" if s.get(k) is None else s.get(k)) for k in SUTUNLAR})


def kaydet(satir: dict | None, dosya: Path = VARSAYILAN_DOSYA,
           simdi: datetime | None = None) -> bool:
    """EKLEME-YALNIZCA: ayni gozlem zaten varsa dokunmaz (ilk kayit kalir)."""
    if not satir:
        return False
    mevcut = oku(dosya)
    if any(s.get("gozlem_zaman") == satir["gozlem_zaman"] for s in mevcut):
        return False
    simdi = simdi or datetime.now(timezone.utc)
    mevcut.append({**satir, "kayit_zamani": simdi.astimezone(timezone.utc).isoformat(timespec="seconds")})
    yaz(mevcut, dosya)
    return True


def kosu(raporlar: list, klasor: Path = KLASOR) -> dict | None:
    """Bot cagrisi: en yeni rutin METAR'i degerlendirip kaydeder. Kaydedilen
    satiri (ya da None) dondurur. Hata yukari iletilir; bot fail-open sarar."""
    metarlar = [r for r in raporlar if r.get("tip") == "METAR" and r.get("zaman")]
    if not metarlar:
        return None
    rapor = max(metarlar, key=lambda r: r["zaman"])
    import ltfj_gozlem_arsivi
    arsiv = ltfj_gozlem_arsivi.oku(Path(klasor) / "gozlem_arsivi.csv")
    satir = tahmin(rapor, arsiv, model_oku(Path(klasor) / "sis_modeli" / "veri" / "qv3_donmus.json"))
    return satir if kaydet(satir, Path(klasor) / DOSYA_ADI) else None


def birlestir(a: list, b: list) -> list:
    """Ayni gozlemde ONCE KAYDEDILEN kalir (simetrik, idempotent)."""
    secilen = {}
    for s in list(a) + list(b):
        k, eski = s.get("gozlem_zaman"), secilen.get(s.get("gozlem_zaman"))
        if eski is None or (s.get("kayit_zamani") or "", tuple(str(s.get(c) or "") for c in SUTUNLAR)) < \
                (eski.get("kayit_zamani") or "", tuple(str(eski.get(c) or "") for c in SUTUNLAR)):
            secilen[k] = s
    return list(secilen.values())


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--dosya", default=str(VARSAYILAN_DOSYA))
    a.add_argument("--birlestir-bizim", metavar="DOSYA",
                   help="push cakismasi: bizim gunlugu diskteki ile birlestir")
    s = a.parse_args(argv)
    if s.birlestir_bizim:
        sonuc = birlestir(oku(Path(s.dosya)), oku(Path(s.birlestir_bizim)))
        yaz(sonuc, Path(s.dosya))
        print(f"LVO hazırlık günlüğü birleştirildi: {len(sonuc)} satır")
    return 0


if __name__ == "__main__":
    sys.exit(main())
