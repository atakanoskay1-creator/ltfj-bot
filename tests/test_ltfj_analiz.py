"""ltfj_analiz.py testleri: metar_coz kategorileri, boundary'ler,
matematiksel ozellikler (property) ve fark_bul."""
import math

import pytest

import ornekler as o
from ltfj_analiz import fark_bul, metar_coz, uyarilar, yan_ruzgar


# --------------------------------------------------------- kategori testleri
def test_normal_metar():
    d = metar_coz(o.NORMAL)
    assert d["ruzgar_yon"] == 60 and d["ruzgar_hiz"] == 10
    assert d["gorus"] == 9999
    assert d["tavan"] == 4000  # BKN040 -> min(SCT025 sayilmaz, BKN040)
    assert d["nosig"] is True


def test_speci():
    d = metar_coz(o.SPECI)
    assert d["ruzgar_hiz"] == 15 and d["ruzgar_hamle"] == 25
    assert d["hava"] == ["-SHRA"]
    assert d["tavan"] == 1200  # BKN012 < BKN025CB


def test_cavok():
    d = metar_coz(o.CAVOK)
    assert d["cavok"] is True
    assert d["gorus"] == 10000


def test_sakin_ruzgar():
    d = metar_coz(o.SAKIN_RUZGAR)
    assert d["ruzgar_yon"] == 0 and d["ruzgar_hiz"] == 0


def test_degisken_ruzgar_vrb():
    d = metar_coz(o.DEGISKEN_RUZGAR)
    assert d["ruzgar_yon"] is None  # VRB -> yon bilinmiyor
    assert d["ruzgar_hiz"] == 3


def test_degisken_yon_grubu():
    d = metar_coz(o.DEGISKEN_YON_GRUBU)
    assert d["degisken"] == (20, 90)
    assert d["ruzgar_yon"] == 50  # taban ruzgar ayri, degisken ek bilgi


def test_hamle():
    d = metar_coz(o.HAMLE)
    assert d["ruzgar_hiz"] == 18 and d["ruzgar_hamle"] == 30


@pytest.mark.parametrize("ornek,beklenen_hava", [
    (o.YAGMUR, ["-RA"]),
    (o.SIDDETLI_YAGMUR, ["+RA"]),
    (o.FIRTINA, ["+TSRA"]),
    (o.DONAN_YAGIS, ["-FZRA"]),
    (o.SIS, ["FG"]),
    (o.PUS, ["BR"]),
    (o.KAR, ["-SN"]),
])
def test_hava_kategorileri(ornek, beklenen_hava):
    assert metar_coz(ornek)["hava"] == beklenen_hava


def test_dusuk_gorus():
    d = metar_coz(o.DUSUK_GORUS)
    assert d["gorus"] == 600


def test_gorus_0000_sinir():
    d = metar_coz(o.GORUS_0000)
    assert d["gorus"] == 0


def test_becmg_ana_govdeden_cikarilir():
    d = metar_coz(o.BECMG_GRUBU)
    # BECMG sonrasindaki 09015KT ana govdeye karismamali; ana govdedeki
    # ruzgar hala ilk (06010KT) grubu olmali.
    assert d["ruzgar_hiz"] == 10


def test_tempo_ana_govdeden_cikarilir():
    d = metar_coz(o.TEMPO_GRUBU)
    # TEMPO icindeki SHRA/BKN012CB "su an" degil - d["hava"] bos kalmali.
    # Ana govdede sadece SCT025 var (SCT tavan sayilmaz) -> tavan None.
    assert d["hava"] == []
    assert d["tavan"] is None


def test_nosig():
    assert metar_coz(o.NOSIG_ORNEGI)["nosig"] is True
    assert metar_coz(o.SIDDETLI_YAGMUR)["nosig"] is False


def test_rmk_govdeden_disari_atilir():
    d = metar_coz(o.PIST_RUZGARI_RMK)
    # RMK'daki RWY24R/RWY06R/RWY24L token'lari ana govde alanlarina sizmamali
    assert d["ruzgar_yon"] == 40 and d["ruzgar_hiz"] == 7


# ----------------------------------------------------------- edge case'ler
def test_eksik_ruzgar_grubu_crash_etmez():
    d = metar_coz(o.EKSIK_VERI)
    assert d["ruzgar_yon"] is None and d["ruzgar_hiz"] is None
    assert d["gorus"] == 9999  # digeri normal parse edilmis


def test_bozuk_metar_crash_etmez_hersey_none():
    d = metar_coz(o.BOZUK_METAR)
    assert d["ruzgar_hiz"] is None
    assert d["gorus"] is None
    assert d["hava"] == []


def test_beklenmeyen_token_sessizce_yutulur():
    d = metar_coz(o.BEKLENMEYEN_TOKEN)
    # ZZZFOO ne hataya ne de hava/baska bir alana girer, digerleri saglam kalir
    assert d["ruzgar_hiz"] == 10
    assert d["nosig"] is True
    assert d["hava"] == []


def test_tavan_yuksekligi_bilinmeyen_katman():
    """EDGE CASE (rapor D bolumu): BKN/// -> tavan None olur, 'tavan yok'
    (SKC/CLR) ile ayni sonucu uretir. Bu testin amaci mevcut davranisi
    belgelemek - davranisi degistirmiyoruz, sadece kayit altina aliyoruz."""
    d = metar_coz(o.TAVAN_YUKSEKLIGI_BILINMIYOR)
    assert d["bulutlar"] == [{"ortu": "BKN", "ft": None, "tur": None}]
    assert d["tavan"] is None


def test_qnh_a_formati_dogru_donusturulur():
    d = metar_coz(o.QNH_A_FORMATI)
    assert d["qnh"] == 1013  # A2992 inHg -> ~1013 hPa


# ------------------------------------------------------------- boundary'ler
@pytest.mark.parametrize("gorus,beklenen_uyari_var", [
    (1501, False), (1500, False), (1499, True),   # gorus_dusuk = 1500, siniri "<"
    (801, True), (800, True), (799, True),         # gorus_cok_dusuk = 800 (ikisi de tetikler)
])
def test_gorus_esik_siniri(gorus, beklenen_uyari_var):
    d = metar_coz(o.NORMAL)
    d["gorus"] = gorus
    u = uyarilar(d)
    var = any("örüş" in x for x in u)
    assert var == beklenen_uyari_var


@pytest.mark.parametrize("hiz,hamle,beklenen", [
    (24, None, False), (25, None, True), (26, None, True),   # ruzgar_kuvvetli=25
    (10, 29, False), (10, 30, True), (10, 31, True),          # hamle_kuvvetli=30
])
def test_ruzgar_esik_siniri(hiz, hamle, beklenen):
    d = metar_coz(o.NORMAL)
    d["ruzgar_hiz"], d["ruzgar_hamle"] = hiz, hamle
    u = uyarilar(d)
    var = any("üzgâr" in x or "amle" in x for x in u)
    assert var == beklenen


# ------------------------------------------------------- property testleri
@pytest.mark.parametrize("yon,hiz", [
    (0, 10), (45, 15), (64.10, 20), (90, 5), (150, 25), (244.10, 12),
    (300, 8), (359, 30), (10, 0),
])
def test_property_crosswind_non_negative(yon, hiz):
    yr = yan_ruzgar(yon, hiz)
    assert yr >= 0


@pytest.mark.parametrize("yon,hiz,pist", [
    (0, 10, 64.10), (64.10, 20, 64.10), (90, 15, 64.10),
    (150, 25, 64.10), (244.10, 12, 64.10), (300, 8, 64.10),
])
def test_property_crosswind_ile_headwind_pisagor(yon, hiz, pist):
    """headwind^2 + crosswind^2 == wind^2 (trig ozdesligi - kesin esitlik,
    sadece kayan nokta yuvarlama payi ile)."""
    headwind = hiz * math.cos(math.radians(yon - pist))
    crosswind = yan_ruzgar(yon, hiz, pist)
    assert headwind ** 2 + crosswind ** 2 == pytest.approx(hiz ** 2, abs=1e-9)


def test_property_tam_bas_ruzgarinda_crosswind_sifir():
    assert yan_ruzgar(64.10, 15, pist=64.10) == pytest.approx(0, abs=1e-9)


def test_property_tam_yan_ruzgarinda_crosswind_esit_hiza():
    assert yan_ruzgar(64.10 + 90, 15, pist=64.10) == pytest.approx(15, abs=1e-9)


def test_yan_ruzgar_yon_yoksa_none():
    assert yan_ruzgar(None, 15) is None
    assert yan_ruzgar(60, None) is None


# ------------------------------------------------------------- fark_bul ---
def test_fark_ruzgar_yon_30_derece_esik():
    assert fark_bul(*o.FARK_RUZGAR_YON) == ["Rüzgâr: 050° 10kt → 090° 10kt"]


def test_fark_ruzgar_hiz_5kt_esik():
    assert fark_bul(*o.FARK_RUZGAR_HIZ) == ["Rüzgâr: 050° 10kt → 050° 18kt"]


def test_fark_gorus_esik_atlama():
    farklar = fark_bul(*o.FARK_GORUS_ESIK)
    assert any("örüş" in f for f in farklar)


def test_fark_tavan_500ft_esik():
    farklar = fark_bul(*o.FARK_TAVAN)
    assert any("avan" in f for f in farklar)


def test_fark_hava_degisimi():
    farklar = fark_bul(*o.FARK_HAVA)
    assert any(f.startswith("Hava:") for f in farklar)


def test_fark_qnh_2hpa_esik():
    assert fark_bul(*o.FARK_QNH) == ["QNH: 1015 → 1012 hPa"]


def test_fark_kucuk_oynama_rapor_edilmez():
    assert fark_bul(*o.FARK_YOK) == []


def test_fark_ilk_rapor_bos_onceki():
    assert fark_bul("", o.NORMAL) == []


@pytest.mark.parametrize("a_yon,b_yon,beklenen", [
    # 350 derece ile 10 derece arasindaki GERCEK (dairesel) fark 20 derecedir
    # (360-340=20), naif |b-a|=340 hesaplansaydi (yanlis) esigi asardi.
    # Kod dogru dairesel mesafeyi kullandigi icin uyari OLMAMALI.
    (350, 10, False),
    (10, 350, False),
    (0, 29, False),    # 29 derece esik alti
    (0, 30, True),     # tam esik
    (0, 31, True),
])
def test_fark_ruzgar_yon_dairesel_hesap(a_yon, b_yon, beklenen):
    a = f"METAR LTFJ 161250Z {a_yon:03d}10KT 9999 SCT025 18/12 Q1015 NOSIG"
    b = f"METAR LTFJ 161320Z {b_yon:03d}10KT 9999 SCT025 18/12 Q1015 NOSIG"
    farklar = fark_bul(a, b)
    var = any(f.startswith("Rüzgâr:") for f in farklar)
    assert var == beklenen
