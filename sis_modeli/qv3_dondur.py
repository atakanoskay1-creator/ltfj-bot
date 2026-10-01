#!/usr/bin/env python3
"""QV3 modellerini DONDURUR: gelistirme donemi (2012-2023) tamamiyla
egitilir ve veri/qv3_donmus.json'a yazilir. Holdout (2024-2026) bu adimda
HIC kullanilmaz; qv3_holdout.py yalnizca bu dosyayi okur.

Dondurulanlar (hepsi ayni kurallarla, sonuclara bakilmadan):
  gbm       - asil model: GBM, agac sayisi 2023'te secildi, Platt + izotonik
              kalibrasyon 2021-2023'un donem-disi tahminleriyle
  woe       - QV3 WoE lojistik, degiskenler ileri secimle (ic dogrulama 2023)
  model_a   - Model A'nin 5 degiskeni, ayni hedefte
  iklim     - ay x saat taban orani
  gorus     - mevcut gorus bandina gore taban orani

QV3 CANLIYA BAGLANMAZ.

Kullanim (repo kokunden, ~3 dk):
    python -m sis_modeli.qv3_dondur
"""

import json
from datetime import date
from pathlib import Path

from sis_modeli import bolme, model, qv3_egit, qv3_gbm, qv3_hedef, qv3_model
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku

DONMUS_DOSYA = Path(__file__).resolve().parent / "veri" / "qv3_donmus.json"


def dondur(gelistirme: list) -> dict:
    k = qv3_gbm.egit_kalibreli(gelistirme)
    secim = qv3_model.ileri_secim(gelistirme)
    beta, tablolar, l2 = qv3_model.egit(gelistirme, secim["secilen"])
    beta_a, tablolar_a, l2_a = qv3_model.egit(gelistirme, qv3_model.MODEL_A_ALANLARI)
    iklim, iklim_genel = model.iklim_baseline(gelistirme)
    gorus, gorus_genel = qv3_egit.gorus_iklimi(gelistirme)
    yillar = sorted({r["dt"].year for r in gelistirme})
    return {
        "aciklama": "QV3 - LVO Hazirlik Safhasi'na 3 saat icinde gecis. CANLIDA DEGIL.",
        "egitim_yillari": [yillar[0], yillar[-1]],
        "olusturma": date.today().isoformat(),
        "gbm": {"model": k["model"], "agac": k["agac"], "platt": list(k["platt"]),
                "izotonik": k["izotonik"], "kalibrasyon_n": k["kalibrasyon_n"]},
        "woe": {"alanlar": secim["secilen"], "katsayilar": beta, "tablolar": tablolar, "l2": l2},
        "model_a": {"alanlar": list(qv3_model.MODEL_A_ALANLARI), "katsayilar": beta_a,
                    "tablolar": tablolar_a, "l2": l2_a},
        "iklim": {"tablo": [[a, s, p] for (a, s), p in sorted(iklim.items())],
                  "genel": iklim_genel},
        "gorus": {"tablo": [[b, p] for b, p in gorus.items()], "genel": gorus_genel},
    }


def yaz(donmus: dict, yol: Path = DONMUS_DOSYA) -> None:
    yol.write_text(json.dumps(donmus, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")


def oku(yol: Path = DONMUS_DOSYA) -> dict:
    return json.loads(Path(yol).read_text(encoding="utf-8"))


def tahminler(donmus: dict, kayit: dict) -> dict:
    """Bir kayit icin tum dondurulmus modellerin olasiliklari."""
    g = donmus["gbm"]
    ham = qv3_gbm.olasilik(g["model"], kayit)
    w, a = donmus["woe"], donmus["model_a"]
    iklim = {(ay, saat): p for ay, saat, p in donmus["iklim"]["tablo"]}
    gorus = {b: p for b, p in donmus["gorus"]["tablo"]}
    return {
        "GBM + Platt": qv3_gbm.platt_uygula(ham, g["platt"]),
        "GBM ham": ham,
        "QV3 WoE": model.olasilik(w["katsayilar"], kayit, w["tablolar"]),
        "Model A seti": model.olasilik(a["katsayilar"], kayit, a["tablolar"]),
        "görüş bandı iklimi": gorus.get(qv3_egit.gorus_bandi(kayit.get("gorus")),
                                        donmus["gorus"]["genel"]),
        "ay×saat iklimi": iklim.get((kayit["ay"], kayit["saat"]), donmus["iklim"]["genel"]),
    }


def main() -> int:
    aday = qv3_model.aday_ekle(qv3_hedef.veri_hazirla(veri_oku(VARSAYILAN_VERI),
                                                      qv3_hedef.rvr_oku()))
    gelistirme = bolme.gelistirme(aday)
    donmus = dondur(gelistirme)
    yaz(donmus)
    g = donmus["gbm"]
    print(f"Donduruldu -> {DONMUS_DOSYA} ({DONMUS_DOSYA.stat().st_size // 1024} KB)")
    print(f"  eğitim {donmus['egitim_yillari']}, {len(gelistirme)} an")
    print(f"  GBM: {g['agac']} ağaç, Platt a={g['platt'][0]:.3f} b={g['platt'][1]:+.3f} "
          f"({g['kalibrasyon_n']} kalibrasyon anı)")
    print(f"  QV3 WoE: {', '.join(donmus['woe']['alanlar'])} (L2 {donmus['woe']['l2']:g})")
    print("  GBM önem: " + ", ".join(f"{a} {v:.0%}" for a, v in qv3_gbm.onem(g["model"])[:10]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
