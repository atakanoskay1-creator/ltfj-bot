(function () {
  "use strict";
  // VFR sekmesi/paneli TAMAMEN statik render edilir (bkz. ltfj_vfr.py) -
  // burada sadece acma/kapama var, hicbir fetch() yapilmaz.
  // Dinleyici BELGEDE (olay yetkilendirme): canli guncelleme panelin
  // icerigini yeniden yaziyor (bkz. 12_canli.js); dugmelere dogrudan
  // bagli dinleyiciler o anda kaybolurdu.
  document.addEventListener("click", function (e) {
    var ortu = document.getElementById("vfr-panel-ortu");
    if (!ortu || !e.target.closest) return;
    if (e.target.closest("#vfr-sekme")) { ortu.hidden = false; return; }
    if (e.target.closest("#vfr-panel-kapat") || e.target === ortu) { ortu.hidden = true; }
  });
})();
