"""Yerel Qwen ajaninin GUVENLIK ve ayristirma kurallari (ag yok).

Ajan kullanicinin bilgisayarinda calisiyor; burada yalnizca saf fonksiyonlar
sinaniyor: hangi dosyalara dokunabilir, issue nasil okunur, dal adi, yazar
izni ve temizligin yalnizca isaretli klonda calismasi.
"""
import importlib.util
from pathlib import Path

import pytest

_yol = Path(__file__).resolve().parents[1] / "araclar" / "qwen_ajan.py"
_spec = importlib.util.spec_from_file_location("qwen_ajan", _yol)
aj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aj)

IZLENEN = {"ltfj_bot.py", "sis_modeli/hedef.py", "tests/test_x.py"}


def test_dosyalar_bolumu_ayristiriliyor():
    govde = ("## Görev\nBir şey yap\n\n## Dosyalar\n- `ltfj_bot.py`\n"
             "* tests\\test_yeni.py\n- ltfj_bot.py\n\n## Kabul\n- pytest yeşil\n")
    assert aj.dosyalari_ayikla(govde) == ["ltfj_bot.py", "tests/test_yeni.py"]
    assert aj.dosyalari_ayikla("## Görev\nyok\n") == []


@pytest.mark.parametrize("yol", [
    "index.html", "ltfj_state.json", "gozlem_arsivi.csv", "tahmin_gunlugu.csv",
    "ltfj_sis_olasilik.py", "ltfj_tavan_tablosu.py", "CONVENTIONS.md", ".env",
    ".github/workflows/ltfj.yml", "araclar/qwen_ajan.py",
    "sis_modeli/veri/ltfj_ozellik.csv.gz", "sis_modeli/hedef.py",
    "../disari.py", "/etc/passwd", "C:/Windows/x.py",
])
def test_yasak_yollar(yol):
    assert aj.yol_ihlali(yol, IZLENEN)


@pytest.mark.parametrize("yol", ["ltfj_bot.py", "tests/test_yeni.py",
                                 "sis_modeli/yeni_denetim.py"])
def test_izinli_yollar(yol):
    """sis_modeli/ altinda YENI dosya olur; izlenen dosya olmaz."""
    assert aj.yol_ihlali(yol, IZLENEN) is None


def test_porcelain_ayristirma_aider_dosyalarini_yok_sayar():
    cikti = (" M ltfj_bot.py\n?? tests/test_yeni.py\n?? .aider.chat.history.md\n"
             "?? __pycache__/\n?? tests/__pycache__/x.pyc\n?? .pytest_cache/\n"
             "R  eski.py -> yeni.py\n D silinen.py\n")
    assert aj.degisen_yollar(cikti) == ["ltfj_bot.py", "tests/test_yeni.py",
                                        "eski.py", "yeni.py", "silinen.py"]


def test_izin_disi_degisiklik_yakalaniyor():
    izinli = ["ltfj_bot.py", "tests/test_yeni.py"]
    assert aj.izin_disi(["ltfj_bot.py"], izinli, IZLENEN) == []
    assert aj.izin_disi(["ltfj_bot.py", "index.html"], izinli, IZLENEN) == ["index.html"]
    # listede olsa bile yasak dosya yine yakalanir
    assert aj.izin_disi(["index.html"], ["index.html"], IZLENEN) == ["index.html"]


def test_dal_adi_turkce_ve_uzunluk():
    d = aj.dal_adi(12, "Doğrulama özetine bağımsız olay sayısı ekle!")
    assert d.startswith("qwen/12-") and d == d.lower()
    assert all(c.isascii() for c in d) and len(d) <= len("qwen/12-") + 40
    assert aj.dal_adi(3, "!!!") == "qwen/3-gorev"


def test_yazar_izni():
    assert aj.yazar_izinli({"author_association": "OWNER"}, set())
    assert not aj.yazar_izinli({"author_association": "NONE",
                                "user": {"login": "yabanci"}}, set())
    assert aj.yazar_izinli({"author_association": "NONE",
                            "user": {"login": "claude[bot]"}}, {"claude[bot]"})


def test_temizlik_yalnizca_isaretli_klonda(tmp_path):
    (tmp_path / ".git").mkdir()
    with pytest.raises(RuntimeError):
        aj.temizle(tmp_path)


def test_gorev_mesaji_izinli_dosyalari_ve_kurallari_iceriyor():
    m = aj.gorev_mesaji({"number": 7, "title": "Başlık", "body": "Açıklama"},
                        ["ltfj_bot.py", "tests/test_yeni.py"])
    assert "#7" in m and "ltfj_bot.py, tests/test_yeni.py" in m
    assert "Git komutu calistirma" in m and "CONVENTIONS.md" in m


def test_kuyruk_ansi_temizler_ve_keser():
    metin = "\n".join(f"\x1b[31msatir {i}\x1b[0m" for i in range(100))
    k = aj.kuyruk(metin, 5)
    assert k.splitlines() == [f"satir {i}" for i in range(95, 100)]


def test_ajan_merge_etmiyor_ve_main_e_push_etmiyor():
    kaynak = _yol.read_text(encoding="utf-8")
    assert "/merge" not in kaynak and "merge_pull_request" not in kaynak
    assert '"push", "-q", "-u", "origin", dal' in kaynak
    assert 'push", "-q", "-u", "origin", "main"' not in kaynak


def test_token_ciktiya_yazilmiyor():
    kaynak = _yol.read_text(encoding="utf-8")
    for satir in kaynak.splitlines():
        if "print(" in satir:
            assert "token" not in satir.lower(), satir


def test_gorev_mesaji_baglamdaki_dosya_adlarini_ayiriyor():
    """Ilk gercek denemede model, metindeki "`ltfj_bot.py` icindeki fonksiyon"
    ifadesini dosya adi sanip o adla dosya olusturdu."""
    m = aj.gorev_mesaji({"number": 1, "title": "t", "body": "`ltfj_bot.py` icindeki"},
                        ["tests/test_a.py"])
    assert "HARFI HARFINE kullan: tests/test_a.py" in m
    assert "cumle parcasini dosya adi yapma" in m


def test_durum_turkce_adlari_okunur_ve_dosyalari_tek_tek_listeler():
    kaynak = _yol.read_text(encoding="utf-8")
    assert '"core.quotePath=false", "status", "--porcelain", "-uall"' in kaynak
    assert 'git(repo, "status", "--porcelain")' not in kaynak


def test_basarisizlik_yorumu_aider_ciktisini_iceriyor_ve_gunluk_git_altinda():
    kaynak = _yol.read_text(encoding="utf-8")
    assert "Aider çıktısının son satırları" in kaynak
    assert 'repo / ".git" / "qwen-ajan-gunluk"' in kaynak


def test_bos_dosya_ve_testsiz_test_dosyasi_eksik_sayilir(tmp_path):
    """Ilk ajan PR'i (#113) bos bir test dosyasiydi: Aider dosyayi bos
    olusturdu, model yazmadi, paket yine yesildi."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_bos.py").write_text("\n  \n", encoding="utf-8")
    (tmp_path / "tests" / "test_testsiz.py").write_text("import os\n", encoding="utf-8")
    (tmp_path / "tests" / "test_dolu.py").write_text(
        "def test_a():\n    assert True\n", encoding="utf-8")
    (tmp_path / "modul.py").write_text("", encoding="utf-8")
    (tmp_path / "dolu.py").write_text("X = 1\n", encoding="utf-8")
    yollar = ["tests/test_bos.py", "tests/test_testsiz.py", "tests/test_dolu.py",
              "modul.py", "dolu.py", "silinen.py"]
    assert aj.icerik_eksikleri(tmp_path, yollar) == [
        "tests/test_bos.py", "tests/test_testsiz.py", "modul.py"]


def test_eksik_icerikte_pr_acilmiyor_duzeltme_istenir():
    kaynak = _yol.read_text(encoding="utf-8")
    assert "eksikler = icerik_eksikleri(repo, degisenler)" in kaynak
    assert kaynak.index("icerik_eksikleri(repo, degisenler)") < kaynak.index(
        "yesil, cikti = testleri_calistir(repo)")
    assert "mesaj = eksik_mesaji(eksikler)" in kaynak
