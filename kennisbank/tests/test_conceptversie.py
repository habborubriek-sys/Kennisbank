"""1.17.0 stap B: een conceptversie naast de gepubliceerde versie (ontwerp 11 november).

Medewerkers zien de gepubliceerde tekst; de redactie werkt in de conceptversie. Publiceren gaat via het
gewone opslaan en ruimt de conceptversie op.
"""

from urllib.parse import urlencode

from django.contrib.admin.models import LogEntry

from kennisbank import diensten
from kennisbank.models import Artikel, ArtikelVersie, Conceptversie, FavorietenMail, Kladversie, Status
from kennisbank.tests.test_bakken import Basis
from kennisbank.tests.test_kennisbank import beheerdata


class ConceptversieTests(Basis):
    def setUp(self):
        self.a = Artikel.objects.create(
            omgeving=self.noord,
            titel="Rappel versturen",
            samenvatting="Hoe je een rappel verstuurt, stap voor stap.",
            inhoud="<p>Oude tekst</p>",
            status=Status.GEPUBLICEERD,
        )
        diensten.herbouw_secties(self.a)
        diensten.registreer_publicatie(self.a, self.anna)
        self.a.refresh_from_db()
        self.url = f"/beheer/kennisbank/artikel/{self.a.pk}/change/"

    def post(self, data, **knop):
        return self.client.post(
            self.url, urlencode({**data, **knop}, doseq=True), content_type="application/x-www-form-urlencoded"
        )

    def concept_opslaan(self, wie=None, **velden):
        self.als(wie or self.anna)
        data = beheerdata(self.a, **{"inhoud": "<p>Nieuwe tekst</p>", "wijzigingstoelichting": "", **velden})
        data.setdefault("geladen_concept", "")
        return self.post(data, _conceptversie="1")

    def test_opslaan_als_conceptversie_raakt_het_artikel_niet(self):
        r = self.concept_opslaan(titel="Rappel versturen (nieuw)")
        self.assertEqual(r.status_code, 302, r.content[:600])
        self.a.refresh_from_db()
        self.assertEqual(self.a.inhoud, "<p>Oude tekst</p>")
        self.assertEqual(self.a.titel, "Rappel versturen")
        self.assertEqual(self.a.versie, 1)
        self.assertEqual(ArtikelVersie.objects.filter(artikel=self.a).count(), 1)
        self.assertFalse(FavorietenMail.objects.exists())
        c = Conceptversie.objects.get(artikel=self.a)
        self.assertEqual((c.velden["titel"], c.velden["inhoud"]), ("Rappel versturen (nieuw)", "<p>Nieuwe tekst</p>"))
        self.assertEqual((c.gestart_door, c.basis_versie), (self.anna, 1))
        # Zonder toelichting: die hoort bij publiceren, niet bij een conceptversie.
        self.assertIn(
            "Conceptversie opgeslagen",
            LogEntry.objects.filter(object_id=str(self.a.pk)).latest("action_time").get_change_message(),
        )

    def test_medewerkers_zien_de_gepubliceerde_tekst(self):
        self.concept_opslaan()
        r = self.als(self.lies).get(f"/api/v1/artikelen/{self.a.pk}")
        self.assertIn("Oude tekst", r.content.decode())
        self.assertNotIn("Nieuwe tekst", r.content.decode())

    def test_openen_toont_de_conceptversie(self):
        self.concept_opslaan()
        r = self.als(self.bram).get(self.url)
        html = r.content.decode()
        self.assertIn("Medewerkers zien versie", html)
        self.assertIn("Nieuwe tekst", r.context["adminform"].form.initial["inhoud"])
        self.assertIn("Medewerkers zien nog versie 1", html)

    def test_publiceren_vanuit_de_conceptversie(self):
        self.concept_opslaan()
        c = Conceptversie.objects.get(artikel=self.a)
        self.als(self.bram)
        data = beheerdata(self.a, inhoud="<p>Nieuwe tekst</p>", geladen_concept=c.stempel)
        r = self.post(data, _save="Opslaan")
        self.assertEqual(r.status_code, 302, r.content[:600])
        self.a.refresh_from_db()
        self.assertEqual((self.a.inhoud, self.a.versie), ("<p>Nieuwe tekst</p>", 2))
        self.assertFalse(Conceptversie.objects.filter(artikel=self.a).exists())

    def test_publiceren_vraagt_nog_steeds_een_toelichting(self):
        self.concept_opslaan()
        c = Conceptversie.objects.get(artikel=self.a)
        self.als(self.anna)
        r = self.post(
            beheerdata(self.a, inhoud="<p>Nieuwe tekst</p>", wijzigingstoelichting="", geladen_concept=c.stempel),
            _save="1",
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("wijzigingstoelichting", r.context["adminform"].form.errors)
        self.assertTrue(Conceptversie.objects.filter(artikel=self.a).exists())

    def test_twee_redacteuren_in_dezelfde_conceptversie(self):
        self.concept_opslaan()
        oud = Conceptversie.objects.get(artikel=self.a).stempel
        # Bram slaat de conceptversie op...
        self.concept_opslaan(wie=self.bram, geladen_concept=oud, inhoud="<p>Van Bram</p>")
        # ...en Anna, met een scherm van daarvoor, kan hem niet ongemerkt overschrijven.
        r = self.concept_opslaan(wie=self.anna, geladen_concept=oud, inhoud="<p>Van Anna</p>")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Conceptversie.objects.get(artikel=self.a).velden["inhoud"], "<p>Van Bram</p>")
        berichten = [str(m) for m in r.wsgi_request._messages]
        self.assertTrue(any("NIET opgeslagen" in m for m in berichten), berichten)

    def test_publiceren_met_een_verouderd_scherm_wordt_geweigerd(self):
        self.concept_opslaan()
        self.als(self.bram)
        # Bram had het artikel geopend vóór de conceptversie bestond (geladen_concept leeg).
        r = self.post(beheerdata(self.a, inhoud="<p>Brams directe wijziging</p>", geladen_concept=""), _save="1")
        self.assertEqual(r.status_code, 200)
        self.assertIn("conceptversie van dit artikel", r.content.decode())
        self.a.refresh_from_db()
        self.assertEqual(self.a.inhoud, "<p>Oude tekst</p>")
        self.assertTrue(Conceptversie.objects.filter(artikel=self.a).exists())

    def test_weggooien(self):
        self.concept_opslaan()
        self.assertEqual(
            self.client.get(f"/beheer/kennisbank/artikel/{self.a.pk}/conceptversie/weggooien/").status_code, 405
        )
        r = self.client.post(f"/beheer/kennisbank/artikel/{self.a.pk}/conceptversie/weggooien/")
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Conceptversie.objects.filter(artikel=self.a).exists())
        self.assertNotIn("Medewerkers zien versie", self.client.get(self.url).content.decode())

    def test_bekijken_is_geschoond(self):
        # Opslaan schoont de tekst al; hier rechtstreeks een vervuilde conceptversie (zoals uit een oude
        # import of een fout elders), om de tweede verdediging in het voorbeeldscherm zelf te testen.
        Conceptversie.objects.create(
            artikel=self.a,
            velden={"titel": "x", "inhoud": '<p>Hallo</p><script>alert(1)</script><img src=x onerror="alert(2)">'},
        )
        r = self.als(self.anna).get(f"/beheer/kennisbank/artikel/{self.a.pk}/conceptversie/bekijken/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("Hallo", html)
        self.assertNotIn("alert(1)", html)
        self.assertNotIn("onerror", html)

    def test_opslaan_schoont_de_tekst(self):
        self.concept_opslaan(inhoud="<p>Hallo</p><script>alert(1)</script>")
        self.assertNotIn("script", Conceptversie.objects.get(artikel=self.a).velden["inhoud"])

    def test_redacteur_van_een_andere_omgeving_kan_er_niet_bij(self):
        self.concept_opslaan()
        self.als(self.zoe)
        self.assertEqual(
            self.client.get(f"/beheer/kennisbank/artikel/{self.a.pk}/conceptversie/bekijken/").status_code, 404
        )
        self.assertEqual(
            self.client.post(f"/beheer/kennisbank/artikel/{self.a.pk}/conceptversie/weggooien/").status_code, 404
        )
        self.assertTrue(Conceptversie.objects.filter(artikel=self.a).exists())

    def test_alleen_naast_een_gepubliceerde_versie(self):
        concept = Artikel.objects.create(
            omgeving=self.noord, titel="Nog nooit gepubliceerd", samenvatting="x", inhoud="<p>x</p>"
        )
        self.als(self.anna)
        r = self.client.get(f"/beheer/kennisbank/artikel/{concept.pk}/change/")
        self.assertNotIn("Opslaan als conceptversie", r.content.decode())
        # Toch de knop meesturen: dan is het een gewone opslag, geen conceptversie.
        data = beheerdata(concept, inhoud="<p>gewoon opgeslagen</p>", geladen_concept="")
        self.client.post(
            f"/beheer/kennisbank/artikel/{concept.pk}/change/",
            urlencode({**data, "_conceptversie": "1"}),
            content_type="application/x-www-form-urlencoded",
        )
        concept.refresh_from_db()
        self.assertEqual(concept.inhoud, "<p>gewoon opgeslagen</p>")
        self.assertFalse(Conceptversie.objects.exists())

    def test_kladversie_wordt_afgesloten_na_opslaan_als_conceptversie(self):
        diensten.klad_opslaan(self.anna, self.a, {"titel": "x"}, redactie_omgevingen={self.noord.pk})
        self.concept_opslaan()
        self.assertIsNotNone(Kladversie.objects.get(gebruiker=self.anna, artikel=self.a).afgesloten_op)

    def test_werkplek_toont_de_conceptversie(self):
        self.concept_opslaan(titel="Rappel versturen (nieuw)")
        r = self.als(self.anna).get("/beheer/?bak=concepten")
        self.assertEqual(
            [c["titel"] for c in r.context["werkplek"]["inhoud"]["conceptversies"]], ["Rappel versturen (nieuw)"]
        )
        menu = {b["sleutel"]: b["aantal"] for b in r.context["werkplek"]["menu"]["artikelkant"]}
        self.assertEqual(menu["concepten"], 2)  # deze conceptversie + het nooit gepubliceerde concept uit Basis
