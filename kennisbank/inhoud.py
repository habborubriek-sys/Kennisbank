"""Opschonen van artikelinhoud.

Secties worden opgeslagen als HTML (uit de editor in het beheerscherm of uit een Word-import).
Alles wat de browser te zien krijgt gaat door `schoon()`: alleen de tags en attributen in de
allowlist blijven staan. Zo kan een redacteur (of een Word-document) nooit scripts, formulieren of
externe inhoud in de kennisbank zetten.

Een artikel is één tekst. Daarin:
- <section class="sectie"><h2 class="sectie-kop">Titel</h2>…</section> is een in- en uitklapbare
  sectie: een kader om een stuk tekst, met een titel. Tekst buiten een sectie (ervoor, ertussen,
  erna) is altijd zichtbaar.
- <div class="onboarding">…</div> is uitleg voor nieuwe collega's; alleen zichtbaar met de
  schakelaar 'Onboarding' aan. Mag overal en meerdere keren voorkomen, ook binnen een sectie.
"""

import re

import nh3

ONBOARDING_KLASSE = "onboarding"
SECTIE_KLASSE = "sectie"
SECTIEKOP_KLASSE = "sectie-kop"

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
    "section",
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
TOEGESTANE_KLASSEN = {"div": {ONBOARDING_KLASSE}, "section": {SECTIE_KLASSE}, "h2": {SECTIEKOP_KLASSE}}

# Gewone koppen uit Word/editor terugbrengen naar h3/h4 (binnen de tekst). Alleen h2.sectie blijft h2.
_KOP_OMLAAG = [("h1", "h3"), ("h2", "h3"), ("h5", "h4"), ("h6", "h4")]
_TAG = re.compile(r"<[^>]+>")
_WIT = re.compile(r"\s+")
_SECTIE = re.compile(
    rf'<section class="{SECTIE_KLASSE}">\s*(?:<h2 class="{SECTIEKOP_KLASSE}">(.*?)</h2>)?(.*?)</section>', re.S
)
_PLACEHOLDER = "\x00SECTIEKOP\x00"


def _koppen_normaliseren(html: str) -> str:
    # Sectiekoppen tijdelijk beschermen, zodat alleen gewone h2's omlaag gaan.
    html = re.sub(rf"""<h2\s+class=["']{SECTIEKOP_KLASSE}["'][^>]*>""", _PLACEHOLDER, html, flags=re.I)
    bewaard = []

    def _bewaar(m):
        bewaard.append(m.group(0))
        return f"\x00KOP{len(bewaard) - 1}\x00"

    html = re.sub(rf"{_PLACEHOLDER}(.*?)</h2\s*>", _bewaar, html, flags=re.S | re.I)
    for van, naar in _KOP_OMLAAG:
        html = re.sub(rf"<{van}(\s[^>]*)?>", f"<{naar}>", html, flags=re.I)
        html = re.sub(rf"</{van}\s*>", f"</{naar}>", html, flags=re.I)
    for i, kop in enumerate(bewaard):
        kop = kop.replace(_PLACEHOLDER, f'<h2 class="{SECTIEKOP_KLASSE}">')
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
    schoon_html = _ontnest_secties(schoon_html)
    return schoon_html.strip()


def _ontnest_secties(html: str) -> str:
    """Een sectie in een sectie kan niet: de binnenste wordt gewone tekst (titel wordt een kop)."""
    uit, diepte, i = [], 0, 0
    for m in re.finditer(rf'<section class="{SECTIE_KLASSE}">|</section>', html):
        uit.append(html[i : m.start()])
        if m.group(0).startswith("<section"):
            diepte += 1
            if diepte == 1:
                uit.append(m.group(0))
        else:
            if diepte == 1:
                uit.append(m.group(0))
            diepte = max(0, diepte - 1)
        i = m.end()
    uit.append(html[i:])
    html = "".join(uit)
    # Titels van weggehaalde binnenste secties worden gewone koppen.
    delen = _SECTIE.split(html)  # [tekst, kop, inhoud, tekst, kop, inhoud, ...]
    for j in range(len(delen)):
        if j % 3 != 1:  # alles behalve de echte sectietitels
            delen[j] = re.sub(rf'<h2 class="{SECTIEKOP_KLASSE}">(.*?)</h2>', r"<h3>\1</h3>", delen[j] or "", flags=re.S)
    herbouwd = delen[0]
    for j in range(1, len(delen), 3):
        kop = delen[j] or ""
        herbouwd += (
            f'<section class="{SECTIE_KLASSE}"><h2 class="{SECTIEKOP_KLASSE}">{kop}</h2>'
            f"{delen[j + 1]}</section>{delen[j + 2]}"
        )
    return herbouwd


def blokken(html: str) -> list[dict]:
    """Deel de artikeltekst op in blokken, in leesvolgorde.

    [{"type": "tekst", "html": ...}, {"type": "sectie", "nummer": 1, "kop": ..., "html": ...}, ...]
    Een sectie zonder titel krijgt de kop "Sectie n". Lege tekstblokken worden overgeslagen.
    """
    html = schoon(html)
    uit, pos, n = [], 0, 0
    for m in _SECTIE.finditer(html):
        tussen = html[pos : m.start()].strip()
        if tussen:
            uit.append({"type": "tekst", "html": tussen})
        n += 1
        kop = _WIT.sub(" ", _TAG.sub("", m.group(1) or "")).replace("&nbsp;", " ").strip()
        uit.append({"type": "sectie", "nummer": n, "kop": (kop or f"Sectie {n}")[:200], "html": m.group(2).strip()})
        pos = m.end()
    rest = html[pos:].strip()
    if rest:
        uit.append({"type": "tekst", "html": rest})
    return uit


def sectie(kop: str, inhoud_html: str) -> str:
    """Bouw een sectie-kader (voor imports en migraties)."""
    import html as _html

    return (
        f'<section class="{SECTIE_KLASSE}"><h2 class="{SECTIEKOP_KLASSE}">{_html.escape(kop)}</h2>'
        f"{schoon(inhoud_html)}</section>"
    )


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
