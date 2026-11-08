import json

from django.core.management.base import BaseCommand, CommandError

from kennisbank.uitwisseling import ImportFout, importeer


class Command(BaseCommand):
    help = "Importeer artikelen uit een JSON-bestand (zie docs/importformaat.md). Bestaande slugs worden bijgewerkt."

    def add_arguments(self, parser):
        parser.add_argument("bestand")
        parser.add_argument(
            "--toelichting",
            default="Import",
            help="Tekst in de versiegeschiedenis; medewerkers zien die als wijzigingsmelding bij gewijzigde artikelen",
        )
        parser.add_argument(
            "--kleine-correctie",
            action="store_true",
            help="Gewijzigde artikelen krijgen wel een versie, maar geen wijzigingsmelding en geen e-mail",
        )

    def handle(self, bestand, toelichting, kleine_correctie=False, **opties):
        with open(bestand, encoding="utf-8") as f:
            data = json.load(f)
        try:
            t = importeer(data, toelichting=toelichting, kleine_correctie=kleine_correctie)
        except ImportFout as e:
            raise CommandError(str(e)) from e
        self.stdout.write(
            self.style.SUCCESS(
                f"{t['nieuw']} nieuw, {t['bijgewerkt']} bijgewerkt, {t['nieuwe_versies']} nieuwe versies."
            )
        )
