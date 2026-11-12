/* De indeling van het bewerkscherm voor artikelen (1.22.0).
 *
 * De server levert het gewone beheerformulier, plus (in change_form.html) een balk, een leeg blad en
 * lege panelen. Dit script verhuist de velden naar hun plek: titel, samenvatting en tekst naar het blad,
 * de overige velden naar het paneel Eigenschappen, de versiegeschiedenis naar Geschiedenis. Alles blijft
 * binnen het <form>, dus opslaan, de controles op de server en de kladversie werken zoals altijd.
 * Werkt JavaScript niet, dan staat alles gewoon onder elkaar.
 *
 * Draait vóór beheer-editor.js (volgorde in ArtikelAdmin.Media), zodat de editor op zijn nieuwe plek
 * wordt gemaakt.
 */
(function () {
  "use strict";
  var VOORBEELD_URL = "/beheer/kennisbank/artikel/voorbeeld/";

  function $(sel, ouder) { return (ouder || document).querySelector(sel); }
  function $$(sel, ouder) { return Array.prototype.slice.call((ouder || document).querySelectorAll(sel)); }

  function opbouwen() {
    var balk = $("form .kb-balk");
    var form = balk && balk.closest("form");
    if (!form) return;
    document.body.classList.add("kb-scherm");

    // --- Titel, samenvatting en tekst naar het blad -------------------------------------
    var titel = form.elements.namedItem("titel");
    var samen = form.elements.namedItem("samenvatting");
    // Elk veld met een plek op het blad (titel, samenvatting, inhoud of tekst) gaat daarheen, met zijn foutmelding.
    $$("[data-kb-plek]", form).forEach(function (plek) {
      var veld = form.elements.namedItem(plek.dataset.kbPlek);
      if (!veld || !veld.closest) return;
      var rij = veld.closest(".form-row");
      plek.appendChild(veld);
      if (rij) $$(".errorlist", rij).forEach(function (fout) { plek.appendChild(fout); });
    });
    if (titel) {
      var titelPlek = titel.closest("[data-kb-plek]");
      titel.placeholder = (titelPlek && titelPlek.dataset.kbUitleg) || "Titel: waar gaat dit artikel over?";
      titel.setAttribute("aria-label", "Titel");
    }
    if (samen) {
      samen.placeholder = "Samenvatting: in één of twee zinnen wat een medewerker hier vindt. Deze zin verschijnt ook in de zoekresultaten en in het zaaksysteem.";
      samen.setAttribute("aria-label", "Samenvatting");
      samen.rows = 1;
    }
    // De eerste groep velden houdt alleen nog de verborgen stempels over: uit beeld.
    $$("fieldset.module", form).forEach(function (fs) {
      if (fs.closest(".inline-group") || fs.closest(".kb-paneel")) return;
      var zichtbaar = $$(".form-row", fs).filter(function (r) { return !r.classList.contains("hidden") && r.querySelector("input:not([type=hidden]), select, textarea, .readonly"); });
      if (!zichtbaar.length) fs.classList.add("kb-oud-verborgen");
    });

    // --- Overige velden naar Eigenschappen, versies naar Geschiedenis --------------------
    var eig = $("#kb-p-eig", form), gesch = $("#kb-p-gesch", form);
    $$("fieldset.module", form).forEach(function (fs) {
      if (fs.closest(".inline-group") || fs.closest(".kb-paneel") || fs.classList.contains("kb-oud-verborgen")) return;
      eig.appendChild(fs);
    });
    if (gesch) {
      $$(".form-row.field-versie, .form-row.field-gepubliceerd_op", eig).forEach(function (r) { gesch.appendChild(r); });
      $$(".inline-group", form).forEach(function (g) { gesch.appendChild(g); });
    }

    // Meldingen ("is opgeslagen") en foutmeldingen van het hele formulier boven het blad, onder de balk.
    var werkvlak = $(".kb-werkvlak", form);
    var meldingen = $(".messagelist");
    if (meldingen) werkvlak.parentNode.insertBefore(meldingen, werkvlak);
    var fouten = $$(".errornote, ul.errorlist.nonfield", form).filter(function (e) { return !e.closest(".kb-paneel"); });
    if (fouten.length) {
      var vak = document.createElement("div");
      vak.className = "kb-banner kb-banner-spoed";
      fouten.forEach(function (f) { vak.appendChild(f); });
      werkvlak.parentNode.insertBefore(vak, werkvlak);
    }

    // --- Knoppen naar de balk ------------------------------------------------------------
    var plek = $(".kb-balk-afronden", balk);
    var afr = $(".kb-afronden-knop", form);
    if (afr) plek.appendChild(afr);
    else {
      // Nieuw of nog niet gepubliceerd artikel: de gewone opslagknoppen.
      var opslaan = $('.submit-row input[name="_save"]', form);
      var verder = $('.submit-row input[name="_continue"]', form);
      if (verder) { verder.classList.add("kb-balk-opslaan", "kb-balk-opslaan-2"); verder.value = "Opslaan en verder"; plek.appendChild(verder); }
      if (opslaan) { opslaan.classList.add("kb-balk-opslaan"); plek.appendChild(opslaan); }
    }
    // Verwijderen (alleen waar dat mag, zoals bij nieuwsberichten): onderaan het paneel Eigenschappen.
    var weg = $(".submit-row .deletelink", form);
    if (weg && eig) { var p = document.createElement("p"); p.className = "kb-paneel-weg"; p.appendChild(weg); eig.appendChild(p); }

    // --- Panelen -------------------------------------------------------------------------
    function paneel(naam) {
      $$(".kb-paneel", form).forEach(function (p) {
        p.classList.toggle("kb-open", p.id === "kb-p-" + naam && !p.classList.contains("kb-open"));
      });
      $$("[data-kb-paneel]", balk).forEach(function (b) {
        var p = $("#kb-p-" + b.dataset.kbPaneel, form);
        var open = !!p && p.classList.contains("kb-open");
        b.classList.toggle("kb-aan", open);
        b.setAttribute("aria-expanded", open ? "true" : "false");
      });
    }
    $$("[data-kb-paneel]", balk).forEach(function (b) { b.addEventListener("click", function () { paneel(b.dataset.kbPaneel); }); });
    $$(".kb-paneel-sluit", form).forEach(function (b) { b.addEventListener("click", function () { paneel(""); }); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !$(".kb-venster-laag") && !$(".kb-lees")) paneel(""); });
    // Een fout in een veld van een paneel: dat paneel meteen open.
    var metFout = $$(".kb-paneel", form).filter(function (p) { return $(".errorlist li", p); })[0];
    if (metFout) paneel(metFout.id.replace("kb-p-", ""));

    // --- Kleine dingen -------------------------------------------------------------------
    var soortVeld = form.elements.namedItem("soort"), soortLabel = $("[data-kb-soort]", form);
    if (soortVeld && soortLabel && soortVeld.options) {
      var zetSoort = function () { var o = soortVeld.options[soortVeld.selectedIndex]; if (o) soortLabel.textContent = o.text; };
      soortVeld.addEventListener("change", zetSoort);
      zetSoort();
    }
    var balkTitel = $(".kb-balk-titel", balk);
    if (titel && balkTitel) titel.addEventListener("input", function () { balkTitel.textContent = titel.value.trim() || "Nieuw artikel"; });

    // Titel en samenvatting: Enter springt door, de samenvatting groeit mee.
    function groei() { if (!samen) return; samen.style.height = "auto"; samen.style.height = samen.scrollHeight + 2 + "px"; }
    if (samen) { samen.addEventListener("input", groei); window.addEventListener("resize", groei); setTimeout(groei, 0); }
    function naarTekst() { var t = $(".kb-blad .kb-ae-inhoud", form); if (t) t.focus(); }
    if (titel) titel.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); if (samen) samen.focus(); else naarTekst(); } });
    if (samen) samen.addEventListener("keydown", function (e) {
      if (e.key !== "Enter") return;
      e.preventDefault();
      naarTekst();
    });

    // Op slot (ter inzage): ook titel en samenvatting alleen-lezen.
    if (document.getElementById("kb-op-slot")) {
      document.body.classList.add("kb-op-slot");
      [titel, samen].forEach(function (v) { if (v) v.readOnly = true; });
    }

    // De balk is sticky; de werkbalk van de editor plakt eronder.
    function balkHoogte() { document.body.style.setProperty("--kb-balk-h", balk.offsetHeight + "px"); }
    balkHoogte();
    window.addEventListener("resize", balkHoogte);

    // --- Opmerkingen van het reviewteam in de marge ---------------------------------------
    var opmKnop = $("[data-kb-opm]", balk);
    if (opmKnop) {
      var lijst = [];
      try { lijst = JSON.parse(document.getElementById("kb-opmerkingen").textContent); } catch (e) { lijst = []; }
      opmKnop.addEventListener("click", function () {
        var aan = !document.body.classList.contains("kb-met-opm");
        document.body.classList.toggle("kb-met-opm", aan);
        opmKnop.classList.toggle("kb-aan", aan);
        opmKnop.setAttribute("aria-pressed", aan ? "true" : "false");
        if (window.kbInhoudEditor) window.kbInhoudEditor.opmerkingen(aan ? lijst : []);
      });
      // Na teruggeven wil je ze meteen zien.
      if (lijst.length && !document.getElementById("kb-op-slot")) setTimeout(function () { opmKnop.click(); }, 0);
    }

    // --- Bekijk als medewerker ----------------------------------------------------------
    var lees = $("[data-kb-lees]", balk);
    if (lees) lees.addEventListener("click", function () { bekijkAlsMedewerker(form); });
  }

  function bekijkAlsMedewerker(form) {
    if (window.kbInhoudEditor) window.kbInhoudEditor.synchronizeValues();
    var waarde = function (n) { var e = form.elements.namedItem(n); return e ? e.value : ""; };
    var laag = document.createElement("div");
    laag.className = "kb-lees";
    laag.setAttribute("role", "dialog");
    laag.setAttribute("aria-label", "Zo ziet een medewerker het artikel");
    var kop = document.createElement("div");
    kop.className = "kb-lees-balk";
    var t = document.createElement("strong");
    t.textContent = "Kennisbank";
    var tag = document.createElement("span");
    tag.className = "kb-lees-tag";
    tag.textContent = "ZO ZIET EEN MEDEWERKER HET";
    var sluit = document.createElement("button");
    sluit.type = "button";
    sluit.textContent = "Terug naar bewerken";
    kop.appendChild(t);
    kop.appendChild(tag);
    kop.appendChild(sluit);
    var frame = document.createElement("iframe");
    frame.title = "Voorbeeld voor medewerkers";
    frame.src = VOORBEELD_URL;
    laag.appendChild(kop);
    laag.appendChild(frame);
    document.body.appendChild(laag);
    function opKlaar(e) {
      if (e.origin !== location.origin || !e.data || e.data.type !== "kb-voorbeeld-klaar") return;
      frame.contentWindow.postMessage(
        { type: "kb-voorbeeld", titel: waarde("titel"), samenvatting: waarde("samenvatting"), soort: waarde("soort"), inhoud: waarde("inhoud"), opmerkingen: [] },
        location.origin
      );
    }
    function dicht() {
      window.removeEventListener("message", opKlaar);
      document.removeEventListener("keydown", opEsc);
      laag.remove();
    }
    function opEsc(e) { if (e.key === "Escape") dicht(); }
    window.addEventListener("message", opKlaar);
    document.addEventListener("keydown", opEsc);
    sluit.addEventListener("click", dicht);
    sluit.focus();
  }

  document.addEventListener("DOMContentLoaded", opbouwen);
})();
