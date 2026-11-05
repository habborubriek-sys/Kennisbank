# Van prototype naar product

Elke functie uit het klikbare prototype en de functionele schets, en waar die in de applicatie zit.

| Functie (schets) | Prototype | Product |
|---|---|---|
| Artikelen met titel, samenvatting en inklapbare subtitels | ✓ | ✓ Secties met kop en inhoud; "alles uit-/inklappen" |
| Onboarding-functie | ✓ schakelaar | ✓ Schakelaar; de keuze wordt per gebruiker onthouden |
| Zoekfunctie met tags en filters | trefwoorden in de browser | ✓ Zoeken op de server met Nederlandse woordstammen; filters op cluster, soort en tag |
| Favorieten | ✓ in de browser | ✓ Per gebruiker opgeslagen |
| Recent bezocht | ✓ in de browser | ✓ Per gebruiker, maximaal 10, met bewaartermijn |
| Delen | ✓ link met `#` | ✓ Echte link `/artikel/<naam>` |
| Verbetervoorstellen op geselecteerde tekst, met terugkoppeling | ✓ | ✓ Met status, terugkoppeling, artikelversie en e-mailmelding |
| AI-ondersteuning met verwijzing naar het artikel | gesimuleerd | ✓ Zoekt in de kennisbank; met taalmodel naar keuze een samengevat antwoord met bronverwijzingen |
| Profielen en autorisaties, "omgevingen" | wisselknop | ✓ Rollen per omgeving via groepen uit Entra ID |
| Koppeling met het zaaksysteem per zaaktype | simulatie | ✓ Inbedden via `/zaaktype/<code>` en een API-endpoint; de assistent krijgt het zaaktype als context |
| Gebruikersstatistieken | voorbeeldcijfers | ✓ Weergaven, zoektermen, zoektermen zonder resultaat, voorstellen, assistentgebruik; zonder persoonsgegevens |
| Eigenaarschap bij procesmanagement | – | ✓ Redacteursrol, versiegeschiedenis met toelichting, eigenaar per artikel |
| Artikelen bewerken | "valt buiten prototype" | ✓ Beheerscherm met secties, publicatiestatus en versies |
| Horizon: organisatiebreed inzetbaar | – | ✓ Meerdere omgevingen in één installatie |

Nieuw ten opzichte van het prototype: concept/gepubliceerd/gearchiveerd, onveranderlijke versiegeschiedenis, import en export, bewaartermijnen, inloggen via de identity provider, API met OpenAPI-specificatie, toegankelijkheidstest.
