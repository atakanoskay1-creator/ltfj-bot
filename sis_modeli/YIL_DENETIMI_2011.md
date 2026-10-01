# 2011 yıl denetimi — bulgu notu (salt okuma)

**Soru:** Eğitim verisinde (2011–2023) yıllık olay başlangıcı 10–50 arasında
değişirken 2011'de yalnızca 2. Veri eksik mi, yıl gerçekten sissiz mi?

**Araç:** `python sis_modeli/yil_denetimi.py` (repo kökünden). Model eğitmez,
dosya yazmaz. Not: `FG` sütunu yalnızca tam `FG` kodunu sayar (`BCFG`, `FZFG`
gibi kodlar bu sütuna girmez); `sis_kodu1` ile bu yüzden birebir aynı değildir.

## Yıllık tablo (çıktıdan)

| yıl | satır | g<1000 | g<5000 | BR | min görüş |
|---|---|---|---|---|---|
| 2011 | 17163 | **5** | 616 | 534 | 300 |
| 2012 | 17378 | 75 | 800 | 512 | 150 |
| 2013 | 17464 | 86 | 769 | 592 | 50 |
| 2020 | 16588 | 28 | 584 | 472 | 100 |
| 2022 | 17517 | 139 | 565 | 244 | 100 |

(tam tablo için betiği çalıştırın)

## Ay kırılımı: g<1000 / g<5000

| | Oca | Şub | Mar | Nis | May | Ara |
|---|---|---|---|---|---|---|
| 2011 | **0** / 98 | **0** / 98 | 2 / 122 | 0 / 46 | 3 / 29 | **0** / 129 |
| 2012 | 10 / 137 | 22 / 195 | 9 / 61 | 0 / 19 | 4 / 77 | 12 / 80 |
| 2013 | 18 / 118 | 5 / 86 | 0 / 53 | 17 / 74 | 15 / 106 | 2 / 50 |

## SONUÇ (01.10.2026): 2011 verisi büyük ölçüde LTBA'ya ait

Aşağıdaki "belirlenemez" sorusu cevaplandı. IEM `station=LTFJ` isteğine
2011 için **16.821 LTBA (Atatürk) METAR'ı ve yalnızca 343 LTFJ METAR'ı**
döndürüyor (kullanıcının indirdiği tam IEM çıktısında METAR metnindeki ICAO
koduyla sayıldı; CSV'nin `station` sütunu yanıltıcı biçimde "LTFJ"). Örnek:
`LTBA 312050Z 32015KT 7000 -SHRA FEW007 SCT025 BKN080 07/07 Q1009`.
Görüşün neredeyse hiç 1000 m altına inmemesi LTFJ'nin değil LTBA'nın 2011
iklimi. Yani kayıt farkı değil, **yanlış istasyon**. Ayrıntı ve alınan
önlem: `README.md` → "Veri kalitesi" (0).

## Bulgu (ilk denetim — yukarıdaki sonuçtan önce yazıldı)

- 2011'de veri **eksik değil**: satır sayısı tam, pus (BR) kodları ve 5000 m
  altı görüş diğer yıllarla aynı düzeyde.
- Ama görüş neredeyse hiç **1000 m altına inmemiş**: sis mevsiminde (Oca, Şub,
  Ara) sıfır. 5000 m altı gözlemlerin 1000 m altına inen payı diğer yıllarda
  %5–25, 2011'de **%0,8** — belirgin aykırı değer.
- Gerçekten sissiz bir yıl mı, yoksa o yılın görüş kaydında/aktarımında bir
  farklılık mı, bu veriyle **belirlenemez**. Kesin cevap için 2011 kışının
  ham METAR metinlerine ya da MGM'nin o yılın sis günü kayıtlarına bakılmalı.

## Etki ve karar

- 2011, Model A/B eğitim verisinde (224.825 anın ~17 bini). Hatalıysa taban
  oranı hafifçe düşük gösterir; yürüyen pencere değerlendirmesi 2015'ten
  başladığı için ölçülen başarı rakamlarını etkilemez.
- **Şimdi değişiklik yok** (izleme dönemi). Model ileride yeniden eğitilirse
  "2011 dışlansın mı?" sorusu bu not ve ham METAR kontrolüyle karara bağlanır.
