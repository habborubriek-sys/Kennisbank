"""REST-API (versie 1). Wordt gebruikt door de eigen frontend en door koppelingen (zaaksysteem).

Documentatie: /api/schema/ (OpenAPI) en /api/docs/ (interactief).
"""

from django.db.models import Count, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from . import diensten
from .assistent import beantwoord
from .inhoud import schoon
from .models import (
    Artikel,
    ArtikelVersie,
    AssistentTelling,
    Cluster,
    Favoriet,
    RecentBezocht,
    Sectie,
    Soort,
    Tag,
    Verbetervoorstel,
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

    class Meta:
        model = Artikel
        fields = [
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
        ]


class SectieSerializer(serializers.ModelSerializer):
    inhoud_html = serializers.SerializerMethodField()

    class Meta:
        model = Sectie
        fields = ["kop", "inhoud_html"]

    def get_inhoud_html(self, obj) -> str:
        return schoon(obj.inhoud)


class ArtikelSerializer(ArtikelKortSerializer):
    secties = SectieSerializer(many=True, read_only=True)
    gerelateerd = serializers.SerializerMethodField()
    bewerk_url = serializers.SerializerMethodField()

    class Meta(ArtikelKortSerializer.Meta):
        fields = ArtikelKortSerializer.Meta.fields + ["secties", "gerelateerd", "bewerk_url"]

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
        return [{"slug": a.slug, "titel": a.titel} for a in qs]

    def get_bewerk_url(self, obj) -> str | None:
        if self.context["rechten"].mag_redigeren(obj):
            return f"/beheer/kennisbank/artikel/{obj.pk}/change/"
        return None


class VoorstelSerializer(serializers.ModelSerializer):
    artikel = serializers.SlugRelatedField(slug_field="slug", queryset=Artikel.objects.all())
    artikel_titel = serializers.CharField(source="artikel.titel", read_only=True)
    ingediend_door = serializers.SerializerMethodField()
    van_mij = serializers.SerializerMethodField()

    class Meta:
        model = Verbetervoorstel
        fields = [
            "id",
            "artikel",
            "artikel_titel",
            "artikel_versie",
            "citaat",
            "tekst",
            "status",
            "terugkoppeling",
            "ingediend_op",
            "ingediend_door",
            "van_mij",
            "behandeld_op",
        ]
        read_only_fields = ["artikel_versie", "status", "terugkoppeling", "ingediend_op", "behandeld_op"]

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


def _artikel_of_404(request, slug):
    artikel = get_object_or_404(
        Artikel.objects.select_related("omgeving").prefetch_related(
            "clusters", "tags", "zaaktypen", Prefetch("secties", Sectie.objects.order_by("volgorde", "id"))
        ),
        slug=slug,
    )
    if not rechten(request).mag_lezen(artikel):
        # 404 in plaats van 403: verraad niet dat het artikel bestaat.
        from django.http import Http404

        raise Http404
    return artikel


def _ctx(request):
    return {"request": request, "rechten": rechten(request)}


# --- Endpoints ------------------------------------------------------------------------


@extend_schema(
    summary="Huidige gebruiker (GET) en voorkeuren wijzigen (PATCH)",
    request=inline_serializer("IkWijzigen", {"onboarding": serializers.BooleanField(required=False)}),
    responses=inline_serializer(
        "Ik",
        {
            "naam": serializers.CharField(),
            "is_redacteur": serializers.BooleanField(),
            "onboarding": serializers.BooleanField(),
            "favorieten": serializers.ListField(),
            "recent": serializers.ListField(),
            "uitlog_url": serializers.CharField(),
        },
    ),
)
@api_view(["GET", "PATCH"])
def ik(request):
    p = diensten.profiel(request.user)
    if request.method == "PATCH":
        if "onboarding" in request.data:
            p.onboarding = bool(request.data["onboarding"])
            p.save(update_fields=["onboarding"])
    r = rechten(request)
    zichtbaar = r.gepubliceerde_artikelen()
    recent = (
        RecentBezocht.objects.filter(gebruiker=request.user, artikel__in=zichtbaar)
        .select_related("artikel")
        .order_by("-bezocht_op")
    )
    from django.conf import settings

    return Response(
        {
            "naam": request.user.get_full_name() or request.user.get_username(),
            "is_redacteur": r.is_redacteur,
            "onboarding": p.onboarding,
            "favorieten": list(
                Favoriet.objects.filter(gebruiker=request.user, artikel__in=zichtbaar).values_list(
                    "artikel__slug", flat=True
                )
            ),
            "recent": [{"slug": x.artikel.slug, "bezocht_op": x.bezocht_op} for x in recent],
            "beheer_url": "/beheer/" if request.user.is_staff else None,
            "uitlog_url": "/oidc/logout/" if settings.KB_AUTH_MODUS == "oidc" else "/uitloggen/",
            "ai_aan": settings.KB_AI_PROVIDER != "uit",
            "app_naam": settings.KB_APP_NAAM,
        }
    )


@extend_schema(summary="Keuzelijsten voor filters (clusters, soorten, tags, zaaktypen)", responses=OpenApiTypes.OBJECT)
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
            diensten.registreer_zoekopdracht(q, len(resultaat))
    else:
        resultaat = qs.order_by("titel")
    return Response(ArtikelKortSerializer(resultaat, many=True, context=_ctx(request)).data)


@extend_schema(summary="Eén artikel met secties", responses=ArtikelSerializer)
@api_view(["GET"])
def artikel(request, slug):
    a = _artikel_of_404(request, slug)
    return Response(ArtikelSerializer(a, context=_ctx(request)).data)


@extend_schema(summary="Weergave registreren (statistiek en 'recent bezocht')", request=None, responses={204: None})
@api_view(["POST"])
def weergave(request, slug):
    a = _artikel_of_404(request, slug)
    diensten.registreer_weergave(request.user, a)
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(summary="Favoriet aan (PUT) of uit (DELETE)", request=None, responses={204: None})
@api_view(["PUT", "DELETE"])
def favoriet(request, slug):
    a = _artikel_of_404(request, slug)
    diensten.zet_favoriet(request.user, a, request.method == "PUT")
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(summary="Versiegeschiedenis van een artikel (redacteuren)", responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
def versies(request, slug):
    a = _artikel_of_404(request, slug)
    if not rechten(request).mag_redigeren(a):
        raise PermissionDenied
    return Response(
        [
            {
                "versie": v.versie,
                "gepubliceerd_op": v.gepubliceerd_op,
                "gepubliceerd_door": v.gepubliceerd_door.get_full_name() if v.gepubliceerd_door else None,
                "toelichting": v.toelichting,
                "inhoud": v.inhoud,
            }
            for v in ArtikelVersie.objects.filter(artikel=a).select_related("gepubliceerd_door")
        ]
    )


class VoorstelBehandelSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=VoorstelStatus.choices)
    terugkoppeling = serializers.CharField(allow_blank=True, max_length=4000)


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
    qs = Verbetervoorstel.objects.select_related("artikel", "ingediend_door")
    qs = qs.filter(Q(ingediend_door=request.user) | Q(artikel__omgeving_id__in=r.redactie_omgevingen))
    return Response(VoorstelSerializer(qs, many=True, context=_ctx(request)).data)


@extend_schema(
    summary="Verbetervoorstel behandelen (redacteuren)",
    request=VoorstelBehandelSerializer,
    responses=VoorstelSerializer,
)
@api_view(["PATCH"])
def voorstel(request, pk):
    v = get_object_or_404(Verbetervoorstel.objects.select_related("artikel", "ingediend_door"), pk=pk)
    if not rechten(request).mag_redigeren(v.artikel):
        raise PermissionDenied
    s = VoorstelBehandelSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    gewijzigd = (v.status, v.terugkoppeling) != (s.validated_data["status"], s.validated_data["terugkoppeling"])
    v.status = s.validated_data["status"]
    v.terugkoppeling = s.validated_data["terugkoppeling"].strip()
    v.behandeld_door = request.user
    v.behandeld_op = timezone.now()
    v.save()
    if gewijzigd and v.terugkoppeling:
        diensten.meld_terugkoppeling(v)
    return Response(VoorstelSerializer(v, context=_ctx(request)).data)


@extend_schema(
    summary="Gebruiksstatistieken (redacteuren). Geaggregeerd, zonder persoonsgegevens.",
    parameters=[OpenApiParameter("dagen", int, description="Periode, standaard 30")],
    responses=OpenApiTypes.OBJECT,
)
@api_view(["GET"])
def statistieken(request):
    r = rechten(request)
    if not r.is_redacteur:
        raise PermissionDenied
    dagen = max(1, min(int(request.query_params.get("dagen", 30)), 3650))
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
                "slug": a.slug,
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
        ZoekTelling.objects.filter(datum__gte=sinds)
        .values("term")
        .annotate(aantal=Sum("aantal"), zonder_resultaat=Sum("zonder_resultaat"))
        .order_by("-aantal")[:15]
    )
    zonder = (
        ZoekTelling.objects.filter(datum__gte=sinds, zonder_resultaat__gt=0)
        .values("term")
        .annotate(aantal=Sum("zonder_resultaat"))
        .order_by("-aantal")[:10]
    )
    vs = Verbetervoorstel.objects.filter(artikel__in=arts)
    ass = AssistentTelling.objects.filter(datum__gte=sinds).aggregate(v=Sum("vragen"), z=Sum("zonder_bron"))
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
    qs = rechten(request).gepubliceerde_artikelen().filter(zaaktypen__code=code).distinct()
    qs = qs.select_related("omgeving").prefetch_related("clusters", "tags", "zaaktypen").order_by("titel")
    return Response(ArtikelKortSerializer(qs, many=True, context=_ctx(request)).data)


@extend_schema(exclude=True)
@api_view(["GET"])
@permission_classes([AllowAny])
def niet_gevonden(request, *args, **kwargs):
    return Response({"detail": "Onbekend endpoint."}, status=404)
