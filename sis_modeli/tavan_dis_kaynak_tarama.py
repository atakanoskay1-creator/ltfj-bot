#!/usr/bin/env python3
"""Düşük tavan (<500 ft) hedefi için DIŞ KAYNAK adaylarının WoE/IV taraması.

tavan_tarama.py'nin AYNISI, tek farkla: ADAYLAR artık LTFJ METAR'ından değil,
komşu istasyon (LTFM) ve Open-Meteo reanalysis'ten (bkz. veri_birlestir.py)
geliyor. Bu, kullanıcının "daha yüksek kesinlik arıyorum, meteorologlar hangi
verileri kullanıyor" sorusuna somut bir yanıt denemesidir - inversiyon gücü,
komşu istasyon sinyali gibi klasik sis/düşük tavan öngörü değişkenleri.

A PRİORİ ADAY LİSTESİ - sonuçlara BAKILMADAN, veri_birlestir.turet()'in
ürettiği TÜM türetilmiş alanlar dahil edildi (cherry-pick YOK).

Bu tarama SADECE bir keşiftir - herhangi bir aday burada güçlü çıksa bile
tek başına canlıya alma gerekçesi DEĞİLDİR (bkz. sis_modeli/README.md'deki
"tablo çifti güncellendi" bölümünün disiplini: holdout'ta AYRICA doğrulanmalı,
ve büyüklük pratik anlamda değerlendirilmelidir).

Kullanım:
    python -m sis_modeli.tavan_dis_kaynak_tarama
"""

import argparse
import sys
from pathlib import Path

from sis_modeli import bolme, tavan, veri_birlestir, woe
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku

# A priori: veri_birlestir.turet()'in ürettiği türetilmiş alanların TAMAMI.
#
# NOT (2026-09-21, gerçek veriyle doğrulandı): inversiyon_925/850 burada
# KASITLI OLARAK duruyor, silinmedi - "kova kurulamadı" çıktısı BUG DEĞİL,
# bir bulgu: Open-Meteo'nun tarihsel arşiv API'si (archive-api) 925/850hPa
# basınç seviyesi parametrelerini İSİM OLARAK kabul ediyor (hata vermiyor)
# ama tüm 2003-2026 aralığında BOŞ döndürüyor - muhtemelen bu uç nokta
# basınç seviyesi çıktısını hiç desteklemiyor (Forecast API'de olabilir,
# Historical/Archive API'de yok). İnversiyon gücü fikri BU KAYNAKLA
# çalışmıyor; başka bir veri kaynağı gerekiyor (bkz. README).
ADAYLAR = [
    "inversiyon_925", "inversiyon_850",
    "acik_meteo_nem_2m", "acik_meteo_ruzgar_10m", "acik_meteo_bulut_alcak",
    "komsu_sis_var", "komsu_lvo_var", "komsu_tavan_ozellik", "komsu_gorus",
]


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    a.add_argument("--esik", type=int, default=tavan.TABLO_ESIGI_FT)
    a.add_argument("--komsu", type=Path, default=veri_birlestir.VARSAYILAN_KOMSU)
    a.add_argument("--acik-meteo", type=Path,
                   default=veri_birlestir.VARSAYILAN_ACIK_METEO)
    secenek = a.parse_args(argv)
    if not secenek.veri.exists():
        print(f"HATA: {secenek.veri} yok.", file=sys.stderr)
        return 1
    if not secenek.komsu.exists() or not secenek.acik_meteo.exists():
        print(f"HATA: dış kaynak dosyaları eksik ({secenek.komsu}, "
              f"{secenek.acik_meteo}) - önce veri_cek_komsu / "
              "veri_cek_acik_meteo çalıştırılmalı.", file=sys.stderr)
        return 1

    aday = tavan.hazirla(veri_oku(secenek.veri), esik_ft=secenek.esik)
    zengin = veri_birlestir.turet(
        veri_birlestir.zenginlestir(aday, secenek.komsu, secenek.acik_meteo))
    gelistirme = bolme.gelistirme(zengin)
    holdout_ = bolme.holdout(zengin)

    poz = sum(r["hedef"] for r in gelistirme)
    print(f"Hedef: önümüzdeki 3 saat içinde tavan <{secenek.esik} ft (onset)")
    print(f"Dış kaynak kapsamı: komşu istasyon 2018-2026, Open-Meteo 2003-2026 "
          f"- rejim penceresi {tavan.REJIM_ILK_YIL}+ olduğu için komşu verisi "
          f"pencerenin yaklaşık ilk yılında eksik olacak (None -> kova dışı).")
    print(f"Geliştirme evreni: {len(gelistirme)} an, {poz} pozitif "
          f"(%{100*poz/len(gelistirme):.2f})")
    print(f"Holdout evreni:    {len(holdout_)} an, "
          f"{sum(r['hedef'] for r in holdout_)} pozitif\n")

    print(f"{'değişken':<24}{'IV':>8}{'%5–%95':>18}{'mono':>7}{'PSI':>8}  yorum")
    sonuc = []
    for alan in ADAYLAR:
        t = woe.kova_tablosu(gelistirme, alan, "hedef")
        if not t:
            print(f"{alan:<24}{'—':>8}   (kova kurulamadı - veri yok/sabit)")
            continue
        sinirlar = [k["ust"] for k in t[:-1]]
        deger = woe.iv(t)
        alt, ust = woe.iv_guven_araligi(gelistirme, alan, "hedef", "gun",
                                        list(sinirlar), tekrar=200)
        p = woe.psi(gelistirme, holdout_, alan, list(sinirlar))
        print(f"{alan:<24}{deger:>8.3f}{f'{alt:.3f} – {ust:.3f}':>18}"
              f"{'evet' if woe.monoton_mu(t) else 'hayır':>7}{p:>8.3f}"
              f"  {woe.iv_yorumla(deger)}"
              f"{'  ** DAĞILIM KAYMIŞ' if p > 0.25 else ''}")
        sonuc.append((deger, alan, t))

    print("\n=== En güçlü üç dış kaynak adayının kova tabloları ===")
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
