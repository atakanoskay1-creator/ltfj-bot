"""Sayfanin en ustundeki YAPISKAN tek satir ozet seridi.

Amac: "su an bir sikinti var mi?" sorusu sifir kaydirmayla
yanitlanabilsin. Kartlar katlandiktan sonra sayfa kisaldi ama
kaydirinca guncel METAR karti yine ekrandan cikiyordu.

Sozlesme: serit HAM METAR degerlerini gosterir - yorum/tahmin YOK.
Eksik alan "—" olur; satir hic cizilmemektense eksik cizilir, cunku
yoklugun kendisi de bilgidir (or. tavan bildirilmiyor)."""
from datetime import datetime, timezone

import ltfj_sayfa as s

SIMDI = datetime.now(timezone.utc)


def _rapor(metin, tip="METAR"):
    return {"tip": tip, "metin": metin, "zaman": SIMDI, "icao": "LTFJ"}


def _sayfa(tmp_path, raporlar) -> str:
    hedef = tmp_path / "index.html"
    s.sayfa_yaz(raporlar, [], hedef)
    return hedef.read_text(encoding="utf-8")


METAR = "LTFJ 172120Z 06004KT 3000 BR SCT008 18/16 Q1015"


# ------------------------------------------------------------- icerik
def test_ham_metar_degerleri_seritte():
    html = s._ozet_serit_html(
        {"gorus": 3000, "tavan": 800, "ruzgar_yon": 60, "ruzgar_hiz": 4,
         "ruzgar_hamle": None, "sicaklik": 18, "cig_noktasi": 16}, None)
    assert "3 km" in html
    assert "800 ft" in html
    assert "060°/4" in html
    assert "Δ2°" in html


def test_hamle_varsa_G_ile_yaziliyor():
    html = s._ozet_serit_html({"ruzgar_yon": 60, "ruzgar_hiz": 18,
                               "ruzgar_hamle": 28}, None)
    assert "060°/18G28" in html


def test_degisken_ruzgar_VRB_yaziliyor():
    html = s._ozet_serit_html({"ruzgar_yon": None, "ruzgar_hiz": 3,
                               "ruzgar_hamle": None}, None)
    assert "VRB/3" in html


def test_gorus_10km_ustu_kisaltiliyor():
    """Tahmin seridiyle AYNI kisaltma - iki yerde iki farkli bicim
    okuyucuyu 9999 ile 10+ km ayni sey mi diye dusundurmesin."""
    assert "10+ km" in s._ozet_serit_html({"gorus": 9999}, None)
    assert "600 m" in s._ozet_serit_html({"gorus": 600}, None)


def test_tavan_bildirilmiyorsa_bos_birakilmiyor():
    """"tavan yok" ile "veri gelmedi" ayni sey degil ama ikisi de
    kaydirmadan gorunmeli - bos hucre birakmak sessizce yaniltir."""
    assert "tavan yok" in s._ozet_serit_html({"gorus": 9999, "tavan": None}, None)


def test_eksik_alanlar_cokmeden_tire_oluyor():
    """Kismi cozum (or. ruzgar okunmus, gerisi yok) - eksik alanlar
    "—" olur, satir yine cizilir."""
    html = s._ozet_serit_html({"ruzgar_yon": 60, "ruzgar_hiz": 4}, None)
    assert html.count("—") == 2      # gorus + spread
    assert 'class="ozet-serit"' in html


def test_tamamen_bos_cozumde_serit_cizilmiyor():
    """Dort tireden ibaret bir satir bilgi degil gurultudur - ham
    METAR'dan hicbir alan okunamadiysa serit hic cikmasin."""
    assert s._ozet_serit_html({}, None) == ""


def test_cozum_yoksa_serit_hic_basilmiyor(tmp_path):
    """METAR/SPECI yoksa (yalniz TAF) uydurulacak bir "su an" yok."""
    assert s._ozet_serit_html(None, None) == ""
    html = _sayfa(tmp_path, [_rapor("LTFJ 172000Z 1721/1824 06005KT", "TAF")])
    assert 'class="ozet-serit"' not in html


# --------------------------------------------------------------- rozet
def test_renk_rozeti_kart_rozetiyle_ayni_hesaptan_geliyor(tmp_path):
    """REGRESYON riski: rozet burada YENIDEN hesaplansaydi (esikler
    kopyalanarak) ust serit ile kart sessizce farklilasabilirdi."""
    import ltfj_pist
    from ltfj_analiz import metar_coz
    cozum = metar_coz("METAR " + METAR)
    notlar = ltfj_pist.havacilik_notlari(cozum, METAR, SIMDI)
    kod = notlar["renk"][0]

    html = _sayfa(tmp_path, [_rapor(METAR)])
    serit = html.split('class="ozet-serit"')[1].split("</div>")[0]
    assert f">{kod}<" in serit
    assert s.RENK_KODU[kod] in serit


def test_renk_yoksa_rozet_cizilmiyor():
    assert "ozet-renk" not in s._ozet_serit_html({"gorus": 9999}, None)
    assert "ozet-renk" not in s._ozet_serit_html({"gorus": 9999}, {"renk": None})


# -------------------------------------------------------------- yerlesim
def test_serit_header_ile_govde_ARASINDA(tmp_path):
    """Serit kartlarin USTUNDE olmali - altinda kalirsa ilk ekranda
    gorunmez ve tum amaci kaybolur."""
    html = _sayfa(tmp_path, [_rapor(METAR)])
    assert html.index("</header>") < html.index('id="ozet-serit"')
    assert html.index('id="ozet-serit"') < html.index('class="basrow"')


def test_yapiskan_ve_opak(tmp_path):
    """position:sticky + OPAK arka plan - saydam olsaydi altindan
    kayan yazi seridin uzerine binerdi."""
    html = _sayfa(tmp_path, [_rapor(METAR)])
    css = html.split(".ozet-serit {")[1].split("}")[0]
    assert "position:sticky" in css
    assert "top:0" in css
    assert "background:var(--kart)" in css


def test_sabit_katmanlarin_ALTINDA_kaliyor(tmp_path):
    """VFR sekmesi (58) ve ATC modali (65) sabit; serit onlarin ustune
    cikarsa modal acikken uzerinde bir cubuk asili kalir."""
    html = _sayfa(tmp_path, [_rapor(METAR)])
    css = html.split(".ozet-serit {")[1].split("}")[0]
    z = int(css.split("z-index:")[1].split(";")[0])
    assert 1 < z < 55
