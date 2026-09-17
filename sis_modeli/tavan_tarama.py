#!/usr/bin/env python3
"""Dusuk tavan hedefi icin tek degiskenli WoE/IV taramasi + kararlilik.

Sis modelindeki taramanin aynisi, tek farkla: hedef 'onumuzdeki 3 saat
icinde tavan <500 ft'e dusecek mi' (bkz. sis_modeli/tavan.py).

Cikti uc soruya cevap verir:
  IV            - degisken bilgi tasiyor mu?
  monotonluk    - iliskinin yonu fiziksel olarak anlamli mi?
  PSI           - degiskenin DAGILIMI gelistirme/holdout arasinda kaymis mi?
  blok bootstrap- IV'nin guven araligi (gun bazinda; satir bazinda olcum
                  otokorelasyon yuzunden yalan soyler)

Kullanim:
    python -m sis_modeli.tavan_tarama
"""

import argparse
import sys
from pathlib import Path

from sis_modeli import bolme, tavan, woe
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku

ADAYLAR = [
    "tavan_ozellik", "spread", "gorus", "saat", "ay", "sicaklik",
    "ruzgar_kuzey", "ruzgar_dogu", "ruzgar_hiz",
    "spread_egilim_1", "spread_egilim_3", "qnh_egilim_3",
]


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    a.add_argument("--esik", type=int, default=tavan.TABLO_ESIGI_FT)
    secenek = a.parse_args(argv)
    if not secenek.veri.exists():
        print(f"HATA: {secenek.veri} yok.", file=sys.stderr)
        return 1

    aday = tavan.hazirla(veri_oku(secenek.veri), esik_ft=secenek.esik)
    gelistirme = bolme.gelistirme(aday)
    holdout_ = bolme.holdout(aday)

    poz = sum(r["hedef"] for r in gelistirme)
    gun_poz = len({r["gun"] for r in gelistirme if r["hedef"]})
    print(f"Hedef: önümüzdeki {tavan.__dict__.get('UFUK', 3)} saat içinde "
          f"tavan <{secenek.esik} ft (onset)")
    print(f"Rejim penceresi: {tavan.REJIM_ILK_YIL}+   "
          f"holdout: {'-'.join(map(str, bolme.HOLDOUT_YILLARI))}")
    print(f"Geliştirme evreni: {len(gelistirme)} an, {poz} pozitif "
          f"(%{100*poz/len(gelistirme):.2f}), {gun_poz} ayrı gün")
    print(f"Holdout evreni:    {len(holdout_)} an, "
          f"{sum(r['hedef'] for r in holdout_)} pozitif\n")

    print(f"{'değişken':<18}{'IV':>8}{'%5–%95':>18}{'mono':>7}{'PSI':>8}  yorum")
    sonuc = []
    for alan in ADAYLAR:
        t = woe.kova_tablosu(gelistirme, alan, "hedef")
        if not t:
            print(f"{alan:<18}{'—':>8}   (kova kurulamadı)")
            continue
        sinirlar = [k["ust"] for k in t[:-1]]
        deger = woe.iv(t)
        alt, ust = woe.iv_guven_araligi(gelistirme, alan, "hedef", "gun",
                                        list(sinirlar), tekrar=200)
        p = woe.psi(gelistirme, holdout_, alan, list(sinirlar))
        print(f"{alan:<18}{deger:>8.3f}{f'{alt:.3f} – {ust:.3f}':>18}"
              f"{'evet' if woe.monoton_mu(t) else 'hayır':>7}{p:>8.3f}"
              f"  {woe.iv_yorumla(deger)}"
              f"{'  ** DAĞILIM KAYMIŞ' if p > 0.25 else ''}")
        sonuc.append((deger, alan, t))

    print("\n=== En güçlü üç değişkenin kova tabloları ===")
    for deger, alan, t in sorted(sonuc, reverse=True)[:3]:
        print(f"\n{alan}  (IV {deger:.3f})")
        print(f"  {'aralık':<22}{'n':>8}{'poz':>6}{'oran':>9}{'WoE':>8}")
        for k in t:
            alt = "-∞" if k["alt"] is None else f"{k['alt']:g}"
            ust = "+∞" if k["ust"] is None else f"{k['ust']:g}"
            print(f"  {f'[{alt}, {ust})':<22}{k['n']:>8}{k['pozitif']:>6}"
                  f"{100*k['oran']:>8.2f}%{k['woe']:>8.2f}"
                  f"{'  (kararsız)' if k['kararsiz'] else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
