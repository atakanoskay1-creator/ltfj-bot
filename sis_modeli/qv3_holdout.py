#!/usr/bin/env python3
"""QV3 NIHAI HOLDOUT (2024-2026) - TEK ATIS.

Dondurulmus modeller (veri/qv3_donmus.json, qv3_dondur.py) holdout
yillarinda degerlendirilir. Olcutler ve karsilastirmalar holdout
acilmadan ONCE QV3_RAPOR.md'ye yazildi ("Holdout protokolu"); bu betik
yalnizca onlari hesaplar. Holdout sonucuna bakilarak model AYARLANMAZ.

Kullanim (repo kokunden):
    python -m sis_modeli.qv3_holdout
"""

from datetime import timedelta

from sis_modeli import bolme, degerlendir, qv3_dondur, qv3_hedef, qv3_model
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku

ESIKLER = (0.10, 0.20, 0.30)
ASIL = "GBM + Platt"


def olaylar(kayitlar: list, gercek: list) -> list:
    """Pozitif hedef anlarinin bloklari (1 saatten kisa bosluk ayni olay)."""
    sonuc, onceki = [], None
    for i, (r, y) in enumerate(zip(kayitlar, gercek)):
        if not y:
            continue
        if sonuc and onceki is not None and r["dt"] - kayitlar[onceki]["dt"] <= timedelta(hours=1):
            sonuc[-1].append(i)
        else:
            sonuc.append([i])
        onceki = i
    return sonuc


def esik_satiri(kayitlar, p, g, olay, esik) -> dict:
    uyari = [i for i, x in enumerate(p) if x >= esik]
    return {"esik": esik,
            "olay_yakalanan": sum(any(p[i] >= esik for i in o) for o in olay),
            "olay": len(olay),
            "uyari_gunu": len({kayitlar[i]["dt"].date() for i in uyari}),
            "isabet": sum(g[i] for i in uyari) / len(uyari) if uyari else 0.0}


def main() -> int:
    donmus = qv3_dondur.oku()
    aday = qv3_model.aday_ekle(qv3_hedef.veri_hazirla(veri_oku(VARSAYILAN_VERI),
                                                      qv3_hedef.rvr_oku()))
    test = bolme.holdout(aday)
    g = [bool(r["hedef"]) for r in test]
    tahmin = {}
    for r in test:
        for ad, p in qv3_dondur.tahminler(donmus, r).items():
            tahmin.setdefault(ad, []).append(p)
    olay = olaylar(test, g)
    gunler = [r["gun"] for r in test]
    iklim = tahmin["ay×saat iklimi"]
    print(f"HOLDOUT {min(r['dt'] for r in test):%Y-%m-%d} - {max(r['dt'] for r in test):%Y-%m-%d}: "
          f"{len(test)} an, {sum(g)} pozitif (%{100 * sum(g) / len(g):.2f}), {len(olay)} olay, "
          f"{len(set(gunler))} gün\n")
    for ad, p in tahmin.items():
        print(f"  {ad:<20} AP {degerlendir.ortalama_kesinlik(p, g):.3f}  "
              f"AUC {degerlendir.roc_auc(p, g):.3f}  Brier {degerlendir.brier(p, g):.5f}  "
              f"BSS {degerlendir.brier_skill(p, g, iklim):+.3f}  ort. %{100 * sum(p) / len(p):.2f}")

    print("\nYıl bazında AP:")
    for yil in sorted({r["dt"].year for r in test}):
        idx = [i for i, r in enumerate(test) if r["dt"].year == yil]
        gy = [g[i] for i in idx]
        print(f"  {yil}: {sum(gy)} pozitif  " + "  ".join(
            f"{ad} {degerlendir.ortalama_kesinlik([tahmin[ad][i] for i in idx], gy):.3f}"
            for ad in (ASIL, "QV3 WoE", "Model A seti", "görüş bandı iklimi")))

    seriler = {ad: (gunler, tahmin[ad], g) for ad in (ASIL, "QV3 WoE", "Model A seti")}
    araliklar, farklar = degerlendir.esli_blok_guven_araligi(
        seriler, degerlendir.ortalama_kesinlik, tekrar=500)
    print("\nAP %5-%95 aralığı (gün blok bootstrap, 500 tekrar):")
    for ad, (alt, ust) in araliklar.items():
        print(f"  {ad:<20} {alt:.3f} - {ust:.3f}")
    for (a, b), (alt, ust, med, oran) in farklar.items():
        print(f"  {a} - {b}: medyan {med:+.3f}, aralık {alt:+.3f} … {ust:+.3f}, "
              f"pozitif replika %{100 * oran:.0f}")

    print(f"\nUyarı eşikleri ({ASIL}):")
    for e in ESIKLER:
        s = esik_satiri(test, tahmin[ASIL], g, olay, e)
        print(f"  %{100 * e:.0f}: olay {s['olay_yakalanan']}/{s['olay']} "
              f"(%{100 * s['olay_yakalanan'] / max(s['olay'], 1):.0f}), "
              f"uyarı günü {s['uyari_gunu']}/{len(set(gunler))}, isabet %{100 * s['isabet']:.0f}")
    print(f"\nGüvenilirlik ({ASIL}): " + "; ".join(
        f"{k['ortalama_tahmin']:.0%}->{k['gerceklesen']:.0%} (n={k['n']})"
        for k in degerlendir.guvenilirlik(tahmin[ASIL], g, kova_sayisi=10) if k["n"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
