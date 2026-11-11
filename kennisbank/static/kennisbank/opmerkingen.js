/* Opmerkingen bij geselecteerde tekst (reviewproces, stap D).
 *
 * Gedeeld door de leesweergave van de reviewer (/review/<id>/) en het live voorbeeld in het volledig scherm
 * van de redacteur. Een opmerking bewaart het citaat: de tekst waar hij over ging. Hier zoeken we dat citaat
 * in de getoonde tekst en zetten er een gele markering met een nummer om. Staat het citaat er niet meer
 * (de redacteur paste de zin aan), dan blijft de opmerking met het oorspronkelijke citaat in de lijst staan,
 * met "tekst is intussen gewijzigd".
 *
 * Alles via textContent en DOM-methodes: geen innerHTML met tekst van gebruikers.
 */
(function () {
  "use strict";

  function normaal(s) { return (s || "").replace(/\s+/g, " ").trim(); }

  // Alle tekstknopen onder `root`, behalve die in <del> (weggehaalde tekst in de verschilweergave) en in
  // markeringen die we zelf eerder plaatsten (het nummer).
  function tekstknopen(root) {
    var uit = [], walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        for (var p = n.parentNode; p && p !== root; p = p.parentNode) {
          if (p.nodeName === "DEL" || (p.classList && p.classList.contains("kb-opm-nr"))) return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    while (walker.nextNode()) uit.push(walker.currentNode);
    return uit;
  }

  // Zoek `citaat` in de tekst onder root (witruimte telt als één spatie) en zet er <mark>-elementen om.
  // Geeft het eerste <mark> terug, of null als het citaat er niet (meer) staat.
  function markeer(root, citaat, nr) {
    var zoek = normaal(citaat);
    if (!zoek) return null;
    var knopen = tekstknopen(root), tekens = [], kaart = [], vorigSpatie = true;
    knopen.forEach(function (k) {
      var s = k.nodeValue;
      for (var i = 0; i < s.length; i++) {
        var c = s[i];
        if (/\s/.test(c)) { if (vorigSpatie) continue; c = " "; vorigSpatie = true; } else vorigSpatie = false;
        tekens.push(c); kaart.push([k, i]);
      }
    });
    var tekst = tekens.join(""), pos = tekst.indexOf(zoek);
    if (pos < 0) pos = tekst.toLowerCase().indexOf(zoek.toLowerCase());
    if (pos < 0) return null;
    var eind = pos + zoek.length - 1, stukken = [];
    // Per tekstknoop het stuk [van, tot) dat bij het citaat hoort.
    for (var j = pos; j <= eind; j++) {
      var k = kaart[j][0], off = kaart[j][1], laatste = stukken[stukken.length - 1];
      if (laatste && laatste.knoop === k) laatste.tot = off + 1; else stukken.push({ knoop: k, van: off, tot: off + 1 });
    }
    var eerste = null;
    // Van achter naar voren splitsen, zodat de offsets van eerdere stukken blijven kloppen.
    for (var s = stukken.length - 1; s >= 0; s--) {
      var st = stukken[s], midden = st.knoop.splitText(st.van);
      midden.splitText(st.tot - st.van);
      var m = document.createElement("mark");
      m.className = "kb-opm"; m.dataset.nr = String(nr);
      midden.parentNode.insertBefore(m, midden); m.appendChild(midden);
      eerste = m;
    }
    var sup = document.createElement("sup"); sup.className = "kb-opm-nr"; sup.textContent = String(nr);
    sup.setAttribute("aria-label", "opmerking " + nr);
    eerste.insertBefore(sup, eerste.firstChild);
    return eerste;
  }

  // Een element zichtbaar maken (dichte <details> openen) en ernaartoe scrollen.
  function toon(el) {
    for (var p = el.parentNode; p; p = p.parentNode) if (p.nodeName === "DETAILS") p.open = true;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("kb-opm-flits");
    setTimeout(function () { el.classList.remove("kb-opm-flits"); }, 1200);
  }

  function regel(tekst, klasse) { var p = document.createElement("span"); p.className = klasse; p.textContent = tekst; return p; }

  /* Zet de markeringen in `tekstRoot` en vul `lijst` (een <ol>) met de opmerkingen.
   * items: [{nr, wie, wanneer, tekst, citaat}]. Geeft het aantal gevonden citaten terug. */
  function plaats(tekstRoot, lijst, items) {
    var gevonden = 0;
    lijst.textContent = "";
    items.forEach(function (o) {
      var mark = o.citaat ? markeer(tekstRoot, o.citaat, o.nr) : null;
      if (mark) gevonden++;
      var li = document.createElement("li");
      li.className = "kb-opm-item" + (o.citaat && !mark ? " kb-opm-weg" : "");
      li.id = "kb-opm-" + o.nr;
      li.appendChild(regel(o.nr + ". " + o.wie + (o.wanneer ? " · " + o.wanneer : ""), "kb-opm-wie"));
      if (o.citaat) {
        var q = document.createElement("q"); q.className = "kb-opm-citaat"; q.textContent = o.citaat; li.appendChild(q);
        if (!mark) li.appendChild(regel("tekst is intussen gewijzigd", "kb-opm-status"));
      } else {
        li.appendChild(regel("algemene opmerking", "kb-opm-status"));
      }
      if (o.voorlopig) li.appendChild(regel("voorlopig: teruggeroepen terwijl het team nog bezig was", "kb-opm-status kb-opm-voorlopig"));
      li.appendChild(regel(o.tekst, "kb-opm-tekst"));
      if (mark) {
        li.tabIndex = 0; li.classList.add("kb-opm-klikbaar");
        var ga = function () { toon(mark); };
        li.addEventListener("click", ga);
        li.addEventListener("keydown", function (e) { if (e.key === "Enter") ga(); });
        mark.addEventListener("click", function () { toon(li); });
      }
      lijst.appendChild(li);
    });
    return gevonden;
  }

  window.KbOpmerkingen = { markeer: markeer, plaats: plaats, normaal: normaal };
})();
