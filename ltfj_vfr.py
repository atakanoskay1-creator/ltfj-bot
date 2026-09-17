#!/usr/bin/env python3
"""En son METAR/SPECI'nin görüş/tavan değerlerini ICAO Annex 2 (Rules of the
Air), Bölüm 3, Table 3-1'in FL100 (3.050 m / 10.000 ft AMSL) altı satırıyla
karşılaştırır - Sabiha Gökçen CTR'si (surface'ten itibaren kontrollü hava
sahası, hiçbir irtifada Class G) için o satırın rakamları tüm irtifalarda
aynıdır (5 km görüş, 1.500 m yatay/300 m dikey buluttan uzaklık); ayrıca
CTR içinde iniş/kalkış ve gece VFR için ayrı bir bulut tabanı (ceiling)
şartı (≥ 1.500 ft) vardır.

METAR sadece yer seviyesi görüş ve tavan (bulut taban yüksekliği) bildirir,
"buluttan uzaklık" (1.500 m/300 ft, seyir sırasında bulutlara yaklaşma
mesafesi) METAR'dan OKUNAMAZ - bu yüzden değerlendirme sadece görüş ve
tavan eşikleriyle sınırlıdır.

NOT: Bu modül LVO/AWOS/ATIS panelindeki "otomatik karar üretme yasağı"
kapsamında DEĞİLDİR - o yasak kullanıcının açıkça talep ettiği LVO/CAT II/
RVR paneline özeldi. Burada METAR görüş+tavanının VFR eşikleriyle
karşılaştırılması ve sonucun yeşil/kırmızı gösterilmesi kullanıcının açıkça
istediği bir özelliktir; ayrıca havacılıkta VFR/IFR ayrımının METAR'dan
doğrudan okunması standart, rutin bir sınıflandırmadır (bkz. projede zaten
var olan "Sis oluşum göstergesi" gibi METAR tabanlı diğer göstergeler)."""

VFR_GORUS_ESIGI_M = 5000
VFR_TAVAN_ESIGI_FT = 1500


def vfr_degerlendir(cozum: dict) -> dict:
    """cozum: ltfj_analiz.metar_coz() çıktısı (gorus: metre|None,
    tavan: ft|None - ilk BKN/OVC/VV katmanı, metar_coz() zaten hesaplar).

    Döner: {"vfr": True|False|None, "sebepler": [str, ...]}
    vfr=None -> METAR'da görüş bilgisi yok, değerlendirme yapılamıyor
    (sebepler bu durumu açıklayan tek bir metin içerir)."""
    gorus = cozum.get("gorus")
    tavan = cozum.get("tavan")

    if gorus is None:
        return {"vfr": None,
                "sebepler": ["METAR'da görüş bilgisi yok — değerlendirme yapılamıyor."]}

    sebepler = []
    if gorus < VFR_GORUS_ESIGI_M:
        sebepler.append(
            f"Görüş {gorus} m, VFR eşiği olan {VFR_GORUS_ESIGI_M} m'nin altında.")
    if tavan is not None and tavan < VFR_TAVAN_ESIGI_FT:
        sebepler.append(
            f"Tavan {tavan} ft, VFR eşiği olan {VFR_TAVAN_ESIGI_FT} ft'in altında.")

    return {"vfr": len(sebepler) == 0, "sebepler": sebepler}
