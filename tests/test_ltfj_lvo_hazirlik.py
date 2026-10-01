"""bot/ltfj_lvo_hazirlik.py - QV3 golge modu.

EN ONEMLI TEST: canli girdi hesabi ve agac tahmini, EGITIM HATTININ
KENDISIYLE (sis_modeli: ozellik_cikar -> hedef.hazirla -> qv3_model.aday_ekle
-> qv3_gbm) ayni girdileri ve ayni olasiligi vermeli. Bot sis_modeli'ni
import etmedigi icin kod iki yerde; bu test ikisini birbirine kilitler."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import ltfj_gozlem_arsivi as ga
import ltfj_lvo_hazirlik as lh
from ltfj_analiz import metar_coz
from sis_modeli import hedef, qv3_gbm, qv3_hedef, qv3_model, veri_cek_rvr
from sis_modeli.ozellik import ozellik_cikar

T0 = datetime(2025, 1, 14, 0, 20, tzinfo=timezone.utc)
# 30 dakikalik rutin METAR dizisi: KD ruzgar, dusen spread, BR -> BCFG + RVR,
# VRB ruzgar, eksik QNH, CAVOK - egilim ve kodlarin hepsi calissin.
METINLER = [
    "LTFJ 140020Z 03006KT 9999 FEW030 08/05 Q1021 NOSIG",
    "LTFJ 140050Z 03005KT 9999 FEW030 07/05 Q1021 NOSIG",
    "LTFJ 140120Z 04005KT 8000 NSC 07/05 Q1021 NOSIG",
    "LTFJ 140150Z VRB02KT 6000 BR NSC 06/05 Q1021 NOSIG",
    "LTFJ 140220Z 03004KT 5000 BR NSC 06/05 Q1021 NOSIG",
    "LTFJ 140250Z 04005KT 4000 BR SCT003 06/05 Q1020 NOSIG",
    "LTFJ 140320Z 04006KT 3000 R24L/1100N R06R/P2000N BCFG BR SCT002 05/05 Q1020 BECMG 0800 FG",
    "LTFJ 140350Z 03005KT 9999 R24L/0900D BCFG BKN003 05/05 NOSIG",
    "LTFJ 140420Z 03004KT CAVOK 05/04 Q1021 NOSIG",
]
ZAMANLAR = [T0 + timedelta(minutes=30 * i) for i in range(len(METINLER))]


@pytest.fixture(scope="module")
def gbm():
    return lh.model_oku()


def _egitim_hatti(n):
    """Ilk n METAR icin egitimdeki satirlar (aday_ekle sonrasi)."""
    satirlar = [s for s in (ozellik_cikar(m, z) for m, z in zip(METINLER[:n], ZAMANLAR[:n])) if s]
    rvr = [{"zaman": z.strftime("%Y-%m-%dT%H:%M"),
            **{k: "" if v is None else str(v) for k, v in veri_cek_rvr.rvr_cikar(m).items()}}
           for m, z in zip(METINLER[:n], ZAMANLAR[:n])]
    qv3_hedef.etiketle(qv3_hedef.rvr_birlestir(satirlar, rvr))
    return qv3_model.aday_ekle(hedef.hazirla(satirlar, etiket="hazirlik"))


def _arsiv(n, tmp_path):
    """Botun gozlem_arsivi.csv'si: ayni METAR'lar, CSV'ye yazilip okunmus."""
    satirlar = [ga._satir_kur({"zaman": z, "tip": "METAR"}, metar_coz(m))
                for m, z in zip(METINLER[:n], ZAMANLAR[:n])]
    yol = tmp_path / "gozlem_arsivi.csv"
    ga.yaz(satirlar, yol)
    return ga.oku(yol)


@pytest.mark.parametrize("n", range(1, len(METINLER) + 1))
def test_canli_girdiler_ve_olasilik_egitim_hattiyla_ayni(n, gbm, tmp_path):
    egitim = _egitim_hatti(n)[-1]
    canli = lh.ozellikler(METINLER[n - 1], ZAMANLAR[n - 1], _arsiv(n, tmp_path))
    for alan in gbm["model"]["alanlar"]:
        e, c = egitim.get(alan), canli.get(alan)
        assert (e is None and c is None) or e == pytest.approx(c), alan
    beklenen_ham = qv3_gbm.olasilik(gbm["model"], egitim)
    beklenen = qv3_gbm.platt_uygula(beklenen_ham, gbm["platt"])
    p, ham = lh.olasilik(gbm, canli)
    assert ham == pytest.approx(beklenen_ham, rel=1e-12)
    assert p == pytest.approx(beklenen, rel=1e-12)


@pytest.mark.parametrize("metin", METINLER + [
    "METAR LTFJ 140350Z 03005KT 0300 R06/M0050 R24/0600V1000U FG VV001 05/05 Q1020=",
    "LTFJ 140350Z 03005KT 9999 NSC 05/05 Q1020 TEMPO 0400 R24L/0300 FG",
])
def test_rvr_cikar_egitimdekiyle_ayni(metin):
    beklenen = veri_cek_rvr.rvr_cikar(metin)
    assert lh.rvr_cikar(metin) == {k: beklenen[k] for k in ("rvr_06", "rvr_24", "rvr_min")}


def test_hazirlik_suruyorsa_olasilik_yazilmaz(gbm, tmp_path):
    # 03:50: RVR 900 ama BKN003 -> tavan 300 ft, sart yok; ayni satir RVR 700 olsa sart var
    rapor = {"tip": "METAR", "zaman": ZAMANLAR[7],
             "metin": METINLER[7].replace("R24L/0900D", "R24L/0700D")}
    s = lh.tahmin(rapor, _arsiv(7, tmp_path), gbm)
    assert s["durum"] == "hazirlik_suruyor" and s["olasilik"] == "" and s["rvr_min"] == 700
    rapor = {"tip": "METAR", "zaman": ZAMANLAR[7], "metin": METINLER[7]}
    s = lh.tahmin(rapor, _arsiv(7, tmp_path), gbm)
    assert s["durum"] == "onset" and 0 < float(s["olasilik"]) < 1


def test_speci_ve_eksik_metar_degerlendirilmez(gbm):
    assert lh.tahmin({"tip": "SPECI", "zaman": ZAMANLAR[0], "metin": METINLER[0]}, [], gbm) is None
    assert lh.tahmin({"tip": "METAR", "zaman": ZAMANLAR[0],
                      "metin": "LTFJ 140020Z 03006KT 9999 FEW030 Q1021"}, [], gbm) is None


def test_kosu_en_yeni_metari_bir_kez_kaydeder(tmp_path, monkeypatch):
    (tmp_path / "sis_modeli" / "veri").mkdir(parents=True)
    (tmp_path / "sis_modeli" / "veri" / "qv3_donmus.json").write_text(
        lh.MODEL_DOSYASI.read_text(encoding="utf-8"), encoding="utf-8")
    _arsiv(5, tmp_path)
    raporlar = [{"tip": "METAR", "zaman": ZAMANLAR[4], "metin": METINLER[4]},
                {"tip": "SPECI", "zaman": ZAMANLAR[4] + timedelta(minutes=10), "metin": METINLER[4]},
                {"tip": "METAR", "zaman": ZAMANLAR[3], "metin": METINLER[3]}]
    s = lh.kosu(raporlar, tmp_path)
    assert s["gozlem_zaman"] == ZAMANLAR[4].isoformat() and s["durum"] == "onset"
    assert lh.kosu(raporlar, tmp_path) is None            # ayni gozlem tekrar yazilmaz
    satirlar = lh.oku(tmp_path / lh.DOSYA_ADI)
    assert len(satirlar) == 1 and satirlar[0]["model"].startswith("qv3-gbm-")


def test_birlestir_once_kaydedilen_kalir(tmp_path):
    a = [{"gozlem_zaman": "x", "kayit_zamani": "2026-10-01T10:00:00+00:00", "olasilik": "0.1"}]
    b = [{"gozlem_zaman": "x", "kayit_zamani": "2026-10-01T10:05:00+00:00", "olasilik": "0.2"},
         {"gozlem_zaman": "y", "kayit_zamani": "2026-10-01T10:05:00+00:00", "olasilik": "0.3"}]
    assert lh.birlestir(a, b) == lh.birlestir(b, a)
    assert sorted((s["gozlem_zaman"], s["olasilik"]) for s in lh.birlestir(a, b)) == \
        [("x", "0.1"), ("y", "0.3")]
    disk, bizim = tmp_path / "d.csv", tmp_path / "b.csv"
    lh.yaz(a, disk)
    lh.yaz(b, bizim)
    assert lh.main(["--dosya", str(disk), "--birlestir-bizim", str(bizim)]) == 0
    assert [s["olasilik"] for s in lh.oku(disk)] == ["0.1", "0.3"]


def test_dondurulmus_model_degismedi(gbm):
    """Golge mod holdout'ta test edilen modeli kullanir; dosya degisirse
    bu test bilerek kirilir."""
    assert gbm["agac"] == 50 and len(gbm["model"]["agaclar"]) == 50
    assert gbm["platt"] == pytest.approx([1.026, -0.113], abs=5e-4)


def test_sayfa_ve_bildirim_golge_modu_kullanmaz():
    for dosya in ("ltfj_sayfa.py", "ltfj_panel.py", "ltfj_push.py"):
        assert "ltfj_lvo_hazirlik" not in Path("bot", dosya).read_text(encoding="utf-8")
    kaynak = Path("bot/ltfj_lvo_hazirlik.py").read_text(encoding="utf-8")
    assert "sis_modeli" not in "\n".join(l for l in kaynak.splitlines()
                                         if l.startswith(("import", "from")))


def test_bot_golge_modu_fail_open_ve_tahmin_gunlugunden_sonra_cagirir():
    kaynak = Path("bot/ltfj_bot.py").read_text(encoding="utf-8")
    govde = kaynak[kaynak.index("def main():"):]
    assert govde.index("kosu_isle(") < govde.index("ltfj_tahmin_gunlugu.kaydet(") \
        < govde.index("ltfj_lvo_hazirlik.kosu(raporlar, KLASOR)")
    blok = govde[govde.index("import ltfj_lvo_hazirlik"):]
    assert blok.index("except Exception") < blok.index("sayfa_yaz(")


def test_is_akisi_golge_gunlugunu_commit_eder_ve_cakismada_birlestirir():
    wf = Path(".github/workflows/ltfj.yml").read_text(encoding="utf-8")
    assert "lvo_hazirlik_gunlugu.csv" in wf.split("DOSYALAR=")[1].split("\n")[0]
    assert wf.index("cp lvo_hazirlik_gunlugu.csv /tmp/bizim_lvo_hazirlik_gunlugu.csv") \
        < wf.index('git reset --hard "origin/${DAL}"') \
        < wf.index("python bot/ltfj_lvo_hazirlik.py --birlestir-bizim /tmp/bizim_lvo_hazirlik_gunlugu.csv")
