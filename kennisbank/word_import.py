"""Een Word-document (.docx) omzetten naar een artikel.

Regels:
- De tekst wordt één artikeltekst. Alleen alinea's met de Word-stijl 'Sectie' worden sectiekoppen
  (zie docs/sjabloon-werkinstructie.docx). Gewone koppen (Kop 1, 2, 3) blijven koppen in de tekst.
- De Word-stijl 'Titel', of anders één Kop 1 helemaal bovenaan, wordt de titel van het artikel.
- De eerste alinea (vóór de eerste sectiekop) wordt de samenvatting.
- Alinea's met de Word-stijl 'Onboarding' worden onboarding-blokken.
- Opmaak (vet, cursief, onderstreept, lijsten, tabellen, links) blijft behouden. Afbeeldingen worden
  overgeslagen; het aantal wordt teruggemeld.
"""

import re
from dataclasses import dataclass, field

import mammoth

from .inhoud import ONBOARDING_KLASSE, SECTIE_KLASSE, naar_platte_tekst, schoon

STIJLKAART = f"""
p[style-name='Sectie'] => h2.{SECTIE_KLASSE}:fresh
p[style-name='sectie'] => h2.{SECTIE_KLASSE}:fresh
p[style-name='Onboarding'] => div.{ONBOARDING_KLASSE} > p:fresh
p[style-name='onboarding'] => div.{ONBOARDING_KLASSE} > p:fresh
p[style-name='Title'] => h1.titel:fresh
p[style-name='Titel'] => h1.titel:fresh
u => u
strike => s
"""


class WordImportFout(ValueError):
    pass


@dataclass
class WordArtikel:
    titel: str
    samenvatting: str
    inhoud: str
    aantal_secties: int = 0
    afbeeldingen_overgeslagen: int = 0
    meldingen: list[str] = field(default_factory=list)


def lees_docx(bestand, bestandsnaam: str = "") -> WordArtikel:
    teller = {"afbeeldingen": 0}

    def geen_afbeelding(image):
        teller["afbeeldingen"] += 1
        return {"src": ""}

    try:
        resultaat = mammoth.convert_to_html(
            bestand, style_map=STIJLKAART, convert_image=mammoth.images.img_element(geen_afbeelding)
        )
    except Exception as e:  # noqa: BLE001 - alles wat geen geldig .docx is
        raise WordImportFout("Dit bestand kon niet als Word-document (.docx) worden gelezen.") from e

    artikel = _verwerk(resultaat.value, bestandsnaam)
    artikel.afbeeldingen_overgeslagen = teller["afbeeldingen"]
    if teller["afbeeldingen"]:
        artikel.meldingen.append(
            f"{teller['afbeeldingen']} afbeelding(en) overgeslagen: de kennisbank ondersteunt nog geen afbeeldingen."
        )
    return artikel


def _verwerk(html: str, bestandsnaam: str) -> WordArtikel:
    html = html.strip()
    titel = ""

    # Titel: Word-stijl 'Titel', of anders precies één Kop 1 helemaal aan het begin.
    m = re.match(r'\s*<h1 class="titel">(.*?)</h1>', html, re.S)
    if m:
        titel = naar_platte_tekst(m.group(1))
        html = html[m.end() :]
    else:
        m = re.match(r"\s*<h1>(.*?)</h1>", html, re.S)
        if m and html.count("<h1") == 1:
            titel = naar_platte_tekst(m.group(1))
            html = html[m.end() :]
    if not titel:
        titel = re.sub(r"[-_]+", " ", re.sub(r"\.docx$", "", bestandsnaam, flags=re.I)).strip() or "Nieuw artikel"

    # Samenvatting: de eerste alinea, mits die vóór de eerste sectiekop staat en geen onboarding is.
    samenvatting = ""
    m = re.match(r"\s*<p>(.*?)</p>", html, re.S)
    if m:
        samenvatting = naar_platte_tekst(m.group(1))[:1000]
        html = html[m.end() :]

    inhoud = schoon(html)
    aantal_secties = len(re.findall(rf'<h2 class="{SECTIE_KLASSE}">', inhoud))
    artikel = WordArtikel(titel=titel[:200], samenvatting=samenvatting, inhoud=inhoud, aantal_secties=aantal_secties)
    if not samenvatting:
        artikel.meldingen.append(
            "Geen samenvatting gevonden: vul die zelf in (de eerste alinea van het document wordt de samenvatting)."
        )
    if not aantal_secties:
        artikel.meldingen.append(
            "Geen sectiekoppen gevonden: het artikel heeft nog geen in- en uitklapbare secties. "
            "Gebruik in Word de stijl 'Sectie' (uit het sjabloon), of markeer regels hier met de knop 'Sectiekop'."
        )
    return artikel
