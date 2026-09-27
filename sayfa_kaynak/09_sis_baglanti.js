
(function () {
  "use strict";
  // Istatistiksel sis olasiligi kartindaki "Iki modelin baglantisini gor"
  // butonu - statik bir PNG'yi (sis_model_baglantisi.png) modalda gosterir,
  // hicbir fetch() yapilmaz.
  var btn = document.getElementById("sis-model-diyagram-btn");
  var ortu = document.getElementById("sis-model-modal");
  var kapat = document.getElementById("sis-model-modal-kapat");
  if (!btn || !ortu) return;
  btn.addEventListener("click", function () { ortu.hidden = false; });
  if (kapat) kapat.addEventListener("click", function () { ortu.hidden = true; });
  ortu.addEventListener("click", function (e) { if (e.target === ortu) ortu.hidden = true; });
})();
