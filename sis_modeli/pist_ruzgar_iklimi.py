import csv
import gzip
import math
import os
import sys

# ltfj_ayarlar modülü sis_modeli dizininde veya üst dizinde olabilir
# Proje yapısına göre import yolu ayarlanmalı.
# Genellikle sis_modeli bir paket ise: from ltfj_ayarlar import ...
# Eğer ltfj_ayarlar.py sis_modeli içinde değilse, sys.path ayarı gerekebilir.
# Ancak görev "tek kaynak" diyor ve CONVENTIONS.md'de ltfj_ayarlar.py'nin varlığından bahsediliyor.
# Standart bir python projesinde ltfj_ayarlar.py kök dizindeyse ve sis_modeli bir paketse:
# from ltfj_ayarlar import PIST_EKSENI_24
# Eğer ltfj_ayarlar.py sis_modeli içindeyse:
# from .ltfj_ayarlar import PIST_EKSENI_24
# Görev metninde "from ltfj_ayarlar import PIST_EKSENI_24" denmiş.
# Bu, ltfj_ayarlar'ın sys.path'te olması gerektiği anlamına gelir.
# Sis_modeli dizininde çalıştırıldığında kök dizin sys.path'te olmalı.

try:
    from ltfj_ayarlar import PIST_EKSENI_24
except ImportError:
    # Eğer doğrudan import edilemiyorsa, sis_modeli dizinini path'e ekleme denemesi
    # Ancak CONVENTIONS.md'ye göre "Yeni kütüphane ekleme" ve "Küçük değişiklik".
    # En güvenli yol, ltfj_ayarlar'ın kök dizinde olduğunu varsaymak ve betiğin kök dizinden çalıştırılmasını sağlamak.
    # Ya da sis_modeli/__init__.py varsa ve ltfj_ayarlar kökteyse, betik kökten çalıştırılmalı.
    # Burada basitçe import hatasını yakalayıp kullanıcıya bilgi verelim veya varsayalım.
    # Görev metni "from ltfj_ayarlar import PIST_EKSENI_24" diyor, bunu aynen kullanacağım.
    # Eğer hata verirse, bu bir kurulum/çalıştırma hatasıdır.
    raise

SINIFLAR = ("sakin", "degisken", "24_kuyruk", "06_kuyruk", "serbest")

def pist_bilesenleri(yon, hiz, pist_yonu):
    """
    Rüzgarın pist eksenine dik ve paralel bileşenlerini hesaplar.
    yon: Rüzgarın geldiği yön (derece)
    hiz: Rüzgar hızı (knot)
    pist_yonu: Pistin yönü (derece)
    Dönüş: (bas, yan)
    bas: Pist eksenine paralel bileşen. Negatifse kuyruk rüzgarı.
    yan: Pist eksenine dik bileşen (mutlak değer).
    """
    aci = math.radians(yon - pist_yonu)
    bas = hiz * math.cos(aci)
    yan = abs(hiz * math.sin(aci))
    return bas, yan

def sinif(yon, hiz):
    """
    Tek bir gözlemi sınıflandırır.
    yon: Rüzgar yönü (None olabilir)
    hiz: Rüzgar hızı
    """
    if hiz < 3:
        return "sakin"
    if yon is None:
        return "degisken"
    
    bas, _ = pist_bilesenleri(yon, hiz, PIST_EKSENI_24)
    
    if bas < -5:
        return "24_kuyruk"
    elif bas > 5:
        return "06_kuyruk"
    else:
        return "serbest"

def ozet(satirlar, anahtar):
    """
    Satırları anahtar alanına göre gruplayıp sınıf yüzdelerini hesaplar.
    satirlar: DictReader'dan gelen satır listesi
    anahtar: Gruplama alanı ("ay" veya "saat")
    """
    gruplar = {}
    
    for s in satirlar:
        hiz_str = s.get("ruzgar_hiz", "").strip()
        if not hiz_str:
            continue
            
        yon_str = s.get("ruzgar_yon", "").strip()
        if yon_str:
            yon = float(yon_str)
        else:
            yon = None
            
        hiz = float(hiz_str)
        
        # Grup anahtarı
        try:
            anahtar_deger = int(s[anahtar])
        except (ValueError, KeyError):
            continue
            
        if anahtar_deger not in gruplar:
            gruplar[anahtar_deger] = {sinif: 0 for sinif in SINIFLAR}
            gruplar[anahtar_deger]["n"] = 0
            
        sinif_ad = sinif(yon, hiz)
        gruplar[anahtar_deger][sinif_ad] += 1
        gruplar[anahtar_deger]["n"] += 1
        
    # Sonuçları hazırla
    sonuc = {}
    for k in sorted(gruplar.keys()):
        g = gruplar[k]
        n = g["n"]
        if n == 0:
            continue
        satir = {"n": n}
        for sinif_ad in SINIFLAR:
            satir[sinif_ad] = round(100 * g[sinif_ad] / n, 1)
        sonuc[k] = satir
        
    return sonuc

def main():
    veri_yolu = os.path.join(os.path.dirname(__file__), "veri", "ltfj_ozellik.csv.gz")
    
    if not os.path.exists(veri_yolu):
        print(f"[uyarı] Veri dosyası bulunamadı: {veri_yolu}", file=sys.stderr)
        return

    with gzip.open(veri_yolu, "rt", encoding="utf-8") as f:
        okuyucu = csv.DictReader(f)
        satirlar = []
        for satir in okuyucu:
            # Yalnızca 2011 ve sonrası
            zaman = satir.get("zaman", "")
            if zaman[:4] >= "2011":
                satirlar.append(satir)
                
    # Aylık özet
    ay_tablosu = ozet(satirlar, "ay")
    print("=== Aylık Pist/Rüzgar İklimi ===")
    for ay, veri in ay_tablosu.items():
        print(f"Ay {ay}: n={veri['n']}, sakin={veri['sakin']}%, degisken={veri['degisken']}%, "
              f"24_kuyruk={veri['24_kuyruk']}%, 06_kuyruk={veri['06_kuyruk']}%, serbest={veri['serbest']}%")
              
    # Saatlik özet
    saat_tablosu = ozet(satirlar, "saat")
    print("\n=== Saatlik Pist/Rüzgar İklimi ===")
    for saat, veri in saat_tablosu.items():
        print(f"Saat {saat}: n={veri['n']}, sakin={veri['sakin']}%, degisken={veri['degisken']}%, "
              f"24_kuyruk={veri['24_kuyruk']}%, 06_kuyruk={veri['06_kuyruk']}%, serbest={veri['serbest']}%")

if __name__ == "__main__":
    main()
