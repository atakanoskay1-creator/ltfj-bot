
(function () {
  "use strict";
  // Trend grafiklerinde imlecin/parmagin altindaki noktanin saatini ve
  // degerini gosterir. Fare: uzerine gelince gorunur, ayrilinca kaybolur.
  // Dokunmatik: basili tutup surukledikce gosterir, parmak kalkinca kaybolur.
  // Nokta verisi sayfa uretilirken data-noktalar'a gomulu - hicbir fetch()
  // yapilmaz (bkz. ltfj_sayfa._grafik_blogu).
  var kutular = document.querySelectorAll(".grafik-kutu");
  Array.prototype.forEach.call(kutular, function (kutu) {
    var noktalar;
    try {
      noktalar = JSON.parse(kutu.getAttribute("data-noktalar") || "[]");
    } catch (e) {
      return;
    }
    if (!noktalar.length) return;

    var sarmal = kutu.querySelector(".grafik-sarmal");
    var imlec = kutu.querySelector(".grafik-imlec");
    var nokta = kutu.querySelector(".grafik-nokta");
    var balon = kutu.querySelector(".grafik-balon");
    if (!sarmal || !imlec || !nokta || !balon) return;
    var basili = false;

    function gizle() {
      basili = false;
      imlec.hidden = true;
      nokta.hidden = true;
      balon.hidden = true;
    }

    function goster(olay) {
      var alan = sarmal.getBoundingClientRect();
      if (!alan.width) return;
      var oran = (olay.clientX - alan.left) / alan.width;
      var enYakin = noktalar[0], enKisa = Infinity;
      for (var i = 0; i < noktalar.length; i++) {
        var uzaklik = Math.abs(noktalar[i].x - oran);
        if (uzaklik < enKisa) { enKisa = uzaklik; enYakin = noktalar[i]; }
      }
      var px = enYakin.x * alan.width;
      imlec.style.left = px + "px";
      nokta.style.left = px + "px";
      nokta.style.top = (enYakin.y * alan.height) + "px";
      balon.textContent = enYakin.s + " · " + enYakin.d;
      imlec.hidden = false;
      nokta.hidden = false;
      balon.hidden = false;
      // balon grafik kutusunun ICINDE kalsin: yatayda kenarlarda kirpilmasin,
      // dikeyde noktanin TERS tarafina gecsin (noktayi ve baslik satirini
      // kapatmasin).
      var genislik = balon.offsetWidth;
      balon.style.left = Math.max(0, Math.min(px - genislik / 2, alan.width - genislik)) + "px";
      balon.style.top = (enYakin.y < 0.5 ? alan.height - balon.offsetHeight : 0) + "px";
    }

    sarmal.addEventListener("pointerenter", function (e) {
      if (e.pointerType === "mouse") goster(e);
    });
    sarmal.addEventListener("pointermove", function (e) {
      if (e.pointerType === "mouse" || basili) goster(e);
    });
    sarmal.addEventListener("pointerdown", function (e) {
      if (e.pointerType !== "mouse") { basili = true; goster(e); }
    });
    sarmal.addEventListener("pointerleave", gizle);
    sarmal.addEventListener("pointerup", function (e) {
      if (e.pointerType !== "mouse") gizle();
    });
    sarmal.addEventListener("pointercancel", gizle);
  });
})();
