"""Dondurulmus dusuk-tavan tablosu + LVO farkindalik notu testleri.

En kritik uc test:
(1) Tablo KAT soyluyor, mutlak yuzde DEGIL - olculdu ki tablonun seviyesi
    donemler arasi ~2.3 kat kayiyor, sirasi ise tasiniyor; yuzde yayinlamak
    olculmus bir hatayi kesin sayi gibi sunmak olurdu,
(2) Not 500 ft'i acikca yaziyor - CAT II (200 ft) sanilmasin diye; 200 ft
    esiginde tablo kurulamadi (18 yilda ~61 bagimsiz olay),
(3) Calisma ani modulu HICBIR SEY import etmiyor (izolasyon sozlesmesi).
"""
import ast
import re
from pathlib import Path

import ltfj_lvo_farkindalik as f
import ltfj_tavan_tablosu as t
from tests.test_ltfj_sayfa_lvo import YASAK_KARAR_KALIPLARI

KOK = Path(__file__).resolve().parent.parent


def _cozum(sicaklik=8, cig=7.5, gorus=3000):
    return {"sicaklik": sicaklik, "cig_noktasi": cig, "gorus": gorus}


# ------------------------------------------------------------------ tablo
def test_modul_hicbir_sey_import_etmiyor():
    """Dondurulmus cikti saf veri + aritmetik olmali."""
    agac = ast.parse((KOK / "ltfj_tavan_tablosu.py").read_text(encoding="utf-8"))
    for node in ast.walk(agac):
        assert not isinstance(node, (ast.Import, ast.ImportFrom)), ast.dump(node)


def test_kat_eksik_degerde_none():
    assert t.kat(spread=None, gorus=3000) is None
    assert t.kat(spread=1.0, gorus=None) is None


def test_kat_spread_arttikca_azaliyor():
    """CAVOK bandinda spread tek degisken - iliski monoton olmali."""
    katlar = [t.kat(spread=sp, gorus=10000)["kat"]
              for sp in (0.5, 1.5, 2.5, 4.0, 6.0, 9.0)]
    assert katlar == sorted(katlar, reverse=True)


def test_aralik_nokta_tahmini_kapsiyor():
    for hucre in t.TABLO.values():
        _n, _poz, kat, alt, ust = hucre
        assert alt <= kat <= ust


def test_butun_katlar_pozitif_ve_taban_oran_makul():
    assert all(h[2] > 0 for h in t.TABLO.values())
    assert 0.005 < t.TABAN_ORAN < 0.03


def test_agirlikli_ortalama_kat_bire_yakin():
    """Kat = hucre olasiligi / taban oran; gozlem agirlikli ortalamasi
    tanimi geregi ~1 olmali (buzulme kucuk bir sapma birakir)."""
    n_top = sum(h[0] for h in t.TABLO.values())
    ortalama = sum(h[0] * h[2] for h in t.TABLO.values()) / n_top
    assert 0.8 < ortalama < 1.2


def test_bant_sinirlari_projenin_kendi_esikleri():
    from ltfj_vfr import VFR_GORUS_ESIGI_M
    assert VFR_GORUS_ESIGI_M in t.GORUS_BANTLARI
    assert 550 in t.GORUS_BANTLARI and 1000 in t.GORUS_BANTLARI


def test_hedef_500_ft_cat_ii_degil():
    """200 ft'te tablo kurulamadi - metin 500 yazmali ki CAT II sanilmasin."""
    assert t.HEDEF_TAVAN_FT == 500
    assert t.HEDEF_UFUK_SAAT == 3


# -------------------------------------------------------------------- not
def test_not_yuksek_riskte_cikiyor():
    n = f.tavan_istatistik_notu(_cozum(sicaklik=8, cig=7.5, gorus=3000))
    assert n and "kat" in n


def test_not_dusuk_riskte_cikmiyor():
    assert f.tavan_istatistik_notu(_cozum(sicaklik=20, cig=5, gorus=10000)) is None


def test_not_esigin_hemen_altinda_cikmiyor():
    """Esik a priori 3.0 kat; 2.4 katlik hucre not uretmemeli."""
    hucre = t.kat(spread=1.5, gorus=10000)
    assert 1.0 < hucre["kat"] < f.TAVAN_KAT_ESIGI
    assert f.tavan_istatistik_notu(_cozum(sicaklik=10, cig=8.5, gorus=10000)) is None


def test_not_sicaklik_veya_cig_yoksa_cikmiyor():
    assert f.tavan_istatistik_notu(_cozum(sicaklik=None)) is None
    assert f.tavan_istatistik_notu(_cozum(cig=None)) is None
    assert f.tavan_istatistik_notu(None) is None


def test_not_mutlak_yuzde_vermiyor():
    """Seviye donemler arasi ~2.3 kat kaydigi icin yuzde YAYINLANMAZ.
    Metinde yalnizca guven araligi etiketi olarak '%5-95' gecebilir."""
    n = f.tavan_istatistik_notu(_cozum())
    assert "GÖRELİ" in n and "mutlak olasılık değildir" in n
    for yuzde in re.findall(r"%\s*[\d.]+", n):
        assert yuzde.replace(" ", "") == "%5", n


def test_not_500_ft_ve_ufku_yaziyor():
    n = f.tavan_istatistik_notu(_cozum())
    assert "500 ft" in n and "3 saat" in n
    assert "CAT II" not in n


def test_not_ince_bandi_isaretliyor():
    """28 gozlemli bir hucrede metin bunu acikca soylemeli."""
    n = f.tavan_istatistik_notu(_cozum(sicaklik=10, cig=8.5, gorus=400))
    assert n and "gözlem var" in n and "aralık geniş" in n


def test_not_kalin_bandi_isaretlemiyor():
    n = f.tavan_istatistik_notu(_cozum())
    assert "aralık geniş" not in n


def test_not_hedge_tasiyor_ve_karar_vermiyor():
    n = f.tavan_istatistik_notu(_cozum())
    assert "Resmî bir tespit değildir" in n
    for kalip in YASAK_KARAR_KALIPLARI:
        assert not re.search(kalip, n, re.IGNORECASE), kalip


# ------------------------------------------------------------------ sayfa
def _sayfa(metin):
    import tempfile
    from datetime import datetime, timezone
    import ltfj_sayfa as s
    with tempfile.TemporaryDirectory() as d:
        hedef = Path(d) / "index.html"
        rapor = {"tip": "METAR", "metin": metin,
                 "zaman": datetime.now(timezone.utc), "icao": "LTFJ"}
        s.sayfa_yaz([rapor], [], hedef, {}, "")
        return hedef.read_text(encoding="utf-8")


def test_not_sayfada_lvo_panelinde_gorunuyor():
    html = _sayfa("LTFJ 172120Z 01003KT 3000 BR SCT015 08/08 Q1020")
    assert "uzun dönem ortalamasının" in html
    assert "lvo-fark-metar-taf" in html


def test_not_acik_havada_sayfada_yok():
    html = _sayfa("LTFJ 172120Z 18005KT CAVOK 22/05 Q1015")
    assert "uzun dönem ortalamasının" not in html
