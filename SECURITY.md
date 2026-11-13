# Beveiligingsproblemen melden

Meld een (vermoeden van een) kwetsbaarheid niet via een openbaar issue, maar bij de beheerorganisatie van deze applicatie via het CERT- of security-meldpunt van de organisatie. Vermeld de versie (zie CHANGELOG) en hoe het probleem te reproduceren is.

Ondersteunde versie: de laatste release in de CHANGELOG; oudere versies krijgen geen aparte fixes. Elke release heeft sinds 1.32.0 een tag (`v1.32.0`).

Afhankelijkheden worden in de CI-pipeline gecontroleerd met `pip-audit`. Een SBOM staat in `sbom.cdx.json`; daarin staan de Python-pakketten en elk pakket uit de meegeleverde editor (Tiptap en ProseMirror). De editor is één gebundeld bestand; een kwetsbaarheid in een van die pakketten vraagt een nieuwe bundel (zie `frontend/README.md`).
