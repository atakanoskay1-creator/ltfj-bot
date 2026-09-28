#!/usr/bin/env python3
"""Deney 1 - merge oncesi audit (AUDIT-ONLY; karar degistirmez).

V2a/b/c'nin basarisizlik karari, protokol kriterleri ve spesifikasyonlar
DEGISMEZ. Yeni aday (V2d) uretilmez. Bu betik yalnizca betimler:

  1) V1'in fold bazindaki `gorus` WoE kovalari ile gv60'in 4 anlik bandi.
  2) Ayni anlik bant icinde 60 dk egilim sinifina gore hedef orani / WoE.
  3) V1 - V2 log-loss farkinin gorus araliklarina dagilimi (OOS test).
  4) >=9999 bandinda dusus hucrelerinin neden bos oldugu.
  5) dspread_1sa: WoE siralamasi ile lojistik katsayinin isareti
     (kodlama / es-dogrusallik; meteorolojik yorum YOK).

Deney 1 artefaktlari diske yazilmadigi icin fold modelleri, Deney 1'in
dondurulmus proseduruyle (commit 4483836) deterministik olarak yeniden
uretilir. Ayni modellerin elde edildigi, raporlanan havuzlanmis LL/ΔLL
degerleriyle birebir eslesme uzerinden dogrulanir (bkz. cikti §0).
Hicbir yeni model spesifikasyonu, lambda ya da kural denenmez.

Kullanim:
    python -m sis_modeli.deney1_audit > audit.md
"""

import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path

from sis_modeli import deney1, degerlendir, hedef, v1_benchmark, v2_evren
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku

BANT_AD = ("1000–3000", "3000–5000", "5000–9999", "≥9999")
INCE_AD = ("< 1000", "1000–1500", "1500–3000", "3000–5000", "5000–8000", "8000–9999", "≥9999")
# Deney 1 raporundaki (878da38) havuzlanmis degerler - yeniden uretim kontrolu
RAPOR_LL = {"V1": 0.027349, "V2a": 0.027690, "V2b": 0.027664, "V2c": 0.027677}

_t, _o = v1_benchmark._t, v1_benchmark._o


def _ll1(p, y):
    p = min(max(p, 1e-9), 1 - 1e-9)
    return -math.log(p) if y else -math.log(1 - p)


def _bant_araligi(b):
    alt = 1000 if b == 0 else deney1.ANLIK_BANT[b - 1]
    ust = deney1.ANLIK_BANT[b] if b < len(deney1.ANLIK_BANT) else None
    return alt, ust


def v1_kova_ozeti(tablo: list) -> list:
    """V1 gorus WoE kovalarini anlik bantlara gore siniflar. Bir kova bir
    bandin icinde mi, yoksa bant sinirini mi asiyor - ikisi ayri sayilir."""
    satir = []
    for b in range(4):
        b_alt, b_ust = _bant_araligi(b)
        icinde, asan = [], []
        for k in tablo:
            k_alt = k["alt"] if k["alt"] is not None else -math.inf
            k_ust = k["ust"] if k["ust"] is not None else math.inf
            if k_ust <= b_alt or (b_ust is not None and k_alt >= b_ust):
                continue
            tam = k_alt >= b_alt and (b_ust is None or k_ust <= b_ust)
            (icinde if tam else asan).append(k)
        satir.append((b, icinde, asan))
    return satir


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    s = a.parse_args(argv)
    if not s.veri.exists():
        print(f"HATA: {s.veri} yok.", file=sys.stderr)
        return 1

    kayitlar = v2_evren.gelistirme_kayitlari(veri_oku(s.veri))
    onset = hedef.onset_adaylari(kayitlar)
    deney1.gecikmeleri_ekle(kayitlar, onset)
    foldlar = v1_benchmark.BIRINCIL_FOLDLAR
    v1 = {f: v1_benchmark.fold_calistir(kayitlar, onset, f) for f in foldlar}
    v2 = {(f, v): deney1.fold_egit(kayitlar, onset, f[0], v) for f in foldlar for v in deney1.VARYANTLAR}
    hib = {(f, v): deney1.hibrit_tahmin(v1[f]["test_satirlar"], v2[(f, v)], v1[f]["tahmin"], v)
           for f in foldlar for v in deney1.VARYANTLAR}

    print("# Deney 1 — merge öncesi audit (çıktı; audit-only)\n")

    # 0) yeniden uretim kontrolu
    print("## 0. Yeniden üretim kontrolü\n")
    Y = [y for f in foldlar for y in v1[f]["gercek"]]
    rows = [["V1", _o(degerlendir.log_loss([p for f in foldlar for p in v1[f]["tahmin"]], Y), 6),
             _o(RAPOR_LL["V1"], 6)]]
    for v in deney1.VARYANTLAR:
        rows.append([v, _o(degerlendir.log_loss([p for f in foldlar for p in hib[(f, v)][0]], Y), 6),
                     _o(RAPOR_LL[v], 6)])
    print(_t(["model", "yeniden üretilen havuzlanmış LL", "Deney 1 raporundaki"], rows))
    print("\nλ (V1 / V2a / V2b / V2c): " + "; ".join(
        f"{v1_benchmark._fold_ad(f)}: {v1_benchmark._l2(v1[f]['ic']['secilen'])} / "
        + " / ".join(v1_benchmark._l2(v2[(f, v)]["ic"]["secilen"]) for v in deney1.VARYANTLAR)
        for f in foldlar) + "\n")

    # 1) V1 gorus kovalari vs gv60 bantlari
    print("## 1. V1 `gorus` WoE kovaları ile gv60'ın dört anlık bandı\n")
    print("V1 kovaları her fold'un ambargolu eğitim satırlarından (`woe.kova_tablosu`). "
          "\"Bant içinde\": kova tamamen o anlık bandın içinde. \"Sınırı aşan\": kova bant "
          "sınırını kesiyor (iki banda birden düşüyor). gv60 bant WoE'si: aynı eğitim "
          "satırlarından eğilimden bağımsız bant WoE'si (k=4).\n")
    for f in foldlar:
        tab = v1[f]["tablolar"]["gorus"]
        t2 = v2[(f, "V2a")]["tablolar"]
        E_poz = v1[f]["egitim_poz"]
        E_neg = v1[f]["egitim"] - E_poz
        print(f"### {v1_benchmark._fold_ad(f)}\n")
        print(_t(["V1 kova", "satır", "Y=1", "oran %", "WoE"],
                 [[f"{'—' if k['alt'] is None else int(k['alt'])} – {'—' if k['ust'] is None else int(k['ust'])}",
                   k["n"], k["pozitif"], f"{100 * k['oran']:.3f}", f"{k['woe']:+.3f}"] for k in tab]))
        rows = []
        for b, icinde, asan in v1_kova_ozeti(tab):
            n, p, _ = t2["sayim"]["bant"].get(b, (0, 0, 0))
            w_b = deney1.woe(p, n - p, E_poz, E_neg, 4) if n else None
            ws = [k["woe"] for k in icinde + asan]
            rows.append([BANT_AD[b], len(icinde), len(asan),
                         f"{min(ws):+.3f} … {max(ws):+.3f}" if ws else "—",
                         f"{max(ws) - min(ws):.3f}" if ws else "—",
                         f"{w_b:+.3f}" if w_b is not None else "—", n, p])
        print()
        print(_t(["anlık bant", "V1 kovası (bant içinde)", "V1 kovası (sınırı aşan)",
                  "V1 WoE aralığı", "V1 WoE ayrımı (maks−min)", "gv60 bant WoE (eğilimsiz)",
                  "bant satırı", "bant Y=1"], rows))
        print()

    # 2) bant icinde egilim
    print("## 2. Aynı anlık bant içinde 60 dk eğilim — hedef oranı ve WoE (betimsel)\n")
    print("Eğitim satırları (her fold'un ambargolu eğitimi, gecikmesi tam). WoE: gv60 hücre "
          "formülü (k=12). Model seçmez.\n")
    for f in foldlar:
        t2 = v2[(f, "V2a")]["tablolar"]
        E_poz = v1[f]["egitim_poz"]
        E_neg = v1[f]["egitim"] - E_poz
        rows = []
        for b in range(4):
            taban = None
            for e in deney1.EGILIM_SINIFLARI:
                n, p, o = t2["sayim"]["hucre"].get((b, e), (0, 0, 0))
                oran = p / n if n else None
                if e == "iyilesen_sabit":
                    taban = oran
                w = deney1.woe(p, n - p, E_poz, E_neg, 12) if n else None
                rows.append([BANT_AD[b], e, n, p, o, f"{100 * oran:.3f}" if oran is not None else "—",
                             f"{oran / taban:.2f}" if oran and taban else "—",
                             f"{w:+.3f}" if w is not None else "—", t2["gv60"][(b, e)][0]])
        print(f"### {v1_benchmark._fold_ad(f)}\n")
        print(_t(["anlık bant", "60 dk eğilim", "satır", "Y=1", "olay", "oran %",
                  "oran / (iyileşen-sabit)", "WoE", "gv60 kaynağı"], rows))
        print()

    # OOS test satirlarinda da ayni betimleme (havuzlanmis)
    print("**Havuzlanmış OOS test satırları (2017–2026), gecikmesi tam olanlar:**\n")
    say = defaultdict(lambda: [0, 0])
    for f in foldlar:
        for r in v1[f]["test_satirlar"]:
            if deney1.uygun(r, "V2a"):
                c = deney1.ham_kategoriler(r)
                say[(c["bant"], c["e60"])][0] += 1
                say[(c["bant"], c["e60"])][1] += int(bool(r["hedef"]))
    rows = []
    for b in range(4):
        n0, p0 = say[(b, "iyilesen_sabit")]
        for e in deney1.EGILIM_SINIFLARI:
            n, p = say[(b, e)]
            rows.append([BANT_AD[b], e, n, p, f"{100 * p / n:.3f}" if n else "—",
                         f"{(p / n) / (p0 / n0):.2f}" if n and p0 else "—"])
    print(_t(["anlık bant", "60 dk eğilim", "satır", "Y=1", "oran %", "oran / (iyileşen-sabit)"], rows))

    # 3) LL farkinin dagilimi
    print("\n## 3. V1 − V2 log-loss farkının görüş aralıklarına dağılımı (OOS, tanılama)\n")
    print("Katkı = Σ[LL(V1) − LL(V2 hibrit)] / N_toplam; satırların katkıları toplamı "
          "birincil ΔLL'ye eşittir. Negatif = V2 o aralıkta kaybettiriyor. Yeniden eğitim "
          "yok; aynı OOS tahminler.\n")
    N = len(Y)
    for v in deney1.VARYANTLAR:
        top = defaultdict(lambda: [0, 0, 0.0, 0.0, 0.0])      # n, poz, dLL, p1, p2
        for f in foldlar:
            for r, p1, p2, y in zip(v1[f]["test_satirlar"], v1[f]["tahmin"], hib[(f, v)][0],
                                    v1[f]["gercek"]):
                k = deney1.ince_indeks(r["gorus"])
                x = top[k]
                x[0] += 1
                x[1] += int(bool(y))
                x[2] += _ll1(p1, y) - _ll1(p2, y)
                x[3] += p1
                x[4] += p2
        toplam = sum(x[2] for x in top.values()) / N
        rows = []
        for k in sorted(top):
            n, p, dll, s1, s2 = top[k]
            rows.append([INCE_AD[k], BANT_AD[deney1.anlik_bant(1000 if k == 0 else deney1.INCE_BANT[k - 1])],
                         n, p, f"{100 * p / n:.3f}", f"{100 * s1 / n:.3f}", f"{100 * s2 / n:.3f}",
                         f"{dll / N:+.6f}", f"{100 * (dll / N) / toplam:.0f}" if toplam else "—"])
        print(f"### {v} (toplam ΔLL {toplam:+.6f})\n")
        print(_t(["anlık görüş (ince bant)", "gv60 bandı", "satır", "Y=1", "gerçekleşen %",
                  "ort. V1 %", "ort. V2 %", "ΔLL katkısı", "toplamın %'si"], rows))
        print()

    # V1 kovasina gore (son fold, en genis egitim) - V2a
    f = foldlar[-1]
    tab = v1[f]["tablolar"]["gorus"]
    sinirlar = [k["ust"] for k in tab[:-1]]
    from sis_modeli import woe as woe_mod
    top = defaultdict(lambda: [0, 0, 0.0])
    for r, p1, p2, y in zip(v1[f]["test_satirlar"], v1[f]["tahmin"], hib[(f, "V2a")][0], v1[f]["gercek"]):
        k = woe_mod._kovala(r["gorus"], sinirlar)
        top[k][0] += 1
        top[k][1] += int(bool(y))
        top[k][2] += _ll1(p1, y) - _ll1(p2, y)
    n_f = len(v1[f]["gercek"])
    print(f"### V2a — {v1_benchmark._fold_ad(f)} test satırları, o fold'un V1 `gorus` kovasına göre\n")
    print(_t(["V1 kova", "V1 WoE", "satır", "Y=1", "ΔLL katkısı (fold içi)"],
             [[f"{'—' if tab[k]['alt'] is None else int(tab[k]['alt'])} – {'—' if tab[k]['ust'] is None else int(tab[k]['ust'])}",
               f"{tab[k]['woe']:+.3f}", top[k][0], top[k][1], f"{top[k][2] / n_f:+.6f}"] for k in sorted(top)]))

    # 4) >=9999
    print("\n## 4. ≥9999 bandında düşüş hücreleri\n")
    say = defaultdict(int)
    for r in onset:
        if r.get("_g60") is not None and r["gorus"] >= 9999:
            say[deney1.egilim(r["gorus"], r["_g60"])] += 1
    print("Tüm geliştirme evreni (onset, t−60 mevcut, anlık görüş ≥ 9999): " + ", ".join(
        f"{e}: {say[e]}" for e in deney1.EGILIM_SINIFLARI) + ".\n")
    print("Açıklama: eğilim Δ = ince_indeks(t) − ince_indeks(t−60). ≥9999 ince bandın en üst "
          f"indeksi ({deney1.ince_indeks(9999)}); t−60 ne olursa olsun indeksi ≤ "
          f"{deney1.ince_indeks(9999)}, dolayısıyla Δ ≥ 0 ve sınıf her zaman \"iyileşen/sabit\". "
          "Bu, eğilim tanımının (anlık − geçmiş, üst bant açık uçlu) matematiksel sonucudur; "
          "veri ya da kodlama hatası değildir. Aynı mantıkla ≥9999 bandında gv60 = tek hücre = "
          "bant WoE'sine eşdeğerdir; o bantta eğilim bilgisi yapısal olarak taşınamaz.\n")
    say = defaultdict(int)
    for r in onset:
        if r.get("_g60") is not None:
            b = deney1.anlik_bant(r["gorus"])
            say[(b, deney1.egilim(r["gorus"], r["_g60"]))] += 1
    print(_t(["anlık bant", "iyileşen/sabit", "1 bant", "2+ bant"],
             [[BANT_AD[b]] + [say[(b, e)] for e in deney1.EGILIM_SINIFLARI] for b in range(4)]))

    # 5) dspread
    print("\n## 5. `dspread_1sa`: WoE sıralaması ve lojistik katsayı işareti\n")
    rows = []
    for f in foldlar:
        t2 = v2[(f, "V2b")]["tablolar"]
        beta = v2[(f, "V2b")]["katsayilar"]
        rows.append([v1_benchmark._fold_ad(f)] + [f"{t2['dspread_1sa'][k]:+.3f}" for k in deney1.DSPREAD_KOVALARI]
                    + [f"{beta[-1]:+.3f}"])
    print(_t(["fold"] + [f"WoE {k}" for k in deney1.DSPREAD_KOVALARI] + ["katsayı"], rows))

    # es-dogrusallik: son fold egitiminde WoE sutunlari arasi korelasyon
    f = foldlar[-1]
    x = v2[(f, "V2b")]
    E = [r for r in v1_benchmark.bolme.ayir_embargolu(
        onset, tuple(range(v1_benchmark.bolme.ILK_YIL, f[0])), f[0]) if deney1.uygun(r, "V2b")]
    ad = deney1.ORTAK + ["gv60", "dspread_1sa"]
    X = [deney1.desen(r, x["tablolar"], "V2b") for r in E]

    def kor(i, j):
        n = len(X)
        mi = sum(v[i] for v in X) / n
        mj = sum(v[j] for v in X) / n
        c = sum((v[i] - mi) * (v[j] - mj) for v in X)
        si = math.sqrt(sum((v[i] - mi) ** 2 for v in X))
        sj = math.sqrt(sum((v[j] - mj) ** 2 for v in X))
        return c / (si * sj) if si and sj else 0.0

    j = ad.index("dspread_1sa")
    print(f"\n{v1_benchmark._fold_ad(f)} eğitim satırlarında (uygun, {len(E)}) WoE sütunlarının "
          "`dspread_1sa` WoE'siyle korelasyonu:\n")
    print(_t(["WoE sütunu", "korelasyon"], [[ad[i], f"{kor(i, j):+.3f}"] for i in range(len(ad)) if i != j]))

    # spread duzeyi icinde dspread'e gore oran (betimsel)
    print(f"\n{v1_benchmark._fold_ad(f)} eğitim satırlarında spread düzeyi içinde "
          "`dspread_1sa` kovasına göre hedef oranı (%):\n")
    say = defaultdict(lambda: [0, 0])
    for r in E:
        sp = r["spread"]
        sk = "≤ 1" if sp <= 1 else ("2–3" if sp <= 3 else "≥ 4")
        dk = deney1.dspread_kovasi(r["spread"] - r["_s60"])
        say[(sk, dk)][0] += 1
        say[(sk, dk)][1] += int(bool(r["hedef"]))
    rows = []
    for sk in ("≤ 1", "2–3", "≥ 4"):
        rows.append([sk] + [(f"{100 * say[(sk, k)][1] / say[(sk, k)][0]:.2f} (n={say[(sk, k)][0]})"
                             if say[(sk, k)][0] else "—") for k in deney1.DSPREAD_KOVALARI])
    print(_t(["spread(t) °C"] + list(deney1.DSPREAD_KOVALARI), rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
