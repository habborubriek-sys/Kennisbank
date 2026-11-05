from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
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


def login_voltooid(request):
    """Wordt in een popup geopend vanuit de ingebedde weergave; meldt de login terug aan het iframe."""
    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login

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


def healthz(request):
    """Liveness: het proces draait."""
    return HttpResponse("ok", content_type="text/plain")


def readyz(request):
    """Readiness: de database is bereikbaar en gemigreerd."""
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1 FROM kennisbank_omgeving LIMIT 1")
    except Exception as e:  # noqa: BLE001
        return JsonResponse({"status": "niet gereed", "reden": type(e).__name__}, status=503)
    return JsonResponse({"status": "gereed"})
