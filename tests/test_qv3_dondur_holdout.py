"""sis_modeli/qv3_dondur.py + qv3_holdout.py (sentetik veri, gercek arsiv
ve holdout okunmaz)."""
import json
import random
from datetime import datetime, timedelta

from sis_modeli import qv3_dondur as D, qv3_gbm, qv3_holdout as H, qv3_model


def _sentetik(tohum=11):
    rnd = random.Random(tohum)
    K = []
    for yil in (2015, 2016, 2017):
        t0 = datetime(yil, 1, 1)
        for i in range(1500):
            dt = t0 + timedelta(minutes=30 * i)
            r = {a: rnd.random() * 10 for a in qv3_model.SAYISAL}
            r.update({a: int(rnd.random() < 0.2) for a in qv3_model.IKILI})
            r.update({"dt": dt, "ay": dt.month, "saat": dt.hour,
                      "gorus": rnd.choice((800, 3000, 9999))})
            r["hedef"] = rnd.random() < (0.3 if r["gorus"] == 800 and r["br"] else 0.01)
            K.append(r)
    return K


def test_dondur_json_gidis_donus_ve_tahminler(tmp_path, monkeypatch):
    monkeypatch.setattr(qv3_gbm, "MAKS_AGAC", 20)
    donmus = D.dondur(_sentetik())
    yol = tmp_path / "donmus.json"
    D.yaz(donmus, yol)
    geri = D.oku(yol)
    assert geri["egitim_yillari"] == [2015, 2017]
    assert json.loads(yol.read_text(encoding="utf-8")) == geri
    kayit = {a: 5.0 for a in qv3_model.SAYISAL} | {a: 1 for a in qv3_model.IKILI}
    kayit.update({"ay": 1, "saat": 3, "gorus": 800})
    t = D.tahminler(geri, kayit)
    assert set(t) == {"GBM + Platt", "GBM ham", "QV3 WoE", "Model A seti",
                      "görüş bandı iklimi", "ay×saat iklimi"}
    assert all(0.0 <= p <= 1.0 for p in t.values())
    # JSON'dan okunan model, bellekteki ile ayni tahmini verir
    assert t["GBM ham"] == qv3_gbm.olasilik(donmus["gbm"]["model"], kayit)


def test_olaylar_bir_saatten_kisa_bosluk_ayni_olay():
    t0 = datetime(2024, 1, 1, 3, 20)
    K = [{"dt": t0 + timedelta(minutes=30 * i)} for i in range(8)]
    g = [True, True, False, False, True, False, False, True]
    assert H.olaylar(K, g) == [[0, 1], [4], [7]]


def test_esik_satiri():
    t0 = datetime(2024, 1, 1)
    K = [{"dt": t0 + timedelta(hours=12 * i)} for i in range(4)]
    s = H.esik_satiri(K, [0.5, 0.05, 0.3, 0.01], [True, False, False, True], [[0], [3]], 0.2)
    assert s == {"esik": 0.2, "olay_yakalanan": 1, "olay": 2, "uyari_gunu": 2, "isabet": 0.5}


def test_dondurma_holdout_kullanmaz_holdout_yalnizca_dosyayi_okur():
    d = open("sis_modeli/qv3_dondur.py", encoding="utf-8").read()
    h = open("sis_modeli/qv3_holdout.py", encoding="utf-8").read()
    assert "bolme.gelistirme(aday)" in d and "bolme.holdout" not in d
    assert "bolme.holdout(aday)" in h and "dondur(" not in h and "egit" not in h
