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

**Hiçbir varyant §8 birincil kuralını geçmedi. Deney 1 kapanır.**
**Önceden dondurulmuş V2a/b/c spesifikasyonlarının hiçbiri V1 referansını
iyileştirmedi.** Bu deney, gidişat bilgisinin V1'e *koşullu olarak* sıfır ek
bilgi taşıdığını göstermez: gv60, V1'in `gorus` WoE'sine eklenmedi, onun yerine
geçti. Gözlenen ΔLL, gidişattan gelen olası kazanç ile anlık görüş
çözünürlüğündeki kaybın toplamıdır ve bu deney ikisini ayırmaz (merge öncesi
audit, §6). Kayda geçen: Protokol 1.0'daki V2a/b/c formülasyonları başarısız
oldu; gidişat fikri "işe yaramaz" diye kapatılmadı.

**Bilimsel yorum (28.09.2026):** Protokol 1.0 kapsamındaki V2a/V2b/V2c hattı
kapanmıştır. "Gidişat hipotezi reddedildi" sonucu çıkarılmaz. Audit, ileride
ayrı ve yeni bir araştırma protokolü kurulursa V1'in ayrıntılı `gorus`
temsilini koruyup gidişatı ek değişken olarak sınamanın bilimsel olarak makul
bir soru olduğunu gösteriyor. Bu, Deney 1'in devamı ya da bir V2d değildir ve
şu anda çalıştırılmayacaktır.

Üç varyantta da nokta ΔLL negatif
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

Yapılan audit kontrollerinde sonucu açıklayan bir uygulama hatası saptanmadı.
Bu, aşağıda sayılan kontrollerle sınırlıdır; test edilmemiş hata sınıflarının
dışlandığı anlamına gelmez.

- Coverage yüksek (%99,87–99,93); geri dönüş sonucu belirlemiyor.
- Her fold'da ve her varyantta bütün λ'lar yakınsadı; seçim 1e-4 kuralıyla
  hep λ=100 (en küçük iç LL çoğunlukla λ=10'da, 1e-4 içinde eşit).
- gv60 hücre kaynakları (§7.5 hiyerarşisi): 2023–24 ve 2025–26'da hiç satırı
  olmayan "≥9999 × düşüş" hücreleri dışında bütün hücreler kendi WoE'sini
  aldı. Daha küçük eğitim kümelerinde bazı hücreler 500 satır eşiğinin altında
  kaldı ve bant düzeyine düştü: 2017–18'de 1000–3000 × (1 bant, 2+ bant) ve
  3000–5000 × 2+ bant; 2019–20'de aynı üç hücre; 2021–22'de 1000–3000 ×
  (1 bant, 2+ bant). Hiçbir hücre V1 `gorus` düzeyine düşmedi. (İlk sürümde
  burada "hücrelerin tamamı kendi WoE'sini aldı" yazıyordu; merge öncesi
  audit'te düzeltildi.) Hücre WoE'leri beklenen yönde: aynı anlık bantta görüş
  düşüşü arttıkça WoE artıyor.
- Katsayılar fold'lar arasında tutarlı. `dspread_1sa` katsayısı birincil
  fold'larda negatif (−0,10 … −0,16); `spread_egilim_3`'ün son iki fold'daki
  negatif işareti V2'de de sürüyor. Bunlar kayıt olarak yazıldı; yorumlanmadı.
- Anlık görüş çözünürlüğü kaybı: merge öncesi audit'te (§6) betimsel olarak
  incelendi. Sonuç görüldükten sonra ortaya çıkan bu inceleme yeni bir aday
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

## 6. Merge öncesi audit (audit-only; karar değiştirmez)

**Kapsam:** Kullanıcı talebiyle, Deney 1'in başarısızlık kararını, protokol
kriterlerini ve spesifikasyonları değiştirmeden yapılan betimsel inceleme. Yeni
aday (V2d) üretilmedi, yeni λ ya da kural denenmedi. Betik:
`sis_modeli/deney1_audit.py` (commit `c834e14`, sonuç görülmeden önce). Deney 1
artefaktları diske yazılmadığı için fold modelleri dondurulmuş prosedürle
deterministik olarak yeniden üretildi. Dört modelin havuzlanmış LL'si
(0,027349 / 0,027690 / 0,027664 / 0,027677) ve bütün λ'lar Deney 1 raporuyla
birebir eşleşti. Tam çıktı Ek B'de.

### 6.1 V1 `gorus` kovaları ile gv60 bantları

V1, anlık görüşü her fold'da 10–11 kovaya ayırıyor; gv60 ise 4 banda. 2025–26
fold'unda:

| gv60 bandı | bu bantla kesişen V1 kovaları | V1 WoE aralığı | V1 WoE ayrımı | gv60 bant WoE (eğilimsiz) |
|---|---|---|---|---|
| 1000–3000 | 4 (≤1600, 1600–2200, 2200–2800, 2800–3400*) | +2,54 … +4,61 | 2,08 | +3,75 |
| 3000–5000 | 4 (2800–3400*, 3400–4000, 4000–4600, 4600–6000*) | +1,43 … +2,54 | 1,11 | +1,97 |
| 5000–9999 | 2 (4600–6000*, 6000–9999) | +0,80 … +1,43 | 0,63 | +0,84 |
| ≥9999 | 2 (9999, ≥10000) | −1,16 … −1,09 | 0,07 | −1,12 |

\* bant sınırını kesen kova. Bütün birincil fold'larda desen aynı: 1000–3000
bandında V1'in WoE ayrımı 1,88–2,16, 3000–5000'de 0,98–1,11, 5000–9999'da
0,63–1,51, ≥9999'da 0,02–0,38.

### 6.2 Bant içinde 60 dk eğilim (betimsel)

Havuzlanmış OOS test satırları (2017–2026), hedef oranı ve iyileşen/sabit
sınıfına oranı (parantezde satır sayısı):

| anlık bant | iyileşen/sabit | 1 bant düşüş | ≥ 2 bant düşüş |
|---|---|---|---|
| 1000–3000 | %19,0 (758) | %21,2 (373) · 1,11× | %30,3 (373) · 1,59× |
| 3000–5000 | %4,05 (2.642) | %5,46 (916) · 1,35× | %7,78 (668) · 1,92× |
| 5000–9999 | %1,14 (8.304) | %1,38 (2.545) · 1,20× | %3,13 (2.142) · 2,73× |
| ≥9999 | %0,232 (149.594) | — (0) | — (0) |

Her fold'un eğitim tablolarında da aynı sıralama var; hücre WoE'leri düşüş
arttıkça yükseliyor. **Sınırlılık:** bu betimleme eğilimin etkisini bant içi
konumdan ayırmaz. Örneğin 1000–3000 bandında "≥2 bant düşüş" sınıfına bandın
alt ucundaki (1000–1500) satırlar daha kolay düşer. Yani bu oranlar kısmen
bant içi görüş çözünürlüğünü de yansıtıyor olabilir.

**Yorum:** Bant içindeki kötüleşme sınıflarında hedef oranının düzenli artması
bir gidişat sinyali bulunduğunu düşündürür; ancak bunun anlık görüş
seviyesinden bağımsız artımsal bilgi olduğunu bu deney kanıtlamaz.

### 6.3 V1 − V2 log-loss farkının görüş aralıklarına dağılımı (OOS, tanılama)

Katkı = Σ[LL(V1) − LL(V2 hibrit)] / N; katkılar toplamı birincil ΔLL'dir.
Parantezde V2a toplamındaki pay.

| anlık görüş | satır | Y=1 | gerçekleşen | ort. V1 | ort. V2a | V2a katkı | V2b katkı | V2c katkı |
|---|---|---|---|---|---|---|---|---|
| 1000–1500 | 358 | 161 | %45,0 | %35,8 | %25,2 | −0,000166 (%49) | −0,000164 | −0,000188 |
| 1500–3000 | 1.148 | 177 | %15,4 | %18,8 | %22,7 | −0,000151 (%44) | −0,000155 | −0,000103 |
| 3000–5000 | 4.234 | 209 | %4,94 | %6,52 | %6,53 | −0,000026 (%8) | −0,000027 | −0,000006 |
| 5000–8000 | 8.740 | 154 | %1,76 | %2,86 | %2,79 | +0,000075 (−%22) | +0,000076 | +0,000022 |
| 8000–9999 | 4.271 | 43 | %1,01 | %1,52 | %2,13 | −0,000080 (%24) | −0,000074 | −0,000092 |
| ≥9999 | 149.678 | 347 | %0,232 | %0,260 | %0,266 | +0,000007 (−%2) | +0,000029 | +0,000039 |
| **toplam** | | | | | | **−0,000340** | −0,000315 | −0,000328 |

- Kaybın ~%93'ü (V2a) 1000–3000 m aralığında. V1, 1000–1500 m (gerçekleşen
  %45) ile 1500–3000 m'yi (%15) ayırıyor. V2 bu ikisini aynı gv60 bandına
  topladığı için 1000–1500'de tahmini düşürüyor (%35,8 → %25,2), 1500–3000'de
  yükseltiyor (%18,8 → %22,7).
- 8000–9999 m (5000–8000 ile aynı gv60 bandında) ikinci kayıp kaynağı.
- 5000–8000 m ve ≥9999'da V2 küçük kazanç sağlıyor.
- Bu dağılım, gözlenen negatif ΔLL'nin önemli kısmının anlık görüş
  çözünürlüğü kaybıyla eşzamanlı olduğunu gösteriyor. Gidişatın kendi katkısını
  ayrı ölçmez. Yalnızca tanılamadır ve seçimde kullanılmaz.

### 6.4 ≥9999 bandında düşüş hücreleri

Tüm geliştirme evreninde (t−60 mevcut, anlık ≥9999) eğilim sınıfları:
iyileşen/sabit 239.284, 1 bant 0, 2+ bant 0. Bu, eğilim tanımının matematiksel
sonucudur: Δ = ince_indeks(t) − ince_indeks(t−60) ve ≥9999 en üst indekstir
(6), dolayısıyla Δ ≥ 0. Veri ya da kodlama hatası değildir. Sonuç olarak ≥9999
bandında gv60 tek hücrelidir ve eğilimsiz bant WoE'sine eşdeğerdir. Diğer üç
bantta düşüş hücreleri doludur (1 bant / 2+ bant: 1000–3000 636/663;
3000–5000 1.571/1.020; 5000–9999 3.955/3.877).

### 6.5 `dspread_1sa`: WoE ve katsayı işareti

Kova WoE'leri (bütün fold'larda benzer; 2025–26): ≤−2: −0,65 · −1: +0,16 ·
0: +0,40 · +1: −0,48 · ≥+2: −1,62. Doğrusal değil. Lojistik katsayı
−0,10 … −0,16.

- 2025–26 eğitiminde `dspread_1sa` WoE'si, `spread_egilim_3` WoE'siyle +0,54 ve
  `spread` WoE'siyle +0,38 korelasyonlu.
- Spread düzeyi sabit tutulduğunda `dspread_1sa` kovaları arasında hedef oranı
  farkı küçük (spread ≤1 °C: %3,6 / %3,8 / %3,7 / %4,4; 2–3 °C: %0,56 / %0,49 /
  %0,56 / %0,63 / %1,53).
- Marjinal WoE büyük ölçüde spread düzeyi ve 3 saatlik spread eğilimiyle
  örtüşen bilgiyi taşıyor. Bu örtüşmede katsayının küçük ve işaretinin
  marjinal WoE'ye ters olması, WoE-lojistik modellerde eş-doğrusallıkla
  beklenebilir bir kodlama sonucudur. Meteorolojik nedensellik yorumu yapılmadı.

---

# Ek A — Deney 1 betik çıktısı (tam tablolar, eğitim artefaktları dahil)


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


# Ek B — merge öncesi audit çıktısı (tam; `python -m sis_modeli.deney1_audit`)

Not: §1 tablosundaki "bant içinde / sınırı aşan" sayımında alt sınırı açık
kova (`— – 1600`) "sınırı aşan" sayılıyor; onset evreninde görüş ≥ 1000 m
olduğundan bu kova fiilen 1000–3000 bandının içindedir.

## 0. Yeniden üretim kontrolü

| model | yeniden üretilen havuzlanmış LL | Deney 1 raporundaki |
|---|---:|---:|
| V1 | 0.027349 | 0.027349 |
| V2a | 0.027690 | 0.027690 |
| V2b | 0.027664 | 0.027664 |
| V2c | 0.027677 | 0.027677 |

λ (V1 / V2a / V2b / V2c): 2017–18: 100 / 100 / 100 / 100; 2019–20: 100 / 100 / 100 / 100; 2021–22: 100 / 100 / 100 / 100; 2023–24: 100 / 100 / 100 / 100; 2025–26: 100 / 100 / 100 / 100

## 1. V1 `gorus` WoE kovaları ile gv60'ın dört anlık bandı

### 2017–18

| V1 kova | satır | Y=1 | oran % | WoE |
|---|---:|---:|---:|---:|
| — – 1600 | 263 | 107 | 40.684 | +4.445 |
| 1600 – 2200 | 397 | 100 | 25.189 | +3.735 |
| 2200 – 2800 | 327 | 58 | 17.737 | +3.293 |
| 2800 – 3400 | 637 | 60 | 9.419 | +2.564 |
| 3400 – 4000 | 416 | 20 | 4.808 | +1.858 |
| 4000 – 4600 | 1419 | 53 | 3.735 | +1.580 |
| 4600 – 6000 | 738 | 28 | 3.794 | +1.604 |
| 6000 – 8000 | 7142 | 147 | 2.058 | +0.961 |
| 8000 – 9999 | 2381 | 22 | 0.924 | +0.168 |
| 9999 – 10000 | 55035 | 124 | 0.225 | -1.269 |
| 10000 – — | 35045 | 106 | 0.302 | -0.973 |

| anlık bant | V1 kovası (bant içinde) | V1 kovası (sınırı aşan) | V1 WoE aralığı | V1 WoE ayrımı (maks−min) | gv60 bant WoE (eğilimsiz) | bant satırı | bant Y=1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1000–3000 | 2 | 2 | +2.564 … +4.445 | 1.880 | +3.736 | 1124 | 283 |
| 3000–5000 | 2 | 2 | +1.580 … +2.564 | 0.984 | +1.792 | 2816 | 129 |
| 5000–9999 | 2 | 1 | +0.168 … +1.604 | 1.437 | +0.867 | 9780 | 183 |
| ≥9999 | 2 | 0 | -1.269 … -0.973 | 0.296 | -1.141 | 90080 | 230 |

### 2019–20

| V1 kova | satır | Y=1 | oran % | WoE |
|---|---:|---:|---:|---:|
| — – 1600 | 382 | 167 | 43.717 | +4.572 |
| 1600 – 2200 | 529 | 127 | 24.008 | +3.674 |
| 2200 – 2800 | 507 | 83 | 16.371 | +3.198 |
| 2800 – 3400 | 935 | 77 | 8.235 | +2.419 |
| 3400 – 4000 | 646 | 27 | 4.180 | +1.709 |
| 4000 – 4600 | 2039 | 71 | 3.482 | +1.509 |
| 4600 – 6000 | 1096 | 34 | 3.102 | +1.397 |
| 6000 – 8000 | 9707 | 177 | 1.823 | +0.841 |
| 8000 – 9999 | 3495 | 27 | 0.773 | -0.013 |
| 9999 – 10000 | 73249 | 165 | 0.225 | -1.266 |
| 10000 – — | 45975 | 144 | 0.313 | -0.935 |

| anlık bant | V1 kovası (bant içinde) | V1 kovası (sınırı aşan) | V1 WoE aralığı | V1 WoE ayrımı (maks−min) | gv60 bant WoE (eğilimsiz) | bant satırı | bant Y=1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1000–3000 | 2 | 2 | +2.419 … +4.572 | 2.153 | +3.709 | 1621 | 399 |
| 3000–5000 | 2 | 2 | +1.397 … +2.419 | 1.023 | +1.686 | 4163 | 172 |
| 5000–9999 | 2 | 1 | -0.013 … +1.397 | 1.410 | +0.720 | 13552 | 219 |
| ≥9999 | 2 | 0 | -1.266 … -0.935 | 0.331 | -1.124 | 119224 | 309 |

### 2021–22

| V1 kova | satır | Y=1 | oran % | WoE |
|---|---:|---:|---:|---:|
| — – 1600 | 446 | 195 | 43.722 | +4.652 |
| 1600 – 2200 | 617 | 145 | 23.501 | +3.726 |
| 2200 – 2800 | 620 | 96 | 15.484 | +3.211 |
| 2800 – 3400 | 1106 | 91 | 8.228 | +2.497 |
| 3400 – 4000 | 798 | 39 | 4.887 | +1.948 |
| 4000 – 4600 | 2467 | 95 | 3.851 | +1.691 |
| 4600 – 6000 | 1442 | 41 | 2.843 | +1.384 |
| 6000 – 8000 | 11405 | 186 | 1.631 | +0.807 |
| 8000 – 9999 | 4528 | 29 | 0.640 | -0.123 |
| 9999 – 10000 | 90491 | 179 | 0.198 | -1.317 |
| 10000 – — | 58650 | 169 | 0.288 | -0.940 |

| anlık bant | V1 kovası (bant içinde) | V1 kovası (sınırı aşan) | V1 WoE aralığı | V1 WoE ayrımı (maks−min) | gv60 bant WoE (eğilimsiz) | bant satırı | bant Y=1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1000–3000 | 2 | 2 | +2.497 … +4.652 | 2.155 | +3.749 | 1917 | 458 |
| 3000–5000 | 2 | 2 | +1.384 … +2.497 | 1.113 | +1.832 | 5127 | 226 |
| 5000–9999 | 2 | 1 | -0.123 … +1.384 | 1.508 | +0.670 | 16385 | 233 |
| ≥9999 | 2 | 0 | -1.317 … -0.940 | 0.377 | -1.150 | 149141 | 348 |

### 2023–24

| V1 kova | satır | Y=1 | oran % | WoE |
|---|---:|---:|---:|---:|
| — – 1600 | 549 | 239 | 43.534 | +4.576 |
| 1600 – 2200 | 715 | 173 | 24.196 | +3.695 |
| 2200 – 2800 | 713 | 118 | 16.550 | +3.221 |
| 2800 – 3400 | 1209 | 101 | 8.354 | +2.445 |
| 3400 – 4000 | 903 | 56 | 6.202 | +2.127 |
| 4000 – 4600 | 2823 | 128 | 4.534 | +1.792 |
| 4600 – 6000 | 1649 | 51 | 3.093 | +1.400 |
| 6000 – 8000 | 13149 | 250 | 1.901 | +0.894 |
| 8000 – 9999 | 5388 | 48 | 0.891 | +0.134 |
| 9999 – 10000 | 108991 | 279 | 0.256 | -1.128 |
| 10000 – — | 71267 | 186 | 0.261 | -1.108 |

| anlık bant | V1 kovası (bant içinde) | V1 kovası (sınırı aşan) | V1 WoE aralığı | V1 WoE ayrımı (maks−min) | gv60 bant WoE (eğilimsiz) | bant satırı | bant Y=1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1000–3000 | 2 | 2 | +2.445 … +4.576 | 2.131 | +3.724 | 2237 | 553 |
| 3000–5000 | 2 | 2 | +1.400 … +2.445 | 1.045 | +1.895 | 5817 | 291 |
| 5000–9999 | 2 | 1 | +0.134 … +1.400 | 1.266 | +0.770 | 19044 | 320 |
| ≥9999 | 2 | 0 | -1.128 … -1.108 | 0.020 | -1.119 | 180258 | 465 |

### 2025–26

| V1 kova | satır | Y=1 | oran % | WoE |
|---|---:|---:|---:|---:|
| — – 1600 | 586 | 249 | 42.491 | +4.613 |
| 1600 – 2200 | 772 | 181 | 23.446 | +3.733 |
| 2200 – 2800 | 777 | 123 | 15.830 | +3.247 |
| 2800 – 3400 | 1314 | 111 | 8.447 | +2.536 |
| 3400 – 4000 | 997 | 64 | 6.419 | +2.243 |
| 4000 – 4600 | 3127 | 138 | 4.413 | +1.843 |
| 4600 – 6000 | 1940 | 57 | 2.938 | +1.426 |
| 6000 – 9999 | 20567 | 329 | 1.600 | +0.797 |
| 9999 – 10000 | 126981 | 313 | 0.246 | -1.087 |
| 10000 – — | 85259 | 195 | 0.229 | -1.161 |

| anlık bant | V1 kovası (bant içinde) | V1 kovası (sınırı aşan) | V1 WoE aralığı | V1 WoE ayrımı (maks−min) | gv60 bant WoE (eğilimsiz) | bant satırı | bant Y=1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1000–3000 | 2 | 2 | +2.536 … +4.613 | 2.077 | +3.753 | 2421 | 576 |
| 3000–5000 | 2 | 2 | +1.426 … +2.536 | 1.110 | +1.970 | 6484 | 323 |
| 5000–9999 | 1 | 1 | +0.797 … +1.426 | 0.629 | +0.841 | 21175 | 353 |
| ≥9999 | 2 | 0 | -1.161 … -1.087 | 0.074 | -1.115 | 212240 | 508 |

## 2. Aynı anlık bant içinde 60 dk eğilim — eğitim satırları

| fold | anlık bant | iyileşen/sabit oran % (satır) | 1 bant oran % (satır) · kaynak | 2+ bant oran % (satır) · kaynak |
|---|---|---|---|---|
| 2017–18 | 1000–3000 | 22.08 (548) | 25.48 (263) · bant | 31.38 (290) · bant |
| 2017–18 | 3000–5000 | 3.10 (1773) | 6.41 (655) · hücre | 8.52 (352) · bant |
| 2017–18 | 5000–9999 | 1.41 (6548) | 1.99 (1410) · hücre | 3.46 (1735) · hücre |
| 2019–20 | 1000–3000 | 22.66 (821) | 24.10 (390) · bant | 29.35 (385) · bant |
| 2019–20 | 3000–5000 | 2.86 (2723) | 5.61 (909) · hücre | 8.37 (490) · bant |
| 2019–20 | 5000–9999 | 1.15 (9134) | 1.82 (2032) · hücre | 3.23 (2291) · hücre |
| 2021–22 | 1000–3000 | 20.69 (981) | 24.57 (460) · bant | 30.16 (451) · bant |
| 2021–22 | 3000–5000 | 3.52 (3355) | 5.31 (1130) · hücre | 7.68 (599) · hücre |
| 2021–22 | 5000–9999 | 1.00 (10954) | 1.48 (2638) · hücre | 3.05 (2692) · hücre |
| 2023–24 | 1000–3000 | 21.41 (1135) | 25.28 (530) · hücre | 31.08 (547) · hücre |
| 2023–24 | 3000–5000 | 3.77 (3736) | 6.07 (1286) · hücre | 9.31 (752) · hücre |
| 2023–24 | 5000–9999 | 1.28 (12630) | 1.53 (3145) · hücre | 3.41 (3166) · hücre |
| 2025–26 | 1000–3000 | 20.59 (1219) | 24.01 (579) · hücre | 30.10 (598) · hücre |
| 2025–26 | 3000–5000 | 3.88 (4119) | 6.03 (1427) · hücre | 8.39 (894) · hücre |
| 2025–26 | 5000–9999 | 1.25 (13896) | 1.56 (3583) · hücre | 3.34 (3590) · hücre |

≥9999 bandında her fold'da yalnız iyileşen/sabit sınıfı dolu (bkz. §4).
Havuzlanmış OOS test satırları için tablo raporun §6.2'sinde.

## 3. V1 − V2 log-loss farkının dağılımı

Anlık görüş (ince bant) tablosu raporun §6.3'ünde. Ek olarak, V2a — 2025–26
test satırları, o fold'un V1 `gorus` kovasına göre:

| V1 kova | V1 WoE | satır | Y=1 | ΔLL katkısı (fold içi) |
|---|---:|---:|---:|---:|
| — – 1600 | +4.613 | 56 | 27 | -0.000198 |
| 1600 – 2200 | +3.733 | 51 | 6 | +0.000000 |
| 2200 – 2800 | +3.247 | 77 | 9 | -0.000021 |
| 2800 – 3400 | +2.536 | 101 | 5 | +0.000044 |
| 3400 – 4000 | +2.243 | 104 | 2 | +0.000029 |
| 4000 – 4600 | +1.843 | 253 | 8 | +0.000030 |
| 4600 – 6000 | +1.426 | 239 | 3 | -0.000001 |
| 6000 – 9999 | +0.797 | 1507 | 27 | +0.000020 |
| 9999 – 10000 | -1.087 | 14880 | 52 | -0.000021 |
| 10000 – — | -1.161 | 12641 | 17 | +0.000011 |

## 4. ≥9999 bandında düşüş hücreleri

| anlık bant | iyileşen/sabit | 1 bant | 2+ bant |
|---|---:|---:|---:|
| 1000–3000 | 1306 | 636 | 663 |
| 3000–5000 | 4415 | 1571 | 1020 |
| 5000–9999 | 14855 | 3955 | 3877 |
| ≥9999 | 239284 | 0 | 0 |

## 5. `dspread_1sa`

| fold | WoE <=-2 | WoE -1 | WoE 0 | WoE +1 | WoE >=+2 | katsayı |
|---|---:|---:|---:|---:|---:|---:|
| 2017–18 | -0.614 | +0.251 | +0.361 | -0.428 | -1.836 | -0.100 |
| 2019–20 | -0.665 | +0.252 | +0.354 | -0.385 | -2.099 | -0.131 |
| 2021–22 | -0.680 | +0.248 | +0.366 | -0.410 | -2.235 | -0.114 |
| 2023–24 | -0.611 | +0.170 | +0.394 | -0.480 | -1.615 | -0.155 |
| 2025–26 | -0.654 | +0.160 | +0.402 | -0.483 | -1.617 | -0.159 |

2025–26 eğitiminde (uygun satır 241.679) `dspread_1sa` WoE'sinin diğer WoE
sütunlarıyla korelasyonu: ruzgar_kuzey +0.095, saat +0.205, spread +0.378,
spread_egilim_3 +0.539, gv60 +0.104.

Spread düzeyi içinde `dspread_1sa` kovasına göre hedef oranı (%), 2025–26 eğitimi:

| spread(t) °C | <=-2 | -1 | 0 | +1 | >=+2 |
|---|---:|---:|---:|---:|---:|
| ≤ 1 | 3.59 (n=1753) | 3.76 (n=9705) | 3.72 (n=21191) | 4.41 (n=2469) | — |
| 2–3 | 0.56 (n=4494) | 0.49 (n=13061) | 0.56 (n=28418) | 0.63 (n=12629) | 1.53 (n=1760) |
| ≥ 4 | 0.06 (n=20500) | 0.02 (n=28330) | 0.05 (n=39723) | 0.05 (n=30130) | 0.05 (n=27516) |

