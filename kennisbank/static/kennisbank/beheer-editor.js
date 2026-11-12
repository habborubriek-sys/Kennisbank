/* Het beheerscherm: de editor koppelen, de kladversie, het zachte slot, de toelichting bij publiceren
 * en het venster Afronden.
 *
 * De editor zelf staat in artikel-editor.js (Tiptap, lokaal meegeleverd; sinds 1.22.0 voor artikelen,
 * sinds 1.23.0 ook voor nieuwsberichten). Plakken uit Word wordt daar opgeschoond; de server schoont
 * daarna nog een keer op (inhoud.py).
 */
(function () {
  "use strict";

  /* De editor (Tiptap, artikel-editor.js) op elk tekstvak met class "kb-editor".
   *
   * Op het bewerkscherm (artikel of nieuwsbericht) staat de werkbalk al in de pagina; anders komt hij
   * boven het tekstvak. Nieuwsberichten krijgen geen knoppen voor secties en onboarding. */
  function init(textarea) {
    if (textarea.dataset.kbEditor || !window.KBArtikelEditor) return;
    textarea.dataset.kbEditor = "1";
    var artikel = textarea.name === "inhoud";
    var balk = document.querySelector(".kb-ae-werkbalk-in");
    if (!balk || balk.dataset.kbInGebruik) {
      var los = document.createElement("div");
      los.className = "kb-ae-werkbalk kb-ae-werkbalk-los";
      balk = document.createElement("div");
      balk.className = "kb-ae-werkbalk-in";
      balk.setAttribute("role", "toolbar");
      balk.setAttribute("aria-label", "Opmaak van de tekst");
      los.appendChild(balk);
      textarea.parentNode.insertBefore(los, textarea);
    }
    balk.dataset.kbInGebruik = "1";
    var editor = window.KBArtikelEditor.maak(textarea, {
      werkbalk: balk,
      marge: artikel ? document.getElementById("kb-marge") : null,
      eenvoudig: !artikel,
    });
    if (artikel) {
      inhoudEditor = editor;  // voor de kladversie en het slot
      window.kbInhoudEditor = editor;
    }
  }

  function initAll(scope) {
    (scope || document).querySelectorAll("textarea.kb-editor").forEach(function (t) {
      // Het lege sjabloon van Django's inline ('__prefix__') niet initialiseren.
      if (t.name.indexOf("__prefix__") !== -1) return;
      init(t);
    });
  }

  /* ----------------------------------------------------------------------------------------
   * Zacht slot, beveiligingscode en de toelichting bij opslaan.
   *
   * Het bewerkscherm meldt elke 30 seconden aan de server dat het nog openstaat. Dat doet drie
   * dingen tegelijk: het houdt de claim op dit artikel levend, het vertelt wie er nog meer in zit,
   * en het merkt het meteen als de beveiligingscode (CSRF) niet meer geldig is — bijvoorbeeld
   * doordat de redacteur in een ander tabblad opnieuw is ingelogd. Dat laatste zou anders pas bij
   * het opslaan blijken, met een foutpagina en een leeg scherm als resultaat.
   * -------------------------------------------------------------------------------------- */
  var HARTSLAG_MS = 30000;

  function veld(naam) { return document.querySelector('[name="' + naam + '"]'); }

  function vensterTonen(opties) {
    var laag = document.createElement("div");
    laag.className = "kb-venster-laag";
    var vak = document.createElement("div");
    vak.className = "kb-venster";
    var titel = document.createElement("h2");
    titel.textContent = opties.titel;
    vak.appendChild(titel);
    (opties.alineas || []).forEach(function (t) { var p = document.createElement("p"); p.textContent = t; vak.appendChild(p); });
    if (opties.inhoud) vak.appendChild(opties.inhoud);
    var rij = document.createElement("div");
    rij.className = "kb-venster-knoppen";
    (opties.knoppen || []).forEach(function (k) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "button" + (k.primair ? "" : " kb-knop-rustig");
      b.textContent = k.tekst;
      b.addEventListener("click", function () { if (k.doen && k.doen() === false) return; sluit(); });
      rij.appendChild(b);
    });
    vak.appendChild(rij);
    laag.appendChild(vak);
    document.body.appendChild(laag);
    function sluit() { if (laag.parentNode) laag.parentNode.removeChild(laag); }
    var eerste = vak.querySelector("textarea, input, button");
    if (eerste) eerste.focus();
    return { sluit: sluit, vak: vak };
  }

  function balkTonen(klasse, tekst) {
    var bestaand = document.querySelector("." + klasse);
    if (bestaand) { bestaand.textContent = tekst; return; }
    var balk = document.createElement("div");
    balk.className = "kb-melding " + klasse;
    balk.setAttribute("role", "status");
    balk.textContent = tekst;
    var doel = document.querySelector("#content h1") || document.querySelector("#content");
    if (doel && doel.parentNode) doel.parentNode.insertBefore(balk, doel.nextSibling);
  }

  function zachtSlot() {
    var pad = location.pathname.match(/^(.*)\/kennisbank\/artikel\/(\d+)\/change\//);
    var form = document.querySelector("#artikel_form, form#content-main form, #content form");
    if (!pad || !form) return;
    var url = pad[1] + "/kennisbank/artikel/" + pad[2] + "/bewerkclaim/";
    var bekend = {};
    var eerste = true;
    var codeVerlopen = false;

    function token() { var t = form.querySelector('[name="csrfmiddlewaretoken"]'); return t ? t.value : ""; }

    function ping(stoppen) {
      var body = new URLSearchParams();
      body.set("csrfmiddlewaretoken", token());
      if (stoppen) body.set("stoppen", "1");
      return fetch(url, { method: "POST", body: body, credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" } })
        .then(function (r) {
          if (r.status === 403 || r.status === 401) { codeVerlopenMelden(); return null; }
          return r.ok ? r.json() : null;
        })
        .catch(function () { return null; });
    }

    function codeVerlopenMelden() {
      if (codeVerlopen) return;
      codeVerlopen = true;
      var veilig = window.kbKladNu ? window.kbKladNu() : false;
      balkTonen(
        "kb-melding-fout",
        "Let op: dit scherm is verlopen, waarschijnlijk doordat je in een ander tabblad opnieuw bent " +
          "ingelogd. Opslaan lukt nu niet. " +
          (veilig
            ? "Je werk staat veilig in deze browser: ververs de pagina met Ctrl+F5 en kies daarna 'Verder gaan'."
            : "Kopieer je tekst, ververs deze pagina met Ctrl+F5 en plak hem terug.")
      );
    }

    function anderenVerwerken(gegevens) {
      if (!gegevens) return;
      var anderen = gegevens.anderen || [];
      if (eerste) {
        eerste = false;
        anderen.forEach(function (a) { bekend[a.naam] = true; });
        if (anderen.length) {
          var wie = anderen.map(function (a) { return a.naam + " (sinds " + a.sinds + ")"; }).join(", ");
          vensterTonen({
            titel: "Iemand anders bewerkt dit artikel",
            alineas: [
              wie + " heeft dit artikel nu ook open.",
              "Als jullie allebei opslaan, kan het werk van de een dat van de ander overschrijven. " +
                "Overleg even voordat je verdergaat.",
            ],
            knoppen: [
              { tekst: "Terug naar de lijst", doen: function () { location.href = pad[1] + "/kennisbank/artikel/"; } },
              { tekst: "Toch bewerken", primair: true },
            ],
          });
        }
        return;
      }
      anderen.forEach(function (a) {
        if (bekend[a.naam]) return;
        bekend[a.naam] = true;
        balkTonen("kb-melding-let-op", "Let op: " + a.naam + " heeft dit artikel zojuist ook geopend.");
      });
    }

    ping(false).then(anderenVerwerken);
    setInterval(function () { ping(false).then(anderenVerwerken); }, HARTSLAG_MS);
    window.addEventListener("pagehide", function () {
      var body = new URLSearchParams();
      body.set("csrfmiddlewaretoken", token());
      body.set("stoppen", "1");
      if (navigator.sendBeacon) navigator.sendBeacon(url, body);
    });
    form.addEventListener("submit", function () { codeVerlopen = false; });
    window.kbCodeVerlopen = function () { return codeVerlopen; };
  }

  /* ----------------------------------------------------------------------------------------
   * Kladversie: onopgeslagen werk bewaren.
   *
   * - De browser houdt elke paar seconden een kopie bij (localStorage). Dat werkt ook zonder
   *   verbinding, en overleeft een verlopen sessie, een crash en een dichtgeklapte laptop.
   * - De server krijgt de kladversie elke twee minuten als er iets is veranderd, direct als de
   *   verbinding terugkomt, en bij het sluiten of wegklikken van het tabblad.
   * - Bij openen: staat er een kladversie die afwijkt van wat er nu in het formulier staat, dan vraagt
   *   het scherm of je verder wilt gaan. Terugzetten zet ook het oude stempel terug, zodat de
   *   conflictcontrole aanslaat als iemand anders intussen heeft opgeslagen.
   *
   * Pas een kladversie als iemand echt iets heeft gedaan. De editor maakt de HTML na het laden soms
   * net anders op; zonder die drempel zou alleen al het openen van een artikel een kladversie geven.
   * -------------------------------------------------------------------------------------- */
  var KLAD_LOKAAL_MS = 3000;     // zo vaak kijken of er iets is veranderd, en dan de browserkopie bijwerken
  var KLAD_SERVER_MS = 120000;   // zo vaak naar de server, als er sinds de vorige keer iets is veranderd
  var KLAD_TEKST = ["titel", "samenvatting", "inhoud", "soort", "omgeving", "eigenaar", "tags_tekst"];
  var KLAD_LIJST = ["clusters", "zaaktypen"];
  var inhoudEditor = null;

  function kladversie() {
    // Bij een spoedcorrectie geen kladversie: die hoort bij het werk aan de conceptversie.
    if (document.getElementById("kb-spoed")) return;
    var m = location.pathname.match(/^(.*)\/kennisbank\/artikel\/(?:(\d+)\/change|add)\/$/);
    var form = document.querySelector("#artikel_form, form#content-main form, #content form");
    if (!m || !form) return;
    var url = m[1] + "/kennisbank/artikel/" + (m[2] ? m[2] + "/" : "") + "kladversie/";
    var sleutel = null, bewaardagen = 30, verschil = 0, heeftGewerkt = false, klaar = false;
    // Servertijd waarop dit scherm zijn kladversie ophaalde. De server weigert een kladversie te
    // heropenen die ná dit moment is afgesloten: dan is het werk uit dit scherm al opgeslagen.
    var geopendOp = "";
    // Gezet zodra het formulier wordt verstuurd. Daarna geen kladversie meer naar de server: het
    // opslaan sluit hem af, en een baken bij het verlaten van de pagina zou hem weer openen.
    var bezigMetOpslaan = false;
    var basisTekst = null, laatsteLokaal = null, laatsteServer = null, geenVerbindingGemeld = false;

    var nu = function () { return Date.now() + verschil; };  // servertijd, zodat een scheve klok niet uitmaakt
    function el(naam) { return form.elements.namedItem(naam); }  // ook velden die naar het volledige scherm zijn verhuisd
    function token() { var t = form.querySelector('[name="csrfmiddlewaretoken"]'); return t ? t.value : ""; }

    function lees() {
      var v = {};
      KLAD_TEKST.forEach(function (n) {
        if (n === "inhoud" && inhoudEditor) { v.inhoud = inhoudEditor.value; return; }
        var e = el(n);
        if (e && typeof e.value === "string") v[n] = e.value;
      });
      KLAD_LIJST.forEach(function (n) {
        var naar = document.getElementById("id_" + n + "_to");  // Django's twee-vakken-widget
        var e = naar || el(n);
        if (!e || !e.options) return;
        v[n] = Array.prototype.slice.call(e.options).filter(function (o) { return naar ? true : o.selected; }).map(function (o) { return o.value; });
      });
      return v;
    }
    function tekst(v) { return JSON.stringify(v); }
    function stempel() { var s = el("geladen_stempel"); return s ? s.value : ""; }

    function zetLijst(n, waarden) {
      var gewenst = {};
      (waarden || []).forEach(function (w) { gewenst[w] = true; });
      try {
        var van = "id_" + n + "_from", naar = "id_" + n + "_to";
        if (window.SelectBox && document.getElementById(van) && document.getElementById(naar)) {
          window.SelectBox.move_all(naar, van);
          Array.prototype.slice.call(document.getElementById(van).options).forEach(function (o) { o.selected = !!gewenst[o.value]; });
          window.SelectBox.move(van, naar);
          if (window.SelectFilter && window.SelectFilter.refresh_icons) window.SelectFilter.refresh_icons("id_" + n);
          return;
        }
        var e = el(n);
        if (e && e.options) Array.prototype.slice.call(e.options).forEach(function (o) { o.selected = !!gewenst[o.value]; });
      } catch (fout) { /* clusters en zaaktypen zijn een extraatje; de tekst is wat telt */ }
    }

    function zet(v, basis) {
      KLAD_TEKST.forEach(function (n) {
        if (!(n in v)) return;
        if (n === "inhoud" && inhoudEditor) { inhoudEditor.value = v.inhoud; inhoudEditor.synchronizeValues(); return; }
        var e = el(n);
        if (e && typeof e.value === "string") e.value = v[n];
      });
      KLAD_LIJST.forEach(function (n) { if (n in v) zetLijst(n, v[n]); });
      if (basis && el("geladen_stempel")) el("geladen_stempel").value = basis;
    }

    /* --- browserkopie ------------------------------------------------------------------ */
    function lokaal() {
      if (!sleutel) return null;
      try { var x = JSON.parse(localStorage.getItem(sleutel) || "null"); return x && x.velden ? x : null; } catch (e) { return null; }
    }
    function lokaalWeg() { try { if (sleutel) localStorage.removeItem(sleutel); } catch (e) {} }
    function lokaalBewaren(velden, opServer) {
      if (!sleutel) return false;
      try {
        localStorage.setItem(sleutel, JSON.stringify({ velden: velden, basis_stempel: stempel(), bewaard_op: nu(), op_server: !!opServer }));
        return true;
      } catch (e) { return false; }  // vol of uitgeschakeld: de serverkopie blijft
    }

    /* --- melding rechtsonder ----------------------------------------------------------- */
    var meldTimer = null;
    function meld(tekstje, blijvend) {
      var t = document.getElementById("kb-klad-melding");
      if (!t) {
        t = document.createElement("div");
        t.id = "kb-klad-melding";
        t.setAttribute("role", "status");
        t.setAttribute("aria-live", "polite");
        document.body.appendChild(t);
      }
      t.textContent = tekstje;
      t.classList.add("zichtbaar");
      t.classList.toggle("offline", !!blijvend);
      clearTimeout(meldTimer);
      if (!blijvend) meldTimer = setTimeout(function () { t.classList.remove("zichtbaar"); }, 3500);
    }
    function tijd() { var d = new Date(); return ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2); }

    /* --- server ------------------------------------------------------------------------- */
    function body(velden, weggooien) {
      var b = new URLSearchParams();
      b.set("csrfmiddlewaretoken", token());
      if (weggooien) b.set("weggooien", "1");
      else { b.set("velden", JSON.stringify(velden)); b.set("basis_stempel", stempel()); b.set("geopend_op", geopendOp); }
      return b;
    }
    function naarServer(dringend) {
      if (!klaar || !heeftGewerkt || bezigMetOpslaan) return;
      var velden = lees(), s = tekst(velden);
      if (s === basisTekst || s === laatsteServer) return;
      if (!dringend && !navigator.onLine) { geenVerbinding(); return; }
      fetch(url, { method: "POST", body: body(velden), credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" } })
        .then(function (r) {
          if (!r.ok) return;  // 403: het zachte slot meldt de verlopen code al; de browserkopie is het vangnet
          laatsteServer = s;
          if (tekst(lees()) === s) lokaalBewaren(velden, true);
          geenVerbindingGemeld = false;
          meld("Kladversie opgeslagen om " + tijd());
        })
        .catch(geenVerbinding);
    }
    function geenVerbinding() {
      if (geenVerbindingGemeld) return;
      geenVerbindingGemeld = true;
      kladNu();
      meld("Geen verbinding. Je werk wordt in deze browser bewaard en gaat naar de server zodra de verbinding terug is.", true);
    }
    function bakenBijVertrek() {
      if (!klaar || !heeftGewerkt || bezigMetOpslaan) return;
      var velden = lees(), s = tekst(velden);
      if (s === basisTekst) return;
      lokaalBewaren(velden, false);
      if (s !== laatsteServer && navigator.sendBeacon && navigator.sendBeacon(url, body(velden))) laatsteServer = s;
    }

    /* Nu meteen in de browser vastleggen. Voor de melding "dit scherm is verlopen". */
    function kladNu() {
      if (!klaar || !heeftGewerkt) return false;
      var velden = lees();
      if (tekst(velden) === basisTekst) return false;
      return lokaalBewaren(velden, false);
    }
    window.kbKladNu = kladNu;

    /* --- elke paar seconden ------------------------------------------------------------ */
    function controle() {
      if (!klaar) return;
      var velden = lees(), s = tekst(velden);
      if (!heeftGewerkt) { basisTekst = s; return; }  // zolang niemand iets deed, verschuift het vertrekpunt mee
      if (s === basisTekst || s === laatsteLokaal) return;
      laatsteLokaal = s;
      lokaalBewaren(velden, s === laatsteServer);
    }

    ["input", "keydown", "paste", "drop", "cut", "change"].forEach(function (soort) {
      document.addEventListener(soort, function (e) {
        var toets = e.key || "";
        // Rondkijken is geen werk: tab, pijltjes, shift en kopiëren veranderen niets.
        if (soort === "keydown" && (toets === "Tab" || toets === "Shift" || toets.indexOf("Arrow") === 0 || (e.ctrlKey && toets === "c"))) return;
        if (e.target && e.target.closest && e.target.closest(".kb-venster")) return;  // typen in een vraagvenster telt niet
        heeftGewerkt = true;
      }, true);
    });
    document.addEventListener("click", function (e) {
      // Werkbalkknoppen (vet, lijst, sectie) en de pijltjes van clusters en zaaktypen veranderen
      // de inhoud zonder dat er getypt wordt.
      if (e.target.closest && e.target.closest(".kb-ae-werkbalk, .kb-ae-menu, .selector-chooser, .selector-chooseall, .selector-clearall")) heeftGewerkt = true;
    }, true);

    /* --- bij openen: is er een kladversie? -------------------------------------------- */
    function voorproefje(v) {
      // Een inerte parser: in een DOMParser-document laadt en draait niets.
      var t = "";
      try {
        var doc = new DOMParser().parseFromString(v.inhoud || "", "text/html");
        // Een spatie achter elk blok, anders plakken kop en alinea aan elkaar ("Brief opstellenSjablonen").
        doc.body.querySelectorAll("p,li,h1,h2,h3,h4,h5,h6,div,section,td,th,br").forEach(function (n) { n.appendChild(doc.createTextNode(" ")); });
        t = doc.body.textContent || "";
      } catch (e) {}
      t = t.replace(/\s+/g, " ").trim();
      return t.length > 220 ? t.slice(0, 220) + "…" : t;
    }

    function vraag(kandidaat, huidigStempel) {
      var inhoud = document.createElement("div");
      var regel = document.createElement("p");
      regel.className = "kb-klad-voorproef";
      var titel = document.createElement("strong");
      titel.textContent = kandidaat.velden.titel || "(zonder titel)";
      regel.appendChild(titel);
      var stukje = voorproefje(kandidaat.velden);
      if (stukje) { regel.appendChild(document.createElement("br")); regel.appendChild(document.createTextNode(stukje)); }
      inhoud.appendChild(regel);
      var alineas = ["Er staat een kladversie klaar van " + kandidaat.tijd + ". Verder gaan waar je gebleven was?"];
      if (kandidaat.basis_stempel && huidigStempel && kandidaat.basis_stempel !== huidigStempel) {
        alineas.push(
          "Let op: het artikel is opgeslagen nadat je aan deze kladversie begon. Ga je verder en sla je op, " +
            "dan meldt het scherm dat er intussen iets is veranderd, zodat je niemands werk overschrijft."
        );
      }
      var voorAanpassing = tekst(lees());
      wachtOpVrijScherm(function () {
        vensterTonen({
          titel: "Verder gaan waar je gebleven was?",
          alineas: alineas,
          inhoud: inhoud,
          knoppen: [
            {
              tekst: "Weggooien",
              doen: function () {
                lokaalWeg();
                fetch(url, { method: "POST", body: body(null, true), credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" } })
                  .then(function (r) { return r.ok ? r.json() : null; })
                  .then(function (j) { if (j && j.server_nu) geopendOp = j.server_nu; })  // nieuw werk in dit scherm mag weer
                  .catch(function () {});
                basisTekst = tekst(lees());
                laatsteServer = null;
                heeftGewerkt = false;
              },
            },
            {
              tekst: "Verder gaan",
              primair: true,
              doen: function () {
                zet(kandidaat.velden, kandidaat.basis_stempel);
                // Het vertrekpunt blijft het artikel zoals het was: de teruggezette tekst is
                // onopgeslagen werk en moet dus ook bewaard blijven.
                basisTekst = voorAanpassing;
                heeftGewerkt = true;
                laatsteLokaal = null;
                controle();
                meld("Kladversie teruggezet. Vergeet niet op te slaan.");
              },
            },
          ],
        });
      });
    }

    function wachtOpVrijScherm(daarna) {
      // Het zachte slot kan net een eigen vraag tonen ("iemand anders bewerkt dit artikel").
      var pogingen = 0;
      (function kijk() {
        if (!document.querySelector(".kb-venster-laag") || pogingen++ > 200) daarna();
        else setTimeout(kijk, 300);
      })();
    }

    function anderenTonen(anderen) {
      if (!anderen || !anderen.length) return;
      var balk = document.createElement("div");
      balk.className = "kb-melding kb-melding-klad";
      balk.setAttribute("role", "status");
      anderen.forEach(function (a, i) {
        if (i) balk.appendChild(document.createElement("br"));
        balk.appendChild(document.createTextNode(a.naam + " heeft een kladversie van dit artikel (laatst " + a.tijd + "). "));
        var link = document.createElement("a");
        link.href = a.url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = "Bekijken";
        balk.appendChild(link);
      });
      var doel = document.querySelector("#content h1") || document.querySelector("#content");
      if (doel && doel.parentNode) doel.parentNode.insertBefore(balk, doel.nextSibling);
    }

    function verwerk(g) {
      sleutel = g.sleutel;
      bewaardagen = g.bewaardagen || 30;
      verschil = Date.parse(g.server_nu) - Date.now() || 0;
      geopendOp = g.server_nu || "";
      anderenTonen(g.anderen);
      var plaatselijk = lokaal();
      if (plaatselijk && nu() - plaatselijk.bewaard_op > bewaardagen * 864e5) { lokaalWeg(); plaatselijk = null; }
      var afgesloten = g.afgesloten_op ? Date.parse(g.afgesloten_op) : null;
      var server = g.mijn ? { velden: g.mijn.velden, basis_stempel: g.mijn.basis_stempel, bewaard_op: Date.parse(g.mijn.bijgewerkt_op), tijd: g.mijn.tijd } : null;
      if (plaatselijk) {
        // Wist de server de kladversie (opgeslagen, weggegooid of opgeruimd), dan ook de kopie die hij al kende.
        if (plaatselijk.op_server && !server) { lokaalWeg(); plaatselijk = null; }
        // Werk dat nooit de server bereikte, maar daarna toch is opgeslagen of weggegooid.
        else if (!plaatselijk.op_server && afgesloten && plaatselijk.bewaard_op <= afgesloten) { lokaalWeg(); plaatselijk = null; }
      }
      if (plaatselijk) {
        var d = new Date(plaatselijk.bewaard_op - verschil);
        plaatselijk.tijd = (d.toDateString() === new Date().toDateString() ? "" : d.getDate() + "-" + (d.getMonth() + 1) + " ") +
          ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2);
      }
      var kandidaat = server;
      if (plaatselijk && (!server || plaatselijk.bewaard_op > server.bewaard_op)) kandidaat = plaatselijk;
      klaar = true;
      basisTekst = tekst(lees());
      if (server) laatsteServer = tekst(server.velden);
      if (!kandidaat) return;
      // Staat de kladversie er al (bijvoorbeeld na een mislukte opslag), dan valt er niets te vragen.
      var huidig = lees(), anders = Object.keys(kandidaat.velden).some(function (n) { return tekst(huidig[n]) !== tekst(kandidaat.velden[n]); });
      if (!anders) { heeftGewerkt = true; return; }
      vraag(kandidaat, g.huidig_stempel);
    }

    var wachttijden = [0, 5000, 15000, 30000];
    function ophalen(poging) {
      fetch(url, { credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" } })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(verwerk)
        .catch(function () { setTimeout(function () { ophalen(poging + 1); }, wachttijden[Math.min(poging + 1, wachttijden.length - 1)] || 60000); });
    }
    // Even wachten tot de editor de tekst heeft opgemaakt, anders telt dat als een verschil.
    setTimeout(function () { ophalen(0); }, 600);
    setInterval(controle, KLAD_LOKAAL_MS);
    setInterval(function () { naarServer(false); }, KLAD_SERVER_MS);
    window.addEventListener("online", function () { geenVerbindingGemeld = false; meld("Verbinding terug."); naarServer(true); });
    window.addEventListener("offline", geenVerbinding);
    window.addEventListener("pagehide", bakenBijVertrek);
    document.addEventListener("visibilitychange", function () { if (document.visibilityState === "hidden") bakenBijVertrek(); });
    // Bij opslaan: de laatste stand nog even in de browser, voor het geval het verzenden mislukt, en
    // daarna niets meer naar de server. Houdt een andere controle het versturen tegen (preventDefault),
    // dan gaat het gewoon door zoals daarvoor. Komt het scherm terug met een foutmelding, dan is de
    // pagina opnieuw geladen en staat de vlag vanzelf weer uit.
    form.addEventListener("submit", function (e) {
      kladNu();
      bezigMetOpslaan = true;
      setTimeout(function () { if (e.defaultPrevented) bezigMetOpslaan = false; }, 0);
    });
    // Conceptversie weggooien: dan hoort ook de kopie in deze browser weg, anders vraagt het scherm
    // straks "verder gaan?" met het werk dat je net bewust hebt weggegooid.
    form.addEventListener("submit", function (e) {
      if (e.submitter && e.submitter.name === "_weggooien") lokaalWeg();
    });
    // Afronden → Afbreken: de kladversie van dit scherm weggooien, in de browser en op de server, en
    // daarna niets meer bewaren (ook niet bij het verlaten van de pagina).
    window.kbKladAfbreken = function () {
      bezigMetOpslaan = true;
      lokaalWeg();
      var data = new FormData();
      data.append("weggooien", "1");
      return fetch(url, {
        method: "POST", credentials: "same-origin", body: data,
        headers: { "X-CSRFToken": token(), "X-Requested-With": "XMLHttpRequest" },
      });
    };
  }

  /* Eén knop Afronden met een keuzevenster (bouwlijst 1.21.0). Het venster drukt op de bestaande
   * knoppen, zodat alles wat daaraan vastzit blijft werken: de vraag om een toelichting, de bevestiging
   * bij werk van een collega, het opruimen van de kladversie. Zonder JavaScript blijven die knoppen gewoon
   * in beeld. */
  function afronden() {
    var data = document.getElementById("kb-afronden");
    var form = document.querySelector("#artikel_form");
    if (!data || !form) return;
    var cfg;
    try { cfg = JSON.parse(data.textContent); } catch (e) { return; }
    // De knop staat sinds 1.22.0 in de balk bovenaan (artikel-scherm.js verhuist hem); nog steeds in het formulier.
    var knop = form.querySelector(".kb-afronden-knop");
    if (!knop) return;
    form.classList.add("kb-met-afronden");

    function klik(selector) {
      var b = form.querySelector(selector);
      if (b) b.click();
      return !!b;
    }
    function gewijzigd() {
      var begin = window.kbBeginwaarden || {};
      return Object.keys(begin).some(function (naam) { var el = veld(naam); return el && el.value !== begin[naam]; });
    }
    function afbreken() {
      vensterTonen({
        titel: "Afbreken zonder opslaan?",
        alineas: [
          "Wat je sinds het laatste opslaan hebt veranderd, gaat verloren.",
          cfg.concept ? "De conceptversie zoals die is opgeslagen, blijft gewoon staan." : "Medewerkers blijven de gepubliceerde versie zien.",
        ],
        knoppen: [
          { tekst: "Nee, verder werken" },
          {
            tekst: "Ja, afbreken", primair: true, doen: function () {
              var weg = function () { location.href = cfg.werkplek; };
              if (window.kbKladAfbreken) window.kbKladAfbreken().then(weg, weg); else weg();
            },
          },
        ],
      });
    }
    function terInzage() {
      var vak = document.createElement("div");
      vak.className = "kb-venster-veld kb-afronden-teamkeuze";
      var vinkjes = cfg.teams.map(function (t) {
        var l = document.createElement("label");
        l.className = "kb-venster-keuze";
        var hok = document.createElement("input");
        hok.type = "checkbox";
        hok.value = t.pk;
        hok.checked = !!t.gekozen;
        l.appendChild(hok);
        l.appendChild(document.createTextNode(" " + t.naam));
        vak.appendChild(l);
        return hok;
      });
      var fout = document.createElement("p");
      fout.className = "kb-venster-fout";
      fout.hidden = true;
      vak.appendChild(fout);
      vensterTonen({
        titel: "Ter inzage aanbieden",
        alineas: [
          "Je wijzigingen worden eerst opgeslagen als conceptversie. Daarna gaat precies die tekst naar het team, en staat hij op slot tot het team reageert of je hem terugroept.",
          "Aan welk team?",
        ],
        inhoud: vak,
        knoppen: [
          { tekst: "Annuleren" },
          {
            tekst: "Opslaan en ter inzage geven", primair: true, doen: function () {
              var gekozen = vinkjes.filter(function (h) { return h.checked; });
              if (!gekozen.length) {
                fout.textContent = "Kies minstens één reviewteam.";
                fout.hidden = false;
                return false;
              }
              var doel = document.getElementById("kb-afronden-teams");
              doel.textContent = "";
              gekozen.forEach(function (h) {
                var i = document.createElement("input");
                i.type = "hidden";
                i.name = "reviewteams";
                i.value = h.value;
                doel.appendChild(i);
              });
              document.getElementById("kb-daarna-ter-inzage").value = "1";
              setTimeout(function () { klik('button[name="_conceptversie"]'); }, 0);
            },
          },
        ],
      });
    }

    knop.addEventListener("click", function () {
      var keuzes = [];
      if (cfg.op_slot) {
        keuzes.push({ tekst: "Terugroepen", uitleg: "Haal de conceptversie terug bij het reviewteam. Daarna kun je weer bewerken, publiceren of weggooien.", doen: function () { klik('button[name="_terugroepen"]'); } });
      } else {
        if (!cfg.spoed) {
          keuzes.push({ tekst: "Opslaan als concept", uitleg: "Medewerkers merken niets. Je kunt later verder.", doen: function () { klik('button[name="_conceptversie"]'); } });
          if (cfg.teams.length) keuzes.push({ tekst: "Ter inzage aanbieden", uitleg: "Eerst opslaan, dan naar een reviewteam.", doen: terInzage });
        }
        keuzes.push({ tekst: "Publiceren", uitleg: cfg.spoed ? "De correctie gaat meteen live voor alle medewerkers." : "Alle medewerkers zien deze tekst meteen.", doen: function () { klik('input[name="_save"].kb-publiceren'); } });
      }
      keuzes.push({ tekst: "Afbreken", uitleg: "Sluiten zonder op te slaan.", doen: afbreken, rustig: true });

      var lijst = document.createElement("div");
      lijst.className = "kb-afronden-keuzes";
      var venster;
      keuzes.forEach(function (k) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "kb-afronden-keuze" + (k.rustig ? " kb-afronden-rustig" : "");
        var t = document.createElement("strong");
        t.textContent = k.tekst;
        var u = document.createElement("span");
        u.textContent = k.uitleg;
        b.appendChild(t);
        b.appendChild(u);
        b.addEventListener("click", function () { venster.sluit(); setTimeout(k.doen, 0); });
        lijst.appendChild(b);
      });
      var alineas = [];
      if (cfg.akkoord && gewijzigd()) alineas.push("Let op: je hebt de tekst gewijzigd na het akkoord van het reviewteam. Sla je op of publiceer je, dan geldt het akkoord niet meer.");
      venster = vensterTonen({ titel: "Afronden", alineas: alineas, inhoud: lijst, knoppen: [{ tekst: "Annuleren" }] });
    });

    // Na een akkoord: meteen zeggen dat wijzigen het akkoord laat vervallen (review 1.20.1, bevinding 1).
    if (cfg.akkoord) {
      var gemeld = false;
      form.addEventListener("input", function () {
        if (gemeld || !gewijzigd()) return;
        gemeld = true;
        balkTonen("kb-akkoord-let", "Let op: je wijzigt de tekst na het akkoord van het reviewteam. Sla je dit op of publiceer je het, dan vervalt het akkoord.");
      });
    }
  }

  /* De toelichting bij publiceren staat buiten het volledige scherm. Zonder deze controle zou
   * opslaan vanuit het volledige scherm stilletjes mislukken op een foutmelding die je niet ziet. */
  function publicerenVersturen() {
    var form = document.querySelector("#artikel_form");
    var knop = form && form.querySelector('input[name="_save"]');
    if (knop) { knop.dataset.toelichtingGevraagd = "1"; knop.click(); }
  }

  function toelichtingNodig(beginwaarden) {
    var status = veld("status");
    if (!status || status.value !== "gepubliceerd") return false;
    var hint = veld("al_gepubliceerd");
    if (!hint || !hint.value) return false;
    var toel = veld("wijzigingstoelichting");
    var klein = veld("kleine_correctie");
    if (toel && toel.value.trim()) return false;
    if (klein && klein.checked) return false;
    // Een conceptversie verschilt per definitie van wat medewerkers nu zien.
    if (document.querySelector('input[name="kb_conceptmodus"]')) return true;
    return Object.keys(beginwaarden).some(function (naam) {
      var el = veld(naam);
      return el && el.value !== beginwaarden[naam];
    });
  }

  function vraagToelichting(melding, daarna) {
    var toel = veld("wijzigingstoelichting");
    var klein = veld("kleine_correctie");
    var vak = document.createElement("div");
    vak.className = "kb-venster-veld";
    var label = document.createElement("label");
    label.textContent = "Wat is er gewijzigd?";
    label.setAttribute("for", "kb-toel");
    var invoer = document.createElement("textarea");
    invoer.id = "kb-toel";
    invoer.rows = 3;
    invoer.maxLength = 300;
    invoer.value = toel ? toel.value : "";
    var keuze = document.createElement("label");
    keuze.className = "kb-venster-keuze";
    var hok = document.createElement("input");
    hok.type = "checkbox";
    keuze.appendChild(hok);
    keuze.appendChild(document.createTextNode(" Kleine correctie (typfout of opmaak): geen melding en geen e-mail"));
    var fout = document.createElement("p");
    fout.className = "kb-venster-fout";
    fout.hidden = true;
    vak.appendChild(label);
    vak.appendChild(invoer);
    vak.appendChild(keuze);
    vak.appendChild(fout);
    function opslaan() {
      if (!hok.checked && !invoer.value.trim()) {
        fout.textContent = "Geef in één zin aan wat er is gewijzigd, of vink 'Kleine correctie' aan.";
        fout.hidden = false;
        invoer.focus();
        return false;
      }
      if (toel) toel.value = invoer.value;
      if (klein) klein.checked = hok.checked;
      if (daarna) daarna();
      return true;
    }
    hok.addEventListener("change", function () { invoer.disabled = hok.checked; });
    vensterTonen({
      titel: "Wat is er gewijzigd?",
      alineas: [
        melding ||
          "Dit artikel is gepubliceerd. Medewerkers krijgen jouw toelichting als melding te zien; " +
            "wie het als favoriet heeft, krijgt hem per e-mail.",
      ],
      inhoud: vak,
      knoppen: [{ tekst: "Annuleren" }, { tekst: "Publiceren", primair: true, doen: opslaan }],
    });
    return true;
  }

  window.kbMelding = function (opties) {
    vensterTonen({ titel: opties.titel, alineas: opties.alineas, knoppen: [{ tekst: "Sluiten", primair: true }] });
  };
  window.kbToelichtingNodig = toelichtingNodig;
  window.kbVenster = vensterTonen;
  window.kbVraagToelichting = vraagToelichting;

  /* Suggestielijst bij het tagveld: kijkt alleen naar het stukje achter de laatste komma. */
  function tagSuggesties() {
    var doos = document.querySelector(".kb-tagsuggesties");
    var invoer = veld("tags_tekst");
    if (!doos || !invoer) return;
    var alle = [];
    try { alle = JSON.parse(doos.getAttribute("data-tags") || "[]"); } catch (e) { return; }
    var actief = -1;

    function huidigDeel() {
      var tot = invoer.value.slice(0, invoer.selectionStart === null ? invoer.value.length : invoer.selectionStart);
      var komma = tot.lastIndexOf(",");
      return tot.slice(komma + 1).trim().toLowerCase();
    }
    function alGekozen() {
      return invoer.value.split(",").map(function (t) { return t.trim().toLowerCase(); }).filter(Boolean);
    }
    function kies(naam) {
      var delen = invoer.value.split(",");
      delen[delen.length - 1] = " " + naam;
      invoer.value = delen.join(",").replace(/^[\s,]+/, "") + ", ";
      invoer.focus();
      toon();
    }
    function toon() {
      var deel = huidigDeel(), gekozen = alGekozen();
      var lijst = alle.filter(function (t) {
        return gekozen.indexOf(t.naam) === -1 && (!deel || t.naam.indexOf(deel) !== -1);
      }).slice(0, 10);
      doos.innerHTML = "";
      if (!lijst.length) { doos.hidden = true; return; }
      lijst.forEach(function (t, i) {
        var r = document.createElement("button");
        r.type = "button";
        r.className = "kb-tagsuggestie" + (i === actief ? " actief" : "");
        r.innerHTML = "";
        var naam = document.createElement("span"); naam.textContent = t.naam;
        var n = document.createElement("em"); n.textContent = t.aantal + "\u00d7";
        r.appendChild(naam); r.appendChild(n);
        r.addEventListener("mousedown", function (e) { e.preventDefault(); kies(t.naam); });
        doos.appendChild(r);
      });
      doos.hidden = false;
    }
    invoer.addEventListener("focus", function () { actief = -1; toon(); });
    invoer.addEventListener("input", function () { actief = -1; toon(); });
    invoer.addEventListener("blur", function () { setTimeout(function () { doos.hidden = true; }, 120); });
    invoer.addEventListener("keydown", function (e) {
      var rijen = doos.querySelectorAll(".kb-tagsuggestie");
      if (doos.hidden || !rijen.length) return;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        actief = (actief + (e.key === "ArrowDown" ? 1 : -1) + rijen.length) % rijen.length;
        toon();
      } else if ((e.key === "Enter" || e.key === "Tab") && actief >= 0) {
        e.preventDefault();
        kies(rijen[actief].querySelector("span").textContent);
      } else if (e.key === "Escape") {
        doos.hidden = true;
      }
    });
  }

  // Ligt de conceptversie ter inzage bij een reviewteam, dan staat hij op slot: alleen-lezen. Publiceren
  // kan pas na terugroepen (besluit 12 november); de server weigert het ook.
  function opSlot() {
    if (!document.getElementById("kb-op-slot")) return;
    if (inhoudEditor && inhoudEditor.setReadOnly) inhoudEditor.setReadOnly(true);
    var publicatie = veld("wijzigingstoelichting");
    document.querySelectorAll("#artikel_form fieldset.module").forEach(function (fs) {
      if (publicatie && fs.contains(publicatie)) return;
      fs.classList.add("kb-op-slot");
      fs.setAttribute("aria-disabled", "true");
      fs.querySelectorAll("input, textarea, select").forEach(function (el) {
        if (el.type === "hidden") return;
        el.setAttribute("readonly", "readonly");
        el.tabIndex = -1;
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initAll();
    opSlot();
    zachtSlot();
    tagSuggesties();
    kladversie();
    // Beginwaarden onthouden, zodat we weten of er iets inhoudelijks is veranderd.
    window.kbBeginwaarden = {};
    ["titel", "samenvatting", "inhoud", "soort", "eigenaar", "omgeving", "tags_tekst"].forEach(function (naam) {
      var el = veld(naam);
      if (el) window.kbBeginwaarden[naam] = el.value;
    });
    afronden();
    // Mislukte opslag door de ontbrekende toelichting: toon hem alsnog in beeld.
    var foutje = document.querySelector(".field-wijzigingstoelichting .errorlist li");
    // Na het invullen echt versturen: zonder vervolgactie sloot het venster en gebeurde er niets
    // (functionele review 11 november, B1).
    if (foutje) setTimeout(function () { vraagToelichting(foutje.textContent, publicerenVersturen); }, 60);
    // Publiceren vanaf de knoppen onderaan: eerst om de toelichting vragen als die nodig is, in plaats
    // van een foutmelding na het laden van de pagina.
    document.querySelectorAll('input.kb-publiceren').forEach(function (knop) {
      knop.addEventListener("click", function (e) {
        if (knop.dataset.toelichtingGevraagd === "1") return;
        var collegas = document.getElementById("kb-concept-collegas");
        var nogBevestigen = collegas && knop.dataset.collegaBevestigd !== "1";
        var toelichting = toelichtingNodig(window.kbBeginwaarden || {});
        if (!nogBevestigen && !toelichting) return;
        e.preventDefault();
        function verder() { knop.dataset.toelichtingGevraagd = "1"; knop.click(); }
        function naBevestigen() {
          knop.dataset.collegaBevestigd = "1";
          if (toelichtingNodig(window.kbBeginwaarden || {})) vraagToelichting(null, verder); else verder();
        }
        if (!nogBevestigen) { naBevestigen(); return; }
        // Werk van een collega live zetten: eerst bevestigen; de collega krijgt een e-mail (punt 4.3).
        vensterTonen({
          titel: "Werk van een collega publiceren?",
          alineas: [
            "Aan deze conceptversie werkte ook " + collegas.value + ".",
            "Publiceer je nu, dan zien alle medewerkers deze tekst en krijgt " + collegas.value + " daar een e-mail over. Overleg eerst als je twijfelt of het werk af is.",
          ],
          knoppen: [{ tekst: "Annuleren" }, { tekst: "Ja, publiceren", primair: true, doen: function () { setTimeout(naBevestigen, 0); } }],
        });
      });
    });
    // Nieuwe sectie toegevoegd via "Nog een sectie toevoegen".
    document.addEventListener("formset:added", function (e) {
      initAll(e.target);
      // Nieuwe sectie standaard achteraan.
      var volgordes = Array.from(document.querySelectorAll('input[name$="-volgorde"]')).filter(function (i) { return i.name.indexOf("__prefix__") === -1 && i.value !== ""; }).map(function (i) { return Number(i.value); });
      var nieuw = e.target.querySelector('input[name$="-volgorde"]');
      if (nieuw && volgordes.length) nieuw.value = Math.max.apply(null, volgordes) + 1;
    });
  });
})();
