"""Beveiligingstest: kan een gebruiker bij gegevens van een omgeving waar hij geen toegang toe heeft?

Dit is geen gewone functionele test maar een aanval op onze eigen lokale kopie. Het scenario is
vijandig opgezet: twee organisaties (Noord en Zuid) die niets met elkaar te maken hebben, een lezer
die is opgesloten in Noord, en een redacteur van Noord. Elke test probeert via een andere route bij
Zuid te komen. De verdediging hoort elke keer te winnen, met een 404 (niet 403) zodat het bestaan van
het artikel niet wordt verraden.

De omgevingsscheiding is het kroonjuweel: elke andere fout kost je een scherm, deze kost je de
werkinstructies van een andere afdeling. Vandaar een eigen bestand, zodat een toekomstige wijziging die
hier iets openzet onmiddellijk opvalt.
"""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.authtoken.models import Token

from kennisbank.models import Artikel, Omgeving, Rol, Status, Toegang, Verbetervoorstel

User = get_user_model()


class OmgevingsscheidingTests(TestCase):
    """Noord en Zuid delen niets. Een inwoner van Noord mag Zuid op geen enkele manier zien."""

    @classmethod
    def setUpTestData(cls):
        cls.noord = Omgeving.objects.create(slug="noord", naam="Regio Noord")
        cls.zuid = Omgeving.objects.create(slug="zuid", naam="Regio Zuid")

        g_noord_lezer = Group.objects.create(name="noord-lezers")
        g_noord_red = Group.objects.create(name="noord-redactie")
        g_zuid_lezer = Group.objects.create(name="zuid-lezers")
        Toegang.objects.create(omgeving=cls.noord, groep=g_noord_lezer, rol=Rol.LEZER)
        Toegang.objects.create(omgeving=cls.noord, groep=g_noord_red, rol=Rol.REDACTEUR)
        Toegang.objects.create(omgeving=cls.zuid, groep=g_zuid_lezer, rol=Rol.LEZER)

        cls.lezer_noord = User.objects.create_user("lezer_noord", password="x")
        cls.lezer_noord.groups.add(g_noord_lezer)
        cls.redacteur_noord = User.objects.create_user("redacteur_noord", password="x")
        cls.redacteur_noord.groups.add(g_noord_red)
        cls.lezer_zuid = User.objects.create_user("lezer_zuid", password="x")
        cls.lezer_zuid.groups.add(g_zuid_lezer)

        # Een gepubliceerd geheim in Zuid, en een concept in Zuid.
        cls.geheim_zuid = Artikel.objects.create(
            omgeving=cls.zuid, titel="Interne werkwijze Zuid", samenvatting="Geheim voor Noord", inhoud="<p>xx</p>",
            status=Status.GEPUBLICEERD, versie=1,
        )
        cls.concept_zuid = Artikel.objects.create(
            omgeving=cls.zuid, titel="Concept Zuid", samenvatting="Nog niet af", inhoud="<p>xx</p>",
            status=Status.CONCEPT,
        )
        cls.artikel_noord = Artikel.objects.create(
            omgeving=cls.noord, titel="Werkwijze Noord", samenvatting="Gewoon zichtbaar in Noord", inhoud="<p>xx</p>",
            status=Status.GEPUBLICEERD, versie=1,
        )

    def als(self, gebruiker):
        c = self.client
        c.force_login(gebruiker)
        return c

    # --- directe toegang op id -------------------------------------------------------

    def test_artikel_van_zuid_opvragen_op_id_geeft_404(self):
        r = self.als(self.lezer_noord).get(f"/api/v1/artikelen/{self.geheim_zuid.pk}")
        self.assertEqual(r.status_code, 404, "lezer van Noord kon een artikel van Zuid op id opvragen")

    def test_een_concept_van_zuid_opvragen_geeft_404(self):
        r = self.als(self.lezer_noord).get(f"/api/v1/artikelen/{self.concept_zuid.pk}")
        self.assertEqual(r.status_code, 404)

    def test_de_lijst_bevat_nooit_een_artikel_van_zuid(self):
        r = self.als(self.lezer_noord).get("/api/v1/artikelen")
        self.assertEqual(r.status_code, 200)
        ids = {a["id"] for a in r.json()["results"]} if "results" in r.json() else {a["id"] for a in r.json()}
        self.assertNotIn(self.geheim_zuid.pk, ids)
        self.assertIn(self.artikel_noord.pk, ids)

    def test_de_omgevingsfilter_dwingen_naar_zuid_levert_niets(self):
        """?omgeving=zuid mag niet ineens Zuid tonen aan iemand van Noord."""
        r = self.als(self.lezer_noord).get("/api/v1/artikelen?omgeving=zuid")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        rijen = data["results"] if "results" in data else data
        self.assertEqual(rijen, [])

    # --- zijdeuren die een id aannemen ------------------------------------------------

    def test_favoriet_maken_van_een_artikel_in_zuid_geeft_404(self):
        """Een leescontrole op de detailpagina helpt niet als 'markeer favoriet' het bestaan bevestigt."""
        r = self.als(self.lezer_noord).put(f"/api/v1/artikelen/{self.geheim_zuid.pk}/favoriet")
        self.assertEqual(r.status_code, 404)

    def test_weergave_tellen_van_een_artikel_in_zuid_geeft_404(self):
        r = self.als(self.lezer_noord).post(f"/api/v1/artikelen/{self.geheim_zuid.pk}/weergave")
        self.assertEqual(r.status_code, 404)

    # --- keuzelijsten en zoeken -------------------------------------------------------

    def test_keuzelijsten_lekken_geen_clusters_van_zuid(self):
        self.geheim_zuid.clusters.create(naam="Zuid-only cluster")
        r = self.als(self.lezer_noord).get("/api/v1/keuzelijsten")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Zuid-only cluster", json.dumps(r.json()))

    def test_zoeken_vindt_geen_artikel_van_zuid(self):
        # Zoeken loopt via /artikelen?q=, niet via een eigen /zoeken-pad.
        r = self.als(self.lezer_noord).get("/api/v1/artikelen?q=Zuid")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(self.geheim_zuid.pk, {a["id"] for a in r.json()})

    def test_zoeken_met_omgeving_zuid_forceren_lekt_niets(self):
        r = self.als(self.lezer_noord).get("/api/v1/artikelen?q=werkwijze&omgeving=zuid")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(self.geheim_zuid.pk, {a["id"] for a in r.json()})

    # --- verbetervoorstellen ----------------------------------------------------------

    def test_voorstel_indienen_op_een_artikel_van_zuid_wordt_geweigerd(self):
        """De serializer beperkt het artikelveld tot leesbare artikelen; Zuid hoort een 400 te geven."""
        r = self.als(self.lezer_noord).post(
            "/api/v1/voorstellen",
            data=json.dumps({"artikel": self.geheim_zuid.pk, "tekst": "Ik wil hier iets over zeggen", "citaat": "xx"}),
            content_type="application/json",
        )
        self.assertIn(r.status_code, (400, 404), r.content)
        self.assertFalse(
            Verbetervoorstel.objects.filter(artikel=self.geheim_zuid).exists(),
            "er is een voorstel aangemaakt op een artikel in een andere omgeving",
        )

    def test_redacteur_noord_ziet_geen_voorstel_van_zuid(self):
        """Er is geen losse GET op één voorstel; ze komen via de lijst. Die mag Zuid niet bevatten."""
        v = Verbetervoorstel.objects.create(
            artikel=self.geheim_zuid, artikel_versie=1, tekst="intern Zuid", ingediend_door=self.lezer_zuid,
        )
        from kennisbank.rechten import werk_staf_status_bij

        werk_staf_status_bij(self.redacteur_noord)
        r = self.als(self.redacteur_noord).get("/api/v1/voorstellen")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        rijen = data["results"] if isinstance(data, dict) and "results" in data else data
        self.assertNotIn(v.pk, {p["id"] for p in rijen}, "voorstel uit Zuid stond in de lijst van een Noord-redacteur")
        # En de berichten-deur op dat voorstel hoort dicht te zitten.
        b = self.als(self.redacteur_noord).post(
            f"/api/v1/voorstellen/{v.pk}/berichten",
            data=json.dumps({"tekst": "ingang via de achterdeur"}),
            content_type="application/json",
        )
        self.assertIn(b.status_code, (403, 404))
        self.assertEqual(v.berichten.count(), 0, "Noord-redacteur kon een bericht plaatsen op een voorstel uit Zuid")

    def test_redacteur_noord_kan_geen_status_zetten_op_een_voorstel_van_zuid(self):
        v = Verbetervoorstel.objects.create(
            artikel=self.geheim_zuid, artikel_versie=1, tekst="intern Zuid", ingediend_door=self.lezer_zuid,
        )
        from kennisbank.rechten import werk_staf_status_bij

        werk_staf_status_bij(self.redacteur_noord)
        r = self.als(self.redacteur_noord).patch(
            f"/api/v1/voorstellen/{v.pk}",
            data=json.dumps({"status": "afgewezen"}),
            content_type="application/json",
        )
        self.assertIn(r.status_code, (403, 404))
        v.refresh_from_db()
        self.assertEqual(v.status, "nieuw", "status van een voorstel uit Zuid is door Noord gewijzigd")

    # --- redacteur van Noord mag niet in Zuid schrijven -------------------------------

    def test_redacteur_noord_kan_geen_artikel_van_zuid_bewerken_via_beheer(self):
        from kennisbank.rechten import werk_staf_status_bij

        werk_staf_status_bij(self.redacteur_noord)
        r = self.als(self.redacteur_noord).get(f"/beheer/kennisbank/artikel/{self.geheim_zuid.pk}/change/")
        self.assertIn(r.status_code, (302, 403, 404), "redacteur van Noord kreeg het wijzigscherm van een Zuid-artikel")

    def test_redacteur_noord_kan_geen_versie_van_zuid_bekijken(self):
        from kennisbank.rechten import werk_staf_status_bij

        werk_staf_status_bij(self.redacteur_noord)
        r = self.als(self.redacteur_noord).get(
            f"/beheer/kennisbank/artikel/{self.geheim_zuid.pk}/versie/1/"
        )
        self.assertIn(r.status_code, (302, 403, 404))


class RechtenverhogingTests(TestCase):
    """Een gewone lezer mag het beheer niet in, en is_staff mag niet per ongeluk aanstaan."""

    @classmethod
    def setUpTestData(cls):
        cls.omg = Omgeving.objects.create(slug="noord", naam="Noord")
        g = Group.objects.create(name="lezers")
        Toegang.objects.create(omgeving=cls.omg, groep=g, rol=Rol.LEZER)
        cls.lezer = User.objects.create_user("gewone_lezer", password="x")
        cls.lezer.groups.add(g)

    def test_een_pure_lezer_is_geen_staf(self):
        from kennisbank.rechten import werk_staf_status_bij

        werk_staf_status_bij(self.lezer)
        self.lezer.refresh_from_db()
        self.assertFalse(self.lezer.is_staff, "een lezer zonder redacteurschap kreeg staf-toegang")

    def test_een_pure_lezer_komt_het_beheer_niet_in(self):
        self.client.force_login(self.lezer)
        r = self.client.get("/beheer/")
        self.assertIn(r.status_code, (302, 403), "een lezer kwam op de beheerstartpagina")
        r2 = self.client.get("/beheer/kennisbank/artikel/")
        self.assertIn(r2.status_code, (302, 403), "een lezer kon de artikelenlijst in het beheer openen")


class TokenScheidingTests(TestCase):
    """Een koppeling (zaaksysteem) met een token erft de rechten van zijn account, niet meer."""

    @classmethod
    def setUpTestData(cls):
        cls.noord = Omgeving.objects.create(slug="noord", naam="Noord")
        cls.zuid = Omgeving.objects.create(slug="zuid", naam="Zuid")
        g = Group.objects.create(name="noord-lezers")
        Toegang.objects.create(omgeving=cls.noord, groep=g, rol=Rol.LEZER)
        cls.koppeling = User.objects.create_user("zaaksysteem", password="x")
        cls.koppeling.groups.add(g)
        cls.token = Token.objects.create(user=cls.koppeling)
        cls.geheim_zuid = Artikel.objects.create(
            omgeving=cls.zuid, titel="Zuid intern", samenvatting="geheim", inhoud="<p>x</p>",
            status=Status.GEPUBLICEERD, versie=1,
        )

    def test_token_van_noord_komt_niet_bij_een_artikel_van_zuid(self):
        r = self.client.get(
            f"/api/v1/artikelen/{self.geheim_zuid.pk}",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )
        self.assertEqual(r.status_code, 404, "token van een Noord-account kon bij Zuid")

    def test_zonder_token_geen_toegang(self):
        r = self.client.get(f"/api/v1/artikelen/{self.geheim_zuid.pk}")
        self.assertIn(r.status_code, (401, 403))
