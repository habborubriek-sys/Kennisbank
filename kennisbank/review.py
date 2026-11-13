"""Het reviewproces (stap C, ontwerp 11 november; bouwlijst `ronde3-reviewproces-bouwlijst.md`).

Een redacteur geeft een conceptversie *ter inzage* aan één of meer reviewteams. Zolang er een team
mee bezig is, staat de conceptversie op slot voor de redactie. Een reviewer pakt het stuk op, plaatst
opmerkingen en geeft het terug of geeft akkoord. Akkoord geldt voor precies die tekst: verandert de
conceptversie daarna, dan vervalt het. Publiceren kan als niets meer ter inzage ligt (besluit 12 november);
de versiegeschiedenis vermeldt hoe het
met de review stond.

Alles wat de toestand verandert, staat hier, zodat de regels op één plek staan.
"""

from django.conf import settings
from django.db import transaction
from django.db.models import F, Max
from django.utils import timezone

from .diensten import _mail, laatste_stand, mail_na_commit, naam_van
from .models import OPEN as OPEN_VOORSTEL
from .models import (
    Conceptversie,
    Inzage,
    InzageStatus,
    ReviewOpmerking,
    Reviewteam,
    Systeemstand,
    Verbetervoorstel,
)


class ReviewFout(Exception):
    """Iets wat in het reviewproces niet kan, met een uitleg in gewoon Nederlands."""


# --- Wie, wat --------------------------------------------------------------------------------


def teams_van(gebruiker):
    """De reviewteams waar deze gebruiker in zit (via de groep uit de identity provider)."""
    if not gebruiker or not gebruiker.is_authenticated:
        return Reviewteam.objects.none()
    return Reviewteam.objects.filter(groep__user=gebruiker).distinct()


def is_reviewer(gebruiker) -> bool:
    return teams_van(gebruiker).exists()


def gebruikt_review(artikel) -> bool:
    return bool(artikel.omgeving.reviewproces) and artikel.omgeving.reviewteams.exists()


def huidige(artikel_id):
    """De inzages die nog meetellen: van de huidige conceptversie, niet afgesloten."""
    return Inzage.objects.filter(artikel_id=artikel_id, afgesloten=False)


def op_slot(artikel_id) -> bool:
    """Ligt de conceptversie nu bij een reviewteam? Dan kan de redactie hem niet wijzigen."""
    return huidige(artikel_id).filter(status=InzageStatus.TER_INZAGE).exists()


def voorgevulde_teams(artikel):
    """De teams van de clusters van het artikel (aan te passen bij Ter inzage)."""
    return Reviewteam.objects.filter(omgeving=artikel.omgeving, clusters__in=artikel.clusters.all()).distinct()


def _datum(moment) -> str:
    d = timezone.localtime(moment)
    return f"{d.day}-{d.month}-{d.year}"


def _concept_stempel(artikel_id) -> str:
    concept = Conceptversie.objects.filter(artikel_id=artikel_id).values_list("bijgewerkt_op", flat=True).first()
    return concept.isoformat() if concept else ""


def stand(artikel):
    """Hoe de review er nu voor staat, voor het beheer.

    Geeft {"rijen": [...], "op_slot": bool, "label": str | None, "ronde": int} terug. Alleen de laatste
    ronde telt; eerdere rondes (met hun opmerkingen) staan in "eerder".
    """
    rijen = list(
        huidige(artikel.pk).select_related("team", "reviewer", "gestart_door").prefetch_related("opmerkingen__auteur")
    )
    if not rijen:
        return {"rijen": [], "eerder": [], "op_slot": False, "label": None, "ronde": 0}
    ronde = max(r.ronde for r in rijen)
    laatste = [r for r in rijen if r.ronde == ronde]
    eerder = [r for r in rijen if r.ronde < ronde]
    stempel = _concept_stempel(artikel.pk)
    akkoord = [r for r in laatste if r.status == InzageStatus.AKKOORD and r.akkoord_stempel == stempel]
    label = None
    if laatste and len(akkoord) == len(laatste):
        teams = ", ".join(sorted(r.team.naam for r in akkoord))
        datum = max(r.afgerond_op for r in akkoord)
        label = f"Versie {(artikel.versie or 0) + 1} akkoord bevonden door {teams}, {_datum(datum)}"
    for r in laatste:
        r.vervallen = r.status == InzageStatus.AKKOORD and r.akkoord_stempel != stempel
    return {
        "rijen": laatste,
        "eerder": eerder,
        "op_slot": any(r.status == InzageStatus.TER_INZAGE for r in laatste),
        "label": label,
        "ronde": ronde,
    }


def akkoord_voorstellen(artikel):
    """De voorstellen die meegenomen waren toen de versie met akkoord ter inzage ging (ronde A, M7).

    None als er nu geen geldig akkoord is. Een voorstel dat nu meegenomen is maar hier niet in staat, is
    ná het akkoord meegenomen: de reviewer heeft het niet gezien. Daar waarschuwt het bewerkscherm voor.
    """
    st = stand(artikel)
    if not st["label"]:
        return None
    ids = set()
    for r in st["rijen"]:
        ids.update(r.voorstellen or [])
    return ids


# --- Redactie ----------------------------------------------------------------------------------


def ter_inzage_geven(artikel, door, teams, geladen_stempel: str):
    """Geef de huidige conceptversie ter inzage aan deze teams (een nieuwe ronde)."""
    teams = list(teams)
    with transaction.atomic():
        concept = Conceptversie.objects.select_for_update().filter(artikel=artikel).first()
        if concept is None:
            raise ReviewFout("Sla je wijzigingen eerst op als conceptversie; die gaat ter inzage.")
        if not artikel.omgeving.reviewproces:
            raise ReviewFout("Het reviewproces staat voor deze omgeving niet aan.")
        if (geladen_stempel or "") != concept.stempel:
            raise ReviewFout(
                "De conceptversie is gewijzigd sinds je dit scherm opende. Ververs de pagina en kijk wat er nu staat."
            )
        if op_slot(artikel.pk):
            raise ReviewFout("De conceptversie ligt al ter inzage.")
        if not teams:
            raise ReviewFout("Kies minstens één reviewteam.")
        if any(t.omgeving_id != artikel.omgeving_id for t in teams):
            raise ReviewFout("Kies een reviewteam van de omgeving van dit artikel.")
        ronde = (huidige(artikel.pk).aggregate(m=Max("ronde"))["m"] or 0) + 1
        nu = timezone.now()
        meegenomen = sorted(
            Verbetervoorstel.objects.filter(
                artikel=artikel, in_conceptversie=True, status__in=OPEN_VOORSTEL
            ).values_list("pk", flat=True)
        )
        rijen = [
            Inzage(
                artikel=artikel,
                team=t,
                ronde=ronde,
                concept_stempel=concept.stempel,
                gestart_door=door,
                gestart_op=nu,
                voorstellen=meegenomen,
            )
            for t in teams
        ]
        Inzage.objects.bulk_create(rijen)
    return rijen


def terugroepen(artikel, door, reden: str = "") -> int:
    """Haal de conceptversie terug bij alle teams die er nog mee bezig zijn.

    Wat een reviewer al opmerkte, blijft bewaard; de redacteur ziet het als voorlopig. Een reviewer die
    het stuk had opgepakt, krijgt een e-mail, zodat hij niet doorwerkt aan iets wat weg is.
    """
    with transaction.atomic():
        rijen = list(
            huidige(artikel.pk)
            .select_for_update(of=("self",))
            .select_related("reviewer", "team")
            .filter(status=InzageStatus.TER_INZAGE)
        )
        nu = timezone.now()
        for r in rijen:
            r.status = InzageStatus.TERUGGEROEPEN
            r.afgerond_op = nu
            r.save(update_fields=["status", "afgerond_op"])
            if r.reviewer and r.reviewer.email and r.reviewer.is_active:
                n = r.opmerkingen.count()
                mail_na_commit(
                    f"Teruggeroepen: {artikel.titel}",
                    (
                        reden
                        or f"{naam_van(door)} heeft de conceptversie van '{artikel.titel}' teruggeroepen uit de review "
                        f"van {r.team.naam}."
                    )
                    + " Je hoeft er nu niets meer mee te doen."
                    + (
                        f" Je {n} opmerking{'' if n == 1 else 'en'} tot nu toe {'is' if n == 1 else 'zijn'} bewaard en "
                        "zichtbaar voor de redacteur, als voorlopig."
                        if n
                        else ""
                    )
                    + f"\n\n{settings.KB_BASIS_URL}/review/",
                    [r.reviewer.email],
                )
    return len(rijen)


def balk_stand(stand_) -> dict:
    """Eén korte regel voor de balk van het bewerkscherm (1.22.0): hoe staat de review ervoor?"""
    rijen = stand_["rijen"]
    if not rijen:
        return {"soort": "niet", "tekst": "Review: nog niet ter inzage"}
    if stand_["op_slot"]:
        bezig = [r for r in rijen if r.status == InzageStatus.TER_INZAGE]
        teams = ", ".join(r.team.naam for r in bezig)
        bij = [naam_van(r.reviewer) for r in bezig if r.reviewer_id]
        return {
            "soort": "inzage",
            "tekst": f"Ter inzage bij {teams}" + (f" · ligt bij {', '.join(bij)}" if bij else ""),
        }
    if stand_["label"]:
        return {"soort": "akkoord", "tekst": "Akkoord: " + ", ".join(sorted(r.team.naam for r in rijen))}
    terug = [r for r in rijen if r.status == InzageStatus.TERUGGEGEVEN]
    if terug:
        n = sum(len(r.opmerkingen.all()) for r in terug)
        teams = ", ".join(r.team.naam for r in terug)
        return {"soort": "terug", "tekst": f"Teruggegeven door {teams} · {n} opmerking{'' if n == 1 else 'en'}"}
    if any(getattr(r, "vervallen", False) for r in rijen):
        return {"soort": "niet", "tekst": "Akkoord vervallen: tekst gewijzigd"}
    return {"soort": "niet", "tekst": "Teruggeroepen"}


def terugroep_vraag(stand_) -> str:
    """De bevestigingsvraag bij Terugroepen als een team er al mee bezig is ('' = niet nodig)."""
    bezig = []
    for r in stand_["rijen"]:
        if r.status != InzageStatus.TER_INZAGE:
            continue
        n = len(r.opmerkingen.all())
        if r.reviewer_id or n:
            bezig.append(f"{r.team.naam} ({n} opmerking{'' if n == 1 else 'en'})")
    if not bezig:
        return ""
    return f"{' en '.join(bezig)} {'is' if len(bezig) == 1 else 'zijn'} hier al mee bezig. Toch terugroepen?"


def samenvatting_bij_publiceren(artikel, gewijzigd_na_concept: bool = False) -> str:
    """De regel voor de versiegeschiedenis: hoe stond de review toen er werd gepubliceerd?

    `gewijzigd_na_concept`: de tekst die live gaat, wijkt af van de opgeslagen conceptversie (rechtstreeks
    gepubliceerd vanaf het scherm). Een akkoord geldt dan niet voor deze tekst (review 1.20.1, bevinding 1).
    """
    if not artikel.omgeving.reviewproces:
        return ""
    s = stand(artikel)
    if not s["rijen"]:
        return "Gepubliceerd zonder review."
    if s["label"]:
        teams = ", ".join(sorted(r.team.naam for r in s["rijen"]))
        if gewijzigd_na_concept:
            return f"Gepubliceerd met wijzigingen na het akkoord van {teams}."
        return f"Akkoord van {teams}."
    zonder = ", ".join(
        sorted(
            r.team.naam
            for r in s["rijen"]
            if not (r.status == InzageStatus.AKKOORD and not getattr(r, "vervallen", False))
        )
    )
    return f"Gepubliceerd zonder akkoord van {zonder}."


def afsluiten(artikel) -> int:
    """De conceptversie is gepubliceerd of weggegooid: de inzages tellen niet meer mee."""
    return huidige(artikel.pk).update(afgesloten=True)


def stoppen(artikel, reden: str) -> int:
    """De review van dit artikel houdt op (gearchiveerd of naar een andere omgeving verhuisd).

    Review 1.20.1, bevinding 2 en 6: een reviewer die ermee bezig was, krijgt een e-mail met de reden, en
    alle inzages tellen daarna niet meer mee. De conceptversie zelf blijft bewaard.
    """
    with transaction.atomic():
        bezig = list(
            huidige(artikel.pk)
            .select_for_update(of=("self",))
            .select_related("reviewer", "team")
            .filter(status=InzageStatus.TER_INZAGE, reviewer__isnull=False)
        )
        for r in bezig:
            if r.reviewer.email and r.reviewer.is_active:
                mail_na_commit(
                    f"Review gestopt: {artikel.titel}",
                    f"De review van '{artikel.titel}' door {r.team.naam} is gestopt: {reden} "
                    "Je hoeft er niets meer mee te doen.",
                    [r.reviewer.email],
                )
        return afsluiten(artikel)


def reviewproces_uitgezet(omgeving, door) -> int:
    """Een beheerder zette het reviewproces uit: alles wat ter inzage ligt, gaat terug (bevinding 3).

    Anders bleef de conceptversie op de server op slot, terwijl het scherm hem weer bewerkbaar toonde,
    en publiceerde *Publiceren* stilletjes de oude opgeslagen tekst.
    """
    from .models import Artikel

    n = 0
    for artikel in Artikel.objects.filter(
        omgeving=omgeving, inzages__afgesloten=False, inzages__status=InzageStatus.TER_INZAGE
    ).distinct():
        n += terugroepen(
            artikel,
            door,
            reden=f"Het reviewproces voor {omgeving.naam} is uitgezet, daarom is de conceptversie van "
            f"'{artikel.titel}' teruggeroepen.",
        )
    return n


# --- Reviewers ---------------------------------------------------------------------------------


def _inzage_voor(gebruiker, pk, slot=False):
    # Alleen een team van de omgeving waar het artikel nu staat (bevinding 2: verhuisd artikel).
    qs = Inzage.objects.filter(
        pk=pk, team__in=teams_van(gebruiker), afgesloten=False, team__omgeving_id=F("artikel__omgeving_id")
    )
    if slot:
        qs = qs.select_for_update(of=("self",))
    return qs.select_related("artikel", "artikel__omgeving", "team", "reviewer", "gestart_door").first()


def _moet_open(inzage):
    if inzage.status != InzageStatus.TER_INZAGE:
        raise ReviewFout(f"Dit stuk is al {inzage.get_status_display().lower()}; er kan niets meer aan worden gedaan.")


def oppakken(inzage, reviewer):
    _moet_open(inzage)
    inzage.reviewer = reviewer
    inzage.opgepakt_op = timezone.now()
    inzage.save(update_fields=["reviewer", "opgepakt_op"])


def opmerking_toevoegen(inzage, auteur, tekst: str, citaat: str = ""):
    """Een opmerking, bij een stuk tekst (citaat, stap D) of algemeen (zonder citaat)."""
    _moet_open(inzage)
    tekst = (tekst or "").strip()[:4000]
    if not tekst:
        raise ReviewFout("Schrijf eerst je opmerking.")
    if inzage.reviewer_id is None:
        oppakken(inzage, auteur)
    citaat = " ".join((citaat or "").split())[:1000]
    return ReviewOpmerking.objects.create(inzage=inzage, auteur=auteur, tekst=tekst, citaat=citaat)


def _eigen_opmerking(inzage, gebruiker, opmerking_id):
    """1.30.0 (M16, besluit Alex): alleen de schrijver, en alleen zolang het stuk in deze ronde ter inzage ligt."""
    _moet_open(inzage)
    try:
        opm = inzage.opmerkingen.select_for_update().get(pk=int(opmerking_id))
    except (ValueError, TypeError, ReviewOpmerking.DoesNotExist):
        raise ReviewFout("Deze opmerking bestaat niet meer.") from None
    if opm.auteur_id != gebruiker.pk:
        raise ReviewFout("Je kunt alleen je eigen opmerkingen aanpassen.")
    return opm


def opmerking_wijzigen(inzage, gebruiker, opmerking_id, tekst: str):
    opm = _eigen_opmerking(inzage, gebruiker, opmerking_id)
    tekst = (tekst or "").strip()[:4000]
    if not tekst:
        raise ReviewFout("Een opmerking kan niet leeg zijn. Wil je hem weg? Kies dan Weghalen.")
    if tekst != opm.tekst:
        opm.tekst = tekst
        opm.bewerkt_op = timezone.now()
        opm.save(update_fields=["tekst", "bewerkt_op"])
    return opm


def opmerking_weghalen(inzage, gebruiker, opmerking_id):
    _eigen_opmerking(inzage, gebruiker, opmerking_id).delete()


def _afronden(inzage, door, status, tekst, citaat=""):
    _moet_open(inzage)
    if (tekst or "").strip():
        opmerking_toevoegen(inzage, door, tekst, citaat)
    if status == InzageStatus.TERUGGEGEVEN and not inzage.opmerkingen.exists():
        raise ReviewFout("Schrijf bij teruggeven wat er anders moet; dat leest de redacteur.")
    inzage.status = status
    inzage.afgerond_op = timezone.now()
    if inzage.reviewer_id is None:
        inzage.reviewer = door
        inzage.opgepakt_op = inzage.afgerond_op
    if status == InzageStatus.AKKOORD:
        inzage.akkoord_stempel = _concept_stempel(inzage.artikel_id)
    inzage.save(update_fields=["status", "afgerond_op", "reviewer", "opgepakt_op", "akkoord_stempel"])
    ontvanger = inzage.gestart_door
    if ontvanger and ontvanger.email and ontvanger.is_active:
        wat = "akkoord bevonden" if status == InzageStatus.AKKOORD else "teruggegeven met opmerkingen"
        mail_na_commit(
            f"Review: {inzage.artikel.titel} — {wat}",
            f"{inzage.team.naam} ({naam_van(door)}) heeft de conceptversie van '{inzage.artikel.titel}' {wat}.\n\n"
            f"{settings.KB_BASIS_URL}/beheer/kennisbank/artikel/{inzage.artikel_id}/change/",
            [ontvanger.email],
        )


def teruggeven(inzage, door, tekst: str = "", citaat: str = ""):
    _afronden(inzage, door, InzageStatus.TERUGGEGEVEN, tekst, citaat)


def akkoord_geven(inzage, door, tekst: str = "", citaat: str = ""):
    _afronden(inzage, door, InzageStatus.AKKOORD, tekst, citaat)


# --- Dagelijkse samenvatting voor reviewers (besluit c) -----------------------------------------


def verstuur_reviewmail(nu=None) -> int:
    """Eén e-mail per reviewer met wat er sinds de vorige keer ter inzage kwam bij zijn teams."""
    from django.contrib.auth import get_user_model

    nu = nu or timezone.now()
    vorige = laatste_stand("reviewmail")
    sinds = vorige.moment if vorige else nu - timezone.timedelta(days=1)
    nieuw = list(
        Inzage.objects.filter(
            gestart_op__gt=sinds, gestart_op__lte=nu, status=InzageStatus.TER_INZAGE, afgesloten=False
        )
        .select_related("artikel", "team")
        .order_by("gestart_op")
    )
    per_team = {}
    for i in nieuw:
        per_team.setdefault(i.team_id, []).append(i)
    verstuurd = 0
    if per_team:
        ontvangers = {}
        for _pk, email, team_id in (
            get_user_model()
            .objects.filter(is_active=True, groups__kennisbank_reviewteams__in=list(per_team))
            .exclude(email="")
            .values_list("pk", "email", "groups__kennisbank_reviewteams")
        ):
            ontvangers.setdefault(email, set()).add(team_id)
        for email, team_ids in ontvangers.items():
            regels = [f"- {i.artikel.titel} ({i.team.naam})" for tid in sorted(team_ids) for i in per_team.get(tid, [])]
            if not regels:
                continue
            tekst = (
                f"Er {'ligt' if len(regels) == 1 else 'liggen'} {len(regels)} nieuwe conceptversie"
                f"{'' if len(regels) == 1 else 's'} ter inzage bij je team:\n\n"
                + "\n".join(regels)
                + f"\n\nLezen en reageren: {settings.KB_BASIS_URL}/review/"
            )
            if _mail(f"Kennisbank: {len(regels)} stuk(ken) ter inzage", tekst, [email]):
                verstuurd += 1
    Systeemstand.objects.update_or_create(
        sleutel="reviewmail",
        defaults={"moment": nu, "melding": f"{len(nieuw)} nieuw ter inzage, {verstuurd} mail(s) verstuurd"},
    )
    return verstuurd
