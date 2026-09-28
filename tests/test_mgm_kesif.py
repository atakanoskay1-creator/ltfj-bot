"""mgm_kesif: MGM yanıt sözleşmesi keşfi - salt okunur ve ölçen.

Ağ kullanılmaz; yanıtlar sentetik __NEXT_DATA__ sözlükleridir. Kilitler:
  - yanıt yapısı (üst anahtarlar, veri alanı) uydurulmadan raporlanır;
  - METAR/SPECI sayıları, en eski/en yeni gözlem zamanı, ızgara eksikleri,
    COR ve aynı (zaman, tip) için birden çok kayıt doğru sayılır;
  - betik repo/state/arşiv dosyalarına YAZMAZ;
  - iş akışı salt okunurdur ve commit/push etmez.
"""
from pathlib import Path

import pytest

import mgm_kesif as k

WF = Path(".github/workflows/mgm-kesif.yml").read_text(encoding="utf-8")


def _kayit(zaman, metin, id_=None, **ek):
    d = {"observationTimeNormal": zaman, "observationText": metin}
    if id_ is not None:
        d["id"] = id_
    d.update(ek)
    return d


def _data(listeler: dict, icao="LTFJ"):
    blok = {"istInfo": {"icao": icao}}
    blok.update(listeler)
    return {"props": {"pageProps": {"response": [blok], "selectedObj": {}}},
            "query": {"hours": "24"}, "page": "/result", "buildId": "x"}


KAYITLAR = [
    _kayit("2026-09-28T00:20:00Z", "METAR LTFJ 280020Z 03004KT 9999 NSC 17/16 Q1014", 1),
    _kayit("2026-09-28T00:50:00Z", "METAR LTFJ 280050Z 03004KT 9999 NSC 17/16 Q1014", 2),
    # 01:20 eksik
    _kayit("2026-09-28T01:50:00Z", "METAR LTFJ 280150Z 03004KT 0800 FG 16/16 Q1014", 3),
    _kayit("2026-09-28T01:50:00Z", "METAR COR LTFJ 280150Z 03004KT 0700 FG 16/16 Q1014", 4),
    _kayit("2026-09-28T01:07:00Z", "SPECI LTFJ 280107Z 03004KT 1500 BR 16/16 Q1014", 5),
    _kayit("2026-09-28T00:00:00Z", "TAF LTFJ 272300Z 2800/2906 03005KT 9999 SCT030", 6),
]


def test_liste_ozeti_sayimlar():
    o = k.liste_ozeti(KAYITLAR)
    assert o["kayit"] == 6
    assert o["tipler"] == {"METAR": 4, "SPECI": 1, "TAF": 1}
    assert o["duzeltme"] == {"COR": 1}
    assert o["gozlem_zamani_en_eski"] == "2026-09-28T00:20:00+00:00"
    assert o["gozlem_zamani_en_yeni"] == "2026-09-28T01:50:00+00:00"
    assert o["metar_izgara"] == 4 and o["metar_izgara_disi"] == 0
    assert o["izgara_eksik_slot"] == ["2026-09-28T01:20:00+00:00"]
    assert o["ayni_zaman_tip_birden_cok"] == ["2026-09-28T01:50:00+00:00 METAR ×2"]
    assert o["id_var"] == 6 and o["id_benzersiz"] == 6


def test_SPECI_izgara_slotu_doldurmaz():
    o = k.liste_ozeti([
        _kayit("2026-09-28T00:20:00Z", "METAR LTFJ 280020Z 9999"),
        _kayit("2026-09-28T00:50:00Z", "SPECI LTFJ 280050Z 0800 FG"),
        _kayit("2026-09-28T01:20:00Z", "METAR LTFJ 280120Z 9999"),
    ])
    assert o["izgara_eksik_slot"] == ["2026-09-28T00:50:00+00:00"]


def test_zaman_alanlari_uydurulmadan_listelenir():
    o = k.liste_ozeti([_kayit("2026-09-28T00:20:00Z", "METAR LTFJ 280020Z 9999",
                              receiveTime="2026-09-28T00:24:00Z")])
    assert set(o["zaman_alanlari"]) == {"observationTimeNormal", "receiveTime"}
    assert "receiveTime" in o["ilk_kayit_anahtarlari"]


def test_ozetle_veri_alanini_adiyla_bulur_ve_baska_istasyonu_atlar():
    d = _data({"dataLast": KAYITLAR[:2], "data": KAYITLAR, "baska": [1, 2]})
    d["props"]["pageProps"]["response"].append({"istInfo": {"icao": "LTFM"},
                                                "dataLast": KAYITLAR})
    o = k.ozetle(d, 24)
    assert o["ust_anahtarlar"] == ["buildId", "page", "props", "query"]
    assert o["response_uzunluk"] == 2
    ltfj, ltfm = o["bloklar"]
    assert set(ltfj["listeler"]) == {"dataLast", "data"}      # metin tasiyan listeler
    assert ltfj["listeler"]["data"]["kayit"] == 6
    assert ltfm["icao"] == "LTFM" and ltfm["listeler"] == {}


def test_ozetle_next_data_yoksa_hata():
    assert "hata" in k.ozetle(None, 3)


def test_markdown_karsilastirma_alt_kume():
    o0 = k.ozetle(_data({"dataLast": KAYITLAR[:1]}), 0)
    o24 = k.ozetle(_data({"dataLast": KAYITLAR}), 24)
    md = k.markdown([o0, o24], {0: {}, 24: {}})
    assert "veri alanı `dataLast`" in md
    assert "hours=0 `dataLast` (1) ⊆ hours=24 `dataLast` (5): evet" in md
    assert "düzeltme {'COR': 1}" in md


def test_main_yalniz_stdout_ozet_ve_ham_dizine_yazar(monkeypatch, tmp_path, capsys):
    """Salt okunur: repo dosyalarina yazmaz; yalniz verilen gecici yerlere."""
    monkeypatch.setattr(k, "cek", lambda saat: (_data({"dataLast": KAYITLAR}),
                                                {"url": "u", "http": 200, "bayt": 1,
                                                 "cekim_utc": "t"}))
    ozet = tmp_path / "ozet.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(ozet))
    monkeypatch.chdir(tmp_path)
    ham = tmp_path / "ham"
    assert k.main(["--saat", "0", "24", "--ham-dizin", str(ham)]) == 0
    assert sorted(p.name for p in ham.iterdir()) == ["mgm_hours_0.json", "mgm_hours_24.json"]
    yazilan = {p.name for p in tmp_path.iterdir()}
    assert yazilan == {"ozet.md", "ham"}
    assert "hours=24" in capsys.readouterr().out and "hours=24" in ozet.read_text()


def test_main_ag_hatasinda_diger_saatlere_devam_ve_hata_kodu(monkeypatch, capsys):
    import ltfj_rasat

    def cek(saat):
        if saat == 3:
            raise ltfj_rasat.AgHatasi("zaman asimi")
        return _data({"dataLast": KAYITLAR}), {}

    monkeypatch.setattr(k, "cek", cek)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert k.main(["--saat", "0", "3", "24"]) == 1
    out = capsys.readouterr().out
    assert "AgHatasi: zaman asimi" in out and "## hours=24" in out


def test_cek_ltfj_rasat_parametrelerini_yalniz_hours_degisecek_kullanir(monkeypatch):
    goren = {}

    class Yanit:
        url, status_code, content = "u", 200, b"x"
        text = '<script id="__NEXT_DATA__" type="application/json">{"props": {}}</script>'

    def getir(params, timeout):
        goren["params"] = params
        return Yanit()

    monkeypatch.setattr(k.rasat, "_sayfayi_getir", getir)
    data, meta = k.cek(24)
    assert data == {"props": {}}
    assert goren["params"] == [("stations", "LTFJ"), ("obsType", "1"), ("obsType", "2"),
                               ("hours", "24")]


def test_bot_cekimi_degismedi():
    """PR-1 canli akisa dokunmaz: botun parametreleri hala hours=0."""
    import ltfj_rasat
    assert ltfj_rasat.EK_PARAMS == [("obsType", "1"), ("obsType", "2"), ("hours", "0")]


# ------------------------------------------------------------ is akisi ---
def test_is_akisi_salt_okunur():
    assert "permissions:\n  contents: read" in WF
    for yasak in ("git push", "git commit", "contents: write", "git add"):
        assert yasak not in WF


def test_is_akisi_zamanlanmis_degil_ve_tetikleyiciler_dar():
    assert "schedule" not in WF and "cron" not in WF
    assert "workflow_dispatch:" in WF
    assert 'paths:\n      - "mgm_kesif.py"\n      - ".github/workflows/mgm-kesif.yml"' in WF


def test_is_akisi_kesif_betigini_gecici_dizinle_calistirir():
    assert 'python mgm_kesif.py --ham-dizin "$RUNNER_TEMP/mgm_kesif"' in WF
    assert "actions/upload-artifact@v4" in WF


def test_saniye_alti_kesirli_zaman_izgarada_eksik_sayilmaz():
    """Ilk gercek kesif: MGM zamanlari saniye-alti kesir tasiyor
    (07:20:00.032). Izgara karsilastirmasi dakikaya indirilerek yapilmali;
    aksi halde butun slotlar sahte 'eksik' gorunur."""
    o = k.liste_ozeti([
        _kayit("2026-09-28T06:50:00.845Z", "METAR LTFJ 280650Z 9999"),
        _kayit("2026-09-28T07:20:00.032Z", "METAR LTFJ 280720Z 9999"),
        _kayit("2026-09-28T07:50:00.404Z", "METAR LTFJ 280750Z 9999"),
    ])
    assert o["izgara_eksik_slot"] == []
    assert o["metar_izgara"] == 3 and o["saniye_alti_kesirli_zaman"] == 3


def test_kategorik_alan_dagilimi_ve_tip_capraz_tablosu():
    kay = [_kayit("2026-09-28T00:20:00Z", "METAR LTFJ 280020Z 9999", 1,
                  observationStatus=1, observationType=1),
           _kayit("2026-09-28T00:50:00Z", "METAR COR LTFJ 280050Z 9999", 2,
                  observationStatus=2, observationType=1)]
    o = k.liste_ozeti(kay)
    assert o["kategorik_alanlar"]["observationStatus"] == {"1": 1, "2": 1}
    assert o["tip_x_status_x_type"] == {"METAR / status=1 / type=1": 1,
                                        "METAR / status=2 / type=1": 1}


def test_blok_alan_turleri_bos_listeyi_de_gosterir():
    o = k.ozetle(_data({"dataLast": [], "data": KAYITLAR, "gamet": None}), 24)
    tur = o["bloklar"][0]["alan_turleri"]
    assert tur["dataLast"] == "list(0)" and tur["data"] == "list(6)" and tur["gamet"] == "NoneType"


def test_normal_disi_durumlu_kayitlar_ayrintiyla_listelenir():
    kay = [_kayit("2026-09-28T00:20:00Z", "METAR LTFJ 280020Z 9999", 10, observationStatus=1),
           _kayit("2026-09-28T00:50:00Z", "METAR LTFJ 280050Z 0800 FG", 30,
                  observationStatus=4, observationStatusExplanation="CCA   "),
           _kayit("2026-09-28T01:20:00Z", "METAR LTFJ 280120Z 9999", 20, observationStatus=1)]
    nd = k.liste_ozeti(kay)["normal_disi_kayitlar"]
    assert len(nd) == 1
    assert nd[0]["id"] == 30 and nd[0]["onceki_ayni_tip_id"] == 10 and nd[0]["sonraki_ayni_tip_id"] == 20
    assert nd[0]["aciklama"] == "CCA" and nd[0]["metin"] == "METAR LTFJ 280050Z 0800 FG"
