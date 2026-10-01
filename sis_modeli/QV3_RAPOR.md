# QV3 — LVO Hazırlık Safhası'na geçiş modeli (deneysel, canlıda değil)

**Soru:** Şu an LVO Hazırlık şartı yokken, **önümüzdeki 3 saatte** Hazırlık
Safhası'na geçilecek mi?

Şart (TL.007 madde 6.2.a): RVR < 800 m **veya** tavan < 200 ft.

QV3 **canlıya bağlanmaz**; yalnızca V3 için görmek amaçlıdır. Canlı Model A
ve onun veri dosyası **değişmedi**. 2024–2026 holdout'u yalnızca dondurulan
modellerle, önceden yazılmış protokole göre **bir kez** açıldı (aşağıda).

Tekrar üretmek için (repo kökünden):

```
python -m sis_modeli.qv3_hedef   # evren ve yıllık pozitifler
python -m sis_modeli.qv3_egit             # seçim + etkileşim + walk-forward (~3 dk)
python -m sis_modeli.qv3_egit --kararli   # + kararlı seçim (~9 dk)
python -m sis_modeli.qv3_gbm              # GBM + kalibrasyon, walk-forward (~5 dk)
python -m sis_modeli.qv3_dondur           # 2012-2023 ile dondur -> veri/qv3_donmus.json
python -m sis_modeli.qv3_holdout          # 2024-2026 tek atış
```

## Veri ve hedef (`qv3_hedef.py`)

- **Gözlemler:** `veri/ltfj_ozellik.csv.gz` (dondurulmuş, değişmedi).
- **RVR:** `veri/ltfj_rvr.csv.gz` (#139, aynı IEM kaynağı ve istasyon koruması).
  İki dosya `zaman` üzerinden birleştirilir.
- **Dönem:** 2012 ve sonrası; 2011 büyük ölçüde LTBA verisi olduğu için dışarıda.
- **Evren (onset):** o an Hazırlık şartı yok.
  - Geliştirme (2012–2023): **207.504 an, 1.935 pozitif** (~345 bağımsız olay).
  - Taban oranı %0,93.
- **Etiketi ne belirliyor:** büyük ölçüde RVR. 2012'den beri yalnızca 265 gözlemde tavan < 200 ft.

## Değişken seçimi (`qv3_model.py`) — elle değil, veriyle

Aday havuzu (22):

| Grup | Adaylar |
|---|---|
| Görüş | görüş, görüş 1 sa eğilimi |
| RVR | RVR (en düşük / 24 ucu / 06 ucu; raporlanmadıysa 2000 m) |
| Tavan | tavan (yoksa 20 000 ft) |
| Nem | spread ve 1/3 sa eğilimleri, sıcaklık |
| Rüzgâr | hız, kuzey/doğu bileşenleri, 1 sa eğilimi |
| Diğer sürekli | QNH 3 sa eğilimi, saat, ay |
| 0/1 kodlar | parçalı sis (BC/PR/MI/VC FG), BR, yağış |
| Ömerli | hafif KD rüzgârı (0–60°, 3–10 kt); KD × spread ≤ 1 °C (`kd_nemli`) |

Her test döneminde **yalnızca o dönemin eğitim yıllarıyla**:

1. Eğitimin son yılı iç doğrulama, öncesi iç eğitim olarak ayrılır.
2. İç eğitimde IV < 0,02 olanlar elenir; IV'si en yüksek 12 aday kalır.
3. Boş kümeden başlanır. Her adımda iç doğrulama AP'sini en çok artıran
   değişken eklenir. Kazanç < 0,005 ya da 6 değişkene ulaşılınca durur.
4. Seçilen setle model (WoE + L2 lojistik, Model A ile aynı aile) tüm eğitimde
   kurulur. L2 eğitimin son yılında seçilir.

Teknik düzeltmeler (`model.py`'ye dokunmadan):

- **0/1 değişkenler:** sabit `[1]` sınırıyla kovalanır. Eşit frekanslı kovalama
  nadir bir 0/1 değişkeni tek kovaya düşürüp sessizce yok ediyordu.
- **Yakınsama:** güçlü değişkenlerde yakınsama olmazsa bir sonraki daha güçlü
  L2'ye geçilir.

### Seçilen değişkenler

| Test dönemi | Seçim sırası (iç doğrulama AP'si) |
|---|---|
| 2015–16 | görüş (0,18) → saat → **kd_hafif** → spread_egilim_3 (0,25) |
| 2017–18 | görüş (0,09) → ruzgar_kuzey → **kd_nemli** → saat → br (0,25) |
| 2019–20 | **rvr_24** (0,13) → **kd_nemli** → saat → görüş (0,29) |
| 2021–23 | görüş (0,07) → saat → **rvr_min** → spread (0,15) |

Seçilme sıklığı (4 dönem):

- her dönemde: **görüş 4**, **saat 4**;
- Ömerli tarafı: **kd_nemli 2**, kd_hafif 1;
- RVR (24 ucu ya da en düşük): 2;
- birer kez: spread, spread_egilim_3, ruzgar_kuzey, br.

Tek değişkenli bilgi değerinde (IV) her dönemde ilk sırada spread var
(2,6–3,1). Ama görüşle birlikte girince ek katkısı küçük kalıyor; aynı
durum Model A'da da görülmüştü.

## Sonuç (walk-forward 2015–2023, 1.357 pozitif an)

| Model | AP | ROC-AUC | Brier | BSS (ay×saat'e göre) |
|---|---|---|---|---|
| **QV3** (veriyle seçilen set) | **0,165** | 0,905 | **0,00789** | **+0,085** |
| QV3 kararlı seçim (aşağıda) | 0,138 | 0,868 | 0,00803 | +0,069 |
| **GBM** (`qv3_gbm.py`, 22 adayın hepsi; aşağıda) | **0,196** | **0,938** | 0,00825 | +0,043 |
| GBM + Platt, tek yıllık kalibrasyon (ilk deneme) | 0,176 | 0,936 | 0,00805 | +0,066 |
| **GBM + Platt, 3 yıllık kalibrasyon (dondurulan)** | **0,191** | **0,935** | **0,00778** | **+0,097** |
| QV3 + etkileşim terimleri (aşağıda) | 0,163 | 0,908 | 0,00789 | +0,084 |
| Model A'nın 5 değişkeni (bu hedefte yeniden eğitildi) | 0,155 | **0,915** | 0,00795 | +0,077 |
| Mevcut görüş bandı iklimi | 0,113 | 0,792 | 0,00809 | +0,062 |
| Ay × saat iklimi | 0,026 | 0,760 | 0,00862 | 0 |

Dönem dönem AP (QV3 / Model A seti):

| Dönem | QV3 | Model A seti |
|---|---|---|
| 2015–16 | 0,183 | 0,184 |
| 2017–18 | 0,229 | 0,205 |
| 2019–20 | 0,207 | 0,192 |
| 2021–23 | 0,178 | 0,156 |

### Uyarı eşiği karşılığı (QV3, 2015–2023)

Olay = önümüzdeki 3 saatte Hazırlık şartına giden pozitif anlar bloğu
(244 olay). "Olasılık eşiği geçince uyarı" denseydi:

| Eşik | Önceden en az bir uyarı alan olay | Uyarı verilen gün (3.267 gün) | Uyarı anlarının isabeti |
|---|---|---|---|
| %5 | **%84** (205) | 1.060 | %11 |
| %10 | %62 (151) | 499 | %20 |
| %20 | %43 (104) | 227 | %31 |
| %30 | %30 (74) | 147 | %41 |

İsabet, uyarı verilen anlardan sonraki 3 saatte gerçekten Hazırlık
şartının oluşma payıdır.

### Kararlı seçim denemesi (`qv3_model.kararli_secim`) — işe yaramadı

Tek yıllık iç doğrulama gürültülü olduğu için, her test döneminde eğitimin
**her yılı sırayla** iç doğrulama yapıldı ve ileri seçim yeniden koşuldu.
Koşuların en az %50'sinde seçilen değişkenler tutuldu. Eşik sonuçlara
bakmadan sabitlendi.

| Test dönemi | Koşu | Kararlı set | Yakın kalanlar (sıklık) |
|---|---|---|---|
| 2015–16 | 3 | görüş, saat, spread_egilim_3 | kd_nemli, kd_hafif, br %33 |
| 2017–18 | 5 | saat, görüş | spread, spread_egilim_3, ruzgar_kuzey %40 |
| 2019–20 | 7 | saat, görüş, rvr_24 | **kd_nemli %43** |
| 2021–23 | 9 | saat, görüş | **kd_nemli %44**, ruzgar_kuzey %44 |

Sonuç: AP **0,138**. Bu, tek yıllık seçimin (0,165) ve Model A setinin
(0,155) altında. Dönem dönem kararlı seçim hep daha düşük:

| Dönem | Kararlı | Tek yıllık |
|---|---|---|
| 2015–16 | 0,172 | 0,183 |
| 2017–18 | 0,154 | 0,229 |
| 2019–20 | 0,184 | 0,207 |
| 2021–23 | 0,152 | 0,178 |

**Neden:** nem ve rüzgâr değişkenleri (spread ve eğilimi, ruzgar_kuzey,
kd_nemli, kd_hafif) **birbirinin yerine geçiyor**. Her koşuda biri seçiliyor
ama hangisinin seçildiği değişiyor. Bu yüzden tek tek hiçbiri %50'yi
geçemiyor ve set görüş + saate iniyor; o iki değişken de bu bilgiyi
taşımıyor.

Ders: tek tek kararlılık burada yanlış ölçüt. Doğrusu bu ailenin **bir
temsilcisini** kesin tutmak.

Eşiği sonuçlara bakarak düşürmek (örneğin %30) test verisine ayar olurdu;
yapılmadı.

### GBM denemesi (`qv3_gbm.py`) — sıralama belirgin iyi, olasılıklar fazla yüksek

WoE lojistik model her değişkenin etkisini ayrı ayrı öğreniyor; "hafif KD
rüzgârı + düşük spread + gece" gibi etkileşimleri ancak elle türetilmiş bir
değişkenle görebiliyor. Sığ ağaçlar (gradient boosting) bunları kendiliğinden
bulur. Değişken seçimini de ağaçlar yapar: 22 adayın hepsi verildi.

Yöntem: saf Python, yeni kütüphane yok.
- Ağaçlar: histogram tabanlı, derinlik 3, öğrenme hızı 0,1.
- Örnekleme: pozitiflerin hepsi ve negatiflerin %10'u alınır, negatiflere
  ağırlık 10 verilir.
- Ağaç sayısı: eğitimin son yılında AP'ye göre seçilir. Test yılları
  karışmaz.
- **Çapraz kontrol:** aynı veri, aynı dönemler ve aynı ayarlarla
  scikit-learn `HistGradientBoostingClassifier` AP 0,206, AUC 0,940 verdi.
  Saf Python sürüm uyumlu (0,196 / 0,938). sklearn repoya girmedi.

| Dönem | Ağaç | AP | ROC-AUC | BSS |
|---|---|---|---|---|
| 2015–16 | 50 | 0,197 | 0,928 | +0,066 |
| 2017–18 | 100 | 0,253 | 0,959 | +0,087 |
| 2019–20 | 210 | 0,202 | 0,952 | −0,038 |
| 2021–23 | 250 | 0,179 | 0,929 | +0,032 |
| **Toplam** | | **0,196** | **0,938** | +0,043 |

AP, WoE QV3'e göre +0,031, Model A setine göre +0,041. Dönem bazında:
2015–16 ve 2017–18'de WoE QV3'ten açıkça yüksek, 2021–23'te eşit
(0,179'a karşı 0,178), 2019–20'de biraz düşük (0,202'ye karşı 0,207).
ROC-AUC dört dönemin dördünde de en yüksek.

**Ağaçların kullandığı değişkenler** (toplam bölme kazancı payı, dört dönem
ortalaması):

- spread %24, görüş %20, tavan %10, saat %10;
- görüşün 1 saatlik değişimi %7, sıcaklık %7, ay %5;
- rüzgârın doğu bileşeni %3, kd_nemli %3, rüzgârın kuzey bileşeni %2.

Spread, WoE modelinde görüşün gölgesinde kalıyordu. Ağaçlarda en çok
kullanılan değişken oldu: etkisi koşullu (görüşe, saate ve rüzgâra göre
değişiyor), ve ağaçlar bunu yakalıyor.

**Zayıf yan — kalibrasyon:** olasılıklar sistematik olarak fazla yüksek.

- Ortalama tahmin %1,36, gerçekleşen %0,87.
- Model %35 dediğinde gerçekleşen %16, %75 dediğinde %41.
- Bu yüzden Brier skoru WoE modelinden kötü; 2019–20'de BSS negatif.

Muhtemel nedenler: ağaç sayısının AP'ye göre seçilmesi (AP olasılık
düzeyine bakmaz) ve eğitimdeki eski, daha sisli yıllar. Olasılık olarak
gösterilecekse önce kalibre edilmeli; eğitimin son yılında izotonik
kalibrasyon yapılabilir (`kalibrasyon.py` mevcut).

**Uyarı karşılığı:** olasılık ölçekleri farklı olduğu için **aynı uyarı
yükünde** karşılaştırmak gerek.

| Model ve eşik | Uyarı günü (3.267 gün) | Önceden yakalanan olay | Uyarı anlarının isabeti |
|---|---|---|---|
| WoE QV3 %10 | 499 | %62 | %20 |
| GBM %30 | 445 | %60 | %28 |
| WoE QV3 %5 | 1.060 | %84 | %11 |
| GBM %10 | 1.080 | %84 | %15 |

Aynı sayıda uyarı gününde aynı oranda olay yakalanıyor. GBM'in farkı,
uyarı verdiği anların daha isabetli olması (%20 → %28; %11 → %15).

### GBM kalibrasyonu — yüzdeler düzeliyor, ama tek yıl kırılgan

Ağaç sayısının seçildiği iç modelin iç doğrulama yılındaki tahminleriyle
iki harita uyduruldu ve nihai modele uygulandı; test yılları karışmadı.
**Platt** (p' = sigmoid(a·logit p + b), sıralamayı bozmaz) sonuçlar
görülmeden **asıl** yöntem olarak seçildi. İzotonik ikincil yöntem.

| Dönem | Kalibrasyon yılı | Gerçekleşen | Ham ort. | Platt ort. | Ham BSS | Platt BSS |
|---|---|---|---|---|---|---|
| 2015–16 | 2014 | %1,16 | %1,51 | %1,93 | +0,066 | −0,003 |
| 2017–18 | 2016 | %0,82 | %1,35 | %0,58 | +0,087 | **+0,138** |
| 2019–20 | 2018 | %0,63 | %1,35 | %0,94 | −0,038 | +0,060 |
| 2021–23 | 2020 | %0,87 | %1,28 | %0,51 | +0,032 | +0,084 |
| **Toplam** | | %0,87 | %1,36 | **%0,94** | +0,043 | **+0,066** |

Güvenilirlik, Platt sonrası:

| Model ne dedi | Gerçekleşen | n |
|---|---|---|
| %13 | %10 | 1.815 |
| %24 | %21 | 431 |
| %34 | %31 | 248 |
| %45 | %26 | 148 |
| %65 | %28 | 72 |
| %94 | %52 | 48 |

Orta aralıkta isabetli; üst uçta (az örnek) hâlâ fazla iddialı.

- **Kalibrasyon yılı belirleyici.** Olaylı bir yıl (2014) haritayı yukarı,
  sakin bir yıl aşağı itiyor. 2015–16'da Platt durumu kötüleştirdi.
- **Birleşik AP neden düştü (0,196 → 0,176):** dönem içi sıralama aynı
  kalıyor; Platt dönem içinde AP'yi değiştirmez. Ama her dönem farklı yöne
  kaydırıldığı için dönemler birleştirilince sıralama karışıyor. Tek bir
  canlı modelde bu sorun olmaz; AP için dönem değerleri esas alınmalı.
#### Çok yıllı kalibrasyon (`kalibrasyon_ciftleri`) — dondurulan yöntem

Tek yıl yerine eğitimin **son 3 yılının dönem-dışı tahminleri**
kullanıldı (`kalibrasyon.py`'nin Model A için yaptığı gibi). Her yıl,
kendisinden önceki yıllarla eğitilmiş modelle tahmin edildi. Kalibrasyon
seti dönem başına 35–52 bin an. 3 yıl sonuçlara bakılmadan seçildi.

| Dönem | Gerçekleşen | Ham ort. | Platt ort. | Ham BSS | Platt BSS |
|---|---|---|---|---|---|
| 2015–16 | %1,16 | %1,51 | %1,70 | +0,066 | +0,063 |
| 2017–18 | %0,82 | %1,35 | %1,14 | +0,087 | **+0,142** |
| 2019–20 | %0,63 | %1,35 | %0,69 | −0,038 | **+0,112** |
| 2021–23 | %0,87 | %1,28 | %0,67 | +0,032 | **+0,092** |
| **Toplam** | %0,87 | %1,36 | **%1,01** | +0,043 | **+0,097** |

- Birleşik AP **0,191**. Tek yıllıkta 0,176, hamda 0,196. Dönemler artık
  daha tutarlı kaydırılıyor.
- **BSS +0,097, tüm modellerin en iyisi** (WoE QV3 +0,085).

Güvenilirlik, 3 yıllık Platt sonrası:

| Model ne dedi | Gerçekleşen | n |
|---|---|---|
| %1 | %1 | 152.820 |
| %14 | %13 | 1.660 |
| %24 | %19 | 490 |
| %35 | %32 | 246 |
| %45 | %36 | 128 |
| %64 | %56 | 52 |
| %84 | %59 | 34 |

%35'e kadar isabetli; üst uçta hâlâ biraz fazla iddialı, ama az örnek.
İzotonik benzer sonuç veriyor (AP 0,193, BSS +0,099); asıl yöntem
önceden Platt seçildiği için Platt dondu.

### Etkileşim terimli lojistik regresyon — GBM'in farkını açıklamıyor

Soru: GBM'in kazancı etkileşimlerden mi geliyor; basit bir modele
etkileşim eklemek yeter mi? Fiziksel olarak anlamlı üç birleşik kategori,
sonuçlar görülmeden tanımlandı ve aday havuzuna eklendi
(`qv3_model.ETKILESIM`):

- spread bandı × gece;
- spread bandı × görüş bandı;
- spread bandı × rüzgâr hızı bandı.

Seçim aynı kurallarla yapıldı.

- Sonuç: AP **0,163**; etkileşimsiz QV3 0,165, GBM 0,196.
- Etkileşimler 4 dönemin 2'sinde seçildi (2017–18: spread × gece; 2019–20:
  spread × görüş ve spread × rüzgâr). İki dönemde de test AP'si düştü:
  0,229 → 0,199 ve 0,207 → 0,172. İç doğrulamada iyi görünüp testte
  tutmadılar.
- 2015–16'da etkileşim seçilmedi, ama havuz değiştiği için seçim yolu da
  değişti ve AP 0,183'ten 0,165'e indi.
- 2021–23'te seçim aynı kaldı.

Yorum: GBM'in üstünlüğü bu basit ikili etkileşimlerden **gelmiyor**.
Muhtemel kaynaklar iki tane:

- GBM 22 değişkenin hepsini aynı anda kullanabiliyor; WoE modeli seçimle
  4–6 değişkende kalıyor.
- Çok yönlü, eşikli ilişkileri yakalıyor; örneğin "tavan düşük **ve**
  spread küçük **ve** gece".

Okunabilir bir modelle aynı sonucu almak bu iki denemeyle mümkün
olmadı.

**Uyarı:** aynı 2015–2023 testinde artık birkaç yöntem karşılaştırıldı.
En iyisini bu testin sonucuna bakarak seçmek biraz iyimserlik katar. Kesin
karar ancak holdout (2024–2026) açıldığında verilebilir.

## Holdout protokolü (2024–2026) — holdout AÇILMADAN önce yazıldı

**Dondurulan model** (`python -m sis_modeli.qv3_dondur` →
`veri/qv3_donmus.json`):

- **GBM:** 22 aday, derinlik 3, öğrenme hızı 0,1, negatif örnekleme %10.
  - Eğitim: 2012–2023 tamamı.
  - Ağaç sayısı: 2012–2022 ile eğitip 2023'te AP'ye göre.
  - Platt kalibrasyonu: 2021–2023'ün dönem-dışı tahminleriyle.
- **Karşılaştırmalar** (hepsi 2012–2023 ile, aynı kurallarla):
  - QV3 WoE (değişkenler ileri seçimle, iç doğrulama 2023);
  - Model A'nın 5 değişkeni;
  - görüş bandı iklimi;
  - ay × saat iklimi.

**Dondurma çıktısı** (holdout açılmadan, olduğu gibi kaydedildi):

- **GBM:** 50 ağaç. 2023 iç doğrulamasında seçildi; 2023 olayı az bir yıl,
  walk-forward'da bu sayı 50–250 arasındaydı.
  - Platt a = 1,026, b = −0,113; 52.266 kalibrasyon anı.
  - Önem: spread %29, görüş %27, sıcaklık %8, tavan %7, saat %6,
    **kd_nemli %6**.
- **QV3 WoE:** ileri seçim yalnızca `rvr_min_d` ve `sicaklik`'ı seçti
  (L2 10 000).
  - Aynı kural, ama tek iç doğrulama yılı (2023) zayıf olduğu için bu
    karşılaştırma modeli muhtemelen zayıf.
  - Protokol değiştirilmedi. Asıl karşılaştırma Model A setiyle.

**Ölçütler** (`python -m sis_modeli.qv3_holdout`, tek atış):

1. **Asıl:** GBM + Platt'ın AP'si, ROC-AUC, Brier, BSS (ay × saat iklimine
   göre) ve ortalama tahmin / gerçekleşen.
2. **Fark testi:** GBM + Platt ile QV3 WoE ve Model A seti arasındaki AP
   farkı için gün blok bootstrap (500 tekrar, eşli), %5–%95 aralığı.
3. Yıl bazında AP.
4. Uyarı eşikleri (%10, %20, %30):
   - önceden yakalanan olay (1 saatten kısa boşluk aynı olay);
   - uyarı günü;
   - uyarı anlarının isabeti.
5. Güvenilirlik tablosu (10 kova).

**Kural:**

- Sonuç ne çıkarsa çıksın aşağıya aynen yazılır.
- Holdout'a bakılarak model, eşik ya da kalibrasyon değiştirilmez.
- Değiştirilirse holdout "kullanılmış" sayılır, yeni bir test dönemi
  beklenir.
- **Başarı ölçütü** (önceden): GBM + Platt'ın AP'si görüş bandı iklimini
  ve Model A setini geçmeli; BSS > 0 olmalı.

## Holdout sonucu (2024-01-01 – 2026-09-17, tek atış)

- Kapsam: 47.279 an, 423 pozitif (%0,89), **71 olay**, 991 gün.
- Protokol, holdout açılmadan `2dfe8ae` commit'iyle kaydedildi.
- Sonuçtan sonra hiçbir şey değiştirilmedi.

| Model | AP | ROC-AUC | Brier | BSS | Ort. tahmin |
|---|---|---|---|---|---|
| **GBM + Platt** (asıl) | **0,158** | **0,935** | **0,00829** | **+0,057** | %0,51 |
| GBM ham | 0,158 | 0,935 | 0,00825 | +0,061 | %0,61 |
| Model A seti | 0,117 | 0,896 | 0,00865 | +0,016 | %0,81 |
| QV3 WoE | 0,087 | 0,750 | 0,00883 | −0,005 | %0,92 |
| Görüş bandı iklimi | 0,061 | 0,688 | 0,00862 | +0,019 | %0,68 |
| Ay × saat iklimi | 0,028 | 0,787 | 0,00879 | 0 | %0,95 |

Yıl bazında AP:

| Yıl | Pozitif | GBM + Platt | Model A seti | QV3 WoE | Görüş bandı |
|---|---|---|---|---|---|
| 2024 | 149 | **0,125** | 0,081 | 0,056 | 0,031 |
| 2025 | 141 | **0,149** | 0,117 | 0,101 | 0,088 |
| 2026* | 133 | **0,247** | 0,172 | 0,120 | 0,085 |

\* 17 Eylül 2026'ya kadar.

**Eşli fark** (gün blok bootstrap, 500 tekrar, %5–%95):

| Fark | Medyan | Aralık | Pozitif replika |
|---|---|---|---|
| GBM + Platt − Model A seti | **+0,041** | +0,011 … +0,070 | %98 |
| GBM + Platt − QV3 WoE | +0,066 | +0,030 … +0,104 | %100 |

GBM + Platt AP aralığı: 0,120–0,205.

**Başarı ölçütü (önceden yazılan): SAĞLANDI.**

- AP görüş bandı iklimini (0,061) ve Model A setini (0,117) geçti; Model A
  setine farkın aralığı sıfırın üstünde.
- BSS > 0.
- Üç yılın üçünde de en yüksek AP.

**Ama dikkat:**

1. **Walk-forward'dan düşük** (0,191 → 0,158). Beklenen bir düşüş, iki
   nedeni var:
   - aynı test döneminde birkaç yöntem karşılaştırılmasının iyimserliği;
   - dondurulan modelde ağaç sayısının olayı az 2023'e göre seçilmesi
     (yalnızca 50 ağaç).
2. **Bu kez olasılıklar düşük kaldı.** Ortalama tahmin %0,51, gerçekleşen
   %0,89. Walk-forward'daki fazla yüksek tahminin tersi: holdout yılları
   eğitimin son yıllarından daha olaylı. Orta aralık yine makul:

   | Model ne dedi | Gerçekleşen | n |
   |---|---|---|
   | %14 | %17 | 146 |
   | %24 | %25 | 44 |
   | %35 | %47 | 32 |

   Üst uç çok az örnekli.
3. **Uyarı eşikleri** (GBM + Platt):

   | Eşik | Önceden yakalanan olay | Uyarı günü (991 gün) | İsabet |
   |---|---|---|---|
   | %10 | %45 (32/71) | 112 | %24 |
   | %20 | %32 (23/71) | 63 | %32 |
   | %30 | %27 (19/71) | 42 | %36 |

   Olasılıklar düşük kaldığı için aynı eşik walk-forward'dakinden daha az
   olay yakalıyor; isabet ise korunuyor. Canlıda eşik, olasılık değil
   **uyarı yükü** üzerinden belirlenmeli.
4. **QV3 WoE zayıf çıktı.** Dondurmada not edildiği gibi yalnızca 2
   değişken seçilmişti. Tek yıllık iç doğrulamaya dayalı seçim kırılgan.
5. **71 olay az.** Aralıklar geniş; sonuç yönü açık ama büyüklüğü kesin
   değil.

**Sonuç:** GBM, WoE ailesinden (Model A dahil) daha iyi bir LVO Hazırlık
öngörücüsü olarak holdout'u geçti. Canlıya alınması ayrı bir karar. İzleme
dönemi bitince, olasılık seviyesinin (kalibrasyonun) güncel yıllarla
yenilenmesiyle birlikte değerlendirilmeli.

## Yorum

1. **Hedef öğrenilebilir.**
   - İki model de iklimi (AP 0,026) ve "hava zaten kapalı" sezgisini
     (görüş bandı, 0,113) açıkça geçiyor.
   - Taban oranı %0,93 iken AP 0,16–0,23.
2. **QV3 Model A'nın setini 4 dönemin 3'ünde geçiyor**, toplamda AP +0,010.
   - Fark küçük ve güven aralığı hesaplanmadı. Kesin üstünlük diye
     okunmamalı.
   - ROC-AUC'de Model A seti biraz önde (0,915'e karşı 0,905): sıralamayı
     genelde biraz daha iyi yapıyor, en yüksek riskli anları QV3 biraz daha
     iyi yakalıyor.
3. **Ömerli sinyali veriyle seçildi.** `kd_nemli` / `kd_hafif` 4 dönemin
   3'ünde, hiç yönlendirme olmadan girdi. Hafif KD × düşük spread etkileşimi
   (README "Ömerli'den nem taşınması") Hazırlık hedefinde de bilgi taşıyor.
4. **RVR, görüşün yerini tutmuyor; ama 2 dönemde ek bilgi olarak seçildi.**
   RVR yalnızca görüş/RVR < 1500 m iken raporlandığı için çoğu anda boş.
5. **Seçim kararsız; ama bunun nedeni gürültü değil, ikame.**
   - Görüş ve saat dışındaki değişkenler dönemden döneme değişiyor.
   - Kararlı seçim denemesi bunun büyük ölçüde nem/rüzgâr değişkenlerinin
     birbirinin yerine geçmesinden kaynaklandığını gösterdi. Sıklığa göre
     tek tek elemek setin bilgisini düşürdü (AP 0,138).
   - V3 için öneri: değişkenleri **aile** olarak seçmek. Örneğin "nem
     (spread ailesi)" ve "Ömerli (KD × spread)" ailelerinden en az birer
     temsilci zorunlu tutulur, temsilci iç doğrulamayla seçilir.

## Sınırlar

- **Satır düzeyi ölçüm.** Olay düzeyi değerlendirme
  (`olay_degerlendirme.py`) bu hedefe henüz uygulanmadı.
- **Etiket RVR'ın raporlandığı anlara bağlı.**
  - IEM'de SPECI yok; yarım saat arasında kısa süreli RVR düşüşleri kaçar.
  - Pist ucu ayrımı yapılmadı: hangi pistin kullanımda olduğu bilinmiyor,
    `rvr_min` tüm uçların en düşüğü.
- **2021–2023 çiy noktası kusuru** spread'i etkiliyor; bu dönem ayrıca
  temizlenmedi.
- **Holdout (2024–2026)** yalnızca dondurulan modellerle, protokole göre bir kez açıldı (aşağıda).
- **Canlıya bağlanmadı.** İzleme dönemi kuralı: model değişikliği yok.
