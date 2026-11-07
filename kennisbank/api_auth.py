"""Token-authenticatie voor koppelingen (zaaksysteem), met een vervaldatum.

Een token van een technisch account blijft anders eindeloos geldig. Met KB_API_TOKEN_MAX_DAGEN
(standaard 365; 0 = nooit verlopen) wordt een token na die tijd geweigerd met een duidelijke
melding, zodat rotatie niet vergeten kan worden. Nieuw token: `beheer kennisbank_token <account>`.
"""

from django.conf import settings
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication


class VerlopendTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        max_dagen = settings.KB_API_TOKEN_MAX_DAGEN
        if max_dagen and token.created < timezone.now() - timezone.timedelta(days=max_dagen):
            raise exceptions.AuthenticationFailed(
                f"Dit API-token is ouder dan {max_dagen} dagen en verlopen. "
                "Vraag functioneel beheer om een nieuw token (beheer kennisbank_token)."
            )
        return user, token
