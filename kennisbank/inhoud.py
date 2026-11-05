"""Omzetten van Markdown (wat redacteuren schrijven) naar veilige HTML (wat de browser toont)."""

import re

import markdown
import nh3

TOEGESTANE_TAGS = {
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
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
    "span",
    "div",
}
TOEGESTANE_ATTRIBUTEN = {"a": {"href", "title"}, "th": {"scope"}}
TOEGESTANE_KLASSEN = {"span": {"flow-stap", "flow-pijl"}, "div": {"flow"}}


def naar_html(tekst: str) -> str:
    if not tekst:
        return ""
    ruw = markdown.markdown(tekst, extensions=["sane_lists", "tables"], output_format="html")
    return nh3.clean(
        ruw,
        tags=TOEGESTANE_TAGS,
        attributes=TOEGESTANE_ATTRIBUTEN,
        allowed_classes=TOEGESTANE_KLASSEN,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer",
    )


def naar_platte_tekst(tekst: str) -> str:
    """Markdown zonder opmaaktekens, voor zoeken en de assistent."""
    html = naar_html(tekst)
    tekst = re.sub(r"<[^>]+>", " ", html)
    tekst = tekst.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return re.sub(r"\s+", " ", tekst).strip()
