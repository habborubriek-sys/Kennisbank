"""Maakt of vernieuwt het API-token van een (technisch) account voor een koppeling."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = "Maak of vernieuw het API-token van een account. Een bestaand token wordt vervangen (rotatie)."

    def add_arguments(self, parser):
        parser.add_argument("gebruikersnaam")
        parser.add_argument("--intrekken", action="store_true", help="Alleen het bestaande token intrekken.")

    def handle(self, gebruikersnaam, intrekken, **opties):
        User = get_user_model()
        try:
            gebruiker = User.objects.get(username=gebruikersnaam)
        except User.DoesNotExist as e:
            raise CommandError(f"Account '{gebruikersnaam}' bestaat niet.") from e
        verwijderd = Token.objects.filter(user=gebruiker).delete()[0]
        if intrekken:
            self.stdout.write(f"Token van {gebruikersnaam} ingetrokken." if verwijderd else "Er was geen token.")
            return
        token = Token.objects.create(user=gebruiker)
        self.stdout.write(f"Nieuw token voor {gebruikersnaam} (het oude is ingetrokken):\n{token.key}")
