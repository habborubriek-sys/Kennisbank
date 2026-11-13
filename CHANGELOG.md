# Wijzigingen

## 1.31.3 – 2026-11-13

Feedback van Alex op de lade: de knoppen waren te lang en werden afgekapt, *Dubbel…* stond lichtgrijs, de titel had een rand alsof het een knop was, en de lijst met steuners was te lang.

- De drie knoppen in het blok *Afhandelen zonder nieuwe versie* heten nu **Afhandelen**, **Afwijzen** en **Ontdubbelen** (was *Afhandelen als verwerkt…*, *Afwijzen…* en *Dubbel…*). Ze passen naast elkaar in de lade. De vensters erachter zijn niet veranderd.
- **Ontdubbelen** staat niet meer grijs als er geen ander voorstel bij het artikel is; dat oogde alsof de knop niet werkte. Je kunt er nu altijd op klikken; is er geen ander voorstel, dan legt een venster dat uit.
- De knoppen staan alleen nog uit (grijs) als het voorstel is meegenomen in een versie die ter inzage ligt, met de uitleg eronder. *Afhandelen* staat ook uit bij een artikel dat niet gepubliceerd is.
- De titel *Open verbetervoorstellen* boven de lade heeft geen rand meer. Die verscheen als de lade openging (de titel krijgt dan de focus, voor de schermlezer) en liet de titel op een knop lijken. De focus gaat er nog steeds heen; de titel staat niet in de Tab-volgorde.
- **Steun korter**: in plaats van een lijst met de eerste vijf namen staat er één regel, "[naam] en [n] anderen steunen dit voorstel". Klik je erop, dan klapt de lijst met alle namen uit; *Minder tonen* klapt hem weer in. Bij één steuner staat er alleen "[naam] steunt dit voorstel". Het aantal staat niet meer ook nog in de regel erboven.
- `docs/functioneel-beheer.md` en `docs/nvda-testscript.md` gebruiken de nieuwe namen.
- Geen wijziging aan de server-regels; 674 tests. Geen migratie.
- Met Playwright nagelopen: de drie knoppen op één regel en niet afgekapt (1440, 1280 en 1024 px), Ontdubbelen zonder ander voorstel, de titel zonder rand, en de steun in- en uitklappen met het toetsenbord. axe op de lade: 0 overtredingen.

## 1.31.2 – 2026-11-13

Melding van Alex (bouwlijst `bouwlijst-1.31.2-kleine-correctie-en-afhandelen.md`): een tikfout gepubliceerd als kleine correctie, met het voorstel aangevinkt bij *Meenemen*. Het scherm *Meegenomen voorstellen afhandelen* kwam niet.

**Een kleine correctie neemt voorstellen mee (K1)**
- Aangevinkte voorstellen gelden als verwerkt in de nieuwe versie, ook als die een **kleine correctie** is. Na het publiceren volgt het afhandelscherm met het voorgevulde bericht. Dat geldt voor de gewone weg en voor de spoedcorrectie.
- "Kleine correctie" betekent alleen nog: geen melding en geen favorietenmail voor medewerkers. Dat is niet veranderd.
- Publiceren **zonder inhoudelijke wijziging** (er komt geen nieuwe versie) telt nog steeds niet mee; de melding daarover blijft.
- Dit draait een keuze uit 1.28.0 terug (ronde A, M3). Een voorstel over een tikfout is juist een kleine correctie.

**Afhandelen als verwerkt, in de lade (K2)**
- Nieuwe knop **Afhandelen als verwerkt…**, naast *Afwijzen…* en *Dubbel…*. Voor een voorstel waarvan de tekst al is aangepast in de versie die medewerkers nu zien, bijvoorbeeld via een kleine correctie van vóór deze versie, of door een collega.
- Het venster heeft hetzelfde voorgevulde bedankbericht als het scherm na publiceren ("verwerkt in versie n"). Het voorstel krijgt de status *Verwerkt* met het versienummer; de indiener krijgt een melding en een e-mail. Het loopt door dezelfde dienst als het afhandelscherm.
- Staat de geciteerde tekst nog letterlijk in de gepubliceerde versie, dan vraagt de kennisbank eerst of je het zeker weet. De focus staat dan op *Annuleren*. De server controleert dit ook zelf.
- De knop werkt niet als het voorstel is meegenomen in een versie die ter inzage ligt, en niet bij een artikel dat niet gepubliceerd is.
- Deed een collega intussen iets met het voorstel, dan verstuurt de lade niets (409), net als bij de andere handelingen.
- Het blok heet nu **Afhandelen zonder nieuwe versie** (was *Afhandelen zonder wijziging*).

**Tests en documentatie**
- 21 nieuwe tests (`test_kleine_correctie_1312.py`) en één in `test_ronde_a_1280.py`; drie bestaande tests legden het oude gedrag vast en zijn omgezet. Nu 674 tests.
- Mutatiecheck: 9 bewust aangebrachte fouten in de nieuwe code, alle 9 betrapt (één test is daarvoor aangescherpt).
- Met Playwright nagelopen: de knop met het toetsenbord, beide vensters (focus, Escape, Enter), afhandelen, en publiceren als kleine correctie tot en met het afhandelscherm. axe op de lade, de twee vensters en het afhandelscherm: 0 overtredingen.
- `docs/functioneel-beheer.md` bijgewerkt; `docs/nvda-testscript.md` heeft een stap voor de nieuwe knop.
- Geen migratie.

## 1.31.1 – 2026-11-13

Feedback van Alex op 1.30.0 (bouwlijst `bouwlijst-1.31.1-paars-en-opmerking-opslaan.md`).

**Kleuren (besluit Alex)**
- **Opmerkingen van de review zijn paars**, overal: in de editor (markering en kaartjes in de marge), op de reviewpagina, in het voorbeeld en in de legenda's.
- Op de reviewpagina zijn ook de knoppen en links bij de opmerkingen paars, zodat het één geheel is. Weghalen blijft rood.
- In de verschilweergave is **nieuwe tekst weer groen** onderstreept; weggehaalde tekst blijft rood doorgestreept, zoals in Word.
- Voorstellen blijven blauw. Opmerking en voorstel verschillen ook in vorm: een doorgetrokken lijn met een vierkant nummer, tegenover een stippellijn met een rond nummer.

**Opmerkingen op de reviewpagina**
- **Plaatsen, wijzigen en weghalen gebeurt zonder dat de pagina opnieuw laadt.** Het kaartje staat meteen op zijn plek, en de focus gaat ernaartoe. De schermlezer leest de melding voor.
- Gaat het mis (bijvoorbeeld omdat het stuk intussen is teruggeroepen), dan blijft je tekst in het vak staan en zie je de melding erbij.
- Bij het laden verschijnen de kaartjes pas als ze op hun plek staan, en niet eerst bovenaan.
- De voorbeeldtekst in het opmerkingenvak is weg.
- Zonder JavaScript werkt alles nog zoals eerst.

## 1.31.0 – 2026-11-13

Ronde C na de onafhankelijke review van 1.27.0: schermen en teksten (bouwlijst
`bouwlijst-1.30.0-reviewpagina-en-ronde-c.md`, deel 1.31.0). M12 en M16 zaten al in 1.30.0.

**Smalle schermen (M14)**
- Zijn de lade en de opmerkingen allebei open op een scherm smaller dan 1600 px, dan staan de opmerkingen onder de tekst. Het blad blijft breed genoeg en de titel wordt niet meer afgekapt.
- De werkbalk van de editor en de meldingen bovenaan schuiven opzij als de lade open is. Eerst vielen de eerste knoppen onder de lade.
- Springen naar een stuk tekst (*Toon in de tekst*, een opmerking) houdt rekening met de vaste balken, zodat de tekst er niet achter verdwijnt.
- De werkbak past op 1024 px: de voorstelkolom neemt de ruimte die er is en wordt afgekapt met "…".
- Al in ronde B: de melding "staat op slot" schuift mee met de lade, en bij 400% zoom vult de lade het scherm.

**Oude Django-schermen (M15)**
- Geen zijmenu van Django meer in het beheer; de werkplek is het menu (met *Alle onderdelen*). Het kruimelpad is een lichte regel in plaats van een tweede blauwe balk.
- *Meegenomen voorstellen afhandelen* (na publiceren) in de stijl van de werkplek, met ← Werkplek.
- De artikellijst heet **Artikelen**, met de knoppen **Artikel uit Word** en **Nieuw artikel**. Een brede tabel kun je opzij schuiven.
- Paneel *Geschiedenis*: de naam van wie publiceerde in plaats van de inlognaam, en "ja" bij een kleine correctie in plaats van rode kruisjes.

**Teksten en vensters (laag-punten van reviewer 3)**
- B12: **Terugroepen** en **Conceptversie weggooien** vragen het in een venster van de kennisbank in plaats van met een vraag van de browser. De focus staat op Annuleren. In alle vensters is de hoofdknop nu donkerblauw en Annuleren rustig.
- B13: meldingen na opslaan zeggen "Het artikel … is opgeslagen" in plaats van "De artikel … is met succes gewijzigd. U kunt deze hieronder weer bewerken." Bij publiceren zegt het venster "Na het publiceren krijgen medewerkers …" in plaats van "Dit artikel is gepubliceerd". Overal heet het nu **Ter inzage geven** (in *Afronden* stond "Ter inzage aanbieden").
- B14: in **elke bak** kun je zoeken, niet alleen in Afgehandeld. **← Werkplek** brengt je terug naar de bak waar je was. De kolom "Bij" heet "Bij wie".
- B16: weglopen uit de editor met wijzigingen die nog niet zijn opgeslagen? Dan vraagt de browser het eerst. De kladversie vangt het werk ook op.

**Tests**
- 10 nieuwe tests.

## 1.30.0 – 2026-11-13

De reviewpagina gelijk aan de editor, en M12 en M16 uit de review van 1.27.0 (bouwlijst
`bouwlijst-1.30.0-reviewpagina-en-ronde-c.md`, go van Alex).

**Eén balk, zoals in de editor**
- Bovenaan staat een blauwe balk met **← Review**, de titel, **Wijzigingen tonen**, **Bekijk als medewerker**, **☾ Donker** en **Afronden…**. Daaronder staat een lichte infobalk: team, bij wie het stuk ligt, wie het voorlegde, met welke versie wordt vergeleken, en een legenda.
- **Wijzigingen tonen** zet de markeringen van nieuw en weg aan of uit. De browser onthoudt die keuze. De tweede kopie van de tekst onderaan is weg.
- **Bekijk als medewerker** opent een venster met de conceptversie zoals medewerkers hem zien. Dat is hetzelfde voorbeeld als in de editor, met onboarding aan of uit.

**Kleuren**
- Groen is alleen nog voor opmerkingen. **Nieuwe tekst is vet en lichtgrijs** met een donkere streep eronder; weggehaalde tekst blijft rood doorgestreept. De streep links van een gewijzigd blok is grijs in plaats van geel.
- **Verbetervoorstellen staan blauw in de tekst** (stippellijn, rond nummer). Ze zijn genummerd in *Waarom deze wijziging* en hebben daar *Toon in de tekst*. Gaat een voorstel over tekst die is weggehaald, dan staat dat erbij. Namen staan er nog steeds niet bij.
- Genummerde lijsten houden hun nummers, en onboarding-blokken zijn herkenbaar, zoals medewerkers ze zien (review 1.27.0, R3 B15).

**Opmerkingen in de marge**
- Elke opmerking is een kaartje rechts, op de hoogte van de tekst waar het over gaat, met een lijntje ernaar. Ga je met de muis over het kaartje, dan kleurt de markering feller. Op een smal scherm staan de kaartjes onder de tekst.
- Je selecteert tekst en kiest **Opmerking**, of je kiest **+ Algemene opmerking**. Typen of plakken van het stuk tekst kan nog steeds.
- **Je eigen opmerking wijzigen of weghalen** kan zolang het stuk in deze ronde ter inzage ligt (M16, besluit Alex). Een gewijzigde opmerking krijgt "bewerkt", en weghalen vraagt eerst een bevestiging. Alleen de schrijver mag dit; de server controleert dat.
- Vóór **Oppakken** kun je alleen meelezen. Ligt het stuk bij een collega, dan zie je **Overnemen**.

**Afronden**
- **Afronden…** opent een venster met **Teruggeven met opmerkingen** of **Akkoord**, met de uitleg erbij en een vak voor een laatste opmerking.
- Staat er nog een kaartje met tekst open, dan zegt het venster dat en gaat die tekst mee.
- Teruggeven zonder een enkele opmerking kan niet.

**Eerdere rondes en de lijst**
- Eerdere rondes staan ingeklapt onder de tekst. Per oude opmerking zie je het citaat en of die tekst er nog hetzelfde staat of is aangepast.
- In de lijst *Review* staat wat bij jou ligt bovenaan.

**Editor (M12)**
- Opmerking en verbetervoorstel op dezelfde tekst zijn allebei zichtbaar: het groene vlak met de groene lijn, en daaronder de blauwe stippellijn. Eerder verdween het groen.

**Techniek**
- Migratie `0031_opmerking_bewerkt`.
- Nieuw adres `/review/<id>/voorbeeld/`.
- In het voorbeeld werkt Escape nu ook bij vaste inhoud.
- Zonder JavaScript werkt de reviewpagina nog steeds: de kaartjes staan dan als lijst en de knoppen onder de opmerkingen.
- 22 nieuwe tests. axe op de reviewpagina in licht en donker, met alle vensters open: 0 overtredingen.

## 1.29.1 – 2026-11-13

Werkplek en lade na feedback van Alex (bouwlijst `bouwlijst-1.29.1-werkplek-en-lade.md`).

**Werkplek**
- *Procesmanagers* heeft dezelfde kop als *Werkvoorraad* en *Artikelen*.
- *Nieuw artikel*, *Nieuw bericht* en *Artikel uit Word* staan bovenaan de kolom. Zo blijven ze in beeld, ook als de lijst langer wordt.
- **Je eigen bak staat altijd in beeld.** De collega's staan onder **Collega's (n)**, dat je kunt in- en uitklappen. De browser onthoudt of de lijst open of dicht stond. Hij klapt vanzelf open als je in de bak van een collega kijkt of als er bij een collega iets te lang ligt.

**Lade**
- De titel is **Open verbetervoorstellen**. De uitlegzin eronder is weg.
- Zakelijker meldingen, bijvoorbeeld: "1 wijziging bij Meenemen is nog niet opgeslagen. Kies Afronden om op te slaan. Pas dan wordt het voorstel meegenomen en aan jou toegewezen."
- Geen voorbeeldtekst meer in de vakken *Bericht* en *Notitie*. De knoppen heten **✉ Bericht** en **🔒 Notitie**, zodat er niets meer wordt afgekapt.
- **Steun:** de eerste vijf namen als korte lijst, en de rest onder "En nog n meer".
- **De regel onder de titel** noemt alleen de sectie, de steun en bij wie het voorstel ligt. Of de tekst al is aangepast, staat in het uitgeklapte voorstel. Titel en regel worden niet meer afgekapt.
- 6 nieuwe tests; nu 613. axe op de werkplek en de lade: 0 overtredingen.

## 1.29.0 – 2026-11-13

Ronde B na de onafhankelijke review van 1.27.0: toegankelijkheid (bouwlijst `bouwlijst-1.29.0-ronde-b.md`). Doel: het redactie- en reviewdeel haalt WCAG 2.1 AA, ook voor wie met het toetsenbord of een schermlezer werkt.

**Kleuren van de markeringen** (besluit Alex)
- Een **verbetervoorstel is blauw**, een **opmerking van de review is groen**. Geel is er alleen nog voor "Voor nieuwe collega's".
- Ook zonder kleur is het verschil te zien: een voorstel heeft een stippellijn en een rond nummer, een opmerking een doorgetrokken lijn en een vierkant nummer. Het groene nummer heeft een contrast van 6,5:1 (was 3,3:1 bij het oranje).
- Dit geldt overal: in de editor, de marge, de reviewpagina, *Bekijk als medewerker* en de legenda.

**Vensters en panelen**
- Alle vensters in het beheer zijn echte dialogen: Afronden, Versturen, Afwijzen, Dubbel, Link, Overnemen en de kladversie. De schermlezer leest de titel en de uitleg voor, Tab blijft in het venster, Escape sluit het, en daarna staat de focus weer waar je was.
- **Panelen** (Eigenschappen, Geschiedenis, Review): openen zet de focus in het paneel, sluiten zet hem terug op de knop. De knoppen zeggen of het paneel open of dicht is.
- **Bekijk als medewerker**: Escape werkt ook vanuit het voorbeeld. Tab kan niet meer onzichtbaar de tekst in, en na sluiten staat de focus weer op de knop.

**De lade**
- Na elke handeling blijft de focus waar je was (voorstel openen, meenemen, bericht of notitie).
- Een dichte lade is ook voor Tab en de schermlezer dicht. Het tabblad staat vóór de lade, openen zet de focus erin, en Escape of ✕ sluit de lade.
- Meldingen ("nog niet opgeslagen", "Bericht verstuurd") worden voorgelezen.
- *Bericht* en *Interne notitie* zijn knoppen met "ingedrukt".
- Nieuw: **Toon in de tekst** zet de cursor op het citaat.
- Op een smal scherm of bij 400% zoom vult de lade het hele scherm. De meldingen bovenaan schuiven mee opzij.

**In de tekst**
- De schermlezer leest een nummer niet meer als getal in de zin, maar hoort "begin verbetervoorstel 2 … einde verbetervoorstel 2" of "begin opmerking 1 van de review".

**Reviewpagina**
- Een opmerking bij een stuk tekst kan ook zonder muis: na een selectie met Shift+pijltjes, of door de tekst te typen of te plakken.
- Elke opmerking heeft een knop *Ga naar opmerking n in de tekst*.

**Kleiner**
- De werkbalk van de editor is één Tab-stop; met de pijltjes ga je van knop naar knop. De namen van *x²* en *1.≡* kloppen met wat je ziet, en aan/uit-knoppen zeggen hun stand.
- Het sectiemenu (⋯ en +) werkt met de pijltjes. Escape en Tab zetten de focus terug.
- **Werkbak:** het vinkje noemt het voorstel, de stip en het rode aantal hebben een tekst voor de schermlezer, en de balk telt hoeveel voorstellen je hebt aangevinkt (`werkplek.js`).
- Geen dode verwijzingen meer naar hulpteksten. Dat gold ook voor de vinkjes bij Clusters, een fout in Django.
- Meer contrast voor de focusrand van titel en samenvatting, de tekstvakken in de lade, de grijze datums in de beheerlijst, en het blok *Waarom deze wijziging* op de reviewpagina in donker.

**Documentatie en tests**
- `docs/toegankelijkheid.md` is opnieuw opgezet, met de meting van nu en wat nog niet getoetst is.
- Nieuw: `docs/nvda-testscript.md` (32 stappen met verwachtingen) voor een handmatige test met een schermlezer.
- Nieuw: `scripts/browsertests/axe.js` meet 20 schermen met axe: 0 overtredingen. Het toetsenbordgedrag is met Playwright nagelopen.
- 13 nieuwe tests (`test_ronde_b_1290.py`); nu 607.

## 1.28.0 – 2026-11-13

Ronde A na de onafhankelijke review van 1.27.0: de juiste stand en geen werkverlies (bouwlijst `bouwlijst-1.28.0-ronde-a.md`, met de besluiten van Alex).

**Werk gaat niet meer verloren**
- **Tekst in de lade blijft staan.** Wat je typt bij *Bericht* of *Interne notitie* verdween bij een tabwissel, bij meenemen of bij typen in het artikel. Nu niet meer, en weglopen met een bericht dat nog niet is verstuurd, geeft een waarschuwing.
- **Venster "Verder gaan waar je gebleven was?"**: de focus staat op *Verder gaan*, niet op *Weggooien*. Weggooien vraagt eerst om bevestiging. Heeft een collega intussen opgeslagen, dan zegt het venster dat *Verder gaan* diens tekst vervangt. In alle vensters staat de focus nu op het eerste invoerveld of op de hoofdknop.
- **Vinkjes bij Meenemen blijven staan** als opslaan mislukt, met "nog niet opgeslagen". De foutmelding bovenaan noemt het veld en waar het staat ("Kijk naar: Omgeving (in Eigenschappen, rechts)").
- **Voorstel indienen op de site**: naast het venster klikken sluit het niet meer als je al iets hebt getypt, en wat je typte staat er weer als je het venster opnieuw opent.

**De regels gelden overal**
- "Een meegenomen voorstel niet afhandelen zolang de versie ter inzage ligt" staat nu in de dienstlaag: de lade, de API (409) en het oude beheerformulier moeten er allemaal langs.
- **Het oude behandelscherm en het oude beheerformulier verwerken voor open voorstellen niets meer.** Een POST uit een oud tabblad gaat naar de editor; wat je had getypt, staat in de melding. Afgehandelde voorstellen kunnen daar nog een bericht of notitie krijgen.
- **Een verouderd scherm draait het werk van een collega niet meer terug.** Bij opslaan telt alleen wat je zelf bij Meenemen veranderde (nieuw verborgen veld `kb_mee_geladen`). Je wordt niet meer ongevraagd eigenaar.
- **De lade kijkt eerst wat er intussen gebeurde.** Stuurde een collega een bericht, of ligt het voorstel inmiddels bij een ander, dan wordt er niets verstuurd; de lade toont de nieuwe stand en je tekst blijft staan.

**Voorstellen blijven niet meer hangen**
- Een conceptversie gepubliceerd als **kleine correctie**, of **zonder inhoudelijke wijziging**: de meegenomen voorstellen gelden niet als verwerkt en staan weer open, met een melding.
- **Spoedcorrectie**: een voorstel uit een conceptversie die ter inzage ligt, kan niet mee (vinkje uit, met uitleg). Een kleine correctie neemt ook bij een spoedcorrectie geen voorstellen mee. Meenemen bij een spoedcorrectie komt in het logboek.
- Een afgewezen of dubbel voorstel is niet langer "meegenomen". Dubbel in een kring (A → B → C → A) kan niet meer.

**Meegenomen, maar ook verwerkt?** (besluit Alex: waarschuwen, het akkoord blijft staan)
- Neem je na een **akkoord** nog een voorstel mee, dan waarschuwen de lade en *Afronden*: de reviewer heeft het niet gezien. Daarvoor legt *Ter inzage* vast welke voorstellen er toen in zaten (migratie `0030`).
- Staat de tekst van een meegenomen voorstel nog letterlijk in het artikel: "tekst nog ongewijzigd – al aangepast?". Is hij aangepast: "aangepast ✓" in plaats van de gele waarschuwing.

**Privacy**
- **Verborgen voorstellen ziet de reviewer niet meer** (alleen "1 voorstel is niet zichtbaar, omdat er persoonlijke gegevens in staan"). Drie keer onafhankelijk gevonden.
- De selectiebalk in de werkbak wijst alleen toe aan redacteuren van je eigen omgevingen, zonder namen van anderen te tonen. *Onlangs afgerond* op de reviewpagina toont geen artikelen meer die naar een andere omgeving zijn verhuisd. De selectiebalk controleert de eigenaar opnieuw op het moment van opslaan.

**Kleiner**
- Heb je maar één omgeving, dan staat die bij een nieuw artikel, nieuwsbericht en Word-import al ingevuld.
- **Licht en donker** (besluit Alex): het beheer is altijd licht. De site volgt het apparaat en heeft rechtsboven een knop **☾ Donker** om dat om te draaien; de keuze onthoudt de browser (`thema.js`, in de `<head>` zodat er geen flits is). Ook op de reviewpagina's. Contrast van de gele "gewijzigd"-balk in de donkere modus verbeterd (was 4,1:1).
- **Artikel uit Word** staat als knop op de werkplek. De importpagina heeft de stijl van de werkplek (geen broodkruimel of zijbalk), en de melding na de import klopt weer ("kies Afronden" in plaats van "zet de status op Gepubliceerd").

**Tests**
- 49 nieuwe tests (`test_ronde_a_1280.py`), waaronder de vier gaten uit de mutatietest en formuliertests met de velden die de pagina echt verstuurt (conceptversie, spoedcorrectie, nieuwsbericht). Tests van het oude behandelscherm zijn omgezet naar de lade. Nu 594 tests.
- Mutatietest herhaald: 28 bewust aangebrachte fouten, alle 28 betrapt.
- In de browser nagelopen; axe op de site in de donkere modus: 0 fouten.

## 1.27.0 – 2026-11-12

Verbetervoorstellen behandelen in de editor, stap 2.

- **De reviewer ziet waarom de tekst veranderde.** Op de reviewpagina staat boven de wijzigingen een blauw blok *Waarom deze wijziging* met de verbetervoorstellen die in deze versie zijn meegenomen: het citaat en de tekst. **Niet** wie het indiende, en niet de interne notities of berichten (besluit van Alex). Zonder meegenomen voorstellen staat het blok er niet.
- Tests (nu 548); in de browser nagelopen.

## 1.26.0 – 2026-11-12

Verbetervoorstellen behandelen in de editor, stap 1 (bouwlijst `bouwlijst-1.26.0-voorstellen-in-editor.md`, ontwerp en prototype met Alex).

- **De werkbak is een rustige lijst.** Eén regel per voorstel (artikel, begin van het voorstel, bij wie, hoe lang, steun), klik opent. Geen knoppen per regel meer.
- **Toewijzen en verplaatsen in de werkbak**, via vinkjes en een balk erboven, ook voor meerdere voorstellen tegelijk. Heeft een collega een aangevinkt voorstel intussen opgepakt, dan wordt het overgeslagen en gemeld.
- **Een open voorstel opent in het bewerkscherm van het artikel**, met links een **lade Verbetervoorstellen** (een tabblad dat uit de linkerrand steekt). Daarin alle open voorstellen bij het artikel, genummerd, met als titel de eerste zin.
- **In de tekst** staat het citaat blauw met een stippellijn en hetzelfde ronde nummer; klik op het nummer opent het voorstel. Opmerkingen van de review blijven geel, nu met een vierkant oranje nummer. Kleine legenda in de infobalk.
- **Meenemen in deze versie** telt pas bij opslaan. Wie meeneemt wordt eigenaar; ligt het voorstel bij een collega, dan eerst een vraag, en bij opslaan krijgt die collega een e-mail. Kan ook bij een spoedcorrectie; niet terwijl de versie ter inzage ligt.
- **Bericht aan de indiener en interne notitie** in twee aparte tabbladen (blauw en geel); versturen vraagt een bevestiging. **Afwijzen** en **Dubbel** met een afsluitend bericht; een meegenomen voorstel kun je niet afwijzen zolang de review loopt. **Verbergen voor collega's** staat er ook.
- **Het behandelscherm** bestaat alleen nog voor afgehandelde voorstellen (alleen-lezen). Oude links en e-mails naar een open voorstel komen in de editor uit.
- Tests (nu 546); in de browser nagelopen.

## 1.25.1 – 2026-11-12

- **Kleinere balk in het bewerkscherm** (wens Alex: "nog steeds te groot"). De blauwe balk is nu één regel: ← Werkplek, de titel, de knoppen en Afronden. De labels (Conceptversie, stand van de review) en de details staan eronder in een dunne, lichte infobalk met kleine letters. Geldt ook voor nieuwsberichten.

## 1.25.0 – 2026-11-12

Eén uitstraling voor review, beheer en bewerkschermen (bouwlijst `bouwlijst-1.25.0-consistentie.md`, todo van Alex).

- **Fout hersteld uit 1.24.0:** een *nieuw* artikel opslaan mislukte altijd met "Corrigeer de onderstaande fout". De (lege) versielijst ontbrak in het formulier. Er is nu een test die het formulier verstuurt zoals de browser dat doet.
- **Review heet overal Review.** De reviewpagina heette "Ter inzage", de knop op de site "Review". "Ter inzage" is nu alleen nog de stand van een stuk.
- **Eén bovenbalk** voor de site, de reviewpagina's en alle beheerpagina's: logo, omrande knoppen (Review, Werkplek, Naar de kennisbank; de pagina waar je bent staat wit), je naam en Uitloggen. De balk van Django ("Kennisbank – beheer", hoofdletterlinks) is weg.
- **Eén knoppenstijl in het beheer:** de hoofdactie donkerblauw gevuld (Openen, Nieuw artikel), de rest omrand (Oppakken, Toewijzen, Verplaatsen, Zoeken). Ook *Artikel toevoegen* en *Importeren uit Word* boven de lijsten.
- **Balk van het bewerkscherm met meer structuur:** titel; daaronder de labels (Conceptversie, stand van de review) met klein de details; daaronder de knoppen. *Bekijk de gepubliceerde versie*, *Corrigeer de gepubliceerde versie* en *Conceptversie weggooien* staan onder **Meer ▾**.
- **Afronden ook bij een nieuw artikel en bij nieuwsberichten**, met de keuzes Opslaan als concept, Publiceren en Afbreken (bij een gepubliceerd bericht: Opslaan, Terugzetten naar concept, Afbreken).
- Bij een nieuw artikel of bericht staat de cursor in de titel, niet meer op de eerste knop van de balk (die zag eruit alsof hij "aan" stond).
- **Onlangs afgerond** op de reviewpagina: één regel per artikel met de laatste uitkomst; eerdere rondes inklapbaar.
- Tests (nu 524); in de browser nagelopen.

## 1.24.1 – 2026-11-12

- **Geen HTML-code meer te zien tijdens het laden** (melding van Alex: "nog steeds het oude scherm"). Heel even, voordat de editor klaar was, stond het tekstvak met de opgeslagen code in beeld. Dat vak blijft nu onzichtbaar tot de editor er is; de werkbalk houdt vast zijn hoogte, zodat er niets verspringt. Lukt het script niet, dan verschijnt het tekstvak na 3 seconden toch.

## 1.24.0 – 2026-11-12

Het bewerkscherm zonder "oud scherm" eronder, en een nettere balk (bouwlijst `bouwlijst-1.24.0-scherm-server.md`, verzoek van Alex).

- **De server bouwt het scherm meteen goed op.** Titel, samenvatting en tekst staan direct op het blad, de overige velden in Eigenschappen, versies in Geschiedenis. Er wordt niets meer verhuisd na het laden, dus er is geen flits en geen verborgen wachttijd meer (de oplossing van 1.23.1 is vervallen). Geldt voor artikelen en nieuwsberichten.
- **Balk netter uitgelijnd.** Boven: de titel met de stand eronder, rechts het reviewlabel. Daaronder één regel: links **← Werkplek**, rechts de panelen en als laatste **Afronden…**, alle knoppen even hoog. Afronden is kleiner en staat met wat extra ruimte naast de andere knoppen.
- Meldingen ("is opgeslagen") en foutmeldingen staan onder de balk, in een rode kader bij fouten.
- Wie een artikel alleen mag bekijken, ziet de gewone weergave.
- Tests (nu 514); in de browser nagelopen.

## 1.23.1 – 2026-11-12

- **Geen flits meer van het oude formulier** bij het openen van een artikel of nieuwsbericht (melding van Alex). Het scherm blijft onzichtbaar tot de velden op hun plek staan; dat duurt meestal minder dan een halve seconde. Lukt het script niet, dan verschijnt het formulier na 3 seconden toch.

## 1.23.0 – 2026-11-12

Nieuwsberichten in hetzelfde scherm als artikelen (bouwlijst `bouwlijst-1.23.0-nieuwsberichten.md`, keuze van Alex: "Zelfde scherm als artikelen").

- **Nieuwsbericht bewerken** gaat zoals een artikel: een balk bovenaan met *Opslaan* en *Eigenschappen*, het bericht als blad (titel en tekst), en omgeving, gekoppelde artikelen, status, vastpinnen en verloopdatum in het paneel Eigenschappen. Verwijderen staat onderaan dat paneel.
- **Dezelfde editor** (Tiptap) met dezelfde werkbalk, zonder secties en onboarding.
- **Jodit is uit het pakket**: de bestanden, de SBOM-regel en de oude code voor secties, tussenruimte en het volledig scherm zijn weg. IT heeft nog één editor om bij te houden.
- Meldingen ("is opgeslagen") staan op beide schermen onder de balk in plaats van erboven.
- Tests (nu 509); in de browser nagelopen.

## 1.22.0 – 2026-11-12

Eén bewerkscherm voor artikelen: je bewerkt het artikel zoals medewerkers het zien (bouwlijst `bouwlijst-1.22.0-nieuw-bewerkscherm.md`, na het ontwerp en het prototype; Alex koos Tiptap als editor).

- **Eén scherm in plaats van twee.** Het splitscreen (volledig scherm met voorbeeld) verdwijnt. Bovenaan staat één balk: ← Werkplek, de titel, *Conceptversie · medewerkers zien versie n*, de stand van de review (*Ter inzage bij Team Water · ligt bij Wim*, *Teruggegeven · 2 opmerkingen*, *Akkoord*), de knoppen Opmerkingen, Bekijk als medewerker, Eigenschappen, Geschiedenis en Review, en Afronden.
- **Nieuwe editor (Tiptap).** Een sectie is een kaart met een kop en tekst, zoals in de kennisbank, en kan niet meer half kapot of genest raken. Tussen twee blokken verschijnt een **+** om tekst of een sectie in te voegen. Elke sectie heeft een ⋯-menu: omhoog, omlaag, opheffen, verwijderen. Onboarding staat in het gele kader. Ongedaan maken en opnieuw werken over het hele artikel (Ctrl+Z, Ctrl+Y en knoppen). De "tussenruimte" met stippellijnen is weg.
- **Titel en samenvatting** staan bovenaan het artikel, zijn altijd aanwezig en platte tekst, met uitleg als ze leeg zijn en een label als je erin klikt. Enter springt door naar het volgende veld.
- **Opmerkingen van de review in de rechtermarge**, op de hoogte van de gemarkeerde tekst. Na teruggeven staan ze meteen aan. De markering zit niet in de tekst.
- **Bekijk als medewerker**: het artikel met dichtgeklapte secties en de onboardingschakelaar, in een laag over het scherm.
- **Panelen** rechts: Eigenschappen (soort, omgeving, clusters, tags, zaaktypen, nakijkdatum, status, publicatie), Geschiedenis (versies, meegenomen voorstellen) en Review (stand, opmerkingen, eerdere rondes, terugroepen).
- **Niets veranderd** aan opslaan, controles, kladversie, slot, spoedcorrectie en Afronden, en aan het opgeslagen formaat: bestaande artikelen werken zonder omzetten.
- Tiptap wordt meegeleverd (`vendor/tiptap/`, gebouwd in `frontend/` met vaste versies) en staat in de SBOM. Nieuwsberichten gebruiken nog Jodit.
- Tests (nu 507); het hele scherm in de browser nagelopen: typen, + tussen blokken, sectiemenu, ongedaan maken, onboarding, tabel, opmerkingen, ter inzage (alleen lezen), spoedcorrectie, kladversie, afbreken, nieuw artikel, bekijk als medewerker.

## 1.21.0 – 2026-11-12

Reparaties na de onafhankelijke review van alles sinds 1.15.0, en één knop *Afronden* (bouwlijst `bouwlijst-1.21.0-reviewbevindingen.md`, besluiten van Alex van 11 en 12 november).

**Afronden**

- Onder een gepubliceerd artikel staat **één knop *Afronden…*** met een venster: **Opslaan als concept**, **Ter inzage aanbieden**, **Publiceren** en **Afbreken**. Ligt de conceptversie ter inzage, dan alleen **Terugroepen** en **Afbreken**; bij een spoedcorrectie alleen **Publiceren** en **Afbreken**.
- **Ter inzage aanbieden slaat eerst op**: het team leest altijd de tekst van het scherm (bevinding 4).
- **Afbreken** sluit zonder op te slaan en ruimt de kladversie van dat scherm op; een opgeslagen conceptversie blijft staan.
- **Na een akkoord** waarschuwt een balk zodra je gaat typen. Publiceer je een andere tekst dan het team zag, dan staat in de versiegeschiedenis "Gepubliceerd met wijzigingen na het akkoord van …" in plaats van "Akkoord van …" (bevinding 1). Opslaan zonder wijziging laat het akkoord staan.

**Reviewproces**

- **Publiceren en weggooien kan pas na terugroepen** zolang de conceptversie ter inzage ligt (besluit Alex). Voor haast is er de spoedcorrectie (bevinding 7).
- **Reviewproces uitzetten** roept alles terug wat ter inzage ligt, met een e-mail aan de reviewer (bevinding 3).
- **Archiveren** (lijst en scherm) en **verhuizen naar een andere omgeving** stoppen de review, met een e-mail aan een reviewer die bezig was. De conceptversie blijft bewaard; bij archiveren blijft de gepubliceerde tekst in het artikel (bevinding 6 en 15).
- **Spoedcorrectie**: de omgeving zit vast. Reviewers zien alleen stukken van de omgeving van hun team (bevinding 2).
- **Reviewers**: een afgerond stuk staat in *Onlangs afgerond* zonder link en zonder tekst (bevinding 11). Is een stuk intussen gestopt of teruggeroepen, dan een nette melding met de getypte tekst in plaats van "pagina niet gevonden" (bevinding 7). *Oppakken* neemt niet meer stilletjes over van een teamgenoot (bevinding 16).
- **Terugroepen vanaf een verouderd scherm** zegt wat er intussen gebeurde, bijvoorbeeld "Team Water heeft intussen akkoord gegeven" (bevinding 14).

**Verbetervoorstellen**

- **Verbergen voor collega's** en **Meenemen** zetten de stand die je ziet in plaats van om te wisselen (bevinding 5).
- **Oppakken, terugleggen en toewijzen vanaf een oude werkplek** doen niets als het voorstel intussen bij een collega ligt; je ziet bij wie (bevinding 9).
- **Conceptversie weggooien** zet *meenemen* uit; een kleine correctie neemt geen voorstellen mee (bevinding 8).
- **Dubbel** alleen bij een voorstel van hetzelfde artikel, en niet in een kring (bevinding 10).
- **Afhandelen via de API** en het oude beheerformulier mailen ook de vorige eigenaar (bevinding 12).
- **De dagelijkse samenvatting** noemt alleen voorstellen die nog open staan (bevinding 13).

- Bevinding 17 (andere velden in de verschilweergave) vervalt: geen inhoudelijke wijziging (besluit Alex).
- Tests (nu 501), elke reparatie tegen een bewust kapotte versie gedraaid; *Afronden* in de browser nagelopen.

## 1.20.1 – 2026-11-11

Terugroepen terwijl een reviewer al bezig is (vraag van Alex):

- **Eerst een vraag**: "Team Water (2 opmerkingen) is hier al mee bezig. Toch terugroepen?"
- **E-mail aan de reviewer** die het stuk had opgepakt, met hoeveel opmerkingen er bewaard zijn.
- De opmerkingen die er al waren, blijven bewaard en heten voor de redacteur **voorlopig**: in de gele balk "mogelijk niet compleet", in het voorbeeld van het volledig scherm "voorlopig: teruggeroepen terwijl het team nog bezig was".
- Tests (nu 468), elk tegen een bewust kapotte versie gedraaid; in de browser nagelopen.

## 1.20.0 – 2026-11-11

Het reviewproces, stap C2 en D (bouwlijst `ronde3-reviewproces-bouwlijst.md`, keuzes van Alex van 11 november).

**C2: voorstellen en spoedcorrectie**

- **Meenemen in de nieuwe versie** in het behandelscherm van een voorstel (en weer uitzetten). De gele balk van het artikel noemt de meegenomen voorstellen.
- **Na publiceren** een scherm met per meegenomen voorstel een **voorgevuld bericht** ("We hebben het verwerkt in versie n …") en een vinkje *Nu afhandelen*. Zonder vinkje blijft het voorstel open met "Verwerkt in versie n".
- **Corrigeer de gepubliceerde versie** (spoedcorrectie) in de gele balk: de gepubliceerde tekst aanpassen terwijl er een conceptversie is. De conceptversie, een lopende review, de kladversie en meegenomen voorstellen blijven ongemoeid; de gele balk en de reviewer zien daarna dat de gepubliceerde versie is aangepast. Versiegeschiedenis: "Spoedcorrectie".

**D: opmerkingen bij de tekst**

- De reviewer **selecteert tekst** in de weergave met de wijzigingen en zet er een opmerking bij; een algemene opmerking kan ook. De citaten zijn geel gemarkeerd met een nummer, de opmerkingen staan genummerd ernaast.
- De redacteur ziet de opmerkingen van de laatste ronde **in het live voorbeeld van het volledig scherm**: markeringen met nummers, een lijst bovenaan, klikken springt naar de plek. Past hij de zin aan, dan verdwijnt de markering en staat er "tekst is intussen gewijzigd", met het oorspronkelijke citaat. In de gele balk staat bij elke opmerking het citaat.
- Opmerkingen zijn voor de redacteur pas zichtbaar als het team heeft gereageerd (zoals de reviewer te zien krijgt).

- **Tests** (nu 465): meenemen, scherm na publiceren met e-mail, overslaan, alleen eigen omgeving; spoedcorrectie (opent de gepubliceerde tekst, raakt conceptversie en review niet, vraagt een toelichting, neemt geen voorstellen mee, waarschuwing bij redacteur en reviewer); citaat bewaren, algemene opmerking, citaat bij teruggeven, gegevens voor reviewer en voorbeeld, geen HTML, alleen de laatste ronde en pas na reactie. Elke bescherming tegen een bewust kapotte versie gedraaid. In de browser nagelopen: tekst selecteren, markeringen bij de reviewer, markeringen in het volledig scherm, zin aanpassen.

## 1.19.0 – 2026-11-11

Het reviewproces, stap C1 (bouwlijst `ronde3-reviewproces-bouwlijst.md`, keuzes van Alex van 11 november). Standaard uit; een beheerder zet het per omgeving aan.

- **Reviewteams** (alleen een beheerder): naam, omgeving, de Entra ID-groep van het team en de clusters waarvoor het team is voorgevuld. Wie in de groep zit, is reviewer.
- **Ter inzage** in de gele balk van een conceptversie: het team van het cluster staat aangevinkt, meer teams mag. De conceptversie staat daarna **op slot** (het scherm wordt alleen-lezen, en de server weigert opslaan als conceptversie). **Terugroepen** maakt hem weer vrij.
- **Leesweergave voor reviewers** op `/review/`, buiten het beheer: een statusbalk (hoeveel ter inzage, bij jou, nog niet opgepakt, oudste), per stuk de nieuwe tekst met **de wijzigingen gemarkeerd** zoals in Word, oppakken ("ligt bij"), opmerkingen, **teruggeven met opmerkingen** of **akkoord**. Knop **Review** in de kennisbank voor reviewers.
- **Akkoord-label** in het beheer: "Versie n akkoord bevonden door Team Water, datum". Bij meer teams pas als alle teams akkoord zijn. **Wijzigt de redacteur daarna iets, dan vervalt het akkoord.** Teruggegeven opmerkingen en eerdere rondes staan in de gele balk; de redacteur krijgt een e-mail bij teruggeven of akkoord.
- **Publiceren kan altijd.** Ligt de conceptversie nog ter inzage, dan gaat precies de opgeslagen tekst live. De versiegeschiedenis heeft een kolom *Review*: "Akkoord van Team Water." of "Gepubliceerd zonder akkoord van …".
- **Werkplek**: bak *Ter inzage* onder Artikelen, met de stand per team; teruggegeven bovenaan en in de telling.
- **Dagelijkse samenvatting voor reviewers** (besluit c), via `opschonen` en `kennisbank_voorstellenmail`.
- **Demo**: reviewproces aan, een Team Water (cluster Nat beheer) en het account `reviewer` / `demo`.
- **Reparatie (uit 1.18.0)**: op het behandelscherm van een voorstel wezen de bakken in de linkerkolom naar het scherm zelf in plaats van naar de werkplek.
- **Tests** (nu 446): ter inzage (voorgevuld, op slot, oud scherm, andere omgeving, niet dubbel, reviewproces uit), publiceren tijdens de review publiceert de conceptversie, terugroepen, weggooien, werkplekbak, de leesweergave (alleen het eigen team, niet ingelogd, wijzigingen gemarkeerd, oppakken, opmerking, teruggeven alleen met opmerking, akkoord en vervallen, versiegeschiedenis), meerdere teams en rondes, reviewteams alleen voor een beheerder, de samenvatting, `/ik`, het verschil (ook geen HTML). Elke bescherming tegen een bewust kapotte versie gedraaid; twee gaten gevonden en gedicht. In de browser nagelopen met de demo-accounts.

## 1.18.0 – 2026-11-11

Ronde 2 uit de functionele review van 11 november (punt 10), met de besluiten c, d en e van Alex.

**Eigen behandelscherm voor een voorstel** (`/beheer/voorstel/<id>/`)

- In de stijl van de werkplek, met de kolom links en *Terug naar de werkplek*. Het vervangt het kale beheerformulier; oude links sturen door.
- Bovenaan het voorstel met de geselecteerde tekst **in de tekst van het artikel**, geel gemarkeerd. Overal volledige namen; de redactie ziet wie het voorstel steunt.
- **Bericht aan [naam]** met de knoppen *Versturen*, *Versturen en verwerkt* en *Versturen en afwijzen*, en de uitleg dat de indiener het als melding en per e-mail krijgt. Afhandelen zonder bericht kan niet.
- **Afwijzen als dubbel** van een ander voorstel bij hetzelfde artikel (besluit d): niet samenvoegen, de steun gaat niet mee.
- **Iemand anders was je voor**: heeft een collega intussen een bericht gestuurd of de status veranderd, dan wordt er niets verstuurd; je ziet wat er gebeurde en je tekst blijft staan (functioneel analist, punt 8).
- Handel je een voorstel uit de bak van een collega af, dan krijgt die collega een e-mail.
- Bakacties (oppakken, terugleggen, toewijzen, verplaatsen) en *Verbergen voor collega's* in een zijkolom.

**Interne notities**: alleen voor de redactie, met naam en tijd. Nooit zichtbaar voor de indiener of collega's; ze verdwijnen bij het anonimiseren van het voorstel (migratie 0027).

**Keuzevak bij zaaktypen in het Nederlands**: Django 5.2 vertaalt "Choose all", "Remove all" en de uitleg bij het dubbele keuzevak niet; die vertaling staat nu in `kennisbank/locale` (omzetten met `scripts/maak_mo.py`).

**Zoeken in Afgehandeld**: op artikel, voorstel, berichten en notities, binnen je eigen omgevingen.

**Archiveren sluit voorstellen af** (besluit e): de open voorstellen bij een gearchiveerd artikel krijgen de nieuwe status **Vervallen** met het bericht "Het artikel … is ingetrokken". De indiener krijgt een melding en een e-mail. Afgehandelde voorstellen blijven zoals ze waren.

**Dagelijkse samenvatting voor redacteuren** (besluit c): in plaats van een e-mail per nieuw voorstel aan elke redacteur één e-mail per dag met de nieuwe voorstellen in je omgeving(en), je eigen bak en wat langer dan 30 dagen ligt. Verstuurd door `opschonen`; apart: `kennisbank_voorstellenmail`. Niets nieuw, geen e-mail.

- **Tests** (nu 418): het behandelscherm (inhoud, alleen eigen omgeving, oude link, bericht, leeg bericht, verwerkt alleen met bericht, e-mail aan de collega, dubbel zonder steun, dubbel uit een andere omgeving, nieuw bericht of status intussen, definitief, notities alleen voor de redactie en weg bij anonimiseren, verbergen, terug na een bakactie), het citaat in de tekst (ook geen HTML), zoeken in het archief (ook niet in een andere omgeving), archiveren, de samenvatting (per redacteur, niet dubbel, via opschonen) en de dienst zelf als tweede laag. Elke bescherming tegen een bewust kapotte versie gedraaid. In de browser nagelopen.

## 1.17.1 – 2026-11-11

Ronde 1 uit de functionele review van 11 november (UX-ontwerper en functioneel analist; in het project: `review-functioneel-ux-1.17.0.md` en `review-functioneel-analist-1.17.0.md`), met de keuzes van Alex.

**Verbetervoorstellen**

- **Afhandelen gaat met een bericht.** Wie een voorstel op *Verwerkt* of *Afgewezen* zet, moet erbij schrijven waarom (beheer en API). Vroeger kreeg de indiener dan zijn laatste tussenbericht ("we kijken ernaar") nog eens als antwoord. Een statuswijziging zonder bericht mailt alleen de nieuwe status; terug naar *Nieuw* mailt niet.
- **Afgehandeld is definitief** (besluit van Alex): de status van een verwerkt of afgewezen voorstel staat op slot, ook via de API (409). Een bericht aan de indiener kan nog wel.
- **Verplaatsen zonder keuze** verhuisde het voorstel stilletjes naar Algemeen; nu volgt "Kies eerst een bak".
- **Eigen meldingen** na oppakken, toewijzen, verplaatsen en opslaan, met de titel van het artikel en waar het voorstel nu ligt (in plaats van "1 voorstel(len)" en Djangos "De verbetervoorstel …").
- **Medewerker**: een nieuw antwoord op je eigen voorstel staat altijd bovenaan, ook als het filter het anders verbergt, en de teller krijgt dan de blauwe stip zoals bij Nieuws. Het indienvenster zegt dat procesmanagement laat weten wat ermee gebeurt, en bij steunen staat dat procesmanagement ziet wie steunt.
- **Venster "Er ligt al een voorstel"**: een eigen tekst als het enige open voorstel van jezelf is, je geselecteerde tekst staat erin, en na steunen wordt de knop *Klaar*.

**Publiceren**

- Bij een gepubliceerd artikel heten de knoppen **Publiceren…** en **Publiceren en verder bewerken**; *Opslaan en nieuwe toevoegen* is weg. Ontbreekt de toelichting, dan vraagt een venster erom vóór het versturen; in conceptmodus altijd. Na de foutmelding over een ontbrekende toelichting verstuurt het venster nu echt (sloot eerst zonder iets te doen).
- **Werk van een collega publiceren**: is de conceptversie begonnen of het laatst bijgewerkt door een collega, dan volgt eerst een bevestiging, en die collega krijgt na publiceren een e-mail.
- Na *Publiceren…* ga je terug naar je werkplek.
- Clusters kies je met vinkjes in plaats van het half-Engelse dubbele keuzevak.

**Werkplek**

- Heeft een collega je iets toegewezen dat je nog niet opende, dan opent de werkplek met je eigen bak.
- Aantallen zijn rood alleen als er iets langer dan 30 dagen ligt.
- De omgeving staat alleen bij een voorstel als je in meer omgevingen redacteur bent (de controle keek per ongeluk naar het aantal bakken).
- Knop **Werkplek** rechtsboven in de kennisbank voor redacteuren.

- **Tests** (nu 386): afsluitend bericht (beheer en API), geen mail bij terug naar Nieuw, afgehandeld op slot (beheer en API) met bericht nog mogelijk, verplaatsen zonder keuze, de meldingen, de knoppen, de collega-bevestiging en de e-mail, terug naar de werkplek, eigen bak eerst, rood alleen bij lang liggen, omgevingslabel, werkplekknop. Elk tegen een bewust kapotte versie gedraaid. In de browser nagelopen: werkplekknop, verplaatsen zonder keuze, toelichtingsvenster, collega-bevestiging, venster bij dubbele voorstellen.

## 1.17.0 – 2026-11-11

De eerste twee stappen uit het ontwerp voor verbetervoorstellen per cluster en het reviewproces (ontwerp met Alex, 11 november; in het project: `ontwerp-reviewproces.md`). Stap A en B; het reviewproces zelf (C) en de opmerkingen in de zijbalk (D) volgen.

**A. Werkvoorraad per cluster**

- Een nieuw voorstel komt in de werkbak van het **cluster** van het artikel als dat er precies één heeft, en anders in **Algemeen** (geen cluster, of twee of meer). Op de werkplek staat de werkvoorraad nu als *Algemeen* plus één bak per cluster, met aantallen. Alleen clusters die in je eigen omgevingen voorkomen.
- Met *Naar bak…* → *Verplaatsen* zet je een voorstel in een andere bak, ook naar Algemeen; dat staat in de geschiedenis van het voorstel. Het cluster blijft als label staan als iemand het voorstel oppakt, en terugleggen brengt het terug in die bak. Ook in het behandelscherm te kiezen (*Clusterbak*).
- Bestaande voorstellen worden bij de update volgens dezelfde regel verdeeld.

**B. Conceptversie naast de gepubliceerde versie**

- Nieuwe knop **Opslaan als conceptversie** bij een gepubliceerd artikel. Medewerkers blijven de gepubliceerde versie zien: geen nieuwe versie, geen melding, geen e-mail, geen wijziging in de zoekindex. Er is één conceptversie per artikel, voor de hele redactie.
- Een artikel met een conceptversie opent in het beheer met die conceptversie, met een gele balk (wie, wanneer, welke versie medewerkers zien) en de knoppen *Conceptversie bekijken* en *Conceptversie weggooien*. **Opslaan** publiceert de conceptversie (met de gewone toelichting) en ruimt hem op.
- Twee redacteuren in dezelfde conceptversie overschrijven elkaar niet ongemerkt, en publiceren vanuit een scherm waarvan de conceptversie intussen is veranderd wordt geweigerd. In het volledige scherm slaat *Opslaan* de conceptversie op. Weggooien ruimt ook de kopie in de browser op.
- Op de werkplek staan conceptversies onder *Concepten*.

- **Tests** (nu 369): de binnenkomstregel (ook via de API), de werkplek per cluster en de afscherming van clusters tussen omgevingen, verplaatsen, terugleggen, vast aantal databasevragen; de conceptversie (artikel blijft ongewijzigd, medewerkers zien de oude tekst, openen toont de conceptversie, publiceren, toelichting blijft verplicht, twee redacteuren, verouderd scherm, weggooien, bekijken geschoond, andere omgeving, alleen naast een gepubliceerde versie, kladversie, werkplek). De beschermingen zijn ook tegen een bewust kapotte versie gedraaid; één test raakte de tweede verdediging niet en is aangescherpt.

## 1.16.0 – 2026-11-10

De werkplek voor redacteuren, en de reparaties uit de onafhankelijke review van 10 november over alles sinds 1.11.0 (rapport in het project: `review-sinds-1.11.0-onafhankelijk.md`).

**Werkplek in het beheer** (wens van Alex)

- `/beheer/` heeft links een kolom met de werkbakken: **Werkvoorraad** bovenaan (bij meer omgevingen één per omgeving), daaronder **alle procesmanagers** met het aantal open voorstellen in hun bak (ook als dat 0 is; je eigen naam bovenaan, met "nieuw"), het archief **Afgehandeld**, en de artikelkant: **Concepten**, **Mijn kladversies** en **Opnieuw nakijken**. Rechts staat de inhoud van wat je aanklikt, met knoppen *Oppakken*, *Overnemen*, *Terugleggen*, *Toewijzen aan…* en *Openen*. Na opslaan in het behandelscherm kom je terug in de bak waar je vandaan kwam.
- De oude lijst *Verbetervoorstellen* staat niet meer onder "Alle onderdelen". Het behandelscherm met het gesprek blijft.

**Reparaties uit de review**

- **Kladversies kwamen na opslaan terug (ernstig, uit 1.14.0).** Het baken dat de browser bij het verlaten van de pagina stuurt, kwam bij de server aan nét nadat het opslaan de kladversie had afgesloten, en opende hem weer. Gevolg: bij een nieuw artikel de vraag "Verder gaan?" voor iets wat al was opgeslagen, en bij een bestaand artikel een spook-kladversie die ook collega's zagen. Nu stuurt de browser na *Opslaan* niets meer naar de server, en weigert de server een kladversie te heropenen die is afgesloten nadat het scherm werd geopend (409). In de browser nagespeeld: na opslaan blijft hij dicht.
- **Een verouderd behandelscherm draaide het werk van een collega terug.** Opende Anna een voorstel, pakte Bram het intussen op en verstuurde Anna alleen een bericht, dan stond het voorstel weer in de werkvoorraad. Het scherm onthoudt nu wat er bij het openen stond en voert alleen door wat de redacteur zelf veranderde; wilde hij precies veranderen wat een collega al veranderde, dan volgt een melding. De API vergrendelt nu vóór het vergelijken en accepteert `verwachte_status`.
- **Privacy bij "Alle voorstellen"**: het indienvenster zegt nu *"Collega's zien je voorstel, zonder je naam. Alleen procesmanagement ziet wie het indiende, voor als ze contact met je willen opnemen."*; collega's zien alleen de datum, niet het tijdstip; en de redactie kan een voorstel **verbergen voor collega's** (migratie 0024).
- **Geen voorstellen meer in de bak van iemand die er niet meer bij kan.** Bij een rechtenwijziging, het verhuizen van een artikel naar een andere omgeving, en dagelijks in `opschonen` gaan zulke voorstellen terug naar de werkvoorraad.
- **Wie afhandelt, is eigenaar** (keuze van Alex), ook als het voorstel bij een collega lag. Status terug naar *Nieuw* laat de eigenaar staan (besluit van Alex).
- Steun intrekken kan alleen nog bij een open voorstel. De werkvoorraad toont alleen open voorstellen. De beheerlijst *Kladversies* deed één databasevraag per rij. Een bericht via `PATCH` met `terugkoppeling` valt nu onder het dubbelklikslot. De API-documentatie beschrijft `lijst` en `artikel`.
- **Bekende beperking, bewust niet gebouwd**: twee *nieuwe* artikelen tegelijk in twee tabbladen delen één kladversie. Staat in de handleiding.

**Kleine wensen**

- De uitlegzin boven *Alle voorstellen* is weg. De link naar de API-documentatie staat alleen nog bij functioneel beheerders. Het label "Demo" naast de naam bovenin is weg.

- **Tests** (nu 348): de werkplek (kolom en aantallen, inhoud per bak, acties, scheiding tussen omgevingen, vast aantal databasevragen) en elke reparatie uit de review. De reparaties zijn ook tegen een bewust kapotte versie gedraaid om te zien dat de tests erop vallen; een test die dat eerst niet deed (de rechtencontrole), is aangescherpt.

## 1.15.0 – 2026-11-10

Verbetervoorstellen in bakken, steun van collega's, een startpagina voor redacteuren, en Nederlandse foutpagina's (S8). Wensen van Alex van 10 november.

**Bakken voor verbetervoorstellen (in het beheer)**

- Een nieuw voorstel komt in de **gezamenlijke bak** van zijn omgeving. Een redacteur **pakt het op** (naar zijn eigen bak), **wijst het toe** aan een collega of **legt het terug**. Iedere redacteur kan in elkaars bak kijken en er een voorstel uit **overnemen**, bijvoorbeeld bij ziekte; dat staat in de geschiedenis van het voorstel.
- Oppakken en toewijzen zetten een nieuw voorstel op *In behandeling*. Terugleggen zet het terug op *Nieuw* zolang er nog geen bericht naar de indiener is gegaan; daarna blijft het *In behandeling*. Een afgehandeld voorstel blijft bij wie het afhandelde.
- Wie een voorstel toegewezen krijgt, krijgt een e-mail met een link naar het voorstel. In de lijst staat "nog niet geopend" tot de eigenaar het opent: "gelezen" is nu per bak.
- Alles loopt via één functie (`diensten.voorstel_naar_bak`), met een rijslot, zodat twee redacteuren die tegelijk hetzelfde voorstel verplaatsen elkaar niet in de weg zitten. Wie de status zet van een voorstel uit de gezamenlijke bak, neemt het daarmee in zijn bak — ook via de API.
- Behandelen gebeurt niet meer in de kennisbank zelf: het statusmenu en het berichtenvak voor redacteuren zijn daar weg, met een knop naar het werkoverzicht. De API-eindpunten om te behandelen blijven bestaan.

**Startpagina voor redacteuren**

- `/beheer/` toont een **werkoverzicht**: mijn bak, de gezamenlijke bak, de bakken van collega's (hoeveel en hoe lang), concepten, eigen kladversies, artikelen over hun herzieningsdatum, en knoppen voor *Nieuw artikel* en *Nieuw bericht*. Django's lijst met onderdelen staat eronder onder "Alle onderdelen". Het aantal databasevragen is vast (bewaakt door een test).

**Steun van collega's (de like-knop)**

- In de kennisbank heeft *Verbetervoorstellen* twee knoppen: **Mijn voorstellen** (zoals voorheen, nu met het aantal steunbetuigingen) en **Alle voorstellen**: de open voorstellen bij artikelen die je mag lezen, zonder naam van de indiener, met een knop **Steunen**. Sorteren op nieuwste of meeste steun.
- Eén keer per persoon, alleen bij een open voorstel, niet bij je eigen voorstel. Collega's zien alleen het aantal; de redactie ziet ook wie (keuze van Alex). Bij de anonimisering na afhandeling worden de namen gewist en blijft het aantal staan.
- **Wie een voorstel wil indienen bij een artikel waar al open voorstellen liggen, ziet die eerst in een schermvullend venster**, met de vraag of hij er een wil steunen. "Toch een eigen voorstel indienen" gaat door naar het gewone venster, met de geselecteerde tekst.

**Nederlandse foutpagina's (S8)**

- 400 (bijvoorbeeld een te groot verzoek), 403, 404 en 500 tonen een eigen pagina in de stijl van de kennisbank, met uitleg in gewoon Nederlands en een knop terug, in plaats van Django's Engelse standaardpagina. Onder `/api/` blijft het antwoord JSON. De pagina valt bij een probleem met de stijlbestanden terug op kale HTML, zodat een foutpagina zelf nooit een fout geeft.

- **Tests** (nu 321): bakken (oppakken, toewijzen met e-mail, terugleggen met en zonder bericht, afgehandeld blijft staan, alleen redacteuren van de omgeving, overnemen in de geschiedenis, filter per bak, "nog niet geopend"), de startpagina (inhoud, scheiding tussen omgevingen, vast aantal vragen), steun (dubbelklik, eigen, afgehandeld, onzichtbare artikelen, geen namen in de lijst van collega's, anonimisering), de foutpagina's, en de datamigratie. Vijf tests zijn ook tegen een bewust kapotte versie gedraaid om te zien dat ze erop vallen.

## 1.14.2 – 2026-11-10

- **Gebruiksstatistieken: twee schuifbalken.** Naast het middenstuk schoof ook de hele pagina, inclusief de bovenbalk. De oorzaak was een onzichtbaar label voor schermlezers in de tabelkop ("Verhouding"). Dat hing aan de pagina in plaats van aan het middenstuk en maakte de pagina zo langer dan het scherm. Gemeld door Alex. De zijbalk en het middenstuk zijn nu het ankerpunt voor zulke labels, zodat dit ook op andere pagina's niet meer kan gebeuren.

## 1.14.1 – 2026-11-10

Drie verbeteringen uit de stresstest van 9 november (S2, S3, S5).

- **Grote artikelen vol tabellen konden niet worden opgeslagen.** De browser codeert de tekst bij het versturen, waardoor die groeit: ×1,35 bij inhoud uit Word, maar ×1,6 bij een artikel dat vooral uit tabellen bestaat. Zo'n artikel op de maximale omvang (4 MB) werd 6,4 MB, boven de grens van 6 MB, en Django weigerde het met een kale foutpagina nog vóórdat de kennisbank de nette melding "dit artikel is te groot" kon geven. Ook de kladversie van zo'n artikel kwam niet aan. **`KB_MAX_VERZOEK_MB` staat nu standaard op 8.** Dat is nog altijd zuiniger dan de 12 van vóór 1.13.0.
- **Waarschuwing bij een te lage grens.** `manage.py check` en `migrate` melden `kennisbank.W001` als `KB_MAX_VERZOEK_MB` te laag staat voor de grootste toegestane artikelen, met het advies in gewoon Nederlands. De statuspagina toont de grens met dezelfde controle. In de documentatie stond "net boven de 4 MB", en dat was precies de valkuil.
- **Beheer: verbetervoorstellen** haalde de indiener per rij apart op: 106 databasevragen voor één pagina. Nu 6. Gemeten bij 3000 artikelen en 1200 voorstellen: van 172 naar 54 ms.
- **Beheer: artikelenlijst voor een redacteur** zocht zijn rechten bij elke controle op het scherm opnieuw op (filters, acties, knoppen): 31 keer per pagina. Er bestond al een geheugen per verzoek (`rechten(request)`), maar op vier plekken in het beheer werd daar omheen gewerkt. Van 44 naar 14 vragen, van 110 naar 69 ms. In het stresstestrapport stond dit als "een vraag per rij"; dat klopte niet, het was een vast pakket per pagina.
- **Beheer: nieuwsberichten** haalde de schrijver per rij op. Gevonden bij het nalopen van alle beheerlijsten; zelfde soort reparatie.

- **Tests** (nu 283): elke beheerlijst met weinig en met veel rijen moet hetzelfde aantal vragen doen; de rechten van een redacteur mogen per verzoek hooguit één keer worden opgezocht; en een artikel van 4 MB vol tabellen moet door het formulier én de kladversie komen, verstuurd zoals de browser het doet. Alle nieuwe tests zijn ook tegen de oude code gedraaid om te zien dat ze erop vallen. Twee deden dat eerst niet, en daar zat telkens iets achter: de artikelenlijst bleek geen probleem per rij te hebben maar per pagina, en de testclient verstuurde het formulier anders dan de browser.

## 1.14.0 – 2026-11-09

Ronde 6, deel 1: **kladversies** (punt 36). Een verlopen sessie, een vastgelopen browser, een dichtgeklapte laptop of een verbroken verbinding kost een redacteur geen werk meer.

**Hoe het werkt**

- **Twee lagen.** De browser bewaart elke paar seconden een kopie (`localStorage`), ook zonder verbinding. De server krijgt de kladversie elke twee minuten als er iets is veranderd, meteen als de verbinding terugkomt, en bij het sluiten of wegklikken van het tabblad (`sendBeacon`). Rechtsonder verschijnt kort *"Kladversie opgeslagen om 14:32"*; valt de verbinding weg, dan zegt de melding dat het werk in de browser wordt bewaard.
- **Terugkomen.** Staat er een kladversie die afwijkt van het formulier, dan vraagt het scherm *"Verder gaan waar je gebleven was?"*, met de titel en het begin van de tekst. De nieuwste van browser- en serverkopie wint. Ook voor een nieuw artikel dat nog nooit is opgeslagen.
- **Na het inloggen** toont de kennisbank één keer per sessie de kladversies die nog openstaan, ná het welkomstvenster als dat er ook is. In het beheer staat het aantal boven de artikelenlijst, en onder **Kladversies** staan ze allemaal.
- **Collega's** in dezelfde omgeving zien dát iemand een kladversie heeft en kunnen hem lezen, zodat werk over te nemen is als iemand ziek is. Redacteuren van een andere omgeving zien niets (404, ook niet dat hij bestaat). De tekst gaat bij het lezen door dezelfde schoonmaak als een gepubliceerd artikel.
- **De melding "dit scherm is verlopen"** zei "kopieer je tekst en plak hem terug". Nu: je werk staat veilig in deze browser, ververs de pagina en kies Verder gaan.

**Wat ervoor zorgt dat het niet misgaat**

- **Terugzetten zet ook het oude stempel terug.** Heeft een collega het artikel intussen opgeslagen, dan waarschuwt de vraag daar al voor, en geeft opslaan de bekende conflictmelding in plaats van dat diens werk ongemerkt wordt overschreven. Zonder dit zou de conflictcontrole blind zijn geweest voor een teruggezette kladversie.
- **Na opslaan of weggooien blijft er een lege, afgesloten rij staan.** Zonder die markering zou een oude browserkopie op een andere laptop de kladversie later laten herrijzen, en kreeg je "verder gaan?" voor werk dat allang is opgeslagen. De markering wordt ook gemaakt als er nooit een serverkopie was, want de browser kan er al wel een hebben.
- **Alleen openen is geen kladversie.** De editor maakt HTML na het laden soms net anders op; pas als iemand typt, plakt, de werkbalk gebruikt of een keuzelijst verandert, begint het bewaren.
- **Publicatiekeuzes worden niet bewaard** (status, toelichting, kleine correctie): die horen bij het moment van opslaan, niet bij het schrijfwerk.
- `opschonen` ruimt kladversies ouder dan `KB_KLADVERSIE_DAGEN` (standaard 30) op.

**Gevonden tijdens het testen in de browser**

- Het seintje na het inloggen bleef weg bij een redacteur die de app nog nooit had geopend: het welkomstvenster had voorrang en het seintje werd overgeslagen. De aanname "wie voor het eerst inlogt, heeft nog geen kladversies" klopte niet: een redacteur kan rechtstreeks in het beheer beginnen. Het seintje komt nu ná het welkomstvenster.
- De lijst *Kladversies* onthield in de eerste opzet op het gedeelde beheerobject wie er keek. Bij twee redacteuren tegelijk kon de een dan de knoppen van de ander zien. Nu per rij in de database berekend.

- **Tests** (nu 273): twintig voor de kladversie aan de serverkant (opslaan, één rij bij twee keer opslaan, onbekende velden, rechten voor collega, vreemde redacteur en lezer, de schoonmaak bij het lezen, nieuw artikel met en zonder eigen omgeving, afsluiten na opslaan en na weggooien, de markering zonder serverkopie, opruimen, het seintje). De schoonmaaktest is eerst zonder de reparatie gelopen om te zien dat hij er echt op valt. Daarnaast tien scenario's in de browser: alleen openen, typen, verbinding weg en terug, tabblad dicht zonder opslaan, terugkomen, een collega die meeleest, een collega die tussendoor opslaat (met echte conflictmelding), opslaan, nieuw artikel, en het seintje in de app.

## 1.13.1 – 2026-11-08

Drie aanpassingen aan de nieuwspagina, op verzoek.

- **Een bericht is net zo breed als een artikel.** De berichtkaart stond op een eigen, smallere maat (80 tekens); hij volgt nu dezelfde leeskolom als een artikel, met dezelfde marge. De tekst erin loopt mee.
- **Het nieuws op de startpagina verdwijnt zodra je het hebt gelezen.** Boven *Recent bezocht* en *Alle artikelen* stond het laatste nieuws permanent; nu staat er alleen wat deze medewerker nog niet heeft gezien, onder de kop "Nieuw sinds je laatste bezoek". Heeft hij de nieuwspagina bekeken, dan is het blok weg. Anders zou dezelfde mededeling eindeloos op twee plekken staan en zou een aparte nieuwspagina geen doel meer dienen.
- **In de zijbalk staan op de nieuwspagina de koppen van de berichten** (de laatste zes, met datum), in plaats van de filters voor cluster, soort en onderwerp — dat zijn artikelfilters en op die pagina zeggen ze niets. Klikken springt naar het bericht; staat het onder *Ouder nieuws*, dan klapt dat eerst open.

## 1.13.0 – 2026-11-08

Veegronde: alle resterende punten uit de review van 8 november. Daarmee is de reviewlijst leeg — er staat niets meer open uit een review of hardingstest sinds 1.7.0.

**Merkbaar voor medewerkers**

- **De assistent geeft niet meer op bij een lege eerste bron.** Vond hij het beste artikel maar lukte het niet er een citaat uit te halen (een sectie zonder lopende tekst, bijvoorbeeld alleen een tabel), dan antwoordde hij "Ik vond hier geen antwoord op" terwijl het antwoord in het tweede artikel stond. Hij loopt de bronnen nu af tot er een citaat uitkomt.
- **De melding bij gemiste wijzigingen noemt het juiste aantal.** Wie er zeven had gemist, las "Er zijn 5 wijzigingen" — dat was het aantal dat eronder paste, niet het aantal dat er was. Er staat nu het echte aantal, met "de 5 nieuwste staan hieronder" als de lijst is ingekort.
- **De pagina na een verlopen formulier werkt zonder JavaScript.** De enige knop gebruikte `onclick`, en dat blokkeert het beveiligingsbeleid buiten het beheer. Je kreeg dus een pagina met een knop die niets deed. Nu staan er twee gewone links, en de tekst wijst op de terugknop van de browser.

**Techniek en beheer**

- **De voorstellenlijst doet een vast aantal queries.** Per voorstel werd geteld hoeveel berichten ongelezen waren — bij driehonderd voorstellen dus driehonderd extra queries. Dat telt nu mee in wat al was opgehaald: gemeten 7 queries bij 1, 5, 20 en 50 voorstellen (was 12 bij één en 31 bij twintig).
- **Index op "opnieuw nakijken"** (`Artikel(status, herzien_voor)`, migratie 0021). De lijst en het aantal in de banner lazen de hele artikeltabel.
- **E-mail gaat pas weg als de wijziging is opgeslagen.** Liep een opslag halverwege vast, dan was de mail er al: een collega kreeg bericht over een terugkoppeling die niet in de database stond. Het verzenden hangt nu aan het doorvoeren van de transactie.
- **Geen e-mailadres meer in het logboek.** Bij een mislukte verzending werd de volledige traceback weggeschreven, en bij een geweigerde ontvanger staat het adres daarin. Nu alleen het soort fout en het aantal ontvangers. Wie in het logboek op een adres zocht om een verzendprobleem te vinden, moet dat vanaf nu anders doen.
- **De slug van een artikel kijkt niet meer over omgevingen heen.** Bestond dezelfde titel in een andere afdeling, dan kreeg het nieuwe artikel `-2` achter zijn adres; daaruit kon een redacteur afleiden dat er elders een artikel met die titel bestond, terwijl hij die omgeving niet mag zien. Binnen een omgeving blijft de slug uniek, en het zoeken ernaar kost nu één query in plaats van één per poging.
- **Dubbele titels worden ook met rare witruimte gevonden.** Het slot normaliseerde dubbele spaties weg, de controle eronder niet — "Melding    registreren" glipte langs "Melding registreren".
- **De statuspagina vertelt wat de laatste opschoonronde heeft gedaan** (aantal verstuurde favorietenmails, opgeruimde regels) in plaats van alleen dat hij heeft gelopen. Die uitkomst werd al vastgelegd en werd nergens uitgelezen.
- **`KB_MAX_VERZOEK_MB`** (standaard 6) maakt de maximale grootte van een verzoek instelbaar. Bij het importeren van een zeer groot Word-document liep je anders tegen een vaste grens aan die niet in de configuratie stond. Zie [configuratie](docs/configuratie.md).

**Bewust zo gelaten, nu opgeschreven**

"Gelezen" bij een verbetervoorstel is één stempel voor de hele redactie: opent de ene redacteur het voorstel, dan is het stipje ook bij de ander weg. Dat blijft zo — het is een teampostvak, zoals een gedeeld postvak in Outlook. Per persoon bijhouden zou een nieuwe collega bij binnenkomst elk voorstel van de afgelopen jaren als ongelezen tonen, en sinds het gesprek eenrichting is komt er aan de redactiekant na het eerste bericht niets meer binnen. Wie het heeft opgepakt staat bij *Behandeld door*. De keuze staat nu in de code, in [functioneel beheer](docs/functioneel-beheer.md) en in een test, zodat een wijziging hierin een besluit is en geen ongeluk.

- **Tests** (nu 235): tien nieuwe, waaronder de query-meting op de voorstellenlijst bij 1, 5, 20 en 50 voorstellen, de slug over omgevingen heen, de mail die wacht op de commit, het logboek zonder adres, en het teampostvak. De test voor de lege bron is eerst zonder de reparatie gelopen om te controleren dat hij er echt op valt.

## 1.12.0 – 2026-11-08

Ronde 5: de laatste bevindingen uit de functionele review en de hardingstests, plus de kleine punten uit de review van vandaag. Hiermee is die lijst leeg.

**Voor medewerkers**

- **Filteren op onderwerp.** Tags waren wel te zien bij een artikel, maar niet te gebruiken als filter vanaf het overzicht. In de zijbalk staat nu **Onderwerp** naast cluster en soort. Onderwerpen zijn te combineren — een artikel moet dan aan alle gekozen onderwerpen voldoen — en alleen onderwerpen die in zichtbare artikelen voorkomen worden aangeboden, dus een filter levert nooit nul resultaten op. Bij meer dan twaalf staat de rest achter *Toon alle*.
- **Bij de eerste keer inloggen** vraagt de kennisbank of je nieuw bent bij Rijkswaterstaat of bij deze afdeling. Zeg je ja, dan staat de extra uitleg voor nieuwe collega's meteen aan — anders moet je die schakelaar eerst zelf vinden, en dat doet bijna niemand. De vraag komt één keer, ook als je nee zegt. In het zaaksysteem wordt hij niet gesteld.
- **Zonder JavaScript** bleef de kennisbank eindeloos op "Laden…" staan, zonder uitleg. Er staat nu een `<noscript>`-melding met wat er aan de hand is en waar je terechtkunt.

**Voor procesmanagement en beheer**

- **Tegel "vragen zonder bron"** in de statistieken: hoe vaak de assistent in de kennisbank niets kon vinden om op te antwoorden, met het percentage. Samen met "gezocht zonder resultaat" is dat de beste aanwijzing voor welke kennis nog ontbreekt. De vragen zelf worden nog steeds niet opgeslagen.
- **Sjablonen** (*Beheer → Sjablonen*, alleen beheerders) en de actie **Vullen met de sjablonen** bij een omgeving. Een lege kennisbank is het grootste risico bij invoering: de eerste medewerker vindt niets en de eerste redacteur weet niet hoe een goed artikel eruitziet. De sjablonen worden als **concept** geplaatst en een titel die er al staat wordt overgeslagen. De inhoud wordt bewust niet meegeleverd: die hoort van de organisatie zelf te komen.
- **Dubbelklikken levert geen dubbel voorstel en geen dubbel bericht meer op**, ook niet bij exact gelijktijdige verzoeken (adviesslot op dezelfde tekst van dezelfde persoon, net als bij het aanmaken van een artikel). Een tweede identiek voorstel krijgt het eerste terug in plaats van een foutmelding, en de indiener krijgt één e-mail in plaats van twee.
- **Je ziet wie een voorstel heeft opgepakt.** Twee redacteuren die tegelijk een status zetten, gingen allebei van de oude stand uit; dat is nu vergrendeld, en bij het voorstel staat "Opgepakt door … op …". Zonder dat kon de indiener twee antwoorden krijgen die elkaar tegenspraken.
- **De clusterlijst is afgeschermd.** `/api/v1/keuzelijsten` filterde tags en zaaktypen wel op zichtbare artikelen, maar clusters niet — een account zonder enige omgevingstoegang kreeg zo de volledige clusterindeling van de organisatie.
- **Nederlandse melding bij te veel verzoeken.** De vertaling van Django REST Framework maakte van "throttled" het woord "verstikt" en liet de tweede helft Engels. Er staat nu "Je hebt dit de afgelopen tijd vaak gedaan. Probeer het over 2 minuten opnieuw."
- **Nederlandse meervouden in het beheer**: "profiels", "zaaktypes", "favoriets" en "zoek tellings" zijn nu profielen, zaaktypen, favorieten en zoektellingen (migratie 0018, raakt alleen wat er op het scherm staat).

**Kleine reparaties uit de review van vandaag**

- Het **`SECTIEKOP`-lek**: een sectiekop zonder afsluitende tag liet de interne markering als het woord "SECTIEKOP" in de tekst achter.
- **"Markeren als nagekeken"** sloeg concepten niet over, waardoor het eerste herzieningsvenster na publicatie korter was dan ingesteld.
- De Word-keuze **"eerste rij als koprij"** schreef een onbruikbaar `scope`-attribuut weg (letterlijke backslashes), wat een schermlezer de kolomrelatie kostte. En bij een **geneste tabel** kreeg de binnenste tabel ook een koprij; die laat de import nu met rust.
- Een **absurde herzieningstermijn** (`KB_HERZIENINGSTERMIJN_MAANDEN=100000`) gaf een serverfout bij het publiceren omdat het jaartal buiten bereik viel.
- Het **telverschil bij overgeslagen afbeeldingen**: de melding noemde drie afbeeldingen waar vier markeringen in de tekst stonden. Nu wordt geteld wat er daadwerkelijk in de tekst komt.

**Gevonden tijdens deze ronde**

Het Omgevingen-overzicht in het beheer gaf sinds 1.10.0 een serverfout: de nieuwe kolom met het aantal artikelen gebruikte `Count("artikel")` terwijl de relatie `artikelen` heet. Geen test, geen browsercontrole en geen van beide reviews had dat scherm geopend. Daarom is er nu een rooktest die **elk** beheerscherm en elk toevoegscherm één keer opent — de goedkoopste test in de hele suite, en precies het gat waardoor dit erdoor glipte.

- **Tests** (nu 221): het tagfilter, de begroeting bij de eerste inlog, de sjablonen (plaatsen, twee keer plaatsen, zonder sjablonen, rechten), dubbelklik op een voorstel en op een bericht (ook echt gelijktijdig, met threads), de afgeschermde clusterlijst, de Nederlandse 429-tekst, de meervouden, en de vijf kleine reparaties hierboven.

Nog open uit de review van vandaag, meegenomen naar een volgende veegronde: de voorstellenlijst doet één query per voorstel, de assistent kijkt niet naar de volgende bron als het eerste citaat leeg is, "gelezen" is één vlag voor alle redacteuren samen, en een reeks kleinere punten. Zie `claude/openstaande-punten.md` in het project.

## 1.11.0 – 2026-11-08

Reparaties na een onafhankelijke technische review en een eigen hardingstest over alles sinds 1.7.0. Beide rapporten wezen het gesprek bij verbetervoorstellen uit 1.10.0 aan als het zwakste onderdeel; dat is hier rechtgezet en tegelijk vereenvoudigd.

- **De bewaartermijn op de naam van de indiener werkt weer.** `opschonen` wiste na een jaar alleen de naam op het voorstel zelf. De berichten die sinds 1.10.0 bij een voorstel horen hebben hun eigen auteur, en die bleef staan: het voorstel zei "Onbekend (geanonimiseerd)" terwijl het bericht eronder nog de volledige naam toonde. De anonimisering was daarmee cosmetisch, en `docs/beveiliging-en-privacy.md` beloofde het tegenovergestelde. Nu gaan beide plekken mee. De naam van de redacteur die heeft teruggekoppeld blijft staan zolang het voorstel bestaat — dat is verantwoording voor wat er aan een collega is toegezegd — en die keuze staat nu expliciet in de privacydocumentatie in plaats van dat hij per ongeluk zo uitkwam. Ook belangrijk: `behandeld_op` wordt alleen nog bij een statuswijziging gezet, zodat een tussentijdse update de bewaartermijn niet meer opschuift.
- **Terugkoppelen gaat nu via één kanaal, en de terugkoppeling kan niet meer verdwijnen.** Vulde je in het beheerscherm het veld *Terugkoppeling* in én schreef je er een bericht bij, dan was die terugkoppeling na het opslaan uit de database verdwenen — zonder melding. Het losse veld is weg; de terugkoppeling is nu afgeleid uit het laatste bericht van procesmanagement, en `diensten.voorstelbericht_toevoegen` is de enige schrijver. Migratie 0017 maakt van elke bestaande terugkoppeling een bericht, zodat een medewerker die vóór de upgrade antwoord kreeg dat blijft zien.
- **Het gesprek is bewust eenrichtingsverkeer geworden.** De medewerker dient een voorstel in; procesmanagement koppelt terug en houdt hem op de hoogte. Terugschrijven in de kennisbank kan niet meer. Een gesprek heen en weer zou een tweede kanaal naast Teams en e-mail opleveren en de verwachting wekken dat er altijd iemand meeleest. Daarmee vervalt ook de stille fout dat een antwoord van de indiener bij niemand aankwam zolang nog geen redacteur het voorstel had opgepakt.
- **Een nul-byte in een bericht geeft een nette melding in plaats van een serverfout.** Dit was het enige schrijvende endpoint dat de invoer rauw uit het verzoek haalde, zonder serializer; PostgreSQL accepteert dat teken niet in een tekstkolom. Er zit nu een serializer voor, wat tegelijk de 500 op een getal, lijst of boolean wegneemt en de lengtegrens op één plek zet (`MAX_VOORSTELBERICHT` in het model).
- **De publicatiecontrole geldt nu ook voor de lijstactie.** De controle uit 1.9.0 zat in het bewerkformulier; de lijstactie *Publiceren* kwam daar niet langs. Een artikel met de titel `werkinstructie DEFINITIEF.docx`, de samenvatting `n.v.t.` en een sectie zonder titel was via de lijst dus gewoon te publiceren. De regel staat nu in `diensten.problemen_eerste_publicatie` en wordt vanuit beide routes aangeroepen; de actie meldt per artikel wat er nog aan moet gebeuren, met een link naar het bewerkscherm.
- **Het upgradehoofdstuk klopt weer.** Dat heette eerder "Upgraden naar 1.7.0" en er was alleen het versienummer vervangen, waardoor een beheerder las dat zijn wijzigingsgeschiedenis bij de upgrade zou worden afgevinkt. Er staat nu per versie wat er met bestaande gegevens gebeurt, inclusief de enige migratie die rijen verwijdert (0011, afgeleide gegevens) en de nieuwe backfill.
- **Tests** (nu 193): de anonimisering op alle plekken waar een naam staat, de nul-byte en onzin-invoer, dat een bericht niets overschrijft, dat de indiener niet kan terugschrijven, dat een tussentijds bericht de bewaartermijn niet opschuift, de publicatiecontrole via de lijstactie, en een migratietest over 0010 t/m 0017 — die laatste ontbrak, waardoor de enige verwijderende migratie geen test had.

Nog open uit deze review, meegenomen naar de volgende ronde: de voorstellenlijst doet één query per voorstel, de assistent kijkt niet naar de volgende bron als het eerste citaat leeg is, dubbelklikken levert twee identieke berichten, en een reeks kleinere punten (geen index op de herzieningsdatum, e-mail binnen de transactie, de knop op de CSRF-pagina, de slug-dedup over omgevingen heen). Zie `claude/openstaande-punten.md` in het project.

## 1.10.0 – 2026-11-08

Vierde ronde: de kant van de beheerder, en voorstellen die een gesprek worden in plaats van een eenmalig antwoord.

- **Statuspagina voor de functioneel beheerder** (*Beheer → Status*). Per onderdeel een stoplicht met wat er gemeten is en, als iets niet goed staat, wat eraan te doen is: versie en instellingen, database en openstaande migraties, zoekindex, e-mail en de wachtrij, assistent en daglimiet, de geplande taak, toegang en inhoud. Hiermee zijn de dingen die anders stil kapot gaan in één oogopslag te zien: een cron die niet meer draait, secties zonder zoekdocument, een omgeving waar geen enkele groep aan hangt. De onderhoudscommando's leggen nu vast wanneer ze liepen, zodat "de geplande taak staat niet aan" ook echt opvalt.
- **Groepen uit Entra ID krijgen een leesbare naam.** De groepen-claim bevat bij RWS vaak object-id's, dus een beheerder die toegang regelde, koos uit een lijst GUID's. Bij *Groepen* staat nu per groep hoeveel mensen ermee hebben ingelogd en tot welke omgevingen hij toegang geeft, en kan hij er de naam uit Entra ID bij zetten. Die naam wordt daarna overal gebruikt; de code blijft er grijs bij staan om te vergelijken.
- **Opnieuw nakijken voor.** Elk gepubliceerd artikel heeft een herzieningsdatum, bij publiceren automatisch gevuld volgens `KB_HERZIENINGSTERMIJN_MAANDEN` (standaard twaalf maanden, `0` = uit). De artikelenlijst heeft een kolom met kleur, een filter en een melding bovenaan als er artikelen over de datum zijn. Klopt een artikel nog? Dan schuift de actie *Markeren als nagekeken* de datum vooruit zonder nieuwe versie en zonder melding bij medewerkers. Publiceren schuift de datum ook mee — dat is immers het moment van nakijken — maar een kleine correctie niet. Medewerkers zien de datum niet; het is een hulpmiddel voor procesmanagement.
- **Verbetervoorstellen zijn een gesprek geworden.** Procesmanagement kon één terugkoppeling geven en daarmee was het klaar, dus een voorstel dat in behandeling was, leek maanden stil te liggen. Nu kunnen beide kanten berichten sturen: elk bericht van procesmanagement komt bij de indiener binnen als melding in de kennisbank en als e-mail, en hij kan erop antwoorden. De indiener ziet hoeveel berichten nieuw voor hem zijn; procesmanagement ziet in de lijst hoeveel er is gewisseld en kan filteren op *Indiener heeft als laatste geschreven*. Het invoervak voor een voorstel is bovendien twee keer zo groot, en de voorstellenlijst heeft filters op status.
- **Keuzelijsten opruimen.** Bij clusters, tags en zaaktypen staat hoeveel artikelen het item gebruiken, met een filter *Nergens gebruikt* en een actie die precies die items verwijdert; wat nog in gebruik is, wordt overgeslagen en bij naam genoemd. Alleen een functioneel beheerder kan opruimen. Bij *Omgevingen* staat nu ook hoeveel groepen en artikelen eraan hangen.
- **Tests** (nu 180): de herzieningsdatum (vullen, meeschuiven, kleine correctie, actie, niet zichtbaar voor medewerkers), de statuspagina inclusief een controle die zelf stuklopen mag, de groepsnamen, het opruimen van keuzelijsten, en het gesprek bij een voorstel (meerdere updates, melding per bericht, rechten, grenzen). Daarnaast een browsercontrole van alle zes punten.
- **Gevonden tijdens die browsercontrole**, en meteen opgelost: de inline met het gesprek werd voor een redacteur helemaal weggelaten (de rechten komen uit zijn omgevingen, niet uit de Django-rechtentabel), en berichten werden als gelezen gemarkeerd terwijl de medewerker naar de artikelenlijst keek.

## 1.9.0 – 2026-11-08

Derde ronde na de beoordelingen, en deze keer helemaal aan de kant van de redacteur: van een Word-document naar een artikel dat af is, en van "er is iets gewijzigd" naar "dit is er gewijzigd".

- **De knop *Sectie* neemt de kop over die je selecteert.** Begon je selectie met een kop — na een Word-import is dat bijna altijd zo — dan kreeg je een sectie met een lege titel en diezelfde kop er nog eens ín. Voor de lezer heette dat kader dan "Sectie 1". Nu wordt die kop de titel van de sectie en verdwijnt hij uit de tekst. De knop zelf werkt onveranderd: er ontstaat alleen een sectie als jij erop drukt.
- **Een laatste controle bij de eerste publicatie.** Een artikel dat voor het eerst zichtbaar wordt voor medewerkers, wordt geweigerd als de titel een bestandsnaam of versie-aanduiding is, als de samenvatting leeg of nietszeggend is, of als er een sectie zonder titel in staat — met per geval de uitleg wat eraan moet gebeuren. Ontbreekt er alleen een zaaktype of tag, dan volgt een waarschuwing en gaat de publicatie door: slecht vindbaar is soms de bedoeling. Een al gepubliceerd artikel wordt niet opnieuw gekeurd, zodat een typfout altijd te herstellen blijft.
- **De tekst van een eerdere versie is terug te lezen.** In de versiegeschiedenis staat bij elke regel "Tekst bekijken". Dat opent de opgeslagen momentopname van die versie, zoals medewerkers hem toen zagen — niet de tekst van vandaag. Dat is precies waar de versiegeschiedenis voor bedoeld was.
- **Wie meerdere wijzigingen miste, ziet ze allemaal.** Na een vakantie van drie weken toonde de melding alleen de laatste wijziging; de twee daarvoor waren weg. Nu staat de nieuwste bovenaan met de eerder gemiste eronder (maximaal vier), en vinkt één keer "Ik snap het" ze samen af.
- **Afdrukken of opslaan als PDF.** Een knop in het artikel klapt alle secties open, zet er een regel met titel, versienummer, afdrukdatum en webadres onder, en opent het printvenster van de browser. Daar kiest de medewerker zelf "Opslaan als PDF". Op papier vallen zijbalk, knoppen en meldingen weg en worden de sectiekaders gewone koppen met tekst eronder. Bewust geen PDF-bouwer op de server: niets extra's om te beheren, en de afdruk komt altijd uit de tekst van nu.
- **Twee keuzes bij de Word-import, standaard uit.** "Gebruik de eerste kop in het document als titel" en "Eerste rij van een tabel als koprij". Beide staan standaard uit, want de opmaak in een Word-document zegt niet betrouwbaar wat de bedoeling was; je laatste keuze staat de volgende keer alvast goed. Vind je geen kop om als titel te gebruiken, dan blijft de bestandsnaam de titel en meldt de import dat.
- **Tests** (nu 143): de controle bij de eerste publicatie, het terugkijken van een versie inclusief de rechten per omgeving, meerdere gemiste wijzigingen, en de twee importkeuzes. Daarnaast een browsercontrole van de sectieknop, de printknop en de meldingen.

## 1.8.1 – 2026-11-08

Tweede ronde na de functionele review: de dingen die in een demo of bij invoering het eerst misgaan.

- **De assistent beweert niets meer wat hij niet kan laten zien.** Elk artikel kreeg een lege sectierij voor de tekst vóór de eerste sectiekop, ook als die tekst er niet was. Zo'n lege rij droeg in zijn zoekdocument wél de artikeltitel en won daardoor regelmatig de zoekopdracht; de assistent antwoordde dan met "Dit staat in … onder het kopje :" gevolgd door niets. Die rijen worden niet meer aangemaakt, een bestaande installatie ruimt ze op bij het bijwerken (migratie 0011), lege secties tellen niet meer mee bij het zoeken, en bij een leeg citaat zegt de assistent voortaan dat hij geen antwoord heeft gevonden. Een sectie zonder kop heet in het antwoord "Inleiding".
- **Geen toegang ziet er niet meer uit als een lege kennisbank.** Wie nog niet aan een omgeving is gekoppeld, kreeg een normale kennisbank te zien met de tekst "Geen artikelen gevonden. Probeer een ander trefwoord" — de meest voorkomende en minst herkenbare melding bij invoering. Nu volgt een eigen scherm met uitleg en een contactadres.
- **Nieuwe instelling `KB_CONTACT`**: waar medewerkers terechtkunnen met vragen. Verschijnt in de zijbalk onder "Hulp" en op het scherm hierboven.
- **In het zaaksysteem is zoeken geen doodlopende weg meer.** De zijbalk is daar verborgen, dus na één zoekactie kwam je niet meer terug bij de artikelen van de zaak. Er staat nu een vaste knop "← Artikelen bij …" boven het paneel, en het zoekveld leegmaken brengt je er ook terug.
- **Het zaaksysteem-paneel schaalt mee.** Bij een breed zaaktype stonden alle artikelen alfabetisch onder elkaar — bij 49 artikelen een lijst van ruim vierduizend pixels naast een zaak. Nu staan de acht meest geraadpleegde artikelen van de laatste 90 dagen bovenaan, met "Toon alle N artikelen" eronder.
- **Tests** (nu 122): lege secties, antwoorden van de assistent, het scherm bij geen toegang, en de volgorde van het zaaktype-paneel.

## 1.8.0 – 2026-11-08

Eerste ronde na twee onafhankelijke beoordelingen (een functionele review en twee hardingstests). Deze versie gaat volledig over gegevensintegriteit: niemand mag stilletjes het werk van een ander overschrijven, en een verkeerd teken in een webadres mag de kennisbank niet laten omvallen.

- **Archiveren werkt de wijzigingsdatum bij.** De lijstactie gebruikte een bulk-update, waardoor de wijzigingsdatum ongemoeid bleef. Een redacteur met een openstaand bewerkscherm zette een zojuist gearchiveerd artikel daarmee ongemerkt weer online. Gaat nu per artikel, zoals publiceren al deed.
- **Gelijktijdig opslaan wordt echt tegengehouden.** De controle op tussentijdse wijzigingen las de huidige stand zonder vergrendeling. Sloegen twee redacteuren binnen enkele tientallen milliseconden op, dan kwamen ze er allebei doorheen en verdween het werk van één van beiden zonder melding. Het artikel wordt nu vergrendeld vóór de controle, binnen dezelfde transactie als het schrijven.
- **Een ontbrekend stempel geldt als conflict.** Een leeg verborgen veld sloeg de hele controle over; hij faalde dus "open". Nu wordt zo'n opslag geweigerd met de uitleg dat het scherm niet te controleren was en dat de tekst nog in het scherm staat.
- **Publiceren via de lijstactie eist dezelfde toelichting** als het bewerkscherm. Via concept + lijstactie kon een inhoudelijke wijziging anders bij alle medewerkers binnenkomen met de melding "Gepubliceerd via lijstactie". De actie meldt nu hoeveel artikelen zijn overgeslagen en waarom.
- **Dubbelklikken op "artikel toevoegen" maakt geen dubbele artikelen meer** (ook niet bij exact gelijktijdige verzoeken, dankzij een adviesslot op titel en omgeving), en artikelen met dezelfde titel krijgen elk een eigen webadres. Oude links naar een artikel verwijzen weer door in plaats van een 404 te geven.
- **Een nul-byte in een webadres geeft een nette 400** in plaats van een serverfout. `?tag=%00` en varianten lieten de database afbreken.
- **Een tag die alleen in schrijfwijze verschilt** van een bestaande (`Rappel` naast `rappel`) geeft een nette melding in plaats van een serverfout; de naam wordt nu genormaliseerd vóór de controle op dubbelen.
- **Een te groot artikel** levert een Nederlandse melding in het formulier op (grens 4 MB) in plaats van een kale Engelse foutpagina waarbij alle tekst verloren ging.
- **Tagveld met echte suggesties.** De oude lijst van de browser vergeleek de hele regel, dus na de eerste komma matchte er niets meer. Nu een eigen lijstje dat opengaat zodra je in het veld klikt, de meest gebruikte tags bovenaan zet, matcht op elk deel van een woord, en al gekozen tags weglaat. De tagbeheerlijst toont hoe vaak elke tag wordt gebruikt.
- **Tests** (nu 114): gelijktijdig opslaan, archiveren, ontbrekend stempel, dubbele titel, lijstactie publiceren, nul-bytes en tagnamen.

## 1.7.1 – 2026-11-08

Samen in één artikel werken zonder elkaars werk kwijt te raken, en opslaan dat nooit stilletjes mislukt.

- **Zacht slot bij bewerken.** Open je een artikel dat een collega op dat moment ook open heeft, dan verschijnt een venster met zijn naam en vanaf hoe laat, met de keuze *Toch bewerken* of *Terug naar de lijst*. Zit je er al in en komt er iemand bij, dan verschijnt bovenin *"Let op: … heeft dit artikel zojuist ook geopend."* Bewust geen hard slot: dat levert vooral sloten op die blijven hangen. De claim wordt elke 30 seconden verlengd en vervalt na twee minuten; `kennisbank_opschonen` ruimt restanten op.
- **Opslaan overschrijft niemand meer stilletjes.** Is het artikel gewijzigd terwijl jouw scherm openstond, dan wordt de opslag geweigerd met de datum en de naam van wie het opsloeg. Je tekst blijft in het scherm staan, zodat je hem kunt overzetten.
- **Verlopen beveiligingscode** (meestal doordat je in een ander tabblad opnieuw inlogt) wordt nu in het bewerkscherm gemeld zodra het gebeurt, en levert bij opslaan een Nederlandse uitlegpagina op in plaats van het technische Django-scherm.
- **Volledig scherm vraagt om de toelichting.** Het veld staat op de pagina eronder, waardoor opslaan vanuit het volledige scherm kon mislukken op een melding die je niet zag. Nu verschijnt er een venster met het toelichtingsveld en het vinkje *Kleine correctie*, en daarna wordt alsnog opgeslagen.
- **Opmaak**: een artikel met een openstaande wijziging staat in de lijst op een licht gele kaart met een amberkleurige balk *Gewijzigd …* over de volle breedte boven de titel; de melding in het artikel zelf (met de toelichting) heeft dezelfde kleuren. De artikeltekst mag langer worden (90 tekens per regel in plaats van 70) en de artikelkolom is smaller, zodat tekst en kaart op elkaar aansluiten; tabellen mogen breder.
- Migratie `0010_zacht_slot`. **Tests** (nu 102): claims zien, vervallen en opruimen, rechten per omgeving op het claim-endpoint, conflict bij opslaan, en de eigen CSRF-pagina.

## 1.7.0 – 2026-11-08

Wijzigingsmeldingen en nieuws: medewerkers zien wat er is veranderd, en procesmanagement heeft één plek voor mededelingen.

- **Wijzigingsmelding bij een artikel.** Bij een inhoudelijke wijziging van een gepubliceerd artikel ziet de medewerker bovenaan het artikel *Gewijzigd op <datum> — <toelichting>* met de knop **Ik snap het**. De melding blijft staan tot hij is afgevinkt of tot de volgende wijziging. In de lijst staat het label *Gewijzigd*; nieuw menu-onderdeel **Gewijzigd** met teller en *alles als gezien markeren*. Geen meldingen voor wijzigingen van vóór de eerste inlog van de gebruiker, en niet voor versie 1 (de publicatie zelf).
- **Toelichting verplicht** bij een inhoudelijke wijziging van een gepubliceerd artikel; nieuw vinkje **Kleine correctie, geen melding** (typfout, opmaak) waarbij wel een versie ontstaat maar geen melding of e-mail. Versies tonen die vlag in de versiegeschiedenis.
- **E-mail aan favoriet-houders**: wie het artikel als favoriet heeft krijgt de toelichting per e-mail, standaard gebundeld tot één mail per dag per persoon (`KB_FAVORIETEN_MAIL`: `gebundeld`, `direct` of `uit`). Nieuw commando `kennisbank_favorietenmail`; `kennisbank_opschonen` roept het ook aan. Medewerkers kunnen de mail zelf uitzetten onder *Instellingen* in het menu. `KB_EMAIL_HOST=console` toont e-mails in de serverlog (test/demo).
- **Nieuws**: nieuwsberichten per omgeving met titel, opgemaakte tekst, gekoppelde artikelen, concept/gepubliceerd, vastpinnen en vervaldatum. Nieuw menu-onderdeel **Nieuws** met ongelezen-teller; de laatste berichten staan ook op de startpagina. Niet zichtbaar in het zaaksysteem (ingebed). Beheer onder *Nieuwsberichten*; de editor heeft daar alleen de opmaakknoppen.
- **Koppeling**: bij publiceren het vinkje **Ook als nieuwsbericht plaatsen** maakt een concept-bericht met de toelichting, gekoppeld aan het artikel.
- **API**: `wijziging` in artikel(lijst), `POST /artikelen/<id>/gezien`, `POST /wijzigingen/gezien`, `GET /berichten`, `POST /berichten/gezien`; `ik` geeft en accepteert `mail_bij_favorieten` en geeft `nieuws_ongelezen`.
- **Demo-inhoud**: een negende artikel zonder secties (korte werkafspraak), twee nieuwsberichten en één voorbeeldwijziging, zodat alle paden in de demo zichtbaar zijn en meelopen in de tests.
- **Tags** hebben nu overal dezelfde schrijfwijze (kleine letters), ook bij import; bestaande tags worden door migratie `0009` genormaliseerd en samengevoegd. Zonder dit zou een geïmporteerd artikel met een hoofdletter-tag bij de eerste opslag in het beheer ten onrechte als "inhoudelijk gewijzigd" tellen (bevinding uit de onafhankelijke review van deze ronde).
- **Import** (`kennisbank_import`) heeft `--kleine-correctie`; de documentatie vermeldt dat een import meldingen en e-mails veroorzaakt.
- **Robuustheid** (uit de review): een mislukte e-mail blijft in de wachtrij voor de volgende ronde en gelijktijdige runs sturen niet dubbel; ontvangers zonder leesrecht of bij een gearchiveerd artikel krijgen geen mail; "Ik snap het" vinkt af tot de versie die de gebruiker zag (niet een intussen gepubliceerde); nieuwsberichten worden ook bij tonen opgeschoond; een bericht dat terug naar concept gaat telt bij herpublicatie weer als nieuw.
- Migraties `0008_wijzigingen_en_nieuws` en `0009_bestaande_gegevens_1_7` (bestaande versies worden voor bestaande gebruikers als gezien gemarkeerd; zie [installatie-en-beheer](docs/installatie-en-beheer.md#naar-170-vanaf-een-oudere-versie)). **Tests** (nu 93): meldingen (verschijnen, afvinken, kleine correctie, eerste inlog, alles gezien, beheerformulier), favorietenmail (gebundeld, direct, uit, eigen voorkeur, opschonen), nieuws (rechten per omgeving, verlopen, ongelezen-teller, opschoning, beheer).

## 1.6.1 – 2026-11-08

- **Artikel zonder secties opende niet**: de kennisbank toonde "Er ging iets mis bij het laden" voor elk artikel zonder inklapbare sectie — dus ook voor elk artikel direct na een Word-import, dat bewust nog geen secties heeft. De oorzaak zat in de browser (de knop "Alles uitklappen" werd aangesloten terwijl hij er niet was); de server deed het goed. Zat erin sinds 1.3.0. Ververs na het bijwerken de pagina met Ctrl+F5.

## 1.6.0 – 2026-11-07

Derde ronde uit de onafhankelijke code-review: de kleinere punten en de ontbrekende tests.

- **Zoeken schaalt mee**: de zoekdocumenten staan opgeslagen (`tsvector` met GIN-index op artikel en sectie) en worden bij elke opslag bijgewerkt, in plaats van per zoekopdracht berekend. Migratie `0007_zoekvectoren` vult ze voor bestaande inhoud.
- **API-tokens verlopen** na `KB_API_TOKEN_MAX_DAGEN` (standaard een jaar); nieuw commando `beheer kennisbank_token <account>` maakt of vernieuwt een token (`--intrekken` trekt in). Een koppeling zonder geldig token krijgt een echte 401.
- **Opschonen** verwijdert ook verlopen sessies (`clearsessions`).
- **API-randjes**: een voorstel bij een onzichtbaar artikel geeft dezelfde fout als bij een onbestaand artikel; een voorstel behandelen dat niet van jouw omgeving is geeft 404; `?dagen=abc` geeft 400 in plaats van 500; `onboarding` in `PATCH /ik` wordt echt als ja/nee gelezen; `PATCH` op een voorstel mag alleen de status of alleen de terugkoppeling bevatten.
- **Inhoud**: kale `<div>`/`<span>` uit geplakte tekst worden uitgepakt en een onboarding-blok in een onboarding-blok wordt één blok, zodat onboarding-tekst nooit per ongeluk in het gewone antwoord of bij de assistent belandt. Sectietitels met `&` of `<` werden dubbel ge-escaped.
- **Frontend**: externe links in een artikel openen in een nieuw tabblad (ook in het zaaksysteem); voorbeeldvragen van de assistent alleen in de demo; de lengte van "recent bezocht" volgt `KB_RECENT_MAX`.
- **Import** weigert een ongeldige `slug` met een duidelijke melding. Een tag hernoemen of verwijderen in het beheer werkt direct door in de zoekindex.
- **OpenAPI** volledig getypeerd (`ik`, `keuzelijsten`, `versies`, `statistieken`).
- **Documentatie**: `KB_FORWARDED_ALLOW_IPS` met advies voor productie; tokenrotatie in [koppeling-zaaksysteem](docs/koppeling-zaaksysteem.md).
- **Tests** (nu 67): beheer weigert een andere omgeving, begrenzing van de assistent, geneste onboarding, tag hernoemen, tokenverloop, sessie-opschoning, slug-validatie, zoeken na upgrade.

## 1.5.0 – 2026-11-07

Tweede ronde reparaties uit de onafhankelijke code-review.

- **Rechten werken direct door.** Toegang tot het beheer (redacteur) volgt automatisch uit groepen en de regels onder *Toegang*; een wijziging daar geldt meteen, niet pas bij de volgende login. In OIDC-modus worden de rechten standaard elke 15 minuten stilletjes opnieuw bij de identity provider opgehaald (`KB_OIDC_HERNIEUW_SECONDEN`), zodat een geblokkeerd account of een gewijzigde groep niet tot het einde van de sessie doorwerkt.
- **Statistieken per omgeving.** Zoektermen en assistentgebruik worden per omgeving geteld; redacteuren zien alleen die van hun eigen omgeving(en). Bestaande tellingen worden bij de migratie aan de omgeving gekoppeld als er precies één is.
- **Assistent verhard.** Artikeltekst en zaaktype gaan als gemarkeerde gegevens in het gebruikersbericht naar het taalmodel (niet in de systeemprompt); links in het antwoord anders dan bronverwijzingen worden tekst; antwoordlengte begrensd (`KB_AI_MAX_TOKENS`); kostenplafond per dag voor de hele installatie (`KB_ASSISTENT_DAGLIMIET`, standaard 2000) met terugval op citeren. Kostenparagraaf in [docs/ai-assistent.md](docs/ai-assistent.md).
- **Migraties bevroren.** De inhoudsomzettingen van 0002 en 0004 gebruiken alleen nog bevroren functies uit `kennisbank/oud_formaat.py`; updateprocedure met back-up/terugvalpunt beschreven in [docs/installatie-en-beheer.md](docs/installatie-en-beheer.md#dagelijks-beheer).

Migratie: `0006_tellingen_per_omgeving` (nieuwe kolommen en één nieuwe tabel; geen inhoudswijziging).

## 1.4.1 – 2026-11-07

Reparaties naar aanleiding van een onafhankelijke code-review (beveiliging en overdraagbaarheid).

- **Health-checks** `/healthz` en `/readyz` werken nu ook als Kubernetes of Docker ze aanroept met het pod-IP als Host (vóór deze versie gaven ze 400 zodra `KB_ALLOWED_HOSTS` was ingevuld, waardoor de pod nooit *Ready* werd). De CI-rooktest controleert dit.
- **OIDC-modus**: wachtwoord-inloggen is volledig uit. Het inlogscherm van het beheer stuurt door naar de identity provider, `/inloggen/` bestaat niet en een wachtwoord in de database werkt nergens. Ingelogd zonder beheerrechten geeft een uitlegpagina.
- **Word-import** weigert documenten die uitgepakt groter zijn dan 20 MB of meer dan 2 MB tekst opleveren (bescherming tegen 'zip-bommen' die het geheugen vol laten lopen).
- **Editor** Jodit bijgewerkt van 4.2.47 naar 4.18.12 (bekende XSS-kwetsbaarheden verholpen). Meegeleverde browserbibliotheken staan in `vendor/componenten.json` en zitten in de SBOM (`scripts/maak_sbom.py`); een test bewaakt de versie.
- Opsommingen in de editor stonden te ver ingesprongen door een stijl van het Django-beheer.
- Logregels bij 4xx/5xx bevatten alleen methode en pad, geen querystring meer.
- API-schema en -documentatie (`/api/schema/`, `/api/docs/`) alleen voor ingelogde gebruikers.
- Eén versiebron (`kennisbank/__init__.py`); een test controleert dat alle bestanden dezelfde versie noemen. Documentatie op een paar punten gecorrigeerd (CSP in het beheer, aantal tests, API-pad).

## 1.4.0 – 2026-11-06

- Lege regels zijn altijd bewust en blijven staan, ook vlak voor of na een sectiekader. De typ-ruimte die de editor zelf rond kaders zet is nu zichtbaar gemarkeerd (*tussenruimte, wordt niet opgeslagen*) en is het enige dat bij opslaan vervalt.
- Word-import: lege regels blijven staan (meerdere achter elkaar worden er één); op de plek van een overgeslagen afbeelding staat *[afbeelding weggelaten]*.

## 1.3.3 – 2026-11-06

- Volledig scherm: titel en samenvatting staan links boven de editor (ook live in het voorbeeld), sleepbalk in het midden (verdeling wordt onthouden), bovenbalk in een eigen kleur
- Altijd een lege regel vóór, tussen en na sectiekaders om te kunnen typen; alleen lege regels direct tegen een kader aan vervallen bij opslaan. Lege regels tussen gewone alinea's blijven voortaan staan.

## 1.3.2 – 2026-11-06

- **Volledig scherm** vervangt de knop Voorbeeld: links de editor, rechts het voorbeeld dat live meeloopt terwijl je typt, met *Opslaan en doorgaan* en *Sluiten* (Esc)

## 1.3.1 – 2026-11-06

- Word-import bewust eenvoudig: alleen tekst en opmaak komen mee. Titel = bestandsnaam, samenvatting vul je in; secties en onboarding maak je in de editor. Het Word-sjabloon en de stijlen *Sectie*, *Einde sectie* en *Onboarding* zijn vervallen.

## 1.3.0 – 2026-11-06

- Secties zijn kaders: selecteer tekst, klik **Sectie**, typ de titel in de blauwe balk. Tekst buiten een kader is altijd zichtbaar, ook tussen en na secties. Nogmaals klikken haalt het kader weg. Onboarding-blokken staan zichtbaar binnen of buiten een kader.
- Word: de stijl *Sectie* begint een sectie; de nieuwe stijl *Einde sectie* sluit hem af (zit in het sjabloon)
- API: artikeldetail geeft `blokken[]` in leesvolgorde in plaats van `inleiding_html` + `secties[]`
- Importformaat versie 4; versie 3 wordt nog gelezen. Migratie zet bestaande artikelen en versiegeschiedenis automatisch om.

## 1.2.1 – 2026-11-06

- Knop **Voorbeeld** in de editor: toont het artikel zoals het gepubliceerd zou zijn, met de nog niet opgeslagen tekst
- Sectiekop: na het markeren springt de cursor naar een nieuwe regel eronder; weergave in de editor als `«Sectiekop» naam «Sectiekop»`
- Opsommingen tonen weer bolletjes en nummers in de editor

## 1.2.0 – 2026-11-06

- Een artikel is één tekst; secties maak je met de knop **Sectiekop** (of de Word-stijl *Sectie*). Gewone koppen maken geen sectie meer. Tekst vóór de eerste sectiekop is de inleiding.
- Links werken op het artikelnummer (`/artikel/412/naam`): blijvend bij hernoemen of verhuizen; dezelfde titel mag in meerdere omgevingen voorkomen. Oude links worden doorverwezen. Het veld *Slug* is uit het formulier verdwenen.
- API: artikelen op `id`; `url` en `id` in alle antwoorden; artikeldetail heeft `inleiding_html` en `secties[]`.
- Importformaat versie 3 (`inhoud` per artikel); versies 1 en 2 worden nog gelezen. Export per omgeving op (omgeving, slug).
- Migratie zet bestaande secties en versiegeschiedenis automatisch om.

## 1.1.0 – 2026-11-06

- Secties worden bewerkt in een opmaak-editor (koppen, vet, cursief, onderstreept, lijsten, tabellen, links); plakken uit Word wordt opgeschoond
- Onboarding-uitleg is nu een markering in de tekst (knop **Onboarding**), meerdere blokken per sectie mogelijk; het aparte veld is vervallen
- Importeren uit Word (.docx): koppen worden secties, de Word-stijl 'Onboarding' wordt herkend; Word-sjabloon meegeleverd
- Tags typ je als tekst bij het artikel; nieuwe tags worden automatisch aangemaakt
- Importformaat versie 2 (HTML); versie 1 (Markdown) wordt nog gelezen
- Migratie zet bestaande inhoud en versiegeschiedenis automatisch om

## 1.0.0 – 2026-11-05

Eerste versie, gebaseerd op het klikbare prototype en de functionele schets.

- Artikelen met inklapbare secties, onboarding-uitleg, zoeken en filters, favorieten, recent bezocht, delen
- Verbetervoorstellen op geselecteerde tekst, met behandeling en terugkoppeling
- Assistent op basis van de kennisbank; optioneel taalmodel (Azure OpenAI of OpenAI-compatibel)
- Omgevingen en rollen via groepen uit de identity provider (OIDC)
- Versiegeschiedenis van gepubliceerde artikelen
- Gebruiksstatistieken zonder persoonsgegevens
- Koppeling met het zaaksysteem: inbedden per zaaktype en API
- Import en export (JSON), bewaartermijnen, demomodus
- Container-image, Kubernetes-manifesten, CI-pipelines, SBOM
