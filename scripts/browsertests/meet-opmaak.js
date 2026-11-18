/* Meet de opmaak op de belangrijkste schermen: lettertype, lettergroottes, hoogte van balk en knoppen.
 * Hulpmiddel bij 1.38.0 (opmaak compact en gelijk). Gebruik, met de testserver aan:
 *     KB_URL=http://127.0.0.1:8765 node meet-opmaak.js            (tabel)
 * Niet in draai.sh: de vaste controles staan in rook.js. */
const g = require("./gemeen");
const B = g.B, o = g.OPZET;
(async () => {
  const browser = await g.start();
  const red = await g.sessie(browser, "redacteur", { breedte: 1280, hoogte: 800 });
  const rev = await g.sessie(browser, "reviewer", { breedte: 1280, hoogte: 800 });
  const paden = [[red, "/"], [red, `/artikel/${o.demo.artikel}/${o.demo.slug}`], [red, "/hulp/"], [red, "/beheer/"], [red, "/beheer/?bak=alles"],
    [red, "/beheer/kennisbank/artikel/"], [red, "/beheer/kennisbank/synoniem/"], [red, `/beheer/kennisbank/artikel/${o.rustig.artikel}/change/`],
    [rev, "/review/"]];
  for (const [p, pad] of paden) {
    await p.goto(B + pad); await p.waitForTimeout(900); await g.dichtVensters(p).catch(() => {});
    const m = await p.evaluate(() => {
      const zicht = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== "hidden"; };
      const fam = (e) => getComputedStyle(e).fontFamily.split(",")[0].replace(/"/g, "");
      const groottes = {}, fams = {};
      const loop = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      while (loop.nextNode()) { const t = loop.currentNode; if (!t.textContent.trim()) continue; const e = t.parentElement; if (!e || !zicht(e)) continue;
        const s = getComputedStyle(e).fontSize; groottes[s] = (groottes[s] || 0) + t.textContent.trim().length; fams[fam(e)] = (fams[fam(e)] || 0) + 1; }
      const kn = {}; document.querySelectorAll("button, a.tb, a.button, input[type=submit], .button").forEach((e) => { if (!zicht(e)) return; const h = Math.round(e.getBoundingClientRect().height); kn[h] = (kn[h] || 0) + 1; });
      const kop = document.querySelector("header"); const h1 = [...document.querySelectorAll("h1")].find(zicht);
      const sorteer = (x) => Object.entries(x).sort((a, b) => b[1] - a[1]).map(([k, v]) => k + "×" + v).join(" ");
      return { balk: kop ? Math.round(kop.getBoundingClientRect().height) : "-", body: getComputedStyle(document.body).fontSize + " " + fam(document.body),
        h1: h1 ? getComputedStyle(h1).fontSize : "-", groottes: sorteer(groottes), fams: sorteer(fams), knoppen: sorteer(kn) };
    });
    console.log(`\n${pad}\n  balk ${m.balk} | body ${m.body} | h1 ${m.h1}\n  letters: ${m.groottes}\n  types: ${m.fams}\n  knophoogtes: ${m.knoppen}`);
  }
  await browser.close();
})();
