#!/usr/bin/env python3
"""
Iki ltfj_state.json dosyasini birlestirir.

Iki calistirma ayni anda state yazarsa git bunu cakisma sayar ve rebase edemez -
cunku dosyanin ortak atasi yoktur. Halbuki dogru cozum belli: gonderilmis rapor
listelerinin BIRLESIMI alinir. Bir rapor iki tarafta da "gonderildi" ise zaten
gonderilmistir; birinde varsa yine gonderilmistir.

Kullanim:
  python state_birlestir.py hedef.json digeri.json
     -> ikisini birlestirip hedef.json'a yazar
"""

import json
import re
import sys
from pathlib import Path

GECMIS_LIMIT = 200
OLCUM_GECMIS_LIMIT = 300

# METAR/SPECI govdesindeki DDHHMMZ gozlem zaman grubu (ornek: "161250Z").
_RE_GOZLEM_ZAMANI = re.compile(r"\b(\d{2})(\d{2})(\d{2})Z\b")


def oku(yol: Path) -> dict:
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def yeni_olan(a: dict, b: dict, alan: str):
    """guncelleme damgasi (state'in YAZILMA zamani) daha yeni olanin
    alanini dondurur. Sadece zaman anlami tasimayan alanlar (ornegin
    durum_mesaj_id - Telegram mesaj kimligi) icin uygundur; bir METAR
    GOZLEMinin ne zaman olustugunu YAZMA zamanindan cikarsamayiz (bkz.
    _son_metar_ve_renk_sec, _en_yeni_zaman_damgasi)."""
    if not a.get(alan):
        return b.get(alan)
    if not b.get(alan):
        return a.get(alan)
    return (b if b.get("guncelleme", "") > a.get("guncelleme", "") else a).get(alan)


def _gozlem_zamani(metar_metni: str):
    """METAR/SPECI metnindeki DDHHMMZ gozlem zamanini (gun,saat,dakika)
    ucluyle dondurur - metnin kendisinden okundugu icin state'in NE ZAMAN
    YAZILDIGINDAN bagimsizdir. Ay/yil bilgisi METAR govdesinde yok, bu
    yuzden ay siniri asan (ornegin ayin son gunu <-> yeni ayin ilk gunu)
    karsilastirmalar YANLIS SIRALANABILIR - bu, iki calistirmanin ayni
    ~saatler icinde yarisan cikislarini birlestirme senaryosu icin kabul
    edilebilir bir sinirlama (state_birlestir'in TEK kullanim amaci bu)."""
    if not metar_metni:
        return None
    m = _RE_GOZLEM_ZAMANI.search(metar_metni)
    return tuple(int(x) for x in m.groups()) if m else None


def _son_metar_ve_renk_sec(a: dict, b: dict) -> tuple[str, str | None]:
    """son_metar VE son_renk'i BIRLIKTE, ayni taraftan secer - son_renk
    son_metar'dan HESAPLANAN bir deger oldugundan ikisi ayri ayri
    secilirse (ayri guncelleme damgalarina gore) tutarsiz bir cift ortaya
    cikabilir (ornegin A'nin METAR'i ile B'nin rengi).

    Once METAR govdesindeki GERCEK gozlem zamanina bakilir (state'in
    yazilma zamanina degil) - iki calistirma yarisip biri digerinden
    GEC YAZILSA bile ESKI bir gozlemi tasiyorsa (ornegin agdaki gecikme
    yuzunden), o taraf kazanmamali. Gozlem zamanindan karar cikmazsa
    (parse edilemedi ya da esit) eski davranisa (yazma zamani) dusulur."""
    a_metar, b_metar = a.get("son_metar") or "", b.get("son_metar") or ""
    if not a_metar:
        return b.get("son_metar") or "", b.get("son_renk")
    if not b_metar:
        return a.get("son_metar") or "", a.get("son_renk")

    za, zb = _gozlem_zamani(a_metar), _gozlem_zamani(b_metar)
    if za is not None and zb is not None and za != zb:
        b_kazanir = zb > za
    else:
        b_kazanir = b.get("guncelleme", "") > a.get("guncelleme", "")

    secilen = b if b_kazanir else a
    return secilen.get("son_metar") or "", secilen.get("son_renk")


def _en_yeni_zaman_damgasi(a: dict, b: dict, alan: str) -> str | None:
    """alan'in kendisi ISO 8601 bir zaman damgasiysa (son_veri_zamani,
    son_uyari gibi - ikisi de MEVCUT KODDA ZATEN dogrudan bir zaman
    degeri, state'in ne zaman yazildigindan bagimsiz), guncelleme'ye
    BAKMADAN dogrudan degerlerin kendisini karsilastirir. ISO 8601
    string'ler ayni saat dilimi bicimiyle yazildiginda lexicographic
    karsilastirma dogru sonuc verir (bkz. datetime.isoformat kullanimi
    ltfj_bot.py::state_yaz/sessizlik_kontrol icinde)."""
    degerler = [v for v in (a.get(alan), b.get(alan)) if v]
    return max(degerler) if degerler else None


def birlestir(a: dict, b: dict) -> dict:
    # Gonderilmis rapor kimlikleri: sirayi bozmadan birlesim
    gonderilen = list(a.get("gonderilen") or [])
    gonderilen += [k for k in (b.get("gonderilen") or []) if k not in gonderilen]

    # Olcum gecmisi (trend grafikleri): zaman damgasina gore birlesim
    gecmis = {g["zaman"]: g for g in (a.get("olcum_gecmisi") or []) if g.get("zaman")}
    for g in (b.get("olcum_gecmisi") or []):
        if g.get("zaman"):
            gecmis.setdefault(g["zaman"], g)
    olcum_gecmisi = sorted(gecmis.values(), key=lambda g: g["zaman"])[-OLCUM_GECMIS_LIMIT:]

    # Claude yorum onbellegi: ham metin anahtarina gore birlesim
    onbellek = dict(a.get("yorum_onbellegi") or {})
    onbellek.update(b.get("yorum_onbellegi") or {})

    son_metar, son_renk = _son_metar_ve_renk_sec(a, b)

    return {
        "gonderilen": gonderilen[-GECMIS_LIMIT:],
        # Iki taraftan biri bile calismissa artik ilk calisma degiliz
        "ilk_calisma": bool(a.get("ilk_calisma", True)) and bool(b.get("ilk_calisma", True)),
        "son_metar": son_metar,
        "son_uyari": _en_yeni_zaman_damgasi(a, b, "son_uyari"),
        "son_renk": son_renk,
        # durum_mesaj_id zaman anlami tasimaz (Telegram mesaj kimligi) -
        # hangi calistirmanin DAHA SON yazdigi (guncelleme) esas alinir.
        "durum_mesaj_id": yeni_olan(a, b, "durum_mesaj_id"),
        "son_veri_zamani": _en_yeni_zaman_damgasi(a, b, "son_veri_zamani"),
        "olcum_gecmisi": olcum_gecmisi,
        "yorum_onbellegi": onbellek,
        "guncelleme": max(a.get("guncelleme", ""), b.get("guncelleme", "")),
    }


def main():
    if len(sys.argv) != 3:
        sys.exit("Kullanim: python state_birlestir.py hedef.json digeri.json")

    hedef, digeri = Path(sys.argv[1]), Path(sys.argv[2])
    sonuc = birlestir(oku(hedef), oku(digeri))
    hedef.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"Birlestirildi: {len(sonuc['gonderilen'])} kayit -> {hedef}")


if __name__ == "__main__":
    main()
