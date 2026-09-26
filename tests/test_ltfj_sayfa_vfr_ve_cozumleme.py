# -*- coding: utf-8 -*-
"""Renk ölçeğinin sökülmesi + VFR bandı + METAR/TAF çözümlemesi.

Bu dosya, silinen testlerin YERİNE geçiyor. Bir sözleşmeyi kaldırmak
onu korumasız bırakmak demek değil: eskiden "renk rozeti doğru hesaptan
geliyor mu" diye bakılıyordu, şimdi "renk rozeti HİÇ YOK mu" diye
bakılıyor. İkisi de aynı ciddiyette kilitlenmeli, yoksa ölçek bir
sonraki düzenlemede sessizce geri sızar.
"""
import math
import re
from datetime import datetime, timezone

import pytest

from ltfj_sayfa import sayfa_yaz

METAR = ("METAR LTFJ 161250Z 06010KT 9999 SCT025 BKN040 18/12 Q1015 NOSIG "
         "RMK RWY06R 07012KT")
TAF = ("TAF LTFJ 161100Z 1612/1712 06012KT CAVOK "
       "TEMPO 1618/1622 3000 -SHRA BKN008 "
       "PROB30 TEMPO 1700/1706 0800 FG OVC002")
AN = datetime(2026, 9, 16, 12, 50, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def sayfa(tmp_path_factory):
    hedef = tmp_path_factory.mktemp("s") / "i.html"
    sayfa_yaz(
        [{"tip": "METAR", "icao": "LTFJ", "metin": METAR, "zaman": AN},
         {"tip": "TAF", "icao": "LTFJ", "metin": TAF,
          "zaman": AN.replace(hour=11)}],
        [], hedef, {}, "", "")
    return hedef.read_text(encoding="utf-8")


# ===================================================== renk ölçeği gitti

@pytest.mark.parametrize("kod", ["BLU", "WHT", "GRN", "YLO", "AMB"])
def test_renk_kodu_sayfada_HICBIR_YERDE_yok(sayfa, kod):
    """CSS YORUMLARI DA SAYILIR. İlk denemede kodlar koddan silinmişti
    ama kaldırılan özelliği ANLATAN yorumlar <style> bloğunun içinde
    tarayıcıya inmeye devam ediyordu."""
    assert kod not in sayfa


def test_RED_rozet_olarak_gecmiyor(sayfa):
    """'RED' masum kelimelerin içinde geçebilir; rozet/kod olarak
    geçmemeli."""
    assert ">RED<" not in sayfa and "RED ·" not in sayfa


def test_kartta_durum_rozeti_ve_kenar_rengi_yok(sayfa):
    assert 'class="rozet"' not in sayfa
    assert "kart-durum" not in sayfa and "--durum-renk" not in sayfa


def test_ozet_seritte_renk_cipi_yok(sayfa):
    assert "ozet-renk" not in sayfa


def test_bant_gostergesi_yok(sayfa):
    """Altı kutuluk BLU..RED şeridi kalktı - ölçeğin adı gidince o
    kutular efsanesiz kalıyordu."""
    assert "bant-kutu" not in sayfa and "bant-kod" not in sayfa


def test_ESIKLER_DURUYOR_sayi_vurgusu_korundu(tmp_path):
    """KALKAN ŞEY ÖLÇEĞİN ADI, ÖLÇEĞİN KENDİSİ DEĞİL. Düşük görüş/tavan
    hâlâ vurgulanıyor ve yanında kelimesi yazıyor - renk tek taşıyıcı
    değil."""
    kotu = "METAR LTFJ 161250Z 06010KT 0500 OVC001 18/17 Q1015"
    hedef = tmp_path / "i.html"
    sayfa_yaz([{"tip": "METAR", "icao": "LTFJ", "metin": kotu, "zaman": AN}],
              [], hedef, {}, "", "")
    s = hedef.read_text(encoding="utf-8")
    assert "hero-uyari" in s, "esik asiminda sayi vurgulanmiyor"
    assert "eşik altı" in s, "vurgu YALNIZCA renkle tasiniyor"


# ===================================================== VFR bandı

def test_tepede_VFR_bandi_var(sayfa):
    assert 'class="durum-blok"' in sayfa
    assert "ICAO Annex 2" in sayfa


def test_VFR_esikler_saglaninca_VFR_yazar(sayfa):
    """9999 m / BKN040 - iki eşik de sağlanıyor."""
    blok = sayfa.split('class="durum-blok"')[1].split("</div>")[0]
    assert ">VFR<" in blok and "vfr-nokta yesil" in blok


def test_VFR_saglanmayinca_IFR_yazar(tmp_path):
    kotu = "METAR LTFJ 161250Z 06010KT 0500 OVC001 18/17 Q1015"
    hedef = tmp_path / "i.html"
    sayfa_yaz([{"tip": "METAR", "icao": "LTFJ", "metin": kotu, "zaman": AN}],
              [], hedef, {}, "", "")
    blok = hedef.read_text(encoding="utf-8").split('class="durum-blok"')[1]
    blok = blok.split("</div>")[0]
    assert ">IFR<" in blok and "vfr-nokta kirmizi" in blok


def test_VFR_RENK_TEK_TASIYICI_degil(sayfa):
    """Nokta rengi tek başına kalırsa renk körü kullanıcı için gösterge
    yok demektir."""
    blok = sayfa.split('class="durum-blok"')[1].split("\n  </div>")[0]
    assert "VFR şartları sağlanıyor" in blok


def test_gorus_yoksa_VFR_UYDURULMUYOR(tmp_path):
    """Görüş bilgisi olmayan bir raporda 'VFR' demek uydurmaktır."""
    eksik = "METAR LTFJ 161250Z 06010KT 18/12 Q1015"
    hedef = tmp_path / "i.html"
    sayfa_yaz([{"tip": "METAR", "icao": "LTFJ", "metin": eksik, "zaman": AN}],
              [], hedef, {}, "", "")
    blok = hedef.read_text(encoding="utf-8").split('class="durum-blok"')[1]
    blok = blok.split("\n  </div>")[0]
    assert ">VFR<" not in blok and ">IFR<" not in blok
    assert "değerlendirilemiyor" in blok


# ===================================================== çözümleme

def test_metar_cozumlemesi_sayfada(sayfa):
    assert 'class="cozum"' in sayfa
    assert "Düzenli hava gözlem raporu" in sayfa
    assert "060° (kuzeydoğu) yönünden 10 kt" in sayfa
    assert "QNH 1015 hPa" in sayfa


def test_bulut_tabani_sayfada_FT_olarak(sayfa):
    assert "2500 ft" in sayfa and "4000 ft" in sayfa


def test_taf_degisim_gruplari_ETIKETLI(sayfa):
    assert "Geçici olarak" in sayfa
    assert "%30 olasılıkla, geçici olarak" in sayfa


def test_HAM_METIN_KAYBOLMADI_ama_katlandi(sayfa):
    """Çözümleyici yanılabilir; bağlayıcı olan ham metin. Sayfadan
    kalkmadı, yalnızca varsayılan görünüm olmaktan çıktı."""
    assert "ham-kat" in sayfa
    assert METAR.split(" RMK")[0] in sayfa
    assert "<summary>Ham metin</summary>" in sayfa


def test_RMK_satiri_DIK_diziliyor(sayfa):
    """Yatay düzende RMK'nın uzun kuyruğu dar jeton sütununa sıkışıp
    satır satır kırılıyordu."""
    assert "coz-dik" in sayfa and "jeton-genis" in sayfa


def test_cozulemeyen_grup_SAYFADA_KALIR(tmp_path):
    """Sessizce atılsaydı okuyan listeyi tam sanırdı."""
    tuhaf = "METAR LTFJ 161250Z 06010KT 9999 18/12 Q1015 ZZZZ9"
    hedef = tmp_path / "i.html"
    sayfa_yaz([{"tip": "METAR", "icao": "LTFJ", "metin": tuhaf, "zaman": AN}],
              [], hedef, {}, "", "")
    s = hedef.read_text(encoding="utf-8")
    assert "ZZZZ9" in s and "çözümlenemedi" in s


# ===================================================== marka tonu

def _oklab(hx):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    hx = hx.lstrip("#")
    r, g, b = (lin(int(hx[i:i + 2], 16)) for i in (0, 2, 4))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def _dE(a, b):
    return 100 * math.sqrt(sum((p - q) ** 2
                               for p, q in zip(_oklab(a), _oklab(b))))


def _token(sayfa, ad, koyu):
    """Bir CSS token'ının açık/koyu temadaki değeri."""
    blok = sayfa.split(':root[data-theme="dark"] {')[1] if koyu \
        else sayfa.split(":root {")[1]
    m = re.search(rf"{re.escape(ad)}:(#[0-9a-f]{{6}})", blok.split("}")[0])
    return m.group(1) if m else None


@pytest.mark.parametrize("koyu", [False, True])
def test_marka_tonu_ANLAMSAL_durum_renklerinden_ayirt_edilebilir(sayfa, koyu):
    """ESKİ TEST YANLIŞ KÜMEYE BAKIYORDU: marka tonunu RENK_KODU'nun
    (BLU/WHT/...) hex'leriyle karşılaştırıyordu. O kodlar sayfadan
    kalktı; asıl risk marka tonunun ANLAMSAL durum renkleriyle
    (--iyi/--dikkat/--uyari/--bilgi) karışmasıydı ve o hiç ölçülmüyordu.
    Ölçülünce görüldü ki eski mor ton koyu temada bilgi mavisine 10.6 -
    yani rehberin normal-görüş tabanının (15) ALTINDA."""
    marka = _token(sayfa, "--marka", koyu)
    assert marka, "marka tonu tanimli degil"
    for ad in ("--iyi", "--dikkat", "--uyari-metin", "--bilgi"):
        durum = _token(sayfa, ad, koyu)
        if not durum:
            continue
        d = _dE(marka, durum)
        assert d >= 15, f"{'koyu' if koyu else 'acik'}: marka ~ {ad} DeltaE {d:.1f}"


def test_marka_tonu_grafik_cizgisinde_kullaniliyor(sayfa):
    grafik = sayfa.split("\n  .grafik {")[1].split("}")[0]
    assert "var(--marka)" in grafik


# ===================================================== TAF katlanır

def test_TAF_cozumlemesi_VARSAYILAN_KATLI(sayfa):
    """24 saatlik tahmin beş-altı grup sürüyor; açık bırakıldığında
    sayfanın en uzun bloğu oluyor ve altındaki her şeyi ekrandan
    itiyordu."""
    assert '<details class="cozum cozum-kat">' in sayfa
    assert "<summary>Çözümleme · " in sayfa
    # details'te "open" YOK - kapalı başlıyor.
    kat = sayfa.split('<details class="cozum cozum-kat"')[1][:40]
    assert "open" not in kat


def test_TAF_katlisi_KAC_GRUP_oldugunu_soyluyor(sayfa):
    """Katlanmış şeyin ne olduğu görünmeli; boş bir 'Çözümleme +'
    başlığı 'aç da gör' demektir."""
    import re as _re
    m = _re.search(r"<summary>Çözümleme · (\d+) grup</summary>", sayfa)
    assert m and int(m.group(1)) >= 2, "grup sayisi basliga yazilmiyor"


def test_METAR_cozumlemesi_ACIK_kaliyor(sayfa):
    """METAR 'şu an ne var' - kısa ve bir bakışta okunur; onu
    katlamak asıl bilgiyi bir dokunuş arkasına saklardı."""
    assert '<div class="cozum">' in sayfa


# ===================================================== NOTAM kartı

def test_notam_karti_CUMLEYI_one_cikariyor(sayfa):
    """notac'ın sırası: kimlik satırı, sonra düz dil cümlesi kartın
    en büyük öğesi olarak. Eskiden cümle küçük gri yazıdaydı ve
    üstündeki çip duvarı onu bastırıyordu."""
    js = sayfa.split("function notamKarti(n)")[1].split("function kisaZaman")[0]
    assert '"notam-cumle"' in js
    # Cumle, kimlik satirindan SONRA geliyor.
    assert js.index('"notam-ust"') < js.index('"notam-cumle"')
    # Etiketler cumleden SONRA.
    assert js.index('"notam-cumle"') < js.index('"notam-etiketler"')


def test_notam_ozet_uyarisi_KARTTA_TEKRARLANMIYOR(sayfa):
    """28 kartlık bir listede kart başına bir uyarı = 28 tekrar.
    Uyarı bölüm başında, bir kez."""
    assert sayfa.count("NOTAC otomatik özeti") == 0
    assert sayfa.count('class="notam-not"') == 1
    assert "bağlayıcı olan, her kartın altındaki" in sayfa


def test_notam_not_SARI_UYARI_KUTUSU_bicimini_almiyor(sayfa):
    """AD ÇAKIŞMASI: ilk yazımda bu dipnota '.notam-uyari' demiştim -
    o ad sayfada dört yerde kullanılan sarı bilgi kutusunun kuralı ve
    sessiz dipnotum ekranda sarı çerçeveli bir uyarı olarak çiziliyordu.
    Tarayıcıda yakalandı, testte kilitleniyor."""
    assert '.notam-not {' in sayfa
    not_kural = sayfa.split("\n  .notam-not {")[1].split("}")[0]
    assert "var(--cizgi)" in not_kural
    assert "dikkat" not in not_kural and "uyari" not in not_kural


def test_notam_kunyesinde_ISO_damga_YOK(sayfa):
    """Geçerlilik tarihleri ISO damga olarak basılıyordu
    ('2026-08-28T07:11:00Z') - sayfadaki hiçbir başka zaman o biçimde
    değil ve künye satırını tek başına iki katına çıkarıyordu."""
    js = sayfa.split("function notamKarti(n)")[1].split("function kisaZaman")[0]
    assert "kisaZaman(n.effective_start)" in js
    assert "esc(n.effective_start" not in js


def test_notam_Q_kodu_CIP_degil_KUNYE_satirinda(sayfa):
    """Q kodu bir kimlik alanı, bir rozet değil - üst satırdaki çip
    duvarını büyütüyordu."""
    js = sayfa.split("function notamKarti(n)")[1].split("function kisaZaman")[0]
    assert "ltfjNotamQEtiketi" not in js
    assert '"Q " + esc(n.q_code)' in js


def test_notam_cumle_YOKSA_ham_govdeye_dusuyor(sayfa):
    """reading_short gelmezse kart boş kalmamalı - boş kart, NOTAM'ı
    görünmez kılmak demek."""
    js = sayfa.split("function notamKarti(n)")[1].split("function kisaZaman")[0]
    assert "n.reading_short || n.text" in js
