"""Pist diyagramı, gün/gece, bant göstergesi ve yüzey derinliği.

Ortak ilke: bunların hiçbiri SÜS değil. Üçü gerçek veriyi görselleştirir,
dördüncüsü (yüzey) anlam taşımaz ama anlam taşıyan renkleri de harcamaz.
"""
import math
import re
from datetime import datetime, timedelta, timezone

import pytest

import ltfj_pist as pist
import ltfj_sayfa as s

SIMDI = datetime.now(timezone.utc)


def _sayfa(tmp_path, metin="LTFJ 241720Z 06015KT 9999 FEW030 12/08 Q1008") -> str:
    hedef = tmp_path / "i.html"
    s.sayfa_yaz([{"tip": "METAR", "icao": "LTFJ", "zaman": SIMDI, "metin": metin}],
                [], hedef)
    return hedef.read_text(encoding="utf-8")


def _govde(html_metin: str) -> str:
    return re.sub(r"<!--.*?-->", "", html_metin.split("</style>")[1], flags=re.S)


# ================================================== 1) pist diyagramı
def test_diyagram_YENI_KARAR_CAGRISI_yapmiyor():
    """En önemlisi. Tercih edilen pist DIŞARIDAN geliyor -
    havacilik_notlari() onu zaten hesaplıyor ve Telegram da aynı değeri
    kullanıyor. Burada yeniden hesaplamak, aynı METAR için iki farklı
    cevap riski doğururdu.

    tests/test_ltfj_sayfa_lvo.py'deki koruma bunu zaten yakaladı; bu
    test niyeti AÇIKÇA yazıyor ki koruma bir gün gevşetilirse sebep
    kaybolmasın."""
    from pathlib import Path
    kaynak = Path(s.__file__).read_text(encoding="utf-8")
    assert "tercih_edilen_pist" not in kaynak


def test_diyagram_bilesenleri_PIST_MODULUNDEN(tmp_path):
    """Hesap kopyalanmadı: baş/yan bileşen ltfj_pist.bilesenler()'in
    kendisi.

    FİKSTÜR BİLEREK AÇILI: ilk sürüm 060/15 kt kullanıyordu ve pist
    ekseni 064 olduğu için baş rüzgârı 15·cos(4.1°) = 14.96 ≈ 15, yani
    hızın kendisine eşit çıkıyordu. "bileşen = hız" diyen sahte bir
    hesap da testi geçiyordu - mutasyonla ortaya çıktı. 120°'de baş ve
    yan bileşen hem birbirinden hem hızdan ayrışıyor."""
    html_metin = _govde(_sayfa(tmp_path, "LTFJ 241720Z 12015KT 9999 12/08 Q1008"))
    okumalar = re.findall(r'<span class="pd-etiket">(baş|kuyruk|yan)</span>'
                          r'<b>(\d+)</b>', html_metin)
    assert okumalar, "bileşen okuması yok"
    bulunan = {ad: int(v) for ad, v in okumalar}
    # \S+ acgozlu davranip "06L</div>" yakaliyordu - < disarida.
    tercih = re.search(r'class="pd-pist-ad">([^<]+)<', html_metin).group(1)
    bas, yan, _ = pist.bilesenler(120, 15, pist.PISTLER[tercih]["yon"])
    assert bulunan.get("baş", bulunan.get("kuyruk")) == round(abs(bas))
    assert bulunan["yan"] == round(yan)
    # Sahte "bilesen = hiz" hesabini AYIRT EDEBILIYOR olmali:
    assert round(abs(bas)) != 15 and round(yan) != 15


def test_ruzgar_yonu_yoksa_DIYAGRAM_HIC_cizilmiyor(tmp_path):
    """VRB'de yön bilinmiyor - ok çizmek uydurma olurdu.

    TEST BOŞA YEŞİLDİ (mutasyonla bulundu): ilk sürüm "diyagram varsa
    ok olmasın" diyordu, ama VRB'de tercih edilen pist zaten
    hesaplanamadığı için diyagram HİÇ çizilmiyor - yani koşul hiçbir
    zaman girilmiyordu ve içerideki guard'ı kaldırmak testi kırmıyordu.

    Artık GERÇEK davranış doğrulanıyor: yön yoksa diyagram yok.
    (Fonksiyonun içindeki `yon is not None` kontrolü savunma amaçlı
    duruyor - bu yoldan ulaşılmıyor ama pist_ruzgar_kaynagi'nın
    dönüşü değişirse ok uydurulmasın diye.)"""
    html_metin = _govde(_sayfa(tmp_path, "LTFJ 241720Z VRB03KT 9999 12/08 Q1008"))
    assert '<div class="pist-diyagram">' not in html_metin
    # Yon BILINIYORSA ok ciziliyor - yukaridaki iddia bos degil:
    varsa = _govde(_sayfa(tmp_path, "LTFJ 241720Z 06015KT 9999 12/08 Q1008"))
    assert 'class="pd-ok"' in varsa


def test_diyagram_ATC_ATAMASI_OLMADIGINI_soyluyor(tmp_path):
    """tercih_edilen_pist() kendi açıklamasında bunu vurguluyor;
    ekranda da yazmalı."""
    html_metin = _govde(_sayfa(tmp_path))
    assert "aktif pisti ATC belirler" in html_metin


@pytest.mark.parametrize("ruzgar,beklenen_uc", [
    ("06015KT", "06"), ("24015KT", "24"),
])
def test_tercih_edilen_UC_diyagramda_isaretli(ruzgar, beklenen_uc, tmp_path):
    html_metin = _govde(_sayfa(tmp_path, f"LTFJ 241720Z {ruzgar} 9999 12/08 Q1008"))
    m = re.search(r'class="pd-uc-ad pd-uc-tercih"[^>]*>(\d\d)</text>', html_metin)
    assert m and m.group(1) == beklenen_uc


def test_pist_numaralari_TERS_okunmuyor(tmp_path):
    """İki numara da soldan sağa okunmalı. Gerçek pistte birbirine göre
    terstirler ama 11 piksellik bir diyagramda okunurluk önce gelir."""
    html_metin = _govde(_sayfa(tmp_path))
    aci = [float(a) for a in re.findall(r'class="pd-uc-ad[^"]*"[^>]*'
                                        r'transform="rotate\(([-\d.]+)', html_metin)]
    assert len(aci) == 2, aci
    assert aci[0] == aci[1], "iki numara farkli aciyla donmus"
    assert -90 <= aci[0] <= 90, f"numara ters okunuyor: {aci[0]}"


# ================================================== 2) gün/gece
def test_gunes_saatleri_GOMULU_ve_GERCEK(tmp_path):
    """ltfj_pist._gunes_saatleri() LTFJ için gerçekten hesaplıyor -
    "akşam oldu" diye bir tahmin değil."""
    html_metin = _sayfa(tmp_path)
    dogus = re.search(r'data-gun-dogumu="([^"]*)"', html_metin).group(1)
    batim = re.search(r'data-gun-batimi="([^"]*)"', html_metin).group(1)
    d, b = datetime.fromisoformat(dogus), datetime.fromisoformat(batim)
    assert d < b
    # Ayni gun icinde ve makul bir gunduz uzunlugu.
    assert timedelta(hours=8) < (b - d) < timedelta(hours=16)


def test_gunes_hesabi_KOPYALANMADI():
    """İki ayrı güneş hesabı olsaydı sayfanın "gece" dediği an ile
    sis_riski()'nin "gece" dediği an ayrışabilirdi."""
    dogus, batim = s._gunes_iso(SIMDI)
    beklenen = pist._gunes_saatleri(SIMDI)
    assert beklenen is not None
    assert dogus == beklenen[0].isoformat()
    assert batim == beklenen[1].isoformat()


def test_gece_kararı_ISTEMCIDE_veriliyor(tmp_path):
    """Sunucuda gömülü bir "gündüz" etiketi, sayfa açık kalınca saat
    21:00'de yalan olurdu - tazelik rozetiyle aynı gerekçe."""
    html_metin = _sayfa(tmp_path)
    betik = html_metin.split("<script>")[1].split("</script>")[0]
    assert "data-gun-dogumu" in betik and "Date.now()" in betik
    assert 'setAttribute("data-faz"' in betik


def test_kullanicinin_TEMA_SECIMI_kazaniyor(tmp_path):
    """Gece otomatik koyu tema açılıyor ama kullanıcının açık tercihi
    (data-theme) varsa ona dokunulmamalı."""
    betik = _sayfa(tmp_path).split("<script>")[1].split("</script>")[0]
    assert '!k.getAttribute("data-theme")' in betik


# ================================================== 4) bant göstergesi
@pytest.mark.parametrize("gorus,kod", [
    (9999, "BLU"), (5000, "WHT"), (3700, "GRN"),
    (1600, "YLO"), (800, "AMB"), (300, "RED"),
])
def test_bant_kodu_PIST_TABLOSUNDAN(gorus, kod):
    assert s._olcu_bant_kodu({"gorus": gorus}, "gorus") == kod


def test_bant_esikleri_KOPYALANMADI():
    """Tablo değişirse bu test de değişir - kopya olmadığının kanıtı."""
    en_dusuk = pist.RENK_DURUMLARI[-1][2]
    assert s._olcu_bant_kodu({"gorus": en_dusuk}, "gorus") == pist.RENK_DURUMLARI[-1][0]
    assert s._olcu_bant_kodu({"gorus": en_dusuk - 1}, "gorus") == "RED"


def test_bant_RENK_TEK_TASIYICI_degil(tmp_path):
    """Konum (hangi kutu dolu) + kod metni, renkten bağımsız okunur."""
    html_metin = _govde(_sayfa(tmp_path, "LTFJ 241720Z 06015KT 0300 FG VV001 12/12 Q1008"))
    assert 'class="bant-kod">RED<' in html_metin
    assert html_metin.count('class="bant-kutu') >= 6
    assert 'aria-label="Görüş durum bandı: RED"' in html_metin


def test_deger_yoksa_BANT_da_yok(tmp_path):
    """Tavan bildirilmemişse bant çizmek uydurma olurdu."""
    html_metin = _govde(_sayfa(tmp_path, "LTFJ 241720Z 06015KT 9999 12/08 Q1008"))
    assert "Tavan durum bandı" not in html_metin


# ================================================== 5) yüzey derinliği
def test_golge_KOYU_TEMADA_yok(tmp_path):
    """Siyah üzerine gölge görünmez; parlaklık eklemek de gece
    kullanımını bozardı. Koyu temada derinlik yüzey basamaklarından
    (--bg < --panel < --kart) geliyor."""
    html_metin = _sayfa(tmp_path)
    assert html_metin.count("--golge:none") == 2, "iki koyu tema blogunda da olmali"
    kart = html_metin.split("\n  .kart {")[1].split("}")[0]
    assert "box-shadow:var(--golge)" in kart


def test_kart_ZEMINDEN_ayrisiyor(tmp_path):
    """Kart beyaz, sayfa zemini tonlu - aksi halde kart sınırı yalnızca
    1px kenarlıkla taşınıyordu."""
    html_metin = _sayfa(tmp_path)
    kok = html_metin.split(":root {")[1].split("}")[0]
    bg = re.search(r"--bg:(#[0-9a-f]{6})", kok).group(1)
    kart = re.search(r"--kart:(#[0-9a-f]{6})", kok).group(1)
    assert bg != kart
    assert kart.lower() == "#ffffff"
