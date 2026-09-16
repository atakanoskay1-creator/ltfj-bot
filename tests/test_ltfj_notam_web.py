"""ltfj_notam.notam_veri_yaz(): web katmani icin ayri JSON dosyasi.

MOD 3/MOD 5 ayrimi: "aktif" SADECE en son senkronda NOTAC'in gercekten
dondurdugu kayitlar (last_seen == notam_son_senkron VE status=='active'),
"gecmis" ise botun BUGUNE KADAR gordugu TUM yerel kayitlar - bunlarin
NOTAC'in tam arsivi OLMADIGI (sadece botun gordugu) testlerle sabitleniyor."""
import json

import ltfj_notam as nm


def test_bos_state_gecerli_bos_yapisi_uretir(tmp_path):
    hedef = tmp_path / "notam_veri.json"
    nm.notam_veri_yaz({}, hedef)
    veri = json.loads(hedef.read_text(encoding="utf-8"))
    assert veri["istasyon"] == "LTFJ"
    assert veri["kaynak"] == "NOTAC"
    assert veri["son_senkron"] is None
    assert veri["aktif"] == []
    assert veri["gecmis"] == []
    assert "Bilgi amaçlıdır" in veri["bilgi_uyarisi"]


def test_son_senkronla_eslesen_aktif_kayit_aktif_listesine_girer(tmp_path):
    son_senkron = "2026-09-16T12:00:00+00:00"
    state = {
        "notam_son_senkron": son_senkron,
        "notam_gecmisi": {
            "abc": {
                "id": "abc", "number": "B1/26", "status": "active",
                "first_seen": "2026-09-01T00:00:00+00:00",
                "last_seen": son_senkron, "last_active": son_senkron,
            },
        },
    }
    hedef = tmp_path / "notam_veri.json"
    nm.notam_veri_yaz(state, hedef)
    veri = json.loads(hedef.read_text(encoding="utf-8"))
    assert [k["id"] for k in veri["aktif"]] == ["abc"]
    assert [k["id"] for k in veri["gecmis"]] == ["abc"]


def test_son_senkronda_gorunmeyen_kayit_gecmiste_kalir_aktifte_kalmaz(tmp_path):
    son_senkron = "2026-09-16T12:00:00+00:00"
    state = {
        "notam_son_senkron": son_senkron,
        "notam_gecmisi": {
            "dusen": {
                "id": "dusen", "number": "B2/26", "status": "active",
                "first_seen": "2026-09-01T00:00:00+00:00",
                # onceki senkronda gorulmus ama SON senkronda degil -
                # aktif listeden dustu, ama yerel gecmisten SILINMEDI.
                "last_seen": "2026-09-15T00:00:00+00:00",
                "last_active": "2026-09-15T00:00:00+00:00",
            },
        },
    }
    hedef = tmp_path / "notam_veri.json"
    nm.notam_veri_yaz(state, hedef)
    veri = json.loads(hedef.read_text(encoding="utf-8"))
    assert veri["aktif"] == []
    assert [k["id"] for k in veri["gecmis"]] == ["dusen"]


def test_status_active_degilse_aktif_listesine_girmez(tmp_path):
    son_senkron = "2026-09-16T12:00:00+00:00"
    state = {
        "notam_son_senkron": son_senkron,
        "notam_gecmisi": {
            "iptal": {
                "id": "iptal", "number": "B3/26", "status": "withdrawn",
                "first_seen": "2026-09-01T00:00:00+00:00",
                "last_seen": son_senkron, "last_active": "2026-09-10T00:00:00+00:00",
            },
        },
    }
    hedef = tmp_path / "notam_veri.json"
    nm.notam_veri_yaz(state, hedef)
    veri = json.loads(hedef.read_text(encoding="utf-8"))
    assert veri["aktif"] == []
    assert [k["id"] for k in veri["gecmis"]] == ["iptal"]


def test_gecmis_last_seen_e_gore_azalan_siralanir(tmp_path):
    state = {
        "notam_son_senkron": "2026-09-16T12:00:00+00:00",
        "notam_gecmisi": {
            "eski": {"id": "eski", "last_seen": "2026-09-01T00:00:00+00:00", "status": "active"},
            "yeni": {"id": "yeni", "last_seen": "2026-09-16T12:00:00+00:00", "status": "active"},
            "orta": {"id": "orta", "last_seen": "2026-09-10T00:00:00+00:00", "status": "active"},
        },
    }
    hedef = tmp_path / "notam_veri.json"
    nm.notam_veri_yaz(state, hedef)
    veri = json.loads(hedef.read_text(encoding="utf-8"))
    assert [k["id"] for k in veri["gecmis"]] == ["yeni", "orta", "eski"]


def test_hicbir_zaman_senkron_edilmemisse_aktif_bos(tmp_path):
    state = {
        "notam_son_senkron": None,
        "notam_gecmisi": {
            "x": {"id": "x", "last_seen": "2026-09-16T12:00:00+00:00", "status": "active"},
        },
    }
    hedef = tmp_path / "notam_veri.json"
    nm.notam_veri_yaz(state, hedef)
    veri = json.loads(hedef.read_text(encoding="utf-8"))
    assert veri["aktif"] == []
