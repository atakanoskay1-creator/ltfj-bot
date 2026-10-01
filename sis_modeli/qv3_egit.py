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
    python -m sis_modeli.qv3_egit
"""

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


def fold_calistir(egitim: list, test: list) -> dict:
    secim = qv3_model.ileri_secim(egitim)
    alanlar = secim["secilen"] or list(qv3_model.MODEL_A_ALANLARI)
    beta, tablolar, l2 = qv3_model.egit(egitim, alanlar)
    beta_a, tablolar_a, l2_a = qv3_model.egit(egitim, qv3_model.MODEL_A_ALANLARI)
    iklim = model.iklim_baseline(egitim)
    g_iklim = gorus_iklimi(egitim)
    return {
        "secim": secim, "l2": l2, "l2_a": l2_a,
        "gercek": [bool(r["hedef"]) for r in test],
        "tahmin": {
            "QV3": [qv3_model.olasilik(beta, r, tablolar) for r in test],
            "Model A seti": [qv3_model.olasilik(beta_a, r, tablolar_a) for r in test],
            "görüş bandı iklimi": [gorus_iklimi_tahmin(g_iklim, r) for r in test],
            "ay×saat iklimi": [model.iklim_tahmin(iklim, r) for r in test],
        },
    }


def main() -> int:
    aday = qv3_model.aday_ekle(qv3_hedef.veri_hazirla(veri_oku(VARSAYILAN_VERI),
                                                      qv3_hedef.rvr_oku()))
    gelistirme = bolme.gelistirme(aday)
    print(f"Geliştirme evreni (2012-2023, holdout kapalı): {len(gelistirme)} an, "
          f"{sum(r['hedef'] for r in gelistirme)} pozitif\n")

    birikmis = {"gercek": [], "tahmin": {}}
    secim_sayaci = Counter()
    for egitim_yillari, test_yillari in bolme.foldlar():
        egitim = bolme.ayir(gelistirme, egitim_yillari)
        test = bolme.ayir(gelistirme, test_yillari)
        f = fold_calistir(egitim, test)
        secim_sayaci.update(f["secim"]["secilen"])
        print(f"=== Test {test_yillari[0]}-{test_yillari[-1]} "
              f"(eğitim {min(r['dt'].year for r in egitim)}-{egitim_yillari[-1]}), "
              f"{sum(f['gercek'])} pozitif")
        print("  IV (iç eğitim, ilk 10): " + ", ".join(
            f"{a} {v:.2f}" for a, v in f["secim"]["iv"][:10]))
        print("  ileri seçim: " + " -> ".join(f"{a} ({ap:.3f})" for a, ap in f["secim"]["adimlar"])
              + f"   [L2 QV3 {f['l2']:g}, Model A seti {f['l2_a']:g}]")
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
    print("\nSeçilme sıklığı (fold sayısı): " + ", ".join(
        f"{a} {n}" for a, n in secim_sayaci.most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
