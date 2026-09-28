#!/usr/bin/env python3
"""Sis modeli V2 - ambargolu V1 referans benchmark'i (V2_PROTOKOL.md §5-§7.1, §9).

Hedefin teknik adi: LTFJ dusuk gorus/FG olayi.

BU BETIK V2 EGITMEZ. Yalnizca V1 referansini (egit.ALANLAR: gorus, spread,
spread_egilim_3, saat, ruzgar_kuzey; WoE + L2 lojistik) protokol 1.0'in
prosedurleriyle HER DIS FOLD ICINDE YENIDEN egitir. Canlidaki dondurulmus V1
katsayilari kullanilmaz; eski AP 0,210 / BSS 0,118 yalnizca tarihsel sonuctur.

Prosedur (protokolden birebir):
  - Evren: v2_evren.gelistirme_kayitlari (yalniz :20/:50, §3 / B10) ->
    hedef.onset_adaylari.
  - Dis fold'lar (§5): test 2017-18, 2019-20, 2021-22, 2023-24, 2025-26
    (birincil); 2015-16 yalnizca erken donem tanilamasi. Egitim = 2011 ..
    test baslangicindan onceki yil (genisleyen), sinirdan onceki son 3 saat
    cikarilir (bolme.embargo_penceresi).
  - L2 (§6): izgara model.L2_ADAYLARI. Ic bloklar = dis egitim doneminde en
    az 3 yil egitimden sonra gelen her takvim yili (2014 ..). Blok icin ic
    egitim = o yildan onceki butun yillar (ambargolu). WoE tablolari ic
    egitimden kurulur. Olcut = butun ic bloklarin HAVUZLANMIS log-loss'u.
    En iyiye <= 1e-4 nat uzakliktaki L2'ler esit; en BUYUGU secilir.
    Herhangi bir blokta TekilSistem/Yakinsamadi veren L2 o fold icin elenir.
    Secilen L2 ile dis egitimin tamami yakinsamazsa spesifikasyon basarisiz.
  - Test olcutleri: log-loss (dogal log), Brier, AP, LSS (referans: YALNIZCA
    o fold'un ambargolu egitim satirlarindan kurulan ay x saat iklimi,
    model.iklim_baseline). Havuzlanmis sonuc = bes fold'un out-of-sample
    tahminlerinin BIRLESIMI (fold ortalamasi degil).
  - Ayrica, V1 yeniden egitilmeden, ayni OOS tahminlerin kesitleri: onceden
    bildirilmis 6/6 tam ufuk tanilamasi (Deney 0 raporu §7.2) ve SN
    tanilamalari (§9.3). Olay duzeyi: §9.1 yakalama tanimi, bant esigi
    dondurulmus V1 taban oraninin 5 kati. Bunlar karar vermez.

Kullanim:
    python -m sis_modeli.v1_benchmark > rapor.md
"""

import argparse
import math
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path

import ltfj_sis_olasilik as sis_olasilik

from sis_modeli import bolme, degerlendir, egit, hedef, model, v2_evren
from sis_modeli.deney0_veri_denetimi import olay_ata, sn_var, ufuk_slotlari
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku
from sis_modeli.olay_degerlendirme import bagimsiz_olaylar

ALANLAR = list(egit.ALANLAR)
BIRINCIL_FOLDLAR = ((2017, 2018), (2019, 2020), (2021, 2022), (2023, 2024), (2025, 2026))
TANILAMA_FOLDLARI = ((2015, 2016),)
IC_BLOK_ASGARI_YIL = 3                      # §6: en az 3 yil egitimden sonra
ESITLIK_TOLERANSI = 1e-4                    # §6: nat
EPS = 1e-9                                  # degerlendir.log_loss ile ayni
BANT_ESIGI = 5 * sis_olasilik.EGITIM_POZITIF / sis_olasilik.EGITIM_AN_SAYISI   # §9.1
ONCESI_SAAT = 3                             # §9.1


class SpesifikasyonBasarisiz(Exception):
    """§6: hic gecerli L2 yok ya da secilen L2 ile nihai egitim yakinsamadi."""


# ------------------------------------------------------------ prosedur ---
def ic_bloklar(test_bas: int) -> list:
    return list(range(bolme.ILK_YIL + IC_BLOK_ASGARI_YIL, test_bas))


def l2_sec(havuz_ll: dict, tolerans: float = ESITLIK_TOLERANSI):
    """havuz_ll: {l2: havuzlanmis LL ya da None (elendi)} -> secilen l2.
    En iyiye <= tolerans uzaklikta olanlar esit; en buyugu secilir."""
    gecerli = {l2: ll for l2, ll in havuz_ll.items() if ll is not None}
    if not gecerli:
        raise SpesifikasyonBasarisiz("hicbir L2 butun ic bloklarda yakinsamadi")
    en_iyi = min(gecerli.values())
    return max(l2 for l2, ll in gecerli.items() if ll - en_iyi <= tolerans)


def _ll_toplam(tahmin: list, gercek: list) -> float:
    t = 0.0
    for p, y in zip(tahmin, gercek):
        p = min(max(p, EPS), 1 - EPS)
        t += -math.log(p) if y else -math.log(1 - p)
    return t


def _egit(egitim: list, l2: float):
    tablolar = model.woe_tablolari(egitim, ALANLAR)
    d, t, p = model.desenlere_topla(egitim, tablolar)
    return model.egit(d, t, p, l2=l2), tablolar


def ic_dogrulama(E: list, test_bas: int, adaylar=model.L2_ADAYLARI) -> dict:
    """§6 ic dogrulama. E: dis fold'un ambargolu egitim satirlari."""
    bloklar = []
    ll_top = {l2: 0.0 for l2 in adaylar}
    n_top = 0
    elenen = {}
    for y in ic_bloklar(test_bas):
        ic_eg = bolme.embargo_penceresi([r for r in E if r["dt"].year < y], y)
        ic_val = [r for r in E if r["dt"].year == y]
        tablolar = model.woe_tablolari(ic_eg, ALANLAR)
        d, t, p = model.desenlere_topla(ic_eg, tablolar)
        gercek = [bool(r["hedef"]) for r in ic_val]
        bloklar.append({"yil": y, "ic_egitim": len(ic_eg),
                        "ic_egitim_poz": sum(1 for r in ic_eg if r["hedef"]),
                        "dogrulama": len(ic_val), "dogrulama_poz": sum(gercek)})
        n_top += len(ic_val)
        for l2 in adaylar:
            if l2 in elenen:
                continue
            try:
                beta = model.egit(d, t, p, l2=l2)
            except (model.TekilSistem, model.Yakinsamadi) as e:
                elenen[l2] = f"{y}: {type(e).__name__}"
                continue
            ll_top[l2] += _ll_toplam([model.olasilik(beta, r, tablolar) for r in ic_val], gercek)
    havuz = {l2: (None if l2 in elenen else ll_top[l2] / n_top) for l2 in adaylar}
    return {"bloklar": bloklar, "havuz_ll": havuz, "elenen": elenen,
            "secilen": l2_sec(havuz)}


def olcutler(tahmin: list, gercek: list, iklim: list) -> dict:
    n = len(gercek)
    ll = degerlendir.log_loss(tahmin, gercek)
    ll_ik = degerlendir.log_loss(iklim, gercek)
    return {"n": n, "poz": sum(1 for y in gercek if y),
            "ll": ll, "ll_iklim": ll_ik,
            "lss": 1 - ll / ll_ik if ll_ik > 0 else None,
            "brier": degerlendir.brier(tahmin, gercek),
            "ap": degerlendir.ortalama_kesinlik(tahmin, gercek),
            "ort_tahmin": sum(tahmin) / n if n else None}


def olay_yakalama(olaylar: list, tahmin_zamani: dict, esik: float = BANT_ESIGI) -> list:
    """§9.1: olay, baslangicindan onceki 3 saatteki onset satirlarindan
    birinde tahmin >= esik ise yakalanmis. Doner: her olay icin
    {'baslangic', 'satir', 'yakalandi', 'sure_dk'} (satir = penceredeki
    OOS tahmin sayisi; 0 ise olay degerlendirilemez)."""
    zamanlar = sorted(tahmin_zamani)
    import bisect
    sonuc = []
    for o in olaylar:
        bas = o["baslangic"]
        i = bisect.bisect_left(zamanlar, bas - timedelta(hours=ONCESI_SAAT))
        j = bisect.bisect_left(zamanlar, bas)
        pencere = zamanlar[i:j]
        alarmlar = [t for t in pencere if tahmin_zamani[t] >= esik]
        sonuc.append({"baslangic": bas, "satir": len(pencere),
                      "yakalandi": bool(alarmlar),
                      "sure_dk": (bas - alarmlar[0]).total_seconds() / 60 if alarmlar else 0.0})
    return sonuc


def fold_calistir(kayitlar: list, onset: list, test_yillari: tuple) -> dict:
    test_bas = test_yillari[0]
    ham_egitim = [r for r in onset if bolme.ILK_YIL <= r["dt"].year < test_bas]
    E = bolme.ayir_embargolu(onset, tuple(range(bolme.ILK_YIL, test_bas)), test_bas)
    T = [r for r in onset if r["dt"].year in test_yillari]
    egitim_tam = [r for r in kayitlar if bolme.ILK_YIL <= r["dt"].year < test_bas]
    test_tam = [r for r in kayitlar if r["dt"].year in test_yillari]

    sonuc = {"fold": test_yillari, "egitim_ham": len(ham_egitim), "egitim": len(E),
             "egitim_poz": sum(1 for r in E if r["hedef"]),
             "embargo_cikan": len(ham_egitim) - len(E),
             "embargo_cikan_poz": sum(1 for r in ham_egitim if r["hedef"])
             - sum(1 for r in E if r["hedef"]),
             "egitim_olay": len(bagimsiz_olaylar(egitim_tam, etiket="sis", bosluk_saat=3.0)),
             "test": len(T), "test_poz": sum(1 for r in T if r["hedef"]),
             "test_olaylar": bagimsiz_olaylar(test_tam, etiket="sis", bosluk_saat=3.0),
             "test_satirlar": T}
    ic = ic_dogrulama(E, test_bas)
    sonuc["ic"] = ic
    try:
        beta, tablolar = _egit(E, ic["secilen"])
    except (model.TekilSistem, model.Yakinsamadi) as e:
        raise SpesifikasyonBasarisiz(f"{test_yillari}: nihai egitim: {e}") from e
    sonuc["katsayilar"] = beta
    sonuc["tablolar"] = tablolar
    iklim = model.iklim_baseline(E)
    sonuc["tahmin"] = [model.olasilik(beta, r, tablolar) for r in T]
    sonuc["iklim"] = [model.iklim_tahmin(iklim, r) for r in T]
    sonuc["gercek"] = [bool(r["hedef"]) for r in T]
    return sonuc


# -------------------------------------------------------------- rapor ---
def _t(basliklar, satirlar) -> str:
    c = ["| " + " | ".join(basliklar) + " |",
         "|" + "|".join("---:" if i else "---" for i in range(len(basliklar))) + "|"]
    c += ["| " + " | ".join(str(x) for x in s) + " |" for s in satirlar]
    return "\n".join(c)


def _o(x, b=4):
    return "—" if x is None else f"{x:.{b}f}"


def _l2(x):
    return f"{x:g}"


def _fold_ad(f):
    return f"{f[0]}–{str(f[1])[2:]}"


def olcut_satiri(ad, m):
    return [ad, m["n"], m["poz"], _o(m["ll"], 5), _o(m["ll_iklim"], 5), _o(m["lss"]),
            f"{1e4 * m['brier']:.2f}", _o(m["ap"], 3),
            f"{100 * m['poz'] / m['n']:.3f}" if m["n"] else "—",
            _o(100 * m["ort_tahmin"], 3) if m["ort_tahmin"] is not None else "—"]


OLCUT_BASLIK = ["kesit", "satır", "Y=1", "LL (nat)", "LL iklim", "LSS", "Brier×10⁴",
                "AP", "taban %", "ort. tahmin %"]


def kesit(sonuclar: list, secici) -> dict:
    p, y, ik = [], [], []
    for s in sonuclar:
        for r, pp, yy, ii in zip(s["test_satirlar"], s["tahmin"], s["gercek"], s["iklim"]):
            if secici(r):
                p.append(pp)
                y.append(yy)
                ik.append(ii)
    return olcutler(p, y, ik)


def yakalama_ozeti(kayitlar_olay: list, yakalama: list) -> list:
    deg = [x for x in yakalama if x["satir"]]
    if not deg:
        return [len(yakalama), 0, 0, "—", "—"]
    yak = sum(1 for x in deg if x["yakalandi"])
    sureler = sorted(x["sure_dk"] for x in deg)
    return [len(yakalama), len(yakalama) - len(deg), len(deg),
            f"{yak} (%{100 * yak / len(deg):.1f})", f"{sureler[len(sureler) // 2]:.0f}"]


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    s = a.parse_args(argv)
    if not s.veri.exists():
        print(f"HATA: {s.veri} yok.", file=sys.stderr)
        return 1

    kayitlar = v2_evren.gelistirme_kayitlari(veri_oku(s.veri))
    onset = hedef.onset_adaylari(kayitlar)
    yer = {r["dt"]: i for i, r in enumerate(kayitlar)}
    tam_ufuk = {r["dt"] for r in onset if len(ufuk_slotlari(yer, r["dt"])) == hedef.ADIM_SAYISI}
    pencere_sn = {r["dt"] for r in onset
                  if any(sn_var(kayitlar[j]) for j in ufuk_slotlari(yer, r["dt"]))}

    print("# V1 referans benchmark'ı (çıktı)\n")
    print(f"Evren: `v2_evren.gelistirme_kayitlari` — {len(kayitlar)} ızgara satırı, "
          f"{len(onset)} onset satırı, {sum(1 for r in onset if r['hedef'])} Y=1. "
          f"Değişkenler: {', '.join(ALANLAR)}. L2 ızgarası: "
          f"{', '.join(_l2(x) for x in model.L2_ADAYLARI)}. Eşitlik toleransı "
          f"{ESITLIK_TOLERANSI:g} nat. V2 eğitilmedi.\n")

    sonuclar, tanilama = [], []
    for grup, liste in ((BIRINCIL_FOLDLAR, sonuclar), (TANILAMA_FOLDLARI, tanilama)):
        for f in grup:
            liste.append(fold_calistir(kayitlar, onset, f))
    hepsi = sonuclar + tanilama

    print("## 1. Fold sayımları (ambargo sonrası gerçek eğitim)\n")
    rows = []
    for x in hepsi:
        rows.append([_fold_ad(x["fold"]) + ("" if x in sonuclar else " (tanılama)"),
                     f"{bolme.ILK_YIL}–{x['fold'][0] - 1}", x["egitim_ham"], x["embargo_cikan"],
                     x["embargo_cikan_poz"], x["egitim"], x["egitim_poz"], x["egitim_olay"],
                     x["test"], x["test_poz"], len(x["test_olaylar"])])
    print(_t(["dış fold (test)", "eğitim yılları", "eğitim (ambargo öncesi)",
              "ambargo çıkan", "ambargo çıkan Y=1", "eğitim (gerçek)", "eğitim Y=1",
              "eğitim olayı", "test", "test Y=1", "test olayı"], rows))
    print("\nOlay sayıları §5.1 bölütlemesiyle, ilgili dönemin tam (onset filtresiz) "
          "ızgara kaydından. Eğitim olayı ambargo öncesi eğitim yıllarından.\n")

    print("## 2. İç içe zaman bölmeli L2 seçimi (§6)\n")
    for x in hepsi:
        ic = x["ic"]
        print(f"### {_fold_ad(x['fold'])}{'' if x in sonuclar else ' (tanılama)'}\n")
        print("İç bloklar: " + "; ".join(
            f"{b['yil']} (iç eğitim {b['ic_egitim']} / Y=1 {b['ic_egitim_poz']}, "
            f"doğrulama {b['dogrulama']} / Y=1 {b['dogrulama_poz']})" for b in ic["bloklar"]) + "\n")
        en_iyi = min(v for v in ic["havuz_ll"].values() if v is not None)
        rows = []
        for l2 in model.L2_ADAYLARI:
            v = ic["havuz_ll"][l2]
            rows.append([_l2(l2), _o(v, 6) if v is not None else "elendi",
                         "—" if v is None else f"{v - en_iyi:.2e}",
                         ic["elenen"].get(l2, ""),
                         "**seçildi**" if l2 == ic["secilen"] else ""])
        print(_t(["λ", "havuzlanmış iç LL (nat)", "en iyiden fark", "eleme nedeni", ""], rows))
        print()

    print("## 3. Test sonuçları — birincil tam onset evreni\n")
    rows = [olcut_satiri(_fold_ad(x["fold"]) + f" (λ={_l2(x['ic']['secilen'])})",
                         olcutler(x["tahmin"], x["gercek"], x["iklim"])) for x in sonuclar]
    rows.append(olcut_satiri("**havuzlanmış (5 fold OOS birleşimi)**",
                             kesit(sonuclar, lambda r: True)))
    print(_t(OLCUT_BASLIK, rows))
    print("\nLSS = 1 − LL(V1) / LL(iklim); iklim = her fold'un yalnızca kendi ambargolu "
          "eğitim satırlarından kurulan ay × saat taban oranı (`model.iklim_baseline`). "
          "Havuzlanmış LSS = 1 − ΣLL(V1)/ΣLL(iklim), yani birleşik tahminlerden.\n")
    for x in tanilama:
        print("Erken dönem tanılaması (birincil karara girmez):\n")
        print(_t(OLCUT_BASLIK, [olcut_satiri(_fold_ad(x["fold"]) + f" (λ={_l2(x['ic']['secilen'])})",
                                             olcutler(x["tahmin"], x["gercek"], x["iklim"]))]))
        print()

    print("## 4. Katsayılar (fold başına, V1 referansı)\n")
    adlar = ["sabit"] + sorted(ALANLAR)
    for x in hepsi:
        if sorted(x["tablolar"]) != sorted(ALANLAR):     # bos WoE tablosu -> degisken dusmus
            print(f"UYARI {_fold_ad(x['fold'])}: WoE tablosu olan degiskenler "
                  f"{sorted(x['tablolar'])}\n")
    rows = [[_fold_ad(x["fold"]), _l2(x["ic"]["secilen"])] + [f"{b:.3f}" for b in x["katsayilar"]]
            for x in hepsi]
    print(_t(["fold", "λ"] + adlar, rows))
    print("\nWoE kova sayısı: " + "; ".join(
        f"{_fold_ad(x['fold'])}: " + ", ".join(f"{k} {len(v)}" for k, v in sorted(x["tablolar"].items()))
        for x in hepsi) + "\n")

    print("## 5. Önceden bildirilmiş tanılama — ufku tam (6/6) satırlar (karar vermez)\n")
    print("Aynı OOS tahminler; V1 yeniden eğitilmedi. Seçim Y'ye bakılmadan, yalnız ufuk "
          "tamlığına göre (Deney 0 raporu §7.2).\n")
    rows = []
    for x in sonuclar:
        rows.append(olcut_satiri(_fold_ad(x["fold"]), kesit([x], lambda r: r["dt"] in tam_ufuk)))
    rows.append(olcut_satiri("**havuzlanmış 6/6**", kesit(sonuclar, lambda r: r["dt"] in tam_ufuk)))
    rows.append(olcut_satiri("havuzlanmış, ufku eksik (tümleyen)",
                             kesit(sonuclar, lambda r: r["dt"] not in tam_ufuk)))
    print(_t(OLCUT_BASLIK, rows))
    print(f"\nTüm geliştirme evreninde 6/6 onset satırı: {len(tam_ufuk)}.\n")

    print("## 6. SN tanılamaları (§9.3; karar vermez)\n")
    print("Satır düzeyi: hedef penceresinde (t, t+3sa] hiç SN gözlemi olmayan / olan satırlar.\n")
    rows = [olcut_satiri("penceresinde SN yok", kesit(sonuclar, lambda r: r["dt"] not in pencere_sn)),
            olcut_satiri("penceresinde SN var", kesit(sonuclar, lambda r: r["dt"] in pencere_sn))]
    print(_t(OLCUT_BASLIK, rows))

    print(f"\nOlay düzeyi (§9.1 yakalama tanımı; bant eşiği = 5 × dondurulmuş V1 taban oranı "
          f"= {100 * BANT_ESIGI:.3f}%; ilk alarm süresi yakalanmayan olayda 0 dk). Olaylar "
          "her fold'un test döneminde bölütlendi; penceresinde hiç OOS tahmin satırı olmayan "
          "olay değerlendirilemez ve ayrı sayılır.\n")
    rows = []
    tum_yak, tum_olay, tum_sn = [], [], []
    for x in sonuclar:
        tz = {r["dt"]: p for r, p in zip(x["test_satirlar"], x["tahmin"])}
        yak = olay_yakalama(x["test_olaylar"], tz)
        test_tam = [r for r in kayitlar if r["dt"].year in x["fold"]]
        sn_bayrak = [False] * len(x["test_olaylar"])
        for r in test_tam:
            if r["sis"] and sn_var(r):
                i = olay_ata(x["test_olaylar"], r["dt"])
                if i is not None:
                    sn_bayrak[i] = True
        tum_yak += yak
        tum_olay += x["test_olaylar"]
        tum_sn += sn_bayrak
        rows.append([_fold_ad(x["fold"]), "tümü"] + yakalama_ozeti(x["test_olaylar"], yak))
    for ad, sec in (("tümü", lambda i: True), ("≥ 1 SN", lambda i: tum_sn[i]),
                    ("SN'siz", lambda i: not tum_sn[i])):
        idx = [i for i in range(len(tum_olay)) if sec(i)]
        rows.append(["**havuzlanmış**", ad] + yakalama_ozeti([tum_olay[i] for i in idx],
                                                            [tum_yak[i] for i in idx]))
    print(_t(["fold", "olay grubu", "olay", "değerlendirilemez", "değerlendirilen",
              "yakalanan", "medyan ilk alarm (dk)"], rows))

    print("\n## 7. Güvenilirlik (havuzlanmış OOS, tanılama)\n")
    p = [pp for x in sonuclar for pp in x["tahmin"]]
    y = [yy for x in sonuclar for yy in x["gercek"]]
    rows = [[f"{k['kova'] / 10:.1f}–{(k['kova'] + 1) / 10:.1f}", k["n"],
             f"{100 * k['ortalama_tahmin']:.3f}", f"{100 * k['gerceklesen']:.3f}", k["pozitif"]]
            for k in degerlendir.guvenilirlik(p, y)]
    print(_t(["tahmin kovası", "satır", "ort. tahmin %", "gerçekleşen %", "Y=1"], rows))
    ince = Counter()
    for pp, yy in zip(p, y):
        k = next(i for i, e in enumerate((0.005, 0.01, 0.02, 0.05, 0.1, 1.01)) if pp < e)
        ince[(k, "n")] += 1
        ince[(k, "p")] += yy
        ince[(k, "s")] += pp
    etiket = ["< 0,5", "0,5–1", "1–2", "2–5", "5–10", "≥ 10"]
    print("\nDüşük olasılık bölgesi (tahmin %):\n")
    print(_t(["tahmin %", "satır", "ort. tahmin %", "gerçekleşen %", "Y=1"],
             [[etiket[k], ince[(k, "n")], f"{100 * ince[(k, 's')] / ince[(k, 'n')]:.3f}",
               f"{100 * ince[(k, 'p')] / ince[(k, 'n')]:.3f}", ince[(k, "p")]]
              for k in range(6) if ince[(k, "n")]]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
