"""1.20.0: stap C2 (voorstel meenemen, afhandelen na publiceren, spoedcorrectie) en D (opmerkingen bij tekst).

Bouwt op test_review_c1.ReviewBasis.
"""

import json

from django.core import mail
from django.test import override_settings

from kennisbank import diensten, review
from kennisbank.models import (
    ArtikelVersie,
    Conceptversie,
    Inzage,
    InzageStatus,
    ReviewOpmerking,
    Verbetervoorstel,
    VoorstelStatus,
)
from kennisbank.tests.test_kennisbank import beheerdata
from kennisbank.tests.test_review_c1 import ReviewBasis


class MeenemenTests(ReviewBasis):
    def setUp(self):
        super().setUp()
        self.v = self.voorstel(artikel=self.a, tekst="Twee weken is te kort")

    def meenemen(self):
        """Sinds 1.26.0 neem je mee in de lade, en dat telt bij opslaan. Hier: de stand direct omzetten."""
        Verbetervoorstel.objects.filter(pk=self.v.pk).update(in_conceptversie=not self.v.in_conceptversie)
        self.v.refresh_from_db()

    def publiceer_concept(self, **extra):
        c = Conceptversie.objects.get(artikel=self.a)
        self.client.force_login(self.anna)
        return self.post(
            self.url, beheerdata(self.a, inhoud=c.velden["inhoud"], geladen_concept=c.stempel, **extra), _save="1"
        )

    def test_meenemen_en_weer_uitzetten(self):
        self.als(self.anna)
        self.meenemen()
        self.assertTrue(self.v.in_conceptversie)
        self.assertIn("Meegenomen verbetervoorstellen (1)", self.client.get(self.url).content.decode())
        self.meenemen()
        self.assertFalse(self.v.in_conceptversie)

    def test_afgehandeld_voorstel_kan_niet_mee(self):
        diensten.voorstel_afhandelen(self.v, self.anna, VoorstelStatus.AFGEWEZEN, "Nee")
        r = self.als(self.anna).post(f"/beheer/voorstel/{self.v.pk}/", {"actie": "meenemen"})
        self.assertEqual(r.status_code, 404)

    @override_settings(KB_EMAIL_AAN=True)
    def test_na_publiceren_het_scherm_met_voorgevuld_bericht(self):
        self.maak_concept()
        self.meenemen()
        r = self.publiceer_concept()
        afhandelen = f"/beheer/kennisbank/artikel/{self.a.pk}/voorstellen-afhandelen/"
        self.assertEqual(r["Location"], afhandelen)
        self.v.refresh_from_db()
        self.assertEqual((self.v.verwerkt_in_versie, self.v.in_conceptversie), (2, False))
        html = self.client.get(afhandelen).content.decode()
        self.assertIn("verwerkt in versie 2 van", html)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(
                afhandelen, {f"afhandelen-{self.v.pk}": "1", f"bericht-{self.v.pk}": "Dank je, staat erin."}
            )
        self.v.refresh_from_db()
        self.assertEqual(self.v.status, VoorstelStatus.VERWERKT)
        self.assertEqual(self.v.terugkoppeling, "Dank je, staat erin.")
        self.assertEqual([m.to for m in mail.outbox], [["lies@example.org"]])
        self.assertEqual(r["Location"], "/beheer/")

    def test_overslaan_laat_het_voorstel_open_met_label(self):
        self.maak_concept()
        self.meenemen()
        self.publiceer_concept()
        afhandelen = f"/beheer/kennisbank/artikel/{self.a.pk}/voorstellen-afhandelen/"
        self.client.post(afhandelen, {f"bericht-{self.v.pk}": "x"})  # geen vinkje
        self.v.refresh_from_db()
        self.assertTrue(self.v.is_open)
        # Sinds 1.26.0 staat het open voorstel in de lade, met "al verwerkt in versie 2".
        html = self.client.get(f"/beheer/voorstel/{self.v.pk}/", follow=True).content.decode()
        self.assertIn('"verwerkt_in_versie": 2', html)

    def test_zonder_meegenomen_voorstellen_gewoon_naar_de_werkplek(self):
        self.maak_concept()
        r = self.publiceer_concept()
        self.assertEqual(r["Location"], "/beheer/")

    def test_afhandelscherm_alleen_eigen_omgeving(self):
        self.assertEqual(
            self.als(self.zoe).get(f"/beheer/kennisbank/artikel/{self.a.pk}/voorstellen-afhandelen/").status_code, 404
        )


class SpoedcorrectieTests(ReviewBasis):
    def setUp(self):
        super().setUp()
        self.c = self.maak_concept()
        self.ter_inzage()

    def test_spoed_opent_de_gepubliceerde_tekst(self):
        html = self.client.get(self.url + "?spoed=1").content.decode()
        self.assertIn("Spoedcorrectie: je past de gepubliceerde versie aan", html)
        self.assertIn("twee weken", html)
        self.assertNotIn('id="kb-op-slot"', html)
        self.assertIn("Corrigeer de gepubliceerde versie", self.client.get(self.url).content.decode())

    def test_spoed_publiceert_zonder_de_conceptversie_te_raken(self):
        data = beheerdata(
            self.a,
            inhoud="<p>Stuur na twee weken een rappel. Bel 030-1234567.</p>",
            wijzigingstoelichting="Telefoonnummer toegevoegd",
        )
        r = self.post(self.url + "?spoed=1", data, _save="1")
        self.assertEqual(r.status_code, 302, r.content[:600])
        self.a.refresh_from_db()
        self.assertIn("030-1234567", self.a.inhoud)
        self.assertEqual(self.a.versie, 2)
        # De conceptversie en de review zijn ongemoeid.
        c = Conceptversie.objects.get(artikel=self.a)
        self.assertEqual((c.stempel, c.velden["inhoud"]), (self.c.stempel, "<p>Stuur na drie weken een rappel.</p>"))
        self.assertTrue(review.op_slot(self.a.pk))
        self.assertIn("Spoedcorrectie", ArtikelVersie.objects.get(artikel=self.a, versie=2).review)
        # De gele balk en de reviewer zien dat de gepubliceerde versie is aangepast.
        self.assertIn("is gewijzigd nadat deze conceptversie begon", self.client.get(self.url).content.decode())
        i = Inzage.objects.get()
        self.assertIn(
            "is aangepast nadat deze conceptversie begon", self.als(self.wim).get(f"/review/{i.pk}/").content.decode()
        )

    def test_spoed_vraagt_ook_een_toelichting(self):
        data = beheerdata(self.a, inhoud="<p>Iets anders.</p>", wijzigingstoelichting="")
        r = self.post(self.url + "?spoed=1", data, _save="1")
        self.assertEqual(r.status_code, 200)
        self.a.refresh_from_db()
        self.assertEqual(self.a.versie, 1)

    def test_spoed_neemt_geen_voorstellen_mee(self):
        v = self.voorstel(artikel=self.a)
        Verbetervoorstel.objects.filter(pk=v.pk).update(in_conceptversie=True)
        data = beheerdata(self.a, inhoud="<p>Spoed.</p>", wijzigingstoelichting="Spoed")
        self.post(self.url + "?spoed=1", data, _save="1")
        v.refresh_from_db()
        self.assertTrue(v.in_conceptversie)
        self.assertIsNone(v.verwerkt_in_versie)


class OpmerkingBijTekstTests(ReviewBasis):
    def setUp(self):
        super().setUp()
        self.maak_concept()
        self.ter_inzage()
        self.i = Inzage.objects.get()

    def test_opmerking_bewaart_het_citaat(self):
        self.als(self.wim).post(
            f"/review/{self.i.pk}/",
            {"actie": "opmerking", "tekst": "Moet dit niet zes zijn?", "citaat": "  drie   weken "},
        )
        o = ReviewOpmerking.objects.get()
        self.assertEqual((o.citaat, o.tekst), ("drie weken", "Moet dit niet zes zijn?"))

    def test_algemene_opmerking_kan_ook(self):
        self.als(self.wim).post(f"/review/{self.i.pk}/", {"actie": "opmerking", "tekst": "Helder stuk."})
        self.assertEqual(ReviewOpmerking.objects.get().citaat, "")

    def test_citaat_bij_teruggeven(self):
        self.als(self.wim).post(
            f"/review/{self.i.pk}/", {"actie": "teruggeven", "tekst": "Zes.", "citaat": "drie weken"}
        )
        self.i.refresh_from_db()
        self.assertEqual(self.i.status, InzageStatus.TERUGGEGEVEN)
        self.assertEqual(ReviewOpmerking.objects.get().citaat, "drie weken")

    def test_reviewer_krijgt_de_opmerkingen_als_gegevens(self):
        review.opmerking_toevoegen(self.i, self.wim, "Zes?", "drie weken")
        html = self.als(self.wim).get(f"/review/{self.i.pk}/").content.decode()
        # 1.30.0: de kaarten staan in de pagina; het script zoekt het citaat en zet de markering.
        self.assertIn('id="rv-opm-1" data-nr="1" data-citaat="drie weken"', html)
        self.assertIn('<p class="rv-kaart-tekst">Zes?</p>', html)
        self.assertIn("opmerkingen.js", html)

    def test_redacteur_krijgt_de_opmerkingen_voor_het_voorbeeld(self):
        review.opmerking_toevoegen(self.i, self.wim, "Zes?", "drie weken")
        review.teruggeven(self.i, self.wim)
        html = self.als(self.anna).get(self.url).content.decode()
        self.assertIn('id="kb-opmerkingen"', html)
        self.assertIn("drie weken", html)
        self.assertIn("Team Water \\u00b7 Wim", html)

    def test_geen_html_in_het_citaat(self):
        review.opmerking_toevoegen(self.i, self.wim, "x", "<script>alert(1)</script>")
        html = self.als(self.anna).get(self.url).content.decode()
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_opmerkingen_van_een_afgesloten_review_niet_meer_in_het_voorbeeld(self):
        review.opmerking_toevoegen(self.i, self.wim, "Zes?", "drie weken")
        review.afsluiten(self.a)
        self.assertNotIn('id="kb-opmerkingen"', self.als(self.anna).get(self.url).content.decode())


class OpmerkingenPasNaReactieTests(ReviewBasis):
    def test_redacteur_ziet_opmerkingen_pas_als_het_team_reageert(self):
        self.maak_concept()
        self.ter_inzage()
        i = Inzage.objects.get()
        review.opmerking_toevoegen(i, self.wim, "Nog aan het lezen", "drie weken")
        html = self.als(self.anna).get(self.url).content.decode()
        self.assertNotIn("Nog aan het lezen", html)
        self.assertNotIn('id="kb-opmerkingen"', html)
        review.teruggeven(i, self.wim)
        html = self.client.get(self.url).content.decode()
        self.assertIn("Nog aan het lezen", html)
        self.assertIn('id="kb-opmerkingen"', html)

    def test_voorbeeld_toont_alleen_de_laatste_ronde(self):
        self.maak_concept()
        self.ter_inzage()
        eerste = Inzage.objects.get()
        review.teruggeven(eerste, self.wim, "Oude opmerking", "twee")
        self.maak_concept(inhoud="<p>Stuur na vier weken een rappel.</p>")
        self.ter_inzage()
        tweede = Inzage.objects.exclude(pk=eerste.pk).get()
        review.teruggeven(tweede, self.wim, "Nieuwe opmerking", "vier weken")
        html = self.als(self.anna).get(self.url).content.decode()
        start = html.index('id="kb-opmerkingen"')
        data = json.loads(html[html.index(">", start) + 1 : html.index("</script>", start)])
        self.assertEqual([d["tekst"] for d in data], ["Nieuwe opmerking"])


class TerugroepenTijdensReviewTests(ReviewBasis):
    def setUp(self):
        super().setUp()
        self.maak_concept()
        self.ter_inzage()
        self.i = Inzage.objects.get()

    def test_vraag_bij_terugroepen_als_het_team_bezig_is(self):
        self.assertNotIn("al mee bezig", self.als(self.anna).get(self.url).content.decode())
        review.oppakken(self.i, self.wim)
        review.opmerking_toevoegen(self.i, self.wim, "Half af", "drie weken")
        html = self.client.get(self.url).content.decode()
        self.assertIn("Team Water (1 opmerking) is hier al mee bezig. Toch terugroepen?", html)

    @override_settings(KB_EMAIL_AAN=True)
    def test_reviewer_krijgt_een_mail_en_opmerkingen_zijn_voorlopig(self):
        review.oppakken(self.i, self.wim)
        review.opmerking_toevoegen(self.i, self.wim, "Half af", "drie weken")
        mail.outbox.clear()
        self.client.force_login(self.anna)
        with self.captureOnCommitCallbacks(execute=True):
            self.post(f"/beheer/kennisbank/artikel/{self.a.pk}/terugroepen/", {})
        self.assertEqual([m.to for m in mail.outbox], [["wim@example.org"]])
        self.assertIn("1 opmerking tot nu toe is bewaard", mail.outbox[0].body)
        html = self.client.get(self.url).content.decode()
        self.assertIn("mogelijk niet compleet", html)
        start = html.index('id="kb-opmerkingen"')
        data = json.loads(html[html.index(">", start) + 1 : html.index("</script>", start)])
        self.assertEqual([(d["tekst"], d["voorlopig"]) for d in data], [("Half af", True)])

    @override_settings(KB_EMAIL_AAN=True)
    def test_geen_mail_als_niemand_het_had_opgepakt(self):
        mail.outbox.clear()
        self.client.force_login(self.anna)
        with self.captureOnCommitCallbacks(execute=True):
            self.post(f"/beheer/kennisbank/artikel/{self.a.pk}/terugroepen/", {})
        self.assertEqual(mail.outbox, [])
