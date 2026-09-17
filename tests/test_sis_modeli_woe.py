"""WoE/IV taramasi ve ileriye bakan hedef uretimi testleri.

En kritik test: hedefin GELECEGE baktigini ve t anindan sonraki hicbir
bilginin ozelliklere sizmadigini dogrulamak (bkz. sis_modeli/hedef.py)."""
from datetime import datetime, timedelta, timezone

from sis_modeli import hedef, woe

BASLANGIC = datetime(2024, 1, 15, 0, 0, tzinfo=timezone.utc)


def _seri(sis_indeksleri=(), n=48, **alanlar):
    """n adet yarim saatlik gozlem; sis_indeksleri'ndekilerde sis=1."""
    satirlar = []
    for i in range(n):
        t = BASLANGIC + timedelta(minutes=30 * i)
        r = {"zaman": t.strftime("%Y-%m-%dT%H:%M"), "ay": t.month, "saat": t.hour,
             "sicaklik": 10, "cig_noktasi": 8, "spread": 2.0, "ruzgar_hiz": 5,
             "ruzgar_yon": 90, "gorus": 9999, "tavan": None, "qnh": 1015,
             "sis_kodu": 0, "sis": int(i in sis_indeksleri), "lvo": 0}
        for a, degerler in alanlar.items():
            r[a] = degerler[i]
        satirlar.append(r)
    return satirlar


# ------------------------------------------------------------------ hedef
def test_hedef_gelecege_bakiyor():
    """20. gozlemde sis varsa, 3 saat (6 adim) oncesindeki gozlemlerin hedefi
    1 olmali - ama 7 adim oncesininki 0."""
    k = hedef.hazirla(_seri(sis_indeksleri={20}))
    assert k[14]["hedef"] is True      # 6 adim once -> pencere icinde
    assert k[19]["hedef"] is True      # 1 adim once
    assert k[13]["hedef"] is False     # 7 adim once -> pencere disinda


def test_hedef_gecmise_bakmiyor():
    """Sis'ten SONRAKI gozlemlerin hedefi (baska sis yoksa) 0 olmali -
    aksi halde model gecmisi 'tahmin' ediyor olurdu."""
    k = hedef.hazirla(_seri(sis_indeksleri={5}))
    assert all(not r["hedef"] for r in k[5:])


def test_sizinti_yok_ozellikler_yalnizca_gecmisten():
    """t anindaki egilim ozellikleri SADECE t ve oncesini kullanmali.
    Gelecekte spread'i sifirlayip ozelliklerin degismedigini dogruluyoruz."""
    normal = hedef.hazirla(_seri(n=24, spread=[2.0] * 24))
    gelecegi_bozuk = hedef.hazirla(_seri(n=24, spread=[2.0] * 12 + [0.0] * 12))
    for alan in ("spread_egilim_1", "spread_egilim_3"):
        assert normal[6][alan] == gelecegi_bozuk[6][alan], alan


def test_egilim_dususu_negatif_isaretle_gosteriyor():
    dusen = [5.0 - 0.25 * i for i in range(24)]
    k = hedef.hazirla(_seri(n=24, spread=dusen))
    assert k[10]["spread_egilim_1"] < 0          # son 1 saatte dusmus
    assert k[10]["spread_egilim_3"] < k[10]["spread_egilim_1"]


def test_ruzgar_bilesenleri_dairesel_sorunu_cozuyor():
    """350 ile 010 derece arasi mesafe 340 degil 20'dir; bilesenler bunu
    dogal olarak hallediyor."""
    k = hedef.hazirla(_seri(n=4, ruzgar_yon=[350, 10, 90, 180]))
    assert k[0]["ruzgar_kuzey"] > 0 and k[1]["ruzgar_kuzey"] > 0
    assert abs(k[0]["ruzgar_kuzey"] - k[1]["ruzgar_kuzey"]) < 0.1
    assert k[2]["ruzgar_dogu"] > 0               # 090 -> dogudan
    assert k[3]["ruzgar_kuzey"] < 0              # 180 -> guneyden


def test_onset_adaylari_sisli_anlari_disliyor():
    k = hedef.hazirla(_seri(sis_indeksleri={10, 11}))
    aday = hedef.onset_adaylari(k)
    assert all(not r["sis"] for r in aday)
    assert len(aday) == len(k) - 2


# ------------------------------------------------------------------ WoE
def _woe_verisi():
    """spread dustukce hedef olasiligi artan sentetik veri."""
    satirlar = []
    for gun in range(60):
        for i in range(24):
            spread = (i % 8) * 1.0
            satirlar.append({"gun": f"2024-01-{gun+1:02d}", "spread": spread,
                             "hedef": spread < 1.5 and i % 2 == 0})
    return satirlar


def test_woe_monoton_iliskiyi_yakaliyor():
    t = woe.kova_tablosu(_woe_verisi(), "spread", "hedef")
    assert t
    assert woe.monoton_mu(t)
    assert woe.iv(t) > 0.3


def test_iliskisiz_degiskende_iv_dusuk():
    import random
    r = random.Random(0)
    satirlar = [{"gun": f"2024-01-{i % 30 + 1:02d}", "x": r.random(),
                 "hedef": r.random() < 0.05} for i in range(4000)]
    t = woe.kova_tablosu(satirlar, "x", "hedef")
    assert woe.iv(t) < 0.1        # gurultu -> "zayif"/"ise yaramaz"


def test_blok_bootstrap_araligi_iv_yi_kapsiyor():
    veri = _woe_verisi()
    t = woe.kova_tablosu(veri, "spread", "hedef")
    sinirlar = [x["ust"] for x in t[:-1]]
    alt, ust = woe.iv_guven_araligi(veri, "spread", "hedef", "gun", sinirlar, tekrar=80)
    assert alt <= woe.iv(t) <= ust
    assert alt > 0


def test_bos_kova_woe_yi_sonsuz_yapmiyor():
    """Haldane-Anscombe duzeltmesi: hic pozitifi olmayan kovada log(0) olmaz."""
    satirlar = [{"gun": "2024-01-01", "x": i % 10, "hedef": i % 10 == 0}
                for i in range(2000)]
    t = woe.kova_tablosu(satirlar, "x", "hedef")
    assert all(abs(k["woe"]) != float("inf") for k in t)


def test_psi_ayni_dagilimda_sifira_yakin():
    a = [{"x": i % 10} for i in range(1000)]
    b = [{"x": i % 10} for i in range(1000)]
    assert woe.psi(a, b, "x", [2, 4, 6, 8]) < 0.01


def test_psi_kaymis_dagilimda_buyuk():
    a = [{"x": i % 5} for i in range(1000)]          # 0-4
    b = [{"x": 5 + i % 5} for i in range(1000)]      # 5-9
    assert woe.psi(a, b, "x", [2, 4, 6, 8]) > 0.25


def test_iv_yorumu_esikleri():
    assert woe.iv_yorumla(0.01) == "işe yaramaz"
    assert woe.iv_yorumla(0.05) == "zayıf"
    assert woe.iv_yorumla(0.2) == "orta"
    assert woe.iv_yorumla(0.4) == "güçlü"
