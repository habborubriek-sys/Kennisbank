"""Beheerscherm (/beheer/).

- Redacteuren (procesmanagement) bewerken hier artikelen en behandelen voorstellen,
  alleen binnen de omgeving(en) waar zij redacteur zijn.
- Functioneel beheerders (superusers) beheren daarnaast omgevingen, toegang en keuzelijsten.
"""

import datetime
import json

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Count, OuterRef, Subquery
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.formats import date_format
from django.utils.html import format_html

from . import diensten, lade
from .models import (
    AFGEHANDELD,
    GUID_PATROON,
    MAX_INHOUD,
    Artikel,
    ArtikelVersie,
    Bericht,
    BerichtStatus,
    Cluster,
    Conceptversie,
    GroepLabel,
    InzageStatus,
    Kladversie,
    Omgeving,
    ReviewOpmerking,
    Reviewteam,
    Sjabloon,
    Soort,
    Status,
    Systeemstand,
    Tag,
    Toegang,
    Verbetervoorstel,
    VoorstelBericht,
    VoorstelStatus,
    Zaaktype,
    normaliseer_tag,
)
from .models import (
    OPEN as OPEN_VOORSTEL,
)
from .rechten import rechten
from .word_import import WordImportFout, lees_docx


class Vinkjes(forms.CheckboxSelectMultiple):
    """Vinkjes met een id voor de groep, zodat de hulptekst eronder ook een id krijgt.

    Django geeft elk vinkje `aria-describedby="id_<veld>_helptext"`, maar zet dat id alleen op de hulptekst als
    het veld een id voor het label heeft; bij vinkjes is dat leeg. Dan wees de verwijzing naar niets (ronde B).
    """

    def id_for_label(self, id_, index=None):
        return id_ if index is None else super().id_for_label(id_, index)


def enige_omgeving(request):
    """De pk van de enige omgeving waarin deze gebruiker iets mag maken, of None als dat er meer (of geen) zijn."""
    if request.user.is_superuser:
        ids = list(Omgeving.objects.values_list("pk", flat=True)[:2])
    else:
        ids = sorted(rechten(request).redactie_omgevingen)
    return ids[0] if len(ids) == 1 else None


class RedactieRechtenMixin:
    """Beperkt toegang tot objecten in de omgevingen waar de gebruiker redacteur is."""

    omgeving_pad = "omgeving"

    def _omgevingen(self, request):
        # rechten(request) onthoudt de uitkomst voor de rest van het verzoek. Een nieuw Rechten-object
        # zocht ze bij elke aanroep opnieuw op, en Django vraagt de rechten per rij in de lijst.
        return rechten(request).redactie_omgevingen

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(**{f"{self.omgeving_pad}__in": self._omgevingen(request)})

    def has_module_permission(self, request):
        return request.user.is_active and (request.user.is_superuser or bool(self._omgevingen(request)))

    def get_changeform_initial_data(self, request):
        """Ronde A (review 1.27.0, M11): heb je maar één omgeving, dan staat die bij iets nieuws al ingevuld."""
        data = super().get_changeform_initial_data(request)
        if self.omgeving_pad == "omgeving" and "omgeving" not in data:
            enige = enige_omgeving(request)
            if enige is not None:
                data["omgeving"] = enige
        return data

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
    max_num = 0  # geen lege regel onderaan; er valt hier niets toe te voegen
    can_delete = False
    fields = ["versie", "gepubliceerd_op", "door", "toelichting", "klein", "review", "bekijk"]
    readonly_fields = fields
    verbose_name_plural = "Versiegeschiedenis (onveranderlijk)"

    # 1.31.0 (review 1.27.0, M15): de naam in plaats van de inlognaam, en "ja" in plaats van een rood kruisje.
    @admin.display(description="Gepubliceerd door")
    def door(self, obj):
        return diensten.naam_van(obj.gepubliceerd_door) if obj.gepubliceerd_door_id else "—"

    @admin.display(description="Kleine correctie")
    def klein(self, obj):
        return "ja" if obj.kleine_correctie else ""

    @admin.display(description="")
    def bekijk(self, obj):
        """Link naar de opgeslagen tekst van die versie, zoals medewerkers hem toen zagen."""
        if not obj.pk:
            return ""
        url = reverse("admin:kennisbank_artikel_versie", args=[obj.artikel_id, obj.versie])
        return format_html('<a href="{}" target="_blank" rel="noopener">Tekst bekijken</a>', url)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True


class TagsWidget(forms.TextInput):
    """Tekstvak met een eigen suggestielijst van bestaande tags.

    Een gewone datalist van de browser vergelijkt de hele veldwaarde met de opties, dus zodra er een
    komma in staat matcht er niets meer. Daarom een eigen lijstje: het kijkt alleen naar het stukje
    dat je nu typt, matcht op elk deel van een tag en zet de meest gebruikte tags bovenaan.
    """

    template_name = "admin/kennisbank/tags_widget.html"

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        tags = Tag.objects.annotate(_n=Count("artikel")).order_by("-_n", "naam").values_list("naam", "_n")
        ctx["tags_json"] = json.dumps([{"naam": n, "aantal": a} for n, a in tags])
        ctx["widget"]["attrs"]["autocomplete"] = "off"
        return ctx


def tags_uit_tekst(tekst: str) -> list[str]:
    gezien, uit = set(), []
    for deel in (tekst or "").split(","):
        naam = normaliseer_tag(deel)
        if naam and naam not in gezien:
            gezien.add(naam)
            uit.append(naam)
    return uit


#: Binnen hoeveel dagen een naderende herziening al wordt gemarkeerd.
HERZIENING_BINNENKORT = 30


class HerzieningFilter(admin.SimpleListFilter):
    """Filter op de datum "opnieuw nakijken voor", zodat een redacteur zijn achterstand kan zien."""

    title = "opnieuw nakijken"
    parameter_name = "herziening"

    def lookups(self, request, model_admin):
        return [
            ("te_laat", "Datum verstreken"),
            ("binnenkort", f"Binnen {HERZIENING_BINNENKORT} dagen"),
            ("later", "Later"),
            ("geen", "Geen datum ingevuld"),
        ]

    def queryset(self, request, queryset):
        vandaag = timezone.localdate()
        keuze = self.value()
        if keuze == "te_laat":
            return queryset.filter(status=Status.GEPUBLICEERD, herzien_voor__lt=vandaag)
        if keuze == "binnenkort":
            grens = vandaag + datetime.timedelta(days=HERZIENING_BINNENKORT)
            return queryset.filter(status=Status.GEPUBLICEERD, herzien_voor__gte=vandaag, herzien_voor__lte=grens)
        if keuze == "later":
            grens = vandaag + datetime.timedelta(days=HERZIENING_BINNENKORT)
            return queryset.filter(herzien_voor__gt=grens)
        if keuze == "geen":
            return queryset.filter(herzien_voor__isnull=True)
        return queryset


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
    geladen_stempel = forms.CharField(required=False, widget=forms.HiddenInput)
    #: Stempel van de conceptversie toen dit scherm werd geopend ('' = er was er geen). Zie
    #: diensten.concept_opslaan: zo overschrijft niemand ongemerkt de conceptversie van een collega.
    geladen_concept = forms.CharField(required=False, widget=forms.HiddenInput)
    #: Alleen een hint voor het bewerkscherm (is dit artikel al eens gepubliceerd?), zodat het
    #: volledige scherm weet wanneer het om een toelichting moet vragen. De regel zelf staat in clean().
    al_gepubliceerd = forms.CharField(required=False, widget=forms.HiddenInput)
    nieuwsbericht = forms.BooleanField(
        required=False,
        label="Ook als nieuwsbericht plaatsen",
        help_text="Maakt een concept-nieuwsbericht met deze toelichting, gekoppeld aan dit artikel. "
        "Je kunt het daarna aanvullen en publiceren.",
    )

    class Meta:
        model = Artikel
        fields = [
            "titel",
            "samenvatting",
            "inhoud",
            "soort",
            "omgeving",
            "eigenaar",
            "herzien_voor",
            "clusters",
            "zaaktypen",
            "status",
        ]
        widgets = {"inhoud": forms.Textarea(attrs={"class": "kb-editor", "rows": 24})}

    #: Gezet door ArtikelAdmin.get_form: wordt dit verzoek opgeslagen als conceptversie, en welke
    #: conceptversie hoort bij dit artikel?
    als_concept = False
    conceptversie = None
    spoed = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Het bewerkscherm (1.24.0) toont titel en samenvatting op het blad, zonder label: uitleg in het veld.
        if "titel" in self.fields:
            self.fields["titel"].widget.attrs.update(
                {"placeholder": "Titel: waar gaat dit artikel over?", "aria-label": "Titel"}
            )
        if "samenvatting" in self.fields:
            self.fields["samenvatting"].widget.attrs.update(
                {
                    "placeholder": "Samenvatting: in één of twee zinnen wat een medewerker hier vindt. Deze zin "
                    "verschijnt ook in de zoekresultaten en in het zaaksysteem.",
                    "aria-label": "Samenvatting",
                    "rows": 1,
                }
            )
        if self.spoed and "omgeving" in self.fields:
            self.fields["omgeving"].disabled = True  # bevinding 2: spoed verhuist niets
            self.fields["omgeving"].help_text = "Bij een spoedcorrectie blijft de omgeving zoals hij is."
        if self.instance.pk and not self.is_bound:
            self.fields["tags_tekst"].initial = ", ".join(self.instance.tags.values_list("naam", flat=True))
            self.fields["geladen_stempel"].initial = stempel_van(self.instance)
            self.fields["al_gepubliceerd"].initial = "1" if self.instance.versie else ""
            if self.conceptversie is not None:
                # Er wordt aan een nieuwe versie gewerkt: die openen, niet de gepubliceerde tekst.
                self.initial.update(diensten.concept_beginwaarden(self.conceptversie))
                self.fields["geladen_concept"].initial = self.conceptversie.stempel

    def clean(self):
        data = super().clean()
        if self.als_concept:
            # Opslaan als conceptversie: het artikel zelf verandert niet, dus geen controle op de
            # publicatieregels of een toelichting. Wel op de omvang; een collega die de conceptversie
            # intussen opsloeg, vangt concept_opslaan onder slot af.
            self._controleer_omvang(data)
            return data
        self._controleer_conflict(data)
        if self.spoed and self.instance.pk:
            # Review 1.20.1, bevinding 2: een spoedcorrectie is voor een tekstfout, niet voor een verhuizing.
            data["omgeving"] = self.instance.omgeving
        if not self.spoed:  # een spoedcorrectie raakt de conceptversie niet
            self._controleer_concept(data)
            if data.get("status") != Status.GEPUBLICEERD:
                self._gepubliceerde_tekst_houden(data)
            else:
                self._niet_tijdens_review()
        self._controleer_omvang(data)
        self._controleer_dubbele_titel(data)
        self._controleer_eerste_publicatie(data)
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

    def _controleer_concept(self, data):
        """Publiceren vanuit een scherm waarvan de conceptversie intussen is veranderd, weigeren.

        Anders zou het publiceren de nieuwere conceptversie van een collega weggooien (bij publiceren
        verdwijnt de conceptversie), of een conceptversie publiceren die hier nooit te zien was.
        """
        if not self.instance.pk:
            return
        with transaction.atomic():
            nu = diensten.concept_stand(self.instance.pk)
        if nu != (data.get("geladen_concept") or ""):
            raise forms.ValidationError(
                "Een collega heeft de conceptversie van dit artikel opgeslagen, gepubliceerd of weggegooid "
                "terwijl jij het openhad. Je wijzigingen zijn niet opgeslagen; ze staan nog in dit scherm. "
                "Open het artikel in een nieuw tabblad om te zien wat er nu staat."
            )

    def _niet_tijdens_review(self):
        """Publiceren terwijl de conceptversie ter inzage ligt kan niet (besluit Alex, 12 november).

        Eerst terugroepen; voor een dringende fout is er de spoedcorrectie. Zo gaat er nooit een tekst live
        waar een reviewer nog mee bezig is, en ziet de reviewer zijn werk niet zomaar verdwijnen.
        """
        from . import review

        if self.instance.pk and review.op_slot(self.instance.pk):
            raise forms.ValidationError(
                "De conceptversie ligt ter inzage bij een reviewteam. Roep hem eerst terug voordat je publiceert. "
                "Is er een dringende fout in de gepubliceerde versie? Gebruik dan 'Corrigeer de gepubliceerde versie'."
            )

    def _gepubliceerde_tekst_houden(self, data):
        """Archiveren met een conceptversie: de gepubliceerde tekst blijft staan (bevinding 15).

        Het scherm toont de conceptversie. Zonder deze regel kwam bij *Gearchiveerd* de concepttekst in het
        artikel terecht, zonder versie. De conceptversie zelf blijft bewaard.
        """
        a = self.instance
        if not a.pk or a.status != Status.GEPUBLICEERD or self.conceptversie is None:
            return
        for veld in ("titel", "samenvatting", "inhoud", "soort", "eigenaar", "herzien_voor", "omgeving"):
            data[veld] = getattr(a, veld)
        data["clusters"] = a.clusters.all()
        data["zaaktypen"] = a.zaaktypen.all()
        data["tags_tekst"] = ", ".join(a.tags.values_list("naam", flat=True))

    def _controleer_eerste_publicatie(self, data):
        """Laatste controle voordat een artikel voor het eerst zichtbaar wordt voor medewerkers.

        De regel zelf staat in `diensten.problemen_eerste_publicatie`, zodat de lijstactie Publiceren
        hem ook gebruikt; hier worden de meldingen alleen aan de juiste velden gehangen.
        """
        if data.get("status") != Status.GEPUBLICEERD or self.instance.versie:
            return
        for veld, melding in diensten.problemen_eerste_publicatie(
            titel=data.get("titel") or "",
            samenvatting=data.get("samenvatting") or "",
            inhoud=data.get("inhoud") or "",
        ).items():
            self.add_error(veld, melding)

    def _controleer_omvang(self, data):
        inhoud = data.get("inhoud") or ""
        if len(inhoud.encode("utf-8")) > MAX_INHOUD:
            mb = MAX_INHOUD / (1024 * 1024)
            self.add_error(
                "inhoud",
                f"Dit artikel is te groot om op te slaan (grens: {mb:.0f} MB). Splits het op in meerdere "
                "artikelen, of verwijder meegeplakte opmaak uit Word.",
            )

    def _controleer_dubbele_titel(self, data):
        """Voorkom dat dubbelklikken of de terugknop hetzelfde artikel twee keer aanmaakt."""
        if self.instance.pk:
            return
        titel, omgeving = data.get("titel"), data.get("omgeving")
        if not titel or not omgeving:
            return
        # Dezelfde normalisatie voor het slot als voor de controle eronder. Stonden ze uit elkaar, dan
        # namen "Melding  registreren" (dubbele spatie) en "Melding registreren" wel hetzelfde slot,
        # maar gold de een niet als dubbel van de ander.
        genormaliseerd = " ".join(titel.split())
        sleutel = genormaliseerd.lower()
        # Een adviesslot op titel+omgeving, zodat twee gelijktijdige verzoeken (dubbelklik) niet
        # allebei "bestaat nog niet" zien. Het slot geldt tot het einde van de transactie, dus het
        # tweede verzoek wacht tot het eerste is weggeschreven en vindt het artikel dan wél.
        diensten.slot(f"artikel:{omgeving.pk}:{sleutel}")
        # Vergelijken op de genormaliseerde titel: anders is "Melding  registreren" geen dubbele van
        # "Melding registreren", terwijl het voor een lezer hetzelfde artikel is.
        bestaand = next(
            (
                a
                for a in Artikel.objects.filter(omgeving=omgeving, titel__icontains=genormaliseerd.split()[0])
                if " ".join(a.titel.split()).lower() == sleutel
            ),
            None,
        )
        if bestaand:
            self.add_error(
                "titel",
                f"Er bestaat in deze omgeving al een artikel met deze titel (nummer {bestaand.pk}). "
                "Bedoelde je dat artikel te bewerken? Kies anders een andere titel.",
            )

    def _controleer_conflict(self, data):
        """Is het artikel sinds het openen van dit scherm door iemand anders opgeslagen?

        Zonder deze controle zou de laatste opslag de wijzigingen van de ander stilletjes
        overschrijven. We weigeren dan liever, zodat de redacteur zijn tekst nog in de editor heeft
        staan en zelf kan samenvoegen.
        """
        if not self.instance.pk:
            return
        # select_for_update: zonder vergrendeling lezen twee gelijktijdige opslagen allebei nog de oude
        # waarde en komen ze er allebei doorheen, waarna de laatste de ander stil overschrijft. Met de
        # vergrendeling wacht de tweede transactie tot de eerste klaar is en ziet hij de nieuwe waarde.
        # De admin draait de hele opslag al in één transactie, dus het slot blijft staan tot na het schrijven.
        with transaction.atomic():
            huidig = (
                Artikel.objects.select_for_update()
                .filter(pk=self.instance.pk)
                .values_list("gewijzigd_op", flat=True)
                .first()
            )
        if huidig is None:
            return
        geladen = (data.get("geladen_stempel") or "").strip()
        if not geladen:
            # Geen stempel betekent niet "geen controle": het scherm is dan onbetrouwbaar (oude pagina
            # uit de cache, formulier van buitenaf). Weigeren is hier veiliger dan doorlaten.
            raise forms.ValidationError(
                "Dit scherm kon niet worden gecontroleerd op tussentijdse wijzigingen; je wijzigingen "
                "zijn niet opgeslagen. Kopieer je tekst, open het artikel opnieuw en plak hem terug."
            )
        if geladen == stempel_van_waarde(huidig):
            return
        door = ""
        laatste = (
            ArtikelVersie.objects.filter(artikel_id=self.instance.pk)
            .select_related("gepubliceerd_door")
            .order_by("-versie")
            .first()
        )
        if laatste and laatste.gepubliceerd_door:
            naam = laatste.gepubliceerd_door.get_full_name() or laatste.gepubliceerd_door.get_username()
            door = f" door {naam}"
        tijd = date_format(timezone.localtime(huidig), "j F Y H:i")
        raise forms.ValidationError(
            f"Dit artikel is op {tijd}{door} opgeslagen terwijl jij het openhad. Je wijzigingen zijn "
            "niet opgeslagen; ze staan nog in dit scherm. Open het artikel in een nieuw tabblad om te "
            "zien wat er nu staat, zet je wijzigingen over en sla daarna opnieuw op."
        )


def stempel_van_waarde(gewijzigd_op) -> str:
    return gewijzigd_op.isoformat() if gewijzigd_op else ""


def stempel_van(artikel) -> str:
    return stempel_van_waarde(getattr(artikel, "gewijzigd_op", None))


class WordImportForm(forms.Form):
    bestand = forms.FileField(label="Word-document (.docx)")
    omgeving = forms.ModelChoiceField(queryset=Omgeving.objects.all(), label="Omgeving")
    soort = forms.ChoiceField(choices=Soort.choices, initial=Soort.WERKINSTRUCTIE, label="Soort")
    # Bewust twee losse keuzes, standaard uit. De opmaak in een Word-document zegt niet betrouwbaar wat
    # de bedoeling was, dus de redacteur bepaalt per document of hij deze omzettingen wil. Je laatste
    # keuze staat de volgende keer alvast goed.
    kop_als_titel = forms.BooleanField(
        required=False,
        label="Gebruik de eerste kop in het document als titel",
        help_text="Anders wordt de bestandsnaam de titel. De kop verdwijnt dan uit de tekst, zodat de "
        "titel er niet twee keer staat.",
    )
    tabelkoprij = forms.BooleanField(
        required=False,
        label="Eerste rij van een tabel als koprij",
        help_text="Maakt van de eerste rij van elke tabel een koprij. Handig bij tabellen met kolomnamen, "
        "onhandig bij tabellen die meteen met gegevens beginnen.",
    )

    def clean_bestand(self):
        f = self.cleaned_data["bestand"]
        if not f.name.lower().endswith(".docx"):
            raise forms.ValidationError(
                "Alleen .docx-bestanden (Word 2007 of nieuwer). Sla een .doc of PDF eerst op als .docx."
            )
        if f.size > 20 * 1024 * 1024:
            raise forms.ValidationError("Het bestand is groter dan 20 MB.")
        return f


def _eenvoudig_afronden(context, obj, gepubliceerd, mag):
    """Afronden voor een nieuw of nog nooit gepubliceerd artikel en voor nieuwsberichten (1.25.0): dezelfde knop als
    bij een gepubliceerd artikel, met minder keuzes (opslaan als concept, publiceren, afbreken)."""
    if context.get("kb_afronden") or not mag:
        return
    from .werkoverzicht import werkplek_url

    context["kb_afronden"] = {
        "eenvoudig": True,
        "nieuw": obj is None or not obj.pk,
        "gepubliceerd": gepubliceerd,
        "spoed": False,
        "op_slot": False,
        "concept": False,
        "teams": [],
        "werkplek": werkplek_url(),
        "akkoord": False,
    }


@admin.register(Artikel)
class ArtikelAdmin(RedactieRechtenMixin, admin.ModelAdmin):
    form = ArtikelForm
    list_display = [
        "titel",
        "nummer",
        "soort",
        "status",
        "versie_label",
        "omgeving",
        "gepubliceerd_op",
        "nakijken",
        "bekijk",
    ]
    list_filter = ["status", "soort", "omgeving", HerzieningFilter, "clusters", "zaaktypen"]
    search_fields = ["titel", "samenvatting", "inhoud", "=id"]
    # Clusters als vinkjes: het dubbele keuzevak van Django sprak half Engels ("Choose all") en is voor
    # een handvol clusters overbodig (functionele review 11 november, B7). Zaaktypen kunnen er veel zijn.
    filter_horizontal = ["zaaktypen"]
    inlines = [VersieInline]
    readonly_fields = ["versie", "gepubliceerd_op", "link"]
    actions = ["publiceren", "archiveren", "nagekeken"]
    change_list_template = "admin/kennisbank/artikel/change_list.html"
    change_form_template = "admin/kennisbank/artikel/change_form.html"
    fieldsets = [
        (
            None,
            {"fields": ["titel", "samenvatting", "inhoud", "geladen_stempel", "geladen_concept", "al_gepubliceerd"]},
        ),
        ("Eigenschappen", {"fields": ["soort", "omgeving", "eigenaar", "herzien_voor", "link"]}),
        ("Vindbaarheid", {"fields": ["clusters", "tags_tekst", "zaaktypen"]}),
        (
            "Publicatie",
            {
                "fields": [
                    "status",
                    "wijzigingstoelichting",
                    "kleine_correctie",
                    "nieuwsbericht",
                ]
            },
        ),
        # Eigen groep, zodat het bewerkscherm hem in het paneel Geschiedenis zet (1.24.0).
        ("Versie", {"fields": ["versie", "gepubliceerd_op"]}),
    ]

    class Media:
        # Het bewerkscherm voor artikelen (1.22.0): de editor Tiptap en de nieuwe indeling.
        css = {
            "all": [
                "kennisbank/fonts.css",
                "kennisbank/beheer-editor.css",
                "kennisbank/artikel-scherm.css",
                "kennisbank/voorstellen-lade.css",
            ]
        }
        js = [
            "kennisbank/vendor/tiptap/tiptap.min.js",
            "kennisbank/artikel-editor.js",
            "kennisbank/artikel-scherm.js",
            "kennisbank/beheer-editor.js",
            "kennisbank/voorstellen-lade.js",
        ]

    def get_urls(self):
        eigen = [
            path(
                "importeren-word/",
                self.admin_site.admin_view(self.importeren_word),
                name="kennisbank_artikel_importeren_word",
            ),
            path("voorbeeld/", self.admin_site.admin_view(self.voorbeeld), name="kennisbank_artikel_voorbeeld"),
            path(
                "<int:pk>/versie/<int:versie>/",
                self.admin_site.admin_view(self.versie_bekijken),
                name="kennisbank_artikel_versie",
            ),
            path(
                "<int:pk>/bewerkclaim/",
                self.admin_site.admin_view(self.bewerkclaim),
                name="kennisbank_artikel_bewerkclaim",
            ),
            path(
                "<int:pk>/ter-inzage/",
                self.admin_site.admin_view(self.ter_inzage),
                name="kennisbank_artikel_ter_inzage",
            ),
            path(
                "<int:pk>/voorstellen-afhandelen/",
                self.admin_site.admin_view(self.voorstellen_afhandelen),
                name="kennisbank_artikel_voorstellen_afhandelen",
            ),
            path(
                "<int:pk>/terugroepen/",
                self.admin_site.admin_view(self.terugroepen),
                name="kennisbank_artikel_terugroepen",
            ),
            path(
                "<int:pk>/conceptversie/weggooien/",
                self.admin_site.admin_view(self.concept_weggooien),
                name="kennisbank_artikel_concept_weggooien",
            ),
            path(
                "<int:pk>/conceptversie/bekijken/",
                self.admin_site.admin_view(self.concept_bekijken),
                name="kennisbank_artikel_concept_bekijken",
            ),
            path("kladversie/", self.admin_site.admin_view(self.kladversie), name="kennisbank_artikel_klad_nieuw"),
            path(
                "<int:pk>/kladversie/",
                self.admin_site.admin_view(self.kladversie),
                name="kennisbank_artikel_klad",
            ),
            path(
                "kladversie/<int:klad>/bekijken/",
                self.admin_site.admin_view(self.kladversie_bekijken),
                name="kennisbank_artikel_klad_bekijken",
            ),
        ]
        return eigen + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        """Een waarschuwing bovenaan de lijst als er artikelen zijn waarvan de nakijkdatum is verstreken.

        Alleen over de artikelen die deze redacteur mag zien, en niet als hij al op dat filter staat.
        """
        eigen = self.get_queryset(request)
        extra = extra_context or {}
        extra.setdefault("title", "Artikelen")  # 1.31.0 (M15): niet "Selecteer artikel om te wijzigen"
        extra["mijn_kladversies"] = Kladversie.objects.filter(
            gebruiker=request.user, afgesloten_op__isnull=True
        ).count()
        if not request.GET.get("herziening"):
            vandaag = timezone.localdate()
            extra["te_herzien"] = diensten.te_herzien(eigen).count()
            extra["herzien_binnenkort"] = eigen.filter(
                status=Status.GEPUBLICEERD,
                herzien_voor__gte=vandaag,
                herzien_voor__lte=vandaag + datetime.timedelta(days=HERZIENING_BINNENKORT),
            ).count()
        return super().changelist_view(request, extra)

    def bewerkclaim(self, request, pk):
        """Hartslag van het bewerkscherm: verleng mijn claim en zeg wie er nog meer in dit artikel zit.

        Dit is meteen de controle op de beveiligingscode (CSRF): mislukt dit verzoek met 403, dan weet
        het bewerkscherm dat de code verlopen is en kan het dat melden vóórdat de redacteur opslaat.
        """
        from django.core.exceptions import PermissionDenied

        # Via get_queryset, want has_change_permission kijkt niet naar het object zelf: zo geldt
        # dezelfde beperking per omgeving als overal in het beheer.
        artikel = self.get_queryset(request).filter(pk=pk).first()
        if artikel is None or not self.has_change_permission(request, artikel):
            raise PermissionDenied
        if request.method != "POST":
            raise PermissionDenied
        if request.POST.get("stoppen"):
            diensten.claim_opheffen(artikel, request.user)
            return JsonResponse({"anderen": []})
        anderen = diensten.claim_vernieuwen(artikel, request.user)
        return JsonResponse(
            {
                "anderen": [
                    {"naam": c.naam, "sinds": date_format(timezone.localtime(c.begonnen_op), "H:i")} for c in anderen
                ],
                # Het stempel van dít moment. De editor leest het niet; het staat erin zodat een
                # toekomstige hartslag het verborgen veld kan bijwerken als niemand anders iets heeft
                # opgeslagen. Haal het weg als die functie er niet komt.
                "stempel": stempel_van(artikel),
            }
        )

    def kladversie(self, request, pk=None):
        """Kladversie van dit artikel (of van een nieuw artikel als pk leeg is) ophalen, opslaan of weggooien.

        GET  -> mijn kladversie, of wanneer hij is afgesloten, plus de kladversies van collega's.
        POST -> velden (JSON) en basis_stempel opslaan; met weggooien=1 afsluiten zonder op te slaan.
        """
        from django.core.exceptions import PermissionDenied

        from .rechten import rechten

        if pk is None:
            if not self.has_add_permission(request):
                raise PermissionDenied
            artikel = None
        else:
            # Via get_queryset, net als bij de bewerkclaim: zo geldt de beperking per omgeving.
            artikel = self.get_queryset(request).filter(pk=pk).first()
            if artikel is None or not self.has_change_permission(request, artikel):
                raise PermissionDenied
        r = rechten(request)
        if request.method == "POST":
            if request.POST.get("weggooien"):
                diensten.klad_afsluiten(request.user, artikel)
                return JsonResponse({"ok": True, "server_nu": timezone.now().isoformat()})
            try:
                velden = json.loads(request.POST.get("velden") or "{}")
            except ValueError:
                return JsonResponse({"fout": "De kladversie kon niet worden gelezen."}, status=400)
            geopend_op = parse_datetime(request.POST.get("geopend_op") or "")
            try:
                rij = diensten.klad_opslaan(
                    request.user,
                    artikel,
                    velden,
                    request.POST.get("basis_stempel", ""),
                    redactie_omgevingen=r.redactie_omgevingen,
                    geopend_op=geopend_op,
                )
            except diensten.KladAfgesloten:
                return JsonResponse({"afgesloten": True}, status=409)
            return JsonResponse(
                {"ok": True, "bijgewerkt_op": rij.bijgewerkt_op.isoformat(), "tijd": self._klad_tijd(rij.bijgewerkt_op)}
            )
        if request.method != "GET":
            raise PermissionDenied
        rij = diensten.klad_van(request.user, artikel)
        anderen = []
        if artikel is not None:
            anderen = [
                {
                    "naam": k.naam,
                    "tijd": self._klad_tijd(k.bijgewerkt_op),
                    "url": reverse("admin:kennisbank_artikel_klad_bekijken", args=[k.pk]),
                }
                for k in diensten.zichtbare_kladversies(request.user, r)
                .filter(artikel=artikel)
                .exclude(gebruiker=request.user)
            ]
        return JsonResponse(
            {
                "server_nu": timezone.now().isoformat(),
                "sleutel": f"kb.klad.{request.user.pk}.{artikel.pk if artikel else 'nieuw'}",
                "bewaardagen": settings.KB_KLADVERSIE_DAGEN,
                "mijn": (
                    {
                        "velden": rij.velden,
                        "basis_stempel": rij.basis_stempel,
                        "bijgewerkt_op": rij.bijgewerkt_op.isoformat(),
                        "tijd": self._klad_tijd(rij.bijgewerkt_op),
                    }
                    if rij and rij.open
                    else None
                ),
                "afgesloten_op": rij.afgesloten_op.isoformat() if rij and not rij.open else None,
                "huidig_stempel": stempel_van(artikel) if artikel else "",
                "anderen": anderen,
            }
        )

    @staticmethod
    def _klad_tijd(moment) -> str:
        """'14:32' voor vandaag, anders '8 nov 14:32'."""
        lokaal = timezone.localtime(moment)
        if lokaal.date() == timezone.localdate():
            return date_format(lokaal, "H:i")
        return date_format(lokaal, "j M H:i")

    def kladversie_bekijken(self, request, klad):
        """De kladversie van een collega lezen (of je eigen), zonder hem over te nemen."""
        from django.http import Http404

        from .inhoud import schoon
        from .models import Kladversie
        from .rechten import rechten

        rij = Kladversie.objects.filter(pk=klad, afgesloten_op__isnull=True).select_related("gebruiker").first()
        # 404 in plaats van 403: verraad niet dat er in een andere omgeving een kladversie bestaat.
        if rij is None or not diensten.mag_klad_zien(request.user, rechten(request), rij):
            raise Http404("Deze kladversie bestaat niet (meer).")
        velden = rij.velden or {}
        return render(
            request,
            "kennisbank/voorbeeld.html",
            {
                "app_naam": settings.KB_APP_NAAM,
                "vaste_inhoud": {
                    "titel": velden.get("titel", ""),
                    "samenvatting": velden.get("samenvatting", ""),
                    "soort": velden.get("soort", ""),
                    # De inhoud komt rauw uit de browser van de schrijver: eerst door dezelfde
                    # schoonmaak als een gepubliceerd artikel, voordat een collega hem te zien krijgt.
                    "inhoud": schoon(velden.get("inhoud", "")),
                },
                "vaste_regel": (
                    f"kladversie van {rij.naam} · laatst bijgewerkt {self._klad_tijd(rij.bijgewerkt_op)} · "
                    "niet opgeslagen en niet zichtbaar voor medewerkers"
                ),
            },
        )

    def voorbeeld(self, request):
        """Lege voorbeeldpagina voor in het splitscreen; de inhoud komt via postMessage uit de editor."""
        if not self.has_change_permission(request):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        return render(request, "kennisbank/voorbeeld.html", {"app_naam": settings.KB_APP_NAAM})

    def versie_bekijken(self, request, pk, versie):
        """De tekst van een eerdere versie, zoals medewerkers die toen zagen.

        We tonen de opgeslagen momentopname, niet de huidige tekst: dat is precies waarvoor de
        versiegeschiedenis bestaat (Archiefwet, "welke instructie gold er toen").
        """
        from django.core.exceptions import PermissionDenied
        from django.http import Http404

        artikel = self.get_queryset(request).filter(pk=pk).first()
        if artikel is None or not self.has_view_permission(request, artikel):
            raise PermissionDenied
        rij = artikel.versies.filter(versie=versie).first()
        if rij is None:
            raise Http404("Deze versie bestaat niet.")
        momentopname = rij.inhoud if isinstance(rij.inhoud, dict) else {}
        door = rij.gepubliceerd_door
        naam = (door.get_full_name() or door.get_username()) if door else "onbekend"
        return render(
            request,
            "kennisbank/voorbeeld.html",
            {
                "app_naam": settings.KB_APP_NAAM,
                "vaste_inhoud": {
                    "titel": momentopname.get("titel", artikel.titel),
                    "samenvatting": momentopname.get("samenvatting", ""),
                    "soort": momentopname.get("soort", artikel.soort),
                    "inhoud": momentopname.get("inhoud", ""),
                },
                "vaste_regel": (
                    f"versie {rij.versie} · gepubliceerd {date_format(rij.gepubliceerd_op, 'j F Y')} "
                    f"door {naam}" + (f" · {rij.toelichting}" if rij.toelichting else "")
                ),
                "vaste_titelbalk": f"Versie {rij.versie}",
            },
        )

    def importeren_word(self, request):
        """Upload een .docx; het wordt een concept-artikel met secties. Daarna door naar het bewerkscherm."""
        if not self.has_add_permission(request):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        profiel = diensten.profiel(request.user)
        form = WordImportForm(
            request.POST or None,
            request.FILES or None,
            # De keuzes van de vorige import staan alvast goed; wijzigen doet de redacteur zelf.
            initial={
                "kop_als_titel": profiel.import_kop_als_titel,
                "tabelkoprij": profiel.import_tabelkoprij,
                "omgeving": enige_omgeving(request),
            },
        )
        if not request.user.is_superuser:
            form.fields["omgeving"].queryset = Omgeving.objects.filter(pk__in=self._omgevingen(request))
        if request.method == "POST" and form.is_valid():
            kop_als_titel = bool(form.cleaned_data["kop_als_titel"])
            tabelkoprij = bool(form.cleaned_data["tabelkoprij"])
            if (profiel.import_kop_als_titel, profiel.import_tabelkoprij) != (kop_als_titel, tabelkoprij):
                profiel.import_kop_als_titel = kop_als_titel
                profiel.import_tabelkoprij = tabelkoprij
                profiel.save(update_fields=["import_kop_als_titel", "import_tabelkoprij"])
            try:
                gelezen = lees_docx(
                    form.cleaned_data["bestand"],
                    form.cleaned_data["bestand"].name,
                    kop_als_titel=kop_als_titel,
                    tabelkoprij=tabelkoprij,
                )
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
                    f"'{gelezen.titel}' is ingelezen als concept; medewerkers zien nog niets. Vul de samenvatting "
                    "in, controleer de titel en de secties, en kies Afronden als je klaar bent.",
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

    @admin.display(description="Nakijken voor", ordering="herzien_voor")
    def nakijken(self, obj):
        """De herzieningsdatum, met kleur zodra hij in zicht komt of verstreken is."""
        if not obj.herzien_voor:
            return format_html('<span style="color:var(--body-quiet-color)">—</span>')
        dagen = (obj.herzien_voor - timezone.localdate()).days
        datum = date_format(obj.herzien_voor, "j M Y")
        if obj.status != Status.GEPUBLICEERD:
            return format_html('<span style="color:var(--body-quiet-color)">{}</span>', datum)
        if dagen < 0:
            return format_html('<b style="color:#a6192e">{} · {} dagen te laat</b>', datum, -dagen)
        if dagen <= HERZIENING_BINNENKORT:
            return format_html('<span style="color:#8a5a00">{} · over {} dagen</span>', datum, dagen)
        return datum

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "omgeving" and not request.user.is_superuser:
            kwargs["queryset"] = Omgeving.objects.filter(pk__in=self._omgevingen(request))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "clusters":
            kwargs["widget"] = Vinkjes
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    # --- Conceptversie ------------------------------------------------------------------

    @staticmethod
    def _kan_concept(obj) -> bool:
        """Een conceptversie bestaat alleen naast een gepubliceerde versie."""
        return bool(obj and obj.pk and obj.versie and obj.status == Status.GEPUBLICEERD)

    @staticmethod
    def _concept_van(obj):
        if not (obj and obj.pk):
            return None
        return Conceptversie.objects.filter(artikel=obj).select_related("gestart_door", "bijgewerkt_door").first()

    def get_form(self, request, obj=None, change=False, **kwargs):
        Form = super().get_form(request, obj, change=change, **kwargs)
        als_concept = request.method == "POST" and "_conceptversie" in request.POST and self._kan_concept(obj)
        if als_concept:
            request._kb_als_concept = True
        concept = self._concept_van(obj)
        # Spoedcorrectie (reviewpunt 12): de gepubliceerde versie aanpassen terwijl er een conceptversie
        # is. Het formulier opent dan de gepubliceerde tekst; de conceptversie blijft ongewijzigd.
        spoed = request.GET.get("spoed") == "1" and concept is not None and not als_concept
        if spoed:
            request._kb_spoed = True
        return type(
            Form.__name__,
            (Form,),
            {"als_concept": als_concept, "conceptversie": None if spoed else concept, "spoed": spoed},
        )

    def _mag_lade(self, request, obj) -> bool:
        return self.has_change_permission(request, obj) and rechten(request).mag_redigeren(obj)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj is not None:
            concept = self._concept_van(obj)
            extra["kb_kan_concept"] = self._kan_concept(obj)
            if self._mag_lade(request, obj):
                from . import review as _review

                extra["kb_lade"] = lade.lade_gegevens(
                    obj,
                    request.user,
                    request.GET.get("voorstel"),
                    op_slot=_review.op_slot(obj.pk),
                    post=request.POST if request.method == "POST" else None,
                    akkoord=_review.akkoord_voorstellen(obj),
                )
                open_pk = extra["kb_lade"]["open"]
                if open_pk:
                    # Geopend vanuit de werkbak: telt als gezien (de stip in de werkbak gaat weg).
                    Verbetervoorstel.objects.filter(pk=open_pk, eigenaar=request.user).update(
                        eigenaar_gezien_op=timezone.now()
                    )
            extra["kb_meegenomen"] = [
                {"titel": v.tekst[:90], "url": reverse("beheer-voorstel", args=[v.pk])}
                for v in Verbetervoorstel.objects.filter(artikel=obj, in_conceptversie=True, status__in=OPEN_VOORSTEL)
            ]
            if request.GET.get("spoed") == "1" and concept is not None:
                # Spoedcorrectie: de gepubliceerde versie, niet de conceptversie (reviewpunt 12).
                from . import review

                extra["kb_spoed"] = True
                extra["kb_spoed_op_slot"] = review.op_slot(obj.pk)
                extra["kb_concept_url"] = reverse("admin:kennisbank_artikel_change", args=[obj.pk])
                concept = None
            extra["kb_concept"] = concept
            if concept is not None:
                extra["kb_concept_gestart_door"] = diensten.naam_van(concept.gestart_door)
                extra["kb_concept_bijgewerkt_door"] = diensten.naam_van(concept.bijgewerkt_door)
                # Collega's die aan deze conceptversie werkten: wie publiceert, bevestigt eerst (punt 4.3).
                extra["kb_concept_collegas"] = " en ".join(
                    sorted(
                        {
                            diensten.naam_van(u)
                            for u in (concept.gestart_door, concept.bijgewerkt_door)
                            if u and u.pk != request.user.pk
                        }
                    )
                )
                extra["kb_concept_artikel_gewijzigd"] = concept.basis_stempel != stempel_van(obj)
                extra["kb_concept_bekijken"] = reverse("admin:kennisbank_artikel_concept_bekijken", args=[obj.pk])
                from . import review

                if review.gebruikt_review(obj):
                    stand = review.stand(obj)
                    voor = set(review.voorgevulde_teams(obj).values_list("pk", flat=True))
                    extra["kb_review"] = stand
                    extra["kb_terugroep_vraag"] = review.terugroep_vraag(stand)
                    extra["kb_balk_stand"] = review.balk_stand(stand)
                    # Stap D: de opmerkingen voor het live voorbeeld in het volledig scherm.
                    extra["kb_opmerkingen"] = [
                        {
                            "nr": nr,
                            "wie": o.inzage.team.naam
                            + " · "
                            + (diensten.naam_van(o.auteur) if o.auteur_id else "reviewer"),
                            "wanneer": date_format(timezone.localtime(o.moment), "j F H:i"),
                            "tekst": o.tekst,
                            "citaat": o.citaat,
                            # Teruggeroepen terwijl het team nog bezig was: misschien niet compleet.
                            "voorlopig": o.inzage.status == InzageStatus.TERUGGEROEPEN,
                        }
                        for nr, o in enumerate(
                            # Van de laatste ronde, en pas als het team heeft gereageerd: zolang een stuk ter
                            # inzage ligt, zijn de opmerkingen nog van de reviewer.
                            ReviewOpmerking.objects.filter(
                                inzage__in=[r.pk for r in stand["rijen"] if r.status != InzageStatus.TER_INZAGE]
                            )
                            .select_related("inzage__team", "auteur")
                            .order_by("moment", "pk"),
                            start=1,
                        )
                    ]
                    extra["kb_review_teams"] = [
                        {"pk": t.pk, "naam": t.naam, "gekozen": t.pk in voor}
                        for t in obj.omgeving.reviewteams.order_by("naam")
                    ]
                    extra["kb_ter_inzage_url"] = reverse("admin:kennisbank_artikel_ter_inzage", args=[obj.pk])
                    extra["kb_terugroepen_url"] = reverse("admin:kennisbank_artikel_terugroepen", args=[obj.pk])
                extra["kb_concept_weggooien"] = reverse("admin:kennisbank_artikel_concept_weggooien", args=[obj.pk])
            if extra["kb_kan_concept"]:
                # De knop Afronden (bouwlijst 1.21.0): wat het keuzevenster mag aanbieden.
                from . import review
                from .werkoverzicht import werkplek_url

                spoed = bool(extra.get("kb_spoed"))
                op_slot = bool(extra.get("kb_review", {}).get("op_slot")) if not spoed else False
                teams = []
                if not spoed and not op_slot and review.gebruikt_review(obj):
                    voor = set(review.voorgevulde_teams(obj).values_list("pk", flat=True))
                    teams = [
                        {"pk": t.pk, "naam": t.naam, "gekozen": t.pk in voor}
                        for t in obj.omgeving.reviewteams.order_by("naam")
                    ]
                extra["kb_afronden"] = {
                    "spoed": spoed,
                    "op_slot": op_slot,
                    "concept": concept is not None,
                    "teams": teams,
                    "werkplek": werkplek_url(),
                    "akkoord": bool(extra.get("kb_review", {}).get("label")),
                }
        return super().change_view(request, object_id, form_url, extra)

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        # Nog nooit gepubliceerd (of nieuw): ook één knop Afronden (1.25.0).
        if not self._kan_concept(obj):
            mag = self.has_add_permission(request) if add else self.has_change_permission(request, obj)
            _eenvoudig_afronden(context, obj, gepubliceerd=False, mag=mag)
        return super().render_change_form(request, context, add=add, change=change, form_url=form_url, obj=obj)

    def save_model(self, request, obj, form, change):
        if getattr(form, "als_concept", False):
            # Het artikel zelf blijft zoals het is; alleen de conceptversie wordt bijgewerkt.
            try:
                diensten.concept_opslaan(
                    obj,
                    request.user,
                    diensten.concept_velden(form.cleaned_data),
                    form.cleaned_data.get("geladen_concept"),
                )
            except diensten.ConceptOpSlot:
                request._kb_concept_conflict = True
                request._kb_concept_op_slot = True
            except diensten.ConceptConflict:
                request._kb_concept_conflict = True
            return
        super().save_model(request, obj, form, change)

    def log_change(self, request, obj, message):
        if getattr(request, "_kb_als_concept", False):
            if getattr(request, "_kb_concept_conflict", False):
                return None
            message = "Conceptversie opgeslagen."
        return super().log_change(request, obj, message)

    def response_change(self, request, obj):
        if getattr(request, "_kb_als_concept", False):
            if getattr(request, "_kb_concept_op_slot", False):
                self.message_user(
                    request,
                    "De conceptversie ligt ter inzage bij een reviewteam en staat op slot. Je wijzigingen zijn NIET "
                    "opgeslagen; ze staan nog in de kladversie in deze browser. Roep de conceptversie eerst terug "
                    "als je verder wilt werken.",
                    messages.ERROR,
                )
            elif getattr(request, "_kb_concept_conflict", False):
                self.message_user(
                    request,
                    "Een collega heeft de conceptversie opgeslagen, gepubliceerd of weggegooid terwijl jij het "
                    "artikel openhad. Je wijzigingen zijn NIET opgeslagen; ze staan nog in de kladversie in deze "
                    "browser. Kijk wat er nu staat en kies dan of je verder wilt gaan met je kladversie.",
                    messages.ERROR,
                )
            elif request.POST.get("kb_daarna_ter_inzage") == "1":
                # Afronden → Ter inzage aanbieden: eerst opgeslagen (hierboven), dan ter inzage. Zo gaat
                # altijd de tekst van het scherm naar het team (review 1.20.1, bevinding 4).
                self._ter_inzage_na_opslaan(request, obj)
            else:
                self.message_user(
                    request,
                    f"Conceptversie opgeslagen. Medewerkers zien nog versie {obj.versie}; zij merken pas iets als "
                    "je publiceert.",
                    messages.SUCCESS,
                )
            return redirect(reverse("admin:kennisbank_artikel_change", args=[obj.pk]))
        if getattr(request, "_kb_meegenomen", False):
            return redirect(reverse("admin:kennisbank_artikel_voorstellen_afhandelen", args=[obj.pk]))
        # Na "Publiceren…" terug naar de werkplek: daar ligt het volgende werk, niet in de lange
        # artikellijst (functionele review 11 november, B9). "Verder bewerken" blijft op het artikel.
        if (
            "_continue" not in request.POST
            and "_addanother" not in request.POST
            and "_saveasnew" not in request.POST
            and rechten(request).is_redacteur
        ):
            from .werkoverzicht import werkplek_url

            obj.refresh_from_db(fields=["versie", "status"])  # de versie is in save_related opgehoogd
            if obj.status == Status.GEPUBLICEERD:
                tekst = f"'{obj.titel}' staat live als versie {obj.versie}. Je bent terug op je werkplek."
            else:
                tekst = f"'{obj.titel}' is opgeslagen ({obj.get_status_display().lower()})."
            self.message_user(request, tekst, messages.SUCCESS)
            return redirect(werkplek_url())
        return super().response_change(request, obj)

    def _ter_inzage_na_opslaan(self, request, obj):
        from . import review

        concept = Conceptversie.objects.filter(artikel=obj).first()
        keuze = [int(t) for t in request.POST.getlist("reviewteams") if t.isdigit()]
        teams = list(obj.omgeving.reviewteams.filter(pk__in=keuze))
        try:
            rijen = review.ter_inzage_geven(obj, request.user, teams, concept.stempel if concept else "")
        except review.ReviewFout as e:
            self.message_user(
                request, f"De conceptversie is opgeslagen, maar ligt nog niet ter inzage: {e}", messages.WARNING
            )
            return
        namen = ", ".join(r.team.naam for r in rijen)
        LogEntry.objects.log_actions(
            request.user.pk, [obj], CHANGE, change_message=f"Conceptversie ter inzage bij {namen}.", single_object=True
        )
        self.message_user(
            request,
            f"Opgeslagen en ter inzage gegeven aan {namen}. De conceptversie staat op slot tot het team reageert of "
            "je hem terugroept.",
            messages.SUCCESS,
        )

    def ter_inzage(self, request, pk):
        """Knop *Ter inzage* in de gele balk: de conceptversie naar één of meer reviewteams."""
        from . import review

        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        obj = get_object_or_404(self.get_queryset(request), pk=pk)
        keuze = [int(t) for t in request.POST.getlist("reviewteams") if t.isdigit()]
        teams = list(obj.omgeving.reviewteams.filter(pk__in=keuze))
        try:
            rijen = review.ter_inzage_geven(obj, request.user, teams, request.POST.get("geladen_concept", ""))
        except review.ReviewFout as e:
            self.message_user(request, str(e), messages.WARNING)
        else:
            namen = ", ".join(r.team.naam for r in rijen)
            LogEntry.objects.log_actions(
                request.user.pk,
                [obj],
                CHANGE,
                change_message=f"Conceptversie ter inzage bij {namen}.",
                single_object=True,
            )
            self.message_user(
                request,
                f"De conceptversie ligt ter inzage bij {namen}. Hij staat op slot tot het team reageert of je hem "
                "terugroept. Publiceren of weggooien kan pas na terugroepen.",
            )
        return redirect(reverse("admin:kennisbank_artikel_change", args=[obj.pk]))

    def voorstellen_afhandelen(self, request, pk):
        """Na publiceren: de meegenomen voorstellen afhandelen met een voorgevuld bericht (reviewpunt 11)."""
        obj = get_object_or_404(self.get_queryset(request), pk=pk)
        qs = (
            Verbetervoorstel.objects.filter(artikel=obj, verwerkt_in_versie__isnull=False, status__in=OPEN_VOORSTEL)
            .select_related("ingediend_door")
            .order_by("ingediend_op")
        )
        if request.method == "POST":
            gedaan = 0
            for v in qs:
                if request.POST.get(f"afhandelen-{v.pk}") != "1":
                    continue
                with transaction.atomic():
                    v = (
                        Verbetervoorstel.objects.select_for_update(of=("self",))
                        .select_related("artikel", "eigenaar")
                        .get(pk=v.pk)
                    )
                    try:
                        diensten.voorstel_afhandelen(
                            v, request.user, VoorstelStatus.VERWERKT, request.POST.get(f"bericht-{v.pk}", "")
                        )
                    except diensten.VoorstelFout as e:
                        self.message_user(request, f"{v.artikel.titel}: {e}", messages.WARNING)
                        continue
                    admin.site._registry[Verbetervoorstel].log_change(
                        request, v, f"Verwerkt in versie {v.verwerkt_in_versie}."
                    )
                    gedaan += 1
            if gedaan:
                self.message_user(request, f"{gedaan} voorstel(len) afgehandeld; de indieners krijgen je bericht.")
            if qs.all().exists():  # .all(): opnieuw vragen, niet de lijst van hierboven
                return redirect(request.path)
            from .werkoverzicht import werkplek_url

            return redirect(werkplek_url())
        from .behandelen import scherm_url

        rijen = [
            {
                "v": v,
                "indiener": diensten.naam_van(v.ingediend_door) if v.ingediend_door_id else "de indiener",
                "bericht": (
                    f"Dank je wel voor je verbetervoorstel. We hebben het verwerkt in versie {v.verwerkt_in_versie} "
                    f"van '{obj.titel}', die nu voor iedereen te zien is."
                ),
                "url": scherm_url(v),
            }
            for v in qs
        ]
        return render(
            request,
            "admin/kennisbank/artikel/voorstellen_afhandelen.html",
            {
                **self.admin_site.each_context(request),
                "title": f"Voorstellen afhandelen: {obj.titel}",
                "artikel": obj,
                "rijen": rijen,
                "artikel_url": reverse("admin:kennisbank_artikel_change", args=[obj.pk]),
            },
        )

    def terugroepen(self, request, pk):
        from . import review

        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        obj = get_object_or_404(self.get_queryset(request), pk=pk)
        if review.terugroepen(obj, request.user):
            LogEntry.objects.log_actions(
                request.user.pk,
                [obj],
                CHANGE,
                change_message="Conceptversie teruggeroepen uit de review.",
                single_object=True,
            )
            self.message_user(request, "De conceptversie is teruggeroepen. Je kunt er weer aan werken.")
        else:
            # Review 1.20.1, bevinding 14: vanaf een verouderd scherm. Zeg wat er intussen gebeurde.
            stand = review.stand(obj)
            wat = {
                InzageStatus.AKKOORD: "heeft intussen akkoord gegeven",
                InzageStatus.TERUGGEGEVEN: "heeft het intussen teruggegeven",
                InzageStatus.TERUGGEROEPEN: "was al teruggeroepen",
            }
            reacties = [f"{r.team.naam} {wat[r.status]}" for r in stand["rijen"] if r.status in wat]
            self.message_user(
                request,
                "Er lag niets meer ter inzage"
                + (": " + " en ".join(reacties) + "." if reacties else ".")
                + " Er is niets veranderd.",
                messages.WARNING,
            )
        return redirect(reverse("admin:kennisbank_artikel_change", args=[obj.pk]))

    def concept_weggooien(self, request, pk):
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        obj = get_object_or_404(self.get_queryset(request), pk=pk)
        try:
            weg = diensten.concept_weggooien(obj)
        except diensten.ConceptTerInzage as e:
            self.message_user(request, str(e), messages.WARNING)
            return redirect(reverse("admin:kennisbank_artikel_change", args=[obj.pk]))
        if weg:
            diensten.klad_afsluiten(request.user, obj)
            LogEntry.objects.log_actions(
                request.user.pk, [obj], CHANGE, change_message="Conceptversie weggegooid.", single_object=True
            )
            for v in getattr(obj, "_kb_niet_meer_meegenomen", []):
                admin.site._registry[Verbetervoorstel].log_change(
                    request, v, "Niet meer meegenomen: de conceptversie is weggegooid."
                )
            self.message_user(request, "De conceptversie is weggegooid. Je ziet weer de gepubliceerde tekst.")
        return redirect(reverse("admin:kennisbank_artikel_change", args=[obj.pk]))

    def concept_bekijken(self, request, pk):
        from .inhoud import schoon

        obj = get_object_or_404(self.get_queryset(request), pk=pk)
        concept = get_object_or_404(Conceptversie, artikel=obj)
        return render(
            request,
            "kennisbank/voorbeeld.html",
            {
                "app_naam": settings.KB_APP_NAAM,
                "vaste_inhoud": {
                    "titel": concept.titel,
                    "samenvatting": concept.velden.get("samenvatting", ""),
                    "soort": concept.velden.get("soort", obj.soort),
                    "inhoud": schoon(concept.velden.get("inhoud", "")),
                },
                "vaste_regel": (
                    f"conceptversie · bijgewerkt {date_format(timezone.localtime(concept.bijgewerkt_op), 'j F Y H:i')} "
                    f"door {diensten.naam_van(concept.bijgewerkt_door)} · gepubliceerd is versie {obj.versie}"
                ),
                "vaste_titelbalk": "Conceptversie",
            },
        )

    def save_related(self, request, form, formsets, change):
        if getattr(form, "als_concept", False):
            # Niets aan het artikel zelf: geen clusters/tags/zaaktypen, geen zoekindex, geen versie.
            for formset in formsets:  # het beheer leest deze lijsten voor zijn logboek
                formset.new_objects, formset.changed_objects, formset.deleted_objects = [], [], []
            diensten.claim_opheffen(form.instance, request.user)
            if not getattr(request, "_kb_concept_conflict", False):
                diensten.klad_afsluiten(request.user, form.instance)
                lade.meenemen_opslaan(request, form.instance)  # 1.26.0: de vinkjes in de lade
            return
        super().save_related(request, form, formsets, change)
        review_regel = ""
        had_concept = False
        spoed = getattr(form, "spoed", False)
        if spoed:
            # De conceptversie (en een lopende review) blijft zoals hij is; ook de kladversie, want daar
            # staat het werk aan de conceptversie in.
            review_regel = "Spoedcorrectie op de gepubliceerde versie; de conceptversie bleef ongewijzigd."
        elif change:
            from . import review

            # Hoe stond de review? Dat komt in de versiegeschiedenis (stap C).
            if form.instance.status == Status.GEPUBLICEERD:
                concept = Conceptversie.objects.filter(artikel=form.instance).first()
                had_concept = concept is not None
                if concept is not None:
                    review_regel = review.samenvatting_bij_publiceren(
                        form.instance, gewijzigd_na_concept=diensten.wijkt_af_van_concept(concept, form.cleaned_data)
                    )
                # Gepubliceerd vanuit dit scherm: de conceptversie is daarmee afgehandeld. Bij archiveren
                # blijft hij bewaard (bevinding 6 en 15); de review stopt dan via het signaal.
                diensten.concept_gepubliceerd(form.instance, request.user)
        diensten.claim_opheffen(form.instance, request.user)  # opgeslagen = niet meer aan het bewerken
        # Opgeslagen = de kladversie is afgehandeld. Bij een nieuw artikel was dat de kladversie
        # "nieuw"; die hoort nu niet meer op het toevoegscherm terug te komen. Niet bij een spoedcorrectie,
        # ook niet als een collega de conceptversie intussen weggooide en dit een gewone publicatie werd
        # (ronde A, review 1.27.0 R1 B8): het spoedscherm blijft van de kladversie af.
        if not spoed and request.GET.get("spoed") != "1":
            diensten.klad_afsluiten(request.user, form.instance if change else None)
        form.instance.tags.set(
            [Tag.objects.get_or_create(naam=n)[0] for n in tags_uit_tekst(form.cleaned_data.get("tags_tekst", ""))]
        )
        diensten.herbouw_secties(form.instance)  # ook de zoekdocumenten, dus ná de tags
        versie = diensten.registreer_publicatie(
            form.instance,
            request.user,
            form.cleaned_data.get("wijzigingstoelichting", ""),
            kleine_correctie=bool(form.cleaned_data.get("kleine_correctie")),
            review=review_regel,
        )
        # Ronde A (review 1.27.0, M3/M4): voorstellen tellen alleen mee in een echte nieuwe versie. Een kleine
        # correctie, of publiceren zonder inhoudelijke wijziging, verwerkt geen voorstellen; dat is één regel
        # voor de gewone weg en de spoedcorrectie.
        telt = bool(versie) and not versie.kleine_correctie
        if change and form.instance.status == Status.GEPUBLICEERD:
            # 1.26.0: de vinkjes *Meenemen in deze versie* in de lade. Bij een spoedcorrectie horen ze bij de
            # versie die nu wordt gepubliceerd, anders volgen ze het gewone meenemen.
            mee = lade.meenemen_opslaan(request, form.instance, spoed=spoed, telt=telt)
            if spoed:
                if telt and mee:
                    Verbetervoorstel.objects.filter(pk__in=mee, status__in=OPEN_VOORSTEL).update(
                        in_conceptversie=False, verwerkt_in_versie=versie.versie
                    )
                    request._kb_meegenomen = True
                elif mee:
                    waarom = "dit een kleine correctie was" if versie else "er geen inhoudelijke wijziging was"
                    messages.warning(
                        request,
                        f"De aangevinkte voorstellen zijn niet meegenomen, omdat {waarom}. "
                        "Ze staan nog open in de lade.",
                    )
            else:
                meegenomen = Verbetervoorstel.objects.filter(
                    artikel=form.instance, in_conceptversie=True, status__in=OPEN_VOORSTEL
                )
                if telt:
                    # Reviewpunt 11: voorstellen die in deze versie zijn meegenomen, krijgen het
                    # versienummer; na het opslaan vraagt de kennisbank of je ze wilt afhandelen.
                    if meegenomen.update(in_conceptversie=False, verwerkt_in_versie=versie.versie):
                        request._kb_meegenomen = True
                else:
                    # De conceptversie is weg (gepubliceerd); wat erin was meegenomen, hangt nergens meer aan.
                    # Zonder conceptversie blijft "meegenomen" staan voor de volgende versie (bevinding 8b).
                    n = (meegenomen.update(in_conceptversie=False) if had_concept else 0) + len(mee)
                    if n:
                        waarom = "dit een kleine correctie was" if versie else "er geen inhoudelijke wijziging was"
                        messages.warning(
                            request,
                            f"{n} meegenomen voorstel{'len' if n > 1 else ''} "
                            f"{'gelden' if n > 1 else 'geldt'} niet als verwerkt, omdat {waarom}. "
                            f"{'Ze staan' if n > 1 else 'Het staat'} weer open in de lade.",
                        )
        if versie:
            if versie.versie == 1:
                messages.info(request, "Gepubliceerd als versie 1.")
                # Niet blokkerend: zonder zaaktype of tag is het artikel gepubliceerd maar slecht
                # vindbaar. Dat is soms de bedoeling, dus we zeggen het en laten het aan de redacteur.
                mist = []
                if not form.instance.zaaktypen.exists():
                    mist.append("geen zaaktype")
                if not form.instance.tags.exists():
                    mist.append("geen tags")
                if mist:
                    messages.warning(
                        request,
                        f"Dit artikel heeft {' en '.join(mist)}. Medewerkers vinden het dan alleen via de "
                        "zoekbalk op woorden uit de tekst, niet via het zaaksysteem of een onderwerp.",
                    )
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

    @admin.action(description="Markeren als nagekeken (nakijkdatum opschuiven)")
    def nagekeken(self, request, queryset):
        """Voor artikelen die nog kloppen: de nakijkdatum opschuiven zonder een nieuwe versie te maken.

        Dit is geen wijziging van de tekst, dus er komt geen versie en geen melding bij medewerkers.
        """
        maanden = settings.KB_HERZIENINGSTERMIJN_MAANDEN
        if maanden <= 0:
            messages.error(
                request,
                "Er is geen herzieningstermijn ingesteld (KB_HERZIENINGSTERMIJN_MAANDEN). "
                "Vul de datum per artikel in, of vraag IT de termijn in te stellen.",
            )
            return
        n, overgeslagen = 0, 0
        for a in queryset:
            # Alleen gepubliceerde artikelen. Zette je de datum ook op een concept, dan bleef die staan
            # bij het publiceren (een datum in de toekomst wordt niet overschreven) en was het eerste
            # herzieningsvenster korter dan de ingestelde termijn.
            if a.status != Status.GEPUBLICEERD:
                overgeslagen += 1
                continue
            a.herzien_voor = None  # leegmaken, zodat de termijn vanaf vandaag opnieuw gaat tellen
            Artikel.objects.filter(pk=a.pk).update(herzien_voor=diensten.herzieningsdatum(a))
            n += 1
        if n:
            messages.success(
                request,
                f"{n} artikel(en) gemarkeerd als nagekeken; de nakijkdatum staat nu {maanden} maanden "
                "vooruit. Er is geen nieuwe versie gemaakt en medewerkers krijgen hiervan geen melding.",
            )
        if overgeslagen:
            messages.warning(
                request,
                f"{overgeslagen} artikel(en) overgeslagen omdat ze niet gepubliceerd zijn. Een concept "
                "krijgt zijn nakijkdatum automatisch bij de eerste publicatie.",
            )

    @admin.action(description="Publiceren")
    def publiceren(self, request, queryset):
        n, zonder_toelichting, onaf = 0, [], []
        for a in queryset:
            # Elke route naar publiceren moet dezelfde regels volgen als het bewerkscherm. Doet deze
            # actie dat niet, dan is zij een achterdeur om die regels te omzeilen — en dat is hier al
            # twee keer gebeurd: eerst bij de verplichte wijzigingstoelichting, daarna bij de controle
            # op een onaf artikel.
            if not a.versie:
                problemen = diensten.problemen_eerste_publicatie(
                    titel=a.titel, samenvatting=a.samenvatting, inhoud=a.inhoud
                )
                if problemen:
                    onaf.append((a, problemen))
                    continue
            # Een inhoudelijke wijziging hoort een toelichting te krijgen, want medewerkers zien die
            # als melding. Via deze lijstactie is er geen veld om er een te typen, dus sturen we de
            # redacteur naar het bewerkscherm.
            if diensten.is_inhoudelijk_gewijzigd(a, diensten.momentopname(a)):
                zonder_toelichting.append(a)
                continue
            a.status = Status.GEPUBLICEERD
            a.save(update_fields=["status", "gewijzigd_op"])
            if diensten.registreer_publicatie(a, request.user, "Gepubliceerd via lijstactie"):
                n += 1
        self.message_user(request, f"{n} artikel(en) gepubliceerd.")
        if zonder_toelichting:
            namen = ", ".join(a.titel for a in zonder_toelichting[:5]) + ("…" if len(zonder_toelichting) > 5 else "")
            self.message_user(
                request,
                f"{len(zonder_toelichting)} artikel(en) niet gepubliceerd omdat de inhoud is gewijzigd "
                f"zonder toelichting: {namen}. Publiceer die via het bewerkscherm, dan kun je aangeven "
                "wat er is veranderd.",
                level=messages.WARNING,
            )
        for a, problemen in onaf[:5]:
            self.message_user(
                request,
                format_html(
                    "<b>{}</b> is nog niet gepubliceerd: {} Open het artikel via "
                    '<a href="{}">het bewerkscherm</a> om dit aan te vullen.',
                    a.titel,
                    " ".join(problemen.values()),
                    reverse("admin:kennisbank_artikel_change", args=[a.pk]),
                ),
                level=messages.WARNING,
            )
        if len(onaf) > 5:
            self.message_user(
                request,
                f"Nog {len(onaf) - 5} artikel(en) zijn om dezelfde reden niet gepubliceerd.",
                level=messages.WARNING,
            )

    @admin.action(description="Archiveren (niet meer zichtbaar voor medewerkers)")
    def archiveren(self, request, queryset):
        # Per object opslaan in plaats van een bulk-update: alleen zo wordt gewijzigd_op bijgewerkt,
        # en alleen dan ziet de conflictcontrole dat dit artikel is veranderd. Met een bulk-update kon
        # een redacteur met een openstaand scherm een zojuist gearchiveerd artikel weer publiceren.
        n = 0
        for a in queryset:
            a.status = Status.GEARCHIVEERD
            a.save(update_fields=["status", "gewijzigd_op"])
            n += 1
        self.message_user(request, f"{n} artikel(en) gearchiveerd. De versiegeschiedenis blijft bewaard.")


class VoorstelOpenFilter(admin.SimpleListFilter):
    """Standaardblik voor een redacteur: wat ligt er nog, en waar wacht de indiener op antwoord?"""

    title = "wat ligt er"
    parameter_name = "ligt"

    def lookups(self, request, model_admin):
        return [
            ("open", "Nog te behandelen"),
            ("wacht", "Indiener heeft als laatste geschreven"),
            ("klaar", "Afgehandeld"),
        ]

    def queryset(self, request, queryset):
        keuze = self.value()
        if keuze == "open":
            return queryset.filter(status__in=[VoorstelStatus.NIEUW, VoorstelStatus.IN_BEHANDELING])
        if keuze == "klaar":
            return queryset.filter(status__in=AFGEHANDELD)
        if keuze == "wacht":
            laatste = (
                VoorstelBericht.objects.filter(voorstel=OuterRef("pk"))
                .order_by("-moment", "-pk")
                .values("van_redactie")[:1]
            )
            return queryset.annotate(_laatste_van_redactie=Subquery(laatste)).filter(_laatste_van_redactie=False)
        return queryset


class BakFilter(admin.SimpleListFilter):
    """In wiens bak ligt het voorstel: de gezamenlijke bak, de mijne, of die van een collega."""

    title = "bak"
    parameter_name = "bak"

    def lookups(self, request, model_admin):
        keuzes = [("gezamenlijk", "Gezamenlijke bak"), ("mijn", "Mijn bak")]
        eigenaren = (
            model_admin.get_queryset(request)
            .exclude(eigenaar__isnull=True)
            .exclude(eigenaar=request.user)
            .values_list("eigenaar_id", "eigenaar__first_name", "eigenaar__last_name", "eigenaar__username")
            .distinct()
        )
        collegas = sorted((f"{v} {a}".strip() or g, pk) for pk, v, a, g in eigenaren)
        keuzes += [(f"u{pk}", f"Bak van {naam}") for naam, pk in collegas]
        return keuzes

    def queryset(self, request, queryset):
        keuze = self.value()
        if keuze == "gezamenlijk":
            # Alleen wat nog opgepakt moet worden; dat telt de startpagina ook (review, bevinding 5).
            return queryset.filter(
                eigenaar__isnull=True, status__in=[VoorstelStatus.NIEUW, VoorstelStatus.IN_BEHANDELING]
            )
        if keuze == "mijn":
            return queryset.filter(eigenaar=request.user)
        if keuze and keuze.startswith("u") and keuze[1:].isdigit():
            return queryset.filter(eigenaar_id=int(keuze[1:]))
        return queryset


class VoorstelForm(forms.ModelForm):
    """Het behandelformulier, met een keuzelijst 'bak' bovenaan.

    De bak is geen gewoon modelveld: verplaatsen loopt via diensten.voorstel_naar_bak, zodat de status
    en de e-mail aan een collega meelopen. Daarom een los formulierveld, verwerkt in save_model.
    """

    # Hoe het voorstel eruitzag toen het scherm werd geopend. Zo weten we wat de redacteur zélf heeft
    # veranderd, los van wat een collega intussen deed (zie clean).
    geladen_eigenaar = forms.CharField(required=False, widget=forms.HiddenInput)
    geladen_status = forms.CharField(required=False, widget=forms.HiddenInput)

    naar_bak = forms.ChoiceField(
        label="Bak",
        required=False,
        help_text="Kies jezelf om het op te pakken, een collega om het toe te wijzen (die krijgt een "
        "e-mail), of 'niemand' om het terug te leggen in de werkvoorraad.",
    )

    class Meta:
        model = Verbetervoorstel
        fields = ["status", "cluster", "verborgen"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        v = self.instance
        keuzes = [("", "— Niemand (ligt in de werkvoorraad)")]
        if v.pk:
            keuzes += [(str(u.pk), diensten.naam_van(u)) for u in diensten.redacteuren_van(v.artikel.omgeving_id)]
            if v.eigenaar_id and str(v.eigenaar_id) not in {k for k, _ in keuzes}:
                # Eigenaar die intussen geen redacteur meer is: wel tonen, anders lijkt het voorstel
                # stil te verhuizen naar de gezamenlijke bak.
                keuzes.append((str(v.eigenaar_id), f"{diensten.naam_van(v.eigenaar)} (geen redacteur meer)"))
        self.fields["naar_bak"].choices = keuzes
        if v.pk and "cluster" in self.fields:
            from .werkoverzicht import clusters_van

            toegestaan = [pk for pk, _ in clusters_van([v.artikel.omgeving_id])]
            if v.cluster_id:
                toegestaan.append(v.cluster_id)
            self.fields["cluster"].queryset = Cluster.objects.filter(pk__in=toegestaan)
            self.fields["cluster"].empty_label = "Algemeen"
        self.fields["naar_bak"].initial = str(v.eigenaar_id or "")
        self.fields["geladen_eigenaar"].initial = str(v.eigenaar_id or "")
        self.fields["geladen_status"].initial = v.status
        if v.pk and not v.is_open:
            self.fields["naar_bak"].disabled = True
            self.fields["naar_bak"].help_text = "Een afgehandeld voorstel blijft bij wie het afhandelde."
            # Afgehandeld is definitief: geen heropenen. Wie iets nieuws ziet, dient een nieuw voorstel
            # in. Berichten aan de indiener kunnen nog wel (functionele review 11 november, besluit Alex).
            self.fields["status"].disabled = True
            self.fields["status"].help_text = (
                "Afgehandeld is definitief. Is er toch iets nieuws, dan dient de indiener een nieuw voorstel in. "
                "Een bericht aan de indiener kan nog wel."
            )
        self.wil_bak = self.wil_status = False

    def clean(self):
        """Alleen doorvoeren wat deze redacteur zelf heeft veranderd, en weigeren als een collega
        precies dat intussen ook heeft veranderd.

        Zonder dit draaide een scherm dat al even openstond stil het werk van een collega terug: Anna
        opent een voorstel en typt een bericht, Bram pakt het intussen op, Anna verstuurt alleen haar
        bericht, en het voorstel stond weer in de gezamenlijke bak (review 10 november, bevinding 2).
        """
        data = super().clean()
        v = self.instance
        if not v.pk or "geladen_status" not in self.data:
            # Zonder de verborgen velden (een oude pagina in de browser): vergelijken met de database.
            self.wil_bak = "naar_bak" in self.changed_data
            self.wil_status = "status" in self.changed_data
            return data
        geladen_eigenaar = data.get("geladen_eigenaar") or ""
        geladen_status = data.get("geladen_status") or ""
        # Vergrendelen tot het einde van het opslaan (het beheer slaat op in één transactie).
        nu = Verbetervoorstel.objects.select_for_update(of=("self",)).select_related("eigenaar").get(pk=v.pk)
        self.wil_bak = (data.get("naar_bak") or "") != geladen_eigenaar and not self.fields["naar_bak"].disabled
        self.wil_status = data.get("status") != geladen_status
        collega = []
        if self.wil_bak and str(nu.eigenaar_id or "") != geladen_eigenaar:
            bak = f"de bak van {diensten.naam_van(nu.eigenaar)}" if nu.eigenaar else "de gezamenlijke bak"
            collega.append(f"het ligt intussen in {bak}")
        if self.wil_status and nu.status != geladen_status:
            collega.append(f"de status is intussen '{nu.get_status_display()}'")
        if collega:
            raise forms.ValidationError(
                "Een collega heeft dit voorstel gewijzigd terwijl jij het openhad: "
                + " en ".join(collega)
                + ". Je wijziging is niet opgeslagen. Open het voorstel opnieuw en kijk of het nog nodig is."
            )
        self.db_stand = nu  # save_model neemt hieruit over wat deze redacteur niet heeft aangeraakt
        self._controleer_afsluitend_bericht(data)
        return data

    def _controleer_afsluitend_bericht(self, data):
        """Wie een voorstel afhandelt, schrijft de indiener erbij waarom (ronde 1, punt 1).

        Anders kreeg de indiener bij 'Afgewezen' zijn laatste tussenbericht ("we kijken ernaar") nog
        eens als antwoord. Het nieuwe bericht staat in de inline eronder; die is hier nog niet
        gevalideerd, dus we kijken naar wat er is ingevuld.
        """
        if not self.wil_status or data.get("status") not in AFGEHANDELD:
            return
        nieuw = [
            waarde
            for sleutel, waarde in self.data.items()
            if sleutel.startswith("berichten-")
            and sleutel.endswith("-tekst")
            and (waarde or "").strip()
            and not self.data.get(sleutel[: -len("tekst")] + "id")
        ]
        if not nieuw:
            self.add_error(
                "status",
                "Schrijf onder 'Gesprek met de indiener' waarom het voorstel is "
                + ("verwerkt" if data.get("status") == VoorstelStatus.VERWERKT else "afgewezen")
                + ". De indiener krijgt dat als antwoord, per melding en per e-mail.",
            )


class VoorstelBerichtInline(admin.TabularInline):
    """Het gesprek tot nu toe, en één lege regel om een bericht toe te voegen."""

    model = VoorstelBericht
    extra = 1
    fields = ["moment", "wie", "tekst"]
    readonly_fields = ["moment", "wie"]
    verbose_name = "bericht"
    verbose_name_plural = "Gesprek met de indiener"

    @admin.display(description="Van")
    def wie(self, obj):
        if not obj or not obj.pk:
            return ""
        return f"{obj.naam} ({'procesmanagement' if obj.van_redactie else 'indiener'})"

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.form.base_fields["tekst"].widget = forms.Textarea(attrs={"rows": 4, "cols": 70})
        formset.form.base_fields["tekst"].help_text = (
            "Een nieuw bericht gaat als melding en e-mail naar de indiener. Gebruik dit ook voor "
            "tussentijdse updates: 'opgepakt, we kijken ernaar met Toezicht'."
        )
        return formset

    # De rechten van de redacteur komen uit zijn omgevingen (RedactieRechtenMixin op het voorstel),
    # niet uit de Django-rechtentabel. Zonder deze methoden laat Django de inline helemaal weg.
    def _mag(self, request):
        return request.user.is_superuser or rechten(request).is_redacteur

    def has_view_permission(self, request, obj=None):
        return self._mag(request)

    def has_add_permission(self, request, obj=None):
        return self._mag(request)

    def has_change_permission(self, request, obj=None):
        return False  # een verstuurd bericht pas je niet meer aan; schrijf er een nieuw bij

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # een verstuurd bericht is niet meer ongedaan te maken


@admin.register(Verbetervoorstel)
class VerbetervoorstelAdmin(RedactieRechtenMixin, admin.ModelAdmin):
    omgeving_pad = "artikel__omgeving"
    form = VoorstelForm
    list_display = ["artikel", "status", "bak", "steun_kolom", "ingediend_op", "ingediend_door", "gesprek", "kort"]
    # In één keer meenemen; anders haalt de lijst voor elke rij de indiener apart op.
    list_select_related = ["artikel", "ingediend_door", "eigenaar"]
    list_filter = [BakFilter, VoorstelOpenFilter, "status", "artikel__omgeving"]
    actions = ["oppakken", "terugleggen"]
    search_fields = ["tekst", "citaat", "artikel__titel", "berichten__tekst"]
    inlines = [VoorstelBerichtInline]
    readonly_fields = [
        "artikel",
        "artikel_versie",
        "citaat",
        "tekst",
        "ingediend_door",
        "ingediend_op",
        "behandeld_door",
        "behandeld_op",
        "laatste_terugkoppeling",
        "steun_overzicht",
    ]
    fieldsets = [
        (
            "Het voorstel",
            {
                "fields": [
                    "artikel",
                    "artikel_versie",
                    "citaat",
                    "tekst",
                    "ingediend_door",
                    "ingediend_op",
                    "geladen_eigenaar",
                    "geladen_status",
                ]
            },
        ),
        (
            "Behandeling",
            {
                "fields": [
                    "naar_bak",
                    "cluster",
                    "status",
                    "verborgen",
                    "steun_overzicht",
                    "laatste_terugkoppeling",
                    "behandeld_door",
                    "behandeld_op",
                ],
                "description": "Terugkoppelen gaat via de berichten onderaan: elk bericht komt bij de "
                "indiener binnen als melding en als e-mail. Het laatste bericht is wat hij als antwoord "
                "ziet staan.",
            },
        ),
    ]

    @admin.display(description="Laatste terugkoppeling")
    def laatste_terugkoppeling(self, obj):
        """Alleen ter informatie: dit is het laatste bericht dat de indiener heeft gekregen."""
        return obj.terugkoppeling or "— nog geen terugkoppeling gestuurd"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_berichten=Count("berichten", distinct=True), _steun=Count("steun", distinct=True))
        )

    @admin.display(description="Bak", ordering="eigenaar__first_name")
    def bak(self, obj):
        if not obj.eigenaar_id:
            return "Gezamenlijk"
        naam = diensten.naam_van(obj.eigenaar)
        if obj.is_open and obj.eigenaar_gezien_op is None:
            return format_html("{} <b>· nog niet geopend</b>", naam)
        return naam

    @admin.display(description="Steun", ordering="_steun")
    def steun_kolom(self, obj):
        return obj._steun or "—"

    @admin.display(description="Steun van collega's")
    def steun_overzicht(self, obj):
        rijen = list(obj.steun.select_related("gebruiker"))
        if not rijen:
            return "Nog niemand"
        namen = ", ".join(r.naam for r in rijen)
        return f"{len(rijen)} collega('s): {namen}"

    @admin.action(description="Oppakken: naar mijn bak (ook om over te nemen van een collega)")
    def oppakken(self, request, queryset):
        self._verplaats(request, queryset, request.user, "opgepakt")

    @admin.action(description="Terugleggen in de gezamenlijke bak")
    def terugleggen(self, request, queryset):
        self._verplaats(request, queryset, None, "teruggelegd")

    def _verplaats(self, request, queryset, naar, werkwoord):
        gelukt, fouten = 0, []
        for v in queryset.select_related("artikel", "eigenaar"):
            vorige = v.eigenaar
            try:
                diensten.voorstel_naar_bak(v, request.user, naar)
            except diensten.VoorstelFout as e:
                fouten.append(f"{v.artikel.titel}: {e}")
                continue
            gelukt += 1
            if naar is None:
                bericht = f"Teruggelegd in de gezamenlijke bak (lag bij {diensten.naam_van(vorige)})."
            elif naar.pk != request.user.pk:
                bericht = f"Toegewezen aan {diensten.naam_van(naar)}."
            elif vorige and vorige.pk != request.user.pk:
                bericht = f"Overgenomen uit de bak van {diensten.naam_van(vorige)}."
            else:
                bericht = "Opgepakt."
            self.log_change(request, v, bericht)
        if gelukt == 1 and queryset.count() == 1:
            v = queryset.select_related("artikel", "eigenaar", "cluster").first()
            self.message_user(
                request, f"Voorstel bij '{v.artikel.titel}' {werkwoord}. {self._waar_ligt(v)}", messages.SUCCESS
            )
        elif gelukt:
            self.message_user(request, f"{gelukt} voorstel(len) {werkwoord}.", messages.SUCCESS)
        for f in fouten:
            self.message_user(request, f, messages.WARNING)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        # Behandelen gebeurt sinds 1.18.0 op het eigen behandelscherm (kennisbank/behandelen.py). Oude
        # links en bladwijzers komen daar uit; het formulier hier blijft voor bestaande koppelingen.
        v = self.get_object(request, object_id)
        if request.method == "GET":
            if v is not None:
                from .behandelen import scherm_url

                return redirect(scherm_url(v, request.GET.get("terug")))
        elif v is not None and v.is_open and self.has_change_permission(request, v):
            # Ronde A (review 1.27.0, M1): open voorstellen behandel je in de lade van de editor; dit oude
            # formulier verwerkt voor hen niets meer (anders omzeilt het de regels van de lade).
            from .behandelen import naar_editor

            return naar_editor(request, v)
        return super().change_view(request, object_id, form_url, extra_context)

    def get_model_perms(self, request):
        # Niet meer in de lijst met onderdelen: voorstellen behandel je vanuit de werkbakken op de
        # startpagina (kennisbank/werkoverzicht.py). Het behandelscherm zelf blijft gewoon bereikbaar.
        return {"add": False, "change": False, "delete": False, "view": False}

    def response_change(self, request, obj):
        # Na opslaan terug naar de werkbak waar je vandaan kwam, niet naar de oude lijst.
        if "_continue" not in request.POST and "_addanother" not in request.POST:
            from .werkoverzicht import werkplek_url

            self.message_user(
                request, f"Voorstel bij '{obj.artikel.titel}' opgeslagen. {self._waar_ligt(obj)}", messages.SUCCESS
            )
            return redirect(werkplek_url(request.GET.get("terug")))
        # Eigen melding in plaats van Djangos "De verbetervoorstel ... U kunt hieronder ..." (B7).
        self.message_user(
            request, f"Voorstel bij '{obj.artikel.titel}' opgeslagen. {self._waar_ligt(obj)}", messages.SUCCESS
        )
        return redirect(request.get_full_path())

    @staticmethod
    def _waar_ligt(v):
        if v.eigenaar_id:
            return f"Het ligt in de bak van {diensten.naam_van(v.eigenaar)}."
        if v.status in AFGEHANDELD:
            return "Het is afgehandeld."
        return f"Het ligt in de bak {v.cluster.naam if v.cluster_id else 'Algemeen'}."

    @admin.display(description="Gesprek", ordering="_berichten")
    def gesprek(self, obj):
        return f"{obj._berichten} bericht(en)" if obj._berichten else "—"

    @admin.display(description="Voorstel")
    def kort(self, obj):
        return obj.tekst[:80]

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        # Wat deze redacteur niet heeft aangeraakt, blijft zoals het nu (vergrendeld) in de database
        # staat. Het formulier zette de status uit de oude pagina; die geldt alleen als hij hem zelf koos.
        stand = getattr(form, "db_stand", None)
        if stand is not None:
            velden = ["behandeld_door_id", "behandeld_op", "eigenaar_id", "eigenaar_sinds", "eigenaar_gezien_op"]
            if not form.wil_status:
                velden.append("status")
            for veld in velden:
                setattr(obj, veld, getattr(stand, veld))
        # Eerst de bak: dat loopt via de dienstlaag (slot, status, e-mail). Daarna de velden die die
        # dienst schreef overnemen in obj, anders zet het opslaan hieronder de oude waarden terug.
        if form.wil_bak:
            keuze = form.cleaned_data.get("naar_bak")
            naar = diensten.redacteuren_van(obj.artikel.omgeving_id).filter(pk=keuze).first() if keuze else None
            vorige = obj.eigenaar
            try:
                v = diensten.voorstel_naar_bak(obj, request.user, naar)
            except diensten.VoorstelFout as e:
                self.message_user(request, str(e), messages.WARNING)
            else:
                velden = list(diensten.BAK_VELDEN)
                if not form.wil_status:
                    velden += ["status", "behandeld_door", "behandeld_op"]
                for veld in velden:
                    setattr(obj, veld, getattr(v, veld))
                if naar and vorige and vorige.pk not in (naar.pk, request.user.pk) and naar.pk == request.user.pk:
                    self.message_user(request, f"Overgenomen uit de bak van {diensten.naam_van(vorige)}.")
        # behandeld_door/op horen bij de status: wie heeft dit voorstel afgehandeld, en wanneer. Een
        # tussentijds bericht raakt ze niet aan (zie diensten.voorstelbericht_toevoegen), want de
        # bewaartermijn van de naam van de indiener hangt eraan.
        if form.wil_status:
            vorige = obj.eigenaar
            obj.behandeld_door = request.user
            obj.behandeld_op = timezone.now()
            diensten.eigenaar_bij_statuswijziging(obj, request.user)
            if obj.status in AFGEHANDELD:
                # Review 1.20.1, bevinding 12: ook via dit oude formulier hoort de vorige eigenaar het.
                diensten.meld_vorige_eigenaar_afgehandeld(obj, vorige, request.user)
        # Alleen deze velden: de rest (terugkoppeling, gelezen-stempels) schrijft de dienstlaag, en die
        # mag een verouderd object hier niet overschrijven.
        obj.save(
            update_fields=["status", "cluster", "verborgen", "behandeld_door", "behandeld_op", *diensten.BAK_VELDEN]
        )

    def save_related(self, request, form, formsets, change):
        """Elk nieuw bericht gaat via de dienstlaag, zodat de melding en de e-mail er één keer uitgaan.

        Het formulier schrijft `terugkoppeling` niet meer zelf (het veld is `editable=False`), dus er
        is maar één schrijver en een nieuw bericht kan niets overschrijven.
        """
        obj = form.instance
        teksten, leeggemaakt = [], []
        for formset in formsets:
            if formset.model is not VoorstelBericht:
                continue
            for f in formset.forms:
                if f.instance.pk is None and (f.cleaned_data.get("tekst") or "").strip():
                    teksten.append(f.cleaned_data["tekst"])
                    # Leegmaken zodat de inline zelf niets wegschrijft; de dienstlaag doet dat, inclusief
                    # de melding. We houden de rijen bij die we zo hebben leeggemaakt, zodat het opruimen
                    # hieronder niet per ongeluk een ander bericht raakt.
                    f.cleaned_data["tekst"] = ""
                    f.instance.tekst = ""
                    leeggemaakt.append(f.instance)
        super().save_related(request, form, formsets, change)
        pks = [b.pk for b in leeggemaakt if b.pk]
        if pks:
            VoorstelBericht.objects.filter(pk__in=pks).delete()
        for tekst in teksten:
            diensten.voorstelbericht_toevoegen(obj, request.user, tekst, van_redactie=True)
        if not teksten and form.wil_status:
            diensten.meld_terugkoppeling(obj)


class BerichtForm(forms.ModelForm):
    class Meta:
        model = Bericht
        fields = ["titel", "tekst", "omgeving", "artikelen", "status", "vastgepind", "verloopt_op"]
        widgets = {
            "titel": forms.TextInput(
                attrs={"placeholder": "Titel van het bericht: wat is er nieuw?", "aria-label": "Titel"}
            ),
            "tekst": forms.Textarea(attrs={"class": "kb-editor", "rows": 12}),
        }


@admin.register(Bericht)
class BerichtAdmin(RedactieRechtenMixin, admin.ModelAdmin):
    """Nieuwsberichten: redacteuren schrijven en publiceren ze voor hun eigen omgeving(en)."""

    form = BerichtForm
    list_display = ["titel", "omgeving", "status", "vastgepind", "gepubliceerd_op", "verloopt_op", "auteur"]
    list_select_related = ["omgeving", "auteur"]  # anders per rij een vraag naar de schrijver
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
        # Sinds 1.23.0 hetzelfde scherm en dezelfde editor als bij artikelen (zonder secties en onboarding).
        css = {"all": ["kennisbank/fonts.css", "kennisbank/beheer-editor.css", "kennisbank/artikel-scherm.css"]}
        js = [
            "kennisbank/vendor/tiptap/tiptap.min.js",
            "kennisbank/artikel-editor.js",
            "kennisbank/artikel-scherm.js",
            "kennisbank/beheer-editor.js",
        ]

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        mag = self.has_add_permission(request) if add else self.has_change_permission(request, obj)
        _eenvoudig_afronden(context, obj, gepubliceerd=bool(obj and obj.status == BerichtStatus.GEPUBLICEERD), mag=mag)
        return super().render_change_form(request, context, add=add, change=change, form_url=form_url, obj=obj)

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


class SjabloonForm(forms.ModelForm):
    class Meta:
        model = Sjabloon
        fields = ["naam", "titel", "samenvatting", "inhoud", "soort", "volgorde", "actief"]
        widgets = {"inhoud": forms.Textarea(attrs={"class": "kb-editor", "rows": 20})}


class ToegangInline(admin.TabularInline):
    model = Toegang
    extra = 1
    autocomplete_fields = ["groep"]
    fields = ["groep", "groep_uitleg", "rol"]
    readonly_fields = ["groep_uitleg"]
    verbose_name = "groep met toegang"
    verbose_name_plural = "Wie heeft toegang tot deze omgeving"

    @admin.display(description="Welke groep is dit?")
    def groep_uitleg(self, obj):
        """De leesbare naam erbij, want in Entra ID is de groepsnaam vaak een object-id."""
        if not obj or not obj.groep_id:
            return ""
        return groep_omschrijving(obj.groep)


@admin.register(Sjabloon)
class SjabloonAdmin(admin.ModelAdmin):
    """Voorbeeldartikelen om een nieuwe omgeving mee te vullen. Alleen voor functioneel beheerders."""

    list_display = ["naam", "titel", "soort", "volgorde", "actief"]
    list_editable = ["volgorde", "actief"]
    list_filter = ["actief", "soort"]
    search_fields = ["naam", "titel", "inhoud"]
    form = SjabloonForm

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Reviewteam)
class ReviewteamAdmin(admin.ModelAdmin):
    """Reviewteams (stap C): alleen een beheerder maakt ze aan en koppelt ze aan een Entra ID-groep."""

    list_display = ["naam", "omgeving", "groep", "clusterlijst"]
    list_filter = ["omgeving"]
    fields = ["naam", "omgeving", "groep", "clusters"]

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "clusters":
            kwargs["widget"] = Vinkjes
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    @admin.display(description="Clusters (voorgevuld)")
    def clusterlijst(self, obj):
        return ", ".join(obj.clusters.values_list("naam", flat=True)) or "—"

    def _beheerder(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_module_permission(self, request):
        return self._beheerder(request)

    def has_view_permission(self, request, obj=None):
        return self._beheerder(request)

    def has_add_permission(self, request):
        return self._beheerder(request)

    def has_change_permission(self, request, obj=None):
        return self._beheerder(request)

    def has_delete_permission(self, request, obj=None):
        return self._beheerder(request)


@admin.register(Omgeving)
class OmgevingAdmin(admin.ModelAdmin):
    list_display = ["naam", "slug", "aantal_groepen", "aantal_artikelen"]
    prepopulated_fields = {"slug": ["naam"]}
    inlines = [ToegangInline]
    actions = ["vullen_met_sjablonen"]

    @admin.action(description="Vullen met de sjablonen (als concept)")
    def vullen_met_sjablonen(self, request, queryset):
        """Plaats elk actief sjabloon als concept-artikel in de gekozen omgeving(en).

        Als concept, zodat een redacteur ze eerst naloopt en aanvult; een sjabloon dat per ongeluk
        zichtbaar wordt voor medewerkers is erger dan een lege kennisbank. Een sjabloon dat er al staat
        (zelfde titel) wordt overgeslagen, zodat de actie twee keer uitvoeren niets dubbel oplevert.
        """
        if not request.user.is_superuser:
            messages.error(request, "Alleen een functioneel beheerder kan een omgeving vullen.")
            return
        sjablonen = list(Sjabloon.objects.filter(actief=True))
        if not sjablonen:
            messages.warning(
                request,
                "Er staan nog geen sjablonen klaar. Maak ze eerst aan onder Sjablonen; de inhoud daarvan "
                "schrijf je zelf, in de woorden van de organisatie.",
            )
            return
        gemaakt, overgeslagen = 0, 0
        for omgeving in queryset:
            for sj in sjablonen:
                if Artikel.objects.filter(omgeving=omgeving, titel__iexact=sj.titel).exists():
                    overgeslagen += 1
                    continue
                artikel = Artikel.objects.create(
                    omgeving=omgeving,
                    titel=sj.titel,
                    samenvatting=sj.samenvatting,
                    inhoud=sj.inhoud,
                    soort=sj.soort,
                    status=Status.CONCEPT,
                )
                diensten.herbouw_secties(artikel)
                gemaakt += 1
        if gemaakt:
            messages.success(
                request,
                f"{gemaakt} concept-artikel(en) geplaatst. Ze staan op concept, dus medewerkers zien ze "
                "nog niet; loop ze na en publiceer wat klaar is.",
            )
        if overgeslagen:
            messages.info(request, f"{overgeslagen} sjabloon(en) overgeslagen: die titel stond er al.")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_groepen=Count("toegang", distinct=True), _artikelen=Count("artikelen", distinct=True))
        )

    @admin.display(description="Groepen met toegang", ordering="_groepen")
    def aantal_groepen(self, obj):
        return obj._groepen

    @admin.display(description="Artikelen", ordering="_artikelen")
    def aantal_artikelen(self, obj):
        return obj._artikelen


@admin.register(Toegang)
class ToegangAdmin(admin.ModelAdmin):
    list_display = ["welke_groep", "groepscode", "rol", "omgeving"]
    list_filter = ["omgeving", "rol"]
    autocomplete_fields = ["groep"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("groep__kennisbank_label", "omgeving")

    @admin.display(description="Groep")
    def welke_groep(self, obj):
        return groep_omschrijving(obj.groep)

    @admin.display(description="Code uit Entra ID")
    def groepscode(self, obj):
        """De ruwe naam uit de groepen-claim. Een GUID zetten we er grijs bij, die leest niemand."""
        naam = obj.groep.name
        if GUID_PATROON.match(naam):
            return format_html('<span style="color:#666">{}</span>', naam)
        return naam


def groep_omschrijving(groep) -> str:
    """Leesbare naam van een groep; valt terug op de code met een duidelijke hint als er geen label is."""
    label = getattr(groep, "kennisbank_label", None)
    if label:
        return label.omschrijving
    if GUID_PATROON.match(groep.name):
        return "(nog geen naam ingevuld — zie Groepsnamen)"
    return groep.name


class GroepLabelInline(admin.StackedInline):
    model = GroepLabel
    can_delete = True
    verbose_name_plural = "Leesbare naam"
    extra = 0
    max_num = 1


class GroepAdmin(DjangoGroupAdmin):
    """Django's groepenscherm met de leesbare naam en waar de groep voor wordt gebruikt erbij.

    In Entra ID-modus worden groepen automatisch aangemaakt vanuit de groepen-claim bij het inloggen.
    De naam daarin is bij RWS vaak een object-id, dus zonder deze toevoeging ziet een beheerder een
    lijst codes.
    """

    inlines = [GroepLabelInline]
    list_display = ["welke_groep", "naam_uit_entra", "aantal_gebruikers", "waarvoor"]
    search_fields = ["name", "kennisbank_label__omschrijving"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("kennisbank_label")
            .prefetch_related("kennisbank_toegang__omgeving")
            .annotate(_gebruikers=Count("user", distinct=True))
        )

    @admin.display(description="Groep")
    def welke_groep(self, obj):
        return groep_omschrijving(obj)

    @admin.display(description="Naam uit Entra ID", ordering="name")
    def naam_uit_entra(self, obj):
        return obj.name

    @admin.display(description="Heeft ingelogd", ordering="_gebruikers")
    def aantal_gebruikers(self, obj):
        return f"{obj._gebruikers} gebruiker(s)"

    @admin.display(description="Toegang tot")
    def waarvoor(self, obj):
        rijen = [f"{t.omgeving.naam} ({t.get_rol_display()})" for t in obj.kennisbank_toegang.all()]
        return ", ".join(rijen) or "—"


admin.site.unregister(Group)
admin.site.register(Group, GroepAdmin)


@admin.register(Systeemstand)
class StatusAdmin(admin.ModelAdmin):
    """Eén scherm waarop de functioneel beheerder ziet of alles nog loopt.

    Hangt aan het model Systeemstand, zodat "Status" gewoon in het beheermenu staat. De lijst zelf is
    vervangen door de statuspagina; er valt hier niets te wijzigen.
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_module_permission(self, request):
        return request.user.is_superuser

    def changelist_view(self, request, extra_context=None):
        from django.core.exceptions import PermissionDenied

        if not self.has_view_permission(request):
            raise PermissionDenied
        from . import status as status_mod

        return render(
            request,
            "admin/kennisbank/status.html",
            {
                **self.admin_site.each_context(request),
                "title": "Status",
                "overzicht": status_mod.overzicht(),
                "opts": self.model._meta,
            },
        )


class RedactieKeuzelijstAdmin(admin.ModelAdmin):
    """Redacteuren mogen keuzelijsten aanvullen; alleen beheerders verwijderen."""

    search_fields = ["naam"]

    def _mag(self, request):
        return request.user.is_superuser or rechten(request).is_redacteur

    def has_module_permission(self, request):
        return self._mag(request)

    has_view_permission = lambda self, request, obj=None: self._mag(request)  # noqa: E731
    has_add_permission = lambda self, request: self._mag(request)  # noqa: E731
    has_change_permission = lambda self, request, obj=None: self._mag(request)  # noqa: E731

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


class OngebruiktFilter(admin.SimpleListFilter):
    """Filter op "nergens gebruikt", zodat een beheerder een keuzelijst kan opruimen."""

    title = "gebruik"
    parameter_name = "gebruik"

    def lookups(self, request, model_admin):
        return [("ongebruikt", "Nergens gebruikt"), ("gebruikt", "In gebruik")]

    def queryset(self, request, queryset):
        if self.value() == "ongebruikt":
            return queryset.filter(_aantal=0)
        if self.value() == "gebruikt":
            return queryset.filter(_aantal__gt=0)
        return queryset


class OpruimbareKeuzelijstAdmin(RedactieKeuzelijstAdmin):
    """Keuzelijst met een gebruiksteller, een filter op "nergens gebruikt" en een opruimactie.

    Keuzelijsten groeien: een import, een typefout of een reorganisatie laat items achter die nergens
    meer aan hangen. Die staan vervolgens wel in elk keuzemenu. Verwijderen mag alleen een beheerder,
    en alleen items die echt nergens meer in gebruik zijn.
    """

    #: Naam van de relatie naar Artikel waarop we het gebruik tellen.
    gebruiksrelatie = "artikel"
    list_filter = [OngebruiktFilter]
    actions = ["ongebruikte_verwijderen"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_aantal=Count(self.gebruiksrelatie, distinct=True))

    @admin.display(description="Gebruikt in", ordering="_aantal")
    def aantal_artikelen(self, obj):
        return f"{obj._aantal} artikel(en)"

    @admin.action(description="Verwijderen als ze nergens worden gebruikt")
    def ongebruikte_verwijderen(self, request, queryset):
        if not request.user.is_superuser:
            messages.error(request, "Alleen een functioneel beheerder kan keuzelijsten opruimen.")
            return
        in_gebruik = [str(o) for o in queryset.filter(_aantal__gt=0)]
        aantal, _ = queryset.filter(_aantal=0).delete()
        if aantal:
            messages.success(request, f"{aantal} ongebruikt(e) item(s) verwijderd.")
        if in_gebruik:
            messages.warning(
                request,
                f"Overgeslagen omdat ze nog in gebruik zijn: {', '.join(in_gebruik[:10])}"
                + (f" en {len(in_gebruik) - 10} andere" if len(in_gebruik) > 10 else "")
                + ". Haal ze eerst bij die artikelen weg.",
            )
        if not aantal and not in_gebruik:
            messages.info(request, "Niets geselecteerd om op te ruimen.")


@admin.register(Cluster)
class ClusterAdmin(OpruimbareKeuzelijstAdmin):
    gebruiksrelatie = "artikel"
    list_display = ["naam", "volgorde", "aantal_artikelen"]
    list_editable = ["volgorde"]


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ["naam"]

    def clean_naam(self):
        # Tag.save() normaliseert de naam; zonder dat hier ook te doen controleert het formulier op
        # de ongenormaliseerde waarde. "Rappel" naast "rappel" kwam dan door de validatie en liep
        # daarna stuk op de unieke index — een serverfout in plaats van een nette melding.
        return normaliseer_tag(self.cleaned_data["naam"])


@admin.register(Tag)
class TagAdmin(OpruimbareKeuzelijstAdmin):
    form = TagForm
    gebruiksrelatie = "artikel"
    list_display = ["naam", "aantal_artikelen"]


@admin.register(Zaaktype)
class ZaaktypeAdmin(OpruimbareKeuzelijstAdmin):
    gebruiksrelatie = "artikel"
    list_display = ["naam", "code", "aantal_artikelen"]
    search_fields = ["naam", "code"]


@admin.register(Kladversie)
class KladversieAdmin(admin.ModelAdmin):
    """Openstaande kladversies: je eigen, en die van collega's in jouw omgeving(en).

    Alleen lezen. Verdergaan doe je in het bewerkscherm (daar staat de vraag of je verder wilt), en
    een kladversie van een collega open je via Bekijken zonder hem over te nemen. Een kladversie van
    een nieuw artikel heeft nog geen bewerkscherm; deze lijst is de enige plek waar een collega hem ziet.
    """

    list_display = ["titel_kolom", "schrijver", "omgeving_kolom", "bijgewerkt", "acties"]
    list_display_links = None
    ordering = ["-bijgewerkt_op"]

    def _r(self, request):
        return rechten(request)

    def get_queryset(self, request):
        from django.db.models import BooleanField, Case, Value, When

        # Per rij: is dit de kladversie van wie er kijkt? Niet op de ModelAdmin onthouden: die wordt
        # gedeeld tussen verzoeken, en dan kan de ene redacteur de knoppen van de ander zien.
        return diensten.zichtbare_kladversies(request.user, self._r(request)).annotate(
            is_mijn=Case(
                When(gebruiker=request.user, then=Value(True)), default=Value(False), output_field=BooleanField()
            )
        )

    def has_module_permission(self, request):
        return request.user.is_active and (request.user.is_superuser or self._r(request).is_redacteur)

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Artikel")
    def titel_kolom(self, obj):
        if obj.artikel_id:
            return obj.titel
        return format_html(
            '{} <span style="color:var(--body-quiet-color)">(nieuw, nog nooit opgeslagen)</span>', obj.titel
        )

    @admin.display(description="Van")
    def schrijver(self, obj):
        return obj.naam

    @admin.display(description="Omgeving")
    def omgeving_kolom(self, obj):
        omg = obj.artikel.omgeving if obj.artikel_id else obj.omgeving
        return omg.naam if omg else "—"

    @admin.display(description="Laatst bijgewerkt", ordering="bijgewerkt_op")
    def bijgewerkt(self, obj):
        return ArtikelAdmin._klad_tijd(obj.bijgewerkt_op)

    @admin.display(description="")
    def acties(self, obj):
        bekijk = reverse("admin:kennisbank_artikel_klad_bekijken", args=[obj.pk])
        links = [format_html('<a href="{}" target="_blank">Bekijken</a>', bekijk)]
        if getattr(obj, "is_mijn", False):
            verder = (
                reverse("admin:kennisbank_artikel_change", args=[obj.artikel_id])
                if obj.artikel_id
                else reverse("admin:kennisbank_artikel_add")
            )
            links.append(format_html('<a href="{}"><b>Verder gaan</b></a>', verder))
        return format_html(" · ".join(["{}"] * len(links)), *links)
