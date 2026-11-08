# Importformaat

Artikelen kunnen in bulk worden aangeleverd als JSON. Hetzelfde formaat komt uit de export, dus export → bewerken → import werkt.

```bash
beheer kennisbank_import artikelen.json --toelichting "Eerste vulling"
beheer kennisbank_export handhaving export.json
```

Bestaande artikelen (zelfde `slug`) worden bijgewerkt. Als een gepubliceerd artikel daardoor inhoudelijk wijzigt, ontstaat een nieuwe versie met de opgegeven toelichting — en **medewerkers zien die toelichting als wijzigingsmelding bij het artikel; wie het als favoriet heeft krijgt een e-mail**. Kies de toelichting dus met zorg, of gebruik `--kleine-correctie` als de wijzigingen geen melding waard zijn (dan ontstaat wel een versie, maar geen melding of e-mail). Een import is één transactie: bij een fout wordt niets doorgevoerd. Tags worden genormaliseerd naar kleine letters.

```json
{
  "formaat": "kennisbank-import",
  "versie": 4,
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
      "inhoud": "<p>Inleiding.</p><section class=\"sectie\"><h2 class=\"sectie-kop\">Termijnen</h2><ul><li>Reactietermijn verzoek: 4 weken</li><li>Tweede rappel: 2 weken na het eerste</li></ul><div class=\"onboarding\"><p>Twijfel je over de termijn? Vraag het je buddy.</p></div></section>"
    }
  ]
}
```

| Veld | Verplicht | Waarden |
|---|---|---|
| `slug` | ja | kleine letters, cijfers en `-`; identificeert het artikel binnen de omgeving bij een volgende import (bijwerken i.p.v. toevoegen). In de link staat het nummer van het artikel; de slug is daar alleen de leesbare naam. |
| `titel`, `samenvatting`, `inhoud` | ja | |
| `soort` | nee | `werkinstructie` (standaard), `werkafspraak`, `proces` |
| `status` | nee | `concept` (standaard), `gepubliceerd`, `gearchiveerd` |
| `clusters` | nee | leeg = geldt voor alle clusters |
| `tags`, `zaaktypen` | nee | worden aangemaakt als ze nog niet bestaan |
| `inhoud` | | De hele artikeltekst als HTML (opgeschoond tot: p, strong, em, u, s, sub, sup, ul, ol, li, a, h3, h4, table, blockquote, code, hr, section.sectie, h2.sectie-kop, div.onboarding). Een sectie is `<section class="sectie"><h2 class="sectie-kop">Titel</h2>…</section>`; onboarding-uitleg is `<div class="onboarding">…</div>`. Tekst buiten een sectie is altijd zichtbaar. |
| `versie` | | `4` = sectiekaders (huidig). `3` = sectiekoppen `<h2 class="sectie">`; `2` = `secties[]` met HTML; `1` = `secties[]` in Markdown met apart veld `onboarding`. Oudere versies worden bij import omgezet. |

Een voorbeeld met negen artikelen staat in [demo/voorbeeldinhoud.json](../demo/voorbeeldinhoud.json). Losse Word-documenten importeer je eenvoudiger via **Beheer → Artikelen → Importeren uit Word** (zie [functioneel-beheer](functioneel-beheer.md)); dit JSON-formaat is bedoeld voor bulk en voor uitwisseling tussen installaties.
