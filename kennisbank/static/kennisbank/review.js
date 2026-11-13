/* Leesweergave voor reviewers (/review/<id>/): tekst selecteren voor een opmerking, en de opmerkingen
 * als genummerde markeringen in de tekst (stap D). Zonder JavaScript werkt de pagina ook: dan zijn alle
 * opmerkingen algemene opmerkingen en staat de lijst gewoon rechts. */
(function () {
  "use strict";
  var tekst = document.querySelector(".rv-verschil");
  var data = document.getElementById("rv-opmerkingen-data");
  var lijst = document.getElementById("rv-opmerkingen-lijst");
  if (tekst && data && lijst && window.KbOpmerkingen) {
    try {
      var items = JSON.parse(data.textContent);
      if (items.length) { window.KbOpmerkingen.plaats(tekst, lijst, items); lijst.hidden = false; }
      var leeg = document.getElementById("rv-opmerkingen-leeg");
      if (leeg) leeg.hidden = items.length > 0;
      var oud = document.getElementById("rv-opmerkingen-zonderjs");
      if (oud) oud.hidden = true;
    } catch (e) { /* de lijst zonder markeringen blijft staan */ }
  }

  // Selecteren: een knop bij de selectie, die het citaat in het opmerkingenvak zet.
  var veld = document.getElementById("rv-citaat"), vak = document.getElementById("rv-citaat-vak");
  var toonTekst = document.getElementById("rv-citaat-tekst"), wis = document.getElementById("rv-citaat-wis");
  var invoer = document.getElementById("rv-tekst");
  if (!tekst || !veld || !vak) return;
  var knop = document.createElement("button");
  knop.type = "button"; knop.className = "tb primary rv-selectieknop"; knop.textContent = "Opmerking bij deze tekst";
  // Ronde B (M20): direct na de tekst in de volgorde, zodat Tab hem na een selectie met het toetsenbord vindt.
  knop.hidden = true; tekst.parentNode.insertBefore(knop, tekst.nextSibling);
  var gekozen = "";
  var zelf = document.getElementById("rv-citaat-invoer");

  function geselecteerd() {
    var sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) return "";
    var r = sel.getRangeAt(0);
    if (!tekst.contains(r.commonAncestorContainer)) return "";
    // Weggehaalde tekst (<del>) en de nummers van markeringen horen niet bij het citaat.
    var kopie = document.createElement("div"); kopie.appendChild(r.cloneContents());
    kopie.querySelectorAll("del, .kb-opm-nr, .kb-sr").forEach(function (n) { n.remove(); });
    return window.KbOpmerkingen ? window.KbOpmerkingen.normaal(kopie.textContent).slice(0, 1000) : "";
  }

  function bijSelectie() {
    setTimeout(function () {
      gekozen = geselecteerd();
      if (!gekozen) { knop.hidden = true; return; }
      var rect = window.getSelection().getRangeAt(0).getBoundingClientRect();
      var ouder = knop.offsetParent || document.body;
      var o = ouder.getBoundingClientRect();
      knop.style.top = (rect.bottom - o.top + ouder.scrollTop + 6) + "px";
      knop.style.left = (rect.left - o.left + ouder.scrollLeft) + "px";
      knop.hidden = false;
    }, 10);
  }
  document.addEventListener("mouseup", bijSelectie);
  // Ook met het toetsenbord (Shift + pijltjes): de site deed dat al, de reviewpagina nog niet.
  document.addEventListener("keyup", function (e) {
    if (e.shiftKey || /^(Arrow|Home|End)/.test(e.key)) bijSelectie();
  });
  function zetCitaat(t) {
    veld.value = t;
    toonTekst.textContent = t;
    vak.hidden = !t;
    if (zelf && zelf.value !== t) zelf.value = t;
  }
  if (zelf) zelf.addEventListener("input", function () { var t = zelf.value.trim(); veld.value = t; toonTekst.textContent = t; vak.hidden = !t; });
  knop.addEventListener("mousedown", function (e) { e.preventDefault(); });
  knop.addEventListener("click", function () {
    zetCitaat(gekozen); knop.hidden = true;
    if (invoer) invoer.focus();
  });
  if (wis) wis.addEventListener("click", function () { zetCitaat(""); if (invoer) invoer.focus(); });
})();
