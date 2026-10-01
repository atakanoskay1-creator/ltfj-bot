#!/usr/bin/env python3
"""
ATC Notes (durumsal farkindalik notlari) icin arka plan temizlik gorevi.

Notlarin kendisi (olusturma + okuma) DOGRUDAN tarayicidan Firebase Realtime
Database'e yazilir/okunur (bkz. ltfj_sayfa.py) - bu modulun TEK isi, 48
saati dolmus notlari storage'dan FIILEN silmek (frontend'de gizlemek
yetmez). METAR/TAF/NOTAM sisteminden TAMAMEN bagimsizdir; bu modulun
basarisiz olmasi (Firebase erisilemez, servis hesabi tanimli degil vb.)
METAR/NOTAM akisini hicbir sekilde etkilemez - cagiran taraf (ltfj_bot.py)
tum hatalari yakalayip sadece bu ozelligi atlar.

GUVENLIK: FIREBASE_SERVICE_ACCOUNT ortam degiskeni (servis hesabi JSON'u)
GERCEK bir sirdir - NOTAC_API_KEY ile AYNI desen: os.getenv() ile okunur,
asla loglanmaz, asla istemciye/JS'e gonderilmez. Notlarin okuma/yazma
akisi (tarayici <-> Firebase) bu credential'i HIC gormez; sadece bu
cleanup script'i, admin yetkisiyle Realtime Database Rules'u bypass
ederek silme yapmak icin kullanir.
"""

import json
import os
import time

NOT_YASAM_SURESI_SANIYE = 48 * 3600


class AtcNotesTemizlikHatasi(Exception):
    """Yapilandirma eksik ya da Firebase'e erisilemedi - cagiran taraf
    (ltfj_bot.py) tek bu sinifi yakalamasi yeterli."""


def yapilandirilmis_mi() -> bool:
    return bool(os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()) and \
        bool(os.environ.get("FIREBASE_DATABASE_URL", "").strip())


def _uygulama_al():
    """firebase_admin'i burada, fonksiyon icinde import ediyoruz - boylece
    paket kurulu olmasa bile (ör. testlerde) modulun geri kalani
    calisabilir, sadece bu fonksiyon cagrildiginda ImportError alinir."""
    import firebase_admin
    from firebase_admin import credentials

    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()
    if not sa_json:
        raise AtcNotesTemizlikHatasi("FIREBASE_SERVICE_ACCOUNT tanımlı değil.")
    database_url = os.environ.get("FIREBASE_DATABASE_URL", "").strip()
    if not database_url:
        raise AtcNotesTemizlikHatasi("FIREBASE_DATABASE_URL tanımlı değil.")

    try:
        sa_bilgisi = json.loads(sa_json)
    except json.JSONDecodeError as e:
        raise AtcNotesTemizlikHatasi(f"FIREBASE_SERVICE_ACCOUNT geçerli JSON değil: {e}") from e

    if firebase_admin._apps:
        return firebase_admin.get_app()
    try:
        cred = credentials.Certificate(sa_bilgisi)
        return firebase_admin.initialize_app(cred, {"databaseURL": database_url})
    except Exception as e:
        raise AtcNotesTemizlikHatasi(f"Firebase uygulaması başlatılamadı: {e}") from e


def expired_atc_notes_cleanup(simdi_ms: int | None = None) -> int:
    """created_at + 48 saati dolmus TUM ATC notlarini Realtime Database'den
    fiilen SILER, silinen kayit sayisini dondurur.

    Idempotent: silinecek bir sey kalmadiginda tekrar tekrar cagirilsa da
    hata vermez, 0 doner - bozuk/eksik alanli bir kayit da crash etmez,
    sadece atlanir (silinmeden birakilir, bir sonraki calistirmada tekrar
    denenir)."""
    from firebase_admin import db

    _uygulama_al()
    simdi_ms = simdi_ms if simdi_ms is not None else int(time.time() * 1000)

    ref = db.reference("atc_notes")
    try:
        kayitlar = ref.get() or {}
    except Exception as e:
        raise AtcNotesTemizlikHatasi(f"Realtime Database okunamadı: {e}") from e

    silinen = 0
    for not_id, kayit in kayitlar.items():
        if not isinstance(kayit, dict):
            continue
        created_at = kayit.get("created_at")
        if not isinstance(created_at, (int, float)):
            continue
        if simdi_ms - created_at >= NOT_YASAM_SURESI_SANIYE * 1000:
            ref.child(not_id).delete()
            silinen += 1
    return silinen
