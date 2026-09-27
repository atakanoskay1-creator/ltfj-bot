"""Bot, "su an" raporunu listenin SIRASINA degil ZAMANINA gore seciyor mu?

Eskiden durum_mesaji_kur ve state["son_metar"] `next(...)` ile listenin
ILK gozlemini aliyordu - yani raporlari_cek'in "en yeni basta" siralamasina
ortuk olarak guveniyordu. Siralama bugun dogru; bu testler, bir gun
bozulursa bot'un sessizce ESKI bir raporu "su an" diye yazmayacagini
kilitliyor.
"""
import inspect
from datetime import datetime, timedelta, timezone

import pytest

import ltfj_bot as b

T0 = datetime(2026, 9, 27, 12, 20, tzinfo=timezone.utc)


def _r(tip, dk, metin, zaman=True):
    return {"tip": tip, "id": dk, "duzeltme": None,
            "zaman": (T0 + timedelta(minutes=dk)) if zaman else None,
            "metin": metin}


ESKI = _r("METAR", 0, "METAR LTFJ 271220Z 04008KT 9999 FEW030 17/13 Q1018")
SPECI = _r("SPECI", 17, "SPECI LTFJ 271237Z 04015KT 0800 FG VV002 14/14 Q1018")
TAF_ESKI = _r("TAF", -300, "TAF LTFJ 270700Z 2709/2809 04010KT 9999 SCT030")
TAF_YENI = _r("TAF", -60, "TAF LTFJ 271100Z 2712/2812 04012KT 9999 BKN025")


@pytest.mark.parametrize("sira", [
    [SPECI, ESKI],          # kaynagin bugunku sirasi
    [ESKI, SPECI],          # TERS - eski kod burada ESKI'yi seciyordu
])
def test_en_yeni_gozlem_SIRADAN_BAGIMSIZ(sira):
    assert b.en_yeni_rapor(sira, b.GOZLEM_TIPLERI) is SPECI


def test_TAF_de_zamana_gore_seciliyor():
    assert b.en_yeni_rapor([TAF_ESKI, TAF_YENI], ("TAF",)) is TAF_YENI


def test_tip_suzgeci_TAFi_gozlem_sanmiyor():
    """TAF gozlemlerden daha yeni olabilir; 'su an' gozlemi olmamali."""
    taf_cok_yeni = _r("TAF", 60, "TAF LTFJ 271320Z 2715/2815 04012KT 9999")
    assert b.en_yeni_rapor([ESKI, taf_cok_yeni], b.GOZLEM_TIPLERI) is ESKI


def test_zamansiz_rapor_zamanliya_KAZANAMAZ():
    """Kaynak da ayni kurali kullaniyor: zamani okunamayan rapor en eski."""
    zamansiz = _r("METAR", 999, "METAR LTFJ 27//// 00000KT 9999", zaman=False)
    assert b.en_yeni_rapor([zamansiz, ESKI], b.GOZLEM_TIPLERI) is ESKI


def test_esit_zamanda_LISTEDEKI_ILK_kazanir():
    """Ayni dakikanin COR'u kaynakta once gelir; beraberlikte sira korunur."""
    cor = dict(ESKI, duzeltme="COR", metin=ESKI["metin"].replace("FEW030", "SCT030"))
    assert b.en_yeni_rapor([cor, ESKI], b.GOZLEM_TIPLERI) is cor


def test_bos_liste_None():
    assert b.en_yeni_rapor([], b.GOZLEM_TIPLERI) is None
    assert b.en_yeni_rapor([TAF_YENI], b.GOZLEM_TIPLERI) is None


def test_durum_mesaji_TERS_listede_de_SPECIyi_gosteriyor(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    state = b.state_oku()
    mesaj = b.durum_mesaji_kur([ESKI, TAF_ESKI, SPECI, TAF_YENI], state)
    assert "271237Z" in mesaj, "en yeni gozlem (SPECI) mesajda yok"
    assert "271220Z" not in mesaj, "eski METAR 'su an' diye yazilmis"
    assert "271100Z" in mesaj and "270700Z" not in mesaj, "eski TAF secilmis"


def test_son_metar_da_ayni_yardimciyi_kullaniyor():
    """main() dogrudan test edilemiyor (ag + Telegram); son_metar'in
    listenin ilkinden degil yardimcidan geldigini kaynaktan dogruluyoruz."""
    kaynak = inspect.getsource(b.main)
    blok = kaynak.split('state["son_metar"] =')[0].rsplit("\n\n", 1)[-1]
    assert "en_yeni_rapor(raporlar, GOZLEM_TIPLERI)" in blok
    assert 'if r["tip"] in ("METAR", "SPECI")' not in blok
