// Toegankelijkheid: meet de schermen met axe-core (WCAG 2.0/2.1 A en AA), de site en de review in licht én donker.
//
// Draait tegen de server van `manage.py kennisbank_browsertest`, vóór rook.js (dat de testgegevens wijzigt).
// Het script stopt met code 1 als er een overtreding is. Zie README.md.
const g = require("./gemeen");
const { B, OPZET: o, meet, stap } = g;

(async () => {
  const browser = await g.start();
  const sessie = (wie, schema) => g.sessie(browser, wie, { schema, bypassCSP: true, breedte: 1280, hoogte: 900 });

  for (const schema of ["light", "dark"]) {
    const naam = schema === "light" ? "licht" : "donker";
    const m = await sessie("medewerker", schema);
    await stap(`site (${naam})`, m, async () => {
      await m.goto(B + "/"); await m.locator("#q").waitFor(); await m.waitForTimeout(800); await meet(m, `${naam}: site start`);
      await m.goto(B + `/artikel/${o.rustig.artikel}/${o.rustig.slug}`); await m.locator("h1").first().waitFor(); await m.waitForTimeout(800); await meet(m, `${naam}: site artikel`);
      await m.locator("#propBtn").click(); await m.locator("#propText").waitFor(); await meet(m, `${naam}: site venster verbetervoorstel`);
      await m.locator("#propCancel").click();
      await m.goto(B + `/artikel/${o.demo.artikel}/${o.demo.slug}`); await m.locator("h1").first().waitFor(); await m.waitForTimeout(800); await meet(m, `${naam}: site artikel met tags en wijzigingsmelding`);
      await m.locator("#propBtn").click(); await m.locator("#dubbel").waitFor(); await meet(m, `${naam}: site venster er ligt al een voorstel`);
      await m.keyboard.press("Escape");
      await m.fill("#q", "rappel"); await m.waitForTimeout(1200); await meet(m, `${naam}: site zoeken`);
      await m.locator("button[data-view='nieuws']").click(); await m.waitForTimeout(800); await meet(m, `${naam}: site nieuws`);
      await m.locator("button[data-view='voorstellen']").click(); await m.waitForTimeout(800); await meet(m, `${naam}: site verbetervoorstellen`);
    });
    const rv = await sessie("reviewer", schema);
    await stap(`review (${naam})`, rv, async () => {
      await rv.goto(B + "/review/"); await rv.waitForTimeout(600); await meet(rv, `${naam}: reviewlijst`);
      await rv.goto(B + `/review/${o.inzage.inzage}/`); await rv.locator("#rv-verschil").waitFor(); await rv.waitForTimeout(900); await meet(rv, `${naam}: reviewpagina met opmerking`);
      await rv.locator("#rv-alg-knop").click(); await rv.waitForTimeout(300); await meet(rv, `${naam}: reviewpagina, nieuwe opmerking`);
      await rv.locator("#rv-afronden-knop").click(); await rv.waitForTimeout(300); await meet(rv, `${naam}: reviewpagina, venster Afronden`);
      await rv.keyboard.press("Escape");
    });
    await m.context().close(); await rv.context().close();
  }

  const r = await sessie("redacteur", "light");
  await stap("beheer: werkplek en lijsten", r, async () => {
    await r.goto(B + "/beheer/"); await r.waitForTimeout(600); await meet(r, "werkplek");
    await r.goto(B + "/beheer/?bak=algemeen"); await r.waitForTimeout(600); await meet(r, "werkbak Algemeen");
    await r.goto(B + "/beheer/"); await r.locator("a.kb-bakregel", { hasText: "Nat beheer" }).first().click(); await r.waitForTimeout(600); await meet(r, "werkbak van een cluster, met voorstellen");
    await r.goto(B + "/beheer/?bak=afgehandeld"); await r.waitForTimeout(600); await meet(r, "werkbak Afgehandeld");
    await r.goto(B + "/beheer/kennisbank/artikel/"); await r.waitForTimeout(600); await meet(r, "artikellijst");
    await r.goto(B + "/beheer/kennisbank/artikel/importeren-word/"); await r.waitForTimeout(600); await meet(r, "Artikel uit Word");
    await r.goto(B + `/beheer/kennisbank/artikel/${o.rustig.artikel}/history/`); await r.waitForTimeout(600); await meet(r, "geschiedenis van een artikel");
  });
  await stap("beheer: bewerkscherm", r, async () => {
    await r.goto(B + "/beheer/kennisbank/artikel/add/"); await r.locator(".ProseMirror").first().waitFor(); await r.waitForTimeout(600); await g.dichtVensters(r); await meet(r, "nieuw artikel");
    await r.goto(B + "/beheer/kennisbank/bericht/add/"); await r.locator(".ProseMirror").first().waitFor(); await r.waitForTimeout(600); await g.dichtVensters(r); await meet(r, "nieuw nieuwsbericht");
    await g.bewerk(r, o.rustig.artikel); await meet(r, "bewerkscherm zonder voorstellen");
    await r.click(".kb-afronden-knop"); await r.waitForTimeout(300); await meet(r, "venster Afronden");
    await r.keyboard.press("Escape");
    await r.click("[data-kb-paneel='eig']"); await r.waitForTimeout(300); await meet(r, "paneel Eigenschappen");
    await r.keyboard.press("Escape");
    await r.click("[data-kb-paneel='gesch']"); await r.waitForTimeout(300); await meet(r, "paneel Geschiedenis");
    await r.keyboard.press("Escape");
    await g.bewerk(r, o.spoed.artikel); await r.locator(".kb-meer summary").click(); await r.waitForTimeout(200); await meet(r, "bewerkscherm met conceptversie en menu Meer");
    await g.bewerk(r, o.inzage.artikel, `?voorstel=${o.inzage.voorstel}`); await meet(r, "bewerkscherm ter inzage, met lade en opmerking");
  });
  await stap("beheer: de lade en haar vensters", r, async () => {
    await g.bewerk(r, o.lade.artikel, `?voorstel=${o.lade.steun}`); await meet(r, "lade open");
    await r.locator(`[data-kb-focus="steun-${o.lade.steun}"]`).click(); await meet(r, "lade met de steun uitgeklapt");
    await r.locator(`[data-kb-focus="vwk-${o.lade.steun}"]`).click(); await r.waitForTimeout(300); await meet(r, "venster De tekst staat nog in het artikel");
    await r.locator("dialog[open] button", { hasText: "Ja, het is verwerkt" }).click(); await r.waitForTimeout(400); await meet(r, "venster Afhandelen als verwerkt");
    await r.keyboard.press("Escape");
    await r.locator(`[data-kb-focus="afw-${o.lade.steun}"]`).click(); await r.waitForTimeout(300); await meet(r, "venster Voorstel afwijzen");
    await r.keyboard.press("Escape");
    await r.locator(`[data-kb-focus="dub-${o.lade.steun}"]`).click(); await r.waitForTimeout(300); await meet(r, "venster Dubbel voorstel");
    await r.keyboard.press("Escape");
  });

  await browser.close();
  g.klaar();
})().catch((e) => { console.log("FOUT onverwacht :: " + (e.stack || e)); process.exit(1); });
