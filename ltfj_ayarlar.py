#!/usr/bin/env python3
"""
ayarlar.json yukleyicisi.

Dosya yoksa ya da bozuksa varsayilanlarla devam eder - bot bir ayar dosyasi
yuzunden durmaz. Eksik anahtarlar varsayilandan tamamlanir, yani ayarlar.json'a
sadece degistirmek istedigin satiri yazman yeter.
"""

import json
from pathlib import Path
from zoneinfo import ZoneInfo

KLASOR = Path(__file__).resolve().parent
DOSYA = KLASOR / "ayarlar.json"

# LTFJ Turkiye'de, "yerel saat" her zaman Europe/Istanbul demektir. Bunu
# python'un `datetime.astimezone()` (argumansiz) cagrisina birakmak,
# sonucu calisma ortaminin (OS/konteyner) TZ ayarina baglar - sessiz
# saatler gibi karar mantigi bu sekilde ortam degisince fark edilmeden
# kayabilir. Tum modul bu SABIT uzerinden "yerel" hesaplasin diye burada.
YEREL_TZ = ZoneInfo("Europe/Istanbul")

# Veri akisinin KESILDIGI sayilan sure. ltfj_bot bununla Telegram alarmi
# atiyor, ltfj_sayfa ayni esikle basliktaki durum gostergesini kirmiziya
# cekiyor - BURADA duruyor ki ikisi sessizce ayrismasin (sayfa "canli"
# derken Telegram "kesinti" diyemesin).
SESSIZLIK_SAAT = 6

# Bir GOZLEMIN tazeligi. METAR :20/:50'de yayinlanir (30 dk kadans) ve
# rasat.mgm.gov.tr'ye ortalama 5 dk icinde duser -> beklenen azami yas
# ~35 dk. Esik bunun IKI KATI: bir raporu kacirmak normal, ikisini
# kacirmak degil. Ayni "2x kadans" mantigi NOTAM_BAYAT_MS'te de kullanildi.
GOZLEM_TAZE_DK = 70

# "TAM ZAMANINDA" esigi. LTFJ METAR kadansi :20/:50 (30 dk) + MGM'in
# ~5 dakikalik yayin gecikmesi; yani NORMAL calisan bir sistemde en
# yasli gozlem ~35 dakikaliktir. 35-70 dk arasi "bir gozlem kacti"
# demektir ve bu aralik eskiden "CANLI" kutusunun icindeydi - olcum
# aninda METAR 49 dakikaliktir ve rozet CANLI diyordu.
# GOZLEM_TAZE_DK (70) bunun IKI KATI olarak duruyor: 70'i de asmak
# "iki gozlem kacti" demek ve orasi GECIKMELI.
GOZLEM_BEKLENEN_DK = 35

# LTFJ pist ekseni GERCEK yonleri (AIP AD 2.12, AIRAC AMDT 07/26). Hem
# ltfj_analiz.py (yan_ruzgar - Telegram ozet mesajindaki crosswind) hem de
# ltfj_pist.py (PISTLER - pist basi bazinda bas/kuyruk/yan bilesenleri) bu
# TEK degerden besleniyor. Ikisi ayri ayri "64.10"/"244.12" hardcode etseydi,
# gelecekte bir AIRAC guncellemesinde biri degisip digeri unutulursa iki
# hesap sessizce birbirinden sapardi.
PIST_EKSENI_06 = 64.10
PIST_EKSENI_24 = 244.12

VARSAYILAN = {
    "istasyon": "LTFJ",
    "esikler": {
        "gorus_dusuk": 1500,
        "gorus_cok_dusuk": 800,
        "tavan_dusuk": 500,
        "tavan_cok_dusuk": 200,
        "ruzgar_kuvvetli": 25,
        "hamle_kuvvetli": 30,
        "yan_ruzgar_dikkat": 15,
    },
    "bildirim": {
        "sabit_mesaj": True,
        "rutin_metar": "gizle",          # gizle | sessiz | gonder
        "bildir": {
            "speci": True,
            "taf": True,
            "duzeltme": True,
            "dikkat": True,
            "renk_degisimi": True,
        },
        "sessiz_saatler": {"aktif": False, "baslangic": "23:00", "bitis": "07:00"},
    },
    "mesaj": {"bicim": "kisa", "ham_bulten": True, "claude_yorum": True},
    "web_sayfasi": True,
    "atc_paneli": True,
    "notam": {
        # NOTAC entegrasyonu tamamen opsiyonel - NOTAC_API_KEY ortam
        # degiskeni tanimli degilse zaten sessizce devre disi kalir
        # (bkz. ltfj_notam_client.api_anahtari_var_mi()); "aktif": False
        # anahtar tanimli olsa bile ozelligi kapatmak icin ayrica bir anahtar.
        "aktif": True,
        # NOTAM METAR kadar sik degismiyor - varsayilan olarak 6 saatte bir
        # senkronize ediyoruz (API kredisini gereksiz tuketmemek icin).
        "senkron_araligi_saat": 6,
        "location": "LTFJ",
    },
    "atc_notes": {
        # ATC Notes (durumsal farkindalik notlari) - okuma/yazma DOGRUDAN
        # tarayicidan Firebase Realtime Database'e yapilir (bkz. ltfj_sayfa.
        # py), Python tarafi SADECE 48 saati dolmus notlari fiilen silen
        # arka plan temizligini yapar (bkz. ltfj_atc_notes_cleanup.py).
        # FIREBASE_SERVICE_ACCOUNT/FIREBASE_DATABASE_URL ortam degiskenleri
        # tanimli degilse temizlik sessizce atlanir - bu METAR/NOTAM akisini
        # hicbir sekilde etkilemez.
        "aktif": True,
        # Firebase Realtime Database REST API'sini DOGRUDAN fetch() ile
        # kullaniyoruz (bkz. ltfj_sayfa.py) - ayri bir SDK/CDN scripti
        # gerekmiyor, sayfanin geri kalaniyla ayni sade fetch() deseni.
        # Bu URL Firebase'in KENDI tasarimi geregi GIZLI DEGIL - istemci
        # tarafinda (index.html) aynen gorunecek, guvenlik Firebase
        # Realtime Database Rules ile saglanir (bkz. firebase-rules.json),
        # URL'nin "gizlenmesiyle" degil. Bos birakilirsa (varsayilan) web
        # sayfasindaki ATC Notes bolumu "yapilandirilmamis" mesaji gosterir,
        # METAR/NOTAM bolumlerini etkilemez.
        "database_url": "",
    },
    "push": {
        # Web Push (tarayici bildirimleri, Telegram'a EK) - SPECI, TAF,
        # duzeltme (AMD/COR), renk kotulesmesi ve yeni NOTAM icin. Abonelik
        # kayitlari atc_notes ile AYNI Firebase Realtime Database'de,
        # "push_abonelikler" path'inde tutulur (ayri bir database_url
        # gerekmez). VAPID_PRIVATE_KEY ortam degiskeni tanimli degilse
        # (ya da pywebpush kurulu degilse) tum ozellik sessizce devre disi
        # kalir - METAR/TAF/NOTAM akisini hicbir sekilde etkilemez (bkz.
        # ltfj_push.py).
        "aktif": True,
        # VAPID public key GIZLI DEGIL - istemci tarafinda (index.html)
        # applicationServerKey olarak aynen gorunur; guvenlik ozel anahtarin
        # (VAPID_PRIVATE_KEY, GH secret, asla buraya yazilmaz) gizliliginden
        # gelir. Ikisi TEK SEFERDE, birlikte uretildi - biri degisirse
        # digeri de degismeli, aksi halde var olan abonelikler gecersiz kalir.
        "vapid_public_key": "BMdotDlhyTA4r0JaNfv3l530aWh5n57WKqxEh2XroHWhxdbcbqp_aBLMIGOUN2FTdyjd_9t1W1N3J73SDJko0KI",
        # Push servislerine "bu gonderen kim" diye kendini tanitmak icin bir
        # iletisim adresi (RFC 8292) - kotuye kullanim bulunursa push servisi
        # bu adresten ulasir. Gercek bir adresle degistirilmeli.
        "vapid_subject": "mailto:ornek@ornek.com",
    },
}


def _birlestir(varsayilan: dict, gelen: dict) -> dict:
    """Ic ice sozlukleri varsayilanla tamamlar. '_' ile baslayan anahtarlar
    aciklama satiridir, yok sayilir."""
    sonuc = dict(varsayilan)
    for k, v in (gelen or {}).items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and isinstance(sonuc.get(k), dict):
            sonuc[k] = _birlestir(sonuc[k], v)
        else:
            sonuc[k] = v
    return sonuc


def yukle() -> dict:
    try:
        gelen = json.loads(DOSYA.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(VARSAYILAN)
    return _birlestir(VARSAYILAN, gelen)


AYARLAR = yukle()


def esik(ad: str):
    return AYARLAR["esikler"].get(ad, VARSAYILAN["esikler"].get(ad))


def ayar(*yol, varsayilan=None):
    """ayar('bildirim', 'rutin_metar') -> 'gizle'"""
    d = AYARLAR
    for k in yol:
        if not isinstance(d, dict) or k not in d:
            return varsayilan
        d = d[k]
    return d
