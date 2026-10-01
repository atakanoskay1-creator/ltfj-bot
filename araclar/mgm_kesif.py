#!/usr/bin/env python3
"""MGM rasat yanıt sözleşmesini KEŞFET - SALT OKUNUR.

NEDEN VAR: Bot MGM'den `hours=0` ile yalnızca son raporları çekiyor ve
yanıttaki `dataLast` alanını okuyor. Kaçan METAR'ları geri doldurmak için
(arşiv PR-2) `hours=N`'nin ne döndürdüğünü bilmemiz gerekiyor:

  - Son N saatin bütün METAR/SPECI'leri geliyor mu, eksiksiz mi?
  - Kayıtlar yine `dataLast`'ta mı, başka bir alanda mı?
  - COR/AMD düzeltmeleri nasıl temsil ediliyor; aynı gözlem zamanı için
    birden çok sürüm var mı; hangi zaman/kimlik alanları mevcut?

Bu betik bunları ÖLÇER; alan adı ya da semantik UYDURMAZ. Hiçbir kalıcı
veriyi değiştirmez: yalnızca stdout'a, verilmişse $GITHUB_STEP_SUMMARY'ye
ve verilmişse --ham-dizin'e (Actions'ta geçici dizin, artifact olarak
yüklenir) yazar. Repo dosyalarına, state'e ya da arşive dokunmaz.

Çalıştırma (GitHub Actions, "MGM keşif" iş akışı):
    python araclar/mgm_kesif.py --ham-dizin "$RUNNER_TEMP/mgm_kesif"
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# bot modulleri bot/ altinda; repo kokunden `python araclar/mgm_kesif.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bot"))

import ltfj_rasat as rasat

SAATLER = (0, 3, 24)
IZGARA_DK = (20, 50)
ZAMAN_ALANI = "observationTimeNormal"      # ltfj_rasat'in bugun okudugu alan
METIN_ALANI = "observationText"
KATEGORIK_ESIK = 20                        # bundan az farkli degerli alanlar dagilimiyla basilir


def dakikaya_indir(z):
    """Gozlem zamanini dakikaya indirir. MGM observationTimeNormal degerleri
    saniye-alti kesir tasiyor (ilk kesif: ornegin 07:20:00.032); izgara
    karsilastirmasi dakika duzeyinde yapilmali."""
    return z.replace(second=0, microsecond=0) if z is not None else None


def cek(saat: int, icao: str = rasat.ICAO, timeout: int = 30) -> tuple:
    """(next_data_json, meta) - ltfj_rasat'in istek parametreleri ve yeniden
    deneme mantigiyla, yalnizca `hours` degistirilerek."""
    params = [("stations", icao), ("obsType", "1"), ("obsType", "2"), ("hours", str(saat))]
    r = rasat._sayfayi_getir(params, timeout)
    m = rasat.NEXT_DATA.search(r.text)
    meta = {"url": r.url, "http": r.status_code, "bayt": len(r.content),
            "cekim_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if not m:
        return None, meta
    return json.loads(m.group(1)), meta


def _tip(metin: str) -> str:
    t = (metin or "").split()
    return t[0].upper() if t else "?"


def _duzeltme(metin: str):
    t = (metin or "").split()
    return next((x for x in t[1:3] if x in rasat.DUZELTMELER), None)


def _kayit_listeleri(blok: dict) -> dict:
    """Blok icindeki, elemanlari rapor metni tasiyan liste alanlari."""
    out = {}
    for k, v in blok.items():
        if isinstance(v, list) and v and isinstance(v[0], dict) and \
                any(METIN_ALANI in e for e in v if isinstance(e, dict)):
            out[k] = v
    return out


def _zamanlar(kayitlar: list) -> dict:
    """Zaman gibi gorunen her alan icin (en eski, en yeni) - hangi zaman
    alanlarinin var oldugunu gostermek icin."""
    alan = defaultdict(list)
    for e in kayitlar:
        for k, v in e.items():
            if isinstance(v, str) and ("time" in k.lower() or "date" in k.lower()):
                z = rasat._zaman(v)
                if z is not None:
                    alan[k].append(z)
    return {k: (min(v).isoformat(), max(v).isoformat(), len(v)) for k, v in sorted(alan.items())}


def liste_ozeti(kayitlar: list) -> dict:
    tipler = Counter()
    duzeltme = Counter()
    gozlem = []                     # (zaman, tip, duzeltme, id, metin)
    for e in kayitlar:
        metin = " ".join((e.get(METIN_ALANI) or "").split())
        tip = _tip(metin)
        tipler[tip] += 1
        d = _duzeltme(metin)
        if d:
            duzeltme[d] += 1
        if tip in ("METAR", "SPECI"):
            gozlem.append((rasat._zaman(e.get(ZAMAN_ALANI)), tip, d, e.get("id"), metin))
    zamanli = [g for g in gozlem if g[0] is not None]
    kesirli = sum(1 for g in zamanli if g[0].second or g[0].microsecond)
    metar = sorted(dakikaya_indir(g[0]) for g in zamanli if g[1] == "METAR")
    izgara = [z for z in metar if z.minute in IZGARA_DK]
    eksik = []
    if izgara:
        t, son = izgara[0], izgara[-1]
        mevcut = set(izgara)
        while t <= son:
            if t not in mevcut:
                eksik.append(t)
            t += timedelta(minutes=30)
    ayni_zaman = Counter((dakikaya_indir(g[0]), g[1]) for g in zamanli)
    kategorik = {}
    for alan in sorted({k for e in kayitlar for k in e} - {METIN_ALANI, ZAMAN_ALANI, "id"}):
        degerler = Counter(str(e.get(alan)) for e in kayitlar)
        if len(degerler) <= KATEGORIK_ESIK:
            kategorik[alan] = dict(degerler)
    # observationStatus NORMAL (1) disindaki kayitlar tam ayrintiyla - ikinci
    # kesif 24 saatte 3 METAR'in status=4 / "CCA" oldugunu gosterdi; metinde
    # COR yoktu. Duzeltmenin nasil temsil edildigini gormek icin: zaman, id,
    # komsu METAR id'leri (ekleme sirasi ipucu) ve ham metin.
    sirali = sorted(((rasat._zaman(e.get(ZAMAN_ALANI)), e) for e in kayitlar
                     if rasat._zaman(e.get(ZAMAN_ALANI)) is not None), key=lambda x: x[0])
    normal_disi = []
    for i, (z, e) in enumerate(sirali):
        if str(e.get("observationStatus")) not in ("1", "None"):
            onceki = next((x[1].get("id") for x in reversed(sirali[:i])
                           if _tip(x[1].get(METIN_ALANI)) == _tip(e.get(METIN_ALANI))), None)
            sonraki = next((x[1].get("id") for x in sirali[i + 1:]
                            if _tip(x[1].get(METIN_ALANI)) == _tip(e.get(METIN_ALANI))), None)
            normal_disi.append({
                "zaman": z.isoformat(), "id": e.get("id"), "onceki_ayni_tip_id": onceki,
                "sonraki_ayni_tip_id": sonraki, "status": e.get("observationStatus"),
                "aciklama": (e.get("observationStatusExplanation") or "").strip(),
                "metin": " ".join((e.get(METIN_ALANI) or "").split())})
    tip_durum = Counter((_tip(" ".join((e.get(METIN_ALANI) or "").split())),
                         str(e.get("observationStatus")), str(e.get("observationType")))
                        for e in kayitlar)
    idler = [e.get("id") for e in kayitlar if e.get("id") is not None]   # butun kayitlar
    return {
        "kayit": len(kayitlar),
        "ilk_kayit_anahtarlari": sorted(kayitlar[0].keys()) if kayitlar else [],
        "tipler": dict(tipler),
        "duzeltme": dict(duzeltme),
        "gozlem_zamani_en_eski": min(g[0] for g in zamanli).isoformat() if zamanli else None,
        "gozlem_zamani_en_yeni": max(g[0] for g in zamanli).isoformat() if zamanli else None,
        "zamansiz_gozlem": len(gozlem) - len(zamanli),
        "saniye_alti_kesirli_zaman": kesirli,
        "normal_disi_kayitlar": normal_disi,
        "kategorik_alanlar": kategorik,
        "tip_x_status_x_type": {f"{a} / status={b} / type={c}": v
                                for (a, b, c), v in sorted(tip_durum.items())},
        "metar_izgara": len(izgara),
        "metar_izgara_disi": len(metar) - len(izgara),
        "izgara_eksik_slot": [z.isoformat() for z in eksik],
        "ayni_zaman_tip_birden_cok": [f"{k[0].isoformat()} {k[1]} ×{v}"
                                      for k, v in sorted(ayni_zaman.items()) if v > 1],
        "id_var": len(idler), "id_benzersiz": len(set(idler)),
        "zaman_alanlari": _zamanlar(kayitlar),
        "gozlemler": [(g[0].isoformat() if g[0] else None, g[1], g[2], g[3])
                      for g in sorted(gozlem, key=lambda g: (g[0] is None, g[0] or 0))],
        "_anahtarlar": {(g[0], g[1], g[4]) for g in zamanli},
    }


def ozetle(data, saat: int, icao: str = rasat.ICAO) -> dict:
    """Bir next_data yanitinin yapisal ozeti."""
    if data is None:
        return {"saat": saat, "hata": "__NEXT_DATA__ bulunamadi"}
    pp = (data.get("props") or {}).get("pageProps") or {}
    yanit = pp.get("response")
    o = {"saat": saat, "ust_anahtarlar": sorted(data.keys()),
         "pageProps_anahtarlari": sorted(pp.keys()), "query": data.get("query"),
         "response_turu": type(yanit).__name__,
         "response_uzunluk": len(yanit) if isinstance(yanit, list) else None, "bloklar": []}
    for blok in yanit if isinstance(yanit, list) else []:
        if not isinstance(blok, dict):
            continue
        b = {"blok_anahtarlari": sorted(blok.keys()),
             "icao": (blok.get("istInfo") or {}).get("icao"), "listeler": {},
             "alan_turleri": {k: (f"list({len(v)})" if isinstance(v, list) else type(v).__name__)
                              for k, v in sorted(blok.items())}}
        if (b["icao"] or "").upper() == icao.upper():
            for k, v in _kayit_listeleri(blok).items():
                b["listeler"][k] = liste_ozeti(v)
        o["bloklar"].append(b)
    return o


def _istasyon_listeleri(o: dict) -> dict:
    for b in o.get("bloklar", []):
        if b["listeler"]:
            return b["listeler"]
    return {}


def markdown(ozetler: list, meta: dict) -> str:
    s = ["# MGM keşif (salt okunur)\n"]
    for o in ozetler:
        m = meta.get(o["saat"], {})
        s.append(f"## hours={o['saat']}\n")
        s.append(f"- istek: `{m.get('url')}` · HTTP {m.get('http')} · {m.get('bayt')} bayt · "
                 f"çekim {m.get('cekim_utc')} UTC")
        if "hata" in o:
            s.append(f"- **HATA:** {o['hata']}\n")
            continue
        s.append(f"- üst seviye anahtarlar: `{o['ust_anahtarlar']}`")
        s.append(f"- pageProps anahtarları: `{o['pageProps_anahtarlari']}`")
        s.append(f"- query: `{o['query']}`")
        s.append(f"- response: {o['response_turu']} (uzunluk {o['response_uzunluk']})")
        for i, b in enumerate(o["bloklar"]):
            s.append(f"- blok {i}: icao `{b['icao']}`, anahtarlar `{b['blok_anahtarlari']}`")
            s.append(f"  - alan türleri: `{b['alan_turleri']}`")
            for ad, lo in b["listeler"].items():
                s.append(f"  - **veri alanı `{ad}`**: {lo['kayit']} kayıt · tipler {lo['tipler']} · "
                         f"düzeltme {lo['duzeltme'] or '{}'}")
                s.append(f"    - gözlem zamanı ({ZAMAN_ALANI}): en eski {lo['gozlem_zamani_en_eski']} · "
                         f"en yeni {lo['gozlem_zamani_en_yeni']} · zamansız {lo['zamansiz_gozlem']}")
                s.append(f"    - saniye-altı kesirli gözlem zamanı: {lo['saniye_alti_kesirli_zaman']} "
                         "(ızgara karşılaştırması dakikaya indirilerek yapıldı)")
                s.append(f"    - kategorik alanlar (değer: adet): `{lo['kategorik_alanlar']}`")
                s.append(f"    - tip × observationStatus × observationType: `{lo['tip_x_status_x_type']}`")
                for nd in lo["normal_disi_kayitlar"]:
                    s.append(f"    - NORMAL DIŞI: {nd['zaman']} · id {nd['id']} (aynı tipte önceki "
                             f"id {nd['onceki_ayni_tip_id']}, sonraki {nd['sonraki_ayni_tip_id']}) · "
                             f"status {nd['status']} `{nd['aciklama']}` · `{nd['metin']}`")
                s.append(f"    - METAR ızgara (:20/:50) {lo['metar_izgara']} · ızgara dışı METAR "
                         f"{lo['metar_izgara_disi']} · aralıkta eksik ızgara slotu "
                         f"{len(lo['izgara_eksik_slot'])} {lo['izgara_eksik_slot'][:20]}")
                s.append(f"    - aynı (zaman, tip) birden çok kayıt: {lo['ayni_zaman_tip_birden_cok'] or 'yok'}")
                s.append(f"    - id: {lo['id_var']} kayıtta var, {lo['id_benzersiz']} benzersiz")
                s.append(f"    - kayıt anahtarları: `{lo['ilk_kayit_anahtarlari']}`")
                s.append(f"    - zaman gibi alanlar (en eski, en yeni, adet): `{lo['zaman_alanlari']}`")
                s.append("    - gözlemler (zaman, tip, düzeltme, id): "
                         + "; ".join(f"{z} {t}{' ' + d if d else ''} #{i_}" for z, t, d, i_ in lo["gozlemler"]))
        s.append("")
    # capraz karsilastirma
    kume = {}
    for o in ozetler:
        for ad, lo in _istasyon_listeleri(o).items():
            kume[(o["saat"], ad)] = lo["_anahtarlar"]
    if kume:
        s.append("## Karşılaştırma — (gözlem zamanı, tip, metin) kümeleri\n")
        anahtarlar = sorted(kume)
        for a in anahtarlar:
            for b in anahtarlar:
                if a < b:
                    ka, kb = kume[a], kume[b]
                    s.append(f"- hours={a[0]} `{a[1]}` ({len(ka)}) ⊆ hours={b[0]} `{b[1]}` ({len(kb)}): "
                             f"{'evet' if ka <= kb else 'HAYIR'} · kesişim {len(ka & kb)} · "
                             f"yalnız ilkinde {len(ka - kb)}")
    return "\n".join(s) + "\n"


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--saat", type=int, nargs="+", default=list(SAATLER))
    a.add_argument("--ham-dizin", type=Path, default=None,
                   help="ham __NEXT_DATA__ JSON'larinin yazilacagi GECICI dizin (artifact)")
    s = a.parse_args(argv)

    ozetler, meta = [], {}
    for saat in s.saat:
        try:
            data, meta[saat] = cek(saat)
        except rasat.RasatHatasi as e:
            ozetler.append({"saat": saat, "hata": f"{type(e).__name__}: {e}"})
            continue
        ozetler.append(ozetle(data, saat))
        if s.ham_dizin is not None and data is not None:
            s.ham_dizin.mkdir(parents=True, exist_ok=True)
            (s.ham_dizin / f"mgm_hours_{saat}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    rapor = markdown(ozetler, meta)
    print(rapor)
    ozet_yolu = os.environ.get("GITHUB_STEP_SUMMARY")
    if ozet_yolu:
        with open(ozet_yolu, "a", encoding="utf-8") as f:
            f.write(rapor)
    return 0 if all("hata" not in o for o in ozetler) else 1


if __name__ == "__main__":
    raise SystemExit(main())
