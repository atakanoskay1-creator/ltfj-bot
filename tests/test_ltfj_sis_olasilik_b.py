"""ltfj_sis_olasilik_b.py (Model B, görüşsüz) - dondurulmuş model + kart
entegrasyonu testleri.

En kritik üç test:
(1) Çalışma anı modülü sis_modeli/'ni import ETMİYOR (izolasyon sözleşmesi,
    ltfj_sis_olasilik.py ile aynı disiplin),
(2) tertil() A_UST_SINIR ve ÜZERİNDE (>= %2) HİÇBİR ŞEY DÖNMÜYOR -
    ab_karsilastirma.py'de o bölgede B'nin katkısına dair kanıt
    BULUNAMADIĞI için gösterge orada YOK olmalı,
(3) Kart, A çok düşükken ek göstergeyi gösteriyor, A yüksekken GÖSTERMİYOR."""
import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ltfj_sayfa as s
import ltfj_sis_olasilik_b as b

KOK = Path(__file__).resolve().parent.parent
SIMDI = datetime.now(timezone.utc)


def _gecmis(saatler=7):
    return [{"zaman": (SIMDI - timedelta(hours=h)).isoformat(),
             "ruzgar_hiz": 3, "tavan": 2000, "qnh": 1020, "sicaklik": 8,
             "cig_noktasi": 8 - h * 0.5}
            for h in range(saatler - 1, -1, -1)]


def _sayfa(metin, gecmis=None):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        hedef = Path(d) / "index.html"
        rapor = {"tip": "METAR", "metin": metin, "zaman": SIMDI, "icao": "LTFJ"}
        s.sayfa_yaz([rapor], gecmis if gecmis is not None else _gecmis(), hedef, {}, "")
        return hedef.read_text(encoding="utf-8")


# ------------------------------------------------------------------- model
def test_olasilik_spread_yoksa_none():
    assert b.olasilik(spread=None, sicaklik=10, saat=3) is None


def test_olasilik_her_zaman_0_1_araliginda():
    for spread in (-2.0, 0.0, 15.0):
        for sicaklik in (-5, 10, 30):
            p = b.olasilik(spread=spread, sicaklik=sicaklik, saat=4,
                           ruzgar_kuzey=0.0, spread_egilim_3=0.0)
            assert 0.0 <= p <= 1.0


def test_katsayilarin_hepsi_pozitif():
    assert all(k > 0 for k in b.KATSAYILAR.values())


def test_woe_tablolari_katsayilarla_ayni_alanlari_kapsiyor():
    assert set(b.WOE_TABLOLARI) == set(b.KATSAYILAR)


def test_ruzgar_kuzey_bileseni_daireselligi_cozuyor():
    assert b.ruzgar_kuzey_bileseni(0, 10) > 9.9
    assert b.ruzgar_kuzey_bileseni(180, 10) < -9.9
    assert b.ruzgar_kuzey_bileseni(None, 10) is None


# ----------------------------------------------------------------- tertil
def test_tertil_a_ust_sinirin_ustunde_none():
    """A_UST_SINIR (=%2) ve UZERINDE gosterge YOK - ab_karsilastirma.py'de
    o bolgede kanit bulunamadi."""
    assert b.tertil(b.A_UST_SINIR, 0.5) is None
    assert b.tertil(0.10, 0.5) is None


def test_tertil_a_veya_b_eksikse_none():
    assert b.tertil(None, 0.01) is None
    assert b.tertil(0.005, None) is None


def test_tertil_dusuk_orta_yuksek_dogru_siniflandiriyor():
    alt, ust = b.TERTIL_SINIRLARI[0]  # (0.0, 0.01) bandı
    (alt_a, ust_a), (s1, s2) = alt, ust
    assert alt_a == 0.0 and ust_a == 0.01
    assert b.tertil(0.005, s1 - 0.0001) == "düşük"
    assert b.tertil(0.005, (s1 + s2) / 2) == "orta"
    assert b.tertil(0.005, s2 + 0.001) == "yüksek"


def test_tertil_siniri_disindaki_a_bandinda_none():
    """TERTIL_SINIRLARI yalnizca %0-2 araligini kapsiyor - araya
    (ornegin tam olarak tanimsiz bir bosluk olsaydi) dusen bir deger
    icin de fonksiyon sessizce None donmeli, uydurma yapmamali."""
    # Tanimli araliklarin DISINDA (>= A_UST_SINIR) zaten yukarida test edildi;
    # burada araliklarin BIRLESIK olarak [0, A_UST_SINIR)'i kapladigini dogrula.
    kapsanan = [(alt, ust) for (alt, ust), _ in b.TERTIL_SINIRLARI]
    assert kapsanan[0][0] == 0.0
    assert kapsanan[-1][1] == b.A_UST_SINIR


# --------------------------------------------------------------- izolasyon
def test_calisma_ani_modulu_sis_modelini_import_etmiyor():
    agac = ast.parse((KOK / "ltfj_sis_olasilik_b.py").read_text(encoding="utf-8"))
    for node in ast.walk(agac):
        adlar = ([a.name for a in node.names] if isinstance(node, ast.Import)
                 else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
        for ad in adlar:
            assert not ad.startswith("sis_modeli"), ad


def _importlar(dosya: str) -> set:
    agac = ast.parse((KOK / dosya).read_text(encoding="utf-8"))
    adlar = set()
    for node in ast.walk(agac):
        if isinstance(node, ast.Import):
            adlar.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            adlar.add(node.module.split(".")[0])
    return adlar


def test_calisma_aninda_agir_bagimlilik_yok():
    assert _importlar("ltfj_sis_olasilik_b.py") == {"math"}


# ------------------------------------------------------------------- sayfa
def test_kart_a_cok_dusukken_ek_gostergeyi_gosterir():
    """Acik havada (CAVOK) A cok dusuk cikar - ek gosterge gorunmeli."""
    html = _sayfa("LTFJ 172120Z 18005KT CAVOK 22/05 Q1015")
    assert "Ek atmosferik gösterge" in html


def test_kart_a_yuksekken_ek_gosterge_gorunmuyor():
    """Sisli/dusuk gorusle A >= %2'ye cikar - ek gosterge KAYBOLMALI."""
    html = _sayfa("LTFJ 172120Z 01003KT 1500 BR 06/06 Q1020")
    assert "İstatistiksel sis olasılığı" in html    # kart hala var
    assert "Ek atmosferik gösterge" not in html


def test_kart_ek_gosterge_bant_siniflarindan_birini_tasir():
    html = _sayfa("LTFJ 172120Z 18005KT CAVOK 22/05 Q1015")
    i = html.index("Ek atmosferik gösterge")
    blok = html[i:i + 200]
    assert any(f'class="sis-olasilik-bant {sinif}"' in blok
              for sinif in ("dusuk", "orta", "yuksek"))
