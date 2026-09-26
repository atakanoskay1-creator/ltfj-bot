"""Tasarım sistemi: renk/yüzey token'ları ve erişilebilirlik.

NEDEN VAR: her anlamsal renk sayfaya DAĞILMIŞ sabit hex olarak duruyordu.
"Dikkat" tonu üç ayrı kuralda, her biri ayrıca iki koyu tema bloğunda —
dokuz yer. Birini güncelleyip ötekileri unutmak an meselesiydi; bu testler
tam olarak o sessiz sapmayı yakalar.

EN KRİTİK İKİSİ:
  1) KONTRAST ÖLÇÜLÜR, iddia edilmez. Token değerleri CSS'ten okunup
     WCAG AA (4.5:1) eşiğine karşı hesaplanır.
  2) ANLAMSAL RENK SABİT HEX OLARAK TEKRAR GİRMESİN - bir sonraki kişi
     "hızlıca" #ef4444 yazarsa test kırmızıya döner.
"""
import re
from datetime import datetime, timedelta, timezone

import ltfj_sayfa as s

SIMDI = datetime.now(timezone.utc)
AA = 4.5


def _sayfa(tmp_path) -> str:
    hedef = tmp_path / "index.html"
    rapor = {"tip": "METAR", "zaman": SIMDI, "icao": "LTFJ",
             "metin": "LTFJ 231420Z 06005KT 1500 BR SCT008 06/06 Q1020"}
    gecmis = [{"zaman": (SIMDI - timedelta(hours=h)).isoformat(),
               "ruzgar_hiz": 3, "tavan": 600, "qnh": 1020,
               "sicaklik": 6, "cig_noktasi": 6 - h * 0.3} for h in range(7, -1, -1)]
    s.sayfa_yaz([rapor], gecmis, hedef)
    return hedef.read_text(encoding="utf-8")


# ----------------------------------------------------------- kontrast
def _isik(h):
    h = h.lstrip("#")
    def k(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * k(r) + 0.7152 * k(g) + 0.0722 * k(b)


def _kontrast(on, arka):
    a, b = _isik(on), _isik(arka)
    a, b = max(a, b), min(a, b)
    return (a + 0.05) / (b + 0.05)


def _harmanla(ust, alt, alfa):
    ust, alt = ust.lstrip("#"), alt.lstrip("#")
    return "#" + "".join(
        f"{round(int(ust[i:i+2], 16) * alfa + int(alt[i:i+2], 16) * (1 - alfa)):02x}"
        for i in (0, 2, 4))


def _token(html: str, ad: str, koyu=False) -> str:
    """Token değerini CSS'in KENDİSİNDEN okur - test sabit bir kopya
    tutsaydı, kaynak değişince test yine geçer ve hata gizlenirdi."""
    blok = html.split(':root[data-theme="dark"] {')[1] if koyu else html.split(":root {")[1]
    m = re.search(rf"{re.escape(ad)}:(#[0-9a-fA-F]{{3,8}})", blok.split("}")[0])
    assert m, f"{ad} token'ı bulunamadı ({'koyu' if koyu else 'açık'})"
    return m.group(1)


def test_sis_bandi_tonlari_AA_geciyor(tmp_path):
    """Sis olasılığı bandı operasyonel bir uyarı taşıyor; okunamazsa işe
    yaramaz. Zemin yarı saydam, o yüzden kart üstüne HARMANLANARAK ölçülür."""
    html = _sayfa(tmp_path)
    for koyu, kart in ((False, "#ffffff"), (True, "#111a2e")):
        for metin_token, zemin_dolu in (("--iyi", "#22c55e"), ("--uyari-metin", "#ef4444")):
            on = _token(html, metin_token, koyu)
            arka = _harmanla(zemin_dolu, kart, 0x26 / 255)
            oran = _kontrast(on, arka)
            assert oran >= AA, (
                f"{'koyu' if koyu else 'açık'} tema {metin_token}: "
                f"{oran:.2f}:1 < {AA}")


def test_dikkat_tonu_AA_geciyor(tmp_path):
    """Bayat NOTAM / sis saati uyarısı düz kart üstünde duruyor."""
    html = _sayfa(tmp_path)
    for koyu, kart in ((False, "#ffffff"), (True, "#111a2e")):
        oran = _kontrast(_token(html, "--dikkat", koyu), kart)
        assert oran >= AA, f"{'koyu' if koyu else 'açık'} --dikkat: {oran:.2f}:1"


# ------------------------------------------- sabit hex geri sizmasin
ANLAMSAL_HEX = ("#b45309", "#fbbf24", "#16a34a", "#dc2626", "#22c55e26", "#ef444426")


def test_anlamsal_renkler_KURAL_ICINDE_sabit_hex_DEGIL(tmp_path):
    """Bu hex'ler yalnızca token TANIMINDA geçebilir. Bir CSS kuralının
    içinde yeniden belirirlerse tema başına üçleme geri gelmiş demektir."""
    html = _sayfa(tmp_path)
    css = html.split("<style>")[1].split("</style>")[0]
    # 1) CSS YORUMLARINI AT. Yorum bir kural değildir; ayrıca token'ların
    #    gerekçesi doğal olarak eski hex değerlerini anıyor ve testin ilk
    #    sürümü tam da kendi açıklama metnine takılmıştı.
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    # 2) Token TANIMLARINI at: "--ad:#deger" meşru tek yerdir.
    kural_ici = re.sub(r"--[a-z0-9-]+:\s*#[0-9a-fA-F]{3,8}", "", css)
    for h in ANLAMSAL_HEX:
        assert h not in kural_ici, f"{h} bir CSS kuralında sabit yazılmış"


def test_tema_ezmeleri_TEKRARLANMIYOR(tmp_path):
    """Eskiden .tahmin-sis ve .notam-durum-gecmis için ayrı koyu tema
    kuralları vardı; token'la birlikte gereksizleştiler."""
    html = _sayfa(tmp_path)
    # .tahmin-hucre-sis -> .tahmin-sisli (serit tabloya cevrildi:
    # artik tek hucrenin kenarligi degil tum kolonun zemini).
    for secici in (".tahmin-sisli", ".tahmin-sis", ".notam-durum-gecmis"):
        assert html.count(secici + " {") == 1, f"{secici} birden fazla kuralda"


# --------------------------------------------------------- katmanlar
def test_yuzey_katmanlari_AYRISIYOR(tmp_path):
    """zemin -> panel -> kart -> etkileşim: her katman bir üstünden
    ayırt edilebilmeli, yoksa hiyerarşi görünmez."""
    html = _sayfa(tmp_path)
    for koyu in (False, True):
        d = [_isik(_token(html, t, koyu)) for t in ("--bg", "--panel", "--kart")]
        assert len(set(round(x, 4) for x in d)) == 3, (
            f"{'koyu' if koyu else 'açık'} temada yüzeyler ayrışmıyor: {d}")


def test_koyu_tema_saf_siyah_DEGIL(tmp_path):
    """Brief: profesyonel havacılık yazılımı, oyun paneli değil."""
    html = _sayfa(tmp_path)
    assert _token(html, "--bg", koyu=True).lower() not in ("#000", "#000000")
    assert _isik(_token(html, "--bg", koyu=True)) > 0.001


def test_iki_koyu_tema_blogu_AYNI_token_listesini_tasiyor(tmp_path):
    """Koyu tema iki yerde tanımlı olmak zorunda (sistem tercihi + elle
    seçim). İkisi ayrışırsa kullanıcı temayı elle seçince renk değişir."""
    html = _sayfa(tmp_path)
    medya = html.split(':root:not([data-theme="light"]) {')[1].split("}")[0]
    elle = html.split(':root[data-theme="dark"] {')[1].split("}")[0]
    cikar = lambda t: dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8})", t))
    assert cikar(medya) == cikar(elle)


# ------------------------------------------------------ hareket azaltma
def test_hareket_azaltma_destekleniyor(tmp_path):
    """İşletim sisteminde hareket azaltmayı açan kullanıcı için geçişler
    durmalı - sayfa işlevini kaybetmeden."""
    html = _sayfa(tmp_path)
    assert "prefers-reduced-motion: reduce" in html
    blok = html.split("prefers-reduced-motion: reduce")[1].split("}\n  }")[0]
    assert "transition-duration" in blok and "animation-duration" in blok


# ------------------------------------ havacilik renk kodu AYRI kalmali
