import re

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
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


class GroepLabel(models.Model):
    """Een leesbare naam bij een groep uit de identity provider.

    In Entra ID bevat de groepen-claim vaak object-id's (GUID's) in plaats van groepsnamen. Een
    beheerder die toegang regelt, ziet dan een lijst codes waarin hij niets terugkent. Hier zet hij
    erbij welke groep dat is; de kennisbank gebruikt dat label overal waar de groep wordt getoond.
    """

    groep = models.OneToOneField(Group, on_delete=models.CASCADE, related_name="kennisbank_label")
    omschrijving = models.CharField(
        max_length=120,
        help_text="Hoe deze groep in Entra ID heet, bijvoorbeeld 'RWS-Handhaving-MN-Procesmanagement'.",
    )

    class Meta:
        verbose_name = "groepsnaam"
        verbose_name_plural = "groepsnamen"
        ordering = ["omschrijving"]

    def __str__(self):
        return self.omschrijving


def groepnaam(groep: Group) -> str:
    """De leesbare naam van een groep: het label als de beheerder er een heeft gezet, anders de code."""
    label = getattr(groep, "kennisbank_label", None)
    return label.omschrijving if label else groep.name


#: Een groepsnaam die eruitziet als een object-id uit Entra ID en dus voor niemand leesbaar is.
GUID_PATROON = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


class Cluster(models.Model):
    naam = models.CharField(max_length=80, unique=True)
    volgorde = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["volgorde", "naam"]

    def __str__(self):
        return self.naam


def normaliseer_tag(naam: str) -> str:
    """Tags zijn kleine letters met enkele spaties, max. 60 tekens — overal dezelfde regel (beheer en import),
    zodat 'Omgevingswet' en 'omgevingswet' één tag zijn en een import later in het beheer niet als wijziging telt."""
    return " ".join((naam or "").split()).strip().lower()[:60]


class Tag(models.Model):
    naam = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["naam"]

    def __str__(self):
        return self.naam

    def save(self, *args, **kwargs):
        self.naam = normaliseer_tag(self.naam)
        super().save(*args, **kwargs)


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


#: Grootste HTML-tekst van één artikel. Afgestemd op de grens van de Word-import (2 MB), met ruimte
#: om daarna nog te bewerken. De instelling DATA_UPLOAD_MAX_MEMORY_SIZE moet hier ruim boven liggen,
#: anders kapt Django het verzoek af vóórdat deze nette melding kan verschijnen.
MAX_INHOUD = 4 * 1024 * 1024


class Artikel(models.Model):
    omgeving = models.ForeignKey(Omgeving, on_delete=models.PROTECT, related_name="artikelen")
    slug = models.SlugField(
        max_length=120,
        db_index=True,
        editable=False,
        help_text="Leesbaar deel van de link; wordt uit de titel afgeleid. De link werkt op het nummer.",
    )
    titel = models.CharField(max_length=200)
    samenvatting = models.TextField(help_text="Eén of twee zinnen: waar gaat dit artikel over?")
    inhoud = models.TextField(
        blank=True,
        help_text="De tekst van het artikel. Selecteer tekst en klik op 'Sectie' om er een in- en uitklapbare sectie "
        "van te maken; markeer alinea's als 'Onboarding' om ze alleen aan nieuwe collega's te tonen. "
        "Tekst buiten een sectie is altijd zichtbaar.",
    )
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
    herzien_voor = models.DateField(
        null=True,
        blank=True,
        verbose_name="opnieuw nakijken voor",
        help_text="Wanneer dit artikel uiterlijk opnieuw moet worden nagekeken. Leeg laten mag; bij het "
        "publiceren vult de kennisbank hem zelf in volgens de termijn die IT heeft ingesteld. "
        "Alleen zichtbaar voor redacteuren.",
    )
    versie = models.PositiveIntegerField(default=0, editable=False)
    gepubliceerd_op = models.DateTimeField(null=True, blank=True, editable=False)
    aangemaakt_op = models.DateTimeField(auto_now_add=True)
    gewijzigd_op = models.DateTimeField(auto_now=True)
    # Opgeslagen zoekdocument (titel, tags, samenvatting, secties); bijgewerkt in diensten.herbouw_secties.
    zoekvector = SearchVectorField(null=True, editable=False)

    objects = ArtikelQuerySet.as_manager()

    class Meta:
        verbose_name = "artikel"
        verbose_name_plural = "artikelen"
        ordering = ["titel"]
        indexes = [GinIndex(fields=["zoekvector"], name="artikel_zoekvector_gin")]

    def __str__(self):
        return self.titel

    def get_absolute_url(self):
        return f"/artikel/{self.pk}/{self.slug}" if self.slug else f"/artikel/{self.pk}"

    def save(self, *args, **kwargs):
        from django.utils.text import slugify

        from .inhoud import schoon

        if not self.slug:
            # Twee artikelen met dezelfde titel krijgen elk een eigen slug. Anders kon een oude link
            # (/artikel/<slug>) naar meerdere artikelen wijzen, en die gaf dan voor allemaal een 404.
            basis = slugify(self.titel)[:120] or "artikel"
            kandidaat, n = basis, 1
            while Artikel.objects.filter(slug=kandidaat).exclude(pk=self.pk).exists():
                n += 1
                kandidaat = f"{basis[:115]}-{n}"
            self.slug = kandidaat
        self.inhoud = schoon(self.inhoud)
        super().save(*args, **kwargs)


class Sectie(models.Model):
    """Afgeleide tabel: de secties van een artikel, opgebouwd uit Artikel.inhoud (zie diensten.herbouw_secties).

    Wordt gebruikt voor zoeken en voor de assistent (per sectie een treffer). Niet handmatig bewerken.
    volgorde 0 is de inleiding (tekst vóór de eerste sectiekop), met een lege kop.
    """

    artikel = models.ForeignKey(Artikel, on_delete=models.CASCADE, related_name="secties")
    volgorde = models.PositiveIntegerField(default=0)
    kop = models.CharField(max_length=200, blank=True)
    inhoud = models.TextField(blank=True)
    zoekvector = SearchVectorField(null=True, editable=False)

    class Meta:
        verbose_name = "sectie"
        verbose_name_plural = "secties"
        ordering = ["volgorde", "id"]
        indexes = [GinIndex(fields=["zoekvector"], name="sectie_zoekvector_gin")]

    def __str__(self):
        return self.kop or "(inleiding)"


class ArtikelVersie(models.Model):
    """Onveranderlijke momentopname van een gepubliceerd artikel.

    Elke publicatie levert een nieuwe versie op. Zo is altijd na te gaan welke
    instructie op welk moment gold (Archiefwet, kwaliteitsborging).
    """

    artikel = models.ForeignKey(Artikel, on_delete=models.CASCADE, related_name="versies")
    versie = models.PositiveIntegerField()
    inhoud = models.JSONField()
    toelichting = models.CharField(max_length=300, blank=True)
    kleine_correctie = models.BooleanField(
        default=False,
        help_text="Typfout, opmaak of iets anders waar medewerkers geen melding van hoeven te krijgen.",
    )
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
    mail_bij_favorieten = models.BooleanField(
        default=True, help_text="E-mail ontvangen als een favoriet artikel inhoudelijk wijzigt."
    )
    nieuws_gezien_op = models.DateTimeField(
        null=True, blank=True, help_text="Wanneer de gebruiker de nieuwspagina voor het laatst opende."
    )
    #: Keuzes bij de Word-import. Standaard uit: de opmaak in een Word-document zegt niet betrouwbaar
    #: wat de bedoeling was, dus de redacteur zet dit per geval zelf aan. Zijn laatste keuze blijft staan.
    import_kop_als_titel = models.BooleanField(
        default=False, help_text="Bij een Word-import de eerste kop in het document als artikeltitel gebruiken."
    )
    import_tabelkoprij = models.BooleanField(
        default=False, help_text="Bij een Word-import de eerste rij van elke tabel als koprij opmaken."
    )


class WijzigingGezien(models.Model):
    """Tot en met welke versie van een artikel de gebruiker de wijzigingsmelding heeft afgevinkt ("Ik snap het").

    Eén regel per gebruiker en artikel. De melding verschijnt (opnieuw) zodra er een inhoudelijke versie
    is met een hoger nummer dan hier staat.
    """

    gebruiker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    artikel = models.ForeignKey(Artikel, on_delete=models.CASCADE, related_name="gezien_door")
    versie = models.PositiveIntegerField()
    gezien_op = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "wijziging gezien"
        verbose_name_plural = "wijzigingen gezien"
        constraints = [models.UniqueConstraint(fields=["gebruiker", "artikel"], name="uniek_gezien_per_artikel")]


class FavorietenMail(models.Model):
    """Wachtrij voor de e-mail aan medewerkers van wie een favoriet artikel inhoudelijk is gewijzigd.

    Bij publicatie komt er per ontvanger een regel bij; het commando `kennisbank_favorietenmail`
    (ook aangeroepen door `kennisbank_opschonen`) bundelt alle openstaande regels per ontvanger tot
    één e-mail. Zie KB_FAVORIETEN_MAIL in de configuratie.
    """

    gebruiker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    artikel = models.ForeignKey(Artikel, on_delete=models.CASCADE)
    versie = models.PositiveIntegerField()
    toelichting = models.CharField(max_length=300, blank=True)
    aangemaakt_op = models.DateTimeField(default=timezone.now)
    verzonden_op = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "favorietenmail"
        verbose_name_plural = "favorietenmails"
        ordering = ["aangemaakt_op"]


class BerichtStatus(models.TextChoices):
    CONCEPT = "concept", "Concept"
    GEPUBLICEERD = "gepubliceerd", "Gepubliceerd"


class BerichtQuerySet(models.QuerySet):
    def gepubliceerd(self):
        return self.filter(status=BerichtStatus.GEPUBLICEERD)

    def actueel(self):
        """Gepubliceerd en niet verlopen."""
        nu = timezone.now()
        from django.db.models import Q

        return self.gepubliceerd().filter(Q(verloopt_op__isnull=True) | Q(verloopt_op__gt=nu))


class Bericht(models.Model):
    """Nieuwsbericht voor medewerkers van een omgeving: nieuwe werkwijzen, gewijzigde artikelen, mededelingen."""

    omgeving = models.ForeignKey(Omgeving, on_delete=models.PROTECT, related_name="berichten")
    titel = models.CharField(max_length=200)
    tekst = models.TextField(help_text="De inhoud van het bericht. Zelfde opmaakmogelijkheden als een artikel.")
    artikelen = models.ManyToManyField(
        Artikel, blank=True, related_name="berichten", help_text="Artikelen waar dit bericht over gaat."
    )
    status = models.CharField(max_length=20, choices=BerichtStatus.choices, default=BerichtStatus.CONCEPT)
    vastgepind = models.BooleanField(default=False, help_text="Bovenaan de nieuwspagina houden.")
    gepubliceerd_op = models.DateTimeField(null=True, blank=True, editable=False)
    verloopt_op = models.DateTimeField(
        null=True, blank=True, help_text="Daarna staat het bericht onder 'Ouder nieuws' (leeg = geen einddatum)."
    )
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    aangemaakt_op = models.DateTimeField(auto_now_add=True)
    gewijzigd_op = models.DateTimeField(auto_now=True)

    objects = BerichtQuerySet.as_manager()

    class Meta:
        verbose_name = "nieuwsbericht"
        verbose_name_plural = "nieuwsberichten"
        ordering = ["-vastgepind", "-gepubliceerd_op", "-aangemaakt_op"]

    def __str__(self):
        return self.titel

    def save(self, *args, **kwargs):
        from .inhoud import schoon

        self.tekst = schoon(self.tekst)
        if self.status == BerichtStatus.GEPUBLICEERD and not self.gepubliceerd_op:
            self.gepubliceerd_op = timezone.now()
        elif self.status != BerichtStatus.GEPUBLICEERD:
            self.gepubliceerd_op = None  # terug naar concept: bij opnieuw publiceren telt het weer als nieuw
        super().save(*args, **kwargs)


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
    """Zoektermen per dag en per omgeving, zonder gebruiker. 'zonder_resultaat' laat zien welke kennis ontbreekt.

    Een zoekterm kan een naam of zaaknummer bevatten; daarom zien redacteuren alleen de termen van
    hun eigen omgeving(en). Zoekt iemand in meerdere omgevingen tegelijk, dan telt de term in elk mee.
    """

    omgeving = models.ForeignKey(Omgeving, on_delete=models.CASCADE, null=True, related_name="zoektellingen")
    term = models.CharField(max_length=100)
    datum = models.DateField()
    aantal = models.PositiveIntegerField(default=0)
    zonder_resultaat = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["omgeving", "term", "datum"], name="uniek_zoekterm_per_dag_omgeving")
        ]


class AssistentTelling(models.Model):
    """Gebruik van de assistent per dag en per omgeving. De vragen zelf worden niet opgeslagen."""

    omgeving = models.ForeignKey(Omgeving, on_delete=models.CASCADE, null=True, related_name="assistenttellingen")
    datum = models.DateField()
    vragen = models.PositiveIntegerField(default=0)
    zonder_bron = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["omgeving", "datum"], name="uniek_assistent_per_dag_omgeving")]


class AssistentDagTotaal(models.Model):
    """Aantal aanroepen van het taalmodel per dag, over alle omgevingen heen: voor het kostenplafond
    (KB_ASSISTENT_DAGLIMIET). Bewust in de database, zodat de limiet geldt voor alle replica's samen."""

    datum = models.DateField(unique=True)
    modelaanroepen = models.PositiveIntegerField(default=0)


class Systeemstand(models.Model):
    """Wanneer een onderhoudstaak voor het laatst heeft gelopen.

    Eén regel per taak (bijvoorbeeld "opschonen"). De statuspagina gebruikt dit om te zien of de
    geplande taken daadwerkelijk lopen; zonder deze registratie is "de cron staat niet aan" pas te
    merken als er iets niet meer werkt.
    """

    sleutel = models.CharField(max_length=60, unique=True)
    moment = models.DateTimeField(default=timezone.now)
    melding = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "status"
        verbose_name_plural = "status"
        ordering = ["sleutel"]

    def __str__(self):
        return f"{self.sleutel}: {self.moment:%Y-%m-%d %H:%M}"


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
    #: Afgeleid: het laatste bericht van procesmanagement. Alleen `diensten.voorstelbericht_toevoegen`
    #: schrijft hier, zodat er geen tweede invoerveld is dat dit stil kan overschrijven.
    terugkoppeling = models.TextField(blank=True, editable=False)
    behandeld_door = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="behandelde_voorstellen",
    )
    behandeld_op = models.DateTimeField(null=True, blank=True)
    #: Tot wanneer beide kanten het gesprek hebben gelezen; bepaalt of er een "nieuw"-stip staat.
    gelezen_indiener_op = models.DateTimeField(null=True, blank=True, editable=False)
    gelezen_redactie_op = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "verbetervoorstel"
        verbose_name_plural = "verbetervoorstellen"
        ordering = ["-ingediend_op"]

    def __str__(self):
        return f"Voorstel bij {self.artikel} ({self.get_status_display()})"

    @property
    def is_open(self):
        return self.status in {VoorstelStatus.NIEUW, VoorstelStatus.IN_BEHANDELING}


#: Een bericht mag lang zijn (een onderbouwde terugkoppeling), maar niet eindeloos. Eén bron van
#: waarheid: de API valideert hierop en het model begrenst hetzelfde veld.
MAX_VOORSTELBERICHT = 5000


class VoorstelBericht(models.Model):
    """Eén bericht van procesmanagement in de behandeling van een verbetervoorstel.

    Een voorstel is zelden in één keer klaar: procesmanagement wil tussentijds kunnen melden dat het
    is opgepakt, en later wat ermee is gebeurd. Elk bericht komt bij de indiener binnen als melding en
    als e-mail.

    Bewust eenrichtingsverkeer: de medewerker dient een voorstel in, procesmanagement koppelt terug en
    houdt hem op de hoogte. Een gesprek heen en weer in de kennisbank zou een tweede kanaal naast
    Teams en e-mail opleveren, en de verwachting wekken dat iemand meeleest.

    `van_redactie` staat daarom altijd aan. Het veld blijft bestaan omdat er in een bestaande
    installatie berichten van een indiener kunnen staan uit de periode dat antwoorden wel kon, en
    omdat de anonimisering erop filtert.
    """

    voorstel = models.ForeignKey(Verbetervoorstel, on_delete=models.CASCADE, related_name="berichten")
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    van_redactie = models.BooleanField(
        default=True, help_text="Van procesmanagement (aan) of van de indiener (uit; komt niet meer voor)."
    )
    tekst = models.TextField(max_length=MAX_VOORSTELBERICHT)
    moment = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "bericht bij een voorstel"
        verbose_name_plural = "gesprek"
        ordering = ["moment", "pk"]

    def __str__(self):
        return f"{'Procesmanagement' if self.van_redactie else 'Indiener'}: {self.tekst[:60]}"

    @property
    def naam(self) -> str:
        """Wie het bericht schreef, of 'Procesmanagement' / 'Indiener' als de naam is verwijderd."""
        if self.auteur:
            return self.auteur.get_full_name() or self.auteur.get_username()
        return "Procesmanagement" if self.van_redactie else "Indiener"


class BewerkClaim(models.Model):
    """Wie heeft dit artikel op dit moment in het bewerkscherm open.

    Een zacht slot: het informeert, het blokkeert niet. Een tweede redacteur mag doorgaan na een
    waarschuwing; beiden zien van elkaar dat ze in hetzelfde artikel zitten en kunnen overleggen.
    De claim wordt vanuit het bewerkscherm periodiek verlengd en vervalt daarna vanzelf, zodat een
    gesloten tabblad of een dichtgeklapte laptop nooit een artikel op slot laat staan.
    """

    artikel = models.ForeignKey(Artikel, on_delete=models.CASCADE, related_name="bewerkclaims")
    gebruiker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    begonnen_op = models.DateTimeField(default=timezone.now)
    laatst_gezien = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "bewerkclaim"
        verbose_name_plural = "bewerkclaims"
        constraints = [models.UniqueConstraint(fields=["artikel", "gebruiker"], name="uniek_claim_per_gebruiker")]
        indexes = [models.Index(fields=["artikel", "laatst_gezien"])]

    def __str__(self):
        return f"{self.gebruiker} bewerkt {self.artikel}"

    @property
    def naam(self) -> str:
        return self.gebruiker.get_full_name() or self.gebruiker.get_username()
