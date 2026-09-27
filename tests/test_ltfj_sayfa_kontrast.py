"""WCAG AA metin kontrasti - TOKEN duzeyinde, iki tema, her yuzey.

Tarayicida tum sekmeler iki temada tarandiginda 17 ihlal cikti. Hepsi
iki kokten geliyordu:
  1) --soluk/--sessiz tonlari tonlu yuzeylerde (panel, etkilesim,
     kod-bg) esigin altindaydi; --sessiz acik temada 2.28:1'di,
  2) metin tasiyan kurallar ustune opacity ekleyerek token'in AA
     garantisini bozuyordu (cip sayaci, birim, pusula harfi, pist
     seridi uzerindeki numaralar).
Bu testler ikisini de kilitliyor: token'lar her yuzeyde >= 4.5, ve
metin tasiyan kurallarda opaklik yok.
"""
import re
from pathlib import Path

import pytest

import ltfj_sayfa

CSS = (Path(ltfj_sayfa.VARLIK_KLASORU) / "stil.css").read_text(encoding="utf-8")
YUZEYLER = ("--bg", "--panel", "--kart", "--etkilesim", "--kod-bg")
MUREKKEPLER = ("--metin", "--soluk", "--sessiz", "--baglanti")


# Koyu tema IKI yerde tanimli: sistem tercihi (media) ve elle secim
# (data-theme). Ikisi ayri yazildigi icin ikisi de ayri olculuyor.
TEMALAR = {
    "acik": ":root {",
    "koyu-sistem": ':root:not([data-theme="light"]) {',
    "koyu-elle": ':root[data-theme="dark"] {',
}


def _blok(tema):
    return CSS.split(TEMALAR[tema])[1].split("}")[0]


def _token(ad, tema):
    m = re.search(rf"{re.escape(ad)}:(#[0-9a-fA-F]{{6}})", _blok(tema))
    if m is None and tema != "acik":     # koyu blokta yoksa acik temadan miras
        return _token(ad, "acik")
    assert m, ad
    return m.group(1)


def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _L(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _k(a, b):
    x, y = _L(a), _L(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


@pytest.mark.parametrize("tema", list(TEMALAR))
@pytest.mark.parametrize("murekkep", MUREKKEPLER)
def test_metin_tonu_HER_YUZEYDE_AA(tema, murekkep):
    renk = _token(murekkep, tema)
    for yuzey in YUZEYLER:
        z = _token(yuzey, tema)
        assert _k(renk, z) >= 4.5, f"{murekkep} {renk} / {yuzey} {z}: {_k(renk, z):.2f}"


@pytest.mark.parametrize("tema", list(TEMALAR))
def test_murekkep_HIYERARSISI_korunuyor(tema):
    """Uc katman ayri kalmali - AA icin hepsini ayni tona cekmek
    hiyerarsiyi yok ederdi."""
    zemin = _token("--kart", tema)
    metin, soluk, sessiz = (_k(_token(t, tema), zemin) for t in ("--metin", "--soluk", "--sessiz"))
    assert metin > soluk > sessiz, (metin, soluk, sessiz)


@pytest.mark.parametrize("tema", list(TEMALAR))
def test_secili_cip_metni_AA(tema):
    """Secili cipte metin --bg, zemin --baglanti."""
    assert _k(_token("--bg", tema), _token("--baglanti", tema)) >= 4.5


@pytest.mark.parametrize("tema", list(TEMALAR))
def test_pist_ucu_numarasi_serit_uzerinde_AA(tema):
    """Pist ucu numaralari (fill --kart) --sessiz seridin USTUNDE duruyor.
    Tarayici olcer SVG cizgisini zemin olarak goremedigi icin bu durum
    elle hesaplaniyor."""
    assert _k(_token("--kart", tema), _token("--sessiz", tema)) >= 4.5


def _kural(secici):
    m = re.search(r"\n\s*" + re.escape(secici) + r"\s*\{([^}]*)\}", CSS)
    assert m, secici
    # Yorumlar kural degil: "opacity" kelimesi bir aciklamada gecebilir.
    return re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S)


@pytest.mark.parametrize("secici", [
    ".notam-cip b", ".tahmin-birim", ".pd-kuzey", ".pd-pist",
])
def test_metin_tasiyan_kuralda_OPAKLIK_yok(secici):
    """Opaklik token'in AA garantisini sessizce bozuyor: token 4.7:1
    verse bile opacity:.75 onu esigin altina itiyordu."""
    assert "opacity" not in _kural(secici), secici
