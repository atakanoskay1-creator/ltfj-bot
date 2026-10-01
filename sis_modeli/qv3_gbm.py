#!/usr/bin/env python3
"""QV3 hedefinde GBM (gradient boosting) denemesi - saf Python, yeni
kutuphane yok. Canliya baglanmaz.

NEDEN: WoE lojistik model her degiskenin etkisini AYRI AYRI (toplamsal)
ogreniyor. "Hafif KD ruzgari + dusuk spread + gece" gibi ETKILESIMLERI
ancak elle turetilmis bir degiskenle (kd_nemli) gorebiliyor. Sig agaclar bu
etkilesimleri kendiliginden bulur; degisken secimini de agaclar yapar (22
adayin hepsi verilir).

YONTEM (LightGBM/XGBoost'un cekirdegi, kucultulmus):
  - Her degisken egitim verisinin dagilim dilimlerine gore en fazla
    KOVA_SAYISI kovaya bolunur; eksik deger (None) ayri kova (0).
  - Lojistik kayip, Newton adimi: her agac gradyan/hessian histogramindan
    en iyi bolmeyi secer (L2 = LAMBDA), derinlik DERINLIK, yaprakta en az
    MIN_HESS agirlikli hessian.
  - Negatif ornekleme: pozitiflerin hepsi + negatiflerin NEG_ORAN'i,
    negatiflere 1/NEG_ORAN agirlik (olasiliklar kalibre kalir, hiz ~10x).
  - Agac sayisi egitimin SON YILINDA (ic dogrulama) AP'ye gore secilir,
    sonra tum egitimle o sayida yeniden egitilir - test yillari karismaz.

KALIBRASYON: ham GBM olasiliklari fazla yuksek cikti (ort. %1,36, gerceklesen
%0,87). Egitimin son KALIBRASYON_YILI yilinin donem-disi tahminleriyle iki
harita uydurulur ve nihai modelin ciktisina uygulanir - test yillari
karismaz:
  - Platt (ASIL, sonuclardan ONCE secildi): p' = sigmoid(a*logit(p) + b);
    siralamayi bozmaz, yalnizca yuzdeleri duzeltir.
  - Izotonik (ikincil, kalibrasyon.py): basamakli, siralamayi biraz bozabilir.

Kullanim (repo kokunden, ~5 dk):
    python -m sis_modeli.qv3_gbm
"""

import math
import random
from bisect import bisect_right
from collections import Counter

from sis_modeli import bolme, degerlendir, kalibrasyon, model, qv3_hedef, qv3_model
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku

KOVA_SAYISI = 32
DERINLIK = 3
OGRENME = 0.1
MAKS_AGAC = 300
KONTROL_ARALIGI = 10
LAMBDA = 1.0
MIN_HESS = 5.0
NEG_ORAN = 0.1
TOHUM = 0


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


def sinirlar_kur(kayitlar: list, alanlar) -> dict:
    """Her alan icin en fazla KOVA_SAYISI-1 esik (esit frekansli, tekil)."""
    sinirlar = {}
    for a in alanlar:
        degerler = sorted(r[a] for r in kayitlar if r.get(a) is not None)
        esikler = []
        for k in range(1, KOVA_SAYISI):
            if not degerler:
                break
            d = degerler[k * len(degerler) // KOVA_SAYISI]
            if not esikler or d > esikler[-1]:
                esikler.append(d)
        sinirlar[a] = esikler
    return sinirlar


def kova(deger, esikler: list) -> int:
    """0 = eksik; 1.. = esiklere gore sira (deger < esik[0] -> 1)."""
    return 0 if deger is None else 1 + bisect_right(esikler, deger)


def _sutunlar(kayitlar: list, alanlar, sinirlar: dict) -> list:
    return [[kova(r.get(a), sinirlar[a]) for r in kayitlar] for a in alanlar]


def _agac_kur(sutunlar, kova_sayilari, g, h, satirlar, derinlik) -> dict:
    G = sum(g[i] for i in satirlar)
    H = sum(h[i] for i in satirlar)
    yaprak = {"deger": -OGRENME * G / (H + LAMBDA)}
    if derinlik == 0 or H < 2 * MIN_HESS:
        return yaprak
    taban = G * G / (H + LAMBDA)
    en_iyi = (0.0, None, None)
    for j, sutun in enumerate(sutunlar):
        hg = [0.0] * kova_sayilari[j]
        hh = [0.0] * kova_sayilari[j]
        for i in satirlar:
            b = sutun[i]
            hg[b] += g[i]
            hh[b] += h[i]
        gl = hl = 0.0
        for b in range(kova_sayilari[j] - 1):
            gl += hg[b]
            hl += hh[b]
            hr = H - hl
            if hl < MIN_HESS:
                continue
            if hr < MIN_HESS:
                break
            gr = G - gl
            kazanc = gl * gl / (hl + LAMBDA) + gr * gr / (hr + LAMBDA) - taban
            if kazanc > en_iyi[0]:
                en_iyi = (kazanc, j, b)
    kazanc, j, b = en_iyi
    if j is None:
        return yaprak
    sol = [i for i in satirlar if sutunlar[j][i] <= b]
    sag = [i for i in satirlar if sutunlar[j][i] > b]
    return {"alan": j, "kova": b, "kazanc": kazanc,
            "sol": _agac_kur(sutunlar, kova_sayilari, g, h, sol, derinlik - 1),
            "sag": _agac_kur(sutunlar, kova_sayilari, g, h, sag, derinlik - 1)}


def _agac_tahmin(agac: dict, kovalar) -> float:
    while "alan" in agac:
        agac = agac["sol"] if kovalar[agac["alan"]] <= agac["kova"] else agac["sag"]
    return agac["deger"]


def _orneklem(kayitlar: list, tohum: int) -> tuple:
    rnd = random.Random(tohum)
    secilen, agirlik = [], []
    for r in kayitlar:
        if r["hedef"]:
            secilen.append(r)
            agirlik.append(1.0)
        elif rnd.random() < NEG_ORAN:
            secilen.append(r)
            agirlik.append(1.0 / NEG_ORAN)
    return secilen, agirlik


def egit(egitim: list, alanlar=qv3_model.ADAYLAR, agac_sayisi: int = MAKS_AGAC,
         dogrulama: list = None, tohum: int = TOHUM) -> dict:
    """GBM egitir. dogrulama verilirse her KONTROL_ARALIGI agacta AP olculur
    ve model["ap_egrisi"] = [(agac, ap)] eklenir."""
    alanlar = list(alanlar)
    ornek, w = _orneklem(egitim, tohum)
    sinirlar = sinirlar_kur(ornek, alanlar)
    sutunlar = _sutunlar(ornek, alanlar, sinirlar)
    kova_sayilari = [len(sinirlar[a]) + 2 for a in alanlar]
    y = [1.0 if r["hedef"] else 0.0 for r in ornek]
    pw = sum(wi * yi for wi, yi in zip(w, y))
    nw = sum(w) - pw
    f0 = math.log(pw / nw) if pw and nw else 0.0
    F = [f0] * len(ornek)
    tum = list(range(len(ornek)))

    d_kova = d_F = d_y = None
    if dogrulama:
        d_kova = list(zip(*_sutunlar(dogrulama, alanlar, sinirlar)))
        d_F = [f0] * len(dogrulama)
        d_y = [bool(r["hedef"]) for r in dogrulama]

    agaclar, egri = [], []
    for t in range(1, agac_sayisi + 1):
        p = [_sigmoid(x) for x in F]
        g = [wi * (pi - yi) for wi, pi, yi in zip(w, p, y)]
        h = [wi * pi * (1 - pi) for wi, pi in zip(w, p)]
        agac = _agac_kur(sutunlar, kova_sayilari, g, h, tum, DERINLIK)
        agaclar.append(agac)
        for i in tum:
            F[i] += _agac_tahmin(agac, [s[i] for s in sutunlar])
        if dogrulama:
            for i, kv in enumerate(d_kova):
                d_F[i] += _agac_tahmin(agac, kv)
            if t % KONTROL_ARALIGI == 0:
                egri.append((t, degerlendir.ortalama_kesinlik([_sigmoid(x) for x in d_F], d_y)))
    m = {"alanlar": alanlar, "sinirlar": sinirlar, "f0": f0, "agaclar": agaclar}
    if dogrulama:
        m["ap_egrisi"] = egri
    return m


def egit_secerek(egitim: list, alanlar=qv3_model.ADAYLAR) -> tuple:
    """Agac sayisini egitimin son yilinda secer, tum egitimle yeniden egitir.
    (model, secilen_agac_sayisi)"""
    son = max(r["dt"].year for r in egitim)
    ic_e = [r for r in egitim if r["dt"].year < son]
    ic_t = [r for r in egitim if r["dt"].year == son]
    egri = egit(ic_e, alanlar, MAKS_AGAC, dogrulama=ic_t)["ap_egrisi"]
    en_iyi = max(egri, key=lambda c: (c[1], -c[0]))[0]
    return egit(egitim, alanlar, en_iyi), en_iyi


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def platt_uydur(ciftler: list, l2: float = 1e-3) -> tuple:
    """[(p, y)] -> (a, b): p' = sigmoid(a*logit(p) + b). Newton, 2 parametre."""
    a, b = 1.0, 0.0
    for _ in range(50):
        ga = gb = haa = hab = hbb = 0.0
        for p, y in ciftler:
            x = _logit(p)
            q = _sigmoid(a * x + b)
            r, w = q - float(bool(y)), q * (1 - q)
            ga += r * x
            gb += r
            haa += w * x * x
            hab += w * x
            hbb += w
        haa += l2
        hbb += l2
        det = haa * hbb - hab * hab
        if det <= 0:
            break
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        a, b = a - da, b - db
        if abs(da) + abs(db) < 1e-9:
            break
    return a, b


def platt_uygula(p: float, ab: tuple) -> float:
    return _sigmoid(ab[0] * _logit(p) + ab[1])


KALIBRASYON_YILI = 3


def kalibrasyon_ciftleri(egitim: list, alanlar, agac: int,
                         yil_sayisi: int = KALIBRASYON_YILI) -> list:
    """Egitimin son `yil_sayisi` yilinin DONEM-DISI tahminleri: her yil, o
    yildan ONCEKI yillarla egitilmis modelle tahmin edilir. [(p, y)]

    Tek yillik kalibrasyon (ilk deneme) o yilin karakterine fazla bagliydi:
    olayli 2014 haritayi yukari itip 2015-16'yi bozdu. Birden fazla yil bu
    oynakligi dengeler (kalibrasyon.py Model A icin ayni ilkeyi kullanir).
    yil_sayisi=3 sonuclara bakilmadan secildi."""
    yillar = sorted({r["dt"].year for r in egitim})
    ciftler = []
    for yil in yillar[1:][-yil_sayisi:]:
        once = [r for r in egitim if r["dt"].year < yil]
        bu = [r for r in egitim if r["dt"].year == yil]
        if not any(r["hedef"] for r in once):
            continue
        m = egit(once, alanlar, agac)
        ciftler += [(olasilik(m, r), bool(r["hedef"])) for r in bu]
    return ciftler


def egit_kalibreli(egitim: list, alanlar=qv3_model.ADAYLAR) -> dict:
    """Agac sayisi egitimin son yilinda; kalibrasyon haritalari son
    KALIBRASYON_YILI yilin donem-disi tahminleriyle; nihai model tum
    egitimle. {"model", "agac", "platt", "izotonik", "kalibrasyon_n"}"""
    son = max(r["dt"].year for r in egitim)
    ic_e = [r for r in egitim if r["dt"].year < son]
    ic_t = [r for r in egitim if r["dt"].year == son]
    egri = egit(ic_e, alanlar, MAKS_AGAC, dogrulama=ic_t)["ap_egrisi"]
    n = max(egri, key=lambda c: (c[1], -c[0]))[0]
    ciftler = kalibrasyon_ciftleri(egitim, alanlar, n)
    return {"model": egit(egitim, alanlar, n), "agac": n,
            "platt": platt_uydur(ciftler), "kalibrasyon_n": len(ciftler),
            "izotonik": kalibrasyon.kalibrasyon_tablosu(kalibrasyon.izotonik_uydur(ciftler))}


def olasilik(m: dict, kayit: dict) -> float:
    kv = [kova(kayit.get(a), m["sinirlar"][a]) for a in m["alanlar"]]
    return _sigmoid(m["f0"] + sum(_agac_tahmin(t, kv) for t in m["agaclar"]))


def onem(m: dict) -> list:
    """[(alan, toplam kazanc payi)] - hangi degisken ne kadar kullanildi."""
    sayac = Counter()

    def gez(d):
        if "alan" in d:
            sayac[m["alanlar"][d["alan"]]] += d["kazanc"]
            gez(d["sol"])
            gez(d["sag"])

    for t in m["agaclar"]:
        gez(t)
    toplam = sum(sayac.values()) or 1.0
    return [(a, v / toplam) for a, v in sayac.most_common()]


def _olc(p, g, ik) -> str:
    return (f"AP {degerlendir.ortalama_kesinlik(p, g):.3f}  AUC {degerlendir.roc_auc(p, g):.3f}  "
            f"Brier {degerlendir.brier(p, g):.5f}  BSS {degerlendir.brier_skill(p, g, ik):+.3f}  "
            f"ort. tahmin %{100 * sum(p) / len(p):.2f}")


def main() -> int:
    aday = qv3_model.aday_ekle(qv3_hedef.veri_hazirla(veri_oku(VARSAYILAN_VERI),
                                                      qv3_hedef.rvr_oku()))
    gelistirme = bolme.gelistirme(aday)
    print(f"Geliştirme evreni (2012-2023, holdout kapalı): {len(gelistirme)} an, "
          f"{sum(r['hedef'] for r in gelistirme)} pozitif\n")
    turler = ("ham", "Platt", "izotonik")
    tum = {t: [] for t in turler}
    tum_g, tum_iklim = [], []
    onem_toplam = Counter()
    for egitim_yillari, test_yillari in bolme.foldlar():
        egitim = bolme.ayir(gelistirme, egitim_yillari)
        test = bolme.ayir(gelistirme, test_yillari)
        k = egit_kalibreli(egitim)
        ham = [olasilik(k["model"], r) for r in test]
        p = {"ham": ham,
             "Platt": [platt_uygula(x, k["platt"]) for x in ham],
             "izotonik": [kalibrasyon.kalibre_uygula(x, k["izotonik"]) for x in ham]}
        g = [bool(r["hedef"]) for r in test]
        iklim = model.iklim_baseline(egitim)
        ik = [model.iklim_tahmin(iklim, r) for r in test]
        print(f"=== Test {test_yillari[0]}-{test_yillari[-1]}: {k['agac']} ağaç, "
              f"Platt a={k['platt'][0]:.2f} b={k['platt'][1]:+.2f} "
              f"({k['kalibrasyon_n']} an), "
              f"gerçekleşen %{100 * sum(g) / len(g):.2f}")
        for t in turler:
            print(f"  {t:<9} {_olc(p[t], g, ik)}")
            tum[t] += p[t]
        o = onem(k["model"])
        print("  önem: " + ", ".join(f"{a} {v:.0%}" for a, v in o[:8]))
        onem_toplam.update(dict(o))
        tum_g += g
        tum_iklim += ik
    print(f"\n=== TOPLAM (2015-2023), {sum(tum_g)} pozitif, "
          f"gerçekleşen %{100 * sum(tum_g) / len(tum_g):.2f}")
    for t in turler:
        print(f"  {t:<9} {_olc(tum[t], tum_g, tum_iklim)}")
    print("  güvenilirlik (Platt): " + "; ".join(
        f"{k['ortalama_tahmin']:.0%}->{k['gerceklesen']:.0%} (n={k['n']})"
        for k in degerlendir.guvenilirlik(tum["Platt"], tum_g, kova_sayisi=10) if k["n"]))
    print("Ortalama önem: " + ", ".join(
        f"{a} {v / 4:.0%}" for a, v in onem_toplam.most_common(10)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
