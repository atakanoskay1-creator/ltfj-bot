#!/usr/bin/env python3
"""MODEL B - NIHAI HOLDOUT degerlendirmesi - TEK ATIS.

Model A'nin holdout_degerlendir.py'siyle AYNI disiplin: 2024-2026 gelistirme
boyunca hic acilmadi. Bu betik dondurulmus prosedurle (olusum_egit.ALANLAR)
TUM gelistirme donemini (2011-2023, sinir embargolu) egitip holdout uzerinde
BIR KEZ olcer.

AYRICA gorussuz/gorus-katildi karsilastirmasi (Bolum 11'deki "no-visibility
ablation") burada, AYNI egitim/test bolmesinde yapilir - bu, "gorusun
kattigi bilgi" sorusuna dogrudan, ayni holdout uzerinde bir cevap verir.

KURAL: bu sonuc gorulduKTEN SONRA degisken seti, embargo veya metodoloji
DEGISTIRILIRSE holdout gecerliligini yitirir. Ne cikarsa o raporlanir.

Not (Bolum 14, metodolojik durustluk): 2024-2026 penceresi bu programda
(sis modeli -> tavan matrisi -> ciy noktasi A/B -> simdi Model B) ARTIK
DORDUNCU kez "holdout" olarak aciliyor. Her biri kendi TEK ATIS kuralini
onceden ilan ettigi icin TEKIL olarak mesru, ama aninin "surprizi" kumulatif
olarak azaliyor - bu durustce not edilir.
"""

import sys
from pathlib import Path

from sis_modeli import bolme, degerlendir, hedef, model, olay_degerlendirme
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku
from sis_modeli.olusum_alanlar import dogrula
from sis_modeli.olusum_egit import ALANLAR, hava_sutunu_ekle


def main() -> int:
    if not VARSAYILAN_VERI.exists():
        print(f"HATA: {VARSAYILAN_VERI} yok.", file=sys.stderr)
        return 1

    dogrula(ALANLAR)

    ham = [r for r in veri_oku(VARSAYILAN_VERI) if r["zaman"][:4] >= str(bolme.ILK_YIL)]
    kayitlar = hava_sutunu_ekle(hedef.hazirla(ham))
    aday = hedef.onset_adaylari(kayitlar)

    egitim = bolme.embargo_penceresi(bolme.gelistirme(aday), min(bolme.HOLDOUT_YILLARI))
    test = bolme.holdout(aday)               # ILK KEZ aciliyor
    if not test:
        print("HATA: holdout bos.", file=sys.stderr)
        return 1

    print("=== MODEL B — NİHAİ HOLDOUT (2024-2026) — TEK ATIŞ ===\n")
    print(f"Eğitim (2011-2023, sınır embargolu): {len(egitim)} an, "
          f"{sum(r['hedef'] for r in egitim)} pozitif")
    print(f"HOLDOUT (2024-2026): {len(test)} an, {sum(r['hedef'] for r in test)} pozitif "
          f"(taban oran %{100*sum(r['hedef'] for r in test)/len(test):.2f})")
    print(f"Değişkenler (görüşsüz): {', '.join(ALANLAR)}\n")

    gercek = [bool(r["hedef"]) for r in test]
    taban_egitim = sum(r["hedef"] for r in egitim) / len(egitim)
    iklim = [taban_egitim] * len(test)

    katsayilar_b, tablolar_b, l2_b = model.egit_secerek(egitim, ALANLAR)
    tahmin_b = [model.olasilik(katsayilar_b, r, tablolar_b) for r in test]

    alanlar_a = ALANLAR + ["gorus"]
    katsayilar_a, tablolar_a, l2_a = model.egit_secerek(egitim, alanlar_a)
    tahmin_a = [model.olasilik(katsayilar_a, r, tablolar_a) for r in test]

    tahminler = {
        "Model B (görüşsüz)": tahmin_b,
        "Model B + görüş (ablasyon)": tahmin_a,
        "iklim": iklim,
        "basit kural (spread+rüzgâr)": [model.basit_kural_baseline(r) for r in test],
    }

    print(f"Seçilen L2 — görüşsüz: {l2_b:.0f}, görüş dahil: {l2_a:.0f}\n")
    print(f"{'yöntem':<28}{'Brier×10⁴':>11}{'BSS':>8}{'AP':>8}"
          f"{'LogLoss':>9}{'ROC-AUC':>9}{'AP %5–%95':>18}")
    for ad, p in tahminler.items():
        alt, ust = degerlendir.blok_guven_araligi(test, p, gercek,
                                                  degerlendir.ortalama_kesinlik)
        print(f"{ad:<28}{1e4*degerlendir.brier(p, gercek):>11.2f}"
              f"{degerlendir.brier_skill(p, gercek, iklim):>8.3f}"
              f"{degerlendir.ortalama_kesinlik(p, gercek):>8.3f}"
              f"{degerlendir.log_loss(p, gercek):>9.3f}"
              f"{degerlendir.roc_auc(p, gercek):>9.3f}"
              f"{f'{alt:.3f} – {ust:.3f}':>18}")

    fark_ap = (degerlendir.ortalama_kesinlik(tahmin_a, gercek)
              - degerlendir.ortalama_kesinlik(tahmin_b, gercek))
    print(f"\nGörüşün kattığı AP (Model B+görüş − Model B): {fark_ap:+.3f}")

    print("\n=== Güvenilirlik (Model B, görüşsüz) ===")
    print(f"  {'kova':<10}{'n':>8}{'ort. tahmin':>13}{'gerçekleşen':>13}{'poz':>6}")
    for k in degerlendir.guvenilirlik(tahmin_b, gercek):
        print(f"  {k['kova']/10:.1f}-{(k['kova']+1)/10:.1f}   {k['n']:>8}"
              f"{100*k['ortalama_tahmin']:>12.2f}%{100*k['gerceklesen']:>12.2f}%{k['pozitif']:>6}")

    # ------------------------------------------------------- event-level
    tahmin_map_b = {r["dt"]: p for r, p in zip(test, tahmin_b)}
    olaylar = [o for o in olay_degerlendirme.bagimsiz_olaylar(kayitlar)
              if o["baslangic"].year in bolme.HOLDOUT_YILLARI]
    temsilciler = olay_degerlendirme.olay_temsilci_satirlari(kayitlar, olaylar)
    print(f"\n=== Event-level (holdout, {len(olaylar)} bağımsız olay) — Model B ===")
    print(f"  {'eşik':>6}{'olay':>7}{'yakalanan':>11}{'duyarlılık':>12}{'%5–%95':>16}")
    for e in olay_degerlendirme.olay_bazli_esik_tablosu(temsilciler, tahmin_map_b):
        alt, ust = olay_degerlendirme.olay_bazli_guven_araligi(
            temsilciler, tahmin_map_b, e["esik"], tekrar=150)
        print(f"  {100*e['esik']:>5.0f}%{e['toplam_olay']:>7}{e['yakalanan']:>11}"
              f"{100*e['duyarlilik']:>11.1f}%{f'{100*alt:.1f}–{100*ust:.1f}%':>16}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
