# Wijzigingen

## 1.4.1 – 2026-11-07

Reparaties naar aanleiding van een onafhankelijke code-review (beveiliging en overdraagbaarheid).

- **Health-checks** `/healthz` en `/readyz` werken nu ook als Kubernetes of Docker ze aanroept met het pod-IP als Host (vóór deze versie gaven ze 400 zodra `KB_ALLOWED_HOSTS` was ingevuld, waardoor de pod nooit *Ready* werd). De CI-rooktest controleert dit.
- **OIDC-modus**: wachtwoord-inloggen is volledig uit. Het inlogscherm van het beheer stuurt door naar de identity provider, `/inloggen/` bestaat niet en een wachtwoord in de database werkt nergens. Ingelogd zonder beheerrechten geeft een uitlegpagina.
- **Word-import** weigert documenten die uitgepakt groter zijn dan 20 MB of meer dan 2 MB tekst opleveren (bescherming tegen 'zip-bommen' die het geheugen vol laten lopen).
- **Editor** Jodit bijgewerkt van 4.2.47 naar 4.18.12 (bekende XSS-kwetsbaarheden verholpen). Meegeleverde browserbibliotheken staan in `vendor/componenten.json` en zitten in de SBOM (`scripts/maak_sbom.py`); een test bewaakt de versie.
- Opsommingen in de editor stonden te ver ingesprongen door een stijl van het Django-beheer.
- Logregels bij 4xx/5xx bevatten alleen methode en pad, geen querystring meer.
- API-schema en -documentatie (`/api/schema/`, `/api/docs/`) alleen voor ingelogde gebruikers.
- Eén versiebron (`kennisbank/__init__.py`); een test controleert dat alle bestanden dezelfde versie noemen. Documentatie op een paar punten gecorrigeerd (CSP in het beheer, aantal tests, API-pad).

## 1.4.0 – 2026-11-06

- Lege regels zijn altijd bewust en blijven staan, ook vlak voor of na een sectiekader. De typ-ruimte die de editor zelf rond kaders zet is nu zichtbaar gemarkeerd (*tussenruimte, wordt niet opgeslagen*) en is het enige dat bij opslaan vervalt.
- Word-import: lege regels blijven staan (meerdere achter elkaar worden er één); op de plek van een overgeslagen afbeelding staat *[afbeelding weggelaten]*.

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
