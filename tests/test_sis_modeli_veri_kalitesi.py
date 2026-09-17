"""Arsiv kusuru teshisi ve dondurulmus modelin korunmasi testleri.

En kritik iki test:
(1) Suzgec YIL bazinda calisir, satir bazinda DEGIL - satir bazinda suzmek
    (ornegin "spread=0 olanlari at") etiketle iliskili bir degiskene gore
    secim yapmak olur ve gercek sis olaylarini da siler,
(2) Dondurulmus model A/B sonucuna gore DEGISMEDI - onceden ilan edilen
    kural "hayir" dedi (bkz. sis_modeli/README.md).
"""
import ast
from pathlib import Path

from sis_modeli import degerlendir, veri_kalitesi as vk

KOK = Path(__file__).resolve().parent.parent


def _kayit(yil, ay=1, spread=5.0, gorus=9999, sis=0):
    return {"zaman": f"{yil}-{ay:02d}-15T03:00", "ay": ay, "spread": spread,
            "gorus": gorus, "sis": sis}


# ------------------------------------------------------------------ süzgeç
def test_suzgec_yil_bazinda_calisiyor():
    s = [_kayit(2020), _kayit(2022), _kayit(2025)]
    assert [r["zaman"][:4] for r in vk.ciy_temiz(s)] == ["2020", "2025"]


def test_suzgec_satir_bazinda_secim_yapmiyor():
    """Kusurlu yilda spread=0 OLMAYAN satirlar da cikar; temiz yilda
    spread=0 OLAN satirlar kalir. Yani olcut yil, deger degil."""
    s = [_kayit(2022, spread=0.0), _kayit(2022, spread=7.0),
         _kayit(2019, spread=0.0), _kayit(2019, spread=7.0)]
    kalan = vk.ciy_temiz(s)
    assert len(kalan) == 2
    assert {r["spread"] for r in kalan} == {0.0, 7.0}


def test_kusurlu_yillar_belgelenmis_uclu():
    assert vk.CIY_KUSURLU_YILLAR == (2021, 2022, 2023)


def test_suzgec_kaynagi_bozmuyor():
    s = [_kayit(2022)]
    assert len(vk.ciy_temiz(s)) == 0 and len(s) == 1


# ------------------------------------------------------------------ teşhis
def test_spread_imzasi_sifir_oranini_ve_cavok_payini_buluyor():
    s = ([_kayit(2022, spread=0.0, gorus=9999)] * 30
         + [_kayit(2022, spread=0.0, gorus=500)] * 10
         + [_kayit(2022, spread=5.0)] * 60)
    r = vk.spread_imzasi(s, (("test", {2022}),))[0]
    assert abs(r["sifir_orani"] - 0.40) < 1e-9
    assert abs(r["cavok_payi"] - 0.75) < 1e-9
    assert r["negatif"] == 0


def test_ay_eslenmis_sapma_mevsim_kompozisyonunu_eliyor():
    """Kusurlu donem YALNIZCA kis aylarini icerseydi, ham ortalama farki
    kusur sanilirdi. Ay eslemesi bunu onler."""
    s = []
    for ay in (1, 7):
        temiz = 3.0 if ay == 1 else 9.0          # mevsimsel fark buyuk
        s += [_kayit(2019, ay=ay, spread=temiz)] * 50
        s += [_kayit(2022, ay=ay, spread=temiz - 1.0)] * 50   # kusur: -1 °C
    sapmalar = vk.ay_eslenmis_sapma(s)
    assert len(sapmalar) == 2
    for x in sapmalar:
        assert abs(x["sapma"] - 1.0) < 1e-9      # mevsim degil, kusur olculdu


def test_ay_eslenmis_sapma_tek_donem_varsa_atliyor():
    assert vk.ay_eslenmis_sapma([_kayit(2019, ay=1)] * 10) == []


# --------------------------------------------------------- eşleştirilmiş CI
def test_eslesmis_fark_araligi_acik_ustunlugu_yakaliyor():
    kayitlar = [{"gun": f"2024-01-{i % 20 + 1:02d}"} for i in range(400)]
    gercek = [i % 5 == 0 for i in range(400)]
    iyi = [0.9 if y else 0.1 for y in gercek]
    kotu = [0.5] * 400
    alt, ust = vk.eslesmis_fark_araligi(kayitlar, kotu, iyi, gercek,
                                        degerlendir.ortalama_kesinlik, tekrar=80)
    assert alt > 0 and ust > alt        # B acikca daha iyi


def test_eslesmis_fark_araligi_ayni_modelde_sifiri_kapsiyor():
    kayitlar = [{"gun": f"2024-01-{i % 20 + 1:02d}"} for i in range(400)]
    gercek = [i % 5 == 0 for i in range(400)]
    p = [0.3 if y else 0.2 for y in gercek]
    alt, ust = vk.eslesmis_fark_araligi(kayitlar, p, list(p), gercek,
                                        degerlendir.ortalama_kesinlik, tekrar=80)
    assert alt <= 0 <= ust


def test_eslesmis_fark_araligi_bos_veride_cokmez():
    assert vk.eslesmis_fark_araligi([], [], [], [], degerlendir.brier) == (0.0, 0.0)


# ------------------------------------------- dondurulmus model DEGISMEDI
def test_dondurulmus_model_ab_sonrasi_korundu():
    """Onceden ilan edilen kural saglanmadi: A korunur.

    Bu test, ileride birisi 'temiz model'i sessizce dondurursa uyarir -
    dondurmak ancak kural saglanirsa mesrudur ve o zaman bu test de
    beklentisiyle birlikte guncellenmelidir."""
    import ltfj_sis_olasilik as m
    assert abs(m.SABIT_TERIM - (-4.653635228753809)) < 1e-12
    assert abs(m.KATSAYILAR["spread"] - 0.470302867198085) < 1e-12
    assert abs(m.KATSAYILAR["gorus"] - 0.6139640243075414) < 1e-12


def test_veri_kalitesi_calisma_anina_sizmiyor():
    """Izolasyon sozlesmesi: bot sis_modeli/'ni import ETMEZ."""
    for dosya in ("ltfj_sis_olasilik.py", "ltfj_bot.py", "ltfj_sayfa.py"):
        agac = ast.parse((KOK / dosya).read_text(encoding="utf-8"))
        for node in ast.walk(agac):
            adlar = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom)
                     else [])
            assert not any(a.startswith("sis_modeli") for a in adlar), dosya


def test_karar_kurali_belgede_ve_kodda():
    """Kural sonuclara bakilmadan yazildi; modul basliginda duruyor."""
    kaynak = (KOK / "sis_modeli" / "veri_kalitesi.py").read_text(encoding="utf-8")
    assert "ONCEDEN ILAN EDILEN KARAR KURALI" in kaynak
    readme = (KOK / "sis_modeli" / "README.md").read_text(encoding="utf-8")
    assert "Dışlama denendi ve reddedildi" in readme
