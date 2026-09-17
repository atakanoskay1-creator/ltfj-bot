"""Dondurulmus istatistiksel sis olasiligi modeli + web karti testleri.

En kritik iki test:
(1) Calisma ani modulu sis_modeli/'ni IMPORT ETMIYOR (izolasyon sozlesmesi),
(2) Yeni kart mevcut ltfj_pist.sis_riski() gostergesinin YERINE GECMIYOR -
    ikisi ayni sayfada bagimsiz olarak duruyor."""
import ast
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ltfj_sayfa as s
import ltfj_sis_olasilik as m

KOK = Path(__file__).resolve().parent.parent
SIMDI = datetime.now(timezone.utc)


def _gecmis(saatler=7, cig_var=True):
    return [{"zaman": (SIMDI - timedelta(hours=h)).isoformat(),
             "ruzgar_hiz": 3, "tavan": 2000, "qnh": 1020, "sicaklik": 8,
             **({"cig_noktasi": 8 - h * 0.5} if cig_var else {})}
            for h in range(saatler - 1, -1, -1)]


def _sayfa(metin, gecmis=None):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        hedef = Path(d) / "index.html"
        rapor = {"tip": "METAR", "metin": metin, "zaman": SIMDI, "icao": "LTFJ"}
        s.sayfa_yaz([rapor], gecmis if gecmis is not None else _gecmis(), hedef, {}, "")
        return hedef.read_text(encoding="utf-8")


# ------------------------------------------------------------------- model
def test_olasilik_sisli_kosulda_yuksek_acik_havada_dusuk():
    sisli = m.olasilik(spread=0.0, gorus=1500, saat=3, ruzgar_kuzey=3.0)
    acik = m.olasilik(spread=12.0, gorus=9999, saat=13, ruzgar_kuzey=5.0)
    assert sisli > acik
    assert sisli > 0.10 and acik < 0.01


def test_spread_veya_gorus_yoksa_none():
    assert m.olasilik(spread=None, gorus=3000, saat=3) is None
    assert m.olasilik(spread=1.0, gorus=None, saat=3) is None


def test_olasilik_her_zaman_0_1_araliginda():
    for spread in (-5.0, 0.0, 30.0):
        for gorus in (0, 500, 9999, 99999):
            p = m.olasilik(spread=spread, gorus=gorus, saat=3, ruzgar_kuzey=0.0)
            assert 0.0 <= p <= 1.0


def test_eksik_egilim_cokmez_ve_notr_davranir():
    """spread_egilim_3 ilk calistirmalarda yok (gecmiste cig noktasi
    birikmemis olabilir) - WoE 0 ile calismali."""
    var = m.olasilik(spread=1.0, gorus=3000, saat=3, ruzgar_kuzey=2.0,
                     spread_egilim_3=-0.5)
    yok = m.olasilik(spread=1.0, gorus=3000, saat=3, ruzgar_kuzey=2.0,
                     spread_egilim_3=None)
    assert yok is not None
    assert abs(var - yok) < 0.05        # etkisi kucuk olmali (beta 0.038)


def test_gorus_dustukce_olasilik_artar():
    oncekiler = [m.olasilik(spread=1.0, gorus=g, saat=3, ruzgar_kuzey=2.0)
                 for g in (9999, 6000, 3000, 1500)]
    assert oncekiler == sorted(oncekiler)


def test_spread_arttikca_olasilik_azalir():
    degerler = [m.olasilik(spread=sp, gorus=5000, saat=3, ruzgar_kuzey=2.0)
                for sp in (0.0, 2.5, 4.0, 10.0)]
    assert degerler == sorted(degerler, reverse=True)


def test_ruzgar_kuzey_bileseni_daireselligi_cozuyor():
    assert m.ruzgar_kuzey_bileseni(0, 10) > 9.9        # kuzeyden
    assert m.ruzgar_kuzey_bileseni(180, 10) < -9.9     # guneyden
    assert abs(m.ruzgar_kuzey_bileseni(90, 10)) < 0.1  # dogudan
    assert m.ruzgar_kuzey_bileseni(None, 10) is None


def test_katsayilarin_hepsi_pozitif():
    """WoE modelinde saglikli katsayi pozitiftir (bkz. tanilama.isaret_kontrolu)."""
    assert all(k > 0 for k in m.KATSAYILAR.values())


def test_woe_tablolari_katsayilarla_ayni_alanlari_kapsiyor():
    assert set(m.WOE_TABLOLARI) == set(m.KATSAYILAR)


# --------------------------------------------------------------- izolasyon
def test_calisma_ani_modulu_sis_modelini_import_etmiyor():
    """Egitim laboratuvari (sis_modeli/) calisma anina SIZMAMALI - buraya
    yalnizca dondurulmus ciktilar tasinir."""
    agac = ast.parse((KOK / "ltfj_sis_olasilik.py").read_text(encoding="utf-8"))
    for node in ast.walk(agac):
        adlar = ([a.name for a in node.names] if isinstance(node, ast.Import)
                 else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
        for ad in adlar:
            assert not ad.startswith("sis_modeli"), ad


def _importlar(dosya: str) -> set:
    """Gercek import ifadeleri - ham metin taramasi DEGIL.

    Ham metin taransaydi 'numpy GEREKMEZ' gibi bir ACIKLAMA satiri yanlis
    pozitif uretirdi (bir kez uretti)."""
    agac = ast.parse((KOK / dosya).read_text(encoding="utf-8"))
    adlar = set()
    for node in ast.walk(agac):
        if isinstance(node, ast.Import):
            adlar.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            adlar.add(node.module.split(".")[0])
    return adlar


def test_calisma_aninda_agir_bagimlilik_yok():
    """Kart calisma aninda sadece standart kutuphaneyle hesaplanmali."""
    assert _importlar("ltfj_sis_olasilik.py") == {"math"}


# ------------------------------------------------------------------- sayfa
def test_kart_sayfada_yuzde_olarak_gorunuyor():
    html = _sayfa("LTFJ 172120Z 01003KT 6000 SCT020 08/07 Q1020")
    assert "İstatistiksel sis olasılığı" in html
    assert re.search(r'sis-olasilik-deger">%[\d.]+<', html)


def test_kart_mevcut_sis_gostergesinin_yerine_gecmiyor():
    """Kullanici acikca istedi: sis_riski() kalacak, yeni kart AYRI duracak."""
    html = _sayfa("LTFJ 172120Z 01003KT 6000 SCT020 08/07 Q1020")
    assert "Sis riski" in html                      # mevcut sezgisel gosterge
    assert "İstatistiksel sis olasılığı" in html    # yeni kart
    assert "sezgisel yöntem" in html                # mevcutun kendi uyarisi


def test_kart_kaynagini_ve_sinirlarini_belirtiyor():
    html = _sayfa("LTFJ 172120Z 01003KT 6000 SCT020 08/07 Q1020")
    assert "İSTATİSTİKSEL" in html
    assert "2011–2023" in html
    assert "resmî tahmin değildir" in html


def test_sicaklik_yoksa_kart_hic_cikmiyor():
    html = _sayfa("LTFJ 172120Z 01003KT 6000 SCT020 Q1020")
    assert "İstatistiksel sis olasılığı" not in html


def test_cig_noktasiz_eski_gecmisle_kart_yine_calisiyor():
    """Eski state kayitlarinda cig_noktasi yok - kart yine de uretilmeli."""
    html = _sayfa("LTFJ 172120Z 01003KT 6000 SCT020 08/07 Q1020",
                  gecmis=_gecmis(cig_var=False))
    assert "İstatistiksel sis olasılığı" in html


def test_spread_egilimi_gecmisten_hesaplaniyor():
    dusen = [{"zaman": (SIMDI - timedelta(hours=h)).isoformat(),
              "sicaklik": 10, "cig_noktasi": 10 - h}      # spread gecmiste buyuk
             for h in range(4, -1, -1)]
    egilim = s._spread_egilimi(dusen, SIMDI)
    assert egilim is not None and egilim < 0            # spread dusmus


def test_spread_egilimi_cig_noktasi_yoksa_none():
    assert s._spread_egilimi(_gecmis(cig_var=False), SIMDI) is None
