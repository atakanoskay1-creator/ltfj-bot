"""arsiv_oynat: PR-2 dogrulama betigi - SALT OKUNUR.

Kilitler: kaynak klasordeki arsiv katmanlarina YAZMAZ; H24 islemesini
gecici kopyada yapar; backfill_kurtarilan'i durum gecisi olarak, kontrol
anahtarlarini once/sonra ve idempotency'yi raporlar. Yanitlar sentetik.
"""
import json

import arsiv_oynat as o
import ltfj_gozlem_arsivi as ga
from ltfj_analiz import metar_coz


def _mgm(zaman_ham, metin, id_, status=1, aciklama="NORMAL"):
    return {"id": id_, "observationStatus": status, "observationStatusExplanation": aciklama,
            "observationText": metin, "observationTimeNormal": zaman_ham,
            "observationType": 4, "observationTypeExplanation": "SATU",
            "stationIcaoCode": "LTFJ", "stationNO": 0}


def _json(tmp_path, kayitlar):
    p = tmp_path / "mgm_hours_24.json"
    p.write_text(json.dumps({"props": {"pageProps": {"response": [
        {"istInfo": {"icao": "LTFJ"}, "data": kayitlar, "dataLast": None, "gamet": []}]}}}))
    return p


def _hazirla(tmp_path):
    klasor = tmp_path / "repo"
    klasor.mkdir()
    # canli arsiv: 06:20 (eski baslik, ham metin yok) ve 07:20 var; 06:50 yok
    ga._csv_yaz([{"zaman": "2026-09-28T06:20:00+00:00", "tip": "METAR", "gorus": "6000",
                  "tavan": "", "sicaklik": "18", "cig_noktasi": "16", "ruzgar_yon": "20",
                  "ruzgar_hiz": "9", "qnh": "1014", "hava": "-SHRA", "cavok": "0"},
                 {"zaman": "2026-09-28T07:20:00+00:00", "tip": "METAR", "gorus": "9999",
                  "sicaklik": "18", "cig_noktasi": "16", "ruzgar_yon": "20",
                  "ruzgar_hiz": "9", "qnh": "1014", "cavok": "0"}],
                ga.SUTUNLAR[:12], klasor / "gozlem_arsivi.csv")
    js = _json(tmp_path, [
        _mgm("2026-09-28T06:20:00.309Z", "METAR LTFJ 280620Z 02009KT 6000 -SHRA SCT009 "
             "BKN025 18/16 Q1014", 55274848, 4, "CCA   "),
        _mgm("2026-09-28T06:50:00.845Z", "METAR LTFJ 280650Z 02009KT 9999 18/16 Q1014",
             55281077),
        _mgm("2026-09-28T07:20:00.032Z", "METAR LTFJ 280720Z 02009KT 9999 18/16 Q1014",
             55289417)])
    return klasor, js


def test_kaynak_klasore_YAZMAZ_ve_rapor_uretir(tmp_path, capsys):
    klasor, js = _hazirla(tmp_path)
    once = {p.name: p.read_bytes() for p in klasor.iterdir()}
    kod = o.main(["--json", str(js), "--alinma", "2026-09-28T09:35:54Z",
                  "--klasor", str(klasor),
                  "--kontrol", "2026-09-28T06:50 METAR", "--kontrol", "2026-09-28T06:20 METAR"])
    assert kod == 0
    assert {p.name: p.read_bytes() for p in klasor.iterdir()} == once
    out = capsys.readouterr().out
    assert "2026-09-28T06:50:00+00:00 METAR" in out
    assert "idempotency" in out and "evet" in out
    assert "\"CCA   \"" in out                               # ham aciklama gorunur


def test_oynat_durum_gecisi_ve_kontroller(tmp_path):
    klasor, js = _hazirla(tmp_path)
    data = json.loads(js.read_text())
    import ltfj_rasat as rasat
    raporlar = rasat.raporlari_ayikla(data, "LTFJ", 24)
    tmp = tmp_path / "calisma"
    o.katmanlari_kopyala(klasor, tmp)
    alinma = o._zaman("2026-09-28T09:35:54Z")
    r = o.oynat(raporlar, alinma, alinma, tmp,
                [o._kontrol_anahtari("2026-09-28T06:50 METAR"),
                 o._kontrol_anahtari("2026-09-28T06:20 METAR")], metar_coz)
    k650, k620 = r["kontroller"]
    assert r["isleme"]["eklenen_anahtarlar"] == ["2026-09-28T06:50:00+00:00 METAR"]
    assert (k650["once_kanonikte"], k650["sonra_kanonikte"], k650["backfill_kurtarilan"]) == \
        (False, True, True)
    assert (k650["slot_once"], k650["slot_sonra"]) == ("bekleniyor", None)
    assert k650["surumler"][0]["zaman_ham"] == "2026-09-28T06:50:00.845Z"
    assert k650["surumler"][0]["mgm_id"] == "55281077"
    # kanonik icerik degismedi (yalnizca baslik iki bos sutunla genisledi)
    assert ga._deger_demeti(k620["kanonik_once"], ga.SUTUNLAR) == \
        ga._deger_demeti(k620["kanonik_sonra"], ga.SUTUNLAR)
    assert k620["backfill_kurtarilan"] is False and k620["ayristirma_farkli"] is True
    assert k620["surumler"][0]["mgm_status_aciklama"] == "CCA   "
    assert r["idempotent"] is True


def test_kontrol_anahtari_bicimi():
    assert o._kontrol_anahtari("2026-09-27T16:20 METAR") == ("2026-09-27T16:20:00+00:00",
                                                            "METAR")
