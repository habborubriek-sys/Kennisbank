# Wijzigingen

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
