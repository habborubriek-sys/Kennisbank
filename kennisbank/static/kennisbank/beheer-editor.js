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
      // Stap D: opmerkingen van de review, als markeringen in het voorbeeld.
      var opm = [];
      try { var d = document.getElementById("kb-opmerkingen"); if (d) opm = JSON.parse(d.textContent); } catch (e) {}
      frame.contentWindow.postMessage({ type: "kb-voorbeeld", titel: val("titel"), samenvatting: val("samenvatting"), soort: val("soort"), inhoud: editor.value, opmerkingen: opm }, location.origin);
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
            window.kbKladNu && window.kbKladNu()
              ? "Je werk staat veilig in deze browser: ververs de pagina met Ctrl+F5 en kies daarna 'Verder gaan'."
              : "Je tekst staat er nog: kopieer hem, ververs de pagina met Ctrl+F5 en plak hem terug.",
          ],
        });
        return;
      }
      // Wordt er aan een conceptversie gewerkt, dan bewaart het volledige scherm de conceptversie;
      // publiceren gebeurt bewust onderaan het gewone scherm, waar de toelichting staat.
      var conceptKnop = form.querySelector('input[name="kb_conceptmodus"]') && form.querySelector('button[name="_conceptversie"]');
      function bewaren() {
        try { sessionStorage.setItem("kb.split.heropen", "1"); } catch (e) {}
        var knop = conceptKnop || form.querySelector('input[name="_continue"]');
        if (knop) knop.click(); else form.submit();
      }
      if (conceptKnop) { bewaren(); return; }
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
    if (textarea.name === "inhoud") inhoudEditor = editor;  // voor de kladversie
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
      if (e.target.closest && e.target.closest(".jodit-toolbar__box, .jodit-toolbar, .selector-chooser, .selector-chooseall, .selector-clearall")) heeftGewerkt = true;
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

  // Ligt de conceptversie ter inzage bij een reviewteam, dan staat hij op slot: alleen-lezen, behalve
  // de publicatievelden (publiceren kan altijd). De server publiceert dan sowieso de opgeslagen tekst.
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
