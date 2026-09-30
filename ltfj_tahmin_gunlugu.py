#!/usr/bin/env python3
"""V1 (Model A) ILERIYE DONUK DOGRULAMA: tahmin gunlugu + eslestirici.

SORU: sayfadaki "Dusuk gorus (< 1000 m) olasiligi" (ltfj_sis_olasilik,
Model A) gercekte ne kadar tuttu? Holdout (2024-2026) sonucu gecmis
veride olculdu; bu modul AYNI modeli CANLI kullanimda, sonuc belli
OLMADAN ONCE kaydedilen tahminlerle olcer.

UC PARCA (sayfaya BASILMAZ - kullanici istedi: "ayri bir dosyada
tutulmasi yeterli, sonradan acip bakmak icin")
  1) GUNLUK (tahmin_gunlugu.csv) - EKLEME-YALNIZCA. Her yeni gozlem icin
     sayfada gosterilen olasilik, girdileriyle birlikte, sonuc
     bilinmeden yazilir. Anahtar (gozlem_zaman, gozlem_tip); ayni
     gozlemin ilk kaydi kalir (gozlem arsivindeki kuralin aynisi) - bot
     ayni gozlemi sonraki kosularda tekrar gorse de satir DEGISMEZ.
  2) ESLESTIRICI (sonuclandir) - gunlugu gozlem arsiviyle
     (gozlem_arsivi.csv) karsilastirir.
  3) OKUMA DOSYASI (tahmin_dogrulama.csv) - her kosuda gunluk + arsivden
     YENIDEN uretilir (TURETILMIS, kaynak degil; silinse de kayip yok).
     Her satir: tahmin + sonraki 6 METAR + sonuc, en yeni ustte. GitHub
     CSV'yi tablo olarak gosterir. Ozet olcumler: --ozet.

HEDEF TANIMI - EGITIMDEKIYLE AYNI (sis_modeli/hedef.py, ozellik.py):
  olay = gorus < 1000 m VEYA alani kaplayan FG (MI/BC/PR tanimlayicili
  ve VC siddetli FG sayilmaz). Ufuk 3 saat; egitim 30 dakikalik RUTIN
  METAR izgarasiyla yapildi, SPECI'ler hedefe girmedi. Bu yuzden ASIL
  sonuc yalnizca (t, t+3 sa] araligindaki :20/:50 METAR slotlarina
  bakar - her tahmin icin 6 slot. SPECI'deki olay AYRI bir bilgi
  alanidir, olcumlere GIRMEZ.

EVREN: model yalnizca "su an olay YOKKEN" anlarla egitildi (onset). Olay
SURERKEN verilen tahmin "olay_suruyor" diye isaretlenir ve olcumlere
girmez (sureklilik skoru sisirirdi).

SONUC DURUMLARI
  oldu              bir slotta olay var (gorulur gorulmez kesin)
  olmadi            6 slotun HEPSI gozlenmis, hicbirinde olay yok
  bekliyor          3 saat dolmadi, henuz olay yok
  eksik_bekleniyor  3 saat doldu, slot eksik; arsivin 24 saatlik geri
                    doldurmasi eksigi kapatabilir
  belirsiz          t + 3 + 24 sa gecti, slot hala eksik, olay yok.
                    TAHMIN EDILMEZ; olcumlere girmez, AYRICA sayilir.

ONCEDEN SABITLENEN OLCUMLER (sonuclara bakilip DEGISTIRILMEZ)
  - Bant basina gerceklesme orani + Wilson %95 guven araligi. Bantlar
    sayfadakiyle AYNI: taban orana gore kat < 2 dusuk, < 5 orta, aksi
    yuksek (BANT_KAT_SINIRLARI).
  - Brier skoru ve iklime (ltfj_sis_olasilik.TABAN_ORAN) gore Brier
    beceri skoru (BSS). BSS, sonuclanmis olay sayisi YORUM_ESIGI_OLAY'a
    ulasmadan GOSTERILMEZ - bir iki olayla hesaplanan beceri skoru
    gurultudur.
  - Yalnizca evren == onset ve durum oldu/olmadi. Belirsiz ve evren disi
    satirlar dislanir ama SAYILARI gosterilir.

NE YAPMAZ: modeli, katsayilari, kalibrasyonu DEGISTIRMEZ; yeni bir tahmin
uretmez. Bot gunluge sayfanin hesapladigi degeri yazar (bkz. ltfj_sayfa.
sis_tahmini).
"""

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ltfj_sis_olasilik as sis_olasilik
from ltfj_analiz import RE_HAVA

KLASOR = Path(__file__).resolve().parent
DOSYA_ADI = "tahmin_gunlugu.csv"
VARSAYILAN_DOSYA = KLASOR / DOSYA_ADI
ARSIV_DOSYASI = KLASOR / "gozlem_arsivi.csv"
DOGRULAMA_DOSYA_ADI = "tahmin_dogrulama.csv"
DOGRULAMA_SUTUNLARI = (
    "gozlem_zaman", "gozlem_tip", "olasilik_yuzde", "bant", "evren", "sonuc",
    "ilk_olay", "slot_1", "slot_2", "slot_3", "slot_4", "slot_5", "slot_6",
    "speci_olay", "model_surumu",
)
# Botun bir slotu arsive alma payi (METAR :20/:50, bot :24/:54 + gecikme):
# bu surede arsivde olmayan slot "eksik" degil "henuz" yazilir.
ALIM_PAYI_DK = 40

SUTUNLAR = (
    "gozlem_zaman", "gozlem_tip", "kayit_zamani", "olasilik", "bant", "evren",
    "gorus", "hava", "spread", "saat_sayfa", "saat_gozlem", "ruzgar_kuzey",
    "spread_egilim_3", "b_tertil", "model_surumu",
)

UFUK_SAAT = sis_olasilik.HEDEF_UFUK_SAAT          # 3
OLAY_GORUS_M = sis_olasilik.HEDEF_GORUS_M         # 1000
IZGARA_DAKIKALARI = (20, 50)                      # LTFJ rutin METAR
SLOT_ADIM_DK = 30
GERI_DOLDURMA_SAAT = 24                           # arsivin H24 penceresi
BANT_KAT_SINIRLARI = (2, 5)
YORUM_ESIGI_OLAY = 10

# FG'yi alani kaplayan sis olmaktan cikaranlar (sis_modeli/ozellik.py ile
# AYNI - bot sis_modeli'ni import etmez, bkz. ltfj_sis_olasilik izolasyonu).
SIS_DISI_TANIMLAYICILAR = ("MI", "BC", "PR")


# ------------------------------------------------------------ tanimlar ---
def bant(p: float | None) -> str | None:
    """Sayfadaki bant: taban orana gore kat."""
    if p is None:
        return None
    kat = p / sis_olasilik.TABAN_ORAN
    if kat < BANT_KAT_SINIRLARI[0]:
        return "dusuk"
    if kat < BANT_KAT_SINIRLARI[1]:
        return "orta"
    return "yuksek"


def _hava_listesi(hava) -> list:
    if not hava:
        return []
    if isinstance(hava, str):
        return hava.split()
    return list(hava)


def sis_kodu_var(hava) -> bool:
    """Hava kodlarinda ALANI KAPLAYAN FG var mi (ozellik._sis_kodu_var)."""
    for token in _hava_listesi(hava):
        m = RE_HAVA.match(token)
        if not m:
            continue
        siddet, tanimlayici, olay = m.groups()
        if "FG" not in olay or siddet == "VC":
            continue
        if any(t in (tanimlayici or "") for t in SIS_DISI_TANIMLAYICILAR):
            continue
        return True
    return False


def _sayi(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def olay_mi(gorus, hava) -> bool | None:
    """True/False; gorus bilinmiyor VE FG yoksa None (karar verilemez)."""
    if sis_kodu_var(hava):
        return True
    g = _sayi(gorus)
    if g is None:
        return None
    return g < OLAY_GORUS_M


def model_surumu() -> str:
    """Dondurulmus katsayilarin kisa ozeti - katsayilar degisirse gunlukte
    iki model birbirine karismasin."""
    veri = json.dumps([sis_olasilik.SABIT_TERIM, sis_olasilik.KATSAYILAR,
                       sis_olasilik.WOE_TABLOLARI], sort_keys=True, default=str)
    return "A-" + hashlib.sha1(veri.encode("utf-8")).hexdigest()[:10]


def _utc(z: datetime) -> datetime:
    return z.astimezone(timezone.utc)


def _iso(z: datetime) -> str:
    return _utc(z).replace(second=0, microsecond=0).isoformat()


def _dt(s) -> datetime | None:
    if not s:
        return None
    try:
        z = datetime.fromisoformat(str(s))
    except ValueError:
        return None
    return z if z.tzinfo else z.replace(tzinfo=timezone.utc)


def _yuvarla(v, basamak):
    return "" if v is None else round(float(v), basamak)


# -------------------------------------------------------------- gunluk ---
def satir_kur(tahmin: dict, kayit_zamani: datetime) -> dict:
    """ltfj_sayfa.sis_tahmini() ciktisini bir gunluk satirina cevirir."""
    p = tahmin["olasilik"]
    olay = olay_mi(tahmin.get("gorus"), tahmin.get("hava"))
    return {
        "gozlem_zaman": _iso(tahmin["zaman"]),
        "gozlem_tip": tahmin["tip"],
        "kayit_zamani": _utc(kayit_zamani).isoformat(timespec="seconds"),
        "olasilik": f"{p:.6f}",
        "bant": bant(p),
        "evren": "olay_suruyor" if olay else "onset",
        "gorus": "" if tahmin.get("gorus") is None else tahmin["gorus"],
        "hava": " ".join(_hava_listesi(tahmin.get("hava"))),
        "spread": _yuvarla(tahmin.get("spread"), 1),
        "saat_sayfa": tahmin.get("saat_sayfa", ""),
        "saat_gozlem": tahmin.get("saat_gozlem", ""),
        "ruzgar_kuzey": _yuvarla(tahmin.get("ruzgar_kuzey"), 2),
        "spread_egilim_3": _yuvarla(tahmin.get("spread_egilim_3"), 1),
        "b_tertil": tahmin.get("b_tertil") or "",
        "model_surumu": model_surumu(),
    }


def _anahtar(s: dict) -> tuple:
    return (s.get("gozlem_zaman"), s.get("gozlem_tip"))


def oku(dosya: Path = VARSAYILAN_DOSYA) -> list[dict]:
    dosya = Path(dosya)
    if not dosya.exists():
        return []
    with dosya.open("r", encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def yaz(satirlar: list, dosya: Path = VARSAYILAN_DOSYA) -> None:
    dosya = Path(dosya)
    dosya.parent.mkdir(parents=True, exist_ok=True)
    sirali = sorted(satirlar, key=lambda s: (s.get("gozlem_zaman") or "",
                                             s.get("gozlem_tip") or ""))
    with dosya.open("w", encoding="utf-8", newline="") as f:
        y = csv.DictWriter(f, fieldnames=SUTUNLAR, extrasaction="ignore")
        y.writeheader()
        for s in sirali:
            y.writerow({k: ("" if s.get(k) is None else s.get(k)) for k in SUTUNLAR})


def kaydet(tahmin: dict | None, dosya: Path = VARSAYILAN_DOSYA,
           simdi: datetime | None = None) -> bool:
    """Tahmini gunluge EKLER. Ayni gozlem zaten kayitliysa DOKUNMAZ (ilk
    kayit kalir) ve False doner. Tahmin yoksa (girdi eksik) False."""
    if not tahmin or tahmin.get("olasilik") is None:
        return False
    simdi = simdi or datetime.now(timezone.utc)
    satir = satir_kur(tahmin, simdi)
    mevcut = oku(dosya)
    if any(_anahtar(s) == _anahtar(satir) for s in mevcut):
        return False
    mevcut.append(satir)
    yaz(mevcut, dosya)
    return True


def birlestir(a: list, b: list) -> list:
    """Iki gunlugun birlesimi. Ayni anahtarda ONCE KAYDEDILEN kalir -
    simetrik ve idempotent (esit kayit zamaninda icerik sirasi karar
    verir)."""
    secilen = {}
    for s in list(a) + list(b):
        k = _anahtar(s)
        eski = secilen.get(k)
        if eski is None or (s.get("kayit_zamani") or "", tuple(s.get(c) or "" for c in SUTUNLAR)) < \
                (eski.get("kayit_zamani") or "", tuple(eski.get(c) or "" for c in SUTUNLAR)):
            secilen[k] = s
    return list(secilen.values())


def birlestir_bizim(bizim: Path, dosya: Path = VARSAYILAN_DOSYA) -> int:
    """Workflow push cakismasi: uzaktaki (diskteki) gunluk + bizimki."""
    sonuc = birlestir(oku(dosya), oku(bizim))
    yaz(sonuc, dosya)
    return len(sonuc)


# --------------------------------------------------------- eslestirici ---
def slotlar(t: datetime) -> list[datetime]:
    """(t, t + UFUK] icindeki rutin METAR slotlari (:20/:50) - her zaman 6."""
    t = _utc(t)
    bas = t.replace(second=0, microsecond=0)
    # t'den SONRAKI ilk izgara dakikasi
    aday = bas.replace(minute=0)
    while aday <= t or aday.minute not in IZGARA_DAKIKALARI:
        aday += timedelta(minutes=10)
    out = []
    while aday <= t + timedelta(hours=UFUK_SAAT):
        out.append(aday)
        aday += timedelta(minutes=SLOT_ADIM_DK)
    return out


def _arsiv_dizini(arsiv: list) -> tuple[dict, list]:
    metar, speci = {}, []
    for s in arsiv:
        z = _dt(s.get("zaman"))
        if z is None:
            continue
        z = _utc(z)
        if s.get("tip") == "METAR":
            metar[z] = s
        elif s.get("tip") == "SPECI":
            speci.append((z, s))
    speci.sort(key=lambda x: x[0])
    return metar, speci


def _slot_kaydi(z: datetime, s: dict | None) -> dict:
    if s is None:
        return {"zaman": z.isoformat(), "var": False, "gorus": None, "hava": "",
                "olay": None}
    return {"zaman": z.isoformat(), "var": True, "gorus": _sayi(s.get("gorus")),
            "hava": s.get("hava") or "", "olay": olay_mi(s.get("gorus"), s.get("hava"))}


def sonuclandir(gunluk: list, arsiv: list, simdi: datetime) -> list[dict]:
    """Her gunluk satiri icin sonuc. Gunluk sirasini korur."""
    simdi = _utc(simdi)
    metar, speci = _arsiv_dizini(arsiv)
    out = []
    for g in gunluk:
        t = _dt(g.get("gozlem_zaman"))
        if t is None:
            continue
        t = _utc(t)
        bitis = t + timedelta(hours=UFUK_SAAT)
        slot_listesi = [_slot_kaydi(z, metar.get(z)) for z in slotlar(t)]
        speci_listesi = [_slot_kaydi(z, s) for z, s in speci if t < z <= bitis]
        ilk_olay = next((s["zaman"] for s in slot_listesi if s["olay"]), None)
        hepsi_bilinen = all(s["olay"] is not None for s in slot_listesi)
        if ilk_olay:
            durum = "oldu"
        elif hepsi_bilinen:
            durum = "olmadi"
        elif simdi < bitis:
            durum = "bekliyor"
        elif simdi < bitis + timedelta(hours=GERI_DOLDURMA_SAAT):
            durum = "eksik_bekleniyor"
        else:
            durum = "belirsiz"
        out.append({
            "gozlem_zaman": t.isoformat(),
            "gozlem_tip": g.get("gozlem_tip"),
            "olasilik": _sayi(g.get("olasilik")),
            "bant": g.get("bant") or bant(_sayi(g.get("olasilik"))),
            "evren": g.get("evren") or "onset",
            "model_surumu": g.get("model_surumu") or "",
            "durum": durum,
            "ilk_olay": ilk_olay,
            "slotlar": slot_listesi,
            "speci": speci_listesi,
            "speci_olay": any(s["olay"] for s in speci_listesi),
        })
    return out


# ------------------------------------------------------------- olcumler ---
def wilson(k: int, n: int, z: float = 1.96) -> tuple | None:
    """Wilson %95 guven araligi (oran icin; kucuk orneklemde normal
    yaklasimdan cok daha durust)."""
    if n <= 0:
        return None
    p = k / n
    payda = 1 + z * z / n
    merkez = (p + z * z / (2 * n)) / payda
    yari = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / payda
    return (max(0.0, merkez - yari), min(1.0, merkez + yari))


def ozet(sonuclar: list) -> dict:
    """Onceden sabitlenmis olcumler (bkz. modul belgesi)."""
    say = {"toplam": len(sonuclar), "bekliyor": 0, "eksik_bekleniyor": 0,
           "belirsiz": 0, "evren_disi": 0}
    sayilan = []
    for s in sonuclar:
        if s["evren"] != "onset":
            say["evren_disi"] += 1
        elif s["durum"] in ("oldu", "olmadi") and s["olasilik"] is not None:
            sayilan.append(s)
        elif s["durum"] in say:
            say[s["durum"]] += 1
    bantlar = {}
    for ad in ("dusuk", "orta", "yuksek"):
        grup = [s for s in sayilan if s["bant"] == ad]
        k = sum(1 for s in grup if s["durum"] == "oldu")
        n = len(grup)
        bantlar[ad] = {
            "n": n, "olay": k,
            "oran": (k / n) if n else None,
            "ga": wilson(k, n),
            "ort_tahmin": (sum(s["olasilik"] for s in grup) / n) if n else None,
        }
    n = len(sayilan)
    olay = sum(1 for s in sayilan if s["durum"] == "oldu")
    brier = brier_iklim = bss = None
    if n:
        brier = sum((s["olasilik"] - (s["durum"] == "oldu")) ** 2 for s in sayilan) / n
        c = sis_olasilik.TABAN_ORAN
        brier_iklim = sum((c - (s["durum"] == "oldu")) ** 2 for s in sayilan) / n
        if olay >= YORUM_ESIGI_OLAY and brier_iklim > 0:
            bss = 1 - brier / brier_iklim
    return {"sayim": say, "n": n, "olay": olay,
            # Ayni sis olayi kendinden onceki birkac tahmini "oldu" yapar;
            # hepsi ayni ilk_olay'i tasir. Bagimsiz olay = farkli ilk_olay.
            "bagimsiz_olay": len({s.get("ilk_olay") for s in sayilan
                                  if s["durum"] == "oldu" and s.get("ilk_olay")}),
            "bantlar": bantlar, "brier": brier, "brier_iklim": brier_iklim,
            "bss": bss, "yorum_esigi_olay": YORUM_ESIGI_OLAY}


def dogrulama_verisi(klasor: Path = KLASOR, simdi: datetime | None = None) -> dict:
    """Gunluk + arsivden sonuclar ve ozet."""
    simdi = simdi or datetime.now(timezone.utc)
    gunluk = oku(Path(klasor) / DOSYA_ADI)
    arsiv = []
    arsiv_dosyasi = Path(klasor) / "gozlem_arsivi.csv"
    if arsiv_dosyasi.exists():
        with arsiv_dosyasi.open("r", encoding="utf-8", newline="") as f:
            arsiv = [dict(r) for r in csv.DictReader(f)]
    sonuclar = sonuclandir(gunluk, arsiv, simdi)
    return {"sonuclar": sonuclar, "ozet": ozet(sonuclar),
            "baslangic": gunluk[0]["gozlem_zaman"] if gunluk else None}


def _saat(iso: str | None) -> str:
    z = _dt(iso)
    return _utc(z).strftime("%H:%M") if z else ""


def _gozlem_metni(slot: dict) -> str:
    """'04:50 0800 FG' - METAR'daki gibi 4 haneli gorus + hava kodlari."""
    g = slot["gorus"]
    metin = f'{_saat(slot["zaman"])} ' + ("////" if g is None else f"{int(g):04d}")
    return metin + (f' {slot["hava"]}' if slot["hava"] else "")


def dogrulama_satirlari(sonuclar: list, simdi: datetime) -> list[dict]:
    """Okuma dosyasinin satirlari - en yeni tahmin ustte."""
    simdi = _utc(simdi)
    out = []
    for s in sorted(sonuclar, key=lambda x: x["gozlem_zaman"], reverse=True):
        satir = {
            "gozlem_zaman": _utc(_dt(s["gozlem_zaman"])).strftime("%Y-%m-%d %H:%MZ"),
            "gozlem_tip": s["gozlem_tip"],
            "olasilik_yuzde": "" if s["olasilik"] is None else f'{100 * s["olasilik"]:.1f}',
            "bant": s["bant"] or "",
            "evren": s["evren"],
            "sonuc": s["durum"],
            "ilk_olay": _saat(s["ilk_olay"]),
            "speci_olay": " | ".join(_gozlem_metni(x) for x in s["speci"] if x["olay"]),
            "model_surumu": s["model_surumu"],
        }
        for i, sl in enumerate(s["slotlar"], 1):
            if sl["var"]:
                deger = _gozlem_metni(sl) + (" [OLAY]" if sl["olay"] else "")
            elif _dt(sl["zaman"]) > simdi - timedelta(minutes=ALIM_PAYI_DK):
                deger = f'{_saat(sl["zaman"])} henuz'
            else:
                deger = f'{_saat(sl["zaman"])} yok'
            satir[f"slot_{i}"] = deger
        out.append(satir)
    return out


def dogrulama_yaz(klasor: Path = KLASOR, simdi: datetime | None = None) -> dict:
    """tahmin_dogrulama.csv'yi gunluk + arsivden yeniden uretir; ozeti doner."""
    simdi = simdi or datetime.now(timezone.utc)
    v = dogrulama_verisi(klasor, simdi)
    hedef = Path(klasor) / DOGRULAMA_DOSYA_ADI
    if not v["sonuclar"]:
        return v["ozet"]
    with hedef.open("w", encoding="utf-8", newline="") as f:
        y = csv.DictWriter(f, fieldnames=DOGRULAMA_SUTUNLARI)
        y.writeheader()
        for r in dogrulama_satirlari(v["sonuclar"], simdi):
            y.writerow(r)
    return v["ozet"]


# ------------------------------------------------------------------ CLI ---
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--birlestir-bizim", metavar="DOSYA",
                    help="push cakismasi: bizim gunlugu diskteki ile birlestir")
    ap.add_argument("--dosya", default=str(VARSAYILAN_DOSYA))
    ap.add_argument("--ozet", action="store_true", help="olcumleri yazdir")
    ap.add_argument("--dogrulama-yaz", action="store_true",
                    help="tahmin_dogrulama.csv'yi gunluk + arsivden yeniden uret")
    a = ap.parse_args(argv)
    if a.birlestir_bizim:
        n = birlestir_bizim(Path(a.birlestir_bizim), Path(a.dosya))
        print(f"tahmin gunlugu birlestirildi: {n} satir")
        return 0
    if a.dogrulama_yaz:
        o = dogrulama_yaz(Path(a.dosya).resolve().parent)
        print(f"tahmin_dogrulama.csv: {o['n']} sonuclanan, {o['olay']} olay")
        return 0
    if a.ozet:
        v = dogrulama_verisi(Path(a.dosya).resolve().parent)
        print(json.dumps(v["ozet"], ensure_ascii=False, indent=1, default=str))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
