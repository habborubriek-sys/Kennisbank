"""Zoeken met PostgreSQL full-text search (Nederlandse woordstammen, prefix-matching).

De zoekdocumenten staan opgeslagen in Artikel.zoekvector en Sectie.zoekvector (met GIN-index) en
worden bijgewerkt in diensten.herbouw_secties. Zoeken is daardoor een indexopzoeking, ook bij
duizenden artikelen; er is geen aparte zoekmachine nodig.
"""

import re

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import F

from .models import Sectie

CONFIG = "dutch"
_WOORD = re.compile(r"[\w]+", re.UNICODE)


def termen(tekst: str) -> list[str]:
    return [w.lower() for w in _WOORD.findall(tekst or "") if len(w) > 1][:12]


def zoekvraag(tekst: str, alle_termen: bool) -> SearchQuery | None:
    """Bouw een tsquery met prefix-matching. Zoekbalk: alle termen (AND). Assistent: OR."""
    woorden = termen(tekst)
    if not woorden:
        return None
    teken = " & " if alle_termen else " | "
    raw = teken.join(f"{w}:*" for w in woorden)
    return SearchQuery(raw, search_type="raw", config=CONFIG)


def zoek_artikelen(queryset, tekst: str):
    """Filter en sorteer artikelen op relevantie. Geeft de queryset ongewijzigd terug zonder zoektekst."""
    vraag = zoekvraag(tekst, alle_termen=True)
    if vraag is None:
        return queryset
    return list(
        queryset.filter(zoekvector=vraag).annotate(rang=SearchRank(F("zoekvector"), vraag)).order_by("-rang", "titel")
    )


#: Ondergrens voor de score van een sectietreffer. Onder deze waarde is het verband met de vraag zo
#: zwak dat "dit staat in …" misleidend is; de assistent zegt dan liever dat hij het niet weet.
MINIMALE_RANG = 0.05


def zoek_secties(artikelen_qs, tekst: str, zaaktype: str | None = None, aantal: int = 5):
    """Meest relevante secties voor een vraag, voor de assistent."""
    vraag = zoekvraag(tekst, alle_termen=False)
    if vraag is None:
        return []
    kandidaten = list(
        Sectie.objects.filter(artikel__in=artikelen_qs, zoekvector=vraag)
        .exclude(inhoud__regex=r"^\s*$")  # een sectie zonder tekst valt niets uit te citeren
        .annotate(rang=SearchRank(F("zoekvector"), vraag))
        .select_related("artikel")
        .prefetch_related("artikel__zaaktypen")
        .order_by("-rang")[: aantal * 4]
    )
    if zaaktype:
        for s in kandidaten:
            if any(z.code == zaaktype for z in s.artikel.zaaktypen.all()):
                s.rang *= 1.5
        kandidaten.sort(key=lambda s: -s.rang)
    if kandidaten:
        # Zwakke treffers weglaten: alleen secties die in de buurt komen van de beste, én die op
        # zichzelf iets voorstellen. Zonder die absolute ondergrens levert één toevallig woord uit de
        # titel al een "dit staat in …" op.
        grens = max(kandidaten[0].rang * 0.25, MINIMALE_RANG)
        kandidaten = [s for s in kandidaten if s.rang >= grens]
    return kandidaten[:aantal]
