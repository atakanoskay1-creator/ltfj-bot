"""Q kodu ve NOTAMR/NOTAMC bilgisi.

KULLANICI ISTEGI: LVO suzgeci anahtar kelime yerine Q koduna dayansin,
ve bir NOTAM'in baska bir NOTAM'in yerine gecip gecmedigi (NOTAMR) ya da
onu iptal edip etmedigi (NOTAMC) gorunsun.

SINIR - BILEREK: "yerine gectigi NOTAM'IN NUMARASI" NOTAC'in gozlenen
yanitinda AYRI BIR ALAN OLARAK YOK ve "text" yalnizca E) govdesini
tasiyor (16 gercek kayitta "NOTAMR B1234/26" kalibi hic gecmedi).
Numara ancak metinde GERCEKTEN yaziyorsa gosteriliyor; eslestirme
TAHMIN EDILMIYOR - ayni Q kodu + ayni pist gibi bir cikarim yanlis
NOTAM'i isaret edebilirdi."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

import ltfj_notam as notam
import ltfj_sayfa as s
from tests import notam_ornekler as o

METAR = {"tip": "METAR", "icao": "LTFJ", "zaman": datetime.now(timezone.utc),
         "metin": "LTFJ 241720Z 06010KT 9999 FEW030 12/08 Q1013"}


def _sayfa(tmp_path) -> str:
    hedef = tmp_path / "i.html"
    s.sayfa_yaz([METAR], [], hedef)
    return hedef.read_text(encoding="utf-8")


# ------------------------------------------------------------ Q kodu
def test_model_q_kodunu_TASIYOR():
    """Onceden NOTAC q_code veriyordu ama model onu atiyordu."""
    m = notam._notam_modeline_cevir(o.RUNWAY_KAPANIS)
    assert m["q_code"] == "QMRLC"


@pytest.mark.parametrize("kod,beklenen", [
    ("QMRLC", "MR"), ("qmrlc", "MR"), ("QILAS", "IL"),
    ("", None), ("QMR", None), ("QMRLCX", None), ("QMR1C", None), (None, None),
])
def test_q_konusu_ayristirma(kod, beklenen):
    """Bicim beklenmedikse None: yanlis bir dilimden konu uydurmaktansa
    "bilmiyorum" deyip anahtar kelime yedegine dusmek dogru."""
    assert notam.q_konusu({"q_code": kod}) is beklenen or notam.q_konusu({"q_code": kod}) == beklenen


def test_lvo_kararinda_BILMIYORUM_ile_HAYIR_ayri():
    """False = "baktim, ilgili degil"; None = "bakamadim". Ikisi
    karistirilirsa Q kodsuz kayitlar sessizce elenirdi."""
    assert notam.lvo_ile_ilgili_mi({"q_code": "QMRLC"}) is True
    assert notam.lvo_ile_ilgili_mi({"q_code": "QFAXX"}) is False
    assert notam.lvo_ile_ilgili_mi({}) is None
    assert notam.lvo_ile_ilgili_mi({"q_code": "bozuk"}) is None


def test_gercek_ornekler_LVO_ILGILI():
    for ornek in (o.RUNWAY_KAPANIS, o.RUNWAY_YUZEY_DUZENSIZLIGI):
        m = notam._notam_modeline_cevir(ornek)
        assert notam.lvo_ile_ilgili_mi(m) is True, m["q_code"]


def test_q_kodu_ARANABILIR():
    kayitlar = [notam._notam_modeline_cevir(o.RUNWAY_KAPANIS),
                notam._notam_modeline_cevir(o.MINIMAL_KAYIT)]
    assert len(notam.notam_ara(kayitlar, anahtar_kelime="QMR")) == 1


# ------------------------------------------- NOTAMR / NOTAMC referansi
def test_notam_tipi_MODELDE_var():
    assert notam._notam_modeline_cevir(o.RUNWAY_YUZEY_DUZENSIZLIGI)["notam_type"] == "R"
    assert notam._notam_modeline_cevir(o.RUNWAY_KAPANIS)["notam_type"] == "N"


@pytest.mark.parametrize("metin,beklenen", [
    ("B3455/26 NOTAMR B3210/26\nRWY CLSD", {"tip": "R", "numara": "B3210/26"}),
    ("A0001/26 NOTAMC A0000/26", {"tip": "C", "numara": "A0000/26"}),
    ("notamr b1234/26", {"tip": "R", "numara": "B1234/26"}),
    ("PRESENCE SURFACE IRREGULARITIES ON RWY 06L/24R", None),
    ("", None),
])
def test_ilgili_notam_referansi(metin, beklenen):
    assert notam.ilgili_notam_referansi({"text": metin}) == beklenen


def test_GERCEK_veride_referans_YOK_bu_beklenen():
    """Bu test bir SINIRI belgeliyor: NOTAC'in verdigi metinde bu kalip
    yok. Bir gun gelirse test kirilir ve biz de bunu ogreniriz."""
    for ornek in (o.RUNWAY_KAPANIS, o.RUNWAY_YUZEY_DUZENSIZLIGI):
        m = notam._notam_modeline_cevir(ornek)
        assert notam.ilgili_notam_referansi(m) is None


# ------------------------------------------------------- geriye donuk
def test_YENI_ALAN_mevcut_gecmis_kayitlarina_da_doluyor():
    """EN KRITIK GECIS TESTI. gecmisi_guncelle yalnizca
    record_updated_at degisince kaydi tazeliyordu; q_code gibi SONRADAN
    eklenen bir alan, NOTAC kaydi guncellemedigi surece mevcut 16
    kayda HIC gelmezdi - yani Q koduna dayali suzgec onlari hic
    gormezdi."""
    yeni = notam._notam_modeline_cevir(o.RUNWAY_KAPANIS)
    eski_kayit = {k: v for k, v in yeni.items() if k != "q_code"}
    eski_kayit.update(first_seen="2026-01-01T00:00:00+00:00",
                      last_seen="2026-01-01T00:00:00+00:00",
                      last_active="2026-01-01T00:00:00+00:00")
    gecmis = notam.gecmisi_guncelle({yeni["id"]: eski_kayit}, [yeni],
                                    "2026-09-25T10:00:00+00:00")
    kayit = gecmis[yeni["id"]]
    assert kayit["q_code"] == "QMRLC"
    # Gecmise ait alanlar KORUNMALI - tazeleme onlari ezmemeli.
    assert kayit["first_seen"] == "2026-01-01T00:00:00+00:00"


# ------------------------------------------------------------- sayfa
def test_sayfadaki_Q_KONU_listesi_PYTHON_ILE_AYNI(tmp_path):
    html_metin = _sayfa(tmp_path)
    m = re.search(r"var LVO_Q_KONULARI = (\[[^\]]*\]);", html_metin)
    assert m, "Q konu listesi sayfaya gömülmemiş"
    assert json.loads(m.group(1)) == list(notam.LVO_Q_KONULARI)


def test_suzgec_ONCE_Q_KODUNA_bakiyor_anahtar_kelime_YEDEK(tmp_path):
    html_metin = _sayfa(tmp_path)
    govde = html_metin.split("function notamLvoIliskiliMi")[1].split("}}")[0]
    # Q kodu once, erken donus ile
    assert "LVO_Q_KONULARI.indexOf(konu)" in govde
    assert "return true" in govde
    # ve anahtar kelime yolu DURUYOR (kaldirilmadi)
    assert "LVO_NOTAM_ANAHTAR_KELIMELER" in govde


def test_kartta_tip_ve_Q_kodu_rozetleri_var(tmp_path):
    html_metin = _sayfa(tmp_path)
    assert "ltfjNotamTipEtiketi" in html_metin
    assert "ltfjNotamQEtiketi" in html_metin
    assert "NOTAMR" in html_metin and "NOTAMC" in html_metin
    # "N" (yeni) icin rozet YOK - her kartta duran rozet gurultu olurdu.
    tipler = html_metin.split("var tipler = {{")[1].split("}};")[0] \
        if "var tipler = {{" in html_metin else html_metin.split("var tipler = {")[1].split("};")[0]
    assert '"N"' not in tipler


def test_sayfada_KONTROL_KARAKTERI_yok(tmp_path):
    """BU TEST BIR HATADAN DOGDU. SABLON ham (raw) bir dize DEGIL: JS
    regex'ine yazilan "\\b" Python tarafindan BACKSPACE (0x08)
    karakterine cevriliyor ve sayfaya oyle yaziliyordu - regex sessizce
    hicbir seyle eslesmiyordu. Hicbir cikti karakteri kontrol
    karakteri olmamali (sekme/satir sonu haric)."""
    html_metin = _sayfa(tmp_path)
    kotu = {c for c in html_metin if ord(c) < 32 and c not in "\t\n\r"}
    assert not kotu, [hex(ord(c)) for c in kotu]
