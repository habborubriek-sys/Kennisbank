from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie


def _shell(request, embed=False, zaaktype=""):
    return render(
        request,
        "kennisbank/app.html",
        {
            "app_naam": settings.KB_APP_NAAM,
            "embed": embed,
            "zaaktype": zaaktype,
            "demo": settings.KB_DEMO_MODUS,
            "auth_modus": settings.KB_AUTH_MODUS,
            "contact": settings.KB_CONTACT,  # voor het <noscript>-blok; de app haalt hem zelf via /ik
        },
    )


@never_cache
@ensure_csrf_cookie
@login_required
def app(request, **kwargs):
    """Alle gewone pagina's (/, /artikel/<slug>, /favorieten, ...) laden dezelfde frontend."""
    return _shell(request)


@never_cache
@ensure_csrf_cookie
def ingebed(request, code):
    """Compacte weergave voor in een iframe in het zaaksysteem.

    Bewust zonder login_required: identity providers weigeren hun loginpagina in een iframe.
    De frontend toont bij een ontbrekende sessie een knop die inloggen in een nieuw venster opent.
    """
    return _shell(request, embed=True, zaaktype=code)


@login_required
def oude_artikel_link(request, slug):
    """Links van vóór versie 1.2 (/artikel/<slug>) doorverwijzen naar de nieuwe link op nummer."""
    from django.shortcuts import redirect

    from .models import Artikel
    from .rechten import rechten

    kandidaten = [a for a in Artikel.objects.filter(slug=slug) if rechten(request).mag_lezen(a)]
    if not kandidaten:
        raise Http404
    # Nieuwe artikelen krijgen een unieke slug, maar in oude gegevens kunnen dubbelen staan. Dan is
    # doorverwijzen naar het laatst bijgewerkte artikel beter dan iedereen een 404 geven.
    kandidaten.sort(key=lambda a: a.gewijzigd_op or a.pk, reverse=True)
    return redirect(kandidaten[0].get_absolute_url(), permanent=len(kandidaten) == 1)


def login_voltooid(request):
    """Wordt in een popup geopend vanuit de ingebedde weergave; meldt de login terug aan het iframe."""
    if not request.user.is_authenticated:
        return redirect_to_login("/login-voltooid/")
    return render(request, "kennisbank/login_voltooid.html")


def demo_zaaksysteem(request):
    if not settings.KB_DEMO_MODUS:
        raise Http404
    return render(request, "kennisbank/demo_zaaksysteem.html", {"app_naam": settings.KB_APP_NAAM})


class Inloggen(auth_views.LoginView):
    template_name = "kennisbank/inloggen.html"
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(app_naam=settings.KB_APP_NAAM, demo=settings.KB_DEMO_MODUS)
        return ctx


def beheer_login_via_idp(request):
    """In OIDC-modus heeft het beheer geen eigen inlogscherm: altijd via de identity provider."""
    from django.shortcuts import redirect
    from django.utils.http import url_has_allowed_host_and_scheme

    volgende = request.GET.get("next") or "/beheer/"
    if not url_has_allowed_host_and_scheme(volgende, allowed_hosts=None):  # alleen paden op deze site
        volgende = "/beheer/"
    if not request.user.is_authenticated:
        return redirect_to_login(volgende)
    if request.user.is_staff:
        return redirect(volgende)
    # Ingelogd, maar geen redacteur of beheerder: geen loginscherm tonen (zou een lus geven), maar uitleggen.
    return HttpResponseForbidden(
        render_to_string(
            "kennisbank/geen_beheer.html",
            {"app_naam": settings.KB_APP_NAAM, "gebruiker": request.user.get_username(), "uitlog_url": "/oidc/logout/"},
            request=request,
        )
    )


def csrf_verlopen(request, reason=""):
    """Eigen pagina bij een mislukte CSRF-controle, in plaats van het Engelse Django-scherm.

    Komt in de praktijk vooral voor als een bewerkscherm lang openstaat en de redacteur intussen in
    een ander tabblad opnieuw inlogt: de code in het oude scherm hoort dan niet meer bij de sessie.
    """
    return HttpResponseForbidden(
        render_to_string("kennisbank/csrf_verlopen.html", {"app_naam": settings.KB_APP_NAAM}, request=request)
    )


# --- Foutpagina's (400, 403, 404, 500) -------------------------------------------------
#
# Zonder deze functies toont Django buiten de app zijn eigen kale, Engelse pagina ("Not Found",
# "Server Error (500)") zonder weg terug. Onder /api/ blijft het antwoord JSON, zoals de rest van de API.

FOUTEN = {
    400: (
        "Dit verzoek kon niet worden verwerkt",
        [
            "De kennisbank kreeg iets binnen wat hij niet kon verwerken. Dat gebeurt bijvoorbeeld bij een "
            "heel groot artikel dat in één keer wordt opgeslagen, of bij een adres dat niet klopt.",
        ],
        "Ga terug met de terugknop van je browser. Gebeurde dit bij het opslaan van een artikel, kopieer "
        "je tekst dan voor de zekerheid en meld het bij de beheerder van de kennisbank.",
    ),
    403: (
        "Hier heb je geen toegang toe",
        ["Je bent ingelogd, maar deze pagina hoort niet bij jouw rechten in de kennisbank."],
        "Denk je dat je hier wel bij zou moeten kunnen? Vraag het na bij de beheerder van de kennisbank.",
    ),
    404: (
        "Deze pagina bestaat niet",
        [
            "Het adres klopt niet, of wat hier stond is verplaatst of verwijderd.",
            "Kwam je hier via een link in een document of e-mail? Zoek het artikel dan op in de kennisbank.",
        ],
        "",
    ),
    500: (
        "Er ging iets mis",
        [
            "Dit ligt niet aan jou: er ging op de server iets fout. Wat je net deed, is mogelijk niet opgeslagen.",
        ],
        "Probeer het over een paar minuten opnieuw. Blijft het gebeuren, meld het dan bij de beheerder van de "
        "kennisbank, met het tijdstip en wat je aan het doen was.",
    ),
}


def _foutpagina(request, code):
    from django.http import HttpResponse, JsonResponse

    titel, uitleg, hint = FOUTEN[code]
    if request is not None and request.path.startswith("/api/"):
        return JsonResponse({"detail": titel + "."}, status=code)
    try:
        beheer = bool(request is not None and getattr(request, "user", None) and request.user.is_staff)
    except Exception:  # noqa: BLE001 - bij een 500 kan zelfs de sessie het probleem zijn
        beheer = False
    try:
        html = render_to_string(
            "kennisbank/fout.html",
            {"app_naam": settings.KB_APP_NAAM, "titel": titel, "uitleg": uitleg, "hint": hint, "code": code,
             "beheer": beheer},
        )
    except Exception:  # noqa: BLE001 - een foutpagina mag zelf nooit omvallen
        html = (
            f"<!doctype html><html lang='nl'><meta charset='utf-8'><title>{titel}</title>"
            f"<h1>{titel}</h1><p><a href='/'>Naar de kennisbank</a></p></html>"
        )
    return HttpResponse(html, status=code)


def fout_400(request, exception=None):
    return _foutpagina(request, 400)


def fout_403(request, exception=None):
    return _foutpagina(request, 403)


def fout_404(request, exception=None):
    return _foutpagina(request, 404)


def fout_500(request):
    return _foutpagina(request, 500)
