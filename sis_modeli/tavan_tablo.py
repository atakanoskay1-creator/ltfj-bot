#!/usr/bin/env python3
"""Iki degiskenli, kalibre edilmis dusuk-tavan olasilik TABLOSU.

NEDEN TABLO, NEDEN MODEL DEGIL: bkz. sis_modeli/tavan.py bas kismi. Ozetle
LVO icin asil onemli esikte (<200 ft) yalnizca ~61 bagimsiz olay var;
lojistik regresyon icin kabul ettigimiz 150 olay tabaninin altinda. Olay
sayisi yeten <500 ft esiginde ise tablo kuruluyor - parametre sayisi az,
her hucre dogrudan okunabiliyor ve belirsizligi hucre basina gosterilebiliyor.

TABLONUN OKUMA BIRIMI "KAT"TIR, MUTLAK YUZDE DEGIL. Bu bir tercih degil,
olcum sonucu: gelistirme (2017-2023) tablosu holdout'ta (2024-2026) sinaninca
hucre katlarinin log korelasyonu 0.986 cikti - yani SIRALAMA aynen tasiniyor -
ama kat oranlarinin medyani 2.27, yani SEVIYE tasinmiyor. Gelistirmede
ogrenilen %9.8, holdout'ta %14.0 olarak gerceklesiyor. Tabloyu yuzde olarak
yayinlamak, olculmus 2.3 kat hatayi kesin bir sayi gibi sunmak olurdu.

HUCRE OLASILIGI ham orandan DEGIL, marjinale dogru BUZULTULMUS (shrunk)
orandan gelir:

    p = (pozitif + K * taban_oran) / (n + K),   K = woe.KOVA_MIN_GOZLEM

K, projenin baska yerinde de kullanilan "200 gozlem guvenilir bir oran
tahmini verir" kuralinin ayni sayisi - sonuca bakilarak secilmedi. 40
gozlemli bir hucrede 1 pozitif gormek %2.5 degil, taban orana yakin bir sey
demektir; buzulme bunu otomatik yapar ve tabloyu kalibre tutar.

DEGISKEN CIFTI SECIMI gelistirme donemi ICINDE yuruyen pencereyle yapilir;
holdout (2024-2026) yalnizca secim bittikten SONRA, TEK KEZ acilir.

Kullanim:
    python -m sis_modeli.tavan_tablo            # secim + holdout
    python -m sis_modeli.tavan_tablo --secim    # yalnizca cift secimi
"""

import argparse
import sys
from pathlib import Path

from sis_modeli import bolme, degerlendir, tavan, woe
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku

# Buzulme agirligi: kac "sanal gozlem" kadar taban orana cekilecek.
BUZULME = woe.KOVA_MIN_GOZLEM

# Tablonun okunabilir kalmasi icin degisken basina azami bant.
AZAMI_BANT = 5

# BANT SINIRLARI A PRIORI - quantile ile DEGIL.
#
# Once otomatik (esit frekansli) bantlama denendi ve MEKANIK olarak coktu:
# gorus gozlemlerinin %87'si 9999-10000 m'de yigili oldugu icin quantile
# sinirlari cakisti ve gorus 8 bilgilendirici banttan 3'e dustu - tarama
# tablosunda %27 pozitif orani olan <1700 m bandi, %0.5'lik CAVOK kutlesiyle
# ayni hucreye girdi. Bu, woe.py'de zaten belgelenmis bir coku modu.
#
# Yerine projede ZATEN VAR OLAN esikler kullanildi; hicbiri sonuca bakilarak
# secilmedi:
#   spread  -> istatistik.SPREAD_KOVALARI
#   gorus   -> LVO_GORUS_M (550), SIS_GORUS_M (1000), VFR esigi (5000), CAVOK
#   tavan   -> CAT II (500), VFR (1500)
# Olculdu: a priori bantlar her aday cift icin quantile'dan iyi (AP 0.082 vs
# 0.058 en iyi cift icin) - yani sorun degiskenlerde degil bantlamadaydi.
APRIORI_BANTLAR = {
    "spread": [1, 2, 3, 5, 8],
    "gorus": [550, 1000, 5000, 9999],
    "saat": [4, 9, 14, 19],
    "tavan_ozellik": [500, 1000, 1500, 3000],
    "ruzgar_kuzey": [-3, 0, 3],
    # Dondurulmus sis modelinin ciktisi icin log-olcekli bantlar.
    "sis_olasilik": [0.005, 0.02, 0.05, 0.15, 0.35],
    # Bagil nem (%) - doyma esigine (RH->%100) yaklasan klasik meteorolojik
    # esikler; tavan_dis_kaynak_tarama.py taramasindan SONRA degil, o
    # taramanin BULGUSUNA (IV 2.235, guclu monoton) dayanarak eklendi ama
    # sinirlarin kendisi sonuca bakilarak degil, fiziksel esiklerle secildi.
    "acik_meteo_nem_2m": [70, 80, 90, 95],
    # Komsu istasyonun (LTFM) kendi tavani - LTFJ'nin tavan_ozellik'iyle
    # AYNI fiziksel buyukluk, AYNI a priori esikler (CAT II/VFR) tekrar
    # kullanildi - yeni bir esik uydurulmadi.
    "komsu_tavan_ozellik": [500, 1000, 1500, 3000],
}

ADAY_CIFTLER = [
    ("spread", "gorus"),
    ("spread", "tavan_ozellik"),
    ("spread", "saat"),
    ("spread", "ruzgar_kuzey"),
    ("gorus", "tavan_ozellik"),
    ("gorus", "saat"),
    # sis_olasilik (dondurulmus Model A'nin cikisi) simdiye kadar tabloya
    # yalnizca RAKIP bir yontem olarak kiyaslanmisti (_yontemler ->
    # "ham SİS modeli") - hic bir CIFTIN EKSENI olarak denenmedi. Oysa
    # olculdu: Model A'nin ham skoru TEK BASINA holdout'ta tabloyu (AP
    # 0.093) geciyor (AP 0.103, bkz. README "Dikkat çeken sonuç"). spread
    # ve gorus'un asil kazanan cifte zaten yaptigi gibi, sis_olasilik de
    # BURADA gorus/spread'in ayni "hub" rolunu deneyecek sekilde her
    # degiskenle eslendi - tek bir cift onceden secilip kazanmasi
    # beklenmedi (spread'in aday listesindeki tum eslerle simetrik).
    # DIKKAT: sis_olasiligi_ekle()'nin kendi uyarisi burada da gecerli -
    # gelistirme (2017-2023) donemi Model A'nin KENDI egitim donemi
    # icinde, yani asagidaki cift_sec() sonucu o adaylar icin ORNEK ICI
    # (iyimser) olabilir; kazanan cift ancak holdout'ta (Model A icin
    # GERCEKTEN disarida kalan 2024-2026) dogrulanirsa guvenilir sayilir.
    ("sis_olasilik", "spread"),
    ("sis_olasilik", "gorus"),
    ("sis_olasilik", "tavan_ozellik"),
    ("sis_olasilik", "saat"),
    ("sis_olasilik", "ruzgar_kuzey"),
    # DIS KAYNAK ADAYLARI (tavan_dis_kaynak_tarama.py'de tek degiskenli
    # taramada guclu cikanlar - IV 2.235 ve 1.761, bkz. README). AYNI
    # simetride: spread'in orijinal es kumesiyle + sis_olasilik ile eslendi.
    # DIKKAT: komsu_tavan_ozellik icin veri sadece 2018 sonrasi mevcut
    # (LTFM o yil acildi) - rejim penceresinin (2017+) ilk ~1.5 yili bu
    # eksende "veri yok" hucresine duser, cokmez ama o donemde bilgisizdir.
    ("acik_meteo_nem_2m", "spread"),
    ("acik_meteo_nem_2m", "gorus"),
    ("acik_meteo_nem_2m", "tavan_ozellik"),
    ("acik_meteo_nem_2m", "saat"),
    ("acik_meteo_nem_2m", "ruzgar_kuzey"),
    ("acik_meteo_nem_2m", "sis_olasilik"),
    ("komsu_tavan_ozellik", "spread"),
    ("komsu_tavan_ozellik", "gorus"),
    ("komsu_tavan_ozellik", "tavan_ozellik"),
    ("komsu_tavan_ozellik", "saat"),
    ("komsu_tavan_ozellik", "ruzgar_kuzey"),
    ("komsu_tavan_ozellik", "sis_olasilik"),
    ("acik_meteo_nem_2m", "komsu_tavan_ozellik"),
]


def bantlar(egitim: list, alan: str, azami: int = AZAMI_BANT) -> list:
    """Bant sinirlari: a priori liste varsa o, yoksa egitimden quantile."""
    if alan in APRIORI_BANTLAR:
        return list(APRIORI_BANTLAR[alan])
    t = woe.kova_tablosu(egitim, alan, "hedef", hedef_kova=azami)
    return [k["ust"] for k in t[:-1]]


def _bant(deger, sinirlar: list) -> int:
    if deger is None:
        return -1                      # "veri yok" kendi hucresi
    for i, s in enumerate(sinirlar):
        if deger < s:
            return i
    return len(sinirlar)


def tablo_kur(egitim: list, alan_a: str, alan_b: str,
              sinir_a: list = None, sinir_b: list = None) -> dict:
    """(bant_a, bant_b) -> {n, pozitif, ham_oran, olasilik} tablosu."""
    sinir_a = bantlar(egitim, alan_a) if sinir_a is None else sinir_a
    sinir_b = bantlar(egitim, alan_b) if sinir_b is None else sinir_b

    toplam, pozitif = {}, {}
    for r in egitim:
        h = (_bant(r.get(alan_a), sinir_a), _bant(r.get(alan_b), sinir_b))
        toplam[h] = toplam.get(h, 0) + 1
        pozitif[h] = pozitif.get(h, 0) + int(bool(r["hedef"]))

    n_top = sum(toplam.values()) or 1
    taban = sum(pozitif.values()) / n_top

    hucreler = {}
    for h, n in toplam.items():
        p = pozitif[h]
        olasilik = (p + BUZULME * taban) / (n + BUZULME)
        hucreler[h] = {
            "n": n, "pozitif": p, "ham_oran": p / n, "olasilik": olasilik,
            # KAT (lift) = hucre olasiligi / donemin taban orani.
            # Tablonun ASIL cikti birimi budur: mutlak yuzde donemler arasi
            # ~2.2x kayiyor, kat ise tasiniyor (bkz. kat_kararliligi()).
            "kat": olasilik / taban if taban > 0 else 0.0,
        }
    return {"alan_a": alan_a, "alan_b": alan_b, "sinir_a": sinir_a,
            "sinir_b": sinir_b, "taban": taban, "hucreler": hucreler}


def tahmin(tablo: dict, kayit: dict) -> float:
    """Tabloda olmayan hucre icin taban oran dondurulur - uydurma yapilmaz."""
    h = (_bant(kayit.get(tablo["alan_a"]), tablo["sinir_a"]),
         _bant(kayit.get(tablo["alan_b"]), tablo["sinir_b"]))
    hucre = tablo["hucreler"].get(h)
    return tablo["taban"] if hucre is None else hucre["olasilik"]


def _aralik(i: int, sinirlar: list) -> str:
    if i == -1:
        return "veri yok"
    alt = "-∞" if i == 0 else f"{sinirlar[i-1]:g}"
    ust = "+∞" if i == len(sinirlar) else f"{sinirlar[i]:g}"
    return f"[{alt}, {ust})"


def yazdir(tablo: dict, kayitlar: list = None, tekrar: int = 200) -> None:
    """Tabloyu hucre basina n / pozitif / olasilik ve (kayitlar verilirse)
    gun bazli blok bootstrap %5-95 araligiyla basar."""
    a, b = tablo["alan_a"], tablo["alan_b"]
    araliklar = degerlendir_araliklar(tablo, kayitlar, tekrar) if kayitlar else {}

    print(f"\nTablo: {a} × {b}   (taban oran %{100*tablo['taban']:.2f}, "
          f"büzülme K={BUZULME})")
    baslik = (f"  {a[:14]:<16}{b[:14]:<16}{'n':>8}{'poz':>6}"
              f"{'kat':>8}{'olasılık':>11}")
    print(baslik + (f"{'%5–%95':>18}" if araliklar else ""))
    for h in sorted(tablo["hucreler"]):
        c = tablo["hucreler"][h]
        satir = (f"  {_aralik(h[0], tablo['sinir_a']):<16}"
                 f"{_aralik(h[1], tablo['sinir_b']):<16}"
                 f"{c['n']:>8}{c['pozitif']:>6}{c['kat']:>7.1f}×"
                 f"{100*c['olasilik']:>10.2f}%")
        if h in araliklar:
            alt, ust = araliklar[h]
            satir += f"{f'{100*alt:.2f} – {100*ust:.2f}%':>18}"
        print(satir)


def degerlendir_araliklar(tablo: dict, kayitlar: list, tekrar: int = 200,
                          tohum: int = 0) -> dict:
    """Hucre olasiliklarinin GUN BAZINDA blok bootstrap araligi.

    Satir bazinda ornekleme yapilsaydi aralik sahte sekilde daralirdi: bir
    dusuk-tavan olayi ~6 satir uretiyor."""
    import random
    from collections import Counter, defaultdict

    gun_top, gun_poz = defaultdict(Counter), defaultdict(Counter)
    for r in kayitlar:
        h = (_bant(r.get(tablo["alan_a"]), tablo["sinir_a"]),
             _bant(r.get(tablo["alan_b"]), tablo["sinir_b"]))
        gun_top[r["gun"]][h] += 1
        gun_poz[r["gun"]][h] += int(bool(r["hedef"]))

    gunler = list(gun_top)
    if not gunler:
        return {}
    rastgele = random.Random(tohum)
    ornekler = defaultdict(list)
    for _ in range(tekrar):
        top, poz = Counter(), Counter()
        for _ in gunler:
            g = rastgele.choice(gunler)
            top.update(gun_top[g]); poz.update(gun_poz[g])
        n_top = sum(top.values()) or 1
        taban = sum(poz.values()) / n_top
        for h in tablo["hucreler"]:
            n = top.get(h, 0)
            ornekler[h].append((poz.get(h, 0) + BUZULME * taban) / (n + BUZULME))

    cikti = {}
    for h, v in ornekler.items():
        v.sort()
        cikti[h] = (v[int(0.05 * len(v))], v[min(int(0.95 * len(v)), len(v) - 1)])
    return cikti


def kat_kararliligi(tablo: dict, test: list, asgari_n: int = 150) -> dict:
    """Tablonun YAPISI baska bir doneme tasiniyor mu?

    Iki olcu dondurur:
      log_korelasyon - hucre KATLARININ log uzayinda korelasyonu (yapi)
      kat_orani_medyan - test katlari / egitim katlari medyani (seviye)

    Olculdu (gelistirme 2017-2023 -> holdout 2024-2026): log korelasyon
    0.990 ama kat orani medyani 2.21. Yani SIRALAMA aynen tasiniyor, SEVIYE
    tasinmiyor. Tablonun mutlak yuzde yerine KAT cinsinden okunmasinin
    gerekcesi budur."""
    import math
    from collections import Counter

    n, poz = Counter(), Counter()
    for r in test:
        h = (_bant(r.get(tablo["alan_a"]), tablo["sinir_a"]),
             _bant(r.get(tablo["alan_b"]), tablo["sinir_b"]))
        n[h] += 1
        poz[h] += int(bool(r["hedef"]))
    toplam = sum(n.values())
    if not toplam:
        return {}
    taban = sum(poz.values()) / toplam

    ciftler = []
    for h, hucre in tablo["hucreler"].items():
        if n[h] < asgari_n or hucre["n"] < asgari_n:
            continue
        test_kat = (poz[h] / n[h]) / taban if taban > 0 else 0.0
        ciftler.append((hucre["kat"], test_kat))
    if len(ciftler) < 3:
        return {}

    lx = [math.log(max(a, 1e-4)) for a, _ in ciftler]
    ly = [math.log(max(b, 1e-4)) for _, b in ciftler]
    m = len(lx)
    ox, oy = sum(lx) / m, sum(ly) / m
    sx = math.sqrt(sum((a - ox) ** 2 for a in lx))
    sy = math.sqrt(sum((b - oy) ** 2 for b in ly))
    kor = (sum((a - ox) * (b - oy) for a, b in zip(lx, ly)) / (sx * sy)
           if sx > 1e-12 and sy > 1e-12 else 0.0)
    oranlar = sorted(b / a for a, b in ciftler if a > 0)
    return {"hucre": m, "log_korelasyon": kor, "test_taban": taban,
            "kat_orani_medyan": oranlar[len(oranlar) // 2] if oranlar else 0.0}


# ------------------------------------------------------- cift secimi
def _ic_foldlar(yillar: list) -> list:
    """Gelistirme donemi ICINDE yuruyen pencere - holdout'a dokunmadan."""
    yillar = sorted(yillar)
    return [(tuple(yillar[:i]), (yillar[i],)) for i in range(2, len(yillar))]


def cift_sec(gelistirme: list, ciftler=ADAY_CIFTLER) -> list:
    """Her aday cifti gelistirme ICINDEKI yuruyen pencerede olcer.

    Holdout HIC acilmaz. Donen liste AP'ye gore sirali."""
    yillar = sorted({r["dt"].year for r in gelistirme})
    sonuc = []
    for a, b in ciftler:
        gercek, tahminler = [], []
        for eg_yillar, test_yillar in _ic_foldlar(yillar):
            eg = bolme.ayir(gelistirme, eg_yillar)
            te = bolme.ayir(gelistirme, test_yillar)
            if not te or not any(r["hedef"] for r in te):
                continue
            t = tablo_kur(eg, a, b)
            gercek += [bool(r["hedef"]) for r in te]
            tahminler += [tahmin(t, r) for r in te]
        sonuc.append({
            "cift": (a, b),
            "ap": degerlendir.ortalama_kesinlik(tahminler, gercek),
            "brier": degerlendir.brier(tahminler, gercek),
            "n": len(gercek), "poz": sum(gercek),
        })
    return sorted(sonuc, key=lambda s: -s["ap"])


def sis_olasiligi_ekle(kayitlar: list) -> list:
    """Her kayda dondurulmus SIS modelinin ciktisini ekler.

    Izolasyon sozlesmesi TEK YONLUDUR: calisma ani (ltfj_*) sis_modeli'ni
    import ETMEZ; tersi serbesttir (ozellik.py de ltfj_analiz'i kullaniyor).
    Burada modeli yeniden egitmiyoruz, DONDURULMUS ciktisini okuyoruz.

    DIKKAT - bu ciktinin gelistirme donemi (2017-2023) sis modelinin KENDI
    egitim donemi icindedir; yani buradaki sis_olasilik degerleri orada
    ORNEK ICI'dir. Bu yuzden gelistirmedeki her skoru iyimser saymak ve
    karari holdout'a (2024-2026, sis modelinin de disinda kalan donem)
    birakmak gerekir.
    """
    import ltfj_sis_olasilik as sis_modeli_donmus

    for r in kayitlar:
        p = sis_modeli_donmus.olasilik(
            spread=r.get("spread"), gorus=r.get("gorus"), saat=r.get("saat"),
            ruzgar_kuzey=r.get("ruzgar_kuzey"),
            spread_egilim_3=r.get("spread_egilim_3"))
        r["sis_olasilik"] = 0.0 if p is None else p
    return kayitlar


def dis_kaynak_ekle(kayitlar: list, komsu_yol: Path = None,
                    acik_meteo_yol: Path = None) -> list:
    """Her kayda komsu istasyon + Open-Meteo türetilmiş alanlarını ekler
    (veri_birlestir.py). tavan_dis_kaynak_tarama.py'deki tek değişkenli
    taramada acik_meteo_nem_2m (IV 2.235) ve komsu_tavan_ozellik (IV 1.761)
    güçlü çıktı (bkz. README) - bu fonksiyon o adayları GERÇEK tabloya
    (ADAY_CIFTLER'daki "DIŞ KAYNAK ADAYLARI" çiftleri) sokar."""
    from sis_modeli import veri_birlestir

    komsu_yol = komsu_yol or veri_birlestir.VARSAYILAN_KOMSU
    acik_meteo_yol = acik_meteo_yol or veri_birlestir.VARSAYILAN_ACIK_METEO
    return veri_birlestir.turet(
        veri_birlestir.zenginlestir(kayitlar, komsu_yol, acik_meteo_yol))


def kalibrasyon_tablosu(kayitlar: list, alan: str = "sis_olasilik",
                        sinirlar: list = None) -> list:
    """Bir olasilik ciktisinin bant bazinda GERCEKLESEN oranini verir.

    Yani "model %13 dediginde tavan gercekten kacta bir <500 ft'e dustu?"
    Bu, tablonun kendisidir: bir siralayici degil, bir OKUMA cetveli."""
    from collections import Counter

    sinirlar = list(APRIORI_BANTLAR[alan]) if sinirlar is None else sinirlar
    n, poz, top = Counter(), Counter(), Counter()
    for r in kayitlar:
        b = _bant(r.get(alan), sinirlar)
        n[b] += 1
        poz[b] += int(bool(r["hedef"]))
        top[b] += r.get(alan) or 0.0
    return [{"bant": b, "aralik": _aralik(b, sinirlar), "n": n[b],
             "pozitif": poz[b], "ortalama_tahmin": top[b] / n[b],
             "gerceklesen": poz[b] / n[b]} for b in sorted(n)]


def kalibrasyon_araliklari(kayitlar: list, alan: str = "sis_olasilik",
                           sinirlar: list = None, tekrar: int = 200,
                           tohum: int = 0) -> dict:
    """Kalibrasyon tablosunun her bandi icin gun bazli blok bootstrap %5-95."""
    import random
    from collections import Counter, defaultdict

    sinirlar = list(APRIORI_BANTLAR[alan]) if sinirlar is None else sinirlar
    gun_n, gun_poz = defaultdict(Counter), defaultdict(Counter)
    for r in kayitlar:
        b = _bant(r.get(alan), sinirlar)
        gun_n[r["gun"]][b] += 1
        gun_poz[r["gun"]][b] += int(bool(r["hedef"]))

    gunler = list(gun_n)
    if not gunler:
        return {}
    rastgele = random.Random(tohum)
    ornek = defaultdict(list)
    for _ in range(tekrar):
        n, poz = Counter(), Counter()
        for _ in gunler:
            g = rastgele.choice(gunler)
            n.update(gun_n[g]); poz.update(gun_poz[g])
        for b in n:
            ornek[b].append(poz.get(b, 0) / n[b])
    cikti = {}
    for b, v in ornek.items():
        v.sort()
        cikti[b] = (v[int(0.05 * len(v))], v[min(int(0.95 * len(v)), len(v) - 1)])
    return cikti


def kalibre_et(kalibrasyon: list, kayit: dict, alan: str = "sis_olasilik",
               sinirlar: list = None) -> float:
    """Bir olasilik ciktisini kalibrasyon tablosundan okunan orana cevirir."""
    sinirlar = list(APRIORI_BANTLAR[alan]) if sinirlar is None else sinirlar
    b = _bant(kayit.get(alan), sinirlar)
    for k in kalibrasyon:
        if k["bant"] == b:
            return k["gerceklesen"]
    return kayit.get(alan) or 0.0


def _yontemler(egitim: list, test: list, cift: tuple) -> dict:
    """Karsilastirilan tum yontemlerin test uzerindeki tahminleri."""
    t = tablo_kur(egitim, *cift)
    kal = kalibrasyon_tablosu(egitim)
    taban = sum(bool(r["hedef"]) for r in egitim) / max(len(egitim), 1)
    return {
        f"tablo ({' × '.join(cift)})": [tahmin(t, r) for r in test],
        "kalibre SİS modeli": [kalibre_et(kal, r) for r in test],
        "ham SİS modeli (kalibresiz)": [r["sis_olasilik"] for r in test],
        # Sureklilik: mevcut tavan ne kadar alcaksa o kadar olasi.
        "süreklilik (mevcut tavan)": [
            max(0.0, min(1.0, (3000 - (r.get("tavan_ozellik") or 99999)) / 3000))
            for r in test],
        "iklim (sabit taban oran)": [taban] * len(test),
    }


def _skor_bas(baslik: str, gercek: list, tahminler: dict) -> None:
    iklim = tahminler["iklim (sabit taban oran)"]
    print(f"\n{baslik}")
    print(f"  {'yöntem':<30}{'Brier×10⁴':>12}{'BSS':>9}{'AP':>8}")
    for ad, p in tahminler.items():
        print(f"  {ad:<30}{1e4*degerlendir.brier(p, gercek):>12.2f}"
              f"{degerlendir.brier_skill(p, gercek, iklim):>9.3f}"
              f"{degerlendir.ortalama_kesinlik(p, gercek):>8.3f}")


def _kalibrasyon_bas(baslik: str, kayitlar: list) -> None:
    araliklar = kalibrasyon_araliklari(kayitlar)
    print(f"\n{baslik}")
    print(f"  {'model bandı':<18}{'n':>8}{'poz':>6}{'ort. tahmin':>13}"
          f"{'gerçekleşen':>13}{'%5–%95':>18}")
    for k in kalibrasyon_tablosu(kayitlar):
        alt, ust = araliklar.get(k["bant"], (float("nan"), float("nan")))
        print(f"  {k['aralik']:<18}{k['n']:>8}{k['pozitif']:>6}"
              f"{100*k['ortalama_tahmin']:>12.2f}%{100*k['gerceklesen']:>12.2f}%"
              f"{f'{100*alt:.2f} – {100*ust:.2f}%':>18}")


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    a.add_argument("--esik", type=int, default=tavan.TABLO_ESIGI_FT)
    a.add_argument("--holdout", action="store_true",
                   help="nihai holdout'u (2024-2026) AC - TEK ATIS")
    secenek = a.parse_args(argv)
    if not secenek.veri.exists():
        print(f"HATA: {secenek.veri} yok.", file=sys.stderr)
        return 1

    aday = dis_kaynak_ekle(sis_olasiligi_ekle(
        tavan.hazirla(veri_oku(secenek.veri), esik_ft=secenek.esik)))
    gelistirme = bolme.gelistirme(aday)

    print(f"Hedef: 3 saat içinde tavan <{secenek.esik} ft (onset), "
          f"rejim {tavan.REJIM_ILK_YIL}+")
    print(f"Geliştirme: {len(gelistirme)} an, "
          f"{sum(r['hedef'] for r in gelistirme)} pozitif, "
          f"{len({r['gun'] for r in gelistirme if r['hedef']})} ayrı gün")

    print("\n=== 1) Değişken çifti seçimi (geliştirme içi yürüyen pencere) ===")
    print(f"{'çift':<32}{'AP':>8}{'Brier×10⁴':>12}{'test n':>9}{'poz':>6}")
    siralama = cift_sec(gelistirme)
    for s in siralama:
        print(f"{' × '.join(s['cift']):<32}{s['ap']:>8.3f}"
              f"{1e4*s['brier']:>12.2f}{s['n']:>9}{s['poz']:>6}")
    en_iyi = siralama[0]["cift"]

    print("\n=== 2) En iyi tablo, mevcut yöntemlerle karşılaştırma ===")
    print("(geliştirme içi yürüyen pencere; SİS modeli için ÖRNEK İÇİ - iyimser)")
    yillar = sorted({r["dt"].year for r in gelistirme})
    gercek, birikmis = [], {}
    for eg_y, te_y in _ic_foldlar(yillar):
        eg, te = bolme.ayir(gelistirme, eg_y), bolme.ayir(gelistirme, te_y)
        if not te or not any(r["hedef"] for r in te):
            continue
        gercek += [bool(r["hedef"]) for r in te]
        for ad, p in _yontemler(eg, te, en_iyi).items():
            birikmis.setdefault(ad, []).extend(p)
    _skor_bas(f"Birikmiş ({len(gercek)} an, {sum(gercek)} pozitif):",
              gercek, birikmis)

    tablo = tablo_kur(gelistirme, *en_iyi)
    yazdir(tablo, gelistirme)
    _kalibrasyon_bas("=== 3) SİS modeli çıktısının tavan hedefi için "
                     "kalibrasyonu (geliştirme) ===", gelistirme)

    if not secenek.holdout:
        print("\n(Holdout açılmadı. Açmak için: --holdout)")
        return 0

    print("\n" + "=" * 70)
    print("=== 4) NİHAİ HOLDOUT 2024-2026 - TEK ATIŞ ===")
    print("=" * 70)
    hol = bolme.holdout(aday)
    print(f"Holdout: {len(hol)} an, {sum(r['hedef'] for r in hol)} pozitif, "
          f"{len({r['gun'] for r in hol if r['hedef']})} ayrı gün")
    g_hol = [bool(r["hedef"]) for r in hol]
    _skor_bas("Skorlar:", g_hol, _yontemler(gelistirme, hol, en_iyi))
    _kalibrasyon_bas("Kalibrasyon (holdout):", hol)

    k = kat_kararliligi(tablo, hol)
    if k:
        print("\n=== 5) Tablonun YAPISI holdout'a taşınıyor mu? ===")
        print(f"  karşılaştırılan hücre           {k['hucre']:>8}")
        print(f"  kat'ların log korelasyonu       {k['log_korelasyon']:>8.3f}"
              "   (1.00 = sıralama aynen taşındı)")
        print(f"  kat oranı medyanı               "
              f"{k['kat_orani_medyan']:>8.2f}   (1.00 = seviye de taşındı)")
        print(f"  holdout taban oranı             "
              f"%{100*k['test_taban']:>7.3f}")
        if k["log_korelasyon"] > 0.9 and abs(k["kat_orani_medyan"] - 1) > 0.5:
            print("\n  SONUÇ: sıralama taşınıyor, SEVİYE TAŞINMIYOR."
                  "\n  Tablo MUTLAK YÜZDE olarak değil, KAT olarak okunmalıdır;"
                  "\n  mutlak seviye güncel bir taban orana bağlanmak zorundadır.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
