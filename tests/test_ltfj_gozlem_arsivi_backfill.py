"""PR-2: gozlem arsivi geri doldurma + surum katmani + eksik slot saglik.

Ag kullanilmaz. MGM yanitlari, PR #99 kesfinde OLCULEN alan adlariyla
(observationTimeNormal kesirli saniyeli, observationStatus 1/4,
observationStatusExplanation "NORMAL"/"CCA   ", observationType 4/5)
kurulmus SENTETIK sozluklerdir; metinler sentetiktir.

Kilitlenenler:
  - ham zaman/metin/status aynen saklanir; kanonik zaman saniyesi kesilir;
  - kanonik katman tekil ve ilk yakalanan; surum katmani ekleme-yalnizca,
    status'a gore SECIM YOK;
  - backfill_kurtarilan bir DURUM GECISIDIR (H24 oncesi yok -> sonrasi var);
  - 60dk_uzeri_gec_ingest ondan AYRI;
  - eksik slot durumlari; geri doldurma hatasi canli akisi etkilemez;
  - idempotency ve simetrik birlestirme; kanonik celiski GIZLENMEZ;
  - canli akisin sozlesmesi (hours=0, dataLast, eski anahtarlar) degismez.
"""
import ast
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import ltfj_gozlem_arsivi as ga
import ltfj_rasat as rasat
from ltfj_analiz import metar_coz

UTC = timezone.utc


def _t(s):
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


def _mgm(zaman_ham, metin, id_, status=1, aciklama="NORMAL", tip_kodu=None):
    tip = metin.split()[0]
    kod = tip_kodu if tip_kodu is not None else {"METAR": 4, "SPECI": 5, "TAF": 6}[tip]
    return {"id": id_, "observationStatus": status,
            "observationStatusExplanation": aciklama,
            "observationText": metin, "observationTimeNormal": zaman_ham,
            "observationType": kod,
            "observationTypeExplanation": {4: "SATU", 5: "SPTU", 6: "FTTU"}.get(kod, "?"),
            "stationIcaoCode": "LTFJ", "stationNO": 0}


def _next_data(kayitlar, saat):
    blok = {"istInfo": {"icao": "LTFJ"}, "gamet": None,
            "dataLast": kayitlar if saat == 0 else None,
            "data": None if saat == 0 else kayitlar}
    return {"props": {"pageProps": {"response": [blok]}}, "query": {"hours": str(saat)}}


def _raporlar(kayitlar, saat=24):
    return rasat.raporlari_ayikla(_next_data(kayitlar, saat), "LTFJ", saat)


def _metar(hhmm, gun=28, ek="9999 FEW030 18/16 Q1014", ms="000"):
    hh, mm = hhmm.split(":")
    return (f"2026-09-{gun:02d}T{hh}:{mm}:00.{ms}Z",
            f"METAR LTFJ {gun:02d}{hh}{mm}Z 02009KT {ek}")


def _k(hhmm, id_, gun=28, **kw):
    ek = kw.pop("ek", "9999 FEW030 18/16 Q1014")
    ms = kw.pop("ms", "000")
    z, m = _metar(hhmm, gun, ek, ms)
    return _mgm(z, m, id_, **kw)


@pytest.fixture
def klasor(tmp_path):
    return tmp_path


def _f(klasor):
    return ga._dosyalar(klasor)


# ================================================================ zaman ===
def test_kanonik_zaman_saniye_ve_mikrosaniyeyi_KESER():
    assert ga.kanonik_zaman(_t("2026-09-28T06:20:00.309")) == "2026-09-28T06:20:00+00:00"
    assert ga.kanonik_zaman(_t("2026-09-28T06:20:37.500")) == "2026-09-28T06:20:00+00:00"
    # yuvarlama DEGIL: 06:19:59.9 -> 06:19 (izgara disi kalir, sessizce 06:20 olmaz)
    assert ga.kanonik_zaman(_t("2026-09-28T06:19:59.900")) == "2026-09-28T06:19:00+00:00"


def test_ham_zaman_aynen_saklanir_kanonik_zaman_kesilir(klasor):
    f = _f(klasor)
    ga.arsive_isle(_raporlar([_k("06:20", 55274848, ms="309")]), metar_coz,
                   ga.KAYNAK_BACKFILL, _t("2026-09-28T09:35:54"), f["kanonik"], f["surum"])
    kan = ga.oku(f["kanonik"])[0]
    sur = ga.surumleri_oku(f["surum"])[0]
    assert kan["zaman"] == "2026-09-28T06:20:00+00:00"
    assert sur["zaman"] == kan["zaman"]
    assert sur["zaman_ham"] == "2026-09-28T06:20:00.309Z"


def test_ayni_gozlemin_farkli_kesirli_zamani_YENI_SURUM_DEGIL(klasor):
    f = _f(klasor)
    ga.arsive_isle(_raporlar([_k("06:20", 1, ms="309")]), metar_coz, ga.KAYNAK_CANLI,
                   _t("2026-09-28T06:24:00"), f["kanonik"], f["surum"])
    s = ga.arsive_isle(_raporlar([_k("06:20", 1, ms="777")]), metar_coz,
                       ga.KAYNAK_BACKFILL, _t("2026-09-28T07:24:00"), f["kanonik"], f["surum"])
    assert s["surum_eklenen"] == 0 and s["ayni_surum_farkli_ham_zaman"] == 1
    assert len(ga.surumleri_oku(f["surum"])) == 1
    assert ga.surumleri_oku(f["surum"])[0]["zaman_ham"].endswith("00.309Z")   # ilk goren


def test_ayni_surum_farkli_id_yeni_surum_degil_ama_sayilir(klasor):
    f = _f(klasor)
    ga.arsive_isle(_raporlar([_k("06:20", 1)]), metar_coz, ga.KAYNAK_CANLI,
                   _t("2026-09-28T06:24:00"), f["kanonik"], f["surum"])
    s = ga.arsive_isle(_raporlar([_k("06:20", 2)]), metar_coz, ga.KAYNAK_BACKFILL,
                       _t("2026-09-28T07:24:00"), f["kanonik"], f["surum"])
    assert s["surum_eklenen"] == 0 and s["ayni_surum_farkli_id"] == 1


def test_surum_anahtari_metni_yalnizca_karsilastirmada_normalize_eder(klasor):
    f = _f(klasor)
    r = _raporlar([_mgm("2026-09-28T06:20:00.1Z", "METAR  LTFJ 280620Z 9999  Q1014=", 1)])
    ga.arsive_isle(r, metar_coz, ga.KAYNAK_CANLI, _t("2026-09-28T06:24:00"),
                   f["kanonik"], f["surum"])
    r2 = _raporlar([_mgm("2026-09-28T06:20:00.1Z", "METAR LTFJ 280620Z 9999 Q1014", 1)])
    s = ga.arsive_isle(r2, metar_coz, ga.KAYNAK_BACKFILL, _t("2026-09-28T07:24:00"),
                       f["kanonik"], f["surum"])
    assert s["surum_eklenen"] == 0
    assert ga.surumleri_oku(f["surum"])[0]["metin"] == "METAR  LTFJ 280620Z 9999  Q1014="


# ======================================================== surum / CCA ====
def test_status_NORMAL_den_CCA_ya_ayni_metin_YENI_SURUM_kanonik_DEGISMEZ(klasor):
    f = _f(klasor)
    ga.arsive_isle(_raporlar([_k("06:20", 1)]), metar_coz, ga.KAYNAK_CANLI,
                   _t("2026-09-28T06:24:00"), f["kanonik"], f["surum"])
    kanonik_once = f["kanonik"].read_bytes()
    s = ga.arsive_isle(_raporlar([_k("06:20", 1, status=4, aciklama="CCA   ")]), metar_coz,
                       ga.KAYNAK_BACKFILL, _t("2026-09-28T07:24:00"), f["kanonik"], f["surum"])
    assert s["surum_eklenen"] == 1 and s["mevcut_anahtara_yeni_surum"] == 1
    assert s["eklenen_anahtarlar"] == []                    # kurtarilan DEGIL
    assert f["kanonik"].read_bytes() == kanonik_once          # kanonik dokunulmadi
    surumler = ga.surumleri_oku(f["surum"])
    assert [v["mgm_status"] for v in surumler] == ["1", "4"]  # hicbiri silinmedi
    assert surumler[1]["mgm_status_aciklama"] == "CCA   "      # sondaki bosluklar korundu


def test_eski_metinsiz_satir_varken_backfill_farkli_icerik_getirirse(klasor):
    """06:20 ornegi: canli arsivde (PR-2 oncesi, ham metin yok) tavan bos;
    MGM'nin bugunku CCA metni BKN025 tasiyor. Kanonik satir DEGISMEZ,
    ham surum eklenir, ayristirma farki sayilir - hicbir surum secilmez."""
    f = _f(klasor)
    ga._csv_yaz([{"zaman": "2026-09-28T06:20:00+00:00", "tip": "METAR", "gorus": "6000",
                  "tavan": "", "sicaklik": "18", "cig_noktasi": "16", "ruzgar_yon": "20",
                  "ruzgar_hiz": "9", "ruzgar_hamle": "", "qnh": "1014", "hava": "-SHRA",
                  "cavok": "0"}],
                 ga.SUTUNLAR[:12], f["kanonik"])                     # eski baslik
    once = f["kanonik"].read_bytes()
    metin = ("METAR LTFJ 280620Z 02009KT 350V050 6000 -SHRA SCT009 BKN025 BKN080 "
             "18/16 Q1014 RESHRA NOSIG")
    r = _raporlar([_mgm("2026-09-28T06:20:00.309Z", metin, 55274848, 4, "CCA   ")])
    s = ga.arsive_isle(r, metar_coz, ga.KAYNAK_BACKFILL, _t("2026-09-28T09:35:54"),
                       f["kanonik"], f["surum"])
    assert s["eklenen_anahtarlar"] == [] and s["surum_eklenen"] == 1
    assert f["kanonik"].read_bytes() == once
    d = ga.durum_ozeti(ga.oku(f["kanonik"]), ga.surumleri_oku(f["surum"]),
                       _t("2026-09-28T09:35:54"), metar_coz)
    assert d["surum"]["kanonik_ile_ayristirma_farkli"] == {
        "sayi": 1, "son": ["2026-09-28T06:20:00+00:00 METAR"]}
    assert d["surum"]["mgm_status"] == {"4": 1}


def test_ayristirma_karsilastirmasi_coz_verilmezse_hesaplanmaz(klasor):
    d = ga.durum_ozeti([], [], _t("2026-09-28T09:00:00"))
    assert d["surum"]["kanonik_ile_ayristirma_farkli"] is None


def test_kod_status_degerine_gore_SECIM_yapmiyor():
    """COR/CCA semantigi bilinmiyor: modulde status degerine dayali bir
    karsilastirma (ör. == '4', 'CCA') OLMAMALI."""
    kaynak = Path(ga.__file__).read_text(encoding="utf-8")
    for yasak in ('== "4"', "== '4'", '"CCA"', "'CCA'", '"COR"', "'COR'"):
        assert yasak not in kaynak, yasak


def test_cozulemeyen_rapor_surumu_yazilir_kanonik_eklenmez(klasor, capsys):
    f = _f(klasor)

    def coz(m):
        raise ValueError("bozuk")

    s = ga.arsive_isle(_raporlar([_k("06:20", 1)]), coz, ga.KAYNAK_BACKFILL,
                       _t("2026-09-28T07:00:00"), f["kanonik"], f["surum"])
    assert s["cozulemeyen"] == 1 and s["surum_eklenen"] == 1
    assert ga.oku(f["kanonik"]) == []
    assert "çözülemedi" in capsys.readouterr().err


def test_tip_kodu_uyusmazligi_yalnizca_sayilir_tip_metinden(klasor):
    f = _f(klasor)
    s = ga.arsive_isle(_raporlar([_k("06:20", 1, tip_kodu=5)]), metar_coz,
                       ga.KAYNAK_BACKFILL, _t("2026-09-28T07:00:00"), f["kanonik"], f["surum"])
    assert s["tip_kodu_uyusmazligi"] == 1
    assert ga.oku(f["kanonik"])[0]["tip"] == "METAR"


def test_TAF_iki_katmana_da_girmez(klasor):
    f = _f(klasor)
    r = _raporlar([_mgm("2026-09-28T04:40:00Z", "TAF LTFJ 280440Z 2806/2912 03005KT 9999", 1)])
    s = ga.arsive_isle(r, metar_coz, ga.KAYNAK_BACKFILL, _t("2026-09-28T07:00:00"),
                       f["kanonik"], f["surum"])
    assert s["rapor"] == 0 and not f["kanonik"].exists() and not f["surum"].exists()


# ============================================= backfill_kurtarilan (durum) ===
def _kosu(klasor, h0, h24, alinma, h24_hata=None):
    saat = iter([alinma + timedelta(seconds=i) for i in range(20)])

    def cek():
        if h24_hata:
            raise h24_hata
        return _raporlar(h24)

    return ga.kosu_isle(_raporlar(h0, 0), alinma, metar_coz, cek, klasor,
                        zaman_fn=lambda: next(saat))


def test_backfill_kurtarilan_DURUM_GECISI_olarak_tanimli(klasor):
    """H24 islemesi BASLAMADAN ONCE kanonikte olmayan ve H24 sonucu ILK KEZ
    eklenen anahtar. 07:20 H24 yanitinda da var ama H0 onu once ekledigi
    icin kurtarilan DEGIL; 06:20 kosudan once zaten arsivde."""
    f = _f(klasor)
    ga.arsive_isle(_raporlar([_k("06:20", 1)]), metar_coz, ga.KAYNAK_CANLI,
                   _t("2026-09-28T06:24:00"), f["kanonik"], f["surum"])
    d = _kosu(klasor, h0=[_k("07:20", 3)],
              h24=[_k("06:20", 1), _k("06:50", 2, ms="845"), _k("07:20", 3)],
              alinma=_t("2026-09-28T07:24:00"))
    b = d["cekim"]["backfill_h24"]["son_isleme"]
    assert b["backfill_kurtarilan"] == ["2026-09-28T06:50:00+00:00 METAR"]
    kan = {s["zaman"][11:16]: s for s in ga.oku(f["kanonik"])}
    assert kan["06:20"]["kaynak"] == "canli_h0"
    assert kan["07:20"]["kaynak"] == "canli_h0"
    assert kan["06:50"]["kaynak"] == "backfill_h24"
    assert d["arsiv"]["ingest"]["backfill_kurtarilan"] == {"METAR": 1, "SPECI": 0}


def test_H0_ve_H24_ikisinde_de_olan_anahtar_canli_sayilir(klasor):
    d = _kosu(klasor, h0=[_k("07:20", 3)], h24=[_k("07:20", 3)],
              alinma=_t("2026-09-28T07:24:00"))
    assert d["cekim"]["backfill_h24"]["son_isleme"]["backfill_kurtarilan"] == []
    assert d["cekim"]["canli_h0"]["son_isleme"]["eklenen_anahtarlar"] == [
        "2026-09-28T07:20:00+00:00 METAR"]


def test_kurtarilan_ile_60dk_uzeri_gec_ingest_AYRI_metrikler(klasor):
    """06:50 -> 07:24 (34 dk, kurtarilan ama gec degil); 05:50 -> 07:24
    (94 dk, kurtarilan VE gec); canli 07:20 -> 07:24 (ikisi de degil)."""
    d = _kosu(klasor, h0=[_k("07:20", 3)],
              h24=[_k("05:50", 1), _k("06:20", 4), _k("06:50", 2), _k("07:20", 3)],
              alinma=_t("2026-09-28T07:24:00"))
    ing = d["arsiv"]["ingest"]
    assert ing["tablo"]["METAR"]["backfill_h24"] == {"60dk_ve_alti": 1, "60dk_uzeri": 2}
    assert ing["tablo"]["METAR"]["canli_h0"] == {"60dk_ve_alti": 1, "60dk_uzeri": 0}
    assert ing["backfill_kurtarilan"]["METAR"] == 3
    assert ing["60dk_uzeri_gec_ingest"]["METAR"] == 2


def test_PR2_oncesi_satirlar_bilinmiyor_sayilir(klasor):
    f = _f(klasor)
    ga.ekle(_raporlar([_k("06:20", 1)]), metar_coz, f["kanonik"])     # eski yol
    d = ga.durum_ozeti(ga.oku(f["kanonik"]), [], _t("2026-09-28T07:00:00"))
    assert d["ingest"]["tablo"]["METAR"]["bilinmiyor"] == 1
    assert d["ingest"]["backfill_kurtarilan"]["METAR"] == 0


# ============================================================ eksik slot ===
def _kanonik(*hhmm, tip="METAR"):
    return [{"zaman": f"2026-09-28T{h}:00+00:00", "tip": tip} for h in hhmm]


def test_SPECI_izgara_slotunu_DOLDURMAZ_ve_ayni_dakikada_ikisi_de_kalir(klasor):
    satirlar = _kanonik("06:20", "07:20") + _kanonik("06:50", tip="SPECI")
    eksik = ga.eksik_slotlar(satirlar, _t("2026-09-28T07:25:00"))
    assert [d["slot"][11:16] for d in eksik] == ["06:50"]

    f = _f(klasor)
    r = _raporlar([_k("06:50", 1),
                   _mgm("2026-09-28T06:50:00.2Z", "SPECI LTFJ 280650Z 0800 FG", 2)])
    ga.arsive_isle(r, metar_coz, ga.KAYNAK_CANLI, _t("2026-09-28T06:55:00"),
                   f["kanonik"], f["surum"])
    assert sorted(s["tip"] for s in ga.oku(f["kanonik"])) == ["METAR", "SPECI"]


def test_slot_durumlari_ve_24_saat_siniri():
    simdi = _t("2026-09-28T09:35:00")
    # 27.09 09:20 tam sinirda degil (09:35-24h=09:35) -> disarida;
    # 27.09 09:50 pencerede -> bekleniyor.
    satirlar = [{"zaman": "2026-09-27T08:50:00+00:00", "tip": "METAR"},
                {"zaman": "2026-09-27T10:20:00+00:00", "tip": "METAR"},
                {"zaman": "2026-09-28T09:20:00+00:00", "tip": "METAR"}]
    eksik = {d["slot"][:16]: d["durum"] for d in ga.eksik_slotlar(satirlar, simdi)}
    assert eksik["2026-09-27T09:20"] == "backfill_penceresi_disinda"
    assert eksik["2026-09-27T09:50"] == "bekleniyor"
    assert eksik["2026-09-28T08:50"] == "bekleniyor"
    assert "kalıcı" not in json.dumps(eksik) and "kalici" not in json.dumps(eksik)


def test_tam_sinirdaki_slot_pencere_disinda():
    simdi = _t("2026-09-28T09:20:00")
    satirlar = _kanonik("09:20") + [{"zaman": "2026-09-27T08:50:00+00:00", "tip": "METAR"}]
    eksik = {d["slot"][:16]: d["durum"] for d in ga.eksik_slotlar(satirlar, simdi)}
    assert eksik["2026-09-27T09:20"] == "backfill_penceresi_disinda"
    assert eksik["2026-09-27T09:50"] == "bekleniyor"


def test_mgm_yanitinda_yok_yalnizca_yanit_kapsiyorsa():
    simdi = _t("2026-09-28T08:00:00")
    satirlar = _kanonik("06:20", "07:50")
    yanit = {"metar": {_t("2026-09-28T06:20:00"), _t("2026-09-28T07:50:00")},
             "en_eski": _t("2026-09-28T06:20:00"), "en_yeni": _t("2026-09-28T07:50:00")}
    eksik = {d["slot"][11:16]: d for d in ga.eksik_slotlar(satirlar, simdi, yanit)}
    assert eksik["06:50"]["mgm_yanitinda_yok"] is True
    assert {d["mgm_yanitinda_yok"] for d in ga.eksik_slotlar(satirlar, simdi)} == {None}


def test_eksik_slota_deger_YAZILMAZ(klasor):
    d = _kosu(klasor, h0=[_k("07:20", 3)], h24=[_k("06:20", 1), _k("07:20", 3)],
              alinma=_t("2026-09-28T07:24:00"))
    zamanlar = [s["zaman"][11:16] for s in ga.oku(_f(klasor)["kanonik"])]
    assert "06:50" not in zamanlar
    assert d["arsiv"]["eksik_slot"]["bekleniyor"] == 1
    assert d["arsiv"]["eksik_slot"]["en_uzun_bosluk"]["slot_sayisi"] == 1


# ========================================================== saglik / hata ===
def test_backfill_hatasi_canli_arsivlemeyi_ETKILEMEZ_saglik_ayri(klasor, capsys):
    d = _kosu(klasor, h0=[_k("07:20", 3)], h24=None, alinma=_t("2026-09-28T07:24:00"),
              h24_hata=rasat.AgHatasi("3 denemede ulasilamadi"))
    assert [s["zaman"][11:16] for s in ga.oku(_f(klasor)["kanonik"])] == ["07:20"]
    c, b = d["cekim"]["canli_h0"], d["cekim"]["backfill_h24"]
    assert c["ardisik_hata"] == 0 and c["son_basarili"]
    assert b["ardisik_hata"] == 1 and b["son_hata"]["sinif"] == "AgHatasi"
    assert "son_basarili" not in b
    assert "geri doldurma" in capsys.readouterr().err

    d = _kosu(klasor, h0=[_k("07:50", 4)], h24=None, alinma=_t("2026-09-28T07:54:00"),
              h24_hata=rasat.AyiklamaHatasi("hours=24 yanitinda 'data' listesi yok"))
    assert d["cekim"]["backfill_h24"]["ardisik_hata"] == 2
    assert d["cekim"]["canli_h0"]["ardisik_hata"] == 0

    # sonraki basarili kosu sayaci sifirlar ve boslugu doldurur
    d = _kosu(klasor, h0=[_k("08:20", 5)],
              h24=[_k("07:20", 3), _k("07:50", 4), _k("08:20", 5)],
              alinma=_t("2026-09-28T08:24:00"))
    assert d["cekim"]["backfill_h24"]["ardisik_hata"] == 0
    assert d["cekim"]["backfill_h24"]["son_hata"]["sinif"] == "AyiklamaHatasi"  # gecmis kalir


def test_canli_hata_kaydet_yalnizca_canli_sagligi_gunceller(klasor):
    d = _kosu(klasor, h0=[_k("07:20", 3)], h24=[_k("07:20", 3)],
              alinma=_t("2026-09-28T07:24:00"))
    arsiv_once = d["arsiv"]
    ga.canli_hata_kaydet(rasat.AgHatasi("zaman asimi"), klasor,
                         zaman_fn=lambda: _t("2026-09-28T07:54:00"))
    yeni = ga.durum_oku(_f(klasor)["durum"])
    assert yeni["cekim"]["canli_h0"]["ardisik_hata"] == 1
    assert yeni["cekim"]["canli_h0"]["son_hata"]["mesaj"] == "zaman asimi"
    assert yeni["cekim"]["backfill_h24"] == d["cekim"]["backfill_h24"]
    assert yeni["arsiv"] == arsiv_once


def test_kosu_isle_canli_rapor_listesini_DEGISTIRMEZ(klasor):
    h0 = _raporlar([_k("07:20", 3)], 0)
    kopya = [dict(r) for r in h0]
    ga.kosu_isle(h0, _t("2026-09-28T07:24:00"), metar_coz,
                 lambda: _raporlar([_k("06:50", 2), _k("07:20", 3)]), klasor)
    assert h0 == kopya and len(h0) == 1


def test_gizli_anahtar_hicbir_arsiv_dosyasina_yazilmaz(klasor, monkeypatch):
    monkeypatch.setenv("NOTAM_API_KEY", "GIZLI-deneme-anahtari")
    _kosu(klasor, h0=[_k("07:20", 3)], h24=None, alinma=_t("2026-09-28T07:24:00"),
          h24_hata=rasat.AgHatasi("baglanti"))
    for p in klasor.iterdir():
        assert "GIZLI-deneme-anahtari" not in p.read_text(encoding="utf-8")


# ======================================================== idempotency ====
def test_ayni_yanit_iki_kez_islenince_katmanlar_BAYT_BAYT_ayni(klasor):
    h24 = [_k("06:20", 1), _k("06:50", 2), _k("07:20", 3, status=4, aciklama="CCA   ")]
    _kosu(klasor, h0=[_k("07:20", 3)], h24=h24, alinma=_t("2026-09-28T07:24:00"))
    f = _f(klasor)
    once = {ad: f[ad].read_bytes() for ad in ("kanonik", "surum")}
    d = _kosu(klasor, h0=[_k("07:20", 3)], h24=h24, alinma=_t("2026-09-28T07:54:00"))
    assert {ad: f[ad].read_bytes() for ad in ("kanonik", "surum")} == once
    assert d["cekim"]["backfill_h24"]["son_isleme"]["surum_eklenen"] == 0


# ========================================================= birlestirme ===
def _iki_taraf(tmp_path, a_rapor, b_rapor, a_alinma, b_alinma, kaynak=ga.KAYNAK_CANLI):
    a, b = tmp_path / "a", tmp_path / "b"
    for d, r, al in ((a, a_rapor, a_alinma), (b, b_rapor, b_alinma)):
        f = _f(d)
        d.mkdir()
        ga.arsive_isle(_raporlar(r), metar_coz, kaynak, al, f["kanonik"], f["surum"])
    return _f(a), _f(b)


def _dosya_adlari(kok):
    return sorted(p.name for p in kok.rglob("*") if p.is_file())


def test_birlestirme_simetrik_ve_idempotent(tmp_path):
    fa, fb = _iki_taraf(tmp_path, [_k("06:20", 1), _k("06:50", 2)],
                        [_k("06:50", 2), _k("07:20", 3)],
                        _t("2026-09-28T07:24:00"), _t("2026-09-28T07:25:00"))
    h1, h2 = tmp_path / "h1.csv", tmp_path / "h2.csv"
    ga.birlestir(fa["kanonik"], fb["kanonik"], h1)
    ga.birlestir(fb["kanonik"], fa["kanonik"], h2)
    assert h1.read_bytes() == h2.read_bytes()
    once = h1.read_bytes()
    ga.birlestir(h1, h1, h1)
    assert h1.read_bytes() == once
    s1, s2 = tmp_path / "s1.csv", tmp_path / "s2.csv"
    ga.surumleri_birlestir(fa["surum"], fb["surum"], s1)
    ga.surumleri_birlestir(fb["surum"], fa["surum"], s2)
    assert s1.read_bytes() == s2.read_bytes()
    assert len(ga.surumleri_oku(s1)) == 3


def test_ayni_kanonik_icerigi_iki_kosu_farkli_zamanda_alirsa_celiski_YOK(tmp_path, capsys):
    """Eszamanli iki kosu ayni gozlemi ayni icerikle alir: yalnizca
    provenance farkli. En erken alinan kalir, celiski SAYILMAZ."""
    fa, fb = _iki_taraf(tmp_path, [_k("06:50", 2)], [_k("06:50", 2)],
                        _t("2026-09-28T07:25:00"), _t("2026-09-28T07:24:00"))
    h = tmp_path / "k.csv"
    ga.birlestir(fa["kanonik"], fb["kanonik"], h)
    assert [s["alinma_zamani"][11:16] for s in ga.oku(h)] == ["07:24"]
    assert "UYARI" not in capsys.readouterr().err


def test_ayni_surumu_iki_kosu_farkli_zamanda_gorurse_en_erken_kalir_celiski_YOK(tmp_path, capsys):
    fa, fb = _iki_taraf(tmp_path, [_k("06:50", 2)], [_k("06:50", 2)],
                        _t("2026-09-28T07:25:00"), _t("2026-09-28T07:24:00"))
    h = tmp_path / "s.csv"
    ga.surumleri_birlestir(fa["surum"], fb["surum"], h)
    assert [s["alinma_zamani"][11:16] for s in ga.surumleri_oku(h)] == ["07:24"]
    assert "UYARI" not in capsys.readouterr().err


def _celiskili_taraflar(tmp_path):
    return _iki_taraf(tmp_path, [_k("06:20", 1, ek="6000 -SHRA 18/16 Q1014")],
                      [_k("06:20", 1, ek="6000 -SHRA BKN025 18/16 Q1014")],
                      _t("2026-09-28T06:24:00"), _t("2026-09-28T06:54:00"))


def test_kanonik_celiski_deterministik_ama_GIZLENMIYOR_ve_AYRI_DOSYA_YOK(tmp_path, capsys):
    """Ayni (zaman, tip) iki tarafta FARKLI ayristirilmis icerikle: en erken
    alinan secilir; stderr'e acik DEGISMEZLIK IHLALI uyarisi yazilir; iki
    yon ayni sonucu verir; kalici ayri celiski dosyasi URETILMEZ."""
    fa, fb = _celiskili_taraflar(tmp_path)
    once = _dosya_adlari(tmp_path)
    h1, h2 = tmp_path / "h1" / "gozlem_arsivi.csv", tmp_path / "h2" / "gozlem_arsivi.csv"
    ga.birlestir(fa["kanonik"], fb["kanonik"], h1)
    ga.birlestir(fb["kanonik"], fa["kanonik"], h2)
    err = capsys.readouterr().err
    assert err.count("DEĞİŞMEZLİK İHLALİ - kanonik çelişki: 2026-09-28T06:20:00+00:00 METAR") == 2
    assert '"tavan": "2500"' in err                           # elenen icerik logda
    assert h1.read_bytes() == h2.read_bytes()
    assert ga.oku(h1)[0]["tavan"] == ""
    assert ga.oku(h1)[0]["alinma_zamani"].endswith("06:24:00+00:00")
    assert _dosya_adlari(tmp_path) == sorted(once + ["gozlem_arsivi.csv"] * 2)


def test_kanonik_celiskide_eski_satir_onceligi(tmp_path, capsys):
    eski, yeni = tmp_path / "eski.csv", tmp_path / "yeni.csv"
    ga._csv_yaz([{"zaman": "2026-09-28T06:20:00+00:00", "tip": "METAR", "gorus": "6000"}],
                ga.SUTUNLAR[:12], eski)
    ga._csv_yaz([{"zaman": "2026-09-28T06:20:00+00:00", "tip": "METAR", "gorus": "5000",
                  "alinma_zamani": "2026-09-28T06:24:00+00:00", "kaynak": "canli_h0"}],
                ga.SUTUNLAR, yeni)
    h = tmp_path / "h.csv"
    ga.birlestir(yeni, eski, h)
    assert ga.oku(h)[0]["gorus"] == "6000"
    assert "kural eski_satir_onceligi" in capsys.readouterr().err


def test_eski_ve_yeni_baslikli_ayni_satir_celiski_SAYILMAZ(tmp_path, capsys):
    eski, yeni = tmp_path / "eski.csv", tmp_path / "yeni.csv"
    satir = {"zaman": "2026-09-28T06:20:00+00:00", "tip": "METAR", "gorus": "6000"}
    ga._csv_yaz([satir], ga.SUTUNLAR[:12], eski)
    ga._csv_yaz([satir], ga.SUTUNLAR, yeni)
    ga.birlestir(eski, yeni, tmp_path / "h.csv")
    assert "UYARI" not in capsys.readouterr().err


def test_surum_birlestirmede_ham_alan_farki_uyarilir(tmp_path, capsys):
    fa, fb = _iki_taraf(tmp_path, [_k("06:20", 1)], [_k("06:20", 99)],
                        _t("2026-09-28T06:24:00"), _t("2026-09-28T06:54:00"))
    h = tmp_path / "s.csv"
    ga.surumleri_birlestir(fa["surum"], fb["surum"], h)
    assert "sürüm ham alan farkı: 2026-09-28T06:20:00+00:00 METAR" in capsys.readouterr().err
    assert [s["mgm_id"] for s in ga.surumleri_oku(h)] == ["1"]


def test_bot_birlestirmesinde_celiski_DURUM_JSON_da_sayilir_ve_tasinir(tmp_path, capsys):
    """Tercih edilen model: ayri dosya yok; durum['catisma'] icinde sayac +
    son (zaman, tip) anahtarlari. Sonraki kosular sayaci tasir; ayni
    anahtar yeniden tespit edilirse tekrar sayilmaz."""
    uzak, bizim = tmp_path / "uzak", tmp_path / "bizim"
    uzak.mkdir(), bizim.mkdir()
    _kosu(uzak, h0=[_k("06:20", 1, ek="6000 -SHRA 18/16 Q1014")], h24=None,
          alinma=_t("2026-09-28T06:24:00"), h24_hata=rasat.AgHatasi("x"))
    _kosu(bizim, h0=[_k("06:20", 1, ek="6000 -SHRA BKN025 18/16 Q1014")], h24=None,
          alinma=_t("2026-09-28T06:54:00"), h24_hata=rasat.AgHatasi("x"))
    d = ga.birlestir_bizim(bizim, uzak, zaman_fn=lambda: _t("2026-09-28T06:55:00"))
    assert d["catisma"]["kanonik_catisma_sayisi"] == 1
    assert d["catisma"]["kanonik_catisma_son"] == [
        {"zaman": "2026-09-28T06:20:00+00:00", "tip": "METAR", "kural": "en_erken_alinma",
         "tespit_zamani": "2026-09-28T06:55:00+00:00"}]
    # Surum katmani iki ham surumu de tutar (provenance kaybolmaz).
    assert len(ga.surumleri_oku(_f(uzak)["surum"])) == 2
    assert "DEĞİŞMEZLİK İHLALİ" in capsys.readouterr().err
    assert _dosya_adlari(uzak) == ["gozlem_arsivi.csv", "gozlem_arsivi_durum.json",
                                   "gozlem_surumleri.csv"]

    # ayni celiski ikinci birlestirme denemesinde yeniden tespit -> sayac ayni
    d = ga.birlestir_bizim(bizim, uzak, zaman_fn=lambda: _t("2026-09-28T06:56:00"))
    assert d["catisma"]["kanonik_catisma_sayisi"] == 1

    # sonraki normal kosu sayaci tasir; canli hata kaydi da dokunmaz
    d = _kosu(uzak, h0=[_k("07:20", 3)], h24=[_k("07:20", 3)],
              alinma=_t("2026-09-28T07:24:00"))
    assert d["catisma"]["kanonik_catisma_sayisi"] == 1
    ga.canli_hata_kaydet(rasat.AgHatasi("y"), uzak)
    assert ga.durum_oku(_f(uzak)["durum"])["catisma"]["kanonik_catisma_sayisi"] == 1


def test_normal_kosuda_celiski_sayaclari_SIFIR(klasor):
    d = _kosu(klasor, h0=[_k("07:20", 3)], h24=[_k("07:20", 3)],
              alinma=_t("2026-09-28T07:24:00"))
    assert d["catisma"] == ga.catisma_bos()


def test_catisma_guncelle_iki_tarafi_birlestirir_tekrar_saymaz():
    a = {"kanonik_catisma_sayisi": 2, "kanonik_catisma_son": [
        {"zaman": "z1", "tip": "METAR", "kural": "k", "tespit_zamani": "t1"},
        {"zaman": "z2", "tip": "METAR", "kural": "k", "tespit_zamani": "t2"}]}
    b = {"kanonik_catisma_sayisi": 1, "kanonik_catisma_son": [
        {"zaman": "z1", "tip": "METAR", "kural": "k", "tespit_zamani": "t1"}]}
    yeni = [{"tur": "kanonik", "zaman": "z2", "tip": "METAR", "kural": "k",
             "tespit_zamani": "t3"},
            {"tur": "kanonik", "zaman": "z3", "tip": "SPECI", "kural": "k",
             "tespit_zamani": "t3"}]
    c = ga.catisma_guncelle([a, b], yeni)
    assert c["kanonik_catisma_sayisi"] == 3
    assert [x["zaman"] for x in c["kanonik_catisma_son"]] == ["z1", "z2", "z3"]
    assert c["surum_ham_fark_sayisi"] == 0
    assert ga.catisma_guncelle([None, {}], []) == ga.catisma_bos()


# ====================================== bir kerelik sema gecisi (migration) ===
def _satirlar(p):
    return p.read_bytes().decode("utf-8").split("\r\n")


def _migrasyon_dogrula(eski_dosya: Path, tmp_path: Path):
    """Eski bicimli (12 sutun) arsiv, yeni bir satir eklenince yeni bicimde
    yeniden yazilir: baslik iki sutun uzar, ESKI HER SATIR birebir ayni
    kalip yalnizca sonuna ',,' eklenir; veri degeri degismez."""
    hedef = tmp_path / "gozlem_arsivi.csv"
    hedef.write_bytes(eski_dosya.read_bytes())
    eski = _satirlar(hedef)
    eski_basliksiz = [x for x in eski[1:] if x]
    eski_icerik = ga.oku(hedef)
    assert eski[0] == ",".join(ga.SUTUNLAR[:12])

    s = ga.arsive_isle(_raporlar([_k("23:50", 9, gun=30)]), metar_coz,
                       ga.KAYNAK_BACKFILL, _t("2026-09-30T23:55:00"),
                       hedef, tmp_path / "gozlem_surumleri.csv")
    assert s["eklenen_anahtarlar"] == ["2026-09-30T23:50:00+00:00 METAR"]
    yeni = _satirlar(hedef)
    assert yeni[0] == ",".join(ga.SUTUNLAR)
    yeni_satir = next(x for x in yeni if x.startswith("2026-09-30T23:50"))
    yeni_basliksiz = [x for x in yeni[1:] if x and x != yeni_satir]
    assert yeni_basliksiz == [x + ",," for x in eski_basliksiz]
    # sutun bazinda: eski 12 sutunun degerleri satir satir ayni
    sonra = {(r["zaman"], r["tip"]): r for r in ga.oku(hedef)}
    for r in eski_icerik:
        y = sonra[(r["zaman"], r["tip"])]
        assert {k: y[k] for k in ga.SUTUNLAR[:12]} == {k: r[k] for k in ga.SUTUNLAR[:12]}
        assert y["alinma_zamani"] == "" and y["kaynak"] == ""

    # ikinci yazim: artik yeni bicim -> eski satirlar HIC degismez (bir kerelik)
    ara = hedef.read_bytes()
    ga.arsive_isle(_raporlar([_k("23:20", 10, gun=30)]), metar_coz, ga.KAYNAK_BACKFILL,
                   _t("2026-09-30T23:56:00"), hedef, tmp_path / "gozlem_surumleri.csv")
    son = _satirlar(hedef)
    assert [x for x in son if not x.startswith("2026-09-30T23:20")] == _satirlar_bytes(ara)
    return len(eski_basliksiz)


def _satirlar_bytes(b):
    return b.decode("utf-8").split("\r\n")


def test_sema_gecisi_sentetik_eski_dosya(tmp_path):
    eski = tmp_path / "eski.csv"
    ga._csv_yaz([{"zaman": "2026-09-23T13:01:00+00:00", "tip": "SPECI", "gorus": "800",
                  "hava": "-SHRA BR", "cavok": "0"},
                 {"zaman": "2026-09-23T13:20:00+00:00", "tip": "METAR", "gorus": "9999",
                  "tavan": "3000", "sicaklik": "18", "cig_noktasi": "16", "ruzgar_yon": "20",
                  "ruzgar_hiz": "9", "ruzgar_hamle": "", "qnh": "1014", "hava": "",
                  "cavok": "1"}],
                ga.SUTUNLAR[:12], eski)
    assert _migrasyon_dogrula(eski, tmp_path) == 2


def test_sema_gecisi_GERCEK_repo_arsivi(tmp_path):
    """Repodaki gercek gozlem_arsivi.csv (PR-2 oncesi bicim). Dosya ileride
    yeni bicime gecmisse bu test yalnizca 'yeni bicimde satirlar degismez'
    sozlesmesini dogrular."""
    gercek = Path("gozlem_arsivi.csv")
    if _satirlar(gercek)[0] == ",".join(ga.SUTUNLAR):
        hedef = tmp_path / "gozlem_arsivi.csv"
        hedef.write_bytes(gercek.read_bytes())
        once = _satirlar(hedef)
        # Sentetik kayit, gercek arsivde OLAMAYACAK bir zamanda: arsiv
        # 27.09'dan basliyor ve yalnizca ileri buyuyor. (Onceden 30.09
        # 23:50 kullaniliyordu; bot o METAR'i gercekten arsive yazinca
        # test kirildi.)
        ga.arsive_isle(_raporlar([_k("23:13", 9, gun=1)]), metar_coz, ga.KAYNAK_BACKFILL,
                       _t("2099-01-01T00:00:00"), hedef, tmp_path / "s.csv")
        sonra = _satirlar(hedef)
        assert any(x.startswith("2026-09-01T23:13") for x in sonra)
        assert [x for x in sonra if not x.startswith("2026-09-01T23:13")] == once
        return
    n = _migrasyon_dogrula(gercek, tmp_path)
    assert n >= 244


def test_birlestir_bizim_uc_katman_ve_durum(tmp_path):
    uzak, bizim = tmp_path / "uzak", tmp_path / "bizim"
    uzak.mkdir(), bizim.mkdir()
    _kosu(uzak, h0=[_k("07:20", 3)], h24=[_k("07:20", 3)], alinma=_t("2026-09-28T07:24:00"))
    _kosu(bizim, h0=[_k("07:20", 3)], h24=[_k("06:50", 2), _k("07:20", 3)],
          alinma=_t("2026-09-28T07:25:00"))
    bizim_cekim = ga.durum_oku(_f(bizim)["durum"])["cekim"]
    d = ga.birlestir_bizim(bizim, uzak, zaman_fn=lambda: _t("2026-09-28T07:26:00"))
    assert [s["zaman"][11:16] for s in ga.oku(_f(uzak)["kanonik"])] == ["06:50", "07:20"]
    assert d["cekim"] == bizim_cekim
    assert d["arsiv"]["ingest"]["backfill_kurtarilan"]["METAR"] == 1
    assert d["arsiv"]["surum"]["kanonik_ile_ayristirma_farkli"] is None


def test_cli_birlestir_bizim(tmp_path, capsys):
    uzak, bizim = tmp_path / "uzak", tmp_path / "bizim"
    uzak.mkdir(), bizim.mkdir()
    _kosu(bizim, h0=[_k("07:20", 3)], h24=[_k("07:20", 3)], alinma=_t("2026-09-28T07:24:00"))
    assert ga.main(["--birlestir-bizim", str(bizim),
                    "--dosya", str(uzak / "gozlem_arsivi.csv")]) == 0
    assert len(ga.oku(uzak / "gozlem_arsivi.csv")) == 1
    assert (uzak / "gozlem_surumleri.csv").exists() and (uzak / "gozlem_arsivi_durum.json").exists()


def test_eski_ekle_yolu_surum_dosyasi_OLUSTURMAZ(klasor):
    ga.ekle(_raporlar([_k("06:20", 1)]), metar_coz, klasor / "gozlem_arsivi.csv")
    assert sorted(p.name for p in klasor.iterdir()) == ["gozlem_arsivi.csv"]


# ============================================== canli akis sozlesmesi ====
def test_raporlari_ayikla_hours0_dataLast_hours24_data():
    kayit = [_k("07:20", 3)]
    assert len(rasat.raporlari_ayikla(_next_data(kayit, 0), "LTFJ", 0)) == 1
    assert len(rasat.raporlari_ayikla(_next_data(kayit, 24), "LTFJ", 24)) == 1
    # hours=24 yaniti yalnizca dataLast tasirsa: OTOMATIK alan degisimi yok
    ters = _next_data(kayit, 0)
    with pytest.raises(rasat.AyiklamaHatasi, match="data"):
        rasat.raporlari_ayikla(ters, "LTFJ", 24)
    # hours=0 yolu eskisi gibi hosgoruru: dataLast yoksa bos liste
    assert rasat.raporlari_ayikla(_next_data(kayit, 24), "LTFJ", 0) == []


def test_rapor_sozlugu_eski_anahtarlari_ve_degerleri_ayni_ham_alanlar_EK():
    r = rasat.raporlari_ayikla(_next_data([_k("06:20", 55274848, ms="309", status=4,
                                              aciklama="CCA   ")], 0), "LTFJ", 0)[0]
    assert {k: r[k] for k in ("id", "tip", "duzeltme", "metin")} == {
        "id": 55274848, "tip": "METAR", "duzeltme": None,
        "metin": "METAR LTFJ 280620Z 02009KT 9999 FEW030 18/16 Q1014"}
    assert r["zaman"] == _t("2026-09-28T06:20:00.309")
    assert set(r) == {"id", "tip", "duzeltme", "zaman", "metin", "zaman_ham", "metin_ham",
                      "mgm_status", "mgm_status_aciklama", "mgm_type", "mgm_type_aciklama"}
    assert r["mgm_status_aciklama"] == "CCA   " and r["zaman_ham"].endswith(".309Z")


def test_raporlari_cek_varsayilani_hours0_ve_saat_parametresi(monkeypatch):
    gorulen, denemeler = [], []

    class Yanit:
        url, text = "u", ('<script id="__NEXT_DATA__" type="application/json">'
                          + json.dumps(_next_data([_k("07:20", 3)], 24)) + "</script>")

    def getir(params, timeout, deneme):
        gorulen.append(params)
        denemeler.append(deneme)
        return Yanit()

    monkeypatch.setattr(rasat, "_sayfayi_getir", getir)
    rasat.raporlari_cek("LTFJ")
    assert gorulen[-1] == [("stations", "LTFJ")] + rasat.EK_PARAMS
    assert rasat.EK_PARAMS == [("obsType", "1"), ("obsType", "2"), ("hours", "0")]
    assert denemeler[-1] == rasat.DENEME                    # canli: 3 deneme aynen
    assert len(rasat.raporlari_cek("LTFJ", saat=24, deneme=1)) == 1
    assert denemeler[-1] == 1
    assert gorulen[-1] == [("stations", "LTFJ"), ("obsType", "1"), ("obsType", "2"),
                           ("hours", "24")]


def test_ham_alanlar_panel_verisini_DEGISTIRMEZ(tmp_path):
    from ltfj_panel import panel_verisi_yaz
    ham = rasat.raporlari_ayikla(_next_data([_k("07:20", 3)], 0), "LTFJ", 0)
    eski = [{k: r[k] for k in ("id", "tip", "duzeltme", "zaman", "metin")} for r in ham]
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    panel_verisi_yaz(ham, [], a)
    panel_verisi_yaz(eski, [], b)
    ja, jb = json.loads(a.read_text()), json.loads(b.read_text())
    ja.pop("uretildi"), jb.pop("uretildi")
    assert ja == jb


# =================================================== bot entegrasyonu ====
def _bot():
    return ast.parse(Path("bot/ltfj_bot.py").read_text(encoding="utf-8"))


def test_bot_H24_cekimini_YALNIZCA_kosu_isle_ye_verilen_lambda_icinde_yapar():
    """Geri doldurma raporlari `raporlar` degiskenine / bildirim akisina
    hic girmemeli: saat= ile raporlari_cek yalnizca kosu_isle'nin
    argumanindaki lambda'da cagrilir."""
    kok = _bot()
    izinli = set()
    for d in ast.walk(kok):
        if (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                and d.func.attr == "kosu_isle"):
            for arg in d.args:
                if isinstance(arg, ast.Lambda):
                    izinli |= {id(x) for x in ast.walk(arg)}
    saatli = [d for d in ast.walk(kok)
              if isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
              and d.func.id == "raporlari_cek"
              and any(k.arg == "saat" for k in d.keywords)]
    assert saatli and all(id(d) in izinli for d in saatli)
    atamalar = [d for d in ast.walk(kok) if isinstance(d, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "raporlar" for t in d.targets)]
    assert len(atamalar) == 1                     # yalnizca canli hours=0 cagrisi


def test_bot_canli_hata_dalinda_arsiv_sagligini_fail_open_kaydeder():
    kok = _bot()
    for d in ast.walk(kok):
        if isinstance(d, ast.Try):
            cagrilar = [c for c in ast.walk(d) if isinstance(c, ast.Call)
                        and isinstance(c.func, ast.Attribute)
                        and c.func.attr == "canli_hata_kaydet"]
            if cagrilar and d.body and any(c in ast.walk(n) for n in d.body for c in cagrilar):
                assert "stderr" in ast.dump(ast.Module(body=d.handlers, type_ignores=[]))
                return
    pytest.fail("canli_hata_kaydet fail-open try icinde cagrilmiyor")


# ========================================================== is akislari ===
WF_BOT = Path(".github/workflows/ltfj.yml").read_text(encoding="utf-8")
WF_DOG = Path(".github/workflows/arsiv-dogrulama.yml").read_text(encoding="utf-8")


def test_bot_is_akisi_yeni_katmanlari_commit_eder_ve_uc_katmani_birlestirir():
    dosyalar = WF_BOT.split("DOSYALAR=")[1].split("\n")[0]
    for d in ("gozlem_surumleri.csv", "gozlem_arsivi_durum.json"):
        assert d in dosyalar
    # celiski kaydi ayri kalici dosya DEGIL (durum JSON'unda sayac)
    assert "catisma" not in WF_BOT
    assert "--birlestir-bizim /tmp/bizim_arsiv" in WF_BOT
    assert "/tmp/bizim_arsiv.csv" not in WF_BOT


def test_dogrulama_is_akisi_salt_okunur_ve_artifact_a_BAGIMLI_DEGIL():
    assert "contents: read" in WF_DOG and "actions: read" in WF_DOG
    for yasak in ("git push", "git commit", "contents: write", "schedule", "cron"):
        assert yasak not in WF_DOG
    assert "continue-on-error: true" in WF_DOG
    assert "steps.indir.outcome != 'success'" in WF_DOG
    assert "--canli" in WF_DOG


def test_bot_arsiv_dogrulama_betigini_CAGIRMAZ():
    """Replay yalnizca PR-2 dogrulamasi; production akisinda yok."""
    for dosya in ("bot/ltfj_bot.py", "bot/ltfj_gozlem_arsivi.py", ".github/workflows/ltfj.yml"):
        assert "arsiv_oynat" not in Path(dosya).read_text(encoding="utf-8")


def test_bot_geri_doldurmayi_TEK_deneme_ve_kisa_zaman_asimiyla_cagirir():
    """Bot is akisi 5 dk ile sinirli: geri doldurma canli akisin suresini
    tehlikeye atmamali (en kotu durum ~ baglanti 10 sn + okuma 20 sn)."""
    assert ga.BACKFILL_DENEME == 1 and ga.BACKFILL_ZAMAN_ASIMI <= 20
    lambdalar = [a for d in ast.walk(_bot()) if isinstance(d, ast.Call)
                 and isinstance(d.func, ast.Attribute) and d.func.attr == "kosu_isle"
                 for a in d.args if isinstance(a, ast.Lambda)]
    cagri = lambdalar[0].body
    kw = {k.arg: ast.unparse(k.value) for k in cagri.keywords}
    assert kw == {"timeout": "ltfj_gozlem_arsivi.BACKFILL_ZAMAN_ASIMI",
                  "saat": "ltfj_gozlem_arsivi.BACKFILL_SAAT",
                  "deneme": "ltfj_gozlem_arsivi.BACKFILL_DENEME"}


def test_sayfayi_getir_deneme_1_ise_tekrar_denemez(monkeypatch):
    import requests
    cagri = []

    def get(*a, **k):
        cagri.append(1)
        raise requests.Timeout("yavas")

    monkeypatch.setattr(rasat.requests, "get", get)
    monkeypatch.setattr(rasat.time, "sleep", lambda s: pytest.fail("beklememeli"))
    with pytest.raises(rasat.AgHatasi, match="1 denemede"):
        rasat._sayfayi_getir([("stations", "LTFJ")], 20, deneme=1)
    assert len(cagri) == 1
