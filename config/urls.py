from django.conf import settings
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView

from kennisbank import api, views

admin.site.site_header = f"{settings.KB_APP_NAAM} – beheer"
admin.site.site_title = f"{settings.KB_APP_NAAM} – beheer"
admin.site.index_title = "Artikelen, voorstellen en toegang"
admin.site.site_url = "/"

api_v1 = [
    path("ik", api.ik, name="api-ik"),
    path("keuzelijsten", api.keuzelijsten, name="api-keuzelijsten"),
    path("artikelen", api.artikelen, name="api-artikelen"),
    path("artikelen/<slug:slug>", api.artikel, name="api-artikel"),
    path("artikelen/<slug:slug>/weergave", api.weergave, name="api-weergave"),
    path("artikelen/<slug:slug>/favoriet", api.favoriet, name="api-favoriet"),
    path("artikelen/<slug:slug>/versies", api.versies, name="api-versies"),
    path("voorstellen", api.voorstellen, name="api-voorstellen"),
    path("voorstellen/<int:pk>", api.voorstel, name="api-voorstel"),
    path("statistieken", api.statistieken, name="api-statistieken"),
    path("assistent", api.assistent, name="api-assistent"),
    path("zaaktypen/<str:code>/artikelen", api.zaaktype_artikelen, name="api-zaaktype-artikelen"),
    re_path(r"^.*$", api.niet_gevonden),
]

urlpatterns = [
    path("healthz", views.healthz),
    path("readyz", views.readyz),
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularRedocView.as_view(url_name="schema"), name="api-docs"),
    path("beheer/", admin.site.urls),
    path("oidc/", include("mozilla_django_oidc.urls")),
    path("inloggen/", views.Inloggen.as_view(), name="inloggen"),
    path("uitloggen/", LogoutView.as_view(), name="uitloggen"),
    path("login-voltooid/", views.login_voltooid, name="login-voltooid"),
    path("demo/zaaksysteem/", views.demo_zaaksysteem, name="demo-zaaksysteem"),
    path("zaaktype/<str:code>", views.ingebed, name="ingebed"),
    path("", views.app, name="app"),
    re_path(r"^(?:artikel/[\w-]+|artikelen|favorieten|recent|voorstellen|statistieken)/?$", views.app),
]
