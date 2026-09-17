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


# --------------------------------------------------------- sinir embargosu
#
# NEDEN GEREKLI: hedef.hazirla() TUM (henuz bolunmemis) arsiv uzerinde
# calisir - bkz. egit.py/holdout_degerlendir.py: once hedef.hazirla(ham),
# SONRA bolme.gelistirme()/ayir() ile bolunuyor. Bunun somut sonucu: bir
# egitim satirinin ileriye bakan hedef penceresi (UFUK_SAAT saat) disarida
# kalan bir donemin (bir sonraki fold'un test'i veya holdout) HAM
# gozlemlerini kullanmis olabilir. Ornek: 31 Aralik 23:30'daki bir satirin
# hedefi, 1 Ocak 00:00-02:30 kayitlarina (ertesi donem) bakarak hesaplanir.
#
# Bu FEATURE sizintisi DEGIL (model hicbir zaman gelecek bir DEGERI girdi
# olarak gormuyor) - bir ETIKET (y) sinir kontaminasyonudur: sinira yakin
# birkac satirin etiketi, nominal olarak "disarida" olan bir donemin ham
# verisinden etkilenmis olabilir. Etkilenen satir sayisi kucuktur (sinir
# basina en fazla UFUK_SAAT saatlik pencere) ama gercektir ve yeni bir
# deney icin (ozellikle zayif sinyalli gorussuz modelde) kapatilmasi
# onerilir. Mevcut donmus modelleri (sis, tavan) BOZMADAN, yalnizca yeni
# calismalarin ISTEGE BAGLI kullanabilecegi bir yardimci olarak eklendi.
def embargo_penceresi(kayitlar: list, sinir_yil: int, saat: float = None) -> list:
    """kayitlar icinden, sinir_yil'in 1 Ocak 00:00'ina giden `saat`'lik
    pencereye dusen satirlari CIKARIR (etiketi degil, satirin kendisini).

    `saat` verilmezse kayitlardaki 'hedef_ufuk_saat' alanindan (hedef.hazirla
    tarafindan eklenir) otomatik alinir - ufuk degisirse embargo da otomatik
    dogru kalir."""
    from datetime import datetime, timedelta

    if saat is None:
        ufuklar = {r["hedef_ufuk_saat"] for r in kayitlar if "hedef_ufuk_saat" in r}
        saat = max(ufuklar) if ufuklar else 3.0
    sinir = datetime(sinir_yil, 1, 1)
    pencere_baslangic = sinir - timedelta(hours=saat)
    return [r for r in kayitlar if not (pencere_baslangic <= r["dt"] < sinir)]


def ayir_embargolu(kayitlar: list, yillar: tuple, sonraki_yil: int = None,
                   saat: float = None) -> list:
    """ayir() + embargo_penceresi() - egitim/fold kumesini SINIRA GIDEN
    pencere disarida birakilarak dondurur.

    sonraki_yil verilmezse yillar'in bir sonraki yili varsayilir (walk-forward
    fold'larda test donemi hep egitim yillarinin hemen ardindan basladigi
    icin bu varsayilan dogru sinirdir)."""
    alt_kume = ayir(kayitlar, yillar)
    if not alt_kume:
        return alt_kume
    sinir_yil = sonraki_yil if sonraki_yil is not None else max(yillar) + 1
    return embargo_penceresi(alt_kume, sinir_yil, saat)
