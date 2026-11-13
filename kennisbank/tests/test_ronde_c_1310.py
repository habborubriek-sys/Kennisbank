"""1.31.0, ronde C: schermen en teksten (bouwlijst `bouwlijst-1.30.0-reviewpagina-en-ronde-c.md`, deel 1.31.0).

De opmaak (smalle schermen, de lade naast de marge, vensters) is in de browser nagelopen. Hier wat de server
meegeeft en de teksten.
"""

from django.contrib import messages
from django.test import RequestFactory, SimpleTestCase

from kennisbank import diensten
from kennisbank.berichten import Berichten, herschrijf
from kennisbank.models import ArtikelVersie, Verbetervoorstel
from kennisbank.tests.test_voorstellen_lade_1260 import LadeBasis


class Meldingen(SimpleTestCase):
    """R3 B13: de standaardzinnen van Django in de toon van de kennisbank."""

    def test_het_artikel_en_je(self):
        self.assertEqual(
            herschrijf("De artikel ‘Rappel’ is met succes toegevoegd. U kunt deze hieronder weer bewerken."),
            "Het artikel “Rappel” is toegevoegd.",
        )
        self.assertEqual(
            herschrijf("De nieuwsbericht ‘X’ is met succes gewijzigd. U kunt deze hieronder nogmaals bewerken."),
            "Het nieuwsbericht “X” is opgeslagen.",
        )
        self.assertEqual(herschrijf("De tag ‘brug’ is met succes gewijzigd."), "De tag “brug” is opgeslagen.")
        self.assertEqual(
            herschrijf("De cluster ‘Nat’ is met succes toegevoegd. U kunt hieronder nog een cluster toevoegen."),
            "Het cluster “Nat” is toegevoegd. Je kunt hieronder nog een cluster toevoegen.",
        )

    def test_eigen_meldingen_blijven_zoals_ze_zijn(self):
        self.assertEqual(herschrijf("Conceptversie opgeslagen."), "Conceptversie opgeslagen.")

    def test_link_blijft_veilig(self):
        from django.utils.html import format_html
        from django.utils.safestring import SafeData

        verzoek = RequestFactory().get("/")
        verzoek.session = {}
        opslag = Berichten(verzoek)
        link = format_html('<a href="/x">{}</a>', "R")
        opslag.add(messages.SUCCESS, format_html("De artikel ‘{}’ is met succes gewijzigd.", link))
        m = list(opslag._queued_messages)[0]
        self.assertIsInstance(m.message, SafeData)
        self.assertEqual(m.message, 'Het artikel “<a href="/x">R</a>” is opgeslagen.')


class Werkbak(LadeBasis):
    def test_b14_terug_naar_de_bak_waar_je_was(self):
        self.client.force_login(self.anna)
        bak = f"cluster-{self.water.pk}"
        self.client.get(f"/beheer/?bak={bak}")
        html = self.client.get("/beheer/").content.decode()
        self.assertIn(f'href="/beheer/?bak={bak}" aria-current="page"', html)

    def test_b14_verdwenen_bak_valt_terug(self):
        self.client.force_login(self.anna)
        sessie = self.client.session
        sessie["kb_werkplek_bak"] = "cluster-999999"
        sessie.save()
        r = self.client.get("/beheer/")
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(self.client.session.get("kb_werkplek_bak"), "cluster-999999")

    def test_b14_zoeken_in_een_open_bak(self):
        self.voorstel(tekst="Termijn klopt niet.")
        self.voorstel(tekst="Telefoonnummer ontbreekt.")
        self.client.force_login(self.anna)
        html = self.client.get(f"/beheer/?bak=cluster-{self.water.pk}&q=telefoon").content.decode()
        self.assertIn("Telefoonnummer ontbreekt", html)
        self.assertNotIn("Termijn klopt niet", html)
        self.assertIn("Zoeken in deze bak", html)
        self.assertIn(">Bij wie</th>", html)


class Schermen(LadeBasis):
    def test_m15_geen_zijmenu_van_django(self):
        html = self.als(self.anna).get("/beheer/kennisbank/artikel/").content.decode()
        self.assertNotIn('id="nav-sidebar"', html)
        self.assertIn("<h1>Artikelen</h1>", html)
        self.assertIn(">Nieuw artikel</a>", html)
        self.assertNotIn("artikel toevoegen", html)

    def test_m15_afhandelscherm_in_de_nieuwe_stijl(self):
        v = self.voorstel()
        Verbetervoorstel.objects.filter(pk=v.pk).update(verwerkt_in_versie=1)
        url = f"/beheer/kennisbank/artikel/{self.a.pk}/voorstellen-afhandelen/"
        html = self.als(self.anna).get(url).content.decode()
        self.assertIn("← Werkplek", html)
        self.assertNotIn('class="breadcrumbs"', html)
        self.assertEqual(html.count("<h1"), 1)

    def test_m15_geschiedenis_met_naam_en_zonder_kruisje(self):
        ArtikelVersie.objects.filter(artikel=self.a).update(kleine_correctie=False)
        html = self.als(self.anna).get(self.url).content.decode()
        self.assertIn(diensten.naam_van(self.anna), html)
        self.assertNotIn("icon-no.svg", html)

    def test_b12_geen_confirm_van_de_browser(self):
        from kennisbank import review

        self.maak_concept()
        self.ter_inzage()
        self.assertTrue(review.op_slot(self.a.pk))
        html = self.als(self.anna).get(self.url).content.decode()
        self.assertNotIn("confirm(", html)
        self.assertIn('data-kb-vraag-titel="Terugroepen?"', html)
