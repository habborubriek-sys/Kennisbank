"""1.30.0: de reviewpagina gelijk aan de editor, en M16 (bouwlijst `bouwlijst-1.30.0-reviewpagina-en-ronde-c.md`).

Het gedrag in de browser (marge, selectie, vensters) is nagelopen met Playwright en axe. Hier: wie mag wat, wat de
server meegeeft, en de verschilweergave.
"""

from django.contrib.auth.models import Group
from django.utils import timezone

from kennisbank import review
from kennisbank.models import Inzage, InzageStatus, ReviewOpmerking, Verbetervoorstel
from kennisbank.tests.test_review_c1 import ReviewBasis, User
from kennisbank.verschil import verschil_html


class Basis1300(ReviewBasis):
    def setUp(self):
        super().setUp()
        self.maak_concept()
        self.ter_inzage()
        self.i = Inzage.objects.get(artikel=self.a)
        self.stuk = f"/review/{self.i.pk}/"

    def oppakken(self, wie):
        self.client.force_login(wie)
        return self.client.post(self.stuk, {"actie": "oppakken", "geladen_reviewer": str(self.i.reviewer_id or "")})

    def doe(self, wie, **data):
        self.client.force_login(wie)
        return self.client.post(self.stuk, data)

    def collega(self):
        u = User.objects.create_user("wanda", email="wanda@example.org", password="x", first_name="Wanda")
        u.groups.add(Group.objects.get(name="team-water"))
        return u


class EigenOpmerking(Basis1300):
    """M16, besluit Alex: je eigen opmerking wijzigen of weghalen, zolang het stuk in deze ronde ter inzage ligt."""

    def test_wijzigen_zet_bewerkt(self):
        self.oppakken(self.wim)
        o = review.opmerking_toevoegen(self.i, self.wim, "Zes weken?", "drie weken")
        r = self.doe(self.wim, actie="opmerking_wijzigen", opmerking=o.pk, tekst="Vier weken?")
        self.assertEqual(r.status_code, 302)
        o.refresh_from_db()
        self.assertEqual(o.tekst, "Vier weken?")
        self.assertEqual(o.citaat, "drie weken", "het citaat blijft")
        self.assertIsNotNone(o.bewerkt_op)
        html = self.client.get(self.stuk).content.decode()
        self.assertIn("· bewerkt", html)

    def test_zelfde_tekst_is_niet_bewerkt(self):
        self.oppakken(self.wim)
        o = review.opmerking_toevoegen(self.i, self.wim, "Zes weken?")
        self.doe(self.wim, actie="opmerking_wijzigen", opmerking=o.pk, tekst="  Zes weken?  ")
        o.refresh_from_db()
        self.assertIsNone(o.bewerkt_op)

    def test_leeg_maken_kan_niet(self):
        self.oppakken(self.wim)
        o = review.opmerking_toevoegen(self.i, self.wim, "Zes weken?")
        self.doe(self.wim, actie="opmerking_wijzigen", opmerking=o.pk, tekst="   ")
        o.refresh_from_db()
        self.assertEqual(o.tekst, "Zes weken?")

    def test_weghalen(self):
        self.oppakken(self.wim)
        o = review.opmerking_toevoegen(self.i, self.wim, "Zes weken?")
        self.doe(self.wim, actie="opmerking_weghalen", opmerking=o.pk)
        self.assertFalse(ReviewOpmerking.objects.filter(pk=o.pk).exists())

    def test_niet_van_een_ander(self):
        wanda = self.collega()
        self.oppakken(wanda)
        o = review.opmerking_toevoegen(self.i, wanda, "Van Wanda.")
        self.oppakken(self.wim)  # Wim neemt het stuk over
        self.doe(self.wim, actie="opmerking_wijzigen", opmerking=o.pk, tekst="Overschreven")
        self.doe(self.wim, actie="opmerking_weghalen", opmerking=o.pk)
        o.refresh_from_db()
        self.assertEqual(o.tekst, "Van Wanda.")

    def test_niet_van_een_andere_inzage(self):
        """Een opmerking-id van een ander stuk wordt niet gevonden, ook niet als het je eigen opmerking is."""
        self.oppakken(self.wim)
        o = review.opmerking_toevoegen(self.i, self.wim, "Hier.")
        review.teruggeven(self.i, self.wim)
        self.maak_concept(inhoud="<p>Stuur na vier weken een rappel.</p>")
        self.ter_inzage()
        nieuw = Inzage.objects.filter(artikel=self.a, status=InzageStatus.TER_INZAGE).get()
        with self.assertRaises(review.ReviewFout):
            review.opmerking_weghalen(nieuw, self.wim, o.pk)
        self.assertTrue(ReviewOpmerking.objects.filter(pk=o.pk).exists())

    def test_niet_meer_na_afronden(self):
        self.oppakken(self.wim)
        o = review.opmerking_toevoegen(self.i, self.wim, "Zes weken?")
        review.teruggeven(self.i, self.wim)
        with self.assertRaises(review.ReviewFout):
            review.opmerking_wijzigen(self.i, self.wim, o.pk, "Later")
        with self.assertRaises(review.ReviewFout):
            review.opmerking_weghalen(self.i, self.wim, o.pk)
        o.refresh_from_db()
        self.assertEqual(o.tekst, "Zes weken?")

    def test_niet_na_terugroepen(self):
        self.oppakken(self.wim)
        o = review.opmerking_toevoegen(self.i, self.wim, "Zes weken?")
        review.terugroepen(self.a, self.anna)
        r = self.doe(self.wim, actie="opmerking_weghalen", opmerking=o.pk)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(ReviewOpmerking.objects.filter(pk=o.pk).exists())

    def test_onzin_id(self):
        self.oppakken(self.wim)
        r = self.doe(self.wim, actie="opmerking_weghalen", opmerking="abc")
        self.assertEqual(r.status_code, 302)

    def test_knoppen_alleen_bij_eigen_opmerking(self):
        wanda = self.collega()
        review.opmerking_toevoegen(self.i, wanda, "Van Wanda.")
        self.oppakken(self.wim)
        mijn = review.opmerking_toevoegen(self.i, self.wim, "Van Wim.")
        html = self.client.get(self.stuk).content.decode()
        self.assertEqual(html.count('value="opmerking_weghalen"'), 1)
        self.assertIn(f'<input type="hidden" name="opmerking" value="{mijn.pk}">', html)

    def test_geen_knoppen_als_het_stuk_bij_een_ander_ligt(self):
        self.oppakken(self.wim)
        review.opmerking_toevoegen(self.i, self.wim, "Van Wim.")
        self.oppakken(self.collega())
        self.client.force_login(self.wim)
        html = self.client.get(self.stuk).content.decode()
        self.assertNotIn('value="opmerking_weghalen"', html)
        self.assertNotIn('id="rv-nieuw"', html)
        self.assertIn(">Overnemen</button>", html)


class Pagina(Basis1300):
    def test_voor_oppakken_alleen_lezen(self):
        self.client.force_login(self.wim)
        html = self.client.get(self.stuk).content.decode()
        self.assertIn(">Oppakken</button>", html)
        self.assertIn('class="rv-alleen-lezen"', html)
        self.assertNotIn('id="rv-nieuw"', html)
        self.assertNotIn('id="rv-afronden"', html)

    def test_na_oppakken_balk_marge_en_vensters(self):
        self.oppakken(self.wim)
        html = self.client.get(self.stuk).content.decode()
        self.assertIn('class="rv-balk"', html)
        self.assertIn('id="rv-afronden-knop"', html)
        self.assertIn('id="rv-wijz-knop" aria-pressed="true"', html)
        self.assertIn('id="rv-nieuw"', html)
        self.assertIn('<dialog class="rv-venster-laag" id="rv-afronden"', html)
        self.assertIn('<dialog class="rv-venster-laag" id="rv-weg"', html)
        # Zonder JavaScript blijven de knoppen gewoon bruikbaar.
        self.assertIn('id="rv-afronden-zonderjs"', html)
        self.assertNotIn("Toon de nieuwe tekst zoals medewerkers hem straks zien", html)

    def test_afronden_via_het_venster_met_laatste_opmerking(self):
        self.oppakken(self.wim)
        self.doe(self.wim, actie="teruggeven", tekst="Termijn klopt niet.", citaat="drie weken")
        self.i.refresh_from_db()
        self.assertEqual(self.i.status, InzageStatus.TERUGGEGEVEN)
        self.assertEqual(list(self.i.opmerkingen.values_list("citaat", flat=True)), ["drie weken"])

    def test_voorstellen_genummerd_zonder_naam(self):
        Verbetervoorstel.objects.create(
            artikel=self.a,
            artikel_versie=1,
            tekst="Twee is te kort.",
            citaat="twee weken",
            ingediend_door=self.lies,
            in_conceptversie=True,
        )
        self.oppakken(self.wim)
        html = self.client.get(self.stuk).content.decode()
        self.assertIn('id="rv-vs-1" data-nr="1" data-citaat="twee weken"', html)
        self.assertIn('<span class="rv-vs-nr" aria-hidden="true">1</span>', html)
        self.assertNotIn("Lies", html)

    def test_voorbeeld_voor_de_reviewer(self):
        self.client.force_login(self.wim)
        r = self.client.get(f"{self.stuk}voorbeeld/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("drie weken", r.content.decode())
        self.client.force_login(self.zara)  # ander team, andere omgeving
        self.assertEqual(self.client.get(f"{self.stuk}voorbeeld/").status_code, 404)
        review.terugroepen(self.a, self.anna)
        self.client.force_login(self.wim)
        self.assertEqual(self.client.get(f"{self.stuk}voorbeeld/").status_code, 404)

    def test_eerdere_rondes_met_stand_van_de_tekst(self):
        self.oppakken(self.wim)
        review.opmerking_toevoegen(self.i, self.wim, "Is drie goed?", "drie weken")
        review.opmerking_toevoegen(self.i, self.wim, "En de aanhef?", "Stuur na")
        review.opmerking_toevoegen(self.i, self.wim, "Algemeen goed.")
        review.teruggeven(self.i, self.wim)
        self.maak_concept(inhoud="<p>Stuur na vier weken een rappel.</p>")
        self.ter_inzage()
        nieuw = Inzage.objects.filter(artikel=self.a, status=InzageStatus.TER_INZAGE).get()
        self.client.force_login(self.wim)
        html = self.client.get(f"/review/{nieuw.pk}/").content.decode()
        self.assertIn("Eerdere rondes (1)", html)
        a = html.index("Is drie goed?")
        self.assertIn("tekst is aangepast", html[a - 300 : a])
        b = html.index("En de aanhef?")
        self.assertIn("staat er nog hetzelfde", html[b - 300 : b])
        c = html.index("Algemeen goed.")
        self.assertIn(">algemeen<", html[c - 200 : c])


class Lijst(Basis1300):
    def test_wat_bij_jou_ligt_staat_bovenaan(self):
        from kennisbank import diensten
        from kennisbank.models import Artikel, Status

        b = Artikel.objects.create(
            omgeving=self.noord,
            titel="Tweede stuk",
            samenvatting="Nog een stuk.",
            inhoud="<p>x</p>",
            status=Status.GEPUBLICEERD,
        )
        b.clusters.add(self.water)
        diensten.herbouw_secties(b)
        diensten.registreer_publicatie(b, self.anna)
        b.refresh_from_db()
        self.a = b
        self.url = f"/beheer/kennisbank/artikel/{b.pk}/change/"
        self.maak_concept(inhoud="<p>y</p>")
        self.ter_inzage()
        tweede = Inzage.objects.get(artikel=b)
        Inzage.objects.filter(pk=tweede.pk).update(gestart_op=timezone.now() + timezone.timedelta(minutes=5))
        self.client.force_login(self.wim)
        self.client.post(f"/review/{tweede.pk}/", {"actie": "oppakken", "geladen_reviewer": ""})
        html = self.client.get("/review/").content.decode()
        self.assertLess(html.index(">Tweede stuk</a>"), html.index(">Rappel versturen</a>"))


class Verschilweergave(Basis1300):
    def test_genummerde_lijst_houdt_nummers(self):
        html, _ = verschil_html("<ol><li>een</li><li>twee</li></ol>", "<ol><li>een</li><li>twee</li><li>drie</li></ol>")
        self.assertIn('<p class="vs-li vs-ol" data-nr="2">twee</p>', html)
        self.assertIn('<p class="vs-li vs-ol vs-nieuw" data-nr="3"><ins>drie</ins></p>', html)

    def test_opsomming_in_genummerde_lijst(self):
        html, _ = verschil_html("", "<ol><li>een<ul><li>sub</li></ul></li><li>twee</li></ol>")
        self.assertIn('data-nr="1"><ins>een</ins>', html)
        self.assertIn('<p class="vs-li vs-nieuw"><ins>sub</ins></p>', html)
        self.assertIn('data-nr="2"><ins>twee</ins>', html)

    def test_onboarding_herkenbaar(self):
        html, _ = verschil_html("", '<div class="onboarding"><p>Voor nieuwe collega\'s</p></div><p>daarna</p>')
        self.assertIn('<p class="vs-nieuw vs-onb"><ins>Voor nieuwe collega&#x27;s</ins></p>', html)
        self.assertIn('<p class="vs-nieuw"><ins>daarna</ins></p>', html)

    def test_geen_html_uit_het_artikel(self):
        html, _ = verschil_html("", '<ol><li onclick="x()">a<script>b</script></li></ol>')
        self.assertNotIn("onclick", html)
        self.assertNotIn("<script", html)
