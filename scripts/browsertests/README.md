# Browsertests

Tests die de kennisbank in een echte browser bedienen. Ze draaien bij elke push in de CI (sinds 1.32.0) en
houden een push tegen als ze falen.

| Script | Wat het doet |
|---|---|
| `axe.js` | Meet 45 schermen en vensters met axe-core (WCAG 2.0/2.1 A en AA). De site en de reviewpagina's in licht én donker; het beheer in licht. |
| `rook.js` | Loopt de belangrijkste paden af, van begin tot eind: de lade, van voorstel tot gepubliceerde versie met review, spoedcorrectie, nieuw artikel, nieuwsbericht, kladversie, en de bediening met het toetsenbord. Bezoekt daarna elk beheerscherm. |
| `gemeen.js` | Gedeelde hulpfuncties: inloggen, een stap uitvoeren, meten met axe. |
| `draai.sh` | Start de testserver, draait `axe.js` en `rook.js`, en herhaalt één keer bij een fout. |

Een fout in een script van de pagina telt in beide tests als fout, en een melding van de Content-Security-Policy
ook. Zo betrapt elke stap ook een kapot script, of iets inline dat het beheer niet meer toestaat.

## Draaien

Nodig: PostgreSQL, de Python-pakketten van de kennisbank, Node.js 20 of nieuwer.

```sh
cd scripts/browsertests
npm ci                              # precies de versies uit package-lock.json
npx playwright install chromium     # eenmalig; of zet KB_CHROME=<pad naar Chrome of Chromium>
cd ../..
KB_DATABASE_URL=postgres://kennisbank:kennisbank@localhost:5432/kennisbank scripts/browsertests/draai.sh
```

Duur: ongeveer vier minuten. Bij een fout staat er een schermafdruk in `uitvoer/` en het logboek van de server
in `.server.log`; in de CI zijn die te downloaden bij de mislukte run.

## De testgegevens

`draai.sh` start `python manage.py kennisbank_browsertest`. Die opdracht:

- werkt alleen met `KB_DEMO_MODUS=aan`;
- maakt een **eigen database** (`browsertest_<naam>`), zodat je gewone database niet wordt aangeraakt;
- laadt de demo-inhoud en de demo-accounts (`medewerker`, `redacteur`, `reviewer`, `beheerder`, wachtwoord `demo`);
- zet daarbovenop altijd hetzelfde klaar:
  - *Browsertest lade*: vier open voorstellen, het eerste met vier steuners;
  - *Browsertest ter inzage*: een conceptversie die bij Team Water ligt, opgepakt, met een opmerking en een
    meegenomen voorstel;
  - *Browsertest stroom*: een kaal artikel waarop de hele stroom loopt;
  - *Browsertest spoed*: een artikel met een conceptversie die niet ter inzage ligt;
  - *Browsertest rustig*: een artikel waar niets mee gebeurt;
- schrijft de id's naar `.opzet.json`, waar de scripts ze lezen;
- start de ontwikkelserver op poort 8765.

`rook.js` wijzigt de gegevens (het publiceert, wijst af, gooit weg). Daarom draait `axe.js` eerst, en begint elke
ronde met een verse database.

Los draaien, bijvoorbeeld om één test te onderzoeken:

```sh
KB_DEMO_MODUS=aan KB_DEBUG=1 python manage.py kennisbank_browsertest --opzet scripts/browsertests/.opzet.json &
cd scripts/browsertests && node rook.js
```

## Een test toevoegen

- Een pad of knop: een nieuwe `stap(...)` in `rook.js`. Wacht op wat je verwacht te zien (`locator.waitFor()`),
  niet op tijd. Een stap die een uitzondering geeft, telt als fout en krijgt een schermafdruk; de stappen erna
  draaien door.
- Een scherm voor de toegankelijkheid: een regel `meet(pagina, "naam")` in `axe.js`.
- Andere testgegevens: `klaarzetten()` in `kennisbank/management/commands/kennisbank_browsertest.py`.

## Versies

Playwright en axe-core liggen vast in `package.json` en `package-lock.json`; een test bewaakt dat het exacte
versies zijn. Bijwerken: het versienummer in `package.json` aanpassen, `npm install`, en de tests draaien. Een
nieuwe versie van axe-core kan nieuwe regels meten en dus nieuwe overtredingen vinden.

## Wat hier niet in zit

- Een echte schermlezer. Daarvoor is `docs/nvda-testscript.md`, een handmatige test.
- Firefox en Safari. De tests draaien in Chromium, de basis van Edge.
- Inloggen via Entra ID; de tests gebruiken de demo-accounts.
