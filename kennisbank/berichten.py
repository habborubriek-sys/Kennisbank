"""Meldingen na opslaan in de eigen toon van de kennisbank (1.31.0, review 1.27.0 R3 B13).

Django zegt na opslaan in het beheer bijvoorbeeld "De artikel ‘…’ is met succes toegevoegd. U kunt deze hieronder
weer bewerken." Dat klopt niet ("het artikel") en is formeler dan de rest van de kennisbank ("je"). In plaats van
elk beheerscherm apart aan te passen, herschrijft deze opslag de standaardzinnen van Django één keer, op de plek
waar alle meldingen langskomen. Eigen meldingen van de kennisbank blijven zoals ze zijn.
"""

import re

from django.contrib.messages.storage.fallback import FallbackStorage
from django.utils.safestring import SafeData, mark_safe

#: Zelfstandige naamwoorden die "het" krijgen. De rest houdt "de".
HET = {"artikel", "nieuwsbericht", "bericht", "cluster", "zaaktype", "reviewteam", "verbetervoorstel", "voorstel"}

_ZINNEN = [
    (re.compile(r" U kunt deze hieronder (?:weer|nogmaals|opnieuw) bewerken\."), ""),
    (re.compile(r" U kunt hieronder nog een (\S+) toevoegen\."), r" Je kunt hieronder nog een \1 toevoegen."),
    (re.compile(r"is met succes toegevoegd"), "is toegevoegd"),
    (re.compile(r"is met succes gewijzigd"), "is opgeslagen"),
    (re.compile(r"zijn met succes gewijzigd"), "zijn opgeslagen"),
    (re.compile(r"is met succes verwijderd"), "is verwijderd"),
    (re.compile(r"zijn met succes verwijderd"), "zijn verwijderd"),
    (re.compile(r"‘([^’]*)’"), r"“\1”"),
]
_LIDWOORD = re.compile(r"^De (\S+) (?=“)")


def herschrijf(tekst: str) -> str:
    for patroon, vervanging in _ZINNEN:
        tekst = patroon.sub(vervanging, tekst)
    m = _LIDWOORD.match(tekst)
    if m and m.group(1).lower() in HET:
        tekst = "Het " + tekst[3:]
    return tekst


class Berichten(FallbackStorage):
    def add(self, level, message, extra_tags=""):
        if isinstance(message, str) and ("met succes" in message or "U kunt" in message):
            # Django zet een link naar het onderdeel in de melding (veilige HTML); die moet veilig blijven.
            veilig = isinstance(message, SafeData)
            message = herschrijf(message)
            if veilig:
                message = mark_safe(message)  # noqa: S308 - alleen vaste zinsdelen vervangen
        return super().add(level, message, extra_tags)
