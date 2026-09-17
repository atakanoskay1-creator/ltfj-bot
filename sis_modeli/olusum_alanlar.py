#!/usr/bin/env python3
"""Model B ("gorussuz atmosferik sis olusum potansiyeli") icin aday ve
yasakli degisken listeleri.

BAGLAM: Model A (sis_modeli/egit.py) soruyor - "mevcut gorus DAHIL, onumuzdeki
3 saatte sis riski nedir?" Model B FARKLI bir soru soruyor - "gorus henuz
dusmemisken, salt atmosferik degiskenler yaklasan sisi ne kadar onceden
haber veriyor?" Iki model birbirinin YERINE GECMEZ, ayri sorulara cevap verir
(bkz. sis-tavan-metodoloji dokumaninin arastirma raporu eki).

DORT KATEGORI (arastirma raporunda talep edildigi gibi):
  1) GUVENLI       - T anina ait veya kesinlikle gecmise donuk, gorusle
                      dogrudan/dolayli iliskisi olmayan atmosferik olcum.
  2) POTANSIYEL SIZINTI - bu listede yok: hedef.hazirla()'nin gecmis()
                      mekanizmasi (yalnizca t-saat) zaten sizintisiz;
                      ADAYLAR'daki hicbir alan gelecegi okumuyor.
  3) YASAKLI (circular)  - hedefin kendisiyle ayni bilgiyi baska bir
                      kodlamayla tasiyan alanlar. Ozellik olarak KULLANILMAZ.
  4) TARTISMALI     - fiziksel olarak farkli ama veri kalitesi/rejim riski
                      tasiyan alanlar; ADAYLAR'a DAHIL EDILMEZ, ayrica
                      taranmak istenirse TARTISMALI_ADAYLAR'dan alinir.
"""

# ---------------------------------------------------------------- 1) güvenli
# hedef.hazirla()'nin urettigi/tasidigi, gorusle iliskisiz atmosferik alanlar.
# WoE/IV taramasi olusum_egit.py'de BU LISTE uzerinde YENIDEN yapilir - Model
# A'nin tarama sonuclari (ornegin qnh_egilim_3 IV 0.03 ile elenmesi) BASKA
# BIR HEDEFTE olculmustu, buraya otomatik tasinmaz (projenin kendi ilkesi:
# her hedef kendi taramasini hak eder - tavan calismasinda da boyle yapildi).
ADAYLAR = [
    "sicaklik", "cig_noktasi", "spread",
    "spread_egilim_1", "spread_egilim_3",
    "ruzgar_hiz", "ruzgar_kuzey", "ruzgar_dogu", "ruzgar_egilim_1",
    "saat", "ay",
    "qnh", "qnh_egilim_3",
]

# ------------------------------------------------------------- 4) tartışmalı
# Fiziksel olarak GORUSTEN bagimsiz (bulut tabani yuksekligi ayrı bir olcum)
# ama Model A'nin kendi taramasinda PSI 0.24 (donemler arasi kayma) nedeniyle
# dislanmisti - bu gorus DEGIL, veri kalitesi/rejim riski. Model B'de aday
# olarak kalir ama ADAYLAR'a DAHIL DEGIL; ayrica ve dikkatli taranmalidir
# (muhtemelen tavan matrisi calismasindaki gibi 2017+ rejim penceresi
# gerektirir - bkz. sis_modeli/tavan.py REJIM_ILK_YIL).
#
# "hava" sutunundaki BR (pus) ve nitelikli FG (VC/MI/BC/PR - civarda/alcak/
# parcali/kismi) kodlari da bu kategoride: cikplak, niteliksiz FG'den (=
# sis_kodu, YASAKLI) farkli olarak bunlar alani KAPLAYAN sis DEGIL (bkz.
# sis_yakinligi() asagida) - ama sis'e komsu/oncul bir durumu isaret
# edebilirler. Henuz hicbir modelde ozellik olarak KULLANILMIYOR.
TARTISMALI_ADAYLAR = ["tavan", "sis_yakinligi"]

# ------------------------------------------------------------------ 3) yasak
# Gorusun KENDISI, gorusten turetilebilecek herhangi bir ozellik (henuz
# yok ama onceden yasaklaniyor), etiketin kendisi/turevleri ve sis_kodu.
#
# sis_kodu ozel durum: test_sis_modeli.py ile dogrulandi - yalnizca ALANI
# KAPLAYAN, niteliksiz (VC/MI/BC/PR'siz) FG kodunde 1 oluyor; bu TAM OLARAK
# "sis" etiketinin ikinci OR-kosulu. Feature olarak kullanmak, hedefi baska
# bir kodlamayla modele geri vermek olur - dairesel (circular) predictor.
YASAKLI = (
    "gorus", "gorus_egilim_1", "gorus_egilim_3",   # gorus_egilim_* HENUZ YOK,
                                                    # ama var olursa yasakli
    "sis", "lvo", "sis_kodu",
)


def sis_yakinligi(hava_metni: str) -> int:
    """'hava' sutunundaki ham METAR hava kodlarinda SIS ONCULU bir isaret
    var mi? (0/1)

    BR (pus, gorus 1000-5000 m) veya nitelikli FG (VC/MI/BC/PR - civarda/
    alcak/parcali/kismi) alani KAPLAYAN sis DEGILDIR - test_sis_modeli.py
    bunlarin HICBIRININ sis_kodu'nu tetiklemedigini dogruluyor (VCFG, MIFG,
    BCFG, PRFG hepsi sis_kodu=0). Ama fiziksel olarak KOMSU/YAKLASAN bir nem
    durumunu gosterebilirler - GUVENLI (kategori 1) ile YASAKLI (kategori 3,
    ciplak FG) arasinda bir ONCUL sinyal. Bu yuzden TARTISMALI_ADAYLAR'da
    tutulur, ADAYLAR'a OTOMATIK dahil edilmez."""
    from ltfj_analiz import RE_HAVA

    if not hava_metni:
        return 0
    for token in hava_metni.split():
        m = RE_HAVA.match(token)
        if not m:
            continue
        siddet, tanim, olaylar = m.groups()
        if "BR" in olaylar:
            return 1
        if "FG" in olaylar and (siddet == "VC" or any(
                t in (tanim or "") for t in ("MI", "BC", "PR"))):
            return 1
    return 0


def dogrula(alanlar: list) -> None:
    """Bir ozellik listesinde YASAKLI bir alan varsa ValueError firlatir.

    olusum_egit.py / ufuk_deneyi.py bu fonksiyonu ALANLAR'i kullanmadan
    ONCE cagirir - boylece gorus veya turevlerinin yanlislikla Model B'ye
    sizmasi calisma zamaninda (test zamaninda degil) da engellenir."""
    celisen = [a for a in alanlar if a in YASAKLI]
    if celisen:
        raise ValueError(
            f"Model B (gorussuz) icin YASAKLI alan(lar) kullanilamaz: "
            f"{celisen}. Bkz. sis_modeli/olusum_alanlar.py YASAKLI listesi.")
