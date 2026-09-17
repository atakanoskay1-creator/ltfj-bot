"""sis_modeli/ alt projesi testleri.

Iki sey dogrulanir:
(1) ozellik cikarimi (METAR -> ozellik/etiket) dogru calisiyor,
(2) IZOLASYON SOZLESMESI (bkz. sis_modeli/README.md) kod seviyesinde
    gercekten geceriyor - calisma anindaki bot bu klasore bagimli DEGIL,
    ve alt proje ikinci bir METAR ayristiricisi YAZMIYOR.
"""
import ast
import gzip
from datetime import datetime, timezone
from pathlib import Path

from sis_modeli import istatistik, ozellik

KOK = Path(__file__).resolve().parent.parent
# Calisma aninda (her 15 dakikada bir) calisan modiller - bunlarin HICBIRI
# sis_modeli'ne bagimli olmamali.
CALISMA_ANI_MODULLERI = (
    "ltfj_bot.py", "ltfj_sayfa.py", "ltfj_pist.py", "ltfj_analiz.py",
    "ltfj_rasat.py", "ltfj_panel.py", "ltfj_notam.py", "ltfj_ayarlar.py",
    "state_birlestir.py", "ltfj_vfr.py", "ltfj_lvo_referans.py",
    "ltfj_lvo_farkindalik.py", "ltfj_atc_notes_cleanup.py",
)

ZAMAN = datetime(2024, 1, 15, 5, 20, tzinfo=timezone.utc)


# ------------------------------------------------------------- ozellik cikarimi
def test_acik_havada_sis_etiketi_yok():
    o = ozellik.ozellik_cikar("LTFJ 150520Z 06008KT CAVOK 12/03 Q1018 NOSIG", ZAMAN)
    assert o["sis"] == 0 and o["lvo"] == 0
    assert o["spread"] == 9
    assert o["ay"] == 1 and o["saat"] == 5


def test_sis_gorus_esigi_altinda_etiketleniyor():
    o = ozellik.ozellik_cikar("LTFJ 150520Z 00000KT 0400 FG VV001 03/03 Q1020", ZAMAN)
    assert o["sis"] == 1
    assert o["lvo"] == 1          # 400 < 550
    assert o["spread"] == 0
    assert o["sis_kodu"] == 1


def test_gorus_esik_arasinda_sis_var_lvo_yok():
    o = ozellik.ozellik_cikar("LTFJ 150520Z 00000KT 0800 FG OVC002 04/04 Q1020", ZAMAN)
    assert o["sis"] == 1
    assert o["lvo"] == 0          # 800 >= 550


def test_gorus_dusuk_ama_kod_yoksa_yine_sis_sayilir():
    """Bazi raporlar FG kodunu atlayip sadece gorusu dusurur."""
    o = ozellik.ozellik_cikar("LTFJ 150520Z 00000KT 0600 OVC001 05/05 Q1020", ZAMAN)
    assert o["sis"] == 1 and o["sis_kodu"] == 0


def test_civarda_sis_alanda_sis_sayilmaz():
    """VCFG = civarda sis; alanda gorus hala yuksek, sis kodu isaretlenmemeli."""
    o = ozellik.ozellik_cikar("LTFJ 150520Z 00000KT 9999 VCFG SCT020 06/05 Q1020", ZAMAN)
    assert o["sis_kodu"] == 0
    assert o["sis"] == 0


def test_alcak_sis_mifg_alanda_sis_sayilmaz():
    """MIFG = alcak sis; goz seviyesinde gorus >= 1000 m."""
    o = ozellik.ozellik_cikar("LTFJ 150520Z 00000KT 3000 MIFG SCT020 06/06 Q1020", ZAMAN)
    assert o["sis_kodu"] == 0
    assert o["sis"] == 0


def test_sicaklik_veya_gorus_yoksa_satir_atlanir():
    """Sicaklik/cig noktasi olmadan ne spread ne etiket uretilebilir."""
    assert ozellik.ozellik_cikar("LTFJ 150520Z 06008KT 9999 SCT020 Q1018", ZAMAN) is None


def test_bozuk_metar_hata_vermez():
    assert ozellik.ozellik_cikar("BOZUK VERI", ZAMAN) is None


def test_sutunlar_ozellik_anahtarlariyla_ayni():
    """SUTUNLAR listesi veri_cek.py'nin CSV basligini belirler - ozellik
    sozlugunun anahtarlariyla birebir ayni olmali, yoksa sessizce sutun
    kaybederiz."""
    o = ozellik.ozellik_cikar("LTFJ 150520Z 06008KT CAVOK 12/03 Q1018", ZAMAN)
    assert set(o) == set(ozellik.SUTUNLAR)


# ------------------------------------------------------------- istatistik
def test_istatistik_gzip_veriyi_okuyabiliyor(tmp_path):
    yol = tmp_path / "ornek.csv.gz"
    with gzip.open(yol, "wt", encoding="utf-8", newline="") as f:
        f.write(",".join(ozellik.SUTUNLAR) + "\n")
        f.write("2024-01-15T05:20,1,5,3,3,0.0,0,,400,100,1020,1,1,1\n")
        f.write("2024-06-15T12:20,6,12,28,10,18.0,8,60,9999,,1015,0,0,0\n")
    satirlar = istatistik.veri_oku(yol)
    assert len(satirlar) == 2
    assert satirlar[0]["sis"] == 1 and satirlar[1]["sis"] == 0
    assert satirlar[0]["ruzgar_yon"] is None      # bos alan None kalmali
    assert satirlar[1]["spread"] == 18.0


def test_bozuk_sayisal_alan_raporu_cokertmez(tmp_path):
    """375 bin satirlik bir arsivde tek bir beklenmedik deger butun analizi
    dusurmemeli - bozuk alan None'a duser, satir korunur."""
    yol = tmp_path / "bozuk.csv.gz"
    with gzip.open(yol, "wt", encoding="utf-8", newline="") as f:
        f.write(",".join(ozellik.SUTUNLAR) + "\n")
        f.write("2024-01-15T05:20,1,5,3,3,0.0,M,,400,100,1020,1,1,1\n")
    satirlar = istatistik.veri_oku(yol)
    assert len(satirlar) == 1
    assert satirlar[0]["ruzgar_hiz"] is None       # "M" -> None, exception yok
    assert satirlar[0]["gorus"] == 400


def test_ondalikli_deger_float_olarak_okunur(tmp_path):
    yol = tmp_path / "ondalik.csv.gz"
    with gzip.open(yol, "wt", encoding="utf-8", newline="") as f:
        f.write(",".join(ozellik.SUTUNLAR) + "\n")
        f.write("2024-01-15T05:20,1,5,10,7.5,2.5,4,60,9999,,1020,0,0,0\n")
    satirlar = istatistik.veri_oku(yol)
    assert satirlar[0]["cig_noktasi"] == 7.5
    assert satirlar[0]["spread"] == 2.5


# ------------------------------------------------------------- izolasyon
def test_calisma_ani_modulleri_sis_modeline_bagimli_degil():
    """Alt proje AGIR (pandas vb.) olabilir; botun her 15 dakikada bir calisan
    akisi ona HIC dokunmamali. AST ile gercek import ifadeleri kontrol edilir."""
    for dosya in CALISMA_ANI_MODULLERI:
        yol = KOK / dosya
        if not yol.exists():
            continue
        agac = ast.parse(yol.read_text(encoding="utf-8"))
        for node in ast.walk(agac):
            if isinstance(node, ast.Import):
                adlar = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                adlar = [node.module or ""]
            else:
                continue
            for ad in adlar:
                assert not ad.startswith("sis_modeli"), (
                    f"{dosya} calisma aninda sis_modeli'ni import ediyor - "
                    "izolasyon sozlesmesi ihlali (bkz. sis_modeli/README.md)")


def test_alt_proje_kendi_metar_ayristiricisini_yazmiyor():
    """Bagimlilik yonu tek tarafli: sis_modeli ana projenin test edilmis
    ayristiricisini KULLANIR, kendi regex'ini kurmaz."""
    kaynak = (KOK / "sis_modeli" / "ozellik.py").read_text(encoding="utf-8")
    assert "from ltfj_analiz import" in kaynak
    assert "re.compile" not in kaynak


def test_ham_arsiv_repoya_yazilmiyor():
    """veri_cek.py ham CSV'yi diske dokmemeli - satirlar aninda ayristirilip
    sadece turetilmis alanlar gzip'e yazilmali (repo kucuk kalsin)."""
    kaynak = (KOK / "sis_modeli" / "veri_cek.py").read_text(encoding="utf-8")
    assert "gzip.open" in kaynak
    assert ".csv.gz" in kaynak
