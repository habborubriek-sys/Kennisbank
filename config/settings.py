"""
Instellingen voor de Kennisbank.

Alle omgevingsafhankelijke waarden komen uit omgevingsvariabelen (12-factor).
Zie docs/configuratie.md voor de volledige lijst met uitleg en standaardwaarden.
"""

import re
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from kennisbank import __version__

from .env import env, env_bool, env_int, env_list

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Kern -------------------------------------------------------------------

DEBUG = env_bool("KB_DEBUG", False)
SECRET_KEY = env("KB_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "alleen-voor-ontwikkeling-niet-in-productie-gebruiken"
    else:
        raise ImproperlyConfigured("KB_SECRET_KEY is verplicht wanneer KB_DEBUG uit staat.")

ALLOWED_HOSTS = env_list("KB_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env_list("KB_CSRF_TRUSTED_ORIGINS", [])

# Naam die in de kop van de applicatie staat, en de standaard-omgeving.
KB_APP_NAAM = env("KB_APP_NAAM", "Kennisbank")
KB_DEMO_MODUS = env_bool("KB_DEMO_MODUS", False)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "mozilla_django_oidc",
    "django.contrib.postgres",
    "kennisbank",
]

MIDDLEWARE = [
    # Vooraan: /healthz en /readyz worden beantwoord vóór de hostnaam-controle (zie kennisbank/gezondheid.py).
    "kennisbank.gezondheid.GezondheidMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "kennisbank.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # In OIDC-modus wordt hieronder SessionRefresh toegevoegd (rechten periodiek opnieuw ophalen).
    # XFrameOptionsMiddleware bewust niet: inbedden wordt geregeld via
    # CSP frame-ancestors (KB_FRAME_ANCESTORS), zodat het zaaksysteem de
    # kennisbank in een iframe kan tonen.
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database ---------------------------------------------------------------
# Alleen PostgreSQL wordt ondersteund (zoeken gebruikt PostgreSQL full-text search).

DATABASES = {
    "default": dj_database_url.parse(
        env("KB_DATABASE_URL", "postgres://kennisbank:kennisbank@localhost:5432/kennisbank"),
        conn_max_age=env_int("KB_DATABASE_CONN_MAX_AGE", 60),
        conn_health_checks=True,
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Taal en tijd -------------------------------------------------------------

LANGUAGE_CODE = "nl"
TIME_ZONE = env("KB_TIJDZONE", "Europe/Amsterdam")
USE_I18N = True
USE_TZ = True

# --- Statische bestanden ------------------------------------------------------
# WhiteNoise serveert ze vanuit de container; een aparte webserver is niet nodig.

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

# --- Authenticatie ------------------------------------------------------------
# KB_AUTH_MODUS=oidc  -> inloggen via de identity provider (bijv. Entra ID)
# KB_AUTH_MODUS=lokaal -> gebruikersnaam/wachtwoord in de applicatie (test/demo)

KB_AUTH_MODUS = env("KB_AUTH_MODUS", "lokaal").lower()
if KB_AUTH_MODUS not in {"oidc", "lokaal"}:
    raise ImproperlyConfigured("KB_AUTH_MODUS moet 'oidc' of 'lokaal' zijn.")

if KB_AUTH_MODUS == "oidc":
    # Uitsluitend de identity provider. Bewust géén ModelBackend: anders zou iemand met een
    # wachtwoord in de database (bijv. een createsuperuser-account) via /beheer/login/ om
    # Entra ID en MFA heen kunnen. Beheerders komen binnen via KB_BEHEERDERS_GROEPEN.
    AUTHENTICATION_BACKENDS = ["kennisbank.auth.KennisbankOIDCBackend"]
    OIDC_RP_CLIENT_ID = env("KB_OIDC_CLIENT_ID", required=True)
    OIDC_RP_CLIENT_SECRET = env("KB_OIDC_CLIENT_SECRET", required=True)
    OIDC_RP_SIGN_ALGO = env("KB_OIDC_SIGN_ALGO", "RS256")
    OIDC_OP_AUTHORIZATION_ENDPOINT = env("KB_OIDC_AUTHORIZATION_ENDPOINT", required=True)
    OIDC_OP_TOKEN_ENDPOINT = env("KB_OIDC_TOKEN_ENDPOINT", required=True)
    OIDC_OP_USER_ENDPOINT = env("KB_OIDC_USERINFO_ENDPOINT", required=True)
    OIDC_OP_JWKS_ENDPOINT = env("KB_OIDC_JWKS_ENDPOINT", required=True)
    OIDC_OP_LOGOUT_ENDPOINT = env("KB_OIDC_LOGOUT_ENDPOINT", "")
    OIDC_RP_SCOPES = env("KB_OIDC_SCOPES", "openid email profile")
    OIDC_STORE_ID_TOKEN = True
    OIDC_USE_PKCE = True
    if OIDC_OP_LOGOUT_ENDPOINT:
        OIDC_OP_LOGOUT_URL_METHOD = "kennisbank.auth.logout_url"
    LOGIN_URL = "oidc_authentication_init"
    # Rechten verversen: na dit aantal seconden wordt de gebruiker bij een paginaweergave stilletjes
    # (prompt=none) opnieuw bij de identity provider langs gestuurd. Zo komen gewijzigde groepen en
    # een geblokkeerd account binnen die tijd door, in plaats van pas na het verlopen van de sessie.
    MIDDLEWARE.append("mozilla_django_oidc.middleware.SessionRefresh")
    OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = env_int("KB_OIDC_HERNIEUW_SECONDEN", 15 * 60)
    # Niet verversen bij de ingebedde weergave zelf (een identity provider weigert in een iframe).
    # De API geeft bij een verlopen token een 403 met refresh_url; de frontend laadt dan de pagina
    # opnieuw, of toont in het iframe de knop die het inloggen in een eigen venster opent.
    OIDC_EXEMPT_URLS = ["/uitloggen/", re.compile(r"^/zaaktype/")]
else:
    AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
    LOGIN_URL = "inloggen"

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# Welke claims de gebruiker en zijn groepen bepalen.
KB_OIDC_GEBRUIKERSNAAM_CLAIM = env("KB_OIDC_GEBRUIKERSNAAM_CLAIM", "sub")
KB_OIDC_GROEPEN_CLAIM = env("KB_OIDC_GROEPEN_CLAIM", "groups")
# Leden van deze groep(en) worden functioneel beheerder (toegang tot alles).
KB_BEHEERDERS_GROEPEN = env_list("KB_BEHEERDERS_GROEPEN", [])

SESSION_COOKIE_AGE = env_int("KB_SESSIE_DUUR_SECONDEN", 8 * 3600)
SESSION_COOKIE_HTTPONLY = True
# 'None' is nodig als het zaaksysteem op een ander domein de kennisbank in een iframe toont.
SESSION_COOKIE_SAMESITE = env("KB_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = SESSION_COOKIE_SAMESITE
SESSION_COOKIE_SECURE = env_bool("KB_COOKIES_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE

# --- Beveiligingsheaders ------------------------------------------------------

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin-allow-popups"
SECURE_HSTS_SECONDS = env_int("KB_HSTS_SECONDEN", 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
# Achter een reverse proxy / ingress die TLS afhandelt:
if env_bool("KB_ACHTER_PROXY", True):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
SECURE_SSL_REDIRECT = env_bool("KB_SSL_REDIRECT", False)
SECURE_REDIRECT_EXEMPT = [r"^healthz$", r"^readyz$"]

# Welke sites de kennisbank in een iframe mogen tonen (CSP frame-ancestors).
KB_FRAME_ANCESTORS = env_list("KB_FRAME_ANCESTORS", ["'self'"])

# --- API ----------------------------------------------------------------------

# API-tokens van koppelingen verlopen na dit aantal dagen (0 = nooit). Zie kennisbank/api_auth.py.
KB_API_TOKEN_MAX_DAGEN = env_int("KB_API_TOKEN_MAX_DAGEN", 365)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # Token eerst: dan krijgt een koppeling zonder/met verlopen token een echte 401 (met WWW-Authenticate).
        "kennisbank.api_auth.VerlopendTokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_THROTTLE_RATES": {
        "assistent": env("KB_ASSISTENT_LIMIET", "30/min"),
        "voorstel": env("KB_VOORSTEL_LIMIET", "20/hour"),
    },
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Kennisbank API",
    "DESCRIPTION": "API van de Kennisbank: artikelen, zoeken, assistent, "
    "verbetervoorstellen en de koppeling met het zaaksysteem.",
    "VERSION": __version__,
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    # Documentatiepagina zonder externe CDN
    "REDOC_DIST": "SIDECAR",
    # Schema en documentatie alleen voor ingelogde gebruikers.
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAuthenticated"],
    "ENUM_NAME_OVERRIDES": {
        "ArtikelStatusEnum": "kennisbank.models.Status",
        "VoorstelStatusEnum": "kennisbank.models.VoorstelStatus",
    },
}

# --- AI-assistent ---------------------------------------------------------------
# uit     -> assistent zoekt en citeert alleen (geen taalmodel)
# openai  -> elk OpenAI-compatibel endpoint (ook zelf gehoste modellen)
# azure   -> Azure OpenAI

KB_AI_PROVIDER = env("KB_AI_PROVIDER", "uit").lower()
KB_AI_BASE_URL = env("KB_AI_BASE_URL", "")
KB_AI_API_KEY = env("KB_AI_API_KEY", "")
KB_AI_MODEL = env("KB_AI_MODEL", "")
KB_AI_AZURE_API_VERSIE = env("KB_AI_AZURE_API_VERSIE", "2024-10-21")
KB_AI_TIMEOUT_SECONDEN = env_int("KB_AI_TIMEOUT_SECONDEN", 30)
KB_AI_MAX_BRONNEN = env_int("KB_AI_MAX_BRONNEN", 5)
KB_AI_TEMPERATUUR = float(env("KB_AI_TEMPERATUUR", "0.1"))
# Maximale lengte van een antwoord (tokens) en het kostenplafond: maximaal aantal aanroepen van het
# taalmodel per dag voor de hele installatie (0 = geen plafond). Daarboven valt de assistent terug op
# citeren uit de kennisbank, zonder taalmodel.
KB_AI_MAX_TOKENS = env_int("KB_AI_MAX_TOKENS", 600)
KB_ASSISTENT_DAGLIMIET = env_int("KB_ASSISTENT_DAGLIMIET", 2000)
if KB_AI_PROVIDER not in {"uit", "openai", "azure"}:
    raise ImproperlyConfigured("KB_AI_PROVIDER moet 'uit', 'openai' of 'azure' zijn.")
if KB_AI_PROVIDER != "uit" and not (KB_AI_BASE_URL and KB_AI_MODEL):
    raise ImproperlyConfigured("KB_AI_BASE_URL en KB_AI_MODEL zijn verplicht als de AI aan staat.")

# --- Bewaartermijnen (AVG) --------------------------------------------------------
# Uitgevoerd door: python manage.py kennisbank_opschonen (dagelijks inplannen)

KB_BEWAAR_RECENT_DAGEN = env_int("KB_BEWAAR_RECENT_DAGEN", 90)
KB_BEWAAR_STATISTIEK_DAGEN = env_int("KB_BEWAAR_STATISTIEK_DAGEN", 730)
KB_ANONIMISEER_VOORSTEL_DAGEN = env_int("KB_ANONIMISEER_VOORSTEL_DAGEN", 365)
KB_RECENT_MAX = env_int("KB_RECENT_MAX", 10)

# --- E-mail (optioneel) -------------------------------------------------------------
# Zonder KB_EMAIL_HOST worden geen e-mails verstuurd; meldingen staan dan alleen in de app.

if env("KB_EMAIL_HOST", ""):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("KB_EMAIL_HOST")
    EMAIL_PORT = env_int("KB_EMAIL_PORT", 587)
    EMAIL_HOST_USER = env("KB_EMAIL_GEBRUIKER", "")
    EMAIL_HOST_PASSWORD = env("KB_EMAIL_WACHTWOORD", "")
    EMAIL_USE_TLS = env_bool("KB_EMAIL_TLS", True)
    KB_EMAIL_AAN = True
else:
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    KB_EMAIL_AAN = False
DEFAULT_FROM_EMAIL = env("KB_EMAIL_AFZENDER", "kennisbank@localhost")
KB_BASIS_URL = env("KB_BASIS_URL", "http://localhost:8000")

# --- Logging ------------------------------------------------------------------------
# Gestructureerde JSON-regels naar stdout, zodat het platform ze kan oppikken.

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "kennisbank.logformaat.JsonFormatter"},
        "tekst": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "formatter": "json" if env("KB_LOG_FORMAAT", "json") == "json" else "tekst",
        }
    },
    "root": {"handlers": ["stdout"], "level": env("KB_LOG_NIVEAU", "INFO")},
    "loggers": {
        "django.request": {"level": "WARNING"},
        "httpx": {"level": "WARNING"},
    },
}
