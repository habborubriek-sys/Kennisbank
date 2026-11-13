# Browsertests (toegankelijkheid)

Sinds 1.29.0 (ronde B). Ze draaien tegen een draaiende kennisbank met de demo-inhoud (`kennisbank_demo`) en de
demo-gebruikers (wachtwoord `demo`). In ronde D gaan ze de CI in; tot die tijd draai je ze met de hand.

```
npm install playwright axe-core
npx playwright install chromium
KB_URL=http://localhost:8000 KB_ARTIKEL=<id van een gepubliceerd artikel> \
  node axe.js <inzage-id met een opmerking> <artikel-id met open voorstellen> <voorstel-id>
```

`axe.js` meet met axe-core (WCAG 2.0/2.1 A en AA) de site en de reviewpagina's in licht én donker, en het beheer:
werkplek, werkbak, artikellijst, Artikel uit Word, nieuw artikel, nieuw nieuwsbericht, het bewerkscherm met open
lade, het venster Afronden en het paneel Eigenschappen. Het script stopt met code 1 als er iets fout is.

Het toetsenbordgedrag (vensters, lade, panelen, Bekijk als medewerker) staat in `docs/nvda-testscript.md` als
handmatige test, en is bij elke ronde met Playwright nagelopen.
