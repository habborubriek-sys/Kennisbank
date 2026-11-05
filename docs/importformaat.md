# Importformaat

Artikelen kunnen in bulk worden aangeleverd als JSON. Hetzelfde formaat komt uit de export, dus export → bewerken → import werkt.

```bash
beheer kennisbank_import artikelen.json --toelichting "Eerste vulling"
beheer kennisbank_export handhaving export.json
```

Bestaande artikelen (zelfde `slug`) worden bijgewerkt. Als een gepubliceerd artikel daardoor inhoudelijk wijzigt, ontstaat een nieuwe versie met de opgegeven toelichting. Een import is één transactie: bij een fout wordt niets doorgevoerd.

```json
{
  "formaat": "kennisbank-import",
  "versie": 1,
  "omgeving": {"slug": "handhaving", "naam": "Handhaving", "beschrijving": "…"},
  "clusters": ["Nat beheer", "Droog beheer"],
  "zaaktypen": [{"code": "Melding", "naam": "Melding"}],
  "artikelen": [
    {
      "slug": "rappel-versturen",
      "titel": "Rappel versturen bij uitblijvende reactie",
      "samenvatting": "Termijnen en stappen voor het eerste en tweede rappel.",
      "soort": "werkinstructie",
      "status": "gepubliceerd",
      "eigenaar": "Procesmanagement",
      "clusters": ["Droog beheer"],
      "tags": ["rappel", "termijnen"],
      "zaaktypen": ["Melding Omgevingswet"],
      "secties": [
        {
          "kop": "Termijnen",
          "inhoud": "- Reactietermijn verzoek: 4 weken\n- Tweede rappel: 2 weken na het eerste",
          "onboarding": "Twijfel je over de termijn? Vraag het je buddy."
        }
      ]
    }
  ]
}
```

| Veld | Verplicht | Waarden |
|---|---|---|
| `slug` | ja | kleine letters, cijfers en `-`; wordt de link `/artikel/<slug>` |
| `titel`, `samenvatting`, `secties` | ja | |
| `soort` | nee | `werkinstructie` (standaard), `werkafspraak`, `proces` |
| `status` | nee | `concept` (standaard), `gepubliceerd`, `gearchiveerd` |
| `clusters` | nee | leeg = geldt voor alle clusters |
| `tags`, `zaaktypen` | nee | worden aangemaakt als ze nog niet bestaan |
| `secties[].inhoud`, `secties[].onboarding` | | Markdown: `**vet**`, `- lijst`, `1. stappen`, `[link](https://…)`, tabellen |

Een voorbeeld met acht artikelen staat in [demo/voorbeeldinhoud.json](../demo/voorbeeldinhoud.json). Bestaande werkinstructies in Word kunnen met een conversie naar Markdown (bijv. pandoc) in dit formaat worden gezet.
