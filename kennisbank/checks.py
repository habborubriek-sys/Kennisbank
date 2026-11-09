"""Controles bij het opstarten (``manage.py check``, ``migrate``) en op de statuspagina."""

import math

from django.conf import settings
from django.core.checks import Warning, register

#: HTML groeit bij het verzenden als formulier: de browser codeert ``< > " =`` en spaties.
#: Gemeten in de stresstest van 9 november: x1,1 voor lopende tekst, x1,35 voor inhoud uit Word, x1,6
#: voor een artikel dat vooral uit tabellen bestaat. Lege tabelcellen lopen op tot ~x2,1; 2 dekt alles
#: wat in de praktijk voorkomt.
VERZOEK_FACTOR = 2.0
MIB = 1024 * 1024


def minimale_verzoekgrens_mb() -> int:
    from .models import MAX_INHOUD

    return math.ceil(MAX_INHOUD * VERZOEK_FACTOR / MIB)


def verzoekgrens_te_laag() -> str:
    """Lege tekst als de verzoekgrens ruim genoeg is voor het grootste toegestane artikel."""
    from .models import MAX_INHOUD

    grens = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
    minimum = minimale_verzoekgrens_mb()
    if grens is None or grens >= minimum * MIB:
        return ""
    return (
        f"KB_MAX_VERZOEK_MB staat op {grens / MIB:g}. Een artikel van de maximale omvang "
        f"({MAX_INHOUD / MIB:g} MB) wordt bij het opslaan groter dan dat, omdat de browser de tekst voor "
        "het verzenden codeert. Opslaan van zo'n artikel mislukt dan met een foutpagina in plaats van de "
        f"melding dat het artikel te groot is. Zet KB_MAX_VERZOEK_MB op minimaal {minimum}."
    )


@register()
def controleer_verzoekgrens(app_configs, **kwargs):
    melding = verzoekgrens_te_laag()
    return [Warning(melding, id="kennisbank.W001")] if melding else []
