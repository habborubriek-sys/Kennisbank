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
    Bericht,
    Cluster,
    Omgeving,
    Soort,
    Status,
    Tag,
    Toegang,
    Verbetervoorstel,
    Zaaktype,
    normaliseer_tag,
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
    fields = ["versie", "gepubliceerd_op", "gepubliceerd_door", "toelichting", "kleine_correctie"]
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
        naam = normaliseer_tag(deel)
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
        widget=forms.TextInput(attrs={"style": "width:60%", "placeholder": "Wat is er veranderd, in één zin?"}),
        label="Toelichting bij deze wijziging",
        help_text="Verplicht als een gepubliceerd artikel inhoudelijk wijzigt. Medewerkers zien deze zin als "
        "melding bij het artikel, en wie het als favoriet heeft krijgt hem per e-mail. "
        "Bijvoorbeeld: 'Termijn tweede rappel aangepast van 2 naar 3 weken'.",
    )
    kleine_correctie = forms.BooleanField(
        required=False,
        label="Kleine correctie, geen melding",
        help_text="Typfout, opmaak, een verouderde naam. De wijziging komt wel in de versiegeschiedenis, "
        "maar medewerkers krijgen geen melding en geen e-mail.",
    )
    nieuwsbericht = forms.BooleanField(
        required=False,
        label="Ook als nieuwsbericht plaatsen",
        help_text="Maakt een concept-nieuwsbericht met deze toelichting, gekoppeld aan dit artikel. "
        "Je kunt het daarna aanvullen en publiceren.",
    )

    class Meta:
        model = Artikel
        fields = ["titel", "samenvatting", "inhoud", "soort", "omgeving", "eigenaar", "clusters", "zaaktypen", "status"]
        widgets = {"inhoud": forms.Textarea(attrs={"class": "kb-editor", "rows": 24})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and not self.is_bound:
            self.fields["tags_tekst"].initial = ", ".join(self.instance.tags.values_list("naam", flat=True))

    def clean(self):
        data = super().clean()
        if data.get("status") != Status.GEPUBLICEERD or not self.instance.pk:
            return data
        # Zou opslaan een nieuwe versie opleveren? Dan is een toelichting verplicht (tenzij kleine correctie),
        # want die toelichting is precies wat medewerkers als melding te zien krijgen.
        if self.errors:
            return data
        from .inhoud import schoon

        nieuw = {
            "titel": data.get("titel", ""),
            "samenvatting": data.get("samenvatting", ""),
            "soort": data.get("soort", ""),
            "eigenaar": data.get("eigenaar", ""),
            "omgeving": data["omgeving"].slug if data.get("omgeving") else "",
            "clusters": sorted(c.naam for c in data.get("clusters", [])),
            "tags": sorted(tags_uit_tekst(data.get("tags_tekst", ""))),
            "zaaktypen": sorted(z.code for z in data.get("zaaktypen", [])),
            "formaat": "artikel-html",
            "inhoud": schoon(data.get("inhoud", "")),
        }
        if (
            diensten.is_inhoudelijk_gewijzigd(self.instance, nieuw)
            and not data.get("kleine_correctie")
            and not (data.get("wijzigingstoelichting") or "").strip()
        ):
            self.add_error(
                "wijzigingstoelichting",
                "Geef in één zin aan wat er is gewijzigd; medewerkers zien dit als melding bij het artikel. "
                "Is het alleen een typfout of opmaak? Vink dan 'Kleine correctie' aan.",
            )
        return data


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
        (
            "Publicatie",
            {
                "fields": [
                    "status",
                    "wijzigingstoelichting",
                    "kleine_correctie",
                    "nieuwsbericht",
                    "versie",
                    "gepubliceerd_op",
                ]
            },
        ),
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
        """Lege voorbeeldpagina voor in het splitscreen; de inhoud komt via postMessage uit de editor."""
        if not self.has_change_permission(request):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        return render(request, "kennisbank/voorbeeld.html", {"app_naam": settings.KB_APP_NAAM})

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
        form.instance.tags.set(
            [Tag.objects.get_or_create(naam=n)[0] for n in tags_uit_tekst(form.cleaned_data.get("tags_tekst", ""))]
        )
        diensten.herbouw_secties(form.instance)  # ook de zoekdocumenten, dus ná de tags
        versie = diensten.registreer_publicatie(
            form.instance,
            request.user,
            form.cleaned_data.get("wijzigingstoelichting", ""),
            kleine_correctie=bool(form.cleaned_data.get("kleine_correctie")),
        )
        if versie:
            if versie.versie == 1:
                messages.info(request, "Gepubliceerd als versie 1.")
            elif versie.kleine_correctie:
                messages.info(request, f"Gepubliceerd als versie {versie.versie} (kleine correctie, geen melding).")
            else:
                messages.info(
                    request,
                    f"Gepubliceerd als versie {versie.versie}. Medewerkers zien de toelichting als melding "
                    "bij het artikel; wie het als favoriet heeft krijgt een e-mail.",
                )
            if form.cleaned_data.get("nieuwsbericht"):
                bericht = diensten.maak_nieuwsconcept(form.instance, versie, request.user)
                url = reverse("admin:kennisbank_bericht_change", args=[bericht.pk])
                messages.info(
                    request,
                    format_html(
                        'Er staat een concept-nieuwsbericht klaar: <a href="{}">{}</a>. Vul het aan en publiceer het.',
                        url,
                        bericht.titel,
                    ),
                )
        elif form.cleaned_data.get("nieuwsbericht"):
            messages.warning(request, "Geen nieuwsbericht gemaakt: het artikel is niet (opnieuw) gepubliceerd.")

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


class BerichtForm(forms.ModelForm):
    class Meta:
        model = Bericht
        fields = ["titel", "tekst", "omgeving", "artikelen", "status", "vastgepind", "verloopt_op"]
        widgets = {"tekst": forms.Textarea(attrs={"class": "kb-editor", "rows": 12})}


@admin.register(Bericht)
class BerichtAdmin(RedactieRechtenMixin, admin.ModelAdmin):
    """Nieuwsberichten: redacteuren schrijven en publiceren ze voor hun eigen omgeving(en)."""

    form = BerichtForm
    list_display = ["titel", "omgeving", "status", "vastgepind", "gepubliceerd_op", "verloopt_op", "auteur"]
    list_filter = ["status", "omgeving", "vastgepind"]
    search_fields = ["titel", "tekst"]
    filter_horizontal = ["artikelen"]
    readonly_fields = ["gepubliceerd_op", "auteur"]
    fieldsets = [
        (None, {"fields": ["titel", "tekst"]}),
        ("Waar en waarover", {"fields": ["omgeving", "artikelen"]}),
        ("Publicatie", {"fields": ["status", "vastgepind", "verloopt_op", "gepubliceerd_op", "auteur"]}),
    ]

    class Media:
        css = {"all": ["kennisbank/vendor/jodit/jodit.min.css", "kennisbank/beheer-editor.css"]}
        js = ["kennisbank/vendor/jodit/jodit.min.js", "kennisbank/beheer-editor.js"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "omgeving" and not request.user.is_superuser:
            kwargs["queryset"] = Omgeving.objects.filter(pk__in=self._omgevingen(request))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "artikelen":
            qs = Artikel.objects.exclude(status=Status.GEARCHIVEERD).order_by("titel")
            if not request.user.is_superuser:
                qs = qs.filter(omgeving__in=self._omgevingen(request))
            kwargs["queryset"] = qs
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not obj.auteur_id:
            obj.auteur = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        # Een redacteur mag zijn eigen berichten wel weggooien (anders dan bij artikelen, die een geschiedenis hebben).
        return self.has_module_permission(request)


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
