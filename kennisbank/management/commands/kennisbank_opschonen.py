"""Voert de bewaartermijnen uit. Dagelijks inplannen (cronjob / Kubernetes CronJob)."""

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from kennisbank import diensten
from kennisbank.models import (
    AFGEHANDELD,
    AssistentDagTotaal,
    AssistentTelling,
    FavorietenMail,
    RecentBezocht,
    Steun,
    Verbetervoorstel,
    VoorstelBericht,
    VoorstelNotitie,
    WeergaveTelling,
    ZoekTelling,
)


class Command(BaseCommand):
    help = "Verwijder of anonimiseer gegevens waarvan de bewaartermijn is verstreken."

    def handle(self, **opties):
        nu = timezone.now()
        vandaag = timezone.localdate()
        recent = RecentBezocht.objects.filter(
            bezocht_op__lt=nu - timezone.timedelta(days=settings.KB_BEWAAR_RECENT_DAGEN)
        ).delete()[0]
        grens = vandaag - timezone.timedelta(days=settings.KB_BEWAAR_STATISTIEK_DAGEN)
        stats = (
            WeergaveTelling.objects.filter(datum__lt=grens).delete()[0]
            + ZoekTelling.objects.filter(datum__lt=grens).delete()[0]
            + AssistentTelling.objects.filter(datum__lt=grens).delete()[0]
            + AssistentDagTotaal.objects.filter(datum__lt=grens).delete()[0]
        )
        # Anonimiseren van afgehandelde verbetervoorstellen. De naam van de indiener staat op twee
        # plekken: op het voorstel zelf en op zijn eventuele berichten. Allebei wissen, anders is de
        # bewaartermijn alleen cosmetisch: het voorstel zegt dan "Onbekend (geanonimiseerd)" terwijl
        # het bericht eronder nog de volledige naam toont.
        #
        # De naam van de redacteur die heeft terugkoppeld, blijft wél staan: dat is verantwoording,
        # zolang het voorstel bestaat. Die keuze staat in docs/beveiliging-en-privacy.md.
        verjaard = Verbetervoorstel.objects.filter(
            status__in=AFGEHANDELD,
            behandeld_op__lt=nu - timezone.timedelta(days=settings.KB_ANONIMISEER_VOORSTEL_DAGEN),
        )
        berichten_anoniem = VoorstelBericht.objects.filter(
            voorstel__in=verjaard, van_redactie=False, auteur__isnull=False
        ).update(auteur=None)
        anoniem = verjaard.filter(ingediend_door__isnull=False).update(ingediend_door=None)
        # Wie een voorstel steunde, is ook een naam: het aantal blijft staan, de namen gaan weg.
        Steun.objects.filter(voorstel__in=verjaard, gebruiker__isnull=False).update(gebruiker=None)
        # Interne notities kunnen namen bevatten en zijn na afhandeling niet meer nodig: weg.
        notities = VoorstelNotitie.objects.filter(voorstel__in=verjaard).delete()[0]
        call_command("clearsessions")  # verlopen sessies uit django_session
        # Eerst de openstaande favorietenmail versturen, dan de verzonden regels na 30 dagen opruimen.
        mails = diensten.verstuur_favorietenmail()
        voorstellenmails = diensten.verstuur_voorstellenmail()
        wachtrij = FavorietenMail.objects.filter(verzonden_op__lt=nu - timezone.timedelta(days=30)).delete()[0]
        claims = diensten.verlopen_claims_opruimen()
        klad = diensten.kladversies_opruimen()
        bakken = diensten.bakken_rechtzetten()  # vangnet; normaal gebeurt dit al bij de rechtenwijziging
        diensten.stand_vastleggen(
            "opschonen",
            f"{mails} mail(s) verstuurd, {voorstellenmails} samenvatting(en) voorstellen, "
            f"{claims} claim(s) opgeruimd, {klad} kladversie(s) opgeruimd, "
            f"{bakken} voorstel(len) teruggelegd",
        )
        self.stdout.write(
            f"Opgeschoond: {recent} recent-bezocht-regels, {stats} statistiekregels, "
            f"{anoniem} voorstellen geanonimiseerd ({berichten_anoniem} bericht(en) meegenomen, "
            f"{notities} interne notitie(s) verwijderd), "
            f"verlopen sessies verwijderd, "
            f"{mails} favorietenmail(s) verstuurd, {voorstellenmails} samenvatting(en) van nieuwe voorstellen, "
            f"{wachtrij} verzonden mailregels opgeruimd, "
            f"{claims} verlopen bewerkclaim(s) opgeruimd, {klad} oude kladversie(s) opgeruimd, "
            f"{bakken} voorstel(len) teruggelegd in de gezamenlijke bak (eigenaar geen redacteur meer)."
        )
