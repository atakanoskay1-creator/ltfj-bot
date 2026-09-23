"""SPECI'li gozlem arsivi - ekleme-yalnizca dosyanin sozlesmesi.

EN KRITIK UC SEY:
  1) SPECI GERCEKTEN GIRIYOR ve GORUS GERCEKTEN SAKLANIYOR - dosyanin tum
     varlik sebebi bu. (Egitim arsivi SPECI tasimiyor, olcum_gecmisi gorus
     tasimiyor; bkz. ltfj_gozlem_arsivi modul aciklamasi.)
  2) HICBIR SATIR KAYBOLMUYOR - ne tekrar eklemede, ne birlestirmede.
     Ekleme-yalnizca bir dosyada veri kaybi sessizdir ve geri alinamaz.
  3) TEK BOZUK RAPOR TUM EKLEMEYI DUSURMUYOR - bot akisi bu dosyaya
     bagimli degil.
"""
from datetime import datetime, timedelta, timezone

import pytest

import ltfj_gozlem_arsivi as ga


def _rapor(dk, tip="METAR", metin=None):
    return {"tip": tip,
            "zaman": datetime(2026, 9, 23, 6, 0, tzinfo=timezone.utc) + timedelta(minutes=dk),
            "metin": metin or f"{tip} LTFJ 230600Z 0000KT"}


def _coz(metin):
    """metar_coz yerine gecen sahte cozucu - bu modul ltfj_analiz'e
    bagimli olmamali (bagimliysa test bunu yakalar)."""
    return {"gorus": 350, "tavan": 100, "sicaklik": 14.0, "cig_noktasi": 13.5,
            "ruzgar_yon": 0, "ruzgar_hiz": 0, "ruzgar_hamle": None,
            "qnh": 1015, "hava": ["FG"], "cavok": False}


@pytest.fixture
def dosya(tmp_path):
    return tmp_path / "gozlem_arsivi.csv"


# ------------------------------------------------- 1) SPECI ve gorus
def test_SPECI_arsive_giriyor(dosya):
    ga.ekle([_rapor(0, "METAR"), _rapor(7, "SPECI")], _coz, dosya)
    tipler = [s["tip"] for s in ga.oku(dosya)]
    assert tipler.count("SPECI") == 1, "SPECI dusuruluyor - dosyanin tum amaci bu"


def test_gorus_alani_SAKLANIYOR(dosya):
    """state['olcum_gecmisi'] gorusu atiyor; burada atilmamali."""
    ga.ekle([_rapor(0)], _coz, dosya)
    assert ga.oku(dosya)[0]["gorus"] == "350"


def test_tum_sutunlar_yaziliyor(dosya):
    ga.ekle([_rapor(0)], _coz, dosya)
    satir = ga.oku(dosya)[0]
    assert set(satir) == set(ga.SUTUNLAR)
    assert satir["hava"] == "FG" and satir["cavok"] == "0"


def test_hava_listesi_bosluk_ayrili_dizeye_ceviriliyor(dosya):
    """Egitim arsivindeki 'hava' sutunuyla ayni bicim olmali ki iki
    kaynak ileride birlestirilebilsin."""
    ga.ekle([_rapor(0)], lambda m: {"hava": ["BCFG", "BR"]}, dosya)
    assert ga.oku(dosya)[0]["hava"] == "BCFG BR"


def test_TAF_arsive_GIRMIYOR(dosya):
    """Arsiv gozlem arsivi - tahmin degil."""
    assert ga.ekle([_rapor(0, "TAF")], _coz, dosya) == 0


def test_zamansiz_rapor_atlaniyor(dosya):
    r = _rapor(0)
    r["zaman"] = None
    assert ga.ekle([r], _coz, dosya) == 0


# ------------------------------------------------- 2) satir kaybi yok
def test_ayni_rapor_ikinci_kez_eklenmiyor(dosya):
    """Bot her kosuda MGM'den ayni son raporlari yeniden gorur."""
    raporlar = [_rapor(0), _rapor(7, "SPECI")]
    assert ga.ekle(raporlar, _coz, dosya) == 2
    assert ga.ekle(raporlar, _coz, dosya) == 0
    assert len(ga.oku(dosya)) == 2


def test_ayni_zamanda_METAR_ve_SPECI_ikisi_de_kaliyor(dosya):
    """Tekillik anahtari (zaman, tip) - yalnizca zaman olsaydi ayni
    dakikadaki SPECI METAR'i ezerdi."""
    ga.ekle([_rapor(0, "METAR"), _rapor(0, "SPECI")], _coz, dosya)
    assert len(ga.oku(dosya)) == 2


def test_eski_satirlar_yeni_eklemede_korunuyor(dosya):
    ga.ekle([_rapor(0)], _coz, dosya)
    ga.ekle([_rapor(30)], _coz, dosya)
    assert len(ga.oku(dosya)) == 2


def test_dosya_zamana_gore_sirali_yaziliyor(dosya):
    """Gec gelen bir SPECI dosyayi sirasizlastirmamali."""
    ga.ekle([_rapor(60), _rapor(0), _rapor(30)], _coz, dosya)
    zamanlar = [s["zaman"] for s in ga.oku(dosya)]
    assert zamanlar == sorted(zamanlar)


def test_zaman_UTC_ve_saniye_hassasiyetinde(dosya):
    ga.ekle([_rapor(0)], _coz, dosya)
    assert ga.oku(dosya)[0]["zaman"] == "2026-09-23T06:00:00+00:00"


def test_yerel_saatli_rapor_UTC_ye_ceviriliyor(dosya):
    """MGM yerel saatli bir damga verirse arsivde UTC'ye normalize
    edilmeli - yoksa gecis sureleri 3 saat kayar."""
    r = _rapor(0)
    r["zaman"] = datetime(2026, 9, 23, 9, 0, tzinfo=timezone(timedelta(hours=3)))
    ga.ekle([r], _coz, dosya)
    assert ga.oku(dosya)[0]["zaman"].startswith("2026-09-23T06:00:00")


def test_olmayan_dosya_okumasi_bos_liste(dosya):
    """Ilk kosu bir hata degil."""
    assert ga.oku(dosya) == []


# ------------------------------------------------- birlestirme (yaris hali)
def test_birlestirme_iki_tarafin_satirlarini_da_tutuyor(dosya, tmp_path):
    ga.ekle([_rapor(0)], _coz, dosya)
    oteki = tmp_path / "oteki.csv"
    ga.ekle([_rapor(30)], _coz, oteki)
    ga.birlestir(dosya, oteki, dosya)
    assert [s["zaman"][11:16] for s in ga.oku(dosya)] == ["06:00", "06:30"]


def test_birlestirme_ortak_satirlari_KOPYALAMIYOR(dosya, tmp_path):
    ga.ekle([_rapor(0), _rapor(30)], _coz, dosya)
    oteki = tmp_path / "oteki.csv"
    ga.ekle([_rapor(30), _rapor(60)], _coz, oteki)
    assert ga.birlestir(dosya, oteki, dosya) == 3


def test_birlestirme_uzak_dosya_YOKKEN_calisiyor(dosya, tmp_path):
    """Workflow'da uzaktaki dalda arsiv henuz olmayabilir."""
    ga.ekle([_rapor(0)], _coz, dosya)
    assert ga.birlestir(tmp_path / "yok.csv", dosya, dosya) == 1


# ------------------------------------------------- 3) fail-open / dayaniklilik
def test_tek_bozuk_rapor_digerlerini_DUSURMUYOR(dosya, capsys):
    def ara_sira_patla(metin):
        if "PATLA" in metin:
            raise ValueError("cozulemedi")
        return _coz(metin)

    n = ga.ekle([_rapor(0), _rapor(7, "SPECI", metin="SPECI PATLA"), _rapor(30)],
                ara_sira_patla, dosya)
    assert n == 2
    assert "atlan" in capsys.readouterr().err       # sessizce yutulmuyor


def test_eksik_alanlar_bos_yaziliyor_cokme_yok(dosya):
    ga.ekle([_rapor(0)], lambda m: {}, dosya)
    satir = ga.oku(dosya)[0]
    assert satir["gorus"] == "" and satir["tavan"] == ""


def test_modul_agir_bagimlilik_ICE_AKTARMIYOR():
    """Bot akisindaki fail-open try/except'in isini kolaylastirir: bu
    modul yalnizca stdlib kullanir, import'u patlamaz."""
    import ast
    from pathlib import Path
    kok = ast.parse(Path(ga.__file__).read_text(encoding="utf-8"))
    adlar = set()
    for d in ast.walk(kok):
        if isinstance(d, ast.Import):
            adlar |= {a.name.split(".")[0] for a in d.names}
        elif isinstance(d, ast.ImportFrom) and d.module:
            adlar.add(d.module.split(".")[0])
    assert adlar <= {"csv", "sys", "datetime", "pathlib", "argparse"}, adlar


def test_gorus_gercek_metar_cozucusuyle_de_geliyor(dosya):
    """Sahte cozucu gercek sozlesmeyi gizlemesin: ltfj_analiz.metar_coz
    ciktisi _satir_kur'un bekledigi anahtarlari tasiyor mu."""
    from ltfj_analiz import metar_coz
    r = _rapor(0, "SPECI", metin="SPECI LTFJ 230607Z 00000KT 0300 FG VV002 13/13 Q1015")
    ga.ekle([r], metar_coz, dosya)
    satir = ga.oku(dosya)[0]
    assert satir["gorus"] == "300" and satir["tip"] == "SPECI"
    assert satir["sicaklik"] == "13" and "FG" in satir["hava"]


def test_CAVOK_bayragi_yaziliyor(dosya):
    from ltfj_analiz import metar_coz
    ga.ekle([_rapor(0, metin="METAR LTFJ 230600Z 00000KT CAVOK 20/10 Q1015")],
            metar_coz, dosya)
    assert ga.oku(dosya)[0]["cavok"] == "1"


# ------------------------------------------------- CLI (workflow bunu cagiriyor)
def test_cli_birlestir_calisiyor(dosya, tmp_path, capsys):
    a = tmp_path / "a.csv"
    ga.ekle([_rapor(0)], _coz, a)
    ga.ekle([_rapor(30)], _coz, dosya)
    assert ga.main(["--birlestir", str(a), str(dosya), "--dosya", str(dosya)]) == 0
    assert len(ga.oku(dosya)) == 2
    assert "SPECI" in capsys.readouterr().out       # ozet basiliyor


def test_cli_bos_arsivde_cokmuyor(tmp_path, capsys):
    assert ga.main(["--dosya", str(tmp_path / "yok.csv")]) == 0
    assert "boş" in capsys.readouterr().out


# ------------------------------------------------- bot entegrasyonu (AST)
def _bot_agaci():
    import ast
    from pathlib import Path
    return ast.parse(Path("ltfj_bot.py").read_text(encoding="utf-8"))


def _arsiv_cagrisini_saran_try():
    """ltfj_gozlem_arsivi.ekle cagrisini SARAN try dugumunu bulur."""
    import ast
    for dugum in ast.walk(_bot_agaci()):
        if not isinstance(dugum, ast.Try):
            continue
        for ic in ast.walk(dugum):
            if (isinstance(ic, ast.Call)
                    and isinstance(ic.func, ast.Attribute)
                    and ic.func.attr == "ekle"
                    and isinstance(ic.func.value, ast.Name)
                    and ic.func.value.id == "ltfj_gozlem_arsivi"):
                return dugum
    return None


def test_bot_arsiv_cagrisini_try_ICINDE_yapiyor():
    """FAIL-OPEN: arsiv yazilamazsa METAR/TAF/push akisi durmamali."""
    assert _arsiv_cagrisini_saran_try() is not None, \
        "ltfj_gozlem_arsivi.ekle korumasiz cagriliyor"


def test_bot_arsiv_hatasini_YUTMUYOR_yaziyor():
    """Fail-open sessiz-open olmamali: hata stderr'e dusmeli."""
    import ast
    dugum = _arsiv_cagrisini_saran_try()
    govde = ast.dump(ast.Module(body=dugum.handlers, type_ignores=[]))
    assert "stderr" in govde, "arsiv hatasi sessizce yutuluyor"


def test_bot_arsivi_state_yazmadan_ONCE_guncelliyor():
    """Arsiv cagrisi raporlar elde edildikten sonra, `return` eden
    'rapor donmedi' dalindan once olmali - yoksa hicbir zaman
    calismayan bir kod parcasi olur."""
    import ast
    kaynak = __import__("pathlib").Path("ltfj_bot.py").read_text(encoding="utf-8")
    kok = ast.parse(kaynak)
    arsiv_satiri = _arsiv_cagrisini_saran_try().lineno
    olcum = next(d.lineno for d in ast.walk(kok)
                 if isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
                 and d.func.id == "olcum_gecmisini_guncelle")
    assert arsiv_satiri < olcum


# ------------------------------------- arsiv -> gecis analizi (olu uc degil)
def test_gecis_analizi_arsivi_DOGRUDAN_okuyabiliyor(dosya):
    """Arsivin varlik sebebi bu zincir: SPECI'li gozlem -> gorus gecis
    sureleri. Bicim uyusmazsa dosya olu bir uc olur."""
    from datetime import datetime as dt
    from sis_modeli import gorus_gecis

    # <2km 4 saat, icinde <1km 2 saat, karsiz -> TR07 olayi
    gorusler = ([9999] * 12 + [1500] * 4 + [500] * 4 + [1500] * 4 + [9999] * 12)
    raporlar = []
    for i, v in enumerate(gorusler):
        raporlar.append({
            "tip": "METAR",
            "zaman": dt(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=30 * i),
            "metin": f"m{i}",
            "_g": v,
        })
    ga.ekle(raporlar, lambda m: {"gorus": gorusler[int(m[1:])], "hava": ""}, dosya)

    satirlar = gorus_gecis.veri_oku(dosya)
    assert len(satirlar) == len(gorusler)
    assert len(gorus_gecis.olaylari_bul(satirlar)) == 1


def test_gecis_analizi_SPECI_cozunurlugunu_goruyor(dosya):
    """30 dk izgarasinin altindaki bir SPECI arsivde kendi satirini
    aliyor - 0.5 saat tabanini kiran sey tam olarak bu."""
    from datetime import datetime as dt
    from sis_modeli import gorus_gecis

    raporlar = [
        {"tip": "METAR", "zaman": dt(2026, 1, 1, 6, 20, tzinfo=timezone.utc), "metin": "a"},
        {"tip": "SPECI", "zaman": dt(2026, 1, 1, 6, 37, tzinfo=timezone.utc), "metin": "b"},
        {"tip": "METAR", "zaman": dt(2026, 1, 1, 6, 50, tzinfo=timezone.utc), "metin": "c"},
    ]
    gorusler = {"a": 3000, "b": 800, "c": 400}
    ga.ekle(raporlar, lambda m: {"gorus": gorusler[m], "hava": ""}, dosya)

    dakikalar = [s["dt"].minute for s in gorus_gecis.veri_oku(dosya)]
    assert dakikalar == [20, 37, 50]
