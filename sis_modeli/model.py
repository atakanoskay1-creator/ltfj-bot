#!/usr/bin/env python3
"""WoE tabanli lojistik regresyon + karsilastirma baseline'lari.

BAGIMLILIK YOK: egitim de tahmin de saf standart kutuphane. 8 degiskenli bir
lojistik regresyon icin numpy/sklearn getirmek, projenin "gereksiz bagimlilik
yok" ilkesini sirf kolaylik icin bozmak olurdu. Ayrica boylece egitilmis model
CALISMA ANINDA sadece bir katsayi tablosu + aritmetik olarak tasinabilir
(bkz. sis_modeli/README.md - izolasyon sozlesmesi).

Yontem: degiskenler once WoE'ye cevrilir (dogrusal-disi iliskiyi fonksiyonel
form tahmin etmeden yakalar, olceklemeyi de halleder), sonra L2 cezali
lojistik regresyon IRLS ile cozulur. IRLS ~5-10 iterasyonda yakinsar; gradyan
inisi yuzlerce adim isterdi.

HIZ: ayni WoE kova kombinasyonuna dusen satirlar TEK bir desende toplanir
(agirlikli regresyon). 190.000 satir tipik olarak birkac bin desene iner.
"""

import math
from collections import Counter, defaultdict

from sis_modeli import woe

# Sayisal guvenlik: sigmoid'i 0/1'e tam yapistirmayalim (log(0) olmasin)
EPS = 1e-9
# L2 ceza katsayisi. Nadir olayda (305 bagimsiz olay) duzenlilestirme sart -
# aksi halde ayrik kovalarda katsayilar sonsuza kacar.
L2 = 1.0
MAKS_ITER = 30
YAKINSAMA = 1e-7


def woe_tablolari(egitim: list, alanlar: list, hedef: str = "hedef") -> dict:
    """Her degisken icin WoE tablosu (kova sinirlari + WoE degerleri).

    YALNIZCA EGITIM verisinden uretilir; test donemi kova sinirlarini
    belirlemeye KATILMAZ, aksi halde gelecege bakmis oluruz."""
    tablolar = {}
    for a in alanlar:
        t = woe.kova_tablosu(egitim, a, hedef)
        if t:
            tablolar[a] = t
    return tablolar


def _woe_degeri(tablo: list, deger) -> float:
    """Bir degeri ait oldugu kovanin WoE'sine cevirir. Eksik deger (None)
    icin 0 doner - yani 'bilgi yok, taban orandan sapma yok'."""
    if deger is None:
        return 0.0
    sinirlar = [k["ust"] for k in tablo[:-1]]
    return tablo[woe._kovala(deger, sinirlar)]["woe"]


def desen(kayit: dict, tablolar: dict) -> tuple:
    return tuple(_woe_degeri(t, kayit.get(a)) for a, t in sorted(tablolar.items()))


def desenlere_topla(kayitlar: list, tablolar: dict, hedef: str = "hedef") -> tuple:
    """Ayni WoE desenine dusen satirlari (toplam, pozitif) olarak toplar."""
    toplam, pozitif = Counter(), Counter()
    for r in kayitlar:
        d = desen(r, tablolar)
        toplam[d] += 1
        pozitif[d] += int(bool(r[hedef]))
    desenler = list(toplam)
    return desenler, [toplam[d] for d in desenler], [pozitif[d] for d in desenler]


class TekilSistem(Exception):
    """IRLS sistemi tekil/kotu kosullu - katsayilar cozulemedi.

    SESSIZCE SIFIR DONDURMEK YASAK: onceki surum tekil matriste [0,0,...]
    donduruyordu; model sabit tahmin uretiyor, AP tam taban orana esitleniyor
    ve bu 'modelleme sonucu' sanilip raporlanabiliyordu. Gercek nedeni
    (ayrisma/es-dogrusallik) gizleyen bu davranis bir kez yanlis yoruma yol
    acti - artik acikca hata firlatilir."""


def _coz(A: list, b: list) -> list:
    """Kucuk simetrik sistemi Gauss elemesiyle cozer (8x8 civari)."""
    n = len(b)
    M = [satir[:] + [b[i]] for i, satir in enumerate(A)]
    for i in range(n):
        p = max(range(i, n), key=lambda k: abs(M[k][i]))
        if abs(M[p][i]) < 1e-12:
            raise TekilSistem(f"{i}. eksende pivot ~0 - L2 artirilmali")
        M[i], M[p] = M[p], M[i]
        pivot = M[i][i]
        for k in range(i + 1, n):
            c = M[k][i] / pivot
            if c:
                for j in range(i, n + 1):
                    M[k][j] -= c * M[i][j]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = M[i][n] - sum(M[i][j] * x[j] for j in range(i + 1, n))
        x[i] = s / M[i][i]
    return x


def egit_secerek(egitim: list, alanlar: list, adaylar=(10.0, 50.0, 200.0, 1000.0),
                 ic_dogrulama_yili: int = None, hedef_alan: str = "hedef") -> tuple:
    """L2'yi EGITIM VERISININ ICINDE secer ve (katsayilar, tablolar, l2) doner.

    L2'yi walk-forward sonuclarina bakarak secmek, degerlendirme setine ayar
    yapmak olurdu (dolayli overfit). Bunun yerine her fold'un kendi egitim
    donemi ikiye ayrilir: son yil ic dogrulama, oncesi ic egitim."""
    yillar = sorted({r["dt"].year for r in egitim})
    if len(yillar) < 2:
        tablolar = woe_tablolari(egitim, alanlar, hedef_alan)
        d, t, p = desenlere_topla(egitim, tablolar, hedef_alan)
        return egit(d, t, p, l2=adaylar[len(adaylar) // 2]), tablolar, adaylar[len(adaylar) // 2]

    sinir = ic_dogrulama_yili or yillar[-1]
    ic_egitim = [r for r in egitim if r["dt"].year < sinir]
    ic_test = [r for r in egitim if r["dt"].year >= sinir]
    if not ic_egitim or not any(r[hedef_alan] for r in ic_test):
        ic_egitim, ic_test = egitim, egitim

    ic_tablolar = woe_tablolari(ic_egitim, alanlar, hedef_alan)
    d, t, p = desenlere_topla(ic_egitim, ic_tablolar, hedef_alan)
    ic_gercek = [bool(r[hedef_alan]) for r in ic_test]

    en_iyi, en_iyi_l2 = -1.0, adaylar[-1]
    for l2 in adaylar:
        try:
            beta = egit(d, t, p, l2=l2)
        except TekilSistem:
            continue
        tahmin = [olasilik(beta, r, ic_tablolar) for r in ic_test]
        skor = _ortalama_kesinlik(tahmin, ic_gercek)
        if skor > en_iyi:
            en_iyi, en_iyi_l2 = skor, l2

    # secilen L2 ile TUM egitim verisinde yeniden egit
    tablolar = woe_tablolari(egitim, alanlar, hedef_alan)
    d, t, p = desenlere_topla(egitim, tablolar, hedef_alan)
    return egit(d, t, p, l2=en_iyi_l2), tablolar, en_iyi_l2


def _ortalama_kesinlik(tahminler: list, gercekler: list) -> float:
    """degerlendir.ortalama_kesinlik ile ayni - dairesel import olmasin diye
    burada kucuk bir kopya tutuluyor (model -> degerlendir bagimliligi yok)."""
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


def egit(desenler: list, toplam: list, pozitif: list, l2: float = L2) -> list:
    """Agirlikli, L2 cezali lojistik regresyon (IRLS). Katsayi listesi doner;
    ilk eleman sabit terim (intercept)."""
    if not desenler:
        return [0.0]
    p_sayi = len(desenler[0]) + 1                 # +1 sabit terim
    beta = [0.0] * p_sayi
    # sabit terimi taban orandan baslat - yakinsamayi hizlandirir
    toplam_n, toplam_k = sum(toplam), sum(pozitif)
    if 0 < toplam_k < toplam_n:
        beta[0] = math.log(toplam_k / (toplam_n - toplam_k))

    X = [(1.0,) + d for d in desenler]
    for _ in range(MAKS_ITER):
        XtWX = [[0.0] * p_sayi for _ in range(p_sayi)]
        XtWz = [0.0] * p_sayi
        for x, n, k in zip(X, toplam, pozitif):
            eta = sum(b * xi for b, xi in zip(beta, x))
            p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, eta))))
            p = min(max(p, EPS), 1 - EPS)
            w = n * p * (1 - p)
            z = eta + (k - n * p) / (n * p * (1 - p))
            for i in range(p_sayi):
                wx = w * x[i]
                XtWz[i] += wx * z
                for j in range(i, p_sayi):
                    XtWX[i][j] += wx * x[j]
        for i in range(p_sayi):                   # simetrik tamamla + L2
            for j in range(i):
                XtWX[i][j] = XtWX[j][i]
            if i > 0:                             # sabit terim cezalandirilmaz
                XtWX[i][i] += l2

        yeni = _coz(XtWX, XtWz)
        fark = max(abs(a - b) for a, b in zip(yeni, beta))
        beta = yeni
        if fark < YAKINSAMA:
            break
    return beta


def olasilik(katsayilar: list, kayit: dict, tablolar: dict) -> float:
    x = (1.0,) + desen(kayit, tablolar)
    eta = sum(b * xi for b, xi in zip(katsayilar, x))
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, eta))))


# ------------------------------------------------------------- baseline'lar
def iklim_baseline(egitim: list, hedef: str = "hedef") -> dict:
    """Ay x saat taban orani - hava durumuna HIC bakmaz. Model bunu yenemezse
    hicbir sey ogrenmemis demektir."""
    top, poz = Counter(), Counter()
    for r in egitim:
        a = (r["ay"], r["saat"])
        top[a] += 1
        poz[a] += int(bool(r[hedef]))
    genel = (sum(poz.values()) + 1) / (sum(top.values()) + 2)
    # Laplace duzeltmesi: az gozlemli hucre genel orana cekilir
    return {a: (poz[a] + 2 * genel) / (top[a] + 2) for a in top}, genel


def iklim_tahmin(model, kayit: dict) -> float:
    tablo, genel = model
    return tablo.get((kayit["ay"], kayit["saat"]), genel)


def sureklilik_baseline(kayit: dict) -> float:
    """Mevcut gorus ne kadar dusukse o kadar yuksek olasilik - 'hava zaten
    kapali' sezgisi. Onset gorevinde sis YOK oldugu icin bu, esige ne kadar
    yakin oldugumuzu olcer."""
    g = kayit.get("gorus")
    if g is None:
        return 0.01
    if g < 2000:
        return 0.20
    if g < 5000:
        return 0.05
    if g < 9999:
        return 0.01
    return 0.002


def basit_kural_baseline(kayit: dict) -> float:
    """Mevcut ltfj_pist.sis_riski() sezgisel yonteminin ozu: dusuk spread +
    sakin ruzgar. Tarama bu kuralin ruzgar ayaginin ise yaramadigini
    gosterdi (IV 0.09) - model bunu yenmeli."""
    sp, rz = kayit.get("spread"), kayit.get("ruzgar_hiz")
    if sp is None:
        return 0.01
    if sp <= 1 and (rz is None or rz <= 5):
        return 0.25
    if sp <= 2:
        return 0.08
    if sp <= 3:
        return 0.02
    return 0.002
