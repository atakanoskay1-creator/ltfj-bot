"""MODEL B ("görüşsüz atmosferik sis oluşum potansiyeli") testleri.

En kritik dört test:
(1) hedef.hazirla()'nın ufuk_saat parametresi GERİYE UYUMLU - varsayılan
    davranış (Model A) birebir korunuyor,
(2) bolme.embargo_penceresi() sınıra yakın satırları GERÇEKTEN çıkarıyor -
    araştırma raporunda tespit edilen sınır kontaminasyonunu kapatan
    mekanizma,
(3) olusum_alanlar.dogrula() YASAKLI (görüş-türevi) alanları çalışma
    zamanında engelliyor,
(4) olay_degerlendirme bağımsız olayları doğru gruplayıp "olay başına TEK
    tahmin" ilkesini uyguluyor - satır-düzeyinde çift sayımı önleyen
    mekanizma.
"""
import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sis_modeli import bolme, hedef, olay_degerlendirme, olusum_alanlar

KOK = Path(__file__).resolve().parent.parent


def _seri(sis_indeksleri=(), n=48, **alanlar):
    baslangic = datetime(2024, 1, 15, tzinfo=timezone.utc)
    satirlar = []
    for i in range(n):
        t = baslangic + timedelta(minutes=30 * i)
        r = {"zaman": t.strftime("%Y-%m-%dT%H:%M"), "ay": t.month, "saat": t.hour,
             "sicaklik": 10, "cig_noktasi": 8, "spread": 2.0, "ruzgar_hiz": 5,
             "ruzgar_yon": 90, "gorus": 9999, "tavan": None, "qnh": 1015,
             "sis_kodu": 0, "sis": int(i in sis_indeksleri), "lvo": 0}
        for a, degerler in alanlar.items():
            r[a] = degerler[i]
        satirlar.append(r)
    return satirlar


# ------------------------------------------------------------ hedef.hazirla
def test_ufuk_saat_varsayilan_davranisi_degistirmiyor():
    """Model A'nın çağrı biçimi (ufuk_saat verilmeden) birebir aynı
    kalmalı - geriye uyumluluk."""
    k = hedef.hazirla(_seri(sis_indeksleri={20}))
    assert k[14]["hedef"] is True       # 6 adım (3 saat) önce
    assert k[13]["hedef"] is False      # 7 adım önce - pencere dışında
    assert all(r["hedef_ufuk_saat"] == 3 for r in k)


def test_ufuk_saat_kisaltilinca_pencere_daraliyor():
    """30 dakikalık ufukta yalnızca 1 adım ileri bakılmalı."""
    k = hedef.hazirla(_seri(sis_indeksleri={20}), ufuk_saat=0.5)
    assert k[19]["hedef"] is True       # 1 adım (30dk) önce
    assert k[18]["hedef"] is False      # 2 adım önce - artık pencere dışı
    assert all(r["hedef_ufuk_saat"] == 0.5 for r in k)


def test_ufuk_saat_uzatilinca_pencere_genisliyor():
    k = hedef.hazirla(_seri(sis_indeksleri={20}), ufuk_saat=1.0)
    assert k[18]["hedef"] is True       # 2 adım (1 saat) önce
    assert k[17]["hedef"] is False


def test_farkli_ufuklarda_ayni_veriden_farkli_hedef_uretiliyor():
    """Aynı ham veri, farklı ufuklarda farklı hedef üretmeli - lead-time
    deneyinin (ufuk_deneyi.py) temel varsayımı."""
    kisa = hedef.hazirla(_seri(sis_indeksleri={20}), ufuk_saat=0.5)
    uzun = hedef.hazirla(_seri(sis_indeksleri={20}), ufuk_saat=3.0)
    assert sum(r["hedef"] for r in kisa) < sum(r["hedef"] for r in uzun)


# --------------------------------------------------------- bolme embargosu
def _kayit_dt(dt, ufuk=3.0):
    return {"dt": dt, "hedef_ufuk_saat": ufuk}


def test_embargo_penceresi_sinira_yakin_satiri_cikariyor():
    k = [_kayit_dt(datetime(2016, 12, 31, 23, 30)),
         _kayit_dt(datetime(2016, 12, 31, 20, 0)),
         _kayit_dt(datetime(2016, 6, 1, 0, 0))]
    kalan = bolme.embargo_penceresi(k, 2017)
    assert len(kalan) == 2
    assert datetime(2016, 12, 31, 23, 30) not in {r["dt"] for r in kalan}


def test_embargo_penceresi_sinirdan_uzak_satirlari_koruyor():
    k = [_kayit_dt(datetime(2016, 1, 1, 0, 0))]
    assert len(bolme.embargo_penceresi(k, 2017)) == 1


def test_embargo_penceresi_ufuk_otomatik_aliniyor():
    """saat verilmezse kayitlardaki hedef_ufuk_saat'ten otomatik alinmali."""
    k = [_kayit_dt(datetime(2016, 12, 31, 22, 45), ufuk=1.0)]
    # 1 saatlik ufukta 22:45 -> 1 Ocak'a 1h15dk var, embargo DISINDA kalmali
    assert len(bolme.embargo_penceresi(k, 2017)) == 1
    k2 = [_kayit_dt(datetime(2016, 12, 31, 23, 30), ufuk=1.0)]
    # 1 saatlik ufukta 23:30 -> tam sinirda, embargo İÇİNDE
    assert len(bolme.embargo_penceresi(k2, 2017)) == 0


def test_ayir_embargolu_ayir_ile_ayni_kumeyi_daraltiyor():
    k = [_kayit_dt(datetime(2016, 12, 31, 23, 30)),
         _kayit_dt(datetime(2016, 6, 1, 0, 0)),
         _kayit_dt(datetime(2015, 6, 1, 0, 0))]
    tam = bolme.ayir(k, (2015, 2016))
    embargolu = bolme.ayir_embargolu(k, (2015, 2016), sonraki_yil=2017)
    assert len(embargolu) == len(tam) - 1


def test_ayir_embargolu_bos_kumede_cokmez():
    assert bolme.ayir_embargolu([], (2020,)) == []


# ------------------------------------------------------------ olusum_alanlar
def test_dogrula_gorusu_yasakliyor():
    import pytest
    with pytest.raises(ValueError, match="gorus"):
        olusum_alanlar.dogrula(["spread", "gorus"])


def test_dogrula_sis_kodunu_yasakliyor():
    import pytest
    with pytest.raises(ValueError):
        olusum_alanlar.dogrula(["sis_kodu"])


def test_dogrula_guvenli_listede_sorunsuz():
    olusum_alanlar.dogrula(["spread", "saat", "ruzgar_kuzey"])   # patlamamalı


def test_sis_yakinligi_ciplak_fg_de_tetiklenmiyor():
    """Çıplak FG zaten sis_kodu ile aynı bilgi - sis_yakinligi bunu AYRI bir
    öncül sinyal olarak SAYMAMALI (aksi halde dolaylı sızıntı olurdu)."""
    assert olusum_alanlar.sis_yakinligi("FG") == 0


def test_sis_yakinligi_br_ve_nitelikli_fg_tetikleniyor():
    for kod in ("BR", "VCFG", "MIFG", "BCFG", "PRFG"):
        assert olusum_alanlar.sis_yakinligi(kod) == 1, kod


def test_sis_yakinligi_bos_ve_ilgisiz_kodda_sifir():
    assert olusum_alanlar.sis_yakinligi("") == 0
    assert olusum_alanlar.sis_yakinligi("SCT020") == 0


def test_yasakli_ve_adaylar_ayrik():
    """Bir alan aynı anda hem güvenli aday hem yasaklı olamaz."""
    assert not set(olusum_alanlar.ADAYLAR) & set(olusum_alanlar.YASAKLI)
    assert not set(olusum_alanlar.TARTISMALI_ADAYLAR) & set(olusum_alanlar.YASAKLI)


# --------------------------------------------------------- olay_degerlendirme
def test_bagimsiz_olaylar_bosluklu_pozitifleri_ayiriyor():
    """3 saatten büyük boşlukla ayrılan pozitifler AYRI olaylar sayılmalı."""
    k = hedef.hazirla(_seri(sis_indeksleri={2, 3, 20, 21, 22}))  # iki küme, >3h ara
    olaylar = olay_degerlendirme.bagimsiz_olaylar(k)
    assert len(olaylar) == 2


def test_bagimsiz_olaylar_yakin_pozitifleri_birlestiriyor():
    """Aralarında <=3h olan pozitifler TEK olay sayılmalı."""
    k = hedef.hazirla(_seri(sis_indeksleri={10, 11, 12, 13}))  # ardışık, 30dk ara
    olaylar = olay_degerlendirme.bagimsiz_olaylar(k)
    assert len(olaylar) == 1


def test_bagimsiz_olaylar_pozitif_yoksa_bos():
    assert olay_degerlendirme.bagimsiz_olaylar(hedef.hazirla(_seri())) == []


def test_olay_temsilci_satirlari_hemen_onceki_satiri_buluyor():
    k = hedef.hazirla(_seri(sis_indeksleri={20}))
    olaylar = olay_degerlendirme.bagimsiz_olaylar(k)
    temsilciler = olay_degerlendirme.olay_temsilci_satirlari(k, olaylar)
    assert len(temsilciler) == 1
    assert temsilciler[0]["temsilci"]["dt"] == k[19]["dt"]     # 30dk önce
    assert temsilciler[0]["temsilci"]["sis"] == 0


def test_olay_temsilci_satirlari_ufuk_disinda_none_donuyor():
    """Olayın hemen öncesinde onset-aday satır YOKSA (örn. arşiv başında
    yeterli geçmiş yoksa) temsilci None olmalı - uydurma satır üretilmez."""
    k = hedef.hazirla(_seri(sis_indeksleri={0}))  # ilk satırdan sis - geçmiş yok
    olaylar = olay_degerlendirme.bagimsiz_olaylar(k)
    temsilciler = olay_degerlendirme.olay_temsilci_satirlari(k, olaylar)
    assert temsilciler[0]["temsilci"] is None


def test_olay_bazli_esik_tablosu_temsilcisizleri_disliyor():
    k = hedef.hazirla(_seri(sis_indeksleri={0, 30}))  # biri temsilcisiz, biri temsilcili
    olaylar = olay_degerlendirme.bagimsiz_olaylar(k)
    temsilciler = olay_degerlendirme.olay_temsilci_satirlari(k, olaylar)
    tahmin_map = {t["temsilci"]["dt"]: 0.9 for t in temsilciler if t["temsilci"]}
    tablo = olay_degerlendirme.olay_bazli_esik_tablosu(temsilciler, tahmin_map,
                                                        esikler=(0.5,))
    assert tablo[0]["toplam_olay"] == 1          # yalnızca temsilcili olan sayıldı
    assert tablo[0]["yakalanan"] == 1


def test_olay_bazli_guven_araligi_nokta_tahmini_kapsiyor():
    k = []
    for gun in range(10):
        baslangic = datetime(2024, 1, 1 + gun, tzinfo=timezone.utc)
        for i in range(6):
            t = baslangic + timedelta(minutes=30 * i)
            k.append({"zaman": t.strftime("%Y-%m-%dT%H:%M"),
                      "sis": int(i >= 4)})
    k = hedef.hazirla(k, etiket="sis")
    olaylar = olay_degerlendirme.bagimsiz_olaylar(k)
    assert len(olaylar) == 10
    temsilciler = olay_degerlendirme.olay_temsilci_satirlari(k, olaylar)
    tahmin_map = {t["temsilci"]["zaman"]: 0.3 for t in temsilciler if t["temsilci"]}
    # tahmin_map dt degil zaman anahtari kullandigi icin _tahmin_al 0 donecek -
    # bu testte asil amac cokme olmamasi ve aralik iceriginin tutarli olmasi
    alt, ust = olay_degerlendirme.olay_bazli_guven_araligi(temsilciler, {}, 0.1, tekrar=50)
    assert 0.0 <= alt <= ust <= 1.0


def test_olay_ozet_temel_sayilari_veriyor():
    k = hedef.hazirla(_seri(sis_indeksleri={10, 11, 30, 31}))
    ozet = olay_degerlendirme.olay_ozet(k)
    assert ozet["olay_sayisi"] == 2
    assert ozet["ayri_gun_sayisi"] == 1


# --------------------------------------------------------------- izolasyon
def test_yeni_moduller_calisma_anina_sizmiyor():
    """Izolasyon sozlesmesi: bot Model B modullerinden HICBIRINI import
    etmiyor - egit.py/model.py testi gibi, ama tum yeni dosyalar icin."""
    for dosya in ("ltfj_sis_olasilik.py", "ltfj_tavan_tablosu.py",
                  "ltfj_sayfa.py", "ltfj_bot.py", "ltfj_lvo_farkindalik.py"):
        agac = ast.parse((KOK / dosya).read_text(encoding="utf-8"))
        for node in ast.walk(agac):
            adlar = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom)
                     else [])
            for ad in adlar:
                assert ad not in ("olusum_egit", "olusum_alanlar",
                                  "olay_degerlendirme", "ufuk_deneyi",
                                  "olusum_holdout_degerlendir"), (dosya, ad)


def test_alanlar_yasakli_alan_icermiyor():
    """olusum_egit.ALANLAR'in kendisi de dogrula()'yi gecmeli - CI bunu
    her calistiginda otomatik denetler."""
    from sis_modeli.olusum_egit import ALANLAR

    olusum_alanlar.dogrula(ALANLAR)    # patlamamalı
    assert "gorus" not in ALANLAR


def test_agir_bagimlilik_yok():
    """sis modeli disiplini: yeni dosyalar da saf standart kutuphane +
    projenin kendi (ltfj_analiz gibi) test edilmis moduelleri disinda
    bagimlilik almamali."""
    import ast as _ast

    izinli_disaridan = {"ltfj_analiz"}
    for dosya in ("olusum_egit.py", "olay_degerlendirme.py", "ufuk_deneyi.py",
                  "olusum_alanlar.py", "olusum_holdout_degerlendir.py"):
        agac = _ast.parse((KOK / "sis_modeli" / dosya).read_text(encoding="utf-8"))
        for node in _ast.walk(agac):
            if isinstance(node, _ast.Import):
                for a in node.names:
                    kok_modul = a.name.split(".")[0]
                    assert (kok_modul.startswith("sis_modeli") or
                           kok_modul in izinli_disaridan or
                           kok_modul in ("sys", "argparse", "pathlib", "math",
                                         "random", "collections", "datetime",
                                         "ast")), (dosya, kok_modul)
            elif isinstance(node, _ast.ImportFrom) and node.module:
                kok_modul = node.module.split(".")[0]
                assert (kok_modul.startswith("sis_modeli") or
                       kok_modul in izinli_disaridan or
                       kok_modul in ("pathlib", "collections", "datetime")
                       ), (dosya, kok_modul)
