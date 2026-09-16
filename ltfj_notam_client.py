#!/usr/bin/env python3
"""
NOTAC (https://notac.aero) API - ham HTTP istemci katmani.

BILEREK KUCUK TUTULDU: bu modul SADECE HTTP istegini atar ve ham JSON'u
oldugu gibi dondurur. NOTAC'in gercek yanit alan (field) isimlerini
BILMIYORUZ - kullaniciyla birlikte dogrulanana kadar hicbir alan adini
TAHMIN ETMIYORUZ. Ham yaniti sozluge (dict) donusturme/model esleme
(notam_number, effective_start vb.) BURADA YAPILMAZ - gercek bir NOTAC
yaniti gozlemlenip alan isimleri dogrulandiktan SONRA ayri bir modulde
(notam_service.py / notam_model.py, henuz yazilmadi) yapilacak.

VERI KAYNAGI: NOTAC'in kendi belgelemesine gore (https://notac.aero/api/
authentication/) alttaki veri ABD FAA NOTAM Management System'den geliyor.
NOTAC resmi bir operasyonel NOTAM/PIB kaynagi DEGILDIR - bilgi amaclidir.
LTFJ (Turkiye) icin kapsam/güncellik garantisi yoktur; bu, gercek bir yanit
gozlemlenene kadar acik bir risk olarak kalir.

AUTHENTICATION: "Authorization: Bearer <NOTAC_API_KEY>" - token bicimi
"lb_" + 40 hex karakter, self-service olusturulamiyor, NOTAC'tan talep
edilir. API anahtari:
  - asla kaynak koduna yazilmaz (ortam degiskeninden okunur)
  - asla log'a yazilmaz (Authorization header'i hicbir print/log satirinda
    gorunmez)
  - asla JavaScript/HTML'e gonderilmez (bu istemci sadece Python
    tarafinda, GitHub Actions/lokal calistirmada kullanilir)
"""
import os

import requests

BASE_URL = "https://notac.aero/api/v1"
VARSAYILAN_TIMEOUT = 15


class NotamHatasi(Exception):
    """Bu modulun tum hatalarinin atasi."""


class NotamYetkiHatasi(NotamHatasi):
    """KALICI: API anahtari tanimli degil / gecersiz / suresi dolmus (401).
    Retry ile cozulmez - anahtarin kendisi duzeltilmeli."""


class NotamAgHatasi(NotamHatasi):
    """GECICI: NOTAC'a ulasilamadi (timeout/baglanti) ya da sunucu tarafi
    hata (5xx). Bir sonraki calistirmada tekrar denenebilir."""


class NotamAyiklamaHatasi(NotamHatasi):
    """KALICI: yanit JSON degil ya da beklenmeyen HTTP durumu."""


def api_anahtari_var_mi() -> bool:
    """NOTAM ozelligi butunuyle opsiyonel: anahtar tanimli degilse bu
    modulu cagiran taraf ozelligi sessizce atlayabilir (bkz. ltfj_bot.py -
    METAR/TAF/RVR analizi NOTAM'dan bagimsiz calismaya devam etmeli)."""
    return bool(os.environ.get("NOTAC_API_KEY", "").strip())


def _api_anahtari() -> str:
    anahtar = os.environ.get("NOTAC_API_KEY", "").strip()
    if not anahtar:
        raise NotamYetkiHatasi("NOTAC_API_KEY tanımlı değil.")
    return anahtar


def notam_getir(location: str = "LTFJ", timeout: int = VARSAYILAN_TIMEOUT) -> dict:
    """Verilen lokasyon icin NOTAC'in HAM (parse edilmemis) JSON yanitini
    dondurur. Alan isimlerini burada yorumlamiyoruz - cagiran taraf ham
    sozlugu alir.

    Endpoint ve authentication semasi kullanicidan dogrulanmis sekilde
    alindi (https://notac.aero/api/authentication/):
      GET {BASE_URL}/notam/?location=<ICAO>
      Authorization: Bearer <NOTAC_API_KEY>
    Yanit govdesinin sekli (sayfalama, alan adlari, NOTAM listesi anahtari
    vb.) HENUZ dogrulanmadi - bu fonksiyon bilerek "ham JSON dondur, model
    esleme yapma" sinirinda duruyor."""
    anahtar = _api_anahtari()
    try:
        r = requests.get(
            f"{BASE_URL}/notam/",
            params={"location": location},
            headers={"Authorization": f"Bearer {anahtar}", "Accept": "application/json"},
            timeout=timeout,
        )
    except requests.RequestException as e:
        # Hata mesaji requests'in kendi exception metnini icerir; bu Authorization
        # header'ini ICERMEZ (requests boyle bir bilgiyi exception'a gomm ez).
        raise NotamAgHatasi(f"NOTAC'a ulaşılamadı: {e.__class__.__name__}") from e

    if r.status_code == 401:
        # Govde (ör. {"detail":"...","code":"token_revoked"}) hassas bilgi
        # tasimiyor (NOTAC'in kendi dokumantasyonuna gore "insan okumasi
        # icin yazilir") - ama yine de asiri uzun/beklenmeyen govdeyi
        # kirpiyoruz.
        raise NotamYetkiHatasi(
            f"NOTAC yetkilendirme reddetti (401): {r.text[:200]!r}"
        )
    if r.status_code >= 400:
        raise NotamAyiklamaHatasi(
            f"NOTAC beklenmeyen HTTP durumu ({r.status_code}): {r.text[:200]!r}"
        )

    try:
        return r.json()
    except ValueError as e:
        raise NotamAyiklamaHatasi(f"NOTAC yanıtı geçerli JSON değil: {e}") from e
