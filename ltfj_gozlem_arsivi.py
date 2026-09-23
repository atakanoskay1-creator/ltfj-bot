#!/usr/bin/env python3
"""SPECI DAHIL, GORUS TASIYAN, ekleme-yalnizca gozlem arsivi.

NEDEN VAR - IKI AYRI BOSLUK:

1) Egitim arsivi (sis_modeli/veri/ltfj_ozellik.csv.gz) IEM ASOS'tan geliyor
   ve SPECI ICERMIYOR. Olculdu: 274.907 satirin 274.901'i :20/:50'de,
   yani rutin METAR kadansi; izgara disi yalnizca 6 satir (%0.002).
   Oysa CANLI yol (MGM, ltfj_rasat.py) SPECI'yi yakaliyor - ayni olcumde
   state'teki son 300 kaydin 16'si (%5.3) izgara disiydi.

   Bu fark onemli cunku SPECI tam da GECIS anlarinda yayinlanir; sis
   olusum/dagilma surelerinin gercek hizi ancak onlarla gorulur (bkz.
   sis_modeli/gorus_gecis.py ve Misawa ve ark. 2026'nin SPECI vurgusu).
   Su an "0.5 saat" dedigimiz en hizli gecis aslinda "<=0.5 saat"tir.

2) state["olcum_gecmisi"] SPECI'yi tasiyor AMA:
   - OLCUM_GECMIS_LIMIT = 300 (~6 gun) - kayan pencere, arsiv degil;
     web sayfasindaki trend grafikleri icin boyutlandirilmis.
   - GORUS ALANINI HIC SAKLAMIYOR (zaman/ruzgar/tavan/qnh/sicaklik/ciy).
     Yani en cok ihtiyac duydugumuz alan atiliyor.

   olcum_gecmisi'ni buyutup gorus eklemek YANLIS olurdu: o yapi her
   kosuda ltfj_state.json icinde commit ediliyor ve sinirsiz buyumesi
   state dosyasini sisirirdi. Bu yuzden AYRI, ekleme-yalnizca bir dosya.

BICIM - DUZ CSV, gzip DEGIL: dosya her kosuda git'e commit ediliyor.
Ekleme-yalnizca duz metin git'te yalnizca DELTA saklar ve satir bazli
birlesir; gzip ise her commit'te tum dosyayi yeni bir ikili blob olarak
saklardi ve birlestirilemezdi.

BOYUT: ~50 gozlem/gun -> ~18 bin satir/yil, satir basi ~90 bayt =
yilda ~1,6 MB. Git icin sorun degil.

GERIYE DONUK DOLDURMA YOK: bu dosya BUGUNDEN ITIBAREN birikir. Gecmis
SPECI'ler icin IEM'in SPECI tasiyip tasimadigi ayrica arastirilmali
(bkz. README "SPECI boslugu").
"""

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

VARSAYILAN_DOSYA = Path(__file__).resolve().parent / "gozlem_arsivi.csv"

# Sutun sirasi SABIT - yeni alan yalnizca SONA eklenir, yoksa eski
# satirlar kayar. Okuyucu eksik sutunu bos sayar.
SUTUNLAR = ("zaman", "tip", "gorus", "tavan", "sicaklik", "cig_noktasi",
            "ruzgar_yon", "ruzgar_hiz", "ruzgar_hamle", "qnh", "hava", "cavok")


def _satir_kur(rapor: dict, cozum: dict) -> dict:
    """Tek bir METAR/SPECI'yi arsiv satirina cevirir.

    `hava` listesi bosluk ayrili tek dizeye cevriliyor - egitim
    arsivindeki (ltfj_ozellik.csv.gz) 'hava' sutunuyla AYNI bicim, ki
    ikisi ileride birlestirilebilsin."""
    hava = cozum.get("hava") or []
    return {
        "zaman": rapor["zaman"].astimezone(timezone.utc).isoformat(timespec="seconds"),
        "tip": rapor["tip"],
        "gorus": cozum.get("gorus"),
        "tavan": cozum.get("tavan"),
        "sicaklik": cozum.get("sicaklik"),
        "cig_noktasi": cozum.get("cig_noktasi"),
        "ruzgar_yon": cozum.get("ruzgar_yon"),
        "ruzgar_hiz": cozum.get("ruzgar_hiz"),
        "ruzgar_hamle": cozum.get("ruzgar_hamle"),
        "qnh": cozum.get("qnh"),
        "hava": " ".join(hava) if isinstance(hava, list) else (hava or ""),
        "cavok": int(bool(cozum.get("cavok"))),
    }


def oku(dosya: Path = VARSAYILAN_DOSYA) -> list[dict]:
    """Arsivi okur; yoksa bos liste doner (hata DEGIL - ilk kosu)."""
    if not dosya.exists():
        return []
    with dosya.open("r", encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def yaz(satirlar: list, dosya: Path = VARSAYILAN_DOSYA) -> None:
    """Zaman damgasina gore SIRALI ve TEKIL yazar.

    Siralama sart: dosya ekleme-yalnizca ama bot bazen gecmise donuk bir
    rapor gorebilir (MGM geciken bir SPECI yayinlayabilir). Sirasiz
    dosya hem okunmaz hem de git diff'lerini gereksiz buyutur."""
    tekil = {}
    for s in satirlar:
        tekil[(s.get("zaman"), s.get("tip"))] = s
    sirali = sorted(tekil.values(), key=lambda s: (s.get("zaman") or "",
                                                   s.get("tip") or ""))
    dosya.parent.mkdir(parents=True, exist_ok=True)
    with dosya.open("w", encoding="utf-8", newline="") as f:
        y = csv.DictWriter(f, fieldnames=SUTUNLAR, extrasaction="ignore")
        y.writeheader()
        for s in sirali:
            y.writerow({k: ("" if s.get(k) is None else s.get(k)) for k in SUTUNLAR})


def ekle(raporlar: list, coz, dosya: Path = VARSAYILAN_DOSYA) -> int:
    """Yeni METAR/SPECI'leri arsive ekler; EKLENEN satir sayisini doner.

    coz: metar_coz gibi (metin -> cozum) bir fonksiyon. Disaridan
    veriliyor ki bu modul ltfj_analiz'e bagimli olmasin ve testler sahte
    bir cozucuyle calisabilsin.

    Ayni (zaman, tip) ciftinden ikinci kez eklenmez - bot her kosuda ayni
    raporu yeniden gorur."""
    mevcut = oku(dosya)
    anahtarlar = {(s.get("zaman"), s.get("tip")) for s in mevcut}
    yeni = []
    for r in raporlar:
        if r.get("tip") not in ("METAR", "SPECI") or not r.get("zaman"):
            continue
        try:
            cozum = coz(r["metin"])
        except Exception as e:                       # tek bozuk rapor
            print(f"[uyarı] gözlem arşivi: rapor çözülemedi, atlanıyor: {e}",
                  file=sys.stderr)
            continue
        satir = _satir_kur(r, cozum)
        if (satir["zaman"], satir["tip"]) in anahtarlar:
            continue
        anahtarlar.add((satir["zaman"], satir["tip"]))
        yeni.append(satir)
    if not yeni:
        return 0
    yaz(mevcut + yeni, dosya)
    return len(yeni)


def birlestir(a: Path, b: Path, hedef: Path) -> int:
    """Iki arsiv dosyasini BIRLESTIRIR (zaman+tip birlesimi).

    NEDEN GEREKLI: ltfj.yml iki kosu ust uste bindiginde
    `git reset --hard origin/<dal>` yapip kendi dosyalarini geri
    kopyaliyor. Ekleme-yalnizca bir dosyada bu, uzaktaki kosunun
    eklediklerini KAYBETTIRIR. state_birlestir.py ayni sorunu
    ltfj_state.json icin cozuyor; bu onun gozlem arsivi karsiligi."""
    hepsi = oku(a) + oku(b)
    yaz(hepsi, hedef)
    return len(oku(hedef))


def _ozet(dosya: Path) -> str:
    satirlar = oku(dosya)
    if not satirlar:
        return f"{dosya.name}: boş"
    speci = sum(1 for s in satirlar if s.get("tip") == "SPECI")
    gorus_var = sum(1 for s in satirlar if s.get("gorus"))
    return (f"{dosya.name}: {len(satirlar)} gözlem "
            f"({satirlar[0]['zaman'][:16]} → {satirlar[-1]['zaman'][:16]}), "
            f"{speci} SPECI (%{100 * speci / len(satirlar):.1f}), "
            f"{gorus_var} görüşlü")


def main(argv=None) -> int:
    import argparse

    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--dosya", type=Path, default=VARSAYILAN_DOSYA)
    a.add_argument("--birlestir", nargs=2, type=Path, metavar=("A", "B"),
                   help="iki arşivi birleştirip --dosya'ya yazar")
    s = a.parse_args(argv)
    if s.birlestir:
        n = birlestir(s.birlestir[0], s.birlestir[1], s.dosya)
        print(f"birleştirildi: {n} gözlem -> {s.dosya}")
    print(_ozet(s.dosya))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
