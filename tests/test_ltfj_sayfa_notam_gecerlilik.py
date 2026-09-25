"""NOTAM kartlarinin GUNCEL gecerlilik etiketi + aktif liste filtreleri.

Arka plan (gercek kusur): notam_veri.json'daki `status` alani NOTAC'tan en
son GORULDUGU andaki degerdir ve DONUKTUR. Suresi dolmus bir NOTAM yerel
gecmiste sonsuza dek "active" yazar; bu yuzden arama sonuclarinda bitmis
NOTAM'lar aktif (yesil noktali) gorunuyordu. Sayfa artik effective_start/
effective_end'i her cizimde SIMDIKI zamana gore degerlendiriyor.

Bu testler uretilen HTML'deki JS'i metin olarak dogrular - tarayicidaki
davranis ayrica Playwright ile elle test edildi (bkz. commit mesaji)."""
from pathlib import Path

import ltfj_sayfa as s


def _sayfa(tmp_path) -> str:
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([], [], hedef)
    return hedef.read_text(encoding="utf-8")


# ------------------------------------------------- gecerlilik hesaplamasi
def test_gecerlilik_yardimcisi_tek_yerde_tanimli(tmp_path):
    """Ayni "aktif mi?" karari eskiden iki ayri script'te kopyalanmisti
    ve iki kopya da ayni hatayi tasiyordu - tek kaynak olmali."""
    html = _sayfa(tmp_path)
    assert html.count("window.ltfjNotamGecerlilik = function") == 1


def test_yesil_nokta_donuk_status_yerine_hesaplanan_duruma_bagli(tmp_path):
    """REGRESYON: eskiden `n.status === "active"` kontrol ediliyordu, bu
    yuzden suresi dolmus NOTAM'lar da yesil nokta aliyordu."""
    html = _sayfa(tmp_path)
    assert 'n.status === "active"' not in html
    assert 'g.durum === "yururlukte"' in html
    # LVO panelindeki ikinci kopya da ayni yardimciya bagli olmali.
    assert 'window.ltfjNotamGecerlilik(n).durum === "yururlukte"' in html


def test_suresi_dolmus_ve_baslamamis_etiketleri_var(tmp_path):
    html = _sayfa(tmp_path)
    assert "süresi doldu" in html
    assert "henüz başlamadı" in html


# --------------------------------------------------------- kalan sure
def test_yururluktekilerde_kalan_sure_yaziliyor(tmp_path):
    """'yürürlükte' yazmak bilgi tasimiyordu - Aktif NOTAM listesindeki
    HER kart zaten yururlukte. Yerine kalan sure yaziliyor."""
    html = _sayfa(tmp_path)
    assert "window.ltfjKalanSure" in html
    assert '"yürürlükte"' not in html


def test_kalan_sure_kademeleri_ve_kalici_notam(tmp_path):
    html = _sayfa(tmp_path)
    for parca in ("dk kaldı", "sa kaldı", "gün kaldı",
                  "birazdan bitiyor", "süresiz"):
        assert parca in html, parca


def test_kalan_sure_goreceli_yaziliyor_mutlak_saat_degil(tmp_path):
    """Sayfadaki saatler yerel, NOTAM verisi UTC - mutlak saat yazmak
    saat dilimi belirtilmeden yaniltici olurdu."""
    html = _sayfa(tmp_path)
    assert "toLocaleTimeString" not in html.split("ltfjKalanSure")[1][:400]


def test_iptal_edilmis_notam_tarihten_bagimsiz_olarak_ayri_ele_aliniyor(tmp_path):
    """NOTAC'in kendi status'u 'active' DEGILSE (cancelled/withdrawn)
    tarih penceresi bakilmadan o deger gosterilmeli - iptal edilmis bir
    NOTAM tarihi gecmemis olsa da yururlukte degildir."""
    html = _sayfa(tmp_path)
    assert 'if (n.status && n.status !== "active")' in html


def test_arama_durum_filtresi_hesaplanan_gecerliligi_kullaniyor(tmp_path):
    """Kartta 'süresi doldu' yazarken filtrede 'active' secenegi olmasi
    tutarsiz olurdu - filtre de ayni hesaplamaya bagli."""
    html = _sayfa(tmp_path)
    assert 'gecerlilik(n).durum !== durum' in html
    assert 'n.status !== durum' not in html


def test_durum_secenekleri_ham_statusten_uretilmiyor(tmp_path):
    """Eski durumSecenekleriDoldur() ham status degerlerinden secenek
    uretiyordu (pratikte hep tek bir 'active'); yerini sabit, anlamli
    gecerlilik secenekleri aldi."""
    html = _sayfa(tmp_path)
    assert "durumSecenekleriDoldur" not in html
    for deger in ('value="yururlukte"', 'value="doldu"', 'value="baslamadi"'):
        assert deger in html


# ------------------------------------------------------- aktif filtreleri
def test_aktif_panelinde_filtre_alanlari_var(tmp_path):
    html = _sayfa(tmp_path)
    for eid in ("notam-aktif-q", "notam-aktif-kategori",
                "notam-aktif-eleman", "notam-aktif-temizle"):
        assert 'id="' + eid + '"' in html, eid


def test_aktif_liste_suresi_dolmuslari_ayikliyor(tmp_path):
    """Senkron bayatlarsa (NOTAC erisilemez) aradan gecen surede suresi
    biten bir NOTAM 'aktif' listesinde kalirdi - tarih kontrolu kapatir."""
    html = _sayfa(tmp_path)
    assert "function yururluktekiler()" in html
    assert 'gecerlilik(n).durum === "yururlukte"' in html


def test_upcoming_notamlar_ayri_listede_gosteriliyor(tmp_path):
    html = _sayfa(tmp_path)
    assert "Upcoming NOTAM'lar" in html
    assert 'id="notam-upcoming-liste"' in html
    assert 'id="notam-upcoming-sayi"' in html
    assert "function yaklasanlar()" in html
    assert 'gecerlilik(n).durum === "baslamadi"' in html
    assert "upcomingGosterilecek.map(notamKarti)" in html


def test_notam_numarasi_kaynaktaki_number_alanindan_etiketli_gosteriliyor(tmp_path):
    html = _sayfa(tmp_path)
    assert "NOTAM NO:" in html
    assert 'esc(n.number || "—")' in html


def test_notamc_aktif_ve_upcoming_listelerinden_filtrelenmiyor(tmp_path):
    """N/R/C ayrimi rozet icindir; C kaydi liste seciminde elenmemeli."""
    html = _sayfa(tmp_path)
    yaklasan_govde = html.split("function yaklasanlar()", 1)[1].split("function aktifFiltrele", 1)[0]
    yururlukte_govde = html.split("function yururluktekiler()", 1)[1].split("function yaklasanlar", 1)[0]
    assert "n.notam_type" not in yaklasan_govde
    assert "n.notam_type" not in yururlukte_govde
    assert '"C": {ad: "NOTAMC"' in html


def test_filtre_secenekleri_aktif_ve_upcoming_notamlardan_uretiliyor(tmp_path):
    html = _sayfa(tmp_path)
    assert "function aktifFiltreSecenekleriDoldur()" in html
    assert "yururluktekiler().concat(yaklasanlar())" in html
    # Secenekler her veri yuklemesinde YENIDEN kurulur; eskiden secenek
    # eklemesi temizlenmedigi icin yinelenme riski vardi.
    assert "while (el.options.length > 1) el.remove(1);" in html


def test_filtreler_notam_bolumunun_icinde(tmp_path):
    """Filtreler listenin USTUNDE ve NOTAM bolumunun icinde olmali - sekme
    secili degilken filtre satiri da gorunmemeli.

    Ac/kapa artik ne elle yazilmis JS ne de <details>: NOTAM kendi SEKME
    PANELI. Eski aktifGovdeEl/aktifPaneliAcKapat mekanizmasi kaldirildi."""
    html = _sayfa(tmp_path)
    assert "aktifPaneliAcKapat" not in html
    notam_karti = html.split('id="panel-notam"')[1]
    for eid in ("notam-aktif-filtre", "notam-aktif-liste", "notam-q"):
        assert 'id="' + eid + '"' in notam_karti, eid
    # Filtre satiri listeden ONCE gelmeli.
    assert notam_karti.index('id="notam-aktif-filtre"') < \
        notam_karti.index('id="notam-aktif-liste"')


# ------------------------------------------------------- canli arama
def test_arama_butonu_kaldirildi_canli_suzuluyor(tmp_path):
    """Aktif liste yazdikca suzulurken aramanin ayri bir 'Ara' adimi
    istemesi ayni sayfada iki farkli etkilesim demekti."""
    html = _sayfa(tmp_path)
    assert "notam-ara-btn" not in html
    assert 'id="notam-arama-temizle"' in html
    assert 'getElementById("notam-q").addEventListener("input", aramaCalistir)' in html


def test_arama_tarih_ve_durum_degisiminde_de_calisiyor(tmp_path):
    html = _sayfa(tmp_path)
    for eid in ("notam-tarih-baslangic", "notam-tarih-bitis"):
        assert 'getElementById("' + eid + '").addEventListener("change", aramaCalistir)' in html
    assert 'durumSelectEl.addEventListener("change", aramaCalistir)' in html


def test_kriter_yoksa_tum_gecmis_dokulmuyor(tmp_path):
    """Bilincli tercih: 'gecmis' NOTAC'in arsivi degil, sadece botun
    gordukleri - istenmeden dokulmesi yaniltici olur."""
    html = _sayfa(tmp_path)
    assert "if (!q && !ts && !te && !durum)" in html
    assert "Aramak için yukarıdaki" in html


def test_artik_kullanilmayan_arama_bayragi_kalmadi(tmp_path):
    assert "aramaYapildiMi" not in _sayfa(tmp_path)
