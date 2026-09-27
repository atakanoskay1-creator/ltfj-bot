
(function () {
  "use strict";
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
    });
  }

  var veri = null;
  var yaklasanBolumEl = document.getElementById("notam-yaklasan-bolum");
  var yaklasanEl = document.getElementById("notam-yaklasan-liste");
  var aktifEl = document.getElementById("notam-aktif-liste");
  var aktifQEl = document.getElementById("notam-aktif-q");
  var aktifKategoriEl = document.getElementById("notam-aktif-kategori");
  var aktifElemanEl = document.getElementById("notam-aktif-eleman");
  var aktifSiralamaEl = document.getElementById("notam-aktif-siralama");
  // Kategori artik bir <select> DEGIL cip grubu; secim DOM'da degil
  // burada tutuluyor. Cipler her veri yenilenisinde yeniden ciziliyor
  // ve o sirada bir <select>'in value'su gibi kendiliginden korunmazdi.
  var aktifKategori = "";
  var aktifSayiEl = document.getElementById("notam-aktif-sayi");
  var senkronEl = document.getElementById("notam-senkron-zamani");
  var sonucEl = document.getElementById("notam-arama-sonuc");
  var durumSelectEl = document.getElementById("notam-durum");

  var gecerlilik = window.ltfjNotamGecerlilik;

  // NOTAC'IN SIRASI. Kart eskiden tersten diziliyordu: once numara,
  // tip, Q kodu, kategori, BUTUN etiketler ve BUTUN etkilenen pistler
  // tek bir cip duvarinda; duz dil ozeti ise altta, kucuk gri yazida
  // ve her kartta tekrarlanan bir parantez uyarisiyla ("NOTAC otomatik
  // ozeti - hata icerebilir") beraber. 28 kartta o uyari 28 kez
  // yaziliyordu ve okunmasi gereken asil cumleyi bastiriyordu.
  //
  // Simdi: ust satir KIMLIK (numara + tip + kategori), sonra CUMLE -
  // kartin en buyuk ogesi, cunku okunan o -, sonra sessiz bir kunye
  // satiri (Q kodu, yururluk), en altta etiketler. Uyari kartta degil
  // BOLUM BASINDA, bir kez (bkz. .notam-not).
  function notamKarti(n) {
    var etiketler = (n.tags || []).concat(
      (n.affected_elements || []).map(function (e) { return e.ref; })
    ).filter(Boolean).map(function (t) {
      return '<span class="notam-etiket">' + esc(t) + "</span>";
    }).join("");
    var kategori = n.category_etiketi
      ? '<span class="notam-kategori">' + esc(n.category_etiketi) + "</span>" : "";
    var g = gecerlilik(n);
    // Cumle YOKSA ham E) govdesine duseriz - bos birakmak NOTAM'i
    // gorunmez kilmak demek olurdu.
    var cumle = esc(n.reading_short || n.text || "");
    // Yesil nokta SADECE su anda gercekten yururlukte olan NOTAM'a konur.
    var aktifNoktasi = g.durum === "yururlukte"
      ? '<span class="notam-aktif-nokta" title="Şu anda yürürlükte"></span>' : "";
    var kunye = [];
    if (n.q_code) kunye.push("Q " + esc(n.q_code));
    kunye.push(esc(kisaZaman(n.effective_start)) + " → " +
               esc(kisaZaman(n.effective_end)));
    return (
      '<div class="notam-kart">' +
      '<div class="notam-ust">' + aktifNoktasi +
      '<span class="notam-no">' + esc(n.number || "—") + "</span>" +
      window.ltfjNotamTipEtiketi(n) + kategori +
      '<span class="notam-durum' + (g.vurgula ? " notam-durum-gecmis" : "") + '">' +
      esc(g.etiket) + "</span></div>" +
      '<div class="notam-cumle">' + cumle + "</div>" +
      window.ltfjNotamIlgiliSatiri(n) +
      '<div class="notam-kunye">' + kunye.join(" · ") + "</div>" +
      (etiketler ? '<div class="notam-etiketler">' + etiketler + "</div>" : "") +
      "<details class=\"notam-ham\"><summary>Ham NOTAM metni</summary>" +
      '<div class="notam-metin">' + esc(n.text || "") + "</div></details>" +
      "</div>"
    );
  }

  // Kunyedeki tarihler ISO damga olarak basiliyordu
  // ("2026-08-28T07:11:00Z") - sayfadaki hicbir baska zaman o bicimde
  // degil ve tek basina kunye satirini iki katina cikariyordu.
  function kisaZaman(iso) {
    if (!iso) return "—";
    var d = new Date(iso);
    if (isNaN(d)) return iso;
    var ik = function (x) { return (x < 10 ? "0" : "") + x; };
    return ik(d.getUTCDate()) + "." + ik(d.getUTCMonth() + 1) + " " +
           ik(d.getUTCHours()) + ":" + ik(d.getUTCMinutes()) + "Z";
  }

  // Aktif listeye giren kayitlar: NOTAC'in son senkronda dondurduklerinden
  // suresi GERCEKTEN dolmamis olanlar. Senkron bayatlarsa (NOTAC erisilemez)
  // aradan gecen surede suresi biten bir NOTAM burada kalmaya devam
  // ederdi - tarih kontrolu bunu da kapatiyor.
  function yururluktekiler() {
    return (veri.aktif || []).filter(function (n) {
      return gecerlilik(n).durum === "yururlukte";
    }).sort(function (a, b) {
      return (a.number || "").localeCompare(b.number || "");
    });
  }

  function aktifFiltrele(liste) {
    var q = aktifQEl.value.trim().toLowerCase();
    var kat = aktifKategori;
    var eleman = aktifElemanEl.value;
    return liste.filter(function (n) {
      if (kat && n.category_etiketi !== kat) return false;
      if (eleman) {
        var refler = (n.affected_elements || []).map(function (e) { return e.ref; });
        if (refler.indexOf(eleman) === -1) return false;
      }
      if (q) {
        var alanlar = [n.number, n.text, n.reading_short, n.reading_long]
          .concat(n.tags || [])
          .concat((n.affected_elements || []).map(function (e) { return e.ref; }))
          .filter(Boolean).join(" ").toLowerCase();
        if (alanlar.indexOf(q) === -1) return false;
      }
      return true;
    });
  }

  // KAPALI MI? Uydurma degil - NOTAM'in KENDI soyledigi iki isaret:
  // (1) ICAO Q kodunun 4-5. harfleri "LC" (closed); (2) NOTAC'in
  // kendi verdigi "closure" etiketi. Ikisinden biri yetiyor: Q kodu
  // gelmeyen kayitlar var (45'te 3), etiket ise hepsinde var.
  function kapaliMi(n) {
    var kod = (n.q_code || "").toUpperCase();
    if (kod.length === 5 && kod.substring(3, 5) === "LC") return true;
    return (n.tags || []).indexOf("closure") !== -1;
  }

  function zamanSayisi(iso) {
    var t = Date.parse(iso || "");
    return isNaN(t) ? null : t;
  }

  // Eksik tarih HER ZAMAN SONA. Ne 0 ne Infinity: ikisi de kaydi bir
  // uca yapistirip "en yakin biten" ya da "en yeni" gibi gosterirdi.
  function tariheGore(a, b, alan, artan) {
    var x = zamanSayisi(a[alan]), y = zamanSayisi(b[alan]);
    if (x === null && y === null) return 0;
    if (x === null) return 1;
    if (y === null) return -1;
    return artan ? x - y : y - x;
  }

  function numarayaGore(a, b) {
    return (a.number || "").localeCompare(b.number || "");
  }

  function sirala(liste) {
    var mod = aktifSiralamaEl ? aktifSiralamaEl.value : "kapanis";
    var kopya = liste.slice();
    if (mod === "bitis") {
      kopya.sort(function (a, b) {
        return tariheGore(a, b, "effective_end", true) || numarayaGore(a, b);
      });
    } else if (mod === "yeni") {
      kopya.sort(function (a, b) {
        return tariheGore(a, b, "effective_start", false) || numarayaGore(a, b);
      });
    } else if (mod === "numara") {
      kopya.sort(numarayaGore);
    } else {
      // KAPANISLAR ONCE: yalnizca IKI obek (kapali / digerleri). Uc
      // katmanli bir "kapali > hizmet disi > oteki" sirasi yazmak,
      // NOTAC'in soylemedigi bir onem sirasi UYDURMAK olurdu.
      kopya.sort(function (a, b) {
        var fa = kapaliMi(a) ? 0 : 1, fb = kapaliMi(b) ? 0 : 1;
        return fa - fb || numarayaGore(a, b);
      });
    }
    return kopya;
  }

  function yaklasanGoster() {
    // Tarih kontrolu ISTEMCIDE yeniden yapiliyor: sayfa saatlerce acik
    // kalabilir ve bu arada bir NOTAM yururluge girer. Python'un yazdigi
    // liste o an dogruydu, simdi degil - girenler listeden dusmeli.
    if (!yaklasanBolumEl) return;
    var liste = ((veri && veri.yaklasan) || []).filter(function (n) {
      return gecerlilik(n).durum === "baslamadi";
    }).sort(function (a, b) {
      return String(a.effective_start || "").localeCompare(String(b.effective_start || ""));
    });
    yaklasanBolumEl.hidden = liste.length === 0;
    yaklasanEl.innerHTML = liste.map(notamKarti).join("");
  }

  function aktifGoster() {
    if (!veri) return;
    // Ham UTC damgasi ("2026-09-22 19:51") GOSTERILMIYOR: sayfadaki diger
    // saatler YEREL, bu ise UTC idi ve etiketsizdi - hangi saat dilimi
    // oldugu belirtilmeden yaniltici. Ayni gerekce NOTAM kalan suresinde
    // de goreceli bicimi sectirmisti (bkz. window.ltfjKalanSure).
    //
    // Ayrica bayatlik artik GORUNUR: NOTAC gunlerce erisilemezse liste
    // sessizce eskiyordu, kucuk gri bir tarihten bunu cikarmak
    // kullanicinin isi degil.
    senkronEl.classList.remove("notam-senkron-bayat");
    if (!veri.son_senkron) {
      senkronEl.textContent = "henüz senkronize edilmedi";
    } else {
      var yasMs = Date.now() - new Date(veri.son_senkron).getTime();
      senkronEl.textContent = isNaN(yasMs)
        ? "senkron zamanı okunamadı"
        : window.ltfjGecenSure(yasMs) + " senkronize edildi";
      if (yasMs > NOTAM_BAYAT_MS) {
        senkronEl.classList.add("notam-senkron-bayat");
        // Emoji DEGIL duz metin: burasi textContent, SVG konulamaz.
        // Renk zaten .notam-senkron-bayat ile veriliyor; metin ikinci
        // isaret, yani durum renge TEK BASINA bagli degil.
        senkronEl.textContent += " · liste eski olabilir";
      }
    }

    if (!veri.son_senkron) {
      aktifSayiEl.textContent = "";
      aktifEl.innerHTML = '<div class="notam-bos">NOTAM verisi şu anda alınamıyor.</div>';
      return;
    }

    yaklasanGoster();

    var tumu = yururluktekiler();
    var gosterilecek = sirala(aktifFiltrele(tumu));

    aktifSayiEl.textContent = !tumu.length
      ? "aktif yok"
      : (gosterilecek.length === tumu.length
          ? tumu.length + " aktif"
          : gosterilecek.length + " / " + tumu.length + " aktif");

    if (!tumu.length) {
      aktifEl.innerHTML = '<div class="notam-bos">Aktif NOTAM bulunmuyor.</div>';
    } else if (!gosterilecek.length) {
      aktifEl.innerHTML = '<div class="notam-bos">Filtreye uyan aktif NOTAM yok.</div>';
    } else {
      aktifEl.innerHTML = gosterilecek.map(notamKarti).join("");
    }
  }

  // Filtre secenekleri SADECE yururlukteki NOTAM'larda gercekten bulunan
  // degerlerden uretilir - bos sonuc veren secenek listelenmez.
  function aktifFiltreSecenekleriDoldur() {
    var liste = yururluktekiler();
    var kategoriler = {}, elemanlar = {};
    liste.forEach(function (n) {
      if (n.category_etiketi) {
        kategoriler[n.category_etiketi] = (kategoriler[n.category_etiketi] || 0) + 1;
      }
      (n.affected_elements || []).forEach(function (e) {
        if (e.ref) elemanlar[e.ref] = true;
      });
    });

    // --- eleman <select>'i (degismedi) ---
    var elemanSecili = aktifElemanEl.value;
    while (aktifElemanEl.options.length > 1) aktifElemanEl.remove(1);
    var elemanListesi = Object.keys(elemanlar).sort();
    elemanListesi.forEach(function (d) {
      var o = document.createElement("option");
      o.value = d; o.textContent = d;
      aktifElemanEl.appendChild(o);
    });
    aktifElemanEl.value = elemanListesi.indexOf(elemanSecili) !== -1 ? elemanSecili : "";

    // --- kategori CIPLERI, sayaclariyla ---
    var adlar = Object.keys(kategoriler).sort(function (a, b) {
      // COK OLAN ONCE. Alfabetik sirada "Apron 3" ile "Runway 4"
      // arasinda hangisinin agir bastigi ancak sayilar okunarak
      // anlasiliyordu; siralama o isi kendisi yapsin.
      return kategoriler[b] - kategoriler[a] || a.localeCompare(b);
    });
    // Secili kategori veri yenilenince artik yoksa secim DUSURULUR -
    // yoksa hicbir kayda uymayan bir suzgec acik kalir ve liste bos
    // gorunur, kullanici da nedenini goremez.
    if (aktifKategori && adlar.indexOf(aktifKategori) === -1) aktifKategori = "";
    aktifKategoriEl.innerHTML = "";
    adlar.forEach(function (ad) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "notam-cip";
      b.setAttribute("aria-pressed", ad === aktifKategori ? "true" : "false");
      b.appendChild(document.createTextNode(ad));
      var sayi = document.createElement("b");
      sayi.textContent = kategoriler[ad];
      b.appendChild(sayi);
      b.addEventListener("click", function () {
        // AYNI CIPE TEKRAR BASMAK SUZGECI KALDIRIR. Cip grubunda
        // "hepsi" diye ayri bir dugme yok; olsaydi hem yer yerdi hem
        // de secili olmayan durumu iki ayri bicimde anlatirdi.
        aktifKategori = (aktifKategori === ad) ? "" : ad;
        aktifFiltreSecenekleriDoldur();
        aktifGoster();
      });
      aktifKategoriEl.appendChild(b);
    });
  }

  function aramaCalistir() {
    if (!veri) return;
    var q = document.getElementById("notam-q").value.trim().toLowerCase();
    var ts = document.getElementById("notam-tarih-baslangic").value;
    var te = document.getElementById("notam-tarih-bitis").value;
    var durum = durumSelectEl.value;

    // Hicbir kriter girilmediyse TUM gecmisi dokmuyoruz - bu bilincli bir
    // tercih: "gecmis" NOTAC'in arsivi degil, sadece botun gordukleri;
    // istenmeden karsiya dokulmesi yaniltici olur.
    if (!q && !ts && !te && !durum) {
      sonucEl.innerHTML = '<div class="notam-bos">Aramak için yukarıdaki '
        + "alanlardan birini doldurun.</div>";
      return;
    }

    var sonuclar = (veri.gecmis || []).filter(function (n) {
      // Kayittaki donuk `status` yerine HESAPLANAN gecerlilik - kartta
      // gorunen etiketle birebir ayni olsun.
      if (durum && gecerlilik(n).durum !== durum) return false;
      if (q) {
        var alanlar = [n.number, n.text, n.reading_short, n.reading_long]
          .concat(n.tags || [])
          .concat((n.affected_elements || []).map(function (e) { return e.ref; }))
          .filter(Boolean).join(" ").toLowerCase();
        if (alanlar.indexOf(q) === -1) return false;
      }
      if (ts && n.effective_end && n.effective_end < ts) return false;
      if (te && n.effective_start && n.effective_start > te) return false;
      return true;
    });

    sonucEl.innerHTML = sonuclar.length
      ? sonuclar.map(notamKarti).join("")
      : '<div class="notam-bos">Sonuç bulunamadı.</div>';
  }

  function veriYukle() {
    fetch("notam_veri.json?_=" + Date.now(), {cache: "no-store"})
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (v) {
        veri = v;
        aktifFiltreSecenekleriDoldur();
        aktifGoster();
        // Bolum katli geldigi icin basliktaki sayac, icinde ne kadar kayit
        // oldugunu acmadan gosterir.
        var gecmisSayiEl = document.getElementById("notam-gecmis-sayi");
        if (gecmisSayiEl) {
          var adet = (veri.gecmis || []).length;
          gecmisSayiEl.textContent = adet ? adet + " kayıt" : "";
        }
        // Kriter girilmemisse aramaCalistir zaten ipucu metnini basar.
        aramaCalistir();
      })
      .catch(function (err) {
        var mesaj = '<div class="notam-bos">NOTAM verisi şu anda alınamıyor.</div>';
        aktifEl.innerHTML = mesaj;
        sonucEl.innerHTML = mesaj;
        senkronEl.textContent = "";
        console.error("[notam] veri yüklenemedi:", err);
      });
  }

  // Ac/kapa artik <details> ile yapiliyor (bkz. NOTAM karti) - eskiden
  // burada elle yazilmis bir ok/aria-expanded yonetimi vardi, kalktikca
  // ayni isi tarayicinin yerlisi goruyor.
  // Filtre satirindaki tiklamalar paneli KAPATMAMALI - basligin disinda
  // olmasina ragmen govde baslikla ayni kartta, kullanici yanlislikla
  // katlamasin.
  aktifQEl.addEventListener("input", aktifGoster);
  // Kategori artik <select> degil cip grubu: "change" olayi YOK, her
  // cip kendi dinleyicisini aktifFiltreSecenekleriDoldur icinde
  // baglıyor. Burada eski "change" dinleyicisi kalsaydi sessizce hic
  // tetiklenmeyen olu kod olurdu.
  aktifElemanEl.addEventListener("change", aktifGoster);
  aktifSiralamaEl.addEventListener("change", aktifGoster);
  document.getElementById("notam-aktif-temizle").addEventListener("click", function () {
    aktifQEl.value = "";
    aktifKategori = "";
    aktifElemanEl.value = "";
    // SIRALAMA SIFIRLANMIYOR: bir suzgec degil, GORUNUM tercihi.
    // "Temizle" suzgecleri kaldirir; kullanicinin sectigi sirayi da
    // geri almak, istemedigi bir seyi degistirmek olurdu.
    aktifFiltreSecenekleriDoldur();
    aktifGoster();
  });

  // Aktif liste filtreleriyle AYNI davranis: yazdikca/sectikce suzuluyor,
  // ayri bir "Ara" adimi yok. Gecmis birkac yuz kayitla sinirli oldugu icin
  // her tusta yeniden cizmek sorun degil.
  document.getElementById("notam-q").addEventListener("input", aramaCalistir);
  document.getElementById("notam-tarih-baslangic").addEventListener("change", aramaCalistir);
  document.getElementById("notam-tarih-bitis").addEventListener("change", aramaCalistir);
  durumSelectEl.addEventListener("change", aramaCalistir);
  document.getElementById("notam-arama-temizle").addEventListener("click", function () {
    document.getElementById("notam-q").value = "";
    document.getElementById("notam-tarih-baslangic").value = "";
    document.getElementById("notam-tarih-bitis").value = "";
    durumSelectEl.value = "";
    aramaCalistir();
  });
  veriYukle();
})();
