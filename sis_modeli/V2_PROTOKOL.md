# Sis modeli V2 — deney ve değerlendirme protokolü

**Durum:** TASLAK (sürüm 0.1) — henüz dondurulmadı.
Bu belge dondurulduktan (merge edildikten) sonra karar kuralları ancak §15'teki
değişiklik denetimiyle değiştirilebilir. Deney 1'in sonuçları görüldükten sonra
karar kuralları **hiç** değiştirilemez.

---

## 1. Amaç ve terminoloji

Proje adı "sis modeli V2"dir; ancak **her teknik değerlendirmede istatistiksel
hedef "LTFJ düşük görüş/FG olayı" olarak yazılır** (bkz. `README.md`
"Hedef tanımı ve terminoloji").

```
Olay gözlemi:  Görüş < 1000 m  ∨  FG(meydanı kaplayan) = 1        (sis_modeli/ozellik.py)
Hedef:         Y_t = 1  ⟺  ∃ τ ∈ (t, t+3sa] : τ anındaki gözlem olay gözlemidir
Onset adayı:   Y^şimdi_t = 0
```

Araştırma sorusu: *Model A'nın tahmin ettiği 3 saatlik düşük görüş/FG olayının
olasılık tahmini, geçmiş görüş/spread gidişatı bilgisiyle, Model A'nın mevcut
girdilerinin ötesinde iyileştirilebilir mi?*

Sonuç raporlarında "daha iyi sis modeli" ifadesi ancak §9.3'teki SN-dışı tanılama
da aynı yönü gösteriyorsa kullanılabilir; aksi hâlde "daha iyi düşük görüş/FG
modeli" denir.

## 2. Roller

| rol | model | durum |
|---|---|---|
| şampiyon (V1) | Model A — `ltfj_sis_olasilik.py` | canlı, dondurulmuş, değişmez |
| yarışmacı (V2) | bu protokolle seçilecek tek spesifikasyon | gölge modda sınanır |
| — | Model B — `ltfj_sis_olasilik_b.py` | dondurulmuş ek gösterge; geliştirilmiyor, V2'nin öncülü değil |

V2 ancak §12'deki ileriye dönük sınavı geçerse V1'in yerine canlıya alınır.

## 3. Veri ve dönemler

- **Kaynak:** `sis_modeli/veri/ltfj_ozellik.csv.gz` (IEM METAR arşivi).
- **Geliştirme dönemi: 2011 – arşivin sonu (2026).** 2024–2026 bu protokolle
  geliştirme dönemi olarak etiketlenir. V1'in 2024–2026 sonuçları (AP 0,184,
  BSS 0,092) silinmez; **"V1'in tarihsel sınavı"** olarak kalır. Hiçbir raporda
  "V2 holdout 2024–26" ifadesi kullanılmaz.
- **V2'nin tek sınavı:** §11'deki T0 anından sonra gölge modda ileriye doğru
  biriken veri.
- **Değişkenler yalnızca :20/:50 ızgarasından hesaplanır** — eğitimde de canlıda
  da. SPECI yalnızca ileriye dönük değerlendirmede olay gözlemini (etiketi)
  belirlemek için kullanılır (§12). Ayrıca tanılama olarak etiketin yalnızca
  ızgara gözlemleriyle hesaplandığı hâli de raporlanır.

## 4. Deney 0 — veri kalitesi denetimi (model performansına bakılmaz)

1. **Gecikme eksikliği:** t−30, t−60, t−120 dk gözlemleri **tam o zamanda**
   mevcut mu (en yakın gözlem kullanılmaz). P(eksik | Y=1) ile P(eksik | Y=0),
   meteorolojik gün bootstrap'iyle; ay ve saate göre ayrıca.
   Oran [0,8; 1,25] dışında ve aralık 1'i dışlıyorsa kayda geçer (§7.4 zaten
   V1'e geri dönüş uyguladığı için model davranışı değişmez; rapora yazılır).
2. **2011 denetimi:** gözlem sayısı, görüş < 1000 m sayısı, FG-ailesi kodları,
   eksik görüş/hava alanları ve rapor biçimi 2012–2014 ile karşılaştırılır.
   Neden tahmin edilmez; kanıt ne diyorsa o yazılır.
3. **Yıllara göre SN bileşimi** (olay gözlemleri ve pozitif satırlar).
4. **Canlı arşiv bütünlüğü:** bot bir çalıştırmayı kaçırdığında aradaki METAR'ın
   `gozlem_arsivi.csv`'ye yine yazılıp yazılmadığı kod ve arşiv üzerinden
   doğrulanır. Yazılmıyorsa gölge modda gecikme eksikliği canlıda artar; bu
   §7.4 kapsama oranına yansır ve rapora yazılır.

Deney 0 raporu Deney 1'den önce yazılır ve bu protokolün eki olur.

## 5. Bölme, ambargo ve bootstrap birimleri

- **Dış fold'lar (2 yıllık test blokları):** 2017–18 · 2019–20 · 2021–22 ·
  2023–24 · 2025–26. Birincil havuzlanmış karşılaştırma yalnızca bu beş fold'dan
  yapılır.
- **2015–16** "erken dönem tanılaması" olarak ayrıca raporlanır; birincil karara
  girmez. Gerekçe performans değil: bu fold'da iç doğrulama için yalnızca bir yıl
  (2014) oluşuyor.
- **Ambargo:** her eğitim/test sınırında (dış ve iç), hedef penceresi sınırı
  aşan eğitim satırları (sınırdan önceki son 3 saat) çıkarılır
  (`bolme.embargo_penceresi`). V1 referansı da aynı ambargoyla hesaplanır.
- **Bootstrap birimleri:**
  - satır düzeyi ölçütler (LL, AP, Brier, LSS): **meteorolojik gün**
    (12 UTC – ertesi gün 12 UTC);
  - olay düzeyi ölçütler (yakalama, ilk alarm süresi): **bağımsız olay**
    (`olay_degerlendirme.bagimsiz_olaylar`, 3 saat boşluk).
  - Bu birimlerin bağımsız olduğu iddia edilmez; bağımlılığı daha iyi gruplayan
    birimlerdir.
  - Tekrar sayısı: 2000.

## 6. L2 seçimi — iç içe zaman bölmeli doğrulama

- **Izgara (dondurulmuş):** `model.L2_ADAYLARI` = (0,1; 1; 10; 100; 1000; 10000).
  Izgara sonuçlar görüldükten sonra genişletilmez.
- **İç doğrulama blokları:** her dış fold'un eğitim döneminde, en az 3 yıl
  eğitimden sonra gelen **her takvim yılı** bir iç doğrulama bloğudur
  (2017–18 fold'unda 2014, 2015, 2016; …; 2025–26 fold'unda 2014–2024). Her blok
  için iç eğitim = o yıldan önceki bütün yıllar (genişleyen pencere), ambargolu.
- **Seçim ölçütü:** her L2 için bütün iç blokların **havuzlanmış log-loss**'u;
  λ* = en küçük olan. Eşitlikte (4 anlamlı basamak) **daha büyük L2** seçilir
  (daha muhafazakâr).
- **Yakınsama:** bir L2 herhangi bir iç blokta `TekilSistem` ya da `Yakinsamadi`
  verirse o dış fold için elenir. Seçilen L2 ile dış fold'un tüm eğitim
  verisindeki eğitim yakınsamazsa o spesifikasyon **başarısız** sayılır.
- V1 referansı ve bütün V2 varyantları **aynı** prosedürle eğitilir.

## 7. Model spesifikasyonları

### 7.1 V1 referansı (geliştirme karşılaştırması için)
V1'in değişken seti (`gorus, spread, spread_egilim_3, saat, ruzgar_kuzey`), WoE +
L2 lojistik regresyon, §6 prosedürüyle her dış fold'da yeniden eğitilir. Böylece
V1–V2 farkı yalnızca değişkenlerden gelir. Dondurulmuş canlı V1'in aynı satırlardaki
skoru yalnızca **tanılama** olarak raporlanır (2011–2023 ile eğitildiği için
o yılları içeren fold'larda örnek içidir).

### 7.2 Görüş gidişatı değişkenleri (a priori)
- **İnce görüş bantları:** 1000 / 1500 / 3000 / 5000 / 8000 / 9999 m.
- **Eğilim sınıfı** (ince bant indeksindeki değişim, pencere §7.3'e göre):
  `iyileşen/sabit` (Δbant ≥ 0) · `1 bant düşüş` · `≥ 2 bant düşüş`.
  Gerekçe: metre farkı ölçeğe bağlı (10000→7000 ile 2000→1500 aynı şey değil);
  bant geçişi operasyonel eşiklerden türüyor.
- **Birleşik değişken (görüş × eğilim):** anlık görüş bantları
  1000–3000 / 3000–5000 / 5000–9999 / ≥ 9999 (girdi sayımına göre; sonuca
  bakılmadan) × 3 eğilim sınıfı = **12 hücre**, tek bir WoE değişkeni olarak.
- **Seyrek hücre kuralı** (her dış fold'un **eğitim** verisinde ölçülür):
  en az 500 gözlem, en az 10 pozitif satır, en az 5 bağımsız olay.
  Sağlamayan hücre **aynı görüş bandının `iyileşen/sabit` hücresiyle** birleşir.
  `iyileşen/sabit` hücresinin kendisi sağlamıyorsa o görüş bandının tamamı bir
  üst görüş bandıyla birleşir. Birleştirme yönü veriye bakılarak seçilmez.
- **Δspread_1sa:** tam 60 dk gecikme; kovalar ≤ −2, −1, 0, +1, ≥ +2 °C
  (METAR sıcaklığı tam sayı olduğu için doğal kovalar).

### 7.3 Varyantlar (en fazla üç)
| varyant | değişkenler |
|---|---|
| **V2a** | V1, ama `gorus` yerine birleşik görüş × eğilim (60 dk penceresi) |
| **V2b** | V2a + Δspread_1sa |
| **V2c** | **[KARAR BEKLİYOR]** V2b, ama eğilim sınıfı 120 dk penceresiyle |

Not: V1'in `spread_egilim_3` değişkeni zaten tam 3 saatlik gecikmeli Δspread
(`hedef.hazirla`). Bu yüzden önceki taslaktaki "V2c = V2b + Δspread_3sa" yeni
bilgi eklemiyordu ve çıkarıldı.

### 7.4 Eksik gecikme → V1'e geri dönüş
Bir satırda gerekli gecikmelerden biri eksikse V2'nin tahmini yerine **V1'in
tahmini** kullanılır (geliştirmede aynı fold'un V1 referansı; canlıda dondurulmuş
V1). Birincil değerlendirme bu birleşik sistem üzerinden yapılır.

## 8. Birincil karar (geliştirme, Deney 1)

- **Ölçü:** ΔLL = ortalama LL(V1 referansı) − ortalama LL(V2x); beş dış fold'un
  bütün satırları havuzlanır, geri dönüş dahil. Pozitif = V2 daha iyi.
- **Kural:** meteorolojik gün eşleştirilmiş bootstrap'le **ΔLL için tek taraflı
  %98,33 alt güven sınırı > 0** (üç varyant için Bonferroni: 0,05 / 3).
- **Koruma şartları** (her ikisi de gerekli; §9.1).
- **Seçim:** birincil kuralı ve koruma şartlarını geçen varyantlar arasından
  nokta ΔLL'si en büyük olan tek V2 spesifikasyonu olarak seçilir.
- **Hiçbiri geçmezse:** Deney 1 kapanır; gidişat bilgisi mevcut girdilerin
  ötesinde ölçülebilir bilgi taşımıyor sonucu raporlanır. Deney 1b, hazard ve
  sonraki adımlara geçilmez.

## 9. İkincil ölçütler, koruma şartları ve tanılamalar

### 9.1 Koruma şartları (kötüleşmeme / non-inferiority) — karar verir
- Bant eşiği: dondurulmuş V1'in taban oranının 5 katı
  (`5 × EGITIM_POZITIF / EGITIM_AN_SAYISI`), sayfadaki "yüksek" bandı.
- **Olay yakalama:** bir olay, başlangıcından önceki 3 saatteki onset-adayı
  satırlarından herhangi birinde tahmin ≥ bant eşiği ise yakalanmış sayılır.
  V2 − V1 yakalama oranı farkının, olay bootstrap'inde **%5 alt sınırı ≥ −5 puan**.
- **İlk alarm süresi:** ilk ≥ bant eşiği alarmından başlangıca kadar geçen dakika
  (yakalanmayan olay = 0 dk). Medyan farkın (V2 − V1) **%5 alt sınırı ≥ −30 dk**.

### 9.2 Yalnızca raporlanan ölçütler
- LSS: referans her fold'da yalnızca o fold'un eğitim satırlarından kurulan
  ay × saat iklimi (`model.iklim_baseline`).
- AP/taban, Brier, güvenilirlik tablosu.
- **Kapsama:** V2'nin gerçekten kullanıldığı satırların oranı.
- Yalnızca V2'nin çalıştığı satırlarda ΔLL (tanılama).
- 2015–16 erken dönem tanılaması.

### 9.3 SN tanılaması — zorunlu raporlanır, karar vermez
- **Satır düzeyi:** hedef penceresi (t, t+3sa] içinde **hiç SN gözlemi
  bulunmayan** satırlarda eşleştirilmiş ΔLL.
- **Olay düzeyi (örtüşen):** tüm olaylar / en az bir SN gözlemi içeren olaylar /
  hiç SN gözlemi içermeyen olaylar.

## 10. Sonraki deneyler (yalnızca Deney 1 bir V2 seçerse)

- **Deney 1b — gradient boosting:** seçilen V2'nin değişkenleriyle, sığ ağaçlar,
  güçlü düzenlileştirme, fiziksel yönü belli değişkenlerde yön kısıtı. Soru:
  "ek karmaşıklık, WoE lojistiğe göre §8 kuralıyla ölçülebilir kazanç getiriyor
  mu?" Getirmiyorsa seçilen V2 kalır.
- **Deney 2 — ayrık zamanlı hazard:** tek model, zaman dilimi değişken olarak;
  kümülatif 3 saatlik olasılık birincil karşılaştırmada V1 ile aynı ölçüyle
  sınanır. Ara ufuklar sınavı geçene kadar sayfada gösterilmez.

## 11. Dondurma, güç analizi ve T0

1. **Güç analizi** (seçimden sonra, dondurmadan önce): geliştirme tahminlerinden
   N bağımsız olay içeren meteorolojik günler ve orantılı olaysız günler yeniden
   örneklenir; her N için tek taraflı %95 alt sınır > 0 ve koruma şartlarının
   birlikte sağlanma olasılığı hesaplanır. Varsayılan gerçek etki senaryoları:
   0,25× · 0,50× · 1,00× ΔLL_geliştirme — üçü de raporlanır.
   **N\*** = 0,50× senaryosunda gücün %80'e ulaştığı en küçük olay sayısı;
   alt sınır 20. **N\* > 60** ise ileriye dönük sınav "bu etki büyüklüğü için
   yapılamaz" diye kayda geçer ve V2 canlıya ilerlemez; kriter gevşetilmez.
2. **Dondurma:** V2'nin kodu, dondurulmuş tabloları, bu protokolün o anki sürümü
   ve hash'i ile N\* tek bir PR'da merge edilir.
3. **T0** = o merge commit'inin zamanı ile gölge kaydın V2 tahmini yazdığı ilk
   çalıştırmanın zamanından **geç olanı**. T0 öncesi gölge kayıtlar yalnızca
   altyapı testidir.

## 12. İleriye dönük sınav (gölge mod)

- **Gölge kayıt** (yalnızca sona eklenir, her çalıştırmada git'e commit edilir):
  `observation_time`, `prediction_generated_at`, `bot_commit_sha`,
  `model_version` + dondurulmuş tablo hash'i, `feature_schema_version`, ham
  değişken değerleri, `v1_prob`, `v2_prob`, `v2_fallback`.
  **Sonuç (olay oldu mu) bu dosyada bulunmaz;** ayrı bir değerlendirme betiği
  SPECI'li gözlem arşiviyle sonradan birleştirir.
- **Kör bekleme:** T0'dan sonra N\* bağımsız olay birikene kadar yalnızca olay
  sayısı ve kayıt sağlığı izlenir; performans hesaplanmaz.
- **Tek değerlendirme:** dondurulmuş V1 vs dondurulmuş V2, aynı satırlar.
  Birincil kural: ΔLL için tek taraflı **%95** alt güven sınırı > 0 (tek
  karşılaştırma; Bonferroni geliştirme seçimine aitti). Koruma şartları §9.1
  ile aynı. SN tanılaması zorunlu raporlanır.
- **Geçerse** V2 canlıya alınır; **geçmezse** V1 kalır ve sonuç olduğu gibi
  raporlanır.

## 13. Bakış kaydı

| tarih | ne yapıldı | kim | not |
|---|---|---|---|
| — | — | — | — |

## 14. Raporlama

- Olumsuz sonuçlar da aynı ayrıntıyla raporlanır.
- Her raporda hedef "düşük görüş/FG olayı" olarak adlandırılır.

## 15. Değişiklik denetimi

- Deney 1'in sonuçlarından **önce**: bu belge sürüm numarası artırılarak,
  gerekçesiyle ve tarihli olarak değiştirilebilir.
- Deney 1'in sonuçlarından **sonra**: §5–§9 ve §11–§12'deki karar kuralları
  değiştirilemez. Hata düzeltmesi gerekiyorsa sonuçları etkileyip etkilemediği
  ayrıca raporlanır.
