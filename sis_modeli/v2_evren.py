#!/usr/bin/env python3
"""Sis modeli V2 - gelistirme evreni (V2_PROTOKOL.md §3; Deney 0 B10 duzeltmesi).

Hedefin teknik adi: LTFJ dusuk gorus/FG olayi.

§3: "Degiskenler yalnizca :20/:50 izgarasindan hesaplanir - egitimde de
canlida da. SPECI yalnizca ileriye donuk degerlendirmede olay gozlemini
(etiketi) belirlemek icin kullanilir (§12)."

Deney 0 (B10), mevcut pipeline'in izgara disi kayitlari (IEM arsivindeki
6 SPECI) hedef.hazirla'ya ve olay bolutlemesine sizdirdigini gosterdi:
5'i onset (tahmin) satiri oluyordu, biri (2022-10-31 23:01, 900 m BCFG)
tek basina bir bagimsiz olay olusturuyordu. Bu bir protokol degisikligi
degil, §3'un uygulanmasini duzelten bir kodlama duzeltmesidir (§15).

V2 gelistirme evreni:
  - tahmin/onset satirlari : yalniz :20/:50
  - hedef (Y)              : yalniz :20/:50 gozlemleri
  - olay bolutlemesi (§5.1): yalniz :20/:50 gozlemleri
Izgara filtresi hedef.hazirla'dan ONCE uygulanir. Veri dosyasindan hicbir
satir silinmez; filtre yalnizca bu evreni kurarken uygulanir.

V1 referansi ve V2 varyantlari bu AYNI evreni kullanir. Canli V1'in
davranisi (ltfj_sis_olasilik.py) DEGISMEZ. Ileriye donuk sinavda (§12)
tahmin zamanlari/degiskenler yine yalniz izgaradan; sonuc/olay
degerlendirmesi SPECI dahil ve ayrica izgara-yalniz tanilama ile yapilir -
o kisim bu modulun kapsami disindadir.
"""

from datetime import datetime

from sis_modeli import bolme, hedef
from sis_modeli.olay_degerlendirme import bagimsiz_olaylar

IZGARA_DK = (20, 50)


def izgara_disi(dt: datetime) -> bool:
    return dt.minute not in IZGARA_DK or dt.second != 0 or dt.microsecond != 0


def izgara_kayitlari(satirlar: list) -> list:
    """Yalniz :20/:50 zaman damgali satirlar (girdi degistirilmez)."""
    return [r for r in satirlar if not izgara_disi(datetime.fromisoformat(r["zaman"]))]


def gelistirme_kayitlari(ham: list, ilk_yil: int = bolme.ILK_YIL) -> list:
    """V2 gelistirme evreninin tam kayit kumesi: yil >= ilk_yil, izgara
    filtresi, SONRA hedef.hazirla (onset filtresi uygulanmamis)."""
    secili = [r for r in ham if r["zaman"][:4] >= str(ilk_yil)]
    return hedef.hazirla(izgara_kayitlari(secili))


def gelistirme_olaylari(kayitlar: list) -> list:
    """§5.1 bagimsiz olaylar - gelistirme_kayitlari() ciktisi uzerinde."""
    return bagimsiz_olaylar(kayitlar, etiket="sis", bosluk_saat=3.0)
