#!/usr/bin/env python3
"""Sis modeli V2 gelistirme hatti - sonumlu Newton cozucusu (§15 cozucu duzeltmesi).

NEDEN: V1 referans benchmark'inin ilk (duzeltme oncesi) calismasinda
model.egit'in adim kontrolu olmayan IRLS'i, bazi fit'lerde iterasyon 5
civarindan itibaren iraksadi ve Yakinsamadi verdi; §6 kurali bu yuzden
lambda = 0,1 / 1 / 10 / 100'u bazi dis fold'larda eledi. Incelenen o
fit'lerde ayni cezali amac fonksiyonu sonumlu Newton ile sonlu ve olagan
olcekte bir cozume yakinsadi (V2_V1_BENCHMARK_RAPORU.md). Bu, protokol §15
kapsaminda bir uygulama hatasi olarak siniflandirildi.

model.egit DEGISTIRILMEDI: tarihsel V1 deneyleri ayni sekilde yeniden
uretilebilir kalir. Bu modul yalnizca V2 gelistirme hattinda (V1 referansi
ve V2a/b/c) kullanilir.

AMAC FONKSIYONU (model.egit ile ayni tanim):
    f(b) = sum_d [ n_d * log(1 + exp(eta_d)) - k_d * eta_d ] + (l2/2) * sum_{i>=1} b_i^2
    eta_d = b_0 + sum_i b_i * x_di        (sabit terim cezalandirilmaz)

ALGORITMA: Newton adimi s = -(H)^-1 g, H = X'WX + l2*I (sabit terim haric),
g = X'(n*p - k) + l2*b. Tam adim (a = 1) denenir; amac fonksiyonunu
KOTULESTIREN adim kabul edilmez, a yarilanir (deterministik backtracking).
Kabul kosulu: f(yeni) <= f(eski). Baslangic model.egit ile ayni (sabit terim
taban oran log-odds'u, egimler 0).

SABITLER (benchmark sonuclarina tekrar bakilmadan belirlendi, testle kilitli):
  YAKINSAMA   = 1e-7   TAM Newton adiminin max |bilesen|'i bunun altindaysa yakinsadi
                       (esik model.YAKINSAMA ile ayni; yarilanmis adim olcut degildir)
  AZALIM_GORELI = 1e-12  VEYA Newton azalimi (g'H^-1 g / 2 = amacin beklenen
                       iyilesmesi) <= AZALIM_GORELI * max(1, |f|) ise yakinsadi.
                       Gerekce: zayif belirlenen bir yonde (kucuk l2) optimumda
                       gradyanin kayan nokta gurultusu H^-1 ile buyur ve tam adim
                       1e-7'nin altina inmeyebilir; amac ise hesaplama
                       cozunurlugunde sabitlenmistir. Ilk tasarimda yalniz adim
                       olcutu vardi; gercek veri testinde (ic blok 2016,
                       lambda=0,1) optimumda "amaci kotulestirmeyen adim
                       bulunamadi" hatasi verdi. Bu olcut benchmark sonuclarina
                       bakilmadan, cozucu testi uzerine eklendi.
  MAKS_ITER   = 100    Newton iterasyonu ust siniri
  ASGARI_ADIM = 2**-30 adim carpani bunun altina inerse ilerleme yok sayilir

BASARISIZLIK KOSULLARI (model'in istisna siniflari kullanilir, boylece §6
eleme kurali ayni sekilde isler):
  - Hessian cozulemiyor (pivot ~0)                 -> model.TekilSistem
  - MAKS_ITER icinde yakinsamadi                    -> model.Yakinsamadi
  - yakinsama saglanmadan, a >= ASGARI_ADIM olan
    hicbir adim amaci kotulestirmemeyi saglamiyor    -> model.Yakinsamadi
  - amac fonksiyonu sonlu degil                     -> model.Yakinsamadi
"""

import math

from sis_modeli import model

YAKINSAMA = 1e-7
AZALIM_GORELI = 1e-12
MAKS_ITER = 100
ASGARI_ADIM = 2.0 ** -30


def _softplus(eta: float) -> float:
    """log(1 + e^eta), sayisal olarak kararli."""
    if eta > 0:
        return eta + math.log1p(math.exp(-eta))
    return math.log1p(math.exp(eta))


def _sigmoid(eta: float) -> float:
    if eta >= 0:
        return 1.0 / (1.0 + math.exp(-eta))
    e = math.exp(eta)
    return e / (1.0 + e)


def amac(beta: list, X: list, toplam: list, pozitif: list, l2: float) -> float:
    """Cezali negatif log-olabilirlik (desen agirlikli)."""
    s = 0.0
    for x, n, k in zip(X, toplam, pozitif):
        eta = sum(b * xi for b, xi in zip(beta, x))
        s += n * _softplus(eta) - k * eta
    return s + 0.5 * l2 * sum(b * b for b in beta[1:])


def egit(desenler: list, toplam: list, pozitif: list, l2: float = model.L2,
         iz: list = None) -> list:
    """Sonumlu Newton ile cezali lojistik regresyon. model.egit ile ayni
    arayuz ve ayni katsayi duzeni (ilk eleman sabit terim).

    iz: verilirse her KABUL EDILEN iterasyon icin
    {'amac', 'adim', 'yarilama', 'fark'} sozlukleri eklenir (tanilama/test)."""
    if not desenler:
        return [0.0]
    m = len(desenler[0]) + 1
    beta = [0.0] * m
    top_n, top_k = sum(toplam), sum(pozitif)
    if 0 < top_k < top_n:
        beta[0] = math.log(top_k / (top_n - top_k))
    X = [(1.0,) + tuple(d) for d in desenler]
    f = amac(beta, X, toplam, pozitif, l2)
    if iz is not None:
        iz.append({"amac": f, "adim": 0.0, "yarilama": 0, "fark": float("nan")})

    for _ in range(MAKS_ITER):
        g = [0.0] * m
        H = [[0.0] * m for _ in range(m)]
        for x, n, k in zip(X, toplam, pozitif):
            eta = sum(b * xi for b, xi in zip(beta, x))
            p = _sigmoid(eta)
            w = n * p * (1.0 - p)
            r = n * p - k
            for i in range(m):
                g[i] += r * x[i]
                wx = w * x[i]
                for j in range(i, m):
                    H[i][j] += wx * x[j]
        for i in range(m):
            for j in range(i):
                H[i][j] = H[j][i]
            if i > 0:
                H[i][i] += l2
                g[i] += l2 * beta[i]
        adim = model._coz(H, [-gi for gi in g])      # TekilSistem burada
        tam_adim = max(abs(x) for x in adim)
        azalim = -0.5 * sum(gi * si for gi, si in zip(g, adim))
        if tam_adim < YAKINSAMA or azalim <= AZALIM_GORELI * max(1.0, abs(f)):
            # Yakinsama TAM Newton adiminin buyuklugune gore olculur, kabul
            # edilen (yarilanmis olabilecek) adima gore degil: cok yarilanmis
            # kucuk bir adim sahte "yakinsadi" sinyali vermesin.
            yeni = [b + s for b, s in zip(beta, adim)]
            fy = amac(yeni, X, toplam, pozitif, l2)
            if math.isfinite(fy) and fy <= f:
                beta, f = yeni, fy
            if iz is not None:
                iz.append({"amac": f, "adim": 1.0, "yarilama": 0, "fark": tam_adim})
            return beta

        a, yarilama = 1.0, 0
        while True:
            yeni = [b + a * s for b, s in zip(beta, adim)]
            fy = amac(yeni, X, toplam, pozitif, l2)
            if math.isfinite(fy) and fy <= f:
                break
            a /= 2.0
            yarilama += 1
            if a < ASGARI_ADIM:
                raise model.Yakinsamadi(
                    f"sonumlu Newton: amaci kotulestirmeyen adim bulunamadi "
                    f"(l2={l2}, a<{ASGARI_ADIM:g})")
        fark = max(abs(y - b) for y, b in zip(yeni, beta))
        beta, f = yeni, fy
        if iz is not None:
            iz.append({"amac": f, "adim": a, "yarilama": yarilama, "fark": fark})
    raise model.Yakinsamadi(
        f"sonumlu Newton: MAKS_ITER={MAKS_ITER} iterasyonda yakinsamadi (l2={l2})")
