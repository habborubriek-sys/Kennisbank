/* Leesweergave voor reviewers (/review/<id>/), sinds 1.30.0 opgezet zoals het bewerkscherm van de redacteur.
 *
 * - Wijzigingen tonen aan/uit (onthouden in deze browser).
 * - Verbetervoorstellen blauw in de tekst, gekoppeld aan "Waarom deze wijziging".
 * - Opmerkingen groen in de tekst, met hun kaart in de marge op dezelfde hoogte.
 * - Tekst selecteren → Opmerking → een nieuw kaartje in de marge. Ook zonder muis: Shift+pijltjes, of het citaat
 *   typen in het kaartje (ronde B, M20).
 * - Afronden… in een venster; Weghalen vraagt eerst een bevestiging; Bekijk als medewerker in een venster.
 *
 * Zonder JavaScript werkt de pagina ook: dan staat alles als gewone lijst en formulieren in de marge.
 */
(function () {
  "use strict";
  var body = document.body;
  var K = window.KbOpmerkingen;
  var tekst = document.getElementById("rv-verschil");
  if (!tekst || !K) return;
  body.classList.add("rv-js");
  var blad = document.querySelector(".rv-blad");
  var marge = document.getElementById("rv-marge");
  var kaartenLijst = document.getElementById("rv-kaarten");
  var nieuw = document.getElementById("rv-nieuw");
  var magReageren = body.classList.contains("rv-mag-reageren");
  var gepland = 0;
  function straks() { if (!gepland) gepland = requestAnimationFrame(indelen); }

  function lees(sleutel) { try { return localStorage.getItem(sleutel); } catch (e) { return null; } }
  function bewaar(sleutel, w) { try { localStorage.setItem(sleutel, w); } catch (e) { /* privévenster */ } }

  /* --- Wijzigingen tonen aan/uit --------------------------------------------------------------------- */
  var wijzKnop = document.getElementById("rv-wijz-knop");
  function zetWijz(aan) {
    body.classList.toggle("rv-zonder-wijz", !aan);
    if (wijzKnop) wijzKnop.setAttribute("aria-pressed", aan ? "true" : "false");
    straks();
  }
  zetWijz(lees("kb-rv-wijzigingen") !== "uit");
  if (wijzKnop) {
    wijzKnop.hidden = false;
    wijzKnop.addEventListener("click", function () {
      var aan = wijzKnop.getAttribute("aria-pressed") !== "true";
      bewaar("kb-rv-wijzigingen", aan ? "aan" : "uit");
      zetWijz(aan);
    });
  }

  function flits(el) {
    el.classList.add("rv-flits");
    setTimeout(function () { el.classList.remove("rv-flits"); }, 1200);
  }
  function naar(el, focus) {
    for (var p = el.parentNode; p; p = p.parentNode) if (p.nodeName === "DETAILS") p.open = true;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    if (focus) { if (!el.hasAttribute("tabindex")) el.tabIndex = -1; el.focus({ preventScroll: true }); }
    flits(el);
  }

  /* --- Verbetervoorstellen blauw in de tekst ---------------------------------------------------------- */
  Array.prototype.forEach.call(document.querySelectorAll(".rv-vs[data-nr]"), function (li) {
    var nr = li.getAttribute("data-nr"), citaat = li.getAttribute("data-citaat") || "";
    var status = li.querySelector(".rv-vs-status");
    var m = citaat ? K.markeer(tekst, citaat, nr, { klasse: "rv-vs-mark", geenNummer: true, metDel: true, sr: "verbetervoorstel " + nr }) : null;
    if (!m) {
      if (citaat && status) { status.textContent = "De tekst waar dit over ging, staat er niet meer in deze vorm."; status.hidden = false; }
      return;
    }
    var weg = true;
    tekst.querySelectorAll('mark.rv-vs-mark[data-nr="' + nr + '"]').forEach(function (x) { if (!x.closest("del")) weg = false; });
    if (weg && status) { status.textContent = "Deze tekst is weggehaald (doorgestreept in de tekst)."; status.hidden = false; }
    var sup = document.createElement("sup");
    sup.className = "rv-vs-nr"; sup.textContent = nr; sup.setAttribute("aria-hidden", "true"); sup.title = "Verbetervoorstel " + nr;
    var na = m.kbLaatste || m;
    na.parentNode.insertBefore(sup, na.nextSibling);
    sup.addEventListener("click", function () { naar(li, true); });
    var knop = document.createElement("button");
    knop.type = "button"; knop.className = "rv-link"; knop.textContent = "Toon in de tekst";
    knop.addEventListener("click", function () { naar(m, true); });
    li.querySelector(".rv-vs-tekst").appendChild(document.createTextNode(" "));
    li.querySelector(".rv-vs-tekst").appendChild(knop);
  });

  /* --- Opmerkingen: groen in de tekst, kaart in de marge ---------------------------------------------- */
  var kaarten = kaartenLijst ? Array.prototype.slice.call(kaartenLijst.querySelectorAll(".rv-kaart")) : [];
  var plek = {};
  kaarten.forEach(function (k) {
    var nr = k.getAttribute("data-nr"), citaat = k.getAttribute("data-citaat");
    if (!citaat) return;
    var m = K.markeer(tekst, citaat, nr);
    if (!m) {
      var s = document.createElement("span"); s.className = "rv-kaart-wie"; s.textContent = "Tekst niet meer gevonden.";
      k.querySelector(".rv-kaart-inhoud").appendChild(s);
      return;
    }
    plek[nr] = m;
    var marks = tekst.querySelectorAll('mark.kb-opm[data-nr="' + nr + '"]');
    function actief(aan) {
      k.classList.toggle("rv-actief", aan);
      marks.forEach(function (x) { x.classList.toggle("kb-opm-actief", aan); });
    }
    k.addEventListener("mouseenter", function () { actief(true); });
    k.addEventListener("mouseleave", function () { actief(false); });
    k.addEventListener("focusin", function () { actief(true); });
    k.addEventListener("focusout", function () { actief(false); });
    marks.forEach(function (x) {
      x.addEventListener("click", function () { naar(k, false); });
      x.addEventListener("mouseenter", function () { actief(true); });
      x.addEventListener("mouseleave", function () { actief(false); });
    });
    var toon = k.querySelector(".rv-toon");
    if (toon) { toon.hidden = false; toon.addEventListener("click", function () { naar(m, true); }); }
  });

  /* --- De marge indelen: elke kaart op de hoogte van zijn tekst, zonder overlap ----------------------- */
  var breed = window.matchMedia ? window.matchMedia("(min-width: 1101px)") : { matches: true };
  var nieuwWens = -1;
  function indelen() {
    gepland = 0;
    if (!marge) return;
    var zweeft = breed.matches;
    marge.classList.toggle("rv-zweeft", zweeft);
    var items = kaarten.slice();
    if (nieuw && !nieuw.hidden) items.unshift(nieuw);
    if (!zweeft) {
      items.forEach(function (k) { k.style.top = ""; });
      marge.style.minHeight = "";
      return;
    }
    var mtop = marge.getBoundingClientRect().top;
    var kop = marge.querySelector(".rv-marge-kopregel");
    var leeg = document.getElementById("rv-opm-leeg");
    var start = kop.offsetTop + kop.offsetHeight + 8;
    if (leeg && !leeg.hidden) start = leeg.offsetTop + leeg.offsetHeight + 8;
    var lijst = items.map(function (k) {
      var wens = -1;
      if (k === nieuw) wens = nieuwWens;
      else { var m = plek[k.getAttribute("data-nr")]; if (m) wens = m.getBoundingClientRect().top - mtop - 8; }
      return { k: k, wens: wens };
    });
    // Algemene opmerkingen bovenaan, daarna op volgorde van de tekst. Bij gelijke hoogte de nieuwe het laatst.
    lijst.sort(function (a, b) { return a.wens - b.wens || (a.k === nieuw ? 1 : b.k === nieuw ? -1 : 0); });
    var onder = start;
    lijst.forEach(function (x) {
      var top = Math.max(x.wens, onder);
      x.k.style.top = top + "px";
      onder = top + x.k.offsetHeight + 10;
    });
    marge.style.minHeight = onder + "px";
  }
  window.addEventListener("resize", straks);
  if (breed.addEventListener) breed.addEventListener("change", straks);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(straks);
  document.querySelectorAll("details").forEach(function (d) { d.addEventListener("toggle", straks); });

  /* --- Nieuwe opmerking ------------------------------------------------------------------------------- */
  var veld = document.getElementById("rv-citaat"), vak = document.getElementById("rv-citaat-vak");
  var toonTekst = document.getElementById("rv-citaat-tekst"), wis = document.getElementById("rv-citaat-wis");
  var invoer = document.getElementById("rv-tekst"), zelf = document.getElementById("rv-citaat-invoer");
  var annuleer = document.getElementById("rv-nieuw-annuleer"), algKnop = document.getElementById("rv-alg-knop");
  var terugNa = null;

  function zetCitaat(t) {
    veld.value = t;
    toonTekst.textContent = t;
    vak.hidden = !t;
    if (zelf && zelf.value !== t) zelf.value = t;
    straks();
  }
  function openNieuw(citaat, wens, vanaf) {
    terugNa = vanaf || null;
    nieuw.hidden = false;
    zetCitaat(citaat);
    var zelfVak = document.getElementById("rv-citaat-zelf");
    if (zelfVak) zelfVak.hidden = !!citaat;
    nieuwWens = wens;
    indelen();
    if (!breed.matches) nieuw.scrollIntoView({ behavior: "smooth", block: "center" });
    invoer.focus({ preventScroll: breed.matches });
  }
  function sluitNieuw(wissen) {
    if (wissen) { invoer.value = ""; zetCitaat(""); }
    nieuw.hidden = true;
    straks();
    var t = terugNa && document.contains(terugNa) ? terugNa : algKnop;
    if (t && t.focus) t.focus();
  }

  if (magReageren && nieuw && veld) {
    nieuw.hidden = true;
    if (annuleer) { annuleer.hidden = false; annuleer.addEventListener("click", function () { sluitNieuw(true); }); }
    // Escape: het kaartje gaat dicht, maar wat je typte blijft bewaard (Afronden waarschuwt ervoor).
    nieuw.addEventListener("keydown", function (e) { if (e.key === "Escape") { e.preventDefault(); sluitNieuw(false); } });
    if (algKnop) { algKnop.hidden = false; algKnop.addEventListener("click", function () { openNieuw("", -1, algKnop); }); }
    if (zelf) zelf.addEventListener("input", function () { var t = zelf.value.trim(); veld.value = t; toonTekst.textContent = t; vak.hidden = !t; });
    if (wis) wis.addEventListener("click", function () {
      zetCitaat("");
      var zelfVak = document.getElementById("rv-citaat-zelf");
      if (zelfVak) zelfVak.hidden = false;
      invoer.focus();
    });

    // Tekst selecteren: een knop "Opmerking" bij de selectie.
    var knop = document.createElement("button");
    knop.type = "button"; knop.className = "rv-selectieknop"; knop.textContent = "Opmerking";
    knop.setAttribute("aria-label", "Opmerking bij de geselecteerde tekst");
    // Direct na de tekst in de volgorde, zodat Tab hem na een selectie met het toetsenbord vindt (ronde B, M20).
    knop.hidden = true; tekst.parentNode.insertBefore(knop, tekst.nextSibling);
    var gekozen = "", gekozenTop = -1;
    var geselecteerd = function () {
      var sel = window.getSelection();
      if (!sel || sel.isCollapsed || !sel.rangeCount) return "";
      var r = sel.getRangeAt(0);
      if (!tekst.contains(r.commonAncestorContainer)) return "";
      // Weggehaalde tekst (<del>) en de nummers van markeringen horen niet bij het citaat.
      var kopie = document.createElement("div"); kopie.appendChild(r.cloneContents());
      kopie.querySelectorAll("del, .kb-opm-nr, .rv-vs-nr, .kb-sr").forEach(function (n) { n.remove(); });
      return K.normaal(kopie.textContent).slice(0, 1000);
    };
    var bijSelectie = function () {
      setTimeout(function () {
        gekozen = geselecteerd();
        if (!gekozen) { knop.hidden = true; return; }
        var rect = window.getSelection().getRangeAt(0).getBoundingClientRect();
        var o = blad.getBoundingClientRect();
        knop.style.top = (rect.bottom - o.top + 6) + "px";
        knop.style.left = Math.max(8, rect.left - o.left) + "px";
        gekozenTop = marge ? rect.top - marge.getBoundingClientRect().top - 8 : -1;
        knop.hidden = false;
      }, 10);
    };
    document.addEventListener("mouseup", function (e) { if (e.target !== knop) bijSelectie(); });
    document.addEventListener("keyup", function (e) {
      if (e.shiftKey || /^(Arrow|Home|End)/.test(e.key)) bijSelectie();
    });
    knop.addEventListener("mousedown", function (e) { e.preventDefault(); });
    knop.addEventListener("click", function () {
      knop.hidden = true;
      openNieuw(gekozen, gekozenTop, null);
      var sel = window.getSelection(); if (sel) sel.removeAllRanges();
    });
  }

  /* --- Vensters ---------------------------------------------------------------------------------------- */
  var terugFocus = new WeakMap();
  function venster(d, vanaf) {
    terugFocus.set(d, vanaf || document.activeElement);
    if (d.showModal) d.showModal(); else d.setAttribute("open", "");
  }
  function dicht(d) { if (d.open && d.close) d.close(); else d.removeAttribute("open"); }
  document.querySelectorAll("dialog.rv-venster-laag, dialog.rv-lees").forEach(function (d) {
    d.addEventListener("close", function () {
      var t = terugFocus.get(d);
      if (t && t.focus && document.contains(t)) { try { t.focus(); } catch (e) { /* niet erg */ } }
    });
    d.querySelectorAll("[data-rv-sluit]").forEach(function (b) { b.addEventListener("click", function () { dicht(d); }); });
  });

  // Weghalen: eerst vragen.
  var wegVenster = document.getElementById("rv-weg"), wegJa = document.getElementById("rv-weg-ja"), wegForm = null;
  document.querySelectorAll(".rv-weg-form").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (!wegVenster || f.dataset.bevestigd === "1") return;
      e.preventDefault();
      wegForm = f;
      document.getElementById("rv-weg-titel").textContent = "Opmerking " + f.getAttribute("data-nr") + " weghalen?";
      venster(wegVenster, f.querySelector("button"));
      // De focus op Annuleren: Enter haalt dan niet per ongeluk iets weg.
      wegVenster.querySelector("[data-rv-sluit]").focus();
    });
  });
  if (wegJa) wegJa.addEventListener("click", function () {
    if (!wegForm) return;
    wegForm.dataset.bevestigd = "1";
    var b = wegForm.querySelector("button[name=actie]");
    if (wegForm.requestSubmit) wegForm.requestSubmit(b);
    else { var h = document.createElement("input"); h.type = "hidden"; h.name = "actie"; h.value = b.value; wegForm.appendChild(h); wegForm.submit(); }
  });

  // Afronden…
  var afrKnop = document.getElementById("rv-afronden-knop"), afr = document.getElementById("rv-afronden");
  if (afrKnop && afr) {
    afrKnop.hidden = false;
    var afrTekst = document.getElementById("rv-afronden-tekst"), afrCitaat = document.getElementById("rv-afronden-citaat");
    var afrOpen = document.getElementById("rv-afronden-open"), fout = document.getElementById("rv-afronden-fout");
    afrKnop.addEventListener("click", function () {
      var nogOpen = !!(invoer && invoer.value.trim());
      afrOpen.hidden = !nogOpen;
      if (nogOpen) { afrTekst.value = invoer.value; afrCitaat.value = veld.value; }
      fout.hidden = true;
      venster(afr, afrKnop);
      afrTekst.focus();
    });
    document.getElementById("rv-keuze-terug").addEventListener("click", function (e) {
      if (!kaarten.length && !afrTekst.value.trim()) {
        e.preventDefault();
        fout.hidden = false;
        afrTekst.focus();
      }
    });
  }

  // Bekijk als medewerker.
  var leesKnop = document.getElementById("rv-lees-knop"), lees_ = document.getElementById("rv-lees");
  if (leesKnop && lees_) {
    leesKnop.hidden = false;
    var frame = document.getElementById("rv-lees-frame");
    leesKnop.addEventListener("click", function () {
      if (!frame.getAttribute("src")) frame.src = leesKnop.getAttribute("data-url");
      venster(lees_, leesKnop);
      lees_.querySelector("[data-rv-sluit]").focus();
    });
    // Escape in het voorbeeld zelf (een iframe): voorbeeld.js stuurt een bericht.
    window.addEventListener("message", function (e) {
      if (e.origin === window.location.origin && e.data && e.data.type === "kb-voorbeeld-esc" && lees_.open) dicht(lees_);
    });
  }

  indelen();
})();
