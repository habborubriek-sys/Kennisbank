"""Het behandelscherm van een verbetervoorstel: /beheer/voorstel/<id>/ (ronde 2, functionele review 11 november).

In de stijl van de werkplek, met de kolom links. Bovenaan het voorstel met het citaat in de tekst van het
artikel; daaronder het gesprek met de indiener, met een eigen knop *Versturen* en de knoppen om af te
handelen; ernaast de interne notities en wat je met de bak doet.

Het oude beheerformulier (VerbetervoorstelAdmin) blijft bestaan voor bestaande koppelingen en
bladwijzers, maar wie het opent, komt hier uit.

Twee redacteuren tegelijk: het scherm onthoudt bij het openen de status, de eigenaar en het laatste
bericht. Is een daarvan intussen veranderd, dan wordt er niets verstuurd en blijft je tekst staan, met
wat er intussen gebeurde (review van de functioneel analist, punt 8).
"""

import re
from html import escape
from urllib.parse import urlencode

from django.contrib import admin, messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from . import diensten
from .inhoud import naar_platte_tekst
from .models import Conceptversie, Omgeving, Verbetervoorstel, VoorstelStatus
from .rechten import rechten
from .werkoverzicht import _menu, clusters_van, redacteuren_per_omgeving, werkplek_url

#: Hoeveel tekens van het artikel er rond het citaat te zien zijn.
CONTEXT_TEKENS = 350


def scherm_url(voorstel, terug=None) -> str:
    url = reverse("beheer-voorstel", args=[voorstel.pk])
    return f"{url}?{urlencode({'terug': terug})}" if terug else url


def _normaal(tekst: str) -> str:
    return " ".join((tekst or "").split())


def citaat_in_context(artikel_html: str, citaat: str):
    """Het citaat in de huidige tekst van het artikel, met wat ervoor en erna staat.

    Geeft (html, gevonden). De html is geschoond: alleen platte tekst met een <mark> om het citaat.
    Staat het citaat er niet (meer) letterlijk in, dan het begin van het artikel en gevonden=False.
    """
    tekst = _normaal(naar_platte_tekst(artikel_html or ""))
    stuk = _normaal(citaat)
    if not stuk:
        return "", False
    m = re.search(re.escape(stuk), tekst, flags=re.IGNORECASE)
    if not m:
        return "", False
    begin = max(0, m.start() - CONTEXT_TEKENS)
    eind = min(len(tekst), m.end() + CONTEXT_TEKENS)
    voor = ("… " if begin else "") + tekst[begin : m.start()]
    na = tekst[m.end() : eind] + (" …" if eind < len(tekst) else "")
    html = f"{escape(voor)}<mark>{escape(tekst[m.start() : m.end()])}</mark>{escape(na)}"
    return mark_safe(html), True  # noqa: S308 - alles hierboven is ge-escaped


def _voorstel_voor(request, pk, slot=False):
    r = rechten(request)
    qs = Verbetervoorstel.objects.filter(artikel__omgeving_id__in=r.redactie_omgevingen)
    if slot:
        qs = qs.select_for_update(of=("self",))
    v = (
        qs.select_related("artikel", "artikel__omgeving", "eigenaar", "ingediend_door", "cluster", "behandeld_door")
        .filter(pk=pk)
        .first()
    )
    if v is None:
        raise Http404  # verraad niet dat het bestaat
    return v, r


def _laatste_bericht_id(v) -> int:
    return v.berichten.order_by("-pk").values_list("pk", flat=True).first() or 0


def _context(request, v, r, terug, invoer=None, intussen=None):
    omgevingen = sorted(r.redactie_omgevingen)
    namen_omgeving = dict(Omgeving.objects.filter(pk__in=omgevingen).values_list("pk", "naam"))
    menu = _menu(request, omgevingen, namen_omgeving)
    context_html, gevonden = citaat_in_context(v.artikel.inhoud, v.citaat)
    indiener = diensten.naam_van(v.ingediend_door) if v.ingediend_door_id else None
    collegas = [
        (pk, naam)
        for pk, naam in redacteuren_per_omgeving([v.artikel.omgeving_id]).get(v.artikel.omgeving_id, [])
        if pk != v.eigenaar_id
    ]
    clusters = clusters_van([v.artikel.omgeving_id])
    bakken = ([("algemeen", "Algemeen")] if v.cluster_id else []) + [
        (str(pk), naam) for pk, naam in clusters if pk != v.cluster_id
    ]
    andere = (
        Verbetervoorstel.objects.filter(artikel=v.artikel)
        .exclude(pk=v.pk)
        .order_by("-ingediend_op")
        .values_list("pk", "ingediend_op", "status", "tekst")[:30]
    )
    status_label = dict(VoorstelStatus.choices)
    berichten = list(v.berichten.select_related("auteur").order_by("moment", "pk"))
    notities = list(v.notities.select_related("auteur").order_by("moment", "pk"))
    steun = list(v.steun.select_related("gebruiker"))
    invoer = invoer or {}
    return {
        **admin.site.each_context(request),
        "title": f"Voorstel bij {v.artikel.titel}",
        "werkplek": {
            "menu": menu,
            "gekozen": terug or "",
            "is_alles": False,
            "nieuw_artikel_url": reverse("admin:kennisbank_artikel_add"),
            "nieuw_bericht_url": reverse("admin:kennisbank_bericht_add"),
        },
        "v": v,
        "terug": terug or "",
        "terug_url": werkplek_url(terug),
        "indiener": indiener,
        "eigenaar": diensten.naam_van(v.eigenaar) if v.eigenaar_id else None,
        "van_mij": v.eigenaar_id == request.user.pk,
        "behandeld_door": diensten.naam_van(v.behandeld_door) if v.behandeld_door_id else None,
        "artikel_url": v.artikel.get_absolute_url(),
        "artikel_bewerken_url": reverse("admin:kennisbank_artikel_change", args=[v.artikel_id]),
        "geschiedenis_url": reverse("admin:kennisbank_verbetervoorstel_history", args=[v.pk]),
        "heeft_conceptversie": Conceptversie.objects.filter(artikel_id=v.artikel_id).exists(),
        "afhandelen_url": reverse("admin:kennisbank_artikel_voorstellen_afhandelen", args=[v.artikel_id]),
        "context_html": context_html,
        "citaat_gevonden": gevonden,
        "berichten": [{"naam": b.naam, "moment": b.moment, "tekst": b.tekst, "pm": b.van_redactie} for b in berichten],
        "notities": [{"naam": diensten.naam_van(n.auteur), "moment": n.moment, "tekst": n.tekst} for n in notities],
        "steun": [s.naam for s in steun],
        "collegas": collegas,
        "bakken": bakken if v.is_open else [],
        "andere": [
            {"pk": pk, "label": f"{timezone.localtime(op):%d-%m-%Y} · {status_label.get(st, st)} · {tekst[:70]}"}
            for pk, op, st, tekst in andere
        ],
        "dubbel_van": v.dubbel_van,
        "dubbel_van_url": scherm_url(v.dubbel_van) if v.dubbel_van_id else None,
        "dubbele": [scherm_url(d) for d in v.dubbele.all()[:10]],
        "geladen": {"status": v.status, "eigenaar": str(v.eigenaar_id or ""), "bericht": _laatste_bericht_id(v)},
        "invoer": invoer,
        "intussen": intussen,
        "actie_url": reverse("beheer-werkplek-actie"),
    }


def voorstel_scherm(request, pk):
    terug = request.GET.get("terug") or request.POST.get("terug") or None
    if request.method == "POST":
        return _verwerk(request, pk, terug)
    v, r = _voorstel_voor(request, pk)
    if not r.is_redacteur:
        raise Http404
    diensten.voorstel_gezien_door_eigenaar(v, request.user)
    return TemplateResponse(request, "admin/kennisbank/voorstel.html", _context(request, v, r, terug))


def _verwerk(request, pk, terug):
    actie = request.POST.get("actie")
    tekst = (request.POST.get("bericht") or "").strip()
    notitie = (request.POST.get("notitie") or "").strip()
    invoer = {"bericht": tekst, "notitie": notitie, "dubbel": request.POST.get("dubbel_van") or ""}
    with transaction.atomic():
        v, r = _voorstel_voor(request, pk, slot=True)
        if not r.is_redacteur:
            raise Http404
        if actie == "notitie":
            if not notitie:
                messages.warning(request, "Schrijf eerst een notitie.")
                return _opnieuw(request, v, r, terug, invoer)
            diensten.notitie_toevoegen(v, request.user, notitie)
            messages.success(request, "Notitie toegevoegd. Alleen de redactie ziet hem.")
            return redirect(scherm_url(v, terug))
        if actie == "meenemen":
            # Reviewpunt 11: dit voorstel wordt verwerkt in de nieuwe versie van het artikel.
            if not v.is_open:
                raise Http404
            v.in_conceptversie = not v.in_conceptversie
            v.save(update_fields=["in_conceptversie"])
            admin.site._registry[Verbetervoorstel].log_change(
                request,
                v,
                "Meegenomen in de nieuwe versie van het artikel."
                if v.in_conceptversie
                else "Niet meer meegenomen in de nieuwe versie.",
            )
            messages.success(
                request,
                "Het voorstel wordt meegenomen in de nieuwe versie. Na publiceren vraagt de kennisbank of je het "
                "wilt afhandelen."
                if v.in_conceptversie
                else "Het voorstel wordt niet meer meegenomen in de nieuwe versie.",
            )
            return redirect(scherm_url(v, terug))
        if actie == "verbergen":
            v.verborgen = not v.verborgen
            v.save(update_fields=["verborgen"])
            admin.site._registry[Verbetervoorstel].log_change(
                request, v, "Verborgen voor collega's." if v.verborgen else "Weer zichtbaar voor collega's."
            )
            messages.success(
                request,
                "Het voorstel is verborgen voor collega's." if v.verborgen else "Collega's zien het voorstel weer.",
            )
            return redirect(scherm_url(v, terug))
        if actie not in ("bericht", "verwerkt", "afwijzen"):
            raise Http404

        # Is er sinds het openen iets veranderd? Dan niets versturen en laten zien wat.
        intussen = []
        if actie != "bericht" and (request.POST.get("geladen_status") or v.status) != v.status:
            intussen.append(f"de status is intussen '{v.get_status_display()}'")
        if (request.POST.get("geladen_eigenaar") or "") != str(v.eigenaar_id or "") and actie != "bericht":
            waar = f"de bak van {diensten.naam_van(v.eigenaar)}" if v.eigenaar_id else "de werkvoorraad"
            intussen.append(f"het ligt intussen in {waar}")
        geladen_bericht = request.POST.get("geladen_bericht") or "0"
        nieuwe = v.berichten.filter(pk__gt=int(geladen_bericht) if geladen_bericht.isdigit() else 0)
        if nieuwe.exists():
            namen = sorted({b.naam for b in nieuwe.select_related("auteur")})
            intussen.append(f"{' en '.join(namen)} stuurde intussen een bericht aan de indiener (zie hieronder)")
        if intussen:
            return _opnieuw(request, v, r, terug, invoer, intussen)

        if not tekst:
            messages.warning(
                request,
                "Schrijf eerst je bericht aan de indiener."
                if actie == "bericht"
                else "Schrijf de indiener waarom. Dat bericht krijgt hij als antwoord, per melding en per e-mail.",
            )
            return _opnieuw(request, v, r, terug, invoer)

        model_admin = admin.site._registry[Verbetervoorstel]
        if actie == "bericht":
            diensten.voorstelbericht_toevoegen(v, request.user, tekst, van_redactie=True)
            # Een bericht uit de werkvoorraad: wie schrijft, pakt het op (zoals in het oude scherm).
            if v.is_open and v.eigenaar_id is None:
                diensten.voorstel_naar_bak(v, request.user, request.user)
            model_admin.log_change(request, v, "Bericht aan de indiener verstuurd.")
            aan = f" naar {diensten.naam_van(v.ingediend_door)}" if v.ingediend_door_id else ""
            messages.success(request, f"Bericht verstuurd{aan}.")
            return redirect(scherm_url(v, terug))

        status = VoorstelStatus.VERWERKT if actie == "verwerkt" else VoorstelStatus.AFGEWEZEN
        dubbel = None
        keuze = request.POST.get("dubbel_van") or ""
        if actie == "afwijzen" and keuze:
            dubbel = (
                Verbetervoorstel.objects.filter(
                    pk=int(keuze) if keuze.isdigit() else 0, artikel__omgeving_id__in=r.redactie_omgevingen
                )
                .select_related("artikel")
                .first()
            )
            if dubbel is None:
                raise Http404
        try:
            diensten.voorstel_afhandelen(v, request.user, status, tekst, dubbel_van=dubbel)
        except diensten.VoorstelFout as e:
            messages.warning(request, str(e))
            return _opnieuw(request, v, r, terug, invoer)
        uitleg = "Verwerkt." if status == VoorstelStatus.VERWERKT else "Afgewezen."
        if dubbel:
            uitleg = f"Afgewezen als dubbel van voorstel {dubbel.pk}."
        model_admin.log_change(request, v, uitleg)
    aan = f"; {diensten.naam_van(v.ingediend_door)} krijgt je bericht" if v.ingediend_door_id else ""
    messages.success(
        request,
        f"Voorstel bij '{v.artikel.titel}' {v.get_status_display().lower()}{aan}. Het staat nu onder Afgehandeld.",
    )
    return redirect(werkplek_url(terug))


def _opnieuw(request, v, r, terug, invoer, intussen=None):
    """Het scherm opnieuw tonen met wat de redacteur had ingevuld (niets is verstuurd)."""
    return TemplateResponse(
        request, "admin/kennisbank/voorstel.html", _context(request, v, r, terug, invoer, intussen), status=200
    )
