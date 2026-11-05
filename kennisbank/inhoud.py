"""Opschonen van artikelinhoud.

Secties worden opgeslagen als HTML (uit de editor in het beheerscherm of uit een Word-import).
Alles wat de browser te zien krijgt gaat door `schoon()`: alleen de tags en attributen in de
allowlist blijven staan. Zo kan een redacteur (of een Word-document) nooit scripts, formulieren of
externe inhoud in de kennisbank zetten.

Onboarding-uitleg is een blok in de inhoud: <div class="onboarding">…</div>. Een sectie kan er
meerdere bevatten; de frontend toont ze alleen als de gebruiker de schakelaar 'Onboarding' aanzet.
"""

import re

import nh3

ONBOARDING_KLASSE = "onboarding"

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
TOEGESTANE_KLASSEN = {"div": {ONBOARDING_KLASSE}}

# Koppen uit Word/editor die te hoog zijn voor binnen een sectie, terugbrengen naar h3/h4.
_KOP_OMLAAG = [("h1", "h3"), ("h2", "h3"), ("h5", "h4"), ("h6", "h4")]
_TAG = re.compile(r"<[^>]+>")
_WIT = re.compile(r"\s+")


def _koppen_normaliseren(html: str) -> str:
    for van, naar in _KOP_OMLAAG:
        html = re.sub(rf"<{van}(\s[^>]*)?>", f"<{naar}>", html, flags=re.I)
        html = re.sub(rf"</{van}\s*>", f"</{naar}>", html, flags=re.I)
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
