#!/usr/bin/env python3
"""Gozlem arsivi geri doldurmasinin SALT OKUNUR dogrulamasi (PR-2).

Repodaki arsiv katmanlarini (gozlem_arsivi.csv, gozlem_surumleri.csv)
GECICI bir dizine kopyalar, bir MGM hours=24 yanitini
botun H24 yoluyla (ltfj_gozlem_arsivi.arsive_isle, kaynak=backfill_h24)
bu kopyaya isler ve ne oldugunu raporlar:

  - bu cagri oncesi kanonikte olmayip sonrasinda olan anahtarlar
    (backfill_kurtarilan, durum gecisi olarak),
  - --kontrol ile verilen anahtarlarin once/sonra kanonik satiri, surum
    satirlari (ham zaman, mgm_id, status, aciklama, metin) ve slot durumu,
  - arsiv durum ozeti (eksik slotlar, ingest tablosu, surum sayaclari),
  - idempotency: ayni yanit ikinci kez islenince dosyalar bayt bayt ayni mi.

Iki kaynak:
  --json DOSYA   kayitli bir __NEXT_DATA__ yaniti (ör. PR #99 kesif
                 artifact'i mgm_hours_24.json); --alinma zorunlu.
  --canli        su anki hours=24 yaniti (kuru calistirma).

Repo dosyalarina YAZMAZ. Production bagimliligi DEGILDIR: bot bu betigi
cagirmaz; kayitli artifact silinse de normal sistem etkilenmez.

    python arsiv_oynat.py --json mgm_hours_24.json --alinma 2026-09-28T09:35:54Z \\
        --kontrol "2026-09-27T16:20 METAR"
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import ltfj_gozlem_arsivi as ga
import ltfj_rasat as rasat
from ltfj_analiz import metar_coz

KLASOR = Path(__file__).resolve().parent


def _zaman(s: str) -> datetime:
    z = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if z.tzinfo is None:
        raise ValueError(f"saat dilimsiz zaman: {s}")
    return z.astimezone(timezone.utc)


def _kontrol_anahtari(s: str) -> tuple:
    zaman, tip = s.split()
    return ga.kanonik_zaman(_zaman(zaman if len(zaman) > 16 else zaman + ":00+00:00")), tip


def katmanlari_kopyala(kaynak: Path, hedef: Path) -> dict:
    """Arsiv katmanlarini kopyalar; durum dosyasini KOPYALAMAZ (oynatma
    kendi ozetini uretir)."""
    hedef.mkdir(parents=True, exist_ok=True)
    kaynak_f, hedef_f = ga._dosyalar(kaynak), ga._dosyalar(hedef)
    for ad in ("kanonik", "surum"):
        if kaynak_f[ad].exists():
            shutil.copyfile(kaynak_f[ad], hedef_f[ad])
    return hedef_f


def _bayt(f: dict) -> dict:
    return {ad: (p.read_bytes() if p.exists() else None)
            for ad, p in f.items() if ad != "durum"}


def oynat(raporlar: list, alinma: datetime, simdi: datetime, dizin: Path,
          kontroller: list, coz=metar_coz) -> dict:
    """Kopyalanmis katmanlar uzerinde H24 islemesi; rapor sozlugu doner."""
    f = ga._dosyalar(dizin)
    once_satirlar = ga.oku(f["kanonik"])
    once = {(s.get("zaman"), s.get("tip")): s for s in once_satirlar}
    eksik_once = {d["slot"]: d for d in ga.eksik_slotlar(once_satirlar, simdi)}

    sonuc = ga.arsive_isle(raporlar, coz, ga.KAYNAK_BACKFILL, alinma,
                           f["kanonik"], f["surum"])
    sonra_satirlar = ga.oku(f["kanonik"])
    sonra = {(s.get("zaman"), s.get("tip")): s for s in sonra_satirlar}
    yanit = ga._backfill_yaniti(raporlar)
    eksik_sonra = {d["slot"]: d for d in ga.eksik_slotlar(sonra_satirlar, simdi, yanit)}
    surumler = ga.surumleri_oku(f["surum"])
    durum = ga.durum_ozeti(sonra_satirlar, surumler, simdi, coz, yanit)

    # Idempotency: ayni yanit ikinci kez -> hicbir sey eklenmez, bayt bayt ayni.
    once_bayt = _bayt(f)
    ikinci = ga.arsive_isle(raporlar, coz, ga.KAYNAK_BACKFILL, alinma,
                            f["kanonik"], f["surum"])
    idempotent = (_bayt(f) == once_bayt and ikinci["surum_eklenen"] == 0
                  and not ikinci["eklenen_anahtarlar"])

    farkli = set((durum["surum"]["kanonik_ile_ayristirma_farkli"] or {}).get("son", []))
    ayrintilar = []
    for anahtar in kontroller:
        zaman, tip = anahtar
        ayrintilar.append({
            "anahtar": f"{zaman} {tip}",
            "once_kanonikte": anahtar in once,
            "sonra_kanonikte": anahtar in sonra,
            "backfill_kurtarilan": f"{zaman} {tip}" in sonuc["eklenen_anahtarlar"],
            "kanonik_once": once.get(anahtar),
            "kanonik_sonra": sonra.get(anahtar),
            "slot_once": (eksik_once.get(zaman) or {}).get("durum") if tip == "METAR" else None,
            "slot_sonra": (eksik_sonra.get(zaman) or {}).get("durum") if tip == "METAR" else None,
            "surumler": [s for s in surumler if (s.get("zaman"), s.get("tip")) == anahtar],
            "ayristirma_farkli": f"{zaman} {tip}" in farkli,
        })
    return {"yanit": ga.yanit_ozeti(raporlar), "isleme": sonuc, "durum": durum,
            "idempotent": idempotent, "ikinci_isleme": ikinci, "kontroller": ayrintilar,
            "kanonik_once": len(once_satirlar), "kanonik_sonra": len(sonra_satirlar)}


def markdown(baslik: str, r: dict, meta: dict) -> str:
    isl, d = r["isleme"], r["durum"]
    s = [f"## {baslik}", ""]
    for k, v in meta.items():
        s.append(f"- {k}: `{v}`")
    y = r["yanit"]
    s += [f"- yanıt: {y['kayit']} kayıt (METAR {y['METAR']}, SPECI {y['SPECI']}, "
          f"TAF {y['TAF']}), gözlem aralığı {y['en_eski']} → {y['en_yeni']}",
          f"- kanonik satır: {r['kanonik_once']} → {r['kanonik_sonra']}",
          f"- **backfill_kurtarilan** (H24 öncesi kanonikte yok → sonrası var): "
          f"METAR {isl['kanonik_eklenen']['METAR']}, SPECI {isl['kanonik_eklenen']['SPECI']}",
          f"  - {', '.join(isl['eklenen_anahtarlar']) or 'yok'}",
          f"- sürüm eklenen {isl['surum_eklenen']} · mevcut anahtara yeni sürüm "
          f"{isl['mevcut_anahtara_yeni_surum']} · aynı sürüm farklı ham zaman "
          f"{isl['ayni_surum_farkli_ham_zaman']} · aynı sürüm farklı id "
          f"{isl['ayni_surum_farkli_id']} · tip kodu uyuşmazlığı "
          f"{isl['tip_kodu_uyusmazligi']} · çözülemeyen {isl['cozulemeyen']}",
          f"- idempotency (aynı yanıt ikinci kez → 0 ekleme, dosyalar bayt bayt aynı): "
          f"{'evet' if r['idempotent'] else 'HAYIR'}",
          f"- sürüm status dağılımı: `{d['surum']['mgm_status']}` · açıklama "
          f"`{json.dumps(d['surum']['mgm_status_aciklama'], ensure_ascii=False)}`",
          f"- kanonik ile ayrıştırma farklı: "
          f"`{json.dumps(d['surum']['kanonik_ile_ayristirma_farkli'], ensure_ascii=False)}`",
          f"- eksik slot: bekleniyor {d['eksik_slot']['bekleniyor']} · "
          f"backfill_penceresi_disinda {d['eksik_slot']['backfill_penceresi_disinda']}",
          f"  - son: `{json.dumps(d['eksik_slot']['son'][-8:], ensure_ascii=False)}`",
          f"- ingest tablosu: `{json.dumps(d['ingest']['tablo'], ensure_ascii=False)}`",
          ""]
    for k in r["kontroller"]:
        s.append(f"### {k['anahtar']}")
        s.append(f"- kanonikte: önce {'var' if k['once_kanonikte'] else 'yok'} → "
                 f"sonra {'var' if k['sonra_kanonikte'] else 'yok'} · "
                 f"backfill_kurtarilan: {'evet' if k['backfill_kurtarilan'] else 'hayır'}")
        if k["slot_once"] is not None or k["slot_sonra"] is not None or k["anahtar"].endswith("METAR"):
            s.append(f"- ızgara slotu: önce {k['slot_once'] or 'dolu'} → "
                     f"sonra {k['slot_sonra'] or 'dolu'}")
        for ad in ("kanonik_once", "kanonik_sonra"):
            if k[ad]:
                s.append(f"- {ad}: `{json.dumps(k[ad], ensure_ascii=False)}`")
        s.append(f"- kanonik ile ayrıştırma farklı: {'evet' if k['ayristirma_farkli'] else 'hayır'}")
        for v in k["surumler"]:
            s.append(f"- sürüm: zaman_ham `{v.get('zaman_ham')}` · mgm_id `{v.get('mgm_id')}` · "
                     f"status `{v.get('mgm_status')}` · açıklama "
                     f"`{json.dumps(v.get('mgm_status_aciklama'), ensure_ascii=False)}` · "
                     f"type `{v.get('mgm_type')}` · alinma `{v.get('alinma_zamani')}` · "
                     f"kaynak `{v.get('kaynak')}`")
            s.append(f"  - metin: `{v.get('metin')}`")
        s.append("")
    return "\n".join(s)


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    kay = a.add_mutually_exclusive_group(required=True)
    kay.add_argument("--json", type=Path, help="kayıtlı __NEXT_DATA__ yanıtı")
    kay.add_argument("--canli", action="store_true", help="şu anki hours=24 yanıtı")
    a.add_argument("--alinma", help="kayıtlı yanıtın çekim zamanı (ISO, UTC)")
    a.add_argument("--simdi", help="slot sınıflandırması için an (varsayılan: alınma)")
    a.add_argument("--kontrol", action="append", default=[],
                   help='"2026-09-27T16:20 METAR" biçiminde anahtar (tekrarlanabilir)')
    a.add_argument("--klasor", type=Path, default=KLASOR,
                   help="arşiv katmanlarının okunacağı klasör (yalnızca okunur)")
    s = a.parse_args(argv)

    if s.json:
        if not s.alinma:
            a.error("--json için --alinma zorunlu")
        data = json.loads(s.json.read_text(encoding="utf-8"))
        raporlar = rasat.raporlari_ayikla(data, rasat.ICAO, ga.BACKFILL_SAAT)
        alinma = _zaman(s.alinma)
        baslik = f"Kayıttan yeniden oynatma ({s.json.name})"
    else:
        raporlar = rasat.raporlari_cek(rasat.ICAO, saat=ga.BACKFILL_SAAT)
        alinma = datetime.now(timezone.utc)
        baslik = "Canlı H24 kuru çalıştırma"
    simdi = _zaman(s.simdi) if s.simdi else alinma
    kontroller = [_kontrol_anahtari(k) for k in s.kontrol]

    with tempfile.TemporaryDirectory() as tmp:
        katmanlari_kopyala(s.klasor, Path(tmp))
        r = oynat(raporlar, alinma, simdi, Path(tmp), kontroller)
    md = markdown(baslik, r, {"alınma": ga._utc_iso(alinma), "slot anı": ga._utc_iso(simdi),
                              "arşiv kaynağı (salt okunur)": str(s.klasor)})
    print(md)
    ozet = os.environ.get("GITHUB_STEP_SUMMARY")
    if ozet:
        with open(ozet, "a", encoding="utf-8") as f:
            f.write(md + "\n")
    return 0 if r["idempotent"] else 1


if __name__ == "__main__":
    sys.exit(main())
