# Yerel Qwen ajanı — kurulum ve kullanım

Ajan **sizin bilgisayarınızda** çalışır. GitHub'daki `qwen-gorev` etiketli
issue'ları alır ve LM Studio'daki modele (Aider aracılığıyla) yaptırır.
Testleri kendisi çalıştırır; testler kırmızıysa hata çıktısını modele geri
verir (en fazla 3 tur). Yeşilse dalı push eder ve PR açar. **Merge etmez.**
Merge, inceleme sonrası sizin onayınızla yapılır.

```
Claude görev yazar ──► GitHub issue [qwen-gorev]
                                │  (5 dk'da bir bakar)
                         yerel ajan: dal açar → Qwen yazar → testler
                                │        ▲ kırmızıysa hata çıktısı geri
                                ▼        │
                         push + PR ──► Claude inceler ──► sizin onayınızla merge
```

## Güvenlik kuralları (kodda zorunlu)

- **Hangi issue'lar işlenir:** yalnızca `qwen-gorev` etiketli issue'lar.
  - Bu etiketi yalnızca repoya yazma yetkisi olanlar ekleyebilir.
  - Yazar ayrıca OWNER, COLLABORATOR ya da MEMBER olmalı; ya da `AJAN_EK_YAZARLAR` listesinde yer almalı.
- **Hangi dosyalar değişebilir:** yalnızca issue'daki `## Dosyalar` listesindekiler.
  - Şunlar listelense bile **her zaman yasak**: bot'un ürettiği dosyalar, dondurulmuş modeller, `.github/`, `araclar/` ve `CONVENTIONS.md`.
  - İhlal olursa hiçbir şey push edilmez.
- **Nerede çalışır:** yalnızca `--kur` ile hazırlanmış, işaretli **ayrı bir klonda**.
  - Ajan o klonu her görevden sonra sıfırlar.
  - Sizin çalışma klasörünüze dokunmaz.
- **Neye dokunmaz:** `main`'e push etmez, merge etmez, GitHub token'ını hiçbir çıktıya yazmaz.

## Kurulum (Windows, bir kez)

1. **Aider:**
   ```bat
   py -m pip install aider-install
   aider-install
   aider --version
   ```
2. **LM Studio:**
   - Modeli yükleyin; bağlam uzunluğu en az 32k olsun.
   - *Developer* sekmesinden sunucuyu başlatın (`http://localhost:1234`).
   - Modelin **API identifier** değerini not edin.
3. **GitHub token** (github.com → Settings → Developer settings → Personal access tokens → *Fine-grained*):
   - Repository access: **Only select repositories → ltfj-bot**
   - Permissions: **Contents**, **Issues** ve **Pull requests**, üçü de *Read and write*.
   - Süre: 90 gün. Token'ı kimseyle paylaşmayın; repoya da yazmayın.
4. **Ortam değişkenleri** (yeni bir cmd penceresi açınca geçerli olur):
   ```bat
   setx AJAN_GITHUB_TOKEN "github_pat_..."
   setx AJAN_MODEL "<LM Studio API identifier>"
   ```
5. **Ajan klonu:** OneDrive **dışında**, boş bir klasör olmalı. Mevcut klonunuzun içinden çalıştırın:
   ```bat
   py araclar\qwen_ajan.py --kur C:\ltfj-ajan
   ```
   Push için git'in mevcut GitHub girişiniz kullanılır.
6. **Test bağımlılıkları** (aynı Python'a):
   ```bat
   cd C:\ltfj-ajan
   py -m pip install -r requirements.txt -r requirements-dev.txt
   ```

## Çalıştırma

```bat
cd C:\ltfj-ajan
py araclar\qwen_ajan.py --bir-kez     REM bekleyen ilk görevi işler, çıkar
py araclar\qwen_ajan.py --dongu       REM 5 dk'da bir bakar (Ctrl+C ile durur)
```

LM Studio sunucusu açık olmalıdır.

## Görev (issue) biçimi

GitHub'da *New issue → Qwen görevi* şablonunu kullanın. Başlık kısa olsun. Gövde:

```
## Görev
Ne yapılacak, neden.

## Dosyalar
- ltfj_bot.py
- tests/test_yeni.py

## Kabul
- py -m pytest -q yeşil
- ... davranışı test edilsin
```

## Durum etiketleri

| Etiket | Anlamı |
|---|---|
| `qwen-gorev` | kuyrukta |
| `qwen-isleniyor` | ajan üzerinde çalışıyor |
| `qwen-bitti` | PR açıldı (issue'daki yorumda link var) |
| `qwen-basarisiz` | tamamlanamadı; neden ve test çıktısı yorumda |

Başarısız bir görevi yeniden denemek için `qwen-basarisiz` etiketini kaldırın.

## Ayarlar (isteğe bağlı ortam değişkenleri)

| Değişken | Varsayılan |
|---|---|
| `AJAN_LLM_URL` | `http://localhost:1234/v1` |
| `AJAN_TUR` | `3` (test-düzelt turu) |
| `AJAN_ARALIK_SN` | `300` |
| `AJAN_AIDER_ZAMAN_ASIMI` | `3600` sn |
| `AJAN_TEST_ZAMAN_ASIMI` | `1800` sn |
| `AJAN_EK_YAZARLAR` | boş (virgülle GitHub kullanıcı adları) |
| `AJAN_AIDER` | `aider` |
