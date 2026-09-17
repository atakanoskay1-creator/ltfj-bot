"""ltfj_lvo_referans.py testleri.

Bu modul SADECE PDF'ten (TL.007 Rev.1) alinmis STATIK referans verisi
tasir - hicbir karar fonksiyonu icermez. Testler; (1) dokuman metadata'sinin
dogru oldugunu, (2) esik/tablo degerlerinin PDF'teki degerlerle eslestigini,
(3) bu modulun METAR/pist karar mantigina (ltfj_analiz, ltfj_pist) HICBIR
BAGIMLILIGI olmadigini dogruluyor - boylece LVO referans katmani ile
operasyonel karar katmani arasindaki ayrimin kod seviyesinde de gercekten
var oldugu kanitlanmis olur."""
import ast
from pathlib import Path

import ltfj_lvo_referans as lvo


def test_dokuman_metadata_doğru():
    assert lvo.DOKUMAN["dok_no"] == "TL.007"
    assert lvo.DOKUMAN["rev_no"] == "REV.1"
    assert lvo.DOKUMAN["rev_tarihi"] == "16.08.2024"
    assert lvo.DOKUMAN["etiket"] == "DOCUMENT REFERENCE ONLY"


def test_pist_tablosu_dort_pisti_de_iceriyor():
    pistler = {p["pist"] for p in lvo.PIST_TABLOSU}
    assert pistler == {"06R", "24L", "06L", "24R"}


def test_06r_cat_ii_inis_ve_kalkis_araligi_dogru():
    p = next(p for p in lvo.PIST_TABLOSU if p["pist"] == "06R")
    assert p["kategori"] == "CAT II"
    assert p["inis_rvr"] == "550–300"
    assert p["kalkis_rvr"] == "400–125"


def test_24r_sadece_lvto_kalkis():
    p = next(p for p in lvo.PIST_TABLOSU if p["pist"] == "24R")
    assert p["kategori"] == "CAT I"
    assert p["inis_rvr"] == "—"
    assert p["kalkis_rvr"] == "400–125"
    assert "LVTO" in p["aciklama"]


def test_06l_24l_inis_kalkis_tanimsiz():
    for pist in ("06L", "24L"):
        p = next(p for p in lvo.PIST_TABLOSU if p["pist"] == pist)
        assert p["inis_rvr"] == "—"
        assert p["kalkis_rvr"] == "—"


def test_rvr_esikleri_dokumandaki_dort_deger():
    esikler = {e["esik_altinda_m"] for e in lvo.RVR_ESIKLERI}
    assert esikler == {800, 550, 400, 350}


def test_kategori_tanimlari_rvr_ve_dh_birlikte_tasiniyor():
    """CAT I/II tanimlari RVR TEK BASINA degil DH ile BIRLIKTE - ikisi de
    her kayitta bulunmali, tek bir sayi indirgenmis olmamali."""
    for k in lvo.KATEGORI_TANIMLARI:
        assert "rvr" in k and "dh" in k
    cat2 = next(k for k in lvo.KATEGORI_TANIMLARI if k["kategori"] == "CAT II")
    assert "300" in cat2["rvr"] and "550" in cat2["rvr"]


def test_uyari_notlari_bos_degil():
    assert len(lvo.UYARI_NOTLARI) >= 1
    assert all(isinstance(n, str) and n for n in lvo.UYARI_NOTLARI)


def test_bilgi_uyarisi_operasyonel_karar_yerine_gecmez_ifadesini_tasir():
    assert "Operasyonel karar yerine geçmez" in lvo.BILGI_UYARISI


# --------------------------------------------------- izolasyon garantisi
def test_modulun_hic_importu_yok_karar_katmanina_bagimli_degil():
    """LVO referans modulu ltfj_pist.py / ltfj_analiz.py (meteorolojik
    karar/pist tercih katmani) veya ltfj_notam*.py'a HICBIR sekilde
    bagimli olmamali - bu modul TAMAMEN izole, sadece statik veri tasir.
    AST ile kaynagi ayristirip gercek import ifadelerini kontrol ediyoruz
    (yorum satirindaki gecmis metinlere degil)."""
    kaynak = Path(lvo.__file__).read_text(encoding="utf-8")
    agac = ast.parse(kaynak)
    importlar = set()
    for node in ast.walk(agac):
        if isinstance(node, ast.Import):
            importlar.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            importlar.add(node.module)
    assert importlar == set(), f"Beklenmeyen import(lar): {importlar}"


def test_modulde_karar_uretecek_fonksiyon_yok():
    """Bu modulde 'def' ile tanimlanmis HICBIR fonksiyon olmamali - sadece
    sabit veri (dict/list) tasimali. Bir fonksiyon varligi bile, ileride
    yanlislikla bir karsilastirma/karar mantigi eklenmesi riskini artirir."""
    kaynak = Path(lvo.__file__).read_text(encoding="utf-8")
    agac = ast.parse(kaynak)
    fonksiyonlar = [n.name for n in ast.walk(agac) if isinstance(n, ast.FunctionDef)]
    assert fonksiyonlar == [], f"Beklenmeyen fonksiyon(lar): {fonksiyonlar}"
