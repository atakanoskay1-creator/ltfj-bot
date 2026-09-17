"""sis_modeli/ alt projesi testleri.

Iki sey dogrulanir:
(1) ozellik cikarimi (METAR -> ozellik/etiket) dogru calisiyor,
(2) IZOLASYON SOZLESMESI (bkz. sis_modeli/README.md) kod seviyesinde
    gercekten geceriyor - calisma anindaki bot bu klasore bagimli DEGIL,
    ve alt proje ikinci bir METAR ayristiricisi YAZMIYOR.
"""
import ast
import csv
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


def test_parcali_ve_kismi_sis_alanda_sis_sayilmaz():
    """BCFG (parca parca) / PRFG (kismi): meydanin bir bolumunde sis var ama
    istasyon gorusu yuksek kalabilir. Gercek arsivde bunlar dahil edildiginde
    yaz aylarindaki 'sis' kayitlarinin medyan gorusu 2500 m cikiyordu."""
    for kod in ("BCFG", "PRFG"):
        o = ozellik.ozellik_cikar(
            f"LTFJ 150520Z 00000KT 4000 {kod} SCT020 18/17 Q1015", ZAMAN)
        assert o["sis_kodu"] == 0, kod
        assert o["sis"] == 0, kod


def test_donan_sis_fzfg_alanda_sis_sayilir():
    """FZFG = donan sis - alani kaplayan gercek sistir, SAYILMALI."""
    o = ozellik.ozellik_cikar("LTFJ 150520Z 00000KT 0500 FZFG VV001 M02/M02 Q1030", ZAMAN)
    assert o["sis_kodu"] == 1
    assert o["sis"] == 1 and o["lvo"] == 1


def test_ham_hava_kodlari_saklaniyor():
    """Etiket TANIMI ileride degisirse 20 yillik arsiv yeniden indirilmesin."""
    o = ozellik.ozellik_cikar("LTFJ 150520Z 00000KT 0300 FG VV001 03/03 Q1020", ZAMAN)
    assert o["hava"] == "FG"


def test_atlama_nedeni_ayirt_ediyor():
    """'53.145 satir atlandi' gibi opak bir sayi veri kalitesi sorununu
    gizler - neden bazinda kirilim sart."""
    assert ozellik.atlama_nedeni("LTFJ 150520Z 06008KT CAVOK 12/03 Q1018") is None
    assert ozellik.atlama_nedeni("LTFJ 150520Z 06008KT 9999 SCT020 Q1018") == "sicaklik/cig yok"
    assert ozellik.atlama_nedeni("LTFJ 150520Z 06008KT 12/03 Q1018") == "gorus yok"


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
def _gz_yaz(yol: Path, *kayitlar: dict):
    """Fixture satirlarini SOZLUKTEN yazar: ham virgullu string kullanilsaydi
    SUTUNLAR'a yeni bir alan eklendiginde satirlar sessizce kayar ve testler
    yanlis alani dogrulamaya devam ederdi (bir kez basimiza geldi)."""
    with gzip.open(yol, "wt", encoding="utf-8", newline="") as f:
        yazici = csv.DictWriter(f, fieldnames=list(ozellik.SUTUNLAR))
        yazici.writeheader()
        for k in kayitlar:
            yazici.writerow({alan: k.get(alan, "") for alan in ozellik.SUTUNLAR})


def test_istatistik_gzip_veriyi_okuyabiliyor(tmp_path):
    yol = tmp_path / "ornek.csv.gz"
    _gz_yaz(yol,
            {"zaman": "2024-01-15T05:20", "ay": 1, "saat": 5, "sicaklik": 3,
             "cig_noktasi": 3, "spread": 0.0, "ruzgar_hiz": 0, "gorus": 400,
             "tavan": 100, "qnh": 1020, "hava": "FG", "sis_kodu": 1,
             "sis": 1, "lvo": 1},
            {"zaman": "2024-06-15T12:20", "ay": 6, "saat": 12, "sicaklik": 28,
             "cig_noktasi": 10, "spread": 18.0, "ruzgar_hiz": 8, "ruzgar_yon": 60,
             "gorus": 9999, "qnh": 1015, "sis_kodu": 0, "sis": 0, "lvo": 0})
    satirlar = istatistik.veri_oku(yol)
    assert len(satirlar) == 2
    assert satirlar[0]["sis"] == 1 and satirlar[1]["sis"] == 0
    assert satirlar[0]["ruzgar_yon"] is None      # bos alan None kalmali
    assert satirlar[1]["spread"] == 18.0


def test_bozuk_sayisal_alan_raporu_cokertmez(tmp_path):
    """375 bin satirlik bir arsivde tek bir beklenmedik deger butun analizi
    dusurmemeli - bozuk alan None'a duser, satir korunur."""
    yol = tmp_path / "bozuk.csv.gz"
    _gz_yaz(yol, {"zaman": "2024-01-15T05:20", "ay": 1, "saat": 5, "sicaklik": 3,
                  "cig_noktasi": 3, "spread": 0.0, "ruzgar_hiz": "M", "gorus": 400,
                  "tavan": 100, "qnh": 1020, "hava": "FG", "sis_kodu": 1,
                  "sis": 1, "lvo": 1})
    satirlar = istatistik.veri_oku(yol)
    assert len(satirlar) == 1
    assert satirlar[0]["ruzgar_hiz"] is None       # "M" -> None, exception yok
    assert satirlar[0]["gorus"] == 400


def test_ondalikli_deger_float_olarak_okunur(tmp_path):
    yol = tmp_path / "ondalik.csv.gz"
    _gz_yaz(yol, {"zaman": "2024-01-15T05:20", "ay": 1, "saat": 5, "sicaklik": 10,
                  "cig_noktasi": 7.5, "spread": 2.5, "ruzgar_hiz": 4,
                  "ruzgar_yon": 60, "gorus": 9999, "qnh": 1020,
                  "sis_kodu": 0, "sis": 0, "lvo": 0})
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
