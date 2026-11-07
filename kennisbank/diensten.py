"""Bedrijfslogica die vanuit meerdere plekken (beheerscherm, API, import) wordt gebruikt."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import (
    Artikel,
    ArtikelVersie,
    Favoriet,
    Profiel,
    RecentBezocht,
    Rol,
    Status,
    WeergaveTelling,
    ZoekTelling,
)

log = logging.getLogger("kennisbank")


def momentopname(artikel: Artikel) -> dict:
    return {
        "titel": artikel.titel,
        "samenvatting": artikel.samenvatting,
        "soort": artikel.soort,
        "eigenaar": artikel.eigenaar,
        "omgeving": artikel.omgeving.slug,
        "clusters": sorted(artikel.clusters.values_list("naam", flat=True)),
        "tags": sorted(artikel.tags.values_list("naam", flat=True)),
        "zaaktypen": sorted(artikel.zaaktypen.values_list("code", flat=True)),
        "formaat": "artikel-html",
        "inhoud": artikel.inhoud,
    }


def herbouw_secties(artikel: Artikel) -> int:
    """Bouw de afgeleide sectietabel opnieuw op uit Artikel.inhoud. Geeft het aantal secties terug."""
    from .inhoud import blokken
    from .models import Sectie

    alle = blokken(artikel.inhoud)
    vrije_tekst = "".join(b["html"] for b in alle if b["type"] == "tekst")
    rijen = [Sectie(artikel=artikel, volgorde=0, kop="", inhoud=vrije_tekst)]
    rijen += [
        Sectie(artikel=artikel, volgorde=b["nummer"], kop=b["kop"], inhoud=b["html"])
        for b in alle
        if b["type"] == "sectie"
    ]
    artikel.secties.all().delete()
    Sectie.objects.bulk_create(rijen)
    werk_zoekvectoren_bij(artikel.pk)
    return len(rijen) - 1


# Zoekdocumenten in PostgreSQL. Dezelfde SQL staat (bevroren) in migratie 0007 voor de eerste vulling.
# Secties: artikeltitel en kop wegen het zwaarst, dan de sectietekst, dan de samenvatting.
# Artikel: titel en tags het zwaarst, dan samenvatting, dan alle sectieteksten.
_SQL_SECTIE_VECTOR = """
UPDATE kennisbank_sectie s SET zoekvector =
    setweight(to_tsvector('dutch', a.titel), 'A')
 || setweight(to_tsvector('dutch', coalesce(s.kop, '')), 'A')
 || setweight(to_tsvector('dutch', coalesce(s.inhoud, '')), 'B')
 || setweight(to_tsvector('dutch', coalesce(a.samenvatting, '')), 'D')
FROM kennisbank_artikel a WHERE a.id = s.artikel_id AND a.id = %s
"""
_SQL_ARTIKEL_VECTOR = """
UPDATE kennisbank_artikel a SET zoekvector =
    setweight(to_tsvector('dutch', a.titel), 'A')
 || setweight(to_tsvector('dutch', coalesce((SELECT string_agg(t.naam, ' ') FROM kennisbank_artikel_tags at
        JOIN kennisbank_tag t ON t.id = at.tag_id WHERE at.artikel_id = a.id), '')), 'A')
 || setweight(to_tsvector('dutch', coalesce(a.samenvatting, '')), 'B')
 || setweight(to_tsvector('dutch', coalesce((SELECT string_agg(coalesce(s.kop, '') || ' ' || coalesce(s.inhoud, ''),
        ' ') FROM kennisbank_sectie s WHERE s.artikel_id = a.id), '')), 'C')
WHERE a.id = %s
"""


def werk_zoekvectoren_bij(artikel_id: int) -> None:
    """Zet de opgeslagen zoekdocumenten van het artikel en zijn secties opnieuw (na wijziging van inhoud of tags)."""
    from django.db import connection

    with connection.cursor() as c:
        c.execute(_SQL_SECTIE_VECTOR, [artikel_id])
        c.execute(_SQL_ARTIKEL_VECTOR, [artikel_id])


@transaction.atomic
def registreer_publicatie(artikel: Artikel, gebruiker=None, toelichting: str = "") -> ArtikelVersie | None:
    """Leg een nieuwe versie vast als een gepubliceerd artikel inhoudelijk is gewijzigd.

    Wordt aangeroepen na elke opslag. Concepten krijgen geen versie; bij elke wijziging
    van een gepubliceerd artikel ontstaat er wel één. Ongewijzigd opslaan levert niets op.
    """
    if artikel.status != Status.GEPUBLICEERD:
        return None
    artikel = Artikel.objects.select_for_update().get(pk=artikel.pk)
    inhoud = momentopname(artikel)
    laatste = artikel.versies.order_by("-versie").first()
    if laatste and laatste.inhoud == inhoud:
        return None
    nieuw_nummer = (laatste.versie if laatste else 0) + 1
    nu = timezone.now()
    versie = ArtikelVersie.objects.create(
        artikel=artikel,
        versie=nieuw_nummer,
        inhoud=inhoud,
        toelichting=toelichting[:300],
        gepubliceerd_door=gebruiker if gebruiker and gebruiker.is_authenticated else None,
        gepubliceerd_op=nu,
    )
    Artikel.objects.filter(pk=artikel.pk).update(versie=nieuw_nummer, gepubliceerd_op=nu)
    log.info("artikel gepubliceerd", extra={"artikel": artikel.slug, "versie": nieuw_nummer})
    return versie


def profiel(gebruiker) -> Profiel:
    p, _ = Profiel.objects.get_or_create(gebruiker=gebruiker)
    return p


def registreer_weergave(gebruiker, artikel: Artikel):
    vandaag = timezone.localdate()
    telling, _ = WeergaveTelling.objects.get_or_create(artikel=artikel, datum=vandaag)
    WeergaveTelling.objects.filter(pk=telling.pk).update(aantal=F("aantal") + 1)

    RecentBezocht.objects.update_or_create(
        gebruiker=gebruiker, artikel=artikel, defaults={"bezocht_op": timezone.now()}
    )
    oud = RecentBezocht.objects.filter(gebruiker=gebruiker).order_by("-bezocht_op")[settings.KB_RECENT_MAX :]
    RecentBezocht.objects.filter(pk__in=[r.pk for r in oud]).delete()


def registreer_zoekopdracht(term: str, aantal_resultaten: int, omgevingen):
    """Telt de zoekterm mee voor elke omgeving waarin is gezocht (meestal één)."""
    term = " ".join(term.lower().split())[:100]
    if len(term) < 2:
        return
    for omgeving_id in omgevingen:
        telling, _ = ZoekTelling.objects.get_or_create(omgeving_id=omgeving_id, term=term, datum=timezone.localdate())
        ZoekTelling.objects.filter(pk=telling.pk).update(
            aantal=F("aantal") + 1,
            zonder_resultaat=F("zonder_resultaat") + (1 if aantal_resultaten == 0 else 0),
        )


def zet_favoriet(gebruiker, artikel: Artikel, aan: bool):
    if aan:
        Favoriet.objects.get_or_create(gebruiker=gebruiker, artikel=artikel)
    else:
        Favoriet.objects.filter(gebruiker=gebruiker, artikel=artikel).delete()


# --- Meldingen per e-mail (alleen als KB_EMAIL_HOST is ingesteld) ----------------------


def _mail(onderwerp, tekst, ontvangers):
    ontvangers = sorted({o for o in ontvangers if o})
    if not settings.KB_EMAIL_AAN or not ontvangers:
        return
    try:
        send_mail(onderwerp, tekst, None, ontvangers, fail_silently=False)
    except Exception:  # noqa: BLE001 - een mislukte mail mag de gebruiker niet blokkeren
        log.exception("versturen e-mail mislukt", extra={"onderwerp": onderwerp})


def meld_nieuw_voorstel(voorstel):
    from django.contrib.auth import get_user_model

    redacteuren = (
        get_user_model()
        .objects.filter(
            groups__kennisbank_toegang__omgeving=voorstel.artikel.omgeving,
            groups__kennisbank_toegang__rol=Rol.REDACTEUR,
            is_active=True,
        )
        .values_list("email", flat=True)
    )
    _mail(
        f"Nieuw verbetervoorstel: {voorstel.artikel.titel}",
        f"Er is een verbetervoorstel ingediend bij '{voorstel.artikel.titel}'.\n\n"
        f"{voorstel.tekst}\n\nBehandelen: {settings.KB_BASIS_URL}/voorstellen",
        redacteuren,
    )


def meld_terugkoppeling(voorstel):
    if not voorstel.ingediend_door:
        return
    _mail(
        f"Terugkoppeling op je verbetervoorstel: {voorstel.artikel.titel}",
        f"Status: {voorstel.get_status_display()}\n\n{voorstel.terugkoppeling}\n\n"
        f"Bekijk: {settings.KB_BASIS_URL}/voorstellen",
        [voorstel.ingediend_door.email],
    )
