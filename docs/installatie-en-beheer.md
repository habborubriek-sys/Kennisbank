# Installatie en beheer

Dit document is voor de beheerorganisatie. De applicatie is één stateless container met één PostgreSQL-database. Alle instellingen komen uit omgevingsvariabelen ([configuratie](configuratie.md)).

## Overzicht

```
gebruiker ──https──▶ ingress / reverse proxy (TLS) ──http──▶ container :8000 ──▶ PostgreSQL
                                                                 │
                                       (optioneel) ──────────────┼──▶ Entra ID (OIDC)
                                                                 ├──▶ taalmodel (Azure OpenAI / eigen endpoint)
                                                                 └──▶ SMTP
```

## 1. Image

```bash
docker build -t registry.example.nl/kennisbank:1.9.0 .
docker push registry.example.nl/kennisbank:1.9.0
```

Moet een goedgekeurde basis-image worden gebruikt, geef die dan mee: `--build-arg BASE_IMAGE=registry.example.nl/python:3.13-slim`. De image:

- draait als gebruiker `10001`, niet als root;
- werkt met een read-only root filesystem (alleen `/tmp` beschrijfbaar, bijv. als tmpfs);
- heeft geen netwerkverbindingen nodig tijdens het starten, behalve naar de database;
- bevat alle statische bestanden (lettertypes, scripts, stijlen) en laadt niets van externe domeinen.

## 2. Database

PostgreSQL 14 of hoger. Maak een lege database en een gebruiker die eigenaar is:

```sql
CREATE USER kennisbank WITH PASSWORD '...';
CREATE DATABASE kennisbank OWNER kennisbank;
```

Geef de verbinding door als `KB_DATABASE_URL=postgres://kennisbank:...@host:5432/kennisbank?sslmode=require`. Het schema wordt aangemaakt door de migraties (`migreer`, zie hieronder). Er zijn geen extensies nodig.

## 3. Inloggen via Entra ID

1. Maak een app-registratie (web-applicatie).
2. Redirect-URI: `https://<host>/oidc/callback/`. Front-channel logout-URL: `https://<host>/`.
3. Maak een client secret en noteer client-ID en tenant-ID.
4. Voeg onder *Token configuration* de **groups**-claim toe (Security groups, als Group ID). Wil je de groepen beperken tot de relevante groepen, wijs dan alleen die groepen toe aan de applicatie en kies *Groups assigned to the application*.
5. Vul de `KB_OIDC_*`-variabelen in; [.env.voorbeeld](../.env.voorbeeld) bevat de Entra-endpoints. Gebruik `KB_OIDC_GEBRUIKERSNAAM_CLAIM=oid`, de onveranderlijke object-ID van de gebruiker.
6. Zet de object-ID van de groep functioneel beheerders in `KB_BEHEERDERS_GROEPEN`. Dit is in OIDC-modus de enige weg naar beheerdersrechten: een met `createsuperuser` aangemaakt account kan niet inloggen, omdat wachtwoord-inloggen dan volledig uit staat.

Elke andere identity provider die OpenID Connect spreekt werkt ook.

> Let op: Entra ID zet de groepen-claim niet in het token als iemand in meer dan 200 groepen zit (*groups overage*). Beperk daarom de groepen tot de groepen die aan de applicatie zijn toegewezen (stap 4).

## 4. Uitrollen

### Kubernetes / OpenShift

[deploy/kubernetes](../deploy/kubernetes) bevat een kustomize-basis:

```bash
# Geheimen aanmaken (zie secret.voorbeeld.yaml voor alle sleutels)
kubectl -n kennisbank create secret generic kennisbank-geheimen --from-env-file=productie.env
# Image, host en configuratie aanpassen in kustomization.yaml en configmap.yaml, dan:
kubectl apply -k deploy/kubernetes
```

Onderdelen: Deployment (2 replica's, probes, resource-limieten, restrictieve securityContext), Service, Ingress (voorbeeld), migratie-Job en een dagelijkse CronJob voor de bewaartermijnen.

### Docker / losse server

```bash
docker run -d --name kennisbank -p 8000:8000 --env-file productie.env --read-only --tmpfs /tmp \
  registry.example.nl/kennisbank:1.9.0
```

Zet er een reverse proxy met TLS voor. De applicatie leest `X-Forwarded-Proto` en `X-Forwarded-Host` (uit te zetten met `KB_ACHTER_PROXY=nee`).

### Containercommando's

| Commando | Doet |
|---|---|
| `web` (standaard) | migreert de database (tenzij `KB_MIGREER_BIJ_START=nee`) en start gunicorn |
| `migreer` | alleen migraties |
| `opschonen` | voert de bewaartermijnen uit en verstuurt de gebundelde favorietenmail; **dagelijks inplannen** |
| `beheer kennisbank_favorietenmail` | alleen de favorietenmail versturen; optioneel vaker inplannen dan dagelijks (zie `KB_FAVORIETEN_MAIL`) |
| `beheer <commando>` | beheercommando, bijvoorbeeld `beheer kennisbank_import /data/artikelen.json` |

### Upgraden naar 1.9.0

De migraties lopen automatisch mee bij het starten (of via `migreer`). Twee dingen om te weten:

- Tags worden overal naar kleine letters gebracht; tags die daardoor samenvallen worden samengevoegd (de artikelen gaan mee).
- Wijzigingsmeldingen gelden alleen voor wijzigingen vanaf 1.9.0: bestaande versies worden voor alle bestaande gebruikers als gezien gemarkeerd, zodat niemand na de upgrade de hele geschiedenis als openstaande melding krijgt.
- E-mail bij wijziging van favorieten staat standaard op `gebundeld`; zonder `KB_EMAIL_HOST` wordt er niets verstuurd. Zie [configuratie](configuratie.md).

## 5. Toegang en inhoud

Toegang werkt per **omgeving** (bijvoorbeeld "Handhaving"). Een groep uit Entra ID krijgt in een omgeving de rol *lezer* of *redacteur*:

```bash
# in de container:
beheer kennisbank_toegang handhaving <object-id-groep-medewerkers> lezer --naam "Handhaving"
beheer kennisbank_toegang handhaving <object-id-groep-procesmanagement> redacteur
```

Dit kan ook in het beheerscherm (`/beheer/` → Omgevingen → Toegang). Daarna de inhoud laden:

```bash
beheer kennisbank_import /pad/naar/artikelen.json
```

Het formaat staat in [importformaat](importformaat.md). Een export maak je met `beheer kennisbank_export handhaving /tmp/export.json`.

## Dagelijks beheer

**Monitoring.** `GET /healthz` geeft aan of het proces draait (liveness). `GET /readyz` geeft aan of de database bereikbaar en gemigreerd is (readiness, 503 als dat niet zo is). Logs gaan als JSON-regels naar stdout: applicatielogs plus een access-log zonder IP-adressen en zonder querystrings.

**Back-up.** Alle gegevens staan in PostgreSQL. Een normale database-back-up (bijvoorbeeld `pg_dump` of de back-up van het databaseplatform) is voldoende. De container zelf heeft geen staat. Een inhoudelijke export van de artikelen maak je met `kennisbank_export`.

**Updates.** Nieuwe image bouwen, eerst de `migreer`-Job draaien en dan de Deployment bijwerken. Lees bij elke versie de [CHANGELOG](../CHANGELOG.md). Werkwijze:

1. Maak vlak vóór de update een databaseback-up (`pg_dump`); dat is het terugvalpunt.
2. Draai de migraties met de nieuwe image (`migreer`). Elke migratie draait in zijn eigen transactie: mislukt er een, dan is die ene ongedaan gemaakt, maar eerdere migraties uit dezelfde update blijven toegepast. Zet in dat geval de back-up uit stap 1 terug.
3. Rol daarna de nieuwe image uit. Zolang de oude image nog draait tegen een gemigreerde database kunnen er fouten optreden; houd de overgang kort of plan hem buiten werktijd.

Terugdraaien naar een vorige versie doe je door de back-up uit stap 1 terug te zetten en de oude image uit te rollen. Gebruik niet `migrate` naar een oudere migratie: inhoudsomzettingen (bijvoorbeeld van 1.0 naar 1.3) worden niet teruggerekend. De omzettingen in de migraties zijn bevroren in `kennisbank/oud_formaat.py`; een geautomatiseerde test migreert een database met inhoud van versie 1.0 naar de huidige versie, zodat ook een installatie die meerdere versies overslaat in één keer kan bijwerken.

**Schalen.** De container is stateless: meer replica's of `KB_WORKERS` verhogen. De limiet op vragen aan de assistent wordt per worker bijgehouden. Bij veel replica's is die dus ruimer dan ingesteld; is dat een probleem, begrens dan ook op de ingress.

**Afhankelijkheden.** Alle Python-pakketten staan vast in [requirements.txt](../requirements.txt). De CI-pipeline draait `pip-audit` op bekende kwetsbaarheden en maakt een SBOM (CycloneDX) met `python scripts/maak_sbom.py`; die bevat ook de meegeleverde browserbibliotheek (de editor Jodit, zie `kennisbank/static/kennisbank/vendor/componenten.json`). Jodit valt niet onder `pip-audit`; controleer bij elke release op [npm](https://www.npmjs.com/package/jodit) of er een nieuwere versie met beveiligingsfixes is en vervang dan `jodit.min.js`/`jodit.min.css` (map `es2021/` van het npm-pakket) en de versie in `componenten.json`. Django 5.2 is een LTS-versie met beveiligingsupdates tot april 2028.

## Problemen oplossen

| Verschijnsel | Oorzaak / oplossing |
|---|---|
| `KB_SECRET_KEY is verplicht` bij starten | Stel `KB_SECRET_KEY` in (lange willekeurige waarde). |
| 400 Bad Request | De hostnaam staat niet in `KB_ALLOWED_HOSTS`. |
| 403 CSRF bij inloggen of opslaan | De URL staat niet in `KB_CSRF_TRUSTED_ORIGINS` (inclusief `https://`). |
| Ingelogd, maar geen artikelen | De groepen van de gebruiker zijn niet gekoppeld aan een omgeving (stap 5), of de groepen-claim ontbreekt in het token. |
| Inbedden in het zaaksysteem toont een lege frame | Het domein van het zaaksysteem ontbreekt in `KB_FRAME_ANCESTORS`. Zie [koppeling-zaaksysteem](koppeling-zaaksysteem.md). |
