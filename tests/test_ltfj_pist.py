"""ltfj_pist.py testleri: pist bilesenleri, RVR, renk durumu, PRS, LVTO/CAT.

Tum boundary/deger beklentileri once gercek kodun ciktisina bakilarak
(varsayimla degil) dogrulandiktan sonra buraya yazildi.
"""
import pytest

import ornekler as o
from ltfj_analiz import metar_coz
from datetime import datetime, timezone

from ltfj_pist import (
    bilesenler,
    bilesenler_araligi,
    en_dusuk_rvr,
    esik_karsilastir,
    gorus_operasyonu,
    havacilik_notlari,
    kuyruk_asanlar,
    kuyruk_limiti,
    pist_raporu,
    pist_ruzgarlari,
    prs_askida,
    renk_durumu,
    rvr_gruplari,
    rvr_kayitlari,
    sis_riski,
    tercih_edilen_pist,
)


# --------------------------------------------------------------- bilesenler
def test_tam_bas_ruzgarinda_kuyruk_sifir_crosswind_sifir():
    bas, yan, _ = bilesenler(64.10, 15, 64.10)
    assert bas == pytest.approx(15, abs=1e-9)
    assert yan == pytest.approx(0, abs=1e-9)


def test_tam_kuyruk_ruzgarinda_bas_negatif():
    bas, yan, _ = bilesenler(244.10, 15, 64.10)
    assert bas == pytest.approx(-15, abs=1e-9)
    assert yan == pytest.approx(0, abs=1e-9)


def test_tam_yan_ruzgarinda_bas_sifir():
    bas, yan, taraf = bilesenler(64.10 + 90, 15, 64.10)
    assert bas == pytest.approx(0, abs=1e-9)
    assert yan == pytest.approx(15, abs=1e-9)


def test_bilesenler_yon_veya_hiz_yoksa_none():
    assert bilesenler(None, 10, 64.10) == (None, None, None)
    assert bilesenler(60, None, 64.10) == (None, None, None)


@pytest.mark.parametrize("yon,taraf_beklenen", [(64.10 + 30, "sağdan"), (64.10 - 30, "soldan")])
def test_yan_ruzgar_tarafi(yon, taraf_beklenen):
    _, _, taraf = bilesenler(yon, 10, 64.10)
    assert taraf == taraf_beklenen


# --------------------------------------------------------------- pist secimi
def test_tercih_edilen_pist_field_metar_fallback():
    """RMK yoksa alan METAR ruzgarina dusuluyor. 06L ve 06R AYNI eksende
    (64.10) oldugundan alan-ruzgari senaryosunda skorlari esit olur; kod
    TERCIHLI_PISTLER tuple sirasina gore (06L,24R,06R,24L) ilk gorduguyle
    esitligi bozuyor - bu test o emergent davranisi sabitliyor."""
    d = metar_coz(o.NORMAL)  # 060/10, RMK yok
    assert tercih_edilen_pist(d, o.NORMAL) == "06L"


def test_tercih_edilen_pist_kuvvetli_kuyruk_senaryosu():
    metin = "METAR LTFJ 161250Z 24025KT 9999 SCT025 18/12 Q1015 NOSIG"
    d = metar_coz(metin)
    assert tercih_edilen_pist(d, metin) == "24R"


def test_tercih_edilen_pist_rmk_kismiyken_eksik_pist_de_adaydir():
    """DUZELTME: RMK'da SADECE 24R/06R/24L raporlanmis (06L yok). Eskiden
    tercih_edilen_pist() "olculenler or [tum pistler alan ruzgarindan]"
    mantigiyla RMK varsa SADECE RMK'daki pistleri degerlendiriyordu - 06L
    hicbir zaman aday bile olamiyordu, ayni pist_ruzgar_kaynagi() sinifindaki
    (F2) hatanin bu fonksiyonda AYRI bir tekrariydi. Artik ortak
    pist_ruzgar_kaynagi() uzerinden 06L de alan METAR ruzgarina (04007KT)
    duserek adaya giriyor ve gercekte en iyi bas ruzgarini (~6.4 kt) o
    veriyor - digerleri kuyruk ruzgari (24L/24R) ya da daha dusuk bas
    ruzgari (06R, ~4.1 kt) aliyor."""
    d = metar_coz(o.PIST_RUZGARI_RMK)
    assert tercih_edilen_pist(d, o.PIST_RUZGARI_RMK) == "06L"


def test_kuyruk_asanlar_normal_ruzgarda_bos():
    d = metar_coz(o.NORMAL)
    assert kuyruk_asanlar(d, o.NORMAL) == []


def test_kuyruk_asanlar_kuvvetli_kuyrukta_dolar():
    metin = "METAR LTFJ 161250Z 24025KT 9999 SCT025 18/12 Q1015 NOSIG"
    d = metar_coz(metin)
    # 244 yonunden 25kt ruzgar -> 06L/06R pistlerinde ~25kt kuyruk, kuru limit
    # 10kt'yi asiyor.
    assert kuyruk_asanlar(d, metin) == ["06L", "06R"]


def test_kuyruk_asanlar_rmk_kismi_iken_eksik_pist_alan_ruzgarina_duser():
    """F2: RMK sadece 24R/24L icin anemometre verisi tasiyorsa, RMK'da hic
    gecmeyen 06L/06R onceden TAMAMEN atlaniyordu (kuyruk limiti asimi bile
    olsa raporlanmiyordu). Alan METAR ruzgari (240/25) bu pistlerde guclu
    kuyruk ruzgari anlamina geliyor - artik dogru sekilde yakalaniyor."""
    d = metar_coz(o.PIST_RUZGARI_RMK_KISMEN_KUYRUK)
    assert kuyruk_asanlar(d, o.PIST_RUZGARI_RMK_KISMEN_KUYRUK) == ["06L", "06R"]


# ------------------------------------------------------------ kuyruk_limiti
def test_kuyruk_limiti_yagis_varsa_islak_5kt():
    d = metar_coz(o.YAGMUR)
    limit, gerekce = kuyruk_limiti(d)
    assert limit == 5 and "ıslak" in gerekce


def test_kuyruk_limiti_yagis_yoksa_kuru_10kt():
    d = metar_coz(o.NORMAL)
    limit, gerekce = kuyruk_limiti(d)
    assert limit == 10 and "kuru" in gerekce


def test_kuyruk_limiti_gerekcesi_cikarsanan_oldugunu_belirtir():
    """RWYCC METAR'da hiç yayınlanmıyor; bu limit AIP/operator'den doğrudan
    okunan resmi bir değer değil, yağış varlığına bakarak PROGRAMIN
    ÇIKARDIĞI konservatif bir varsayım. Gerekçe metni bunu açıkça
    'CIKARSANAN varsayım' diye etiketlemeli - aksi halde gerçek bir RWYCC
    limitiymiş izlenimi verir."""
    _, gerekce = kuyruk_limiti(metar_coz(o.NORMAL))
    assert "CIKARSANAN" in gerekce
    assert "RWYCC" in gerekce


# ------------------------------------------------------------------ RMK yok
def test_pist_ruzgarlari_rmk_yoksa_bos_liste():
    assert pist_ruzgarlari(o.NORMAL) == []


def test_pist_ruzgarlari_rmk_varsa_parse_edilir():
    kayitlar = pist_ruzgarlari(o.PIST_RUZGARI_RMK)
    pistler = {k["pist"] for k in kayitlar}
    assert pistler == {"24R", "06R", "24L"}


# --------------------------------------------------------------- pist_raporu
def test_pist_raporu_golden_alan_ruzgari():
    """2026-09-17 degisikligi: pist_raporu() artik HESAPLANAN bas/kuyruk/yan
    bilesenini degil, METAR/RMK'da NE YAZILIYSA onu (ham yon/hiz) gosterir -
    kullanici raporlanan RMK degeriyle ekrandaki sayinin FARKLI gorunmesinin
    (trigonometrik donusum sonucu) kafa karistirdigini bildirdi. RMK yoksa
    (bu ornek) her 4 pist de alan METAR ruzgarina (060°/10kt) duser."""
    d = metar_coz(o.NORMAL)  # 060/10, RMK yok -> alan ruzgarina dusuluyor
    assert pist_raporu(d, o.NORMAL) == [
        "06L: 060° 10 kt",
        "06R: 060° 10 kt",
        "24L: 060° 10 kt",
        "24R: 060° 10 kt",
        "(alan rüzgârından; kuyruk limiti 10 kt — CIKARSANAN varsayım — "
        "RWYCC bildirilmedi, yağış yok, kuru pist kabul edildi)",
    ]


def test_pist_raporu_golden_rmk_anemometreleri():
    """F2 duzeltmesinden ONCE bu test 06L'in RMK'da bildirilmedigi icin
    ciktida hic gorunmedigini sabitliyordu (o pist sessizce kayboluyordu).
    Duzeltmeden sonra RMK'da GECMEYEN her pist kendi basina alan METAR
    ruzgarina (04007KT) duser ve ciktida kalir; kaynak karisikligi
    footer'da pist bazinda ayristirilarak belirtilir.

    2026-09-17: satirlar artik HAM RMK degerini (yon/hiz, degisken ise
    340V080 gibi aralik) gosteriyor - bilesene CEVRILMIYOR (bkz.
    test_pist_raporu_golden_alan_ruzgari notu)."""
    d = metar_coz(o.PIST_RUZGARI_RMK)
    assert pist_raporu(d, o.PIST_RUZGARI_RMK) == [
        "06L: 040° 7 kt",
        "06R: 010° 7 kt",
        "24L: 030° 6 kt",
        "24R: 360° (değişken 340°–080°) 7 kt",
        "(06L: alan rüzgârından; 06R, 24L, 24R: AD 2.15 anemometreleri; "
        "kuyruk limiti 5 kt — CIKARSANAN varsayım — RWYCC bildirilmedi, "
        "yağış nedeniyle ıslak/kirli pist kabul edildi)",
    ]


def test_pist_raporu_golden_kuyruk_limit_asimi_isaretlenir():
    """PRS arka ruzgar limiti asimi artik pist basina degil (satir HAM
    deger tasidigi icin), footer'da ayri, acikca 'hesaplanan' etiketli bir
    liste olarak gosteriliyor - kuyruk_asanlar() hala trig kullaniyor, ama
    ciktisi sadece pist kodu (06L, 06R), ham bir sayi degil."""
    d = metar_coz(o.FIRTINA)
    satirlar = pist_raporu(d, o.FIRTINA)
    footer = satirlar[-1]
    assert "PRS arka rüzgâr limitini aşan pist(ler) (hesaplanan): 06L, 06R" in footer


def test_pist_raporu_hamleli_ruzgarda_steady_ve_gust_ayri_gosterilir():
    """FIRTINA: 25022G35KT - steady 22 kt, hamle 35 kt. Ham deger olarak
    ikisi ayri ayri gosterilir (asil hiz + parantezde hamle)."""
    d = metar_coz(o.FIRTINA)
    satirlar = pist_raporu(d, o.FIRTINA)
    satir_06L = next(s for s in satirlar if s.startswith("06L"))
    assert satir_06L == "06L: 250° 22 kt (hamle 35 kt)"


def test_pist_raporu_hamlesiz_ruzgarda_parantez_yok():
    d = metar_coz(o.NORMAL)  # 06010KT, hamlesiz
    satirlar = pist_raporu(d, o.NORMAL)
    assert not any("hamle" in s for s in satirlar[:-1])


def test_pist_raporu_degisken_yonde_yon_bilgisi_acikca_belirsiz():
    """VRB (tamamen degisken yon, ozel bir aralik grubu degil) icin pist
    basina 'degisken yon' yaziliyor - olmayan bir kesin deger UYDURULMUYOR."""
    d = metar_coz(o.DEGISKEN_RUZGAR)
    satirlar = pist_raporu(d, o.DEGISKEN_RUZGAR)
    assert all("değişken yön" in s for s in satirlar[:4])


# ------------------------------------------------------- degisken yon ark
def test_bilesenler_araligi_pist_ekseni_arkta_ise_tam_ruzgar_ulasilir():
    """Ark [20,90] pist ekseni 64.10'u icerdiginden azami bas ruzgari
    neredeyse tam hiz'e (8 kt) ulasmali (ark ic ice 1 derecelik adimlarla
    tarandigindan 64 ya da 65 dereceye isabet eder, tam 64.10'a degil -
    bu yuzden yaklasik, kesin degil)."""
    aralik = bilesenler_araligi(20, 90, 8, 64.10)
    assert aralik["bas_max"] == pytest.approx(8, abs=0.05)
    assert aralik["bas_min"] > 5   # ark disinda kuyruk noktasi (244.10) yok


def test_bilesenler_araligi_sarma_360_gecisini_dogru_isler():
    """340V080: ark 0/360'i geciyor (saat yonunde 340'tan 80'e). Pist
    ekseni 244.12 (24R icin) bu arkin DISINDA - ark boyunca hep kuyruk
    ruzgari cikmali (bas_max <= 0)."""
    aralik = bilesenler_araligi(340, 80, 7, 244.12)
    assert aralik["bas_max"] <= 0
    assert aralik["bas_min"] == pytest.approx(-7, abs=0.05)


def test_bilesenler_araligi_hiz_yoksa_none():
    assert bilesenler_araligi(20, 90, None, 64.10) is None


def test_pist_raporu_degisken_yon_grubu_araligi_gosterir():
    """DEGISKEN_YON_GRUBU: ortalama yon 050 (mean wind, hiz 8), ama METAR
    ayrica '020V090' degisken yon grubu tasiyor. Bu HAM aralik METAR'da
    nasil yaziliysa oyle (ortalama yon + degisken araligi ayri ayri)
    gosterilir - tek bir 'kesin' bilesen sayisi UYDURULMAZ."""
    d = metar_coz(o.DEGISKEN_YON_GRUBU)
    satirlar = pist_raporu(d, o.DEGISKEN_YON_GRUBU)
    for s in satirlar[:4]:
        assert "050° (değişken 020°–090°) 8 kt" in s


# ------------------------------------------------------------------- RVR
def test_rvr_kayitlari_tekli():
    kayitlar = rvr_kayitlari(o.RVR_TEK)
    assert kayitlar == [{"pist": "06R", "deger": 550, "on_ek": "", "ust": None,
                          "ust_on_ek": "", "egilim": "N"}]


def test_rvr_kayitlari_p_m_onekleri():
    kayitlar = rvr_kayitlari(o.RVR_PM)
    onekler = {k["pist"]: k["on_ek"] for k in kayitlar}
    assert onekler == {"06R": "M", "24L": "P"}


def test_rvr_kayitlari_degisken():
    kayitlar = rvr_kayitlari(o.RVR_DEGISKEN)
    assert kayitlar[0]["ust"] == 800 and kayitlar[0]["egilim"] == "U"


def test_rvr_gruplari_metin_bicimi():
    assert rvr_gruplari(o.RVR_TEK) == ["06R: 550 m, sabit"]
    assert rvr_gruplari(o.RVR_DEGISKEN) == ["06R: 400 m – 800 m arası değişken, yükseliyor"]


def test_rvr_kayitlari_degisken_ust_oneki_korunur():
    """F1: degisken RVR'nin ust (ikinci) degerindeki P/M oneki onceden
    regex'te yakalanip sessizce atiliyordu (v_ek grubu kullanilmiyordu).
    Artik ust_on_ek alaninda saklaniyor."""
    kayitlar = rvr_kayitlari(o.RVR_DEGISKEN_UST_ONEKLI)
    assert kayitlar[0]["ust_on_ek"] == "P"
    assert kayitlar[0]["ust_on_ek"] != ""


def test_rvr_gruplari_ust_oneki_metne_yansir():
    assert rvr_gruplari(o.RVR_DEGISKEN_UST_ONEKLI) == [
        "06R: 600 m – en az 2000 m arası değişken, sabit"
    ]


def test_en_dusuk_rvr_rvr_yoksa_none():
    assert en_dusuk_rvr(o.NORMAL) is None


def test_en_dusuk_rvr_birden_fazla_pistin_minimumu():
    assert en_dusuk_rvr(o.RVR_PM) == 350  # min(350, 2000)


# ------------------------------------------------------- esik_karsilastir
@pytest.mark.parametrize("deger,on_ek,esik,beklenen", [
    (399, "", 400, "evet"), (400, "", 400, "hayir"), (401, "", 400, "hayir"),
    (300, "M", 400, "evet"),      # M300: gercek<=300<400 -> kesin altinda
    (400, "M", 400, "belirsiz"),  # M400: gercek<=400, 400 esigin ALTINDA degil ama olabilir
    (600, "M", 400, "belirsiz"),  # M600: gercek 0-600 arasi herhangi bir sey olabilir
    (2000, "P", 400, "hayir"),    # P2000: gercek>=2000>=400 -> kesin ustunde
    (300, "P", 400, "belirsiz"),  # P300: gercek>=300, esigin altinda mi bilinmiyor
])
def test_esik_karsilastir_p_m_semantigi(deger, on_ek, esik, beklenen):
    assert esik_karsilastir(deger, on_ek, esik) == beklenen


# ------------------------------------------------------------- LVTO / CAT
@pytest.mark.parametrize("rvr_deger,lvto_beklenir,cat1_beklenir", [
    (399, True, True), (400, False, True), (401, False, True),
    (549, False, True), (550, False, False), (551, False, False),
])
def test_gorus_operasyonu_rvr_siniri(rvr_deger, lvto_beklenir, cat1_beklenir):
    metin = f"METAR LTFJ 161250Z 06005KT 9999 R06R/{rvr_deger:04d}N FEW030 18/12 Q1015"
    d = metar_coz(metin)
    notlar = gorus_operasyonu(d, metin)
    assert any("LVTO" in n for n in notlar) == lvto_beklenir
    assert any("CAT I" in n for n in notlar) == cat1_beklenir


def test_gorus_operasyonu_rvr_yoksa_gorus_kullanilir():
    metin = "METAR LTFJ 161250Z 06005KT 0300 FG VV001 05/05 Q1020"
    d = metar_coz(metin)
    notlar = gorus_operasyonu(d, metin)
    assert any("CAT I" in n for n in notlar)  # 300m < 550 tipik esik


def test_gorus_operasyonu_m_onekli_sinirda_belirsiz_diyor():
    """DUZELTME (esik_karsilastir): 'M' oneki (ICAO Annex 3) gercek RVR'nin
    raporlanandan daha dusuk olabilecegini belirtir - M0400, gercek degerin
    0-400 arasinda herhangi bir sey olabilecegi anlamina gelir. Esik tam
    400 (LVTO_RVR) oldugunda "400 < 400" (naif karsilastirma) "hayir" derdi
    - oysa gercek deger 400'un cok altinda olabilir. Artik bu durum acikca
    'belirsiz' olarak isaretleniyor, ne "LVTO yok" ne de "LVTO var" diye
    KESIN bir iddia YAPILMIYOR (kesin olmayan veriyi kesin gibi sunmama
    ilkesi). CAT I esigi (550) icin ise 400 < 550 KESIN dogru (M0400 ->
    gercek <= 400 < 550), o yuzden CAT I orada KESIN 'evet'."""
    d = metar_coz(o.RVR_M_ESIK)
    notlar = gorus_operasyonu(d, o.RVR_M_ESIK)
    assert any("LVTO durumu belirsiz" in n and "R06R" in n for n in notlar)
    assert not any(n.startswith("LVTO yürürlükte") for n in notlar)
    assert any("CAT I" in n and "tipik CAT I eşiği" in n for n in notlar)


def test_gorus_operasyonu_m_oneki_esigin_altindaysa_kesin_evet():
    """M0300 ile LVTO esigi 400: 300 < 400 oldugundan (M -> gercek <= 300)
    gercek deger KESIN olarak 400'un altinda - burada belirsizlik yok,
    dogrudan LVTO yürürlükte denebilir."""
    metin = "METAR LTFJ 161250Z 06005KT 9999 R06R/M0300N FEW030 18/12 Q1015"
    d = metar_coz(metin)
    notlar = gorus_operasyonu(d, metin)
    assert any(n.startswith("LVTO yürürlükte") for n in notlar)
    assert not any("belirsiz" in n for n in notlar)


def test_gorus_operasyonu_oneksiz_rvr_belirsiz_uretmez():
    d = metar_coz(o.RVR_TEK)
    notlar = gorus_operasyonu(d, o.RVR_TEK)
    assert not any("belirsiz" in n for n in notlar)


# ------------------------------------------------------------------- PRS
def test_prs_askida_firtinada_birden_fazla_sebep():
    d = metar_coz(o.FIRTINA)
    sebepler = prs_askida(d, o.FIRTINA)
    assert "gök gürültülü fırtına" in sebepler
    assert "şiddetli yağış" in sebepler


def test_prs_askida_ruzgar_kesmesinde():
    d = metar_coz(o.RUZGAR_KESMESI)
    sebepler = prs_askida(d, o.RUZGAR_KESMESI)
    assert any("rüzgâr kesmesi" in s for s in sebepler)


def test_prs_askida_normalde_bos():
    d = metar_coz(o.NORMAL)
    assert prs_askida(d, o.NORMAL) == []


def test_prs_askida_m_onekli_rvr_belirsiz_diye_isaretlenir():
    """M0400 (LVTO esigi 400 ile ayni) esik_karsilastir() tarafindan
    'belirsiz' donuyor (bkz. o testler) - prs_askida() bunu sessizce 'evet'
    ya da 'hayir' gibi davranmamali, pist kimligiyle birlikte belirsiz
    oldugunu belirtmeli."""
    d = metar_coz(o.RVR_M_ESIK)
    sebepler = prs_askida(d, o.RVR_M_ESIK)
    assert any("belirsiz" in s and "R06R" in s for s in sebepler)


# --------------------------------------------------------------- renk durumu
@pytest.mark.parametrize("tavan,gorus,beklenen_kod", [
    (2500, 8000, "BLU"), (2499, 8000, "WHT"), (2500, 7999, "WHT"),
    (1500, 5000, "WHT"), (1499, 5000, "GRN"),
    (700, 3700, "GRN"), (699, 3700, "YLO"),
    (300, 1600, "YLO"), (299, 1600, "AMB"),
    (200, 800, "AMB"), (199, 799, "RED"),
])
def test_renk_durumu_bant_sinirlari(tavan, gorus, beklenen_kod):
    kod, _ = renk_durumu({"tavan": tavan, "gorus": gorus})
    assert kod == beklenen_kod


def test_renk_durumu_tavan_yoksa_sinirsiz_sayilir():
    """EDGE CASE (rapor D bolumu): tavan=None -> kod tavani 99999 kabul
    ediyor, yani sadece gorus bandi belirleyici oluyor. Mevcut davranisi
    belgeliyoruz."""
    kod, _ = renk_durumu({"tavan": None, "gorus": 9000})
    assert kod == "BLU"


def test_renk_durumu_ikisi_de_yoksa_none():
    assert renk_durumu({"tavan": None, "gorus": None}) is None


# ------------------------------------------------------------ sis riski
def test_sis_riski_metnin_disclaimer_ilk_ikinokta_sonrasinda_hayatta_kalir():
    """ltfj_bot.py/ltfj_sayfa.py sis_riski() metnini ilk ':' isaretinden
    BOLUP sadece sonraki kismi gosteriyor. 'METAR tabanlı heuristik' uyarisi
    ve seviye kelimesi bu bolme sonrasi da kalmali, yoksa kullaniciya
    kesin bir tahmin gibi gorunur."""
    metin = "METAR LTFJ 161250Z 06003KT 9999 SCT025 10/09 Q1015 NOSIG"
    d = metar_coz(metin)
    tam = sis_riski(d, None)
    assert tam is not None
    sonrasi = tam.split(":", 1)[-1].strip()
    assert "heuristik" in sonrasi
    assert "resmi tahmin değil" in sonrasi
    assert "orta" in sonrasi or "yüksek" in sonrasi


def test_sis_riski_gece_seviyeyi_yukseltir():
    metin = "METAR LTFJ 161250Z 06003KT 9999 SCT025 10/09 Q1015 NOSIG"
    d = metar_coz(metin)
    gunduz = sis_riski(d, datetime(2026, 6, 1, 10, tzinfo=timezone.utc))
    gece = sis_riski(d, datetime(2026, 6, 1, 1, tzinfo=timezone.utc))
    assert gunduz is not None and "orta" in gunduz
    assert gece is not None and "yüksek" in gece


def test_sis_riski_genis_aralikta_none():
    metin = "METAR LTFJ 161250Z 06003KT 9999 SCT025 20/05 Q1015 NOSIG"
    d = metar_coz(metin)
    assert sis_riski(d, None) is None


def test_sis_riski_zaten_sis_varsa_none():
    d = metar_coz(o.SIS)
    assert sis_riski(d, None) is None


# --------------------------------------------------------- havacilik_notlari
def test_havacilik_notlari_varsayimlar_kuyruk_gerekcesini_tasir():
    """P2: kuyruk_limiti()'nin CIKARSANAN gerekcesi her zaman en az bir
    varsayim olarak listelenir - RWYCC hicbir METAR'da yayinlanmiyor,
    dolayisiyla bu varsayim HER METAR icin gecerlidir."""
    d = metar_coz(o.NORMAL)
    n = havacilik_notlari(d, o.NORMAL, None)
    assert any("CIKARSANAN" in v and "RWYCC" in v for v in n["varsayimlar"])


def test_havacilik_notlari_sis_varsa_varsayimlara_da_eklenir():
    metin = "METAR LTFJ 161250Z 06003KT 9999 SCT025 10/09 Q1015 NOSIG"
    d = metar_coz(metin)
    n = havacilik_notlari(d, metin, None)
    assert n["sis"] is not None
    assert n["sis"] in n["varsayimlar"]


def test_havacilik_notlari_renk_etiketi_resmi_olmadigini_belirtir():
    d = metar_coz(o.NORMAL)
    n = havacilik_notlari(d, o.NORMAL, None)
    assert n["renk_etiketi"] == "LTFJ Bot durum seviyesi"
