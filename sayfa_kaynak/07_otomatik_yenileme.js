
(function () {
  "use strict";
  // Sayfanin METAR/TAF/pist govdesi bot her calistiginda YENIDEN uretilen
  // statik bir dosyadir (canli bir fetch() ile guncellenmez) - "Yenile"
  // butonu bu yuzden butun sayfayi, tarayici onbellegini atlayacak sekilde
  // (cache-buster query param) yeniden yukler; boylece NOTAM/ATC Notes
  // bolumleri de en guncel notam_veri.json/Firebase verisiyle acilir.
  document.getElementById("sayfa-yenile-btn").addEventListener("click", function () {
    window.location.href = window.location.pathname + "?_=" + Date.now();
  });
})();
