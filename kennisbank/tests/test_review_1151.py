"""1.15.1: reparaties na de onafhankelijke review van 10 november (rapport in het project:
review-sinds-1.11.0-onafhankelijk.md). Elke test noemt het nummer van de bevinding.
"""

from urllib.parse import urlencode

from django.contrib.auth.models import Group
from django.db import connection
from django.test.utils import CaptureQueriesContext

from kennisbank import diensten
from kennisbank.models import Kladversie, VoorstelBericht, VoorstelStatus
from kennisbank.tests.test_bakken import Basis, wijzig_url


class KladversieHerrijstNietTests(Basis):
    """Bevinding 1: na opslaan mocht het baken van de oude pagina de kladversie niet heropenen."""

    def url(self, artikel=None):
        basis = "/beheer/kennisbank/artikel/"
        return f"{basis}{artikel.pk}/kladversie/" if artikel else f"{basis}kladversie/"

    def post(self, artikel, **extra):
        data = {"velden": '{"titel": "x", "inhoud": "<p>werk</p>"}', "basis_stempel": "", **extra}
        return self.client.post(self.url(artikel), data)

    def test_baken_van_een_al_opgeslagen_scherm_wordt_geweigerd(self):
        for artikel in (self.artikel, None):
            with self.subTest(nieuw=artikel is None):
                c = self.als(self.anna)
                geopend = c.get(self.url(artikel)).json()["server_nu"]
                self.assertEqual(self.post(artikel, geopend_op=geopend).status_code, 200)
                diensten.klad_afsluiten(self.anna, artikel)  # opslaan
                r = self.post(artikel, geopend_op=geopend)  # het baken van de oude pagina
                self.assertEqual(r.status_code, 409)
                rij = Kladversie.objects.get(gebruiker=self.anna, artikel=artikel)
                self.assertIsNotNone(rij.afgesloten_op, "de kladversie is weer opengegaan")
                self.assertIsNone(c.get(self.url(artikel)).json()["mijn"])

    def test_nieuw_werk_in_een_nieuw_scherm_mag_wel(self):
        c = self.als(self.anna)
        diensten.klad_afsluiten(self.anna, self.artikel)
        geopend = c.get(self.url(self.artikel)).json()["server_nu"]  # nieuw scherm, ná het afsluiten
        self.assertEqual(self.post(self.artikel, geopend_op=geopend).status_code, 200)
        self.assertIsNone(Kladversie.objects.get(gebruiker=self.anna, artikel=self.artikel).afgesloten_op)

    def test_na_weggooien_mag_hetzelfde_scherm_verder(self):
        c = self.als(self.anna)
        self.post(self.artikel, geopend_op=c.get(self.url(self.artikel)).json()["server_nu"])
        r = c.post(self.url(self.artikel), {"weggooien": "1"})
        nieuw_geopend = r.json()["server_nu"]
        self.assertEqual(self.post(self.artikel, geopend_op=nieuw_geopend).status_code, 200)


class VerouderdFormulierTests(Basis):
    """Bevinding 2: een scherm dat al even openstaat, draait het werk van een collega niet terug."""

    def formulier(self, geladen, **velden):
        data = {
            "geladen_status": geladen["status"],
            "geladen_eigenaar": geladen["eigenaar"],
            "status": velden.pop("status", geladen["status"]),
            "naar_bak": velden.pop("naar_bak", geladen["eigenaar"]),
            "berichten-TOTAL_FORMS": "1",
            "berichten-INITIAL_FORMS": "0",
            "berichten-MIN_NUM_FORMS": "0",
            "berichten-MAX_NUM_FORMS": "1000",
            "berichten-0-tekst": velden.pop("bericht", ""),
        }
        return urlencode(data)

    def test_een_oud_formulier_laat_het_oppakken_van_een_collega_staan(self):
        # Ronde A: het oude formulier verwerkt voor een open voorstel niets meer (het gaat naar de editor).
        v = self.voorstel()
        geladen = {"status": v.status, "eigenaar": ""}  # Anna opent het scherm
        diensten.voorstel_naar_bak(v, self.bram, self.bram)  # Bram pakt het intussen op
        r = self.als(self.anna).post(
            wijzig_url(v),
            self.formulier(geladen, naar_bak="", bericht="We kijken ernaar"),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(r.status_code, 302)
        self.assertIn("?voorstel=", r["Location"])
        v.refresh_from_db()
        self.assertEqual((v.eigenaar, v.status), (self.bram, VoorstelStatus.IN_BEHANDELING))
        self.assertEqual(VoorstelBericht.objects.filter(voorstel=v).count(), 0)

    def test_api_met_verwachte_status(self):
        v = self.voorstel()
        diensten.voorstel_naar_bak(v, self.bram, self.bram)
        r = self.als(self.anna).patch(
            f"/api/v1/voorstellen/{v.pk}",
            {"status": "afgewezen", "verwachte_status": "nieuw"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 409)
        v.refresh_from_db()
        self.assertEqual(v.status, VoorstelStatus.IN_BEHANDELING)


class PrivacyTests(Basis):
    """Bevinding 3 en de keuzes van Alex: alleen de datum, en de redactie kan verbergen."""

    def test_collegas_zien_alleen_de_datum(self):
        self.voorstel()
        p = self.als(self.piet).get("/api/v1/voorstellen?lijst=alle").json()[0]
        self.assertRegex(p["ingediend_op"], r"^\d{4}-\d{2}-\d{2}$")

    def test_verborgen_voorstel_is_voor_collegas_weg(self):
        v = self.voorstel(verborgen=True)
        self.assertEqual(self.als(self.piet).get("/api/v1/voorstellen?lijst=alle").json(), [])
        self.assertEqual(self.client.put(f"/api/v1/voorstellen/{v.pk}/steun").status_code, 404)
        # De indiener ziet het gewoon.
        self.assertEqual(len(self.als(self.lies).get("/api/v1/voorstellen?lijst=mijn").json()), 1)

    def test_verbergen_via_de_lade(self):
        v = self.voorstel()
        r = self.als(self.anna).post(f"/beheer/voorstel/{v.pk}/lade/", {"actie": "verbergen", "waarde": "1"})
        self.assertEqual(r.status_code, 200)
        v.refresh_from_db()
        self.assertTrue(v.verborgen)

    def test_indienvenster_zegt_wie_wat_ziet(self):
        html = self.als(self.lies).get("/").content.decode()
        self.assertIn("Alleen procesmanagement ziet wie het indiende", html)


class EigenaarZonderRechtenTests(Basis):
    """Bevinding 4: geen voorstellen in de bak van iemand die er niet meer bij kan."""

    def test_artikel_verhuist_naar_een_andere_omgeving(self):
        v = diensten.voorstel_naar_bak(self.voorstel(), self.anna, self.anna)
        self.artikel.omgeving = self.zuid
        self.artikel.save()
        v.refresh_from_db()
        self.assertIsNone(v.eigenaar)
        self.assertEqual(v.status, VoorstelStatus.NIEUW)

    def test_redacteur_raakt_zijn_rol_kwijt(self):
        v = diensten.voorstel_naar_bak(self.voorstel(), self.anna, self.anna)
        self.anna.groups.remove(Group.objects.get(name="noord-redactie"))
        v.refresh_from_db()
        self.assertIsNone(v.eigenaar)

    def test_opschoonronde_als_vangnet(self):
        v = diensten.voorstel_naar_bak(self.voorstel(), self.anna, self.anna)
        # Rechtstreeks in de database, zonder signaal: zoals een import of een fout in een koppeling.
        Group.objects.get(name="noord-redactie").user_set.through.objects.filter(user=self.anna).delete()
        self.assertEqual(diensten.bakken_rechtzetten(), 1)
        v.refresh_from_db()
        self.assertIsNone(v.eigenaar)


class EigenaarschapTests(Basis):
    def test_wie_afhandelt_wordt_eigenaar(self):  # bevinding 6, keuze van Alex
        v = diensten.voorstel_naar_bak(self.voorstel(), self.bram, self.bram)
        url = f"/api/v1/voorstellen/{v.pk}"
        self.als(self.anna).patch(
            url, {"status": "verwerkt", "terugkoppeling": "Gedaan."}, content_type="application/json"
        )
        v.refresh_from_db()
        self.assertEqual(v.eigenaar, self.anna)

    def test_terug_naar_nieuw_laat_de_eigenaar_staan(self):  # bevinding 7, besluit van Alex: zo laten
        v = diensten.voorstel_naar_bak(self.voorstel(), self.anna, self.anna)
        self.als(self.anna).patch(f"/api/v1/voorstellen/{v.pk}", {"status": "nieuw"}, content_type="application/json")
        v.refresh_from_db()
        self.assertEqual((v.eigenaar, v.status), (self.anna, VoorstelStatus.NIEUW))

    def test_steun_intrekken_na_afhandeling_kan_niet(self):  # bevinding 8
        v = self.voorstel()
        diensten.steun_geven(v, self.piet)
        v.status = VoorstelStatus.VERWERKT
        v.save()
        self.assertEqual(self.als(self.piet).delete(f"/api/v1/voorstellen/{v.pk}/steun").status_code, 409)
        self.assertEqual(v.steun.count(), 1)


class KladversielijstTests(Basis):
    def test_vast_aantal_vragen(self):  # bevinding 9
        c = self.als(self.anna)

        def tel():
            c.get("/beheer/kennisbank/kladversie/")
            with CaptureQueriesContext(connection) as q:
                self.assertEqual(c.get("/beheer/kennisbank/kladversie/").status_code, 200)
            return len(q)

        diensten.klad_opslaan(self.anna, self.artikel, {"titel": "a"}, redactie_omgevingen={self.noord.pk})
        weinig = tel()
        for i in range(6):
            from kennisbank.models import Artikel

            a = Artikel.objects.create(omgeving=self.noord, titel=f"A{i}", samenvatting="x", inhoud="<p>x</p>")
            diensten.klad_opslaan(self.bram, a, {"titel": f"a{i}"}, redactie_omgevingen={self.noord.pk})
        self.assertEqual(tel(), weinig)


class KleineWensenTests(Basis):
    def test_api_documentatie_alleen_voor_beheerders(self):
        self.assertFalse(self.als(self.anna).get("/api/v1/ik").json()["is_beheerder"])
        self.assertFalse(self.als(self.lies).get("/api/v1/ik").json()["is_beheerder"])

    def test_geen_demo_label_meer(self):
        html = self.als(self.lies).get("/").content.decode()
        self.assertNotIn('class="proto"', html)

    def test_nieuw_voorstel_mail_wijst_naar_de_werkvoorraad(self):
        from django.core import mail
        from django.test import override_settings

        self.voorstel()
        with override_settings(KB_EMAIL_AAN=True):
            diensten.verstuur_voorstellenmail()
        self.assertTrue(mail.outbox)
        self.assertIn("/beheer/", mail.outbox[0].body)
        self.assertIn("werkplek", mail.outbox[0].body)
