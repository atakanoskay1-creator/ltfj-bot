#!/usr/bin/env python3
"""QV3 (LVO Hazirlik hedefi) - aday degiskenler, veri-tabanli secim, model.

Model A ile ayni aile: degiskenler WoE'ye cevrilir, L2 cezali lojistik
regresyon IRLS ile cozulur (sis_modeli.model). Fark: degisken seti ELLE
secilmez - her fold'un KENDI egitim verisi icinde ileri secimle bulunur
(ileri_secim). Test yillari secime hic karismaz.

Iki teknik duzeltme (QV3 denemesinde olculdu, model.py'ye dokunmadan):
  - 0/1 degiskenler: woe._esitlik_kovalari esit frekansli sinir arar; nadir
    bir 0/1 degiskende tum degerler tek kovaya duser ve degisken sessizce
    kaybolur. IKILI alanlar icin sinir [1] verilir (0 | 1).
  - Yakinsama: guclu bir degisken (or. parcali sis) bazi L2 degerlerinde
    quasi-complete separation'a yol aciyor (model.Yakinsamadi). Secilen L2
    yakinsamazsa bir sonraki DAHA GUCLU L2 denenir.

QV3 CANLIYA BAGLANMAZ.
"""

import math
import re
from collections import Counter
from datetime import timedelta

from sis_modeli import model, woe

RVR_YOK_M = 2000          # RVR raporlanmadi = gorus ve RVR 1500 m ustunde
TAVAN_YOK_FT = 20000      # BKN/OVC/VV yok

SAYISAL = ("gorus", "gorus_egilim_1", "rvr_min_d", "rvr_24_d", "rvr_06_d", "tavan_d",
           "spread", "spread_egilim_1", "spread_egilim_3", "sicaklik",
           "ruzgar_hiz", "ruzgar_kuzey", "ruzgar_dogu", "ruzgar_egilim_1",
           "qnh_egilim_3", "saat", "ay")
IKILI = ("parcali_sis", "br", "yagis", "kd_hafif", "kd_nemli")
ADAYLAR = SAYISAL + IKILI
MODEL_A_ALANLARI = ("spread", "spread_egilim_3", "saat", "ruzgar_kuzey", "gorus")

IV_ESIK = 0.02            # "zayif"in alti - secime hic girmez
ON_SECIM = 12             # IV'ye gore ilk N aday ileri secime girer
MAKS_DEGISKEN = 6
MIN_KAZANC = 0.005        # ic dogrulama AP'sinde
SECIM_L2 = 100.0

_PARCALI = re.compile(r"(BC|PR|MI|VC)FG")
_YAGIS = re.compile(r"(RA|DZ|SN|SG|PL|GR|GS|UP)")


def _ikili_kod(hava, desen) -> int:
    return int(any(desen.search(k) for k in (hava or "").split()))


def aday_ekle(kayitlar: list) -> list:
    """hedef.hazirla + qv3_hedef ciktisina turetilmis adaylari ekler."""
    yer = {r["dt"]: r for r in kayitlar}
    for r in kayitlar:
        hava = r.get("hava")
        r["parcali_sis"] = _ikili_kod(hava, _PARCALI)
        r["br"] = int(any(k.lstrip("+-") == "BR" for k in (hava or "").split()))
        r["yagis"] = _ikili_kod(hava, _YAGIS)
        yon, hiz, sp = r.get("ruzgar_yon"), r.get("ruzgar_hiz"), r.get("spread")
        r["kd_hafif"] = (None if yon is None or hiz is None
                         else int(3 <= hiz <= 10 and (0 <= yon <= 60 or yon == 360)))
        r["kd_nemli"] = (None if r["kd_hafif"] is None or sp is None
                         else int(r["kd_hafif"] == 1 and sp <= 1))
        for a in ("rvr_min", "rvr_24", "rvr_06"):
            r[f"{a}_d"] = RVR_YOK_M if r.get(a) is None else r[a]
        r["tavan_d"] = TAVAN_YOK_FT if r.get("tavan") is None else r["tavan"]
        onceki = yer.get(r["dt"] - timedelta(hours=1))
        r["gorus_egilim_1"] = (None if onceki is None or r.get("gorus") is None
                               or onceki.get("gorus") is None
                               else r["gorus"] - onceki["gorus"])
    return kayitlar


def woe_tablolari(egitim: list, alanlar) -> dict:
    tablolar = {}
    for a in alanlar:
        t = woe.kova_tablosu(egitim, a, "hedef", sinirlar=[1] if a in IKILI else None)
        if t:
            tablolar[a] = t
    return tablolar


def _egit_yedekli(desenler, toplam, pozitif, l2):
    """Yakinsamazsa bir sonraki daha guclu L2. (katsayilar, kullanilan_l2)"""
    for aday in [x for x in model.L2_ADAYLARI if x >= l2] or [l2]:
        try:
            return model.egit(desenler, toplam, pozitif, l2=aday), aday
        except (model.Yakinsamadi, model.TekilSistem):
            continue
    raise model.Yakinsamadi(f"hicbir L2 >= {l2} yakinsamadi")


def egit(egitim: list, alanlar) -> tuple:
    """L2'yi egitimin son yilinda (ic dogrulama) secer, tum egitimle yeniden
    egitir. (katsayilar, tablolar, l2) - model.egit_secerek ile ayni kural."""
    yillar = sorted({r["dt"].year for r in egitim})
    ic_egitim = [r for r in egitim if r["dt"].year < yillar[-1]]
    ic_test = [r for r in egitim if r["dt"].year == yillar[-1]]
    en_iyi, en_iyi_l2 = -1.0, SECIM_L2
    if ic_egitim and any(r["hedef"] for r in ic_test):
        tablolar = woe_tablolari(ic_egitim, alanlar)
        d, t, p = model.desenlere_topla(ic_egitim, tablolar)
        gercek = [bool(r["hedef"]) for r in ic_test]
        for l2 in model.L2_ADAYLARI:
            try:
                beta = model.egit(d, t, p, l2=l2)
            except (model.Yakinsamadi, model.TekilSistem):
                continue
            skor = model._ortalama_kesinlik(
                [model.olasilik(beta, r, tablolar) for r in ic_test], gercek)
            if skor > en_iyi:
                en_iyi, en_iyi_l2 = skor, l2
    tablolar = woe_tablolari(egitim, alanlar)
    d, t, p = model.desenlere_topla(egitim, tablolar)
    beta, l2 = _egit_yedekli(d, t, p, en_iyi_l2)
    return beta, tablolar, l2


def olasilik(katsayilar, kayit, tablolar) -> float:
    return model.olasilik(katsayilar, kayit, tablolar)


def iv_tarama(egitim: list, adaylar=ADAYLAR) -> list:
    """[(alan, IV)] buyukten kucuge - yalnizca verilen egitim verisiyle."""
    tablolar = woe_tablolari(egitim, adaylar)
    return sorted(((a, woe.iv(t)) for a, t in tablolar.items()), key=lambda x: -x[1])


def _ap_alt_kume(sutun_e, sutun_t, y_e, y_t, alanlar) -> float:
    """Onbellekli WoE sutunlariyla bir alt kumenin ic dogrulama AP'si."""
    top, poz = Counter(), Counter()
    for i, y in enumerate(y_e):
        d = tuple(sutun_e[a][i] for a in alanlar)
        top[d] += 1
        poz[d] += y
    desenler = list(top)
    try:
        beta, _ = _egit_yedekli(desenler, [top[d] for d in desenler],
                                [poz[d] for d in desenler], SECIM_L2)
    except (model.Yakinsamadi, model.TekilSistem):
        return -1.0
    tahmin = []
    for i in range(len(y_t)):
        eta = beta[0] + sum(b * sutun_t[a][i] for b, a in zip(beta[1:], alanlar))
        tahmin.append(1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, eta)))))
    return model._ortalama_kesinlik(tahmin, [bool(y) for y in y_t])


def ileri_secim(egitim: list, adaylar=ADAYLAR, maks=MAKS_DEGISKEN,
                min_kazanc=MIN_KAZANC) -> dict:
    """Egitimin son yili ic dogrulama, oncesi ic egitim:
      1) ic egitimde IV < IV_ESIK olanlar elenir, kalanlardan IV'si en
         yuksek ON_SECIM aday alinir;
      2) bos kumeden baslayip her adimda ic dogrulama AP'sini en cok
         artiran degisken eklenir; kazanc min_kazanc'in altina dusunce durur.
    Donus: {"secilen": [...], "adimlar": [(alan, ap)], "iv": [(alan, iv)]}"""
    yillar = sorted({r["dt"].year for r in egitim})
    ic_e = [r for r in egitim if r["dt"].year < yillar[-1]]
    ic_t = [r for r in egitim if r["dt"].year == yillar[-1]]
    iv = iv_tarama(ic_e, adaylar)
    havuz = [a for a, v in iv if v >= IV_ESIK][:ON_SECIM]
    tablolar = woe_tablolari(ic_e, havuz)
    havuz = [a for a in havuz if a in tablolar]
    sutun_e = {a: [model._woe_degeri(tablolar[a], r.get(a)) for r in ic_e] for a in havuz}
    sutun_t = {a: [model._woe_degeri(tablolar[a], r.get(a)) for r in ic_t] for a in havuz}
    y_e = [int(bool(r["hedef"])) for r in ic_e]
    y_t = [int(bool(r["hedef"])) for r in ic_t]

    secilen, adimlar, mevcut = [], [], 0.0
    while len(secilen) < maks:
        skorlar = [(_ap_alt_kume(sutun_e, sutun_t, y_e, y_t, secilen + [a]), a)
                   for a in havuz if a not in secilen]
        if not skorlar:
            break
        ap, a = max(skorlar)
        if ap - mevcut < min_kazanc:
            break
        secilen.append(a)
        adimlar.append((a, round(ap, 4)))
        mevcut = ap
    return {"secilen": secilen, "adimlar": adimlar, "iv": iv}
