"""Beheerscherm (/beheer/).

- Redacteuren (procesmanagement) bewerken hier artikelen en behandelen voorstellen,
  alleen binnen de omgeving(en) waar zij redacteur zijn.
- Functioneel beheerders (superusers) beheren daarnaast omgevingen, toegang en keuzelijsten.
"""

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from . import diensten
from .models import (
    Artikel,
    ArtikelVersie,
    Cluster,
    Omgeving,
    Soort,
    Status,
    Tag,
    Toegang,
    Verbetervoorstel,
    Zaaktype,
)
from .rechten import Rechten
from .word_import import WordImportFout, lees_docx


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


class TagsWidget(forms.TextInput):
    """Tekstvak met suggesties van bestaande tags (datalist)."""

    template_name = "admin/kennisbank/tags_widget.html"

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx["bestaande_tags"] = list(Tag.objects.values_list("naam", flat=True))
        return ctx


def tags_uit_tekst(tekst: str) -> list[str]:
    gezien, uit = set(), []
    for deel in (tekst or "").split(","):
        naam = " ".join(deel.split()).strip().lower()[:60]
        if naam and naam not in gezien:
            gezien.add(naam)
            uit.append(naam)
    return uit


class ArtikelForm(forms.ModelForm):
    tags_tekst = forms.CharField(
        required=False,
        label="Tags",
        widget=TagsWidget(attrs={"style": "width:60%", "autocomplete": "off"}),
        help_text="Gescheiden door komma's, bijvoorbeeld: rappel, termijnen, brief. "
        "Nieuwe tags worden automatisch aangemaakt.",
    )
    wijzigingstoelichting = forms.CharField(
        required=False,
        max_length=300,
        label="Toelichting bij deze wijziging",
        help_text="Komt in de versiegeschiedenis. Bijvoorbeeld: 'Termijn tweede rappel aangepast n.a.v. voorstel'.",
    )

    class Meta:
        model = Artikel
        fields = ["titel", "samenvatting", "inhoud", "soort", "omgeving", "eigenaar", "clusters", "zaaktypen", "status"]
        widgets = {"inhoud": forms.Textarea(attrs={"class": "kb-editor", "rows": 24})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and not self.is_bound:
            self.fields["tags_tekst"].initial = ", ".join(self.instance.tags.values_list("naam", flat=True))


class WordImportForm(forms.Form):
    bestand = forms.FileField(label="Word-document (.docx)")
    omgeving = forms.ModelChoiceField(queryset=Omgeving.objects.all(), label="Omgeving")
    soort = forms.ChoiceField(choices=Soort.choices, initial=Soort.WERKINSTRUCTIE, label="Soort")

    def clean_bestand(self):
        f = self.cleaned_data["bestand"]
        if not f.name.lower().endswith(".docx"):
            raise forms.ValidationError(
                "Alleen .docx-bestanden (Word 2007 of nieuwer). Sla een .doc of PDF eerst op als .docx."
            )
        if f.size > 20 * 1024 * 1024:
            raise forms.ValidationError("Het bestand is groter dan 20 MB.")
        return f


@admin.register(Artikel)
class ArtikelAdmin(RedactieRechtenMixin, admin.ModelAdmin):
    form = ArtikelForm
    list_display = ["titel", "nummer", "soort", "status", "versie_label", "omgeving", "gepubliceerd_op", "bekijk"]
    list_filter = ["status", "soort", "omgeving", "clusters", "zaaktypen"]
    search_fields = ["titel", "samenvatting", "inhoud", "=id"]
    filter_horizontal = ["clusters", "zaaktypen"]
    inlines = [VersieInline]
    readonly_fields = ["versie", "gepubliceerd_op", "link"]
    actions = ["publiceren", "archiveren"]
    change_list_template = "admin/kennisbank/artikel/change_list.html"
    fieldsets = [
        (None, {"fields": ["titel", "samenvatting", "inhoud"]}),
        ("Eigenschappen", {"fields": ["soort", "omgeving", "eigenaar", "link"]}),
        ("Vindbaarheid", {"fields": ["clusters", "tags_tekst", "zaaktypen"]}),
        ("Publicatie", {"fields": ["status", "wijzigingstoelichting", "versie", "gepubliceerd_op"]}),
    ]

    class Media:
        css = {"all": ["kennisbank/vendor/jodit/jodit.min.css", "kennisbank/beheer-editor.css"]}
        js = ["kennisbank/vendor/jodit/jodit.min.js", "kennisbank/beheer-editor.js"]

    def get_urls(self):
        eigen = [
            path(
                "importeren-word/",
                self.admin_site.admin_view(self.importeren_word),
                name="kennisbank_artikel_importeren_word",
            ),
            path("voorbeeld/", self.admin_site.admin_view(self.voorbeeld), name="kennisbank_artikel_voorbeeld"),
        ]
        return eigen + super().get_urls()

    def voorbeeld(self, request):
        """Toon de (nog niet opgeslagen) tekst uit de editor zoals het artikel er gepubliceerd uit zou zien."""
        from django.http import HttpResponseNotAllowed

        from .inhoud import blokken

        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not self.has_change_permission(request):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        alle = blokken(request.POST.get("inhoud", ""))
        soorten = dict(Soort.choices)
        ctx = {
            "app_naam": settings.KB_APP_NAAM,
            "titel": request.POST.get("titel", "").strip() or "(nog geen titel)",
            "samenvatting": request.POST.get("samenvatting", "").strip(),
            "soort": request.POST.get("soort", ""),
            "soort_label": soorten.get(request.POST.get("soort", ""), ""),
            "eigenaar": request.POST.get("eigenaar", "").strip(),
            "blokken": alle,
            "heeft_secties": any(b["type"] == "sectie" for b in alle),
        }
        return render(request, "kennisbank/voorbeeld.html", ctx)

    def importeren_word(self, request):
        """Upload een .docx; het wordt een concept-artikel met secties. Daarna door naar het bewerkscherm."""
        if not self.has_add_permission(request):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        form = WordImportForm(request.POST or None, request.FILES or None)
        if not request.user.is_superuser:
            form.fields["omgeving"].queryset = Omgeving.objects.filter(pk__in=self._omgevingen(request))
        if request.method == "POST" and form.is_valid():
            try:
                gelezen = lees_docx(form.cleaned_data["bestand"], form.cleaned_data["bestand"].name)
            except WordImportFout as e:
                form.add_error("bestand", str(e))
            else:
                artikel = Artikel.objects.create(
                    omgeving=form.cleaned_data["omgeving"],
                    titel=gelezen.titel,
                    samenvatting="(vul een samenvatting in)",
                    inhoud=gelezen.inhoud,
                    soort=form.cleaned_data["soort"],
                    status=Status.CONCEPT,
                )
                diensten.herbouw_secties(artikel)
                messages.success(
                    request,
                    f"'{gelezen.titel}' is ingelezen als concept. Pas de titel aan, vul de samenvatting in, "
                    "maak secties en onboarding-uitleg in de editor, en zet de status op 'Gepubliceerd'.",
                )
                for m in gelezen.meldingen:
                    messages.warning(request, m)
                return redirect(reverse("admin:kennisbank_artikel_change", args=[artikel.pk]))
        ctx = {
            **self.admin_site.each_context(request),
            "title": "Artikel importeren uit Word",
            "form": form,
            "opts": self.model._meta,
        }
        return render(request, "admin/kennisbank/artikel/importeren_word.html", ctx)

    @admin.display(description="Nr.", ordering="id")
    def nummer(self, obj):
        return obj.pk

    @admin.display(description="Link")
    def link(self, obj):
        if not obj.pk:
            return "Wordt toegekend bij opslaan (het nummer in de link verandert daarna nooit meer)."
        return format_html('<a href="{0}" target="_blank">{0}</a>', obj.get_absolute_url())

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
        diensten.herbouw_secties(form.instance)
        form.instance.tags.set(
            [Tag.objects.get_or_create(naam=n)[0] for n in tags_uit_tekst(form.cleaned_data.get("tags_tekst", ""))]
        )
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
