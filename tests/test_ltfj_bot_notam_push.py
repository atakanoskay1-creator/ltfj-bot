"""ltfj_bot.py::notam_senkronize - yeni NOTAM push tetikleyicisi testleri.

En kritik test: gecmis BOŞSA (ilk senkronizasyon - o an aktif olan HER
NOTAM teknik olarak "yeni") HİÇBİR push gönderilmemeli - aksi halde ilk
çalıştırmada aktif NOTAM sayısı kadar bildirim patlardı (ltfj_bot'un kendi
METAR tarafındaki "ilk_calisma" ilkesiyle aynı)."""
import sys
import types
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

import ltfj_bot as bot
import ltfj_notam_client as notam_client


@pytest.fixture
def sahte_notam_ortami(monkeypatch):
    monkeypatch.setattr(notam_client, "api_anahtari_var_mi", lambda: True)

    fake_push = types.ModuleType("ltfj_push")
    fake_push.yapilandirilmis_mi = MagicMock(return_value=True)
    fake_push.gonder = MagicMock(return_value={"gonderildi": 1, "silindi": 0, "hata": 0})
    monkeypatch.setitem(sys.modules, "ltfj_push", fake_push)
    return fake_push


def _kayit(nid, number="A0001/26", text="Örnek NOTAM metni"):
    return {"id": nid, "number": number, "text": text, "status": "active",
           "record_updated_at": "2026-09-20T00:00:00Z"}


def test_ilk_senkronizasyonda_hic_push_gonderilmiyor(monkeypatch, sahte_notam_ortami):
    monkeypatch.setattr(bot.ltfj_notam, "yururlukteki_ve_yaklasan_notamlar",
                        lambda loc, gecmis=None: [_kayit("n1"), _kayit("n2")])
    state = {}   # notam_gecmisi yok - bu bir ilk senkronizasyon

    bot.notam_senkronize(state)

    sahte_notam_ortami.gonder.assert_not_called()
    assert set(state["notam_gecmisi"]) == {"n1", "n2"}


def test_ikinci_senkronizasyonda_yeni_notam_push_atiyor(monkeypatch, sahte_notam_ortami):
    monkeypatch.setattr(bot.ltfj_notam, "yururlukteki_ve_yaklasan_notamlar",
                        lambda loc, gecmis=None: [_kayit("n1"), _kayit("n2", number="A0002/26")])
    eski_zaman = "2026-09-19T00:00:00+00:00"
    state = {"notam_gecmisi": {"n1": {**_kayit("n1"), "first_seen": eski_zaman,
                                       "last_seen": eski_zaman, "last_active": eski_zaman}},
             "notam_son_senkron": eski_zaman}

    bot.notam_senkronize(state)

    sahte_notam_ortami.gonder.assert_called_once()
    args, kwargs = sahte_notam_ortami.gonder.call_args
    assert "A0002/26" in args[1]      # govde
    assert kwargs.get("etiket") == "NOTAM"


def test_mevcut_notam_tekrar_push_atmiyor(monkeypatch, sahte_notam_ortami):
    """Zaten gorulmus (gecmiste olan) bir NOTAM her senkronizasyonda tekrar
    tekrar bildirim ATMAMALI - sadece GERCEKTEN yeni id'ler icin gonderilir."""
    eski_zaman = "2026-09-19T00:00:00+00:00"
    monkeypatch.setattr(bot.ltfj_notam, "yururlukteki_ve_yaklasan_notamlar",
                        lambda loc, gecmis=None: [_kayit("n1")])
    state = {"notam_gecmisi": {"n1": {**_kayit("n1"), "first_seen": eski_zaman,
                                       "last_seen": eski_zaman, "last_active": eski_zaman}},
             "notam_son_senkron": eski_zaman}

    bot.notam_senkronize(state)

    sahte_notam_ortami.gonder.assert_not_called()


def test_notam_push_govde_number_ve_metni_iceriyor():
    govde = bot._notam_push_govde({"number": "A0001/26", "text": "Pist kapalı"},
                                  yururlukte=True)
    assert "A0001/26" in govde and "Pist kapalı" in govde


def test_notam_push_govde_alanlar_eksikse_genel_metin():
    assert bot._notam_push_govde({}, yururlukte=True) == "Yeni bir NOTAM yayınlandı."


# =============================== yaklaşan / yürürlüğe giren bildirimleri
# KULLANICI SORUSU: "upcoming NOTAM'lar için bildirim atıyor mu, yoksa
# onlar aktif olduğunda mı?" Cevap: ilk GÖRÜLDÜĞÜNDE atıyordu ve metin
# yürürlüğe giriş zamanını HİÇ söylemiyordu - telefona "pist kapanıyor"
# düşüyor ama NOTAM iki gün sonra başlıyor olabiliyordu.
from datetime import datetime, timedelta, timezone   # noqa: E402

SIMDI = datetime.now(timezone.utc)


def _zamanli(nid, bas, bit=None, **ek):
    return {"id": nid, "number": "B9999/26", "text": "RWY 06L/24R WILL BE CLSD.",
            "status": "active", "record_updated_at": "2026-09-20T00:00:00Z",
            "effective_start": bas.isoformat(),
            "effective_end": (bit or (bas + timedelta(days=3))).isoformat(), **ek}


def test_yaklasan_NOTAM_baslikta_ayirt_ediliyor(monkeypatch, sahte_notam_ortami):
    """İkisi aynı başlıkla gitseydi okuyan ayırt edemezdi."""
    ileri = _zamanli("n9", SIMDI + timedelta(days=2))
    monkeypatch.setattr(bot.ltfj_notam, "yururlukteki_ve_yaklasan_notamlar",
                        lambda loc, gecmis=None: [ileri])
    eski = {"n1": {**_kayit("n1"), "first_seen": "x", "last_seen": "x", "last_active": "x"}}
    bot.notam_senkronize({"notam_gecmisi": eski})

    baslik, govde, _ = sahte_notam_ortami.gonder.call_args.args[:3]
    assert "Yaklaşan" in baslik and "Yeni NOTAM" not in baslik
    assert "Yürürlüğe giriyor:" in govde, govde


def test_yururlukteki_NOTAM_govdesinde_giris_zamani_YOK(monkeypatch, sahte_notam_ortami):
    """Zaten yürürlükteyse "yürürlüğe giriyor" satırı gürültü olurdu."""
    simdiki = _zamanli("n9", SIMDI - timedelta(hours=1))
    monkeypatch.setattr(bot.ltfj_notam, "yururlukteki_ve_yaklasan_notamlar",
                        lambda loc, gecmis=None: [simdiki])
    eski = {"n1": {**_kayit("n1"), "first_seen": "x", "last_seen": "x", "last_active": "x"}}
    bot.notam_senkronize({"notam_gecmisi": eski})

    baslik, govde, _ = sahte_notam_ortami.gonder.call_args.args[:3]
    assert "Yeni NOTAM" in baslik
    assert "Yürürlüğe giriyor:" not in govde


def test_yururluge_GIRDIGINDE_ikinci_bildirim_atiliyor(monkeypatch, sahte_notam_ortami):
    """İlk bildirim "iki gün sonra başlıyor" diyordu; o an geldiğinde
    bunu söyleyen bir şey olmalı."""
    kayit = _zamanli("n9", SIMDI - timedelta(minutes=5))
    monkeypatch.setattr(bot.ltfj_notam, "yururlukteki_ve_yaklasan_notamlar",
                        lambda loc, gecmis=None: [kayit])
    # Daha once YAKLASAN diye bildirilmis, henuz yururluk bildirimi yok
    eski = {"n9": {**kayit, "push_yaklasan": True,
                   "first_seen": "x", "last_seen": "x", "last_active": "x"}}
    state = {"notam_gecmisi": eski}
    bot.notam_senkronize(state)

    baslik, govde, _ = sahte_notam_ortami.gonder.call_args.args[:3]
    assert "yürürlükte" in baslik.lower()
    assert "Şu an yürürlükte." in govde
    assert state["notam_gecmisi"]["n9"]["push_yururluk"] is True


def test_yururluk_bildirimi_BIR_KEZ_atiliyor(monkeypatch, sahte_notam_ortami):
    """İşaret konmasaydı her senkronda (3 saatte bir) tekrar giderdi."""
    kayit = _zamanli("n9", SIMDI - timedelta(minutes=5))
    monkeypatch.setattr(bot.ltfj_notam, "yururlukteki_ve_yaklasan_notamlar",
                        lambda loc, gecmis=None: [kayit])
    eski = {"n9": {**kayit, "push_yaklasan": True, "push_yururluk": True,
                   "first_seen": "x", "last_seen": "x", "last_active": "x"}}
    bot.notam_senkronize({"notam_gecmisi": eski})
    sahte_notam_ortami.gonder.assert_not_called()


def test_zaten_yururlukteyken_gorulene_ikinci_bildirim_YOK(monkeypatch, sahte_notam_ortami):
    """push_yaklasan işareti yoksa "başladı" bildirimi anlamsız -
    zaten "Yeni NOTAM" diye bildirilmişti."""
    kayit = _zamanli("n9", SIMDI - timedelta(days=1))
    monkeypatch.setattr(bot.ltfj_notam, "yururlukteki_ve_yaklasan_notamlar",
                        lambda loc, gecmis=None: [kayit])
    eski = {"n9": {**kayit, "first_seen": "x", "last_seen": "x", "last_active": "x"}}
    bot.notam_senkronize({"notam_gecmisi": eski})
    sahte_notam_ortami.gonder.assert_not_called()


def test_hala_yaklasan_ise_ikinci_bildirim_ATILMIYOR(monkeypatch, sahte_notam_ortami):
    kayit = _zamanli("n9", SIMDI + timedelta(days=1))
    monkeypatch.setattr(bot.ltfj_notam, "yururlukteki_ve_yaklasan_notamlar",
                        lambda loc, gecmis=None: [kayit])
    eski = {"n9": {**kayit, "push_yaklasan": True,
                   "first_seen": "x", "last_seen": "x", "last_active": "x"}}
    bot.notam_senkronize({"notam_gecmisi": eski})
    sahte_notam_ortami.gonder.assert_not_called()


def test_UCTAN_UCA_yaklasan_gorulur_sonra_yururluge_girer(monkeypatch, sahte_notam_ortami):
    """MUTASYON DERSİ. Öteki testler push_yaklasan işaretini FİKSTÜRE
    elle koyuyordu, yani işareti KOYAN satırı silmek hiçbir testi
    kırmıyordu - özellik iki senkron boyunca hiç izlenmemişti.

    GERÇEK SENARYO ÖNEMLİ: NOTAM'ın effective_start'ı DEĞİŞMEZ, ilerleyen
    şey SAATTİR. İlk denememde ikinci senkronda başlangıcı geçmişe
    çekmiştim; o hiç çalışmadı, çünkü gecisi_guncelle record_updated_at
    aynıyken saklanan kaydı korur (haklı olarak - NOTAM değişmedi).
    Bu yüzden burada gerçek saat kullanılıyor: başlangıç çok yakın bir
    geleceğe konup kısa bir süre bekleniyor."""
    import time

    # Art arda uc senkron: normalde 3 saatlik sure kapisi ikinciyi ve
    # ucuncuyu BASTAN eler (notam_senkronize erken doner). Zorlama
    # bayragi tam da bunun icin var - testte de onu kullaniyoruz, yani
    # bayrak bu akista ayrica dogrulanmis oluyor.
    monkeypatch.setenv("NOTAM_ZORLA_SENKRON", "true")

    state = {"notam_gecmisi": {
        "n1": {**_kayit("n1"), "first_seen": "x", "last_seen": "x", "last_active": "x"}}}
    kayit = _zamanli("n9", datetime.now(timezone.utc) + timedelta(milliseconds=400),
                     bit=datetime.now(timezone.utc) + timedelta(days=3))
    monkeypatch.setattr(bot.ltfj_notam, "yururlukteki_ve_yaklasan_notamlar",
                        lambda loc, gecmis=None: [kayit])

    # 1. SENKRON - henuz baslamadi
    bot.notam_senkronize(state)
    baslik1 = sahte_notam_ortami.gonder.call_args.args[0]
    assert "Yaklaşan" in baslik1
    assert state["notam_gecmisi"]["n9"]["push_yaklasan"] is True, "işaret konmamış"
    assert "push_yururluk" not in state["notam_gecmisi"]["n9"]

    # 2. SENKRON - ayni kayit, ilerleyen tek sey saat
    time.sleep(0.7)
    sahte_notam_ortami.gonder.reset_mock()
    bot.notam_senkronize(state)
    baslik2, govde2, _ = sahte_notam_ortami.gonder.call_args.args[:3]
    assert "yürürlükte" in baslik2.lower()
    assert "Şu an yürürlükte." in govde2
    assert state["notam_gecmisi"]["n9"]["push_yururluk"] is True

    # 3. SENKRON - bir daha atmamali
    sahte_notam_ortami.gonder.reset_mock()
    bot.notam_senkronize(state)
    sahte_notam_ortami.gonder.assert_not_called()
