#!/usr/bin/env python3
"""
NOTAC NOTAM verisini internal modelimize cevirir, LTFJ aktif NOTAM'larini
sayfalama takip ederek ceker, yerel gecmisi (state) guncelleyip arama
saglar.

VERI TABANLI TASNIF (modul geneli):
  BILGI AMACLI - bu modulun urettigi HER SEY NOTAC kaynakli bir BILGI
  katmanidir, METAR/TAF/RVR/pist analizinin (ltfj_pist.py) GOZLEMLENEN/
  HESAPLANAN katmanlarindan TAMAMEN AYRIDIR. Bu modul hicbir operasyonel
  karar (pist secimi, "kullanilmali/kullanilamaz", gecikme tahmini) URETMEZ
  - sadece NOTAC'in kendi verdigi bilgiyi (raw metin + NOTAC'in kendi
  kategori/etiket/plain-English readings alanlari) aynen tasir.

DOGRULANMIS SEMA (kullanicinin 2026-09-16'da GitHub Actions'tan attigi
gercek "GET /notam/?location=LTFJ" istegine gore, bkz. ltfj_notam_client.py):
  her NOTAM kaydi en azindan: id, number, notam_type, q_code, status,
  effective_start, effective_end, notam_issued, notam_updated,
  record_updated_at, text, category {code,label,description},
  tags [{name,label,description}], affected_elements [{ref,type}],
  readings [{short,long,generated_at}], location {code,icao_code,...},
  location_code alanlarini tasiyor.

  Kategori/etiket NOTAC'in KENDI siniflandirmasidir - kendi regex'imizle
  yeniden tahmin ETMIYORUZ (bkz. category_kodu/category_etiketi/tags).
  "readings" NOTAC'in kendi otomatik plain-English yorumudur (raw metnin
  YERINE degil, YANINDA tutulur) - NOTAC'in kendi sitesindeki uyarisina
  gore "generated automatically and may contain errors".

  NOTAMR/NOTAMC SINIRI: notam_type ("N"/"R"/"C") yapisal bir alandir ve
  her kayitta vardir. Ama YERINE GECILEN / IPTAL EDILEN NOTAM'IN
  NUMARASI NOTAC yanitinda AYRI BIR ALAN OLARAK YOK; "text" yalnizca
  E) govdesini tasiyor (16 gercek LTFJ kaydinda "NOTAMR B1234/26"
  kalibi hic gecmedi). Numara ancak metinde GERCEKTEN yaziyorsa
  cikariliyor (bkz. ilgili_notam_referansi) - eslestirme TAHMIN
  EDILMIYOR, cunku yanlis NOTAM'i isaret etmek bilgi degil zarar olur.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import ltfj_notam_client as client

LOCATION = "LTFJ"
MAKS_SAYFA = 5   # guvenlik siniri - runaway sayfalama donguyu onler

KAYNAK_ETIKETI = "NOTAC"
BILGI_UYARISI = (
    "Bilgi amaçlıdır. Operasyon öncesi güncel resmî NOTAM/PIB kontrol edilmelidir."
)


class NotamServisHatasi(Exception):
    """aktif_notamlari_getir() gibi ust seviye fonksiyonlarin sardigi hata -
    cagiran taraf (ltfj_bot.py) sadece BU tek sinifi yakalamasi yeterli."""


# --------------------------------------------------------------- Q kodu
# ICAO Q kodunun 2-3. harfleri NOTAM'in KONUSUNU verir. Asagidaki liste
# bir ANLAM TABLOSU DEGIL, bir GORUNURLUK listesi: LVO panelinde hangi
# konularin listeleneceğini secer. Yaninda yazan karsiliklar insan
# gozden gecirsin diye duruyor, urunde HICBIR YERDE gosterilmiyor -
# kartta Q kodu ham haliyle yaziyor.
#
# Yanlis bir giris burada "panelde gorunur/gorunmez" demek; operasyonel
# bir iddia uretmiyor. Yine de eksik kalirsa NOTAM'in sessizce
# kaybolmamasi icin anahtar kelime suzgeci YEDEKTE tutuluyor (bkz.
# ltfj_sayfa.notamLvoIliskiliMi) - iki yol BIRLESIM, biri otekini
# devre disi birakmiyor.
LVO_Q_KONULARI = (
    "MR",   # pist
    "MT",   # esik (threshold)
    "MS",   # stopway
    "MX",   # taksi yolu
    "MW",   # serit/omuz
    "MD",   # ilan edilmis mesafeler
    "IC",   # ILS
    "IL",   # lokalizer
    "IG",   # glide path
    "ID",   # ILS'e ait DME
    "IM",   # middle marker
    "IO",   # outer marker
    "LA",   # yaklasma isiklandirma sistemi
    "LC",   # pist merkez hatti isiklari
    "LE",   # pist kenar isiklari
    "LH",   # yuksek yogunluklu pist isiklari
    "LP",   # PAPI
    "LR",   # inis sahasi isiklandirmasi
    "LT",   # esik isiklari
    "LZ",   # dokunma bolgesi isiklari
)


def q_konusu(kayit: dict) -> str | None:
    """Q kodunun KONU harfleri (2-3.), ornegin "QMRLC" -> "MR".

    Bicim beklenmedikse None doner - yanlis bir dilimden konu
    UYDURMAKTANSA "bilmiyorum" demek dogru; cagiran taraf o zaman
    anahtar kelime yedegine duser."""
    kod = (kayit.get("q_code") or "").strip().upper()
    if len(kod) != 5 or not kod.startswith("Q") or not kod.isalpha():
        return None
    return kod[1:3]


def lvo_ile_ilgili_mi(kayit: dict) -> bool | None:
    """Q koduna gore LVO panelinde listelenmeli mi?

    None = Q kodu yok/okunamadi, yani BU YOLLA karar verilemiyor -
    cagiran taraf anahtar kelime yedegini kullanmali. False ile None'i
    ayirmak onemli: False "baktim, ilgili degil", None "bakamadim".
    """
    konu = q_konusu(kayit)
    if konu is None:
        return None
    return konu in LVO_Q_KONULARI


# NOTAM basligindaki "NOTAMR B1234/26" / "NOTAMC B1234/26" referansi.
#
# DUZELTME (kullanici, NOTAC arayuzunden ekran goruntusuyle): daha once
# "bu numara NOTAC'ta yok" sonucuna varmistim - YANLISTI. Dogrulayabildigim
# tek sey BIZIM SAKLADIGIMIZ "text" alaniydi ve o yalnizca E) govdesini
# tasiyor. NOTAC'in kendi arayuzu ise TAM orijinal metni gosteriyor:
#
#     B3455/26 NOTAMR B2849/26
#      Q) LTBB/QMRXX/IV/BO /A /000/999/4054N02919E005
#      A) LTFJ B) 2608280711 C) 2610021600
#      E) PRESENCE SURFACE IRREGULARITIES ON RWY 06L/24R ...
#
# Yani numara yanitta BIR YERDE var; hangi alanda oldugunu daha
# olcmedik (bkz. notam_kesif.py). Bu yuzden alan adi SABITLENMIYOR:
# kaydin tum metin alanlarinda ariyoruz. Dogru alan geldigi gun kod
# kendiliginden calisir, biz de alan adini UYDURMAMIS oluruz.
ILGILI_NOTAM_KALIBI = re.compile(
    r"\bNOTAM(?P<tip>[RC])\s+(?P<numara>[A-Z]\d{4}/\d{2})\b", re.IGNORECASE)


def ilgili_notam_referansi(kayit: dict) -> dict | None:
    """Bu NOTAM'in yerine gectigi (R) ya da iptal ettigi (C) NOTAM'in
    numarasi - kaydin metin alanlarindan HERHANGI BIRINDE geciyorsa.
    Gecmiyorsa None; TAHMIN EDILMEZ.

    notam_type ("R"/"C") ile karistirilmamali: tip NOTAC'in yapisal
    alani ve her kayitta var; referans numarasi ayri bir bilgidir.

    Kalip, NOTAM'in KENDI numarasini degil SONRAKI numarayi yakalar:
    "B3455/26 NOTAMR B2849/26" -> B2849/26."""
    for deger in kayit.values():
        if not isinstance(deger, str):
            continue
        m = ILGILI_NOTAM_KALIBI.search(deger)
        if m:
            return {"tip": m.group("tip").upper(), "numara": m.group("numara").upper()}
    return None


def _notam_modeline_cevir(ham: dict) -> dict:
    """Bir NOTAC NOTAM kaydini internal modelimize cevirir. Alan adi
    eksikse/None ise KESIN degerler UYDURMUYORUZ - .get() ile guvenli
    varsayilanlara (None / bos liste) dusuyoruz. Raw metin HER ZAMAN
    korunur."""
    kategori = ham.get("category") or {}
    location = ham.get("location") or {}
    readings = ham.get("readings") or []
    ilk_okuma = readings[0] if readings and isinstance(readings[0], dict) else {}
    etiketler = ham.get("tags") or []

    return {
        "id": ham.get("id"),
        "number": ham.get("number"),
        "notam_type": ham.get("notam_type"),
        "location": ham.get("location_code") or location.get("code"),
        "status": ham.get("status"),
        "effective_start": ham.get("effective_start"),
        "effective_end": ham.get("effective_end"),
        "notam_issued": ham.get("notam_issued"),
        "notam_updated": ham.get("notam_updated"),
        "record_updated_at": ham.get("record_updated_at"),
        # Q KODU HAM HALIYLE TASINIYOR, cozumlenmiyor. "QMRLC" gibi bes
        # harfli ICAO kodu; 2-3. harfler KONU (MR = pist), 4-5. harfler
        # DURUM. Sayfa bunu oldugu gibi gosteriyor - kendi Turkce
        # karsiligimizi UYDURMUYORUZ (yanlis bir cevirinin operasyonel
        # maliyeti var; NOTAC'in kendi category/tags alanlari zaten
        # insan diliyle etiket veriyor).
        "q_code": ham.get("q_code"),
        "category_kodu": kategori.get("code"),
        "category_etiketi": kategori.get("label"),
        "tags": [t.get("name") for t in etiketler if isinstance(t, dict) and t.get("name")],
        "affected_elements": [
            {"ref": e.get("ref"), "type": e.get("type")}
            for e in (ham.get("affected_elements") or [])
            if isinstance(e, dict)
        ],
        "text": ham.get("text") or "",
        # Referans HAM kayittan cikariliyor: tam orijinal metin hangi
        # alanda gelirse gelsin yakalansin diye (bkz.
        # ilgili_notam_referansi). Sayfa kendi regex'ini calistirmiyor -
        # ayni kural iki dilde iki kez yazilmis olurdu.
        "ilgili_notam": ilgili_notam_referansi(ham),
        "reading_short": ilk_okuma.get("short"),
        "reading_long": ilk_okuma.get("long"),
        "source": KAYNAK_ETIKETI,
    }


# NOTAC'in "status" suzgeci - OLCULDU (OPTIONS /notam/ yanitinin kendi
# tarifi, bkz. notam_kesif.py ciktisi):
#
#     ?status=active|upcoming|expired|any   (varsayilan: active)
#
# "all" DEGIL - onu denemek HTTP hatasi verdi. Varsayilan "active"
# oldugu icin bot bugune kadar yalnizca yururluktekileri goruyordu;
# yaklasanlar (LTFJ'de olcum aninda 6 kayit) hic gelmiyordu.
DURUM_AKTIF = "active"
DURUM_YAKLASAN = "upcoming"


def notamlari_getir(location: str = LOCATION, durum: str | None = None) -> list[dict]:
    """NOTAC'tan verilen lokasyon (ve istege bagli yururluk durumu) icin
    TUM NOTAM'lari (sayfalama varsa DRF'nin verdigi "next" URL'sini
    takip ederek) ceker, internal modele cevirir.

    durum=None: NOTAC'in varsayilani, yani yalnizca yururluktekiler."""
    try:
        yanit = client.notam_getir(
            location, ek_parametreler={"status": durum} if durum else None)
        kayitlar = list(yanit.get("results") or [])

        sayfa = 1
        sonraki = yanit.get("next")
        while sonraki and sayfa < MAKS_SAYFA:
            yanit = client.sayfa_getir(sonraki)
            kayitlar += list(yanit.get("results") or [])
            sonraki = yanit.get("next")
            sayfa += 1
    except client.NotamHatasi as e:
        raise NotamServisHatasi(str(e)) from e

    modele_cevrilmis = [_notam_modeline_cevir(k) for k in kayitlar if isinstance(k, dict)]
    # API seviyesinde zaten location=LTFJ ile filtrelendi (bkz. client) -
    # bu sadece bir guvenlik agi, ana filtreleme mekanizmasi degil.
    return [n for n in modele_cevrilmis if n["location"] == location]


def aktif_notamlari_getir(location: str = LOCATION) -> list[dict]:
    """Yururlukteki NOTAM'lar. Geriye donuk uyumluluk icin duruyor -
    mevcut cagiranlar (ve testleri) aynen calismaya devam etsin diye."""
    return notamlari_getir(location)


def yururlukteki_ve_yaklasan_notamlar(location: str = LOCATION) -> list[dict]:
    """Yururluktekiler + henuz baslamamislar, TEK listede.

    IKI AYRI SORGU: NOTAC'in status suzgeci tekil deger aliyor ve
    varsayilani "active". "any" da var ama onu kullanmiyoruz - suresi
    DOLMUS NOTAM'lari da getirirdi ve yerel gecmisimizi NOTAC'in
    arsiviyle karistirirdi (bkz. modul aciklamasi: "gecmis" alani
    SADECE bu botun gordugu kayitlardir).

    Yaklasan sorgusu BASARISIZ OLURSA yururluktekiler yine donuyor -
    yeni ve ikincil bir bilgi yuzunden ana akisi kaybetmeyiz."""
    yururlukte = notamlari_getir(location, DURUM_AKTIF)
    try:
        yaklasan = notamlari_getir(location, DURUM_YAKLASAN)
    except NotamServisHatasi as e:
        print(f"[uyarı] yaklaşan NOTAM sorgusu başarısız: {e}", file=sys.stderr)
        yaklasan = []
    # Ayni NOTAM iki sorgudan da gelebilir; id'ye gore tekillestiriyoruz.
    gorulen = {n.get("id") for n in yururlukte}
    return yururlukte + [n for n in yaklasan if n.get("id") not in gorulen]


# ------------------------------------------------------------- arama/filtre
def _tarih_ayristir(deger: str | None) -> datetime | None:
    if not deger:
        return None
    try:
        return datetime.fromisoformat(deger.replace("Z", "+00:00"))
    except ValueError:
        return None


def notam_ara(
    kayitlar: list[dict],
    anahtar_kelime: str | None = None,
    tarih_baslangic: str | None = None,
    tarih_bitis: str | None = None,
    durum: str | None = None,
) -> list[dict]:
    """Verilen NOTAM kayit listesini (internal model, aktif liste ya da
    yerel gecmis farketmez) basit kriterlerle filtreler.

    anahtar_kelime: NOTAM numarasinda, raw metinde, etkilenen pist/taksi
      yolu referansinda (ör. '24R') ya da tag adinda GECEN (kucuk/buyuk
      harf duyarsiz) alt dizeyi arar. Ozel bir "pist" alani AYRI
      TUTULMUYOR - kullanici '24R' ya da 'RWY 24R' yazdiginda hem
      affected_elements hem raw metin uzerinden es zamanli eslesebilsin
      diye tek bir genel anahtar kelime alanı kullaniliyor.
    tarih_baslangic/tarih_bitis: ISO 8601 tarih/zaman - NOTAM'in
      effective_start/effective_end araligi bu pencereyle KESISIYORSA
      sonuca dahil edilir (NOTAM'in TAMAMEN bu aralikta olmasi sart
      degil - bir kisim gunu bile kesisen NOTAM'lar goruntulenir).
    durum: NOTAC'in kendi status degerine (ornegin 'active') tam eslesme.
    """
    sonuc = []
    baslangic_dt = _tarih_ayristir(tarih_baslangic)
    bitis_dt = _tarih_ayristir(tarih_bitis)

    for n in kayitlar:
        if durum is not None and n.get("status") != durum:
            continue

        if anahtar_kelime:
            ak = anahtar_kelime.strip().lower()
            alanlar = [
                n.get("number") or "",
                n.get("text") or "",
                n.get("reading_short") or "",
                n.get("reading_long") or "",
                # Q kodu da aranabilir: "QMRLC" ya da "QMR" yazarak
                # pistle ilgili NOTAM'lari suzebilmek icin.
                n.get("q_code") or "",
                " ".join(n.get("tags") or []),
                " ".join(e.get("ref") or "" for e in n.get("affected_elements") or []),
            ]
            if not any(ak in alan.lower() for alan in alanlar):
                continue

        if baslangic_dt or bitis_dt:
            n_baslangic = _tarih_ayristir(n.get("effective_start"))
            n_bitis = _tarih_ayristir(n.get("effective_end"))
            # Tarihi ayristirilamayan (None) bir NOTAM tarih filtresi
            # uygulanirken KESIN olarak elenmiyor - kullaniciya sessizce
            # kayip veri gostermek yerine sonuca dahil ediyoruz; boylece
            # eksik/bozuk tarih verisi "bu aralikta yok" gibi yanlis bir
            # kesinlik vermez.
            if n_baslangic and bitis_dt and n_baslangic > bitis_dt:
                continue
            if n_bitis and baslangic_dt and n_bitis < baslangic_dt:
                continue

        sonuc.append(n)

    return sonuc


# --------------------------------------------------------------- gecmis
def gecmisi_guncelle(eski_gecmis: dict, yeni_kayitlar: list[dict], simdi: str | None = None) -> dict:
    """Yerel NOTAM gecmisini (id -> kayit sozlugu) yeni cekilen aktif
    listeyle gunceller. Donen sozlukteki her kayit ayrica su alanlari
    tasir:
      first_seen   - botun bu NOTAM'i ILK gordugu an (ISO)
      last_seen    - botun bu NOTAM'i EN SON gordugu an (ISO) - sadece
                     NOTAM aktif listede goruldugunde ilerler
      last_active  - NOTAM'in status'unun 'active' oldugu bilinen SON an
                     (ISO) - aktif listeden dustugunde bu DEGISMEZ, boylece
                     "en son ne zaman aktifti" bilgisi kaybolmaz

    Aynı NOTAM (id'ye gore) her calistirmada YENIDEN olusturulmuyor -
    record_updated_at degismisse mevcut kaydin UZERINE yazilir (guncelleme
    sayilir), degismemisse dokunulmaz. Aktif listede artik gorunmeyen bir
    NOTAM SILINMIYOR - yerel gecmiste kalir, status'u NOTAC'ten son
    goruldugu haliyle korunur (NOTAC "withdrawn" gibi bir status
    yayinlarsa bir sonraki aktif+arama sorgusunda gorulup guncellenebilir;
    aktif listeden sessizce dusmesi TEK BASINA "iptal edildi" anlamina
    gelmez, sadece "artik aktif degil" anlamina gelir)."""
    simdi = simdi or datetime.now(timezone.utc).isoformat(timespec="seconds")
    gecmis = {k: dict(v) for k, v in (eski_gecmis or {}).items()}
    gorulen_idler = set()

    for kayit in yeni_kayitlar:
        nid = kayit.get("id")
        if not nid:
            continue
        gorulen_idler.add(nid)
        onceki = gecmis.get(nid)

        if onceki is None:
            yeni = dict(kayit)
            yeni["first_seen"] = simdi
            yeni["last_seen"] = simdi
            yeni["last_active"] = simdi if kayit.get("status") == "active" else None
            gecmis[nid] = yeni
            continue

        guncellendi = onceki.get("record_updated_at") != kayit.get("record_updated_at")
        # MODELE YENI ALAN EKLENDIGINDE geriye donuk dolsun. Eskiden
        # yalnizca record_updated_at'e bakiliyordu: NOTAC kaydi
        # degistirmedigi surece saklanan kayit oldugu gibi korunuyordu,
        # yani q_code gibi SONRADAN eklenen bir alan mevcut kayitlara
        # HIC gelmezdi (16 kaydin hepsi Q kodsuz kalirdi ve Q koduna
        # dayali suzgec onlari hic gormezdi).
        eksik_alan = set(kayit) - set(onceki)
        birlesmis = dict(kayit) if guncellendi else {**onceki, **{k: kayit[k] for k in eksik_alan}}
        birlesmis["first_seen"] = onceki.get("first_seen", simdi)
        birlesmis["last_seen"] = simdi
        if kayit.get("status") == "active":
            birlesmis["last_active"] = simdi
        else:
            birlesmis["last_active"] = onceki.get("last_active")
        gecmis[nid] = birlesmis

    # Aktif listede artik gorunmeyenler: sadece last_seen'i ILERLETMIYORUZ
    # (bu NOTAM'in "hala su an gorunuyor" olmadigini dogal olarak yansitir),
    # kaydi SILMIYORUZ.
    return gecmis


# ----------------------------------------------------------------- web veri
def notam_veri_yaz(state: dict, hedef: Path, location: str = LOCATION):
    """MOD 5 (web arayuzu) icin index.html'in fetch() ile okudugu ayri bir
    JSON dosyasi uretir - panel_veri.json'un ltfj_panel.py::panel_verisi_yaz
    ile ayni deseni (Python hesaplar/yazar, sayfa istemci tarafinda okur).

    "aktif" listesi, yerel gecmisteki last_seen'i EN SON senkronla (state's
    notam_son_senkron) TAM ESLESEN ve status'u 'active' olan kayitlardan
    olusur - yani "NOTAC'in bir onceki sorguda gercekten dondurdugu" liste.
    Bu, botun GORDUGU yerel gecmis ile NOTAC'in kendi arsivini KARISTIRMAZ
    (bkz. modul docstring'i ve kullanicinin MOD3 ayrimi talebi): "gecmis"
    alani SADECE bu botun sync'lerde bugune kadar gordugu kayitlardir,
    NOTAC'in tam tarihsel arsivi degildir - bu netlik web tarafinda da
    ayrica metinle belirtilir (bkz. ltfj_sayfa.py)."""
    son_senkron = state.get("notam_son_senkron")
    gecmis = state.get("notam_gecmisi") or {}

    tum_kayitlar = sorted(
        gecmis.values(),
        key=lambda k: k.get("last_seen") or "",
        reverse=True,
    )
    aktif = [
        k for k in tum_kayitlar
        if son_senkron and k.get("last_seen") == son_senkron and k.get("status") == "active"
    ]
    # YAKLASAN: son senkronda gorulmus ama yururluk BASLANGICI henuz
    # gelmemis kayitlar. Bunlari "aktif" listesine koymak, olmayan bir
    # kisitlamayi varmis gibi gostermek olurdu; hic gostermemek ise
    # "yarin pist kapaniyor" bilgisini kaybettirirdi - ayri liste.
    #
    # NOTAC'in VARSAYILAN sorgusu yalnizca yururluktekileri donduruyor;
    # yaklasanlar icin ?status=upcoming gerekiyor (OLCULDU: LTFJ'de o
    # sorgu 6 kayit dondurdu, hepsi gelecek tarihli). Bot artik iki
    # sorguyu da atiyor (bkz. yururlukteki_ve_yaklasan_notamlar).
    #
    # STATUS'A BAKMIYORUZ, BILEREK. Yaklasan kayitlarin "status" alaninda
    # hangi degeri tasidigini HENUZ OLCMEDIK ("active" mi, "upcoming" mi).
    # `status == "active"` sarti koysaydik, deger "upcoming" ise bu liste
    # SESSIZCE BOS kalirdi - yani ozellik calismiyor gibi gorunurdu ama
    # hata da vermezdi.
    #
    # Sarta gerek de yok: bu listeye yalnizca SON SENKRONDA GORULEN
    # kayitlar giriyor ve biz yalnizca "active" + "upcoming" sorgusu
    # atiyoruz (bkz. yururlukteki_ve_yaklasan_notamlar). Suresi dolmus
    # ya da iptal edilmis bir kayit o kumeye zaten girmiyor.
    simdi_iso = datetime.now(timezone.utc)
    yaklasan = []
    for k in tum_kayitlar:
        if not son_senkron or k.get("last_seen") != son_senkron:
            continue
        bas = _tarih_ayristir(k.get("effective_start"))
        if bas and bas > simdi_iso:
            yaklasan.append(k)
    yaklasan.sort(key=lambda k: k.get("effective_start") or "")

    veri = {
        "istasyon": location,
        "kaynak": KAYNAK_ETIKETI,
        "bilgi_uyarisi": BILGI_UYARISI,
        "uretildi": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "son_senkron": son_senkron,
        "aktif": aktif,
        "yaklasan": yaklasan,
        "gecmis": tum_kayitlar,
    }

    hedef.write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")
