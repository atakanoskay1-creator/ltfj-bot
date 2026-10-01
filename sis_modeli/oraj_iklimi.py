import csv
import gzip
import statistics
from datetime import datetime


def oraj_mi(hava, yakin_dahil=False):
    if not hava:
        return False
    kods = hava.split()
    for kod in kods:
        if kod.startswith("VC"):
            if yakin_dahil and "TS" in kod:
                return True
        else:
            if "TS" in kod:
                return True
    return False


def aylik_gun_sayisi(satirlar):
    ay_gunler = {}
    for s in satirlar:
        if oraj_mi(s["hava"]):
            ay = int(s["ay"])
            gun = s["zaman"][:10]
            if ay not in ay_gunler:
                ay_gunler[ay] = set()
            ay_gunler[ay].add(gun)
    
    sonuc = {}
    for ay in sorted(ay_gunler.keys()):
        sonuc[ay] = len(ay_gunler[ay])
    return sonuc


def saatlik_dagilim(satirlar):
    oraj_satirlar = [s for s in satirlar if oraj_mi(s["hava"])]
    if not oraj_satirlar:
        return {}
    
    toplam = len(oraj_satirlar)
    saat_sayilari = {}
    for s in oraj_satirlar:
        saat = int(s["saat"])
        saat_sayilari[saat] = saat_sayilari.get(saat, 0) + 1
        
    sonuc = {}
    for saat in sorted(saat_sayilari.keys()):
        yuzde = round(100 * saat_sayilari[saat] / toplam, 1)
        sonuc[saat] = yuzde
    return sonuc


def olay_sureleri(zamanlar, bosluk_dk=60):
    if not zamanlar:
        return []
    
    sirali = sorted(zamanlar)
    sureler = []
    olay_baslangic = sirali[0]
    
    for i in range(1, len(sirali)):
        fark = sirali[i] - sirali[i-1]
        if fark.total_seconds() > bosluk_dk * 60:
            # Yeni olay başlıyor, önceki olayın süresini hesapla
            sure = int((sirali[i-1] - olay_baslangic).total_seconds() // 60)
            sureler.append(sure)
            olay_baslangic = sirali[i]
            
    # Son olayın süresi
    sure = int((sirali[-1] - olay_baslangic).total_seconds() // 60)
    sureler.append(sure)
    
    return sureler


def main():
    yol = "sis_modeli/veri/ltfj_ozellik.csv.gz"
    satirlar = []
    with gzip.open(yol, "rt", encoding="utf-8") as f:
        okuyucu = csv.DictReader(f)
        for s in okuyucu:
            yil = s["zaman"][:4]
            if "2011" <= yil <= "2025":
                satirlar.append(s)
                
    # Ay başına yılda ortalama oraj günü
    ay_gun = aylik_gun_sayisi(satirlar)
    print("Ay başına yılda ortalama oraj günü:")
    for ay in sorted(ay_gun.keys()):
        ortalama = ay_gun[ay] / 15
        print(f"  {ay}: {ortalama:.1f}")
        
    # Saatlik dağılım
    dagilim = saatlik_dagilim(satirlar)
    print("Saatlik dağılım (UTC):")
    for saat in sorted(dagilim.keys()):
        print(f"  {saat}: {dagilim[saat]}%")
        
    # Olay süreleri
    zamanlar = [datetime.fromisoformat(s["zaman"]) for s in satirlar if oraj_mi(s["hava"])]
    sureler = olay_sureleri(zamanlar)
    
    if sureler:
        medyan = statistics.median(sureler)
        en_uzun = max(sureler)
        print(f"Olay sayısı: {len(sureler)}")
        print(f"Medyan süre: {medyan} dk")
        print(f"En uzun süre: {en_uzun} dk")
    else:
        print("Olay bulunamadı.")


if __name__ == "__main__":
    main()
