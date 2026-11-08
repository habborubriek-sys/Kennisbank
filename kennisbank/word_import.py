"""Een Word-document (.docx) inlezen als artikeltekst.

Bewust eenvoudig: alleen de tekst en de opmaak komen mee (vet, cursief, onderstreept, doorgehaald,
koppen, lijsten, tabellen, links). Secties en onboarding-uitleg voeg je daarna in de editor toe.
De titel wordt de bestandsnaam; de samenvatting vul je zelf in. Afbeeldingen worden overgeslagen;
op hun plek komt de tekst "[afbeelding weggelaten]" en het aantal wordt teruggemeld. Lege regels uit
Word blijven staan; meerdere lege regels achter elkaar worden er één.
"""

import html as _html
import re
import zipfile
from dataclasses import dataclass, field

import mammoth

from .inhoud import schoon

AFBEELDING_MARKERING = "[afbeelding weggelaten]"

# Een .docx is een zip. Een kwaadwillend bestand van een paar honderd kB kan uitgepakt honderden MB's
# zijn ('zip-bom') en het proces uit zijn geheugen laten lopen. Daarom grenzen op de uitgepakte
# grootte en op de lengte van het resultaat; een echte werkinstructie komt daar nooit bij in de buurt.
MAX_UITGEPAKT = 20 * 1024 * 1024
MAX_HTML = 2 * 1024 * 1024

STIJLKAART = """
u => u
strike => s
"""


class WordImportFout(ValueError):
    pass


def _controleer_grootte(bestand):
    try:
        with zipfile.ZipFile(bestand) as zf:
            uitgepakt = sum(info.file_size for info in zf.infolist())
    except zipfile.BadZipFile as e:
        raise WordImportFout("Dit bestand kon niet als Word-document (.docx) worden gelezen.") from e
    finally:
        bestand.seek(0)
    if uitgepakt > MAX_UITGEPAKT:
        mb, grens = uitgepakt // (1024 * 1024), MAX_UITGEPAKT // (1024 * 1024)
        raise WordImportFout(
            f"Dit document is uitgepakt {mb} MB; de grens is {grens} MB. "
            "Verwijder ingesloten bestanden of splits het document."
        )


@dataclass
class WordArtikel:
    titel: str
    inhoud: str
    afbeeldingen_overgeslagen: int = 0
    meldingen: list[str] = field(default_factory=list)


def _eerste_kop_als_titel(html: str) -> tuple[str, str]:
    """Haal de eerste kop uit de tekst en geef hem terug als titel.

    Veel werkinstructies beginnen met hun eigen titel als kop. Staat die kop ook in het artikel, dan
    leest hij als een dubbele titel. Dit is bewust een keuze van de redacteur: de opmaak in Word zegt
    niet betrouwbaar wat de bedoeling was.
    """
    m = re.search(r"<h[1-3]\b[^>]*>(.*?)</h[1-3]>", html, re.S | re.I)
    if not m:
        return "", html
    titel = _html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
    titel = re.sub(r"\s+", " ", titel)
    if not titel:
        return "", html
    return titel, (html[: m.start()] + html[m.end() :])


def _eerste_tabelrij_als_koprij(html: str) -> str:
    """Maak van de cellen in de eerste rij van elke tabel koppen (<th>).

    Mammoth levert alle cellen als <td>; welke rij een koprij was, is uit de Word-opmaak niet
    betrouwbaar af te leiden. Daarom ook dit als keuze van de redacteur.
    """

    def per_tabel(m):
        tabel = m.group(0)
        rij = re.search(r"<tr\b[^>]*>.*?</tr>", tabel, re.S | re.I)
        if not rij:
            return tabel
        if re.search(r"<table\b", rij.group(0), re.I):
            # Een geneste tabel in de eerste rij: dan weten we niet waar die rij ophoudt, en zouden we
            # ook de binnenste tabel een koprij geven. Zo'n tabel laten we met rust.
            return tabel
        nieuw = re.sub(r"<td(\b[^>]*)>", r'<th\1 scope="col">', rij.group(0), flags=re.I)
        nieuw = re.sub(r"</td>", "</th>", nieuw, flags=re.I)
        return tabel[: rij.start()] + nieuw + tabel[rij.end() :]

    return re.sub(r"<table\b.*?</table>", per_tabel, html, flags=re.S | re.I)


def lees_docx(
    bestand,
    bestandsnaam: str = "",
    *,
    kop_als_titel: bool = False,
    tabelkoprij: bool = False,
) -> WordArtikel:
    teller = {"afbeeldingen": 0}

    def geen_afbeelding(image):
        teller["afbeeldingen"] += 1
        return {"src": ""}

    _controleer_grootte(bestand)
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
    if len(html) > MAX_HTML:
        raise WordImportFout("Dit document is te groot om in één artikel te zetten. Splits het in meerdere artikelen.")
    # Op de plek van een afbeelding een duidelijke markering, zodat je ziet waar je iets moet aanvullen.
    # Het aantal markeringen is wat de redacteur in de tekst terugvindt, en dus wat we melden. De teller
    # van de omzetter liep daar soms één achter: mammoth roept de omzetter niet aan voor een plaatje dat
    # het zelf al niet kon lezen, maar laat er wel een <img> staan.
    html, aantal_markeringen = re.subn(r"<img\b[^>]*>", f"<em>{AFBEELDING_MARKERING}</em>", html)
    # Lege regels: meerdere achter elkaar worden er één; lege cellen en het begin/einde van het document niet.
    html = re.sub(r"(<p></p>)+", "<p><br></p>", html)
    html = re.sub(r"(<t[dh]>)<p><br></p>(</t[dh]>)", r"\1\2", html)
    html = re.sub(r"^(<p><br></p>)+|(<p><br></p>)+$", "", html.strip())

    titel = re.sub(r"[-_]+", " ", re.sub(r"\.docx$", "", bestandsnaam, flags=re.I)).strip() or "Nieuw artikel"
    uit_de_kop = ""
    if kop_als_titel:
        uit_de_kop, html = _eerste_kop_als_titel(html)
        if uit_de_kop:
            titel = uit_de_kop
    if tabelkoprij:
        html = _eerste_tabelrij_als_koprij(html)
    artikel = WordArtikel(
        titel=titel[:200],
        inhoud=schoon(html),
        afbeeldingen_overgeslagen=max(aantal_markeringen, teller["afbeeldingen"]),
    )
    if kop_als_titel and not uit_de_kop:
        artikel.meldingen.append(
            "Geen kop gevonden om als titel te gebruiken; de bestandsnaam is de titel geworden."
        )
    if artikel.afbeeldingen_overgeslagen:
        artikel.meldingen.append(
            f"{artikel.afbeeldingen_overgeslagen} afbeelding(en) overgeslagen: de kennisbank ondersteunt "
            f"nog geen afbeeldingen. Op die plekken staat nu '{AFBEELDING_MARKERING}'."
        )
    if not artikel.inhoud:
        artikel.meldingen.append("Het document bevatte geen tekst.")
    return artikel
