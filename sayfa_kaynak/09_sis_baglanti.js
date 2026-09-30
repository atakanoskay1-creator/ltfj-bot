(function () {
  "use strict";
  // Istatistiksel sis olasiligi kartindaki "Iki modelin baglantisini gor"
  // butonu - statik bir PNG'yi (sis_model_baglantisi.png) modalda gosterir,
  // hicbir fetch() yapilmaz. Dinleyici BELGEDE: kart canli guncellemede
  // yeniden yaziliyor (bkz. 12_canli.js).
  document.addEventListener("click", function (e) {
    var ortu = document.getElementById("sis-model-modal");
    if (!ortu || !e.target.closest) return;
    if (e.target.closest("#sis-model-diyagram-btn")) { ortu.hidden = false; return; }
    if (e.target.closest("#sis-model-modal-kapat") || e.target === ortu) { ortu.hidden = true; }
  });
})();
