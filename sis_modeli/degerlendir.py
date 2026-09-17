#!/usr/bin/env python3
"""Nadir olay icin olasilik tahmini metrikleri.

DOGRULUK (accuracy) BILEREK YOK: taban oran %0.7 oldugu icin "hic sis olmaz"
demek %99.3 dogruluk verir. Bu metrik burada bilgi tasimaz ve yaniltir.

Kullanilan metrikler:
  - Brier: ortalama kareli olasilik hatasi (dusuk = iyi)
  - Brier Skill Score (BSS): iklim baseline'ina gore KAZANC (>0 = iyi)
  - Guvenilirlik (reliability): "%40" dedigimizde gercekten %40 mi cikiyor?
    Kullaniciya olasilik gosterecegimiz icin EN ONEMLI metrik budur.
  - Ortalama kesinlik (AP / PR egrisi alti): siralama gucu
  - Belirli esiklerde precision/recall: "kac kere bosuna alarm, kac kacirma"
"""

from collections import defaultdict
import random


def brier(tahminler: list, gercekler: list) -> float:
    n = len(tahminler) or 1
    return sum((p - int(bool(y))) ** 2 for p, y in zip(tahminler, gercekler)) / n


def brier_skill(tahminler: list, gercekler: list, referans: list) -> float:
    """BSS = 1 - Brier(model) / Brier(referans). 0 = referansla ayni,
    1 = mukemmel, negatif = referanstan KOTU."""
    b_ref = brier(referans, gercekler)
    if b_ref <= 0:
        return 0.0
    return 1.0 - brier(tahminler, gercekler) / b_ref


def guvenilirlik(tahminler: list, gercekler: list, kova_sayisi: int = 10) -> list:
    """Tahmin edilen olasiliga gore kovalar; her kovada ORTALAMA TAHMIN ile
    GERCEKLESEN ORAN yan yana. Ikisi birbirine ne kadar yakinsa model o kadar
    iyi kalibredir."""
    kovalar = defaultdict(lambda: [0, 0.0, 0])      # [n, tahmin toplami, pozitif]
    for p, y in zip(tahminler, gercekler):
        k = min(int(p * kova_sayisi), kova_sayisi - 1)
        kovalar[k][0] += 1
        kovalar[k][1] += p
        kovalar[k][2] += int(bool(y))
    return [{"kova": k, "n": v[0], "ortalama_tahmin": v[1] / v[0],
             "gerceklesen": v[2] / v[0], "pozitif": v[2]}
            for k, v in sorted(kovalar.items()) if v[0]]


def ortalama_kesinlik(tahminler: list, gercekler: list) -> float:
    """Average precision (PR egrisi alti). AUC-ROC yerine bu kullanilir:
    nadir olayda ROC, cok sayida kolay negatif yuzunden modeli oldugundan
    iyi gosterir."""
    ciftler = sorted(zip(tahminler, gercekler), key=lambda c: -c[0])
    toplam_poz = sum(1 for _, y in ciftler if y)
    if not toplam_poz:
        return 0.0
    dogru, ap = 0, 0.0
    for i, (_, y) in enumerate(ciftler, start=1):
        if y:
            dogru += 1
            ap += dogru / i
    return ap / toplam_poz


def esik_tablosu(tahminler: list, gercekler: list, esikler=(0.05, 0.10, 0.20, 0.40)) -> list:
    cikti = []
    toplam_poz = sum(1 for y in gercekler if y)
    for e in esikler:
        tp = sum(1 for p, y in zip(tahminler, gercekler) if p >= e and y)
        fp = sum(1 for p, y in zip(tahminler, gercekler) if p >= e and not y)
        cikti.append({
            "esik": e, "alarm": tp + fp, "dogru": tp, "yanlis": fp,
            "kesinlik": tp / (tp + fp) if tp + fp else 0.0,
            "duyarlilik": tp / toplam_poz if toplam_poz else 0.0,
        })
    return cikti


def blok_guven_araligi(kayitlar: list, tahminler: list, gercekler: list,
                       olcu, gun_alani: str = "gun", tekrar: int = 200,
                       tohum: int = 0) -> tuple:
    """Metrigin %5-%95 araligi - GUN bazinda blok bootstrap.

    Satir bazinda yeniden ornekleme araligi sahte sekilde daraltirdi: ayni
    sis olayinin ~12 satiri bagimsiz sayilamaz."""
    gunler = defaultdict(list)
    for r, p, y in zip(kayitlar, tahminler, gercekler):
        gunler[r[gun_alani]].append((p, y))
    anahtarlar = list(gunler)
    if not anahtarlar:
        return (0.0, 0.0)
    rastgele = random.Random(tohum)

    sonuclar = []
    for _ in range(tekrar):
        p_ler, y_ler = [], []
        for _ in anahtarlar:
            for p, y in gunler[rastgele.choice(anahtarlar)]:
                p_ler.append(p)
                y_ler.append(y)
        sonuclar.append(olcu(p_ler, y_ler))
    sonuclar.sort()
    return (sonuclar[int(0.05 * len(sonuclar))],
            sonuclar[min(int(0.95 * len(sonuclar)), len(sonuclar) - 1)])
