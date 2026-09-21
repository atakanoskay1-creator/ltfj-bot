#!/usr/bin/env python3
"""
Web Push (tarayici bildirimleri) sunucu tarafi - Telegram'a EK bir kanal,
onun YERINE gecmez.

ltfj_atc_notes_cleanup.py ile AYNI desen: firebase_admin ile abonelikleri
(push_abonelikler) okur, pywebpush ile her birine gonderir. Istemci tarafi
(abone olma) DOGRUDAN tarayicidan Firebase'e yazar (bkz. ltfj_sayfa.py);
bu modul SADECE gonderimi yapar.

FIREBASE_SERVICE_ACCOUNT / FIREBASE_DATABASE_URL / VAPID_PRIVATE_KEY ortam
degiskenlerinden HERHANGI BIRI tanimli degilse (ya da pywebpush kurulu
degilse) ozellik sessizce devre disi kalir - METAR/TAF/NOTAM akisini
HICBIR SEKILDE etkilemez; cagiran taraf (ltfj_bot.py) tum hatalari
yakalayip sadece bu ozelligi atlar.

GUVENLIK: FIREBASE_SERVICE_ACCOUNT ve VAPID_PRIVATE_KEY GERCEK birer
sirdir - ltfj_atc_notes_cleanup.py/NOTAC_API_KEY ile AYNI desen: os.
getenv() ile okunur, asla loglanmaz, asla istemciye/JS'e gonderilmez.
VAPID_PUBLIC_KEY (ayarlar.json::push.vapid_public_key) bunun tam tersi -
GIZLI DEGIL, istemci tarafinda aynen gorunur.
"""

import json
import os

# Push servisleri gecersiz/iptal edilmis bir abonelige bu durum kodlarindan
# biriyle cevap verir (RFC 8030) - bu durumda kayit gercekten kaybolmus
# demektir (kullanici bildirimleri kapatmis, tarayici verisini silmis vb.),
# baska bir hata degil, Firebase'den fiilen silinir.
GECERSIZ_ABONELIK_KODLARI = (404, 410)


class PushGonderimHatasi(Exception):
    """Yapilandirma eksik ya da Firebase'e erisilemedi - cagiran taraf
    (ltfj_bot.py) tek bu sinifi yakalamasi yeterli."""


def yapilandirilmis_mi() -> bool:
    return bool(os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()) and \
        bool(os.environ.get("FIREBASE_DATABASE_URL", "").strip()) and \
        bool(os.environ.get("VAPID_PRIVATE_KEY", "").strip())


def _uygulama_al():
    """firebase_admin'i burada, fonksiyon icinde import ediyoruz - boylece
    paket kurulu olmasa bile (ör. testlerde) modulun geri kalani
    calisabilir, sadece bu fonksiyon cagrildiginda ImportError alinir.
    ltfj_atc_notes_cleanup._uygulama_al ile AYNI uygulamayi (tek firebase_
    admin app) paylasir - iki modul de ayni Firebase projesine bagli."""
    import firebase_admin
    from firebase_admin import credentials

    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()
    if not sa_json:
        raise PushGonderimHatasi("FIREBASE_SERVICE_ACCOUNT tanımlı değil.")
    database_url = os.environ.get("FIREBASE_DATABASE_URL", "").strip()
    if not database_url:
        raise PushGonderimHatasi("FIREBASE_DATABASE_URL tanımlı değil.")

    try:
        sa_bilgisi = json.loads(sa_json)
    except json.JSONDecodeError as e:
        raise PushGonderimHatasi(f"FIREBASE_SERVICE_ACCOUNT geçerli JSON değil: {e}") from e

    if firebase_admin._apps:
        return firebase_admin.get_app()
    try:
        cred = credentials.Certificate(sa_bilgisi)
        return firebase_admin.initialize_app(cred, {"databaseURL": database_url})
    except Exception as e:
        raise PushGonderimHatasi(f"Firebase uygulaması başlatılamadı: {e}") from e


def _abonelikler_referansi():
    from firebase_admin import db

    _uygulama_al()
    return db.reference("push_abonelikler")


def govde_kur(baslik: str, govde: str, etiket: str | None = None, url: str = "./") -> str:
    """sw.js'nin ('push' olayı) beklediği JSON gövdesini üretir - alan
    adları (baslik/govde/etiket/url) sw.js ile TAM eşleşmeli."""
    return json.dumps(
        {"baslik": baslik, "govde": govde, "etiket": etiket, "url": url},
        ensure_ascii=False)


def gonder(baslik: str, govde: str, vapid_subject: str,
          etiket: str | None = None, url: str = "./") -> dict:
    """Tum abonelere gonderir, {"abone", "gonderildi", "silindi", "hata"}
    sayaclarini dondurur. TEK bir abonenin basarisiz olmasi digerlerini
    ENGELLEMEZ - her biri kendi try/except'i icinde. Gecersiz/iptal edilmis
    bir abonelik (404/410) Firebase'den fiilen SILINIR; diger hatalar (gecici
    ag sorunu vb.) sessizce atlanir, bir sonraki gonderimde tekrar denenir.

    "abone" KAYITLI abonelik sayisidir: 0 ise gonderilecek kimse yoktur -
    "abone var ama hepsi hata verdi" durumundan ayirt edilebilsin diye ayri
    tutulur (bkz. ltfj_bot._push_gonder_guvenli'nin log satiri)."""
    if not yapilandirilmis_mi():
        raise PushGonderimHatasi("Push yapılandırılmamış (VAPID/Firebase eksik).")

    from pywebpush import WebPushException, webpush

    ref = _abonelikler_referansi()
    try:
        abonelikler = ref.get() or {}
    except Exception as e:
        raise PushGonderimHatasi(f"Realtime Database okunamadı: {e}") from e

    vapid_private_key = os.environ["VAPID_PRIVATE_KEY"].strip()
    payload = govde_kur(baslik, govde, etiket, url)

    sonuc = {"abone": len(abonelikler), "gonderildi": 0, "silindi": 0, "hata": 0}
    for abonelik_id, abonelik in abonelikler.items():
        if not isinstance(abonelik, dict) or "endpoint" not in abonelik or "keys" not in abonelik:
            continue
        try:
            webpush(
                subscription_info={"endpoint": abonelik["endpoint"], "keys": abonelik["keys"]},
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims={"sub": vapid_subject},
            )
            sonuc["gonderildi"] += 1
        except WebPushException as e:
            durum = getattr(e.response, "status_code", None) if e.response is not None else None
            if durum in GECERSIZ_ABONELIK_KODLARI:
                try:
                    ref.child(abonelik_id).delete()
                    sonuc["silindi"] += 1
                except Exception:
                    sonuc["hata"] += 1
            else:
                sonuc["hata"] += 1
        except Exception:
            sonuc["hata"] += 1
    return sonuc
