import math
import csv
import gzip
from ltfj_ayarlar import PIST_EKSENI_24   # 244.12 (derece), tek kaynak - kopyalama

SINIFLAR = ("sakin", "degisken", "24_kuyruk", "06_kuyruk", "serbest")

def pist_bilesenleri(yon, hiz, pist_yonu):
    aci = math.radians(yon - pist_yonu)
    bas = hiz * math.cos(aci)
    yan = abs(hiz * math.sin(aci))
    return (bas, yan)

def sinif(yon, hiz):
    if hiz < 3:
        return "sakin"
    if yon is None:
        return "degisken"
    bas, _ = pist_bilesenleri(yon, hiz, PIST_EKSENI_24)
    if bas < -5:
        return "24_kuyruk"
    if bas > 5:
        return "06_kuyruk"
    return "serbest"

def ozet(satirlar, anahtar):
    gruplar = {}
    for s in satirlar:
        hiz_str = s.get("ruzgar_hiz", "")
        if not hiz_str:
            continue
        hiz = float(hiz_str)
        yon_str = s.get("ruzgar_yon", "")
        yon = float(yon_str) if yon_str else None
        
        anahtar_deger = int(s[anahtar])
        if anahtar_deger not in gruplar:
            gruplar[anahtar_deger] = {c: 0 for c in SINIFLAR}
        
        s_sınıf = sinif(yon, hiz)
        gruplar[anahtar_deger][s_sınıf] += 1
    
    sonuc = {}
    for k in sorted(gruplar.keys()):
        sayilar = gruplar[k]
        n = sum(sayilar.values())
        if n == 0:
            continue
        ozet_satir = {"n": n}
        for c in SINIFLAR:
            ozet_satir[c] = round(100 * sayilar[c] / n, 1)
        sonuc[k] = ozet_satir
    return sonuc

def main():
    yol = "sis_modeli/veri/ltfj_ozellik.csv.gz"
    with gzip.open(yol, "rt", encoding="utf-8") as f:
        okuyucu = csv.DictReader(f)
        satirlar = []
        for satir in okuyucu:
            if satir.get("zaman", "")[:4] >= "2011":
                satirlar.append(satir)
        
        print("Aylık Özet:")
        ay_ozet = ozet(satirlar, "ay")
        for ay, veri in ay_ozet.items():
            print(f"  Ay {ay}: n={veri['n']}, sakin={veri['sakin']}%, degisken={veri['degisken']}%, 24_kuyruk={veri['24_kuyruk']}%, 06_kuyruk={veri['06_kuyruk']}%, serbest={veri['serbest']}%")
            
        print("\nSaatlik Özet (UTC):")
        saat_ozet = ozet(satirlar, "saat")
        for saat, veri in saat_ozet.items():
            print(f"  Saat {saat}: n={veri['n']}, sakin={veri['sakin']}%, degisken={veri['degisken']}%, 24_kuyruk={veri['24_kuyruk']}%, 06_kuyruk={veri['06_kuyruk']}%, serbest={veri['serbest']}%")

if __name__ == "__main__":
    main()
