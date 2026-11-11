"""De startpagina van het beheer: de werkplek van een redacteur.

Links een kolom met de werkbakken: bovenaan de **Werkvoorraad** (de gezamenlijke bak van een omgeving),
daaronder alle procesmanagers met het aantal open voorstellen in hun bak, het archief **Afgehandeld**,
en de artikelkant: concepten, eigen kladversies en artikelen die opnieuw moeten worden nagekeken.
Rechts de inhoud van wat je aanklikt, met knoppen om een voorstel op te pakken, toe te wijzen,
over te nemen of terug te leggen. Het behandelscherm met het gesprek blijft het bestaande beheerscherm.

Alles is beperkt tot de omgevingen waar de gebruiker redacteur is. Het aantal databasevragen hangt niet
af van het aantal voorstellen of artikelen (bewaakt door een test).
"""

from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Min, Q
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone

from . import diensten
from .models import (
    AFGEHANDELD,
    Artikel,
    Cluster,
    Conceptversie,
    Inzage,
    InzageStatus,
    Kladversie,
    Omgeving,
    Rol,
    Status,
    Verbetervoorstel,
    VoorstelStatus,
)
from .rechten import rechten

OPEN = [VoorstelStatus.NIEUW, VoorstelStatus.IN_BEHANDELING]
# Na zoveel dagen kleurt het aantal in een bak rood: dan ligt er iets te lang.
LANG_GELEDEN_DAGEN = 30
KLAAR = list(AFGEHANDELD)
PER_PAGINA = 25


def werkplek_url(bak=None) -> str:
    url = reverse("beheer-start")
    return f"{url}?{urlencode({'bak': bak})}" if bak else url


def _dagen(moment):
    if not moment:
        return None
    return max(0, (timezone.now() - moment).days)


def _naam(voornaam, achternaam, gebruikersnaam) -> str:
    return f"{voornaam} {achternaam}".strip() or gebruikersnaam


def redacteuren_per_omgeving(omgevingen) -> dict:
    """{omgeving_id: [(pk, naam), ...]}: wie per omgeving een voorstel in zijn bak mag hebben.

    Hetzelfde als diensten.redacteuren_van, maar voor alle omgevingen tegelijk in twee vragen, zodat de
    keuzelijst "Toewijzen aan" per regel geen eigen vraag kost.
    """
    User = get_user_model()
    per = {oid: {} for oid in omgevingen}
    for pk, v, a, g, oid in (
        User.objects.filter(
            is_active=True,
            groups__kennisbank_toegang__omgeving_id__in=omgevingen,
            groups__kennisbank_toegang__rol=Rol.REDACTEUR,
        )
        .values_list("pk", "first_name", "last_name", "username", "groups__kennisbank_toegang__omgeving_id")
        .distinct()
    ):
        per[oid][pk] = _naam(v, a, g)
    beheerders = {
        pk: _naam(v, a, g)
        for pk, v, a, g in User.objects.filter(is_active=True, is_superuser=True).values_list(
            "pk", "first_name", "last_name", "username"
        )
    }
    for oid in per:
        per[oid].update(beheerders)
    return {oid: sorted(namen.items(), key=lambda x: x[1].lower()) for oid, namen in per.items()}


def clusters_van(omgevingen, open_qs=None):
    """[(pk, naam)]: de clusters die in deze omgevingen voorkomen (bij een artikel of een open voorstel).

    Clusters zijn organisatiebreed; een redacteur ziet alleen de clusters van zijn eigen omgevingen,
    net als in de keuzelijsten van de kennisbank.
    """
    voorwaarde = Q(artikel__omgeving_id__in=omgevingen)
    if open_qs is not None:
        voorwaarde |= Q(voorstellen__in=open_qs)
    return list(Cluster.objects.filter(voorwaarde).distinct().order_by("volgorde", "naam").values_list("pk", "naam"))


def _menu(request, omgevingen, namen_omgeving):
    """De linkerkolom: alle bakken met hun aantal, en de artikelkant."""
    User = get_user_model()
    ik = request.user
    open_qs = Verbetervoorstel.objects.filter(status__in=OPEN, artikel__omgeving_id__in=omgevingen)
    # Rood alleen als er iets lang ligt; een gewoon aantal is geen alarm (functionele review 11 november, B9).
    lang = Q(ingediend_op__lt=timezone.now() - timedelta(days=LANG_GELEDEN_DAGEN))

    algemeen = {
        rij["artikel__omgeving_id"]: rij
        for rij in open_qs.filter(eigenaar__isnull=True, cluster__isnull=True)
        .values("artikel__omgeving_id")
        .annotate(n=Count("pk"), oud=Count("pk", filter=lang))
    }
    per_cluster = {
        rij["cluster_id"]: rij
        for rij in open_qs.filter(eigenaar__isnull=True, cluster__isnull=False)
        .values("cluster_id")
        .annotate(n=Count("pk"), oud=Count("pk", filter=lang))
    }
    per_eigenaar = {
        rij["eigenaar_id"]: rij
        for rij in open_qs.exclude(eigenaar__isnull=True)
        .values("eigenaar_id")
        .annotate(
            n=Count("pk"),
            oud=Count("pk", filter=lang),
            nieuw=Count("pk", filter=Q(eigenaar_gezien_op__isnull=True)),
            oudste=Min("eigenaar_sinds"),
        )
    }
    # Alle procesmanagers van mijn omgevingen, ook met een lege bak, plus wie er nu iets heeft liggen
    # (bijvoorbeeld een functioneel beheerder die een voorstel heeft opgepakt).
    mensen = {
        pk: _naam(v, a, g)
        for pk, v, a, g in User.objects.filter(is_active=True)
        .filter(
            Q(groups__kennisbank_toegang__omgeving_id__in=omgevingen, groups__kennisbank_toegang__rol=Rol.REDACTEUR)
            | Q(pk__in=list(per_eigenaar))
            | Q(pk=ik.pk)
        )
        .values_list("pk", "first_name", "last_name", "username")
        .distinct()
    }

    # De werkvoorraad: de algemene bak (per omgeving als er meer zijn) en één bak per cluster.
    bakken = []
    for oid in sorted(omgevingen, key=lambda o: namen_omgeving[o].lower()):
        sleutel = "algemeen" if len(omgevingen) == 1 else f"algemeen-{oid}"
        bakken.append(
            {
                "sleutel": sleutel,
                "naam": "Algemeen" if len(omgevingen) == 1 else f"Algemeen · {namen_omgeving[oid]}",
                "aantal": algemeen.get(oid, {}).get("n", 0),
                "oud": algemeen.get(oid, {}).get("oud", 0),
                "soort": "werkvoorraad",
            }
        )
    for cid, naam in clusters_van(omgevingen, open_qs):
        bakken.append(
            {
                "sleutel": f"cluster-{cid}",
                "naam": naam,
                "aantal": per_cluster.get(cid, {}).get("n", 0),
                "oud": per_cluster.get(cid, {}).get("oud", 0),
                "soort": "cluster",
            }
        )
    personen = []
    for pk, naam in mensen.items():
        rij = per_eigenaar.get(pk, {})
        personen.append(
            {
                "sleutel": f"u{pk}",
                "naam": naam,
                "aantal": rij.get("n", 0),
                "oud": rij.get("oud", 0),
                "nieuw": rij.get("nieuw", 0) if pk == ik.pk else 0,
                "ik": pk == ik.pk,
                "soort": "persoon",
            }
        )
    personen.sort(key=lambda p: (not p["ik"], p["naam"].lower()))

    afgehandeld = Verbetervoorstel.objects.filter(status__in=KLAAR, artikel__omgeving_id__in=omgevingen).count()
    concepten = (
        Artikel.objects.filter(status=Status.CONCEPT, omgeving_id__in=omgevingen).count()
        + Conceptversie.objects.filter(artikel__omgeving_id__in=omgevingen).count()
    )
    klad = Kladversie.objects.filter(gebruiker=ik, afgesloten_op__isnull=True).exclude(velden={}).count()
    nakijken = Artikel.objects.filter(
        status=Status.GEPUBLICEERD, omgeving_id__in=omgevingen, herzien_voor__lt=timezone.localdate()
    ).count()
    artikelkant = [
        {"sleutel": "concepten", "naam": "Concepten", "aantal": concepten},
        {"sleutel": "kladversies", "naam": "Mijn kladversies", "aantal": klad},
        {"sleutel": "nakijken", "naam": "Opnieuw nakijken", "aantal": nakijken},
    ]
    # Reviewproces (stap C): alleen als het in een van mijn omgevingen aanstaat.
    if Omgeving.objects.filter(pk__in=omgevingen, reviewproces=True).exists():
        lopend = Inzage.objects.filter(artikel__omgeving_id__in=omgevingen, afgesloten=False)
        artikelkant.insert(
            1,
            {
                "sleutel": "ter_inzage",
                "naam": "Ter inzage",
                "aantal": lopend.values("artikel_id").distinct().count(),
                "oud": lopend.filter(status=InzageStatus.TERUGGEGEVEN).values("artikel_id").distinct().count(),
            },
        )
    return {
        "bakken": bakken,
        "personen": personen,
        "overig": [
            {"sleutel": "afgehandeld", "naam": "Afgehandeld", "aantal": afgehandeld},
        ],
        "artikelkant": artikelkant,
        "mensen": mensen,
    }


def _voorstellen(request, qs, omgevingen, bak):
    """De rechterkant voor een bak met voorstellen."""
    qs = qs.select_related("artikel", "artikel__omgeving", "eigenaar", "cluster").annotate(
        _steun=Count("steun", distinct=True)
    )
    pagina = Paginator(qs, PER_PAGINA).get_page(request.GET.get("pagina"))
    keuzes = redacteuren_per_omgeving(omgevingen)
    clusterkeuzes = clusters_van(omgevingen)
    terug = bak
    rijen = []
    for v in pagina.object_list:
        rijen.append(
            {
                "v": v,
                "url": reverse("beheer-voorstel", args=[v.pk]) + "?" + urlencode({"terug": terug}),
                "artikel_url": reverse("admin:kennisbank_artikel_change", args=[v.artikel_id]),
                "eigenaar": diensten.naam_van(v.eigenaar) if v.eigenaar_id else None,
                "van_mij": v.eigenaar_id == request.user.pk,
                "steun": v._steun,
                "nog_niet_geopend": v.is_open and v.eigenaar_id and v.eigenaar_gezien_op is None,
                "dagen": _dagen(v.eigenaar_sinds if v.eigenaar_id else v.ingediend_op),
                "collegas": [(pk, naam) for pk, naam in keuzes.get(v.artikel.omgeving_id, []) if pk != v.eigenaar_id],
                "bakken": ([("algemeen", "Algemeen")] if v.cluster_id else [])
                + [(str(pk), naam) for pk, naam in clusterkeuzes if pk != v.cluster_id]
                if v.cluster_id
                else [(str(pk), naam) for pk, naam in clusterkeuzes],
            }
        )
    return {"rijen": rijen, "pagina": pagina}


def _artikelen(request, qs, sleutel):
    pagina = Paginator(qs, PER_PAGINA).get_page(request.GET.get("pagina"))
    return {
        "artikelen": [
            {
                "titel": a.titel,
                "url": reverse("admin:kennisbank_artikel_change", args=[a.pk]),
                "gewijzigd_op": a.gewijzigd_op,
                "herzien_voor": a.herzien_voor,
                "omgeving": a.omgeving.naam,
            }
            for a in pagina.object_list
        ],
        "pagina": pagina,
    }


def werkplek(request):
    """/beheer/: links de bakken, rechts de inhoud van de gekozen bak."""
    r = rechten(request)
    if not r.is_redacteur:
        return admin.site.index(request)
    omgevingen = sorted(r.redactie_omgevingen)
    namen_omgeving = dict(Omgeving.objects.filter(pk__in=omgevingen).values_list("pk", "naam"))
    menu = _menu(request, omgevingen, namen_omgeving)

    # Liggen er nieuwe voorstellen in je eigen bak (toegewezen door een collega), dan begin je daar.
    eigen = next((p for p in menu["personen"] if p["ik"]), None)
    standaard = eigen["sleutel"] if eigen and eigen["nieuw"] else menu["bakken"][0]["sleutel"]
    bak = request.GET.get("bak") or standaard
    open_qs = Verbetervoorstel.objects.filter(status__in=OPEN, artikel__omgeving_id__in=omgevingen)
    inhoud, titel, uitleg = {}, "", ""
    if bak == "werkvoorraad":  # oude naam (links in e-mails, bladwijzers)
        bak = menu["bakken"][0]["sleutel"]
    if bak == "algemeen" or bak.startswith("algemeen-"):
        qs = open_qs.filter(eigenaar__isnull=True, cluster__isnull=True)
        if bak.startswith("algemeen-"):
            oid = bak.split("-", 1)[1]
            if not oid.isdigit() or int(oid) not in namen_omgeving:
                raise Http404
            qs = qs.filter(artikel__omgeving_id=int(oid))
            titel = f"Algemeen · {namen_omgeving[int(oid)]}"
        else:
            titel = "Algemeen"
        uitleg = (
            "Nieuwe voorstellen bij artikelen zonder cluster of met meer clusters, en wat uit een clusterbak "
            "is verplaatst. Oudste bovenaan."
        )
        inhoud = _voorstellen(request, qs.order_by("ingediend_op"), omgevingen, bak)
    elif bak.startswith("cluster-"):
        cid = bak.split("-", 1)[1]
        clusters = {int(b["sleutel"].split("-", 1)[1]): b["naam"] for b in menu["bakken"] if b["soort"] == "cluster"}
        if not cid.isdigit() or int(cid) not in clusters:
            raise Http404
        titel = clusters[int(cid)]
        uitleg = "Nieuwe voorstellen bij artikelen van dit cluster die nog niemand heeft opgepakt. Oudste bovenaan."
        qs = open_qs.filter(eigenaar__isnull=True, cluster_id=int(cid))
        inhoud = _voorstellen(request, qs.order_by("ingediend_op"), omgevingen, bak)
    elif bak.startswith("u") and bak[1:].isdigit():
        pk = int(bak[1:])
        if pk not in menu["mensen"]:
            raise Http404
        naam = menu["mensen"][pk]
        titel = "Mijn bak" if pk == request.user.pk else f"Bak van {naam}"
        uitleg = "Open voorstellen in deze bak. Langst liggend bovenaan."
        inhoud = _voorstellen(request, open_qs.filter(eigenaar_id=pk).order_by("eigenaar_sinds"), omgevingen, bak)
    elif bak == "afgehandeld":
        titel = "Afgehandeld"
        uitleg = (
            "Het archief: verwerkte, afgewezen en vervallen voorstellen, nieuwste bovenaan. Alleen zichtbaar in "
            "het beheer."
        )
        qs = Verbetervoorstel.objects.filter(status__in=KLAAR, artikel__omgeving_id__in=omgevingen)
        # Zoeken in het archief (ronde 2): op artikel, voorstel, berichten en interne notities.
        zoek = (request.GET.get("q") or "").strip()[:200]
        if zoek:
            treffers = (
                Q(artikel__titel__icontains=zoek)
                | Q(tekst__icontains=zoek)
                | Q(citaat__icontains=zoek)
                | Q(berichten__tekst__icontains=zoek)
                | Q(notities__tekst__icontains=zoek)
            )
            qs = qs.filter(pk__in=Verbetervoorstel.objects.filter(treffers).values("pk"))
        inhoud = _voorstellen(request, qs.order_by("-behandeld_op", "-pk"), omgevingen, bak)
        inhoud["zoek"] = zoek
        inhoud["zoekbaar"] = True
    elif bak == "concepten":
        titel = "Concepten"
        uitleg = (
            "Nieuwe versies van gepubliceerde artikelen waar nog aan wordt gewerkt (medewerkers zien de "
            "gepubliceerde versie), en artikelen die nog nooit zijn gepubliceerd. Laatst gewijzigd bovenaan."
        )
        qs = Artikel.objects.filter(status=Status.CONCEPT, omgeving_id__in=omgevingen).select_related("omgeving")
        inhoud = _artikelen(request, qs.order_by("-gewijzigd_op"), bak)
        inhoud["conceptversies"] = [
            {
                "titel": c.titel,
                "url": reverse("admin:kennisbank_artikel_change", args=[c.artikel_id]),
                "bijgewerkt_op": c.bijgewerkt_op,
                "door": diensten.naam_van(c.bijgewerkt_door),
                "versie": c.artikel.versie,
                "omgeving": c.artikel.omgeving.naam,
            }
            for c in Conceptversie.objects.filter(artikel__omgeving_id__in=omgevingen)
            .select_related("artikel__omgeving", "bijgewerkt_door")
            .order_by("-bijgewerkt_op")
        ]
    elif bak == "ter_inzage":
        titel = "Ter inzage"
        uitleg = (
            "Conceptversies die bij een reviewteam liggen of terugkwamen. Teruggegeven met opmerkingen staat "
            "bovenaan. Publiceren kan pas als je het stuk hebt teruggeroepen of het team heeft gereageerd."
        )
        rijen = {}
        for i in (
            Inzage.objects.filter(artikel__omgeving_id__in=omgevingen, afgesloten=False)
            .select_related("artikel", "artikel__omgeving", "team", "reviewer")
            .order_by("-ronde", "team__naam")
        ):
            a = rijen.setdefault(
                i.artikel_id,
                {
                    "titel": i.artikel.titel,
                    "url": reverse("admin:kennisbank_artikel_change", args=[i.artikel_id]),
                    "omgeving": i.artikel.omgeving.naam,
                    "ronde": i.ronde,
                    "teams": [],
                    "teruggegeven": False,
                },
            )
            if i.ronde != a["ronde"]:
                continue  # alleen de laatste ronde
            a["teams"].append(
                {
                    "naam": i.team.naam,
                    "status": i.status,
                    "label": i.get_status_display().lower(),
                    "sinds": i.gestart_op,
                    "bij": diensten.naam_van(i.reviewer) if i.reviewer_id else None,
                }
            )
            a["teruggegeven"] = a["teruggegeven"] or i.status == InzageStatus.TERUGGEGEVEN
        inhoud = {"inzages": sorted(rijen.values(), key=lambda r: (not r["teruggegeven"], r["titel"].lower()))}
    elif bak == "nakijken":
        titel = "Opnieuw nakijken"
        uitleg = "Gepubliceerde artikelen waarvan de herzieningsdatum is verstreken. Langst over datum bovenaan."
        qs = Artikel.objects.filter(
            status=Status.GEPUBLICEERD, omgeving_id__in=omgevingen, herzien_voor__lt=timezone.localdate()
        ).select_related("omgeving")
        inhoud = _artikelen(request, qs.order_by("herzien_voor"), bak)
    elif bak == "kladversies":
        titel = "Mijn kladversies"
        uitleg = (
            "Werk dat je nog niet hebt opgeslagen. Open het artikel om verder te gaan of de kladversie weg te gooien."
        )
        klad = (
            Kladversie.objects.filter(gebruiker=request.user, afgesloten_op__isnull=True)
            .exclude(velden={})
            .select_related("artikel")
            .order_by("-bijgewerkt_op")
        )
        inhoud = {
            "kladversies": [
                {
                    "titel": k.titel,
                    "bijgewerkt_op": k.bijgewerkt_op,
                    "url": reverse("admin:kennisbank_artikel_change", args=[k.artikel_id])
                    if k.artikel_id
                    else reverse("admin:kennisbank_artikel_add"),
                }
                for k in klad
            ]
        }
    elif bak == "alles":
        titel = "Alle onderdelen"
        uitleg = ""
    else:
        raise Http404

    context = {
        **admin.site.each_context(request),
        "title": titel,
        "werkplek": {
            "menu": menu,
            "meer_omgevingen": len(omgevingen) > 1,
            "lang_dagen": LANG_GELEDEN_DAGEN,
            "gekozen": bak,
            "titel": titel,
            "uitleg": uitleg,
            "inhoud": inhoud,
            "is_alles": bak == "alles",
            "actie_url": reverse("beheer-werkplek-actie"),
            "nieuw_artikel_url": reverse("admin:kennisbank_artikel_add"),
            "nieuw_bericht_url": reverse("admin:kennisbank_bericht_add"),
            "url": werkplek_url,
        },
        "app_list": admin.site.get_app_list(request) if bak == "alles" else [],
    }
    return TemplateResponse(request, "admin/kennisbank/werkplek.html", context)


def werkplek_actie(request):
    """POST vanuit de werkplek: een voorstel oppakken, overnemen, toewijzen of terugleggen."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    r = rechten(request)
    terug = request.POST.get("terug") or None
    v = Verbetervoorstel.objects.filter(
        pk=request.POST.get("voorstel") if (request.POST.get("voorstel") or "").isdigit() else None,
        artikel__omgeving_id__in=r.redactie_omgevingen,  # 404: verraad niet dat het bestaat
    ).first()
    if v is None:
        raise Http404
    actie = request.POST.get("actie")
    # Review 1.20.1, bevinding 9: is de eigenaar veranderd sinds dit scherm werd geladen, dan niets doen
    # en zeggen bij wie het intussen ligt. Een bewuste "Overnemen" (met de eigenaar in beeld) kan daarna.
    if "geladen_eigenaar" in request.POST and actie in ("oppakken", "terugleggen", "toewijzen"):
        if (request.POST.get("geladen_eigenaar") or "") != str(v.eigenaar_id or ""):
            if v.eigenaar_id == request.user.pk:
                messages.info(request, f"Het voorstel bij '{v.artikel.titel}' lag al bij jou.")
            elif v.eigenaar_id:
                messages.warning(
                    request,
                    f"{diensten.naam_van(v.eigenaar)} heeft het voorstel bij '{v.artikel.titel}' intussen "
                    "opgepakt. Er is niets veranderd. Wil je het toch overnemen? Klik dan nog eens.",
                )
            else:
                messages.warning(
                    request,
                    f"Het voorstel bij '{v.artikel.titel}' ligt intussen weer in de werkvoorraad. "
                    "Er is niets veranderd.",
                )
            return _terug_naar(request, v, terug)
    if actie == "oppakken":
        naar = request.user
    elif actie == "terugleggen":
        naar = None
    elif actie == "naar_bak":
        # Zonder keuze stuurt de browser het veld niet mee (de eerste optie is uitgeschakeld). Vroeger
        # verhuisde het voorstel dan stilletjes naar Algemeen (functionele review 11 november, B4).
        keuze = request.POST.get("cluster") or ""
        if not keuze:
            messages.warning(request, "Kies eerst een bak om het voorstel naartoe te verplaatsen.")
            return _terug_naar(request, v, terug)
        cluster = None
        if keuze != "algemeen":
            toegestaan = dict(clusters_van(sorted(r.redactie_omgevingen)))
            if not keuze.isdigit() or int(keuze) not in toegestaan:
                raise Http404
            cluster = Cluster.objects.get(pk=int(keuze))
        try:
            diensten.voorstel_naar_clusterbak(v, request.user, cluster)
        except diensten.VoorstelFout as e:
            messages.warning(request, str(e))
            return _terug_naar(request, v, terug)
        model_admin = admin.site._registry[Verbetervoorstel]
        waar = cluster.naam if cluster else "Algemeen"
        model_admin.log_change(request, v, f"Verplaatst naar de bak {waar}.")
        messages.success(request, f"Het voorstel bij '{v.artikel.titel}' ligt nu in de bak {waar}.")
        return _terug_naar(request, v, terug)
    elif actie == "toewijzen":
        keuze = request.POST.get("naar") or ""
        naar = diensten.redacteuren_van(v.artikel.omgeving_id).filter(pk=keuze).first() if keuze.isdigit() else None
        if naar is None:
            messages.warning(request, "Kies eerst een collega om het voorstel aan toe te wijzen.")
            return _terug_naar(request, v, terug)
    else:
        raise Http404
    model_admin = admin.site._registry[Verbetervoorstel]
    werkwoord = {"oppakken": "opgepakt", "terugleggen": "teruggelegd", "toewijzen": "toegewezen"}[actie]
    model_admin._verplaats(request, Verbetervoorstel.objects.filter(pk=v.pk), naar, werkwoord)
    return _terug_naar(request, v, terug)


def _terug_naar(request, v, terug):
    """Terug naar waar de actie vandaan kwam: de werkplek, of het behandelscherm van het voorstel."""
    if request.POST.get("na") == "scherm":
        url = reverse("beheer-voorstel", args=[v.pk])
        return redirect(f"{url}?{urlencode({'terug': terug})}" if terug else url)
    return redirect(werkplek_url(terug))


# Oude naam, voor wie nog naar de startpagina verwijst.
startpagina = werkplek
