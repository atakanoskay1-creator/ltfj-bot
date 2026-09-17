"""Dusuk tavan etiketi, rejim penceresi ve olasilik tablosu testleri.

En kritik uc test:
(1) 'tavan bildirilmemis' SIFIR etiketi demektir, EKSIK VERI degil - aksi
    halde gozlemlerin %62'si (CAVOK/NSC) tablodan dusurdu ve en guclu
    negatif gosterge kaybolurdu,
(2) hedef GELECEGE bakiyor ve onset kosullu (su an tavan dusuk DEGILKEN),
(3) tablonun bant sinirlari A PRIORI - quantile bantlama gorus degiskenini
    mekanik olarak coktururdu (bkz. tavan_tablo.APRIORI_BANTLAR).
"""
from datetime import datetime, timedelta, timezone

from sis_modeli import bolme, tavan, tavan_tablo

BASLANGIC = datetime(2020, 1, 15, 0, 0, tzinfo=timezone.utc)


def _seri(n=48, yil=2020, **alanlar):
    """n adet yarim saatlik gozlem; alanlar listeyle gecilir."""
    satirlar = []
    for i in range(n):
        t = BASLANGIC.replace(year=yil) + timedelta(minutes=30 * i)
        r = {"zaman": t.strftime("%Y-%m-%dT%H:%M"), "ay": t.month, "saat": t.hour,
             "sicaklik": 10, "cig_noktasi": 8, "spread": 2.0, "ruzgar_hiz": 5,
             "ruzgar_yon": 90, "gorus": 9999, "tavan": None, "qnh": 1015,
             "sis_kodu": 0, "sis": 0, "lvo": 0}
        for a, degerler in alanlar.items():
            r[a] = degerler[i]
        satirlar.append(r)
    return satirlar


# ----------------------------------------------------------------- etiket
def test_tavan_bildirilmemisse_dusuk_tavan_yok_demektir():
    """CAVOK/NSC 'veri eksik' degil 'dusuk tavan yok' demektir."""
    k = tavan.etiketle([{"tavan": None}, {"tavan": 300}, {"tavan": 900}])
    assert [r["tavan_dusuk"] for r in k] == [0, 1, 0]


def test_tavan_ozelligi_bildirilmemisi_sozde_degere_cevirir():
    """None kalsaydi WoE kova tablosu bu satirlari ATARDI - gozlemlerin
    %62'si boyle ve en guclu negatif gosterge kaybolurdu."""
    assert tavan.tavan_ft({"tavan": None}) == tavan.TAVAN_YOK_FT
    assert tavan.tavan_ft({"tavan": 400}) == 400


def test_etiketleme_kaynagi_bozmuyor():
    kaynak = [{"tavan": 300}]
    tavan.etiketle(kaynak)
    assert "tavan_dusuk" not in kaynak[0]


def test_esik_degistirilebilir():
    k = tavan.etiketle([{"tavan": 800}], esik_ft=tavan.CAT_II_FT)
    assert k[0]["tavan_dusuk"] == 0
    k = tavan.etiketle([{"tavan": 800}], esik_ft=1000)
    assert k[0]["tavan_dusuk"] == 1


# ---------------------------------------------------------- rejim penceresi
def test_rejim_penceresi_eksik_bildirim_yillarini_disliyor():
    """2011-2016 dusuk tavani sistematik olarak eksik bildiriyor; o yillar
    etiket olarak kullanilamaz (bkz. sis_modeli/README.md)."""
    s = _seri(n=2, yil=2014) + _seri(n=2, yil=2020)
    assert {r["zaman"][:4] for r in tavan.rejim_penceresi(s)} == {"2020"}
    assert tavan.REJIM_ILK_YIL == 2017


def test_rejim_taramasi_yuvarlak_yigilmayi_olcuyor():
    """Insan tahmini 500 ft katlarina yigilir; tarama bunu gorebilmeli."""
    s = [{"zaman": f"2020-01-01T{i//2:02d}:00", "tavan": 3000 if i % 2 else 2700}
         for i in range(2000)]
    r = tavan.rejim_taramasi(s)[0]
    assert abs(r["yuvarlak_orani"] - 0.5) < 0.01


def test_rejim_taramasi_ince_yillari_atliyor():
    assert tavan.rejim_taramasi([{"zaman": "2020-01-01T00:00", "tavan": 500}]) == []


# ------------------------------------------------------------------ hedef
def test_hedef_gelecege_bakiyor_ve_onset_kosullu():
    tavanlar = [None] * 20 + [300] * 2 + [None] * 26
    aday = tavan.hazirla(_seri(n=48, tavan=tavanlar), ilk_yil=2011)
    yer = {r["zaman"]: r for r in aday}
    def an(i):
        t = BASLANGIC + timedelta(minutes=30 * i)
        return yer.get(t.strftime("%Y-%m-%dT%H:%M"))
    assert an(14)["hedef"] is True      # 6 adim (3 saat) once
    assert an(13)["hedef"] is False     # 7 adim once - pencere disinda
    # onset: tavanin ZATEN dusuk oldugu anlar evrende yok
    assert an(20) is None and an(21) is None


def test_hedef_gecmise_bakmiyor():
    tavanlar = [300] * 2 + [None] * 46
    aday = tavan.hazirla(_seri(n=48, tavan=tavanlar), ilk_yil=2011)
    assert not any(r["hedef"] for r in aday)


# ------------------------------------------------------------------ tablo
def test_bant_sinirlari_apriori_ve_projeden():
    """Sinirlar veriye BAKILARAK secilmedi: projenin kendi esikleri.
    Otomatik quantile bantlama gorus'u 8 bilgilendirici banttan 3'e
    dusuruyordu (yigilmis dagilim coku modu, bkz. woe.py)."""
    g = tavan_tablo.APRIORI_BANTLAR["gorus"]
    from ltfj_vfr import VFR_GORUS_ESIGI_M
    from sis_modeli.ozellik import LVO_GORUS_M, SIS_GORUS_M
    assert LVO_GORUS_M in g and SIS_GORUS_M in g and VFR_GORUS_ESIGI_M in g
    assert tavan_tablo.bantlar([], "gorus") == g


def test_bant_sinirlari_kopya_donduruyor():
    """Cagiran taraf listeyi degistirirse a priori sabit bozulmamali."""
    a = tavan_tablo.bantlar([], "spread")
    a.append(999)
    assert 999 not in tavan_tablo.APRIORI_BANTLAR["spread"]


def _tablo_verisi(n=4000):
    """spread dustukce hedef olasiligi artan sentetik veri; gunler farkli."""
    import random
    r = random.Random(3)
    satirlar = []
    for i in range(n):
        spread = r.choice([0.5, 1.5, 2.5, 4.0, 6.0, 9.0])
        satirlar.append({
            "gun": f"2020-01-{i % 40 + 1:02d}", "spread": spread,
            "gorus": r.choice([800, 3000, 7000, 9999, 10000]),
            "hedef": r.random() < max(0.0, 0.25 - 0.04 * spread),
        })
    return satirlar


def test_tablo_bos_hucrede_uydurmuyor():
    """Egitimde hic gorulmemis hucre icin taban oran doner."""
    t = tavan_tablo.tablo_kur(_tablo_verisi(), "spread", "gorus")
    assert tavan_tablo.tahmin(t, {"spread": -99, "gorus": -99}) == t["taban"]


def test_buzulme_seyrek_hucreyi_taban_orana_cekiyor():
    """5 gozlemde 1 pozitif %20 degil, taban orana yakin bir sey demektir."""
    veri = ([{"gun": "2020-01-01", "spread": 9.0, "gorus": 9999, "hedef": False}] * 3000
            + [{"gun": "2020-01-02", "spread": 0.5, "gorus": 800, "hedef": True}] * 1
            + [{"gun": "2020-01-02", "spread": 0.5, "gorus": 800, "hedef": False}] * 4)
    t = tavan_tablo.tablo_kur(veri, "spread", "gorus")
    seyrek = tavan_tablo.tahmin(t, {"spread": 0.5, "gorus": 800})
    assert seyrek < 0.20 / 4          # ham oran %20 - buzulme ciddi cekmeli
    assert seyrek > t["taban"]        # ama sinyali tamamen yok etmemeli


def test_tablo_sinyali_yakaliyor_ve_kat_uretiyor():
    t = tavan_tablo.tablo_kur(_tablo_verisi(), "spread", "gorus")
    dusuk = tavan_tablo.tahmin(t, {"spread": 0.5, "gorus": 800})
    yuksek = tavan_tablo.tahmin(t, {"spread": 9.0, "gorus": 10000})
    assert dusuk > yuksek
    katlar = [c["kat"] for c in t["hucreler"].values()]
    assert max(katlar) > 1.0 > min(katlar)


def test_kat_tanimi_olasilik_bolu_taban():
    t = tavan_tablo.tablo_kur(_tablo_verisi(), "spread", "gorus")
    for c in t["hucreler"].values():
        assert abs(c["kat"] - c["olasilik"] / t["taban"]) < 1e-12


def test_blok_bootstrap_araligi_hucre_olasiligini_kapsiyor():
    veri = _tablo_verisi()
    t = tavan_tablo.tablo_kur(veri, "spread", "gorus")
    araliklar = tavan_tablo.degerlendir_araliklar(t, veri, tekrar=60)
    kapsanan = sum(alt <= t["hucreler"][h]["olasilik"] <= ust
                   for h, (alt, ust) in araliklar.items())
    assert kapsanan >= 0.8 * len(araliklar)


def test_kat_kararliligi_ayni_dagilimda_bire_yakin():
    a, b = _tablo_verisi(6000), _tablo_verisi(6000)
    for r in b:                      # ikinci orneklem farkli gunlerde olsun
        r["gun"] = "2021-" + r["gun"][5:]
    k = tavan_tablo.kat_kararliligi(tavan_tablo.tablo_kur(a, "spread", "gorus"),
                                    b, asgari_n=50)
    assert k["log_korelasyon"] > 0.8
    assert 0.5 < k["kat_orani_medyan"] < 2.0


def test_kat_kararliligi_az_hucrede_bos_donuyor():
    t = tavan_tablo.tablo_kur(_tablo_verisi(), "spread", "gorus")
    assert tavan_tablo.kat_kararliligi(t, [], asgari_n=50) == {}


# -------------------------------------------------------------- izolasyon
def test_ic_foldlar_holdouta_dokunmuyor():
    yillar = list(range(tavan.REJIM_ILK_YIL, min(bolme.HOLDOUT_YILLARI)))
    for egitim, test in tavan_tablo._ic_foldlar(yillar):
        assert max(egitim) < min(test)
        assert not (set(egitim) | set(test)) & set(bolme.HOLDOUT_YILLARI)


def test_calisma_ani_modulu_tavan_modulunu_import_etmiyor():
    """Izolasyon sozlesmesi: bot sis_modeli/'ni import ETMEZ."""
    import ast
    from pathlib import Path
    kok = Path(__file__).resolve().parent.parent
    for dosya in ("ltfj_sis_olasilik.py", "ltfj_sayfa.py", "ltfj_bot.py"):
        agac = ast.parse((kok / dosya).read_text(encoding="utf-8"))
        for node in ast.walk(agac):
            adlar = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom)
                     else [])
            assert not any(a.startswith("sis_modeli") for a in adlar), dosya
