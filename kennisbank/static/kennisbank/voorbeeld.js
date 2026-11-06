/* Voorbeeldpagina: onboarding-schakelaar en alles uit-/inklappen, zonder server. */
(function () {
  var body = document.body, t = document.getElementById("onbToggle");
  var aan = false;
  try { aan = localStorage.getItem("kb.voorbeeld.onb") === "1"; } catch (e) {}
  function zet(v) { aan = v; body.classList.toggle("onboarding", v); t.setAttribute("aria-pressed", String(v)); try { localStorage.setItem("kb.voorbeeld.onb", v ? "1" : "0"); } catch (e) {} }
  zet(aan);
  t.addEventListener("click", function () { zet(!aan); });
  var ta = document.getElementById("toggleAll");
  if (ta) ta.addEventListener("click", function () {
    var ds = Array.prototype.slice.call(document.querySelectorAll("details.sec"));
    var open = ds.some(function (d) { return !d.open; });
    ds.forEach(function (d) { d.open = open; });
    ta.textContent = open ? "Alles inklappen" : "Alles uitklappen";
  });
})();
