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
    #: Stap C van het reviewproces (ontwerp 11 november): conceptversies kunnen ter inzage naar een
    #: reviewteam. Uit = alles werkt zoals daarvoor.
    reviewproces = models.BooleanField(
        "reviewproces gebruiken",
        default=False,
        help_text="Redacteuren kunnen een conceptversie ter inzage geven aan een reviewteam. Een review blokkeert "
        "nooit de publicatie.",
    )

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
        verbose_name = "cluster"
        verbose_name_plural = "clusters"
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
        verbose_name = "zaaktype"
        verbose_name_plural = "zaaktypen"
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


class Sjabloon(models.Model):
    """Een voorbeeldartikel waarmee een nieuwe omgeving niet leeg begint.

    Een lege kennisbank is het grootste risico bij invoering: de eerste medewerker die inlogt vindt
    niets, en de eerste redacteur weet niet hoe een goed artikel eruitziet. Een beheerder kan hier
    sjablonen klaarzetten en die met één actie in een nieuwe omgeving plaatsen — als concept, zodat er
    niets ongewenst zichtbaar wordt.

    De inhoud wordt niet meegeleverd: die hoort van de organisatie zelf te komen, in haar eigen
    woorden. Zie docs/functioneel-beheer.md.
    """

    naam = models.CharField(max_length=120, help_text="Waar dit sjabloon voor is, bijvoorbeeld 'Lege werkinstructie'.")
    titel = models.CharField(max_length=200, help_text="De titel die het nieuwe artikel krijgt.")
    samenvatting = models.TextField(blank=True)
    inhoud = models.TextField(
        blank=True,
        help_text="De tekst van het artikel, met dezelfde opmaak als in de editor. "
        'Secties maak je met <section class="sectie"><h2 class="sectie-kop">Titel</h2>…</section>.',
    )
    soort = models.CharField(max_length=20, choices=Soort.choices, default=Soort.WERKINSTRUCTIE)
    volgorde = models.PositiveIntegerField(default=0, help_text="Bepaalt de volgorde waarin ze worden geplaatst.")
    actief = models.BooleanField(default=True, help_text="Alleen actieve sjablonen worden aangeboden.")

    class Meta:
        verbose_name = "sjabloon"
        verbose_name_plural = "sjablonen"
        ordering = ["volgorde", "naam"]

    def __str__(self):
        return self.naam


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
        indexes = [
            GinIndex(fields=["zoekvector"], name="artikel_zoekvector_gin"),
            # De artikelenlijst in het beheer en de statuspagina filteren hier elke keer op.
            models.Index(fields=["status", "herzien_voor"], name="artikel_herzien_idx"),
        ]

    def __str__(self):
        return self.titel

    def get_absolute_url(self):
        return f"/artikel/{self.pk}/{self.slug}" if self.slug else f"/artikel/{self.pk}"

    def save(self, *args, **kwargs):
        from django.utils.text import slugify

        from .inhoud import schoon

        if not self.slug:
            # Twee artikelen met dezelfde titel binnen één omgeving krijgen elk een eigen slug. Anders
            # kon een oude link (/artikel/<slug>) naar meerdere artikelen wijzen, en die gaf dan voor
            # allemaal een 404.
            #
            # Bewust alleen binnen de eigen omgeving: keek de controle over omgevingen heen, dan kon een
            # redacteur uit de "-2" achter zijn slug afleiden dat er elders in de installatie een artikel
            # met exact dezelfde titel bestaat. Dat is informatie over een omgeving waar hij niets mag
            # zien, en overal elders is de afscherming wél per omgeving.
            #
            # In één query in plaats van een lus: die deed er één per poging, dus het dertiende artikel
            # met dezelfde titel kostte veertien queries.
            basis = slugify(self.titel)[:120] or "artikel"
            bezet = set(
                Artikel.objects.filter(omgeving_id=self.omgeving_id, slug__startswith=basis[:115])
                .exclude(pk=self.pk)
                .values_list("slug", flat=True)
            )
            kandidaat, n = basis, 1
            while kandidaat in bezet:
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
    #: Hoe het met de review stond bij publicatie ("Akkoord van Team Water", "Gepubliceerd zonder
    #: akkoord van …"). Leeg als het reviewproces niet werd gebruikt.
    review = models.CharField(max_length=300, blank=True)

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
    #: Of de gebruiker de openingsvraag ("ben je nieuw bij RWS?") al heeft gezien. Los van `onboarding`,
    #: want "nee, ik ben niet nieuw" en "ik heb de vraag nog niet gehad" zijn niet hetzelfde: zonder dit
    #: veld zou de vraag bij elke inlog terugkomen zolang iemand de uitleg uit laat staan.
    begroet_op = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "profiel"
        verbose_name_plural = "profielen"


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
        verbose_name = "favoriet"
        verbose_name_plural = "favorieten"
        constraints = [models.UniqueConstraint(fields=["gebruiker", "artikel"], name="uniek_favoriet")]


class RecentBezocht(models.Model):
    """Persoonlijke lijst 'recent bezocht'. Beperkt tot KB_RECENT_MAX regels en KB_BEWAAR_RECENT_DAGEN."""

    gebruiker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    artikel = models.ForeignKey(Artikel, on_delete=models.CASCADE)
    bezocht_op = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "recent bezocht artikel"
        verbose_name_plural = "recent bezochte artikelen"
        ordering = ["-bezocht_op"]
        constraints = [models.UniqueConstraint(fields=["gebruiker", "artikel"], name="uniek_recent")]


class WeergaveTelling(models.Model):
    """Aantal weergaven per artikel per dag. Bevat bewust geen gebruikersgegevens."""

    artikel = models.ForeignKey(Artikel, on_delete=models.CASCADE, related_name="weergaven")
    datum = models.DateField()
    aantal = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "weergavetelling"
        verbose_name_plural = "weergavetellingen"
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
        verbose_name = "zoektelling"
        verbose_name_plural = "zoektellingen"
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
        verbose_name = "assistenttelling"
        verbose_name_plural = "assistenttellingen"
        constraints = [models.UniqueConstraint(fields=["omgeving", "datum"], name="uniek_assistent_per_dag_omgeving")]


class AssistentDagTotaal(models.Model):
    """Aantal aanroepen van het taalmodel per dag, over alle omgevingen heen: voor het kostenplafond
    (KB_ASSISTENT_DAGLIMIET). Bewust in de database, zodat de limiet geldt voor alle replica's samen."""

    datum = models.DateField(unique=True)
    modelaanroepen = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "assistent-dagtotaal"
        verbose_name_plural = "assistent-dagtotalen"


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
    #: Afgesloten zonder oordeel, omdat het artikel is gearchiveerd ("het artikel is ingetrokken").
    VERVALLEN = "vervallen", "Vervallen"


#: Alle eindstanden. Afgehandeld is definitief (besluit van Alex, 11 november).
AFGEHANDELD = (VoorstelStatus.VERWERKT, VoorstelStatus.AFGEWEZEN, VoorstelStatus.VERVALLEN)
OPEN = (VoorstelStatus.NIEUW, VoorstelStatus.IN_BEHANDELING)


def standaard_clusterbak(artikel):
    """De bak voor een nieuw voorstel: het cluster als het artikel er precies één heeft, anders
    None (de algemene bak). Een artikel zonder cluster geldt voor iedereen, en een artikel met twee
    clusters bedient twee teams: beide horen in de algemene bak."""
    clusters = list(artikel.clusters.all()[:2])
    return clusters[0] if len(clusters) == 1 else None


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
    #: Tot wanneer de indiener het gesprek heeft gelezen. Per persoon, want een voorstel heeft
    #: precies één indiener.
    gelezen_indiener_op = models.DateTimeField(null=True, blank=True, editable=False)
    #: Tot wanneer *de redactie* het gesprek heeft gelezen -- bewust één stempel voor de hele
    #: redactie, niet per redacteur. Opent redacteur A het voorstel, dan is de stip ook voor B weg.
    #: Dat is de bedoeling: dit is een teampostvak. Een rij per redacteur (het patroon van
    #: WijzigingGezien) zou een nieuwe collega bij binnenkomst elk afgehandeld voorstel als
    #: ongelezen tonen, en omdat het gesprek eenrichting is krijgt de redactie na het eerste
    #: bericht niets meer binnen. Wie het heeft opgepakt staat in behandeld_door.
    gelezen_redactie_op = models.DateTimeField(null=True, blank=True, editable=False)
    #: In wiens bak het voorstel ligt. Leeg = de gezamenlijke bak van de omgeving. Alleen de functies
    #: in diensten (voorstel_naar_bak) zetten dit veld, zodat de status en de e-mail meelopen.
    eigenaar = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="voorstellen_in_bak",
        editable=False,
    )
    eigenaar_sinds = models.DateTimeField(null=True, blank=True, editable=False)
    #: Wanneer de eigenaar het voorstel voor het laatst opende. Zo ziet hij wat nieuw in zijn bak is:
    #: "gelezen" is per bak. Voor de gezamenlijke bak blijft gelezen_redactie_op het teamstempel.
    eigenaar_gezien_op = models.DateTimeField(null=True, blank=True, editable=False)
    #: In welke werkbak het voorstel ligt zolang niemand het heeft opgepakt (en als label daarna):
    #: een cluster, of leeg = de algemene bak. Bij binnenkomst gezet door save(): precies één cluster
    #: bij het artikel → die clusterbak; geen of meerdere clusters → algemeen. Daarna met de hand te
    #: verplaatsen.
    cluster = models.ForeignKey(
        Cluster,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="voorstellen",
        verbose_name="clusterbak",
        help_text="Leeg = de algemene bak.",
    )
    #: Door de redactie verborgen voor collega's (onder "Alle voorstellen"), bijvoorbeeld omdat er de
    #: naam van een collega in staat. De indiener en de redactie zien het gewoon.
    verborgen = models.BooleanField(
        "verbergen voor collega's",
        default=False,
        help_text="Het voorstel staat dan niet meer onder 'Alle voorstellen' en kan niet meer worden gesteund, "
        "bijvoorbeeld omdat er een naam van een collega in staat. De indiener ziet het gewoon.",
    )

    #: Afgewezen als dubbel van dit voorstel (besluit van Alex: niet samenvoegen; de steun gaat niet mee,
    #: anders telt een steunbetuiging dubbel).
    dubbel_van = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dubbele",
        editable=False,
    )

    #: Meegenomen in de nieuwe versie (meestal de conceptversie) van het artikel (reviewpunt 11). Bij
    #: publiceren wordt dit verwerkt_in_versie, en vraagt de kennisbank of het voorstel af kan.
    in_conceptversie = models.BooleanField(default=False, editable=False)
    verwerkt_in_versie = models.PositiveIntegerField(null=True, blank=True, editable=False)

    def save(self, *args, **kwargs):
        if self._state.adding and self.cluster_id is None and self.artikel_id:
            self.cluster = standaard_clusterbak(self.artikel)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "verbetervoorstel"
        verbose_name_plural = "verbetervoorstellen"
        ordering = ["-ingediend_op"]
        indexes = [models.Index(fields=["eigenaar", "status"], name="voorstel_bak_idx")]

    def __str__(self):
        return f"Voorstel bij {self.artikel} ({self.get_status_display()})"

    @property
    def is_open(self):
        return self.status in OPEN


class VoorstelNotitie(models.Model):
    """Een interne notitie bij een voorstel: alleen de redactie ziet hem.

    Voor wat de volgende behandelaar moet weten ("gebeld met Toezicht, wacht op antwoord"), zonder dat
    het bij de indiener belandt. Bij het anonimiseren van een afgehandeld voorstel gaan de notities
    weg: er kunnen namen in staan.
    """

    voorstel = models.ForeignKey(Verbetervoorstel, on_delete=models.CASCADE, related_name="notities")
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    tekst = models.TextField(max_length=4000)
    moment = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "interne notitie"
        verbose_name_plural = "interne notities"
        ordering = ["moment", "pk"]

    def __str__(self):
        return f"Notitie bij voorstel {self.voorstel_id}"


class Steun(models.Model):
    """Een collega steunt een verbetervoorstel (de like-knop).

    Eén keer per persoon, alleen bij een open voorstel en niet bij je eigen voorstel; dat bewaken de
    diensten en de unieke index. Collega's zien alleen het aantal, de redactie ziet ook wie. Bij de
    anonimisering van een afgehandeld voorstel wordt `gebruiker` leeggemaakt: het aantal blijft, de
    namen gaan weg.
    """

    voorstel = models.ForeignKey(Verbetervoorstel, on_delete=models.CASCADE, related_name="steun")
    gebruiker = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    moment = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "steun"
        verbose_name_plural = "steun"
        ordering = ["moment", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["voorstel", "gebruiker"],
                condition=models.Q(gebruiker__isnull=False),
                name="een_steun_per_persoon",
            )
        ]

    def __str__(self):
        return f"Steun voor voorstel {self.voorstel_id}"

    @property
    def naam(self) -> str:
        if not self.gebruiker:
            return "Collega (geanonimiseerd)"
        return self.gebruiker.get_full_name() or self.gebruiker.get_username()


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


class Conceptversie(models.Model):
    """Een nieuwe versie van een gepubliceerd artikel waar nog aan wordt gewerkt.

    Medewerkers blijven de gepubliceerde tekst zien; de redactie werkt in de conceptversie. Er is er
    hoogstens één per artikel, gedeeld door de redactie (anders dan een kladversie, die van één persoon
    is en alleen een vangnet). Publiceren zet de inhoud in het artikel, maakt een nieuwe versie en
    verwijdert de conceptversie. Fundament voor het reviewproces (ontwerp 11 november).

    `velden` bevat het bewerkformulier zoals de redacteur het opsloeg: titel, samenvatting, inhoud
    (geschoond), soort, eigenaar, omgeving (pk), herzien_voor, clusters/zaaktypen (pk's) en tags_tekst.
    """

    artikel = models.OneToOneField(Artikel, on_delete=models.CASCADE, related_name="conceptversie")
    velden = models.JSONField(default=dict)
    #: Het versienummer van het artikel toen de conceptversie begon, en de stempel ervan. Wijkt het
    #: artikel daarna af (bijvoorbeeld via de import), dan waarschuwt het bewerkscherm.
    basis_versie = models.PositiveIntegerField(default=0)
    basis_stempel = models.CharField(max_length=40, blank=True)
    gestart_door = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    gestart_op = models.DateTimeField(default=timezone.now)
    bijgewerkt_door = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    bijgewerkt_op = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "conceptversie"
        verbose_name_plural = "conceptversies"

    def __str__(self):
        return f"Conceptversie van {self.artikel}"

    @property
    def stempel(self) -> str:
        return self.bijgewerkt_op.isoformat() if self.bijgewerkt_op else ""

    @property
    def titel(self) -> str:
        return self.velden.get("titel") or self.artikel.titel


class Kladversie(models.Model):
    """Onopgeslagen werk in het bewerkscherm, zodat een verlopen sessie of een dichtgeklapte laptop
    geen werk kost.

    Eén kladversie per persoon per artikel; voor een nieuw, nog nooit opgeslagen artikel is ``artikel``
    leeg en heeft iedereen er hooguit één. Een kladversie is nooit zichtbaar voor lezers, telt niet als
    versie en levert geen wijzigingsmelding op. Redacteuren van dezelfde omgeving zien dát hij er is en
    kunnen hem lezen (bijvoorbeeld om over te nemen als iemand ziek is).

    Na opslaan of weggooien blijft de rij staan met ``afgesloten_op`` gezet en lege ``velden``: een
    grafsteen. Zonder die markering zou een oude kopie in de browser van een andere laptop de kladversie
    later weer tot leven wekken, terwijl het werk allang is opgeslagen. Na KB_KLADVERSIE_DAGEN ruimt de
    dagelijkse opschoonronde zowel open als afgesloten kladversies op.
    """

    gebruiker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="kladversies")
    artikel = models.ForeignKey(
        Artikel,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="kladversies",
        help_text="Leeg bij een nieuw artikel dat nog nooit is opgeslagen.",
    )
    #: Voor een nieuw artikel: de gekozen omgeving, zodat collega's van die omgeving hem kunnen zien.
    #: Alleen gezet als de schrijver daar redacteur is.
    omgeving = models.ForeignKey(Omgeving, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    #: De formuliervelden: titel, samenvatting, inhoud, soort, omgeving, eigenaar, tags_tekst,
    #: clusters, zaaktypen.
    velden = models.JSONField(default=dict, blank=True)
    #: Het stempel (gewijzigd_op) van het artikel toen deze kladversie begon. Terugzetten zet dit
    #: stempel terug in het formulier, zodat de conflictcontrole aanslaat als iemand anders intussen
    #: heeft opgeslagen -- in plaats van dat diens werk ongemerkt wordt overschreven.
    basis_stempel = models.CharField(max_length=64, blank=True)
    aangemaakt_op = models.DateTimeField(default=timezone.now)
    bijgewerkt_op = models.DateTimeField(default=timezone.now)
    afgesloten_op = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "kladversie"
        verbose_name_plural = "kladversies"
        ordering = ["-bijgewerkt_op"]
        constraints = [
            models.UniqueConstraint(
                fields=["gebruiker", "artikel"],
                condition=models.Q(artikel__isnull=False),
                name="een_kladversie_per_artikel",
            ),
            models.UniqueConstraint(
                fields=["gebruiker"],
                condition=models.Q(artikel__isnull=True),
                name="een_kladversie_voor_nieuw",
            ),
        ]
        indexes = [models.Index(fields=["bijgewerkt_op"])]

    def __str__(self):
        return f"Kladversie van {self.naam}: {self.titel}"

    @property
    def naam(self) -> str:
        return self.gebruiker.get_full_name() or self.gebruiker.get_username()

    @property
    def titel(self) -> str:
        t = (self.velden or {}).get("titel") or ""
        if t:
            return t
        return self.artikel.titel if self.artikel_id else "Nieuw artikel zonder titel"

    @property
    def open(self) -> bool:
        return self.afgesloten_op is None


# --- Reviewproces (stap C, ontwerp 11 november) ------------------------------------------------


class Reviewteam(models.Model):
    """Een team dat conceptversies leest en akkoord geeft, bijvoorbeeld "Team Water".

    Wie in de groep zit (in productie een Entra ID-groep), is reviewer voor dit team. Alleen een
    beheerder maakt teams aan. De clusters bepalen welk team bij *Ter inzage* is voorgevuld.
    """

    naam = models.CharField(max_length=120)
    omgeving = models.ForeignKey(Omgeving, on_delete=models.CASCADE, related_name="reviewteams")
    groep = models.ForeignKey(
        Group,
        on_delete=models.PROTECT,
        related_name="kennisbank_reviewteams",
        help_text="De groep uit de identity provider (Entra ID). Iedereen in deze groep is reviewer voor dit team.",
    )
    clusters = models.ManyToManyField(
        "Cluster",
        blank=True,
        related_name="reviewteams",
        help_text="Bij artikelen met deze clusters staat dit team voorgevuld bij Ter inzage.",
    )

    class Meta:
        verbose_name = "reviewteam"
        verbose_name_plural = "reviewteams"
        ordering = ["naam"]
        constraints = [models.UniqueConstraint(fields=["omgeving", "naam"], name="reviewteam_naam_uniek")]

    def __str__(self):
        return self.naam


class InzageStatus(models.TextChoices):
    TER_INZAGE = "ter_inzage", "Ter inzage"
    TERUGGEGEVEN = "teruggegeven", "Teruggegeven"
    AKKOORD = "akkoord", "Akkoord"
    TERUGGEROEPEN = "teruggeroepen", "Teruggeroepen"


class Inzage(models.Model):
    """Een conceptversie ter inzage bij één reviewteam. Eén rij per team per ronde.

    Zolang er een rij *Ter inzage* is, staat de conceptversie op slot voor de redactie. Akkoord geldt
    voor precies de tekst van dat moment (`akkoord_stempel`); verandert de conceptversie daarna, dan
    vervalt het akkoord vanzelf. Bij publiceren of weggooien van de conceptversie worden de rijen
    afgesloten (`afgesloten`): ze tellen dan niet meer mee, maar blijven als geschiedenis bestaan.
    """

    artikel = models.ForeignKey("Artikel", on_delete=models.CASCADE, related_name="inzages")
    team = models.ForeignKey(Reviewteam, on_delete=models.CASCADE, related_name="inzages")
    ronde = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=InzageStatus.choices, default=InzageStatus.TER_INZAGE)
    #: De stempel van de conceptversie toen hij ter inzage ging, en bij akkoord.
    concept_stempel = models.CharField(max_length=40, blank=True)
    akkoord_stempel = models.CharField(max_length=40, blank=True)
    gestart_door = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    gestart_op = models.DateTimeField(default=timezone.now)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    opgepakt_op = models.DateTimeField(null=True, blank=True)
    afgerond_op = models.DateTimeField(null=True, blank=True)
    afgesloten = models.BooleanField(default=False)

    class Meta:
        verbose_name = "inzage"
        verbose_name_plural = "inzages"
        ordering = ["-gestart_op", "pk"]
        indexes = [models.Index(fields=["artikel", "afgesloten"], name="inzage_artikel_idx")]

    def __str__(self):
        return f"{self.artikel} bij {self.team} ({self.get_status_display()})"


class ReviewOpmerking(models.Model):
    """Een opmerking van een reviewer bij een conceptversie die ter inzage ligt."""

    inzage = models.ForeignKey(Inzage, on_delete=models.CASCADE, related_name="opmerkingen")
    #: De tekst waar de opmerking bij hoort (stap D); leeg = een algemene opmerking. Het citaat blijft
    #: bewaard, ook als de redacteur de zin later aanpast: zo is altijd terug te lezen wat er stond.
    citaat = models.TextField(blank=True, max_length=1000)
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    tekst = models.TextField(max_length=4000)
    moment = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "opmerking bij een review"
        verbose_name_plural = "opmerkingen bij reviews"
        ordering = ["moment", "pk"]

    def __str__(self):
        return f"Opmerking bij {self.inzage}"
