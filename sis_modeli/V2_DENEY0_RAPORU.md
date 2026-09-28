# Sis modeli V2 — Deney 0 raporu (V2_PROTOKOL.md §4 eki)

**Tarih:** 28 Eylül 2026 · **Protokol:** 1.0 (dondurma commit'i `0ee9de9`) ·
**Betik:** `python -m sis_modeli.deney0_veri_denetimi` (2000 bootstrap tekrarı, tohum 0)

Hedefin teknik adı: **LTFJ düşük görüş/FG olayı** (olay gözlemi = görüş < 1000 m
∨ meydanı kaplayan FG; Y_t = 1 ⟺ (t, t+3sa] içinde olay gözlemi var).

**Bu deneyde yapılmayanlar:** V1 referansı ya da V2a/b/c eğitilmedi; hiçbir
tahmin üretilmedi; log-loss, ΔLL, AP, Brier, LSS veya başka bir performans
ölçütü hesaplanmadı. Betik `model`, `egit`, `degerlendir`, `woe` ve canlı model
modüllerini içe almaz (bir test bunu kilitler). Protokolde hiçbir değişiklik
yapılmadı.

---

## 0. Kullanılan kesin tanımlar

| kavram | tanım |
|---|---|
| satır evreni | `veri_oku(ltfj_ozellik.csv.gz)` → `zaman ≥ 2011` → `hedef.hazirla` (273.423 satır) |
| onset satırı | `hedef.onset_adaylari`: `sis = 0` (272.240 satır; Y=1: 1.916) |
| tam zaman gecikmesi | `dt − 60 dk` (ve `dt − 120 dk`) zaman damgalı kayıt; en yakın gözlem kullanılmaz |
| V2a/V2b kapsama | t−60 kaydı var. Ek olarak "alan dolu" sürümü: görüş(t), görüş(t−60) [V2b: + spread(t), spread(t−60)] dolu |
| V2c kapsama | t−60 **ve** t−120 kayıtları var (alan sürümü: + görüş(t−120)) |
| meteorolojik gün | `(dt − 12 sa).date()` — 12 UTC'den ertesi gün 12 UTC'ye |
| oran (§4.1) | P(eksik \| Y=1) / P(eksik \| Y=0); gün blok bootstrap, 2000 tekrar, iki yanlı %95 yüzdelik aralık |
| ufuk adımları | t+30, t+60, …, t+180 dk (`hedef.hazirla` ile aynı aritmetik) |
| etiketi doğrulanamayan satır | 6 ufuk adımından en az biri arşivde yok **ve** Y=0 |
| yüksek riskli satır | yukarıdakilerden, eksik adımın ±30/±60 dk'sında arşivde bir olay gözlemi olanlar |
| bağımsız olay | `bagimsiz_olaylar(kayitlar, etiket="sis", bosluk_saat=3.0)` (§5.1), 2011+ tam kayıt |
| SN | hava alanında `SN\|SG\|PL` (`sis_iklim.kod_kategorisi` ile aynı) |
| FG-ailesi | `sis_kodu` (meydanı kaplayan FG) ∨ `(BC\|MI\|PR)FG` |

**Protokolün açık bırakıp benim seçtiğim iki uygulama ayrıntısı** (sonuçlara
bakmadan önce betiğe yazıldı; ikisi de karar kuralı değil):
1. §4.1 aralığın güven düzeyini söylemiyor; **iki yanlı %95** kullanıldı.
2. Y=1 satırlarında hiç eksik olmayan tabakada oran 0 ve aralık [0, 0] olur.
   Kural harfiyen uygulanırsa bunlar da "kayda geçer". Bunlar gizlenmedi,
   **"dejenere"** diye ayrı işaretlendi (ay: 5; saat: 16 tabaka).

---

## 1. Özet bulgular

| # | bulgu | sayı | benim değerlendirmem |
|---|---|---|---|
| B1 | t−60 eksikliği hedefle ilişkili (§4.1 **kayda geçer**) | oran **2,62** [%95: 1,08 – 4,58]; Y=1'de 12/1.916 (%0,63), Y=0'da 646/270.324 (%0,24) | Protokol §7.4 bu satırlarda V1 referansına düşer; ΔLL katkısı 0 olur. Kapsama yüksek (%99,76). Geçerliliği bozduğunu düşünmüyorum; kayda geçti |
| B2 | V2c için (t−60 ∨ t−120) eksikliği | oran 2,09 [0,99 – 3,51]; 19/1.916 vs 1.283/270.324 | Kurala göre kayda geçmez (alt sınır 0,99), ama sınırda |
| B3 | Eksik slotlar düşük görüşün çevresinde yoğunlaşıyor | komşuda olay gözlemi %0,85 · komşu 1000–2999 m %1,04 · 3000–4999 %0,62 · ≥5000 %0,23 | B1'in mekanizması. Ayrıştırıcı kaynaklı değil: 2011+ ayrıştırıcı yalnızca 10 satır attı; eksiklik IEM kaynağında |
| B4 | Etiketi doğrulanamayan satırlar (ufuk eksik ∧ Y=0) | **2.991** (Y=0'ların %1,11); yüksek riskli **16** | V1 ve V2 aynı etiketlerle değerlendirilir; V2'ye özgü değil. 2011'de 1.221 (%7,1), 2015'te 505 |
| B5 | Ufku eksik satırlar Y=1'de daha sık | Y=1'lerin %4,65'i vs Y=0'ların %1,11'i | B3 ile aynı mekanizma (Y=1 etiketi yine de doğru) |
| B6 | 2011: düşük görüş neredeyse yok | <1000 m: 5 gözlem (2012–14: 75/86/133); FG-ailesi 18 (128–251); olay 2 | Aşağıda §3: kanıt karışık; ne "sakin yıl" ne "veri hatası" kanıtlanabiliyor |
| B7 | 2011: rüzgâr hızı dağılımı farklı | ≤2 kt %5,2 (2012–14: %16,0 / 14,7 / 15,9); her ay 2012–14'ün altında | Beklenmedik. Gerçek iklim de ölçüm/rapor farkı da olabilir; ham METAR'a erişim olmadan ayırt edilemez |
| B8 | 514/1.702 yeniden doğrulandı | 2011–2023: 1.702 Y=1, üç SN tanımında da 514; 2011–2026: 582/1.916 | Tutarlı |
| B9 | Olay düzeyi SN altyapısı çalışıyor | 290 olay: ≥1 SN 78, SN'siz 212; olayına atanamayan pozitif satır 0, gözlem 0 | Tutarlı |
| B10 | Izgara dışı 6 satır (5 SPECI 2022, 1 2026) | biri olay gözlemi: **2022-10-31 23:01, 900 m BCFG** | Bu gözlem tek başına bir bağımsız olay oluşturuyor, ama **hiçbir satırın hedef penceresine girmiyor** (pozitif satırı atanmamış tek olay). Ayrıca 5 ızgara dışı satır onset satırı olarak evrende |
| B11 | Zaman damgası bütünlüğü | yinelenen 0, sırasız 0, biçim hatası 0, ay/saat/spread/etiket tutarsızlığı 0 | Temiz |
| B12 | Canlı arşiv (§4.4) kaçan METAR'ları geri doldurmuyor | 4,5 günde 215 slotun 3'ü eksik (%1,40); tarihsel oran %0,24 | Gölge modda V2 kapsaması tarihselden düşük olacak (bkz. §6) |

---

## 2. B1–B5 ayrıntısı

**Y=1 satırlarında t−60'ı eksik 12 satır:** 2012-01-14 15:50, 2012-03-01 07:50,
2015-02-17 11:50, 2015-02-19 00:20, 2015-02-19 00:50, 2015-04-12 01:50,
2015-04-12 02:20, 2015-10-06 02:20, 2015-10-06 02:50, 2015-12-31 05:50,
2017-02-21 01:20, 2017-07-13 00:20. **7'si 2015'te.** Beşinde hava SN/SHSN.

**Olay gözleminin komşusundaki 15 eksik slot** 2015–2017 arasında; komşular
çoğunlukla +SHSN ya da BCFG/FG (liste: 2015-01-08 11:20, 2015-02-10 07:50 ve
15:20, 2015-06-11 01:20, 2015-09-05 03:20, 2015-10-05 02:20, 2016-01-01 00:20,
2016-02-17 18:50, 2016-12-14 00:50, 2017-01-09 15:20 ve 16:20, 2017-02-21 00:20
ve 03:20, 2017-03-24 21:50, 2017-05-04 04:50).

**Kaynak mı, ayrıştırıcı mı?** `sis-veri.yml`'in son çalıştırmasının
(17.09.2026) günlüğüne göre ayrıştırıcı 2011–2026'da toplam 10 satır attı
(2011:1, 2012:3, 2013:1, 2020:2, 2022:2, 2025:1). Eksik slot sayısı yüzlerce.
Yani eksik gözlemler IEM arşivinde hiç yok. Neden eksik oldukları
(yayımlanmamış, iletilmemiş, arşive girmemiş) buradan belirlenemez.

**Ne anlama geliyor (performans değil, yapı):** Eksiklik rastgele değil; düşük
görüş anlarında 3–4 kat daha sık. §7.4 gereği bu satırlarda V2 yerine aynı
fold'un V1 referansı kullanılacak; dolayısıyla bu satırlar V1–V2 farkına
sıfır katkı verir ve karşılaştırmayı V2 lehine çarpıtamaz. Etkilenen pozitif
satır oranı: V2a/b %0,63, V2c %0,99.

---

## 3. B6–B7: 2011 denetimi — kanıt ne diyor

Veri hattı açısından 2011 normal görünüyor:
- gözlem sayısı 17.163 (ızgara doluluğu %98,0; 2012: %98,9);
- boş görüş/spread alanı yok; hava alanı boş oranı %89,7 (diğer yıllar %84–89);
- tavan boş %67,5 (diğer yıllar %54–66); ayrıştırıcı yalnızca 1 satır attı.

Meteorolojik ve biçimsel farklar:
- **Düşük görüş yok denecek kadar az.** <1000 m 5 gözlem; 1000–2999 m 63
  (2012–14: 259/153/192); 5000–9998 m daha fazla (%13,4).
- **Kış:** Ocak–Şubat–Aralık 2011'de <1000 m 0; SN içeren gözlem 8/3/2
  (2012–14 ort. 102/88/77). Ocak'ta spread ≤1 °C %10,3 (2012–14 ort. %21,3).
  Aralık 2011'de BR 113 (ort. 58), <5000 m 129 (ort. 99), ama <1000 m 0.
- **Rüzgâr (beklenmedik):** ≤2 kt oranı %5,2. 2012–2026'nın en düşüğü 2026'da
  %6,2, genel aralık %8–16. Eylül–Kasım 2011'de %1,5–2,9 (2012–14 ort.
  %14,5–17,3). Aralık 2010 %26,5 → 2011 boyunca düşük → Ocak 2012 %25,0.
  Dağılımda özellikle 1 kt (%1,0; 2012–14 ≈ %4,6–5,1) ve 2 kt (%2,8; ≈ %7,5) az.
- **Aynı elverişli koşulda daha az düşük görüş.** Elverişli gözlem (spread ≤1,
  ≤2 kt, 18–06 UTC) 2011'de 177, 2013'te 169 (benzer). Ama bunların <1000 m
  olanı 3'e karşı 11, <3000 m olanı 12'ye karşı 32.
- **Görüş değer yapısı:** 40 farklı görüş değeri (2012–2023: 56–63). 1000 m
  altında yalnız 300 ve 600 m var; 1000–2999 m arası seyrek.

**Sonuç:** "Sakin/sise elverişsiz bir yıl" açıklaması rüzgâr ve kış nemi
bulgularıyla uyumlu, ama benzer elverişli koşulda bile düşük görüşün az olması
ve rüzgâr dağılımının yıl boyu kayması tek başına iklimle açıklanmayı zorlaştırıyor.
Veri hatası da kanıtlanmış değil. 2011'in 2 olayı/12 pozitif satırı ile
17.158 onset satırı bütün dış fold'ların eğitimine girer (iç doğrulama
blokları 2014'te başlar). Etkisi V1 referansı ve V2 için ortaktır.

---

## 4. B8–B10: hedef bileşimi ve SN altyapısı

- Olay gözlemleri (2011–2026): 1.183; FG (meydanı kaplayan) 666, FG-ailesi 945,
  SN içeren 253, FG-ailesi ∧ SN 16, SN'siz 930, ne FG-ailesi ne SN 1.
- SN'li olay gözlemi yalnız Aralık–Mart'ta. Nisan–Kasım'ın hepsi SN'siz.
- Yıllar arası SN payı çok değişken: 2014, 2018, 2020, 2024'te 0; 2022'de
  139'un 72'si, 2025'te 36'nın 17'si.
- **Y=1 satırlarında SN (2011–2023): 514/1.702.** (a) pencerede herhangi bir
  gözlemde SN, (b) penceredeki olay gözleminde SN, (c) ilk olay gözleminde SN
  tanımları üçü de 514 veriyor. 2011–2026: 582/1.916.
- §9.3 satır tanılaması evreni: penceresinde SN olmayan satırlar Y=0'da
  265.613, Y=1'de 1.334.
- Olay düzeyi: 290 olay; ≥1 SN 78, SN'siz 212. Olayına atanamayan pozitif
  satır 0, olaya atanamayan olay gözlemi 0.
- **B10:** 2022-10-31 23:01 (SPECI, 900 m BCFG) tek gözlemlik bir olay:
  sonraki olay gözlemi 03:50'de (4 sa 49 dk sonra). Izgara aritmetiği (+30k dk)
  bu zamana hiç denk gelmediği için hiçbir satırın Y'sine girmez. 290 olayın
  **289'unun** en az bir pozitif satırı var; bu olayın yok. Ayrıca ızgara dışı
  5 satır (sis=0) onset evreninde; gecikme ve ufuk adımları ızgara dışında
  kaldığı için ufukları 0/6 ve Y=0.

---

## 5. Veri bütünlüğü

Yinelenen zaman damgası 0, dosya sırasında geri giden 0, biçim tek (16
karakter), ay/saat sütunu tutarsızlığı 0, `spread ≠ T − Td` 0, `sis` yeniden
hesap tutarsızlığı 0. Ardışık aralıklar (2011+): 30 dk 272.851; <30 dk 9
(ızgara dışı satırlar); 1 eksik adım 427; 2–5 eksik adım 109; 3 sa–24 sa 22;
>24 sa 4 (en uzunu 2020-04-10 → 2020-05-01, 480,5 sa; 2012-07-14 → 07-16,
48,5 sa). 2011 öncesi 1.484 satır analiz dışı.

---

## 6. Canlı arşiv bütünlüğü (§4.4)

**Kod:** `ltfj_rasat.raporlari_cek` MGM'den `hours=0` ile yalnızca **son
raporları** alır; `ltfj_gozlem_arsivi.ekle` yalnızca o çalıştırmada dönen
raporları yazar. Geri doldurma yok.

**Arşiv (`gozlem_arsivi.csv`, 23.09 13:50 → 28.09 00:50 UTC):** 212 METAR +
8 SPECI; 215 beklenen :20/:50 slotunun 3'ü eksik (%1,40): 27.09 02:50, 04:50,
16:20.

**Git geçmişi:** Arşivi değiştiren 214 commit'in 208'i 1 satır, 6'sı 2 satır
ekliyor (her seferinde SPECI + METAR; iki METAR birden hiç yok). Eksik
slotların çevresinde bot çalışıyordu: örneğin 27.09 02:54 UTC'de çalıştırma
var ama 02:50 METAR'ı arşive girmedi; 03:25'te yalnızca 03:20 geldi. Yani
kayıp bir çalıştırmanın atlanmasından değil, raporun yayımlanma gecikmesiyle
çalıştırma zamanının çakışmasından doğuyor ve kalıcı. (MGM'ye bu ortamdan
erişilemediği için yanıt içeriği doğrudan görülemedi; çıkarım kod ve commit
geçmişine dayanıyor.)

**Sonuç:** Canlıda t−60 eksikliği kabaca %1,4 (tarihsel %0,24). Gölge modda
V2a/b kapsaması ≈ %98,6, V2c ≈ %97,2 beklenir; eksik satırlarda §7.4 gereği
dondurulmuş V1 kullanılır. Canlı eksikliğin mekanizması hava durumundan
bağımsız (yayın gecikmesi), tarihsel eksiklik ise düşük görüşle ilişkili (B3).
Bu iki eksiklik türü farklıdır.

---

## 7. Sınıflandırma için size getirilenler

Deney 1'e (ambargolu V1 benchmark'a) otomatik geçilmedi. Kararınızı
gerektiren noktalar:

1. **B1 (§4.1 kayda geçti).** Protokol bunu "rapora yazılır, model davranışı
   değişmez" diye önceden bağlamış. Önerim: kayıt olarak kalsın; ek işlem yok.
2. **B6–B7 (2011).** Neden belirlenemedi. Seçenekler: (i) protokol gereği
   olduğu gibi kullanmak (2011 zaten `bolme.ILK_YIL`); (ii) "veri düzeltmesi"
   sayıp dışlamak. (ii) protokolün veri tanımını değiştirir; sonuç görülmeden
   önce ve gerekçesi veri kalitesi olarak yazılmalı.
3. **B10 (ızgara dışı SPECI satırları).** §3 "değişkenler yalnızca :20/:50
   ızgarasından" diyor, ama `hazirla` ızgara dışı 6 satırı evrende bırakıyor
   (5 onset satırı + 1 pozitif satırsız olay). Sayısal etkisi çok küçük.
   Sınıflandırma: kodlama/protokol uyumsuzluğu mu, yoksa olduğu gibi mi kalsın?
4. **B12 (canlı arşiv).** Gölge modun kapsamasını düşürür ama geçersiz kılmaz.
   Botun toplama biçimini değiştirmek (ör. daha uzun geçmiş istemek) V2
   protokolünün değil botun işi. Şimdilik yalnızca raporlandı.

Hiçbirini ben uygulamadım.

---

# Ek A — betik çıktısı (tam tablolar)


Kaynak: `ltfj_ozellik.csv.gz`; 2011+ satır: 273423; onset satırı: 272240; Y=1: 1916; bağımsız olay: 290. Model eğitilmedi; performans ölçütü hesaplanmadı.

## 1. Gecikme eksikliği ve kapsama (onset evreni)

Onset satırı: 272240. Tam zaman kuralı: kayıt `dt − 60 dk` / `dt − 120 dk` anında yoksa gecikme eksik.

| ölçüt | satır | % |
|---|---:|---:|
| t−60 zaman damgası yok | 658 | 0.24 |
| t−120 zaman damgası yok | 785 | 0.29 |
| t−60 var ama görüş boş | 0 | 0.000 |
| t−120 var ama görüş boş | 0 | 0.000 |
| t−60 var, görüş dolu, spread boş | 0 | 0.000 |
| anlık (t) görüş boş | 0 | 0.000 |
| anlık (t) spread boş | 0 | 0.000 |
| **V2a/V2b kapsama — zaman (t−60)** | 271582 | 99.76 |
| **V2c kapsama — zaman (t−60 ∧ t−120)** | 270938 | 99.52 |
| V2a kapsama — zaman + görüş(t, t−60) dolu | 271582 | 99.76 |
| V2b kapsama — + spread(t, t−60) dolu | 271582 | 99.76 |
| V2c kapsama — + görüş(t−120) dolu | 270938 | 99.52 |

### 1.1 Yıla göre

| yıl | satır | Y=1 | t−60 yok | % | t−120 yok | % | V2a/b kapsama % | V2c kapsama % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2011 | 17158 | 12 | 251 | 1.46 | 288 | 1.68 | 98.54 | 97.08 |
| 2012 | 17303 | 179 | 32 | 0.18 | 40 | 0.23 | 99.82 | 99.64 |
| 2013 | 17378 | 134 | 39 | 0.22 | 47 | 0.27 | 99.78 | 99.56 |
| 2014 | 17352 | 139 | 26 | 0.15 | 29 | 0.17 | 99.85 | 99.70 |
| 2015 | 17223 | 216 | 116 | 0.67 | 148 | 0.86 | 99.33 | 98.66 |
| 2016 | 17392 | 145 | 75 | 0.43 | 90 | 0.52 | 99.57 | 99.14 |
| 2017 | 17337 | 157 | 34 | 0.20 | 40 | 0.23 | 99.80 | 99.61 |
| 2018 | 17423 | 117 | 8 | 0.05 | 12 | 0.07 | 99.95 | 99.91 |
| 2019 | 17450 | 112 | 11 | 0.06 | 12 | 0.07 | 99.94 | 99.88 |
| 2020 | 16560 | 54 | 19 | 0.11 | 22 | 0.13 | 99.89 | 99.77 |
| 2021 | 17412 | 124 | 8 | 0.05 | 11 | 0.06 | 99.95 | 99.91 |
| 2022 | 17378 | 240 | 9 | 0.05 | 12 | 0.07 | 99.95 | 99.92 |
| 2023 | 17459 | 73 | 5 | 0.03 | 5 | 0.03 | 99.97 | 99.94 |
| 2024 | 17505 | 58 | 12 | 0.07 | 16 | 0.09 | 99.93 | 99.86 |
| 2025 | 17476 | 90 | 7 | 0.04 | 7 | 0.04 | 99.96 | 99.93 |
| 2026 | 12434 | 66 | 6 | 0.05 | 6 | 0.05 | 99.95 | 99.91 |

### 1.2 Aya göre (tüm yıllar)

| ay | satır | Y=1 | t−60 yok | % | t−120 yok | % | V2a/b kapsama % | V2c kapsama % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 23505 | 302 | 66 | 0.28 | 83 | 0.35 | 99.72 | 99.44 |
| 2 | 21376 | 393 | 35 | 0.16 | 37 | 0.17 | 99.84 | 99.68 |
| 3 | 23602 | 195 | 54 | 0.23 | 66 | 0.28 | 99.77 | 99.55 |
| 4 | 21910 | 98 | 79 | 0.36 | 87 | 0.40 | 99.64 | 99.29 |
| 5 | 23666 | 124 | 41 | 0.17 | 49 | 0.21 | 99.83 | 99.66 |
| 6 | 22901 | 129 | 76 | 0.33 | 87 | 0.38 | 99.67 | 99.34 |
| 7 | 23541 | 113 | 56 | 0.24 | 69 | 0.29 | 99.76 | 99.53 |
| 8 | 23660 | 143 | 63 | 0.27 | 70 | 0.30 | 99.73 | 99.47 |
| 9 | 22328 | 46 | 38 | 0.17 | 46 | 0.21 | 99.83 | 99.66 |
| 10 | 22164 | 127 | 62 | 0.28 | 76 | 0.34 | 99.72 | 99.46 |
| 11 | 21426 | 122 | 37 | 0.17 | 50 | 0.23 | 99.83 | 99.65 |
| 12 | 22161 | 124 | 51 | 0.23 | 65 | 0.29 | 99.77 | 99.54 |

### 1.3 UTC saate göre (tüm yıllar)

| saat | satır | Y=1 | t−60 yok | % | t−120 yok | % | V2a/b kapsama % | V2c kapsama % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 11239 | 241 | 80 | 0.71 | 47 | 0.42 | 99.29 | 99.14 |
| 1 | 11236 | 210 | 66 | 0.59 | 91 | 0.81 | 99.41 | 98.72 |
| 2 | 11233 | 169 | 41 | 0.36 | 81 | 0.72 | 99.64 | 99.07 |
| 3 | 11241 | 111 | 22 | 0.20 | 42 | 0.37 | 99.80 | 99.47 |
| 4 | 11286 | 84 | 18 | 0.16 | 25 | 0.22 | 99.84 | 99.65 |
| 5 | 11320 | 50 | 38 | 0.34 | 34 | 0.30 | 99.66 | 99.51 |
| 6 | 11353 | 52 | 21 | 0.18 | 44 | 0.39 | 99.82 | 99.48 |
| 7 | 11330 | 41 | 20 | 0.18 | 25 | 0.22 | 99.82 | 99.64 |
| 8 | 11382 | 31 | 58 | 0.51 | 23 | 0.20 | 99.49 | 99.31 |
| 9 | 11378 | 22 | 24 | 0.21 | 60 | 0.53 | 99.79 | 99.29 |
| 10 | 11384 | 24 | 22 | 0.19 | 26 | 0.23 | 99.81 | 99.60 |
| 11 | 11387 | 30 | 27 | 0.24 | 27 | 0.24 | 99.76 | 99.57 |
| 12 | 11394 | 34 | 22 | 0.19 | 28 | 0.25 | 99.81 | 99.57 |
| 13 | 11385 | 28 | 17 | 0.15 | 25 | 0.22 | 99.85 | 99.67 |
| 14 | 11386 | 20 | 21 | 0.18 | 19 | 0.17 | 99.82 | 99.68 |
| 15 | 11389 | 21 | 18 | 0.16 | 22 | 0.19 | 99.84 | 99.66 |
| 16 | 11399 | 24 | 23 | 0.20 | 23 | 0.20 | 99.80 | 99.65 |
| 17 | 11399 | 32 | 15 | 0.13 | 28 | 0.25 | 99.87 | 99.66 |
| 18 | 11395 | 45 | 22 | 0.19 | 20 | 0.18 | 99.81 | 99.68 |
| 19 | 11388 | 63 | 21 | 0.18 | 22 | 0.19 | 99.82 | 99.62 |
| 20 | 11394 | 83 | 22 | 0.19 | 22 | 0.19 | 99.81 | 99.62 |
| 21 | 11356 | 113 | 11 | 0.10 | 27 | 0.24 | 99.90 | 99.71 |
| 22 | 11325 | 169 | 11 | 0.10 | 13 | 0.11 | 99.90 | 99.81 |
| 23 | 11261 | 219 | 18 | 0.16 | 11 | 0.10 | 99.84 | 99.75 |

### 1.4 Eksiklik ile hedef ilişkisi — P(eksik | Y=1) / P(eksik | Y=0)

Meteorolojik gün (12–12 UTC) blok bootstrap, 2000 tekrar, tohum 0, iki yanlı %95 yüzdelik aralık. Kayda geçme: oran [0.8; 1.25] dışında **ve** aralık 1'i dışlıyor. Bir tekrarda P(eksik|Y=0) = 0 ya da tabakada Y=1 yoksa oran tanımsızdır; geçerli tekrar tekrarların %90'ından azsa aralık verilmez. Y=1 satırlarında hiç eksik olmayan tabakada oran 0 ve aralık [0, 0] olur; kural harfiyen uygulanırsa bu tabakalar da "kayda geçer", ama bu bir sıfır sayımıdır — "dejenere" diye ayrı işaretlenir.


**t−60 zaman yok (V2a/b geri dönüşü)**

| tabaka | Y=1 satır | eksik | % | Y=0 satır | eksik | % | oran | %95 aralık | geçerli tekrar | §4.1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| tümü | 1916 | 12 | 0.63 | 270324 | 646 | 0.24 | 2.62 | 1.08 – 4.58 | 2000 | KAYDA GEÇER |
| ay 1 | 302 | 1 | 0.33 | 23203 | 65 | 0.28 | 1.18 | 0.00 – 4.35 | 2000 |  |
| ay 2 | 393 | 4 | 1.02 | 20983 | 31 | 0.15 | 6.89 | 0.00 – 18.00 | 2000 |  |
| ay 3 | 195 | 1 | 0.51 | 23407 | 53 | 0.23 | 2.26 | 0.00 – 8.18 | 2000 |  |
| ay 4 | 98 | 2 | 2.04 | 21812 | 77 | 0.35 | 5.78 | 0.00 – 22.13 | 2000 |  |
| ay 5 | 124 | 0 | 0.00 | 23542 | 41 | 0.17 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| ay 6 | 129 | 0 | 0.00 | 22772 | 76 | 0.33 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| ay 7 | 113 | 1 | 0.88 | 23428 | 55 | 0.23 | 3.77 | 0.00 – 13.40 | 2000 |  |
| ay 8 | 143 | 0 | 0.00 | 23517 | 63 | 0.27 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| ay 9 | 46 | 0 | 0.00 | 22282 | 38 | 0.17 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| ay 10 | 127 | 2 | 1.57 | 22037 | 60 | 0.27 | 5.78 | 0.00 – 21.96 | 2000 |  |
| ay 11 | 122 | 0 | 0.00 | 21304 | 37 | 0.17 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| ay 12 | 124 | 1 | 0.81 | 22037 | 50 | 0.23 | 3.55 | 0.00 – 10.67 | 2000 |  |
| saat 0 | 241 | 3 | 1.24 | 10998 | 77 | 0.70 | 1.78 | 0.00 – 5.00 | 2000 |  |
| saat 1 | 210 | 2 | 0.95 | 11026 | 64 | 0.58 | 1.64 | 0.00 – 4.52 | 2000 |  |
| saat 2 | 169 | 3 | 1.78 | 11064 | 38 | 0.34 | 5.17 | 0.00 – 15.63 | 2000 |  |
| saat 3 | 111 | 0 | 0.00 | 11130 | 22 | 0.20 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 4 | 84 | 0 | 0.00 | 11202 | 18 | 0.16 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 5 | 50 | 1 | 2.00 | 11270 | 37 | 0.33 | 6.09 | 0.00 – 21.90 | 2000 |  |
| saat 6 | 52 | 0 | 0.00 | 11301 | 21 | 0.19 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 7 | 41 | 1 | 2.44 | 11289 | 19 | 0.17 | 14.49 | 0.00 – 59.00 | 2000 |  |
| saat 8 | 31 | 0 | 0.00 | 11351 | 58 | 0.51 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 9 | 22 | 0 | 0.00 | 11356 | 24 | 0.21 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 10 | 24 | 0 | 0.00 | 11360 | 22 | 0.19 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 11 | 30 | 1 | 3.33 | 11357 | 26 | 0.23 | 14.56 | 0.00 – 56.07 | 2000 |  |
| saat 12 | 34 | 0 | 0.00 | 11360 | 22 | 0.19 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 13 | 28 | 0 | 0.00 | 11357 | 17 | 0.15 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 14 | 20 | 0 | 0.00 | 11366 | 21 | 0.18 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 15 | 21 | 1 | 4.76 | 11368 | 17 | 0.15 | 31.84 | 0.00 – 125.98 | 2000 |  |
| saat 16 | 24 | 0 | 0.00 | 11375 | 23 | 0.20 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 17 | 32 | 0 | 0.00 | 11367 | 15 | 0.13 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 18 | 45 | 0 | 0.00 | 11350 | 22 | 0.19 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 19 | 63 | 0 | 0.00 | 11325 | 21 | 0.19 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 20 | 83 | 0 | 0.00 | 11311 | 22 | 0.19 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 21 | 113 | 0 | 0.00 | 11243 | 11 | 0.10 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 22 | 169 | 0 | 0.00 | 11156 | 11 | 0.10 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 23 | 219 | 0 | 0.00 | 11042 | 18 | 0.16 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |

**t−60 ∨ t−120 zaman yok (V2c geri dönüşü)**

| tabaka | Y=1 satır | eksik | % | Y=0 satır | eksik | % | oran | %95 aralık | geçerli tekrar | §4.1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| tümü | 1916 | 19 | 0.99 | 270324 | 1283 | 0.47 | 2.09 | 0.99 – 3.51 | 2000 |  |
| ay 1 | 302 | 2 | 0.66 | 23203 | 129 | 0.56 | 1.19 | 0.00 – 3.34 | 2000 |  |
| ay 2 | 393 | 6 | 1.53 | 20983 | 63 | 0.30 | 5.08 | 0.71 – 12.81 | 2000 |  |
| ay 3 | 195 | 2 | 1.03 | 23407 | 105 | 0.45 | 2.29 | 0.00 – 8.26 | 2000 |  |
| ay 4 | 98 | 3 | 3.06 | 21812 | 152 | 0.70 | 4.39 | 0.00 – 16.85 | 2000 |  |
| ay 5 | 124 | 0 | 0.00 | 23542 | 81 | 0.34 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| ay 6 | 129 | 0 | 0.00 | 22772 | 152 | 0.67 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| ay 7 | 113 | 1 | 0.88 | 23428 | 110 | 0.47 | 1.88 | 0.00 – 6.72 | 2000 |  |
| ay 8 | 143 | 0 | 0.00 | 23517 | 125 | 0.53 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| ay 9 | 46 | 0 | 0.00 | 22282 | 76 | 0.34 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| ay 10 | 127 | 2 | 1.57 | 22037 | 117 | 0.53 | 2.97 | 0.00 – 11.03 | 2000 |  |
| ay 11 | 122 | 0 | 0.00 | 21304 | 74 | 0.35 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| ay 12 | 124 | 3 | 2.42 | 22037 | 99 | 0.45 | 5.39 | 0.00 – 13.41 | 2000 |  |
| saat 0 | 241 | 3 | 1.24 | 10998 | 94 | 0.85 | 1.46 | 0.00 – 4.05 | 2000 |  |
| saat 1 | 210 | 3 | 1.43 | 11026 | 141 | 1.28 | 1.12 | 0.00 – 2.63 | 2000 |  |
| saat 2 | 169 | 4 | 2.37 | 11064 | 101 | 0.91 | 2.59 | 0.00 – 7.02 | 2000 |  |
| saat 3 | 111 | 0 | 0.00 | 11130 | 60 | 0.54 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 4 | 84 | 0 | 0.00 | 11202 | 40 | 0.36 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 5 | 50 | 1 | 2.00 | 11270 | 55 | 0.49 | 4.10 | 0.00 – 14.73 | 2000 |  |
| saat 6 | 52 | 1 | 1.92 | 11301 | 58 | 0.51 | 3.75 | 0.00 – 13.08 | 2000 |  |
| saat 7 | 41 | 1 | 2.44 | 11289 | 40 | 0.35 | 6.88 | 0.00 – 24.71 | 2000 |  |
| saat 8 | 31 | 1 | 3.23 | 11351 | 77 | 0.68 | 4.76 | 0.00 – 16.06 | 2000 |  |
| saat 9 | 22 | 1 | 4.55 | 11356 | 80 | 0.70 | 6.45 | 0.00 – 21.63 | 2000 |  |
| saat 10 | 24 | 0 | 0.00 | 11360 | 45 | 0.40 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 11 | 30 | 1 | 3.33 | 11357 | 48 | 0.42 | 7.89 | 0.00 – 27.44 | 2000 |  |
| saat 12 | 34 | 0 | 0.00 | 11360 | 49 | 0.43 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 13 | 28 | 1 | 3.57 | 11357 | 37 | 0.33 | 10.96 | 0.00 – 39.39 | 2000 |  |
| saat 14 | 20 | 0 | 0.00 | 11366 | 37 | 0.33 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 15 | 21 | 1 | 4.76 | 11368 | 38 | 0.33 | 14.25 | 0.00 – 52.68 | 2000 |  |
| saat 16 | 24 | 0 | 0.00 | 11375 | 40 | 0.35 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 17 | 32 | 0 | 0.00 | 11367 | 39 | 0.34 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 18 | 45 | 0 | 0.00 | 11350 | 37 | 0.33 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 19 | 63 | 1 | 1.59 | 11325 | 42 | 0.37 | 4.28 | 0.00 – 15.75 | 2000 |  |
| saat 20 | 83 | 0 | 0.00 | 11311 | 43 | 0.38 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 21 | 113 | 0 | 0.00 | 11243 | 33 | 0.29 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 22 | 169 | 0 | 0.00 | 11156 | 21 | 0.19 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |
| saat 23 | 219 | 0 | 0.00 | 11042 | 28 | 0.25 | 0.00 | 0.00 – 0.00 | 2000 | dejenere (Y=1'de 0 eksik) |

### 1.5 Gecikme eksikliği × ufuk eksikliği (onset satırları)

|  | ufuk tam (6/6) | ufuk eksik (< 6) |
|---|---:|---:|
| t−60 var | 268566 | 3016 |
| t−60 yok | 594 | 64 |

### 1.6 Eksik ızgara slotu — komşu gözlemin durumuna göre

Birim: ilk ve son :20/:50 gözlemi arasındaki her beklenen 30 dk slot. Komşu = slot ± 30 dk'daki gözlem(ler). Grup önceliği: komşuda olay gözlemi > komşu görüş 1000–2999 > 3000–4999 > ≥ 5000. Model/tahmin yok; yalnızca sayım.

| grup | slot | eksik | % |
|---|---:|---:|---:|
| komşuda olay gözlemi | 1756 | 15 | 0.85 |
| komşu görüş 1000–2999 | 3544 | 37 | 1.04 |
| komşu görüş 3000–4999 | 8961 | 56 | 0.62 |
| komşu görüş ≥ 5000 | 259819 | 589 | 0.23 |
| iki komşu da yok | 1376 | 1342 | 97.53 | 

## 2. Hedef ufku bütünlüğü (onset evreni)

Tanım: t anındaki onset satırı için beklenen adımlar t+30, t+60, …, t+180 dk (`hedef.hazirla` ile aynı aritmetik). `hazirla` eksik adımı atlar; hiçbir mevcut adımda olay yoksa Y=0 yazar. Dolayısıyla **ufku eksik ve Y=0** olan satırın etiketi doğrulanamaz (eksik adımda olay olabilirdi). Ufku eksik ve Y=1 olan satırın etiketi doğrudur (olay mevcut bir adımda görülmüş).

| mevcut adım | satır | % | Y=0 | Y=1 |
|---|---:|---:|---:|---:|
| 6/6 | 269160 | 98.869 | 267333 | 1827 |
| 5/6 | 2304 | 0.846 | 2235 | 69 |
| 4/6 | 476 | 0.175 | 459 | 17 |
| 3/6 | 151 | 0.055 | 149 | 2 |
| 2/6 | 77 | 0.028 | 76 | 1 |
| 1/6 | 40 | 0.015 | 40 | 0 |
| 0/6 | 32 | 0.012 | 32 | 0 |

- Ufku eksik satır: 3080 (%1.13); Y=0: 2991 (Y=0'ların %1.11), Y=1: 89 (Y=1'lerin %4.65).
- **Etiketi doğrulanamayan satır (ufuk eksik ∧ Y=0): 2991.**
- Bunlardan eksik adımın ±60 dk komşuluğunda arşivde bir olay gözlemi bulunan (yüksek riskli) satır: **16**.

### 2.1 Yıla göre

| yıl | satır | ufuk eksik | % | eksik ∧ Y=0 | eksik ∧ Y=1 | 0/6 adım ∧ Y=0 | arşiv sonu kesik | yüksek riskli |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2011 | 17158 | 1223 | 7.13 | 1221 | 2 | 10 | 0 | 0 |
| 2012 | 17303 | 154 | 0.89 | 148 | 6 | 2 | 0 | 0 |
| 2013 | 17378 | 187 | 1.08 | 185 | 2 | 2 | 0 | 0 |
| 2014 | 17352 | 120 | 0.69 | 120 | 0 | 1 | 0 | 0 |
| 2015 | 17223 | 548 | 3.18 | 505 | 43 | 5 | 0 | 12 |
| 2016 | 17392 | 314 | 1.81 | 298 | 16 | 2 | 0 | 0 |
| 2017 | 17337 | 171 | 0.99 | 151 | 20 | 2 | 0 | 4 |
| 2018 | 17423 | 29 | 0.17 | 29 | 0 | 0 | 0 | 0 |
| 2019 | 17450 | 53 | 0.30 | 53 | 0 | 0 | 0 | 0 |
| 2020 | 16560 | 92 | 0.56 | 92 | 0 | 1 | 0 | 0 |
| 2021 | 17412 | 30 | 0.17 | 30 | 0 | 0 | 0 | 0 |
| 2022 | 17378 | 23 | 0.13 | 23 | 0 | 4 | 0 | 0 |
| 2023 | 17459 | 18 | 0.10 | 18 | 0 | 0 | 0 | 0 |
| 2024 | 17505 | 50 | 0.29 | 50 | 0 | 1 | 0 | 0 |
| 2025 | 17476 | 31 | 0.18 | 31 | 0 | 0 | 0 | 0 |
| 2026 | 12434 | 37 | 0.30 | 37 | 0 | 2 | 6 | 0 |

### 2.2 Aya göre (tüm yıllar)

| ay | satır | ufuk eksik | % | eksik ∧ Y=0 | eksik ∧ Y=1 | yüksek riskli |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 23505 | 282 | 1.20 | 260 | 22 | 4 |
| 2 | 21376 | 178 | 0.83 | 159 | 19 | 2 |
| 3 | 23602 | 258 | 1.09 | 251 | 7 | 0 |
| 4 | 21910 | 339 | 1.55 | 339 | 0 | 0 |
| 5 | 23666 | 186 | 0.79 | 184 | 2 | 0 |
| 6 | 22901 | 333 | 1.45 | 328 | 5 | 2 |
| 7 | 23541 | 281 | 1.19 | 279 | 2 | 0 |
| 8 | 23660 | 315 | 1.33 | 311 | 4 | 2 |
| 9 | 22328 | 213 | 0.95 | 205 | 8 | 3 |
| 10 | 22164 | 293 | 1.32 | 288 | 5 | 1 |
| 11 | 21426 | 145 | 0.68 | 142 | 3 | 0 |
| 12 | 22161 | 257 | 1.16 | 245 | 12 | 2 |

Yüksek riskli satırların meteorolojik günleri (10 gün):

| meteorolojik gün | satır |
|---|---:|
| 2015-01-06 | 2 |
| 2015-02-09 | 1 |
| 2015-02-17 | 1 |
| 2015-06-10 | 2 |
| 2015-09-04 | 1 |
| 2015-09-16 | 2 |
| 2015-10-04 | 1 |
| 2015-12-31 | 2 |
| 2017-01-08 | 2 |
| 2017-08-05 | 2 | 

## 3. 2011 denetimi (2012–2014 ile karşılaştırma; bağlam için tüm yıllar)

### 3.1 Görüş dağılımı (gözlem sayısı, parantezde %)

| yıl | gözlem | boş | < 1000 | 1000–2999 | 3000–4999 | 5000–9998 | ≥ 9999 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2011 | 17163 | 0 (0.00) | 5 (0.03) | 63 (0.37) | 548 (3.19) | 2306 (13.44) | 14241 (82.98) |
| 2012 | 17378 | 0 (0.00) | 75 (0.43) | 259 (1.49) | 466 (2.68) | 1965 (11.31) | 14613 (84.09) |
| 2013 | 17464 | 0 (0.00) | 86 (0.49) | 153 (0.88) | 530 (3.03) | 1336 (7.65) | 15359 (87.95) |
| 2014 | 17485 | 0 (0.00) | 133 (0.76) | 192 (1.10) | 468 (2.68) | 1563 (8.94) | 15129 (86.53) |
| 2015 | 17342 | 0 (0.00) | 119 (0.69) | 287 (1.65) | 403 (2.32) | 1399 (8.07) | 15134 (87.27) |
| 2016 | 17471 | 0 (0.00) | 79 (0.45) | 170 (0.97) | 401 (2.30) | 1214 (6.95) | 15607 (89.33) |
| 2017 | 17465 | 0 (0.00) | 128 (0.73) | 282 (1.61) | 730 (4.18) | 1766 (10.11) | 14559 (83.36) |
| 2018 | 17507 | 0 (0.00) | 84 (0.48) | 215 (1.23) | 617 (3.52) | 2003 (11.44) | 14588 (83.33) |
| 2019 | 17507 | 0 (0.00) | 57 (0.33) | 174 (0.99) | 530 (3.03) | 1426 (8.15) | 15320 (87.51) |
| 2020 | 16588 | 0 (0.00) | 28 (0.17) | 122 (0.74) | 434 (2.62) | 1408 (8.49) | 14596 (87.99) |
| 2021 | 17508 | 0 (0.00) | 96 (0.55) | 185 (1.06) | 405 (2.31) | 1572 (8.98) | 15250 (87.10) |
| 2022 | 17517 | 0 (0.00) | 139 (0.79) | 135 (0.77) | 291 (1.66) | 1087 (6.21) | 15865 (90.57) |
| 2023 | 17515 | 0 (0.00) | 56 (0.32) | 104 (0.59) | 436 (2.49) | 1249 (7.13) | 15670 (89.47) |
| 2024 | 17541 | 0 (0.00) | 36 (0.21) | 80 (0.46) | 226 (1.29) | 887 (5.06) | 16312 (92.99) |
| 2025 | 17512 | 0 (0.00) | 36 (0.21) | 88 (0.50) | 349 (1.99) | 977 (5.58) | 16062 (91.72) |
| 2026 | 12460 | 0 (0.00) | 26 (0.21) | 121 (0.97) | 217 (1.74) | 636 (5.10) | 11460 (91.97) |

### 3.2 Hava kodları, olay gözlemi, onset/pozitif/olay

`hava boş %`: hava alanı boş olan gözlem yüzdesi. `FG (alanı kaplayan)`: `sis_kodu`. `FG içeren`: hava metninde FG geçen her gözlem (BCFG/MIFG/PRFG/VCFG/FZFG dahil). Olay sayısı başlangıç yılına göre (§5.1).

| yıl | gözlem | hava boş % | BR | FG (alanı kaplayan) | BC/MI/PRFG | FG içeren | SN/SG/PL | RA/DZ | HZ/FU/DU | olay gözlemi | onset satır | Y=1 satır | bağımsız olay |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2011 | 17163 | 89.7 | 534 | 5 | 13 | 18 | 106 | 1223 | 4 | 5 | 17158 | 12 | 2 |
| 2012 | 17378 | 86.5 | 512 | 29 | 99 | 128 | 627 | 1283 | 12 | 75 | 17303 | 179 | 27 |
| 2013 | 17464 | 88.0 | 592 | 61 | 103 | 164 | 166 | 1233 | 11 | 86 | 17378 | 134 | 21 |
| 2014 | 17485 | 86.8 | 509 | 91 | 160 | 251 | 100 | 1546 | 10 | 133 | 17352 | 139 | 21 |
| 2015 | 17342 | 87.5 | 436 | 54 | 157 | 212 | 403 | 1188 | 22 | 119 | 17223 | 216 | 36 |
| 2016 | 17471 | 87.9 | 388 | 34 | 137 | 171 | 361 | 1386 | 10 | 79 | 17392 | 145 | 22 |
| 2017 | 17465 | 85.3 | 813 | 69 | 152 | 221 | 268 | 1455 | 10 | 128 | 17337 | 157 | 23 |
| 2018 | 17507 | 84.1 | 754 | 63 | 116 | 179 | 95 | 1998 | 1 | 84 | 17423 | 117 | 17 |
| 2019 | 17507 | 86.4 | 549 | 47 | 120 | 167 | 157 | 1590 | 19 | 57 | 17450 | 112 | 18 |
| 2020 | 16588 | 86.0 | 472 | 19 | 126 | 145 | 77 | 1805 | 3 | 28 | 16560 | 54 | 8 |
| 2021 | 17508 | 84.5 | 250 | 53 | 196 | 249 | 355 | 1947 | 9 | 96 | 17412 | 124 | 18 |
| 2022 | 17517 | 88.2 | 244 | 60 | 104 | 164 | 438 | 1297 | 0 | 139 | 17378 | 240 | 34 |
| 2023 | 17515 | 87.6 | 423 | 34 | 76 | 111 | 194 | 1629 | 9 | 56 | 17459 | 73 | 10 |
| 2024 | 17541 | 88.8 | 219 | 21 | 180 | 201 | 72 | 1552 | 4 | 36 | 17505 | 58 | 9 |
| 2025 | 17512 | 88.9 | 335 | 15 | 122 | 137 | 268 | 1343 | 0 | 36 | 17476 | 90 | 13 |
| 2026 | 12460 | 86.9 | 259 | 11 | 116 | 129 | 173 | 1271 | 6 | 26 | 12434 | 66 | 11 |

### 3.3 Görüş değer yapısı ve diğer alanlar

| yıl | farklı görüş değeri | en küçük görüş | %1 | %5 | %10 | medyan | tavan boş % | spread boş % | spread ≤ 1 % | rüzgâr yönü boş % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2011 | 40 | 300 | 3400 | 6000 | 6000 | 9999 | 67.5 | 0.0 | 9.9 | 8.0 |
| 2012 | 58 | 150 | 1800 | 6000 | 7000 | 9999 | 63.5 | 0.0 | 13.4 | 10.2 |
| 2013 | 59 | 50 | 2200 | 6000 | 7000 | 9999 | 63.1 | 0.0 | 8.6 | 9.3 |
| 2014 | 61 | 150 | 1400 | 6000 | 7000 | 9999 | 55.2 | 0.0 | 12.6 | 9.3 |
| 2015 | 63 | 100 | 1400 | 6000 | 7000 | 9999 | 61.6 | 0.0 | 17.0 | 6.9 |
| 2016 | 58 | 200 | 2200 | 6000 | 8000 | 9999 | 65.6 | 0.0 | 12.5 | 6.6 |
| 2017 | 62 | 100 | 1200 | 4200 | 6000 | 9999 | 61.1 | 0.0 | 12.2 | 7.6 |
| 2018 | 62 | 150 | 2100 | 4800 | 7000 | 9999 | 53.7 | 0.0 | 15.0 | 6.5 |
| 2019 | 61 | 100 | 2400 | 6000 | 8000 | 9999 | 63.5 | 0.0 | 14.1 | 6.0 |
| 2020 | 56 | 100 | 3100 | 6000 | 8000 | 9999 | 62.1 | 0.0 | 16.3 | 5.1 |
| 2021 | 62 | 50 | 1600 | 6000 | 7000 | 9999 | 59.7 | 0.0 | 20.7 | 6.2 |
| 2022 | 62 | 100 | 1600 | 6000 | 9999 | 9999 | 64.0 | 0.0 | 24.9 | 5.1 |
| 2023 | 61 | 100 | 3100 | 6000 | 8000 | 9999 | 60.0 | 0.0 | 22.2 | 5.8 |
| 2024 | 55 | 400 | 3600 | 8000 | 9999 | 9999 | 65.0 | 0.0 | 9.6 | 6.2 |
| 2025 | 56 | 250 | 3400 | 7000 | 9999 | 9999 | 66.3 | 0.0 | 8.9 | 7.1 |
| 2026 | 58 | 250 | 2500 | 7000 | 9999 | 9999 | 60.1 | 0.0 | 10.7 | 5.4 |

### 3.3b Rüzgâr hızı dağılımı ve sise elverişli koşullar

`sakin`: rüzgâr ≤ 2 kt. `elverişli`: spread ≤ 1 °C ∧ rüzgâr ≤ 2 kt ∧ 18–06 UTC. Son iki sütun elverişli gözlemlerden görüşü < 1000 / < 3000 olanlar.

| yıl | 0 kt % | 1 kt % | 2 kt % | sakin % | hız boş | elverişli | elverişli ∧ < 1000 | elverişli ∧ < 3000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2011 | 1.4 | 1.0 | 2.8 | 5.2 | 0 | 177 | 3 | 12 |
| 2012 | 3.1 | 5.1 | 7.8 | 16.0 | 46 | 341 | 15 | 46 |
| 2013 | 2.9 | 4.6 | 7.3 | 14.7 | 0 | 169 | 11 | 32 |
| 2014 | 3.7 | 4.5 | 7.7 | 15.9 | 0 | 214 | 19 | 46 |
| 2015 | 1.1 | 2.0 | 5.2 | 8.3 | 0 | 229 | 8 | 30 |
| 2016 | 3.4 | 2.4 | 5.2 | 11.0 | 0 | 285 | 12 | 29 |
| 2017 | 3.8 | 2.7 | 5.7 | 12.3 | 0 | 281 | 28 | 71 |
| 2018 | 1.9 | 2.3 | 4.7 | 8.9 | 0 | 235 | 10 | 40 |
| 2019 | 4.4 | 2.3 | 4.0 | 10.7 | 9 | 264 | 5 | 25 |
| 2020 | 7.0 | 2.1 | 3.7 | 12.9 | 0 | 311 | 7 | 28 |
| 2021 | 1.3 | 2.0 | 5.8 | 9.0 | 2 | 326 | 18 | 34 |
| 2022 | 5.3 | 1.8 | 3.3 | 10.4 | 0 | 402 | 9 | 16 |
| 2023 | 4.0 | 1.7 | 3.9 | 9.7 | 0 | 363 | 19 | 30 |
| 2024 | 2.3 | 1.7 | 4.2 | 8.2 | 0 | 127 | 3 | 6 |
| 2025 | 2.1 | 2.3 | 5.4 | 9.8 | 10 | 208 | 3 | 25 |
| 2026 | 0.9 | 1.6 | 3.7 | 6.2 | 0 | 55 | 0 | 3 |

Aylık — 2011 ile 2012–2014 ortalaması:

| ay | sakin % 2011 | 2012–14 | spread ≤ 1 % 2011 | 2012–14 | ort. sıcaklık 2011 | 2012–14 |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 11.1 | 21.2 | 10.3 | 21.3 | 6.7 | 6.5 |
| 2 | 4.4 | 17.6 | 15.0 | 24.4 | 6.4 | 6.7 |
| 3 | 9.1 | 17.7 | 16.0 | 12.8 | 7.9 | 9.4 |
| 4 | 3.0 | 20.9 | 16.5 | 8.3 | 10.1 | 14.2 |
| 5 | 7.1 | 17.9 | 10.8 | 9.1 | 16.6 | 18.5 |
| 6 | 4.7 | 12.6 | 5.6 | 3.3 | 22.3 | 22.4 |
| 7 | 3.7 | 8.0 | 2.8 | 3.5 | 26.6 | 24.9 |
| 8 | 2.7 | 6.0 | 1.8 | 3.1 | 24.8 | 25.0 |
| 9 | 1.5 | 15.0 | 5.4 | 2.1 | 23.3 | 21.1 |
| 10 | 1.6 | 14.5 | 8.6 | 11.4 | 15.3 | 16.6 |
| 11 | 2.9 | 17.3 | 9.1 | 13.5 | 9.7 | 12.9 |
| 12 | 10.2 | 17.6 | 17.3 | 26.1 | 9.2 | 7.7 |

### 3.4 Gözlem zaman yapısı

| yıl | gözlem | :20 | :50 | diğer dakika | gözlemli gün | ızgara doluluk % |
|---|---:|---:|---:|---:|---:|---:|
| 2011 | 17163 | 8554 | 8609 | 0 | 365 | 98.0 |
| 2012 | 17378 | 8691 | 8687 | 0 | 365 | 98.9 |
| 2013 | 17464 | 8728 | 8736 | 0 | 365 | 99.7 |
| 2014 | 17485 | 8742 | 8743 | 0 | 365 | 99.8 |
| 2015 | 17342 | 8657 | 8685 | 0 | 365 | 99.0 |
| 2016 | 17471 | 8732 | 8739 | 0 | 366 | 99.4 |
| 2017 | 17465 | 8729 | 8736 | 0 | 365 | 99.7 |
| 2018 | 17507 | 8755 | 8752 | 0 | 365 | 99.9 |
| 2019 | 17507 | 8753 | 8754 | 0 | 365 | 99.9 |
| 2020 | 16588 | 8294 | 8294 | 0 | 346 | 94.4 |
| 2021 | 17508 | 8755 | 8753 | 0 | 365 | 99.9 |
| 2022 | 17517 | 8755 | 8757 | 5 | 365 | 100.0 |
| 2023 | 17515 | 8757 | 8758 | 0 | 365 | 100.0 |
| 2024 | 17541 | 8770 | 8771 | 0 | 366 | 99.8 |
| 2025 | 17512 | 8756 | 8756 | 0 | 365 | 100.0 |
| 2026 | 12460 | 6229 | 6230 | 1 | 260 | 71.1 |

### 3.5 2011 ile 2012–2014 ortalaması — aylık

| ay | gözlem 2011 | 2012–14 ort. | <1000 2011 | 2012–14 ort. | <5000 2011 | 2012–14 ort. | BR 2011 | 2012–14 ort. | FG içeren 2011 | 2012–14 ort. | SN 2011 | 2012–14 ort. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1480 | 1482 | 0 | 21.3 | 98 | 146.3 | 100 | 84.0 | 7 | 28.7 | 8 | 102.3 |
| 2 | 1329 | 1359 | 0 | 24.3 | 98 | 138.7 | 91 | 92.3 | 1 | 29.7 | 3 | 87.7 |
| 3 | 1457 | 1487 | 2 | 3.0 | 122 | 41.7 | 89 | 28.7 | 5 | 4.3 | 93 | 29.7 |
| 4 | 1389 | 1438 | 0 | 6.0 | 46 | 41.0 | 34 | 30.7 | 0 | 11.3 | 0 | 0.3 |
| 5 | 1461 | 1487 | 3 | 8.3 | 29 | 72.3 | 29 | 57.3 | 5 | 15.7 | 0 | 0.0 |
| 6 | 1399 | 1438 | 0 | 2.7 | 1 | 26.7 | 1 | 17.0 | 0 | 9.7 | 0 | 0.7 |
| 7 | 1405 | 1453 | 0 | 5.3 | 0 | 33.0 | 0 | 20.3 | 0 | 15.7 | 0 | 0.0 |
| 8 | 1460 | 1467 | 0 | 4.3 | 4 | 55.7 | 0 | 41.7 | 0 | 16.7 | 0 | 0.0 |
| 9 | 1421 | 1439 | 0 | 0.0 | 4 | 11.3 | 4 | 6.3 | 0 | 0.0 | 0 | 0.0 |
| 10 | 1467 | 1478 | 0 | 7.3 | 31 | 59.7 | 18 | 48.3 | 0 | 12.7 | 0 | 0.0 |
| 11 | 1430 | 1430 | 0 | 2.0 | 54 | 61.7 | 55 | 52.7 | 0 | 8.3 | 0 | 0.0 |
| 12 | 1465 | 1484 | 0 | 13.3 | 129 | 99.3 | 113 | 58.3 | 0 | 28.3 | 2 | 77.0 |

### 3.6 2011'in bütün olay gözlemleri

| zaman | görüş | hava | sis_kodu |
|---|---:|---:|---:|
| 2011-03-28T20:20 | 300 | FG | 1 |
| 2011-03-28T20:50 | 300 | FG | 1 |
| 2011-05-13T23:20 | 600 | FG | 1 |
| 2011-05-13T23:50 | 600 | FG | 1 |
| 2011-05-14T00:20 | 600 | FG | 1 | 

## 4. Hedef bileşimi ve SN tanılama altyapısı

### 4.1 Olay gözlemlerinin bileşimi — yıla göre (örtüşen bayraklar)

| yıl | olay gözlemi | FG (alanı kaplayan) | FG-ailesi | SN içeren | FG-ailesi ∧ SN | SN'siz | ne FG-ailesi ne SN |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2011 | 5 | 5 | 5 | 0 | 0 | 5 | 0 |
| 2012 | 75 | 29 | 59 | 30 | 14 | 45 | 0 |
| 2013 | 86 | 61 | 80 | 8 | 2 | 78 | 0 |
| 2014 | 133 | 91 | 133 | 0 | 0 | 133 | 0 |
| 2015 | 119 | 54 | 72 | 47 | 0 | 72 | 0 |
| 2016 | 79 | 34 | 70 | 9 | 0 | 70 | 0 |
| 2017 | 128 | 69 | 105 | 22 | 0 | 106 | 1 |
| 2018 | 84 | 63 | 84 | 0 | 0 | 84 | 0 |
| 2019 | 57 | 47 | 56 | 1 | 0 | 56 | 0 |
| 2020 | 28 | 19 | 28 | 0 | 0 | 28 | 0 |
| 2021 | 96 | 53 | 69 | 27 | 0 | 69 | 0 |
| 2022 | 139 | 60 | 67 | 72 | 0 | 67 | 0 |
| 2023 | 56 | 34 | 37 | 19 | 0 | 37 | 0 |
| 2024 | 36 | 21 | 36 | 0 | 0 | 36 | 0 |
| 2025 | 36 | 15 | 19 | 17 | 0 | 19 | 0 |
| 2026 | 26 | 11 | 25 | 1 | 0 | 25 | 0 |
| **toplam** | 1183 | 666 | 945 | 253 | 16 | 930 | 1 |

### 4.2 Olay gözlemlerinin bileşimi — aya göre

| ay | olay gözlemi | FG (alanı kaplayan) | FG-ailesi | SN içeren | FG-ailesi ∧ SN | SN'siz | ne FG-ailesi ne SN |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 206 | 118 | 131 | 78 | 3 | 128 | 0 |
| 2 | 274 | 112 | 178 | 98 | 2 | 176 | 0 |
| 3 | 131 | 49 | 75 | 56 | 0 | 75 | 0 |
| 4 | 72 | 43 | 72 | 0 | 0 | 72 | 0 |
| 5 | 89 | 70 | 89 | 0 | 0 | 89 | 0 |
| 6 | 46 | 27 | 46 | 0 | 0 | 46 | 0 |
| 7 | 53 | 32 | 52 | 0 | 0 | 53 | 1 |
| 8 | 41 | 26 | 41 | 0 | 0 | 41 | 0 |
| 9 | 19 | 13 | 19 | 0 | 0 | 19 | 0 |
| 10 | 78 | 62 | 78 | 0 | 0 | 78 | 0 |
| 11 | 104 | 82 | 104 | 0 | 0 | 104 | 0 |
| 12 | 70 | 32 | 60 | 21 | 11 | 49 | 0 |

### 4.3 Pozitif onset satırları (Y=1) ve SN

Tanımlar: (a) (t, t+3sa] içindeki herhangi bir :20/:50 gözleminde SN; (b) penceredeki olay gözlemlerinden en az birinde SN; (c) penceredeki ilk olay gözleminde SN. §9.3 satır tanılaması tanım (a)'nın tümleyenini kullanır: "hedef penceresinde hiç SN gözlemi bulunmayan satırlar".

| yıl | Y=1 | (a) pencerede SN | (b) olay gözleminde SN | (c) ilk olay gözleminde SN | SN'siz (a'nın tümleyeni) |
|---|---:|---:|---:|---:|---:|
| 2011 | 12 | 0 | 0 | 0 | 12 |
| 2012 | 179 | 79 | 79 | 79 | 100 |
| 2013 | 134 | 29 | 29 | 29 | 105 |
| 2014 | 139 | 0 | 0 | 0 | 139 |
| 2015 | 216 | 102 | 102 | 102 | 114 |
| 2016 | 145 | 35 | 35 | 35 | 110 |
| 2017 | 157 | 28 | 28 | 28 | 129 |
| 2018 | 117 | 0 | 0 | 0 | 117 |
| 2019 | 112 | 6 | 6 | 6 | 106 |
| 2020 | 54 | 0 | 0 | 0 | 54 |
| 2021 | 124 | 51 | 51 | 51 | 73 |
| 2022 | 240 | 156 | 156 | 156 | 84 |
| 2023 | 73 | 28 | 28 | 28 | 45 |
| 2024 | 58 | 0 | 0 | 0 | 58 |
| 2025 | 90 | 62 | 62 | 62 | 28 |
| 2026 | 66 | 6 | 6 | 6 | 60 |
| 2011–2023 (V1 eğitim dönemi) | 1702 | 514 | 514 | 514 | 1188 |
| **toplam** | 1916 | 582 | 582 | 582 | 1334 |

- Olayına atanamayan pozitif satır: **0** (§5.1: ilk olay gözleminin ait olduğu olaya atama).

§9.3 satır tanılaması evreni (tüm onset satırları, tanım a):

|  | penceresinde SN yok | penceresinde SN var |
|---|---:|---:|
| Y=0 | 265613 | 4711 |
| Y=1 | 1334 | 582 |

### 4.4 Bağımsız olaylar (§5.1, 2011+ tam kayıt) — tümü / ≥ 1 SN / SN'siz

| başlangıç yılı | olay | ≥ 1 SN | SN'siz | ≥ 1 FG-ailesi | ne SN ne FG-ailesi |
|---|---:|---:|---:|---:|---:|
| 2011 | 2 | 0 | 2 | 2 | 0 |
| 2012 | 27 | 11 | 16 | 19 | 0 |
| 2013 | 21 | 4 | 17 | 18 | 0 |
| 2014 | 21 | 0 | 21 | 21 | 0 |
| 2015 | 36 | 16 | 20 | 20 | 0 |
| 2016 | 22 | 5 | 17 | 17 | 0 |
| 2017 | 23 | 3 | 20 | 19 | 1 |
| 2018 | 17 | 0 | 17 | 17 | 0 |
| 2019 | 18 | 1 | 17 | 17 | 0 |
| 2020 | 8 | 0 | 8 | 8 | 0 |
| 2021 | 18 | 6 | 12 | 12 | 0 |
| 2022 | 34 | 19 | 15 | 16 | 0 |
| 2023 | 10 | 3 | 7 | 7 | 0 |
| 2024 | 9 | 0 | 9 | 9 | 0 |
| 2025 | 13 | 9 | 4 | 4 | 0 |
| 2026 | 11 | 1 | 10 | 10 | 0 |
| **toplam** | 290 | 78 | 212 | 216 | 1 |

- Hiçbir olaya atanamayan olay gözlemi: **0**. 

## 5. Zaman damgası bütünlüğü (tüm dosya, filtre öncesi)

| denetim | sayı |
|---|---:|
| toplam satır | 274907 |
| 2011 öncesi satır (analiz dışı) | 1484 |
| dosya sırasında geriye giden zaman damgası | 0 |
| ardışık eşit zaman damgası | 0 |
| yinelenen zaman metni (fazla kopya) | 0 |
| ayrıştırma sonrası yinelenen an (fazla kopya) | 0 |
| zaman metni biçimleri | uzunluk=16: 274907 |
| ızgara dışı (dakika ∉ {20, 50} ya da saniye ≠ 0) | 6 |
| `ay` sütunu ≠ zaman damgasının ayı | 0 |
| `saat` sütunu ≠ zaman damgasının saati | 0 |
| `spread` ≠ sıcaklık − çiy noktası | 0 |
| `sis` ≠ (görüş < 1000 ∨ sis_kodu) yeniden hesabı | 0 |

Izgara dışı satırlar:

| zaman | görüş | hava | sis |
|---|---:|---:|---:|
| 2022-10-02T08:00 | 9999 | -SHRA | 0 |
| 2022-10-02T08:04 | 9999 | -TSRA | 0 |
| 2022-10-04T09:57 | 9999 | — | 0 |
| 2022-10-31T22:56 | 3200 | PRFG | 0 |
| 2022-10-31T23:01 | 900 | BCFG | 1 |
| 2026-08-28T02:06 | 9999 | -TSRA | 0 |

Ardışık gözlem aralıkları (2011+, tekil anlar, sıralı):

| aralık | sayı |
|---|---:|
| < 30 dk | 9 |
| 30 dk | 272851 |
| 31–60 dk (1 eksik adım) | 427 |
| 61–180 dk (2–5 eksik adım) | 109 |
| 181 dk – 24 sa | 22 |
| > 24 sa | 4 |

3 saatten uzun boşluklar: 26 adet. En uzun 15:

| son gözlem | sonraki gözlem | süre (sa) |
|---|---:|---:|
| 2020-04-10T23:50 | 2020-05-01T00:20 | 480.5 |
| 2012-07-14T04:50 | 2012-07-16T05:20 | 48.5 |
| 2012-08-14T04:50 | 2012-08-15T05:20 | 24.5 |
| 2011-07-02T04:50 | 2011-07-03T05:20 | 24.5 |
| 2011-12-31T21:50 | 2012-01-01T06:20 | 8.5 |
| 2024-12-25T20:20 | 2024-12-26T03:50 | 7.5 |
| 2017-01-09T19:20 | 2017-01-10T01:20 | 6.0 |
| 2015-10-31T23:50 | 2015-11-01T05:20 | 5.5 |
| 2014-11-01T23:50 | 2014-11-02T05:20 | 5.5 |
| 2013-11-02T23:50 | 2013-11-03T05:20 | 5.5 |
| 2013-10-25T23:50 | 2013-10-26T05:20 | 5.5 |
| 2011-04-30T20:50 | 2011-05-01T01:50 | 5.0 |
| 2016-12-29T06:20 | 2016-12-29T10:50 | 4.5 |
| 2015-03-27T12:50 | 2015-03-27T16:50 | 4.0 |
| 2011-05-31T20:50 | 2011-06-01T00:50 | 4.0 | 

## 6. Canlı arşiv (`gozlem_arsivi.csv`) ızgara doluluğu

| ölçüt | değer |
|---|---:|
| kapsam | 2026-09-23T13:50 → 2026-09-28T00:50 UTC |
| satır (METAR / SPECI) | 212 / 8 |
| ızgara dışı METAR | 0 |
| beklenen :20/:50 slotu | 215 |
| eksik slot | 3 (%1.40) |
| eksik slotlar | 2026-09-27T02:50, 2026-09-27T04:50, 2026-09-27T16:20 |
