"""Verbetervoorstellen in het bewerkscherm: de lade links (1.26.0, ontwerp `ontwerp-voorstellen-in-editor.md`).

Een redacteur behandelt voorstellen waar hij de tekst aanpast. De lade toont de open voorstellen bij het
artikel; daar neem je ze mee in de versie waar je aan werkt, stuur je de indiener een bericht, schrijf
je een interne notitie, of wijs je een voorstel af.

Twee soorten handelingen:

- **Meenemen** hoort bij het artikel en telt pas als je opslaat (besluit 1 van Alex). Het formulier stuurt
  mee welke voorstellen in de lade stonden (`kb_lade`) en welke daarvan zijn aangevinkt (`kb_meenemen`);
  `meenemen_opslaan` verwerkt dat na een geslaagde opslag. Wie meeneemt, wordt eigenaar; de vorige
  eigenaar krijgt een e-mail (besluit 3). Bij een spoedcorrectie geldt het voor de versie die dan wordt
  gepubliceerd (besluit 5).
- **Bericht, notitie, afwijzen, dubbel** staan los van het artikel en gaan meteen (`lade_actie`, JSON).
  Een voorstel dat is meegenomen in een versie die ter inzage ligt, kun je niet afwijzen (besluit 5).
"""

import re

from django.contrib import admin
from django.db import transaction
from django.http import Http404, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from . import diensten
from .models import OPEN, Verbetervoorstel, VoorstelStatus
from .rechten import rechten

#: Zo lang mag de titel in de lijst zijn (de eerste zin van het voorstel, ingekort).
TITEL_TEKENS = 60


def titel_van(tekst: str) -> str:
    """De titel van een voorstel: de eerste zin, ingekort. De indiener vult geen titel in (besluit 10)."""
    tekst = " ".join((tekst or "").split())
    zin = re.split(r"(?<=[.!?])\s", tekst, maxsplit=1)[0].rstrip(".!?")
    return zin if len(zin) <= TITEL_TEKENS else zin[: TITEL_TEKENS - 1].rstrip() + "…"


def _moment(m) -> str:
    return date_format(timezone.localtime(m), "j F Y H:i") if m else ""


def _item(v, gebruiker, andere):
    return {
        "id": v.pk,
        "titel": titel_van(v.tekst),
        "citaat": v.citaat or "",
        "tekst": v.tekst,
        "indiener": diensten.naam_van(v.ingediend_door) if v.ingediend_door_id else "",
        "op": date_format(timezone.localtime(v.ingediend_op), "j F Y"),
        "steun": v.steun.count(),
        # De redactie ziet wie steunt (collega's zien alleen het aantal).
        "steuners": [st.naam for st in v.steun.select_related("gebruiker")],
        "eigenaar": (diensten.naam_van(v.eigenaar) if v.eigenaar_id else ""),
        "van_mij": v.eigenaar_id == gebruiker.pk,
        "mee": v.in_conceptversie,
        "berichten": [
            {"tekst": b.tekst, "naam": b.naam, "moment": _moment(b.moment)}
            for b in v.berichten.select_related("auteur").order_by("moment", "pk")
        ],
        "notities": [
            {"tekst": n.tekst, "naam": diensten.naam_van(n.auteur), "moment": _moment(n.moment)}
            for n in v.notities.select_related("auteur").order_by("moment", "pk")
        ],
        "andere": [a for a in andere if a["id"] != v.pk],
        "verborgen": v.verborgen,
        # Al verwerkt in een gepubliceerde versie, maar nog niet afgehandeld (venster na publiceren overgeslagen).
        "verwerkt_in_versie": v.verwerkt_in_versie,
        "afhandelen_url": reverse("admin:kennisbank_artikel_voorstellen_afhandelen", args=[v.artikel_id])
        if v.verwerkt_in_versie
        else "",
    }


def _open_voorstellen(artikel):
    return (
        Verbetervoorstel.objects.filter(artikel=artikel, status__in=OPEN)
        .select_related("ingediend_door", "eigenaar")
        .order_by("ingediend_op", "pk")
    )


def _andere(artikel):
    """Voor *Dubbel…*: de andere voorstellen bij dit artikel (ook afgehandelde)."""
    return [
        {"id": pk, "label": f"{titel_van(tekst)} ({dict(VoorstelStatus.choices).get(st, st).lower()})"}
        for pk, tekst, st in Verbetervoorstel.objects.filter(artikel=artikel)
        .order_by("-ingediend_op")
        .values_list("pk", "tekst", "status")[:30]
    ]


def lade_gegevens(artikel, gebruiker, open_pk=None, op_slot=False) -> dict:
    """Wat het bewerkscherm nodig heeft voor de lade (als JSON in de pagina)."""
    andere = _andere(artikel)
    voorstellen = [_item(v, gebruiker, andere) for v in _open_voorstellen(artikel)]
    open_id = None
    if open_pk and str(open_pk).isdigit() and any(v["id"] == int(open_pk) for v in voorstellen):
        open_id = int(open_pk)
    return {
        "voorstellen": voorstellen,
        "open": open_id,
        "op_slot": op_slot,
        "actie_url": reverse("beheer-voorstel-lade", args=[0]),
    }


# --- meenemen bij opslaan -------------------------------------------------------------------------------


def _ids(waarde: str) -> set:
    return {int(x) for x in (waarde or "").split(",") if x.strip().isdigit()}


def meenemen_opslaan(request, artikel, *, spoed=False) -> list:
    """Verwerk de vinkjes *Meenemen in deze versie* na een geslaagde opslag.

    Alleen voor de voorstellen die in de lade stonden: een voorstel dat intussen is binnengekomen, raakt
    het formulier niet. Gewoon opslaan of publiceren: `in_conceptversie` volgt het vinkje. Spoedcorrectie:
    de aangevinkte voorstellen horen bij de correctie die nu wordt gepubliceerd; geeft hun ids terug (de
    aanroeper zet het versienummer). Wie meeneemt, wordt eigenaar; de vorige eigenaar krijgt een e-mail.
    """
    if "kb_lade" not in request.POST:
        return []
    in_lade = _ids(request.POST.get("kb_lade"))
    mee = _ids(request.POST.get("kb_meenemen")) & in_lade
    spoed_ids = []
    model_admin = admin.site._registry.get(Verbetervoorstel)
    for v in (
        Verbetervoorstel.objects.select_for_update(of=("self",))
        .select_related("artikel", "eigenaar")
        .filter(artikel=artikel, status__in=OPEN, pk__in=in_lade)
    ):
        gewenst = v.pk in mee
        if spoed:
            if gewenst:
                spoed_ids.append(v.pk)
                _eigenaar_worden(request, v)
            continue
        if gewenst == v.in_conceptversie:
            continue
        v.in_conceptversie = gewenst
        v.save(update_fields=["in_conceptversie"])
        if gewenst:
            _eigenaar_worden(request, v)
        if model_admin:
            model_admin.log_change(
                request,
                v,
                "Meegenomen in de nieuwe versie van het artikel."
                if gewenst
                else "Niet meer meegenomen in de nieuwe versie.",
            )
    return spoed_ids


def _eigenaar_worden(request, v) -> None:
    vorige = v.eigenaar if v.eigenaar_id and v.eigenaar_id != request.user.pk else None
    if v.eigenaar_id == request.user.pk:
        return
    try:
        diensten.voorstel_naar_bak(v, request.user, request.user)
    except diensten.VoorstelFout:
        return
    if vorige is not None and vorige.email and vorige.is_active:
        diensten.mail_na_commit(
            f"Voorstel overgenomen: {v.artikel.titel}",
            f"{diensten.naam_van(request.user)} heeft het verbetervoorstel bij '{v.artikel.titel}' uit jouw bak "
            "overgenomen en neemt het mee in de nieuwe versie van het artikel. Je hoeft er niets meer mee te doen.\n\n"
            f"{diensten.voorstel_beheer_url(v)}",
            [vorige.email],
        )


# --- bericht, notitie, afwijzen, dubbel ---------------------------------------------------------------------


def _fout(tekst, status=400):
    return JsonResponse({"fout": tekst}, status=status)


@require_POST
def lade_actie(request, pk):
    """Eén handeling vanuit de lade. Antwoordt met het bijgewerkte voorstel (of `weg` als het is afgehandeld)."""
    from . import review

    actie = request.POST.get("actie")
    tekst = (request.POST.get("tekst") or "").strip()
    if actie not in ("bericht", "notitie", "afwijzen", "dubbel", "verbergen"):
        return _fout("Onbekende handeling.")
    if not tekst and actie != "verbergen":
        return _fout("Schrijf eerst je tekst." if actie == "notitie" else "Schrijf eerst je bericht aan de indiener.")
    r = rechten(request)
    with transaction.atomic():
        v = (
            Verbetervoorstel.objects.select_for_update(of=("self",))
            .select_related("artikel", "artikel__omgeving", "eigenaar", "ingediend_door")
            .filter(pk=pk, artikel__omgeving_id__in=r.redactie_omgevingen)
            .first()
        )
        if v is None or not r.is_redacteur:
            raise Http404
        model_admin = admin.site._registry[Verbetervoorstel]
        if actie == "verbergen":
            # Verbergen voor collega's (bijvoorbeeld omdat er een naam in staat): de stand die de knop wil.
            gewenst = request.POST.get("waarde") == "1"
            if gewenst != v.verborgen:
                v.verborgen = gewenst
                v.save(update_fields=["verborgen"])
                model_admin.log_change(
                    request, v, "Verborgen voor collega's." if gewenst else "Weer zichtbaar voor collega's."
                )
            melding = "Verborgen voor collega's." if gewenst else "Collega's zien het voorstel weer."
        elif actie == "notitie":
            diensten.notitie_toevoegen(v, request.user, tekst)
            melding = "Notitie bewaard. Alleen redacteuren zien hem."
        elif not v.is_open:
            return _fout("Dit voorstel is intussen afgehandeld.", status=409)
        elif actie == "bericht":
            diensten.voorstelbericht_toevoegen(v, request.user, tekst, van_redactie=True)
            if v.eigenaar_id is None:  # een bericht uit de werkvoorraad: wie schrijft, pakt het op
                v = diensten.voorstel_naar_bak(v, request.user, request.user)
            model_admin.log_change(request, v, "Bericht aan de indiener verstuurd.")
            aan = f" aan {diensten.naam_van(v.ingediend_door)}" if v.ingediend_door_id else ""
            melding = f"Bericht verstuurd{aan}."
        else:
            if v.in_conceptversie and review.op_slot(v.artikel_id):
                return _fout(
                    "Dit voorstel is meegenomen in de versie die ter inzage ligt. "
                    "Afwijzen kan pas als de review terug is.",
                    status=409,
                )
            dubbel = None
            if actie == "dubbel":
                keuze = request.POST.get("dubbel_van") or ""
                dubbel = (
                    Verbetervoorstel.objects.filter(pk=int(keuze) if keuze.isdigit() else 0, artikel=v.artikel)
                    .exclude(pk=v.pk)
                    .first()
                )
                if dubbel is None:
                    return _fout("Kies van welk voorstel dit een dubbel is.")
            try:
                diensten.voorstel_afhandelen(v, request.user, VoorstelStatus.AFGEWEZEN, tekst, dubbel_van=dubbel)
            except diensten.VoorstelFout as e:
                return _fout(str(e), status=409)
            model_admin.log_change(
                request, v, f"Afgewezen als dubbel van voorstel {dubbel.pk}." if dubbel else "Afgewezen."
            )
            aan = f"; {diensten.naam_van(v.ingediend_door)} krijgt je bericht" if v.ingediend_door_id else ""
            return JsonResponse({"weg": True, "melding": f"Afgehandeld{aan}. Het staat nu onder Afgehandeld."})
    v.refresh_from_db()
    return JsonResponse({"voorstel": _item(v, request.user, _andere(v.artikel)), "melding": melding})
