"""Tavan için GÖRÜŞSÜZ iki model (A: süreklilik, B: oluşum) testleri.

En kritik üç test:
(1) dogrula_b() tavanın KENDİSİNİ de yasaklıyor - Model B'ye sızarsa
    süreklilik olurdu, oluşum değil (Model A/B ayrımının temeli),
(2) hazirla_tum() onset filtresiz TAM kayıt kümesini dönüyor - bağımsız
    olay tanımlaması bunsuz yanlış sınır bulur,
(3) ALANLAR_A ve ALANLAR_B'nin ikisi de kendi yasak listelerini geçiyor -
    CI her çalıştığında bunu otomatik denetler.
"""
import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sis_modeli import bolme, tavan, tavan_gorussuz as tg

KOK = Path(__file__).resolve().parent.parent


def _seri(tavan_dizisi, n=48, yil=2020):
    baslangic = datetime(yil, 1, 15, tzinfo=timezone.utc)
    satirlar = []
    for i in range(n):
        t = baslangic + timedelta(minutes=30 * i)
        satirlar.append({
            "zaman": t.strftime("%Y-%m-%dT%H:%M"), "ay": t.month, "saat": t.hour,
            "sicaklik": 10, "cig_noktasi": 8, "spread": 2.0, "ruzgar_hiz": 5,
            "ruzgar_yon": 90, "gorus": 9999, "tavan": tavan_dizisi[i],
            "qnh": 1015, "sis_kodu": 0, "sis": 0, "lvo": 0,
        })
    return satirlar


# ------------------------------------------------------------------- yasak
def test_dogrula_b_tavani_yasakliyor():
    with pytest.raises(ValueError, match="tavan"):
        tg.dogrula_b(["spread", "tavan"])


def test_dogrula_b_tavan_ozelligini_yasakliyor():
    with pytest.raises(ValueError):
        tg.dogrula_b(["spread", "tavan_ozellik"])


def test_dogrula_b_gorusu_de_yasakliyor():
    """Model B, olusum_alanlar.YASAKLI'yi (gorus dahil) MIRAS alıyor."""
    with pytest.raises(ValueError):
        tg.dogrula_b(["gorus"])


def test_dogrula_b_guvenli_listede_sorunsuz():
    tg.dogrula_b(["spread", "saat", "ruzgar_kuzey"])   # patlamamalı


def test_alanlar_a_gorus_icermiyor_ama_tavan_icerir():
    """Model A görüşsüz ama SÜREKLİLİK olduğu için tavan_ozellik'i
    kasıtlı olarak İÇERİR - bu yasaklı değil."""
    assert "gorus" not in tg.ALANLAR_A
    assert "tavan_ozellik" in tg.ALANLAR_A


def test_alanlar_b_gecerli():
    """CI koruması: ALANLAR_B her zaman kendi yasak listesini geçmeli."""
    tg.dogrula_b(tg.ALANLAR_B)
    assert "tavan" not in tg.ALANLAR_B and "tavan_ozellik" not in tg.ALANLAR_B


# ------------------------------------------------------------ hazirla_tum
def test_hazirla_tum_onset_filtresiz_tum_kayitlari_donuyor():
    """tavan.hazirla() yalnizca onset adaylarini dondurur (tavan_dusuk=0);
    hazirla_tum() ise TUMUNU - bagimsiz olay tanimlamasi icin sart."""
    tavanlar = [None] * 20 + [300] * 2 + [None] * 26     # 2020 -> rejim içinde
    tum = tg.hazirla_tum(_seri(tavanlar))
    # tavan_dusuk=1 olan satirlar da (20, 21) sette kalmali
    pozitif_sayisi = sum(r["tavan_dusuk"] for r in tum)
    assert pozitif_sayisi == 2


def test_onset_kumesi_pozitifleri_disliyor():
    tavanlar = [None] * 20 + [300] * 2 + [None] * 26
    tum = tg.hazirla_tum(_seri(tavanlar))
    aday = tg.onset_kumesi(tum)
    assert all(r["tavan_dusuk"] == 0 for r in aday)
    assert len(aday) == len(tum) - 2


def test_hazirla_tum_tavan_ozelligi_ve_sis_yakinligi_ekliyor():
    tavanlar = [3000] * 48
    tum = tg.hazirla_tum(_seri(tavanlar))
    assert all("tavan_ozellik" in r for r in tum)
    assert all("sis_yakinligi" in r for r in tum)


def test_hazirla_tum_rejim_disini_disliyor():
    """2016 (rejim disi) veriler tamamen elenmeli."""
    tavanlar = [300] * 48
    tum = tg.hazirla_tum(_seri(tavanlar, yil=2016))
    assert tum == []


# ---------------------------------------------------------------- wf_olc
def _dev_seri(gun_sayisi=40, pozitif_gunler=(5, 15, 25)):
    """Basit sentetik bir gelistirme kumesi - dt/gun alanlari icin
    hedef.hazirla() ile isleniyor."""
    from sis_modeli import hedef

    satirlar = []
    for gun in range(gun_sayisi):
        for saat in range(0, 24, 3):
            t = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=gun, hours=saat)
            dusuk = gun in pozitif_gunler and 0 <= saat < 6
            satirlar.append({
                "zaman": t.strftime("%Y-%m-%dT%H:%M"), "ay": t.month, "saat": t.hour,
                "spread": 0.5 if dusuk else 5.0, "ruzgar_hiz": 3, "ruzgar_yon": 0,
                "tavan_dusuk": int(dusuk),
            })
    return hedef.hazirla(satirlar, etiket="tavan_dusuk")


def test_wf_olc_temel_alanlarla_cokmez():
    gel = _dev_seri()
    for r in gel:
        r["dt"] = r["dt"].replace(year=2018 if r["dt"].month <= 6 else 2019)
        r["gun"] = r["dt"].strftime("%Y-%m-%d")
    sonuc = tg.wf_olc(gel, ["spread", "saat"])
    assert 0.0 <= sonuc["ap"] <= 1.0
    assert "tahmin_map" in sonuc


# -------------------------------------------------------------- izolasyon
def test_calisma_ani_modulu_tavan_gorussuzu_import_etmiyor():
    for dosya in ("ltfj_sis_olasilik.py", "ltfj_tavan_tablosu.py",
                  "ltfj_sayfa.py", "ltfj_bot.py", "ltfj_lvo_farkindalik.py"):
        agac = ast.parse((KOK / dosya).read_text(encoding="utf-8"))
        for node in ast.walk(agac):
            adlar = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom)
                     else [])
            assert "tavan_gorussuz" not in adlar, dosya


def test_agir_bagimlilik_yok():
    izinli = {"ltfj_analiz"}
    agac = ast.parse((KOK / "sis_modeli" / "tavan_gorussuz.py").read_text(encoding="utf-8"))
    for node in ast.walk(agac):
        if isinstance(node, ast.Import):
            for a in node.names:
                kok = a.name.split(".")[0]
                assert (kok.startswith("sis_modeli") or kok in izinli or
                       kok in ("sys", "argparse", "pathlib")), kok
        elif isinstance(node, ast.ImportFrom) and node.module:
            kok = node.module.split(".")[0]
            assert kok.startswith("sis_modeli") or kok in izinli or kok == "pathlib", kok
