"""REST-API (versie 1). Wordt gebruikt door de eigen frontend en door koppelingen (zaaksysteem).

Documentatie: /api/schema/ (OpenAPI) en /api/docs/ (interactief).
"""

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_field, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from . import diensten
from .assistent import beantwoord
from .models import (
    MAX_VOORSTELBERICHT,
    Artikel,
    ArtikelVersie,
    AssistentTelling,
    Bericht,
    Cluster,
    Favoriet,
    Omgeving,
    RecentBezocht,
    Soort,
    Tag,
    Verbetervoorstel,
    VoorstelBericht,
    VoorstelStatus,
    WeergaveTelling,
    Zaaktype,
    ZoekTelling,
)
from .rechten import rechten
from .zoeken import zoek_artikelen

# --- Serializers ----------------------------------------------------------------------


class ArtikelKortSerializer(serializers.ModelSerializer):
    clusters = serializers.SlugRelatedField(many=True, read_only=True, slug_field="naam")
    tags = serializers.SlugRelatedField(many=True, read_only=True, slug_field="naam")
    zaaktypen = serializers.SlugRelatedField(many=True, read_only=True, slug_field="code")
    omgeving = serializers.SlugRelatedField(read_only=True, slug_field="slug")
    url = serializers.CharField(source="get_absolute_url", read_only=True)
    wijziging = serializers.SerializerMethodField()

    class Meta:
        model = Artikel
        fields = [
            "id",
            "slug",
            "titel",
            "samenvatting",
            "soort",
            "status",
            "omgeving",
            "clusters",
            "tags",
            "zaaktypen",
            "versie",
            "gepubliceerd_op",
            "eigenaar",
            "url",
            "wijziging",
        ]

    def get_wijziging(self, obj) -> dict | None:
        """De nog niet afgevinkte inhoudelijke wijzigingen voor de huidige gebruiker.

        {versie, datum, toelichting, eerdere: [{versie, datum, toelichting}, ...]} — `eerdere` bevat de
        wijzigingen die daarvoor zijn gemist, nieuwste eerst, of is leeg.
        """
        wijzigingen = self.context.get("wijzigingen")
        if wijzigingen is None:
            request = self.context.get("request")
            wijzigingen = diensten.wijzigingen_voor(request.user if request else None, [obj])
        return wijzigingen.get(obj.pk)


class ArtikelSerializer(ArtikelKortSerializer):
    blokken = serializers.SerializerMethodField()
    gerelateerd = serializers.SerializerMethodField()
    bewerk_url = serializers.SerializerMethodField()

    class Meta(ArtikelKortSerializer.Meta):
        fields = ArtikelKortSerializer.Meta.fields + ["blokken", "gerelateerd", "bewerk_url"]

    def get_blokken(self, obj) -> list[dict]:
        """De tekst in leesvolgorde: vrije tekst (altijd zichtbaar) en secties (in-/uitklapbaar)."""
        from .inhoud import blokken

        return blokken(obj.inhoud)

    def get_gerelateerd(self, obj) -> list[dict]:
        r = self.context["rechten"]
        tags = obj.tags.all()
        qs = (
            r.gepubliceerde_artikelen()
            .filter(tags__in=tags)
            .exclude(pk=obj.pk)
            .annotate(overlap=Count("tags"))
            .order_by("-overlap", "titel")[:3]
        )
        return [{"id": a.pk, "slug": a.slug, "titel": a.titel, "url": a.get_absolute_url()} for a in qs]

    def get_bewerk_url(self, obj) -> str | None:
        if self.context["rechten"].mag_redigeren(obj):
            return f"/beheer/kennisbank/artikel/{obj.pk}/change/"
        return None


class VoorstelBerichtSerializer(serializers.ModelSerializer):
    """Eén bericht in het gesprek over een verbetervoorstel."""

    naam = serializers.CharField(read_only=True)

    class Meta:
        model = VoorstelBericht
        fields = ["id", "naam", "van_redactie", "tekst", "moment"]
        read_only_fields = fields


class VoorstelSerializer(serializers.ModelSerializer):
    artikel = serializers.PrimaryKeyRelatedField(queryset=Artikel.objects.all())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Alleen artikelen die de gebruiker mag lezen zijn geldig. Een onzichtbaar artikel geeft zo dezelfde
        # fout als een onbestaand artikel, en verraadt dus niet dat het bestaat.
        r = (self.context or {}).get("rechten")
        if r is not None:
            self.fields["artikel"].queryset = r.artikelen()

    artikel_url = serializers.CharField(source="artikel.get_absolute_url", read_only=True)
    artikel_titel = serializers.CharField(source="artikel.titel", read_only=True)
    ingediend_door = serializers.SerializerMethodField()
    van_mij = serializers.SerializerMethodField()
    berichten = serializers.SerializerMethodField()
    ongelezen = serializers.SerializerMethodField()

    class Meta:
        model = Verbetervoorstel
        fields = [
            "id",
            "artikel",
            "artikel_titel",
            "artikel_url",
            "artikel_versie",
            "citaat",
            "tekst",
            "status",
            "terugkoppeling",
            "ingediend_op",
            "ingediend_door",
            "van_mij",
            "behandeld_op",
            "berichten",
            "ongelezen",
        ]
        read_only_fields = ["artikel_versie", "status", "terugkoppeling", "ingediend_op", "behandeld_op"]

    @extend_schema_field(VoorstelBerichtSerializer(many=True))
    def get_berichten(self, obj):
        """Het hele gesprek, oudste eerst."""
        return VoorstelBerichtSerializer(obj.berichten.all(), many=True).data

    def get_ongelezen(self, obj) -> int:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return 0
        return diensten.voorstel_ongelezen(obj, request.user)

    def get_ingediend_door(self, obj) -> str:
        if not obj.ingediend_door:
            return "Onbekend (geanonimiseerd)"
        return obj.ingediend_door.get_full_name() or obj.ingediend_door.email or "Collega"

    def get_van_mij(self, obj) -> bool:
        return obj.ingediend_door_id == self.context["request"].user.pk

    def validate_tekst(self, value):
        if not value.strip():
            raise serializers.ValidationError("Beschrijf wat er beter kan.")
        return value.strip()[:4000]

    def validate_citaat(self, value):
        return (value or "").strip()[:2000]


class AssistentThrottle(UserRateThrottle):
    scope = "assistent"


class VoorstelThrottle(UserRateThrottle):
    """Begrenst alleen het indienen, niet het bekijken."""

    scope = "voorstel"

    def allow_request(self, request, view):
        if request.method != "POST":
            return True
        return super().allow_request(request, view)


# --- Hulpfuncties ---------------------------------------------------------------------


def _artikelen_voor(request):
    return rechten(request).artikelen().select_related("omgeving").prefetch_related("clusters", "tags", "zaaktypen")


def _filter(qs, params):
    if cluster := params.get("cluster"):
        # Artikelen zonder cluster gelden voor alle clusters.
        qs = qs.filter(Q(clusters__naam=cluster) | Q(clusters__isnull=True))
    if soort := params.get("soort"):
        qs = qs.filter(soort=soort)
    for tag in params.getlist("tag"):
        qs = qs.filter(tags__naam=tag)
    if zaaktype := params.get("zaaktype"):
        qs = qs.filter(zaaktypen__code=zaaktype)
    if omgeving := params.get("omgeving"):
        qs = qs.filter(omgeving__slug=omgeving)
    if status_ := params.get("status"):
        qs = qs.filter(status=status_)
    return qs.distinct()


def _artikel_of_404(request, pk):
    artikel = get_object_or_404(
        Artikel.objects.select_related("omgeving").prefetch_related("clusters", "tags", "zaaktypen"),
        pk=pk,
    )
    if not rechten(request).mag_lezen(artikel):
        # 404 in plaats van 403: verraad niet dat het artikel bestaat.
        from django.http import Http404

        raise Http404
    return artikel


def _ctx(request, artikelen=None):
    ctx = {"request": request, "rechten": rechten(request)}
    if artikelen is not None:
        ctx["wijzigingen"] = diensten.wijzigingen_voor(request.user, artikelen)
    return ctx


# --- Endpoints ------------------------------------------------------------------------


class IkWijzigenSerializer(serializers.Serializer):
    onboarding = serializers.BooleanField(required=False)
    mail_bij_favorieten = serializers.BooleanField(required=False)


@extend_schema(
    summary="Huidige gebruiker (GET) en voorkeuren wijzigen (PATCH)",
    request=IkWijzigenSerializer,
    responses=inline_serializer(
        "Ik",
        {
            "naam": serializers.CharField(),
            "is_redacteur": serializers.BooleanField(),
            "onboarding": serializers.BooleanField(),
            "mail_bij_favorieten": serializers.BooleanField(),
            "favorieten_mail": serializers.CharField(help_text="KB_FAVORIETEN_MAIL: gebundeld, direct of uit"),
            "nieuws_gezien_op": serializers.DateTimeField(allow_null=True),
            "nieuws_ongelezen": serializers.IntegerField(),
            "favorieten": serializers.ListField(child=serializers.IntegerField(), help_text="Artikel-id's"),
            "recent": inline_serializer(
                "RecentBezocht",
                {"id": serializers.IntegerField(), "bezocht_op": serializers.DateTimeField()},
                many=True,
            ),
            "recent_max": serializers.IntegerField(),
            "beheer_url": serializers.CharField(allow_null=True),
            "uitlog_url": serializers.CharField(),
            "ai_aan": serializers.BooleanField(),
            "app_naam": serializers.CharField(),
        },
    ),
)
@api_view(["GET", "PATCH"])
def ik(request):
    p = diensten.profiel(request.user)
    if request.method == "PATCH":
        s = IkWijzigenSerializer(data=request.data)
        s.is_valid(raise_exception=True)  # 400 {"onboarding": [...]} bij onzin
        velden = [veld for veld in ("onboarding", "mail_bij_favorieten") if veld in s.validated_data]
        for veld in velden:
            setattr(p, veld, s.validated_data[veld])
        if velden:
            p.save(update_fields=velden)
    r = rechten(request)
    berichten = diensten.berichten_voor(request.user, r.leesbare_omgevingen)
    nieuws_ongelezen = (
        berichten.filter(gepubliceerd_op__gt=p.nieuws_gezien_op).count() if p.nieuws_gezien_op else berichten.count()
    )
    zichtbaar = r.gepubliceerde_artikelen()
    recent = (
        RecentBezocht.objects.filter(gebruiker=request.user, artikel__in=zichtbaar)
        .select_related("artikel")
        .order_by("-bezocht_op")
    )
    return Response(
        {
            "naam": request.user.get_full_name() or request.user.get_username(),
            "is_redacteur": r.is_redacteur,
            "onboarding": p.onboarding,
            "mail_bij_favorieten": p.mail_bij_favorieten,
            "favorieten_mail": settings.KB_FAVORIETEN_MAIL,
            "nieuws_gezien_op": p.nieuws_gezien_op,
            "nieuws_ongelezen": nieuws_ongelezen,
            "favorieten": list(
                Favoriet.objects.filter(gebruiker=request.user, artikel__in=zichtbaar).values_list(
                    "artikel_id", flat=True
                )
            ),
            "recent": [{"id": x.artikel_id, "bezocht_op": x.bezocht_op} for x in recent],
            "recent_max": settings.KB_RECENT_MAX,
            "beheer_url": "/beheer/" if request.user.is_staff else None,
            "uitlog_url": "/oidc/logout/" if settings.KB_AUTH_MODUS == "oidc" else "/uitloggen/",
            "ai_aan": settings.KB_AI_PROVIDER != "uit",
            "app_naam": settings.KB_APP_NAAM,
            # Zonder toegangsregel ziet de kennisbank er precies zo uit als een lege kennisbank. Dat
            # is de meest voorkomende melding bij invoering, en de minst herkenbare; daarom zegt de
            # frontend het nu met zoveel woorden.
            "geen_toegang": not r.leesbare_omgevingen and not request.user.is_superuser,
            "contact": settings.KB_CONTACT,
        }
    )


@extend_schema(
    summary="Keuzelijsten voor filters (clusters, soorten, tags, zaaktypen)",
    responses=inline_serializer(
        "Keuzelijsten",
        {
            "clusters": serializers.ListField(child=serializers.CharField()),
            "soorten": inline_serializer(
                "Soort", {"waarde": serializers.CharField(), "label": serializers.CharField()}, many=True
            ),
            "tags": serializers.ListField(child=serializers.CharField()),
            "zaaktypen": inline_serializer(
                "ZaaktypeKeuze", {"code": serializers.CharField(), "naam": serializers.CharField()}, many=True
            ),
        },
    ),
)
@api_view(["GET"])
def keuzelijsten(request):
    zichtbaar = rechten(request).gepubliceerde_artikelen()
    return Response(
        {
            "clusters": list(Cluster.objects.values_list("naam", flat=True)),
            "soorten": [{"waarde": w, "label": label} for w, label in Soort.choices],
            "tags": list(Tag.objects.filter(artikel__in=zichtbaar).distinct().values_list("naam", flat=True)),
            "zaaktypen": list(Zaaktype.objects.filter(artikel__in=zichtbaar).distinct().values("code", "naam")),
        }
    )


def _gezochte_omgevingen(request):
    """De omgevingen waarin deze zoekopdracht zocht: de omgevingsfilter als die is gezet, anders alle leesbare."""
    filter_slug = request.query_params.get("omgeving")
    leesbaar = rechten(request).leesbare_omgevingen
    if filter_slug:
        return set(Omgeving.objects.filter(slug=filter_slug, id__in=leesbaar).values_list("id", flat=True))
    return leesbaar


@extend_schema(
    summary="Artikelen zoeken en filteren",
    parameters=[
        OpenApiParameter("q", str, description="Zoektekst"),
        OpenApiParameter("registreer", str, description="'1' = zoekterm meetellen in de statistiek"),
        OpenApiParameter("cluster", str),
        OpenApiParameter("soort", str),
        OpenApiParameter("tag", str, many=True),
        OpenApiParameter("zaaktype", str),
        OpenApiParameter("omgeving", str),
        OpenApiParameter("status", str),
    ],
    responses=ArtikelKortSerializer(many=True),
)
@api_view(["GET"])
def artikelen(request):
    qs = _filter(_artikelen_voor(request), request.query_params)
    q = request.query_params.get("q", "").strip()
    if q:
        resultaat = zoek_artikelen(qs, q)
        # Alleen meetellen in de statistiek als de client dat vraagt (niet bij elke toetsaanslag).
        if request.query_params.get("registreer") == "1":
            diensten.registreer_zoekopdracht(q, len(resultaat), _gezochte_omgevingen(request))
    else:
        resultaat = qs.order_by("titel")
    resultaat = list(resultaat)
    return Response(ArtikelKortSerializer(resultaat, many=True, context=_ctx(request, resultaat)).data)


@extend_schema(summary="Eén artikel met secties", responses=ArtikelSerializer)
@api_view(["GET"])
def artikel(request, pk):
    a = _artikel_of_404(request, pk)
    return Response(ArtikelSerializer(a, context=_ctx(request)).data)


@extend_schema(summary="Weergave registreren (statistiek en 'recent bezocht')", request=None, responses={204: None})
@api_view(["POST"])
def weergave(request, pk):
    a = _artikel_of_404(request, pk)
    diensten.registreer_weergave(request.user, a)
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(summary="Favoriet aan (PUT) of uit (DELETE)", request=None, responses={204: None})
@api_view(["PUT", "DELETE"])
def favoriet(request, pk):
    a = _artikel_of_404(request, pk)
    diensten.zet_favoriet(request.user, a, request.method == "PUT")
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    summary="Versiegeschiedenis van een artikel (redacteuren)",
    responses=inline_serializer(
        "ArtikelVersie",
        {
            "versie": serializers.IntegerField(),
            "gepubliceerd_op": serializers.DateTimeField(),
            "gepubliceerd_door": serializers.CharField(allow_null=True),
            "toelichting": serializers.CharField(),
            "kleine_correctie": serializers.BooleanField(),
            "inhoud": serializers.DictField(help_text="Momentopname: {formaat, titel, samenvatting, inhoud, ...}"),
        },
        many=True,
    ),
)
@api_view(["GET"])
def versies(request, pk):
    a = _artikel_of_404(request, pk)
    if not rechten(request).mag_redigeren(a):
        raise PermissionDenied
    return Response(
        [
            {
                "versie": v.versie,
                "gepubliceerd_op": v.gepubliceerd_op,
                "gepubliceerd_door": v.gepubliceerd_door.get_full_name() if v.gepubliceerd_door else None,
                "toelichting": v.toelichting,
                "kleine_correctie": v.kleine_correctie,
                "inhoud": v.inhoud,
            }
            for v in ArtikelVersie.objects.filter(artikel=a).select_related("gepubliceerd_door")
        ]
    )


class VoorstelBehandelSerializer(serializers.Serializer):
    """PATCH: de status van een voorstel.

    `terugkoppeling` blijft hier geaccepteerd voor bestaande koppelingen, maar wordt verwerkt als een
    bericht aan de indiener — niet meer als los veld. Zo is er één schrijver van dat veld
    (`diensten.voorstelbericht_toevoegen`) en kan het niet stil worden overschreven.
    """

    status = serializers.ChoiceField(choices=VoorstelStatus.choices, required=False)
    terugkoppeling = serializers.CharField(
        allow_blank=True, max_length=MAX_VOORSTELBERICHT, required=False, trim_whitespace=True
    )


@extend_schema(
    summary="Verbetervoorstellen: lijst (GET) of indienen (POST)",
    request=VoorstelSerializer,
    responses=VoorstelSerializer(many=True),
)
@api_view(["GET", "POST"])
@throttle_classes([VoorstelThrottle])
def voorstellen(request):
    r = rechten(request)
    if request.method == "POST":
        s = VoorstelSerializer(data=request.data, context=_ctx(request))
        s.is_valid(raise_exception=True)
        a = s.validated_data["artikel"]
        if not r.mag_lezen(a):
            raise PermissionDenied
        v = s.save(ingediend_door=request.user, artikel_versie=a.versie)
        diensten.meld_nieuw_voorstel(v)
        return Response(VoorstelSerializer(v, context=_ctx(request)).data, status=status.HTTP_201_CREATED)

    # Lezers zien hun eigen voorstellen; redacteuren alle voorstellen in hun omgeving(en).
    qs = Verbetervoorstel.objects.select_related("artikel", "ingediend_door").prefetch_related("berichten__auteur")
    qs = qs.filter(Q(ingediend_door=request.user) | Q(artikel__omgeving_id__in=r.redactie_omgevingen))
    gevraagd = request.GET.get("status")
    if gevraagd == "open":
        qs = qs.filter(status__in=[VoorstelStatus.NIEUW, VoorstelStatus.IN_BEHANDELING])
    elif gevraagd in dict(VoorstelStatus.choices):
        qs = qs.filter(status=gevraagd)
    return Response(VoorstelSerializer(qs, many=True, context=_ctx(request)).data)


@extend_schema(
    summary="Verbetervoorstel behandelen (redacteuren)",
    request=VoorstelBehandelSerializer,
    responses=VoorstelSerializer,
)
@api_view(["PATCH"])
def voorstel(request, pk):
    v = get_object_or_404(
        Verbetervoorstel.objects.select_related("artikel", "ingediend_door"),
        pk=pk,
        artikel__omgeving_id__in=rechten(request).redactie_omgevingen,  # 404, verraad niet dat het bestaat
    )
    s = VoorstelBehandelSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    nieuwe_status = s.validated_data.get("status", v.status)
    if nieuwe_status != v.status:
        v.status = nieuwe_status
        v.behandeld_door = request.user
        v.behandeld_op = timezone.now()
        v.save(update_fields=["status", "behandeld_door", "behandeld_op"])
    # Een meegestuurde terugkoppeling wordt een bericht aan de indiener; daar zit de melding en de
    # e-mail al aan vast. Dubbel versturen voorkomen we door hem over te slaan als hij niet verandert.
    tekst = (s.validated_data.get("terugkoppeling") or "").strip()
    if tekst and tekst != v.terugkoppeling:
        diensten.voorstelbericht_toevoegen(v, request.user, tekst, van_redactie=True)
        v.refresh_from_db()
    return Response(VoorstelSerializer(v, context=_ctx(request)).data)


class VoorstelBerichtInSerializer(serializers.Serializer):
    """Een terugkoppeling of tussentijdse update van procesmanagement aan de indiener.

    Bewust een serializer en geen handmatige controle op `request.data`: die laat het type, de
    lengtegrens en nul-bytes allemaal door, en een nul-byte in een tekstkolom is in PostgreSQL een
    harde fout. Dit was het enige schrijvende endpoint dat de invoer rauw verwerkte.
    """

    tekst = serializers.CharField(max_length=MAX_VOORSTELBERICHT, trim_whitespace=True)


@extend_schema(
    summary="Terugkoppeling of update sturen bij een verbetervoorstel (redacteuren)",
    description="Alleen redacteuren van de omgeving van het artikel. De indiener krijgt er een melding "
    "en een e-mail van. Bewust eenrichtingsverkeer: de indiener kan niet terugschrijven.",
    request=VoorstelBerichtInSerializer,
    responses=VoorstelSerializer,
)
@api_view(["POST"])
@throttle_classes([VoorstelThrottle])
def voorstel_bericht(request, pk):
    v = _voorstel_voor(request, pk)
    if v.artikel.omgeving_id not in rechten(request).redactie_omgevingen:
        # De indiener mag zijn eigen voorstel zien, maar er niet in schrijven. Zie VoorstelBericht.
        raise PermissionDenied("Alleen procesmanagement kan een bericht bij een voorstel plaatsen.")
    s = VoorstelBerichtInSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    diensten.voorstelbericht_toevoegen(v, request.user, s.validated_data["tekst"], van_redactie=True)
    v.refresh_from_db()
    return Response(VoorstelSerializer(v, context=_ctx(request)).data, status=status.HTTP_201_CREATED)


@extend_schema(
    summary="Gesprek over een verbetervoorstel als gelezen markeren",
    request=None,
    responses={204: None},
)
@api_view(["POST"])
def voorstel_gelezen(request, pk):
    diensten.voorstel_gelezen(_voorstel_voor(request, pk), request.user)
    return Response(status=status.HTTP_204_NO_CONTENT)


def _voorstel_voor(request, pk):
    """Het voorstel, als deze gebruiker de indiener is of redacteur in de omgeving van het artikel."""
    r = rechten(request)
    return get_object_or_404(
        Verbetervoorstel.objects.select_related("artikel", "ingediend_door", "behandeld_door").filter(
            Q(ingediend_door=request.user) | Q(artikel__omgeving_id__in=r.redactie_omgevingen)
        ),
        pk=pk,
    )


@extend_schema(
    summary="Gebruiksstatistieken (redacteuren). Geaggregeerd, zonder persoonsgegevens.",
    parameters=[OpenApiParameter("dagen", int, description="Periode, standaard 30")],
    responses=inline_serializer(
        "Statistieken",
        {
            "dagen": serializers.IntegerField(),
            "totaal_weergaven": serializers.IntegerField(),
            "artikelen": inline_serializer(
                "ArtikelStatistiek",
                {
                    "id": serializers.IntegerField(),
                    "slug": serializers.CharField(),
                    "url": serializers.CharField(),
                    "titel": serializers.CharField(),
                    "soort": serializers.CharField(),
                    "status": serializers.CharField(),
                    "weergaven": serializers.IntegerField(),
                    "voorstellen": serializers.IntegerField(),
                },
                many=True,
            ),
            "aantal_artikelen": serializers.IntegerField(),
            "voorstellen_totaal": serializers.IntegerField(),
            "voorstellen_open": serializers.IntegerField(),
            "voorstellen_verwerkt": serializers.IntegerField(),
            "zoektermen": inline_serializer(
                "Zoekterm",
                {
                    "term": serializers.CharField(),
                    "aantal": serializers.IntegerField(),
                    "zonder_resultaat": serializers.IntegerField(),
                },
                many=True,
            ),
            "zoektermen_zonder_resultaat": inline_serializer(
                "ZoektermZonderResultaat",
                {"term": serializers.CharField(), "aantal": serializers.IntegerField()},
                many=True,
            ),
            "assistent_vragen": serializers.IntegerField(),
            "assistent_zonder_bron": serializers.IntegerField(),
        },
    ),
)
@api_view(["GET"])
def statistieken(request):
    r = rechten(request)
    if not r.is_redacteur:
        raise PermissionDenied
    try:
        dagen = max(1, min(int(request.query_params.get("dagen", 30)), 3650))
    except ValueError as e:
        raise serializers.ValidationError({"dagen": "Geef een geheel aantal dagen op."}) from e
    sinds = timezone.localdate() - timezone.timedelta(days=dagen - 1)
    arts = Artikel.objects.filter(omgeving_id__in=r.redactie_omgevingen)
    weergaven = dict(
        WeergaveTelling.objects.filter(artikel__in=arts, datum__gte=sinds)
        .values_list("artikel_id")
        .annotate(n=Sum("aantal"))
    )
    voorst = dict(Verbetervoorstel.objects.filter(artikel__in=arts).values_list("artikel_id").annotate(n=Count("id")))
    rijen = sorted(
        (
            {
                "id": a.pk,
                "slug": a.slug,
                "url": a.get_absolute_url(),
                "titel": a.titel,
                "soort": a.soort,
                "status": a.status,
                "weergaven": weergaven.get(a.pk, 0),
                "voorstellen": voorst.get(a.pk, 0),
            }
            for a in arts
        ),
        key=lambda x: (-x["weergaven"], x["titel"]),
    )
    termen = (
        ZoekTelling.objects.filter(datum__gte=sinds, omgeving_id__in=r.redactie_omgevingen)
        .values("term")
        .annotate(aantal=Sum("aantal"), zonder_resultaat=Sum("zonder_resultaat"))
        .order_by("-aantal")[:15]
    )
    zonder = (
        ZoekTelling.objects.filter(datum__gte=sinds, zonder_resultaat__gt=0, omgeving_id__in=r.redactie_omgevingen)
        .values("term")
        .annotate(aantal=Sum("zonder_resultaat"))
        .order_by("-aantal")[:10]
    )
    vs = Verbetervoorstel.objects.filter(artikel__in=arts)
    ass = AssistentTelling.objects.filter(datum__gte=sinds, omgeving_id__in=r.redactie_omgevingen).aggregate(
        v=Sum("vragen"), z=Sum("zonder_bron")
    )
    return Response(
        {
            "dagen": dagen,
            "totaal_weergaven": sum(weergaven.values()),
            "artikelen": rijen,
            "aantal_artikelen": arts.filter(status="gepubliceerd").count(),
            "voorstellen_totaal": vs.count(),
            "voorstellen_open": vs.filter(status__in=["nieuw", "in_behandeling"]).count(),
            "voorstellen_verwerkt": vs.filter(status="verwerkt").count(),
            "zoektermen": list(termen),
            "zoektermen_zonder_resultaat": list(zonder),
            "assistent_vragen": ass["v"] or 0,
            "assistent_zonder_bron": ass["z"] or 0,
        }
    )


class AssistentVraagSerializer(serializers.Serializer):
    vraag = serializers.CharField(max_length=1000)
    zaaktype = serializers.CharField(required=False, allow_blank=True, max_length=80)


@extend_schema(
    summary="Vraag stellen aan de assistent",
    request=AssistentVraagSerializer,
    responses=inline_serializer(
        "AssistentAntwoord",
        {
            "html": serializers.CharField(),
            "bronnen": serializers.ListField(),
            "modus": serializers.CharField(),
            "melding": serializers.CharField(),
        },
    ),
)
@api_view(["POST"])
@throttle_classes([AssistentThrottle])
def assistent(request):
    s = AssistentVraagSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    a = beantwoord(
        s.validated_data["vraag"],
        rechten(request).gepubliceerde_artikelen(),
        zaaktype=s.validated_data.get("zaaktype") or None,
        omgevingen=rechten(request).leesbare_omgevingen,
    )
    return Response({"html": a.html, "bronnen": a.bronnen, "modus": a.modus, "melding": a.melding})


@extend_schema(
    summary="Artikelen bij een zaaktype (voor het zaaksysteem)",
    description="Geeft de gepubliceerde artikelen die aan dit zaaktype zijn gekoppeld. "
    "Gebruik `code` zoals het zaaksysteem het zaaktype identificeert.",
    responses=ArtikelKortSerializer(many=True),
)
@api_view(["GET"])
def zaaktype_artikelen(request, code):
    """De artikelen bij een zaaktype, de meest geraadpleegde eerst.

    Alfabetisch sorteren werkt prima bij tien artikelen, maar een breed zaaktype als "Melding" kan er
    honderd hebben. Dan is een alfabetische muur naast een zaak geen hulp. Daarom hier de volgorde van
    het gebruik in de laatste 90 dagen; de frontend toont er een handvol van met een uitklap.
    """
    qs = rechten(request).gepubliceerde_artikelen().filter(zaaktypen__code=code).distinct()
    qs = list(qs.select_related("omgeving").prefetch_related("clusters", "tags", "zaaktypen"))
    sinds = timezone.now().date() - timezone.timedelta(days=90)
    weergaven = dict(
        WeergaveTelling.objects.filter(artikel__in=qs, datum__gte=sinds)
        .values_list("artikel")
        .annotate(n=Sum("aantal"))
    )
    qs.sort(key=lambda a: (-weergaven.get(a.pk, 0), a.titel.lower()))
    return Response(ArtikelKortSerializer(qs, many=True, context=_ctx(request, qs)).data)


# --- Wijzigingsmeldingen en nieuws ------------------------------------------------------


class GezienSerializer(serializers.Serializer):
    versie = serializers.IntegerField(
        required=False, min_value=1, help_text="De versie die de gebruiker te zien kreeg (standaard: de huidige)."
    )


@extend_schema(
    summary="Wijzigingsmelding van een artikel afvinken ('Ik snap het')",
    description="Daarna verschijnt de melding pas weer bij een volgende inhoudelijke wijziging. Stuur de getoonde "
    "`versie` mee: een versie die intussen is gepubliceerd blijft dan als melding staan.",
    request=GezienSerializer,
    responses={204: None},
)
@api_view(["POST"])
def wijziging_gezien(request, pk):
    a = _artikel_of_404(request, pk)
    s = GezienSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    diensten.markeer_gezien(request.user, [a], tot_versie=s.validated_data.get("versie"))
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    summary="Alle openstaande wijzigingsmeldingen afvinken ('Alles gezien')",
    request=None,
    responses=inline_serializer("AllesGezien", {"aantal": serializers.IntegerField()}),
)
@api_view(["POST"])
def wijzigingen_gezien(request):
    zichtbaar = rechten(request).artikelen()
    open_ids = diensten.wijzigingen_voor(request.user, zichtbaar)
    n = diensten.markeer_gezien(request.user, zichtbaar.filter(pk__in=open_ids))
    return Response({"aantal": n})


class BerichtSerializer(serializers.ModelSerializer):
    omgeving = serializers.SlugRelatedField(read_only=True, slug_field="slug")
    tekst = serializers.SerializerMethodField()
    auteur = serializers.SerializerMethodField()
    artikelen = serializers.SerializerMethodField()
    verlopen = serializers.SerializerMethodField()
    bewerk_url = serializers.SerializerMethodField()

    class Meta:
        model = Bericht
        fields = [
            "id",
            "titel",
            "tekst",
            "omgeving",
            "artikelen",
            "vastgepind",
            "gepubliceerd_op",
            "verloopt_op",
            "verlopen",
            "auteur",
            "bewerk_url",
        ]

    def get_tekst(self, obj) -> str:
        """Net als artikelinhoud ook bij tonen opgeschoond (tweede linie, naast de opschoning bij opslaan)."""
        from .inhoud import schoon

        return schoon(obj.tekst)

    def get_auteur(self, obj) -> str:
        return (obj.auteur.get_full_name() or obj.auteur.get_username()) if obj.auteur else "Procesmanagement"

    def get_artikelen(self, obj) -> list[dict]:
        r = self.context["rechten"]
        return [
            {"id": a.pk, "titel": a.titel, "url": a.get_absolute_url()} for a in obj.artikelen.all() if r.mag_lezen(a)
        ]

    def get_verlopen(self, obj) -> bool:
        return bool(obj.verloopt_op and obj.verloopt_op <= timezone.now())

    def get_bewerk_url(self, obj) -> str | None:
        if obj.omgeving_id in self.context["rechten"].redactie_omgevingen:
            return f"/beheer/kennisbank/bericht/{obj.pk}/change/"
        return None


@extend_schema(
    summary="Nieuwsberichten in de omgeving(en) van de gebruiker",
    description="Gepubliceerde berichten, vastgepinde eerst en dan op datum (nieuwste bovenaan). "
    "Verlopen berichten staan er ook in, met `verlopen: true`.",
    responses=BerichtSerializer(many=True),
)
@api_view(["GET"])
def berichten(request):
    r = rechten(request)
    qs = diensten.berichten_voor(request.user, r.leesbare_omgevingen)
    return Response(BerichtSerializer(qs, many=True, context=_ctx(request)).data)


@extend_schema(
    summary="Nieuws als gelezen markeren (de teller 'ongelezen' gaat naar nul)",
    request=None,
    responses={204: None},
)
@api_view(["POST"])
def berichten_gezien(request):
    p = diensten.profiel(request.user)
    p.nieuws_gezien_op = timezone.now()
    p.save(update_fields=["nieuws_gezien_op"])
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(exclude=True)
@api_view(["GET"])
@permission_classes([AllowAny])
def niet_gevonden(request, *args, **kwargs):
    return Response({"detail": "Onbekend endpoint."}, status=404)
