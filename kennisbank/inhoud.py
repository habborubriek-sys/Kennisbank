"""Opschonen van artikelinhoud.

Secties worden opgeslagen als HTML (uit de editor in het beheerscherm of uit een Word-import).
Alles wat de browser te zien krijgt gaat door `schoon()`: alleen de tags en attributen in de
allowlist blijven staan. Zo kan een redacteur (of een Word-document) nooit scripts, formulieren of
externe inhoud in de kennisbank zetten.

Een artikel is één tekst. Daarin:
- <h2 class="sectie">Kop</h2> is een sectiekop: alles tot de volgende sectiekop vormt een in- en
  uitklapbare sectie. Tekst vóór de eerste sectiekop is de inleiding (altijd zichtbaar).
- <div class="onboarding">…</div> is uitleg voor nieuwe collega's; alleen zichtbaar met de
  schakelaar 'Onboarding' aan. Mag overal en meerdere keren voorkomen.
"""

import re

import nh3

ONBOARDING_KLASSE = "onboarding"
SECTIE_KLASSE = "sectie"

TOEGESTANE_TAGS = {
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "sub",
    "sup",
    "ul",
    "ol",
    "li",
    "a",
    "code",
    "pre",
    "blockquote",
    "h2",
    "h3",
    "h4",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "hr",
    "div",
    "span",
}
TOEGESTANE_ATTRIBUTEN = {
    "a": {"href", "title"},
    "th": {"scope", "colspan", "rowspan"},
    "td": {"colspan", "rowspan"},
    "ol": {"start"},
}
TOEGESTANE_KLASSEN = {"div": {ONBOARDING_KLASSE}, "h2": {SECTIE_KLASSE}}

# Gewone koppen uit Word/editor terugbrengen naar h3/h4 (binnen de tekst). Alleen h2.sectie blijft h2.
_KOP_OMLAAG = [("h1", "h3"), ("h2", "h3"), ("h5", "h4"), ("h6", "h4")]
_TAG = re.compile(r"<[^>]+>")
_WIT = re.compile(r"\s+")
_SECTIEKOP = re.compile(rf'<h2 class="{SECTIE_KLASSE}">(.*?)</h2>', re.S)
_PLACEHOLDER = "\x00SECTIEKOP\x00"


def _koppen_normaliseren(html: str) -> str:
    # Sectiekoppen tijdelijk beschermen, zodat alleen gewone h2's omlaag gaan.
    html = re.sub(rf"""<h2\s+class=["']{SECTIE_KLASSE}["']\s*>""", _PLACEHOLDER, html, flags=re.I)
    bewaard = []

    def _bewaar(m):
        bewaard.append(m.group(0))
        return f"\x00KOP{len(bewaard) - 1}\x00"

    html = re.sub(rf"{_PLACEHOLDER}(.*?)</h2\s*>", _bewaar, html, flags=re.S | re.I)
    for van, naar in _KOP_OMLAAG:
        html = re.sub(rf"<{van}(\s[^>]*)?>", f"<{naar}>", html, flags=re.I)
        html = re.sub(rf"</{van}\s*>", f"</{naar}>", html, flags=re.I)
    for i, kop in enumerate(bewaard):
        kop = kop.replace(_PLACEHOLDER, f'<h2 class="{SECTIE_KLASSE}">')
        html = html.replace(f"\x00KOP{i}\x00", kop)
    return html


def schoon(html: str) -> str:
    """Maak HTML veilig voor weergave. Idempotent: schoon(schoon(x)) == schoon(x)."""
    if not html or not html.strip():
        return ""
    html = _koppen_normaliseren(html)
    # Editors schrijven soms <b>/<i>; standaardiseren naar strong/em.
    html = re.sub(r"<(/?)b(\s[^>]*)?>", r"<\1strong>", html, flags=re.I)
    html = re.sub(r"<(/?)i(\s[^>]*)?>", r"<\1em>", html, flags=re.I)
    schoon_html = nh3.clean(
        html,
        tags=TOEGESTANE_TAGS,
        attributes=TOEGESTANE_ATTRIBUTEN,
        allowed_classes=TOEGESTANE_KLASSEN,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer",
        strip_comments=True,
    )
    # Lege alinea's die editors achterlaten.
    schoon_html = re.sub(r"<p>(\s|&nbsp;|<br>)*</p>", "", schoon_html)
    schoon_html = schoon_html.replace('<div class="">', "<div>")
    return schoon_html.strip()


def splits_secties(html: str) -> tuple[str, list[tuple[str, str]]]:
    """Deel de artikeltekst op: (inleiding_html, [(kop, sectie_html), ...]).

    Sectiekoppen zonder tekst worden overgeslagen. Een lege sectie (kop zonder inhoud) blijft bestaan.
    """
    html = schoon(html)
    delen = _SECTIEKOP.split(html)
    inleiding = delen[0].strip()
    secties = []
    for i in range(1, len(delen), 2):
        kop = _WIT.sub(" ", _TAG.sub("", delen[i])).strip()
        tekst = delen[i + 1].strip() if i + 1 < len(delen) else ""
        if not kop:
            # Lege sectiekop: de tekst erna hoort bij wat ervoor stond.
            if secties:
                secties[-1] = (secties[-1][0], (secties[-1][1] + tekst).strip())
            else:
                inleiding = (inleiding + tekst).strip()
            continue
        secties.append((kop[:200], tekst))
    return inleiding, secties


def sectiekop(kop: str) -> str:
    import html as _html

    return f'<h2 class="{SECTIE_KLASSE}">{_html.escape(kop)}</h2>'


def naar_platte_tekst(html: str) -> str:
    """Tekst zonder opmaak, voor de assistent en zoekfragmenten."""
    tekst = _TAG.sub(" ", schoon(html))
    tekst = (
        tekst.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&nbsp;", " ")
    )
    return _WIT.sub(" ", tekst).strip()


def zonder_onboarding(html: str) -> str:
    """De inhoud zonder de onboarding-blokken."""
    return re.sub(rf'<div class="{ONBOARDING_KLASSE}">.*?</div>', "", schoon(html), flags=re.S)


def onboarding_blokken(html: str) -> list[str]:
    return re.findall(rf'<div class="{ONBOARDING_KLASSE}">(.*?)</div>', schoon(html), flags=re.S)


def onboarding_blok(html: str) -> str:
    inhoud = schoon(html)
    return f'<div class="{ONBOARDING_KLASSE}">{inhoud}</div>' if inhoud else ""


def markdown_naar_html(tekst: str) -> str:
    """Voor oude inhoud (versie 1 van het importformaat en de eerste installaties): Markdown → HTML."""
    if not tekst:
        return ""
    import markdown

    return schoon(markdown.markdown(tekst, extensions=["sane_lists", "tables"], output_format="html"))
