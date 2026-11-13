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
- **Afhandelen als verwerkt** (1.31.2, K2) is voor een voorstel waarvan de tekst al in een gepubliceerde
  versie is aangepast, bijvoorbeeld door een collega of in een eerdere correctie. Het krijgt het nummer van
  de versie die medewerkers nu zien en loopt door dezelfde dienst als het scherm na publiceren. Staat de
  geciteerde tekst nog letterlijk in de gepubliceerde versie, dan moet de redacteur het eerst bevestigen.
"""

import re

from django.contrib import admin, messages
from django.db import transaction
from django.http import Http404, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from . import diensten
from .models import OPEN, Status, Verbetervoorstel, VoorstelStatus
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


def verwerkt_versie(v) -> int:
    """In welke gepubliceerde versie is dit voorstel verwerkt als je het nu als verwerkt afhandelt? 0 = kan niet.

    Is het al meegenomen in een gepubliceerde versie (het scherm na publiceren is overgeslagen), dan dat
    nummer; anders de versie die medewerkers nu zien. Een artikel dat niet gepubliceerd is, heeft er geen.
    """
    artikel = v.artikel
    if artikel.status != Status.GEPUBLICEERD or not artikel.versie:
        return 0
    return v.verwerkt_in_versie or artikel.versie


def citaat_gepubliceerd(v) -> bool:
    """Staat de geciteerde tekst nog letterlijk in de versie die medewerkers nu zien? (Niet: in de conceptversie.)"""
    from .behandelen import citaat_in_context

    return bool(v.citaat) and citaat_in_context(v.artikel.inhoud, v.citaat)[1]


def verwerkt_bericht(v, versie: int) -> str:
    """Het voorgevulde bedankbericht, gelijk aan dat op het scherm na publiceren."""
    return (
        f"Dank je wel voor je verbetervoorstel. We hebben het verwerkt in versie {versie} "
        f"van '{v.artikel.titel}', die nu voor iedereen te zien is."
    )


def _item(v, gebruiker, andere):
    versie = verwerkt_versie(v)
    return {
        # 1.31.2 (K2): *Afhandelen als verwerkt*. 0 = kan niet (het artikel is niet gepubliceerd).
        "verwerkt_versie": versie,
        "verwerkt_bericht": verwerkt_bericht(v, versie) if versie else "",
        "citaat_gepubliceerd": bool(versie) and citaat_gepubliceerd(v),
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
        # Ronde A (M5): hoe het voorstel erbij lag toen de lade werd getekend. Gaat mee met elke handeling;
        # is het intussen veranderd, dan weigert de server en toont de lade de nieuwe stand.
        "geladen_eigenaar": v.eigenaar_id or 0,
        "geladen_bericht": v.berichten.order_by("-pk").values_list("pk", flat=True).first() or 0,
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
        .select_related("ingediend_door", "eigenaar", "artikel")
        .order_by("ingediend_op", "pk")
    )


def _andere(artikel):
    """Voor *Ontdubbelen*: de andere voorstellen bij dit artikel (ook afgehandelde)."""
    return [
        {"id": pk, "label": f"{titel_van(tekst)} ({dict(VoorstelStatus.choices).get(st, st).lower()})"}
        for pk, tekst, st in Verbetervoorstel.objects.filter(artikel=artikel)
        .order_by("-ingediend_op")
        .values_list("pk", "tekst", "status")[:30]
    ]


def lade_gegevens(artikel, gebruiker, open_pk=None, op_slot=False, post=None, akkoord=None) -> dict:
    """Wat het bewerkscherm nodig heeft voor de lade (als JSON in de pagina).

    `post`: het formulier kwam terug met een fout (ronde A, M6). Wat de redacteur bij Meenemen had
    veranderd, staat dan als `mee_gewenst` bij het voorstel; de lade toont het als "nog niet opgeslagen".
    `akkoord`: de voorstellen die meegenomen waren toen het laatste akkoord werd gegeven (ronde A, M7), of
    None als er geen akkoord is.
    """
    andere = _andere(artikel)
    voorstellen = [_item(v, gebruiker, andere) for v in _open_voorstellen(artikel)]
    if post is not None and "kb_lade" in post:
        in_lade = _ids(post.get("kb_lade"))
        gewenst = _ids(post.get("kb_meenemen")) & in_lade
        geladen = _ids(post.get("kb_mee_geladen")) & in_lade if "kb_mee_geladen" in post else None
        for item in voorstellen:
            if item["id"] not in in_lade:
                continue
            wil = item["id"] in gewenst
            was = (item["id"] in geladen) if geladen is not None else item["mee"]
            if wil != was:
                item["mee_gewenst"] = wil
    open_id = None
    if open_pk and str(open_pk).isdigit() and any(v["id"] == int(open_pk) for v in voorstellen):
        open_id = int(open_pk)
    return {
        "voorstellen": voorstellen,
        "open": open_id,
        "op_slot": op_slot,
        "akkoord": sorted(akkoord) if akkoord is not None else None,
        "actie_url": reverse("beheer-voorstel-lade", args=[0]),
    }


# --- meenemen bij opslaan -------------------------------------------------------------------------------


def _ids(waarde: str) -> set:
    return {int(x) for x in (waarde or "").split(",") if x.strip().isdigit()}


def meenemen_opslaan(request, artikel, *, spoed=False, telt=True) -> list:
    """Verwerk de vinkjes *Meenemen in deze versie* na een geslaagde opslag.

    Alleen voor de voorstellen die in de lade stonden: een voorstel dat intussen is binnengekomen, raakt
    het formulier niet. Wie meeneemt, wordt eigenaar; de vorige eigenaar krijgt een e-mail.

    - **Conceptversie of gewone publicatie** (ronde A, M2): alleen wat deze redacteur zelf heeft veranderd
      telt (`kb_mee_geladen` is de stand bij het laden). Heeft een collega hetzelfde voorstel intussen
      anders gezet, dan wordt het overgeslagen en gemeld; een verouderd scherm draait zo niets terug.
    - **Spoedcorrectie**: de aangevinkte voorstellen horen bij de correctie die nu wordt gepubliceerd;
      geeft hun ids terug (de aanroeper zet het versienummer). Een voorstel dat in een conceptversie zit
      die ter inzage ligt, kan niet (ronde A, M4).
    - **telt=False** (geen inhoudelijke wijziging, dus geen nieuwe versie): er verandert niets. Geeft de ids
      terug die de redacteur nieuw had aangevinkt, zodat de aanroeper kan zeggen dat ze niet meetellen.
    """
    if "kb_lade" not in request.POST:
        return []
    in_lade = _ids(request.POST.get("kb_lade"))
    mee = _ids(request.POST.get("kb_meenemen")) & in_lade
    geladen = _ids(request.POST.get("kb_mee_geladen")) & in_lade if "kb_mee_geladen" in request.POST else None
    model_admin = admin.site._registry.get(Verbetervoorstel)
    qs = (
        Verbetervoorstel.objects.select_for_update(of=("self",))
        .select_related("artikel", "eigenaar")
        .filter(artikel=artikel, status__in=OPEN, pk__in=in_lade)
        .order_by("pk")
    )
    if not telt:
        return [v.pk for v in qs if v.pk in mee and not (geladen is not None and v.pk in geladen)]
    gevonden = set()
    spoed_ids, overgeslagen = [], []
    for v in qs:
        gevonden.add(v.pk)
        if spoed:
            if v.pk not in mee:
                continue
            if diensten.voorstel_op_slot(v):
                overgeslagen.append(f"'{titel_van(v.tekst)}' (meegenomen in de versie die ter inzage ligt)")
                continue
            spoed_ids.append(v.pk)
            _eigenaar_worden(request, v)
            if model_admin:
                model_admin.log_change(request, v, "Meegenomen in een spoedcorrectie.")
            continue
        gewenst = v.pk in mee
        was = (v.pk in geladen) if geladen is not None else v.in_conceptversie
        if gewenst == was:
            continue  # niet door deze redacteur veranderd: laten zoals het is
        if v.in_conceptversie == gewenst:
            continue  # een collega deed intussen hetzelfde
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
    # Aangevinkt, maar intussen afgehandeld (en dus niet meer open): zeg het (review 1.27.0, R1 B8).
    weg = [pk for pk in mee if pk not in gevonden and (geladen is None or pk not in geladen or spoed)]
    if weg:
        overgeslagen.append(
            f"{len(weg)} voorstel{'len' if len(weg) > 1 else ''} (intussen afgehandeld door een collega)"
        )
    if overgeslagen:
        messages.warning(request, "Niet meegenomen: " + "; ".join(overgeslagen) + ".")
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


def _intussen(request, v, actie):
    """Is er sinds het tekenen van de lade iets veranderd wat deze handeling raakt? Dan de uitleg, anders None.

    Hetzelfde als het oude behandelscherm deed (review functioneel analist punt 8): een bericht gaat niet
    als een collega intussen ook schreef; afwijzen, dubbel en verwerkt niet als het voorstel intussen bij
    een ander ligt. Zonder de velden (een oude pagina) wordt er niet vergeleken.
    """
    nieuw_bericht = request.POST.get("geladen_bericht")
    if nieuw_bericht is not None and nieuw_bericht.isdigit():
        nieuwe = v.berichten.filter(pk__gt=int(nieuw_bericht)).select_related("auteur")
        if nieuwe.exists():
            namen = " en ".join(sorted({b.naam for b in nieuwe}))
            return f"{namen} stuurde intussen een bericht aan de indiener. Lees het eerst; er is niets verstuurd."
    eigenaar = request.POST.get("geladen_eigenaar")
    if actie in ("afwijzen", "dubbel", "verwerkt") and eigenaar is not None and eigenaar.isdigit():
        if int(eigenaar) != (v.eigenaar_id or 0):
            waar = f"bij {diensten.naam_van(v.eigenaar)}" if v.eigenaar_id else "weer in de werkvoorraad"
            return f"Dit voorstel ligt intussen {waar}. Kijk eerst wat er is gebeurd; er is niets verstuurd."
    return None


@require_POST
def lade_actie(request, pk):
    """Eén handeling vanuit de lade. Antwoordt met het bijgewerkte voorstel (of `weg` als het is afgehandeld)."""
    actie = request.POST.get("actie")
    tekst = (request.POST.get("tekst") or "").strip()
    if actie not in ("bericht", "notitie", "afwijzen", "dubbel", "verbergen", "verwerkt"):
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
        elif (intussen := _intussen(request, v, actie)) is not None:
            # Ronde A (M5): een collega deed intussen iets met dit voorstel. Niets versturen; de lade toont
            # de nieuwe stand en je getypte tekst blijft staan.
            return JsonResponse({"fout": intussen, "voorstel": _item(v, request.user, _andere(v.artikel))}, status=409)
        elif actie == "bericht":
            diensten.voorstelbericht_toevoegen(v, request.user, tekst, van_redactie=True)
            if v.eigenaar_id is None:  # een bericht uit de werkvoorraad: wie schrijft, pakt het op
                v = diensten.voorstel_naar_bak(v, request.user, request.user)
            model_admin.log_change(request, v, "Bericht aan de indiener verstuurd.")
            aan = f" aan {diensten.naam_van(v.ingediend_door)}" if v.ingediend_door_id else ""
            melding = f"Bericht verstuurd{aan}."
        elif actie == "verwerkt":
            # 1.31.2 (K2): de tekst is al aangepast in een gepubliceerde versie.
            versie = verwerkt_versie(v)
            if not versie:
                return _fout(
                    "Dit artikel is niet gepubliceerd. Afhandelen als verwerkt kan pas als de aangepaste tekst "
                    "voor medewerkers te zien is.",
                    status=409,
                )
            if diensten.voorstel_op_slot(v):
                return _fout(diensten.OP_SLOT_TEKST, status=409)
            if citaat_gepubliceerd(v) and request.POST.get("zeker") != "1":
                # De lade vraagt dit zelf al; dit is voor als de tekst intussen is veranderd. Niets versturen.
                return JsonResponse(
                    {
                        "fout": "De geciteerde tekst staat nog letterlijk in de gepubliceerde versie. "
                        "Kies opnieuw Afhandelen en bevestig dat het voorstel toch is verwerkt. "
                        "Er is niets verstuurd.",
                        "voorstel": _item(v, request.user, _andere(v.artikel)),
                    },
                    status=409,
                )
            try:
                diensten.voorstel_afhandelen(v, request.user, VoorstelStatus.VERWERKT, tekst)
            except diensten.VoorstelFout as e:
                return _fout(str(e), status=409)
            v.verwerkt_in_versie = versie
            v.save(update_fields=["verwerkt_in_versie"])
            model_admin.log_change(request, v, f"Verwerkt in versie {versie} (afgehandeld vanuit de lade).")
            aan = f"; {diensten.naam_van(v.ingediend_door)} krijgt je bericht" if v.ingediend_door_id else ""
            melding = f"Afgehandeld als verwerkt in versie {versie}{aan}. Het staat nu onder Afgehandeld."
            return JsonResponse({"weg": True, "melding": melding})
        else:
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
            except diensten.VoorstelOpSlot:
                return _fout(
                    "Dit voorstel is meegenomen in de versie die ter inzage ligt. "
                    "Afwijzen kan pas als de review terug is.",
                    status=409,
                )
            except diensten.VoorstelFout as e:
                return _fout(str(e), status=409)
            model_admin.log_change(
                request, v, f"Afgewezen als dubbel van voorstel {dubbel.pk}." if dubbel else "Afgewezen."
            )
            aan = f"; {diensten.naam_van(v.ingediend_door)} krijgt je bericht" if v.ingediend_door_id else ""
            return JsonResponse({"weg": True, "melding": f"Afgehandeld{aan}. Het staat nu onder Afgehandeld."})
    v.refresh_from_db()
    return JsonResponse({"voorstel": _item(v, request.user, _andere(v.artikel)), "melding": melding})
