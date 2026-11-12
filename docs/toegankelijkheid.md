# Toegankelijkheid

Doel: **WCAG 2.1 niveau AA**, de norm uit het Besluit digitale toegankelijkheid overheid (EN 301 549).

## Geautomatiseerde test

Getest met axe-core 4.10 (regels `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`) in Chromium, op de draaiende container, bij oplevering van versie 1.2.0:

| Scherm | Licht | Donker |
|---|---|---|
| Inloggen | geen overtredingen | – |
| Artikellijst | geen overtredingen | geen overtredingen |
| Artikel met onboarding-uitleg open | geen overtredingen | geen overtredingen |
| Assistent met antwoord | geen overtredingen | geen overtredingen |
| Venster verbetervoorstel | geen overtredingen | geen overtredingen |
| Verbetervoorstellen (redacteur) | geen overtredingen | geen overtredingen |
| Statistieken | geen overtredingen | geen overtredingen |
| Ingebed bij zaaktype | geen overtredingen | geen overtredingen |
| Artikel op telefoonformaat (390 px) | geen overtredingen | – |
| Artikel met tabel en koppen uit Word | geen overtredingen | geen overtredingen |

Bij de eerste meting faalden twee kleuren uit het prototype op contrast (groen voor "proces" en oranje voor "in behandeling"). Die zijn aangepast naar een contrast van minimaal 4,5:1.

## Ingebouwd

- Semantische opbouw: kop, navigatie, `main`, koppen per niveau; skip-link "Naar de inhoud".
- Volledig met het toetsenbord te bedienen; zichtbare focus; `/` springt naar zoeken, `Esc` sluit vensters.
- Inklapbare secties met native `<details>`/`<summary>`, dus correct aangekondigd door schermlezers.
- Statusmeldingen (toasts, zoekresultaten, antwoorden van de assistent) via `aria-live`.
- Schakelaars met `aria-pressed`; menu en assistent met `aria-expanded`.
- Werkt bij 400% zoom en op 320 px breedte zonder horizontaal scrollen; respecteert `prefers-reduced-motion` en donkere modus.

## Nog te doen door de organisatie

Een geautomatiseerde test vindt ongeveer een derde van de mogelijke problemen. Laat vóór livegang een handmatige toets uitvoeren (met schermlezer en toetsenbord) en publiceer de toegankelijkheidsverklaring via het register van DigiToegankelijk. Het beheerscherm (`/beheer/`) is het standaard Django-beheer en valt onder dezelfde toets. Bekend punt daar: links in het kruimelpad zijn alleen door kleur te onderscheiden (axe `link-in-text-block`); dat zit in Django zelf. De editor van artikelen (Tiptap) heeft een werkbalk met echte knoppen en labels, de tekst is een tekstvak met `role="textbox"`; de + tussen blokken is alleen met de muis te bereiken, maar *+ Sectie* in de werkbalk doet hetzelfde met het toetsenbord. De editor van nieuwsberichten (Jodit) heeft een toetsenbord-bedienbare werkbalk. Geen van beide is apart met een schermlezer getoetst.
