"""1.35.1 (wens Alex): een functioneel beheerder begint in het beheer bij *Alle onderdelen*.

Hij is geen redacteur, maar mag wel overal in. De werkplek van de redactie is voor hem dus geen logisch begin.
Ligt er toch iets in zijn eigen bak (per ongeluk opgepakt, of toegewezen), dan zegt de startpagina dat: het
voorstel is dan uit de werkvoorraad van de redactie en mag niet ongemerkt blijven liggen.
"""

from unittest import mock

from django.contrib.auth.models import User

from kennisbank import status, werkoverzicht
from kennisbank.tests.test_bakken import Basis


class BeheerderStart(Basis):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.baas = User.objects.create_superuser("baas", password="x", first_name="Bea", last_name="Beheer")
        # Beheerder die óók via een groep redacteur is: die houdt de werkplek van de redactie.
        cls.dubbel = User.objects.create_superuser("dubbel", password="x")
        cls.dubbel.groups.add(*cls.anna.groups.all())

    def start(self, gebruiker, **params):
        r = self.als(gebruiker).get("/beheer/", params)
        self.assertEqual(r.status_code, 200)
        return r, r.context["werkplek"], r.content.decode()

    def test_wie_is_alleen_beheerder(self):
        self.assertTrue(werkoverzicht.alleen_beheerder(self.baas))
        self.assertFalse(werkoverzicht.alleen_beheerder(self.dubbel))
        self.assertFalse(werkoverzicht.alleen_beheerder(self.anna))
        self.assertFalse(werkoverzicht.alleen_beheerder(self.lies))

    def test_beheerder_begint_bij_alle_onderdelen(self):
        self.voorstel()  # er ligt werk voor de redactie; dat verandert de startpagina van de beheerder niet
        r, w, html = self.start(self.baas)
        self.assertTrue(w["is_alles"])
        self.assertEqual(w["titel"], "Alle onderdelen")
        self.assertIn("Omgevingen", html)
        self.assertIn("Toegang", html)

    def test_redacteur_begint_zoals_altijd_bij_een_bak(self):
        self.voorstel()
        for gebruiker in (self.anna, self.dubbel):
            r, w, html = self.start(gebruiker)
            self.assertFalse(w["is_alles"], gebruiker)
            self.assertFalse(w["beheerder"], gebruiker)
            self.assertIsNone(w["status"])
            self.assertNotIn("kb-beheer-seintje", html)
            # Voor hem staat Alle onderdelen onderaan, zonder de kop Beheer.
            self.assertNotIn('<h2 class="kb-kolomkop">Beheer</h2>', html)
            self.assertIn("?bak=alles", html)

    def test_redacteur_op_alle_onderdelen_ziet_geen_status_en_geen_regel_over_zijn_bak(self):
        """De statuspagina is alleen voor de beheerder; de samenvatting ervan dus ook."""
        self.voorstel(eigenaar=self.anna)
        for gebruiker in (self.anna, self.dubbel):
            r, w, html = self.start(gebruiker, bak="alles")
            self.assertTrue(w["is_alles"])
            self.assertIsNone(w["status"])
            self.assertIsNone(w["eigen_bak"])
            self.assertNotIn("kb-beheer-seintje", html)
            self.assertNotIn("statuspagina", html)

    def test_in_de_kolom_staat_alle_onderdelen_voor_de_beheerder_bovenaan_en_een_keer(self):
        r, w, html = self.start(self.baas)
        self.assertEqual(html.count("?bak=alles"), 1)
        self.assertLess(html.index('<h2 class="kb-kolomkop">Beheer</h2>'), html.index("Werkvoorraad</h2>"))
        self.assertIn('aria-current="page">Alle onderdelen', html)
        # De bakken van de redactie staan er nog: hij kan overal in.
        self.assertIn("?bak=concepten", html)
        self.assertEqual(self.als(self.baas).get("/beheer/", {"bak": "concepten"}).status_code, 200)

    def test_ligt_er_iets_bij_de_beheerder_dan_zegt_de_startpagina_dat(self):
        r, w, html = self.start(self.baas)
        self.assertIsNone(w["eigen_bak"])
        self.assertNotIn("Bij jou lig", html)
        self.voorstel(eigenaar=self.baas)
        r, w, html = self.start(self.baas)
        self.assertTrue(w["is_alles"])  # hij landt nog steeds op Alle onderdelen
        self.assertIn("Bij jou ligt 1 verbetervoorstel.", html)
        self.assertIn(f'href="/beheer/?bak=u{self.baas.pk}">Open je bak</a>', html)
        self.assertIn("kb-beheer-let-op", html)
        self.voorstel(eigenaar=self.baas)
        self.voorstel(eigenaar=self.anna)  # van een ander: telt niet mee
        self.assertIn("Bij jou liggen 2 verbetervoorstellen.", self.start(self.baas)[2])
        # In een bak staat de regel niet; daar zie je de voorstellen zelf.
        self.assertNotIn("Bij jou lig", self.start(self.baas, bak=f"u{self.baas.pk}")[2])

    def test_de_redacteur_ziet_het_voorstel_in_de_bak_van_de_beheerder(self):
        """Het voorstel is niet weg: de bak van de beheerder staat bij de redactie in de kolom."""
        self.voorstel(eigenaar=self.baas)
        r, w, html = self.start(self.anna)
        bak = next(p for p in w["menu"]["personen"] if p["sleutel"] == f"u{self.baas.pk}")
        self.assertEqual((bak["naam"], bak["aantal"]), ("Bea Beheer", 1))

    def test_statusregel_in_drie_standen(self):
        def met(*standen):
            rijen = [{"naam": "x", "stand": s, "waarde": "", "advies": ""} for s in standen]
            totaal = "fout" if "fout" in standen else ("let_op" if "let_op" in standen else "goed")
            ov = {"groepen": [{"titel": "t", "rijen": rijen}], "totaal": totaal, "gemeten_op": None}
            with mock.patch.object(status, "overzicht", return_value=ov):
                return self.start(self.baas)[2]

        html = met("goed", "goed")
        self.assertIn("<b>Alles loopt.</b>", html)
        self.assertNotIn("kb-beheer-let-op", html)
        html = met("goed", "let_op")
        self.assertIn("<b>1 punt vraagt aandacht</b>", html)
        self.assertIn("kb-beheer-let-op", html)
        html = met("fout", "let_op", "goed")
        self.assertIn("<b>2 punten vragen aandacht</b>", html)
        self.assertIn('href="/beheer/kennisbank/systeemstand/">Naar de statuspagina</a>', html)

    def test_statusregel_klopt_met_de_statuspagina_en_staat_alleen_op_alle_onderdelen(self):
        ov = status.overzicht()
        punten = sum(1 for g in ov["groepen"] for rij in g["rijen"] if rij["stand"] != "goed")
        r, w, html = self.start(self.baas)
        self.assertEqual((w["status"]["stand"], w["status"]["punten"]), (ov["totaal"], punten))
        self.assertEqual(self.als(self.baas).get(w["status"]["url"]).status_code, 200)
        with mock.patch.object(status, "overzicht", side_effect=AssertionError("niet meten in een bak")):
            r, w, html = self.start(self.baas, bak="concepten")
        self.assertIsNone(w["status"])

    def test_terug_naar_de_werkplek_onthoudt_ook_alle_onderdelen(self):
        c = self.als(self.baas)
        self.assertTrue(c.get("/beheer/").context["werkplek"]["is_alles"])
        self.assertEqual(c.get("/beheer/", {"bak": "concepten"}).context["werkplek"]["gekozen"], "concepten")
        self.assertEqual(c.get("/beheer/").context["werkplek"]["gekozen"], "concepten")  # terug waar hij was
        c.get("/beheer/", {"bak": "alles"})
        self.assertTrue(c.get("/beheer/").context["werkplek"]["is_alles"])
        # Voor de redacteur blijft het zoals het was: Alle onderdelen wordt niet onthouden.
        c = self.als(self.anna)
        c.get("/beheer/", {"bak": "concepten"})
        c.get("/beheer/", {"bak": "alles"})
        self.assertEqual(c.get("/beheer/").context["werkplek"]["gekozen"], "concepten")

    def test_het_afhandelscherm_toont_dezelfde_kolom(self):
        v = self.voorstel(status="verwerkt", terugkoppeling="Dank.", behandeld_door=self.anna)
        html = self.als(self.baas).get(f"/beheer/voorstel/{v.pk}/").content.decode()
        self.assertIn('<h2 class="kb-kolomkop">Beheer</h2>', html)
        self.assertEqual(html.count("?bak=alles"), 1)
        html = self.als(self.anna).get(f"/beheer/voorstel/{v.pk}/").content.decode()
        self.assertNotIn('<h2 class="kb-kolomkop">Beheer</h2>', html)
        self.assertEqual(html.count("?bak=alles"), 1)
