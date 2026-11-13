// Gedeelde hulpfuncties voor de browsertests (rook.js en axe.js). Zie README.md.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const B = process.env.KB_URL || "http://127.0.0.1:8765";
const OPZET = JSON.parse(fs.readFileSync(process.env.KB_OPZET || path.join(__dirname, ".opzet.json"), "utf8"));
const UITVOER = path.join(__dirname, "uitvoer");
const AXE = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");

let fouten = 0;
let controles = 0;
const cspGezien = new Set();

function ok(voorwaarde, naam, extra) {
  controles++;
  if (!voorwaarde) fouten++;
  console.log((voorwaarde ? "OK   " : "FOUT ") + naam + (extra && !voorwaarde ? " :: " + extra : ""));
}

// KB_CHROME: pad naar een al geïnstalleerde Chrome/Chromium, als `npx playwright install chromium` niet kan.
async function start() {
  return chromium.launch(process.env.KB_CHROME ? { executablePath: process.env.KB_CHROME } : {});
}

// Een ingelogde pagina. Fouten in de scripts van de pagina en meldingen van de Content-Security-Policy tellen
// als fout: zo betrapt elke test ook een kapot script of een inline script dat de CSP tegenhoudt.
async function sessie(browser, gebruiker, opties) {
  opties = opties || {};
  const context = await browser.newContext({
    viewport: { width: opties.breedte || 1440, height: opties.hoogte || 950 },
    colorScheme: opties.schema || "light",
    bypassCSP: !!opties.bypassCSP, // alleen axe.js: axe wordt als inline script ingevoegd
  });
  const p = await context.newPage();
  p.on("pageerror", (e) => { fouten++; console.log("FOUT script op " + p.url() + " :: " + e.message); });
  p.on("console", (m) => {
    if (m.type() === "error" && /Content Security Policy|Content-Security-Policy/i.test(m.text())) {
      const sleutel = new URL(p.url()).pathname + m.text().slice(0, 160);
      if (cspGezien.has(sleutel)) return; // dezelfde melding op hetzelfde scherm telt één keer
      cspGezien.add(sleutel);
      fouten++; console.log("FOUT CSP op " + p.url() + " :: " + m.text().slice(0, 300));
    }
  });
  await p.goto(B + "/inloggen/?next=/");
  await p.fill('input[name="username"]', gebruiker);
  await p.fill('input[name="password"]', "demo");
  await Promise.all([p.waitForURL((u) => !/inloggen/.test(u.pathname)), p.click('button[type="submit"]')]);
  // De eerste keer op de site komt het welkomstvenster; dat staat de tests in de weg.
  try { await p.locator("#welkomNee").click({ timeout: 2500 }); } catch (_) { /* geen welkomstvenster */ }
  return p;
}

// Vensters die bij het openen van een scherm vanzelf komen (bijvoorbeeld een kladversie): de veilige knop.
async function dichtVensters(p) {
  for (let i = 0; i < 4 && (await p.locator("dialog[open]").count()); i++) {
    await p.locator("dialog[open] button").last().click();
    await p.waitForTimeout(400);
  }
}

// Het bewerkscherm van een artikel, klaar om in te werken.
async function bewerk(p, artikel, query) {
  await p.goto(B + `/beheer/kennisbank/artikel/${artikel}/change/` + (query || ""));
  await p.locator(".ProseMirror").first().waitFor();
  await p.waitForTimeout(600);
  await dichtVensters(p);
}

async function meet(p, naam) {
  await p.addScriptTag({ content: AXE });
  const r = await p.evaluate(async () =>
    (await axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] })).violations.map(
      (v) => v.id + "(" + v.nodes.length + "): " + v.nodes.slice(0, 2).map((n) => n.target.join(" ") + " " + ((n.any[0] && n.any[0].message) || "")).join(" || ")
    )
  );
  ok(!r.length, "axe " + naam, JSON.stringify(r));
}

// Eén onderdeel van de test. Een fout hierin (een knop die er niet is, een wachttijd die verloopt) telt als fout,
// met een schermafdruk in uitvoer/, en de volgende onderdelen draaien gewoon door.
async function stap(naam, p, fn) {
  console.log("--- " + naam);
  try {
    await fn();
  } catch (e) {
    fouten++;
    console.log("FOUT " + naam + " :: " + String(e.message || e).split("\n").slice(0, 4).join(" | "));
    try {
      fs.mkdirSync(UITVOER, { recursive: true });
      await p.screenshot({ path: path.join(UITVOER, naam.replace(/[^a-z0-9]+/gi, "-").toLowerCase() + ".png") });
    } catch (_) { /* de pagina is al weg */ }
    try { await p.keyboard.press("Escape"); } catch (_) { /* idem */ }
  }
}

function klaar() {
  console.log(`\n${controles} controles, ${fouten} fout${fouten === 1 ? "" : "en"}.`);
  process.exit(fouten ? 1 : 0);
}

module.exports = { B, OPZET, ok, start, sessie, dichtVensters, bewerk, meet, stap, klaar, aantalFouten: () => fouten };
