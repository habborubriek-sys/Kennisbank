"""Beheerscherm (/beheer/).

- Redacteuren (procesmanagement) bewerken hier artikelen en behandelen voorstellen,
  alleen binnen de omgeving(en) waar zij redacteur zijn.
- Functioneel beheerders (superusers) beheren daarnaast omgevingen, toegang en keuzelijsten.
"""

import datetime
import json
import re

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.models import Group
from django.db import connection, transaction
from django.db.models import Count, OuterRef, Subquery
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.html import format_html

from . import diensten
from . import inhoud as inhoud_mod
from .models import (
    GUID_PATROON,
    MAX_INHOUD,
    Artikel,
    ArtikelVersie,
    Bericht,
    Cluster,
    GroepLabel,
    Omgeving,
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
    max_num = 0  # geen lege regel onderaan; er valt hier niets toe te voegen
    can_delete = False
    fields = ["versie", "gepubliceerd_op", "gepubliceerd_door", "toelichting", "kleine_correctie", "bekijk"]
    readonly_fields = fields
    verbose_name_plural = "Versiegeschiedenis (onveranderlijk)"

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


#: Titels die onmiskenbaar nog uit de bestandsmap komen in plaats van uit de kennisbank. Alleen gebruikt
#: bij de eerste publicatie, als zachte vangnet: een redacteur ziet het meestal zelf, maar niet altijd.
#: Let op: "concept" en "definitief" in gewone schrijfwijze zijn gewone woorden ("conceptbesluit"), dus
#: daar gaan we niet op af. Alleen op schreeuwende kapitalen en op wat er verder in bestandsnamen staat.
_TITEL_RUIS = re.compile(
    r"\.(docx?|pdf|odt|rtf|txt)\s*$"
    r"|\b(kopie\s+van|nieuwe\s+map)\b"
    r"|\bversie\s*\d|\bv\d+[._]\d+\b|[_\s-]v\d",
    re.I,
)
#: Schreeuwende kapitalen zijn een bestandsnaam-gewoonte; in kleine letters zijn het gewone woorden.
_TITEL_RUIS_KAPITAAL = re.compile(r"\b(DEFINITIEF|DEFINITIEVE|FINAL|CONCEPT)\b")

#: Samenvattingen die net zo goed leeg hadden kunnen zijn.
_SAMENVATTING_RUIS = {
    "", "nvt", "n.v.t", "n.v.t.", "geen", "volgt", "volgt nog", "nog invullen", "nog in te vullen",
    "tbd", "todo", "to do", "x", "xxx", "test", "tekst", "samenvatting", "zie artikel", "zie inhoud",
}


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and not self.is_bound:
            self.fields["tags_tekst"].initial = ", ".join(self.instance.tags.values_list("naam", flat=True))
            self.fields["geladen_stempel"].initial = stempel_van(self.instance)
            self.fields["al_gepubliceerd"].initial = "1" if self.instance.versie else ""

    def clean(self):
        data = super().clean()
        self._controleer_conflict(data)
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


    def _controleer_eerste_publicatie(self, data):
        """Laatste controle voordat een artikel voor het eerst zichtbaar wordt voor medewerkers.

        Alleen bij de eerste publicatie, en alleen op dingen die onmiskenbaar nog niet af zijn: een
        bestandsnaam als titel, een lege of nietszeggende samenvatting, of een sectie zonder titel
        (die heet voor de lezer "Sectie 1"). Een redacteur die bewust iets anders wil, kan het artikel
        als concept opslaan en in twee stappen publiceren.
        """
        if data.get("status") != Status.GEPUBLICEERD or self.instance.versie:
            return
        titel = (data.get("titel") or "").strip()
        if titel and (_TITEL_RUIS.search(titel) or _TITEL_RUIS_KAPITAAL.search(titel)):
            self.add_error(
                "titel",
                "Deze titel lijkt een bestandsnaam of een versie-aanduiding. Medewerkers zoeken op de titel, "
                "dus geef het artikel de naam waaronder zij het zouden zoeken.",
            )
        samenvatting = " ".join((data.get("samenvatting") or "").split())
        if not samenvatting:
            self.add_error(
                "samenvatting",
                "Vul een samenvatting in. Medewerkers zien die in de lijst en in de zoekresultaten; zonder "
                "samenvatting moeten zij elk artikel openen om te zien of het het juiste is.",
            )
        elif samenvatting.strip(" .-–—_").lower() in _SAMENVATTING_RUIS or len(samenvatting) < 20:
            self.add_error(
                "samenvatting",
                "Deze samenvatting zegt nog niets. Schrijf één of twee zinnen over waar dit artikel over gaat.",
            )
        zonder_kop = inhoud_mod.secties_zonder_kop(data.get("inhoud") or "")
        if zonder_kop:
            nummers = ", ".join(str(n) for n in zonder_kop)
            self.add_error(
                "inhoud",
                f"Er {'is een sectie' if len(zonder_kop) == 1 else 'zijn secties'} zonder titel "
                f"(nummer {nummers}). Medewerkers zien dat kader dan dichtgeklapt staan als "
                f"'Sectie {zonder_kop[0]}'. Geef elke sectie een titel, of haal het kader weg.",
            )

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
        sleutel = " ".join(titel.split()).lower()
        # Een adviesslot op titel+omgeving, zodat twee gelijktijdige verzoeken (dubbelklik) niet
        # allebei "bestaat nog niet" zien. Het slot geldt tot het einde van de transactie, dus het
        # tweede verzoek wacht tot het eerste is weggeschreven en vindt het artikel dan wél.
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"artikel:{omgeving.pk}:{sleutel}"])
        bestaand = Artikel.objects.filter(omgeving=omgeving, titel__iexact=titel.strip()).first()
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
    filter_horizontal = ["clusters", "zaaktypen"]
    inlines = [VersieInline]
    readonly_fields = ["versie", "gepubliceerd_op", "link"]
    actions = ["publiceren", "archiveren", "nagekeken"]
    change_list_template = "admin/kennisbank/artikel/change_list.html"
    fieldsets = [
        (None, {"fields": ["titel", "samenvatting", "inhoud", "geladen_stempel", "al_gepubliceerd"]}),
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
        ]
        return eigen + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        """Een waarschuwing bovenaan de lijst als er artikelen zijn waarvan de nakijkdatum is verstreken.

        Alleen over de artikelen die deze redacteur mag zien, en niet als hij al op dat filter staat.
        """
        eigen = self.get_queryset(request)
        extra = extra_context or {}
        if not request.GET.get("herziening"):
            vandaag = timezone.localdate()
            extra["te_herzien"] = diensten.te_herzien(eigen).count()
            extra["herzien_binnenkort"] = (
                eigen.filter(
                    status=Status.GEPUBLICEERD,
                    herzien_voor__gte=vandaag,
                    herzien_voor__lte=vandaag + datetime.timedelta(days=HERZIENING_BINNENKORT),
                ).count()
            )
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
                "stempel": stempel_van(artikel),
            }
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

    @admin.display(description="Nakijken voor", ordering="herzien_voor")
    def nakijken(self, obj):
        """De herzieningsdatum, met kleur zodra hij in zicht komt of verstreken is."""
        if not obj.herzien_voor:
            return format_html('<span style="color:#888">—</span>')
        dagen = (obj.herzien_voor - timezone.localdate()).days
        datum = date_format(obj.herzien_voor, "j M Y")
        if obj.status != Status.GEPUBLICEERD:
            return format_html('<span style="color:#888">{}</span>', datum)
        if dagen < 0:
            return format_html(
                '<b style="color:#a6192e">{} · {} dagen te laat</b>', datum, -dagen
            )
        if dagen <= HERZIENING_BINNENKORT:
            return format_html('<span style="color:#8a5a00">{} · over {} dagen</span>', datum, dagen)
        return datum

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "omgeving" and not request.user.is_superuser:
            kwargs["queryset"] = Omgeving.objects.filter(pk__in=self._omgevingen(request))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        diensten.claim_opheffen(form.instance, request.user)  # opgeslagen = niet meer aan het bewerken
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
        n = 0
        for a in queryset:
            a.herzien_voor = None  # leegmaken, zodat de termijn vanaf vandaag opnieuw gaat tellen
            nieuw = diensten.herzieningsdatum(a)
            Artikel.objects.filter(pk=a.pk).update(herzien_voor=nieuw)
            n += 1
        messages.success(
            request,
            f"{n} artikel(en) gemarkeerd als nagekeken; de nakijkdatum staat nu {maanden} maanden vooruit. "
            "Er is geen nieuwe versie gemaakt en medewerkers krijgen hiervan geen melding.",
        )

    @admin.action(description="Publiceren")
    def publiceren(self, request, queryset):
        n, geweigerd = 0, []
        for a in queryset:
            # Dezelfde regel als in het bewerkscherm: een inhoudelijke wijziging hoort een toelichting
            # te krijgen, want medewerkers zien die als melding. Via deze lijstactie is er geen veld om
            # er een te typen, dus sturen we de redacteur naar het bewerkscherm in plaats van een
            # nietszeggende "Gepubliceerd via lijstactie" aan iedereen te tonen.
            if diensten.is_inhoudelijk_gewijzigd(a, diensten.momentopname(a)):
                geweigerd.append(a)
                continue
            a.status = Status.GEPUBLICEERD
            a.save(update_fields=["status", "gewijzigd_op"])
            if diensten.registreer_publicatie(a, request.user, "Gepubliceerd via lijstactie"):
                n += 1
        self.message_user(request, f"{n} artikel(en) gepubliceerd.")
        if geweigerd:
            namen = ", ".join(a.titel for a in geweigerd[:5]) + ("…" if len(geweigerd) > 5 else "")
            self.message_user(
                request,
                f"{len(geweigerd)} artikel(en) niet gepubliceerd omdat de inhoud is gewijzigd zonder "
                f"toelichting: {namen}. Publiceer die via het bewerkscherm, dan kun je aangeven wat er "
                "is veranderd.",
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
            return queryset.filter(status__in=[VoorstelStatus.VERWERKT, VoorstelStatus.AFGEWEZEN])
        if keuze == "wacht":
            laatste = (
                VoorstelBericht.objects.filter(voorstel=OuterRef("pk"))
                .order_by("-moment", "-pk")
                .values("van_redactie")[:1]
            )
            return queryset.annotate(_laatste_van_redactie=Subquery(laatste)).filter(_laatste_van_redactie=False)
        return queryset


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
        return request.user.is_superuser or Rechten(request.user).is_redacteur

    def has_view_permission(self, request, obj=None):
        return self._mag(request)

    def has_add_permission(self, request, obj=None):
        return self._mag(request)

    def has_change_permission(self, request, obj=None):
        return False  # een verstuurd bericht pas je niet meer aan; schrijf er een nieuw bij

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # een verstuurd bericht is niet meer ongedaan te maken


class VoorstelForm(forms.ModelForm):
    class Meta:
        model = Verbetervoorstel
        fields = ["status", "terugkoppeling"]
        widgets = {"terugkoppeling": forms.Textarea(attrs={"rows": 6, "cols": 80})}


@admin.register(Verbetervoorstel)
class VerbetervoorstelAdmin(RedactieRechtenMixin, admin.ModelAdmin):
    form = VoorstelForm
    omgeving_pad = "artikel__omgeving"
    list_display = ["artikel", "status", "ingediend_op", "ingediend_door", "gesprek", "kort"]
    list_filter = [VoorstelOpenFilter, "status", "artikel__omgeving"]
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
    ]
    fieldsets = [
        (
            "Het voorstel",
            {"fields": ["artikel", "artikel_versie", "citaat", "tekst", "ingediend_door", "ingediend_op"]},
        ),
        (
            "Behandeling",
            {
                "fields": ["status", "terugkoppeling", "behandeld_door", "behandeld_op"],
                "description": "De terugkoppeling is wat de indiener als antwoord ziet. Wil je er meer dan "
                "één bericht over sturen, gebruik dan het gesprek onderaan.",
            },
        ),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_berichten=Count("berichten"))

    @admin.display(description="Gesprek", ordering="_berichten")
    def gesprek(self, obj):
        return f"{obj._berichten} bericht(en)" if obj._berichten else "—"

    @admin.display(description="Voorstel")
    def kort(self, obj):
        return obj.tekst[:80]

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        obj.behandeld_door = request.user
        obj.behandeld_op = timezone.now()
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        """Nieuwe gespreksberichten en een gewijzigde terugkoppeling leveren precies één melding op."""
        obj = form.instance
        nieuwe_berichten = []
        for formset in formsets:
            if formset.model is not VoorstelBericht:
                continue
            for f in formset.forms:
                if f.instance.pk is None and (f.cleaned_data.get("tekst") or "").strip():
                    nieuwe_berichten.append(f.cleaned_data["tekst"])
                    f.cleaned_data["tekst"] = ""  # we schrijven hem zelf weg via de dienst
                    f.instance.tekst = ""
        super().save_related(request, form, formsets, change)
        VoorstelBericht.objects.filter(voorstel=obj, tekst="").delete()  # de lege regels van hierboven
        for tekst in nieuwe_berichten:
            diensten.voorstelbericht_toevoegen(obj, request.user, tekst, van_redactie=True)
        if not nieuwe_berichten and "terugkoppeling" in form.changed_data and obj.terugkoppeling.strip():
            diensten.voorstelbericht_toevoegen(obj, request.user, obj.terugkoppeling, van_redactie=True)
        elif not nieuwe_berichten and "status" in form.changed_data:
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


@admin.register(Omgeving)
class OmgevingAdmin(admin.ModelAdmin):
    list_display = ["naam", "slug", "aantal_groepen", "aantal_artikelen"]
    prepopulated_fields = {"slug": ["naam"]}
    inlines = [ToegangInline]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_groepen=Count("toegang", distinct=True), _artikelen=Count("artikel", distinct=True))
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
        return request.user.is_superuser or Rechten(request.user).is_redacteur

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
