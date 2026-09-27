#!/usr/bin/env python3
"""DONDURULMUS sis iklimbilimi - sis_modeli/sis_iklim.py uretti.

ELLE DUZENLEME. Yeniden uretmek icin:
    python -m sis_modeli.sis_iklim --dondur

Sayfa bu sayilari gosteriyor ama bot arsivi her kosuda okuyamaz -
ltfj_gorus_gecis_tablo ile ayni disiplin: SABIT tasir, hesap yapmaz.

Tanim ve sinirlar: sis_modeli/sis_iklim.py modul aciklamasi ve
sis_modeli/README.md "Sis iklimbilimi". Saatler YEREL (UTC+3).
"""

KAPSAM_ILK_YIL = 2011
KAPSAM_SON_YIL = 2026
GOZLEM = 273423
SIS_GOZLEM = 1183
LVO_GOZLEM = 642

# ay: sisli_gun = o ayda en az bir sisli gozlem olan gun sayisi (tum yillar),
# oran_yuzde = o ayin gozlemlerinin yuzde kaci sisli,
# pay_yuzde = tum sisli gozlemlerin yuzde kaci o ayda.
AYLAR = [{'ay': 1, 'sisli_gun': 40, 'lvo_gozlem': 133, 'oran_yuzde': 0.87, 'pay_yuzde': 17.3},
 {'ay': 2, 'sisli_gun': 45, 'lvo_gozlem': 98, 'oran_yuzde': 1.25, 'pay_yuzde': 22.8},
 {'ay': 3, 'sisli_gun': 21, 'lvo_gozlem': 96, 'oran_yuzde': 0.58, 'pay_yuzde': 11.6},
 {'ay': 4, 'sisli_gun': 16, 'lvo_gozlem': 36, 'oran_yuzde': 0.33, 'pay_yuzde': 6.1},
 {'ay': 5, 'sisli_gun': 20, 'lvo_gozlem': 52, 'oran_yuzde': 0.37, 'pay_yuzde': 7.5},
 {'ay': 6, 'sisli_gun': 21, 'lvo_gozlem': 24, 'oran_yuzde': 0.2, 'pay_yuzde': 3.9},
 {'ay': 7, 'sisli_gun': 18, 'lvo_gozlem': 29, 'oran_yuzde': 0.22, 'pay_yuzde': 4.5},
 {'ay': 8, 'sisli_gun': 23, 'lvo_gozlem': 14, 'oran_yuzde': 0.17, 'pay_yuzde': 3.5},
 {'ay': 9, 'sisli_gun': 8, 'lvo_gozlem': 8, 'oran_yuzde': 0.08, 'pay_yuzde': 1.6},
 {'ay': 10, 'sisli_gun': 20, 'lvo_gozlem': 48, 'oran_yuzde': 0.35, 'pay_yuzde': 6.5},
 {'ay': 11, 'sisli_gun': 18, 'lvo_gozlem': 66, 'oran_yuzde': 0.49, 'pay_yuzde': 8.9},
 {'ay': 12, 'sisli_gun': 17, 'lvo_gozlem': 38, 'oran_yuzde': 0.31, 'pay_yuzde': 5.8}]

SAATLER = [{'saat': 0, 'oran_yuzde': 0.33, 'pay_yuzde': 3.2},
 {'saat': 1, 'oran_yuzde': 0.4, 'pay_yuzde': 3.9},
 {'saat': 2, 'oran_yuzde': 0.58, 'pay_yuzde': 5.6},
 {'saat': 3, 'oran_yuzde': 0.85, 'pay_yuzde': 8.1},
 {'saat': 4, 'oran_yuzde': 1.22, 'pay_yuzde': 11.7},
 {'saat': 5, 'oran_yuzde': 1.41, 'pay_yuzde': 13.6},
 {'saat': 6, 'oran_yuzde': 1.39, 'pay_yuzde': 13.4},
 {'saat': 7, 'oran_yuzde': 0.92, 'pay_yuzde': 8.9},
 {'saat': 8, 'oran_yuzde': 0.75, 'pay_yuzde': 7.2},
 {'saat': 9, 'oran_yuzde': 0.46, 'pay_yuzde': 4.5},
 {'saat': 10, 'oran_yuzde': 0.33, 'pay_yuzde': 3.2},
 {'saat': 11, 'oran_yuzde': 0.19, 'pay_yuzde': 1.9},
 {'saat': 12, 'oran_yuzde': 0.23, 'pay_yuzde': 2.2},
 {'saat': 13, 'oran_yuzde': 0.16, 'pay_yuzde': 1.5},
 {'saat': 14, 'oran_yuzde': 0.13, 'pay_yuzde': 1.3},
 {'saat': 15, 'oran_yuzde': 0.14, 'pay_yuzde': 1.4},
 {'saat': 16, 'oran_yuzde': 0.17, 'pay_yuzde': 1.6},
 {'saat': 17, 'oran_yuzde': 0.17, 'pay_yuzde': 1.6},
 {'saat': 18, 'oran_yuzde': 0.11, 'pay_yuzde': 1.0},
 {'saat': 19, 'oran_yuzde': 0.08, 'pay_yuzde': 0.8},
 {'saat': 20, 'oran_yuzde': 0.05, 'pay_yuzde': 0.5},
 {'saat': 21, 'oran_yuzde': 0.08, 'pay_yuzde': 0.8},
 {'saat': 22, 'oran_yuzde': 0.1, 'pay_yuzde': 0.9},
 {'saat': 23, 'oran_yuzde': 0.14, 'pay_yuzde': 1.4}]

# kat = sis sirasindaki pay / genel pay (1'in ustu: o ruzgarda sis normalden sik)
RUZGAR = [{'sektor': 'sakin', 'sis_pay_yuzde': 16.1, 'genel_pay_yuzde': 10.7, 'kat': 1.52},
 {'sektor': 'K', 'sis_pay_yuzde': 14.5, 'genel_pay_yuzde': 15.2, 'kat': 0.96},
 {'sektor': 'KD', 'sis_pay_yuzde': 55.2, 'genel_pay_yuzde': 44.5, 'kat': 1.24},
 {'sektor': 'D', 'sis_pay_yuzde': 4.4, 'genel_pay_yuzde': 3.4, 'kat': 1.28},
 {'sektor': 'GD', 'sis_pay_yuzde': 0.8, 'genel_pay_yuzde': 1.3, 'kat': 0.66},
 {'sektor': 'G', 'sis_pay_yuzde': 3.0, 'genel_pay_yuzde': 5.3, 'kat': 0.56},
 {'sektor': 'GB', 'sis_pay_yuzde': 2.8, 'genel_pay_yuzde': 10.6, 'kat': 0.26},
 {'sektor': 'B', 'sis_pay_yuzde': 2.3, 'genel_pay_yuzde': 6.3, 'kat': 0.36},
 {'sektor': 'KB', 'sis_pay_yuzde': 0.5, 'genel_pay_yuzde': 1.3, 'kat': 0.39}]
HIZ_MEDYAN_KT = 6
HIZ_5KT_ALTI_YUZDE = 47

# Guneyli (140-250 derece) sis ve digerleri - olay suresi ve LVO orani
GUNEY = {'sis_gozlem': 82,
 'pay_yuzde': 6.9,
 'sisli_gun': 22,
 'aylar': [1, 2, 3, 4, 10, 11, 12],
 'olay': 9,
 'sure_medyan_sa': 4.0,
 'lvo_yuzde': 77}
DIGER = {'olay': 342, 'sure_medyan_sa': 1.0, 'lvo_yuzde': 53}
