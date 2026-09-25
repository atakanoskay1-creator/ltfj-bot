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
from datetime import datetime, timedelta, timezone
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


# ================================================ NOTAMR referansı (düzeltme)
# KULLANICI DÜZELTMESİ: "bu numara NOTAC'ta yok" sonucuna varmıştım ve bu
# YANLIŞTI. Doğrulayabildiğim tek şey BİZİM SAKLADIĞIMIZ "text" alanıydı;
# NOTAC'ın kendi arayüzü tam orijinal metni gösteriyor:
#
#     B3455/26 NOTAMR B2849/26
#      Q) LTBB/QMRXX/IV/BO /A /000/999/4054N02919E005
#      A) LTFJ B) 2608280711 C) 2610021600
#      E) PRESENCE SURFACE IRREGULARITIES ON RWY 06L/24R ...
#
# Numaranın hangi alanda geldiği henüz ölçülmedi (bkz. notam_kesif.py),
# o yüzden alan adı SABİTLENMİYOR: tüm metin alanlarında aranıyor.
TAM_ORIJINAL_METIN = (
    "B3455/26 NOTAMR B2849/26\n"
    " Q) LTBB/QMRXX/IV/BO /A /000/999/4054N02919E005\n"
    " A) LTFJ B) 2608280711 C) 2610021600\n"
    " E) PRESENCE SURFACE IRREGULARITIES ON RWY 06L/24R REDUCING DRIVING\n"
    " QUALITY."
)


def test_NOTAC_ekranindaki_tam_metinden_referans_cikiyor():
    """Kullanıcının paylaştığı gerçek metin birebir."""
    assert notam.ilgili_notam_referansi({"text": TAM_ORIJINAL_METIN}) == {
        "tip": "R", "numara": "B2849/26"}


def test_referans_ALAN_ADINA_bagli_degil():
    """EN ÖNEMLİSİ. Tam metin hangi alanda gelirse gelsin bulunmalı -
    alan adını uydurmak yerine hepsine bakıyoruz."""
    for alan in ("original_text", "raw_text", "full_text", "icao_text", "bilinmeyen_alan"):
        kayit = {"text": "E) SADECE GOVDE", alan: TAM_ORIJINAL_METIN}
        assert notam.ilgili_notam_referansi(kayit) == {"tip": "R", "numara": "B2849/26"}, alan


def test_referans_NOTAMIN_KENDI_numarasini_vermiyor():
    """Metin "B3455/26 NOTAMR B2849/26" ile başlıyor; yakalanması
    gereken İKİNCİ numara."""
    s = notam.ilgili_notam_referansi({"text": TAM_ORIJINAL_METIN})
    assert s["numara"] == "B2849/26" and s["numara"] != "B3455/26"


def test_model_ilgili_notam_alanini_tasiyor():
    ham = {**o.RUNWAY_YUZEY_DUZENSIZLIGI, "original_text": TAM_ORIJINAL_METIN}
    m = notam._notam_modeline_cevir(ham)
    assert m["ilgili_notam"] == {"tip": "R", "numara": "B2849/26"}
    # Referans yoksa alan VAR ama None - sayfa "yok" ile "bilinmiyor"u
    # ayirmak zorunda degil, ikisi de satiri cizdirmiyor.
    assert notam._notam_modeline_cevir(o.RUNWAY_KAPANIS)["ilgili_notam"] is None


def test_sayfa_KENDI_regexini_calistirmiyor(tmp_path):
    """Aynı kural iki dilde iki kez yazılmış olurdu ve JS tarafı hangi
    alanda arandığını da sabitlerdi."""
    html_metin = _sayfa(tmp_path)
    blok = html_metin.split("ltfjNotamIlgiliSatiri = function")[1].split("}};")[0]
    assert "NOTAM([RC])" not in blok, "regex kopyası JS'e geri gelmiş"
    assert "n.ilgili_notam" in blok


# ==================================================== yaklaşan NOTAM'lar
def _gecmis_kaydi(numara, bas, bit, son_senkron):
    return {"id": numara, "number": numara, "status": "active",
            "effective_start": bas, "effective_end": bit,
            "last_seen": son_senkron, "last_active": son_senkron,
            "first_seen": son_senkron, "text": "X", "notam_type": "N"}


def test_yururluge_girmemis_NOTAM_ayri_listeye_giriyor(tmp_path):
    """Aktif listeye koymak, olmayan bir kısıtlamayı varmış gibi
    göstermek olurdu; hiç göstermemek "yarın pist kapanıyor" bilgisini
    kaybettirirdi."""
    simdi = datetime.now(timezone.utc)
    ss = simdi.isoformat(timespec="seconds")
    state = {"notam_son_senkron": ss, "notam_gecmisi": {
        "su-an": _gecmis_kaydi("B0001/26", (simdi - timedelta(days=1)).isoformat(),
                               (simdi + timedelta(days=1)).isoformat(), ss),
        "yarin": _gecmis_kaydi("B0002/26", (simdi + timedelta(days=1)).isoformat(),
                               (simdi + timedelta(days=3)).isoformat(), ss),
    }}
    hedef = tmp_path / "notam_veri.json"
    notam.notam_veri_yaz(state, hedef)
    veri = json.loads(hedef.read_text(encoding="utf-8"))
    assert [k["number"] for k in veri["yaklasan"]] == ["B0002/26"]
    # Yururlukteki kayit yaklasan listesine SIZMAMALI.
    assert "B0001/26" not in [k["number"] for k in veri["yaklasan"]]
    # Kayit "aktif" listesinde de durabilir (NOTAC'in dondurdugu ham
    # liste budur); sayfa onu gecerlilik kontrolüyle "baslamadi" diye
    # aktif listeden eliyor (bkz. yururluktekiler). Buradaki iddia
    # AYRI LISTENIN dogru doldugu.


def test_yaklasan_bolumu_VARSAYILAN_GIZLI_ve_istemcide_suzuluyor(tmp_path):
    """Sürekli duran boş bir başlık, "yaklaşan yok" ile "veri gelmiyor"
    arasındaki farkı silerdi. Ayrıca sayfa saatlerce açık kalabilir ve
    bu arada bir NOTAM yürürlüğe girer - liste istemcide yeniden
    süzülmeli."""
    html_metin = _sayfa(tmp_path)
    assert 'id="notam-yaklasan-bolum" hidden' in html_metin
    blok = html_metin.split("function yaklasanGoster()")[1].split("function aktifGoster")[0]
    assert 'gecerlilik(n).durum === "baslamadi"' in blok
    assert "yaklasanBolumEl.hidden = liste.length === 0" in blok
