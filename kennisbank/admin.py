"""Beheerscherm (/beheer/).

- Redacteuren (procesmanagement) bewerken hier artikelen en behandelen voorstellen,
  alleen binnen de omgeving(en) waar zij redacteur zijn.
- Functioneel beheerders (superusers) beheren daarnaast omgevingen, toegang en keuzelijsten.
"""

from django import forms
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from . import diensten
from .models import (
    Artikel,
    ArtikelVersie,
    Cluster,
    Omgeving,
    Sectie,
    Status,
    Tag,
    Toegang,
    Verbetervoorstel,
    Zaaktype,
)
from .rechten import Rechten


class RedactieRechtenMixin:
    """Beperkt toegang tot objecten in de omgevingen waar de gebruiker redacteur is."""

    omgeving_pad = "omgeving"

    def _omgevingen(self, request):
        return Rechten(request.user).redactie_omgevingen

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(**{f"{self.omgeving_pad}__in": self._omgevingen(request)})

    def has_module_permission(self, request):
        return request.user.is_active and (request.user.is_superuser or bool(self._omgevingen(request)))

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


class SectieInline(admin.StackedInline):
    model = Sectie
    extra = 0
    fields = ["volgorde", "kop", "inhoud", "onboarding"]
    formfield_overrides = {}

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        veld = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name in {"inhoud", "onboarding"}:
            veld.widget.attrs.update(rows=6 if db_field.name == "inhoud" else 3, style="width:90%")
        return veld

    def has_add_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return True

    def has_view_permission(self, request, obj=None):
        return True


class VersieInline(admin.TabularInline):
    model = ArtikelVersie
    extra = 0
    can_delete = False
    fields = ["versie", "gepubliceerd_op", "gepubliceerd_door", "toelichting"]
    readonly_fields = fields
    verbose_name_plural = "Versiegeschiedenis (onveranderlijk)"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True


class ArtikelForm(forms.ModelForm):
    wijzigingstoelichting = forms.CharField(
        required=False,
        max_length=300,
        label="Toelichting bij deze wijziging",
        help_text="Komt in de versiegeschiedenis. Bijvoorbeeld: 'Termijn tweede rappel aangepast n.a.v. voorstel'.",
    )

    class Meta:
        model = Artikel
        fields = [
            "titel",
            "slug",
            "samenvatting",
            "soort",
            "omgeving",
            "eigenaar",
            "clusters",
            "tags",
            "zaaktypen",
            "status",
        ]


@admin.register(Artikel)
class ArtikelAdmin(RedactieRechtenMixin, admin.ModelAdmin):
    form = ArtikelForm
    list_display = ["titel", "soort", "status", "versie_label", "omgeving", "gepubliceerd_op", "bekijk"]
    list_filter = ["status", "soort", "omgeving", "clusters", "zaaktypen"]
    search_fields = ["titel", "samenvatting", "secties__inhoud"]
    prepopulated_fields = {"slug": ["titel"]}
    filter_horizontal = ["clusters", "tags", "zaaktypen"]
    inlines = [SectieInline, VersieInline]
    readonly_fields = ["versie", "gepubliceerd_op"]
    actions = ["publiceren", "archiveren"]
    fieldsets = [
        (None, {"fields": ["titel", "slug", "samenvatting", "soort", "omgeving", "eigenaar"]}),
        ("Vindbaarheid", {"fields": ["clusters", "tags", "zaaktypen"]}),
        ("Publicatie", {"fields": ["status", "wijzigingstoelichting", "versie", "gepubliceerd_op"]}),
    ]

    @admin.display(description="Versie")
    def versie_label(self, obj):
        return f"v{obj.versie}" if obj.versie else "–"

    @admin.display(description="")
    def bekijk(self, obj):
        return format_html('<a href="{}" target="_blank">Bekijk</a>', obj.get_absolute_url())

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "omgeving" and not request.user.is_superuser:
            kwargs["queryset"] = Omgeving.objects.filter(pk__in=self._omgevingen(request))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        versie = diensten.registreer_publicatie(
            form.instance, request.user, form.cleaned_data.get("wijzigingstoelichting", "")
        )
        if versie:
            messages.info(request, f"Gepubliceerd als versie {versie.versie}.")

    @admin.action(description="Publiceren")
    def publiceren(self, request, queryset):
        n = 0
        for a in queryset:
            a.status = Status.GEPUBLICEERD
            a.save(update_fields=["status", "gewijzigd_op"])
            if diensten.registreer_publicatie(a, request.user, "Gepubliceerd via lijstactie"):
                n += 1
        self.message_user(request, f"{n} artikel(en) gepubliceerd.")

    @admin.action(description="Archiveren (niet meer zichtbaar voor medewerkers)")
    def archiveren(self, request, queryset):
        n = queryset.update(status=Status.GEARCHIVEERD)
        self.message_user(request, f"{n} artikel(en) gearchiveerd. De versiegeschiedenis blijft bewaard.")


@admin.register(Verbetervoorstel)
class VerbetervoorstelAdmin(RedactieRechtenMixin, admin.ModelAdmin):
    omgeving_pad = "artikel__omgeving"
    list_display = ["artikel", "status", "ingediend_op", "ingediend_door", "kort"]
    list_filter = ["status", "artikel__omgeving"]
    search_fields = ["tekst", "citaat", "artikel__titel"]
    readonly_fields = [
        "artikel",
        "artikel_versie",
        "citaat",
        "tekst",
        "ingediend_door",
        "ingediend_op",
        "behandeld_door",
        "behandeld_op",
    ]
    fields = readonly_fields[:6] + ["status", "terugkoppeling", "behandeld_door", "behandeld_op"]

    @admin.display(description="Voorstel")
    def kort(self, obj):
        return obj.tekst[:80]

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        obj.behandeld_door = request.user
        obj.behandeld_op = timezone.now()
        super().save_model(request, obj, form, change)
        if "terugkoppeling" in form.changed_data or "status" in form.changed_data:
            diensten.meld_terugkoppeling(obj)


# --- Alleen voor functioneel beheerders ------------------------------------------------


class ToegangInline(admin.TabularInline):
    model = Toegang
    extra = 1
    autocomplete_fields = ["groep"]


@admin.register(Omgeving)
class OmgevingAdmin(admin.ModelAdmin):
    list_display = ["naam", "slug"]
    prepopulated_fields = {"slug": ["naam"]}
    inlines = [ToegangInline]


@admin.register(Toegang)
class ToegangAdmin(admin.ModelAdmin):
    list_display = ["groep", "rol", "omgeving"]
    list_filter = ["omgeving", "rol"]
    autocomplete_fields = ["groep"]


class RedactieKeuzelijstAdmin(admin.ModelAdmin):
    """Redacteuren mogen keuzelijsten aanvullen; alleen beheerders verwijderen."""

    search_fields = ["naam"]

    def _mag(self, request):
        return request.user.is_superuser or Rechten(request.user).is_redacteur

    def has_module_permission(self, request):
        return self._mag(request)

    has_view_permission = lambda self, request, obj=None: self._mag(request)  # noqa: E731
    has_add_permission = lambda self, request: self._mag(request)  # noqa: E731
    has_change_permission = lambda self, request, obj=None: self._mag(request)  # noqa: E731

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Cluster)
class ClusterAdmin(RedactieKeuzelijstAdmin):
    list_display = ["naam", "volgorde"]
    list_editable = ["volgorde"]


@admin.register(Tag)
class TagAdmin(RedactieKeuzelijstAdmin):
    pass


@admin.register(Zaaktype)
class ZaaktypeAdmin(RedactieKeuzelijstAdmin):
    list_display = ["naam", "code"]
    search_fields = ["naam", "code"]
