"""Üretilen HTML İYİ BİÇİMLİ mi?

NEDEN VAR — GERÇEK BİR OLAY: LVO panelini yeniden düzenlerken bir
`</details>` yanlış fonksiyona kaçtı ve hero hücrelerinin içine düştü.
Sonuç: `#panel-lvo` tarayıcıda 0 piksel yüksekliğe çöktü, yani LVO
sekmesi TAMAMEN BOŞ açılıyordu.

**1013 test bunu yakalamadı.** Hiçbiri sayfanın iyi biçimli olduğunu
doğrulamıyordu; hepsi metin parçası arıyordu ve parçalar yerindeydi.
Bozuk olan YAPIYDI.

Bu dosya o boşluğu kapatır: her anlamlı veri kombinasyonunda üretilen
sayfa ayrıştırılır ve etiket dengesi denetlenir.
"""
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

import pytest

import ltfj_sayfa as s

SIMDI = datetime.now(timezone.utc)

# Kendi kendini kapatan etiketler - yigina girmezler.
BOS_ETIKETLER = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
    # satir ici SVG
    "circle", "ellipse", "line", "path", "polygon", "polyline", "rect",
    "stop", "use",
}


class _Denetci(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.yigin = []
        self.hatalar = []

    def handle_starttag(self, etiket, ozellikler):
        if etiket not in BOS_ETIKETLER:
            self.yigin.append((etiket, self.getpos()))

    def handle_startendtag(self, etiket, ozellikler):
        pass                      # <foo /> kendini kapatir

    def handle_endtag(self, etiket):
        if etiket in BOS_ETIKETLER:
            return
        if not self.yigin:
            self.hatalar.append(f"fazladan </{etiket}> @{self.getpos()}")
            return
        acik, yer = self.yigin[-1]
        if acik != etiket:
            self.hatalar.append(
                f"</{etiket}> @{self.getpos()} kapatiyor ama acik olan "
                f"<{acik}> @{yer}")
            # kurtar: ayni adli en yakin acigi kapat
            for i in range(len(self.yigin) - 1, -1, -1):
                if self.yigin[i][0] == etiket:
                    del self.yigin[i:]
                    return
            return
        self.yigin.pop()


def _denetle(html: str):
    d = _Denetci()
    d.feed(html)
    return d.hatalar, [e for e, _ in d.yigin]


def _gecmis(n=12, gorus=True):
    g = []
    for i in range(n - 1, -1, -1):
        k = {"zaman": (SIMDI - timedelta(minutes=30 * i)).isoformat(),
             "tavan": 200 + i * 40, "ruzgar_hiz": 4, "qnh": 1019,
             "sicaklik": 13.0 + i * 0.2, "cig_noktasi": 13.0 + i * 0.1}
        if gorus:
            k["gorus"] = 400 + i * 220
        g.append(k)
    return g


def _rapor(tip, metin, dk=0):
    return {"tip": tip, "zaman": SIMDI - timedelta(minutes=dk),
            "icao": "LTFJ", "metin": metin}


METAR_SISLI = "LTFJ 231420Z 06005KT 0400 FG VV002 13/13 Q1019 NOSIG"
METAR_ACIK = "LTFJ 231420Z 06005KT CAVOK 20/10 Q1019 NOSIG"
TAF = "TAF LTFJ 231400Z 2315/2415 06005KT 3000 BR BKN004"

# Her senaryo AYRI bir kod yolunu acar: hero kivilcimlari, sis tahmin
# hucresi, Claude yorumu (katlanir), bos veri, coklu rapor karti.
SENARYOLAR = {
    "sisli + gecmis + tahmin": dict(
        raporlar=[_rapor("METAR", METAR_SISLI), _rapor("TAF", TAF, 40)],
        gecmis=_gecmis(),
        saatlik_tahmin=[{"saat": (SIMDI + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
                         "temperature_2m": 8, "dew_point_2m": 8, "visibility": 300,
                         "wind_speed_10m": 2, "cloud_cover_low": 95,
                         "weather_code": 45, "boundary_layer_height": 120}]),
    "acik hava, gecmis yok": dict(
        raporlar=[_rapor("METAR", METAR_ACIK)], gecmis=[]),
    "gorussuz gecmis (kivilcim eksik)": dict(
        raporlar=[_rapor("METAR", METAR_SISLI)], gecmis=_gecmis(gorus=False)),
    "SPECI + METAR + TAF": dict(
        raporlar=[_rapor("SPECI", METAR_SISLI), _rapor("METAR", METAR_ACIK, 20),
                  _rapor("TAF", TAF, 40)],
        gecmis=_gecmis()),
    "hic rapor yok": dict(raporlar=[], gecmis=[]),
    # TAHMIN YOK: "Beklenti" sekmesi bu senaryoda TAMAMEN BOS aciliyordu.
    # Testin ilk surumu bunu kacirmisti cunku tek senaryosu tahminliydi -
    # emoji testindekiyle AYNI kapsama bosluk deseni.
    "tahmin yok (bos sekme riski)": dict(
        raporlar=[_rapor("METAR", METAR_ACIK)], gecmis=_gecmis()),
    "bozuk METAR alanlari": dict(
        raporlar=[_rapor("METAR", "LTFJ 231420Z /////KT //// // Q////")],
        gecmis=[]),
}


@pytest.mark.parametrize("ad", list(SENARYOLAR))
def test_uretilen_sayfa_IYI_BICIMLI(ad, tmp_path):
    """Her senaryoda etiketler dengeli kapanmalı.

    Metin parçası aramak YETMEZ: parçalar yerinde dururken yapı bozulabilir
    ve bir panel sessizce 0 piksele çöker."""
    hedef = tmp_path / "index.html"
    s.sayfa_yaz(hedef=hedef, **SENARYOLAR[ad])
    hatalar, acik = _denetle(hedef.read_text(encoding="utf-8"))
    assert not hatalar, f"[{ad}] etiket hatası: {hatalar[:3]}"
    assert not acik, f"[{ad}] kapanmamış: {acik}"


class _PanelIcerik(HTMLParser):
    """Her sekme panelinin GERÇEK metin içeriğini toplar.

    Asıl belirtiyi ölçer: etiket dengesi bozulunca panel tarayıcıda 0
    piksele çöker ve sekme BOŞ açılır. Bir parça aramak bunu yakalamaz -
    parça sayfada durur, yanlış yerde durur."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.derinlik = {}          # panel adı -> açılış yığın derinliği
        self.icerik = {}            # panel adı -> toplanan metin
        self.yigin = []
        self.aktif = None

    def handle_starttag(self, etiket, ozellikler):
        if etiket in BOS_ETIKETLER:
            return
        oz = dict(ozellikler)
        kimlik = oz.get("id") or ""
        self.yigin.append(etiket)
        if kimlik.startswith("panel-"):
            ad = kimlik[len("panel-"):]
            self.aktif = ad
            self.derinlik[ad] = len(self.yigin)
            self.icerik[ad] = ""

    def handle_endtag(self, etiket):
        if etiket in BOS_ETIKETLER or not self.yigin:
            return
        if (self.aktif is not None
                and len(self.yigin) == self.derinlik.get(self.aktif)):
            self.aktif = None
        self.yigin.pop()

    def handle_data(self, veri):
        if self.aktif:
            self.icerik[self.aktif] += veri


def test_HICBIR_sekme_paneli_BOS_degil(tmp_path):
    """Bozuk bir kapanış etiketi paneli 0 piksele çökertir ve sekme boş
    açılır - tam olarak bu oldu. Panelin metin içeriği ölçülür."""
    hedef = tmp_path / "index.html"
    s.sayfa_yaz(hedef=hedef, **SENARYOLAR["tahmin yok (bos sekme riski)"])
    a = _PanelIcerik()
    a.feed(hedef.read_text(encoding="utf-8"))
    for anahtar in ("durum", "beklenti", "istatistik", "lvo", "notam"):
        assert anahtar in a.icerik, f"panel-{anahtar} hiç açılmamış"
        metin = " ".join(a.icerik[anahtar].split())
        assert len(metin) > 40, (
            f"panel-{anahtar} neredeyse boş ({len(metin)} karakter): {metin!r}")
