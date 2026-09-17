#!/usr/bin/env python3
"""NIHAI HOLDOUT degerlendirmesi - TEK ATIS.

Model gelistirme boyunca 2024-2026 verisine HIC bakilmadi. Bu betik
dondurulmus prosedurle (sis_modeli.egit.ALANLAR, model.L2_ADAYLARI) TUM
gelistirme donemini (2011-2023) egitip holdout uzerinde olcer.

KURAL: bu sonuc gorulduKTEN SONRA degisken seti, L2 izgarasi, esikler veya
metodoloji DEGISTIRILIRSE holdout gecerliligini yitirir. Ne cikarsa o
raporlanir.
"""

import sys
from pathlib import Path

from sis_modeli import bolme, degerlendir, hedef, model
from sis_modeli.egit import ALANLAR
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku


def main() -> int:
    ham = [r for r in veri_oku(VARSAYILAN_VERI) if r["zaman"][:4] >= str(bolme.ILK_YIL)]
    kayitlar = hedef.hazirla(ham)
    aday = hedef.onset_adaylari(kayitlar)

    egitim = bolme.gelistirme(aday)          # 2011-2023
    test = bolme.holdout(aday)               # 2024-2026 - ILK KEZ aciliyor
    if not test:
        print("HATA: holdout bos.", file=sys.stderr)
        return 1

    print(f"Eğitim (2011-2023): {len(egitim)} an, {sum(r['hedef'] for r in egitim)} pozitif")
    print(f"HOLDOUT (2024-2026): {len(test)} an, {sum(r['hedef'] for r in test)} pozitif "
          f"(taban oran %{100*sum(r['hedef'] for r in test)/len(test):.2f})")
    print(f"Değişkenler: {', '.join(ALANLAR)}\n")

    katsayilar, tablolar, l2 = model.egit_secerek(egitim, ALANLAR)
    iklim = model.iklim_baseline(egitim)
    gercek = [bool(r["hedef"]) for r in test]
    tahminler = {
        "model": [model.olasilik(katsayilar, r, tablolar) for r in test],
        "iklim": [model.iklim_tahmin(iklim, r) for r in test],
        "süreklilik": [model.sureklilik_baseline(r) for r in test],
        "basit kural": [model.basit_kural_baseline(r) for r in test],
    }

    print(f"Seçilen L2 (iç doğrulamayla): {l2:.0f}\n")
    print(f"{'yöntem':<16}{'Brier×10⁴':>11}{'BSS':>8}{'AP':>8}{'AP %5–%95':>18}")
    for ad, p in tahminler.items():
        bss = degerlendir.brier_skill(p, gercek, tahminler["iklim"])
        ap = degerlendir.ortalama_kesinlik(p, gercek)
        alt, ust = degerlendir.blok_guven_araligi(test, p, gercek,
                                                  degerlendir.ortalama_kesinlik)
        print(f"{ad:<16}{1e4*degerlendir.brier(p, gercek):>11.2f}{bss:>8.3f}{ap:>8.3f}"
              f"{f'{alt:.3f} – {ust:.3f}':>18}")

    print("\n=== Güvenilirlik (model) ===")
    print(f"  {'kova':<10}{'n':>8}{'ort. tahmin':>13}{'gerçekleşen':>13}{'poz':>6}")
    for k in degerlendir.guvenilirlik(tahminler["model"], gercek):
        print(f"  {k['kova']/10:.1f}-{(k['kova']+1)/10:.1f}   {k['n']:>8}"
              f"{100*k['ortalama_tahmin']:>12.2f}%{100*k['gerceklesen']:>12.2f}%{k['pozitif']:>6}")

    print("\n=== Eşik tablosu (model) ===")
    print(f"  {'eşik':>6}{'alarm':>8}{'doğru':>7}{'yanlış':>8}{'kesinlik':>10}{'duyarlılık':>12}")
    for e in degerlendir.esik_tablosu(tahminler["model"], gercek):
        print(f"  {100*e['esik']:>5.0f}%{e['alarm']:>8}{e['dogru']:>7}{e['yanlis']:>8}"
              f"{100*e['kesinlik']:>9.1f}%{100*e['duyarlilik']:>11.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
