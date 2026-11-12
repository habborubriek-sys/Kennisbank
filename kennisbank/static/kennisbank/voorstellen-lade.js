/* Verbetervoorstellen in het bewerkscherm: de lade links (1.26.0).
 *
 * De server zet de open voorstellen bij dit artikel als JSON in de pagina (kb-lade-gegevens). Dit script
 * tekent de lade (een tabblad dat uit de linkerrand steekt), markeert de citaten blauw in de tekst met een
 * rond nummer, en houdt twee verborgen velden bij die met het formulier meegaan: welke voorstellen in de
 * lade stonden (kb_lade) en welke zijn aangevinkt (kb_meenemen). Meenemen telt dus pas bij opslaan.
 *
 * Bericht aan de indiener, interne notitie, afwijzen en dubbel gaan meteen naar de server (los van het
 * artikel). Bericht en notitie staan in twee tabbladen, nooit tegelijk in beeld; versturen vraagt een
 * bevestiging (opmerking van Alex: "dicht op elkaar, fout is snel gemaakt").
 */
(function () {
  "use strict";

  function $(s, r) { return (r || document).querySelector(s); }
  function el(tag, cls, tekst) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (tekst != null) e.textContent = tekst;
    return e;
  }
  function venster(o) {
    if (window.kbVenster) return window.kbVenster(o);
    if (window.confirm([o.titel].concat(o.alineas || []).join("\n\n"))) {
      var k = (o.knoppen || []).filter(function (x) { return x.primair; })[0];
      if (k && k.doen) k.doen();
    }
    return null;
  }

  function start() {
    var bron = document.getElementById("kb-lade-gegevens");
    var lade = document.getElementById("kb-lade");
    var lip = document.getElementById("kb-lip");
    if (!bron || !lade || !lip) return;
    var g = JSON.parse(bron.textContent);
    var form = lade.closest("form");
    var spoed = !!document.getElementById("kb-spoed");
    var opSlot = !!g.op_slot && !spoed;
    var lijst = g.voorstellen || [];
    var actief = g.open;
    var tab = {};
    var info = {};
    var bewaard = {}, mee = {};
    lijst.forEach(function (v) { bewaard[v.id] = spoed ? false : !!v.mee; mee[v.id] = bewaard[v.id]; });
    var csrf = form && form.querySelector("input[name=csrfmiddlewaretoken]");
    var verzonden = false;
    if (form) form.addEventListener("submit", function () { verzonden = true; });

    if (!lijst.length) return; // geen open voorstellen: geen lade, geen tabblad
    lade.hidden = false;
    lip.hidden = false;
    document.body.classList.add("kb-met-lade");
    var open = !!actief || sessionStorageLees() === "open";
    zetOpen(open);
    lip.addEventListener("click", function () { zetOpen(!document.body.classList.contains("kb-lade-open")); });

    function sessionStorageLees() { try { return sessionStorage.getItem("kb-lade"); } catch (e) { return null; } }
    function zetOpen(aan) {
      document.body.classList.toggle("kb-lade-open", aan);
      lip.setAttribute("aria-expanded", aan ? "true" : "false");
      $(".kb-lip-pijl", lip).textContent = aan ? "◀" : "▶";
      try { sessionStorage.setItem("kb-lade", aan ? "open" : "dicht"); } catch (e) { /* geen opslag: niet erg */ }
      if (window.kbInhoudEditor && window.kbInhoudEditor.tekenMarge) setTimeout(window.kbInhoudEditor.tekenMarge, 260);
    }

    function nr(v) { return lijst.indexOf(v) + 1; }
    function zoek(id) { return lijst.filter(function (v) { return v.id === id; })[0]; }
    function aantalOnbewaard() { return lijst.filter(function (v) { return mee[v.id] !== bewaard[v.id]; }).length; }

    function velden() {
      $("#kb-lade-ids").value = lijst.map(function (v) { return v.id; }).join(",");
      $("#kb-meenemen").value = lijst.filter(function (v) { return mee[v.id]; }).map(function (v) { return v.id; }).join(",");
    }

    function markeer() {
      var ed = window.kbInhoudEditor;
      if (!ed || !ed.voorstellen) return false;
      info = ed.voorstellen(lijst.map(function (v) { return { id: v.id, nr: nr(v), citaat: v.citaat, actief: v.id === actief }; }));
      return true;
    }

    function infobalk() {
      var sub = document.querySelector(".kb-balk-sub");
      if (!sub) return;
      var oud = sub.querySelector(".kb-lade-info");
      if (oud) oud.remove();
      var n = lijst.filter(function (v) { return mee[v.id]; }).length, o = aantalOnbewaard();
      var span = el("span", "kb-lade-info");
      if (n || o) {
        span.appendChild(el("span", "kb-pil kb-pil-vs", n + " voorstel" + (n === 1 ? "" : "len") + " meegenomen" + (o ? " · " + o + " nog niet opgeslagen" : "")));
      }
      var leg = el("span", "kb-legenda");
      leg.innerHTML = '<span><i class="kb-leg-vs"></i>verbetervoorstel</span><span><i class="kb-leg-opm"></i>opmerking van de review</span>';
      span.appendChild(leg);
      sub.appendChild(span);
    }

    function meldingen() {
      var m = $("#kb-lade-meldingen");
      m.textContent = "";
      if (opSlot) m.appendChild(el("div", "kb-lade-melding kb-lade-slot", "Ter inzage: je kunt nu niets meenemen. Een bericht sturen kan wel, en voorstellen die niet zijn meegenomen kun je afwijzen."));
      if (spoed) m.appendChild(el("div", "kb-lade-melding kb-lade-spoed", "Spoedcorrectie: wat je hier meeneemt, wordt afgehandeld als je deze correctie publiceert."));
      var o = aantalOnbewaard();
      if (o) m.appendChild(el("div", "kb-lade-melding kb-lade-onbewaard", o + (o === 1 ? " wijziging" : " wijzigingen") + " bij Meenemen nog niet opgeslagen. Sla op via Afronden; anders telt het niet en is het voorstel ook niet opgepakt."));
    }

    function teken() {
      velden();
      markeer();
      $("#kb-lip-teller").textContent = String(lijst.length);
      meldingen();
      infobalk();
      var doel = $("#kb-lade-lijst");
      doel.textContent = "";
      if (!lijst.length) { doel.appendChild(el("p", "kb-lade-uitleg", "Geen open voorstellen meer bij dit artikel.")); return; }
      lijst.forEach(function (v) { doel.appendChild(kaart(v)); });
    }

    function kaart(v) {
      var isOpen = v.id === actief;
      var k = el("div", "kb-vk" + (isOpen ? " kb-vk-open" : ""));
      var rij = el("div", "kb-vk-rij");
      rij.setAttribute("role", "button");
      rij.tabIndex = 0;
      rij.setAttribute("aria-expanded", isOpen ? "true" : "false");
      rij.appendChild(el("span", "kb-vk-nr", String(nr(v))));
      var blok = el("span", "kb-vk-titelblok");
      blok.appendChild(el("span", "kb-vk-titel", v.titel));
      var i = info[v.id] || {};
      var sub = [v.citaat ? (i.gevonden ? (i.sectie || "begin van het artikel") : "tekst niet meer gevonden") : "hele artikel",
        v.steun ? v.steun + " steun" : "", v.eigenaar ? "bij " + (v.van_mij ? "jou" : v.eigenaar) : ""].filter(Boolean).join(" · ");
      blok.appendChild(el("span", "kb-vk-sub", sub));
      rij.appendChild(blok);
      if (mee[v.id]) {
        var stip = el("span", "kb-vk-stip" + (mee[v.id] === bewaard[v.id] ? "" : " kb-vk-stip-onbewaard"));
        stip.title = mee[v.id] === bewaard[v.id] ? "Meegenomen" : "Meegenomen, nog niet opgeslagen";
        rij.appendChild(stip);
      }
      rij.appendChild(el("span", "kb-vk-pijl", isOpen ? "▾" : "▸"));
      function wissel() {
        actief = isOpen ? null : v.id;
        teken();
        if (actief && window.kbInhoudEditor && window.kbInhoudEditor.naarVoorstel) window.kbInhoudEditor.naarVoorstel(v.id);
      }
      rij.addEventListener("click", wissel);
      rij.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); wissel(); } });
      k.appendChild(rij);
      if (!isOpen) return k;

      var d = el("div", "kb-vk-detail");
      if (v.citaat) d.appendChild(el("div", "kb-vk-citaat", "“" + v.citaat + "”"));
      d.appendChild(el("div", "kb-vk-tekst", v.tekst));
      d.appendChild(el("div", "kb-vk-meta", [v.indiener || "Indiener onbekend", v.op, v.steun ? v.steun + (v.steun === 1 ? " collega steunt dit" : " collega's steunen dit") + (v.steuners && v.steuners.length ? ": " + v.steuners.join(", ") : "") : "nog geen steun"].join(" · ")));
      if (v.citaat && !i.gevonden) d.appendChild(el("div", "kb-vk-weg", "Deze tekst staat niet meer letterlijk in het artikel."));
      if (spoed && v.mee) d.appendChild(el("div", "kb-vk-let", "Dit voorstel is al meegenomen in de conceptversie."));
      if (v.verwerkt_in_versie) {
        var vw = el("div", "kb-vk-let", "Al verwerkt in versie " + v.verwerkt_in_versie + ", maar nog niet afgehandeld. ");
        var link = el("a", null, "Nu afhandelen");
        link.href = v.afhandelen_url;
        vw.appendChild(link);
        d.appendChild(vw);
      }

      // Meenemen
      var lab = el("label", "kb-vk-mee" + (opSlot ? " kb-vk-mee-uit" : ""));
      var vak = document.createElement("input");
      vak.type = "checkbox";
      vak.checked = !!mee[v.id];
      vak.disabled = opSlot;
      lab.appendChild(vak);
      var tekst = el("span");
      tekst.appendChild(el("b", null, spoed ? "Meenemen in deze spoedcorrectie" : "Meenemen in deze versie"));
      if (mee[v.id] !== bewaard[v.id]) tekst.appendChild(document.createTextNode(" · nog niet opgeslagen"));
      if (opSlot) tekst.appendChild(document.createTextNode(" · kan niet terwijl de versie ter inzage ligt"));
      lab.appendChild(tekst);
      vak.addEventListener("click", function (e) {
        e.preventDefault();
        var wil = !mee[v.id];
        function zet() { mee[v.id] = wil; v._overgenomen = wil; teken(); }
        if (wil && v.eigenaar && !v.van_mij && !v._overgenomen) {
          venster({
            titel: "Dit voorstel ligt bij " + v.eigenaar,
            alineas: [v.eigenaar + " heeft dit voorstel opgepakt. Neem je het mee, dan neem je het over. " + v.eigenaar + " krijgt daar een e-mail over zodra je opslaat."],
            knoppen: [{ tekst: "Niet overnemen" }, { tekst: "Overnemen en meenemen", primair: true, doen: zet }],
          });
          return;
        }
        zet();
      });
      d.appendChild(lab);
      if (v.eigenaar && !v.van_mij) d.appendChild(el("p", "kb-vk-uitleg", "Ligt bij " + v.eigenaar + ". Neem je het mee, dan neem je het over (je krijgt eerst een vraag)."));

      // Bericht of notitie: twee tabbladen, één tegelijk zichtbaar.
      var welk = tab[v.id] || "bericht";
      var voornaam = (v.indiener || "de indiener").split(" ")[0];
      var tabs = el("div", "kb-vk-tabs");
      tabs.setAttribute("role", "tablist");
      [["bericht", "✉ Bericht aan " + voornaam], ["notitie", "🔒 Interne notitie"]].forEach(function (t) {
        var b = el("button", "kb-vk-tab kb-vk-tab-" + t[0] + (welk === t[0] ? " kb-vk-tab-aan" : ""), t[1]);
        b.type = "button";
        b.setAttribute("role", "tab");
        b.setAttribute("aria-selected", welk === t[0] ? "true" : "false");
        b.addEventListener("click", function () { tab[v.id] = t[0]; teken(); });
        tabs.appendChild(b);
      });
      d.appendChild(tabs);
      if (welk === "bericht") {
        var vakB = el("div", "kb-vk-vak kb-vk-vak-bericht");
        vakB.appendChild(el("div", "kb-vk-vakkop", v.indiener ? "Gaat per e-mail naar " + v.indiener + " (de indiener)" : "Gaat naar de indiener"));
        v.berichten.forEach(function (b) { var x = el("div", "kb-vk-bericht", b.tekst); x.appendChild(el("small", null, b.naam + ", " + b.moment)); vakB.appendChild(x); });
        var taB = el("textarea");
        taB.placeholder = "Laat " + voornaam + " weten hoe het ervoor staat. Een reactie terug is niet mogelijk; voor overleg gebruik je Teams of mail.";
        taB.setAttribute("aria-label", "Bericht aan " + (v.indiener || "de indiener"));
        vakB.appendChild(taB);
        var stuur = el("button", "button default", "Versturen aan " + voornaam + "…");
        stuur.type = "button";
        stuur.addEventListener("click", function () {
          var t = taB.value.trim();
          if (!t) { taB.focus(); return; }
          var inhoud = el("div", "kb-vk-bericht kb-vk-voorbeeld", t);
          venster({
            titel: "Versturen aan " + (v.indiener || "de indiener") + "?",
            alineas: ["Dit bericht gaat per e-mail naar de indiener en staat daarna bij het voorstel:"],
            inhoud: inhoud,
            knoppen: [{ tekst: "Nog niet" }, { tekst: "Versturen", primair: true, doen: function () { actie(v, "bericht", t); } }],
          });
        });
        var r1 = el("div", "kb-vk-knoppen"); r1.appendChild(stuur); vakB.appendChild(r1);
        d.appendChild(vakB);
      } else {
        var vakN = el("div", "kb-vk-vak kb-vk-vak-notitie");
        vakN.appendChild(el("div", "kb-vk-vakkop", "Alleen redacteuren zien dit. Gaat nooit naar de indiener of de reviewer."));
        v.notities.forEach(function (n) { var x = el("div", "kb-vk-notitie", n.tekst); x.appendChild(el("small", null, n.naam + ", " + n.moment)); vakN.appendChild(x); });
        var taN = el("textarea");
        taN.placeholder = "Notitie voor collega-redacteuren";
        taN.setAttribute("aria-label", "Interne notitie");
        vakN.appendChild(taN);
        var bewaar = el("button", "button", "Notitie bewaren");
        bewaar.type = "button";
        bewaar.addEventListener("click", function () { var t = taN.value.trim(); if (t) actie(v, "notitie", t); else taN.focus(); });
        var r2 = el("div", "kb-vk-knoppen"); r2.appendChild(bewaar); vakN.appendChild(r2);
        d.appendChild(vakN);
      }

      // Afhandelen zonder wijziging
      var magAf = !(opSlot && bewaard[v.id]);
      var af = el("div", "kb-vk-af");
      af.appendChild(el("h3", null, "Afhandelen zonder wijziging"));
      var kn = el("div", "kb-vk-knoppen");
      var afw = el("button", "button kb-gevaar", "Afwijzen…"); afw.type = "button"; afw.disabled = !magAf;
      var dub = el("button", "button", "Dubbel…"); dub.type = "button"; dub.disabled = !magAf || !v.andere.length;
      afw.addEventListener("click", function () { afsluiten(v, "afwijzen"); });
      dub.addEventListener("click", function () { afsluiten(v, "dubbel"); });
      kn.appendChild(afw); kn.appendChild(dub);
      af.appendChild(kn);
      // Verbergen voor collega's (onder "Alle voorstellen"), bijvoorbeeld als er een naam in staat.
      var verberg = el("button", "kb-vk-verberg", v.verborgen ? "Weer tonen aan collega's" : "Verbergen voor collega's");
      verberg.type = "button";
      verberg.title = "Collega's zien het voorstel dan niet meer onder Alle voorstellen en kunnen het niet steunen. De indiener ziet het gewoon.";
      verberg.addEventListener("click", function () { actie(v, "verbergen", "", "", v.verborgen ? "0" : "1"); });
      af.appendChild(verberg);
      if (!magAf) af.appendChild(el("p", "kb-vk-uitleg", "Dit voorstel is meegenomen in de versie die ter inzage ligt. Afwijzen kan pas als de review terug is."));
      d.appendChild(af);
      k.appendChild(d);
      return k;
    }

    function afsluiten(v, soort) {
      var inhoud = el("div", "kb-vk-afsluiten");
      var keuze = null;
      if (soort === "dubbel") {
        keuze = document.createElement("select");
        keuze.setAttribute("aria-label", "Dubbel van");
        var leeg = el("option", null, "Dubbel van welk voorstel?"); leeg.value = ""; keuze.appendChild(leeg);
        v.andere.forEach(function (a) { var o = el("option", null, a.label); o.value = String(a.id); keuze.appendChild(o); });
        inhoud.appendChild(keuze);
      }
      var ta = el("textarea");
      ta.value = soort === "dubbel"
        ? "Dank je wel voor je voorstel. Dit punt is al eerder gemeld; we nemen het daar mee."
        : "Dank je wel voor je voorstel. We nemen het niet over, omdat ";
      ta.setAttribute("aria-label", "Bericht aan de indiener");
      inhoud.appendChild(ta);
      venster({
        titel: soort === "dubbel" ? "Dubbel voorstel" : "Voorstel afwijzen",
        alineas: ["Laat " + (v.indiener || "de indiener") + " weten waarom. Dit is het afsluitende bericht; het voorstel gaat daarna naar Afgehandeld."],
        inhoud: inhoud,
        knoppen: [
          { tekst: "Annuleren" },
          {
            tekst: soort === "dubbel" ? "Afsluiten en versturen" : "Afwijzen en versturen",
            primair: true,
            doen: function () {
              if (!ta.value.trim()) { ta.focus(); return false; }
              if (keuze && !keuze.value) { keuze.focus(); return false; }
              actie(v, soort, ta.value.trim(), keuze ? keuze.value : "");
            },
          },
        ],
      });
    }

    function actie(v, soort, tekst, dubbelVan, waarde) {
      var data = new FormData();
      data.append("actie", soort);
      data.append("tekst", tekst);
      if (dubbelVan) data.append("dubbel_van", dubbelVan);
      if (waarde) data.append("waarde", waarde);
      fetch(g.actie_url.replace("/0/", "/" + v.id + "/"), {
        method: "POST",
        body: data,
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrf ? csrf.value : "", "X-Requested-With": "fetch" },
      }).then(function (r) {
        return r.json().catch(function () { return { fout: "De server gaf een onverwacht antwoord (" + r.status + ")." }; });
      }).then(function (antw) {
        if (antw.fout) { melding(antw.fout, true); return; }
        if (antw.weg) {
          lijst = lijst.filter(function (x) { return x.id !== v.id; });
          delete mee[v.id]; delete bewaard[v.id];
          actief = null;
        } else if (antw.voorstel) {
          var i = lijst.indexOf(v);
          var nieuw = antw.voorstel;
          nieuw._overgenomen = v._overgenomen;
          lijst[i] = nieuw;
        }
        melding(antw.melding, false);
        teken();
      }).catch(function () { melding("Geen verbinding met de server. Er is niets verstuurd.", true); });
    }

    function melding(tekst, fout) {
      if (!tekst) return;
      var m = el("div", "kb-lade-toast" + (fout ? " kb-lade-toast-fout" : ""), tekst);
      m.setAttribute("role", fout ? "alert" : "status");
      document.body.appendChild(m);
      setTimeout(function () { m.remove(); }, fout ? 7000 : 4000);
    }

    // Klik op een nummer in de tekst: open dat voorstel in de lade.
    window.kbOpVoorstel = function (id) {
      if (!zoek(id)) return;
      actief = id;
      zetOpen(true);
      teken();
      var kaartEl = document.querySelector(".kb-vk-open");
      if (kaartEl) kaartEl.scrollIntoView({ block: "nearest" });
    };

    // Weggaan met meenemen dat nog niet is opgeslagen.
    window.addEventListener("beforeunload", function (e) {
      if (verzonden || !aantalOnbewaard()) return;
      e.preventDefault();
      e.returnValue = "";
    });

    // De editor wordt in dezelfde ronde gemaakt (beheer-editor.js); wacht er kort op voor de markering.
    var pogingen = 0;
    (function wacht() {
      if (markeer() || pogingen++ > 100) {
        teken();
        if (actief && window.kbInhoudEditor && window.kbInhoudEditor.naarVoorstel) {
          setTimeout(function () { window.kbInhoudEditor.naarVoorstel(actief); }, 120);
        }
        return;
      }
      setTimeout(wacht, 30);
    })();
    // Tekst verandert: nummers en "niet meer gevonden" bijwerken (de markering zelf volgt de editor).
    var tik = null;
    document.addEventListener("input", function (e) {
      if (!e.target || e.target.name !== "inhoud") return; // alleen de tekst van het artikel, niet de lade zelf
      clearTimeout(tik);
      tik = setTimeout(function () { if (!lade.contains(document.activeElement)) teken(); }, 400);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
