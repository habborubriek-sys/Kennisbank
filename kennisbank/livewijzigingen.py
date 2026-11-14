"""Wat is er in de live versie veranderd sinds het concept begon, en wat doet het concept ermee? (1.33.0)

Er zijn drie teksten in het spel:

- de **basis**: de versie waar het concept van is afgeleid (``Conceptversie.basis_versie``);
- **live**: wat medewerkers nu zien (het artikel zelf);
- het **concept**: wat de redacteur op dit moment in het bewerkscherm heeft staan.

Wie de live versie verbetert terwijl er een concept ligt, verandert alleen *live*. Deze module zet basis en
live naast elkaar (wat is er live veranderd?) en kijkt per wijziging wat het concept met dezelfde alinea heeft
gedaan. Daaruit volgt de soort:

``veilig``      de alinea is in het concept niet aangeraakt: overnemen kan zonder iets te verliezen;
``nieuw``       de alinea is live toegevoegd en staat nog niet in het concept;
``verwijderd``  de alinea is live weggehaald en staat nog ongewijzigd in het concept;
``zelf``        de redacteur heeft dezelfde alinea in het concept zelf ook gewijzigd: met de hand aanpassen;
``weg``         de alinea staat niet meer in het concept: er is niets over te nemen.

Er wordt naar **tekst** gekeken, per alinea, kop, opsommingspunt of tabelcel. Een wijziging in alleen de
opmaak (vet, een link naar een ander adres) valt er dus buiten; dat staat in de documentatie.

De module schrijft niets weg. Overnemen levert een nieuwe tekst op die het bewerkscherm in de editor zet; hij
is pas van het concept als de redacteur opslaat.
"""

from __future__ import annotations

import difflib
import hashlib
import re
from html import escape
from html.parser import HTMLParser

from .verschil import woordverschil

#: De kleinste stukken tekst waar we naar kijken. Een <li> of <td> met een <p> erin telt als die <p>.
EENHEDEN = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "li", "td", "th"}
_LEEG = {"br", "hr", "img", "input", "col", "wbr"}
#: Vanaf deze gelijkenis (0-1, per woord) zien we twee alinea's als "dezelfde alinea, gewijzigd".
DREMPEL = 0.5
#: Wat een redacteur over een wijziging kan besluiten zonder dat het aan de tekst te zien is.
BESLUITEN = {"niet", "aangepast", "gezien"}
MAX_BESLUITEN = 500

_WIT = re.compile(r"\s+")


class Knoop:
    __slots__ = ("tag", "klassen", "ouder", "kinderen", "begin", "eind", "binnen_begin", "binnen_eind", "stukken")

    def __init__(self, tag, klassen=(), ouder=None, begin=0):
        self.tag = tag
        self.klassen = set(klassen)
        self.ouder = ouder
        self.kinderen = []
        self.begin = begin
        self.eind = begin
        self.binnen_begin = begin
        self.binnen_eind = begin
        self.stukken = []  # tekst en kindknopen, in volgorde

    def tekst(self) -> str:
        delen = []

        def loop(k):
            for s in k.stukken:
                if isinstance(s, str):
                    delen.append(s)
                elif s.tag == "br":
                    delen.append(" ")
                else:
                    loop(s)

        loop(self)
        return " ".join("".join(delen).split())

    def afstammelingen(self):
        for k in self.kinderen:
            yield k
            yield from k.afstammelingen()


class _Boom(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.html = html
        self._regels = [0]
        for m in re.finditer("\n", html):
            self._regels.append(m.end())
        self.wortel = Knoop("", begin=0)
        self.wortel.binnen_eind = self.wortel.eind = len(html)
        self._nu = self.wortel
        self.feed(html)
        self.close()
        while self._nu is not self.wortel:
            self._sluit(self._nu, len(html), len(html))

    def _pos(self) -> int:
        regel, kolom = self.getpos()
        return self._regels[regel - 1] + kolom

    def _sluit(self, knoop, binnen_eind, eind):
        knoop.binnen_eind = binnen_eind
        knoop.eind = eind
        self._nu = knoop.ouder or self.wortel

    def handle_starttag(self, tag, attrs):
        begin = self._pos()
        ruw = self.get_starttag_text() or ""
        k = Knoop(tag, (dict(attrs).get("class") or "").split(), self._nu, begin)
        k.binnen_begin = k.binnen_eind = k.eind = begin + len(ruw)
        self._nu.kinderen.append(k)
        self._nu.stukken.append(k)
        if tag not in _LEEG:
            self._nu = k

    def handle_startendtag(self, tag, attrs):
        nu = self._nu
        self.handle_starttag(tag, attrs)
        self._nu = nu

    def handle_endtag(self, tag):
        begin = self._pos()
        eind = self.html.find(">", begin) + 1 or len(self.html)
        k = self._nu
        while k is not self.wortel and k.tag != tag:
            k = k.ouder
        if k is self.wortel:
            return  # een sluittag zonder begin: overslaan
        while self._nu is not k:
            self._sluit(self._nu, begin, begin)
        self._sluit(k, begin, eind)

    def handle_data(self, data):
        self._nu.stukken.append(data)


class Eenheid:
    __slots__ = ("knoop", "tekst", "sleutel", "sectie", "soort", "nr")

    def __init__(self, knoop, tekst, sectie, soort):
        self.knoop = knoop
        self.tekst = tekst
        #: Zonder witruimte: zo vindt het bewerkscherm dezelfde alinea terug in de editor.
        self.sleutel = _WIT.sub("", tekst)
        self.sectie = sectie
        self.soort = soort
        self.nr = 0  # de hoeveelste eenheid met deze sleutel in de tekst (vanaf 0)


class Tekst:
    """Een artikeltekst, ontleed in eenheden met hun plek in de bron."""

    def __init__(self, html: str):
        self.html = html or ""
        self.wortel = _Boom(self.html).wortel
        self.eenheden: list[Eenheid] = []
        geteld: dict[str, int] = {}
        for k in self.wortel.afstammelingen():
            if k.tag not in EENHEDEN or any(a.tag in EENHEDEN for a in k.afstammelingen()):
                continue
            tekst = k.tekst()
            if not tekst:
                continue
            e = Eenheid(k, tekst, _sectie_van(k), _soort_van(k))
            e.nr = geteld.get(e.sleutel, 0)
            geteld[e.sleutel] = e.nr + 1
            self.eenheden.append(e)
        self._van_knoop = {id(e.knoop): i for i, e in enumerate(self.eenheden)}

    def binnen(self, knoop) -> list[int]:
        """De nummers van de eenheden in (of gelijk aan) deze knoop."""
        uit = []
        if id(knoop) in self._van_knoop:
            uit.append(self._van_knoop[id(knoop)])
        for a in knoop.afstammelingen():
            if id(a) in self._van_knoop:
                uit.append(self._van_knoop[id(a)])
        return uit

    def bron(self, knoop) -> str:
        return self.html[knoop.begin : knoop.eind]


def _sectie_van(knoop) -> str:
    k = knoop
    while k is not None:
        if k.tag == "section":
            kop = next((c for c in k.kinderen if c.tag == "h2"), None)
            return kop.tekst() if kop else ""
        k = k.ouder
    return ""


def _soort_van(knoop) -> str:
    if knoop.tag.startswith("h"):
        return "kop"
    k = knoop
    while k is not None and k.tag:
        if k.tag == "li":
            return "opsommingspunt"
        if k.tag in ("td", "th"):
            return "tabelcel"
        k = k.ouder
    return "alinea"


def _gelijkenis(a: str, b: str) -> float:
    per_woord = difflib.SequenceMatcher(None, a.split(), b.split(), autojunk=False).ratio()
    if per_woord >= DREMPEL or min(len(a), len(b)) > 80:
        return per_woord
    # Een korte regel bestaat uit zo weinig woorden dat één ander woord al "heel anders" lijkt: kijk per letter.
    return max(per_woord, difflib.SequenceMatcher(None, a, b, autojunk=False).ratio())


def _paren(a: list[str], b: list[str]) -> list[tuple[int, int]]:
    """Welke alinea uit a hoort bij welke uit b, binnen één gewijzigd stuk? In volgorde, alleen als ze genoeg
    op elkaar lijken. Zoekt de koppeling met de meeste gelijkenis (als een langste gemeenschappelijke rij)."""
    n, m = len(a), len(b)
    if not n or not m:
        return []
    if n * m > 4000:  # een heel groot herschreven stuk: op volgorde koppelen is dan goed genoeg
        return [(i, i) for i in range(min(n, m)) if _gelijkenis(a[i], b[i]) >= DREMPEL]
    score = [[_gelijkenis(x, y) for y in b] for x in a]
    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            w = max(best[i + 1][j], best[i][j + 1])
            if score[i][j] >= DREMPEL:
                w = max(w, score[i][j] + best[i + 1][j + 1])
            best[i][j] = w
    uit, i, j = [], 0, 0
    while i < n and j < m:
        if score[i][j] >= DREMPEL and best[i][j] == score[i][j] + best[i + 1][j + 1]:
            uit.append((i, j))
            i, j = i + 1, j + 1
        elif best[i + 1][j] >= best[i][j + 1]:
            i += 1
        else:
            j += 1
    return uit


def koppel(a: Tekst, b: Tekst) -> tuple[dict[int, tuple[int, bool]], list[int]]:
    """Leg de eenheden van a naast die van b.

    Geeft (naar, los): ``naar[i] = (j, gelijk)`` voor eenheid i van a die in b terugkomt (gelijk of
    gewijzigd), en ``los`` met de eenheden van b die nergens bij horen (nieuw in b).
    """
    ta = [e.sleutel for e in a.eenheden]
    tb = [e.sleutel for e in b.eenheden]
    naar: dict[int, tuple[int, bool]] = {}
    bezet = set()
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
        if op == "equal":
            for d in range(i2 - i1):
                naar[i1 + d] = (j1 + d, True)
                bezet.add(j1 + d)
        elif op == "replace" and i2 - i1 == 1 and j2 - j1 == 1:
            # Eén alinea op de plek van één alinea: dezelfde alinea, hoe grondig hij ook is herschreven.
            naar[i1] = (j1, False)
            bezet.add(j1)
        elif op == "replace":
            for i, j in _paren([e.tekst for e in a.eenheden[i1:i2]], [e.tekst for e in b.eenheden[j1:j2]]):
                naar[i1 + i] = (j1 + j, False)
                bezet.add(j1 + j)
    return naar, [j for j in range(len(tb)) if j not in bezet]


def _id(*delen) -> str:
    return hashlib.sha1("\x1f".join(str(d) for d in delen).encode(), usedforsecurity=False).hexdigest()[:16]


def _klim(tekst: Tekst, knoop, eigen: set[int]):
    """De grootste knoop rond ``knoop`` die alleen eenheden uit ``eigen`` bevat (een <li> om een <p>, een hele
    nieuwe lijst, een hele nieuwe sectie)."""
    k = knoop
    while k.ouder is not None and k.ouder.tag and set(tekst.binnen(k.ouder)) <= eigen:
        k = k.ouder
    return k


class Vergelijking:
    """Basis, live en concept naast elkaar. ``wijzigingen`` is de lijst voor het paneel."""

    def __init__(self, basis: dict, live: dict, concept: dict, besluiten: dict | None = None):
        self.basis_velden, self.live_velden, self.concept_velden = basis, live, concept
        self.besluiten = besluiten or {}
        self.basis = Tekst(basis.get("inhoud") or "")
        self.live = Tekst(live.get("inhoud") or "")
        self.concept = Tekst(concept.get("inhoud") or "")
        self.b_l, self.l_nieuw = koppel(self.basis, self.live)
        self.b_c, self.c_nieuw = koppel(self.basis, self.concept)
        self.l_b = {j: (i, gelijk) for i, (j, gelijk) in self.b_l.items()}
        self._acties: dict[str, tuple] = {}
        self.wijzigingen = self._velden() + self._inhoud()
        for w in self.wijzigingen:
            w["stand"], w["door"] = self._stand(w)

    # --- titel en samenvatting -------------------------------------------------------------

    def _velden(self) -> list[dict]:
        uit = []
        for naam, label in (("titel", "Titel"), ("samenvatting", "Samenvatting")):
            oud = (self.basis_velden.get(naam) or "").strip()
            nieuw = (self.live_velden.get(naam) or "").strip()
            if oud == nieuw:
                continue
            mijn = (self.concept_velden.get(naam) or "").strip()
            wid = _id("veld", naam, oud, nieuw)
            w = {
                "id": wid,
                "sectie": label,
                "plek": "",
                "live": woordverschil(oud, nieuw),
                "anker": {"veld": naam},
                "auto": False,
                "klaar": mijn == nieuw,
            }
            if mijn == nieuw:
                w["soort"] = "veilig"
            elif mijn == oud:
                w["soort"] = "veilig"
                w["auto"] = True
                self._acties[wid] = ("veld", naam, nieuw)
            else:
                w["soort"] = "zelf"
            uit.append(w)
        return uit

    # --- de tekst --------------------------------------------------------------------------

    def _concept_van_live(self, j: int, los: dict[str, list[int]]) -> int | None:
        """De eenheid in het concept die bij eenheid j van live hoort: via de basis, of (voor een alinea die
        live nieuw is) omdat dezelfde tekst er al in staat."""
        if j in self.l_b:
            c = self.b_c.get(self.l_b[j][0])
            return c[0] if c else None
        rij = los.get(self.live.eenheden[j].sleutel)
        return rij[0] if rij else None

    def _inhoud(self) -> list[dict]:
        L, C, B = self.live.eenheden, self.concept.eenheden, self.basis.eenheden
        # Tekst die alleen in het concept staat (niet uit de basis): daaraan zien we wat al is overgenomen.
        los: dict[str, list[int]] = {}
        for k in self.c_nieuw:
            los.setdefault(C[k].sleutel, []).append(k)
        rijen = []  # (volgorde in live, wijziging)

        # 1. Gewijzigd: de alinea bestond al en heeft live een andere tekst gekregen.
        for i, (j, gelijk) in sorted(self.b_l.items()):
            if gelijk:
                continue
            oud, nieuw = B[i], L[j]
            wid = _id("gewijzigd", oud.sleutel, nieuw.sleutel, oud.nr)
            w = self._rij(wid, nieuw, woordverschil(oud.tekst, nieuw.tekst))
            c = self.b_c.get(i)
            if c is None:
                w["soort"] = "weg"
                w["klaar"] = bool(los.get(nieuw.sleutel))
                if w["klaar"]:
                    w["anker"] = self._anker(C[los[nieuw.sleutel][0]])
            else:
                k, onaangeraakt = c
                w["anker"] = self._anker(C[k])
                if C[k].sleutel == nieuw.sleutel:
                    w["soort"], w["klaar"] = "veilig", True
                elif onaangeraakt:
                    w["soort"], w["auto"] = "veilig", True
                    self._acties[wid] = ("vervang", k, j)
                else:
                    w["soort"] = "zelf"
                    w["concept"] = C[k].tekst
            rijen.append(((j, 1), w))

        # 2. Verwijderd: de alinea is live weggehaald.
        volgende_live = len(L)
        na: dict[int, int] = {}
        for i in range(len(B) - 1, -1, -1):
            if i in self.b_l:
                volgende_live = self.b_l[i][0]
            na[i] = volgende_live
        for i, oud in enumerate(B):
            if i in self.b_l:
                continue
            wid = _id("verwijderd", oud.sleutel, oud.nr)
            w = self._rij(wid, oud, f"<del>{escape(oud.tekst)}</del>")
            c = self.b_c.get(i)
            if c is None:
                w["soort"], w["klaar"] = "verwijderd", True
            else:
                k, onaangeraakt = c
                w["anker"] = self._anker(C[k])
                doel = _klim(self.concept, C[k].knoop, {k})
                # Een cel uit een tabel halen of een sectie zonder titel achterlaten: dat doet de redacteur zelf.
                kan = doel.tag not in ("td", "th") and "sectie-kop" not in doel.klassen
                if onaangeraakt and kan:
                    w["soort"], w["auto"] = "verwijderd", True
                    self._acties[wid] = ("verwijder", k)
                elif onaangeraakt:
                    w["soort"] = "verwijderd"
                else:
                    w["soort"] = "zelf"
                    w["concept"] = C[k].tekst
            rijen.append(((na[i], 0), w))

        # 3. Nieuw: live toegevoegd. Wat bij elkaar hoort (een hele lijst, een hele sectie) is één wijziging.
        nieuw_set = set(self.l_nieuw)
        groepen: dict[int, list[int]] = {}
        knopen = {}
        for j in self.l_nieuw:
            top = _klim(self.live, L[j].knoop, nieuw_set)
            groepen.setdefault(id(top), []).append(j)
            knopen[id(top)] = top
        for sleutel, leden in groepen.items():
            top = knopen[sleutel]
            eerste = L[leden[0]]
            wid = _id("nieuw", *[L[j].sleutel for j in leden], eerste.nr)
            w = self._rij(wid, eerste, "".join(f"<p><ins>{escape(L[j].tekst)}</ins></p>" for j in leden), blok=True)
            w["soort"] = "nieuw"
            al = [los.get(L[j].sleutel) for j in leden]
            if all(al):
                w["klaar"] = True
                w["anker"] = self._anker(C[al[0][0]])
            else:
                plek = self._invoegplek(top, los)
                if plek:
                    w["auto"] = True
                    w["anker"] = dict(self._anker(C[plek[2]]), na=plek[1] == "na", voor=plek[1] == "voor")
                    self._acties[wid] = ("voegin", plek[0], self.live.bron(top))
            rijen.append(((leden[0], 1), w))

        rijen.sort(key=lambda r: r[0])
        return [w for _, w in rijen]

    def _rij(self, wid, eenheid, live_html, blok=False) -> dict:
        return {
            "id": wid,
            "sectie": eenheid.sectie or "Tekst buiten een sectie",
            "plek": eenheid.soort,
            "live": live_html,
            "blok": blok,
            "anker": None,
            "auto": False,
            "klaar": False,
        }

    @staticmethod
    def _anker(eenheid) -> dict:
        return {"sleutel": eenheid.sleutel, "nr": eenheid.nr}

    def _invoegplek(self, top, los):
        """Waar komt een nieuw stuk in het concept? Naast een buurman die ook in het concept staat.

        Geeft (positie in de concepttekst, "na"/"voor", nummer van de eenheid ernaast) of None.
        """
        buren = top.ouder.kinderen if top.ouder is not None else []
        plek = next((n for n, k in enumerate(buren) if k is top), -1)
        if plek < 0:
            return None
        kandidaten = [(b, "na") for b in reversed(buren[:plek])] + [(b, "voor") for b in buren[plek + 1 :]]
        for buur, kant in kandidaten:
            leden = self.live.binnen(buur)
            # Elke alinea van de buurman is goed om hem in het concept terug te vinden; de dichtstbijzijnde eerst.
            for j in reversed(leden) if kant == "na" else leden:
                k = self._concept_van_live(j, los)
                if k is None:
                    continue
                # Even ver omhoog als in live: van de alinea naar de buurman op hetzelfde niveau.
                lk, ck = self.live.eenheden[j].knoop, self.concept.eenheden[k].knoop
                while lk is not buur and ck is not None:
                    lk, ck = lk.ouder, ck.ouder
                if ck is None or not ck.tag or ck.tag != buur.tag:
                    continue
                if (ck.ouder.tag if ck.ouder is not None else "") != (top.ouder.tag if top.ouder is not None else ""):
                    continue
                return (ck.eind if kant == "na" else ck.begin), kant, k
        return None

    # --- stand en overnemen ----------------------------------------------------------------

    def _stand(self, w) -> tuple[str, str]:
        """'open', 'overgenomen' (staat in het concept), of een besluit van een redacteur."""
        if w.pop("klaar", False):
            return "overgenomen", ""
        b = self.besluiten.get(w["id"])
        if isinstance(b, dict) and b.get("besluit") in BESLUITEN:
            return b["besluit"], str(b.get("door") or "")
        return "open", ""

    def kan_overnemen(self, wid: str) -> bool:
        return wid in self._acties and any(w["id"] == wid and w["stand"] in ("open", "niet") for w in self.wijzigingen)

    def overnemen(self, wid: str) -> dict:
        """De velden van het concept met deze ene wijziging erin. Wie er meer wil, vergelijkt daarna opnieuw."""
        velden = dict(self.concept_velden)
        actie = self._acties[wid]
        html = self.concept.html
        if actie[0] == "veld":
            velden[actie[1]] = actie[2]
        elif actie[0] == "vervang":
            doel, bron = self.concept.eenheden[actie[1]].knoop, self.live.eenheden[actie[2]].knoop
            if doel.tag == bron.tag:
                velden["inhoud"] = html[: doel.begin] + self.live.bron(bron) + html[doel.eind :]
            else:
                binnen = self.live.html[bron.binnen_begin : bron.binnen_eind]
                velden["inhoud"] = html[: doel.binnen_begin] + binnen + html[doel.binnen_eind :]
        elif actie[0] == "verwijder":
            doel = _klim(self.concept, self.concept.eenheden[actie[1]].knoop, {actie[1]})
            velden["inhoud"] = html[: doel.begin] + html[doel.eind :]
        elif actie[0] == "voegin":
            velden["inhoud"] = html[: actie[1]] + actie[2] + html[actie[1] :]
        return velden


def vergelijk(basis: dict, live: dict, concept: dict, besluiten: dict | None = None) -> Vergelijking:
    return Vergelijking(basis, live, concept, besluiten)


def neem_over(basis: dict, live: dict, concept: dict, ids, besluiten: dict | None = None) -> tuple[dict, list[str]]:
    """Neem de genoemde wijzigingen over (of met ``ids="veilig"`` alles wat veilig kan).

    Na elke wijziging wordt opnieuw vergeleken: de plekken in de tekst zijn dan verschoven. Geeft de nieuwe
    velden en de ids die echt zijn overgenomen.
    """
    gedaan: list[str] = []
    velden = dict(concept)
    for _ in range(MAX_BESLUITEN):
        v = Vergelijking(basis, live, velden, besluiten)
        kandidaten = [
            w["id"]
            for w in v.wijzigingen
            if v.kan_overnemen(w["id"])
            and w["id"] not in gedaan
            and (w["stand"] == "open" if ids == "veilig" else w["id"] in ids)
        ]
        if not kandidaten:
            break
        velden = v.overnemen(kandidaten[0])
        gedaan.append(kandidaten[0])
    return velden, gedaan


def besluiten_bijwerken(oud: dict, nieuw, naam: str, moment: str) -> dict:
    """De besluiten zoals het bewerkscherm ze meestuurt, met naam en tijd van de server.

    Een besluit dat er al stond, houdt wie het nam; alleen wat nieuw of anders is, komt op naam van wie nu
    opslaat. Zo kan niemand een besluit op andermans naam zetten.
    """
    uit = {}
    if not isinstance(nieuw, dict):
        return dict(oud or {})
    for wid, b in list(nieuw.items())[:MAX_BESLUITEN]:
        soort = b.get("besluit") if isinstance(b, dict) else b
        if not isinstance(wid, str) or not re.fullmatch(r"[0-9a-f]{16}", wid) or soort not in BESLUITEN:
            continue
        vorig = (oud or {}).get(wid)
        if isinstance(vorig, dict) and vorig.get("besluit") == soort:
            uit[wid] = vorig
        else:
            uit[wid] = {"besluit": soort, "door": naam, "op": moment}
    return uit


def telling(wijzigingen) -> dict:
    """Voor de melding en het venster Afronden."""
    open_ = sum(1 for w in wijzigingen if w["stand"] == "open")
    niet = sum(1 for w in wijzigingen if w["stand"] == "niet")
    return {"totaal": len(wijzigingen), "open": open_, "niet": niet, "vervalt": open_ + niet}
