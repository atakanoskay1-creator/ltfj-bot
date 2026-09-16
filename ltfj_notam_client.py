#!/usr/bin/env python3
"""
NOTAC (https://notac.aero) API - ham HTTP istemci katmani.

BILEREK KUCUK TUTULDU: bu modul SADECE HTTP istegini atar ve ham JSON'u
oldugu gibi dondurur. Alan (field) isimlerini burada YORUMLAMIYORUZ/
ESLEMIYORUZ - model esleme ltfj_notam.py'de, GERCEK bir NOTAC yaniti
gozlemlenip alan adlari kullanıcıyla dogrulandiktan SONRA yapildi.

DOGRULANMIS SOZLESME (2026-09-16, kullanicinin GitHub Actions'tan attigi
gercek test istegiyle):
  GET {BASE_URL}/notam/?location=<ICAO>
  Authorization: Bearer <NOTAC_API_KEY>
  -> 200: {"count": int, "next": <url|null>, "previous": <url|null>,
           "results": [ {...NOTAM...}, ... ]}
  (standart DRF sayfalama zarfi - "next" TAM bir URL'dir, sayfa numarasi
  degil.)
  LTFJ icin gercekten veri donuyor (test isteginde 11 aktif NOTAM) - bu,
  daha once bilinmeyen "LTFJ/Turkiye kapsami var mi" sorusunu cozdu.

VERI KAYNAGI: NOTAC'in kendi belgelemesine gore (https://notac.aero/api/
authentication/) alttaki veri ABD FAA NOTAM Management System'den geliyor.
NOTAC resmi bir operasyonel NOTAM/PIB kaynagi DEGILDIR - bilgi amaclidir.

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


def _istek_at(url: str, params: dict | None, timeout: int) -> dict:
    """Ortak HTTP + hata siniflandirma katmani. notam_getir() (ilk sayfa)
    ve sayfa_getir() (DRF'nin verdigi TAM "next" URL'si) BUNU paylasir."""
    anahtar = _api_anahtari()
    try:
        r = requests.get(
            url,
            params=params,
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


def notam_getir(location: str = "LTFJ", timeout: int = VARSAYILAN_TIMEOUT) -> dict:
    """Verilen lokasyon icin NOTAC'in HAM (parse edilmemis) ILK SAYFA JSON
    yanitini dondurur: {"count", "next", "previous", "results": [...]}.
    Sonraki sayfalar icin sayfa_getir(yanit["next"]) kullanilir."""
    return _istek_at(f"{BASE_URL}/notam/", {"location": location}, timeout)


def sayfa_getir(sayfa_url: str, timeout: int = VARSAYILAN_TIMEOUT) -> dict:
    """DRF sayfalama zarfindaki "next" (ya da "previous") alaninda gelen
    TAM URL'yi cagirir - bu URL zaten sorgu parametrelerini (location,
    page vb.) icerir, ayrica params gecirmiyoruz."""
    return _istek_at(sayfa_url, None, timeout)
