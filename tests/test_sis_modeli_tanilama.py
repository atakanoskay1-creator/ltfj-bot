"""Coklu dogrusal baglanti tanilamasi testleri.

Korelasyon/VIF HAM deger uzerinde degil WOE uzerinde olculmeli - model de
WoE'yi goruyor."""
import math
from datetime import datetime, timezone

from sis_modeli import model, tanilama


def _kayitlar(n=3000):
    """x ile ikizi_x neredeyse ayni; bagimsiz_x GERCEKTEN iliskisiz.

    Dikkat: (i*7) % 10 gibi bir ifade bagimsiz DEGILDIR - 7 ile 10 aralarinda
    asal oldugu icin i % 10'un deterministik bir permutasyonudur (bu fixture
    bir kez bu yuzden yanlis kuruldu). Bagimsizlik icin ayri bir rastgele
    kaynak sart."""
    import random
    rastgele = random.Random(42)
    kayitlar = []
    for i in range(n):
        x = i % 10
        kayitlar.append({
            "dt": datetime(2020, 1, 1, tzinfo=timezone.utc),
            "gun": f"2020-01-{i % 28 + 1:02d}",
            "x": x,
            "ikizi_x": x + (0.01 if i % 2 else -0.01),   # x'in kopyasi
            "bagimsiz_x": rastgele.randrange(10),
            "hedef": x >= 8,
        })
    return kayitlar


def _tablolar(kayitlar, alanlar):
    return model.woe_tablolari(kayitlar, alanlar)


def test_kopya_degisken_yuksek_korelasyon_veriyor():
    k = _kayitlar()
    t = _tablolar(k, ["x", "ikizi_x", "bagimsiz_x"])
    adlar, M = tanilama.korelasyon_matrisi(k, t)
    i, j = adlar.index("x"), adlar.index("ikizi_x")
    assert M[i][j] > 0.9


def test_iliskisiz_degisken_dusuk_korelasyon():
    k = _kayitlar()
    t = _tablolar(k, ["x", "bagimsiz_x"])
    adlar, M = tanilama.korelasyon_matrisi(k, t)
    i, j = adlar.index("x"), adlar.index("bagimsiz_x")
    assert abs(M[i][j]) < 0.5


def test_korelasyon_matrisi_simetrik_ve_kosegeni_bir():
    k = _kayitlar()
    t = _tablolar(k, ["x", "bagimsiz_x"])
    _, M = tanilama.korelasyon_matrisi(k, t)
    for i in range(len(M)):
        assert abs(M[i][i] - 1.0) < 1e-9
        for j in range(len(M)):
            assert abs(M[i][j] - M[j][i]) < 1e-9


def test_vif_kopya_degiskende_yuksek():
    k = _kayitlar()
    t = _tablolar(k, ["x", "ikizi_x", "bagimsiz_x"])
    v = tanilama.vif(k, t)
    assert v["x"] > tanilama.VIF_CIDDI
    assert v["ikizi_x"] > tanilama.VIF_CIDDI
    assert v["bagimsiz_x"] < tanilama.VIF_DIKKAT


def test_vif_bagimsiz_degiskenlerde_bire_yakin():
    k = _kayitlar()
    t = _tablolar(k, ["x", "bagimsiz_x"])
    for deger in tanilama.vif(k, t).values():
        assert deger < 2.0


def test_vif_tek_degiskende_bir():
    k = _kayitlar()
    assert tanilama.vif(k, _tablolar(k, ["x"])) == {"x": 1.0}


def test_isaret_kontrolu_negatif_katsayiyi_isaretliyor():
    """WoE modelinde saglikli katsayi POZITIF olmali; negatif katsayi
    degiskenin 'duzeltici' olarak kullanildigini gosterir."""
    tablolar = {"a": [{"woe": 0.0}], "b": [{"woe": 0.0}]}
    sonuc = tanilama.isaret_kontrolu(tablolar, [0.0, 0.5, -0.3])
    isaretli = {s["alan"]: s["sorunlu"] for s in sonuc}
    assert isaretli["a"] is False
    assert isaretli["b"] is True


def test_isaret_kontrolu_alan_sirasi_katsayilarla_eslesiyor():
    """Katsayi vektoru sirasi desen() ile ayni olmali (alfabetik), yoksa
    isaretler yanlis degiskene atanir."""
    tablolar = {"zeta": [{"woe": 0.0}], "alfa": [{"woe": 0.0}]}
    sonuc = tanilama.isaret_kontrolu(tablolar, [0.0, 1.0, -1.0])
    assert sonuc[0]["alan"] == "alfa" and sonuc[0]["katsayi"] == 1.0
    assert sonuc[1]["alan"] == "zeta" and sonuc[1]["katsayi"] == -1.0
