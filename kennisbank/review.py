"""Het reviewproces (stap C, ontwerp 11 november; bouwlijst `ronde3-reviewproces-bouwlijst.md`).

Een redacteur geeft een conceptversie *ter inzage* aan één of meer reviewteams. Zolang er een team
mee bezig is, staat de conceptversie op slot voor de redactie. Een reviewer pakt het stuk op, plaatst
opmerkingen en geeft het terug of geeft akkoord. Akkoord geldt voor precies die tekst: verandert de
conceptversie daarna, dan vervalt het. Publiceren kan altijd; de versiegeschiedenis vermeldt hoe het
met de review stond.

Alles wat de toestand verandert, staat hier, zodat de regels op één plek staan.
"""

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .diensten import _mail, laatste_stand, mail_na_commit, naam_van
from .models import Conceptversie, Inzage, InzageStatus, ReviewOpmerking, Reviewteam, Systeemstand


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
        rijen = [
            Inzage(
                artikel=artikel, team=t, ronde=ronde, concept_stempel=concept.stempel, gestart_door=door, gestart_op=nu
            )
            for t in teams
        ]
        Inzage.objects.bulk_create(rijen)
    return rijen


def terugroepen(artikel, door) -> int:
    """Haal de conceptversie terug bij alle teams die er nog mee bezig zijn."""
    with transaction.atomic():
        rijen = list(huidige(artikel.pk).select_for_update().filter(status=InzageStatus.TER_INZAGE))
        nu = timezone.now()
        for r in rijen:
            r.status = InzageStatus.TERUGGEROEPEN
            r.afgerond_op = nu
            r.save(update_fields=["status", "afgerond_op"])
    return len(rijen)


def samenvatting_bij_publiceren(artikel) -> str:
    """De regel voor de versiegeschiedenis: hoe stond de review toen er werd gepubliceerd?"""
    if not artikel.omgeving.reviewproces:
        return ""
    s = stand(artikel)
    if not s["rijen"]:
        return "Gepubliceerd zonder review."
    if s["label"]:
        teams = ", ".join(sorted(r.team.naam for r in s["rijen"]))
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


# --- Reviewers ---------------------------------------------------------------------------------


def _inzage_voor(gebruiker, pk, slot=False):
    qs = Inzage.objects.filter(pk=pk, team__in=teams_van(gebruiker), afgesloten=False)
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
