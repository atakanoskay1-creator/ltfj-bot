
// ---- ORTAK: goreli sure yazimi -------------------------------------------
// BURADA, cunku ilk tuketicisi hemen asagidaki baslik betigi. Eskiden bu
// fonksiyon NOTAM blogunun icinde, baslik betiginden SONRA tanimliydi ve
// baslik sessizce yedek bicime ("120 dk once") dusuyordu - "2 sa once"
// yerine. Tanim tuketiciden once gelmeli.
//
// GORECELI yaziyoruz cunku sayfadaki saatler yerel, veri UTC: "16:00'da"
// hangi saat dilimi oldugu soylenmeden yaniltici, "6 sa once" degil.
// SU AN blogu ekrandan cikinca yapiskan seridi ac. Ikisi ayni dort
// olcuyu gosteriyor; ayni anda ikisini birden cizmek, ayni sayiyi
// 374 piksel arayla iki kez yazmak demekti (bkz. _olcu).
// IntersectionObserver yoksa (cok eski tarayici) serit HEP acik kalir -
// bilgi kaybi degil, yalnizca tekrar.
(function () {
  var suAn = document.getElementById("su-an");
  var sarmal = document.querySelector(".yapiskan-ust");
  if (!sarmal) return;
  if (!suAn || !("IntersectionObserver" in window)) {
    sarmal.classList.add("serit-acik");
    return;
  }
  new IntersectionObserver(function (girisler) {
    girisler.forEach(function (g) {
      sarmal.classList.toggle("serit-acik", !g.isIntersecting);
    });
  }, {threshold: 0}).observe(suAn);
})();

window.ltfjGecenSure = function (ms) {
  if (ms == null || isNaN(ms) || ms < 0) return "az önce";
  var dk = Math.floor(ms / 60000);
  if (dk < 1) return "az önce";
  if (dk < 60) return dk + " dk önce";
  var sa = Math.floor(dk / 60);
  if (sa < 24) return sa + " sa önce";
  return Math.floor(sa / 24) + " gün önce";
};

// ---- UYGULAMA BASLIGI: UTC saat + veri tazeligi ---------------------------
// SUNUCUDA hesaplanamaz: sayfa bir vardiya boyunca acik kalabiliyor ve
// sunucuda yazilan "canli" etiketi bir saat sonra yalan olurdu. Butun
// yaslandirma burada, tarayicinin saatine gore yapiliyor.
//
// ESIKLER PYTHON TARAFINDAN GELIYOR (ltfj_ayarlar): GOZLEM_TAZE_DK ve
// SESSIZLIK_SAAT. Ikincisini bot Telegram alarmi icin de kullaniyor -
// sayfa "canli" derken Telegram "kesinti" diyemesin.
(function () {
  var BEKLENEN_DK = @@gozlem_beklenen_dk@@;
  var TAZE_DK = @@gozlem_taze_dk@@;
  var KESINTI_DK = @@sessizlik_saat@@ * 60;
  var durumEl = document.getElementById("ust-durum");
  var saatEl = document.getElementById("ust-saat");

  function yasDk(iso) {
    if (!iso) { return null; }
    var t = Date.parse(iso);
    return isNaN(t) ? null : (Date.now() - t) / 60000;
  }

  function ikonNokta() {
    return '<svg class="ikon" viewBox="0 0 24 24" aria-hidden="true">'
         + '<circle cx="12" cy="12" r="5"/></svg>';
  }

  // ACIK SEKME BAYATLIGI - kullanici bildirdi (iPad'de sayfa acik).
  //
  // Gozlem damgasi (data-gozlem) HTML'e GOMULU; yas her 15 saniyede
  // ISTEMCIDE yeniden hesaplaniyor. Sayfa kendini yenilemedigi icin
  // sekme acik durdukca yas buyuyor, SUNUCUDAKI veri taze olsa bile.
  //
  // Olculdu - sayfayi 12:00'de acinca:
  //   12:20  sekmede 12:00 gozlemi, rozet CANLI  (gercek guncel 12:20)
  //   12:45  sekmede 12:00 gozlemi, rozet CANLI  (gercek guncel 12:20)
  //   12:51  yas 51 dk -> "1 GOZLEM KACTI"
  // Yani once 45 DAKIKALIK BIR METAR "CANLI" diye gosteriliyor (sessiz
  // ve yanlis), sonra da yanlis alarm veriliyor. Ikisi de kotu.
  //
  // COZUM: kadansa yakin araliklarla SUNUCUYA BAK, ama YALNIZCA SAYFA
  // DEGISTIYSE bir sey yap.
  //
  // CANLI GUNCELLEME (kullanici istedi: "sayfayi yenilemesem bile bilgi
  // guncellenebilir mi"). Eskiden yeni gozlem gorulunce SAYFA YENIDEN
  // YUKLENIYORDU; yazarken / panel acikken ise hic yuklenmiyor ve kullanici
  // eski veriye bakmaya devam ediyordu. Artik yeni HTML indirilip veri
  // bolgeleri YERINDE degistiriliyor (bkz. 12_canli.js): kaydirma, acik
  // sekme, acik bolumler ve yazilan girdiler oldugu gibi kaliyor.
  // Yerinde degisim yapilamazsa (sayfa yapisi degismis) eski yol: gozlem
  // degistiyse ve guvenliyse yeniden yukle.
  //
  // MALIYET: her dakika yalnizca bir HEAD istegi (govdesiz, ~1 KB).
  // Sayfanin kendisi (~60 KB) YALNIZCA surum damgasi (ETag /
  // Last-Modified) degisince iner - yani bot her yeni sayfa yazdiginda.
  var KONTROL_MS = 60000;             // 1 dk - METAR kadansinin cok altinda
  var kontrolBekliyor = false;
  var oncekiSinif = null;
  var sonSurum = null;                // son UYGULANAN sayfanin damgasi

  function yenilemeGuvenli() {
    // Kullanici YAZIYORSA yeniden yukleme: LVO RVR girdileri kalici
    // degil, silinirdi.
    var odak = document.activeElement;
    if (odak && /^(INPUT|TEXTAREA|SELECT)$/.test(odak.tagName)) { return false; }
    // Acik bir panel/modal varken de yukleme - kullanici onun icinde.
    var ortuler = document.querySelectorAll(".atc-panel-ortu, .vfr-panel-ortu");
    for (var i = 0; i < ortuler.length; i++) {
      if (!ortuler[i].hasAttribute("hidden")) { return false; }
    }
    return true;
  }

  function surumDamgasi(y) {
    return y.headers.get("ETag") || y.headers.get("Last-Modified") || null;
  }

  function yeniVeriVarMi() {
    if (kontrolBekliyor || document.hidden || !window.fetch) { return; }
    var simdikiGozlem = durumEl ? durumEl.getAttribute("data-gozlem") : null;
    if (!simdikiGozlem) { return; }
    kontrolBekliyor = true;
    function adres() { return window.location.pathname + "?_=" + Date.now(); }
    fetch(adres(), {method: "HEAD", cache: "no-store"})
      .then(function (h) {
        var damga = h.ok ? surumDamgasi(h) : null;
        // Damga AYNIYSA govde hic inmez.
        if (damga && damga === sonSurum) { return null; }
        return fetch(adres(), {cache: "no-store"}).then(function (y) {
          if (!y.ok) { return null; }
          var d = surumDamgasi(y) || damga;
          return y.text().then(function (metin) { return {metin: metin, damga: d}; });
        });
      })
      .then(function (cevap) {
        kontrolBekliyor = false;
        if (!cevap || !cevap.metin) { return; }
        var metin = cevap.metin;
        var m = metin.match(/id="ust-durum" data-gozlem="([^"]*)"/);
        if (!m || !m[1]) { return; }
        // Once YERINDE guncelleme. "bekle": kullanici su an degisecek
        // bolgenin icinde yaziyor ya da bir pencere acik - damga
        // kaydedilmiyor, bir sonraki kontrolde yeniden denenir.
        var sonuc = window.ltfjCanliUygula ? window.ltfjCanliUygula(metin) : "yukle";
        if (sonuc === "bekle") { return; }
        if (sonuc !== "yukle") { sonSurum = cevap.damga; return; }
        // YEDEK YOL: yerinde guncellenemedi. Damga AYNIYSA yeniden yukleme
        // yok: bayatlik gercek, rozet onu durustce zaten soyluyor.
        if (m[1] === simdikiGozlem) { sonSurum = cevap.damga; return; }
        if (!yenilemeGuvenli()) { return; }
        window.location.replace(window.location.pathname + "?_=" + Date.now());
      })
      .catch(function () { kontrolBekliyor = false; });   // cevrimdisi: sessiz
  }

  function durumTazele() {
    if (saatEl) {
      var d = new Date();
      saatEl.textContent =
        String(d.getUTCHours()).padStart(2, "0") + ":" +
        String(d.getUTCMinutes()).padStart(2, "0") + "Z";
    }
    if (!durumEl) { return; }
    var gozlem = durumEl.getAttribute("data-gozlem");
    var dk = yasDk(gozlem);
    var sinif, metin;
    if (dk === null) { sinif = "kesinti"; metin = "VERİ YOK"; }
    else if (dk <= BEKLENEN_DK) { sinif = "taze"; metin = "CANLI"; }
    // BESINCI DURUM. Dort durum varken 35-70 dk arasi "CANLI" kutusunun
    // icindeydi: METAR 49 dakikalikken rozet CANLI diyordu. Oysa kadans
    // 30 dk + ~5 dk gecikme, yani o aralik "bir gozlem kacti" demek.
    // Kacirilmis bir gozlem hata degil (MGM gecikebilir) ama CANLI da
    // degil - okuyanin bilmesi gereken bir sey.
    else if (dk <= TAZE_DK) { sinif = "gecikmeli"; metin = "1 GÖZLEM KAÇTI"; }
    else if (dk <= KESINTI_DK) { sinif = "gecikmeli"; metin = "GECİKMELİ"; }
    else { sinif = "kesinti"; metin = "VERİ KESİNTİSİ"; }
    // Rozet CANLI'dan ciktiginda (ya da sayfa zaten bayat acildiginda)
    // TEK SEFERLIK bir halka - kosede kucuk bir rozetin degisimi kolay
    // kacar. Durum ayni kaldikca 15 sn'lik tazeleme tekrar oynatmaz.
    var degisti = sinif !== oncekiSinif && sinif !== "taze";
    oncekiSinif = sinif;
    durumEl.className = "ust-durum " + sinif + (degisti ? " durum-degisti" : "");
    durumEl.innerHTML = ikonNokta() + metin;
    // Renk TEK BASINA durum anlatmaz - ekran okuyucu icin metin de var.
    durumEl.setAttribute("aria-label", "Veri durumu: " + metin);
  }

  function yaslariTazele() {
    var oge = document.querySelectorAll(".veri-oge time[data-zaman]");
    Array.prototype.forEach.call(oge, function (t) {
      var dk = yasDk(t.getAttribute("data-zaman"));
      if (dk === null) { t.textContent = "—"; return; }
      t.textContent = window.ltfjGecenSure
        ? window.ltfjGecenSure(dk * 60000)
        : Math.round(dk) + " dk önce";
      t.parentNode.classList.toggle("bayat", dk > KESINTI_DK);
    });
  }

  function fazTazele() {
    var el = document.getElementById("ust-faz");
    var k = document.documentElement;
    if (!el) { return; }
    var dogus = Date.parse(k.getAttribute("data-gun-dogumu") || "");
    var batim = Date.parse(k.getAttribute("data-gun-batimi") || "");
    if (isNaN(dogus) || isNaN(batim)) { el.textContent = ""; return; }
    var t = Date.now();
    var gunduz = (t >= dogus && t < batim);
    // Siradaki gecis: gunduzsek batim, gecesek dogus.
    var sirada = new Date(gunduz ? batim : dogus);
    function ikili(n) { return String(n).padStart(2, "0"); }
    var saat = ikili(sirada.getUTCHours()) + ":" + ikili(sirada.getUTCMinutes()) + "Z";
    el.textContent = (gunduz ? "gündüz · batım " : "gece · doğuş ") + saat;
    el.setAttribute("title", gunduz
      ? "Gün batımı " + saat + " (LTFJ için hesaplanmış)"
      : "Gün doğumu " + saat + " (LTFJ için hesaplanmış) — sis penceresi");
  }

  function hepsi() { durumTazele(); yaslariTazele(); fazTazele(); }
  // Canli guncelleme yeni damgalari yazdiktan sonra rozet/yaslar HEMEN
  // tazelensin, 15 sn beklemesin.
  window.ltfjBaslikTazele = hepsi;
  hepsi();
  // Kadans kontrolu: dakikada bir sunucuya bak. Sekme arkada iken
  // atlaniyor (pil), one gelince hemen bir kez bakiliyor.
  setInterval(yeniVeriVarMi, KONTROL_MS);
  // 15 sn: dakika degisimini kacirmayacak kadar sik, saniye saymayacak
  // kadar seyrek - surekli hareket operasyonel ekranda gurultudur.
  setInterval(hepsi, 15000);
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) { hepsi(); yeniVeriVarMi(); }
  });
})();

// ---- SEKME GECISI --------------------------------------------------------
// Gorunurlugu CSS yapiyor (html[data-sekme=...]), JS degil. Sebep: acilista
// dogru panelin ILK karede acik olmasi gerekiyor ve bunu <head>'deki satir
// ici betik hallediyor. Burada yalnizca durumu DEGISTIRIYORUZ; iki yerde
// iki ayri gizleme mantigi olsaydi biri otekinden sapardi.
(function () {
  var cubuk = document.querySelector(".sekme-cubugu");
  if (!cubuk) { return; }
  var dugmeler = Array.prototype.slice.call(cubuk.querySelectorAll(".sekme"));

  function sec(anahtar, odakla) {
    document.documentElement.setAttribute("data-sekme", anahtar);
    dugmeler.forEach(function (d) {
      var bu = d.getAttribute("data-sekme") === anahtar;
      d.setAttribute("aria-selected", String(bu));
      // Klavyeyle gezinirken Tab tek seferde cubugu gecsin diye secili
      // olmayanlar sekme sirasindan cikarilir (WAI-ARIA tablist deseni).
      d.tabIndex = bu ? 0 : -1;
      if (bu && odakla) { d.focus(); }
      // Cubuk tasiyorsa secili sekme gorunur olsun: NOTAM'dayken sayfayi
      // yeniden acinca o sekme cubugun disinda kalabiliyordu.
      // scrollIntoView DEGIL - o, yapiskan cubugu tasidigi icin SAYFAYI da
      // kaydiriyor; yalnizca cubugun kendi scrollLeft'ini oynatiyoruz.
      if (bu) {
        var sol = d.offsetLeft, sag = sol + d.offsetWidth;
        if (sol < cubuk.scrollLeft) { cubuk.scrollLeft = sol - 4; }
        else if (sag > cubuk.scrollLeft + cubuk.clientWidth) {
          cubuk.scrollLeft = sag - cubuk.clientWidth + 4;
        }
      }
    });
    try { localStorage.setItem("ltfj-sekme", anahtar); } catch (e) {}
  }

  dugmeler.forEach(function (d, i) {
    d.addEventListener("click", function () {
      sec(d.getAttribute("data-sekme"), false);
    });
    d.addEventListener("keydown", function (e) {
      var yon = e.key === "ArrowRight" ? 1 : (e.key === "ArrowLeft" ? -1 : 0);
      if (!yon) { return; }
      e.preventDefault();
      var j = (i + yon + dugmeler.length) % dugmeler.length;
      sec(dugmeler[j].getAttribute("data-sekme"), true);
    });
  });

  // <head> betiginin sectigi sekmeyi dugme durumlariyla hizala: o betik
  // yalnizca data-sekme yaziyor, aria-selected hep "durum"da kaliyordu.
  var acik = document.documentElement.getAttribute("data-sekme") || "durum";
  sec(acik, false);
})();

// NOTAM'in SU ANKI gecerliligi - HEM "Aktif NOTAM'lar"/arama bolumu HEM DE
// LVO panelindeki NOTAM listesi bunu kullanir. TEK yerde durmasinin sebebi
// somut: ayni "aktif mi?" karari iki ayri script'te kopyalanmisti ve
// kopyalarin ikisi de ayni hatayi tasiyordu.
//
// Kritik: kayitlardaki `status` alani NOTAC'tan en son GORULDUGU andaki
// degerdir ve DONUKTUR - suresi dolmus bir NOTAM yerel gecmiste sonsuza
// dek "active" yazar. Bu yuzden suresi bitmis NOTAM'lar aktif gorunuyordu.
// Tarih penceresini her cizimde YENIDEN hesapliyoruz; sayfa saatlerce
// acik kalsa bile etiket kendiliginden dogruya doner.
//
// NOTAC'in kendi status'u yine de belirleyici: "cancelled"/"withdrawn"
// gibi bir deger tarih penceresinden BAGIMSIZ olarak gecerlidir (iptal
// edilmis bir NOTAM tarihi gecmemis olsa da yururlukte degildir).
// effective_end bos olan NOTAM kalicidir (ornegin G4445/14), suresi dolmaz.
// NOTAM TIPI (N/R/C) ve Q KODU - iki NOTAM listesi de (Aktif/arama ve
// LVO paneli) ayni yardimcilari kullaniyor.
//
// NOTAMR/NOTAMC HANGI NOTAM'I etkiliyor? notam_type alani NOTAC'in
// YAPISAL alani ve her kayitta var ("N" yeni, "R" yerine gecen, "C"
// iptal). Ama YERINE GECTIGI NOTAM'IN NUMARASI NOTAC'in gozlenen
// yanitinda AYRI BIR ALAN OLARAK YOK ve "text" yalnizca E) govdesini
// tasiyor - 16 gercek kayitta "NOTAMR B1234/26" kalibi hic gecmedi.
// Bu yuzden numara ancak metinde GERCEKTEN yaziyorsa gosteriliyor;
// yoksa satir hic cizilmiyor. Eslestirmeyi TAHMIN ETMIYORUZ (ayni Q
// kodu + ayni pist gibi bir cikarim yanlis NOTAM'i isaret edebilirdi).
window.ltfjNotamKacis = function (s) {
  "use strict";
  return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
    return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
  });
};

window.ltfjNotamTipEtiketi = function (n) {
  "use strict";
  // "N" (yeni) icin rozet YOK: her kartta duran bir rozet bilgi
  // tasimaz, yalnizca gurultu olur. Dikkat ceken R ve C.
  var tipler = {
    "R": {ad: "NOTAMR", baslik: "Önceki bir NOTAM'ın yerine geçti"},
    "C": {ad: "NOTAMC", baslik: "Bir NOTAM'ı iptal ediyor"},
  };
  var bilgi = tipler[(n.notam_type || "").toUpperCase()];
  if (!bilgi) return "";
  return '<span class="notam-tip" title="' + window.ltfjNotamKacis(bilgi.baslik) +
         '">' + bilgi.ad + "</span>";
};

window.ltfjNotamQEtiketi = function (n) {
  "use strict";
  // Q kodu HAM gosteriliyor - kendi Turkce karsiligimizi uydurmuyoruz.
  var kod = (n.q_code || "").trim().toUpperCase();
  if (!kod) return "";
  return '<span class="notam-q" title="ICAO Q kodu (NOTAC verisi)">' +
         window.ltfjNotamKacis(kod) + "</span>";
};

window.ltfjNotamIlgiliSatiri = function (n) {
  // REGEX PYTHON TARAFINDA. Once burada bir kopyasi vardi; ayni kural
  // iki dilde iki kez yazilmis oluyordu ve hangi alanda arandigini da
  // sabitliyordu. Artik ltfj_notam.ilgili_notam_referansi() ham kaydin
  // TUM metin alanlarinda ariyor, sonucu "ilgili_notam" olarak geliyor.
  "use strict";
  var satirlar = "";
  var i = n.ilgili_notam;
  if (i && i.numara) {
    var fiil = String(i.tip).toUpperCase() === "C" ? "iptal ettiği" : "yerine geçtiği";
    satirlar += '<div class="notam-ilgili">' + window.ltfjNotamKacis(fiil) +
                " NOTAM: <b>" + window.ltfjNotamKacis(i.numara) + "</b></div>";
  }
  // Bu NOTAM'i IPTAL EDEN NOTAMC ve iptal tarihi (bkz. ltfj_notam.
  // iptalleri_isle). Tarih NOTAMC'nin B) alanidir.
  var p = n.iptal;
  if (p) {
    var z = window.ltfjNotamIptalZamani(p.zaman);
    satirlar += '<div class="notam-ilgili notam-iptal">İptal edildi' +
                (p.eden ? ": <b>" + window.ltfjNotamKacis(p.eden) + "</b>" : "") +
                (z ? " · " + window.ltfjNotamKacis(z) : "") + "</div>";
  }
  return satirlar;
};

// NOTAMC iptal zamani, NOTAM kunyesindeki bicimle ("24.09 18:18Z").
window.ltfjNotamIptalZamani = function (iso) {
  "use strict";
  var d = new Date(iso || "");
  if (!iso || isNaN(d)) return "";
  var ik = function (x) { return (x < 10 ? "0" : "") + x; };
  return ik(d.getUTCDate()) + "." + ik(d.getUTCMonth() + 1) + "." + d.getUTCFullYear() +
         " " + ik(d.getUTCHours()) + ":" + ik(d.getUTCMinutes()) + "Z";
};

window.ltfjNotamGecerlilik = function (n) {
  "use strict";
  var simdi = Date.now();
  // IPTAL EDILDI (NOTAMC). Botun kendi isareti (bkz. ltfj_notam.
  // iptalleri_isle): tarih penceresinden ve NOTAC'in donuk status'undan
  // ONCE bakiliyor - iptal edilen NOTAM tarihi gecmemis olsa da artik
  // yururlukte degildir. Aktif/yaklasan listeleri bu durumu dislar.
  if (n.iptal) {
    var z = window.ltfjNotamIptalZamani(n.iptal.zaman);
    return {durum: "iptal",
            etiket: "iptal edildi" + (z ? " · " + z : ""),
            vurgula: true};
  }
  // NOTAMC'NIN KENDISI bir kisitlama degil, iptal bildirimi: "kalan sure"
  // yazmak onu yururlukteki bir kisitlama gibi gosterirdi. Aktif listeye
  // zaten girmiyor (bkz. ltfj_notam._listeden_haric); gecmiste boyle gorunur.
  if (String(n.notam_type || "").toUpperCase() === "C") {
    return {durum: "iptal_bildirimi", etiket: "iptal bildirimi", vurgula: true};
  }
  // "upcoming" DA CANLI BIR DURUM. Bu satir yalnizca "active" varken
  // yazilmisti; NOTAC'in status sozlugu OLCULUNCE (active / upcoming /
  // expired) yururluge girmemis kayitlarin "upcoming" tasidigi ortaya
  // cikti ve bu kontrol onlari "diger" kutusuna atiyordu - yani
  // Yaklasan NOTAM bolumu VERI OLDUGU HALDE bos kaliyordu.
  // (Tarayicida yakalandi; birim testleri "active" fiksturu kullandigi
  // icin gormemisti.)
  var CANLI_DURUMLAR = ["active", "upcoming"];
  if (n.status && CANLI_DURUMLAR.indexOf(String(n.status).toLowerCase()) === -1) {
    return {durum: "diger", etiket: n.status, vurgula: true};
  }
  var bas = n.effective_start ? Date.parse(n.effective_start) : NaN;
  var bit = n.effective_end ? Date.parse(n.effective_end) : NaN;
  if (!isNaN(bit) && bit < simdi) {
    return {durum: "doldu", etiket: "süresi doldu", vurgula: true};
  }
  if (!isNaN(bas) && bas > simdi) {
    return {durum: "baslamadi", etiket: "henüz başlamadı", vurgula: true};
  }
  if (!n.status) {
    return {durum: "bilinmiyor", etiket: "", vurgula: false};
  }
  // "yururlukte" yazmak bilgi tasimiyordu - Aktif NOTAM listesindeki HER
  // kart zaten yururlukte. Yerine kontrolorun gercekten merak ettigi sey:
  // ne kadar kaldi. effective_end bos olan NOTAM kalici, "süresiz".
  return {
    durum: "yururlukte",
    etiket: isNaN(bit) ? "süresiz" : window.ltfjKalanSure(bit - simdi),
    vurgula: false,
  };
};

// Milisaniye farkini kisa, okunur bir kalan sureye cevirir. Mutlak saat
// yerine GORECELI sure yaziyoruz: sayfada saatler yerel, NOTAM verisi UTC -
// "16:00'da bitiyor" hangi saat dilimi oldugu belirtilmeden yaniltici olur,
// "6 sa kaldı" ise saat diliminden bagimsiz dogru.
// ESIK AYARDAN TURETILIYOR, elle yazilmiyor: senkron araliginin iki
// katini gecmisse bir senkron kacmis demektir (bkz. ltfj_ayarlar.
// notam_bayat_saat). Eskiden burada "12 * 3600 * 1000" sabiti vardi ve
// yaninda "ayarlarda 6 saat" diye bir yorum duruyordu - ayar degisince
// sabit yerinde kalir, esik 2x yerine 4x olurdu.
var NOTAM_BAYAT_MS = @@notam_bayat_saat@@ * 3600 * 1000;

window.ltfjKalanSure = function (ms) {
  "use strict";
  var dk = Math.floor(ms / 60000);
  if (dk < 1) return "birazdan bitiyor";
  if (dk < 60) return dk + " dk kaldı";
  var saat = Math.floor(dk / 60);
  if (saat < 48) return saat + " sa kaldı";
  return Math.floor(saat / 24) + " gün kaldı";
};
