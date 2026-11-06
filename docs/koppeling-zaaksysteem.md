# Koppeling met het zaaksysteem

Er zijn twee manieren, en ze kunnen naast elkaar bestaan. Allebei vragen ze aan de kant van het zaaksysteem alleen configuratie: een URL met het zaaktype erin.

## 1. Inbedden (aanbevolen om mee te beginnen)

Het zaaksysteem toont in een paneel of tabblad een iframe:

```html
<iframe src="https://kennisbank.example.nl/zaaktype/{zaaktype-code}" title="Kennisbank"></iframe>
```

Het paneel laat de artikelen bij dat zaaktype zien. De gebruiker kan erin zoeken, artikelen lezen en de assistent vragen stellen, die het zaaktype als context meekrijgt. Een demonstratie staat op `/demo/zaaksysteem/` (alleen met `KB_DEMO_MODUS=aan`).

**Instellen in de kennisbank**

| Instelling | Waarde |
|---|---|
| `KB_FRAME_ANCESTORS` | `'self' https://zaaksysteem.example.nl` |
| `KB_COOKIE_SAMESITE` | `Lax` als zaaksysteem en kennisbank onder hetzelfde domein vallen (bijv. beide `*.rws.nl`); anders `None` |
| Zaaktypen | In het beheerscherm onder *Zaaktypes*: `code` = de waarde die het zaaksysteem in de URL zet. Koppel artikelen aan zaaktypen op het artikel. |

**Inloggen.** Identity providers (ook Entra ID) laten hun loginpagina niet in een iframe zien. Is de gebruiker nog niet ingelogd, dan toont het paneel een knop "Inloggen". Die opent het inloggen in een klein venster en ververst daarna het paneel automatisch. Wie al in de kennisbank is ingelogd (single sign-on), ziet direct de artikelen.

## 2. API

Voor een eigen weergave in het zaaksysteem, bijvoorbeeld een lijstje links bij de zaak:

```
GET /api/v1/zaaktypen/{code}/artikelen
Authorization: Token <token>
```

Antwoord (ingekort):
```json
[{"id": 412, "slug": "melding-registreren", "titel": "Melding registreren in het zaaksysteem",
  "samenvatting": "…", "soort": "werkinstructie", "versie": 3, "url": "/artikel/412/melding-registreren"}]
```

Het artikeldetail (`GET /api/v1/artikelen/<id>`) geeft de tekst als `blokken[]` in leesvolgorde: `{"type": "tekst", "html"}` (altijd zichtbaar) en `{"type": "sectie", "nummer", "kop", "html"}` (in-/uitklapbaar). Gebruik `url` (of `id`) om naar het artikel te linken: het nummer is blijvend, de naam erachter is alleen leesbaar. Ook beschikbaar: `GET /api/v1/artikelen/<id>`, `GET /api/v1/artikelen?zaaktype=…&q=…` en `POST /api/v1/assistent` met `{"vraag": "…", "zaaktype": "…"}`. De volledige specificatie staat in [openapi.yaml](openapi.yaml) en op `/api/docs/`.

**Token voor een koppeling aanmaken.** Maak een technisch account met leesrechten:

```bash
beheer shell -c "from django.contrib.auth.models import User, Group; u,_=User.objects.get_or_create(username='zaaksysteem'); u.groups.add(Group.objects.get(name='<groep met lezer-rol>'))"
beheer drf_create_token zaaksysteem
```

Het token geeft dezelfde rechten als dat account: alleen gepubliceerde artikelen in de omgevingen waar het lezer is.

## Wat het zaaksysteem zelf moet doen

Voor optie 1 alleen een iframe met een URL op basis van het zaaktype. Voor optie 2 één GET-verzoek. Er gaan geen zaakgegevens naar de kennisbank, behalve de zaaktype-code in de URL.
