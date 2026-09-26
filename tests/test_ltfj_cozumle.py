# -*- coding: utf-8 -*-
"""ltfj_cozumle: METAR/TAF gruplarının satır satır Türkçeye çevrilmesi.

Bu testlerin ASIL İŞİ "çıktı boş değil mi" demek DEĞİL. Çözümleyicinin
iki kusuru sessizdir ve ikisi de tehlikelidir:
  1) YANLIŞ çevirir (400 ft'e 4000 ft demek gibi) - kimse fark etmez,
  2) ANLAMADIĞINI belli etmeden atar - okuyan raporu tam sanır.
Testler ikisini de hedefler.
"""
import pytest

import ltfj_cozumle as c


def _ad(satirlar, ad):
    return [s for s in satirlar if s["ad"] == ad]


def _token(satirlar, token):
    return next(s for s in satirlar if s["token"] == token)


# ===================================================== yön ve ek

@pytest.mark.parametrize("derece, beklenen", [
    (0, "kuzey"), (350, "kuzey"), (10, "kuzey"),
    (40, "kuzeydoğu"), (67, "kuzeydoğu"),     # sınır 67.5'te
    (68, "doğu"), (90, "doğu"),
    (180, "güney"), (270, "batı"), (315, "kuzeybatı"),
    (360, "kuzey"),
])
def test_yon_adi_SEKIZ_dilime_dogru_oturuyor(derece, beklenen):
    assert c.yon_adi(derece) == beklenen


def test_gun_eki_TURKCE_okunusa_gore(): 
    """'ayın 26'i' diye bir şey yok. Ek sayının SON OKUNAN kelimesine
    göre değişir; tek bir "'i" kullanmak günlerin yarısını bozuyordu."""
    beklenen = {1: "i", 2: "si", 3: "ü", 6: "sı", 9: "u", 10: "u",
                16: "sı", 20: "si", 23: "ü", 26: "sı", 29: "u",
                30: "u", 31: "i"}
    for gun, ek in beklenen.items():
        assert c.gun_eki(gun) == ek, gun


def test_gun_eki_her_gun_icin_tanimli():
    for gun in range(1, 32):
        assert c.gun_eki(gun) in ("i", "si", "sı", "ü", "u")


# ===================================================== tekil gruplar

def test_ruzgar_yon_hiz_ve_hamle():
    s = c.grup_coz("12015G25KT")
    assert s["cozuldu"] and s["ad"] == "Rüzgâr"
    assert "120°" in s["aciklama"]
    assert "15 kt" in s["aciklama"]
    assert "25 kt" in s["aciklama"] and "hamle" in s["aciklama"]


def test_ruzgar_degisken_yon_DERECE_UYDURMUYOR():
    """VRB'de yön YOKTUR. Bir derece yazmak uydurmaktır."""
    s = c.grup_coz("VRB03KT")
    assert "Değişken yönlü" in s["aciklama"]
    assert "°" not in s["aciklama"]


def test_ruzgar_MPS_birimi_KT_diye_yazilmaz():
    """Birim çevrilmiyor, OLDUĞU GİBİ söyleniyor: 5 m/s'ye '5 kt'
    demek iki kat hata olurdu."""
    s = c.grup_coz("04005MPS")
    assert "m/s" in s["aciklama"] and " kt" not in s["aciklama"]


@pytest.mark.parametrize("token, ft", [
    ("FEW004", "400 ft"), ("SCT035", "3500 ft"),
    ("BKN100", "10000 ft"), ("OVC003", "300 ft"),
])
def test_bulut_tabani_YUZ_ile_carpiliyor(token, ft):
    """METAR bulut tabanını 100 ft biriminde verir. Çarpmayı unutmak
    400 ft'lik bir tavanı 4 ft ya da 4000 ft gösterirdi."""
    assert ft in c.grup_coz(token)["aciklama"]


def test_bulut_CB_turu_soyleniyor():
    s = c.grup_coz("FEW020CB")
    assert "2000 ft" in s["aciklama"] and "kümülonimbus" in s["aciklama"]


def test_dikey_gorus_BULUT_degil():
    """VV002 bir bulut katmanı değil, dikey görüştür - 'kapalı' demek
    yanlış olurdu."""
    s = c.grup_coz("VV002")
    assert s["ad"] == "Dikey görüş" and "200 ft" in s["aciklama"]


def test_bulut_yuksekligi_olculemedigi_soyleniyor():
    s = c.grup_coz("BKN///")
    assert s["cozuldu"] and "ölçülemedi" in s["aciklama"]


def test_gorus_9999_ON_KM_VE_UZERI():
    """9999 '9999 m' değil, '10 km ve üzeri' demektir."""
    assert "10 km ve üzeri" in c.grup_coz("9999")["aciklama"]


def test_gorus_0000_ELLI_METREDEN_AZ():
    assert "50 m'den az" in c.grup_coz("0000")["aciklama"]


def test_gorus_ara_deger_oldugu_gibi():
    assert "4000 m" in c.grup_coz("4000")["aciklama"]


def test_sicaklik_eksi_isareti_M_ile_geliyor():
    s = c.grup_coz("M02/M05")
    assert "-2 °C" in s["aciklama"] and "-5 °C" in s["aciklama"]


def test_sicaklik_spread_hesaplaniyor():
    assert "spread 4 °C" in c.grup_coz("17/13")["aciklama"]


def test_qnh_hPa():
    assert "QNH 1018 hPa" in c.grup_coz("Q1018")["aciklama"]


def test_altimetre_inHg_hPa_karsiligiyla():
    s = c.grup_coz("A3003")
    assert "30.03 inHg" in s["aciklama"] and "1017 hPa" in s["aciklama"]


@pytest.mark.parametrize("token, parca", [
    ("R06L/0800", "Pist 06L"),
    ("R24R/P2000", "üzerinde"),
    ("R06R/M0050", "altında"),
])
def test_rvr_nitelikleri(token, parca):
    s = c.grup_coz(token)
    assert s["cozuldu"] and s["ad"] == "RVR" and parca in s["aciklama"]


def test_rvr_degisken_ve_egilim():
    s = c.grup_coz("R06L/0500V0900U")
    assert "değişken" in s["aciklama"] and "yükseliyor" in s["aciklama"]


def test_hava_olayi_siddet_ve_tanimlayici():
    assert c.grup_coz("-SHRA")["aciklama"] == "Hafif sağanak yağmur"
    assert c.grup_coz("+TSRA")["aciklama"].startswith("Kuvvetli gök gürültülü")


def test_yakin_gecmis_hava_olayi_SU_AN_degil():
    """RERA 'şu an yağmur' değil, 'gözlemden önce yağmur' demektir."""
    s = c.grup_coz("RERA")
    assert s["ad"] == "Yakın geçmiş" and "önce" in s["aciklama"]


def test_yonlu_gorus():
    s = c.grup_coz("2000NE")
    assert "Kuzeydoğuda" in s["aciklama"] and "2000 m" in s["aciklama"]


def test_zaman_grubu_AY_YIL_UYDURMUYOR():
    """METAR gün+saat taşır, ay ve yıl TAŞIMAZ."""
    s = c.grup_coz("261450Z")
    assert "26" in s["aciklama"] and "14:50" in s["aciklama"]
    for yasak in ("Eylül", "2026", "/"):
        assert yasak not in s["aciklama"]


def test_bulut_yok_kodlari_AYIRT_EDILIYOR():
    """NSC ile NCD aynı şey değil: biri 'önemli bulut yok', öteki
    'otomatik istasyon bulut saptayamadı'."""
    assert c.grup_coz("NSC")["aciklama"] != c.grup_coz("NCD")["aciklama"]
    assert "otomatik" in c.grup_coz("NCD")["aciklama"].lower()


def test_bilinmeyen_token_SESSIZCE_ATILMIYOR():
    """Çözülemeyen grup kaybolmaz - işaretlenir. Aksi halde okuyan
    raporun tamamını gördüğünü sanır."""
    s = c.grup_coz("ZZZZ9")
    assert s["cozuldu"] is False and s["token"] == "ZZZZ9"


def test_ICAO_kodu_YALNIZCA_basta_istasyon():
    """Bayrak olmadan raporun ortasındaki dört harfli her kod istasyon
    sanılırdı."""
    assert c.grup_coz("LTFJ", ilk_icao=True)["ad"] == "İstasyon"
    assert c.grup_coz("LTFJ", ilk_icao=False)["cozuldu"] is False


def test_CAVOK_istasyon_sanilmiyor():
    """CAVOK da dört harf - ilk_icao bayrağı açıkken bile istasyon
    olmamalı."""
    assert c.grup_coz("CAVOK", ilk_icao=True)["ad"] == "Görüş ve bulut"


# ===================================================== METAR bütünü

METAR = ("METAR LTFJ 252120Z 04008KT CAVOK 17/13 Q1018 NOSIG "
         "RMK RWY24R 02004KT 350V050 RWY06R 03007KT RWY24L 05005KT")


def test_metar_tum_gruplar_cozuldu():
    satirlar = c.metar_satirlari(METAR)
    assert c.cozulemeyenler(satirlar) == []


def test_metar_istasyon_ve_zaman_ayri_satir():
    satirlar = c.metar_satirlari(METAR)
    assert _ad(satirlar, "İstasyon") and _ad(satirlar, "Zaman")


def test_metar_RMK_SONRASI_TEK_SATIR():
    """RMK sonrası ulusal ek bilgidir; token token çözmeye çalışmak
    uydurmaya davettir. Tek satırda, ham hâliyle duruyor."""
    satirlar = c.metar_satirlari(METAR)
    notlar = _ad(satirlar, "Notlar")
    assert len(notlar) == 1
    assert notlar[0]["token"].startswith("RWY24R")
    # RMK icindeki gruplar AYRI satir olmamali
    assert not any(s["token"] == "02004KT" for s in satirlar)


def test_metar_RMK_ICINDEKI_ruzgar_ana_ruzgari_EZMIYOR():
    satirlar = c.metar_satirlari(METAR)
    ruzgarlar = _ad(satirlar, "Rüzgâr")
    assert len(ruzgarlar) == 1 and ruzgarlar[0]["token"] == "04008KT"


def test_metar_sonundaki_esittir_isareti_son_grubu_DUSURMUYOR():
    """'... Q1021=' - eşittir son token'a yapışık gelir."""
    satirlar = c.metar_satirlari("METAR LTFJ 252120Z 04008KT 9999 17/13 Q1021=")
    assert _ad(satirlar, "Basınç")


# ===================================================== TAF bütünü

TAF = ("TAF LTFJ 251640Z 2518/2618 04015KT CAVOK "
       "BECMG 2518/2521 04005KT "
       "PROB30 2602/2606 FEW004 "
       "BECMG 2607/2610 04015KT")


def test_taf_ilk_bolum_TAHMININ_BASLANGICI():
    b = c.taf_bolumleri(TAF)
    assert b[0]["baslik"] == "Tahminin başlangıcı"
    assert "25" in b[0]["pencere"] and "26" in b[0]["pencere"]


def test_taf_degisim_gruplari_AYRI_BOLUM():
    basliklar = [x["baslik"] for x in c.taf_bolumleri(TAF)]
    assert basliklar.count("Tedricen değişiyor") == 2
    assert "%30 olasılıkla" in basliklar


def test_taf_her_bolumun_KENDI_penceresi_var():
    for b in c.taf_bolumleri(TAF):
        assert b["pencere"], b["baslik"]


def test_taf_gecerlilik_BASLIKTA_satirda_DEGIL():
    """Geçerlilik penceresi bölümün kimliğidir; satır listesine
    düşerse her bölümde bir kez daha tekrarlanır."""
    for b in c.taf_bolumleri(TAF):
        assert not _ad(b["satirlar"], "Geçerlilik")


def test_taf_PROB30_TEMPO_TEK_bolum():
    """'PROB30 TEMPO' ikiye bölünürse '%30 olasılıkla' ve 'geçici
    olarak' diye birbirinden kopuk iki başlık çıkar."""
    metin = "TAF LTFJ 261040Z 2612/2712 05015KT PROB30 TEMPO 2622/2702 -SHRA BKN030"
    bolumler = c.taf_bolumleri(metin)
    basliklar = [b["baslik"] for b in bolumler]
    assert "%30 olasılıkla, geçici olarak" in basliklar
    assert "geçici olarak" not in basliklar


def test_taf_FM_grubu_bolum_basliyor():
    metin = "TAF LTFJ 261040Z 2612/2712 05015KT FM261800 09010KT 9999"
    basliklar = [b["baslik"] for b in c.taf_bolumleri(metin)]
    assert any("18:00" in x and "itibarıyla" in x for x in basliklar)


def test_taf_tum_gruplar_cozuldu():
    for b in c.taf_bolumleri(TAF):
        assert c.cozulemeyenler(b["satirlar"]) == [], b["baslik"]


def test_taf_bos_bolum_URETILMIYOR():
    for b in c.taf_bolumleri(TAF):
        assert b["satirlar"] or b["pencere"]
