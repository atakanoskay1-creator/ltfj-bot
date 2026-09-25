# LTFJ Bot — Kullanıcı Kılavuzu

Bu kılavuz, LTFJ (İstanbul Sabiha Gökçen) hava durumu sayfasını, ATC panelini ve bildirimleri kullanmak isteyenler içindir. Depoyu kendi hesabında çalıştırma adımları için [Kurulum](#9-kendi-kopyanı-kurma) bölümüne bak.

> **Kullanım sınırı:** Bu proje eğitim, simülasyon ve hobi amaçlıdır. Veriler gecikebilir, eksik veya hatalı olabilir. Uçuş planlaması ve gerçek ATC operasyonlarında kullanılamaz. METAR/TAF, NOTAM, AWOS, ATIS ve ilgili prosedürler için yetkili resmî kaynakları kullan.

## 1. Sayfaları açma

GitHub Pages etkinse ana sayfa `https://atakanoskay1-creator.github.io/ltfj-bot/`, ATC paneli `https://atakanoskay1-creator.github.io/ltfj-bot/panel.html` adresindedir. Başka bir hesaptaki fork için kullanıcı adını ve gerekirse depo adını değiştir. Pages açılmamışsa bu adresler çalışmaz; [Kurulum](#9-kendi-kopyanı-kurma) bölümündeki Pages adımını uygula.

Ana sayfadaki **Yenile** düğmesi sayfayı yeniden yükler. Veri, botun son başarılı çalışmasına bağlıdır; sayfayı yenilemek tek başına yeni METAR çekmez. Üstteki **CANLI / GECİKMELİ / VERİ KESİNTİSİ** etiketi ile METAR, TAF ve NOTAM yaşlarını kontrol et. Saatlerde `Z` UTC'yi, `yerel` Türkiye saatini ifade eder. Bu etiket açık kalan sayfada da güncellenir.

## 2. Ana sayfayı okuma

Sayfanın başındaki **GÖRÜŞ · TAVAN · RÜZGÂR · SPREAD** alanı son ölçümü özetler. *Spread*, sıcaklık ile çiy noktası arasındaki farktır; tek başına sis oluşacağının garantisi değildir. BLU/WHT/GRN/YLO/AMB/RED rozeti projenin kendi durum sınıflamasıdır, resmî yaklaşma veya LVO kategorisi değildir.

Telefonda sekmeler üstte yataydır; dar ekranda yana kaydırılabilir. Geniş ekranda sol tarafta görünürler:

| Sekme | Ne gösterir? | Nasıl kullanılır? |
| --- | --- | --- |
| **Durum** | Son METAR/SPECI, TAF, çözümleme, pist/rüzgâr bileşenleri ve son 6 saatin eğilimleri. | Rapor saatini ve ham bülteni açarak yorumu kontrol et; geçmiş grafiklerini gerektiğinde genişlet. |
| **Beklenti** | Open-Meteo kaynaklı saatlik model tahmini. | Model çıktısının yaşını kontrol et; TAF yerine kullanma. Veri alınamadığında sekme bunu açıklar. |
| **İstatistik** | Önümüzdeki 3 saatte görüşün 1000 m altına düşmesine ilişkin istatistiksel olasılık, tavan istatistiği ve geçmiş görüş geçiş süreleri. | Olasılığı geçmiş örüntülere dayalı tahmin olarak oku; kesin saat veya resmî sis tahmini sayma. |
| **LVO** | Farkındalık notları, elle girilen AWOS RVR, ilişkili NOTAM ve açılabilir doküman referansı. | Kaynak ve zamanları ayrı ayrı kontrol et; panel LVO/CAT II kararı vermez. |
| **NOTAM** | Botun aldığı aktif NOTAM listesi ve yerel geçmiş araması. | Numara/pist/anahtar kelimeyle ara, filtrele; resmî NOTAM/PIB ile doğrula. |

Sayfanın sağındaki **VFR** düğmesi son METAR/SPECI görüşünü **5000 m**, tavanını **1500 ft** eşiğiyle karşılaştırır. Düğmeye basınca hangi eşiklerin sağlanmadığı görünür. Bu gösterge buluttan uzaklık, trafik, izinler ve diğer uçuş şartlarını değerlendirmez; resmî VFR uygunluğu kararı değildir.

## 3. NOTAM arama

**NOTAM → Aktif NOTAM'lar** bölümünde numara, pist veya kelime yaz; kategori ve eleman filtrelerini seç. **Temizle** filtreleri sıfırlar. **Geçmiş / Arama** başlığını açarak tarih aralığı ve yürürlük durumu ile yalnızca botun bugüne kadar kaydettiği NOTAM'larda ara. Bu arşiv eksiksiz tarihçe değildir. Liste eski veya erişilemiyor uyarısı gösteriyorsa ona güvenme. Kaynak NOTAC adlı üçüncü taraf servistir; operasyon öncesi resmî NOTAM/PIB gereklidir.

## 4. LVO ve elle AWOS RVR girişi

**LVO** sekmesinde **B) AWOS RVR** altında pisti (**06R** veya **24R**) seç; mevcutsa **TDZ**, **MID** ve **STOP-END** değerlerini metre cinsinden girip **SAVE AWOS RVR** düğmesine bas. En az bir değer gereklidir. Girilen değerler paylaşımlı Firebase veritabanına yazılır; diğer ziyaretçiler görür. Değerleri yalnızca doğru kaynaktan, güncel zamanı bilerek gir. **CLEAR** seçili piste ait girilmiş değerlerin tamamını onaydan sonra siler.

**A) Farkındalık Notları** ölçümler ile eşiklere dair bilgilendirici karşılaştırmalar, **C)** ilgili NOTAM'lar, katlı **D) Doküman Referansı** ise statik metin içerir. Statik metnin güncelliğini resmî yayınlardan ayrıca doğrula. Firebase kurulmamışsa manuel kayıt kullanılamaz; diğer sekmeler etkilenmez.

## 5. ATC Notes

Sağ alttaki **ATC Notes** düğmesini aç, **+ NOT EKLE**'ye bas, adını ve notunu yazıp **Kaydet**'i seç. Notlar ortak görünür, kimlik doğrulaması yapılmaz ve oluşturulduktan 48 saat sonra temizlenir. Gizli, kişisel veya operasyonel talimat niteliğinde bilgi yazma. Firebase yapılandırılmamışsa not panosu kullanılamaz.

## 6. ATC paneli

`panel.html` sayfasında **KULE** ve **YAKLAŞMA** düğmeleri widget'ları farklı öncelik sırasına koyar. Widget'ları tutamaçtan sürükleyebilir veya **▲ / ▼** ile sıralayabilir, **✕** ile gizleyebilir, üstteki **Gizli:** alanından geri getirebilirsin. Tercihler yalnızca kullandığın tarayıcıda saklanır; rol düğmesine yeniden basmak ilgili hazır düzene döner.

Panel `panel_veri.json` verisini yaklaşık **60 saniyede bir** tekrar okur; **Yenile** düğmesi beklemeden okumayı dener. Üstteki tazelik/bayat veri uyarısını kontrol et. Tekrar okuma botu tetiklemez; veri bot çalışınca üretilir. Panel de yalnızca eğitim/simülasyon içindir.

## 7. Bildirimler

**Telegram:** Bot, `ayarlar.json` yapılandırmasına göre yeni SPECI, TAF, düzeltme, dikkat eşiği ve önemli renk değişimlerini iletebilir. Varsayılan ayarda rutin METAR ayrı bildirim olarak gizlidir; sabit durum mesajı açıktır. Hangi olayların iletileceği, sessiz saatler ve mesaj ayrıntısı depo sahibinin ayarlarına bağlıdır. Telegram'da mesaj gelmiyorsa önce botun son Actions koşusuna ve doğru sohbet kimliğine bak.

**Tarayıcı bildirimleri:** Ana sayfada **Bildirimlere izin ver** görünüyorsa düğmeye basıp tarayıcı iznini onayla. Bu kanal SPECI, TAF, AMD/COR, durumun kötüleşmesi ve yeni NOTAM için tasarlanmıştır; rutin METAR için değildir. Düğme yoksa veya bildirim gelmiyorsa tarayıcı desteği/izinleri ile Firebase ve VAPID kurulumunu kontrol et. Depo sahibi **Actions → Push testi (elle) → Run workflow** ile kayıtlı cihazlara test gönderebilir. Telefon ve tarayıcıların bildirim davranışı farklı olabilir.

## 8. Sık karşılaşılan durumlar

| Durum | Kontrol |
| --- | --- |
| **GECİKMELİ / VERİ KESİNTİSİ** | METAR yaşı ve son Actions koşusuna bak. Sayfa yenilemesi veri üretmez. GitHub zamanlayıcısı gecikebilir; README'deki dış tetikleme açıklamasına bak. |
| **Beklenti verisi eski/yok** | Tahmin kaynağı ve **Dış kaynak önbelleği** Actions koşusunu kontrol et. Eski model çıktısını güncel TAF sayma. |
| **NOTAM yok/eski** | NOTAC anahtarı, NOTAM senkron zamanı ve son bot koşusunu kontrol et. Aktif listede olmaması resmî kaynakta NOTAM olmadığı anlamına gelmez. |
| **AWOS kaydetme/temizleme veya ATC Notes çalışmıyor** | Firebase URL'si, ilgili Secrets ve yayınlanmış güncel `firebase-rules.json` kurallarını kontrol et. |
| **Panel güncellenmiyor** | `panel_veri.json` dosyasının son bot koşusunda üretildiğini ve panelde bayatlık uyarısı olup olmadığını kontrol et. |
| **Telegram veya push gelmiyor** | `ayarlar.json` bildirim tercihlerini ve Actions loglarını kontrol et; push için **Push testi (elle)** kullan. |

## 9. Kendi kopyanı kurma

1. Depoyu GitHub hesabına **Fork** et. **Settings → Actions → General** bölümünde Actions'ın çalışabildiğini ve workflow için **Read and write permissions** verildiğini kontrol et; iş akışı üretilen sayfayı ve durumu depoya yazıyor.
2. Telegram'da **BotFather** ile bot oluştur ve mesaj göndereceği sohbetin `chat_id` değerini edin. **Settings → Secrets and variables → Actions → Repository secrets** altında `TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` ekle. Yapay zekâ yorumunu kullanacaksan `ANTHROPIC_API_KEY` ekle; anahtar yoksa bu yorum üretilmez.
3. **Actions → LTFJ bildirim → Run workflow** ile ilk çalıştırmayı başlat. Sonuç ve hata nedenleri için koşu loglarını incele. Ardından **Settings → Pages** altında **Deploy from a branch**, `main` ve kök klasörü seç. Sayfa adresi GitHub Pages ekranında görünür.
4. Gerekiyorsa `ayarlar.json` içindeki eşik, Telegram, mesaj, web ve NOTAM seçeneklerini düzenle. Anahtarları dosyaya koyma. NOTAM için `NOTAC_API_KEY`; ATC Notes ve manuel RVR için README'deki Firebase kurulumu gerekir. Tarayıcı bildirimleri için ayrıca uyumlu VAPID anahtar çifti ve güncel Firebase kuralları gerekir.
5. Düzenli güncelleme için Actions'ın zamanlanmış koşularını izle. Dakika hassasiyetinde dış tetikleme istersen README'deki `repository_dispatch` örneklerini kullan; tetikleyici erişim anahtarını gizli tut. Kurulumun ayrıntıları ve tüm Secrets listesi [README](README.md) içindedir.

_Kılavuz, deponun 25 Eylül 2026 tarihindeki arayüzü ve yapılandırmasına göre hazırlanmıştır._
