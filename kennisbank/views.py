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
