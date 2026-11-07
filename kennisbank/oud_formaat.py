"""Bevroren omzettingen van oudere inhoudsvormen.

Gebruikt door de migraties 0002 en 0004 en door het inlezen van oude importformaten (versie 1 t/m 3).
Deze functies mogen NIET meegroeien met kennisbank/inhoud.py: een migratie moet over een jaar nog
precies hetzelfde doen als vandaag. Wijzig dit bestand daarom niet; voeg bij een volgende omzetting
een nieuwe functie toe.
"""

import re

import nh3

# --- Opschoning zoals die gold toen de HTML-inhoud werd ingevoerd (1.1 / 1.3) -----------------

_TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "s", "sub", "sup", "ul", "ol", "li", "a", "code", "pre",
    "blockquote", "h2", "section", "h3", "h4", "table", "thead", "tbody", "tr", "th", "td", "hr", "div", "span",
}  # fmt: skip
_ATTRIBUTEN = {
    "a": {"href", "title"},
    "th": {"scope", "colspan", "rowspan"},
    "td": {"colspan", "rowspan"},
    "ol": {"start"},
}
_KLASSEN = {"div": {"onboarding"}, "section": {"sectie"}, "h2": {"sectie", "sectie-kop"}}


_KOP_OMLAAG = [("h1", "h3"), ("h2", "h3"), ("h5", "h4"), ("h6", "h4")]


def schoon_bevroren(html: str) -> str:
    """Kopie van kennisbank.inhoud.schoon uit versie 1.1.0 (de versie waarmee migratie 0002 is geschreven):
    koppen h1/h2 → h3 en h5/h6 → h4 (behalve sectiekoppen), b/i → strong/em, allowlist, lege alinea's weg."""
    if not html or not html.strip():
        return ""
    # Sectiekoppen (h2 met klasse sectie of sectie-kop) beschermen; alle andere koppen gaan omlaag.
    bewaard = []

    def _bewaar(m):
        bewaard.append(m.group(0))
        return f"\x00KOP{len(bewaard) - 1}\x00"

    html = re.sub(r"""<h2\s+class=["']sectie(?:-kop)?["'][^>]*>.*?</h2\s*>""", _bewaar, html, flags=re.S | re.I)
    for van, naar in _KOP_OMLAAG:
        html = re.sub(rf"<{van}(\s[^>]*)?>", f"<{naar}>", html, flags=re.I)
        html = re.sub(rf"</{van}\s*>", f"</{naar}>", html, flags=re.I)
    for i, kop in enumerate(bewaard):
        html = html.replace(f"\x00KOP{i}\x00", kop)
    html = re.sub(r"<(/?)b(\s[^>]*)?>", r"<\1strong>", html, flags=re.I)
    html = re.sub(r"<(/?)i(\s[^>]*)?>", r"<\1em>", html, flags=re.I)
    uit = nh3.clean(
        html,
        tags=_TAGS,
        attributes=_ATTRIBUTEN,
        allowed_classes=_KLASSEN,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer",
        strip_comments=True,
    )
    uit = re.sub(r"<p>(\s|&nbsp;|<br>)*</p>", "", uit)  # lege alinea's die editors achterlaten (gedrag 1.1)
    return uit.replace('<div class="">', "<div>").strip()


def markdown_naar_html_bevroren(tekst: str) -> str:
    """Importformaat versie 1 en migratie 0002: Markdown → HTML."""
    if not tekst:
        return ""
    import markdown

    return schoon_bevroren(markdown.markdown(tekst, extensions=["sane_lists", "tables"], output_format="html"))


def onboarding_blok_bevroren(html: str) -> str:
    inhoud = schoon_bevroren(html)
    return f'<div class="onboarding">{inhoud}</div>' if inhoud else ""


# --- Migratie 0004 en importformaat versie 3: sectiekoppen → sectiekaders ------------------------

_KOP = re.compile(r'<h2 class="sectie">(.*?)</h2>', re.S)


def koppen_naar_kaders(html: str) -> str:
    """Oude vorm: alles na een sectiekop tot de volgende sectiekop wordt een sectiekader."""
    if not html or '<h2 class="sectie">' not in html:
        return html or ""
    delen = _KOP.split(html)
    uit = delen[0]
    for i in range(1, len(delen), 2):
        kop = re.sub(r"<[^>]+>", "", delen[i]).strip()
        inhoud = delen[i + 1] if i + 1 < len(delen) else ""
        uit += f'<section class="sectie"><h2 class="sectie-kop">{kop}</h2>{inhoud}</section>'
    return uit


_SECTIE = re.compile(r'<section class="sectie">\s*(?:<h2 class="sectie-kop">(.*?)</h2>)?(.*?)</section>', re.S)
_TAG = re.compile(r"<[^>]+>")
_WIT = re.compile(r"\s+")


def blokken_bevroren(html: str) -> list[dict]:
    """Zoals kennisbank.inhoud.blokken in versie 1.3, voor het herbouwen van de sectietabel in migratie 0004."""
    html = schoon_bevroren(html)
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
