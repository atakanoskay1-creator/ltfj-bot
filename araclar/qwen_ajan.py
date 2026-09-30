#!/usr/bin/env python3
"""Yerel Qwen ajani: GitHub'daki `qwen-gorev` issue'larini yerel modele yaptirir.

AKIS (bkz. araclar/QWEN_AJAN.md)
  1) Claude (ya da siz) `qwen-gorev` etiketli bir issue acar; govdesinde
     "## Dosyalar" basligi altinda degisecek dosyalarin listesi olur.
  2) Bu betik, KULLANICININ BILGISAYARINDA, AYRI bir klonda calisir: issue'yu
     alir, main'den `qwen/<no>-<konu>` dalini acar, Aider ile LM Studio'daki
     modele isi yaptirir, testleri KENDISI calistirir; kirmiziysa hata
     ciktisini modele geri verir (en fazla AJAN_TUR tur).
  3) Yesilse dali push eder, PR acar, issue'ya yazar. MERGE ETMEZ - merge
     insan onayiyla, inceleme sonrasi yapilir.

GUVENLIK
  - Yalnizca `qwen-gorev` etiketli issue'lar islenir. Etiketi yalnizca repoya
    yazma yetkisi olanlar ekleyebilir; ayrica yazar OWNER/COLLABORATOR/MEMBER
    ya da AJAN_EK_YAZARLAR listesinde olmali.
  - Yalnizca issue'da listelenen dosyalar degisebilir; bot'un urettigi
    dosyalar, dondurulmus modeller, workflow'lar ve ajanin kendisi HER ZAMAN
    yasak. Ihlal varsa hicbir sey push edilmez.
  - Ajan yalnizca `--kur` ile hazirlanmis, isaretli bir klonda calisir
    (reset/clean yapar - kullanicinin calisma kopyasina asla dokunmaz).
  - GitHub token'i hicbir ciktiya yazilmaz.

KULLANIM
  py araclar/qwen_ajan.py --kur C:\\ltfj-ajan      # bir kez: ayri klon
  py araclar/qwen_ajan.py --bir-kez                # (klonun icinden) tek tur
  py araclar/qwen_ajan.py --dongu                  # 5 dk'da bir kontrol
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

# ----------------------------------------------------------------- ayarlar ---
GITHUB_API = "https://api.github.com"
VARSAYILAN_REPO = "atakanoskay1-creator/ltfj-bot"
ISARET_DOSYASI = "qwen-ajan-klonu"          # .git/ altinda

ETIKET_GOREV = "qwen-gorev"
ETIKET_ISLENIYOR = "qwen-isleniyor"
ETIKET_BITTI = "qwen-bitti"
ETIKET_BASARISIZ = "qwen-basarisiz"
ETIKET_RENK = {ETIKET_GOREV: "5319e7", ETIKET_ISLENIYOR: "fbca04",
               ETIKET_BITTI: "0e8a16", ETIKET_BASARISIZ: "d93f0b"}

IZINLI_YAZAR_ILISKISI = ("OWNER", "COLLABORATOR", "MEMBER")

# Issue'da listelense BILE degistirilemez (bkz. CONVENTIONS.md "Dokunma").
YASAK_DOSYALAR = frozenset({
    "index.html", "ltfj_state.json", "panel_veri.json", "notam_veri.json",
    "gozlem_arsivi.csv", "gozlem_surumleri.csv", "gozlem_arsivi_durum.json",
    "tahmin_gunlugu.csv", "tahmin_dogrulama.csv", "dis_kaynak_cache.json",
    "ltfj_sis_olasilik.py", "ltfj_sis_olasilik_b.py", "ltfj_tavan_tablosu.py",
    "CONVENTIONS.md", ".env",
})
YASAK_ONEKLER = (".github/", "araclar/", "sis_modeli/veri/")
# sis_modeli/ altinda YENI (salt okuma) betik eklenebilir, mevcutlar degismez.
DONDURULMUS_KLASOR = "sis_modeli/"

KUYRUK_SATIR = 60          # yoruma eklenecek test ciktisi satiri


def ayar(ad: str, varsayilan: str = "") -> str:
    return os.environ.get(ad, varsayilan).strip()


# ------------------------------------------------------------ saf yardimci ---
def dosyalari_ayikla(govde: str) -> list[str]:
    """Issue govdesindeki "## Dosyalar" bolumunun madde listesi."""
    out, icinde = [], False
    for satir in (govde or "").splitlines():
        s = satir.strip()
        if re.match(r"^#{1,6}\s", s):
            icinde = s.lstrip("#").strip().lower().startswith("dosyalar")
            continue
        if icinde and re.match(r"^[-*]\s+", s):
            yol = re.sub(r"^[-*]\s+", "", s).strip().strip("`").strip()
            yol = yol.replace("\\", "/")
            if yol and yol not in out:
                out.append(yol)
    return out


def yol_ihlali(yol: str, izlenenler: set) -> str | None:
    """Yol yasaksa nedenini, degilse None doner. izlenenler: git ls-files."""
    if not yol or yol.startswith("/") or re.match(r"^[A-Za-z]:", yol):
        return "mutlak yol"
    if ".." in Path(yol).parts:
        return "ust klasor (..)"
    if yol in YASAK_DOSYALAR:
        return "yasak dosya"
    if any(yol.startswith(o) for o in YASAK_ONEKLER):
        return "yasak klasor"
    if yol.startswith(DONDURULMUS_KLASOR) and yol in izlenenler:
        return "dondurulmus model dosyasi (yalnizca yeni dosya eklenebilir)"
    return None


# Arac/test calismasinin kendiliginden urettigi dosyalar - degisiklik sayilmaz.
# (Olculdu: ikinci turda pytest'in __pycache__'i "izin disi" sayilip gorev
# iptal ediliyordu.)
URETILEN_PARCALAR = ("__pycache__", ".pytest_cache")


def aider_dosyasi_mi(yol: str) -> bool:
    """Aider'in ve testlerin urettigi, commit'e girmeyecek dosyalar."""
    parcalar = Path(yol.rstrip("/")).parts
    return (Path(yol.rstrip("/")).name.startswith(".aider")
            or yol.endswith(".pyc")
            or any(p in URETILEN_PARCALAR for p in parcalar))


def degisen_yollar(porcelain: str) -> list[str]:
    """`git status --porcelain` ciktisindan degisen/yeni yollar."""
    out = []
    for satir in porcelain.splitlines():
        if len(satir) < 4:
            continue
        yol = satir[3:]
        if " -> " in yol:                       # yeniden adlandirma
            eski, yol = yol.split(" -> ", 1)
            out.append(eski.strip('"'))
        out.append(yol.strip('"'))
    return [y for y in out if not aider_dosyasi_mi(y)]


def izin_disi(degisenler: list[str], izinliler: list[str], izlenenler: set) -> list[str]:
    """Degisen ama izin verilmeyen (ya da yasak) yollar."""
    return [y for y in degisenler
            if y not in izinliler or yol_ihlali(y, izlenenler)]


def dal_adi(no: int, baslik: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    konu = re.sub(r"[^a-z0-9]+", "-", baslik.translate(tr).lower()).strip("-")
    return f"qwen/{no}-{konu[:40].rstrip('-') or 'gorev'}"


def yazar_izinli(issue: dict, ek_yazarlar: set) -> bool:
    return (issue.get("author_association") in IZINLI_YAZAR_ILISKISI
            or (issue.get("user") or {}).get("login") in ek_yazarlar)


def kuyruk(metin: str, n: int = KUYRUK_SATIR) -> str:
    temiz = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", metin or "")
    return "\n".join(temiz.strip().splitlines()[-n:])


def gorev_mesaji(issue: dict, dosyalar: list[str]) -> str:
    return (
        f"GOREV (#{issue['number']}): {issue['title']}\n\n"
        f"{issue.get('body') or ''}\n\n"
        "CALISMA KURALLARI:\n"
        f"- DOSYA YOLLARI: yalnizca su yollari HARFI HARFINE kullan: {', '.join(dosyalar)}\n"
        "- Gorev metninde gecen diger dosya adlari yalnizca BAGLAMDIR: onlari "
        "duzenleme, yeni dosya adi uydurma, cumle parcasini dosya adi yapma.\n"
        "- Baska hicbir dosyaya dokunma. Git komutu calistirma.\n"
        "- CONVENTIONS.md'deki kurallara uy (veri uydurma, yeni kutuphane yok).\n"
        "- Testler pytest ile calistirilacak; kirmizi olursa cikti sana "
        "verilecek, o zaman duzelt. Testi silme/atlatma.\n")


def eksik_mesaji(eksikler: list[str]) -> str:
    return ("Su dosyalar BOS ya da icinde hic test yok: " + ", ".join(eksikler)
            + ". Dosyanin TAM icerigini yaz (gorevdeki testlerin hepsi); "
            "yalnizca izin verilen dosyalari degistir.")


def duzeltme_mesaji(test_ciktisi: str) -> str:
    return ("Testler KIRMIZI. Asagidaki ciktiya gore duzelt; yalnizca izin "
            "verilen dosyalari degistir, testi silme ya da atlatma.\n\n"
            + kuyruk(test_ciktisi, 120))


# ------------------------------------------------------------------ github ---
class GitHub:
    def __init__(self, token: str, repo: str):
        self.repo = repo
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}",
                               "Accept": "application/vnd.github+json",
                               "X-GitHub-Api-Version": "2022-11-28"})

    def _istek(self, yontem, yol, **kw):
        r = self.s.request(yontem, f"{GITHUB_API}{yol}", timeout=30, **kw)
        if r.status_code >= 400:
            # Token URL'de degil, header'da - hata metninde gecmez.
            raise RuntimeError(f"GitHub {yontem} {yol}: {r.status_code} {r.text[:300]}")
        return r.json() if r.content else None

    def gorevler(self) -> list[dict]:
        liste = self._istek("GET", f"/repos/{self.repo}/issues",
                            params={"labels": ETIKET_GOREV, "state": "open",
                                    "sort": "created", "direction": "asc",
                                    "per_page": 30})
        return [i for i in liste if "pull_request" not in i]

    def etiketleri_hazirla(self):
        for ad, renk in ETIKET_RENK.items():
            try:
                self._istek("POST", f"/repos/{self.repo}/labels",
                            json={"name": ad, "color": renk})
            except RuntimeError as e:
                if "422" not in str(e):         # zaten var
                    raise

    def etiket_ekle(self, no, ad):
        self._istek("POST", f"/repos/{self.repo}/issues/{no}/labels", json={"labels": [ad]})

    def etiket_kaldir(self, no, ad):
        try:
            self._istek("DELETE", f"/repos/{self.repo}/issues/{no}/labels/{ad}")
        except RuntimeError:
            pass

    def yorum(self, no, metin):
        self._istek("POST", f"/repos/{self.repo}/issues/{no}/comments", json={"body": metin})

    def pr_ac(self, dal, baslik, govde) -> str:
        pr = self._istek("POST", f"/repos/{self.repo}/pulls",
                         json={"title": baslik, "head": dal, "base": "main", "body": govde})
        return pr["html_url"]


# --------------------------------------------------------------------- git ---
def calistir(komut, cwd, zaman_asimi=600, girdi=None) -> subprocess.CompletedProcess:
    # PYTHONDONTWRITEBYTECODE: model dosyayi ayni saniyede ayni uzunlukta
    # yeniden yazinca Python bayat .pyc'yi kullanip dogru duzeltmeyi
    # "kirmizi" gosterebiliyordu (simulasyonda olculdu).
    ortam = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(komut, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          timeout=zaman_asimi, input=girdi, env=ortam)


def git(repo, *args, kontrol=True) -> str:
    r = calistir(["git", *args], repo)
    if kontrol and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[:300]}")
    return r.stdout


def klon_mu(repo: Path) -> bool:
    return (repo / ".git" / ISARET_DOSYASI).exists()


def temizle(repo: Path):
    """Ajan klonunu origin/main'e dondurur. YALNIZCA isaretli klonda."""
    if not klon_mu(repo):
        raise RuntimeError("isaretli ajan klonu degil - temizleme reddedildi")
    git(repo, "checkout", "-q", "-f", "main", kontrol=False)
    git(repo, "fetch", "-q", "origin", "main")
    git(repo, "reset", "-q", "--hard", "origin/main")
    git(repo, "clean", "-q", "-fd")


def testleri_calistir(repo: Path) -> tuple[bool, str]:
    r = calistir([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], repo,
                 zaman_asimi=int(ayar("AJAN_TEST_ZAMAN_ASIMI", "1800")))
    return r.returncode == 0, r.stdout + r.stderr


def icerik_eksikleri(repo: Path, yollar: list[str]) -> list[str]:
    """Bos kalan dosyalar ve icinde toplanan test olmayan test dosyalari.

    Aider, listede olup bulunmayan dosyayi bastan BOS olusturur; model icerik
    yazmazsa dosya bos kalir, tum paket yine yesil gecer ve bos dosya PR olur
    (ilk ajan PR'i #113 boyle geldi). pytest'in "test toplanmadi" kodu 5."""
    eksik = []
    for y in yollar:
        dosya = repo / y
        if not dosya.is_file():
            continue                            # silinen dosya
        if not dosya.read_text(encoding="utf-8", errors="replace").strip():
            eksik.append(y)
            continue
        ad = Path(y)
        if ad.parts[:1] == ("tests",) and ad.name.startswith("test_") and ad.suffix == ".py":
            r = calistir([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                          "--collect-only", y], repo, zaman_asimi=300)
            if r.returncode == 5:
                eksik.append(y)
    return eksik


def durum(repo: Path) -> str:
    """Calisma agaci durumu; Turkce dosya adlari okunur yazilsin
    (core.quotePath), yeni klasorlerin icindeki dosyalar tek tek (-uall)."""
    return git(repo, "-c", "core.quotePath=false", "status", "--porcelain", "-uall")


def aider_calistir(repo: Path, mesaj: str, dosyalar: list[str], gunluk: Path = None) -> str:
    gecici = Path(tempfile.mkdtemp(prefix="qwen-ajan-"))
    mesaj_dosyasi = gecici / "mesaj.md"
    mesaj_dosyasi.write_text(mesaj, encoding="utf-8")
    komut = [
        ayar("AJAN_AIDER", "aider"),
        "--model", f"openai/{ayar('AJAN_MODEL')}",
        "--openai-api-base", ayar("AJAN_LLM_URL", "http://localhost:1234/v1"),
        "--openai-api-key", ayar("AJAN_LLM_ANAHTAR", "lm-studio"),
        "--read", "CONVENTIONS.md",
        "--yes-always", "--no-auto-commits", "--no-dirty-commits",
        "--no-gitignore", "--no-check-update", "--analytics-disable",
        "--no-show-model-warnings", "--no-pretty", "--no-stream",
        "--map-tokens", "0",
        "--chat-history-file", str(gecici / "sohbet.md"),
        "--input-history-file", str(gecici / "girdi.txt"),
        "--test-cmd", f'"{sys.executable}" -m pytest -q -x -p no:cacheprovider',
        "--auto-test",
        "--message-file", str(mesaj_dosyasi),
    ]
    if ayar("AJAN_EDIT_FORMAT"):
        komut += ["--edit-format", ayar("AJAN_EDIT_FORMAT")]
    komut += dosyalar
    r = calistir(komut, repo, zaman_asimi=int(ayar("AJAN_AIDER_ZAMAN_ASIMI", "3600")))
    cikti = r.stdout + r.stderr
    # Modelin ne yaptigi sonradan okunabilsin (ilk gercek denemede
    # gorulemiyordu). .git/ altinda: hicbir zaman commit'e girmez.
    if gunluk is not None:
        gunluk.parent.mkdir(parents=True, exist_ok=True)
        gunluk.write_text(cikti, encoding="utf-8")
    return cikti


# -------------------------------------------------------------------- ajan ---
def gorevi_isle(gh: GitHub, repo: Path, issue: dict) -> None:
    no, baslik = issue["number"], issue["title"]
    print(f"[ajan] #{no} {baslik}")
    dosyalar = dosyalari_ayikla(issue.get("body") or "")
    temizle(repo)
    izlenenler = set(git(repo, "ls-files").splitlines())

    son_aider = {"cikti": ""}

    def basarisiz(neden, ek=""):
        gh.etiket_kaldir(no, ETIKET_ISLENIYOR)
        gh.etiket_ekle(no, ETIKET_BASARISIZ)
        aider = kuyruk(son_aider["cikti"], 40)
        gh.yorum(no, f"Yerel ajan görevi tamamlayamadı: **{neden}**"
                 + (f"\n\n```\n{ek}\n```" if ek else "")
                 + (f"\n\n<details><summary>Aider çıktısının son satırları</summary>"
                    f"\n\n```\n{aider}\n```\n</details>" if aider else ""))
        temizle(repo)
        print(f"[ajan] #{no} basarisiz: {neden}")

    gh.etiket_ekle(no, ETIKET_ISLENIYOR)
    if not dosyalar:
        return basarisiz('issue\'da "## Dosyalar" listesi yok')
    ihlaller = [f"{y}: {yol_ihlali(y, izlenenler)}" for y in dosyalar
                if yol_ihlali(y, izlenenler)]
    if ihlaller:
        return basarisiz("izin verilmeyen dosya", "\n".join(ihlaller))

    dal = dal_adi(no, baslik)
    git(repo, "checkout", "-q", "-B", dal, "origin/main")

    mesaj = gorev_mesaji(issue, dosyalar)
    tur_sayisi = int(ayar("AJAN_TUR", "3"))
    yesil, cikti, neden = False, "", ""
    for tur in range(1, tur_sayisi + 1):
        print(f"[ajan] #{no} tur {tur}/{tur_sayisi}: model calisiyor...")
        son_aider["cikti"] = aider_calistir(
            repo, mesaj, dosyalar, repo / ".git" / "qwen-ajan-gunluk" / f"{no}-tur{tur}.log")
        degisenler = degisen_yollar(durum(repo))
        disi = izin_disi(degisenler, dosyalar, izlenenler)
        if disi:
            return basarisiz("model izin verilmeyen dosyalara dokundu", "\n".join(disi))
        if not degisenler:
            return basarisiz("model hiçbir dosyayı değiştirmedi")
        eksikler = icerik_eksikleri(repo, degisenler)
        if eksikler:
            neden = f"{tur_sayisi} turda dosya boş kaldı ya da test yazılmadı"
            cikti = "\n".join(eksikler)
            print(f"[ajan] #{no} tur {tur}: icerik eksik: {', '.join(eksikler)}")
            mesaj = eksik_mesaji(eksikler)
            continue
        yesil, cikti = testleri_calistir(repo)
        print(f"[ajan] #{no} tur {tur}: testler {'YESIL' if yesil else 'KIRMIZI'}")
        if yesil:
            break
        neden = f"{tur_sayisi} turda testler yeşile dönmedi"
        mesaj = duzeltme_mesaji(cikti)
    if not yesil:
        return basarisiz(neden, kuyruk(cikti))

    degisenler = degisen_yollar(durum(repo))
    git(repo, "add", "--", *degisenler)
    git(repo, "commit", "-q", "-m", f"Qwen: {baslik} (#{no})\n\n"
        "Yerel ajan (Qwen) tarafindan uretildi; inceleme bekliyor.")
    git(repo, "push", "-q", "-u", "origin", dal, "--force-with-lease")
    govde = (f"Refs #{no}\n\n**Yerel ajan (Qwen) tarafından üretildi — merge "
             "öncesi inceleme gerekli.**\n\n"
             "Değişen dosyalar:\n" + "".join(f"- `{y}`\n" for y in degisenler)
             + f"\nTest sonucu (ajanın bilgisayarında):\n```\n{kuyruk(cikti, 3)}\n```")
    url = gh.pr_ac(dal, f"Qwen: {baslik}", govde)
    gh.etiket_kaldir(no, ETIKET_ISLENIYOR)
    gh.etiket_ekle(no, ETIKET_BITTI)
    gh.yorum(no, f"Yerel ajan PR açtı: {url}")
    temizle(repo)
    print(f"[ajan] #{no} PR: {url}")


def bir_tur(gh: GitHub, repo: Path) -> None:
    ek_yazarlar = {y for y in ayar("AJAN_EK_YAZARLAR").split(",") if y}
    atla = {ETIKET_ISLENIYOR, ETIKET_BITTI, ETIKET_BASARISIZ}
    for issue in gh.gorevler():
        etiketler = {e["name"] for e in issue.get("labels", [])}
        if etiketler & atla:
            continue
        if not yazar_izinli(issue, ek_yazarlar):
            print(f"[ajan] #{issue['number']} atlandi: yazar izinli degil "
                  f"({(issue.get('user') or {}).get('login')}); gerekiyorsa "
                  "AJAN_EK_YAZARLAR'a ekleyin.")
            continue
        try:
            gorevi_isle(gh, repo, issue)
        except Exception as e:                  # tek gorev hatasi donguyu durdurmaz
            print(f"[ajan] #{issue['number']} beklenmeyen hata: {e}", file=sys.stderr)
            try:
                gh.etiket_kaldir(issue["number"], ETIKET_ISLENIYOR)
                gh.etiket_ekle(issue["number"], ETIKET_BASARISIZ)
                gh.yorum(issue["number"], f"Yerel ajan beklenmeyen hata: `{str(e)[:300]}`")
                temizle(repo)
            except Exception:
                pass
        return                                  # turda en fazla bir gorev


def kur(hedef: Path, repo_adi: str) -> None:
    if hedef.exists() and any(hedef.iterdir()):
        sys.exit(f"{hedef} bos degil - ayri, bos bir klasor secin.")
    r = calistir(["git", "clone", f"https://github.com/{repo_adi}.git", str(hedef)],
                 Path.cwd(), zaman_asimi=1800)
    if r.returncode != 0:
        sys.exit(f"git clone basarisiz: {r.stderr.strip()[:300]}")
    (hedef / ".git" / ISARET_DOSYASI).write_text("qwen ajan klonu\n", encoding="utf-8")
    # Ajanin commit'leri kullanicinin kendi commit'lerinden ayirt edilsin.
    git(hedef, "config", "user.name", ayar("AJAN_GIT_AD", "Qwen yerel ajan"))
    git(hedef, "config", "user.email",
        ayar("AJAN_GIT_EPOSTA", "qwen-ajan@users.noreply.github.com"))
    with open(hedef / ".git" / "info" / "exclude", "a", encoding="utf-8") as f:
        f.write("\n.aider*\n__pycache__/\n.pytest_cache/\n*.pyc\n")
    print(f"Ajan klonu hazir: {hedef}\nBundan sonra bu klasorden calistirin:\n"
          f"  cd {hedef}\n  py araclar\\qwen_ajan.py --bir-kez")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Yerel Qwen ajani")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--kur", metavar="KLASOR", help="ayri ajan klonu olustur")
    g.add_argument("--bir-kez", action="store_true", help="tek tur calis")
    g.add_argument("--dongu", action="store_true", help="surekli calis")
    a = ap.parse_args(argv)
    repo_adi = ayar("AJAN_GITHUB_REPO", VARSAYILAN_REPO)

    if a.kur:
        kur(Path(a.kur), repo_adi)
        return 0

    repo = Path(__file__).resolve().parents[1]
    if not klon_mu(repo):
        sys.exit("Bu klasor ajan klonu degil. Once: py araclar/qwen_ajan.py --kur <bos klasor>")
    token = ayar("AJAN_GITHUB_TOKEN")
    if not token or not ayar("AJAN_MODEL"):
        sys.exit("AJAN_GITHUB_TOKEN ve AJAN_MODEL tanimli olmali (bkz. araclar/QWEN_AJAN.md).")
    gh = GitHub(token, repo_adi)
    gh.etiketleri_hazirla()
    aralik = int(ayar("AJAN_ARALIK_SN", "300"))
    while True:
        try:
            bir_tur(gh, repo)
        except Exception as e:
            print(f"[ajan] tur hatasi: {e}", file=sys.stderr)
        if not a.dongu:
            return 0
        time.sleep(aralik)


if __name__ == "__main__":
    sys.exit(main())
