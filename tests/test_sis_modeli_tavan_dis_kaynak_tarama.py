"""sis_modeli/tavan_dis_kaynak_tarama.py testleri.

Ağır bir istatistiksel doğrulama değil - amaç uçtan uca akışın (LTFJ arşivi
+ dış kaynaklar -> zenginleştirme -> WoE taraması) ÇÖKMEDEN çalıştığını ve
eksik dosya durumunda açık/anlaşılır bir hatayla çıktığını doğrulamak."""
import csv
import gzip
from pathlib import Path

import pytest

from sis_modeli import tavan_dis_kaynak_tarama as tdkt


def _ltfj_gz_yaz(yol: Path, n=60):
    """REJIM_ILK_YIL (2017) sonrasi, tavan.hazirla()'nin isleyebilecegi
    minimal gecerli bir arsiv - ozellik.SUTUNLAR semasiyla uyumlu."""
    satirlar = []
    for i in range(n):
        gun = 1 + (i % 27)
        saat = (i * 30 // 60) % 24
        dk = "00" if i % 2 == 0 else "30"
        dusuk = i % 10 == 0
        satirlar.append({
            "zaman": f"2020-01-{gun:02d}T{saat:02d}:{dk}", "ay": 1, "saat": saat,
            "sicaklik": 5, "cig_noktasi": 3, "spread": 2,
            "ruzgar_hiz": 5, "ruzgar_yon": 180,
            "gorus": 400 if dusuk else 9999,
            "tavan": 300 if dusuk else 3000,
            "qnh": 1013, "hava": "", "sis_kodu": 0,
            "sis": int(dusuk), "lvo": 0,
        })
    yol.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(yol, "wt", encoding="utf-8", newline="") as f:
        yazici = csv.DictWriter(f, fieldnames=list(satirlar[0].keys()))
        yazici.writeheader()
        yazici.writerows(satirlar)


def _dis_kaynak_gz_yaz(yol: Path, alanlar: dict, n=60):
    satirlar = []
    for i in range(n):
        gun = 1 + (i % 27)
        saat = (i * 30 // 60) % 24
        satir = {"zaman": f"2020-01-{gun:02d}T{saat:02d}:00"}
        satir.update(alanlar)
        satirlar.append(satir)
    yol.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(yol, "wt", encoding="utf-8", newline="") as f:
        yazici = csv.DictWriter(f, fieldnames=list(satirlar[0].keys()))
        yazici.writeheader()
        yazici.writerows(satirlar)


@pytest.fixture
def dosyalar(tmp_path):
    ltfj = tmp_path / "ltfj_ozellik.csv.gz"
    komsu = tmp_path / "komsu_ltfm_ozellik.csv.gz"
    acik_meteo = tmp_path / "acik_meteo_ltfj.csv.gz"
    _ltfj_gz_yaz(ltfj)
    _dis_kaynak_gz_yaz(komsu, {"spread": "1", "sis": "0", "gorus": "9999", "tavan": ""})
    _dis_kaynak_gz_yaz(acik_meteo, {
        "temperature_2m": "5.0", "relative_humidity_2m": "80",
        "wind_speed_10m": "5.0", "cloud_cover_low": "10",
        "temperature_925hPa": "", "temperature_850hPa": "",
    })
    return ltfj, komsu, acik_meteo


def test_uctan_uca_cokmez_basariyla_biter(dosyalar, capsys):
    ltfj, komsu, acik_meteo = dosyalar
    kod = tdkt.main(["--veri", str(ltfj), "--komsu", str(komsu),
                     "--acik-meteo", str(acik_meteo)])
    assert kod == 0
    cikti = capsys.readouterr().out
    assert "Geliştirme evreni" in cikti


def test_bos_basinc_seviyesi_kova_kurulamadi_diye_raporlanir_cokmez(dosyalar, capsys):
    """UCUNCU BULGU: basinc seviyesi alanlari gercek veride hep bos geliyor -
    bu durumun cokme yerine acik bir mesajla raporlandigini dogrular."""
    ltfj, komsu, acik_meteo = dosyalar
    kod = tdkt.main(["--veri", str(ltfj), "--komsu", str(komsu),
                     "--acik-meteo", str(acik_meteo)])
    assert kod == 0
    cikti = capsys.readouterr().out
    assert "inversiyon_925" in cikti
    assert "kova kurulamadı" in cikti


def test_ltfj_arsivi_yoksa_hata_ile_cikar(tmp_path, capsys):
    kod = tdkt.main(["--veri", str(tmp_path / "yok.csv.gz")])
    assert kod == 1
    assert "yok" in capsys.readouterr().err.lower()


def test_dis_kaynak_eksikse_hata_ile_cikar(dosyalar, tmp_path, capsys):
    ltfj, komsu, acik_meteo = dosyalar
    kod = tdkt.main(["--veri", str(ltfj), "--komsu", str(tmp_path / "yok.csv.gz"),
                     "--acik-meteo", str(acik_meteo)])
    assert kod == 1
    assert "eksik" in capsys.readouterr().err.lower()


def test_adaylar_veri_birlestir_turet_alanlariyla_tutarli():
    """ADAYLAR listesindeki her alan, turet()'in urettigi anahtarlarin bir
    alt kumesi olmali - yazim hatasi sessizce hicbir sey taramamasin."""
    from sis_modeli import veri_birlestir
    ornek = veri_birlestir.turet([{
        "acik_meteo_temperature_2m": 1.0, "acik_meteo_temperature_925hPa": 1.0,
        "acik_meteo_temperature_850hPa": 1.0, "acik_meteo_relative_humidity_2m": 1,
        "acik_meteo_wind_speed_10m": 1, "acik_meteo_cloud_cover_low": 1,
        "komsu_ltfm_sis": 0, "komsu_ltfm_lvo": 0, "komsu_ltfm_tavan": 1,
        "komsu_ltfm_gorus": 1,
    }])[0]
    for alan in tdkt.ADAYLAR:
        assert alan in ornek
