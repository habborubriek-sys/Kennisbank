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
    const headers = { Accept: "application/json" };
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
  let onboarding = false;
  const state = { view: "recent", artikel: null, q: "", cluster: null, soort: null, tags: new Set(), zoekresultaat: null };
  let huidigArtikel = null;     // volledig artikel dat nu open is
  let zoekT, registreerT, zoekVolgnr = 0;

  const isPM = () => !!(ik && ik.is_redacteur);
  const artBySlug = (slug) => artikelen.find((a) => a.slug === slug);
  const clusterLabel = (a) => (a.clusters.length ? a.clusters.join(", ") : "Alle clusters");
  const soortLabel = (w) => { const s = lijsten.soorten.find((x) => x.waarde === w); return s ? s.label : w; };
  const VOORSTEL_LABEL = { nieuw: "Nieuw", in_behandeling: "In behandeling", verwerkt: "Verwerkt", afgewezen: "Afgewezen" };

  /* ---------- Navigatie (echte URL's, zodat links te delen zijn) ---------- */
  const VIEWS = ["recent", "artikelen", "favorieten", "voorstellen", "statistieken"];

  function leesUrl() {
    if (EMBED) return;
    const pad = location.pathname.replace(/\/+$/, "");
    const m = pad.match(/^\/artikel\/([\w-]+)$/);
    state.artikel = m ? m[1] : null;
    const v = pad.replace(/^\//, "");
    if (!m) state.view = VIEWS.includes(v) ? v : (ik && ik.recent.length ? "recent" : "artikelen");
  }

  function zetUrl(vervang) {
    if (EMBED) return;
    const pad = state.artikel ? "/artikel/" + state.artikel : "/" + (state.view === "recent" ? "" : state.view);
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
    renderFilters();
    const m = $("#main");
    try {
      if (!ik) { m.innerHTML = renderLogin(); wireLogin(); return; }
      if (state.artikel) {
        if (!huidigArtikel || huidigArtikel.slug !== state.artikel) {
          m.innerHTML = '<p class="loading">Laden…</p>';
          huidigArtikel = await api("artikelen/" + encodeURIComponent(state.artikel));
          registreerWeergave(huidigArtikel.slug);
        }
        m.innerHTML = renderArticle(huidigArtikel);
        wireArticle();
      } else if (state.view === "zaaktype") {
        m.innerHTML = renderZaaktype(); wireList();
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
      bron = artikelen.filter((a) => favs.has(a.slug)); titel = "Favorieten";
      leeg = '<div class="empty">Nog geen favorieten. Open een artikel en klik op de ster om het hier vast te zetten.</div>';
    } else if (state.view === "recent") {
      bron = ik.recent.map((r) => artBySlug(r.slug)).filter(Boolean); titel = "Recent bezocht";
      when = Object.fromEntries(ik.recent.map((r) => [r.slug, ago(r.bezocht_op)]));
      leeg = '<div class="empty">Hier verschijnen de artikelen die je het laatst hebt geopend.<br><br>Zoek hierboven op een trefwoord, of <button class="tb" type="button" data-nav="artikelen">bekijk alle artikelen</button></div>';
    } else { bron = artikelen; titel = "Alle artikelen"; }
    return renderList(filtered(bron), titel, when, leeg, zoekend && state.zoekresultaat === null);
  }

  function cardHTML(a, when) {
    const meta = [];
    if (isPM()) {
      meta.push(`<span class="type ${esc(a.soort)}">${esc(soortLabel(a.soort))}</span>`, `<span>${esc(clusterLabel(a))}</span>`, "<span>·</span>", `<span>v${a.versie}, ${datum(a.gepubliceerd_op)}</span>`);
      if (a.status !== "gepubliceerd") meta.push(`<span class="status nieuw">${esc(a.status)}</span>`);
    }
    if (when) meta.push((isPM() ? "<span>·</span>" : "") + `<span class="when">${esc(when)}</span>`);
    return `<article class="card">
      <button class="star" type="button" data-fav="${esc(a.slug)}" aria-pressed="${favs.has(a.slug)}" aria-label="${favs.has(a.slug) ? "Verwijder uit favorieten" : "Voeg toe aan favorieten"}: ${esc(a.titel)}">${favs.has(a.slug) ? "★" : "☆"}</button>
      <h2><a href="${esc(a.url)}" data-open="${esc(a.slug)}" class="linkbtn card-link">${esc(a.titel)}</a></h2>
      <p>${esc(a.samenvatting)}</p>
      ${meta.length ? `<div class="meta">${meta.join("")}</div>` : ""}
    </article>`;
  }

  function renderList(list, title, whenMap, emptyHtml, laden) {
    const active = [state.cluster, state.soort && soortLabel(state.soort), ...state.tags].filter(Boolean);
    const filterend = active.length || state.q.trim();
    let inhoud;
    if (laden) inhoud = '<p class="loading">Zoeken…</p>';
    else if (list.length) inhoud = `<div class="cards">${list.map((a) => cardHTML(a, whenMap && whenMap[a.slug])).join("")}</div>`;
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
        <button class="tb" type="button" id="favBtn" aria-pressed="${favs.has(a.slug)}">${favs.has(a.slug) ? "★ Favoriet" : "☆ Favoriet"}</button>
        <button class="tb" type="button" id="shareBtn">⤴ Delen</button>
        ${EMBED ? `<a class="tb" href="${esc(a.url)}" target="_blank" rel="noopener">↗ Open in kennisbank</a>` : ""}
        ${a.bewerk_url ? `<a class="tb primary" href="${esc(a.bewerk_url)}" ${EMBED ? 'target="_blank" rel="noopener"' : ""}>Bewerken</a>` : ""}
       </div></div>
      <h1 id="artTitel">${esc(a.titel)}</h1>
      <p class="summary">${esc(a.samenvatting)}</p>
      <p class="docline">${esc(clusterLabel(a))} · ${zt} · versie ${a.versie}, bijgewerkt ${datum(a.gepubliceerd_op)} · eigenaar ${esc(a.eigenaar)}</p>
      <div class="secbar"><button class="tb" type="button" id="toggleAll">Alles uitklappen</button></div>
      <div class="sections">${a.secties.map((s, i) => `<details class="sec" id="sectie-${i}" ${i === 0 ? "open" : ""}><summary>${esc(s.kop)}</summary><div class="body">${s.onboarding_html ? `<div class="onb"><b>Voor nieuwe collega's</b>${s.onboarding_html}</div>` : ""}${s.inhoud_html}</div></details>`).join("")}</div>
      <div class="foot">
       ${a.gerelateerd.length ? `<div class="related"><h2 class="stats-h">Gerelateerd</h2><ul>${a.gerelateerd.map((r) => `<li><button type="button" data-open="${esc(r.slug)}">${esc(r.titel)}</button></li>`).join("")}</ul></div>` : ""}
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
      <div class="ph"><span><button class="tb" type="button" data-open="${esc(p.artikel)}">${esc(p.artikel_titel)}</button> &nbsp;${esc(p.van_mij ? "Jij" : p.ingediend_door)} · ${datum(p.ingediend_op)} · bij versie ${p.artikel_versie}</span><span class="status ${esc(p.status)}">${esc(VOORSTEL_LABEL[p.status] || p.status)}</span></div>
      ${p.citaat ? `<blockquote>“${esc(p.citaat)}”</blockquote>` : ""}
      <div>${esc(p.tekst)}</div>
      ${p.terugkoppeling ? `<div class="fb"><b>Terugkoppeling procesmanagement</b>${esc(p.terugkoppeling)}</div>` : ""}
      ${isPM() ? `<div class="manage"><label class="visually-hidden" for="st-${p.id}">Status</label><select id="st-${p.id}" data-status="${p.id}">${Object.entries(VOORSTEL_LABEL).map(([k, v]) => `<option value="${k}" ${p.status === k ? "selected" : ""}>${v}</option>`).join("")}</select><label class="visually-hidden" for="fb-${p.id}">Terugkoppeling</label><input id="fb-${p.id}" data-fb="${p.id}" placeholder="Terugkoppeling aan de indiener…" value="${esc(p.terugkoppeling || "")}"><button class="tb" type="button" data-save="${p.id}">Opslaan</button></div>` : ""}
     </div>`).join("")}</div>` : '<div class="empty">Nog geen verbetervoorstellen. Open een artikel en selecteer tekst om er een in te dienen.</div>'}</div>`;
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
     ${s.artikelen.map((a) => `<tr><td><button type="button" class="linkbtn" data-open="${esc(a.slug)}">${esc(a.titel)}</button>${a.status !== "gepubliceerd" ? ` <span class="versie-badge">(${esc(a.status)})</span>` : ""}</td><td><span class="type ${esc(a.soort)}">${esc(soortLabel(a.soort))}</span></td><td class="num">${a.weergaven}</td><td><div class="bar" aria-hidden="true"><i data-w="${Math.round((a.weergaven / max) * 100)}"></i></div></td><td class="num">${a.voorstellen}</td></tr>`).join("")}
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
  function openArticle(slug, sectie) {
    state.artikel = slug;
    zetUrl();
    render(true).then(() => {
      if (sectie == null) return;
      const d = document.getElementById("sectie-" + sectie);
      if (d) { d.open = true; d.scrollIntoView({ block: "start" }); d.querySelector("summary").focus(); }
    });
  }

  async function registreerWeergave(slug) {
    try {
      await api("artikelen/" + encodeURIComponent(slug) + "/weergave", { method: "POST" });
      ik.recent = [{ slug, bezocht_op: new Date().toISOString() }, ...ik.recent.filter((r) => r.slug !== slug)].slice(0, 10);
      renderFilters();
    } catch (e) { /* statistiek is niet kritisch */ }
  }

  async function toggleFav(slug) {
    const aan = !favs.has(slug);
    try {
      await api("artikelen/" + encodeURIComponent(slug) + "/favoriet", { method: aan ? "PUT" : "DELETE" });
      aan ? favs.add(slug) : favs.delete(slug);
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
    $("#back").addEventListener("click", () => {
      state.artikel = null; huidigArtikel = null;
      if (EMBED) { state.view = "zaaktype"; render(true); } else if (history.length > 1 && document.referrer.startsWith(location.origin)) history.back(); else ga(state.view);
    });
    $("#favBtn").addEventListener("click", () => toggleFav(a.slug));
    $("#shareBtn").addEventListener("click", () => {
      const url = location.origin + a.url;
      const klaar = () => toast("Link gekopieerd");
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(url).then(klaar).catch(() => toast("Link: " + url));
      else toast("Link: " + url);
    });
    $("#propBtn").addEventListener("click", () => openProp(""));
    const ta = $("#toggleAll");
    ta.addEventListener("click", () => {
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
      const v = await api("voorstellen", { method: "POST", body: { artikel: huidigArtikel.slug, citaat: $("#propQuote").hidden ? "" : $("#propQuote").textContent, tekst: $("#propText").value.trim() } });
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
        a.bronnen.forEach((b) => { if (!uniek.some((u) => u.slug === b.slug && u.sectie === b.sectie)) uniek.push(b); });
        html += `<div class="bronnen">${uniek.slice(0, 3).map((b) => `<button class="src" type="button" data-open="${esc(b.slug)}" data-sectie="${b.sectie_index}">↗ ${esc(b.titel)} – ${esc(b.sectie)}</button>`).join("")}</div>`;
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
    favs = new Set(ik.favorieten);
    [lijsten, artikelen] = await Promise.all([api("keuzelijsten"), api("artikelen")]);
    await laadVoorstellen();
    if (EMBED) state.view = "zaaktype"; else leesUrl();
    if (state.view === "statistieken" && !isPM()) state.view = "artikelen";
    const suggesties = EMBED && ZAAKTYPE
      ? ["Waar moet ik op letten bij dit zaaktype?", "Welke termijnen gelden hier?"]
      : ["Wanneer stuur ik een tweede rappel?", "Welke velden zijn verplicht bij een melding?", "Wat doe ik met een zwerfboot in de vaargeul?"];
    suggesties.forEach((s) => { const b = document.createElement("button"); b.type = "button"; b.textContent = s; b.addEventListener("click", () => botAnswer(s)); $("#sugg").appendChild(b); });
    addMsg("<p>Hallo! Stel je vraag over een werkinstructie of werkafspraak. Ik zoek het antwoord in de kennisbank en verwijs je naar het juiste artikel.</p>", "bot");
    render();
  }
  start();
})();
