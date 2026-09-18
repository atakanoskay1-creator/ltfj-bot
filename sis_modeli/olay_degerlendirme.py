#!/usr/bin/env python3
"""Olay (event) duzeyinde degerlendirme - satir duzeyinde metriklerin (AP,
Brier, ...) EK'i, YERINE GECMEZ.

NEDEN GEREKLI: bir sis olayina yaklasan onset-aday satirlarin HEPSI (UFUK_SAAT
icindeki her 30 dakikalik adim) ayni olay icin AYRI AYRI "hedef=True" tasir.
Yani TEK bir olay, satir-duzeyinde AP/Brier hesabina birden fazla kez (en
fazla UFUK_SAAT*60/ADIM_DK kez) pozitif olarak girer - model olayi yalnizca
son 30 dakikada "koklese" bile bu, satir-duzeyinde skoru buyutebilir. Gun
bazli blok bootstrap (degerlendir.blok_guven_araligi) bu durumun VARYANSINI
duzeltir ama NOKTA TAHMININDEKI cift-sayimi degil - event-level degerlendirme
bu bosluk icin ayrica gerekli (bkz. arastirma raporu Bolum 10).

Bagimlilik yok: saf standart kutuphane.
"""

import random
from collections import defaultdict
from datetime import timedelta


def bagimsiz_olaylar(kayitlar: list, etiket: str = "sis",
                     bosluk_saat: float = 3.0) -> list:
    """Ardisik POZITIF (etiket=1) zaman damgalarini `bosluk_saat`'ten BUYUK
    aralarla ayirarak bagimsiz olaylara gruplar.

    Bu, sis_modeli disinda (tavan feasibility olcumunde) daha once kullanilan
    "epizot sayma" mantigidir - burada kalici, test edilebilir bir fonksiyon
    olarak formalize edildi. `kayitlar`, hedef.hazirla()'nin urettigi HAM
    (onset filtresi UYGULANMAMIS) tam kayit kumesi olmalidir - cunku olay
    tanimi POZITIF anlari gruplandirir, onset_adaylari() ise pozitifleri
    zaten disariya atmis olur."""
    pozitifler = sorted(r["dt"] for r in kayitlar if r.get(etiket))
    if not pozitifler:
        return []
    esik = timedelta(hours=bosluk_saat)
    olaylar = [[pozitifler[0], pozitifler[0]]]
    for t in pozitifler[1:]:
        if t - olaylar[-1][1] > esik:
            olaylar.append([t, t])
        else:
            olaylar[-1][1] = t
    return [{"baslangic": a, "bitis": b, "gun": a.strftime("%Y-%m-%d")}
            for a, b in olaylar]


def olay_temsilci_satirlari(kayitlar: list, olaylar: list, etiket: str = "sis",
                            ufuk_saat: float = 3.0, adim_dk: int = 30) -> list:
    """Her olay icin, baslangicindan HEMEN ONCEKI onset-aday (etiket=0)
    satirini bulur - "olay basina TEK tahmin" ilkesinin karsiligi.

    En yakin (30 dk once) adimdan baslar, bulunamazsa bir onceki adima
    gecer (archive bosluklarina karsi); ufuk_saat'i asarsa (yani modelin
    zaten gorebilecegi pencerenin disinda kalirsa) temsilci=None doner -
    boyle bir olay event-level degerlendirmeye KATILMAZ (uydurma satir
    yaratilmaz)."""
    yer = {r["dt"]: r for r in kayitlar}
    adim_sayisi = int(round(ufuk_saat * 60 / adim_dk))
    cikti = []
    for olay in olaylar:
        temsilci = None
        for k in range(1, adim_sayisi + 1):
            aday = yer.get(olay["baslangic"] - timedelta(minutes=adim_dk * k))
            if aday is not None and not aday.get(etiket):
                temsilci = aday
                break
        cikti.append({**olay, "temsilci": temsilci})
    return cikti


def _tahmin_al(tahminler_map: dict, satir: dict) -> float:
    return tahminler_map.get(satir["dt"], 0.0)


def olay_bazli_esik_tablosu(temsilciler: list, tahminler_map: dict,
                            esikler=(0.05, 0.10, 0.20, 0.40)) -> list:
    """Yalnizca temsilcisi bulunan olaylar uzerinden event-level DUYARLILIK
    (recall): esigi gecen olay orani. temsilcisiz olaylar (ufuk disinda
    kalanlar) PAYDAYA GIRMEZ - bunlari "kacirilmis" saymak yanlis olurdu,
    cunku model o anda zaten gozlem yapamazdi."""
    gecerli = [t for t in temsilciler if t["temsilci"] is not None]
    toplam = len(gecerli)
    cikti = []
    for e in esikler:
        yakalanan = sum(1 for t in gecerli
                        if _tahmin_al(tahminler_map, t["temsilci"]) >= e)
        cikti.append({"esik": e, "toplam_olay": toplam, "yakalanan": yakalanan,
                      "duyarlilik": yakalanan / toplam if toplam else 0.0})
    return cikti


def olay_bazli_guven_araligi(temsilciler: list, tahminler_map: dict,
                             esik: float, tekrar: int = 200,
                             tohum: int = 0) -> tuple:
    """Event-level duyarliligin GUN (olayin baslangic gunu) bazinda blok
    bootstrap %5-95 araligi - satir bazli degil, OLAY bazli yeniden
    orneklenir (her olay zaten tek bir temsilci satirla temsil edildigi
    icin burada ayrica gun-ici cift sayim riski yok, ama gunler arasi
    bağımlılık -aynı sinoptik durumun birden fazla güne yayılması-
    yine de mümkün, bu yüzden gün bloklanıyor)."""
    gecerli = [t for t in temsilciler if t["temsilci"] is not None]
    if not gecerli:
        return (0.0, 0.0)
    gunler = defaultdict(list)
    for t in gecerli:
        gunler[t["gun"]].append(t)
    anahtarlar = list(gunler)
    rastgele = random.Random(tohum)

    sonuclar = []
    for _ in range(tekrar):
        ornek = []
        for _ in anahtarlar:
            ornek.extend(gunler[rastgele.choice(anahtarlar)])
        if not ornek:
            sonuclar.append(0.0)
            continue
        yakalanan = sum(1 for t in ornek
                        if _tahmin_al(tahminler_map, t["temsilci"]) >= esik)
        sonuclar.append(yakalanan / len(ornek))
    sonuclar.sort()
    return (sonuclar[int(0.05 * len(sonuclar))],
            sonuclar[min(int(0.95 * len(sonuclar)), len(sonuclar) - 1)])


def olay_ozet(kayitlar: list, etiket: str = "sis", bosluk_saat: float = 3.0) -> dict:
    """Hizli teshis: kac bagimsiz olay, kac ayri gun, yil basina ortalama."""
    olaylar = bagimsiz_olaylar(kayitlar, etiket, bosluk_saat)
    yillar = {o["baslangic"].year for o in olaylar}
    return {
        "olay_sayisi": len(olaylar),
        "ayri_gun_sayisi": len({o["gun"] for o in olaylar}),
        "yil_sayisi": len(yillar),
        "olay_yil_basina": len(olaylar) / len(yillar) if yillar else 0.0,
    }
