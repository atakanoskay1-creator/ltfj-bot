#!/usr/bin/env python3
"""LTFJ sis IKLIMBILIMI: hangi ay, hangi saat, hangi ruzgarda.

Bu bir MODEL DEGIL, TARIHSEL SAYIM - gorus_gecis.py ile ayni cins.
Tahmin uretmiyor, sizinti kavrami gecerli degil, holdout'a dokunmuyor.

SIS TANIMI modelinkiyle AYNI (ozellik.py): gorus < 1000 m VE alani
kaplayan FG (MI/BC/PR/VC sayilmaz). Arsivdeki `sis` sutunu bu tanimla
uretildi; burada yeniden hesaplanmiyor.

SAATLER YEREL (UTC+3). Turkiye 2016'dan beri yaz saati uygulamiyor;
2011-2016 yazlarinda da yerel saat UTC+3'tu, yani sabit ofset tum
kapsam icin dogru.

RUZGAR SEKTORLERI: <=2 kt "sakin", VRB "degisken", digerleri 8 sektor.
"kat" = (sis sirasinda o sektorun payi) / (tum gozlemlerde payi). 1'in
ustu o ruzgarda sisin NORMALDEN SIK goruldugu anlamina gelir. Ham pay
tek basina yaniltir: LTFJ'de en sik ruzgar zaten KD, "sisin cogu KD'de"
bu yuzden kendiliginden dogru olur.

GUNEYLI SIS: 140-250 derece, >2 kt. Nadir ama en uzun ve en yogun
olaylar bunlar (bkz. README "Sis iklimbilimi"). Olay gruplamasi: ardisik
sisli gozlemler arasi <= 61 dk; olay, gozlemlerinin cogunlugu guneyli
ise "guneyli" sayilir.

SINIR: arsivde SPECI yok (30 dk izgara). Kisa ve keskin sisler EKSIK
sayiliyor olabilir - literaturdeki 5 Kasim 2015 vakasi (en dusuk 100 m)
bu arsivde 1100 m BCFG gorunuyor.

Kullanim:
    python -m sis_modeli.sis_iklim
    python -m sis_modeli.sis_iklim --dondur    # ltfj_sis_iklim_tablo.py
"""

import argparse
import collections
import csv
import gzip
import pprint
from datetime import datetime, timedelta
from pathlib import Path

from sis_modeli.gorus_gecis import ASGARI_YILLIK_KAYIT

VARSAYILAN_VERI = Path(__file__).resolve().parent / "veri" / "ltfj_ozellik.csv.gz"
DONDURULMUS_YOL = Path(__file__).resolve().parent.parent / "ltfj_sis_iklim_tablo.py"

YEREL_OFSET = timedelta(hours=3)
SAKIN_KT = 2
SEKTORLER = ("K", "KD", "D", "GD", "G", "GB", "B", "KB")
GUNEY_ARALIK = (140, 250)
OLAY_BOSLUK = timedelta(minutes=61)


def veri_oku(dosya: Path) -> list[dict]:
    with gzip.open(dosya, "rt", encoding="utf-8") as f:
        satirlar = []
        for x in csv.DictReader(f):
            satirlar.append({
                "yerel": datetime.fromisoformat(x["zaman"]) + YEREL_OFSET,
                "yil": int(x["zaman"][:4]),
                "yon": int(x["ruzgar_yon"]) if x["ruzgar_yon"] not in ("", "VRB") else None,
                "degisken": x["ruzgar_yon"] == "VRB",
                "hiz": int(x["ruzgar_hiz"]) if x["ruzgar_hiz"] else None,
                "sis": x["sis"] == "1",
                "lvo": x["lvo"] == "1",
            })
    return satirlar


def kapsama_indir(satirlar: list) -> tuple[list, int, int]:
    """Seyrek yillari (2003, 2010) cikarir - gorus_gecis ile ayni esik."""
    sayim = collections.Counter(s["yil"] for s in satirlar)
    dolu = sorted(y for y, n in sayim.items() if n >= ASGARI_YILLIK_KAYIT)
    if not dolu:
        return [], 0, 0
    return [s for s in satirlar if s["yil"] in dolu], dolu[0], dolu[-1]


def sektor(s: dict) -> str | None:
    if s["hiz"] is None:
        return None
    if s["hiz"] <= SAKIN_KT:
        return "sakin"
    if s["degisken"] or s["yon"] is None:
        return "degisken"
    return SEKTORLER[int(((s["yon"] + 22.5) % 360) // 45)]


def guneyli(s: dict) -> bool:
    return (s["yon"] is not None and s["hiz"] is not None and s["hiz"] > SAKIN_KT
            and GUNEY_ARALIK[0] <= s["yon"] <= GUNEY_ARALIK[1])


def olaylar(sisli: list) -> list[list]:
    """Ardisik sisli gozlemleri olaylara gruplar (zamana gore sirali girdi)."""
    sonuc = []
    for s in sisli:
        if sonuc and s["yerel"] - sonuc[-1][-1]["yerel"] <= OLAY_BOSLUK:
            sonuc[-1].append(s)
        else:
            sonuc.append([s])
    return sonuc


def olay_suresi_saat(olay: list) -> float:
    """Ilk ve son sisli gozlem arasi + bir izgara adimi (30 dk)."""
    return (olay[-1]["yerel"] - olay[0]["yerel"]).total_seconds() / 3600 + 0.5


def _medyan(d: list) -> float:
    d = sorted(d)
    return d[len(d) // 2] if d else 0.0


def hesapla(satirlar: list) -> dict:
    tum = sorted(satirlar, key=lambda s: s["yerel"])
    sisli = [s for s in tum if s["sis"]]
    if not sisli:
        return {"gozlem": len(tum), "sis_gozlem": 0}

    ay_tum = collections.Counter(s["yerel"].month for s in tum)
    ay_sis = collections.Counter(s["yerel"].month for s in sisli)
    ay_lvo = collections.Counter(s["yerel"].month for s in tum if s["lvo"])
    ay_gun = collections.Counter(d.month for d in {s["yerel"].date() for s in sisli})
    aylar = [{"ay": m, "sisli_gun": ay_gun[m], "lvo_gozlem": ay_lvo[m],
              "oran_yuzde": round(100 * ay_sis[m] / ay_tum[m], 2) if ay_tum[m] else 0.0,
              "pay_yuzde": round(100 * ay_sis[m] / len(sisli), 1)}
             for m in range(1, 13)]

    sa_tum = collections.Counter(s["yerel"].hour for s in tum)
    sa_sis = collections.Counter(s["yerel"].hour for s in sisli)
    saatler = [{"saat": h,
                "oran_yuzde": round(100 * sa_sis[h] / sa_tum[h], 2) if sa_tum[h] else 0.0,
                "pay_yuzde": round(100 * sa_sis[h] / len(sisli), 1)}
               for h in range(24)]

    sek_tum = collections.Counter(sektor(s) for s in tum)
    sek_sis = collections.Counter(sektor(s) for s in sisli)
    n_tum = sum(v for k, v in sek_tum.items() if k)
    n_sis = sum(v for k, v in sek_sis.items() if k)
    ruzgar = []
    for k in ("sakin",) + SEKTORLER:
        genel = sek_tum[k] / n_tum if n_tum else 0
        pay = sek_sis[k] / n_sis if n_sis else 0
        ruzgar.append({"sektor": k, "sis_pay_yuzde": round(100 * pay, 1),
                       "genel_pay_yuzde": round(100 * genel, 1),
                       "kat": round(pay / genel, 2) if genel else 0.0})
    hizlar = [s["hiz"] for s in sisli if s["hiz"] is not None]

    evler = olaylar(sisli)

    def _tip(e):
        return sum(guneyli(s) for s in e) * 2 > len(e)

    g_ev = [e for e in evler if _tip(e)]
    d_ev = [e for e in evler if not _tip(e)]
    g_goz = [s for s in sisli if guneyli(s)]
    d_goz = [s for s in sisli if not guneyli(s)]

    def _lvo(x):
        return round(100 * sum(s["lvo"] for s in x) / len(x)) if x else 0

    guney = {
        "sis_gozlem": len(g_goz),
        "pay_yuzde": round(100 * len(g_goz) / len(sisli), 1),
        "sisli_gun": len({s["yerel"].date() for s in g_goz}),
        "aylar": sorted({s["yerel"].month for s in g_goz}),
        "olay": len(g_ev),
        "sure_medyan_sa": _medyan([olay_suresi_saat(e) for e in g_ev]),
        "lvo_yuzde": _lvo(g_goz),
    }
    diger = {
        "olay": len(d_ev),
        "sure_medyan_sa": _medyan([olay_suresi_saat(e) for e in d_ev]),
        "lvo_yuzde": _lvo(d_goz),
    }
    return {
        "gozlem": len(tum),
        "sis_gozlem": len(sisli),
        "lvo_gozlem": sum(s["lvo"] for s in tum),
        "aylar": aylar,
        "saatler": saatler,
        "ruzgar": ruzgar,
        "hiz_medyan_kt": _medyan(hizlar),
        "hiz_5kt_alti_yuzde": round(100 * sum(h <= 5 for h in hizlar) / len(hizlar)) if hizlar else 0,
        "guney": guney,
        "diger": diger,
    }


def _bic(deger) -> str:
    return pprint.pformat(deger, width=88, sort_dicts=False)


def dondur(sonuc: dict, ilk: int, son: int, yol: Path = DONDURULMUS_YOL) -> None:
    yol.write_text(f'''#!/usr/bin/env python3
"""DONDURULMUS sis iklimbilimi - sis_modeli/sis_iklim.py uretti.

ELLE DUZENLEME. Yeniden uretmek icin:
    python -m sis_modeli.sis_iklim --dondur

Sayfa bu sayilari gosteriyor ama bot arsivi her kosuda okuyamaz -
ltfj_gorus_gecis_tablo ile ayni disiplin: SABIT tasir, hesap yapmaz.

Tanim ve sinirlar: sis_modeli/sis_iklim.py modul aciklamasi ve
sis_modeli/README.md "Sis iklimbilimi". Saatler YEREL (UTC+3).
"""

KAPSAM_ILK_YIL = {ilk}
KAPSAM_SON_YIL = {son}
GOZLEM = {sonuc["gozlem"]}
SIS_GOZLEM = {sonuc["sis_gozlem"]}
LVO_GOZLEM = {sonuc["lvo_gozlem"]}

# ay: sisli_gun = o ayda en az bir sisli gozlem olan gun sayisi (tum yillar),
# oran_yuzde = o ayin gozlemlerinin yuzde kaci sisli,
# pay_yuzde = tum sisli gozlemlerin yuzde kaci o ayda.
AYLAR = {_bic(sonuc["aylar"])}

SAATLER = {_bic(sonuc["saatler"])}

# kat = sis sirasindaki pay / genel pay (1'in ustu: o ruzgarda sis normalden sik)
RUZGAR = {_bic(sonuc["ruzgar"])}
HIZ_MEDYAN_KT = {sonuc["hiz_medyan_kt"]}
HIZ_5KT_ALTI_YUZDE = {sonuc["hiz_5kt_alti_yuzde"]}

# Guneyli (140-250 derece) sis ve digerleri - olay suresi ve LVO orani
GUNEY = {_bic(sonuc["guney"])}
DIGER = {_bic(sonuc["diger"])}
''', encoding="utf-8")
    print(f"donduruldu: {yol.name}")


def _yaz(sonuc: dict, ilk: int, son: int) -> None:
    print(f"LTFJ sis iklimbilimi — {ilk}–{son}, {sonuc['gozlem']} gözlem, "
          f"{sonuc['sis_gozlem']} sisli, {sonuc['lvo_gozlem']} LVO\n")
    print("ay  sisli-gün  oran%  pay%  lvo")
    for a in sonuc["aylar"]:
        print(f"{a['ay']:2d} {a['sisli_gun']:8d} {a['oran_yuzde']:6.2f} "
              f"{a['pay_yuzde']:5.1f} {a['lvo_gozlem']:4d}")
    print("\nsaat(yerel)  oran%  pay%")
    for s in sonuc["saatler"]:
        print(f"{s['saat']:02d} {s['oran_yuzde']:6.2f} {s['pay_yuzde']:5.1f}")
    print("\nsektör  sis-payı%  genel%  kat")
    for r in sonuc["ruzgar"]:
        print(f"{r['sektor']:7s} {r['sis_pay_yuzde']:6.1f} {r['genel_pay_yuzde']:7.1f} "
              f"{r['kat']:5.2f}")
    print(f"\nsis sırasında hız medyanı {sonuc['hiz_medyan_kt']} kt, "
          f"≤5 kt %{sonuc['hiz_5kt_alti_yuzde']}")
    print(f"güneyli: {sonuc['guney']}\ndiğer:   {sonuc['diger']}")


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    a.add_argument("--dondur", action="store_true",
                   help="sonuçları ltfj_sis_iklim_tablo.py'ye DONDUR")
    s = a.parse_args(argv)
    if not s.veri.exists():
        import sys
        print(f"HATA: {s.veri} yok.", file=sys.stderr)
        return 1
    satirlar, ilk, son = kapsama_indir(veri_oku(s.veri))
    sonuc = hesapla(satirlar)
    _yaz(sonuc, ilk, son)
    if s.dondur:
        dondur(sonuc, ilk, son)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
