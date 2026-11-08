"""Verstuurt de gebundelde e-mail aan medewerkers van wie een favoriet artikel is gewijzigd.

Wordt ook aangeroepen door `kennisbank_opschonen` (dagelijks). Apart inplannen kan als je vaker wilt
mailen, bijvoorbeeld elk uur. Zie KB_FAVORIETEN_MAIL in docs/configuratie.md.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from kennisbank import diensten


class Command(BaseCommand):
    help = "Bundel de openstaande wijzigingen van favoriete artikelen per medewerker tot één e-mail en verstuur die."

    def handle(self, **opties):
        if settings.KB_FAVORIETEN_MAIL == "uit":
            self.stdout.write("KB_FAVORIETEN_MAIL staat uit; er is niets verstuurd.")
            return
        n = diensten.verstuur_favorietenmail()
        self.stdout.write(f"{n} e-mail(s) verstuurd.")
