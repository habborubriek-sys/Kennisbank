"""Bedrijfslogica die vanuit meerdere plekken (beheerscherm, API, import) wordt gebruikt."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.formats import date_format

from .models import (
    Artikel,
    ArtikelVersie,
    Bericht,
    BerichtStatus,
    Favoriet,
    FavorietenMail,
    Profiel,
    RecentBezocht,
    Rol,
    Status,
    WeergaveTelling,
    WijzigingGezien,
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
def registreer_publicatie(
    artikel: Artikel, gebruiker=None, toelichting: str = "", kleine_correctie: bool = False
) -> ArtikelVersie | None:
    """Leg een nieuwe versie vast als een gepubliceerd artikel inhoudelijk is gewijzigd.

    Wordt aangeroepen na elke opslag. Concepten krijgen geen versie; bij elke wijziging
    van een gepubliceerd artikel ontstaat er wel één. Ongewijzigd opslaan levert niets op.

    Vanaf de tweede versie krijgen medewerkers een wijzigingsmelding bij het artikel en gaat er
    een e-mail in de wachtrij voor wie het artikel als favoriet heeft — tenzij het een kleine
    correctie is (typfout, opmaak). De eerste versie is de publicatie zelf; daar is niets gewijzigd.
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
        kleine_correctie=kleine_correctie,
        gepubliceerd_door=gebruiker if gebruiker and gebruiker.is_authenticated else None,
        gepubliceerd_op=nu,
    )
    Artikel.objects.filter(pk=artikel.pk).update(versie=nieuw_nummer, gepubliceerd_op=nu)
    log.info("artikel gepubliceerd", extra={"artikel": artikel.slug, "versie": nieuw_nummer})
    if nieuw_nummer > 1 and not kleine_correctie:
        zet_favorietenmail_klaar(artikel, versie)
    return versie


def is_inhoudelijk_gewijzigd(artikel: Artikel, nieuwe_momentopname: dict) -> bool:
    """Of opslaan met deze gegevens een nieuwe versie zou opleveren (voor de controle in het beheerformulier)."""
    laatste = artikel.versies.order_by("-versie").first() if artikel.pk else None
    return laatste is not None and laatste.inhoud != nieuwe_momentopname


# --- Wijzigingsmeldingen ---------------------------------------------------------------


def wijzigingen_voor(gebruiker, artikelen) -> dict[int, dict]:
    """Per artikel-id de nog niet afgevinkte inhoudelijke wijziging voor deze gebruiker, of niets.

    Een wijziging telt als: een versie hoger dan 1, geen kleine correctie, gepubliceerd nadat de
    gebruiker voor het eerst inlogde (eerder gepubliceerd = nooit anders gekend), en hoger dan de
    versie die de gebruiker met "Ik snap het" heeft afgevinkt. Van meerdere wijzigingen telt de laatste.
    """
    if hasattr(artikelen, "values_list"):
        ids = list(artikelen.values_list("pk", flat=True))
    else:
        ids = [a.pk for a in artikelen]
    if not ids or not gebruiker or not gebruiker.is_authenticated:
        return {}
    gezien = dict(
        WijzigingGezien.objects.filter(gebruiker=gebruiker, artikel_id__in=ids).values_list("artikel_id", "versie")
    )
    versies = (
        ArtikelVersie.objects.filter(
            artikel_id__in=ids, versie__gt=1, kleine_correctie=False, gepubliceerd_op__gt=gebruiker.date_joined
        )
        .order_by("artikel_id", "-versie")
        .values("artikel_id", "versie", "toelichting", "gepubliceerd_op")
    )
    uit = {}
    for v in versies:
        aid = v["artikel_id"]
        if aid in uit:
            continue  # alleen de hoogste per artikel (de volgorde is -versie)
        if v["versie"] <= gezien.get(aid, 0):
            continue
        uit[aid] = {"versie": v["versie"], "toelichting": v["toelichting"], "datum": v["gepubliceerd_op"]}
    return uit


def markeer_gezien(gebruiker, artikelen, tot_versie: int | None = None) -> int:
    """Vink de wijzigingsmelding af tot en met `tot_versie` (standaard: de huidige versie van het artikel).

    De frontend stuurt de versie mee die de gebruiker te zien kreeg; is er intussen een nieuwere versie
    gepubliceerd, dan blijft die als melding staan. Afvinken gaat nooit terug naar een lagere versie.
    """
    n = 0
    for a in artikelen:
        versie = min(tot_versie, a.versie) if tot_versie else a.versie
        rij, nieuw = WijzigingGezien.objects.get_or_create(
            gebruiker=gebruiker, artikel=a, defaults={"versie": versie, "gezien_op": timezone.now()}
        )
        if not nieuw and rij.versie < versie:
            rij.versie = versie
            rij.gezien_op = timezone.now()
            rij.save(update_fields=["versie", "gezien_op"])
        n += 1
    return n


# --- Nieuws ------------------------------------------------------------------------------


def maak_nieuwsconcept(artikel: Artikel, versie: ArtikelVersie, gebruiker=None) -> Bericht:
    """Zet de toelichting van een publicatie klaar als concept-nieuwsbericht bij het artikel."""
    b = Bericht.objects.create(
        omgeving=artikel.omgeving,
        titel=f"Gewijzigd: {artikel.titel}"[:200],
        tekst=f"<p>{_html_escape(versie.toelichting) or 'Het artikel is bijgewerkt.'}</p>",
        status=BerichtStatus.CONCEPT,
        auteur=gebruiker if gebruiker and gebruiker.is_authenticated else None,
    )
    b.artikelen.add(artikel)
    return b


def _html_escape(tekst: str) -> str:
    from django.utils.html import escape

    return escape(tekst or "")


def berichten_voor(gebruiker, omgevingen):
    """Gepubliceerde berichten in de omgevingen die de gebruiker mag lezen, vastgepind eerst."""
    return (
        Bericht.objects.gepubliceerd()
        .filter(omgeving_id__in=omgevingen)
        .select_related("omgeving", "auteur")
        .prefetch_related("artikelen")
    )


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


def _mail(onderwerp, tekst, ontvangers) -> bool:
    """Verstuurt een e-mail als e-mail aan staat. Geeft terug of dat lukte; een fout blokkeert nooit de gebruiker."""
    ontvangers = sorted({o for o in ontvangers if o})
    if not settings.KB_EMAIL_AAN or not ontvangers:
        return False
    try:
        send_mail(onderwerp, tekst, None, ontvangers, fail_silently=False)
        return True
    except Exception:  # noqa: BLE001 - een mislukte mail mag de gebruiker niet blokkeren
        log.exception("versturen e-mail mislukt", extra={"onderwerp": onderwerp})
        return False


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


# --- E-mail bij wijziging van een favoriet artikel -------------------------------------
#
# KB_FAVORIETEN_MAIL:  gebundeld (standaard) = in de wachtrij; het commando kennisbank_favorietenmail
#                      (of kennisbank_opschonen) stuurt per ontvanger één mail met alles wat open staat.
#                      direct = meteen één mail per wijziging.  uit = geen mail (de melding in de app blijft).
# Medewerkers kunnen het zelf uitzetten (Profiel.mail_bij_favorieten).


def zet_favorietenmail_klaar(artikel: Artikel, versie: ArtikelVersie) -> int:
    """Zet voor elke ontvanger een regel in de wachtrij; bij 'direct' wordt die meteen verstuurd."""
    modus = settings.KB_FAVORIETEN_MAIL
    if modus == "uit":
        return 0
    from .rechten import Rechten

    ontvangers = (
        Favoriet.objects.filter(artikel=artikel, gebruiker__is_active=True)
        .exclude(gebruiker__email="")
        .exclude(gebruiker__kennisbank_profiel__mail_bij_favorieten=False)
        .select_related("gebruiker")
    )
    # Alleen wie het artikel (nog) mag lezen; een ingetrokken toegang betekent ook geen mail meer.
    regels = [
        FavorietenMail(gebruiker=f.gebruiker, artikel=artikel, versie=versie.versie, toelichting=versie.toelichting)
        for f in ontvangers
        if Rechten(f.gebruiker).mag_lezen(artikel)
    ]
    FavorietenMail.objects.bulk_create(regels)
    if modus == "direct" and regels:
        transaction.on_commit(verstuur_favorietenmail)
    return len(regels)


@transaction.atomic
def verstuur_favorietenmail() -> int:
    """Bundelt alle openstaande regels per ontvanger tot één e-mail. Geeft het aantal verstuurde mails terug.

    Een regel wordt pas als verzonden gemarkeerd als de mail is gelukt; bij een storing blijft hij staan
    voor de volgende ronde. De regels worden vergrendeld, zodat twee gelijktijdige runs (cronjob en
    'direct'-modus) niet dezelfde mail twee keer sturen.
    """
    if settings.KB_FAVORIETEN_MAIL == "uit":
        return 0
    open_regels = (
        FavorietenMail.objects.filter(verzonden_op__isnull=True)
        .select_for_update(skip_locked=True, of=("self",))
        .select_related("gebruiker", "artikel")
        .order_by("gebruiker_id", "aangemaakt_op")
    )
    per_ontvanger: dict[int, list[FavorietenMail]] = {}
    for r in open_regels:
        per_ontvanger.setdefault(r.gebruiker_id, []).append(r)
    verstuurd = 0
    nu = timezone.now()
    for regels in per_ontvanger.values():
        gebruiker = regels[0].gebruiker
        # Per artikel alleen de laatste wijziging noemen (twee keer bijgewerkt = één regel), en alleen
        # artikelen die nog gepubliceerd zijn (een inmiddels gearchiveerd artikel is geen nieuws meer).
        laatste: dict[int, FavorietenMail] = {}
        for r in regels:
            if r.artikel.status == Status.GEPUBLICEERD:
                laatste[r.artikel_id] = r
        rijen = sorted(laatste.values(), key=lambda r: r.artikel.titel.lower())
        gelukt = True
        if rijen and gebruiker.email and settings.KB_EMAIL_AAN:
            gelukt = _mail(_favorieten_onderwerp(rijen), _favorieten_tekst(gebruiker, rijen), [gebruiker.email])
            verstuurd += int(gelukt)
        if gelukt:
            FavorietenMail.objects.filter(pk__in=[r.pk for r in regels]).update(verzonden_op=nu)
    return verstuurd


def _favorieten_onderwerp(rijen) -> str:
    naam = settings.KB_APP_NAAM
    if len(rijen) == 1:
        return f"{naam}: '{rijen[0].artikel.titel}' is gewijzigd"
    return f"{naam}: {len(rijen)} favoriete artikelen zijn gewijzigd"


def _favorieten_tekst(gebruiker, rijen) -> str:
    aanhef = gebruiker.first_name or gebruiker.get_full_name() or "collega"
    regels = [f"Beste {aanhef},", ""]
    regels.append(
        "Een artikel dat je als favoriet hebt is inhoudelijk gewijzigd:"
        if len(rijen) == 1
        else "Deze artikelen die je als favoriet hebt zijn inhoudelijk gewijzigd:"
    )
    regels.append("")
    for r in rijen:
        datum = date_format(timezone.localtime(r.aangemaakt_op), "j F Y")
        regels.append(f"- {r.artikel.titel} (versie {r.versie}, {datum})")
        if r.toelichting:
            regels.append(f"  {r.toelichting}")
        regels.append(f"  {settings.KB_BASIS_URL}{r.artikel.get_absolute_url()}")
        regels.append("")
    regels.append(
        "Je krijgt deze e-mail omdat je het artikel als favoriet hebt gemarkeerd. "
        f"Uitzetten kan in de kennisbank, onder 'Instellingen' in het menu: {settings.KB_BASIS_URL}/"
    )
    return "\n".join(regels)
