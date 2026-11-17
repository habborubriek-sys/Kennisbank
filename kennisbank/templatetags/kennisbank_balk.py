"""De bovenbalk die de kennisbank, de reviewpagina's en het beheer delen (1.25.0).

Zelfde blauwe balk, logo en knoppen als de site (app.html), zodat je overal hetzelfde ziet: Kennisbank,
Review, Werkplek, Hulp, je naam en Uitloggen, overal in die volgorde. De knop van de pagina waar je bent,
staat "aan".
"""

from django import template
from django.conf import settings

from kennisbank import review
from kennisbank.diensten import naam_van
from kennisbank.werkoverzicht import alleen_beheerder

register = template.Library()


@register.inclusion_tag("kennisbank/_bovenbalk.html", takes_context=True)
def bovenbalk(context, actief="", titel=""):
    request = context.get("request")
    gebruiker = getattr(request, "user", None)
    ingelogd = bool(gebruiker and gebruiker.is_authenticated)
    knoppen = []
    if ingelogd:
        # 1.36.2 (wens Alex): overal dezelfde volgorde. Eerst de plekken (Kennisbank, Review, Werkplek), dan
        # Hulp. Een knop die niet voor jou is, ontbreekt; de rest schuift daardoor niet van plaats. De site
        # (app.html) houdt dezelfde volgorde aan; de test `test_bovenbalk_1362` bewaakt dat.
        knoppen.append({"naam": "kennisbank", "tekst": "Kennisbank", "url": "/"})
        if review.is_reviewer(gebruiker):
            knoppen.append({"naam": "review", "tekst": "Review", "url": "/review/"})
        if gebruiker.is_staff:
            knoppen.append({"naam": "werkplek", "tekst": "Werkplek", "url": "/beheer/"})
        # 1.36.0: Hulp opent bij het hoofdstuk dat past bij waar je bent. Vanaf de hulppagina zelf zonder herkomst.
        bij = {"review": "review", "werkplek": "werkplek"}.get(actief, "")
        if bij == "werkplek" and alleen_beheerder(gebruiker):
            bij = "beheer"
        knoppen.append({"naam": "hulp", "tekst": "Hulp", "url": "/hulp/" + (f"?bij={bij}" if bij else "")})
    for k in knoppen:
        k["actief"] = k["naam"] == actief
    return {
        "app_naam": settings.KB_APP_NAAM,
        "titel": titel,
        "knoppen": knoppen,
        "ingelogd": ingelogd,
        "naam": naam_van(gebruiker) if ingelogd else "",
        "uitlog_url": "/oidc/logout/" if settings.KB_AUTH_MODUS == "oidc" else "/uitloggen/",
        "csrf_token": context.get("csrf_token"),
        # 1.28.0: de knop Licht/Donker staat op de site en de reviewpagina's, niet in het beheer (altijd licht).
        "thema": actief != "werkplek",

    }
