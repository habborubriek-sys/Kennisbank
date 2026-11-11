# Beveiliging en privacy

Dit document geeft de informatie die nodig is voor een beveiligingstoets (BIO), een DPIA of pre-scan, en de verwerkingsregistratie. Het beschrijft wat de applicatie doet. De organisatorische maatregelen (wie beheert, waar het draait) blijven bij de organisatie.

## Beveiligingsmaatregelen in de applicatie

| Onderwerp | Maatregel |
|---|---|
| Authenticatie | Via de identity provider (OIDC met PKCE). Met `KB_AUTH_MODUS=oidc` is wachtwoord-inloggen volledig uitgeschakeld: het inlogscherm van het beheer stuurt door naar de identity provider, `/inloggen/` bestaat niet en een eventueel wachtwoord in de database (bijv. van `createsuperuser`) werkt nergens. Beheerders komen binnen via de groep in `KB_BEHEERDERS_GROEPEN`. |
| Autorisatie | Rollen per omgeving op basis van groepen uit de identity provider; centraal afgedwongen in API en beheerscherm. Geen toegang = 404 (bestaan lekt niet uit). |
| Sessies | HttpOnly- en Secure-cookies, SameSite instelbaar, standaard 8 uur geldig. In OIDC-modus worden de rechten standaard elke 15 minuten stilletjes opnieuw bij de identity provider opgehaald (`KB_OIDC_HERNIEUW_SECONDEN`), zodat een geblokkeerd account of een gewijzigde groep niet tot het einde van de sessie doorwerkt. Een nul-byte in het pad of in een parameter wordt door `NulByteMiddleware` geweigerd met 400, en in de inhoud van een verzoek door de serializer van het betreffende endpoint (PostgreSQL accepteert dat teken niet in tekstvelden). CSRF-bescherming op alle wijzigende verzoeken; mislukt die controle, dan volgt een eigen Nederlandse uitlegpagina (`CSRF_FAILURE_VIEW`) in plaats van het standaardscherm, en het bewerkscherm meldt het al vóór het opslaan. |
| Invoer en uitvoer | Artikelinhoud en nieuwsberichten (HTML uit de editor of uit een Word-import) worden bij opslaan én bij tonen opgeschoond met een allowlist (nh3/ammonia). Geen scripts, event-handlers, afbeeldingen of `javascript:`-links mogelijk. Antwoorden van het taalmodel gaan door dezelfde opschoning. Geüploade Word-bestanden worden alleen gelezen (max. 20 MB) en niet bewaard. |
| Browserbeveiliging | Content-Security-Policy zonder `unsafe-inline` en zonder externe bronnen voor de kennisbank zelf; `frame-ancestors` beperkt inbedden tot opgegeven domeinen; `nosniff`, `Referrer-Policy: same-origin`, `Permissions-Policy`, optioneel HSTS. Het beheerscherm (`/beheer/`, alleen voor redacteuren) gebruikt het standaard Django-beheer, dat inline scripts nodig heeft; daar is de policy ruimer (`'unsafe-inline'`, wel alleen eigen bronnen). |
| Externe afhankelijkheden in de browser | Geen. Lettertypes, scripts en stijlen komen van de eigen server; er gaan geen gegevens naar CDN's of trackers. De enige meegeleverde bibliotheek is de editor Jodit (MIT), vastgelegd in `kennisbank/static/kennisbank/vendor/componenten.json` en opgenomen in de SBOM. Bij een nieuwe release wordt gecontroleerd of er een nieuwere Jodit met beveiligingsfixes is; een test bewaakt dat de versie in de SBOM die van het bestand is. |
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
| Onboarding-voorkeur, e-mailvoorkeur bij favorieten, "nieuws gezien op" | Functie voor de gebruiker zelf | Gebruiker | Zolang het account bestaat |
| Afgevinkte wijzigingsmeldingen (per artikel het versienummer) | Functie voor de gebruiker zelf ("Ik snap het") | Gebruiker | Zolang het account of het artikel bestaat |
| Wachtrij favorietenmail (gebruiker, artikel, versie) | Bundelen van de e-mail per dag | Gebruik | Verzonden regels worden na 30 dagen verwijderd door `opschonen` |
| Verbetervoorstellen met naam indiener | Terugkoppeling aan de indiener | Gebruiker | Naam wordt `KB_ANONIMISEER_VOORSTEL_DAGEN` (standaard 365 dagen) na afhandeling verwijderd, op het voorstel **en** op zijn eventuele berichten; de inhoud blijft voor de kwaliteitshistorie |
| Naam bij een terugkoppeling of update van procesmanagement | Verantwoording (wie heeft wat toegezegd) | Redacteur | Zolang het voorstel bestaat |
| Wie een voorstel van een collega steunt (de like-knop) | Procesmanagement ziet hoeveel en welke collega's achter een voorstel staan | Gebruiker | Collega's zien alleen het aantal, nooit namen; de redactie ziet de namen. Bij de anonimisering van het voorstel (`KB_ANONIMISEER_VOORSTEL_DAGEN` na afhandeling) worden de namen gewist en blijft het aantal staan. Intrekken kan zolang het voorstel open is |
| Interne notities bij een voorstel (naam redacteur, tekst) | Overdracht binnen de redactie ("gebeld met Toezicht") | Redacteur | Alleen zichtbaar voor de redactie, nooit voor de indiener of collega's. Worden verwijderd bij de anonimisering van het voorstel (`KB_ANONIMISEER_VOORSTEL_DAGEN` na afhandeling): er kunnen namen in staan |
| In wiens bak een voorstel ligt (eigenaar) | Werkverdeling binnen de redactie | Redacteur | Zolang het voorstel bestaat, net als de naam bij een terugkoppeling |
| Naam bij publicatie van een artikelversie | Verantwoording (wie heeft wat vastgesteld) | Redacteur | Zolang de versie bestaat (archiefwaardig) |
| Kladversie: naam van de redacteur, het artikel, het tijdstip en de nog niet opgeslagen tekst | Geen werk kwijt bij een verlopen sessie, crash of verbroken verbinding; collega's kunnen werk overnemen | Redacteur | Tot de redacteur opslaat of weggooit; daarna blijft alleen een lege markering ("afgesloten op") over. Beide worden na `KB_KLADVERSIE_DAGEN` (standaard 30 dagen) verwijderd door `opschonen` |
| Kopie van de kladversie in de browser (`localStorage`) | Werkt ook zonder verbinding | Redacteur | Op dat ene apparaat, tot opslaan of weggooien, uiterlijk `KB_KLADVERSIE_DAGEN` |

**Niet verwerkt.** Er worden geen gegevens per persoon bijgehouden over welke artikelen iemand leest, hoe lang, of wat iemand zoekt of vraagt. Statistieken zijn tellingen per dag zonder gebruiker. Wie wat leest is dus niet te herleiden. Dat is een bewuste ontwerpkeuze: de statistieken dienen om artikelen te verbeteren, niet om medewerkers te beoordelen.

**Twee namen bij een verbetervoorstel, twee termijnen.** De naam van de **indiener** is die van een medewerker die een signaal afgeeft; die verdwijnt een jaar na afhandeling, op het voorstel en op zijn berichten. De naam van de **redacteur** die heeft teruggekoppeld blijft staan zolang het voorstel bestaat: dat is verantwoording voor wat er aan een medewerker is toegezegd, vergelijkbaar met de naam bij een artikelversie. Wie die keuze anders wil, zet `KB_ANONIMISEER_VOORSTEL_DAGEN` korter of verwijdert het voorstel; verwijderen haalt de berichten mee.

De termijn wordt gerekend vanaf `behandeld_op`, en dat veld wordt alleen bij een **statuswijziging** gezet. Een tussentijdse update ("opgepakt, we kijken ernaar") schuift de termijn dus niet op.

**Voorstellen van collega's.** Medewerkers zien de open voorstellen bij artikelen die zij mogen lezen, om ze te kunnen steunen. Daarbij staat **geen naam** van de indiener en niet het gesprek met de redactie; alleen het artikel, het citaat, de tekst, de status, de **datum** van indienen (niet het tijdstip, dat in een klein team kan verraden wie het was) en het aantal steunbetuigingen. Het indienvenster zegt dit vooraf: *"Collega's zien je voorstel, zonder je naam. Alleen procesmanagement ziet wie het indiende."* De redactie kan een voorstel **verbergen voor collega's**, bijvoorbeeld als er een naam van een collega in staat; dan is het voor collega's onzichtbaar (404) en kan het niet worden gesteund. Afgehandelde voorstellen zijn voor collega's niet zichtbaar. Een voorstel bij een concept of in een andere omgeving is onzichtbaar (404). De redactie ziet wie een voorstel steunt; dat is een bewuste keuze van de opdrachtgever, zodat procesmanagement bij twijfel kan navragen wat iemand bedoelt.

**Kladversies.** Een kladversie is werk dat een redacteur nog niet heeft opgeslagen. Hij is nooit zichtbaar voor medewerkers en telt niet als versie. Redacteuren van **dezelfde omgeving** zien dát een collega een kladversie heeft en kunnen hem lezen, bijvoorbeeld om het werk over te nemen als iemand ziek is; redacteuren van een andere omgeving zien niets, ook niet dat hij bestaat. De tekst gaat bij het lezen door dezelfde schoonmaak als een gepubliceerd artikel. Naast de serverkopie houdt de browser een kopie bij in `localStorage`, zodat werk ook zonder verbinding bewaard blijft. Die kopie staat op het apparaat van de redacteur en wordt gewist bij opslaan of weggooien; op een **gedeelde computer** blijft hij tot dat moment staan. Bij persoonlijke werklaptops is dat geen punt; wie de kennisbank op gedeelde werkplekken wil gebruiken, moet dit meewegen.

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
