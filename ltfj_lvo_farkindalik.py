#!/usr/bin/env python3
"""LVO REFERENCE panelindeki "Farkındalık Notları" alt bölümü için GAYRİ
RESMİ, hedge'li ("olabilir") ipucu metinleri üretir.

Bu modul RVR/CAT II/LVTO/LVO gibi bir SONUÇ üretmez - sadece OKUNAN
değerlerin (METAR'ın kendi görüş/tavanı, TAF'in kendi tavan verisi, ATC'nin
manuel girdiği AWOS RVR) dokümanın (TL.007, bkz. ltfj_lvo_referans.py) kendi
eşik değerleriyle karşılaştırmasını, "LVO şartları oluşabilir. Resmî bir
tespit değildir." hedge'iyle metne döker. "LVO aktif", "CAT II
kullanılabilir", "LVTO yapılabilir", "şu pist kullanılmalı" gibi kesin bir
operasyonel ifade HİÇBİR ZAMAN üretilmez (bkz. tests/test_ltfj_sayfa_lvo.py
YASAK_KARAR_KALIPLARI - bu modül eklendikten sonra da geçerli/geçiyor).

METAR'dan RVR TÜRETİLMEZ - burada METAR'ın SADECE kendi görüş/tavan
(bulut taban yüksekliği) değeri kullanılır. RVR sadece ATC'nin manuel AWOS
girişinden (gerçek ölçüm) okunur; o veri Firebase'de (yalnızca istemci
tarafında) yaşadığı için buradaki rvr_notu() sunucu tarafında ÇAĞRILMAZ -
web sayfasındaki LVO script'i (ltfj_sayfa.py) AYNI mantığı, bu modülün
export ettiği RVR_ESIKLERI ile JavaScript'te tekrar uygular (embedded JSON
üzerinden, tek kaynaktan - ltfj_lvo_referans.RVR_ESIKLERI)."""

from ltfj_lvo_referans import RVR_ESIKLERI

# madde 6.2.a / 6.3.1.a - CAT II bulut tabanı aralığının (100-200 ft) üst
# sınırı; METAR/TAF tavanı bu değerin altındaysa farkındalık notu üretilir.
CEILING_FARKINDALIK_ESIGI_FT = 200

_HEDGE = "LVO şartları oluşabilir. Resmî bir tespit değildir."


def metar_tavan_notu(cozum: dict | None) -> str | None:
    """cozum: ltfj_analiz.metar_coz() çıktısı. Tavan eşiğin altındaysa bir
    not döner, değilse (veya tavan/METAR yoksa) None döner."""
    if not cozum:
        return None
    tavan = cozum.get("tavan")
    if tavan is None or tavan >= CEILING_FARKINDALIK_ESIGI_FT:
        return None
    return (f"METAR tavanı {tavan} ft — düşük (CAT II bulut tabanı aralığı "
            f"100–200 ft, madde 6.2.a/6.3.1.a). {_HEDGE}")


def taf_tavan_notu(en_dusuk_tavan_ft: int | None) -> str | None:
    """en_dusuk_tavan_ft: TAF metninde gecen TÜM BKN/OVC/VV katmanlarının en
    düşüğü (metar_coz()'un zaten hesapladığı 'tavan' alanı, TAF metnine
    uygulanmış hali - TAF'in TEK bir donem/BECMG/TEMPO ayrimi yapilmadan
    tüm geçerlilik süresi için en kötü/en düşük tavanı)."""
    if en_dusuk_tavan_ft is None or en_dusuk_tavan_ft >= CEILING_FARKINDALIK_ESIGI_FT:
        return None
    return (f"TAF döneminde öngörülen en düşük tavan {en_dusuk_tavan_ft} ft — düşük. "
            f"{_HEDGE}")


def rvr_notu(pist: str, pozisyon: str, deger_m: int) -> str | None:
    """Manuel AWOS RVR değerini (gerçek ölçüm) dokümanın kendi eşikleriyle
    (RVR_ESIKLERI) karşılaştırır; en derin (en küçük esik_altinda_m) geçilen
    eşiği bulur. Hiçbir eşik geçilmemişse None döner."""
    gecilen = [e for e in RVR_ESIKLERI if deger_m < e["esik_altinda_m"]]
    if not gecilen:
        return None
    en_derin = min(gecilen, key=lambda e: e["esik_altinda_m"])
    return (f"{pist} {pozisyon} AWOS RVR {deger_m} m — dokümanın "
            f"{en_derin['esik_altinda_m']} m eşiğinin ({en_derin['safha']}) altında. "
            f"{_HEDGE}")
