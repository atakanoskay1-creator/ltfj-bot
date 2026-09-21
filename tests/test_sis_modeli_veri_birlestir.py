"""sis_modeli/veri_birlestir.py testleri.

En kritik test: tolerans DIŞINDAKİ bir gözlem SESSİZCE yanlış (çok uzak) bir
komşuya eşlenmemeli - alan None kalmalı. İkinci kritik test: kaynak dosya
yoksa (henüz çekilmemişse) zenginlestir() ÇÖKMEMELİ, sadece tüm ek alanları
None bırakmalı."""
import csv
import gzip
from pathlib import Path

import pytest

from sis_modeli import veri_birlestir as vb


def _gz_yaz(yol: Path, satirlar: list[dict]):
    yol.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(yol, "wt", encoding="utf-8", newline="") as f:
        yazici = csv.DictWriter(f, fieldnames=list(satirlar[0].keys()))
        yazici.writeheader()
        yazici.writerows(satirlar)


@pytest.fixture
def komsu_dosyasi(tmp_path):
    yol = tmp_path / "komsu_ltfm_ozellik.csv.gz"
    _gz_yaz(yol, [
        {"zaman": "2024-01-01T00:00", "spread": "1.0", "sis": "0", "gorus": "9999", "tavan": ""},
        {"zaman": "2024-01-01T03:00", "spread": "0.0", "sis": "1", "gorus": "400", "tavan": "200"},
    ])
    return yol


@pytest.fixture
def acik_meteo_dosyasi(tmp_path):
    yol = tmp_path / "acik_meteo_ltfj.csv.gz"
    _gz_yaz(yol, [
        {"zaman": "2024-01-01T00:00", "temperature_2m": "5.0", "temperature_925hPa": "3.0",
         "temperature_850hPa": "8.0", "relative_humidity_2m": "90"},
        {"zaman": "2024-01-01T03:00", "temperature_2m": "2.0", "temperature_925hPa": "6.0",
         "temperature_850hPa": "9.0", "relative_humidity_2m": "98"},
    ])
    return yol


def _ltfj_kayit(zaman):
    return {"zaman": zaman, "hedef": False}


# --------------------------------------------------------- _en_yakini_bul
def test_en_yakini_bul_tolerans_icinde_esler():
    from datetime import datetime
    zamanlar = [datetime(2024, 1, 1, 0, 0), datetime(2024, 1, 1, 3, 0)]
    kayitlar = [{"id": "a"}, {"id": "b"}]

    sonuc = vb._en_yakini_bul(datetime(2024, 1, 1, 0, 10), zamanlar, kayitlar, 45)
    assert sonuc == {"id": "a"}


def test_en_yakini_bul_tolerans_disinda_none_doner():
    """KRITIK: cok uzak bir gozlem SESSIZCE yanlis eslenmemeli."""
    from datetime import datetime
    zamanlar = [datetime(2024, 1, 1, 0, 0), datetime(2024, 1, 1, 3, 0)]
    kayitlar = [{"id": "a"}, {"id": "b"}]

    sonuc = vb._en_yakini_bul(datetime(2024, 1, 1, 1, 30), zamanlar, kayitlar, 45)
    assert sonuc is None


def test_en_yakini_bul_bos_listede_none_doner():
    from datetime import datetime
    assert vb._en_yakini_bul(datetime(2024, 1, 1), [], [], 45) is None


# --------------------------------------------------------- zenginlestir
def test_zenginlestir_tolerans_icinde_alanlari_ekler(komsu_dosyasi, acik_meteo_dosyasi):
    ltfj = [_ltfj_kayit("2024-01-01T00:05")]

    sonuc = vb.zenginlestir(ltfj, komsu_dosyasi, acik_meteo_dosyasi)

    assert len(sonuc) == 1
    r = sonuc[0]
    assert r["komsu_ltfm_spread"] == 1.0
    assert r["komsu_ltfm_sis"] == 0
    assert r["acik_meteo_temperature_2m"] == 5.0
    assert r["acik_meteo_temperature_925hPa"] == 3.0


def test_zenginlestir_tolerans_disinda_none_birakir(komsu_dosyasi, acik_meteo_dosyasi):
    ltfj = [_ltfj_kayit("2024-01-01T01:30")]   # iki komsu gozlem arasinda, uzak

    sonuc = vb.zenginlestir(ltfj, komsu_dosyasi, acik_meteo_dosyasi)

    assert sonuc[0]["komsu_ltfm_spread"] is None
    assert sonuc[0]["acik_meteo_temperature_2m"] is None


def test_zenginlestir_kaynak_dosya_yoksa_cokmez(tmp_path):
    ltfj = [_ltfj_kayit("2024-01-01T00:00")]
    olmayan_komsu = tmp_path / "yok_komsu.csv.gz"
    olmayan_am = tmp_path / "yok_am.csv.gz"

    sonuc = vb.zenginlestir(ltfj, olmayan_komsu, olmayan_am)

    assert len(sonuc) == 1
    assert sonuc[0]["zaman"] == "2024-01-01T00:00"


def test_zenginlestir_girdi_kaydini_degistirmez(komsu_dosyasi, acik_meteo_dosyasi):
    ltfj = [_ltfj_kayit("2024-01-01T00:00")]
    vb.zenginlestir(ltfj, komsu_dosyasi, acik_meteo_dosyasi)
    assert "komsu_ltfm_spread" not in ltfj[0]


# --------------------------------------------------------- turet
def test_turet_inversiyon_hesaplar():
    kayitlar = [{"acik_meteo_temperature_2m": 5.0, "acik_meteo_temperature_925hPa": 3.0,
                "acik_meteo_temperature_850hPa": 8.0}]
    sonuc = vb.turet(kayitlar)
    assert sonuc[0]["inversiyon_925"] == pytest.approx(2.0)
    assert sonuc[0]["inversiyon_850"] == pytest.approx(-3.0)


def test_turet_eksik_alanda_none_doner_cokmez():
    kayitlar = [{"acik_meteo_temperature_2m": None, "acik_meteo_temperature_925hPa": 3.0}]
    sonuc = vb.turet(kayitlar)
    assert sonuc[0]["inversiyon_925"] is None
