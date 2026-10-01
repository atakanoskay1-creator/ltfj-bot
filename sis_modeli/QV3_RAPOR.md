# QV3 — LVO Hazırlık Safhası'na geçiş modeli (deneysel, canlıda değil)

**Soru:** Şu an LVO Hazırlık şartı yokken, **önümüzdeki 3 saatte** Hazırlık
Safhası'na geçilecek mi?

Şart (TL.007 madde 6.2.a): RVR < 800 m **veya** tavan < 200 ft.

QV3 **canlıya bağlanmaz**; yalnızca V3 için görmek amaçlıdır. Canlı Model A,
onun veri dosyası ve 2024–2026 holdout'u **değişmedi / açılmadı**.

Tekrar üretmek için (repo kökünden):

```
python -m sis_modeli.qv3_hedef   # evren ve yıllık pozitifler
python -m sis_modeli.qv3_egit    # seçim + walk-forward (~8 dk, kararlı seçim dahil)
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
- **Holdout (2024–2026) açılmadı.** Bir modele karar vermeden açılmamalı.
- **Canlıya bağlanmadı.** İzleme dönemi kuralı: model değişikliği yok.
