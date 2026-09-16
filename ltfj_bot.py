#!/usr/bin/env python3
"""
LTFJ METAR/TAF Telegram bildirim botu.

Bir kere calisir, isini yapar, cikar. Surekli calismaz -> systemd timer / cron ile
belirli araliklarla tetiklenir. Ayni raporu iki kez GONDERMEZ.

Dosyalar:
  ltfj_rasat.py      -> veri cekme (ayni klasorde olmali)
  .env               -> gizli anahtarlar
  ltfj_state.json    -> gonderilmis rapor kayitlari (otomatik olusur)

Kurulum:
  pip install requests
  .env dosyasi olustur (asagidaki ORNEK_ENV'e bak)
  python ltfj_bot.py
"""

import html
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from ltfj_rasat import raporlari_cek

# ----------------------------------------------------------------- ayarlar ---
ICAO = "LTFJ"
KLASOR = Path(__file__).resolve().parent
STATE = KLASOR / "ltfj_state.json"
ENV = KLASOR / ".env"

# Ilk calistirmada gecmisi doldurup susmak yerine en yeni raporu gonderir.
# Boylece kurulumun calistigini hemen gorursun.
ILK_CALISTIRMADA_GONDER = True

# Hafizada tutulacak gecmis kayit sayisi (dosya sismesin diye)
GECMIS_LIMIT = 200

# Claude yorumu (istege bagli). .env icinde ANTHROPIC_API_KEY yoksa atlanir.
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_URL = "https://api.anthropic.com/v1/messages"

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


def gerekli(anahtar):
    deger = os.environ.get(anahtar, "").strip()
    if not deger:
        sys.exit(
            f"HATA: {anahtar} tanimli degil.\n"
            f"{ENV} dosyasi olustur, icine sunu yaz:\n\n{ORNEK_ENV}"
        )
    return deger


# ------------------------------------------------------------------ state ---
def state_oku() -> dict:
    if not STATE.exists():
        return {"gonderilen": [], "ilk_calisma": True}
    try:
        d = json.loads(STATE.read_text(encoding="utf-8"))
        d.setdefault("gonderilen", [])
        d.setdefault("ilk_calisma", False)
        return d
    except (json.JSONDecodeError, OSError):
        return {"gonderilen": [], "ilk_calisma": True}


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


def mesaj_kur(rapor: dict) -> str:
    simge = {"METAR": "🛬", "SPECI": "⚠️", "TAF": "📅"}.get(rapor["tip"], "ℹ️")
    if rapor.get("zaman"):
        yerel = rapor["zaman"].astimezone()
        damga = f'{rapor["zaman"]:%d.%m %H:%MZ} · {yerel:%H:%M} yerel'
    else:
        damga = ""

    satirlar = [
        f'{simge} <b>{ICAO} {rapor["tip"]}</b>  <i>{damga}</i>',
        "",
        f'<pre>{html.escape(rapor["metin"])}</pre>',
    ]
    yorum = claude_yorum(rapor["metin"], rapor["tip"])
    if yorum:
        satirlar += ["", html.escape(yorum)]
    return "\n".join(satirlar)


# ------------------------------------------------------------------- main ---
def main():
    env_yukle()
    token = gerekli("TELEGRAM_BOT_TOKEN")
    chat_id = gerekli("TELEGRAM_CHAT_ID")

    try:
        raporlar = raporlari_cek(ICAO)
    except Exception as e:
        # Ag hatasi kalici bir ariza degil - bir sonraki turda tekrar denenir.
        # Bilerek 0 ile cikiyoruz ki GitHub Actions bunu "basarisiz" saymasin.
        print(f"[uyari] Rapor cekilemedi, bu tur atlaniyor: {e}", file=sys.stderr)
        return

    if not raporlar:
        print("Rapor donmedi, cikiliyor.")
        return

    state = state_oku()
    gorulen = set(state["gonderilen"])
    yeniler = [r for r in raporlar if anahtar(r) not in gorulen]

    if "--hepsi" in sys.argv:
        # Elle test icin: state'e bakmadan su anki tum raporlari gonder.
        gonderilecek = list(reversed(raporlar))
        print(f"--hepsi: {len(gonderilecek)} rapor gonderiliyor (state yok sayildi).")
    elif state["ilk_calisma"]:
        # Gecmisi bir kerede bombalamayalim: sadece en yenisini gonder.
        gonderilecek = yeniler[:1] if ILK_CALISTIRMADA_GONDER else []
        print(f"Ilk calisma. {len(yeniler)} rapor kaydediliyor, "
              f"{len(gonderilecek)} tanesi gonderiliyor.")
    else:
        gonderilecek = list(reversed(yeniler))   # eskiden yeniye dogru
        print(f"{len(gonderilecek)} yeni rapor.")

    for rapor in gonderilecek:
        try:
            telegram_gonder(token, chat_id, mesaj_kur(rapor))
            print(f'  gonderildi: {rapor["tip"]} {anahtar(rapor)}')
        except Exception as e:
            print(f'  GONDERILEMEDI ({rapor["tip"]}): {e}', file=sys.stderr)
            continue   # bu raporu "gorulmus" saymiyoruz, sonraki turda tekrar dener
        gorulen.add(anahtar(rapor))

    # Ilk calismada gondermediklerimizi de gorulmus say ki bir daha atmasin
    if state["ilk_calisma"]:
        gorulen.update(anahtar(r) for r in raporlar)

    state["gonderilen"] = [k for k in state["gonderilen"] if k in gorulen]
    state["gonderilen"] += [k for k in gorulen if k not in state["gonderilen"]]
    state["ilk_calisma"] = False
    state_yaz(state)


if __name__ == "__main__":
    main()