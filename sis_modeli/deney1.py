#!/usr/bin/env python3
"""Sis modeli V2 - Deney 1: V2a / V2b / V2c (V2_PROTOKOL.md §7-§9).

Hedefin teknik adi: LTFJ dusuk gorus/FG olayi.

Protokol 1.0 spesifikasyonunun birebir uygulamasi. Yeni degisken, etkilesim,
30 dk egilim ya da aday YOKTUR.

  V2a = gv60 + spread + spread_egilim_3 + saat + ruzgar_kuzey
  V2b = V2a + dspread_1sa
  V2c = V2b + egilim120 (anlik gorusle caprazlanmaz)

Egitim ve test ayrimi (sizinti kilidi): bir dis fold'un butun egitim
artefaktlari (WoE tablolari, gv60 hucre kaynaklari, tek boyutlu tablolar,
yeterlilik kararlari, olay sayimlari, lambda secimi, katsayilar, V1 referansi)
YALNIZCA o fold'un egitim yillarindan uretilir; test yillarinin hicbir
kaydina bakilmaz (testle kilitli).

UYGULAMA AYRINTILARI (protokolun acikca yazmadigi, sonuclara bakilmadan
secilen; rapora yazilir):
  U1. V2x lojistik fit'i, gerekli tam gecikmeleri bulunan egitim satirlarinda
      yapilir (gecikmesiz satirda gv60 tanimsiz). WoE tablolarinin H'si
      (sozde koddaki "E'nin tamami") butun E satirlaridir.
  U2. V2x'in ic dogrulama havuzlanmis LL'si, ic dogrulama blogunun V2x'in
      uygulanabildigi (gecikmeleri tam) satirlarinda hesaplanir. Gecikmesiz
      satirlarda hibrit tahmin V1'dir ve V2x'in lambda'sina bagli degildir.
  U3. "Gecikme eksik": gereken zaman damgasinda kayit yok YA DA o kayitta
      gereken alan (gorus; V2b/c'de spread) bos. Deney 0: ikincisi 0 satir.
  U4. Ilk alarm suresi koruma sarti: olay basina (V2 - V1) farkinin
      medyani; olay bootstrap'inde %5 alt siniri >= -30 dk. [KULLANICI ONAYI
      BEKLIYOR - bkz. rapor]
"""

import argparse
import math
import random
import sys
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

from sis_modeli import bolme, degerlendir, hedef, model, v1_benchmark, v2_cozucu, v2_evren
from sis_modeli.deney0_veri_denetimi import meteo_gun, olay_ata, sn_var, ufuk_slotlari
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku
from sis_modeli.olay_degerlendirme import bagimsiz_olaylar

# ------------------------------------------------ dondurulmus sabitler ---
INCE_BANT = (1000, 1500, 3000, 5000, 8000, 9999)      # §7.2 / §7.6
ANLIK_BANT = (3000, 5000, 9999)                        # 1000-3000/3000-5000/5000-9999/>=9999
EGILIM_SINIFLARI = ("iyilesen_sabit", "1_bant", "2+_bant")
DSPREAD_KOVALARI = ("<=-2", "-1", "0", "+1", ">=+2")
YETERLI_SATIR, YETERLI_POZ, YETERLI_OLAY = 500, 10, 5  # §7.5
DUZELTME = 0.5                                         # Haldane-Anscombe (woe.DUZELTME)
ORTAK = ["ruzgar_kuzey", "saat", "spread", "spread_egilim_3"]
VARYANTLAR = {
    "V2a": ("gv60",),
    "V2b": ("gv60", "dspread_1sa"),
    "V2c": ("gv60", "dspread_1sa", "egilim120"),
}
GECIKMELER = {"V2a": (60,), "V2b": (60,), "V2c": (60, 120)}
BOOTSTRAP_TEKRAR = 2000                                # §5
BIRINCIL_ALFA = 0.05 / 3                               # §8: tek tarafli %98,33
KORUMA_ALFA = 0.05                                     # §9.1: %5 alt sinir
KORUMA_YAKALAMA = -0.05                                # -5 puan
KORUMA_SURE_DK = -30.0                                 # -30 dk
BANT_ESIGI = v1_benchmark.BANT_ESIGI                   # 5 x dondurulmus V1 taban orani


# ------------------------------------------------------ degiskenler ---
def ince_indeks(g) -> int:
    return sum(1 for e in INCE_BANT if g >= e)


def anlik_bant(g) -> int:
    return sum(1 for e in ANLIK_BANT if g >= e)


def egilim(g_t, g_gecmis) -> str:
    d = ince_indeks(g_t) - ince_indeks(g_gecmis)
    return "iyilesen_sabit" if d >= 0 else ("1_bant" if d == -1 else "2+_bant")


def dspread_kovasi(d) -> str:
    if d <= -2:
        return "<=-2"
    if d <= -1:
        return "-1"
    if d < 1:
        return "0"
    if d < 2:
        return "+1"
    return ">=+2"


def gecikmeleri_ekle(kayitlar: list, onset: list) -> None:
    """Onset satirlarina tam-zaman gecikme degerlerini ekler (en yakin gozlem
    YOK): _g60, _g120, _s60 (kayit yoksa ya da alan bossa None)."""
    yer = {r["dt"]: r for r in kayitlar}
    for r in onset:
        k60 = yer.get(r["dt"] - timedelta(minutes=60))
        k120 = yer.get(r["dt"] - timedelta(minutes=120))
        r["_g60"] = k60.get("gorus") if k60 else None
        r["_s60"] = k60.get("spread") if k60 else None
        r["_g120"] = k120.get("gorus") if k120 else None


def uygun(r: dict, varyant: str) -> bool:
    """§7.4: varyantin gerektirdigi tam gecikmeler mevcut mu (U3)."""
    if r.get("gorus") is None or r.get("_g60") is None:
        return False
    if "dspread_1sa" in VARYANTLAR[varyant] and (r.get("_s60") is None or r.get("spread") is None):
        return False
    if 120 in GECIKMELER[varyant] and r.get("_g120") is None:
        return False
    return True


def ham_kategoriler(r: dict) -> dict:
    """Uygun bir satirin yeni degisken kategorileri."""
    c = {"bant": anlik_bant(r["gorus"]), "e60": egilim(r["gorus"], r["_g60"])}
    if r.get("_s60") is not None and r.get("spread") is not None:
        c["ds"] = dspread_kovasi(r["spread"] - r["_s60"])
    if r.get("_g120") is not None:
        c["e120"] = egilim(r["gorus"], r["_g120"])
    return c


# ------------------------------------------------ olay atamasi (§5.1) ---
def olay_atamalari(egitim_tam: list, satirlar: list) -> dict:
    """Pozitif satir -> olay indeksi. Olaylar YALNIZCA egitim_tam (egitim
    yillarinin tam izgara kaydi) uzerinde bolutlenir; satir, (t, t+3sa]
    penceresindeki ILK olay gozleminin olayina atanir."""
    olaylar = bagimsiz_olaylar(egitim_tam, etiket="sis", bosluk_saat=3.0)
    yer = {r["dt"]: i for i, r in enumerate(egitim_tam)}
    atama = {}
    for r in satirlar:
        if not r["hedef"]:
            continue
        idx = ufuk_slotlari(yer, r["dt"])
        ilk = next((egitim_tam[j] for j in idx if egitim_tam[j]["sis"]), None)
        atama[r["dt"]] = olay_ata(olaylar, ilk["dt"]) if ilk is not None else None
    return atama


# --------------------------------------------------- WoE / yeterlilik ---
def woe(h_poz, h_neg, H_poz, H_neg, k) -> float:
    return math.log(((h_poz + DUZELTME) / (H_poz + DUZELTME * k))
                    / ((h_neg + DUZELTME) / (H_neg + DUZELTME * k)))


class _Sayac:
    __slots__ = ("n", "poz", "olay")

    def __init__(self):
        self.n, self.poz, self.olay = 0, 0, set()

    def ekle(self, r, atama):
        self.n += 1
        if r["hedef"]:
            self.poz += 1
            o = atama.get(r["dt"])
            if o is not None:
                self.olay.add(o)

    def yeterli(self) -> bool:
        return self.n >= YETERLI_SATIR and self.poz >= YETERLI_POZ and len(self.olay) >= YETERLI_OLAY


def tablolar_kur(E: list, egitim_tam: list, varyant: str) -> dict:
    """Bir egitim kumesinden V2x'in butun tablolarini kurar (§7.5, §7.6).
    E: ambargolu egitim onset satirlari; egitim_tam: ayni egitim yillarinin
    tam izgara kaydi (olay bolutlemesi icin)."""
    atama = olay_atamalari(egitim_tam, E)
    H_poz = sum(1 for r in E if r["hedef"])
    H_neg = len(E) - H_poz
    v1_tab = model.woe_tablolari(E, v1_benchmark.ALANLAR)
    ortak = {a: v1_tab[a] for a in ORTAK if a in v1_tab}
    hucre = defaultdict(_Sayac)
    bant = defaultdict(_Sayac)
    ds, e120 = defaultdict(_Sayac), defaultdict(_Sayac)
    for r in E:
        if r.get("gorus") is not None:
            bant[anlik_bant(r["gorus"])].ekle(r, atama)
        if r.get("gorus") is not None and r.get("_g60") is not None:
            c = ham_kategoriler(r)
            hucre[(c["bant"], c["e60"])].ekle(r, atama)
            if "ds" in c:
                ds[c["ds"]].ekle(r, atama)
            if "e120" in c:
                e120[c["e120"]].ekle(r, atama)

    def _w(s, k):
        return woe(s.poz, s.n - s.poz, H_poz, H_neg, k)

    gv60 = {}
    for b in range(len(ANLIK_BANT) + 1):
        for e in EGILIM_SINIFLARI:
            h = hucre[(b, e)]
            if h.yeterli():
                gv60[(b, e)] = ("hucre", _w(h, 12))
            elif bant[b].yeterli():
                gv60[(b, e)] = ("bant", _w(bant[b], 4))
            else:
                gv60[(b, e)] = ("v1_gorus", None)
    t = {"ortak": ortak, "v1_gorus": v1_tab.get("gorus"), "gv60": gv60,
         "sayim": {"hucre": {k: (v.n, v.poz, len(v.olay)) for k, v in hucre.items()},
                   "bant": {k: (v.n, v.poz, len(v.olay)) for k, v in bant.items()}}}
    if "dspread_1sa" in VARYANTLAR[varyant]:
        t["dspread_1sa"] = {k: (_w(ds[k], len(DSPREAD_KOVALARI)) if ds[k].yeterli() else 0.0)
                            for k in DSPREAD_KOVALARI}
        t["sayim"]["dspread_1sa"] = {k: (ds[k].n, ds[k].poz, len(ds[k].olay)) for k in DSPREAD_KOVALARI}
    if "egilim120" in VARYANTLAR[varyant]:
        t["egilim120"] = {k: (_w(e120[k], len(EGILIM_SINIFLARI)) if e120[k].yeterli() else 0.0)
                          for k in EGILIM_SINIFLARI}
        t["sayim"]["egilim120"] = {k: (e120[k].n, e120[k].poz, len(e120[k].olay))
                                   for k in EGILIM_SINIFLARI}
    return t


def desen(r: dict, t: dict, varyant: str) -> tuple:
    """Uygun satirin WoE vektoru: ORTAK (V1 davranisi, eksik -> 0), gv60,
    dspread_1sa, egilim120 - sabit sira."""
    x = [model._woe_degeri(t["ortak"][a], r.get(a)) if a in t["ortak"] else 0.0 for a in ORTAK]
    c = ham_kategoriler(r)
    kaynak, w = t["gv60"][(c["bant"], c["e60"])]
    if kaynak == "v1_gorus":
        w = model._woe_degeri(t["v1_gorus"], r["gorus"]) if t["v1_gorus"] else 0.0
    x.append(w)
    if "dspread_1sa" in VARYANTLAR[varyant]:
        x.append(t["dspread_1sa"][c["ds"]])
    if "egilim120" in VARYANTLAR[varyant]:
        x.append(t["egilim120"][c["e120"]])
    return tuple(x)


def _topla(satirlar, t, varyant):
    top, poz = Counter(), Counter()
    for r in satirlar:
        d = desen(r, t, varyant)
        top[d] += 1
        poz[d] += int(bool(r["hedef"]))
    ds = list(top)
    return ds, [top[d] for d in ds], [poz[d] for d in ds]


def olasilik(beta, x) -> float:
    eta = beta[0] + sum(b * xi for b, xi in zip(beta[1:], x))
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, eta))))


# ------------------------------------------------------ egitim (§6) ---
def _tam_kayit(kayitlar, bas, bit):
    return [r for r in kayitlar if bas <= r["dt"].year < bit]


def ic_dogrulama(kayitlar: list, E: list, test_bas: int, varyant: str,
                 cozucu=v2_cozucu.egit, adaylar=model.L2_ADAYLARI) -> dict:
    """§6 ic dogrulama, V2x icin (U2)."""
    ll_top = {l2: 0.0 for l2 in adaylar}
    n_top, elenen, bloklar = 0, {}, []
    for y in v1_benchmark.ic_bloklar(test_bas):
        ic_eg = bolme.embargo_penceresi([r for r in E if r["dt"].year < y], y)
        t = tablolar_kur(ic_eg, _tam_kayit(kayitlar, bolme.ILK_YIL, y), varyant)
        d, top, poz = _topla([r for r in ic_eg if uygun(r, varyant)], t, varyant)
        val = [r for r in E if r["dt"].year == y and uygun(r, varyant)]
        xs = [desen(r, t, varyant) for r in val]
        gercek = [bool(r["hedef"]) for r in val]
        bloklar.append({"yil": y, "ic_egitim_uygun": sum(top), "dogrulama_uygun": len(val),
                        "dogrulama_poz": sum(gercek)})
        n_top += len(val)
        for l2 in adaylar:
            if l2 in elenen:
                continue
            try:
                beta = cozucu(d, top, poz, l2=l2)
            except (model.TekilSistem, model.Yakinsamadi) as e:
                elenen[l2] = f"{y}: {type(e).__name__}"
                continue
            ll_top[l2] += v1_benchmark._ll_toplam([olasilik(beta, x) for x in xs], gercek)
    havuz = {l2: (None if l2 in elenen or not n_top else ll_top[l2] / n_top) for l2 in adaylar}
    return {"bloklar": bloklar, "havuz_ll": havuz, "elenen": elenen,
            "secilen": v1_benchmark.l2_sec(havuz)}


def fold_egit(kayitlar: list, onset: list, test_bas: int, varyant: str,
              cozucu=v2_cozucu.egit) -> dict:
    """Bir dis fold'un V2x egitim artefaktlari. YALNIZCA test_bas oncesi
    yillar kullanilir (sizinti kilidi)."""
    E = bolme.ayir_embargolu(onset, tuple(range(bolme.ILK_YIL, test_bas)), test_bas)
    egitim_tam = _tam_kayit(kayitlar, bolme.ILK_YIL, test_bas)
    ic = ic_dogrulama(kayitlar, E, test_bas, varyant, cozucu)
    t = tablolar_kur(E, egitim_tam, varyant)
    d, top, poz = _topla([r for r in E if uygun(r, varyant)], t, varyant)
    try:
        beta = cozucu(d, top, poz, l2=ic["secilen"])
    except (model.TekilSistem, model.Yakinsamadi) as e:
        raise v1_benchmark.SpesifikasyonBasarisiz(f"{varyant} {test_bas}: nihai egitim: {e}") from e
    return {"varyant": varyant, "ic": ic, "tablolar": t, "katsayilar": beta,
            "egitim_uygun": sum(top), "egitim": len(E)}


def hibrit_tahmin(T: list, v2: dict, v1_tahmin: list, varyant: str) -> tuple:
    """§7.4 gelistirme: uygun satirda V2x, degilse AYNI fold'un V1 referansi."""
    out, kullanildi = [], []
    for r, p1 in zip(T, v1_tahmin):
        if uygun(r, varyant):
            out.append(olasilik(v2["katsayilar"], desen(r, v2["tablolar"], varyant)))
            kullanildi.append(True)
        else:
            out.append(p1)
            kullanildi.append(False)
    return out, kullanildi


# --------------------------------------------------------- bootstrap ---
def dll_bootstrap(satirlar: list, p1: list, p2: list, gercek: list,
                  tekrar: int = BOOTSTRAP_TEKRAR, tohum: int = 0) -> list:
    """Meteorolojik gun eslestirilmis bootstrap: ΔLL = LL(V1) - LL(V2)
    ornekleri (sirali)."""
    gun = defaultdict(lambda: [0.0, 0.0, 0])
    for r, a, b, y in zip(satirlar, p1, p2, gercek):
        g = gun[meteo_gun(r["dt"])]
        g[0] += v1_benchmark._ll_toplam([a], [y])
        g[1] += v1_benchmark._ll_toplam([b], [y])
        g[2] += 1
    anahtar = sorted(gun)
    c1 = [gun[k][0] for k in anahtar]
    c2 = [gun[k][1] for k in anahtar]
    cn = [gun[k][2] for k in anahtar]
    D = len(anahtar)
    rs = random.Random(tohum)
    import operator
    ornek = []
    for _ in range(tekrar):
        say = Counter(rs.choices(range(D), k=D))
        w = [say.get(i, 0) for i in range(D)]
        n = sum(map(operator.mul, w, cn))
        ornek.append((sum(map(operator.mul, w, c1)) - sum(map(operator.mul, w, c2))) / n)
    ornek.sort()
    return ornek


def alt_sinir(ornek: list, alfa: float) -> float:
    """Tek tarafli (1 - alfa) alt siniri: alfa yuzdeligi."""
    return ornek[int(math.floor(alfa * len(ornek)))]


def olay_bootstrap(yak1: list, yak2: list, tekrar: int = BOOTSTRAP_TEKRAR,
                   tohum: int = 0) -> tuple:
    """Olay bootstrap'i (§5, §9.1). yak1/yak2: ayni olay sirasinda V1 ve V2
    olay_yakalama kayitlari (degerlendirilebilir olaylar). Doner (sirali):
    (yakalama farki, olay basina fark medyani [U4, karar], medyanlar farki
    [alternatif okuma, yalniz tanilama]) ornekleri."""
    n = len(yak1)
    rs = random.Random(tohum)
    fy, fs, fm = [], [], []
    for _ in range(tekrar):
        idx = [rs.randrange(n) for _ in range(n)]
        fy.append(sum(yak2[i]["yakalandi"] - yak1[i]["yakalandi"] for i in idx) / n)
        fs.append(_medyan([yak2[i]["sure_dk"] - yak1[i]["sure_dk"] for i in idx]))
        fm.append(_medyan([yak2[i]["sure_dk"] for i in idx]) - _medyan([yak1[i]["sure_dk"] for i in idx]))
    return sorted(fy), sorted(fs), sorted(fm)


def _medyan(d):
    d = sorted(d)
    n = len(d)
    return (d[n // 2] if n % 2 else (d[n // 2 - 1] + d[n // 2]) / 2) if n else 0.0


# ------------------------------------------------------------- rapor ---
_t, _o, _l2, _fold_ad = v1_benchmark._t, v1_benchmark._o, v1_benchmark._l2, v1_benchmark._fold_ad


def _dll_satiri(ad, satirlar, p1, p2, y, alfa=BIRINCIL_ALFA):
    if not satirlar:
        return [ad, 0, 0, "—", "—", "—"]
    ll1, ll2 = degerlendir.log_loss(p1, y), degerlendir.log_loss(p2, y)
    ornek = dll_bootstrap(satirlar, p1, p2, y)
    return [ad, len(satirlar), sum(1 for v in y if v), f"{ll1 - ll2:+.6f}",
            f"{alt_sinir(ornek, alfa):+.6f}", f"{ornek[len(ornek) // 2]:+.6f}"]


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    s = a.parse_args(argv)
    if not s.veri.exists():
        print(f"HATA: {s.veri} yok.", file=sys.stderr)
        return 1

    kayitlar = v2_evren.gelistirme_kayitlari(veri_oku(s.veri))
    onset = hedef.onset_adaylari(kayitlar)
    gecikmeleri_ekle(kayitlar, onset)
    yer = {r["dt"]: i for i, r in enumerate(kayitlar)}
    tam_ufuk = {r["dt"] for r in onset if len(ufuk_slotlari(yer, r["dt"])) == hedef.ADIM_SAYISI}
    pencere_sn = {r["dt"] for r in onset
                  if any(sn_var(kayitlar[j]) for j in ufuk_slotlari(yer, r["dt"]))}

    foldlar = v1_benchmark.BIRINCIL_FOLDLAR + v1_benchmark.TANILAMA_FOLDLARI
    v1 = {f: v1_benchmark.fold_calistir(kayitlar, onset, f) for f in foldlar}
    v2 = {(f, v): fold_egit(kayitlar, onset, f[0], v) for f in foldlar for v in VARYANTLAR}
    hib = {}
    for f in foldlar:
        for v in VARYANTLAR:
            hib[(f, v)] = hibrit_tahmin(v1[f]["test_satirlar"], v2[(f, v)], v1[f]["tahmin"], v)

    def havuz(v, foldlar_=v1_benchmark.BIRINCIL_FOLDLAR, secici=lambda r: True):
        R, P1, P2, Y, IK, K = [], [], [], [], [], []
        for f in foldlar_:
            x = v1[f]
            p2, kul = hib[(f, v)] if v else (x["tahmin"], [False] * len(x["tahmin"]))
            for r, a1, a2, y, ik, k in zip(x["test_satirlar"], x["tahmin"], p2, x["gercek"],
                                           x["iklim"], kul):
                if secici(r):
                    R.append(r), P1.append(a1), P2.append(a2), Y.append(y), IK.append(ik), K.append(k)
        return R, P1, P2, Y, IK, K

    print("# Deney 1 — V2a / V2b / V2c (çıktı)\n")
    print(f"Evren: {len(kayitlar)} ızgara satırı, {len(onset)} onset satırı. Çözücü: sönümlü "
          f"Newton. Bootstrap: {BOOTSTRAP_TEKRAR} tekrar, tohum 0. Birincil karar: 5 dış fold "
          "havuzlanmış, geri dönüş dahil.\n")

    # --- birincil tablo
    print("## 1. Birincil sonuç (§8) — beş dış fold havuzlanmış OOS\n")
    rows = []
    R, P1, _, Y, IK, _ = havuz(None)
    m1 = v1_benchmark.olcutler(P1, Y, IK)
    rows.append(["V1 referansı", " / ".join(_l2(v1[f]["ic"]["secilen"]) for f in v1_benchmark.BIRINCIL_FOLDLAR),
                 "—", _o(m1["ll"], 6), "—", "—", _o(m1["ap"], 3), f"{1e4 * m1['brier']:.2f}",
                 _o(m1["lss"]), ""])
    karar = {}
    for v in VARYANTLAR:
        R, P1, P2, Y, IK, K = havuz(v)
        m2 = v1_benchmark.olcutler(P2, Y, IK)
        ornek = dll_bootstrap(R, P1, P2, Y)
        dll = m1["ll"] - m2["ll"]
        lb = alt_sinir(ornek, BIRINCIL_ALFA)
        karar[v] = {"dll": dll, "lb": lb, "birincil": lb > 0}
        rows.append([v, " / ".join(_l2(v2[(f, v)]["ic"]["secilen"]) for f in v1_benchmark.BIRINCIL_FOLDLAR),
                     f"{100 * sum(K) / len(K):.2f}", _o(m2["ll"], 6), f"{dll:+.6f}", f"{lb:+.6f}",
                     _o(m2["ap"], 3), f"{1e4 * m2['brier']:.2f}", _o(m2["lss"]),
                     "geçti" if lb > 0 else "geçmedi"])
    print(_t(["model", "λ (fold 1–5)", "coverage_V2 %", "LL (nat)", "ΔLL = LL(V1)−LL(V2)",
              "tek taraflı %98,33 alt sınır", "AP", "Brier×10⁴", "LSS", "birincil kural"], rows))
    print("\nLL/AP/Brier/LSS V2 satırlarında hibrit sistemin (geri dönüş dahil) değerleridir. "
          "LSS referansı her fold'un yalnız eğitim satırlarından kurulan ay × saat iklimi.\n")

    # --- koruma sartlari
    print("## 2. Koruma şartları (§9.1) — olay bootstrap'i\n")
    print(f"Bant eşiği = 5 × dondurulmuş V1 taban oranı = {100 * BANT_ESIGI:.3f}%. Olay: "
          "başlangıçtan önceki 3 saatteki onset satırlarından birinde tahmin ≥ eşik. İlk alarm "
          "süresi: ilk alarm → başlangıç (yakalanmayan olay 0 dk). Koruma: yakalama farkı "
          "(V2 − V1) %5 alt sınırı ≥ −5 puan; olay başına ilk alarm farkının (V2 − V1) medyanı "
          "için %5 alt sınır ≥ −30 dk (U4).\n")
    rows = []
    yakalama_kayit = {}
    for v in VARYANTLAR:
        y1, y2 = [], []
        for f in v1_benchmark.BIRINCIL_FOLDLAR:
            x = v1[f]
            tz1 = {r["dt"]: p for r, p in zip(x["test_satirlar"], x["tahmin"])}
            tz2 = {r["dt"]: p for r, p in zip(x["test_satirlar"], hib[(f, v)][0])}
            a1 = v1_benchmark.olay_yakalama(x["test_olaylar"], tz1)
            a2 = v1_benchmark.olay_yakalama(x["test_olaylar"], tz2)
            sn_bayrak = [False] * len(x["test_olaylar"])
            for r in kayitlar:
                if r["dt"].year in f and r["sis"] and sn_var(r):
                    i = olay_ata(x["test_olaylar"], r["dt"])
                    if i is not None:
                        sn_bayrak[i] = True
            for e1, e2, sn in zip(a1, a2, sn_bayrak):
                if e1["satir"]:
                    y1.append(e1), y2.append(e2)
                    yakalama_kayit.setdefault(v, []).append((e1, e2, sn))
        fy, fs, fm = olay_bootstrap(y1, y2)
        c1 = sum(e["yakalandi"] for e in y1) / len(y1)
        c2 = sum(e["yakalandi"] for e in y2) / len(y2)
        md = _medyan([b["sure_dk"] - a["sure_dk"] for a, b in zip(y1, y2)])
        lb_y, lb_s = alt_sinir(fy, KORUMA_ALFA), alt_sinir(fs, KORUMA_ALFA)
        lb_m = alt_sinir(fm, KORUMA_ALFA)
        gecti = lb_y >= KORUMA_YAKALAMA and lb_s >= KORUMA_SURE_DK
        alternatif = lb_y >= KORUMA_YAKALAMA and lb_m >= KORUMA_SURE_DK
        karar[v]["koruma"] = gecti
        rows.append([v, len(y1), f"{100 * c1:.1f}", f"{100 * c2:.1f}", f"{100 * (c2 - c1):+.1f}",
                     f"{100 * lb_y:+.1f}", f"{_medyan([e['sure_dk'] for e in y1]):.0f}",
                     f"{_medyan([e['sure_dk'] for e in y2]):.0f}", f"{md:+.0f}", f"{lb_s:+.0f}",
                     "geçti" if gecti else "geçmedi", f"{lb_m:+.0f}",
                     ("aynı" if alternatif == gecti else "**FARKLI**")])
    print(_t(["varyant", "olay", "yakalama V1 %", "yakalama V2 %", "fark (puan)",
              "fark %5 alt sınır", "medyan ilk alarm V1 (dk)", "medyan V2 (dk)",
              "olay başına fark medyanı (dk)", "%5 alt sınır (dk)", "koruma",
              "alt. okuma: medyanlar farkı %5 alt sınır (dk)", "alt. okumayla karar"], rows))
    print("\nSon iki sütun yalnız tanılamadır: §9.1'in \"medyan fark\" ifadesinin diğer okuması "
          "(medyan(V2) − medyan(V1)). Karar U4'e göre verilir; iki okuma farklı sonuç verirse "
          "burada \"FARKLI\" yazar ve kullanıcıya getirilir.")

    # --- secim
    print("\n## 3. Seçim (§8)\n")
    gecen = [v for v in VARYANTLAR if karar[v]["birincil"] and karar[v]["koruma"]]
    for v in VARYANTLAR:
        print(f"- {v}: birincil {'geçti' if karar[v]['birincil'] else 'geçmedi'}, koruma "
              f"{'geçti' if karar[v]['koruma'] else 'geçmedi'} (ΔLL {karar[v]['dll']:+.6f}).")
    if gecen:
        sec = max(gecen, key=lambda v: karar[v]["dll"])
        print(f"\n**Seçilen tek spesifikasyon: {sec}** (geçenler arasında en büyük nokta ΔLL).\n")
    else:
        print("\n**Hiçbir varyant geçmedi. Deney 1 kapanır** (§8).\n")

    # --- tanilamalar
    print("## 4. Tanılamalar (karar vermez)\n")
    print("ΔLL = LL(V1) − LL(V2 hibrit); alt sınır tek taraflı %98,33 (karşılaştırılabilirlik "
          "için); medyan = bootstrap medyanı.\n")
    for baslik, sec_ in (
            ("### 4.1 Yalnız V2'nin çalıştığı satırlar (§9.2)", None),
            ("### 4.2 Penceresinde SN olmayan satırlar (§9.3)", lambda r: r["dt"] not in pencere_sn),
            ("### 4.3 Ufku tam (6/6) satırlar (Deney 0 §7.2)", lambda r: r["dt"] in tam_ufuk)):
        print(baslik + "\n")
        rows = []
        for v in VARYANTLAR:
            if sec_ is None:
                R, P1, P2, Y, _, K = havuz(v)
                idx = [i for i, k in enumerate(K) if k]
                R, P1, P2, Y = ([L[i] for i in idx] for L in (R, P1, P2, Y))
            else:
                R, P1, P2, Y, _, _ = havuz(v, secici=sec_)
            rows.append(_dll_satiri(v, R, P1, P2, Y))
        print(_t(["varyant", "satır", "Y=1", "ΔLL", "tek taraflı %98,33 alt sınır",
                  "bootstrap medyanı"], rows))
        print()
    print("### 4.4 Olay düzeyi SN tanılaması (§9.3) — yakalama\n")
    rows = []
    for v in VARYANTLAR:
        for ad, sec_ in (("tümü", None), ("≥ 1 SN", True), ("SN'siz", False)):
            L = []
            for e1, e2, sn in yakalama_kayit[v]:
                if sec_ is None or sn == sec_:
                    L.append((e1, e2))
            if L:
                rows.append([v, ad, len(L), f"{100 * sum(a['yakalandi'] for a, _ in L) / len(L):.1f}",
                             f"{100 * sum(b['yakalandi'] for _, b in L) / len(L):.1f}"])
    print(_t(["varyant", "olay grubu", "olay", "yakalama V1 %", "yakalama V2 %"], rows))
    print("\n### 4.5 Fold başına ΔLL ve 2015–16 erken dönem tanılaması\n")
    rows = []
    for v in VARYANTLAR:
        for f in foldlar:
            R, P1, P2, Y, _, K = havuz(v, foldlar_=(f,))
            m1_ = degerlendir.log_loss(P1, Y)
            m2_ = degerlendir.log_loss(P2, Y)
            rows.append([v, _fold_ad(f) + ("" if f in v1_benchmark.BIRINCIL_FOLDLAR else " (tanılama)"),
                         _l2(v2[(f, v)]["ic"]["secilen"]), f"{100 * sum(K) / len(K):.2f}",
                         _o(m1_, 6), _o(m2_, 6), f"{m1_ - m2_:+.6f}"])
    print(_t(["varyant", "fold", "λ", "coverage %", "LL V1", "LL V2 hibrit", "ΔLL"], rows))

    # --- artefaktlar
    print("\n## 5. Eğitim artefaktları (§7.5 — her fold'da hücre kaynakları)\n")
    for v in VARYANTLAR:
        for f in foldlar:
            x = v2[(f, v)]
            print(f"### {v} — {_fold_ad(f)}\n")
            ic = x["ic"]
            en_iyi = min(val for val in ic["havuz_ll"].values() if val is not None)
            esit = sorted(l2 for l2, val in ic["havuz_ll"].items()
                          if val is not None and val - en_iyi <= v1_benchmark.ESITLIK_TOLERANSI)
            print(_t(["λ", "havuzlanmış iç LL (uygun satırlar)", "en iyiden fark", "eleme"],
                     [[_l2(l2), _o(ic["havuz_ll"][l2], 6) if ic["havuz_ll"][l2] is not None else "elendi",
                       "—" if ic["havuz_ll"][l2] is None else f"{ic['havuz_ll'][l2] - en_iyi:.2e}",
                       ic["elenen"].get(l2, "")] for l2 in model.L2_ADAYLARI]))
            print(f"\n1e-4 içinde eşit: {{{', '.join(_l2(z) for z in esit)}}} → seçilen λ={_l2(ic['secilen'])}. "
                  f"Eğitim satırı {x['egitim']}, V2 fit'ine giren (uygun) {x['egitim_uygun']}.\n")
            t = x["tablolar"]
            bant_ad = ["1000–3000", "3000–5000", "5000–9999", "≥9999"]
            rows = []
            for b in range(4):
                for e in EGILIM_SINIFLARI:
                    kaynak, w = t["gv60"][(b, e)]
                    n, p, o = t["sayim"]["hucre"].get((b, e), (0, 0, 0))
                    rows.append([bant_ad[b], e, n, p, o, kaynak, _o(w, 3) if w is not None else "V1 gorus WoE"])
            print(_t(["anlık bant", "60 dk eğilim", "satır", "Y=1", "olay", "kaynak", "WoE"], rows))
            for ad in ("dspread_1sa", "egilim120"):
                if ad in t:
                    print(f"\n`{ad}`: " + "; ".join(
                        f"{k}: n={t['sayim'][ad][k][0]}, Y=1={t['sayim'][ad][k][1]}, olay={t['sayim'][ad][k][2]}, "
                        f"WoE={t[ad][k]:.3f}" for k in t[ad]))
            print("\nKatsayılar (sabit, " + ", ".join(ORTAK + list(VARYANTLAR[v])) + "): "
                  + ", ".join(f"{b:.3f}" for b in x["katsayilar"]) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
