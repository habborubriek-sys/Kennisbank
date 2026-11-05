"""Zoeken met PostgreSQL full-text search (Nederlandse woordstammen, prefix-matching).

Voor een kennisbank van enkele honderden tot duizenden artikelen is dit ruim voldoende
en vergt het geen aparte zoekmachine.
"""

import re

from django.contrib.postgres.aggregates import StringAgg
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import F, OuterRef, Subquery, TextField, Value
from django.db.models.functions import Coalesce, Concat

from .models import Artikel, Sectie

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


def _tekst_van(model_qs, expressie):
    """Alle teksten van gerelateerde rijen samengevoegd tot één string (subquery per artikel)."""
    return Coalesce(
        Subquery(
            model_qs.values("_groep").annotate(t=StringAgg(expressie, " ", output_field=TextField())).values("t")[:1],
            output_field=TextField(),
        ),
        Value("", output_field=TextField()),
        output_field=TextField(),
    )


def artikel_vector():
    """Eén zoekdocument per artikel: titel en tags wegen het zwaarst, dan samenvatting, dan secties."""
    secties = Sectie.objects.filter(artikel=OuterRef("pk")).annotate(_groep=F("artikel"))
    tags = Artikel.tags.through.objects.filter(artikel=OuterRef("pk")).annotate(_groep=F("artikel"))
    sectietekst = _tekst_van(
        secties, Concat("kop", Value(" "), "inhoud", Value(" "), "onboarding", output_field=TextField())
    )
    tagtekst = _tekst_van(tags, F("tag__naam"))
    return (
        SearchVector("titel", weight="A", config=CONFIG)
        + SearchVector(tagtekst, weight="A", config=CONFIG)
        + SearchVector("samenvatting", weight="B", config=CONFIG)
        + SearchVector(sectietekst, weight="C", config=CONFIG)
    )


def zoek_artikelen(queryset, tekst: str):
    """Filter en sorteer artikelen op relevantie. Geeft de queryset ongewijzigd terug zonder zoektekst."""
    vraag = zoekvraag(tekst, alle_termen=True)
    if vraag is None:
        return queryset
    treffers = list(
        queryset.annotate(document=artikel_vector())
        .filter(document=vraag)
        .annotate(rang=SearchRank(F("document"), vraag))
        .order_by("-rang", "titel")
    )
    return treffers


def zoek_secties(artikelen_qs, tekst: str, zaaktype: str | None = None, aantal: int = 5):
    """Meest relevante secties voor een vraag, voor de assistent."""
    vraag = zoekvraag(tekst, alle_termen=False)
    if vraag is None:
        return []
    vector = (
        SearchVector("artikel__titel", weight="A", config=CONFIG)
        + SearchVector("kop", weight="A", config=CONFIG)
        + SearchVector("inhoud", weight="B", config=CONFIG)
        + SearchVector("onboarding", weight="C", config=CONFIG)
        + SearchVector("artikel__samenvatting", weight="D", config=CONFIG)
    )
    kandidaten = list(
        Sectie.objects.filter(artikel__in=artikelen_qs)
        .annotate(document=vector)
        .filter(document=vraag)
        .annotate(rang=SearchRank(F("document"), vraag))
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
        # Zwakke treffers weglaten: alleen secties die in de buurt komen van de beste.
        grens = kandidaten[0].rang * 0.25
        kandidaten = [s for s in kandidaten if s.rang >= grens]
    return kandidaten[:aantal]
