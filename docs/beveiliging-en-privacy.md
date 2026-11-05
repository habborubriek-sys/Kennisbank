# Beveiliging en privacy

Dit document geeft de informatie die nodig is voor een beveiligingstoets (BIO), een DPIA of pre-scan, en de verwerkingsregistratie. Het beschrijft wat de applicatie doet. De organisatorische maatregelen (wie beheert, waar het draait) blijven bij de organisatie.

## Beveiligingsmaatregelen in de applicatie

| Onderwerp | Maatregel |
|---|---|
| Authenticatie | Via de identity provider (OIDC met PKCE). De applicatie slaat geen wachtwoorden op in productie (`KB_AUTH_MODUS=oidc`). |
| Autorisatie | Rollen per omgeving op basis van groepen uit de identity provider; centraal afgedwongen in API en beheerscherm. Geen toegang = 404 (bestaan lekt niet uit). |
| Sessies | HttpOnly- en Secure-cookies, SameSite instelbaar, standaard 8 uur geldig. CSRF-bescherming op alle wijzigende verzoeken. |
| Invoer en uitvoer | Artikelinhoud (HTML uit de editor of uit een Word-import) wordt bij opslaan én bij tonen opgeschoond met een allowlist (nh3/ammonia). Geen scripts, event-handlers, afbeeldingen of `javascript:`-links mogelijk. Antwoorden van het taalmodel gaan door dezelfde opschoning. Geüploade Word-bestanden worden alleen gelezen (max. 20 MB) en niet bewaard. |
| Browserbeveiliging | Content-Security-Policy zonder `unsafe-inline` en zonder externe bronnen; `frame-ancestors` beperkt inbedden tot opgegeven domeinen; `nosniff`, `Referrer-Policy: same-origin`, `Permissions-Policy`, optioneel HSTS. |
| Externe afhankelijkheden in de browser | Geen. Lettertypes, scripts en stijlen komen van de eigen server; er gaan geen gegevens naar CDN's of trackers. |
| Misbruik | Begrenzing per gebruiker op vragen aan de assistent en op voorstellen (instelbaar). |
| Container | Niet-root (uid 10001), werkt met read-only root filesystem, geen extra capabilities nodig, healthcheck. |
| Afhankelijkheden | Vastgepinde versies; `pip-audit` en een SBOM (CycloneDX) in de CI-pipeline. Django 5.2 LTS. Bij oplevering: geen bekende kwetsbaarheden. |
| Logging | JSON-logs naar stdout. Het access-log bevat geen IP-adressen en geen querystrings (dus geen zoektermen per persoon). Vragen aan de assistent worden niet gelogd. |
| Audittrail | Versiegeschiedenis van artikelen (wie, wanneer, toelichting, volledige inhoud). Wijzigingen in het beheerscherm staan in het beheerlogboek. |

## Verwerkte persoonsgegevens

| Gegeven | Waarom | Bron | Bewaartermijn |
|---|---|---|---|
| Naam, e-mailadres, object-ID, groepen | Inloggen, rechten, naam bij voorstellen, e-mailmeldingen | Identity provider (bij elke login bijgewerkt) | Zolang het account bestaat. Verwijderen kan via het beheerscherm. |
| Favorieten | Functie voor de gebruiker zelf | Gebruiker | Tot de gebruiker ze verwijdert of het account wordt verwijderd |
| Recent bezocht (max. 10 artikelen) | Functie voor de gebruiker zelf | Gebruik | `KB_BEWAAR_RECENT_DAGEN` (standaard 90 dagen) |
| Onboarding-voorkeur | Functie voor de gebruiker zelf | Gebruiker | Zolang het account bestaat |
| Verbetervoorstellen met naam indiener | Terugkoppeling aan de indiener | Gebruiker | Naam wordt `KB_ANONIMISEER_VOORSTEL_DAGEN` (standaard 365 dagen) na afhandeling verwijderd; de inhoud blijft voor de kwaliteitshistorie |
| Naam bij publicatie van een artikelversie | Verantwoording (wie heeft wat vastgesteld) | Redacteur | Zolang de versie bestaat (archiefwaardig) |

**Niet verwerkt.** Er worden geen gegevens per persoon bijgehouden over welke artikelen iemand leest, hoe lang, of wat iemand zoekt of vraagt. Statistieken zijn tellingen per dag zonder gebruiker. Wie wat leest is dus niet te herleiden. Dat is een bewuste ontwerpkeuze: de statistieken dienen om artikelen te verbeteren, niet om medewerkers te beoordelen.

**Bewaartermijnen uitvoeren.** Het commando `opschonen` (in Kubernetes een CronJob) voert de termijnen dagelijks uit.

## AI-assistent en gegevensstromen

Staat de AI aan, dan gaan per vraag de **vraagtekst** en de **tekst van de gevonden secties** naar het ingestelde taalmodel. Er gaat **geen** naam, e-mailadres, gebruikers-ID of sessie mee. De organisatie bepaalt welk endpoint dat is (bijvoorbeeld Azure OpenAI in een EU-regio onder een eigen contract, of een zelf gehost model) en legt dat vast in de verwerkersovereenkomst. Een medewerker kan zelf persoonsgegevens in een vraag typen. Neem daarom in de gebruiksinstructie op dat dat niet de bedoeling is, en kies een endpoint dat geen gegevens bewaart of voor training gebruikt.

Staat de AI uit (`KB_AI_PROVIDER=uit`, de standaard), dan verlaat er niets de applicatie.

## Punten voor de organisatie

- Kies de hosting en database binnen de eigen infrastructuur of onder een bestaand contract.
- Neem de applicatie op in de verwerkingsregistratie (doel: kennisdeling en kwaliteitsborging werkprocessen).
- Bepaal of een DPIA nodig is. Met de AI uit is de verwerking beperkt (accountgegevens en eigen voorkeuren). Met de AI aan is de keuze van het taalmodel het belangrijkste aandachtspunt.
- Beoordeel de archiefwaardigheid van de artikelversies (werkinstructies die op een bepaald moment golden) en leg de bewaartermijn vast in de selectielijst.
- Laat de applicatie vóór productie penetratietesten volgens het eigen beleid.
