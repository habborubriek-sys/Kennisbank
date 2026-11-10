# Architectuur

## Componenten

```mermaid
flowchart LR
  subgraph Gebruiker
    B[Browser]
    Z[Zaaksysteem<br/>iframe of API]
  end
  subgraph Container["Kennisbank-container (stateless)"]
    G[gunicorn] --> D[Django-applicatie]
    D --> F[Frontend<br/>HTML + JS + CSS, statisch]
    D --> A[REST-API /api/v1]
    D --> AD[Beheerscherm /beheer]
    D --> S[Zoeken<br/>PostgreSQL full-text]
    D --> AS[Assistent]
  end
  B -->|https via ingress| G
  Z -->|https| G
  D --> P[(PostgreSQL)]
  D -.->|OIDC| IDP[Entra ID]
  AS -.->|optioneel| LLM[Taalmodel<br/>Azure OpenAI / eigen endpoint]
  D -.->|optioneel| SMTP[SMTP]
```

| Laag | Keuze | Waarom |
|---|---|---|
| Taal en framework | Python 3.12+, Django 5.2 LTS | Breed bekend, LTS met beveiligingsupdates tot april 2028, ingebouwd beheerscherm, rechten en migraties |
| API | Django REST Framework, OpenAPI 3 via drf-spectacular | Gestandaardiseerd, schema in [openapi.yaml](openapi.yaml) en op `/api/docs/` |
| Database | PostgreSQL | Ook de zoekmachine (Nederlandse woordstammen); geen aparte zoekdienst nodig. Een beheerde PostgreSQL werkt zonder aanpassing; wat een ánder databaseproduct zou kosten, staat in [installatie en beheer](installatie-en-beheer.md#een-andere-database-dan-postgresql) |
| Frontend | Eén HTML-pagina, vanilla JavaScript en CSS, zonder build-stap | Niets te compileren, geen npm-afhankelijkheden in productie, strenge CSP mogelijk |
| Editor in het beheer | Jodit 4 (MIT), lokaal meegeleverd | Word-achtige opmaak, tabellen, opschonen bij plakken uit Word; geen externe verbindingen |
| Word-import | mammoth (BSD) | Zet .docx om naar schone HTML (alleen tekst en opmaak; secties en onboarding maak je in de editor) |
| Webserver | gunicorn + WhiteNoise | Statische bestanden komen uit de container zelf; geen aparte webserver |
| Inloggen | OpenID Connect (mozilla-django-oidc) | Sluit aan op Entra ID; groepen bepalen de rollen |

## Datamodel

```mermaid
erDiagram
  OMGEVING ||--o{ ARTIKEL : bevat
  OMGEVING ||--o{ TOEGANG : "regelt"
  GROEP ||--o{ TOEGANG : "krijgt rol"
  ARTIKEL ||--o{ SECTIE : "afgeleid uit inhoud"
  ARTIKEL ||--o{ ARTIKELVERSIE : "onveranderlijke versies"
  ARTIKEL }o--o{ CLUSTER : ""
  ARTIKEL }o--o{ TAG : ""
  ARTIKEL }o--o{ ZAAKTYPE : "verschijnt bij"
  ARTIKEL ||--o{ VERBETERVOORSTEL : ""
  ARTIKEL ||--o{ WEERGAVETELLING : "per dag, anoniem"
  GEBRUIKER ||--o{ FAVORIET : ""
  GEBRUIKER ||--o{ RECENTBEZOCHT : "max 10"
  GEBRUIKER ||--o{ VERBETERVOORSTEL : "dient in"
  GEBRUIKER ||--o{ WIJZIGINGGEZIEN : "Ik snap het"
  GEBRUIKER ||--o{ FAVORIETENMAIL : "wachtrij"
  GEBRUIKER ||--o{ BEWERKCLAIM : "heeft open"
  OMGEVING ||--o{ BERICHT : "nieuws"
  BERICHT }o--o{ ARTIKEL : "gaat over"
```

- **Omgeving**: afgeschermd deel van de kennisbank (bijv. per afdeling). Hiermee kan de applicatie later ook buiten één afdeling worden gebruikt zonder dat artikelen door elkaar lopen.
- **Toegang**: groep uit de identity provider + rol (*lezer* of *redacteur*) per omgeving. Functioneel beheerders (`KB_BEHEERDERS_GROEPEN`) mogen alles.
- **Artikel**: één HTML-tekst (`inhoud`) uit de editor of uit een Word-import, bij opslaan én bij tonen opgeschoond met een allowlist (`inhoud.py`). Daarin zijn `<section class="sectie">` kaders met een `<h2 class="sectie-kop">` titel de in- en uitklapbare secties (tekst buiten een kader is altijd zichtbaar; kaders nesten niet), en `<div class="onboarding">` blokken uitleg voor nieuwe collega's, die de frontend alleen met de onboarding-schakelaar toont. `inhoud.blokken()` levert de tekst in leesvolgorde op als tekst- en sectieblokken.
- **Sectie** (sinds 1.8.1 géén rij meer voor lege vrije tekst: zo'n rij droeg de artikeltitel in zijn zoekdocument en won daarmee zoekopdrachten zonder iets te kunnen tonen; migratie 0011 ruimt bestaande op) is een *afgeleide* tabel: bij elke opslag opnieuw opgebouwd uit `inhoud` (`diensten.herbouw_secties`), zodat zoeken en de assistent per sectie kunnen werken. Volgorde 0 is alle vrije tekst samen.
- **Zoekdocumenten** (`Artikel.zoekvector`, `Sectie.zoekvector`, type `tsvector` met GIN-index) worden in dezelfde stap bijgewerkt. Zoeken is daardoor een indexopzoeking die meeschaalt met het aantal artikelen; titel en tags wegen het zwaarst, dan de samenvatting, dan de tekst.
- **Links** werken op het nummer van het artikel: `/artikel/412/melding-registreren`. De naam (`slug`) is alleen leesbaar. Hij is uniek *binnen een omgeving* — twee artikelen met dezelfde titel in dezelfde omgeving krijgen `-2`, `-3` enzovoort — maar bewust niet daarbuiten: twee omgevingen mogen dezelfde titel en dezelfde slug hebben, want anders zou een redacteur uit die `-2` kunnen afleiden dat er elders een artikel met dezelfde titel bestaat. Links van vóór versie 1.2 (`/artikel/<slug>`) worden doorverwezen; komen er meerdere artikelen in aanmerking, dan gaat de verwijzing naar het meest recent gewijzigde dat de bezoeker mag lezen.
- **Artikelversie**: elke wijziging van een gepubliceerd artikel levert een onveranderlijke momentopname op, met wie, wanneer en waarom. Zo is altijd te reconstrueren welke instructie op welk moment gold. De vlag `kleine_correctie` (typfout, opmaak) zorgt dat zo'n versie geen melding of e-mail oplevert; versie 1 (de publicatie zelf) telt ook niet als wijziging.
- **WijzigingGezien**: per gebruiker en artikel het versienummer tot waar de wijzigingsmelding is afgevinkt. `diensten.wijzigingen_voor()` bepaalt per artikel de openstaande melding: de hoogste inhoudelijke versie > 1, gepubliceerd ná de eerste inlog van de gebruiker (`date_joined`) en hoger dan het afgevinkte nummer.
- **FavorietenMail**: wachtrij voor de e-mail aan wie het artikel als favoriet heeft; `diensten.verstuur_favorietenmail()` bundelt per ontvanger (zie `KB_FAVORIETEN_MAIL`).
- **BewerkClaim**: wie heeft dit artikel nu in het bewerkscherm open. Een zacht slot: het bewerkscherm verlengt de claim elke 30 seconden en hij vervalt na twee minuten (`diensten.CLAIM_VERVALT_NA`), zodat een gesloten tabblad nooit een artikel op slot laat staan. Een tweede redacteur krijgt een waarschuwing en mag doorgaan; beiden zien van elkaar dat ze in hetzelfde artikel zitten. Hetzelfde verzoek is meteen de controle op de beveiligingscode: komt er een 403 terug, dan meldt het scherm dat de sessie is verlopen vóórdat er wordt opgeslagen. Daarnaast weigert het beheerformulier een opslag waarvan het scherm ouder is dan de laatste wijziging (verborgen veld `geladen_stempel` tegen `Artikel.gewijzigd_op`), zodat niemand stilletjes het werk van een ander overschrijft. Die controle leest het artikel sinds 1.8.0 met `select_for_update()`, binnen dezelfde transactie als het schrijven: zonder vergrendeling kwamen twee gelijktijdige opslagen er allebei doorheen. Een ontbrekend stempel geldt als conflict (falen naar de veilige kant), en elk pad dat de status wijzigt werkt `gewijzigd_op` bij — een bulk-`update()` doet dat niet en maakte de controle blind.
- **Kladversie**: onopgeslagen werk in het bewerkscherm, één per redacteur per artikel (voor een nieuw artikel: `artikel` leeg, één per redacteur). Twee lagen: de browser bewaart elke paar seconden een kopie in `localStorage` (werkt offline), de server krijgt de kladversie elke twee minuten, bij `online` en bij `pagehide` (`sendBeacon`). Bij openen vergelijkt `beheer-editor.js` de browser- en de serverkopie en vraagt of de redacteur verder wil. Terugzetten zet ook `geladen_stempel` terug naar het stempel van toen, zodat de conflictcontrole hierboven aanslaat als iemand anders intussen heeft opgeslagen. Na opslaan of weggooien blijft een lege rij met `afgesloten_op` staan: zonder die grafsteen zou een oude browserkopie op een andere laptop de kladversie later laten herrijzen. Pas een kladversie als de redacteur echt iets heeft gedaan (typen, plakken, werkbalk): de editor maakt HTML na het laden soms net anders op, en alleen openen mag geen kladversie geven. `opschonen` ruimt alles ouder dan `KB_KLADVERSIE_DAGEN` op.
- **Bericht**: nieuwsbericht per omgeving, met dezelfde opschoning als artikelinhoud, optioneel gekoppeld aan artikelen, vastgepind en/of met een vervaldatum. Niet in de export/import; nieuws is tijdgebonden.
- **Tellingen** (weergaven, zoektermen, assistentgebruik) zijn per dag en per omgeving geaggregeerd en bevatten geen gebruikers.

## Rechten

| | Lezer | Redacteur (procesmanagement) | Functioneel beheerder |
|---|---|---|---|
| Gepubliceerde artikelen lezen, zoeken, assistent | ✓ | ✓ | ✓ |
| Favorieten, onboarding, verbetervoorstel indienen | ✓ | ✓ | ✓ |
| Eigen voorstellen en terugkoppeling zien | ✓ | ✓ | ✓ |
| Open voorstellen van collega's zien (zonder naam) en steunen | ✓ | ✓ | ✓ |
| Concepten zien, artikelen schrijven en publiceren | | ✓ eigen omgeving | ✓ |
| Voorstellen behandelen (bakken), statistieken | | ✓ eigen omgeving | ✓ |
| Omgevingen, toegang, verwijderen | | | ✓ |

Alle controles zitten op één plek ([kennisbank/rechten.py](../kennisbank/rechten.py)) en gelden zowel voor de API als het beheerscherm. Een artikel waar iemand geen toegang toe heeft geeft 404, niet 403, zodat het bestaan ervan niet uitlekt.

## Belangrijke stromen

**Artikel lezen.** De frontend haalt `GET /api/v1/artikelen/<id>` op en meldt `POST …/weergave`. Dat verhoogt de anonieme dagtelling en zet het artikel bovenaan in "recent bezocht" van de gebruiker.

**Publiceren.** Een redacteur bewerkt in `/beheer/`. Bij opslaan met status *gepubliceerd* vergelijkt de applicatie de inhoud met de laatste versie. Bij verschil ontstaat versie *n+1* met de opgegeven toelichting (verplicht, tenzij *kleine correctie*). Ongewijzigd opslaan maakt geen versie. Een inhoudelijke versie > 1 zet de wijzigingsmelding klaar voor alle lezers (berekend bij het ophalen, niets wordt vooraf per gebruiker opgeslagen) en een regel in de mailwachtrij voor elke favoriet-houder met e-mail die de mail niet heeft uitgezet. Optioneel ontstaat een concept-nieuwsbericht.

**Verbetervoorstel.** Een medewerker selecteert tekst, en het voorstel wordt opgeslagen met het citaat en het versienummer van het artikel op dat moment. Liggen er bij dat artikel al open voorstellen, dan toont de frontend die eerst (`GET /api/v1/voorstellen?lijst=alle&artikel=<id>`), zodat hij het bestaande voorstel kan steunen (`PUT …/voorstellen/<id>/steun`). Een nieuw voorstel komt in de **gezamenlijke bak** van de omgeving (`eigenaar` leeg); redacteuren van die omgeving krijgen (als e-mail is ingesteld) een melding. Op de werkplek in het beheer pakken redacteuren het op, wijzen het toe of leggen het terug; dat loopt via `diensten.voorstel_naar_bak`, die de status, het slot en de e-mail aan een collega regelt. Bij een statuswijziging zet `diensten.eigenaar_bij_statuswijziging` de eigenaar (wie afhandelt, is eigenaar), en `diensten.bakken_rechtzetten` legt voorstellen terug als de eigenaar geen redacteur van de omgeving meer is (bij een rechtenwijziging, het verhuizen van een artikel, en dagelijks in `opschonen`). Het behandelscherm vergelijkt bij opslaan wat er bij het openen stond met de database, zodat een verouderd scherm het werk van een collega niet terugdraait. Status en terugkoppeling zijn zichtbaar voor de indiener.

**Werkplek in het beheer.** `/beheer/` is de werkplek uit `kennisbank/werkoverzicht.py`: links de bakken (werkvoorraad, alle procesmanagers, afgehandeld) en de artikelkant (concepten, kladversies, opnieuw nakijken), rechts de inhoud, met acties via `POST /beheer/werkplek/actie/`. Django's lijst met onderdelen staat onder "Alle onderdelen"; de oude voorstellenlijst staat daar niet meer in. Het aantal databasevragen is vast, ongeacht het aantal voorstellen of artikelen.

**Foutpagina's.** 400, 403, 404 en 500 hebben eigen Nederlandse pagina's (`kennisbank/views.py`, `templates/kennisbank/fout.html`) met een weg terug; onder `/api/` blijft het antwoord JSON. Met `DEBUG` aan toont Django zijn eigen foutinformatie.

**Assistent.** Zie [ai-assistent](ai-assistent.md).

**Zaaksysteem.** Zie [koppeling-zaaksysteem](koppeling-zaaksysteem.md).

## Broncode

| Pad | Inhoud |
|---|---|
| `config/` | Instellingen (alles via omgevingsvariabelen), URL's |
| `kennisbank/models.py` | Datamodel |
| `kennisbank/rechten.py` | Autorisatie |
| `kennisbank/api.py` | REST-API |
| `kennisbank/zoeken.py` | Zoeken |
| `kennisbank/assistent.py` | Assistent en koppeling met het taalmodel |
| `kennisbank/inhoud.py` | Opschonen van artikelinhoud (allowlist), onboarding-blokken |
| `kennisbank/word_import.py` | Word-document → artikel met secties |
| `kennisbank/diensten.py` | Publiceren/versies, tellingen, meldingen |
| `kennisbank/admin.py` | Beheerscherm |
| `kennisbank/auth.py` | OIDC-login en groepen |
| `kennisbank/static/kennisbank/` | Frontend |
| `kennisbank/management/commands/` | Beheercommando's (import, export, toegang, opschonen, demo) |
| `kennisbank/tests/` | Geautomatiseerde tests |
