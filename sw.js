// LTFJ push bildirimi servis çalışanı.
//
// TEK işi var: gelen bir push olayını (bkz. ltfj_push.py::_govde_kur) OS
// bildirimine çevirmek, ve tıklanınca siteyi açmak. Sayfanın kendisini
// önbelleğe almaz, offline çalışma sağlamaz - bot her 15 dakikada bir yeni
// bir index.html ürettiği için "bayat önbellek" riski, faydasından ağır
// basar (bkz. ltfj_sayfa.py "Yenile" butonunun cache-buster mantığı).

self.addEventListener("push", function (event) {
  var veri = {};
  try {
    veri = event.data ? event.data.json() : {};
  } catch (e) {
    veri = {};
  }

  var baslik = veri.baslik || "LTFJ";
  var secenekler = {
    body: veri.govde || "",
    icon: "panel_icon.png",
    badge: "panel_icon.png",
    tag: veri.etiket || undefined,
    // ayni etiketli bir sonraki bildirim onceki gorunumun yerine gecsin -
    // ama zaten gorulmus bir bildirimi SESSIZCE guncellemesin.
    renotify: !!veri.etiket,
    data: { url: veri.url || "./" },
  };

  event.waitUntil(self.registration.showNotification(baslik, secenekler));
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  var url = (event.notification.data && event.notification.data.url) || "./";

  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (pencereler) {
      for (var i = 0; i < pencereler.length; i++) {
        if ("focus" in pencereler[i]) return pencereler[i].focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
