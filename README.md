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

### 8. Tasarım Sistemi (renk/yüzey token'ları)

Her anlamsal renk eskiden sayfaya **dağılmış sabit hex** olarak duruyordu.
"Dikkat" tonu (`#b45309` açık / `#fbbf24` koyu) **üç ayrı kuralda**, her biri
ayrıca **iki koyu tema bloğunda** tekrarlanmıştı — dokuz yer. Birini
güncelleyip ötekileri unutmak an meselesiydi.

**Yüzey katmanları:** `--bg` → `--panel` → `--kart` → `--etkilesim`. Her katman
bir üstünden ayrışır; koyu temada saf siyah ve aşırı kontrast yok.

**Anlamsal renkler** durum anlatır, dekorasyon değildir:

| Token | Kullanım |
|---|---|
| `--iyi` / `--iyi-zemin` / `--iyi-dolu` | metin / rozet arka planı / dolu yüzey |
| `--dikkat` / `--dikkat-zemin` / `--dikkat-dolu` | bayat veri, sis saati uyarısı |
| `--uyari` / `--uyari-zemin` / `--uyari-metin` | hata, kritik eşik |
| `--bilgi` / `--bilgi-zemin` | bilgilendirme |

**`RENK_KODU` BU SİSTEME DAHİL DEĞİL.** BLU/WHT/GRN/YLO/AMB/RED bir **havacılık
durum kodu**, arayüz rengi değil; Telegram tarafıyla aynı kavramı paylaşıyor ve
tema değiştirince RED'in kırmızılığı değişmemeli. Bir test bunu koruyor.

#### Kontrast ölçüldü, iddia edilmedi

Token tonları WCAG AA (4.5:1) eşiğine karşı **hesaplanarak** seçildi. Yarı
saydam rozet zeminleri kart rengiyle harmanlanıp ölçüldü:

| Tema | Öğe | Önce | Sonra |
|---|---|---|---|
| açık | sis bandı düşük | 2.89:1 ❌ | **6.26:1** ✅ |
| açık | sis bandı yüksek | 3.97:1 ❌ | **5.32:1** ✅ |
| koyu | sis bandı düşük | 4.10:1 ❌ | **7.75:1** ✅ |
| koyu | sis bandı yüksek | 3.14:1 ❌ | **5.48:1** ✅ |

Açık temadaki iki başarısızlık **mevcut bir kusurdu** — token'laştırma sırasında
ölçünce ortaya çıktı. Hesap testin içinde yaşıyor: token değerleri CSS'ten
okunup yeniden hesaplanıyor, yani bir sonraki renk değişikliğinde sessizce
kaybolamaz.

**Hareket azaltma** (`prefers-reduced-motion`) desteği eklendi; sayfa işlevini
kaybetmez, geçişler anlık olur.

#### Görsel doğrulama

Token'laştırma **saf bir yeniden düzenleme**: 2 tema × 5 sekme = 10 durumun
**8'i piksel bazında aynı**. Değişen yalnızca İstatistik sekmesi — tam da
kontrastı düzeltilen yer.

### 9. Uygulama Kabuğu (başlık + ikonlar)

**Başlıkta durum göstergesi:** `CANLI` / `GECİKMELİ` / `VERİ KESİNTİSİ`,
yanında canlı UTC saati ve METAR/TAF/NOTAM yaşları.

**Durum SUNUCUDA değil İSTEMCİDE hesaplanır.** Sayfa bir vardiya boyunca açık
kalabiliyor; sunucuda yazılan "CANLI" bir saat sonra yalan olurdu. HTML yalnızca
gözlem zaman damgasını taşır (`data-gozlem`), etiketi JS 15 saniyede bir
tazeler. Zaman bilinmiyorsa boş dize gider ve "VERİ YOK" yazılır — uydurma bir
damga yazmaktansa bilinmediğini söylemek doğru.

**Eşikler tek kaynaktan** (`ltfj_ayarlar.py`):

| Sabit | Değer | Gerekçe |
|---|---|---|
| `GOZLEM_TAZE_DK` | 70 | METAR 30 dk kadans + ~5 dk MGM gecikmesi = ~35 dk beklenen azami yaş; eşik bunun **iki katı**. Bir raporu kaçırmak normal, ikisini kaçırmak değil. |
| `SESSIZLIK_SAAT` | 6 | **Botun Telegram alarmıyla aynı sabit.** `ltfj_bot.py`'den buraya taşındı ki sayfa "canlı" derken Telegram "kesinti" diyemesin. |

#### İkon sistemi

Arayüzde **emoji yok**. Emoji platforma göre bambaşka çizilir, boyu yazı tipiyle
uyuşmaz ve ekran okuyucu onları yüksek sesle okur. Tümü **satır içi SVG**
(`IKONLAR` + `ikon()`); ikon fontu ya da sprite dosyası havalimanı ağında
engellenebilirdi. İkonlar `currentColor` kullanır, yani her temada ve her durum
renginde kendiliğinden doğru çizilir.

**`RENK_SIMGE` Telegram tarafında KALDI.** Telegram'da SVG yok — orada emoji
doğru ortam. Yalnızca web kullanımı SVG noktaya çevrildi. Bir test her iki
tarafı da AST ile doğruluyor.

**Sekme ikonları yalnızca geniş ekran rayında.** Ölçüldü: çubuk 360px'te tam
kapasitede (326/326px); ikon eklemek NOTAM sekmesini keserdi. DOM'da duruyor ama
`display:none`, rayda (140px) açılıyor.

### 10. Yazı Tipi (yazitipi/)

Sayfa **IBM Plex Sans** (gövde) ve **IBM Plex Mono** (ham METAR/TAF/NOTAM kod
blokları) kullanır. Yazı tipleri `yazitipi/` klasöründen, yani **kendi
deposundan** servis edilir; `fonts.googleapis.com`'a istek gitmez. Sebep: sayfa
havalimanı ağından açılıyor ve üçüncü taraf bir CDN engellenirse yazı tipi hata
vermeden sessizce sistem fontuna düşerdi.

`yazitipi/` içindeki 6 woff2 dosyası (toplam ~130 KB) **statiktir, bot
tarafından yeniden üretilmez** — silinirlerse sayfa çalışmaya devam eder ama
yedek sistem fontuyla çizilir. `tests/test_ltfj_sayfa_yazitipi.py` hem
dosyaların varlığını hem de geçerli woff2 olduklarını doğrular.

Neden bu ikisi:

- **Plex Mono'nun sıfırı eğik çizgilidir** (`0` ≠ `O`). METAR/NOTAM kodlarında
  (`06004KT`, `Q1015`, `NOSIG`) bu ayrım işlevseldir.
- Türkçe `latin` alt kümesine sığmaz: `ğ/ş/İ` `latin-ext`'te, `ı` `latin`'de.
  İkisi de gömülüdür. `Δ`, `▶`, `⟳` ve emoji hiçbir alt kümede yoktur; tarayıcı
  onları karakter bazında sistem fontuna düşürür — beklenen davranıştır.
- Sans **değişken** fonttur (400..700), sayfadaki `font-weight:650` gibi ara
  ağırlıklar yuvarlanmadan çizilir.

Yazı tipleri [SIL Open Font License 1.1](https://github.com/IBM/plex/blob/master/LICENSE.txt)
ile lisanslıdır.

### 11. Sayfa Düzeni: Sekmeler

Sayfa **beş yatay sekmeye** bölündü: **Durum · Beklenti · İstatistik · LVO ·
NOTAM**. Öncesinde hepsi alt alta katlanır başlıklardı ve sayfa gereksiz
uzuyordu.

**Neden yatay, neden sol dikey ray değil.** İçerik sütunu `max-width:680px`,
telefonda ise tam genişlik (~360px). Soldaki dikey bir ray yatay genişliği
**kalıcı olarak** yerdi (~%25); üstelik "İstatistik" gibi uzun etiketler ya
döndürülmüş yazı ya kısaltma gerektirirdi ve sayfanın sağ kenarı zaten VFR
sekmesiyle meşgul. Yatay çubuk dikey yerden **bir kez** ödün verir.

Ölçüldü (Chromium, gerçek sayfa): çubuk 360/390/412/680px'te taşmıyor. 320px'te
36px taşıyor — orada yatay kaydırma devrede ve seçili sekme otomatik görünür
yapılıyor.

**Geniş ekranda ise SOL RAY.** İtiraz telefona aitti; masaüstünde durum tersine
döner. İçerik sütunu 680px'te **ortalanıyor**, yani solda zaten boş alan var:

| Ekran | İçerik sütunu | Soldaki boş alan |
|---|---|---|
| 390px | 358px | 16px |
| 768px | 680px | 44px |
| 1024px | 680px | **172px** |
| 1280px | 680px | **300px** |
| 1440px | 680px | **380px** |

`≥1024px`'te ray o boşluğa yerleşir (`position:fixed`, 140px) ve **içerik sütunu
hiç daralmaz** — telefondaki bedel burada yok. HTML aynı kalır; yalnızca CSS
`flex-direction`'ı değiştirir.

Konum `left:calc(50% - 496px)` ile hesaplanır: `496 = 340 (sütunun yarısı) + 16
(boşluk) + 140 (ray)`. Üçü birbirine bağlı, o yüzden bir test bu aritmetiği
**CSS'ten okuyarak** doğruluyor — `.sar` genişliği ya da ray genişliği
değişirse çakışma anında yakalanır.

**Rozetler çubukta, çünkü sekme içeriği gizliyor.** NOTAM sayfadayken
kaydırırken göz ucuyla görülüyordu; sekmenin arkasına girince yeni NOTAM'ı
fark etmenin tek yolu çubuktaki rozet kalır. Aynısı sis olasılığı için de
geçerli. NOTAM rozeti mevcut istemci JS'iyle aynı `id`'yi kullanır
(`notam-aktif-sayi`) — rozet mantığı tek yerde.

Sis rozeti **tam sayıya** yuvarlanır (`%28`), panel ondalığı gösterir: bir
sekme rozetinde `%27.8` sahte hassasiyettir — rozet "bakmalı mıyım?" sorusunu
yanıtlar, kesin değeri panel verir.

**JS yoksa sayfa bozulmaz.** Paneller HTML'de `hidden` DEĞİL; gizleme yalnızca
`<html class="js">` varken devreye girer ve o sınıfı `<head>` içindeki satır
içi betik gövde çizilmeden önce ekler (açılışta titreme olmaz). Betik
engellenirse çubuk hiç çizilmez ve sayfa eski "hepsi alt alta" hâline düşer —
boş değil.

Seçili sekme `localStorage`'a yazılır; okuma `try/catch` ile sarılıdır (gizli
sekmede erişim istisna atabilir) ve bilinmeyen bir değer reddedilir — yoksa
hiçbir CSS kuralıyla eşleşmeyen bir sekme sayfayı tamamen boş açardı.

Özet şerit ile sekme çubuğu **tek bir yapışkan blokta** (`.yapiskan-ust`).
İkisini ayrı ayrı yapışkan yapmak, çubuğa "şerit ne kadar yüksek?" diye sabit
bir `top:` değeri uydurmayı gerektirirdi; şerit dar ekranda satır kaydırdığı
için o sayı sabit değil.

Bölümler sekme içinde **ayrıca katlanmaz** — sekmeye basıp bir de başlığı
açmak iki tıklama olurdu. LVO'nun eski elle yazılmış aç/kapa mekanizması bu
yüzden kaldırıldı.

### 11.1. "İstatistik" Sekmesinin İçeriği

Arşivden öğrenilmiş her şey **tek katlanır başlık** altında toplandı:

- **İstatistiksel sis olasılığı** (önceden "Beklenti" altındaydı)
- **Tavan istatistiği** — göreli oranlar (önceden LVO Farkındalık Notları'ndaydı)
- **Görüş geçiş süreleri** — yeni; bkz. `sis_modeli/README.md`

**Ayrımın gerekçesi:** sayfa "bu ölçüm mü, tahmin mi, istatistik mi" ayrımını
her yerde koruyor ama istatistikler üç ayrı yere dağılmıştı. LVO panelinde
**kalan** notlar eşik karşılaştırmasıdır (METAR/TAF değeri şu eşiğin altında
mı) — onlar ölçüm. "Beklenti" başlığında **kalan** tek şey Open-Meteo model
tahmini.

### 12. Cron Güvenilirliği (ÖNEMLİ)

**GitHub zamanlanmış koşuları düşürür.** Bu depoda ölçüldü: dış kaynak
önbelleği `:3,23,43` (20 dakikada bir) ayarlıyken 26 saatte **78 yerine 6**
planlı koşu gerçekleşti; aralıklar 2–6 saat. Koşuların **hepsi başarılıydı** —
sorun kodda değil, GitHub'ın `schedule` olayını yüksek yükte geciktirmesi/
düşürmesi. Ana bot workflow'u da aynı durumda (4×/saat ayarlı, gerçekte 4–5
saat aralıklarla).

Bunun görünen sonucu: sayfa beklenenden seyrek güncelleniyor ve "Önümüzdeki
saatler" şeridi bir dönem tamamen kayboluyordu.

**Bu depoda alınan önlemler:**

1. Bayatlık eşiği gerçek kadansa göre ayarlandı (`TAHMIN_ESIK_DK = 360`) ve
   şerit bayatlayınca gizlenmek yerine **yaşını yazıyor**.
2. Bot workflow'u, önbellek bayatsa çalıştırmadan önce **bir kez tazelemeyi
   dener** (`continue-on-error: true`, 2 dakika sınırlı). Botun kodu hâlâ
   yalnızca yerel dosyayı okur — gevşek bağlılık sözleşmesi korunuyor, sadece
   tetikleme fırsatı artıyor. Sonuç bilerek commit edilmez; tek yazar
   `dis-kaynak-onbellek.yml`.
3. NOTAM listesi 12 saatten eski senkronla gösterilirse sayfada
   **"⚠ liste eski olabilir"** uyarısı çıkar.

**Gerçekten dakika hassasiyeti gerekiyorsa** tek güvenilir yol dışarıdan
tetiklemedir. Her iki workflow da `repository_dispatch` kabul eder:

```bash
# Ana bot
curl -X POST -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer <PAT>" \
  https://api.github.com/repos/<kullanici>/ltfj-bot/dispatches \
  -d '{"event_type":"run-ltfj-bot"}'

# Dış kaynak önbelleği
curl -X POST -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer <PAT>" \
  https://api.github.com/repos/<kullanici>/ltfj-bot/dispatches \
  -d '{"event_type":"dis-kaynak-onbellek"}'
```

PAT'in `repo` yetkisi olmalı. Bu isteği herhangi bir güvenilir zamanlayıcı
(kendi sunucun, ücretsiz bir cron servisi, bir Raspberry Pi) atabilir.

### 13. SPECI Boşluğu ve `gozlem_arsivi.csv`

**Sorun.** Sis geçiş sürelerini (`sis_modeli/gorus_gecis.py`) hesapladığımız
eğitim arşivi IEM ASOS'tan geliyor ve **SPECI içermiyor**. Ölçüldü: 274.907
satırın 274.901'i `:20`/`:50` dakikasında — yani düpedüz rutin METAR kadansı;
ızgara dışı toplam **6 satır (%0,002)**.

Bu ciddi bir kısıt, çünkü **SPECI tam da geçiş anlarında** yayımlanır. Görüş
30 dakikalık ızgarada örneklendiği için raporladığımız en hızlı düşüş "0,5
saat" görünür; gerçekte o **"≤0,5 saat"**tir. Misawa ve ark. (2026) dakika
çözünürlüğüne SPECI sayesinde çıkabiliyor.

**Canlı yol SPECI'yi yakalıyor.** MGM'den okuyan `ltfj_rasat.py` ızgara dışı
raporları görüyor: aynı ölçümde `state["olcum_gecmisi"]`'ndeki son 300 kaydın
**16'sı (%5,3)** `:20`/`:50` dışındaydı. Yani boşluk bizim hattımızda değil,
**IEM arşivinde**.

**Neden `olcum_gecmisi` yetmiyor.** İki nedenle:

- `OLCUM_GECMIS_LIMIT = 300` — kayan pencere (~6 gün), arşiv değil; sayfadaki
  trend grafikleri için boyutlandırılmış.
- **Görüş alanını hiç saklamıyor** (zaman/rüzgâr/tavan/QNH/sıcaklık/çiy). Tam
  da en çok ihtiyaç duyulan alan atılıyor.

Bu yapıyı büyütmek yanlış olurdu: `ltfj_state.json` her koşuda commit ediliyor,
sınırsız büyümesi state dosyasını şişirirdi.

**Çözüm: ayrı, ekleme-yalnızca bir dosya.** `ltfj_gozlem_arsivi.py` her koşuda
yeni METAR **ve SPECI**'leri görüş dahil `gozlem_arsivi.csv`'ye ekliyor.

| Karar | Gerekçe |
|---|---|
| Düz CSV, gzip değil | Dosya her koşuda git'e yazılıyor. Ekleme-yalnızca düz metinde git yalnızca **delta** saklar ve satır bazlı birleşir; gzip her commit'te yeni bir ikili blob olur ve birleştirilemez. |
| Tekillik anahtarı `(zaman, tip)` | Aynı dakikada hem METAR hem SPECI olabilir; yalnız zaman anahtarı biri diğerini ezerdi. |
| Zaman damgası UTC, saniye hassasiyetinde | Yerel saatli bir damga arşivi 3 saat kaydırırdı. |
| Yazarken sırala | Geciken bir SPECI dosyayı sırasızlaştırır, git diff'lerini de gereksiz büyütürdü. |
| `--birlestir` CLI'ı | İki koşu üst üste bindiğinde workflow `git reset --hard` yapıyor; ekleme-yalnızca bir dosyada bu, araya giren koşunun eklediklerini **kaybettirir**. `state_birlestir.py`'nin gözlem arşivi karşılığı. |
| Bot tarafında fail-open | Arşiv yazılamazsa METAR/TAF/bildirim akışı **etkilenmez** — ama hata `stderr`'e yazılır, sessizce yutulmaz. |

`sis_modeli/gorus_gecis.py` artık düz CSV'yi de okuyabiliyor, yani yeterli olay
biriktiğinde aynı analiz doğrudan bu dosyadan çalıştırılabilir:

```bash
python -m sis_modeli.gorus_gecis --veri gozlem_arsivi.csv
```

**Dürüst sınır — geriye dönük doldurma YOK.** Bu dosya **bugünden itibaren**
birikir. Mevcut "0,5 saat" tabanını geçmişe dönük düzeltmez; tablodaki
`p10 = 0,5 sa` değeri bugün de "≤0,5 sa" olarak okunmalıdır. Geçmiş SPECI'ler
ancak SPECI taşıyan başka bir arşiv kaynağı bulunursa gelir (IEM'in
`report_type=4` parametresi istekte zaten gönderiliyor — dönen veride karşılığı
çıkmadı; ayrıca araştırılmalı).

Boyut: ~50 gözlem/gün → ~18 bin satır/yıl, satır başı ~90 bayt = **yılda ~1,6 MB**.

## ⚠️ Yasal Uyarı

Bu yazılım tamamen **eğitim, simülasyon ve hobi amaçlı** olarak geliştirilmiştir. Havacılıkta hava durumu verileri hayati önem taşır. Bu botun sağladığı veriler gecikmeli, eksik veya hatalı olabilir. **Gerçek uçuş planlamaları veya gerçek havacılık operasyonları için kesinlikle KULLANILAMAZ.** Gerçek uçuş operasyonları için sadece yetkili ve resmi meteoroloji servis sağlayıcılarını kullanınız.

---

