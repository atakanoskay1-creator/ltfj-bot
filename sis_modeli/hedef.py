#!/usr/bin/env python3
"""Ileriye bakan hedef + egilim ozellikleri uretir.

EN KRITIK TASARIM KARARI - SIZINTI (leakage):
Ham veride etiket AYNI ANI anlatir ("bu gozlemde gorus <1000 m miydi?").
Bu etiket dogrudan modele verilirse gorus hem girdi hem ciktidir; model
"gorus 400 ise sis var" diye mukemmel dogrulukla ogrenir ve HICBIR ISE
YARAMAZ. Bu yuzden hedef GELECEGE kaydirilir:

    hedef = onumuzdeki UFUK_SAAT icinde sis olacak mi?

Ozellikler yalnizca t anina aittir; t'den sonraki hicbir bilgi kullanilmaz.

Ayrica ONSET (olusum) gorevi ayrilir: su an sis YOKKEN sis olusacak mi?
Sis varken "3 saat sonra da olacak" demek kolaydir (sureklilik) ve skoru
sisirir; asil degerli olan sorunun olusum tarafidir.
"""

from datetime import datetime, timedelta

UFUK_SAAT = 3
ADIM_DK = 30                       # arsiv yarim saatlik izgarada
ADIM_SAYISI = UFUK_SAAT * 60 // ADIM_DK

# Egilim penceresi: spread'in DUSUS HIZI, seviyesinden daha bilgilendirici
# olabilir ("spread 0" ile "spread 3'ten 0'a iniyor" ayni sey degil).
EGILIM_SAAT = (1, 3)


def hazirla(satirlar: list, etiket: str = "sis", ufuk_saat: float = None) -> list:
    """Zaman siralar, egilim ozelliklerini ve ileriye bakan hedefi ekler.

    ufuk_saat: None ise modul sabiti UFUK_SAAT (3) kullanilir - mevcut
    cagrilarin DAVRANISI BIREBIR AYNI kalir. Lead-time deneyi (30dk/1h/2h/3h)
    icin acikca gecilebilir (bkz. ufuk_deneyi.py). 30 dakikalik veri
    izgarasinin alti kati olmayan bir ufuk (ornegin 45 dk) son adimi kismen
    kapsar - bu yuzden ADIM_DK'nin (30) tam katlari kullanilmasi onerilir.

    Eklenen alanlar:
      dt              - datetime
      gun             - "YYYY-MM-DD" (blok bootstrap icin)
      spread_egilim_1 - son 1 saatteki spread degisimi (negatif = dusuyor)
      spread_egilim_3 - son 3 saatteki spread degisimi
      qnh_egilim_3    - son 3 saatteki basinc degisimi
      ruzgar_egilim_1 - son 1 saatteki ruzgar degisimi
      ruzgar_dogu     - rüzgâr yönünün dogu bileseni (advection hipotezi)
      ruzgar_kuzey    - rüzgâr yönünün kuzey bileseni
      hedef           - ufuk_saat icinde etiket gerceklesecek mi (bool)
      hedef_ufuk_saat - bu hedefin hesaplandigi ufuk (embargo icin gerekli)
    """
    import math

    ufuk = UFUK_SAAT if ufuk_saat is None else ufuk_saat
    adim_sayisi = round(ufuk * 60 / ADIM_DK)

    kayitlar = [dict(r) for r in satirlar]
    for r in kayitlar:
        r["dt"] = datetime.fromisoformat(r["zaman"])
        r["gun"] = r["zaman"][:10]
    kayitlar.sort(key=lambda r: r["dt"])
    yer = {r["dt"]: i for i, r in enumerate(kayitlar)}

    def gecmis(i, saat, alan):
        j = yer.get(kayitlar[i]["dt"] - timedelta(hours=saat))
        if j is None:
            return None
        onceki, simdiki = kayitlar[j].get(alan), kayitlar[i].get(alan)
        if onceki is None or simdiki is None:
            return None
        return simdiki - onceki

    for i, r in enumerate(kayitlar):
        for saat in EGILIM_SAAT:
            r[f"spread_egilim_{saat}"] = gecmis(i, saat, "spread")
        r["qnh_egilim_3"] = gecmis(i, 3, "qnh")
        r["ruzgar_egilim_1"] = gecmis(i, 1, "ruzgar_hiz")

        # Ruzgar yonu dairesel: 350 ile 010 arasi mesafe 340 degil 20'dir.
        # Bilesenlere ayirmak hem bu sorunu cozer hem advection hipotezini
        # test edilebilir kilar (denizden gelen yon baskin mi?).
        yon, hiz = r.get("ruzgar_yon"), r.get("ruzgar_hiz")
        if yon is not None and hiz is not None:
            aci = math.radians(yon)
            r["ruzgar_dogu"] = hiz * math.sin(aci)
            r["ruzgar_kuzey"] = hiz * math.cos(aci)
        else:
            r["ruzgar_dogu"] = r["ruzgar_kuzey"] = None

        # ileriye bakan hedef
        r["hedef"] = False
        r["hedef_ufuk_saat"] = ufuk
        for k in range(1, adim_sayisi + 1):
            j = yer.get(r["dt"] + timedelta(minutes=ADIM_DK * k))
            if j is not None and kayitlar[j][etiket]:
                r["hedef"] = True
                break

    return kayitlar


def onset_adaylari(kayitlar: list, etiket: str = "sis") -> list:
    """Su an sis YOKKEN olan anlar - olusum gorevinin egitim/test evreni."""
    return [r for r in kayitlar if not r[etiket]]
