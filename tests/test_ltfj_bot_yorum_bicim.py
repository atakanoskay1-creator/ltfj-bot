import pytest
import ltfj_bot as b

@pytest.mark.parametrize("girdi,beklenen", [
    ("Rüzgâr: 270/08 KT", "<b>Rüzgâr:</b> 270/08 KT"),
    ("Görüş : 10 km", "<b>Görüş:</b> 10 km"),
    ("Dikkat:  CB < 5 km & TS", "<b>Dikkat:</b> CB &lt; 5 km &amp; TS"),
    ("rüzgâr: küçük harf", "rüzgâr: küçük harf"),
    ("Özet: listede yok", "Özet: listede yok"),
    ("Dikkat:", "Dikkat:"),
])
def test_etiketler(girdi, beklenen):
    assert b._yorumu_bicimle(girdi) == beklenen

def test_madde_isareti():
    assert b._yorumu_bicimle("-yağmur") == "•yağmur"

def test_html_kacis():
    assert b._yorumu_bicimle("Uyarı: <CB> & TS") == "Uyarı: &lt;CB&gt; &amp; TS"

def test_cok_satirli():
    girdi = "Uçuşa etkisi: yok\n- madde\n\n  Düz satır  "
    beklenen = "<b>Uçuşa etkisi:</b> yok\n• madde\nDüz satır"
    assert b._yorumu_bicimle(girdi) == beklenen

@pytest.mark.parametrize("girdi", ["", "   \n\n  "])
def test_bos_girdi(girdi):
    assert b._yorumu_bicimle(girdi) == ""
