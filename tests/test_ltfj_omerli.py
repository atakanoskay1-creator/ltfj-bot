"""ltfj_omerli.py - Omerli istasyonlari ileriye donuk kaydi (ag YOK, sahte oturum)."""
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

import ltfj_omerli as om

SIMDI = datetime(2026, 10, 1, 11, 36, tzinfo=timezone.utc)
# PR #133 kesif ciktisindaki gercek yanitlar (kisaltilmis)
CEKMEKOY = {"istNo": 18397, "sicaklik": 15.4, "nem": 80, "ruzgarYon": 23, "ruzgarHiz": 6.48,
            "aktuelBasinc": 1013.6, "gorus": -9999, "veriZamani": "2026-10-01T11:34:00.000Z"}
BARAJ = {"istNo": 18736, "sicaklik": 17.5, "nem": 89, "ruzgarYon": -9999, "ruzgarHiz": -9999,
         "aktuelBasinc": -9999, "veriZamani": "2026-10-01T11:34:00.000Z"}


class _Yanit:
    def __init__(self, veri, durum=200):
        self.veri, self.durum = veri, durum

    def raise_for_status(self):
        if self.durum >= 400:
            raise requests.HTTPError(f"{self.durum}")

    def json(self):
        return self.veri


class _Oturum:
    def __init__(self, yanitlar):
        self.yanitlar, self.cagrilar = yanitlar, []

    def get(self, url, params=None, headers=None, timeout=None):
        self.cagrilar.append((url, params, timeout))
        y = self.yanitlar[params["istno"]]
        if isinstance(y, Exception):
            raise y
        return y


@pytest.mark.parametrize("t,rh,beklenen", [
    (15.4, 80, 12.0), (17.5, 89, 15.7), (10.0, 100, 10.0),
    (None, 80, None), (15.0, None, None), (15.0, 0, None),
])
def test_ciy_noktasi(t, rh, beklenen):
    assert om.ciy_noktasi(t, rh) == beklenen


@pytest.mark.parametrize("z,beklenen", [
    (datetime(2026, 10, 1, 11, 34, 59, tzinfo=timezone.utc), "2026-10-01T11:30"),
    (datetime(2026, 10, 1, 11, 40, tzinfo=timezone.utc), "2026-10-01T11:40"),
    (datetime(2026, 10, 1, 14, 9, tzinfo=om.timezone(om.timedelta(hours=3))), "2026-10-01T11:00"),
])
def test_dilim_utc_ve_10_dakika(z, beklenen):
    assert om.dilim(z) == beklenen


def test_satir_kur_eksik_degerler_bos_ve_cig_hesaplanir():
    s = om.satir_kur(BARAJ, SIMDI)
    assert s["zaman"] == "2026-10-01T11:30" and s["ist_no"] == "18736"
    assert (s["sicaklik"], s["nem"], s["ciy"]) == (17.5, 89.0, 15.7)
    assert s["ruzgar_yon"] is None and s["ruzgar_hiz_kmh"] is None and s["basinc"] is None
    s = om.satir_kur(CEKMEKOY, SIMDI)
    assert (s["ruzgar_yon"], s["ruzgar_hiz_kmh"], s["basinc"]) == (23, 6.5, 1013.6)


def test_satir_kur_bayat_veya_zamansiz_kaydi_atar():
    assert om.satir_kur({**CEKMEKOY, "veriZamani": "2026-10-01T09:00:00.000Z"}, SIMDI) is None
    assert om.satir_kur({**CEKMEKOY, "veriZamani": None}, SIMDI) is None
    assert om.satir_kur({**CEKMEKOY, "sicaklik": -9999, "nem": -9999}, SIMDI) is None


def test_kosu_ekler_ve_ayni_dilimde_ilk_kayit_kalir(tmp_path):
    dosya = tmp_path / "omerli.csv"
    oturum = _Oturum({18736: _Yanit([BARAJ]), 18397: _Yanit([CEKMEKOY])})
    assert om.kosu(dosya, SIMDI, oturum) == 2
    assert all(t == om.ZAMAN_ASIMI_SN for _, _, t in oturum.cagrilar)
    # ayni 10 dk diliminde degisen deger -> satir DEGISMEZ
    oturum2 = _Oturum({18736: _Yanit([{**BARAJ, "nem": 95, "veriZamani": "2026-10-01T11:38:00Z"}]),
                       18397: _Yanit([CEKMEKOY])})
    assert om.kosu(dosya, SIMDI, oturum2) == 0
    satirlar = om.oku(dosya)
    assert [(s["zaman"], s["ist_no"], s["nem"]) for s in satirlar] == \
        [("2026-10-01T11:30", "18397", "80.0"), ("2026-10-01T11:30", "18736", "89.0")]
    assert Path(dosya).read_text(encoding="utf-8").splitlines()[0] == ",".join(om.SUTUNLAR)


def test_kosu_fail_open_biri_duserse_digeri_kaydedilir(tmp_path, capsys):
    dosya = tmp_path / "omerli.csv"
    oturum = _Oturum({18736: requests.ReadTimeout("zaman asimi"), 18397: _Yanit([CEKMEKOY])})
    assert om.kosu(dosya, SIMDI, oturum) == 1
    assert "18736" in capsys.readouterr().err
    oturum = _Oturum({18736: _Yanit({}, 503), 18397: _Yanit([])})
    assert om.kosu(tmp_path / "bos.csv", SIMDI, oturum) == 0
    assert not (tmp_path / "bos.csv").exists()


def test_main_hata_yutar(monkeypatch, tmp_path, capsys):
    def patla(*a, **k):
        raise RuntimeError("beklenmedik")
    monkeypatch.setattr(om, "kosu", patla)
    assert om.main(["--dosya", str(tmp_path / "x.csv")]) == 0
    assert "atlandı" in capsys.readouterr().err


def test_birlestir_once_kaydedilen_kalir_simetrik(tmp_path):
    a = [{"zaman": "2026-10-01T11:30", "ist_no": "18736", "nem": "89", "kayit_zamani": "2026-10-01T11:36:00Z"}]
    b = [{"zaman": "2026-10-01T11:30", "ist_no": "18736", "nem": "95", "kayit_zamani": "2026-10-01T11:39:00Z"},
         {"zaman": "2026-10-01T11:40", "ist_no": "18736", "nem": "90", "kayit_zamani": "2026-10-01T11:44:00Z"}]
    assert om.birlestir(a, b) == om.birlestir(b, a)
    assert sorted((s["zaman"], s["nem"]) for s in om.birlestir(a, b)) == \
        [("2026-10-01T11:30", "89"), ("2026-10-01T11:40", "90")]
    disk, bizim = tmp_path / "disk.csv", tmp_path / "bizim.csv"
    om.yaz(a, disk)
    om.yaz(b, bizim)
    assert om.main(["--dosya", str(disk), "--birlestir-bizim", str(bizim)]) == 0
    assert [s["nem"] for s in om.oku(disk)] == ["89", "90"]


WF = Path(".github/workflows/ltfj.yml").read_text(encoding="utf-8")


def test_is_akisi_kaydeder_hatayi_yutar_ve_cakismada_birlestirir():
    assert "omerli_gozlem.csv" in WF.split("DOSYALAR=")[1].split("\n")[0]
    adim = WF.split("Omerli istasyonlarini kaydet")[1].split("- name:")[0]
    assert "continue-on-error: true" in adim and "python -m ltfj_omerli" in adim
    # bot adimindan SONRA, commit adimindan ONCE
    assert WF.index("python ltfj_bot.py") < WF.index("python -m ltfj_omerli\n") \
        < WF.index("State ve sayfayi repoya geri yaz")
    # yedek reset'ten ONCE, birlestirme reset'ten SONRA
    assert WF.index("cp omerli_gozlem.csv /tmp/bizim_omerli_gozlem.csv") \
        < WF.index('git reset --hard "origin/${DAL}"') \
        < WF.index("python -m ltfj_omerli --birlestir-bizim /tmp/bizim_omerli_gozlem.csv")


def test_bot_ve_sayfa_omerli_kaydini_okumaz():
    for dosya in ("ltfj_bot.py", "ltfj_sayfa.py", "ltfj_sis_olasilik.py"):
        assert "omerli" not in Path(dosya).read_text(encoding="utf-8").lower()
