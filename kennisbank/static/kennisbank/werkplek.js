/* Werkplek (1.29.0, ronde B, review 1.27.0 L4): de selectiebalk zegt hoeveel voorstellen je hebt aangevinkt,
 * ook voor de schermlezer (role=status). */
(function () {
  "use strict";
  function start() {
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
