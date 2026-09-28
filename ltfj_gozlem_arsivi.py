#!/usr/bin/env python3
"""SPECI DAHIL, GORUS TASIYAN, ekleme-yalnizca gozlem arsivi.

NEDEN VAR - IKI AYRI BOSLUK:

1) Egitim arsivi (sis_modeli/veri/ltfj_ozellik.csv.gz) IEM ASOS'tan geliyor
   ve SPECI ICERMIYOR. Olculdu: 274.907 satirin 274.901'i :20/:50'de,
   yani rutin METAR kadansi; izgara disi yalnizca 6 satir (%0.002).
   Oysa CANLI yol (MGM, ltfj_rasat.py) SPECI'yi yakaliyor - ayni olcumde
   state'teki son 300 kaydin 16'si (%5.3) izgara disiydi.

   Bu fark onemli cunku SPECI tam da GECIS anlarinda yayinlanir; sis
   olusum/dagilma surelerinin gercek hizi ancak onlarla gorulur (bkz.
   sis_modeli/gorus_gecis.py ve Misawa ve ark. 2026'nin SPECI vurgusu).
   Su an "0.5 saat" dedigimiz en hizli gecis aslinda "<=0.5 saat"tir.

2) state["olcum_gecmisi"] SPECI'yi tasiyor AMA:
   - OLCUM_GECMIS_LIMIT = 300 (~6 gun) - kayan pencere, arsiv degil;
     web sayfasindaki trend grafikleri icin boyutlandirilmis.
   - GORUS ALANINI HIC SAKLAMIYOR (zaman/ruzgar/tavan/qnh/sicaklik/ciy).
     Yani en cok ihtiyac duydugumuz alan atiliyor.

   olcum_gecmisi'ni buyutup gorus eklemek YANLIS olurdu: o yapi her
   kosuda ltfj_state.json icinde commit ediliyor ve sinirsiz buyumesi
   state dosyasini sisirirdi. Bu yuzden AYRI, ekleme-yalnizca bir dosya.

BICIM - DUZ CSV, gzip DEGIL: dosya her kosuda git'e commit ediliyor.
Ekleme-yalnizca duz metin git'te yalnizca DELTA saklar ve satir bazli
birlesir; gzip ise her commit'te tum dosyayi yeni bir ikili blob olarak
saklardi ve birlestirilemezdi.

BOYUT: ~50 gozlem/gun -> ~18 bin satir/yil, satir basi ~90 bayt =
yilda ~1,6 MB. Git icin sorun degil.

EGITIM ARSIVINE GERIYE DONUK DOLDURMA YOK: bu dosya 23.09.2026'dan
itibaren birikir. Gecmis SPECI'ler icin IEM'in SPECI tasiyip tasimadigi
ayrica arastirilmali (bkz. README "SPECI boslugu"). MGM'den geri
doldurma yalnizca son 24 saati kapsar (asagida).

IKI KATMAN (PR-2):

  gozlem_arsivi.csv     KANONIK, TEKIL - anahtar (zaman, tip). O anahtari
                        ILK yakalayan surumun ayristirilmis hali; bir daha
                        DEGISTIRILMEZ. "Ilk yakalanan" yalnizca bir ARSIV
                        davranisidir; meteorolojik olarak dogru/nihai
                        surum oldugu anlamina GELMEZ. gorus_gecis/deney0
                        bunu okur ve cift satir gormez.
  gozlem_surumleri.csv  HAM, EKLEME-YALNIZCA provenance - anahtar
                        (zaman, tip, metin_norm, mgm_status). MGM alanlari
                        oldugu gibi (observationTimeNormal, observationText,
                        id, observationStatus/Explanation "CCA   " dahil).
                        Status'a bakarak HICBIR surum secilmez/silinmez:
                        COR/CCA'nin revizyon semantigi bilinmiyor.

ZAMAN: kanonik `zaman` = observationTimeNormal (UTC) saniye/mikrosaniyesi
SIFIRLANMIS (kesme). MGM ".309" gibi kesirli saniye tasiyor; ham deger
`zaman_ham` sutununda aynen durur.

GERI DOLDURMA: bot her kosuda once canli hours=0 raporlarini, sonra AYRI
bir hours=24 cekimini isler (kosu_isle). Saglik iki cekim icin ayri tutulur
(gozlem_arsivi_durum.json).

  backfill_kurtarilan    DURUM GECISI: H24 islemesi BASLAMADAN ONCE kanonik
                         arsivde OLMAYAN ve H24 islemesi sonucunda ILK KEZ
                         eklenen gozlem anahtari (kanonik `kaynak` =
                         backfill_h24; yazma aninda kaydedilir).
  60dk_uzeri_gec_ingest  alinma_zamani - zaman > 60 dk olan kanonik satir,
                         kaynaktan bagimsiz. Iki metrik AYRIDIR: 06:50'yi
                         07:24'te kurtaran backfill "kurtarilan"dir ama
                         "60 dk uzeri" degildir.

Eksik izgara slotu: `bekleniyor` (24 sa penceresinde) ya da
`backfill_penceresi_disinda`; eksik slota hicbir deger yazilmaz.
"""

import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
VARSAYILAN_DOSYA = KLASOR / "gozlem_arsivi.csv"
SURUM_DOSYASI = KLASOR / "gozlem_surumleri.csv"
DURUM_DOSYASI = KLASOR / "gozlem_arsivi_durum.json"

# Sutun sirasi SABIT - yeni alan yalnizca SONA eklenir, yoksa eski
# satirlar kayar. Okuyucu eksik sutunu bos sayar.
SUTUNLAR = ("zaman", "tip", "gorus", "tavan", "sicaklik", "cig_noktasi",
            "ruzgar_yon", "ruzgar_hiz", "ruzgar_hamle", "qnh", "hava", "cavok",
            # PR-2: bu anahtari ILK ekleyen cekimin zamani ve kaynagi.
            # PR-2 oncesi satirlarda bos ("bilinmiyor").
            "alinma_zamani", "kaynak")
# Kanonik satirin METAR'dan AYRISTIRILAN alanlari (zaman/tip/provenance haric).
AYRISTIRMA_SUTUNLARI = SUTUNLAR[2:12]

# Surum (provenance) katmani: MGM'nin ham alanlari OLDUGU GIBI.
SURUM_SUTUNLARI = ("zaman", "tip", "zaman_ham", "metin", "mgm_id",
                   "mgm_status", "mgm_status_aciklama", "mgm_type",
                   "mgm_type_aciklama", "alinma_zamani", "kaynak")

GOZLEM_TIPLERI = ("METAR", "SPECI")
KAYNAK_CANLI = "canli_h0"
KAYNAK_BACKFILL = "backfill_h24"
# MGM kesfi (PR #99): hours=24 `data` alani son 24 saatin 48/48 izgara
# METAR'ini dondurdu. Pencere buna SABITLENDI; baska degere otomatik
# gecis yok.
BACKFILL_SAAT = 24
# Geri doldurma cekimi TEK deneme, kisa zaman asimi: bot is akisi 5 dk ile
# sinirli ve canli akis (state/sayfa commit'i) bundan etkilenmemeli. Kacan
# cekim bir sonraki kosuda 24 saatlik pencerede zaten yeniden denenir.
BACKFILL_DENEME = 1
BACKFILL_ZAMAN_ASIMI = 20
GEC_INGEST_DK = 60
IZGARA_DAKIKALARI = (20, 50)
# Kesifte gozlenen eslesme (METAR -> 4/SATU, SPECI -> 5/SPTU). YALNIZCA
# uyusmazlik SAYACI icin; tip her zaman metnin ilk kelimesinden gelir.
TIP_KODU = {"METAR": "4", "SPECI": "5"}
LISTE_SINIRI = 20


# ------------------------------------------------------------ yardimcilar ---
def _utc_iso(z: datetime) -> str:
    return z.astimezone(timezone.utc).isoformat(timespec="seconds")


def kanonik_zaman(z: datetime) -> str:
    """Kanonik gozlem zamani: UTC, saniye ve mikrosaniye SIFIRLANMIS.

    KESME, yuvarlama degil: 06:19:59.9 -> 06:19 olur ve izgara disi METAR
    olarak gorunur; sessizce 06:20'ye cekilmez. Ham deger surum
    katmaninda `zaman_ham` olarak aynen saklanir."""
    return z.astimezone(timezone.utc).replace(second=0, microsecond=0).isoformat()


def _dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def _ham(v) -> str:
    return "" if v is None else str(v)


def metin_norm(metin) -> str:
    """YALNIZCA karsilastirma icin: bosluklar teklenir, sondaki '=' atilir.
    Dosyaya ham metin yazilir."""
    return " ".join((metin or "").split()).rstrip("=").rstrip()


def surum_anahtari(s: dict) -> tuple:
    """(zaman, tip, metin_norm, mgm_status).

    ANAHTARDA OLMAYANLAR: zaman_ham (ayni gozlemin .309 / .xxx gelmesi yeni
    surum degil), mgm_id (kalici kimlik oldugu kanitlanmadi), alinma_zamani.
    mgm_status ANAHTARDA: ayni metnin NORMAL -> CCA degismesi kaynakta
    gercek bir degisikliktir ve kaybolmamali."""
    return (s.get("zaman") or "", s.get("tip") or "",
            metin_norm(s.get("metin")), s.get("mgm_status") or "")


def _satir_kur(rapor: dict, cozum: dict, zaman: str = None,
               alinma_zamani: str = "", kaynak: str = "") -> dict:
    """Tek bir METAR/SPECI'yi kanonik arsiv satirina cevirir.

    `hava` listesi bosluk ayrili tek dizeye cevriliyor - egitim
    arsivindeki (ltfj_ozellik.csv.gz) 'hava' sutunuyla AYNI bicim, ki
    ikisi ileride birlestirilebilsin."""
    hava = cozum.get("hava") or []
    return {
        "zaman": zaman or kanonik_zaman(rapor["zaman"]),
        "tip": rapor["tip"],
        "gorus": cozum.get("gorus"),
        "tavan": cozum.get("tavan"),
        "sicaklik": cozum.get("sicaklik"),
        "cig_noktasi": cozum.get("cig_noktasi"),
        "ruzgar_yon": cozum.get("ruzgar_yon"),
        "ruzgar_hiz": cozum.get("ruzgar_hiz"),
        "ruzgar_hamle": cozum.get("ruzgar_hamle"),
        "qnh": cozum.get("qnh"),
        "hava": " ".join(hava) if isinstance(hava, list) else (hava or ""),
        "cavok": int(bool(cozum.get("cavok"))),
        "alinma_zamani": alinma_zamani or "",
        "kaynak": kaynak or "",
    }


def _surum_satiri(rapor: dict, zaman: str, alinma_zamani: str, kaynak: str) -> dict:
    metin = rapor.get("metin_ham")
    if metin is None:
        metin = rapor.get("metin")
    return {
        "zaman": zaman,
        "tip": rapor["tip"],
        "zaman_ham": _ham(rapor.get("zaman_ham")),
        "metin": _ham(metin),
        "mgm_id": _ham(rapor.get("id")),
        "mgm_status": _ham(rapor.get("mgm_status")),
        "mgm_status_aciklama": _ham(rapor.get("mgm_status_aciklama")),
        "mgm_type": _ham(rapor.get("mgm_type")),
        "mgm_type_aciklama": _ham(rapor.get("mgm_type_aciklama")),
        "alinma_zamani": alinma_zamani or "",
        "kaynak": kaynak or "",
    }


def _csv_oku(dosya) -> list[dict]:
    if dosya is None or not Path(dosya).exists():
        return []
    with Path(dosya).open("r", encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _csv_yaz(satirlar: list, sutunlar: tuple, dosya) -> None:
    dosya = Path(dosya)
    dosya.parent.mkdir(parents=True, exist_ok=True)
    with dosya.open("w", encoding="utf-8", newline="") as f:
        y = csv.DictWriter(f, fieldnames=sutunlar, extrasaction="ignore")
        y.writeheader()
        for s in satirlar:
            y.writerow({k: ("" if s.get(k) is None else s.get(k)) for k in sutunlar})


def _deger_demeti(s: dict, sutunlar: tuple) -> tuple:
    return tuple("" if s.get(k) is None else str(s.get(k)) for k in sutunlar)


# ------------------------------------------------------ kanonik katman ---
def oku(dosya: Path = VARSAYILAN_DOSYA) -> list[dict]:
    """Arsivi okur; yoksa bos liste doner (hata DEGIL - ilk kosu)."""
    return _csv_oku(dosya)


def yaz(satirlar: list, dosya: Path = VARSAYILAN_DOSYA) -> None:
    """Zaman damgasina gore SIRALI ve TEKIL yazar.

    Siralama sart: dosya ekleme-yalnizca ama bot gecmise donuk bir rapor
    gorebilir (geri doldurma, geciken SPECI). Sirasiz dosya hem okunmaz
    hem de git diff'lerini gereksiz buyutur. Cagiranlar ayni anahtardan
    iki FARKLI satir vermez (birlestir celiskiyi once cozer ve kaydeder)."""
    tekil = {}
    for s in satirlar:
        tekil[(s.get("zaman"), s.get("tip"))] = s
    sirali = sorted(tekil.values(), key=lambda s: (s.get("zaman") or "",
                                                   s.get("tip") or ""))
    _csv_yaz(sirali, SUTUNLAR, dosya)


# -------------------------------------------------------- surum katmani ---
def surumleri_oku(dosya: Path = SURUM_DOSYASI) -> list[dict]:
    return _csv_oku(dosya)


def _surum_sirasi(s: dict) -> tuple:
    return (s.get("zaman") or "", s.get("tip") or "", s.get("alinma_zamani") or "",
            s.get("mgm_status") or "", s.get("metin") or "", s.get("zaman_ham") or "",
            s.get("mgm_id") or "")


def surumleri_yaz(satirlar: list, dosya: Path = SURUM_DOSYASI) -> None:
    """Surum anahtarina gore TEKIL (en erken alinan kalir) ve sirali yazar."""
    tekil = {}
    for s in sorted(satirlar, key=_surum_sirasi):
        tekil.setdefault(surum_anahtari(s), s)
    _csv_yaz(sorted(tekil.values(), key=_surum_sirasi), SURUM_SUTUNLARI, dosya)


# ------------------------------------------------------------- isleme ---
def arsive_isle(raporlar: list, coz, kaynak: str = "", alinma_zamani: datetime = None,
                dosya: Path = VARSAYILAN_DOSYA,
                surum_dosyasi: Path = SURUM_DOSYASI) -> dict:
    """Raporlari iki katmana isler; ne olduguna dair sayaclari doner.

    coz: metar_coz gibi (metin -> cozum). Disaridan veriliyor ki bu modul
    ltfj_analiz'e bagimli olmasin.

    KANONIK: (zaman, tip) arsivde yoksa ilk goruldugu surumun ayristirilmis
    hali eklenir; VARSA HIC DOKUNULMAZ. "Ilk yakalanan" yalnizca arsiv
    davranisidir - meteorolojik olarak dogru/nihai surum iddiasi DEGIL.
    SURUM: surum anahtari yoksa ham satir eklenir. Hicbir satir silinmez,
    status'a bakilarak hicbir surum secilmez.

    `eklenen_anahtarlar` bir DURUM GECISIDIR: bu cagri BASLAMADAN ONCE
    kanonik arsivde olmayan ve bu cagrinin sonunda arsivde olan anahtarlar.
    kaynak=backfill_h24 icin bu tam olarak `backfill_kurtarilan`dir."""
    alinma = _utc_iso(alinma_zamani) if alinma_zamani else ""
    mevcut = oku(dosya)
    kanonik = {(s.get("zaman"), s.get("tip")): s for s in mevcut}
    once = set(kanonik)
    surumler = surumleri_oku(surum_dosyasi) if surum_dosyasi is not None else None
    surum_idx = {surum_anahtari(s): s for s in (surumler or [])}

    sonuc = {"kaynak": kaynak, "rapor": 0,
             "kanonik_eklenen": {t: 0 for t in GOZLEM_TIPLERI},
             "surum_eklenen": 0, "mevcut_anahtara_yeni_surum": 0,
             "ayni_surum_farkli_ham_zaman": 0, "ayni_surum_farkli_id": 0,
             "tip_kodu_uyusmazligi": 0, "cozulemeyen": 0, "zamansiz": 0,
             "eklenen_anahtarlar": []}
    yeni, yeni_surum = [], []
    for r in raporlar:
        tip = r.get("tip")
        if tip not in GOZLEM_TIPLERI:
            continue
        sonuc["rapor"] += 1
        if not r.get("zaman"):
            sonuc["zamansiz"] += 1
            continue
        zaman = kanonik_zaman(r["zaman"])
        anahtar = (zaman, tip)
        kod = r.get("mgm_type")
        if kod is not None and _ham(kod) != TIP_KODU[tip]:
            sonuc["tip_kodu_uyusmazligi"] += 1

        if surumler is not None:
            s = _surum_satiri(r, zaman, alinma, kaynak)
            k = surum_anahtari(s)
            eski = surum_idx.get(k)
            if eski is None:
                surum_idx[k] = s
                yeni_surum.append(s)
                if anahtar in kanonik:
                    sonuc["mevcut_anahtara_yeni_surum"] += 1
            else:
                if (eski.get("zaman_ham") or "") != s["zaman_ham"]:
                    sonuc["ayni_surum_farkli_ham_zaman"] += 1
                if (eski.get("mgm_id") or "") != s["mgm_id"]:
                    sonuc["ayni_surum_farkli_id"] += 1

        if anahtar in kanonik:
            continue
        try:
            cozum = coz(r["metin"])
        except Exception as e:                       # tek bozuk rapor
            # Surum satiri (ham metin) yine yazildi; kanonik satir BOS
            # alanlarla eklenmez - tuketiciler onu "deger yok" okurdu.
            print(f"[uyarı] gözlem arşivi: rapor çözülemedi, atlanıyor: {e}",
                  file=sys.stderr)
            sonuc["cozulemeyen"] += 1
            continue
        satir = _satir_kur(r, cozum, zaman, alinma, kaynak)
        kanonik[anahtar] = satir
        yeni.append(satir)

    if yeni:
        yaz(mevcut + yeni, dosya)
    if yeni_surum:
        surumleri_yaz(surumler + yeni_surum, surum_dosyasi)

    eklenen = sorted(set(kanonik) - once)
    for _, t in eklenen:
        sonuc["kanonik_eklenen"][t] += 1
    sonuc["eklenen_anahtarlar"] = [f"{z} {t}" for z, t in eklenen]
    sonuc["surum_eklenen"] = len(yeni_surum)
    return sonuc


def ekle(raporlar: list, coz, dosya: Path = VARSAYILAN_DOSYA) -> int:
    """Yalnizca kanonik katmana ekler; EKLENEN satir sayisini doner.

    Ayni (zaman, tip) ciftinden ikinci kez eklenmez - bot her kosuda ayni
    raporu yeniden gorur."""
    s = arsive_isle(raporlar, coz, dosya=dosya, surum_dosyasi=None)
    return sum(s["kanonik_eklenen"].values())


# --------------------------------------------------------- birlestirme ---
def _kanonik_oncelik(s: dict) -> tuple:
    # 1) PR-2 oncesi (alinma_zamani bos) satir once, 2) en erken alinma,
    # 3) kaynak, 4) icerik sirasi (esit alinmada deterministik son care).
    al = s.get("alinma_zamani") or ""
    return (1 if al else 0, al, s.get("kaynak") or "", _deger_demeti(s, SUTUNLAR))


def _kural(sec: dict, ele: dict) -> str:
    a, b = _kanonik_oncelik(sec), _kanonik_oncelik(ele)
    if a[0] != b[0]:
        return "eski_satir_onceligi"
    if a[1] != b[1]:
        return "en_erken_alinma"
    if a[2] != b[2]:
        return "kaynak_sirasi"
    return "icerik_sirasi"


def _kanonik_birlestir(sa: list, sb: list, tespit: str) -> tuple:
    gruplar = {}
    for s in sa + sb:
        gruplar.setdefault((s.get("zaman"), s.get("tip")), []).append(s)
    sonuc, catismalar = [], []
    for (zaman, tip), liste in gruplar.items():
        benzersiz = {}
        for s in liste:
            benzersiz.setdefault(_deger_demeti(s, SUTUNLAR), s)
        sirali = sorted(benzersiz.values(), key=_kanonik_oncelik)
        sec = sirali[0]
        sonuc.append(sec)
        for ele in sirali[1:]:
            # Iki kosunun AYNI gozlemi ayni icerikle farkli zamanda alması
            # (yalnizca alinma_zamani/kaynak farki) NORMALDIR: en erken
            # alinan kalir, celiski degildir. Celiski = ayristirilmis
            # icerik farki.
            if (_deger_demeti(ele, AYRISTIRMA_SUTUNLARI)
                    == _deger_demeti(sec, AYRISTIRMA_SUTUNLARI)):
                continue
            catismalar.append({
                "tur": "kanonik", "zaman": zaman, "tip": tip,
                "kural": _kural(sec, ele), "tespit_zamani": tespit,
                "secilen": dict(zip(SUTUNLAR, _deger_demeti(sec, SUTUNLAR))),
                "elenen": dict(zip(SUTUNLAR, _deger_demeti(ele, SUTUNLAR))),
            })
    return sonuc, catismalar


_SURUM_HAM = tuple(c for c in SURUM_SUTUNLARI if c not in ("alinma_zamani", "kaynak"))


def _surum_birlestir(sa: list, sb: list, tespit: str) -> tuple:
    gruplar = {}
    for s in sa + sb:
        gruplar.setdefault(surum_anahtari(s), []).append(s)
    sonuc, catismalar = [], []
    for liste in gruplar.values():
        sirali = sorted(liste, key=_surum_sirasi)
        sec = sirali[0]
        sonuc.append(sec)
        # Ayni surumu iki kosunun farkli zamanda gormesi NORMAL (yalnizca
        # alinma_zamani/kaynak farkli). Ham alanlar farkliysa kayda gecer.
        for ele in sirali[1:]:
            if _deger_demeti(ele, _SURUM_HAM) != _deger_demeti(sec, _SURUM_HAM):
                catismalar.append({
                    "tur": "surum_ham_fark", "zaman": sec.get("zaman"),
                    "tip": sec.get("tip"), "kural": "en_erken_alinma",
                    "tespit_zamani": tespit,
                    "secilen": dict(zip(SURUM_SUTUNLARI, _deger_demeti(sec, SURUM_SUTUNLARI))),
                    "elenen": dict(zip(SURUM_SUTUNLARI, _deger_demeti(ele, SURUM_SUTUNLARI))),
                })
    return sonuc, catismalar


def _catisma_bildir(catismalar: list) -> None:
    for c in catismalar:
        baslik = ("DEĞİŞMEZLİK İHLALİ - kanonik çelişki" if c["tur"] == "kanonik"
                  else "sürüm ham alan farkı")
        print(f"[UYARI] gözlem arşivi birleştirme: {baslik}: {c['zaman']} {c['tip']} "
              f"- kural {c['kural']}; seçilen "
              f"{json.dumps(c['secilen'], ensure_ascii=False)} / elenen "
              f"{json.dumps(c['elenen'], ensure_ascii=False)}", file=sys.stderr)


def _kanonik_dosya_birlestir(a: Path, b: Path, hedef: Path, tespit: str) -> list:
    satirlar, catismalar = _kanonik_birlestir(oku(a), oku(b), tespit)
    yaz(satirlar, hedef)
    _catisma_bildir(catismalar)
    return catismalar


def _surum_dosya_birlestir(a: Path, b: Path, hedef: Path, tespit: str) -> list:
    satirlar, catismalar = _surum_birlestir(surumleri_oku(a), surumleri_oku(b), tespit)
    surumleri_yaz(satirlar, hedef)
    _catisma_bildir(catismalar)
    return catismalar


def birlestir(a: Path, b: Path, hedef: Path, tespit_zamani: datetime = None) -> int:
    """Iki kanonik arsiv dosyasini BIRLESTIRIR (zaman+tip birlesimi).

    NEDEN GEREKLI: ltfj.yml iki kosu ust uste bindiginde
    `git reset --hard origin/<dal>` yapip kendi dosyalarini geri
    kopyaliyor. Ekleme-yalnizca bir dosyada bu, uzaktaki kosunun
    eklediklerini KAYBETTIRIR.

    Ayni anahtarda yalnizca alinma_zamani/kaynak farkliysa (iki kosu ayni
    gozlemi ayni icerikle almis) en erken alinan kalir; bu celiski DEGIL.
    Ayni anahtarda FARKLI ayristirilmis icerik bir DEGISMEZLIK IHLALIDIR
    (normal calismada olusmamali). Secim deterministiktir (eski satir,
    sonra en erken alinma) ama GIZLENMEZ: stderr'e acik uyari; bot
    kosusunda (birlestir_bizim) durum dosyasinda sayilir. Ham farkli
    surumler zaten gozlem_surumleri.csv'de denetlenebilir."""
    tespit = _utc_iso(tespit_zamani or datetime.now(timezone.utc))
    _kanonik_dosya_birlestir(a, b, hedef, tespit)
    return len(oku(hedef))


def surumleri_birlestir(a: Path, b: Path, hedef: Path,
                        tespit_zamani: datetime = None) -> int:
    tespit = _utc_iso(tespit_zamani or datetime.now(timezone.utc))
    _surum_dosya_birlestir(a, b, hedef, tespit)
    return len(surumleri_oku(hedef))


def catisma_bos() -> dict:
    return {"kanonik_catisma_sayisi": 0, "kanonik_catisma_son": [],
            "surum_ham_fark_sayisi": 0, "surum_ham_fark_son": []}


def catisma_guncelle(onceki: list, yeni: list) -> dict:
    """Durum dosyasindaki celiski sayaclari (kalici, ayri dosya YOK).

    onceki: iki tarafin (uzak + bizim) durum['catisma'] bolumleri.
    Sayac, celiski gorulen FARKLI (zaman, tip) anahtar sayisidir: ayni
    anahtar sonraki birlestirme denemelerinde yeniden tespit edilirse
    tekrar sayilmaz (son listesiyle karsilastirilir). Iki taraftan buyuk
    olan sayac taban alinir. Normal calismada her sey 0 kalir."""
    out = catisma_bos()
    for tur in ("kanonik_catisma", "surum_ham_fark"):
        sayi = max([int((o or {}).get(f"{tur}_sayisi") or 0) for o in onceki] or [0])
        son, goruldu = [], set()
        for o in onceki:
            for c in (o or {}).get(f"{tur}_son") or []:
                k = (c.get("zaman"), c.get("tip"))
                if k not in goruldu:
                    goruldu.add(k)
                    son.append(c)
        etiket = "kanonik" if tur == "kanonik_catisma" else "surum_ham_fark"
        for c in yeni:
            k = (c["zaman"], c["tip"])
            if c["tur"] != etiket or k in goruldu:
                continue
            goruldu.add(k)
            sayi += 1
            son.append({"zaman": c["zaman"], "tip": c["tip"], "kural": c["kural"],
                        "tespit_zamani": c["tespit_zamani"]})
        son.sort(key=lambda c: (c.get("tespit_zamani") or "", c.get("zaman") or "",
                                c.get("tip") or ""))
        out[f"{tur}_sayisi"] = sayi
        out[f"{tur}_son"] = son[-LISTE_SINIRI:]
    return out


# -------------------------------------------------------- eksik slotlar ---
def _izgarada(z: datetime) -> bool:
    return z.minute in IZGARA_DAKIKALARI and z.second == 0 and z.microsecond == 0


def eksik_slotlar(kanonik_satirlar: list, simdi: datetime,
                  backfill_yaniti: dict = None) -> list[dict]:
    """Ilk arsivlenmis izgara METAR'indan `simdi`ye kadar her :20/:50 slotu;
    yalnizca kanonik bir METAR slotu doldurur (SPECI DOLDURMAZ).

    durum:
      bekleniyor                  slot > simdi - 24 sa (geri doldurma
                                  penceresinde; sonraki kosu getirebilir)
      backfill_penceresi_disinda  slot <= simdi - 24 sa. MGM'nin bu slotu hic
                                  yayinlayip yayinlamadigina dair iddia YOK.
    mgm_yanitinda_yok: yalnizca bu kosunun basarili H24 yaniti slotu
    kapsiyorsa True/False; aksi halde None. Eksik slota DEGER YAZILMAZ."""
    metar = set()
    for s in kanonik_satirlar:
        if s.get("tip") != "METAR":
            continue
        z = _dt(s.get("zaman"))
        if z is not None and _izgarada(z):
            metar.add(z.astimezone(timezone.utc))
    if not metar:
        return []
    simdi = simdi.astimezone(timezone.utc)
    sinir = simdi - timedelta(hours=BACKFILL_SAAT)
    adim = timedelta(minutes=30)
    out = []
    t = min(metar)
    while t <= simdi:
        if t not in metar:
            d = {"slot": t.isoformat(),
                 "durum": "bekleniyor" if t > sinir else "backfill_penceresi_disinda",
                 "mgm_yanitinda_yok": None}
            if (d["durum"] == "bekleniyor" and backfill_yaniti
                    and backfill_yaniti.get("en_eski") and backfill_yaniti.get("en_yeni")
                    and backfill_yaniti["en_eski"] <= t <= backfill_yaniti["en_yeni"]):
                d["mgm_yanitinda_yok"] = t not in backfill_yaniti["metar"]
            out.append(d)
        t += adim
    return out


def _en_uzun_bosluk(eksikler: list) -> dict | None:
    en, bas, onceki, n = None, None, None, 0
    for d in eksikler:
        t = _dt(d["slot"])
        if onceki is not None and t - onceki == timedelta(minutes=30):
            n += 1
        else:
            bas, n = t, 1
        if en is None or n > en["slot_sayisi"]:
            en = {"baslangic": bas.isoformat(), "bitis": t.isoformat(), "slot_sayisi": n}
        onceki = t
    return en


# ------------------------------------------------------------ durum ---
def yanit_ozeti(raporlar: list) -> dict:
    tipler = {}
    zamanlar = []
    for r in raporlar:
        tipler[r.get("tip")] = tipler.get(r.get("tip"), 0) + 1
        if r.get("tip") in GOZLEM_TIPLERI and r.get("zaman"):
            zamanlar.append(r["zaman"])
    return {"kayit": len(raporlar),
            "METAR": tipler.get("METAR", 0), "SPECI": tipler.get("SPECI", 0),
            "TAF": tipler.get("TAF", 0),
            "en_eski": kanonik_zaman(min(zamanlar)) if zamanlar else None,
            "en_yeni": kanonik_zaman(max(zamanlar)) if zamanlar else None}


def _backfill_yaniti(raporlar: list) -> dict:
    metar = set()
    for r in raporlar:
        if r.get("tip") == "METAR" and r.get("zaman"):
            z = _dt(kanonik_zaman(r["zaman"]))
            if _izgarada(z):
                metar.add(z)
    return {"metar": metar, "en_eski": min(metar) if metar else None,
            "en_yeni": max(metar) if metar else None}


def _ayristirma_farkli(kanonik: dict, surumler: list, coz) -> list:
    """Surum metni BUGUNKU ayristiriciyla cozuldugunde kanonik satirin
    ayristirilmis alanlarindan farkli cikan anahtarlar. (Fark kaynak
    degisikligi de olabilir, ayristirici degisikligi de - yorum yok.)"""
    farkli = set()
    for s in surumler:
        k = (s.get("zaman"), s.get("tip"))
        kan = kanonik.get(k)
        if kan is None or k in farkli:
            continue
        try:
            cozum = coz(" ".join((s.get("metin") or "").split()))
        except Exception:
            continue
        yeni = _satir_kur({"tip": s.get("tip")}, cozum, s.get("zaman"))
        if _deger_demeti(yeni, AYRISTIRMA_SUTUNLARI) != _deger_demeti(kan, AYRISTIRMA_SUTUNLARI):
            farkli.add(k)
    return sorted(farkli)


def durum_ozeti(kanonik_satirlar: list, surumler: list, simdi: datetime,
                coz=None, backfill_yaniti: dict = None) -> dict:
    """Arsivden TURETILEN saglik ozeti - dosyalardan her zaman yeniden
    uretilebilir (birlestirmede bozulmaz)."""
    kanonik = {(s.get("zaman"), s.get("tip")): s for s in kanonik_satirlar}
    gozlem = [s for s in kanonik_satirlar if s.get("tip") in GOZLEM_TIPLERI]

    # ---- ingest: kaynak x gecikme (METAR/SPECI ayri)
    ingest = {}
    kurtarilan = []
    for t in GOZLEM_TIPLERI:
        ingest[t] = {KAYNAK_CANLI: {"60dk_ve_alti": 0, "60dk_uzeri": 0},
                     KAYNAK_BACKFILL: {"60dk_ve_alti": 0, "60dk_uzeri": 0},
                     "bilinmiyor": 0}
    for s in gozlem:
        t, kay = s["tip"], s.get("kaynak") or ""
        al, z = _dt(s.get("alinma_zamani")), _dt(s.get("zaman"))
        if kay not in (KAYNAK_CANLI, KAYNAK_BACKFILL) or al is None or z is None:
            ingest[t]["bilinmiyor"] += 1
            continue
        gec = (al - z).total_seconds() / 60 > GEC_INGEST_DK
        ingest[t][kay]["60dk_uzeri" if gec else "60dk_ve_alti"] += 1
        if kay == KAYNAK_BACKFILL:
            kurtarilan.append(f"{s['zaman']} {t}")

    # ---- surumler
    status, aciklama, anahtar_surum = {}, {}, {}
    for s in surumler:
        st, ac = s.get("mgm_status") or "", s.get("mgm_status_aciklama") or ""
        status[st] = status.get(st, 0) + 1
        aciklama[ac] = aciklama.get(ac, 0) + 1
        anahtar_surum.setdefault((s.get("zaman"), s.get("tip")), []).append(s)
    cok = sorted(k for k, v in anahtar_surum.items() if len(v) > 1)
    farkli = _ayristirma_farkli(kanonik, surumler, coz) if coz is not None else None

    # ---- eksik slotlar
    eksik = eksik_slotlar(kanonik_satirlar, simdi, backfill_yaniti)
    yedi_gun = simdi - timedelta(days=7)
    disarida = [d for d in eksik if d["durum"] == "backfill_penceresi_disinda"]

    return {
        "uretim_zamani": _utc_iso(simdi),
        "kanonik": {
            "toplam": len(kanonik_satirlar),
            "METAR": sum(1 for s in gozlem if s["tip"] == "METAR"),
            "SPECI": sum(1 for s in gozlem if s["tip"] == "SPECI"),
            "ilk": gozlem[0]["zaman"] if gozlem else None,
            "son": gozlem[-1]["zaman"] if gozlem else None,
            "not": "Kanonik satır o anahtarı ilk yakalayan sürümdür; "
                   "meteorolojik olarak doğru/nihai sürüm iddiası taşımaz.",
        },
        "ingest": {
            "tablo": ingest,
            "backfill_kurtarilan": {t: ingest[t][KAYNAK_BACKFILL]["60dk_ve_alti"]
                                    + ingest[t][KAYNAK_BACKFILL]["60dk_uzeri"]
                                    for t in GOZLEM_TIPLERI},
            "60dk_uzeri_gec_ingest": {t: ingest[t][KAYNAK_CANLI]["60dk_uzeri"]
                                      + ingest[t][KAYNAK_BACKFILL]["60dk_uzeri"]
                                      for t in GOZLEM_TIPLERI},
            "backfill_kurtarilan_son": kurtarilan[-LISTE_SINIRI:],
        },
        "surum": {
            "toplam": len(surumler),
            "mgm_status": dict(sorted(status.items())),
            "mgm_status_aciklama": dict(sorted(aciklama.items())),
            "cok_surumlu_anahtar": len(cok),
            "cok_surumlu_anahtar_son": [
                {"anahtar": f"{z} {t}",
                 "surumler": [{"mgm_status": s.get("mgm_status"),
                               "alinma_zamani": s.get("alinma_zamani"),
                               "kaynak": s.get("kaynak")}
                              for s in anahtar_surum[(z, t)]]}
                for z, t in cok[-LISTE_SINIRI:]],
            "kanonik_ile_ayristirma_farkli": (
                None if farkli is None else
                {"sayi": len(farkli),
                 "son": [f"{z} {t}" for z, t in farkli[-LISTE_SINIRI:]]}),
        },
        "eksik_slot": {
            "bekleniyor": sum(1 for d in eksik if d["durum"] == "bekleniyor"),
            "backfill_penceresi_disinda": {
                "son_7_gun": sum(1 for d in disarida if _dt(d["slot"]) > yedi_gun),
                "toplam": len(disarida)},
            "son": eksik[-LISTE_SINIRI:],
            "en_uzun_bosluk": _en_uzun_bosluk(eksik),
        },
    }


def durum_oku(dosya: Path = DURUM_DOSYASI) -> dict:
    try:
        return json.loads(Path(dosya).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def durum_yaz(durum: dict, dosya: Path = DURUM_DOSYASI) -> None:
    Path(dosya).write_text(json.dumps(durum, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")


def _dosyalar(klasor: Path) -> dict:
    klasor = Path(klasor)
    return {"kanonik": klasor / VARSAYILAN_DOSYA.name,
            "surum": klasor / SURUM_DOSYASI.name,
            "durum": klasor / DURUM_DOSYASI.name}


def _hata(e: Exception, zaman: datetime) -> dict:
    return {"zaman": _utc_iso(zaman), "sinif": type(e).__name__, "mesaj": str(e)[:300]}


def _su_an() -> datetime:
    return datetime.now(timezone.utc)


# -------------------------------------------------------- bot kosusu ---
def kosu_isle(raporlar_h0: list, h0_alinma: datetime, coz, cek_h24,
              klasor: Path = KLASOR, zaman_fn=_su_an) -> dict:
    """Botun her kosusunda: once canli hours=0 raporlari, sonra AYRI bir
    hours=24 cekimi arsive islenir; saglik iki cekim icin AYRI tutulur.

    cek_h24: argumansiz, hours=24 rapor listesini donduren fonksiyon.
    Geri doldurma raporlari YALNIZCA arsive gider; cagiran (bot) onlari
    bildirim/state/sayfa akisina hic almaz. Hicbir hata disari sizmaz."""
    f = _dosyalar(klasor)
    onceki_durum = durum_oku(f["durum"])
    onceki = onceki_durum.get("cekim") or {}
    cekim = {KAYNAK_CANLI: dict(onceki.get(KAYNAK_CANLI) or {}),
             KAYNAK_BACKFILL: dict(onceki.get(KAYNAK_BACKFILL) or {})}

    c = cekim[KAYNAK_CANLI]
    c.update(son_deneme=_utc_iso(h0_alinma), son_basarili=_utc_iso(h0_alinma),
             ardisik_hata=0, son_yanit=yanit_ozeti(raporlar_h0))
    try:
        c["son_isleme"] = arsive_isle(raporlar_h0, coz, KAYNAK_CANLI, h0_alinma,
                                      f["kanonik"], f["surum"])
    except Exception as e:
        c["son_isleme"] = {"hata": _hata(e, zaman_fn())}
        print(f"[uyarı] gözlem arşivi (canlı) işlenemedi: {e}", file=sys.stderr)

    b = cekim[KAYNAK_BACKFILL]
    b["son_deneme"] = _utc_iso(zaman_fn())
    yanit = None
    try:
        raporlar_h24 = cek_h24()
    except Exception as e:
        b["ardisik_hata"] = int(b.get("ardisik_hata") or 0) + 1
        b["son_hata"] = _hata(e, zaman_fn())
        b["son_isleme"] = None
        print(f"[uyarı] gözlem arşivi geri doldurma çekimi başarısız: "
              f"{type(e).__name__}: {e}", file=sys.stderr)
    else:
        alinma = zaman_fn()
        b.update(son_basarili=_utc_iso(alinma), ardisik_hata=0,
                 son_yanit=dict(yanit_ozeti(raporlar_h24), veri_alani="data",
                                saat=BACKFILL_SAAT))
        try:
            isl = arsive_isle(raporlar_h24, coz, KAYNAK_BACKFILL, alinma,
                              f["kanonik"], f["surum"])
            # Durum gecisi: H24 oncesi kanonikte yok -> H24 sonrasi var.
            isl["backfill_kurtarilan"] = isl["eklenen_anahtarlar"]
            b["son_isleme"] = isl
            yanit = _backfill_yaniti(raporlar_h24)
            if isl["backfill_kurtarilan"]:
                print(f"  geri doldurma: {len(isl['backfill_kurtarilan'])} gözlem "
                      f"kurtarıldı ({', '.join(isl['backfill_kurtarilan'])})")
        except Exception as e:
            b["son_isleme"] = {"hata": _hata(e, zaman_fn())}
            print(f"[uyarı] gözlem arşivi (geri doldurma) işlenemedi: {e}",
                  file=sys.stderr)

    durum = {"cekim": cekim,
             "arsiv": durum_ozeti(oku(f["kanonik"]), surumleri_oku(f["surum"]),
                                  zaman_fn(), coz, yanit),
             # Celiskiler yalnizca birlestirmede tespit edilir; kosu onlari
             # oldugu gibi tasir (arsivden turetilemez).
             "catisma": onceki_durum.get("catisma") or catisma_bos()}
    durum_yaz(durum, f["durum"])
    return durum


def canli_hata_kaydet(hata: Exception, klasor: Path = KLASOR, zaman_fn=_su_an) -> None:
    """Canli hours=0 cekimi basarisizsa yalnizca canli saglik guncellenir
    (geri doldurma bu kosuda DENENMEZ; arsiv bolumu oldugu gibi kalir)."""
    f = _dosyalar(klasor)
    durum = durum_oku(f["durum"])
    cekim = durum.setdefault("cekim", {})
    c = cekim.setdefault(KAYNAK_CANLI, {})
    simdi = zaman_fn()
    c.update(son_deneme=_utc_iso(simdi), son_hata=_hata(hata, simdi),
             ardisik_hata=int(c.get("ardisik_hata") or 0) + 1)
    durum_yaz(durum, f["durum"])


def birlestir_bizim(bizim: Path, klasor: Path = KLASOR, zaman_fn=_su_an) -> dict:
    """Workflow push cakismasi: `klasor` uzaktaki (reset sonrasi) dosyalar,
    `bizim` bu kosunun kenara aldigi kopyalar. Kanonik ve surum katmanlari
    birlestirilir, arsiv durumu yeniden uretilir; `cekim` bolumu bu
    kosununki kalir; celiski sayaclari iki taraftan birlestirilip bu
    birlestirmede bulunanlar eklenir."""
    f, bz = _dosyalar(klasor), _dosyalar(bizim)
    simdi = zaman_fn()
    tespit = _utc_iso(simdi)
    uzak_durum, bizim_durum = durum_oku(f["durum"]), durum_oku(bz["durum"])
    yeni = _kanonik_dosya_birlestir(f["kanonik"], bz["kanonik"], f["kanonik"], tespit)
    if f["surum"].exists() or bz["surum"].exists():
        yeni += _surum_dosya_birlestir(f["surum"], bz["surum"], f["surum"], tespit)
    cekim = bizim_durum.get("cekim") or uzak_durum.get("cekim") or {}
    # coz yok: ayristirma karsilastirmasi burada hesaplanmaz (None);
    # sonraki bot kosusu tam ozeti yeniden uretir.
    durum = {"cekim": cekim,
             "arsiv": durum_ozeti(oku(f["kanonik"]), surumleri_oku(f["surum"]), simdi),
             "catisma": catisma_guncelle([uzak_durum.get("catisma"),
                                          bizim_durum.get("catisma")], yeni)}
    durum_yaz(durum, f["durum"])
    return durum


def _ozet(dosya: Path) -> str:
    satirlar = oku(dosya)
    if not satirlar:
        return f"{dosya.name}: boş"
    speci = sum(1 for s in satirlar if s.get("tip") == "SPECI")
    gorus_var = sum(1 for s in satirlar if s.get("gorus"))
    return (f"{dosya.name}: {len(satirlar)} gözlem "
            f"({satirlar[0]['zaman'][:16]} → {satirlar[-1]['zaman'][:16]}), "
            f"{speci} SPECI (%{100 * speci / len(satirlar):.1f}), "
            f"{gorus_var} görüşlü")


def main(argv=None) -> int:
    import argparse

    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--dosya", type=Path, default=VARSAYILAN_DOSYA)
    a.add_argument("--birlestir", nargs=2, type=Path, metavar=("A", "B"),
                   help="iki kanonik arşivi birleştirip --dosya'ya yazar")
    a.add_argument("--birlestir-bizim", type=Path, metavar="DIZIN",
                   help="workflow çakışması: DIZIN'deki kopyaları --dosya'nın "
                        "klasöründeki (uzak) katmanlarla birleştirir, durumu yeniler")
    s = a.parse_args(argv)
    if s.birlestir_bizim:
        birlestir_bizim(s.birlestir_bizim, s.dosya.parent)
        print(f"birleştirildi (kanonik + sürüm): {s.birlestir_bizim}")
    elif s.birlestir:
        n = birlestir(s.birlestir[0], s.birlestir[1], s.dosya)
        print(f"birleştirildi: {n} gözlem -> {s.dosya}")
    print(_ozet(s.dosya))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
