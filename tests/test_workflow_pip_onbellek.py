"""Bot workflow'u bagimliliklari requirements.txt'ten kuruyor ve pip
onbellegini o dosyanin ozetine bagliyor. Paket listesi workflow'a geri
yazilirsa onbellek anahtari gercek kurulumla kopar - bu testler onu kilitliyor."""
from pathlib import Path

WF = Path(".github/workflows/ltfj.yml").read_text(encoding="utf-8")
GEREKSINIM = Path("requirements.txt").read_text(encoding="utf-8")


def _paketler():
    return {s.strip() for s in GEREKSINIM.splitlines()
            if s.strip() and not s.lstrip().startswith("#")}


def test_bot_workflowu_pip_ONBELLEGI_requirements_ozetine_bagli():
    assert "cache: pip" in WF
    assert "cache-dependency-path: requirements.txt" in WF


def test_kurulum_AYNI_dosyadan():
    assert "pip install --quiet -r requirements.txt" in WF
    assert "pip install --quiet requests firebase-admin" not in WF


def test_botun_calisma_zamani_paketleri_listede():
    assert {"requests", "firebase-admin", "pywebpush"} <= _paketler()
