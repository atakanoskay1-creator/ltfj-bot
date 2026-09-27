
(function () {
  "use strict";
  // Web Push (tarayici bildirimleri) - SPECI/TAF/duzeltme/renk kotulesmesi
  // ve yeni NOTAM icin (bkz. ltfj_push.py). Abonelik ATC Notes ile AYNI
  // Firebase Realtime Database'e, "push_abonelikler" path'ine, DOGRUDAN
  // fetch() ile yazilir - ayri bir SDK/CDN gerekmez. VAPID_PUBLIC_KEY GIZLI
  // DEGIL (bkz. ltfj_ayarlar.py::push); bos ise buton hic gosterilmez.
  var VAPID_PUBLIC_KEY = @@push_vapid_public_key@@;
  var DB_URL = @@atc_notes_db_url@@;
  var btn = document.getElementById("bildirim-izin-btn");
  if (!btn || !VAPID_PUBLIC_KEY) return;

  function destekleniyor_mu() {
    return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  }

  function tabanUrl() {
    var taban = DB_URL;
    while (taban.length && taban.charAt(taban.length - 1) === "/") {
      taban = taban.slice(0, -1);
    }
    return taban + "/push_abonelikler";
  }

  function urlBase64ToUint8Array(base64String) {
    var dolgu = "=".repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + dolgu).replace(/-/g, "+").replace(/_/g, "/");
    var ham = atob(base64);
    var dizi = new Uint8Array(ham.length);
    for (var i = 0; i < ham.length; i++) dizi[i] = ham.charCodeAt(i);
    return dizi;
  }

  // Guvenlik icin degil - sadece "ayni endpoint hep ayni anahtara yazsin"
  // (yeniden abone olma cakisma/yinelenen kayit uretmesin) icin senkron,
  // basit bir hash. crypto.subtle.digest promise dondurdugu icin burada
  // gereksiz karmasiklik katardi.
  function idUret(endpoint) {
    var h = 2166136261;
    for (var i = 0; i < endpoint.length; i++) {
      h ^= endpoint.charCodeAt(i);
      h = (h * 16777619) >>> 0;
    }
    return "p" + h.toString(16) + endpoint.length;
  }

  // Ikon ve metin ayri dugum: yalnizca metin degisir, SVG yerinde kalir.
  var ZIL = @@ikon_zil_js@@;
  var ZIL_KAPALI = @@ikon_zil_kapali_js@@;
  var btnIkon = document.getElementById("bildirim-ikon");
  var btnMetin = document.getElementById("bildirim-metin");

  function durumGoster(durum) {
    btn.hidden = false;
    var DURUMLAR = {
      "acik":          ["Bildirimler açık",            false, ZIL],
      "reddedildi":    ["İzin verilmedi",              true,  ZIL_KAPALI],
      "beklemede":     ["…",                           true,  ZIL],
      "hata":          ["Bildirimler (tekrar dene)",   false, ZIL],
      "varsayilan":    ["Bildirimlere izin ver",       false, ZIL]
    };
    if (durum === "desteklenmiyor") { btn.hidden = true; return; }
    var d = DURUMLAR[durum] || DURUMLAR["varsayilan"];
    if (btnMetin) { btnMetin.textContent = d[0]; }
    if (btnIkon) { btnIkon.innerHTML = d[2]; }
    btn.disabled = d[1];
  }

  // Tarayicidaki abonelik TEK BASINA yetmez - sunucu (ltfj_push.py) SADECE
  // Firebase'deki kayitlara gonderir. fetch() HTTP 401/403'te REDDETMEZ, bu
  // yuzden yanit.ok ACIKCA kontrol edilir: aksi halde kurallar yazmayi
  // engellese bile buton "Bildirimler acik" der, kullanici abone oldugunu
  // sanir ama sunucuda hicbir kayit olmaz (21.09.2026 TAF'inda bu oldu).
  function abonelikKaydet(sub) {
    var veri = sub.toJSON();
    if (!DB_URL) return Promise.reject(new Error("DB_URL tanımlı değil"));
    return fetch(tabanUrl() + "/" + idUret(veri.endpoint) + ".json", {
      method: "PUT",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        endpoint: veri.endpoint, keys: veri.keys,
        created_at: {".sv": "timestamp"},
      }),
    }).then(function (yanit) {
      if (!yanit.ok) {
        throw new Error("abonelik sunucuya kaydedilemedi: HTTP " + yanit.status +
                        " (Firebase kuralları push_abonelikler yazmaya izin veriyor mu?)");
      }
      return yanit;
    });
  }

  function aboneOl() {
    if (Notification.permission === "denied") { durumGoster("reddedildi"); return; }
    durumGoster("beklemede");
    navigator.serviceWorker.register("sw.js").then(function () {
      // subscribe() aktif (activate asamasini gecmis) bir servis calisani
      // ister - register()'in dondurdugu kayit "installing" durumunda
      // olabilir, bu yuzden hazir olana kadar bekleyen .ready kullanilir.
      return navigator.serviceWorker.ready;
    }).then(function (kayit) {
      return Notification.requestPermission().then(function (izin) {
        if (izin !== "granted") { durumGoster("reddedildi"); throw new Error("izin verilmedi"); }
        return kayit.pushManager.getSubscription().then(function (mevcut) {
          return mevcut || kayit.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
          });
        });
      });
    }).then(function (sub) {
      return abonelikKaydet(sub).then(function () { durumGoster("acik"); });
    }).catch(function (err) {
      console.error("[push] abone olma hatası:", err);
      if (Notification.permission !== "denied") durumGoster("hata");
    });
  }

  function baslangicDurumu() {
    if (!destekleniyor_mu()) { durumGoster("desteklenmiyor"); return; }
    if (Notification.permission === "denied") { durumGoster("reddedildi"); return; }
    navigator.serviceWorker.getRegistration().then(function (kayit) {
      return kayit ? kayit.pushManager.getSubscription() : null;
    }).then(function (sub) {
      durumGoster(sub ? "acik" : "kapali");
    }).catch(function () { durumGoster("kapali"); });
  }

  btn.addEventListener("click", aboneOl);
  baslangicDurumu();
})();
