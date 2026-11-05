# Functioneel beheer (voor procesmanagement)

Als **redacteur** schrijf en onderhoud je de artikelen in jouw omgeving, behandel je verbetervoorstellen en bekijk je de statistieken.

## Een artikel schrijven of wijzigen

1. Ga naar **Beheer** (link links onderin de kennisbank) → *Artikelen*, of klik in een artikel op **Bewerken**.
2. Vul in: titel, link-naam (`slug`, wordt automatisch voorgesteld), samenvatting, soort, cluster(s), tags en zaaktypen.
   - Geen cluster gekozen = het artikel geldt voor alle clusters.
   - Zaaktypen bepalen bij welke zaken het artikel in het zaaksysteem verschijnt.
3. Voeg **secties** toe. Elke sectie is een in- en uitklapbaar blok met een kop en inhoud. In het veld *Onboarding* zet je extra uitleg die alleen zichtbaar is als iemand de schakelaar *Onboarding* aanzet.
4. Opmaak gaat met Markdown:

   | Je typt | Je krijgt |
   |---|---|
   | `**Cluster**` | **Cluster** |
   | `- punt` (elke regel) | opsomming |
   | `1. stap` | genummerde stappen |
   | `[tekst](https://…)` | link |

5. Kies de **status**:
   - *Concept*: alleen zichtbaar voor redacteuren.
   - *Gepubliceerd*: zichtbaar voor iedereen in de omgeving.
   - *Gearchiveerd*: niet meer zichtbaar; de versiegeschiedenis blijft bewaard.
6. Vul bij een wijziging de **toelichting** in, bijvoorbeeld "Termijn tweede rappel aangepast n.a.v. voorstel". Die komt in de versiegeschiedenis.

Elke keer dat je een gepubliceerd artikel inhoudelijk wijzigt, ontstaat automatisch een nieuwe versie. Onderaan het artikel in het beheer zie je alle versies: wanneer, door wie en waarom. Oude versies zijn niet te wijzigen of te verwijderen.

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
