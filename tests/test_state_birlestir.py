"""state_birlestir.py testleri: alan kaybi olmamasi, bozuk/eksik dosya,
gecmis ve onbellek birlesimi."""
import json

import state_birlestir as sb


def test_oku_olmayan_dosya_bos_dict():
    assert sb.oku(__import__("pathlib").Path("/tmp/__yok_boyle_bir_dosya__.json")) == {}


def test_oku_bozuk_json_bos_dict(tmp_path):
    dosya = tmp_path / "bozuk.json"
    dosya.write_text("{bu gecerli json degil", encoding="utf-8")
    assert sb.oku(dosya) == {}


def test_yeni_olan_guncelleme_damgasina_gore_secer():
    a = {"alan": "eski", "guncelleme": "2026-01-01T00:00:00+00:00"}
    b = {"alan": "yeni", "guncelleme": "2026-01-02T00:00:00+00:00"}
    assert sb.yeni_olan(a, b, "alan") == "yeni"
    assert sb.yeni_olan(b, a, "alan") == "yeni"


def test_yeni_olan_bir_taraf_bos_diger_kullanilir():
    a = {"alan": None, "guncelleme": "2026-01-01T00:00:00+00:00"}
    b = {"alan": "deger", "guncelleme": "2026-01-02T00:00:00+00:00"}
    assert sb.yeni_olan(a, b, "alan") == "deger"
    assert sb.yeni_olan(b, a, "alan") == "deger"


def test_birlestir_tum_alanlari_korur_regresyon():
    """PR gecmisinde bir kez kirilan tam senaryo: son_renk, durum_mesaj_id,
    son_veri_zamani, olcum_gecmisi, yorum_onbellegi hicbiri kaybolmamali."""
    a = {
        "gonderilen": ["id:1", "id:2"], "ilk_calisma": False,
        "son_metar": "METAR A", "son_uyari": None,
        "son_renk": "GRN", "durum_mesaj_id": 111,
        "son_veri_zamani": "2026-01-01T00:00:00+00:00",
        "olcum_gecmisi": [{"zaman": "2026-01-01T00:00:00+00:00", "ruzgar_hiz": 5,
                            "tavan": 3000, "qnh": 1013, "sicaklik": 18}],
        "yorum_onbellegi": {"METAR A": "yorum A"},
        "guncelleme": "2026-01-01T00:00:00+00:00",
    }
    b = {
        "gonderilen": ["id:2", "id:3"], "ilk_calisma": False,
        "son_metar": "METAR B", "son_uyari": None,
        "son_renk": "YLO", "durum_mesaj_id": 222,
        "son_veri_zamani": "2026-01-01T01:00:00+00:00",
        "olcum_gecmisi": [{"zaman": "2026-01-01T01:00:00+00:00", "ruzgar_hiz": 6,
                            "tavan": 2800, "qnh": 1012, "sicaklik": 19}],
        "yorum_onbellegi": {"METAR B": "yorum B"},
        "guncelleme": "2026-01-01T01:00:00+00:00",
    }
    sonuc = sb.birlestir(a, b)

    assert sonuc["son_renk"] == "YLO"          # b daha yeni
    assert sonuc["durum_mesaj_id"] == 222       # b daha yeni
    assert sonuc["son_veri_zamani"] == "2026-01-01T01:00:00+00:00"
    assert len(sonuc["olcum_gecmisi"]) == 2     # ikisi de korunmus
    assert sonuc["yorum_onbellegi"] == {"METAR A": "yorum A", "METAR B": "yorum B"}
    assert sonuc["gonderilen"] == ["id:1", "id:2", "id:3"]  # sira bozulmadan birlesim


def test_birlestir_gonderilen_tekrar_etmez():
    a = {"gonderilen": ["id:1", "id:2"]}
    b = {"gonderilen": ["id:2", "id:1", "id:3"]}
    sonuc = sb.birlestir(a, b)
    assert sonuc["gonderilen"] == ["id:1", "id:2", "id:3"]


def test_birlestir_ilk_calisma_ikisi_de_true_olmali_true_kalsin():
    a = {"ilk_calisma": True}
    b = {"ilk_calisma": True}
    assert sb.birlestir(a, b)["ilk_calisma"] is True


def test_birlestir_ilk_calisma_biri_calismissa_false():
    a = {"ilk_calisma": True}
    b = {"ilk_calisma": False}
    assert sb.birlestir(a, b)["ilk_calisma"] is False


def test_birlestir_olcum_gecmisi_ayni_zaman_damgasi_tekrarlanmaz():
    ortak = {"zaman": "2026-01-01T00:00:00+00:00", "ruzgar_hiz": 5,
              "tavan": 3000, "qnh": 1013, "sicaklik": 18}
    a = {"olcum_gecmisi": [ortak]}
    b = {"olcum_gecmisi": [ortak, {"zaman": "2026-01-01T00:30:00+00:00",
                                    "ruzgar_hiz": 6, "tavan": 2900,
                                    "qnh": 1013, "sicaklik": 18}]}
    sonuc = sb.birlestir(a, b)
    assert len(sonuc["olcum_gecmisi"]) == 2


def test_birlestir_bos_taraflarla_crash_etmez():
    assert sb.birlestir({}, {}) == {
        "gonderilen": [], "ilk_calisma": True, "son_metar": "",
        "son_uyari": None, "son_renk": None, "durum_mesaj_id": None,
        "son_veri_zamani": None, "olcum_gecmisi": [], "yorum_onbellegi": {},
        "guncelleme": "",
    }


def test_ana_akis_dosyadan_dosyaya_birlestirme(tmp_path):
    hedef = tmp_path / "hedef.json"
    digeri = tmp_path / "digeri.json"
    hedef.write_text(json.dumps({"gonderilen": ["id:1"], "son_renk": "BLU",
                                  "guncelleme": "2026-01-01T00:00:00+00:00"}),
                      encoding="utf-8")
    digeri.write_text(json.dumps({"gonderilen": ["id:2"], "son_renk": "GRN",
                                   "guncelleme": "2026-01-01T01:00:00+00:00"}),
                       encoding="utf-8")
    sonuc = sb.birlestir(sb.oku(hedef), sb.oku(digeri))
    hedef.write_text(json.dumps(sonuc, ensure_ascii=False), encoding="utf-8")

    yazilan = json.loads(hedef.read_text(encoding="utf-8"))
    assert yazilan["gonderilen"] == ["id:1", "id:2"]
    assert yazilan["son_renk"] == "GRN"
