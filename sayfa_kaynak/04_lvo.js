
(function () {
  "use strict";
  // LVO REFERENCE paneli - METAR/NOTAM/ATC Notes'tan TAMAMEN bağımsız bir
  // bilgi katmanı, yukarıdaki hiçbir script'le değişken/durum PAYLAŞMAZ.
  // Bu script SADECE mevcut bilgileri (AWOS RVR manuel girişi, LVO ile
  // ilişkili NOTAM'lar, Farkındalık Notları) provenance ve zaman damgasıyla
  // GÖSTERİR - hiçbir operasyonel karar (LVO aktif mi, CAT II kullanılabilir
  // mi, hangi pist kullanılmalı) ÜRETMEZ. Farkındalık Notları GAYRİ RESMİ,
  // hedge'li ("... olabilir. Resmî bir tespit değildir.") metinlerdir - bkz.
  // ltfj_lvo_farkindalik.py. AWOS değerleri asla METAR'dan türetilmez,
  // sadece kullanıcının manuel girdiği değerlerdir. Okuma/yazma ATC Notes
  // ile AYNI Firebase veritabanına, farklı path'e (awos_rvr) yapılır - ayrı
  // bir proje/kurulum gerekmez.
  var DB_URL = @@atc_notes_db_url@@;
  var RVR_ESIKLERI = @@rvr_esikleri_json@@;   // ltfj_lvo_referans.RVR_ESIKLERI ile AYNI kaynak
  var STALE_ESIK_DK = 30;   // SADECE veri tazeliği göstergesi - operasyonel bir minima DEĞİL
  var AWOS_PISTLER = ["06R", "24R"];
  var AWOS_POZISYONLAR = ["TDZ", "MID", "STOP-END"];
  // Q KODU BIRINCIL SUZGEC. Anahtar kelime listesi YEDEKTE kaliyor:
  // Q kodu olmayan (ornegin modele q_code eklenmeden once senkronlanmis)
  // ya da bicimi okunamayan kayitlar sessizce kaybolmasin diye. Ikisi
  // BIRLESIM calisiyor - panelde bir NOTAM'in eksik kalmasi, fazladan
  // bir NOTAM gorunmesinden daha pahali.
  var LVO_Q_KONULARI = @@lvo_q_konulari_json@@;   // ltfj_notam.LVO_Q_KONULARI ile AYNI kaynak
  var LVO_NOTAM_ANAHTAR_KELIMELER = [
    "runway", "rwy", "ils", "localizer", "glide", "approach light", "yaklaşma işık",
    "runway light", "pist ışık", "taxiway", "taksi yolu", "stop bar", "rvr", "awos",
    "atis", "low visibility", "düşük görüş", "aerodrome equipment", "havalimanı ekipman",
  ];

  var awosListeEl = document.getElementById("lvo-awos-liste");
  var notamListeEl = document.getElementById("lvo-notam-liste");
  var awosHataEl = document.getElementById("lvo-awos-hata");
  var awosKaydetBtn = document.getElementById("lvo-awos-kaydet");
  var sonAwosGonderim = 0;

  // LVO ac/kapa mantigi KALDIRILDI: panel artik bir sekme paneli, gorunur
  // olup olmadigini sekme cubugu belirliyor. Ayri bir ac/kapa, sekmeye
  // bastiktan sonra bir de basliga basmak demekti.
  var farkRvrListeEl = document.getElementById("lvo-fark-rvr-liste");
  var farkBosEl = document.getElementById("lvo-fark-bos");

  function tabanUrl(yol) {
    var taban = DB_URL;
    while (taban.length && taban.charAt(taban.length - 1) === "/") {
      taban = taban.slice(0, -1);
    }
    return taban + "/" + yol + ".json";
  }

  function yasGoster(ms) {
    var dk = Math.floor((Date.now() - ms) / 60000);
    if (dk < 1) return "az önce";
    if (dk < 60) return dk + " dk önce";
    var saat = Math.floor(dk / 60), kalanDk = dk % 60;
    return saat + " sa " + kalanDk + " dk önce";
  }

  // -------------------------------------------------------------- AWOS
  function awosGoster(kayitlar) {
    if (!DB_URL) {
      awosListeEl.textContent = "AWOS RVR: NOT AVAILABLE";
      farkindalikRvrGuncelle({});
      return;
    }
    var enSon = {};
    Object.keys(kayitlar || {}).forEach(function (id) {
      var k = kayitlar[id];
      if (!k || typeof k.entered_at !== "number") return;
      var anahtar = k.runway + "|" + k.position;
      if (!enSon[anahtar] || k.entered_at > enSon[anahtar].entered_at) enSon[anahtar] = k;
    });

    var verilerVarMi = false;
    var grid = document.createElement("div");
    grid.className = "lvo-awos-grid";

    AWOS_PISTLER.forEach(function (pist) {
      var kart = document.createElement("div");
      kart.className = "lvo-awos-kart";
      var baslik = document.createElement("div");
      baslik.className = "lvo-awos-pist";
      baslik.textContent = pist;
      kart.appendChild(baslik);

      var pistteVeriVar = false;
      var enYeniZaman = 0;
      AWOS_POZISYONLAR.forEach(function (poz) {
        var kayit = enSon[pist + "|" + poz];
        var satir = document.createElement("div");
        satir.className = "lvo-awos-deger";
        var etiket = document.createElement("span");
        etiket.textContent = poz;
        satir.appendChild(etiket);
        var deger = document.createElement("span");
        if (kayit) {
          pistteVeriVar = true;
          verilerVarMi = true;
          if (kayit.entered_at > enYeniZaman) enYeniZaman = kayit.entered_at;
          deger.textContent = kayit.value + " " + kayit.unit;
          if ((Date.now() - kayit.entered_at) > STALE_ESIK_DK * 60000) {
            var staleEl = document.createElement("span");
            staleEl.className = "lvo-stale";
            staleEl.textContent = "STALE";
            deger.appendChild(staleEl);
          }
        } else {
          deger.textContent = "—";
        }
        satir.appendChild(deger);
        kart.appendChild(satir);
      });

      if (pistteVeriVar) {
        var alt = document.createElement("div");
        alt.className = "lvo-awos-alt";
        alt.textContent = "MANUAL AWOS · " + yasGoster(enYeniZaman);
        kart.appendChild(alt);
      }
      grid.appendChild(kart);
    });

    awosListeEl.innerHTML = "";
    if (!verilerVarMi) {
      awosListeEl.textContent = "AWOS RVR: NOT AVAILABLE";
    } else {
      awosListeEl.appendChild(grid);
    }

    farkindalikRvrGuncelle(enSon);
  }

  // Manuel AWOS RVR degerlerini (gercek olcum) dokumanin kendi esikleriyle
  // (RVR_ESIKLERI - ltfj_lvo_farkindalik.rvr_notu() ile AYNI mantik) GAYRI
  // RESMI, hedge'li notlara cevirir; "LVO aktif/CAT II kullanilabilir" gibi
  // kesin bir ifade URETMEZ.
  function rvrFarkindalikNotu(pist, pozisyon, degerM) {
    var enDerin = null;
    RVR_ESIKLERI.forEach(function (e) {
      if (degerM < e.esik_altinda_m && (!enDerin || e.esik_altinda_m < enDerin.esik_altinda_m)) {
        enDerin = e;
      }
    });
    if (!enDerin) return null;
    return pist + " " + pozisyon + " AWOS RVR " + degerM + " m — dokümanın " +
      enDerin.esik_altinda_m + " m eşiğinin (" + enDerin.safha + ") altında. " +
      "LVO şartları oluşabilir. Resmî bir tespit değildir.";
  }

  function farkindalikRvrGuncelle(enSonAwos) {
    farkRvrListeEl.innerHTML = "";
    Object.keys(enSonAwos || {}).sort().forEach(function (anahtar) {
      var k = enSonAwos[anahtar];
      var not_ = rvrFarkindalikNotu(k.runway, k.position, k.value);
      if (!not_) return;
      var li = document.createElement("li");
      li.textContent = not_;
      farkRvrListeEl.appendChild(li);
    });
    var toplamNot = document.querySelectorAll("#lvo-fark-metar-taf li, #lvo-fark-rvr-liste li").length;
    farkBosEl.hidden = toplamNot > 0;
  }

  function awosYukle() {
    if (!DB_URL) { awosGoster({}); return; }
    fetch(tabanUrl("awos_rvr") + "?_=" + Date.now())
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(awosGoster)
      .catch(function (err) {
        awosListeEl.textContent = "AWOS RVR: NOT AVAILABLE";
        console.error("[lvo] awos okuma hatası:", err);
      });
  }

  // Secili pistin TUM AWOS RVR kayitlarini siler. Tek tek degil hepsi,
  // cunku gosterim her pist|pozisyon icin EN YENI kaydi seciyor - sadece
  // sonuncuyu silmek bir oncekini geri getirirdi.
  //
  // Firebase kurali silmeye izin verir ama UZERINE YAZMAYA izin vermez
  // (bkz. firebase-rules.json awos_rvr: "!data.exists() || !newData.exists()").
  // Kurallarin guncel hali yayinlanmamissa istek 401/403 doner ve bunu
  // sessizce yutmuyoruz - kullaniciya soyluyoruz.
  document.getElementById("lvo-awos-temizle").addEventListener("click", function () {
    awosHataEl.textContent = "";
    if (!DB_URL) { awosHataEl.textContent = "LVO paneli şu anda yapılandırılmamış."; return; }
    var pist = document.getElementById("lvo-awos-pist").value;
    // Paylasilan operasyonel veri siliniyor - once onay.
    if (!window.confirm(pist + " pistinin girilmiş AWOS RVR değerleri silinecek. Onaylıyor musunuz?")) return;

    var btn = document.getElementById("lvo-awos-temizle");
    btn.disabled = true;
    fetch(tabanUrl("awos_rvr") + "?_=" + Date.now())
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (kayitlar) {
        var idler = Object.keys(kayitlar || {}).filter(function (id) {
          return kayitlar[id] && kayitlar[id].runway === pist;
        });
        if (!idler.length) {
          awosHataEl.textContent = pist + " için silinecek kayıt yok.";
          return null;
        }
        return Promise.all(idler.map(function (id) {
          // tabanUrl() sonuna ".json" EKLER - kaydin yolunu ona parametre
          // olarak vermek gerekir. Birlestirerek yazmak
          // ".../awos_rvr.json/<id>.json" gibi gecersiz bir URL uretiyordu.
          return fetch(tabanUrl("awos_rvr/" + encodeURIComponent(id)),
                       {method: "DELETE"})
            .then(function (r) {
              if (!r.ok) throw new Error("HTTP " + r.status);
            });
        }));
      })
      .then(function (sonuc) { if (sonuc) awosYukle(); })
      .catch(function (err) {
        // Hata metni SEBEBI tasisin: ilk surumde sadece "kurallar silmeye
        // izin veriyor mu?" yaziyordu ve asil sorun (bozuk URL) teshis
        // edilemiyordu. 401/403 kural, 400/404 yol sorununu isaret eder.
        awosHataEl.textContent = "AWOS RVR temizlenemedi (" + err.message + ")."
          + " 401/403 ise Firebase kuralları silmeye izin vermiyor demektir.";
        console.error("[lvo] awos temizleme hatası:", err);
      })
      .finally(function () { btn.disabled = false; });
  });

  document.getElementById("lvo-awos-kaydet").addEventListener("click", function () {
    awosHataEl.textContent = "";
    if (!DB_URL) { awosHataEl.textContent = "LVO paneli şu anda yapılandırılmamış."; return; }
    if (Date.now() - sonAwosGonderim < 3000) return;

    var pist = document.getElementById("lvo-awos-pist").value;
    var alanlar = [
      {poz: "TDZ", el: document.getElementById("lvo-awos-tdz")},
      {poz: "MID", el: document.getElementById("lvo-awos-mid")},
      {poz: "STOP-END", el: document.getElementById("lvo-awos-end")},
    ];
    var gonderilecekler = [];
    for (var i = 0; i < alanlar.length; i++) {
      var ham = alanlar[i].el.value.trim();
      if (ham === "") continue;
      var sayi = Number(ham);
      if (!isFinite(sayi) || sayi < 0 || sayi > 9999) {
        awosHataEl.textContent = alanlar[i].poz + " değeri 0-9999 arası bir sayı olmalı.";
        return;
      }
      gonderilecekler.push({position: alanlar[i].poz, value: sayi});
    }
    if (!gonderilecekler.length) {
      awosHataEl.textContent = "En az bir RVR değeri girin.";
      return;
    }

    awosKaydetBtn.disabled = true;
    Promise.all(gonderilecekler.map(function (g) {
      return fetch(tabanUrl("awos_rvr"), {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          runway: pist, position: g.position, value: g.value, unit: "m",
          entered_at: {".sv": "timestamp"}, source: "MANUAL AWOS",
        }),
      }).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); });
    }))
      .then(function () {
        sonAwosGonderim = Date.now();
        alanlar.forEach(function (a) { a.el.value = ""; });
        awosYukle();
      })
      .catch(function (err) {
        awosHataEl.textContent = "AWOS RVR kaydedilemedi, tekrar deneyin.";
        console.error("[lvo] awos yazma hatası:", err);
      })
      .finally(function () { awosKaydetBtn.disabled = false; });
  });

  // ------------------------------------------------------- LVO-ilişkili NOTAM
  function notamKarti(n) {
    var kart = document.createElement("div");
    kart.className = "notam-kart";
    var ust = document.createElement("div");
    ust.className = "notam-ust";
    if (window.ltfjNotamGecerlilik(n).durum === "yururlukte") {
      var nokta = document.createElement("span");
      nokta.className = "notam-aktif-nokta";
      nokta.title = "Şu anda yürürlükte";
      ust.appendChild(nokta);
    }
    var no = document.createElement("span");
    no.className = "notam-no";
    no.textContent = n.number || "—";
    ust.appendChild(no);
    kart.appendChild(ust);
    var metin = document.createElement("div");
    metin.className = "notam-cumle";
    metin.textContent = n.reading_short || n.text || "";
    kart.appendChild(metin);
    return kart;
  }

  function qKonusu(n) {
    // "QMRLC" -> "MR". Bicim beklenmedikse null: yanlis bir dilimden
    // konu uydurmaktansa "bilmiyorum" deyip yedege dusmek dogru.
    var kod = (n.q_code || "").trim().toUpperCase();
    if (kod.length !== 5 || kod.charAt(0) !== "Q" || !/^[A-Z]{5}$/.test(kod)) return null;
    return kod.substring(1, 3);
  }

  function notamLvoIliskiliMi(n) {
    var konu = qKonusu(n);
    if (konu !== null && LVO_Q_KONULARI.indexOf(konu) !== -1) return true;
    var alanlar = [n.text, n.reading_short, n.reading_long, n.category_etiketi]
      .concat(n.tags || [])
      .filter(Boolean).join(" ").toLowerCase();
    return LVO_NOTAM_ANAHTAR_KELIMELER.some(function (kw) { return alanlar.indexOf(kw) !== -1; });
  }

  function notamYukle() {
    fetch("notam_veri.json?_=" + Date.now(), {cache: "no-store"})
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (v) {
        // Suresi dolmus bir NOTAM burada aktifmis gibi gorunmemeli - LVO
        // panelinde bu, olmayan bir kisitlamayi varmis gibi gostermek olur.
        var aktif = ((v && v.aktif) || []).filter(function (n) {
          return window.ltfjNotamGecerlilik(n).durum === "yururlukte";
        });
        var iliskili = aktif.filter(notamLvoIliskiliMi);
        notamListeEl.innerHTML = "";
        if (!iliskili.length) {
          notamListeEl.textContent = "No LVO-related NOTAM in local cache";
        } else {
          iliskili.forEach(function (n) { notamListeEl.appendChild(notamKarti(n)); });
        }
      })
      .catch(function (err) {
        notamListeEl.textContent = "No LVO-related NOTAM in local cache";
        console.error("[lvo] notam okuma hatası:", err);
      });
  }

  awosYukle();
  notamYukle();
  window.ltfjLvoNotamYenile = notamYukle;
  setInterval(function () { awosYukle(); }, 45000);
})();
