"""Health-checks die onafhankelijk zijn van de hostnaam-controle.

Kubernetes en Docker roepen /healthz en /readyz aan met het pod-IP of 127.0.0.1 als Host-header.
Die staan niet in KB_ALLOWED_HOSTS, dus als deze paden door de normale middleware-keten zouden
gaan, zou Django ze met 400 (DisallowedHost) weigeren en zou de pod nooit 'Ready' worden.
Deze middleware staat vooraan in de keten en beantwoordt de twee paden direct, zonder sessie,
CSRF of hostnaam-controle. De antwoorden bevatten geen gegevens, dus dat is veilig.
"""

from django.db import connection
from django.http import HttpResponse, JsonResponse

PADEN = ("/healthz", "/readyz")


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


class GezondheidMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        pad = request.path_info.rstrip("/") or "/"
        if pad == "/healthz" and request.method in ("GET", "HEAD"):
            return healthz(request)
        if pad == "/readyz" and request.method in ("GET", "HEAD"):
            return readyz(request)
        return self.get_response(request)
