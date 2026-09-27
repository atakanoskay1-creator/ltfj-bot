
(function () {
  "use strict";
  // VFR sekmesi/paneli TAMAMEN statik render edilir (bkz. ltfj_vfr.py) -
  // burada sadece acma/kapama var, hicbir fetch() yapilmaz.
  var sekme = document.getElementById("vfr-sekme");
  var ortu = document.getElementById("vfr-panel-ortu");
  var kapat = document.getElementById("vfr-panel-kapat");
  if (!sekme || !ortu) return;
  sekme.addEventListener("click", function () { ortu.hidden = false; });
  if (kapat) kapat.addEventListener("click", function () { ortu.hidden = true; });
  ortu.addEventListener("click", function (e) { if (e.target === ortu) ortu.hidden = true; });
})();
