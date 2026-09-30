
// ---- HAREKET: yalnizca bilgi tasiyan hareket ------------------------------
// Sayfa statik; yeni gozlem geldiginde kendini YENIDEN YUKLUYOR (bkz.
// baslik betigi, yeniVeriVarMi). "Ne degisti?" sorusunun cevabi bu yuzden
// ancak TARAYICIDA verilebilir: son gorulen gozlemin damgasi ve degerleri
// localStorage'da tutulur, sayfa YENI bir gozlemle acilinca:
//   - degeri degisen olcu bir kez vurgulanir (olcu-degisti),
//   - esik bandina (sinirli / esik alti) YENI giren olcu tek seferlik bir
//     cerceve alir (esik-girdi),
//   - ruzgar oku onceki yonden yeni yone doner.
// Ayni kiyas canli guncellemeden (12_canli.js) sonra da calisir.
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
    // Canli guncelleme <details> acik durumunu geri yuklerken de "toggle"
    // atiliyor - o da kullanicinin actigi bir sey degil.
    window.ltfjToggleSustur = function () {
      togglHazir = false;
      setTimeout(function () { togglHazir = true; }, 150);
    };
    document.addEventListener("toggle", function (e) {
      var d = e.target;
      if (togglHazir && d && d.tagName === "DETAILS" && d.open) { tekSefer(d, "acildi"); }
    }, true);
  }

  // -- Degisen olcu / esik girisi / ruzgar oku / yeni gozlem duyurusu.
  // Sayfa acilisinda VE canli guncellemeden sonra (bkz. 12_canli.js)
  // calisir: ikisinde de soru ayni - "son baktigimdan bu yana ne degisti?"
  var ANAHTAR = "ltfj-son-gozlem";

  function metin(el) {
    var d = el.querySelector(".hero-deger") || el;
    var kopya = d.cloneNode(true);
    // Onceki deger rozeti olcunun PARCASI degil - karsilastirmaya girmesin.
    Array.prototype.forEach.call(kopya.querySelectorAll(".olcu-onceki"),
                                 function (r) { r.parentNode.removeChild(r); });
    return (kopya.textContent || "").replace(/\s+/g, " ").trim();
  }

  function zulu(iso) {
    var d = new Date(iso || "");
    if (!iso || isNaN(d)) { return ""; }
    var ik = function (x) { return (x < 10 ? "0" : "") + x; };
    return ik(d.getUTCHours()) + ":" + ik(d.getUTCMinutes()) + "Z";
  }

  // Duyuru: yeni gozlem geldi (ya da son ziyaretten beri gelmis). Ekranin
  // ustunde birkac saniye durur; dokununca kapanir. role=status - ekran
  // okuyucu da duyar. Hareket azaltmada da GORUNUR (bilgi), yalnizca
  // kayarak girmez.
  function duyur(baslik, ayrinti) {
    var eski = document.getElementById("canli-duyuru");
    if (eski) { eski.parentNode.removeChild(eski); }
    var k = document.createElement("div");
    k.id = "canli-duyuru";
    k.className = "canli-duyuru";
    k.setAttribute("role", "status");
    var b = document.createElement("b");
    b.appendChild(document.createTextNode(baslik));
    k.appendChild(b);
    if (ayrinti) {
      var a = document.createElement("span");
      a.appendChild(document.createTextNode(ayrinti));
      k.appendChild(a);
    }
    document.body.appendChild(k);
    function kapat() {
      if (!k.parentNode) { return; }
      k.classList.add("kapaniyor");
      setTimeout(function () { if (k.parentNode) { k.parentNode.removeChild(k); } }, 300);
    }
    k.addEventListener("click", kapat);
    setTimeout(kapat, 8000);
  }
  window.ltfjDuyur = duyur;

  // Degisen olcunun ONCEKI degeri: hucrenin kosesinde kisa sure durur,
  // sonra kaybolur. Ara deger degil - gercekte gozlenmis bir onceki okuma.
  function oncekiRozeti(el, eskiDeger) {
    if (azalt || !el.querySelector(".hero-deger")) { return; }
    var var_ = el.querySelector(".olcu-onceki");
    if (var_) { var_.parentNode.removeChild(var_); }
    var r = document.createElement("span");
    r.className = "olcu-onceki";
    r.setAttribute("aria-hidden", "true");
    r.appendChild(document.createTextNode("önce " + eskiDeger));
    el.appendChild(r);
    r.addEventListener("animationend", function () {
      if (r.parentNode) { r.parentNode.removeChild(r); }
    });
  }

  function karsilastir(canli) {
    var durumEl = document.getElementById("ust-durum");
    var gozlem = durumEl ? durumEl.getAttribute("data-gozlem") : null;
    if (!gozlem) { return; }

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

    var degisen = 0;
    Object.keys(simdiki.degerler).forEach(function (k) {
      var el = olcuEl[k];
      var eski = (onceki.degerler || {})[k];
      if (eski !== undefined && eski !== simdiki.degerler[k]) {
        degisen++;
        tekSefer(el.querySelector(".hero-deger") || el, "olcu-degisti");
        oncekiRozeti(el, eski);
      }
      var bant = simdiki.bantlar[k];
      var eskiBant = (onceki.bantlar || {})[k];
      if ((bant === "dikkat" || bant === "uyari") && eskiBant !== undefined && eskiBant !== bant) {
        tekSefer(el, "esik-girdi");
      }
    });

    duyur("Yeni gözlem · " + zulu(gozlem),
          (canli ? "Sayfa yenilenmeden güncellendi" : "Son bakıştan bu yana") +
          (degisen ? " · " + degisen + " ölçü değişti" : " · ölçüler aynı"));

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
      okG.style.transition = "transform 1200ms cubic-bezier(.2,.7,.2,1)";
      okG.style.transform = "rotate(" + hedef + "deg)";
    }
  }
  window.ltfjHareketKarsilastir = karsilastir;
  karsilastir(false);
})();
