"""De startpagina van het beheer: het werkoverzicht van een redacteur.

In plaats van Django's lijst met onderdelen ziet een redacteur eerst wat er voor hem ligt: de bakken
met verbetervoorstellen, zijn concepten en kladversies, en de artikelen die herzien moeten worden. De
lijst met onderdelen staat eronder ("Alle onderdelen"), zodat niets onbereikbaar wordt.

Alles hier is alleen lezen, en beperkt tot de omgevingen waar de gebruiker redacteur is. Het aantal
databasevragen is vast, hoe groot de kennisbank ook is (bewaakt door een test).
"""

from django.contrib import admin
from django.db.models import Count, Min
from django.urls import reverse
from django.utils import timezone

from . import diensten
from .models import Artikel, Kladversie, Omgeving, Status, Verbetervoorstel, VoorstelStatus
from .rechten import rechten

#: Hoeveel concepten en kladversies er op de startpagina staan; de rest zit achter "alle ...".
TOP = 5

OPEN = [VoorstelStatus.NIEUW, VoorstelStatus.IN_BEHANDELING]


def _dagen(moment) -> int | None:
    if not moment:
        return None
    return max(0, (timezone.now() - moment).days)


def werkoverzicht(request) -> dict:
    r = rechten(request)
    omgevingen = sorted(r.redactie_omgevingen)
    voorstellen_url = reverse("admin:kennisbank_verbetervoorstel_changelist")
    artikelen_url = reverse("admin:kennisbank_artikel_changelist")
    open_qs = Verbetervoorstel.objects.filter(status__in=OPEN, artikel__omgeving_id__in=omgevingen)

    namen = dict(Omgeving.objects.filter(pk__in=omgevingen).values_list("pk", "naam"))
    per_omgeving = {
        rij["artikel__omgeving_id"]: rij
        for rij in open_qs.filter(eigenaar__isnull=True)
        .values("artikel__omgeving_id")
        .annotate(aantal=Count("pk"), oudste=Min("ingediend_op"))
    }
    gezamenlijk = [
        {
            "naam": namen[oid],
            "aantal": per_omgeving.get(oid, {}).get("aantal", 0),
            "oudste_dagen": _dagen(per_omgeving.get(oid, {}).get("oudste")),
            "url": f"{voorstellen_url}?bak=gezamenlijk&artikel__omgeving__id__exact={oid}",
        }
        for oid in sorted(namen, key=lambda o: namen[o].lower())
    ]

    mijn = open_qs.filter(eigenaar=request.user).aggregate(
        aantal=Count("pk"), oudste=Min("eigenaar_sinds")
    )
    mijn_nieuw = open_qs.filter(eigenaar=request.user, eigenaar_gezien_op__isnull=True).count()
    collegas = [
        {
            "naam": f"{rij['eigenaar__first_name']} {rij['eigenaar__last_name']}".strip() or rij["eigenaar__username"],
            "aantal": rij["aantal"],
            "oudste_dagen": _dagen(rij["oudste"]),
            "url": f"{voorstellen_url}?bak=u{rij['eigenaar_id']}",
        }
        for rij in open_qs.exclude(eigenaar__isnull=True)
        .exclude(eigenaar=request.user)
        .values("eigenaar_id", "eigenaar__first_name", "eigenaar__last_name", "eigenaar__username")
        .annotate(aantal=Count("pk"), oudste=Min("eigenaar_sinds"))
        .order_by("eigenaar__first_name", "eigenaar__last_name", "eigenaar__username")
    ]

    concepten_qs = Artikel.objects.filter(status=Status.CONCEPT, omgeving_id__in=omgevingen)
    concepten = list(concepten_qs.order_by("-gewijzigd_op").values("pk", "titel", "gewijzigd_op")[:TOP])
    for c in concepten:
        c["url"] = reverse("admin:kennisbank_artikel_change", args=[c["pk"]])

    klad = list(
        Kladversie.objects.filter(gebruiker=request.user, afgesloten_op__isnull=True)
        .exclude(velden={})
        .select_related("artikel")
        .order_by("-bijgewerkt_op")[:TOP]
    )
    kladversies = [
        {
            "titel": k.titel,
            "bijgewerkt_op": k.bijgewerkt_op,
            "url": reverse("admin:kennisbank_artikel_change", args=[k.artikel_id])
            if k.artikel_id
            else reverse("admin:kennisbank_artikel_add"),
        }
        for k in klad
    ]

    herzien = Artikel.objects.filter(
        status=Status.GEPUBLICEERD, omgeving_id__in=omgevingen, herzien_voor__lt=timezone.localdate()
    ).count()

    return {
        "werkoverzicht": {
            "gezamenlijk": gezamenlijk,
            "mijn": {
                "aantal": mijn["aantal"],
                "nieuw": mijn_nieuw,
                "oudste_dagen": _dagen(mijn["oudste"]),
                "url": f"{voorstellen_url}?bak=mijn&ligt=open",
            },
            "collegas": collegas,
            "concepten": concepten,
            "concepten_aantal": concepten_qs.count(),
            "concepten_url": f"{artikelen_url}?status__exact={Status.CONCEPT}",
            "kladversies": kladversies,
            "herzien": herzien,
            "herzien_url": f"{artikelen_url}?herziening=te_laat",
            "nieuw_artikel_url": reverse("admin:kennisbank_artikel_add"),
            "nieuw_bericht_url": reverse("admin:kennisbank_bericht_add"),
            "naam": diensten.naam_van(request.user),
        }
    }


def startpagina(request):
    """/beheer/: het werkoverzicht bovenaan, Django's lijst met onderdelen eronder."""
    extra = werkoverzicht(request) if rechten(request).is_redacteur else {}
    return admin.site.index(request, extra_context=extra)
