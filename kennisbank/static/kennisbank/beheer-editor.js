/* Opmaak-editor voor secties in het beheerscherm (Jodit, lokaal meegeleverd).
 *
 * - Werkbalk met de basisopmaak uit Word: koppen, vet, cursief, onderstreept, doorgehaald,
 *   lijsten, inspringen, link, tabel, citaat, opmaak wissen, ongedaan maken.
 * - Knop "Sectiekop": maakt van de huidige regel een sectiekop (<h2 class="sectie">). Alles tot de
 *   volgende sectiekop wordt in de kennisbank een in- en uitklapbare sectie. Nogmaals klikken maakt
 *   er weer een gewone alinea van.
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

  function sectiekopToggle(editor) {
    var root = editor.editor;
    var blok = blokVan(editor.s.range.startContainer, root);
    if (!blok) {
      // Lege editor of cursor buiten een alinea: nieuwe sectiekop aan het eind.
      var doc0 = root.ownerDocument, h0 = doc0.createElement("h2"); h0.className = SEC; h0.textContent = "Nieuwe sectie";
      root.appendChild(h0); root.appendChild(legeAlinea(doc0));
      editor.s.setCursorIn(h0); editor.synchronizeValues(); return;
    }
    var doc = root.ownerDocument;
    if (blok.tagName === "H2" && blok.classList.contains(SEC)) {
      var p = doc.createElement("p"); p.innerHTML = blok.innerHTML || "<br>"; blok.parentNode.replaceChild(p, blok);
      editor.s.setCursorIn(p, false);
    } else {
      // Een sectiekop staat altijd op het hoogste niveau (niet in een onboarding-blok of lijst).
      var top = blok.parentNode === root ? blok : blok.parentNode;
      var h = doc.createElement("h2"); h.className = SEC;
      h.textContent = (blok.textContent || "").replace(/\s+/g, " ").trim() || "Nieuwe sectie";
      if (top === blok) blok.parentNode.replaceChild(h, blok);
      else { top.parentNode.insertBefore(h, top); blok.parentNode.removeChild(blok); if (!top.textContent.trim()) top.parentNode.removeChild(top); }
      // Altijd een gewone regel na de sectiekop, en daar de cursor neerzetten.
      var volgende = h.nextSibling;
      if (!volgende || volgende.nodeType !== 1 || volgende.tagName !== "P") { volgende = legeAlinea(doc); h.parentNode.insertBefore(volgende, h.nextSibling); }
      editor.s.setCursorIn(volgende, true);
    }
    editor.synchronizeValues();
  }

  function blokVan(node, root) {
    // Dichtstbijzijnde alinea-achtig element binnen de editor.
    var el = node.nodeType === 1 ? node : node.parentNode;
    while (el && el !== root) {
      if (/^(P|H[1-6]|UL|OL|TABLE|BLOCKQUOTE|PRE|DIV)$/.test(el.tagName) && el.parentNode === root) return el;
      if (/^(P|H[1-6]|UL|OL|TABLE|BLOCKQUOTE|PRE)$/.test(el.tagName) && el.parentNode && el.parentNode.classList && el.parentNode.classList.contains(ONB)) return el;
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
      var top = function (b) { return b.parentNode === root ? b : b.parentNode; };
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

  /* Voorbeeld: open het artikel in een nieuw tabblad zoals het gepubliceerd zou zijn, met wat nu in de editor staat. */
  function voorbeeld(editor) {
    editor.synchronizeValues();
    var form = document.getElementById("artikel_form") || editor.element.form;
    var val = function (naam) { var el = form && form.querySelector('[name="' + naam + '"]'); return el ? el.value : ""; };
    var f = document.createElement("form");
    f.method = "post"; f.action = "/beheer/kennisbank/artikel/voorbeeld/"; f.target = "kb-voorbeeld"; f.style.display = "none";
    var velden = { csrfmiddlewaretoken: val("csrfmiddlewaretoken"), titel: val("titel"), samenvatting: val("samenvatting"), inhoud: editor.value, soort: val("soort"), eigenaar: val("eigenaar") };
    Object.keys(velden).forEach(function (k) { var i = document.createElement("input"); i.type = "hidden"; i.name = k; i.value = velden[k]; f.appendChild(i); });
    document.body.appendChild(f); f.submit(); document.body.removeChild(f);
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
        name: "voorbeeld",
        tooltip: "Voorbeeld: bekijk in een nieuw tabblad hoe het artikel er gepubliceerd uitziet (ook zonder op te slaan)",
        text: "Voorbeeld",
        exec: voorbeeld
      },
      "|",
      {
        name: "sectiekop",
        tooltip: "Sectiekop: deze regel begint een in- en uitklapbare sectie",
        text: "Sectiekop",
        exec: sectiekopToggle
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
        p: true, br: true, strong: true, b: true, em: true, i: true, u: true, s: true, strike: true, sub: true, sup: true,
        ul: true, ol: { start: true }, li: true, a: { href: true, title: true }, code: true, pre: true, blockquote: true,
        h1: true, h2: { class: true }, h3: true, h4: true, h5: true, h6: true,
        table: true, thead: true, tbody: true, tr: true, th: { colspan: true, rowspan: true, scope: true }, td: { colspan: true, rowspan: true },
        hr: true, div: { class: true }, span: true
      }
    }
  };

  function init(textarea) {
    if (textarea.dataset.kbEditor) return;
    textarea.dataset.kbEditor = "1";
    Jodit.make(textarea, config);
  }

  function initAll(scope) {
    (scope || document).querySelectorAll("textarea.kb-editor").forEach(function (t) {
      // Het lege sjabloon van Django's inline ('__prefix__') niet initialiseren.
      if (t.name.indexOf("__prefix__") !== -1) return;
      init(t);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initAll();
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
