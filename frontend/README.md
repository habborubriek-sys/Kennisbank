# frontend

Bouwt de editor van het bewerkscherm voor artikelen: Tiptap (MIT) met ProseMirror (MIT), gebundeld tot één
bestand zonder externe verzoeken.

Het resultaat staat in `kennisbank/static/kennisbank/vendor/tiptap/tiptap.min.js` en wordt meegecommit.
Deze map is dus alleen nodig om de bundel opnieuw te bouwen, bijvoorbeeld bij een beveiligingsupdate van
Tiptap. De container gebruikt hem niet (staat in `.dockerignore`).

```sh
cd frontend
npm ci          # precies de versies uit package-lock.json
npm run bouw    # schrijft vendor/tiptap/tiptap.min.js
```

Na een nieuwe versie:

1. Pas het versienummer aan in de banner in `package.json`, in `vendor/componenten.json` en in de SBOM (`python scripts/maak_sbom.py`).
2. Werk `vendor/tiptap/LICENSES.txt` bij.
3. Loop het bewerkscherm na in de browser.

`bundel.js` zegt welke onderdelen meegaan. De code die de editor zelf maakt (secties, onboarding, de + tussen blokken, opmerkingen), staat in `kennisbank/static/kennisbank/artikel-editor.js`.
