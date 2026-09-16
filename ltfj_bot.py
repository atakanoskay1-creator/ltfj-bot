#!/usr/bin/env python3
"""
LTFJ METAR/TAF Telegram bildirim botu.

Bir kere calisir, isini yapar, cikar. Surekli calismaz -> GitHub Actions / systemd
timer ile belirli araliklarla tetiklenir. Ayni raporu iki kez GONDERMEZ.

Dosyalar:
  ltfj_rasat.py      -> veri cekme        (ayni klasorde olmali)
  ltfj_analiz.py     -> METAR cozumleme   (ayni klasorde olmali)
  .env               -> gizli anahtarlar  (GitHub Actions'ta Secrets kullanilir)
  ltfj_state.json    -> gonderilmis rapor kayitlari (otomatik olusur)

Cikis kodlari:
  0 = her sey yolunda ya da gecici ag sorunu (bir sonraki turda telafi edilir)
  1 = mudahale gerektiren kalici sorun (eksik ayar, MGM sayfa yapisi degismis)

Kurulum:
  pip install requests
  .env dosyasi olustur (asagidaki ORNEK_ENV'e bak)
  python ltfj_bot.py

Bayraklar:
  --hepsi   state'i yok sayip su anki tum raporlari gonderir (elle test)
"""

import html
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from ltfj_analiz import fark_bul, metar_coz, ozet_satiri, uyarilar
from ltfj_rasat import AgHatasi, AyiklamaHatasi, raporlari_cek

# ----------------------------------------------------------------- ayarlar ---
ICAO = "LTFJ"
KLASOR = Path(__file__).resolve().parent
STATE = KLASOR / "ltfj_state.json"
ENV = KLASOR / ".env"

# Ilk calistirmada gecmisi doldurup susmak yerine en yeni raporu gonderir.
ILK_CALISTIRMADA_GONDER = True

# Hafizada tutulacak gecmis kayit sayisi (dosya sismesin diye)
GECMIS_LIMIT = 200

# Kalp atisi: en yeni rapor bu kadar saatten eskiyse "veri gelmiyor" uyarisi at.
# LTFJ'de METAR yarim saatte bir yayinlanir, 6 saat sessizlik gercekten anormal.
SESSIZLIK_SAAT = 6
UYARI_ARALIGI_SAAT = 12        # ayni uyariyi tekrar tekrar atmayalim

# Claude yorumu (istege bagli). ANTHROPIC_API_KEY yoksa atlanir.
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_URL = "https://api.anthropic.com/v1/messages"

SIMGE = {"METAR": "🛬", "SPECI": "⚠️", "TAF": "📅"}

ORNEK_ENV = """\
TELEGRAM_BOT_TOKEN=123456:AA...
TELEGRAM_CHAT_ID=987654321
# Asagidaki satir istege bagli - silersen Claude yorumu yapilmaz
ANTHROPIC_API_KEY=sk-ant-...
"""


# -------------------------------------------------------------------- env ---
def env_yukle():
    """.env dosyasini os.environ'a yukler (harici kutuphane yok)."""
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
    bos = {"gonderilen": [], "ilk_calisma": True, "son_metar": "", "son_uyari": None}
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
    state["guncelleme"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def anahtar(rapor: dict) -> str:
    """Her rapor icin benzersiz kimlik. id yoksa tip+zaman'a duser."""
    if rapor.get("id"):
        return f"id:{rapor['id']}"
    z = rapor["zaman"].isoformat() if rapor.get("zaman") else "?"
    return f"{rapor['tip']}:{z}"


# ----------------------------------------------------------------- claude ---
def claude_yorum(metin: str, tip: str) -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return None

    istem = (
        f"Asagidaki {tip} raporunu bir pilota degil, havacilik bilmeyen birine "
        f"anlatir gibi sade Turkce ile ozetle. En fazla 3 kisa cumle. "
        f"Ruzgar, gorus, bulut, yagis ve varsa dikkat cekici bir durum olsun. "
        f"Giris cumlesi kurma, dogrudan ozetle.\n\n{metin}"
    )
    try:
        r = requests.post(
            CLAUDE_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": 300,
                "messages": [{"role": "user", "content": istem}],
            },
            timeout=30,
        )
        r.raise_for_status()
        parcalar = r.json().get("content", [])
        return "".join(p.get("text", "") for p in parcalar).strip() or None
    except requests.RequestException as e:
        print(f"[uyari] Claude yorumu alinamadi: {e}", file=sys.stderr)
        return None


# --------------------------------------------------------------- telegram ---
def telegram_gonder(token: str, chat_id: str, metin: str):
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": metin,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    r.raise_for_status()
    if not r.json().get("ok"):
        raise RuntimeError(f"Telegram reddetti: {r.text}")


def mesaj_kur(rapor: dict, onceki_metar: str = "") -> str:
    tip = rapor["tip"]
    duzeltme = rapor.get("duzeltme")
    simge = SIMGE.get(tip, "ℹ️")

    baslik = f"{ICAO} {tip}"
    if duzeltme == "AMD":
        baslik += " (DUZELTME)"
        simge = "✏️"
    elif duzeltme == "COR":
        baslik += " (DUZELTILMIS)"
        simge = "✏️"

    if rapor.get("zaman"):
        yerel = rapor["zaman"].astimezone()
        damga = f'{rapor["zaman"]:%d.%m %H:%MZ} · {yerel:%H:%M} yerel'
    else:
        damga = ""

    satirlar = [f"{simge} <b>{html.escape(baslik)}</b>  <i>{damga}</i>"]

    # METAR/SPECI icin dikkat satiri ve degisim ozeti
    if tip in ("METAR", "SPECI"):
        cozum = metar_coz(rapor["metin"])

        dikkat = uyarilar(cozum)
        if dikkat:
            satirlar.append("")
            satirlar.append("🔴 <b>DIKKAT</b> · " + html.escape(" · ".join(dikkat)))

        farklar = fark_bul(onceki_metar, rapor["metin"])
        if farklar:
            satirlar.append("")
            satirlar.append("<b>Degisim</b>")
            satirlar += [f"• {html.escape(f)}" for f in farklar]

    satirlar += ["", f'<pre>{html.escape(rapor["metin"])}</pre>']

    yorum = claude_yorum(rapor["metin"], tip)
    if yorum:
        satirlar += ["", html.escape(yorum)]
    elif tip in ("METAR", "SPECI"):
        # Claude kapaliysa en azindan makine ozeti olsun
        satirlar += ["", html.escape(ozet_satiri(metar_coz(rapor["metin"])))]

    return "\n".join(satirlar)


# ----------------------------------------------------------- kalp atisi ---
def sessizlik_kontrol(state: dict, raporlar: list, token: str, chat_id: str):
    """En yeni rapor cok eskiyse haber ver. Bot calisiyor ama veri akmiyorsa
    kimse fark etmesin istemiyoruz."""
    zamanlar = [r["zaman"] for r in raporlar if r.get("zaman")]
    if not zamanlar:
        return
    en_yeni = max(zamanlar)
    simdi = datetime.now(timezone.utc)
    yas = simdi - en_yeni

    if yas < timedelta(hours=SESSIZLIK_SAAT):
        state["son_uyari"] = None        # durum normale dondu
        return

    # Ayni uyariyi surekli tekrarlamayalim
    if state.get("son_uyari"):
        try:
            onceki = datetime.fromisoformat(state["son_uyari"])
            if simdi - onceki < timedelta(hours=UYARI_ARALIGI_SAAT):
                return
        except ValueError:
            pass

    saat = int(yas.total_seconds() // 3600)
    mesaj = (
        f"🟡 <b>{ICAO} · veri akmiyor</b>\n\n"
        f"Bot calisiyor ama MGM'deki en yeni rapor <b>{saat} saat</b> oncesine ait "
        f"({en_yeni:%d.%m %H:%M}Z).\n\n"
        f"Muhtemel sebepler: MGM tarafinda yayin durmus, istasyon bakimda, "
        f"ya da sayfa yapisi degismis."
    )
    try:
        telegram_gonder(token, chat_id, mesaj)
        state["son_uyari"] = simdi.isoformat(timespec="seconds")
        print(f"[uyari] Sessizlik uyarisi gonderildi ({saat} saat).", file=sys.stderr)
    except Exception as e:
        print(f"[uyari] Sessizlik uyarisi gonderilemedi: {e}", file=sys.stderr)


# ------------------------------------------------------------------- main ---
def main():
    env_yukle()
    token = gerekli("TELEGRAM_BOT_TOKEN")
    chat_id = gerekli("TELEGRAM_CHAT_ID")

    try:
        raporlar = raporlari_cek(ICAO)
    except AgHatasi as e:
        # GECICI: bir sonraki turda telafi edilir, hata sayilmaz.
        print(f"[uyari] MGM'ye ulasilamadi, bu tur atlaniyor: {e}", file=sys.stderr)
        return
    except AyiklamaHatasi as e:
        # KALICI: sessizce gecersek bot haftalarca olu kalir. Gurultu cikar.
        sys.exit(f"KRITIK: veri ayiklanamadi, parser guncellenmeli.\n{e}")

    if not raporlar:
        print("Rapor donmedi, cikiliyor.")
        return

    state = state_oku()
    sessizlik_kontrol(state, raporlar, token, chat_id)

    gorulen = set(state["gonderilen"])
    yeniler = [r for r in raporlar if anahtar(r) not in gorulen]

    if "--hepsi" in sys.argv:
        gonderilecek = list(reversed(raporlar))
        print(f"--hepsi: {len(gonderilecek)} rapor gonderiliyor (state yok sayildi).")
    elif state["ilk_calisma"]:
        gonderilecek = yeniler[:1] if ILK_CALISTIRMADA_GONDER else []
        print(f"Ilk calisma. {len(yeniler)} rapor kaydediliyor, "
              f"{len(gonderilecek)} tanesi gonderiliyor.")
    else:
        gonderilecek = list(reversed(yeniler))   # eskiden yeniye dogru
        print(f"{len(gonderilecek)} yeni rapor.")

    onceki_metar = state.get("son_metar", "")

    for rapor in gonderilecek:
        try:
            telegram_gonder(token, chat_id, mesaj_kur(rapor, onceki_metar))
            print(f'  gonderildi: {rapor["tip"]} {anahtar(rapor)}')
        except Exception as e:
            print(f'  GONDERILEMEDI ({rapor["tip"]}): {e}', file=sys.stderr)
            continue   # bu raporu "gorulmus" saymiyoruz, sonraki turda tekrar dener
        gorulen.add(anahtar(rapor))
        if rapor["tip"] in ("METAR", "SPECI"):
            onceki_metar = rapor["metin"]        # zincirleme karsilastirma

    # Ilk calismada gondermediklerimizi de gorulmus say ki bir daha atmasin
    if state["ilk_calisma"]:
        gorulen.update(anahtar(r) for r in raporlar)

    # Karsilastirma referansi: gonderilmemis olsa bile en guncel METAR
    guncel_metar = next((r["metin"] for r in raporlar
                         if r["tip"] in ("METAR", "SPECI")), "")
    state["son_metar"] = guncel_metar or onceki_metar

    state["gonderilen"] = [k for k in state["gonderilen"] if k in gorulen]
    state["gonderilen"] += [k for k in gorulen if k not in state["gonderilen"]]
    state["ilk_calisma"] = False
    state_yaz(state)


if __name__ == "__main__":
    main()