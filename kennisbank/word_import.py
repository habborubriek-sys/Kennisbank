"""Een Word-document (.docx) omzetten naar een artikel met secties.

Regels:
- Koppen bepalen de secties. Staat er precies één 'Kop 1' bovenaan, dan is dat de titel en
  worden de 'Kop 2'-koppen de secties. Anders worden alle 'Kop 1'-koppen secties.
- De tekst vóór de eerste kop: de eerste alinea wordt de samenvatting, de rest komt in een
  sectie 'Inleiding'.
- Alinea's met de Word-stijl 'Onboarding' worden onboarding-blokken (zie docs/sjabloon-werkinstructie.docx).
- Opmaak (vet, cursief, onderstreept, lijsten, tabellen, links) blijft behouden. Afbeeldingen
  worden overgeslagen; het aantal wordt teruggemeld.
"""

import re
from dataclasses import dataclass, field

import mammoth

from .inhoud import ONBOARDING_KLASSE, naar_platte_tekst, schoon

STIJLKAART = f"""
p[style-name='Onboarding'] => div.{ONBOARDING_KLASSE} > p:fresh
p[style-name='onboarding'] => div.{ONBOARDING_KLASSE} > p:fresh
p[style-name='Title'] => h1.titel:fresh
p[style-name='Titel'] => h1.titel:fresh
u => u
strike => s
"""

_KOP = re.compile(r"<h([1-6])[^>]*>(.*?)</h\1>", re.S | re.I)


class WordImportFout(ValueError):
    pass


@dataclass
class WordSectie:
    kop: str
    inhoud: str


@dataclass
class WordArtikel:
    titel: str
    samenvatting: str
    secties: list[WordSectie] = field(default_factory=list)
    afbeeldingen_overgeslagen: int = 0
    meldingen: list[str] = field(default_factory=list)


def _tekst(html: str) -> str:
    return naar_platte_tekst(html)


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

    html = resultaat.value
    artikel = _splits(html, bestandsnaam)
    artikel.afbeeldingen_overgeslagen = teller["afbeeldingen"]
    if teller["afbeeldingen"]:
        artikel.meldingen.append(
            f"{teller['afbeeldingen']} afbeelding(en) overgeslagen: de kennisbank ondersteunt nog geen afbeeldingen."
        )
    return artikel


def _splits(html: str, bestandsnaam: str) -> WordArtikel:
    # Documenttitel (Word-stijl 'Titel') apart halen.
    titel = ""
    m = re.search(r'<h1 class="titel">(.*?)</h1>', html, re.S)
    if m:
        titel = _tekst(m.group(2) if m.lastindex and m.lastindex >= 2 else m.group(1))
        html = html[: m.start()] + html[m.end() :]

    koppen = [(int(n), _tekst(t), mm.start(), mm.end()) for mm in _KOP.finditer(html) for n, t in [mm.groups()]]
    niveaus = sorted({k[0] for k in koppen})

    sectieniveau = None
    if niveaus:
        hoogste = niveaus[0]
        aantal_hoogste = sum(1 for k in koppen if k[0] == hoogste)
        if not titel and aantal_hoogste == 1 and koppen[0][0] == hoogste and len(niveaus) > 1:
            # Eén bovenste kop = titel; de koppen op het niveau eronder worden de secties.
            titel = koppen[0][1]
            html = html[: koppen[0][2]] + html[koppen[0][3] :]
            koppen = [(int(n), _tekst(t), mm.start(), mm.end()) for mm in _KOP.finditer(html) for n, t in [mm.groups()]]
            sectieniveau = niveaus[1]
        else:
            sectieniveau = hoogste

    if not titel:
        titel = re.sub(r"[-_]+", " ", re.sub(r"\.docx$", "", bestandsnaam, flags=re.I)).strip() or "Nieuw artikel"

    sectiekoppen = [k for k in koppen if k[0] == sectieniveau] if sectieniveau else []
    stukken = []  # (kop, html)
    vooraf = html[: sectiekoppen[0][2]] if sectiekoppen else html
    for i, (_, kop, _start, einde) in enumerate(sectiekoppen):
        volgende = sectiekoppen[i + 1][2] if i + 1 < len(sectiekoppen) else len(html)
        stukken.append((kop, html[einde:volgende]))

    # Samenvatting: eerste alinea vóór de eerste kop.
    samenvatting = ""
    rest = vooraf
    m = re.search(r"<p>(.*?)</p>", vooraf, re.S)
    if m and ONBOARDING_KLASSE not in vooraf[: m.start()]:
        samenvatting = _tekst(m.group(1))[:1000]
        rest = vooraf[: m.start()] + vooraf[m.end() :]
    if schoon(rest):
        stukken.insert(0, ("Inleiding", rest))
    if not stukken:
        stukken.append(("Inhoud", vooraf if not samenvatting else ""))

    artikel = WordArtikel(titel=titel[:200], samenvatting=samenvatting)
    for kop, inhoud in stukken:
        inhoud = schoon(inhoud)
        if not inhoud and not kop:
            continue
        artikel.secties.append(WordSectie(kop=(kop or "Inhoud")[:200], inhoud=inhoud))
    if not samenvatting:
        artikel.meldingen.append(
            "Geen samenvatting gevonden: vul die zelf in (de eerste alinea vóór de eerste kop wordt de samenvatting)."
        )
    if not sectiekoppen:
        artikel.meldingen.append(
            "Geen koppen gevonden: alles staat in één sectie. Gebruik 'Kop 1' of 'Kop 2' in Word om secties te maken."
        )
    return artikel
