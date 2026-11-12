/* Het gedrag van het bewerkscherm voor artikelen en nieuwsberichten (1.22.0).
 *
 * Sinds 1.24.0 bouwt de server het scherm helemaal op (change_form.html): elk veld staat meteen op zijn plek,
 * er wordt niets verhuisd en er is geen "oud scherm" meer. Dit script doet alleen nog het gedrag: panelen
 * open en dicht, Enter van titel naar samenvatting naar tekst, de samenvatting die meegroeit, de opmerkingen
 * van het reviewteam in de marge en "Bekijk als medewerker".
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

    var titel = form.elements.namedItem("titel");
    var samen = form.elements.namedItem("samenvatting");
    // Fouten van het hele formulier staan boven het blad; zet ze in beeld.
    var fout = $(".errornote", form);
    if (fout) {
      // Ronde A (review 1.27.0, M11): "Corrigeer de onderstaande fout" wees naar een veld dat in een paneel
      // rechts kan staan. Noem het veld en de plek.
      var gezien = {};
      var plekken = $$('[aria-invalid="true"]', form).map(function (veld) {
        var label = veld.id && $('label[for="' + veld.id + '"]', form);
        var naam = (label ? label.textContent : veld.getAttribute("aria-label") || veld.name || "").replace(/[:*]\s*$/, "").trim();
        var paneelEl = veld.closest(".kb-paneel");
        var waar = paneelEl ? " (in " + (paneelEl.getAttribute("aria-label") || "het paneel") + ", rechts)" : "";
        if (!naam || gezien[naam]) return "";
        gezien[naam] = true;
        return naam + waar;
      }).filter(Boolean);
      if (plekken.length) fout.textContent = "Nog niet opgeslagen. Kijk naar: " + plekken.join(", ") + ".";
      if (fout.scrollIntoView) fout.scrollIntoView({ block: "center" });
    }

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
    function balkHoogte() {
      document.body.style.setProperty("--kb-balk-h", balk.offsetHeight + "px");
      var wb = document.querySelector(".kb-ae-werkbalk");
      if (wb) document.body.style.setProperty("--kb-werkbalk-h", wb.offsetHeight + "px"); // de lade begint eronder
    }
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

    // Bij een nieuw artikel of bericht zet Django de cursor op het eerste element van het formulier: dat is nu
    // een knop in de balk, die er dan "aan" uitziet. Zet hem in de titel, daar begin je (1.25.0). Django laadt dat
    // script met async, dus pas na "load" weten we zeker dat het klaar is.
    function focusGoed() {
      if (!balk.contains(document.activeElement)) return;
      if (titel && !titel.value) titel.focus();
      else document.activeElement.blur();
    }
    if (document.readyState === "complete") setTimeout(focusGoed, 0);
    else window.addEventListener("load", focusGoed);

    // --- Meer ▾: dicht bij een klik ernaast of Escape ------------------------------------
    var meer = $(".kb-meer", balk);
    if (meer) {
      document.addEventListener("click", function (e) { if (meer.open && !meer.contains(e.target)) meer.open = false; });
      document.addEventListener("keydown", function (e) { if (e.key === "Escape" && meer.open) { meer.open = false; $("summary", meer).focus(); } });
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
