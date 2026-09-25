#!/usr/bin/env python3
"""NOTAC yanıt sözleşmesini KEŞFET - tahmin etmek yerine servise sor.

NEDEN VAR: NOTAC'ın web arayüzü bir NOTAM'ın TAM orijinal metnini
gösteriyor ("B3455/26 NOTAMR B2849/26 / Q) ... / A) ... / E) ...").
Bizim sakladığımız `text` alanı ise yalnızca E) gövdesini taşıyor, yani
"hangi NOTAM'ın yerine geçti" bilgisi başka bir alanda olmalı. Ayrıca
henüz yürürlüğe girmemiş (upcoming) NOTAM'ları hangi sorgu parametresinin
getirdiğini de bilmiyoruz.

Bu script bunların ikisini de ÖLÇER. Çıktısına bakıp kodu ona göre
yazacağız - alan/parametre adı UYDURMUYORUZ.

ÇALIŞTIRMA: NOTAC_API_KEY tanımlı bir ortamda (GitHub Actions'taki
"NOTAM keşif" iş akışı). API anahtarı HİÇBİR satıra yazılmaz.
"""
import json
import os
import sys
from datetime import datetime, timezone

import ltfj_notam_client as client

LOCATION = os.environ.get("NOTAM_KESIF_LOCATION", "LTFJ")

# Ham metni tasiyabilecek alan adlari - degerleri BASILIR (NOTAM verisi
# kamuya aciktir). Diger alanlarin yalnizca ADI basilir.
METIN_ADAYLARI = ("text", "original_text", "raw_text", "full_text", "notam_text",
                  "raw", "original", "body", "message", "content", "icao_text")


def _baslik(s):
    print("\n" + "=" * 68)
    print(s)
    print("=" * 68)


def alanlari_dok(yanit: dict):
    _baslik("1) YANIT ZARFI VE ALAN ADLARI")
    print("zarf anahtarları:", sorted(yanit.keys()))
    print("count:", yanit.get("count"), "| next var mı:", bool(yanit.get("next")))
    sonuclar = yanit.get("results") or []
    if not sonuclar:
        print("!! results boş - başka bir şey ölçülemez")
        return None
    ilk = sonuclar[0]
    print(f"\nilk kaydın ({ilk.get('number')}) TÜM alanları:")
    for k in sorted(ilk):
        tip = type(ilk[k]).__name__
        print(f"   {k:24s} {tip}")
    return sonuclar


def orijinal_metni_ara(sonuclar: list):
    _baslik("2) 'NOTAMR/NOTAMC <numara>' HANGİ ALANDA?")
    bulundu = False
    for kayit in sonuclar:
        for alan, deger in kayit.items():
            if not isinstance(deger, str):
                continue
            if "NOTAMR" in deger.upper() or "NOTAMC" in deger.upper():
                print(f"  ✓ {kayit.get('number')} · alan={alan!r}")
                print(f"    {deger[:220]!r}")
                bulundu = True
    if not bulundu:
        print("  Hiçbir üst düzey metin alanında bulunamadı.")
        print("  Metin adayı alanların ilk kayıttaki içeriği:")
        ilk = sonuclar[0]
        for alan in METIN_ADAYLARI:
            if alan in ilk:
                print(f"    {alan}: {str(ilk[alan])[:160]!r}")
        print("\n  İç içe (nested) alanlarda arıyorum:")
        for kayit in sonuclar[:3]:
            for alan, deger in kayit.items():
                if isinstance(deger, (dict, list)):
                    ham = json.dumps(deger, ensure_ascii=False)
                    if "NOTAMR" in ham.upper() or "NOTAMC" in ham.upper():
                        print(f"    ✓ {kayit.get('number')} · {alan}: {ham[:220]}")
                        bulundu = True
        if not bulundu:
            print("    yok")


def secenekleri_dok():
    _baslik("3) OPTIONS /notam/ - DESTEKLENEN SÜZGEÇLER")
    try:
        opt = client.secenekleri_getir()
    except Exception as e:
        print("  alınamadı:", e.__class__.__name__, e)
        return
    print(json.dumps(opt, ensure_ascii=False, indent=1)[:2500])


def yaklasanlari_dene():
    """Yaklasan NOTAM'lar hangi parametreyle geliyor? Aday parametreleri
    TEK TEK deneyip DONEN KAYIT SAYISINI ve icinde gelecek tarihli kayit
    olup olmadigini raporluyoruz. Bilinmeyen parametreyi DRF genelde
    yok sayar - o zaman sayi degismez, yani 'ise yaramadi' demektir."""
    _baslik("4) YAKLAŞAN (upcoming) NOTAM'LAR HANGİ PARAMETREYLE?")
    simdi = datetime.now(timezone.utc)

    def olc(etiket, ek):
        try:
            y = client.notam_getir(LOCATION, ek_parametreler=ek)
        except Exception as e:
            print(f"  {etiket:34s} HATA: {e.__class__.__name__}")
            return
        sonuclar = y.get("results") or []
        ileri = 0
        for k in sonuclar:
            try:
                if datetime.fromisoformat(
                        (k.get("effective_start") or "").replace("Z", "+00:00")) > simdi:
                    ileri += 1
            except ValueError:
                pass
        print(f"  {etiket:34s} count={y.get('count')!s:>5}  sayfa={len(sonuclar):>3}  "
              f"gelecek tarihli={ileri}")

    # ARTIK TAHMIN LISTESI DEGIL: OPTIONS yaniti suzgeci kendisi tarif
    # etti (?status=active|upcoming|expired|any, varsayilan active) ve
    # ?status=upcoming olculdu - 6 kayit, hepsi gelecek tarihli.
    olc("(parametresiz - mevcut davranış)", None)
    for durum in ("active", "upcoming", "expired", "any"):
        olc(f"status={durum}", {"status": durum})


def detay_ucunu_dene(sonuclar: list):
    """LISTE ucunda bulunamadi. DRF'de liste ve DETAY serileştiricileri
    genelde FARKLIDIR: detay ucu cogu zaman daha fazla alan doner.
    NOTAC'in web arayuzu tam orijinal metni gosterdigine gore metin bir
    yerde var - once burada ariyoruz."""
    _baslik("5) DETAY UCU: /notam/{id}/ DAHA FAZLA ALAN DONUYOR MU?")
    ilk = sonuclar[0]
    nid = ilk.get("id")
    if not nid:
        print("  id yok, denenemiyor"); return
    try:
        detay = client._istek_at(f"{client.BASE_URL}/notam/{nid}/", None,
                                 client.VARSAYILAN_TIMEOUT)
    except Exception as e:
        print(f"  detay ucu alinamadi: {e.__class__.__name__}: {e}")
        return
    if not isinstance(detay, dict):
        print("  beklenmedik yanit tipi:", type(detay).__name__); return
    yeni_alanlar = sorted(set(detay) - set(ilk))
    print(f"  {ilk.get('number')} · detayda FAZLADAN olan alanlar: {yeni_alanlar or 'yok'}")
    for alan in yeni_alanlar:
        print(f"    {alan}: {str(detay[alan])[:220]!r}")
    ham = json.dumps(detay, ensure_ascii=False)
    print("  detayda NOTAMR/NOTAMC geciyor mu:",
          "EVET" if ("NOTAMR" in ham.upper() or "NOTAMC" in ham.upper()) else "hayir")
    if "NOTAMR" in ham.upper() or "NOTAMC" in ham.upper():
        for alan, deger in detay.items():
            if isinstance(deger, str) and ("NOTAMR" in deger.upper() or "NOTAMC" in deger.upper()):
                print(f"    ✓ alan={alan!r}: {deger[:220]!r}")


def durum_sozlugunu_dok():
    """Yaklasan kayitlarin "status" alani hangi degeri tasiyor? Kod bu
    degere BAGLI OLMASIN diye zaten sarta koymadik (bkz.
    ltfj_notam.notam_veri_yaz), ama bilmek dogrulamayi kolaylastirir."""
    _baslik("6) status ALANI HANGI DEGERLERI ALIYOR?")
    for durum in (None, "active", "upcoming", "expired", "any"):
        ek = {"status": durum} if durum else None
        try:
            y = client.notam_getir(LOCATION, ek_parametreler=ek)
        except Exception as e:
            print(f"  status={durum!s:10s} HATA: {e.__class__.__name__}")
            continue
        degerler = sorted({(k.get("status") or "?") for k in (y.get("results") or [])})
        tipler = sorted({(k.get("notam_type") or "?") for k in (y.get("results") or [])})
        print(f"  status={durum!s:10s} count={y.get('count')!s:>5} "
              f"status degerleri={degerler} notam_type={tipler}")


def main():
    if not client.api_anahtari_var_mi():
        print("NOTAC_API_KEY tanımlı değil - keşif yapılamaz.", file=sys.stderr)
        return 1
    print(f"NOTAC keşif · location={LOCATION} · {datetime.now(timezone.utc):%Y-%m-%d %H:%MZ}")
    yanit = client.notam_getir(LOCATION)
    sonuclar = alanlari_dok(yanit)
    if sonuclar:
        orijinal_metni_ara(sonuclar)
    secenekleri_dok()
    yaklasanlari_dene()
    if sonuclar:
        detay_ucunu_dene(sonuclar)
    durum_sozlugunu_dok()
    print("\nBitti. Çıktıyı olduğu gibi paylaş - koda buna göre karar vereceğiz.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
