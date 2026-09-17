"""VFR sekmesi (ltfj_sayfa.py) testleri - sayfa kenarindaki gosterge
dogru renk/sebep metniyle render ediliyor mu, ve statik/JS-toggle-only
oldugu (hicbir fetch() yapmadigi) dogrulanir."""
from datetime import datetime, timezone

import ltfj_sayfa as s

_ORTAK = {"zaman": datetime(2026, 9, 16, 12, 50, tzinfo=timezone.utc), "icao": "LTFJ"}


def _sayfa_yaz(tmp_path, metin) -> str:
    hedef = tmp_path / "index.html"
    rapor = {"tip": "METAR", "metin": metin, **_ORTAK}
    s.sayfa_yaz([rapor], [], hedef, {}, "")
    return hedef.read_text(encoding="utf-8")


def test_iyi_havada_vfr_sekmesi_yesil(tmp_path):
    html = _sayfa_yaz(tmp_path, "LTFJ 161250Z 06010KT 9999 FEW020 22/15 Q1013 NOSIG")
    assert 'id="vfr-sekme" class="vfr-sekme vfr-yesil"' in html
    assert "VFR şartları sağlanıyor" in html


def test_dusuk_gorus_ve_tavanda_vfr_sekmesi_kirmizi(tmp_path):
    html = _sayfa_yaz(tmp_path, "LTFJ 161250Z 06010KT 3000 BKN008 22/15 Q1013 NOSIG")
    assert 'id="vfr-sekme" class="vfr-sekme vfr-kirmizi"' in html
    assert "VFR şartları sağlanmıyor" in html
    assert "Görüş 3000 m" in html
    assert "Tavan 800 ft" in html


def test_esik_metinleri_panelde_gorunur(tmp_path):
    html = _sayfa_yaz(tmp_path, "LTFJ 161250Z 06010KT 9999 FEW020 22/15 Q1013 NOSIG")
    assert "görüş ≥ 5000 m" in html
    assert "tavan ≥ 1500 ft" in html
    assert "ICAO Annex 2" in html


def test_rapor_yoksa_hata_vermez_bilinmiyor_gosterir(tmp_path):
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([], [], hedef, {}, "")
    html = hedef.read_text(encoding="utf-8")
    assert 'class="vfr-sekme vfr-bilinmiyor"' in html
    assert "VFR değerlendirilemiyor" in html


def test_vfr_panel_toggle_scripti_var_fetch_yok(tmp_path):
    """VFR sekmesi tamamen statik render edilir - script sadece ac/kapa
    yapmali, hicbir fetch() cagrisi icermemeli (ATC/NOTAM/LVO script'lerinin
    aksine)."""
    html = _sayfa_yaz(tmp_path, "LTFJ 161250Z 06010KT 9999 FEW020 22/15 Q1013 NOSIG")
    assert 'document.getElementById("vfr-sekme")' in html
    idx = html.index('document.getElementById("vfr-sekme")')
    blok = html[idx - 200: idx + 700]
    yurutulen = "\n".join(satir for satir in blok.splitlines()
                           if not satir.strip().startswith("//"))
    assert "fetch(" not in yurutulen
