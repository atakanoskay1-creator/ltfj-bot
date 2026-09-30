# ltfj-bot çalışma kuralları

Bu dosya, bu repoda çalışan her kodlama asistanı (yerel model, Aider,
Continue, Cline vb.) ve insan için geçerlidir. Aider: `aider --read CONVENTIONS.md`.

## Genel
- Yanıt dili Türkçe. Kod yorumları bulunduğu dosyanın üslubuna uyar
  (çoğu dosyada ASCII Türkçe: "gorus", "tavan").
- **Veri uydurma.** Bilinmeyen değer boş kalır; tahminle, ortalamayla ya da
  "makul" bir sayıyla doldurulmaz. Emin olmadığın bir şeyi olmuş gibi yazma.
- Yeni kütüphane ekleme. Mevcutlar yeterli (`requests`, standart kütüphane).
- Web sayfasında (index.html, sayfa_kaynak/) emoji yok.
- Küçük, tek amaçlı değişiklik yap. İstenmeyen dosyaya dokunma, "bu arada"
  düzeltmesi yapma.

## Test
- Her değişiklikten sonra: `python -m pytest -q` (yaklaşık 90 sn).
- Test kırmızıyken iş bitmiş sayılmaz. Testi geçirmek için testi silme,
  atlama (`skip`) ya da beklenen değeri gelişigüzel değiştirme.
- Hata düzeltmesinde önce hatayı gösteren, BAŞARISIZ olan bir test yaz;
  sonra düzelt.
- Kurulum: `pip install -r requirements.txt -r requirements-dev.txt`

## Dokunma
- **Bot üretir, elle değiştirme:** `index.html`, `ltfj_state.json`,
  `panel_veri.json`, `notam_veri.json`, `gozlem_arsivi.csv`,
  `gozlem_surumleri.csv`, `gozlem_arsivi_durum.json`, `tahmin_gunlugu.csv`,
  `tahmin_dogrulama.csv`, `dis_kaynak_cache.json`.
- **Dondurulmuş modeller (izleme dönemi, değişiklik yok):** `sis_modeli/`
  altındaki eğitim kodu ve veriler, `ltfj_sis_olasilik.py`,
  `ltfj_sis_olasilik_b.py`, `ltfj_tavan_tablosu.py`. Katsayı, eşik ve
  kalibrasyon değişikliği yapılmaz; yeni model deneyi başlatılmaz.
  İstisna: açıkça istenen SALT OKUMA analiz betikleri (`sis_modeli/`
  altında yeni dosya, mevcutları değiştirmeden).
- `.github/workflows/` değişiklikleri yalnızca açıkça istendiğinde.

## Güvenlik
- `NOTAC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY`,
  `VAPID_PRIVATE_KEY`, `FIREBASE_SERVICE_ACCOUNT` hiçbir log'a, HTML'e, JS'e,
  test çıktısına yazılmaz.
- `ltfj_bot.py`'yi gerçek anahtarlarla yerelde çalıştırma: Telegram grubuna
  gerçek mesaj gider ve state dosyaları değişir. Denemeyi testlerle yap.

## Davranış kuralları
- **Fail-open:** dış servis (MGM, Telegram, NOTAC, Firebase, Claude) hatası
  uyarı basar (`[uyarı] ...`, stderr), koşu devam eder; botu düşürmez.
- Arşiv ve günlük dosyaları **yalnızca eklemeyle** büyür; mevcut satır
  silinmez, değiştirilmez.
- Operasyonel karar üretme: pist ataması, clearance, kesin gecikme/iptal
  tahmini yok. Sayfa ve mesajlar bilgi amaçlıdır.

## Git
- `main`'e doğrudan commit yok. Her iş ayrı dalda (`qwen/<konu>`), PR ile.
- Bot `main`'e yaklaşık 30 dakikada bir commit atar: işe başlamadan
  `git pull origin main`.
- Force push ve geçmiş yeniden yazma yok.
