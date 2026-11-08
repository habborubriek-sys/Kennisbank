"""Statuspagina voor de functioneel beheerder: loopt alles nog?

Eén scherm met per onderdeel een stoplicht, wat er gemeten is en — als er iets niet goed staat —
wat eraan te doen is. Bedoeld voor het gesprek met IT en voor de dagelijkse controle daarna: de
dingen die stil kapot gaan (een cron die niet draait, een lege zoekindex, een omgeving waar niemand
bij kan) zijn hier in één oogopslag te zien.

Alleen lezen; deze module verandert niets.
"""

import sys

import django
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Count, Min
from django.utils import timezone
from django.utils.formats import date_format

from kennisbank import __version__

from . import diensten
from .models import (
    GUID_PATROON,
    Artikel,
    AssistentDagTotaal,
    FavorietenMail,
    GroepLabel,
    Omgeving,
    Sectie,
    Status,
    Verbetervoorstel,
    VoorstelStatus,
)

GOED, LET_OP, FOUT = "goed", "let_op", "fout"

#: Na hoeveel uur zonder opschoonronde we aannemen dat de geplande taak niet draait.
ONDERHOUD_GRENS_UREN = 48


def _regel(naam, stand, waarde, advies=""):
    return {"naam": naam, "stand": stand, "waarde": waarde, "advies": advies}


def _versie_en_modus():
    rijen = [
        _regel("Versie kennisbank", GOED, __version__),
        _regel("Python / Django", GOED, f"Python {sys.version.split()[0]} · Django {django.get_version()}"),
    ]
    if settings.DEBUG:
        # Op een testomgeving is DEBUG normaal; ziet het eruit als een echte installatie (inloggen via
        # Entra ID), dan is het een echt probleem en zeggen we dat ook zo.
        lijkt_productie = settings.KB_AUTH_MODUS != "lokaal"
        rijen.append(
            _regel(
                "Ontwikkelstand (DEBUG)",
                FOUT if lijkt_productie else LET_OP,
                "staat aan",
                "DEBUG hoort in productie uit te staan: met DEBUG aan toont een fout de interne "
                "gegevens van de server. Zet KB_DEBUG op 0. Op een test- of ontwikkelomgeving mag "
                "DEBUG aan staan.",
            )
        )
    else:
        rijen.append(_regel("Ontwikkelstand (DEBUG)", GOED, "staat uit"))

    modus = settings.KB_AUTH_MODUS
    if modus == "lokaal":
        rijen.append(
            _regel(
                "Inloggen",
                LET_OP,
                "lokale wachtwoorden (KB_AUTH_MODUS=lokaal)",
                "Dit is de teststand. In productie hoort KB_AUTH_MODUS op 'oidc' te staan, zodat "
                "medewerkers met hun RWS-account inloggen en rechten uit Entra ID komen.",
            )
        )
    else:
        rijen.append(_regel("Inloggen", GOED, "Entra ID (OIDC)"))

    if settings.KB_DEMO_MODUS:
        rijen.append(
            _regel(
                "Demo-inhoud",
                LET_OP,
                "staat aan",
                "KB_DEMO_MODUS vult de kennisbank met voorbeeldartikelen. Zet hem uit zodra de "
                "echte inhoud erin staat.",
            )
        )
    if not settings.KB_CONTACT:
        rijen.append(
            _regel(
                "Contactadres",
                LET_OP,
                "niet ingevuld",
                "Vul KB_CONTACT met het adres of teamkanaal waar medewerkers met vragen terechtkunnen; "
                "het staat in de zijbalk en op het scherm voor wie nog geen toegang heeft.",
            )
        )
    else:
        rijen.append(_regel("Contactadres", GOED, settings.KB_CONTACT))
    return rijen


def _database():
    rijen = []
    try:
        with connection.cursor() as c:
            c.execute("SELECT version()")
            versie = (c.fetchone() or [""])[0].split(",")[0]
        rijen.append(_regel("Database", GOED, versie))
    except Exception as e:  # noqa: BLE001 - we rapporteren wat er misgaat, we lossen het niet op
        return [
            _regel(
                "Database",
                FOUT,
                f"niet bereikbaar ({type(e).__name__})",
                "Zonder database werkt de kennisbank niet. Controleer KB_DATABASE_URL en of de "
                "databaseserver draait.",
            )
        ]
    try:
        executor = MigrationExecutor(connection)
        openstaand = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if openstaand:
            rijen.append(
                _regel(
                    "Databasestructuur",
                    FOUT,
                    f"{len(openstaand)} migratie(s) nog niet uitgevoerd",
                    "Voer 'python manage.py migrate' uit. Zolang dit openstaat, kan de kennisbank "
                    "fouten geven op velden die nog niet bestaan.",
                )
            )
        else:
            rijen.append(_regel("Databasestructuur", GOED, "bij"))
    except Exception as e:  # noqa: BLE001
        rijen.append(_regel("Databasestructuur", LET_OP, f"niet te bepalen ({type(e).__name__})"))
    return rijen


def _zoekindex():
    totaal = Sectie.objects.count()
    leeg = Sectie.objects.filter(zoekvector__isnull=True).count()
    if totaal == 0:
        return [_regel("Zoekindex", LET_OP, "nog geen secties", "Er staat nog geen inhoud in de kennisbank.")]
    if leeg:
        return [
            _regel(
                "Zoekindex",
                FOUT,
                f"{leeg} van {totaal} secties zonder zoekdocument",
                "Die secties zijn niet te vinden via de zoekbalk en de assistent. Open de artikelen "
                "en sla ze opnieuw op, of laat IT 'kennisbank_import' / een herbouw uitvoeren.",
            )
        ]
    return [_regel("Zoekindex", GOED, f"{totaal} secties geïndexeerd")]


def _mail():
    modus = settings.KB_FAVORIETEN_MAIL
    rijen = [_regel("E-mail bij favorieten", GOED, f"{modus} (KB_FAVORIETEN_MAIL)")]
    if modus == "uit":
        return rijen
    open_rijen = FavorietenMail.objects.filter(verzonden_op__isnull=True)
    aantal = open_rijen.count()
    oudste = open_rijen.aggregate(m=Min("aangemaakt_op"))["m"]
    if not aantal:
        rijen.append(_regel("Mailwachtrij", GOED, "leeg"))
        return rijen
    uren = (timezone.now() - oudste).total_seconds() / 3600 if oudste else 0
    if uren > ONDERHOUD_GRENS_UREN:
        rijen.append(
            _regel(
                "Mailwachtrij",
                FOUT,
                f"{aantal} regel(s), oudste {uren:.0f} uur oud",
                "De gebundelde e-mail wordt verstuurd door 'kennisbank_favorietenmail' (of door "
                "'kennisbank_opschonen'). Dat die blijft staan, betekent vrijwel altijd dat de "
                "geplande taak niet draait.",
            )
        )
    else:
        rijen.append(_regel("Mailwachtrij", GOED, f"{aantal} regel(s) wachtend, oudste {uren:.0f} uur"))
    return rijen


def _assistent():
    if settings.KB_AI_PROVIDER == "uit":
        return [
            _regel(
                "Assistent",
                LET_OP,
                "uitgeschakeld (KB_AI_PROVIDER=uit)",
                "Medewerkers kunnen geen vragen stellen. Dat is een geldige keuze; is het niet de "
                "bedoeling, dan moet IT de taalmodel-instellingen invullen.",
            )
        ]
    limiet = settings.KB_ASSISTENT_DAGLIMIET
    vandaag = AssistentDagTotaal.objects.filter(datum=timezone.localdate()).first()
    gebruikt = vandaag.modelaanroepen if vandaag else 0
    if limiet and gebruikt >= limiet:
        return [
            _regel(
                "Assistent",
                FOUT,
                f"daglimiet bereikt ({gebruikt} van {limiet})",
                "De assistent antwoordt vandaag niet meer. Verhoog KB_ASSISTENT_DAGLIMIET als dit "
                "structureel te laag blijkt.",
            )
        ]
    if limiet and gebruikt > limiet * 0.8:
        return [
            _regel(
                "Assistent",
                LET_OP,
                f"{gebruikt} van {limiet} aanroepen vandaag",
                "Bijna aan de daglimiet.",
            )
        ]
    rest = f"{gebruikt} van {limiet} aanroepen vandaag" if limiet else f"{gebruikt} aanroepen vandaag (geen limiet)"
    return [_regel("Assistent", GOED, f"{settings.KB_AI_PROVIDER} · {rest}")]


def _onderhoud():
    rijen = _onderhoudstaak(
        "opschonen",
        "Zet 'python manage.py kennisbank_opschonen' dagelijks in de planning. Die verstuurt "
        "de favorietenmail, ruimt oude statistieken en bewerkclaims op en anonimiseert "
        "afgehandelde verbetervoorstellen.",
        verplicht=True,
    )
    # De favorietenmail hoeft niet apart te zijn ingepland: 'opschonen' verstuurt hem ook. Loopt hij
    # wel apart, dan is het nuttig om te zien wanneer dat voor het laatst was.
    los = diensten.laatste_stand("favorietenmail")
    if los is not None:
        rijen += _onderhoudstaak("favorietenmail", "", verplicht=False)
    return rijen


def _onderhoudstaak(sleutel, advies, *, verplicht):
    naam = f"Geplande taak '{sleutel}'"
    stand = diensten.laatste_stand(sleutel)
    if stand is None:
        if not verplicht:
            return []
        return [_regel(naam, FOUT, "nog nooit gelopen", advies)]
    uren = (timezone.now() - stand.moment).total_seconds() / 3600
    wanneer = date_format(timezone.localtime(stand.moment), "j F Y, H:i")
    # De samenvatting die het commando zelf heeft achtergelaten; precies wat een beheerder wil zien.
    uitkomst = f" — {stand.melding}" if stand.melding else ""
    if verplicht and uren > ONDERHOUD_GRENS_UREN:
        return [
            _regel(
                naam,
                FOUT,
                f"laatst {wanneer} ({uren:.0f} uur geleden){uitkomst}",
                "Hoort dagelijks te lopen. Controleer de planning (cronjob of Kubernetes CronJob).",
            )
        ]
    return [_regel(naam, GOED, f"laatst {wanneer}{uitkomst}")]


def _toegang():
    rijen = []
    zonder = [o.naam for o in Omgeving.objects.annotate(n=Count("toegang")).filter(n=0)]
    if zonder:
        rijen.append(
            _regel(
                "Omgevingen zonder toegang",
                FOUT,
                ", ".join(zonder),
                "Hier kan niemand bij: er is geen groep aan gekoppeld. Koppel bij Omgevingen een "
                "groep uit Entra ID aan de omgeving, met de rol Lezer of Redacteur.",
            )
        )
    else:
        rijen.append(_regel("Omgevingen zonder toegang", GOED, "geen"))

    # Groepen waarvan de naam een object-id is en waar niemand een leesbare naam bij heeft gezet.
    gelabeld = set(GroepLabel.objects.values_list("groep_id", flat=True))
    from django.contrib.auth.models import Group

    naamloos = [
        g.name
        for g in Group.objects.exclude(pk__in=gelabeld).filter(kennisbank_toegang__isnull=False).distinct()
        if GUID_PATROON.match(g.name)
    ]
    if naamloos:
        rijen.append(
            _regel(
                "Groepen zonder leesbare naam",
                LET_OP,
                f"{len(naamloos)} groep(en)",
                "Deze groepen heten in Entra ID een object-id (een GUID), dus in het beheer is niet "
                "te zien welke groep het is. Vul bij Groepsnamen in hoe ze heten.",
            )
        )
    return rijen


def _inhoud():
    per_status = dict(Artikel.objects.values_list("status").annotate(n=Count("id")))
    te_herzien = diensten.te_herzien().count()
    open_voorstellen = Verbetervoorstel.objects.filter(
        status__in=[VoorstelStatus.NIEUW, VoorstelStatus.IN_BEHANDELING]
    ).count()
    rijen = [
        _regel(
            "Artikelen",
            GOED,
            f"{per_status.get(Status.GEPUBLICEERD, 0)} gepubliceerd · "
            f"{per_status.get(Status.CONCEPT, 0)} concept · "
            f"{per_status.get(Status.GEARCHIVEERD, 0)} gearchiveerd",
        ),
        _regel("Omgevingen", GOED, str(Omgeving.objects.count())),
    ]
    if te_herzien:
        rijen.append(
            _regel(
                "Opnieuw nakijken",
                LET_OP,
                f"{te_herzien} artikel(en) over de datum",
                "Filter in de artikelenlijst op 'Datum verstreken' en laat de redacteuren ze nakijken.",
            )
        )
    else:
        rijen.append(_regel("Opnieuw nakijken", GOED, "geen achterstand"))
    if open_voorstellen:
        rijen.append(_regel("Openstaande verbetervoorstellen", LET_OP, str(open_voorstellen)))
    else:
        rijen.append(_regel("Openstaande verbetervoorstellen", GOED, "geen"))
    return rijen


ONDERDELEN = [
    ("Versie en instellingen", _versie_en_modus),
    ("Database", _database),
    ("Zoeken", _zoekindex),
    ("E-mail", _mail),
    ("Assistent", _assistent),
    ("Onderhoud", _onderhoud),
    ("Toegang", _toegang),
    ("Inhoud", _inhoud),
]


def overzicht() -> dict:
    """Alle controles, gegroepeerd per onderdeel, plus de zwaarste stand die eruit komt."""
    groepen = []
    standen = []
    for titel, functie in ONDERDELEN:
        try:
            rijen = functie()
        except Exception as e:  # noqa: BLE001 - één kapotte controle mag de pagina niet slopen
            rijen = [_regel(titel, LET_OP, f"controle mislukt ({type(e).__name__})")]
        groepen.append({"titel": titel, "rijen": rijen})
        standen += [r["stand"] for r in rijen]
    totaal = FOUT if FOUT in standen else (LET_OP if LET_OP in standen else GOED)
    return {"groepen": groepen, "totaal": totaal, "gemeten_op": timezone.now()}
