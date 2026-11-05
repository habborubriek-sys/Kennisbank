from django.conf import settings


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
        # Het beheerscherm van Django gebruikt inline scripts; daar een ruimere policy.
        if request.path.startswith("/beheer/") or request.path.startswith("/api/docs"):
            response.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; frame-ancestors 'self'",
            )
        else:
            response.setdefault("Content-Security-Policy", self.csp)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response
