# Configuratie

Alle instellingen zijn omgevingsvariabelen. Elke variabele kan ook uit een bestand komen: zet `NAAM_FILE=/pad/naar/bestand` (handig voor Docker- en Kubernetes-secrets). Ja/nee-waarden accepteren `ja/nee`, `aan/uit`, `true/false` en `1/0`.

## Basis

| Variabele | Standaard | Omschrijving |
|---|---|---|
| `KB_SECRET_KEY` | — **verplicht** | Geheime sleutel voor sessies en CSRF. Lang en willekeurig, bijv. `python -c "import secrets;print(secrets.token_urlsafe(50))"`. |
| `KB_DATABASE_URL` | `postgres://kennisbank:kennisbank@localhost:5432/kennisbank` | Databaseverbinding. Voeg `?sslmode=require` toe voor TLS. |
| `KB_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Hostnamen waaronder de applicatie bereikbaar is (komma-gescheiden). |
| `KB_CSRF_TRUSTED_ORIGINS` | leeg | Volledige origins, bijv. `https://kennisbank.example.nl`. |
| `KB_BASIS_URL` | `http://localhost:8000` | Publieke URL, voor links in e-mails. |
| `KB_APP_NAAM` | `Kennisbank` | Naam in de kop en de titel. |
| `KB_CONTACT` | _(leeg)_ | Waar medewerkers terechtkunnen met vragen over de kennisbank: een e-mailadres, een Teams-kanaal of een naam. Verschijnt in de zijbalk en op het scherm voor wie nog geen toegang heeft. Leeg laten kan, maar dan heeft een gebruiker zonder toegang geen bestemming. |
| `KB_TIJDZONE` | `Europe/Amsterdam` | |
| `KB_DEBUG` | `nee` | **Nooit aan in productie.** |
| `KB_DEMO_MODUS` | `nee` | Laadt voorbeeldinhoud en demo-accounts met een bekend wachtwoord, en zet de demopagina van het zaaksysteem aan. **Alleen voor test en demo.** |

## Inloggen

| Variabele | Standaard | Omschrijving |
|---|---|---|
| `KB_AUTH_MODUS` | `lokaal` | `oidc` voor Entra ID of een andere OIDC-provider. `lokaal` = accounts in de applicatie (test/demo). |
| `KB_OIDC_CLIENT_ID`, `KB_OIDC_CLIENT_SECRET` | — | Verplicht bij `oidc`. |
| `KB_OIDC_AUTHORIZATION_ENDPOINT`, `KB_OIDC_TOKEN_ENDPOINT`, `KB_OIDC_USERINFO_ENDPOINT`, `KB_OIDC_JWKS_ENDPOINT` | — | Verplicht bij `oidc`. |
| `KB_OIDC_LOGOUT_ENDPOINT` | leeg | Bij uitloggen ook uitloggen bij de provider. |
| `KB_OIDC_SCOPES` | `openid email profile` | |
| `KB_OIDC_SIGN_ALGO` | `RS256` | |
| `KB_OIDC_GEBRUIKERSNAAM_CLAIM` | `sub` | Stabiele identificatie van de gebruiker. Voor Entra ID: `oid`. |
| `KB_OIDC_GROEPEN_CLAIM` | `groups` | Claim met de groepen. |
| `KB_BEHEERDERS_GROEPEN` | leeg | Groep(en) die functioneel beheerder worden (alle rechten). |
| `KB_OIDC_HERNIEUW_SECONDEN` | `900` (15 min) | Alleen bij `oidc`. Na deze tijd worden de rechten bij de volgende paginaweergave stilletjes opnieuw opgehaald bij de identity provider (`prompt=none`). Gewijzigde groepen en geblokkeerde accounts komen zo binnen deze tijd door. |
| `KB_SESSIE_DUUR_SECONDEN` | `28800` (8 uur) | Maximale duur van een sessie. |

## Beveiliging en inbedden

| Variabele | Standaard | Omschrijving |
|---|---|---|
| `KB_FRAME_ANCESTORS` | `'self'` | Wie de kennisbank in een iframe mag tonen (CSP `frame-ancestors`), bijv. `'self' https://zaaksysteem.example.nl`. |
| `KB_COOKIE_SAMESITE` | `Lax` | `None` als het zaaksysteem op een **ander domein** draait en de kennisbank inbedt. |
| `KB_COOKIES_SECURE` | `ja` (tenzij debug) | Cookies alleen over https. Alleen uit voor een lokale demo via http. |
| `KB_HSTS_SECONDEN` | `0` | Bijv. `31536000` als TLS overal is ingericht. |
| `KB_ACHTER_PROXY` | `ja` | Vertrouw `X-Forwarded-Proto`/`-Host` van de reverse proxy. |
| `KB_SSL_REDIRECT` | `nee` | Doorsturen naar https in de applicatie. Meestal doet de ingress dat. |
| `KB_API_TOKEN_MAX_DAGEN` | `365` | API-tokens van koppelingen verlopen na dit aantal dagen (`0` = nooit). Nieuw token: `beheer kennisbank_token <account>`. |
| `KB_ASSISTENT_LIMIET` | `30/min` | Maximaal aantal vragen aan de assistent per gebruiker (per worker bijgehouden). Het dagplafond voor de hele installatie is `KB_ASSISTENT_DAGLIMIET`. |
| `KB_VOORSTEL_LIMIET` | `20/hour` | Maximaal aantal verbetervoorstellen per gebruiker. |

## AI-assistent

Zie [ai-assistent](ai-assistent.md).

| Variabele | Standaard | Omschrijving |
|---|---|---|
| `KB_AI_PROVIDER` | `uit` | `uit`, `openai` (elk OpenAI-compatibel endpoint, ook zelf gehost) of `azure` (Azure OpenAI). |
| `KB_AI_BASE_URL` | — | Bijv. `https://<resource>.openai.azure.com` of `https://llm.intern/v1`. |
| `KB_AI_MODEL` | — | Modelnaam, of bij Azure de deployment-naam. |
| `KB_AI_API_KEY` | leeg | API-sleutel. |
| `KB_AI_AZURE_API_VERSIE` | `2024-10-21` | Alleen bij `azure`. |
| `KB_AI_TIMEOUT_SECONDEN` | `30` | Daarna valt de assistent terug op zoeken. |
| `KB_AI_MAX_BRONNEN` | `5` | Aantal secties dat als bron wordt meegestuurd. |
| `KB_AI_TEMPERATUUR` | `0.1` | Laag = feitelijk en voorspelbaar. |
| `KB_AI_MAX_TOKENS` | `600` | Maximale lengte van een antwoord van het model. |
| `KB_ASSISTENT_DAGLIMIET` | `2000` | Kostenplafond: maximaal aantal aanroepen van het taalmodel per dag voor de hele installatie (`0` = geen). Daarboven citeert de assistent zonder taalmodel. Zie [ai-assistent](ai-assistent.md#kosten-en-begrenzing). |

## Bewaartermijnen

Uitgevoerd door het commando `opschonen` (dagelijks inplannen); dat verwijdert ook verlopen sessies uit de database, verstuurt de gebundelde favorietenmail en ruimt verzonden mailregels na 30 dagen op. Zie [beveiliging-en-privacy](beveiliging-en-privacy.md).

| Variabele | Standaard | Omschrijving |
|---|---|---|
| `KB_BEWAAR_RECENT_DAGEN` | `90` | Hoe lang "recent bezocht" per gebruiker bewaard blijft. |
| `KB_RECENT_MAX` | `10` | Maximaal aantal regels "recent bezocht" per gebruiker. |
| `KB_BEWAAR_STATISTIEK_DAGEN` | `730` | Geanonimiseerde tellingen (weergaven, zoektermen). |
| `KB_ANONIMISEER_VOORSTEL_DAGEN` | `365` | Na afhandeling wordt de naam van de indiener van een voorstel verwijderd. |
| `KB_HERZIENINGSTERMIJN_MAANDEN` | `12` | Na hoeveel maanden een gepubliceerd artikel opnieuw moet worden nagekeken. Bij publiceren vult de kennisbank de datum "opnieuw nakijken voor" zo in als de redacteur hem leeg laat; een datum die al verstreken was, schuift mee. `0` = niet automatisch vullen (de redacteur kan de datum dan nog altijd zelf zetten). |

## E-mail (optioneel)

Zonder `KB_EMAIL_HOST` worden geen e-mails verstuurd. Meldingen zijn dan alleen in de applicatie te zien.

| Variabele | Standaard |
|---|---|
| `KB_EMAIL_HOST` | leeg |
| `KB_EMAIL_PORT` | `587` |
| `KB_EMAIL_GEBRUIKER`, `KB_EMAIL_WACHTWOORD` | leeg |
| `KB_EMAIL_TLS` | `ja` |
| `KB_EMAIL_AFZENDER` | `kennisbank@localhost` |

Voor test en demo: `KB_EMAIL_HOST=console` verstuurt niets maar schrijft elke e-mail in de serverlog (terminal), zodat je ziet wat er verstuurd zou worden.

### E-mail bij wijziging van een favoriet artikel

Wie een artikel als favoriet heeft, krijgt een e-mail als het inhoudelijk wijzigt (niet bij een *kleine correctie*). Elke medewerker kan dit zelf uitzetten onder *Instellingen* in het menu; IT bepaalt de werkwijze:

| Variabele | Standaard | Omschrijving |
|---|---|---|
| `KB_FAVORIETEN_MAIL` | `gebundeld` | `gebundeld`: wijzigingen worden verzameld en per ontvanger als één e-mail verstuurd zodra `kennisbank_favorietenmail` draait — dat gebeurt in elk geval bij het dagelijkse `opschonen`, dus standaard één mail per dag. Vaker mailen? Plan `beheer kennisbank_favorietenmail` apart in (bijv. elk uur). `direct`: meteen één mail per wijziging. `uit`: geen e-mail; de melding in de kennisbank zelf blijft. |

## Webserver en logging

| Variabele | Standaard | Omschrijving |
|---|---|---|
| `KB_POORT` | `8000` | |
| `KB_WORKERS` | `3` | Gunicorn-workers per container. |
| `KB_TIMEOUT_SECONDEN` | `60` | |
| `KB_FORWARDED_ALLOW_IPS` | `*` | IP's (of reeksen) van de reverse proxy/ingress waarvan `X-Forwarded-*` vertrouwd wordt. `*` is alleen veilig als de container uitsluitend via de proxy bereikbaar is (gebruikelijk in Kubernetes met een NetworkPolicy); zet anders het IP-bereik van de proxy, bijv. `10.0.0.0/8`. |
| `KB_MIGREER_BIJ_START` | `ja` | Zet `nee` als migraties via een aparte Job lopen. |
| `KB_DATABASE_CONN_MAX_AGE` | `60` | Hergebruik van databaseverbindingen (seconden). |
| `KB_LOG_FORMAAT` | `json` | `json` of `tekst`. |
| `KB_LOG_NIVEAU` | `INFO` | |
