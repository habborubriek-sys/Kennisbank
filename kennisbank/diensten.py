"""Bedrijfslogica die vanuit meerdere plekken (beheerscherm, API, import) wordt gebruikt."""

import calendar
import datetime
import logging
import re

from django.conf import settings
from django.core.mail import send_mail
from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.formats import date_format

from .models import (
    AFGEHANDELD,
    OPEN,
    Artikel,
    ArtikelVersie,
    Bericht,
    BerichtStatus,
    BewerkClaim,
    Conceptversie,
    Favoriet,
    FavorietenMail,
    Kladversie,
    Profiel,
    RecentBezocht,
    Rol,
    Status,
    Steun,
    Systeemstand,
    Verbetervoorstel,
    VoorstelBericht,
    VoorstelNotitie,
    VoorstelStatus,
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
    # Alleen een rij voor de vrije tekst als die er ook echt is. Een lege rij droeg wél de artikeltitel
    # in zijn zoekdocument en won daarmee regelmatig de zoekopdracht, waarna de assistent "Dit staat
    # in …" zei en vervolgens niets kon citeren.
    rijen = []
    if vrije_tekst.strip():
        rijen.append(Sectie(artikel=artikel, volgorde=0, kop="", inhoud=vrije_tekst))
    rijen += [
        Sectie(artikel=artikel, volgorde=b["nummer"], kop=b["kop"], inhoud=b["html"])
        for b in alle
        if b["type"] == "sectie"
    ]
    artikel.secties.all().delete()
    Sectie.objects.bulk_create(rijen)
    werk_zoekvectoren_bij(artikel.pk)
    return sum(1 for r in rijen if r.volgorde)


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
    velden = {"versie": nieuw_nummer, "gepubliceerd_op": nu}
    nieuwe_datum = herzieningsdatum(artikel, kleine_correctie=kleine_correctie)
    if nieuwe_datum is not None:
        velden["herzien_voor"] = nieuwe_datum
        artikel.herzien_voor = nieuwe_datum
    Artikel.objects.filter(pk=artikel.pk).update(**velden)
    log.info("artikel gepubliceerd", extra={"artikel": artikel.slug, "versie": nieuw_nummer})
    if nieuw_nummer > 1 and not kleine_correctie:
        zet_favorietenmail_klaar(artikel, versie)
    return versie


def stand_vastleggen(sleutel: str, melding: str = "") -> None:
    """Leg vast dat een onderhoudstaak nu heeft gelopen (voor de statuspagina)."""
    Systeemstand.objects.update_or_create(
        sleutel=sleutel, defaults={"moment": timezone.now(), "melding": melding[:300]}
    )


def laatste_stand(sleutel: str):
    """De laatste keer dat een onderhoudstaak liep, of None als dat nooit is vastgelegd."""
    return Systeemstand.objects.filter(sleutel=sleutel).first()


#: Titels die onmiskenbaar nog uit de bestandsmap komen. Let op: "concept" en "definitief" in gewone
#: schrijfwijze zijn gewone woorden ("conceptbesluit"), dus daar gaan we niet op af — alleen op
#: schreeuwende kapitalen en op wat er verder in bestandsnamen staat.
_TITEL_RUIS = re.compile(
    r"\.(docx?|pdf|odt|rtf|txt)\s*$"
    r"|\b(kopie\s+van|nieuwe\s+map)\b"
    r"|\bversie\s*\d|\bv\d+[._]\d+\b|[_\s-]v\d",
    re.I,
)
_TITEL_RUIS_KAPITAAL = re.compile(r"\b(DEFINITIEF|DEFINITIEVE|FINAL|CONCEPT)\b")

#: Samenvattingen die net zo goed leeg hadden kunnen zijn.
_SAMENVATTING_RUIS = {
    "",
    "nvt",
    "n.v.t",
    "n.v.t.",
    "geen",
    "volgt",
    "volgt nog",
    "nog invullen",
    "nog in te vullen",
    "tbd",
    "todo",
    "to do",
    "x",
    "xxx",
    "test",
    "tekst",
    "samenvatting",
    "zie artikel",
    "zie inhoud",
}

#: Minimale lengte van een samenvatting die iets zegt.
MINIMALE_SAMENVATTING = 20


def problemen_eerste_publicatie(*, titel: str, samenvatting: str, inhoud: str) -> dict[str, str]:
    """Wat er nog niet af is aan een artikel dat voor het eerst gepubliceerd gaat worden.

    Geeft per veld een melding terug, of een leeg resultaat als het artikel klaar is. Deze controle
    hoort bij *elke* route naar publiceren: het bewerkformulier én de lijstactie. In 1.9.0 zat hij
    alleen in het formulier, waardoor de lijstactie hem omzeilde — dezelfde fout als eerder met de
    verplichte wijzigingstoelichting.

    Alleen dingen die onmiskenbaar nog niet af zijn: een bestandsnaam of versie-aanduiding als titel,
    een lege of nietszeggende samenvatting, of een sectie zonder titel (die heet voor de lezer
    "Sectie 1"). Een ontbrekend zaaktype of tag hoort hier niet: slecht vindbaar is soms de bedoeling.
    """
    from .inhoud import secties_zonder_kop

    uit = {}
    titel = (titel or "").strip()
    if titel and (_TITEL_RUIS.search(titel) or _TITEL_RUIS_KAPITAAL.search(titel)):
        uit["titel"] = (
            "Deze titel lijkt een bestandsnaam of een versie-aanduiding. Medewerkers zoeken op de titel, "
            "dus geef het artikel de naam waaronder zij het zouden zoeken."
        )
    kort = " ".join((samenvatting or "").split())
    if not kort:
        uit["samenvatting"] = (
            "Vul een samenvatting in. Medewerkers zien die in de lijst en in de zoekresultaten; zonder "
            "samenvatting moeten zij elk artikel openen om te zien of het het juiste is."
        )
    elif kort.strip(" .-–—_").lower() in _SAMENVATTING_RUIS or len(kort) < MINIMALE_SAMENVATTING:
        uit["samenvatting"] = (
            "Deze samenvatting zegt nog niets. Schrijf één of twee zinnen over waar dit artikel over gaat."
        )
    zonder_kop = secties_zonder_kop(inhoud or "")
    if zonder_kop:
        nummers = ", ".join(str(n) for n in zonder_kop)
        uit["inhoud"] = (
            f"Er {'is een sectie' if len(zonder_kop) == 1 else 'zijn secties'} zonder titel "
            f"(nummer {nummers}). Medewerkers zien dat kader dan dichtgeklapt staan als "
            f"'Sectie {zonder_kop[0]}'. Geef elke sectie een titel, of haal het kader weg."
        )
    return uit


def herzieningsdatum(artikel: Artikel, *, kleine_correctie: bool = False):
    """De nieuwe datum "opnieuw nakijken voor" bij deze publicatie, of None als die niet verandert.

    Leeg veld wordt gevuld, en een datum die al verstreken is schuift mee: publiceren is immers het
    moment waarop de redacteur de tekst heeft nagekeken. Een kleine correctie (typfout, opmaak)
    schuift niets op — dat is geen inhoudelijke herziening. Een datum die de redacteur zelf in de
    toekomst heeft gezet, laten we staan.
    """
    maanden = getattr(settings, "KB_HERZIENINGSTERMIJN_MAANDEN", 12)
    if maanden <= 0:
        return None
    vandaag = timezone.localdate()
    if artikel.herzien_voor and (artikel.herzien_voor >= vandaag or kleine_correctie):
        return None
    jaar, maand = divmod(vandaag.month - 1 + maanden, 12)
    if vandaag.year + jaar > datetime.date.max.year:
        # Een onzinnige instelling mag geen serverfout bij het publiceren geven.
        log.warning("KB_HERZIENINGSTERMIJN_MAANDEN van %s valt buiten het datumbereik", maanden)
        return datetime.date.max
    dag = min(vandaag.day, calendar.monthrange(vandaag.year + jaar, maand + 1)[1])
    return vandaag.replace(year=vandaag.year + jaar, month=maand + 1, day=dag)


def te_herzien(queryset=None, dagen_vooruit: int = 0):
    """Gepubliceerde artikelen waarvan de herzieningsdatum is verstreken (of binnen `dagen_vooruit` komt)."""
    qs = queryset if queryset is not None else Artikel.objects.all()
    grens = timezone.localdate() + datetime.timedelta(days=dagen_vooruit)
    return qs.filter(status=Status.GEPUBLICEERD, herzien_voor__isnull=False, herzien_voor__lte=grens)


def is_inhoudelijk_gewijzigd(artikel: Artikel, nieuwe_momentopname: dict) -> bool:
    """Of opslaan met deze gegevens een nieuwe versie zou opleveren (voor de controle in het beheerformulier)."""
    laatste = artikel.versies.order_by("-versie").first() if artikel.pk else None
    return laatste is not None and laatste.inhoud != nieuwe_momentopname


# --- Wijzigingsmeldingen ---------------------------------------------------------------


#: Hoeveel eerdere gemiste wijzigingen we onder de nieuwste tonen. Meer dan dit is geen melding meer
#: maar een geschiedenis; daarvoor is de versiegeschiedenis in het beheerscherm.
MAX_EERDERE_WIJZIGINGEN = 4


def wijzigingen_voor(gebruiker, artikelen) -> dict[int, dict]:
    """Per artikel-id de nog niet afgevinkte inhoudelijke wijziging voor deze gebruiker, of niets.

    Een wijziging telt als: een versie hoger dan 1, geen kleine correctie, gepubliceerd nadat de
    gebruiker voor het eerst inlogde (eerder gepubliceerd = nooit anders gekend), en hoger dan de
    versie die de gebruiker met "Ik snap het" heeft afgevinkt.

    Zijn er meerdere wijzigingen gemist (bijvoorbeeld na een vakantie), dan staat de nieuwste bovenaan
    en staan de eerdere eronder in `eerdere`, nieuwste eerst. Afvinken gebeurt op de nieuwste versie en
    daarmee in één keer op alle regels: wie ze alle drie leest, hoeft niet drie keer te klikken.
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
        if v["versie"] <= gezien.get(aid, 0):
            continue
        regel = {"versie": v["versie"], "toelichting": v["toelichting"], "datum": v["gepubliceerd_op"]}
        if aid in uit:
            uit[aid]["aantal"] += 1
            if len(uit[aid]["eerdere"]) < MAX_EERDERE_WIJZIGINGEN:
                uit[aid]["eerdere"].append(regel)  # de volgorde is -versie, dus al nieuwste eerst
            continue
        # `aantal` is het werkelijke aantal gemiste wijzigingen; `eerdere` is er hooguit vier lang.
        # Zonder dat telde de app "eerdere + 1" en las iemand die er zeven miste "Er zijn 5 wijzigingen".
        uit[aid] = dict(regel, eerdere=[], aantal=1)
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


def mail_na_commit(onderwerp, tekst, ontvangers) -> None:
    """Verstuur de e-mail pas als de transactie is doorgevoerd.

    Zonder dit gaat de mail de deur uit terwijl de transactie nog open is. Rolt die daarna terug — een
    validatiefout verderop, een conflict — dan heeft de ontvanger een bericht gekregen over iets dat
    niet is gebeurd. Buiten een transactie verstuurt `on_commit` meteen.
    """
    transaction.on_commit(lambda: _mail(onderwerp, tekst, ontvangers))


def _mail(onderwerp, tekst, ontvangers) -> bool:
    """Verstuurt een e-mail als e-mail aan staat. Geeft terug of dat lukte; een fout blokkeert nooit de gebruiker."""
    ontvangers = sorted({o for o in ontvangers if o})
    if not settings.KB_EMAIL_AAN or not ontvangers:
        return False
    try:
        send_mail(onderwerp, tekst, None, ontvangers, fail_silently=False)
        return True
    except Exception as e:  # noqa: BLE001 - een mislukte mail mag de gebruiker niet blokkeren
        # Bewust zonder traceback en zonder adressen: uitzonderingen als SMTPRecipientsRefused bevatten
        # het e-mailadres, en dat hoort niet in een applicatielogboek terecht te komen.
        log.warning(
            "versturen e-mail mislukt",
            extra={"onderwerp": onderwerp, "fout": type(e).__name__, "ontvangers": len(ontvangers)},
        )
        return False


#: Na zoveel dagen telt een open voorstel in de dagelijkse samenvatting als "ligt lang".
LANG_LIGGEN_DAGEN = 30


def verstuur_voorstellenmail(nu=None) -> int:
    """De dagelijkse samenvatting voor redacteuren: welke voorstellen er sinds de vorige keer binnenkwamen.

    Vervangt de e-mail per nieuw voorstel aan elke redacteur (besluit c van Alex, 11 november). Wie
    in een omgeving redacteur is waar iets nieuws binnenkwam, krijgt één e-mail met de nieuwe
    voorstellen, wat er in zijn eigen bak ligt en wat al lang ligt. Komt er niets nieuws binnen, dan
    gaat er niets uit. Geeft het aantal verstuurde e-mails terug.
    """
    from django.contrib.auth import get_user_model

    nu = nu or timezone.now()
    vorige = laatste_stand("voorstellenmail")
    sinds = vorige.moment if vorige else nu - datetime.timedelta(days=1)
    nieuw = list(
        Verbetervoorstel.objects.filter(ingediend_op__gt=sinds, ingediend_op__lte=nu)
        .select_related("artikel", "cluster")
        .order_by("ingediend_op")
    )
    per_omgeving = {}
    for v in nieuw:
        per_omgeving.setdefault(v.artikel.omgeving_id, []).append(v)
    ontvangers = {}
    if per_omgeving:
        for u in (
            get_user_model()
            .objects.filter(
                is_active=True,
                groups__kennisbank_toegang__omgeving_id__in=list(per_omgeving),
                groups__kennisbank_toegang__rol=Rol.REDACTEUR,
            )
            .exclude(email="")
            .values_list("pk", "email", "groups__kennisbank_toegang__omgeving_id")
        ):
            ontvangers.setdefault((u[0], u[1]), set()).add(u[2])
    verstuurd = 0
    lang_grens = nu - datetime.timedelta(days=LANG_LIGGEN_DAGEN)
    for (pk, email), omgevingen in ontvangers.items():
        voorstellen = [v for oid in sorted(omgevingen) for v in per_omgeving.get(oid, [])]
        if not voorstellen:
            continue
        regels = [
            f"- {v.artikel.titel} ({'bak ' + v.cluster.naam if v.cluster_id else 'Algemeen'}): "
            f"{' '.join(v.tekst.split())[:140]}"
            for v in voorstellen
        ]
        eigen = Verbetervoorstel.objects.filter(eigenaar_id=pk, status__in=OPEN)
        n_eigen = eigen.count()
        n_ongeopend = eigen.filter(eigenaar_gezien_op__isnull=True).count()
        n_lang = Verbetervoorstel.objects.filter(
            status__in=OPEN, artikel__omgeving_id__in=omgevingen, ingediend_op__lt=lang_grens
        ).count()
        extra = []
        if n_eigen:
            extra.append(
                f"In jouw bak liggen {n_eigen} open voorstel(len)"
                + (f", waarvan {n_ongeopend} nog niet geopend." if n_ongeopend else ".")
            )
        if n_lang:
            extra.append(f"{n_lang} open voorstel(len) liggen al langer dan {LANG_LIGGEN_DAGEN} dagen.")
        tekst = (
            f"Sinds de vorige samenvatting {'is' if len(voorstellen) == 1 else 'zijn'} er {len(voorstellen)} "
            f"nieuw{'' if len(voorstellen) == 1 else 'e'} verbetervoorstel{'' if len(voorstellen) == 1 else 'len'} "
            "binnengekomen:\n\n"
            + "\n".join(regels)
            + "\n\n"
            + ("\n".join(extra) + "\n\n" if extra else "")
            + f"Naar je werkplek: {settings.KB_BASIS_URL}/beheer/"
        )
        onderwerp = f"Kennisbank: {len(voorstellen)} nieuw{'' if len(voorstellen) == 1 else 'e'} verbetervoorstel" + (
            "" if len(voorstellen) == 1 else "len"
        )
        if _mail(onderwerp, tekst, [email]):
            verstuurd += 1
    Systeemstand.objects.update_or_create(
        sleutel="voorstellenmail",
        defaults={"moment": nu, "melding": f"{len(nieuw)} nieuw(e) voorstel(len), {verstuurd} mail(s) verstuurd"},
    )
    return verstuurd


def meld_terugkoppeling(voorstel):
    """Een statuswijziging zonder nieuw bericht: alleen de nieuwe status, geen oud bericht erbij.

    Vroeger stond hier het laatste bericht in; dan kreeg de indiener bij 'Afgewezen' het tussenbericht
    "we kijken ernaar" als antwoord. Terug naar 'Nieuw' levert geen e-mail op: voor de indiener is er
    dan niets gebeurd.
    """
    if not voorstel.ingediend_door or voorstel.status == VoorstelStatus.NIEUW:
        return
    mail_na_commit(
        f"Je verbetervoorstel: {voorstel.artikel.titel}",
        f"De status van je verbetervoorstel bij '{voorstel.artikel.titel}' is nu: "
        f"{voorstel.get_status_display().lower()}.\n\nBekijk: {settings.KB_BASIS_URL}/voorstellen",
        [voorstel.ingediend_door.email],
    )


#: Binnen hoeveel seconden een identieke invoer als dubbelklik geldt in plaats van als nieuwe invoer.
#: Ruim genoeg voor een trage verbinding of een tweede tabblad, kort genoeg dat iemand die écht twee
#: keer hetzelfde wil zeggen daar niet door wordt gehinderd.
DUBBEL_VENSTER = 120


def slot(sleutel: str) -> None:
    """Een adviesslot tot het einde van de transactie, zodat twee gelijktijdige verzoeken op elkaar wachten.

    Zonder dit slot zien twee verzoeken die binnen enkele milliseconden aankomen allebei "bestaat nog
    niet" en maken ze allebei een rij aan — een gewone controle is daar niet genoeg voor. Hetzelfde
    patroon als bij het aanmaken van een artikel.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", [sleutel])


def bestaand_voorstel(artikel, gebruiker, tekst: str):
    """Een identiek voorstel van dezelfde persoon bij hetzelfde artikel van net, of None.

    Voor het dubbelklik-geval: dan wil de indiener één voorstel, geen twee. Het slot moet vóór de
    controle, anders komen twee gelijktijdige verzoeken er allebei door.
    """
    kern = " ".join((tekst or "").split()).lower()
    if not kern or not gebruiker or not gebruiker.is_authenticated:
        return None
    slot(f"voorstel:{artikel.pk}:{gebruiker.pk}:{kern[:200]}")
    return (
        Verbetervoorstel.objects.filter(
            artikel=artikel,
            ingediend_door=gebruiker,
            ingediend_op__gte=timezone.now() - datetime.timedelta(seconds=DUBBEL_VENSTER),
        )
        .filter(tekst__iexact=(tekst or "").strip())
        .first()
    )


def voorstelbericht_toevoegen(voorstel, auteur, tekst: str, *, van_redactie: bool, melden: bool = True):
    """Voeg een bericht toe aan het gesprek over een voorstel en meld het aan de andere kant.

    Dit is de enige plek waar een bericht ontstaat, zodat de afgeleide gegevens altijd kloppen: het
    veld `terugkoppeling` houdt het laatste bericht van procesmanagement vast (de app en de API
    tonen dat), en de leesmomenten worden bijgewerkt voor de kant die net iets heeft geschreven.
    """
    tekst = (tekst or "").strip()
    if not tekst:
        return None
    # Dubbelklik of een tweede tabblad: hetzelfde bericht twee keer versturen zou de indiener ook twee
    # keer dezelfde e-mail bezorgen. Het slot zorgt dat ook twee exact gelijktijdige verzoeken op
    # elkaar wachten, en dan vindt de tweede het bericht van de eerste wél.
    kern = " ".join(tekst.split()).lower()
    slot(f"voorstelbericht:{voorstel.pk}:{getattr(auteur, 'pk', 0)}:{kern[:200]}")
    al_gestuurd = voorstel.berichten.filter(
        auteur=auteur if auteur and auteur.is_authenticated else None,
        tekst__iexact=tekst,
        moment__gte=timezone.now() - datetime.timedelta(seconds=DUBBEL_VENSTER),
    ).first()
    if al_gestuurd:
        return al_gestuurd
    nu = timezone.now()
    bericht = VoorstelBericht.objects.create(
        voorstel=voorstel,
        auteur=auteur if auteur and auteur.is_authenticated else None,
        van_redactie=van_redactie,
        tekst=tekst,
        moment=nu,
    )
    if van_redactie:
        # Bewust NIET behandeld_door/behandeld_op bijwerken. Die betekenen "wie heeft dit voorstel
        # behandeld en wanneer" en worden gezet bij een statuswijziging. Zou een tussentijdse update
        # ("opgepakt, we kijken ernaar") behandeld_op opschuiven, dan schuift ook de bewaartermijn mee
        # waarop kennisbank_opschonen de naam van de indiener wist — en dat is precies wat we niet willen.
        voorstel.terugkoppeling = tekst
        voorstel.gelezen_redactie_op = nu
        velden = ["terugkoppeling", "gelezen_redactie_op"]
    else:
        voorstel.gelezen_indiener_op = nu
        velden = ["gelezen_indiener_op"]
    voorstel.save(update_fields=velden)
    if melden:
        meld_voorstelbericht(bericht)
    return bericht


def meld_voorstelbericht(bericht):
    """E-mail aan de indiener van het voorstel: procesmanagement heeft iets laten weten.

    Alleen deze richting: berichten gaan van procesmanagement naar de indiener (zie VoorstelBericht).
    Mocht er uit een oudere installatie nog een bericht van een indiener komen, dan gaat er geen mail
    uit; dat is in de kennisbank zelf wel te zien aan de ongelezen-teller.
    """
    if not bericht.van_redactie:
        return
    voorstel = bericht.voorstel
    ontvanger = voorstel.ingediend_door
    if not ontvanger or not ontvanger.email or not ontvanger.is_active:
        return
    mail_na_commit(
        f"Bericht over je verbetervoorstel: {voorstel.artikel.titel}",
        f"{bericht.naam} (procesmanagement) schreef:\n\n{bericht.tekst}\n\n"
        f"Status: {voorstel.get_status_display()}\n\n"
        f"Bekijk: {settings.KB_BASIS_URL}/voorstellen",
        [ontvanger.email],
    )


def voorstel_ongelezen(voorstel, gebruiker) -> int:
    """Hoeveel berichten deze gebruiker nog niet heeft gezien in dit gesprek.

    Voor de indiener tellen de berichten van procesmanagement, en omgekeerd; je eigen berichten
    hoef je niet te lezen.
    """
    van_mij_is_indiener = voorstel.ingediend_door_id == getattr(gebruiker, "pk", None)
    sinds = voorstel.gelezen_indiener_op if van_mij_is_indiener else voorstel.gelezen_redactie_op
    # In Python tellen op de berichten die de lijst al heeft opgehaald (prefetch_related). Met een
    # .filter().count() ging de prefetch verloren en deed de voorstellenpagina één extra query per
    # voorstel — bij driehonderd voorstellen dus driehonderd queries.
    # Ben ik de indiener, dan zijn de berichten van procesmanagement nieuw voor mij, en omgekeerd.
    return sum(
        1
        for b in voorstel.berichten.all()
        if b.van_redactie == van_mij_is_indiener and (sinds is None or b.moment > sinds)
    )


def voorstel_gelezen(voorstel, gebruiker) -> None:
    """Markeer het gesprek als gelezen voor de kant waar deze gebruiker op zit."""
    nu = timezone.now()
    if voorstel.ingediend_door_id == getattr(gebruiker, "pk", None):
        voorstel.gelezen_indiener_op = nu
        voorstel.save(update_fields=["gelezen_indiener_op"])
    else:
        voorstel.gelezen_redactie_op = nu
        voorstel.save(update_fields=["gelezen_redactie_op"])


# --- Conceptversie: een nieuwe versie naast de gepubliceerde --------------------------------
#
# Medewerkers zien de gepubliceerde tekst; de redactie werkt in de conceptversie. Opslaan als
# conceptversie raakt het artikel niet (geen versie, geen melding, geen zoekindex). Publiceren gaat via
# het gewone opslaan van het bewerkscherm; daarna verdwijnt de conceptversie.


class ConceptConflict(Exception):
    """De conceptversie is gewijzigd (of weg) sinds dit scherm werd geopend."""


def concept_velden(cleaned_data) -> dict:
    """De velden van het bewerkformulier, zoals ze in een conceptversie worden bewaard."""
    from .inhoud import schoon

    herzien = cleaned_data.get("herzien_voor")
    omgeving = cleaned_data.get("omgeving")
    return {
        "titel": cleaned_data.get("titel") or "",
        "samenvatting": cleaned_data.get("samenvatting") or "",
        "inhoud": schoon(cleaned_data.get("inhoud") or ""),
        "soort": cleaned_data.get("soort") or "",
        "eigenaar": cleaned_data.get("eigenaar") or "",
        "omgeving": omgeving.pk if omgeving else None,
        "herzien_voor": herzien.isoformat() if herzien else "",
        "clusters": sorted(c.pk for c in cleaned_data.get("clusters") or []),
        "zaaktypen": sorted(z.pk for z in cleaned_data.get("zaaktypen") or []),
        "tags_tekst": cleaned_data.get("tags_tekst") or "",
    }


def concept_beginwaarden(concept) -> dict:
    """Wat het bewerkscherm invult als er een conceptversie is."""
    v = concept.velden or {}
    waarden = {k: v[k] for k in ("titel", "samenvatting", "inhoud", "soort", "eigenaar", "tags_tekst") if k in v}
    if v.get("omgeving"):
        waarden["omgeving"] = v["omgeving"]
    if "herzien_voor" in v:
        waarden["herzien_voor"] = v["herzien_voor"] or None
    for veld in ("clusters", "zaaktypen"):
        if veld in v:
            waarden[veld] = v[veld]
    return waarden


def concept_stand(artikel_id) -> str:
    """De stempel van de huidige conceptversie (vergrendeld), of '' als er geen is."""
    moment = (
        Conceptversie.objects.select_for_update()
        .filter(artikel_id=artikel_id)
        .values_list("bijgewerkt_op", flat=True)
        .first()
    )
    return moment.isoformat() if moment else ""


def concept_opslaan(artikel, gebruiker, velden, geladen: str) -> Conceptversie:
    """Bewaar de conceptversie van een gepubliceerd artikel.

    ``geladen`` is de stempel van de conceptversie toen het scherm werd geopend ('' als er toen geen
    was). Wijkt die af van wat er nu staat, dan heeft een collega intussen de conceptversie opgeslagen,
    gepubliceerd of weggegooid: ConceptConflict, zodat niemand ongemerkt andermans werk overschrijft.
    """
    nu = timezone.now()
    with transaction.atomic():
        if concept_stand(artikel.pk) != (geladen or ""):
            raise ConceptConflict
        concept = Conceptversie.objects.filter(artikel=artikel).first()
        if concept is None:
            concept = Conceptversie(
                artikel=artikel,
                basis_versie=artikel.versie or 0,
                basis_stempel=artikel.gewijzigd_op.isoformat() if artikel.gewijzigd_op else "",
                gestart_door=gebruiker,
                gestart_op=nu,
            )
        concept.velden = velden
        concept.bijgewerkt_door = gebruiker
        concept.bijgewerkt_op = nu
        concept.save()
    return concept


def concept_weggooien(artikel) -> bool:
    return Conceptversie.objects.filter(artikel=artikel).delete()[0] > 0


def concept_gepubliceerd(artikel, door) -> bool:
    """De conceptversie is gepubliceerd: haal hem weg en laat collega's die eraan werkten het weten.

    Wie een conceptversie publiceert die een collega begon of als laatste bijwerkte, krijgt in het
    scherm eerst een bevestiging; de collega krijgt daarna een e-mail, zodat hij niet verder zoekt naar
    werk dat al live staat (functionele review 11 november, punt 4.3).
    """
    concept = Conceptversie.objects.filter(artikel=artikel).select_related("gestart_door", "bijgewerkt_door").first()
    if concept is None:
        return False
    collegas = {u for u in (concept.gestart_door, concept.bijgewerkt_door) if u and u.pk != door.pk and u.email}
    concept.delete()
    if collegas and artikel.status == Status.GEPUBLICEERD:
        mail_na_commit(
            f"Conceptversie gepubliceerd: {artikel.titel}",
            f"{naam_van(door)} heeft de conceptversie van '{artikel.titel}' gepubliceerd, waar jij ook aan werkte. "
            "Medewerkers zien die tekst nu; de conceptversie is daarmee afgesloten.\n\n"
            f"{settings.KB_BASIS_URL}/beheer/kennisbank/artikel/{artikel.pk}/change/",
            [u.email for u in collegas],
        )
    return True


# --- Bakken: wie heeft een verbetervoorstel ---------------------------------------------
#
# Een nieuw voorstel ligt in de gezamenlijke bak van zijn omgeving (eigenaar leeg). Een redacteur
# pakt het op (naar zijn eigen bak), wijst het toe aan een collega, of legt het terug. Alles loopt
# via voorstel_naar_bak, zodat de status, de e-mail en het slot op één plek geregeld zijn.


class VoorstelFout(Exception):
    """Iets wat met een voorstel niet kan, met een uitleg in gewoon Nederlands."""


def voorstel_beheer_url(voorstel) -> str:
    return f"{settings.KB_BASIS_URL}/beheer/voorstel/{voorstel.pk}/"


def naam_van(gebruiker) -> str:
    if not gebruiker:
        return "Onbekend"
    return gebruiker.get_full_name() or gebruiker.get_username()


def redacteuren_van(omgeving_id):
    """Iedereen die een voorstel uit deze omgeving in zijn bak mag hebben: redacteuren en beheerders."""
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    return (
        get_user_model()
        .objects.filter(is_active=True)
        .filter(
            Q(is_superuser=True)
            | Q(groups__kennisbank_toegang__omgeving_id=omgeving_id, groups__kennisbank_toegang__rol=Rol.REDACTEUR)
        )
        .distinct()
        .order_by("first_name", "last_name", "username")
    )


def _nog_geen_bericht(voorstel) -> bool:
    """'Er is nog niet aan gewerkt': de indiener heeft nog geen bericht van de redactie gekregen."""
    return not voorstel.berichten.filter(van_redactie=True).exists()


BAK_VELDEN = ["eigenaar", "eigenaar_sinds", "eigenaar_gezien_op"]


def voorstel_naar_bak(voorstel, door, naar=None):
    """Leg een voorstel in de bak van `naar`, of met naar=None terug in de gezamenlijke bak.

    - Oppakken (naar == door) en toewijzen (naar is een collega) zetten een nieuw voorstel op
      'In behandeling'. Bij toewijzen krijgt de collega een e-mail.
    - Terugleggen zet het voorstel terug op 'Nieuw' zolang er nog geen bericht naar de indiener is
      gegaan; is dat wel gebeurd, dan blijft het 'In behandeling' (er ís al aan gewerkt).
    - Een afgehandeld voorstel blijft bij wie het afhandelde; dat is de geschiedenis van die bak.

    Geeft het bijgewerkte voorstel terug. Gooit VoorstelFout als het niet kan.
    """
    nu = timezone.now()
    with transaction.atomic():
        v = Verbetervoorstel.objects.select_for_update().select_related("artikel").get(pk=voorstel.pk)
        if not v.is_open:
            raise VoorstelFout("Dit voorstel is al afgehandeld en blijft bij wie het afhandelde.")
        if naar is None:
            if v.eigenaar_id is None:
                return v
            v.eigenaar = None
            v.eigenaar_sinds = None
            v.eigenaar_gezien_op = None
            if v.status == VoorstelStatus.IN_BEHANDELING and _nog_geen_bericht(v):
                v.status = VoorstelStatus.NIEUW
                v.behandeld_door = None
                v.behandeld_op = None
        else:
            if not redacteuren_van(v.artikel.omgeving_id).filter(pk=naar.pk).exists():
                raise VoorstelFout(f"{naam_van(naar)} is geen redacteur van de omgeving van dit artikel.")
            if v.eigenaar_id == naar.pk:
                return v
            v.eigenaar = naar
            v.eigenaar_sinds = nu
            v.eigenaar_gezien_op = nu if naar.pk == getattr(door, "pk", None) else None
            if v.status == VoorstelStatus.NIEUW:
                v.status = VoorstelStatus.IN_BEHANDELING
                v.behandeld_door = door
                v.behandeld_op = nu
        v.save(update_fields=[*BAK_VELDEN, "status", "behandeld_door", "behandeld_op"])
        if naar is not None and naar.pk != getattr(door, "pk", None):
            mail_na_commit(
                f"Verbetervoorstel in je bak: {v.artikel.titel}",
                f"{naam_van(door)} heeft een verbetervoorstel bij '{v.artikel.titel}' aan je toegewezen.\n\n"
                f"{v.tekst}\n\nBekijken: {voorstel_beheer_url(v)}",
                [naar.email],
            )
    return v


def voorstel_naar_clusterbak(voorstel, door, cluster) -> None:
    """Verplaats een open voorstel naar een andere werkbak: een cluster, of None = de algemene bak.

    Raakt de eigenaar niet: ligt het voorstel bij iemand, dan verandert alleen het label, en bij
    terugleggen komt het in de nieuwe bak terecht.
    """
    with transaction.atomic():
        v = Verbetervoorstel.objects.select_for_update().get(pk=voorstel.pk)
        if not v.is_open:
            raise VoorstelFout("Dit voorstel is al afgehandeld.")
        v.cluster = cluster
        v.save(update_fields=["cluster"])


def eigenaar_bij_statuswijziging(voorstel, door) -> None:
    """Wie de status van een voorstel wijzigt, wordt in twee gevallen eigenaar:

    - het voorstel lag in de gezamenlijke bak (en gaat naar In behandeling, Verwerkt of Afgewezen);
    - het voorstel wordt afgehandeld (Verwerkt of Afgewezen): wie afhandelt, is eigenaar, ook als het in
      de bak van een collega lag. Zo staat in elke bak alleen wat die persoon zelf afhandelde.

    Aangeroepen door het beheerscherm en de API vóór het opslaan, nadat de nieuwe status is gezet. Een
    statuswijziging terug naar Nieuw laat de eigenaar staan (besluit van 10 november).
    """
    if voorstel.status == VoorstelStatus.NIEUW or voorstel.eigenaar_id == getattr(door, "pk", None):
        return
    if voorstel.eigenaar_id is None or not voorstel.is_open:
        nu = timezone.now()
        voorstel.eigenaar = door
        voorstel.eigenaar_sinds = nu
        voorstel.eigenaar_gezien_op = nu


def bakken_rechtzetten(gebruiker=None, artikel=None) -> int:
    """Leg open voorstellen terug in de gezamenlijke bak als de eigenaar er geen redacteur meer van is.

    Dat gebeurt als iemand zijn redacteursrol kwijtraakt, of als een artikel naar een andere omgeving
    verhuist. Zonder dit ziet de eigenaar het voorstel nergens meer, en zien redacteuren van de nieuwe
    omgeving een naam van buiten hun omgeving. Aangeroepen bij elke rechtenwijziging van een gebruiker,
    bij het verplaatsen van een artikel, en als vangnet door de dagelijkse opschoonronde.
    Geeft het aantal teruggelegde voorstellen terug.
    """
    qs = Verbetervoorstel.objects.filter(
        eigenaar__isnull=False, status__in=[VoorstelStatus.NIEUW, VoorstelStatus.IN_BEHANDELING]
    ).select_related("artikel")
    if gebruiker is not None:
        qs = qs.filter(eigenaar=gebruiker)
    if artikel is not None:
        qs = qs.filter(artikel=artikel)
    bevoegd = {}
    teruggelegd = 0
    for v in qs:
        oid = v.artikel.omgeving_id
        if oid not in bevoegd:
            bevoegd[oid] = set(redacteuren_van(oid).values_list("pk", flat=True))
        if v.eigenaar_id not in bevoegd[oid]:
            try:
                voorstel_naar_bak(v, None, None)
            except VoorstelFout:
                continue
            teruggelegd += 1
    return teruggelegd


def voorstel_afhandelen(voorstel, door, status, tekst: str, *, dubbel_van=None):
    """Sluit een voorstel af met een afsluitend bericht aan de indiener (Verwerkt, Afgewezen, Vervallen).

    Afgehandeld is definitief (besluit van Alex): een afgesloten voorstel gaat niet meer open. Het
    bericht is verplicht als er een redacteur afhandelt; dat is wat de indiener als antwoord krijgt.
    Wie een voorstel uit de bak van een collega afhandelt, wordt eigenaar; die collega krijgt een
    e-mail, zodat hij niet verder werkt aan iets wat al af is.

    De aanroeper zet het voorstel op slot (select_for_update binnen een transactie).
    """
    if status not in AFGEHANDELD:
        raise VoorstelFout("Onbekende eindstand.")
    if not voorstel.is_open:
        raise VoorstelFout("Dit voorstel is al afgehandeld. Dat is definitief; een bericht kan nog wel.")
    tekst = (tekst or "").strip()
    if not tekst:
        raise VoorstelFout(
            "Schrijf de indiener waarom. Dat bericht krijgt hij als antwoord, per melding en per e-mail."
        )
    if dubbel_van is not None:
        if status != VoorstelStatus.AFGEWEZEN:
            raise VoorstelFout("Alleen afwijzen kan als dubbel voorstel.")
        if dubbel_van.pk == voorstel.pk or dubbel_van.artikel.omgeving_id != voorstel.artikel.omgeving_id:
            raise VoorstelFout("Kies een ander voorstel uit dezelfde omgeving.")
    vorige = voorstel.eigenaar
    nu = timezone.now()
    voorstel.status = status
    voorstel.behandeld_door = door
    voorstel.behandeld_op = nu
    voorstel.dubbel_van = dubbel_van
    if door is not None:
        eigenaar_bij_statuswijziging(voorstel, door)
    voorstel.save(update_fields=["status", "behandeld_door", "behandeld_op", "dubbel_van", *BAK_VELDEN])
    voorstelbericht_toevoegen(voorstel, door, tekst, van_redactie=True)
    if vorige and door is not None and vorige.pk != door.pk and vorige.email and vorige.is_active:
        mail_na_commit(
            f"Voorstel afgehandeld: {voorstel.artikel.titel}",
            f"{naam_van(door)} heeft het verbetervoorstel bij '{voorstel.artikel.titel}' uit jouw bak "
            f"afgehandeld ({voorstel.get_status_display().lower()}). Je hoeft er niets meer mee te doen.\n\n"
            f"{voorstel_beheer_url(voorstel)}",
            [vorige.email],
        )
    return voorstel


#: Het afsluitende bericht als een artikel wordt gearchiveerd (besluit e van Alex).
INGETROKKEN_BERICHT = (
    "Het artikel '{titel}' is ingetrokken. Daarom sluiten we je verbetervoorstel af. Bedankt voor het meedenken."
)


def voorstellen_vervallen(artikel) -> int:
    """Sluit de open voorstellen van een gearchiveerd artikel af als *Vervallen*, met een bericht."""
    n = 0
    with transaction.atomic():
        for v in (
            Verbetervoorstel.objects.select_for_update(of=("self",))
            .select_related("artikel", "eigenaar")
            .filter(artikel=artikel, status__in=OPEN)
        ):
            voorstel_afhandelen(v, None, VoorstelStatus.VERVALLEN, INGETROKKEN_BERICHT.format(titel=artikel.titel))
            n += 1
    return n


def notitie_toevoegen(voorstel, auteur, tekst: str):
    """Een interne notitie: alleen de redactie ziet hem. Een dubbelklik geeft geen tweede notitie."""
    tekst = (tekst or "").strip()[:4000]
    if not tekst:
        return None
    slot(f"voorstelnotitie:{voorstel.pk}")
    dubbel = voorstel.notities.filter(
        auteur=auteur, tekst=tekst, moment__gte=timezone.now() - datetime.timedelta(seconds=DUBBEL_VENSTER)
    ).first()
    return dubbel or VoorstelNotitie.objects.create(voorstel=voorstel, auteur=auteur, tekst=tekst)


def voorstel_gezien_door_eigenaar(voorstel, gebruiker) -> None:
    if voorstel.eigenaar_id and voorstel.eigenaar_id == getattr(gebruiker, "pk", None):
        Verbetervoorstel.objects.filter(pk=voorstel.pk).update(eigenaar_gezien_op=timezone.now())


# --- Steun (de like-knop) -------------------------------------------------------------


def steun_geven(voorstel, gebruiker) -> bool:
    """Steun een voorstel. Geeft True als er steun bij kwam, False als die er al was."""
    if not voorstel.is_open:
        raise VoorstelFout("Dit voorstel is al afgehandeld; steunen kan alleen bij een open voorstel.")
    if voorstel.ingediend_door_id == gebruiker.pk:
        raise VoorstelFout("Je eigen voorstel kun je niet steunen.")
    with transaction.atomic():
        slot(f"steun:{voorstel.pk}:{gebruiker.pk}")  # dubbelklik: één steun, geen fout
        _, nieuw = Steun.objects.get_or_create(voorstel=voorstel, gebruiker=gebruiker)
    return nieuw


def steun_intrekken(voorstel, gebruiker) -> None:
    """Steun intrekken kan alleen zolang het voorstel open is; daarna is het aantal geschiedenis."""
    if not voorstel.is_open:
        raise VoorstelFout("Dit voorstel is al afgehandeld; de steun blijft staan.")
    Steun.objects.filter(voorstel=voorstel, gebruiker=gebruiker).delete()


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


# --- Zacht slot bij bewerken --------------------------------------------------------------

#: Hoe lang een claim meegaat zonder verlenging. Het bewerkscherm verlengt elke 30 seconden;
#: valt het tabblad weg, dan vervalt de claim vanzelf en staat niemand voor een dicht artikel.
CLAIM_VERVALT_NA = 120


def _claimgrens():
    return timezone.now() - timezone.timedelta(seconds=CLAIM_VERVALT_NA)


def actieve_claims(artikel: Artikel, behalve=None):
    """De redacteuren die dit artikel nu open hebben, zonder de opgegeven gebruiker."""
    qs = BewerkClaim.objects.filter(artikel=artikel, laatst_gezien__gte=_claimgrens()).select_related("gebruiker")
    if behalve is not None and behalve.is_authenticated:
        qs = qs.exclude(gebruiker=behalve)
    return list(qs.order_by("begonnen_op"))


def claim_vernieuwen(artikel: Artikel, gebruiker) -> list[BewerkClaim]:
    """Leg vast dat deze gebruiker het artikel open heeft en geef terug wie er nog meer in zit."""
    nu = timezone.now()
    claim, nieuw = BewerkClaim.objects.get_or_create(
        artikel=artikel, gebruiker=gebruiker, defaults={"begonnen_op": nu, "laatst_gezien": nu}
    )
    if not nieuw:
        velden = {"laatst_gezien": nu}
        if claim.laatst_gezien < _claimgrens():
            velden["begonnen_op"] = nu  # vervallen claim: opnieuw begonnen
        BewerkClaim.objects.filter(pk=claim.pk).update(**velden)
    return actieve_claims(artikel, behalve=gebruiker)


def claim_opheffen(artikel: Artikel, gebruiker) -> None:
    BewerkClaim.objects.filter(artikel=artikel, gebruiker=gebruiker).delete()


def verlopen_claims_opruimen() -> int:
    aantal, _ = BewerkClaim.objects.filter(laatst_gezien__lt=_claimgrens()).delete()
    return aantal


# --- Kladversies ---------------------------------------------------------------------
#
# Onopgeslagen werk in het bewerkscherm. De browser houdt continu een kopie bij (ook zonder
# verbinding); de server krijgt de kladversie elke twee minuten en bij het sluiten van het tabblad.
# Na opslaan of weggooien blijft er een afgesloten rij staan (zie Kladversie): die vertelt een oude
# browserkopie op een andere laptop dat zijn werk al is afgehandeld.

#: De formuliervelden die in een kladversie worden bewaard. Publicatiekeuzes (status, toelichting,
#: kleine correctie) bewust niet: die horen bij het moment van opslaan, niet bij het schrijfwerk.
KLAD_TEKSTVELDEN = ("titel", "samenvatting", "inhoud", "soort", "omgeving", "eigenaar", "tags_tekst")
KLAD_LIJSTVELDEN = ("clusters", "zaaktypen")


def _klad_rijen(gebruiker, artikel):
    if artikel is None:
        return Kladversie.objects.filter(gebruiker=gebruiker, artikel__isnull=True)
    return Kladversie.objects.filter(gebruiker=gebruiker, artikel=artikel)


def klad_van(gebruiker, artikel):
    """De kladversie-rij van deze gebruiker voor dit artikel (of voor een nieuw artikel), open of afgesloten."""
    return _klad_rijen(gebruiker, artikel).first()


def _schone_kladvelden(velden) -> dict:
    """Alleen de bekende velden, alleen tekst of een lijst tekst. De rest valt weg."""
    if not isinstance(velden, dict):
        return {}
    uit = {}
    for naam in KLAD_TEKSTVELDEN:
        waarde = velden.get(naam)
        if isinstance(waarde, str | int):
            uit[naam] = str(waarde)
    for naam in KLAD_LIJSTVELDEN:
        waarde = velden.get(naam)
        if isinstance(waarde, list):
            uit[naam] = [str(w) for w in waarde if isinstance(w, str | int)][:500]
    return uit


class KladAfgesloten(Exception):
    """Het scherm dat deze kladversie stuurt, is al opgeslagen of weggegooid."""


def klad_opslaan(gebruiker, artikel, velden, basis_stempel="", *, redactie_omgevingen=(), geopend_op=None):
    """Bewaar (of heropen) de kladversie. Geeft de rij terug.

    ``geopend_op``: het moment (servertijd) waarop het bewerkscherm zijn kladversie ophaalde. Is de
    kladversie ná dat moment afgesloten, dan is het werk uit dat scherm al opgeslagen of weggegooid,
    en mag hij niet heropend worden: dan gooit deze functie KladAfgesloten. Zonder die controle zette
    het baken dat de browser bij het verlaten van de pagina stuurt, de kladversie direct na het opslaan
    weer open (review 10 november, bevinding 1).

    ``redactie_omgevingen``: waar deze gebruiker redacteur is. Bij een nieuw artikel wordt de gekozen
    omgeving alleen vastgelegd als hij daar redacteur is; anders zou een collega van een andere
    omgeving de kladversie te zien krijgen.
    """
    velden = _schone_kladvelden(velden)
    omgeving_id = None
    if artikel is None:
        try:
            gekozen = int(velden.get("omgeving") or 0)
        except ValueError:
            gekozen = 0
        if gekozen and (gebruiker.is_superuser or gekozen in set(redactie_omgevingen)):
            omgeving_id = gekozen
    nu = timezone.now()
    sleutel = f"klad:{gebruiker.pk}:{artikel.pk if artikel else 'nieuw'}"
    with transaction.atomic():
        slot(sleutel)  # twee tabbladen tegelijk mogen geen dubbele rij maken
        rij = klad_van(gebruiker, artikel)
        if rij is None:
            rij = Kladversie(gebruiker=gebruiker, artikel=artikel, aangemaakt_op=nu)
        elif rij.afgesloten_op is not None:
            if geopend_op is not None and rij.afgesloten_op >= geopend_op:
                raise KladAfgesloten
            rij.aangemaakt_op = nu  # een nieuwe kladversie na een afgesloten exemplaar
        rij.velden = velden
        rij.basis_stempel = (basis_stempel or "")[:64]
        rij.omgeving_id = omgeving_id
        rij.bijgewerkt_op = nu
        rij.afgesloten_op = None
        rij.save()
    return rij


def klad_afsluiten(gebruiker, artikel) -> None:
    """Na opslaan of weggooien. Laat altijd een afgesloten rij achter, ook als er nooit een
    kladversie op de server stond: de browser kan wel al een kopie hebben, en die moet weten dat het
    werk is afgehandeld."""
    nu = timezone.now()
    sleutel = f"klad:{gebruiker.pk}:{artikel.pk if artikel else 'nieuw'}"
    with transaction.atomic():
        slot(sleutel)
        rij = klad_van(gebruiker, artikel) or Kladversie(gebruiker=gebruiker, artikel=artikel, aangemaakt_op=nu)
        rij.velden = {}
        rij.omgeving_id = None
        rij.bijgewerkt_op = nu
        rij.afgesloten_op = nu
        rij.save()


def zichtbare_kladversies(gebruiker, r):
    """Open kladversies die deze gebruiker mag zien: zijn eigen, en die van collega's in een omgeving
    waar hij redacteur is (ook van nieuwe artikelen waarvoor al een omgeving is gekozen)."""
    from django.db.models import Q

    qs = Kladversie.objects.filter(afgesloten_op__isnull=True).select_related(
        "gebruiker", "artikel__omgeving", "omgeving"
    )  # artikel__omgeving: de beheerlijst toont de omgeving; anders één vraag per rij (review, bevinding 9)
    if gebruiker.is_superuser:
        return qs
    redactie = r.redactie_omgevingen
    return qs.filter(
        Q(gebruiker=gebruiker)
        | Q(artikel__omgeving_id__in=redactie)
        | Q(artikel__isnull=True, omgeving_id__in=redactie)
    )


def mag_klad_zien(gebruiker, r, klad) -> bool:
    return zichtbare_kladversies(gebruiker, r).filter(pk=klad.pk).exists()


def kladversies_opruimen() -> int:
    """Open en afgesloten kladversies ouder dan KB_KLADVERSIE_DAGEN."""
    grens = timezone.now() - datetime.timedelta(days=settings.KB_KLADVERSIE_DAGEN)
    return Kladversie.objects.filter(bijgewerkt_op__lt=grens).delete()[0]
