"""P3: MGM'ye erisilememesi (AgHatasi) 'yeni veri yok' ile AYNI SEY degil.

Onceden main() AgHatasi'ni yakaladiginda dogrudan return ediyordu -
sessizlik_kontrol() hic cagrilmiyordu, yani MGM TAMAMEN COKSE bile "veri
akmıyor" alarmi hicbir zaman tetiklenemiyordu (tam da alarmin en cok
gerekli oldugu an). Bu test main()'in artik AgHatasi'nda da
sessizlik_kontrol()'u (bos rapor listesiyle) calistirdigini, state'teki
onceden bilinen veri zamanina gore yaslandirma yaptigini dogruluyor."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import ltfj_bot as b
from ltfj_rasat import AgHatasi


def _sahte_telegram_post():
    gonderilenler = []

    def fake_post(url, headers=None, json=None, timeout=None):
        gonderilenler.append(json)

        class R:
            content = b'{"ok": true, "result": {"message_id": 1}}'

            def json(self):
                return {"ok": True, "result": {"message_id": 1}}
        return R()

    return fake_post, gonderilenler


def test_mgm_erisilemezse_stale_veri_alarmi_yine_de_kontrol_edilir(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "sahte-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setattr(b, "STATE", tmp_path / "ltfj_state.json")
    monkeypatch.setattr(b, "ENV", tmp_path / ".env")   # gercek .env okunmasin

    # State'te 10 saat once gorulmus bir veri var (SESSIZLIK_SAAT=6 asilmis) -
    # MGM'ye simdi erisilemezse bu, alarmi tetiklemesi gereken tam senaryo.
    eski_zaman = datetime.now(timezone.utc) - timedelta(hours=10)
    baslangic_state = {
        "gonderilen": [], "ilk_calisma": False, "son_metar": "",
        "son_uyari": None, "durum_mesaj_id": None, "son_renk": None,
        "son_veri_zamani": eski_zaman.isoformat(timespec="seconds"),
        "olcum_gecmisi": [], "yorum_onbellegi": {},
    }
    b.STATE.write_text(__import__("json").dumps(baslangic_state), encoding="utf-8")

    fake_post, gonderilenler = _sahte_telegram_post()

    with patch("ltfj_bot.raporlari_cek", side_effect=AgHatasi("bağlantı koptu")), \
            patch("requests.post", fake_post):
        b.main()

    # sessizlik_kontrol() calisti VE alarmi gonderdi.
    mesajlar = [g["text"] for g in gonderilenler if "text" in g]
    assert any("veri akmıyor" in m for m in mesajlar)

    # state dosyasi yine de yazildi (son_uyari guncellendi, calisma cokmedi).
    yazilan_state = __import__("json").loads(b.STATE.read_text(encoding="utf-8"))
    assert yazilan_state["son_uyari"] is not None
