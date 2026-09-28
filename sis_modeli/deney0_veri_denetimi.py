#!/usr/bin/env python3
"""Sis modeli V2 - Deney 0: veri kalitesi denetimi (V2_PROTOKOL.md §4).

Hedefin teknik adi: LTFJ dusuk gorus/FG olayi (olay gozlemi = gorus < 1000 m
VEYA alani kaplayan FG; Y_t = (t, t+3sa] icinde olay gozlemi var mi).

BU BETIK MODEL EGITMEZ VE PERFORMANS OLCMEZ. V1/V2 tahmini, log-loss, AP,
Brier ya da herhangi bir skor hesaplamaz. Yalnizca sayar:

  1) Tam zaman gecikme eksikligi (t-60, t-120) - yil/ay/saat; V2a/b ve V2c
     kapsamasi ayri; P(eksik | Y=1) / P(eksik | Y=0) orani, meteorolojik gun
     bootstrap'i (12 UTC - ertesi gun 12 UTC).
  2) Hedef ufku butunlugu: her onset satiri icin (t, t+3sa] icinde beklenen
     alti :20/:50 gozleminden kacinin arsivde bulundugu.
  3) 2011 denetimi (2012-2014 ile karsilastirma).
  4) Hedef bilesimi: FG-ailesi / SN iceren / SN'siz (yil ve ay); pozitif
     pencerelerde SN; olay duzeyi tum / >=1 SN / SN'siz.
  5) Zaman damgasi butunlugu (yinelenen, sirasiz, izgara disi, kadans).

Tanimlar (protokolden, degistirilmeden):
  - Satirlar: hedef.hazirla(yil >= bolme.ILK_YIL), onset = hedef.onset_adaylari.
  - Gecikme "tam zaman": dt - 60 dk (ve dt - 120 dk) zaman damgali kayit;
    en yakin gozlem KULLANILMAZ.
  - Bagimsiz olay: olay_degerlendirme.bagimsiz_olaylar(bosluk_saat=3.0) (§5.1).
  - SN: hava alaninda SN|SG|PL (sis_iklim.kod_kategorisi ile ayni).
  - FG-ailesi: sis_kodu (alani kaplayan FG) ya da BCFG/MIFG/PRFG.

Kullanim:
    python -m sis_modeli.deney0_veri_denetimi [--tekrar 2000] > rapor.md
"""

import argparse
import operator
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from sis_modeli import bolme, hedef, v2_evren
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku
from sis_modeli.olay_degerlendirme import bagimsiz_olaylar
from sis_modeli.ozellik import SIS_GORUS_M

IZGARA_DK = v2_evren.IZGARA_DK
TEKRAR = 2000                      # §5: bootstrap tekrar sayisi
ORAN_BANDI = (0.8, 1.25)           # §4.1 kayda gecme bandi
GUVEN = 0.95                       # §4.1 duzeyi belirtmiyor; iki yanli %95 kullanildi
SN_DESENI = re.compile(r"SN|SG|PL")
FG_KISMI_DESENI = re.compile(r"(BC|MI|PR)FG")
METEO_GUN_KAYMA = timedelta(hours=12)


# ------------------------------------------------------------ tanimlar ---
izgara_disi = v2_evren.izgara_disi

# §5 dis fold test bloklari; 2015-16 yalnizca erken donem tanilamasi.
DIS_FOLDLAR = ((2015, 2016), (2017, 2018), (2019, 2020), (2021, 2022),
               (2023, 2024), (2025, 2026))


def meteo_gun(dt: datetime) -> str:
    """12 UTC - ertesi gun 12 UTC; gun, basladigi takvim gunuyle adlanir."""
    return (dt - METEO_GUN_KAYMA).date().isoformat()


def sn_var(r: dict) -> bool:
    return bool(SN_DESENI.search(r.get("hava") or ""))


def fg_ailesi(r: dict) -> bool:
    return bool(r.get("sis_kodu")) or bool(FG_KISMI_DESENI.search(r.get("hava") or ""))


def gecikme_durumu(yer: dict, kayitlar: list, dt: datetime, dakika: int,
                   alanlar: tuple = ("gorus",)) -> str:
    """'zaman_yok' | 'alan_bos' | 'var' - tam zaman eslemesi."""
    j = yer.get(dt - timedelta(minutes=dakika))
    if j is None:
        return "zaman_yok"
    if any(kayitlar[j].get(a) is None for a in alanlar):
        return "alan_bos"
    return "var"


def ufuk_slotlari(yer: dict, dt: datetime) -> list:
    """(t, t+3sa] icindeki beklenen alti adimdan arsivde BULUNANLARIN
    indeksleri (hedef.hazirla ile ayni aritmetik: dt + 30k dk)."""
    return [j for k in range(1, hedef.ADIM_SAYISI + 1)
            if (j := yer.get(dt + timedelta(minutes=hedef.ADIM_DK * k))) is not None]


def olay_ata(olaylar: list, dt: datetime):
    """dt anindaki olay gozlemini iceren olayin indeksi (yoksa None).
    olaylar baslangica gore sirali, cakismaz (bagimsiz_olaylar ciktisi)."""
    lo, hi = 0, len(olaylar)
    while lo < hi:
        m = (lo + hi) // 2
        if olaylar[m]["baslangic"] <= dt:
            lo = m + 1
        else:
            hi = m
    i = lo - 1
    if i >= 0 and olaylar[i]["baslangic"] <= dt <= olaylar[i]["bitis"]:
        return i
    return None


def slot_komsuluk(kayitlar: list, yer: dict) -> Counter:
    """{(grup, slot_var_mi): sayi} - her beklenen :20/:50 slotu, +-30 dk
    komsularinin gorus/olay durumuna gore gruplanir."""
    izgara = [r["dt"] for r in kayitlar if not izgara_disi(r["dt"])]
    c = Counter()
    if not izgara:
        return c
    t, son = izgara[0], izgara[-1]
    adim = timedelta(minutes=hedef.ADIM_DK)
    while t <= son:
        kom = [kayitlar[j] for j in (yer.get(t - adim), yer.get(t + adim)) if j is not None]
        if not kom:
            g = "iki komşu da yok"
        elif any(k["sis"] for k in kom):
            g = "komşuda olay gözlemi"
        elif any(k["gorus"] < 3000 for k in kom):
            g = "komşu görüş 1000–2999"
        elif any(k["gorus"] < 5000 for k in kom):
            g = "komşu görüş 3000–4999"
        else:
            g = "komşu görüş ≥ 5000"
        c[(g, t in yer)] += 1
        t += adim
    return c


# ---------------------------------------------------------- bootstrap ---
def oran(e1: int, n1: int, e0: int, n0: int):
    """P(eksik|Y=1) / P(eksik|Y=0); tanimsizsa None."""
    if not n1 or not n0 or not e0:
        return None
    return (e1 / n1) / (e0 / n0)


def gun_bootstrap(gunluk: dict, tekrar: int = TEKRAR, tohum: int = 0,
                  guven: float = GUVEN) -> dict:
    """gunluk: {gun: {tabaka: (e1, n1, e0, n0)}}. Gunler BUTUN olarak yerine
    koymali orneklenir; her tabaka icin nokta orani ve yuzdelik aralik.
    Tum tabakalar ayni gun cekilisini paylasir (tekrar basina tek cekilis).

    Doner: {tabaka: (nokta, alt, ust, gecerli_tekrar)}"""
    gunler = sorted(gunluk)
    tabakalar = sorted({t for g in gunler for t in gunluk[g]}, key=str)
    sutun = {t: [[gunluk[g].get(t, (0, 0, 0, 0))[k] for g in gunler]
                 for k in range(4)] for t in tabakalar}
    toplam = {t: [sum(c) for c in sutun[t]] for t in tabakalar}
    rastgele = random.Random(tohum)
    ornekler = defaultdict(list)
    D = len(gunler)
    for _ in range(tekrar):
        sayac = Counter(rastgele.choices(range(D), k=D))
        w = [sayac.get(i, 0) for i in range(D)]
        for t in tabakalar:
            e1, n1, e0, n0 = (sum(map(operator.mul, w, c)) for c in sutun[t])
            o = oran(e1, n1, e0, n0)
            if o is not None:
                ornekler[t].append(o)
    sonuc = {}
    a = (1 - guven) / 2
    for t in tabakalar:
        s = sorted(ornekler[t])
        nokta = oran(*toplam[t])
        if len(s) < 0.9 * tekrar or nokta is None:
            sonuc[t] = (nokta, None, None, len(s))
            continue
        sonuc[t] = (nokta, s[int(a * len(s))], s[min(int((1 - a) * len(s)), len(s) - 1)], len(s))
    return sonuc


def kayda_gecer(nokta, alt, ust) -> bool:
    """§4.1: oran [0,8; 1,25] disinda VE aralik 1'i disliyor."""
    if nokta is None or alt is None:
        return False
    disinda = nokta < ORAN_BANDI[0] or nokta > ORAN_BANDI[1]
    return disinda and (alt > 1 or ust < 1)


def s41_durumu(e1: int, nokta, alt, ust) -> str:
    """§4.1 sutunu. Y=1'de hic eksik yoksa oran 0 ve bootstrap araligi
    [0, 0] olur: kural harfiyen uygulanirsa 'kayda gecer' der, ama bu
    bilgi degil sifir sayimin sonucudur - ayri etiketlenir, gizlenmez."""
    if e1 == 0 and nokta == 0:
        return "dejenere (Y=1'de 0 eksik)"
    return "KAYDA GEÇER" if kayda_gecer(nokta, alt, ust) else ""


# ------------------------------------------------------------ bicim ---
def _y(x, n, basamak=1):
    return "—" if not n else f"{100 * x / n:.{basamak}f}"


def _tablo(basliklar, satirlar) -> str:
    cikti = ["| " + " | ".join(basliklar) + " |",
             "|" + "|".join("---:" if i else "---" for i in range(len(basliklar))) + "|"]
    for s in satirlar:
        cikti.append("| " + " | ".join(str(x) for x in s) + " |")
    return "\n".join(cikti)


def _f(x, b=2):
    return "—" if x is None else f"{x:.{b}f}"


# -------------------------------------------------------------- analiz ---
def butunluk(ham_tumu: list) -> str:
    out = ["## 5. Zaman damgası bütünlüğü (tüm dosya, filtre öncesi)\n"]
    zam = [r["zaman"] for r in ham_tumu]
    dts = [datetime.fromisoformat(z) for z in zam]
    sirasiz = sum(1 for a, b in zip(dts, dts[1:]) if b < a)
    esit_ardisik = sum(1 for a, b in zip(dts, dts[1:]) if b == a)
    ym = Counter(zam)
    yin_metin = sum(c - 1 for c in ym.values() if c > 1)
    yd = Counter(dts)
    yin_dt = sum(c - 1 for c in yd.values() if c > 1)
    bicim = Counter("uzunluk=%d" % len(z) for z in zam)
    dis = [r for r, d in zip(ham_tumu, dts) if izgara_disi(d)]
    ay_uyumsuz = sum(1 for r, d in zip(ham_tumu, dts) if r["ay"] != d.month)
    saat_uyumsuz = sum(1 for r, d in zip(ham_tumu, dts) if r["saat"] != d.hour)
    spread_uyumsuz = sum(1 for r in ham_tumu
                         if None not in (r["sicaklik"], r["cig_noktasi"], r["spread"])
                         and r["spread"] != r["sicaklik"] - r["cig_noktasi"])
    etiket_uyumsuz = sum(1 for r in ham_tumu
                         if int(r["sis"] or 0) != int((r["gorus"] is not None and r["gorus"] < SIS_GORUS_M)
                                                      or bool(r["sis_kodu"])))
    on = sum(1 for d in dts if d.year < bolme.ILK_YIL)
    out.append(_tablo(["denetim", "sayı"], [
        ["toplam satır", len(ham_tumu)],
        [f"{bolme.ILK_YIL} öncesi satır (analiz dışı)", on],
        ["dosya sırasında geriye giden zaman damgası", sirasiz],
        ["ardışık eşit zaman damgası", esit_ardisik],
        ["yinelenen zaman metni (fazla kopya)", yin_metin],
        ["ayrıştırma sonrası yinelenen an (fazla kopya)", yin_dt],
        ["zaman metni biçimleri", ", ".join(f"{k}: {v}" for k, v in sorted(bicim.items()))],
        ["ızgara dışı (dakika ∉ {20, 50} ya da saniye ≠ 0)", len(dis)],
        ["`ay` sütunu ≠ zaman damgasının ayı", ay_uyumsuz],
        ["`saat` sütunu ≠ zaman damgasının saati", saat_uyumsuz],
        ["`spread` ≠ sıcaklık − çiy noktası", spread_uyumsuz],
        ["`sis` ≠ (görüş < 1000 ∨ sis_kodu) yeniden hesabı", etiket_uyumsuz],
    ]))
    if dis:
        out.append("\nIzgara dışı satırlar:\n")
        out.append(_tablo(["zaman", "görüş", "hava", "sis"],
                          [[r["zaman"], r["gorus"], r["hava"] or "—", r["sis"]] for r in dis]))
    # kadans: 2011+ sirali ardisik farklar
    s = sorted(d for d in yd if d.year >= bolme.ILK_YIL)
    fark = Counter()
    for a, b in zip(s, s[1:]):
        dk = int((b - a).total_seconds() // 60)
        if dk == 30:
            fark["30 dk"] += 1
        elif dk < 30:
            fark["< 30 dk"] += 1
        elif dk <= 60:
            fark["31–60 dk (1 eksik adım)"] += 1
        elif dk <= 180:
            fark["61–180 dk (2–5 eksik adım)"] += 1
        elif dk <= 1440:
            fark["181 dk – 24 sa"] += 1
        else:
            fark["> 24 sa"] += 1
    sira = ["< 30 dk", "30 dk", "31–60 dk (1 eksik adım)", "61–180 dk (2–5 eksik adım)",
            "181 dk – 24 sa", "> 24 sa"]
    out.append(f"\nArdışık gözlem aralıkları ({bolme.ILK_YIL}+, tekil anlar, sıralı):\n")
    out.append(_tablo(["aralık", "sayı"], [[k, fark.get(k, 0)] for k in sira]))
    uzun = sorted(((b - a, a, b) for a, b in zip(s, s[1:]) if b - a > timedelta(hours=3)),
                  reverse=True)
    out.append(f"\n3 saatten uzun boşluklar: {len(uzun)} adet. En uzun 15:\n")
    out.append(_tablo(["son gözlem", "sonraki gözlem", "süre (sa)"],
                      [[a.isoformat(timespec='minutes'), b.isoformat(timespec='minutes'),
                        f"{d.total_seconds() / 3600:.1f}"] for d, a, b in uzun[:15]]))
    return "\n".join(out)


def gecikme_bolumu(kayitlar, yer, onset, tekrar) -> str:
    out = ["## 1. Gecikme eksikliği ve kapsama (onset evreni)\n"]
    durum = []
    for r in onset:
        dt = r["dt"]
        z60 = yer.get(dt - timedelta(minutes=60)) is not None
        z120 = yer.get(dt - timedelta(minutes=120)) is not None
        g60 = gecikme_durumu(yer, kayitlar, dt, 60, ("gorus",))
        g120 = gecikme_durumu(yer, kayitlar, dt, 120, ("gorus",))
        s60 = gecikme_durumu(yer, kayitlar, dt, 60, ("gorus", "spread"))
        anlik_g = r.get("gorus") is not None
        anlik_s = r.get("spread") is not None
        durum.append({
            "z60": z60, "z120": z120,
            "ab_zaman": z60, "c_zaman": z60 and z120,
            "a_alan": g60 == "var" and anlik_g,
            "b_alan": s60 == "var" and anlik_g and anlik_s,
            "c_alan": s60 == "var" and g120 == "var" and anlik_g and anlik_s,
            "g60_alan_bos": g60 == "alan_bos", "g120_alan_bos": g120 == "alan_bos",
            "s60_alan_bos": z60 and s60 == "alan_bos" and g60 == "var",
            "anlik_g_bos": not anlik_g, "anlik_s_bos": not anlik_s,
        })

    N = len(onset)
    say = lambda k: sum(1 for d in durum if d[k])
    out.append(f"Onset satırı: {N}. Tam zaman kuralı: kayıt `dt − 60 dk` / "
               "`dt − 120 dk` anında yoksa gecikme eksik.\n")
    out.append(_tablo(["ölçüt", "satır", "%"], [
        ["t−60 zaman damgası yok", N - say("z60"), _y(N - say("z60"), N, 2)],
        ["t−120 zaman damgası yok", N - say("z120"), _y(N - say("z120"), N, 2)],
        ["t−60 var ama görüş boş", say("g60_alan_bos"), _y(say("g60_alan_bos"), N, 3)],
        ["t−120 var ama görüş boş", say("g120_alan_bos"), _y(say("g120_alan_bos"), N, 3)],
        ["t−60 var, görüş dolu, spread boş", say("s60_alan_bos"), _y(say("s60_alan_bos"), N, 3)],
        ["anlık (t) görüş boş", say("anlik_g_bos"), _y(say("anlik_g_bos"), N, 3)],
        ["anlık (t) spread boş", say("anlik_s_bos"), _y(say("anlik_s_bos"), N, 3)],
        ["**V2a/V2b kapsama — zaman (t−60)**", say("ab_zaman"), _y(say("ab_zaman"), N, 2)],
        ["**V2c kapsama — zaman (t−60 ∧ t−120)**", say("c_zaman"), _y(say("c_zaman"), N, 2)],
        ["V2a kapsama — zaman + görüş(t, t−60) dolu", say("a_alan"), _y(say("a_alan"), N, 2)],
        ["V2b kapsama — + spread(t, t−60) dolu", say("b_alan"), _y(say("b_alan"), N, 2)],
        ["V2c kapsama — + görüş(t−120) dolu", say("c_alan"), _y(say("c_alan"), N, 2)],
    ]))

    def kirilim(anahtar, ad, degerler):
        g = defaultdict(list)
        for r, d in zip(onset, durum):
            g[anahtar(r)].append((r, d))
        sat = []
        for k in degerler:
            L = g.get(k, [])
            n = len(L)
            p = sum(1 for r, _ in L if r["hedef"])
            m60 = sum(1 for _, d in L if not d["z60"])
            m120 = sum(1 for _, d in L if not d["z120"])
            ab = sum(1 for _, d in L if d["ab_zaman"])
            c = sum(1 for _, d in L if d["c_zaman"])
            sat.append([k, n, p, m60, _y(m60, n, 2), m120, _y(m120, n, 2),
                        _y(ab, n, 2), _y(c, n, 2)])
        return _tablo([ad, "satır", "Y=1", "t−60 yok", "%", "t−120 yok", "%",
                       "V2a/b kapsama %", "V2c kapsama %"], sat)

    yillar = sorted({r["dt"].year for r in onset})
    out.append("\n### 1.1 Yıla göre\n")
    out.append(kirilim(lambda r: r["dt"].year, "yıl", yillar))
    out.append("\n### 1.2 Aya göre (tüm yıllar)\n")
    out.append(kirilim(lambda r: r["dt"].month, "ay", range(1, 13)))
    out.append("\n### 1.3 UTC saate göre (tüm yıllar)\n")
    out.append(kirilim(lambda r: r["dt"].hour, "saat", range(24)))

    # eksiklik - hedef iliskisi
    out.append("\n### 1.4 Eksiklik ile hedef ilişkisi — P(eksik | Y=1) / P(eksik | Y=0)\n")
    out.append(f"Meteorolojik gün (12–12 UTC) blok bootstrap, {tekrar} tekrar, tohum 0, "
               f"iki yanlı %{int(GUVEN * 100)} yüzdelik aralık. Kayda geçme: oran "
               f"[{ORAN_BANDI[0]}; {ORAN_BANDI[1]}] dışında **ve** aralık 1'i dışlıyor. "
               "Bir tekrarda P(eksik|Y=0) = 0 ya da tabakada Y=1 yoksa oran tanımsızdır; "
               "geçerli tekrar tekrarların %90'ından azsa aralık verilmez. Y=1 satırlarında "
               "hiç eksik olmayan tabakada oran 0 ve aralık [0, 0] olur; kural harfiyen "
               "uygulanırsa bu tabakalar da \"kayda geçer\", ama bu bir sıfır sayımıdır — "
               "\"dejenere\" diye ayrı işaretlenir.\n")
    sonuclar = {}
    for ad, anahtar in (("t−60 zaman yok (V2a/b geri dönüşü)", "ab_zaman"),
                        ("t−60 ∨ t−120 zaman yok (V2c geri dönüşü)", "c_zaman")):
        gunluk = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0]))
        for r, d in zip(onset, durum):
            e = 0 if d[anahtar] else 1
            y = r["hedef"]
            g = meteo_gun(r["dt"])
            for t in ("tümü", ("ay", r["dt"].month), ("saat", r["dt"].hour)):
                v = gunluk[g][t]
                if y:
                    v[0] += e; v[1] += 1
                else:
                    v[2] += e; v[3] += 1
        gunluk = {g: {t: tuple(v) for t, v in d.items()} for g, d in gunluk.items()}
        topl = defaultdict(lambda: [0, 0, 0, 0])
        for d in gunluk.values():
            for t, v in d.items():
                for k in range(4):
                    topl[t][k] += v[k]
        sonuclar[ad] = (gun_bootstrap(gunluk, tekrar=tekrar), topl)

    for ad, (bs, topl) in sonuclar.items():
        out.append(f"\n**{ad}**\n")
        sat = []
        sirali = (["tümü"] + [("ay", m) for m in range(1, 13)]
                  + [("saat", h) for h in range(24)])
        for t in sirali:
            e1, n1, e0, n0 = topl[t]
            nokta, alt, ust, gecerli = bs.get(t, (None, None, None, 0))
            etiket = t if t == "tümü" else f"{t[0]} {t[1]}"
            sat.append([etiket, n1, e1, _y(e1, n1, 2), n0, e0, _y(e0, n0, 2),
                        _f(nokta), f"{_f(alt)} – {_f(ust)}" if alt is not None else "—",
                        gecerli, s41_durumu(e1, nokta, alt, ust)])
        out.append(_tablo(["tabaka", "Y=1 satır", "eksik", "%", "Y=0 satır", "eksik", "%",
                           "oran", "%95 aralık", "geçerli tekrar", "§4.1"], sat))

    # gecikme eksikligi x ufuk eksikligi
    out.append("\n### 1.5 Gecikme eksikliği × ufuk eksikliği (onset satırları)\n")
    capraz = Counter()
    for r, d in zip(onset, durum):
        tam = len(ufuk_slotlari(yer, r["dt"])) == hedef.ADIM_SAYISI
        capraz[(d["ab_zaman"], tam)] += 1
    out.append(_tablo(["", "ufuk tam (6/6)", "ufuk eksik (< 6)"], [
        ["t−60 var", capraz[(True, True)], capraz[(True, False)]],
        ["t−60 yok", capraz[(False, True)], capraz[(False, False)]],
    ]))

    out.append("\n### 1.6 Eksik ızgara slotu — komşu gözlemin durumuna göre\n")
    out.append("Birim: ilk ve son :20/:50 gözlemi arasındaki her beklenen 30 dk slot. Komşu = "
               "slot ± 30 dk'daki gözlem(ler). Grup önceliği: komşuda olay gözlemi > komşu "
               "görüş 1000–2999 > 3000–4999 > ≥ 5000. Model/tahmin yok; yalnızca sayım.\n")
    sira = ["komşuda olay gözlemi", "komşu görüş 1000–2999", "komşu görüş 3000–4999",
            "komşu görüş ≥ 5000", "iki komşu da yok"]
    c = slot_komsuluk(kayitlar, yer)
    out.append(_tablo(["grup", "slot", "eksik", "%"],
                      [[g, c[(g, True)] + c[(g, False)], c[(g, False)],
                        _y(c[(g, False)], c[(g, True)] + c[(g, False)], 2)] for g in sira]))
    return "\n".join(out), durum


def ufuk_bolumu(kayitlar, yer, onset) -> str:
    out = ["## 2. Hedef ufku bütünlüğü (onset evreni)\n"]
    son_dt = kayitlar[-1]["dt"]
    olay_zamanlari = sorted(r["dt"] for r in kayitlar if r["sis"])
    olay_kume = set(olay_zamanlari)

    def olay_yakininda(dt_eksik):
        return any((dt_eksik + timedelta(minutes=d)) in olay_kume for d in (-60, -30, 30, 60))

    dagilim = Counter()
    yil = defaultdict(lambda: Counter())
    ay = defaultdict(lambda: Counter())
    riskli = []
    for r in onset:
        dt = r["dt"]
        var = ufuk_slotlari(yer, dt)
        n = len(var)
        kesik = dt + timedelta(hours=hedef.UFUK_SAAT) > son_dt
        dagilim[(n, bool(r["hedef"]))] += 1
        anahtar = "tam" if n == hedef.ADIM_SAYISI else "eksik"
        yil[dt.year][(anahtar, bool(r["hedef"]))] += 1
        ay[dt.month][(anahtar, bool(r["hedef"]))] += 1
        if kesik:
            yil[dt.year]["arsiv_sonu"] += 1
        if n < hedef.ADIM_SAYISI and not r["hedef"]:
            eksikler = [dt + timedelta(minutes=hedef.ADIM_DK * k)
                        for k in range(1, hedef.ADIM_SAYISI + 1)
                        if (dt + timedelta(minutes=hedef.ADIM_DK * k)) not in yer]
            if any(olay_yakininda(e) for e in eksikler):
                riskli.append(r)
            if n == 0:
                yil[dt.year]["hic_slot_yok_neg"] += 1

    out.append("Tanım: t anındaki onset satırı için beklenen adımlar t+30, t+60, …, t+180 dk "
               "(`hedef.hazirla` ile aynı aritmetik). `hazirla` eksik adımı atlar; hiçbir "
               "mevcut adımda olay yoksa Y=0 yazar. Dolayısıyla **ufku eksik ve Y=0** olan "
               "satırın etiketi doğrulanamaz (eksik adımda olay olabilirdi). Ufku eksik ve "
               "Y=1 olan satırın etiketi doğrudur (olay mevcut bir adımda görülmüş).\n")
    sat = []
    N = len(onset)
    for n in range(hedef.ADIM_SAYISI, -1, -1):
        a, b = dagilim[(n, False)], dagilim[(n, True)]
        sat.append([f"{n}/6", a + b, _y(a + b, N, 3), a, b])
    out.append(_tablo(["mevcut adım", "satır", "%", "Y=0", "Y=1"], sat))

    eks0 = sum(v for (n, y), v in dagilim.items() if n < 6 and not y)
    eks1 = sum(v for (n, y), v in dagilim.items() if n < 6 and y)
    tum0 = sum(v for (n, y), v in dagilim.items() if not y)
    tum1 = sum(v for (n, y), v in dagilim.items() if y)
    out.append(f"\n- Ufku eksik satır: {eks0 + eks1} (%{_y(eks0 + eks1, N, 2)}); "
               f"Y=0: {eks0} (Y=0'ların %{_y(eks0, tum0, 2)}), "
               f"Y=1: {eks1} (Y=1'lerin %{_y(eks1, tum1, 2)}).")
    out.append(f"- **Etiketi doğrulanamayan satır (ufuk eksik ∧ Y=0): {eks0}.**")
    out.append(f"- Bunlardan eksik adımın ±60 dk komşuluğunda arşivde bir olay gözlemi "
               f"bulunan (yüksek riskli) satır: **{len(riskli)}**.")

    out.append("\n### 2.1 Yıla göre\n")
    s = []
    for y in sorted(yil):
        c = yil[y]
        tam = c[("tam", False)] + c[("tam", True)]
        eks = c[("eksik", False)] + c[("eksik", True)]
        s.append([y, tam + eks, eks, _y(eks, tam + eks, 2), c[("eksik", False)],
                  c[("eksik", True)], c["hic_slot_yok_neg"], c["arsiv_sonu"],
                  sum(1 for r in riskli if r["dt"].year == y)])
    out.append(_tablo(["yıl", "satır", "ufuk eksik", "%", "eksik ∧ Y=0", "eksik ∧ Y=1",
                       "0/6 adım ∧ Y=0", "arşiv sonu kesik", "yüksek riskli"], s))
    out.append("\n### 2.2 Aya göre (tüm yıllar)\n")
    s = []
    for m in range(1, 13):
        c = ay[m]
        tam = c[("tam", False)] + c[("tam", True)]
        eks = c[("eksik", False)] + c[("eksik", True)]
        s.append([m, tam + eks, eks, _y(eks, tam + eks, 2), c[("eksik", False)],
                  c[("eksik", True)], sum(1 for r in riskli if r["dt"].month == m)])
    out.append(_tablo(["ay", "satır", "ufuk eksik", "%", "eksik ∧ Y=0", "eksik ∧ Y=1",
                       "yüksek riskli"], s))
    if riskli:
        gunler = Counter(meteo_gun(r["dt"]) for r in riskli)
        out.append(f"\nYüksek riskli satırların meteorolojik günleri ({len(gunler)} gün):\n")
        out.append(_tablo(["meteorolojik gün", "satır"], sorted(gunler.items())))
    return "\n".join(out)


def _gorus_kovasi(g):
    if g is None:
        return "boş"
    if g < 1000:
        return "< 1000"
    if g < 3000:
        return "1000–2999"
    if g < 5000:
        return "3000–4999"
    if g < 9999:
        return "5000–9998"
    return "≥ 9999"


def yil_denetimi(kayitlar, onset, olaylar_tum) -> str:
    out = ["## 3. 2011 denetimi (2012–2014 ile karşılaştırma; bağlam için tüm yıllar)\n"]
    yillar = sorted({r["dt"].year for r in kayitlar})
    by = defaultdict(list)
    for r in kayitlar:
        by[r["dt"].year].append(r)
    poz = Counter(r["dt"].year for r in onset if r["hedef"])
    ons = Counter(r["dt"].year for r in onset)
    olay_y = Counter(o["baslangic"].year for o in olaylar_tum)

    kovalar = ["boş", "< 1000", "1000–2999", "3000–4999", "5000–9998", "≥ 9999"]
    s = []
    for y in yillar:
        L = by[y]
        c = Counter(_gorus_kovasi(r["gorus"]) for r in L)
        s.append([y, len(L)] + [f"{c[k]} ({_y(c[k], len(L), 2)})" for k in kovalar])
    out.append("### 3.1 Görüş dağılımı (gözlem sayısı, parantezde %)\n")
    out.append(_tablo(["yıl", "gözlem"] + kovalar, s))

    def hava_say(L, desen):
        d = re.compile(desen)
        return sum(1 for r in L if d.search(r.get("hava") or ""))

    s = []
    for y in yillar:
        L = by[y]
        n = len(L)
        s.append([y, n,
                  _y(sum(1 for r in L if not (r.get("hava") or "").strip()), n),
                  hava_say(L, r"(?<![A-Z])BR"), sum(1 for r in L if r["sis_kodu"]),
                  hava_say(L, r"(BC|MI|PR)FG"), hava_say(L, r"FG"),
                  hava_say(L, r"SN|SG|PL"), hava_say(L, r"RA|DZ"), hava_say(L, r"HZ|FU|DU"),
                  sum(1 for r in L if r["sis"]), ons[y], poz[y], olay_y[y]])
    out.append("\n### 3.2 Hava kodları, olay gözlemi, onset/pozitif/olay\n")
    out.append("`hava boş %`: hava alanı boş olan gözlem yüzdesi. `FG (alanı kaplayan)`: "
               "`sis_kodu`. `FG içeren`: hava metninde FG geçen her gözlem (BCFG/MIFG/PRFG/"
               "VCFG/FZFG dahil). Olay sayısı başlangıç yılına göre (§5.1).\n")
    out.append(_tablo(["yıl", "gözlem", "hava boş %", "BR", "FG (alanı kaplayan)",
                       "BC/MI/PRFG", "FG içeren", "SN/SG/PL", "RA/DZ", "HZ/FU/DU",
                       "olay gözlemi", "onset satır", "Y=1 satır", "bağımsız olay"], s))

    s = []
    for y in yillar:
        L = by[y]
        n = len(L)
        g = sorted(r["gorus"] for r in L if r["gorus"] is not None)
        ayri = len(set(g))
        q = lambda p: g[min(int(p * len(g)), len(g) - 1)] if g else None
        min_g = g[0] if g else None
        s.append([y, ayri, min_g, q(0.01), q(0.05), q(0.10), q(0.5),
                  _y(sum(1 for r in L if r["tavan"] is None), n),
                  _y(sum(1 for r in L if r["spread"] is None), n),
                  _y(sum(1 for r in L if r["spread"] is not None and r["spread"] <= 1), n),
                  _y(sum(1 for r in L if r["ruzgar_yon"] is None), n)])
    out.append("\n### 3.3 Görüş değer yapısı ve diğer alanlar\n")
    out.append(_tablo(["yıl", "farklı görüş değeri", "en küçük görüş", "%1", "%5", "%10",
                       "medyan", "tavan boş %", "spread boş %", "spread ≤ 1 %",
                       "rüzgâr yönü boş %"], s))

    out.append("\n### 3.3b Rüzgâr hızı dağılımı ve sise elverişli koşullar\n")
    out.append("`sakin`: rüzgâr ≤ 2 kt. `elverişli`: spread ≤ 1 °C ∧ rüzgâr ≤ 2 kt ∧ "
               "18–06 UTC. Son iki sütun elverişli gözlemlerden görüşü < 1000 / < 3000 "
               "olanlar.\n")
    s = []
    for y in yillar:
        L = by[y]
        n = len(L)
        hiz = Counter(r["ruzgar_hiz"] for r in L)
        el = [r for r in L if r["spread"] is not None and r["spread"] <= 1
              and r["ruzgar_hiz"] is not None and r["ruzgar_hiz"] <= 2
              and (r["dt"].hour >= 18 or r["dt"].hour < 6)]
        s.append([y, _y(hiz[0], n), _y(hiz[1], n), _y(hiz[2], n),
                  _y(sum(v for k, v in hiz.items() if k is not None and k <= 2), n),
                  hiz[None], len(el), sum(1 for r in el if r["gorus"] < 1000),
                  sum(1 for r in el if r["gorus"] < 3000)])
    out.append(_tablo(["yıl", "0 kt %", "1 kt %", "2 kt %", "sakin %", "hız boş",
                       "elverişli", "elverişli ∧ < 1000", "elverişli ∧ < 3000"], s))
    s = []
    for m in range(1, 13):
        def sakin(y):
            L = [r for r in by[y] if r["dt"].month == m]
            return 100 * sum(1 for r in L if r["ruzgar_hiz"] is not None
                             and r["ruzgar_hiz"] <= 2) / len(L) if L else 0
        def doy(y):
            L = [r for r in by[y] if r["dt"].month == m]
            return 100 * sum(1 for r in L if r["spread"] <= 1) / len(L) if L else 0
        def ort_t(y):
            L = [r for r in by[y] if r["dt"].month == m]
            return sum(r["sicaklik"] for r in L) / len(L) if L else 0
        s.append([m, f"{sakin(2011):.1f}", f"{sum(sakin(y) for y in (2012, 2013, 2014)) / 3:.1f}",
                  f"{doy(2011):.1f}", f"{sum(doy(y) for y in (2012, 2013, 2014)) / 3:.1f}",
                  f"{ort_t(2011):.1f}", f"{sum(ort_t(y) for y in (2012, 2013, 2014)) / 3:.1f}"])
    out.append("\nAylık — 2011 ile 2012–2014 ortalaması:\n")
    out.append(_tablo(["ay", "sakin % 2011", "2012–14", "spread ≤ 1 % 2011", "2012–14",
                       "ort. sıcaklık 2011", "2012–14"], s))

    out.append("\n### 3.4 Gözlem zaman yapısı\n")
    s = []
    for y in yillar:
        L = by[y]
        dk = Counter(r["dt"].minute for r in L)
        s.append([y, len(L), dk.get(20, 0), dk.get(50, 0),
                  sum(v for k, v in dk.items() if k not in IZGARA_DK),
                  len({r["dt"].date() for r in L}),
                  _y(len(L), 48 * (366 if y % 4 == 0 else 365), 1)])
    out.append(_tablo(["yıl", "gözlem", ":20", ":50", "diğer dakika", "gözlemli gün",
                       "ızgara doluluk %"], s))

    out.append("\n### 3.5 2011 ile 2012–2014 ortalaması — aylık\n")
    s = []
    for m in range(1, 13):
        def ay_ol(y):
            return [r for r in by[y] if r["dt"].month == m]
        a = ay_ol(2011)
        karsi = [ay_ol(y) for y in (2012, 2013, 2014)]
        ort = lambda f: sum(f(k) for k in karsi) / 3
        s.append([m, len(a), f"{ort(len):.0f}",
                  sum(1 for r in a if r["gorus"] is not None and r["gorus"] < 1000),
                  f"{ort(lambda k: sum(1 for r in k if r['gorus'] is not None and r['gorus'] < 1000)):.1f}",
                  sum(1 for r in a if r["gorus"] is not None and r["gorus"] < 5000),
                  f"{ort(lambda k: sum(1 for r in k if r['gorus'] is not None and r['gorus'] < 5000)):.1f}",
                  hava_say(a, r"(?<![A-Z])BR"), f"{ort(lambda k: hava_say(k, r'(?<![A-Z])BR')):.1f}",
                  hava_say(a, r"FG"), f"{ort(lambda k: hava_say(k, r'FG')):.1f}",
                  hava_say(a, r"SN|SG|PL"), f"{ort(lambda k: hava_say(k, r'SN|SG|PL')):.1f}"])
    out.append(_tablo(["ay", "gözlem 2011", "2012–14 ort.", "<1000 2011", "2012–14 ort.",
                       "<5000 2011", "2012–14 ort.", "BR 2011", "2012–14 ort.",
                       "FG içeren 2011", "2012–14 ort.", "SN 2011", "2012–14 ort."], s))

    y11 = [r for r in by.get(2011, []) if r["sis"]]
    out.append("\n### 3.6 2011'in bütün olay gözlemleri\n")
    out.append(_tablo(["zaman", "görüş", "hava", "sis_kodu"],
                      [[r["zaman"], r["gorus"], r["hava"] or "—", r["sis_kodu"]] for r in y11]))
    return "\n".join(out)


def bilesim_bolumu(kayitlar, yer, onset, olaylar_tum) -> str:
    out = ["## 4. Hedef bileşimi ve SN tanılama altyapısı\n"]
    olay_gozlem = [r for r in kayitlar if r["sis"]]

    def bil(L):
        n = len(L)
        fg = sum(1 for r in L if fg_ailesi(r))
        fgk = sum(1 for r in L if r["sis_kodu"])
        sn = sum(1 for r in L if sn_var(r))
        fg_sn = sum(1 for r in L if fg_ailesi(r) and sn_var(r))
        hic = sum(1 for r in L if not fg_ailesi(r) and not sn_var(r))
        return [n, fgk, fg, sn, fg_sn, n - sn, hic]

    bas = ["olay gözlemi", "FG (alanı kaplayan)", "FG-ailesi", "SN içeren",
           "FG-ailesi ∧ SN", "SN'siz", "ne FG-ailesi ne SN"]
    out.append("### 4.1 Olay gözlemlerinin bileşimi — yıla göre (örtüşen bayraklar)\n")
    yillar = sorted({r["dt"].year for r in kayitlar})
    out.append(_tablo(["yıl"] + bas,
                      [[y] + bil([r for r in olay_gozlem if r["dt"].year == y]) for y in yillar]
                      + [["**toplam**"] + bil(olay_gozlem)]))
    out.append("\n### 4.2 Olay gözlemlerinin bileşimi — aya göre\n")
    out.append(_tablo(["ay"] + bas,
                      [[m] + bil([r for r in olay_gozlem if r["dt"].month == m]) for m in range(1, 13)]))

    # pozitif pencereler
    olay_liste = olaylar_tum
    tanimsiz = 0
    sat_yil = defaultdict(Counter)
    tum_sn = Counter()
    for r in onset:
        idx = ufuk_slotlari(yer, r["dt"])
        pencere = [kayitlar[j] for j in idx]
        a = any(sn_var(k) for k in pencere)
        c = sat_yil[r["dt"].year]
        tum_sn[(bool(r["hedef"]), a)] += 1
        if not r["hedef"]:
            continue
        olaylilar = [k for k in pencere if k["sis"]]
        b = any(sn_var(k) for k in olaylilar)
        ilk = olaylilar[0] if olaylilar else None
        cc = bool(ilk) and sn_var(ilk)
        if ilk is None or olay_ata(olay_liste, ilk["dt"]) is None:
            tanimsiz += 1
        c["poz"] += 1
        c["a"] += a
        c["b"] += b
        c["c"] += cc
    toplam = Counter()
    for c in sat_yil.values():
        toplam.update(c)
    out.append("\n### 4.3 Pozitif onset satırları (Y=1) ve SN\n")
    out.append("Tanımlar: (a) (t, t+3sa] içindeki herhangi bir :20/:50 gözleminde SN; "
               "(b) penceredeki olay gözlemlerinden en az birinde SN; (c) penceredeki ilk "
               "olay gözleminde SN. §9.3 satır tanılaması tanım (a)'nın tümleyenini "
               "kullanır: \"hedef penceresinde hiç SN gözlemi bulunmayan satırlar\".\n")
    s = [[y, c["poz"], c["a"], c["b"], c["c"], c["poz"] - c["a"]]
         for y, c in sorted(sat_yil.items())]
    alt = Counter()
    for y, c in sat_yil.items():
        if y <= 2023:
            alt.update(c)
    s.append(["2011–2023 (V1 eğitim dönemi)", alt["poz"], alt["a"], alt["b"], alt["c"],
              alt["poz"] - alt["a"]])
    s.append(["**toplam**", toplam["poz"], toplam["a"], toplam["b"], toplam["c"],
              toplam["poz"] - toplam["a"]])
    out.append(_tablo(["yıl", "Y=1", "(a) pencerede SN", "(b) olay gözleminde SN",
                       "(c) ilk olay gözleminde SN", "SN'siz (a'nın tümleyeni)"], s))
    out.append(f"\n- Olayına atanamayan pozitif satır: **{tanimsiz}** "
               "(§5.1: ilk olay gözleminin ait olduğu olaya atama).")
    out.append("\n§9.3 satır tanılaması evreni (tüm onset satırları, tanım a):\n")
    out.append(_tablo(["", "penceresinde SN yok", "penceresinde SN var"], [
        ["Y=0", tum_sn[(False, False)], tum_sn[(False, True)]],
        ["Y=1", tum_sn[(True, False)], tum_sn[(True, True)]],
    ]))

    # olay duzeyi
    olay_sn = [False] * len(olay_liste)
    olay_fg = [False] * len(olay_liste)
    for r in olay_gozlem:
        i = olay_ata(olay_liste, r["dt"])
        if i is None:
            continue
        olay_sn[i] |= sn_var(r)
        olay_fg[i] |= fg_ailesi(r)
    atanmayan_gozlem = sum(1 for r in olay_gozlem if olay_ata(olay_liste, r["dt"]) is None)
    out.append("\n### 4.4 Bağımsız olaylar (§5.1, 2011+ tam kayıt) — tümü / ≥ 1 SN / SN'siz\n")
    s = []
    for y in yillar:
        idx = [i for i, o in enumerate(olay_liste) if o["baslangic"].year == y]
        s.append([y, len(idx), sum(olay_sn[i] for i in idx),
                  sum(1 for i in idx if not olay_sn[i]),
                  sum(1 for i in idx if olay_fg[i]),
                  sum(1 for i in idx if not olay_sn[i] and not olay_fg[i])])
    n = len(olay_liste)
    s.append(["**toplam**", n, sum(olay_sn), n - sum(olay_sn), sum(olay_fg),
              sum(1 for i in range(n) if not olay_sn[i] and not olay_fg[i])])
    out.append(_tablo(["başlangıç yılı", "olay", "≥ 1 SN", "SN'siz", "≥ 1 FG-ailesi",
                       "ne SN ne FG-ailesi"], s))
    out.append(f"\n- Hiçbir olaya atanamayan olay gözlemi: **{atanmayan_gozlem}**.")
    return "\n".join(out)


def evren_ozeti(kayitlar: list) -> dict:
    """Once/sonra karsilastirmasi icin tek bir evrenin temel sayimlari."""
    yer = {r["dt"]: i for i, r in enumerate(kayitlar)}
    onset = hedef.onset_adaylari(kayitlar)
    olaylar = bagimsiz_olaylar(kayitlar, etiket="sis", bosluk_saat=3.0)
    n1 = sum(1 for r in onset if r["hedef"])
    n0 = len(onset) - n1
    say = Counter()
    atanan = set()
    for r in onset:
        dt, y = r["dt"], bool(r["hedef"])
        z60 = (dt - timedelta(minutes=60)) in yer
        z120 = (dt - timedelta(minutes=120)) in yer
        say[("e60", y)] += not z60
        say[("ec", y)] += not (z60 and z120)
        idx = ufuk_slotlari(yer, dt)
        if len(idx) < hedef.ADIM_SAYISI:
            say[("ufuk_eksik", y)] += 1
        if y:
            ilk = next(kayitlar[j] for j in idx if kayitlar[j]["sis"])
            atanan.add(olay_ata(olaylar, ilk["dt"]))
    olay_sn = [False] * len(olaylar)
    for r in kayitlar:
        if r["sis"] and sn_var(r):
            i = olay_ata(olaylar, r["dt"])
            if i is not None:
                olay_sn[i] = True
    return {
        "kayit": len(kayitlar),
        "izgara_disi_kayit": sum(1 for r in kayitlar if izgara_disi(r["dt"])),
        "onset": len(onset), "y1": n1,
        "olay": len(olaylar),
        "pozitif_satirsiz_olay": len(olaylar) - len(atanan - {None}),
        "olay_sn": sum(olay_sn), "olay_snsiz": len(olaylar) - sum(olay_sn),
        "e60_y1": say[("e60", True)], "e60_y0": say[("e60", False)],
        "ec_y1": say[("ec", True)], "ec_y0": say[("ec", False)],
        "oran60": oran(say[("e60", True)], n1, say[("e60", False)], n0),
        "oranc": oran(say[("ec", True)], n1, say[("ec", False)], n0),
        "kapsama_ab": (len(onset) - say[("e60", True)] - say[("e60", False)]) / len(onset),
        "kapsama_c": (len(onset) - say[("ec", True)] - say[("ec", False)]) / len(onset),
        "ufuk_eksik_y0": say[("ufuk_eksik", False)],
        "ufuk_eksik_y1": say[("ufuk_eksik", True)],
    }


def fold_sayimlari(kayitlar: list) -> list:
    """Her dis fold icin test donemi (onset, Y=1, olay) ve egitim yillari
    olay sayisi. §5.1: bolutleme ilgili donemin satirlarina uygulanir."""
    sonuc = []
    for test in DIS_FOLDLAR:
        te = [r for r in kayitlar if r["dt"].year in test]
        eg = [r for r in kayitlar if bolme.ILK_YIL <= r["dt"].year < test[0]]
        te_on = hedef.onset_adaylari(te)
        sonuc.append({
            "fold": f"{test[0]}–{str(test[1])[2:]}",
            "test_onset": len(te_on),
            "test_y1": sum(1 for r in te_on if r["hedef"]),
            "test_olay": len(bagimsiz_olaylar(te, etiket="sis", bosluk_saat=3.0)),
            "egitim_olay": len(bagimsiz_olaylar(eg, etiket="sis", bosluk_saat=3.0)),
        })
    return sonuc


def once_sonra_bolumu(ilk: list, duz: list) -> str:
    out = ["## 0. Deney 0 ilk denetim → §3 uygulama düzeltmesi (B10) sonrası geliştirme evreni\n"]
    out.append("**Önce:** `hedef.hazirla(yıl ≥ 2011)` — ızgara dışı kayıtlar dahil (Deney 0 ilk "
               "denetimi). **Sonra:** `v2_evren.gelistirme_kayitlari` — ızgara filtresi "
               "(`:20/:50`) `hedef.hazirla`'dan ve olay bölütlemesinden **önce**. Veri "
               "dosyasından satır silinmedi. Aşağıdaki bütün bölümler (1–4) **sonra** "
               "evrenindedir.\n")
    a, b = evren_ozeti(ilk), evren_ozeti(duz)
    satir = [
        ("kayıt (2011+)", "kayit", "d"), ("ızgara dışı kayıt", "izgara_disi_kayit", "d"),
        ("onset satırı", "onset", "d"), ("Y=1", "y1", "d"),
        ("bağımsız olay (§5.1)", "olay", "d"),
        ("pozitif satırı olmayan olay", "pozitif_satirsiz_olay", "d"),
        ("olay: ≥ 1 SN", "olay_sn", "d"), ("olay: SN'siz", "olay_snsiz", "d"),
        ("t−60 yok ∧ Y=1", "e60_y1", "d"), ("t−60 yok ∧ Y=0", "e60_y0", "d"),
        ("(t−60 ∨ t−120) yok ∧ Y=1", "ec_y1", "d"), ("(t−60 ∨ t−120) yok ∧ Y=0", "ec_y0", "d"),
        ("oran P(eksik|Y=1)/P(eksik|Y=0), t−60 (nokta)", "oran60", "f"),
        ("oran, t−60 ∨ t−120 (nokta)", "oranc", "f"),
        ("V2a/b kapsama %", "kapsama_ab", "p"), ("V2c kapsama %", "kapsama_c", "p"),
        ("ufuk eksik ∧ Y=0 (etiketi doğrulanamayan)", "ufuk_eksik_y0", "d"),
        ("ufuk eksik ∧ Y=1", "ufuk_eksik_y1", "d"),
    ]

    def bic(v, t):
        if t == "f":
            return _f(v)
        if t == "p":
            return f"{100 * v:.3f}"
        return v

    s = []
    for ad, k, t in satir:
        fark = b[k] - a[k] if t == "d" else None
        s.append([ad, bic(a[k], t), bic(b[k], t), "" if fark in (None, 0) else f"{fark:+d}"])
    out.append(_tablo(["sayım", "önce (ilk denetim)", "sonra (düzeltilmiş)", "fark"], s))

    out.append("\n**Dış fold'lara göre** (test dönemi satırları; eğitim olayı = o fold'un "
               f"eğitim yılları {bolme.ILK_YIL}–(test−1), ambargo öncesi, §5.1 bölütlemesi). "
               "2015–16 yalnızca erken dönem tanılamasıdır.\n")
    fa, fb = fold_sayimlari(ilk), fold_sayimlari(duz)
    s = []
    for x, y in zip(fa, fb):
        s.append([x["fold"],
                  f"{x['test_onset']} → {y['test_onset']}", f"{x['test_y1']} → {y['test_y1']}",
                  f"{x['test_olay']} → {y['test_olay']}", f"{x['egitim_olay']} → {y['egitim_olay']}"])
    out.append(_tablo(["dış fold (test)", "test onset", "test Y=1", "test olayı",
                       "eğitim olayı"], s))
    return "\n".join(out)


def canli_arsiv_bolumu(yol: Path) -> str:
    """gozlem_arsivi.csv'de METAR izgara doluluğu (yalnizca sayim)."""
    import csv
    out = ["## 6. Canlı arşiv (`gozlem_arsivi.csv`) ızgara doluluğu\n"]
    if not yol.exists():
        out.append(f"`{yol.name}` yok.")
        return "\n".join(out)
    with yol.open(encoding="utf-8", newline="") as f:
        satir = list(csv.DictReader(f))
    tip = Counter(r.get("tip") for r in satir)
    metar = sorted({datetime.fromisoformat(r["zaman"]).replace(tzinfo=None)
                    for r in satir if r.get("tip") == "METAR"})
    if not metar:
        out.append("METAR yok.")
        return "\n".join(out)
    dis = [t for t in metar if izgara_disi(t)]
    izg = [t for t in metar if not izgara_disi(t)]
    kume = set(izg)
    eksik = []
    t = izg[0]
    while t <= izg[-1]:
        if t not in kume:
            eksik.append(t)
        t += timedelta(minutes=hedef.ADIM_DK)
    beklenen = len(izg) + len(eksik)
    out.append(_tablo(["ölçüt", "değer"], [
        ["kapsam", f"{izg[0].isoformat(timespec='minutes')} → {izg[-1].isoformat(timespec='minutes')} UTC"],
        ["satır (METAR / SPECI)", f"{tip.get('METAR', 0)} / {tip.get('SPECI', 0)}"],
        ["ızgara dışı METAR", len(dis)],
        ["beklenen :20/:50 slotu", beklenen],
        ["eksik slot", f"{len(eksik)} (%{_y(len(eksik), beklenen, 2)})"],
        ["eksik slotlar", ", ".join(e.isoformat(timespec='minutes') for e in eksik) or "—"],
    ]))
    return "\n".join(out)


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    a.add_argument("--tekrar", type=int, default=TEKRAR)
    s = a.parse_args(argv)
    if not s.veri.exists():
        print(f"HATA: {s.veri} yok.", file=sys.stderr)
        return 1

    ham_tumu = veri_oku(s.veri)
    ham = [r for r in ham_tumu if r["zaman"][:4] >= str(bolme.ILK_YIL)]
    ilk_denetim = hedef.hazirla(ham)                      # B10 oncesi (karsilastirma)
    kayitlar = v2_evren.gelistirme_kayitlari(ham_tumu)    # §3: izgara filtresi hazirla'dan once
    yer = {r["dt"]: i for i, r in enumerate(kayitlar)}
    onset = hedef.onset_adaylari(kayitlar)
    olaylar_tum = bagimsiz_olaylar(kayitlar, etiket="sis", bosluk_saat=3.0)

    print("# Deney 0 — veri kalitesi denetimi (çıktı)\n")
    print(once_sonra_bolumu(ilk_denetim, kayitlar), "\n")
    print(f"Geliştirme evreni (düzeltilmiş): `{s.veri.name}`; {bolme.ILK_YIL}+ ızgara satırı: {len(kayitlar)}; "
          f"onset satırı: {len(onset)}; Y=1: {sum(1 for r in onset if r['hedef'])}; "
          f"bağımsız olay: {len(olaylar_tum)}. Model eğitilmedi; performans ölçütü "
          "hesaplanmadı.\n")
    metin, _ = gecikme_bolumu(kayitlar, yer, onset, s.tekrar)
    print(metin, "\n")
    print(ufuk_bolumu(kayitlar, yer, onset), "\n")
    print(yil_denetimi(kayitlar, onset, olaylar_tum), "\n")
    print(bilesim_bolumu(kayitlar, yer, onset, olaylar_tum), "\n")
    print(butunluk(ham_tumu), "\n")
    print(canli_arsiv_bolumu(Path(__file__).resolve().parent.parent / "gozlem_arsivi.csv"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
