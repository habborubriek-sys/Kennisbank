# ruff: noqa: E501 - de teksten zijn HTML; een regel afbreken midden in een zin maakt ze niet leesbaarder
"""De standaardset hulpartikelen die het pakket meelevert (1.36.0; herschreven in 1.37.0).

Uitgangspunt (Alex, 17 november 2026): wie alle artikelen van zijn rol heeft gelezen, begrijpt de functies van de
kennisbank. Dus per artikel de context (waar dient dit voor, wat gebeurt er daarna), duidelijke stappen, en beeld:
een schermafbeelding (`[[beeld:naam|bijschrift]]`) of, als het artikel deel is van een proces, een schema
(`[[schema:naam]]`). Zie `hulp.verrijk`.

Afspraken voor wie hier iets aan verandert:
- Aanspreekvorm "je", zakelijk van toon.
- Een knop, menu, bak of veld staat vet en heet precies zoals op het scherm. De test `test_hulp_1360.Woorden`
  bewaakt dat, zodat de hulp niet stil veroudert.
- De schermafbeeldingen maak je opnieuw met `scripts/browsertests/hulpbeelden.sh`; een test bewaakt dat elk
  genoemd beeld bestaat en elk bestaand beeld wordt gebruikt.
- Wat de functioneel beheerder zelf heeft aangepast (`Hulpartikel.aangepast`) blijft bij een upgrade met rust.

Dit is uitleg over de kennisbank zelf. Hoe een afdeling ermee werkt (wie reviewt wat, binnen welke termijn) hoort
in een eigen artikel van die afdeling; zie `Omgeving.werkafspraken_artikel`.
"""

M, V, R, B = "medewerker", "reviewer", "redacteur", "beheerder"

# --- Schema's: een proces in stappen, met per stap wie hem zet -------------------------------------------------------

SCHEMAS = {
    "rollen": {
        "titel": "Wie doet wat in de kennisbank",
        "stappen": [
            ("Medewerker", "Lezen en melden", "Zoekt en leest artikelen, en dient een verbetervoorstel in als iets niet klopt."),
            ("Reviewer", "Meelezen", "Beoordeelt een concept inhoudelijk voordat het wordt gepubliceerd."),
            ("Redacteur", "Schrijven en publiceren", "Schrijft en wijzigt artikelen, behandelt verbetervoorstellen en plaatst nieuws."),
            ("Functioneel beheerder", "Inrichten", "Regelt omgevingen, toegang en reviewteams, en bewaakt of alles loopt."),
        ],
        "noot": "Elke rol kan ook wat de rol ervoor kan. Een redacteur leest en zoekt dus net als een medewerker.",
    },
    "verbetervoorstel": {
        "titel": "Van verbetervoorstel tot aangepast artikel",
        "stappen": [
            ("Medewerker", "Voorstel indienen", "Bij het artikel, met de tekst waar het om gaat."),
            ("Kennisbank", "Werkvoorraad", "Het voorstel wacht tot een redacteur het oppakt."),
            ("Redacteur", "Behandelen", "Meenemen in een concept, afhandelen of afwijzen."),
            ("Redacteur", "Publiceren", "De aangepaste tekst wordt de live versie."),
            ("Medewerker", "Bericht", "De indiener krijgt bericht over de uitkomst."),
        ],
        "noot": "Bij afwijzen of ontdubbelen vervalt de stap Publiceren; de indiener krijgt dan meteen bericht.",
    },
    "concept-tot-publicatie": {
        "titel": "Van concept tot gepubliceerd artikel",
        "stappen": [
            ("Redacteur", "Concept schrijven", "Medewerkers zien hier niets van."),
            ("Redacteur", "Ter inzage geven", "Alleen in een omgeving die met reviewteams werkt."),
            ("Reviewteam", "Reviewen", "Teruggeven met opmerkingen, of akkoord."),
            ("Redacteur", "Publiceren", "Het concept wordt de live versie."),
            ("Medewerker", "Lezen", "Na een melding staat het artikel onder Gewijzigd."),
        ],
        "noot": "Geeft het reviewteam het concept terug, dan begint het weer bij de eerste stap. Een review houdt publiceren nooit tegen: de redacteur beslist.",
    },
    "live-en-concept": {
        "titel": "Een fout in de live versie herstellen terwijl je concept nog niet af is",
        "stappen": [
            ("Redacteur", "Concept loopt", "Je werkt aan een grotere wijziging die nog niet klaar is."),
            ("Redacteur", "Live versie verbeteren", "Via Bewerken op de site. Je herstelt alleen de fout."),
            ("Redacteur", "Apart publiceren", "Medewerkers zien de verbetering meteen."),
            ("Redacteur", "Overnemen in het concept", "Het concept laat zien wat er live is veranderd."),
            ("Redacteur", "Concept publiceren", "De verbetering blijft behouden."),
        ],
        "noot": "Sla je het overnemen over, dan zet het publiceren van het concept de fout terug. De kennisbank waarschuwt daarvoor.",
    },
}

# --- De artikelen ----------------------------------------------------------------------------------------------------

STANDAARD = [
    # --- Medewerker ---------------------------------------------------------------------------------------
    {
        "slug": "kennisbank-in-het-kort",
        "titel": "De kennisbank in het kort",
        "doelgroep": M,
        "tekst": """
<p>De kennisbank is de plek waar de werkinstructies, werkafspraken en procesbeschrijvingen van de afdeling staan. Elk artikel heeft één geldende versie. Wat je hier leest, is dus de afspraak zoals die nu geldt.</p>
<h3>Wat je er kunt doen</h3>
<ul>
<li>Een artikel zoeken en lezen.</li>
<li>Bijhouden wat er is gewijzigd in de artikelen die voor jou van belang zijn.</li>
<li>Een verbetervoorstel indienen als een artikel onjuist, verouderd of onduidelijk is.</li>
<li>Het nieuws van procesmanagement volgen.</li>
<li>Een vraag stellen aan de assistent.</li>
</ul>
<p>[[beeld:site-start|De eerste pagina: bovenaan de zoekbalk, links het menu]]</p>
<h3>Hoe het scherm is opgebouwd</h3>
<ul>
<li>Bovenaan staat de zoekbalk, met daarnaast de knoppen voor de weergave en voor <strong>Hulp</strong>.</li>
<li>Links staat het menu: <strong>Recent bezocht</strong>, <strong>Favorieten</strong>, <strong>Gewijzigd</strong>, <strong>Nieuws</strong>, <strong>Alle artikelen</strong> en <strong>Verbetervoorstellen</strong>. Daaronder kun je de lijst beperken met <strong>Cluster</strong>, <strong>Soort</strong> en <strong>Onderwerp</strong>.</li>
<li>Rechtsonder staat de knop <strong>Assistent</strong>.</li>
</ul>
<h3>Wie doet wat</h3>
<p>[[schema:rollen]]</p>
<p>Je ziet alleen de artikelen van de omgevingen waar je toegang toe hebt. Mis je een omgeving, vraag dat dan na bij de functioneel beheerder.</p>
""",
    },
    {
        "slug": "zoeken-en-lezen",
        "titel": "Zoeken en lezen",
        "doelgroep": M,
        "tekst": """
<p>De snelste weg naar een artikel is de zoekbalk. De kennisbank zoekt in de titel, de samenvatting, de onderwerpen en de volledige tekst van alle artikelen die je mag lezen.</p>
<h3>Zoeken</h3>
<ol>
<li>Klik in de zoekbalk bovenaan.</li>
<li>Typ wat je zoekt. Enkele woorden volstaan; een hele vraag mag ook.</li>
<li>De resultaten verschijnen tijdens het typen. Het best passende artikel staat bovenaan.</li>
<li>Klik op een artikel om het te openen.</li>
</ol>
<p>[[beeld:zoeken|Zoeken met een typfout: de regel boven de resultaten zegt waarop is gezocht]]</p>
<h3>Als je niet precies het goede woord typt</h3>
<p>De kennisbank helpt mee, en zegt in een regel boven de resultaten wat er is gedaan:</p>
<ul>
<li>Bij een typfout wordt gezocht op het woord dat erop lijkt.</li>
<li>Bij een ander woord voor hetzelfde vind je ook de artikelen met het gebruikelijke woord. Procesmanagement houdt daarvoor een lijst met synoniemen bij.</li>
<li>Bevat geen artikel alle woorden, dan krijg je de artikelen die het dichtst in de buurt komen.</li>
</ul>
<h3>De lijst beperken</h3>
<p>Vind je te veel, kies dan in het menu links een <strong>Cluster</strong>, een <strong>Soort</strong> of een <strong>Onderwerp</strong>. Een lange lijst toont vijftig artikelen; met <strong>Meer laden</strong> komen de volgende erbij.</p>
<h3>Een artikel lezen</h3>
<p>[[beeld:artikel|Een artikel: de samenvatting bovenaan, daaronder de secties]]</p>
<ul>
<li>Bovenaan staan de titel, de soort, de versie en de datum van de laatste wijziging.</li>
<li>De tekst is verdeeld in secties. Klik op de kop van een sectie om die open of dicht te klappen.</li>
<li>Onderaan staat de vraag <strong>Was dit artikel nuttig?</strong> Je antwoord helpt procesmanagement om artikelen te verbeteren. Er wordt alleen een aantal geteld, niet wie het antwoord gaf.</li>
</ul>
<blockquote><p><strong>Niets gevonden?</strong> Dan staat het mogelijk nog niet in de kennisbank. Stel de vraag aan de assistent of meld het bij procesmanagement. Zoekopdrachten zonder resultaat worden anoniem geteld, zodat procesmanagement ziet welke kennis ontbreekt.</p></blockquote>
""",
    },
    {
        "slug": "favorieten-en-wijzigingen",
        "titel": "Favorieten en gewijzigde artikelen",
        "doelgroep": M,
        "tekst": """
<p>Een werkinstructie kan veranderen. De kennisbank houdt voor je bij welke artikelen inhoudelijk zijn gewijzigd sinds je ze voor het laatst hebt gezien, zodat je niet met een oude werkwijze doorwerkt.</p>
<h3>Een artikel als favoriet bewaren</h3>
<ol>
<li>Open het artikel.</li>
<li>Klik boven de titel op <strong>Favoriet</strong>. In een lijst met artikelen kan het ook: klik daar op de ster rechts van de titel.</li>
<li>Het artikel staat nu onder <strong>Favorieten</strong> in het menu links.</li>
</ol>
<p>Nog een klik haalt het artikel weer uit je favorieten.</p>
<h3>Gewijzigde artikelen nalopen</h3>
<p>[[beeld:gewijzigd|Onder Gewijzigd staat per artikel wat er is veranderd]]</p>
<ol>
<li>Klik in het menu op <strong>Gewijzigd</strong>. Het getal erachter is het aantal artikelen dat je nog niet hebt nagelopen.</li>
<li>Lees per artikel de toelichting: daarin staat in een zin wat er is veranderd.</li>
<li>Open het artikel en lees de wijziging.</li>
<li>Klik op <strong>Ik snap het</strong>. Het artikel verdwijnt uit de lijst.</li>
</ol>
<p>Heb je alles al gelezen, dan kun je bovenaan de pagina alle artikelen in een keer als gezien markeren.</p>
<h3>Een e-mail bij een wijziging</h3>
<p>Wil je een e-mail ontvangen als een van je favorieten wijzigt, zet dan onder <strong>Instellingen</strong> in het menu links het vinkje aan.</p>
<blockquote><p><strong>Let op.</strong> Niet elke wijziging komt in deze lijst. Bij een taalfout of een kleine aanpassing kan de redacteur ervoor kiezen geen melding te geven. De inhoud van de afspraak is dan niet veranderd.</p></blockquote>
""",
    },
    {
        "slug": "verbetervoorstel",
        "titel": "Een verbetervoorstel indienen",
        "doelgroep": M,
        "tekst": """
<p>De kennisbank blijft alleen kloppen als gebruikers melden wat niet klopt. Zie je een fout, een verouderde afspraak of een onduidelijke passage, dien dan een verbetervoorstel in. Procesmanagement beoordeelt elk voorstel en laat je weten wat ermee is gedaan.</p>
<p>[[schema:verbetervoorstel]]</p>
<h3>Een voorstel indienen</h3>
<ol>
<li>Open het artikel waar het om gaat.</li>
<li>Selecteer met de muis de tekst die volgens jou niet klopt. Er verschijnt een knop om een voorstel te doen. Gaat je voorstel over het hele artikel, gebruik dan de link onderaan het artikel.</li>
<li>Beschrijf wat er onjuist, verouderd of onduidelijk is, en wat het volgens jou zou moeten zijn.</li>
<li>Klik op <strong>Indienen</strong>.</li>
</ol>
<p>[[beeld:voorstel-indienen|Het venster Verbetervoorstel indienen, met de geselecteerde tekst erboven]]</p>
<h3>Als er al een voorstel ligt</h3>
<p>Ligt er bij dit artikel al een open voorstel, dan zie je dat voordat je het jouwe verstuurt. Gaat het over hetzelfde, steun dan het bestaande voorstel. Een voorstel met veel steun laat procesmanagement zien dat meer collega's ertegenaan lopen, en je voorkomt dubbel werk.</p>
<h3>Je voorstel volgen</h3>
<p>[[beeld:voorstellen|Onder Verbetervoorstellen zie je de stand van elk voorstel]]</p>
<ol>
<li>Klik in het menu op <strong>Verbetervoorstellen</strong>.</li>
<li>Onder <strong>Mijn voorstellen</strong> staan de voorstellen die je zelf hebt ingediend, met de berichten van procesmanagement erbij. Je kunt kiezen tussen <strong>Nog open</strong>, <strong>Verwerkt</strong> en <strong>Afgewezen</strong>.</li>
<li>Onder <strong>Alle voorstellen</strong> staan de open voorstellen van collega's, zonder naam van de indiener. Hier kun je een voorstel steunen.</li>
</ol>
<blockquote><p><strong>Wat je kunt verwachten.</strong> Je krijgt bericht van procesmanagement zodra je voorstel is behandeld. Is het overgenomen, dan staat erbij in welke versie van het artikel. Is het afgewezen, dan staat erbij waarom.</p></blockquote>
""",
    },
    {
        "slug": "nieuws",
        "titel": "Nieuws",
        "doelgroep": M,
        "tekst": """
<p>Onder <strong>Nieuws</strong> plaatst procesmanagement mededelingen: een nieuwe werkwijze, een belangrijke wijziging of een aankondiging. Een nieuwsbericht verwijst vaak naar de artikelen waar het over gaat.</p>
<p>[[beeld:nieuws|De nieuwspagina, met de nieuwste berichten bovenaan]]</p>
<h3>Nieuws lezen</h3>
<ol>
<li>Klik in het menu op <strong>Nieuws</strong>. Het getal erachter is het aantal berichten dat je nog niet hebt gezien.</li>
<li>Lees de berichten. Een bericht dat is vastgepind, staat bovenaan.</li>
<li>Klik op een genoemd artikel om het te openen.</li>
</ol>
<h3>Ongelezen nieuws op de eerste pagina</h3>
<p>Berichten die je nog niet hebt gezien, staan ook bovenaan de eerste pagina, onder de kop "Nieuw sinds je laatste bezoek". Zodra je de nieuwspagina hebt bekeken, verdwijnt dat blok. Het komt terug als er een nieuw bericht is.</p>
<p>Oudere berichten vind je onderaan de nieuwspagina.</p>
""",
    },
    {
        "slug": "assistent",
        "titel": "De assistent",
        "doelgroep": M,
        "tekst": """
<p>De assistent beantwoordt een vraag in gewone woorden op basis van de artikelen in de kennisbank. Hij is bedoeld voor het geval je niet weet in welk artikel het antwoord staat.</p>
<h3>Een vraag stellen</h3>
<ol>
<li>Klik rechtsonder op <strong>Assistent</strong>.</li>
<li>Typ je vraag, bijvoorbeeld: "Binnen welke termijn verstuur ik een rappel?"</li>
<li>Lees het antwoord. Onder het antwoord staat uit welk artikel het komt.</li>
<li>Klik op het artikel om de volledige tekst te lezen.</li>
</ol>
<p>[[beeld:assistent|De assistent, met het antwoord en het artikel waar het uit komt]]</p>
<h3>Wat de assistent wel en niet doet</h3>
<ul>
<li>De assistent gebruikt alleen artikelen die jij mag lezen.</li>
<li>Staat het antwoord niet in de kennisbank, dan zegt de assistent dat. Hij vult niets aan uit andere bronnen.</li>
<li>De assistent onthoudt geen eerdere gesprekken.</li>
</ul>
<blockquote><p><strong>Let op.</strong> Het artikel is de bron; de assistent vat samen. Neem je een besluit op basis van het antwoord, lees dan het artikel zelf.</p></blockquote>
""",
    },
    {
        "slug": "onboarding-en-weergave",
        "titel": "Onboarding en donkere weergave",
        "doelgroep": M,
        "tekst": """
<p>Bovenaan de site staan twee knoppen waarmee je instelt hoe de kennisbank eruitziet. Ze veranderen niets aan de inhoud.</p>
<h3>Onboarding: extra uitleg voor nieuwe collega's</h3>
<p>Redacteuren kunnen in een artikel uitleg opnemen die alleen voor nieuwe collega's bedoeld is: achtergrond, begrippen, waarom iets zo gaat. Die uitleg staat standaard uit, zodat ervaren collega's een korter artikel zien.</p>
<ol>
<li>Zet bovenaan <strong>Onboarding</strong> aan.</li>
<li>Open een artikel. De extra uitleg staat in een geel blok tussen de tekst.</li>
<li>Zet Onboarding uit zodra je de uitleg niet meer nodig hebt.</li>
</ol>
<p>[[beeld:onboarding|Een artikel met Onboarding aan: de extra uitleg staat in een geel blok]]</p>
<p>Bij je eerste bezoek vraagt de kennisbank of je nieuw bent. Kies je ja, dan staat Onboarding meteen aan.</p>
<h3>Licht of donker</h3>
<p>Met <strong>Donker</strong> wissel je tussen een lichte en een donkere weergave. De kennisbank volgt eerst de instelling van je apparaat en onthoudt daarna je eigen keuze, per apparaat.</p>
""",
    },
    # --- Reviewer -----------------------------------------------------------------------------------------
    {
        "slug": "concept-reviewen",
        "titel": "Een concept reviewen",
        "doelgroep": V,
        "tekst": """
<p>Als lid van een reviewteam beoordeel je een concept inhoudelijk voordat het wordt gepubliceerd. De redacteur vraagt daarom; jij bepaalt of de tekst klopt. De review is een advies: de redacteur beslist over de publicatie.</p>
<p>[[schema:concept-tot-publicatie]]</p>
<h3>Waar je je werk vindt</h3>
<ol>
<li>Je krijgt een e-mail als er een concept voor je team ligt.</li>
<li>Klik bovenaan op <strong>Review</strong>.</li>
<li>Bovenaan de lijst staat wat bij jou of bij je team ligt. Daaronder staat wat al is afgerond.</li>
</ol>
<p>[[beeld:review-lijst|De reviewpagina: bovenaan wat op jou wacht]]</p>
<h3>Het concept beoordelen</h3>
<ol>
<li>Open het stuk. Je kunt het eerst rustig lezen.</li>
<li>Klik op <strong>Oppakken</strong>. Daarmee laat je je team zien dat jij dit stuk beoordeelt. Vanaf dat moment kun je opmerkingen plaatsen.</li>
<li>Selecteer de tekst waar je iets over wilt zeggen, en plaats er een opmerking bij.</li>
<li>Wil je iets zeggen over het stuk als geheel, klik dan op <strong>+ Algemene opmerking</strong>.</li>
</ol>
<p>[[beeld:review-stuk|Een concept ter review: de wijzigingen in groen en rood, de opmerkingen in de marge]]</p>
<h3>Wat je op het scherm ziet</h3>
<ul>
<li>Groen is tekst die de redacteur heeft toegevoegd, rood is tekst die is weggehaald. Met <strong>Wijzigingen tonen</strong> zet je dat uit en aan.</li>
<li>Paars gemarkeerd is tekst waar een opmerking bij staat. De opmerking zelf staat in de marge.</li>
<li>Blauw gemarkeerd is tekst waar een verbetervoorstel van een collega over ging. Zo zie je waarom de redacteur iets heeft aangepast.</li>
<li>Met <strong>Bekijk als medewerker</strong> zie je het artikel zoals het er na publicatie uitziet.</li>
</ul>
<blockquote><p><strong>Goed om te weten.</strong> Een opmerking die je hebt geplaatst, kun je in dezelfde ronde nog wijzigen of weghalen. De redacteur ziet je opmerkingen pas als je het stuk teruggeeft.</p></blockquote>
""",
    },
    {
        "slug": "teruggeven-of-akkoord",
        "titel": "Teruggeven of akkoord",
        "doelgroep": V,
        "tekst": """
<p>Een review eindigt altijd met een uitspraak: je geeft het concept terug met opmerkingen, of je geeft je akkoord. Pas dan weet de redacteur waar hij aan toe is.</p>
<h3>De review afronden</h3>
<ol>
<li>Controleer of al je opmerkingen zijn geplaatst.</li>
<li>Klik op <strong>Afronden…</strong>.</li>
<li>Kies een van de twee mogelijkheden en bevestig.</li>
</ol>
<p>[[beeld:review-afronden|Het venster waarin je de review afrondt]]</p>
<h3>De twee mogelijkheden</h3>
<table>
<thead><tr><th>Keuze</th><th>Wanneer</th><th>Wat er gebeurt</th></tr></thead>
<tbody>
<tr><td><strong>Teruggeven met opmerkingen</strong></td><td>Er moet nog iets worden aangepast. Je hebt minstens één opmerking geplaatst.</td><td>De redacteur krijgt bericht en ziet je opmerkingen naast de tekst. Het concept is weer te bewerken.</td></tr>
<tr><td><strong>Akkoord</strong></td><td>Je hebt geen opmerkingen meer.</td><td>De redacteur krijgt bericht. In de geschiedenis van het artikel staat dat je team akkoord was.</td></tr>
</tbody>
</table>
<h3>Een nieuwe ronde</h3>
<p>Na teruggeven kan de redacteur het aangepaste concept opnieuw voorleggen. Dat is een nieuwe ronde. Je opmerkingen uit de vorige ronde blijven zichtbaar, zodat je kunt nagaan wat ermee is gedaan.</p>
<blockquote><p><strong>Let op.</strong> Een akkoord geldt voor precies de tekst die je hebt beoordeeld. Wijzigt de redacteur daarna nog iets, dan vervalt het akkoord. En een review houdt de publicatie nooit tegen: de redacteur kan publiceren zonder akkoord, en dat is dan in de geschiedenis te zien.</p></blockquote>
""",
    },
    # --- Redacteur ----------------------------------------------------------------------------------------
    {
        "slug": "werkplek-en-bakken",
        "titel": "De werkplek en de bakken",
        "doelgroep": R,
        "tekst": """
<p>De werkplek is het beginpunt van al het redactiewerk. Je ziet er in een oogopslag wat er op je wacht: verbetervoorstellen van medewerkers, concepten waar je aan werkt en stukken die bij een reviewteam liggen.</p>
<p>[[beeld:werkplek|De werkplek: links de bakken, rechts de inhoud van de gekozen bak]]</p>
<h3>De werkplek openen</h3>
<p>Klik bovenaan op <strong>Werkplek</strong>. Links staan de bakken, met achter elke bak het aantal stukken. Klik op een bak om de inhoud te zien.</p>
<h3>De bakken</h3>
<table>
<thead><tr><th>Bak</th><th>Wat erin ligt</th></tr></thead>
<tbody>
<tr><td><strong>Werkvoorraad</strong></td><td>Verbetervoorstellen die nog niemand heeft opgepakt, verdeeld per cluster. Dit is gezamenlijk werk.</td></tr>
<tr><td><strong>Procesmanagers</strong></td><td>Je eigen bak en de bakken van je collega's. Zo zie je wie waarmee bezig is.</td></tr>
<tr><td><strong>Afgehandeld</strong></td><td>Voorstellen die zijn verwerkt, afgewezen of vervallen. Hier kun je terugzoeken.</td></tr>
<tr><td><strong>Concepten</strong></td><td>Artikelen waarvan een concept openstaat.</td></tr>
<tr><td><strong>Review</strong></td><td>Concepten die ter inzage liggen of zijn teruggegeven, met de stand erbij.</td></tr>
<tr><td><strong>Mijn kladversies</strong></td><td>Werk dat je niet hebt opgeslagen. Een kladversie vervalt na dertig dagen.</td></tr>
<tr><td><strong>Opnieuw nakijken</strong></td><td>Artikelen waarvan de datum voor herziening is verstreken.</td></tr>
<tr><td><strong>Alle onderdelen</strong></td><td>De lijsten erachter: alle artikelen, nieuwsberichten, synoniemen en sjablonen.</td></tr>
</tbody>
</table>
<h3>Een verbetervoorstel oppakken</h3>
<ol>
<li>Open een bak onder <strong>Werkvoorraad</strong>.</li>
<li>Vink het voorstel aan. Je kunt er meer tegelijk aanvinken.</li>
<li>Kies in de balk boven de lijst bij <strong>Toewijzen aan…</strong> voor <strong>Mijzelf</strong>, of voor een collega.</li>
<li>Klik op <strong>Toewijzen</strong>. Het voorstel gaat uit de werkvoorraad naar de gekozen bak.</li>
</ol>
<p>Kun je het toch niet behandelen, vink het dan aan in je eigen bak, kies <strong>Terug naar de werkvoorraad</strong> en klik op Toewijzen. Hoort een voorstel bij een ander cluster, kies dan bij <strong>Naar bak…</strong> de juiste bak en klik op <strong>Verplaatsen</strong>.</p>
<p>Met <strong>Verbergen voor collega's</strong> haal je een voorstel dat niet voor iedereen bedoeld is uit de lijst die medewerkers zien. Met <strong>Weer tonen</strong> maak je dat ongedaan.</p>
<h3>Iets nieuws beginnen</h3>
<p>Bovenaan de kolom staan <strong>Nieuw artikel</strong>, <strong>Nieuw bericht</strong> (een nieuwsbericht) en <strong>Artikel uit Word</strong> (een bestaand document inlezen).</p>
<blockquote><p><strong>Goed om te weten.</strong> Ligt een voorstel te lang in een bak, dan klapt die bak bij je collega's vanzelf open. Elke dag krijg je per e-mail een samenvatting van wat er nieuw is.</p></blockquote>
""",
    },
    {
        "slug": "artikel-bewerken",
        "titel": "Een artikel schrijven of bewerken",
        "doelgroep": R,
        "tekst": """
<p>Je schrijft en bewerkt een artikel in een scherm dat eruitziet zoals medewerkers het artikel straks lezen. Zolang je niet publiceert, verandert er voor medewerkers niets.</p>
<p>[[beeld:bewerkscherm|Het bewerkscherm: de balk met knoppen, de werkbalk voor opmaak en het artikel]]</p>
<h3>Een artikel openen</h3>
<ul>
<li>Een nieuw artikel: klik op de werkplek op <strong>Nieuw artikel</strong>.</li>
<li>Een bestaand artikel: open het op de site en klik op <strong>Bewerken</strong>, of open het vanuit een bak op de werkplek.</li>
</ul>
<h3>De opbouw van een artikel</h3>
<ol>
<li>De titel zegt wat de lezer wil doen of weten.</li>
<li>De samenvatting is een of twee zinnen. Deze staat in de zoekresultaten.</li>
<li>De tekst is verdeeld in secties. Elke sectie heeft een kop en is voor de lezer in en uit te klappen. Gebruik de werkbalk boven de tekst voor koppen, lijsten, een tabel of een nieuwe sectie.</li>
<li>Uitleg voor nieuwe collega's is een blok dat alleen zichtbaar is voor wie Onboarding heeft aangezet.</li>
</ol>
<h3>De knoppen in de balk</h3>
<table>
<thead><tr><th>Knop</th><th>Waarvoor</th></tr></thead>
<tbody>
<tr><td><strong>Eigenschappen</strong></td><td>Soort, clusters, tags, eigenaar en de datum waarop het artikel opnieuw moet worden nagekeken.</td></tr>
<tr><td><strong>Geschiedenis</strong></td><td>Eerdere versies, met wie wat heeft gewijzigd en waarom.</td></tr>
<tr><td><strong>Bekijk als medewerker</strong></td><td>Controleren hoe het artikel eruit komt te zien.</td></tr>
<tr><td><strong>Afronden…</strong></td><td>Opslaan, ter inzage geven of publiceren.</td></tr>
</tbody>
</table>
<h3>Je werk bewaren</h3>
<ol>
<li>Klik op <strong>Afronden…</strong>.</li>
<li>Kies <strong>Opslaan als concept</strong>.</li>
</ol>
<p>[[beeld:afronden|Het venster Afronden, met de keuzes]]</p>
<p>Met <strong>Afbreken</strong> sluit je het scherm zonder op te slaan.</p>
<p>Het concept blijft staan tot je het publiceert of weggooit. Je vindt het terug in de bak <strong>Concepten</strong>.</p>
<blockquote><p><strong>Als je het scherm sluit zonder op te slaan.</strong> Wat je typt, wordt tussendoor bewaard als kladversie. De volgende keer vraagt de kennisbank of je daarmee verder wilt. Een kladversie is alleen van jou en vervalt na dertig dagen; een concept is van de redactie en vervalt niet.</p></blockquote>
""",
    },
    {
        "slug": "concept-en-live-versie",
        "titel": "Concept en live versie",
        "doelgroep": R,
        "tekst": """
<p>Van een gepubliceerd artikel bestaan twee versies naast elkaar. De <em>live versie</em> is wat medewerkers lezen. Het <em>concept</em> is de versie waarin jij werkt. Medewerkers zien het concept pas als je het publiceert. Zo kun je aan een grotere wijziging werken zonder dat er een halve tekst in de kennisbank staat.</p>
<h3>Een fout in de live versie, terwijl je concept nog niet af is</h3>
<p>Dit is de situatie waarin het onderscheid ertoe doet. Je werkt aan een herziening, en ondertussen blijkt er een fout in de geldende tekst te staan die niet kan wachten.</p>
<p>[[schema:live-en-concept]]</p>
<ol>
<li>Open het artikel op de site en klik op <strong>Bewerken</strong>.</li>
<li>De kennisbank vraagt wat je wilt doen. Kies <strong>De live versie verbeteren</strong>. De andere keuze, <strong>Verder met het concept</strong>, opent het concept waar je aan werkte.</li>
<li>Herstel de fout, en alleen de fout.</li>
<li>Publiceer via <strong>Afronden…</strong>. Medewerkers zien de verbetering meteen. Je concept is niet aangeraakt.</li>
</ol>
<p>[[beeld:live-keuze|Bij Bewerken op de site kies je wat je wilt aanpassen]]</p>
<h3>De verbetering overnemen in je concept</h3>
<p>Je concept is gemaakt van de oude tekst en bevat de verbetering dus nog niet. Open je het concept, dan meldt het scherm dat de live versie is bijgewerkt.</p>
<ol>
<li>Open het paneel <strong>Veranderd in de live versie</strong>.</li>
<li>Het paneel toont de wijzigingen een voor een, in rood en groen.</li>
<li>Neem een wijziging over, of pas de alinea zelf aan als je die in je concept al had herschreven.</li>
<li>Sla het concept op. Je keuzes worden dan bewaard, ook voor collega's.</li>
</ol>
<p>[[beeld:live-paneel|Het paneel Veranderd in de live versie, naast het concept]]</p>
<h3>Een concept weggooien</h3>
<p>Wil je het concept niet meer, klik dan op <strong>Afronden…</strong> en kies <strong>Concept weggooien</strong>. De live versie verandert daardoor niet.</p>
<blockquote><p><strong>Let op.</strong> De vergelijking kijkt naar tekst, niet naar opmaak. Publiceer je het concept zonder de wijzigingen over te nemen, dan komt de oude fout terug. De kennisbank waarschuwt daarvoor bij het afronden.</p></blockquote>
""",
    },
    {
        "slug": "ter-inzage-geven",
        "titel": "Een concept ter inzage geven",
        "doelgroep": R,
        "tekst": """
<p>In een omgeving die met reviewteams werkt, kun je een concept inhoudelijk laten beoordelen voordat je het publiceert. Dat heet ter inzage geven. Het team leest mee en geeft het terug met opmerkingen of geeft akkoord.</p>
<p>[[schema:concept-tot-publicatie]]</p>
<h3>Ter inzage geven</h3>
<ol>
<li>Zorg dat het concept inhoudelijk af is.</li>
<li>Klik op <strong>Afronden…</strong> en kies <strong>Ter inzage geven</strong>.</li>
<li>Kies het reviewteam en bevestig. Het team krijgt een e-mail.</li>
</ol>
<p>Het concept gaat op slot: zolang het bij het team ligt, kan niemand de tekst wijzigen. Zo beoordeelt het team precies de tekst die jij hebt voorgelegd.</p>
<h3>De stand volgen</h3>
<p>In het bewerkscherm en in de bak <strong>Review</strong> staat steeds een van drie standen, met in de regel erachter wat er speelt.</p>
<table>
<thead><tr><th>Stand</th><th>Betekenis</th><th>Wie is aan zet</th></tr></thead>
<tbody>
<tr><td><strong>Bij de redactie</strong></td><td>Nog niet voorgelegd, teruggeroepen of teruggegeven met opmerkingen.</td><td>Jij</td></tr>
<tr><td><strong>Bij het reviewteam</strong></td><td>Het concept ligt ter inzage en is op slot.</td><td>Het team</td></tr>
<tr><td><strong>Akkoord</strong></td><td>Het team heeft geen opmerkingen meer.</td><td>Jij: publiceren</td></tr>
</tbody>
</table>
<p>[[beeld:review-standen|De bak Review, met per concept de stand]]</p>
<h3>Als het team het concept teruggeeft</h3>
<ol>
<li>Open het concept. De opmerkingen staan in de marge naast de tekst waar ze over gaan.</li>
<li>Verwerk de opmerkingen in de tekst.</li>
<li>Geef het concept opnieuw ter inzage als je een nieuwe beoordeling wilt, of publiceer.</li>
</ol>
<h3>Terugroepen</h3>
<p>Wil je toch nog iets wijzigen terwijl het concept bij het team ligt, kies dan <strong>Terugroepen</strong>. Het slot gaat eraf. Was een reviewer al bezig, dan krijgt die bericht; zijn opmerkingen blijven bewaard.</p>
<blockquote><p><strong>Let op.</strong> Een akkoord geldt voor precies die tekst; wijzig je daarna nog iets, dan vervalt het. Een review houdt publiceren nooit tegen: jij beslist. Publiceer je zonder akkoord, dan staat dat in de geschiedenis van het artikel.</p></blockquote>
""",
    },
    {
        "slug": "publiceren",
        "titel": "Publiceren",
        "doelgroep": R,
        "tekst": """
<p>Met publiceren maak je het concept tot de live versie. Vanaf dat moment is dit de tekst die geldt en die medewerkers lezen. De vorige versie blijft bewaard in de geschiedenis.</p>
<h3>Publiceren</h3>
<ol>
<li>Controleer de tekst met <strong>Bekijk als medewerker</strong>.</li>
<li>Klik op <strong>Afronden…</strong> en kies <strong>Publiceren</strong>.</li>
<li>Beantwoord de vraag <strong>Moeten medewerkers dit weten?</strong></li>
</ol>
<p>[[beeld:weten|Bij publiceren kies je of medewerkers een melding krijgen]]</p>
<h3>De vraag of medewerkers het moeten weten</h3>
<table>
<thead><tr><th>Antwoord</th><th>Wanneer</th><th>Wat er gebeurt</th></tr></thead>
<tbody>
<tr><td><strong>Ja</strong></td><td>De werkwijze of de afspraak is veranderd.</td><td>Je schrijft in een zin wat er anders is. Het artikel staat bij medewerkers onder Gewijzigd tot zij het hebben afgevinkt. Wie het artikel als favoriet heeft, kan een e-mail krijgen.</td></tr>
<tr><td><strong>Nee</strong></td><td>Een taalfout, een opmaakfout of een verduidelijking zonder inhoudelijke wijziging.</td><td>Er gaat geen melding uit. De nieuwe versie staat wel in de geschiedenis.</td></tr>
</tbody>
</table>
<h3>Na het publiceren</h3>
<ul>
<li>Het concept bestaat niet meer; het is de live versie geworden.</li>
<li>Had je verbetervoorstellen meegenomen, dan volgt een scherm waarin je de indieners bericht stuurt. De tekst van dat bericht is al voor je ingevuld.</li>
<li>Een nieuw artikel is vanaf nu vindbaar voor iedereen die de omgeving mag lezen.</li>
</ul>
<blockquote><p><strong>Let op.</strong> Schrijf de toelichting voor de lezer: wat moet hij vanaf nu anders doen? "Termijn tweede rappel is nu drie weken" helpt; "tekst aangepast" niet.</p></blockquote>
""",
    },
    {
        "slug": "voorstellen-behandelen",
        "titel": "Verbetervoorstellen behandelen",
        "doelgroep": R,
        "tekst": """
<p>Een verbetervoorstel is een melding van een medewerker dat er iets niet klopt in een artikel. Elk voorstel krijgt een uitkomst en de indiener krijgt bericht. Je behandelt een voorstel in het artikel zelf, zodat je de tekst en het voorstel naast elkaar hebt.</p>
<p>[[schema:verbetervoorstel]]</p>
<h3>Een voorstel openen</h3>
<ol>
<li>Open op de werkplek je eigen bak, of pak eerst een voorstel op uit de <strong>Werkvoorraad</strong>.</li>
<li>Klik op het voorstel. Het bewerkscherm van het artikel opent, met links de lade <strong>Open verbetervoorstellen</strong>.</li>
<li>De tekst waar het voorstel over gaat, is blauw gemarkeerd. Met <strong>Toon in de tekst</strong> spring je ernaartoe.</li>
</ol>
<p>[[beeld:lade|Het bewerkscherm met de lade: links de voorstellen, rechts het artikel]]</p>
<h3>De vier uitkomsten</h3>
<table>
<thead><tr><th>Keuze</th><th>Wanneer</th><th>Wat er gebeurt</th></tr></thead>
<tbody>
<tr><td><strong>Meenemen</strong></td><td>Het voorstel klopt en je past de tekst aan.</td><td>Je zet het vinkje <strong>Meenemen in deze versie</strong> en wijzigt de tekst in het concept. Na het publiceren stuur je de indiener bericht dat het is verwerkt.</td></tr>
<tr><td><strong>Afhandelen</strong></td><td>De tekst is al aangepast in de live versie.</td><td>Je bedankt de indiener. Het voorstel krijgt de stand verwerkt, zonder nieuwe versie.</td></tr>
<tr><td><strong>Afwijzen</strong></td><td>Je neemt het voorstel niet over.</td><td>Je legt de indiener uit waarom.</td></tr>
<tr><td><strong>Ontdubbelen</strong></td><td>Het is hetzelfde als een ander voorstel bij dit artikel.</td><td>Het voorstel vervalt en verwijst naar het andere. De indiener krijgt bericht.</td></tr>
</tbody>
</table>
<h3>Overleggen</h3>
<ul>
<li>Onder <strong>Bericht</strong> stel je de indiener een vraag. Hij krijgt een e-mail en ziet het bericht bij zijn voorstel op de site.</li>
<li>Onder <strong>Notitie</strong> leg je iets vast voor collega's van de redactie. De indiener ziet notities niet.</li>
<li>Bij een voorstel met steun zie je welke collega's het steunen.</li>
</ul>
<blockquote><p><strong>Let op.</strong> Afgehandeld is definitief: een voorstel kan daarna niet worden heropend. Meenemen telt pas als je het concept opslaat. Ligt het concept ter inzage, dan ziet het reviewteam welke voorstellen zijn meegenomen, zonder de naam van de indiener.</p></blockquote>
""",
    },
    {
        "slug": "nieuwsbericht-plaatsen",
        "titel": "Een nieuwsbericht plaatsen",
        "doelgroep": R,
        "tekst": """
<p>Met een nieuwsbericht breng je iets onder de aandacht van alle medewerkers van een omgeving: een nieuwe werkwijze, een belangrijke wijziging, een aankondiging. Een nieuwsbericht vervangt een artikel niet. De afspraak zelf staat in het artikel; het bericht wijst erop.</p>
<p>[[beeld:nieuwsbericht|Het bewerkscherm van een nieuwsbericht]]</p>
<h3>Een bericht schrijven</h3>
<ol>
<li>Klik op de werkplek op <strong>Nieuw bericht</strong>.</li>
<li>Geef het bericht een titel die zegt wat er nieuw is.</li>
<li>Schrijf de tekst. Houd het kort en verwijs naar het artikel voor de details.</li>
<li>Open <strong>Eigenschappen</strong> en kies de omgeving en de artikelen waar het bericht over gaat.</li>
</ol>
<h3>Publiceren</h3>
<ol>
<li>Klik op <strong>Afronden…</strong>.</li>
<li>Kies <strong>Publiceren</strong>.</li>
</ol>
<p>Medewerkers zien het bericht onder Nieuws en, zolang zij het niet hebben gelezen, bovenaan hun eerste pagina.</p>
<h3>Mogelijkheden onder Eigenschappen</h3>
<ul>
<li>Vastpinnen: het bericht blijft bovenaan de nieuwspagina staan.</li>
<li>Een verloopdatum: na die datum staat het bericht onder ouder nieuws.</li>
<li>Artikelen: de lezer kan vanuit het bericht doorklikken naar de genoemde artikelen.</li>
</ul>
<blockquote><p><strong>Let op.</strong> Een wijziging in een artikel hoeft geen nieuwsbericht te zijn: bij publiceren kun je medewerkers al een melding geven. Gebruik een nieuwsbericht voor wat iedereen moet weten, ook wie het artikel nooit opent.</p></blockquote>
""",
    },
    {
        "slug": "synoniemen-en-statistieken",
        "titel": "Synoniemen en statistieken",
        "doelgroep": R,
        "tekst": """
<p>De statistieken laten zien hoe de kennisbank wordt gebruikt: wat er wordt gelezen, waar op wordt gezocht en wat niet wordt gevonden. Daarmee stuur je op de inhoud. Alle cijfers zijn aantallen; er wordt niet bijgehouden wie wat leest of zoekt.</p>
<p>[[beeld:statistieken|Gebruiksstatistieken over de laatste dertig dagen]]</p>
<h3>De statistieken openen</h3>
<p>Klik op de site in het menu links op <strong>Gebruiksstatistieken</strong>. Alleen redacteuren zien dit menu.</p>
<h3>Wat je er ziet</h3>
<table>
<thead><tr><th>Lijst</th><th>Wat het zegt</th><th>Wat je ermee doet</th></tr></thead>
<tbody>
<tr><td>Artikelen</td><td>Hoe vaak een artikel is bekeken, hoeveel voorstellen er liggen, en hoe vaak lezers het nuttig of niet nuttig vonden.</td><td>Een veelgelezen artikel dat vaak niet nuttig wordt gevonden, verdient aandacht.</td></tr>
<tr><td><strong>Gezocht zonder resultaat</strong></td><td>Zoektermen waar niets passends bij werd gevonden.</td><td>Staat het nog niet in de kennisbank: een artikel schrijven. Staat het er wel: een synoniem maken.</td></tr>
<tr><td><strong>Gevonden, maar niet geholpen</strong></td><td>Zoektermen waarna iemand binnen een minuut opnieuw zocht zonder iets te openen.</td><td>Nagaan of de titel en de samenvatting van het bedoelde artikel duidelijk zijn.</td></tr>
</tbody>
</table>
<h3>Een synoniem maken</h3>
<p>Medewerkers gebruiken soms een ander woord dan in de artikelen staat. Met een synoniem vinden zij het artikel toch.</p>
<ol>
<li>Klik bij de zoekterm op <strong>Synoniem maken</strong>. Het formulier opent met de zoekterm al ingevuld bij <strong>Medewerkers zeggen ook</strong>.</li>
<li>Vul bij <strong>Woord in de kennisbank</strong> het woord in dat wel in de artikelen staat.</li>
<li>Sla op. Het synoniem werkt meteen, in beide richtingen.</li>
</ol>
<p>[[beeld:synoniem|Een synoniem: het woord uit de artikelen en de woorden die hetzelfde betekenen]]</p>
<p>De hele lijst staat op de werkplek onder <strong>Alle onderdelen</strong>, bij Synoniemen. De lijst geldt per omgeving.</p>
""",
    },
    # --- Functioneel beheerder ----------------------------------------------------------------------------
    {
        "slug": "omgevingen-en-toegang",
        "titel": "Omgevingen en toegang",
        "doelgroep": B,
        "tekst": """
<p>Als functioneel beheerder richt je de kennisbank in: welke omgevingen er zijn, wie wat mag en hoe het reviewproces loopt. Je bent zelf geen redacteur, maar je kunt overal in.</p>
<p>[[beeld:alle-onderdelen|Je startpagina: Alle onderdelen, met bovenaan de stand van de statuspagina]]</p>
<h3>Wat een omgeving is</h3>
<p>Een omgeving is een afgeschermd deel van de kennisbank, bijvoorbeeld van een afdeling. Elk artikel, elk nieuwsbericht en elk synoniem hoort bij precies één omgeving. Wie geen toegang heeft tot een omgeving, ziet er niets van: niet in de lijsten, niet in de zoekresultaten en niet bij de assistent.</p>
<h3>De rollen</h3>
<table>
<thead><tr><th>Rol</th><th>Waar geregeld</th><th>Wat de rol mag</th></tr></thead>
<tbody>
<tr><td>Lezer</td><td>Per omgeving, via een groep</td><td>Lezen, zoeken, verbetervoorstellen indienen.</td></tr>
<tr><td>Redacteur</td><td>Per omgeving, via een groep</td><td>Alles van de lezer, en schrijven, publiceren en voorstellen behandelen.</td></tr>
<tr><td>Reviewer</td><td>Via een reviewteam</td><td>Concepten beoordelen die aan het team zijn voorgelegd.</td></tr>
<tr><td>Functioneel beheerder</td><td>Technisch ingesteld, voor de hele kennisbank</td><td>Inrichten en overal in kunnen.</td></tr>
</tbody>
</table>
<h3>Toegang regelen</h3>
<ol>
<li>Open onder <strong>Alle onderdelen</strong> de lijst Omgevingen en kies de omgeving.</li>
<li>Voeg onder <strong>Wie heeft toegang tot deze omgeving</strong> een groep toe en kies de rol: lezer of redacteur.</li>
<li>Sla op. De wijziging werkt meteen; niemand hoeft opnieuw in te loggen.</li>
</ol>
<p>[[beeld:omgeving|Een omgeving, met de groepen die toegang hebben]]</p>
<blockquote><p><strong>Goed om te weten.</strong> Je kent rechten toe aan groepen, niet aan personen. De groepen en hun leden komen uit de inlogvoorziening van de organisatie.</p></blockquote>
""",
    },
    {
        "slug": "reviewteams",
        "titel": "Reviewteams",
        "doelgroep": B,
        "tekst": """
<p>Een reviewteam is een groep collega's die concepten inhoudelijk beoordeelt voordat ze worden gepubliceerd. Het reviewproces is per omgeving aan of uit te zetten. Staat het uit, dan publiceert de redactie zonder tussenstap.</p>
<p>[[schema:concept-tot-publicatie]]</p>
<h3>Een reviewteam maken</h3>
<ol>
<li>Open onder <strong>Alle onderdelen</strong> de lijst Reviewteams en voeg een team toe.</li>
<li>Geef het team een naam en kies de omgeving.</li>
<li>Kies de groep waarvan de leden reviewer zijn.</li>
<li>Kies desgewenst de clusters waarvoor het team bedoeld is.</li>
</ol>
<p>[[beeld:reviewteam|Een reviewteam: naam, omgeving, groep en clusters]]</p>
<h3>Het reviewproces aanzetten</h3>
<ol>
<li>Open de omgeving.</li>
<li>Zet <strong>Reviewproces gebruiken</strong> aan en sla op.</li>
</ol>
<p>Redacteuren van die omgeving krijgen nu bij Afronden de keuze om een concept ter inzage te geven.</p>
<blockquote><p><strong>Goed om te weten.</strong> Reviewers hoeven geen lezer van de omgeving te zijn. Zij zien alleen de concepten die aan hun team zijn voorgelegd. Zet je het reviewproces uit terwijl er nog concepten ter inzage liggen, dan stoppen die reviews en krijgen de redacteuren hun concept terug.</p></blockquote>
""",
    },
    {
        "slug": "statuspagina-en-dagelijkse-taak",
        "titel": "De statuspagina en de dagelijkse taak",
        "doelgroep": B,
        "tekst": """
<p>De statuspagina laat zien of de onderdelen van de kennisbank werken. Je hoeft er geen technische kennis voor te hebben: bij elk punt staat wat het betekent en wat je kunt doen.</p>
<h3>De stand bekijken</h3>
<ol>
<li>Open het beheer. Bovenaan je startpagina staat in een regel de uitkomst: alles loopt, of het aantal punten dat aandacht vraagt.</li>
<li>Klik op <strong>Naar de statuspagina</strong> voor de details.</li>
</ol>
<p>[[beeld:statuspagina|De statuspagina: per onderdeel de stand en het advies]]</p>
<h3>Wat er wordt gecontroleerd</h3>
<ul>
<li>De database en de zoekindex.</li>
<li>Of e-mail kan worden verstuurd.</li>
<li>De assistent.</li>
<li>De dagelijkse taak.</li>
<li>Instellingen die in een productieomgeving niet horen, zoals de demo-modus.</li>
</ul>
<h3>De dagelijkse taak</h3>
<p>Elke dag draait er automatisch een taak die opruimt (verlopen kladversies, oude tellingen) en de samenvattingen per e-mail verstuurt aan redacteuren en reviewers. Die samenvatting is de enige e-mail over nieuwe verbetervoorstellen en reviews.</p>
<blockquote><p><strong>Let op.</strong> Loopt de dagelijkse taak niet, dan krijgt niemand bericht en blijft werk ongemerkt liggen. De statuspagina waarschuwt daarvoor. Het herstellen is werk voor de technisch beheerder; geef de melding van de statuspagina aan hem door.</p></blockquote>
""",
    },
    {
        "slug": "hulp-aanpassen",
        "titel": "Deze hulp aanpassen",
        "doelgroep": B,
        "tekst": """
<p>De hulpartikelen worden met de kennisbank meegeleverd en beschrijven hoe de kennisbank werkt. Je kunt ze aanpassen aan jullie situatie, verbergen of aanvullen met eigen artikelen.</p>
<p>[[beeld:hulpartikelen|De lijst met hulpartikelen, met per artikel de doelgroep en de herkomst]]</p>
<h3>Een artikel aanpassen</h3>
<ol>
<li>Open onder <strong>Alle onderdelen</strong> de lijst Hulpartikelen. Of klik op de hulppagina onder een artikel op <strong>Dit hulpartikel aanpassen</strong>.</li>
<li>Pas de titel of de tekst aan.</li>
<li>Kies onder <strong>Eigenschappen</strong> voor wie het artikel is en waar het in het menu staat.</li>
<li>Sla op. De wijziging is meteen zichtbaar.</li>
</ol>
<h3>Wat er bij een nieuwe versie gebeurt</h3>
<table>
<thead><tr><th>Artikel</th><th>Bij een nieuwe versie van de kennisbank</th></tr></thead>
<tbody>
<tr><td>Meegeleverd, niet aangepast</td><td>Krijgt vanzelf de nieuwe tekst en de nieuwe schermafbeeldingen.</td></tr>
<tr><td>Meegeleverd, zelf aangepast</td><td>Blijft zoals jij het hebt gemaakt. Controleer zelf of de uitleg nog klopt.</td></tr>
<tr><td>Eigen artikel</td><td>Wordt niet aangeraakt.</td></tr>
</tbody>
</table>
<p>Wil je de meegeleverde tekst terug, vink het artikel dan aan in de lijst en kies <strong>Standaardtekst terugzetten</strong>.</p>
<h3>Schermafbeeldingen en schema's</h3>
<p>In de tekst staat een schermafbeelding als een regel tussen dubbele rechte haken, die begint met het woord beeld. Een schema begint met het woord schema. Je kunt zo'n regel verplaatsen of weghalen, en het bijschrift achter de streep aanpassen. Eigen afbeeldingen toevoegen kan niet.</p>
<h3>Jullie eigen werkafspraken</h3>
<p>Hoe jullie afdeling met de kennisbank werkt, hoort niet hier maar in een eigen artikel in de kennisbank. Wijs dat bij de omgeving aan in het veld <strong>Artikel met eigen werkafspraken</strong>. De hulppagina toont er dan bovenaan een link naar, voor iedereen die de omgeving mag lezen.</p>
""",
    },
]

for _nummer, _artikel in enumerate(STANDAARD, start=1):
    _artikel["volgorde"] = _nummer * 10
    _artikel["tekst"] = _artikel["tekst"].strip()
