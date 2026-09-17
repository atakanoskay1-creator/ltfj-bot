#!/usr/bin/env python3
"""Yuruyen pencere (walk-forward) egitim ve degerlendirme.

Her fold'da model YALNIZCA kendi gecmisiyle egitilir - WoE kova sinirlari
dahil. Test donemi hicbir sekilde egitime karismaz.

NIHAI HOLDOUT (2024-2026) bu betikte ACILMAZ; model dondurulduktan sonra
ayrica degerlendirilir (bkz. sis_modeli/bolme.py).

Kullanim:
    python -m sis_modeli.egit
"""

import argparse
import sys
from pathlib import Path

from sis_modeli import bolme, degerlendir, hedef, model
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku

# Tarama sonucuna gore secilen degiskenler (bkz. PR #30):
#   - ruzgar_hiz (IV 0.09) ve qnh_egilim_3 (0.03) ELENDI - bilgi tasimiyor
#   - tavan (PSI 0.24) ve ruzgar_dogu (PSI 0.23) donemler arasi KAYIYOR,
#     bu yuzden disarida birakildi; kararlilik onceligi
#   - gorus tutuldu: IV'si ufukla eriyor (sureklilik) ama yine de bilgi tasiyor
ALANLAR = ["spread", "spread_egilim_3", "saat", "ruzgar_kuzey", "gorus", "ay"]


def _fold_calistir(egitim: list, test: list) -> dict:
    # L2 fold'un KENDI egitim verisi icinde secilir - walk-forward sonucuna
    # bakarak secmek degerlendirme setine ayar yapmak olurdu.
    katsayilar, tablolar, l2 = model.egit_secerek(egitim, ALANLAR)

    iklim = model.iklim_baseline(egitim)
    gercek = [bool(r["hedef"]) for r in test]
    tahmin = {
        "model": [model.olasilik(katsayilar, r, tablolar) for r in test],
        "iklim": [model.iklim_tahmin(iklim, r) for r in test],
        "süreklilik": [model.sureklilik_baseline(r) for r in test],
        "basit kural": [model.basit_kural_baseline(r) for r in test],
    }
    return {"gercek": gercek, "tahmin": tahmin, "katsayilar": katsayilar,
            "tablolar": tablolar, "test": test, "l2": l2}


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    secenek = a.parse_args(argv)
    if not secenek.veri.exists():
        print(f"HATA: {secenek.veri} yok.", file=sys.stderr)
        return 1

    ham = [r for r in veri_oku(secenek.veri) if r["zaman"][:4] >= str(bolme.ILK_YIL)]
    kayitlar = hedef.hazirla(ham)
    aday = hedef.onset_adaylari(kayitlar)
    gelistirme = bolme.gelistirme(aday)

    print(f"Onset evreni (holdout hariç): {len(gelistirme)} an, "
          f"{sum(r['hedef'] for r in gelistirme)} pozitif")
    print(f"Değişkenler: {', '.join(ALANLAR)}\n")

    birikmis = {"gercek": [], "test": []}
    birikmis_tahmin = {k: [] for k in ("model", "iklim", "süreklilik", "basit kural")}

    print(f"{'fold (test yılı)':<20}{'n':>8}{'poz':>6}"
          f"{'Brier×10⁴':>11}{'BSS':>8}{'AP':>8}{'L2':>8}")
    for egitim_yillari, test_yillari in bolme.foldlar():
        egitim = bolme.ayir(gelistirme, egitim_yillari)
        test = bolme.ayir(gelistirme, test_yillari)
        if not test or not any(r["hedef"] for r in test):
            continue
        s = _fold_calistir(egitim, test)
        bss = degerlendir.brier_skill(s["tahmin"]["model"], s["gercek"],
                                      s["tahmin"]["iklim"])
        ap = degerlendir.ortalama_kesinlik(s["tahmin"]["model"], s["gercek"])
        etiket = "-".join(str(y) for y in (test_yillari[0], test_yillari[-1]))
        print(f"{etiket:<20}{len(test):>8}{sum(s['gercek']):>6}"
              f"{1e4*degerlendir.brier(s['tahmin']['model'], s['gercek']):>11.2f}"
              f"{bss:>8.3f}{ap:>8.3f}{s['l2']:>8.0f}")
        birikmis["gercek"].extend(s["gercek"])
        birikmis["test"].extend(s["test"])
        for k, v in s["tahmin"].items():
            birikmis_tahmin[k].extend(v)

    g = birikmis["gercek"]
    print(f"\n=== Tüm fold'lar birikmiş: {len(g)} an, {sum(g)} pozitif ===")
    print(f"{'yöntem':<16}{'Brier×10⁴':>11}{'BSS (iklime göre)':>20}{'AP':>8}")
    for ad, p in birikmis_tahmin.items():
        bss = degerlendir.brier_skill(p, g, birikmis_tahmin["iklim"])
        print(f"{ad:<16}{1e4*degerlendir.brier(p, g):>11.2f}{bss:>20.3f}"
              f"{degerlendir.ortalama_kesinlik(p, g):>8.3f}")

    alt, ust = degerlendir.blok_guven_araligi(
        birikmis["test"], birikmis_tahmin["model"], g,
        degerlendir.ortalama_kesinlik)
    print(f"\nModel AP %5–%95 (blok bootstrap): {alt:.3f} – {ust:.3f}")

    print("\n=== Güvenilirlik (model) ===")
    print(f"  {'kova':<10}{'n':>8}{'ort. tahmin':>13}{'gerçekleşen':>13}{'poz':>6}")
    for k in degerlendir.guvenilirlik(birikmis_tahmin["model"], g):
        print(f"  {k['kova']/10:.1f}-{(k['kova']+1)/10:.1f}   {k['n']:>8}"
              f"{100*k['ortalama_tahmin']:>12.2f}%{100*k['gerceklesen']:>12.2f}%"
              f"{k['pozitif']:>6}")

    print("\n=== Eşik tablosu (model) ===")
    print(f"  {'eşik':>6}{'alarm':>8}{'doğru':>7}{'yanlış':>8}{'kesinlik':>10}{'duyarlılık':>12}")
    for e in degerlendir.esik_tablosu(birikmis_tahmin["model"], g):
        print(f"  {100*e['esik']:>5.0f}%{e['alarm']:>8}{e['dogru']:>7}{e['yanlis']:>8}"
              f"{100*e['kesinlik']:>9.1f}%{100*e['duyarlilik']:>11.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
