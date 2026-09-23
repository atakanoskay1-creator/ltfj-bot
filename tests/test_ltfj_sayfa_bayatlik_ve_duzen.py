"""NOTAM senkron yasi, bayatlik uyarisi ve footer hizalamasi.

ORTAK TEMA - SESSIZ BAYATLIK: bu projede ayni kusur uc kez cikti
(push gitmiyordu, suresi dolmus NOTAM aktif gorunuyordu, Open-Meteo
seridi kayboluyordu). Ucunde de veri sessizce eskiyor ya da kayboluyor
ve kullanici bunu FARK EDEMIYOR. Buradaki testler NOTAM listesi icin
ayni sinifin dordunculusunu kapatir.
"""
import ltfj_sayfa as s


def _sayfa(tmp_path) -> str:
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([], [], hedef)
    return hedef.read_text(encoding="utf-8")


# ------------------------------------------- NOTAM senkron yasi goreceli
def test_ham_utc_damgasi_ARTIK_basilmiyor(tmp_path):
    """REGRESYON: eskiden "son senkron 2026-09-22 19:51" yaziyordu.
    Bu UTC'ydi ama etiketsizdi; sayfadaki diger saatler YEREL. Hangi
    saat dilimi oldugu belirtilmeden yaniltici."""
    html = _sayfa(tmp_path)
    assert 'veri.son_senkron.replace("T", " ")' not in html


def test_gecen_sure_yardimcisi_var_ve_TEK(tmp_path):
    html = _sayfa(tmp_path)
    assert html.count("window.ltfjGecenSure = function") == 1


def test_gecen_sure_kademeleri(tmp_path):
    html = _sayfa(tmp_path)
    for parca in ('"az önce"', '" dk önce"', '" sa önce"', '" gün önce"'):
        assert parca in html, parca


def test_senkron_metni_goreceli_yaziliyor(tmp_path):
    html = _sayfa(tmp_path)
    assert "window.ltfjGecenSure(yasMs)" in html
    assert "senkronize edildi" in html


def test_hic_senkron_yoksa_ayri_mesaj(tmp_path):
    assert "henüz senkronize edilmedi" in _sayfa(tmp_path)


def test_bozuk_zaman_damgasi_cokmuyor(tmp_path):
    """new Date("saçma") NaN verir; ekrana "NaN dk önce" yazilmamali."""
    html = _sayfa(tmp_path)
    assert "isNaN(yasMs)" in html
    assert "senkron zamanı okunamadı" in html


# ----------------------------------------------------- bayatlik uyarisi
def test_bayatlik_esigi_senkron_araligiyla_TUTARLI(tmp_path):
    """Ayarlardaki notam.senkron_araligi_saat 6; esik bunun iki kati
    olmali - bir senkron kacinca degil, ikisi kacinca uyarmali."""
    from ltfj_ayarlar import ayar
    aralik = ayar("notam", "senkron_araligi_saat", varsayilan=6)
    html = _sayfa(tmp_path)
    assert f"var NOTAM_BAYAT_MS = {2 * aralik} * 3600 * 1000;" in html


def test_bayat_senkronda_gorunur_uyari(tmp_path):
    html = _sayfa(tmp_path)
    assert "notam-senkron-bayat" in html
    assert "liste eski olabilir" in html


def test_bayatlik_sinifi_her_cizimde_TEMIZLENIYOR(tmp_path):
    """Senkron tazelendiginde uyari kalkmali - sinif birikirse bir kez
    bayatlayan liste sonsuza dek bayat gorunurdu."""
    html = _sayfa(tmp_path)
    assert 'senkronEl.classList.remove("notam-senkron-bayat")' in html


def test_bayat_uyarisi_KIRMIZI_degil(tmp_path):
    """Liste hala dogru olabilir, sadece dogrulanmamis - kirmizi
    "yanlis" ima ederdi."""
    html = _sayfa(tmp_path)
    css = html.split(".notam-senkron-bayat {")[1].split("}")[0]
    assert "#ef4444" not in css


# ------------------------------------------------------ footer hizalama
def test_footer_SOLA_yasli(tmp_path):
    """Ortalanmis uzun metinde her satirin sol kenari farkli yerden
    basliyor; goz her satirbasinda yeniden hizalanmak zorunda kaliyor.
    Footer'daki yasal uyari telefonda 15+ satir suruyor."""
    html = _sayfa(tmp_path)
    css = html.split("\n  footer {")[1].split("}")[0]
    assert "text-align:left" in css
    assert "text-align:center" not in css


def test_tahmin_SAAT_basliklari_ORTALI_SAYILAR_SAGA_yasli(tmp_path):
    """Serit tabloya cevrilince hizalama ikiye ayrildi ve bu KASITLI:

    - SAAT basliklari tek kelimelik etiket -> ortali (eski tercih).
    - SAYILAR saga yasli -> basamaklar alt alta gelir. "10+" ile "3.0"
      ortali dizilseydi virgul/basamak hizasi kayardi ve bir sutunu
      dikey taramak zorlasirdi; tabular-nums da ancak saga yasliyken
      ise yarar.
    """
    html = _sayfa(tmp_path)
    hucre = html.split(".tahmin-tablo th, .tahmin-tablo td {")[1].split("}")[0]
    assert "text-align:right" in hucre
    bas = html.split(".tahmin-tablo thead th {")[1].split("}")[0]
    assert "text-align:center" in bas
