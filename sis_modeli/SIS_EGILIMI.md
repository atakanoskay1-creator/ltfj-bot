# Sis sıklığı eğilimi — bulgu notu (salt okuma, 01.10.2026)

**Soru:** LTFJ'de sisli gün sayısı 2012–2018'de ~24/yıl iken 2023–2025'te
9/yıl. Bu düşüş gerçek bir iklim/çevre değişimi mi, yoksa ölçüm/kayıt
kaynaklı mı?

**Araç:** `python -m sis_modeli.sis_egilimi` (repo kökünden). Model
eğitmez, dosya yazmaz. Üç bağımsız kaynağı karşılaştırır: LTFJ METAR,
ERA5 yeniden analizi (istasyon sensöründen bağımsız) ve LTFM METAR
(komşu istasyon, 2019+).

Not (01.10.2026): betik çıktısındaki 2011 satırı büyük ölçüde LTBA verisidir (`README.md` → "Veri kalitesi" (0)); dönem ortalamaları 2012'den başladığı için etkilenmez.

## Dönem ortalamaları (betik çıktısından)

| dönem | LTFJ sisli gün/yıl | LTFJ g<5000 satır/yıl | ERA5 sakin+doymuş gece saati* | LTFM sisli gün/yıl |
|---|---|---|---|---|
| 2012–2018 | **24.1** | 840 | 92.7 | — (veri yok) |
| 2019–2022 | 18.5 | 649 | **51.5** | 18.0 |
| 2023–2025 | **9.0** | 470 | **98.7** | 14.7 |

\* Eki–Nis geceleri (20–06 UTC), ERA5 bağıl nem ≥ %95 ve rüzgâr ≤ 7 km/h.

Yıl bazında tam tablo ve "sise elverişli gece gözleminde (spread ≤ 1 °C,
rüzgâr ≤ 4 kt) görüşün 1000 m altına inme payı" betik çıktısındadır:
2012–2018'de %4.1–10.7, 2019–2020 ve 2024–2025'te %1.8–3.0 (2021–2023
çiy noktası kusuru nedeniyle karşılaştırma dışı).

## Bulgu

1. **Veri eksik değil.** Satır sayısı ve gece gözlemi her yıl ~17.5 bin /
   ~8 bin; düşüş eksik kayıttan gelmiyor. 2011'den farklı olarak 5000 m
   altına inen gözlemlerin 1000 m altına inme payı da çökmemiş
   (2023–2025'te %7.6–10.5; 2012–2018'de %9–17 — biraz düşük ama aynı
   mertebede; 2011'de %0.8 idi).
2. **2019–2022 düşüşü atmosferle tutarlı.** ERA5'te sis mevsimi geceleri
   belirgin şekilde kuru (sakin+doymuş saat 92.7 → 51.5). Bu dönemdeki
   azalma gerçek bir kuru dönemle açıklanabilir.
3. **2023–2025 düşüşü atmosferle tutarlı DEĞİL.** ERA5 koşulları
   2012–2018 düzeyine geri dönmüş (98.7), ama LTFJ sisli günü 24 → 9.
   Aynı yıllarda LTFM'de benzer çöküş yok (2025'te 20 gün), LTFM'de
   5000 m altı gözlem sayısı da azalmamış; LTFJ'de ise 5000 m altı
   gözlemler de ~%44 azalmış. Ayrıca sise elverişli gecelerde sis
   oluşma payı düşmüş: koşullar oluşuyor ama görüş eskisi kadar inmiyor.
4. **ERA5 ile yıl yıl ilişki zayıf** (2012–2025 korelasyon −0.11). ERA5'in
   ~25 km çözünürlüğü yerel sisi çözemiyor; bu yüzden tek başına kanıt
   değil, yalnızca dönem düzeyinde bağlam veriyor.

**Sonuç:** 2023 sonrası düşüş büyük olasılıkla **LTFJ'ye özgü** bir
değişiklikten kaynaklanıyor — yerel çevre (yapılaşma, ısı adası,
meydan içi değişiklikler) ya da ölçüm/rasat uygulaması (görüş sensörü
yeri veya türü). Hangisi olduğu bu veriyle **belirlenemez**. Kesin cevap
için MGM/DHMİ'ye sorulabilecek soru: *"LTFJ'de görüş ölçüm sistemi veya
rasat uygulaması 2019 ve 2023 civarında değişti mi?"*

## Etki ve karar

- Model A 2011–2023 ile eğitildi; taban oranını büyük ölçüde eski
  (sisli) dönemden öğrendi. Holdout'taki hafif fazla tahmin (ortalama
  tahmin %0.43, gerçekleşen %0.34) bu bulguyla **tutarlı**.
- **Şimdi değişiklik yok** (izleme dönemi). Canlı tahmin günlüğünün
  kalibrasyon sonuçları bu notla birlikte okunmalı.
- V3'te sorulacak: son yıllara ağırlık veren / rejim pencereli eğitim ya
  da yalnızca son dönemle yeniden kalibrasyon gerekiyor mu? 2011
  (`YIL_DENETIMI_2011.md`) ve bu not aynı kararın parçası.
