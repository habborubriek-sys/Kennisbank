"""1.35.0: zoeken dat meedenkt (typfouten, accenten, delen van woorden, synoniemen, dichtst in de buurt),
"Was dit artikel nuttig?", "gevonden maar niet geholpen" en zoeken in het beheer via de zoekindex.

Bouwlijst `bouwlijst-1.35.0-zoeken.md`, punten Z1 t/m Z6.
"""

import json
from io import StringIO

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from rest_framework.throttling import UserRateThrottle

from kennisbank import diensten, zoeken
from kennisbank.management.commands.kennisbank_demo import DEMO_SYNONIEMEN, demo_synoniemen
from kennisbank.models import (
    Artikel,
    ArtikelOordeel,
    Rol,
    Status,
    Synoniem,
    Toegang,
    ZoekTelling,
    Zoekwoord,
)
from kennisbank.tests.test_kennisbank import Basis
from kennisbank.tests.zoekset import NOG_NIET, ZOEKSET, meet

SECTIE = '<section class="sectie"><h2 class="sectie-kop">Inhoud</h2><p>{}</p></section>'


def maak(omgeving, titel, tekst, status=Status.GEPUBLICEERD):
    a = Artikel.objects.create(omgeving=omgeving, titel=titel, samenvatting="Samenvatting.", status=status)
    a.inhoud = SECTIE.format(tekst)
    a.save()
    diensten.herbouw_secties(a)
    diensten.werk_zoekvectoren_bij(a.pk)
    return a


class ZoekBasis(Basis):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        demo_synoniemen(cls.hh)
        diensten.zoekwoorden_herbouwen()

    def setUp(self):
        UserRateThrottle.cache.clear()

    @property
    def live(self):
        return Artikel.objects.filter(omgeving=self.hh, status=Status.GEPUBLICEERD)

    def api(self, q, gebruiker=None, **extra):
        r = self.als(gebruiker or self.lezer).get("/api/v1/artikelen", {"q": q, **extra})
        self.assertEqual(r.status_code, 200)
        kop = r.headers.get("X-KB-Zoekhulp")
        return [a["titel"] for a in r.json()], (json.loads(kop) if kop else None)


# --- Z6: de vaste zoekvragen ------------------------------------------------------------------------------------


class Zoekset(ZoekBasis):
    def test_elke_vaste_zoekvraag_geeft_het_goede_artikel_bovenaan(self):
        uitslag = meet(lambda qs, tekst: zoeken.zoek(qs, tekst)[0], self.live)
        mis = [(r["vraag"], r["soort"], r["eerste"]) for r in uitslag if not r["goed"]]
        self.assertEqual(mis, [])
        self.assertGreaterEqual(len(uitslag), 35)

    def test_de_set_heeft_van_elke_soort_vragen(self):
        soorten = {soort for _, _, soort in ZOEKSET}
        self.assertEqual(
            soorten,
            {
                "gewoon",
                "typfout",
                "accent",
                "deel van een woord",
                "synoniem",
                "te veel woorden",
                "hoort niets te vinden",
            },
        )

    def test_de_bekende_grens_is_nog_steeds_een_grens(self):
        """Lost een latere versie dit op, dan hoort de regel naar ZOEKSET: de documentatie noemt hem als grens."""
        uitslag = meet(lambda qs, tekst: zoeken.zoek(qs, tekst)[0], self.live, NOG_NIET)
        self.assertEqual([r["vraag"] for r in uitslag if r["goed"]], [])

    def test_de_demo_synoniemen_staan_in_de_omgeving(self):
        self.assertEqual(Synoniem.objects.filter(omgeving=self.hh).count(), len(DEMO_SYNONIEMEN))
        demo_synoniemen(self.hh)  # nog een keer laden maakt geen dubbele
        self.assertEqual(Synoniem.objects.filter(omgeving=self.hh).count(), len(DEMO_SYNONIEMEN))


# --- Z1 t/m Z3: wat de zoekhulp doet en vertelt ------------------------------------------------------------------


class Zoekhulp(ZoekBasis):
    def test_gewoon_zoeken_geeft_geen_hulp(self):
        lijst, hulp = zoeken.zoek(self.live, "rappel")
        self.assertTrue(lijst[0].titel.startswith("Rappel versturen"))
        self.assertEqual(hulp, {})

    def test_typfout_wordt_verbeterd_en_gemeld(self):
        lijst, hulp = zoeken.zoek(self.live, "rapel")
        self.assertTrue(lijst[0].titel.startswith("Rappel versturen"))
        self.assertEqual(hulp, {"verbeterd": [{"van": "rapel", "naar": ["rappel"]}]})

    def test_alleen_het_foute_woord_wordt_verbeterd(self):
        lijst, hulp = zoeken.zoek(self.live, "dosier afsluiten")
        self.assertTrue(lijst[0].titel.startswith("Dossier afsluiten"))
        self.assertEqual([v["van"] for v in hulp["verbeterd"]], ["dosier"])
        self.assertIn("dossier", hulp["verbeterd"][0]["naar"])

    def test_accent_maakt_niet_uit_in_beide_richtingen(self):
        self.assertEqual(zoeken.zoek(self.live, "rappèl")[1], {})
        self.assertEqual(zoeken.normaal("Privé-CAFÉ ïs"), "prive-cafe is")
        self.assertEqual(zoeken.termen("Rappèl, coördinatie!"), ["rappel", "coordinatie"])
        self.assertTrue(zoeken.zoek(self.live, "RAPPÈL")[0][0].titel.startswith("Rappel versturen"))
        a = maak(self.hh, "Privé-eigendom langs de oever", "Een café op privéterrein.")
        for vraag in ("prive", "privé", "cafe", "café"):
            self.assertIn(a, zoeken.zoek(self.live, vraag)[0], vraag)

    def test_deel_van_een_samengesteld_woord(self):
        lijst, hulp = zoeken.zoek(self.live, "boot")
        self.assertTrue(lijst[0].titel.startswith("Zwerfboot aangetroffen"))
        self.assertEqual(hulp["verbeterd"][0]["van"], "boot")
        self.assertIn("zwerfboot", hulp["verbeterd"][0]["naar"])

    def test_een_deel_van_drie_letters_is_te_kort(self):
        maak(self.hh, "Vaarwegmarkering", "De markering van de vaarweg.")
        self.assertEqual(zoeken.MIN_DEEL, 4)
        self.assertEqual(zoeken._lijkt_op("weg", [self.hh.pk]), [])
        self.assertIn("vaarweg", zoeken._lijkt_op("rweg", [self.hh.pk]))

    def test_synoniem_wordt_gemeld_als_het_woord_zelf_niets_vond(self):
        lijst, hulp = zoeken.zoek(self.live, "wrak")
        self.assertTrue(lijst[0].titel.startswith("Zwerfboot aangetroffen"))
        self.assertEqual(hulp, {"synoniemen": [{"van": "wrak", "naar": ["zwerfboot"]}]})

    def test_synoniem_zwijgt_als_het_woord_zelf_al_iets_vond(self):
        lijst, hulp = zoeken.zoek(self.live, "zwerfboot")
        self.assertTrue(lijst)
        self.assertEqual(hulp, {})

    def test_synoniem_werkt_in_beide_richtingen(self):
        a = maak(self.hh, "Wat doe je met een achtergelaten vaartuig", "Een wrak in de vaargeul.")
        self.assertIn(a, zoeken.zoek(self.live, "wrak")[0])
        # Nu vinden beide woorden zelf iets: dan hoeft de zoeker niets te horen.
        lijst, hulp = zoeken.zoek(self.live, "zwerfboot")
        self.assertIn(a, lijst)
        self.assertEqual(hulp, {})
        self.assertEqual(zoeken.zoek(self.live, "wrak")[1], {})

    def test_synoniem_van_meer_woorden(self):
        lijst, hulp = zoeken.zoek(self.live, "tweede brief")
        self.assertTrue(lijst[0].titel.startswith("Rappel versturen"))
        Synoniem.objects.create(omgeving=self.hh, woord="dossier", alternatieven="rode map")
        lijst, hulp = zoeken.zoek(self.live, "rode map afsluiten")
        self.assertTrue(lijst[0].titel.startswith("Dossier afsluiten"))
        self.assertEqual(hulp["synoniemen"], [{"van": "rode map", "naar": ["dossier"]}])
        a = maak(self.hh, "Schip zonder eigenaar", "Het verlaten schip ligt aan de kade.")
        los = maak(self.hh, "Verlaten van het terrein", "Het schip vaart door.")
        gevonden = zoeken.zoek(self.live, "zwerfboot")[0]
        self.assertIn(a, gevonden)
        self.assertNotIn(los, gevonden)  # de woorden moeten als groep achter elkaar staan

    def test_te_veel_woorden_geeft_wat_het_dichtst_in_de_buurt_komt(self):
        lijst, hulp = zoeken.zoek(self.live, "zwerfboot gezonken melden")
        self.assertTrue(lijst[0].titel.startswith("Zwerfboot aangetroffen"))
        self.assertEqual(hulp, {"dichtbij": True})
        self.assertLessEqual(len(lijst), zoeken.MAX_DICHTBIJ)

    def test_een_zeldzaam_woord_weegt_zwaarder_dan_een_woord_dat_overal_staat(self):
        for n in range(6):
            maak(self.hh, f"Melding nummer {n}", "Een melding melden bij het meldpunt. Melden, melden.")
        lijst, _ = zoeken.zoek(self.live, "zwerfboot gezonken melden")
        self.assertTrue(lijst[0].titel.startswith("Zwerfboot aangetroffen"))
        # Eén zeldzaam woord wint van twee woorden die in veel artikelen staan.
        zeldzaam = maak(self.hh, "Kwelscherm plaatsen", "Het kwelscherm langs de dijk.")
        for n in range(6):
            maak(self.hh, f"Ontheffing {n}", "Een ontheffing aanvragen bij het loket.")
        lijst, hulp = zoeken.zoek(self.live, "kwelscherm ontheffing aanvragen")
        self.assertEqual(hulp, {"dichtbij": True})
        self.assertEqual(lijst[0], zeldzaam)

    def test_onzin_geeft_niets_en_geen_hulp(self):
        for vraag in ("xyzabc", "vuurwerk", "xyzabc qwrtp"):
            self.assertEqual(zoeken.zoek(self.live, vraag), ([], {}), vraag)

    def test_een_stopwoord_wordt_niet_verbeterd(self):
        self.assertTrue(zoeken._stopwoord("hoe"))
        self.assertFalse(zoeken._stopwoord("rappel"))
        lijst, hulp = zoeken.zoek(self.live, "hoe verstuur ik een rappel")
        self.assertTrue(lijst[0].titel.startswith("Rappel versturen"))
        self.assertEqual(hulp, {})
        # Ook als er wel iets te verbeteren valt, blijven de stopwoorden met rust.
        lijst, hulp = zoeken.zoek(self.live, "hoe verstuur ik een rapel")
        self.assertTrue(lijst[0].titel.startswith("Rappel versturen"))
        self.assertEqual([v["van"] for v in hulp["verbeterd"]], ["rapel"])
        # "voor" is lang genoeg om als deel van een woord te gelden (voorbereiden), maar is een stopwoord.
        self.assertTrue(zoeken._stopwoord("voor"))
        self.assertTrue(zoeken._lijkt_op("voor", [self.hh.pk]))
        lijst, hulp = zoeken.zoek(self.live, "voor de rapel")
        self.assertEqual(hulp, {"verbeterd": [{"van": "rapel", "naar": ["rappel"]}]})

    def test_een_verbetering_komt_niet_bij_een_rijtje_gokken(self):
        # "controleer" lijkt ook op "controlle", maar veel minder dan "controle": alleen de beste telt.
        self.assertEqual(zoeken._lijkt_op("controlle", [self.hh.pk]), ["controle"])
        self.assertEqual(zoeken._lijkt_op("rapel", [self.hh.pk]), ["rappel"])
        self.assertEqual(zoeken._lijkt_op("ra", [self.hh.pk]), [])
        self.assertEqual(zoeken._lijkt_op("rapel", []), [])

    def test_tekens_met_een_betekenis_in_de_database_breken_niets(self):
        for vraag in ("100%", "a_b%c", "rappel & | ! :*", "''; DROP TABLE x", "(((", "<->", "\\"):
            lijst, hulp = zoeken.zoek(self.live, vraag)
            self.assertIsInstance(lijst, list, vraag)

    def test_zin_voor_het_beheer(self):
        self.assertEqual(zoeken.hulp_als_zin({}), "")
        self.assertEqual(
            zoeken.hulp_als_zin({"verbeterd": [{"van": "rapel", "naar": ["rappel"]}]}),
            "Resultaten voor rappel; je zocht op rapel.",
        )
        self.assertIn("synoniem van wrak", zoeken.hulp_als_zin({"synoniemen": [{"van": "wrak", "naar": ["x"]}]}))
        self.assertIn("dichtst in de buurt", zoeken.hulp_als_zin({"dichtbij": True}))

    def test_de_assistent_gebruikt_dezelfde_synoniemen_en_verbeteringen(self):
        secties = zoeken.zoek_secties(self.live, "wrak")
        self.assertTrue(secties[0].artikel.titel.startswith("Zwerfboot aangetroffen"))
        secties = zoeken.zoek_secties(self.live, "toezichtbezeok")
        self.assertTrue(secties[0].artikel.titel.startswith("Toezichtbezoek voorbereiden"))
        self.assertEqual(zoeken.zoek_secties(self.live, "xyzabc"), [])


# --- De hulp verklapt niets ------------------------------------------------------------------------------------


class GeenLek(ZoekBasis):
    """De woordenlijst bevat ook woorden uit concepten en uit andere omgevingen. Een lezer mag daar via een
    suggestie niets van merken: een woord wordt alleen voorgesteld als het bij déze zoeker iets oplevert."""

    def test_geen_suggestie_uit_een_concept(self):
        maak(self.hh, "Nog geheim", "Over de kwikzilverlozing bij de sluis.", status=Status.CONCEPT)
        self.assertTrue(Zoekwoord.objects.filter(omgeving=self.hh, woord="kwikzilverlozing").exists())
        self.assertEqual(self.api("kwikzilverlozin"), ([], None))
        self.assertEqual(self.api("kwikzilver"), ([], None))
        r = self.als(self.lezer).get("/api/v1/artikelen", {"q": "kwikzilverlozin"})
        self.assertNotIn("kwikzilverlozing", json.dumps(dict(r.headers)) + r.content.decode())
        # De redacteur ziet het concept wel en krijgt de verbetering dus wel.
        titels, hulp = self.api("kwikzilverlozin", self.redacteur, status="concept")
        self.assertEqual(titels, ["Nog geheim"])
        self.assertEqual(hulp["verbeterd"][0]["naar"], ["kwikzilverlozing"])

    def test_geen_suggestie_en_geen_synoniem_uit_een_andere_omgeving(self):
        maak(self.anders, "Van de buren", "Over het dijkbewakingsrooster.")
        Synoniem.objects.create(omgeving=self.anders, woord="dijkbewakingsrooster", alternatieven="wachtlijst")
        self.assertEqual(self.api("dijkbewakingsroster"), ([], None))
        self.assertEqual(zoeken._lijkt_op("dijkbewakingsroster", [self.hh.pk]), [])  # de lijst is per omgeving
        self.assertEqual(zoeken._lijkt_op("dijkbewakingsroster", [self.anders.pk]), ["dijkbewakingsrooster"])
        self.assertEqual(self.api("wachtlijst"), ([], None))
        titels, hulp = self.api("dijkbewakingsroster", self.buitenstaander)
        self.assertEqual(titels, ["Van de buren"])
        self.assertEqual(hulp["verbeterd"][0]["naar"], ["dijkbewakingsrooster"])
        titels, hulp = self.api("wachtlijst", self.buitenstaander)
        self.assertEqual(titels, ["Van de buren"])
        # En andersom: de synoniemen van handhaving gelden niet bij de buren.
        maak(self.anders, "Rappel bij de buren", "Een rappel sturen.")
        self.assertEqual(self.api("aanmaning", self.buitenstaander), ([], None))

    def test_dichtbij_toont_alleen_wat_de_zoeker_mag_zien(self):
        titels, hulp = self.api("rappel concepttekst")
        self.assertEqual(hulp, {"dichtbij": True})
        self.assertNotIn("Geheim concept", titels)


# --- De woordenlijst ------------------------------------------------------------------------------------------


class Woordenlijst(ZoekBasis):
    def test_opslaan_van_een_artikel_voegt_zijn_woorden_toe(self):
        self.assertFalse(Zoekwoord.objects.filter(woord="oeverbeschoeiing").exists())
        maak(self.hh, "Oeverbeschoeiing herstellen", "De Beschoeiing is kapót. Zie 2024 en a1b2.")
        woorden = set(Zoekwoord.objects.filter(omgeving=self.hh).values_list("woord", flat=True))
        self.assertLessEqual({"oeverbeschoeiing", "beschoeiing", "kapot", "herstellen"}, woorden)
        # Geen cijfers, geen woorden van twee letters, geen accenten, geen hoofdletters.
        self.assertFalse({"2024", "a1b2", "de", "kapót", "Beschoeiing"} & woorden)
        self.assertEqual(Zoekwoord.objects.filter(omgeving=self.hh, woord="kapot").count(), 1)
        self.assertFalse(Zoekwoord.objects.filter(omgeving=self.anders, woord="kapot").exists())

    def test_opschonen_haalt_woorden_weg_die_nergens_meer_staan(self):
        a = maak(self.hh, "Tijdelijk", "Over de strekdamverlichting.")
        a.inhoud = SECTIE.format("Iets anders.")
        a.save()
        diensten.herbouw_secties(a)
        diensten.werk_zoekvectoren_bij(a.pk)
        self.assertTrue(Zoekwoord.objects.filter(woord="strekdamverlichting").exists())
        uit = StringIO()
        call_command("kennisbank_opschonen", stdout=uit)
        self.assertFalse(Zoekwoord.objects.filter(woord="strekdamverlichting").exists())
        self.assertTrue(Zoekwoord.objects.filter(woord="rappel").exists())
        self.assertIn(f"{Zoekwoord.objects.count()} zoekwoord(en)", uit.getvalue())


# --- Z2: de synoniemenlijst in het beheer ------------------------------------------------------------------------


class SynoniemBeheer(ZoekBasis):
    TOEVOEGEN = "/beheer/kennisbank/synoniem/add/"

    def test_redactie_maakt_een_synoniem_en_het_werkt_meteen(self):
        self.assertEqual(self.api("kwartaalbrief"), ([], None))
        r = self.als(self.redacteur).post(
            self.TOEVOEGEN,
            {
                "omgeving": self.hh.pk,
                "woord": "Dossier",
                "alternatieven": "kwartaalbrief;  Tweede  Kwartaalbrief\ndossier",
            },
        )
        self.assertEqual(r.status_code, 302, r.content.decode()[:2000] if r.status_code != 302 else "")
        s = Synoniem.objects.get(woord="Dossier")
        # Opgeschoond, en het woord zelf valt eruit.
        self.assertEqual(s.alternatieven, "kwartaalbrief, Tweede Kwartaalbrief")
        titels, hulp = self.api("kwartaalbrief afsluiten")
        self.assertTrue(titels[0].startswith("Dossier afsluiten"))
        self.assertEqual(hulp["synoniemen"][0]["naar"], ["dossier"])

    def test_bestaat_het_woord_al_dan_komen_de_nieuwe_woorden_erbij(self):
        """Vanuit de statistieken maak je een synoniem zonder te weten of het woord al een regel heeft."""
        voor = Synoniem.objects.count()
        oud = Synoniem.objects.get(omgeving=self.hh, woord="rappel").alternatieven
        r = self.als(self.redacteur).post(
            self.TOEVOEGEN,
            {"omgeving": self.hh.pk, "woord": "Rappel", "alternatieven": "kwartaalbrief, AANMANING"},
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Synoniem.objects.count(), voor)
        self.assertEqual(Synoniem.objects.get(omgeving=self.hh, woord="rappel").alternatieven, oud + ", kwartaalbrief")
        self.assertIn(
            "Het woord rappel had al synoniemen. Toegevoegd: kwartaalbrief.", [str(m) for m in r.context["messages"]]
        )
        self.assertTrue(self.api("kwartaalbrief")[0][0].startswith("Rappel versturen"))
        r = self.als(self.redacteur).post(
            self.TOEVOEGEN, {"omgeving": self.hh.pk, "woord": "rappel", "alternatieven": "aanmaning"}, follow=True
        )
        self.assertIn("Er is niets veranderd.", " ".join(str(m) for m in r.context["messages"]))
        # In een andere omgeving is het gewoon een nieuwe regel.
        Synoniem.objects.create(omgeving=self.anders, woord="rappel", alternatieven="maning")
        self.assertEqual(Synoniem.objects.get(omgeving=self.hh, woord="rappel").alternatieven, oud + ", kwartaalbrief")

    def test_formulier_weigert_een_leeg_of_gelijk_alternatief(self):
        for data in (
            {"woord": "rappel", "alternatieven": "Rappel"},
            {"woord": "rappel", "alternatieven": " , ; "},
            {"woord": "!!!", "alternatieven": "iets"},
        ):
            voor = Synoniem.objects.count()
            r = self.als(self.redacteur).post(self.TOEVOEGEN, {"omgeving": self.hh.pk, **data})
            self.assertEqual(r.status_code, 200, data)
            self.assertEqual(Synoniem.objects.count(), voor, data)

    def test_redactie_ziet_en_kiest_alleen_de_eigen_omgeving(self):
        vreemd = Synoniem.objects.create(omgeving=self.anders, woord="dijk", alternatieven="kade")
        c = self.als(self.redacteur)
        lijst = c.get("/beheer/kennisbank/synoniem/").content.decode()
        self.assertIn("zwerfboot", lijst)
        self.assertNotIn("kade", lijst)
        self.assertEqual(c.get(f"/beheer/kennisbank/synoniem/{vreemd.pk}/change/").status_code, 302)
        r = c.post(self.TOEVOEGEN, {"omgeving": self.anders.pk, "woord": "sluis", "alternatieven": "schutsluis"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Synoniem.objects.filter(woord="sluis").exists())

    def test_redactie_mag_een_synoniem_weghalen(self):
        s = Synoniem.objects.get(omgeving=self.hh, woord="zwerfboot")
        r = self.als(self.redacteur).post(f"/beheer/kennisbank/synoniem/{s.pk}/delete/", {"post": "yes"})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Synoniem.objects.filter(pk=s.pk).exists())
        self.assertEqual(self.api("wrak"), ([], None))

    def test_een_lezer_komt_er_niet_in(self):
        r = self.als(self.lezer).get(self.TOEVOEGEN)
        self.assertIn(r.status_code, (302, 403))
        r = self.als(self.lezer).post(self.TOEVOEGEN, {"omgeving": self.hh.pk, "woord": "a1", "alternatieven": "b1"})
        self.assertFalse(Synoniem.objects.filter(woord="a1").exists())

    def test_de_knop_uit_de_statistieken_vult_het_formulier_voor(self):
        r = self.als(self.redacteur).get(self.TOEVOEGEN, {"alternatieven": "aanschrijving", "omgeving": self.hh.pk})
        html = r.content.decode()
        self.assertIn("aanschrijving</textarea>", html)
        self.assertRegex(html, rf'<option value="{self.hh.pk}" selected')
        # Een omgeving waar je geen redacteur bent wordt niet voorgekozen.
        r = self.als(self.redacteur).get(self.TOEVOEGEN, {"alternatieven": "x", "omgeving": self.anders.pk})
        self.assertNotIn("selected>Ander onderdeel", r.content.decode())


# --- De API: kop, vervolg, oordeel en statistieken ---------------------------------------------------------------


class Api(ZoekBasis):
    def test_kop_alleen_als_er_is_geholpen_en_altijd_gewone_tekens(self):
        titels, hulp = self.api("rappel")
        self.assertIsNone(hulp)
        self.assertTrue(titels[0].startswith("Rappel versturen"))
        titels, hulp = self.api("rapel")
        self.assertEqual(hulp, {"verbeterd": [{"van": "rapel", "naar": ["rappel"]}]})
        Synoniem.objects.create(omgeving=self.hh, woord="dossier", alternatieven="straße")
        r = self.als(self.lezer).get("/api/v1/artikelen", {"q": "straße"})
        self.assertEqual(r.status_code, 200)
        r.headers["X-KB-Zoekhulp"].encode("ascii")
        self.assertEqual(json.loads(r.headers["X-KB-Zoekhulp"])["synoniemen"][0]["van"], "straße")
        self.assertIsInstance(r.json(), list)  # het antwoord zelf blijft een lijst

    def test_zonder_zoektekst_geen_kop_en_alles_op_titel(self):
        r = self.als(self.lezer).get("/api/v1/artikelen")
        self.assertNotIn("X-KB-Zoekhulp", r.headers)
        titels = [a["titel"] for a in r.json()]
        self.assertEqual(titels, sorted(titels))

    def test_vervolgzoekopdracht_telt_bij_de_vorige_term(self):
        self.api("Rappel  Sturen", registreer="1")
        self.api("aanmaning", registreer="1", vervolg_op=" rappel sturen ")
        t = ZoekTelling.objects.get(term="rappel sturen")
        self.assertEqual((t.aantal, t.vervolg), (1, 1))
        self.assertEqual(ZoekTelling.objects.get(term="aanmaning").vervolg, 0)

    def test_vervolg_telt_niet_zonder_registreer_bij_dezelfde_term_of_een_onbekende_term(self):
        self.api("rappel", registreer="1")
        self.api("aanmaning", vervolg_op="rappel")  # tijdens het typen
        self.api("rappel", registreer="1", vervolg_op="RAPPEL")  # dezelfde term nog eens
        self.api("aanmaning", registreer="1", vervolg_op="nooit gezocht")
        self.api("aanmaning", registreer="1", vervolg_op="x")
        self.assertEqual(ZoekTelling.objects.get(term="rappel").vervolg, 0)
        self.assertFalse(ZoekTelling.objects.filter(term="nooit gezocht").exists())

    def test_vervolg_telt_alleen_in_de_eigen_omgeving(self):
        maak(self.anders, "Rappel bij de buren", "Een rappel.")
        self.api("rappel", self.buitenstaander, registreer="1")
        self.api("rappel", registreer="1")
        self.api("iets anders", registreer="1", vervolg_op="rappel")
        self.assertEqual(ZoekTelling.objects.get(term="rappel", omgeving=self.hh).vervolg, 1)
        self.assertEqual(ZoekTelling.objects.get(term="rappel", omgeving=self.anders).vervolg, 0)

    def oordeel(self, artikel, nuttig, gebruiker=None):
        return self.als(gebruiker or self.lezer).post(
            f"/api/v1/artikelen/{artikel.pk}/oordeel", {"nuttig": nuttig}, content_type="application/json"
        )

    def test_oordeel_telt_per_versie_en_zonder_gebruiker(self):
        a = self.live.get(slug="rappel-versturen")
        self.assertEqual(self.oordeel(a, True).status_code, 204)
        self.assertEqual(self.oordeel(a, True).status_code, 204)
        self.assertEqual(self.oordeel(a, False).status_code, 204)
        o = ArtikelOordeel.objects.get(artikel=a)
        self.assertEqual((o.versie, o.nuttig, o.niet_nuttig), (a.versie, 2, 1))
        velden = {f.name for f in ArtikelOordeel._meta.get_fields()}
        self.assertEqual(velden, {"id", "artikel", "versie", "nuttig", "niet_nuttig"})  # geen gebruiker, geen moment
        Artikel.objects.filter(pk=a.pk).update(versie=a.versie + 1)
        self.oordeel(a, False)
        self.assertEqual(ArtikelOordeel.objects.filter(artikel=a).count(), 2)

    def test_oordeel_wil_ja_of_nee(self):
        a = self.live.get(slug="rappel-versturen")
        for fout in ("ja", 1, None, "true"):
            self.assertEqual(self.oordeel(a, fout).status_code, 400, fout)
        r = self.als(self.lezer).post(f"/api/v1/artikelen/{a.pk}/oordeel", {}, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(ArtikelOordeel.objects.exists())

    def test_oordeel_alleen_op_wat_je_mag_lezen(self):
        a = self.live.get(slug="rappel-versturen")
        self.assertEqual(self.oordeel(a, True, self.buitenstaander).status_code, 404)
        self.assertEqual(self.oordeel(self.concept, True).status_code, 404)
        self.client.logout()
        r = self.client.post(f"/api/v1/artikelen/{a.pk}/oordeel", {"nuttig": True}, content_type="application/json")
        self.assertIn(r.status_code, (401, 403))
        self.assertFalse(ArtikelOordeel.objects.exists())

    def test_oordeel_heeft_een_grens(self):
        from kennisbank.api import OordeelThrottle

        a = self.live.get(slug="rappel-versturen")
        self.assertEqual(settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["oordeel"], "30/hour")
        try:
            OordeelThrottle.THROTTLE_RATES = {**settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], "oordeel": "2/hour"}
            self.assertEqual([self.oordeel(a, True).status_code for _ in range(3)], [204, 204, 429])
        finally:
            OordeelThrottle.THROTTLE_RATES = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        self.assertEqual(ArtikelOordeel.objects.get(artikel=a).nuttig, 2)

    def test_statistieken_tonen_oordelen_vervolg_en_de_synoniemknop(self):
        a = self.live.get(slug="rappel-versturen")
        self.oordeel(a, True)
        self.oordeel(a, False)
        self.oordeel(a, False)
        Artikel.objects.filter(pk=a.pk).update(versie=a.versie + 1)  # oordelen over alle versies tellen op
        self.oordeel(a, True)
        self.api("aanschrijving & xyzabc", registreer="1")
        self.api("rappel", registreer="1")
        self.api("zwerfboot", registreer="1", vervolg_op="rappel")
        s = self.als(self.redacteur).get("/api/v1/statistieken").json()
        rij = next(r for r in s["artikelen"] if r["titel"].startswith("Rappel versturen"))
        self.assertEqual((rij["nuttig"], rij["niet_nuttig"]), (2, 2))
        ander = next(r for r in s["artikelen"] if r["titel"].startswith("Zwerfboot"))
        self.assertEqual((ander["nuttig"], ander["niet_nuttig"]), (0, 0))
        zonder = {z["term"]: z for z in s["zoektermen_zonder_resultaat"]}
        self.assertEqual(
            zonder["aanschrijving & xyzabc"]["synoniem_url"],
            f"/beheer/kennisbank/synoniem/add/?alternatieven=aanschrijving+%26+xyzabc&omgeving={self.hh.pk}",
        )
        self.assertEqual(s["zoektermen_met_vervolg"], [{"term": "rappel", "aantal": 1, "vervolg": 1}])

    def test_alleen_iets_in_de_buurt_telt_als_zonder_resultaat(self):
        titels, hulp = self.api("zwerfboot gezonken melden", registreer="1")
        self.assertTrue(titels and hulp == {"dichtbij": True})
        self.api("rapel", registreer="1")  # verbeterd en gevonden: dat is wel een resultaat
        self.assertEqual(ZoekTelling.objects.get(term="zwerfboot gezonken melden").zonder_resultaat, 1)
        self.assertEqual(ZoekTelling.objects.get(term="rapel").zonder_resultaat, 0)

    def test_statistieken_van_een_andere_omgeving_blijven_daar(self):
        maak(self.anders, "Rappel bij de buren", "Een rappel.")
        self.api("rappel", self.buitenstaander, registreer="1")
        self.api("dijk", self.buitenstaander, registreer="1", vervolg_op="rappel")
        s = self.als(self.redacteur).get("/api/v1/statistieken").json()
        self.assertEqual(s["zoektermen_met_vervolg"], [])


# --- Z5: zoeken in het beheer ------------------------------------------------------------------------------------


class BeheerZoeken(ZoekBasis):
    LIJST = "/beheer/kennisbank/artikel/"

    def titels(self, r):
        return [a.titel for a in r.context["cl"].result_list]

    def test_beheer_zoekt_met_dezelfde_hulp_en_het_beste_bovenaan(self):
        r = self.als(self.redacteur).get(self.LIJST, {"q": "rapel"})
        self.assertTrue(self.titels(r)[0].startswith("Rappel versturen"))
        self.assertIn("Resultaten voor rappel; je zocht op rapel.", [str(m) for m in r.context["messages"]])
        r = self.client.get(self.LIJST, {"q": "wrak"})
        self.assertTrue(self.titels(r)[0].startswith("Zwerfboot aangetroffen"))

    def test_beheer_vindt_ook_concepten_en_gewoon_zoeken_geeft_geen_melding(self):
        r = self.als(self.redacteur).get(self.LIJST, {"q": "concepttekst"})
        self.assertEqual(self.titels(r), ["Geheim concept"])
        self.assertEqual(list(r.context["messages"]), [])

    def test_volgorde_is_relevantie_tenzij_je_een_kolom_kiest(self):
        maak(self.hh, "Aanvulling", "Eén keer het woord rappel.")
        r = self.als(self.redacteur).get(self.LIJST, {"q": "rappel"})
        zonder = self.titels(r)
        self.assertTrue(zonder[0].startswith("Rappel versturen"))
        self.assertGreater(zonder.index("Aanvulling"), 0)
        r = self.client.get(self.LIJST, {"q": "rappel", "o": "1"})
        gesorteerd = self.titels(r)
        self.assertEqual(sorted(zonder), sorted(gesorteerd))
        self.assertEqual(gesorteerd[0], "Aanvulling")

    def test_een_getal_zoekt_ook_op_het_nummer(self):
        a = self.live.get(slug="zwerfboot")
        r = self.als(self.redacteur).get(self.LIJST, {"q": str(a.pk)})
        self.assertEqual(self.titels(r)[0], a.titel)

    def test_niets_gevonden_geeft_een_lege_lijst_zonder_melding(self):
        r = self.als(self.redacteur).get(self.LIJST, {"q": "xyzabc"})
        self.assertEqual(self.titels(r), [])
        self.assertEqual(list(r.context["messages"]), [])

    def test_redactie_van_een_andere_omgeving_vindt_dit_niet(self):
        groep = Group.objects.create(name="redactie-anders")
        Toegang.objects.create(omgeving=self.anders, groep=groep, rol=Rol.REDACTEUR)
        buur = User.objects.create_user("buur", password="x")
        buur.groups.add(groep)
        r = self.als(buur).get(self.LIJST, {"q": "rapel"})
        self.assertEqual(self.titels(r), [])
        self.assertEqual(list(r.context["messages"]), [])


# --- De migratie ------------------------------------------------------------------------------------------------


class Migratie(TransactionTestCase):
    """Een bestaande installatie krijgt bij ``migrate`` de extensies, zoekdocumenten zonder accenten en een
    gevulde woordenlijst, zonder dat iemand een artikel opnieuw hoeft op te slaan."""

    def _naar(self, naam):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([("kennisbank", naam)])
        return executor.loader.project_state([("kennisbank", naam)]).apps

    def test_bestaande_artikelen_zijn_na_de_migratie_vindbaar_met_de_nieuwe_hulp(self):
        oud = self._naar("0033_tekst_concept")
        try:
            Omgeving = oud.get_model("kennisbank", "Omgeving")
            ArtikelOud = oud.get_model("kennisbank", "Artikel")
            Sectie = oud.get_model("kennisbank", "Sectie")
            o = Omgeving.objects.create(slug="mig", naam="Migratie")
            a = ArtikelOud.objects.create(
                omgeving=o, slug="cafe", titel="Het café aan de kade", samenvatting="x", status="gepubliceerd", versie=1
            )
            Sectie.objects.create(artikel=a, volgorde=1, kop="Terras", inhoud="<p>De steigervergunning.</p>")
        finally:
            self._naar("0034_zoeken")
        with connection.cursor() as c:
            c.execute("SELECT extname FROM pg_extension WHERE extname IN ('pg_trgm', 'unaccent') ORDER BY 1")
            self.assertEqual([r[0] for r in c.fetchall()], ["pg_trgm", "unaccent"])
        woorden = set(Zoekwoord.objects.filter(omgeving_id=o.pk).values_list("woord", flat=True))
        self.assertLessEqual({"cafe", "kade", "terras", "steigervergunning"}, woorden)
        qs = Artikel.objects.filter(omgeving_id=o.pk)
        for vraag in ("cafe", "café", "steigervergunnig", "vergunning"):
            self.assertEqual([x.slug for x in zoeken.zoek(qs, vraag)[0]], ["cafe"], vraag)
