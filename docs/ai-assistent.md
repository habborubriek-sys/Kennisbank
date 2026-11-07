# AI-assistent

De assistent beantwoordt vragen **uitsluitend op basis van de kennisbank** en verwijst altijd naar het artikel en het kopje waar het antwoord staat.

## Hoe het werkt

1. **Zoeken.** De vraag wordt met PostgreSQL full-text search (Nederlandse woordstammen) vergeleken met alle secties van de gepubliceerde artikelen die de gebruiker mag zien. Concepten en artikelen uit andere omgevingen doen nooit mee. Zwakke treffers vallen af. Komt de vraag uit het zaaksysteem, dan wegen artikelen bij dat zaaktype zwaarder.
2. **Zonder taalmodel** (`KB_AI_PROVIDER=uit`, standaard): de assistent toont de best passende sectie letterlijk, met links naar de bronnen. Dit werkt direct, kost niets en stuurt niets naar buiten.
3. **Met taalmodel**: de vraag en maximaal `KB_AI_MAX_BRONNEN` secties gaan naar het model, met de opdracht:
   - alleen uit de bronnen te antwoorden;
   - te zeggen "Dat staat niet in de kennisbank" als het antwoord er niet in staat;
   - bij elke bewering naar de bron te verwijzen met [1], [2].

   Die verwijzingen worden in het antwoord klikbare links naar de juiste sectie. Het antwoord gaat door dezelfde HTML-opschoning als de artikelen.
4. **Storing.** Is het model niet bereikbaar of te traag (`KB_AI_TIMEOUT_SECONDEN`), dan valt de assistent terug op stap 2 en meldt dat aan de gebruiker.

Zonder treffers antwoordt de assistent dat er niets over in de kennisbank staat. Hij verzint dus geen antwoord, en procesmanagement ziet in de statistieken hoe vaak dat gebeurt.

## Aansluiten

**Azure OpenAI**
```
KB_AI_PROVIDER=azure
KB_AI_BASE_URL=https://<resource>.openai.azure.com
KB_AI_MODEL=<deployment-naam>
KB_AI_API_KEY=<sleutel>
```

**Elk OpenAI-compatibel endpoint** (zelf gehost met vLLM, Ollama of een interne AI-gateway):
```
KB_AI_PROVIDER=openai
KB_AI_BASE_URL=https://llm.intern.example.nl/v1
KB_AI_MODEL=<modelnaam>
KB_AI_API_KEY=<sleutel, indien nodig>
```

De applicatie gebruikt alleen het standaard `chat/completions`-endpoint. Er is geen SDK van een leverancier nodig, en wisselen van model is alleen een configuratiewijziging.

## Wat er naar het model gaat

Per vraag: een vaste instructie (systeemprompt), de tekst van de gevonden secties (met artikeltitel en versie), het zaaktype als de vraag uit het zaaksysteem komt, en de vraag zelf. **Nooit** naam, e-mail, gebruikers-ID of andere gegevens over de gebruiker. Vragen worden niet opgeslagen of gelogd; alleen het aantal vragen per dag en per omgeving (en hoeveel zonder bron) wordt geteld. Zie [beveiliging-en-privacy](beveiliging-en-privacy.md#ai-assistent-en-gegevensstromen).

### Bronnen zijn gegevens, geen instructies

De artikeltekst wordt geschreven door redacteuren en kan uit Word komen; het zaaktype komt uit de URL van het zaaksysteem. Daarom staan ze niet in de systeemprompt, maar in het gebruikersbericht, elk tussen markeringen (`<<<BRON 1>>> … <<<EINDE BRON 1>>>`, `<<<CONTEXT>>>`, `<<<VRAAG>>>`). De systeemprompt zegt het model dat alles tussen die markeringen gegevensmateriaal is en dat instructies daarin niet worden uitgevoerd. Markeringen die in de broninhoud zelf voorkomen worden verwijderd, zodat een tekst niet "uit zijn bron kan breken"; het zaaktype wordt teruggebracht tot een korte code. Dit vermindert het risico van *prompt injection*, maar sluit het niet uit: een taalmodel volgt zijn instructies niet gegarandeerd. Daarom geldt ook: het antwoord wordt door dezelfde HTML-opschoning gehaald als artikelen, en **alle links in het antwoord behalve de bronverwijzingen `[n]` worden gewone tekst**. Het model kan de gebruiker dus nergens anders naartoe sturen dan naar de kennisbank.

### Kosten en begrenzing

Elke vraag met AI aan is één aanroep van het taalmodel met hooguit `KB_AI_MAX_BRONNEN` secties als invoer en `KB_AI_MAX_TOKENS` (standaard 600) tokens als uitvoer. Reken voor een inschatting met ongeveer 1.500–3.000 invoertokens per vraag bij vijf secties van gemiddelde lengte. Drie begrenzingen:

| | Instelling | Standaard | Werking |
|---|---|---|---|
| Per gebruiker | `KB_ASSISTENT_LIMIET` | `30/min` | Daarboven krijgt de gebruiker een melding om even te wachten (per worker bijgehouden). |
| Per antwoord | `KB_AI_MAX_TOKENS` | `600` | Maximale lengte van het antwoord. |
| Per dag, hele installatie | `KB_ASSISTENT_DAGLIMIET` | `2000` | Kostenplafond; `0` = geen plafond. In de database bijgehouden, dus geldig voor alle replica's samen (bij veel gelijktijdige vragen kan het plafond enkele aanroepen overschrijden). Daarboven valt de assistent terug op citeren uit de kennisbank (zonder taalmodel) met de melding dat de AI zijn limiet heeft bereikt; de volgende dag werkt hij weer. |

Bij 2.000 aanroepen per dag en circa 3.000 tokens per aanroep is het verbruik hooguit 6 miljoen tokens per dag; vermenigvuldig dat met het tarief van het gekozen model voor het maximale dagbedrag. Het aantal aanroepen per dag staat in de tabel `kennisbank_assistentdagtotaal`; het bereiken van het plafond wordt als waarschuwing gelogd. De statistieken in het beheer tonen per omgeving het aantal vragen aan de assistent.

## Aanpassen

De instructie aan het model staat in `SYSTEEMPROMPT` in [kennisbank/assistent.py](../kennisbank/assistent.py). Het zoekgedeelte staat in `zoek_secties` in [kennisbank/zoeken.py](../kennisbank/zoeken.py). Wil je later semantisch zoeken (embeddings, bijvoorbeeld met pgvector), dan vervang je alleen die functie. De rest van de assistent blijft gelijk.
