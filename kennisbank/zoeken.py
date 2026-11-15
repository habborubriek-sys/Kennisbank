"""Zoeken met PostgreSQL full-text search (Nederlandse woordstammen, prefix-matching).

De zoekdocumenten staan opgeslagen in Artikel.zoekvector en Sectie.zoekvector (met GIN-index) en
worden bijgewerkt in diensten.herbouw_secties. Zoeken is daardoor een indexopzoeking, ook bij
duizenden artikelen; er is geen aparte zoekmachine nodig.

Sinds 1.35.0 helpt de kennisbank de zoeker in drie stappen, elk alleen als de vorige niets opleverde:

1. **Gewoon zoeken**: alle woorden moeten voorkomen. Accenten doen er niet toe, en woorden uit de
   synoniemenlijst van de omgeving (``Synoniem``) tellen als hetzelfde woord.
2. **Zoekhulp**: een woord dat nergens voorkomt, wordt vervangen door woorden uit de woordenlijst van de
   omgeving (``Zoekwoord``) die erop lijken (*rapel* → *rappel*) of die het bevatten (*boot* → *zwerfboot*).
3. **Dichtst in de buurt**: de artikelen waarin de meeste woorden voorkomen.

``zoek()`` geeft naast de artikelen ook terug wát er is gedaan, zodat de site dat boven de resultaten kan
zeggen. Een voorgesteld woord wordt alleen genoemd als het bij de artikelen die deze gebruiker mag zien iets
oplevert: de woordenlijst verklapt dus niets over artikelen die iemand niet mag lezen.
"""

import re
import unicodedata

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db import connection
from django.db.models import F

from .models import Sectie, Synoniem

CONFIG = "dutch"
_WOORD = re.compile(r"[\w]+", re.UNICODE)
#: Vanaf deze gelijkenis (0-1, pg_trgm) geldt een woord uit de woordenlijst als "bedoelde je dit?".
GELIJKENIS = 0.45
#: Een deel van een woord (*boot* in *zwerfboot*) zoeken we pas vanaf zoveel letters.
MIN_DEEL = 4
#: Zoveel resultaten hoogstens bij "dichtst in de buurt".
MAX_DICHTBIJ = 20


def normaal(tekst: str) -> str:
    """Kleine letters, zonder accenten: zo staan de woorden ook in de zoekdocumenten (unaccent)."""
    plat = unicodedata.normalize("NFKD", tekst or "")
    return "".join(c for c in plat if not unicodedata.combining(c)).lower()


def termen(tekst: str) -> list[str]:
    return [w for w in _WOORD.findall(normaal(tekst)) if len(w) > 1][:12]


def _synoniemgroepen(omgevingen) -> list[list[tuple[str, ...]]]:
    """De synoniemen van deze omgevingen: per groep de woorden, elk als rij losse woorden."""
    groepen = []
    for s in Synoniem.objects.filter(omgeving_id__in=list(omgevingen)):
        leden = []
        for woord in s.woorden():
            delen = tuple(termen(woord))
            if delen and delen not in leden:
                leden.append(delen)
        if len(leden) > 1:
            groepen.append(leden)
    return groepen


def _stuk(delen: tuple[str, ...], getypt: bool) -> str:
    """Een stukje tsquery voor één woord of woordgroep. Wat de zoeker typt, zoekt op het begin van een woord;
    een synoniem van meer woorden moet als groep achter elkaar staan."""
    if len(delen) == 1:
        return f"{delen[0]}:*"
    if getypt:
        return "(" + " & ".join(f"{d}:*" for d in delen) + ")"
    return "(" + " <-> ".join(delen) + ")"


class Eenheid:
    """Eén zoekwoord (of een woordgroep uit de synoniemenlijst) met alles wat ervoor in de plaats mag komen."""

    __slots__ = ("bron", "stukken", "synoniemen", "verbeterd")

    def __init__(self, bron: tuple[str, ...]):
        self.bron = bron
        self.stukken = [_stuk(bron, True)]
        self.synoniemen: list[str] = []
        self.verbeterd: list[str] = []

    @property
    def tekst(self) -> str:
        return " ".join(self.bron)

    def raw(self) -> str:
        return "(" + " | ".join(self.stukken) + ")" if len(self.stukken) > 1 else self.stukken[0]


def eenheden(tekst: str, omgevingen=()) -> list[Eenheid]:
    """Knip de zoektekst in eenheden en vul de synoniemen in."""
    woorden = termen(tekst)
    groepen = _synoniemgroepen(omgevingen) if omgevingen else []
    uit, i = [], 0
    while i < len(woorden):
        beste = None
        for groep in groepen:
            for lid in groep:
                if tuple(woorden[i : i + len(lid)]) == lid and (beste is None or len(lid) > len(beste[1])):
                    beste = (groep, lid)
        if beste:
            groep, lid = beste
            e = Eenheid(lid)
            for ander in groep:
                if ander != lid:
                    e.stukken.append(_stuk(ander, False))
                    e.synoniemen.append(" ".join(ander))
            i += len(lid)
        else:
            e = Eenheid((woorden[i],))
            i += 1
        uit.append(e)
    return uit


def _vraag(delen: list[Eenheid], alle: bool) -> SearchQuery | None:
    if not delen:
        return None
    return SearchQuery((" & " if alle else " | ").join(e.raw() for e in delen), search_type="raw", config=CONFIG)


def zoekvraag(tekst: str, alle_termen: bool, omgevingen=()) -> SearchQuery | None:
    """Bouw een tsquery met prefix-matching. Zoekbalk: alle termen (AND). Assistent: OR."""
    return _vraag(eenheden(tekst, omgevingen), alle_termen)


def _lijkt_op(woord: str, omgevingen) -> list[str]:
    """Woorden uit de woordenlijst die op ``woord`` lijken (typfout) of het bevatten (deel van een woord)."""
    ids = list(omgevingen)
    if not ids or len(woord) < 3:
        return []
    with connection.cursor() as c:
        c.execute(
            "SELECT woord, max(similarity(woord, %s)) FROM kennisbank_zoekwoord "
            "WHERE omgeving_id = ANY(%s) AND woord <> %s AND woord %% %s AND similarity(woord, %s) >= %s "
            "GROUP BY woord ORDER BY 2 DESC, woord LIMIT 3",
            [woord, ids, woord, woord, woord, GELIJKENIS],
        )
        rijen = c.fetchall()
        # Alleen wat ongeveer even goed lijkt als de beste: anders komt er bij één typfout een rijtje gokken.
        uit = [w for w, gelijkenis in rijen if gelijkenis >= rijen[0][1] - 0.1]
        if len(woord) >= MIN_DEEL:
            c.execute(
                "SELECT woord FROM kennisbank_zoekwoord WHERE omgeving_id = ANY(%s) AND woord <> %s "
                "AND woord LIKE %s GROUP BY woord ORDER BY length(woord), woord LIMIT 5",
                [ids, woord, "%" + woord.replace("%", "").replace("_", "") + "%"],
            )
            uit += [r[0] for r in c.fetchall() if r[0] not in uit]
    return uit


def _omgevingen_van(queryset) -> set[int]:
    return set(queryset.order_by().values_list("omgeving_id", flat=True).distinct())


def _raakt(queryset, raw: str) -> bool:
    return queryset.filter(zoekvector=SearchQuery(raw, search_type="raw", config=CONFIG)).exists()


def _stopwoord(woord: str) -> bool:
    """Een woord dat de zoekindex overslaat (de, het, hoe, ik): daar valt niets aan te verbeteren."""
    with connection.cursor() as c:
        c.execute("SELECT numnode(to_tsquery(%s, %s)) = 0", [CONFIG, f"{woord}:*"])
        return bool(c.fetchone()[0])


def _verbeter(queryset, delen: list[Eenheid], omgevingen) -> bool:
    """Stap 2: geef woorden die nergens voorkomen een vervanger uit de woordenlijst. True als er iets veranderde."""
    veranderd = False
    for e in delen:
        if len(e.bron) != 1 or e.synoniemen or _stopwoord(e.bron[0]) or _raakt(queryset, e.raw()):
            continue
        for kandidaat in _lijkt_op(e.bron[0], omgevingen):
            # Alleen wat bij déze zoeker iets oplevert: zo verklapt de woordenlijst niets.
            if _raakt(queryset, f"{kandidaat}:*"):
                e.stukken.append(f"{kandidaat}:*")
                e.verbeterd.append(kandidaat)
                veranderd = True
    return veranderd


def _dichtbij(queryset, delen: list[Eenheid]) -> list:
    """Stap 3: geen artikel bevat alle woorden. Toon wat het dichtst in de buurt komt.

    Een zeldzaam woord zegt meer dan een woord dat overal staat: bij *zwerfboot gezonken melden* hoort het
    artikel over de zwerfboot boven de vele artikelen waarin *melden* voorkomt. Elk woord telt daarom mee
    naar hoe weinig artikelen het bevatten.
    """
    from django.db.models import Case, FloatField, Value, When

    score = Value(0.0, output_field=FloatField())
    for e in delen:
        deelvraag = SearchQuery(e.raw(), search_type="raw", config=CONFIG)
        aantal = queryset.filter(zoekvector=deelvraag).count()
        if aantal:
            score = score + Case(
                When(zoekvector=deelvraag, then=Value(1.0 / aantal)), default=Value(0.0), output_field=FloatField()
            )
    vraag = _vraag(delen, alle=False)
    return list(
        queryset.filter(zoekvector=vraag)
        .annotate(gewicht=score, rang=SearchRank(F("zoekvector"), vraag))
        .order_by("-gewicht", "-rang", "titel")[:MAX_DICHTBIJ]
    )


def _gerangschikt(queryset, vraag):
    return (
        queryset.filter(zoekvector=vraag).annotate(rang=SearchRank(F("zoekvector"), vraag)).order_by("-rang", "titel")
    )


def zoek(queryset, tekst: str, omgevingen=None) -> tuple[list, dict]:
    """Zoek artikelen en vertel wat er is gedaan.

    Geeft ``(artikelen, hulp)``. ``hulp`` is leeg als er gewoon is gezocht, en anders:

    - ``synoniemen``: [{"van": "herinnering", "naar": ["rappel"]}]: ook daarop is gezocht;
    - ``verbeterd``: [{"van": "rapel", "naar": ["rappel"]}]: het getypte woord kwam nergens voor;
    - ``dichtbij``: True als geen artikel alle woorden bevat en de lijst toont wat het dichtst in de buurt komt.
    """
    if omgevingen is None:
        omgevingen = _omgevingen_van(queryset)
    delen = eenheden(tekst, omgevingen)
    vraag = _vraag(delen, alle=True)
    if vraag is None:
        return list(queryset), {}
    hulp: dict = {}
    resultaat = list(_gerangschikt(queryset, vraag))
    if not resultaat and _verbeter(queryset, delen, omgevingen):
        resultaat = list(_gerangschikt(queryset, _vraag(delen, alle=True)))
    if not resultaat and len(delen) > 1:
        resultaat = _dichtbij(queryset, delen)
        if resultaat:
            hulp["dichtbij"] = True
    if resultaat:
        verbeterd = [{"van": e.tekst, "naar": e.verbeterd} for e in delen if e.verbeterd]
        # Een synoniem noemen we alleen als het getypte woord zelf niets vond: dan kwam het resultaat
        # via het andere woord, en dat hoort de zoeker te weten. Vond het woord zelf al iets, dan zwijgt de hulp.
        synoniemen = []
        for e in delen:
            if e.synoniemen and not _raakt(queryset, e.stukken[0]):
                raak = [n for n, stuk in zip(e.synoniemen, e.stukken[1:], strict=False) if _raakt(queryset, stuk)]
                if raak:
                    synoniemen.append({"van": e.tekst, "naar": raak})
        if verbeterd:
            hulp["verbeterd"] = verbeterd
        if synoniemen:
            hulp["synoniemen"] = synoniemen
    return resultaat, hulp


def hulp_als_zin(hulp: dict) -> str:
    """Wat de zoekhulp deed, als één regel tekst (voor het beheer; de site maakt er zelf een regel van)."""
    zinnen = []
    for v in hulp.get("verbeterd", []):
        zinnen.append(f"Resultaten voor {' of '.join(v['naar'])}; je zocht op {v['van']}.")
    for v in hulp.get("synoniemen", []):
        zinnen.append(f"Ook gezocht op {', '.join(v['naar'])} (synoniem van {v['van']}).")
    if hulp.get("dichtbij"):
        zinnen.append("Geen artikel met al deze woorden. Dit komt het dichtst in de buurt.")
    return " ".join(zinnen)


def zoek_artikelen(queryset, tekst: str):
    """Filter en sorteer artikelen op relevantie. Geeft de queryset ongewijzigd terug zonder zoektekst."""
    if not termen(tekst):
        return queryset
    return zoek(queryset, tekst)[0]


#: Ondergrens voor de score van een sectietreffer. Onder deze waarde is het verband met de vraag zo
#: zwak dat "dit staat in …" misleidend is; de assistent zegt dan liever dat hij het niet weet.
MINIMALE_RANG = 0.05


def zoek_secties(artikelen_qs, tekst: str, zaaktype: str | None = None, aantal: int = 5):
    """Meest relevante secties voor een vraag, voor de assistent. Met dezelfde synoniemen en zoekhulp."""
    omgevingen = _omgevingen_van(artikelen_qs)
    delen = eenheden(tekst, omgevingen)
    vraag = _vraag(delen, alle=False)
    if vraag is None:
        return []

    def kandidaten_voor(v):
        return list(
            Sectie.objects.filter(artikel__in=artikelen_qs, zoekvector=v)
            .exclude(inhoud__regex=r"^\s*$")  # een sectie zonder tekst valt niets uit te citeren
            .annotate(rang=SearchRank(F("zoekvector"), v))
            .select_related("artikel")
            .prefetch_related("artikel__zaaktypen")
            .order_by("-rang")[: aantal * 4]
        )

    kandidaten = kandidaten_voor(vraag)
    if not kandidaten and _verbeter(artikelen_qs, delen, omgevingen):
        kandidaten = kandidaten_voor(_vraag(delen, alle=False))
    if zaaktype:
        for s in kandidaten:
            if any(z.code == zaaktype for z in s.artikel.zaaktypen.all()):
                s.rang *= 1.5
        kandidaten.sort(key=lambda s: -s.rang)
    if kandidaten:
        # Zwakke treffers weglaten: alleen secties die in de buurt komen van de beste, én die op
        # zichzelf iets voorstellen. Zonder die absolute ondergrens levert één toevallig woord uit de
        # titel al een "dit staat in …" op.
        grens = max(kandidaten[0].rang * 0.25, MINIMALE_RANG)
        kandidaten = [s for s in kandidaten if s.rang >= grens]
    return kandidaten[:aantal]
