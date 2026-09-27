
(function () {
  "use strict";
  // ATC Notes, NOTAM/METAR'dan TAMAMEN ayrı, bağımsız bir modül - bu script
  // yukarıdaki NOTAM script'iyle hiçbir değişken/durum PAYLAŞMAZ. Okuma/
  // yazma doğrudan Firebase Realtime Database REST API'sine fetch() ile
  // yapılır (ayrı bir SDK/CDN gerekmez). Güvenlik (uzunluk limitleri,
  // "created_at" alanının GERÇEKTEN sunucu saati olması) Firebase Realtime
  // Database Rules ile sağlanır (bkz. firebase-rules.json) - bu script
  // sadece kullanıcı deneyimi için AYRICA istemci tarafında da doğrular,
  // ama gerçek güvenlik sınırı sunucu (Rules) tarafındadır.
  var DB_URL = @@atc_notes_db_url@@;
  var YASAM_SURESI_MS = 48 * 3600 * 1000;
  var POLL_ARALIGI_MS = 45000;
  var AUTHOR_MAKS = 100;
  var TEXT_MAKS = 1000;

  var listeEl = document.getElementById("atc-notes-liste");
  var modalEl = document.getElementById("atc-not-modal");
  var yazanEl = document.getElementById("atc-not-yazan");
  var metinEl = document.getElementById("atc-not-metin");
  var hataEl = document.getElementById("atc-not-hata");
  var kaydetBtn = document.getElementById("atc-not-kaydet");
  var fabEl = document.getElementById("atc-fab");
  var fabRozetEl = document.getElementById("atc-fab-rozet");
  var panelOrtuEl = document.getElementById("atc-panel-ortu");
  var sonGonderimZamani = 0;

  function tabanUrl() {
    var taban = DB_URL;
    while (taban.length && taban.charAt(taban.length - 1) === "/") {
      taban = taban.slice(0, -1);
    }
    return taban + "/atc_notes.json";
  }

  function notKarti(veri) {
    var kart = document.createElement("div");
    kart.className = "notam-kart";

    var ust = document.createElement("div");
    ust.className = "notam-ust";
    var yazan = document.createElement("span");
    yazan.className = "notam-no";
    yazan.textContent = veri.author || "?";
    ust.appendChild(yazan);
    var zamanEl = document.createElement("span");
    zamanEl.className = "notam-durum";
    var d = new Date(veri.created_at);
    zamanEl.textContent = d.toISOString().slice(0, 16).replace("T", " ") + " UTC";
    ust.appendChild(zamanEl);
    kart.appendChild(ust);

    var metin = document.createElement("div");
    metin.className = "notam-cumle";
    metin.textContent = veri.text || "";
    kart.appendChild(metin);

    var kalanMs = veri.created_at + YASAM_SURESI_MS - Date.now();
    var kalanSaat = Math.max(0, Math.round(kalanMs / 3600000));
    var kalan = document.createElement("div");
    kalan.className = "atc-not-kalan";
    // Emoji DEGIL duz metin: burasi textContent, SVG konulamaz.
    kalan.textContent = "yaklaşık " + kalanSaat + " saat sonra otomatik silinecek";
    kart.appendChild(kalan);

    return kart;
  }

  function listeyiGoster(kayitlar) {
    var simdi = Date.now();
    var gecerliler = [];
    Object.keys(kayitlar || {}).forEach(function (id) {
      var n = kayitlar[id];
      if (!n || typeof n.created_at !== "number") return;
      if (simdi - n.created_at >= YASAM_SURESI_MS) return;   // suresi dolmus - gosterme
      gecerliler.push(n);
    });
    gecerliler.sort(function (a, b) { return b.created_at - a.created_at; });

    fabRozetEl.textContent = gecerliler.length > 99 ? "99+" : String(gecerliler.length);
    fabRozetEl.hidden = gecerliler.length === 0;

    listeEl.innerHTML = "";
    if (!gecerliler.length) {
      listeEl.textContent = "Aktif not yok.";
      return;
    }
    gecerliler.forEach(function (n) { listeEl.appendChild(notKarti(n)); });
  }

  function veriYukle() {
    if (!DB_URL) {
      listeEl.textContent = "ATC Notes şu anda yapılandırılmamış.";
      return;
    }
    fetch(tabanUrl() + "?_=" + Date.now())
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(listeyiGoster)
      .catch(function (err) {
        listeEl.textContent = "ATC Notes şu anda yüklenemiyor.";
        console.error("[atc-notes] okuma hatası:", err);
      });
  }

  function panelAc() {
    panelOrtuEl.hidden = false;
    veriYukle();
  }

  function panelKapat() {
    panelOrtuEl.hidden = true;
  }

  function modalAc() {
    yazanEl.value = "";
    metinEl.value = "";
    hataEl.textContent = "";
    modalEl.hidden = false;
    yazanEl.focus();
  }

  function modalKapat() {
    modalEl.hidden = true;
  }

  function notKaydet() {
    var yazan = yazanEl.value.trim();
    var metin = metinEl.value.trim();

    if (!DB_URL) { hataEl.textContent = "ATC Notes şu anda yapılandırılmamış."; return; }
    if (!yazan) { hataEl.textContent = "Adınızı girin."; return; }
    if (yazan.length > AUTHOR_MAKS) { hataEl.textContent = "Ad en fazla " + AUTHOR_MAKS + " karakter olabilir."; return; }
    if (!metin) { hataEl.textContent = "Not boş olamaz."; return; }
    if (metin.length > TEXT_MAKS) { hataEl.textContent = "Not en fazla " + TEXT_MAKS + " karakter olabilir."; return; }
    // basit debounce - art arda hizli gonderimi onler (gercek rate limit
    // sunucu tarafinda yok, bu sadece yanlislikla cift tiklama/spam icin)
    if (Date.now() - sonGonderimZamani < 3000) { return; }

    hataEl.textContent = "";
    kaydetBtn.disabled = true;
    fetch(tabanUrl(), {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({author: yazan, text: metin, created_at: {".sv": "timestamp"}}),
    })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function () {
        sonGonderimZamani = Date.now();
        modalKapat();
        veriYukle();
      })
      .catch(function (err) {
        hataEl.textContent = "Not kaydedilemedi, tekrar deneyin.";
        console.error("[atc-notes] yazma hatası:", err);
      })
      .finally(function () { kaydetBtn.disabled = false; });
  }

  fabEl.addEventListener("click", panelAc);
  document.getElementById("atc-panel-kapat").addEventListener("click", panelKapat);
  panelOrtuEl.addEventListener("click", function (e) { if (e.target === panelOrtuEl) panelKapat(); });

  document.getElementById("atc-not-ekle-btn").addEventListener("click", modalAc);
  document.getElementById("atc-not-iptal").addEventListener("click", modalKapat);
  kaydetBtn.addEventListener("click", notKaydet);
  modalEl.addEventListener("click", function (e) { if (e.target === modalEl) modalKapat(); });

  // Rozet (badge) sayisi icin arka planda da veri cekilir - panel kapaliyken
  // bile FAB uzerindeki aktif-not sayisi guncel kalsin diye.
  veriYukle();
  setInterval(veriYukle, POLL_ARALIGI_MS);
})();
