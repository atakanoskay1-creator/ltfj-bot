# Sis modeli V2 — Deney 1 raporu (V2a / V2b / V2c)

**Tarih:** 28 Eylül 2026 · **Protokol:** 1.0 · **Prosedür commit'i:** `4483836`
(gerçek veride çalıştırılmadan önce) · **Betik:** `python -m sis_modeli.deney1`
(tek çalıştırma, 2000 bootstrap tekrarı, tohum 0)

Hedefin teknik adı: **LTFJ düşük görüş/FG olayı**. Evren: `v2_evren` geliştirme
evreni (273.417 ızgara satırı, 272.235 onset satırı). V1 referansı:
solver-corrected V1 reference benchmark ile aynı prosedür (fold içinde yeniden
eğitilmiş, sönümlü Newton). Sonuç görüldükten sonra hiçbir değişken, seyreklik
kuralı, λ kuralı, bootstrap veya seçim ölçütü değiştirilmedi.

## 1. Sonuç

**Hiçbir varyant §8 birincil kuralını geçmedi. Deney 1 kapanır.** Protokol
1.0'ın bu spesifikasyonları ve bu değerlendirme prosedürüyle, 60/120 dakikalık
görüş ve 60 dakikalık spread gidişatının V1'in mevcut girdilerinin ötesinde
ölçülebilir bilgi taşıdığı gösterilemedi. Üç varyantta da nokta ΔLL negatif
(V2 hibrit sistemi V1 referansından biraz kötü) ve tek taraflı %98,33 alt sınır
sıfırın altında. §8 gereği Deney 1b, hazard modeli ve sonraki adımlara
geçilmez; canlıda V1 (Model A) kalır.

| model | λ (5 fold) | coverage_V2 | LL (nat) | ΔLL = LL(V1) − LL(V2) | tek taraflı %98,33 alt sınır | AP | Brier×10⁴ | LSS | birincil kural |
|---|---|---|---|---|---|---|---|---|---|
| V1 referansı | 100 (hepsi) | — | 0,027349 | — | — | 0,197 | 56,90 | 0,2892 | |
| V2a | 100 (hepsi) | %99,93 | 0,027690 | −0,000340 | −0,000537 | 0,172 | 58,02 | 0,2804 | geçmedi |
| V2b | 100 (hepsi) | %99,93 | 0,027664 | −0,000315 | −0,000517 | 0,170 | 58,04 | 0,2811 | geçmedi |
| V2c | 100 (hepsi) | %99,87 | 0,027677 | −0,000328 | −0,000587 | 0,173 | 57,98 | 0,2807 | geçmedi |

V2 satırlarındaki LL, AP, Brier ve LSS hibrit sistemin (geri dönüş dahil)
değerleridir. Havuzlanmış 168.429 satır, 1.091 Y=1.

## 2. Koruma şartları (§9.1; olay bootstrap'i, 160 olay)

| varyant | yakalama V1 / V2 | fark | fark %5 alt sınır (≥ −5 puan) | medyan ilk alarm V1 / V2 | olay başına fark medyanı | %5 alt sınır (≥ −30 dk) | koruma |
|---|---|---|---|---|---|---|---|
| V2a | %89,4 / %89,4 | 0,0 | −1,2 puan | 120 / 120 dk | 0 | 0 dk | geçti |
| V2b | %89,4 / %89,4 | 0,0 | −1,2 puan | 120 / 120 dk | 0 | 0 dk | geçti |
| V2c | %89,4 / %89,4 | 0,0 | −1,2 puan | 120 / 120 dk | 0 | 0 dk | geçti |

Koruma şartları geçildi ama birincil kural geçilmediği için seçim olmaz.
U4'ün alternatif okuması (medyanlar farkı) da her varyantta aynı kararı verdi
(%5 alt sınır: V2a 0, V2b −15, V2c 0 dk).

## 3. Tanılamalar (karar vermez)

| kesit | V2a ΔLL [alt sınır] | V2b ΔLL [alt sınır] | V2c ΔLL [alt sınır] |
|---|---|---|---|
| yalnız V2'nin çalıştığı satırlar (§9.2) | −0,000341 [−0,000537] | −0,000315 [−0,000518] | −0,000328 [−0,000588] |
| penceresinde SN olmayan satırlar (§9.3) | −0,000373 [−0,000539] | −0,000380 [−0,000545] | −0,000371 [−0,000571] |
| ufku tam 6/6 satırlar (Deney 0 §7.2) | −0,000324 [−0,000519] | −0,000298 [−0,000503] | −0,000312 [−0,000572] |

- Bütün tanılama kesitleri birincil sonuçla aynı yönde. SN'siz satırlarda
  da V2 V1'den iyi değil; §1'deki "daha iyi sis modeli" ifadesi kullanılmaz.
- Olay düzeyi SN: ≥1 SN içeren 42 olayda yakalama V1 %76,2 → V2 %73,8; SN'siz
  118 olayda %94,1 → %94,9 (üç varyantta aynı).
- Fold başına ΔLL: 2021–22'de üç varyant da hafif pozitif (+0,00003 …
  +0,00012), diğer dört birincil fold'da negatif. 2015–16 erken dönem
  tanılamasında V2a/V2b hafif pozitif, V2c negatif.

## 4. Uygulama kontrolleri (sonucu değiştirmez)

- Coverage yüksek (%99,87–99,93); geri dönüş sonucu belirlemiyor.
- Her fold'da ve her varyantta bütün λ'lar yakınsadı; seçim 1e-4 kuralıyla
  hep λ=100 (en küçük iç LL çoğunlukla λ=10'da, 1e-4 içinde eşit).
- gv60 hücrelerinin tamamı kendi WoE'sini aldı (yalnız hiç satırı olmayan
  "≥9999 × düşüş" hücreleri bant düzeyine düştü). Hücre WoE'leri beklenen
  yönde: aynı anlık bantta görüş düşüşü arttıkça WoE artıyor.
- Katsayılar fold'lar arasında tutarlı. `dspread_1sa` katsayısı birincil
  fold'larda negatif (−0,10 … −0,16); `spread_egilim_3`'ün son iki fold'daki
  negatif işareti V2'de de sürüyor. Bunlar kayıt olarak yazıldı; yorumlanmadı.
- Bir olası açıklama (hipotez, sınanmadı): gv60 anlık görüşü 4 banda
  indiriyor; V1'in `gorus` değişkeni ise veriden 10–11 kovaya bölünüyor. Anlık
  görüş çözünürlüğündeki bu kayıp, eğilimin getirdiği bilgiden büyük olabilir.
  Bu hipotez sonuç görüldükten sonra ortaya çıktığı için yeni bir aday
  üretmenin gerekçesi değildir (§7.3).

## 5. Sonuçlara bakılmadan sabitlenen uygulama ayrıntıları (commit `4483836`)

- **U1:** V2x lojistik fit'i, gerekli tam gecikmeleri bulunan eğitim
  satırlarında yapılır; WoE tablolarının H'si bütün E satırlarıdır.
- **U2:** V2x iç doğrulama havuzlanmış LL'si, ilgili bloğun V2x'in
  uygulanabildiği satırlarında hesaplanır.
- **U3:** "Gecikme eksik" = gereken zaman damgasında kayıt yok ya da gereken
  alan boş.
- **U4:** İlk alarm koruma şartı olay başına (V2 − V1) farkının medyanı
  üzerinden. Alternatif okuma tanılama olarak raporlandı ve aynı kararı verdi.

---

# Ek — betik çıktısı (tam tablolar, eğitim artefaktları dahil)


Evren: 273417 ızgara satırı, 272235 onset satırı. Çözücü: sönümlü Newton. Bootstrap: 2000 tekrar, tohum 0. Birincil karar: 5 dış fold havuzlanmış, geri dönüş dahil.

## 1. Birincil sonuç (§8) — beş dış fold havuzlanmış OOS

| model | λ (fold 1–5) | coverage_V2 % | LL (nat) | ΔLL = LL(V1)−LL(V2) | tek taraflı %98,33 alt sınır | AP | Brier×10⁴ | LSS | birincil kural |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V1 referansı | 100 / 100 / 100 / 100 / 100 | — | 0.027349 | — | — | 0.197 | 56.90 | 0.2892 |  |
| V2a | 100 / 100 / 100 / 100 / 100 | 99.93 | 0.027690 | -0.000340 | -0.000537 | 0.172 | 58.02 | 0.2804 | geçmedi |
| V2b | 100 / 100 / 100 / 100 / 100 | 99.93 | 0.027664 | -0.000315 | -0.000517 | 0.170 | 58.04 | 0.2811 | geçmedi |
| V2c | 100 / 100 / 100 / 100 / 100 | 99.87 | 0.027677 | -0.000328 | -0.000587 | 0.173 | 57.98 | 0.2807 | geçmedi |

LL/AP/Brier/LSS V2 satırlarında hibrit sistemin (geri dönüş dahil) değerleridir. LSS referansı her fold'un yalnız eğitim satırlarından kurulan ay × saat iklimi.

## 2. Koruma şartları (§9.1) — olay bootstrap'i

Bant eşiği = 5 × dondurulmuş V1 taban oranı = 3.785%. Olay: başlangıçtan önceki 3 saatteki onset satırlarından birinde tahmin ≥ eşik. İlk alarm süresi: ilk alarm → başlangıç (yakalanmayan olay 0 dk). Koruma: yakalama farkı (V2 − V1) %5 alt sınırı ≥ −5 puan; olay başına ilk alarm farkının (V2 − V1) medyanı için %5 alt sınır ≥ −30 dk (U4).

| varyant | olay | yakalama V1 % | yakalama V2 % | fark (puan) | fark %5 alt sınır | medyan ilk alarm V1 (dk) | medyan V2 (dk) | olay başına fark medyanı (dk) | %5 alt sınır (dk) | koruma | alt. okuma: medyanlar farkı %5 alt sınır (dk) | alt. okumayla karar |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V2a | 160 | 89.4 | 89.4 | +0.0 | -1.2 | 120 | 120 | +0 | +0 | geçti | +0 | aynı |
| V2b | 160 | 89.4 | 89.4 | +0.0 | -1.2 | 120 | 120 | +0 | +0 | geçti | -15 | aynı |
| V2c | 160 | 89.4 | 89.4 | +0.0 | -1.2 | 120 | 120 | +0 | +0 | geçti | +0 | aynı |

Son iki sütun yalnız tanılamadır: §9.1'in "medyan fark" ifadesinin diğer okuması (medyan(V2) − medyan(V1)). Karar U4'e göre verilir; iki okuma farklı sonuç verirse burada "FARKLI" yazar ve kullanıcıya getirilir.

## 3. Seçim (§8)

- V2a: birincil geçmedi, koruma geçti (ΔLL -0.000340).
- V2b: birincil geçmedi, koruma geçti (ΔLL -0.000315).
- V2c: birincil geçmedi, koruma geçti (ΔLL -0.000328).

**Hiçbir varyant geçmedi. Deney 1 kapanır** (§8).

## 4. Tanılamalar (karar vermez)

ΔLL = LL(V1) − LL(V2 hibrit); alt sınır tek taraflı %98,33 (karşılaştırılabilirlik için); medyan = bootstrap medyanı.

### 4.1 Yalnız V2'nin çalıştığı satırlar (§9.2)

| varyant | satır | Y=1 | ΔLL | tek taraflı %98,33 alt sınır | bootstrap medyanı |
|---|---:|---:|---:|---:|---:|
| V2a | 168315 | 1089 | -0.000341 | -0.000537 | -0.000337 |
| V2b | 168315 | 1089 | -0.000315 | -0.000518 | -0.000312 |
| V2c | 168204 | 1089 | -0.000328 | -0.000588 | -0.000325 |

### 4.2 Penceresinde SN olmayan satırlar (§9.3)

| varyant | satır | Y=1 | ΔLL | tek taraflı %98,33 alt sınır | bootstrap medyanı |
|---|---:|---:|---:|---:|---:|
| V2a | 165479 | 754 | -0.000373 | -0.000539 | -0.000370 |
| V2b | 165479 | 754 | -0.000380 | -0.000545 | -0.000377 |
| V2c | 165479 | 754 | -0.000371 | -0.000571 | -0.000367 |

### 4.3 Ufku tam (6/6) satırlar (Deney 0 §7.2)

| varyant | satır | Y=1 | ΔLL | tek taraflı %98,33 alt sınır | bootstrap medyanı |
|---|---:|---:|---:|---:|---:|
| V2a | 167900 | 1071 | -0.000324 | -0.000519 | -0.000320 |
| V2b | 167900 | 1071 | -0.000298 | -0.000503 | -0.000297 |
| V2c | 167900 | 1071 | -0.000312 | -0.000572 | -0.000311 |

### 4.4 Olay düzeyi SN tanılaması (§9.3) — yakalama

| varyant | olay grubu | olay | yakalama V1 % | yakalama V2 % |
|---|---:|---:|---:|---:|
| V2a | tümü | 160 | 89.4 | 89.4 |
| V2a | ≥ 1 SN | 42 | 76.2 | 73.8 |
| V2a | SN'siz | 118 | 94.1 | 94.9 |
| V2b | tümü | 160 | 89.4 | 89.4 |
| V2b | ≥ 1 SN | 42 | 76.2 | 73.8 |
| V2b | SN'siz | 118 | 94.1 | 94.9 |
| V2c | tümü | 160 | 89.4 | 89.4 |
| V2c | ≥ 1 SN | 42 | 76.2 | 73.8 |
| V2c | SN'siz | 118 | 94.1 | 94.9 |

### 4.5 Fold başına ΔLL ve 2015–16 erken dönem tanılaması

| varyant | fold | λ | coverage % | LL V1 | LL V2 hibrit | ΔLL |
|---|---:|---:|---:|---:|---:|---:|
| V2a | 2017–18 | 100 | 99.88 | 0.030553 | 0.031030 | -0.000477 |
| V2a | 2019–20 | 100 | 99.91 | 0.019694 | 0.020393 | -0.000699 |
| V2a | 2021–22 | 100 | 99.96 | 0.042546 | 0.042515 | +0.000031 |
| V2a | 2023–24 | 100 | 99.95 | 0.018565 | 0.018990 | -0.000425 |
| V2a | 2025–26 | 100 | 99.96 | 0.024927 | 0.025033 | -0.000107 |
| V2a | 2015–16 (tanılama) | 100 | 99.45 | 0.040069 | 0.039961 | +0.000108 |
| V2b | 2017–18 | 100 | 99.88 | 0.030553 | 0.031006 | -0.000453 |
| V2b | 2019–20 | 100 | 99.91 | 0.019694 | 0.020401 | -0.000708 |
| V2b | 2021–22 | 100 | 99.96 | 0.042546 | 0.042429 | +0.000117 |
| V2b | 2023–24 | 100 | 99.95 | 0.018565 | 0.018978 | -0.000413 |
| V2b | 2025–26 | 100 | 99.96 | 0.024927 | 0.025022 | -0.000096 |
| V2b | 2015–16 (tanılama) | 100 | 99.45 | 0.040069 | 0.039973 | +0.000096 |
| V2c | 2017–18 | 100 | 99.76 | 0.030553 | 0.031067 | -0.000514 |
| V2c | 2019–20 | 100 | 99.83 | 0.019694 | 0.020349 | -0.000656 |
| V2c | 2021–22 | 100 | 99.93 | 0.042546 | 0.042422 | +0.000124 |
| V2c | 2023–24 | 100 | 99.90 | 0.018565 | 0.019055 | -0.000490 |
| V2c | 2025–26 | 100 | 99.92 | 0.024927 | 0.025001 | -0.000074 |
| V2c | 2015–16 (tanılama) | 100 | 98.91 | 0.040069 | 0.040229 | -0.000160 |

## 5. Eğitim artefaktları (§7.5 — her fold'da hücre kaynakları)

### V2a — 2017–18

| λ | havuzlanmış iç LL (uygun satırlar) | en iyiden fark | eleme |
|---|---:|---:|---:|
| 0.1 | 0.037607 | 1.54e-04 |  |
| 1 | 0.037600 | 1.47e-04 |  |
| 10 | 0.037541 | 8.75e-05 |  |
| 100 | 0.037453 | 0.00e+00 |  |
| 1000 | 0.039503 | 2.05e-03 |  |
| 10000 | 0.048558 | 1.11e-02 |  |

1e-4 içinde eşit: {10, 100} → seçilen λ=100. Eğitim satırı 103800, V2 fit'ine giren (uygun) 103261.

| anlık bant | 60 dk eğilim | satır | Y=1 | olay | kaynak | WoE |
|---|---:|---:|---:|---:|---:|---:|
| 1000–3000 | iyilesen_sabit | 548 | 121 | 50 | hucre | 3.562 |
| 1000–3000 | 1_bant | 263 | 67 | 40 | bant | 3.736 |
| 1000–3000 | 2+_bant | 290 | 91 | 69 | bant | 3.736 |
| 3000–5000 | iyilesen_sabit | 1773 | 55 | 28 | hucre | 1.387 |
| 3000–5000 | 1_bant | 655 | 42 | 32 | hucre | 2.150 |
| 3000–5000 | 2+_bant | 352 | 30 | 24 | bant | 1.792 |
| 5000–9999 | iyilesen_sabit | 6548 | 92 | 45 | hucre | 0.574 |
| 5000–9999 | 1_bant | 1410 | 28 | 20 | hucre | 0.938 |
| 5000–9999 | 2+_bant | 1735 | 60 | 47 | hucre | 1.498 |
| ≥9999 | iyilesen_sabit | 89687 | 229 | 71 | hucre | -1.146 |
| ≥9999 | 1_bant | 0 | 0 | 0 | bant | -1.141 |
| ≥9999 | 2+_bant | 0 | 0 | 0 | bant | -1.141 |

Katsayılar (sabit, ruzgar_kuzey, saat, spread, spread_egilim_3, gv60): -4.759, 0.371, 0.445, 0.553, 0.019, 0.690

### V2a — 2019–20

| λ | havuzlanmış iç LL (uygun satırlar) | en iyiden fark | eleme |
|---|---:|---:|---:|
| 0.1 | 0.034797 | 2.67e-05 |  |
| 1 | 0.034794 | 2.35e-05 |  |
| 10 | 0.034770 | 0.00e+00 |  |
| 100 | 0.034822 | 5.18e-05 |  |
| 1000 | 0.036655 | 1.88e-03 |  |
| 10000 | 0.044791 | 1.00e-02 |  |

1e-4 içinde eşit: {0.1, 1, 10, 100} → seçilen λ=100. Eğitim satırı 138560, V2 fit'ine giren (uygun) 137979.

| anlık bant | 60 dk eğilim | satır | Y=1 | olay | kaynak | WoE |
|---|---:|---:|---:|---:|---:|---:|
| 1000–3000 | iyilesen_sabit | 821 | 186 | 68 | hucre | 3.598 |
| 1000–3000 | 1_bant | 390 | 94 | 54 | bant | 3.709 |
| 1000–3000 | 2+_bant | 385 | 113 | 86 | bant | 3.709 |
| 3000–5000 | iyilesen_sabit | 2723 | 78 | 38 | hucre | 1.306 |
| 3000–5000 | 1_bant | 909 | 51 | 39 | hucre | 2.010 |
| 3000–5000 | 2+_bant | 490 | 41 | 34 | bant | 1.686 |
| 5000–9999 | iyilesen_sabit | 9134 | 105 | 51 | hucre | 0.374 |
| 5000–9999 | 1_bant | 2032 | 37 | 26 | hucre | 0.849 |
| 5000–9999 | 2+_bant | 2291 | 74 | 60 | hucre | 1.430 |
| ≥9999 | iyilesen_sabit | 118804 | 308 | 92 | hucre | -1.127 |
| ≥9999 | 1_bant | 0 | 0 | 0 | bant | -1.124 |
| ≥9999 | 2+_bant | 0 | 0 | 0 | bant | -1.124 |

Katsayılar (sabit, ruzgar_kuzey, saat, spread, spread_egilim_3, gv60): -4.800, 0.446, 0.479, 0.544, 0.031, 0.699

### V2a — 2021–22

| λ | havuzlanmış iç LL (uygun satırlar) | en iyiden fark | eleme |
|---|---:|---:|---:|
| 0.1 | 0.030670 | 1.60e-05 |  |
| 1 | 0.030668 | 1.40e-05 |  |
| 10 | 0.030654 | 0.00e+00 |  |
| 100 | 0.030723 | 6.87e-05 |  |
| 1000 | 0.032325 | 1.67e-03 |  |
| 10000 | 0.039547 | 8.89e-03 |  |

1e-4 içinde eşit: {0.1, 1, 10, 100} → seçilen λ=100. Eğitim satırı 172570, V2 fit'ine giren (uygun) 171959.

| anlık bant | 60 dk eğilim | satır | Y=1 | olay | kaynak | WoE |
|---|---:|---:|---:|---:|---:|---:|
| 1000–3000 | iyilesen_sabit | 981 | 203 | 75 | hucre | 3.562 |
| 1000–3000 | 1_bant | 460 | 113 | 65 | bant | 3.749 |
| 1000–3000 | 2+_bant | 451 | 136 | 101 | bant | 3.749 |
| 3000–5000 | iyilesen_sabit | 3355 | 118 | 53 | hucre | 1.596 |
| 3000–5000 | 1_bant | 1130 | 60 | 45 | hucre | 2.030 |
| 3000–5000 | 2+_bant | 599 | 46 | 38 | hucre | 2.427 |
| 5000–9999 | iyilesen_sabit | 10954 | 109 | 54 | hucre | 0.308 |
| 5000–9999 | 1_bant | 2638 | 39 | 28 | hucre | 0.717 |
| 5000–9999 | 2+_bant | 2692 | 82 | 67 | hucre | 1.449 |
| ≥9999 | iyilesen_sabit | 148699 | 347 | 104 | hucre | -1.153 |
| ≥9999 | 1_bant | 0 | 0 | 0 | bant | -1.150 |
| ≥9999 | 2+_bant | 0 | 0 | 0 | bant | -1.150 |

Katsayılar (sabit, ruzgar_kuzey, saat, spread, spread_egilim_3, gv60): -4.884, 0.453, 0.463, 0.531, 0.024, 0.677

### V2a — 2023–24

| λ | havuzlanmış iç LL (uygun satırlar) | en iyiden fark | eleme |
|---|---:|---:|---:|
| 0.1 | 0.033376 | 1.82e-05 |  |
| 1 | 0.033374 | 1.61e-05 |  |
| 10 | 0.033358 | 0.00e+00 |  |
| 100 | 0.033373 | 1.54e-05 |  |
| 1000 | 0.034577 | 1.22e-03 |  |
| 10000 | 0.041376 | 8.02e-03 |  |

1e-4 içinde eşit: {0.1, 1, 10, 100} → seçilen λ=100. Eğitim satırı 207356, V2 fit'ine giren (uygun) 206732.

| anlık bant | 60 dk eğilim | satır | Y=1 | olay | kaynak | WoE |
|---|---:|---:|---:|---:|---:|---:|
| 1000–3000 | iyilesen_sabit | 1135 | 243 | 90 | hucre | 3.536 |
| 1000–3000 | 1_bant | 530 | 134 | 78 | hucre | 3.754 |
| 1000–3000 | 2+_bant | 547 | 170 | 127 | hucre | 4.040 |
| 3000–5000 | iyilesen_sabit | 3736 | 141 | 67 | hucre | 1.600 |
| 3000–5000 | 1_bant | 1286 | 78 | 59 | hucre | 2.101 |
| 3000–5000 | 2+_bant | 752 | 70 | 59 | hucre | 2.565 |
| 5000–9999 | iyilesen_sabit | 12630 | 161 | 75 | hucre | 0.488 |
| 5000–9999 | 1_bant | 3145 | 48 | 35 | hucre | 0.678 |
| 5000–9999 | 2+_bant | 3166 | 108 | 89 | hucre | 1.496 |
| ≥9999 | iyilesen_sabit | 179805 | 464 | 137 | hucre | -1.121 |
| ≥9999 | 1_bant | 0 | 0 | 0 | bant | -1.119 |
| ≥9999 | 2+_bant | 0 | 0 | 0 | bant | -1.119 |

Katsayılar (sabit, ruzgar_kuzey, saat, spread, spread_egilim_3, gv60): -4.830, 0.470, 0.422, 0.585, -0.101, 0.677

### V2a — 2025–26

| λ | havuzlanmış iç LL (uygun satırlar) | en iyiden fark | eleme |
|---|---:|---:|---:|
| 0.1 | 0.030728 | 1.55e-05 |  |
| 1 | 0.030726 | 1.37e-05 |  |
| 10 | 0.030712 | 0.00e+00 |  |
| 100 | 0.030723 | 1.06e-05 |  |
| 1000 | 0.031747 | 1.03e-03 |  |
| 10000 | 0.037729 | 7.02e-03 |  |

1e-4 içinde eşit: {0.1, 1, 10, 100} → seçilen λ=100. Eğitim satırı 242320, V2 fit'ine giren (uygun) 241679.

| anlık bant | 60 dk eğilim | satır | Y=1 | olay | kaynak | WoE |
|---|---:|---:|---:|---:|---:|---:|
| 1000–3000 | iyilesen_sabit | 1219 | 251 | 95 | hucre | 3.566 |
| 1000–3000 | 1_bant | 579 | 139 | 81 | hucre | 3.764 |
| 1000–3000 | 2+_bant | 598 | 180 | 134 | hucre | 4.073 |
| 3000–5000 | iyilesen_sabit | 4119 | 160 | 75 | hucre | 1.709 |
| 3000–5000 | 1_bant | 1427 | 86 | 65 | hucre | 2.173 |
| 3000–5000 | 2+_bant | 894 | 75 | 64 | hucre | 2.530 |
| 5000–9999 | iyilesen_sabit | 13896 | 174 | 82 | hucre | 0.549 |
| 5000–9999 | 1_bant | 3583 | 56 | 43 | hucre | 0.780 |
| 5000–9999 | 2+_bant | 3590 | 120 | 99 | hucre | 1.554 |
| ≥9999 | iyilesen_sabit | 211774 | 507 | 148 | hucre | -1.117 |
| ≥9999 | 1_bant | 0 | 0 | 0 | bant | -1.115 |
| ≥9999 | 2+_bant | 0 | 0 | 0 | bant | -1.115 |

Katsayılar (sabit, ruzgar_kuzey, saat, spread, spread_egilim_3, gv60): -4.912, 0.470, 0.427, 0.582, -0.091, 0.682

### V2a — 2015–16

| λ | havuzlanmış iç LL (uygun satırlar) | en iyiden fark | eleme |
|---|---:|---:|---:|
| 0.1 | 0.034400 | 4.35e-04 |  |
| 1 | 0.034384 | 4.19e-04 |  |
| 10 | 0.034260 | 2.95e-04 |  |
| 100 | 0.033965 | 0.00e+00 |  |
| 1000 | 0.035777 | 1.81e-03 |  |
| 10000 | 0.043333 | 9.37e-03 |  |

1e-4 içinde eşit: {100} → seçilen λ=100. Eğitim satırı 69185, V2 fit'ine giren (uygun) 68837.

| anlık bant | 60 dk eğilim | satır | Y=1 | olay | kaynak | WoE |
|---|---:|---:|---:|---:|---:|---:|
| 1000–3000 | iyilesen_sabit | 317 | 53 | 29 | bant | 3.706 |
| 1000–3000 | 1_bant | 177 | 40 | 25 | bant | 3.706 |
| 1000–3000 | 2+_bant | 170 | 50 | 37 | bant | 3.706 |
| 3000–5000 | iyilesen_sabit | 1289 | 40 | 21 | hucre | 1.556 |
| 3000–5000 | 1_bant | 461 | 29 | 20 | bant | 1.949 |
| 3000–5000 | 2+_bant | 243 | 22 | 18 | bant | 1.949 |
| 5000–9999 | iyilesen_sabit | 4895 | 53 | 25 | hucre | 0.480 |
| 5000–9999 | 1_bant | 986 | 21 | 14 | hucre | 1.181 |
| 5000–9999 | 2+_bant | 1243 | 31 | 24 | hucre | 1.335 |
| ≥9999 | iyilesen_sabit | 59056 | 123 | 38 | hucre | -1.183 |
| ≥9999 | 1_bant | 0 | 0 | 0 | bant | -1.179 |
| ≥9999 | 2+_bant | 0 | 0 | 0 | bant | -1.179 |

Katsayılar (sabit, ruzgar_kuzey, saat, spread, spread_egilim_3, gv60): -4.876, 0.329, 0.376, 0.537, 0.110, 0.648

### V2b — 2017–18

| λ | havuzlanmış iç LL (uygun satırlar) | en iyiden fark | eleme |
|---|---:|---:|---:|
| 0.1 | 0.037597 | 1.43e-04 |  |
| 1 | 0.037590 | 1.36e-04 |  |
| 10 | 0.037531 | 7.72e-05 |  |
| 100 | 0.037454 | 0.00e+00 |  |
| 1000 | 0.039511 | 2.06e-03 |  |
| 10000 | 0.048552 | 1.11e-02 |  |

1e-4 içinde eşit: {10, 100} → seçilen λ=100. Eğitim satırı 103800, V2 fit'ine giren (uygun) 103261.

| anlık bant | 60 dk eğilim | satır | Y=1 | olay | kaynak | WoE |
|---|---:|---:|---:|---:|---:|---:|
| 1000–3000 | iyilesen_sabit | 548 | 121 | 50 | hucre | 3.562 |
| 1000–3000 | 1_bant | 263 | 67 | 40 | bant | 3.736 |
| 1000–3000 | 2+_bant | 290 | 91 | 69 | bant | 3.736 |
| 3000–5000 | iyilesen_sabit | 1773 | 55 | 28 | hucre | 1.387 |
| 3000–5000 | 1_bant | 655 | 42 | 32 | hucre | 2.150 |
| 3000–5000 | 2+_bant | 352 | 30 | 24 | bant | 1.792 |
| 5000–9999 | iyilesen_sabit | 6548 | 92 | 45 | hucre | 0.574 |
| 5000–9999 | 1_bant | 1410 | 28 | 20 | hucre | 0.938 |
| 5000–9999 | 2+_bant | 1735 | 60 | 47 | hucre | 1.498 |
| ≥9999 | iyilesen_sabit | 89687 | 229 | 71 | hucre | -1.146 |
| ≥9999 | 1_bant | 0 | 0 | 0 | bant | -1.141 |
| ≥9999 | 2+_bant | 0 | 0 | 0 | bant | -1.141 |

`dspread_1sa`: <=-2: n=11891, Y=1=51, olay=30, WoE=-0.614; -1: n=21856, Y=1=223, olay=110, WoE=0.251; 0: n=37338, Y=1=425, olay=125, WoE=0.361; +1: n=19279, Y=1=100, olay=68, WoE=-0.428; >=+2: n=12897, Y=1=16, olay=13, WoE=-1.836

Katsayılar (sabit, ruzgar_kuzey, saat, spread, spread_egilim_3, gv60, dspread_1sa): -4.758, 0.372, 0.446, 0.561, 0.037, 0.689, -0.100

### V2b — 2019–20

| λ | havuzlanmış iç LL (uygun satırlar) | en iyiden fark | eleme |
|---|---:|---:|---:|
| 0.1 | 0.034774 | 2.53e-05 |  |
| 1 | 0.034771 | 2.22e-05 |  |
| 10 | 0.034749 | 0.00e+00 |  |
| 100 | 0.034814 | 6.54e-05 |  |
| 1000 | 0.036661 | 1.91e-03 |  |
| 10000 | 0.044782 | 1.00e-02 |  |

1e-4 içinde eşit: {0.1, 1, 10, 100} → seçilen λ=100. Eğitim satırı 138560, V2 fit'ine giren (uygun) 137979.

| anlık bant | 60 dk eğilim | satır | Y=1 | olay | kaynak | WoE |
|---|---:|---:|---:|---:|---:|---:|
| 1000–3000 | iyilesen_sabit | 821 | 186 | 68 | hucre | 3.598 |
| 1000–3000 | 1_bant | 390 | 94 | 54 | bant | 3.709 |
| 1000–3000 | 2+_bant | 385 | 113 | 86 | bant | 3.709 |
| 3000–5000 | iyilesen_sabit | 2723 | 78 | 38 | hucre | 1.306 |
| 3000–5000 | 1_bant | 909 | 51 | 39 | hucre | 2.010 |
| 3000–5000 | 2+_bant | 490 | 41 | 34 | bant | 1.686 |
| 5000–9999 | iyilesen_sabit | 9134 | 105 | 51 | hucre | 0.374 |
| 5000–9999 | 1_bant | 2032 | 37 | 26 | hucre | 0.849 |
| 5000–9999 | 2+_bant | 2291 | 74 | 60 | hucre | 1.430 |
| ≥9999 | iyilesen_sabit | 118804 | 308 | 92 | hucre | -1.127 |
| ≥9999 | 1_bant | 0 | 0 | 0 | bant | -1.124 |
| ≥9999 | 2+_bant | 0 | 0 | 0 | bant | -1.124 |

`dspread_1sa`: <=-2: n=15468, Y=1=63, olay=38, WoE=-0.665; -1: n=29237, Y=1=298, olay=145, WoE=0.252; 0: n=50565, Y=1=570, olay=164, WoE=0.354; +1: n=25897, Y=1=140, olay=94, WoE=-0.385; >=+2: n=16812, Y=1=16, olay=13, WoE=-2.099

Katsayılar (sabit, ruzgar_kuzey, saat, spread, spread_egilim_3, gv60, dspread_1sa): -4.799, 0.447, 0.482, 0.555, 0.056, 0.698, -0.131

### V2b — 2021–22

| λ | havuzlanmış iç LL (uygun satırlar) | en iyiden fark | eleme |
|---|---:|---:|---:|
| 0.1 | 0.030660 | 1.59e-05 |  |
| 1 | 0.030658 | 1.38e-05 |  |
| 10 | 0.030645 | 0.00e+00 |  |
| 100 | 0.030720 | 7.50e-05 |  |
| 1000 | 0.032329 | 1.68e-03 |  |
| 10000 | 0.039537 | 8.89e-03 |  |

1e-4 içinde eşit: {0.1, 1, 10, 100} → seçilen λ=100. Eğitim satırı 172570, V2 fit'ine giren (uygun) 171959.

| anlık bant | 60 dk eğilim | satır | Y=1 | olay | kaynak | WoE |
|---|---:|---:|---:|---:|---:|---:|
| 1000–3000 | iyilesen_sabit | 981 | 203 | 75 | hucre | 3.562 |
| 1000–3000 | 1_bant | 460 | 113 | 65 | bant | 3.749 |
| 1000–3000 | 2+_bant | 451 | 136 | 101 | bant | 3.749 |
| 3000–5000 | iyilesen_sabit | 3355 | 118 | 53 | hucre | 1.596 |
| 3000–5000 | 1_bant | 1130 | 60 | 45 | hucre | 2.030 |
| 3000–5000 | 2+_bant | 599 | 46 | 38 | hucre | 2.427 |
| 5000–9999 | iyilesen_sabit | 10954 | 109 | 54 | hucre | 0.308 |
| 5000–9999 | 1_bant | 2638 | 39 | 28 | hucre | 0.717 |
| 5000–9999 | 2+_bant | 2692 | 82 | 67 | hucre | 1.449 |
| ≥9999 | iyilesen_sabit | 148699 | 347 | 104 | hucre | -1.153 |
| ≥9999 | 1_bant | 0 | 0 | 0 | bant | -1.150 |
| ≥9999 | 2+_bant | 0 | 0 | 0 | bant | -1.150 |

`dspread_1sa`: <=-2: n=19147, Y=1=71, olay=42, WoE=-0.680; -1: n=36450, Y=1=342, olay=167, WoE=0.248; 0: n=63250, Y=1=667, olay=190, WoE=0.366; +1: n=32244, Y=1=157, olay=106, WoE=-0.410; >=+2: n=20868, Y=1=16, olay=13, WoE=-2.235

Katsayılar (sabit, ruzgar_kuzey, saat, spread, spread_egilim_3, gv60, dspread_1sa): -4.883, 0.454, 0.464, 0.539, 0.048, 0.676, -0.114

### V2b — 2023–24

| λ | havuzlanmış iç LL (uygun satırlar) | en iyiden fark | eleme |
|---|---:|---:|---:|
| 0.1 | 0.033345 | 1.77e-05 |  |
| 1 | 0.033343 | 1.56e-05 |  |
| 10 | 0.033328 | 0.00e+00 |  |
| 100 | 0.033353 | 2.51e-05 |  |
| 1000 | 0.034581 | 1.25e-03 |  |
| 10000 | 0.041369 | 8.04e-03 |  |

1e-4 içinde eşit: {0.1, 1, 10, 100} → seçilen λ=100. Eğitim satırı 207356, V2 fit'ine giren (uygun) 206732.

| anlık bant | 60 dk eğilim | satır | Y=1 | olay | kaynak | WoE |
|---|---:|---:|---:|---:|---:|---:|
| 1000–3000 | iyilesen_sabit | 1135 | 243 | 90 | hucre | 3.536 |
| 1000–3000 | 1_bant | 530 | 134 | 78 | hucre | 3.754 |
| 1000–3000 | 2+_bant | 547 | 170 | 127 | hucre | 4.040 |
| 3000–5000 | iyilesen_sabit | 3736 | 141 | 67 | hucre | 1.600 |
| 3000–5000 | 1_bant | 1286 | 78 | 59 | hucre | 2.101 |
| 3000–5000 | 2+_bant | 752 | 70 | 59 | hucre | 2.565 |
| 5000–9999 | iyilesen_sabit | 12630 | 161 | 75 | hucre | 0.488 |
| 5000–9999 | 1_bant | 3145 | 48 | 35 | hucre | 0.678 |
| 5000–9999 | 2+_bant | 3166 | 108 | 89 | hucre | 1.496 |
| ≥9999 | iyilesen_sabit | 179805 | 464 | 137 | hucre | -1.121 |
| ≥9999 | 1_bant | 0 | 0 | 0 | bant | -1.119 |
| ≥9999 | 2+_bant | 0 | 0 | 0 | bant | -1.119 |

`dspread_1sa`: <=-2: n=22983, Y=1=98, olay=57, WoE=-0.611; -1: n=43764, Y=1=407, olay=201, WoE=0.170; 0: n=76113, Y=1=884, olay=239, WoE=0.394; +1: n=38799, Y=1=189, olay=126, WoE=-0.480; >=+2: n=25073, Y=1=39, olay=25, WoE=-1.615

Katsayılar (sabit, ruzgar_kuzey, saat, spread, spread_egilim_3, gv60, dspread_1sa): -4.830, 0.470, 0.425, 0.597, -0.066, 0.676, -0.155

### V2b — 2025–26

| λ | havuzlanmış iç LL (uygun satırlar) | en iyiden fark | eleme |
|---|---:|---:|---:|
| 0.1 | 0.030700 | 1.50e-05 |  |
| 1 | 0.030698 | 1.32e-05 |  |
| 10 | 0.030685 | 0.00e+00 |  |
| 100 | 0.030704 | 1.92e-05 |  |
| 1000 | 0.031750 | 1.07e-03 |  |
| 10000 | 0.037722 | 7.04e-03 |  |

1e-4 içinde eşit: {0.1, 1, 10, 100} → seçilen λ=100. Eğitim satırı 242320, V2 fit'ine giren (uygun) 241679.

| anlık bant | 60 dk eğilim | satır | Y=1 | olay | kaynak | WoE |
|---|---:|---:|---:|---:|---:|---:|
| 1000–3000 | iyilesen_sabit | 1219 | 251 | 95 | hucre | 3.566 |
| 1000–3000 | 1_bant | 579 | 139 | 81 | hucre | 3.764 |
| 1000–3000 | 2+_bant | 598 | 180 | 134 | hucre | 4.073 |
| 3000–5000 | iyilesen_sabit | 4119 | 160 | 75 | hucre | 1.709 |
| 3000–5000 | 1_bant | 1427 | 86 | 65 | hucre | 2.173 |
| 3000–5000 | 2+_bant | 894 | 75 | 64 | hucre | 2.530 |
| 5000–9999 | iyilesen_sabit | 13896 | 174 | 82 | hucre | 0.549 |
| 5000–9999 | 1_bant | 3583 | 56 | 43 | hucre | 0.780 |
| 5000–9999 | 2+_bant | 3590 | 120 | 99 | hucre | 1.554 |
| ≥9999 | iyilesen_sabit | 211774 | 507 | 148 | hucre | -1.117 |
| ≥9999 | 1_bant | 0 | 0 | 0 | bant | -1.115 |
| ≥9999 | 2+_bant | 0 | 0 | 0 | bant | -1.115 |

`dspread_1sa`: <=-2: n=26747, Y=1=101, olay=60, WoE=-0.654; -1: n=51096, Y=1=435, olay=213, WoE=0.160; 0: n=89332, Y=1=967, olay=257, WoE=0.402; +1: n=45228, Y=1=203, olay=136, WoE=-0.483; >=+2: n=29276, Y=1=42, olay=27, WoE=-1.617

Katsayılar (sabit, ruzgar_kuzey, saat, spread, spread_egilim_3, gv60, dspread_1sa): -4.912, 0.470, 0.429, 0.595, -0.055, 0.680, -0.159

### V2b — 2015–16

| λ | havuzlanmış iç LL (uygun satırlar) | en iyiden fark | eleme |
|---|---:|---:|---:|
| 0.1 | 0.034401 | 4.31e-04 |  |
| 1 | 0.034385 | 4.16e-04 |  |
| 10 | 0.034262 | 2.92e-04 |  |
| 100 | 0.033970 | 0.00e+00 |  |
| 1000 | 0.035777 | 1.81e-03 |  |
| 10000 | 0.043327 | 9.36e-03 |  |

1e-4 içinde eşit: {100} → seçilen λ=100. Eğitim satırı 69185, V2 fit'ine giren (uygun) 68837.

| anlık bant | 60 dk eğilim | satır | Y=1 | olay | kaynak | WoE |
|---|---:|---:|---:|---:|---:|---:|
| 1000–3000 | iyilesen_sabit | 317 | 53 | 29 | bant | 3.706 |
| 1000–3000 | 1_bant | 177 | 40 | 25 | bant | 3.706 |
| 1000–3000 | 2+_bant | 170 | 50 | 37 | bant | 3.706 |
| 3000–5000 | iyilesen_sabit | 1289 | 40 | 21 | hucre | 1.556 |
| 3000–5000 | 1_bant | 461 | 29 | 20 | bant | 1.949 |
| 3000–5000 | 2+_bant | 243 | 22 | 18 | bant | 1.949 |
| 5000–9999 | iyilesen_sabit | 4895 | 53 | 25 | hucre | 0.480 |
| 5000–9999 | 1_bant | 986 | 21 | 14 | hucre | 1.181 |
| 5000–9999 | 2+_bant | 1243 | 31 | 24 | hucre | 1.335 |
| ≥9999 | iyilesen_sabit | 59056 | 123 | 38 | hucre | -1.183 |
| ≥9999 | 1_bant | 0 | 0 | 0 | bant | -1.179 |
| ≥9999 | 2+_bant | 0 | 0 | 0 | bant | -1.179 |

`dspread_1sa`: <=-2: n=8271, Y=1=24, olay=13, WoE=-0.826; -1: n=14475, Y=1=134, olay=64, WoE=0.323; 0: n=24499, Y=1=251, olay=70, WoE=0.424; +1: n=12697, Y=1=49, olay=34, WoE=-0.551; >=+2: n=8895, Y=1=4, olay=4, WoE=0.000

Katsayılar (sabit, ruzgar_kuzey, saat, spread, spread_egilim_3, gv60, dspread_1sa): -4.879, 0.328, 0.375, 0.536, 0.108, 0.648, 0.024

### V2c — 2017–18

| λ | havuzlanmış iç LL (uygun satırlar) | en iyiden fark | eleme |
|---|---:|---:|---:|
| 0.1 | 0.037518 | 1.16e-04 |  |
| 1 | 0.037511 | 1.09e-04 |  |
| 10 | 0.037458 | 5.58e-05 |  |
| 100 | 0.037402 | 0.00e+00 |  |
| 1000 | 0.039192 | 1.79e-03 |  |
| 10000 | 0.047909 | 1.05e-02 |  |

1e-4 içinde eşit: {10, 100} → seçilen λ=100. Eğitim satırı 103800, V2 fit'ine giren (uygun) 102728.

| anlık bant | 60 dk eğilim | satır | Y=1 | olay | kaynak | WoE |
|---|---:|---:|---:|---:|---:|---:|
| 1000–3000 | iyilesen_sabit | 548 | 121 | 50 | hucre | 3.562 |
| 1000–3000 | 1_bant | 263 | 67 | 40 | bant | 3.736 |
| 1000–3000 | 2+_bant | 290 | 91 | 69 | bant | 3.736 |
| 3000–5000 | iyilesen_sabit | 1773 | 55 | 28 | hucre | 1.387 |
| 3000–5000 | 1_bant | 655 | 42 | 32 | hucre | 2.150 |
| 3000–5000 | 2+_bant | 352 | 30 | 24 | bant | 1.792 |
| 5000–9999 | iyilesen_sabit | 6548 | 92 | 45 | hucre | 0.574 |
| 5000–9999 | 1_bant | 1410 | 28 | 20 | hucre | 0.938 |
| 5000–9999 | 2+_bant | 1735 | 60 | 47 | hucre | 1.498 |
| ≥9999 | iyilesen_sabit | 89687 | 229 | 71 | hucre | -1.146 |
| ≥9999 | 1_bant | 0 | 0 | 0 | bant | -1.141 |
| ≥9999 | 2+_bant | 0 | 0 | 0 | bant | -1.141 |

`dspread_1sa`: <=-2: n=11891, Y=1=51, olay=30, WoE=-0.614; -1: n=21856, Y=1=223, olay=110, WoE=0.251; 0: n=37338, Y=1=425, olay=125, WoE=0.361; +1: n=19279, Y=1=100, olay=68, WoE=-0.428; >=+2: n=12897, Y=1=16, olay=13, WoE=-1.836

`egilim120`: iyilesen_sabit: n=96332, Y=1=412, olay=118, WoE=-0.624; 1_bant: n=2619, Y=1=115, olay=58, WoE=1.748; 2+_bant: n=3777, Y=1=281, olay=104, WoE=2.306

Katsayılar (sabit, ruzgar_kuzey, saat, spread, spread_egilim_3, gv60, dspread_1sa, egilim120): -4.765, 0.365, 0.444, 0.566, 0.030, 0.635, -0.106, 0.122

### V2c — 2019–20

| λ | havuzlanmış iç LL (uygun satırlar) | en iyiden fark | eleme |
|---|---:|---:|---:|
| 0.1 | 0.034741 | 2.10e-05 |  |
| 1 | 0.034738 | 1.83e-05 |  |
| 10 | 0.034720 | 0.00e+00 |  |
| 100 | 0.034804 | 8.39e-05 |  |
| 1000 | 0.036487 | 1.77e-03 |  |
| 10000 | 0.044254 | 9.53e-03 |  |

1e-4 içinde eşit: {0.1, 1, 10, 100} → seçilen λ=100. Eğitim satırı 138560, V2 fit'ine giren (uygun) 137405.

| anlık bant | 60 dk eğilim | satır | Y=1 | olay | kaynak | WoE |
|---|---:|---:|---:|---:|---:|---:|
| 1000–3000 | iyilesen_sabit | 821 | 186 | 68 | hucre | 3.598 |
| 1000–3000 | 1_bant | 390 | 94 | 54 | bant | 3.709 |
| 1000–3000 | 2+_bant | 385 | 113 | 86 | bant | 3.709 |
| 3000–5000 | iyilesen_sabit | 2723 | 78 | 38 | hucre | 1.306 |
| 3000–5000 | 1_bant | 909 | 51 | 39 | hucre | 2.010 |
| 3000–5000 | 2+_bant | 490 | 41 | 34 | bant | 1.686 |
| 5000–9999 | iyilesen_sabit | 9134 | 105 | 51 | hucre | 0.374 |
| 5000–9999 | 1_bant | 2032 | 37 | 26 | hucre | 0.849 |
| 5000–9999 | 2+_bant | 2291 | 74 | 60 | hucre | 1.430 |
| ≥9999 | iyilesen_sabit | 118804 | 308 | 92 | hucre | -1.127 |
| ≥9999 | 1_bant | 0 | 0 | 0 | bant | -1.124 |
| ≥9999 | 2+_bant | 0 | 0 | 0 | bant | -1.124 |

`dspread_1sa`: <=-2: n=15468, Y=1=63, olay=38, WoE=-0.665; -1: n=29237, Y=1=298, olay=145, WoE=0.252; 0: n=50565, Y=1=570, olay=164, WoE=0.354; +1: n=25897, Y=1=140, olay=94, WoE=-0.385; >=+2: n=16812, Y=1=16, olay=13, WoE=-2.099

`egilim120`: iyilesen_sabit: n=128540, Y=1=559, olay=150, WoE=-0.605; 1_bant: n=3787, Y=1=154, olay=79, WoE=1.670; 2+_bant: n=5078, Y=1=367, olay=137, WoE=2.277

Katsayılar (sabit, ruzgar_kuzey, saat, spread, spread_egilim_3, gv60, dspread_1sa, egilim120): -4.805, 0.443, 0.479, 0.559, 0.050, 0.655, -0.135, 0.103

### V2c — 2021–22

| λ | havuzlanmış iç LL (uygun satırlar) | en iyiden fark | eleme |
|---|---:|---:|---:|
| 0.1 | 0.030624 | 1.33e-05 |  |
| 1 | 0.030622 | 1.15e-05 |  |
| 10 | 0.030610 | 0.00e+00 |  |
| 100 | 0.030695 | 8.48e-05 |  |
| 1000 | 0.032164 | 1.55e-03 |  |
| 10000 | 0.039043 | 8.43e-03 |  |

1e-4 içinde eşit: {0.1, 1, 10, 100} → seçilen λ=100. Eğitim satırı 172570, V2 fit'ine giren (uygun) 171356.

| anlık bant | 60 dk eğilim | satır | Y=1 | olay | kaynak | WoE |
|---|---:|---:|---:|---:|---:|---:|
| 1000–3000 | iyilesen_sabit | 981 | 203 | 75 | hucre | 3.562 |
| 1000–3000 | 1_bant | 460 | 113 | 65 | bant | 3.749 |
| 1000–3000 | 2+_bant | 451 | 136 | 101 | bant | 3.749 |
| 3000–5000 | iyilesen_sabit | 3355 | 118 | 53 | hucre | 1.596 |
| 3000–5000 | 1_bant | 1130 | 60 | 45 | hucre | 2.030 |
| 3000–5000 | 2+_bant | 599 | 46 | 38 | hucre | 2.427 |
| 5000–9999 | iyilesen_sabit | 10954 | 109 | 54 | hucre | 0.308 |
| 5000–9999 | 1_bant | 2638 | 39 | 28 | hucre | 0.717 |
| 5000–9999 | 2+_bant | 2692 | 82 | 67 | hucre | 1.449 |
| ≥9999 | iyilesen_sabit | 148699 | 347 | 104 | hucre | -1.153 |
| ≥9999 | 1_bant | 0 | 0 | 0 | bant | -1.150 |
| ≥9999 | 2+_bant | 0 | 0 | 0 | bant | -1.150 |

`dspread_1sa`: <=-2: n=19147, Y=1=71, olay=42, WoE=-0.680; -1: n=36450, Y=1=342, olay=167, WoE=0.248; 0: n=63250, Y=1=667, olay=190, WoE=0.366; +1: n=32244, Y=1=157, olay=106, WoE=-0.410; >=+2: n=20868, Y=1=16, olay=13, WoE=-2.235

`egilim120`: iyilesen_sabit: n=160459, Y=1=629, olay=173, WoE=-0.630; 1_bant: n=4831, Y=1=189, olay=93, WoE=1.709; 2+_bant: n=6066, Y=1=428, olay=157, WoE=2.330

Katsayılar (sabit, ruzgar_kuzey, saat, spread, spread_egilim_3, gv60, dspread_1sa, egilim120): -4.892, 0.449, 0.459, 0.549, 0.036, 0.623, -0.116, 0.120

### V2c — 2023–24

| λ | havuzlanmış iç LL (uygun satırlar) | en iyiden fark | eleme |
|---|---:|---:|---:|
| 0.1 | 0.033325 | 1.58e-05 |  |
| 1 | 0.033323 | 1.39e-05 |  |
| 10 | 0.033309 | 0.00e+00 |  |
| 100 | 0.033341 | 3.20e-05 |  |
| 1000 | 0.034449 | 1.14e-03 |  |
| 10000 | 0.040866 | 7.56e-03 |  |

1e-4 içinde eşit: {0.1, 1, 10, 100} → seçilen λ=100. Eğitim satırı 207356, V2 fit'ine giren (uygun) 206116.

| anlık bant | 60 dk eğilim | satır | Y=1 | olay | kaynak | WoE |
|---|---:|---:|---:|---:|---:|---:|
| 1000–3000 | iyilesen_sabit | 1135 | 243 | 90 | hucre | 3.536 |
| 1000–3000 | 1_bant | 530 | 134 | 78 | hucre | 3.754 |
| 1000–3000 | 2+_bant | 547 | 170 | 127 | hucre | 4.040 |
| 3000–5000 | iyilesen_sabit | 3736 | 141 | 67 | hucre | 1.600 |
| 3000–5000 | 1_bant | 1286 | 78 | 59 | hucre | 2.101 |
| 3000–5000 | 2+_bant | 752 | 70 | 59 | hucre | 2.565 |
| 5000–9999 | iyilesen_sabit | 12630 | 161 | 75 | hucre | 0.488 |
| 5000–9999 | 1_bant | 3145 | 48 | 35 | hucre | 0.678 |
| 5000–9999 | 2+_bant | 3166 | 108 | 89 | hucre | 1.496 |
| ≥9999 | iyilesen_sabit | 179805 | 464 | 137 | hucre | -1.121 |
| ≥9999 | 1_bant | 0 | 0 | 0 | bant | -1.119 |
| ≥9999 | 2+_bant | 0 | 0 | 0 | bant | -1.119 |

`dspread_1sa`: <=-2: n=22983, Y=1=98, olay=57, WoE=-0.611; -1: n=43764, Y=1=407, olay=201, WoE=0.170; 0: n=76113, Y=1=884, olay=239, WoE=0.394; +1: n=38799, Y=1=189, olay=126, WoE=-0.480; >=+2: n=25073, Y=1=39, olay=25, WoE=-1.615

`egilim120`: iyilesen_sabit: n=193219, Y=1=828, olay=219, WoE=-0.610; 1_bant: n=5676, Y=1=229, olay=114, WoE=1.671; 2+_bant: n=7221, Y=1=553, olay=200, WoE=2.349

Katsayılar (sabit, ruzgar_kuzey, saat, spread, spread_egilim_3, gv60, dspread_1sa, egilim120): -4.835, 0.464, 0.418, 0.602, -0.068, 0.631, -0.155, 0.101

### V2c — 2025–26

| λ | havuzlanmış iç LL (uygun satırlar) | en iyiden fark | eleme |
|---|---:|---:|---:|
| 0.1 | 0.030695 | 1.33e-05 |  |
| 1 | 0.030693 | 1.17e-05 |  |
| 10 | 0.030682 | 0.00e+00 |  |
| 100 | 0.030707 | 2.56e-05 |  |
| 1000 | 0.031653 | 9.71e-04 |  |
| 10000 | 0.037270 | 6.59e-03 |  |

1e-4 içinde eşit: {0.1, 1, 10, 100} → seçilen λ=100. Eğitim satırı 242320, V2 fit'ine giren (uygun) 241046.

| anlık bant | 60 dk eğilim | satır | Y=1 | olay | kaynak | WoE |
|---|---:|---:|---:|---:|---:|---:|
| 1000–3000 | iyilesen_sabit | 1219 | 251 | 95 | hucre | 3.566 |
| 1000–3000 | 1_bant | 579 | 139 | 81 | hucre | 3.764 |
| 1000–3000 | 2+_bant | 598 | 180 | 134 | hucre | 4.073 |
| 3000–5000 | iyilesen_sabit | 4119 | 160 | 75 | hucre | 1.709 |
| 3000–5000 | 1_bant | 1427 | 86 | 65 | hucre | 2.173 |
| 3000–5000 | 2+_bant | 894 | 75 | 64 | hucre | 2.530 |
| 5000–9999 | iyilesen_sabit | 13896 | 174 | 82 | hucre | 0.549 |
| 5000–9999 | 1_bant | 3583 | 56 | 43 | hucre | 0.780 |
| 5000–9999 | 2+_bant | 3590 | 120 | 99 | hucre | 1.554 |
| ≥9999 | iyilesen_sabit | 211774 | 507 | 148 | hucre | -1.117 |
| ≥9999 | 1_bant | 0 | 0 | 0 | bant | -1.115 |
| ≥9999 | 2+_bant | 0 | 0 | 0 | bant | -1.115 |

`dspread_1sa`: <=-2: n=26747, Y=1=101, olay=60, WoE=-0.654; -1: n=51096, Y=1=435, olay=213, WoE=0.160; 0: n=89332, Y=1=967, olay=257, WoE=0.402; +1: n=45228, Y=1=203, olay=136, WoE=-0.483; >=+2: n=29276, Y=1=42, olay=27, WoE=-1.617

`egilim120`: iyilesen_sabit: n=226489, Y=1=902, olay=237, WoE=-0.604; 1_bant: n=6400, Y=1=248, olay=128, WoE=1.708; 2+_bant: n=8157, Y=1=591, olay=215, WoE=2.368

Katsayılar (sabit, ruzgar_kuzey, saat, spread, spread_egilim_3, gv60, dspread_1sa, egilim120): -4.916, 0.464, 0.424, 0.598, -0.055, 0.642, -0.160, 0.086

### V2c — 2015–16

| λ | havuzlanmış iç LL (uygun satırlar) | en iyiden fark | eleme |
|---|---:|---:|---:|
| 0.1 | 0.034126 | 4.35e-04 |  |
| 1 | 0.034110 | 4.19e-04 |  |
| 10 | 0.033989 | 2.98e-04 |  |
| 100 | 0.033691 | 0.00e+00 |  |
| 1000 | 0.035281 | 1.59e-03 |  |
| 10000 | 0.043037 | 9.35e-03 |  |

1e-4 içinde eşit: {100} → seçilen λ=100. Eğitim satırı 69185, V2 fit'ine giren (uygun) 68492.

| anlık bant | 60 dk eğilim | satır | Y=1 | olay | kaynak | WoE |
|---|---:|---:|---:|---:|---:|---:|
| 1000–3000 | iyilesen_sabit | 317 | 53 | 29 | bant | 3.706 |
| 1000–3000 | 1_bant | 177 | 40 | 25 | bant | 3.706 |
| 1000–3000 | 2+_bant | 170 | 50 | 37 | bant | 3.706 |
| 3000–5000 | iyilesen_sabit | 1289 | 40 | 21 | hucre | 1.556 |
| 3000–5000 | 1_bant | 461 | 29 | 20 | bant | 1.949 |
| 3000–5000 | 2+_bant | 243 | 22 | 18 | bant | 1.949 |
| 5000–9999 | iyilesen_sabit | 4895 | 53 | 25 | hucre | 0.480 |
| 5000–9999 | 1_bant | 986 | 21 | 14 | hucre | 1.181 |
| 5000–9999 | 2+_bant | 1243 | 31 | 24 | hucre | 1.335 |
| ≥9999 | iyilesen_sabit | 59056 | 123 | 38 | hucre | -1.183 |
| ≥9999 | 1_bant | 0 | 0 | 0 | bant | -1.179 |
| ≥9999 | 2+_bant | 0 | 0 | 0 | bant | -1.179 |

`dspread_1sa`: <=-2: n=8271, Y=1=24, olay=13, WoE=-0.826; -1: n=14475, Y=1=134, olay=64, WoE=0.323; 0: n=24499, Y=1=251, olay=70, WoE=0.424; +1: n=12697, Y=1=49, olay=34, WoE=-0.551; >=+2: n=8895, Y=1=4, olay=4, WoE=0.000

`egilim120`: iyilesen_sabit: n=63987, Y=1=215, olay=63, WoE=-0.695; 1_bant: n=1835, Y=1=74, olay=36, WoE=1.832; 2+_bant: n=2670, Y=1=171, olay=61, WoE=2.315

Katsayılar (sabit, ruzgar_kuzey, saat, spread, spread_egilim_3, gv60, dspread_1sa, egilim120): -4.900, 0.315, 0.370, 0.536, 0.098, 0.565, 0.032, 0.202

