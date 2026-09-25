"""NOTAM senkron araligi TEK KAYNAK mi?

Ayni sayi eskiden UC yerde duruyordu: ltfj_ayarlar.VARSAYILAN,
ltfj_bot'taki `varsayilan=6` ve web sayfasinin JS'indeki
`NOTAM_BAYAT_MS = 12 * 3600 * 1000` - sonuncusu "6 saatin iki kati"
diye ELLE yazilmisti, yaninda da "ayarlarda 6 saat" diyen bir yorum.

Ayar 6'dan 3'e cekilince o sabit yerinde kalirdi: bayatlik esigi 2x
yerine 4x olur, yani NOTAC erisilemez oldugunda sayfa bunu 6 saat
yerine 12 saat sonra soylerdi. Kullanici o sure boyunca ekranda duran
eski NOTAM listesine bakmaya devam ederdi. Bu testler o sapmanin geri
gelmesini engelliyor."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

import ltfj_ayarlar as ayarlar
import ltfj_sayfa as s

METAR = {"tip": "METAR", "icao": "LTFJ",
         "zaman": datetime.now(timezone.utc),
         "metin": "LTFJ 241720Z 06010KT 9999 FEW030 12/08 Q1013"}


def _sayfa(tmp_path) -> str:
    hedef = tmp_path / "i.html"
    s.sayfa_yaz([METAR], [], hedef)
    return hedef.read_text(encoding="utf-8")


def test_ayarlar_json_uc_saat():
    """Kullanicinin istedigi deger; ayrica VARSAYILAN ile de tutarli
    olmali - dosyayi silsek bot ayni sikligi kullanmali."""
    gelen = json.loads(Path(ayarlar.DOSYA).read_text(encoding="utf-8"))
    assert gelen["notam"]["senkron_araligi_saat"] == 3
    assert ayarlar.VARSAYILAN["notam"]["senkron_araligi_saat"] == 3
    assert ayarlar.notam_senkron_araligi_saat() == 3


def test_bayat_esigi_ARALIGIN_IKI_KATI():
    """Bir senkron kacmak olagan, ikisi degil."""
    assert ayarlar.notam_bayat_saat() == ayarlar.notam_senkron_araligi_saat() * 2


def test_sayfadaki_esik_AYARDAN_turiyor(tmp_path):
    html_metin = _sayfa(tmp_path)
    m = re.search(r"var NOTAM_BAYAT_MS = (\d+(?:\.\d+)?) \* 3600 \* 1000;", html_metin)
    assert m, "NOTAM_BAYAT_MS bulunamadi"
    assert float(m.group(1)) == ayarlar.notam_bayat_saat()


def test_sayfada_ELLE_YAZILMIS_12_saat_kalmadi(tmp_path):
    """Regresyon capasi: eski sabitin kendisi."""
    assert "NOTAM_BAYAT_MS = 12 * 3600 * 1000" not in _sayfa(tmp_path)


def test_ayar_degisince_sayfa_KENDILIGINDEN_takip_ediyor(tmp_path, monkeypatch):
    """Asil iddia. Ayari 8'e cekiyoruz; sayfanin esigi elle hicbir sey
    yapmadan 16 saate cikmali."""
    monkeypatch.setitem(ayarlar.AYARLAR["notam"], "senkron_araligi_saat", 8)
    html_metin = _sayfa(tmp_path)
    m = re.search(r"var NOTAM_BAYAT_MS = (\d+(?:\.\d+)?) \* 3600 \* 1000;", html_metin)
    assert float(m.group(1)) == 16


@pytest.mark.parametrize("bozuk", [0, -3, True, "uc", None, 0.0])
def test_anlamsiz_deger_VARSAYILANA_duser(monkeypatch, bozuk):
    """0 ya da negatif bir aralik senkronu HER KOSUDA tetiklerdi - yani
    15 dakikada bir NOTAC'a gidilirdi. True'nun ayrica elenmesi lazim:
    Python'da bool bir int ve `True > 0` dogrudur, yani "aktif" diye
    yazilmis bir deger sessizce "1 saat" olurdu."""
    monkeypatch.setitem(ayarlar.AYARLAR["notam"], "senkron_araligi_saat", bozuk)
    assert ayarlar.notam_senkron_araligi_saat() == 3
