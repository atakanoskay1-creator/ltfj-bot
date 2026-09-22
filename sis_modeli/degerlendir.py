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
  - Log-olabilirlik beceri skoru (LSS): BSS'in log-kayip karsiligi. NEDEN
    GEREKLI - Jewson (2004) ve Benedetti (2009), olay olasiligi cok
    kucukken Brier Score'un COZUNURLUGUNU KAYBETTIGINI gosterdi: model
    iyilesse bile BS kipirdamaz. Bu projenin taban orani %0.76, yani tam
    o bolgede (lead-time tablosunda BSS 2 saatte 1 saatten DUSUK cikmisti,
    AP monoton artarken). Ayni referansa gore log-kayip orani cok daha
    duyarli. Bkz. Yabra ve ark. (2026), Ezeiza havaalani.
"""

import math
import random
from collections import defaultdict


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


def log_loss(tahminler: list, gercekler: list, eps: float = 1e-9) -> float:
    """Ortalama log-kayip (negatif log-olabilirlik). Brier'den FARKI: yanlis
    emin tahminleri (ornegin gercek pozitifken %0.1 demek) Brier'den cok daha
    agir cezalandirir - kareli hata sinirli (<=1) ama log-kayip sinirsizdir.

    eps: p tam 0/1'e yapisirsa log(0) olmasin diye kirpma payi."""
    n = len(tahminler) or 1
    toplam = 0.0
    for p, y in zip(tahminler, gercekler):
        p = min(max(p, eps), 1 - eps)
        toplam += -math.log(p) if y else -math.log(1 - p)
    return toplam / n


def log_skill(tahminler: list, gercekler: list, referans: list,
              eps: float = 1e-9) -> float:
    """LSS = 1 - LogLoss(model) / LogLoss(referans).

    brier_skill ile AYNI bicim: 0 = referansla ayni, 1 = mukemmel,
    negatif = referanstan KOTU.

    NOT: Yabra ve ark. (2026) Denklem 4'te LS'yi isaretsiz yazip
    "mukemmel tahmin LS = -sonsuz" diyor; bu iki ifade kendi icinde
    tutarsiz. Beceri skoru (1 - LS/LS_ref) yalnizca LS NEGATIF
    log-olabilirlik iken calisir (mukemmel = 0 -> LSS = 1). Burada
    log_loss() zaten ortalama negatif log-olabilirlik oldugu icin
    dogrudan kullaniliyor."""
    ls_ref = log_loss(referans, gercekler, eps)
    if ls_ref <= 0:
        return 0.0
    return 1.0 - log_loss(tahminler, gercekler, eps) / ls_ref


# Kucuk kovalarin genel taban orana cekilme gucu. 50 = "bir kovanin kendi
# oranina inanmak icin ~50 gozlem gerekir". Sis nadir oldugu icin bu sart:
# yumusatma olmadan tek pozitifi olmayan bir saat kovasi p=0 verir ve o
# saatte bir olay olursa referans SONSUZ ceza alir, LSS anlamsizlasir.
KOVA_YUMUSATMA = 50.0


def kosullu_iklim(anahtarlar: list, gercekler: list,
                  yumusatma: float = KOVA_YUMUSATMA) -> list:
    """Anahtar basina (ornegin saat) taban oran - DUZ taban orandan daha
    ZOR bir referans.

    Neden gerekli: sisin gucli bir gunluk dongusu var ve modelin kendi
    degiskenleri arasinda `saat` DE var. Duz taban orana gore olculen
    beceri, "model gunluk dongusu ogrendi"yi atmosferik beceri gibi
    gosterebilir. Saate kosullu referans bu payi referansa devreder;
    geriye kalan beceri gercekten atmosferik olandir.

    Referans, dogrulama orneginin KENDI ikliminden kurulur (tahmin
    sistemi degil, normalizasyon) - brier_skill'deki duz taban oranla
    ayni uygulama."""
    n = len(gercekler) or 1
    genel = sum(1 for y in gercekler if y) / n
    toplam, pozitif = defaultdict(int), defaultdict(int)
    for a, y in zip(anahtarlar, gercekler):
        toplam[a] += 1
        pozitif[a] += int(bool(y))
    return [(pozitif[a] + yumusatma * genel) / (toplam[a] + yumusatma)
            for a in anahtarlar]


def roc_auc(tahminler: list, gercekler: list) -> float:
    """ROC egrisi alti alan - rastgele bir pozitif/negatif ciftinde pozitife
    daha yuksek skor verme olasiligi (Mann-Whitney U esdegeri).

    DIKKAT (bkz. modul basligi): nadir olayda ROC-AUC modeli oldugundan iyi
    gosterebilir - cok sayida kolay negatif, esik ne olursa olsun yuksek
    "true negative rate" saglar. Bu yuzden BIRINCIL metrik degil; AP'nin
    (ortalama_kesinlik) YANINDA, istenen ek bir gorunum olarak sunulur."""
    ciftler = sorted(zip(tahminler, gercekler), key=lambda c: c[0])
    n = len(ciftler)
    pozitif = sum(1 for _, y in ciftler if y)
    negatif = n - pozitif
    if pozitif == 0 or negatif == 0:
        return 0.5

    # Ortalanmis siralar (bagli/esit skorlarda ortalama sira paylasilir).
    siralar = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and ciftler[j + 1][0] == ciftler[i][0]:
            j += 1
        ortalama_sira = (i + j) / 2.0 + 1.0          # 1-tabanli sira
        for k in range(i, j + 1):
            siralar[k] = ortalama_sira
        i = j + 1

    pozitif_sira_toplami = sum(s for s, (_, y) in zip(siralar, ciftler) if y)
    # U istatistigi -> AUC. Bkz. Mann-Whitney U / Wilcoxon rank-sum esdegerligi.
    u = pozitif_sira_toplami - pozitif * (pozitif + 1) / 2.0
    return u / (pozitif * negatif)


def esli_blok_guven_araligi(seriler: dict, olcu, tekrar: int = 200,
                            tohum: int = 0) -> tuple:
    """Birden cok seri icin AYNI bootstrap orneginde gun-blok araliklari.

    seriler: {ad: (gunler, tahminler, gercekler)} - hepsi ayni gun
    evrenini paylasmali (paylasmiyorsa KESISIM kullanilir).

    NEDEN ESLI: iki marjinal aralik ORTUSUYOR diye "fark yok" denemez -
    bu yaygin bir okuma hatasidir. Ufuklar ayni gunlerin havasini
    paylasiyor; ayni gunleri ornekleyip FARKI olcmek cok daha guclu bir
    kiyastir. Burada her replikada tum seriler ayni gun ornegi uzerinde
    hesaplanir, boylece farkin dagilimi dogrudan cikar.

    olcu: (tahminler, gercekler) -> float. Iklim referansi gerektiren
    beceri skorlari icin referans OLCU ICINDE, her replikanin kendi
    orneginden yeniden kurulmalidir (bkz. ufuk_deneyi).

    Doner: (araliklar, farklar)
      araliklar : {ad: (alt, ust)}                    %5-%95
      farklar   : {(a, b): (alt, ust, medyan, oran)}  a - b farki;
                  `oran` = farkin pozitif ciktigi replika yuzdesi."""
    adlar = list(seriler)
    if not adlar:
        return {}, {}

    # Gun -> satirlar, her seri icin ayri; ortak gun evreni uzerinde.
    indeks, gun_kumeleri = {}, []
    for ad in adlar:
        gunler, tahminler, gercekler = seriler[ad]
        d = defaultdict(list)
        for g, t, y in zip(gunler, tahminler, gercekler):
            d[g].append((t, y))
        indeks[ad] = d
        gun_kumeleri.append(set(d))
    ortak = sorted(set.intersection(*gun_kumeleri))
    if not ortak:
        return {ad: (0.0, 0.0) for ad in adlar}, {}

    rastgele = random.Random(tohum)
    ornekler = {ad: [] for ad in adlar}
    for _ in range(tekrar):
        secilen = [rastgele.choice(ortak) for _ in ortak]
        for ad in adlar:
            d = indeks[ad]
            t_ler, y_ler = [], []
            for g in secilen:
                for t, y in d[g]:
                    t_ler.append(t)
                    y_ler.append(y)
            ornekler[ad].append(olcu(t_ler, y_ler))

    def _aralik(degerler):
        v = sorted(degerler)
        return (v[int(0.05 * len(v))], v[min(int(0.95 * len(v)), len(v) - 1)])

    araliklar = {ad: _aralik(ornekler[ad]) for ad in adlar}
    farklar = {}
    for i, a in enumerate(adlar):
        for b in adlar[i + 1:]:
            d = [x - y for x, y in zip(ornekler[a], ornekler[b])]
            alt, ust = _aralik(d)
            sirali = sorted(d)
            farklar[(a, b)] = (alt, ust, sirali[len(sirali) // 2],
                               sum(1 for x in d if x > 0) / len(d))
    return araliklar, farklar


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
