"""Vult een lege installatie met voorbeeldinhoud en demo-accounts. Alleen met KB_DEMO_MODUS=aan."""

import json
import random
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from kennisbank import diensten
from kennisbank.models import (
    Artikel,
    Bericht,
    BerichtStatus,
    Omgeving,
    Rol,
    Toegang,
    Verbetervoorstel,
    WeergaveTelling,
    ZoekTelling,
)
from kennisbank.rechten import werk_staf_status_bij
from kennisbank.uitwisseling import importeer

DEMO = Path(settings.BASE_DIR) / "demo"


class Command(BaseCommand):
    help = "Laad voorbeeldinhoud en maak demo-accounts aan (medewerker, redacteur, beheerder)."

    def add_arguments(self, parser):
        parser.add_argument("--wachtwoord", default=None, help="Wachtwoord voor de demo-accounts (standaard: demo)")

    def handle(self, wachtwoord=None, **opties):
        if not settings.KB_DEMO_MODUS:
            raise CommandError("Alleen beschikbaar met KB_DEMO_MODUS=aan.")
        wachtwoord = wachtwoord or "demo"
        if Artikel.objects.exists():
            self.stdout.write("Er staan al artikelen in de database; voorbeeldinhoud wordt niet opnieuw geladen.")
        else:
            data = json.loads((DEMO / "voorbeeldinhoud.json").read_text(encoding="utf-8"))
            importeer(data, toelichting="Voorbeeldinhoud")
            self._gebruik()
            self._nieuws_en_wijziging()
        omgeving = Omgeving.objects.get(slug="handhaving")
        lezers, _ = Group.objects.get_or_create(name="demo-medewerkers")
        redactie, _ = Group.objects.get_or_create(name="demo-procesmanagement")
        Toegang.objects.get_or_create(omgeving=omgeving, groep=lezers, defaults={"rol": Rol.LEZER})
        Toegang.objects.get_or_create(omgeving=omgeving, groep=redactie, defaults={"rol": Rol.REDACTEUR})
        User = get_user_model()
        for naam, voornaam, groep, superuser in [
            ("medewerker", "Demo Medewerker", lezers, False),
            ("redacteur", "Demo Procesmanagement", redactie, False),
            ("beheerder", "Demo Beheerder", None, True),
        ]:
            # Aanmaakdatum een week terug: wijzigingsmeldingen gelden alleen voor wijzigingen van ná de eerste inlog,
            # en de voorbeeldwijziging (zie _nieuws_en_wijziging) moet in de demo zichtbaar zijn.
            u, nieuw = User.objects.get_or_create(
                username=naam,
                defaults={"first_name": voornaam, "date_joined": timezone.now() - timezone.timedelta(days=7)},
            )
            if nieuw:
                u.set_password(wachtwoord)
                u.is_superuser = superuser
                u.save()
            if groep:
                u.groups.add(groep)
            werk_staf_status_bij(u)
        self.stdout.write(
            self.style.SUCCESS(
                "Demo klaar. Inloggen met medewerker / redacteur / beheerder (wachtwoord: "
                + ("demo" if wachtwoord == "demo" else "zoals opgegeven")
                + ")."
            )
        )

    def _nieuws_en_wijziging(self):
        """Twee nieuwsberichten en één inhoudelijke wijziging, zodat de nieuwspagina en de wijzigingsmelding
        ('Gewijzigd op … — Ik snap het') meteen te zien zijn. De demo-accounts krijgen in handle() een
        aanmaakdatum van een week geleden, zodat deze wijziging voor hen 'van na de eerste inlog' is."""
        omgeving = Omgeving.objects.get(slug="handhaving")
        rappel = Artikel.objects.get(slug="rappel-versturen")
        rappel.inhoud = rappel.inhoud.replace("Tweede rappel: 2 weken", "Tweede rappel: 3 weken")
        rappel.save()
        diensten.herbouw_secties(rappel)
        diensten.registreer_publicatie(rappel, None, "Termijn tweede rappel verlengd van 2 naar 3 weken")
        b = Bericht.objects.create(
            omgeving=omgeving,
            titel="Termijn tweede rappel wordt 3 weken",
            tekst="<p>Vanaf nu sturen we het tweede rappel <strong>3 weken</strong> na het eerste, in plaats van 2. "
            "De werkinstructie is aangepast; wie hem als favoriet heeft, heeft daar een melding van gekregen.</p>",
            status=BerichtStatus.GEPUBLICEERD,
            vastgepind=True,
        )
        b.artikelen.add(rappel)
        Bericht.objects.create(
            omgeving=omgeving,
            titel="Welkom in de kennisbank",
            tekst="<p>Hier staan de werkinstructies, werkafspraken en processen van het team. Mis je iets of klopt "
            "iets niet? Selecteer de tekst in een artikel en dien een verbetervoorstel in.</p>"
            "<p>Zet de schakelaar <strong>Onboarding</strong> aan voor extra uitleg bij de artikelen.</p>",
            status=BerichtStatus.GEPUBLICEERD,
        )

    def _gebruik(self):
        gebruik = json.loads((DEMO / "voorbeeld_gebruik.json").read_text(encoding="utf-8"))
        rnd = random.Random(42)  # noqa: S311 - alleen voorbeeldcijfers
        vandaag = timezone.localdate()
        for slug, totaal in gebruik["weergaven"].items():
            a = Artikel.objects.filter(slug=slug).first()
            if not a:
                continue
            for d in range(30):
                WeergaveTelling.objects.create(
                    artikel=a,
                    datum=vandaag - timezone.timedelta(days=d),
                    aantal=max(0, round(totaal / 30 + rnd.uniform(-2, 2))),
                )
        for term, n, leeg in [
            ("rappel", 48, 0),
            ("prioriteit", 37, 0),
            ("locatie", 31, 0),
            ("afwijsreden", 22, 0),
            ("sjabloon", 19, 0),
            ("zwerfboot", 14, 0),
            ("verlof", 9, 9),
            ("handhavingsverzoek", 6, 6),
        ]:
            ZoekTelling.objects.create(
                omgeving=Omgeving.objects.get(slug="handhaving"),
                term=term,
                datum=vandaag,
                aantal=n,
                zonder_resultaat=leeg,
            )
        status = {"behandeling": "in_behandeling", "verwerkt": "verwerkt", "nieuw": "nieuw", "afgewezen": "afgewezen"}
        for p in gebruik["voorstellen"]:
            a = Artikel.objects.get(slug=p["art"])
            Verbetervoorstel.objects.create(
                artikel=a,
                artikel_versie=a.versie,
                citaat=p["quote"],
                tekst=p["text"],
                status=status[p["status"]],
                terugkoppeling=p["fb"],
                ingediend_op=timezone.make_aware(timezone.datetime.fromisoformat(p["date"])),
            )
