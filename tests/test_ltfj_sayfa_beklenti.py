"""Beklenti sekmesi: tahmin tablosu HİZALI olmalı.

NEDEN VAR — TARAYICIDA ÖLÇÜLMÜŞ BİR KUSUR:

Tahmin şeridi eskiden her saat için bağımsız bir <div> kolonu
çiziyordu ve iki satır KOŞULLUYDU — sis işareti (weather_code) ve
sınır tabakası yüksekliği (Open-Meteo'nun bazen hiç döndürmediği
deneysel bir alan). Chromium'da ölçülen sonuç:

    hucre 0: 23:00@413 | 2.0°@437 | 10+ km@468 | 11 km/s@486 | ...
    hucre 1: 00:00@413 | 2.0°@437 | sis@468   | 0.3 km@489  | ...
    hucre 2: 01:00@413 | 2.0°@437 | 10+ km@468 | 11 km/s@486   (BLH YOK)

Yani sisli saatin GÖRÜŞÜ (0.3 km, y=489), komşularının RÜZGÂR
satırının hizasındaydı (y=486). "Görüş" satırını yatay tararken sisli
saatte rüzgâr okunuyordu. BLH'si olmayan kolon ise en alt satırı hiç
çizmiyordu. Bir meteoroloji şeridinde bu yanlış okutur.

Bu testler TARAYICI İSTEMEZ, çünkü kusurun kökü piksel değil YAPI:
kolonların hücre sayısı eşit değildi. Tablo bunu yapısal olarak çözer
ve aşağıdaki değişmez onu sabitler: HER SATIRDA BAŞLIKLA AYNI SAYIDA
HÜCRE VAR.
"""
import re
from datetime import datetime, timedelta, timezone

import pytest

import ltfj_sayfa as s

ILK = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(
    minute=0, second=0, microsecond=0)


def saat(i, **ek):
    """Tam dolu bir tahmin saati; ek= ile alan silinip değiştirilebilir."""
    satir = {"saat": (ILK + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M"),
             "temperature_2m": 10.0, "dew_point_2m": 8.0, "visibility": 12000,
             "wind_speed_10m": 11.0, "cloud_cover_low": 30,
             "boundary_layer_height": 400}
    satir.update(ek)
    return {a: d for a, d in satir.items() if d is not ...}


def _satirlar(html_metin):
    """(başlık_hücreleri, [(satır_başlığı, [hücreler]), ...])"""
    tablo = re.search(r'<table class="tahmin-tablo">(.*?)</table>',
                      html_metin, re.S)
    assert tablo, "tahmin tablosu üretilmemiş"
    icerik = tablo.group(1)
    bas = re.findall(r'<th scope="col"[^>]*>(.*?)</th>',
                     icerik.split("</thead>")[0], re.S)
    govde = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", icerik.split("<tbody>")[1], re.S):
        etiket = re.search(r'<th scope="row"[^>]*>(.*?)</th>', tr, re.S)
        govde.append((etiket.group(1) if etiket else None,
                      re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)))
    return bas, govde


# ---------------------------------------------- ASIL DEĞİŞMEZ
@pytest.mark.parametrize("ad,tahmin", [
    ("hepsi tam", [saat(0), saat(1), saat(2)]),
    # Kusurun iki tetikleyicisi, tek tek ve birlikte:
    ("sisli saat var", [saat(0), saat(1, weather_code=45, visibility=300),
                        saat(2)]),
    ("bir saatte BLH yok", [saat(0), saat(1, boundary_layer_height=...),
                            saat(2)]),
    ("hem sis hem eksik BLH",
     [saat(0, boundary_layer_height=...),
      saat(1, weather_code=48, visibility=200), saat(2)]),
    ("ortadaki saatte görüş yok", [saat(0), saat(1, visibility=...), saat(2)]),
    ("tek saat", [saat(0, weather_code=45)]),
])
def test_HER_satirda_baslikla_AYNI_sayida_hucre(ad, tahmin):
    """Hizanın TEK koşulu bu. Bir satır eksik hücreyle çizilirse o
    sütundan sonraki her değer bir üst satıra kayar."""
    bas, govde = _satirlar(s._saatlik_tahmin_html(tahmin))
    assert len(bas) == len(tahmin), f"{ad}: saat başlığı sayısı tutmuyor"
    for etiket, hucreler in govde:
        assert len(hucreler) == len(bas), (
            f"{ad}: '{etiket}' satırında {len(hucreler)} hücre var, "
            f"{len(bas)} olmalı")


def test_sis_isareti_fazladan_SATIR_acmiyor():
    """Kusurun birinci tetikleyicisi: sis işareti eskiden hücrenin
    İÇİNE yeni bir satır olarak giriyordu ve altındaki her şeyi
    aşağı itiyordu. Artık SAAT BAŞLIĞINDA duruyor - tablo başlığı
    tüm kolonlar için ortak yükselir, hiza bozulmaz."""
    sissiz = s._saatlik_tahmin_html([saat(0), saat(1)])
    sisli = s._saatlik_tahmin_html([saat(0), saat(1, weather_code=45)])
    assert '<div class="tahmin-sis"' in sisli, "sis işareti çizilmemiş"
    assert '<div class="tahmin-sis"' not in sissiz
    # Gövde satır sayısı DEĞİŞMİYOR:
    assert len(_satirlar(sissiz)[1]) == len(_satirlar(sisli)[1])
    # ve işaret <thead>'in içinde:
    thead = sisli.split("</thead>")[0]
    assert '<div class="tahmin-sis"' in thead, "sis işareti gövdeye düşmüş"


def test_eksik_deger_SATIRI_gizlemiyor_tire_yaziyor():
    """Kusurun ikinci tetikleyicisi: BLH'si olmayan kolon en alt
    satırı hiç çizmiyordu. Artık '—' yazıyor - eksiklik de bilgidir."""
    _, govde = _satirlar(s._saatlik_tahmin_html(
        [saat(0), saat(1, boundary_layer_height=...), saat(2)]))
    satir = next(h for e, h in govde if "sınır tabakası" in e)
    assert satir[1].strip() in ("—", "&mdash;"), satir
    assert satir[0].strip() == "400" and satir[2].strip() == "400"


def test_alan_HIC_yoksa_satir_bosuna_cizilmiyor():
    """'Bu alan hiç gelmiyor' ile 'bu saatte yok' ayrı şeyler.
    Open-Meteo deneysel alanları reddederse (bkz.
    ltfj_dis_kaynak_cache.HOURLY_DENEYSEL) baştan sona '—' dolu bir
    satır çizmek gürültüden ibaret olurdu."""
    _, govde = _satirlar(s._saatlik_tahmin_html(
        [saat(i, boundary_layer_height=...) for i in range(3)]))
    assert not any("sınır tabakası" in e for e, _ in govde)
    # ama diğer satırlar duruyor ve hizalı:
    assert any("spread" in e for e, _ in govde)


# ---------------------------------------------- etiket ve birim
def test_her_satir_ADIYLA_yaziliyor():
    """Eskiden hangi sayının ne olduğu YALNIZCA tablonun altındaki düz
    metinde yazıyordu ("Satırlar: saat · spread · görüş · ..."). Ekran
    okuyucu için de, göz için de sayı adsızdı."""
    _, govde = _satirlar(s._saatlik_tahmin_html([saat(0)]))
    etiketler = [re.sub(r"<[^>]+>", " ", e) for e, _ in govde]
    for beklenen in ("spread", "görüş", "rüzgâr", "alçak bulut",
                     "sınır tabakası"):
        assert any(beklenen in e for e in etiketler), beklenen


def test_birim_satir_basliginda_hucrede_DEGIL():
    """Aynı birim 12 hücrede tekrar edince tablo 360px'te taşıyordu."""
    html_metin = s._saatlik_tahmin_html([saat(0), saat(1)])
    _, govde = _satirlar(html_metin)
    for etiket, hucreler in govde:
        assert '<span class="tahmin-birim">' in etiket, etiket
        for h in hucreler:
            assert not re.search(r"[a-zA-Z°%]", h.replace("mdash", "")), h


def test_ruzgar_KNOT_cunku_sayfanin_geri_kalani_knot():
    """Open-Meteo'ya wind_speed_unit GÖNDERİLMİYOR, yani km/SAAT
    dönüyor. Sayfa 'km/s' yazıyordu: hem Türkçe'de kilometre/saniye
    okunur, hem de METAR/özet şerit/hero KNOT. Yan yana duran iki
    rüzgâr sayısından biri km/h öteki kt olursa ~2 kat yanlış okunur."""
    html_metin = s._saatlik_tahmin_html([saat(0, wind_speed_10m=18.52)])
    _, govde = _satirlar(html_metin)
    etiket, satir = next((e, h) for e, h in govde if "rüzgâr" in e)
    assert satir[0].strip() == "10", satir      # 18.52 km/sa = 10.0 kt
    # BIRIMIN KENDISINE bakiyoruz, belgenin tamamina degil: satir
    # basliginin tooltip'i "Open-Meteo'nun km/sa degerinden cevrildi"
    # diyor ve bu testin ilk surumu tam da ona takiliyordu - yani
    # "km/s" gecmesin demek yetmiyor, NEREDE gectigi onemli.
    birim = re.search(r'<span class="tahmin-birim">(.*?)</span>',
                      etiket).group(1)
    # Sadece RUZGAR satirinin birimi: "km" tek basina gecerli bir birim,
    # gorus satiri onu kullaniyor - bu yuzden tum belgede "km yok" demek
    # yanlis olurdu (testin ikinci surumu de tam oraya takildi).
    assert birim == "kt", birim


def test_tahmin_yoksa_tablo_da_yok():
    assert s._saatlik_tahmin_html([]) == ""


# ---------------------------------------------- çift başlık
def _sayfa(tmp_path, **ek) -> str:
    hedef = tmp_path / "i.html"
    s.sayfa_yaz([{"tip": "METAR", "icao": "LTFJ",
                  "zaman": datetime.now(timezone.utc),
                  "metin": "LTFJ 231850Z 04003KT 9999 FEW030 12/10 Q1020 NOSIG"}],
                [], hedef, **ek)
    return hedef.read_text(encoding="utf-8")


def _panel(html_metin, ad):
    bas = html_metin.index(f'id="panel-{ad}"')
    son = html_metin.index('<div class="sekme-panel"', bas) \
        if '<div class="sekme-panel"' in html_metin[bas:] else len(html_metin)
    return html_metin[bas:son]


@pytest.mark.parametrize("ad,etiket", [
    ("beklenti", "Beklenti"), ("istatistik", "İstatistik"), ("notam", "NOTAM"),
])
def test_panel_kendi_SEKME_ADINI_baslik_olarak_TEKRARLAMIYOR(ad, etiket, tmp_path):
    """Sekme düğmesi paneli zaten adlandırıyor. Panel bir de kart
    başlığı olarak aynı adı yazınca ("Beklenti · önümüzdeki saatler"
    ve hemen altında "Önümüzdeki saatler · Open-Meteo") aynı şey üst
    üste üç kez görünüyordu."""
    tahmin = [saat(i) for i in range(3)]
    govde = _panel(_sayfa(tmp_path, saatlik_tahmin=tahmin, tahmin_yas_dk=10), ad)
    basliklar = re.findall(r'<span class="tip">(.*?)</span>', govde, re.S)
    assert etiket not in [b.strip() for b in basliklar], (
        f"{ad} paneli sekme adını başlık olarak tekrarlıyor: {basliklar}")


def test_NOTAM_senkron_zamani_TASINIRKEN_kaybolmadi(tmp_path):
    """Dış başlık kaldırılırken içindeki tek gerçek bilgi (senkron
    zamanı) asıl bölüm başlığına taşındı. id AYNI kalmalı, yoksa onu
    dolduran JS sessizce hiçbir şeye yazar."""
    html_metin = _sayfa(tmp_path)
    assert html_metin.count('id="notam-senkron-zamani"') == 1
    # ETIKETI degil MARKUP'i ariyoruz: bu testin ilk surumu duz metin
    # olarak "Aktif NOTAM'lar" aradi ve KENDI ACIKLAMA YORUMUMA takildi
    # (yorum da o ifadeyi aniyor). Bu tuzaga bu projede birkac kez
    # dusuldu - artik kural: yorumlarda gecebilecek bir dizgeyi
    # capa olarak kullanma.
    capa = '<span class="tip">Aktif NOTAM&#x27;lar</span>'
    if capa not in html_metin:
        capa = "<span class=\"tip\">Aktif NOTAM'lar</span>"
    assert capa in html_metin, "aktif NOTAM baslik markup'i bulunamadi"
    yakin = html_metin[html_metin.index(capa):][:220]
    assert 'id="notam-senkron-zamani"' in yakin, yakin


# ---------------------------------------------- yatay kaydırma
def _kural(css: str, secici: str) -> str:
    return css.split(secici + " {")[1].split("}")[0]


def test_yatay_kaydirmada_ETIKET_SUTUNU_yerinde_kaliyor(tmp_path):
    """10 saatlik şerit telefonda (320px) yatay kayar. Satır başlığı
    kaymazsa "bu sayı neydi" bilgisi ekrandan çıkar ve tablo
    okunamaz hale gelir."""
    css = _sayfa(tmp_path)
    kural = _kural(css, '.tahmin-tablo th[scope="row"]')
    assert "position:sticky" in kural and "left:0" in kural
    # Zemin ŞART: saydam olsaydı altından kayan sayılar görünürdü.
    assert "background:var(--kart)" in kural


def test_BASLIK_SATIRININ_kosesi_de_yapiskan(tmp_path):
    """TARAYICIDA GÖRÜLDÜ: satır başlıkları yapışkanken başlık
    satırının sol köşesi değildi. 390px'te 297px kaydırıldığında sol
    üst köşede kayan "02:00"in kuyruğu ("00") görünüyordu - etiket
    sütununun hizasında, saat başlığı gibi okunacak şekilde.

    Köşenin z-index'i satır başlıklarından BÜYÜK olmalı: hem yatay
    hem dikey komşularını örtmesi gerekiyor."""
    css = _sayfa(tmp_path)
    kose = _kural(css, ".tahmin-tablo thead th:first-child")
    assert "position:sticky" in kose and "left:0" in kose
    assert "background:var(--kart)" in kose
    z_kose = int(re.search(r"z-index:(\d+)", kose).group(1))
    z_satir = int(re.search(
        r"z-index:(\d+)", _kural(css, '.tahmin-tablo th[scope="row"]')).group(1))
    assert z_kose > z_satir, (z_kose, z_satir)
