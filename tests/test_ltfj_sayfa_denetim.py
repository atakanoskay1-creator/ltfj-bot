"""Arayüz denetiminde bulunan 12 maddenin regresyon testleri.

Hepsi tarayıcıda ÖLÇÜLDÜ; buradaki testler tarayıcı istemez çünkü her
birinin kökü ölçülebilir bir yapı ya da bir CSS kuralı.

Denetim raporunun madde numaraları (B1…B14 / Ö1…Ö12) yorumlarda geçiyor.
"""
import re
from datetime import datetime, timedelta, timezone

import pytest

import ltfj_ayarlar
import ltfj_pist as pist
import ltfj_sayfa as s

SIMDI = datetime.now(timezone.utc)


def _sayfa(tmp_path, metin="LTFJ 231920Z VRB01KT 9999 FEW030 13/10 Q1020 NOSIG",
           gecmis=None) -> str:
    hedef = tmp_path / "i.html"
    s.sayfa_yaz([{"tip": "METAR", "icao": "LTFJ", "zaman": SIMDI, "metin": metin}],
                gecmis or [], hedef)
    return hedef.read_text(encoding="utf-8")


def _govde(html_metin: str) -> str:
    """Stil bloğu DIŞINDAKİ gövde, yorumlar çıkarılmış.

    Bu dosyadaki dört test ilk sürümde stylesheet'teki KENDİ
    kurallarıma takıldı: ".hero-uyari" bir CSS seçicisi olarak her
    sayfada var, yani "yok" iddiası hiçbir zaman doğrulanamazdı."""
    return re.sub(r"<!--.*?-->", "", html_metin.split("</style>")[1], flags=re.S)


def _kural(html_metin: str, secici: str) -> str:
    """Bir CSS kuralının gövdesi. Çapa TAM KURAL: "\\n  .x {" biçiminde
    aranıyor çünkü ".x {" alt seçicilere de (".js .x", ".y .x") uyuyor
    ve bu projede testler defalarca yanlış kuralın gövdesini okudu."""
    return html_metin.split(f"\n  {secici} {{")[1].split("}")[0]


# ============================================== Ö7 / B1: VFR × Yenile
def test_VFR_sekmesi_dugmelerin_OLUGUNU_yiyor_mu(tmp_path):
    """GERÇEK KUSUR, tarayıcıda ölçüldü: VFR sekmesi position:fixed,
    sağ kenarda ve 29px geniş. 480px altında başlıktaki düğmeler ikinci
    satıra inip tam sekmenin dikey bandına (96-144px) denk geliyordu:

        Yenile : sol=292 sağ=374  üst=101 alt=139
        VFR    : sol=361 sağ=390  üst=96  alt=144
        → 13px yatay, 38px dikey örtüşme

    Yani düğmenin sağ 13px'ine basan parmak Yenile'yi değil VFR
    panelini açıyordu. Kötü havada, VFR göstergesi kırmızıyken.

    elementFromPoint MERKEZ testi bunu YAKALAMIYOR (merkez temiz) -
    kutu kesişimiyle bakmak gerekti."""
    html_metin = _sayfa(tmp_path)
    dar = html_metin.split("@media (max-width:480px)")[1].split("\n  }")[0]
    assert ".header-butonlar" in dar
    m = re.search(r"\.header-butonlar \{[^}]*padding-right:(\d+)px", dar, re.S)
    assert m, "dar ekranda dugmeler icin oluk ayrilmamis"
    sekme = _kural(html_metin, ".vfr-sekme")
    genislik = int(re.search(r"padding:\d+px (\d+)px", sekme).group(1))
    # Oluk, sekmenin kapladigi seritten GENIS olmali.
    assert int(m.group(1)) > genislik * 2, (m.group(1), genislik)


def test_VFR_sekmesi_kontrasti_AA(tmp_path):
    """2.28:1 idi - sayfadaki EN DÜŞÜK kontrast, hem de emniyetle en
    ilgili göstergede."""
    html_metin = _sayfa(tmp_path)

    def parlaklik(hx):
        hx = hx.lstrip("#")
        r, g, b = (int(hx[i:i + 2], 16) for i in (0, 2, 4))
        f = lambda v: (v / 255) / 12.92 if v / 255 <= 0.03928 else \
            (((v / 255) + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

    for sinif in ("vfr-yesil", "vfr-kirmizi", "vfr-bilinmiyor"):
        renk = re.search(rf"\.vfr-sekme\.{sinif} \{{ background:(#[0-9a-f]{{6}})",
                         html_metin).group(1)
        oran = 1.05 / (parlaklik(renk) + 0.05)   # beyaz yazi uzerine
        assert oran >= 4.5, f"{sinif} {renk} -> {oran:.2f}:1"


# ============================================== Ö8 / B6: gece parlaklığı
def test_FAB_koyu_temada_SAYFANIN_EN_PARLAK_nesnesi_DEGIL(tmp_path):
    """Ölçüldü: FAB bağıl parlaklık 0.853, hero 0.023 — 37 kat. Gece
    karartılmış bir kulede ekranın en parlak nesnesi "not ekle"
    düğmesiydi; karanlık adaptasyonunu bozan şey bu."""
    html_metin = _sayfa(tmp_path)
    fab = _kural(html_metin, ".atc-fab")
    assert "var(--fab-zemin)" in fab, "FAB hala tek sabit yuzey kullaniyor"
    # Koyu tema bloklarinin IKISINDE DE tanimli olmali (sistem tercihi
    # ve elle secim ayri ayri).
    assert html_metin.count("--fab-zemin:#1e2a44") == 2, "koyu tema eksik"
    # Dokunma hedefi KUCULMEDI.
    assert "width:56px; height:56px" in fab


# ============================================== Ö4+Ö6 / B7: başlık, etiket
def test_istasyon_kodu_hero_sayilariyla_AYNI_boyda_DEGIL(tmp_path):
    html_metin = _sayfa(tmp_path)
    h1 = _kural(html_metin, "h1")
    hero = _kural(html_metin, ".hero-deger")
    assert "var(--f4)" in h1, h1
    assert "var(--f6)" in hero, hero


def test_hero_etiketleri_SOLUK_degil(tmp_path):
    """9.9px + --sessiz = açık temada 2.56:1. Bunlar sayfadaki en büyük
    dört sayının NE OLDUĞUNU söyleyen etiketler."""
    etiket = _kural(_sayfa(tmp_path), ".hero-etiket")
    assert "var(--soluk)" in etiket and "var(--sessiz)" not in etiket


# ============================================== Ö5 / B8: tipografi ölçeği
def test_tipografi_OLCEGE_oturuyor(tmp_path):
    """Ölçüldü: tek telefon ekranında 17 farklı punto, 11'i 9.9-14.1px
    arasına sıkışmış; 16.8-24px arası tamamen boştu."""
    html_metin = _sayfa(tmp_path)
    stil = html_metin.split("<style>")[1].split("</style>")[0]
    stil = re.sub(r"/\*.*?\*/", "", stil, flags=re.S)   # kendi yorumlarim
    olcek_disi = re.findall(r"font-size:([0-9.]+)(?:rem|px)", stil)
    assert not olcek_disi, f"olcek disi punto: {sorted(set(olcek_disi))}"
    for token in ("--f1", "--f2", "--f3", "--f4", "--f5", "--f6"):
        assert f"{token}:" in html_metin, token


def test_olcekte_ORTA_ADIMLAR_var(tmp_path):
    """Asıl sorun üstteki boşluktu: hero ile gövde arasında hiçbir adım
    yoktu, yani ikincil bir şeyi vurgulamak için araç yoktu."""
    html_metin = _sayfa(tmp_path)
    kok = html_metin.split(":root {")[1].split("}")[0]
    deger = {t: float(re.search(rf"--{t}:([0-9.]+)rem", kok).group(1)) * 16
             for t in ("f1", "f2", "f3", "f4", "f5", "f6")}
    adimlar = [deger[f"f{i}"] for i in range(1, 7)]
    assert adimlar == sorted(adimlar), adimlar
    # Hicbir komsu adim arasinda 2 kattan buyuk sicrama olmasin.
    for a, b in zip(adimlar, adimlar[1:]):
        assert b / a < 2.0, (a, b)


# ============================================== Ö1 / B4: tek "ŞU AN"
def test_dort_olcu_TEK_KAYNAKTAN_bicimleniyor():
    """Hero ile özet şerit aynı dört ölçüyü AYRI AYRI biçimlendiriyordu
    ve aynı ekranda birbirinden farklı konuşuyordu:
        görüş "10+ km" / "9999 m" · tavan "tavan yok" / "— ft"
    Hangisinin doğru olduğu okuyucuya bırakılmıştı."""
    cozum = {"gorus": 9999, "tavan": None, "ruzgar_yon": None,
             "ruzgar_hiz": 1, "sicaklik": 13, "cig_noktasi": 10}
    assert s._olcu(cozum, "gorus") == ("10+", "km")
    assert s._olcu(cozum, "tavan") == ("bildirilmedi", "")
    serit = s._ozet_serit_html(cozum, None)
    assert "10+ km" in serit and "9999" not in serit


def test_hero_SAYFANIN_TEPESINDE_kartin_icinde_DEGIL(tmp_path):
    """Ölçüldü: hero 390px telefonda y=609'da başlıyordu - ilk ekranın
    %72'si aşağıda. Üstünde başlık, düğmeler, özet şerit, sekme çubuğu
    ve kartın kendi başlığı/yapay zekâ özeti vardı."""
    html_metin = _sayfa(tmp_path)
    assert '<div class="su-an"' in html_metin
    assert html_metin.index('<div class="hero">') < html_metin.index('id="panel-durum"')
    # Kartin icinde IKINCI bir hero olmamali.
    assert html_metin.count('<div class="hero">') == 1


def test_serit_hero_gorunurken_GIZLI(tmp_path):
    """İkisi aynı dört ölçüyü gösteriyor; aynı anda ikisini birden
    çizmek aynı sayıyı 374 piksel arayla iki kez yazmak demekti."""
    html_metin = _sayfa(tmp_path)
    assert ".js .ozet-serit { display:none; }" in html_metin
    assert "serit-acik" in html_metin
    assert "IntersectionObserver" in html_metin
    # JS YOKSA serit gorunur kalmali - bilgi kaybi olmasin. Capa TAM
    # KURAL: ".ozet-serit { display:none" ifadesi ".js .ozet-serit"
    # kuralina da uyuyor ve bu guard'in ilk surumu ona takiliyordu.
    assert "\n  .ozet-serit { display:none" not in html_metin


# ============================================== Ö2+Ö3+Ö10 / B2,B3,B5
def test_esik_asiminda_SAYININ_KENDISI_degisiyor(tmp_path):
    """Ölçüldü: RED durumunda hero'nun dört sayısı BLU durumuyla birebir
    aynı çiziliyordu - 28px, aynı siyah, aynı ağırlık. "300 m" ile
    "9999 m" görsel olarak ayırt edilemiyordu; sinyalin tamamı sayıların
    ETRAFINDAKİ rozette ve kutudaydı. Göz önce rakama gider."""
    iyi = _sayfa(tmp_path, "LTFJ 231920Z VRB01KT 9999 FEW030 13/10 Q1020")
    kotu = _sayfa(tmp_path, "LTFJ 231920Z 09012G22KT 0300 FG VV001 12/12 Q1008")
    assert "hero-uyari" not in _govde(iyi)
    assert "hero-uyari" in _govde(kotu)
    # RENK TEK TASIYICI DEGIL: metin isareti de var.
    assert "eşik altı" in _govde(kotu)


def test_esikler_KOPYALANMIYOR_pist_tablosundan_geliyor():
    """Sayfa kendi eşiğini tanımlamamalı; Telegram'ın ve rozetin
    kullandığı tablonun aynı satırlarına bakmalı."""
    red = {"gorus": 300, "tavan": 100}
    ylo = {"gorus": 1600, "tavan": 300}
    blu = {"gorus": 9999, "tavan": 3000}
    assert s._olcu_bandi(red, "gorus") == "uyari"
    assert s._olcu_bandi(ylo, "gorus") == "dikkat"
    assert s._olcu_bandi(blu, "gorus") == ""
    # Tablo DEGISIRSE bu test de degisir - kopya olmadiginin kaniti:
    en_dusuk_gorus = pist.RENK_DURUMLARI[-1][2]
    assert s._olcu_bandi({"gorus": en_dusuk_gorus - 1}, "gorus") == "uyari"
    assert s._olcu_bandi({"gorus": en_dusuk_gorus}, "gorus") == "dikkat"


def test_hero_ruzgarinda_HAMLE_var():
    """METAR "09012G22KT" iken sayfadaki EN BÜYÜK yazı "090°/12 kt"
    diyordu. 12 kt ile 22 kt arasındaki fark bir pist tercihini
    değiştirebilir."""
    cozum = {"ruzgar_yon": 90, "ruzgar_hiz": 12, "ruzgar_hamle": 22}
    assert s._olcu(cozum, "_ruzgar") == ("090°/12G22", "kt")


def test_tavan_yoksa_TIRE_degil_kelime(tmp_path):
    """24px'lik bir tire kalın yatay bir çubuk olarak çiziliyor ve
    "üstü çizilmiş değer" gibi okunuyordu."""
    html_metin = _sayfa(tmp_path, "LTFJ 231920Z 06005KT 9999 15/10 Q1019")
    hero = _govde(html_metin).split('<div class="hero">')[1]
    assert "bildirilmedi" in hero
    assert "hero-deger-metin" in hero, "metin degeri sayi puntosunda kalmis"


# ============================================== Ö11 / B12: trend yeri
def test_gecmis_egilim_GUNCEL_RAPORUN_ALTINDA(tmp_path):
    # GECMIS SART: trend bolumu ancak olcum gecmisi varken ciziliyor.
    gecmis = [{"zaman": (SIMDI - timedelta(minutes=30 * i)).isoformat(),
               "tavan": 2500, "ruzgar_hiz": 5, "qnh": 1015,
               "sicaklik": 14.0, "cig_noktasi": 11.0} for i in range(8, -1, -1)]
    html_metin = _sayfa(tmp_path, gecmis=gecmis)
    panel = html_metin.split('id="panel-durum"')[1].split('class="sekme-panel"')[0]
    assert panel.index("<summary>") > panel.index('class="kart kart-durum"')


# ============================================== Ö12 / B10: beşinci durum
def test_BESINCI_tazelik_durumu_var(tmp_path):
    """Ölçüm anındaki gerçek durum: METAR 49 dk önce, rozet CANLI.
    Kadans 30 dk + ~5 dk gecikme, yani o aralık "bir gözlem kaçtı"."""
    html_metin = _sayfa(tmp_path)
    for metin in ("CANLI", "1 GÖZLEM KAÇTI", "GECİKMELİ",
                  "VERİ KESİNTİSİ", "VERİ YOK"):
        assert f'"{metin}"' in html_metin, metin


def test_beklenen_esik_KADANSTAN_turuyor():
    """30 dk kadans + ~5 dk MGM gecikmesi = ~35 dk."""
    assert ltfj_ayarlar.GOZLEM_BEKLENEN_DK == 35
    assert ltfj_ayarlar.GOZLEM_BEKLENEN_DK < ltfj_ayarlar.GOZLEM_TAZE_DK
    assert ltfj_ayarlar.GOZLEM_TAZE_DK < ltfj_ayarlar.SESSIZLIK_SAAT * 60


def test_esikler_JS_e_AYARLARDAN_geciyor(tmp_path):
    html_metin = _sayfa(tmp_path)
    assert (f"var BEKLENEN_DK = {ltfj_ayarlar.GOZLEM_BEKLENEN_DK};"
            in html_metin)
    assert f"var TAZE_DK = {ltfj_ayarlar.GOZLEM_TAZE_DK};" in html_metin


def test_CANLI_dali_BEKLENEN_esigini_kullaniyor(tmp_path):
    """KAPSAMA BOŞLUĞU KAPATILDI — mutasyonla bulundu.

    İlk sürüm yalnızca beş metnin sayfada GEÇTİĞİNİ doğruluyordu. O
    guard'la, CANLI dalını `BEKLENEN_DK` yerine `TAZE_DK`'ya geri
    çevirmek testi KIRMIYORDU: "1 GÖZLEM KAÇTI" metni sayfada kalıyor
    ama dal ULAŞILMAZ hale geliyor, yani 49 dakikalık gözleme yine
    CANLI denirdi. Test yeşilken kusur geri gelirdi.

    Artık dalların hangi eşiğe baktığı doğrulanıyor."""
    html_metin = _sayfa(tmp_path)
    js = html_metin.split("function durumTazele()")[1].split("}")[0]
    dallar = re.findall(r"dk <= (\w+)\).*?metin = \"([^\"]+)\"",
                        html_metin.split("var dk = yasDk")[1][:900], re.S)
    assert dallar[:2] == [("BEKLENEN_DK", "CANLI"),
                          ("TAZE_DK", "1 GÖZLEM KAÇTI")], dallar
    # Ikinci dal ULASILABILIR olmali: esikler farkli olmak zorunda.
    assert ltfj_ayarlar.GOZLEM_BEKLENEN_DK < ltfj_ayarlar.GOZLEM_TAZE_DK


# ============================================== Ö9 / B9: zaman dili
def test_TEK_zaman_kurali(tmp_path):
    """Ölçüldü: sayfada beş ayrı biçim vardı ve dördü aynı ilk ekranda
    görülüyordu. Havacılıkta zaman UTC konuşulur."""
    html_metin = _sayfa(tmp_path)
    govde = re.sub(r"<!--.*?-->", "", html_metin.split("</style>")[1], flags=re.S)
    duz = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", govde))
    assert re.search(r"\d{2}:\d{2}Z \(\d{2}:\d{2} yerel\)", duz), duz[:300]
    # Eski bicimler GITTI:
    assert not re.search(r"\b\d{2}:\d{2} yerel(?!\))", duz)
    assert not re.search(r"\b\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}\b", duz)


def test_HAM_METAR_damgasina_dokunulmadi(tmp_path):
    """231920Z rapor metninin KENDISI - bizim biçimimiz değil."""
    html_metin = _sayfa(tmp_path)
    assert "231920Z" in html_metin
