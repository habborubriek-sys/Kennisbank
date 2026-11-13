/* Verbetervoorstellen in het bewerkscherm: de lade links (1.26.0).
 *
 * De server zet de open voorstellen bij dit artikel als JSON in de pagina (kb-lade-gegevens). Dit script
 * tekent de lade (een tabblad dat uit de linkerrand steekt), markeert de citaten blauw in de tekst met een
 * rond nummer, en houdt twee verborgen velden bij die met het formulier meegaan: welke voorstellen in de
 * lade stonden (kb_lade) en welke zijn aangevinkt (kb_meenemen). Meenemen telt dus pas bij opslaan.
 *
 * Bericht aan de indiener, interne notitie, afwijzen, dubbel en afhandelen als verwerkt (1.31.2) gaan meteen
 * naar de server (los van het artikel). Bericht en notitie staan in twee tabbladen, nooit tegelijk in beeld; versturen vraagt een
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
    // Ronde A (M6): kwam het formulier terug met een fout, dan zet de server bij `mee_gewenst` wat je bij
    // Meenemen had veranderd. Dat staat dan weer zo, met "nog niet opgeslagen".
    lijst.forEach(function (v) {
      bewaard[v.id] = spoed ? false : !!v.mee;
      mee[v.id] = typeof v.mee_gewenst === "boolean" ? v.mee_gewenst : bewaard[v.id];
    });
    // Ronde A (H1): wat je in een bericht of notitie typt, per voorstel en per tabblad. De lade wordt vaak
    // opnieuw getekend; zonder dit was het vak daarna leeg.
    var concept = {};
    function conceptSleutel(v, soort) { return v.id + "-" + soort; }
    function nietVerstuurd() {
      return Object.keys(concept).filter(function (k) { return concept[k] && concept[k].trim(); }).length;
    }
    var csrf = form && form.querySelector("input[name=csrfmiddlewaretoken]");
    var verzonden = false;
    if (form) form.addEventListener("submit", function () { verzonden = true; });

    if (!lijst.length) return; // geen open voorstellen: geen lade, geen tabblad
    lade.hidden = false;
    lip.hidden = false;
    document.body.classList.add("kb-met-lade");
    var open = !!actief || sessionStorageLees() === "open";
    zetOpen(open);
    // Ronde B (M17): openen met het tabblad zet de focus in de lade; Escape in de lade sluit hem weer.
    lip.addEventListener("click", function () {
      var aan = !document.body.classList.contains("kb-lade-open");
      zetOpen(aan);
      if (aan) { var kop = $(".kb-lade-kop h2", lade); if (kop) { kop.tabIndex = -1; kop.focus(); } }
    });
    lade.addEventListener("keydown", function (e) {
      if (e.key !== "Escape" || document.querySelector("dialog[open]")) return;
      e.stopPropagation();
      zetOpen(false);
      lip.focus();
    });
    var sluitKnop = $(".kb-lade-sluit", lade);
    if (sluitKnop) sluitKnop.addEventListener("click", function () { zetOpen(false); lip.focus(); });

    function sessionStorageLees() { try { return sessionStorage.getItem("kb-lade"); } catch (e) { return null; } }
    function zetOpen(aan) {
      document.body.classList.toggle("kb-lade-open", aan);
      // Een dichte lade is ook voor Tab en de schermlezer dicht (review 1.27.0, M17).
      lade.inert = !aan;
      if (!aan) lade.setAttribute("aria-hidden", "true"); else lade.removeAttribute("aria-hidden");
      lip.setAttribute("aria-expanded", aan ? "true" : "false");
      $(".kb-lip-pijl", lip).textContent = aan ? "◀" : "▶";
      try { sessionStorage.setItem("kb-lade", aan ? "open" : "dicht"); } catch (e) { /* geen opslag: niet erg */ }
      if (window.kbInhoudEditor && window.kbInhoudEditor.tekenMarge) setTimeout(window.kbInhoudEditor.tekenMarge, 260);
      // 1.31.0: de werkbalk schuift mee en kan dan een regel hoger worden; de hoogtes opnieuw laten meten.
      setTimeout(function () { window.dispatchEvent(new Event("resize")); }, 260);
    }

    function nr(v) { return lijst.indexOf(v) + 1; }
    function zoek(id) { return lijst.filter(function (v) { return v.id === id; })[0]; }
    function aantalOnbewaard() { return lijst.filter(function (v) { return mee[v.id] !== bewaard[v.id]; }).length; }

    function velden() {
      $("#kb-lade-ids").value = lijst.map(function (v) { return v.id; }).join(",");
      $("#kb-meenemen").value = lijst.filter(function (v) { return mee[v.id]; }).map(function (v) { return v.id; }).join(",");
      // Ronde A (M2): de stand bij het laden. De server verwerkt alleen wat jij hebt veranderd.
      var geladen = $("#kb-mee-geladen");
      if (geladen) geladen.value = lijst.filter(function (v) { return bewaard[v.id]; }).map(function (v) { return v.id; }).join(",");
    }

    // Ronde A (M7/M13): meegenomen, maar nog niet behandeld? Twee signalen, ook voor het venster Afronden.
    function naAkkoord() {
      if (!g.akkoord || spoed) return [];
      return lijst.filter(function (v) { return mee[v.id] && g.akkoord.indexOf(v.id) < 0; });
    }
    function ongewijzigd() {
      return lijst.filter(function (v) { return mee[v.id] && v.citaat && (info[v.id] || {}).gevonden; });
    }
    window.kbVoorstelWaarschuwingen = function () {
      var r = [];
      var na = naAkkoord(), ong = ongewijzigd();
      if (na.length) r.push("Na het akkoord meegenomen: " + na.map(function (v) { return nr(v) + ". " + v.titel; }).join("; ") + ". De reviewer heeft " + (na.length === 1 ? "dit voorstel" : "deze voorstellen") + " niet gezien. Heb je het echt verwerkt?");
      if (nietVerstuurd()) r.push("In de lade staat een bericht of notitie die je nog niet hebt verstuurd. Opslaan stuurt die niet mee; verstuur hem eerst in de lade.");
      if (ong.length) r.push("Meegenomen, maar de tekst staat nog ongewijzigd in het artikel: " + ong.map(function (v) { return nr(v) + ". " + v.titel; }).join("; ") + ". Al aangepast?");
      return r;
    };

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

    var vorigeOnbewaard = 0;
    function meldingen() {
      var m = $("#kb-lade-meldingen");
      m.textContent = "";
      var nuOnbewaard = aantalOnbewaard();
      if (nuOnbewaard !== vorigeOnbewaard) {
        if (nuOnbewaard) zeg(nuOnbewaard + (nuOnbewaard === 1 ? " wijziging bij Meenemen is" : " wijzigingen bij Meenemen zijn") + " nog niet opgeslagen.");
        vorigeOnbewaard = nuOnbewaard;
      }
      if (opSlot) m.appendChild(el("div", "kb-lade-melding kb-lade-slot", "Deze versie ligt ter inzage. Meenemen kan nu niet. Een bericht sturen kan wel, en voorstellen die niet zijn meegenomen, kun je afwijzen."));
      if (spoed) m.appendChild(el("div", "kb-lade-melding kb-lade-spoed", "Spoedcorrectie: wat je hier meeneemt, geldt als verwerkt zodra je deze correctie publiceert."));
      var na = naAkkoord();
      if (na.length) m.appendChild(el("div", "kb-lade-melding kb-lade-onbewaard", "Na het akkoord meegenomen: " + na.map(function (v) { return "voorstel " + nr(v); }).join(", ") + ". De reviewer heeft dat niet gezien. Controleer of het echt is verwerkt."));
      var o = aantalOnbewaard();
      if (o) m.appendChild(el("div", "kb-lade-melding kb-lade-onbewaard", o + (o === 1 ? " wijziging bij Meenemen is" : " wijzigingen bij Meenemen zijn") + " nog niet opgeslagen. Kies Afronden om op te slaan. Pas dan " + (o === 1 ? "wordt het voorstel" : "worden de voorstellen") + " meegenomen en aan jou toegewezen."));
    }

    // Ronde B (M17): de lade wordt na elke handeling opnieuw getekend. Onthoud waar de focus stond en zet hem
    // daarna terug; is dat element weg (bijvoorbeeld na afwijzen), dan op de kop van de lade.
    var naTeken = null;
    function teken() {
      var a = document.activeElement;
      var sleutel = naTeken || (a && lade.contains(a) ? a.getAttribute("data-kb-focus") : null);
      var hadFocus = !!naTeken || (a && lade.contains(a));
      naTeken = null;
      tekenNu();
      if (!hadFocus) return;
      var doel = sleutel && lade.querySelector('[data-kb-focus="' + sleutel + '"]');
      if (!doel) { doel = $(".kb-lade-kop h2", lade); if (doel) doel.tabIndex = -1; }
      if (doel) doel.focus();
    }
    function tekenNu() {
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
      rij.setAttribute("data-kb-focus", "rij-" + v.id);
      rij.setAttribute("aria-expanded", isOpen ? "true" : "false");
      rij.appendChild(el("span", "kb-vk-nr", String(nr(v))));
      var blok = el("span", "kb-vk-titelblok");
      blok.appendChild(el("span", "kb-vk-titel", v.titel));
      var i = info[v.id] || {};
      // 1.29.1: alleen waar het speelt; of de tekst al is aangepast, staat in het uitgeklapte voorstel.
      var plek = !v.citaat ? "hele artikel" : i.gevonden ? (i.sectie || "begin van het artikel") : mee[v.id] ? "" : "tekst niet meer gevonden";
      var sub = [plek,
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
      d.appendChild(el("div", "kb-vk-meta", [v.indiener || "Indiener onbekend", v.op, v.steun ? v.steun + (v.steun === 1 ? " collega steunt dit" : " collega's steunen dit") : "nog geen steun"].join(" · ")));
      // 1.29.1 (wens Alex): de eerste vijf namen als korte lijst, de rest uitklapbaar.
      if (v.steuners && v.steuners.length) {
        var steunLijst = el("ul", "kb-vk-steuners");
        v.steuners.slice(0, 5).forEach(function (n) { steunLijst.appendChild(el("li", null, n)); });
        d.appendChild(steunLijst);
        if (v.steuners.length > 5) {
          var meer = el("details", "kb-vk-steun-meer");
          var sm = el("summary", null, "En nog " + (v.steuners.length - 5) + " meer");
          sm.setAttribute("data-kb-focus", "steun-" + v.id);
          meer.appendChild(sm);
          var rest = el("ul", "kb-vk-steuners");
          v.steuners.slice(5).forEach(function (n) { rest.appendChild(el("li", null, n)); });
          meer.appendChild(rest);
          d.appendChild(meer);
        }
      }
      // Ronde B (M19): naar het citaat in de tekst, ook met het toetsenbord.
      if (v.citaat && i.gevonden && window.kbInhoudEditor && window.kbInhoudEditor.naarVoorstel) {
        var toon = el("button", "kb-vk-toon", "Toon in de tekst");
        toon.type = "button";
        toon.setAttribute("data-kb-focus", "toon-" + v.id);
        toon.addEventListener("click", function () { window.kbInhoudEditor.naarVoorstel(v.id, true); });
        d.appendChild(toon);
      }
      // Ronde A (M13): meegenomen en de tekst is aangepast = goed; meegenomen en de tekst staat er nog = vraag.
      if (v.citaat && mee[v.id] && !i.gevonden) d.appendChild(el("div", "kb-vk-ok", "Aangepast ✓ De tekst van het voorstel staat niet meer letterlijk in het artikel."));
      else if (v.citaat && mee[v.id] && i.gevonden) d.appendChild(el("div", "kb-vk-let", "Meegenomen, maar de tekst staat nog ongewijzigd in het artikel. Al aangepast?"));
      else if (v.citaat && !i.gevonden) d.appendChild(el("div", "kb-vk-weg", "Deze tekst staat niet meer letterlijk in het artikel."));
      var spoedSlot = spoed && v.mee && g.op_slot;
      if (spoed && v.mee) d.appendChild(el("div", "kb-vk-let", spoedSlot ? "Dit voorstel is meegenomen in de conceptversie die ter inzage ligt. Je kunt het niet in deze spoedcorrectie meenemen; het hoort bij de review." : "Dit voorstel is al meegenomen in de conceptversie. Neem je het hier mee, dan geldt het als verwerkt in deze correctie."));
      if (v.verwerkt_in_versie) {
        var vw = el("div", "kb-vk-let", "Al verwerkt in versie " + v.verwerkt_in_versie + ", maar nog niet afgehandeld. ");
        var link = el("a", null, "Nu afhandelen");
        link.href = v.afhandelen_url;
        vw.appendChild(link);
        d.appendChild(vw);
      }

      // Meenemen
      var lab = el("label", "kb-vk-mee" + (opSlot || spoedSlot ? " kb-vk-mee-uit" : ""));
      var vak = document.createElement("input");
      vak.type = "checkbox";
      vak.checked = !!mee[v.id];
      vak.disabled = opSlot || spoedSlot;
      vak.setAttribute("data-kb-focus", "mee-" + v.id);
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
      if (v.eigenaar && !v.van_mij) d.appendChild(el("p", "kb-vk-uitleg", "Ligt bij " + v.eigenaar + ". Neem je het mee, dan wordt het aan jou toegewezen; je krijgt eerst een vraag."));

      // Bericht of notitie: twee tabbladen, één tegelijk zichtbaar.
      var welk = tab[v.id] || "bericht";
      var voornaam = (v.indiener || "de indiener").split(" ")[0];
      // Ronde B (L1): twee knoppen met aria-pressed in plaats van een half tabbladpatroon.
      var tabs = el("div", "kb-vk-tabs");
      tabs.setAttribute("role", "group");
      tabs.setAttribute("aria-label", "Bericht of interne notitie");
      [["bericht", "✉ Bericht"], ["notitie", "🔒 Notitie"]].forEach(function (t) {
        var b = el("button", "kb-vk-tab kb-vk-tab-" + t[0] + (welk === t[0] ? " kb-vk-tab-aan" : ""), t[1]);
        b.type = "button";
        b.setAttribute("aria-pressed", welk === t[0] ? "true" : "false");
        b.setAttribute("data-kb-focus", "tab-" + v.id + "-" + t[0]);
        b.addEventListener("click", function () { tab[v.id] = t[0]; teken(); });
        tabs.appendChild(b);
      });
      d.appendChild(tabs);
      if (welk === "bericht") {
        var vakB = el("div", "kb-vk-vak kb-vk-vak-bericht");
        vakB.appendChild(el("div", "kb-vk-vakkop", v.indiener ? "Gaat per e-mail naar " + v.indiener + " (de indiener)" : "Gaat naar de indiener"));
        v.berichten.forEach(function (b) { var x = el("div", "kb-vk-bericht", b.tekst); x.appendChild(el("small", null, b.naam + ", " + b.moment)); vakB.appendChild(x); });
        var taB = el("textarea");
        var sB = conceptSleutel(v, "bericht");
        taB.value = concept[sB] || "";
        taB.setAttribute("data-kb-focus", "ta-" + v.id + "-bericht");
        taB.addEventListener("input", function () { concept[sB] = taB.value; });
        taB.setAttribute("aria-label", "Bericht aan " + (v.indiener || "de indiener"));
        vakB.appendChild(taB);
        var stuur = el("button", "button default", "Versturen aan " + voornaam + "…");
        stuur.type = "button";
        stuur.setAttribute("data-kb-focus", "stuur-" + v.id);
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
        var sN = conceptSleutel(v, "notitie");
        taN.value = concept[sN] || "";
        taN.setAttribute("data-kb-focus", "ta-" + v.id + "-notitie");
        taN.addEventListener("input", function () { concept[sN] = taN.value; });
        taN.setAttribute("aria-label", "Interne notitie");
        vakN.appendChild(taN);
        var bewaar = el("button", "button", "Notitie bewaren");
        bewaar.type = "button";
        bewaar.setAttribute("data-kb-focus", "bewaar-" + v.id);
        bewaar.addEventListener("click", function () { var t = taN.value.trim(); if (t) actie(v, "notitie", t); else taN.focus(); });
        var r2 = el("div", "kb-vk-knoppen"); r2.appendChild(bewaar); vakN.appendChild(r2);
        d.appendChild(vakN);
      }

      // Afhandelen zonder nieuwe versie (1.31.2, K2: ook als verwerkt, als de tekst al eerder is aangepast).
      var magAf = !(opSlot && bewaard[v.id]);
      var af = el("div", "kb-vk-af");
      af.appendChild(el("h3", null, "Afhandelen zonder nieuwe versie"));
      var kn = el("div", "kb-vk-knoppen");
      var vwk = el("button", "button", "Afhandelen als verwerkt…"); vwk.type = "button"; vwk.disabled = !magAf || !v.verwerkt_versie;
      vwk.setAttribute("data-kb-focus", "vwk-" + v.id);
      vwk.title = "Voor een voorstel waarvan de tekst al is aangepast in de versie die medewerkers nu zien.";
      vwk.addEventListener("click", function () { verwerkt(v); });
      kn.appendChild(vwk);
      var afw = el("button", "button kb-gevaar", "Afwijzen…"); afw.type = "button"; afw.disabled = !magAf;
      var dub = el("button", "button", "Dubbel…"); dub.type = "button"; dub.disabled = !magAf || !v.andere.length;
      afw.setAttribute("data-kb-focus", "afw-" + v.id);
      dub.setAttribute("data-kb-focus", "dub-" + v.id);
      afw.addEventListener("click", function () { afsluiten(v, "afwijzen"); });
      dub.addEventListener("click", function () { afsluiten(v, "dubbel"); });
      kn.appendChild(afw); kn.appendChild(dub);
      af.appendChild(kn);
      // Verbergen voor collega's (onder "Alle voorstellen"), bijvoorbeeld als er een naam in staat.
      var verberg = el("button", "kb-vk-verberg", v.verborgen ? "Weer tonen aan collega's" : "Verbergen voor collega's");
      verberg.type = "button";
      verberg.setAttribute("data-kb-focus", "verberg-" + v.id);
      verberg.title = "Collega's zien het voorstel dan niet meer onder Alle voorstellen en kunnen het niet steunen. De indiener ziet het gewoon.";
      verberg.addEventListener("click", function () { actie(v, "verbergen", "", "", v.verborgen ? "0" : "1"); });
      af.appendChild(verberg);
      if (!magAf) af.appendChild(el("p", "kb-vk-uitleg", "Dit voorstel is meegenomen in de versie die ter inzage ligt. Afhandelen kan pas als de review terug is."));
      else if (!v.verwerkt_versie) af.appendChild(el("p", "kb-vk-uitleg", "Afhandelen als verwerkt kan pas als het artikel is gepubliceerd."));
      d.appendChild(af);
      k.appendChild(d);
      return k;
    }

    // 1.31.2 (K2): de tekst is al aangepast in een gepubliceerde versie. Staat het citaat er nog letterlijk in,
    // dan eerst de vraag of je het zeker weet; daarna het venster met het voorgevulde bedankbericht.
    function verwerkt(v) {
      if (!v.citaat_gepubliceerd) { verwerktBericht(v, false); return; }
      var inhoud = el("div", "kb-vk-afsluiten");
      inhoud.appendChild(el("div", "kb-vk-citaat", "“" + v.citaat + "”"));
      inhoud.appendChild(el("p", null, "Weet je zeker dat het voorstel is verwerkt?"));
      venster({
        titel: "De tekst staat nog in het artikel",
        alineas: ["De tekst waar dit voorstel over gaat, staat nog letterlijk in versie " + v.verwerkt_versie + ", die medewerkers nu zien:"],
        inhoud: inhoud,
        knoppen: [
          { tekst: "Annuleren", focus: true },
          // Het volgende venster pas openen als dit dicht is, anders gaat de focus terug naar de lade.
          { tekst: "Ja, het is verwerkt", primair: true, doen: function () { setTimeout(function () { verwerktBericht(v, true); }, 0); } },
        ],
      });
    }
    function verwerktBericht(v, zeker) {
      var inhoud = el("div", "kb-vk-afsluiten");
      var ta = el("textarea");
      ta.value = v.verwerkt_bericht || "";
      ta.setAttribute("aria-label", "Bericht aan de indiener");
      inhoud.appendChild(ta);
      venster({
        titel: "Afhandelen als verwerkt",
        alineas: ["Het voorstel is verwerkt in versie " + v.verwerkt_versie + ", die medewerkers nu zien. " + (v.indiener || "De indiener") + " krijgt dit bericht; het voorstel gaat daarna naar Afgehandeld."],
        inhoud: inhoud,
        knoppen: [
          { tekst: "Annuleren" },
          {
            tekst: "Afhandelen en versturen",
            primair: true,
            doen: function () {
              if (!ta.value.trim()) { ta.focus(); return false; }
              actie(v, "verwerkt", ta.value.trim(), "", "", zeker);
            },
          },
        ],
      });
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

    function actie(v, soort, tekst, dubbelVan, waarde, zeker) {
      // Na het antwoord tekent de lade opnieuw: zet de focus dan terug op de knop van deze handeling.
      var focusNa = { bericht: "stuur-", notitie: "bewaar-", verbergen: "verberg-", afwijzen: "rij-", dubbel: "rij-", verwerkt: "vwk-" }[soort] + v.id;
      var data = new FormData();
      data.append("actie", soort);
      data.append("tekst", tekst);
      if (dubbelVan) data.append("dubbel_van", dubbelVan);
      if (waarde) data.append("waarde", waarde);
      if (zeker) data.append("zeker", "1");
      // Ronde A (M5): hoe het voorstel erbij lag. Is dat intussen veranderd, dan weigert de server.
      data.append("geladen_eigenaar", String(v.geladen_eigenaar || 0));
      data.append("geladen_bericht", String(v.geladen_bericht || 0));
      fetch(g.actie_url.replace("/0/", "/" + v.id + "/"), {
        method: "POST",
        body: data,
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrf ? csrf.value : "", "X-Requested-With": "fetch" },
      }).then(function (r) {
        return r.json().catch(function () { return { fout: "De server gaf een onverwacht antwoord (" + r.status + ")." }; });
      }).then(function (antw) {
        naTeken = focusNa;
        if (antw.fout) {
          if (antw.voorstel) {
            // Intussen veranderd: toon de nieuwe stand. Je getypte tekst blijft staan (concept).
            var j = lijst.indexOf(v);
            if (j >= 0) { antw.voorstel._overgenomen = v._overgenomen; lijst[j] = antw.voorstel; }
            teken();
          }
          melding(antw.fout, true);
          return;
        }
        if (soort === "bericht" || soort === "notitie") delete concept[conceptSleutel(v, soort)];
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

    // Eén vaste live-regio (ronde B, M23): de schermlezer leest meldingen voor die erin komen.
    function zeg(tekst) {
      var live = document.getElementById("kb-lade-live");
      if (!live || !tekst) return;
      live.textContent = "";
      setTimeout(function () { live.textContent = tekst; }, 60);
    }

    function melding(tekst, fout) {
      if (!tekst) return;
      var m = el("div", "kb-lade-toast" + (fout ? " kb-lade-toast-fout" : ""), tekst);
      m.setAttribute("aria-hidden", "true"); // voorgelezen via de vaste live-regio
      document.body.appendChild(m);
      zeg(tekst);
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
      var rijEl = kaartEl && kaartEl.querySelector(".kb-vk-rij");
      if (rijEl) rijEl.focus();
    };

    // Weggaan met meenemen dat nog niet is opgeslagen.
    window.addEventListener("beforeunload", function (e) {
      if (verzonden || (!aantalOnbewaard() && !nietVerstuurd())) return;
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
