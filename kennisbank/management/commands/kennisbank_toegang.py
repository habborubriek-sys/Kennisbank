from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from kennisbank.models import Omgeving, Rol, Toegang


class Command(BaseCommand):
    help = (
        "Koppel een groep uit de identity provider aan een rol in een omgeving. "
        "Voorbeeld: kennisbank_toegang handhaving 3f2a...-groep-id redacteur"
    )

    def add_arguments(self, parser):
        parser.add_argument("omgeving", help="slug van de omgeving (wordt aangemaakt als die niet bestaat)")
        parser.add_argument("groep", help="groepsnaam of -id zoals in de groepen-claim")
        parser.add_argument("rol", choices=[r.value for r in Rol])
        parser.add_argument("--naam", help="weergavenaam van een nieuwe omgeving")
        parser.add_argument("--verwijder", action="store_true", help="koppeling verwijderen")

    def handle(self, omgeving, groep, rol, naam=None, verwijder=False, **opties):
        o, _ = Omgeving.objects.get_or_create(slug=omgeving, defaults={"naam": naam or omgeving})
        g, _ = Group.objects.get_or_create(name=groep)
        if verwijder:
            n, _ = Toegang.objects.filter(omgeving=o, groep=g).delete()
            if not n:
                raise CommandError("Deze koppeling bestond niet.")
            self.stdout.write(self.style.SUCCESS(f"Koppeling {g} ↔ {o} verwijderd."))
            return
        Toegang.objects.update_or_create(omgeving=o, groep=g, defaults={"rol": rol})
        self.stdout.write(self.style.SUCCESS(f"Groep '{g}' is nu {rol} in '{o}'."))
