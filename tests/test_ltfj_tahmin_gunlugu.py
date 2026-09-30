"""PR-3: V1 (Model A) ileriye donuk dogrulama - gunluk + eslestirici."""
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import ltfj_sayfa as sy
import ltfj_sis_olasilik as sis
import ltfj_tahmin_gunlugu as tg

UTC = timezone.utc
T0 = datetime(2026, 10, 1, 3, 50, tzinfo=UTC)


def _tahmin(z=T0, p=0.05, gorus=6000, hava=(), tip="METAR"):
    return {"zaman": z, "tip": tip, "olasilik": p, "gorus": gorus, "hava": list(hava),
            "spread": 1.0, "saat_sayfa": z.hour, "saat_gozlem": z.hour}


def _metar(z, gorus="9999", hava="", tip="METAR"):
    return {"zaman": z.isoformat(), "tip": tip, "gorus": gorus, "hava": hava}


def _tam_pencere(t, olay_k=None, eksik_k=()):
    out = []
    for k, z in enumerate(tg.slotlar(t)):
        if k in eksik_k:
            continue
        out.append(_metar(z, "0600" if k == olay_k else "9999", "FG" if k == olay_k else ""))
    return out


# ============================================================== tanimlar
@pytest.mark.parametrize("t,ilk,son", [
    (T0, "04:20", "06:50"),                                           # izgarada
    (datetime(2026, 10, 1, 13, 1, tzinfo=UTC), "13:20", "15:50"),     # SPECI
    (datetime(2026, 10, 1, 13, 20, 40, tzinfo=UTC), "13:50", "16:20"),
])
def test_her_tahmin_icin_tam_6_rutin_slot_t_haric_t3_dahil(t, ilk, son):
    s = tg.slotlar(t)
    assert len(s) == 6
    assert s[0].strftime("%H:%M") == ilk and s[-1].strftime("%H:%M") == son
    assert all(z.minute in (20, 50) for z in s)
    assert all(t < z <= t + timedelta(hours=3) for z in s)


@pytest.mark.parametrize("gorus,hava,beklenen", [
    ("0999", "", True), ("1000", "", False), ("9999", "FG", True),
    ("5000", "BCFG", False), ("5000", "MIFG", False), ("5000", "PRFG", False),
    ("5000", "VCFG", False), ("0600", "BCFG", True),          # gorus kolu yine sayar
    ("3000", "BR", False), ("", "", None), ("", "FG", True),
])
def test_olay_tanimi_egitimdekiyle_ayni(gorus, hava, beklenen):
    assert tg.olay_mi(gorus, hava) is beklenen


def test_bant_sinirlari_sayfadakiyle_ayni_kaynak():
    c = sis.TABAN_ORAN
    assert tg.bant(c * 1.99) == "dusuk"
    assert tg.bant(c * 2) == "orta" and tg.bant(c * 4.99) == "orta"
    assert tg.bant(c * 5) == "yuksek"
    kaynak = Path("ltfj_sayfa.py").read_text(encoding="utf-8")
    assert "bant_sinif = tahmin_gunlugu.bant(p)" in kaynak
    assert "if kat < 2:" not in kaynak                   # ikinci kopya yok


def test_model_surumu_katsayilardan_turetiliyor(monkeypatch):
    a = tg.model_surumu()
    assert a.startswith("A-") and len(a) == 12 and a == tg.model_surumu()
    monkeypatch.setitem(sis.KATSAYILAR, "gorus", 9.9)
    assert tg.model_surumu() != a


# ================================================================ gunluk
def test_kaydet_ekleme_yalnizca_ilk_kayit_kalir(tmp_path):
    d = tmp_path / "g.csv"
    assert tg.kaydet(_tahmin(p=0.05), d, T0 + timedelta(minutes=4))
    assert not tg.kaydet(_tahmin(p=0.90), d, T0 + timedelta(minutes=34))
    satirlar = tg.oku(d)
    assert len(satirlar) == 1
    assert float(satirlar[0]["olasilik"]) == pytest.approx(0.05)
    assert satirlar[0]["kayit_zamani"].startswith("2026-10-01T03:54")
    assert tuple(csv.DictReader(d.open(encoding="utf-8")).fieldnames) == tg.SUTUNLAR


def test_tahmin_yoksa_satir_yazilmaz(tmp_path):
    d = tmp_path / "g.csv"
    assert not tg.kaydet(None, d)
    assert not tg.kaydet(_tahmin(p=None), d)
    assert not d.exists()


def test_olay_surerken_verilen_tahmin_evren_disi(tmp_path):
    d = tmp_path / "g.csv"
    tg.kaydet(_tahmin(gorus=300, hava=["FG"]), d, T0)
    assert tg.oku(d)[0]["evren"] == "olay_suruyor"
    tg.kaydet(_tahmin(z=T0 + timedelta(minutes=30), gorus=6000), d, T0)
    assert tg.oku(d)[1]["evren"] == "onset"


def test_birlestir_simetrik_idempotent_ve_once_kaydedilen_kalir():
    erken = tg.satir_kur(_tahmin(p=0.1), T0 + timedelta(minutes=4))
    gec = tg.satir_kur(_tahmin(p=0.2), T0 + timedelta(minutes=34))
    baska = tg.satir_kur(_tahmin(z=T0 + timedelta(minutes=30)), T0)
    ab = tg.birlestir([erken, baska], [gec])
    ba = tg.birlestir([gec], [erken, baska])
    anahtar = lambda xs: sorted((x["gozlem_zaman"], x["olasilik"]) for x in xs)
    assert anahtar(ab) == anahtar(ba) == anahtar(tg.birlestir(ab, ab))
    assert {x["olasilik"] for x in ab} == {erken["olasilik"], baska["olasilik"]}


def test_cli_birlestir_bizim(tmp_path):
    uzak, bizim = tmp_path / "tahmin_gunlugu.csv", tmp_path / "bizim.csv"
    tg.kaydet(_tahmin(), uzak, T0)
    tg.kaydet(_tahmin(z=T0 + timedelta(minutes=30)), bizim, T0)
    assert tg.main(["--birlestir-bizim", str(bizim), "--dosya", str(uzak)]) == 0
    assert len(tg.oku(uzak)) == 2


# =========================================================== eslestirici
def _g(p=0.05, evren="onset", z=T0):
    s = tg.satir_kur(_tahmin(z=z, p=p), z)
    s["evren"] = evren
    return s


def test_olay_gorulunce_ufuk_dolmadan_kesinlesir():
    arsiv = _tam_pencere(T0, olay_k=1)[:2]              # yalnizca ilk iki slot
    s = tg.sonuclandir([_g()], arsiv, T0 + timedelta(minutes=70))[0]
    assert s["durum"] == "oldu" and s["ilk_olay"].startswith("2026-10-01T04:50")


def test_olmadi_icin_6_slotun_HEPSI_gozlenmis_olmali():
    tam = tg.sonuclandir([_g()], _tam_pencere(T0), T0 + timedelta(hours=4))[0]
    assert tam["durum"] == "olmadi"
    eksik = _tam_pencere(T0, eksik_k=(3,))
    assert tg.sonuclandir([_g()], eksik, T0 + timedelta(hours=2))[0]["durum"] == "bekliyor"
    assert tg.sonuclandir([_g()], eksik, T0 + timedelta(hours=5))[0]["durum"] == "eksik_bekleniyor"
    assert tg.sonuclandir([_g()], eksik, T0 + timedelta(hours=28))[0]["durum"] == "belirsiz"


def test_gorusu_bilinmeyen_slot_gozlenmis_sayilmaz():
    arsiv = _tam_pencere(T0)
    arsiv[2]["gorus"] = ""
    assert tg.sonuclandir([_g()], arsiv, T0 + timedelta(hours=30))[0]["durum"] == "belirsiz"


def test_SPECI_olayi_asil_sonucu_degistirmez_ama_gosterilir():
    arsiv = _tam_pencere(T0) + [_metar(T0 + timedelta(minutes=45), "0800", "FG", tip="SPECI")]
    s = tg.sonuclandir([_g()], arsiv, T0 + timedelta(hours=4))[0]
    assert s["durum"] == "olmadi" and s["speci_olay"] is True


def test_pencere_disindaki_olay_sayilmaz():
    arsiv = _tam_pencere(T0) + [_metar(T0, "0300", "FG"),
                                _metar(T0 + timedelta(hours=3, minutes=30), "0300", "FG")]
    assert tg.sonuclandir([_g()], arsiv, T0 + timedelta(hours=5))[0]["durum"] == "olmadi"


# =============================================================== olcumler
def test_wilson_bilinen_degerler():
    lo, hi = tg.wilson(0, 10)
    assert lo == 0 and hi == pytest.approx(0.2775, abs=1e-3)
    lo, hi = tg.wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-3) and hi == pytest.approx(0.7634, abs=1e-3)
    assert tg.wilson(0, 0) is None


def test_ozet_evren_disi_ve_belirsizi_dislar_ama_sayar():
    s = [{"evren": "onset", "durum": "oldu", "olasilik": 0.3, "bant": "yuksek"},
         {"evren": "onset", "durum": "olmadi", "olasilik": 0.004, "bant": "dusuk"},
         {"evren": "onset", "durum": "belirsiz", "olasilik": 0.5, "bant": "yuksek"},
         {"evren": "onset", "durum": "bekliyor", "olasilik": 0.5, "bant": "yuksek"},
         {"evren": "olay_suruyor", "durum": "oldu", "olasilik": 0.9, "bant": "yuksek"}]
    o = tg.ozet(s)
    assert o["n"] == 2 and o["olay"] == 1
    assert o["sayim"]["belirsiz"] == 1 and o["sayim"]["bekliyor"] == 1
    assert o["sayim"]["evren_disi"] == 1
    assert o["bantlar"]["yuksek"]["n"] == 1 and o["bantlar"]["dusuk"]["olay"] == 0
    assert o["brier"] == pytest.approx(((0.3 - 1) ** 2 + 0.004 ** 2) / 2)
    assert o["bss"] is None                         # 10 olaydan az: yorumlanmaz


def test_bss_yalnizca_yorum_esiginden_sonra():
    s = ([{"evren": "onset", "durum": "oldu", "olasilik": 0.4, "bant": "yuksek"}] * 10
         + [{"evren": "onset", "durum": "olmadi", "olasilik": 0.01, "bant": "dusuk"}] * 90)
    o = tg.ozet(s)
    assert o["bss"] is not None and o["bss"] > 0


def test_dogrulama_verisi_dosyalardan(tmp_path):
    tg.kaydet(_tahmin(), tmp_path / tg.DOSYA_ADI, T0)
    with (tmp_path / "gozlem_arsivi.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["zaman", "tip", "gorus", "hava"])
        w.writeheader()
        for r in _tam_pencere(T0, olay_k=2):
            w.writerow(r)
    v = tg.dogrulama_verisi(tmp_path, T0 + timedelta(hours=4))
    assert v["sonuclar"][0]["durum"] == "oldu"
    assert v["ozet"]["olay"] == 1 and v["baslangic"].startswith("2026-10-01T03:50")


# ==================================================== sayfa + bot + workflow
def test_sis_tahmini_sayfanin_gosterdigi_deger():
    z = datetime(2026, 10, 1, 3, 50, tzinfo=UTC)
    rapor = {"tip": "METAR", "icao": "LTFJ", "zaman": z,
             "metin": "LTFJ 010350Z 36004KT 4000 BR SCT003 11/11 Q1016"}
    simdi = z + timedelta(minutes=34)
    t = sy.sis_tahmini([rapor], [], simdi)
    from ltfj_analiz import metar_coz
    assert t["olasilik"] == sy._sis_olasiligi_hesapla(metar_coz(rapor["metin"]), [], simdi)
    assert (t["saat_gozlem"], t["saat_sayfa"]) == (3, 4)   # fark kaydediliyor
    assert t["tip"] == "METAR" and t["zaman"] == z


def test_sis_tahmini_en_YENI_gozlemi_seciyor():
    eski = {"tip": "SPECI", "zaman": T0, "metin": "LTFJ 010350Z 36004KT 4000 BR 11/10 Q1016"}
    yeni = {"tip": "METAR", "zaman": T0 + timedelta(minutes=30),
            "metin": "LTFJ 010420Z 36004KT 9999 FEW030 12/08 Q1016"}
    taf = {"tip": "TAF", "zaman": T0 + timedelta(hours=1), "metin": "LTFJ 010500Z 0106/0206 36005KT 9999"}
    assert sy.sis_tahmini([eski, taf, yeni], [], T0 + timedelta(hours=1))["zaman"] == yeni["zaman"]


def _arsiv_yaz(klasor, satirlar):
    with (klasor / "gozlem_arsivi.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["zaman", "tip", "gorus", "hava"])
        w.writeheader()
        for r in satirlar:
            w.writerow(r)


def test_okuma_dosyasi_tahmin_karsisinda_6_metar_ve_sonuc(tmp_path):
    tg.kaydet(_tahmin(p=0.31), tmp_path / tg.DOSYA_ADI, T0)
    tg.kaydet(_tahmin(z=T0 - timedelta(hours=1), p=0.004), tmp_path / tg.DOSYA_ADI, T0)
    _arsiv_yaz(tmp_path, _tam_pencere(T0, olay_k=1)[:3]
               + [_metar(T0 + timedelta(minutes=45), "0900", "FG", tip="SPECI")])
    simdi = T0 + timedelta(minutes=120)
    o = tg.dogrulama_yaz(tmp_path, simdi)
    satirlar = list(csv.DictReader((tmp_path / tg.DOGRULAMA_DOSYA_ADI).open(encoding="utf-8")))
    assert tuple(satirlar[0].keys()) == tg.DOGRULAMA_SUTUNLARI
    ust = satirlar[0]                                    # en yeni ustte
    assert ust["gozlem_zaman"] == "2026-10-01 03:50Z" and ust["olasilik_yuzde"] == "31.0"
    assert ust["sonuc"] == "oldu" and ust["ilk_olay"] == "04:50"
    assert ust["slot_1"] == "04:20 9999"
    assert ust["slot_2"] == "04:50 0600 FG [OLAY]"
    assert ust["slot_4"] == "05:50 henuz"                # gelecekte: eksik DEGIL
    assert ust["speci_olay"] == "04:35 0900 FG"
    assert satirlar[1]["slot_1"] == "03:20 yok"          # beklenmesi gereken, arsivde yok
    assert satirlar[1]["sonuc"] == "oldu"                # 02:50 penceresi 04:50yi de kapsar
    assert o["olay"] == 2


def test_gunluk_bossa_okuma_dosyasi_yazilmaz(tmp_path):
    tg.dogrulama_yaz(tmp_path, T0)
    assert not (tmp_path / tg.DOGRULAMA_DOSYA_ADI).exists()


def test_okuma_dosyasi_turetilmis_yeniden_uretilir(tmp_path):
    tg.kaydet(_tahmin(), tmp_path / tg.DOSYA_ADI, T0)
    _arsiv_yaz(tmp_path, [])
    tg.dogrulama_yaz(tmp_path, T0 + timedelta(minutes=10))
    assert "bekliyor" in (tmp_path / tg.DOGRULAMA_DOSYA_ADI).read_text(encoding="utf-8")
    _arsiv_yaz(tmp_path, _tam_pencere(T0))
    assert tg.main(["--dogrulama-yaz", "--dosya", str(tmp_path / tg.DOSYA_ADI)]) == 0
    assert "olmadi" in (tmp_path / tg.DOGRULAMA_DOSYA_ADI).read_text(encoding="utf-8")


def test_sayfaya_BASILMIYOR():
    """Kullanici istedi: dosyada tutulsun, sayfada gosterilmesin."""
    kaynak = Path("ltfj_sayfa.py").read_text(encoding="utf-8")
    assert "_dogrulama_html" not in kaynak and "tahmin_dogrulama" not in kaynak
    assert "dg-slot" not in Path("sayfa_kaynak/stil.css").read_text(encoding="utf-8")


def test_bot_fail_open():
    kaynak = Path("ltfj_bot.py").read_text(encoding="utf-8")
    blok = kaynak.split("# ILERIYE DONUK DOGRULAMA (PR-3)")[1].split("sayfa_yaz(raporlar")[0]
    assert "try:" in blok and "except Exception" in blok
    assert "ltfj_tahmin_gunlugu.kaydet(" in blok and "dogrulama_yaz(KLASOR)" in blok


def test_workflow_gunlugu_commit_eder_ve_cakismada_birlestirir():
    wf = Path(".github/workflows/ltfj.yml").read_text(encoding="utf-8")
    dosyalar = wf.split("DOSYALAR=")[1].split("\n")[0]
    assert "tahmin_gunlugu.csv" in dosyalar and "tahmin_dogrulama.csv" in dosyalar
    assert "cp tahmin_gunlugu.csv /tmp/bizim_tahmin_gunlugu.csv" in wf
    assert "python -m ltfj_tahmin_gunlugu --birlestir-bizim /tmp/bizim_tahmin_gunlugu.csv" in wf
    # yedek, reset'ten ONCE; birlestirme reset'ten SONRA
    assert wf.index("cp tahmin_gunlugu.csv /tmp/") < wf.index('git reset --hard "origin/${DAL}"') \
        < wf.index("--birlestir-bizim /tmp/bizim_tahmin_gunlugu.csv") \
        < wf.index("python -m ltfj_tahmin_gunlugu --dogrulama-yaz")


def test_bot_sis_modeli_ni_import_etmiyor():
    kaynak = Path("ltfj_tahmin_gunlugu.py").read_text(encoding="utf-8")
    assert "sis_modeli" not in "\n".join(l for l in kaynak.splitlines()
                                         if l.startswith(("import", "from")))
