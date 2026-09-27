"""CSS/JS'in sayfa_kaynak/ altina tasinmasinin sozlesmesi.

Tasima sirasinda uretilen sayfa, saat dondurularak once/sonra uretildi
ve BAYT BAYT AYNI cikti. Bu testler o esdegerligi bir sonraki
degisiklikte de koruyacak yapisal kurallari kilitliyor.
"""
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

import ltfj_sayfa as s

KLASOR = Path(s.VARLIK_KLASORU)


def _sayfa(tmp_path):
    hedef = tmp_path / "i.html"
    metin = "METAR LTFJ 161250Z 06010KT 9999 SCT025 BKN040 18/12 Q1015 NOSIG"
    s.sayfa_yaz([{"tip": "METAR", "icao": "LTFJ", "metin": metin,
                  "zaman": datetime(2026, 9, 16, 12, 50, tzinfo=timezone.utc)}],
                [], hedef, {}, "https://db.example", "PUBKEY")
    return hedef.read_text(encoding="utf-8")


def test_SABLONda_CSS_JS_GOVDESI_YOK():
    """SABLON artik yalnizca iskelet: <style> ve her <script> tek bir yer
    tutucu tasiyor. Biri buraya tekrar satir ici CSS/JS yazarsa
    ikilenmis parantez ve kacis sorunlari geri gelir."""
    assert re.findall(r"<style>(.*?)</style>", s.SABLON, re.S) == ["{stil}"]
    betikler = re.findall(r"<script>(.*?)</script>", s.SABLON, re.S)
    assert betikler == ["{" + yer + "}" for yer, _ in s.BETIK_DOSYALARI]


def test_her_betik_dosyasi_VAR_ve_OKSUZ_dosya_YOK():
    tanimli = {d for _, d in s.BETIK_DOSYALARI} | {s.STIL_DOSYASI}
    diskte = {p.name for p in KLASOR.iterdir() if p.suffix in (".js", ".css")}
    assert tanimli == diskte, (tanimli ^ diskte)


def test_varliklarda_FORMAT_SOZDIZIMI_kalmadi():
    """Dosyalar DUZ CSS/JS: Python degeri yalnizca @@ad@@ ile girer.
    {ad} bicimli bir yer tutucu kalmis olsaydi sayfaya OLDUGU GIBI
    basilirdi ({ikon_kapat} olayinin tam aynisi)."""
    for p in KLASOR.iterdir():
        metin = p.read_text(encoding="utf-8")
        adlar = set(re.findall(r"(?<![\w$@{])\{([a-z_][a-z0-9_]*)\}(?!\})", metin))
        # JS'te {ad} tek basina neredeyse hic gecmez; gecerse bile
        # bilinen bir Python degerinin adi OLMAMALI.
        assert not (adlar & PYTHON_DEGERLERI), (p.name, adlar & PYTHON_DEGERLERI)


PYTHON_DEGERLERI = set(re.findall(r"@@(\w+)@@", "".join(
    p.read_text(encoding="utf-8") for p in KLASOR.iterdir()))) | {
    "icao", "govde", "ikon_kapat", "ikon_zil", "ikon_uyari"}


def test_uretilen_sayfada_DOLDURULMAMIS_isaret_YOK(tmp_path):
    html = _sayfa(tmp_path)
    assert not re.search(r"@@\w+@@", html)


def test_bilinmeyen_isaret_URETIMI_DURDURUR():
    """Sessizce '@@ad@@' birakip sayfaya basmaktansa hata vermek dogru."""
    with pytest.raises(KeyError):
        s._varlik_doldur("x @@olmayan_deger@@ y", {})


def test_isaret_degerin_ICINE_girmez():
    """Tek gecis: bir deger '@@baska@@' icerse bile yeniden taranmaz -
    kullanici verisi (ornegin bir URL) sablon diline sizamaz."""
    assert s._varlik_doldur("@@a@@", {"a": "@@b@@"}) == "@@b@@"


def test_varliklar_sayfaya_giriyor(tmp_path):
    html = _sayfa(tmp_path)
    for _, dosya in s.BETIK_DOSYALARI:
        # her dosyanin ilk anlamli satiri sayfada bulunmali
        satir = next(l for l in (KLASOR / dosya).read_text(encoding="utf-8").splitlines()
                     if l.strip() and "@@" not in l)
        assert satir in html, dosya
    assert "https://db.example" in html and "PUBKEY" in html
