# Functioneel beheer (voor procesmanagement)

Als **redacteur** schrijf en onderhoud je de artikelen in jouw omgeving, behandel je verbetervoorstellen en bekijk je de statistieken.

## Een artikel schrijven of wijzigen

1. Ga naar **Beheer** (link links onderin de kennisbank) → *Artikelen*, of klik in een artikel op **Bewerken**.
2. Vul in: titel, link-naam (`slug`, wordt automatisch voorgesteld), samenvatting, soort, cluster(s), tags en zaaktypen.
   - Geen cluster gekozen = het artikel geldt voor alle clusters.
   - **Tags** typ je gescheiden door komma's (bijv. `rappel, termijnen, brief`). Bestaande tags worden voorgesteld terwijl je typt; nieuwe tags worden automatisch aangemaakt.
   - Zaaktypen bepalen bij welke zaken het artikel in het zaaksysteem verschijnt.
3. Voeg **secties** toe. Elke sectie is een in- en uitklapbaar blok met een kop en inhoud. De inhoud bewerk je in een editor met een werkbalk zoals in Word:

   | Knop | Doet |
   |---|---|
   | ¶ | Alinea, Kop, Subkop of Citaat |
   | **B** *I* <u>U</u> ~~S~~ x² | Vet, cursief, onderstreept, doorgehaald, superscript |
   | Lijsten, inspringen | Opsomming, genummerde lijst, inspringing |
   | Link, tabel, lijn | Hyperlink, tabel invoegen, scheidingslijn |
   | Gum | Opmaak van de selectie wissen |
   | **Onboarding** | Markeer de geselecteerde alinea's als uitleg voor nieuwe collega's (zie hieronder) |

   Plakken uit Word werkt: de opmaak wordt opgeschoond, vet/cursief/lijsten/tabellen blijven staan.
4. Kies de **status**:
   - *Concept*: alleen zichtbaar voor redacteuren.
   - *Gepubliceerd*: zichtbaar voor iedereen in de omgeving.
   - *Gearchiveerd*: niet meer zichtbaar; de versiegeschiedenis blijft bewaard.
5. Vul bij een wijziging de **toelichting** in, bijvoorbeeld "Termijn tweede rappel aangepast n.a.v. voorstel". Die komt in de versiegeschiedenis.

Elke keer dat je een gepubliceerd artikel inhoudelijk wijzigt, ontstaat automatisch een nieuwe versie. Onderaan het artikel in het beheer zie je alle versies: wanneer, door wie en waarom. Oude versies zijn niet te wijzigen of te verwijderen.

## Onboarding-uitleg

Nieuwe collega's hebben meer uitleg nodig dan ervaren collega's. Die extra uitleg zet je gewoon in de tekst en markeer je:

1. Zet de cursor in de alinea (of selecteer meerdere alinea's) en klik op **Onboarding** in de werkbalk.
2. De alinea's krijgen een geel kader "Voor nieuwe collega's". In de kennisbank zijn ze alleen zichtbaar als de lezer de schakelaar *Onboarding* aanzet.
3. Nogmaals klikken op **Onboarding** haalt de markering weer weg.

Een sectie mag meerdere onboarding-blokken bevatten, dus je kunt bij elke stap een verdieping geven. De assistent gebruikt de onboarding-uitleg ook, als extra context.

## Een Word-document importeren

Schrijf je artikelen liever eerst in Word? Gebruik dan het [Word-sjabloon](../kennisbank/static/kennisbank/sjabloon-werkinstructie.docx) (ook te downloaden op de importpagina) en upload het document.

1. Ga naar **Beheer → Artikelen → Importeren uit Word** en kies het `.docx`-bestand en de omgeving.
2. De kennisbank maakt een **concept**-artikel en opent het bewerkscherm. Controleer de tekst, vul tags en zaaktypen in en zet de status op *Gepubliceerd*.

Zo wordt het document gelezen:

| In Word | In de kennisbank |
|---|---|
| Eén *Kop 1* bovenaan | De titel |
| *Kop 2*-koppen (of alle *Kop 1*-koppen als er geen titel is) | De secties |
| Eerste alinea vóór de eerste kop | De samenvatting |
| Alinea's met de stijl **Onboarding** (zit in het sjabloon) | Onboarding-uitleg |
| Vet, cursief, onderstreept, lijsten, tabellen, links | Blijven behouden |
| Afbeeldingen | Worden overgeslagen (nog niet ondersteund) |

Een `.doc` of PDF upload je niet rechtstreeks: open het in Word en sla het op als `.docx`. Bij een PDF gaat de structuur (koppen, lijsten) meestal verloren, dus controleer het resultaat extra goed.

## Verbetervoorstellen behandelen

In de kennisbank onder **Verbetervoorstellen** zie je alle voorstellen bij artikelen in jouw omgeving, met de tekst die de collega had geselecteerd en de artikelversie op dat moment.

1. Zet de status: *Nieuw*, *In behandeling*, *Verwerkt* of *Afgewezen*.
2. Schrijf een terugkoppeling en klik op **Opslaan**. De indiener ziet die bij zijn voorstel (en krijgt een e-mail als die is ingesteld).
3. Verwerk je het voorstel, pas dan het artikel aan en noem het voorstel in de toelichting.

## Statistieken

Onder **Gebruiksstatistieken** (alleen zichtbaar voor redacteuren), over de laatste 30 dagen:

- weergaven per artikel en aantal voorstellen per artikel;
- meest gezochte termen;
- **gezocht zonder resultaat**: kennis die collega's zoeken maar niet vinden; een goede bron voor nieuwe artikelen;
- aantal vragen aan de assistent.

De cijfers zijn tellingen zonder namen. Je kunt niet zien wie wat heeft gelezen of gezocht.

## Keuzelijsten

Clusters, tags en zaaktypen beheer je in het beheerscherm. Redacteuren kunnen ze toevoegen en wijzigen; alleen functioneel beheerders kunnen ze verwijderen. Bij een zaaktype moet de **code** precies overeenkomen met wat het zaaksysteem gebruikt.

## Functioneel beheerder

Een functioneel beheerder (lid van de groep in `KB_BEHEERDERS_GROEPEN`) beheert daarnaast:

- **Omgevingen**: bijv. "Handhaving". Elke omgeving heeft eigen artikelen.
- **Toegang**: welke groep uit Entra ID in welke omgeving *lezer* of *redacteur* is. Groepen verschijnen in de lijst zodra iemand uit die groep een keer heeft ingelogd. Je kunt ze ook vooraf aanmaken met de object-ID als naam.
