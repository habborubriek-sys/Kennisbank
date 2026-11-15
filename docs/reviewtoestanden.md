# Toestanden van de review

Wat kan wanneer, voor de redacteur en de reviewer. Dit document is voor beheerders en ontwikkelaars die willen
weten hoe het reviewproces in elkaar zit. De handleiding voor redacteuren staat in
[functioneel-beheer](functioneel-beheer.md#reviewproces-een-concept-laten-meelezen).

De regels worden op de server afgedwongen, in `kennisbank/review.py` en `kennisbank/diensten.py`. De schermen
volgen ze alleen.

## Begrippen

- **Concept**: de nieuwe versie van een gepubliceerd artikel waar de redactie aan werkt. Er is er hoogstens
  één per artikel. Medewerkers zien hem niet.
- **Ter inzage**: het concept ligt bij een of meer reviewteams. Per team per ronde is er één rij (`Inzage`).
- **Ronde**: elke keer dat de redacteur ter inzage geeft, begint een nieuwe ronde. Alleen de laatste ronde telt
  voor de stand; eerdere rondes blijven zichtbaar met hun opmerkingen.
- **Op slot**: zolang minstens één team in de laatste ronde nog *Ter inzage* heeft.
- **Stempel**: het moment waarop het concept voor het laatst is gewijzigd. Een akkoord geldt voor één
  stempel.

## De drie standen die de redacteur ziet (sinds 1.34.0)

De redacteur ziet niet de toestanden hieronder, maar één van drie standen, met de bijzonderheid als regel
erachter (`review.drie_standen`; voor de bakken op de werkplek `review.standen_voor`, twee databasevragen
ongeacht het aantal artikelen).

| Stand | Betekenis | Toestanden die eronder vallen |
|---|---|---|
| **Bij de redactie** | De tekst is te wijzigen | Concept nog niet ter inzage, Teruggegeven, Teruggeroepen, Akkoord vervallen |
| **Bij het reviewteam** | Op slot | Ter inzage (nog niet opgepakt), Ter inzage (opgepakt) |
| **Akkoord** | Klaar om te publiceren | Akkoord |

De toestanden zelf, de rondes, de voorlopige opmerkingen en het slot zijn niet veranderd. De reviewer houdt op
`/review/` zijn eigen woorden ("nog niet opgepakt", "ligt bij jou"): dat is zijn werklijst.

## De toestanden van een concept

| Toestand | Wanneer | Op slot |
|---|---|---|
| Geen concept | Het artikel heeft alleen de live versie | – |
| Concept, nog niet ter inzage | Opgeslagen met *Opslaan als concept* | nee |
| Ter inzage, nog niet opgepakt | Ter inzage gegeven; geen reviewer heeft het opgepakt | ja |
| Ter inzage, opgepakt | Een reviewer heeft *Oppakken* gekozen ("ligt bij …") | ja |
| Teruggegeven | Het team gaf het terug met opmerkingen | nee |
| Akkoord | Alle teams van de laatste ronde gaven akkoord, en de tekst is daarna niet gewijzigd | nee |
| Akkoord vervallen | Er was akkoord, maar het concept is daarna gewijzigd | nee |
| Teruggeroepen | De redacteur haalde het terug voordat het team klaar was | nee |

Bij meer teams geldt per team een eigen rij. Het concept is op slot zolang één team nog bezig is, en
"Akkoord" geldt pas als alle teams akkoord zijn.

## Overgangen

| Van | Handeling | Door | Naar |
|---|---|---|---|
| Geen concept | Opslaan als concept | redacteur | Concept |
| Concept (ook teruggegeven, akkoord, teruggeroepen) | Ter inzage geven | redacteur | Ter inzage, nieuwe ronde |
| Ter inzage | Oppakken of Overnemen | reviewer van het team | Ter inzage, opgepakt |
| Ter inzage, opgepakt | Teruggeven met opmerkingen | de reviewer bij wie het ligt | Teruggegeven |
| Ter inzage, opgepakt | Akkoord | de reviewer bij wie het ligt | Akkoord |
| Ter inzage | Terugroepen | redacteur | Teruggeroepen |
| Akkoord | Het concept wijzigen en opslaan | redacteur | Akkoord vervallen |
| Elke toestand die niet op slot is | Publiceren | redacteur | Geen concept; nieuwe versie |
| Elke toestand die niet op slot is | Concept weggooien | redacteur | Geen concept |
| Elke toestand | Artikel archiveren of naar een andere omgeving verhuizen | redacteur | De review stopt; het concept blijft |
| Elke toestand | Reviewproces van de omgeving uitzetten | beheerder | Alles wat ter inzage ligt, wordt teruggeroepen |

Bij publiceren of weggooien worden de rijen afgesloten: ze tellen niet meer mee voor de stand, maar blijven
bewaard voor de versiegeschiedenis.

## Wat de redacteur kan

| | Niet ter inzage | Ter inzage (op slot) |
|---|---|---|
| Het concept wijzigen | ja | nee |
| Publiceren | ja | nee, eerst terugroepen |
| Concept weggooien | ja | nee, eerst terugroepen |
| Ter inzage geven | ja | nee, ligt er al |
| Terugroepen | – | ja; is een team al bezig, dan eerst een bevestiging |
| De live versie verbeteren (via *Bewerken* op de site) | ja | ja |
| Wijzigingen van de live versie overnemen in het concept | ja | nee, alleen bekijken |
| Opmerkingen van het team zien | na teruggeven of akkoord; na terugroepen als *voorlopig* | nee |
| Bericht aan de indiener van een voorstel, interne notitie | ja | ja |

## Wat de reviewer kan

| | Niet opgepakt | Opgepakt door een teamgenoot | Opgepakt door jou | Afgerond of teruggeroepen |
|---|---|---|---|---|
| De tekst lezen, met de wijzigingen | ja | ja | ja | nee; alleen de uitkomst onder *Onlangs afgerond* |
| Oppakken | ja | Overnemen, bewust | – | nee |
| Opmerking plaatsen | nee, eerst oppakken | nee | ja | nee |
| Eigen opmerking wijzigen of weghalen | – | – | ja | nee |
| Teruggeven of Akkoord | nee | nee | ja; teruggeven vraagt minstens één opmerking | nee |

Een reviewer bewerkt de tekst nooit en publiceert nooit. Hij ziet de meegenomen verbetervoorstellen zonder de
naam van de indiener, en geen notities of berichten van de redactie. Een verborgen voorstel ziet hij niet.

## Verbetervoorstellen tijdens de review

| | Niet ter inzage | Ter inzage |
|---|---|---|
| Meenemen aan- of uitzetten | ja; telt bij opslaan | nee |
| Een meegenomen voorstel afhandelen, afwijzen of ontdubbelen | ja | nee, tot de review terug is |
| Een voorstel dat niet is meegenomen afhandelen, afwijzen of ontdubbelen | ja | ja |
| Een meegenomen voorstel meenemen bij het verbeteren van de live versie | ja | nee; het hoort bij de review |

Dat geldt op elke weg: in de lade, via de API (`PATCH /api/v1/voorstellen/<id>` geeft 409) en in oude schermen.

Welke voorstellen meegenomen waren op het moment van ter inzage geven, wordt bij de rij bewaard. Neemt de
redacteur na een akkoord nog een voorstel mee, dan heeft de reviewer dat niet gezien; het bewerkscherm waarschuwt
daarvoor in het venster Afronden.

Bij publiceren krijgen de meegenomen voorstellen het nummer van de nieuwe versie, ook als medewerkers er geen
melding van krijgen (sinds 1.31.2). Publiceren zonder inhoudelijke wijziging geeft geen nieuwe versie; de voorstellen staan dan weer
open.

## Wat er in de versiegeschiedenis komt

Bij publiceren legt de kennisbank vast hoe de review ervoor stond:

| Stand bij publiceren | Regel in de geschiedenis |
|---|---|
| Het reviewproces staat uit | geen regel |
| Nooit ter inzage geweest | Gepubliceerd zonder review. |
| Akkoord van alle teams, tekst ongewijzigd | Akkoord van Team Water. |
| Akkoord, maar op het scherm nog gewijzigd voor het publiceren | Gepubliceerd met wijzigingen na het akkoord van Team Water. |
| Teruggegeven, teruggeroepen of akkoord vervallen | Gepubliceerd zonder akkoord van Team Water. |

Een akkoord is niet nodig om te publiceren: de redacteur is eindverantwoordelijk.

## E-mail

| Gebeurtenis | Wie krijgt een e-mail |
|---|---|
| Nieuw stuk ter inzage | de reviewers van het team, gebundeld in één e-mail per dag (de dagelijkse taak `kennisbank_opschonen`) |
| Teruggegeven of akkoord | de redacteur die het ter inzage gaf |
| Teruggeroepen | de reviewer die het had opgepakt |
| Review gestopt (archiveren, verhuizen, reviewproces uit) | de reviewer die ermee bezig was |
| Een collega publiceert jouw concept | de redacteur die het begon of het als laatste bijwerkte |

## Gelijktijdig werken

- Slaat een collega het concept op terwijl jij het open hebt, dan wordt jouw opslag geweigerd; je werk staat
  in je kladversie.
- Geeft de redacteur ter inzage vanaf een verouderd scherm, dan weigert de kennisbank dat: het team zou anders
  een andere tekst lezen dan de redacteur zag.
- Wordt een stuk teruggeroepen of gestopt terwijl een reviewer typt, dan krijgt die zijn getypte tekst terug om
  te kopiëren.
- Pakt een teamgenoot het stuk net eerder op, dan zegt de kennisbank dat; overnemen kan daarna bewust.

## Getest

De regels hierboven hebben tests in `kennisbank/tests/` (onder meer `test_review_c1.py`, `test_review_c2_d.py`,
`test_reviewbevindingen_1210.py` en `test_ronde_a_1280.py`). De hele stroom van bewerken, ter inzage geven,
oppakken, opmerking plaatsen, teruggeven en publiceren loopt in de browsertest (`scripts/browsertests/rook.js`).
