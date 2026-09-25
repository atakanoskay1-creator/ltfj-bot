# LTFJ Hava Durumu Sayfası — Kullanım Kılavuzu

Bu kılavuz, İstanbul Sabiha Gökçen hava durumu sayfasını ilk kez açan kullanıcılar içindir. Ekrandaki bilgileri nasıl okuyacağınızı, aradığınız bilgiye hangi sekmeden ulaşacağınızı ve sayfadaki düğmeleri nasıl kullanacağınızı anlatır.

## İlk kullanım: nereden başlamalıyım?

1. **Verinin zamanına bakın.** Başlığın altında son METAR, TAF ve NOTAM bilgisinin ne kadar eski olduğunu kontrol edin.
2. **Dört ana değeri okuyun:** GÖRÜŞ, TAVAN, RÜZGÂR ve SPREAD.
3. **Durum** sekmesinde son raporu ve açıklamalarını inceleyin.
4. İleriye dönük eğilim için **Beklenti**, geçmiş verilerden hesaplanan olasılıklar için **İstatistik** sekmesine geçin.
5. İhtiyacınıza göre **LVO** veya **NOTAM** sekmesini açın.

> Sayfa bilgilendirme, eğitim ve simülasyon amaçlıdır. Gerçek uçuş ve ATC kararlarında güncel resmî kaynaklar kullanılmalıdır.

## 1. Sayfada gezinme ve bilgilerin zamanı

Beş ana sekme vardır: **Durum · Beklenti · İstatistik · LVO · NOTAM**. Bir sekmeye dokunduğunuzda ilgili bölüm açılır. Telefonda sekmeler üstte, geniş ekranlarda soldadır. Telefonda bir sekme görünmüyorsa sekme çubuğunu yatay kaydırın. Son seçtiğiniz sekme aynı tarayıcıda hatırlanır.

Açıklama, grafik veya ham rapor başlıklarından bazıları katlıdır. Başlığa basarak içeriği açabilir, tekrar basarak kapatabilirsiniz.

### Güncellik göstergeleri

| Ekranda gördüğünüz | Nasıl okunmalı? |
| --- | --- |
| **CANLI** | Ekrandaki son gözlem, sayfanın güncellik eşiği içindedir. Sürekli sensör yayını anlamına gelmez. |
| **GECİKMELİ** | Son gözlem beklenenden eskidir. Önce Yenile'ye basın ve rapor saatini yeniden kontrol edin. |
| **VERİ KESİNTİSİ / VERİ YOK** | Güncel gözlem alınamıyor veya gözlem zamanı bilinmiyor. Gösterilen eski değerleri yeni ölçüm saymayın. |
| **METAR / TAF / NOTAM yanında geçen süre** | Her bilgi kaynağının yaşını ayrı ayrı gösterir. Birinin güncel olması diğerlerinin de güncel olduğu anlamına gelmez. |
| **Sayfa zamanı** | Sayfanın hazırlanma zamanıdır; raporun ölçüm/yayın zamanından farklı olabilir. |

**Yenile** düğmesi, yayımlanmış son sayfayı açar. Bastığınızda rapor saati değişmiyorsa yeni bilgi henüz sayfaya yansımamış olabilir. Sayfa açıkken de yeni gözlemleri belirli aralıklarla kontrol eder; yine de rapor saatine bakın. Formlara yazdığınız değerleri kaydetmeden elle yenilemeyin.

**Saat örneği:** `09:50Z (12:50 yerel)` aynı anı iki biçimde gösterir. `Z`, UTC saatidir; parantez içi Türkiye saatidir. Beklenti tablosunun saatleri yereldir.

## 2. Üstteki dört ana değer

| Alan | Anlamı | Okuma örneği |
| --- | --- | --- |
| **GÖRÜŞ** | Son rapordaki yatay görüş. Birimine dikkat edin: metre veya kilometre olabilir. | `10+ km`, 10 km ve üzeri demektir; tam 10 km ölçümü anlamına gelmez. |
| **TAVAN** | Rapordan belirlenen bulut tavanı, feet (ft) olarak gösterilir. | `500 ft` bir yüksekliktir. “Tavan yok” ifadesini gökyüzünün tamamen bulutsuz olduğu şeklinde okumayın. |
| **RÜZGÂR** | Rüzgârın geldiği yön ve knot (kt) cinsinden hızı. Hamle varsa ayrıca belirtilir. | `050°/10 kt`, 050 dereceden 10 knot rüzgâr demektir. `G`, hamleyi belirtir. |
| **SPREAD** | Sıcaklık ile çiy noktası arasındaki fark. | Sıcaklık 12°C, çiy noktası 10°C ise spread 2°C'dir. Tek başına sisin oluşacağını söylemez. |

Bu alanların yanındaki küçük çizgiler geçmiş değişimi gösterir. Gelecek saatlerin tahmini için **Beklenti** sekmesine geçin. Çizgi yoksa bunu “değer sabit” olarak yorumlamayın; yeterli geçmiş veri bulunmayabilir.

**BLU, WHT, GRN, YLO, AMB, RED** rozetleri görüş ve tavana göre oluşturulan durum seviyeleridir. BLU'dan RED'e doğru koşullar daha sınırlayıcıdır. Renkle birlikte sayısal değeri de okuyun; bu rozetler tek başına pist, yaklaşma veya uçuş izni belirlemez.

## 3. Durum: şu anda ne bildiriliyor?

**Durum** sekmesinde son METAR/SPECI, TAF, açıklamalar ve geçmiş eğilimler yer alır.

1. Raporun **tipini ve saatini** kontrol edin. METAR/SPECI gözlemi, TAF ileriye dönük havalimanı tahminini gösterir.
2. Açıklama bölümünü okuyun. Ayrıntıyı kontrol etmek için raporun **ham metnine** bakın.
3. Pist/rüzgâr çizimini ve bileşenlerini incelerken hangi pist yönünün gösterildiğine dikkat edin. Sayfadaki pist değerlendirmesi, o anda kullanılan pistin resmî bildirimi değildir.
4. **Geçmiş eğilim · son 6 saat** başlığını açın. Grafikler son saatlerdeki değişimi incelemek içindir; tahmin olarak okunmamalıdır.

## 4. Beklenti: önümüzdeki saatler nasıl görünüyor?

**Beklenti** sekmesinde saatler sütunlarda, hava değişkenleri satırlarda gösterilir. Aynı satırı soldan sağa izleyerek saatler arasındaki değişimi karşılaştırın. Tablo ekrana sığmıyorsa yatay kaydırın.

| Satır veya işaret | Anlamı |
| --- | --- |
| **spread — °C** | Modelin beklediği sıcaklık–çiy noktası farkı. |
| **görüş — km** | Modelin beklediği görüş. `10+`, 10 km ve üzeridir. |
| **rüzgâr — kt** | Modelin beklediği rüzgâr hızı. |
| **alçak bulut — %** | Alçak seviyedeki bulut örtüsü oranı; bulut tavanı yüksekliği değildir. |
| **sınır tabakası — m** | Veri mevcutsa gösterilen model değişkenidir; bulut tavanıyla karıştırmayın. |
| Saatin altındaki **sis** işareti | Modelin o saat için sis öngördüğünü belirtir. Gerçekleşmiş gözlem değildir. |
| **—** | O hücre için veri yoktur; sıfır demek değildir. |

Başlıkta “... saat önceki model çıktısı” yazıyorsa tahminin yaşını dikkate alın. Bu bölüm Open-Meteo model çıktısıdır. Havalimanının yayımlanmış TAF'ını **Durum** sekmesinde okuyabilirsiniz.

## 5. İstatistik: olasılıkları ve süreleri nasıl okumalıyım?

### İstatistiksel sis olasılığı

Büyük yüzde, **önümüzdeki 3 saat içinde görüşün 1000 m altına düşmesine ilişkin model olasılığını** gösterir. Örneğin `%30`, modelin bu olay için hesapladığı olasılıktır; “3 saatin %30'u sisli geçecek” veya “30 dakika sonra sis başlayacak” anlamına gelmez. Örnek sayı açıklama içindir, güncel tahmin değildir.

**Düşük/yüksek** gibi etiketler sonucu özetler. Ekranda görünen `%0` veya `%0.0` değerini, yuvarlama ve model belirsizliği nedeniyle olayın imkânsız olduğu şeklinde yorumlamayın.

**Sis eğilimi** alanı gösteriliyorsa mevcut koşulların sis oluşumuna uygunluğuna ilişkin ek ipucu verir. Bunu büyük olasılık yüzdesiyle aynı ölçü olarak okumayın. **İki modelin bağlantısını gör** düğmesi açıklayıcı görseli açar; **Kapat** ile geri dönersiniz.

### Tavan istatistiği

Bu bölüm gösterildiğinde oranlar geçmişte benzer koşullarda görülen sonuçları özetler. Mevcut ölçüm veya belirli bir saatte gerçekleşeceği kesinleşmiş tahmin değildir. Oranın yanında yazan koşulları ve açıklamaları birlikte okuyun.

### Görüş geçiş süreleri

Tabloda **Düşme** ve **Toparlanma** satırlarının altında hangi görüş değerleri arasındaki geçişin incelendiği yazar. Süreler **saat** cinsindendir.

- **%10 / %25 / %75:** Geçmiş olayların ilgili yüzdesinin bu süre içinde veya daha kısa sürede tamamlandığını gösterir.
- **Medyan:** Geçmiş olayların ortanca süresidir. Şimdiki olayın kalan süresi değildir.
- **n:** O satırın hesabına giren olay sayısıdır.
- **0.5 saat:** Kullanılan gözlem aralığı nedeniyle “yarım saat veya daha kısa” olarak okunmalıdır.

## 6. NOTAM: arama ve filtreleme

### Aktif NOTAM'ları bulma

1. **NOTAM** sekmesini açın ve listenin güncellenme zamanına bakın.
2. **Numara, pist, anahtar kelime…** alanına aradığınızı yazın. Örneğin `06R` yazarak bu ifadeyi içeren kayıtları arayabilirsiniz.
3. İsterseniz **Tüm kategoriler** ve **Tüm elemanlar** menülerinden filtre seçin. Birden fazla filtre birlikte sonucu daraltır.
4. İlgili kaydın açıklamasını, tarihlerini ve varsa **Ham NOTAM metni** bölümünü açıp okuyun.
5. **Temizle** düğmesi filtreleri kaldırır; NOTAM kayıtlarını silmez.

### Geçmişte arama

**Geçmiş / Arama** başlığını açın. Kelime, tarih aralığı ve **Yürürlükte / Süresi dolmuş / Henüz başlamamış** filtreleriyle arayın. Tarih aralığı, NOTAM'ın geçerlilik dönemiyle ilişkili kayıtları süzer.

Bu arama, sayfanın bugüne kadar biriktirdiği kayıtları kapsar. **Sonuç bulunamadı** mesajı, o konuda hiçbir zaman NOTAM yayımlanmadığı anlamına gelmez. “Liste eski olabilir” veya veri alınamadı uyarısı varsa listenin güncelliği doğrulanamamıştır.

## 7. LVO: bölüm sırası ve RVR girişi

**LVO** sekmesinde dört bölüm bulunur:

| Bölüm | Nasıl kullanılır? |
| --- | --- |
| **A) Farkındalık Notları** | METAR, TAF ve girilmiş RVR'ın eşiklerle karşılaştırılmasına ilişkin notları okuyun. Her notun hangi kaynağa dayandığını ayırt edin. |
| **B) AWOS RVR** | Kullanıcılar tarafından elle girilmiş pist görüş menzillerini ve zamanlarını görüntüleyin; yeni değer gerekiyorsa aşağıdaki formu kullanın. |
| **C) LVO Related NOTAM** | Düşük görüşle ilişkili olabilecek NOTAM'ları inceleyin. |
| **D) Doküman Referansı** | Başlığa basarak referans metnini açın; tekrar basarak kapatın. |

### RVR değeri kaydetme

1. **Runway** menüsünden **06R** veya **24R** seçin.
2. Elinizdeki değerleri **metre** cinsinden ilgili alanlara yazın: **TDZ** teker koyma bölgesi, **MID** orta bölüm, **STOP-END** pistin son bölümü.
3. Bilmediğiniz alanları boş bırakın. En az bir alan doldurulmalıdır; bilinmeyen değer yerine `0` yazmayın.
4. **SAVE AWOS RVR** düğmesine basın.
5. Kaydın listede doğru pist, konum ve değerle göründüğünü kontrol edin.

Buradaki kayıtlar diğer ziyaretçilerle paylaşılır. **MANUAL AWOS**, elle girilmiş bilgi anlamına gelir; bu alan kendiliğinden AWOS sensöründen veri aldığını göstermez. METAR görüşünü RVR yerine girmeyin.

**CLEAR**, seçili piste ait kayıtların tamamını onaydan sonra siler. İşlem ortak listeyi etkiler. Yalnızca formu boşaltmak için bu düğmeyi kullanmayın.

Panelde “LVO şartları oluşabilir” gibi bir ifade görülmesi, LVO'nun başlatıldığı veya bir yaklaşmanın kullanılabilir olduğu anlamına gelmez.

## 8. Sağdaki VFR göstergesi

Sağ kenardaki **VFR** düğmesine basın. Açılan panel, son METAR/SPECI'deki görüş ve tavanın sayfadaki eşikleri sağlayıp sağlamadığını açıklar.

- **Yeşil:** Görüş/tavan karşılaştırmasında eşik altı durum bulunmamıştır.
- **Kırmızı:** Görüş veya tavan eşiğinin altında değer vardır. Ayrıntıda nedenini okuyun.
- Veri yetersizse göstergeye kesin sonuç gibi yaklaşmayın.

Sayfanın karşılaştırdığı eşikler **5000 m görüş** ve **1500 ft tavan**dır. Bu gösterge buluttan uzaklık, izinler ve diğer uçuş şartlarını değerlendirmez. Paneli sağ üstteki kapatma düğmesiyle kapatabilirsiniz.

## 9. ATC Notes: ortak notları okuma ve ekleme

1. Sağ alttaki not simgesine basarak **ATC Notes** panelini açın.
2. Paylaşılmış notları ve zamanlarını okuyun.
3. Not eklemek için **+ NOT EKLE** düğmesine basın.
4. **Adınız** ve **Not** alanlarını doldurun; **Kaydet**'e basın. Vazgeçerseniz **İptal**'i seçin.
5. Yeni notunuzun listede göründüğünü kontrol edin.

Notlar sayfayı kullanan diğer kişilere de görünür. Yazılan adın kimliği doğrulanmaz. Notlar 48 saatlik geçici paylaşımlardır; kalıcı kayıt veya resmî talimat olarak kullanılmaz. Paylaşılmasını istemediğiniz kişisel bilgileri yazmayın.

## 10. Tarayıcı bildirimlerini açma

Üst bölümde **Bildirimlere izin ver** düğmesi görünüyorsa basın ve tarayıcının izin sorusunu onaylayın. Başarılı olduğunda **Bildirimler açık** yazısını kontrol edin.

- **İzin verilmedi:** Bu site için bildirim iznini tarayıcınızın site ayarlarından kontrol edin.
- **Bildirimler (tekrar dene):** Bağlantınızı kontrol edip yeniden deneyin.
- **Düğme görünmüyor:** Özellik o cihazda veya sayfada kullanılamıyor olabilir.

Bildirimler SPECI, yeni TAF, düzeltmeler, durumun kötüleşmesi ve yeni NOTAM gibi olaylar için gönderilebilir. Her rutin METAR için bildirim beklemeyin. **Bildirimler açık** yazması her koşulda teslimat garantisi değildir; raporların zamanını sayfadan da kontrol edin.

## 11. Bir şey çalışmıyorsa

| Karşılaştığınız durum | Yapabileceğiniz işlem |
| --- | --- |
| Değerler eski görünüyor | **Yenile**'ye basın ve rapor saatini kontrol edin. Eski kalıyorsa bir süre sonra tekrar bakın. |
| Beklenti veya istatistik görünmüyor | Bölümdeki açıklamayı okuyun. Eksik bilgi “risk yok” anlamına gelmez. |
| NOTAM araması boş | **Temizle** ile filtreleri kaldırın, daha kısa bir kelime veya daha geniş tarih aralığı deneyin. |
| RVR kaydolmuyor | Pist seçimini, en az bir sayı girdiğinizi ve metre birimini kontrol edin. Hata mesajını okuyun. |
| Not kaydolmuyor | Ad ve not alanlarının dolu olduğunu, bağlantınızı ve hata mesajını kontrol edin. |
| “Yapılandırılmamış” yazıyor | İlgili özellik şu anda kullanılamıyor. Sayfa sorumlusuna bildirin. |
| Sorun devam ediyor | Sayfa sorumlusuna hangi bölümde, saat kaçta, hangi işlemi yaparken sorun yaşadığınızı ve ekrandaki hata mesajını iletin. |

_Kılavuz tarihi: 25 Eylül 2026._
