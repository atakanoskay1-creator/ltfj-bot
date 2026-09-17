"""ltfj_bot.py::atc_notes_temizligini_calistir() gating testleri.

Bu fonksiyon METAR/NOTAM'dan TAMAMEN bagimsiz - testler NOTAM'a hic
dokunmadan sadece bu tek katmanin ayar/yapilandirma kontrolunu
dogruluyor. Gercek Firebase cagrisi burada MOCK'lanir (bkz.
test_ltfj_atc_notes_cleanup.py::expired_atc_notes_cleanup icin ayrintili
testler zaten var - burada sadece ltfj_bot.py'nin bu fonksiyonu DOGRU
kosullarda cagirip cagirmadigi test ediliyor)."""
from unittest.mock import patch

import ltfj_bot as b


def _sahte_ayar(atc_notes_ayarlari):
    def sahte(*yol, varsayilan=None):
        if yol and yol[0] == "atc_notes":
            d = atc_notes_ayarlari
            for k in yol[1:]:
                if not isinstance(d, dict) or k not in d:
                    return varsayilan
                d = d[k]
            return d
        return varsayilan
    return sahte


def test_atc_notes_kapaliysa_temizlik_calismaz(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": False}))
    with patch.object(b.ltfj_atc_notes_cleanup, "yapilandirilmis_mi", return_value=True), \
            patch.object(b.ltfj_atc_notes_cleanup, "expired_atc_notes_cleanup") as sahte_cleanup:
        sonuc = b.atc_notes_temizligini_calistir()
    sahte_cleanup.assert_not_called()
    assert sonuc is None


def test_firebase_yapilandirilmamissa_temizlik_calismaz(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": True}))
    with patch.object(b.ltfj_atc_notes_cleanup, "yapilandirilmis_mi", return_value=False), \
            patch.object(b.ltfj_atc_notes_cleanup, "expired_atc_notes_cleanup") as sahte_cleanup:
        sonuc = b.atc_notes_temizligini_calistir()
    sahte_cleanup.assert_not_called()
    assert sonuc is None


def test_aktif_ve_yapilandirilmissa_temizlik_calisir(monkeypatch):
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": True}))
    with patch.object(b.ltfj_atc_notes_cleanup, "yapilandirilmis_mi", return_value=True), \
            patch.object(b.ltfj_atc_notes_cleanup, "expired_atc_notes_cleanup", return_value=3) as sahte_cleanup:
        sonuc = b.atc_notes_temizligini_calistir()
    sahte_cleanup.assert_called_once()
    assert sonuc == 3


def test_atc_notes_hatasi_notam_senkronunu_etkilemez(monkeypatch):
    """ATC Notes temizligi (Firebase) patlarsa NOTAM senkronizasyonu
    hicbir sekilde etkilenmemeli - main()'deki iki blok birbirinden
    TAMAMEN bagimsiz try/except'lerle sarili (bkz. ltfj_bot.py)."""
    monkeypatch.setattr(b, "ayar", _sahte_ayar({"aktif": True}))
    with patch.object(b.ltfj_atc_notes_cleanup, "yapilandirilmis_mi", return_value=True), \
            patch.object(b.ltfj_atc_notes_cleanup, "expired_atc_notes_cleanup",
                          side_effect=b.ltfj_atc_notes_cleanup.AtcNotesTemizlikHatasi("Firebase çöktü")):
        try:
            b.atc_notes_temizligini_calistir()
            basarisiz_oldu = False
        except b.ltfj_atc_notes_cleanup.AtcNotesTemizlikHatasi:
            basarisiz_oldu = True
    # main() bu hatayi try/except ile yakalar (kaynak koduna bakinca
    # gorulur) - burada fonksiyonun kendisinin hatayi YUTMADIGINI, ust
    # seviyenin (main) yakalamaktan sorumlu oldugunu dogruluyoruz.
    assert basarisiz_oldu
