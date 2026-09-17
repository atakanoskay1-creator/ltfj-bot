"""LVO REFERENCE paneli (ltfj_sayfa.py) testleri.

Bu panel bilgi amaçlıdır; testler ozellikle su ikisini dogruluyor:
(1) dokuman referans verisinin sayfada gorunmesi,
(2) sayfanin HICBIR operasyonel karar ifadesi URETMEDIGI - "LVO aktif",
    "kullanilabilir", "use runway" gibi sonuc cumleleri sayfada yer almamali,
    sadece dokuman/AWOS/ATIS/NOTAM bilgisi kaynagiyla birlikte gosterilmeli."""
import re
from datetime import datetime, timezone
from pathlib import Path

import ltfj_sayfa as s

METAR_ORNEK = {
    "tip": "METAR",
    "metin": "LTFJ 161250Z 06010KT 9999 FEW020 22/15 Q1013 NOSIG",
    "zaman": datetime(2026, 9, 16, 12, 50, tzinfo=timezone.utc),
    "icao": "LTFJ",
}

# Sonucun kendisini iddia eden kalip ifadeler - bunlarin HICBIRI sayfada
# olmamali (kelime sinirlariyla, yanlis pozitif onlemek icin).
YASAK_KARAR_KALIPLARI = [
    r"\bLVO\s+aktif\b",
    r"\bLVO\s+is\s+active\b",
    r"\bCAT\s*II\s+(kullanılabilir|available)\b",
    r"\bLVTO\s+(yapılabilir|available)\b",
    r"\buse\s+runway\b",
    r"\bşu\s+pist\s+kullanılmalı\b",
    r"\btherefore\s+use\b",
]


def _sayfa_yaz(tmp_path, db_url="") -> str:
    hedef = tmp_path / "index.html"
    s.sayfa_yaz([METAR_ORNEK], [], hedef, {}, db_url)
    return hedef.read_text(encoding="utf-8")


def test_lvo_bolumu_sayfada_var(tmp_path):
    html = _sayfa_yaz(tmp_path)
    assert "LVO REFERENCE" in html


def test_dokuman_referans_bilgisi_gorunur(tmp_path):
    html = _sayfa_yaz(tmp_path)
    assert "TL.007" in html
    assert "REV.1" in html
    assert "16.08.2024" in html
    assert "DOCUMENT REFERENCE ONLY" in html


def test_bulut_tabani_esikleri_de_gorunur(tmp_path):
    """RVR yaninda bulut tabani (ceiling) esikleri de - RVR'a alternatif/
    paralel bir tetikleyici oldugu icin - dokuman referans bolumunde
    ayrica gosterilmeli (madde 6.2.a, 6.3.1.a)."""
    html = _sayfa_yaz(tmp_path)
    assert "Bulut tabanı" in html
    assert "6.2.a" in html
    assert "6.3.1.a" in html
    assert "pilot raporlarıyla" in html


def test_bilgi_amaclidir_uyarisi_lvo_bolumunde_de_var(tmp_path):
    html = _sayfa_yaz(tmp_path)
    assert "Operasyonel karar yerine geçmez" in html


def test_provenance_etiketleri_gorunur(tmp_path):
    html = _sayfa_yaz(tmp_path)
    assert "MANUAL AWOS" in html
    assert "MANUAL ATIS" in html
    assert ">NOTAM<" in html


def test_manuel_giris_formlari_var(tmp_path):
    html = _sayfa_yaz(tmp_path)
    assert 'id="lvo-awos-kaydet"' in html
    assert 'id="lvo-atis-kaydet"' in html
    assert 'id="lvo-awos-pist"' in html
    assert 'id="lvo-atis-state"' in html


def test_06r_24r_pistleri_awos_formunda_var(tmp_path):
    html = _sayfa_yaz(tmp_path)
    m = re.search(r'<select id="lvo-awos-pist">(.*?)</select>', html, re.S)
    assert m is not None
    assert "06R" in m.group(1) and "24R" in m.group(1)


def test_atis_state_secenekleri_spec_ile_uyumlu(tmp_path):
    html = _sayfa_yaz(tmp_path)
    m = re.search(r'<select id="lvo-atis-state">(.*?)</select>', html, re.S)
    assert m is not None
    icerik = m.group(1)
    for durum in ("NORMAL", "LVO PREPARATION", "LVO IN PROGRESS", "LVTO IN PROGRESS", "UNKNOWN"):
        assert f'value="{durum}"' in icerik


def test_hicbir_operasyonel_karar_ifadesi_uretilmiyor(tmp_path):
    """Gelistirici yorumlari (// ...) TARANMAZ - bu yorumlar zaten "bunu
    URETMEZ" diye ACIKCA yasagi belgeliyor (bkz. LVO script basindaki
    aciklama), kullaniciya GORUNEN bir metin degil. Test, gercekten
    kullaniciya sunulan HTML/metin icinde bu kalipların olmadigini
    dogruluyor."""
    html = _sayfa_yaz(tmp_path)
    gorunur = "\n".join(
        satir for satir in html.splitlines() if not satir.strip().startswith("//")
    )
    for kalip in YASAK_KARAR_KALIPLARI:
        assert not re.search(kalip, gorunur, re.IGNORECASE), f"Yasak ifade bulundu: {kalip}"


def test_sayfa_lvo_db_url_bos_olsa_da_hata_vermez(tmp_path):
    html = _sayfa_yaz(tmp_path, db_url="")
    assert "LVO REFERENCE" in html


def test_notam_lvo_filtresi_mevcut_notam_veri_json_kaynagini_kullanir(tmp_path):
    """Yeni bir NOTAM sistemi kurulmadigini, mevcut notam_veri.json'a
    fetch() ile erisildigini dogrular - baska bir dosya/endpoint UYDURULMUS
    olmamali."""
    html = _sayfa_yaz(tmp_path)
    assert 'fetch("notam_veri.json' in html


def test_lvo_scripti_atc_notes_ve_notam_scriptinden_bagimsiz_degisken_kullanir(tmp_path):
    """LVO script'i digerleriyle degisken PAYLASMAMALI - kendi DB_URL,
    kendi fonksiyon isimleri (awosYukle/atisYukle) ayri bir IIFE icinde
    olmali (bkz. modul ici yorum)."""
    html = _sayfa_yaz(tmp_path)
    assert "awosYukle();" in html
    assert "atisYukle();" in html
    assert html.count("var DB_URL = ") >= 2  # ATC Notes ve LVO script'leri ayri ayri tanimliyor


def test_pist_karar_fonksiyonlarina_yeni_bir_cagri_eklenmedi():
    """ltfj_sayfa.py'nin LVO icin eklenen kismi tercih_edilen_pist() veya
    RVR esik karsilastirma fonksiyonlarini (esik_karsilastir, gorus_
    operasyonu) HIC cagirmamali - LVO paneli sadece pure statik veri +
    AWOS/ATIS/NOTAM okur, meteorolojik karar fonksiyonlarina dokunmaz."""
    kaynak = Path(s.__file__).read_text(encoding="utf-8")
    for yasak in ("tercih_edilen_pist", "esik_karsilastir", "gorus_operasyonu",
                  "LVTO_RVR", "CAT1_TIPIK_RVR"):
        assert yasak not in kaynak, f"ltfj_sayfa.py beklenmedik şekilde '{yasak}' içeriyor"
