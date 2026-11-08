/* Opmaak-editor voor secties in het beheerscherm (Jodit, lokaal meegeleverd).
 *
 * - Werkbalk met de basisopmaak uit Word: koppen, vet, cursief, onderstreept, doorgehaald,
 *   lijsten, inspringen, link, tabel, citaat, opmaak wissen, ongedaan maken.
 * - Knop "Sectie": zet een kader (<section class="sectie">) om de geselecteerde alinea's, met een
 *   titelbalk (<h2 class="sectie-kop">) erboven. In de kennisbank wordt dat een in- en uitklapbare
 *   sectie. Staat de cursor al in een sectie, dan haalt de knop het kader weer weg.
 * - Knop "Onboarding": markeert de geselecteerde alinea's als uitleg voor nieuwe collega's
 *   (<div class="onboarding">). Nogmaals klikken haalt de markering weg.
 * - Plakken uit Word wordt opgeschoond. De server schoont daarna nog een keer op (inhoud.py).
 */
(function () {
  "use strict";
  if (!window.Jodit) return;

  var ONB = "onboarding";
  var SEC = "sectie";

  function legeAlinea(doc) { var p = doc.createElement("p"); p.appendChild(doc.createElement("br")); return p; }

  var KOP = "sectie-kop";

  function sectieVan(node, root) {
    var el = node.nodeType === 1 ? node : node.parentNode;
    while (el && el !== root) { if (el.tagName === "SECTION" && el.classList.contains(SEC)) return el; el = el.parentNode; }
    return null;
  }

  function sectieToggle(editor) {
    var root = editor.editor, doc = root.ownerDocument, range = editor.s.range;
    var bestaand = sectieVan(range.startContainer, root);
    if (bestaand) {
      // Kader weghalen: titel wordt een gewone kop, inhoud komt op het hoogste niveau.
      var kop = bestaand.querySelector("h2." + KOP);
      if (kop) { if (kop.textContent.trim()) { var h3 = doc.createElement("h3"); h3.textContent = kop.textContent.trim(); bestaand.replaceChild(h3, kop); } else bestaand.removeChild(kop); }
      // De typ-ruimte rond het kader hoort bij het kader en gaat mee weg.
      [bestaand.previousElementSibling, bestaand.nextElementSibling].forEach(function (n) { if (n && n.tagName === "P" && n.classList.contains(RUIMTE)) n.parentNode.removeChild(n); });
      while (bestaand.firstChild) bestaand.parentNode.insertBefore(bestaand.firstChild, bestaand);
      bestaand.parentNode.removeChild(bestaand);
      ruimteRondSecties(editor);
      editor.synchronizeValues();
      return;
    }
    var start = blokVan(range.startContainer, root), eind = blokVan(range.endContainer, root);
    if (!start) { alert("Selecteer eerst de tekst die in de sectie moet komen."); return; }
    if (!eind) eind = start;
    var top = function (b) { var t = b; while (t.parentNode !== root) t = t.parentNode; return t; };
    var a = top(start), z = top(eind), blokken = [], n = a;
    while (n) { blokken.push(n); if (n === z) break; n = n.nextSibling; }
    var sec = doc.createElement("section"); sec.className = SEC;
    var titel = doc.createElement("h2"); titel.className = KOP;
    // Begint de selectie met een kop (zoals na een Word-import), dan nemen we die tekst over als
    // sectietitel in plaats van hem als dubbele kop binnen het kader te laten staan. Dat scheelt per
    // sectie twee handelingen en voorkomt kaders die voor de lezer "Sectie 1" heten omdat de titel
    // nog leeg was. De knop zelf werkt onveranderd: er ontstaat alleen een sectie als jij erop drukt.
    var kopblok = blokken.length && /^H[1-6]$/.test(blokken[0].tagName) && blokken[0].textContent.trim()
      ? blokken.shift() : null;
    if (kopblok) titel.textContent = kopblok.textContent.trim();
    else titel.appendChild(doc.createElement("br"));
    sec.appendChild(titel);
    a.parentNode.insertBefore(sec, a);
    if (kopblok) kopblok.parentNode.removeChild(kopblok);
    if (!blokken.length) { var leeg = doc.createElement("p"); leeg.appendChild(doc.createElement("br")); sec.appendChild(leeg); }
    blokken.forEach(function (b) {
      if (b.tagName === "P" && b.classList.contains(RUIMTE)) { b.parentNode.removeChild(b); return; }  // typ-ruimte hoort niet in de sectie
      if (b.tagName === "SECTION") { // een bestaande sectie in de selectie: opnemen zonder te nesten
        var k = b.querySelector("h2." + KOP); if (k) { if (k.textContent.trim()) { var h = doc.createElement("h3"); h.textContent = k.textContent.trim(); b.replaceChild(h, k); } else b.removeChild(k); }
        while (b.firstChild) sec.appendChild(b.firstChild); b.parentNode.removeChild(b);
      } else sec.appendChild(b);
    });
    ruimteRondSecties(editor);
    editor.s.setCursorIn(titel, true);
    editor.synchronizeValues();
  }

  function blokVan(node, root) {
    // Dichtstbijzijnde alinea-achtig element binnen de editor.
    var el = node.nodeType === 1 ? node : node.parentNode;
    while (el && el !== root) {
      if (/^(P|H[1-6]|UL|OL|TABLE|BLOCKQUOTE|PRE|DIV|SECTION)$/.test(el.tagName) && el.parentNode === root) return el;
      if (/^(P|H[1-6]|UL|OL|TABLE|BLOCKQUOTE|PRE|DIV)$/.test(el.tagName) && el.parentNode && el.parentNode.classList && (el.parentNode.classList.contains(ONB) || el.parentNode.classList.contains(SEC))) return el;
      el = el.parentNode;
    }
    return null;
  }

  function onboardingToggle(editor) {
    var root = editor.editor;
    var range = editor.s.range;
    var start = blokVan(range.startContainer, root);
    var eind = blokVan(range.endContainer, root);
    if (!start) { editor.alert ? editor.alert("Zet de cursor in een alinea en probeer het opnieuw.") : alert("Zet de cursor in een alinea."); return; }
    if (!eind) eind = start;

    var inOnb = start.parentNode.classList && start.parentNode.classList.contains(ONB);
    if (inOnb) {
      // Verwijderen: alle alinea's uit het blok weer op het hoogste niveau zetten.
      var wrap = start.parentNode;
      while (wrap.firstChild) wrap.parentNode.insertBefore(wrap.firstChild, wrap);
      wrap.parentNode.removeChild(wrap);
    } else {
      // Toevoegen: alle top-level blokken van start t/m eind in één div zetten.
      var top = function (b) { return (b.parentNode === root || (b.parentNode.classList && b.parentNode.classList.contains(SEC))) ? b : b.parentNode; };
      var a = top(start), z = top(eind), blokken = [], n = a;
      while (n) { blokken.push(n); if (n === z) break; n = n.nextSibling; }
      var div = root.ownerDocument.createElement("div");
      div.className = ONB;
      a.parentNode.insertBefore(div, a);
      blokken.forEach(function (b) {
        if (b.classList && b.classList.contains(ONB)) { while (b.firstChild) div.appendChild(b.firstChild); b.parentNode.removeChild(b); }
        else div.appendChild(b);
      });
    }
    editor.synchronizeValues();
  }

  /* Typ-ruimte rond secties.
   *
   * Direct vóór en na elk sectiekader staat een gemarkeerde lege regel (<p class="tussenruimte">), zodat
   * je ertussen kunt typen. Alleen die gemarkeerde regel wordt bij het opslaan weggelaten (inhoud.schoon);
   * elke andere lege regel is bewust en blijft staan.
   * - Typ je in de tussenruimte, dan wordt het een gewone alinea en komt er een nieuwe tussenruimte
   *   tussen jouw tekst en de sectie.
   * - Druk je op Enter in de tussenruimte, dan is de regel die niet meer tegen de sectie aan staat een
   *   gewone (bewuste) lege regel; de tussenruimte zelf blijft tegen de sectie aan staan.
   */
  var RUIMTE = "tussenruimte";

  function ruimteRondSecties(editor) {
    var root = editor.editor, doc = root.ownerDocument, veranderd = false;
    var isSectie = function (n) { return !!n && n.tagName === "SECTION" && n.classList.contains(SEC); };
    var isRuimte = function (n) { return !!n && n.tagName === "P" && n.classList.contains(RUIMTE); };
    var isLeeg = function (p) { return !p.textContent.replace(/ /g, " ").trim() && !p.querySelector("img,table,hr"); };
    // 1. Gemarkeerde regels die tekst hebben gekregen of niet (meer) tegen een sectie aan staan: gewone alinea.
    Array.prototype.slice.call(root.querySelectorAll("p." + RUIMTE)).forEach(function (p) {
      var naast = p.parentNode === root && (isSectie(p.previousElementSibling) || isSectie(p.nextElementSibling));
      if (!naast || !isLeeg(p)) { p.classList.remove(RUIMTE); if (!p.className) p.removeAttribute("class"); veranderd = true; }
    });
    // 2. Direct vóór en na elke sectie een tussenruimte.
    Array.prototype.slice.call(root.querySelectorAll(":scope > section." + SEC)).forEach(function (sec) {
      if (!isRuimte(sec.previousElementSibling)) { var voor = legeAlinea(doc); voor.className = RUIMTE; sec.parentNode.insertBefore(voor, sec); veranderd = true; }
      if (!isRuimte(sec.nextElementSibling)) { var na = legeAlinea(doc); na.className = RUIMTE; sec.parentNode.insertBefore(na, sec.nextSibling); veranderd = true; }
    });
    return veranderd;
  }

  /* Volledig scherm: een laag over de pagina met links de editor en rechts het voorbeeld dat live meeloopt. */
  var FRAME_URL = "/beheer/kennisbank/artikel/voorbeeld/";

  function volledigScherm(editor) {
    if (document.getElementById("kb-split")) return;
    editor.synchronizeValues();
    var form = editor.element.form || document.getElementById("artikel_form");
    // Velden vóór het verhuizen opzoeken en onthouden; daarna staan titel en samenvatting buiten het formulier.
    var velden = {};
    ["titel", "samenvatting", "soort"].forEach(function (naam) { velden[naam] = form && form.querySelector('[name="' + naam + '"]'); });
    var veld = function (naam) { return velden[naam]; };
    var val = function (naam) { var el = veld(naam); return el ? el.value : ""; };
    var container = editor.container, plek = document.createElement("div");
    plek.className = "kb-split-plek"; plek.textContent = "De tekst wordt bewerkt in volledig scherm.";
    container.parentNode.insertBefore(plek, container);

    var laag = document.createElement("div"); laag.id = "kb-split";
    laag.innerHTML =
      '<div class="kb-split-balk"><strong>Volledig scherm</strong>' +
      '<span class="kb-split-knoppen"><button type="button" class="button" id="kb-split-opslaan">Opslaan en doorgaan</button>' +
      '<button type="button" class="button" id="kb-split-sluiten">Sluiten</button></span></div>' +
      '<div class="kb-split-panelen"><div class="kb-split-links"><div class="kb-split-velden">' +
      '<label>Titel<span class="kb-split-slot" data-veld="titel"></span></label>' +
      '<label>Samenvatting<span class="kb-split-slot" data-veld="samenvatting"></span></label></div></div>' +
      '<div class="kb-split-greep" title="Sleep om de verdeling te veranderen"></div>' +
      '<div class="kb-split-rechts"><iframe title="Voorbeeld" src="' + FRAME_URL + '"></iframe></div></div>';
    document.body.appendChild(laag);
    document.body.classList.add("kb-split-open");

    // Titel en samenvatting: de echte invoervelden verhuizen mee (en straks weer terug).
    var verhuisd = [];
    ["titel", "samenvatting"].forEach(function (naam) {
      var el = veld(naam); if (!el) return;
      var anker = document.createElement("span"); anker.className = "kb-split-anker"; el.parentNode.insertBefore(anker, el);
      if (form.id) el.setAttribute("form", form.id);  // blijft bij het formulier horen, ook buiten het <form>
      laag.querySelector('.kb-split-slot[data-veld="' + naam + '"]').appendChild(el);
      verhuisd.push({ el: el, anker: anker });
    });
    laag.querySelector(".kb-split-links").appendChild(container);

    // Sleepbalk
    var panelen = laag.querySelector(".kb-split-panelen"), greep = laag.querySelector(".kb-split-greep");
    var verdeling = 50;
    try { verdeling = Number(localStorage.getItem("kb.split.verdeling")) || 50; } catch (e) {}
    function zetVerdeling(pct) { verdeling = Math.max(25, Math.min(75, pct)); panelen.style.gridTemplateColumns = verdeling + "% 8px 1fr"; }
    zetVerdeling(verdeling);
    greep.addEventListener("pointerdown", function (e) {
      e.preventDefault(); greep.setPointerCapture(e.pointerId); laag.classList.add("kb-split-sleept");
      var beweeg = function (ev) { var r = panelen.getBoundingClientRect(); zetVerdeling(((ev.clientX - r.left) / r.width) * 100); };
      var stop = function () { greep.removeEventListener("pointermove", beweeg); greep.removeEventListener("pointerup", stop); laag.classList.remove("kb-split-sleept"); try { localStorage.setItem("kb.split.verdeling", String(Math.round(verdeling))); } catch (e2) {} };
      greep.addEventListener("pointermove", beweeg); greep.addEventListener("pointerup", stop);
    });

    var frame = laag.querySelector("iframe"), klaar = false, timer = null;
    function stuur() {
      if (!klaar) return;
      editor.synchronizeValues();
      frame.contentWindow.postMessage({ type: "kb-voorbeeld", titel: val("titel"), samenvatting: val("samenvatting"), soort: val("soort"), inhoud: editor.value }, location.origin);
    }
    function geplande() { clearTimeout(timer); timer = setTimeout(stuur, 250); }
    function opKlaar(e) { if (e.origin === location.origin && e.data && e.data.type === "kb-voorbeeld-klaar") { klaar = true; stuur(); } }
    window.addEventListener("message", opKlaar);
    editor.events.on("change keyup input", geplande);
    editor.editor.addEventListener("input", geplande);
    verhuisd.forEach(function (v) { v.el.addEventListener("input", geplande); });

    function sluiten() {
      clearTimeout(timer);
      window.removeEventListener("message", opKlaar);
      editor.events.off("change keyup input", geplande);
      editor.editor.removeEventListener("input", geplande);
      verhuisd.forEach(function (v) { v.el.removeEventListener("input", geplande); v.el.removeAttribute("form"); v.anker.parentNode.insertBefore(v.el, v.anker); v.anker.parentNode.removeChild(v.anker); });
      plek.parentNode.insertBefore(container, plek); plek.parentNode.removeChild(plek);
      laag.parentNode.removeChild(laag);
      document.body.classList.remove("kb-split-open");
      document.removeEventListener("keydown", opEsc);
    }
    function opEsc(e) { if (e.key === "Escape") sluiten(); }
    document.addEventListener("keydown", opEsc);
    laag.querySelector("#kb-split-sluiten").addEventListener("click", sluiten);
    laag.querySelector("#kb-split-opslaan").addEventListener("click", function () {
      editor.synchronizeValues();
      if (window.kbCodeVerlopen && window.kbCodeVerlopen()) {
        window.kbMelding({
          titel: "Opslaan lukt nu niet",
          alineas: [
            "Dit scherm is verlopen, waarschijnlijk doordat je in een ander tabblad opnieuw bent ingelogd.",
            "Je tekst staat er nog: kopieer hem, ververs de pagina met Ctrl+F5 en plak hem terug.",
          ],
        });
        return;
      }
      function bewaren() {
        try { sessionStorage.setItem("kb.split.heropen", "1"); } catch (e) {}
        var knop = form.querySelector('input[name="_continue"]');
        if (knop) knop.click(); else form.submit();
      }
      // De toelichting bij publiceren staat op het scherm eronder; vraag hem hier, anders mislukt
      // het opslaan op een foutmelding die in het volledige scherm niet te zien is.
      if (window.kbToelichtingNodig && window.kbToelichtingNodig(window.kbBeginwaarden || {})) {
        window.kbVraagToelichting(null, bewaren);
        return;
      }
      bewaren();
    });
    editor.s.focus();
  }

  var config = {
    language: "nl",
    enter: "p",
    height: 560,
    minHeight: 300,
    toolbarAdaptive: false,
    toolbarSticky: false,
    statusbar: false,
    showCharsCounter: false,
    showWordsCounter: false,
    showXPathInStatusbar: false,
    askBeforePasteHTML: false,
    askBeforePasteFromWord: false,
    defaultActionOnPaste: "insert_clear_html",
    processPasteHTML: true,
    nl2brInPlainText: false,
    sourceEditor: "area",
    disablePlugins: ["about", "print", "file", "image", "video", "media", "source", "preview", "fullsize", "speech-recognize", "ai-assistant", "powered-by-jodit", "class-span", "font", "color", "symbols", "copy-format", "xpath", "stat"],
    controls: {
      paragraph: {
        list: { p: "Alinea", h3: "Kop", h4: "Subkop", blockquote: "Citaat" }
      }
    },
    buttons: [
      "paragraph", "|", "bold", "italic", "underline", "strikethrough", "superscript", "|",
      "ul", "ol", "outdent", "indent", "|", "link", "table", "hr", "|", "eraser", "undo", "redo", "|",
      {
        name: "volledigscherm",
        tooltip: "Volledig scherm: links bewerken, rechts live het voorbeeld",
        text: "Volledig scherm",
        exec: volledigScherm
      },
      "|",
      {
        name: "sectie",
        tooltip: "Sectie: zet een in- en uitklapbare sectie om de geselecteerde tekst (nogmaals klikken haalt het kader weg)",
        text: "Sectie",
        exec: sectieToggle
      },
      {
        name: "onboarding",
        tooltip: "Onboarding: markeer deze alinea('s) als uitleg voor nieuwe collega's",
        text: "Onboarding",
        exec: onboardingToggle
      }
    ],
    cleanHTML: {
      removeEmptyElements: true,
      fillEmptyParagraph: false,
      allowTags: {
        p: { class: true }, br: true, strong: true, b: true, em: true, i: true, u: true, s: true, strike: true, sub: true, sup: true,
        ul: true, ol: { start: true }, li: true, a: { href: true, title: true }, code: true, pre: true, blockquote: true,
        h1: true, h2: { class: true }, h3: true, section: { class: true }, h4: true, h5: true, h6: true,
        table: true, thead: true, tbody: true, tr: true, th: { colspan: true, rowspan: true, scope: true }, td: { colspan: true, rowspan: true },
        hr: true, div: { class: true }, span: true
      }
    }
  };

  // Voor andere teksten dan de artikelinhoud (bijv. een nieuwsbericht): alleen de opmaakknoppen,
  // zonder volledig scherm, secties en onboarding.
  var configEenvoudig = Object.assign({}, config, {
    buttons: config.buttons.slice(0, config.buttons.indexOf("redo") + 1)
  });

  function init(textarea) {
    if (textarea.dataset.kbEditor) return;
    textarea.dataset.kbEditor = "1";
    var editor = Jodit.make(textarea, textarea.name === "inhoud" ? config : configEenvoudig);
    ruimteRondSecties(editor);
    editor.events.on("change", function () { if (ruimteRondSecties(editor)) editor.synchronizeValues(); });
    // Na "Opslaan en doorgaan" vanuit het volledige scherm: dat scherm weer openen.
    var heropen = false;
    try { heropen = sessionStorage.getItem("kb.split.heropen") === "1"; sessionStorage.removeItem("kb.split.heropen"); } catch (e) {}
    if (heropen && textarea.name === "inhoud") setTimeout(function () { volledigScherm(editor); }, 50);
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
      balkTonen(
        "kb-melding-fout",
        "Let op: dit scherm is verlopen, waarschijnlijk doordat je in een ander tabblad opnieuw bent " +
          "ingelogd. Opslaan lukt nu niet. Kopieer je tekst, ververs deze pagina met Ctrl+F5 en plak hem terug."
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

  /* De toelichting bij publiceren staat buiten het volledige scherm. Zonder deze controle zou
   * opslaan vanuit het volledige scherm stilletjes mislukken op een foutmelding die je niet ziet. */
  function toelichtingNodig(beginwaarden) {
    var status = veld("status");
    if (!status || status.value !== "gepubliceerd") return false;
    var hint = veld("al_gepubliceerd");
    if (!hint || !hint.value) return false;
    var toel = veld("wijzigingstoelichting");
    var klein = veld("kleine_correctie");
    if (toel && toel.value.trim()) return false;
    if (klein && klein.checked) return false;
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
      knoppen: [{ tekst: "Annuleren" }, { tekst: "Opslaan", primair: true, doen: opslaan }],
    });
    return true;
  }

  window.kbMelding = function (opties) {
    vensterTonen({ titel: opties.titel, alineas: opties.alineas, knoppen: [{ tekst: "Sluiten", primair: true }] });
  };
  window.kbToelichtingNodig = toelichtingNodig;
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

  document.addEventListener("DOMContentLoaded", function () {
    initAll();
    zachtSlot();
    tagSuggesties();
    // Beginwaarden onthouden, zodat we weten of er iets inhoudelijks is veranderd.
    window.kbBeginwaarden = {};
    ["titel", "samenvatting", "inhoud", "soort", "eigenaar", "omgeving", "tags_tekst"].forEach(function (naam) {
      var el = veld(naam);
      if (el) window.kbBeginwaarden[naam] = el.value;
    });
    // Mislukte opslag door de ontbrekende toelichting: toon hem alsnog in beeld.
    var foutje = document.querySelector(".field-wijzigingstoelichting .errorlist li");
    if (foutje) setTimeout(function () { vraagToelichting(foutje.textContent); }, 60);
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
