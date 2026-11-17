"""De pagina Hulp (1.36.0): uitleg over het werken met de kennisbank, per rol.

Wens van Alex (17 november 2026): een knop Hulp, met artikelen die los staan van de kennisartikelen, op een
eigen pagina met links een menu en rechts het artikel. Wat je ziet hangt af van je rol, als een trap:
medewerker -> reviewer -> redacteur -> functioneel beheerder. Wie hoger staat, ziet ook wat eronder staat.

De artikelen zijn niet geheim (de documentatie staat ook in de repository); de trap is er voor het overzicht.
Toch geeft een artikel boven je eigen niveau een 404, zodat het menu en de adressen hetzelfde verhaal vertellen.
"""

import html as htmllib
import re
from functools import lru_cache

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.http import Http404
from django.shortcuts import render
from django.templatetags.static import static
from django.utils.safestring import mark_safe

from . import review
from .hulp_inhoud import SCHEMAS, STANDAARD
from .models import HULPNIVEAU, Artikel, Hulpartikel, Hulpdoelgroep, Omgeving, Status
from .rechten import rechten

#: Waar de knop Hulp staat -> het hoofdstuk dat daar het meest voor de hand ligt.
BIJ = {
    "kennisbank": Hulpdoelgroep.MEDEWERKER,
    "review": Hulpdoelgroep.REVIEWER,
    "werkplek": Hulpdoelgroep.REDACTEUR,
    "beheer": Hulpdoelgroep.BEHEERDER,
}


# --- Beeld in een hulpartikel (1.37.0) ----------------------------------------------------------------------------
#
# Een hulpartikel is gewone, opgeschoonde HTML: daar past geen <img> in, en dat willen we ook niet openzetten.
# Een schermafbeelding of schema staat daarom als een regel tekst in het artikel:
#
#     [[beeld:werkplek|De werkplek, met links de bakken]]
#     [[schema:concept-tot-publicatie]]
#
# Bij het tonen wordt zo'n regel vervangen. Alleen namen die het pakket kent doen iets: een schermafbeelding moet
# als bestand bestaan in static/kennisbank/hulp/, een schema in SCHEMAS. Een onbekende naam verdwijnt. Zo kan de
# beheerder een beeld verplaatsen of weghalen in de editor, zonder dat er iets onveiligs in de pagina kan komen.

_TEKEN = re.compile(r"<p>\s*\[\[(beeld|schema):([a-z0-9-]+)(?:\|([^\]<]*))?\]\]\s*</p>")


@lru_cache(maxsize=256)
def beeld_bestaat(naam: str) -> bool:
    return bool(finders.find(f"kennisbank/hulp/{naam}.png"))


def _beeld(naam: str, bijschrift: str) -> str:
    if not beeld_bestaat(naam):
        return ""
    tekst = htmllib.escape(htmllib.unescape(bijschrift or "").strip())
    onderschrift = f"<figcaption>{tekst}</figcaption>" if tekst else ""
    bron = static(f"kennisbank/hulp/{naam}.png")
    return (
        f'<figure class="hulp-beeld"><a href="{bron}" target="_blank" rel="noopener">'
        f'<img src="{bron}" alt="Schermafbeelding: {tekst or naam}" loading="lazy">'
        f'<span class="visually-hidden"> (opent groot in een nieuw tabblad)</span></a>{onderschrift}</figure>'
    )


def _schema(naam: str) -> str:
    s = SCHEMAS.get(naam)
    if not s:
        return ""
    e = htmllib.escape
    stappen = "".join(
        f'<li><span class="hulp-rol hulp-rol-{re.sub(r"[^a-z]", "", rol.lower())}">{e(rol)}</span>'
        f'<strong class="hulp-stap-kop">{e(kop)}</strong><span class="hulp-stap-tekst">{e(tekst)}</span></li>'
        for rol, kop, tekst in s["stappen"]
    )
    noot = f'<p class="hulp-noot">{e(s["noot"])}</p>' if s.get("noot") else ""
    return (
        f'<figure class="hulp-schema"><figcaption>{e(s["titel"])}</figcaption>'
        f'<ol class="hulp-stroom">{stappen}</ol>{noot}</figure>'
    )


def verrijk(tekst: str) -> str:
    """Vervang de regels [[beeld:…]] en [[schema:…]] door de schermafbeelding of het schema."""

    def vervang(m):
        return _beeld(m.group(2), m.group(3) or "") if m.group(1) == "beeld" else _schema(m.group(2))

    return _TEKEN.sub(vervang, tekst)


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
            # Veilig: de tekst is opgeschoond bij opslaan (schoon); verrijk voegt alleen eigen, ontsnapte HTML toe.
            "tekst": mark_safe(verrijk(huidig.tekst)) if huidig else "",  # noqa: S308
            "werkafspraken": _werkafspraken(r),
            "mag_bewerken": request.user.is_superuser,
        },
    )


def werkafspraken_keuze(omgeving_id):
    """De artikelen die bij een omgeving als werkafspraken kunnen worden aangewezen."""
    return Artikel.objects.filter(omgeving_id=omgeving_id, status=Status.GEPUBLICEERD).order_by("titel")
