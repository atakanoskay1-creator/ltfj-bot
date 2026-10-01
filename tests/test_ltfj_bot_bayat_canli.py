"""ltfj_bot.bayat_canliyi_tamamla - MGM anlik ucu (hours=0) eski raporda
takili kalinca sayfa/state h24'teki en yeni raporla devam eder.
Olay: 01.10.2026 12:04Z, h0 09:20 METAR'i, h24 11:50 METAR'i veriyordu."""
from datetime import datetime, timezone
from pathlib import Path

import ltfj_bot as bot


def _r(tip, saat, dakika, id_):
    return {"tip": tip, "zaman": datetime(2026, 10, 1, saat, dakika, tzinfo=timezone.utc),
            "metin": f"{tip} LTFJ 01{saat:02d}{dakika:02d}Z", "id": id_}


H0_BAYAT = [_r("METAR", 9, 20, 1), _r("SPECI", 9, 16, 2), _r("TAF", 8, 0, 3)]
H24 = [_r("METAR", 11, 50, 10), _r("METAR", 11, 20, 9), _r("SPECI", 9, 16, 2),
       _r("METAR", 9, 20, 1), _r("TAF", 8, 0, 3), _r("TAF", 5, 0, 4)]


def test_bayat_canli_h24_en_yenisiyle_tamamlanir():
    sonuc, alinan = bot.bayat_canliyi_tamamla(H0_BAYAT, H24)
    assert [r["id"] for r in alinan] == [10, 2]          # en yeni METAR + en yeni SPECI
    assert [(r["tip"], r["id"]) for r in sonuc] == [("METAR", 10), ("SPECI", 2), ("TAF", 3)]
    assert bot.en_yeni_rapor(sonuc, bot.GOZLEM_TIPLERI)["id"] == 10


def test_guncel_canliya_dokunulmaz():
    h0 = [_r("METAR", 11, 50, 10), _r("TAF", 8, 0, 3)]
    sonuc, alinan = bot.bayat_canliyi_tamamla(h0, H24)
    assert sonuc is h0 and alinan == []


def test_h24_yoksa_ya_da_bossa_canli_aynen():
    assert bot.bayat_canliyi_tamamla(H0_BAYAT, None) == (H0_BAYAT, [])
    assert bot.bayat_canliyi_tamamla(H0_BAYAT, []) == (H0_BAYAT, [])


def test_yalniz_taf_bayatsa_yalniz_taf_alinir():
    h0 = [_r("METAR", 11, 50, 10), _r("TAF", 5, 0, 4)]
    sonuc, alinan = bot.bayat_canliyi_tamamla(h0, H24)
    assert [r["id"] for r in alinan] == [3]
    assert [(r["tip"], r["id"]) for r in sonuc] == [("METAR", 10), ("TAF", 3)]


def test_canli_bossa_h24_en_yenileri_kullanilir():
    sonuc, alinan = bot.bayat_canliyi_tamamla([], H24)
    assert [(r["tip"], r["id"]) for r in sonuc] == [("METAR", 10), ("SPECI", 2), ("TAF", 3)]


def test_main_h24_raporlarini_sessizlik_kontrolunden_once_birlestirir():
    kaynak = Path("bot/ltfj_bot.py").read_text(encoding="utf-8")
    govde = kaynak[kaynak.index("def main():"):]
    assert govde.index("kosu_isle(") < govde.index("bayat_canliyi_tamamla(raporlar") \
        < govde.index("sessizlik_kontrol(state, raporlar")
