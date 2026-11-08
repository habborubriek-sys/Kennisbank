/* Voorbeeldpaneel: krijgt de tekst uit de editor via postMessage en toont hem zoals in de kennisbank.
 * Dezelfde opdeling als inhoud.blokken() op de server: <section class="sectie"> = sectie, de rest = vrije tekst.
 */
(function () {
  "use strict";
  var body = document.body, t = document.getElementById("onbToggle"), aan = false;
  try { aan = localStorage.getItem("kb.voorbeeld.onb") === "1"; } catch (e) {}
  function zetOnb(v) { aan = v; body.classList.toggle("onboarding", v); t.setAttribute("aria-pressed", String(v)); try { localStorage.setItem("kb.voorbeeld.onb", v ? "1" : "0"); } catch (e) {} }
  zetOnb(aan);
  t.addEventListener("click", function () { zetOnb(!aan); });

  var open = {};  // welke secties de gebruiker open/dicht heeft gezet, op nummer
  var SOORT = { werkinstructie: "Werkinstructie", werkafspraak: "Werkafspraak", proces: "Proces" };

  function schoonNode(root) {
    // Veiligheidsnet: het is eigen tekst van de redacteur, maar scripts en event-attributen horen er niet in.
    root.querySelectorAll("script,style,iframe,object,embed,img,form,input").forEach(function (n) { n.remove(); });
    // Typ-ruimte rond secties (zie beheer-editor.js) wordt niet opgeslagen en dus ook niet getoond.
    root.querySelectorAll("p.tussenruimte").forEach(function (n) { if (n.textContent.trim()) n.classList.remove("tussenruimte"); else n.remove(); });
    root.querySelectorAll("*").forEach(function (n) {
      Array.prototype.slice.call(n.attributes).forEach(function (a) {
        if (/^on/i.test(a.name) || (a.name === "href" && /^\s*javascript:/i.test(a.value))) n.removeAttribute(a.name);
      });
    });
  }

  function render(d) {
    document.getElementById("artTitel").textContent = (d.titel || "").trim() || "(nog geen titel)";
    var sv = document.getElementById("samenvatting"); sv.textContent = (d.samenvatting || "").trim(); sv.hidden = !sv.textContent;
    var so = document.getElementById("soort"); so.textContent = SOORT[d.soort] || ""; so.className = "type " + (d.soort || ""); so.hidden = !so.textContent;

    var bron = document.createElement("div"); bron.innerHTML = d.inhoud || ""; schoonNode(bron);
    var uit = document.createElement("div"), vrij = document.createElement("div"), n = 0, heeftSectie = false;
    // Ook een bewuste lege regel tussen twee secties is een tekstblok (net als inhoud.blokken op de server).
    function flush() { if (vrij.children.length) { vrij.className = "inleiding"; uit.appendChild(vrij); } vrij = document.createElement("div"); }
    Array.prototype.slice.call(bron.childNodes).forEach(function (node) {
      if (node.nodeType === 1 && node.tagName === "SECTION" && node.classList.contains("sectie")) {
        flush(); n++; heeftSectie = true;
        var kopEl = node.querySelector("h2.sectie-kop"), kop = kopEl ? kopEl.textContent.replace(/\s+/g, " ").trim() : "";
        if (kopEl) kopEl.remove();
        var det = document.createElement("details"); det.className = "sec"; det.id = "sectie-" + n;
        det.open = n in open ? open[n] : n === 1;
        var sum = document.createElement("summary"); sum.textContent = kop || ("Sectie " + n); det.appendChild(sum);
        var bd = document.createElement("div"); bd.className = "body"; while (node.firstChild) bd.appendChild(node.firstChild); det.appendChild(bd);
        (function (nr) { det.addEventListener("toggle", function () { open[nr] = det.open; }); })(n);
        uit.appendChild(det);
      } else vrij.appendChild(node);
    });
    flush();
    var secs = document.getElementById("sections"); secs.innerHTML = "";
    if (!uit.childNodes.length) secs.innerHTML = '<div class="empty">Nog geen tekst.</div>'; else while (uit.firstChild) secs.appendChild(uit.firstChild);
    document.getElementById("secbar").hidden = !heeftSectie;
  }

  document.getElementById("toggleAll").addEventListener("click", function () {
    var ds = Array.prototype.slice.call(document.querySelectorAll("details.sec")), o = ds.some(function (d) { return !d.open; });
    ds.forEach(function (d, i) { d.open = o; open[i + 1] = o; });
    this.textContent = o ? "Alles inklappen" : "Alles uitklappen";
  });

  // Vaste inhoud: dit scherm wordt ook gebruikt om een eerdere versie te bekijken. Dan staat de tekst
  // al in de pagina en is er geen editor die hem doorgeeft.
  var vast = document.getElementById("vasteInhoud");
  if (vast) {
    try { render(JSON.parse(vast.textContent)); } catch (e) {}
    return;
  }

  window.addEventListener("message", function (e) {
    if (e.origin !== location.origin || !e.data || e.data.type !== "kb-voorbeeld") return;
    render(e.data);
  });
  if (window.parent !== window) window.parent.postMessage({ type: "kb-voorbeeld-klaar" }, location.origin);
})();
