#!/usr/bin/env python3
"""DONDURULMUS gorus gecis sureleri - sis_modeli/gorus_gecis.py uretti.

ELLE DUZENLEME. Yeniden uretmek icin:
    python -m sis_modeli.gorus_gecis --dondur

NEDEN DONDURULMUS: sayfa bu sayilari gosteriyor ama bot arsivi (6 MB,
274 bin satir) her kosuda okuyamaz. ltfj_sis_olasilik ile ayni disiplin -
bu modul SABIT tasir, hesap yapmaz, agir bagimlilik import etmez.

Yontem, kapsam ve sinirlar icin: sis_modeli/README.md "Gorus gecis
sureleri" ve sis_modeli/gorus_gecis.py modul aciklamasi.

Sureler SAAT cinsinden ve 30 dakikalik izgaraya YUVARLIDIR (arsivde
SPECI yok) - "0.5 saat" aslinda "0.5 saat VEYA DAHA KISA" demektir.
"""

KAPSAM_ILK_YIL = 2011
KAPSAM_SON_YIL = 2026
OLAY_SAYISI = 64

# Olay tanimi (Tardif & Rasmussen 2007): gorus <2000 m kesintisiz >=3
# saat, icinde <1000 m >=1 saat, kar yok.
ESIK_VMC_M = 5000
ESIK_SVFR_M = 1500
ESIK_SIS_M = 1000

# n = olculebilen olay sayisi (penceresi eksik/zaten dusuk olanlar haric)
DUSME = {"n": 61, "p10": 0.50, "p25": 1.00, "medyan": 1.50, "p75": 2.50}
TOPARLANMA = {"n": 62, "p10": 1.00, "p25": 1.50, "medyan": 2.00, "p75": 3.00}

# Yagisli olay sayisi. LTFJ'de pratikte YOK - makalede yagis sisi en
# yavas gecisi uretiyordu ama burada orneklem olusmuyor. Bu bir eksiklik
# degil, LTFJ hakkinda bir bulgu.
YAGISLI_OLAY = 1
