# ltfj-bot

LTFJ metar taf botu
# ✈️ LTFJ (Sabiha Gökçen) METAR/TAF Telegram Botu

Bu proje, İstanbul Sabiha Gökçen Havalimanı (LTFJ) için güncel havacılık meteorolojisi (METAR ve TAF) verilerini otomatik olarak takip eden, yapay zeka desteğiyle analiz eden ve kritik değişiklikleri anlık olarak Telegram üzerinden bildiren sunucusuz (serverless) bir otomasyon sistemidir.

## 🌟 Özellikler

* **Gerçek Zamanlı Veri Takibi:** MGM (Meteoroloji Genel Müdürlüğü) altyapısı üzerinden LTFJ için anlık METAR ve TAF raporlarını çeker.
* **Akıllı Bildirim Sistemi (State Yönetimi):** Sürekli aynı mesajı atarak spam yapmaz. Sadece hava durumunda operasyonel anlamda bir değişiklik olduğunda (örneğin görüş mesafesi düştüğünde, rüzgar yönü değiştiğinde veya sis çöktüğünde) Telegram bildirimi gönderir.
* **Yapay Zeka Analizi:** Çekilen karmaşık havacılık verileri Anthropic (Claude) API kullanılarak analiz edilir ve pilot/kontrolör perspektifinden anlaşılır bir dile çevrilir.
* **Web Arayüzü:** Her çalışmada otomatik olarak güncel bir `index.html` sayfası üretir. GitHub Pages ile entegre edilerek anlık hava durumu web üzerinden de takip edilebilir. Sayfada son 6 saatin rüzgâr, bulut tavanı, QNH ve sıcaklık değişimini gösteren basit SVG trend grafikleri de bulunur (harici kütüphane kullanılmaz).
* **ATC Panel (`panel.html`):** Hava trafik kontrolörü bakış açısıyla tasarlanmış, koyu temalı, widget tabanlı bir gösterge panosu. Rüzgârı metin yerine pist eksenine göre dönen bir vektör (ok) olarak çizer; RVR, bulut tabanı, QNH, sıcaklık ve aktif uyarılar ayrı widget'larda büyük/renk kodlu rakamlarla gösterilir. Widget'lar sürükle-bırakla yeniden sıralanabilir, gizlenebilir; KULE/YAKLAŞMA rol düğmeleri farklı önceliklere göre hazır düzenler yükler. Düzen tercihleri tarayıcıda saklanır. Veri `panel_veri.json`'dan (bot her çalıştığında yeniden üretir) istemci tarafında çekilir, ~60 saniyede bir tazelenir.
* **Sunucusuz (Serverless) Çalışma:** Harici bir sunucuya (VDS/VPS) ihtiyaç duymaz. Tamamen GitHub Actions ve `cron-job.org` dış tetikleyicisi ile ücretsiz ve 7/24 çalışır.

## 🏗️ Sistem Mimarisi

1. **Tetikleyici:** `cron-job.org` belirli dakikalarda (`10, 25, 40, 55`) GitHub API'sine bir `repository_dispatch` isteği gönderir.
2. **İş Akışı:** GitHub Actions uyanır ve Python ortamını ayağa kaldırır.
3. **Veri Çekme ve Analiz:** `ltfj_rasat.py` ve `ltfj_bot.py` dosyaları çalışır; web'den güncel veri alınır, eski durum ile karşılaştırılır ve Anthropic API'ye yorumlatılır.
4. **Bildirim:** Eğer hava durumunda değişiklik varsa, Telegram Bot API üzerinden ilgili sohbete/kanala mesaj atılır.
5. **Kayıt:** Güncel durum `index.html` dosyasına yazılır ve bot tarafından repoya otomatik olarak `push` edilir.

## 🚀 Kurulum ve Ayarlar

Bu projeyi kendi GitHub hesabınızda (fork) çalıştırmak isterseniz aşağıdaki adımları izleyin:

### 1. Gereksinimler
* Bir Telegram Bot Token'ı (BotFather'dan alınır) ve Chat ID'si.
* Bir Anthropic API Anahtarı.
* Dış tetikleme için [cron-job.org](https://cron-job.org) hesabı.

### 2. Ortam Değişkenleri (GitHub Secrets)
Güvenliğiniz için API anahtarlarını koda yazmak yerine GitHub reponuzda **Settings > Secrets and variables > Actions** yolunu izleyerek aşağıdaki **Repository Secrets**'ları eklemelisiniz:

* `TELEGRAM_BOT_TOKEN` : Telegram botunuzun token değeri.
* `TELEGRAM_CHAT_ID` : Mesajların gönderileceği kişi veya grup ID'si.
* `ANTHROPIC_API_KEY` : Yapay zeka analizleri için kullanılacak API anahtarı.
* `PAT_TOKEN` : `repository_dispatch` tetiklemesi için gerekli (repo ve workflow izinlerine sahip) Personal Access Token.
* `NOTAC_API_KEY` *(opsiyonel)* : NOTAM bilgi katmanı için [NOTAC](https://notac.aero) API anahtarı. Tanımlı değilse NOTAM bölümü sessizce devre dışı kalır.
* `FIREBASE_SERVICE_ACCOUNT` *(opsiyonel)* : ATC Notes'un 48 saatlik otomatik temizliği için Firebase servis hesabı JSON'unun **tamamı**. Aşağıdaki "ATC Notes (Firebase)" bölümüne bakın.
* `FIREBASE_DATABASE_URL` *(opsiyonel)* : Firebase Realtime Database URL'iniz (ör. `https://PROJE-ADI-default-rtdb.europe-west1.firebasedatabase.app`).

### 3. GitHub Pages'i Aktif Etme (Opsiyonel)
Botun ürettiği `index.html` dosyasını canlı bir web sitesi olarak görmek için:
1. Reponuzda **Settings > Pages** sekmesine gidin.
2. "Source" (Kaynak) kısmından `Deploy from a branch` seçeneğini belirleyin.
3. Branch olarak `main` dalını seçip kaydedin. Birkaç dakika içinde projeniz `https://[KULLANICI_ADINIZ].github.io/ltfj-bot` adresinde yayına girecektir.

### 4. ATC Notes (Firebase)

ATC Notes (durumsal farkındalık notları), METAR/TAF/NOTAM sisteminden tamamen bağımsız, kimlik doğrulaması olmayan, paylaşımlı ve geçici (48 saat) bir not panosudur. Okuma/yazma doğrudan tarayıcıdan [Firebase Realtime Database](https://firebase.google.com/products/realtime-database)'e yapılır; Python tarafı yalnızca süresi dolmuş notları arka planda gerçekten siler. Bu özellik opsiyoneldir — kurulmazsa web sayfasındaki ATC Notes bölümü "yapılandırılmamış" mesajı gösterir, METAR/NOTAM bölümleri hiç etkilenmez.

Kurulum:
1. [Firebase Console](https://console.firebase.google.com/)'da yeni bir proje oluşturun (Google Analytics gerekmiyor).
2. Sol menüden **Build > Realtime Database > Create Database** ile bir veritabanı açın (konum olarak size yakın bir bölge seçebilirsiniz), "Locked mode" ile başlatın.
3. **Rules** sekmesine bu reponun köküdeki `firebase-rules.json` dosyasının içeriğini yapıştırıp **Publish** edin. Bu kurallar: herkesin okumasına izin verir, sadece yeni not oluşturmaya (güncelleme/silme yok) izin verir, `author`/`text` uzunluk ve boşluk kontrolü yapar, ve `created_at`'in gerçekten Firebase sunucu saatiyle yazıldığını doğrular — istemcinin gönderdiği bir zaman damgasına güvenilmez.
4. Realtime Database sayfasının üstünde görünen veritabanı URL'inizi (ör. `https://PROJE-ADI-default-rtdb.europe-west1.firebasedatabase.app`) `ayarlar.json`'daki `atc_notes.database_url` alanına yazın. Web sayfası bu URL'e doğrudan `fetch()` ile REST istekleri atar (ayrı bir SDK/CDN gerekmez). **Bu URL gizli değildir** — Firebase'in kendi tasarımı gereği istemci tarafında (web sayfasında) görünür; güvenlik 3. adımdaki Rules ile sağlanır.
5. **Project settings > Service accounts > Generate new private key** ile bir JSON dosyası indirin. **Bu dosya gizlidir** — reponun **Settings > Secrets and variables > Actions** kısmına `FIREBASE_SERVICE_ACCOUNT` adıyla (JSON içeriğinin tamamını) ve `FIREBASE_DATABASE_URL` adıyla veritabanı URL'inizi Repository Secret olarak ekleyin.

> **Not:** `awos_rvr` kuralı girilen RVR değerlerinin **silinmesine** izin verir (LVO panelindeki `CLEAR` butonu); üzerine yazmaya izin vermez. Bu kural değiştiyse Rules sekmesindeki içeriği güncelleyip yeniden **Publish** edin, aksi halde CLEAR butonu 401/403 alır ve sayfada hata gösterir.

> **Not:** `firebase-rules.json` LVO panelinin manuel AWOS RVR giriş yolu (`awos_rvr`) için de kurallar içerir — ATC Notes'u zaten kurduysanız **aynı Firebase projesini** kullanabilirsiniz, sadece Rules sekmesindeki içeriği dosyanın güncel haliyle yeniden yapıştırıp **Publish** etmeniz yeterli (yeni bir proje/veritabanı gerekmez).

### 5. Tarayıcı Bildirimleri (Web Push)

Web sayfasındaki **🔔 Bildirimlere izin ver** butonu, Telegram'dan bağımsız ikinci bir kanaldır: SPECI, TAF, düzeltme (AMD/COR), renk **kötüleşmesi** ve yeni NOTAM durumlarında telefona/tarayıcıya bildirim düşürür (rutin METAR düşürmez). Abonelikler ATC Notes ile aynı Firebase veritabanında, `push_abonelikler` yolunda tutulur; gönderimi `ltfj_push.py` yapar.

Çalışması için **üçü birden** gerekir:

1. **Repository Secret'ları:** `FIREBASE_SERVICE_ACCOUNT`, `FIREBASE_DATABASE_URL` (yukarıdaki ATC Notes kurulumuyla aynı) ve ayrıca `VAPID_PRIVATE_KEY`. Üçünden biri eksikse özellik sessizce devre dışı kalır, METAR/TAF akışı etkilenmez.
2. **`ayarlar.json::push.vapid_public_key`** — özel anahtarla *birlikte* üretilmiş açık anahtar. Gizli değildir, sayfaya gömülür; biri değişirse diğeri de değişmelidir. Boşsa buton hiç gösterilmez.
3. **Firebase Rules'un güncel hali yayınlanmış olmalı.** `firebase-rules.json` içindeki `push_abonelikler` bloğu Rules sekmesinde **yoksa**, tarayıcı aboneliği oluşturur ama Firebase yazmayı reddeder — sunucu tarafında hiç abone olmaz ve *hiçbir bildirim gitmez*. Rules sekmesine dosyanın güncel içeriğini yapıştırıp **Publish** edin.

**Hemen test etmek için:** Actions sekmesinden **Push testi (elle)** workflow'unu çalıştırın (`Run workflow`). Abone olan cihazlara gerçek bir test bildirimi düşürür ve abone/gönderildi/hata sayaçlarını yazar; başarısızsa adım kırmızı yanar. SPECI veya TAF beklemenize gerek kalmaz.

Çalışıp çalışmadığını GitHub Actions logundan da görebilirsiniz — bot her push denemesini yazar:

```
  push [TAF]: 2 abone, 2 gönderildi, 0 geçersiz abonelik silindi, 0 hata.
  push [TAF]: kayıtlı abone YOK - kimseye gönderilmedi.     ← 3. adım eksik olabilir
  push [TAF]: atlandı - FIREBASE_SERVICE_ACCOUNT/... eksik.  ← 1. adım eksik
```

### 6. LVO Reference Paneli

LVO Reference paneli, "SABİHA GÖKÇEN HAVALİMANI DÜŞÜK GÖRÜŞ OPERASYONLARI TALİMATI" (TL.007 Rev.1, 16.08.2024) dokümanındaki referans RVR eşiklerini gösterir, ve ATC'nin manuel olarak gireceği AWOS RVR'ı (06R/24R × TDZ/MID/STOP-END) paylaşımlı olarak tutar. Sayfa açıldığında kapalıdır — panel başlığına tıklanınca açılır, uzun metinler sayfa yüklenirken gösterilmez.

Panelin başında, **Farkındalık Notları** adında gayri resmi bir alt bölüm bulunur: en son METAR/TAF'ın kendi görüş/tavan değeri ve girilen AWOS RVR, dokümanın kendi eşik değerleriyle karşılaştırılıp "... LVO şartları oluşabilir. Resmî bir tespit değildir." gibi hedge'li (kesin olmayan) uyarı cümlelerine dökülür (bkz. `ltfj_lvo_farkindalik.py`). **Bu panel hiçbir operasyonel karar üretmez** — METAR'dan RVR türetmez, "LVO aktif", "CAT II kullanılabilir" gibi kesin bir sonuç çıkarmaz; sadece mevcut bilgileri kaynağıyla ve hedge'li bir dille gösterir. Yukarıdaki ATC Notes kurulumuyla **aynı Firebase veritabanını** kullanır — ayrıca bir kurulum gerekmez, sadece `firebase-rules.json`'ın güncel halinin Rules sekmesine yapıştırılmış olması yeterlidir.

### 7. VFR Sekmesi

Sayfanın sağ kenarında küçük bir "VFR" sekmesi bulunur. Bu sekme, en son METAR/SPECI'nin görüş ve bulut tabanı (tavan) değerlerini ICAO Annex 2 (Rules of the Air) Table 3-1'in FL100 altı satırıyla (görüş ≥ 5 km, tavan ≥ 1.500 ft — Sabiha Gökçen CTR'si sürekli kontrollü hava sahası olduğu için tüm irtifalarda aynı eşik) karşılaştırır ve şartlar sağlanıyorsa yeşil, sağlanmıyorsa kırmızı yanar. Kırmızıyken/tıklandığında açılan panelde hangi eşiğin (görüş ve/veya tavan) sağlanmadığı yazar. Bu, projedeki diğer METAR-tabanlı göstergelerle (ör. sis riski) aynı mantıkla çalışan, tamamen statik/deterministik bir hesaplamadır — ek kurulum, Firebase veya harici veri kaynağı gerektirmez; hiçbir zaman "LVO/CAT II" gibi operasyonel bir karar iddiasında bulunmaz, sadece görüş/tavan-VFR eşiği karşılaştırmasıdır.

## ⚠️ Yasal Uyarı

Bu yazılım tamamen **eğitim, simülasyon ve hobi amaçlı** olarak geliştirilmiştir. Havacılıkta hava durumu verileri hayati önem taşır. Bu botun sağladığı veriler gecikmeli, eksik veya hatalı olabilir. **Gerçek uçuş planlamaları veya gerçek havacılık operasyonları için kesinlikle KULLANILAMAZ.** Gerçek uçuş operasyonları için sadece yetkili ve resmi meteoroloji servis sağlayıcılarını kullanınız.

---

