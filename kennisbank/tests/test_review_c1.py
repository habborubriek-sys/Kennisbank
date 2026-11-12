"""1.19.0: het reviewproces, stap C1 (bouwlijst `ronde3-reviewproces-bouwlijst.md`).

Opzet bovenop test_bakken.Basis: in Noord een Team Water (groep team-water, reviewer Wim, cluster Water)
en een Team Weg (reviewer Willem); in Zuid een team met reviewer Zara. Anna en Bram zijn redacteur.
"""

from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import override_settings

from kennisbank import diensten, review
from kennisbank.models import (
    Artikel,
    ArtikelVersie,
    Cluster,
    Conceptversie,
    Inzage,
    InzageStatus,
    Reviewteam,
    Status,
    VoorstelStatus,
)
from kennisbank.tests.test_bakken import Basis
from kennisbank.tests.test_kennisbank import beheerdata
from kennisbank.verschil import verschil_html, woordverschil

User = get_user_model()


class ReviewBasis(Basis):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.noord.reviewproces = True
        cls.noord.save()
        cls.water = Cluster.objects.create(naam="Water")
        cls.weg = Cluster.objects.create(naam="Weg")

        def reviewer(naam, groepnaam):
            g, _ = Group.objects.get_or_create(name=groepnaam)
            u = User.objects.create_user(naam, email=f"{naam}@example.org", password="x", first_name=naam.title())
            u.groups.add(g)
            return u, g

        cls.wim, g_water = reviewer("wim", "team-water")
        cls.willem, g_weg = reviewer("willem", "team-weg")
        cls.zara, g_zuid = reviewer("zara", "team-zuid")
        cls.team_water = Reviewteam.objects.create(naam="Team Water", omgeving=cls.noord, groep=g_water)
        cls.team_water.clusters.add(cls.water)
        cls.team_weg = Reviewteam.objects.create(naam="Team Weg", omgeving=cls.noord, groep=g_weg)
        cls.team_zuid = Reviewteam.objects.create(naam="Team Zuid", omgeving=cls.zuid, groep=g_zuid)

    def setUp(self):
        self.a = Artikel.objects.create(
            omgeving=self.noord,
            titel="Rappel versturen",
            samenvatting="Hoe je een rappel verstuurt, stap voor stap.",
            inhoud="<p>Stuur na twee weken een rappel.</p>",
            status=Status.GEPUBLICEERD,
        )
        self.a.clusters.add(self.water)
        diensten.herbouw_secties(self.a)
        diensten.registreer_publicatie(self.a, self.anna)
        self.a.refresh_from_db()
        self.url = f"/beheer/kennisbank/artikel/{self.a.pk}/change/"

    def post(self, pad, data, **knop):
        return self.client.post(
            pad, urlencode({**data, **knop}, doseq=True), content_type="application/x-www-form-urlencoded"
        )

    def maak_concept(self, wie=None, inhoud="<p>Stuur na drie weken een rappel.</p>"):
        self.client.force_login(wie or self.anna)
        data = beheerdata(self.a, inhoud=inhoud, wijzigingstoelichting="")
        data["geladen_concept"] = (
            Conceptversie.objects.filter(artikel=self.a).first().stempel
            if Conceptversie.objects.filter(artikel=self.a).exists()
            else ""
        )
        self.post(self.url, data, _conceptversie="1")
        return Conceptversie.objects.get(artikel=self.a)

    def ter_inzage(self, *teams, wie=None):
        c = Conceptversie.objects.get(artikel=self.a)
        self.client.force_login(wie or self.anna)
        return self.post(
            f"/beheer/kennisbank/artikel/{self.a.pk}/ter-inzage/",
            {"geladen_concept": c.stempel, "reviewteams": [t.pk for t in (teams or [self.team_water])]},
        )


class TerInzageTests(ReviewBasis):
    def test_team_van_het_cluster_staat_voorgevuld(self):
        self.maak_concept()
        html = self.client.get(self.url).content.decode()
        # Sinds 1.21.0 in het keuzevenster van Afronden (de gegevens staan als JSON in de pagina).
        self.assertIn(f'{{"pk": {self.team_water.pk}, "naam": "Team Water", "gekozen": true}}', html)
        self.assertIn(f'{{"pk": {self.team_weg.pk}, "naam": "Team Weg", "gekozen": false}}', html)
        self.assertNotIn("Team Zuid", html)

    def test_ter_inzage_zet_de_conceptversie_op_slot(self):
        c = self.maak_concept()
        r = self.ter_inzage()
        self.assertEqual(r.status_code, 302)
        self.assertTrue(review.op_slot(self.a.pk))
        self.assertIn('id="kb-op-slot"', self.client.get(self.url).content.decode())
        # Opslaan als conceptversie lukt niet meer.
        data = beheerdata(
            self.a, inhoud="<p>Toch nog iets anders</p>", wijzigingstoelichting="", geladen_concept=c.stempel
        )
        r = self.post(self.url, data, _conceptversie="1")
        self.assertEqual(
            Conceptversie.objects.get(artikel=self.a).velden["inhoud"], "<p>Stuur na drie weken een rappel.</p>"
        )
        self.assertIn("staat op slot", self.client.get(self.url).content.decode())

    def test_publiceren_kan_pas_na_terugroepen(self):
        # Besluit Alex 12 november (was: publiceren kan altijd).
        c = self.maak_concept()
        self.ter_inzage()
        data = beheerdata(self.a, inhoud="<p>Stiekem iets anders</p>", geladen_concept=c.stempel)
        r = self.post(self.url, data, _save="1")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Roep hem eerst terug", r.content.decode())
        self.a.refresh_from_db()
        self.assertEqual(self.a.versie, 1)
        self.assertTrue(review.op_slot(self.a.pk))
        # Na terugroepen kan het wel; de versiegeschiedenis noemt het team.
        self.post(f"/beheer/kennisbank/artikel/{self.a.pk}/terugroepen/", {})
        data = beheerdata(self.a, inhoud="<p>Stuur na drie weken een rappel.</p>", geladen_concept=c.stempel)
        r = self.post(self.url, data, _save="1")
        self.assertEqual(r.status_code, 302, r.content[:500])
        v = ArtikelVersie.objects.get(artikel=self.a, versie=2)
        self.assertEqual(v.review, "Gepubliceerd zonder akkoord van Team Water.")
        self.assertFalse(Inzage.objects.filter(artikel=self.a, afgesloten=False).exists())

    def test_zonder_conceptversie_of_met_een_oud_scherm_kan_het_niet(self):
        self.client.force_login(self.anna)
        r = self.post(
            f"/beheer/kennisbank/artikel/{self.a.pk}/ter-inzage/",
            {"geladen_concept": "", "reviewteams": [self.team_water.pk]},
        )
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Inzage.objects.exists())
        c = self.maak_concept()
        r = self.post(
            f"/beheer/kennisbank/artikel/{self.a.pk}/ter-inzage/",
            {"geladen_concept": "oud", "reviewteams": [self.team_water.pk]},
        )
        self.assertFalse(Inzage.objects.exists())
        self.assertTrue(c)

    def test_team_van_een_andere_omgeving_telt_niet(self):
        self.maak_concept()
        self.ter_inzage(self.team_zuid)
        self.assertFalse(Inzage.objects.exists())

    def test_niet_twee_keer_ter_inzage(self):
        self.maak_concept()
        self.ter_inzage()
        self.ter_inzage(self.team_weg)
        self.assertEqual(list(Inzage.objects.values_list("team__naam", flat=True)), ["Team Water"])

    def test_dienst_weigert_een_team_van_een_andere_omgeving(self):
        c = self.maak_concept()
        with self.assertRaises(review.ReviewFout):
            review.ter_inzage_geven(self.a, self.anna, [self.team_zuid], c.stempel)

    def test_reviewproces_uit(self):
        self.noord.reviewproces = False
        self.noord.save()
        self.maak_concept()
        self.assertNotIn("Ter inzage geven", self.client.get(self.url).content.decode())
        self.ter_inzage()
        self.assertFalse(Inzage.objects.exists())

    def test_terugroepen(self):
        self.maak_concept()
        self.ter_inzage()
        self.post(f"/beheer/kennisbank/artikel/{self.a.pk}/terugroepen/", {})
        self.assertFalse(review.op_slot(self.a.pk))
        i = Inzage.objects.get()
        self.assertEqual(i.status, InzageStatus.TERUGGEROEPEN)
        # De reviewer kan er niets meer mee.
        self.client.force_login(self.wim)
        self.client.post(f"/review/{i.pk}/", {"actie": "akkoord"})
        i.refresh_from_db()
        self.assertEqual(i.status, InzageStatus.TERUGGEROEPEN)

    def test_weggooien_kan_pas_na_terugroepen_en_sluit_de_review_af(self):
        self.maak_concept()
        self.ter_inzage()
        weg = f"/beheer/kennisbank/artikel/{self.a.pk}/conceptversie/weggooien/"
        self.post(weg, {})
        self.assertTrue(Conceptversie.objects.filter(artikel=self.a).exists())
        self.assertTrue(review.op_slot(self.a.pk))
        self.post(f"/beheer/kennisbank/artikel/{self.a.pk}/terugroepen/", {})
        self.post(weg, {})
        self.assertFalse(Conceptversie.objects.filter(artikel=self.a).exists())
        self.assertFalse(Inzage.objects.filter(afgesloten=False).exists())
        # De reviewer krijgt een nette melding in plaats van "pagina niet gevonden".
        self.client.force_login(self.wim)
        r = self.client.get(f"/review/{Inzage.objects.get().pk}/")
        self.assertEqual(r.status_code, 302)

    def test_werkplek_bak_ter_inzage(self):
        self.maak_concept()
        self.ter_inzage()
        html = self.client.get("/beheer/?bak=ter_inzage").content.decode()
        self.assertIn("Rappel versturen", html)
        self.assertIn("Team Water: ter inzage", html)


class ReviewerTests(ReviewBasis):
    def setUp(self):
        super().setUp()
        self.maak_concept()
        self.ter_inzage()
        self.i = Inzage.objects.get()

    def test_lijst_en_statusbalk(self):
        html = self.als(self.wim).get("/review/").content.decode()
        self.assertIn("Rappel versturen", html)
        self.assertIn("<b>1</b> ter inzage", html)
        self.assertIn("<b>1</b> nog niet opgepakt", html)

    def test_alleen_het_eigen_team(self):
        self.assertNotIn("Rappel versturen", self.als(self.willem).get("/review/").content.decode())
        self.assertEqual(self.client.get(f"/review/{self.i.pk}/").status_code, 404)
        self.assertEqual(self.als(self.zara).get(f"/review/{self.i.pk}/").status_code, 404)
        self.assertEqual(self.client.post(f"/review/{self.i.pk}/", {"actie": "akkoord"}).status_code, 404)
        self.assertIn("geen reviewteam", self.als(self.lies).get("/review/").content.decode())

    def test_niet_ingelogd(self):
        self.client.logout()
        self.assertEqual(self.client.get("/review/").status_code, 302)

    def test_wijzigingen_gemarkeerd(self):
        html = self.als(self.wim).get(f"/review/{self.i.pk}/").content.decode()
        self.assertIn("<del>twee</del><ins>drie</ins>", html)

    def test_oppakken_en_opmerking(self):
        self.als(self.wim).post(f"/review/{self.i.pk}/", {"actie": "oppakken"})
        self.i.refresh_from_db()
        self.assertEqual(self.i.reviewer, self.wim)
        self.client.post(f"/review/{self.i.pk}/", {"actie": "opmerking", "tekst": "Drie weken klopt niet."})
        self.assertEqual(list(self.i.opmerkingen.values_list("tekst", flat=True)), ["Drie weken klopt niet."])
        self.assertIn("bij Wim", self.als(self.anna).get("/beheer/?bak=ter_inzage").content.decode())

    @override_settings(KB_EMAIL_AAN=True)
    def test_teruggeven_alleen_met_opmerking_en_dan_weer_open_voor_de_redactie(self):
        self.als(self.wim).post(f"/review/{self.i.pk}/", {"actie": "teruggeven", "tekst": ""})
        self.i.refresh_from_db()
        self.assertEqual(self.i.status, InzageStatus.TER_INZAGE)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/review/{self.i.pk}/", {"actie": "teruggeven", "tekst": "Het zijn zes weken."})
        self.i.refresh_from_db()
        self.assertEqual(self.i.status, InzageStatus.TERUGGEGEVEN)
        self.assertFalse(review.op_slot(self.a.pk))
        self.assertEqual([m.to for m in mail.outbox], [["anna@example.org"]])
        html = self.als(self.anna).get(self.url).content.decode()
        self.assertIn("Het zijn zes weken.", html)
        self.assertIn("teruggegeven", html)

    def test_akkoord_geeft_het_label_en_dat_vervalt_bij_een_wijziging(self):
        self.als(self.wim).post(f"/review/{self.i.pk}/", {"actie": "akkoord"})
        html = self.als(self.anna).get(self.url).content.decode()
        self.assertIn("Versie 2 akkoord bevonden door Team Water", html)
        self.maak_concept(inhoud="<p>Stuur na vier weken een rappel.</p>")
        html = self.client.get(self.url).content.decode()
        self.assertNotIn("akkoord bevonden door", html)
        self.assertIn("akkoord vervallen", html)

    def test_publiceren_na_akkoord_staat_in_de_versiegeschiedenis(self):
        self.als(self.wim).post(f"/review/{self.i.pk}/", {"actie": "akkoord"})
        c = Conceptversie.objects.get(artikel=self.a)
        self.client.force_login(self.anna)
        self.post(self.url, beheerdata(self.a, inhoud=c.velden["inhoud"], geladen_concept=c.stempel), _save="1")
        self.assertEqual(ArtikelVersie.objects.get(artikel=self.a, versie=2).review, "Akkoord van Team Water.")


class MeerdereTeamsTests(ReviewBasis):
    def test_label_pas_als_alle_teams_akkoord_zijn(self):
        self.maak_concept()
        self.ter_inzage(self.team_water, self.team_weg)
        water = Inzage.objects.get(team=self.team_water)
        weg = Inzage.objects.get(team=self.team_weg)
        self.als(self.wim).post(f"/review/{water.pk}/", {"actie": "akkoord"})
        self.assertTrue(review.op_slot(self.a.pk), "Team Weg is nog bezig")
        self.assertIsNone(review.stand(self.a)["label"])
        self.als(self.willem).post(f"/review/{weg.pk}/", {"actie": "akkoord"})
        self.assertIn("Team Water, Team Weg", review.stand(self.a)["label"])

    def test_nieuwe_ronde_na_teruggeven(self):
        self.maak_concept()
        self.ter_inzage()
        eerste = Inzage.objects.get()
        self.als(self.wim).post(f"/review/{eerste.pk}/", {"actie": "teruggeven", "tekst": "Zes weken."})
        self.maak_concept(inhoud="<p>Stuur na zes weken een rappel.</p>")
        self.ter_inzage()
        tweede = Inzage.objects.exclude(pk=eerste.pk).get()
        self.assertEqual(tweede.ronde, 2)
        s = review.stand(self.a)
        self.assertEqual([r.pk for r in s["rijen"]], [tweede.pk])
        self.assertEqual([r.pk for r in s["eerder"]], [eerste.pk])


class BeheerEnMailTests(ReviewBasis):
    def test_reviewteams_alleen_voor_een_beheerder(self):
        self.assertEqual(self.als(self.anna).get("/beheer/kennisbank/reviewteam/").status_code, 403)
        beheerder = User.objects.create_superuser("bea", "bea@example.org", "x")
        self.assertEqual(self.als(beheerder).get("/beheer/kennisbank/reviewteam/").status_code, 200)

    @override_settings(KB_EMAIL_AAN=True)
    def test_dagelijkse_samenvatting_voor_reviewers(self):
        self.maak_concept()
        self.ter_inzage()
        mail.outbox.clear()
        self.assertEqual(review.verstuur_reviewmail(), 1)
        self.assertEqual(mail.outbox[0].to, ["wim@example.org"])
        self.assertIn("Rappel versturen", mail.outbox[0].body)
        self.assertEqual(review.verstuur_reviewmail(), 0, "niet nog een keer")

    def test_ik_zegt_of_je_reviewer_bent(self):
        self.assertTrue(self.als(self.wim).get("/api/v1/ik").json()["is_reviewer"])
        self.assertFalse(self.als(self.anna).get("/api/v1/ik").json()["is_reviewer"])

    def test_linkerkolom_op_het_behandelscherm_wijst_naar_de_werkplek(self):
        # Sinds 1.26.0 bestaat het scherm alleen nog voor afgehandelde voorstellen (alleen-lezen).
        v = self.voorstel()
        diensten.voorstel_afhandelen(v, self.anna, VoorstelStatus.AFGEWEZEN, "Niet nodig.")
        html = self.als(self.anna).get(f"/beheer/voorstel/{v.pk}/").content.decode()
        self.assertIn('href="/beheer/?bak=afgehandeld"', html)
        self.assertNotIn('href="?bak=', html)


class VerschilTests(Basis):
    def test_woorden_en_escapen(self):
        self.assertEqual(woordverschil("a <b> c", "a <b> d"), "a &lt;b&gt; <del>c</del><ins>d</ins>")

    def test_blokken_erbij_en_eraf(self):
        html, n = verschil_html("<p>een</p><p>twee</p>", "<p>een</p><h2>Nieuw</h2><p>twee</p>")
        self.assertEqual(n, 1)
        self.assertIn('<h2 class="vs-nieuw"><ins>Nieuw</ins></h2>', html)
        html, n = verschil_html("<p>een</p><p>twee</p>", "<p>een</p>")
        self.assertIn("<del>twee</del>", html)

    def test_geen_html_uit_het_artikel(self):
        html, _ = verschil_html("", "<p>&lt;script&gt;x&lt;/script&gt;</p>")
        self.assertNotIn("<script>", html)
