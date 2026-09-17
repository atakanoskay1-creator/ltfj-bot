#!/usr/bin/env python3
"""Yuruyen pencere (walk-forward) bolme + dokunulmamis nihai holdout.

NEDEN RASTGELE 80/20 DEGIL:
Sis bir OLAY olarak saatlerce surer; rastgele bolmede ayni olayin satirlari
hem egitime hem teste duser ve model o olayi ezberler. Ayrica model gercekte
GELECEGI tahmin edecek - durust test "gecmisle egit, gelecegi bil" olmalidir.

NEDEN TEK SABIT BOLME DEGIL:
Tek bir test doneminde yalnizca ~40 onset olayi kaliyor ve yillik degiskenlik
cok yuksek (yila gore 9-38 olay). Tek skorun guven araligi cok genis olur.
Yuruyen pencerede her fold yalnizca KENDI GECMISIYLE egitilir (sizinti yok)
ama fold'lar boyunca toplam test olayi birikir; ayrica yildan yila kararlilik
dogrudan gorunur.

NIHAI HOLDOUT (HOLDOUT_YILLARI) gelistirme boyunca HIC acilmaz - walk-forward
sonucuna bakarak ayar yapa yapa ona da dolayli overfit etmeyelim diye.
"""

# Arsivin ilk yili (2011 oncesi kapsama yok, 2011 kismi)
ILK_YIL = 2011
# Ilk fold'un egitim donemi bu yilda biter, test sonraki FOLD_UZUNLUK yildir.
ILK_EGITIM_SON = 2014
FOLD_UZUNLUK = 2          # tek yil bazen 9 olaya duser - 2 yillik fold
# Bu yillara gelistirme boyunca DOKUNULMAZ.
HOLDOUT_YILLARI = (2024, 2025, 2026)


def foldlar(son_yil: int = None) -> list[tuple]:
    """[(egitim_yillari, test_yillari), ...] dondurur.

    Egitim her zaman ILK_YIL'dan test doneminin BASLANGICINA kadar genisler
    (genisleyen pencere) - boylece her fold, o tarihte gercekten elde olacak
    veriyle egitilmis olur."""
    son = min(son_yil or (min(HOLDOUT_YILLARI) - 1), min(HOLDOUT_YILLARI) - 1)
    cikti = []
    egitim_son = ILK_EGITIM_SON
    while egitim_son + FOLD_UZUNLUK <= son:
        test = tuple(range(egitim_son + 1, egitim_son + 1 + FOLD_UZUNLUK))
        cikti.append((tuple(range(ILK_YIL, egitim_son + 1)), test))
        egitim_son += FOLD_UZUNLUK
    # Artan tek yil kalirsa son fold'a ekle (yalniz basina cok ince olurdu)
    if egitim_son < son:
        egitim, test = cikti[-1]
        cikti[-1] = (egitim, test + tuple(range(egitim_son + 1, son + 1)))
    return cikti


def ayir(kayitlar: list, yillar: tuple) -> list:
    return [r for r in kayitlar if r["dt"].year in yillar]


def holdout(kayitlar: list) -> list:
    """Nihai test seti - yalnizca model dondurulduktan SONRA acilir."""
    return ayir(kayitlar, HOLDOUT_YILLARI)


def gelistirme(kayitlar: list) -> list:
    """Holdout DISINDAKI her sey - walk-forward burada calisir."""
    return [r for r in kayitlar if r["dt"].year not in HOLDOUT_YILLARI]
