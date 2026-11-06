"""Een Word-document (.docx) inlezen als artikeltekst.

Bewust eenvoudig: alleen de tekst en de opmaak komen mee (vet, cursief, onderstreept, doorgehaald,
koppen, lijsten, tabellen, links). Secties en onboarding-uitleg voeg je daarna in de editor toe.
De titel wordt de bestandsnaam; de samenvatting vul je zelf in. Afbeeldingen worden overgeslagen;
het aantal wordt teruggemeld.
"""

import re
from dataclasses import dataclass, field

import mammoth

from .inhoud import schoon

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
            bestand, style_map=STIJLKAART, convert_image=mammoth.images.img_element(geen_afbeelding)
        )
    except Exception as e:  # noqa: BLE001 - alles wat geen geldig .docx is
        raise WordImportFout("Dit bestand kon niet als Word-document (.docx) worden gelezen.") from e

    titel = re.sub(r"[-_]+", " ", re.sub(r"\.docx$", "", bestandsnaam, flags=re.I)).strip() or "Nieuw artikel"
    artikel = WordArtikel(
        titel=titel[:200], inhoud=schoon(resultaat.value), afbeeldingen_overgeslagen=teller["afbeeldingen"]
    )
    if teller["afbeeldingen"]:
        artikel.meldingen.append(
            f"{teller['afbeeldingen']} afbeelding(en) overgeslagen: de kennisbank ondersteunt nog geen afbeeldingen."
        )
    if not artikel.inhoud:
        artikel.meldingen.append("Het document bevatte geen tekst.")
    return artikel
