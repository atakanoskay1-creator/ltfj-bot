
// ---- CANLI GUNCELLEME: sayfa yeniden yuklenmeden yeni veri -----------------
// Baslik betigi (yeniVeriVarMi) sunucudaki sayfanin DEGISTIGINI gorunce
// yeni HTML'i buraya verir. Burada sunucunun urettigi VERI BOLGELERI
// yerinde degistirilir; kabuk (sekmeler, NOTAM/LVO formlari, ATC Notes,
// yazilan girdiler, kaydirma konumu) oldugu gibi kalir.
//
// Donus degeri baslik betigine ne yapacagini soyler:
//   "uygulandi" - bolgeler degisti
//   "ayni"      - sunucudaki sayfa bu sayfayla ayni uretimden
//   "bekle"     - kullanici degisecek bolgenin icinde yaziyor ya da bir
//                 pencere acik; bir sonraki kontrolde yeniden denenir
//   "yukle"     - yapi uyusmuyor (sayfa sablonu degismis): yerinde
//                 guncelleme GUVENLI DEGIL, eski yol (yeniden yukleme)
(function () {
  "use strict";
  if (!window.DOMParser) { return; }

  // Sunucunun her calismada yeniden urettigi bolgeler. Icerikleri
  // (innerHTML) yenisiyle degistirilir; ogenin KENDISI yerinde kalir -
  // uzerindeki gozlemciler (yapiskan serit) ve id'ler bozulmaz.
  var BOLGELER = [
    ".durum-bandi > .durum-blok",
    "#su-an",
    ".veri-kaynak",
    "#ozet-serit",
    "#panel-durum",
    "#panel-beklenti",
    "#panel-istatistik",
    "#lvo-fark-metar-taf",
    ".vfr-panel"
  ];
  // Yalnizca oznitelikleri degisen ogeler (icerigini istemci dolduruyor).
  var OZNITELIKLER = [
    ["html", ["data-gun-dogumu", "data-gun-batimi"]],
    ["#ust-durum", ["data-gozlem"]],
    ["#veri-metar", ["data-zaman"]],
    ["#veri-taf", ["data-zaman"]],
    ["#vfr-sekme", ["class", "title"]]
  ];

  function sec(kok, s) { return s === "html" ? kok.documentElement : kok.querySelector(s); }

  function yaziyorMu(bolge) {
    var odak = document.activeElement;
    return !!(odak && bolge.contains(odak) &&
              /^(INPUT|TEXTAREA|SELECT)$/.test(odak.tagName));
  }

  function acikPencereVarMi(bolge) {
    var ortuler = bolge.querySelectorAll(".modal-ortu");
    for (var i = 0; i < ortuler.length; i++) {
      if (!ortuler[i].hasAttribute("hidden")) { return true; }
    }
    return false;
  }

  // Kullanicinin actigi / kapattigi <details> bolumleri degisimden sonra
  // AYNI kalir. Once ayni sirada ayni sayida bolum varsa siraya gore,
  // yoksa ozet satirinin metnine gore eslestirilir.
  function ozetMetni(d) {
    var s = d.querySelector("summary");
    return s ? (s.textContent || "").replace(/\s+/g, " ").trim() : "";
  }
  function detayDurumu(bolge) {
    return Array.prototype.map.call(bolge.querySelectorAll("details"), function (d) {
      return {acik: d.open, ozet: ozetMetni(d)};
    });
  }
  function detayGeriYukle(bolge, eski) {
    var yeni = bolge.querySelectorAll("details");
    Array.prototype.forEach.call(yeni, function (d, i) {
      var e = null;
      if (yeni.length === eski.length) { e = eski[i]; }
      else {
        var ozet = ozetMetni(d);
        for (var j = 0; j < eski.length; j++) {
          if (eski[j].ozet === ozet) { e = eski[j]; break; }
        }
      }
      if (e && d.open !== e.acik) { d.open = e.acik; }
    });
  }

  window.ltfjCanliUygula = function (metin) {
    var yeniBelge;
    try { yeniBelge = new DOMParser().parseFromString(metin, "text/html"); }
    catch (e) { return "yukle"; }
    if (!yeniBelge || !yeniBelge.getElementById("ust-durum")) { return "yukle"; }

    // 1) Yapi ayni mi? Bir bolge bir tarafta var, digerinde yoksa sablon
    //    degismis demektir - yerinde guncelleme yapilmaz.
    var ciftler = [];
    for (var i = 0; i < BOLGELER.length; i++) {
      var a = document.querySelector(BOLGELER[i]);
      var b = yeniBelge.querySelector(BOLGELER[i]);
      if (!a !== !b) { return "yukle"; }
      if (a) { ciftler.push([a, b]); }
    }

    // 2) Ayni uretim mi? Sayfa damgasi (veri-kaynak: "MGM · sayfa ...")
    //    ve gozlem damgasi ayniysa degistirecek bir sey yok.
    var eskiGozlem = document.getElementById("ust-durum").getAttribute("data-gozlem");
    var yeniGozlem = yeniBelge.getElementById("ust-durum").getAttribute("data-gozlem");
    var eskiTaf = (document.getElementById("veri-taf") || {getAttribute: function () { return ""; }})
                    .getAttribute("data-zaman");
    var yeniTafEl = yeniBelge.getElementById("veri-taf");
    var yeniTaf = yeniTafEl ? yeniTafEl.getAttribute("data-zaman") : "";
    var kaynakA = document.querySelector(".veri-kaynak");
    var kaynakB = yeniBelge.querySelector(".veri-kaynak");
    if (eskiGozlem === yeniGozlem && kaynakA && kaynakB &&
        kaynakA.innerHTML === kaynakB.innerHTML) { return "ayni"; }

    // 3) Kullaniciyi bolmeyelim.
    for (var k = 0; k < ciftler.length; k++) {
      if (yaziyorMu(ciftler[k][0]) || acikPencereVarMi(ciftler[k][0])) { return "bekle"; }
    }

    // 4) Degistir.
    if (window.ltfjToggleSustur) { window.ltfjToggleSustur(); }
    ciftler.forEach(function (c) {
      var eski = c[0], yeni = c[1];
      if (eski.innerHTML === yeni.innerHTML) { return; }
      var detay = detayDurumu(eski);
      eski.innerHTML = yeni.innerHTML;
      detayGeriYukle(eski, detay);
    });
    OZNITELIKLER.forEach(function (o) {
      var a = sec(document, o[0]), b = sec(yeniBelge, o[0]);
      if (!a || !b) { return; }
      o[1].forEach(function (ad) {
        var d = b.getAttribute(ad);
        if (d === null) { a.removeAttribute(ad); }
        else if (a.getAttribute(ad) !== d) { a.setAttribute(ad, d); }
      });
    });

    // 5) Bolgelere bagli istemci isleri.
    var farkBos = document.getElementById("lvo-fark-bos");
    if (farkBos) {
      farkBos.hidden = document.querySelectorAll(
        "#lvo-fark-metar-taf li, #lvo-fark-rvr-liste li").length > 0;
    }
    [window.ltfjBaslikTazele, window.ltfjGrafikIpucuKur,
     window.ltfjNotamYenile, window.ltfjLvoNotamYenile].forEach(function (f) {
      if (typeof f === "function") { try { f(); } catch (e) {} }
    });

    // 6) Ne degisti? Yeni gozlemde hareket betigi degisen olculeri
    //    vurgular ve duyurur; yalnizca TAF yenilendiyse kisa bir duyuru.
    if (eskiGozlem !== yeniGozlem && window.ltfjHareketKarsilastir) {
      window.ltfjHareketKarsilastir(true);
    } else if (eskiTaf !== yeniTaf && yeniTaf && window.ltfjDuyur) {
      var d = new Date(yeniTaf);
      var ik = function (x) { return (x < 10 ? "0" : "") + x; };
      window.ltfjDuyur("Yeni TAF" + (isNaN(d) ? "" :
                       " · " + ik(d.getUTCHours()) + ":" + ik(d.getUTCMinutes()) + "Z"),
                       "Sayfa yenilenmeden güncellendi");
    }
    return "uygulandi";
  };
})();
