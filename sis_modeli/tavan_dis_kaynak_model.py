#!/usr/bin/env python3
"""Tavan<500ft için ÇOK DEĞİŞKENLİ (lojistik regresyon) model - dış kaynak
adaylarının GERÇEK katkısını, tek bir birleşik modelde test eder.

NEDEN AYRI BİR BETİK: `tavan_dis_kaynak_tarama.py` (tekil IV) ve
`tavan_tablo.py`nin PR #50'deki denemesi (ikili tablo) `acik_meteo_nem_2m` ve
`komsu_tavan_ozellik`'i HİÇBİRİ `sis_olasilik` ile AYNI ANDA, diğer tüm hub
değişkenleriyle (spread, görüş, tavan_özellik, saat, rüzgâr_kuzey) BİRLİKTE
test etmedi - tablo formatı yapısal olarak sadece İKİ ekseni birleştirebiliyor
(bkz. tavan_tablo.py'nin PR #50 sonucu: yüksek tekil IV, ikili tabloda
kazanmadı - şüphe: sis_olasilik ile örtüşen/kolineer bilgi). Bu betik
`model.py`nin (sis modelinde kullanılan) AYNI IRLS/WoE makinesini kullanarak
GERÇEKTEN çok değişkenli bir model kurar ve VIF ile kolinerlik iddiasını
SAYISALLAŞTIRIR - varsayım olarak bırakılmaz.

TEMEL (BASELINE) - tavan_tablo.py'nin ADAY_CIFTLER'daki "hub" değişkenleri,
HEPSİ BİRLİKTE: spread, görüş, tavan_özellik, saat, rüzgâr_kuzey, sis_olasılık.

DIŞ KAYNAK ADAYLARI (a priori, PR #49/#50'de tekil/ikili taramada güçlü
çıkanlar): acik_meteo_nem_2m, komsu_tavan_ozellik.

DÖRT SPESİFİKASYON karşılaştırılır (TEMEL, TEMEL+nem, TEMEL+komşu tavan,
TEMEL+ikisi) - geliştirme İÇİNDE yürüyen pencereyle, EŞLEŞTİRİLMİŞ gün bazlı
blok bootstrap ile (aynı fold/gün örneklemesi, iki spesifikasyon arasındaki
FARKIN kendisinin güven aralığı - bkz. veri_kalitesi.eslesmis_fark_araligi).
Holdout yalnızca TEMEL'i geçen bir spesifikasyon varsa VE yalnızca TEK KEZ
açılır.

Kullanım:
    python -m sis_modeli.tavan_dis_kaynak_model
    python -m sis_modeli.tavan_dis_kaynak_model --holdout      # TEK ATIŞ
"""

import argparse
import sys
from pathlib import Path

from sis_modeli import bolme, degerlendir, model, tanilama, tavan
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku
from sis_modeli.tavan_tablo import (_ic_foldlar, dis_kaynak_ekle,
                                    sis_olasiligi_ekle)
from sis_modeli.veri_kalitesi import eslesmis_fark_araligi

TEMEL = ["spread", "gorus", "tavan_ozellik", "saat", "ruzgar_kuzey", "sis_olasilik"]
DIS_KAYNAK = ["acik_meteo_nem_2m", "komsu_tavan_ozellik"]

SPESIFIKASYONLAR = [
    ("TEMEL", list(TEMEL)),
    ("TEMEL + nem", TEMEL + ["acik_meteo_nem_2m"]),
    ("TEMEL + komşu tavan", TEMEL + ["komsu_tavan_ozellik"]),
    ("TEMEL + ikisi", TEMEL + DIS_KAYNAK),
]


def hazirla(veri_yolu: Path, esik_ft: int) -> list:
    aday = tavan.hazirla(veri_oku(veri_yolu), esik_ft=esik_ft)
    aday = sis_olasiligi_ekle(aday)
    return dis_kaynak_ekle(aday)


def wf_karsilastir(gelistirme: list, spesifikasyonlar: list,
                   embargo: bool = True) -> dict:
    """TÜM spesifikasyonları AYNI fold döngüsünde, AYNI test kayıtları
    üzerinde ölçer - EŞLEŞTİRİLMİŞ karşılaştırma için ŞART: eslesmis_fark_araligi
    iki tahmin listesini INDEKS BAZINDA eşler, bu yüzden ikisi FARKLI
    fold kümelerinde üretilirse (biri yakınsayıp diğeri yakınsamazsa)
    sessizce YANLIŞ hizalanır. Bu yüzden bir fold'da HERHANGİ BİR
    spesifikasyon yakınsamazsa (tazeleme.py'deki gibi gerçekten olabiliyor -
    bkz. commit mesajı), o fold TÜM spesifikasyonlar için atlanır."""
    yillar = sorted({r["dt"].year for r in gelistirme})
    kayitlar, gercek = [], []
    tahminler = {ad: [] for ad, _ in spesifikasyonlar}
    atlanan = []
    for eg_yillari, test_yillari in _ic_foldlar(yillar):
        eg = bolme.ayir(gelistirme, eg_yillari)
        if embargo:
            eg = bolme.embargo_penceresi(eg, min(test_yillari))
        te = bolme.ayir(gelistirme, test_yillari)
        if not te or not any(r["hedef"] for r in te):
            continue
        fold_katsayilar = {}
        yakinsamadi = False
        for ad, alanlar in spesifikasyonlar:
            try:
                fold_katsayilar[ad] = model.egit_secerek(eg, alanlar)
            except model.Yakinsamadi:
                yakinsamadi = True
                break
        if yakinsamadi:
            atlanan.append(test_yillari)
            continue
        for r in te:
            kayitlar.append(r)
            gercek.append(bool(r["hedef"]))
        for ad, (katsayilar, tablolar, _l2) in fold_katsayilar.items():
            tahminler[ad].extend(
                model.olasilik(katsayilar, r, tablolar) for r in te)

    taban = sum(gercek) / len(gercek) if gercek else 0.0
    iklim = [taban] * len(gercek)
    sonuc = {"kayitlar": kayitlar, "gercek": gercek, "atlanan": atlanan,
             "spesifikasyon": {}}
    for ad, tahmin in tahminler.items():
        sonuc["spesifikasyon"][ad] = {
            "tahmin": tahmin, "n": len(gercek), "poz": sum(gercek),
            "brier": degerlendir.brier(tahmin, gercek),
            "bss": degerlendir.brier_skill(tahmin, gercek, iklim),
            "ap": degerlendir.ortalama_kesinlik(tahmin, gercek),
        }
    return sonuc


def _dondur_yazdir(ad: str, alanlar: list, egitim: list) -> None:
    """tazeleme.py'nin dondurma cikti bicimiyle AYNI - ltfj_tavan_dis_kaynak.py'ye
    dogrudan yapistirilabilir KATSAYILAR/WOE_TABLOLARI literalleri basar.

    AYNI egitim kumesi (embargo_penceresi ile holdout sinirina kadar
    genisletilmis gelistirme) main()'in --holdout dalinda KULLANILMIS olan
    kumeyle BIREBIR AYNIDIR - yani burada basilan katsayilar, holdout'ta
    dogrulanan sayilarin ta kendisidir, yeni bir egitim degildir."""
    katsayilar, tablolar, l2 = model.egit_secerek(egitim, alanlar)
    print(f"\n--- {ad} (L2={l2:.0f}, n={len(egitim)}, "
          f"poz={sum(r['hedef'] for r in egitim)}) ---")
    print(f"SABIT_TERIM = {katsayilar[0]!r}")
    print("KATSAYILAR = {")
    for alan, k in zip(sorted(tablolar.keys()), katsayilar[1:]):
        print(f"    {alan!r}: {k!r},")
    print("}")
    print("WOE_TABLOLARI = {")
    for alan in sorted(tablolar.keys()):
        print(f"    {alan!r}: (")
        for k in tablolar[alan]:
            print(f"        ({k['ust']!r}, {k['woe']!r}),")
        print("    ),")
    print("}")


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    a.add_argument("--esik", type=int, default=tavan.TABLO_ESIGI_FT)
    a.add_argument("--holdout", action="store_true", help="TEK ATIŞ")
    a.add_argument("--dondur", action="store_true",
                   help="TEMEL ve TEMEL+ikisi icin donuk modul literallerini bas "
                        "(holdout'ta zaten dogrulanmis egitim kumesiyle)")
    secenek = a.parse_args(argv)
    if not secenek.veri.exists():
        print(f"HATA: {secenek.veri} yok.", file=sys.stderr)
        return 1

    aday = hazirla(secenek.veri, secenek.esik)
    gelistirme = bolme.gelistirme(aday)
    print(f"Hedef: 3 saat içinde tavan <{secenek.esik} ft (onset), "
          f"rejim {tavan.REJIM_ILK_YIL}+")
    print(f"Geliştirme: {len(gelistirme)} an, "
          f"{sum(r['hedef'] for r in gelistirme)} pozitif\n")

    print("=== 1) Çoklu doğrusal bağlantı (VIF) — TEMEL + dış kaynak ===")
    tablolar = model.woe_tablolari(gelistirme, TEMEL + DIS_KAYNAK)
    vifler = tanilama.vif(gelistirme, tablolar)
    print(f"  {'değişken':<22}{'VIF':>8}")
    for ad in sorted(vifler):
        uyari = "  ** DİKKAT (yüksek kolinerlik)" if vifler[ad] > tanilama.VIF_DIKKAT else ""
        print(f"  {ad:<22}{vifler[ad]:>8.2f}{uyari}")

    print("\n=== 2) Geliştirme içi yürüyen pencere — spesifikasyon karşılaştırması ===")
    sonuc = wf_karsilastir(gelistirme, SPESIFIKASYONLAR)
    if sonuc["atlanan"]:
        print(f"  (NOT: {len(sonuc['atlanan'])} fold IRLS yakınsamadığı için "
              f"TÜM spesifikasyonlarda atlandı: {sonuc['atlanan']})")
    print(f"  {'spesifikasyon':<24}{'n':>8}{'poz':>6}{'Brier×10⁴':>12}{'BSS':>8}{'AP':>8}")
    for ad, _alanlar in SPESIFIKASYONLAR:
        s = sonuc["spesifikasyon"][ad]
        print(f"  {ad:<24}{s['n']:>8}{s['poz']:>6}{1e4*s['brier']:>12.2f}"
              f"{s['bss']:>8.3f}{s['ap']:>8.3f}")

    print("\n=== 3) TEMEL'e karşı EŞLEŞTİRİLMİŞ fark (gün bazlı blok bootstrap) ===")
    temel = sonuc["spesifikasyon"]["TEMEL"]
    kazanan = None
    for ad, _alanlar in SPESIFIKASYONLAR[1:]:
        s = sonuc["spesifikasyon"][ad]
        fark = s["ap"] - temel["ap"]
        alt, ust = eslesmis_fark_araligi(
            sonuc["kayitlar"], temel["tahmin"], s["tahmin"], sonuc["gercek"],
            degerlendir.ortalama_kesinlik)
        print(f"  {ad:<24}AP farkı {fark:+.3f}   %5–%95: {alt:+.3f} – {ust:+.3f}"
              f"{'  ** GERÇEK KAZANÇ' if alt > 0 else ''}")
        if alt > 0 and (kazanan is None or s["ap"] > sonuc["spesifikasyon"][kazanan]["ap"]):
            kazanan = ad

    if kazanan is None:
        print("\nSONUÇ: hiçbir dış kaynak eklemesi TEMEL'i eşleştirilmiş "
              "aralıkta GERÇEKTEN geçmedi. Holdout açılmayacak (TEK ATIŞ "
              "kuralı: kazanan yoksa tüketmenin gerekçesi yok).")
        return 0
    print(f"\nSONUÇ: '{kazanan}' TEMEL'i eşleştirilmiş aralıkta geçti - "
          f"holdout adayı.")

    if not secenek.holdout:
        print("\n(Holdout açılmadı. Açmak için: --holdout)")
        return 0

    print("\n" + "=" * 70)
    print(f"=== 4) NİHAİ HOLDOUT (2024-2026) — TEK ATIŞ — '{kazanan}' vs TEMEL ===")
    print("=" * 70)
    egitim_tum = bolme.embargo_penceresi(gelistirme, min(bolme.HOLDOUT_YILLARI))
    hol = bolme.holdout(aday)
    if not hol:
        print("HATA: holdout boş.", file=sys.stderr)
        return 1
    gercek_hol = [bool(r["hedef"]) for r in hol]
    print(f"Holdout: {len(hol)} an, {sum(gercek_hol)} pozitif "
          f"(taban oran %{100*sum(gercek_hol)/len(hol):.2f})\n")

    kazanan_alanlar = dict(SPESIFIKASYONLAR)[kazanan]
    print(f"  {'spesifikasyon':<24}{'Brier×10⁴':>12}{'BSS':>8}{'AP':>8}{'AP %5–%95':>18}")
    tahminler_hol = {}
    for ad, alanlar in (("TEMEL", TEMEL), (kazanan, kazanan_alanlar)):
        katsayilar, tablolar, l2 = model.egit_secerek(egitim_tum, alanlar)
        p = [model.olasilik(katsayilar, r, tablolar) for r in hol]
        tahminler_hol[ad] = p
        iklim = [sum(r["hedef"] for r in egitim_tum) / len(egitim_tum)] * len(hol)
        alt, ust = degerlendir.blok_guven_araligi(hol, p, gercek_hol,
                                                  degerlendir.ortalama_kesinlik)
        print(f"  {ad:<24}{1e4*degerlendir.brier(p, gercek_hol):>12.2f}"
              f"{degerlendir.brier_skill(p, gercek_hol, iklim):>8.3f}"
              f"{degerlendir.ortalama_kesinlik(p, gercek_hol):>8.3f}"
              f"{f'{alt:.3f} – {ust:.3f}':>18}   (L2={l2:.0f})")

    fark = (degerlendir.ortalama_kesinlik(tahminler_hol[kazanan], gercek_hol)
            - degerlendir.ortalama_kesinlik(tahminler_hol["TEMEL"], gercek_hol))
    alt, ust = eslesmis_fark_araligi(hol, tahminler_hol["TEMEL"],
                                     tahminler_hol[kazanan], gercek_hol,
                                     degerlendir.ortalama_kesinlik)
    print(f"\nHoldout'ta eşleştirilmiş AP farkı ({kazanan} - TEMEL): {fark:+.3f}"
          f"   %5–%95: {alt:+.3f} – {ust:+.3f}")
    if alt > 0:
        print("KARAR: kural sağlandı - holdout'ta da gerçek kazanç doğrulandı.")
    else:
        print("KARAR: holdout'ta doğrulanmadı - geliştirme içi kazanç "
              "tesadüfi olabilir. Canlıya ALINMAMALI.")
        return 0

    if secenek.dondur:
        print("\n" + "=" * 70)
        print("=== 5) DONDURMA — ltfj_tavan_dis_kaynak.py için literaller ===")
        print("=" * 70)
        print("AŞAĞIDAKİ İKİ BLOK, egitim_tum (embargo'lu geliştirme, holdout "
              "SINIRINA KADAR) üzerinde eğitildi - yukarıdaki holdout "
              "sonuçlarıyla AYNI eğitim kümesi. TEMEL bloğu, dış kaynak "
              "bayat/eksik olduğunda GERİ DÜŞME (fallback) modeli olarak "
              "kullanılacak.")
        _dondur_yazdir("TEMEL (fallback)", TEMEL, egitim_tum)
        _dondur_yazdir(kazanan, kazanan_alanlar, egitim_tum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
