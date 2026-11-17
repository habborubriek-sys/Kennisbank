/* De pagina Hulp (1.36.0). Op een smal scherm staat het menu boven het artikel; dan klapt het dicht, zodat je
 * het artikel meteen ziet. Op een breed scherm staat het ernaast en blijft het open. */
(function () {
  "use strict";
  var menu = document.querySelector(".hulp-uitklap");
  if (!menu || !window.matchMedia) return;
  var smal = window.matchMedia("(max-width: 820px)");
  function zet() { menu.open = !smal.matches; }
  zet();
  if (smal.addEventListener) smal.addEventListener("change", zet);
})();
