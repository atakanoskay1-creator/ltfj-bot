"""ltfj_notam.py testleri: model esleme, LTFJ filtresi, sayfalama, arama,
yerel gecmis birlestirme.

Test verileri notam_ornekler.py'de - kullanicinin GERCEK NOTAC yanitindan
(2026-09-16, GitHub Actions test istegi) alinan alan adlari ve yapisiyla
birebir uyumlu."""
from unittest.mock import patch

import pytest

import notam_ornekler as no

import ltfj_notam as nm
import ltfj_notam_client as client


# ------------------------------------------------------------- model esleme
def test_notam_modeline_cevir_temel_alanlar():
    model = nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI)
    assert model["id"] == "190a947d-aebc-414b-9ea6-f06bb1fbf7a1"
    assert model["number"] == "B3455/26"
    assert model["notam_type"] == "R"
    assert model["location"] == "LTFJ"
    assert model["status"] == "active"
    assert model["effective_start"] == "2026-08-28T07:11:00Z"
    assert model["effective_end"] == "2026-10-02T16:00:00Z"
    assert model["source"] == "NOTAC"


def test_notam_modeline_cevir_kategori_ve_tag_notac_kaynakli():
    """Kendi regex'imizle kategori tahmin ETMIYORUZ - NOTAC'in verdigi
    category/tags dogrudan gecmeli."""
    model = nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI)
    assert model["category_kodu"] == "RUNWAY"
    assert model["category_etiketi"] == "Runway"
    assert set(model["tags"]) == {"maintenance", "movement-area", "runway"}


def test_notam_modeline_cevir_affected_elements_korunur():
    model = nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI)
    assert model["affected_elements"] == [{"ref": "06L/24R", "type": "RWY"}]


def test_notam_modeline_cevir_raw_metin_korunur():
    model = nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI)
    assert "SURFACE IRREGULARITIES" in model["text"]
    assert "RWY 06L/24R" in model["text"]


def test_notam_modeline_cevir_reading_notac_kaynakli_ayri_tutulur():
    model = nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI)
    assert model["reading_short"] == "Runway 06L/24R has surface irregularities."
    assert "reduce driving quality" in model["reading_long"]


def test_notam_modeline_cevir_eksik_opsiyonel_alanlar_crash_etmez():
    """category/tags/readings/affected_elements/location HEPSI eksik olan
    minimal bir kayit crash etmemeli, guvenli varsayilanlara dusmeli."""
    model = nm._notam_modeline_cevir(no.MINIMAL_KAYIT)
    assert model["id"] == "minimal-id-0001"
    assert model["category_kodu"] is None
    assert model["category_etiketi"] is None
    assert model["tags"] == []
    assert model["affected_elements"] == []
    assert model["reading_short"] is None
    assert model["reading_long"] is None
    assert model["location"] == "LTFJ"  # location_code alaninda var


# --------------------------------------------------------- aktif notam getir
def test_aktif_notamlari_getir_ltfj_filtresi_uygulanir(monkeypatch):
    monkeypatch.setenv("NOTAC_API_KEY", "lb_" + "a" * 40)
    karisik_yanit = {
        "count": 2, "next": None, "previous": None,
        "results": [no.RUNWAY_YUZEY_DUZENSIZLIGI, no.BASKA_LOKASYON],
    }
    with patch("ltfj_notam_client.notam_getir", return_value=karisik_yanit):
        kayitlar = nm.aktif_notamlari_getir("LTFJ")
    assert len(kayitlar) == 1
    assert kayitlar[0]["location"] == "LTFJ"


def test_aktif_notamlari_getir_sayfalama_takip_edilir(monkeypatch):
    """DRF 'next' URL'si varsa ikinci sayfa da cekilmeli."""
    monkeypatch.setenv("NOTAC_API_KEY", "lb_" + "a" * 40)
    sayfa1 = {
        "count": 2, "next": "https://notac.aero/api/v1/notam/?location=LTFJ&page=2",
        "previous": None, "results": [no.RUNWAY_YUZEY_DUZENSIZLIGI],
    }
    sayfa2 = {"count": 2, "next": None, "previous": "...", "results": [no.RUNWAY_KAPANIS]}
    with patch("ltfj_notam_client.notam_getir", return_value=sayfa1), \
            patch("ltfj_notam_client.sayfa_getir", return_value=sayfa2) as mock_sayfa:
        kayitlar = nm.aktif_notamlari_getir("LTFJ")
    assert len(kayitlar) == 2
    assert {k["number"] for k in kayitlar} == {"B3455/26", "B7835/25"}
    mock_sayfa.assert_called_once_with(sayfa1["next"])


def test_aktif_notamlari_getir_id_yoksa_atlar(monkeypatch):
    monkeypatch.setenv("NOTAC_API_KEY", "lb_" + "a" * 40)
    yanit = {"count": 1, "next": None, "previous": None, "results": [no.GECERSIZ_KAYIT_ID_YOK]}
    with patch("ltfj_notam_client.notam_getir", return_value=yanit):
        kayitlar = nm.aktif_notamlari_getir("LTFJ")
    # id olmasa da modele cevrilir (id=None) - eleme aktif_notamlari_getir'in
    # isi degil, gecmisi_guncelle() id'siz kayitlari atlar (ayrica test edilir).
    assert kayitlar[0]["id"] is None


def test_aktif_notamlari_getir_ag_hatasi_servis_hatasina_sarilir(monkeypatch):
    monkeypatch.setenv("NOTAC_API_KEY", "lb_" + "a" * 40)
    with patch("ltfj_notam_client.notam_getir", side_effect=client.NotamAgHatasi("koptu")):
        with __import__("pytest").raises(nm.NotamServisHatasi):
            nm.aktif_notamlari_getir("LTFJ")


# ------------------------------------------------------------------- arama
def test_notam_ara_anahtar_kelime_numaraya_gore():
    kayitlar = [nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI),
                nm._notam_modeline_cevir(no.RUNWAY_KAPANIS)]
    sonuc = nm.notam_ara(kayitlar, anahtar_kelime="B3455")
    assert len(sonuc) == 1
    assert sonuc[0]["number"] == "B3455/26"


def test_notam_ara_anahtar_kelime_pist_referansina_gore():
    kayitlar = [nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI)]
    assert nm.notam_ara(kayitlar, anahtar_kelime="24R") == kayitlar
    assert nm.notam_ara(kayitlar, anahtar_kelime="06L/24R") == kayitlar


def test_notam_ara_anahtar_kelime_metin_icinde():
    kayitlar = [nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI)]
    assert nm.notam_ara(kayitlar, anahtar_kelime="surface irregularities") == kayitlar
    assert nm.notam_ara(kayitlar, anahtar_kelime="TAMAMEN ALAKASIZ") == []


def test_notam_ara_buyuk_kucuk_harf_duyarsiz():
    kayitlar = [nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI)]
    assert nm.notam_ara(kayitlar, anahtar_kelime="rwy") == kayitlar  # text icinde 'RWY' var, kucuk harfle de eslesir
    assert nm.notam_ara(kayitlar, anahtar_kelime="SURFACE") == kayitlar


def test_notam_ara_tarih_araligi_kesisim():
    kayitlar = [nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI)]  # 2026-08-28 -> 2026-10-02
    # sorgu araligi NOTAM'in ortasina denk geliyor -> kesisir
    assert nm.notam_ara(kayitlar, tarih_baslangic="2026-09-01T00:00:00Z",
                         tarih_bitis="2026-09-30T00:00:00Z") == kayitlar
    # sorgu araligi tamamen NOTAM'dan ONCE -> kesismez
    assert nm.notam_ara(kayitlar, tarih_baslangic="2026-01-01T00:00:00Z",
                         tarih_bitis="2026-01-31T00:00:00Z") == []
    # sorgu araligi tamamen NOTAM'dan SONRA -> kesismez
    assert nm.notam_ara(kayitlar, tarih_baslangic="2026-12-01T00:00:00Z",
                         tarih_bitis="2026-12-31T00:00:00Z") == []


def test_notam_ara_durum_filtresi():
    kayitlar = [nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI)]
    assert nm.notam_ara(kayitlar, durum="active") == kayitlar
    assert nm.notam_ara(kayitlar, durum="withdrawn") == []


def test_notam_ara_sonuc_bulunamazsa_bos_liste():
    kayitlar = [nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI)]
    assert nm.notam_ara(kayitlar, anahtar_kelime="XYZABC123") == []


def test_notam_ara_kriter_yoksa_hepsi_doner():
    kayitlar = [nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI),
                nm._notam_modeline_cevir(no.RUNWAY_KAPANIS)]
    assert nm.notam_ara(kayitlar) == kayitlar


# ------------------------------------------------------------------- gecmis
def test_gecmisi_guncelle_yeni_kayit_eklenir():
    kayit = nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI)
    gecmis = nm.gecmisi_guncelle({}, [kayit], simdi="2026-09-16T12:00:00Z")
    assert kayit["id"] in gecmis
    assert gecmis[kayit["id"]]["first_seen"] == "2026-09-16T12:00:00Z"
    assert gecmis[kayit["id"]]["last_seen"] == "2026-09-16T12:00:00Z"
    assert gecmis[kayit["id"]]["last_active"] == "2026-09-16T12:00:00Z"


def test_gecmisi_guncelle_id_yoksa_atlanir():
    kayit_id_yok = nm._notam_modeline_cevir(no.GECERSIZ_KAYIT_ID_YOK)
    gecmis = nm.gecmisi_guncelle({}, [kayit_id_yok], simdi="2026-09-16T12:00:00Z")
    assert gecmis == {}


def test_gecmisi_guncelle_degismeyen_kayit_first_seen_korur():
    kayit = nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI)
    gecmis = nm.gecmisi_guncelle({}, [kayit], simdi="2026-09-01T00:00:00Z")
    # ayni record_updated_at ile TEKRAR goruldu (degismedi)
    gecmis2 = nm.gecmisi_guncelle(gecmis, [kayit], simdi="2026-09-16T12:00:00Z")
    kayitli = gecmis2[kayit["id"]]
    assert kayitli["first_seen"] == "2026-09-01T00:00:00Z"   # DEGISMEDI
    assert kayitli["last_seen"] == "2026-09-16T12:00:00Z"    # ILERLEDI


def test_gecmisi_guncelle_degisen_kayit_guncellenir():
    eski = nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI)
    gecmis = nm.gecmisi_guncelle({}, [eski], simdi="2026-09-01T00:00:00Z")

    guncellenmis_ham = dict(no.RUNWAY_YUZEY_DUZENSIZLIGI)
    guncellenmis_ham["record_updated_at"] = "2026-09-15T00:00:00Z"
    guncellenmis_ham["text"] = "GUNCELLENMIS METIN."
    yeni = nm._notam_modeline_cevir(guncellenmis_ham)

    gecmis2 = nm.gecmisi_guncelle(gecmis, [yeni], simdi="2026-09-16T12:00:00Z")
    kayitli = gecmis2[eski["id"]]
    assert kayitli["text"] == "GUNCELLENMIS METIN."
    assert kayitli["first_seen"] == "2026-09-01T00:00:00Z"   # kimlik ayni, first_seen korunur


def test_gecmisi_guncelle_duplicate_yeni_kayit_uretmez():
    """Ayni NOTAM iki farkli calistirmada tekrar tekrar 'yeni' sayilmamali -
    gecmis sozlugunde HEP AYNI id altinda tek bir kayit olarak kalmali."""
    kayit = nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI)
    gecmis = {}
    for i in range(5):
        gecmis = nm.gecmisi_guncelle(gecmis, [kayit], simdi=f"2026-09-{10+i:02d}T00:00:00Z")
    assert len(gecmis) == 1


def test_gecmisi_guncelle_artik_aktif_olmayan_silinmez_last_active_korunur():
    """Bir NOTAM aktif listeden dustugunde (artik NOTAC aktif olarak
    dondurmuyor) yerel gecmisten SILINMEMELI - last_active oldugu gibi
    kalmali, last_seen ilerlemeMEli."""
    kayit = nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI)
    gecmis = nm.gecmisi_guncelle({}, [kayit], simdi="2026-09-01T00:00:00Z")

    # Bir sonraki senkronizasyonda bu NOTAM ARTIK aktif listede YOK.
    gecmis2 = nm.gecmisi_guncelle(gecmis, [], simdi="2026-09-16T12:00:00Z")

    assert kayit["id"] in gecmis2                          # SILINMEDI
    assert gecmis2[kayit["id"]]["last_active"] == "2026-09-01T00:00:00Z"  # korunuyor
    assert gecmis2[kayit["id"]]["last_seen"] == "2026-09-01T00:00:00Z"    # ILERLEMEDI


def test_gecmisi_guncelle_withdrawn_durumu_yansitilir():
    aktif = nm._notam_modeline_cevir(no.RUNWAY_YUZEY_DUZENSIZLIGI)
    gecmis = nm.gecmisi_guncelle({}, [aktif], simdi="2026-09-01T00:00:00Z")

    withdrawn_ham = dict(no.RUNWAY_YUZEY_DUZENSIZLIGI)
    withdrawn_ham["status"] = "withdrawn"
    withdrawn_ham["record_updated_at"] = "2026-09-16T00:00:00Z"
    withdrawn = nm._notam_modeline_cevir(withdrawn_ham)

    gecmis2 = nm.gecmisi_guncelle(gecmis, [withdrawn], simdi="2026-09-16T12:00:00Z")
    kayitli = gecmis2[aktif["id"]]
    assert kayitli["status"] == "withdrawn"
    assert kayitli["last_active"] == "2026-09-01T00:00:00Z"  # son aktif oldugu an KORUNDU


# ------------------------------------------------ yaklasan NOTAM sorgusu
# OLCULDU (bkz. notam_kesif.py ciktisi, OPTIONS /notam/ tarifi):
#     ?status=active|upcoming|expired|any   (varsayilan: active)
# "all" DEGIL - denendi, HTTP hatasi verdi.
def test_varsayilan_sorgu_STATUS_GONDERMIYOR(monkeypatch):
    """NOTAC'in kendi varsayilani zaten "active" - gereksiz parametre
    gondermiyoruz ve mevcut davranis birebir korunuyor."""
    cagrilar = []

    def sahte(location, ek_parametreler=None):
        cagrilar.append(ek_parametreler)
        return {"results": [], "next": None}

    monkeypatch.setattr(nm.client, "notam_getir", sahte)
    nm.notamlari_getir("LTFJ")
    assert cagrilar == [None]


def test_yaklasan_icin_status_upcoming_gonderiliyor(monkeypatch):
    cagrilar = []

    def sahte(location, ek_parametreler=None):
        cagrilar.append(ek_parametreler)
        return {"results": [], "next": None}

    monkeypatch.setattr(nm.client, "notam_getir", sahte)
    nm.notamlari_getir("LTFJ", nm.DURUM_YAKLASAN)
    assert cagrilar == [{"status": "upcoming"}]


def test_iki_sorgu_da_atiliyor_ve_kayitlar_TEKILLESTIRILIYOR(monkeypatch):
    """Ayni NOTAM iki sorgudan da gelebilir; gecmise iki kez girmemeli."""
    def kayit(no, nid):
        return {"id": nid, "number": no, "location_code": "LTFJ", "status": "active",
                "text": "X", "effective_start": "2026-01-01T00:00:00Z"}

    durumlar = []

    def sahte(location, ek_parametreler=None):
        durum = (ek_parametreler or {}).get("status")
        durumlar.append(durum)
        if durum == "upcoming":
            return {"results": [kayit("B0002/26", "i2"), kayit("B0001/26", "i1")], "next": None}
        return {"results": [kayit("B0001/26", "i1")], "next": None}

    monkeypatch.setattr(nm.client, "notam_getir", sahte)
    sonuc = nm.yururlukteki_ve_yaklasan_notamlar("LTFJ")
    assert durumlar == ["active", "upcoming"]
    assert [n["number"] for n in sonuc] == ["B0001/26", "B0002/26"]


def test_yaklasan_sorgusu_COKERSE_yururluktekiler_yine_donuyor(monkeypatch):
    """Yeni ve İKİNCİL bir bilgi yüzünden ana akışı kaybetmeyiz."""
    def sahte(location, ek_parametreler=None):
        if (ek_parametreler or {}).get("status") == "upcoming":
            raise nm.client.NotamAgHatasi("koptu")
        return {"results": [{"id": "i1", "number": "B0001/26", "location_code": "LTFJ",
                             "status": "active", "text": "X"}], "next": None}

    monkeypatch.setattr(nm.client, "notam_getir", sahte)
    sonuc = nm.yururlukteki_ve_yaklasan_notamlar("LTFJ")
    assert [n["number"] for n in sonuc] == ["B0001/26"]


def test_yururluktekiler_sorgusu_cokerse_HATA_YUKSELIYOR(monkeypatch):
    """Ana akış sessizce boş dönmemeli - çağıran taraf bilmeli."""
    def sahte(location, ek_parametreler=None):
        raise nm.client.NotamAgHatasi("koptu")

    monkeypatch.setattr(nm.client, "notam_getir", sahte)
    with pytest.raises(nm.NotamServisHatasi):
        nm.yururlukteki_ve_yaklasan_notamlar("LTFJ")
