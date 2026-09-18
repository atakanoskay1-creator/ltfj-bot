#!/usr/bin/env python3
"""MODEL B - "gorussuz atmosferik sis olusum potansiyeli".

Model A (egit.py) soruyor: "mevcut gorus DAHIL, onumuzdeki 3 saatte sis
riski nedir?" Bu betik FARKLI bir soru soruyor: "gorus henuz dusmemisken,
salt atmosferik degiskenler (spread, ruzgar, saat...) yaklasan sisi ne kadar
onceden haber veriyor?" Iki model birbirinin YERINE GECMEZ.

METODOLOJI ZINCIRI (Model A ile ayni disiplin, hedef farkli):
  veri kalitesi -> sizintisiz hedef -> degisken tarama -> coklu dogrusallik
  -> model -> walk-forward -> (ayrica) dokunulmamis holdout -> dondurulmus
  calisma-ani modulu.

YASAK ALANLAR sis_modeli/olusum_alanlar.py'de tanimli ve `dogrula()` ile
CALISMA ZAMANINDA denetleniyor - gorus veya turevleri yanlislikla Model B'ye
giremiyor.

SINIR EMBARGOSU: varsayilan olarak ACIK (bkz. bolme.ayir_embargolu). Sebep:
hedef.hazirla() TUM veriyi bolunmeden once isliyor; bir egitim satirinin
ileriye bakan penceresi disaridaki bir donemin ham verisini kullanmis
olabilir (bkz. arastirma raporu Bolum 8-9). Bu satir-duzeyinde kucuk bir
etki ama zayif sinyalli gorussuz modelde orantisiz agirlik kazanabilir;
--embargo-kapat ile kapatilip Model A'nin davranisiyla dogrudan
karsilastirma da yapilabilir.

Kullanim:
    python -m sis_modeli.olusum_egit                  # tarama + walk-forward
    python -m sis_modeli.olusum_egit --dahil-gorus     # ablasyon karsilastirmasi
    python -m sis_modeli.olusum_egit --embargo-kapat   # embargosuz (Model A gibi)
    python -m sis_modeli.olusum_egit --tartismali      # tavan/sis_yakinligi de tara
"""

import argparse
import sys
from pathlib import Path

from sis_modeli import bolme, degerlendir, hedef, model, olusum_alanlar, tanilama, woe
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku

# Ablasyon (bu betikle GERCEKTEN OLCULDU - walk-forward, embargo acik,
# gelistirme donemi 2011-2023, holdout kapali):
#
#   kume                                          AP       BSS
#   spread+trend3+ruzgar_kuzey+saat (4)          0.0366   -0.0082
#   + sicaklik (5)  <-- SECILEN                  0.0493    0.0151
#   + ay yerine (5)                              0.0352   -0.0037  (ay ZARARLI)
#   + sicaklik + ay (6)                          0.0487    0.0080  (ay yine ZARARLI)
#   genis kume (8, zayif IV'liler haric)         0.0496    0.0149  (+0.0003 AP, 3 fazla parametre - degmiyor)
#   spread+trend3+trend1+ruzgar_kuzey+saat (5)   0.0411    0.0037  (trend1 trend3'u YENMIYOR)
#   yalniz spread+saat (2)                       0.0442    0.0023
#
# sicaklik EKLENMEDEN (yalnizca spread+trend+ruzgar+saat) model iklimden
# KOTU (BSS negatif) - sicaklik spread'in "seviyesini" tamamlayan bagimsiz
# bilgi tasiyor. ay HER kombinasyonda zararli (mevsimsellik, spread ve
# saat'in zaten tasidigi bilgiyi gurultuyle bulaniklastiriyor). Genis kume
# (8 degisken) ihmal edilebilir bir kazanc icin 3 fazladan parametre
# istiyor - az olayli veride (305 bagimsiz sis olayi) bu iyi bir takas
# degil, AYNI ilke Model A'da da izlendi (bkz. egit.py ALANLAR yorumu).
ALANLAR = ["spread", "spread_egilim_3", "sicaklik", "ruzgar_kuzey", "saat"]


def hava_sutunu_ekle(kayitlar: list) -> list:
    """'hava' ham string sutunundan sis_yakinligi (BR/nitelikli-FG) turetir.

    Sadece --tartismali istendiginde ekrana basiliyor; ALANLAR'a
    OTOMATIK girmiyor (bkz. olusum_alanlar.TARTISMALI_ADAYLAR)."""
    for r in kayitlar:
        r["sis_yakinligi"] = olusum_alanlar.sis_yakinligi(r.get("hava") or "")
    return kayitlar


def _tarama_bas(gelistirme: list, alanlar: list) -> None:
    print(f"{'değişken':<18}{'IV':>8}{'%5–%95':>18}{'mono':>7}{'PSI':>8}  yorum")
    for alan in alanlar:
        t = woe.kova_tablosu(gelistirme, alan, "hedef")
        if not t:
            print(f"{alan:<18}{'—':>8}   (kova kurulamadı - veri yetersiz)")
            continue
        sinirlar = [k["ust"] for k in t[:-1]]
        deger = woe.iv(t)
        alt, ust = woe.iv_guven_araligi(gelistirme, alan, "hedef", "gun",
                                        list(sinirlar), tekrar=150)
        # PSI: gelistirmenin ilk yarisi vs ikinci yarisi (kendi ici kararlilik)
        yillar = sorted({r["dt"].year for r in gelistirme})
        orta = yillar[len(yillar) // 2]
        ilk = [r for r in gelistirme if r["dt"].year < orta]
        son = [r for r in gelistirme if r["dt"].year >= orta]
        p = woe.psi(ilk, son, alan, list(sinirlar)) if ilk and son else 0.0
        print(f"{alan:<18}{deger:>8.3f}{f'{alt:.3f} – {ust:.3f}':>18}"
              f"{'evet' if woe.monoton_mu(t) else 'hayır':>7}{p:>8.3f}"
              f"  {woe.iv_yorumla(deger)}"
              f"{'  ** KAYIYOR' if p > 0.25 else ''}")


def _yontemler(egitim: list, test: list, alanlar: list) -> dict:
    katsayilar, tablolar, l2 = model.egit_secerek(egitim, alanlar)
    taban = sum(r["hedef"] for r in egitim) / max(len(egitim), 1)
    model_etiketi = "model (görüşlü)" if "gorus" in alanlar else "model (görüşsüz)"
    return {
        model_etiketi: [model.olasilik(katsayilar, r, tablolar) for r in test],
        "iklim": [taban] * len(test),
        "basit kural (spread+rüzgâr)": [model.basit_kural_baseline(r) for r in test],
    }, l2


def _skor_bas(baslik: str, gercek: list, tahminler: dict) -> None:
    iklim = tahminler["iklim"]
    print(f"\n{baslik}")
    print(f"  {'yöntem':<28}{'Brier×10⁴':>11}{'BSS':>8}{'AP':>8}"
          f"{'LogLoss':>9}{'ROC-AUC':>9}")
    for ad, p in tahminler.items():
        print(f"  {ad:<28}{1e4*degerlendir.brier(p, gercek):>11.2f}"
              f"{degerlendir.brier_skill(p, gercek, iklim):>8.3f}"
              f"{degerlendir.ortalama_kesinlik(p, gercek):>8.3f}"
              f"{degerlendir.log_loss(p, gercek):>9.3f}"
              f"{degerlendir.roc_auc(p, gercek):>9.3f}")


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--veri", type=Path, default=VARSAYILAN_VERI)
    a.add_argument("--dahil-gorus", action="store_true",
                   help="karşılaştırma için görüşü de ekler (Model A'ya "
                        "yakın bir küme) - Model B'nin KENDİSİ hâlâ görüşsüz "
                        "çalışır, bu YALNIZCA ablasyon karşılaştırması")
    a.add_argument("--embargo-kapat", action="store_true",
                   help="sınır embargosunu kapatır (bkz. modül başlığı)")
    a.add_argument("--tartismali", action="store_true",
                   help="tavan/sis_yakinligi'yi de WoE taramasına ekler")
    secenek = a.parse_args(argv)
    if not secenek.veri.exists():
        print(f"HATA: {secenek.veri} yok.", file=sys.stderr)
        return 1

    olusum_alanlar.dogrula(ALANLAR)   # çalışma zamanı yasak-alan denetimi

    ham = [r for r in veri_oku(secenek.veri) if r["zaman"][:4] >= str(bolme.ILK_YIL)]
    kayitlar = hava_sutunu_ekle(hedef.hazirla(ham))
    aday = hedef.onset_adaylari(kayitlar)
    gelistirme = bolme.gelistirme(aday)

    print(f"Model B — görüşsüz atmosferik sis oluşum potansiyeli "
          f"(ufuk {hedef.UFUK_SAAT}h)")
    print(f"Onset evreni (holdout hariç): {len(gelistirme)} an, "
          f"{sum(r['hedef'] for r in gelistirme)} pozitif, "
          f"{len({r['gun'] for r in gelistirme if r['hedef']})} ayrı gün\n")

    print("=== 1) Değişken tarama — aday kümesi (olusum_alanlar.ADAYLAR) ===")
    tarama_alanlari = list(olusum_alanlar.ADAYLAR)
    if secenek.tartismali:
        tarama_alanlari += olusum_alanlar.TARTISMALI_ADAYLAR
    _tarama_bas(gelistirme, tarama_alanlari)

    print(f"\n=== 2) Çoklu doğrusal bağlantı — seçilen küme {ALANLAR} ===")
    tablolar = model.woe_tablolari(gelistirme, ALANLAR)
    adlar, _ = tanilama.korelasyon_matrisi(gelistirme, tablolar)
    vifler = tanilama.vif(gelistirme, tablolar)
    print(f"  {'değişken':<18}{'VIF':>8}")
    for ad in adlar:
        uyari = "  ** DİKKAT" if vifler[ad] > tanilama.VIF_DIKKAT else ""
        print(f"  {ad:<18}{vifler[ad]:>8.2f}{uyari}")

    alanlar = ALANLAR + (["gorus"] if secenek.dahil_gorus else [])
    baslik = ("=== 3) Walk-forward — GÖRÜŞ DAHİL (ablasyon karşılaştırması) ==="
              if secenek.dahil_gorus else
              "=== 3) Walk-forward — GÖRÜŞSÜZ (Model B) ===")
    print(f"\n{baslik}")
    print(f"Değişkenler: {', '.join(alanlar)}")

    print(f"\n{'fold (test yılı)':<20}{'n':>8}{'poz':>6}"
          f"{'Brier×10⁴':>11}{'BSS':>8}{'AP':>8}{'L2':>8}")
    birikmis_gercek, birikmis_tahmin = [], {}
    for egitim_yillari, test_yillari in bolme.foldlar():
        if secenek.embargo_kapat:
            egitim = bolme.ayir(gelistirme, egitim_yillari)
        else:
            egitim = bolme.ayir_embargolu(gelistirme, egitim_yillari,
                                          sonraki_yil=min(test_yillari))
        test = bolme.ayir(gelistirme, test_yillari)
        if not test or not any(r["hedef"] for r in test):
            continue
        tahminler, l2 = _yontemler(egitim, test, alanlar)
        gercek = [bool(r["hedef"]) for r in test]
        etiket = "-".join(str(y) for y in (test_yillari[0], test_yillari[-1]))
        anahtar = "model (görüşlü)" if secenek.dahil_gorus else "model (görüşsüz)"
        print(f"{etiket:<20}{len(test):>8}{sum(gercek):>6}"
              f"{1e4*degerlendir.brier(tahminler[anahtar], gercek):>11.2f}"
              f"{degerlendir.brier_skill(tahminler[anahtar], gercek, tahminler['iklim']):>8.3f}"
              f"{degerlendir.ortalama_kesinlik(tahminler[anahtar], gercek):>8.3f}"
              f"{l2:>8.0f}")
        birikmis_gercek.extend(gercek)
        for ad, p in tahminler.items():
            birikmis_tahmin.setdefault(ad, []).extend(p)

    _skor_bas(f"Birikmiş ({len(birikmis_gercek)} an, {sum(birikmis_gercek)} pozitif):",
              birikmis_gercek, birikmis_tahmin)

    model_etiketi = "model (görüşlü)" if secenek.dahil_gorus else "model (görüşsüz)"
    print(f"\n=== Güvenilirlik ({model_etiketi}) ===")
    print(f"  {'kova':<10}{'n':>8}{'ort. tahmin':>13}{'gerçekleşen':>13}{'poz':>6}")
    for k in degerlendir.guvenilirlik(birikmis_tahmin[model_etiketi], birikmis_gercek):
        print(f"  {k['kova']/10:.1f}-{(k['kova']+1)/10:.1f}   {k['n']:>8}"
              f"{100*k['ortalama_tahmin']:>12.2f}%{100*k['gerceklesen']:>12.2f}%"
              f"{k['pozitif']:>6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
