"""De pagina Hulp (1.36.0): uitleg over het werken met de kennisbank, per rol.

Wens van Alex (17 november 2026): een knop Hulp, met artikelen die los staan van de kennisartikelen, op een
eigen pagina met links een menu en rechts het artikel. Wat je ziet hangt af van je rol, als een trap:
medewerker -> reviewer -> redacteur -> functioneel beheerder. Wie hoger staat, ziet ook wat eronder staat.

De artikelen zijn niet geheim (de documentatie staat ook in de repository); de trap is er voor het overzicht.
Toch geeft een artikel boven je eigen niveau een 404, zodat het menu en de adressen hetzelfde verhaal vertellen.
"""

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.utils.safestring import mark_safe

from . import review
from .hulp_inhoud import STANDAARD
from .models import HULPNIVEAU, Artikel, Hulpartikel, Hulpdoelgroep, Omgeving, Status
from .rechten import rechten

#: Waar de knop Hulp staat -> het hoofdstuk dat daar het meest voor de hand ligt.
BIJ = {
    "kennisbank": Hulpdoelgroep.MEDEWERKER,
    "review": Hulpdoelgroep.REVIEWER,
    "werkplek": Hulpdoelgroep.REDACTEUR,
    "beheer": Hulpdoelgroep.BEHEERDER,
}


def niveau_van(gebruiker, r=None) -> int:
    """Hoe hoog iemand op de trap staat: 1 medewerker, 2 reviewer, 3 redacteur, 4 functioneel beheerder."""
    if gebruiker.is_superuser:
        return 4
    if r is not None and r.is_redacteur:
        return 3
    if review.is_reviewer(gebruiker):
        return 2
    return 1


def zichtbaar_voor(niveau: int):
    groepen = [d for d, n in HULPNIVEAU.items() if n <= niveau]
    return Hulpartikel.objects.filter(zichtbaar=True, doelgroep__in=groepen)


def laad_standaard(terugzetten=()) -> dict:
    """Zet de meegeleverde hulpartikelen in de database.

    - Bestaat een artikel niet, dan wordt het gemaakt.
    - Bestaat het en is het niet aangepast, dan krijgt het de tekst van deze versie.
    - Is het in het beheer aangepast, dan blijft het zoals het is; behalve als de slug in `terugzetten` staat.
    Een artikel dat de beheerder zelf heeft toegevoegd, wordt nooit geraakt; een meegeleverd artikel dat hij heeft
    verwijderd, komt terug (verbergen is daarvoor de weg).
    """
    bestaand = {h.slug: h for h in Hulpartikel.objects.filter(slug__in=[s["slug"] for s in STANDAARD])}
    uit = {"nieuw": 0, "bijgewerkt": 0, "overgeslagen": 0}
    for s in STANDAARD:
        h = bestaand.get(s["slug"])
        if h is None:
            Hulpartikel.objects.create(**s)
            uit["nieuw"] += 1
            continue
        if h.aangepast and s["slug"] not in terugzetten:
            uit["overgeslagen"] += 1
            continue
        for veld in ("titel", "doelgroep", "volgorde", "tekst"):
            setattr(h, veld, s[veld])
        if s["slug"] in terugzetten:
            h.zichtbaar = True
        h.aangepast = False
        h.save()
        uit["bijgewerkt"] += 1
    return uit


def _werkafspraken(r):
    """De eigen werkafspraken van de omgevingen die deze gebruiker mag lezen (H4)."""
    omgevingen = Omgeving.objects.filter(
        pk__in=r.leesbare_omgevingen,
        werkafspraken_artikel__isnull=False,
        werkafspraken_artikel__status=Status.GEPUBLICEERD,
    ).select_related("werkafspraken_artikel")
    uit = []
    for o in omgevingen:
        a = o.werkafspraken_artikel
        if a.omgeving_id != o.pk:  # een artikel dat later naar een andere omgeving is verhuisd
            continue
        uit.append({"omgeving": o.naam, "titel": a.titel, "url": f"/artikel/{a.pk}/{a.slug}"})
    return uit


@login_required
def pagina(request, slug=None):
    r = rechten(request)
    niveau = niveau_van(request.user, r)
    artikelen = list(zichtbaar_voor(niveau))
    # Het menu: je eigen rol bovenaan, daaronder wat eronder ligt.
    groepen = []
    for doelgroep in sorted(HULPNIVEAU, key=HULPNIVEAU.get, reverse=True):
        eigen = [a for a in artikelen if a.doelgroep == doelgroep]
        if eigen:
            groepen.append({"sleutel": doelgroep, "naam": Hulpdoelgroep(doelgroep).label, "artikelen": eigen})

    if slug:
        huidig = next((a for a in artikelen if a.slug == slug), None)
        if huidig is None:
            raise Http404("Dit hulpartikel bestaat niet, of is niet voor jouw rol.")
    else:
        # Zonder slug: het eerste artikel van het hoofdstuk dat past bij waar je vandaan komt. Ligt dat boven je
        # eigen rol, dan zit het niet in `artikelen` en val je terug op je eigen rol. Zonder herkomst ook.
        gevraagd = BIJ.get(request.GET.get("bij", ""))
        voorkeur = [gevraagd] if gevraagd else []
        huidig = None
        for doelgroep in voorkeur + [g["sleutel"] for g in groepen]:
            huidig = next((a for a in artikelen if a.doelgroep == doelgroep), None)
            if huidig:
                break

    return render(
        request,
        "kennisbank/hulp.html",
        {
            "app_naam": settings.KB_APP_NAAM,
            "groepen": groepen,
            "huidig": huidig,
            "tekst": mark_safe(huidig.tekst) if huidig else "",  # noqa: S308 - opgeschoond bij opslaan (schoon)
            "werkafspraken": _werkafspraken(r),
            "mag_bewerken": request.user.is_superuser,
        },
    )


def werkafspraken_keuze(omgeving_id):
    """De artikelen die bij een omgeving als werkafspraken kunnen worden aangewezen."""
    return Artikel.objects.filter(omgeving_id=omgeving_id, status=Status.GEPUBLICEERD).order_by("titel")
