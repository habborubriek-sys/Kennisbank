# ruff: noqa: E501 - de teksten zijn HTML; een regel afbreken midden in een zin maakt ze niet leesbaarder
"""De standaardset hulpartikelen die het pakket meelevert (1.36.0).

Kort en op taken. Geen schermafbeeldingen: die kloppen na elke versie niet meer. Een knop of menu staat vet en
heet precies zoals op het scherm; de test `test_hulp_1360.Woorden` bewaakt dat, zodat de hulp niet stil
veroudert. Wat de functioneel beheerder zelf heeft aangepast (`Hulpartikel.aangepast`) blijft met rust.

Dit is uitleg over de kennisbank zelf. Hoe een afdeling ermee werkt (wie reviewt wat, binnen welke termijn)
hoort in een eigen artikel van die afdeling; zie `Omgeving.werkafspraken_artikel`.
"""

M, V, R, B = "medewerker", "reviewer", "redacteur", "beheerder"

STANDAARD = [
    # --- Medewerker ---------------------------------------------------------------------------------------
    {
        "slug": "zoeken-en-lezen",
        "titel": "Zoeken en lezen",
        "doelgroep": M,
        "tekst": """
<p>Typ in de zoekbalk bovenaan wat je zoekt. Een paar woorden is genoeg; een hele vraag mag ook.</p>
<ul>
<li>Een typfout is niet erg. Boven de resultaten staat dan waarop is gezocht.</li>
<li>Vind je te veel, kies dan links een <strong>Cluster</strong>, <strong>Soort</strong> of <strong>Onderwerp</strong>.</li>
<li>Een lange lijst toont vijftig artikelen. Met <strong>Meer laden</strong> komen de volgende erbij.</li>
<li>Onder <strong>Recent bezocht</strong> staan de artikelen die je het laatst hebt geopend.</li>
</ul>
<p>Een artikel bestaat uit secties die je open- en dichtklapt. Onderaan staat de vraag
<strong>Was dit artikel nuttig?</strong> Je antwoord helpt procesmanagement; er wordt niet bijgehouden wie het gaf.</p>
<p>Vind je niets? Vraag het dan aan de assistent, of meld het bij procesmanagement: dan kan het artikel erbij komen.</p>
""",
    },
    {
        "slug": "favorieten-en-wijzigingen",
        "titel": "Favorieten en gewijzigde artikelen",
        "doelgroep": M,
        "tekst": """
<p>Klik op de ster bij een artikel om het te bewaren. Je vindt het terug onder <strong>Favorieten</strong>.</p>
<p>Wordt een artikel inhoudelijk gewijzigd, dan staat het onder <strong>Gewijzigd</strong>, met wat er is veranderd.
Open het artikel en klik op <strong>Ik snap het</strong>. Daarna staat het er niet meer.</p>
<p>Wil je een e-mail als een van je favorieten wijzigt? Zet dan links onder <strong>Instellingen</strong> het vinkje aan.</p>
""",
    },
    {
        "slug": "verbetervoorstel",
        "titel": "Een verbetervoorstel indienen",
        "doelgroep": M,
        "tekst": """
<p>Klopt er iets niet in een artikel, of mis je iets? Dien dan een verbetervoorstel in.</p>
<ol>
<li>Open het artikel.</li>
<li>Selecteer de tekst waar het om gaat. Of gebruik de link onderaan het artikel als het over het hele artikel gaat.</li>
<li>Schrijf wat er volgens jou anders moet, en verstuur het.</li>
</ol>
<p>Ligt er al een voorstel bij dit artikel, dan zie je dat eerst. Gaat het over hetzelfde, steun dan het bestaande
voorstel in plaats van een nieuw te maken.</p>
<p>Onder <strong>Verbetervoorstellen</strong> volg je wat ermee gebeurt. <strong>Mijn voorstellen</strong> zijn die van
jou; <strong>Alle voorstellen</strong> zijn de open voorstellen van collega's, zonder naam. Je krijgt bericht van
procesmanagement als je voorstel is behandeld.</p>
""",
    },
    {
        "slug": "nieuws",
        "titel": "Nieuws",
        "doelgroep": M,
        "tekst": """
<p>Onder <strong>Nieuws</strong> staan de mededelingen van procesmanagement: nieuwe werkwijzen en belangrijke
wijzigingen. Een getal achter Nieuws betekent dat er berichten zijn die je nog niet hebt gezien.</p>
<p>Ongelezen berichten staan ook bovenaan de eerste pagina, onder "Nieuw sinds je laatste bezoek". Zodra je de
nieuwspagina hebt bekeken, is dat blok weg.</p>
""",
    },
    {
        "slug": "assistent",
        "titel": "De assistent",
        "doelgroep": M,
        "tekst": """
<p>Met de knop <strong>Assistent</strong> rechtsonder stel je een vraag in gewone woorden. De assistent zoekt in de
artikelen die jij mag lezen en zegt uit welk artikel het antwoord komt.</p>
<p>Lees bij twijfel het artikel zelf: dat is de bron, de assistent vat alleen samen. Staat het antwoord niet in de
kennisbank, dan zegt de assistent dat.</p>
""",
    },
    {
        "slug": "onboarding-en-weergave",
        "titel": "Onboarding en donkere weergave",
        "doelgroep": M,
        "tekst": """
<p>Ben je nieuw? Zet bovenaan <strong>Onboarding</strong> aan. In de artikelen verschijnt dan extra uitleg voor nieuwe
collega's. Zet het weer uit als je het niet meer nodig hebt.</p>
<p>Met <strong>Donker</strong> wissel je tussen een lichte en een donkere weergave. De kennisbank onthoudt je keuze op
dit apparaat.</p>
""",
    },
    # --- Reviewer -----------------------------------------------------------------------------------------
    {
        "slug": "concept-reviewen",
        "titel": "Een concept reviewen",
        "doelgroep": V,
        "tekst": """
<p>Als reviewer lees je een concept mee voordat het wordt gepubliceerd. Je krijgt een e-mail als er iets voor je
team ligt.</p>
<ol>
<li>Klik bovenaan op <strong>Review</strong>. Wat bij jou of je team ligt, staat bovenaan.</li>
<li>Open het stuk en klik op <strong>Oppakken</strong>. Tot dat moment kun je alleen lezen.</li>
<li>Selecteer tekst en plaats er een opmerking bij. Met <strong>+ Algemene opmerking</strong> zeg je iets over het
geheel.</li>
</ol>
<p>Wat de redacteur heeft veranderd, staat in groen (nieuw) en rood (weg). Met <strong>Wijzigingen tonen</strong> zet
je dat uit en aan. Met <strong>Bekijk als medewerker</strong> zie je het artikel zoals het straks wordt.</p>
<p>Een opmerking die je hebt geplaatst, kun je in dezelfde ronde nog wijzigen of weghalen.</p>
""",
    },
    {
        "slug": "teruggeven-of-akkoord",
        "titel": "Teruggeven of akkoord",
        "doelgroep": V,
        "tekst": """
<p>Ben je klaar met lezen, klik dan op <strong>Afronden…</strong> en kies:</p>
<ul>
<li><strong>Teruggeven met opmerkingen</strong>: de redacteur krijgt je opmerkingen en past het concept aan. Je moet
minstens één opmerking hebben geplaatst.</li>
<li><strong>Akkoord</strong>: je hebt geen opmerkingen meer. Het akkoord geldt voor precies deze tekst. Wijzigt de
redacteur daarna nog iets, dan vervalt het.</li>
</ul>
<p>Na teruggeven kan de redacteur het concept opnieuw voorleggen. Dat is een nieuwe ronde; je opmerkingen uit de
vorige ronde blijven zichtbaar.</p>
<p>Een review houdt de publicatie nooit tegen: de redacteur beslist.</p>
""",
    },
    # --- Redacteur ----------------------------------------------------------------------------------------
    {
        "slug": "werkplek-en-bakken",
        "titel": "De werkplek en de bakken",
        "doelgroep": R,
        "tekst": """
<p>Klik bovenaan op <strong>Werkplek</strong>. Links staan je bakken, met achter elke bak hoeveel erin ligt.</p>
<ul>
<li><strong>Werkvoorraad</strong>: verbetervoorstellen die nog niemand heeft opgepakt, per cluster.</li>
<li><strong>Procesmanagers</strong>: jouw eigen bak en die van je collega's.</li>
<li><strong>Afgehandeld</strong>: wat klaar is. Hier kun je terugzoeken.</li>
<li><strong>Concepten</strong>, <strong>Review</strong> en <strong>Mijn kladversies</strong>: waar je mee bezig bent.</li>
</ul>
<p>Een voorstel oppakken: vink het aan en kies in de balk bovenaan <strong>Mijzelf</strong>. Het gaat dan uit de
werkvoorraad naar jouw bak. Met <strong>Terug naar de werkvoorraad</strong> leg je het terug.</p>
<p>Bovenaan de kolom staan <strong>Nieuw artikel</strong>, <strong>Nieuw bericht</strong> en
<strong>Artikel uit Word</strong>.</p>
""",
    },
    {
        "slug": "artikel-bewerken",
        "titel": "Een artikel schrijven of bewerken",
        "doelgroep": R,
        "tekst": """
<p>Je bewerkt een artikel zoals medewerkers het zien: titel, samenvatting en daaronder de tekst in secties.</p>
<ul>
<li>Opmaak zit in de werkbalk boven de tekst: koppen, lijsten, een tabel, een sectie, uitleg voor nieuwe collega's.</li>
<li>Soort, clusters, tags en eigenaar staan onder <strong>Eigenschappen</strong>.</li>
<li>Eerdere versies staan onder <strong>Geschiedenis</strong>.</li>
<li>Met <strong>Bekijk als medewerker</strong> controleer je hoe het eruit komt te zien.</li>
</ul>
<p>Klaar of even stoppen? Klik op <strong>Afronden…</strong> en kies <strong>Opslaan als concept</strong>. Medewerkers
zien daar niets van.</p>
<p>Wat je typt, wordt tussendoor bewaard als kladversie. Sluit je het scherm zonder op te slaan, dan vraagt de
kennisbank de volgende keer of je verder wilt gaan. Een kladversie blijft dertig dagen staan.</p>
""",
    },
    {
        "slug": "concept-en-live-versie",
        "titel": "Concept en live versie",
        "doelgroep": R,
        "tekst": """
<p>Van een gepubliceerd artikel bestaan twee versies: de <em>live versie</em> die medewerkers lezen, en het
<em>concept</em> waarin jij werkt. Medewerkers zien je concept pas als je het publiceert.</p>
<p>Staat er een fout in de live versie terwijl je concept nog niet af is? Open het artikel op de site en klik op
<strong>Bewerken</strong>. Kies <strong>De live versie verbeteren</strong>. Je herstelt de fout en publiceert die apart;
je concept blijft staan.</p>
<p>Open je daarna het concept, dan meldt het scherm dat de live versie is bijgewerkt. In het paneel
<strong>Veranderd in de live versie</strong> loop je de wijzigingen langs en neem je ze over in je concept, zodat de
verbetering niet verdwijnt als je later publiceert.</p>
<p>Wil je het concept niet meer? Kies bij Afronden <strong>Concept weggooien</strong>. De live versie verandert niet.</p>
""",
    },
    {
        "slug": "ter-inzage-geven",
        "titel": "Een concept ter inzage geven",
        "doelgroep": R,
        "tekst": """
<p>Werkt jouw omgeving met reviewteams, dan kun je een concept laten meelezen voordat je publiceert.</p>
<ol>
<li>Klik op <strong>Afronden…</strong> en kies <strong>Ter inzage geven</strong>.</li>
<li>Het concept gaat op slot tot het team heeft gereageerd. Met <strong>Terugroepen</strong> haal je het terug.</li>
<li>Geeft het team het terug, dan staan de opmerkingen in de marge naast de tekst.</li>
</ol>
<p>Je ziet steeds één van drie standen: <strong>Bij de redactie</strong> (jij bent aan zet),
<strong>Bij het reviewteam</strong> of <strong>Akkoord</strong>. Een akkoord geldt voor precies die tekst; wijzig je
daarna nog iets, dan vervalt het.</p>
<p>Een review houdt publiceren nooit tegen. Jij beslist.</p>
""",
    },
    {
        "slug": "publiceren",
        "titel": "Publiceren",
        "doelgroep": R,
        "tekst": """
<p>Klik op <strong>Afronden…</strong> en kies <strong>Publiceren</strong>. Het concept wordt de live versie.</p>
<p>De kennisbank vraagt dan: <strong>Moeten medewerkers dit weten?</strong></p>
<ul>
<li><strong>Ja</strong>: je schrijft in een zin wat er is veranderd. Het artikel komt bij medewerkers onder Gewijzigd, en
wie het als favoriet heeft, krijgt een e-mail.</li>
<li><strong>Nee</strong>: voor een taalfout of een kleine aanpassing. Er gaat geen melding uit.</li>
</ul>
<p>Had je verbetervoorstellen meegenomen, dan volgt na het publiceren een scherm om de indieners te bedanken.</p>
""",
    },
    {
        "slug": "voorstellen-behandelen",
        "titel": "Verbetervoorstellen behandelen",
        "doelgroep": R,
        "tekst": """
<p>Open een voorstel vanuit je bak. Je komt in het artikel, met links de lade met de open voorstellen bij dat
artikel. De tekst waar het voorstel over gaat, is blauw gemarkeerd.</p>
<ul>
<li><strong>Meenemen</strong>: je verwerkt het voorstel in het concept. Na het publiceren krijgt de indiener bericht.</li>
<li><strong>Afhandelen</strong>: de tekst is al aangepast in de live versie. Je bedankt de indiener.</li>
<li><strong>Afwijzen</strong>: je neemt het niet over en legt uit waarom.</li>
<li><strong>Ontdubbelen</strong>: het is hetzelfde als een ander voorstel bij dit artikel.</li>
</ul>
<p>In de lade kun je de indiener een bericht sturen en een notitie voor collega's achterlaten. De indiener ziet
alleen het bericht.</p>
<p>Afgehandeld is definitief: een voorstel kan daarna niet meer worden heropend.</p>
""",
    },
    {
        "slug": "nieuwsbericht-plaatsen",
        "titel": "Een nieuwsbericht plaatsen",
        "doelgroep": R,
        "tekst": """
<p>Klik op de werkplek op <strong>Nieuw bericht</strong>. Geef het bericht een titel die zegt wat er nieuw is, en
schrijf de tekst.</p>
<p>Onder <strong>Eigenschappen</strong> kies je de omgeving en de artikelen waar het over gaat. Je kunt het bericht
bovenaan vastpinnen en een datum geven waarna het onder ouder nieuws komt te staan.</p>
<p>Kies bij <strong>Afronden…</strong> voor <strong>Publiceren</strong>. Medewerkers zien het bericht onder Nieuws en,
zolang ze het niet hebben gelezen, bovenaan hun eerste pagina.</p>
""",
    },
    {
        "slug": "synoniemen-en-statistieken",
        "titel": "Synoniemen en statistieken",
        "doelgroep": R,
        "tekst": """
<p>Onder <strong>Gebruiksstatistieken</strong> op de site zie je wat medewerkers lezen en zoeken. Twee lijsten zijn het
bekijken waard:</p>
<ul>
<li><strong>Gezocht zonder resultaat</strong>: hier zochten collega's naar iets dat ze niet vonden. Staat het nog niet
in de kennisbank, dan is dit een artikel om te schrijven.</li>
<li><strong>Gevonden, maar niet geholpen</strong>: zoektermen waarna iemand meteen opnieuw zocht.</li>
</ul>
<p>Staat het er wel, maar onder een ander woord? Klik bij de zoekterm op <strong>Synoniem maken</strong> en vul het
woord in dat wel in de artikelen staat. Wie daarna op die term zoekt, vindt het artikel. De hele lijst staat op de
werkplek onder <strong>Alle onderdelen</strong>, bij Synoniemen.</p>
<p>Bij elk artikel zie je ook hoe vaak lezers het nuttig of niet nuttig vonden.</p>
""",
    },
    # --- Functioneel beheerder ----------------------------------------------------------------------------
    {
        "slug": "omgevingen-en-toegang",
        "titel": "Omgevingen en toegang",
        "doelgroep": B,
        "tekst": """
<p>Een omgeving is een afgeschermd deel van de kennisbank, bijvoorbeeld van een afdeling. Elk artikel hoort bij
één omgeving.</p>
<p>Wie wat mag, regel je per omgeving met groepen. Open onder <strong>Alle onderdelen</strong> de omgeving en voeg
onder toegang een groep toe met een rol: lezer of redacteur. Wie in de groep zit, krijgt die rol. De groepen zelf
komen uit de inlogvoorziening van de organisatie.</p>
<p>Een wijziging werkt meteen; niemand hoeft opnieuw in te loggen.</p>
""",
    },
    {
        "slug": "reviewteams",
        "titel": "Reviewteams",
        "doelgroep": B,
        "tekst": """
<p>Een reviewteam is een groep collega's die concepten meeleest. Maak het team aan onder
<strong>Alle onderdelen</strong>, koppel het aan een omgeving en kies de groep waarvan de leden reviewer zijn.</p>
<p>Zet daarna bij de omgeving <strong>reviewproces gebruiken</strong> aan. Redacteuren krijgen dan de keuze om een
concept ter inzage te geven. Staat het uit, dan werkt alles zoals zonder review.</p>
<p>Reviewers hoeven geen lezer van de omgeving te zijn: ze zien alleen de stukken die aan hun team zijn voorgelegd.</p>
""",
    },
    {
        "slug": "statuspagina-en-dagelijkse-taak",
        "titel": "De statuspagina en de dagelijkse taak",
        "doelgroep": B,
        "tekst": """
<p>Als je het beheer opent, staat bovenaan in een regel wat de statuspagina zegt. Met
<strong>Naar de statuspagina</strong> zie je per onderdeel of het loopt en wat je kunt doen als dat niet zo is:
de database, e-mail, de assistent en de dagelijkse taak.</p>
<p>De dagelijkse taak ruimt op en verstuurt de samenvattingen per e-mail aan redacteuren en reviewers. Loopt die
niet, dan krijgt niemand bericht over nieuwe voorstellen en reviews. De statuspagina waarschuwt daarvoor; het
herstellen is werk voor de technisch beheerder.</p>
""",
    },
    {
        "slug": "hulp-aanpassen",
        "titel": "Deze hulp aanpassen",
        "doelgroep": B,
        "tekst": """
<p>De hulpartikelen staan onder <strong>Alle onderdelen</strong>, bij Hulpartikelen. Je kunt een artikel aanpassen,
verbergen of er een toevoegen, en kiezen voor wie het is.</p>
<p>Een artikel dat je hebt aangepast, laat een nieuwe versie van de kennisbank met rust. Wil je de meegeleverde
tekst terug, vink het artikel dan aan in de lijst en kies <strong>Standaardtekst terugzetten</strong>.</p>
<p>Hoe jullie afdeling met de kennisbank werkt, hoort niet hier maar in een eigen artikel. Wijs dat bij de omgeving
aan als <strong>artikel met eigen werkafspraken</strong>; de hulppagina linkt er dan naar.</p>
""",
    },
]

for _nummer, _artikel in enumerate(STANDAARD, start=1):
    _artikel["volgorde"] = _nummer * 10
    _artikel["tekst"] = _artikel["tekst"].strip()
