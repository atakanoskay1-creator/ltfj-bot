#!/usr/bin/env python3
"""
LTFJ (Sabiha Gokcen) METAR / SPECI / TAF  -  rasat.mgm.gov.tr

Sayfa Next.js. Veri HTML icindeki <script id="__NEXT_DATA__"> etiketinde JSON olarak
geliyor. Biz o JSON'u cekip ayikliyoruz. Ekstra kutuphane yok, sadece requests.

Kurulum:  pip install requests
Calistir: python ltfj_rasat.py
"""

import json
import re
import sys
import time
from datetime import datetime, timezone

import requests

from ltfj_ayarlar import YEREL_TZ

BASE = "https://rasat.mgm.gov.tr/result"
ICAO = "LTFJ"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Referer": "https://rasat.mgm.gov.tr/",
}

# obsType: 1 = METAR/SPECI grubu, 2 = TAF grubu.  hours: 0 = son (anlik) rapor
# Ornek: /result?stations=LTFJ&obsType=1&obsType=2&hours=0
EK_PARAMS = [("obsType", "1"), ("obsType", "2"), ("hours", "0")]

NEXT_DATA = re.compile(
    r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S | re.I
)

# MGM sunucusu ara sira takiliyor. Tek denemede pes etmeyelim.
DENEME = 3          # toplam deneme sayisi
BEKLE = 5           # denemeler arasi saniye (her turda katlanir: 5, 10)

# Rapor tipinden sonra gelebilecek isaretler
DUZELTMELER = ("AMD", "COR", "RTD")


class RasatHatasi(Exception):
    """Bu modulun tum hatalarinin atasi."""


class AgHatasi(RasatHatasi):
    """GECICI: MGM'ye ulasilamadi. Bir sonraki turda tekrar denenir."""


class AyiklamaHatasi(RasatHatasi):
    """KALICI: sayfa yapisi degismis. Insan mudahalesi gerekir."""


def _sayfayi_getir(params, timeout, deneme=DENEME):
    """MGM sayfasini getirir, GECICI hatalarda (timeout/baglanti/5xx) birkac
    kez tekrar dener. KALICI istemci hatalarinda (4xx) DENEMIYOR - ayni
    istek tekrar ayni sonucu verir, DENEME dongusunun bekleme surelerini
    (5, 10 sn) bosuna tuketmenin anlami yok.

    deneme: toplam deneme sayisi. Canli akis varsayilani (DENEME) kullanir;
    gozlem arsivi geri doldurmasi tek deneme ister (is akisi 5 dk ile
    sinirli, sonraki kosu 24 saatlik pencerede zaten yeniden dener)."""
    son_hata = None
    for i in range(1, deneme + 1):
        try:
            r = requests.get(BASE, params=params, headers=HEADERS,
                             timeout=(10, timeout))   # (baglanti, okuma)
            if 400 <= r.status_code < 500:
                raise AgHatasi(
                    f"MGM {r.status_code} döndürdü (kalıcı istemci hatası, "
                    f"tekrar denenmedi): {r.reason}"
                )
            r.raise_for_status()   # 5xx -> HTTPError, asagida retry edilir
            return r
        except requests.RequestException as e:
            son_hata = e
            if i < deneme:
                bekle = BEKLE * i
                print(f"[uyari] MGM yanit vermedi ({i}/{deneme}): {e.__class__.__name__}"
                      f" - {bekle} sn sonra tekrar deneniyor", file=sys.stderr)
                time.sleep(bekle)
    raise AgHatasi(f"{deneme} denemede ulasilamadi: {son_hata}") from son_hata


def raporlari_cek(icao: str = ICAO, timeout: int = 30, saat: int = 0,
                  deneme: int = DENEME) -> list[dict]:
    """
    Istasyonun raporlarini dondurur. Her eleman:
      {'tip': 'METAR', 'zaman': datetime(UTC), 'metin': 'METAR LTFJ ...', ...}
    En yeni ilk sirada.

    saat=0 (varsayilan, canli akis): yalnizca son raporlar (`dataLast`).
    saat>0: son `saat` saatin raporlari (`data`) - yalnizca gozlem arsivi
    geri doldurmasi kullanir; bildirim/sayfa akisina GIRMEZ. Alan secimi
    salt okunur MGM kesfiyle (PR #99) olculdu: hours=0 -> dataLast,
    hours=3/24 -> data (dataLast None).
    """
    params = [("stations", icao)] + EK_PARAMS[:-1] + [("hours", str(saat))]
    r = _sayfayi_getir(params, timeout, deneme)

    m = NEXT_DATA.search(r.text)
    if not m:
        raise AyiklamaHatasi(
            "__NEXT_DATA__ bulunamadi - MGM sayfa yapisini degistirmis olabilir."
        )

    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise AyiklamaHatasi(f"__NEXT_DATA__ JSON olarak okunamadi: {e}") from e

    if "--debug" in sys.argv:
        with open("next_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        pp = data.get("props", {}).get("pageProps", {})
        print("[debug] istenen URL :", r.url)
        print("[debug] pageProps   :", list(pp.keys()))
        print("[debug] query       :", data.get("query"))
        print("[debug] selectedObj :", pp.get("selectedObj"))
        print("[debug] response    :", len(pp.get("response") or []), "kayit")
        print("[debug] next_data.json yazildi\n")

    return raporlari_ayikla(data, icao, saat)


def raporlari_ayikla(data: dict, icao: str = ICAO, saat: int = 0) -> list[dict]:
    """__NEXT_DATA__ sozlugunden rapor listesini cikarir (ag YOK).

    Ayri fonksiyon, cunku kayitli bir MGM yanitini (ör. kesif artifact'i)
    ayni kodla yeniden oynatabilmek gerekiyor.

    Mevcut anahtarlar (id/tip/duzeltme/zaman/metin) canli akisin
    sozlesmesidir ve DEGISMEZ. Ek olarak MGM'nin ham alanlari tasinir
    (zaman_ham, metin_ham, mgm_status, mgm_status_aciklama, mgm_type,
    mgm_type_aciklama) - yalnizca gozlem arsivinin surum katmani okur."""
    try:
        response = data["props"]["pageProps"].get("response") or []
    except (KeyError, TypeError, AttributeError) as e:
        raise AyiklamaHatasi(f"Beklenen JSON alanlari yok: {e}") from e

    alan = "dataLast" if saat == 0 else "data"
    out = []
    for blok in response:
        if (blok.get("istInfo") or {}).get("icao", "").upper() != icao.upper():
            continue
        kayitlar = blok.get(alan)
        if saat != 0 and not isinstance(kayitlar, list):
            # Geri doldurma yanitinin yapisi kesifte olculenden farkli:
            # baska alana/hours degerine OTOMATIK gecis yok.
            raise AyiklamaHatasi(
                f"hours={saat} yanitinda '{alan}' listesi yok "
                f"({type(kayitlar).__name__})")
        for kayit in (kayitlar or []):
            metin = " ".join((kayit.get("observationText") or "").split())
            if not metin:
                continue
            tokenlar = metin.split()
            # "TAF AMD LTFJ ..." / "METAR COR LTFJ ..." -> duzeltme isareti
            duzeltme = next((t for t in tokenlar[1:3] if t in DUZELTMELER), None)
            out.append({
                "id": kayit.get("id"),                     # MGM'nin kayit numarasi
                "tip": tokenlar[0].upper(),                # METAR / SPECI / TAF
                "duzeltme": duzeltme,                      # AMD / COR / None
                "zaman": _zaman(kayit.get("observationTimeNormal")),
                "metin": metin,
                # MGM'nin ham alanlari - OLDUGU GIBI (yorum yok).
                "zaman_ham": kayit.get("observationTimeNormal"),
                "metin_ham": kayit.get("observationText"),
                "mgm_status": kayit.get("observationStatus"),
                "mgm_status_aciklama": kayit.get("observationStatusExplanation"),
                "mgm_type": kayit.get("observationType"),
                "mgm_type_aciklama": kayit.get("observationTypeExplanation"),
            })
    out.sort(key=lambda d: d["zaman"] or datetime.min.replace(tzinfo=timezone.utc),
             reverse=True)
    return out


def _zaman(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def taf_bicimle(taf: str) -> str:
    """TAF'i degisim gruplarindan bolerek okunakli yazar."""
    return re.sub(r"\s(?=(FM\d|BECMG|TEMPO|PROB\d))", "\n    ", taf)


def main():
    try:
        raporlar = raporlari_cek()
    except AgHatasi as e:
        sys.exit(f"Siteye ulasilamadi: {e}")
    except AyiklamaHatasi as e:
        sys.exit(f"Ayiklama hatasi: {e}")

    if not raporlar:
        print(f"{ICAO} icin rapor donmedi.")
        return

    for r in raporlar:
        if r["zaman"]:
            yerel = r["zaman"].astimezone(YEREL_TZ)
            damga = f'{r["zaman"]:%d.%m %H:%M}Z  ({yerel:%H:%M} yerel)'
        else:
            damga = "zaman yok"
        baslik = r["tip"] + (f' {r["duzeltme"]}' if r.get("duzeltme") else "")
        print(f'== {baslik} == {damga}')
        print(taf_bicimle(r["metin"]) if r["tip"] == "TAF" else r["metin"])
        print()


if __name__ == "__main__":
    main()