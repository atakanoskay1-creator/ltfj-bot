#!/usr/bin/env python3
"""LTFJ'de sis olaylarinda gorusun DUSME ve TOPARLANMA sureleri.

SORU (operasyonel): "Gorus 5000 m'nin altina dustu - LVO esigine ne kadar
zamanim var?" ve "Sis dagiliyor - VMC'ye ne zaman donerim?"

Bu bir MODEL DEGIL, TARIHSEL IKLIMBILIM. Tahmin uretmiyor, gecmiste ne
oldugunu sayiyor. Dolayisiyla:
  - sizinti (leakage) kavrami gecerli degil, holdout'a dokunulmuyor,
  - arsivin tamami kullanilabiliyor. Model tarafi 2011+ kullaniyordu
    cunku 2021-2023 ciy noktasi kusuru vardi; burada ciy noktasi HIC
    KULLANILMIYOR, yalnizca gorus ve hava kodu.

Pratikte kapsam yine de 2011'de basliyor ama bu bir tercih degil VERI
GERCEGI: arsivde 2003'ten tek bir kayit, 2010'dan 1483 kayit var, ilk
tam yil 2011 (~17500 kayit). kapsanan_aralik() bunu otomatik tespit
edip rapora yaziyor - "2003-2026" demek orneklemi oldugundan genis
gosterirdi.

YONTEM: Misawa, Nishi & Sugawara (SOLA 2026) Tablo 1/2'nin LTFJ
karsiligi. Onlarin olay tanimi Tardif & Rasmussen (2007)'den geliyor:
  1. Gorus 2 km'nin altinda KESINTISIZ en az 3 saat,
  2. Bu surenin icinde gorus 1 km'nin altinda en az 1 saat,
  3. Olay boyunca kar YOK.

ONEMLI FARK - COZUNURLUK: makale SPECI raporlarini da kullanarak dakika
cozunurlugune cikiyor. Bu arsiv 30 DAKIKALIK izgarada (LTFJ rutin METAR
kadansi; SPECI pratikte veride yok - bkz. README). Yani buradaki sureler
30 dakikaya YUVARLIDIR. Saatler suren geciseler icin medyan anlamli
kalir ama "45 dakikada indi" gibi bir ayrinti bu veriyle GORULEMEZ.

MAKALENIN SAYILARI BURAYA KOPYALANMAZ: onlarinki Japonya kiyisi,
1989-2015. Tip paylari cografyayla degisiyor (Japonya'da radyasyon %41,
New York'ta yagis %36, Selanik'te adveksiyon %30). Metodoloji alinir,
sayi alinmaz.

SIS TIPI: makale bes tipe ayiriyor ama adveksiyon/radyasyon ayriminin
kendisi zor oldugunu soyluyor ve siniflandiricilarini ayrica test
ediyorlar. Burada YALNIZCA yagisli/yagissiz ayrimi yapiliyor - `hava`
kodundan guvenilir sekilde cikarilabilen ve makalede EN BELIRGIN farki
(4.1 sa vs 1.6-2.0 sa) ureten ayrim bu. Dogrulayamayacagim bir
siniflandirici uydurmuyorum.

Kullanim:
    python -m sis_modeli.gorus_gecis
    python -m sis_modeli.gorus_gecis --json cikti.json
"""

import argparse
import gzip
import csv
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

VARSAYILAN_VERI = Path(__file__).resolve().parent / "veri" / "ltfj_ozellik.csv.gz"

# --- olay tanimi (TR07) ---
OLAY_GORUS_M = 2000        # bu esigin altinda kesintisiz...
OLAY_SURE_SAAT = 3         # ...en az bu kadar
SIS_GORUS_M = 1000         # icinde bu esigin altinda...
SIS_SURE_SAAT = 1          # ...en az bu kadar

# --- olculen gecisler ---
VMC_GORUS_M = 5000         # VFR icin gereken asgari gorus
SVFR_GORUS_M = 1500        # ozel VFR alt siniri
PENCERE_SAAT = 10          # olaydan once/sonra bakilacak azami sure

# Ardisik iki kayit arasi bundan uzunsa SUREKLILIK BILINMIYOR demektir.
# 30 dk'lik izgarada tek bir eksik rapor tolere edilir, ikisi edilmez -
# yoksa 6 saatlik bir bosluk "kesintisiz sis" sayilabilirdi.
AZAMI_BOSLUK_DK = 70

# Bir yilin "kapsanmis" sayilmasi icin gereken asgari kayit. Arsivde 2003
# yilindan TEK bir kayit, 2010'dan 1483 kayit var; bunlari kapsam olarak
# saymak "2003-2026" gibi yaniltici bir aralik yazdirirdi. Tam yil ~17500
# kayit (30 dk izgara), esik bunun kabaca onda biri.
ASGARI_YILLIK_KAYIT = 2000

# METAR hava kodlarinda yagis. Nitelemeler (-, +, VC) ve SH/TS/FZ
# birlesimleri onune gelebildigi icin alt dize araniyor.
YAGIS = re.compile(r"(RA|DZ|SN|SG|PL|GR|GS|IC|UP)")
KAR = re.compile(r"(SN|SG)")


def veri_oku(dosya: Path) -> list[dict]:
    """(zaman, gorus, hava) uclusu - baska alan OKUNMUYOR."""
    with gzip.open(dosya, "rt", encoding="utf-8") as f:
        satirlar = []
        for x in csv.DictReader(f):
            if not x["gorus"]:
                continue
            satirlar.append({
                "dt": datetime.fromisoformat(x["zaman"]),
                "gorus": float(x["gorus"]),
                "hava": x["hava"] or "",
            })
    satirlar.sort(key=lambda s: s["dt"])
    return satirlar


def _bosluksuz_mu(satirlar: list, i: int, j: int) -> bool:
    """[i, j] araliginda AZAMI_BOSLUK_DK'yi asan delik var mi?"""
    for k in range(i, j):
        if (satirlar[k + 1]["dt"] - satirlar[k]["dt"]) > timedelta(minutes=AZAMI_BOSLUK_DK):
            return False
    return True


def kapsanan_aralik(satirlar: list) -> tuple[int, int, list[int]]:
    """(ilk_yil, son_yil, seyrek_yillar) - seyrek yillar kapsama SAYILMAZ.

    Arsiv 2003'ten basliyor gibi gorunuyor ama o yildan tek bir kayit
    var; dusunmeden "2003-2026" yazmak orneklem buyuklugunu oldugundan
    genis gosterirdi."""
    import collections
    sayim = collections.Counter(s["dt"].year for s in satirlar)
    dolu = sorted(y for y, n in sayim.items() if n >= ASGARI_YILLIK_KAYIT)
    seyrek = sorted(y for y, n in sayim.items() if n < ASGARI_YILLIK_KAYIT)
    return (dolu[0], dolu[-1], seyrek) if dolu else (0, 0, seyrek)


def olaylari_bul(satirlar: list) -> list[dict]:
    """TR07 olcutleriyle bagimsiz sis olaylari.

    Doner: {"bas_i", "son_i", "sis_bas_i", "sis_son_i", "yagisli"}
    indeksleri satirlar listesine gore."""
    olaylar = []
    n = len(satirlar)
    i = 0
    while i < n:
        if satirlar[i]["gorus"] >= OLAY_GORUS_M:
            i += 1
            continue
        # <2km blogunun sonunu bul (bosluk da blogu bitirir)
        j = i
        while (j + 1 < n
               and satirlar[j + 1]["gorus"] < OLAY_GORUS_M
               and (satirlar[j + 1]["dt"] - satirlar[j]["dt"])
                   <= timedelta(minutes=AZAMI_BOSLUK_DK)):
            j += 1

        sure = satirlar[j]["dt"] - satirlar[i]["dt"]
        if sure >= timedelta(hours=OLAY_SURE_SAAT):
            # icinde >=1 saat <1km var mi?
            sis_idx = [k for k in range(i, j + 1)
                       if satirlar[k]["gorus"] < SIS_GORUS_M]
            if sis_idx:
                sis_sure = satirlar[sis_idx[-1]]["dt"] - satirlar[sis_idx[0]]["dt"]
                karli = any(KAR.search(satirlar[k]["hava"]) for k in range(i, j + 1))
                if sis_sure >= timedelta(hours=SIS_SURE_SAAT) and not karli:
                    olaylar.append({
                        "bas_i": i, "son_i": j,
                        "sis_bas_i": sis_idx[0], "sis_son_i": sis_idx[-1],
                        # "yagisli": olusumdan onceki 3 saatte yagis gorulmus mu
                        "yagisli": _onceki_yagis(satirlar, sis_idx[0]),
                    })
        i = j + 1
    return olaylar


def _onceki_yagis(satirlar: list, sis_i: int, saat: int = 3) -> bool:
    t0 = satirlar[sis_i]["dt"] - timedelta(hours=saat)
    k = sis_i
    while k >= 0 and satirlar[k]["dt"] >= t0:
        if YAGIS.search(satirlar[k]["hava"]):
            return True
        k -= 1
    return False


def dusme_suresi(satirlar: list, olay: dict) -> tuple[float | None, str]:
    """Gorusun VMC_GORUS_M'den SVFR_GORUS_M'ye inme suresi (saat).

    (sure, durum) doner; sure None ise durum sebebi soyler."""
    t0 = satirlar[olay["sis_bas_i"]]["dt"]
    pencere_bas = t0 - timedelta(hours=PENCERE_SAAT)

    # Pencerenin basinda zaten <5000 ise olay HARIC (makalenin yontemi:
    # boyle olaylarda "5000'den dusus" hic yasanmamistir).
    k = olay["sis_bas_i"]
    while k > 0 and satirlar[k - 1]["dt"] >= pencere_bas:
        k -= 1
    if satirlar[k]["dt"] > pencere_bas + timedelta(minutes=AZAMI_BOSLUK_DK):
        return None, "pencere_eksik"
    if satirlar[k]["gorus"] < VMC_GORUS_M:
        return None, "zaten_dusuk"

    # t0'dan geriye: son >=5000 kaydi
    bes_i = None
    for m in range(olay["sis_bas_i"], k - 1, -1):
        if satirlar[m]["gorus"] >= VMC_GORUS_M:
            bes_i = m
            break
    if bes_i is None:
        return None, "5000_bulunamadi"

    # bes_i'den ileriye: ilk <=1500 kaydi
    bir5_i = None
    for m in range(bes_i, olay["sis_bas_i"] + 1):
        if satirlar[m]["gorus"] <= SVFR_GORUS_M:
            bir5_i = m
            break
    if bir5_i is None:
        return None, "1500_bulunamadi"
    if not _bosluksuz_mu(satirlar, bes_i, bir5_i):
        return None, "veri_boslugu"

    delta = satirlar[bir5_i]["dt"] - satirlar[bes_i]["dt"]
    return delta.total_seconds() / 3600.0, "ok"


def toparlanma_suresi(satirlar: list, olay: dict) -> tuple[float | None, str]:
    """Gorusun SIS_GORUS_M'den VMC_GORUS_M'ye cikma suresi (saat)."""
    son_i = olay["sis_son_i"]
    t_son = satirlar[son_i]["dt"]
    pencere_son = t_son + timedelta(hours=PENCERE_SAAT)
    n = len(satirlar)

    k = son_i
    while k + 1 < n and satirlar[k + 1]["dt"] <= pencere_son:
        k += 1
    if satirlar[k]["dt"] < pencere_son - timedelta(minutes=AZAMI_BOSLUK_DK):
        return None, "pencere_eksik"

    bes_i = None
    for m in range(son_i, k + 1):
        if satirlar[m]["gorus"] >= VMC_GORUS_M:
            bes_i = m
            break
    if bes_i is None:
        return None, "hala_dusuk"
    if not _bosluksuz_mu(satirlar, son_i, bes_i):
        return None, "veri_boslugu"

    delta = satirlar[bes_i]["dt"] - t_son
    return delta.total_seconds() / 3600.0, "ok"


def yuzdelik(degerler: list, p: float) -> float:
    """Dogrusal interpolasyonlu yuzdelik (numpy YOK - bu projede
    calisma ani bagimliligi standart kutuphaneyle sinirli)."""
    if not degerler:
        return float("nan")
    v = sorted(degerler)
    if len(v) == 1:
        return v[0]
    k = (len(v) - 1) * p
    alt, ust = int(k), min(int(k) + 1, len(v) - 1)
    return v[alt] + (v[ust] - v[alt]) * (k - alt)


def ozet(degerler: list) -> dict:
    return {
        "n": len(degerler),
        "p10": yuzdelik(degerler, 0.10),
        "p25": yuzdelik(degerler, 0.25),
        "medyan": yuzdelik(degerler, 0.50),
        "p75": yuzdelik(degerler, 0.75),
    }


def _satir_yaz(ad: str, o: dict) -> None:
    if not o["n"]:
        print(f"  {ad:<22}{'—':>7}  (ölçülebilir olay yok)")
        return
    print(f"  {ad:<22}{o['n']:>5}{o['p10']:>9.1f}{o['p25']:>8.1f}"
          f"{o['medyan']:>9.1f}{o['p75']:>8.1f}")


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    a.add_argument("--json", type=Path, help="sonuçları JSON olarak da yaz")
    s = a.parse_args(argv)
    if not s.veri.exists():
        import sys
        print(f"HATA: {s.veri} yok.", file=sys.stderr)
        return 1

    satirlar = veri_oku(s.veri)
    olaylar = olaylari_bul(satirlar)
    ilk, son, seyrek = kapsanan_aralik(satirlar)
    print(f"LTFJ görüş geçiş süreleri — {ilk}–{son}")
    if seyrek:
        print(f"  (kapsam dışı bırakılan seyrek yıllar: "
              f"{', '.join(map(str, seyrek))})")
    print(f"{len(satirlar)} gözlem, {len(olaylar)} bağımsız sis olayı "
          f"(TR07: <{OLAY_GORUS_M} m ≥{OLAY_SURE_SAAT} sa, içinde "
          f"<{SIS_GORUS_M} m ≥{SIS_SURE_SAAT} sa, kar yok)")
    print(f"Süreler 30 dakikalık ızgaraya YUVARLIDIR (SPECI yok).\n")

    sonuc = {}
    for baslik, fonk, anahtar in (
            (f"DÜŞME  {VMC_GORUS_M} m → {SVFR_GORUS_M} m", dusme_suresi, "dusme"),
            (f"TOPARLANMA  {SIS_GORUS_M} m → {VMC_GORUS_M} m",
             toparlanma_suresi, "toparlanma")):
        hepsi, yagisli, yagissiz = [], [], []
        sebepler = {}
        for o in olaylar:
            sure, durum = fonk(satirlar, o)
            if sure is None:
                sebepler[durum] = sebepler.get(durum, 0) + 1
                continue
            hepsi.append(sure)
            (yagisli if o["yagisli"] else yagissiz).append(sure)

        print(f"{baslik}  (saat)")
        print(f"  {'grup':<22}{'n':>5}{'%10':>9}{'%25':>8}{'medyan':>9}{'%75':>8}")
        _satir_yaz("tümü", ozet(hepsi))
        _satir_yaz("yağışlı", ozet(yagisli))
        _satir_yaz("yağışsız", ozet(yagissiz))
        if sebepler:
            print("  ölçülemeyen: " + ", ".join(
                f"{k}={v}" for k, v in sorted(sebepler.items())))
        print()
        sonuc[anahtar] = {"tumu": ozet(hepsi), "yagisli": ozet(yagisli),
                          "yagissiz": ozet(yagissiz), "olculemeyen": sebepler}

    sonuc["olay_sayisi"] = len(olaylar)
    sonuc["kapsam"] = {"ilk_yil": ilk, "son_yil": son, "seyrek_yillar": seyrek}
    if s.json:
        s.json.write_text(json.dumps(sonuc, ensure_ascii=False, indent=2),
                          encoding="utf-8")
        print(f"JSON yazıldı: {s.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
