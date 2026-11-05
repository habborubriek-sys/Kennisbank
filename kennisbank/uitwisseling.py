"""Import en export van artikelen in een eenvoudig JSON-formaat (zie docs/importformaat.md)."""

from django.db import transaction

from . import diensten
from .models import Artikel, Cluster, Omgeving, Sectie, Soort, Status, Tag, Zaaktype

FORMAAT = "kennisbank-import"


class ImportFout(ValueError):
    pass


def _controleer(data):
    if data.get("formaat") != FORMAAT:
        raise ImportFout(f"Onbekend formaat; verwacht 'formaat': '{FORMAAT}'.")
    if not data.get("omgeving", {}).get("slug"):
        raise ImportFout("'omgeving.slug' ontbreekt.")
    soorten = {s.value for s in Soort}
    statussen = {s.value for s in Status}
    for i, a in enumerate(data.get("artikelen", []), 1):
        for veld in ("slug", "titel", "samenvatting", "secties"):
            if not a.get(veld):
                raise ImportFout(f"Artikel {i}: '{veld}' ontbreekt.")
        if a.get("soort", "werkinstructie") not in soorten:
            raise ImportFout(f"Artikel {a['slug']}: onbekende soort '{a['soort']}'.")
        if a.get("status", "concept") not in statussen:
            raise ImportFout(f"Artikel {a['slug']}: onbekende status '{a['status']}'.")


@transaction.atomic
def importeer(data, gebruiker=None, toelichting="Import") -> dict:
    """Voegt artikelen toe of werkt ze bij (op basis van slug). Geeft tellingen terug."""
    _controleer(data)
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
            slug=a["slug"],
            defaults={
                "omgeving": omgeving,
                "titel": a["titel"],
                "samenvatting": a["samenvatting"],
                "soort": a.get("soort", Soort.WERKINSTRUCTIE),
                "status": a.get("status", Status.CONCEPT),
                "eigenaar": a.get("eigenaar", "Procesmanagement"),
            },
        )
        telling["nieuw" if nieuw else "bijgewerkt"] += 1
        artikel.clusters.set([Cluster.objects.get_or_create(naam=n)[0] for n in a.get("clusters", [])])
        artikel.tags.set([Tag.objects.get_or_create(naam=n)[0] for n in a.get("tags", [])])
        artikel.zaaktypen.set(
            [Zaaktype.objects.get_or_create(code=c, defaults={"naam": c})[0] for c in a.get("zaaktypen", [])]
        )
        artikel.secties.all().delete()
        Sectie.objects.bulk_create(
            [
                Sectie(
                    artikel=artikel,
                    volgorde=i,
                    kop=s["kop"],
                    inhoud=s.get("inhoud", ""),
                    onboarding=s.get("onboarding", ""),
                )
                for i, s in enumerate(a["secties"])
            ]
        )
        if diensten.registreer_publicatie(artikel, gebruiker, toelichting):
            telling["nieuwe_versies"] += 1
    return telling


def exporteer(omgeving: Omgeving) -> dict:
    artikelen = (
        Artikel.objects.filter(omgeving=omgeving)
        .prefetch_related("clusters", "tags", "zaaktypen", "secties")
        .order_by("slug")
    )
    return {
        "formaat": FORMAAT,
        "versie": 1,
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
                "secties": [{"kop": s.kop, "inhoud": s.inhoud, "onboarding": s.onboarding} for s in a.secties.all()],
            }
            for a in artikelen
        ],
    }
