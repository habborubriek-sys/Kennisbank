"""Wat is er veranderd tussen twee versies van een artikeltekst? Voor de reviewer (stap C).

Werkt per blok (alinea, kop, opsommingsregel, tabelcel) en binnen een gewijzigd blok per woord, zoals
"wijzigingen bijhouden" in Word. De uitkomst is platte tekst met <ins> en <del>; opmaak (vet, links)
valt weg, zodat er geen HTML uit het artikel in deze weergave terechtkomt. De volledige nieuwe tekst
met opmaak staat ernaast.
"""

import difflib
import re
from html import escape
from html.parser import HTMLParser

from django.utils.safestring import mark_safe

#: Elementen die een nieuw blok beginnen.
BLOKKEN = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "blockquote", "pre", "section", "div", "tr"}
KOPPEN = {"h1", "h2", "h3", "h4", "h5", "h6"}


class _Blokken(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blokken = []  # [(soort, tekst)]
        self._stapel = []
        self._tekst = []
        # 1.30.0 (review 1.27.0, R3 B15): genummerde lijsten en onboarding zoals medewerkers ze zien.
        self._lijsten = []  # [[soort ("ul"/"ol"), teller]]
        self._divs = []  # per open <div>: is het een onboarding-blok?

    def _afsluiten(self):
        tekst = " ".join("".join(self._tekst).split())
        if tekst:
            soort = next((t for t in reversed(self._stapel) if t in KOPPEN), None)
            if soort is None and "li" in self._stapel:
                lijst = self._lijsten[-1] if self._lijsten else ["ul", 0]
                soort = f"ol:{lijst[1]}" if lijst[0] == "ol" else "li"
            soort = soort or "p"
            if any(self._divs):
                soort += "+onb"
            self.blokken.append((soort, tekst))
        self._tekst = []

    def handle_starttag(self, tag, attrs):
        if tag in BLOKKEN or tag in ("ul", "ol"):
            self._afsluiten()
        if tag == "br":
            self._tekst.append(" ")
        if tag in ("ul", "ol"):
            self._lijsten.append([tag, 0])
        elif tag == "li" and self._lijsten:
            self._lijsten[-1][1] += 1
        if tag == "div":
            self._divs.append("onboarding" in (dict(attrs).get("class") or "").split())
        self._stapel.append(tag)

    def handle_endtag(self, tag):
        if tag in BLOKKEN or tag in ("ul", "ol"):
            self._afsluiten()
        if tag in ("ul", "ol") and self._lijsten:
            self._lijsten.pop()
        if tag == "div" and self._divs:
            self._divs.pop()
        if tag in self._stapel:
            while self._stapel and self._stapel.pop() != tag:
                pass

    def handle_data(self, data):
        self._tekst.append(data)

    def close(self):
        super().close()
        self._afsluiten()


def blokken(html: str):
    p = _Blokken()
    p.feed(html or "")
    p.close()
    return p.blokken


_WOORDEN = re.compile(r"\s+|[^\s]+")


def woordverschil(oud: str, nieuw: str) -> str:
    """Eén regel: woorden die weg zijn in <del>, nieuwe woorden in <ins>. Ge-escaped."""
    a, b = _WOORDEN.findall(oud), _WOORDEN.findall(nieuw)
    uit = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            uit.append(escape("".join(a[i1:i2])))
            continue
        if op in ("delete", "replace") and "".join(a[i1:i2]).strip():
            uit.append(f"<del>{escape(''.join(a[i1:i2]))}</del>")
        if op in ("insert", "replace") and "".join(b[j1:j2]).strip():
            uit.append(f"<ins>{escape(''.join(b[j1:j2]))}</ins>")
    return "".join(uit)


def _blok_html(soort, inhoud, klasse=""):
    soort, _, extra = soort.partition("+")
    klassen = [klasse] if klasse else []
    if extra == "onb":
        klassen.append("vs-onb")
    if soort == "li" or soort.startswith("ol:"):
        # Het opsommingsteken of nummer komt uit de stylesheet, zodat het niet in een geselecteerd citaat belandt.
        klassen.insert(0, "vs-li")
        nr = ""
        if soort.startswith("ol:"):
            klassen.insert(1, "vs-ol")
            nr = f' data-nr="{int(soort[3:] or 0)}"'
        return f'<p class="{" ".join(klassen)}"{nr}>{inhoud}</p>'
    tag = soort if soort in KOPPEN else "p"
    attr = f' class="{" ".join(klassen)}"' if klassen else ""
    return f"<{tag}{attr}>{inhoud}</{tag}>"


def verschil_html(oud_html: str, nieuw_html: str):
    """De nieuwe tekst met de wijzigingen gemarkeerd. Geeft (html, aantal_gewijzigde_blokken)."""
    oud, nieuw = blokken(oud_html), blokken(nieuw_html)
    uit, gewijzigd = [], 0
    matcher = difflib.SequenceMatcher(None, [t for _, t in oud], [t for _, t in nieuw], autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            uit.extend(_blok_html(s, escape(t)) for s, t in nieuw[j1:j2])
            continue
        gewijzigd += max(i2 - i1, j2 - j1)
        if op == "replace":
            paren = list(zip(oud[i1:i2], nieuw[j1:j2], strict=False))
            for (_, ot), (ns, nt) in paren:
                uit.append(_blok_html(ns, woordverschil(ot, nt), "vs-gewijzigd"))
            for s, t in oud[i1 + len(paren) : i2]:
                uit.append(_blok_html(s, f"<del>{escape(t)}</del>", "vs-weg"))
            for s, t in nieuw[j1 + len(paren) : j2]:
                uit.append(_blok_html(s, f"<ins>{escape(t)}</ins>", "vs-nieuw"))
        elif op == "delete":
            uit.extend(_blok_html(s, f"<del>{escape(t)}</del>", "vs-weg") for s, t in oud[i1:i2])
        elif op == "insert":
            uit.extend(_blok_html(s, f"<ins>{escape(t)}</ins>", "vs-nieuw") for s, t in nieuw[j1:j2])
    return mark_safe("\n".join(uit)), gewijzigd  # noqa: S308 - alle tekst is ge-escaped
