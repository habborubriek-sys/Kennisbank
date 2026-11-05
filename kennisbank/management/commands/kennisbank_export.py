import json

from django.core.management.base import BaseCommand, CommandError

from kennisbank.models import Omgeving
from kennisbank.uitwisseling import exporteer


class Command(BaseCommand):
    help = "Exporteer alle artikelen van een omgeving naar JSON (zelfde formaat als de import)."

    def add_arguments(self, parser):
        parser.add_argument("omgeving", help="slug van de omgeving")
        parser.add_argument("bestand", nargs="?", help="Uitvoerbestand; zonder bestand naar stdout")

    def handle(self, omgeving, bestand=None, **opties):
        try:
            o = Omgeving.objects.get(slug=omgeving)
        except Omgeving.DoesNotExist as e:
            raise CommandError(f"Omgeving '{omgeving}' bestaat niet.") from e
        tekst = json.dumps(exporteer(o), ensure_ascii=False, indent=2)
        if bestand:
            with open(bestand, "w", encoding="utf-8") as f:
                f.write(tekst)
        else:
            self.stdout.write(tekst)
