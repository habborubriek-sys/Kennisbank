from django.conf import settings
from django.http import HttpResponseBadRequest


class NulByteMiddleware:
    """Weiger verzoeken met een nul-byte in het pad of de querystring.

    PostgreSQL accepteert geen nul-bytes in tekstvelden, dus zo'n teken in bijvoorbeeld ?tag=%00
    liet een zoekopdracht of het wegschrijven van een zoekstatistiek klappen met een serverfout.
    De formuliervelden weren nul-bytes al; de querystring werd nergens gecontroleerd.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Het pad is al gedecodeerd; in de ruwe querystring staat het teken nog als %00, dus daar
        # kijken we naar de gedecodeerde waarden uit request.GET.
        if "\x00" in request.path:
            return self._weiger()
        for sleutel, waarden in request.GET.lists():
            if "\x00" in sleutel or any("\x00" in w for w in waarden):
                return self._weiger()
        return self.get_response(request)

    @staticmethod
    def _weiger():
        return HttpResponseBadRequest("Ongeldig teken in het webadres.")


class SecurityHeadersMiddleware:
    """Content-Security-Policy en verwante headers.

    De frontend gebruikt geen inline scripts of stijlen en laadt niets van externe
    domeinen, dus de policy kan streng zijn.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        ancestors = " ".join(settings.KB_FRAME_ANCESTORS)
        self.csp = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; "
            f"form-action 'self' {self._idp()}; frame-ancestors {ancestors}"
        ).replace("  ", " ")
        self.csp_beheer = (
            # style-src-attr: de editor (Tiptap) zet bij tabellen een style-attribuut op <table> en <col>. Een
            # <style>-element of een inline script blijft geweigerd.
            "default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; "
            f"form-action 'self' {self._idp()}; frame-ancestors 'self'"
        ).replace("  ", " ")

    @staticmethod
    def _idp():
        endpoint = getattr(settings, "OIDC_OP_AUTHORIZATION_ENDPOINT", "")
        if not endpoint:
            return ""
        from urllib.parse import urlsplit

        deel = urlsplit(endpoint)
        return f"{deel.scheme}://{deel.netloc}"

    def __call__(self, request):
        response = self.get_response(request)
        # De API-documentatie (Redoc) heeft inline scripts en stijlen nodig; alleen daar een ruimere policy.
        if request.path.startswith("/api/docs"):
            response.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; frame-ancestors 'self'",
            )
        # 1.32.0 (review 1.27.0, M9): het beheer staat geen inline scripts meer toe. Eigen sjablonen en Django
        # zelf laden alle scripts als bestand. Het beheer wordt nooit ingebed (frame-ancestors 'self').
        elif request.path.startswith("/beheer/"):
            response.setdefault("Content-Security-Policy", self.csp_beheer)
        else:
            response.setdefault("Content-Security-Policy", self.csp)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response
