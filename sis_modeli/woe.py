#!/usr/bin/env python3
"""Degisken tarama: WoE (Weight of Evidence), IV (Information Value),
monotonluk ve kararlilik (PSI).

Model kurmadan ONCE hangi degiskenin gercekten bilgi tasidigini, iliskinin
yonunun mantikli olup olmadigini ve zaman icinde kayip kaymadigini gosterir.

OTOKORELASYON TUZAGI (bu modulun en onemli tasarim karari):
Arsivde 273.000+ satir var ama sadece ~305 BAGIMSIZ sis olayi. Sis saatlerce
surdugu icin tek bir olay ~12 satir uretir. Satir bazinda ki-kare/p-degeri
hesaplanirsa HER SEY anlamli cikar - cunku bagimsizlik varsayimi coker.
Bu yuzden anlamlilik GUN BAZINDA BLOK BOOTSTRAP ile olculur: gunler
yeniden orneklenip IV'nin guven araligi cikarilir. IV'nin kendisi betimsel
bir olcu oldugu icin satir bazinda hesaplanabilir, ama GUVEN ARALIGI
mutlaka blok bazinda olmalidir.

Bagimlilik yok (numpy/pandas dahil): saf standart kutuphane.
"""

import math
import random
from collections import Counter, defaultdict

# Kova birlestirme MUTLAK gozlem sayisina gore yapilir, ORANA gore DEGIL.
#
# Neden: nadir olayda sinyal tanimi geregi verinin kucuk bir kisminda oturur.
# Gorus degiskeninde gozlemlerin %87'si 9999-10000 m; bilgi tasiyan dusuk
# gorus bolgesi ise verinin %3'unden azi. Oransal bir alt sinir (eski
# KOVA_MIN_ORAN=%3) tam da bu bolgeyi komsusuna katip sinyali yok ediyordu -
# gorus 3 kovaya dusuyor ve model sureklilik baseline'ina yeniliyordu.
# Mutlak sinir bunu cozer: 200+ gozlemli bir kova, verinin %0.3'u olsa bile
# guvenilir bir oran tahmini verir.
KOVA_MIN_GOZLEM = 200
# Bunun altinda pozitifi olan kova "kararsiz" olarak ISARETLENIR ama
# birlestirilmez - birlestirmek nadir olayda sinyali yok eder.
KOVA_MIN_POZITIF = 10

# WoE'de sifira bolmeyi onleyen duzeltme (Haldane-Anscombe)
DUZELTME = 0.5

# Yaygin IV yorum esikleri (kredi skorlama gelenegi).
#
# DIKKAT - bu esikler %5-20 taban oranli kredi verisi icin kalibre edilmistir.
# Buradaki taban oran ~%0.7; nadir olayda kucuk ama cok yuksek oranli bir kova
# WoE'yi buyuttugu icin IV YAPISAL OLARAK sisar. Gercek olcumde spread 3.03,
# gorus 1.87 cikti ve ikisi de sizinti DEGIL (lead time'a gore ayristirildi:
# gorusun IV'si ufukla birlikte duzgunce eriyor - sureklilik imzasi; spread'inki
# erimiyor cunku doymus hava saatlerce doymus kalir). Yani bu esiklere gore
# "cok guclu" damgasi tek basina sizinti kaniti sayilmamalidir; karar lead time
# ayristirmasiyla verilir.
IV_YORUM = (
    (0.02, "işe yaramaz"),
    (0.10, "zayıf"),
    (0.30, "orta"),
    (0.50, "güçlü"),
    (float("inf"), "çok güçlü (nadir olayda beklenir)"),
)


def iv_yorumla(iv: float) -> str:
    for esik, ad in IV_YORUM:
        if iv < esik:
            return ad
    return "?"


def _esitlik_kovalari(degerler: list, hedef_kova: int) -> list:
    """Kova sinirlari uretir.

    Once esit frekansli (quantile) sinirlar denenir. Ancak dagilim tek bir
    degerde yigilmissa (gorus: gozlemlerin %87'si 9999-10000 m) quantile
    sinirlari cakisir ve elde cok az sinir kalir - tam da bilgi tasiyan
    seyrek kuyruk tek kovaya sikisir. Bu durumda FARKLI DEGERLER uzerinden
    de sinir uretilir, boylece seyrek ama ayirt edici bolge cozunur."""
    sirali = sorted(degerler)
    n = len(sirali)
    sinirlar = []
    for k in range(1, hedef_kova):
        d = sirali[k * n // hedef_kova]
        if not sinirlar or d > sinirlar[-1]:
            sinirlar.append(d)

    # Yigilmis dagilim: quantile yeterli sinir uretemedi
    if len(sinirlar) < hedef_kova // 2:
        farkli = sorted(set(sirali))
        if len(farkli) > 2:
            ek = []
            for k in range(1, hedef_kova):
                d = farkli[k * len(farkli) // hedef_kova]
                if d not in ek:
                    ek.append(d)
            sinirlar = sorted(set(sinirlar) | set(ek))
    return sinirlar


def _kovala(deger, sinirlar: list) -> int:
    for i, s in enumerate(sinirlar):
        if deger < s:
            return i
    return len(sinirlar)


def kova_tablosu(satirlar: list, alan: str, hedef: str,
                 sinirlar: list = None, hedef_kova: int = 8) -> list[dict]:
    """Bir degisken icin kova bazinda WoE tablosu uretir.

    sinirlar verilmezse esit frekansli kovalar kurulur, sonra KOVA_MIN_ORAN /
    KOVA_MIN_POZITIF kosulunu saglamayan kovalar komsusuyla BIRLESTIRILIR."""
    veri = [(r[alan], r[hedef]) for r in satirlar if r.get(alan) is not None]
    if not veri:
        return []
    if sinirlar is None:
        sinirlar = _esitlik_kovalari([d for d, _ in veri], hedef_kova)

    def say(sinirlar):
        top, poz = Counter(), Counter()
        for d, y in veri:
            k = _kovala(d, sinirlar)
            top[k] += 1
            poz[k] += int(bool(y))
        return top, poz

    # Kucuk kovalari komsuya kat. SADECE BOYUTA gore birlestirilir, pozitif
    # sayisina gore DEGIL: nadir olayda sinyal tek bir kovada yogunlasabilir
    # (ornegin sis yalnizca spread~0'da olur) ve pozitifsiz kovalari
    # birlestirmek o ayrimi tamamen yok eder - degisken en bilgilendirici
    # halindeyken IV=0 okunur. Pozitifsiz kovada WoE'yi Haldane-Anscombe
    # duzeltmesi zaten sonlu tutuyor; kararsizligi da blok bootstrap araligi
    # gosteriyor. (Bu, sentetik testte yakalanan gercek bir hataydi.)
    while sinirlar:
        top, _ = say(sinirlar)
        zayif = [k for k in sorted(top) if top[k] < KOVA_MIN_GOZLEM]
        if not zayif:
            break
        sinirlar.pop(min(zayif[0], len(sinirlar) - 1))

    top, poz = say(sinirlar)
    toplam_poz = sum(poz.values())
    toplam_neg = sum(top.values()) - toplam_poz
    if toplam_poz == 0 or toplam_neg == 0:
        return []

    tablo = []
    for k in sorted(top):
        p, t = poz[k], top[k]
        neg = t - p
        # Haldane-Anscombe duzeltmesi: bos hucrede WoE sonsuz olmasin
        poz_oran = (p + DUZELTME) / (toplam_poz + DUZELTME * len(top))
        neg_oran = (neg + DUZELTME) / (toplam_neg + DUZELTME * len(top))
        woe = math.log(poz_oran / neg_oran)
        tablo.append({
            "kova": k,
            "alt": None if k == 0 else sinirlar[k - 1],
            "ust": None if k == len(sinirlar) else sinirlar[k],
            "n": t,
            "pozitif": p,
            "oran": p / t,
            "woe": woe,
            "iv_katki": (poz_oran - neg_oran) * woe,
            "kararsiz": p < KOVA_MIN_POZITIF,
        })
    return tablo


def iv(tablo: list[dict]) -> float:
    return sum(k["iv_katki"] for k in tablo)


def monoton_mu(tablo: list[dict]) -> bool:
    """WoE kovalar boyunca tek yonlu mu ilerliyor? Degilse iliski ya gercekten
    dogrusal-disidir (ornegin gun saati) ya da gurultudur."""
    w = [k["woe"] for k in tablo]
    artan = all(a <= b for a, b in zip(w, w[1:]))
    azalan = all(a >= b for a, b in zip(w, w[1:]))
    return artan or azalan


def _iv_sayaclardan(top: dict, poz: dict) -> float:
    """Kova bazinda (toplam, pozitif) sayaclarindan dogrudan IV.

    Satir listesi uzerinden degil SAYAC uzerinden calisir; bootstrap her
    tekrarda 230.000 satiri yeniden kovalamak yerine gun sayaclarini
    toplayabilsin diye ayrildi (aksi halde tarama dakikalar suruyor)."""
    toplam_poz = sum(poz.values())
    toplam_neg = sum(top.values()) - toplam_poz
    if toplam_poz <= 0 or toplam_neg <= 0:
        return 0.0
    kova_sayisi = len(top) or 1
    deger = 0.0
    for k in top:
        p, t = poz.get(k, 0), top[k]
        poz_oran = (p + DUZELTME) / (toplam_poz + DUZELTME * kova_sayisi)
        neg_oran = (t - p + DUZELTME) / (toplam_neg + DUZELTME * kova_sayisi)
        deger += (poz_oran - neg_oran) * math.log(poz_oran / neg_oran)
    return deger


def iv_guven_araligi(satirlar: list, alan: str, hedef: str, gun_alani: str,
                     sinirlar: list, tekrar: int = 200, tohum: int = 0) -> tuple:
    """GUN BAZINDA BLOK BOOTSTRAP ile IV'nin %5-%95 araligi.

    Satirlar bagimsiz DEGIL (bir sis olayi ~12 satir uretir), bu yuzden
    satir bazinda yeniden ornekleme guven araligini SAHTE sekilde daraltir.
    Gunleri blok olarak yeniden ornekleyerek otokorelasyon korunur."""
    # Gun x kova sayaclarini BIR KEZ hesapla
    gun_top, gun_poz = defaultdict(Counter), defaultdict(Counter)
    for r in satirlar:
        d = r.get(alan)
        if d is None:
            continue
        k = _kovala(d, sinirlar)
        gun = r[gun_alani]
        gun_top[gun][k] += 1
        gun_poz[gun][k] += int(bool(r[hedef]))

    anahtarlar = list(gun_top)
    if not anahtarlar:
        return (0.0, 0.0)
    rastgele = random.Random(tohum)

    sonuclar = []
    for _ in range(tekrar):
        top, poz = Counter(), Counter()
        for _ in anahtarlar:
            a = rastgele.choice(anahtarlar)
            top.update(gun_top[a])
            poz.update(gun_poz[a])
        sonuclar.append(_iv_sayaclardan(top, poz))
    sonuclar.sort()
    return (sonuclar[int(0.05 * len(sonuclar))],
            sonuclar[min(int(0.95 * len(sonuclar)), len(sonuclar) - 1)])


def psi(referans: list, guncel: list, alan: str, sinirlar: list) -> float:
    """Population Stability Index: degiskenin DAGILIMI iki donem arasinda
    kaymis mi? (>0.25 ciddi kayma). Model egitildigi donemin disinda
    calisacaksa bu kontrol sart - olay sayilarinin yillara gore cok
    degistigini zaten gorduk."""
    def dagilim(kayitlar):
        s = Counter()
        gecerli = [r[alan] for r in kayitlar if r.get(alan) is not None]
        for d in gecerli:
            s[_kovala(d, sinirlar)] += 1
        n = len(gecerli) or 1
        return {k: max(s[k], 1) / n for k in range(len(sinirlar) + 1)}

    r, g = dagilim(referans), dagilim(guncel)
    return sum((g[k] - r[k]) * math.log(g[k] / r[k]) for k in r)
