#!/usr/bin/env python3
"""Model B: TEK genel model mi, yoksa KATMANLI (mevsim/saat) modeller mi?

SORU (Yabra ve ark. 2026, Ezeiza havaalani): veriyi sis olasiligi
yuksek/dusuk aylara ve saatlere bolup AYRI modeller egitmek, tek bir
genel modeli geciyor mu?

Onlarin bulgusu: 2 saat ve uzeri ufuklarda geciyor (2 saatte %20'ye
varan kazanc), 1 saatte GECMIYOR - orada sureklilik baskin oldugu icin
bolme yalnizca ornek sayisini dusuruyor. Bu betik ayni deneyi bu
projenin verisiyle tekrarlar.

ONEMLI FARK: Ezeiza calismasinin en guclu kestiricisi "baslangic
anindaki sis"ti, yani skorlarinin buyuk kismi SUREKLILIK. Bu proje
hedef.onset_adaylari ile sis zaten varken olan satirlari disarida
birakir - yalnizca OLUSUM tahmin edilir. Dolayisiyla buradaki kazanc
(varsa) onlarinkiyle ayni buyuklukte olmak zorunda degil.

SIZINTI KORUMASI: katman sinirlari (hangi aylar/saatler "yuksek")
YALNIZCA O FOLD'UN EGITIM VERISINDEN turetilir. Tum veriden turetmek,
test yillarinin iklimini egitime sizdirirdi.

Her fold'da her katman icin AYRI model egitilir. Bir katmanda egitim
icin yeterli pozitif yoksa o katman icin havuz modeline DUSULUR ve bu
ekrana yazilir - sessizce farkli bir sey yapmayiz.

Holdout HICBIR konfigurasyonda acilmaz.

Kullanim:
    python -m sis_modeli.katmanli_deney
    python -m sis_modeli.katmanli_deney --bootstrap 200
"""

import argparse
from collections import defaultdict
from pathlib import Path

from sis_modeli import bolme, degerlendir, hedef, model
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku
from sis_modeli.olusum_egit import ALANLAR, hava_sutunu_ekle

UFUKLAR_SAAT = (1.0, 2.0, 3.0)

# Bir katmanda ayri model egitmek icin gereken en az pozitif sayisi.
# Altinda kalirsa havuz modeline dusulur: 5 pozitifle egitilmis bir WoE
# tablosu gurultuden ibarettir ve katmanli yaklasimi haksiz yere kotu
# gosterirdi.
KATMAN_MIN_POZITIF = 30


def _etiket(ufuk: float) -> str:
    return f"{int(round(ufuk * 60))}dk" if ufuk < 1 else f"{ufuk:g}h"


# ----------------------------------------------------------- katman tanimlari
def _yuksek_kova(egitim: list, anahtar) -> set:
    """Egitimde taban oranin USTUNDE sis goren kovalar (ay ya da saat).

    Yabra ve ark. bolmeyi iklimsel sis olasiligina gore yapiyor; burada
    da ayni sey, ama SADECE egitim verisinden."""
    toplam, pozitif = defaultdict(int), defaultdict(int)
    for r in egitim:
        k = anahtar(r)
        toplam[k] += 1
        pozitif[k] += int(bool(r["hedef"]))
    n = len(egitim) or 1
    genel = sum(1 for r in egitim if r["hedef"]) / n
    return {k for k in toplam if toplam[k] and pozitif[k] / toplam[k] > genel}


KATMANLAR = {
    "tek": None,
    "mevsim": lambda r: r["dt"].month,
    "saat": lambda r: r["dt"].hour,
}


def _katman_etiketi(r, anahtar, yuksek: set) -> str:
    return "yuksek" if anahtar(r) in yuksek else "dusuk"


# ------------------------------------------------------------- walk-forward
def calistir(ham: list, ufuk_saat: float, katman_adi: str) -> dict:
    """Tek bir (ufuk, katmanlama) kombinasyonu icin walk-forward."""
    kayitlar = hava_sutunu_ekle(hedef.hazirla(ham, ufuk_saat=ufuk_saat))
    gelistirme = bolme.gelistirme(hedef.onset_adaylari(kayitlar))
    anahtar = KATMANLAR[katman_adi]

    gunler, tahmin, gercek = [], [], []
    geri_dusme = 0
    for eg_yillari, test_yillari in bolme.foldlar():
        egitim = bolme.ayir_embargolu(gelistirme, eg_yillari,
                                      sonraki_yil=min(test_yillari))
        test = bolme.ayir(gelistirme, test_yillari)
        if not test or not any(r["hedef"] for r in test):
            continue

        havuz = model.egit_secerek(egitim, ALANLAR)      # her zaman lazim
        if anahtar is None:
            modeller, yuksek = {}, set()
        else:
            yuksek = _yuksek_kova(egitim, anahtar)
            modeller = {}
            for ad in ("yuksek", "dusuk"):
                alt = [r for r in egitim
                       if _katman_etiketi(r, anahtar, yuksek) == ad]
                if sum(1 for r in alt if r["hedef"]) < KATMAN_MIN_POZITIF:
                    geri_dusme += 1
                    continue                              # havuza dusulur
                modeller[ad] = model.egit_secerek(alt, ALANLAR)

        for r in test:
            if anahtar is None:
                k, t, _ = havuz
            else:
                secili = modeller.get(_katman_etiketi(r, anahtar, yuksek))
                k, t, _ = secili if secili else havuz
            gunler.append(r["gun"])
            tahmin.append(model.olasilik(k, r, t))
            gercek.append(bool(r["hedef"]))

    return {"satirlar": (gunler, tahmin, gercek),
            "n": len(gercek), "poz": sum(gercek), "geri_dusme": geri_dusme}


def _lss(tahminler, gercekler):
    n = len(gercekler) or 1
    taban = sum(1 for y in gercekler if y) / n
    return degerlendir.log_skill(tahminler, gercekler, [taban] * len(gercekler))


def _ap_lift(tahminler, gercekler):
    n = len(gercekler) or 1
    taban = sum(1 for y in gercekler if y) / n
    if taban <= 0:
        return 0.0
    return degerlendir.ortalama_kesinlik(tahminler, gercekler) / taban


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    a.add_argument("--bootstrap", type=int, default=0, metavar="TEKRAR",
                   help="katmanli modelleri TEK modele karsi eşli "
                        "gün-blok bootstrap ile kıyasla (önerilen: 200)")
    secenek = a.parse_args(argv)
    if not secenek.veri.exists():
        import sys
        print(f"HATA: {secenek.veri} yok.", file=sys.stderr)
        return 1

    ham = [r for r in veri_oku(secenek.veri) if r["zaman"][:4] >= str(bolme.ILK_YIL)]

    print("Model B — TEK model mi, KATMANLI mı? (holdout AÇILMADI)")
    print(f"Değişkenler: {', '.join(ALANLAR)}")
    print(f"Katman sınırları YALNIZCA fold'un eğitim verisinden türetiliyor; "
          f"bir katmanda <{KATMAN_MIN_POZITIF} pozitif varsa havuz modeline "
          f"düşülür.\n")

    print(f"{'ufuk':>6}{'katman':>9}{'n':>9}{'poz':>6}{'LSS':>9}"
          f"{'AP/taban':>11}{'geri düşme':>12}")
    sonuclar = {}
    for ufuk in UFUKLAR_SAAT:
        for ad in KATMANLAR:
            s = calistir(ham, ufuk, ad)
            sonuclar[(ufuk, ad)] = s
            g, t, y = s["satirlar"]
            print(f"{_etiket(ufuk):>6}{ad:>9}{s['n']:>9}{s['poz']:>6}"
                  f"{_lss(t, y):>9.3f}{_ap_lift(t, y):>11.2f}"
                  f"{s['geri_dusme']:>12}")
        print()

    if secenek.bootstrap:
        for baslik, olcu in (("LSS", _lss), ("AP/taban", _ap_lift)):
            print(f"{baslik} — katmanlı EKSİ tek (eşli gün-blok bootstrap, "
                  f"{secenek.bootstrap} tekrar, %5–%95)")
            print(f"  {'ufuk':<6}{'katman':<9}{'fark':>9}{'aralık':>20}"
                  f"{'katmanlı>tek':>14}  karar")
            for ufuk in UFUKLAR_SAAT:
                seriler = {ad: sonuclar[(ufuk, ad)]["satirlar"]
                           for ad in KATMANLAR}
                _ar, farklar = degerlendir.esli_blok_guven_araligi(
                    seriler, olcu, tekrar=secenek.bootstrap)
                for ad in ("mevsim", "saat"):
                    cift = (ad, "tek") if (ad, "tek") in farklar else ("tek", ad)
                    alt, ust, orta, oran = farklar[cift]
                    if cift == ("tek", ad):      # yonu cevir
                        alt, ust, orta, oran = -ust, -alt, -orta, 1 - oran
                    karar = "belirsiz" if alt <= 0 <= ust else "AYIRT EDİLİR"
                    print(f"  {_etiket(ufuk):<6}{ad:<9}{orta:>9.3f}"
                          f"{f'[{alt:.3f}, {ust:.3f}]':>20}"
                          f"{f'%{100*oran:.1f}':>14}  {karar}")
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
