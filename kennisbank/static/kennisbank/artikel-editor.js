/* Editor voor de tekst van een artikel (1.22.0, bouwlijst `bouwlijst-1.22.0-nieuw-bewerkscherm.md`).
 *
 * Gebouwd op Tiptap/ProseMirror (vendor/tiptap/tiptap.min.js, window.KBTiptap). Je bewerkt het artikel
 * zoals medewerkers het zien: een sectie is een kaart met een kop en tekst, onboarding een geel kader.
 * Het opgeslagen formaat is hetzelfde als met de vorige editor (zie kennisbank/inhoud.py):
 *   <section class="sectie"><h2 class="sectie-kop">Kop</h2>…</section>
 *   <div class="onboarding">…</div>
 * De server schoont alles daarna nog op (inhoud.schoon); deze editor hoeft niets te beveiligen.
 *
 * Wat de editor erbij geeft:
 * - Een sectie kan niet in een sectie (het schema staat het niet toe) en kan niet "half kapot".
 * - Tussen twee blokken verschijnt bij de muis een + om tekst of een sectie in te voegen.
 * - Elke sectie heeft een ⋯-menu: omhoog, omlaag, opheffen, verwijderen.
 * - Ongedaan maken en opnieuw over het hele artikel (Ctrl+Z, Ctrl+Y, Ctrl+Shift+Z en de knoppen).
 * - Opmerkingen van het reviewteam: markeringen als decoratie, dus nooit in de opgeslagen tekst.
 *
 * Gebruik: KBArtikelEditor.maak(textarea, {werkbalk: element}) geeft een object terug met dezelfde
 * vorm als de vorige editor had voor de kladversie en het slot: value, synchronizeValues(),
 * setReadOnly(), plus editor (de Tiptap-editor) en opmerkingen(lijst).
 */
(function () {
  "use strict";
  var T = window.KBTiptap;
  if (!T) return;

  /* --- Het schema ------------------------------------------------------------------------- */

  var Document = T.Node.create({ name: "doc", topNode: true, content: "(block | sectieblok)+" });

  var SectieKop = T.Node.create({
    name: "sectieKop",
    content: "text*",
    marks: "",
    defining: true,
    parseHTML: function () { return [{ tag: "h2.sectie-kop" }]; },
    renderHTML: function () { return ["h2", { class: "sectie-kop" }, 0]; },
    addKeyboardShortcuts: function () {
      var ed = this.editor;
      return {
        // Enter in de kop: naar het begin van de tekst eronder, niet een tweede kop.
        Enter: function () {
          var $f = ed.state.selection.$from;
          if ($f.parent.type.name !== "sectieKop") return false;
          var naKop = $f.after();
          ed.chain().setTextSelection(naKop + 1).run();
          return true;
        },
      };
    },
  });

  var Sectie = T.Node.create({
    name: "sectie",
    group: "sectieblok",
    content: "sectieKop block+",
    defining: true,
    isolating: true,
    parseHTML: function () { return [{ tag: "section.sectie" }]; },
    renderHTML: function () { return ["section", { class: "sectie" }, 0]; },
    addNodeView: function () {
      return function (p) {
        var dom = document.createElement("section");
        dom.className = "sectie kb-ae-sectie";
        var pijl = document.createElement("span");
        pijl.className = "kb-ae-pijl";
        pijl.contentEditable = "false";
        pijl.setAttribute("aria-hidden", "true");
        pijl.textContent = "▾";
        var knop = document.createElement("button");
        knop.type = "button";
        knop.className = "kb-ae-smenu";
        knop.contentEditable = "false";
        knop.setAttribute("aria-label", "Sectiemenu: omhoog, omlaag, opheffen, verwijderen");
        knop.title = "Omhoog, omlaag, opheffen, verwijderen";
        knop.textContent = "⋯";
        knop.addEventListener("mousedown", function (e) { e.preventDefault(); });
        knop.addEventListener("click", function (e) {
          e.preventDefault();
          e.stopPropagation();
          if (!p.editor.isEditable) return;
          sectieMenu(p.editor, p.getPos(), knop);
        });
        var inhoud = document.createElement("div");
        inhoud.className = "kb-ae-sectie-inhoud";
        dom.appendChild(pijl);
        dom.appendChild(knop);
        dom.appendChild(inhoud);
        return {
          dom: dom,
          contentDOM: inhoud,
          stopEvent: function (e) { return knop.contains(e.target); },
          ignoreMutation: function (m) { return !inhoud.contains(m.target); },
        };
      };
    },
  });

  var Onboarding = T.Node.create({
    name: "onboarding",
    group: "block",
    content: "block+",
    defining: true,
    parseHTML: function () { return [{ tag: "div.onboarding" }]; },
    renderHTML: function () { return ["div", { class: "onboarding" }, 0]; },
  });

  /* Opmerkingen van het reviewteam als decoratie: ze kleuren de tekst, maar zitten er niet in. */
  var opmSleutel = new T.PluginKey("kbOpmerkingen");

  function normaal(s) { return (s || "").replace(/\s+/g, " ").trim(); }

  function vind(doc, citaat) {
    var zoek = normaal(citaat);
    if (!zoek) return null;
    var gevonden = null;
    doc.descendants(function (node, pos) {
      if (gevonden) return false;
      if (!node.isTextblock) return true;
      // Tekst van dit blok met per teken de plek in het document; witruimte telt als één spatie.
      var tekst = "", plek = [], vorigeSpatie = false;
      node.forEach(function (kind, offset) {
        if (kind.isText) {
          for (var i = 0; i < kind.text.length; i++) {
            var c = kind.text[i];
            if (/\s/.test(c)) { if (vorigeSpatie) continue; c = " "; vorigeSpatie = true; } else vorigeSpatie = false;
            tekst += c;
            plek.push(pos + 1 + offset + i);
          }
        } else if (!vorigeSpatie) { tekst += " "; plek.push(pos + 1 + offset); vorigeSpatie = true; }
      });
      var i = tekst.indexOf(zoek);
      if (i >= 0) gevonden = { from: plek[i], to: plek[i + zoek.length - 1] + 1 };
      return false;
    });
    return gevonden;
  }

  function srWidget(tekst) {
    return function () {
      var s = document.createElement("span");
      s.className = "kb-sr";
      s.setAttribute("contenteditable", "false");
      s.textContent = " " + tekst + " ";
      return s;
    };
  }

  function opmDecoraties(doc, lijst) {
    var deco = [];
    (lijst || []).forEach(function (o) {
      if (!o.citaat) return;
      var r = vind(doc, o.citaat);
      o._plek = r;
      if (!r) return;
      deco.push(T.Decoration.inline(r.from, r.to, { class: "kb-ae-opm", "data-nr": String(o.nr) }));
      // Ronde B (M19): de schermlezer hoort waar de opmerking begint en eindigt; het oog ziet paars met een lijn.
      deco.push(T.Decoration.widget(r.from, srWidget("begin opmerking " + o.nr + " van de review"), { side: -1, key: "opmb" + o.nr, ignoreSelection: true }));
      deco.push(T.Decoration.widget(r.to, srWidget("einde opmerking " + o.nr), { side: 1, key: "opme" + o.nr, ignoreSelection: true }));
    });
    return T.DecorationSet.create(doc, deco);
  }

  var Opmerkingen = T.Extension.create({
    name: "kbOpmerkingen",
    addProseMirrorPlugins: function () {
      return [
        new T.Plugin({
          key: opmSleutel,
          state: {
            init: function () { return { lijst: [], deco: T.DecorationSet.empty }; },
            apply: function (tr, oud, _o, nieuw) {
              var lijst = tr.getMeta(opmSleutel);
              if (lijst !== undefined) return { lijst: lijst, deco: opmDecoraties(nieuw.doc, lijst) };
              if (tr.docChanged) return { lijst: oud.lijst, deco: opmDecoraties(nieuw.doc, oud.lijst) };
              return oud;
            },
          },
          props: { decorations: function (state) { return opmSleutel.getState(state).deco; } },
        }),
      ];
    },
  });

  /* Verbetervoorstellen (1.26.0): het citaat blauw met een stippellijn en een rond nummer erachter. Net als
   * de opmerkingen een decoratie: het hoort niet bij de tekst en gaat niet mee bij opslaan. */
  var vsSleutel = new T.PluginKey("kbVoorstellen");

  function vsDecoraties(doc, lijst) {
    var deco = [];
    (lijst || []).forEach(function (v) {
      v._plek = null;
      if (!v.citaat) return;
      var r = vind(doc, v.citaat);
      v._plek = r;
      if (!r) return;
      deco.push(T.Decoration.inline(r.from, r.to, { class: "kb-ae-vs" + (v.actief ? " kb-ae-vs-actief" : ""), "data-vs": String(v.id) }));
      // Ronde B (M19): het nummer is voor het oog (aria-hidden); de schermlezer hoort "begin/einde verbetervoorstel n"
      // in plaats van een los getal midden in de zin.
      deco.push(T.Decoration.widget(r.from, srWidget("begin verbetervoorstel " + v.nr), { side: -1, key: "vsb" + v.id + "-" + v.nr, ignoreSelection: true }));
      deco.push(T.Decoration.widget(r.to, function () {
        var w = document.createElement("span");
        w.setAttribute("contenteditable", "false");
        var s = document.createElement("sup");
        s.className = "kb-ae-vsnr" + (v.actief ? " kb-ae-vsnr-actief" : "");
        s.textContent = String(v.nr);
        s.setAttribute("data-vs", String(v.id));
        s.setAttribute("aria-hidden", "true");
        s.title = "Verbetervoorstel " + v.nr;
        w.appendChild(s);
        var e = document.createElement("span");
        e.className = "kb-sr";
        e.textContent = " einde verbetervoorstel " + v.nr + " ";
        w.appendChild(e);
        return w;
      }, { side: 1, key: "vs" + v.id + "-" + v.nr + (v.actief ? "a" : ""), ignoreSelection: true }));
    });
    return T.DecorationSet.create(doc, deco);
  }

  /* Wijzigingen in de live versie (1.33.0): één alinea aanwijzen, als decoratie. `m` is {sleutel, nr} zoals
   * de server hem geeft: de tekst van de alinea zonder witruimte, en de hoeveelste alinea met die tekst het is.
   * Met `na`/`voor` een streep eronder of erboven (daar komt nieuwe tekst), met `net` groen (zojuist overgenomen). */
  var liveSleutel = new T.PluginKey("kbLive");

  function liveStaat(doc, m) {
    if (!m || !m.sleutel) return { m: null, pos: null, eind: null, deco: T.DecorationSet.empty };
    var nr = 0, pos = null, eind = null;
    doc.descendants(function (node, p) {
      if (pos !== null) return false;
      if (!node.isTextblock) return true;
      if (node.textContent.replace(/\s+/g, "") === m.sleutel) {
        if (nr === (m.nr || 0)) { pos = p; eind = p + node.nodeSize; }
        nr++;
      }
      return false;
    });
    if (pos === null) return { m: m, pos: null, eind: null, deco: T.DecorationSet.empty };
    var klasse = "kb-ae-live" + (m.net ? " kb-ae-live-net" : m.na ? " kb-ae-live-na" : m.voor ? " kb-ae-live-voor" : "");
    return { m: m, pos: pos, eind: eind, deco: T.DecorationSet.create(doc, [T.Decoration.node(pos, eind, { class: klasse })]) };
  }

  var Live = T.Extension.create({
    name: "kbLive",
    addProseMirrorPlugins: function () {
      return [
        new T.Plugin({
          key: liveSleutel,
          state: {
            init: function () { return liveStaat(null, null); },
            apply: function (tr, oud, _o, nieuw) {
              var m = tr.getMeta(liveSleutel);
              if (m !== undefined) return liveStaat(nieuw.doc, m);
              if (tr.docChanged && oud.m) return liveStaat(nieuw.doc, oud.m);
              return oud;
            },
          },
          props: { decorations: function (state) { return liveSleutel.getState(state).deco; } },
        }),
      ];
    },
  });

  function sectieVoor(doc, pos) {
    var kop = "";
    doc.nodesBetween(0, pos, function (node, p) {
      if (p >= pos) return false;
      if (node.type.name === "sectieKop" || node.type.name === "heading") kop = node.textContent;
      return true;
    });
    return kop;
  }

  var Voorstellen = T.Extension.create({
    name: "kbVoorstellen",
    addOptions: function () { return { opKlik: null }; },
    addProseMirrorPlugins: function () {
      var ext = this;
      return [
        new T.Plugin({
          key: vsSleutel,
          state: {
            init: function () { return { lijst: [], deco: T.DecorationSet.empty }; },
            apply: function (tr, oud, _o, nieuw) {
              var lijst = tr.getMeta(vsSleutel);
              if (lijst !== undefined) return { lijst: lijst, deco: vsDecoraties(nieuw.doc, lijst) };
              if (tr.docChanged) return { lijst: oud.lijst, deco: vsDecoraties(nieuw.doc, oud.lijst) };
              return oud;
            },
          },
          props: {
            decorations: function (state) { return vsSleutel.getState(state).deco; },
            handleDOMEvents: {
              mousedown: function (view, e) {
                var t = e.target.closest && e.target.closest("sup.kb-ae-vsnr");
                if (!t || !ext.options.opKlik) return false;
                e.preventDefault();
                ext.options.opKlik(Number(t.getAttribute("data-vs")));
                return true;
              },
            },
          },
        }),
      ];
    },
  });

  /* --- Hulpjes ---------------------------------------------------------------------------- */

  function el(tag, cls, tekst) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (tekst != null) e.textContent = tekst;
    return e;
  }

  function venster(opties) {
    if (window.kbVenster) return window.kbVenster(opties);
    // Zonder het beheerscript: een eenvoudige vraag van de browser.
    var ja = opties.knoppen && opties.knoppen[opties.knoppen.length - 1];
    if (ja && ja.doen && window.confirm(opties.titel + "\n\n" + (opties.alineas || []).join("\n"))) ja.doen();
    return null;
  }

  var openMenu = null, menuAnker = null;
  function sluitMenu(terug) {
    if (!openMenu) return;
    openMenu.remove();
    openMenu = null;
    if (terug && menuAnker && document.contains(menuAnker)) menuAnker.focus();
  }
  document.addEventListener("mousedown", function (e) { if (openMenu && !openMenu.contains(e.target)) sluitMenu(); });
  // Ronde B (L3): Escape en Tab sluiten het menu en zetten de focus terug op de knop ⋯ of +.
  document.addEventListener("keydown", function (e) {
    if (!openMenu) return;
    if (e.key === "Escape" || (e.key === "Tab" && openMenu.contains(document.activeElement))) {
      e.preventDefault();
      sluitMenu(true);
    }
  });

  function toonMenu(anker, items) {
    sluitMenu();
    var m = el("div", "kb-ae-menu");
    m.setAttribute("role", "menu");
    items.forEach(function (it) {
      if (!it) return;
      var b = el("button", "kb-ae-menuknop" + (it.gevaar ? " kb-ae-gevaar" : ""));
      b.type = "button";
      b.setAttribute("role", "menuitem");
      b.appendChild(el("span", "", it.tekst));
      if (it.uitleg) b.appendChild(el("small", "", it.uitleg));
      b.disabled = !!it.uit;
      b.addEventListener("mousedown", function (e) { e.preventDefault(); });
      b.addEventListener("click", function () { sluitMenu(); it.doe(); });
      m.appendChild(b);
    });
    // Pijltjes (en Home/End) door de menuknoppen.
    m.addEventListener("keydown", function (e) {
      var lijst = Array.prototype.slice.call(m.querySelectorAll("button:not([disabled])"));
      var i = lijst.indexOf(document.activeElement);
      var naar = { ArrowDown: i + 1, ArrowUp: i - 1, Home: 0, End: lijst.length - 1 }[e.key];
      if (naar === undefined || !lijst.length) return;
      e.preventDefault();
      lijst[(naar + lijst.length) % lijst.length].focus();
    });
    menuAnker = anker;
    document.body.appendChild(m);
    var r = anker.getBoundingClientRect();
    var links = Math.max(8, Math.min(window.innerWidth - m.offsetWidth - 8, r.left + window.scrollX - m.offsetWidth / 2 + r.width / 2));
    m.style.left = links + "px";
    m.style.top = r.bottom + window.scrollY + 4 + "px";
    openMenu = m;
    var eerste = m.querySelector("button:not([disabled])");
    if (eerste) eerste.focus();
  }

  // Plekken (begin) van de blokken op het hoogste niveau.
  function bovenblokken(doc) {
    var uit = [];
    doc.forEach(function (node, offset, i) { uit.push({ node: node, pos: offset, index: i }); });
    return uit;
  }

  function nieuweSectie(schema, kopTekst, kinderen) {
    var kop = schema.nodes.sectieKop.create(null, kopTekst ? schema.text(kopTekst) : null);
    var inhoud = kinderen && kinderen.length ? kinderen : [schema.nodes.paragraph.create()];
    return schema.nodes.sectie.create(null, [kop].concat(inhoud));
  }

  // Meteen (niet pas bij het volgende beeldje) de cursor zetten en focus geven: anders gaan de eerste
  // letters die je typt verloren.
  function zetCursorIn(ed, pos) {
    var doc = ed.state.doc;
    pos = Math.max(0, Math.min(pos, doc.content.size));
    ed.view.dispatch(ed.state.tr.setSelection(T.TextSelection.near(doc.resolve(pos))).scrollIntoView());
    ed.view.focus();
  }

  /* --- Sectiemenu ------------------------------------------------------------------------- */

  function sectieMenu(ed, pos, anker) {
    var blokken = bovenblokken(ed.state.doc);
    var i = blokken.findIndex(function (b) { return b.pos === pos; });
    if (i < 0) return;
    var b = blokken[i];
    toonMenu(anker, [
      {
        tekst: "Omhoog", uit: i === 0, doe: function () {
          var vorige = blokken[i - 1];
          var tr = ed.state.tr.delete(b.pos, b.pos + b.node.nodeSize).insert(vorige.pos, b.node);
          ed.view.dispatch(tr.scrollIntoView());
          zetCursorIn(ed, vorige.pos + 2);
        },
      },
      {
        tekst: "Omlaag", uit: i === blokken.length - 1, doe: function () {
          var volgende = blokken[i + 1];
          var na = volgende.pos + volgende.node.nodeSize;
          var tr = ed.state.tr.insert(na, b.node).delete(b.pos, b.pos + b.node.nodeSize);
          ed.view.dispatch(tr.scrollIntoView());
          zetCursorIn(ed, na - b.node.nodeSize + 2);
        },
      },
      {
        tekst: "Opheffen", uitleg: "De tekst blijft staan, het uitklapblok verdwijnt", doe: function () {
          var schema = ed.schema, delen = [];
          var kop = b.node.firstChild.textContent.trim();
          if (kop) delen.push(schema.nodes.heading.create({ level: 3 }, schema.text(kop)));
          b.node.forEach(function (kind, _o, j) { if (j > 0) delen.push(kind); });
          ed.view.dispatch(ed.state.tr.replaceWith(b.pos, b.pos + b.node.nodeSize, delen));
          zetCursorIn(ed, b.pos + 1);
        },
      },
      {
        tekst: "Verwijderen", uitleg: "Kop én tekst weg (Ctrl+Z zet hem terug)", gevaar: true, doe: function () {
          ed.view.dispatch(ed.state.tr.delete(b.pos, b.pos + b.node.nodeSize));
          ed.commands.focus();
        },
      },
    ]);
  }

  /* --- Sectie maken: om de selectie heen, of een nieuwe lege ----------------------------- */

  function sectieMaken(ed) {
    var state = ed.state, schema = ed.schema, sel = state.selection;
    var $f = sel.$from, $t = sel.$to;
    // Bovenste blokken die de selectie raakt.
    var van = $f.depth ? $f.before(1) : 0, tot = $t.depth ? $t.after(1) : state.doc.content.size;
    var inSectie = $f.depth && $f.node(1).type.name === "sectie";
    if (sel.empty || inSectie) {
      // Een nieuwe, lege sectie na het blok waar de cursor staat.
      var na = $f.depth ? $f.after(1) : state.doc.content.size;
      ed.view.dispatch(state.tr.insert(na, nieuweSectie(schema)).scrollIntoView());
      zetCursorIn(ed, na + 2);
      return;
    }
    // Selectie over gewone blokken: zet er een sectie omheen. Begint hij met een kop, dan wordt dat de
    // kop van de sectie (zoals na een Word-import). Een sectie in de selectie gaat op in de nieuwe.
    var kinderen = [];
    state.doc.nodesBetween(van, tot, function (node, pos, ouder) {
      if (ouder !== state.doc) return false;
      if (node.type.name === "sectie") {
        var k = node.firstChild.textContent.trim();
        if (k) kinderen.push(schema.nodes.heading.create({ level: 3 }, schema.text(k)));
        node.forEach(function (kind, _o, j) { if (j > 0) kinderen.push(kind); });
      } else kinderen.push(node);
      return false;
    });
    var kopTekst = "";
    if (kinderen.length && kinderen[0].type.name === "heading" && kinderen[0].textContent.trim()) {
      kopTekst = kinderen.shift().textContent.trim();
    }
    ed.view.dispatch(state.tr.replaceWith(van, tot, nieuweSectie(schema, kopTekst, kinderen)).scrollIntoView());
    zetCursorIn(ed, van + 2 + kopTekst.length);
  }

  function onboardingWissel(ed) {
    if (ed.isActive("onboarding")) { ed.chain().focus().lift("onboarding").run(); return; }
    if (!ed.chain().focus().wrapIn("onboarding").run()) {
      venster({ titel: "Onboarding", alineas: ["Zet de cursor in een alinea (niet in de kop van een sectie) en probeer het opnieuw."], knoppen: [{ tekst: "Sluiten", primair: true }] });
    }
  }

  function linkVragen(ed) {
    var huidig = ed.getAttributes("link").href || "";
    var vak = el("div", "kb-venster-veld");
    var label = el("label", "", "Adres (begint met https:// of mailto:)");
    label.setAttribute("for", "kb-ae-link");
    var invoer = el("input");
    invoer.id = "kb-ae-link";
    invoer.type = "url";
    invoer.value = huidig || "https://";
    var fout = el("p", "kb-venster-fout");
    fout.hidden = true;
    vak.appendChild(label);
    vak.appendChild(invoer);
    vak.appendChild(fout);
    var knoppen = [{ tekst: "Annuleren" }];
    if (huidig) knoppen.push({ tekst: "Link weghalen", doen: function () { ed.chain().focus().extendMarkRange("link").unsetLink().run(); } });
    knoppen.push({
      tekst: "Opslaan", primair: true, doen: function () {
        var url = invoer.value.trim();
        if (!/^(https?:\/\/[^\s]+|mailto:[^\s]+)$/i.test(url)) {
          fout.textContent = "Dat is geen geldig adres. Het moet beginnen met https:// (of mailto:).";
          fout.hidden = false;
          return false;
        }
        ed.chain().focus().extendMarkRange("link").setLink({ href: url }).run();
      },
    });
    venster({ titel: huidig ? "Link aanpassen" : "Link toevoegen", inhoud: vak, knoppen: knoppen });
    setTimeout(function () { invoer.focus(); invoer.select(); }, 0);
  }

  /* --- In en uit: dezelfde HTML als met de vorige editor ------------------------------- */

  // Wat er binnenkomt (opgeslagen tekst, kladversie, plakken) eerst in de vorm die het schema verwacht:
  // elke sectie begint met een kop, en een sectie in een sectie wordt gewone tekst (zoals de server
  // ook doet, inhoud._ontnest_secties).
  function voorbewerk(html) {
    var d = new DOMParser().parseFromString("<body>" + (html || "") + "</body>", "text/html").body;
    Array.prototype.slice.call(d.querySelectorAll("section.sectie section.sectie")).reverse().forEach(function (binnen) {
      var kop = binnen.querySelector(":scope > h2.sectie-kop");
      if (kop) {
        if (kop.textContent.trim()) { var h3 = d.ownerDocument.createElement("h3"); h3.textContent = kop.textContent.trim(); binnen.replaceChild(h3, kop); }
        else binnen.removeChild(kop);
      }
      while (binnen.firstChild) binnen.parentNode.insertBefore(binnen.firstChild, binnen);
      binnen.remove();
    });
    d.querySelectorAll("section.sectie").forEach(function (sec) {
      var eerste = sec.firstElementChild;
      if (!eerste || !(eerste.tagName === "H2" && eerste.classList.contains("sectie-kop"))) {
        var kop = d.ownerDocument.createElement("h2");
        kop.className = "sectie-kop";
        sec.insertBefore(kop, sec.firstChild);
      }
    });
    d.querySelectorAll("p.tussenruimte").forEach(function (p) { if (!p.textContent.trim()) p.remove(); });
    return d.innerHTML;
  }

  // Wat er uitgaat: geen extra <p> in elk lijstpunt en elke tabelcel, geen breedtes, geen lege regel
  // die de editor zelf onderaan zet.
  function naarOpslag(html) {
    var d = new DOMParser().parseFromString("<body>" + html + "</body>", "text/html").body;
    d.querySelectorAll("li, td, th").forEach(function (c) {
      if (c.children.length === 1 && c.firstElementChild.tagName === "P" && c.childNodes.length === 1) {
        var p = c.firstElementChild;
        while (p.firstChild) c.insertBefore(p.firstChild, p);
        p.remove();
      }
    });
    d.querySelectorAll("colgroup").forEach(function (g) { g.remove(); });
    d.querySelectorAll("[style]").forEach(function (e) { e.removeAttribute("style"); });
    while (d.lastElementChild && d.lastElementChild.tagName === "P" && !d.lastElementChild.textContent.trim() && !d.lastElementChild.querySelector("br,img") && d.lastElementChild === d.lastChild) d.lastElementChild.remove();
    return d.innerHTML;
  }

  /* --- Plakken uit Word ------------------------------------------------------------------ */

  function wordOpschonen(html) {
    return voorbewerk(html)
      .replace(/<!--[\s\S]*?-->/g, "")
      .replace(/<\/?o:p[^>]*>/gi, "")
      .replace(/<style[\s\S]*?<\/style>/gi, "")
      .replace(/\sclass="?Mso[^"\s>]*"?/gi, "")
      .replace(/\sstyle="[^"]*"/gi, "");
  }

  /* --- De werkbalk ----------------------------------------------------------------------- */

  function werkbalk(ed, plek, eenvoudig) {
    var knoppen = [];
    function knop(tekst, label, doe, actief, extra) {
      var b = el("button", "kb-ae-knop" + (extra ? " " + extra : ""));
      b.type = "button";
      b.innerHTML = tekst;
      b.setAttribute("aria-label", label);
      b.title = label;
      b.addEventListener("mousedown", function (e) { e.preventDefault(); });
      b.addEventListener("click", function () { if (ed.isEditable) doe(); });
      plek.appendChild(b);
      knoppen.push({ b: b, actief: actief });
      return b;
    }
    function scheid() { plek.appendChild(el("span", "kb-ae-scheid")); }
    var c = function () { return ed.chain().focus(); };

    knop("↶", "Ongedaan maken (Ctrl+Z)", function () { c().undo().run(); }, null, "kb-ae-undo");
    knop("↷", "Opnieuw (Ctrl+Y)", function () { c().redo().run(); }, null, "kb-ae-redo");
    scheid();
    var soort = el("select", "kb-ae-soort");
    soort.setAttribute("aria-label", "Soort alinea");
    [["p", "Alinea"], ["h3", "Kop"], ["h4", "Subkop"], ["q", "Citaat"]].forEach(function (o) {
      var opt = el("option", "", o[1]);
      opt.value = o[0];
      soort.appendChild(opt);
    });
    soort.addEventListener("change", function () {
      var v = soort.value;
      if (v === "p") c().setParagraph().run();
      else if (v === "h3") c().setHeading({ level: 3 }).run();
      else if (v === "h4") c().setHeading({ level: 4 }).run();
      else if (v === "q") { if (!ed.isActive("blockquote")) c().setParagraph().toggleBlockquote().run(); }
    });
    plek.appendChild(soort);
    scheid();
    knop("<b>B</b>", "Vet (Ctrl+B)", function () { c().toggleBold().run(); }, "bold");
    knop("<i>I</i>", "Cursief (Ctrl+I)", function () { c().toggleItalic().run(); }, "italic");
    knop("<u>U</u>", "Onderstrepen (Ctrl+U)", function () { c().toggleUnderline().run(); }, "underline");
    knop("<s>S</s>", "Doorhalen", function () { c().toggleStrike().run(); }, "strike");
    knop("x<sup>2</sup>", "x2 superscript", function () { c().toggleSuperscript().run(); }, "superscript");
    scheid();
    knop("•≡", "Opsomming", function () { c().toggleBulletList().run(); }, "bulletList");
    knop("1.≡", "1. Genummerde lijst", function () { c().toggleOrderedList().run(); }, "orderedList");
    scheid();
    knop("Link", "Link", function () { linkVragen(ed); }, "link", "kb-ae-tekst");
    knop("Tabel", "Tabel invoegen", function () { c().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(); }, null, "kb-ae-tekst");
    knop("—", "Lijn", function () { c().setHorizontalRule().run(); });
    knop("⌫<small>opmaak</small>", "Opmaak wissen", function () { c().unsetAllMarks().clearNodes().run(); });
    if (!eenvoudig) {
    scheid();
    knop("+ Sectie", "Sectie: om de geselecteerde tekst, of een nieuwe na de cursor", function () { sectieMaken(ed); }, null, "kb-ae-tekst kb-ae-sterk");
    knop("Onboarding", "Onboarding: alinea's alleen voor nieuwe collega's (nogmaals klikken haalt het weg)", function () { onboardingWissel(ed); }, "onboarding", "kb-ae-tekst kb-ae-sterk");
    }

    // Alleen in een tabel: rijen en kolommen.
    var tabel = el("span", "kb-ae-tabelknoppen");
    tabel.hidden = true;
    plek.appendChild(tabel);
    var tk = function (tekst, label, doe) {
      var b = el("button", "kb-ae-knop kb-ae-tekst", tekst);
      b.type = "button";
      b.title = label;
      b.setAttribute("aria-label", label);
      b.addEventListener("mousedown", function (e) { e.preventDefault(); });
      b.addEventListener("click", doe);
      tabel.appendChild(b);
    };
    tk("+ rij", "Rij eronder", function () { c().addRowAfter().run(); });
    tk("+ kolom", "Kolom rechts", function () { c().addColumnAfter().run(); });
    tk("− rij", "Rij weg", function () { c().deleteRow().run(); });
    tk("− kolom", "Kolom weg", function () { c().deleteColumn().run(); });
    tk("Tabel weg", "Hele tabel weg", function () { c().deleteTable().run(); });

    // Ronde B (L2): de werkbalk is één Tab-stop; met de pijltjes (en Home/End) ga je van knop naar knop.
    function bedienbaar() {
      return Array.prototype.filter.call(plek.querySelectorAll("button, select"), function (x) {
        return !x.disabled && !x.closest("[hidden]");
      });
    }
    function rover() {
      var lijst = bedienbaar();
      var huidig = lijst.filter(function (x) { return x.tabIndex === 0; })[0] || lijst[0];
      Array.prototype.forEach.call(plek.querySelectorAll("button, select"), function (x) { x.tabIndex = -1; });
      if (huidig) huidig.tabIndex = 0;
    }
    plek.addEventListener("keydown", function (e) {
      var lijst = bedienbaar(), i = lijst.indexOf(document.activeElement);
      if (i < 0) return;
      var naar = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: lijst.length - 1 }[e.key];
      if (naar === undefined) return;
      e.preventDefault();
      naar = (naar + lijst.length) % lijst.length;
      lijst.forEach(function (x) { x.tabIndex = -1; });
      lijst[naar].tabIndex = 0;
      lijst[naar].focus();
    });
    plek.addEventListener("focusin", function (e) {
      if (!plek.contains(e.target) || e.target.tabIndex === 0) return;
      Array.prototype.forEach.call(plek.querySelectorAll("button, select"), function (x) { x.tabIndex = -1; });
      e.target.tabIndex = 0;
    });

    function bijwerken() {
      knoppen.forEach(function (k) {
        if (k.actief) {
          var aan = ed.isActive(k.actief);
          k.b.classList.toggle("kb-ae-aan", aan);
          k.b.setAttribute("aria-pressed", aan ? "true" : "false");
        }
        k.b.disabled = !ed.isEditable;
      });
      plek.querySelector(".kb-ae-undo").disabled = !ed.isEditable || !ed.can().undo();
      plek.querySelector(".kb-ae-redo").disabled = !ed.isEditable || !ed.can().redo();
      soort.disabled = !ed.isEditable;
      soort.value = ed.isActive("heading", { level: 3 }) ? "h3" : ed.isActive("heading", { level: 4 }) ? "h4" : ed.isActive("blockquote") ? "q" : "p";
      tabel.hidden = !ed.isActive("table");
      rover();
    }
    ed.on("transaction", bijwerken);
    bijwerken();
  }

  /* --- De + tussen blokken --------------------------------------------------------------- */

  function invoegPlus(ed, wrapper) {
    var plus = el("div", "kb-ae-tussen");
    plus.innerHTML = '<span class="kb-ae-lijntje"></span>';
    var knop = el("button", "kb-ae-plus", "+");
    knop.type = "button";
    knop.setAttribute("aria-label", "Hier tekst of een sectie invoegen");
    knop.title = "Hier tekst of een sectie invoegen";
    plus.appendChild(knop);
    plus.hidden = true;
    wrapper.appendChild(plus);
    var doelPos = null;

    function gaten() {
      // Elk gat tussen twee bovenste blokken (en voor het eerste, na het laatste): hoogte en plek.
      var view = ed.view, blokken = bovenblokken(ed.state.doc), uit = [];
      var w = wrapper.getBoundingClientRect();
      blokken.forEach(function (b, i) {
        var dom = view.nodeDOM(b.pos);
        if (!dom || !dom.getBoundingClientRect) return;
        var r = dom.getBoundingClientRect();
        if (i === 0) uit.push({ y: r.top - w.top - 4, pos: b.pos });
        uit.push({ y: r.bottom - w.top + 4, pos: b.pos + b.node.nodeSize });
      });
      return uit;
    }
    wrapper.addEventListener("mousemove", function (e) {
      if (!ed.isEditable || openMenu) return;
      if (plus.contains(e.target)) return;
      var w = wrapper.getBoundingClientRect(), y = e.clientY - w.top, beste = null;
      gaten().forEach(function (g) { if (Math.abs(g.y - y) < 14 && (!beste || Math.abs(g.y - y) < Math.abs(beste.y - y))) beste = g; });
      if (!beste) { plus.hidden = true; return; }
      doelPos = beste.pos;
      plus.style.top = beste.y - 12 + "px";
      plus.hidden = false;
    });
    wrapper.addEventListener("mouseleave", function () { if (!openMenu) plus.hidden = true; });
    knop.addEventListener("mousedown", function (e) { e.preventDefault(); });
    knop.addEventListener("click", function () {
      var pos = doelPos;
      if (pos == null) return;
      toonMenu(knop, [
        {
          tekst: "Tekst", uitleg: "Een gewone alinea, altijd zichtbaar", doe: function () {
            ed.view.dispatch(ed.state.tr.insert(pos, ed.schema.nodes.paragraph.create()).scrollIntoView());
            zetCursorIn(ed, pos + 1);
            plus.hidden = true;
          },
        },
        {
          tekst: "Sectie", uitleg: "Uitklapbaar blok met een kop", doe: function () {
            ed.view.dispatch(ed.state.tr.insert(pos, nieuweSectie(ed.schema)).scrollIntoView());
            zetCursorIn(ed, pos + 2);
            plus.hidden = true;
          },
        },
      ]);
    });
  }

  /* --- Opmerkingen in de marge ------------------------------------------------------------ */

  function marge(ed, margeEl) {
    var lijst = [], gepland = 0;
    function teken() {
      gepland = 0;
      margeEl.textContent = "";
      if (!lijst.length) return;
      var mtop = margeEl.getBoundingClientRect().top;
      var kaarten = lijst.map(function (o) {
        var k = el("button", "kb-ae-kaart" + (o.citaat ? "" : " kb-ae-alg"));
        k.type = "button";
        var nr = el("span", "kb-ae-nr" + (o.citaat ? "" : " kb-ae-alg"), String(o.nr));
        var tekst = el("span", "kb-ae-kaarttekst");
        tekst.appendChild(el("span", "kb-ae-wie", o.wie + " · " + o.wanneer + (o.citaat ? "" : " · algemeen") + (o.voorlopig ? " · voorlopig" : "")));
        if (o.citaat && !o._plek) tekst.appendChild(el("span", "kb-ae-weg", "Tekst is intussen gewijzigd: “" + o.citaat + "”"));
        tekst.appendChild(el("span", "kb-ae-opmtekst", o.tekst));
        k.appendChild(nr);
        k.appendChild(tekst);
        var markeer = function (aan) {
          ed.view.dom.querySelectorAll('.kb-ae-opm[data-nr="' + o.nr + '"]').forEach(function (m) { m.classList.toggle("kb-ae-opm-actief", aan); });
          k.classList.toggle("kb-ae-actief", aan);
        };
        k.addEventListener("mouseenter", function () { markeer(true); });
        k.addEventListener("mouseleave", function () { markeer(false); });
        k.addEventListener("focus", function () { markeer(true); });
        k.addEventListener("blur", function () { markeer(false); });
        k.addEventListener("click", function () {
          if (!o._plek) return;
          var m = ed.view.dom.querySelector('.kb-ae-opm[data-nr="' + o.nr + '"]');
          if (m) m.scrollIntoView({ behavior: "smooth", block: "center" });
        });
        margeEl.appendChild(k);
        var wens = -1;
        if (o._plek) { try { wens = ed.view.coordsAtPos(o._plek.from).top - mtop - 8; } catch (e) { wens = -1; } }
        return { k: k, wens: wens };
      });
      kaarten.sort(function (a, b) { return a.wens - b.wens; });
      var onder = 0;
      kaarten.forEach(function (x) {
        var top = Math.max(x.wens, onder);
        x.k.style.top = top + "px";
        onder = top + x.k.offsetHeight + 10;
      });
      margeEl.style.minHeight = onder + "px";
    }
    function straks() { if (!gepland) gepland = requestAnimationFrame(teken); }
    ed.on("update", straks);
    window.addEventListener("resize", straks);
    return {
      zet: function (nieuw) {
        lijst = nieuw || [];
        ed.view.dispatch(ed.state.tr.setMeta(opmSleutel, lijst).setMeta("addToHistory", false));
        straks();
      },
      teken: straks,
    };
  }

  /* --- Maken ----------------------------------------------------------------------------- */

  function maak(textarea, opties) {
    opties = opties || {};
    var wrapper = el("div", "kb-ae");
    textarea.parentNode.insertBefore(wrapper, textarea);
    textarea.hidden = true;
    var host = el("div", "kb-ae-host");
    wrapper.appendChild(host);

    var ed = new T.Editor({
      element: host,
      // 1.32.0: geen <style>-element invoegen; de basisstijl staat in vendor/tiptap/tiptap.css (CSP van het beheer).
      injectCSS: false,
      content: voorbewerk(textarea.value || ""),
      extensions: [
        Document,
        T.StarterKit.configure({
          document: false,
          heading: { levels: [3, 4] },
          link: { openOnClick: false, autolink: true, protocols: ["mailto"], HTMLAttributes: { rel: null, target: null } },
          trailingNode: { node: "paragraph" },
        }),
        T.Subscript,
        T.Superscript,
        T.Table.configure({ resizable: false }),
        T.TableRow,
        T.TableHeader,
        T.TableCell,
        SectieKop,
        Sectie,
        Onboarding,
        Opmerkingen,
        Live,
        Voorstellen.configure({ opKlik: function (id) { if (opties.opVoorstel) opties.opVoorstel(id); else if (window.kbOpVoorstel) window.kbOpVoorstel(id); } }),
      ],
      editorProps: {
        attributes: { class: "kb-ae-inhoud art", "aria-label": opties.eenvoudig ? "Tekst" : "Tekst van het artikel", role: "textbox", "aria-multiline": "true" },
        transformPastedHTML: wordOpschonen,
      },
      onUpdate: function (p) { textarea.value = naarOpslag(p.editor.getHTML()); textarea.dispatchEvent(new Event("input", { bubbles: true })); },
    });
    textarea.value = naarOpslag(ed.getHTML());

    if (opties.werkbalk) werkbalk(ed, opties.werkbalk, !!opties.eenvoudig);
    // Nieuwsberichten: geen secties, dus ook geen + tussen blokken.
    if (!opties.eenvoudig) invoegPlus(ed, wrapper);
    else wrapper.classList.add("kb-ae-eenvoudig");
    var opm = opties.marge ? marge(ed, opties.marge) : null;

    return {
      editor: ed,
      element: textarea,
      get value() { return naarOpslag(ed.getHTML()); },
      set value(html) { ed.commands.setContent(voorbewerk(html), { emitUpdate: true }); textarea.value = naarOpslag(ed.getHTML()); },
      synchronizeValues: function () { textarea.value = naarOpslag(ed.getHTML()); },
      setReadOnly: function (aan) { ed.setEditable(!aan); wrapper.classList.toggle("kb-ae-alleen-lezen", !!aan); },
      opmerkingen: function (lijst) { if (opm) opm.zet(lijst); },
      // Verbetervoorstellen markeren: lijst van {id, nr, citaat, actief}. Geeft per id terug of het citaat
      // gevonden is en in welke sectie het staat.
      voorstellen: function (lijst) {
        lijst = (lijst || []).map(function (v) { return { id: v.id, nr: v.nr, citaat: v.citaat, actief: !!v.actief }; });
        ed.view.dispatch(ed.state.tr.setMeta(vsSleutel, lijst).setMeta("addToHistory", false));
        var info = {};
        lijst.forEach(function (v) {
          info[v.id] = { gevonden: !!v._plek, sectie: v._plek ? sectieVoor(ed.state.doc, v._plek.from) : "" };
        });
        return info;
      },
      // Met focus=true (knop "Toon in de tekst", ronde B) komt de cursor op het citaat te staan, geselecteerd.
      naarVoorstel: function (id, focus) {
        var st = vsSleutel.getState(ed.state);
        var v = (st.lijst || []).filter(function (x) { return x.id === id; })[0];
        if (!v || !v._plek) return false;
        if (focus) ed.chain().focus().setTextSelection({ from: v._plek.from, to: v._plek.to }).run();
        var dom = ed.view.domAtPos(v._plek.from);
        var node = dom.node.nodeType === 1 ? dom.node : dom.node.parentElement;
        if (node && node.scrollIntoView) node.scrollIntoView({ block: "center", behavior: "smooth" });
        return true;
      },
      // 1.33.0: de alinea van een wijziging in de live versie aanwijzen (null = niets). Geeft terug of hij is
      // gevonden. Met schuif=true komt hij in beeld, met focus=true staat de cursor erin.
      liveMarkeer: function (m, opties) {
        opties = opties || {};
        ed.view.dispatch(ed.state.tr.setMeta(liveSleutel, m || null).setMeta("addToHistory", false));
        var st = liveSleutel.getState(ed.state);
        if (st.pos === null) return false;
        // De cursor aan het eind van de alinea: daar ga je meestal verder met typen.
        if (opties.focus) ed.chain().focus().setTextSelection(st.eind - 1).run();
        if (opties.schuif) {
          var node = ed.view.nodeDOM(st.pos);
          var rustig = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
          if (node && node.scrollIntoView) node.scrollIntoView({ block: "center", behavior: rustig ? "auto" : "smooth" });
        }
        return true;
      },
      tekenMarge: function () { if (opm) opm.teken(); },
      focus: function () { ed.commands.focus("start"); },
    };
  }

  window.KBArtikelEditor = { maak: maak, vind: vind, voorbewerk: voorbewerk, naarOpslag: naarOpslag };
})();
