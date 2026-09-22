"""Log-olabilirlik beceri skoru (LSS) + saate kosullu iklim referansi.

NEDEN EKLENDI: Jewson (2004) / Benedetti (2009), olay olasiligi cok
kucukken Brier Score'un cozunurlugunu kaybettigini gosterdi. Bu projenin
taban orani %0.76; lead-time tablosunda BSS 2 saatte 1 saatten DUSUK
cikmisti, AP monoton artarken - tam o dejenere bolge.

En kritik test: saate KOSULLU iklim, duz taban orandan DAHA ZOR bir
referans olmali. Modelin kendi degiskenleri arasinda `saat` de var;
duz orana gore olculen beceri "gunluk dongusu ogrenildi"yi atmosferik
beceri gibi gosterebilir.
"""
import math

from sis_modeli import degerlendir as d


def _iklim(gercekler):
    t = sum(1 for y in gercekler if y) / len(gercekler)
    return [t] * len(gercekler)


# ------------------------------------------------------------- log_skill
def test_mukemmel_tahmin_bir_verir():
    g = [True, False, False, True, False]
    assert abs(d.log_skill([1, 0, 0, 1, 0], g, _iklim(g)) - 1.0) < 1e-6


def test_referansin_kendisi_sifir_verir():
    g = [True, False, False, True, False]
    ik = _iklim(g)
    assert abs(d.log_skill(ik, g, ik)) < 1e-12


def test_referanstan_kotu_tahmin_negatif():
    g = [True, False, False, True, False]
    assert d.log_skill([0, 1, 1, 0, 1], g, _iklim(g)) < 0


def test_brier_skill_ile_ayni_isaret_sozlesmesi():
    """Iki beceri skoru ayni yonde okunmali - biri 'yuksek iyi' otekisi
    'dusuk iyi' olsaydi tablo yanlis okunurdu."""
    g = [True, False, False, True, False, False]
    ik = _iklim(g)
    iyi = [0.9 if y else 0.1 for y in g]
    assert d.log_skill(iyi, g, ik) > 0
    assert d.brier_skill(iyi, g, ik) > 0


def test_referans_dejenereyse_cokmuyor():
    """Hic pozitif yoksa referans log-kaybi ~0 olur; 0'a bolme olmamali."""
    g = [False] * 5
    assert d.log_skill([0.0] * 5, g, [0.0] * 5) == 0.0


def test_emin_ve_yanlis_tahmin_sonsuz_vermiyor():
    """eps kirpmasi: p=0 iken gercek pozitifse log(0) cokerdi."""
    s = d.log_skill([0.0, 0.0], [True, False], [0.5, 0.5])
    assert math.isfinite(s)


# ------------------------------------------------- kosullu iklim referansi
def test_kosullu_iklim_saat_yapisini_yakaliyor():
    """Gece pozitif, gunduz negatif: kosullu referans bu ayrimi bilmeli."""
    saatler = [3] * 100 + [15] * 100
    gercekler = [i < 20 for i in range(100)] + [False] * 100
    p = d.kosullu_iklim(saatler, gercekler)
    gece = p[0]
    gunduz = p[150]
    assert gece > gunduz


def test_kosullu_iklim_duz_orandan_DAHA_ZOR_referans():
    """EN KRITIK TEST: gunluk dongusu varken saate kosullu referans, duz
    taban orandan daha iyi (daha dusuk log-kayip) olmali - yoksa duz
    orana gore olculen LSS'in bir kismi sadece 'saat ogrenildi'dir."""
    saatler = [3] * 100 + [15] * 100
    gercekler = [i < 20 for i in range(100)] + [False] * 100
    duz = _iklim(gercekler)
    kosullu = d.kosullu_iklim(saatler, gercekler)
    assert d.log_loss(kosullu, gercekler) < d.log_loss(duz, gercekler)


def test_saat_yapisi_yoksa_iki_referans_birbirine_yakin():
    """Gunluk dongu YOKSA kosullu referans ek bilgi tasimaz.

    DIKKAT (bu test bir kez yanlis yazildi): "yapisiz" ornegi
    saat = i % 24, pozitif = i % 20 ile kurmak YAPI URETIR - 20 ile 24'un
    OBEB'i 4 oldugu icin pozitifler yalnizca 4'un katı saatlere duser.
    Burada her saate ESIT oranda pozitif konuyor."""
    saatler, gercekler = [], []
    for saat in range(24):
        saatler += [saat] * 40
        gercekler += [True] * 2 + [False] * 38      # her saatte tam %5
    duz = _iklim(gercekler)
    kosullu = d.kosullu_iklim(saatler, gercekler)
    assert abs(d.log_loss(kosullu, gercekler) - d.log_loss(duz, gercekler)) < 1e-9


def test_bos_kovada_sifir_olasilik_uretmiyor():
    """Yumusatma olmadan tek pozitifi olmayan bir saat kovasi p=0 verir;
    o saatte bir olay olursa referans SONSUZ ceza alir ve LSS anlamsizlasir."""
    saatler = [3] * 50 + [15] * 50
    gercekler = [False] * 100
    p = d.kosullu_iklim(saatler, gercekler)
    assert all(0.0 <= x < 1.0 for x in p)
    # Genel oran 0 oldugu icin hepsi 0 olabilir ama NEGATIF/NaN olmamali.
    assert all(math.isfinite(x) for x in p)


def test_az_ornekli_kova_genel_orana_cekiliyor():
    """3 gozlemde 3 pozitif goren bir kova p=1.0 demesin."""
    saatler = [3] * 3 + [15] * 997
    gercekler = [True] * 3 + [False] * 997
    p = d.kosullu_iklim(saatler, gercekler)
    assert p[0] < 0.5, "az ornekli kova asiri guvenli"


def test_yumusatma_sabiti_tek_yerde():
    assert d.KOVA_YUMUSATMA > 0


# ============================================== esli (paired) blok bootstrap
# NEDEN ESLI: iki MARJINAL guven araligi ORTUSUYOR diye "fark yok"
# denemez - yaygin bir okuma hatasidir. Ufuklar ayni gunlerin havasini
# paylastigi icin ayni gun ornegi uzerinde FARKI olcmek cok daha guclu.
def _seri(gun_sayisi=40, satir=10, kayma=0.0, tohum=0):
    import random as _r
    r = _r.Random(tohum)
    gunler, tahminler, gercekler = [], [], []
    for g in range(gun_sayisi):
        for _ in range(satir):
            y = r.random() < 0.1
            gunler.append(f"gun{g}")
            gercekler.append(y)
            # kayma buyudukce tahmin gercege daha cok yaklasir
            temel = 0.7 if y else 0.3
            tahminler.append(min(max(temel + kayma * (1 if y else -1), 0.01), 0.99))
    return gunler, tahminler, gercekler


def test_ayni_seri_kendisiyle_kiyaslaninca_fark_tam_sifir():
    """EN KRITIK SAGLAMA: esleme bozuksa (her seri ayri gun ornegi
    gorurse) ayni seri kendisiyle kiyaslandiginda bile sifir olmayan
    bir fark cikar."""
    s = _seri()
    _a, f = d.esli_blok_guven_araligi({"x": s, "y": s}, d.brier, tekrar=40)
    alt, ust, orta, _oran = f[("x", "y")]
    assert alt == ust == orta == 0.0


def test_ayni_seri_araliklari_da_ozdes():
    s = _seri()
    a, _f = d.esli_blok_guven_araligi({"x": s, "y": s}, d.brier, tekrar=40)
    assert a["x"] == a["y"]


def test_acikca_daha_iyi_seri_ayirt_ediliyor():
    g, t_kotu, y = _seri(kayma=0.0)
    _g2, t_iyi, _y2 = _seri(kayma=0.25)
    a, f = d.esli_blok_guven_araligi(
        {"iyi": (g, t_iyi, y), "kotu": (g, t_kotu, y)}, d.brier, tekrar=80)
    alt, ust, _orta, oran = f[("iyi", "kotu")]
    assert ust < 0, "Brier'de dusuk iyidir; iyi - kotu NEGATIF olmali"
    assert oran < 0.05


def test_gun_bloklari_bozulmuyor():
    """Satir bazinda yeniden ornekleme araligi sahte sekilde daraltirdi.
    Blok bozulsaydi ayni gunun satirlari bagimsiz sayilirdi."""
    # DIKKAT (bu test de bir kez yanlis kuruldu): 0.9/True ve 0.1/False
    # bloklari AYNI Brier'i (0.01) verir, karisim ne olursa olsun sonuc
    # sabit cikar ve test blok yapisini sinamaz. Bloklarin metrigi
    # FARKLI olmali.
    gunler = ["a"] * 50 + ["b"] * 50
    tahminler = [0.9] * 100
    gercekler = [True] * 50 + [False] * 50      # a: 0.01, b: 0.81
    a, _f = d.esli_blok_guven_araligi(
        {"x": (gunler, tahminler, gercekler)}, d.brier, tekrar=60)
    alt, ust = a["x"]
    # Yalnizca 2 blok var -> ornek aa/ab/ba/bb; Brier 0.01, 0.41 veya
    # 0.81 olabilir, yani aralik GENIS. Blok bozulup satir bazinda
    # orneklenseydi hepsi ~0.41'e yakinsardi.
    assert ust - alt > 0.1


def test_ortak_olmayan_gunler_kesisime_indiriliyor():
    g1 = ["a"] * 10 + ["b"] * 10
    g2 = ["b"] * 10 + ["c"] * 10
    t = [0.5] * 20
    y = [i % 5 == 0 for i in range(20)]
    a, f = d.esli_blok_guven_araligi(
        {"x": (g1, t, y), "y": (g2, t, y)}, d.brier, tekrar=20)
    assert ("x", "y") in f          # cokmeden kesisim ("b") ile calismali


def test_bos_girdi_cokmuyor():
    assert d.esli_blok_guven_araligi({}, d.brier, tekrar=5) == ({}, {})


def test_tohum_ayni_sonucu_veriyor():
    """Rapor edilen sayilar tekrar uretilebilir olmali."""
    s = _seri()
    kur = lambda: d.esli_blok_guven_araligi({"x": s}, d.brier,
                                            tekrar=30, tohum=7)
    assert kur() == kur()
