/* Kennisbank – frontend.
 * Afgeleid van het klikbare prototype. Geen build-stap, geen externe bibliotheken:
 * dit bestand wordt zo geserveerd. Alle gegevens komen uit /api/v1/.
 */
(function () {
  "use strict";

  /* ---------- Hulpfuncties ---------- */
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const body = document.body;
  const EMBED = body.dataset.embed === "1";
  const DEMO = body.dataset.demo === "1";
  const ZAAKTYPE = body.dataset.zaaktype || "";

  function cookie(naam) {
    const m = document.cookie.match(new RegExp("(?:^|; )" + naam + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : "";
  }

  class ApiFout extends Error {
    constructor(status, detail) { super(detail || "Fout " + status); this.status = status; }
  }

  async function api(pad, opties) {
    opties = opties || {};
    const headers = { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" };
    if (opties.body !== undefined) headers["Content-Type"] = "application/json";
    if (opties.method && opties.method !== "GET") headers["X-CSRFToken"] = cookie("csrftoken");
    const resp = await fetch("/api/v1/" + pad, {
      method: opties.method || "GET",
      headers,
      credentials: "same-origin",
      body: opties.body !== undefined ? JSON.stringify(opties.body) : undefined,
    });
    if (resp.status === 204) return null;
    let data = null;
    try { data = await resp.json(); } catch (e) { /* geen JSON */ }
    if (resp.status === 403 && data && data.refresh_url && !EMBED) {
      // De identity provider moet de rechten opnieuw bevestigen (OIDC SessionRefresh). Een gewone
      // paginaweergave regelt dat stilletjes; daarna komt de gebruiker op dezelfde plek terug.
      // Hooguit één keer per minuut, zodat een haperende identity provider geen herlaad-lus geeft.
      let laatste = 0;
      try { laatste = Number(sessionStorage.getItem("kb.ververs") || 0); sessionStorage.setItem("kb.ververs", String(Date.now())); } catch (e) { /* geen opslag */ }
      if (Date.now() - laatste > 60000) { location.reload(); await new Promise(() => {}); }
    }
    if (!resp.ok) throw new ApiFout(resp.status, data && (data.detail || JSON.stringify(data)));
    return data;
  }

  let toastT;
  function toast(m) {
    const t = $("#toast");
    t.textContent = m;
    t.classList.add("show");
    clearTimeout(toastT);
    toastT = setTimeout(() => t.classList.remove("show"), 2600);
  }

  function ago(iso) {
    const m = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
    if (m < 1) return "zojuist";
    if (m < 60) return m + " min geleden";
    const h = Math.round(m / 60);
    if (h < 24) return h + " uur geleden";
    const d = Math.round(h / 24);
    return d === 1 ? "gisteren" : d + " dagen geleden";
  }
  const datum = (iso) => (iso ? new Date(iso).toLocaleDateString("nl-NL", { day: "numeric", month: "short", year: "numeric" }) : "–");

  /* ---------- Toestand ---------- */
  let ik = null;
  let lijsten = { clusters: [], soorten: [], tags: [], zaaktypen: [] };
  let artikelen = [];           // alle zichtbare artikelen (kort)
  let favs = new Set();
  let voorstellen = [];
  let berichten = null;         // nieuwsberichten, geladen bij de eerste keer dat ze nodig zijn
  let nieuwsGezienOp = null;    // berichten met een latere publicatiedatum zijn "nieuw" voor deze gebruiker
  let nieuwsGezienStraks = null; // nieuwe grens, gaat in zodra de gebruiker de nieuwspagina verlaat (labels blijven zolang staan)
  let onboarding = false;
  const state = { view: "recent", artikel: null, q: "", cluster: null, soort: null, tags: new Set(), zoekresultaat: null };
  let huidigArtikel = null;     // volledig artikel dat nu open is
  let zoekT, registreerT, zoekVolgnr = 0;

  const isPM = () => !!(ik && ik.is_redacteur);
  const artById = (id) => artikelen.find((a) => a.id === Number(id));
  const clusterLabel = (a) => (a.clusters.length ? a.clusters.join(", ") : "Alle clusters");
  const soortLabel = (w) => { const s = lijsten.soorten.find((x) => x.waarde === w); return s ? s.label : w; };
  const VOORSTEL_LABEL = { nieuw: "Nieuw", in_behandeling: "In behandeling", verwerkt: "Verwerkt", afgewezen: "Afgewezen" };

  /* ---------- Navigatie (echte URL's, zodat links te delen zijn) ---------- */
  const VIEWS = ["recent", "artikelen", "favorieten", "gewijzigd", "nieuws", "voorstellen", "statistieken"];
  const gewijzigd = () => artikelen.filter((a) => a.wijziging);
  const nieuwsOngelezen = () => (berichten || []).filter((b) => isNieuw(b)).length;
  const isNieuw = (b) => !nieuwsGezienOp || new Date(b.gepubliceerd_op) > new Date(nieuwsGezienOp);

  function leesUrl() {
    if (EMBED) return;
    const pad = location.pathname.replace(/\/+$/, "");
    const m = pad.match(/^\/artikel\/(\d+)(?:\/[\w-]*)?$/);
    state.artikel = m ? Number(m[1]) : null;
    const v = pad.replace(/^\//, "");
    if (!m) state.view = VIEWS.includes(v) ? v : (ik && ik.recent.length ? "recent" : "artikelen");
  }

  function zetUrl(vervang) {
    if (EMBED) return;
    const a = state.artikel ? (huidigArtikel && huidigArtikel.id === state.artikel ? huidigArtikel : artById(state.artikel)) : null;
    const pad = state.artikel ? (a ? a.url : "/artikel/" + state.artikel) : "/" + (state.view === "recent" ? "" : state.view);
    if (location.pathname !== pad) {
      try { history[vervang ? "replaceState" : "pushState"](null, "", pad); } catch (e) { /* bijv. sandbox */ }
    }
  }

  function ga(view) {
    state.view = view;
    state.q = ""; state.zoekresultaat = null; $("#q").value = "";
    state.artikel = null;
    huidigArtikel = null;
    $("#side").classList.remove("open");
    $("#sideToggle").setAttribute("aria-expanded", "false");
    zetUrl();
    render(true);
  }

  window.addEventListener("popstate", () => { leesUrl(); render(true); });

  /* ---------- Filters ---------- */
  function renderFilters() {
    $("#fCluster").innerHTML = lijsten.clusters.map((c) => `<button class="chip" type="button" data-f="cluster" data-v="${esc(c)}" aria-pressed="${state.cluster === c}">${esc(c)}</button>`).join("");
    $("#fType").innerHTML = lijsten.soorten.map((s) => `<button class="chip" type="button" data-f="soort" data-v="${esc(s.waarde)}" aria-pressed="${state.soort === s.waarde}">${esc(s.label)}</button>`).join("");
    $("#cAll").textContent = artikelen.length;
    $("#cFav").textContent = favs.size;
    $("#cRec").textContent = ik ? ik.recent.length : "";
    $("#cProp").textContent = voorstellen.filter((p) => p.status === "nieuw" || p.status === "in_behandeling").length || "";
    $("#cWijz").textContent = gewijzigd().length || "";
    $("#cNieuws").textContent = (berichten ? (nieuwsGezienStraks ? 0 : nieuwsOngelezen()) : (ik && ik.nieuws_ongelezen)) || "";
    $("#navNieuws").hidden = EMBED;  // in het zaaksysteem alleen de artikelen; nieuws hoort in de kennisbank zelf
    $("#navStats").hidden = !isPM();
    $$(".nav button").forEach((b) => b.setAttribute("aria-current", b.dataset.view === state.view && !state.artikel ? "page" : "false"));
  }

  function filtered(list) {
    return list.filter((a) =>
      (!state.cluster || !a.clusters.length || a.clusters.includes(state.cluster)) &&
      (!state.soort || a.soort === state.soort) &&
      [...state.tags].every((t) => a.tags.includes(t)));
  }

  /* ---------- Weergaven ---------- */
  async function render(focus) {
    if (state.view !== "nieuws" && nieuwsGezienStraks) { nieuwsGezienOp = nieuwsGezienStraks; nieuwsGezienStraks = null; }
    renderFilters();
    const m = $("#main");
    try {
      if (!ik) { m.innerHTML = renderLogin(); wireLogin(); return; }
      if (state.artikel) {
        if (!huidigArtikel || huidigArtikel.id !== state.artikel) {
          m.innerHTML = '<p class="loading">Laden…</p>';
          huidigArtikel = await api("artikelen/" + encodeURIComponent(state.artikel));
          registreerWeergave(huidigArtikel.id);
          zetUrl(true);  // slug in de adresbalk aanvullen
        }
        m.innerHTML = renderArticle(huidigArtikel);
        wireArticle();
      } else if (state.view === "zaaktype") {
        m.innerHTML = renderZaaktype(); wireList();
      } else if (state.view === "nieuws" && !EMBED) {
        if (!berichten) { m.innerHTML = '<p class="loading">Laden…</p>'; await laadBerichten(); }
        m.innerHTML = renderNieuws(); wireList(); wireNieuws();
        markeerNieuwsGezien();
      } else if (state.view === "voorstellen") {
        m.innerHTML = renderProps(); wireList();
      } else if (state.view === "statistieken") {
        m.innerHTML = '<p class="loading">Laden…</p>';
        const s = await api("statistieken?dagen=30");
        m.innerHTML = renderStats(s); wireList(); zetBalken();
      } else {
        m.innerHTML = renderLijstView(); wireList();
      }
    } catch (e) {
      if (e.status === 404) m.innerHTML = '<div class="view"><h1>Niet gevonden</h1><p class="lead">Dit artikel bestaat niet (meer), of je hebt er geen toegang toe.</p><button class="tb" type="button" data-nav="artikelen">Naar alle artikelen</button></div>';
      else if (e.status === 403 || e.status === 401) { ik = null; m.innerHTML = renderLogin(); wireLogin(); return; }
      else m.innerHTML = '<div class="view"><div class="fout">Er ging iets mis bij het laden. Probeer het opnieuw of neem contact op met de beheerder.</div></div>';
      wireList();
    }
    if (focus) { m.scrollTop = 0; window.scrollTo(0, 0); m.focus({ preventScroll: true }); }
  }

  function renderLijstView() {
    const zoekend = !!state.q.trim();
    let bron, titel, leeg = "", when = null;
    if (zoekend) { bron = state.zoekresultaat || []; titel = "Zoekresultaten"; }
    else if (state.view === "favorieten") {
      bron = artikelen.filter((a) => favs.has(a.id)); titel = "Favorieten";
      leeg = '<div class="empty">Nog geen favorieten. Open een artikel en klik op de ster om het hier vast te zetten.</div>';
    } else if (state.view === "gewijzigd") {
      bron = gewijzigd(); titel = "Gewijzigd";
      leeg = '<div class="empty">Geen openstaande wijzigingen. Zodra een artikel inhoudelijk wordt bijgewerkt, zie je hier wat er is veranderd.</div>';
    } else if (state.view === "recent") {
      bron = ik.recent.map((r) => artById(r.id)).filter(Boolean); titel = "Recent bezocht";
      when = Object.fromEntries(ik.recent.map((r) => [r.id, ago(r.bezocht_op)]));
      leeg = '<div class="empty">Hier verschijnen de artikelen die je het laatst hebt geopend.<br><br>Zoek hierboven op een trefwoord, of <button class="tb" type="button" data-nav="artikelen">bekijk alle artikelen</button></div>';
    } else { bron = artikelen; titel = "Alle artikelen"; }
    let html = renderList(filtered(bron), titel, when, leeg, zoekend && state.zoekresultaat === null);
    if (state.view === "gewijzigd" && !zoekend && bron.length) {
      html = html.replace("</h1>", '</h1><p class="lead">Artikelen die inhoudelijk zijn gewijzigd sinds je ze voor het laatst hebt afgevinkt. Open een artikel en klik op <b>Ik snap het</b>, of <button class="link" type="button" id="allesGezien">markeer alles als gezien</button>.</p>');
    }
    const startpagina = (state.view === "recent" || state.view === "artikelen") && !zoekend && !state.cluster && !state.soort && !state.tags.size;
    if (startpagina && !EMBED) html = html.replace('<div class="view">', '<div class="view">' + nieuwsBlok());
    return html;
  }

  /* Startpagina: de laatste nieuwsberichten in het kort. */
  function nieuwsBlok() {
    const lijst = (berichten || []).filter((b) => !b.verlopen).slice(0, 3);
    if (!lijst.length) return "";
    return `<section class="nieuwsblok" aria-labelledby="nbTitel"><div class="nb-head"><h2 id="nbTitel">Nieuws</h2><button class="link" type="button" data-nav="nieuws">Alle berichten</button></div>
      ${lijst.map((b) => `<article class="nb-item"><h3><button class="link" type="button" data-bericht="${b.id}">${esc(b.titel)}</button>${isNieuw(b) ? ' <span class="status nieuw">Nieuw</span>' : ""}</h3><p class="nb-meta">${datum(b.gepubliceerd_op)}</p></article>`).join("")}</section>`;
  }

  function cardHTML(a, when) {
    const meta = [];
    if (isPM()) {
      meta.push(`<span class="type ${esc(a.soort)}">${esc(soortLabel(a.soort))}</span>`, `<span>${esc(clusterLabel(a))}</span>`, "<span>·</span>", `<span>v${a.versie}, ${datum(a.gepubliceerd_op)}</span>`);
      if (a.status !== "gepubliceerd") meta.push(`<span class="status nieuw">${esc(a.status)}</span>`);
    }
    if (when) meta.push((isPM() ? "<span>·</span>" : "") + `<span class="when">${esc(when)}</span>`);
    if (a.wijziging) meta.unshift(`<span class="status wijzig" title="${esc(a.wijziging.toelichting)}">Gewijzigd ${esc(datum(a.wijziging.datum))}</span>`);
    return `<article class="card">
      <button class="star" type="button" data-fav="${a.id}" aria-pressed="${favs.has(a.id)}" aria-label="${favs.has(a.id) ? "Verwijder uit favorieten" : "Voeg toe aan favorieten"}: ${esc(a.titel)}">${favs.has(a.id) ? "★" : "☆"}</button>
      <h2><a href="${esc(a.url)}" data-open="${a.id}" class="linkbtn card-link">${esc(a.titel)}</a></h2>
      <p>${esc(a.samenvatting)}</p>
      ${meta.length ? `<div class="meta">${meta.join("")}</div>` : ""}
    </article>`;
  }

  function renderList(list, title, whenMap, emptyHtml, laden) {
    const active = [state.cluster, state.soort && soortLabel(state.soort), ...state.tags].filter(Boolean);
    const filterend = active.length || state.q.trim();
    let inhoud;
    if (laden) inhoud = '<p class="loading">Zoeken…</p>';
    else if (list.length) inhoud = `<div class="cards">${list.map((a) => cardHTML(a, whenMap && whenMap[a.id])).join("")}</div>`;
    else if (emptyHtml && !filterend) inhoud = emptyHtml;
    else inhoud = '<div class="empty">Geen artikelen gevonden. Probeer een ander trefwoord of wis de filters.<br><br>Mis je een artikel? <button class="tb" type="button" id="askBot">Vraag het de assistent</button></div>';
    return `<div class="view"><h1>${esc(title)}</h1>
      ${filterend && !laden ? `<div class="resulthead"><span class="n" role="status">${list.length} ${list.length === 1 ? "artikel" : "artikelen"}${state.q.trim() ? ` voor “${esc(state.q.trim())}”` : ""}${active.length ? ` · ${active.map(esc).join(", ")}` : ""}</span><button class="tb" type="button" id="clearF">Wissen</button></div>` : ""}
      ${inhoud}</div>`;
  }

  function renderArticle(a) {
    const zt = a.zaaktypen.length ? a.zaaktypen.map(esc).join(", ") : "alle zaaktypen";
    return `<div class="view">
     ${EMBED ? `<div class="crumb"><button type="button" id="back">← Terug naar artikelen bij ${esc(ZAAKTYPE)}</button></div>` : '<div class="crumb"><button type="button" id="back">← Terug</button></div>'}
     <article class="art" id="artikel" aria-labelledby="artTitel">
      ${a.status !== "gepubliceerd" ? `<div class="concept-banner">Dit artikel is <b>${esc(a.status)}</b> en niet zichtbaar voor medewerkers.</div>` : ""}
      <div class="head">${isPM() ? `<span class="type ${esc(a.soort)}">${esc(soortLabel(a.soort))}</span>` : ""}
       <div class="toolbar">
        <button class="tb" type="button" id="favBtn" aria-pressed="${favs.has(a.id)}">${favs.has(a.id) ? "★ Favoriet" : "☆ Favoriet"}</button>
        <button class="tb" type="button" id="shareBtn">⤴ Delen</button>
        ${EMBED ? `<a class="tb" href="${esc(a.url)}" target="_blank" rel="noopener">↗ Open in kennisbank</a>` : ""}
        ${a.bewerk_url ? `<a class="tb primary" href="${esc(a.bewerk_url)}" ${EMBED ? 'target="_blank" rel="noopener"' : ""}>Bewerken</a>` : ""}
       </div></div>
      <h1 id="artTitel">${esc(a.titel)}</h1>
      <p class="summary">${esc(a.samenvatting)}</p>
      ${a.wijziging ? `<div class="wijziging" id="wijzBlok" role="status"><div><b>Gewijzigd op ${esc(datum(a.wijziging.datum))}</b> (versie ${a.wijziging.versie})<p>${esc(a.wijziging.toelichting) || "Het artikel is inhoudelijk bijgewerkt."}</p></div><button class="tb primary" type="button" id="wijzGezien">Ik snap het</button></div>` : ""}
      <p class="docline">${esc(clusterLabel(a))} · ${zt} · versie ${a.versie}, bijgewerkt ${datum(a.gepubliceerd_op)} · eigenaar ${esc(a.eigenaar)}</p>
      ${a.blokken.some((b) => b.type === "sectie") ? '<div class="secbar"><button class="tb" type="button" id="toggleAll">Alles uitklappen</button></div>' : ""}
      <div class="sections">${a.blokken.map((b) => b.type === "tekst" ? `<div class="inleiding">${b.html}</div>` : `<details class="sec" id="sectie-${b.nummer}" ${b.nummer === 1 ? "open" : ""}><summary>${esc(b.kop)}</summary><div class="body">${b.html}</div></details>`).join("")}</div>
      <div class="foot">
       ${a.gerelateerd.length ? `<div class="related"><h2 class="stats-h">Gerelateerd</h2><ul>${a.gerelateerd.map((r) => `<li><a href="${esc(r.url)}" data-open="${r.id}" class="linkbtn">${esc(r.titel)}</a></li>`).join("")}</ul></div>` : ""}
       <div class="chips" aria-label="Tags">${a.tags.map((t) => `<button class="chip" type="button" data-tag="${esc(t)}">${esc(t)}</button>`).join("")}</div>
       <p class="hint">Klopt iets niet of mis je iets? Selecteer de tekst, of <button class="link" type="button" id="propBtn">dien een verbetervoorstel in</button>.</p>
      </div>
     </article></div>`;
  }

  function renderProps() {
    const lijst = [...voorstellen];
    const lead = isPM()
      ? "Voorstellen van collega's bij artikelen in jouw omgeving. Zet de status en geef een terugkoppeling; de indiener ziet die hier terug."
      : "Jouw voorstellen, met de terugkoppeling van procesmanagement.";
    return `<div class="view"><h1>Verbetervoorstellen</h1><p class="lead">${lead}</p>
     ${lijst.length ? `<div class="props">${lijst.map((p) => `<div class="prop">
      <div class="ph"><span><a class="tb" href="${esc(p.artikel_url)}" data-open="${p.artikel}">${esc(p.artikel_titel)}</a> &nbsp;${esc(p.van_mij ? "Jij" : p.ingediend_door)} · ${datum(p.ingediend_op)} · bij versie ${p.artikel_versie}</span><span class="status ${esc(p.status)}">${esc(VOORSTEL_LABEL[p.status] || p.status)}</span></div>
      ${p.citaat ? `<blockquote>“${esc(p.citaat)}”</blockquote>` : ""}
      <div>${esc(p.tekst)}</div>
      ${p.terugkoppeling ? `<div class="fb"><b>Terugkoppeling procesmanagement</b>${esc(p.terugkoppeling)}</div>` : ""}
      ${isPM() ? `<div class="manage"><label class="visually-hidden" for="st-${p.id}">Status</label><select id="st-${p.id}" data-status="${p.id}">${Object.entries(VOORSTEL_LABEL).map(([k, v]) => `<option value="${k}" ${p.status === k ? "selected" : ""}>${v}</option>`).join("")}</select><label class="visually-hidden" for="fb-${p.id}">Terugkoppeling</label><input id="fb-${p.id}" data-fb="${p.id}" placeholder="Terugkoppeling aan de indiener…" value="${esc(p.terugkoppeling || "")}"><button class="tb" type="button" data-save="${p.id}">Opslaan</button></div>` : ""}
     </div>`).join("")}</div>` : '<div class="empty">Nog geen verbetervoorstellen. Open een artikel en selecteer tekst om er een in te dienen.</div>'}</div>`;
  }

  function renderNieuws() {
    const lijst = berichten || [];
    const actueel = lijst.filter((b) => !b.verlopen);
    const ouder = lijst.filter((b) => b.verlopen);
    const item = (b) => `<article class="bericht${b.vastgepind ? " vast" : ""}" id="bericht-${b.id}">
      <div class="b-head"><h2>${esc(b.titel)}</h2>${isNieuw(b) ? '<span class="status nieuw">Nieuw</span>' : ""}${b.vastgepind ? '<span class="status vast" title="Vastgepind">📌</span>' : ""}</div>
      <p class="b-meta">${datum(b.gepubliceerd_op)} · ${esc(b.auteur)}${b.bewerk_url ? ` · <a href="${esc(b.bewerk_url)}">Bewerken</a>` : ""}</p>
      <div class="b-body">${b.tekst}</div>
      ${b.artikelen.length ? `<div class="b-links">Dit gaat over: ${b.artikelen.map((a) => `<a href="${esc(a.url)}" data-open="${a.id}" class="linkbtn">${esc(a.titel)}</a>`).join(", ")}</div>` : ""}
    </article>`;
    return `<div class="view"><h1>Nieuws</h1><p class="lead">Mededelingen en gewijzigde werkwijzen van procesmanagement.${isPM() ? ' <a href="/beheer/kennisbank/bericht/add/">Nieuw bericht schrijven</a>' : ""}</p>
      ${actueel.length ? `<div class="berichten">${actueel.map(item).join("")}</div>` : '<div class="empty">Er is nog geen nieuws.</div>'}
      ${ouder.length ? `<details class="ouder"><summary>Ouder nieuws (${ouder.length})</summary><div class="berichten">${ouder.map(item).join("")}</div></details>` : ""}
    </div>`;
  }

  function renderStats(s) {
    const max = Math.max(1, ...s.artikelen.map((a) => a.weergaven));
    const maxT = Math.max(1, ...s.zoektermen.map((t) => t.aantal));
    return `<div class="view"><h1>Gebruiksstatistieken</h1><p class="lead">Welke artikelen worden gelezen, waar wordt op gezocht en hoeveel voorstellen er binnenkomen, over de afgelopen ${s.dagen} dagen. De cijfers bevatten geen gegevens over personen.</p>
     <div class="tiles">
      <div class="tile"><b>${s.totaal_weergaven.toLocaleString("nl-NL")}</b><span>weergaven</span></div>
      <div class="tile"><b>${s.aantal_artikelen}</b><span>gepubliceerde artikelen</span></div>
      <div class="tile"><b>${s.voorstellen_open}</b><span>open voorstellen</span></div>
      <div class="tile"><b>${s.voorstellen_verwerkt}</b><span>voorstellen verwerkt</span></div>
      <div class="tile"><b>${s.assistent_vragen}</b><span>vragen aan de assistent</span></div>
     </div>
     <div class="table-wrap"><table><caption class="visually-hidden">Weergaven per artikel</caption><thead><tr><th scope="col">Artikel</th><th scope="col">Soort</th><th scope="col" class="num">Weergaven</th><th scope="col"><span class="visually-hidden">Verhouding</span></th><th scope="col" class="num">Voorstellen</th></tr></thead><tbody>
     ${s.artikelen.map((a) => `<tr><td><a href="${esc(a.url)}" class="linkbtn" data-open="${a.id}">${esc(a.titel)}</a>${a.status !== "gepubliceerd" ? ` <span class="versie-badge">(${esc(a.status)})</span>` : ""}</td><td><span class="type ${esc(a.soort)}">${esc(soortLabel(a.soort))}</span></td><td class="num">${a.weergaven}</td><td><div class="bar" aria-hidden="true"><i data-w="${Math.round((a.weergaven / max) * 100)}"></i></div></td><td class="num">${a.voorstellen}</td></tr>`).join("")}
     </tbody></table></div>
     <h2 class="stats-h">Meest gezochte termen</h2>
     ${s.zoektermen.length ? `<div class="table-wrap"><table><thead><tr><th scope="col">Zoekterm</th><th scope="col" class="num">Zoekopdrachten</th><th scope="col"><span class="visually-hidden">Verhouding</span></th></tr></thead><tbody>${s.zoektermen.map((t) => `<tr><td>${esc(t.term)}</td><td class="num">${t.aantal}</td><td><div class="bar" aria-hidden="true"><i data-w="${Math.round((t.aantal / maxT) * 100)}"></i></div></td></tr>`).join("")}</tbody></table></div>` : '<div class="empty">Nog geen zoekopdrachten in deze periode.</div>'}
     <h2 class="stats-h">Gezocht zonder resultaat</h2>
     <p class="lead">Hier zoeken collega's naar kennis die (nog) niet in de kennisbank staat.</p>
     ${s.zoektermen_zonder_resultaat.length ? `<div class="table-wrap"><table><thead><tr><th scope="col">Zoekterm</th><th scope="col" class="num">Keer zonder resultaat</th></tr></thead><tbody>${s.zoektermen_zonder_resultaat.map((t) => `<tr><td>${esc(t.term)}</td><td class="num">${t.aantal}</td></tr>`).join("")}</tbody></table></div>` : '<div class="empty">Geen zoekopdrachten zonder resultaat.</div>'}
    </div>`;
  }

  function zetBalken() { $$(".bar i[data-w]").forEach((i) => { i.style.width = i.dataset.w + "%"; }); }

  function renderZaaktype() {
    const lijst = artikelen.filter((a) => a.zaaktypen.includes(ZAAKTYPE));
    return `<div class="view"><h1>Kennisbank bij ${esc(ZAAKTYPE)}</h1>
      <p class="lead">${lijst.length} ${lijst.length === 1 ? "artikel hoort" : "artikelen horen"} bij dit zaaktype.</p>
      ${lijst.length ? `<div class="cards">${lijst.map((a) => cardHTML(a)).join("")}</div>` : '<div class="empty">Er zijn nog geen artikelen aan dit zaaktype gekoppeld.</div>'}
      <p class="hint">Iets anders nodig? Zoek hierboven of <button class="link" type="button" id="askBot">vraag het de assistent</button>.</p></div>`;
  }

  function renderLogin() {
    return `<div class="embed-login"><h1>Inloggen</h1><p class="lead">Log in om de kennisbank te gebruiken. Het inloggen opent in een nieuw venster.</p><button class="tb primary" type="button" id="loginBtn">Inloggen</button></div>`;
  }
  function wireLogin() {
    const b = $("#loginBtn");
    if (b) b.addEventListener("click", () => window.open("/login-voltooid/?start=1", "kb-login", "width=520,height=680"));
  }
  window.addEventListener("message", (e) => {
    if (e.origin === location.origin && e.data === "kb-ingelogd") location.reload();
  });

  /* ---------- Gedrag ---------- */
  function openArticle(id, sectie) {
    state.artikel = Number(id);
    zetUrl();
    render(true).then(() => {
      if (sectie == null) return;
      const d = document.getElementById("sectie-" + sectie);
      if (d) { d.open = true; d.scrollIntoView({ block: "start" }); d.querySelector("summary").focus(); }
      else if (Number(sectie) === 0) window.scrollTo(0, 0);
    });
  }

  async function registreerWeergave(id) {
    try {
      await api("artikelen/" + id + "/weergave", { method: "POST" });
      ik.recent = [{ id, bezocht_op: new Date().toISOString() }, ...ik.recent.filter((r) => r.id !== id)].slice(0, ik.recent_max || 10);
      renderFilters();
    } catch (e) { /* statistiek is niet kritisch */ }
  }

  async function toggleFav(id) {
    id = Number(id);
    const aan = !favs.has(id);
    try {
      await api("artikelen/" + id + "/favoriet", { method: aan ? "PUT" : "DELETE" });
      aan ? favs.add(id) : favs.delete(id);
      render(false);
      toast(aan ? "Toegevoegd aan favorieten" : "Verwijderd uit favorieten");
    } catch (e) { toast("Opslaan van favoriet is mislukt"); }
  }

  function wireList() {
    $$("[data-open]").forEach((b) => b.addEventListener("click", (e) => { e.preventDefault(); openArticle(b.dataset.open); }));
    $$("[data-nav]").forEach((b) => b.addEventListener("click", () => ga(b.dataset.nav)));
    $$("[data-fav]").forEach((b) => b.addEventListener("click", (e) => { e.stopPropagation(); toggleFav(b.dataset.fav); }));
    const c = $("#clearF");
    if (c) c.addEventListener("click", () => { state.q = ""; $("#q").value = ""; state.zoekresultaat = null; state.cluster = null; state.soort = null; state.tags.clear(); render(false); });
    const ab = $("#askBot");
    if (ab) ab.addEventListener("click", () => { openChat(); $("#chatIn").value = state.q; $("#chatIn").focus(); });
    const ag = $("#allesGezien");
    if (ag) ag.addEventListener("click", async () => {
      ag.disabled = true;
      try {
        await api("wijzigingen/gezien", { method: "POST" });
        artikelen.forEach((a) => { a.wijziging = null; });
        if (huidigArtikel) huidigArtikel.wijziging = null;
        render(false);
        toast("Alle wijzigingen gemarkeerd als gezien");
      } catch (e) { ag.disabled = false; toast("Markeren is mislukt"); }
    });
    $$("[data-bericht]").forEach((b) => b.addEventListener("click", () => { state.scrollNaarBericht = b.dataset.bericht; ga("nieuws"); }));
    $$("[data-save]").forEach((b) => b.addEventListener("click", async () => {
      const id = b.dataset.save;
      try {
        const nieuw = await api("voorstellen/" + id, { method: "PATCH", body: { status: $(`[data-status="${id}"]`).value, terugkoppeling: $(`[data-fb="${id}"]`).value.trim() } });
        voorstellen = voorstellen.map((p) => (String(p.id) === id ? nieuw : p));
        render(false);
        toast("Terugkoppeling opgeslagen");
      } catch (e) { toast("Opslaan is mislukt"); }
    }));
  }

  function wireArticle() {
    const a = huidigArtikel;
    // Externe links in de artikeltekst openen in een nieuw tabblad, zodat de kennisbank (en het
    // zaaksysteem waarin hij ingebed kan zijn) niet wordt weggenavigeerd.
    $$(".art .sections a[href]").forEach((l) => { if (l.origin !== location.origin) { l.target = "_blank"; l.rel = "noopener noreferrer"; } });
    $("#back").addEventListener("click", () => {
      state.artikel = null; huidigArtikel = null;
      if (EMBED) { state.view = "zaaktype"; render(true); } else if (history.length > 1 && document.referrer.startsWith(location.origin)) history.back(); else ga(state.view);
    });
    $("#favBtn").addEventListener("click", () => toggleFav(a.id));
    $("#shareBtn").addEventListener("click", () => {
      const url = location.origin + a.url;  // /artikel/<nummer>/<naam>: het nummer maakt de link blijvend
      const klaar = () => toast("Link gekopieerd");
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(url).then(klaar).catch(() => toast("Link: " + url));
      else toast("Link: " + url);
    });
    $("#propBtn").addEventListener("click", () => openProp(""));
    const wg = $("#wijzGezien");
    if (wg) wg.addEventListener("click", async () => {
      wg.disabled = true;
      try {
        await api("artikelen/" + a.id + "/gezien", { method: "POST", body: { versie: a.wijziging ? a.wijziging.versie : a.versie } });
        a.wijziging = null;
        const kort = artById(a.id); if (kort) kort.wijziging = null;
        const blok = $("#wijzBlok"); if (blok) blok.remove();
        renderFilters();
        toast("Gemarkeerd als gezien");
      } catch (e) { wg.disabled = false; toast("Markeren is mislukt"); }
    });
    // De knop "Alles uitklappen" is er alleen als het artikel secties heeft (bijv. niet direct na een Word-import).
    const ta = $("#toggleAll");
    if (ta) ta.addEventListener("click", () => {
      const ds = $$("details.sec");
      const open = ds.some((d) => !d.open);
      ds.forEach((d) => { d.open = open; });
      ta.textContent = open ? "Alles inklappen" : "Alles uitklappen";
    });
    $$("[data-tag]").forEach((b) => b.addEventListener("click", () => {
      state.tags = new Set([b.dataset.tag]); state.cluster = null; state.soort = null; state.q = ""; $("#q").value = "";
      if (EMBED) { state.artikel = null; huidigArtikel = null; state.view = "artikelen"; render(true); } else ga("artikelen");
    }));
    if (location.hash.startsWith("#sectie-")) {
      const d = document.getElementById(location.hash.slice(1));
      if (d) { d.open = true; d.scrollIntoView(); }
    }
  }

  async function setOnb(v) {
    onboarding = v;
    body.classList.toggle("onboarding", v);
    $("#onbToggle").setAttribute("aria-pressed", String(v));
    try { await api("ik", { method: "PATCH", body: { onboarding: v } }); } catch (e) { /* voorkeur niet opgeslagen */ }
  }

  /* ---------- Zoeken (server-side, met vertraging tijdens typen) ---------- */
  async function zoek(registreer) {
    const q = state.q.trim();
    if (!q) { state.zoekresultaat = null; render(false); return; }
    const nr = ++zoekVolgnr;
    const p = new URLSearchParams({ q });
    if (registreer) p.set("registreer", "1");
    try {
      const res = await api("artikelen?" + p.toString());
      if (nr !== zoekVolgnr) return;  // er is al een nieuwere zoekopdracht
      state.zoekresultaat = res;
      if (!state.artikel) render(false);
    } catch (e) { /* stil */ }
  }

  $("#zoekform").addEventListener("submit", (e) => { e.preventDefault(); clearTimeout(zoekT); clearTimeout(registreerT); zoek(true); });
  $("#q").addEventListener("input", (e) => {
    state.q = e.target.value;
    state.zoekresultaat = null;
    if (state.artikel) { state.artikel = null; huidigArtikel = null; }
    if (!["artikelen", "favorieten"].includes(state.view)) state.view = "artikelen";
    if (!EMBED) zetUrl(true);
    render(false);
    clearTimeout(zoekT); clearTimeout(registreerT);
    zoekT = setTimeout(() => zoek(false), 250);
    // Alleen de 'uitgetypte' zoekterm telt mee in de statistiek.
    registreerT = setTimeout(() => zoek(true), 1500);
  });

  /* ---------- Tekstselectie → verbetervoorstel ---------- */
  const selBtn = $("#selBtn");
  let selText = "";
  function checkSel() {
    const s = window.getSelection();
    const art = $("#artikel");
    if (!art || !s || s.isCollapsed || !s.toString().trim() || !art.contains(s.anchorNode)) { selBtn.classList.remove("show"); return; }
    selText = s.toString().trim().slice(0, 2000);
    const r = s.getRangeAt(0).getBoundingClientRect();
    selBtn.style.left = Math.max(8, Math.min(window.innerWidth - selBtn.offsetWidth - 8, r.left)) + "px";
    selBtn.style.top = (r.top > 60 ? r.top - 44 : r.bottom + 8) + "px";
    selBtn.classList.add("show");
  }
  document.addEventListener("mouseup", () => setTimeout(checkSel, 10));
  document.addEventListener("keyup", (e) => { if (e.shiftKey) checkSel(); });
  document.addEventListener("selectionchange", () => { const s = window.getSelection(); if (!s || s.isCollapsed) selBtn.classList.remove("show"); });
  selBtn.addEventListener("mousedown", (e) => e.preventDefault());
  selBtn.addEventListener("click", () => { openProp(selText); selBtn.classList.remove("show"); });

  /* ---------- Verbetervoorstel-venster ---------- */
  let terugFocus = null;
  function openProp(quote) {
    const a = huidigArtikel;
    terugFocus = document.activeElement;
    $("#propArt").textContent = "Artikel: " + a.titel + " (versie " + a.versie + ")";
    $("#propQuote").textContent = quote;
    $("#propQuote").hidden = !quote;
    $("#propText").value = "";
    $("#backdrop").classList.add("open");
    $("#propText").focus();
  }
  function closeProp() {
    if (!$("#backdrop").classList.contains("open")) return;
    $("#backdrop").classList.remove("open");
    if (terugFocus) terugFocus.focus();
  }
  $("#propCancel").addEventListener("click", closeProp);
  $("#backdrop").addEventListener("click", (e) => { if (e.target === $("#backdrop")) closeProp(); });
  $("#propForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const knop = e.submitter || $("#propForm [type=submit]");
    knop.disabled = true;
    try {
      const v = await api("voorstellen", { method: "POST", body: { artikel: huidigArtikel.id, citaat: $("#propQuote").hidden ? "" : $("#propQuote").textContent, tekst: $("#propText").value.trim() } });
      voorstellen = [v, ...voorstellen];
      closeProp();
      renderFilters();
      toast("Verbetervoorstel ingediend. Je krijgt een terugkoppeling van procesmanagement.");
    } catch (err) {
      toast(err.status === 429 ? "Je hebt veel voorstellen ingediend; probeer het later opnieuw." : "Indienen is mislukt.");
    } finally { knop.disabled = false; }
  });

  /* ---------- Assistent ---------- */
  const drawer = $("#drawer");
  function openChat() {
    drawer.hidden = false;
    requestAnimationFrame(() => drawer.classList.add("open"));
    $("#chatBtn").setAttribute("aria-expanded", "true");
    $("#chatIn").focus();
  }
  function closeChat() {
    if (!drawer.classList.contains("open")) return;
    drawer.classList.remove("open");
    $("#chatBtn").setAttribute("aria-expanded", "false");
    setTimeout(() => { if (!drawer.classList.contains("open")) drawer.hidden = true; }, 260);
    $("#chatBtn").focus();
  }
  function addMsg(html, who) {
    const d = document.createElement("div");
    d.className = "msg " + who;
    d.innerHTML = html;
    $("#msgs").appendChild(d);
    $("#msgs").scrollTop = 1e6;
    d.querySelectorAll("[data-open]").forEach((b) => b.addEventListener("click", (e) => {
      e.preventDefault();
      openArticle(b.dataset.open, b.dataset.sectie != null ? Number(b.dataset.sectie) : null);
      if (window.innerWidth < 900) closeChat();
    }));
    return d;
  }
  async function botAnswer(vraag) {
    addMsg(esc(vraag), "user");
    const wacht = addMsg("<p>…</p>", "bot");
    try {
      const a = await api("assistent", { method: "POST", body: { vraag, zaaktype: ZAAKTYPE || undefined } });
      let html = a.html;
      if (a.bronnen.length) {
        const uniek = [];
        a.bronnen.forEach((b) => { if (!uniek.some((u) => u.id === b.id && u.sectie === b.sectie)) uniek.push(b); });
        html += `<div class="bronnen">${uniek.slice(0, 3).map((b) => `<a class="src" href="${esc(b.url)}" data-open="${b.id}" data-sectie="${b.sectie_index}">↗ ${esc(b.titel)} – ${esc(b.sectie)}</a>`).join("")}</div>`;
      }
      if (a.melding) html += `<p class="melding">${esc(a.melding)}</p>`;
      wacht.remove();
      addMsg(html, "bot");
    } catch (e) {
      wacht.remove();
      addMsg(e.status === 429 ? "<p>Je stelt veel vragen achter elkaar. Wacht even en probeer het opnieuw.</p>" : "<p>De assistent is nu niet bereikbaar. Probeer het later opnieuw, of zoek via de zoekbalk.</p>", "bot");
    }
  }
  $("#chatBtn").addEventListener("click", () => (drawer.classList.contains("open") ? closeChat() : openChat()));
  $("#chatClose").addEventListener("click", closeChat);
  $("#chatform").addEventListener("submit", (e) => { e.preventDefault(); const v = $("#chatIn").value.trim(); if (!v) return; $("#chatIn").value = ""; botAnswer(v); });

  /* ---------- Kop en zijbalk ---------- */
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && !/input|textarea|select/i.test(document.activeElement.tagName)) { e.preventDefault(); $("#q").focus(); }
    if (e.key === "Escape") { closeProp(); closeChat(); }
  });
  $("#onbToggle").addEventListener("click", () => setOnb(!onboarding));
  $("#sideToggle").addEventListener("click", () => {
    const open = $("#side").classList.toggle("open");
    $("#sideToggle").setAttribute("aria-expanded", String(open));
  });
  $$(".nav button").forEach((b) => b.addEventListener("click", () => {
    if (b.dataset.view === "voorstellen") laadVoorstellen().then(() => render(true));
    ga(b.dataset.view);
  }));
  ["#fCluster", "#fType"].forEach((sel) => $(sel).addEventListener("click", (e) => {
    const b = e.target.closest(".chip");
    if (!b) return;
    const v = b.dataset.v;
    if (b.dataset.f === "cluster") state.cluster = state.cluster === v ? null : v;
    else state.soort = state.soort === v ? null : v;
    if (state.artikel) { state.artikel = null; huidigArtikel = null; }
    if (!["artikelen", "favorieten"].includes(state.view)) state.view = "artikelen";
    zetUrl();
    render(false);
  }));

  async function laadVoorstellen() {
    try { voorstellen = await api("voorstellen"); } catch (e) { voorstellen = []; }
  }
  async function laadBerichten() {
    try { berichten = await api("berichten"); } catch (e) { berichten = []; }
  }
  function wireNieuws() {
    if (state.scrollNaarBericht) {
      const el = document.getElementById("bericht-" + state.scrollNaarBericht);
      state.scrollNaarBericht = null;
      if (el) { el.scrollIntoView({ block: "start" }); el.classList.add("licht"); }
    }
  }
  async function markeerNieuwsGezien() {
    // De teller gaat direct naar nul; de labels "Nieuw" blijven staan tot de gebruiker de pagina verlaat.
    if (nieuwsGezienStraks || (!nieuwsOngelezen() && !ik.nieuws_ongelezen)) return;
    nieuwsGezienStraks = new Date().toISOString();
    ik.nieuws_ongelezen = 0;
    renderFilters();
    try { await api("berichten/gezien", { method: "POST" }); } catch (e) { /* teller niet opgeslagen; niet kritisch */ }
  }
  function wireInstellingen() {
    const blok = $("#instellingen"), cb = $("#mailPref");
    blok.hidden = EMBED || ik.favorieten_mail === "uit";
    cb.checked = !!ik.mail_bij_favorieten;
    cb.addEventListener("change", async () => {
      try {
        await api("ik", { method: "PATCH", body: { mail_bij_favorieten: cb.checked } });
        ik.mail_bij_favorieten = cb.checked;
        toast(cb.checked ? "Je krijgt een e-mail als een favoriet wijzigt" : "Geen e-mail meer bij wijzigingen van favorieten");
      } catch (e) { cb.checked = !cb.checked; toast("Opslaan van de instelling is mislukt"); }
    });
  }

  function renderGebruiker() {
    $("#user").innerHTML = `<span class="visually-hidden">Ingelogd als</span><span>${esc(ik.naam)}</span> · <a href="${esc(ik.uitlog_url)}" id="uitlog">Uitloggen</a>`;
    const meer = [];
    if (ik.beheer_url) meer.push(`<a href="${esc(ik.beheer_url)}">Beheer: artikelen bewerken</a>`);
    meer.push('<a href="/api/docs/">API-documentatie</a>');
    $("#meer").innerHTML = meer.join("");
    $("#aiNote").textContent = ik.ai_aan
      ? "Antwoorden komen uit de kennisbank. Controleer belangrijke zaken altijd in het artikel."
      : "De assistent zoekt in de kennisbank en citeert het best passende fragment.";
    $("#aiNote").classList.toggle("ai", !!ik.ai_aan);
    // Uitloggen moet een POST zijn (Django 5).
    $("#uitlog").addEventListener("click", (e) => {
      e.preventDefault();
      const f = document.createElement("form");
      f.method = "post"; f.action = ik.uitlog_url;
      f.innerHTML = `<input type="hidden" name="csrfmiddlewaretoken" value="${esc(cookie("csrftoken"))}">`;
      document.body.appendChild(f); f.submit();
    });
  }

  /* ---------- Start ---------- */
  async function start() {
    try {
      ik = await api("ik");
    } catch (e) {
      ik = null;
      render();
      return;
    }
    renderGebruiker();
    onboarding = ik.onboarding;
    body.classList.toggle("onboarding", onboarding);
    $("#onbToggle").setAttribute("aria-pressed", String(onboarding));
    favs = new Set(ik.favorieten.map(Number));
    nieuwsGezienOp = ik.nieuws_gezien_op;
    wireInstellingen();
    [lijsten, artikelen] = await Promise.all([api("keuzelijsten"), api("artikelen")]);
    await laadVoorstellen();
    if (!EMBED) await laadBerichten();  // ook voor het nieuwsblok op de startpagina
    if (EMBED) state.view = "zaaktype"; else leesUrl();
    if (state.view === "statistieken" && !isPM()) state.view = "artikelen";
    // Voorbeeldvragen: in het zaaksysteem algemeen; daarbuiten alleen in de demo (die horen bij de demo-inhoud).
    const suggesties = EMBED && ZAAKTYPE
      ? ["Waar moet ik op letten bij dit zaaktype?", "Welke termijnen gelden hier?"]
      : DEMO ? ["Wanneer stuur ik een tweede rappel?", "Welke velden zijn verplicht bij een melding?", "Wat doe ik met een zwerfboot in de vaargeul?"] : [];
    suggesties.forEach((s) => { const b = document.createElement("button"); b.type = "button"; b.textContent = s; b.addEventListener("click", () => botAnswer(s)); $("#sugg").appendChild(b); });
    addMsg("<p>Hallo! Stel je vraag over een werkinstructie of werkafspraak. Ik zoek het antwoord in de kennisbank en verwijs je naar het juiste artikel.</p>", "bot");
    render();
  }
  start();
})();
