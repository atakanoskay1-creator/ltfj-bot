#!/usr/bin/env python3
"""Dusuk bulut tabani (tavan) etiketi + bildirim rejimi penceresi.

NEDEN AYRI BIR MODUL, NEDEN MODEL DEGIL TABLO:

Tavan, TL.007 madde 6.2.a / 6.3.1.a uyarinca RVR'dan BAGIMSIZ bir LVO
tetikleyicisi - yani modellenmeye deger. Ama arsiv iki ayri duvara carpiyor
ve ikisi HIC KESISMIYOR:

  1) LVO icin asil onemli esikte (CAT II, <200 ft) 18 yilda yalnizca ~61
     BAGIMSIZ olay var. Lojistik regresyon icin kabul ettigimiz 150 olay
     tabaninin cok altinda.
  2) Olay sayisi yeten esiklerde (<500, <1000 ft) ETIKETIN KENDISI kayiyor:

       donem       <200ft    <500ft   <1000ft   500 ft katlarina yigilma
       2012-2015   %0.126    %0.535    %1.494          %89.1
       2016-2020   %0.089    %0.878    %3.207          %76.9
       2021-2023   %0.135    %1.188    %3.892          %76.7
       2024-2026   %0.061    %1.395    %4.515          %72.0

     <500 ve <1000 dort donemde de TEK YONDE artiyor ve bu artis, bildirilen
     tavan degerlerinin yuvarlak sayilara yigilma oraninin dususuyle ayni
     yonde. Iklim degil OLCUM PRATIGI degisimi: insan gozlemcinin "3000"
     dedigi yere ceilometre "900" diyor. <200 ft ise bu kaymayi GOSTERMIYOR
     (yonsuz gurultu) - cunku VV bildirimi siste zorunlu ve yoruma kapali.

Sonuc: regresyon yerine KALIBRE EDILMIS OLASILIK TABLOSU, ve yalnizca
bildirim rejiminin oturdugu REJIM_ILK_YIL sonrasi uzerinde. Tablo mutlak
seviyesini degil GORELI siralamasini iddia eder; mutlak taban orani icin
kayma uyarisi rapora basilir (bkz. tavan_tablo.py).

Bagimlilik yok: saf standart kutuphane.
"""

# LVO/VFR acisindan anlamli tavan esikleri, ft.
CAT_II_FT = 200           # TL.007 6.3.1.a - asil ilgilendigimiz esik
TABLO_ESIGI_FT = 500      # olay sayisi yeten en dusuk esik
VFR_ESIGI_FT = 1500

# Bildirim rejimi: 2011-2016 arasinda dusuk tavan sistematik olarak eksik
# bildiriliyor (2011'de <1000 ft orani %0.01 - fiziksel olarak imkansiz).
# 2017'den itibaren oran hem daha yuksek hem daha kararli. Bu sinir
# olculerek secildi, sonuca bakilarak DEGIL (bkz. rejim_taramasi()).
REJIM_ILK_YIL = 2017

# Tavan raporlanmadiginda (CAVOK / NSC / SKC / yalnizca FEW-SCT) tavan
# YOKTUR - bu "veri eksik" degil, "dusuk tavan yok" demektir. Etikette 0,
# ozellikte ise asagidaki sozde-deger ile temsil edilir ki kova tablosunda
# kendi bandina dussun.
TAVAN_YOK_FT = 99999


def tavan_ft(satir: dict) -> int:
    """Ozellik olarak kullanilabilir tavan degeri.

    None (bildirilmemis) -> TAVAN_YOK_FT. Bunu None birakmak yanlis olurdu:
    WoE kova tablosu None'lari ATAR ve gozlemlerin %62'si boyle - yani
    'tavan yok' bilgisi, ki en guclu negatif gostergedir, tamamen kaybolurdu.
    """
    t = satir.get("tavan")
    return TAVAN_YOK_FT if t is None else int(t)


def etiketle(satirlar: list, esik_ft: int = TABLO_ESIGI_FT) -> list:
    """Her satira 'tavan_dusuk' (0/1) ekler; kopya dondurur."""
    cikti = []
    for r in satirlar:
        y = dict(r)
        y["tavan_dusuk"] = int(tavan_ft(r) < esik_ft)
        cikti.append(y)
    return cikti


def rejim_penceresi(satirlar: list, ilk_yil: int = REJIM_ILK_YIL) -> list:
    return [r for r in satirlar if int(r["zaman"][:4]) >= ilk_yil]


def rejim_taramasi(satirlar: list, esikler=(CAT_II_FT, TABLO_ESIGI_FT, 1000)) -> list:
    """Yil bazinda esik oranlari + yuvarlak sayiya yigilma orani.

    REJIM_ILK_YIL'i bu ciktiya bakarak sectik; karar surecinin kendisi
    kodda kalsin diye fonksiyon olarak duruyor."""
    yillar = {}
    for r in satirlar:
        yillar.setdefault(int(r["zaman"][:4]), []).append(r)

    cikti = []
    for yil in sorted(yillar):
        alt = yillar[yil]
        bildirilen = [r["tavan"] for r in alt if r.get("tavan") is not None]
        if len(alt) < 1000:
            continue
        cikti.append({
            "yil": yil,
            "n": len(alt),
            "bildirim_orani": len(bildirilen) / len(alt),
            "oranlar": {e: sum(1 for t in bildirilen if t < e) / len(alt)
                        for e in esikler},
            # Insan tahmini yuvarlak sayilara yigilir, ceilometre yigilmaz.
            "yuvarlak_orani": (sum(1 for t in bildirilen if int(t) % 500 == 0)
                               / len(bildirilen)) if bildirilen else 0.0,
        })
    return cikti


def hazirla(satirlar: list, esik_ft: int = TABLO_ESIGI_FT,
            ilk_yil: int = REJIM_ILK_YIL) -> list:
    """Rejim penceresi + etiket + ileriye bakan hedef + onset suzgeci.

    Sirasi onemli: egilim ozellikleri ve ileriye bakan hedef, pencere
    KESILDIKTEN sonra hesaplanir - yoksa pencerenin ilk gunu, kesilen
    gecmisten egilim uretmeye calisirdi."""
    from sis_modeli import hedef as hedef_modulu

    pencere = rejim_penceresi(satirlar, ilk_yil)
    etiketli = etiketle(pencere, esik_ft)
    kayitlar = hedef_modulu.hazirla(etiketli, etiket="tavan_dusuk")
    for r in kayitlar:
        # WoE tablosunda 'tavan yok' kendi bandina dussun diye sozde-deger.
        r["tavan_ozellik"] = tavan_ft(r)
    # Onset: su an tavan ZATEN dusuk degilken, 3 saat icinde dusecek mi?
    # Dusukken "3 saat sonra da dusuk" demek sureklilikten ibarettir ve
    # skoru sisirir.
    return hedef_modulu.onset_adaylari(kayitlar, etiket="tavan_dusuk")
