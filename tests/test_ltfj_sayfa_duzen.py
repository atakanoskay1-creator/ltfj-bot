"""Sayfa düzeni: uzun bölümler katlanabilir.

Ölçüm (390px telefon, gerçek veriyle): sayfa 5004 px = 5.9 ekran
kaydırmaya ulaşmıştı ve bunun %43'ü METAR+TAF kartlarıydı (1175+970 px).
Şişmenin sebebi operasyonel satırlar değil, çok paragraflı yapay zekâ
yorumuydu. Katlamadan sonra 3357 px = 4.0 ekran.

KRİTİK: hiçbir şey SİLİNMEDİ - sadece varsayılan olarak kapalı geliyor.
Testler bunu ayrıca doğruluyor, yoksa "temizlik" adı altında bilgi
kaybedilmiş olurdu.
"""
import re
from datetime import datetime, timezone
from pathlib import Path

import ltfj_sayfa as s

METAR = ("METAR LTFJ 220120Z 06004KT 310V080 9999 FEW080 18/16 Q1013 NOSIG "
         "RMK RWY24R 04003KT")
YORUM = ("**Rüzgâr:** Kuzeydoğudan hafif esiyor.\n"
         "**Görüş:** 10 kilometre ve üzeri.\n"
         "**Gökyüzü:** Az bulutlu.")


def _rapor():
    return {"tip": "METAR", "duzeltme": None, "metin": METAR, "icao": "LTFJ",
            "zaman": datetime(2026, 9, 22, 1, 20, tzinfo=timezone.utc)}


def _gecmis(n=8):
    taban = datetime(2026, 9, 22, 0, 0, tzinfo=timezone.utc)
    return [{"zaman": taban.replace(minute=(i * 7) % 60).isoformat(),
             "ruzgar_hiz": 4 + i % 3, "tavan": 8000, "qnh": 1013,
             "sicaklik": 18, "cig_noktasi": 16} for i in range(n)]


def _sayfa(tmp_path, **kw):
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([_rapor()], _gecmis(), hedef, {METAR: YORUM}, **kw)
    return hedef.read_text(encoding="utf-8")


# ------------------------------------------------- 1) METAR/TAF yorumu
def test_yorum_katlanabilir_geliyor(tmp_path):
    html = _sayfa(tmp_path)
    assert '<details class="kat"><summary>' in html
    assert "Genel değerlendirme" in html


def test_yorum_metni_SILINMEDI_sadece_katlandi(tmp_path):
    """En önemli test: katlama bilgi kaybı DEĞİL."""
    html = _sayfa(tmp_path)
    assert "Kuzeydoğudan hafif esiyor" in html
    assert "Az bulutlu" in html


def test_operasyonel_satirlar_ACIK_kaliyor(tmp_path):
    """Kontrolör önce rakamlara bakıyor - özet satırı ve pist rüzgârları
    katlanan bloğun İÇİNDE olmamalı."""
    html = _sayfa(tmp_path)
    yorum_blogu = re.search(r'<details class="kat"><summary>.*?</details>',
                            html, re.S).group(0)
    assert "Pist 06L" not in yorum_blogu
    assert "Pist 06L" in html


# --------------------------------------------------------- 2) NOTAM arama
def test_notam_arama_katlanabilir(tmp_path):
    html = _sayfa(tmp_path)
    assert 'id="notam-gecmis-sayi"' in html
    # Form alanlari hala DOM'da - JS onlara erişebilmeli.
    for eid in ("notam-q", "notam-durum", "notam-arama-temizle"):
        assert 'id="' + eid + '"' in html, eid


def test_notam_gecmis_sayisi_js_ile_dolduruluyor(tmp_path):
    html = _sayfa(tmp_path)
    assert 'getElementById("notam-gecmis-sayi")' in html
    assert "kayıt" in html


# ------------------------------------------------------------- 3) Trend
def test_trend_katlanabilir_ve_rozetli(tmp_path):
    html = _sayfa(tmp_path)
    assert "Trend · son 6 saat" in html
    assert 'class="kat-rozet"' in html


def test_trend_rozeti_guncel_degerleri_gosteriyor(tmp_path):
    """Kapalıyken de bölüm unutulmasın diye son değerler başlıkta."""
    html = _sayfa(tmp_path)
    rozet = re.search(r'Trend · son 6 saat\s*<span class="kat-rozet">([^<]*)</span>', html)
    assert rozet, "Trend rozeti bulunamadı"
    assert "8000ft" in rozet.group(1)
    assert "1013hPa" in rozet.group(1)


def test_trend_grafikleri_SILINMEDI(tmp_path):
    html = _sayfa(tmp_path)
    assert "<svg" in html


# ------------------------------------------------------------ genel
def test_hicbiri_varsayilan_acik_degil(tmp_path):
    """Katlanan bölümler kapalı başlamalı - aksi halde kısalma olmaz."""
    html = _sayfa(tmp_path)
    assert "<details class=\"kat\" open" not in html
    assert "<details class=\"kat kat-kart\" open" not in html


def test_ok_isareti_summary_icin_mutlak_konumlu(tmp_path):
    """Flex kullanınca uzun rozetle başlık üç satıra kırılıyordu."""
    html = _sayfa(tmp_path)
    assert ".kat > summary::after" in html
    blok = html.split(".kat > summary::after")[1][:200]
    assert "position:absolute" in blok
