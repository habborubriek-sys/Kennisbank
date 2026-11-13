/* Licht of donker op de site (1.28.0, besluit van Alex bij review 1.27.0 M22).
 *
 * Standaard volgt de site het apparaat: staat de telefoon of laptop op donker, dan is de site donker. Met de
 * knop "Donker"/"Licht" in de bovenbalk draai je dat om; die keuze onthoudt deze browser (localStorage, gaat
 * niet naar de server). Dit script staat in de <head> zonder defer, zodat de keuze al geldt voordat de pagina
 * zichtbaar wordt: geen flits van de verkeerde kleur. Het beheer gebruikt dit niet; dat is altijd licht.
 */
(function () {
  "use strict";
  var SLEUTEL = "kb-weergave";
  var root = document.documentElement;
  root.classList.add("kb-js"); // 1.31.1: CSS weet dan al vóór het tekenen dat er JavaScript is

  function lees() { try { return localStorage.getItem(SLEUTEL); } catch (e) { return null; } }
  function bewaar(w) { try { localStorage.setItem(SLEUTEL, w); } catch (e) { /* privévenster: alleen deze pagina */ } }
  function apparaatDonker() { return !!(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches); }

  function toepassen(keuze) {
    if (keuze === "donker") root.setAttribute("data-theme", "dark");
    else if (keuze === "licht") root.setAttribute("data-theme", "light");
    else root.removeAttribute("data-theme");
  }
  function isDonker() {
    var t = root.getAttribute("data-theme");
    return t ? t === "dark" : apparaatDonker();
  }

  toepassen(lees());

  function knoppenBijwerken() {
    var donker = isDonker();
    Array.prototype.forEach.call(document.querySelectorAll("[data-kb-thema]"), function (b) {
      b.setAttribute("aria-pressed", donker ? "true" : "false");
      b.title = donker ? "Terug naar de lichte weergave" : "Donkere weergave, prettig in het donker";
      var icoon = b.querySelector(".kb-thema-icoon");
      if (icoon) icoon.textContent = donker ? "☀" : "☾";
    });
  }

  function start() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-kb-thema]"), function (b) {
      b.hidden = false;
      b.addEventListener("click", function () {
        var nieuw = isDonker() ? "licht" : "donker";
        // Is de keuze gelijk aan wat het apparaat doet, dan niets onthouden: dan volgt de site het apparaat weer.
        var volgt = (nieuw === "donker") === apparaatDonker();
        if (volgt) {
          try { localStorage.removeItem(SLEUTEL); } catch (e) { /* niet erg */ }
          toepassen(null);
        } else {
          bewaar(nieuw);
          toepassen(nieuw);
        }
        knoppenBijwerken();
      });
    });
    knoppenBijwerken();
    if (window.matchMedia) {
      var mq = window.matchMedia("(prefers-color-scheme: dark)");
      var luister = function () { knoppenBijwerken(); };
      if (mq.addEventListener) mq.addEventListener("change", luister);
      else if (mq.addListener) mq.addListener(luister);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
