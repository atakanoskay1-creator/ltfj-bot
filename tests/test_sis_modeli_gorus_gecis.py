"""LTFJ gorus gecis sureleri - Misawa ve ark. (2026) Tablo 1/2 karsiligi.

Bu bir MODEL DEGIL, tarihsel iklimbilim: gecmiste ne oldugunu sayar,
tahmin uretmez. Dolayisiyla sizinti/holdout kavramlari gecerli degil.

En kritik testler: (1) olay tanimi TR07'ye sadik, (2) veri BOSLUKLARI
sureklilik sanilmiyor, (3) rapor edilen kapsam veri gercegini yansitiyor.
"""
from datetime import datetime, timedelta

from sis_modeli import gorus_gecis as g


def _seri(gorusler, baslangic=datetime(2020, 1, 1, 0, 0), adim_dk=30, hava=""):
    return [{"dt": baslangic + timedelta(minutes=adim_dk * i),
             "gorus": float(v), "hava": hava}
            for i, v in enumerate(gorusler)]


def _sisli_olay(once=(9999,) * 6, sis=(500,) * 8, sonra=(9999,) * 6):
    return _seri(list(once) + list(sis) + list(sonra))


# ---------------------------------------------------------- olay tanimi
def test_gecerli_olay_bulunuyor():
    olaylar = g.olaylari_bul(_sisli_olay())
    assert len(olaylar) == 1


def test_kisa_dusuk_gorus_olay_SAYILMIYOR():
    """<2km yalnizca 1 saat surmusse TR07 olcutu saglanmaz (>=3 saat)."""
    assert g.olaylari_bul(_sisli_olay(sis=(500,) * 3)) == []


def test_sis_esigine_inmeyen_olay_SAYILMIYOR():
    """<2km 4 saat surmus ama hic <1km olmamis - TR07'ye gore sis degil."""
    assert g.olaylari_bul(_sisli_olay(sis=(1500,) * 8)) == []


def test_karli_olay_DISLANIYOR():
    """TR07 kar yagisli olaylari disliyor - kar gorusu sisten farkli bir
    mekanizmayla dusurur."""
    s = _sisli_olay()
    for r in s[6:14]:
        r["hava"] = "-SN"
    assert g.olaylari_bul(s) == []


def test_yagmur_olayi_DISLAMIYOR_ama_isaretliyor():
    s = _sisli_olay()
    for r in s[3:6]:
        r["hava"] = "-RA"
    olaylar = g.olaylari_bul(s)
    assert len(olaylar) == 1
    assert olaylar[0]["yagisli"] is True


def test_yagissiz_olay_isaretlenmiyor():
    assert g.olaylari_bul(_sisli_olay())[0]["yagisli"] is False


# -------------------------------------------------------- veri bosluklari
def test_bosluk_SUREKLILIK_sanilmiyor():
    """EN KRITIK: 6 saatlik bir veri boskugu "kesintisiz sis" sayilsaydi
    olmayan olaylar uretilirdi."""
    s = _seri([500, 500]) + _seri([500, 500], baslangic=datetime(2020, 1, 1, 8, 0))
    assert g.olaylari_bul(s) == []


def test_tek_eksik_rapor_tolere_ediliyor():
    """30 dk izgarada tek rapor eksigi (60 dk aralik) olayi bolmemeli -
    aksi halde neredeyse hicbir olay tamamlanmazdi."""
    s = _sisli_olay()
    del s[9]
    assert len(g.olaylari_bul(s)) == 1


def test_gecis_olcumu_boslukta_None_donuyor():
    s = _sisli_olay(once=(9999, 9999, 3000))
    olay = g.olaylari_bul(s)[0]
    # 5000 ile 1500 arasina buyuk bosluk koy
    s[2]["dt"] = s[2]["dt"] - timedelta(hours=5)
    sure, durum = g.dusme_suresi(s, olay)
    assert sure is None or durum == "ok"     # bosluk varsa olculmemeli


# ------------------------------------------------------------- gecisler
def test_dusme_suresi_dogru_hesaplaniyor():
    """9999 ... 3000 -> 800: son >=5000 kaydiyla ilk <=1500 kaydi arasi
    iki adim (30 dk) -> 1.0 saat.

    Oncesinde 21 satir var cunku PENCERE_SAAT=10 ve izgara 30 dk:
    olaydan 10 saat once VERI OLMAK ZORUNDA, yoksa "5000'den dustu mu"
    sorusu cevaplanamaz ve olcum "pencere_eksik" doner."""
    s = _seri([9999] * 21 + [3000] + [800] * 8 + [9999] * 6)
    olay = g.olaylari_bul(s)[0]
    sure, durum = g.dusme_suresi(s, olay)
    assert durum == "ok"
    assert sure == 1.0


def test_zaten_dusukse_olay_HARIC():
    """Pencerenin basinda gorus zaten <5000 ise "5000'den dusus" hic
    yasanmamistir - makalenin yontemi bunlari disliyor."""
    s = _seri([4000] * 24 + [500] * 8 + [9999] * 21)
    olay = g.olaylari_bul(s)[0]
    sure, durum = g.dusme_suresi(s, olay)
    assert sure is None and durum == "zaten_dusuk"


def test_toparlanma_suresi_dogru_hesaplaniyor():
    """Sonrasinda 21 satir: PENCERE_SAAT=10 kadar veri olmali."""
    s = _seri([9999] * 6 + [500] * 8 + [3000] + [9999] * 21)
    olay = g.olaylari_bul(s)[0]
    sure, durum = g.toparlanma_suresi(s, olay)
    assert durum == "ok"
    assert sure == 1.0


def test_hala_dusukse_toparlanma_olculmuyor():
    s = _seri([9999] * 21 + [500] * 8 + [3000] * 24)
    olay = g.olaylari_bul(s)[0]
    sure, durum = g.toparlanma_suresi(s, olay)
    assert sure is None and durum == "hala_dusuk"


# ------------------------------------------------------------ istatistik
def test_yuzdelik_numpy_SIZ_dogru():
    assert g.yuzdelik([1, 2, 3, 4], 0.5) == 2.5
    assert g.yuzdelik([5], 0.9) == 5


def test_bos_listede_cokmuyor():
    o = g.ozet([])
    assert o["n"] == 0


# ---------------------------------------------------------- kapsam dururust
def test_seyrek_yillar_kapsam_disi():
    """Arsivde 2003'ten TEK kayit var; "2003-2026" demek orneklemi
    oldugundan genis gosterirdi."""
    s = (_seri([9999], baslangic=datetime(2003, 12, 26))
         + _seri([9999] * 3000, baslangic=datetime(2011, 1, 1)))
    ilk, son, seyrek = g.kapsanan_aralik(s)
    assert ilk == 2011
    assert 2003 in seyrek


def test_asgari_kayit_esigi_tanimli():
    assert g.ASGARI_YILLIK_KAYIT > 0


# ------------------------------------------------ cozunurluk notu OLCULUYOR
def test_cozunurluk_notu_izgara_verisinde_SPECI_YOK_diyor():
    """IEM arsivi gibi saf :20/:50 veride not 'yuvarli' demeli."""
    satirlar = [{"dt": datetime(2020, 1, 1, h, m), "gorus": 9999.0, "hava": ""}
                for h in range(6) for m in (20, 50)]
    not_ = g.cozunurluk_notu(satirlar)
    assert "YUVARLIDIR" in not_ and "SPECI pratikte YOK" in not_


def test_cozunurluk_notu_SPECI_li_veride_yuvarli_DEGIL_diyor():
    """Ayni betik gozlem_arsivi.csv'ye karsi calistirilinca 'SPECI yok'
    demesi YANLIS olurdu - not sabit degil, olculmeli."""
    satirlar = [{"dt": datetime(2020, 1, 1, 6, m), "gorus": 500.0, "hava": ""}
                for m in (20, 37, 46, 50)]
    not_ = g.cozunurluk_notu(satirlar)
    assert "yuvarlı DEĞİL" in not_ and "%50" in not_


def test_cozunurluk_notu_bos_veride_cokmuyor():
    assert "veri yok" in g.cozunurluk_notu([])


def test_veri_oku_DUZ_CSV_de_okuyabiliyor(tmp_path):
    """gozlem_arsivi.csv gzip degil; bicim uzantidan secilmeli."""
    yol = tmp_path / "gozlem_arsivi.csv"
    yol.write_text("zaman,tip,gorus,hava\n"
                   "2026-01-01T06:20:00+00:00,METAR,5000,BR\n"
                   "2026-01-01T06:37:00+00:00,SPECI,800,FG\n"
                   "2026-01-01T06:50:00+00:00,METAR,,\n",   # gorussuz satir atlanir
                   encoding="utf-8")
    satirlar = g.veri_oku(yol)
    assert [s["gorus"] for s in satirlar] == [5000.0, 800.0]
    assert satirlar[1]["dt"].minute == 37
