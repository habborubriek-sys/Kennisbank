"""1.31.1: opmerkingen plaatsen, wijzigen en weghalen zonder de pagina te herladen (bouwlijst 1.31.1)."""

from kennisbank import review
from kennisbank.models import ReviewOpmerking
from kennisbank.tests.test_reviewpagina_1300 import Basis1300


class Snel(Basis1300):
    def snel(self, **data):
        self.client.force_login(self.wim)
        return self.client.post(self.stuk, data, headers={"X-Kb-Snel": "1"})

    def test_plaatsen_geeft_de_kaartjes_terug(self):
        self.oppakken(self.wim)
        r = self.snel(actie="opmerking", tekst="Zes weken?", citaat="drie weken")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["aantal"], 1)
        self.assertIn('id="rv-kaarten"', d["kaarten"])
        self.assertIn('data-citaat="drie weken"', d["kaarten"])
        self.assertIn("Zes weken?", d["kaarten"])
        self.assertIn('value="opmerking_weghalen"', d["kaarten"], "je eigen opmerking: met Wijzigen en Weghalen")
        # Geen melding die later nog eens op een andere pagina opduikt.
        html = self.client.get(self.stuk).content.decode()
        self.assertNotIn("Opmerking geplaatst", html)

    def test_wijzigen_en_weghalen(self):
        self.oppakken(self.wim)
        o = review.opmerking_toevoegen(self.i, self.wim, "Zes weken?")
        d = self.snel(actie="opmerking_wijzigen", opmerking=o.pk, tekst="Vier weken?").json()
        self.assertTrue(d["ok"])
        self.assertIn("Vier weken?", d["kaarten"])
        self.assertIn("· bewerkt", d["kaarten"])
        d = self.snel(actie="opmerking_weghalen", opmerking=o.pk).json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["aantal"], 0)
        self.assertFalse(ReviewOpmerking.objects.filter(pk=o.pk).exists())

    def test_fout_blijft_op_de_pagina(self):
        self.oppakken(self.wim)
        o = review.opmerking_toevoegen(self.i, self.wim, "Zes weken?")
        d = self.snel(actie="opmerking_wijzigen", opmerking=o.pk, tekst="  ").json()
        self.assertFalse(d["ok"])
        self.assertIn("leeg", d["melding"])

    def test_teruggeroepen(self):
        self.oppakken(self.wim)
        review.terugroepen(self.a, self.anna)
        r = self.snel(actie="opmerking", tekst="Nog even dit.")
        self.assertEqual(r.status_code, 409)
        self.assertFalse(r.json()["ok"])
        self.assertIn("tekst staat nog in het vak", r.json()["melding"])
        self.assertFalse(ReviewOpmerking.objects.filter(tekst="Nog even dit.").exists())

    def test_niet_van_een_ander_ook_niet_snel(self):
        self.oppakken(self.wim)
        o = review.opmerking_toevoegen(self.i, self.anna, "Van Anna.")
        d = self.snel(actie="opmerking_weghalen", opmerking=o.pk).json()
        self.assertFalse(d["ok"])
        self.assertTrue(ReviewOpmerking.objects.filter(pk=o.pk).exists())

    def test_teruggeven_gaat_nooit_snel(self):
        """Afronden laadt altijd een nieuwe pagina (de lijst); de kop verandert daar niets aan."""
        self.oppakken(self.wim)
        r = self.snel(actie="teruggeven", tekst="Graag aanpassen.")
        self.assertEqual(r.status_code, 302)

    def test_geen_voorbeeldtekst_in_het_vak(self):
        self.oppakken(self.wim)
        html = self.client.get(self.stuk).content.decode()
        self.assertNotIn("Bijvoorbeeld: hier klopt", html)
        self.assertIn('id="rv-live"', html)
