"""Inloggen via OpenID Connect (bijv. Microsoft Entra ID).

Bij elke login:
- wordt de gebruiker gevonden of aangemaakt op basis van een stabiele claim (standaard 'sub');
- worden naam en e-mail bijgewerkt;
- worden de groepen uit de groepen-claim overgenomen als Django-groepen. Welke rol een groep
  krijgt, legt de functioneel beheerder vast onder 'Toegang' in het beheerscherm.
"""

from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.models import Group
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from .rechten import werk_staf_status_bij


class KennisbankOIDCBackend(OIDCAuthenticationBackend):
    def _gebruikersnaam(self, claims):
        return str(claims.get(settings.KB_OIDC_GEBRUIKERSNAAM_CLAIM, ""))[:150]

    def verify_claims(self, claims):
        return bool(self._gebruikersnaam(claims))

    def filter_users_by_claims(self, claims):
        naam = self._gebruikersnaam(claims)
        if not naam:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(username=naam)

    def create_user(self, claims):
        gebruiker = self.UserModel.objects.create_user(username=self._gebruikersnaam(claims))
        return self.update_user(gebruiker, claims)

    def update_user(self, gebruiker, claims):
        gebruiker.email = claims.get("email") or claims.get("preferred_username") or ""
        gebruiker.first_name = (claims.get("given_name") or "")[:150]
        gebruiker.last_name = (claims.get("family_name") or "")[:150]
        if not gebruiker.first_name and claims.get("name"):
            gebruiker.first_name = claims["name"][:150]

        groepen = claims.get(settings.KB_OIDC_GROEPEN_CLAIM) or []
        if isinstance(groepen, str):
            groepen = [groepen]
        groepen = [str(g)[:150] for g in groepen]
        gebruiker.is_superuser = bool(set(groepen) & set(settings.KB_BEHEERDERS_GROEPEN))
        gebruiker.save()
        gebruiker.groups.set([Group.objects.get_or_create(name=g)[0] for g in groepen])
        werk_staf_status_bij(gebruiker)
        return gebruiker


def logout_url(request):
    """Uitloggen bij de identity provider na uitloggen in de kennisbank."""
    params = {"post_logout_redirect_uri": request.build_absolute_uri("/")}
    id_token = request.session.get("oidc_id_token")
    if id_token:
        params["id_token_hint"] = id_token
    return f"{settings.OIDC_OP_LOGOUT_ENDPOINT}?{urlencode(params)}"
