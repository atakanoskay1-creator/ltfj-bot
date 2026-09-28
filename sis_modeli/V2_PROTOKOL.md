# Sis modeli V2 — deney ve değerlendirme protokolü

**Durum:** DONDURULDU — sürüm 1.0 (28 Eylül 2026). Dondurma, bu sürümü içeren
PR'ın `main`'e merge edildiği commit'tir.
Dondurmadan sonra §5–§9 ve §11–§12'deki karar ve sayısal seçim kuralları
**hiçbir deney sonucu (Deney 0 dahil) görüldükten sonra değiştirilmez** (§15).

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

1. **Gecikme eksikliği:** varyantların gerektirdiği t−60 ve t−120 dk
   gözlemleri **tam o zamanda** mevcut mu (en yakın gözlem kullanılmaz). P(eksik | Y=1) ile P(eksik | Y=0),
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
    (§5.1).
  - Bu birimlerin bağımsız olduğu iddia edilmez; bağımlılığı daha iyi gruplayan
    birimlerdir.
  - Tekrar sayısı: 2000.

### 5.1 Bağımsız olay tanımı (sabit)

Bu protokolde "bağımsız olay" yalnızca şu anlama gelir
(`olay_degerlendirme.bagimsiz_olaylar(kayitlar, etiket="sis", bosluk_saat=3.0)`):

1. Girdi, `hedef.hazirla` çıktısının **tam** kayıt kümesidir (onset filtresi
   uygulanmamış), yalnızca ilgili dönemin satırları.
2. Olay gözlemleri (`sis = 1`) zamana göre sıralanır.
3. Ardışık iki olay gözlemi arasındaki süre **3 saatten uzunsa** yeni olay
   başlar; 3 saat veya daha kısaysa aynı olaya eklenir.
4. Olayın başlangıcı ilk olay gözleminin zamanıdır.

- **Seyreklik kararlarında** (§7.5) bölütleme **yalnızca ilgili dış fold'un
  eğitim yıllarının** satırlarına uygulanır; test dönemine taşan bir olay eğitim
  sınırında kesilmiş hâliyle sayılır. Test dönemi gözlemleri bölütlemeye girmez.
- **Değerlendirmede** (§9.1 ve olay bootstrap'i) bölütleme ilgili değerlendirme
  döneminin satırlarına uygulanır.
- Bir pozitif satır (Y_t = 1), (t, t+3sa] penceresindeki **ilk** olay
  gözleminin ait olduğu olaya atanır.
- `sis_iklim.py`'deki 61 dakikalık gruplama bir iklim sayımı tanımıdır; bu
  protokolde **kullanılmaz**.

## 6. L2 seçimi — iç içe zaman bölmeli doğrulama

- **Izgara (dondurulmuş):** `model.L2_ADAYLARI` = (0,1; 1; 10; 100; 1000; 10000).
  Izgara sonuçlar görüldükten sonra genişletilmez.
- **İç doğrulama blokları:** her dış fold'un eğitim döneminde, en az 3 yıl
  eğitimden sonra gelen **her takvim yılı** bir iç doğrulama bloğudur
  (2017–18 fold'unda 2014, 2015, 2016; …; 2025–26 fold'unda 2014–2024). Her blok
  için iç eğitim = o yıldan önceki bütün yıllar (genişleyen pencere), ambargolu.
- **Seçim ölçütü:** her L2 için bütün iç blokların **havuzlanmış log-loss**'u;
  λ* = en küçük olan. **Eşitlik toleransı:** en iyi değerle arasındaki havuzlanmış
  ortalama log-loss farkı **≤ 1e-4 nat** olan L2'ler eşit sayılır ve bunlardan
  **en büyüğü** seçilir (daha muhafazakâr). Gerekçe (sonuçlardan değil, ölçekten):
  taban oran %0,757'de iklim referansının log-loss'u ≈ 0,0445 nat; 1e-4 bunun
  %0,22'si, LSS'de ≈ 0,002. **Tolerans protokol 1.0 ile dondurulur ve hiçbir
  deney sonucu görüldükten sonra değiştirilmez.**
- **Yakınsama:** bir L2 herhangi bir iç blokta `TekilSistem` ya da `Yakinsamadi`
  verirse o dış fold için elenir. Seçilen L2 ile dış fold'un tüm eğitim
  verisindeki eğitim yakınsamazsa o spesifikasyon **başarısız** sayılır.
- V1 referansı ve bütün V2 varyantları **aynı** prosedürle eğitilir.

## 7. Model spesifikasyonları

### 7.1 V1 referansı (geliştirme karşılaştırması için)
V1'in değişken seti (`gorus, spread, spread_egilim_3, saat, ruzgar_kuzey`), WoE +
L2 lojistik regresyon, §6 prosedürüyle her dış fold'da yeniden eğitilir. Böylece
V1–V2 farkı yalnızca değişkenlerden gelir. V1'in eski yürüyen pencere sonuçları (AP 0,210 /
BSS 0,118, 2015–2023, ambargosuz, tek yıllık iç doğrulama, AP ile L2 seçimi)
**tarihsel V1 sonucudur; V2 karşılaştırmasının kıyas ölçütü değildir.** Kıyas
ölçütü, bu protokolün fold'ları, ambargosu ve L2 prosedürüyle yeniden hesaplanan
V1 referansıdır. Dondurulmuş canlı V1'in aynı satırlardaki
skoru yalnızca **tanılama** olarak raporlanır (2011–2023 ile eğitildiği için
o yılları içeren fold'larda örnek içidir).

### 7.2 Gidişat değişkenleri (a priori)

**İnce görüş bantları** (eğilim hesabı için; indeks 0–6):
`< 1000 · 1000–1500 · 1500–3000 · 3000–5000 · 5000–8000 · 8000–9999 · ≥ 9999` m.

**Eğilim sınıfı** — ince bant indeksindeki değişim, `Δ = indeks(t) − indeks(t−k)`:
`iyileşen/sabit` (Δ ≥ 0) · `1 bant düşüş` (Δ = −1) · `≥ 2 bant düşüş` (Δ ≤ −2).
Gerekçe: metre farkı ölçeğe bağlı (10000→7000 ile 2000→1500 aynı şey değil);
bant geçişi operasyonel eşiklerden türüyor.

**Anlık görüş bantları** (birleşik değişken için; girdi sayımına göre,
sonuca bakılmadan): `1000–3000 · 3000–5000 · 5000–9999 · ≥ 9999` m.
Onset evreninde anlık görüş tanım gereği ≥ 1000 m'dir.

| değişken | tanım | kovalar |
|---|---|---|
| `gv60` | anlık görüş bandı × 60 dk eğilim sınıfı (tek WoE değişkeni) | 4 × 3 = 12 hücre, §7.5 geri dönüş hiyerarşisiyle |
| `dspread_1sa` | spread(t) − spread(t−60 dk) | ≤ −2 · −1 · 0 · +1 · ≥ +2 °C (METAR tam sayı) |
| `egilim120` | 120 dk eğilim sınıfı (anlık görüşle çaprazlanmaz) | iyileşen/sabit · 1 bant düşüş · ≥ 2 bant düşüş |

`egilim120` bilerek anlık görüşle çaprazlanmaz: anlık görüş bilgisi modele
`gv60` üzerinden zaten giriyor; ikinci bir görüş × eğilim tablosu aynı bilgiyi
iki kez sokardı.

### 7.3 Varyantlar (dondurulmuş; üç model, yenisi eklenmez)

| değişken | V1 referansı | V2a | V2b | V2c |
|---|---|---|---|---|
| `gorus` (V1'deki gibi, veriye göre kovalanan WoE) | ✓ | — | — | — |
| `gv60` | — | ✓ | ✓ | ✓ |
| `spread` | ✓ | ✓ | ✓ | ✓ |
| `spread_egilim_3` (tam 3 sa gecikmeli Δspread) | ✓ | ✓ | ✓ | ✓ |
| `saat` (UTC) | ✓ | ✓ | ✓ | ✓ |
| `ruzgar_kuzey` | ✓ | ✓ | ✓ | ✓ |
| `dspread_1sa` | — | — | ✓ | ✓ |
| `egilim120` | — | — | — | ✓ |
| **gereken tam gecikmeler** | — | t−60 | t−60 | t−60, t−120 |

Sınanan sorular:
- **V2a:** kısa dönem görüş gidişatı, anlık görüşün ötesinde bilgi taşıyor mu?
- **V2b:** buna kısa dönem spread gidişatı ek bilgi katıyor mu?
- **V2c:** 60 dakikanın ötesindeki görüş hareketi ek bilgi taşıyor mu?

`spread`, `spread_egilim_3`, `saat` ve `ruzgar_kuzey` V1'deki gibi, her dış
fold'un eğitim verisinde `woe.kova_tablosu` ile kovalanır. Not: V1'in
`spread_egilim_3` değişkeni zaten tam 3 saatlik gecikmeli Δspread
(`hedef.hazirla`); ayrıca bir Δspread_3sa eklenmez. 30 dakikalık hızlı düşüş
işareti bu deney ailesine alınmadı. Sonuçlar görüldükten sonra yeni aday
üretilip aynı geliştirme testine sokulmaz.

### 7.4 Eksik gecikme → V1'e geri dönüş
Bir satırda varyantın gerektirdiği tam gecikmelerden (tabloda son satır) biri
eksikse o satırda V2'nin tahmini yerine V1'in tahmini kullanılır. En yakın
gözlem kullanılmaz. **Hangi V1'in kullanılacağı kilitlidir:**

| aşama | eksik gecikmede kullanılan |
|---|---|
| **geliştirme** (dış fold değerlendirmesi) | **o dış fold'un eğitim verisiyle kurulan V1 referansının** tahmini |
| **ileriye dönük sınav / canlı** | o tarihte **dondurulmuş, canlıdaki V1**'in tahmini |

Geliştirmede canlıdaki dondurulmuş V1 **hiçbir satırda** kullanılmaz: 2011–2023
ile eğitildiği için test yıllarını görmüş olur ve sızıntı yaratır.

Geri dönüş yalnızca **yeni** gidişat değişkenlerinin gecikmeleri (t−60, t−120)
için tetiklenir. V1'den devralınan değişkenlerin eksik değer davranışı V1'deki
gibidir (değer yoksa WoE = 0; ör. `spread_egilim_3` için t−3sa yoksa).

Birincil değerlendirme bu birleşik sistem üzerinden yapılır. Kapsama her varyant için ayrı raporlanır (V2c'nin kapsaması t−120
gerektirdiği için daha düşük olabilir).

### 7.5 Seyrek hücre ve kova kuralları

**Bütün seyreklik ve birleştirme kararları yalnızca ilgili dış fold'un
(ambargolu) eğitim satırlarıyla verilir.** Dış test satırlarının sayıları veya
pozitifleri hiçbir birleştirme ya da geri dönüş kararına girmez. Her fold'da
hangi hücrenin hangi düzeyden değer aldığı rapora yazılır.

**Yeterlilik** (bütün hücre ve kovalar için aynı): en az 500 satır, en az 10
pozitif satır ve en az 5 bağımsız olay. Olay sayısı: §5.1'e göre yalnızca
eğitim yıllarında bölütlenen olaylardan, o hücreye/kovaya **en az bir pozitif
satırı atanmış** olanların sayısı.

**`gv60` geri dönüş hiyerarşisi** — komşu görüş bandıyla birleştirme **yok**:

1. anlık bant × eğilim hücresinin WoE'si, yeterliyse;
2. değilse aynı anlık bandın **eğilimden bağımsız** WoE'si, yeterliyse;
3. değilse satırın kendi görüşüyle **V1 referansının `gorus` WoE'si** (aynı
   fold'da V1 referansı için kurulan tablo).

Üç düzey de aynı WoE formülünü kullanır (Haldane–Anscombe düzeltmesi 0,5,
doğal logaritma; `woe.kova_tablosu` ile aynı), dolayısıyla değerler aynı
log-odds ölçeğindedir.

**Tek boyutlu değişkenler (`dspread_1sa`, `egilim120`):** kovalar birleştirilmez.
Yeterli kova kendi WoE'sini alır; **yeterli olmayan kovanın WoE'si 0'dır.**
WoE = 0, "bu rejim meteorolojik olarak etkisizdir" iddiası **değildir**: bu
fold'un eğitim verisi bu ek değişken için güvenilir bir olabilirlik oranı
üretmeye yetmediği için değişken o satıra **ek kanıt sağlamaz**. Seyrek bir
rejim komşu rejimden kanıt ödünç almaz.

`gv60` farklıdır: `gorus` V1'den çıkarıldığı için doğrudan 0'a düşmek anlık
görüş bilgisini kaybettirirdi; bu yüzden onun hiyerarşisi (hücre → aynı bandın
eğilimden bağımsız değeri → V1 referansının `gorus` WoE'si) aynen kalır.

### 7.6 Sözde kod (dondurulan algoritma)

```text
# Her dış fold için; E = o fold'un ambargolu eğitim satırları, T = test satırları.
# Aşağıdaki bütün sayımlar YALNIZCA E üzerinden yapılır.

INCE_BANT   = [1000, 1500, 3000, 5000, 8000, 9999]      # indeks = kaç eşiği geçtiği
ANLIK_BANT  = [3000, 5000, 9999]                        # 1000–3000 / 3000–5000 / 5000–9999 / ≥9999
YETERLI(h)  = h.satir >= 500 and h.pozitif >= 10 and h.olay >= 5
WOE(h, H)   = ln( ((h.poz + 0.5) / (H.poz + 0.5·k)) / ((h.neg + 0.5) / (H.neg + 0.5·k)) )
              # H: E'nin tamamı, k: o tablodaki kategori sayısı (woe.kova_tablosu ile aynı)

egilim(g_t, g_gecmis):
    d = ince_indeks(g_t) − ince_indeks(g_gecmis)
    return "iyilesen_sabit" if d >= 0 else ("1_bant" if d == −1 else "2+_bant")

gv60_tablosu(E, v1_gorus_tablosu):
    olaylar = bagimsiz_olaylar(E_tam_kayit)    # §5.1; yalnızca eğitim yılları
    for b in 4 anlık bant:
        bant_h = satırlar(E, anlik_bant == b)
        for e in 3 eğilim sınıfı:
            hucre_h = satırlar(E, anlik_bant == b and egilim60 == e)
            if YETERLI(hucre_h):  tablo[b, e] = ("hucre", WOE(hucre_h, E; k=12))
            elif YETERLI(bant_h): tablo[b, e] = ("bant",  WOE(bant_h,  E; k=4))
            else:                 tablo[b, e] = ("v1_gorus", None)
    return tablo

gv60_woe(satir, tablo, v1_gorus_tablosu):
    kaynak, w = tablo[anlik_bant(satir.gorus_t), egilim(satir.gorus_t, satir.gorus_t−60)]
    return w if kaynak != "v1_gorus" else v1_gorus_tablosu.woe(satir.gorus_t)

tek_boyut_tablosu(E, degisken, kovalar):            # dspread_1sa, egilim120
    return {kova: (WOE(kova, E) if YETERLI(kova) else 0.0) for kova in kovalar}
    # birleştirme YOK; 0 = "bu fold bu değişken için ek kanıt sağlayamıyor"

# DEVELOPMENT (dış fold değerlendirmesi):
tahmin_gelistirme(satir, varyant, v1_referansi_bu_fold):
    if any(gerekli gecikme eksik for varyant):   # tam zaman eşleşmesi, en yakın gözlem YOK
        return v1_referansi_bu_fold.olasilik(satir)   # AYNI dış fold'un eğitimiyle kurulmuş
    return varyant.olasilik(satir)

# PROSPECTIVE / PRODUCTION:
tahmin_canli(satir, v2_dondurulmus, v1_dondurulmus):
    if any(gerekli gecikme eksik for v2_dondurulmus):
        return v1_dondurulmus.olasilik(satir)          # o tarihte canlıdaki dondurulmuş V1
    return v2_dondurulmus.olasilik(satir)
```

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

| tarih | ne yapıldı | not |
|---|---|---|
| 28.09.2026 | Protokol 1.0 donduruldu | V2a/V2b/V2c için hiçbir model eğitilmedi, hiçbir V2 skoru hesaplanmadı; Deney 0 çalıştırılmadı. |
| 28.09.2026 | Deney 0 çalıştırıldı (`deney0_veri_denetimi.py`, rapor `V2_DENEY0_RAPORU.md`) | Yalnızca veri sayımları; hiçbir model eğitilmedi, hiçbir performans ölçütü hesaplanmadı. Kararlar: B1 kayıt (§7.4 yönetir; coverage_V2 zorunlu raporlanır), 2011 dışlanmaz, B12 T0 öncesi operasyonel blocker. |
| 28.09.2026 | **§3 uygulama düzeltmesi (B10, §15 kodlama düzeltmesi)** | Mevcut pipeline ızgara dışı 6 kaydı (IEM SPECI) `hedef.hazirla`'ya ve olay bölütlemesine sızdırıyordu: 5 onset satırı + 1 SPECI-yalnız geliştirme olayı (2022-10-31 23:01, 900 m BCFG). V2 geliştirme pipeline'ında §3 gereği ızgara filtresi hedef hazırlama ve olay bölütlemesinden önce uygulanır (`v2_evren.py`). V1 benchmark'ı ve V2 aynı düzeltilmiş evreni kullanır. Veri silinmedi; canlı V1 değişmedi. Sayılar: onset 272.240 → 272.235, Y=1 1.916 → 1.916, bağımsız olay 290 → 289 (2021–22 test 52 → 51). Düzeltme herhangi bir model sonucu görülmeden yapıldı. |
| 28.09.2026 | Ufku tam (6/6) alt küme tanılaması önceden bildirildi | Deney 0 raporu §7.2. Karar vermez; model seçim ölçütü değildir. Deney 1 sonucu görülmeden tanımlandı. |
| 28.09.2026 | *Audit-only:* protokol belgesi sürümleme notu | `44c8e3b2…3bc961` = Protokol 1.0 dondurma artefaktı (kalıcı kayıt). `e6a3098a…1ded8` = Deney 0 audit kayıtları eklenmiş belge. Bundan sonra bu dosyadaki her değişiklik **normatif kural değişikliği** ya da **audit-only değişiklik** diye ayrılır; 1.0'ın karar kuralları değişmedi. |
| 28.09.2026 | V1 referans benchmark'ı — pre-fix diagnostic run | `model.egit` (IRLS) iç bloklarda λ = 0,1 / 1 / 10 / 100'ü `Yakinsamadi` ile eledi; 2023–24 ve 2025–26'da λ=1000 seçildi. İncelenen fit'lerde aynı cezalı amaç sönümlü Newton ile olağan ölçekte bir çözüme yakınsadı. Nihai benchmark değildir; `V2_V1_BENCHMARK_RAPORU.md` Ek B'de kayıtlı. |
| 28.09.2026 | **§15 çözücü düzeltmesi** (audit-only; karar kuralları değişmedi) | Kullanıcı kararıyla uygulama hatası olarak sınıflandırıldı. V2 geliştirme hattı (V1 referansı ve V2a/b/c) `v2_cozucu.egit` (Newton + deterministik adım yarılama; YAKINSAMA 1e-7, AZALIM_GORELI 1e-12, MAKS_ITER 100, ASGARI_ADIM 2⁻³⁰; testle kilitli) kullanır. `model.egit` değişmedi. λ ızgarası, 1e-4 tolerans, iç blok yapısı ve ambargo değişmedi. Düzeltilmiş V1 benchmark'ında hiçbir λ elenmedi; bütün birincil fold'larda λ=100; havuzlanmış OOS LL 0,02735 (pre-fix 0,02741). |
| 28.09.2026 | *Audit-only:* Deney 1 çalıştırıldı (tek çalıştırma; prosedür commit'i `4483836`, sonuçtan önce) | Hiçbir varyant §8 birincil kuralını geçmedi (ΔLL: V2a −0,000340, V2b −0,000315, V2c −0,000328; tek taraflı %98,33 alt sınırlar < 0). Koruma şartları geçildi. **Deney 1 kapandı**; §8 gereği Deney 1b / hazard / sonraki adımlar yok; canlıda V1 kalır. Sonuç görüldükten sonra hiçbir kural değiştirilmedi. Rapor: `V2_DENEY1_RAPORU.md`. |

**Dondurmadan önce aynı veride yapılmış incelemeler** (şeffaflık için; hiçbiri
V2 değişkenlerinin performansına bakmadı):
- Model A'nın 2011–2023 yürüyen pencere değerlendirmesi ve 2024–2026 tarihsel
  sınavı (README).
- Güneyli rüzgâr kalibrasyon testi (`guneyli_sis_deney.py`) ve ay/saat/rüzgâr
  gruplarında V1 kalan sapma taraması (30 gruptan 11'i 1'in dışında).
- Sis/düşük görüş iklimbilimi, hava kodu bileşimi, SN'siz iklim sayımları.
- LTFM–LTFJ eşzamanlılık sayımları.
- Hedef zinciri doğrulaması (224.825 / 1.702) ve yıllara göre onset satırı,
  pozitif satır ve bağımsız olay sayıları; onset evreninin görüş bandı dağılımı
  (yalnızca girdi sayımı).

## 14. Raporlama

- Olumsuz sonuçlar da aynı ayrıntıyla raporlanır.
- Her raporda hedef "düşük görüş/FG olayı" olarak adlandırılır.

## 15. Değişiklik denetimi

- Protokol 1.0 `main`'e merge edildiği anda donar.
- **Karar ve sayısal seçim kuralları** (§5–§9, §11–§12: fold'lar, ambargo,
  bootstrap birimleri, L2 ızgarası ve toleransı, bantlar, yeterlilik eşikleri,
  geri dönüş kuralları, varyantlar, karar eşikleri, koruma şartları, güç
  analizi kuralı, T0) **hiçbir deney sonucu görüldükten sonra değiştirilmez;
  Deney 0 da buna dahildir.**
- Deney 0 bulguları yalnızca raporlanır ve mevcut kurallarla (ör. §7.4 geri
  dönüş, kapsama raporu) karşılanır. Bir bulgu protokolün uygulanamaz olduğunu
  gösterirse (ör. bir fold'da hiçbir L2 yakınsamıyorsa) bu, kuralı değiştirme
  gerekçesi değil, ilgili spesifikasyonun **başarısız** sayılma gerekçesidir.
- Kodlama hatası düzeltmeleri (protokolün söylediğini yapmayan kod) serbesttir;
  her düzeltme ve sonuçları etkileyip etkilemediği bakış kaydına yazılır.
- Açıklama ve yazım düzeltmeleri, anlamı değiştirmediği sürece sürüm numarası
  artırılarak yapılabilir.
