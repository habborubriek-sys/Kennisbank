"""De vaste zoekvragen bij de voorbeeldinhoud (1.35.0, bouwlijst Z6).

Echte zoekvragen van handhavers zijn er pas als de kennisbank live is. Tot die tijd meet deze set of het zoeken
doet wat het belooft, en bewaakt hij dat een latere wijziging het niet stil slechter maakt. Elke regel: wat de
medewerker typt, het begin van de titel van het artikel dat bovenaan hoort te staan (None = er hoort niets
gevonden te worden), en de soort.

Komen er later echte zoekvragen uit *Gebruiksstatistieken*, voeg ze dan hier toe.
"""

RAPPEL = "Rappel versturen"
BOOT = "Zwerfboot aangetroffen"
DOSSIER = "Dossier afsluiten"
MAILBOX = "Gezamenlijke mailbox"
TELEFOON = "Werkafspraak: telefonische"
OPGEPAKT = "Wordt een melding opgepakt"
PROCES = "Van melding tot afhandeling"
TOEZICHT = "Toezichtbezoek voorbereiden"
MELDING = "Melding registreren"

ZOEKSET = [
    # Dit ging al goed en moet goed blijven.
    ("rappel", RAPPEL, "gewoon"),
    ("rappels versturen", RAPPEL, "gewoon"),
    ("hoe verstuur ik een rappel", RAPPEL, "gewoon"),
    ("zwerfboot", BOOT, "gewoon"),
    ("dossier afsluiten", DOSSIER, "gewoon"),
    ("mailbox", MAILBOX, "gewoon"),
    ("terugbellen", TELEFOON, "gewoon"),
    ("afwijsredenen", OPGEPAKT, "gewoon"),
    ("doorlooptijd", PROCES, "gewoon"),
    # Typfouten.
    ("rapel", RAPPEL, "typfout"),
    ("zwerfbot", BOOT, "typfout"),
    ("dosier afsluiten", DOSSIER, "typfout"),
    ("toezichtbezeok", TOEZICHT, "typfout"),
    ("mailbocx", MAILBOX, "typfout"),
    ("afwijsredenn", OPGEPAKT, "typfout"),
    # Accenten.
    ("rappèl", RAPPEL, "accent"),
    ("prioritéring", OPGEPAKT, "accent"),
    # Een deel van een samengesteld woord.
    ("boot", BOOT, "deel van een woord"),
    ("paal", MELDING, "deel van een woord"),
    ("normen", PROCES, "deel van een woord"),
    ("proef", DOSSIER, "deel van een woord"),
    # Een ander woord voor hetzelfde: de synoniemenlijst.
    ("herinnering", RAPPEL, "synoniem"),
    ("aanmaning sturen", RAPPEL, "synoniem"),
    ("tweede brief", RAPPEL, "synoniem"),
    ("wrak", BOOT, "synoniem"),
    ("verlaten schip", BOOT, "synoniem"),
    ("inspectie", TOEZICHT, "synoniem"),
    ("postvak", MAILBOX, "synoniem"),
    ("QC", DOSSIER, "synoniem"),
    # Meer woorden dan er in één artikel staan: het dichtst in de buurt.
    ("rappel versturen dwangsom", RAPPEL, "te veel woorden"),
    ("zwerfboot gezonken melden", BOOT, "te veel woorden"),
    ("dossier afsluiten archief", DOSSIER, "te veel woorden"),
    # Hier hoort niets uit te komen: de hulp mag geen onzin voorstellen.
    ("vuurwerk", None, "hoort niets te vinden"),
    ("xyzabc", None, "hoort niets te vinden"),
    ("bodemverontreiniging", None, "hoort niets te vinden"),
]

#: Bekende grens: een onregelmatige vervoeging herkent de kennisbank niet uit zichzelf (*geloosd* bij *lozing*).
#: Procesmanagement kan zo'n woord in de synoniemenlijst zetten. De test bewaakt dat dit lijstje klopt: lost een
#: latere versie het op, dan hoort de regel naar ZOEKSET.
NOG_NIET = [
    ("geloosd", MELDING, "vervoeging"),
]


def meet(zoek, artikelen, regels=None) -> list[dict]:
    """Draai de set met de gegeven zoekfunctie (queryset, tekst) -> lijst artikelen. Per regel: goed of niet."""
    uit = []
    for vraag, verwacht, soort in regels if regels is not None else ZOEKSET:
        gevonden = [a.titel for a in zoek(artikelen, vraag)]
        if verwacht is None:
            goed = not gevonden
        else:
            goed = bool(gevonden) and gevonden[0].startswith(verwacht)
        uit.append({"vraag": vraag, "soort": soort, "goed": goed, "eerste": gevonden[0] if gevonden else None})
    return uit


def per_soort(uitslag) -> dict[str, tuple[int, int]]:
    tabel: dict[str, list[int]] = {}
    for r in uitslag:
        t = tabel.setdefault(r["soort"], [0, 0])
        t[0] += r["goed"]
        t[1] += 1
    return {soort: (goed, totaal) for soort, (goed, totaal) in tabel.items()}
