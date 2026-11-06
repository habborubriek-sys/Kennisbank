# Wijzigingen

## 1.3.3 – 2026-11-06

- Volledig scherm: titel en samenvatting staan links boven de editor (ook live in het voorbeeld), sleepbalk in het midden (verdeling wordt onthouden), bovenbalk in een eigen kleur
- Altijd een lege regel vóór, tussen en na sectiekaders om te kunnen typen; alleen lege regels direct tegen een kader aan vervallen bij opslaan. Lege regels tussen gewone alinea's blijven voortaan staan.

## 1.3.2 – 2026-11-06

- **Volledig scherm** vervangt de knop Voorbeeld: links de editor, rechts het voorbeeld dat live meeloopt terwijl je typt, met *Opslaan en doorgaan* en *Sluiten* (Esc)

## 1.3.1 – 2026-11-06

- Word-import bewust eenvoudig: alleen tekst en opmaak komen mee. Titel = bestandsnaam, samenvatting vul je in; secties en onboarding maak je in de editor. Het Word-sjabloon en de stijlen *Sectie*, *Einde sectie* en *Onboarding* zijn vervallen.

## 1.3.0 – 2026-11-06

- Secties zijn kaders: selecteer tekst, klik **Sectie**, typ de titel in de blauwe balk. Tekst buiten een kader is altijd zichtbaar, ook tussen en na secties. Nogmaals klikken haalt het kader weg. Onboarding-blokken staan zichtbaar binnen of buiten een kader.
- Word: de stijl *Sectie* begint een sectie; de nieuwe stijl *Einde sectie* sluit hem af (zit in het sjabloon)
- API: artikeldetail geeft `blokken[]` in leesvolgorde in plaats van `inleiding_html` + `secties[]`
- Importformaat versie 4; versie 3 wordt nog gelezen. Migratie zet bestaande artikelen en versiegeschiedenis automatisch om.

## 1.2.1 – 2026-11-06

- Knop **Voorbeeld** in de editor: toont het artikel zoals het gepubliceerd zou zijn, met de nog niet opgeslagen tekst
- Sectiekop: na het markeren springt de cursor naar een nieuwe regel eronder; weergave in de editor als `«Sectiekop» naam «Sectiekop»`
- Opsommingen tonen weer bolletjes en nummers in de editor

## 1.2.0 – 2026-11-06

- Een artikel is één tekst; secties maak je met de knop **Sectiekop** (of de Word-stijl *Sectie*). Gewone koppen maken geen sectie meer. Tekst vóór de eerste sectiekop is de inleiding.
- Links werken op het artikelnummer (`/artikel/412/naam`): blijvend bij hernoemen of verhuizen; dezelfde titel mag in meerdere omgevingen voorkomen. Oude links worden doorverwezen. Het veld *Slug* is uit het formulier verdwenen.
- API: artikelen op `id`; `url` en `id` in alle antwoorden; artikeldetail heeft `inleiding_html` en `secties[]`.
- Importformaat versie 3 (`inhoud` per artikel); versies 1 en 2 worden nog gelezen. Export per omgeving op (omgeving, slug).
- Migratie zet bestaande secties en versiegeschiedenis automatisch om.

## 1.1.0 – 2026-11-06

- Secties worden bewerkt in een opmaak-editor (koppen, vet, cursief, onderstreept, lijsten, tabellen, links); plakken uit Word wordt opgeschoond
- Onboarding-uitleg is nu een markering in de tekst (knop **Onboarding**), meerdere blokken per sectie mogelijk; het aparte veld is vervallen
- Importeren uit Word (.docx): koppen worden secties, de Word-stijl 'Onboarding' wordt herkend; Word-sjabloon meegeleverd
- Tags typ je als tekst bij het artikel; nieuwe tags worden automatisch aangemaakt
- Importformaat versie 2 (HTML); versie 1 (Markdown) wordt nog gelezen
- Migratie zet bestaande inhoud en versiegeschiedenis automatisch om

## 1.0.0 – 2026-11-05

Eerste versie, gebaseerd op het klikbare prototype en de functionele schets.

- Artikelen met inklapbare secties, onboarding-uitleg, zoeken en filters, favorieten, recent bezocht, delen
- Verbetervoorstellen op geselecteerde tekst, met behandeling en terugkoppeling
- Assistent op basis van de kennisbank; optioneel taalmodel (Azure OpenAI of OpenAI-compatibel)
- Omgevingen en rollen via groepen uit de identity provider (OIDC)
- Versiegeschiedenis van gepubliceerde artikelen
- Gebruiksstatistieken zonder persoonsgegevens
- Koppeling met het zaaksysteem: inbedden per zaaktype en API
- Import en export (JSON), bewaartermijnen, demomodus
- Container-image, Kubernetes-manifesten, CI-pipelines, SBOM
