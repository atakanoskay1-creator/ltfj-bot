
// ---- HAREKET: yalnizca bilgi tasiyan hareket ------------------------------
// Sayfa statik; yeni gozlem geldiginde kendini YENIDEN YUKLUYOR (bkz.
// baslik betigi, yeniVeriVarMi). "Ne degisti?" sorusunun cevabi bu yuzden
// ancak TARAYICIDA verilebilir: son gorulen gozlemin damgasi ve degerleri
// localStorage'da tutulur, sayfa YENI bir gozlemle acilinca:
//   - degeri degisen olcu bir kez vurgulanir (olcu-degisti),
//   - esik bandina (sinirli / esik alti) YENI giren olcu tek seferlik bir
//     cerceve alir (esik-girdi),
//   - ruzgar oku onceki yonden yeni yone doner.
// Ayni gozlem yeniden yuklenirse HICBIR SEY hareket etmez. localStorage
// yoksa/atarsa (gizli sekme) sayfa aynen, hareketsiz calisir.
// prefers-reduced-motion'da hicbir animasyon baslatilmaz.
(function () {
  "use strict";
  var kok = document.documentElement;
  var azalt = !!(window.matchMedia &&
                 window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  function tekSefer(el, sinif) {
    if (azalt || !el) { return; }
    el.classList.remove(sinif);
    void el.offsetWidth;                      // ayni sinifla yeniden baslat
    el.classList.add(sinif);
    el.addEventListener("animationend", function bitti() {
      el.classList.remove(sinif);
      el.removeEventListener("animationend", bitti);
    });
  }
  window.ltfjTekSeferHareket = tekSefer;

  // -- Sekme gecisi: yalnizca KULLANICI sekme degistirince belirme.
  var cubuk = document.querySelector(".sekme-cubugu");
  if (cubuk && !azalt) {
    cubuk.addEventListener("click", function (e) {
      if (e.target.closest && e.target.closest(".sekme")) { kok.classList.add("sekme-gecis"); }
    });
    cubuk.addEventListener("keydown", function () { kok.classList.add("sekme-gecis"); });
  }

  // -- Katlanir bolumler: acilinca icerik belirir. "toggle" olayi baloncuk
  // yapmaz; yakalama asamasinda dinleniyor. Tarayici BASTAN acik gelen
  // <details> icin de yukleme sirasinda "toggle" atiyor - o ilk dalga
  // kullanicinin actigi bir sey degil, sayfa yuklenene kadar yok sayiliyor.
  if (!azalt) {
    var togglHazir = false;
    window.addEventListener("load", function () {
      setTimeout(function () { togglHazir = true; }, 150);
    });
    document.addEventListener("toggle", function (e) {
      var d = e.target;
      if (togglHazir && d && d.tagName === "DETAILS" && d.open) { tekSefer(d, "acildi"); }
    }, true);
  }

  // -- Degisen olcu / esik girisi / ruzgar oku
  var ANAHTAR = "ltfj-son-gozlem";
  var durumEl = document.getElementById("ust-durum");
  var gozlem = durumEl ? durumEl.getAttribute("data-gozlem") : null;
  if (!gozlem) { return; }

  function metin(el) {
    var d = el.querySelector(".hero-deger") || el;
    return (d.textContent || "").replace(/\s+/g, " ").trim();
  }

  var simdiki = {gozlem: gozlem, degerler: {}, bantlar: {}, yon: null};
  var olcuEl = {};
  Array.prototype.forEach.call(document.querySelectorAll("[data-olcu]"), function (el) {
    var k = el.getAttribute("data-olcu");
    olcuEl[k] = el;
    simdiki.degerler[k] = metin(el);
    simdiki.bantlar[k] = el.getAttribute("data-bant") || "";
  });
  var okG = document.querySelector(".pd-ok-g");
  if (okG) {
    var y = parseFloat(okG.getAttribute("data-yon"));
    simdiki.yon = isNaN(y) ? null : y;
  }

  var onceki = null;
  try { onceki = JSON.parse(localStorage.getItem(ANAHTAR) || "null"); } catch (e) { onceki = null; }
  try { localStorage.setItem(ANAHTAR, JSON.stringify(simdiki)); } catch (e) {}

  // Ilk ziyaret ya da AYNI gozlem: karsilastirilacak bir degisim yok.
  if (!onceki || !onceki.gozlem || onceki.gozlem === gozlem) { return; }

  Object.keys(simdiki.degerler).forEach(function (k) {
    var el = olcuEl[k];
    var eski = (onceki.degerler || {})[k];
    if (eski !== undefined && eski !== simdiki.degerler[k]) {
      tekSefer(el.querySelector(".hero-deger") || el, "olcu-degisti");
    }
    var bant = simdiki.bantlar[k];
    var eskiBant = (onceki.bantlar || {})[k];
    if ((bant === "dikkat" || bant === "uyari") && eskiBant !== undefined && eskiBant !== bant) {
      tekSefer(el, "esik-girdi");
    }
  });

  // Ruzgar oku: onceki yonden yeni yone, KISA yoldan (en fazla 180 derece).
  // CSS transform, SVG'nin transform ozniteliginin YERINE gecer; son durum
  // oznitelikle ayni aciya oturur.
  if (okG && !azalt && onceki.yon != null && simdiki.yon != null && onceki.yon !== simdiki.yon) {
    var fark = ((simdiki.yon - onceki.yon) % 360 + 540) % 360 - 180;
    var hedef = simdiki.yon, bas = hedef - fark;
    okG.style.transformBox = "view-box";
    okG.style.transformOrigin = "60px 60px";
    okG.style.transform = "rotate(" + bas + "deg)";
    void okG.getBoundingClientRect();
    okG.style.transition = "transform 600ms cubic-bezier(.2,.7,.2,1)";
    okG.style.transform = "rotate(" + hedef + "deg)";
  }
})();
