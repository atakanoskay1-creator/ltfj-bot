# sis_modeli — LTFJ tarihsel METAR'dan sis/düşük görüş olasılığı

Bu klasör, ana bottan **bağımsız bir alt projedir**. Amacı: LTFJ'nin uzun
dönemli METAR arşivini kullanarak "mevcut koşullarda önümüzdeki N saat
içinde görüşün X metrenin altına düşme olasılığı" sorusuna **yerel, istatistiksel**
bir cevap üretmek.

## Neden ayrı bir alt proje?

Mevcut `ltfj_pist.sis_riski()` elle ayarlanmış bir *sezgisel yöntem* — gerçek
LTFJ taban oranlarına dayanmıyor. Buradaki çalışma onun yerini alabilecek
gerçek sayılar üretmeyi hedefliyor. Ancak eğitim/veri işleme tarafı (büyük
arşiv indirme, `pandas`/`scikit-learn` gibi ağır bağımlılıklar) botun her 15
dakikada bir çalışan hafif akışına **hiçbir şekilde** karışmamalı.

## İzolasyon sözleşmesi

1. **Çalışma anındaki bot bu klasörden hiçbir şey import etmez.** `ltfj_bot.py`,
   `ltfj_sayfa.py`, `ltfj_pist.py` vb. `sis_modeli/`'ye bağımlı değildir.
2. Bağımlılık yönü tek taraflıdır: `sis_modeli/` ana projedeki **test edilmiş**
   METAR ayrıştırıcısını (`ltfj_analiz.metar_coz`) yeniden kullanır; ikinci bir
   ayrıştırıcı yazılmaz.
3. Eğitim çıktısı, ileride bota bağlanacaksa, **saf statik veri taşıyan tek bir
   modül** olarak dışa verilir (tıpkı `ltfj_lvo_referans.py` gibi) — çalışma
   anında `scikit-learn` vb. kurulu olması gerekmez, sadece aritmetik.
4. Bota bağlama kararı **ayrı ve sonraki** bir adımdır. Model doğrulanmadan
   hiçbir şey kullanıcıya gösterilmez.

## Veri kaynağı

Iowa State University — Iowa Environmental Mesonet (IEM) ASOS/AWOS arşivi:
LTFJ'nin ham METAR geçmişini CSV olarak, API anahtarı olmadan sunar.

Ham arşiv **repoya girmez**. `veri_cek.py` indirirken satırları anında
ayrıştırıp yalnızca modele giren alanları sıkıştırılmış bir CSV'ye yazar
(`veri/ltfj_ozellik.csv.gz`), böylece repo küçük kalır ve eğitim ağ erişimi
olmadan tekrarlanabilir olur.

İndirme **GitHub Actions'ta** çalışır (`.github/workflows/sis-veri.yml`,
elle tetiklenir) — geliştirme ortamının ağ politikası harici veri servislerine
izin vermediği için yerelden çekilemez.

## Yöntem (planlanan)

- **Etiket:** gözlem anında görüş < 1000 m (sis) ve < 550 m (LVO seviyesi).
- **Özellikler:** sıcaklık−çiy noktası farkı (spread), rüzgâr hızı, mevcut
  görüş/tavan (süreklilik), ay, UTC saat, QNH.
- **Model:** lojistik regresyon / koşullu olasılık tablosu. Nadir olay olduğu
  için (LVO seviyesi yılda birkaç düzine saat) derin model uygun değil.
- **Doğrulama:** yıl bazlı ayrım (örn. 2003–2020 eğitim, 2021–günümüz test) ve
  basit bir baseline'a (süreklilik + iklim) karşı skor. Bu yapılmadan hiçbir
  sonuç "model çalışıyor" diye sunulmaz.

## Veri kalitesi: bilinen arşiv kusurları

Arşiv ham gözlem değil, **bildirim** kaydıdır; bildirim pratiği değiştiğinde
etiketler de kayar. Ölçülen iki kusur:

**1) Düşük tavan eksik bildirimi (2011–2016).** Bildirilen tavan değerlerinin
500 ft katlarına yığılma oranı %89'dan %72'ye düşerken `<1000 ft` oranı
%1.5'ten %4.5'e çıkıyor. İstanbul'da alçak bulut 3 katına çıkmadı; insan
gözlemcinin "3000" dediği yere ceilometre "900" diyor. Bu yüzden tavan
çalışması yalnızca **2017 sonrası** üzerinde kurulur
(`tavan.REJIM_ILK_YIL`). `<200 ft` bu kaymayı göstermez — VV bildirimi siste
zorunlu ve yoruma kapalıdır.

**2) Sahte doymuş hava (2021–2023).** `spread = 0` (T = Td) oranı:

| dönem | spread=0 oranı | bunların CAVOK olanı | sis oranı |
|---|---|---|---|
| 2011–2020 | %0.6–2.8 | %21.5 | %0.2–0.8 |
| **2021–2023** | **%5.9–12.7** | **%52.3** | %0.3–0.8 |
| 2024–2026 | %0.6–1.0 | %11.0 | %0.2 |

2022'de her ay — haziran, temmuz, ağustos dahil — gözlemlerin %7–24'ü
"doymuş hava" bildiriyor ve bunların yarısından fazlası CAVOK. Doymuş havada
10 km görüş fiziksel bir çelişkidir. 2025'te aynı oran %0–2 ve yalnızca kış
aylarında, yani fiziksel olarak doğru. Sonuç: **2021–2023 çiy noktası
bildirimleri güvenilir değildir.**

Mekanik ayrıntı önemli: hiçbir dönemde **negatif spread yok**, yani bildirim
zinciri Td'yi T'de kırpıyor. Yüksek yanlı bir Td sensörü tam da 0'da böyle
bir sivri üretir. Ve kusur `spread = 0` ile sınırlı değil — ay eşlenmiş
ortalama spread, temiz dönemlerinkinden **0.74 °C düşük** ve bu fark 12 ayın
11'inde aynı yönde. Yani o yıllardaki **tüm** spread değerleri kirli.

Bu yüzden "spread=0 satırlarını at" yanlış bir düzeltmedir; üstelik etiketle
ilişkili bir değişkene göre seçim yapmak (örn. "spread=0 **ve** CAVOK olanları
at") gerçek sis olaylarını da siler ve modeli tehlikeli yönde saldırganlaştırır.
Kırpma bilgiyi geri dönülmez şekilde yok ettiği için yanlılık düzeltilemez de.

### Dışlama denendi ve reddedildi

Geriye tek dürüst seçenek kalıyordu: o yılları eğitimden çıkarmak. Bedeli
255 bağımsız sisli günün 56'sı (%22). Karar kuralı **sonuçlara bakılmadan
önce** ilan edildi (`veri_kalitesi.py`): B yalnızca eşleştirilmiş blok
bootstrap'te (AP_B − AP_A) farkının %5'lik dilimi sıfırın üstündeyse
dondurulur.

| model | Brier×10⁴ | BSS | AP | AP %5–%95 |
|---|---|---|---|---|
| A — mevcut (2011–2023) | 40.85 | 0.092 | **0.184** | 0.098 – 0.292 |
| B — temiz (2021–2023 hariç) | 40.87 | 0.092 | 0.176 | 0.091 – 0.284 |

AP farkı (B − A) **−0.008**, eşleştirilmiş %5–%95 aralığı **−0.014 – −0.002**
— tamamen sıfırın altında. Kural sağlanmadı: **mevcut model korunur.**
Dışlamanın getirdiği temizlik, kaybedilen %22 olayı telafi etmiyor.

Kusurun etkisinin yönü zaten **ihtiyatlı**: sahte doymuş kayıtlar `spread<1`
kovasını seyrelttiği için gerçek doymuş havaya hak ettiğinden *az* kredi
verilir, fazla değil. Modelin 2024–2026 holdout sonucu da bu kusurdan
**sonraki** temiz dönemde ölçüldü.

Not: bu, holdout'un ikinci kullanımıdır. Tek bir ikili karşılaştırma için
açıldı; sonuç "hayır" çıkınca yeni varyant denenmedi — aksi hâli, kuralın
konmasını anlamsız kılardı.

## Düşük tavan (bulut tabanı) çalışması

Tavan, TL.007 madde 6.2.a / 6.3.1.a uyarınca RVR'dan **bağımsız** bir LVO
tetikleyicisi. Ayrı bir tavan modeli kurulup kurulamayacağı ölçüldü:

| eşik | gözlem | bağımsız olay | olay/yıl |
|---|---|---|---|
| CAT II `<200 ft` | 267 | **61** | 3.4 |
| `<500 ft` | 2422 | 352 | 19.6 |
| `<1000 ft` | 8008 | 688 | 38.2 |

LVO için asıl önemli eşikte (`<200 ft`) 61 bağımsız olay var — lojistik
regresyon için kabul edilen 150 olay tabanının altında. Bu yüzden model
değil, `<500 ft` için **koşullu olasılık tablosu** kuruldu
(`tavan.py`, `tavan_tarama.py`, `tavan_tablo.py`).

**Tablonun okuma birimi "kat"tır, mutlak yüzde değil.** Geliştirmede
(2017–2023) öğrenilen tablo holdout'ta (2024–2026) sınandığında hücre
katlarının log korelasyonu **0.986** — sıralama aynen taşınıyor — ama kat
oranlarının medyanı **2.27**: seviye taşınmıyor. Geliştirmede %9.8 olan bir
hücre holdout'ta %14.0 gerçekleşiyor. Yüzde yayınlamak, ölçülmüş 2.3 katlık
hatayı kesin sayı gibi sunmak olurdu.

Holdout skorları (46.850 an, 518 pozitif, 97 ayrı gün):

| yöntem | Brier×10⁴ | BSS | AP |
|---|---|---|---|
| tablo (spread × görüş) | 105.55 | 0.035 | 0.093 |
| ham sis modeli | 105.70 | 0.033 | **0.103** |
| süreklilik (mevcut tavan) | 338.15 | −2.092 | 0.047 |
| iklim | 109.36 | 0.000 | 0.010 |

Dikkat çeken sonuç: **dondurulmuş sis modeli, tavan hedefinde yeni tablodan
daha iyi sıralıyor.** Sis ve düşük tavan birlikte oluyor (CAT II tavanlarının
%86'sı sisli). Tablonun kattığı şey daha iyi bir sıralayıcı değil, tavan
kriterine **doğrudan okunabilir** bir göreli risk ölçeği.

## Model B — görüşsüz atmosferik sis oluşum potansiyeli

Model A (yukarıdaki lojistik regresyon) soruyor: *"mevcut görüş dahil,
önümüzdeki 3 saatte sis riski nedir?"* Bu, görüşü hem girdi hem çıktı olarak
kullanmaz — görüş **T anına ait bir gözlem**, hedef ise **gelecekteki** bir
durum; süreklilik bilgisi (hava zaten kapalı mı?) meşru bir predictor'dır.

**Model B farklı bir soru soruyor:** *"görüş henüz düşmemişken, salt
atmosferik değişkenler (spread, sıcaklık, rüzgâr, saat) yaklaşan sisi ne
kadar önceden haber veriyor?"* Görüş ve türevleri **kesinlikle kullanılmaz**
(`sis_modeli/olusum_alanlar.py` → `YASAKLI`, çalışma zamanında
`dogrula()` ile denetlenir). İki model birbirinin **yerine geçmez** — farklı
sorulara cevap verirler ve sıralanmazlar.

### Değişken tarama ve seçim (`olusum_alanlar.py`, `olusum_egit.py`)

Aday havuzu (`ADAYLAR`): sıcaklık, çiy noktası, spread, spread eğilimi
(1h/3h), rüzgâr hızı/kuzey/doğu bileşeni/eğilimi, saat, ay, QNH, QNH eğilimi.
`sis_kodu` **YASAKLI** — test edildi: yalnızca çıplak, alanı kaplayan FG
kodunda 1 oluyor, yani `sis` etiketinin ikinci OR-koşulunun aynısı (dairesel
predictor). `tavan` (bulut tabanı) ve `hava` sütunundan türetilen
`sis_yakinligi` (BR/nitelikli-FG öncül sinyali) **tartışmalı** kategoride —
aday havuzuna otomatik girmez.

Walk-forward ablasyonla ölçülen (embargo açık, 2011-2023, holdout kapalı):

| küme | AP | BSS |
|---|---|---|
| spread+trend3+rüzgâr_kuzey+saat (4) | 0.037 | −0.008 |
| **+ sıcaklık (5) — SEÇİLEN** | **0.049** | **0.015** |
| + ay yerine (5) | 0.035 | −0.004 (ay ZARARLI) |
| geniş küme (8, zayıf IV'liler hariç) | 0.050 | 0.015 (+0.0003 AP, 3 fazla parametre) |

Sıcaklık eklenmeden model iklimden **kötü** (BSS negatif) — spread'in
"seviyesini" tamamlayan bağımsız bilgi taşıyor. `ay` her kombinasyonda
zararlı. Seçilen küme: `spread, spread_egilim_3, sicaklik, ruzgar_kuzey, saat`
— VIF hepsi <2 (çoklu doğrusallık sorunu yok).

### Sınır embargosu (`bolme.embargo_penceresi`)

Araştırma sırasında **kod üzerinden doğrulanan** bir bulgu: `hedef.hazirla()`
tüm arşivi bölünmeden önce işliyor, bu yüzden bir eğitim satırının ileriye
bakan penceresi dışarıda kalan bir dönemin (bir sonraki fold'un testi veya
holdout) ham verisini kullanmış olabilir — feature sızıntısı DEĞİL, sınıra
yakın birkaç satırın **etiketinin** dışarıdaki veriden etkilenmesi. Model B
(zayıf sinyalli) bu etkiye göreli olarak daha duyarlı olabileceği için
embargo varsayılan olarak **açık**.

### Görüşün kattığı bilgi (no-visibility ablation)

Aynı walk-forward üzerinde, aynı 5 değişken + `gorus`:

| model | AP | BSS |
|---|---|---|
| Model B (görüşsüz) | 0.049 | 0.015 |
| Model B + görüş | 0.182 | 0.103 |

Görüş eklenince AP **+0.133** artıyor — sis riskinin büyük kısmı süreklilik
(mevcut görüş) bilgisinden geliyor, ama görüşsüz haliyle bile iklimden
anlamlı ölçüde iyi (AP 0.049 vs iklim 0.009) — saf atmosferik sinyal **gerçek
ama küçük**.

### Event-level değerlendirme (`olay_degerlendirme.py`)

Satır-düzeyinde AP/Brier, bir olayın yaklaştığı ~6 satırın hepsini ayrı ayrı
pozitif sayar — tek bir olay skoru büyütebilir. `olay_degerlendirme` bağımsız
olayları (>3h boşlukla ayrılan pozitif gruplar) tanımlayıp **olay başına TEK
temsilci tahmin** (onset'ten hemen önceki onset-aday satır) üzerinden
event-level duyarlılık/kesinlik hesaplar — mevcut metrikleri **değiştirmez**,
ek bir katmandır.

### Lead-time (30dk/1h/2h/3h) — `ufuk_deneyi.py`

Soru: *"Görüşü kullanmadan sis oluşumu ne kadar önceden tahmin edilebiliyor?"*
Her ufuk kendi walk-forward döngüsünü çalıştırır (`hedef.hazirla(ufuk_saat=...)`),
holdout hiçbirinde açılmaz. (Sonuçlar için betiği çalıştırın — bu bölüm
metodolojiyi belgeler, sonucu iddia etmez.)

### İzolasyon ve durum

Model B **tamamen `sis_modeli/` içinde** — çalışma anına (ltfj_*.py) hiçbir
şekilde bağlanmadı, hiçbir dondurulmuş modül üretilmedi. Bu bir araştırma
deneyidir; canlı bota entegrasyon **ayrı, sonraki** bir karardır.

## Sınırlar

Bu bir **iklim + süreklilik** modelidir, fizik modeli değildir: yaklaşan bir
cepheyi göremez. ECMWF gibi sayısal hava tahmini ürünlerinin rakibi değil,
tamamlayıcısıdır. Çıktısı **resmî bir tahmin değildir** ve METAR/TAF'ın yerine
geçmez.

## Kullanım

```bash
# Arşivi çek ve türetilmiş veriyi üret (ağ gerekir - Actions'ta çalışır)
python -m sis_modeli.veri_cek --baslangic 2003 --bitis 2026

# Türetilmiş veriyi incele (ağ gerekmez)
python -m sis_modeli.istatistik

# Sis modeli: yürüyen pencere eğitim/değerlendirme
python -m sis_modeli.egit
python -m sis_modeli.holdout_degerlendir        # TEK ATIŞ

# Arşiv kusurları: teşhis ve A/B
python -m sis_modeli.veri_kalitesi
python -m sis_modeli.veri_kalitesi --ab         # HOLDOUT AÇAR

# Düşük tavan: değişken taraması ve olasılık tablosu
python -m sis_modeli.tavan_tarama
python -m sis_modeli.tavan_tablo                # holdout açılmaz
python -m sis_modeli.tavan_tablo --holdout      # TEK ATIŞ

# Model B: görüşsüz atmosferik sis oluşum potansiyeli
python -m sis_modeli.olusum_egit                     # tarama + walk-forward
python -m sis_modeli.olusum_egit --dahil-gorus        # görüş-ablasyon karşılaştırması
python -m sis_modeli.ufuk_deneyi                      # 30dk/1h/2h/3h lead-time
python -m sis_modeli.olusum_holdout_degerlendir       # TEK ATIŞ
```
