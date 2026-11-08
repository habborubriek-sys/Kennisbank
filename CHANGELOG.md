# Wijzigingen

## 1.7.1 – 2026-11-08

Samen in één artikel werken zonder elkaars werk kwijt te raken, en opslaan dat nooit stilletjes mislukt.

- **Zacht slot bij bewerken.** Open je een artikel dat een collega op dat moment ook open heeft, dan verschijnt een venster met zijn naam en vanaf hoe laat, met de keuze *Toch bewerken* of *Terug naar de lijst*. Zit je er al in en komt er iemand bij, dan verschijnt bovenin *"Let op: … heeft dit artikel zojuist ook geopend."* Bewust geen hard slot: dat levert vooral sloten op die blijven hangen. De claim wordt elke 30 seconden verlengd en vervalt na twee minuten; `kennisbank_opschonen` ruimt restanten op.
- **Opslaan overschrijft niemand meer stilletjes.** Is het artikel gewijzigd terwijl jouw scherm openstond, dan wordt de opslag geweigerd met de datum en de naam van wie het opsloeg. Je tekst blijft in het scherm staan, zodat je hem kunt overzetten.
- **Verlopen beveiligingscode** (meestal doordat je in een ander tabblad opnieuw inlogt) wordt nu in het bewerkscherm gemeld zodra het gebeurt, en levert bij opslaan een Nederlandse uitlegpagina op in plaats van het technische Django-scherm.
- **Volledig scherm vraagt om de toelichting.** Het veld staat op de pagina eronder, waardoor opslaan vanuit het volledige scherm kon mislukken op een melding die je niet zag. Nu verschijnt er een venster met het toelichtingsveld en het vinkje *Kleine correctie*, en daarna wordt alsnog opgeslagen.
- **Opmaak**: een artikel met een openstaande wijziging staat in de lijst op een licht gele kaart met een amberkleurige balk *Gewijzigd …* over de volle breedte boven de titel; de melding in het artikel zelf (met de toelichting) heeft dezelfde kleuren. De artikeltekst mag langer worden (90 tekens per regel in plaats van 70) en de artikelkolom is smaller, zodat tekst en kaart op elkaar aansluiten; tabellen mogen breder.
- Migratie `0010_zacht_slot`. **Tests** (nu 102): claims zien, vervallen en opruimen, rechten per omgeving op het claim-endpoint, conflict bij opslaan, en de eigen CSRF-pagina.

## 1.7.0 – 2026-11-08

Wijzigingsmeldingen en nieuws: medewerkers zien wat er is veranderd, en procesmanagement heeft één plek voor mededelingen.

- **Wijzigingsmelding bij een artikel.** Bij een inhoudelijke wijziging van een gepubliceerd artikel ziet de medewerker bovenaan het artikel *Gewijzigd op <datum> — <toelichting>* met de knop **Ik snap het**. De melding blijft staan tot hij is afgevinkt of tot de volgende wijziging. In de lijst staat het label *Gewijzigd*; nieuw menu-onderdeel **Gewijzigd** met teller en *alles als gezien markeren*. Geen meldingen voor wijzigingen van vóór de eerste inlog van de gebruiker, en niet voor versie 1 (de publicatie zelf).
- **Toelichting verplicht** bij een inhoudelijke wijziging van een gepubliceerd artikel; nieuw vinkje **Kleine correctie, geen melding** (typfout, opmaak) waarbij wel een versie ontstaat maar geen melding of e-mail. Versies tonen die vlag in de versiegeschiedenis.
- **E-mail aan favoriet-houders**: wie het artikel als favoriet heeft krijgt de toelichting per e-mail, standaard gebundeld tot één mail per dag per persoon (`KB_FAVORIETEN_MAIL`: `gebundeld`, `direct` of `uit`). Nieuw commando `kennisbank_favorietenmail`; `kennisbank_opschonen` roept het ook aan. Medewerkers kunnen de mail zelf uitzetten onder *Instellingen* in het menu. `KB_EMAIL_HOST=console` toont e-mails in de serverlog (test/demo).
- **Nieuws**: nieuwsberichten per omgeving met titel, opgemaakte tekst, gekoppelde artikelen, concept/gepubliceerd, vastpinnen en vervaldatum. Nieuw menu-onderdeel **Nieuws** met ongelezen-teller; de laatste berichten staan ook op de startpagina. Niet zichtbaar in het zaaksysteem (ingebed). Beheer onder *Nieuwsberichten*; de editor heeft daar alleen de opmaakknoppen.
- **Koppeling**: bij publiceren het vinkje **Ook als nieuwsbericht plaatsen** maakt een concept-bericht met de toelichting, gekoppeld aan het artikel.
- **API**: `wijziging` in artikel(lijst), `POST /artikelen/<id>/gezien`, `POST /wijzigingen/gezien`, `GET /berichten`, `POST /berichten/gezien`; `ik` geeft en accepteert `mail_bij_favorieten` en geeft `nieuws_ongelezen`.
- **Demo-inhoud**: een negende artikel zonder secties (korte werkafspraak), twee nieuwsberichten en één voorbeeldwijziging, zodat alle paden in de demo zichtbaar zijn en meelopen in de tests.
- **Tags** hebben nu overal dezelfde schrijfwijze (kleine letters), ook bij import; bestaande tags worden door migratie `0009` genormaliseerd en samengevoegd. Zonder dit zou een geïmporteerd artikel met een hoofdletter-tag bij de eerste opslag in het beheer ten onrechte als "inhoudelijk gewijzigd" tellen (bevinding uit de onafhankelijke review van deze ronde).
- **Import** (`kennisbank_import`) heeft `--kleine-correctie`; de documentatie vermeldt dat een import meldingen en e-mails veroorzaakt.
- **Robuustheid** (uit de review): een mislukte e-mail blijft in de wachtrij voor de volgende ronde en gelijktijdige runs sturen niet dubbel; ontvangers zonder leesrecht of bij een gearchiveerd artikel krijgen geen mail; "Ik snap het" vinkt af tot de versie die de gebruiker zag (niet een intussen gepubliceerde); nieuwsberichten worden ook bij tonen opgeschoond; een bericht dat terug naar concept gaat telt bij herpublicatie weer als nieuw.
- Migraties `0008_wijzigingen_en_nieuws` en `0009_bestaande_gegevens_1_7` (bestaande versies worden voor bestaande gebruikers als gezien gemarkeerd; zie [installatie-en-beheer](docs/installatie-en-beheer.md#upgraden-naar-170)). **Tests** (nu 93): meldingen (verschijnen, afvinken, kleine correctie, eerste inlog, alles gezien, beheerformulier), favorietenmail (gebundeld, direct, uit, eigen voorkeur, opschonen), nieuws (rechten per omgeving, verlopen, ongelezen-teller, opschoning, beheer).

## 1.6.1 – 2026-11-08

- **Artikel zonder secties opende niet**: de kennisbank toonde "Er ging iets mis bij het laden" voor elk artikel zonder inklapbare sectie — dus ook voor elk artikel direct na een Word-import, dat bewust nog geen secties heeft. De oorzaak zat in de browser (de knop "Alles uitklappen" werd aangesloten terwijl hij er niet was); de server deed het goed. Zat erin sinds 1.3.0. Ververs na het bijwerken de pagina met Ctrl+F5.

## 1.6.0 – 2026-11-07

Derde ronde uit de onafhankelijke code-review: de kleinere punten en de ontbrekende tests.

- **Zoeken schaalt mee**: de zoekdocumenten staan opgeslagen (`tsvector` met GIN-index op artikel en sectie) en worden bij elke opslag bijgewerkt, in plaats van per zoekopdracht berekend. Migratie `0007_zoekvectoren` vult ze voor bestaande inhoud.
- **API-tokens verlopen** na `KB_API_TOKEN_MAX_DAGEN` (standaard een jaar); nieuw commando `beheer kennisbank_token <account>` maakt of vernieuwt een token (`--intrekken` trekt in). Een koppeling zonder geldig token krijgt een echte 401.
- **Opschonen** verwijdert ook verlopen sessies (`clearsessions`).
- **API-randjes**: een voorstel bij een onzichtbaar artikel geeft dezelfde fout als bij een onbestaand artikel; een voorstel behandelen dat niet van jouw omgeving is geeft 404; `?dagen=abc` geeft 400 in plaats van 500; `onboarding` in `PATCH /ik` wordt echt als ja/nee gelezen; `PATCH` op een voorstel mag alleen de status of alleen de terugkoppeling bevatten.
- **Inhoud**: kale `<div>`/`<span>` uit geplakte tekst worden uitgepakt en een onboarding-blok in een onboarding-blok wordt één blok, zodat onboarding-tekst nooit per ongeluk in het gewone antwoord of bij de assistent belandt. Sectietitels met `&` of `<` werden dubbel ge-escaped.
- **Frontend**: externe links in een artikel openen in een nieuw tabblad (ook in het zaaksysteem); voorbeeldvragen van de assistent alleen in de demo; de lengte van "recent bezocht" volgt `KB_RECENT_MAX`.
- **Import** weigert een ongeldige `slug` met een duidelijke melding. Een tag hernoemen of verwijderen in het beheer werkt direct door in de zoekindex.
- **OpenAPI** volledig getypeerd (`ik`, `keuzelijsten`, `versies`, `statistieken`).
- **Documentatie**: `KB_FORWARDED_ALLOW_IPS` met advies voor productie; tokenrotatie in [koppeling-zaaksysteem](docs/koppeling-zaaksysteem.md).
- **Tests** (nu 67): beheer weigert een andere omgeving, begrenzing van de assistent, geneste onboarding, tag hernoemen, tokenverloop, sessie-opschoning, slug-validatie, zoeken na upgrade.

## 1.5.0 – 2026-11-07

Tweede ronde reparaties uit de onafhankelijke code-review.

- **Rechten werken direct door.** Toegang tot het beheer (redacteur) volgt automatisch uit groepen en de regels onder *Toegang*; een wijziging daar geldt meteen, niet pas bij de volgende login. In OIDC-modus worden de rechten standaard elke 15 minuten stilletjes opnieuw bij de identity provider opgehaald (`KB_OIDC_HERNIEUW_SECONDEN`), zodat een geblokkeerd account of een gewijzigde groep niet tot het einde van de sessie doorwerkt.
- **Statistieken per omgeving.** Zoektermen en assistentgebruik worden per omgeving geteld; redacteuren zien alleen die van hun eigen omgeving(en). Bestaande tellingen worden bij de migratie aan de omgeving gekoppeld als er precies één is.
- **Assistent verhard.** Artikeltekst en zaaktype gaan als gemarkeerde gegevens in het gebruikersbericht naar het taalmodel (niet in de systeemprompt); links in het antwoord anders dan bronverwijzingen worden tekst; antwoordlengte begrensd (`KB_AI_MAX_TOKENS`); kostenplafond per dag voor de hele installatie (`KB_ASSISTENT_DAGLIMIET`, standaard 2000) met terugval op citeren. Kostenparagraaf in [docs/ai-assistent.md](docs/ai-assistent.md).
- **Migraties bevroren.** De inhoudsomzettingen van 0002 en 0004 gebruiken alleen nog bevroren functies uit `kennisbank/oud_formaat.py`; updateprocedure met back-up/terugvalpunt beschreven in [docs/installatie-en-beheer.md](docs/installatie-en-beheer.md#dagelijks-beheer).

Migratie: `0006_tellingen_per_omgeving` (nieuwe kolommen en één nieuwe tabel; geen inhoudswijziging).

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
