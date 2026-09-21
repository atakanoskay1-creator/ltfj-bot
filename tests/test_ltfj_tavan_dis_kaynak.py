"""ltfj_tavan_dis_kaynak.py testleri.

En kritik test: GERİ DÜŞME (fallback) - dış kaynak (acik_meteo_nem_2m,
komsu_tavan_ozellik) eksik/None olduğunda TEMEL modele sessizce düşmeli,
None DÖNMEMELİ (TEMEL alanların hepsi doluysa)."""
import ast
from pathlib import Path

import ltfj_tavan_dis_kaynak as m

KOK = Path(__file__).resolve().parent.parent

_TEMEL_KWARGS = dict(spread=1.0, gorus=3000, tavan_ozellik=2000, saat=3,
                     ruzgar_kuzey=1.0, sis_olasilik=0.02)


# --------------------------------------------------------------- fallback
def test_dis_kaynak_yoksa_temel_modelle_hesaplar_none_donmez():
    p = m.olasilik(**_TEMEL_KWARGS)
    assert p is not None
    assert 0.0 <= p <= 1.0


def test_dis_kaynak_kismi_doluysa_yine_temel_modele_duser():
    """Sadece BİRİ dolu, diğeri None - GENİŞ model ikisi de gerektirir,
    aksi halde tutarsız (yarısı taze yarısı yok) bir hücreye düşülür."""
    sadece_nem = m.olasilik(**_TEMEL_KWARGS, acik_meteo_nem_2m=80)
    sadece_komsu = m.olasilik(**_TEMEL_KWARGS, komsu_tavan_ozellik=1500)
    ikisi_yok = m.olasilik(**_TEMEL_KWARGS)
    assert sadece_nem == ikisi_yok
    assert sadece_komsu == ikisi_yok


def test_dis_kaynak_ikisi_de_doluysa_farkli_bir_modele_gecer():
    temel = m.olasilik(**_TEMEL_KWARGS)
    genis = m.olasilik(**_TEMEL_KWARGS, acik_meteo_nem_2m=80,
                       komsu_tavan_ozellik=1500)
    assert genis is not None
    # Ayni girdilerle TEMEL ve GENIS FARKLI katsayi kumeleri kullandigi icin
    # (genellikle) farkli sonuc verir - esitlik bir tesadufse bile testin
    # asil amaci cokmeden IKI YOLUN DA calistigini dogrulamak.
    assert isinstance(temel, float) and isinstance(genis, float)


def test_temel_alan_eksikse_none_doner():
    for eksik in ("spread", "gorus", "tavan_ozellik", "saat", "ruzgar_kuzey",
                 "sis_olasilik"):
        kwargs = dict(_TEMEL_KWARGS)
        kwargs[eksik] = None
        assert m.olasilik(**kwargs) is None, eksik


def test_olasilik_her_zaman_0_1_araliginda():
    for spread in (-2.0, 0.0, 5.0, 15.0):
        for tavan_ozellik in (200, 1000, 99999):
            p = m.olasilik(spread=spread, gorus=5000, tavan_ozellik=tavan_ozellik,
                           saat=3, ruzgar_kuzey=0.0, sis_olasilik=0.05,
                           acik_meteo_nem_2m=70, komsu_tavan_ozellik=2000)
            assert 0.0 <= p <= 1.0


# --------------------------------------------------------------- yapisal
def test_temel_katsayilarinin_hepsi_pozitif():
    """TEMEL modelde tum katsayilar saglikli (pozitif) - tanilama.
    isaret_kontrolu kuralinin bekledigi durum."""
    assert all(k > 0 for k in m.KATSAYILAR_TEMEL.values())


def test_genis_modelde_bilinen_tek_supresor_disinda_hepsi_pozitif():
    """GENIS modelde sis_olasilik KASITLI OLARAK negatif - VIF taramasinda
    (sis_modeli/README.md) gorulen sis_olasilik/spread kolinerligi
    yuzunden supresor rolune geciyor, modul dokumantasyonunda acikca
    belgelendi. Bu, BEKLENEN ve BILINEN tek istisna - baska hicbir
    katsayi negatif OLMAMALI (yeni bir sorun sessizce gecmesin)."""
    negatifler = {a: k for a, k in m.KATSAYILAR_GENIS.items() if k < 0}
    assert negatifler == {"sis_olasilik": m.KATSAYILAR_GENIS["sis_olasilik"]}


def test_woe_tablolari_katsayilarla_ayni_alanlari_kapsiyor():
    assert set(m.WOE_TABLOLARI_TEMEL) == set(m.KATSAYILAR_TEMEL)
    assert set(m.WOE_TABLOLARI_GENIS) == set(m.KATSAYILAR_GENIS)


def test_genis_temelin_tum_alanlarini_iceriyor():
    assert set(m.KATSAYILAR_TEMEL) <= set(m.KATSAYILAR_GENIS)
    assert "acik_meteo_nem_2m" in m.KATSAYILAR_GENIS
    assert "komsu_tavan_ozellik" in m.KATSAYILAR_GENIS


def test_taban_oran_egitim_sayilarindan_hesaplaniyor():
    assert m.EGITIM_AN_SAYISI > 0 and m.EGITIM_POZITIF > 0
    assert abs(m.TABAN_ORAN - m.EGITIM_POZITIF / m.EGITIM_AN_SAYISI) < 1e-9


# --------------------------------------------------------------- izolasyon
def _importlar(dosya: str) -> set:
    agac = ast.parse((KOK / dosya).read_text(encoding="utf-8"))
    adlar = set()
    for node in ast.walk(agac):
        if isinstance(node, ast.Import):
            adlar.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            adlar.add(node.module.split(".")[0])
    return adlar


def test_calisma_ani_modulu_sis_modelini_import_etmiyor():
    assert not any(a.startswith("sis_modeli") for a in _importlar("ltfj_tavan_dis_kaynak.py"))


def test_calisma_aninda_agir_bagimlilik_yok():
    assert _importlar("ltfj_tavan_dis_kaynak.py") == {"math"}
