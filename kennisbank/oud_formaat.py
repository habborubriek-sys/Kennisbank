"""Omzetting van oudere inhoudsvormen (migratie 0004 en importformaat versie 3). Wijzig dit bestand niet."""

import re

_KOP = re.compile(r'<h2 class="sectie">(.*?)</h2>', re.S)


def koppen_naar_kaders(html: str) -> str:
    """Oude vorm: alles na een sectiekop tot de volgende sectiekop wordt een sectiekader."""
    if not html or '<h2 class="sectie">' not in html:
        return html or ""
    delen = _KOP.split(html)
    uit = delen[0]
    for i in range(1, len(delen), 2):
        kop = re.sub(r"<[^>]+>", "", delen[i]).strip()
        inhoud = delen[i + 1] if i + 1 < len(delen) else ""
        uit += f'<section class="sectie"><h2 class="sectie-kop">{kop}</h2>{inhoud}</section>'
    return uit
