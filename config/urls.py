from django.conf import settings
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView

from kennisbank import api, behandelen, views, werkoverzicht

admin.site.site_header = f"{settings.KB_APP_NAAM} – beheer"
admin.site.site_title = f"{settings.KB_APP_NAAM} – beheer"
admin.site.index_title = "Artikelen, voorstellen en toegang"
admin.site.site_url = "/"

api_v1 = [
    path("ik", api.ik, name="api-ik"),
    path("keuzelijsten", api.keuzelijsten, name="api-keuzelijsten"),
    path("artikelen", api.artikelen, name="api-artikelen"),
    path("artikelen/<int:pk>", api.artikel, name="api-artikel"),
    path("artikelen/<int:pk>/weergave", api.weergave, name="api-weergave"),
    path("artikelen/<int:pk>/favoriet", api.favoriet, name="api-favoriet"),
    path("artikelen/<int:pk>/versies", api.versies, name="api-versies"),
    path("artikelen/<int:pk>/gezien", api.wijziging_gezien, name="api-wijziging-gezien"),
    path("wijzigingen/gezien", api.wijzigingen_gezien, name="api-wijzigingen-gezien"),
    path("berichten", api.berichten, name="api-berichten"),
    path("berichten/gezien", api.berichten_gezien, name="api-berichten-gezien"),
    path("voorstellen", api.voorstellen, name="api-voorstellen"),
    path("voorstellen/<int:pk>", api.voorstel, name="api-voorstel"),
    path("voorstellen/<int:pk>/berichten", api.voorstel_bericht, name="api-voorstel-bericht"),
    path("voorstellen/<int:pk>/gelezen", api.voorstel_gelezen, name="api-voorstel-gelezen"),
    path("voorstellen/<int:pk>/steun", api.voorstel_steun, name="api-voorstel-steun"),
    path("statistieken", api.statistieken, name="api-statistieken"),
    path("assistent", api.assistent, name="api-assistent"),
    path("zaaktypen/<str:code>/artikelen", api.zaaktype_artikelen, name="api-zaaktype-artikelen"),
    re_path(r"^.*$", api.niet_gevonden),
]

if settings.KB_AUTH_MODUS == "oidc":
    # Geen wachtwoordschermen: het inlogscherm van het beheer stuurt door naar de identity provider,
    # en /inloggen/ bestaat niet. Zie ook AUTHENTICATION_BACKENDS in settings.py.
    inloggen = [
        path("beheer/login/", views.beheer_login_via_idp),
        path("oidc/", include("mozilla_django_oidc.urls")),
    ]
else:
    inloggen = [
        path("inloggen/", views.Inloggen.as_view(), name="inloggen"),
    ]

urlpatterns = [
    # /healthz en /readyz worden beantwoord door kennisbank.gezondheid.GezondheidMiddleware (vóór de hostnaam-controle).
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularRedocView.as_view(url_name="schema"), name="api-docs"),
    *inloggen,
    # De startpagina van het beheer is het werkoverzicht van de redacteur; vóór admin.site.urls, zodat
    # dit pad wint. admin_view zorgt voor dezelfde inlogcontrole als de rest van het beheer.
    path("beheer/", admin.site.admin_view(werkoverzicht.werkplek), name="beheer-start"),
    path("beheer/werkplek/actie/", admin.site.admin_view(werkoverzicht.werkplek_actie), name="beheer-werkplek-actie"),
    path("beheer/voorstel/<int:pk>/", admin.site.admin_view(behandelen.voorstel_scherm), name="beheer-voorstel"),
    path("beheer/", admin.site.urls),
    path("uitloggen/", LogoutView.as_view(), name="uitloggen"),
    path("login-voltooid/", views.login_voltooid, name="login-voltooid"),
    path("demo/zaaksysteem/", views.demo_zaaksysteem, name="demo-zaaksysteem"),
    path("zaaktype/<str:code>", views.ingebed, name="ingebed"),
    path("", views.app, name="app"),
    re_path(r"^artikel/(?P<pk>\d+)(?:/[\w-]*)?/?$", views.app, name="artikel"),
    re_path(r"^artikel/(?P<slug>[\w-]+)/?$", views.oude_artikel_link),
    re_path(r"^(?:artikelen|favorieten|recent|gewijzigd|nieuws|voorstellen|statistieken)/?$", views.app),
]

# Eigen Nederlandse foutpagina's in plaats van de Engelse standaard van Django (zie kennisbank/views.py).
handler400 = "kennisbank.views.fout_400"
handler403 = "kennisbank.views.fout_403"
handler404 = "kennisbank.views.fout_404"
handler500 = "kennisbank.views.fout_500"
