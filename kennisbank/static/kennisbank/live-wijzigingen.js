/* Veranderd in de live versie (1.33.0).
 *
 * Wie de live versie verbetert terwijl er een concept ligt, raakt het concept niet. Dit paneel laat in het
 * concept zien wat er live is veranderd, één wijziging tegelijk, en neemt over wat veilig kan. De server rekent
 * (kennisbank/livewijzigingen.py): dit script stuurt wat er nu in de editor staat, krijgt de lijst terug en,
 * bij overnemen, de nieuwe tekst. Er wordt niets opgeslagen tot de redacteur *Opslaan als concept* kiest; de
 * besluiten (niet overnemen, aangepast, gezien) gaan dan mee in het verborgen veld kb_live_besluiten.
 */
(function () {
  "use strict";

  function $(id) { return document.getElementById(id); }
  function el(tag, klasse, tekst) {
    var e = document.createElement(tag);
    if (klasse) e.className = klasse;
    if (tekst != null) e.textContent = tekst;
    return e;
  }
  function n(aantal, een, meer) { return aantal === 1 ? een : meer.replace("%", aantal); }

  var STAND = { overgenomen: "Overgenomen ✓", aangepast: "Aangepast ✓", niet: "Niet overgenomen", gezien: "Gezien ✓" };

  function begin() {
    var bron = $("kb-live-gegevens"), paneel = $("kb-p-live");
    if (!bron || !paneel) return;
    var g;
    try { g = JSON.parse(bron.textContent); } catch (e) { return; }
    var form = paneel.closest("form");
    var besluitVeld = $("kb-live-besluiten");
    var besluiten = g.besluiten || {};
    var begonnen = JSON.stringify(besluiten);
    var huidig = 0, bezig = false, fout = "";

    function ed() { return window.kbInhoudEditor; }
    function veld(naam) { return form.elements.namedItem(naam); }
    function open() { return paneel.classList.contains("kb-open"); }
    function lijst() { return g.wijzigingen || []; }
    function telling() {
      var o = 0, niet = 0;
      lijst().forEach(function (w) { if (w.stand === "open") o++; if (w.stand === "niet") niet++; });
      return { totaal: lijst().length, open: o, niet: niet, vervalt: o + niet };
    }
    function veilig() { return lijst().filter(function (w) { return w.stand === "open" && w.auto; }); }

    // --- Praten met de server -------------------------------------------------------------
    function vraag(overnemen) {
      var data = new FormData();
      data.append("titel", veld("titel") ? veld("titel").value : "");
      data.append("samenvatting", veld("samenvatting") ? veld("samenvatting").value : "");
      data.append("inhoud", ed() ? ed().value : (veld("inhoud") ? veld("inhoud").value : ""));
      data.append("kb_live_besluiten", JSON.stringify(besluiten));
      if (overnemen) data.append("overnemen", overnemen);
      var token = form.querySelector('[name="csrfmiddlewaretoken"]');
      return fetch(g.url, { method: "POST", body: data, credentials: "same-origin", headers: { "X-CSRFToken": token ? token.value : "" } })
        .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.fout || "De wijzigingen konden niet worden opgehaald."); return j; }); });
    }
    function verwerk(j, vorigeId) {
      fout = "";
      g.wijzigingen = j.wijzigingen;
      besluiten = j.besluiten || {};
      besluitVeld.value = JSON.stringify(besluiten);
      // Dezelfde wijziging in beeld houden, ook als de lijst is verschoven.
      var i = lijst().findIndex(function (w) { return w.id === vorigeId; });
      if (i >= 0) huidig = i;
      if (huidig >= lijst().length) huidig = Math.max(0, lijst().length - 1);
    }
    function ververs() {
      if (bezig || !open()) return;
      var id = lijst()[huidig] && lijst()[huidig].id;
      vraag("").then(function (j) { verwerk(j, id); teken(false); }).catch(function () { /* de volgende keer weer */ });
    }

    function neemOver(wat, daarna) {
      if (bezig) return;
      bezig = true;
      var w = lijst()[huidig], id = w && w.id;
      vraag(wat).then(function (j) {
        bezig = false;
        if (j.velden) {
          stil = true;
          ["titel", "samenvatting"].forEach(function (naam) {
            var v = veld(naam);
            if (v && v.value !== j.velden[naam]) { v.value = j.velden[naam]; v.dispatchEvent(new Event("input", { bubbles: true })); }
          });
          if (ed() && j.velden.inhoud !== ed().value) ed().value = j.velden.inhoud;
          stil = false;
        }
        verwerk(j, id);
        if (!j.gedaan || !j.gedaan.length) fout = "Overnemen lukte niet: de tekst eromheen is intussen veranderd. Pas het met de hand aan.";
        if (daarna) daarna(j);
      }).catch(function (e) { bezig = false; fout = e.message; teken(false); });
    }

    // --- Besluiten die niet aan de tekst te zien zijn -------------------------------------
    function besluit(w, wat) {
      if (wat) besluiten[w.id] = wat; else delete besluiten[w.id];
      w.stand = wat || "open";
      w.door = "";
      besluitVeld.value = JSON.stringify(besluiten);
    }

    // --- De plek in het concept aanwijzen ---------------------------------------------------
    function wijsAan(w, opties) {
      document.querySelectorAll(".kb-live-hier").forEach(function (x) { x.classList.remove("kb-live-hier"); });
      if (!ed() || !ed().liveMarkeer) return false;
      if (!open() || !w || !w.anker) { ed().liveMarkeer(null); return false; }
      if (w.anker.veld) {
        ed().liveMarkeer(null);
        var v = veld(w.anker.veld), vak = v && v.closest(".kb-vast");
        if (vak) vak.classList.add("kb-live-hier");
        if (v && opties && opties.focus) v.focus();
        else if (vak && opties && opties.schuif) vak.scrollIntoView({ block: "center" });
        return !!v;
      }
      var m = { sleutel: w.anker.sleutel, nr: w.anker.nr };
      if (w.stand === "open") { m.na = w.anker.na; m.voor = w.anker.voor; }
      if (opties && opties.net) m.net = true;
      return ed().liveMarkeer(m, opties);
    }

    // --- Tekenen --------------------------------------------------------------------------
    function uitleg(w) {
      if (w.stand === "overgenomen") return ["De tekst staat in je concept" + (w.anker ? "; in het blad is hij gemarkeerd." : "."), false];
      if (w.stand === "aangepast") return ["Met de hand aangepast in het concept" + (w.door ? ", door " + w.door : "") + ".", false];
      if (w.stand === "niet") return ["Niet overgenomen" + (w.door ? ", door " + w.door : "") + ". Publiceer je het concept, dan vervalt deze wijziging.", false];
      if (w.stand === "gezien") return ["Gezien" + (w.door ? " door " + w.door : "") + ". Er was niets over te nemen.", false];
      if (w.soort === "veilig") return [w.anker && w.anker.veld
        ? "In het concept is dit veld niet gewijzigd, dus overnemen kan veilig."
        : "In het blad staat de alinea gemarkeerd. In het concept is hij niet gewijzigd, dus overnemen kan veilig.", false];
      if (w.soort === "nieuw") return [w.auto
        ? "Dit is nieuw in de live versie. In het concept staat het nog niet; in het blad zie je waar het komt."
        : "Dit is nieuw in de live versie. De kennisbank kan de plek in het concept niet bepalen, omdat de tekst eromheen is veranderd. Voeg het zelf toe.", !w.auto];
      if (w.soort === "verwijderd") return [w.auto
        ? "Deze alinea is uit de live versie gehaald. In het concept staat hij nog, ongewijzigd; in het blad is hij gemarkeerd."
        : "Deze alinea is uit de live versie gehaald. Haal hem zelf weg in het concept: het is een tabelcel of de titel van een sectie.", !w.auto];
      if (w.soort === "zelf") return ["Deze alinea is in het concept zelf ook gewijzigd. Overnemen zou die tekst vervangen. Pas de alinea met de hand aan; in het blad is hij gemarkeerd.", true];
      return ["Deze alinea staat niet meer in het concept. Er is dus niets over te nemen. Kijk wel of de wijziging ergens anders in de tekst terug moet komen.", true];
    }

    function tekenPaneel(schuif) {
      var lijf = $("kb-live-lijf"), alle = lijst(), w = alle[huidig];
      lijf.textContent = "";
      $("kb-live-teller").textContent = alle.length ? "Wijziging " + (huidig + 1) + " van " + alle.length : "Geen wijzigingen";
      $("kb-live-vorige").disabled = huidig === 0;
      $("kb-live-volgende").disabled = huidig >= alle.length - 1;

      var stippen = $("kb-live-stippen");
      stippen.textContent = "";
      alle.forEach(function (x, i) {
        var b = el("button", "kb-live-stip" + (x.stand === "open" ? "" : x.stand === "niet" ? " kb-live-stip-niet" : " kb-live-stip-klaar"));
        b.type = "button";
        b.setAttribute("aria-label", "Wijziging " + (i + 1) + ": " + x.sectie + ", " + (STAND[x.stand] || "nog te doen").replace(" ✓", ""));
        if (i === huidig) b.setAttribute("aria-current", "true");
        b.addEventListener("click", function () { huidig = i; teken(true); });
        stippen.appendChild(b);
      });
      if (!w) return;

      var waar = el("div", "kb-live-waar");
      waar.appendChild(el("b", null, w.sectie));
      if (w.plek) waar.appendChild(el("span", null, w.plek));
      waar.appendChild(el("span", "kb-live-stand" + (w.stand === "open" ? "" : w.stand === "niet" ? " kb-live-stand-niet" : " kb-live-stand-klaar"), STAND[w.stand] || "Nog te doen"));
      lijf.appendChild(waar);

      lijf.appendChild(el("h3", null, "Veranderd in de live versie"));
      var vak = el("div", "kb-live-vak");
      // De server levert platte tekst met alleen <ins>, <del> en <p>; alles is ge-escaped (verschil.woordverschil).
      if (w.blok) vak.innerHTML = w.live; else { var p = el("p"); p.innerHTML = w.live; vak.appendChild(p); }
      lijf.appendChild(vak);

      lijf.appendChild(el("h3", null, "In je concept"));
      var u = uitleg(w);
      lijf.appendChild(el("p", "kb-live-uitleg" + (u[1] ? " kb-live-let" : ""), u[0]));
      if (fout) lijf.appendChild(el("p", "kb-live-uitleg kb-live-let", fout));

      var rij = el("div", "kb-live-rij");
      function knop(tekst, hoofd, doen) {
        var b = el("button", "button" + (hoofd ? "" : " kb-knop-rustig"), tekst);
        b.type = "button";
        b.addEventListener("click", doen);
        rij.appendChild(b);
        return b;
      }
      function door() {
        teken(false);
        var v = $("kb-live-volgende");
        (v.disabled ? paneel.querySelector(".kb-paneel-sluit") : v).focus();
      }
      function metBesluit(wat) { return function () { fout = ""; besluit(w, wat); door(); }; }
      function overnemen() { fout = ""; neemOver(w.id, function () { teken(false); wijsAan(lijst()[huidig], { schuif: true, net: true }); var v = $("kb-live-volgende"); (v.disabled ? paneel.querySelector(".kb-paneel-sluit") : v).focus(); }); }
      function cursor() { wijsAan(w, { focus: true, schuif: true }); }

      if (g.op_slot) {
        // Ter inzage: alleen bekijken.
      } else if (w.stand !== "open") {
        if (w.stand !== "overgenomen") knop("Toch opnieuw bekijken", false, metBesluit(""));
      } else if (w.auto) {
        knop(w.soort === "nieuw" ? "Toevoegen aan het concept" : w.soort === "verwijderd" ? "Ook weghalen uit het concept" : "Overnemen in het concept", true, overnemen);
        knop("Niet overnemen", false, metBesluit("niet"));
      } else if (w.soort === "weg") {
        knop("Gezien", true, metBesluit("gezien"));
      } else {
        if (w.anker) knop(w.anker.veld ? "Zet de cursor in het veld" : "Zet de cursor in de alinea", true, cursor);
        knop("Ik heb het aangepast", !w.anker, metBesluit("aangepast"));
        knop("Niet overnemen", false, metBesluit("niet"));
      }
      lijf.appendChild(rij);
      wijsAan(w, { schuif: schuif });
    }

    function tekenRest() {
      var t = telling(), v = veilig().length;
      $("kb-live-voortgang").textContent = (t.totaal - t.open) + " van " + t.totaal + " verwerkt";
      var alles = $("kb-live-alles");
      alles.textContent = v ? n(v, "De ene veilige wijziging overnemen", "Alle % veilige wijzigingen in één keer overnemen") : "Geen veilige wijzigingen meer over";
      alles.disabled = !v || bezig;
      var knop = $("kb-live-knop");
      if (knop) knop.textContent = t.open ? "Live wijzigingen (" + t.open + ")" : "Live wijzigingen ✓";

      // Nog niet opgeslagen besluiten: zeg het, want de kladversie bewaart alleen de tekst.
      var onbewaard = paneel.querySelector(".kb-live-onbewaard");
      var anders = JSON.stringify(besluiten) !== begonnen;
      if (anders && !onbewaard) $("kb-live-voortgang").parentNode.parentNode.appendChild(el("p", "kb-live-onbewaard", "Je keuzes worden bewaard als je kiest voor Afronden → Opslaan als concept."));
      if (!anders && onbewaard) onbewaard.remove();

      var melding = $("kb-live-melding");
      if (!melding) return;
      var kop = $("kb-live-kop"), zin = $("kb-live-zin"), bekijk = $("kb-live-bekijk");
      melding.classList.toggle("kb-live-klaar", !t.open);
      if (t.open) {
        melding.hidden = false;
        kop.textContent = "Let op: de live versie is bijgewerkt.";
        zin.textContent = t.open === t.totaal
          ? "Dit concept komt niet meer overeen met de publicatie. Er " + n(t.totaal, "is 1 wijziging", "zijn % wijzigingen") + "."
          : "Je hebt " + (t.totaal - t.open) + " van de " + t.totaal + " wijzigingen verwerkt. Je kunt op elk moment verder.";
        if (bekijk) bekijk.textContent = open() ? "Paneel sluiten" : (t.open === t.totaal ? "Loop de wijzigingen langs (" : "Verder met de wijzigingen (") + t.open + ")";
      } else {
        kop.textContent = "De wijzigingen van de live versie zijn verwerkt.";
        zin.textContent = t.niet
          ? n(t.niet, "1 wijziging is", "% wijzigingen zijn") + " bewust niet overgenomen: publiceren vervangt die."
          : "Je concept loopt weer gelijk met wat live is veranderd.";
        if (bekijk) bekijk.textContent = open() ? "Paneel sluiten" : "Nog eens bekijken";
      }
    }

    function teken(schuif) {
      tekenRest();
      if (open()) tekenPaneel(schuif); else wijsAan(null);
    }

    // --- Open en dicht: het paneel zelf gaat via artikel-scherm.js, zoals de andere panelen -------
    var knop = $("kb-live-knop");
    function toon() {
      if (!open() && knop) knop.click();
    }
    var wasOpen = false;
    new MutationObserver(function () {
      var nu = open();
      if (nu === wasOpen) return;
      wasOpen = nu;
      document.body.classList.toggle("kb-live-open", nu);
      if (nu) {
        var eerste = lijst().findIndex(function (w) { return w.stand === "open"; });
        if (eerste >= 0 && lijst()[huidig] && lijst()[huidig].stand !== "open") huidig = eerste;
        teken(true);
        ververs();
      } else {
        teken(false);
      }
      if (ed() && ed().tekenMarge) setTimeout(ed().tekenMarge, 260);
    }).observe(paneel, { attributes: true, attributeFilter: ["class"] });

    $("kb-live-vorige").addEventListener("click", function () { if (huidig > 0) { huidig--; fout = ""; teken(true); } });
    $("kb-live-volgende").addEventListener("click", function () { if (huidig < lijst().length - 1) { huidig++; fout = ""; teken(true); } });
    $("kb-live-alles").addEventListener("click", function () {
      fout = "";
      neemOver("veilig", function () {
        var i = lijst().findIndex(function (w) { return w.stand === "open"; });
        if (i >= 0) huidig = i;
        teken(true);
      });
    });
    var bekijk = $("kb-live-bekijk");
    if (bekijk) bekijk.addEventListener("click", function () { if (knop) knop.click(); });

    // Typt de redacteur in het concept, dan kan de stand veranderen (zelf overgetikt = overgenomen).
    var stil = false, timer = null;
    form.addEventListener("input", function (e) {
      if (stil || !open() || (e.target && e.target.closest && e.target.closest("#kb-p-live"))) return;
      clearTimeout(timer);
      timer = setTimeout(ververs, 1500);
    });

    // Voor het venster Afronden (beheer-editor.js).
    window.kbLive = { telling: telling, toon: toon };
    teken(false);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", begin); else begin();
})();
