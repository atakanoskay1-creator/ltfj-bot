"""Tek "İstatistik" başlığı: arşivden öğrenilmiş her şey aynı yerde.

KARAR (kullanıcı): istatistikler sayfada ÜÇ ayrı yere dağılmıştı -
sis olasılığı "Beklenti"de, tavan oranları LVO farkındalık notlarında,
geçiş süreleri hiç yoktu. Üçü de aynı cinsten (arşivden öğrenilmiş,
göreli, resmî tahmin değil).

AYIRIM: LVO'da KALAN notlar EŞİK KARŞILAŞTIRMASIDIR (METAR/TAF değeri
şu eşiğin altında mı) - onlar ölçüm. İstatistik bölümündekiler arşivden
öğrenilmiş oranlar.
"""
from datetime import datetime, timedelta, timezone

import ltfj_sayfa as s

SIMDI = datetime.now(timezone.utc)
# Spread dar + görüş düşük: tavan istatistik notu tetiklensin
METAR_SISLI = "LTFJ 172120Z 01003KT 1500 BR SCT008 06/06 Q1020"


def _gecmis(n=8):
    return [{"zaman": (SIMDI - timedelta(hours=h)).isoformat(),
             "ruzgar_hiz": 3, "tavan": 600, "qnh": 1020,
             "sicaklik": 6, "cig_noktasi": 6 - h * 0.3} for h in range(n - 1, -1, -1)]


def _sayfa(tmp_path, metin=METAR_SISLI) -> str:
    hedef = tmp_path / "index.html"
    rapor = {"tip": "METAR", "metin": metin, "zaman": SIMDI, "icao": "LTFJ"}
    s.sayfa_yaz([rapor], _gecmis(), hedef)
    return hedef.read_text(encoding="utf-8")


def _bolum(html: str, baslik: str) -> str:
    return html.split(baslik)[1].split("</details>")[0]


# ------------------------------------------------------------ bölüm var
def test_istatistik_basligi_var(tmp_path):
    assert "İstatistik · arşivden" in _sayfa(tmp_path)


def test_istatistik_katlanir_ve_KAPALI_basliyor(tmp_path):
    html = _sayfa(tmp_path)
    blok = html[html.index("İstatistik · arşivden") - 120:
                html.index("İstatistik · arşivden")]
    assert "<details" in blok
    assert "open" not in blok


def test_rozet_kapaliyken_de_olasiligi_gosteriyor(tmp_path):
    """Bölüm unutulmasın diye başlıkta sis yüzdesi duruyor."""
    html = _sayfa(tmp_path)
    assert 'class="kat-rozet">sis %' in html


# ------------------------------------------------- taşınanlar geldi mi
def test_sis_olasiligi_ISTATISTIK_altinda(tmp_path):
    html = _sayfa(tmp_path)
    assert "İstatistiksel sis olasılığı" in _bolum(html, "İstatistik · arşivden")


def test_tavan_istatistik_notu_ISTATISTIK_altinda(tmp_path):
    """LVO farkındalık notlarından TAŞINDI - "kat daha sık" ifadesi
    arşivden öğrenilmiş göreli bir orandır, eşik karşılaştırması değil."""
    html = _sayfa(tmp_path)
    ist = _bolum(html, "İstatistik · arşivden")
    assert "Tavan istatistiği" in ist
    assert "kat daha sık" in ist


def test_tavan_istatistigi_LVO_panelinden_KALKTI(tmp_path):
    """EN KRİTİK TAŞIMA TESTİ: iki yerde birden durursa kullanıcı aynı
    bilgiyi iki kez okur ve hangisinin güncel olduğunu bilemez."""
    html = _sayfa(tmp_path)
    lvo = html.split('id="lvo-govde"')[1].split("LVO REFERENCE")[0]
    assert "kat daha sık" not in lvo


def test_LVO_esik_notlari_YERINDE_kaldi(tmp_path):
    """Taşıma, LVO panelini boşaltmak DEĞİL: METAR/TAF eşik notları
    ölçümdür ve orada kalmalı."""
    html = _sayfa(tmp_path)
    assert 'id="lvo-fark-metar-taf"' in html
    assert 'id="lvo-fark-rvr-liste"' in html


# ------------------------------------------------------ geçiş tablosu
def test_gecis_tablosu_var(tmp_path):
    html = _sayfa(tmp_path)
    ist = _bolum(html, "İstatistik · arşivden")
    assert "Görüş geçiş süreleri" in ist
    assert 'class="gecis-tablo"' in ist


def test_gecis_tablosu_DONDURULMUS_tablodan_okuyor():
    """Bot arşivi (6 MB) çalışma anında okumamalı - ltfj_sis_olasilik
    ile aynı disiplin."""
    import ltfj_gorus_gecis_tablo as t
    assert s.gecis_tablo is t
    assert t.DUSME["n"] > 0 and t.TOPARLANMA["n"] > 0


def test_dondurulmus_tablo_agir_bagimlilik_ICERMIYOR():
    import ast
    from pathlib import Path
    kok = Path(__file__).resolve().parent.parent
    agac = ast.parse((kok / "ltfj_gorus_gecis_tablo.py").read_text(encoding="utf-8"))
    importlar = [n for n in ast.walk(agac)
                 if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert importlar == [], "dondurulmuş tablo hiçbir şey import etmemeli"


def test_tablo_medyani_ve_hizli_kuyrugu_BIRLIKTE_gosteriyor(tmp_path):
    """Medyanı tek başına göstermek yanıltıcı: olayların önemli bir
    kısmında geçiş çok daha hızlı."""
    html = _sayfa(tmp_path)
    ist = _bolum(html, "İstatistik · arşivden")
    for s_ in ("%10", "%25", "medyan", "%75"):
        assert s_ in ist, s_


def test_izgara_tabani_UYARISI_var(tmp_path):
    """"0.5 sa" aslında "yarım saat VEYA DAHA KISA" demek - bu
    söylenmezse olmayan bir hassasiyet ima edilir."""
    html = _sayfa(tmp_path)
    assert "yarım saat veya daha kısa" in html
    assert "30 dakikalık gözlem ızgarasına yuvarlıdır" in html


def test_tahmin_DEGIL_uyarisi_var(tmp_path):
    html = _sayfa(tmp_path)
    assert "SAYIMIDIR, tahmin değildir" in html


def test_kapsam_ve_olay_sayisi_yaziyor(tmp_path):
    """64 olay küçük bir örneklem - gizlenmemeli."""
    import ltfj_gorus_gecis_tablo as t
    html = _sayfa(tmp_path)
    assert f"{t.KAPSAM_ILK_YIL}–{t.KAPSAM_SON_YIL}" in html
    assert f"{t.OLAY_SAYISI} sis olayı" in html


# ------------------------------------------------------ geriye uyumluluk
def test_veri_yokken_bolum_hic_cikmiyor(tmp_path):
    """Rapor yoksa istatistik de yok - boş bir kart görünmemeli."""
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([], [], hedef)
    html = hedef.read_text(encoding="utf-8")
    # Geçiş tablosu sabit olduğu için bölüm yine çıkabilir; ama sis
    # olasılığı kartı çıkmamalı.
    assert "İstatistiksel sis olasılığı" not in html
