"""Import en export van artikelen in een eenvoudig JSON-formaat (zie docs/importformaat.md)."""

import re

from django.db import transaction

from . import diensten
from .inhoud import markdown_naar_html, onboarding_blok, schoon, sectie
from .models import Artikel, Cluster, Omgeving, Soort, Status, Tag, Zaaktype, normaliseer_tag

FORMAAT = "kennisbank-import"
# 1 = secties in Markdown + onboarding-veld; 2 = secties in HTML; 3 = één tekst met sectiekoppen (h2.sectie);
# 4 = één tekst met sectiekaders (<section class="sectie">)
VERSIE = 4


def _artikel_inhoud(a: dict, versie: int) -> str:
    """De artikeltekst uit het importbestand: versie 3 heeft 'inhoud'; oudere versies hebben 'secties'."""
    if versie >= 4:
        return schoon(a.get("inhoud", ""))
    if versie == 3 or "inhoud" in a:
        from .oud_formaat import koppen_naar_kaders

        return schoon(koppen_naar_kaders(a.get("inhoud", "")))
    return "".join(sectie(s["kop"], _sectie_inhoud(s, versie)) for s in a.get("secties", []))


def _sectie_inhoud(s: dict, versie: int) -> str:
    """Inhoud van een sectie uit het importbestand, altijd als opgeschoonde HTML."""
    if versie >= 2:
        html = schoon(s.get("inhoud", ""))
        if s.get("onboarding"):
            html = onboarding_blok(s["onboarding"]) + html
        return html
    html = markdown_naar_html(s.get("inhoud", ""))
    if s.get("onboarding"):
        html = onboarding_blok(markdown_naar_html(s["onboarding"])) + html
    return html


class ImportFout(ValueError):
    pass


def _controleer(data):
    if data.get("formaat") != FORMAAT:
        raise ImportFout(f"Onbekend formaat; verwacht 'formaat': '{FORMAAT}'.")
    if data.get("versie", 1) not in (1, 2, 3, 4):
        raise ImportFout("Onbekende versie van het importformaat; ondersteund: 1 t/m 4.")
    if not data.get("omgeving", {}).get("slug"):
        raise ImportFout("'omgeving.slug' ontbreekt.")
    soorten = {s.value for s in Soort}
    statussen = {s.value for s in Status}
    for i, a in enumerate(data.get("artikelen", []), 1):
        for veld in ("slug", "titel", "samenvatting"):
            if not a.get(veld):
                raise ImportFout(f"Artikel {i}: '{veld}' ontbreekt.")
        if not a.get("inhoud") and not a.get("secties"):
            raise ImportFout(f"Artikel {a['slug']}: 'inhoud' ontbreekt.")
        if a.get("soort", "werkinstructie") not in soorten:
            raise ImportFout(f"Artikel {a['slug']}: onbekende soort '{a['soort']}'.")
        if a.get("status", "concept") not in statussen:
            raise ImportFout(f"Artikel {a['slug']}: onbekende status '{a['status']}'.")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,119}", str(a["slug"])):
            raise ImportFout(
                f"Artikel {a['slug']!r}: slug mag alleen kleine letters, cijfers en '-' bevatten (max. 120 tekens)."
            )


@transaction.atomic
def importeer(data, gebruiker=None, toelichting="Import", kleine_correctie=False) -> dict:
    """Voegt artikelen toe of werkt ze bij (op basis van omgeving + slug). Geeft tellingen terug.

    Een gewijzigd gepubliceerd artikel krijgt een nieuwe versie met `toelichting`; medewerkers zien die als
    wijzigingsmelding en favoriet-houders krijgen een e-mail — tenzij `kleine_correctie` aan staat.
    """
    _controleer(data)
    versie = int(data.get("versie", 1))
    o = data["omgeving"]
    omgeving, _ = Omgeving.objects.update_or_create(
        slug=o["slug"], defaults={"naam": o.get("naam", o["slug"]), "beschrijving": o.get("beschrijving", "")}
    )
    for i, naam in enumerate(data.get("clusters", [])):
        Cluster.objects.update_or_create(naam=naam, defaults={"volgorde": i})
    for z in data.get("zaaktypen", []):
        Zaaktype.objects.update_or_create(code=z["code"], defaults={"naam": z.get("naam", z["code"])})

    telling = {"nieuw": 0, "bijgewerkt": 0, "nieuwe_versies": 0}
    for a in data.get("artikelen", []):
        artikel, nieuw = Artikel.objects.update_or_create(
            omgeving=omgeving,
            slug=a["slug"],
            defaults={
                "titel": a["titel"],
                "inhoud": _artikel_inhoud(a, versie),
                "samenvatting": a["samenvatting"],
                "soort": a.get("soort", Soort.WERKINSTRUCTIE),
                "status": a.get("status", Status.CONCEPT),
                "eigenaar": a.get("eigenaar", "Procesmanagement"),
            },
        )
        telling["nieuw" if nieuw else "bijgewerkt"] += 1
        artikel.clusters.set([Cluster.objects.get_or_create(naam=n)[0] for n in a.get("clusters", [])])
        tagnamen = sorted({normaliseer_tag(n) for n in a.get("tags", [])} - {""})
        artikel.tags.set([Tag.objects.get_or_create(naam=n)[0] for n in tagnamen])
        artikel.zaaktypen.set(
            [Zaaktype.objects.get_or_create(code=c, defaults={"naam": c})[0] for c in a.get("zaaktypen", [])]
        )
        diensten.herbouw_secties(artikel)
        if diensten.registreer_publicatie(artikel, gebruiker, toelichting, kleine_correctie=kleine_correctie):
            telling["nieuwe_versies"] += 1
    return telling


def exporteer(omgeving: Omgeving) -> dict:
    artikelen = (
        Artikel.objects.filter(omgeving=omgeving)
        .prefetch_related("clusters", "tags", "zaaktypen")
        .order_by("slug", "id")
    )
    return {
        "formaat": FORMAAT,
        "versie": VERSIE,
        "omgeving": {"slug": omgeving.slug, "naam": omgeving.naam, "beschrijving": omgeving.beschrijving},
        "clusters": list(Cluster.objects.values_list("naam", flat=True)),
        "zaaktypen": list(Zaaktype.objects.values("code", "naam")),
        "artikelen": [
            {
                "slug": a.slug,
                "titel": a.titel,
                "samenvatting": a.samenvatting,
                "soort": a.soort,
                "status": a.status,
                "eigenaar": a.eigenaar,
                "clusters": [c.naam for c in a.clusters.all()],
                "tags": [t.naam for t in a.tags.all()],
                "zaaktypen": [z.code for z in a.zaaktypen.all()],
                "inhoud": a.inhoud,
            }
            for a in artikelen
        ],
    }
