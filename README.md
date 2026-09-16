# ltfj-bot

LTFJ metar taf botu
# ✈️ LTFJ (Sabiha Gökçen) METAR/TAF Telegram Botu

Bu proje, İstanbul Sabiha Gökçen Havalimanı (LTFJ) için güncel havacılık meteorolojisi (METAR ve TAF) verilerini otomatik olarak takip eden, yapay zeka desteğiyle analiz eden ve kritik değişiklikleri anlık olarak Telegram üzerinden bildiren sunucusuz (serverless) bir otomasyon sistemidir.

## 🌟 Özellikler

* **Gerçek Zamanlı Veri Takibi:** MGM (Meteoroloji Genel Müdürlüğü) altyapısı üzerinden LTFJ için anlık METAR ve TAF raporlarını çeker.
* **Akıllı Bildirim Sistemi (State Yönetimi):** Sürekli aynı mesajı atarak spam yapmaz. Sadece hava durumunda operasyonel anlamda bir değişiklik olduğunda (örneğin görüş mesafesi düştüğünde, rüzgar yönü değiştiğinde veya sis çöktüğünde) Telegram bildirimi gönderir.
* **Yapay Zeka Analizi:** Çekilen karmaşık havacılık verileri Anthropic (Claude) API kullanılarak analiz edilir ve pilot/kontrolör perspektifinden anlaşılır bir dile çevrilir.
* **Web Arayüzü:** Her çalışmada otomatik olarak güncel bir `index.html` sayfası üretir. GitHub Pages ile entegre edilerek anlık hava durumu web üzerinden de takip edilebilir. Sayfada son 6 saatin rüzgâr, bulut tavanı, QNH ve sıcaklık değişimini gösteren basit SVG trend grafikleri de bulunur (harici kütüphane kullanılmaz).
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

### 3. GitHub Pages'i Aktif Etme (Opsiyonel)
Botun ürettiği `index.html` dosyasını canlı bir web sitesi olarak görmek için:
1. Reponuzda **Settings > Pages** sekmesine gidin.
2. "Source" (Kaynak) kısmından `Deploy from a branch` seçeneğini belirleyin.
3. Branch olarak `main` dalını seçip kaydedin. Birkaç dakika içinde projeniz `https://[KULLANICI_ADINIZ].github.io/ltfj-bot` adresinde yayına girecektir.

## ⚠️ Yasal Uyarı

Bu yazılım tamamen **eğitim, simülasyon ve hobi amaçlı** olarak geliştirilmiştir. Havacılıkta hava durumu verileri hayati önem taşır. Bu botun sağladığı veriler gecikmeli, eksik veya hatalı olabilir. **Gerçek uçuş planlamaları veya gerçek havacılık operasyonları için kesinlikle KULLANILAMAZ.** Gerçek uçuş operasyonları için sadece yetkili ve resmi meteoroloji servis sağlayıcılarını kullanınız.

---
*Bu proje [Atakan Oskay](https://github.com/atakanoskay1-creator) tarafından geliştirilmiştir.*
