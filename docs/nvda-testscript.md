# Testscript: handmatige test met NVDA

Voor een handmatige toets van de kennisbank met een echte schermlezer. Gebaseerd op het script van de
onafhankelijke toegankelijkheidsreview van 1.27.0, bijgewerkt naar **1.29.0**. Achter elke stap staat wat je
**zou moeten** horen of zien. Wijkt het af, noteer dan wat er wel gebeurt.

**Voorbereiding**
- Windows met NVDA (actuele versie) en Chrome of Edge. Leg de muis weg en werk alleen met het toetsenbord.
- Lees elke stap in **bladermodus** en in **focusmodus** (NVDA+spatie wisselt tussen de twee).
- Gebruik de demo-inhoud en de demo-gebruikers `medewerker`, `redacteur` en `reviewer` (wachtwoord `demo`).
- Noteer per stap wat NVDA zegt, en of je verder kon zonder muis.

## A. Site, als `medewerker`

1. Ga naar `/` en druk op Tab.
   - *Verwacht:* "Naar de inhoud". Enter zet de cursor in de inhoud.
2. Druk op `/` en typ "rappel".
   - *Verwacht:* de focus staat in het zoekveld, en het aantal resultaten wordt voorgelezen.
3. Open een artikel. Spring met H door de koppen en klap een sectie open en dicht met Enter.
   - *Verwacht:* "uitgeklapt" / "samengeklapt".
4. Selecteer in bladermodus een zin met Shift+pijl rechts.
   - *Verwacht:* de knop *Verbetervoorstel over deze tekst* verschijnt. Lukt selecteren niet, gebruik dan
     *dien een verbetervoorstel in* (bekende beperking).
5. Open het venster *Verbetervoorstel indienen* en typ iets.
   - *Verwacht:* je hoort de titel, en Tab blijft in het venster.
   - Escape sluit het, en de focus staat weer op de knop.
   - Open je het venster opnieuw, dan staat je tekst er nog.
6. Druk op de knop **Donker** rechtsboven.
   - *Verwacht:* "Donker, schakelknop, ingedrukt". Na herladen is de site nog donker.

## B. Werkplek en werkbak, als `redacteur`

7. Ga naar `/beheer/`, druk op D (landmarks) en ga naar *Algemeen*.
   - *Verwacht:* je hoort "Werkbakken, navigatie", en bij *Algemeen* "huidige pagina".
8. Ga met T naar de tabel en lees een rij met Ctrl+Alt+pijlen.
   - *Verwacht:* de kolomkoppen worden genoemd, en bij een nieuw voorstel hoor je "Nog niet geopend".
9. Vink twee voorstellen aan met Spatie.
   - *Verwacht:* je hoort "Selecteer: [voorstel] (bij [artikel])", en daarna "2 voorstellen aangevinkt".
10. Kies bij *Toewijzen aan* jezelf en druk op *Toewijzen*.
    - *Verwacht:* de bevestiging wordt voorgelezen.

## C. Bewerkscherm met lade

Open hiervoor een voorstel uit de werkbak.

11. Druk vanaf het begin op Tab en noteer de volgorde.
    - *Verwacht:* je komt nooit op iets dat je niet ziet.
    - De werkbalk is één stop: daarin ga je met de pijltjes verder, met Tab ga je eruit.
12. Ga naar het tabblad *Voorstellen* en druk op Enter.
    - *Verwacht:* "Voorstellen, knop, uitgeklapt". De focus staat op de kop "Verbetervoorstellen" in de lade.
13. Open een voorstel met Enter.
    - *Verwacht:* de focus blijft op het voorstel, en je hoort "uitgeklapt".
14. Vink *Meenemen in deze versie* aan met Spatie.
    - *Verwacht:* je hoort "aangevinkt", en kort daarna "1 wijziging bij Meenemen nog niet opgeslagen".
15. Druk op *Interne notitie* en daarna op *Bericht aan …*.
    - *Verwacht:* "ingedrukt", en de focus blijft op de knop.
16. Typ een bericht, wissel naar *Interne notitie* en weer terug.
    - *Verwacht:* je tekst staat er nog.
17. Druk op *Versturen aan …*.
    - *Verwacht:* je hoort de titel van het venster en de tekst van je bericht, en Tab blijft in het venster.
    - Escape sluit het venster, en de focus staat weer op *Versturen aan …*.
18. Kies *Afwijzen…*.
    - *Verwacht:* je hoort de titel "Voorstel afwijzen" en de uitleg, en het tekstvak heeft een naam.
    - Breek af met Escape.
19. Druk op *Toon in de tekst* en lees de tekst.
    - *Verwacht:* de cursor staat op het citaat.
    - Je hoort "begin verbetervoorstel 1 … einde verbetervoorstel 1", en geen los getal in de zin.
20. Druk in de lade op Escape.
    - *Verwacht:* de lade gaat dicht, en de focus staat op het tabblad.

## D. Balk, panelen en Afronden

21. Druk bij *Eigenschappen* op Enter.
    - *Verwacht:* "uitgeklapt", en de focus staat op de kop "Eigenschappen".
    - Escape sluit het paneel, en de focus staat weer op de knop. Herhaal dit voor *Geschiedenis* en *Review*.
22. Druk op *Afronden…*.
    - *Verwacht:* je hoort "Afronden, dialoogvenster" en de keuzes met uitleg.
    - Tab blijft in het venster.
    - Escape sluit het venster, en de focus staat weer op *Afronden…*.
23. Kies *Ter inzage geven* en bevestig zonder een team te kiezen.
    - *Verwacht:* je hoort de vraag, de vinkjes met de teamnaam, en de foutmelding.
24. Kies *Bekijk als medewerker* en druk op Escape terwijl de focus in het voorbeeld staat.
    - *Verwacht:* je hoort dat er een venster opent. Escape sluit het, en de focus staat weer op de knop.
25. Gebruik *Link* in de werkbalk, en open het sectiemenu (⋯) bij een sectie.
    - *Verwacht:* het venster wordt voorgelezen.
    - In het menu werken de pijltjes. Escape zet de focus terug op ⋯.
26. Herhaal stap 22 bij een nieuw nieuwsbericht en bij een nieuw artikel.

## E. Reviewpagina, als `reviewer`

27. Ga naar `/review/` en open een stuk.
    - *Verwacht:* de infobalk wordt voorgelezen (team, ter inzage, bij wie).
    - Ligt het nog niet bij jou, kies dan **Oppakken** in de balk.
28. Lees de tekst in bladermodus.
    - *Verwacht:* je hoort "ingevoegd" en "verwijderd". Gebeurt dat niet, zet dan in NVDA bij Documentopmaak
      "Revisies van editor melden" aan.
    - Bij een meegenomen voorstel hoor je "verbetervoorstel 1".
    - Druk op **Wijzigingen tonen**. *Verwacht:* je hoort "niet ingedrukt", en de tekst leest zonder weggehaalde
      stukken.
29. Zet een opmerking bij een stuk tekst.
    - Selecteer met Shift+pijltjes en druk op Tab naar *Opmerking*. Typ, en kies *Plaatsen*.
    - Of kies *+ Algemene opmerking* en gebruik *Bij een bepaald stuk tekst? Typ of plak het hier*.
    - *Verwacht:* beide wegen werken zonder muis.
30. Ga in de marge naar *Toon in de tekst* bij opmerking 1.
    - *Verwacht:* de focus staat op de markering, en je hoort "opmerking 1".
    - Kies bij je eigen opmerking *Wijzigen*, pas de tekst aan en kies *Opslaan*. Kies daarna *Weghalen*.
      *Verwacht:* het venster wordt voorgelezen en de focus staat op *Annuleren*.
    - Kies **Afronden…**. *Verwacht:* het venster *Afronden* wordt voorgelezen, Tab blijft erin, en Escape zet
      de focus terug op de knop.
## F. Algemeen, op elk scherm

31. Zoom in naar 400% (Ctrl +).
    - *Verwacht:* alles is te lezen zonder horizontaal te scrollen.
    - De lade vult het hele scherm en heeft bovenaan een sluitknop.
32. Zet Windows Hoog contrast aan.
    - *Verwacht:* de markeringen zijn nog te herkennen aan de lijnen eronder (stippel bij een voorstel,
      doorgetrokken bij een opmerking).
    - Noteer wat er gebeurt met de pillen in de infobalk, het lade-tabblad en de nummers.
