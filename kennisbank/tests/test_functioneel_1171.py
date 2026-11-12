"""1.17.1: ronde 1 van de functionele review van 11 november (UX-ontwerper en functioneel analist).

Per test staat welk punt het is. Het ontwerp en de besluiten van Alex staan in de projectdocumenten
(review-functioneel-*-1.17.0.md).
"""

from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth.models import Group
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from kennisbank import diensten
from kennisbank.models import Artikel, Conceptversie, Rol, Status, Toegang, Verbetervoorstel, VoorstelStatus
from kennisbank.tests.test_bakken import Basis, wijzig_url
from kennisbank.tests.test_kennisbank import beheerdata


class BehandelFormulier(Basis):
    def post_formulier(self, v, **velden):
        data = {
            "geladen_status": velden.pop("geladen_status", v.status),
            "geladen_eigenaar": velden.pop("geladen_eigenaar", str(v.eigenaar_id or "")),
            "status": velden.pop("status", v.status),
            "naar_bak": velden.pop("naar_bak", str(v.eigenaar_id or "")),
            "berichten-TOTAL_FORMS": "1",
            "berichten-INITIAL_FORMS": "0",
            "berichten-MIN_NUM_FORMS": "0",
            "berichten-MAX_NUM_FORMS": "1000",
            "berichten-0-tekst": velden.pop("bericht", ""),
            **velden,
        }
        return self.client.post(wijzig_url(v), urlencode(data), content_type="application/x-www-form-urlencoded")


class AfsluitendBerichtTests(BehandelFormulier):
    """Punt 1: wie afhandelt, schrijft de indiener waarom."""

    def test_afwijzen_zonder_bericht_kan_niet(self):
        v = self.voorstel()
        r = self.als(self.anna).post(f"/beheer/voorstel/{v.pk}/lade/", {"actie": "afwijzen", "tekst": " "})
        self.assertEqual(r.status_code, 400)
        v.refresh_from_db()
        self.assertEqual(v.status, VoorstelStatus.NIEUW)

    @override_settings(KB_EMAIL_AAN=True)
    def test_afwijzen_met_bericht_stuurt_dat_bericht(self):
        v = self.voorstel()
        diensten.voorstelbericht_toevoegen(v, self.anna, "We kijken ernaar.", van_redactie=True)
        mail.outbox.clear()
        self.als(self.anna)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(
                f"/beheer/voorstel/{v.pk}/lade/", {"actie": "afwijzen", "tekst": "Dit staat zo in de wet."}
            )
        self.assertEqual(r.status_code, 200, r.content[:400])
        teksten = " ".join(m.body for m in mail.outbox)
        self.assertIn("Dit staat zo in de wet.", teksten)
        self.assertNotIn("We kijken ernaar.", teksten, "het oude tussenbericht is geen antwoord")

    def test_api_afhandelen_zonder_bericht_kan_niet(self):
        v = self.voorstel()
        r = self.als(self.anna).patch(
            f"/api/v1/voorstellen/{v.pk}", {"status": "verwerkt"}, content_type="application/json"
        )
        self.assertEqual(r.status_code, 400)
        v.refresh_from_db()
        self.assertEqual(v.status, VoorstelStatus.NIEUW)

    @override_settings(KB_EMAIL_AAN=True)
    def test_terug_naar_nieuw_geeft_geen_mail(self):
        v = self.voorstel(status=VoorstelStatus.IN_BEHANDELING)
        with self.captureOnCommitCallbacks(execute=True):
            v.status = VoorstelStatus.NIEUW
            diensten.meld_terugkoppeling(v)
        self.assertEqual(mail.outbox, [])


class AfgehandeldIsDefinitiefTests(BehandelFormulier):
    """Punt 8, besluit van Alex: afgehandeld is definitief; een bericht kan nog wel."""

    def afgehandeld(self):
        v = diensten.voorstel_naar_bak(self.voorstel(), self.anna, self.anna)
        Verbetervoorstel.objects.filter(pk=v.pk).update(status=VoorstelStatus.VERWERKT)
        v.refresh_from_db()
        return v

    def test_beheer_status_kan_niet_meer_terug(self):
        v = self.afgehandeld()
        self.als(self.anna)
        r = self.post_formulier(v, status="nieuw", geladen_status="verwerkt")
        self.assertEqual(r.status_code, 302, r.content[:400])
        v.refresh_from_db()
        self.assertEqual(v.status, VoorstelStatus.VERWERKT)
        self.assertIn("dat is definitief", self.client.get(wijzig_url(v), follow=True).content.decode())

    def test_api_heropenen_kan_niet(self):
        v = self.afgehandeld()
        r = self.als(self.anna).patch(
            f"/api/v1/voorstellen/{v.pk}", {"status": "in_behandeling"}, content_type="application/json"
        )
        self.assertEqual(r.status_code, 409)
        v.refresh_from_db()
        self.assertEqual(v.status, VoorstelStatus.VERWERKT)

    def test_bericht_na_afhandelen_kan_nog(self):
        v = self.afgehandeld()
        self.als(self.anna)
        r = self.post_formulier(v, bericht="Nog een aanvulling.", geladen_status="verwerkt")
        self.assertEqual(r.status_code, 302, r.content[:400])
        self.assertTrue(v.berichten.filter(tekst="Nog een aanvulling.").exists())


class VerplaatsenTests(Basis):
    """Punt 3 en 6: verplaatsen zonder keuze doet niets; de melding noemt het voorstel en de bak."""

    def test_melding_noemt_voorstel_en_bak(self):
        v = self.voorstel()
        r = self.als(self.anna).post("/beheer/werkplek/actie/", {"voorstel": v.pk, "actie": "oppakken"}, follow=True)
        tekst = r.content.decode()
        self.assertIn("Voorstel bij &#x27;Rappel&#x27; opgepakt", tekst)
        self.assertIn("ligt in de bak van Anna", tekst)
        self.assertNotIn("voorstel(len)", tekst)


class PublicerenTests(Basis):
    """Punt 4.1, 4.3 en 9: de knop heet Publiceren, werk van een collega vraagt bevestiging en een
    e-mail, en na publiceren ben je terug op de werkplek."""

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

    def test_knop_heet_publiceren_bij_een_gepubliceerd_artikel(self):
        html = self.als(self.anna).get(self.url).content.decode()
        self.assertIn('value="Publiceren…"', html)
        self.assertNotIn('name="_addanother"', html)
        concept = self.client.get(f"/beheer/kennisbank/artikel/{self.concept.pk}/change/").content.decode()
        self.assertNotIn("Publiceren…", concept, "een concept-artikel houdt de gewone knoppen")

    def concept_van(self, wie):
        self.als(wie)
        data = beheerdata(self.a, inhoud="<p>Nieuwe tekst</p>", wijzigingstoelichting="")
        data.setdefault("geladen_concept", "")
        self.post(data, _conceptversie="1")
        return Conceptversie.objects.get(artikel=self.a)

    def test_scherm_noemt_de_collega_van_de_conceptversie(self):
        self.concept_van(self.anna)
        html = self.als(self.bram).get(self.url).content.decode()
        self.assertIn('id="kb-concept-collegas" value="Anna"', html)
        self.assertNotIn("kb-concept-collegas", self.als(self.anna).get(self.url).content.decode())

    @override_settings(KB_EMAIL_AAN=True)
    def test_collega_krijgt_een_mail_als_zijn_conceptversie_live_gaat(self):
        c = self.concept_van(self.anna)
        mail.outbox.clear()
        self.als(self.bram)
        data = beheerdata(self.a, inhoud="<p>Nieuwe tekst</p>", geladen_concept=c.stempel)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.post(data, _save="1")
        self.assertEqual(r.status_code, 302, r.content[:400])
        aan_anna = [m for m in mail.outbox if m.to == ["anna@example.org"]]
        self.assertEqual(len(aan_anna), 1)
        self.assertIn("Bram heeft de conceptversie", aan_anna[0].body)

    @override_settings(KB_EMAIL_AAN=True)
    def test_eigen_conceptversie_publiceren_geeft_geen_mail_aan_jezelf(self):
        c = self.concept_van(self.anna)
        mail.outbox.clear()
        self.als(self.anna)
        with self.captureOnCommitCallbacks(execute=True):
            self.post(beheerdata(self.a, inhoud="<p>Nieuwe tekst</p>", geladen_concept=c.stempel), _save="1")
        self.assertFalse([m for m in mail.outbox if "Conceptversie gepubliceerd" in m.subject])

    def test_na_publiceren_terug_naar_de_werkplek(self):
        self.als(self.anna)
        r = self.post(beheerdata(self.a, inhoud="<p>Andere tekst</p>"), _save="1")
        self.assertEqual(r.status_code, 302, r.content[:400])
        self.assertEqual(r["Location"], "/beheer/")
        self.a.refresh_from_db()
        r = self.post(beheerdata(self.a, inhoud="<p>Weer anders</p>"), _continue="1")
        self.assertEqual(r["Location"], self.url)


class WerkplekTests(Basis):
    """Punt 9."""

    def test_eigen_bak_met_nieuw_werk_opent_eerst(self):
        diensten.voorstel_naar_bak(self.voorstel(), self.bram, self.anna)  # Bram wijst toe aan Anna
        w = self.als(self.anna).get("/beheer/").context["werkplek"]
        self.assertEqual(w["gekozen"], f"u{self.anna.pk}")
        w = self.als(self.bram).get("/beheer/").context["werkplek"]
        self.assertEqual(w["gekozen"], "algemeen")

    def test_rood_alleen_als_iets_lang_ligt(self):
        self.voorstel()
        html = self.als(self.anna).get("/beheer/").content.decode()
        self.assertNotIn("kb-aantal vol oud", html)
        oud = self.voorstel()
        Verbetervoorstel.objects.filter(pk=oud.pk).update(ingediend_op=timezone.now() - timedelta(days=31))
        html = self.client.get("/beheer/").content.decode()
        self.assertIn("kb-aantal vol oud", html)

    def test_omgeving_alleen_bij_meer_omgevingen(self):
        self.voorstel()
        html = self.als(self.anna).get("/beheer/").content.decode()
        self.assertNotIn(" · Noord", html)
        # Anna ook redacteur in Zuid: dan wél.
        g = Group.objects.create(name="anna-zuid")
        Toegang.objects.create(omgeving=self.zuid, groep=g, rol=Rol.REDACTEUR)
        self.anna.groups.add(g)
        html = self.als(self.anna).get(f"/beheer/?bak=algemeen-{self.noord.pk}").content.decode()
        self.assertIn(" · Noord", html)

    def test_werkplek_link_in_de_kennisbank(self):
        self.assertIn('id="lnkWerkplek"', self.als(self.lies).get("/").content.decode())
