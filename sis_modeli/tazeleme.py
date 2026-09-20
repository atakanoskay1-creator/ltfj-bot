#!/usr/bin/env python3
"""Model A HOLDOUT TAZELEME denemesi - AYRI TUTULUR, henüz CANLIYA BAĞLANMAZ.

NEDEN: 2024-2026 holdout'u bu projede artık birçok kez "açıldı" (ilk
holdout raporu, 2021-2023 dışlama A/B testi, kalibrasyon denemesi,
ab_karsilastirma.py'nin üç analizi...). Her açılış meşru ama kümülatif
sürpriz azalıyor (bkz. sis_modeli/README.md Bölüm 14 notu). Kullanıcı
"4) holdout'u tazeleyelim" dedi - bu betik 2024-2026'yı EĞİTİME KATIP
modeli tazeleme fikrini dener, ama SONUÇ mantıklı görünene kadar
`ltfj_sis_olasilik.py` DEĞİŞTİRİLMEZ / `ltfj_sayfa.py`'ye BAĞLANMAZ.

DÜRÜSTLÜK NOTU (kaçınılmaz): asağıdaki walk-forward, 2024/2025/2026'yı
SIRAYLA test yılı olarak kullanıyor - yani bu, o dönemin verisine BİR
KEZ DAHA (ve bu kez ayrıntılı, yıl-yıl) bakmaktır. Bunu gizlemiyoruz;
tam tersine bu betiğin VAROLUŞ SEBEBİ budur - amaç yeni bir "TEK ATIŞ"
holdout DEĞİL, "bu yılları eğitime katmak modeli bozar mı" sorusuna
walk-forward diliyle dürüst bir cevaptır.

SONRAKI HOLDOUT: bu tazeleme uygulanırsa, model artık HİÇBİR gerçekten
görülmemiş veriyle test edilmemiş olur - 2027+ verisi birikene kadar
yeni bir kör test YOKTUR. Bu, göze alınması gereken açık bir bedeldir.

Kullanım:
    python -m sis_modeli.tazeleme
"""
import sys
from pathlib import Path

from sis_modeli import bolme, degerlendir, hedef, model
from sis_modeli.egit import ALANLAR
from sis_modeli.istatistik import VARSAYILAN_VERI, veri_oku

# 2024, 2025, 2026'yi SIRAYLA yeni walk-forward test yillari olarak ekliyor -
# bolme.foldlar()'in kendi guvenlik kelepcesini (holdout yillarini asla
# asmama) BILEREK atlıyoruz, bu yuzden bolme.py DEGIL burada, izole ve acikca
# adlandirilmis bir fonksiyonda.
GENISLETILMIS_TEST_YILLARI = (2024, 2025, 2026)


def genisletilmis_foldlar() -> list[tuple]:
    """bolme.foldlar()'in normal (holdout'a dokunmayan) fold'larina,
    2024/2025/2026'yi TEK TEK yeni test yillari olarak ekler - her biri
    KENDINDEN ONCEKI tum yillarla egitilir (genisleyen pencere, ayni ilke)."""
    normal = bolme.foldlar()
    ekstra = []
    for yil in GENISLETILMIS_TEST_YILLARI:
        egitim_yillari = tuple(range(bolme.ILK_YIL, yil))
        ekstra.append((egitim_yillari, (yil,)))
    return normal + ekstra


def main() -> int:
    if not VARSAYILAN_VERI.exists():
        print(f"HATA: {VARSAYILAN_VERI} yok.", file=sys.stderr)
        return 1

    ham = [r for r in veri_oku(VARSAYILAN_VERI) if r["zaman"][:4] >= str(bolme.ILK_YIL)]
    kayitlar = hedef.hazirla(ham)
    aday = hedef.onset_adaylari(kayitlar)   # HOLDOUT DAHIL - bu betiğin amacı bu

    print("=== UYARI: bu betik 2024-2026'yı walk-forward TEST yılı olarak "
         "kullanıyor - holdout'un bir başka (Nth) açılışı ===\n")

    print(f"{'fold (test yılı)':<20}{'n':>8}{'poz':>6}"
         f"{'Brier×10⁴':>11}{'BSS':>8}{'AP':>8}{'L2':>8}")
    birikmis_g, birikmis_p, birikmis_test = [], [], []
    birikmis_iklim = []
    etiketler_atlandi = []
    for egitim_yillari, test_yillari in genisletilmis_foldlar():
        egitim = bolme.ayir(aday, egitim_yillari)
        test = bolme.ayir(aday, test_yillari)
        if not test or not any(r["hedef"] for r in test):
            continue
        etiket = "-".join(str(y) for y in (test_yillari[0], test_yillari[-1]))
        yeni_mi = " (YENİ - eski holdout)" if test_yillari[0] in GENISLETILMIS_TEST_YILLARI else ""
        try:
            katsayilar, tablolar, l2 = model.egit_secerek(egitim, ALANLAR)
        except model.Yakinsamadi as e:
            print(f"{etiket + yeni_mi:<20}YAKINSAMADI - atlandı ({e})")
            etiketler_atlandi.append(etiket + yeni_mi)
            continue
        iklim = model.iklim_baseline(egitim)
        p = [model.olasilik(katsayilar, r, tablolar) for r in test]
        p_iklim = [model.iklim_tahmin(iklim, r) for r in test]
        gercek = [bool(r["hedef"]) for r in test]

        bss = degerlendir.brier_skill(p, gercek, p_iklim)
        ap = degerlendir.ortalama_kesinlik(p, gercek)
        print(f"{etiket + yeni_mi:<20}{len(test):>8}{sum(gercek):>6}"
             f"{1e4*degerlendir.brier(p, gercek):>11.2f}{bss:>8.3f}{ap:>8.3f}{l2:>8.0f}")

        birikmis_g.extend(gercek)
        birikmis_p.extend(p)
        birikmis_test.extend(test)
        birikmis_iklim.extend(p_iklim)

    if etiketler_atlandi:
        print(f"\n(Atlanan fold'lar - yakınsamadı, birikmiş toplama dahil "
             f"DEĞİL: {', '.join(etiketler_atlandi)})")

    ap_tum = degerlendir.ortalama_kesinlik(birikmis_p, birikmis_g)
    bss_tum = degerlendir.brier_skill(birikmis_p, birikmis_g, birikmis_iklim)
    print(f"\n=== Tüm fold'lar (2015-2026) birikmiş: {len(birikmis_g)} an, "
         f"{sum(birikmis_g)} pozitif ===")
    print(f"Brier×10⁴: {1e4*degerlendir.brier(birikmis_p, birikmis_g):.2f}  "
         f"BSS: {bss_tum:.3f}  AP: {ap_tum:.3f}")
    alt, ust = degerlendir.blok_guven_araligi(
        birikmis_test, birikmis_p, birikmis_g, degerlendir.ortalama_kesinlik)
    print(f"AP %5–%95 (blok bootstrap): {alt:.3f} – {ust:.3f}")

    print("\n=== Güvenilirlik (tüm fold'lar, 2015-2026) ===")
    print(f"  {'kova':<10}{'n':>8}{'ort. tahmin':>13}{'gerçekleşen':>13}{'poz':>6}")
    for k in degerlendir.guvenilirlik(birikmis_p, birikmis_g):
        print(f"  {k['kova']/10:.1f}-{(k['kova']+1)/10:.1f}   {k['n']:>8}"
             f"{100*k['ortalama_tahmin']:>12.2f}%{100*k['gerceklesen']:>12.2f}%{k['pozitif']:>6}")

    print("\n=== TASLAK: 2011-2026'nın TAMAMIYLA eğitilmiş NİHAİ aday model "
         "(HENÜZ CANLIYA BAĞLANMADI) ===\n")
    try:
        katsayilar, tablolar, l2 = model.egit_secerek(aday, ALANLAR)
    except model.Yakinsamadi as e:
        print(f"YAKINSAMADI: {e}\n")
        print("=== SONUÇ ===")
        print("Bu deneyin NİHAİ TASLAK adımı üretilemedi: 2011-2026 havuzunun "
             "TAMAMIYLA eğitimi, a priori L2 ızgarasının iç doğrulamayla "
             "seçtiği L2 değerinde yakınsamıyor (muhtemel quasi-complete "
             "separation - havuz büyüyünce ortaya çıkan çok nadir, tam "
             "ayrıştırıcı WoE hücreleri). Bu SONUCU post-hoc daha büyük bir "
             "L2 seçerek 'düzeltmek', ızgaranın sonuca bakılmadan a priori "
             "seçilmesi ilkesini bozar - o yüzden burada yapılmadı. Fold "
             "bazlı walk-forward sonuçları (yukarıda) yine de geçerli ve "
             "yorumlanabilir; sadece TÜM havuzu tek modelde birleştirme "
             "adımı bu haliyle güvenilir bir sonuç üretmiyor. "
             "ltfj_sis_olasilik.py DEĞİŞTİRİLMEDİ, ltfj_sayfa.py'ye "
             "BAĞLANMADI.")
        return 0
    alanlar_sirali = sorted(tablolar.keys())
    print(f"SABIT_TERIM = {katsayilar[0]!r}")
    print(f"Seçilen L2 = {l2:.0f}")
    print("KATSAYILAR = {")
    for alan, k in zip(alanlar_sirali, katsayilar[1:]):
        print(f"    {alan!r}: {k!r},")
    print("}")
    print(f"\nEGITIM_AN_SAYISI = {len(aday)}")
    print(f"EGITIM_POZITIF = {sum(r['hedef'] for r in aday)}")
    print("\n(WOE_TABLOLARI tam çıktısı için --tam bayrağı eklenebilir; burada "
         "yalnızca katsayılar gösteriliyor - taslak inceleme için yeterli.)")

    print("\n=== SONUÇ ===")
    print("Bu bir TASLAK'tır. ltfj_sis_olasilik.py DEĞİŞTİRİLMEDİ, "
         "ltfj_sayfa.py'ye BAĞLANMADI. Yukarıdaki fold sonuçları 'mantıklı' "
         "(önceki fold'larla tutarlı, çöküş yok) görünüyorsa, kullanıcı "
         "onayıyla bu katsayılar ayrı bir dondurulmuş modüle taşınıp "
         "canlıya bağlanabilir - ama bundan sonra YENİ bir gerçek (kör) "
         "holdout ancak 2027+ verisi birikince mümkün olur.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
