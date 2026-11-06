# Functioneel beheer (voor procesmanagement)

Als **redacteur** schrijf en onderhoud je de artikelen in jouw omgeving, behandel je verbetervoorstellen en bekijk je de statistieken.

## Een artikel schrijven of wijzigen

1. Ga naar **Beheer** (link links onderin de kennisbank) → *Artikelen*, of klik in een artikel op **Bewerken**.
2. Vul de **titel** en de **samenvatting** in (één of twee zinnen; staat bovenaan het artikel en in de lijst).
3. Schrijf de **tekst** in de editor. De werkbalk werkt zoals in Word:

   | Knop | Doet |
   |---|---|
   | ¶ | Alinea, Kop, Subkop of Citaat |
   | **B** *I* <u>U</u> ~~S~~ x² | Vet, cursief, onderstreept, doorgehaald, superscript |
   | Lijsten, inspringen | Opsomming, genummerde lijst, inspringing |
   | Link, tabel, lijn | Hyperlink, tabel invoegen, scheidingslijn |
   | Gum | Opmaak van de selectie wissen |
   | **Voorbeeld** | Opent in een nieuw tabblad hoe het artikel er gepubliceerd uitziet, met wat nu in de editor staat (ook als het nog niet is opgeslagen). Klik opnieuw om het tabblad te verversen. |
   | **Sectiekop** | Maakt van de huidige regel een sectiekop (zie hieronder) |
   | **Onboarding** | Markeert de geselecteerde alinea's als uitleg voor nieuwe collega's (zie hieronder) |

   Plakken uit Word werkt: de opmaak wordt opgeschoond, vet/cursief/lijsten/tabellen blijven staan.
4. Vul onder *Eigenschappen* en *Vindbaarheid* in: soort, omgeving, cluster(s), tags en zaaktypen.
   - Geen cluster gekozen = het artikel geldt voor alle clusters.
   - **Tags** typ je gescheiden door komma's (bijv. `rappel, termijnen, brief`). Bestaande tags worden voorgesteld; nieuwe worden automatisch aangemaakt.
   - Zaaktypen bepalen bij welke zaken het artikel in het zaaksysteem verschijnt.
5. Kies de **status**:
   - *Concept*: alleen zichtbaar voor redacteuren.
   - *Gepubliceerd*: zichtbaar voor iedereen in de omgeving.
   - *Gearchiveerd*: niet meer zichtbaar; de versiegeschiedenis blijft bewaard.
6. Vul bij een wijziging de **toelichting** in, bijvoorbeeld "Termijn tweede rappel aangepast n.a.v. voorstel". Die komt in de versiegeschiedenis.

Elke keer dat je een gepubliceerd artikel inhoudelijk wijzigt, ontstaat automatisch een nieuwe versie. Onderaan het artikel in het beheer zie je alle versies: wanneer, door wie en waarom. Oude versies zijn niet te wijzigen of te verwijderen.

**De link van een artikel** wordt bij het opslaan toegekend en heeft de vorm `/artikel/412/melding-registreren`. Het nummer is wat telt: dat verandert nooit, ook niet als je de titel aanpast of het artikel naar een andere omgeving verhuist. De naam erachter is alleen voor de leesbaarheid. Twee afdelingen kunnen dus gerust een artikel met dezelfde titel hebben.

## Secties

Een artikel is één doorlopende tekst. Een **sectie** is een in- en uitklapbaar blok daarin:

1. Zet de cursor op de regel die de naam van de sectie moet worden en klik op **Sectiekop** in de werkbalk. In de editor zie je dan `«Sectiekop» naam «Sectiekop»`; de cursor springt naar een nieuwe regel eronder, zodat je direct verder kunt typen.
2. Alles wat daaronder staat, tot de volgende sectiekop, hoort bij die sectie. De volgorde van de secties is simpelweg de volgorde in de tekst.
3. Tekst **vóór de eerste sectiekop** is de inleiding: die staat altijd open, boven de secties.
4. Nogmaals klikken op **Sectiekop** maakt er weer een gewone regel van.

Gewone koppen (via ¶ → Kop of Subkop) zijn koppen *binnen* de tekst en maken geen sectie. Zo kies je zelf wat een sectie wordt en wat niet.

## Onboarding-uitleg

Nieuwe collega's hebben meer uitleg nodig dan ervaren collega's. Die extra uitleg zet je gewoon in de tekst en markeer je:

1. Zet de cursor in de alinea (of selecteer meerdere alinea's) en klik op **Onboarding** in de werkbalk.
2. De alinea's krijgen een geel kader "Voor nieuwe collega's". In de kennisbank zijn ze alleen zichtbaar als de lezer de schakelaar *Onboarding* aanzet.
3. Nogmaals klikken op **Onboarding** haalt de markering weer weg.

Dit kan zo vaak als je wilt, ook in de inleiding, dus je kunt bij elke stap een verdieping geven. De assistent gebruikt de onboarding-uitleg ook, als extra context.

## Een Word-document importeren

Schrijf je artikelen liever eerst in Word? Gebruik dan het [Word-sjabloon](../kennisbank/static/kennisbank/sjabloon-werkinstructie.docx) (ook te downloaden op de importpagina) en upload het document.

1. Ga naar **Beheer → Artikelen → Importeren uit Word** en kies het `.docx`-bestand en de omgeving.
2. De kennisbank maakt een **concept**-artikel en opent het bewerkscherm. Controleer de tekst, vul tags en zaaktypen in en zet de status op *Gepubliceerd*.

Zo wordt het document gelezen:

| In Word | In de kennisbank |
|---|---|
| Stijl *Titel*, of één *Kop 1* helemaal bovenaan | De titel |
| De eerste alinea | De samenvatting |
| Alinea's met de stijl **Sectie** (zit in het sjabloon) | Sectiekoppen |
| Alinea's met de stijl **Onboarding** (zit in het sjabloon) | Onboarding-uitleg |
| Gewone koppen (Kop 1, 2, 3) | Koppen in de tekst; ze maken géén sectie |
| Vet, cursief, onderstreept, lijsten, tabellen, links | Blijven behouden |
| Afbeeldingen | Worden overgeslagen (nog niet ondersteund) |

Secties bepaal je dus bewust, met de stijl *Sectie* in Word of met de knop *Sectiekop* in de editor; een kopje in Word wordt nooit per ongeluk een sectie.

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
