const { chromium } = require(process.env.PLAYWRIGHT || "playwright");
const fs = require("fs");
const AXE = fs.readFileSync(process.env.AXE_PAD || require.resolve("axe-core/axe.min.js"), "utf8");
// Gebruik: node axe.js <inzage-id met een opmerking> [artikel-id met open voorstellen] [voorstel-id]
// Omgeving: KB_URL (standaard http://localhost:8000), demo-gebruikers met wachtwoord "demo".
const B = process.env.KB_URL || "http://localhost:8000", INZ = process.argv[2], ART = process.argv[3] || "", VS = process.argv[4] || "";
let fouten = 0;
async function sessie(b, u, schema) {
  const p = await (await b.newContext({ viewport: { width: 1280, height: 900 }, bypassCSP: true, colorScheme: schema })).newPage();
  p.on("pageerror", e => console.log("JS-FOUT", e.message));
  await p.goto(B + "/inloggen/?next=/"); await p.fill('input[name="username"]', u); await p.fill('input[name="password"]', "demo"); await p.click('button[type="submit"]'); await p.waitForTimeout(800);
  return p;
}
async function meet(p, naam) {
  await p.addScriptTag({ content: AXE });
  const r = await p.evaluate(async () => (await axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] })).violations.map(v => v.id + "(" + v.nodes.length + "): " + v.nodes.slice(0, 2).map(n => n.target.join(" ") + " " + ((n.any[0] && n.any[0].message) || "")).join(" || ")));
  if (r.length) fouten++;
  console.log((r.length ? "FOUT " : "OK   ") + naam + (r.length ? " " + JSON.stringify(r) : ""));
}
async function dichtVensters(p) { for (let i = 0; i < 4 && await p.locator("dialog[open]").count(); i++) { await p.locator("dialog[open] button").last().click(); await p.waitForTimeout(700); } }
(async () => {
  const b = await chromium.launch();
  for (const schema of ["light", "dark"]) {
    const m = await sessie(b, "medewerker", schema);
    await m.goto(B + "/"); await m.waitForTimeout(1200); await meet(m, schema + " site start");
    await m.goto(B + "/artikel/" + (process.env.KB_ARTIKEL || "1") + "/x"); await m.waitForTimeout(1200); await meet(m, schema + " site artikel");
    await m.fill("#q", "rappel"); await m.waitForTimeout(1200); await meet(m, schema + " site zoeken");
    const rv = await sessie(b, "reviewer", schema);
    await rv.goto(B + "/review/"); await rv.waitForTimeout(800); await meet(rv, schema + " reviewlijst");
    await rv.goto(B + `/review/${INZ}/`); await rv.waitForTimeout(1200); await meet(rv, schema + " reviewpagina met opmerking");
  }
  const r = await sessie(b, "redacteur", "light");
  await r.goto(B + "/beheer/"); await r.waitForTimeout(800); await meet(r, "werkplek");
  await r.goto(B + "/beheer/?bak=algemeen"); await r.waitForTimeout(800); await meet(r, "werkbak algemeen");
  await r.goto(B + "/beheer/kennisbank/artikel/"); await r.waitForTimeout(800); await meet(r, "beheer artikellijst");
  await r.goto(B + "/beheer/kennisbank/artikel/importeren-word/"); await r.waitForTimeout(800); await meet(r, "artikel uit Word");
  await r.goto(B + "/beheer/kennisbank/artikel/add/"); await r.waitForTimeout(1500); await dichtVensters(r); await meet(r, "nieuw artikel");
  await r.goto(B + "/beheer/kennisbank/bericht/add/"); await r.waitForTimeout(1500); await dichtVensters(r); await meet(r, "nieuw nieuwsbericht");
  await r.goto(B + "/beheer/kennisbank/artikel/" + (process.env.KB_ARTIKEL || "1") + "/change/"); await r.waitForTimeout(1500); await dichtVensters(r); await meet(r, "bewerkscherm (geen voorstellen)");
  if (ART) await r.goto(B + `/beheer/kennisbank/artikel/${ART}/change/?voorstel=${VS}`); await r.waitForTimeout(1800); await dichtVensters(r); await meet(r, "bewerkscherm met lade open (ter inzage)");
  await r.click(".kb-afronden-knop"); await r.waitForTimeout(300); await meet(r, "venster Afronden");
  await r.keyboard.press("Escape");
  await r.click("[data-kb-paneel='eig']"); await r.waitForTimeout(300); await meet(r, "paneel Eigenschappen");
  await b.close();
  process.exit(fouten ? 1 : 0);
})();
