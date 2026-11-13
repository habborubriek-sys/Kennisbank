"""Start een server op een wegwerpdatabase met vaste testgegevens, voor de browsertests.

Alleen met KB_DEMO_MODUS=aan. De opdracht maakt een aparte testdatabase (``test_<naam>``, zoals de gewone
tests doen), vult die met de demo-inhoud en een vaste set artikelen, voorstellen en reviews, schrijft de
id's naar een JSON-bestand en start daarna de ontwikkelserver. De gewone database wordt niet aangeraakt.

Gebruik (zie scripts/browsertests/README.md):

    KB_DEMO_MODUS=aan python manage.py kennisbank_browsertest --poort 8765 --opzet /tmp/opzet.json
"""

import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from kennisbank import diensten, review
from kennisbank.models import (
    Artikel,
    Cluster,
    Conceptversie,
    Inzage,
    Omgeving,
    Reviewteam,
    Status,
    Verbetervoorstel,
)

TEKST = (
    '<section class="sectie"><h2 class="sectie-kop">Wanneer</h2>'
    "<p>Stuur na twee weken een rappel. Bel bij spoed dezelfde dag.</p>"
    "<ul><li>Noteer de datum in het logboek.</li><li>Leg het antwoord vast in de zaak.</li></ul></section>"
    '<section class="sectie"><h2 class="sectie-kop">Daarna</h2>'
    "<p>Komt er geen reactie, overleg dan met de coordinator.</p></section>"
)


class Command(BaseCommand):
    help = "Wegwerpdatabase met vaste testgegevens, plus een server, voor de browsertests (alleen demo-modus)."

    def add_arguments(self, parser):
        parser.add_argument("--poort", default="8765")
        parser.add_argument("--opzet", default="", help="Schrijf de id's van de testgegevens naar dit JSON-bestand")
        parser.add_argument("--geen-server", action="store_true", help="Alleen klaarzetten, geen server starten")

    def handle(self, poort, opzet, geen_server, **opties):
        if not settings.KB_DEMO_MODUS:
            raise CommandError("Alleen beschikbaar met KB_DEMO_MODUS=aan.")
        # Een eigen database, zoals de testrunner die maakt. Bestaat hij nog van een vorige keer, dan opnieuw.
        # Een eigen naam, zodat de gewone tests (test_<naam>) er niet mee botsen als ze tegelijk draaien.
        connection.settings_dict.setdefault("TEST", {})["NAME"] = "browsertest_" + connection.settings_dict["NAME"]
        naam = connection.creation.create_test_db(verbosity=0, autoclobber=True, serialize=False)
        call_command("kennisbank_demo", verbosity=0, stdout=open("/dev/null", "w"))  # noqa: SIM115 - weggooien
        gegevens = self.klaarzetten()
        if opzet:
            with open(opzet, "w", encoding="utf-8") as f:
                json.dump(gegevens, f, indent=2)
        self.stdout.write(f"Testdatabase {naam} staat klaar: {json.dumps(gegevens)}")
        if not geen_server:
            call_command("runserver", f"127.0.0.1:{poort}", use_reloader=False)

    # --- de vaste testgegevens -------------------------------------------------------------------------------

    def artikel(self, titel, redacteur, cluster):
        a = Artikel.objects.create(
            omgeving=self.omgeving,
            titel=titel,
            samenvatting="Vast testartikel voor de browsertests.",
            inhoud=TEKST,
            status=Status.GEPUBLICEERD,
        )
        a.clusters.add(cluster)
        diensten.herbouw_secties(a)
        diensten.registreer_publicatie(a, redacteur)
        a.refresh_from_db()
        return a

    def concept(self, a, redacteur, inhoud):
        velden = {
            "titel": a.titel,
            "samenvatting": a.samenvatting,
            "inhoud": inhoud,
            "soort": a.soort,
            "eigenaar": a.eigenaar,
            "omgeving": a.omgeving_id,
            "herzien_voor": a.herzien_voor.isoformat() if a.herzien_voor else "",
            "clusters": sorted(a.clusters.values_list("pk", flat=True)),
            "zaaktypen": sorted(a.zaaktypen.values_list("pk", flat=True)),
            "tags_tekst": "",
        }
        return diensten.concept_opslaan(a, redacteur, velden, "")

    def voorstel(self, a, indiener, tekst, citaat):
        return Verbetervoorstel.objects.create(
            artikel=a, artikel_versie=a.versie, tekst=tekst, citaat=citaat, ingediend_door=indiener
        )

    def klaarzetten(self) -> dict:
        User = get_user_model()
        self.omgeving = Omgeving.objects.get(slug="handhaving")
        redacteur = User.objects.get(username="redacteur")
        medewerker = User.objects.get(username="medewerker")
        reviewer = User.objects.get(username="reviewer")
        team = Reviewteam.objects.get(omgeving=self.omgeving, naam="Team Water")
        cluster = Cluster.objects.get(naam="Nat beheer")
        lezers = Group.objects.get(name="demo-medewerkers")
        steuners = []
        for i, naam in enumerate(["Sanne de Vries", "Karim Bakkali", "Lotte Jansen", "Tom Peters"]):
            voornaam, achternaam = naam.split(" ", 1)
            u = User.objects.create_user(f"steuner{i}", first_name=voornaam, last_name=achternaam)  # logt nooit in
            u.groups.add(lezers)
            steuners.append(u)

        # 1. De lade: vier open voorstellen, het eerste met steun.
        lade = self.artikel("Browsertest lade", redacteur, cluster)
        v_steun = self.voorstel(lade, medewerker, "De termijn klopt niet meer. Het is nu drie weken.", "twee weken")
        for u in steuners:
            diensten.steun_geven(v_steun, u)
        v_weg = self.voorstel(lade, medewerker, "Hier stond een oude naam.", "deze tekst staat er niet meer")
        v_afwijzen = self.voorstel(lade, medewerker, "Kan dit hele artikel weg?", "")
        v_dubbel = self.voorstel(lade, steuners[0], "Twee weken is te kort, maak er drie van.", "twee weken")

        # 2. Ter inzage, opgepakt door de reviewer, met een opmerking en een meegenomen voorstel.
        inzage_a = self.artikel("Browsertest ter inzage", redacteur, cluster)
        v_mee = self.voorstel(inzage_a, medewerker, "Bel ook bij spoed in het weekend.", "Bel bij spoed dezelfde dag")
        c = self.concept(inzage_a, redacteur, TEKST.replace("dezelfde dag", "dezelfde dag, ook in het weekend"))
        Verbetervoorstel.objects.filter(pk=v_mee.pk).update(
            in_conceptversie=True, eigenaar=redacteur, status="in_behandeling"
        )
        review.ter_inzage_geven(inzage_a, redacteur, [team], c.stempel)
        inzage = Inzage.objects.get(artikel=inzage_a)
        review.oppakken(inzage, reviewer)
        review.opmerking_toevoegen(inzage, reviewer, "Klopt dit ook op feestdagen?", "ook in het weekend")

        # 3. Kaal gepubliceerd artikel: de hele stroom van bewerken tot publiceren loopt hierop.
        stroom = self.artikel("Browsertest stroom", redacteur, cluster)

        # 4. Met een conceptversie (niet ter inzage): spoedcorrectie en weggooien.
        spoed = self.artikel("Browsertest spoed", redacteur, cluster)
        self.concept(spoed, redacteur, TEKST.replace("twee weken", "vier weken"))

        # 5. Kaal gepubliceerd artikel waar niets aan gebeurt: voor de axe-meting.
        rustig = self.artikel("Browsertest rustig", redacteur, cluster)

        demo = Artikel.objects.get(slug="rappel-versturen")
        assert Conceptversie.objects.count() == 2  # noqa: S101 - controle op de eigen opzet
        return {
            "lade": {
                "artikel": lade.pk,
                "steun": v_steun.pk,
                "weg": v_weg.pk,
                "afwijzen": v_afwijzen.pk,
                "dubbel": v_dubbel.pk,
            },
            "inzage": {"artikel": inzage_a.pk, "inzage": inzage.pk, "voorstel": v_mee.pk},
            "stroom": {"artikel": stroom.pk},
            "spoed": {"artikel": spoed.pk},
            "rustig": {"artikel": rustig.pk, "slug": rustig.slug},
            # Een artikel uit de demo-inhoud, met tags, onboarding en een wijzigingsmelding.
            "demo": {"artikel": demo.pk, "slug": demo.slug},
        }
