/* Werkplek (1.29.0, ronde B, review 1.27.0 L4): de selectiebalk zegt hoeveel voorstellen je hebt aangevinkt,
 * ook voor de schermlezer (role=status). */
(function () {
  "use strict";
  // 1.29.1: de lijst met collega's onthoudt of hij open of dicht was (per browser). Opent de server hem omdat
  // je in de bak van een collega kijkt of er iets te lang ligt (data-kb-vast), dan blijft hij open.
  function collegas() {
    var d = document.getElementById("kb-collegas");
    if (!d) return;
    var sleutel = "kb-collegas";
    if (!d.hasAttribute("data-kb-vast")) {
      try { d.open = localStorage.getItem(sleutel) === "open"; } catch (e) { /* niet erg */ }
    }
    d.addEventListener("toggle", function () {
      try { localStorage.setItem(sleutel, d.open ? "open" : "dicht"); } catch (e) { /* niet erg */ }
    });
  }

  function start() {
    collegas();
    var teller = document.getElementById("kb-selectie-teller");
    if (!teller) return;
    var vakjes = document.querySelectorAll('input[type="checkbox"][form="kb-selectie"]');
    function tel() {
      var n = Array.prototype.filter.call(vakjes, function (v) { return v.checked; }).length;
      teller.textContent = n ? n + (n === 1 ? " voorstel" : " voorstellen") + " aangevinkt." : "";
    }
    Array.prototype.forEach.call(vakjes, function (v) { v.addEventListener("change", tel); });
    tel();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
