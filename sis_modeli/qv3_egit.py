#!/usr/bin/env python3
"""QV3 walk-forward: LVO Hazirlik hedefinde veri-tabanli degisken secimi +
WoE lojistik model, Model A ile ayni fold'larda (2015-2023 testleri).

Her fold'da:
  - degisken secimi (qv3_model.ileri_secim) YALNIZCA o fold'un egitim
    yillariyla yapilir, test yillari secime karismaz;
  - secilen setle model egitilir (L2 egitimin son yilinda secilir);
  - karsilastirma: Model A'nin 5 degiskenli seti (ayni hedefte yeniden
    egitilir), ay x saat iklimi, mevcut gorus bandina gore kosullu iklim.
NIHAI HOLDOUT (2024-2026) ACILMAZ. Dosya yazmaz.

Kullanim (repo kokunden):
    python -m sis_modeli.qv3_egit              # ~3 dk
    python -m sis_modeli.qv3_egit --kararli    # + kararli secim denemesi
"""

import argparse
from collections import Counter

from sis_modeli import bolme, degerlendir, model, qv3_hedef, qv3_model
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku

GORUS_BANTLARI = (1000, 2000, 3000, 5000, 9999)


def gorus_bandi(gorus) -> int | None:
    if gorus is None:
        return None
    return next((i for i, esik in enumerate(GORUS_BANTLARI) if gorus < esik),
                len(GORUS_BANTLARI))


def gorus_iklimi(egitim: list) -> tuple:
    """Mevcut gorus bandina gore egitim taban orani (Laplace duzeltmeli).
    'Hava zaten kapali' sezgisinin olculmus hali - model bunu yenmeli."""
    top, poz = Counter(), Counter()
    for r in egitim:
        b = gorus_bandi(r.get("gorus"))
        top[b] += 1
        poz[b] += int(bool(r["hedef"]))
    genel = (sum(poz.values()) + 1) / (sum(top.values()) + 2)
    return {b: (poz[b] + 2 * genel) / (top[b] + 2) for b in top}, genel


def gorus_iklimi_tahmin(m, kayit) -> float:
    tablo, genel = m
    return tablo.get(gorus_bandi(kayit.get("gorus")), genel)


def olcutler(tahmin: list, gercek: list, iklim: list) -> dict:
    return {"AP": degerlendir.ortalama_kesinlik(tahmin, gercek),
            "AUC": degerlendir.roc_auc(tahmin, gercek),
            "Brier": degerlendir.brier(tahmin, gercek),
            "BSS": degerlendir.brier_skill(tahmin, gercek, iklim)}


def fold_calistir(egitim: list, test: list, kararli_dahil: bool = False) -> dict:
    secim = qv3_model.ileri_secim(egitim)
    alanlar = secim["secilen"] or list(qv3_model.MODEL_A_ALANLARI)
    beta, tablolar, l2 = qv3_model.egit(egitim, alanlar)
    secim_e = qv3_model.ileri_secim(egitim, qv3_model.ADAYLAR + qv3_model.ETKILESIM)
    alanlar_e = secim_e["secilen"] or list(qv3_model.MODEL_A_ALANLARI)
    beta_e, tablolar_e, l2_e = qv3_model.egit(egitim, alanlar_e)
    beta_a, tablolar_a, l2_a = qv3_model.egit(egitim, qv3_model.MODEL_A_ALANLARI)
    iklim = model.iklim_baseline(egitim)
    g_iklim = gorus_iklimi(egitim)
    sonuc = {
        "secim": secim, "secim_e": secim_e, "l2": l2, "l2_e": l2_e, "l2_a": l2_a,
        "gercek": [bool(r["hedef"]) for r in test],
        "tahmin": {
            "QV3": [qv3_model.olasilik(beta, r, tablolar) for r in test],
            "QV3 + etkileşim": [qv3_model.olasilik(beta_e, r, tablolar_e) for r in test],
            "Model A seti": [qv3_model.olasilik(beta_a, r, tablolar_a) for r in test],
            "görüş bandı iklimi": [gorus_iklimi_tahmin(g_iklim, r) for r in test],
            "ay×saat iklimi": [model.iklim_tahmin(iklim, r) for r in test],
        },
    }
    if kararli_dahil:
        kararli = qv3_model.kararli_secim(egitim)
        alanlar_k = kararli["secilen"] or list(qv3_model.MODEL_A_ALANLARI)
        beta_k, tablolar_k, sonuc["l2_k"] = qv3_model.egit(egitim, alanlar_k)
        sonuc["kararli"] = kararli
        sonuc["tahmin"]["QV3 kararlı"] = [qv3_model.olasilik(beta_k, r, tablolar_k)
                                          for r in test]
    return sonuc


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--kararli", action="store_true",
                   help="yil-disarida-birak kararli secimi de calistir (~6 dk ek)")
    secenek = a.parse_args(argv)
    aday = qv3_model.etkilesim_ekle(qv3_model.aday_ekle(qv3_hedef.veri_hazirla(
        veri_oku(VARSAYILAN_VERI), qv3_hedef.rvr_oku())))
    gelistirme = bolme.gelistirme(aday)
    print(f"Geliştirme evreni (2012-2023, holdout kapalı): {len(gelistirme)} an, "
          f"{sum(r['hedef'] for r in gelistirme)} pozitif\n")

    birikmis = {"gercek": [], "tahmin": {}}
    sayaclar = {"QV3": Counter(), "QV3 + etkileşim": Counter(), "QV3 kararlı": Counter()}
    for egitim_yillari, test_yillari in bolme.foldlar():
        egitim = bolme.ayir(gelistirme, egitim_yillari)
        test = bolme.ayir(gelistirme, test_yillari)
        f = fold_calistir(egitim, test, secenek.kararli)
        sayaclar["QV3"].update(f["secim"]["secilen"])
        sayaclar["QV3 + etkileşim"].update(f["secim_e"]["secilen"])
        print(f"=== Test {test_yillari[0]}-{test_yillari[-1]} "
              f"(eğitim {min(r['dt'].year for r in egitim)}-{egitim_yillari[-1]}), "
              f"{sum(f['gercek'])} pozitif")
        print("  IV (iç eğitim, ilk 10): " + ", ".join(
            f"{a} {v:.2f}" for a, v in f["secim"]["iv"][:10]))
        print("  ileri seçim: " + " -> ".join(f"{a} ({ap:.3f})" for a, ap in f["secim"]["adimlar"])
              + f"   [L2 QV3 {f['l2']:g}, Model A seti {f['l2_a']:g}]")
        print("  etkileşimli seçim: " + " -> ".join(
            f"{a} ({ap:.3f})" for a, ap in f["secim_e"]["adimlar"]) + f"   [L2 {f['l2_e']:g}]")
        if "kararli" in f:
            k = f["kararli"]
            sayaclar["QV3 kararlı"].update(k["secilen"])
            print(f"  kararlı seçim ({k['kosu']} koşu, eşik %{100 * qv3_model.KARARLILIK_ESIGI:.0f}): "
                  + ", ".join(k["secilen"]) + "   [sıklık: "
                  + ", ".join(f"{a} {o:.0%}" for a, o in k["siklik"].items())
                  + f"; L2 {f['l2_k']:g}]")
        iklim = f["tahmin"]["ay×saat iklimi"]
        for ad, t in f["tahmin"].items():
            o = olcutler(t, f["gercek"], iklim)
            print(f"  {ad:<20} AP {o['AP']:.3f}  AUC {o['AUC']:.3f}  "
                  f"Brier {o['Brier']:.5f}  BSS {o['BSS']:+.3f}")
            birikmis["tahmin"].setdefault(ad, []).extend(t)
        birikmis["gercek"].extend(f["gercek"])
        print()

    print(f"=== TOPLAM (2015-2023), {sum(birikmis['gercek'])} pozitif")
    iklim = birikmis["tahmin"]["ay×saat iklimi"]
    for ad, t in birikmis["tahmin"].items():
        o = olcutler(t, birikmis["gercek"], iklim)
        print(f"  {ad:<20} AP {o['AP']:.3f}  AUC {o['AUC']:.3f}  "
              f"Brier {o['Brier']:.5f}  BSS {o['BSS']:+.3f}")
    for ad, sayac in sayaclar.items():
        if sayac:
            print(f"Seçilme sıklığı, {ad} (fold sayısı): " + ", ".join(
                f"{a} {n}" for a, n in sayac.most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
