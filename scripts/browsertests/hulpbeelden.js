/* Maakt de schermafbeeldingen voor de hulpartikelen (1.37.0).
 *
 * Draait tegen de testserver met `--voor-hulp`: dezelfde vaste testgegevens als de browsertests, met gewone
 * titels en zonder vulling. Elk beeld heeft een vaste naam; het hulpartikel verwijst ernaar met
 * [[beeld:naam|bijschrift]]. Gebruik: scripts/browsertests/hulpbeelden.sh (die start de server en verkleint de
 * bestanden). Mislukt een beeld, dan blijft het vorige bestand staan en eindigt het script met een fout.
 */
const path = require("path");
const g = require("./gemeen");
const B = g.B, o = g.OPZET;
const UIT = process.env.KB_HULPBEELDEN || path.join(__dirname, "..", "..", "kennisbank", "static", "kennisbank", "hulp");
const BREED = 1240, HOOG = 760;
let fouten = 0;
const gemaakt = [];

(async () => {
  const browser = await g.start();
  const sessie = (wie) => g.sessie(browser, wie, { breedte: BREED, hoogte: HOOG });
  const med = await sessie("medewerker");
  const red = await sessie("redacteur");
  const rev = await sessie("reviewer");
  const beh = await sessie("beheerder");

  async function beeld(naam, p, voorbereiden, opties) {
    try {
      await voorbereiden();
      await p.waitForTimeout(500);
      const doel = (opties && opties.element) ? p.locator(opties.element).first() : p;
      await doel.screenshot({ path: path.join(UIT, naam + ".png"), animations: "disabled", ...(opties && opties.clip ? { clip: opties.clip } : {}) });
      gemaakt.push(naam); console.log("OK   " + naam);
    } catch (e) { fouten++; console.log("FOUT " + naam + " :: " + String(e.message || e).split("\n")[0]); }
  }
  const site = async (p, view) => { await p.goto(B + "/"); await p.locator("#q").waitFor(); if (view) await p.locator(`button[data-view='${view}']`).click(); };
  const venster = (p) => p.locator("dialog[open]").last();
  const bewerk = async (p, id) => { await p.goto(B + `/beheer/kennisbank/artikel/${id}/change/`); await p.locator(".ProseMirror").first().waitFor(); await g.dichtVensters(p); };

  // --- Medewerker ---------------------------------------------------------------------------------------
  await beeld("site-start", med, async () => { await site(med); });
  await beeld("zoeken", med, async () => { await site(med); await med.fill("#q", "rapel"); await med.locator(".zoekhulp").waitFor(); });
  await beeld("artikel", med, async () => { await med.goto(B + `/artikel/${o.demo.artikel}/${o.demo.slug}`); await med.locator("article h1, .article h1, main h1").first().waitFor(); });
  await beeld("onboarding", med, async () => {
    await med.goto(B + `/artikel/${o.demo.artikel}/${o.demo.slug}`); await med.locator("details.sec").first().waitFor();
    // Vaste beginstand: Onboarding aan (af te lezen aan de pagina zelf) en alle secties open.
    if (!(await med.evaluate(() => document.body.classList.contains("onboarding")))) await med.locator("#onbToggle").click();
    await med.waitForFunction(() => document.body.classList.contains("onboarding"));
    await med.evaluate(() => document.querySelectorAll("details.sec").forEach((d) => { d.open = true; }));
    await med.locator("div.onboarding").first().waitFor({ state: "visible" });
    await med.locator("div.onboarding").first().evaluate((e) => e.scrollIntoView({ block: "center" }));
  });
  if (await med.evaluate(() => document.body.classList.contains("onboarding"))) await med.locator("#onbToggle").click().catch(() => {});
  await beeld("gewijzigd", med, async () => { await site(med, "gewijzigd"); });
  await beeld("nieuws", med, async () => { await site(med, "nieuws"); });
  await beeld("voorstel-indienen", med, async () => {
    await med.goto(B + `/artikel/${o.rustig.artikel}/${o.rustig.slug}`); await med.locator("#propBtn").click(); await med.locator("#propText").waitFor();
    await med.fill("#propText", "De termijn van twee weken klopt niet meer. Sinds 1 november is het drie weken.");
  });
  await med.locator("#propCancel").click().catch(() => {});
  await beeld("voorstellen", med, async () => { await site(med, "voorstellen"); });
  await beeld("assistent", med, async () => {
    await site(med); await med.locator("#chatBtn").click(); await med.fill("#chatIn", "Binnen welke termijn verstuur ik een rappel?");
    await med.keyboard.press("Enter"); await med.waitForTimeout(3500);
  });

  // --- Reviewer -----------------------------------------------------------------------------------------
  await beeld("review-lijst", rev, async () => { await rev.goto(B + "/review/"); await rev.locator("main h1").waitFor(); });
  await beeld("review-stuk", rev, async () => { await rev.goto(B + "/review/"); await Promise.all([rev.waitForNavigation(), rev.locator("main a", { hasText: "Monstername" }).first().click()]); await rev.waitForTimeout(900); });
  await beeld("review-afronden", rev, async () => { await rev.locator("#rv-afronden-knop").click(); await rev.locator("#rv-afronden[open]").waitFor(); });
  await rev.keyboard.press("Escape").catch(() => {});

  // --- Redacteur ----------------------------------------------------------------------------------------
  await beeld("werkplek", red, async () => { await red.goto(B + `/beheer/?bak=cluster-${o.cluster}`); await red.locator("#kb-inhoud-titel").waitFor(); });
  await beeld("review-standen", red, async () => { await red.goto(B + "/beheer/?bak=ter_inzage"); await red.locator("#kb-inhoud-titel").waitFor(); });
  await beeld("bewerkscherm", red, async () => { await bewerk(red, o.rustig.artikel); });
  await beeld("afronden", red, async () => { await red.click(".kb-afronden-knop"); await venster(red).locator(".kb-afronden-keuze").first().waitFor(); });
  await red.keyboard.press("Escape").catch(() => {});
  await beeld("weten", red, async () => {
    await bewerk(red, o.spoed.artikel); await red.click(".kb-afronden-knop");
    await venster(red).locator(".kb-afronden-keuze", { hasText: "Publiceren" }).first().click();
    await venster(red).locator("#kb-weten-ja").waitFor();
  });
  await red.keyboard.press("Escape").catch(() => {});
  await beeld("lade", red, async () => {
    await red.goto(B + `/beheer/kennisbank/artikel/${o.lade.artikel}/change/?voorstel=${o.lade.steun}`);
    await red.locator(".ProseMirror").first().waitFor(); await g.dichtVensters(red); await red.locator(".kb-vk-open").first().waitFor();
  });
  await beeld("live-keuze", red, async () => {
    await red.goto(B + `/artikel/${o.spoed.artikel}/${o.spoed.slug}`); await red.locator("#editBtn, button:has-text('Bewerken')").first().click();
    await red.locator("dialog.bewerk-keuze[open]").waitFor();
  });
  await red.keyboard.press("Escape").catch(() => {});
  await beeld("live-paneel", red, async () => {
    await bewerk(red, o.live.artikel); await red.locator("#kb-live-knop").click(); await red.locator("#kb-live-lijf .kb-live-uitleg").first().waitFor();
    await red.click("#kb-live-volgende");
  });
  await beeld("nieuwsbericht", red, async () => {
    await red.goto(B + "/beheer/kennisbank/bericht/"); await Promise.all([red.waitForNavigation(), red.locator("#result_list a[href*='/change/']").first().click()]);
    await red.locator(".ProseMirror").first().waitFor(); await g.dichtVensters(red);
  });
  // Eerst iets zoeken dat er niet is, zodat de knop Synoniem maken in beeld komt.
  await site(med); await med.fill("#q", "aanschrijving"); await med.keyboard.press("Enter"); await med.waitForTimeout(900);
  await med.fill("#q", "herinnering sturen"); await med.keyboard.press("Enter"); await med.waitForTimeout(900);
  await beeld("statistieken", red, async () => { await red.goto(B + "/statistieken"); await red.locator("h1", { hasText: "Gebruiksstatistieken" }).waitFor(); await red.locator("a", { hasText: "Synoniem maken" }).first().scrollIntoViewIfNeeded(); });
  await beeld("synoniem", red, async () => {
    await red.goto(B + "/beheer/kennisbank/synoniem/"); await Promise.all([red.waitForNavigation(), red.locator("#result_list a[href*='/change/']").first().click()]); await red.locator("#id_woord").waitFor();
  });

  // --- Functioneel beheerder ----------------------------------------------------------------------------
  await beeld("alle-onderdelen", beh, async () => { await beh.goto(B + "/beheer/"); await beh.locator(".kb-beheer-seintje").first().waitFor(); });
  await beeld("omgeving", beh, async () => { await beh.goto(B + "/beheer/kennisbank/omgeving/"); await Promise.all([beh.waitForNavigation(), beh.locator("#result_list a[href*='/change/']").first().click()]); await beh.locator("#id_naam").waitFor(); });
  await beeld("reviewteam", beh, async () => { await beh.goto(B + "/beheer/kennisbank/reviewteam/"); await Promise.all([beh.waitForNavigation(), beh.locator("#result_list a[href*='/change/']").first().click()]); await beh.locator("#id_naam").waitFor(); });
  await beeld("statuspagina", beh, async () => { await beh.goto(B + "/beheer/kennisbank/systeemstand/"); await beh.waitForTimeout(600); });
  await beeld("hulpartikelen", beh, async () => { await beh.goto(B + "/beheer/kennisbank/hulpartikel/"); await beh.locator("#result_list").waitFor(); });

  await browser.close();
  console.log(`${gemaakt.length} schermafbeeldingen gemaakt, ${fouten} mislukt.`);
  process.exit(fouten ? 1 : 0);
})().catch((e) => { console.log("FOUT onverwacht :: " + (e.stack || e)); process.exit(1); });
