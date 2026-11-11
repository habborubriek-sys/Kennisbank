"""Verstuurt de samenvatting van nieuwe verbetervoorstellen aan de redacteuren.

Wordt ook aangeroepen door `kennisbank_opschonen` (dagelijks); apart inplannen hoeft dus niet. Wil je
de samenvatting op een vast moment (bijvoorbeeld om 8 uur), plan dit commando dan zelf in: er gaat
alleen iets uit als er sinds de vorige keer iets nieuws is binnengekomen.
"""

from django.core.management.base import BaseCommand

from kennisbank import diensten, review


class Command(BaseCommand):
    help = "Stuur redacteuren en reviewers één e-mail met wat er sinds de vorige keer is binnengekomen."

    def handle(self, **opties):
        n = diensten.verstuur_voorstellenmail()
        r = review.verstuur_reviewmail()
        self.stdout.write(f"{n} samenvatting(en) voor redacteuren en {r} voor reviewers verstuurd.")
