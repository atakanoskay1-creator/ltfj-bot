#!/usr/bin/env python3
"""Coklu dogrusal baglanti (multicollinearity) tanilamasi.

Model WoE'ye cevrilmis degiskenleri gordugu icin korelasyon/VIF de HAM deger
uzerinde degil WOE UZERINDE olculur - ham deger arasinda dogrusal olmayan
ama WoE sonrasi dogrusal hale gelen iliskiler vardir.

Uc tanilama:
  1. Korelasyon matrisi - hangi ikili birbirinin yerine geciyor
  2. VIF - bir degiskenin DIGERLERININ HEPSI tarafindan ne kadar aciklandigi
     (ikili korelasyonun kaciracagi coklu iliskileri yakalar)
  3. Isaret kontrolu - tek degiskenli WoE yonu ile cok degiskenli katsayi
     isareti celisiyorsa bu klasik es-dogrusallik belirtisidir: model
     degiskeni "duzeltici" olarak kullaniyordur, yorumlanamaz hale gelir.

Bagimlilik yok: saf standart kutuphane.
"""

import math

from sis_modeli.model import _coz, TekilSistem, desen

# VIF yorum esikleri (yaygin kabul)
VIF_DIKKAT = 5.0
VIF_CIDDI = 10.0


def _woe_sutunlari(kayitlar: list, tablolar: dict) -> tuple:
    """(alan adlari, sutun listeleri) - her sutun WoE degerlerinden olusur."""
    adlar = sorted(tablolar)
    sutunlar = [[] for _ in adlar]
    for r in kayitlar:
        for i, d in enumerate(desen(r, tablolar)):
            sutunlar[i].append(d)
    return adlar, sutunlar


def _pearson(x: list, y: list) -> float:
    n = len(x)
    if n < 2:
        return 0.0
    ox, oy = sum(x) / n, sum(y) / n
    sx = math.sqrt(sum((a - ox) ** 2 for a in x))
    sy = math.sqrt(sum((b - oy) ** 2 for b in y))
    if sx < 1e-12 or sy < 1e-12:
        return 0.0
    return sum((a - ox) * (b - oy) for a, b in zip(x, y)) / (sx * sy)


def korelasyon_matrisi(kayitlar: list, tablolar: dict) -> tuple:
    adlar, sutunlar = _woe_sutunlari(kayitlar, tablolar)
    n = len(adlar)
    m = [[1.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            r = _pearson(sutunlar[i], sutunlar[j])
            m[i][j] = m[j][i] = r
    return adlar, m


def vif(kayitlar: list, tablolar: dict) -> dict:
    """Her degisken icin VIF = 1/(1-R^2); R^2, o degiskenin DIGERLERINE
    regresyonundan gelir. Ikili korelasyonun kaciracagi 'ucu birlikte
    bagimli' durumlari yakalar."""
    adlar, sutunlar = _woe_sutunlari(kayitlar, tablolar)
    n_deg = len(adlar)
    if n_deg < 2:
        return {a: 1.0 for a in adlar}

    sonuc = {}
    for j in range(n_deg):
        y = sutunlar[j]
        digerleri = [sutunlar[k] for k in range(n_deg) if k != j]
        p = len(digerleri) + 1                     # + sabit terim
        XtX = [[0.0] * p for _ in range(p)]
        Xty = [0.0] * p
        for i in range(len(y)):
            x = [1.0] + [s[i] for s in digerleri]
            for a in range(p):
                Xty[a] += x[a] * y[i]
                for b in range(a, p):
                    XtX[a][b] += x[a] * x[b]
        for a in range(p):
            for b in range(a):
                XtX[a][b] = XtX[b][a]
            XtX[a][a] += 1e-8                      # sayisal guvenlik
        try:
            beta = _coz(XtX, Xty)
        except TekilSistem:
            sonuc[adlar[j]] = float("inf")
            continue

        oy = sum(y) / len(y)
        ss_top = sum((v - oy) ** 2 for v in y)
        ss_kalan = 0.0
        for i in range(len(y)):
            x = [1.0] + [s[i] for s in digerleri]
            tahmin = sum(b * xi for b, xi in zip(beta, x))
            ss_kalan += (y[i] - tahmin) ** 2
        r2 = 1.0 - ss_kalan / ss_top if ss_top > 1e-12 else 0.0
        sonuc[adlar[j]] = float("inf") if r2 >= 1 - 1e-9 else 1.0 / (1.0 - r2)
    return sonuc


def isaret_kontrolu(tablolar: dict, katsayilar: list) -> list:
    """Tek degiskenli WoE yonu ile cok degiskenli katsayi isaretini karsilastirir.

    WoE tanimi geregi WoE arttikca pozitif olasilik ARTMALIDIR, yani saglikli
    bir modelde her katsayi POZITIF olmalidir. Negatif katsayi, degiskenin
    baska bir degiskeni 'duzeltmek' icin kullanildigini gosterir - es-dogrusallik
    belirtisi ve yorumlanabilirligi bozar."""
    adlar = sorted(tablolar)
    cikti = []
    for i, ad in enumerate(adlar):
        k = katsayilar[i + 1]                       # 0. eleman sabit terim
        cikti.append({"alan": ad, "katsayi": k, "beklenen_isaret": "+",
                      "sorunlu": k < 0})
    return cikti
