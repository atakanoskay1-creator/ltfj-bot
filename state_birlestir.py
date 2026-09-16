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
import sys
from pathlib import Path

GECMIS_LIMIT = 200
OLCUM_GECMIS_LIMIT = 300


def oku(yol: Path) -> dict:
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def yeni_olan(a: dict, b: dict, alan: str):
    """guncelleme damgasi daha yeni olanin alanini dondurur."""
    if not a.get(alan):
        return b.get(alan)
    if not b.get(alan):
        return a.get(alan)
    return (b if b.get("guncelleme", "") > a.get("guncelleme", "") else a).get(alan)


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

    return {
        "gonderilen": gonderilen[-GECMIS_LIMIT:],
        # Iki taraftan biri bile calismissa artik ilk calisma degiliz
        "ilk_calisma": bool(a.get("ilk_calisma", True)) and bool(b.get("ilk_calisma", True)),
        "son_metar": yeni_olan(a, b, "son_metar") or "",
        "son_uyari": yeni_olan(a, b, "son_uyari"),
        "son_renk": yeni_olan(a, b, "son_renk"),
        "durum_mesaj_id": yeni_olan(a, b, "durum_mesaj_id"),
        "son_veri_zamani": yeni_olan(a, b, "son_veri_zamani"),
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
