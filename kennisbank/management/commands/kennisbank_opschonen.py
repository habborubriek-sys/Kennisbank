"""Voert de bewaartermijnen uit. Dagelijks inplannen (cronjob / Kubernetes CronJob)."""

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from kennisbank import diensten
from kennisbank.models import (
    AssistentDagTotaal,
    AssistentTelling,
    FavorietenMail,
    RecentBezocht,
    Verbetervoorstel,
    VoorstelStatus,
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
        anoniem = Verbetervoorstel.objects.filter(
            status__in=[VoorstelStatus.VERWERKT, VoorstelStatus.AFGEWEZEN],
            behandeld_op__lt=nu - timezone.timedelta(days=settings.KB_ANONIMISEER_VOORSTEL_DAGEN),
            ingediend_door__isnull=False,
        ).update(ingediend_door=None)
        call_command("clearsessions")  # verlopen sessies uit django_session
        # Eerst de openstaande favorietenmail versturen, dan de verzonden regels na 30 dagen opruimen.
        mails = diensten.verstuur_favorietenmail()
        wachtrij = FavorietenMail.objects.filter(verzonden_op__lt=nu - timezone.timedelta(days=30)).delete()[0]
        self.stdout.write(
            f"Opgeschoond: {recent} recent-bezocht-regels, {stats} statistiekregels, "
            f"{anoniem} voorstellen geanonimiseerd, verlopen sessies verwijderd, "
            f"{mails} favorietenmail(s) verstuurd, {wachtrij} verzonden mailregels opgeruimd."
        )
