#!/usr/bin/env python3
"""LVO REFERENCE panelindeki "Farkındalık Notları" alt bölümü için GAYRİ
RESMİ, hedge'li ("olabilir") ipucu metinleri üretir.

Bu modul RVR/CAT II/LVTO/LVO gibi bir SONUÇ üretmez - sadece OKUNAN
değerlerin (METAR'ın kendi görüş/tavanı, TAF'in kendi tavan verisi, ATC'nin
manuel girdiği AWOS RVR) dokümanın (TL.007, bkz. ltfj_lvo_referans.py) kendi
eşik değerleriyle karşılaştırmasını, "LVO şartları oluşabilir. Resmî bir
tespit değildir." hedge'iyle metne döker. "LVO aktif", "CAT II
kullanılabilir", "LVTO yapılabilir", "şu pist kullanılmalı" gibi kesin bir
operasyonel ifade HİÇBİR ZAMAN üretilmez (bkz. tests/test_ltfj_sayfa_lvo.py
YASAK_KARAR_KALIPLARI - bu modül eklendikten sonra da geçerli/geçiyor).

METAR'dan RVR TÜRETİLMEZ - burada METAR'ın SADECE kendi görüş/tavan
(bulut taban yüksekliği) değeri kullanılır. RVR sadece ATC'nin manuel AWOS
girişinden (gerçek ölçüm) okunur; o veri Firebase'de (yalnızca istemci
tarafında) yaşadığı için buradaki rvr_notu() sunucu tarafında ÇAĞRILMAZ -
web sayfasındaki LVO script'i (ltfj_sayfa.py) AYNI mantığı, bu modülün
export ettiği RVR_ESIKLERI ile JavaScript'te tekrar uygular (embedded JSON
üzerinden, tek kaynaktan - ltfj_lvo_referans.RVR_ESIKLERI).

Notların ÜÇÜ eşik karşılaştırmasıdır (metar_tavan_notu, taf_tavan_notu,
rvr_notu): okunan değer dokümanın kendi eşiğinin altında mı? Dördüncüsü
(tavan_istatistik_notu) farklı bir cinstir - bir eşik geçildiği için değil,
geçmiş arşivde bu koşullarda düşük tavanın ne sıklıkta görüldüğü için
çıkar. O yüzden mutlak yüzde değil KAT söyler; gerekçesi
ltfj_tavan_tablosu.py başındadır."""

import ltfj_dis_kaynak_cache as dis_kaynak_onbellek
import ltfj_sis_olasilik as sis_olasilik
import ltfj_tavan_dis_kaynak as tavan_dis_kaynak
import ltfj_tavan_tablosu as tavan_tablosu
from ltfj_analiz import RE_BULUT, TAVAN_KATMANLARI, tokenla
from ltfj_lvo_referans import RVR_ESIKLERI

# madde 6.2.a / 6.3.1.a - CAT II bulut tabanı aralığının (100-200 ft) üst
# sınırı; METAR/TAF tavanı bu değerin altındaysa farkındalık notu üretilir.
CEILING_FARKINDALIK_ESIGI_FT = 200

# İstatistiksel tavan notu bu KAT'ın altında üretilmez. Taban oran ~%1;
# 3 kat, tablonun 26 hücresinin en riskli 9'unu seçer ve gözlemlerin
# yalnızca %6.4'ünde gerçekleşir - yani not seyrek çıkar, sürekli yanıp
# duran bir uyarı olmaz. Eşik a priori; sonuçlara bakılarak ayarlanmadı.
TAVAN_KAT_ESIGI = 3.0

# tavan_dis_kaynak_notu() icin AYNI esik - iki notun tetiklenme sikligi
# tutarli kalsin diye (sonuca bakilarak degil, tutarlilik icin secildi).
TAVAN_DIS_KAYNAK_KAT_ESIGI = TAVAN_KAT_ESIGI

# Tavan bildirilmemisse (CAVOK/NSC/SKC) "tavan yok" - sis_modeli/tavan.py
# ile AYNI sozde-deger (TAVAN_YOK_FT), boylece dondurulmus WoE tablosunda
# kendi bandina duser, None olarak "bilgi yok" ile KARISTIRILMAZ.
_TAVAN_YOK_FT = 99999

_HEDGE = "LVO şartları oluşabilir. Resmî bir tespit değildir."


def metar_tavan_notu(cozum: dict | None) -> str | None:
    """cozum: ltfj_analiz.metar_coz() çıktısı. Tavan eşiğin altındaysa bir
    not döner, değilse (veya tavan/METAR yoksa) None döner."""
    if not cozum:
        return None
    tavan = cozum.get("tavan")
    if tavan is None or tavan >= CEILING_FARKINDALIK_ESIGI_FT:
        return None
    return (f"METAR tavanı {tavan} ft — düşük (CAT II bulut tabanı aralığı "
            f"100–200 ft, madde 6.2.a/6.3.1.a). {_HEDGE}")


def taf_en_dusuk_tavan_ft(taf_metni: str) -> int | None:
    """TAF metninin TÜM dönemlerindeki (FM/BECMG/TEMPO/PROB dahil) en düşük
    tavanını bulur. ltfj_analiz.metar_coz() METAR için BECMG/TEMPO sonrasını
    BİLEREK atar (bir METAR'a eklenmiş eğilim grubudur, 'şu anki durum'
    değil) - ama TAF'ın KENDİSİ zaten çok dönemli bir belge; burada o
    kesme YAPILMAZ, tüm dönemler taranır (aksi halde örn. bir BECMG
    grubundaki düşük tavan sessizce atlanırdı)."""
    tokenlar = tokenla(taf_metni)
    if "RMK" in tokenlar:
        tokenlar = tokenlar[:tokenlar.index("RMK")]
    en_dusuk = None
    for t in tokenlar:
        m = RE_BULUT.match(t)
        if not m:
            continue
        ortu, taban, _tur = m.groups()
        if ortu not in TAVAN_KATMANLARI or taban == "///":
            continue
        ft = int(taban) * 100
        en_dusuk = ft if en_dusuk is None else min(en_dusuk, ft)
    return en_dusuk


def taf_tavan_notu(en_dusuk_tavan_ft: int | None) -> str | None:
    """en_dusuk_tavan_ft: taf_en_dusuk_tavan_ft()'in döndürdüğü değer -
    TAF'in TÜM dönemlerinde (BECMG/TEMPO dahil) geçen en düşük tavan."""
    if en_dusuk_tavan_ft is None or en_dusuk_tavan_ft >= CEILING_FARKINDALIK_ESIGI_FT:
        return None
    return (f"TAF döneminde öngörülen en düşük tavan {en_dusuk_tavan_ft} ft — düşük. "
            f"{_HEDGE}")


def rvr_notu(pist: str, pozisyon: str, deger_m: int) -> str | None:
    """Manuel AWOS RVR değerini (gerçek ölçüm) dokümanın kendi eşikleriyle
    (RVR_ESIKLERI) karşılaştırır; en derin (en küçük esik_altinda_m) geçilen
    eşiği bulur. Hiçbir eşik geçilmemişse None döner."""
    gecilen = [e for e in RVR_ESIKLERI if deger_m < e["esik_altinda_m"]]
    if not gecilen:
        return None
    en_derin = min(gecilen, key=lambda e: e["esik_altinda_m"])
    return (f"{pist} {pozisyon} AWOS RVR {deger_m} m — dokümanın "
            f"{en_derin['esik_altinda_m']} m eşiğinin ({en_derin['safha']}) altında. "
            f"{_HEDGE}")


def tavan_istatistik_notu(cozum: dict | None) -> str | None:
    """METAR'in KENDI spread/gorus degerlerini dondurulmus tavan tablosunda
    (ltfj_tavan_tablosu) arar ve GORELI risk olarak not eder.

    Digerlerinden farki: bu not bir ESIK GECILDIGI icin degil, gecmis
    arsivde bu kosullarda ne siklikta dusuk tavan goruldugu icin cikar.
    Bu yuzden metin MUTLAK YUZDE degil KAT soyler - tablonun seviyesi
    donemler arasi ~2.3 kat kayiyor, sirasi ise tasiniyor (bkz.
    ltfj_tavan_tablosu bas kismi).

    Tablonun hedefi 500 ft; CAT II esigi (200 ft) DEGIL. Nedeni arsivde:
    200 ft esiginde 18 yilda yalnizca ~61 bagimsiz olay var, tablo
    kurulamiyor. Metin bu yuzden 500 ft'i acikca yaziyor - okuyanin CAT II
    sandigi bir sey sunulmuyor.
    """
    if not cozum:
        return None
    sicaklik, cig = cozum.get("sicaklik"), cozum.get("cig_noktasi")
    if sicaklik is None or cig is None:
        return None
    hucre = tavan_tablosu.kat(spread=sicaklik - cig, gorus=cozum.get("gorus"))
    if hucre is None or hucre["kat"] < TAVAN_KAT_ESIGI:
        return None

    metin = (
        f"Şu anki spread ({hucre['spread_araligi']}) ve görüş ({hucre['gorus_araligi']}) "
        f"şartlarında, bulut tabanının önümüzdeki {tavan_tablosu.HEDEF_UFUK_SAAT} saat "
        f"içinde {tavan_tablosu.HEDEF_TAVAN_FT} ft altına inmesi LTFJ arşivinde "
        f"normalden çok daha sık görülmüş: ortalama şartlara göre yaklaşık "
        f"{hucre['kat']:.0f} kat daha sık (olası aralık "
        f"{hucre['alt']:.0f}–{hucre['ust']:.0f} kat)."
    )
    if hucre["ince"]:
        metin += f" Bu bantta yalnızca {hucre['n']} gözlem var; aralık geniş."
    return (
        f"{metin} Bu bir olasılık yüzdesi değil, GÖRELİ bir kıyaslamadır — mutlak "
        f"olasılık değildir, kesin bir yüzde olarak okunmamalıdır. LTFJ "
        f"{tavan_tablosu.KAYNAK_DONEM} arşivinden öğrenilmiştir. {_HEDGE}"
    )


def tavan_dis_kaynak_notu(cozum: dict | None, sis_olasilik_p: float | None,
                          saat_utc: int | None) -> str | None:
    """Çok değişkenli (dış kaynak destekli, geri düşmeli) tavan<500ft
    modelinin (bkz. ltfj_tavan_dis_kaynak.py) GÖRELİ risk notu -
    tavan_istatistik_notu ile AYNI "kat" dili, ama daha fazla değişkeni
    (özellikle sis_olasılık + varsa canlı bölgesel nem/komşu istasyon
    tavanı) BİRLİKTE ağırlıklandırarak üretilir - sis_modeli/
    tavan_dis_kaynak_model.py'de HOLDOUT'TA doğrulandı.

    sis_olasilik_p ve saat_utc ÇAĞIRAN TARAFTAN gelir (ltfj_sayfa.py zaten
    sis kartı için hesaplıyor) - burada YENİDEN hesaplanmaz, aynı METAR
    anından tutarlı bir değer kullanılır.

    Dış kaynak (Open-Meteo/LTFM, bkz. ltfj_dis_kaynak_cache.py) BAYAT veya
    HENÜZ mevcut değilse SESSİZCE TEMEL modele (yalnızca METAR + sis
    olasılığı) düşer - hata vermez, not üretmeyi bırakmaz."""
    if not cozum or sis_olasilik_p is None or saat_utc is None:
        return None
    sicaklik, cig = cozum.get("sicaklik"), cozum.get("cig_noktasi")
    if sicaklik is None or cig is None:
        return None
    ruzgar_k = sis_olasilik.ruzgar_kuzey_bileseni(
        cozum.get("ruzgar_yon"), cozum.get("ruzgar_hiz"))
    tavan_deger = cozum.get("tavan")

    dis = dis_kaynak_onbellek.oku()
    p = tavan_dis_kaynak.olasilik(
        spread=sicaklik - cig, gorus=cozum.get("gorus"),
        tavan_ozellik=_TAVAN_YOK_FT if tavan_deger is None else tavan_deger,
        saat=saat_utc, ruzgar_kuzey=ruzgar_k, sis_olasilik=sis_olasilik_p,
        acik_meteo_nem_2m=dis.get("acik_meteo_nem_2m"),
        komsu_tavan_ozellik=dis.get("komsu_tavan_ozellik"))
    if p is None or tavan_dis_kaynak.TABAN_ORAN <= 0:
        return None
    kat = p / tavan_dis_kaynak.TABAN_ORAN
    if kat < TAVAN_DIS_KAYNAK_KAT_ESIGI:
        return None

    genis_mi = (dis.get("acik_meteo_nem_2m") is not None
               and dis.get("komsu_tavan_ozellik") is not None)
    kaynak_notu = ("bölgesel nem ve komşu istasyon verisi dahil" if genis_mi
                   else "şu an yalnızca METAR verisiyle - bölgesel veri kaynağı geçici olarak kullanılamıyor")
    return (
        f"Çok değişkenli istatistiksel modele göre ({kaynak_notu}), bulut "
        f"tabanının önümüzdeki {tavan_dis_kaynak.HEDEF_UFUK_SAAT} saat içinde "
        f"{tavan_dis_kaynak.HEDEF_TAVAN_FT} ft altına inmesi normalden "
        f"yaklaşık {kat:.0f} kat daha olası görünüyor. Bu bir olasılık "
        f"yüzdesi değil, GÖRELİ bir kıyaslamadır — kesin bir tahmin değildir. "
        f"{_HEDGE}"
    )
