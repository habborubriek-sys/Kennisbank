# Wijzigingen

## 1.10.0 – 2026-11-08

Vierde ronde: de kant van de beheerder, en voorstellen die een gesprek worden in plaats van een eenmalig antwoord.

- **Statuspagina voor de functioneel beheerder** (*Beheer → Status*). Per onderdeel een stoplicht met wat er gemeten is en, als iets niet goed staat, wat eraan te doen is: versie en instellingen, database en openstaande migraties, zoekindex, e-mail en de wachtrij, assistent en daglimiet, de geplande taak, toegang en inhoud. Hiermee zijn de dingen die anders stil kapot gaan in één oogopslag te zien: een cron die niet meer draait, secties zonder zoekdocument, een omgeving waar geen enkele groep aan hangt. De onderhoudscommando's leggen nu vast wanneer ze liepen, zodat "de geplande taak staat niet aan" ook echt opvalt.
- **Groepen uit Entra ID krijgen een leesbare naam.** De groepen-claim bevat bij RWS vaak object-id's, dus een beheerder die toegang regelde, koos uit een lijst GUID's. Bij *Groepen* staat nu per groep hoeveel mensen ermee hebben ingelogd en tot welke omgevingen hij toegang geeft, en kan hij er de naam uit Entra ID bij zetten. Die naam wordt daarna overal gebruikt; de code blijft er grijs bij staan om te vergelijken.
- **Opnieuw nakijken voor.** Elk gepubliceerd artikel heeft een herzieningsdatum, bij publiceren automatisch gevuld volgens `KB_HERZIENINGSTERMIJN_MAANDEN` (standaard twaalf maanden, `0` = uit). De artikelenlijst heeft een kolom met kleur, een filter en een melding bovenaan als er artikelen over de datum zijn. Klopt een artikel nog? Dan schuift de actie *Markeren als nagekeken* de datum vooruit zonder nieuwe versie en zonder melding bij medewerkers. Publiceren schuift de datum ook mee — dat is immers het moment van nakijken — maar een kleine correctie niet. Medewerkers zien de datum niet; het is een hulpmiddel voor procesmanagement.
- **Verbetervoorstellen zijn een gesprek geworden.** Procesmanagement kon één terugkoppeling geven en daarmee was het klaar, dus een voorstel dat in behandeling was, leek maanden stil te liggen. Nu kunnen beide kanten berichten sturen: elk bericht van procesmanagement komt bij de indiener binnen als melding in de kennisbank en als e-mail, en hij kan erop antwoorden. De indiener ziet hoeveel berichten nieuw voor hem zijn; procesmanagement ziet in de lijst hoeveel er is gewisseld en kan filteren op *Indiener heeft als laatste geschreven*. Het invoervak voor een voorstel is bovendien twee keer zo groot, en de voorstellenlijst heeft filters op status.
- **Keuzelijsten opruimen.** Bij clusters, tags en zaaktypen staat hoeveel artikelen het item gebruiken, met een filter *Nergens gebruikt* en een actie die precies die items verwijdert; wat nog in gebruik is, wordt overgeslagen en bij naam genoemd. Alleen een functioneel beheerder kan opruimen. Bij *Omgevingen* staat nu ook hoeveel groepen en artikelen eraan hangen.
- **Tests** (nu 180): de herzieningsdatum (vullen, meeschuiven, kleine correctie, actie, niet zichtbaar voor medewerkers), de statuspagina inclusief een controle die zelf stuklopen mag, de groepsnamen, het opruimen van keuzelijsten, en het gesprek bij een voorstel (meerdere updates, melding per bericht, rechten, grenzen). Daarnaast een browsercontrole van alle zes punten.
- **Gevonden tijdens die browsercontrole**, en meteen opgelost: de inline met het gesprek werd voor een redacteur helemaal weggelaten (de rechten komen uit zijn omgevingen, niet uit de Django-rechtentabel), en berichten werden als gelezen gemarkeerd terwijl de medewerker naar de artikelenlijst keek.

## 1.9.0 – 2026-11-08

Derde ronde na de beoordelingen, en deze keer helemaal aan de kant van de redacteur: van een Word-document naar een artikel dat af is, en van "er is iets gewijzigd" naar "dit is er gewijzigd".

- **De knop *Sectie* neemt de kop over die je selecteert.** Begon je selectie met een kop — na een Word-import is dat bijna altijd zo — dan kreeg je een sectie met een lege titel en diezelfde kop er nog eens ín. Voor de lezer heette dat kader dan "Sectie 1". Nu wordt die kop de titel van de sectie en verdwijnt hij uit de tekst. De knop zelf werkt onveranderd: er ontstaat alleen een sectie als jij erop drukt.
- **Een laatste controle bij de eerste publicatie.** Een artikel dat voor het eerst zichtbaar wordt voor medewerkers, wordt geweigerd als de titel een bestandsnaam of versie-aanduiding is, als de samenvatting leeg of nietszeggend is, of als er een sectie zonder titel in staat — met per geval de uitleg wat eraan moet gebeuren. Ontbreekt er alleen een zaaktype of tag, dan volgt een waarschuwing en gaat de publicatie door: slecht vindbaar is soms de bedoeling. Een al gepubliceerd artikel wordt niet opnieuw gekeurd, zodat een typfout altijd te herstellen blijft.
- **De tekst van een eerdere versie is terug te lezen.** In de versiegeschiedenis staat bij elke regel "Tekst bekijken". Dat opent de opgeslagen momentopname van die versie, zoals medewerkers hem toen zagen — niet de tekst van vandaag. Dat is precies waar de versiegeschiedenis voor bedoeld was.
- **Wie meerdere wijzigingen miste, ziet ze allemaal.** Na een vakantie van drie weken toonde de melding alleen de laatste wijziging; de twee daarvoor waren weg. Nu staat de nieuwste bovenaan met de eerder gemiste eronder (maximaal vier), en vinkt één keer "Ik snap het" ze samen af.
- **Afdrukken of opslaan als PDF.** Een knop in het artikel klapt alle secties open, zet er een regel met titel, versienummer, afdrukdatum en webadres onder, en opent het printvenster van de browser. Daar kiest de medewerker zelf "Opslaan als PDF". Op papier vallen zijbalk, knoppen en meldingen weg en worden de sectiekaders gewone koppen met tekst eronder. Bewust geen PDF-bouwer op de server: niets extra's om te beheren, en de afdruk komt altijd uit de tekst van nu.
- **Twee keuzes bij de Word-import, standaard uit.** "Gebruik de eerste kop in het document als titel" en "Eerste rij van een tabel als koprij". Beide staan standaard uit, want de opmaak in een Word-document zegt niet betrouwbaar wat de bedoeling was; je laatste keuze staat de volgende keer alvast goed. Vind je geen kop om als titel te gebruiken, dan blijft de bestandsnaam de titel en meldt de import dat.
- **Tests** (nu 143): de controle bij de eerste publicatie, het terugkijken van een versie inclusief de rechten per omgeving, meerdere gemiste wijzigingen, en de twee importkeuzes. Daarnaast een browsercontrole van de sectieknop, de printknop en de meldingen.

## 1.8.1 – 2026-11-08

Tweede ronde na de functionele review: de dingen die in een demo of bij invoering het eerst misgaan.

- **De assistent beweert niets meer wat hij niet kan laten zien.** Elk artikel kreeg een lege sectierij voor de tekst vóór de eerste sectiekop, ook als die tekst er niet was. Zo'n lege rij droeg in zijn zoekdocument wél de artikeltitel en won daardoor regelmatig de zoekopdracht; de assistent antwoordde dan met "Dit staat in … onder het kopje :" gevolgd door niets. Die rijen worden niet meer aangemaakt, een bestaande installatie ruimt ze op bij het bijwerken (migratie 0011), lege secties tellen niet meer mee bij het zoeken, en bij een leeg citaat zegt de assistent voortaan dat hij geen antwoord heeft gevonden. Een sectie zonder kop heet in het antwoord "Inleiding".
- **Geen toegang ziet er niet meer uit als een lege kennisbank.** Wie nog niet aan een omgeving is gekoppeld, kreeg een normale kennisbank te zien met de tekst "Geen artikelen gevonden. Probeer een ander trefwoord" — de meest voorkomende en minst herkenbare melding bij invoering. Nu volgt een eigen scherm met uitleg en een contactadres.
- **Nieuwe instelling `KB_CONTACT`**: waar medewerkers terechtkunnen met vragen. Verschijnt in de zijbalk onder "Hulp" en op het scherm hierboven.
- **In het zaaksysteem is zoeken geen doodlopende weg meer.** De zijbalk is daar verborgen, dus na één zoekactie kwam je niet meer terug bij de artikelen van de zaak. Er staat nu een vaste knop "← Artikelen bij …" boven het paneel, en het zoekveld leegmaken brengt je er ook terug.
- **Het zaaksysteem-paneel schaalt mee.** Bij een breed zaaktype stonden alle artikelen alfabetisch onder elkaar — bij 49 artikelen een lijst van ruim vierduizend pixels naast een zaak. Nu staan de acht meest geraadpleegde artikelen van de laatste 90 dagen bovenaan, met "Toon alle N artikelen" eronder.
- **Tests** (nu 122): lege secties, antwoorden van de assistent, het scherm bij geen toegang, en de volgorde van het zaaktype-paneel.

## 1.8.0 – 2026-11-08

Eerste ronde na twee onafhankelijke beoordelingen (een functionele review en twee hardingstests). Deze versie gaat volledig over gegevensintegriteit: niemand mag stilletjes het werk van een ander overschrijven, en een verkeerd teken in een webadres mag de kennisbank niet laten omvallen.

- **Archiveren werkt de wijzigingsdatum bij.** De lijstactie gebruikte een bulk-update, waardoor de wijzigingsdatum ongemoeid bleef. Een redacteur met een openstaand bewerkscherm zette een zojuist gearchiveerd artikel daarmee ongemerkt weer online. Gaat nu per artikel, zoals publiceren al deed.
- **Gelijktijdig opslaan wordt echt tegengehouden.** De controle op tussentijdse wijzigingen las de huidige stand zonder vergrendeling. Sloegen twee redacteuren binnen enkele tientallen milliseconden op, dan kwamen ze er allebei doorheen en verdween het werk van één van beiden zonder melding. Het artikel wordt nu vergrendeld vóór de controle, binnen dezelfde transactie als het schrijven.
- **Een ontbrekend stempel geldt als conflict.** Een leeg verborgen veld sloeg de hele controle over; hij faalde dus "open". Nu wordt zo'n opslag geweigerd met de uitleg dat het scherm niet te controleren was en dat de tekst nog in het scherm staat.
- **Publiceren via de lijstactie eist dezelfde toelichting** als het bewerkscherm. Via concept + lijstactie kon een inhoudelijke wijziging anders bij alle medewerkers binnenkomen met de melding "Gepubliceerd via lijstactie". De actie meldt nu hoeveel artikelen zijn overgeslagen en waarom.
- **Dubbelklikken op "artikel toevoegen" maakt geen dubbele artikelen meer** (ook niet bij exact gelijktijdige verzoeken, dankzij een adviesslot op titel en omgeving), en artikelen met dezelfde titel krijgen elk een eigen webadres. Oude links naar een artikel verwijzen weer door in plaats van een 404 te geven.
- **Een nul-byte in een webadres geeft een nette 400** in plaats van een serverfout. `?tag=%00` en varianten lieten de database afbreken.
- **Een tag die alleen in schrijfwijze verschilt** van een bestaande (`Rappel` naast `rappel`) geeft een nette melding in plaats van een serverfout; de naam wordt nu genormaliseerd vóór de controle op dubbelen.
- **Een te groot artikel** levert een Nederlandse melding in het formulier op (grens 4 MB) in plaats van een kale Engelse foutpagina waarbij alle tekst verloren ging.
- **Tagveld met echte suggesties.** De oude lijst van de browser vergeleek de hele regel, dus na de eerste komma matchte er niets meer. Nu een eigen lijstje dat opengaat zodra je in het veld klikt, de meest gebruikte tags bovenaan zet, matcht op elk deel van een woord, en al gekozen tags weglaat. De tagbeheerlijst toont hoe vaak elke tag wordt gebruikt.
- **Tests** (nu 114): gelijktijdig opslaan, archiveren, ontbrekend stempel, dubbele titel, lijstactie publiceren, nul-bytes en tagnamen.

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
