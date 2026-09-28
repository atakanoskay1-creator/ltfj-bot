# Sis modeli V2 — V1 referans benchmark'ı

**Tarih:** 28 Eylül 2026 · **Protokol:** 1.0 · **Betik:** `python -m sis_modeli.v1_benchmark`
Hedefin teknik adı: **LTFJ düşük görüş/FG olayı**. V2a/b/c eğitilmedi; hiçbir
V2 skoru hesaplanmadı.

Bu belgede iki çalışma var ve ikisi de kayıtta kalır:

| çalışma | çözücü | durum | yer |
|---|---|---|---|
| **solver-corrected V1 reference benchmark** | `v2_cozucu.egit` (sönümlü Newton) | **geçerli V1 referansı** | Ek A |
| pre-fix diagnostic run | `model.egit` (adım kontrolsüz IRLS) | nihai benchmark **değildir**; tanılama çalışması | Ek B |

| commit | ne |
|---|---|
| `f550037` | benchmark prosedürü (ilk çalışmadan önce) |
| `8d65ec6` | pre-fix diagnostic run çıktısı |
| `2e161ea` | sönümlü Newton çözücüsü + testleri (düzeltilmiş çalışmadan önce) |

---

## 1. Çözücü bulgusu ve düzeltmesi (§15)

**Bulgu (pre-fix run):** §6 kuralı ("bir L2 herhangi bir iç blokta
`TekilSistem` ya da `Yakinsamadi` verirse o dış fold için elenir") şu λ'ları
eledi:

| λ | ilk ıraksadığı iç blok | elendiği dış fold'lar |
|---|---|---|
| 0,1 ve 1 | 2016 | 5 birincil fold'un hepsi |
| 10 | 2019 | 2021–22, 2023–24, 2025–26 |
| 100 | 2022 | 2023–24, 2025–26 |

`model.egit`'te değişim iterasyon 1–4'te 3–7 düzeyinde, 5. iterasyondan
itibaren patlıyor (10²–10⁵) ve ~7,8×10⁶'da sabitleniyor; sabit terim −6×10⁸'e
gidiyor.

**Değerlendirme:** Mevcut IRLS'in `Yakinsamadi` verdiği incelenen fit'lerde,
aynı cezalı amaç fonksiyonu sönümlü Newton yöntemiyle sonlu ve olağan ölçekte
bir çözüme yakınsamıştır. Bu nedenle gözlenen başarısızlıkların en azından
incelenen örneklerde modelin çözümsüzlüğünden değil, mevcut IRLS adım
mekanizmasından kaynaklandığı değerlendirilmiştir.

| iç blok | λ | iterasyon | son değişim | en büyük gradyan | katsayılar (sabit, gorus, ruzgar_kuzey, saat, spread, spread_egilim_3) |
|---|---|---|---|---|---|
| 2016 | 0,1 | 8 | 8,2e-09 | 3,8e-05 | −4,898 · 0,700 · 0,592 · 0,499 · 0,596 · −0,052 |
| 2016 | 1 | 8 | 7,6e-12 | 3,6e-05 | −4,896 · 0,700 · 0,588 · 0,498 · 0,596 · −0,050 |
| 2019 | 10 | 8 | 1,1e-10 | 8,7e-07 | −4,890 · 0,711 · 0,562 · 0,547 · 0,558 · −0,021 |
| 2022 | 100 | 8 | 2,2e-11 | 1,6e-08 | −4,884 · 0,687 · 0,455 · 0,486 · 0,509 · −0,037 |

(Bu tanıda log-loss, λ seçimi ya da test ölçütü hesaplanmadı.)

**Sınıflandırma (kullanıcı kararı, 28.09.2026):** §15 kapsamında çözücü /
uygulama hatası. λ ızgarası, 1e-4 eşitlik toleransı, iç blok yapısı ve 3 saat
ambargo **değişmedi**.

**Düzeltme — `sis_modeli/v2_cozucu.py`:** `model.egit` değiştirilmedi
(tarihsel V1 deneyleri yeniden üretilebilir). Yeni fonksiyon aynı amaç
fonksiyonunu çözer:
`f(b) = Σ [nᵈ·log(1+e^ηᵈ) − kᵈ·ηᵈ] + (λ/2)·Σᵢ₍ᵢ≥₁₎ bᵢ²` (sabit terim
cezasız). Newton adımı; amacı kötüleştiren adım kabul edilmez, adım çarpanı
deterministik olarak yarılanır (kabul: f(yeni) ≤ f(eski)).

| sabit | değer | anlam |
|---|---|---|
| `YAKINSAMA` | 1e-7 | tam Newton adımının en büyük bileşeni bunun altındaysa yakınsadı |
| `AZALIM_GORELI` | 1e-12 | ya da Newton azalımı gᵀH⁻¹g/2 ≤ 1e-12·max(1, \|f\|) ise yakınsadı |
| `MAKS_ITER` | 100 | aşılırsa `Yakinsamadi` |
| `ASGARI_ADIM` | 2⁻³⁰ | adım çarpanı bunun altına inerse `Yakinsamadi` |
| Hessian çözülemezse | — | `TekilSistem` |

**Tasarım notu (şeffaflık):** İlk tasarımda yalnızca adım ölçütü vardı.
Çözücünün kendi gerçek veri testinde (iç blok 2016, λ=0,1) amaç 1e-12
düzeyinde sabitlendiği hâlde, zayıf belirlenen bir yönde kayan nokta
gürültüsü yüzünden tam adım 1,3e-7'nin altına inmedi ve "amacı kötüleştirmeyen
adım bulunamadı" hatası verdi. Newton azalımı ölçütü bu test üzerine, düzeltilmiş
benchmark çalıştırılmadan **önce** eklendi (commit `2e161ea`).

**Testle kilitlenenler** (`tests/test_sis_modeli_v2_cozucu.py`):
- Sabitlerin değerleri.
- Kabul edilen her adımda cezalı amaç kötüleşmez (sentetik veri, λ ∈ {0,1; 1; 10; 100}).
- Eski IRLS'in düzgün yakınsadığı referans fit'lerde aynı optimum; gerçek
  veride fark < 1e-5 (iç blok 2014/λ 0,1; 2016/100; 2019/100; 2022/1000).
- Pre-fix run'da ıraksayan dört fit (2016/0,1; 2016/1; 2019/10; 2022/100):
  eski IRLS hâlâ `Yakinsamadi` verir, yeni çözücü olağan ölçekte yakınsar ve
  amaç tekdüze azalır.
- Gerçek başarısızlık yolları: cezasız tam ayrışma → `Yakinsamadi`/`TekilSistem`;
  tekil Hessian → `TekilSistem`; `MAKS_ITER` aşımı → `Yakinsamadi`.
- Determinizm.

---

## 2. Solver-corrected V1 reference benchmark — özet

Ayrıntılı tablolar Ek A'da: fold sayımları, bütün λ'ların iç log-loss'ları,
katsayılar, 6/6 ve SN tanılamaları, olay ölçütleri, güvenilirlik.

**λ seçimi:** hiçbir λ elenmedi. Bütün birincil fold'larda λ=100 seçildi.

| fold | en küçük iç LL | 1e-4 içinde eşit | seçilen |
|---|---|---|---|
| 2017–18 | λ=100 | {10, 100} | 100 |
| 2019–20 | λ=10 | {0,1; 1; 10; 100} | 100 |
| 2021–22 | λ=10 | {0,1; 1; 10; 100} | 100 |
| 2023–24 | λ=10 | {0,1; 1; 10; 100} | 100 |
| 2025–26 | λ=10 | {0,1; 1; 10; 100} | 100 |
| 2015–16 (tanılama) | λ=100 | {100} | 100 |

**Test (birincil tam onset evreni):**

| fold | test / Y=1 / olay | LL (nat) | Brier×10⁴ | AP | LSS |
|---|---|---|---|---|---|
| 2017–18 | 34.760 / 274 / 40 | 0,03055 | 66,06 | 0,278 | 0,298 |
| 2019–20 | 34.010 / 166 / 26 | 0,01969 | 41,56 | 0,244 | 0,342 |
| 2021–22 | 34.786 / 364 / 51 | 0,04255 | 92,20 | 0,192 | 0,320 |
| 2023–24 | 34.964 / 131 / 19 | 0,01856 | 36,05 | 0,128 | 0,264 |
| 2025–26 | 29.909 / 156 / 24 | 0,02493 | 47,00 | 0,174 | 0,163 |
| **havuzlanmış OOS** | **168.429 / 1.091 / 160** | **0,02735** | **56,90** | **0,197** | **0,289** |

LSS referansı: her fold'un yalnızca kendi ambargolu eğitim satırlarından
kurulan ay × saat iklimi (yalnız LL/LSS referansı). Olay bant eşiği:
dondurulmuş production V1 taban oranı %0,757'nin 5 katı = %3,785 (§9.1);
benchmark iklimiyle yeniden tanımlanmadı.

## 3. Çözücü düzeltmesinin V1 benchmark'ına etkisi

ΔLL_çözücü = LL(eski) − LL(yeni); pozitif = yeni çözücüyle daha iyi. **Yalnızca
çözücü düzeltmesinin V1 benchmark'ına etkisidir; V2 karşılaştırmasındaki
birincil ΔLL ile karıştırılmamalıdır.**

| fold | eski λ | yeni λ | eski LL | yeni LL | ΔLL_çözücü | eski AP | yeni AP |
|---|---|---|---|---|---|---|---|
| 2017–18 | 100 | 100 | 0,03055 | 0,03055 | 0,00000 | 0,278 | 0,278 |
| 2019–20 | 100 | 100 | 0,01969 | 0,01969 | 0,00000 | 0,244 | 0,244 |
| 2021–22 | 100 | 100 | 0,04255 | 0,04255 | 0,00000 | 0,192 | 0,192 |
| 2023–24 | 1000 | 100 | 0,01889 | 0,01856 | +0,00033 | 0,119 | 0,128 |
| 2025–26 | 1000 | 100 | 0,02490 | 0,02493 | −0,00002 | 0,179 | 0,174 |
| 2015–16 (tanılama) | 100 | 100 | 0,04007 | 0,04007 | 0,00000 | 0,222 | 0,222 |
| **havuzlanmış (5 fold)** | | | 0,02741 | 0,02735 | +0,00006 | 0,197 | 0,197 |

- Seçilen λ'nın değişmediği fold'larda (2017–18, 2019–20, 2021–22, 2015–16)
  sonuçlar iki çözücüde aynı. Bu, iki çözücünün yakınsadıkları yerde aynı
  optimuma ulaştığının bağımsız bir kontrolüdür.
- Fark yalnızca eski çalışmada λ=100'ün yakınsama hatasıyla elendiği iki
  fold'da.

## 4. Beklenmedik bulgular (V1 hattı; performans kararı değil)

1. **`spread_egilim_3` katsayısının işareti son iki fold'da negatif:** 2023–24'te
   −0,109, 2025–26'da −0,100. Önceki fold'larda +0,010 … +0,110. WoE
   kodlamasında negatif katsayı, değişkenin diğerleri sabitken tek başına
   WoE'sinin tersi yönünde çalıştığı anlamına gelir; büyüklüğü küçük. Bu iki
   fold'un eğitimine 2021–2022 giriyor; bilinen 2021–2023 çiy noktası kusuru
   spread'i ve dolayısıyla spread_egilim_3'ü etkiliyor. Neden olduğu bu
   çalışmayla belirlenmedi; kayıt olarak yazıldı. (Pre-fix run'da bu fold'lar
   λ=1000 ile daha çok büzüldüğü için katsayı +0,035/+0,038 görünüyordu.)
2. **Fazla tahmin, orta olasılık bölgesi:** havuzlanmış ortalama tahmin %0,786,
   gerçekleşen oran %0,648. %2–5 kovasında tahmin %3,11'e karşı gerçekleşen
   %2,08; %5–10 kovasında %6,96'ya karşı %4,71; 10–20 kovasında %13,7'ye karşı
   %10,7.
3. **2025–26 LSS en düşük (0,163):** bu fold'da iklim LL'si de düşük (0,0298).
   Fold'lar arası değişkenlik belirgin (0,163 … 0,342).

**V1 hattının kararlılığı:** her fold ve her λ'da yakınsama sağlandı; seçim
bütün fold'larda aynı λ; çözücüler yakınsadıkları yerde aynı sonucu veriyor.

---

# Ek A — solver-corrected V1 reference benchmark (tam çıktı)


Evren: `v2_evren.gelistirme_kayitlari` — 273417 ızgara satırı, 272235 onset satırı, 1916 Y=1. Değişkenler: spread, spread_egilim_3, saat, ruzgar_kuzey, gorus. L2 ızgarası: 0.1, 1, 10, 100, 1000, 10000. Eşitlik toleransı 0.0001 nat. V2 eğitilmedi.

## 1. Fold sayımları (ambargo sonrası gerçek eğitim)

| dış fold (test) | eğitim yılları | eğitim (ambargo öncesi) | ambargo çıkan | ambargo çıkan Y=1 | eğitim (gerçek) | eğitim Y=1 | eğitim olayı | test | test Y=1 | test olayı |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2017–18 | 2011–2016 | 103806 | 6 | 0 | 103800 | 825 | 129 | 34760 | 274 | 40 |
| 2019–20 | 2011–2018 | 138566 | 6 | 0 | 138560 | 1099 | 169 | 34010 | 166 | 26 |
| 2021–22 | 2011–2020 | 172576 | 6 | 0 | 172570 | 1265 | 195 | 34786 | 364 | 51 |
| 2023–24 | 2011–2022 | 207362 | 6 | 0 | 207356 | 1629 | 246 | 34964 | 131 | 19 |
| 2025–26 | 2011–2024 | 242326 | 6 | 0 | 242320 | 1760 | 265 | 29909 | 156 | 24 |
| 2015–16 (tanılama) | 2011–2014 | 69191 | 6 | 0 | 69185 | 464 | 71 | 34615 | 361 | 58 |

Olay sayıları §5.1 bölütlemesiyle, ilgili dönemin tam (onset filtresiz) ızgara kaydından. Eğitim olayı ambargo öncesi eğitim yıllarından.

## 2. İç içe zaman bölmeli L2 seçimi (§6)

### 2017–18

İç bloklar: 2014 (iç eğitim 51833 / Y=1 325, doğrulama 17352 / Y=1 139); 2015 (iç eğitim 69185 / Y=1 464, doğrulama 17223 / Y=1 216); 2016 (iç eğitim 86411 / Y=1 677, doğrulama 17386 / Y=1 145)

| λ | havuzlanmış iç LL (nat) | en iyiden fark | ≤ 1e-4 (eşit) | eleme nedeni |  |
|---|---:|---:|---:|---:|---:|
| 0.1 | 0.038055 | 1.66e-04 | hayır |  |  |
| 1 | 0.038047 | 1.59e-04 | hayır |  |  |
| 10 | 0.037986 | 9.77e-05 | evet |  |  |
| 100 | 0.037889 | 0.00e+00 | evet |  | **seçildi** |
| 1000 | 0.039830 | 1.94e-03 | hayır |  |  |
| 10000 | 0.048944 | 1.11e-02 | hayır |  |  |

En küçük havuzlanmış LL: λ=100. 1e-4 nat içinde eşit sayılanlar: {10, 100} → en büyüğü seçildi: λ=100.

### 2019–20

İç bloklar: 2014 (iç eğitim 51833 / Y=1 325, doğrulama 17352 / Y=1 139); 2015 (iç eğitim 69185 / Y=1 464, doğrulama 17223 / Y=1 216); 2016 (iç eğitim 86411 / Y=1 677, doğrulama 17392 / Y=1 145); 2017 (iç eğitim 103800 / Y=1 825, doğrulama 17337 / Y=1 157); 2018 (iç eğitim 121137 / Y=1 982, doğrulama 17417 / Y=1 117)

| λ | havuzlanmış iç LL (nat) | en iyiden fark | ≤ 1e-4 (eşit) | eleme nedeni |  |
|---|---:|---:|---:|---:|---:|
| 0.1 | 0.034888 | 2.76e-05 | evet |  |  |
| 1 | 0.034885 | 2.43e-05 | evet |  |  |
| 10 | 0.034861 | 0.00e+00 | evet |  |  |
| 100 | 0.034910 | 4.91e-05 | evet |  | **seçildi** |
| 1000 | 0.036693 | 1.83e-03 | hayır |  |  |
| 10000 | 0.044955 | 1.01e-02 | hayır |  |  |

En küçük havuzlanmış LL: λ=10. 1e-4 nat içinde eşit sayılanlar: {0.1, 1, 10, 100} → en büyüğü seçildi: λ=100.

### 2021–22

İç bloklar: 2014 (iç eğitim 51833 / Y=1 325, doğrulama 17352 / Y=1 139); 2015 (iç eğitim 69185 / Y=1 464, doğrulama 17223 / Y=1 216); 2016 (iç eğitim 86411 / Y=1 677, doğrulama 17392 / Y=1 145); 2017 (iç eğitim 103800 / Y=1 825, doğrulama 17337 / Y=1 157); 2018 (iç eğitim 121137 / Y=1 982, doğrulama 17423 / Y=1 117); 2019 (iç eğitim 138560 / Y=1 1099, doğrulama 17450 / Y=1 112); 2020 (iç eğitim 156010 / Y=1 1211, doğrulama 16554 / Y=1 54)

| λ | havuzlanmış iç LL (nat) | en iyiden fark | ≤ 1e-4 (eşit) | eleme nedeni |  |
|---|---:|---:|---:|---:|---:|
| 0.1 | 0.030543 | 1.62e-05 | evet |  |  |
| 1 | 0.030541 | 1.42e-05 | evet |  |  |
| 10 | 0.030527 | 0.00e+00 | evet |  |  |
| 100 | 0.030597 | 7.02e-05 | evet |  | **seçildi** |
| 1000 | 0.032181 | 1.65e-03 | hayır |  |  |
| 10000 | 0.039573 | 9.05e-03 | hayır |  |  |

En küçük havuzlanmış LL: λ=10. 1e-4 nat içinde eşit sayılanlar: {0.1, 1, 10, 100} → en büyüğü seçildi: λ=100.

### 2023–24

İç bloklar: 2014 (iç eğitim 51833 / Y=1 325, doğrulama 17352 / Y=1 139); 2015 (iç eğitim 69185 / Y=1 464, doğrulama 17223 / Y=1 216); 2016 (iç eğitim 86411 / Y=1 677, doğrulama 17392 / Y=1 145); 2017 (iç eğitim 103800 / Y=1 825, doğrulama 17337 / Y=1 157); 2018 (iç eğitim 121137 / Y=1 982, doğrulama 17423 / Y=1 117); 2019 (iç eğitim 138560 / Y=1 1099, doğrulama 17450 / Y=1 112); 2020 (iç eğitim 156010 / Y=1 1211, doğrulama 16560 / Y=1 54); 2021 (iç eğitim 172570 / Y=1 1265, doğrulama 17412 / Y=1 124); 2022 (iç eğitim 189982 / Y=1 1389, doğrulama 17368 / Y=1 240)

| λ | havuzlanmış iç LL (nat) | en iyiden fark | ≤ 1e-4 (eşit) | eleme nedeni |  |
|---|---:|---:|---:|---:|---:|
| 0.1 | 0.033280 | 1.83e-05 | evet |  |  |
| 1 | 0.033278 | 1.61e-05 | evet |  |  |
| 10 | 0.033262 | 0.00e+00 | evet |  |  |
| 100 | 0.033279 | 1.71e-05 | evet |  | **seçildi** |
| 1000 | 0.034459 | 1.20e-03 | hayır |  |  |
| 10000 | 0.041330 | 8.07e-03 | hayır |  |  |

En küçük havuzlanmış LL: λ=10. 1e-4 nat içinde eşit sayılanlar: {0.1, 1, 10, 100} → en büyüğü seçildi: λ=100.

### 2025–26

İç bloklar: 2014 (iç eğitim 51833 / Y=1 325, doğrulama 17352 / Y=1 139); 2015 (iç eğitim 69185 / Y=1 464, doğrulama 17223 / Y=1 216); 2016 (iç eğitim 86411 / Y=1 677, doğrulama 17392 / Y=1 145); 2017 (iç eğitim 103800 / Y=1 825, doğrulama 17337 / Y=1 157); 2018 (iç eğitim 121137 / Y=1 982, doğrulama 17423 / Y=1 117); 2019 (iç eğitim 138560 / Y=1 1099, doğrulama 17450 / Y=1 112); 2020 (iç eğitim 156010 / Y=1 1211, doğrulama 16560 / Y=1 54); 2021 (iç eğitim 172570 / Y=1 1265, doğrulama 17412 / Y=1 124); 2022 (iç eğitim 189982 / Y=1 1389, doğrulama 17374 / Y=1 240); 2023 (iç eğitim 207356 / Y=1 1629, doğrulama 17459 / Y=1 73); 2024 (iç eğitim 224815 / Y=1 1702, doğrulama 17499 / Y=1 58)

| λ | havuzlanmış iç LL (nat) | en iyiden fark | ≤ 1e-4 (eşit) | eleme nedeni |  |
|---|---:|---:|---:|---:|---:|
| 0.1 | 0.030573 | 1.52e-05 | evet |  |  |
| 1 | 0.030571 | 1.34e-05 | evet |  |  |
| 10 | 0.030558 | 0.00e+00 | evet |  |  |
| 100 | 0.030573 | 1.50e-05 | evet |  | **seçildi** |
| 1000 | 0.031596 | 1.04e-03 | hayır |  |  |
| 10000 | 0.037675 | 7.12e-03 | hayır |  |  |

En küçük havuzlanmış LL: λ=10. 1e-4 nat içinde eşit sayılanlar: {0.1, 1, 10, 100} → en büyüğü seçildi: λ=100.

### 2015–16 (tanılama)

İç bloklar: 2014 (iç eğitim 51833 / Y=1 325, doğrulama 17346 / Y=1 139)

| λ | havuzlanmış iç LL (nat) | en iyiden fark | ≤ 1e-4 (eşit) | eleme nedeni |  |
|---|---:|---:|---:|---:|---:|
| 0.1 | 0.034414 | 4.58e-04 | hayır |  |  |
| 1 | 0.034397 | 4.41e-04 | hayır |  |  |
| 10 | 0.034269 | 3.13e-04 | hayır |  |  |
| 100 | 0.033956 | 0.00e+00 | evet |  | **seçildi** |
| 1000 | 0.035687 | 1.73e-03 | hayır |  |  |
| 10000 | 0.043220 | 9.26e-03 | hayır |  |  |

En küçük havuzlanmış LL: λ=100. 1e-4 nat içinde eşit sayılanlar: {100} → en büyüğü seçildi: λ=100.

## 3. Test sonuçları — birincil tam onset evreni

| kesit | satır | Y=1 | LL (nat) | LL iklim | LSS | Brier×10⁴ | AP | taban % | ort. tahmin % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2017–18 (λ=100) | 34760 | 274 | 0.03055 | 0.04355 | 0.2984 | 66.06 | 0.278 | 0.788 | 0.987 |
| 2019–20 (λ=100) | 34010 | 166 | 0.01969 | 0.02994 | 0.3421 | 41.56 | 0.244 | 0.488 | 0.800 |
| 2021–22 (λ=100) | 34786 | 364 | 0.04255 | 0.06256 | 0.3199 | 92.20 | 0.192 | 1.046 | 0.887 |
| 2023–24 (λ=100) | 34964 | 131 | 0.01856 | 0.02523 | 0.2640 | 36.05 | 0.128 | 0.375 | 0.706 |
| 2025–26 (λ=100) | 29909 | 156 | 0.02493 | 0.02980 | 0.1634 | 47.00 | 0.174 | 0.522 | 0.514 |
| **havuzlanmış (5 fold OOS birleşimi)** | 168429 | 1091 | 0.02735 | 0.03848 | 0.2892 | 56.90 | 0.197 | 0.648 | 0.786 |

LSS = 1 − LL(V1) / LL(iklim); iklim = her fold'un yalnızca kendi ambargolu eğitim satırlarından kurulan ay × saat taban oranı (`model.iklim_baseline`). Havuzlanmış LSS = 1 − ΣLL(V1)/ΣLL(iklim), yani birleşik tahminlerden.

Erken dönem tanılaması (birincil karara girmez):

| kesit | satır | Y=1 | LL (nat) | LL iklim | LSS | Brier×10⁴ | AP | taban % | ort. tahmin % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015–16 (λ=100) | 34615 | 361 | 0.04007 | 0.06142 | 0.3476 | 90.98 | 0.222 | 1.043 | 0.752 |

## 4. Katsayılar (fold başına, V1 referansı)

| fold | λ | sabit | gorus | ruzgar_kuzey | saat | spread | spread_egilim_3 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2017–18 | 100 | -4.769 | 0.675 | 0.372 | 0.436 | 0.546 | 0.010 |
| 2019–20 | 100 | -4.814 | 0.694 | 0.441 | 0.477 | 0.534 | 0.027 |
| 2021–22 | 100 | -4.879 | 0.675 | 0.449 | 0.466 | 0.509 | 0.023 |
| 2023–24 | 100 | -4.828 | 0.684 | 0.474 | 0.437 | 0.566 | -0.109 |
| 2025–26 | 100 | -4.914 | 0.691 | 0.478 | 0.443 | 0.565 | -0.100 |
| 2015–16 | 100 | -4.898 | 0.648 | 0.335 | 0.358 | 0.526 | 0.110 |

WoE kova sayısı: 2017–18: gorus 11, ruzgar_kuzey 8, saat 8, spread 8, spread_egilim_3 7; 2019–20: gorus 11, ruzgar_kuzey 8, saat 8, spread 7, spread_egilim_3 7; 2021–22: gorus 11, ruzgar_kuzey 8, saat 8, spread 8, spread_egilim_3 7; 2023–24: gorus 11, ruzgar_kuzey 8, saat 8, spread 8, spread_egilim_3 7; 2025–26: gorus 10, ruzgar_kuzey 8, saat 8, spread 8, spread_egilim_3 7; 2015–16: gorus 9, ruzgar_kuzey 8, saat 8, spread 8, spread_egilim_3 7

## 5. Önceden bildirilmiş tanılama — ufku tam (6/6) satırlar (karar vermez)

Aynı OOS tahminler; V1 yeniden eğitilmedi. Seçim Y'ye bakılmadan, yalnız ufuk tamlığına göre (Deney 0 raporu §7.2).

| kesit | satır | Y=1 | LL (nat) | LL iklim | LSS | Brier×10⁴ | AP | taban % | ort. tahmin % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2017–18 | 34560 | 254 | 0.02908 | 0.04117 | 0.2938 | 62.05 | 0.268 | 0.735 | 0.978 |
| 2019–20 | 33865 | 166 | 0.01970 | 0.03002 | 0.3440 | 41.60 | 0.248 | 0.490 | 0.796 |
| 2021–22 | 34737 | 364 | 0.04260 | 0.06264 | 0.3199 | 92.33 | 0.192 | 1.048 | 0.888 |
| 2023–24 | 34896 | 131 | 0.01859 | 0.02527 | 0.2642 | 36.11 | 0.128 | 0.375 | 0.706 |
| 2025–26 | 29842 | 156 | 0.02497 | 0.02985 | 0.1635 | 47.09 | 0.174 | 0.523 | 0.513 |
| **havuzlanmış 6/6** | 167900 | 1071 | 0.02707 | 0.03805 | 0.2884 | 56.14 | 0.195 | 0.638 | 0.784 |
| havuzlanmış, ufku eksik (tümleyen) | 529 | 20 | 0.11504 | 0.17586 | 0.3459 | 296.46 | 0.472 | 3.781 | 1.623 |

Tüm geliştirme evreninde 6/6 onset satırı: 269160.

## 6. SN tanılamaları (§9.3; karar vermez)

Satır düzeyi: hedef penceresinde (t, t+3sa] hiç SN gözlemi olmayan / olan satırlar.

| kesit | satır | Y=1 | LL (nat) | LL iklim | LSS | Brier×10⁴ | AP | taban % | ort. tahmin % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| penceresinde SN yok | 165479 | 754 | 0.01922 | 0.02808 | 0.3157 | 39.50 | 0.221 | 0.456 | 0.734 |
| penceresinde SN var | 2950 | 337 | 0.48343 | 0.62161 | 0.2223 | 1032.45 | 0.224 | 11.424 | 3.739 |

Olay düzeyi (§9.1 yakalama tanımı; bant eşiği = 5 × dondurulmuş V1 taban oranı = 3.785%; ilk alarm süresi yakalanmayan olayda 0 dk). Olaylar her fold'un test döneminde bölütlendi; penceresinde hiç OOS tahmin satırı olmayan olay değerlendirilemez ve ayrı sayılır.

| fold | olay grubu | olay | değerlendirilemez | değerlendirilen | yakalanan | medyan ilk alarm (dk) |
|---|---:|---:|---:|---:|---:|---:|
| 2017–18 | tümü | 40 | 0 | 40 | 37 (%92.5) | 120 |
| 2019–20 | tümü | 26 | 0 | 26 | 25 (%96.2) | 180 |
| 2021–22 | tümü | 51 | 0 | 51 | 45 (%88.2) | 120 |
| 2023–24 | tümü | 19 | 0 | 19 | 17 (%89.5) | 150 |
| 2025–26 | tümü | 24 | 0 | 24 | 19 (%79.2) | 90 |
| **havuzlanmış** | tümü | 160 | 0 | 160 | 143 (%89.4) | 120 |
| **havuzlanmış** | ≥ 1 SN | 42 | 0 | 42 | 32 (%76.2) | 120 |
| **havuzlanmış** | SN'siz | 118 | 0 | 118 | 111 (%94.1) | 150 |

## 7. Güvenilirlik (havuzlanmış OOS, tanılama)

| tahmin kovası | satır | ort. tahmin % | gerçekleşen % | Y=1 |
|---|---:|---:|---:|---:|
| 0.0–0.1 | 166262 | 0.525 | 0.399 | 663 |
| 0.1–0.2 | 1341 | 13.684 | 10.664 | 143 |
| 0.2–0.3 | 431 | 24.593 | 24.826 | 107 |
| 0.3–0.4 | 215 | 34.609 | 40.930 | 88 |
| 0.4–0.5 | 136 | 45.139 | 49.265 | 67 |
| 0.5–0.6 | 34 | 55.496 | 50.000 | 17 |
| 0.6–0.7 | 10 | 62.661 | 60.000 | 6 |

Düşük olasılık bölgesi (tahmin %):

| tahmin % | satır | ort. tahmin % | gerçekleşen % | Y=1 |
|---|---:|---:|---:|---:|
| < 0,5 | 128769 | 0.115 | 0.092 | 118 |
| 0,5–1 | 16321 | 0.713 | 0.625 | 102 |
| 1–2 | 10644 | 1.424 | 1.268 | 135 |
| 2–5 | 7133 | 3.111 | 2.075 | 148 |
| 5–10 | 3395 | 6.958 | 4.713 | 160 |
| ≥ 10 | 2167 | 20.786 | 19.751 | 428 |

## 8. Çözücü etkisi — `irls_eski` (eski) ile `sonumlu` (yeni)

ΔLL_çözücü = LL(eski) − LL(yeni); pozitif = yeni çözücüyle V1 referansı daha iyi. Yalnızca çözücü düzeltmesinin V1 benchmark'ına etkisidir; V2 karşılaştırmasındaki birincil ΔLL ile karıştırılmamalıdır.

| fold | eski λ | yeni λ | eski LL | yeni LL | ΔLL_çözücü | eski AP | yeni AP | eski LSS | yeni LSS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2017–18 | 100 | 100 | 0.03055 | 0.03055 | -0.00000 | 0.278 | 0.278 | 0.2984 | 0.2984 |
| 2019–20 | 100 | 100 | 0.01969 | 0.01969 | -0.00000 | 0.244 | 0.244 | 0.3421 | 0.3421 |
| 2021–22 | 100 | 100 | 0.04255 | 0.04255 | +0.00000 | 0.192 | 0.192 | 0.3199 | 0.3199 |
| 2023–24 | 1000 | 100 | 0.01889 | 0.01856 | +0.00033 | 0.119 | 0.128 | 0.2511 | 0.2640 |
| 2025–26 | 1000 | 100 | 0.02490 | 0.02493 | -0.00002 | 0.179 | 0.174 | 0.1642 | 0.1634 |
| 2015–16 (tanılama) | 100 | 100 | 0.04007 | 0.04007 | +0.00000 | 0.222 | 0.222 | 0.3476 | 0.3476 |
| **havuzlanmış (5 fold)** |  |  | 0.02741 | 0.02735 | +0.00006 | 0.197 | 0.197 | 0.2876 | 0.2892 |

Eski çalışmada elenen λ'lar: 2017–18: 0.1 (2016: Yakinsamadi), 1 (2016: Yakinsamadi); 2019–20: 0.1 (2016: Yakinsamadi), 1 (2016: Yakinsamadi); 2021–22: 0.1 (2016: Yakinsamadi), 1 (2016: Yakinsamadi), 10 (2019: Yakinsamadi); 2023–24: 0.1 (2016: Yakinsamadi), 1 (2016: Yakinsamadi), 10 (2019: Yakinsamadi), 100 (2022: Yakinsamadi); 2025–26: 0.1 (2016: Yakinsamadi), 1 (2016: Yakinsamadi), 10 (2019: Yakinsamadi), 100 (2022: Yakinsamadi); 2015–16: yok

Yeni çalışmada elenen λ'lar: 2017–18: yok; 2019–20: yok; 2021–22: yok; 2023–24: yok; 2025–26: yok; 2015–16: yok


# Ek B — pre-fix diagnostic run (tam çıktı, değiştirilmeden; nihai benchmark değildir)

Çözücü: `model.egit` (eski IRLS). Yeniden üretmek için: `python -m sis_modeli.v1_benchmark --cozucu irls_eski --karsilastirma yok`.


Evren: `v2_evren.gelistirme_kayitlari` — 273417 ızgara satırı, 272235 onset satırı, 1916 Y=1. Değişkenler: spread, spread_egilim_3, saat, ruzgar_kuzey, gorus. L2 ızgarası: 0.1, 1, 10, 100, 1000, 10000. Eşitlik toleransı 0.0001 nat. V2 eğitilmedi.

## 1. Fold sayımları (ambargo sonrası gerçek eğitim)

| dış fold (test) | eğitim yılları | eğitim (ambargo öncesi) | ambargo çıkan | ambargo çıkan Y=1 | eğitim (gerçek) | eğitim Y=1 | eğitim olayı | test | test Y=1 | test olayı |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2017–18 | 2011–2016 | 103806 | 6 | 0 | 103800 | 825 | 129 | 34760 | 274 | 40 |
| 2019–20 | 2011–2018 | 138566 | 6 | 0 | 138560 | 1099 | 169 | 34010 | 166 | 26 |
| 2021–22 | 2011–2020 | 172576 | 6 | 0 | 172570 | 1265 | 195 | 34786 | 364 | 51 |
| 2023–24 | 2011–2022 | 207362 | 6 | 0 | 207356 | 1629 | 246 | 34964 | 131 | 19 |
| 2025–26 | 2011–2024 | 242326 | 6 | 0 | 242320 | 1760 | 265 | 29909 | 156 | 24 |
| 2015–16 (tanılama) | 2011–2014 | 69191 | 6 | 0 | 69185 | 464 | 71 | 34615 | 361 | 58 |

Olay sayıları §5.1 bölütlemesiyle, ilgili dönemin tam (onset filtresiz) ızgara kaydından. Eğitim olayı ambargo öncesi eğitim yıllarından.

## 2. İç içe zaman bölmeli L2 seçimi (§6)

### 2017–18

İç bloklar: 2014 (iç eğitim 51833 / Y=1 325, doğrulama 17352 / Y=1 139); 2015 (iç eğitim 69185 / Y=1 464, doğrulama 17223 / Y=1 216); 2016 (iç eğitim 86411 / Y=1 677, doğrulama 17386 / Y=1 145)

| λ | havuzlanmış iç LL (nat) | en iyiden fark | eleme nedeni |  |
|---|---:|---:|---:|---:|
| 0.1 | elendi | — | 2016: Yakinsamadi |  |
| 1 | elendi | — | 2016: Yakinsamadi |  |
| 10 | 0.037986 | 9.77e-05 |  |  |
| 100 | 0.037889 | 0.00e+00 |  | **seçildi** |
| 1000 | 0.039830 | 1.94e-03 |  |  |
| 10000 | 0.048944 | 1.11e-02 |  |  |

### 2019–20

İç bloklar: 2014 (iç eğitim 51833 / Y=1 325, doğrulama 17352 / Y=1 139); 2015 (iç eğitim 69185 / Y=1 464, doğrulama 17223 / Y=1 216); 2016 (iç eğitim 86411 / Y=1 677, doğrulama 17392 / Y=1 145); 2017 (iç eğitim 103800 / Y=1 825, doğrulama 17337 / Y=1 157); 2018 (iç eğitim 121137 / Y=1 982, doğrulama 17417 / Y=1 117)

| λ | havuzlanmış iç LL (nat) | en iyiden fark | eleme nedeni |  |
|---|---:|---:|---:|---:|
| 0.1 | elendi | — | 2016: Yakinsamadi |  |
| 1 | elendi | — | 2016: Yakinsamadi |  |
| 10 | 0.034861 | 0.00e+00 |  |  |
| 100 | 0.034910 | 4.91e-05 |  | **seçildi** |
| 1000 | 0.036693 | 1.83e-03 |  |  |
| 10000 | 0.044955 | 1.01e-02 |  |  |

### 2021–22

İç bloklar: 2014 (iç eğitim 51833 / Y=1 325, doğrulama 17352 / Y=1 139); 2015 (iç eğitim 69185 / Y=1 464, doğrulama 17223 / Y=1 216); 2016 (iç eğitim 86411 / Y=1 677, doğrulama 17392 / Y=1 145); 2017 (iç eğitim 103800 / Y=1 825, doğrulama 17337 / Y=1 157); 2018 (iç eğitim 121137 / Y=1 982, doğrulama 17423 / Y=1 117); 2019 (iç eğitim 138560 / Y=1 1099, doğrulama 17450 / Y=1 112); 2020 (iç eğitim 156010 / Y=1 1211, doğrulama 16554 / Y=1 54)

| λ | havuzlanmış iç LL (nat) | en iyiden fark | eleme nedeni |  |
|---|---:|---:|---:|---:|
| 0.1 | elendi | — | 2016: Yakinsamadi |  |
| 1 | elendi | — | 2016: Yakinsamadi |  |
| 10 | elendi | — | 2019: Yakinsamadi |  |
| 100 | 0.030597 | 0.00e+00 |  | **seçildi** |
| 1000 | 0.032181 | 1.58e-03 |  |  |
| 10000 | 0.039573 | 8.98e-03 |  |  |

### 2023–24

İç bloklar: 2014 (iç eğitim 51833 / Y=1 325, doğrulama 17352 / Y=1 139); 2015 (iç eğitim 69185 / Y=1 464, doğrulama 17223 / Y=1 216); 2016 (iç eğitim 86411 / Y=1 677, doğrulama 17392 / Y=1 145); 2017 (iç eğitim 103800 / Y=1 825, doğrulama 17337 / Y=1 157); 2018 (iç eğitim 121137 / Y=1 982, doğrulama 17423 / Y=1 117); 2019 (iç eğitim 138560 / Y=1 1099, doğrulama 17450 / Y=1 112); 2020 (iç eğitim 156010 / Y=1 1211, doğrulama 16560 / Y=1 54); 2021 (iç eğitim 172570 / Y=1 1265, doğrulama 17412 / Y=1 124); 2022 (iç eğitim 189982 / Y=1 1389, doğrulama 17368 / Y=1 240)

| λ | havuzlanmış iç LL (nat) | en iyiden fark | eleme nedeni |  |
|---|---:|---:|---:|---:|
| 0.1 | elendi | — | 2016: Yakinsamadi |  |
| 1 | elendi | — | 2016: Yakinsamadi |  |
| 10 | elendi | — | 2019: Yakinsamadi |  |
| 100 | elendi | — | 2022: Yakinsamadi |  |
| 1000 | 0.034459 | 0.00e+00 |  | **seçildi** |
| 10000 | 0.041330 | 6.87e-03 |  |  |

### 2025–26

İç bloklar: 2014 (iç eğitim 51833 / Y=1 325, doğrulama 17352 / Y=1 139); 2015 (iç eğitim 69185 / Y=1 464, doğrulama 17223 / Y=1 216); 2016 (iç eğitim 86411 / Y=1 677, doğrulama 17392 / Y=1 145); 2017 (iç eğitim 103800 / Y=1 825, doğrulama 17337 / Y=1 157); 2018 (iç eğitim 121137 / Y=1 982, doğrulama 17423 / Y=1 117); 2019 (iç eğitim 138560 / Y=1 1099, doğrulama 17450 / Y=1 112); 2020 (iç eğitim 156010 / Y=1 1211, doğrulama 16560 / Y=1 54); 2021 (iç eğitim 172570 / Y=1 1265, doğrulama 17412 / Y=1 124); 2022 (iç eğitim 189982 / Y=1 1389, doğrulama 17374 / Y=1 240); 2023 (iç eğitim 207356 / Y=1 1629, doğrulama 17459 / Y=1 73); 2024 (iç eğitim 224815 / Y=1 1702, doğrulama 17499 / Y=1 58)

| λ | havuzlanmış iç LL (nat) | en iyiden fark | eleme nedeni |  |
|---|---:|---:|---:|---:|
| 0.1 | elendi | — | 2016: Yakinsamadi |  |
| 1 | elendi | — | 2016: Yakinsamadi |  |
| 10 | elendi | — | 2019: Yakinsamadi |  |
| 100 | elendi | — | 2022: Yakinsamadi |  |
| 1000 | 0.031596 | 0.00e+00 |  | **seçildi** |
| 10000 | 0.037675 | 6.08e-03 |  |  |

### 2015–16 (tanılama)

İç bloklar: 2014 (iç eğitim 51833 / Y=1 325, doğrulama 17346 / Y=1 139)

| λ | havuzlanmış iç LL (nat) | en iyiden fark | eleme nedeni |  |
|---|---:|---:|---:|---:|
| 0.1 | 0.034414 | 4.58e-04 |  |  |
| 1 | 0.034397 | 4.41e-04 |  |  |
| 10 | 0.034269 | 3.13e-04 |  |  |
| 100 | 0.033956 | 0.00e+00 |  | **seçildi** |
| 1000 | 0.035687 | 1.73e-03 |  |  |
| 10000 | 0.043220 | 9.26e-03 |  |  |

## 3. Test sonuçları — birincil tam onset evreni

| kesit | satır | Y=1 | LL (nat) | LL iklim | LSS | Brier×10⁴ | AP | taban % | ort. tahmin % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2017–18 (λ=100) | 34760 | 274 | 0.03055 | 0.04355 | 0.2984 | 66.06 | 0.278 | 0.788 | 0.987 |
| 2019–20 (λ=100) | 34010 | 166 | 0.01969 | 0.02994 | 0.3421 | 41.56 | 0.244 | 0.488 | 0.800 |
| 2021–22 (λ=100) | 34786 | 364 | 0.04255 | 0.06256 | 0.3199 | 92.20 | 0.192 | 1.046 | 0.887 |
| 2023–24 (λ=1000) | 34964 | 131 | 0.01889 | 0.02523 | 0.2511 | 35.60 | 0.119 | 0.375 | 0.714 |
| 2025–26 (λ=1000) | 29909 | 156 | 0.02490 | 0.02980 | 0.1642 | 47.33 | 0.179 | 0.522 | 0.537 |
| **havuzlanmış (5 fold OOS birleşimi)** | 168429 | 1091 | 0.02741 | 0.03848 | 0.2876 | 56.86 | 0.197 | 0.648 | 0.792 |

LSS = 1 − LL(V1) / LL(iklim); iklim = her fold'un yalnızca kendi ambargolu eğitim satırlarından kurulan ay × saat taban oranı (`model.iklim_baseline`). Havuzlanmış LSS = 1 − ΣLL(V1)/ΣLL(iklim), yani birleşik tahminlerden.

Erken dönem tanılaması (birincil karara girmez):

| kesit | satır | Y=1 | LL (nat) | LL iklim | LSS | Brier×10⁴ | AP | taban % | ort. tahmin % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015–16 (λ=100) | 34615 | 361 | 0.04007 | 0.06142 | 0.3476 | 90.98 | 0.222 | 1.043 | 0.752 |

## 4. Katsayılar (fold başına, V1 referansı)

| fold | λ | sabit | gorus | ruzgar_kuzey | saat | spread | spread_egilim_3 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2017–18 | 100 | -4.769 | 0.675 | 0.372 | 0.436 | 0.546 | 0.010 |
| 2019–20 | 100 | -4.814 | 0.694 | 0.441 | 0.477 | 0.534 | 0.027 |
| 2021–22 | 100 | -4.879 | 0.675 | 0.449 | 0.466 | 0.509 | 0.023 |
| 2023–24 | 1000 | -4.610 | 0.602 | 0.206 | 0.237 | 0.475 | 0.035 |
| 2025–26 | 1000 | -4.699 | 0.613 | 0.209 | 0.249 | 0.475 | 0.038 |
| 2015–16 | 100 | -4.898 | 0.648 | 0.335 | 0.358 | 0.526 | 0.110 |

WoE kova sayısı: 2017–18: gorus 11, ruzgar_kuzey 8, saat 8, spread 8, spread_egilim_3 7; 2019–20: gorus 11, ruzgar_kuzey 8, saat 8, spread 7, spread_egilim_3 7; 2021–22: gorus 11, ruzgar_kuzey 8, saat 8, spread 8, spread_egilim_3 7; 2023–24: gorus 11, ruzgar_kuzey 8, saat 8, spread 8, spread_egilim_3 7; 2025–26: gorus 10, ruzgar_kuzey 8, saat 8, spread 8, spread_egilim_3 7; 2015–16: gorus 9, ruzgar_kuzey 8, saat 8, spread 8, spread_egilim_3 7

## 5. Önceden bildirilmiş tanılama — ufku tam (6/6) satırlar (karar vermez)

Aynı OOS tahminler; V1 yeniden eğitilmedi. Seçim Y'ye bakılmadan, yalnız ufuk tamlığına göre (Deney 0 raporu §7.2).

| kesit | satır | Y=1 | LL (nat) | LL iklim | LSS | Brier×10⁴ | AP | taban % | ort. tahmin % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2017–18 | 34560 | 254 | 0.02908 | 0.04117 | 0.2938 | 62.05 | 0.268 | 0.735 | 0.978 |
| 2019–20 | 33865 | 166 | 0.01970 | 0.03002 | 0.3440 | 41.60 | 0.248 | 0.490 | 0.796 |
| 2021–22 | 34737 | 364 | 0.04260 | 0.06264 | 0.3199 | 92.33 | 0.192 | 1.048 | 0.888 |
| 2023–24 | 34896 | 131 | 0.01892 | 0.02527 | 0.2514 | 35.66 | 0.119 | 0.375 | 0.714 |
| 2025–26 | 29842 | 156 | 0.02494 | 0.02985 | 0.1642 | 47.43 | 0.179 | 0.523 | 0.537 |
| **havuzlanmış 6/6** | 167900 | 1071 | 0.02714 | 0.03805 | 0.2868 | 56.11 | 0.195 | 0.638 | 0.789 |
| havuzlanmış, ufku eksik (tümleyen) | 529 | 20 | 0.11522 | 0.17586 | 0.3448 | 296.40 | 0.471 | 3.781 | 1.642 |

Tüm geliştirme evreninde 6/6 onset satırı: 269160.

## 6. SN tanılamaları (§9.3; karar vermez)

Satır düzeyi: hedef penceresinde (t, t+3sa] hiç SN gözlemi olmayan / olan satırlar.

| kesit | satır | Y=1 | LL (nat) | LL iklim | LSS | Brier×10⁴ | AP | taban % | ort. tahmin % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| penceresinde SN yok | 165479 | 754 | 0.01942 | 0.02808 | 0.3085 | 39.52 | 0.218 | 0.456 | 0.740 |
| penceresinde SN var | 2950 | 337 | 0.47582 | 0.62161 | 0.2345 | 1029.44 | 0.230 | 11.424 | 3.688 |

Olay düzeyi (§9.1 yakalama tanımı; bant eşiği = 5 × dondurulmuş V1 taban oranı = 3.785%; ilk alarm süresi yakalanmayan olayda 0 dk). Olaylar her fold'un test döneminde bölütlendi; penceresinde hiç OOS tahmin satırı olmayan olay değerlendirilemez ve ayrı sayılır.

| fold | olay grubu | olay | değerlendirilemez | değerlendirilen | yakalanan | medyan ilk alarm (dk) |
|---|---:|---:|---:|---:|---:|---:|
| 2017–18 | tümü | 40 | 0 | 40 | 37 (%92.5) | 120 |
| 2019–20 | tümü | 26 | 0 | 26 | 25 (%96.2) | 180 |
| 2021–22 | tümü | 51 | 0 | 51 | 45 (%88.2) | 120 |
| 2023–24 | tümü | 19 | 0 | 19 | 16 (%84.2) | 150 |
| 2025–26 | tümü | 24 | 0 | 24 | 18 (%75.0) | 90 |
| **havuzlanmış** | tümü | 160 | 0 | 160 | 141 (%88.1) | 120 |
| **havuzlanmış** | ≥ 1 SN | 42 | 0 | 42 | 31 (%73.8) | 120 |
| **havuzlanmış** | SN'siz | 118 | 0 | 118 | 110 (%93.2) | 150 |

## 7. Güvenilirlik (havuzlanmış OOS, tanılama)

| tahmin kovası | satır | ort. tahmin % | gerçekleşen % | Y=1 |
|---|---:|---:|---:|---:|
| 0.0–0.1 | 166397 | 0.553 | 0.403 | 671 |
| 0.1–0.2 | 1266 | 13.603 | 11.690 | 148 |
| 0.2–0.3 | 425 | 24.595 | 25.882 | 110 |
| 0.3–0.4 | 195 | 34.628 | 45.641 | 89 |
| 0.4–0.5 | 115 | 44.999 | 50.435 | 58 |
| 0.5–0.6 | 22 | 55.239 | 45.455 | 10 |
| 0.6–0.7 | 9 | 62.913 | 55.556 | 5 |

Düşük olasılık bölgesi (tahmin %):

| tahmin % | satır | ort. tahmin % | gerçekleşen % | Y=1 |
|---|---:|---:|---:|---:|
| < 0,5 | 126098 | 0.129 | 0.081 | 102 |
| 0,5–1 | 17946 | 0.709 | 0.619 | 111 |
| 1–2 | 11354 | 1.403 | 1.215 | 138 |
| 2–5 | 7616 | 3.100 | 2.101 | 160 |
| 5–10 | 3383 | 6.949 | 4.730 | 160 |
| ≥ 10 | 2032 | 20.366 | 20.669 | 420 |
