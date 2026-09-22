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
