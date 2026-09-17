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

## Yöntem (planlanan)

- **Etiket:** gözlem anında görüş < 1000 m (sis) ve < 550 m (LVO seviyesi).
- **Özellikler:** sıcaklık−çiy noktası farkı (spread), rüzgâr hızı, mevcut
  görüş/tavan (süreklilik), ay, UTC saat, QNH.
- **Model:** lojistik regresyon / koşullu olasılık tablosu. Nadir olay olduğu
  için (LVO seviyesi yılda birkaç düzine saat) derin model uygun değil.
- **Doğrulama:** yıl bazlı ayrım (örn. 2003–2020 eğitim, 2021–günümüz test) ve
  basit bir baseline'a (süreklilik + iklim) karşı skor. Bu yapılmadan hiçbir
  sonuç "model çalışıyor" diye sunulmaz.

## Sınırlar

Bu bir **iklim + süreklilik** modelidir, fizik modeli değildir: yaklaşan bir
cepheyi göremez. ECMWF gibi sayısal hava tahmini ürünlerinin rakibi değil,
tamamlayıcısıdır. Çıktısı **resmî bir tahmin değildir** ve METAR/TAF'ın yerine
geçmez.

## Kullanım

```bash
# Arşivi çek ve türetilmiş veriyi üret (ağ gerekir - Actions'ta çalışır)
python -m sis_modeli.veri_cek --baslangic 2003 --bitis 2026

# Türetilmiş veriyi incele (ağ gerekmez)
python -m sis_modeli.istatistik
```
