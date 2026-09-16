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
  her NOTAM kaydi en azindan: id, number, notam_type, status,
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
"""
from datetime import datetime, timezone

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
        "category_kodu": kategori.get("code"),
        "category_etiketi": kategori.get("label"),
        "tags": [t.get("name") for t in etiketler if isinstance(t, dict) and t.get("name")],
        "affected_elements": [
            {"ref": e.get("ref"), "type": e.get("type")}
            for e in (ham.get("affected_elements") or [])
            if isinstance(e, dict)
        ],
        "text": ham.get("text") or "",
        "reading_short": ilk_okuma.get("short"),
        "reading_long": ilk_okuma.get("long"),
        "source": KAYNAK_ETIKETI,
    }


def aktif_notamlari_getir(location: str = LOCATION) -> list[dict]:
    """NOTAC'tan verilen lokasyon icin TUM aktif NOTAM'lari (sayfalama
    varsa DRF'nin verdigi "next" URL'sini takip ederek) ceker, internal
    modele cevirir. NOTAC'in ham HTTP hatalarini (bkz. ltfj_notam_client)
    tek bir NotamServisHatasi altinda toplar - cagiran taraf tek exception
    sinifi yakalamasi yeterli olsun diye."""
    try:
        yanit = client.notam_getir(location)
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
        birlesmis = dict(kayit) if guncellendi else dict(onceki)
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
