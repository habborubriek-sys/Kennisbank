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
  "versie": 2,
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
          "inhoud": "<ul><li>Reactietermijn verzoek: 4 weken</li><li>Tweede rappel: 2 weken na het eerste</li></ul><div class=\"onboarding\"><p>Twijfel je over de termijn? Vraag het je buddy.</p></div>"
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
| `secties[].inhoud` | | HTML (wordt opgeschoond tot: p, strong, em, u, s, sub, sup, ul, ol, li, a, h3, h4, table, blockquote, code, hr). Onboarding-uitleg als `<div class="onboarding">…</div>`, meerdere per sectie toegestaan. |
| `versie` | | `2` = inhoud in HTML (huidig). `1` = inhoud in Markdown met een apart veld `onboarding` per sectie; wordt bij import omgezet. |

Een voorbeeld met acht artikelen staat in [demo/voorbeeldinhoud.json](../demo/voorbeeldinhoud.json). Losse Word-documenten importeer je eenvoudiger via **Beheer → Artikelen → Importeren uit Word** (zie [functioneel-beheer](functioneel-beheer.md)); dit JSON-formaat is bedoeld voor bulk en voor uitwisseling tussen installaties.
