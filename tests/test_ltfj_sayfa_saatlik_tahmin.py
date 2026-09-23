"""Sayfadaki "Önümüzdeki saatler" şeridi (Open-Meteo model tahmini).

En kritik test: bu blok TAF'ın yerine geçiyormuş gibi görünMEMELİ. Geriye
dönük dürüst bir doğrulama yapılamadığı için (bkz. ltfj_dis_kaynak_cache
modül açıklaması) buradan bir karar sinyali türetilmiyor; sayfa da bunu
açıkça söylüyor.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ltfj_sayfa as s


def _satirlar(n=3):
    ilk = (datetime.now(timezone.utc) + timedelta(hours=1)
           ).replace(minute=0, second=0, microsecond=0)
    return [{
        "saat": (ilk + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M"),
        "temperature_2m": 12 - i, "dew_point_2m": 8,
        "relative_humidity_2m": 80 + i, "wind_speed_10m": 9,
        "wind_direction_10m": 20, "cloud_cover_low": 40,
        "visibility": 12000 if i == 0 else 3000,
    } for i in range(n)]


# ------------------------------------------------------------- blok yok
def test_tahmin_yoksa_blok_hic_basilmiyor():
    """Önbellek bayat/yoksa boş liste gelir - sayfada boş bir kart
    görünmemeli, blok tamamen çıkmalı."""
    assert s._saatlik_tahmin_html([]) == ""


def test_sayfa_tahmin_verilmeden_de_uretiliyor(tmp_path):
    """Geriye uyumluluk: parametre verilmeyen eski çağrılar çalışmalı.

    'Önümüzdeki saatler' metni CSS yorumunda da geçtiği için kartın
    KENDİSİNE bakılıyor - şerit yalnızca blok basıldığında üretilir."""
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([], [], hedef)
    assert 'class="tahmin-serit"' not in hedef.read_text(encoding="utf-8")


# ------------------------------------------------------------ icerik
def test_taf_degildir_uyarisi_var():
    html = s._saatlik_tahmin_html(_satirlar())
    assert "TAF değildir" in html
    assert "resmî havacılık tahmini yerine geçmez" in html


def test_kaynak_acikca_yaziyor():
    assert "Open-Meteo" in s._saatlik_tahmin_html(_satirlar())


def test_her_saat_icin_bir_hucre():
    html = s._saatlik_tahmin_html(_satirlar(n=5))
    assert html.count('class="tahmin-hucre"') == 5


def test_spread_hesaplaniyor():
    """Spread (sıcaklık - çiy noktası) bu projedeki en güçlü öncü
    göstergeydi, şeritte başa konuyor."""
    html = s._saatlik_tahmin_html(_satirlar(n=1))   # 12 - 8 = 4.0
    assert "4.0°" in html


def test_gorus_10km_ustu_kisaltiliyor():
    """Aradaki her 100 metreyi göstermek olmayan bir hassasiyet ima eder."""
    html = s._saatlik_tahmin_html(_satirlar(n=2))
    assert "10+ km" in html      # 12000 m
    assert "3.0 km" in html      # 3000 m


def test_eksik_degerler_cokmeden_tire_basiliyor():
    satir = [{"saat": _satirlar(n=1)[0]["saat"]}]
    html = s._saatlik_tahmin_html(satir)
    assert "—" in html


def test_bozuk_saat_damgasi_cokmuyor():
    html = s._saatlik_tahmin_html([{"saat": "bozuk", "temperature_2m": 5,
                                    "dew_point_2m": 3}])
    assert 'class="tahmin-hucre"' in html


# ------------------------------------------------------------ sayfaya gomulme
def test_sayfaya_gomulunce_gorunuyor(tmp_path):
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([], [], hedef, saatlik_tahmin=_satirlar())
    html = hedef.read_text(encoding="utf-8")
    assert "Önümüzdeki saatler" in html
    assert "TAF değildir" in html
    assert 'class="tahmin-serit"' in html


# ================================================ sis kodu + sınır tabakası
# Bu iki alan DENEYSEL: Open-Meteo kabul etmezse önbellekte hiç olmazlar
# (bkz. ltfj_dis_kaynak_cache.HOURLY_DENEYSEL). Şerit her iki durumda da
# çizilmeli - eksikliği hata değil.
def _sisli_satir(kod=45, blh=120.0):
    s = _satirlar(n=1)[0]
    s["weather_code"] = kod
    s["boundary_layer_height"] = blh
    return [s]


def test_sis_kodunda_isaret_ve_kenarlik_var():
    html = s._saatlik_tahmin_html(_sisli_satir(kod=45))
    assert '<div class="tahmin-sis"' in html
    assert "tahmin-hucre-sis" in html


def test_kiragili_sis_kodu_48_de_isaretleniyor():
    assert '<div class="tahmin-sis"' in s._saatlik_tahmin_html(_sisli_satir(kod=48))


def test_sissiz_kodda_isaret_yok():
    html = s._saatlik_tahmin_html(_sisli_satir(kod=3))
    assert '<div class="tahmin-sis"' not in html
    assert "tahmin-hucre-sis" not in html


def test_sinir_tabakasi_yuksekligi_gosteriliyor():
    assert "120 m" in s._saatlik_tahmin_html(_sisli_satir(blh=120.0))


def test_deneysel_alanlar_yoksa_serit_yine_ciziliyor():
    """En kritik test: Open-Meteo bu alanları reddederse şerit
    kaybolmamalı, sadece işaret/satır çıkmamalı."""
    html = s._saatlik_tahmin_html(_satirlar(n=3))   # weather_code/blh YOK
    assert html.count('class="tahmin-hucre') == 3
    assert '<div class="tahmin-sis"' not in html


def test_sis_kodlari_tek_yerde_tanimli():
    """Sabit kopyalanmasın - alanın tanımıyla aynı yerde dursun."""
    import ltfj_dis_kaynak_cache as dkc
    assert s.SIS_KODLARI is dkc.SIS_KODLARI
    assert 45 in dkc.SIS_KODLARI and 48 in dkc.SIS_KODLARI


def test_aciklama_sis_isaretini_ve_blh_yi_anlatiyor():
    html = s._saatlik_tahmin_html(_sisli_satir())
    assert "WMO 45/48" in html
    assert "sınır tabakası" in html


# ============================================ bayatlik: gizleme yerine etiket
# GERCEK KUSUR (kullanici bildirdi: "bazen goruluyor bazen gorulmuyor"):
# onbellek cron'u ":3,23,43" (20 dk) ayarliydi ama GitHub zamanlanmis
# kosulari dusuruyor - 26 saatte 78 yerine 6 planli kosu gerceklesti,
# araliklar 2-6 saat (HEPSI BASARILI; cekme kodu saglam). 180 dk'lik
# bayatlik esigi bu gercek kadansin ALTINDA oldugu icin serit zamanin
# onemli kismnda kayboluyordu.
def test_esik_gercek_cron_kadansinin_ustunde():
    """Esik, olculen yenilenme araligindan (2-6 saat) kisa olmamali."""
    import ltfj_dis_kaynak_cache as dkc
    assert dkc.TAHMIN_ESIK_DK >= 360


def test_yas_verilmezse_rozet_yok():
    """Geriye uyumluluk: yas parametresi olmayan eski cagrilar aynen
    calismali ve fazladan bir sey basmamali."""
    html = s._saatlik_tahmin_html(_satirlar())
    assert "tahmin-yas" not in html


def test_taze_tahminde_yas_yazilmiyor():
    """Her seferinde "18 dk once" yazmak bilgi degil gurultu olurdu."""
    assert "tahmin-yas" not in s._saatlik_tahmin_html(_satirlar(), yas_dk=20)


def test_bayat_tahminde_yas_aciklca_yaziliyor():
    html = s._saatlik_tahmin_html(_satirlar(), yas_dk=300)
    assert "tahmin-yas" in html
    assert "5 saat önceki model çıktısı" in html


def test_yas_esigin_hemen_ustunde_ondalikli_yaziliyor():
    """1.6 saat'i "2 saat" diye yuvarlamak olmayan bir bayatligi ima eder."""
    html = s._saatlik_tahmin_html(_satirlar(), yas_dk=95)
    assert "1.6 saat önceki model çıktısı" in html


def test_bayat_tahmin_yine_de_GOSTERILIYOR():
    """EN KRITIK TEST: eski davranis bayat tahmini tamamen gizliyordu.
    Artik gosteriliyor, yalnizca yasi etiketleniyor - "bazen var bazen
    yok" davranisinin kaynagi buydu."""
    html = s._saatlik_tahmin_html(_satirlar(n=4), yas_dk=300)
    assert html.count('class="tahmin-hucre') == 4


def test_yas_sinir_sabiti_tek_yerde():
    assert s.TAHMIN_YAS_UYARI_DK > 0


def test_sayfaya_yas_ile_gomulunce_gorunuyor(tmp_path):
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([], [], hedef, saatlik_tahmin=_satirlar(), tahmin_yas_dk=250)
    assert "4 saat önceki model çıktısı" in hedef.read_text(encoding="utf-8")
