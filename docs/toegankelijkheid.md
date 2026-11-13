# Toegankelijkheid

Doel: **WCAG 2.1 niveau AA**, de norm uit het Besluit digitale toegankelijkheid overheid (EN 301 549).

Bijgewerkt bij **versie 1.29.0** (13 november 2026), na de onafhankelijke toegankelijkheidsreview van 1.27.0.

## Geautomatiseerde meting

Gemeten met axe-core 4.10 (regels `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`) in Chromium, met
`scripts/browsertests/axe.js`, op versie 1.29.0 met de demo-inhoud.

| Scherm | Licht | Donker |
|---|---|---|
| Site: start | geen overtredingen | geen overtredingen |
| Site: artikel | geen overtredingen | geen overtredingen |
| Site: zoeken | geen overtredingen | geen overtredingen |
| Site: venster verbetervoorstel | geen overtredingen | geen overtredingen |
| Review: lijst | geen overtredingen | geen overtredingen |
| Review: stuk met opmerking in de tekst | geen overtredingen | geen overtredingen |
| Beheer: werkplek | geen overtredingen | – (beheer is altijd licht) |
| Beheer: werkbak | geen overtredingen | – |
| Beheer: artikellijst | geen overtredingen | – |
| Beheer: Artikel uit Word | geen overtredingen | – |
| Beheer: nieuw artikel | geen overtredingen | – |
| Beheer: nieuw nieuwsbericht | geen overtredingen | – |
| Beheer: bewerkscherm | geen overtredingen | – |
| Beheer: bewerkscherm met open lade en open voorstel | geen overtredingen | – |
| Beheer: venster Afronden | geen overtredingen | – |
| Beheer: paneel Eigenschappen | geen overtredingen | – |

Een geautomatiseerde test vindt ongeveer een derde van de mogelijke problemen. Daarom is ook het
toetsenbordgedrag nagelopen (hieronder) en is er een script voor een handmatige test met een schermlezer.

## Met het toetsenbord nagelopen (Playwright, Chromium)

- **Vensters in het beheer** (Afronden, Versturen, Afwijzen, Dubbel, Link, Overnemen, de kladversie):
  - het zijn echte dialogen (`<dialog>` met `showModal`), met een titel;
  - Tab blijft in het venster;
  - Escape sluit het;
  - daarna staat de focus weer op de knop waar je vandaan kwam.
- **Panelen** (Eigenschappen, Geschiedenis, Review):
  - de knop zegt open of dicht (`aria-expanded`);
  - openen zet de focus op de kop van het paneel;
  - Escape of ✕ zet hem terug op de knop.
- **Bekijk als medewerker**: een dialoog. Escape werkt ook vanuit het voorbeeld, en daarna staat de focus
  weer op de knop.
- **De lade met verbetervoorstellen:**
  - het tabblad staat vóór de lade;
  - een dichte lade is niet bereikbaar (`inert`);
  - openen zet de focus in de lade, Escape sluit hem;
  - na elke handeling (voorstel openen, meenemen, bericht of notitie) blijft de focus op hetzelfde element;
  - meldingen gaan via één vaste live-regio;
  - *Bericht* en *Notitie* zijn knoppen met `aria-pressed`;
  - *Toon in de tekst* zet de cursor op het citaat.
- **De werkbalk van de editor** is één Tab-stop. Met de pijltjes, Home en End ga je van knop naar knop.
  Knoppen die aan of uit staan, hebben `aria-pressed`.
- **Het sectiemenu (⋯ en +)** werkt met de pijltjes. Escape of Tab sluit het en zet de focus terug.
- **Reviewpagina** (sinds 1.30.0 opgezet als het bewerkscherm):
  - de knop *Opmerking* verschijnt ook na een selectie met Shift+pijltjes, en staat in de Tab-volgorde direct
    na de tekst;
  - in het kaartje voor een algemene opmerking kun je het stuk tekst ook typen of plakken ("Bij een bepaald stuk
    tekst?");
  - elke opmerking en elk verbetervoorstel heeft een knop *Toon in de tekst*; de focus gaat naar de markering;
  - Escape sluit het kaartje van een nieuwe opmerking (de getypte tekst blijft bewaard) en de vensters
    *Afronden*, *Weghalen* en *Bekijk als medewerker*; daarna staat de focus weer op de knop;
  - in het venster *Weghalen* staat de focus op *Annuleren*, zodat Enter niets weghaalt;
  - *Wijzigingen tonen* is een knop met `aria-pressed`.
- **Werkbak:**
  - het vinkje noemt het voorstel en het artikel;
  - de stip "nog niet geopend" en het rode aantal hebben een tekst voor de schermlezer;
  - de balk zegt hoeveel je hebt aangevinkt.

## Markeringen in de tekst

- **Verbetervoorstel:** blauw, met een **stippellijn** eronder en een **rond** nummer.
- **Opmerking van de review:** paars (sinds 1.31.1), met een **doorgetrokken lijn** eronder en een **vierkant** nummer.
- **Uitleg voor nieuwe collega's:** geel.

Behalve de kleur verschilt ook de vorm (WCAG 1.4.1, ook voor kleurenblinden). De nummers zijn voor het oog
(`aria-hidden`). De schermlezer hoort "begin verbetervoorstel 2" en "einde verbetervoorstel 2", of "begin
opmerking 1 van de review" en "einde opmerking 1", in plaats van een los getal midden in de zin. Alle nummers
hebben een contrast van minstens 4,5:1.

Op de reviewpagina tonen *ingevoegd* en *verwijderd* niet alleen kleur: ingevoegde tekst is vet met een
donkere streep eronder, verwijderde tekst doorgehaald (`<ins>`/`<del>`). Sinds 1.31.1 zijn opmerkingen van de review
paars (doorgetrokken lijn, vierkant nummer) en voorstellen blauw (stippellijn, rond nummer); ingevoegde tekst is
groen onderstreept. Opmerking en voorstel op dezelfde tekst zijn allebei zichtbaar. Na plaatsen, wijzigen of
weghalen van een opmerking leest een live-regio de melding voor en gaat de focus naar het kaartje.

## Ingebouwd op de site

- Semantische opbouw: kop, navigatie, `main`, koppen per niveau; skip-link "Naar de inhoud".
- Met het toetsenbord te bedienen; zichtbare focus; `/` springt naar zoeken; `Esc` sluit vensters.
- Inklapbare secties met native `<details>`/`<summary>`.
- Statusmeldingen (toasts, zoekresultaten, antwoorden van de assistent) via `aria-live`.
- Schakelaars met `aria-pressed`; menu en assistent met `aria-expanded`.
- Werkt bij 400% zoom en op 320 px breedte. Het bewerkscherm doet dat ook, met de lade over de volle breedte.
- **Licht of donker:** standaard volgt de site het apparaat. Met de knop **☾ Donker** draai je dat om. Het
  beheer is altijd licht.
- Respecteert `prefers-reduced-motion`.

## Wat nog niet is getoetst

- **Een echte schermlezer** (NVDA of JAWS) op Windows, en Firefox en Edge. Gebruik daarvoor
  [het NVDA-testscript](nvda-testscript.md).
- **Windows Hoog contrast** (forced colors). Waarschijnlijk vallen de achtergrondkleuren van markeringen,
  pillen en het lade-tabblad dan weg; de lijnen onder de markeringen blijven.
- **Een citaat kiezen op de site met het toetsenbord.** In leestekst kun je zonder cursornavigatie (F7) niet
  selecteren. Er is een weg zonder citaat (*dien een verbetervoorstel in*).
- De volledige standaardlijsten en -formulieren van Django (gebruikers, groepen). Bekend punt: links in het
  kruimelpad van die standaardpagina's zijn alleen door kleur te onderscheiden (axe `link-in-text-block`); dat
  zit in Django zelf.
- Tekstafstand (1.4.12), spraakbesturing en tablets.

## Nog te doen door de organisatie

Laat vóór livegang een handmatige toets uitvoeren met schermlezer en toetsenbord
([testscript](nvda-testscript.md)). Publiceer daarna de toegankelijkheidsverklaring via het register van
DigiToegankelijk.
