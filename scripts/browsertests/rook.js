// Rooktest: de belangrijkste paden van de kennisbank, van begin tot eind, in een echte browser.
//
// Draait tegen de server van `manage.py kennisbank_browsertest` (vaste testgegevens; zie README.md).
// Elke stap die mislukt telt als fout; een fout in een script van de pagina of een melding van de
// Content-Security-Policy ook. Het script stopt met code 1 als er iets fout is.
const g = require("./gemeen");
const { B, OPZET: o, ok, stap } = g;

const venster = (p) => p.locator("dialog[open]").last();
const vensterKnop = (p, tekst) => venster(p).locator("button", { hasText: tekst }).first();
const focus = (p) => p.evaluate(() => (document.activeElement && (document.activeElement.getAttribute("data-kb-focus") || document.activeElement.tagName)) || "");
const tekstVan = async (loc) => ((await loc.count()) ? (await loc.first().innerText()).replace(/\s+/g, " ").trim() : "");

// Afronden… → een keuze uit het venster.
async function afronden(p, keuze) {
  await p.click(".kb-afronden-knop");
  await venster(p).locator(".kb-afronden-keuze", { hasText: keuze }).first().click();
}

// Publiceren via Afronden; bij een gepubliceerd artikel volgt het venster "Wat is er gewijzigd?".
async function publiceer(p, opties) {
  opties = opties || {};
  await afronden(p, "Publiceren");
  const toel = p.locator("#kb-toel");
  await toel.waitFor({ timeout: 5000 });
  if (opties.klein) await venster(p).locator('input[type="checkbox"]').check();
  else await toel.fill(opties.toelichting || "Tekst aangepast voor de browsertest");
  await Promise.all([p.waitForNavigation(), vensterKnop(p, "Publiceren").click()]);
}

// Typ tekst aan het eind van de eerste alinea die `bevat` bevat.
async function typInAlinea(p, bevat, tekst) {
  await p.locator(".ProseMirror p", { hasText: bevat }).first().click();
  await p.keyboard.press("End");
  await p.keyboard.type(tekst);
  await p.waitForTimeout(500);
}

(async () => {
  const browser = await g.start();
  const red = await g.sessie(browser, "redacteur");
  const med = await g.sessie(browser, "medewerker");
  const rev = await g.sessie(browser, "reviewer");

  // --- 1. De lade ----------------------------------------------------------------------------------------
  await stap("lade: knoppen, steun en toetsenbord", red, async () => {
    await g.bewerk(red, o.lade.artikel, `?voorstel=${o.lade.steun}`);
    const knoppen = await red.locator(".kb-vk-open .kb-vk-af .kb-vk-knoppen button").allTextContents();
    ok(knoppen.join("|") === "Afhandelen|Afwijzen|Ontdubbelen", "drie knoppen in het blok Afhandelen zonder nieuwe versie", knoppen.join("|"));
    const maten = await red.locator(".kb-vk-open .kb-vk-af .kb-vk-knoppen button").evaluateAll((els) => els.map((e) => ({ top: Math.round(e.getBoundingClientRect().top), kap: e.scrollWidth > e.clientWidth + 1 })));
    ok(new Set(maten.map((m) => m.top)).size === 1 && maten.every((m) => !m.kap), "de knoppen staan op één regel en zijn niet afgekapt", JSON.stringify(maten));
    const steun = red.locator(`[data-kb-focus="steun-${o.lade.steun}"]`);
    ok(/ en 3 anderen steunen dit voorstel$/.test(await steun.textContent()), "steun als één regel", await steun.textContent());
    await steun.focus(); await red.keyboard.press("Enter");
    ok((await red.locator(".kb-vk-open .kb-vk-steuners li").count()) === 4, "steun uitgeklapt: vier namen");
    ok((await focus(red)) === `steun-${o.lade.steun}`, "focus blijft op de steunknop");
    await red.keyboard.press("Enter");
    ok((await red.locator(".kb-vk-open .kb-vk-steuners li").count()) === 0, "Minder tonen klapt weer in");
    // De lade dicht en open met het toetsenbord.
    await red.locator(".kb-lade-sluit").click();
    const lip = red.locator("#kb-lip, .kb-lip").first();
    await lip.focus(); await red.keyboard.press("Enter");
    await red.waitForTimeout(400);
    ok((await focus(red)) === "H2", "lade openen met Enter zet de focus op de kop");
    ok((await red.evaluate(() => getComputedStyle(document.activeElement).outlineStyle)) === "none", "de kop heeft geen rand");
    await red.keyboard.press("Escape");
    await red.waitForTimeout(300);
    ok(await red.locator(".kb-lade").evaluate((e) => e.inert || e.hasAttribute("inert") || e.getAttribute("aria-hidden") === "true"), "Escape sluit de lade");
  });

  await stap("lade: bericht en notitie", red, async () => {
    await g.bewerk(red, o.lade.artikel, `?voorstel=${o.lade.steun}`);
    const vak = red.locator(".kb-vk-open textarea").first();
    await vak.fill("We kijken ernaar; je hoort deze week meer.");
    await red.locator(`[data-kb-focus="stuur-${o.lade.steun}"]`).click();
    ok(/We kijken ernaar/.test(await venster(red).innerText()), "het venster toont het bericht voor het verstuurd wordt");
    await venster(red).locator("button.kb-venster-primair, button").filter({ hasText: /Versturen/ }).first().click();
    await red.locator(".kb-lade-toast", { hasText: "Bericht verstuurd" }).waitFor();
    ok(true, "bericht verstuurd");
    await red.locator(".kb-vk-open button", { hasText: "Notitie" }).first().click();
    await red.locator(".kb-vk-open textarea").first().fill("Gebeld met Toezicht.");
    await red.locator(`[data-kb-focus="bewaar-${o.lade.steun}"]`).click();
    await red.locator(".kb-vk-open", { hasText: "Gebeld met Toezicht." }).waitFor();
    ok(true, "interne notitie bewaard");
  });

  await stap("lade: Afhandelen, Afwijzen en Ontdubbelen", red, async () => {
    await g.bewerk(red, o.lade.artikel, `?voorstel=${o.lade.weg}`);
    // Afhandelen: het citaat staat niet meer in de tekst, dus meteen het venster met het bericht.
    await red.locator(`[data-kb-focus="vwk-${o.lade.weg}"]`).focus(); await red.keyboard.press("Enter");
    ok((await venster(red).locator("h2").textContent()) === "Afhandelen als verwerkt", "Afhandelen opent het venster met het bericht");
    ok(/verwerkt in versie 1/.test(await venster(red).locator("textarea").inputValue()), "voorgevuld bedankbericht");
    ok((await focus(red)) === "TEXTAREA", "focus in het tekstvak");
    await red.keyboard.press("Tab"); await red.keyboard.press("Tab"); await red.keyboard.press("Tab"); await red.keyboard.press("Tab");
    ok(await red.evaluate(() => !!document.activeElement.closest("dialog[open]")), "Tab blijft binnen het venster");
    await red.keyboard.press("Escape");
    ok((await red.locator("dialog[open]").count()) === 0 && (await focus(red)) === `vwk-${o.lade.weg}`, "Escape sluit het venster en zet de focus terug");
    await red.locator(`[data-kb-focus="vwk-${o.lade.weg}"]`).click();
    await vensterKnop(red, "Afhandelen en versturen").click();
    await red.locator(".kb-lade-toast", { hasText: "Afgehandeld als verwerkt in versie 1" }).waitFor();
    ok((await red.locator(".kb-vk").count()) === 3, "het voorstel is uit de lade");

    // Afhandelen bij een citaat dat er nog staat: eerst de vraag.
    await red.locator(`[data-kb-focus="rij-${o.lade.dubbel}"]`).click();
    await red.locator(`[data-kb-focus="vwk-${o.lade.dubbel}"]`).click();
    ok((await venster(red).locator("h2").textContent()) === "De tekst staat nog in het artikel", "staat het citaat er nog, dan eerst de vraag");
    ok((await red.evaluate(() => document.activeElement.textContent)) === "Annuleren", "focus op Annuleren");
    await red.keyboard.press("Enter");
    ok((await red.locator("dialog[open]").count()) === 0, "Enter = Annuleren");

    // Ontdubbelen.
    await red.locator(`[data-kb-focus="dub-${o.lade.dubbel}"]`).click();
    await venster(red).locator("select").selectOption(String(o.lade.steun));
    await vensterKnop(red, "Afsluiten en versturen").click();
    await red.locator(`[data-kb-focus="rij-${o.lade.dubbel}"]`).waitFor({ state: "detached" });
    ok((await red.locator(".kb-vk").count()) === 2, "ontdubbeld: het voorstel is uit de lade");

    // Afwijzen.
    await red.locator(`[data-kb-focus="rij-${o.lade.afwijzen}"]`).click();
    await red.locator(`[data-kb-focus="afw-${o.lade.afwijzen}"]`).click();
    await venster(red).locator("textarea").fill("Dank je wel. We nemen het niet over, omdat het artikel nog wordt gebruikt.");
    await vensterKnop(red, "Afwijzen en versturen").click();
    await red.locator(`[data-kb-focus="rij-${o.lade.afwijzen}"]`).waitFor({ state: "detached" });
    ok((await red.locator(".kb-vk").count()) === 1, "afgewezen: het voorstel is uit de lade");
    ok((await red.locator("#kb-lip-teller").textContent()) === "1", "de teller op het tabblad klopt");
  });

  await stap("lade: meenemen en publiceren als kleine correctie", red, async () => {
    await g.bewerk(red, o.lade.artikel, `?voorstel=${o.lade.steun}`);
    await red.locator(".ProseMirror p", { hasText: "twee weken" }).first().dblclick(); // een woord selecteren
    await red.locator(".ProseMirror p", { hasText: "twee weken" }).first().click();
    await red.keyboard.press("Home");
    for (let i = 0; i < "Stuur na twee".length; i++) await red.keyboard.press("ArrowRight");
    for (let i = 0; i < "twee".length; i++) await red.keyboard.press("Backspace");
    await red.keyboard.type("drie");
    await red.waitForTimeout(500);
    await red.locator(`[data-kb-focus="mee-${o.lade.steun}"]`).click();
    await red.locator(".kb-vk-open", { hasText: /aangepast ✓/i }).waitFor();
    ok(true, "de lade ziet dat de tekst is aangepast");
    await publiceer(red, { klein: true });
    ok(/voorstellen-afhandelen/.test(red.url()), "na publiceren als kleine correctie komt het afhandelscherm", red.url());
    ok(/verwerkt in versie 2/.test(await red.locator("textarea").first().inputValue()), "voorgevuld bericht met versie 2");
    await Promise.all([red.waitForNavigation(), red.locator('button[type="submit"], input[type="submit"]').filter({ hasText: /afhandelen/i }).first().click()]);
    ok(!/voorstellen-afhandelen/.test(red.url()), "afhandelen stuurt terug naar het artikel of de werkplek", red.url());
  });

  // --- 2. Van voorstel tot gepubliceerde versie, met review ----------------------------------------------
  let stroomVoorstel = 0;
  await stap("site: medewerker dient een verbetervoorstel in", med, async () => {
    await med.goto(B + `/artikel/${o.stroom.artikel}/browsertest-stroom`);
    await med.locator("#propBtn").click();
    await med.locator("#propText").fill("De coordinator heet tegenwoordig teamleider.");
    await med.locator('#propForm button[type="submit"]').click();
    await med.locator("text=Verbetervoorstel ingediend").first().waitFor();
    ok(true, "voorstel ingediend, met bevestiging");
  });

  await stap("editor: bewerken, meenemen en opslaan als concept", red, async () => {
    await red.goto(B + "/beheer/");
    await red.locator("a.kb-bakregel", { hasText: "Nat beheer" }).first().click(); // de bak van het cluster
    await red.locator("a, tr", { hasText: "De coordinator heet tegenwoordig teamleider" }).first().waitFor();
    ok(true, "het nieuwe voorstel staat in de werkvoorraad");
    await g.bewerk(red, o.stroom.artikel);
    stroomVoorstel = Number(((await red.locator("[data-kb-focus^='rij-']").first().getAttribute("data-kb-focus")) || "").replace("rij-", ""));
    await g.bewerk(red, o.stroom.artikel, `?voorstel=${stroomVoorstel}`); // opent de lade op dit voorstel
    await typInAlinea(red, "overleg dan met de coordinator", " De coordinator is de teamleider.");
    await red.locator(`[data-kb-focus="mee-${stroomVoorstel}"]`).click();
    await Promise.all([red.waitForNavigation(), afronden(red, "Opslaan als concept")]);
    await red.locator(".ProseMirror").first().waitFor();
    ok(/De coordinator is de teamleider/.test(await red.locator(".ProseMirror").first().innerText()), "de conceptversie bevat de nieuwe tekst");
    await med.goto(B + `/artikel/${o.stroom.artikel}/browsertest-stroom`);
    await med.locator("article, main").first().waitFor();
    await med.waitForTimeout(800);
    ok(!/De coordinator is de teamleider/.test(await med.locator("body").innerText()), "medewerkers zien de conceptversie niet");
  });

  await stap("editor: ter inzage geven", red, async () => {
    await g.bewerk(red, o.stroom.artikel);
    await afronden(red, "Ter inzage geven");
    ok(await venster(red).locator('input[type="checkbox"]').first().isChecked(), "het team van het cluster staat voorgevuld");
    await Promise.all([red.waitForNavigation(), vensterKnop(red, "Opslaan en ter inzage geven").click()]);
    await red.waitForLoadState("networkidle");
    ok(/ter inzage/i.test(await tekstVan(red.locator(".kb-balk"))), "de balk zegt dat de versie ter inzage ligt", await tekstVan(red.locator(".kb-balk")));
    await red.click(".kb-afronden-knop");
    const keuzes = await venster(red).locator(".kb-afronden-keuze strong").allTextContents();
    ok(keuzes.join("|") === "Terugroepen|Afbreken", "op slot: alleen Terugroepen en Afbreken", keuzes.join("|"));
    await red.keyboard.press("Escape");
  });

  await stap("review: oppakken, opmerking plaatsen en teruggeven", rev, async () => {
    await rev.goto(B + "/review/");
    await rev.locator("a", { hasText: "Browsertest stroom" }).first().click();
    await rev.locator("#rv-verschil").waitFor();
    ok(/De coordinator is de teamleider/.test(await rev.locator("#rv-verschil ins").allTextContents().then((t) => t.join(" "))), "de nieuwe tekst staat als nieuw gemarkeerd");
    ok(/teamleider/.test(await tekstVan(rev.locator(".rv-voorstellen"))), "de reviewer ziet het meegenomen voorstel");
    ok(!/Demo Medewerker/.test(await rev.locator("body").innerText()), "zonder de naam van de indiener");
    await Promise.all([rev.waitForNavigation(), rev.locator('button[value="oppakken"]').click()]);
    await rev.locator("#rv-alg-knop").click();
    await rev.locator("#rv-tekst").fill("Graag ook de naam van het team erbij.");
    await rev.locator('#rv-nieuw button[value="opmerking"]').click();
    await rev.locator("#rv-kaarten > *", { hasText: "Graag ook de naam van het team erbij." }).first().waitFor();
    ok(true, "opmerking geplaatst zonder de pagina te herladen");
    await rev.locator("#rv-afronden-knop").click();
    ok(await rev.evaluate(() => !!document.activeElement.closest("dialog[open]")), "het venster Afronden heeft de focus");
    await Promise.all([rev.waitForNavigation(), rev.locator("#rv-keuze-terug").click()]);
    ok(/review\/?$/.test(new URL(rev.url()).pathname) || /Teruggegeven/i.test(await rev.locator("body").innerText()), "teruggegeven", rev.url());
  });

  await stap("editor: opmerking lezen, publiceren en voorstel afhandelen", red, async () => {
    await g.bewerk(red, o.stroom.artikel);
    ok(/Opmerkingen \(1\)/.test(await tekstVan(red.locator(".kb-balk-knoppen"))), "de redacteur ziet dat er een opmerking is", await tekstVan(red.locator(".kb-balk-knoppen")));
    ok(/Graag ook de naam van het team erbij/.test(await red.locator("body").innerText()), "de opmerking staat in de marge");
    await typInAlinea(red, "De coordinator is de teamleider", " Dat is team Nat beheer.");
    await publiceer(red, { toelichting: "De coordinator heet nu teamleider" });
    ok(/voorstellen-afhandelen/.test(red.url()), "na publiceren volgt het afhandelscherm", red.url());
    await Promise.all([red.waitForNavigation(), red.locator('button[type="submit"], input[type="submit"]').filter({ hasText: /afhandelen/i }).first().click()]);
    await med.goto(B + `/artikel/${o.stroom.artikel}/browsertest-stroom`);
    await med.locator("text=Dat is team Nat beheer").first().waitFor({ state: "attached" }); // de sectie staat ingeklapt
    ok(true, "medewerkers zien de nieuwe versie");
    ok(/De coordinator heet nu teamleider/.test(await med.locator("body").textContent()), "met de melding wat er is gewijzigd");
    await med.goto(B + "/#voorstellen");
    await med.locator("button[data-view='voorstellen']").click();
    await med.locator("text=verwerkt in versie 2").first().waitFor();
    ok(true, "de indiener ziet dat zijn voorstel is verwerkt");
  });

  // --- 3. Spoedcorrectie en conceptversie weggooien ------------------------------------------------------
  await stap("editor: spoedcorrectie naast een conceptversie", red, async () => {
    await g.bewerk(red, o.spoed.artikel);
    ok(/vier weken/.test(await red.locator(".ProseMirror").first().innerText()), "het scherm opent met de conceptversie");
    await red.locator(".kb-meer summary").click();
    await Promise.all([red.waitForNavigation(), red.locator(".kb-meer-menu a", { hasText: "Corrigeer de gepubliceerde versie" }).click()]);
    await red.locator(".ProseMirror").first().waitFor(); await red.waitForTimeout(500); await g.dichtVensters(red);
    ok(/twee weken/.test(await red.locator(".ProseMirror").first().innerText()), "de spoedcorrectie toont de gepubliceerde tekst");
    await typInAlinea(red, "Bel bij spoed", " Het nummer staat op intranet.");
    await publiceer(red, { klein: true });
    await med.goto(B + `/artikel/${o.spoed.artikel}/browsertest-spoed`);
    await med.locator("text=Het nummer staat op intranet").first().waitFor();
    ok(true, "de correctie staat meteen live");
    await g.bewerk(red, o.spoed.artikel);
    ok(/vier weken/.test(await red.locator(".ProseMirror").first().innerText()), "de conceptversie is er nog");
  });

  await stap("editor: conceptversie weggooien", red, async () => {
    await g.bewerk(red, o.spoed.artikel);
    await red.locator(".kb-meer summary").click();
    await red.locator(".kb-meer-menu button", { hasText: "Conceptversie weggooien" }).click();
    ok((await red.evaluate(() => document.activeElement.textContent)) === "Annuleren", "het venster Weggooien staat met de focus op Annuleren");
    await Promise.all([red.waitForNavigation(), vensterKnop(red, "Weggooien").click()]);
    await g.bewerk(red, o.spoed.artikel);
    ok(!/vier weken/.test(await red.locator(".ProseMirror").first().innerText()), "de conceptversie is weg");
    ok((await red.locator(".kb-meer").count()) === 0, "zonder conceptversie is er geen menu Meer");
  });

  // --- 4. Nieuw artikel, nieuwsbericht, kladversie -------------------------------------------------------
  await stap("editor: nieuw artikel schrijven en publiceren", red, async () => {
    await red.goto(B + "/beheer/kennisbank/artikel/add/");
    await red.locator(".ProseMirror").first().waitFor(); await red.waitForTimeout(500); await g.dichtVensters(red);
    await red.locator('[data-kb-plek="titel"] [contenteditable], [data-kb-plek="titel"] textarea, [data-kb-plek="titel"] input').first().fill("Browsertest nieuw artikel");
    await red.locator('[data-kb-plek="samenvatting"] [contenteditable], [data-kb-plek="samenvatting"] textarea, [data-kb-plek="samenvatting"] input').first().fill("Geschreven door de browsertest.");
    await red.locator(".ProseMirror p").first().click();
    await red.keyboard.type("Dit is de eerste alinea van het nieuwe artikel.");
    await Promise.all([red.waitForNavigation(), afronden(red, "Publiceren")]);
    await red.waitForLoadState("networkidle");
    await med.goto(B + "/");
    await med.fill("#q", "Browsertest nieuw artikel");
    await med.locator("a, button, h2, h3", { hasText: "Browsertest nieuw artikel" }).first().waitFor();
    ok(true, "het nieuwe artikel is te vinden op de site");
  });

  await stap("editor: nieuwsbericht schrijven en publiceren", red, async () => {
    await red.goto(B + "/beheer/kennisbank/bericht/add/");
    await red.locator(".ProseMirror").first().waitFor(); await red.waitForTimeout(500); await g.dichtVensters(red);
    await red.locator('[data-kb-plek="titel"] [contenteditable], [data-kb-plek="titel"] textarea, [data-kb-plek="titel"] input').first().fill("Browsertest nieuwsbericht");
    await red.locator(".ProseMirror p").first().click();
    await red.keyboard.type("Dit bericht komt van de browsertest.");
    await Promise.all([red.waitForNavigation(), afronden(red, "Publiceren")]);
    await med.goto(B + "/");
    await med.locator("button[data-view='nieuws']").click();
    await med.locator("text=Browsertest nieuwsbericht").first().waitFor();
    ok(true, "het nieuwsbericht staat op de nieuwspagina");
  });

  await stap("editor: kladversie, venster Afronden en Afbreken", red, async () => {
    await g.bewerk(red, o.rustig.artikel);
    await typInAlinea(red, "Stuur na twee weken", " Dit is niet opgeslagen.");
    await red.waitForTimeout(2500); // de kladversie wordt na een korte pauze bewaard
    await red.goto(B + "/beheer/"); // weglopen zonder opslaan (de browser vraagt het; Playwright laat het toe)
    await red.goto(B + `/beheer/kennisbank/artikel/${o.rustig.artikel}/change/`);
    await red.locator("dialog[open]", { hasText: "Verder gaan waar je gebleven was?" }).waitFor();
    ok((await red.evaluate(() => document.activeElement.textContent)) !== "Weggooien", "het kladversie-venster staat niet met de focus op Weggooien");
    await vensterKnop(red, "Verder gaan").click();
    await red.locator(".ProseMirror", { hasText: "Dit is niet opgeslagen." }).first().waitFor();
    ok(true, "de kladversie is terug");
    // Het venster Afronden met het toetsenbord.
    await red.locator(".kb-afronden-knop").focus(); await red.keyboard.press("Enter");
    for (let i = 0; i < 8; i++) await red.keyboard.press("Tab");
    ok(await red.evaluate(() => !!document.activeElement.closest("dialog[open]")), "Tab blijft binnen het venster Afronden");
    await red.keyboard.press("Escape");
    ok((await red.locator("dialog[open]").count()) === 0 && (await red.evaluate(() => document.activeElement.className)).includes("kb-afronden-knop"), "Escape sluit het venster en zet de focus terug op Afronden");
    await afronden(red, "Afbreken");
    await Promise.all([red.waitForNavigation(), vensterKnop(red, "Ja, afbreken").click()]);
    await g.bewerk(red, o.rustig.artikel);
    ok(!/Dit is niet opgeslagen/.test(await red.locator(".ProseMirror").first().innerText()), "na Afbreken is de kladversie weg");
  });

  await stap("editor: panelen en Bekijk als medewerker", red, async () => {
    await g.bewerk(red, o.rustig.artikel);
    await red.locator("[data-kb-paneel='eig']").click();
    ok((await red.locator("[data-kb-paneel='eig']").getAttribute("aria-expanded")) === "true", "paneel Eigenschappen open");
    await red.keyboard.press("Escape");
    ok((await red.locator("[data-kb-paneel='eig']").getAttribute("aria-expanded")) === "false", "Escape sluit het paneel");
    await red.locator("[data-kb-lees]").click();
    await red.locator("dialog[open]").waitFor();
    await red.keyboard.press("Escape");
    ok((await red.locator("dialog[open]").count()) === 0, "Bekijk als medewerker sluit met Escape");
    // Een tabel invoegen mag geen CSP-melding geven (stijlen in de editor).
    await red.locator(".ProseMirror p").first().click();
    await red.locator("button.kb-ae-tekst", { hasText: /^Tabel$/ }).first().click();
    await red.locator(".ProseMirror table").first().waitFor();
    ok(true, "een tabel invoegen werkt");
  });

  // --- 5. Elk beheerscherm laadt, zonder scriptfout of CSP-melding ---------------------------------------
  const beh = await g.sessie(browser, "beheerder");
  await stap("beheer: elk scherm laadt zonder scriptfout of CSP-melding", beh, async () => {
    const voor = g.aantalFouten();
    await beh.goto(B + "/beheer/?bak=alles");
    const paden = await beh.locator("a[href^='/beheer/']").evaluateAll((as) => [...new Set(as.map((a) => a.getAttribute("href")))].filter((h) => !/uitloggen|logout|\/delete\/|actie/.test(h)));
    paden.push("/beheer/", "/beheer/?bak=algemeen", "/beheer/?bak=afgehandeld", "/beheer/kennisbank/artikel/importeren-word/",
      `/beheer/kennisbank/artikel/${o.rustig.artikel}/history/`, `/beheer/kennisbank/artikel/${o.inzage.artikel}/change/?voorstel=${o.inzage.voorstel}`,
      "/beheer/auth/user/add/", "/beheer/password_change/");
    let bezocht = 0;
    for (const pad of [...new Set(paden)].slice(0, 60)) {
      const r = await beh.goto(B + pad);
      await beh.waitForTimeout(350);
      if (r.status() !== 200) ok(false, "scherm laadt: " + pad, "status " + r.status());
      const csp = r.headers()["content-security-policy"] || "";
      if (!/script-src 'self';/.test(csp) || !/style-src 'self';/.test(csp)) ok(false, "strenge CSP op " + pad, csp);
      bezocht++;
    }
    ok(bezocht >= 15, "minstens 15 beheerschermen bezocht", String(bezocht));
    ok(g.aantalFouten() === voor, `geen scriptfout of CSP-melding op ${bezocht} beheerschermen`);
  });

  await browser.close();
  g.klaar();
})().catch((e) => { console.log("FOUT onverwacht :: " + (e.stack || e)); process.exit(1); });
