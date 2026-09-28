"""NOTAMC ile iptal edilen NOTAM'lar.

Istenen davranis: aktif NOTAM'lardan birine NOTAMC gelirse o NOTAM
"iptal edildi" olarak isaretlenir, aktif (ve yaklasan) listeden cikip
gecmis kayitlara duser; iptal tarihi yazilir.

Kilitlenenler:
  - eslestirme YALNIZCA NOTAMC'nin kendi metnindeki numarayla (ilgili_notam)
    ve ayni lokasyonda; numara yoksa ya da hedef gecmiste yoksa HICBIR SEY
    isaretlenmez (tahmin yok);
  - iptal zamani NOTAMC'nin B) alani (effective_start), yoksa notam_issued;
  - NOTAC'tan gelen alanlara (status dahil) dokunulmaz;
  - isaret sonraki senkronlarda ve state birlestirmede KAYBOLMAZ;
  - sayfa iptal edileni aktif listeden cikarir, gecmiste tarihiyle gosterir.

Gercek ornek (28.09 state'i): B3810/26 NOTAMC B3809/26, B) 2609241818.
"""
import json
import sys
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

import ltfj_bot as bot
import ltfj_notam as nm
import ltfj_notam_client as notam_client
import ltfj_sayfa as sayfa
import state_birlestir as sb

SIMDI = datetime.now(timezone.utc)


def _iso(delta_saat=0):
    return (SIMDI + timedelta(hours=delta_saat)).isoformat(timespec="seconds")


def _notam(nid, numara, tip="N", **ek):
    k = {"id": nid, "number": numara, "notam_type": tip, "location": "LTFJ",
         "status": "active", "effective_start": _iso(-24), "effective_end": _iso(48),
         "notam_issued": _iso(-24), "record_updated_at": "2026-09-24T00:00:00Z",
         "text": "RWY 06L/24R CLSD", "ilgili_notam": None}
    k.update(ek)
    return k


def _notamc(nid, numara, iptal_edilen, bas="2026-09-24T18:18:00Z", **ek):
    return _notam(nid, numara, "C", effective_start=bas, effective_end=None,
                  notam_issued=bas, text="NOTAM CNL. NEW NOTAM TO FLW.",
                  raw=f"{numara} NOTAMC {iptal_edilen}\r Q) LTBB/QMRXX/IV/BO /A /000/999/"
                      f"4054N02919E005\r A) LTFJ B) 2609241818\r E) NOTAM CNL. NEW NOTAM TO FLW.",
                  ilgili_notam={"tip": "C", "numara": iptal_edilen}, **ek)


# =============================================================== eslestirme
def test_notamc_hedefi_iptal_isaretler_tarihi_B_alani():
    gecmis = {"a": _notam("a", "B3809/26"), "c": _notamc("c", "B3810/26", "B3809/26")}
    assert nm.iptalleri_isle(gecmis) == ["B3809/26"]
    assert gecmis["a"]["iptal"] == {"eden": "B3810/26", "eden_id": "c",
                                    "zaman": "2026-09-24T18:18:00Z"}
    # NOTAC alanlari degismez
    assert gecmis["a"]["status"] == "active" and "iptal" not in gecmis["c"]


def test_idempotent_ikinci_cagri_bir_sey_degistirmez():
    gecmis = {"a": _notam("a", "B3809/26"), "c": _notamc("c", "B3810/26", "B3809/26")}
    nm.iptalleri_isle(gecmis)
    once = json.dumps(gecmis, sort_keys=True)
    assert nm.iptalleri_isle(gecmis) == []
    assert json.dumps(gecmis, sort_keys=True) == once


def test_GERCEK_ornek_hedef_gecmiste_yoksa_hicbir_sey_isaretlenmez():
    """28.09 state'inde B3810/26 NOTAMC B3809/26 vardi, B3809/26 yoktu."""
    gecmis = {"c": _notamc("c", "B3810/26", "B3809/26"),
              "x": _notam("x", "B3808/26")}
    assert nm.iptalleri_isle(gecmis) == []
    assert not any(k.get("iptal") for k in gecmis.values())


def test_numara_metinde_yoksa_tahmin_edilmez():
    c = _notamc("c", "B3810/26", "B3809/26")
    c["ilgili_notam"] = None                  # referans metinde yok
    gecmis = {"a": _notam("a", "B3809/26"), "c": c}
    assert nm.iptalleri_isle(gecmis) == []


def test_NOTAMR_iptal_sayilmaz():
    r = _notam("r", "B3811/26", "R", ilgili_notam={"tip": "R", "numara": "B3809/26"})
    gecmis = {"a": _notam("a", "B3809/26"), "r": r}
    assert nm.iptalleri_isle(gecmis) == []


def test_baska_lokasyondaki_ayni_numara_eslesmez():
    gecmis = {"a": _notam("a", "B3809/26", location="LTFM"),
              "c": _notamc("c", "B3810/26", "B3809/26")}
    assert nm.iptalleri_isle(gecmis) == []


def test_iptal_zamani_yedegi_notam_issued_yoksa_None():
    c = _notamc("c", "B3810/26", "B3809/26")
    c["effective_start"] = None
    assert nm.iptal_zamani(c) == "2026-09-24T18:18:00Z"          # notam_issued
    c["notam_issued"] = None
    assert nm.iptal_zamani(c) is None


def test_iki_notamc_ayni_hedefi_gosterirse_en_erken_kazanir():
    gecmis = {"a": _notam("a", "B3809/26"),
              "c2": _notamc("c2", "B3900/26", "B3809/26", bas="2026-09-26T00:00:00Z"),
              "c1": _notamc("c1", "B3810/26", "B3809/26", bas="2026-09-24T18:18:00Z")}
    nm.iptalleri_isle(gecmis)
    assert gecmis["a"]["iptal"]["eden"] == "B3810/26"


# ============================================================ kalicilik
def test_isaret_sonraki_senkronda_NOTAC_kaydi_guncellense_de_kalir():
    gecmis = {"a": _notam("a", "B3809/26"), "c": _notamc("c", "B3810/26", "B3809/26")}
    nm.iptalleri_isle(gecmis)
    guncel = _notam("a", "B3809/26", record_updated_at="2026-09-25T00:00:00Z")
    yeni = nm.gecmisi_guncelle(gecmis, [guncel], simdi=_iso())
    assert yeni["a"]["iptal"]["eden"] == "B3810/26"


def test_state_birlestirmede_isaret_bir_taraftaysa_korunur():
    iptalli = {**_notam("a", "B3809/26"), "last_seen": "2026-09-24T20:00:00+00:00",
               "iptal": {"eden": "B3810/26", "eden_id": "c", "zaman": "2026-09-24T18:18:00Z"}}
    # Diger taraf DAHA YENI gorulmus ama isaretsiz: icerik oradan gelir,
    # isaret kaybolmamali.
    isaretsiz = {**_notam("a", "B3809/26"), "last_seen": "2026-09-24T21:00:00+00:00"}
    for a, b in ((iptalli, isaretsiz), (isaretsiz, iptalli)):
        s = sb.birlestir({"notam_gecmisi": {"a": a}}, {"notam_gecmisi": {"a": b}})
        assert s["notam_gecmisi"]["a"]["iptal"]["eden"] == "B3810/26"


# ======================================================= web veri dosyasi
def test_iptal_edilen_aktif_ve_yaklasandan_cikar_gecmiste_kalir(tmp_path):
    ss = _iso()
    aktif = {**_notam("a", "B3809/26"), "last_seen": ss}
    yaklasan = {**_notam("y", "B3812/26", effective_start=_iso(24)), "last_seen": ss}
    diger = {**_notam("d", "B3813/26"), "last_seen": ss}
    c1 = {**_notamc("c1", "B3810/26", "B3809/26"), "last_seen": ss}
    c2 = {**_notamc("c2", "B3814/26", "B3812/26"), "last_seen": ss}
    gecmis = {k["id"]: k for k in (aktif, yaklasan, diger, c1, c2)}
    nm.iptalleri_isle(gecmis)
    hedef = tmp_path / "notam_veri.json"
    nm.notam_veri_yaz({"notam_son_senkron": ss, "notam_gecmisi": gecmis}, hedef)
    veri = json.loads(hedef.read_text(encoding="utf-8"))
    aktif_no = [k["number"] for k in veri["aktif"]]
    assert "B3809/26" not in aktif_no and "B3813/26" in aktif_no
    assert "B3812/26" not in [k["number"] for k in veri["yaklasan"]]
    g = {k["number"]: k for k in veri["gecmis"]}
    assert g["B3809/26"]["iptal"] == {"eden": "B3810/26", "eden_id": "c1",
                                      "zaman": "2026-09-24T18:18:00Z"}
    assert g["B3812/26"]["iptal"]["eden"] == "B3814/26"


# ============================================================ bot akisi
@pytest.fixture
def sahte_notam_ortami(monkeypatch):
    monkeypatch.setattr(notam_client, "api_anahtari_var_mi", lambda: True)
    fake_push = types.ModuleType("ltfj_push")
    fake_push.yapilandirilmis_mi = MagicMock(return_value=True)
    fake_push.gonder = MagicMock(return_value={"gonderildi": 1, "silindi": 0, "hata": 0})
    monkeypatch.setitem(sys.modules, "ltfj_push", fake_push)
    return fake_push


def test_bot_senkronu_NOTAMC_gelince_aktif_notami_iptal_eder(monkeypatch, sahte_notam_ortami,
                                                             capsys):
    eski = "2026-09-24T12:00:00+00:00"
    hedef = _notam("a", "B3809/26")
    state = {"notam_gecmisi": {"a": {**hedef, "first_seen": eski, "last_seen": eski,
                                     "last_active": eski}},
             "notam_son_senkron": eski}
    monkeypatch.setattr(bot.ltfj_notam, "yururlukteki_ve_yaklasan_notamlar",
                        lambda loc, gecmis=None: [hedef, _notamc("c", "B3810/26", "B3809/26")])
    bot.notam_senkronize(state)
    assert state["notam_gecmisi"]["a"]["iptal"]["zaman"] == "2026-09-24T18:18:00Z"
    assert "NOTAMC ile iptal edildi: B3809/26" in capsys.readouterr().out


def test_iptal_edilmis_yaklasan_icin_yururluge_girdi_bildirimi_atilmaz(monkeypatch,
                                                                     sahte_notam_ortami):
    eski = "2026-09-24T12:00:00+00:00"
    hedef = _notam("a", "B3809/26")          # artik yururlukte
    c = _notamc("c", "B3810/26", "B3809/26")
    state = {"notam_gecmisi": {
        "a": {**hedef, "first_seen": eski, "last_seen": eski, "last_active": eski,
              "push_yaklasan": True},
        "c": {**c, "first_seen": eski, "last_seen": eski, "last_active": eski}},
        "notam_son_senkron": eski}
    monkeypatch.setattr(bot.ltfj_notam, "yururlukteki_ve_yaklasan_notamlar",
                        lambda loc, gecmis=None: [hedef, c])
    bot.notam_senkronize(state)
    sahte_notam_ortami.gonder.assert_not_called()
    assert "push_yururluk" not in state["notam_gecmisi"]["a"]


# ================================================================= sayfa
def _html(tmp_path):
    hedef = tmp_path / "index.html"
    sayfa.sayfa_yaz([], [], hedef)
    return hedef.read_text(encoding="utf-8")


def test_sayfa_gecerlilik_iptali_tarih_ve_statusten_ONCE_degerlendirir(tmp_path):
    blok = _html(tmp_path).split("ltfjNotamGecerlilik = function")[1].split("}};")[0]
    assert "if (n.iptal)" in blok and 'durum: "iptal"' in blok
    assert blok.index("if (n.iptal)") < blok.index("CANLI_DURUMLAR.indexOf")
    assert blok.index("if (n.iptal)") < blok.index("effective_end")
    assert '"iptal edildi"' in blok


def test_sayfa_kartta_iptal_eden_ve_tarih_yaziliyor(tmp_path):
    blok = _html(tmp_path).split("ltfjNotamIlgiliSatiri = function")[1].split("}};")[0]
    assert "n.iptal" in blok and "İptal edildi" in blok and "p.eden" in blok
    assert "ltfjNotamIptalZamani(p.zaman)" in blok


def test_sayfa_aramada_iptal_durum_filtresi_var(tmp_path):
    assert '<option value="iptal">İptal edilmiş</option>' in _html(tmp_path)
