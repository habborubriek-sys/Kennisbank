"""Een Word-document (.docx) inlezen als artikeltekst.

Bewust eenvoudig: alleen de tekst en de opmaak komen mee (vet, cursief, onderstreept, doorgehaald,
koppen, lijsten, tabellen, links). Secties en onboarding-uitleg voeg je daarna in de editor toe.
De titel wordt de bestandsnaam; de samenvatting vul je zelf in. Afbeeldingen worden overgeslagen;
op hun plek komt de tekst "[afbeelding weggelaten]" en het aantal wordt teruggemeld. Lege regels uit
Word blijven staan; meerdere lege regels achter elkaar worden er één.
"""

import re
from dataclasses import dataclass, field

import mammoth

from .inhoud import schoon

AFBEELDING_MARKERING = "[afbeelding weggelaten]"

STIJLKAART = """
u => u
strike => s
"""


class WordImportFout(ValueError):
    pass


@dataclass
class WordArtikel:
    titel: str
    inhoud: str
    afbeeldingen_overgeslagen: int = 0
    meldingen: list[str] = field(default_factory=list)


def lees_docx(bestand, bestandsnaam: str = "") -> WordArtikel:
    teller = {"afbeeldingen": 0}

    def geen_afbeelding(image):
        teller["afbeeldingen"] += 1
        return {"src": ""}

    try:
        resultaat = mammoth.convert_to_html(
            bestand,
            style_map=STIJLKAART,
            convert_image=mammoth.images.img_element(geen_afbeelding),
            ignore_empty_paragraphs=False,
        )
    except Exception as e:  # noqa: BLE001 - alles wat geen geldig .docx is
        raise WordImportFout("Dit bestand kon niet als Word-document (.docx) worden gelezen.") from e

    html = resultaat.value
    # Op de plek van een afbeelding een duidelijke markering, zodat je ziet waar je iets moet aanvullen.
    html = re.sub(r"<img\b[^>]*>", f"<em>{AFBEELDING_MARKERING}</em>", html)
    # Lege regels: meerdere achter elkaar worden er één; lege cellen en het begin/einde van het document niet.
    html = re.sub(r"(<p></p>)+", "<p><br></p>", html)
    html = re.sub(r"(<t[dh]>)<p><br></p>(</t[dh]>)", r"\1\2", html)
    html = re.sub(r"^(<p><br></p>)+|(<p><br></p>)+$", "", html.strip())

    titel = re.sub(r"[-_]+", " ", re.sub(r"\.docx$", "", bestandsnaam, flags=re.I)).strip() or "Nieuw artikel"
    artikel = WordArtikel(titel=titel[:200], inhoud=schoon(html), afbeeldingen_overgeslagen=teller["afbeeldingen"])
    if teller["afbeeldingen"]:
        artikel.meldingen.append(
            f"{teller['afbeeldingen']} afbeelding(en) overgeslagen: de kennisbank ondersteunt nog geen afbeeldingen. "
            f"Op die plekken staat nu '{AFBEELDING_MARKERING}'."
        )
    if not artikel.inhoud:
        artikel.meldingen.append("Het document bevatte geen tekst.")
    return artikel
