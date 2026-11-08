# Kennisbank

Eén centrale plek voor werkinstructies, werkafspraken en processen. Medewerkers zoeken en lezen artikelen, zetten extra uitleg voor nieuwe collega's aan, bewaren favorieten, zien bij een artikel wat er is gewijzigd (en krijgen daar als favoriet-houder een e-mail van), drukken een artikel af of bewaren het als PDF, lezen het nieuws van hun afdeling, dienen verbetervoorstellen in — en praten daar met procesmanagement over door — en stellen vragen aan een assistent die alleen antwoordt uit de kennisbank. Procesmanagement schrijft artikelen in een editor met Word-opmaak of importeert ze uit Word, behandelt voorstellen, houdt bij welke artikelen opnieuw moeten worden nagekeken en ziet welke kennis gebruikt en gemist wordt. Functioneel beheer heeft een statuspagina waarop in één oogopslag te zien is of alles nog loopt. Het zaaksysteem kan per zaaktype de juiste artikelen tonen.

> Versie 1.13.1 · Licentie EUPL-1.2 · Python 3.12+ / Django 5.2 LTS / PostgreSQL 14+

## Proberen in één commando

```bash
docker compose up
```

Open daarna http://localhost:8000 en log in als `medewerker`, `redacteur` of `beheerder` (wachtwoord `demo`). Je krijgt dan de voorbeeldinhoud uit het prototype. Op http://localhost:8000/demo/zaaksysteem/ zie je hoe de kennisbank eruitziet als hij in een zaaksysteem is ingebed.

| Artikel met onboarding-uitleg | Assistent met bronnen | Ingebed in het zaaksysteem |
|---|---|---|
| ![](docs/schermafbeeldingen/2-artikel-onboarding.png) | ![](docs/schermafbeeldingen/3-assistent.png) | ![](docs/schermafbeeldingen/6-zaaksysteem.png) |

## Wat IT moet doen om het in productie te nemen

| Stap | Wat | Waar beschreven |
|---|---|---|
| 1 | Image bouwen (of de geleverde gebruiken) en in de eigen registry zetten | [installatie-en-beheer](docs/installatie-en-beheer.md#1-image) |
| 2 | Een PostgreSQL-database aanmaken (een beheerde dienst mag, zie [een andere database](docs/installatie-en-beheer.md#een-andere-database-dan-postgresql)) | [installatie-en-beheer](docs/installatie-en-beheer.md#2-database) |
| 3 | Een app-registratie in Entra ID maken (OIDC, met de groepen-claim) | [installatie-en-beheer](docs/installatie-en-beheer.md#3-inloggen-via-entra-id) |
| 4 | Configuratie en geheimen invullen, de container uitrollen (Docker of Kubernetes) | [configuratie](docs/configuratie.md), [deploy/kubernetes](deploy/kubernetes) |
| 5 | Groepen aan rollen koppelen en de inhoud importeren | [installatie-en-beheer](docs/installatie-en-beheer.md#5-toegang-en-inhoud) |
| Optioneel | AI-model aansluiten, inbedden in het zaaksysteem, e-mail | [ai-assistent](docs/ai-assistent.md), [koppeling-zaaksysteem](docs/koppeling-zaaksysteem.md) |

Er is geen maatwerk aan de infrastructuur nodig: één stateless container achter de bestaande ingress, en één database.

## Wat er in het pakket zit

| Onderdeel | Inhoud |
|---|---|
| Applicatie | Django-applicatie met REST-API (`/api/v1/`, OpenAPI in [docs/openapi.yaml](docs/openapi.yaml)) en een frontend zonder build-stap of externe bibliotheken |
| Container | [Dockerfile](Dockerfile) (niet-root, read-only filesystem mogelijk, healthcheck), [compose.yaml](compose.yaml) om te proberen |
| Kubernetes | [deploy/kubernetes](deploy/kubernetes): Deployment, Service, Ingress, migratie-Job, CronJob voor bewaartermijnen |
| Kwaliteit | geautomatiseerde tests (zie de CHANGELOG voor het aantal per versie), lint, CI-pipelines voor [GitHub](.github/workflows/ci.yml) en [GitLab](.gitlab-ci.yml), SBOM ([sbom.cdx.json](sbom.cdx.json)) |
| Documentatie | Zie hieronder |

## Documentatie

- [Architectuur](docs/architectuur.md): componenten, datamodel, gegevensstromen
- [Installatie en beheer](docs/installatie-en-beheer.md): uitrollen, back-up, updates, monitoring
- [Configuratie](docs/configuratie.md): alle instellingen
- [Beveiliging en privacy](docs/beveiliging-en-privacy.md): maatregelen, verwerkte persoonsgegevens, bewaartermijnen, input voor DPIA
- [AI-assistent](docs/ai-assistent.md): hoe de assistent werkt en welke gegevens naar een taalmodel gaan
- [Koppeling met het zaaksysteem](docs/koppeling-zaaksysteem.md): inbedden en API
- [Toegankelijkheid](docs/toegankelijkheid.md): WCAG 2.1 AA, testresultaten
- [Functioneel beheer](docs/functioneel-beheer.md): handleiding voor procesmanagement
- [Importformaat](docs/importformaat.md): artikelen in bulk aanleveren
- [Van prototype naar product](docs/van-prototype-naar-product.md): welke functie uit het prototype waar zit

## Ontwikkelen

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export KB_DEBUG=1 KB_DEMO_MODUS=1 KB_DATABASE_URL=postgres://kennisbank:kennisbank@localhost:5432/kennisbank
python manage.py migrate && python manage.py kennisbank_demo
python manage.py runserver
python manage.py test kennisbank      # tests (PostgreSQL vereist)
ruff check .                          # lint
```
