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

### Ek veri kaynakları (deneysel, EĞİTİM-ONLY)

Daha yüksek kesinlik arayışıyla, IEM METAR arşivinden **bağımsız** iki yeni
kaynak eklendi. İkisi de sadece geçmişe dönük veri toplar — hiçbiri çalışma
anındaki bota veya donmuş runtime modüllerine (`ltfj_sis_olasilik*.py`,
`ltfj_tavan_tablosu.py`) bağlanmaz. İzolasyon sözleşmesi (yukarıda) burada da
geçerlidir. **Anlamlı bir katkı holdout'ta kanıtlanmadan canlıya alınmaz.**

- **Komşu istasyon METAR'ı** (`veri_cek_komsu.py`, LTFM — İstanbul Havalimanı):
  aynı IEM ASOS mekanizması, farklı ICAO kodu. Amaç: sis/düşük tavan bölgesel
  yayılır; komşu istasyonda birkaç saat önce görülen düşük görüş/tavan bir
  ÖNCÜ (mekansal) sinyal olabilir. → `veri/komsu_ltfm_ozellik.csv.gz`

- **Open-Meteo tarihsel reanalysis** (`veri_cek_acik_meteo.py`, ERA5 tabanlı,
  1940'tan itibaren saatlik, anahtarsız/ücretsiz): yüzey alanları + 925/850 hPa
  basınç seviyesi sıcaklık/nem — klasik radyasyon sisi öncüsü olan ALÇAK
  SEVİYE İNVERSİYON gücünün türetilmesini sağlar. IEM'den bağımsız olduğu için
  ayrıca 2021-2023 çiy noktası kusuru gibi sensör kaymalarını gelecekte
  otomatik çapraz-doğrulamayla yakalamaya da yardımcı olabilir.
  → `veri/acik_meteo_ltfj.csv.gz`

**Durum:** her iki çekici de yazıldı, testleri (mocked HTTP) geçiyor, ayrı bir
GitHub Actions workflow'una (`sis-veri-ek.yml`, elle tetiklenir) bağlandı.

**İlk gerçek çalıştırma (2026-09-21):** Komşu istasyon (LTFM) başarıyla
çekildi — LTFM 2018'de açıldığı için 2003-2017 için 0 gözlem beklenen bir
sonuç, 2018-2026 arası ~138 bin gözlem var. Open-Meteo adımı **hata verdi**:
"Minutely API request limit exceeded" — anahtarsız erişimde Open-Meteo'nun
dakikalık istek limitine, art arda beklemesiz atılan yıl-başı isteklerle
çarpıldı. Önemli olan: **değişken adları doğruydu** (12 yıl sorunsuz
çekilmişti, hata parametre değil hız limitiydi). Düzeltme yapıldı: istekler
artık tek tek değil `YIL_PARCA` (varsayılan 6) yıllık gruplar halinde ve
aralarında bekleyerek atılıyor; hız limiti govdesi diğer kalıcı hatalardan
ayrılıp retry ediliyor. Komşu istasyon adımı workflow'da Open-Meteo'dan önce
çalıştığı ve iş genel olarak hata verince commit adımı atlandığı için LTFM
verisi bu ilk denemede **repoya yazılamadı** — düzeltmeyle birlikte
workflow'un yeniden tetiklenmesi gerekiyor.

**İkinci gerçek çalıştırma (2026-09-21):** hız limiti düzeltmesi çalıştı, ama
içinde bulunulan (henüz bitmemiş) 2026 yılını içeren son dilim "end_date
gelecekte" hatası verdi — düzeltildi (`min(yıl sonu, bugün)`), üçüncü
çalıştırma başarıyla tamamlandı: Open-Meteo 207.960 saatlik gözlem
(2003-01-01 → 2026-09-21), komşu istasyon 138.059 gözlem (2018-11 → 2026-09).

### Birleştirme (join) + tarama sonucu (`veri_birlestir.py`, `tavan_dis_kaynak_tarama.py`)

LTFJ ana arşivi, komşu istasyon ve Open-Meteo'yla zaman damgasına göre en
yakın gözlem eşleştirmesiyle (tolerans: komşu 45dk, Open-Meteo 35dk;
tolerans dışında `None` — sessizce yanlış eşleşme yapılmaz) birleştirildi ve
türetilmiş adaylar (`veri_birlestir.turet()`) tavan<500ft (3 saat ufuk, onset)
hedefine karşı a priori WoE/IV taramasından geçirildi:

| değişken | IV | monoton | yorum |
|---|---|---|---|
| `acik_meteo_nem_2m` (Open-Meteo bağıl nem) | 2.235 | evet | çok güçlü |
| `komsu_tavan_ozellik` (LTFM tavan) | 1.761 | hayır | çok güçlü |
| `komsu_gorus` (LTFM görüş) | 0.900 | hayır | çok güçlü |
| `acik_meteo_bulut_alcak` (alçak bulut örtüsü) | 0.151 | evet | orta |
| `acik_meteo_ruzgar_10m` | 0.096 | hayır | zayıf |
| `komsu_sis_var`, `komsu_lvo_var` | 0.000 | — | işe yaramaz (LTFJ'de ZATEN doğrudan görüş/tavan var, LTFM'nin ikili sis/lvo etiketi buna ek bilgi katmıyor) |
| `inversiyon_925`, `inversiyon_850` | — | — | **kova kurulamadı** — bkz. aşağıdaki bulgu |

**ÖNEMLİ BULGU — basınç seviyesi verisi boş geldi:** Open-Meteo'nun tarihsel
arşiv API'si `925hPa`/`850hPa` parametrelerini isim olarak kabul etti (hata
vermedi, tüm yıllar indi) ama **tüm 208 bin satırda boş** döndürdü. Yüzey
alanları (nem, bulut, rüzgâr) gerçek değer taşıyor — sorun sadece basınç
seviyesi. Demek ki bu uç nokta basınç seviyesi çıkışını hiç desteklemiyor.
**Sonuç: alçak seviye inversiyon gücü fikri bu kaynakla çalışmıyor** —
gerçekleştirilemedi, başka bir veri kaynağı (örn. Forecast API veya gerçek
radiosonde arşivi) gerekiyor.

**Disiplin notu — bu bir keşiftir, doğrulanmış bir model iyileştirmesi
DEĞİLDİR.** `acik_meteo_nem_2m` ve `komsu_tavan_ozellik`'in yüksek IV'si
gerçek bir sinyale işaret ediyor (nem çok yüksekken tavan düşme olasılığı
belirgin artıyor — fiziksel olarak beklenen yön), ama: (1) nadir olayda IV
yapısal olarak şişer (woe.py'nin kendi uyarısı), (2) henüz walk-forward
model eğitimine sokulmadı, (3) holdout'ta AYRICA doğrulanmadı, (4) komşu
istasyon verisi rejim penceresinin (2017+) sadece son ~8 yılını kapsıyor.
Canlıya alma kararı verilmeden önce en az `acik_meteo_nem_2m` ve
`komsu_tavan_ozellik`'in gerçek modele eklenip holdout'ta blok bootstrap ile
sınanması gerekiyor — bu adım henüz yapılmadı.

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

### Tablo çifti güncellendi: sis_olasilık × tavan_özellik

Yukarıdaki bulgu (sis modeli tabloyu tek başına geçiyor) uzun süre bir
karşılaştırma notu olarak kaldı, hiç aksiyona dönüşmedi: `sis_olasilik`
`ADAY_CIFTLER`'da hiçbir çiftin **ekseni** olarak denenmemişti — sadece
rakip bir yöntem olarak ölçülüyordu. `spread`'in aday listesindeki tüm
eşleriyle (görüş, tavan_özellik, saat, rüzgâr_kuzey) simetrik olacak
şekilde `sis_olasilik` da eklendi (a priori, sonuca bakılmadan — `spread`
zaten hangi partnerlerle test ediliyorsa `sis_olasilik` da AYNI partnerlerle
test edildi, tek bir çift önceden seçilip kazanması beklenmedi).

**Gelişme içi seçim** (holdout'a dokunmadan): `sis_olasilık × tavan_özellik`
açık farkla kazandı (AP 0.111, eski şampiyon spread×görüş'ün 0.082'sini
geçti). Bu adım **iyimser** olabilir — `sis_olasilik` o dönemde (2017-2023)
Model A'nın kendi eğitim döneminin İÇİNDE, yani örnek içi.

**Holdout doğrulaması (2024-2026, bu karşılaştırma için TEK ATIŞ #2 — ilk
holdout açılışı yukarıdaki spread×görüş tablosu içindi):**

| yöntem | Brier×10⁴ | BSS | AP |
|---|---|---|---|
| **tablo (sis_olasılık × tavan_özellik) — YENİ** | **104.87** | **0.041** | **0.096** |
| tablo (spread × görüş) — ESKİ | 105.55 | 0.035 | 0.093 |
| ham sis modeli (kalibresiz) | 105.70 | 0.033 | 0.103 |
| kalibre sis modeli | 104.97 | 0.040 | 0.088 |

Yeni çift, eski tabloyu **üç metrikte de** (Brier, BSS, AP) geçiyor — gerçek
ama mütevazı bir kazanç. Ham sis modeli AP'de hâlâ hafifçe önde (0.103), ama
yeni tablo Brier ve BSS'te ondan da iyi — yani tablo formatının kattığı
kalibrasyon (büzülme + iki eksenli hücreleme) ham skordan daha güvenilir
olasılıklar üretiyor. Kat yapısının holdout'a taşınması da önceki tabloyla
aynı örüntüde: log korelasyon 0.935 (sıralama taşınıyor), kat oranı medyanı
2.17 (seviye taşınmıyor — zaten bilinen, ayrı bir sorun değil).

**Durum:** ölçüldü ve doğrulandı, ama HENÜZ canlıya bağlanmadı
(`ltfj_tavan_tablosu.py` hâlâ eski spread×görüş çiftini kullanıyor). Canlıya
almak, çalışma anı modülünün artık `sis_olasilik` değerini de (zaten
`ltfj_sis_olasilik.olasilik()` ile hesaplanıyor, sis kartı için) girdi olarak
alması demek — izolasyon sözleşmesini bozmaz (hâlâ sadece `math`), ama
çağıran tarafın (`ltfj_sayfa.py`) iki modülün çıktısını birbirine
bağlaması gerekir.

### Dış kaynak adayları tabloya eklendi — kazanamadı (negatif ama bilgilendirici sonuç)

`tavan_dis_kaynak_tarama.py`'nin tek değişkenli taramasında `acik_meteo_nem_2m`
(IV 2.235) ve `komsu_tavan_ozellik` (IV 1.761) güçlü çıkmıştı. Bu ikisi,
`sis_olasilik`'in eklenmesiyle AYNI disiplinle (a priori, spread'in orijinal
eş kümesiyle simetrik: görüş, tavan_özellik, saat, rüzgâr_kuzey, + ayrıca
sis_olasilik'in kendisiyle ve birbirleriyle — toplam 13 yeni çift)
`ADAY_CIFTLER`'a eklendi ve **gerçek** iki-değişkenli tabloya sokuldu
(`dis_kaynak_ekle()`).

**Geliştirme içi seçim sonucu (holdout'a DOKUNULMADI):**

| çift | AP | Brier×10⁴ |
|---|---|---|
| **sis_olasılık × tavan_özellik — MEVCUT ŞAMPİYON** | **0.111** | **77.64** |
| acik_meteo_nem_2m × sis_olasılık — EN İYİ YENİ | 0.103 | 77.99 |
| sis_olasılık × saat | 0.103 | 77.93 |
| komsu_tavan_özellik × sis_olasılık | 0.099 | 78.43 |
| *(kalan 21 çift, hepsi daha düşük)* | | |

**Sonuç: hiçbir dış kaynak çifti mevcut şampiyonu geçemedi.** En iyi yeni
aday (`acik_meteo_nem_2m × sis_olasılık`, AP 0.103) ikinci sırada — yakın
ama önde değil. Şampiyon değişmediği için **holdout açılmadı** (TEK ATIŞ
kuralı: yeni bir aday kazanmadıkça holdout'u tüketmenin gerekçesi yok).

**İstatistiksel yorum — neden yüksek tekil IV, ikili tabloda kazanmadı:**
Bu, ders kitabı örneği bir "artık bilgi" (marginal information) durumu.
`acik_meteo_nem_2m`'in TEK BAŞINA IV'si yüksekti çünkü nem, sisin fiziksel
öncüsü — ama `sis_olasilik` (Model A'nın çıktısı) zaten nem dahil birçok
METAR değişkenini bir araya getiren bir bileşik skor. İki değişken
ÇAKIŞAN bilgi taşıyorsa (kolinerlik), ikinci değişkenin TEKİL gücü yüksek
olsa bile BİRLİKTE kullanıldığında kattığı ARTIK bilgi küçük olur — tam
olarak burada gözlenen. `komsu_tavan_özellik` için ayrıca ikinci bir kısıt
var: 2018 öncesi veri yok (LTFM o yıl açıldı), yani rejim penceresinin
(2017+) ilk ~1.5 yılı bu eksende bilgisiz.

**Bu, "veriyi artırmak işe yaramıyor" anlamına GELMEZ** — anlamı şu: basit
iki-eksenli tablo mimarisi, zaten güçlü olan `sis_olasilik`'in üstüne bu
iki değişkenin kattığı payı yakalayamıyor. Gerçek bir kazanç için muhtemelen
gereken, ikiden fazla değişkeni BİRLİKTE (lojistik regresyon gibi düzgün
çok-değişkenli bir model) ağırlıklandırmak — tablo yönteminin kendi
sınırı (bkz. dosya başı: "az parametre, her hücre doğrudan okunabilir"
tercihi tam da bu esnekliği feda ediyor). Bu, ayrı ve daha büyük bir
mimari deney gerektirir, burada yapılmadı.

### Çok değişkenli model (`tavan_dis_kaynak_model.py`) — HOLDOUT'TA DOĞRULANDI

Yukarıdaki tablo denemesi kazanamayınca, aynı adayları GERÇEKTEN çok
değişkenli bir modelde (tablo değil, `model.py`nin sis modelinde kullanılan
aynı IRLS/WoE lojistik regresyonu) test etmek için ayrı bir betik yazıldı.
TEMEL = `spread, görüş, tavan_özellik, saat, rüzgâr_kuzey, sis_olasılık`
(tablo denemesindeki "hub" değişkenlerinin TAMAMI BİRLİKTE) + dış kaynak
adayları (`acik_meteo_nem_2m`, `komsu_tavan_ozellik`) tek tek ve birlikte
eklendi.

**VIF (çoklu doğrusal bağlantı) — kolinerlik iddiası SAYISALLAŞTIRILDI:**
`sis_olasılık` (VIF 14.29) ve `spread` (VIF 11.00) birbiriyle güçlü kolineer
— ama `acik_meteo_nem_2m` (VIF 2.85) ve `komsu_tavan_ozellik` (VIF 1.02)
**DEĞİL**. Bu, yukarıdaki "kolinerlik nedeniyle kazanamadı" hipotezini KISMEN
düzeltiyor: asıl sorun kolinerlik değil, tablo formatının yapısal sınırıymış
(en fazla iki eksen birleştirebilmesi).

**Geliştirme içi, eşleştirilmiş gün bazlı blok bootstrap** (aynı fold/gün
örneklemesi, `veri_kalitesi.eslesmis_fark_araligi`):

| spesifikasyon | AP | AP farkı (TEMEL'e göre) | %5–%95 |
|---|---|---|---|
| TEMEL | 0.091 | — | — |
| TEMEL + nem | 0.127 | +0.036 | +0.020 – +0.052 ✓ |
| TEMEL + komşu tavan | 0.103 | +0.012 | −0.002 – +0.029 |
| **TEMEL + ikisi** | **0.133** | **+0.041** | **+0.009 – +0.074 ✓** |

`TEMEL + ikisi` eşleştirilmiş aralıkta TEMEL'i geçti — TEK ATIŞ kuralına göre
holdout açmayı hak eden bir aday.

**Holdout doğrulaması (2024-2026, TEK ATIŞ — bu betik için #1):**

| spesifikasyon | Brier×10⁴ | BSS | AP | AP %5–%95 |
|---|---|---|---|---|
| TEMEL | 104.09 | 0.048 | 0.114 | 0.086 – 0.149 |
| **TEMEL + ikisi** | **102.47** | **0.063** | **0.136** | **0.104 – 0.178** |

Eşleştirilmiş AP farkı (holdout): **+0.022, %5–%95: +0.000 – +0.043** —
alt sınır sıfırın hemen üzerinde (sınırda ama pozitif), **kural sağlandı**.
Geliştirmedeki kazanç (+0.041) holdout'ta küçüldü (+0.022) — beklenen bir
küçülme (geliştirme-içi seçim her zaman hafif iyimserdir) ama **yön aynı
kaldı ve aralık sıfırı içermedi**. AP'de holdout'ta ~%19 görece artış
(0.114 → 0.136), BSS'te ~%31 görece artış (0.048 → 0.063).

**Bu, oturumun en güçlü, holdout-doğrulanmış bulgusu** — önceki
`sis_olasılık × tavan_özellik` tablo eklemesinden (holdout AP 0.093 → 0.096,
~%3 görece artış) daha büyük bir kazanç.

**KRİTİK MİMARİ FARK — canlıya almadan önce mutlaka değerlendirilmeli:**
Önceki denemelerin (sis_olasılık, tablo çiftleri) hepsi çalışma anında
ZATEN mevcut olan verilerden (METAR'ın kendisi + dondurulmuş `ltfj_sis_
olasilik.olasilik()`) üretiliyordu — hiçbiri yeni bir dış bağımlılık
gerektirmiyordu. **Bu kazanç FARKLI**: `acik_meteo_nem_2m` ve
`komsu_tavan_ozellik` canlı tahmin sırasında GERÇEK ZAMANLI olarak
Open-Meteo ve IEM'den (LTFM) çekilmesi gerekir — yani bot her tahmin
döngüsünde iki yeni dış API'ye bağımlı hale gelir. Bu, projenin baştan
beri koruduğu "çalışma anı sadece `math` import eder, ağa çıkmaz" izolasyon
sözleşmesini GENİŞLETMEK demektir: yeni hata modları (API çökmesi, hız
limiti — tam da bu oturumda karşılaşılan türden), gecikme, ve canlı
kullanıcı deneyiminin üçüncü taraf servislerin çalışma süresine bağlanması.
Canlıya alma kararı **istatistiksel doğrulamadan ayrı, ek bir mimari karar**
gerektirir.

**Risk azaltımı: gevşek bağlı önbellekleyici (`ltfj_dis_kaynak_cache.py`).**
Yukarıdaki riski (özellikle bütçe çakışması ve tek nokta arızası) azaltmak
için ayrı bir önbellekleme katmanı yazıldı: Open-Meteo (gerçek zamanlı
Forecast API, arşiv API'si DEĞİL) ve komşu istasyon (LTFM, `ltfj_rasat.py`
yeniden kullanılarak) kendi bağımsız zamanlamasında (`dis-kaynak-onbellek.yml`,
ana botun 15 dk'lık döngüsüyle SENKRONİZE DEĞİL) çekilip
`dis_kaynak_cache.json`'a yazılır. Ana bot bu dosyayı YEREL olarak okur,
asla kendisi ağa çıkmaz. Bayatlık kontrolü (varsayılan 45 dk) ve kaynak
başına kısmi hata toleransı var — bir kaynak çökerse diğerini kirletmez,
ikisi de bayatsa okuma fonksiyonu None döner (TEMEL'e düşme sinyali).

**CANLIYA BAĞLANDI (`ltfj_tavan_dis_kaynak.py`).** Model, `--holdout --dondur`
ile egitim_tum (embargo'lu geliştirme, holdout sınırına kadar — 2024-2026'ya
dondurma sırasında bile dokunulmadı, `ltfj_sis_olasilik.py` ile AYNI
disiplin) üzerinde dondurulup GERİ DÜŞMELİ (TEMEL/GENİŞ) bir çalışma anı
modülüne taşındı, `ltfj_lvo_farkindalik.tavan_dis_kaynak_notu()` ile LVO
farkındalık paneline (dördüncü not olarak, mevcut üç notun YANINA, hiçbirini
DEĞİŞTİRMEDEN) bağlandı. Dış kaynak taze/mevcutsa GENİŞ model, değilse
sessizce TEMEL model kullanılır — hata vermez.

**Dürüstlük notu — GENİŞ modelde bir supresör etkisi var:** `sis_olasilik`
katsayısı GENİŞ modelde NEGATİF (-0.079, TEMEL modelde +0.093) — VIF
taramasında görülen sis_olasilik/spread kolinerliğinin (14.29/11.00) beklenen
bir sonucu, `tanilama.isaret_kontrolu`'nün "sağlıklı katsayı pozitiftir"
kuralını ihlal ediyor. Agrege holdout performansı (AP/BSS) yine de gerçek ve
doğrulanmış; ama GENİŞ model TEMEL kadar temiz yorumlanamıyor. Gizlenmedi,
hem kod içi dokümantasyonda hem burada açıkça not edildi.

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

Walk-forward (2011-2023) ve nihai holdout (2024-2026, TEK ATIŞ) üzerinde,
aynı 5 değişken + `gorus`:

| model | walk-forward AP | walk-forward BSS | **holdout AP** | **holdout BSS** | holdout AP %5–%95 |
|---|---|---|---|---|---|
| Model B (görüşsüz) | 0.049 | 0.015 | **0.075** | **0.028** | 0.043 – 0.122 |
| Model B + görüş | 0.182 | 0.103 | **0.184** | **0.095** | 0.101 – 0.295 |
| iklim | 0.009 | 0.000 | 0.005 | 0.000 | 0.003 – 0.010 |
| basit kural (mevcut sezgisel) | 0.038 | −0.431 | 0.048 | −0.538 | 0.015 – 0.035 |

Görüş eklenince holdout AP **+0.110** artıyor (walk-forward'da +0.133 idi -
tutarlı büyüklükte). Güven aralıkları **çoğunlukla ayrışıyor** (görüşsüz üst
sınırı 0.122, görüşlü alt sınırı 0.101 - dar bir örtüşme var ama nokta
tahminleri belirgin farklı) - sis modelinin süreklilik baseline'ına karşı
tam örtüşen aralığından (bkz. Bölüm 9, ana metodoloji) daha net bir ayrışma.

**Model B (görüşsüz) holdout'ta iklimden anlamlı ölçüde iyi** (BSS 0.028,
pozitif) - saf atmosferik sinyal küçük ama gerçek ve holdout'ta da
DOĞRULANDI (walk-forward'a göre biraz daha güçlü çıktı - küçük holdout
örnekleminde (214 pozitif) beklenen varyans dahilinde). "Basit kural"
(mevcut sezgisel yöntemin özü) burada da iklimden KÖTÜ (BSS negatif) -
sis modelinde de gözlenen aynı örüntü.

**Kalibrasyon (holdout):** tüm tahminler %10'un altında kaldı (ort. tahmin
%0.58, gerçekleşen %0.45) - hafif aşırı güvenli ama yakın.

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
holdout hiçbirinde açılmaz.

**Ölçülen sonuç — beklenenin TERSİ yönde:**

| ufuk | n | poz | olay | taban | AP | AP/taban | BSS | LSS | LSS\|saat | ROC-AUC |
|---|---|---|---|---|---|---|---|---|---|---|
| 30dk | 155.634 | 250 | 252 | %0.161 | 0.011 | 6.85 | 0.005 | 0.145 | 0.103 | 0.898 |
| 1h | 155.634 | 474 | 256 | %0.305 | 0.021 | 6.90 | 0.010 | 0.169 | 0.122 | 0.901 |
| **2h** | 155.634 | 871 | 256 | %0.560 | 0.038 | 6.79 | 0.004 | **0.194** | **0.145** | 0.903 |
| 3h | 155.634 | 1238 | 256 | %0.795 | **0.049** | 6.16 | 0.015 | 0.190 | 0.139 | 0.891 |

#### LSS eklendikten sonra bu tablo YENİDEN OKUNDU

`LSS` (log-olabilirlik beceri skoru) ve saate koşullu referans sonradan
eklendi (bkz. `degerlendir.log_skill` / `kosullu_iklim`); gerekçe Jewson
(2004) ve Benedetti (2009): olay olasılığı çok küçükken Brier Score
çözünürlüğünü kaybeder. Bu projenin taban oranı %0.8'in altında.

**Eklenmesi üç şeyi değiştirdi:**

**1. BSS'in bu tabloda gürültü ölçtüğü doğrulandı.** BSS 2 saatte (0.004)
hem 1 saatten (0.010) hem 30 dakikadan (0.005) *düşük* çıkıyor — AP
monoton artarken. LSS'te böyle bir kırılma yok: 0.145 → 0.169 → 0.194 →
0.190. Tahmin edilen kusur, tahmin edildiği yerde çıktı.

**2. Olasılık kalitesi 2 saatte tepe yapıyor, 3 saatte değil.** AP (sıralama
gücü) 3 saate kadar artmaya devam ediyor ama LSS (olasılığın kendi
kalitesi) 2 saatte tepe yapıp düşüyor. İkisi farklı soru soruyor:
"satırları riske göre sıralayabiliyor mu" ile "ürettiği olasılık sayısı
doğru mu".

**3. AP'nin ufukla artması büyük ölçüde PREVALANS YAN ETKİSİ.** Rastgele
bir sınıflandırıcının AP'si taban orana eşittir; ufuk genişledikçe olay
sıklaşıyor (%0.161 → %0.795), dolayısıyla AP doğal olarak yükseliyor.
Taban orana bölündüğünde (`AP/taban`) sıralama gücü 30dk–2h arasında
**düz** (~6.8) ve 3 saatte 6.16'ya *düşüyor*.

> **Bu, yukarıdaki "performans ufuk uzadıkça artıyor" ifadesini
> düzeltir.** Ham AP artıyordu; taban orana göre normalize edilmiş
> sıralama gücü artmıyor.

#### Eşli bootstrap: hangi fark gerçek? — `--bootstrap 200`

Yukarıdaki nokta tahminleri tek başına yeterli değildi. Ufuklar **aynı
günlerin havasını** paylaştığı için (dt kümeleri birebir aynı) gün-blok
**eşli** bootstrap yapıldı: her replikada dört ufuk da aynı gün örneği
üzerinde hesaplanıyor, fark doğrudan ölçülüyor. İki marjinal aralığın
örtüşmesi "fark yok" demek değildir — bu koşu bunun ders kitabı örneğini
de verdi (aşağıya bkz.).

```
python -m sis_modeli.ufuk_deneyi --bootstrap 200
```

**LSS** (%5–%95, 200 tekrar):

| ufuk | LSS | aralık | | fark (a−b) | medyan | aralık | karar |
|---|---|---|---|---|---|---|---|
| 30dk | 0.145 | [0.125, 0.165] | | 30dk−1h | −0.023 | [−0.031, −0.016] | **ayırt edilir** |
| 1h | 0.169 | [0.153, 0.186] | | 30dk−2h | −0.048 | [−0.076, −0.016] | **ayırt edilir** |
| 2h | 0.194 | [0.167, 0.220] | | 30dk−3h | −0.045 | [−0.072, −0.016] | **ayırt edilir** |
| 3h | 0.190 | [0.162, 0.214] | | 1h−2h | −0.025 | [−0.050, 0.004] | belirsiz |
| | | | | 1h−3h | −0.021 | [−0.044, 0.005] | belirsiz |
| | | | | **2h−3h** | **0.004** | **[−0.004, 0.010]** | **belirsiz** |

**AP/taban** (%5–%95, 200 tekrar):

| ufuk | AP/taban | aralık | | fark (a−b) | medyan | aralık | karar |
|---|---|---|---|---|---|---|---|
| 30dk | 7.136 | [6.155, 8.556] | | 30dk−1h | 0.285 | [−0.087, 0.815] | belirsiz |
| 1h | 6.876 | [5.979, 8.188] | | 30dk−2h | 0.320 | [−1.240, 2.266] | belirsiz |
| 2h | 6.858 | [6.067, 8.163] | | 1h−2h | 0.041 | [−1.464, 1.581] | belirsiz |
| 3h | 6.195 | [5.496, 7.317] | | 1h−3h | 0.715 | [−0.738, 2.297] | belirsiz |
| | | | | **2h−3h** | **0.636** | **[0.374, 1.038]** | **ayırt edilir** |

**Ne çözüldü, ne çözülmedi:**

1. **30 dakika kesin olarak en zayıf ufuk.** LSS'te üç kıyasın üçü de
   0'ı dışlıyor, replikaların %0.0'ında 30dk öne geçmiyor. Yukarıdaki
   yavaş-eğilim açıklaması **doğrulandı**.

2. **LSS, 1h / 2h / 3h arasını AYIRT EDEMİYOR.** Nokta tahmini 2 saatte
   tepe yapıyor ama 2h−3h farkı [−0.004, 0.010], yani sıfırı içeriyor
   (replikaların %78.5'i 2h lehine — zayıf). *Bu, bu bölümün ilk
   yazımındaki "LSS ve AP/taban birlikte 2 saati işaret ediyor"
   ifadesini ÇÜRÜTÜR: LSS bu konuda sessiz.*

3. **AP/taban'da 2h > 3h GERÇEK.** Fark 0.636, aralık [0.374, 1.038],
   replikaların %100'ü aynı yönde. 3 saatteki sıralama gücü düşüşü
   gürültü değil.

4. **Eşli bootstrap'in neden gerekli olduğunun kanıtı bu tabloda:**
   AP/taban'ın marjinal aralıkları neredeyse tamamen örtüşüyor
   (30dk [6.155, 8.556] ile 3h [5.496, 7.317]), ama eşli 2h−3h farkı dar
   ve sıfırı dışlıyor. Marjinal aralıklara bakıp "hiçbir fark yok"
   denseydi gerçek bir etki kaçırılacaktı.

**Toparlarsak:** "3 saat en iyi ufuk" iddiası desteklenmiyor — 3 saat,
sıralama gücünde 2 saatten ölçülebilir biçimde *kötü*. "2 saat en iyi"
iddiası ise yalnızca AP/taban'a dayanıyor; LSS onu doğrulamıyor. En
savunulabilir okuma: **anlamlı ufuk 1–3 saat aralığı, 30 dakika değil;
bu aralık içinde 2 saat lehine tek yönlü bir kanıt var.**

**Beceri ne kadarı sadece günlük döngü?** `LSS|saat` sütunu, referansın
saati bildiği (dolayısıyla günlük döngüyü referansa devrettiği) durumu
ölçer. Modelin değişkenleri arasında `saat` de var, bu yüzden düz taban
orana göre ölçülen becerinin bir kısmı "model günlük döngüyü öğrendi"
demek. Fark her ufukta **%25–29**. Geriye kalan (~0.14) günlük döngünün
ÖTESİNDE, gerçekten atmosferik olan beceri — mütevazı ama açıkça pozitif.

### Katmanlı model: TEK mi, mevsim/saate göre AYRI mı? — `katmanli_deney.py`

Yabra ve ark. (2026) veriyi sis olasılığı yüksek/düşük aylara ve saatlere
bölüp ayrı modeller eğitmenin tek genel modeli geçtiğini buldu — ama
**yalnızca 2 saat ve üzeri ufuklarda** (2 saatte %20'ye varan kazanç);
1 saatte geçmedi, çünkü orada süreklilik baskın ve bölme sadece örnek
sayısını düşürüyor. Aynı deney bu projenin verisiyle tekrarlandı.

Türetilen katmanlar (yalnızca eğitim verisinden, her fold'da yeniden)
fiziksel olarak anlamlı: **mevsim** = Ocak/Şubat/Mart, **saat** = 21–04
UTC (00:00–07:00 yerel, radyasyon sisi penceresi). Hiçbir fold'da havuza
geri düşülmedi.

```
python -m sis_modeli.katmanli_deney --bootstrap 200
```

| ufuk | katman | LSS | AP/taban | | LSS farkı (katmanlı−tek) | AP/taban farkı |
|---|---|---|---|---|---|---|
| 1h | tek | 0.169 | 6.88 | | — | — |
| 1h | mevsim | 0.101 | 10.07 | | **−0.070** [−0.091, −0.048] | +2.781 [−1.322, 8.454] |
| 1h | **saat** | **0.191** | **10.93** | | **+0.023** [0.003, 0.046] | **+4.295** [2.529, 6.470] |
| 2h | tek | 0.194 | 6.86 | | — | — |
| 2h | mevsim | 0.145 | 6.08 | | **−0.049** [−0.085, −0.017] | −0.777 [−1.792, 0.283] |
| 2h | saat | 0.164 | 7.11 | | **−0.029** [−0.046, −0.011] | +0.315 [−0.584, 1.490] |
| 3h | tek | 0.190 | 6.19 | | — | — |
| 3h | mevsim | 0.170 | 8.00 | | −0.020 [−0.050, 0.006] | **+1.688** [0.128, 4.504] |
| 3h | saat | 0.174 | 6.58 | | −0.016 [−0.033, 0.002] | +0.414 [−0.028, 0.983] |

(Kalın = eşli gün-blok bootstrap'te aralık 0'ı dışlıyor.)

**SONUÇ: makalenin bulgusu tekrarlanmadı, TERSİNE DÖNDÜ.**

Tek açık kazanç **1 saatlik ufukta saate göre katmanlamada** ve iki
metrikte birden görülüyor (LSS +0.023, replikaların %97'si; AP/taban
+4.295, %100'ü). 2 saatte saat katmanlaması LSS'te açıkça *kötüleşiyor*;
3 saatte her iki katmanlama da belirsiz.

**Neden ters?** Ezeiza modellerinin en güçlü kestiricisi başlangıç
anındaki sisti — yani 1 saatte süreklilik her şeyi taşıyordu ve ek yapı
bir işe yaramıyordu. Bu projenin Model B'sinde süreklilik YOK (onset-only,
görüşsüz). Dolayısıyla 1 saat burada "sürekliliğin çözdüğü" bir ufuk
değil; tam tersine, **günlük zamanlamanın en keskin ayırt edici olduğu**
ufuk. "Saat 03:00 ve sis penceresindeyiz" bilgisi, önümüzdeki 1 saatte
sis oluşup oluşmayacağı için güçlü; 2–3 saate yayıldıkça pencere bulanıyor
ve saat etiketi keskinliğini yitiriyor.

`saat` zaten bir model değişkeni olduğu için, saate göre katmanlama
pratikte "her günlük rejim için ayrı WoE tablosu" demek — yani bir
etkileşim etkisi. 1 saatte bunun bedeli (örnek bölünmesi) getirisinden
küçük, 2 saatten sonra büyük.

**Mevsim katmanlaması zararlı.** 1 ve 2 saatte LSS'te açıkça kötüleşiyor.
1 saatte dikkat çekici bir ayrışma var: AP/taban 6.88'den 10.07'ye
çıkarken LSS 0.169'dan 0.101'e *düşüyor* — yani sıralama iyileşiyor ama
olasılıklar bozuluyor. Beklenen bir şey: "düşük sezon" modeli çok az
pozitif görüyor, stratum içinde sıralamayı yapabiliyor ama kalibrasyonu
bozuk kalıyor. Kalibrasyon bu sayfada olasılık gösterdiğimiz için birincil
metrik (bkz. `degerlendir` modül başlığı), dolayısıyla bu bir kazanç
değil.

**Çoklu kıyas uyarısı.** 12 kıyas yapıldı (2 metrik × 3 ufuk × 2
katmanlama), %90 aralıkla. Şansa bağlı ~1 yanlış pozitif beklenir.
1h/saat sonucu İKİ metrikte birden ve yüksek replika oranıyla ayırt
ediliyor — en sağlam bulgu bu. Buna karşılık 3h/mevsim'in AP/taban
kazancı (+1.688) tek metrikte ve kendi LSS'i ters işaretli; bunu kazanç
saymıyorum.

**Yapılmayanlar:** bu bir geliştirme dönemi bulgusudur, **holdout
açılmadı**. Ayrıca "1 saat katmanlı" ile "2 saat tek" doğrudan
kıyaslanmadı — farklı hedefleri tahmin ettikleri için o kıyas anlamlı
değil; tabloda yan yana durmaları bir sıralama iddiası taşımaz.

**Dış kıyas.** Yabra ve ark. (2026, ön baskı) Ezeiza'da 1 saatte ~%70,
6 saatte ~%32 LSS bildiriyor. **Bu sayılar bu tabloyla kıyaslanamaz:**
(1) onların sis tanımı görüş <5000 m (pus dahil), taban oran %4 — burada
ICAO tanımı (<1000 m) ve %0.76; (2) kendi ifadeleriyle modellerinin en
güçlü kestiricisi *başlangıç anındaki sis*, yani skorun büyük kısmı
süreklilik. Bu proje `hedef.onset_adaylari` ile sis zaten varken olan
satırları dışarıda bırakıyor — yalnızca oluşum tahmin ediliyor.

**Event-level tespit oranı (olay başına TEK temsilci tahmin, eşiği geçen
olay yüzdesi) daha da açık konuşuyor:**

| ufuk | ≥%5 | ≥%10 | ≥%20 | ≥%40 |
|---|---|---|---|---|
| 30dk | %0.0 | %0.0 | %0.0 | %0.0 |
| 1h | %2.0 | %0.0 | %0.0 | %0.0 |
| 2h | %23.0 | %8.6 | %0.0 | %0.0 |
| 3h | %35.9 | %11.3 | %0.0 | %0.0 |

**Hiçbir ufukta, hiçbir olay için model %20'nin üzerinde bir olasılık
üretmedi.** Satır-düzeyinde AP/BSS mütevazı ama pozitif bir sinyal
gösterirken, "yaklaşan BU olayı tek bir anda yüksek güvenle işaretle"
sorusuna model — hiçbir ufukta — güçlü bir cevap vermiyor. Bu bir
BAŞARISIZLIK değil (satır-düzeyinde iklimden anlamlı ölçüde iyi kalıyor),
ama görüşsüz atmosferik sinyalin doğası hakkında dürüst bir sınır: **erken
uyarı sistemi olarak güçlü değil, arka plan riskini kademeli olarak
yükselten zayıf ama gerçek bir gösterge.**

**Holdout'ta (2024-2026, TEK ATIŞ) 3 saatlik ufukta event-level sonuç, aynı
örüntüyü doğruluyor:** 33 bağımsız olaydan yalnızca **5'i (%15.2)** %5 eşiğini
geçti (%5–95 aralığı 6.9–27.8%); %10, %20, %40 eşiklerinin HİÇBİRİNİ hiçbir
olay geçmedi (%0.0). Model B, arka plan riskini gerçekten yükseltiyor
(walk-forward'daki gibi holdout'ta da) ama **tek bir olayı önceden yüksek
güvenle işaretleyen bir erken uyarı sistemi değil**.

### İzolasyon ve durum

Model B **tamamen `sis_modeli/` içinde** — çalışma anına (ltfj_*.py) hiçbir
şekilde bağlanmadı, hiçbir dondurulmuş modül üretilmedi. Bu bir araştırma
deneyidir; canlı bota entegrasyon **ayrı, sonraki** bir karardır.

## Tavan için görüşsüz iki model (A: süreklilik, B: oluşum)

TL.007 madde 6.2.a/6.3.1.a: bulut tabanı görüşten **bağımsız** bir LVO
tetikleyicisi. Ama şu ana kadar kurulan hiçbir tavan çalışması gerçekten
görüşsüz değildi — `tavan_tablo.py`'nin kazanan çifti `spread × görüş`
idi. `tavan_gorussuz.py` iki ayrı, sıralanmayan soru sorar:

- **Model A (süreklilik):** mevcut tavan okuması + atmosferik değişkenlerle,
  3 saat içinde tavan<500ft olur mu?
- **Model B (oluşum):** ne görüş ne mevcut tavan — yalnızca atmosferik
  sinyalle (spread, rüzgâr, saat) tavan çökmesi önceden haber verilebiliyor mu?

**Bağımsız olay sayısı, görüşsüz sis modelinden (2017+ rejim) fazla:**

| hedef | gelişt. olay | holdout olay |
|---|---|---|
| sis (Model B) | 128 | 33 |
| **tavan<500ft** | **182** | **81** |

### Değişken seçimi — sis'ten farklı, YENİDEN ölçüldü

Walk-forward ablasyonla (gelişt. içi, embargo açık):

| Model B (oluşum, tavan_ozellik YOK) | AP | BSS |
|---|---|---|
| spread+trend3+rüzgâr_kuzey+saat — **SEÇİLEN** | 0.060 | **0.025** |
| + sıcaklık | 0.041 | 0.014 |

**Dikkat — sis hedefinin tam tersi:** sis modelinde sıcaklık eklenmeden model
iklimden kötüydü; burada sıcaklık eklenince BSS %43 düşüyor. Aynı değişken
iki farklı hedefte zıt yönde davranabiliyor — bu yüzden sis taramasının
sonucu tavan'a otomatik taşınmadı, sıfırdan ölçüldü.

| Model A (süreklilik, tavan_ozellik DAHİL) | AP | BSS |
|---|---|---|
| yukarıdaki + spread_egilim_1 + tavan_ozellik — **SEÇİLEN** (6 değ.) | **0.068** | **0.021** |

VIF: her iki kümede de tüm değişkenler <2.

### Geliştirme-içi event-level (182 bağımsız olay)

| model | ≥%5 | ≥%10 | ≥%20 |
|---|---|---|---|
| Model A (süreklilik) | %34.6 | %11.0 | %0.0 |
| Model B (oluşum) | %33.5 | %4.4 | %0.0 |

Sis modelinin holdout'undaki (%15.2 @ ≥%5) sonuçtan belirgin daha iyi —
daha fazla bağımsız olayın beklenen faydası.

### Nihai holdout (2024-2026, TEK ATIŞ) — beklenmedik ve açıklanmış bir sonuç

| model | holdout AP | holdout BSS | AP %5–%95 |
|---|---|---|---|
| Model A (süreklilik) | 0.076 | 0.015 | 0.059 – 0.101 |
| Model B (oluşum) | 0.081 | 0.015 | 0.062 – 0.105 |
| iklim | 0.010 | 0.000 | 0.009 – 0.018 |
| basit kural (sezgisel) | 0.048 | −0.126 | 0.032 – 0.053 |

Satır düzeyinde iklimden anlamlı ölçüde iyi — ama **event-level tespit her
iki modelde de holdout'ta %0.0'a düştü** (81 olayın hiçbiri hiçbir eşikte
yakalanmadı), geliştirme-içi %34.6'dan keskin bir düşüş.

**Kök neden bulundu ve holdout'a TEKRAR DOKUNMADAN doğrulandı:** her iki
model de holdout eğitiminde `L2=10000` seçti — `model.L2_ADAYLARI`
ızgarasının **en uç (en muhafazakâr) değeri**. Bu L2 ile eğitim kümesindeki
**en yüksek** tahmin bile %2.6 — yani hiçbir satır, en düşük event-level
eşiği olan %5'i bile geçemiyor; sonucun %0.0 çıkması matematiksel bir
zorunluluk, ayrı bir "model başarısız oldu" bulgusu değil.

Bunun nedeni araştırıldı: `egit_secerek()` L2'yi eğitim döneminin **tek bir
son yılına** karşı iç doğrulamayla seçiyor (bkz. `model.py` — iki yıl
denenmiş, tek yıl daha iyi çıkmıştı, ama bu tekliğin bir bedeli var). Aynı
eğitim kümesine en yakın walk-forward fold'u (eğitim 2017-2022, test 2023)
da **aynı L2=10000'i** seçti — yani 2022/2023'e özgü bir ayrışma zorluğu,
tek-yıllık iç doğrulamayı uç bir değere kilitliyor. Diğer fold'lar çok daha
düşük L2 (10-1000) seçip %8-18 aralığında tahminler üretebiliyordu.

**Bu holdout sonucu TEK ATIŞ kuralı gereği değiştirilmedi** — yalnızca
kök nedeni geliştirme verisiyle (holdout'a dokunmadan) doğrulandı ve
raporlanıyor. Gelecekte AYRI, önceden ilan edilen bir deney olarak
`egit_secerek()`'in iç doğrulama prosedürü (örn. çoklu yıl ortalaması)
gözden geçirilebilir — ama bu, mevcut sonuç raporlandıktan SONRA, yeni bir
TEK ATIŞ kuralıyla yapılmalı.

## Model A (görüşlü) vs Model B (görüşsüz) — çapraz karşılaştırma

Model B'nin (görüşsüz sis oluşumu) canlı sisteme entegre edilmeye değer
olup olmadığını sınamak için üç soru soruldu: (1) B, A'dan önce mi sinyal
veriyor (lead-time gain)? (2) A aynı bandındayken B'nin düşük/orta/yüksek
olması gerçek sis oranını değiştiriyor mu (conditional value)? (3) B'nin
yüksek dediği bağımsız olaylardan kaçı gerçekleşiyor (event detection)?
Kod: `sis_modeli/ab_karsilastirma.py` (`python -m sis_modeli.ab_karsilastirma`).

**Dürüstlük notu:** holdout (2024-2026) hem Model A hem Model B için daha
önce AYRI AYRI açılmış ve TEK ATIŞ olarak raporlanmıştı. Bu karşılaştırma
o sonuçları DEĞİŞTİRMEZ veya yeniden ayarlamaz — iki zaten dondurulmuş
modelin tahminlerini aynı holdout satırları üzerinde eşleştirip yeni,
tanımlayıcı bir çapraz analiz yapar; hiçbir model burada yeniden
eğitilmez/ayarlanmaz. Yine de holdout'un bu programda kaçıncı kez
"açıldığını" saymanın bir anlamı var (bkz. yukarıdaki Bölüm 14 notu) —
bu, o sayımın bir eklentisidir.

**1) Event detection (holdout, 33 bağımsız olay):**

| Model | Eşik | Yakalanan | Duyarlılık |
|---|---|---|---|
| A | ≥%5 | 21/33 | %63.6 |
| A | ≥%10 | 18/33 | %54.5 |
| B | ≥%5 | 5/33 | %15.2 |
| B | ≥%10 | 0/33 | %0.0 |

B tek başına holdout'ta çok zayıf — A'nın çok gerisinde.

**2) Lead-time gain:** B, A'dan ÖNCE sinyal vermiyor. Modelin kendi 3
saatlik tasarım ufkunda (n=8 karşılaştırılabilir olay): ortalama fark
**−11.2 dakika**, medyan **0.0 dakika** (B ne erken ne geç — pratikte fark
yok). Daha geniş 6 saatlik keşif penceresinde (n=10): ortalama **−51.0**,
medyan **−15.0 dakika** — yani B ortalamada A'dan DAHA GEÇ sinyal veriyor.
A tek başına 16 olayda sinyal üretirken B hiç üretmiyor; tam tersi
(yalnızca B) sadece 1 olayda (3s ufku) / 3 olayda (6s ufku).

**3) Conditional value:** A'nın kendi bandı içinde B'yi tertile (düşük/
orta/yüksek) ayırınca:

| A bandı | n/tertil | B düşük | B orta | B yüksek | Monoton mu |
|---|---|---|---|---|---|
| %0–1 | 14.278 | %0.0 | %0.1 | %0.3 | ✅ evet |
| %1–2 | 764 | %0.5 | %1.4 | %2.1 | ✅ evet |
| %2–5 | 518 | %1.2 | %1.2 | %6.0 | ⚠️ kısmi |
| %5–10 | 158 | %5.1 | %5.1 | %6.3 | ✅ ama fark küçük |
| %10–20 | 56 | %12.5 | %14.3 | %3.6 | ❌ ters yön |
| %20–101 | 30 | %43.3 | %25.8 | %50.0 | ❌ U-şekilli |

(Not: global bir B eşiğiyle bölünürse A ve B ilişkili olduğu için üst
bantlarda "B düşük" hücresi tamamen BOŞ çıkıyor — bu yüzden her A bandı
KENDİ İÇİNDE tertile ayrıldı; kod hâlâ global bölünmeyi de destekler,
bkz. `kosullu_deger_tertil()`'in üstündeki not.)

**Sonuç:** B'nin katkısı gerçek ama **A'nın zaten düşük olduğu bölgeyle
(yaklaşık %0-2, verinin büyük çoğunluğu) sınırlı** — orada büyük örnekle
(n binlerle) tutarlı, monoton bir ayrım var (örn. %0.5→%2.1, 4 kat). A
yükseldikçe (%5 üzeri) örnek küçülüyor (158→56→30) ve desen bozuluyor;
%10-20 bandındaki ters yön ile %20+ bandındaki U-şekli büyük olasılıkla
küçük-örnek gürültüsü, gerçek bir etki değil. **B'yi bağımsız bir erken
uyarı/olay-tespit aracı olarak kullanmak bu veriyle savunulamaz; ama A
zaten "sakin" derken ikincil bir "ne kadar rahat olalım" göstergesi olarak
istatistiksel temeli var** — canlıya ayrı, küçük bir gösterge olarak
eklenmesi düşünülüyorsa bu çerçevede (yalnızca A düşükken gösterilerek)
değerlendirilmeli.

### A ≥%5 derinlemesine — asıl operasyonel soru

Yukarıdaki %0-2 bulgusu istatistiksel olarak temiz ama asıl kullanım
amacı **A zaten yüksek derken B'nin ek bir şey söyleyip söylemediği**
("A %12 diyor, B'ye bakmalı mıyım?"). Önceki tablodaki %5-10/%10-20/%20+
satırları yalnızca "monoton mu" diye bakıyordu; bu yetersiz - naif
satır-bazlı bir farkın **anlamlı olup olmadığını** GÜN bazlı blok
bootstrap CI ile (`degerlendir.blok_guven_araligi` - aynı sis olayının
ardışık satırlarını bağımsız saymayan yöntem) test etmek gerekiyordu.
Kod: `derinlemesine_a_yuksek()` ve `yillik_kararlilik()`.

| A bandı | n | B düşük (CI) | B orta (CI) | B yüksek (CI) | CI örtüşüyor mu | B'nin bant-içi AP'si vs taban |
|---|---|---|---|---|---|---|
| %5–10 | 474 | %5.1 (1.3–9.3) | %5.1 (1.4–9.1) | %6.3 (2.2–11.0) | ✅ örtüşüyor | 0.084 vs 0.055 |
| %10–20 | 168 | %12.5 (3.7–23.2) | %14.3 (6.8–24.6) | %3.6 (0.0–7.7) | ✅ örtüşüyor | 0.080 vs **0.101** |
| %20–101 | 91 | %43.3 (25.9–61.3) | %25.8 (11.8–43.8) | %50.0 (28.6–67.6) | ✅ örtüşüyor | 0.509 vs 0.396 |

Sorulara doğrudan cevap:

1. **B yükseldikçe oran gerçekten yükseliyor mu?** Hayır tutarlı biçimde —
   %5-10'da neredeyse düz, %10-20'de TERSİNE dönüyor (yüksek en düşük
   oranı taşıyor), %20+'da U-şekilli.
2. **Fark anlamlı mı?** Hayır — **üç bandın hepsinde düşük/yüksek %5-95
   güven aralıkları geniş ölçüde örtüşüyor.** Görünen farklar gürültü
   düzeyinde.
3. **B ek bilgi sağlıyor mu (bant içinde)?** %10-20 bandında B'nin AP'si
   taban orandan (sabit tahmin) DAHA DÜŞÜK — yani bu bantta B rastgeleden
   daha kötü sıralıyor. Diğer iki bantta hafif iyileşme var ama n çok
   küçük (91-474) ve CI'lar zaten örtüştüğü için güvenilir sayılamaz.
4. **A≥%5 + B yüksek → gerçek oran ne?** %6.3 (5-10 bandı), %3.6 (10-20
   bandı — düşükten bile az), %50.0 (20+ bandı). Sabit bir "B yüksekse
   daha riskli" kuralı YOK.
5. **B düşükken A yüksek olduğunda risk gerçekten aşağı geliyor mu?**
   Hayır — %10-20 bandında B düşükken oran (%12.5) B yüksekken olandan
   (%3.6) daha YÜKSEK; %20+ bandında ise düşük/yüksek neredeyse eşit
   (%43.3 vs %50.0). Hipotezin tersi kadar destek var.
6. **Yıllık kararlılık (2024/2025/2026 ayrı ayrı aynı yönde mi?):** Hayır.
   Örnek, %5-10 bandında düşük→orta→yüksek deseni: 2024'te **%8→%12→%11**
   (düz/karışık), 2025'te **%6→%2→%1** (AZALAN), 2026'da **%2→%2→%13**
   (sadece yükseklerde sıçrama). Üç yıl üç farklı yön gösteriyor — bu,
   önceki tablodaki "monoton" görünümün gerçek bir etki değil, örneklem
   gürültüsü olduğunun doğrudan kanıtı. (Yıl başına hücre örnekleri
   13-80 satır / 5-37 ayrı gün arası - resmi bir anlamlılık testi için
   zaten çok ince; bu yüzden "veri yetersiz" dürüst sonuç, "her yıl aynı
   yönde" değil.)

**Nihai sonuç: A ≥%5 bölgesinde B'nin ek bilgi taşıdığına dair bu holdout'ta
güvenilir bir kanıt YOK.** Görünen "trendler" gün-bazlı CI ile test
edildiğinde hepsi örtüşüyor, yön iki bantta tersine dönüyor, yıllar arası
tutarsız. A+B ortak bir model kurmadan önce sorulması gereken "B yeni
bilgi mi taşıyor yoksa A'nın gürültülü bir kopyası mı" sorusunun cevabı,
en azından A'nın yüksek olduğu (operasyonel olarak en kritik) bölge için:
**şimdilik A'nın gürültülü bir kopyası gibi davranıyor.** Tek istisna
%0-2 bandındaki (yukarıdaki) büyük-örnekli, monoton bulgu — o hâlâ geçerli
ve ayrı bir sonuç.

## Model A'yı geliştirme girişimleri

İki somut iyileştirme fikri sınandı — ikisi de kod DEĞİŞTİRMEDEN önce
uygun (dev-only veya zaten var olan) verilerle test edildi.

### 1) Rejim penceresi denetimi — zaten yapılmış, ek işlem yok

Model A'nın 5 özelliğinden ikisi (`spread`, `spread_egilim_3`) doğrudan çiy
noktasından türüyor — yani yukarıdaki **2021-2023 çiy noktası kusuru**
A'yı doğrudan ilgilendiriyor. Ama bu zaten `veri_kalitesi.py --ab` ile
test edilip (bkz. yukarıki "Dışlama denendi ve reddedildi" bölümü)
**reddedilmiş**: o yılları dışlamak holdout AP'sini 0.184'ten 0.176'ya
düşürüyor, fark tamamen eşleştirilmiş CI'nın altında. Diğer bilinen rejim
sorunu (tavan az-bildirimi, 2011-2016) A'nın özellik setinde hiç yok
(A "tavan" kullanmıyor). Sonuç: **yapılacak bir şey yok, mevcut karar
doğru.**

### 2) Yüksek uç kalibrasyonu — denendi ve REDDEDİLDİ

**Teşhis (gerçek, gürültü değil):** holdout güvenilirlik tablosunda
`%30-40` kovası tahmin %34.65 derken gerçekleşme %63.16 (n=19) —İlk
bakışta küçük örneklem şüphesi uyandırıyor (bkz. yukarıdaki A≥%5
bulgusu), ama gün-bazlı blok bootstrap CI **[%42.1 – %82.4]** tahmin
edilen %36.5'in tamamen üstünde. Daha da önemlisi, AYNI desen çok daha
büyük örneklemle **gelişme döneminin kendi walk-forward dışı-katlanmış
(out-of-fold) tahminlerinde** de çıkıyor: `%30-40` kovası n=209 (tahmin
%34.04, gerçekleşen %41.15), `%40-50` kovası n=86 (tahmin %45.20,
gerçekleşen %56.98). Yani model yüksek uçta **sistematik olarak temkinli**
— bu gerçek bir bulgu.

**Düzeltme denemesi** (`sis_modeli/kalibrasyon.py`): PAVA (pool adjacent
violators) izotonik regresyonu, SADECE gelişme dönemi walk-forward
dışı-katlanmış tahminleriyle (155.634 tahmin, holdout hiç kullanılmadan)
uyduruldu, sonra nihai (tüm-gelişme-eğitimli) modelin çıktısına uygulanıp
holdout'ta önce/sonra karşılaştırıldı:

| | AP (ham) | AP (kalibre) | Brier×10⁴ (ham) | Brier×10⁴ (kalibre) |
|---|---|---|---|---|
| Dev (dışı-katlanmış, uydurma verisi) | 0.210 | 0.221 | 69.30 | 68.52 |
| **Holdout** | **0.184** | **0.173** | 40.85 | 40.73 |

Dev verisinde (beklendiği gibi, çünkü kalibrasyon o veriye uyduruldu)
her şey mükemmel kalibre görünüyor. Ama **holdout'ta AP kötüleşiyor**
(0.184→0.173) ve güvenilirlik deseni bile TERSİNE dönüyor (örn. `%10-20`
kovasında ham gerçekleşme %10.12 iken kalibre versiyon %4.92'ye düşüyor,
`%30-40` kovasında ham %63.16 iken kalibre %16.67'ye düşüyor ve n 19'dan
6'ya iniyor). **Sonuç: dev döneminde öğrenilen kalibrasyon deseni holdout'a
TAŞINMIYOR — tıpkı tavan tablosundaki "kat" seviyesinin dönemler arası
2.3 kat kaymasına benzer bir kararsızlık.** Bu düzeltme **prodüksiyona
alınmadı** (`ltfj_sis_olasilik.py` değiştirilmedi). Kod (`kalibrasyon.py`)
ve testleri repoda kalıyor — ileride farklı bir kalibrasyon yaklaşımı
(örn. daha büyük/daha yakın tarihli bir dönemle yeniden uydurma) için
temel oluşturabilir, ama şu an dürüst sonuç "bu haliyle işe yaramıyor".

### 3) A<%2 bandındaki B sinyali — canlıya bağlandı

Önce B'nin ham olasılığını A'ya 6. özellik olarak eklemek (stacking)
denendi — sonuçsuz (global AP 0.210→0.209, A<%2 alt kümesinde AP
0.0125→0.0124, fark yok). Ama bu, sinyalin gerçek olmadığı anlamına
gelmiyordu: A'nın kendi düşük bandı içinde B'yi tertile (düşük/orta/
yüksek) ayırmak, ölçüm metriği olarak AP yerine doğrudan gerçekleşme
oranına (gün-bazlı CI ile) bakıldığında **İKİ BAĞIMSIZ dönemde** (holdout
VE gelişme dönemi walk-forward dışı-katlanmış) net bir ayrım gösterdi:

| A bandı | n/tertil (dev walk-forward) | B düşük | B orta | B yüksek |
|---|---|---|---|---|
| %0–1 | 43.442 | %0.03 [0.00–0.05] | %0.05 [0.03–0.08] | %0.37 [0.28–0.47] |
| %1–2 | ~3.947 | %1.09 [0.76–1.44] | %1.60 [1.11–2.14] | %1.72 [1.15–2.34] |

`%0-1` bandında CI'lar hiç örtüşmüyor — AP'nin yakalayamadığı ama
gerçek olan bir ayrım. **Sonuç:** B'yi A'nın SKORUNA karıştırmak yanlış
yaklaşımmış (AP'ye görünmüyor, WoE kovalama da ince ayrımı sıkıştırıyor);
doğru yaklaşım B'yi **ayrı, küçük bir gösterge** olarak tutmak.

**Uygulama:** `ltfj_sis_olasilik_b.py` — Model B'nin (görüşsüz sis oluşumu,
`ALANLAR = spread, spread_egilim_3, sicaklik, ruzgar_kuzey, saat`) NİHAİ
(tüm gelişme dönemiyle eğitilmiş) katsayı/WoE tabloları, `ltfj_sis_olasilik.py`
ile AYNI dondurulmuş-modül disiplininde (`math` dışında bağımlılık yok,
sis_modeli/ import edilmiyor). `tertil(a_olasiligi, b_olasiligi)` fonksiyonu
A **< %2** iken B'nin o bant içindeki (33/67. yüzdelik, dondurulmuş sınır)
sırasını döner; **A >= %2 iken hiçbir şey döndürmez** — çünkü o bölgede
(`ab_karsilastirma.py`, "A ≥%5 derinlemesine") B'nin katkısına dair
güvenilir kanıt yoktu.

Web sayfasında (`ltfj_sayfa.py::_sis_olasiligi_html`) A<%2 iken kartın
altına küçük, kesikli çizgiyle ayrılmış bir "Sis eğilimi: düşük/orta/yüksek"
satırı ekleniyor — sayısal yüzde GÖSTERİLMİYOR (bu bandın mutlak oranları çok
küçük ve gürültülü görünebilirdi), sadece kategorik etiket + görüşe
dayanmadığını ve resmî olmadığını açıklayan sade bir cümle. İsim ve cümle
bilinçli olarak "atmosferik gösterge", "ince ayrım" gibi model/istatistik
terminolojisinden arındırıldı - kontrolörler istatistik terimi değil, neyi
gösterdiğini bilmek istiyor.

### 4) Holdout tazeleme (2024-2026'yı eğitime katmak) — denendi, YARIDA KALDI

`sis_modeli/tazeleme.py` (AYRI TUTULUYOR, canlıya bağlanmadı): 2024/2025/2026'yı
sırayla walk-forward test yılı olarak ekleyip "bu yılları eğitime katmak modeli
bozar mı" sorusuna bakan bir deneme. Fold bazlı sonuçlar (2024, 2026) önceki
dev fold'larıyla tutarlı (AP 0.193 / 0.226) — ama süreç, tazelemeden bağımsız,
genel bir sağlamlık açığı ortaya çıkardı:

**Bulgu:** `model.py::egit()` IRLS'i, veri havuzu 2024-2026'yı da içerecek
şekilde büyüyünce, hem 2025 fold'unun kendi eğitim setinde (2011-2024) hem de
2011-2026'nın tamamının nihai birleşik eğitiminde **yakınsamıyordu** — sabit
terim her iterasyonda sabit bir miktar (~7 milyon) küçülerek sınırsız
gidiyor, diğer katsayılar Model A'nın normal ölçeğinin (~0.2-0.7) ~100 katı
büyüklükte "sabitleniyordu". Klasik **quasi-complete separation**: havuz
büyüyünce birkaç WoE hücresi aşırı nadir ve tam ayrıştırıcı hale geliyor
(örn. n=1574/poz=0, ya da n=3-6/poz=n). Önceki sürüm bunu HİÇ kontrol
etmiyordu — MAKS_ITER (30) tükenince, yakınsamamış olsa bile son iterasyondaki
anlamsız katsayıları sessizce döndürüyordu. Bu, `tazeleme.py`'nin ilk
çalıştırmasında 2025 fold'unun "zayıf" (BSS −0.008, AP 0.015) görünmesinin
gerçek nedeniydi — zayıf bir yıl değil, yakınsamamış/çöp bir modeldi.

**Düzeltme (genel, tazelemeden bağımsız):** `model.Yakinsamadi` eklendi —
`TekilSistem` ile aynı ilke: IRLS `MAKS_ITER` içinde yakınsamazsa artık
sessizce döndürmüyor, açıkça hata fırlatıyor. `egit_secerek()`'in iç L2
taramasında bu durum diğer L2 adaylarına geçilerek atlanıyor (`TekilSistem`
ile aynı davranış); ama fold'un NİHAİ (tüm eğitim verisiyle) yeniden
eğitimi yakınsamazsa hata `tazeleme.py`'ye kadar yükseliyor — orada o
fold/adım açıkça "YAKINSAMADI" olarak işaretlenip atlanıyor, birikmiş
istatistiklere KATILMIYOR. Mevcut üretim eğitimi (2011-2023, Model A/B)
bu sorunu hiç tetiklemiyor — regresyon testleriyle doğrulandı.

**Sonuç:** 2011-2026'nın tamamıyla eğitilmiş "nihai taslak" model bu haliyle
üretilemiyor (a priori seçilen L2 o havuzda yakınsamıyor). Bunu post-hoc
daha büyük bir L2 seçerek "düzeltmek", L2 ızgarasının sonuca bakılmadan a
priori seçilmesi ilkesini bozar. Yani **holdout tazeleme YAPILMADI** — ne
bu haliyle yakınsamayan bir modelle, ne de sonradan seçilmiş bir L2'yle.
Bunu ileride denemek isteyen biri için gereken: L2 seçim prosedürünü (ya
da aşırı nadir WoE hücrelerini elemeyi) SONUÇLARA bakmadan, a priori olarak
büyütülmüş havuza uyarlayıp yeniden dondurmak — tek seferlik bir sayı
seçimi değil, prosedürün kendisinin gözden geçirilmesi gerekir.

## Sınırlar

Bu bir **iklim + süreklilik** modelidir, fizik modeli değildir: yaklaşan bir
cepheyi göremez. ECMWF gibi sayısal hava tahmini ürünlerinin rakibi değil,
tamamlayıcısıdır. Çıktısı **resmî bir tahmin değildir** ve METAR/TAF'ın yerine
geçmez.

## Kullanım

```bash
# Arşivi çek ve türetilmiş veriyi üret (ağ gerekir - Actions'ta çalışır)
python -m sis_modeli.veri_cek --baslangic 2003 --bitis 2026

# Ek veri kaynakları (deneysel, EĞİTİM-ONLY - ağ gerekir, Actions'ta çalışır)
python -m sis_modeli.veri_cek_komsu --baslangic 2003 --bitis 2026
python -m sis_modeli.veri_cek_acik_meteo --baslangic 2003 --bitis 2026

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

# Düşük tavan: dış kaynak (komşu istasyon + Open-Meteo) aday taraması
python -m sis_modeli.tavan_dis_kaynak_tarama

# Model B: görüşsüz atmosferik sis oluşum potansiyeli
python -m sis_modeli.olusum_egit                     # tarama + walk-forward
python -m sis_modeli.olusum_egit --dahil-gorus        # görüş-ablasyon karşılaştırması
python -m sis_modeli.ufuk_deneyi                      # 30dk/1h/2h/3h lead-time
python -m sis_modeli.ufuk_deneyi --bootstrap 200      # + eşli gün-blok güven aralıkları
python -m sis_modeli.katmanli_deney --bootstrap 200   # tek model mi, mevsim/saat katmanlı mı
python -m sis_modeli.olusum_holdout_degerlendir       # TEK ATIŞ

# Tavan: görüşsüz süreklilik (A) + oluşum (B) modelleri
python -m sis_modeli.tavan_gorussuz                   # tarama + walk-forward
python -m sis_modeli.tavan_gorussuz --holdout          # TEK ATIŞ

# Sis: Model A (görüşlü) vs Model B (görüşsüz) çapraz karşılaştırma
python -m sis_modeli.ab_karsilastirma                 # holdout'u YENİDEN AÇMAZ - zaten dondurulmuş iki modeli eşleştirir

# Model A: yüksek uç kalibrasyon denemesi (SONUÇ: reddedildi, prodüksiyona alınmadı)
python -m sis_modeli.kalibrasyon                      # dev'de uydurur, holdout'ta önce/sonra gösterir
```
