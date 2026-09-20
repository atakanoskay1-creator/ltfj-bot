#!/usr/bin/env python3
"""Model A'nin (ltfj_sis_olasilik) YUKSEK UCTA temkinli kalibrasyonunu
olcer ve DUZELTIR.

TESHIS: holdout guvenilirlik tablosunda ust kovalarda (>= %30) tahmin
edilen olasilik gerceklesenden dusuk cikiyordu (orn. "%35 dendiginde
gerceklesme %63"). Ama o kovalar KUCUK (n=19, n=7) - tam da bu projede
(A>=%5 / Model B analizi) kucuk-orneklem gurultusune karsi ogrendigimiz
suphecilikle bakilmali. Gun-bazli blok bootstrap CI [42.1%-82.4%]
%36.5'lik tahminin TAMAMEN USTUNDE - yani gurultu degil. AYRICA ayni
desen coooook daha buyuk orneklemle (n=209, n=86) walk-forward DEV
donemi disi-katlanmis (out-of-fold) tahminlerinde de goruluyor - bu
teshisi tesadufi olmaktan cikarip guvenilir kilan asil kanit.

DUZELTME: izotonik regresyon (PAVA - pool adjacent violators), SADECE
gelistirme donemi (2011-2023) walk-forward disi-katlanmis tahminleriyle
uydurulur - holdout bu adimda HIC KULLANILMAZ. Kalibrasyon haritasi
sonra NIHAI (tum-gelistirme-egitimli) modelin ciktisina uygulanir ve
holdout'ta (ZATEN COK KEZ ACILMIS, bu da bir istisna degil - durustce
not edilir) ONCE/SONRA karsilastirilir.

Kullanim:
    python -m sis_modeli.kalibrasyon
"""
import sys
from collections import defaultdict
from pathlib import Path

from sis_modeli import bolme, degerlendir, hedef, model
from sis_modeli.egit import ALANLAR
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku


def izotonik_uydur(ciftler: list) -> list:
    """PAVA (pool adjacent violators) ile monoton-artan bir adim fonksiyonu
    uydurur. ciftler: [(p_ham, y_bool), ...]. Donen: p'ye gore ARTAN sirali
    bloklar - her biri {p_min, p_max, n, kalibre}."""
    toplam = defaultdict(lambda: [0, 0])   # p_ham -> [n, poz]
    for p, y in ciftler:
        toplam[p][0] += 1
        toplam[p][1] += int(bool(y))
    noktalar = sorted(toplam.items())

    yigin = []
    for p, (n, poz) in noktalar:
        yigin.append({"p_min": p, "p_max": p, "n": n, "poz": poz})
        while len(yigin) >= 2 and (yigin[-2]["poz"] / yigin[-2]["n"]
                                   > yigin[-1]["poz"] / yigin[-1]["n"]):
            b2, b1 = yigin.pop(), yigin.pop()
            yigin.append({"p_min": b1["p_min"], "p_max": b2["p_max"],
                          "n": b1["n"] + b2["n"], "poz": b1["poz"] + b2["poz"]})
    return [{"p_min": b["p_min"], "p_max": b["p_max"], "n": b["n"],
             "kalibre": b["poz"] / b["n"]} for b in yigin]


def kalibrasyon_tablosu(bloklar: list) -> list:
    """izotonik_uydur() ciktisini calisma-anindaki WOE_TABLOLARI ile ayni
    bicime (ust_sinir, deger) cevirir - ust_sinir=None son blok icin.
    Sinir, iki blok arasindaki BOSLUGUN ortasi (gozlenmemis p degerleri
    icin en makul kesim noktasi)."""
    tablo = []
    for i, b in enumerate(bloklar):
        if i + 1 < len(bloklar):
            sinir = (b["p_max"] + bloklar[i + 1]["p_min"]) / 2
        else:
            sinir = None
        tablo.append((sinir, b["kalibre"]))
    return tablo


def kalibre_uygula(p_ham: float, tablo: list) -> float:
    for ust, deger in tablo:
        if ust is None or p_ham <= ust:
            return deger
    return tablo[-1][1]


def _disi_katlanmis_tahminler(gelistirme: list) -> tuple:
    """egit.py'deki AYNI walk-forward donguyu tekrarlar - HER tahmin
    KENDI test yilinin DISINDA egitilmis bir modelden gelir (gercek
    disi-katlanmis / out-of-fold, dev donemi icinde)."""
    p_ler, y_ler = [], []
    for egitim_yillari, test_yillari in bolme.foldlar():
        egitim = bolme.ayir(gelistirme, egitim_yillari)
        test = bolme.ayir(gelistirme, test_yillari)
        if not test or not any(r["hedef"] for r in test):
            continue
        katsayilar, tablolar, _l2 = model.egit_secerek(egitim, ALANLAR)
        for r in test:
            p_ler.append(model.olasilik(katsayilar, r, tablolar))
            y_ler.append(bool(r["hedef"]))
    return p_ler, y_ler


def main() -> int:
    if not VARSAYILAN_VERI.exists():
        print(f"HATA: {VARSAYILAN_VERI} yok.", file=sys.stderr)
        return 1

    ham = [r for r in veri_oku(VARSAYILAN_VERI) if r["zaman"][:4] >= str(bolme.ILK_YIL)]
    kayitlar = hedef.hazirla(ham)
    aday = hedef.onset_adaylari(kayitlar)
    gelistirme = bolme.gelistirme(aday)

    print("=== 1) Kalibrasyon haritasını UYDUR (dev, dışı-katlanmış, holdout KULLANILMADI) ===\n")
    p_dev, y_dev = _disi_katlanmis_tahminler(gelistirme)
    print(f"Dışı-katlanmış tahmin sayısı: {len(p_dev)}, pozitif: {sum(y_dev)}\n")

    bloklar = izotonik_uydur(list(zip(p_dev, y_dev)))
    tablo = kalibrasyon_tablosu(bloklar)
    print(f"İzotonik blok sayısı: {len(bloklar)} (ham -> kalibre değer çiftleri)")
    print("Yalnızca farkın büyük olduğu bloklar gösteriliyor (|kalibre - ham_orta| > 0.02):")
    print(f"{'p_min':>8}{'p_max':>8}{'n':>8}{'kalibre':>10}")
    for b in bloklar:
        ham_orta = (b["p_min"] + b["p_max"]) / 2
        if abs(b["kalibre"] - ham_orta) > 0.02:
            print(f"{100*b['p_min']:>7.2f}%{100*b['p_max']:>7.2f}%{b['n']:>8}"
                  f"{100*b['kalibre']:>9.2f}%")

    print("\n=== 2) Dışı-katlanmış (dev) veride ÖNCE/SONRA güvenilirlik ===\n")
    p_kalibre_dev = [kalibre_uygula(p, tablo) for p in p_dev]
    for etiket, p_ler in (("HAM", p_dev), ("KALİBRE", p_kalibre_dev)):
        print(f"-- {etiket} --")
        print(f"  {'kova':<10}{'n':>8}{'ort. tahmin':>13}{'gerçekleşen':>13}")
        for k in degerlendir.guvenilirlik(p_ler, y_dev):
            print(f"  {k['kova']/10:.1f}-{(k['kova']+1)/10:.1f}   {k['n']:>8}"
                  f"{100*k['ortalama_tahmin']:>12.2f}%{100*k['gerceklesen']:>12.2f}%")
        print(f"  AP: {degerlendir.ortalama_kesinlik(p_ler, y_dev):.3f}  "
              f"Brier×10⁴: {1e4*degerlendir.brier(p_ler, y_dev):.2f}")
    print()

    print("=== 3) NİHAİ modeli tüm gelişme dönemiyle eğit, HOLDOUT'ta ÖNCE/SONRA "
         "(NOT: holdout bu programda tekrar açılıyor - dürüstlük notu, README'ye işlenecek) ===\n")
    katsayilar, tablolar, l2 = model.egit_secerek(gelistirme, ALANLAR)
    test = bolme.holdout(aday)
    gercek_test = [bool(r["hedef"]) for r in test]
    p_ham_test = [model.olasilik(katsayilar, r, tablolar) for r in test]
    p_kalibre_test = [kalibre_uygula(p, tablo) for p in p_ham_test]

    for etiket, p_ler in (("HAM", p_ham_test), ("KALİBRE", p_kalibre_test)):
        print(f"-- {etiket} (holdout) --")
        print(f"  {'kova':<10}{'n':>8}{'ort. tahmin':>13}{'gerçekleşen':>13}")
        for k in degerlendir.guvenilirlik(p_ler, gercek_test):
            print(f"  {k['kova']/10:.1f}-{(k['kova']+1)/10:.1f}   {k['n']:>8}"
                  f"{100*k['ortalama_tahmin']:>12.2f}%{100*k['gerceklesen']:>12.2f}%")
        ap = degerlendir.ortalama_kesinlik(p_ler, gercek_test)
        brier = degerlendir.brier(p_ler, gercek_test)
        print(f"  AP: {ap:.3f}  Brier×10⁴: {1e4*brier:.2f}")
    print(f"\n(AP'nin HAM/KALİBRE arasında AYNI kalması BEKLENİR - izotonik "
         "regresyon monoton, sıralamayı değiştirmez; sadece Brier/kalibrasyon "
         "düzelir.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
