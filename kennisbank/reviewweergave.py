"""De leesweergave voor reviewers: /review/ (stap C, reviewpunt 13).

Bewust niet het beheer: een reviewer leest, plaatst opmerkingen en geeft terug of akkoord. Hij bewerkt
niets en publiceert niets. Wie in geen reviewteam zit, ziet hier alleen een uitleg.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from . import review
from .diensten import naam_van
from .inhoud import schoon
from .models import Conceptversie, Inzage, InzageStatus
from .verschil import verschil_html, woordverschil


def _basis(request):
    from django.conf import settings

    return {"app_naam": settings.KB_APP_NAAM, "naam": naam_van(request.user)}


@login_required
def lijst(request):
    teams = list(review.teams_van(request.user).select_related("omgeving"))
    open_ = list(
        Inzage.objects.filter(team__in=teams, afgesloten=False, status=InzageStatus.TER_INZAGE)
        .select_related("artikel", "team", "reviewer", "gestart_door")
        .order_by("gestart_op")
    )
    afgerond = list(
        Inzage.objects.filter(team__in=teams)
        .exclude(status=InzageStatus.TER_INZAGE)
        .select_related("artikel", "team", "reviewer")
        .order_by("-afgerond_op")[:15]
    )
    nu = timezone.now()
    rijen = [
        {
            "i": i,
            "url": reverse("review-stuk", args=[i.pk]),
            "bij": naam_van(i.reviewer) if i.reviewer_id else None,
            "van_mij": i.reviewer_id == request.user.pk,
            "door": naam_van(i.gestart_door) if i.gestart_door_id else "procesmanagement",
            "dagen": (nu - i.gestart_op).days,
        }
        for i in open_
    ]
    balk = {
        "totaal": len(rijen),
        "bij_mij": sum(1 for r in rijen if r["van_mij"]),
        "niet_opgepakt": sum(1 for r in rijen if not r["bij"]),
        "oudste": open_[0].gestart_op if open_ else None,
    }
    return render(
        request,
        "kennisbank/review_lijst.html",
        {
            **_basis(request),
            "teams": teams,
            "rijen": rijen,
            "balk": balk,
            "afgerond": [
                {
                    "i": i,
                    "url": reverse("review-stuk", args=[i.pk]),
                    "bij": naam_van(i.reviewer) if i.reviewer_id else "",
                }
                for i in afgerond
                if not i.afgesloten
            ],
        },
    )


@login_required
def stuk(request, pk):
    if request.method == "POST":
        return _actie(request, pk)
    inzage = review._inzage_voor(request.user, pk)
    if inzage is None:
        raise Http404
    concept = Conceptversie.objects.filter(artikel=inzage.artikel).first()
    if concept is None:
        raise Http404
    artikel = inzage.artikel
    v = concept.velden or {}
    verschil, aantal = verschil_html(artikel.inhoud, v.get("inhoud", ""))
    return render(
        request,
        "kennisbank/review_stuk.html",
        {
            **_basis(request),
            "i": inzage,
            "artikel": artikel,
            "titel_verschil": mark_safe(woordverschil(artikel.titel, v.get("titel", artikel.titel))),  # noqa: S308
            "samenvatting_verschil": mark_safe(  # noqa: S308 - woordverschil escapet alles
                woordverschil(artikel.samenvatting, v.get("samenvatting", artikel.samenvatting))
            ),
            "verschil": verschil,
            "aantal_gewijzigd": aantal,
            "nieuwe_tekst": schoon(v.get("inhoud", "")),
            "opmerkingen": [
                {"naam": naam_van(o.auteur) if o.auteur_id else "Reviewer", "moment": o.moment, "tekst": o.tekst}
                for o in inzage.opmerkingen.select_related("auteur")
            ],
            "eerder": [
                {
                    "team": e.team.naam,
                    "ronde": e.ronde,
                    "status": e.get_status_display().lower(),
                    "opmerkingen": list(e.opmerkingen.all()),
                }
                for e in Inzage.objects.filter(
                    artikel=artikel, afgesloten=False, ronde__lt=inzage.ronde, team=inzage.team
                )
                .select_related("team")
                .prefetch_related("opmerkingen")
            ],
            "bij": naam_van(inzage.reviewer) if inzage.reviewer_id else None,
            "van_mij": inzage.reviewer_id == request.user.pk,
            "open": inzage.status == InzageStatus.TER_INZAGE,
            "door": naam_van(inzage.gestart_door) if inzage.gestart_door_id else "procesmanagement",
            "basis_versie": artikel.versie,
        },
    )


def _actie(request, pk):
    actie = request.POST.get("actie")
    tekst = request.POST.get("tekst", "")
    with transaction.atomic():
        inzage = review._inzage_voor(request.user, pk, slot=True)
        if inzage is None:
            raise Http404
        try:
            if actie == "oppakken":
                review.oppakken(inzage, request.user)
                messages.success(request, f"Je hebt dit opgepakt. Het staat nu bij jou in {inzage.team.naam}.")
            elif actie == "opmerking":
                review.opmerking_toevoegen(inzage, request.user, tekst)
                messages.success(
                    request, "Opmerking toegevoegd. De redacteur ziet hem als je teruggeeft of akkoord geeft."
                )
            elif actie == "teruggeven":
                review.teruggeven(inzage, request.user, tekst)
                messages.success(request, "Teruggegeven aan de redacteur, met je opmerkingen.")
                return redirect("review-lijst")
            elif actie == "akkoord":
                review.akkoord_geven(inzage, request.user, tekst)
                messages.success(request, "Akkoord gegeven. De redacteur kan publiceren.")
                return redirect("review-lijst")
            else:
                raise Http404
        except review.ReviewFout as e:
            messages.warning(request, str(e))
    return redirect("review-stuk", pk=pk)
