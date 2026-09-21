"""ltfj_sayfa.py - Web Push (bildirim) buton/script entegrasyonu testleri.

En kritik test: VAPID public key verilmezse (ayarlar.json'da yapılandırılmamış
kurulumlar için varsayılan) bildirim butonu HTML'e hiç gömülü "hidden"
olarak kalmalı - script kendisi de VAPID_PUBLIC_KEY boşsa erken çıkıyor
(bkz. ltfj_sayfa.py'deki `if (!btn || !VAPID_PUBLIC_KEY) return;`)."""
from datetime import datetime, timezone
from pathlib import Path

import ltfj_sayfa as s

KOK = Path(__file__).resolve().parent.parent

METAR_ORNEK = {
    "tip": "METAR",
    "metin": "LTFJ 172120Z 18005KT CAVOK 22/05 Q1015",
    "zaman": datetime(2026, 9, 17, 21, 20, tzinfo=timezone.utc),
    "icao": "LTFJ",
}


def test_vapid_key_yoksa_buton_hidden_kaliyor(tmp_path):
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([METAR_ORNEK], [], hedef, {}, "", "")
    html = hedef.read_text(encoding="utf-8")
    i = html.index('id="bildirim-izin-btn"')
    blok = html[max(0, i - 200):i + 50]
    assert "hidden" in blok


def test_vapid_key_varsa_scripte_gomuluyor(tmp_path):
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([METAR_ORNEK], [], hedef, {}, "", "BFAKE_TEST_VAPID_KEY")
    html = hedef.read_text(encoding="utf-8")
    assert "BFAKE_TEST_VAPID_KEY" in html
    assert 'id="bildirim-izin-btn"' in html


def test_push_abonelikler_path_kullaniliyor():
    """Client script push_abonelikler path'ine (firebase-rules.json ile
    aynı isim) yazmalı - isim uyuşmazlığı sessizce hiçbir şey kaydetmezdi."""
    assert "push_abonelikler" in (KOK / "ltfj_sayfa.py").read_text(encoding="utf-8")


def test_sw_js_dosyasi_var_ve_push_notificationclick_dinliyor():
    metin = (KOK / "sw.js").read_text(encoding="utf-8")
    assert "addEventListener(\"push\"" in metin
    assert "addEventListener(\"notificationclick\"" in metin
