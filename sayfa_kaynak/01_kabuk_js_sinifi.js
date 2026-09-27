
  /* SATIR ICI ve GOVDE CIZILMEDEN ONCE olmak ZORUNDA: paneller varsayilan
     gorunur durumda cizilir (JS'siz tarayici icin). .js sinifini burada
     eklemezsek acilista tum paneller bir kare gorunup sonra kaybolur.
     Kayitli sekme de burada okunur ki dogru panel ILK karede acik olsun. */
  (function () {
    var k = document.documentElement;
    k.className += " js";
    var gecerli = ["durum", "beklenti", "istatistik", "lvo", "notam"];
    var s = "durum";
    try {
      var v = localStorage.getItem("ltfj-sekme");
      if (gecerli.indexOf(v) !== -1) { s = v; }
    } catch (e) {}          /* gizli sekmede localStorage atabilir */
    k.setAttribute("data-sekme", s);

    /* GECE = KOYU TEMA. Gun dogumu/batimi LTFJ icin GERCEKTEN
       hesaplanmis (ltfj_pist._gunes_saatleri); uydurma bir "aksam
       oldu" tahmini degil. Kullanicinin ACIK tercihi (data-theme)
       varsa ona DOKUNULMAZ - bu yuzden yalnizca oznitelik yokken
       yaziliyor. Karar ISTEMCIDE veriliyor cunku sayfa bir vardiya
       boyunca acik kalabiliyor; sunucuda gomulu bir "gunduz" etiketi
       saat 21:00'de yalan olurdu. */
    try {
      var dogus = Date.parse(k.getAttribute("data-gun-dogumu") || "");
      var batim = Date.parse(k.getAttribute("data-gun-batimi") || "");
      if (!isNaN(dogus) && !isNaN(batim) && !k.getAttribute("data-theme")) {
        var t = Date.now();
        k.setAttribute("data-faz", (t >= dogus && t < batim) ? "gunduz" : "gece");
        if (t < dogus || t >= batim) { k.setAttribute("data-theme", "dark"); }
      }
    } catch (e) {}
  })();
