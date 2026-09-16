"""Quiet-hours (sessiz saatler) artik OS/ortam TZ'sine degil, explicit
Europe/Istanbul'a (ltfj_ayarlar.YEREL_TZ) baglaniyor mu?

Bu test rapor'da E.1 diye isaretlenen bug'i kanitliyor: process'in kendi
yerel saat dilimi (ornegin UTC olan bir Docker konteynerinde) ne olursa
olsun sessiz-saat hesaplamasi hep Istanbul saatine gore calismali.

Asagidaki UTC saatleri KASITLI olarak secildi: bunlar tam olarak
"argumansiz astimezone() (OS TZ'sine bagli, eski/bugli davranis)" ile
"astimezone(YEREL_TZ) (yeni, dogru davranis)" FARKLI sonuc verdigi
noktalar - yani testler eski koda karsi calistirilsaydi FAIL olurlardi.
(06:30 UTC = Istanbul 09:30 -> gunduz; 20:30 UTC = Istanbul 23:30 -> sessiz.)
"""
from datetime import datetime, timezone

import ltfj_bot as b
from ltfj_ayarlar import YEREL_TZ


def _sessiz_saatler_ac(monkeypatch, baslangic="23:00", bitis="07:00"):
    def sahte_ayar(*yol, varsayilan=None):
        if yol == ("bildirim", "sessiz_saatler"):
            return {"aktif": True, "baslangic": baslangic, "bitis": bitis}
        return varsayilan
    monkeypatch.setattr(b, "ayar", sahte_ayar)


def test_yerel_tz_gercekten_istanbul():
    assert str(YEREL_TZ) == "Europe/Istanbul"


def test_istanbul_ofseti_yil_boyu_sabit_3_saat():
    # Turkiye 2016'dan beri DST uygulamiyor, Europe/Istanbul yil boyu UTC+3.
    kis = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    yaz = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    assert kis.astimezone(YEREL_TZ).utcoffset().total_seconds() == 3 * 3600
    assert yaz.astimezone(YEREL_TZ).utcoffset().total_seconds() == 3 * 3600


def test_utc_0630_istanbulda_gunduz_sessiz_degil(monkeypatch):
    """UTC 06:30 = Istanbul 09:30 (gunduz). Eger kod yanlislikla UTC'yi
    'yerel' sansaydi 06:30 hala 23:00-07:00 sessiz araliginda sayilir ve
    onemli bir bildirim YANLISLIKLA sessize alinirdi."""
    _sessiz_saatler_ac(monkeypatch)
    zaman = datetime(2026, 1, 15, 6, 30, tzinfo=timezone.utc)
    assert b._sessiz_saatte_mi(zaman) is False


def test_utc_2030_istanbulda_gece_sessiz(monkeypatch):
    """UTC 20:30 = Istanbul 23:30 (sessiz saat icinde). Eger kod yanlislikla
    UTC'yi 'yerel' sansaydi 20:30 sessiz araligin DISINDA sayilir ve gece
    yarisina yakin gereksiz bir bildirim giderdi."""
    _sessiz_saatler_ac(monkeypatch)
    zaman = datetime(2026, 1, 15, 20, 30, tzinfo=timezone.utc)
    assert b._sessiz_saatte_mi(zaman) is True


def test_sessiz_saat_ortam_tz_degiskeninden_bagimsiz(monkeypatch):
    """Bug'in tam senaryosu: process'in OS-seviyesi TZ'si UTC olsa bile
    (TZ env degistirilse bile) sonuc degismemeli, cunku artik
    ZoneInfo('Europe/Istanbul') ACIKCA kullaniliyor, argumansiz
    astimezone() ile ortama guvenilmiyor."""
    _sessiz_saatler_ac(monkeypatch)
    monkeypatch.setenv("TZ", "UTC")
    zaman = datetime(2026, 1, 15, 6, 30, tzinfo=timezone.utc)
    assert b._sessiz_saatte_mi(zaman) is False  # Istanbul'da 09:30, gunduz


def test_sessiz_saatler_kapaliysa_hep_false(monkeypatch):
    def sahte_ayar(*yol, varsayilan=None):
        if yol == ("bildirim", "sessiz_saatler"):
            return {"aktif": False}
        return varsayilan
    monkeypatch.setattr(b, "ayar", sahte_ayar)
    zaman = datetime(2026, 1, 15, 20, 30, tzinfo=timezone.utc)
    assert b._sessiz_saatte_mi(zaman) is False
