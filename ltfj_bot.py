#!/usr/bin/env python3
"""
LTFJ METAR/TAF Telegram bildirim botu.

Bir kere calisir, isini yapar, cikar. GitHub Actions / systemd timer tetikler.

BILDIRIM MANTIGI
  Sohbette SABITLENMIS tek bir "su an" mesaji durur; her raporda yerinde
  guncellenir, telefon otmez. Ayri bildirim SADECE onemli durumda gider:
  SPECI, TAF, duzeltme (AMD/COR), DIKKAT esigi, renk durumu degisimi.
  Boylece gunde ~55 bildirim yerine ~3-5 bildirim olur.
  Davranis ayarlar.json'dan degistirilebilir.

Dosyalar (hepsi ayni klasorde):
  ltfj_rasat.py   veri cekme        ltfj_analiz.py  METAR cozumleme
  ltfj_pist.py    havacilik hesabi  ltfj_ayarlar.py ayar yukleyici
  ltfj_sayfa.py   web sayfasi       ayarlar.json    ayarlar
  .env            gizli anahtarlar  ltfj_state.json gecmis (otomatik)

Cikis kodlari:
  0 = yolunda ya da gecici ag sorunu     1 = mudahale gerektiren kalici sorun

Bayraklar:
  --hepsi   state'i yok sayip su anki tum raporlari gonderir (elle test)
"""

import html
import json
import os
import re
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import requests

import ltfj_atc_notes_cleanup
import ltfj_notam
import ltfj_notam_client as notam_client
from ltfj_analiz import cozum_dokumu, fark_bul, metar_coz, ozet_satiri, uyarilar
from ltfj_ayarlar import AYARLAR, YEREL_TZ, ayar
from ltfj_pist import RENK_SIMGE, havacilik_notlari
from ltfj_rasat import AgHatasi, AyiklamaHatasi, raporlari_cek

# ----------------------------------------------------------------- ayarlar ---
ICAO = AYARLAR.get("istasyon", "LTFJ")
KLASOR = Path(__file__).resolve().parent
STATE = KLASOR / "ltfj_state.json"
ENV = KLASOR / ".env"

ILK_CALISTIRMADA_GONDER = True
GECMIS_LIMIT = 200
OLCUM_GECMIS_LIMIT = 300     # web sayfasindaki trend grafikleri icin (~6 gun)
NOTAM_GECMIS_LIMIT = 500     # state_birlestir.py::NOTAM_GECMIS_LIMIT ile ayni

SESSIZLIK_SAAT = 6
UYARI_ARALIGI_SAAT = 12

CLAUDE_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_URL = "https://api.anthropic.com/v1/messages"
TELEGRAM = "https://api.telegram.org/bot{token}/{yontem}"

SIMGE = {"METAR": "🛬", "SPECI": "⚠️", "TAF": "📅"}

ORNEK_ENV = """\
TELEGRAM_BOT_TOKEN=123456:AA...
TELEGRAM_CHAT_ID=987654321
# Asagidaki satir istege bagli - silersen Claude yorumu yapilmaz
ANTHROPIC_API_KEY=sk-ant-...
# Asagidaki satir istege bagli - silersen NOTAM ozelligi (bkz. ltfj_notam.py)
# sessizce devre disi kalir, METAR/TAF/RVR analizi hicbir sekilde etkilenmez
NOTAC_API_KEY=lb_...
"""


# -------------------------------------------------------------------- env ---
def env_yukle():
    if not ENV.exists():
        return
    for satir in ENV.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        k, v = satir.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def gerekli(ad):
    deger = os.environ.get(ad, "").strip()
    if not deger:
        sys.exit(
            f"HATA: {ad} tanimli degil.\n"
            f"{ENV} dosyasi olustur (ya da GitHub Secrets'a ekle), icine sunu yaz:\n\n"
            f"{ORNEK_ENV}"
        )
    return deger


# ------------------------------------------------------------------ state ---
def state_oku() -> dict:
    bos = {"gonderilen": [], "ilk_calisma": True, "son_metar": "",
           "son_uyari": None, "durum_mesaj_id": None, "son_renk": None,
           "son_veri_zamani": None, "olcum_gecmisi": [], "yorum_onbellegi": {},
           "notam_gecmisi": {}, "notam_son_senkron": None}
    if not STATE.exists():
        return bos
    try:
        d = json.loads(STATE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return bos
    for k, v in bos.items():
        d.setdefault(k, v if k != "ilk_calisma" else False)
    return d


def state_yaz(state: dict):
    state["gonderilen"] = state["gonderilen"][-GECMIS_LIMIT:]
    notam_gecmisi = state.get("notam_gecmisi") or {}
    if len(notam_gecmisi) > NOTAM_GECMIS_LIMIT:
        siralanmis = sorted(notam_gecmisi.items(), key=lambda kv: kv[1].get("last_seen") or "")
        state["notam_gecmisi"] = dict(siralanmis[-NOTAM_GECMIS_LIMIT:])
    state["guncelleme"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ notam ---
def _notam_senkron_gerekli_mi(state: dict) -> bool:
    """NOTAM senkronizasyonu METAR'dan BAGIMSIZ, seyrek araliklarla calisir -
    NOTAC API kredisini gereksiz tuketmemek icin (bkz. ayarlar.json::notam.
    senkron_araligi_saat). Anahtar tanimli degilse ya da ozellik kapaliysa
    sessizce atlanir; bu METAR akisini hicbir sekilde etkilemez."""
    if not ayar("notam", "aktif", varsayilan=True):
        return False
    if not notam_client.api_anahtari_var_mi():
        return False
    son = state.get("notam_son_senkron")
    if not son:
        return True
    try:
        son_dt = datetime.fromisoformat(son)
    except ValueError:
        return True
    araligi_saat = ayar("notam", "senkron_araligi_saat", varsayilan=6)
    return datetime.now(timezone.utc) - son_dt >= timedelta(hours=araligi_saat)


def notam_senkronize(state: dict):
    """NOTAC'tan aktif NOTAM'lari cekip yerel gecmise isler. Basarisizlik
    (ag/yetki/ayiklama) METAR analizini bloke ETMEZ ve daha once cekilmis
    NOTAM gecmisini SILMEZ - sadece bu turdaki senkronizasyon atlanir."""
    if not _notam_senkron_gerekli_mi(state):
        return
    location = ayar("notam", "location", varsayilan="LTFJ")
    try:
        aktif = ltfj_notam.aktif_notamlari_getir(location)
    except ltfj_notam.NotamServisHatasi as e:
        print(f"[uyarı] NOTAM senkronizasyonu başarısız: {e}", file=sys.stderr)
        return
    # Ayni "simdi" hem gecmisteki last_seen'e hem notam_son_senkron'a yazilir -
    # web katmani "su an aktif" kaydini last_seen == notam_son_senkron
    # esitligiyle belirliyor (bkz. ltfj_notam.notam_veri_yaz), iki ayri
    # datetime.now() cagrisi bu esitligi kirar.
    simdi = datetime.now(timezone.utc).isoformat(timespec="seconds")
    eski_gecmis = state.get("notam_gecmisi") or {}
    eski_idler = set(eski_gecmis)
    yeni_gecmis = ltfj_notam.gecmisi_guncelle(eski_gecmis, aktif, simdi)
    state["notam_gecmisi"] = yeni_gecmis
    state["notam_son_senkron"] = simdi
    print(f"  NOTAM senkronize edildi: {len(aktif)} aktif NOTAM ({location}).")

    # Ilk senkronizasyonda (eski_gecmis bos) TUM aktif NOTAM'lar "yeni"
    # sayilir - bu durumda push'a bogulmamak icin HICBIRI bildirilmez
    # (ltfj_bot'un METAR tarafindaki "ilk_calisma" ile ayni ilke).
    if eski_gecmis:
        for nid in set(yeni_gecmis) - eski_idler:
            notam_push_gonder(yeni_gecmis[nid])


def atc_notes_temizligini_calistir() -> int | None:
    """ATC Notes'un 48 saati dolmus kayitlarini Firebase'den fiilen siler.
    Notlarin kendisi (olusturma/okuma) DOGRUDAN tarayicidan Firebase'e
    yazilir/okunur - bu fonksiyon METAR/NOTAM'dan TAMAMEN bagimsizdir,
    ikisinden biri basarisiz olsa da digerini hicbir sekilde etkilemez.
    FIREBASE_SERVICE_ACCOUNT/FIREBASE_DATABASE_URL tanimli degilse ya da
    ozellik ayarlar.json'dan kapatilmissa None doner (sessizce atlanir)."""
    if not ayar("atc_notes", "aktif", varsayilan=True):
        return None
    if not ltfj_atc_notes_cleanup.yapilandirilmis_mi():
        return None
    return ltfj_atc_notes_cleanup.expired_atc_notes_cleanup()


def anahtar(rapor: dict) -> str:
    if rapor.get("id"):
        return f"id:{rapor['id']}"
    z = rapor["zaman"].isoformat() if rapor.get("zaman") else "?"
    return f"{rapor['tip']}:{z}"


def olcum_gecmisini_guncelle(state: dict, raporlar: list):
    """METAR/SPECI degerlerini state'e ekler - web sayfasindaki trend
    grafikleri bu gecmisten beslenir. Ayni zaman damgali kayit tekrarlanmaz.

    cig_noktasi, istatistiksel sis olasiligi kartinin spread egilimini
    hesaplayabilmesi icin tutuluyor (bkz. ltfj_sis_olasilik). Eski kayitlarda
    bulunmaz; o durumda egilim ozelligi devre disi kalir ve model onsuz
    calisir - olculdu, etkisi ihmal edilebilir."""
    mevcut = {g["zaman"] for g in state.get("olcum_gecmisi", [])}
    yeni = []
    for r in raporlar:
        if r["tip"] not in ("METAR", "SPECI") or not r.get("zaman"):
            continue
        z = r["zaman"].isoformat(timespec="seconds")
        if z in mevcut:
            continue
        d = metar_coz(r["metin"])
        yeni.append({
            "zaman": z,
            "ruzgar_hiz": d["ruzgar_hiz"],
            "tavan": d["tavan"],
            "qnh": d["qnh"],
            "sicaklik": d["sicaklik"],
            "cig_noktasi": d["cig_noktasi"],
        })
    if not yeni:
        return
    gecmis = state.get("olcum_gecmisi", []) + yeni
    gecmis.sort(key=lambda g: g["zaman"])
    state["olcum_gecmisi"] = gecmis[-OLCUM_GECMIS_LIMIT:]


# ----------------------------------------------------------------- claude ---
SISTEM_ISTEMI = (
    "Sen havacılık meteorolojisi raporlarını sade Türkçeye çeviren bir asistansın. "
    "Rapor HER ZAMAN LTFJ — İstanbul Sabiha Gökçen Havalimanı içindir; başka hiçbir "
    "şehir, havalimanı veya bölge adı yazma. Sadece sana verilen verilerden konuş: "
    "veride olmayan bir bilgiyi tahmin etme, ekleme, yuvarlama. Emin olmadığın bir şey "
    "varsa o satırı kısa tut. Sayıları verildiği gibi kullan. Şablonu harfiyen uygula, "
    "başlık ve etiketleri değiştirme, giriş veya kapanış cümlesi kurma. "
    "SEN BİR AÇIKLAMA KATMANISIN, KARAR VERİCİ DEĞİLSİN: pist ataması yapma, hangi "
    "pistin 'kullanılması gerektiğini' söyleme, kesin gecikme/iptal tahmini üretme, "
    "ATC talimatı ya da clearance önerisi verme, resmî operasyonel minimum yorumu "
    "yapma. Sana verilen gözlemlenmiş ve hesaplanmış veriyi sade dille anlat; "
    "operasyonel karar insana (pilot/ATC) aittir."
)

METAR_SABLONU = """\
Aşağıdaki gözlem raporunu şu şablona göre anlat. Tam olarak 4 satır yaz, her satır \
etiketle başlasın, her satır tek cümle olsun:

Rüzgâr: <yönü ve şiddeti günlük dille; kuvvetli veya yan rüzgâr varsa belirt>
Görüş: <ne kadar görünüyor, uçuş için rahat mı>
Gökyüzü: <bulut durumu ve yağış; tavan alçaksa belirt>
Uçuşa etkisi: <verideki kısıtlayıcı unsurları (düşük görüş, kuvvetli rüzgâr, \
fırtına vb.) yansıt; kesin gecikme/iptal tahmini üretme, ATC/pilot kararı değil>

Havacılık bilmeyen birine anlatıyorsun: "BKN024" gibi kodları kullanma, "2400 fitte \
çok bulutlu" gibi yaz. Fit yerine yaklaşık metre de ekleyebilirsin.

HAM RAPOR:
{ham}

ÇÖZÜMLENMİŞ VERİ (doğru kaynak budur):
{cozum}"""

TAF_SABLONU = """\
Aşağıdaki hava tahmini raporunu Türkçeye ÇEVİR. SADECE ÇEVİRİ yap - kendi \
yorumunu, değerlendirmeni ya da risk/önem tespitini KATMA; hangisinin \
"dikkat çekici" olduğuna sen karar verme, raporda ne varsa onu oldugu gibi \
sade dille aktar. Şu şablona göre, en fazla 4 satır:

Genel: <tahmin döneminin ana hava durumu, tek cümle - raporda yazani anlat>
- <saat aralığı UTC> <o dönemde beklenen hava, tek cümle>
- <varsa sonraki dönem>

Saatler raporda olduğu gibi UTC kalsın, yerel saate çevirme. TEMPO "geçici", \
BECMG "kademeli geçiş", PROB30 "ihtimal %30" demektir. Havacılık kodlarını \
çözerek yaz ama "dikkat", "önemli", "riskli" gibi kendi degerlendirmeni \
eklemeden, sirf ne bildirildiyse onu belirt.

HAM RAPOR:
{ham}"""

YANLIS_YERLER = (
    "izmir", "ankara", "antalya", "adana", "bursa", "trabzon", "dalaman", "bodrum",
    "konya", "kayseri", "gaziantep", "diyarbakir", "erzurum", "samsun", "van",
    "malatya", "denizli", "eskisehir", "sivas", "hatay", "mugla", "canakkale",
    "balikesir", "elazig", "kars", "sanliurfa", "mardin", "batman", "nevsehir",
    "isparta", "tekirdag", "ataturk havalimani", "istanbul havalimani",
)
TR_HARF = str.maketrans("ıİşŞğĞüÜöÖçÇâÂî", "iisSgGuUoOcCaAi")


def _yer_hatasi(metin: str) -> str | None:
    duz = metin.translate(TR_HARF).lower()
    return next((y for y in YANLIS_YERLER if y in duz), None)


def claude_yorum(rapor, cozum, notlar=None) -> str | None:
    if not ayar("mesaj", "claude_yorum", varsayilan=True):
        return None
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return None

    if rapor["tip"] == "TAF":
        istem = TAF_SABLONU.format(ham=rapor["metin"])
    else:
        veri = cozum_dokumu(cozum)
        if notlar:
            pistler = [p for p in notlar["pistler"] if not p.startswith("(")]
            if pistler:
                veri += "\nPist bileşenleri:\n  " + "\n  ".join(pistler)
            if notlar["ws"]:
                veri += "\nRüzgâr kesmesi: " + ", ".join(notlar["ws"])
            if notlar["rvr"]:
                veri += "\nPist görüş menzili: " + "; ".join(notlar["rvr"])
        istem = METAR_SABLONU.format(ham=rapor["metin"], cozum=veri)

    try:
        r = requests.post(
            CLAUDE_URL,
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": CLAUDE_MODEL, "max_tokens": 500, "temperature": 0,
                  "system": SISTEM_ISTEMI,
                  "messages": [{"role": "user", "content": istem}]},
            timeout=30,
        )
        r.raise_for_status()
        yorum = "".join(p.get("text", "")
                        for p in r.json().get("content", [])).strip()
    except requests.RequestException as e:
        print(f"[uyarı] Claude yorumu alınamadı: {e}", file=sys.stderr)
        return None
    except (ValueError, TypeError, AttributeError, KeyError) as e:
        # r.json() gecersiz JSON donebilir (ValueError/JSONDecodeError) ya da
        # gecerli JSON olup beklenen sekilde olmayabilir (orn. "content": null
        # -> TypeError, bir eleman dict degil -> AttributeError). Her iki
        # durumda da Claude yorumu YOK sayilir, calisma cokmemeli (bkz. main()
        # akisindaki durum_mesajini_guncelle() cagrisi).
        print(f"[uyarı] Claude yanıtı beklenmeyen biçimde ({e!r}), atlandı.",
              file=sys.stderr)
        return None

    if not yorum:
        return None
    hatali = _yer_hatasi(yorum)
    if hatali:
        print(f"[uyarı] Yorumda alakasız yer adı ('{hatali}'), atlandı.",
              file=sys.stderr)
        return None
    return yorum


YORUM_ONBELLEK_LIMIT = 4


def _yorum_getir(state: dict, rapor: dict, cozum, notlar=None) -> str | None:
    """claude_yorum sonucunu ham rapor metnine gore onbellekler.

    durum_mesajini_guncelle() HER calistirmada (yeni rapor olmasa bile)
    sabitlenmis mesaji yeniden kuruyor; onbellek olmadan degismeyen bir
    METAR bile her ~15 dakikada bir Claude'a yeniden soruluyordu - Claude
    cagrisi calistirmanin ~17 saniyesini yiyordu. Ayni METAR ayni calistirma
    icinde (bildirim + durum mesaji) iki kez de sorulabiliyordu. Ayni ham
    metin -> ayni cozum/notlar -> ayni istem oldugundan metne gore
    onbellekleme guvenli. Basarisiz/filtrelenmis (None) sonuclar
    onbelleklenmez ki bir sonraki calistirmada tekrar denensin."""
    onbellek = state.setdefault("yorum_onbellegi", {})
    metin = rapor["metin"]
    if metin in onbellek:
        return onbellek[metin]

    yorum = claude_yorum(rapor, cozum, notlar)
    if yorum is not None:
        onbellek[metin] = yorum
        fazla = len(onbellek) - YORUM_ONBELLEK_LIMIT
        if fazla > 0:
            for eski in list(onbellek)[:fazla]:
                del onbellek[eski]
    return yorum


ETIKET = re.compile(r"^(Rüzgâr|Görüş|Gökyüzü|Uçuşa etkisi|Genel|Dikkat)\s*:\s*(.+)$")


def _yorumu_bicimle(yorum: str) -> str:
    satirlar = []
    for satir in yorum.splitlines():
        satir = satir.strip()
        if not satir:
            continue
        kacis = html.escape(satir)
        m = ETIKET.match(kacis)
        if m:
            satirlar.append(f"<b>{m.group(1)}:</b> {m.group(2)}")
        elif kacis.startswith("-"):
            satirlar.append("•" + kacis[1:])
        else:
            satirlar.append(kacis)
    return "\n".join(satirlar)


# --------------------------------------------------------------- telegram ---
def _tg(token: str, yontem: str, **veri):
    r = requests.post(TELEGRAM.format(token=token, yontem=yontem),
                      json=veri, timeout=20)
    cevap = r.json() if r.content else {}
    if not cevap.get("ok"):
        raise RuntimeError(f"Telegram {yontem} reddetti: {cevap.get('description', r.text)}")
    return cevap.get("result")


def telegram_gonder(token, chat_id, metin, sessiz=False) -> int | None:
    sonuc = _tg(token, "sendMessage", chat_id=chat_id, text=metin,
                parse_mode="HTML", disable_web_page_preview=True,
                disable_notification=sessiz)
    return (sonuc or {}).get("message_id")


def telegram_duzenle(token, chat_id, mesaj_id, metin) -> bool:
    """Var olan mesaji yerinde gunceller. Icerik ayniysa Telegram hata doner,
    bu bir sorun degil - sessizce True sayiyoruz."""
    try:
        _tg(token, "editMessageText", chat_id=chat_id, message_id=mesaj_id,
            text=metin, parse_mode="HTML", disable_web_page_preview=True)
        return True
    except RuntimeError as e:
        if "not modified" in str(e):
            return True
        print(f"[uyarı] Durum mesajı güncellenemedi: {e}", file=sys.stderr)
        return False


def telegram_sabitle(token, chat_id, mesaj_id):
    try:
        _tg(token, "pinChatMessage", chat_id=chat_id, message_id=mesaj_id,
            disable_notification=True)
    except RuntimeError as e:
        print(f"[uyarı] Mesaj sabitlenemedi: {e}", file=sys.stderr)


# ------------------------------------------------------------- bildirim ---
def _sessiz_saatte_mi(zaman: datetime) -> bool:
    s = ayar("bildirim", "sessiz_saatler", varsayilan={}) or {}
    if not s.get("aktif"):
        return False
    try:
        bas = time.fromisoformat(s.get("baslangic", "23:00"))
        bit = time.fromisoformat(s.get("bitis", "07:00"))
    except ValueError:
        return False
    simdi = zaman.astimezone(YEREL_TZ).time()
    return (bas <= simdi or simdi < bit) if bas > bit else (bas <= simdi < bit)


# Renk durumlari kotuden iyiye siralamasi. BLU/WHT "iyi bant" sayilir.
RENK_SIRA = {"BLU": 0, "WHT": 1, "GRN": 2, "YLO": 3, "AMB": 4, "RED": 5}
ONEMLI_BANT = 2          # GRN ve asagisi


def renk_onemli_mi(eski: str | None, yeni: str | None) -> bool:
    """Renk degisimi bildirim hak ediyor mu?

    BLU <-> WHT gibi iyi bant ici oynamalar bildirim uretmez - tavan 2400'den
    2600 ft'e ciktigi icin telefon otmesin. GRN ve asagisina girmek ya da
    oradan cikmak (duzelme) bildirim uretir.
    """
    if not eski or not yeni or eski == yeni:
        return False
    e, y = RENK_SIRA.get(eski, 0), RENK_SIRA.get(yeni, 0)
    return e >= ONEMLI_BANT or y >= ONEMLI_BANT


def renk_kotulesti_mi(eski: str | None, yeni: str | None) -> bool:
    """renk_onemli_mi'nin AKSINE tek yonlu: sadece KOTULESME (BLU/WHT/GRN'den
    YLO/AMB/RED'e) - Web Push icin. Telegram'daki 'renk_degisimi' iyilesmeyi
    de bildirir (kullanicinin bilmek isteyecegi bir sey); Web Push icin
    kullanici acikca 'renk kotulesmesi' istedi (duzelme degil) - bkz.
    ltfj_push.py, push_tetiklenmeli_mi()."""
    if not eski or not yeni or eski == yeni:
        return False
    e, y = RENK_SIRA.get(eski, 0), RENK_SIRA.get(yeni, 0)
    return y > e and y >= ONEMLI_BANT


def push_tetiklenmeli_mi(rapor: dict, renk_kotulesti: bool) -> bool:
    """Web Push SADECE dort durumda tetiklenir: SPECI, TAF, duzeltme
    (AMD/COR), renk KOTULESMESI - kullanicinin acikca istedigi kume (bkz.
    sohbet gecmisi). Rutin METAR ve 'dikkat' esigi (Telegram'daki 'dikkat'
    anahtari) BURADA YOK - kullanici bunlari istemedi, METAR zaten
    kontrolorun ekraninda."""
    b = ayar("bildirim", "bildir", varsayilan={}) or {}
    tip = rapor["tip"]
    return (
        (tip == "SPECI" and b.get("speci", True))
        or (tip == "TAF" and b.get("taf", True))
        or (bool(rapor.get("duzeltme")) and b.get("duzeltme", True))
        or (renk_kotulesti and b.get("renk_degisimi", True))
    )


def _push_baslik(rapor: dict) -> str:
    tip, duzeltme = rapor["tip"], rapor.get("duzeltme")
    simge = SIMGE.get(tip, "ℹ️")
    ad = f"{ICAO} {tip}"
    if duzeltme in ("AMD", "COR"):
        ad += " (DÜZELTME)" if duzeltme == "AMD" else " (DÜZELTİLMİŞ)"
        simge = "✏️"
    return f"{simge} {ad}"


def _push_govde(rapor: dict, cozum: dict | None, renk_bilgisi: tuple | None) -> str:
    """Telegram'daki AYNI kaynaktan (ozet_satiri/RENK_SIMGE) turer - iki
    kanal arasinda bilgi birbirinden FARKLILASMAZ, sadece bicim kisalir
    (push govdesi HTML degil duz metindir, OS bunu birkac satirla sinirlar)."""
    satirlar = []
    if rapor.get("zaman"):
        yerel = rapor["zaman"].astimezone(YEREL_TZ)
        satirlar.append(f'{rapor["zaman"]:%d.%m %H:%MZ} · {yerel:%H:%M} yerel')
    if rapor["tip"] == "TAF":
        satirlar.append("Yeni TAF yayınlandı")
    elif cozum:
        satirlar.append(ozet_satiri(cozum))
    if renk_bilgisi:
        kod, aciklama = renk_bilgisi
        satirlar.append(f'{RENK_SIMGE.get(kod, "")} {kod} — {aciklama}')
    return "\n".join(satirlar) if satirlar else rapor["metin"][:180]


def _push_gonder_guvenli(baslik: str, govde: str, etiket: str) -> None:
    """Basarisizligi (yapilandirilmamis, ag hatasi vb.) HER ZAMAN yutar -
    Web Push Telegram'a EK bir kanaldir, ana akisi asla bozamaz. METAR/
    SPECI/TAF/duzeltme/renk-kotulesmesi VE yeni NOTAM push'lari AYNI bu
    fonksiyondan gecer (bkz. push_bildirimi_gonder, notam_push_gonder)."""
    import ltfj_push

    if not ayar("push", "aktif", varsayilan=True):
        print(f"  push [{etiket}]: atlandı - ayarlar.json::push.aktif kapalı.")
        return
    if not ltfj_push.yapilandirilmis_mi():
        print(f"  push [{etiket}]: atlandı - FIREBASE_SERVICE_ACCOUNT/"
              "FIREBASE_DATABASE_URL/VAPID_PRIVATE_KEY eksik.")
        return
    try:
        sonuc = ltfj_push.gonder(
            baslik, govde,
            ayar("push", "vapid_subject", varsayilan="mailto:ornek@ornek.com"),
            etiket=etiket)
        # HER SONUC yazilir - "0 abone" ve "hepsi hata verdi" durumlari da.
        # Eskiden sadece gonderildi/silindi sifirdan buyukse yazilirdi; bu
        # yuzden "hic abone yok" ile "push hic denenmedi" loglarda AYIRT
        # EDILEMIYORDU (21.09.2026 TAF'inda tam olarak bu oldu).
        if not sonuc["abone"]:
            print(f"  push [{etiket}]: kayıtlı abone YOK - kimseye gönderilmedi.")
        else:
            print(f'  push [{etiket}]: {sonuc["abone"]} abone, '
                 f'{sonuc["gonderildi"]} gönderildi, '
                 f'{sonuc["silindi"]} geçersiz abonelik silindi, '
                 f'{sonuc["hata"]} hata.')
    except Exception as e:
        print(f"[uyarı] Push bildirimi gönderilemedi ({etiket}): {e}", file=sys.stderr)


def push_bildirimi_gonder(rapor: dict, cozum: dict | None, renk_bilgisi: tuple | None) -> None:
    _push_gonder_guvenli(_push_baslik(rapor), _push_govde(rapor, cozum, renk_bilgisi), rapor["tip"])


def _notam_push_govde(kayit: dict) -> str:
    satirlar = []
    if kayit.get("number"):
        satirlar.append(kayit["number"])
    if kayit.get("text"):
        satirlar.append(kayit["text"][:180])
    return "\n".join(satirlar) if satirlar else "Yeni bir NOTAM yayınlandı."


def notam_push_gonder(kayit: dict) -> None:
    _push_gonder_guvenli(f"📋 {ICAO} Yeni NOTAM", _notam_push_govde(kayit), "NOTAM")


def bildirim_karari(rapor, dikkat, renk_degisti) -> tuple[bool, bool]:
    """(ayri_mesaj_at, sessiz_olsun) dondurur."""
    b = ayar("bildirim", "bildir", varsayilan={}) or {}
    tip = rapor["tip"]

    onemli = (
        (tip == "SPECI" and b.get("speci", True))
        or (tip == "TAF" and b.get("taf", True))
        or (rapor.get("duzeltme") and b.get("duzeltme", True))
        or (dikkat and b.get("dikkat", True))
        or (renk_degisti and b.get("renk_degisimi", True))
    )
    if onemli:
        return True, _sessiz_saatte_mi(rapor.get("zaman") or datetime.now(timezone.utc))

    # Rutin METAR
    kip = ayar("bildirim", "rutin_metar", varsayilan="gizle")
    if kip == "gonder":
        return True, False
    if kip == "sessiz":
        return True, True
    return False, True          # gizle


# ---------------------------------------------------------------- mesaj ---
def baslik_kur(rapor, notlar) -> str:
    tip, duzeltme = rapor["tip"], rapor.get("duzeltme")
    simge = SIMGE.get(tip, "ℹ️")
    ad = f"{ICAO} {tip}"
    if duzeltme in ("AMD", "COR"):
        ad += " (DÜZELTME)" if duzeltme == "AMD" else " (DÜZELTİLMİŞ)"
        simge = "✏️"

    if rapor.get("zaman"):
        yerel = rapor["zaman"].astimezone(YEREL_TZ)
        damga = f'{rapor["zaman"]:%d.%m %H:%MZ} · {yerel:%H:%M} yerel'
    else:
        damga = ""

    renk = ""
    if notlar and notlar["renk"]:
        kod, aciklama = notlar["renk"]
        # Etiket ltfj_pist.RENK_ETIKETI'den geliyor (tek kaynak) - BLU/WHT/
        # GRN/YLO/AMB/RED resmi ICAO CAT I/II/III kategorisi ya da baska bir
        # resmi havacilik durumu DEGIL, botun kendi gorus/tavan bandina gore
        # hesapladigi bir onem seviyesi. Bu ibareyi burada ayrica sabit
        # metin olarak YAZMIYORUZ ki ltfj_sayfa.py/panel.html ile ayni
        # kaynaktan gelsin, aralarinda sessizce farklilasmasin.
        renk = f'  {RENK_SIMGE.get(kod, "")} <b>{kod}</b> <i>({notlar["renk_etiketi"]} — {aciklama})</i>'
    return f"{simge} <b>{html.escape(ad)}</b>  <i>{damga}</i>{renk}"


def mesaj_kur(rapor, state, onceki_metar="", uzun=None) -> str:
    if uzun is None:
        uzun = ayar("mesaj", "bicim", varsayilan="kisa") == "uzun"

    tip = rapor["tip"]
    cozum = metar_coz(rapor["metin"]) if tip in ("METAR", "SPECI") else None
    notlar = (havacilik_notlari(cozum, rapor["metin"], rapor.get("zaman"))
              if cozum else None)

    s = [baslik_kur(rapor, notlar)]

    if cozum:
        dikkat = uyarilar(cozum)
        if notlar["ws"]:
            dikkat.insert(0, "RÜZGÂR KESMESİ: " + ", ".join(notlar["ws"]))
        if dikkat:
            s += ["", "🔴 <b>DİKKAT</b> · " + html.escape(" · ".join(dikkat))]
        if notlar["prs"]:
            # "askıda" degil - bu METAR'a dayali bir HESAPLANAN gosterge,
            # PRS'yi fiilen durdurma/durdurmama karari ATC'nindir (AD 2.20 K).
            s += ["", "ℹ️ <b>PRS için kısıtlayıcı koşul (METAR'a göre)</b> · "
                  + html.escape(", ".join(notlar["prs"]))]

        farklar = fark_bul(onceki_metar, rapor["metin"])
        if farklar:
            s += ["", "<b>Değişim</b>"] + [f"• {html.escape(f)}" for f in farklar]

    yorum = _yorum_getir(state, rapor, cozum, notlar)
    if yorum:
        s += ["", _yorumu_bicimle(yorum)]
    elif cozum:
        s += ["", html.escape(ozet_satiri(cozum))]

    if notlar and (uzun or notlar["gorus_op"]):
        s += _havacilik_blogu(notlar, uzun)

    if uzun and ayar("mesaj", "ham_bulten", varsayilan=True):
        s += ["", f'<pre>{html.escape(rapor["metin"])}</pre>']

    return "\n".join(s)


def _havacilik_blogu(n: dict, uzun: bool) -> list[str]:
    s = []
    if uzun:
        pistler = [p for p in n["pistler"] if not p.startswith("(")]
        kaynak = next((p for p in n["pistler"] if p.startswith("(")), "")
        if pistler:
            s += ["", f"✈️ <b>Pist bileşenleri</b> <i>{html.escape(kaynak)}</i>"]
            s += [f"<code>{html.escape(p)}</code>" for p in pistler]
            if n["tercih"]:
                # ATC runway-in-use atamasi degil - sadece ruzgar bilesenlerine
                # gore HESAPLANMIS meteorolojik tercih (bkz. tercih_edilen_pist()).
                s.append(f'Meteorolojik baş rüzgârı tercihi: <b>{n["tercih"]}</b>')

    # Gorus operasyonu kisa bicimde de gosterilir - operasyonel olarak kritik
    if n["gorus_op"]:
        s += [""] + [f"👁 {html.escape(g)}" for g in n["gorus_op"]]

    if not uzun:
        return s

    ekler = []
    if n["rvr"]:
        ekler.append(("Pist görüş menzili", "; ".join(n["rvr"])))
    if n["son_hava"]:
        ekler.append(("Son bir saatte", ", ".join(n["son_hava"])))
    if n["trend"]:
        ekler.append(("Eğilim", n["trend"]))
    if n["sis"]:
        ekler.append(("🌫 Sis", n["sis"].split(":", 1)[-1].strip()))
    if ekler:
        s.append("")
        s += [f"<b>{html.escape(e)}</b> · {html.escape(i)}" for e, i in ekler]
    return s


def durum_mesaji_kur(raporlar: list, state: dict) -> str:
    """Sabitlenmis 'su an' mesaji - her raporda yerinde guncellenir."""
    metar = next((r for r in raporlar if r["tip"] in ("METAR", "SPECI")), None)
    taf = next((r for r in raporlar if r["tip"] == "TAF"), None)
    simdi = datetime.now(timezone.utc).astimezone(YEREL_TZ)

    s = [f"📍 <b>{ICAO} · şu an</b>"]

    if metar:
        s.append(mesaj_kur(metar, state, uzun=True))
    if taf:
        if taf.get("zaman"):
            yerel = taf["zaman"].astimezone(YEREL_TZ)
            damga = f'{taf["zaman"]:%d.%m %H:%MZ} · {yerel:%H:%M} yerel'
        else:
            damga = ""
        s += ["", f"📅 <b>TAF</b> <i>{damga}</i>"]
        yorum = _yorum_getir(state, taf, None, None)
        if yorum:
            s += ["", _yorumu_bicimle(yorum)]
        s += ["", f'<pre>{html.escape(taf["metin"])}</pre>']

    s += ["", f"<i>Son güncelleme: {simdi:%d.%m %H:%M} yerel</i>"]
    return "\n".join(s)


# ----------------------------------------------------------- kalp atisi ---
def sessizlik_kontrol(state, raporlar, token, chat_id):
    """MGM'den hic rapor donmemesi de (bos liste) veri akisinin kesilmesi
    demektir - bu yuzden en yeni rapor zamanini state'e ayrica kaydedip,
    bu turda hic rapor gelmese bile en son bilinen zamana gore yaslandiriyoruz."""
    simdi = datetime.now(timezone.utc)
    zamanlar = [r["zaman"] for r in raporlar if r.get("zaman")]

    if zamanlar:
        en_yeni = max(zamanlar)
        state["son_veri_zamani"] = en_yeni.isoformat(timespec="seconds")
    else:
        try:
            en_yeni = (datetime.fromisoformat(state["son_veri_zamani"])
                       if state.get("son_veri_zamani") else None)
        except ValueError:
            en_yeni = None
        if en_yeni is None:
            return   # daha once hic veri gormedik, olcum noktasi yok

    yas = simdi - en_yeni

    if yas < timedelta(hours=SESSIZLIK_SAAT):
        if state.get("son_uyari"):
            try:
                telegram_gonder(
                    token, chat_id,
                    f"🟢 <b>{ICAO} · veri akışı normale döndü</b>\n\n"
                    f"En yeni rapor: {en_yeni:%d.%m %H:%M}Z."
                )
                print("[uyarı] Veri akışı normale döndü bildirimi gönderildi.",
                      file=sys.stderr)
            except Exception as e:
                print(f"[uyarı] Düzelme bildirimi gönderilemedi: {e}", file=sys.stderr)
        state["son_uyari"] = None
        return

    if state.get("son_uyari"):
        try:
            if simdi - datetime.fromisoformat(state["son_uyari"]) < \
                    timedelta(hours=UYARI_ARALIGI_SAAT):
                return
        except ValueError:
            pass

    saat = int(yas.total_seconds() // 3600)
    mesaj = (
        f"🟡 <b>{ICAO} · veri akmıyor</b>\n\n"
        f"Bot çalışıyor ama MGM'deki en yeni rapor <b>{saat} saat</b> öncesine ait "
        f"({en_yeni:%d.%m %H:%M}Z).\n\n"
        f"Muhtemel sebepler: MGM tarafında yayın durmuş, istasyon bakımda, "
        f"ya da sayfa yapısı değişmiş."
    )
    try:
        telegram_gonder(token, chat_id, mesaj)
        state["son_uyari"] = simdi.isoformat(timespec="seconds")
        print(f"[uyarı] Sessizlik uyarısı gönderildi ({saat} saat).", file=sys.stderr)
    except Exception as e:
        print(f"[uyarı] Sessizlik uyarısı gönderilemedi: {e}", file=sys.stderr)


def durum_mesajini_guncelle(state, raporlar, token, chat_id):
    if not ayar("bildirim", "sabit_mesaj", varsayilan=True):
        return
    metin = durum_mesaji_kur(raporlar, state)
    mesaj_id = state.get("durum_mesaj_id")

    if mesaj_id and telegram_duzenle(token, chat_id, mesaj_id, metin):
        return
    try:
        yeni = telegram_gonder(token, chat_id, metin, sessiz=True)
        if yeni:
            telegram_sabitle(token, chat_id, yeni)
            state["durum_mesaj_id"] = yeni
            print(f"  durum mesajı oluşturuldu ve sabitlendi (id {yeni})")
    except Exception as e:
        print(f"[uyarı] Durum mesajı oluşturulamadı: {e}", file=sys.stderr)


# ------------------------------------------------------------------- main ---
def main():
    env_yukle()
    token = gerekli("TELEGRAM_BOT_TOKEN")
    chat_id = gerekli("TELEGRAM_CHAT_ID")

    state = state_oku()

    try:
        raporlar = raporlari_cek(ICAO)
    except AgHatasi as e:
        print(f"[uyarı] MGM'ye ulaşılamadı, bu tur atlanıyor: {e}", file=sys.stderr)
        # ONEMLI (kaynak sagligi): MGM'ye ULASILAMAMASI "yeni veri yok" ile
        # AYNI SEY DEGIL. Onceden bu durumda fonksiyon burada dogrudan
        # return ediyordu - sessizlik_kontrol() hic CAGRILMIYORDU, yani MGM
        # TAMAMEN COKSE bile "veri akmıyor" alarmi hicbir zaman tetiklenemiyordu
        # (tam da alarmin en cok gerekli oldugu an). Artik kaynak erisim
        # hatasi da bos rapor listesiyle sessizlik_kontrol()'u calistirir -
        # o da zaten state'teki en son BILINEN veri zamanina gore yaslandirma
        # yapiyor (bkz. sessizlik_kontrol icindeki "zamanlar bossa" dali).
        sessizlik_kontrol(state, [], token, chat_id)
        state_yaz(state)
        return
    except AyiklamaHatasi as e:
        sys.exit(f"KRİTİK: veri ayıklanamadı, parser güncellenmeli.\n{e}")

    sessizlik_kontrol(state, raporlar, token, chat_id)

    if not raporlar:
        state_yaz(state)
        print("Rapor dönmedi, çıkılıyor.")
        return

    olcum_gecmisini_guncelle(state, raporlar)

    gorulen = set(state["gonderilen"])
    yeniler = [r for r in raporlar if anahtar(r) not in gorulen]

    if "--hepsi" in sys.argv:
        gonderilecek = list(reversed(raporlar))
        print(f"--hepsi: {len(gonderilecek)} rapor gönderiliyor (state yok sayıldı).")
    elif state["ilk_calisma"]:
        gonderilecek = yeniler[:1] if ILK_CALISTIRMADA_GONDER else []
        print(f"İlk çalışma. {len(yeniler)} rapor kaydediliyor, "
              f"{len(gonderilecek)} tanesi gönderiliyor.")
    else:
        gonderilecek = list(reversed(yeniler))
        print(f"{len(gonderilecek)} yeni rapor.")

    onceki_metar = state.get("son_metar", "")

    for rapor in gonderilecek:
        cozum = (metar_coz(rapor["metin"])
                 if rapor["tip"] in ("METAR", "SPECI") else None)
        notlar = (havacilik_notlari(cozum, rapor["metin"], rapor.get("zaman"))
                  if cozum else None)

        # Bildirim tetikleyicisi SADECE gercek tehlike: esik uyarilari ve
        # ruzgar kesmesi. PRS askiya alinmasi bilgi niteliginde - mesajda
        # gorunur ama telefon oturmez, yoksa hafif yagmurda yarim saatte bir
        # bildirim gelir.
        dikkat = bool(uyarilar(cozum)) if cozum else False
        if notlar and notlar["ws"]:
            dikkat = True

        renk_bilgisi = notlar["renk"] if notlar and notlar["renk"] else None
        renk = renk_bilgisi[0] if renk_bilgisi else None
        renk_degisti = renk_onemli_mi(state.get("son_renk"), renk)
        renk_kotulesti = renk_kotulesti_mi(state.get("son_renk"), renk)

        at, sessiz = bildirim_karari(rapor, dikkat, renk_degisti)

        if at:
            try:
                telegram_gonder(token, chat_id,
                                mesaj_kur(rapor, state, onceki_metar), sessiz=sessiz)
                print(f'  gönderildi{" (sessiz)" if sessiz else ""}: '
                      f'{rapor["tip"]} {anahtar(rapor)}')
            except Exception as e:
                print(f'  GÖNDERİLEMEDİ ({rapor["tip"]}): {e}', file=sys.stderr)
                continue
        else:
            print(f'  rutin, bildirim yok: {rapor["tip"]} {anahtar(rapor)}')

        # Web Push, Telegram'dan TAMAMEN BAGIMSIZ bir kanal - Telegram
        # basarisiz/gonderilmedi olsa da (yukaridaki 'continue' hic
        # calismadiysa) SPECI/TAF/duzeltme/renk-kotulesmesi push'u dener.
        if push_tetiklenmeli_mi(rapor, renk_kotulesti):
            push_bildirimi_gonder(rapor, cozum, renk_bilgisi)

        gorulen.add(anahtar(rapor))
        if renk:
            state["son_renk"] = renk
        if rapor["tip"] in ("METAR", "SPECI"):
            onceki_metar = rapor["metin"]

    # Sabitlenmis durum mesaji - yeni rapor olmasa da saat damgasi tazelenir
    durum_mesajini_guncelle(state, raporlar, token, chat_id)

    # NOTAM senkronizasyonu METAR akisindan bagimsiz bir katman - basarisizligi
    # (NOTAC erisilemez, yetki hatasi vb.) web sayfasinin METAR kismini asla
    # bozmaz, sadece bu turdaki NOTAM guncellemesi atlanir.
    try:
        notam_senkronize(state)
    except Exception as e:
        print(f"[uyarı] NOTAM senkronizasyonu başarısız: {e}", file=sys.stderr)

    if ayar("notam", "aktif", varsayilan=True):
        try:
            ltfj_notam.notam_veri_yaz(state, KLASOR / "notam_veri.json",
                                       ayar("notam", "location", varsayilan="LTFJ"))
        except Exception as e:
            print(f"[uyarı] NOTAM web verisi üretilemedi: {e}", file=sys.stderr)

    # ATC Notes temizligi de METAR/NOTAM'dan bagimsiz bir katman - notlarin
    # kendisi dogrudan tarayicidan Firebase'e yaziliyor, burada SADECE
    # suresi dolmus kayitlar siliniyor.
    try:
        silinen = atc_notes_temizligini_calistir()
        if silinen:
            print(f"  ATC notes temizliği: {silinen} süresi dolmuş not silindi.")
    except Exception as e:
        print(f"[uyarı] ATC notes temizliği başarısız: {e}", file=sys.stderr)

    if ayar("web_sayfasi", varsayilan=True):
        try:
            from ltfj_sayfa import sayfa_yaz

            # Saatlik tahmin GEVŞEK BAĞLI: yerel önbellekten okunur, ağa
            # çıkılmaz. Önbellek yoksa/bayatsa boş liste döner ve o blok
            # sayfada hiç görünmez - METAR/TAF akışı etkilenmez.
            try:
                import ltfj_dis_kaynak_cache
                saatlik_tahmin = ltfj_dis_kaynak_cache.tahmin_oku()
                # Yaş da okunuyor: şerit bayatlayınca artık GİZLENMİYOR,
                # kaç saatlik bir model çıktısı olduğunu yazıyor.
                tahmin_yas_dk = ltfj_dis_kaynak_cache.tahmin_yasi_dk()
            except Exception as e:
                print(f"[uyarı] Saatlik tahmin okunamadı, atlanıyor: {e}", file=sys.stderr)
                saatlik_tahmin = []
                tahmin_yas_dk = None

            sayfa_yaz(raporlar, state.get("olcum_gecmisi", []), KLASOR / "index.html",
                      state.get("yorum_onbellegi", {}),
                      ayar("atc_notes", "database_url", varsayilan=""),
                      ayar("push", "vapid_public_key", varsayilan=""),
                      saatlik_tahmin, tahmin_yas_dk)
        except Exception as e:
            print(f"[uyarı] Web sayfası üretilemedi: {e}", file=sys.stderr)

    if ayar("atc_paneli", varsayilan=True):
        try:
            from ltfj_panel import panel_verisi_yaz
            panel_verisi_yaz(raporlar, state.get("olcum_gecmisi", []), KLASOR / "panel_veri.json")
        except Exception as e:
            print(f"[uyarı] ATC panel verisi üretilemedi: {e}", file=sys.stderr)

    if state["ilk_calisma"]:
        gorulen.update(anahtar(r) for r in raporlar)

    guncel = next((r["metin"] for r in raporlar
                   if r["tip"] in ("METAR", "SPECI")), "")
    state["son_metar"] = guncel or onceki_metar
    state["gonderilen"] = [k for k in state["gonderilen"] if k in gorulen]
    state["gonderilen"] += [k for k in gorulen if k not in state["gonderilen"]]
    state["ilk_calisma"] = False
    state_yaz(state)


if __name__ == "__main__":
    main()
