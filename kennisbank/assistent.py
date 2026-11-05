"""De assistent: beantwoordt vragen uitsluitend op basis van de kennisbank.

Werking (retrieval-augmented generation):
1. Zoek de meest relevante secties met PostgreSQL full-text search (zoeken.zoek_secties).
2. Staat de AI uit (KB_AI_PROVIDER=uit)? Dan citeren we de best passende sectie.
3. Staat de AI aan? Dan sturen we de vraag plus alleen die secties naar het taalmodel,
   met de opdracht uitsluitend daaruit te antwoorden en met [n] naar de bron te verwijzen.

Er wordt nooit iets over de gebruiker naar het taalmodel gestuurd, en vragen worden
niet opgeslagen (alleen het aantal per dag).
"""

import html
import logging
import re
from dataclasses import dataclass, field

import httpx
from django.conf import settings
from django.db.models import F
from django.utils import timezone

from .inhoud import naar_html, naar_platte_tekst
from .models import AssistentTelling
from .zoeken import zoek_secties

log = logging.getLogger("kennisbank.assistent")

SYSTEEMPROMPT = """Je bent de assistent van de kennisbank van een overheidsorganisatie.
Je beantwoordt vragen van medewerkers over hun werk, UITSLUITEND op basis van de bronnen hieronder.

Regels:
- Gebruik alleen informatie uit de bronnen. Voeg geen eigen kennis toe.
- Staat het antwoord niet in de bronnen, zeg dan: "Dat staat niet in de kennisbank."
  en stel voor een verbetervoorstel in te dienen.
- Verwijs na elke bewering naar de bron met [1], [2] enzovoort.
- Antwoord in het Nederlands, kort en concreet (hooguit 150 woorden). Gebruik een lijstje bij stappen.
- Geef geen juridisch advies buiten wat de bronnen zeggen."""


@dataclass
class Antwoord:
    html: str
    bronnen: list = field(default_factory=list)
    modus: str = "zoeken"  # "zoeken" of "ai"
    melding: str = ""


def _bron(sectie, nummer):
    a = sectie.artikel
    return {
        "nummer": nummer,
        "slug": a.slug,
        "titel": a.titel,
        "sectie": sectie.kop,
        "sectie_index": list(a.secties.values_list("pk", flat=True)).index(sectie.pk),
        "versie": a.versie,
    }


def _tel(zonder_bron: bool):
    telling, _ = AssistentTelling.objects.get_or_create(datum=timezone.localdate())
    AssistentTelling.objects.filter(pk=telling.pk).update(
        vragen=F("vragen") + 1, zonder_bron=F("zonder_bron") + (1 if zonder_bron else 0)
    )


def beantwoord(vraag: str, artikelen_qs, zaaktype: str | None = None) -> Antwoord:
    vraag = (vraag or "").strip()[:1000]
    secties = zoek_secties(artikelen_qs, vraag, zaaktype=zaaktype, aantal=settings.KB_AI_MAX_BRONNEN)
    _tel(zonder_bron=not secties)
    if not secties:
        return Antwoord(
            html="<p>Daar vind ik niets over in de kennisbank. Probeer een ander woord, "
            "of dien een verbetervoorstel in als je denkt dat er een artikel ontbreekt.</p>",
        )
    bronnen = [_bron(s, i + 1) for i, s in enumerate(secties)]

    if settings.KB_AI_PROVIDER != "uit":
        try:
            tekst = _vraag_model(vraag, secties, zaaktype)
            return Antwoord(html=_koppel_bronnen(naar_html(tekst), bronnen), bronnen=bronnen, modus="ai")
        except Exception:  # noqa: BLE001 - bij storing terugvallen op zoeken
            log.exception("taalmodel niet bereikbaar, terugval op zoeken")
            antwoord = _citeer(secties[0], bronnen)
            antwoord.melding = "De AI is op dit moment niet beschikbaar. Dit is het best passende fragment."
            return antwoord
    return _citeer(secties[0], bronnen)


def _citeer(sectie, bronnen) -> Antwoord:
    """Zonder taalmodel: toon de best passende sectie (kort) of een ingekort fragment."""
    fragment = naar_platte_tekst(sectie.inhoud)
    if len(fragment) <= 450:
        citaat = f"<blockquote>{naar_html(sectie.inhoud)}</blockquote>"
    else:
        citaat = f"<p>“{html.escape(fragment[:300].rsplit(' ', 1)[0])}…”</p>"
    return Antwoord(
        html=(
            f"<p>Dit staat in <b>{html.escape(sectie.artikel.titel)}</b>, onder het kopje "
            f"<i>{html.escape(sectie.kop)}</i>:</p>{citaat}"
        ),
        bronnen=bronnen,
    )


def _koppel_bronnen(antwoord_html: str, bronnen) -> str:
    per_nummer = {b["nummer"]: b for b in bronnen}

    def vervang(m):
        b = per_nummer.get(int(m.group(1)))
        if not b:
            return m.group(0)
        return (
            f'<a class="bronref" href="/artikel/{b["slug"]}" data-open="{b["slug"]}" '
            f'data-sectie="{b["sectie_index"]}" title="{html.escape(b["titel"])} – '
            f'{html.escape(b["sectie"])}">[{b["nummer"]}]</a>'
        )

    return re.sub(r"\[(\d{1,2})\]", vervang, antwoord_html)


def _vraag_model(vraag, secties, zaaktype) -> str:
    bronnen_tekst = "\n\n".join(
        f"[{i + 1}] Artikel: {s.artikel.titel} (versie {s.artikel.versie})\n"
        f"Kopje: {s.kop}\n{naar_platte_tekst(s.inhoud)}"
        + (f"\nExtra uitleg voor nieuwe collega's: {naar_platte_tekst(s.onboarding)}" if s.onboarding else "")
        for i, s in enumerate(secties)
    )
    context = f"\nDe medewerker werkt in een zaak van het type '{zaaktype}'." if zaaktype else ""
    berichten = [
        {"role": "system", "content": SYSTEEMPROMPT + context + "\n\nBronnen:\n\n" + bronnen_tekst},
        {"role": "user", "content": vraag},
    ]
    if settings.KB_AI_PROVIDER == "azure":
        url = (
            f"{settings.KB_AI_BASE_URL.rstrip('/')}/openai/deployments/{settings.KB_AI_MODEL}"
            f"/chat/completions?api-version={settings.KB_AI_AZURE_API_VERSIE}"
        )
        headers = {"api-key": settings.KB_AI_API_KEY}
        body = {"messages": berichten, "temperature": settings.KB_AI_TEMPERATUUR}
    else:
        url = f"{settings.KB_AI_BASE_URL.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {settings.KB_AI_API_KEY}"} if settings.KB_AI_API_KEY else {}
        body = {"model": settings.KB_AI_MODEL, "messages": berichten, "temperature": settings.KB_AI_TEMPERATUUR}
    resp = httpx.post(url, json=body, headers=headers, timeout=settings.KB_AI_TIMEOUT_SECONDEN)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]
