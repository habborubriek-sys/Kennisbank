from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models
from django.utils import timezone


class Omgeving(models.Model):
    """Een afgeschermd deel van de kennisbank, bijvoorbeeld per afdeling of organisatieonderdeel.

    Artikelen horen bij precies één omgeving. Toegang wordt per omgeving geregeld via groepen.
    """

    slug = models.SlugField(unique=True)
    naam = models.CharField(max_length=120)
    beschrijving = models.TextField(blank=True)

    class Meta:
        verbose_name = "omgeving"
        verbose_name_plural = "omgevingen"
        ordering = ["naam"]

    def __str__(self):
        return self.naam


class Rol(models.TextChoices):
    LEZER = "lezer", "Lezer"
    REDACTEUR = "redacteur", "Redacteur (procesmanagement)"


class Toegang(models.Model):
    """Koppelt een groep uit de identity provider aan een rol binnen een omgeving."""

    omgeving = models.ForeignKey(Omgeving, on_delete=models.CASCADE, related_name="toegang")
    groep = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="kennisbank_toegang")
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.LEZER)

    class Meta:
        verbose_name = "toegang"
        verbose_name_plural = "toegang"
        constraints = [models.UniqueConstraint(fields=["omgeving", "groep"], name="uniek_toegang_per_groep")]

    def __str__(self):
        return f"{self.groep} → {self.get_rol_display()} in {self.omgeving}"


class Cluster(models.Model):
    naam = models.CharField(max_length=80, unique=True)
    volgorde = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["volgorde", "naam"]

    def __str__(self):
        return self.naam


class Tag(models.Model):
    naam = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["naam"]

    def __str__(self):
        return self.naam


class Zaaktype(models.Model):
    """Zaaktype zoals bekend in het zaaksysteem. `code` is wat het zaaksysteem meestuurt."""

    code = models.CharField(
        max_length=80,
        unique=True,
        help_text="De identificatie die het zaaksysteem gebruikt, bijv. de zaaktype-omschrijving of -code.",
    )
    naam = models.CharField(max_length=120)

    class Meta:
        ordering = ["naam"]

    def __str__(self):
        return self.naam


class Soort(models.TextChoices):
    WERKINSTRUCTIE = "werkinstructie", "Werkinstructie"
    WERKAFSPRAAK = "werkafspraak", "Werkafspraak"
    PROCES = "proces", "Proces"


class Status(models.TextChoices):
    CONCEPT = "concept", "Concept"
    GEPUBLICEERD = "gepubliceerd", "Gepubliceerd"
    GEARCHIVEERD = "gearchiveerd", "Gearchiveerd"


class ArtikelQuerySet(models.QuerySet):
    def gepubliceerd(self):
        return self.filter(status=Status.GEPUBLICEERD)


class Artikel(models.Model):
    omgeving = models.ForeignKey(Omgeving, on_delete=models.PROTECT, related_name="artikelen")
    slug = models.SlugField(unique=True, max_length=120, help_text="Deel van de link naar het artikel.")
    titel = models.CharField(max_length=200)
    samenvatting = models.TextField(help_text="Eén of twee zinnen: waar gaat dit artikel over?")
    soort = models.CharField(max_length=20, choices=Soort.choices, default=Soort.WERKINSTRUCTIE)
    clusters = models.ManyToManyField(
        Cluster, blank=True, help_text="Leeg laten als het artikel voor alle clusters geldt."
    )
    tags = models.ManyToManyField(Tag, blank=True)
    zaaktypen = models.ManyToManyField(
        Zaaktype, blank=True, help_text="Bij welke zaaktypen dit artikel in het zaaksysteem verschijnt."
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONCEPT)
    eigenaar = models.CharField(max_length=120, default="Procesmanagement")
    versie = models.PositiveIntegerField(default=0, editable=False)
    gepubliceerd_op = models.DateTimeField(null=True, blank=True, editable=False)
    aangemaakt_op = models.DateTimeField(auto_now_add=True)
    gewijzigd_op = models.DateTimeField(auto_now=True)

    objects = ArtikelQuerySet.as_manager()

    class Meta:
        verbose_name = "artikel"
        verbose_name_plural = "artikelen"
        ordering = ["titel"]

    def __str__(self):
        return self.titel

    def get_absolute_url(self):
        return f"/artikel/{self.slug}"


class Sectie(models.Model):
    """Een in- en uitklapbaar onderdeel van een artikel."""

    artikel = models.ForeignKey(Artikel, on_delete=models.CASCADE, related_name="secties")
    volgorde = models.PositiveIntegerField(default=0)
    kop = models.CharField(max_length=200)
    inhoud = models.TextField(help_text="Opmaak met Markdown: **vet**, lijstjes met - of 1.")
    onboarding = models.TextField(
        blank=True,
        help_text="Extra uitleg die alleen zichtbaar is als de gebruiker 'Onboarding' aanzet.",
    )

    class Meta:
        verbose_name = "sectie"
        verbose_name_plural = "secties"
        ordering = ["volgorde", "id"]

    def __str__(self):
        return self.kop


class ArtikelVersie(models.Model):
    """Onveranderlijke momentopname van een gepubliceerd artikel.

    Elke publicatie levert een nieuwe versie op. Zo is altijd na te gaan welke
    instructie op welk moment gold (Archiefwet, kwaliteitsborging).
    """

    artikel = models.ForeignKey(Artikel, on_delete=models.CASCADE, related_name="versies")
    versie = models.PositiveIntegerField()
    inhoud = models.JSONField()
    toelichting = models.CharField(max_length=300, blank=True)
    gepubliceerd_door = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    gepubliceerd_op = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "artikelversie"
        verbose_name_plural = "artikelversies"
        ordering = ["-versie"]
        constraints = [models.UniqueConstraint(fields=["artikel", "versie"], name="uniek_versienummer")]

    def __str__(self):
        return f"{self.artikel} v{self.versie}"


class Profiel(models.Model):
    gebruiker = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="kennisbank_profiel"
    )
    onboarding = models.BooleanField(default=False)


class Favoriet(models.Model):
    gebruiker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    artikel = models.ForeignKey(Artikel, on_delete=models.CASCADE)
    aangemaakt_op = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["gebruiker", "artikel"], name="uniek_favoriet")]


class RecentBezocht(models.Model):
    """Persoonlijke lijst 'recent bezocht'. Beperkt tot KB_RECENT_MAX regels en KB_BEWAAR_RECENT_DAGEN."""

    gebruiker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    artikel = models.ForeignKey(Artikel, on_delete=models.CASCADE)
    bezocht_op = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-bezocht_op"]
        constraints = [models.UniqueConstraint(fields=["gebruiker", "artikel"], name="uniek_recent")]


class WeergaveTelling(models.Model):
    """Aantal weergaven per artikel per dag. Bevat bewust geen gebruikersgegevens."""

    artikel = models.ForeignKey(Artikel, on_delete=models.CASCADE, related_name="weergaven")
    datum = models.DateField()
    aantal = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["artikel", "datum"], name="uniek_weergave_per_dag")]


class ZoekTelling(models.Model):
    """Zoektermen per dag, zonder gebruiker. 'zonder_resultaat' laat zien welke kennis ontbreekt."""

    term = models.CharField(max_length=100)
    datum = models.DateField()
    aantal = models.PositiveIntegerField(default=0)
    zonder_resultaat = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["term", "datum"], name="uniek_zoekterm_per_dag")]


class AssistentTelling(models.Model):
    """Gebruik van de assistent per dag. De vragen zelf worden niet opgeslagen."""

    datum = models.DateField(unique=True)
    vragen = models.PositiveIntegerField(default=0)
    zonder_bron = models.PositiveIntegerField(default=0)


class VoorstelStatus(models.TextChoices):
    NIEUW = "nieuw", "Nieuw"
    IN_BEHANDELING = "in_behandeling", "In behandeling"
    VERWERKT = "verwerkt", "Verwerkt"
    AFGEWEZEN = "afgewezen", "Afgewezen"


class Verbetervoorstel(models.Model):
    artikel = models.ForeignKey(Artikel, on_delete=models.CASCADE, related_name="voorstellen")
    artikel_versie = models.PositiveIntegerField(help_text="Versie van het artikel bij indienen.")
    citaat = models.TextField(blank=True, help_text="De tekst die de indiener had geselecteerd.")
    tekst = models.TextField()
    ingediend_door = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ingediende_voorstellen",
    )
    ingediend_op = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=VoorstelStatus.choices, default=VoorstelStatus.NIEUW)
    terugkoppeling = models.TextField(blank=True)
    behandeld_door = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="behandelde_voorstellen",
    )
    behandeld_op = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "verbetervoorstel"
        verbose_name_plural = "verbetervoorstellen"
        ordering = ["-ingediend_op"]

    def __str__(self):
        return f"Voorstel bij {self.artikel} ({self.get_status_display()})"

    @property
    def is_open(self):
        return self.status in {VoorstelStatus.NIEUW, VoorstelStatus.IN_BEHANDELING}
