#!/usr/bin/env python3
"""Sis gun dogumundan ne kadar sonra kalkiyor? Salt okuma iklimbilimi.

SORU (operasyonel): "Gun dogdu, meydan hala sisli - gorus ne zaman 1000 m'nin
ustune cikar?" Bu bir MODEL DEGIL; gecmiste ne oldugunu sayar.

YONTEM:
  - Sis olaylari gorus_gecis.olaylari_bul() ile (Tardif & Rasmussen 2007
    tanimi; ayni modulun 30 dk izgara ve kar haric tutma kurallari gecerli).
  - Kalkis ani: olayin son <1000 m gozleminden SONRAKI ilk gozlem
    (gorus >= 1000 m). Arada AZAMI_BOSLUK_DK'dan uzun delik varsa olay
    kalkis olcumune girmez - deligin icinde ne oldugu bilinmiyor.
  - Gun dogumu: ltfj_pist._gunes_saatleri (sayfadaki gun/gece ile ayni
    hesap, UTC).
  - Asil soru icin evren: gun dogumu aninda SIS SURUYOR olan olaylar
    (ilk <1000 m gozlemi gun dogumundan once/esit, son <1000 m gozlemi
    gun dogumundan sonra/esit).

30 dakikalik izgara nedeniyle sureler ~30 dk cozunurluktedir.

Kullanim (repo kokunden):
    python -m sis_modeli.sis_kalkis
"""

from datetime import timedelta, timezone

from ltfj_pist import _gunes_saatleri
from sis_modeli import gorus_gecis as gg

ESIKLER_SAAT = (1, 2, 3, 4)


def gun_dogumu(dt):
    """Naif UTC zamanin ait oldugu gunun gun dogumu (naif UTC)."""
    saatler = _gunes_saatleri(dt.replace(tzinfo=timezone.utc))
    return saatler[0].replace(tzinfo=None) if saatler else None


def kalkis_kayitlari(satirlar: list, olaylar: list) -> list[dict]:
    """Gun dogumunda suren olaylar icin kalkisin gun dogumuna gore gecikmesi.

    Doner: {"sis_bas", "kalkis", "gun_dogumu", "gecikme_dk", "yagisli"}"""
    out = []
    for o in olaylar:
        son_i = o["sis_son_i"]
        if son_i + 1 >= len(satirlar):
            continue
        sonraki = satirlar[son_i + 1]
        if (sonraki["dt"] - satirlar[son_i]["dt"]) > timedelta(minutes=gg.AZAMI_BOSLUK_DK):
            continue
        sis_bas = satirlar[o["sis_bas_i"]]["dt"]
        sis_son = satirlar[son_i]["dt"]
        dogum = gun_dogumu(sis_son)
        if dogum is None or not (sis_bas <= dogum <= sis_son):
            continue
        out.append({
            "sis_bas": sis_bas, "kalkis": sonraki["dt"], "gun_dogumu": dogum,
            "gecikme_dk": round((sonraki["dt"] - dogum).total_seconds() / 60),
            "yagisli": o["yagisli"],
        })
    return out


def kalkmis_payi(gecikmeler_dk: list, esikler_saat=ESIKLER_SAAT) -> dict:
    """Gun dogumundan sonraki her esikte sisin kalkmis oldugu olay yuzdesi."""
    n = len(gecikmeler_dk)
    return {h: (round(100 * sum(1 for g in gecikmeler_dk if g <= 60 * h) / n, 1) if n else None)
            for h in esikler_saat}


def main(argv=None) -> int:
    satirlar = gg.veri_oku(gg.VARSAYILAN_VERI)
    satirlar = [s for s in satirlar if s["dt"].year >= 2011]
    olaylar = gg.olaylari_bul(satirlar)
    kayitlar = kalkis_kayitlari(satirlar, olaylar)

    print(f"Sis olayı (2011+): {len(olaylar)}; gün doğumunda süren ve kalkışı "
          f"ölçülebilen: {len(kayitlar)}")
    if not kayitlar:
        return 0
    gruplar = {"tümü": kayitlar}
    yagisli = [k for k in kayitlar if k["yagisli"]]
    if 0 < len(yagisli) < len(kayitlar):    # tek sinifsa ayri satir tekrar olur
        gruplar["yağışsız"] = [k for k in kayitlar if not k["yagisli"]]
        gruplar["yağışlı"] = yagisli
    gruplar["Eki–Mar"] = [k for k in kayitlar if k["gun_dogumu"].month in (10, 11, 12, 1, 2, 3)]
    gruplar["Nis–Eyl"] = [k for k in kayitlar if k["gun_dogumu"].month in (4, 5, 6, 7, 8, 9)]
    print(f"Öncesinde (3 sa) yağış görülen olay: {len(yagisli)}/{len(kayitlar)}")
    print("\nGün doğumundan sonra kalkış gecikmesi (dakika) ve kalkmış olma payı:")
    print(f"  {'grup':<10}{'n':>5}{'%25':>7}{'medyan':>8}{'%75':>7}{'%90':>7}"
          + "".join(f"{f'≤{h} sa':>8}" for h in ESIKLER_SAAT))
    for ad, grup in gruplar.items():
        if not grup:
            continue
        g = [k["gecikme_dk"] for k in grup]
        pay = kalkmis_payi(g)
        print(f"  {ad:<10}{len(g):>5}{gg.yuzdelik(g, 0.25):>7.0f}{gg.yuzdelik(g, 0.50):>8.0f}"
              f"{gg.yuzdelik(g, 0.75):>7.0f}{gg.yuzdelik(g, 0.90):>7.0f}"
              + "".join(f"{f'%{pay[h]:.0f}':>8}" for h in ESIKLER_SAAT))
    print(f"\n{gg.cozunurluk_notu(satirlar)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
