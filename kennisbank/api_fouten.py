"""Foutmeldingen van de API in begrijpelijk Nederlands.

Django REST Framework heeft een Nederlandse vertaling, maar die is voor een paar meldingen niet
bruikbaar: "Request was throttled" wordt "Aanvraag was verstikt", en de tweede helft van die melding
("Expected available in 30 seconds") blijft Engels. Een medewerker die te snel klikt, krijgt dus een
onbegrijpelijke mededeling.

Deze handler vervangt alleen de meldingen waar dat nodig is en laat de rest met rust.
"""

import math

from rest_framework.exceptions import Throttled
from rest_framework.views import exception_handler


def _wachttekst(seconden) -> str:
    """Hoe lang nog, in woorden waar iemand iets aan heeft."""
    if not seconden:
        return "Probeer het straks opnieuw."
    seconden = int(math.ceil(seconden))
    if seconden < 60:
        return f"Probeer het over {seconden} seconden opnieuw."
    minuten = int(math.ceil(seconden / 60))
    if minuten < 60:
        eenheid = "minuut" if minuten == 1 else "minuten"
        return f"Probeer het over {minuten} {eenheid} opnieuw."
    uren = int(math.ceil(minuten / 60))
    return "Probeer het over een uur opnieuw." if uren == 1 else f"Probeer het over {uren} uur opnieuw."


def nederlandse_fout(exc, context):
    """De standaardhandler van DRF, met een leesbare Nederlandse tekst bij een te-veel-verzoeken-fout."""
    antwoord = exception_handler(exc, context)
    if antwoord is not None and isinstance(exc, Throttled):
        antwoord.data = {
            "detail": "Je hebt dit de afgelopen tijd vaak gedaan. " + _wachttekst(exc.wait),
            "wacht_seconden": int(math.ceil(exc.wait)) if exc.wait else None,
        }
    return antwoord
