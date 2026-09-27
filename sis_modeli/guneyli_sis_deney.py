#!/usr/bin/env python3
"""Model A guneyli sisi HAFIFE aliyor mu?

SORU: sis_iklim.py guneyli (140-250 derece, >2 kt) sisin nadir ama en
uzun/yogun tip oldugunu buldu. Dondurulmus Model A'nin ruzgar_kuzey WoE
tablosu guney bilesenini sis ALEYHINE puanliyor (en guneyli kova -2.45).
Toplamda dogru olabilir, ama guneyli ruzgarda tahmin edilen olasilik
gerceklesenin altinda kaliyor mu?

VERI: yuruyen pencere (egit.py ile BIREBIR ayni foldlar ve ayni
_fold_calistir) - her test yili yalnizca kendi gecmisiyle egitilmis
modelle tahmin edilir. NIHAI HOLDOUT (2024-2026) ACILMAZ: holdout daha
once iki kez kullanildi ve bu bir kesif sorusu.

OLCULER (sonuclara bakmadan ONCE yazildi):
  1) Kalibrasyon orani = gerceklesen oran / ortalama tahmin, tahmin
     anindaki ruzgara gore (guneyli / diger). 1 = kalibre, >1 = hafife
     alma. %5-%95 araligi gun-blok bootstrap (200 tekrar).
  2) Olay duzeyi: her bagimsiz sis baslangicindan onceki 3 saatteki
     (onset evrenindeki) EN YUKSEK tahmin. Olay, sisli gozlemlerinin
     cogunlugu guneyli ise "guneyli" sayilir (sis_iklim ile ayni kural).
     Sayfadaki bantlarin esikleri (taban oranin 2 ve 5 kati: "orta" ve
     "yuksek") ile karsilastirilir.

KARAR KURALI (onceden ilan):
  - "HAFIFE ALIYOR" ancak guneyli kalibrasyon oraninin %5 alt siniri 1'in
    USTUNDEYSE denir.
  - Guneyli olay sayisi 10'un altindaysa olay duzeyi sonuc YALNIZCA
    betimleyicidir; tek basina karar gerekcesi yapilmaz.
  - Sonuc ne olursa olsun bu betik DONDURULMUS MODELI DEGISTIRMEZ.
    Degisiklik yeni bir aday + holdout protokolu gerektirir.

Kullanim:
    python -m sis_modeli.guneyli_sis_deney
"""

import argparse
import random
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import ltfj_sis_olasilik as sis_olasilik

from sis_modeli import bolme, egit, hedef
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku

GUNEY_ARALIK = (140, 250)
SAKIN_KT = 2
ONCESI_SAAT = 3
# Sayfadaki bantlar: taban oranin 2 ve 5 kati "orta" ve "yuksek"
# (ltfj_sayfa._sis_olasiligi_html). Eslik ayni kaynaktan - elle yazilan
# yuzdeler sayfayla sessizce ayrisirdi.
BANT_KATLARI = (2, 5)
BANT_ESIKLERI = tuple(k * sis_olasilik.TABAN_ORAN for k in BANT_KATLARI)
ASGARI_OLAY = 10


def guneyli(r: dict) -> bool:
    yon, hiz = r.get("ruzgar_yon"), r.get("ruzgar_hiz")
    return (yon is not None and hiz is not None and hiz > SAKIN_KT
            and GUNEY_ARALIK[0] <= yon <= GUNEY_ARALIK[1])


def kalibrasyon_orani(tahminler: list, gercekler: list) -> float:
    """gerceklesen oran / ortalama tahmin (bos ya da sifir tahminde 0)."""
    if not tahminler:
        return 0.0
    ort = sum(tahminler) / len(tahminler)
    return (sum(gercekler) / len(gercekler)) / ort if ort else 0.0


def blok_aralik(kayitlar: list, tahminler: list, gercekler: list,
                tekrar: int = 200, tohum: int = 0) -> tuple:
    """Kalibrasyon oraninin %5-%95 araligi, GUN bazinda blok bootstrap."""
    gunler = defaultdict(list)
    for r, p, y in zip(kayitlar, tahminler, gercekler):
        gunler[r["gun"]].append((p, y))
    anahtarlar = list(gunler)
    if not anahtarlar:
        return (0.0, 0.0)
    rastgele = random.Random(tohum)
    sonuc = []
    for _ in range(tekrar):
        p_l, y_l = [], []
        for _ in anahtarlar:
            for p, y in gunler[rastgele.choice(anahtarlar)]:
                p_l.append(p)
                y_l.append(y)
        sonuc.append(kalibrasyon_orani(p_l, y_l))
    sonuc.sort()
    return sonuc[int(0.05 * tekrar)], sonuc[min(int(0.95 * tekrar), tekrar - 1)]


def olaylar(kayitlar: list) -> list:
    """Bagimsiz sis olaylari: ardisik sisli gozlemler (<= 61 dk aralik).
    Doner: [(baslangic_dt, guneyli_mi), ...]"""
    sisli = [r for r in kayitlar if r["sis"]]
    gruplar = []
    for r in sisli:
        if gruplar and r["dt"] - gruplar[-1][-1]["dt"] <= timedelta(minutes=61):
            gruplar[-1].append(r)
        else:
            gruplar.append([r])
    return [(g[0]["dt"], sum(guneyli(r) for r in g) * 2 > len(g)) for g in gruplar]


def olay_oncesi_tepe(olay_listesi: list, tahmin_zamani: dict) -> list:
    """Her olay icin baslangictan onceki ONCESI_SAAT saatteki en yuksek
    tahmin. Onunde hic tahmin olmayan (test disi / veri boslugu) olaylar
    atlanir. Doner: [(tepe, guneyli_mi), ...]"""
    sonuc = []
    for bas, g in olay_listesi:
        adaylar = [p for dt, p in tahmin_zamani.items()
                   if bas - timedelta(hours=ONCESI_SAAT) <= dt < bas]
        if adaylar:
            sonuc.append((max(adaylar), g))
    return sonuc


def _medyan(d: list) -> float:
    d = sorted(d)
    return d[len(d) // 2] if d else 0.0


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    s = a.parse_args(argv)
    if not s.veri.exists():
        print(f"HATA: {s.veri} yok.", file=sys.stderr)
        return 1

    ham = [r for r in veri_oku(s.veri) if r["zaman"][:4] >= str(bolme.ILK_YIL)]
    kayitlar = hedef.hazirla(ham)
    gelistirme = bolme.gelistirme(hedef.onset_adaylari(kayitlar))

    test_kayit, tahmin, gercek, test_yillari_tumu = [], [], [], set()
    for egitim_yillari, test_yillari in bolme.foldlar():
        eg = bolme.ayir(gelistirme, egitim_yillari)
        te = bolme.ayir(gelistirme, test_yillari)
        if not te or not any(r["hedef"] for r in te):
            continue
        sonuc = egit._fold_calistir(eg, te)
        test_kayit += sonuc["test"]
        tahmin += sonuc["tahmin"]["model"]
        gercek += sonuc["gercek"]
        test_yillari_tumu.update(test_yillari)

    ilk, son = min(test_yillari_tumu), max(test_yillari_tumu)
    print(f"Yürüyen pencere test yılları {ilk}–{son} (holdout açılmadı): "
          f"{len(test_kayit)} an, {sum(gercek)} pozitif\n")

    print("1) KALİBRASYON — tahmin anındaki rüzgâra göre")
    print(f"  {'grup':<10}{'an':>8}{'poz':>6}{'ort.tahmin':>12}{'gerçekleşen':>13}"
          f"{'oran':>7}{'%5–%95':>16}")
    gruplar = {"güneyli": [], "diğer": []}
    for i, r in enumerate(test_kayit):
        gruplar["güneyli" if guneyli(r) else "diğer"].append(i)
    for ad, idx in gruplar.items():
        k = [test_kayit[i] for i in idx]
        p = [tahmin[i] for i in idx]
        y = [gercek[i] for i in idx]
        oran = kalibrasyon_orani(p, y)
        alt, ust = blok_aralik(k, p, y)
        print(f"  {ad:<10}{len(k):>8}{sum(y):>6}{100*sum(p)/len(p):>11.2f}%"
              f"{100*sum(y)/len(y):>12.2f}%{oran:>7.2f}   {alt:>5.2f} – {ust:<5.2f}")

    print(f"\n2) OLAY DÜZEYİ — başlangıçtan önceki {ONCESI_SAAT} saatteki en yüksek tahmin")
    tahmin_zamani = {r["dt"]: p for r, p in zip(test_kayit, tahmin)}
    ol = [o for o in olaylar(kayitlar) if o[0].year in test_yillari_tumu]
    tepe = olay_oncesi_tepe(ol, tahmin_zamani)
    print(f"  {'grup':<10}{'olay':>6}{'medyan tepe':>13}"
          + "".join(f"{'≥' + str(k) + 'x':>8}" for k in BANT_KATLARI))
    for ad, g in (("güneyli", True), ("diğer", False)):
        t = [x for x, gg in tepe if gg is g]
        if not t:
            print(f"  {ad:<10}{0:>6}")
            continue
        print(f"  {ad:<10}{len(t):>6}{100*_medyan(t):>12.1f}%"
              + "".join(f"{100*sum(x >= e for x in t)/len(t):>7.0f}%" for e in BANT_ESIKLERI))
    n_g = sum(1 for _, g in tepe if g)
    if n_g < ASGARI_OLAY:
        print(f"  (güneyli olay {n_g} < {ASGARI_OLAY}: olay düzeyi YALNIZCA betimleyici)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
