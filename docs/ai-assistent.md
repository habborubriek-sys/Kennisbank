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

Per vraag: een vaste instructie, de tekst van de gevonden secties (met artikeltitel en versie), het zaaktype als de vraag uit het zaaksysteem komt, en de vraag zelf. **Nooit** naam, e-mail, gebruikers-ID of andere gegevens over de gebruiker. Vragen worden niet opgeslagen of gelogd; alleen het aantal vragen per dag (en hoeveel zonder bron) wordt geteld. Zie [beveiliging-en-privacy](beveiliging-en-privacy.md#ai-assistent-en-gegevensstromen).

## Aanpassen

De instructie aan het model staat in `SYSTEEMPROMPT` in [kennisbank/assistent.py](../kennisbank/assistent.py). Het zoekgedeelte staat in `zoek_secties` in [kennisbank/zoeken.py](../kennisbank/zoeken.py). Wil je later semantisch zoeken (embeddings, bijvoorbeeld met pgvector), dan vervang je alleen die functie. De rest van de assistent blijft gelijk.
