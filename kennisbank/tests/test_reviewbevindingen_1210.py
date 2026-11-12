"""1.21.0: reparaties na de onafhankelijke review sinds 1.15.0 (bouwlijst `bouwlijst-1.21.0-reviewbevindingen.md`).

Elke test hoort bij een bevinding uit `review-sinds-1.15.0-onafhankelijk.md` en is de omgekeerde vorm van
het proefscript van de reviewer: wat daar mis bleek te gaan, mag hier niet meer gebeuren.
"""

import datetime
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from kennisbank import diensten, review
from kennisbank.models import (
    Artikel,
    ArtikelVersie,
    Conceptversie,
    Inzage,
    InzageStatus,
    ReviewOpmerking,
    Status,
    VoorstelStatus,
)
from kennisbank.tests.test_kennisbank import beheerdata
from kennisbank.tests.test_review_c1 import ReviewBasis


def meldingen(r):
    return " | ".join(str(m) for m in get_messages(r.wsgi_request))


class Bevindingen(ReviewBasis):
    def inzage(self):
        return Inzage.objects.get(artikel=self.a, afgesloten=False, status=InzageStatus.TER_INZAGE)

    def akkoord_van_wim(self):
        i = self.inzage()
        self.als(self.wim).post(f"/review/{i.pk}/", {"actie": "akkoord"})
        i.refresh_from_db()
        self.assertEqual(i.status, InzageStatus.AKKOORD)
        return i

    # --- Hoog ---------------------------------------------------------------------------------

    def test_1_akkoord_geldt_niet_voor_een_andere_tekst(self):
        c = self.maak_concept()
        self.ter_inzage()
        self.akkoord_van_wim()
        self.client.force_login(self.anna)
        r = self.post(
            self.url,
            beheerdata(
                self.a,
                inhoud="<p>Stuur na ZES weken een rappel.</p>",
                geladen_concept=c.stempel,
                wijzigingstoelichting="Termijn",
            ),
            _save="1",
        )
        self.assertEqual(r.status_code, 302, r.content[:2000])
        laatste = ArtikelVersie.objects.filter(artikel=self.a).order_by("-versie").first()
        self.assertEqual(laatste.review, "Gepubliceerd met wijzigingen na het akkoord van Team Water.")

    def test_1b_precies_de_goedgekeurde_tekst_houdt_het_akkoord(self):
        c = self.maak_concept()
        self.ter_inzage()
        self.akkoord_van_wim()
        self.client.force_login(self.anna)
        self.post(
            self.url,
            beheerdata(self.a, inhoud=c.velden["inhoud"], geladen_concept=c.stempel, wijzigingstoelichting="Termijn"),
            _save="1",
        )
        laatste = ArtikelVersie.objects.filter(artikel=self.a).order_by("-versie").first()
        self.assertEqual(laatste.review, "Akkoord van Team Water.")

    def test_2_spoedcorrectie_verhuist_het_artikel_niet(self):
        self.anna.groups.add(Group.objects.get(name="zuid-redactie"))
        self.maak_concept()
        self.ter_inzage()
        self.client.force_login(self.anna)
        r = self.post(
            self.url + "?spoed=1",
            beheerdata(self.a, omgeving=self.zuid.pk, wijzigingstoelichting="Hoort bij Zuid"),
            _save="1",
        )
        self.assertEqual(r.status_code, 302, r.content[:2000])
        self.a.refresh_from_db()
        self.assertEqual(self.a.omgeving_id, self.noord.pk)
        self.assertTrue(review.op_slot(self.a.pk))  # de review loopt gewoon door
        html = self.client.get(self.url + "?spoed=1").content.decode()
        self.assertRegex(html, r'<select name="omgeving"[^>]*disabled')

    @override_settings(KB_EMAIL_AAN=True)
    def test_2b_verhuizen_stopt_de_review_en_het_oude_team_leest_niet_mee(self):
        self.maak_concept()
        self.ter_inzage()
        i = self.inzage()
        self.als(self.wim).post(f"/review/{i.pk}/", {"actie": "oppakken"})
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.a.omgeving = self.zuid
            self.a.save()
        self.assertFalse(review.op_slot(self.a.pk))
        self.assertTrue(any("wim@example.org" in m.to and "andere omgeving" in m.body for m in mail.outbox))
        self.assertEqual(self.als(self.wim).get(f"/review/{i.pk}/").status_code, 302)
        self.assertNotIn("Rappel versturen", self.als(self.wim).get("/review/").content.decode().split("afgerond")[0])

    def test_2c_dienst_weigert_een_team_van_een_andere_omgeving_dan_het_artikel(self):
        # Ook als de inzage om wat voor reden nog open staat: alleen een team van de huidige omgeving.
        self.maak_concept()
        self.ter_inzage()
        i = self.inzage()
        Artikel.objects.filter(pk=self.a.pk).update(omgeving=self.zuid)  # zonder signaal
        self.assertIsNone(review._inzage_voor(self.wim, i.pk))

    @override_settings(KB_EMAIL_AAN=True)
    def test_3_reviewproces_uitzetten_roept_alles_terug(self):
        c = self.maak_concept()
        self.ter_inzage()
        i = self.inzage()
        self.als(self.wim).post(f"/review/{i.pk}/", {"actie": "oppakken"})
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.noord.reviewproces = False
            self.noord.save()
        i.refresh_from_db()
        self.assertEqual(i.status, InzageStatus.TERUGGEROEPEN)
        self.assertFalse(review.op_slot(self.a.pk))
        self.assertTrue(any("wim@example.org" in m.to and "uitgezet" in m.body for m in mail.outbox))
        # Publiceren zet nu precies de tekst van het scherm live.
        self.client.force_login(self.anna)
        r = self.post(
            self.url,
            beheerdata(
                self.a, inhoud="<p>Mijn verbeterde tekst</p>", wijzigingstoelichting="Beter", geladen_concept=c.stempel
            ),
            _save="1",
        )
        self.assertEqual(r.status_code, 302, r.content[:2000])
        self.a.refresh_from_db()
        self.assertEqual(self.a.inhoud, "<p>Mijn verbeterde tekst</p>")

    def test_3b_aanzetten_of_iets_anders_wijzigen_roept_niets_terug(self):
        self.maak_concept()
        self.ter_inzage()
        self.noord.naam = "Noord-Nederland"
        self.noord.save()
        self.assertTrue(review.op_slot(self.a.pk))

    # --- Midden -------------------------------------------------------------------------------

    def test_5_verbergen_zet_een_vaste_stand(self):
        v = self.voorstel(artikel=self.a, tekst="Er staat de naam van Kees in")
        url = f"/beheer/voorstel/{v.pk}/"
        self.als(self.bram).post(url, {"actie": "verbergen", "waarde": "1"})
        r = self.als(self.anna).post(url, {"actie": "verbergen", "waarde": "1"})  # oud scherm
        v.refresh_from_db()
        self.assertTrue(v.verborgen)
        self.assertIn("collega al gedaan", meldingen(r))
        self.als(self.anna).post(url, {"actie": "verbergen", "waarde": "0"})
        v.refresh_from_db()
        self.assertFalse(v.verborgen)

    def test_5b_meenemen_dubbelklik_draait_niets_terug(self):
        v = self.voorstel(artikel=self.a)
        url = f"/beheer/voorstel/{v.pk}/"
        self.als(self.anna).post(url, {"actie": "meenemen", "waarde": "1"})
        self.als(self.anna).post(url, {"actie": "meenemen", "waarde": "1"})
        v.refresh_from_db()
        self.assertTrue(v.in_conceptversie)

    def test_5c_het_scherm_stuurt_de_stand_mee(self):
        v = self.voorstel(artikel=self.a)
        html = self.als(self.anna).get(f"/beheer/voorstel/{v.pk}/").content.decode()
        self.assertIn('name="waarde" value="1"><button type="submit" name="actie" value="verbergen"', html)
        self.assertIn('name="waarde" value="1"><button type="submit" name="actie" value="meenemen"', html)

    @override_settings(KB_EMAIL_AAN=True)
    def test_6_archiveren_via_de_lijst_stopt_de_review_en_bewaart_het_concept(self):
        self.maak_concept()
        self.ter_inzage()
        i = self.inzage()
        self.als(self.wim).post(f"/review/{i.pk}/", {"actie": "oppakken"})
        mail.outbox.clear()
        self.client.force_login(self.anna)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                "/beheer/kennisbank/artikel/", {"action": "archiveren", "_selected_action": [self.a.pk], "index": 0}
            )
        self.a.refresh_from_db()
        self.assertEqual(self.a.status, Status.GEARCHIVEERD)
        self.assertTrue(Conceptversie.objects.filter(artikel=self.a).exists())
        self.assertFalse(Inzage.objects.filter(artikel=self.a, afgesloten=False).exists())
        self.assertTrue(any("wim@example.org" in m.to and "gearchiveerd" in m.body for m in mail.outbox))
        self.als(self.wim).post(f"/review/{i.pk}/", {"actie": "akkoord"})
        i.refresh_from_db()
        self.assertEqual(i.status, InzageStatus.TER_INZAGE)  # geen akkoord op een ingetrokken artikel
        self.assertNotIn("Rappel versturen", self.als(self.anna).get("/beheer/?bak=ter_inzage").content.decode())

    def test_7_weggooien_en_publiceren_kunnen_niet_tijdens_de_review(self):
        c = self.maak_concept()
        self.ter_inzage()
        r = self.post(f"/beheer/kennisbank/artikel/{self.a.pk}/conceptversie/weggooien/", {})
        self.assertIn("Roep hem eerst terug", meldingen(r))
        self.assertTrue(Conceptversie.objects.filter(artikel=self.a).exists())
        r = self.post(
            self.url,
            beheerdata(self.a, inhoud=c.velden["inhoud"], geladen_concept=c.stempel, wijzigingstoelichting="x"),
            _save="1",
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(review.op_slot(self.a.pk))

    def test_7b_reviewer_krijgt_een_nette_melding_met_zijn_tekst(self):
        self.maak_concept()
        self.ter_inzage()
        i = self.inzage()
        self.als(self.wim).post(f"/review/{i.pk}/", {"actie": "oppakken"})
        review.afsluiten(self.a)  # bijvoorbeeld gearchiveerd terwijl Wim typte
        r = self.als(self.wim).post(f"/review/{i.pk}/", {"actie": "opmerking", "tekst": "Lang verhaal van een uur"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("Lang verhaal van een uur", meldingen(r))
        self.assertFalse(ReviewOpmerking.objects.exists())

    def test_7c_ook_na_terugroepen_blijft_de_getypte_tekst_bewaard_in_de_melding(self):
        self.maak_concept()
        self.ter_inzage()
        i = self.inzage()
        self.post(f"/beheer/kennisbank/artikel/{self.a.pk}/terugroepen/", {})
        r = self.als(self.wim).post(f"/review/{i.pk}/", {"actie": "teruggeven", "tekst": "Mijn bevindingen"})
        self.assertIn("Mijn bevindingen", meldingen(r))

    def test_7d_een_vreemde_inzage_blijft_404(self):
        self.maak_concept()
        self.ter_inzage()
        i = self.inzage()
        self.assertEqual(self.als(self.zara).get(f"/review/{i.pk}/").status_code, 404)
        self.assertEqual(self.als(self.zara).post(f"/review/{i.pk}/", {"actie": "akkoord"}).status_code, 404)

    def test_8_weggooien_zet_meenemen_uit(self):
        v = self.voorstel(artikel=self.a, tekst="Twee weken is te kort")
        self.maak_concept()
        self.als(self.anna).post(f"/beheer/voorstel/{v.pk}/", {"actie": "meenemen", "waarde": "1"})
        self.client.post(f"/beheer/kennisbank/artikel/{self.a.pk}/conceptversie/weggooien/")
        self.assertFalse(Conceptversie.objects.exists())
        v.refresh_from_db()
        self.assertFalse(v.in_conceptversie)
        self.a.refresh_from_db()
        self.client.force_login(self.bram)
        r = self.post(
            self.url,
            beheerdata(self.a, titel="Rappel versturen.", kleine_correctie="on", wijzigingstoelichting=""),
            _save="1",
        )
        v.refresh_from_db()
        self.assertIsNone(v.verwerkt_in_versie)
        self.assertNotIn("voorstellen-afhandelen", r.get("Location", ""))

    def test_8b_een_kleine_correctie_neemt_geen_voorstellen_mee(self):
        v = self.voorstel(artikel=self.a)
        self.als(self.anna).post(f"/beheer/voorstel/{v.pk}/", {"actie": "meenemen", "waarde": "1"})
        self.client.force_login(self.bram)
        self.post(self.url, beheerdata(self.a, titel="Rappel versturen.", kleine_correctie="on"), _save="1")
        v.refresh_from_db()
        self.assertTrue(v.in_conceptversie)
        self.assertIsNone(v.verwerkt_in_versie)

    def test_9_oppakken_uit_een_oude_werkplek_neemt_niet_stil_over(self):
        v = self.voorstel(artikel=self.a)
        self.als(self.bram).post(
            "/beheer/werkplek/actie/", {"voorstel": v.pk, "actie": "oppakken", "geladen_eigenaar": ""}
        )
        r = self.als(self.anna).post(
            "/beheer/werkplek/actie/", {"voorstel": v.pk, "actie": "oppakken", "geladen_eigenaar": ""}
        )
        v.refresh_from_db()
        self.assertEqual(v.eigenaar, self.bram)
        self.assertIn("intussen opgepakt", meldingen(r))
        # Bewust overnemen (met Bram in beeld) kan gewoon.
        self.als(self.anna).post(
            "/beheer/werkplek/actie/", {"voorstel": v.pk, "actie": "oppakken", "geladen_eigenaar": str(self.bram.pk)}
        )
        v.refresh_from_db()
        self.assertEqual(v.eigenaar, self.anna)

    def test_9b_de_werkplek_stuurt_de_eigenaar_mee(self):
        self.voorstel(artikel=self.a)
        html = self.als(self.anna).get(f"/beheer/?bak=cluster-{self.water.pk}").content.decode()
        self.assertIn('name="geladen_eigenaar" value=""', html)

    # --- Laag ---------------------------------------------------------------------------------

    def test_10_dubbel_alleen_bij_hetzelfde_artikel(self):
        ander = Artikel.objects.create(
            omgeving=self.noord, titel="Iets anders", samenvatting="x", inhoud="<p>y</p>", status=Status.GEPUBLICEERD
        )
        v = self.voorstel(artikel=self.a)
        w = self.voorstel(artikel=ander, tekst="Over iets heel anders")
        with self.assertRaises(diensten.VoorstelFout):
            diensten.voorstel_afhandelen(v, self.anna, VoorstelStatus.AFGEWEZEN, "Dubbel", dubbel_van=w)
        x = self.voorstel(artikel=self.a, tekst="Hetzelfde")
        diensten.voorstel_afhandelen(v, self.anna, VoorstelStatus.AFGEWEZEN, "Dubbel", dubbel_van=x)
        v.refresh_from_db()
        with self.assertRaises(diensten.VoorstelFout):  # geen kring
            diensten.voorstel_afhandelen(x, self.anna, VoorstelStatus.AFGEWEZEN, "Dubbel", dubbel_van=v)

    def test_11_afgerond_stuk_toont_geen_tekst_meer(self):
        self.maak_concept()
        self.ter_inzage()
        i = self.inzage()
        self.als(self.wim).post(f"/review/{i.pk}/", {"actie": "teruggeven", "tekst": "Klopt niet"})
        c = Conceptversie.objects.get(artikel=self.a)
        self.client.force_login(self.anna)
        self.post(
            self.url,
            beheerdata(self.a, inhoud="<p>HALFAF werk</p>", wijzigingstoelichting="", geladen_concept=c.stempel),
            _conceptversie="1",
        )
        r = self.als(self.wim).get(f"/review/{i.pk}/")
        self.assertEqual(r.status_code, 302)
        lijst = self.als(self.wim).get("/review/").content.decode()
        self.assertIn("Rappel versturen", lijst)  # wel in "Onlangs afgerond"
        self.assertNotIn(f'href="/review/{i.pk}/"', lijst)
        self.assertNotIn("HALFAF", lijst)

    @override_settings(KB_EMAIL_AAN=True)
    def test_12_api_afhandelen_mailt_de_vorige_eigenaar(self):
        v = self.voorstel(artikel=self.a)
        diensten.voorstel_naar_bak(v, self.bram, self.bram)
        mail.outbox.clear()
        self.client.force_login(self.anna)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.patch(
                f"/api/v1/voorstellen/{v.pk}",
                {"status": "verwerkt", "terugkoppeling": "Gedaan"},
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(any("bram@example.org" in m.to for m in mail.outbox))
        v.refresh_from_db()
        self.assertEqual(v.status, VoorstelStatus.VERWERKT)
        self.assertEqual(v.berichten.filter(tekst="Gedaan").count(), 1)

    def test_12b_api_dubbel_afhandelen_blijft_geweigerd(self):
        v = self.voorstel(artikel=self.a)
        self.client.force_login(self.anna)
        self.client.patch(
            f"/api/v1/voorstellen/{v.pk}",
            {"status": "verwerkt", "terugkoppeling": "Ja"},
            content_type="application/json",
        )
        r = self.client.patch(
            f"/api/v1/voorstellen/{v.pk}",
            {"status": "afgewezen", "terugkoppeling": "Nee"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 409)

    @override_settings(KB_EMAIL_AAN=True)
    def test_13_samenvatting_alleen_open_voorstellen(self):
        v = self.voorstel(artikel=self.a, tekst="Al lang opgelost voorstel")
        self.voorstel(artikel=self.a, tekst="Nog open voorstel")
        diensten.voorstel_afhandelen(v, self.anna, VoorstelStatus.AFGEWEZEN, "Nee")
        mail.outbox.clear()
        diensten.verstuur_voorstellenmail(nu=timezone.now() + datetime.timedelta(minutes=1))
        teksten = " ".join(m.body for m in mail.outbox)
        self.assertNotIn("Al lang opgelost", teksten)
        self.assertIn("Nog open voorstel", teksten)

    def test_14_terugroepen_uit_een_oud_scherm_zegt_wat_er_gebeurde(self):
        self.maak_concept()
        self.ter_inzage()
        self.akkoord_van_wim()
        self.client.force_login(self.anna)
        r = self.client.post(f"/beheer/kennisbank/artikel/{self.a.pk}/terugroepen/")
        self.assertIn("Team Water heeft intussen akkoord gegeven", meldingen(r))

    def test_15_archiveren_via_het_scherm_houdt_de_gepubliceerde_tekst(self):
        c = self.maak_concept()
        self.client.force_login(self.anna)
        r = self.post(
            self.url,
            beheerdata(self.a, inhoud=c.velden["inhoud"], geladen_concept=c.stempel, status=Status.GEARCHIVEERD),
            _save="1",
        )
        self.assertEqual(r.status_code, 302, r.content[:2000])
        self.a.refresh_from_db()
        self.assertEqual(self.a.status, Status.GEARCHIVEERD)
        self.assertEqual(self.a.inhoud, "<p>Stuur na twee weken een rappel.</p>")
        self.assertTrue(Conceptversie.objects.filter(artikel=self.a).exists())

    def test_16_tweede_reviewer_neemt_niet_stil_over(self):
        w2 = get_user_model().objects.create_user("wanda", email="wanda@example.org", password="x", first_name="Wanda")
        w2.groups.add(Group.objects.get(name="team-water"))
        self.maak_concept()
        self.ter_inzage()
        i = self.inzage()
        self.als(self.wim).post(f"/review/{i.pk}/", {"actie": "oppakken", "geladen_reviewer": ""})
        r = self.als(w2).post(f"/review/{i.pk}/", {"actie": "oppakken", "geladen_reviewer": ""})
        i.refresh_from_db()
        self.assertEqual(i.reviewer, self.wim)
        self.assertIn("intussen opgepakt", meldingen(r))
        self.als(w2).post(f"/review/{i.pk}/", {"actie": "oppakken", "geladen_reviewer": str(self.wim.pk)})
        i.refresh_from_db()
        self.assertEqual(i.reviewer, w2)


class Afronden(ReviewBasis):
    """Bouwlijst 1.21.0, punt 1–5: één knop Afronden. De server-kant: opslaan-dan-ter-inzage en de stempel."""

    def test_4_ter_inzage_aanbieden_slaat_eerst_op(self):
        c = self.maak_concept()
        r = self.post(
            self.url,
            beheerdata(
                self.a, inhoud="<p>Nog net een zin erbij.</p>", wijzigingstoelichting="", geladen_concept=c.stempel
            ),
            _conceptversie="1",
            kb_daarna_ter_inzage="1",
            reviewteams=[self.team_water.pk],
        )
        self.assertEqual(r.status_code, 302)
        self.assertIn("ter inzage gegeven aan Team Water", meldingen(r))
        c.refresh_from_db()
        self.assertEqual(c.velden["inhoud"], "<p>Nog net een zin erbij.</p>")
        i = Inzage.objects.get(artikel=self.a)
        self.assertEqual(i.concept_stempel, c.stempel)

    def test_4b_zonder_team_wel_opgeslagen_niet_ter_inzage(self):
        c = self.maak_concept()
        r = self.post(
            self.url,
            beheerdata(self.a, inhoud="<p>Andere zin.</p>", wijzigingstoelichting="", geladen_concept=c.stempel),
            _conceptversie="1",
            kb_daarna_ter_inzage="1",
        )
        self.assertIn("nog niet ter inzage", meldingen(r))
        self.assertFalse(Inzage.objects.exists())
        c.refresh_from_db()
        self.assertEqual(c.velden["inhoud"], "<p>Andere zin.</p>")

    def test_4c_eerste_keer_ook_zonder_bestaande_conceptversie(self):
        self.client.force_login(self.anna)
        r = self.post(
            self.url,
            beheerdata(self.a, inhoud="<p>Meteen ter inzage.</p>", wijzigingstoelichting="", geladen_concept=""),
            _conceptversie="1",
            kb_daarna_ter_inzage="1",
            reviewteams=[self.team_water.pk],
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(review.op_slot(self.a.pk))

    def test_1c_opslaan_zonder_wijziging_houdt_het_akkoord(self):
        c = self.maak_concept()
        self.ter_inzage()
        i = Inzage.objects.get(artikel=self.a)
        self.als(self.wim).post(f"/review/{i.pk}/", {"actie": "akkoord"})
        self.client.force_login(self.anna)
        self.post(
            self.url,
            beheerdata(self.a, inhoud=c.velden["inhoud"], wijzigingstoelichting="", geladen_concept=c.stempel),
            _conceptversie="1",
        )
        self.assertTrue(review.stand(self.a)["label"])
        self.post(
            self.url,
            beheerdata(self.a, inhoud="<p>Toch anders.</p>", wijzigingstoelichting="", geladen_concept=c.stempel),
            _conceptversie="1",
        )
        self.assertIsNone(review.stand(self.a)["label"])

    def test_5_het_venster_krijgt_de_juiste_keuzes(self):
        import json
        import re

        self.maak_concept()

        def cfg(url=None):
            html = self.client.get(url or self.url).content.decode()
            m = re.search(r'<script id="kb-afronden" type="application/json">(.*?)</script>', html)
            return json.loads(m.group(1))

        c = cfg()
        self.assertFalse(c["op_slot"])
        self.assertEqual([t["naam"] for t in c["teams"]], ["Team Water", "Team Weg"])
        self.ter_inzage()
        c = cfg()
        self.assertTrue(c["op_slot"])
        self.assertEqual(c["teams"], [])
        c = cfg(self.url + "?spoed=1")
        self.assertTrue(c["spoed"])
        self.assertFalse(c["op_slot"])

    def test_5b_nieuw_artikel_krijgt_de_eenvoudige_afronden(self):
        # Sinds 1.25.0 (wens Alex) ook bij een nieuw artikel één knop Afronden, met minder keuzes.
        self.client.force_login(self.anna)
        html = self.client.get("/beheer/kennisbank/artikel/add/").content.decode()
        self.assertIn('id="kb-afronden"', html)
        self.assertIn('"eenvoudig": true', html)


class Bewerkscherm(ReviewBasis):
    """1.22.0: het nieuwe bewerkscherm (bouwlijst-1.22.0-nieuw-bewerkscherm.md). De editor zelf is
    JavaScript en is in de browser nagelopen; hier de server-kant: wat de pagina meekrijgt."""

    def test_artikel_gebruikt_de_nieuwe_editor_en_geen_jodit(self):
        self.maak_concept()
        html = self.client.get(self.url).content.decode()
        self.assertIn("kennisbank/vendor/tiptap/tiptap.min.js", html)
        self.assertIn("kennisbank/artikel-editor.js", html)
        self.assertIn("kennisbank/artikel-scherm.js", html)
        self.assertNotIn("jodit.min.js", html)
        for stuk in (
            'class="kb-balk"',
            'data-kb-plek="titel"',
            'data-kb-plek="inhoud"',
            'id="kb-p-eig"',
            'id="kb-p-gesch"',
            'id="kb-p-rev"',
            "Bekijk als medewerker",
        ):
            self.assertIn(stuk, html)

    def test_nieuwsbericht_krijgt_hetzelfde_scherm_en_geen_jodit_meer(self):
        # 1.23.0: Jodit is helemaal weg uit het pakket.
        self.client.force_login(self.anna)
        html = self.client.get("/beheer/kennisbank/bericht/add/").content.decode()
        self.assertIn("kennisbank/vendor/tiptap/tiptap.min.js", html)
        self.assertNotIn("jodit", html.lower())
        for stuk in (
            'class="kb-balk"',
            'data-kb-plek="titel"',
            'data-kb-plek="tekst"',
            'id="kb-p-eig"',
            "Nieuw nieuwsbericht",
        ):
            self.assertIn(stuk, html)
        self.assertNotIn("Bekijk als medewerker", html)

    def test_jodit_is_uit_het_pakket(self):
        import pathlib

        static = pathlib.Path(__file__).resolve().parents[1] / "static/kennisbank"
        self.assertFalse((static / "vendor/jodit").exists())
        for js in ("beheer-editor.js", "artikel-editor.js", "artikel-scherm.js"):
            self.assertNotIn("Jodit.make", (static / js).read_text())

    def test_nieuwsbericht_opslaan_werkt_zoals_altijd(self):
        from kennisbank.models import Bericht

        self.client.force_login(self.anna)
        r = self.client.post(
            "/beheer/kennisbank/bericht/add/",
            {
                "titel": "Nieuw rooster",
                "tekst": "<p>Vanaf maandag <strong>anders</strong>.</p><script>x</script>",
                "omgeving": self.noord.pk,
                "status": "concept",
                "_save": "1",
            },
        )
        self.assertEqual(r.status_code, 302, r.content[:500])
        b = Bericht.objects.get(titel="Nieuw rooster")
        self.assertIn("<strong>anders</strong>", b.tekst)
        self.assertNotIn("<script>", b.tekst)

    def test_nieuw_artikel_krijgt_ook_het_scherm(self):
        self.client.force_login(self.anna)
        html = self.client.get("/beheer/kennisbank/artikel/add/").content.decode()
        self.assertIn('class="kb-balk"', html)
        self.assertIn("Nieuw artikel", html)
        self.assertNotIn('id="kb-p-gesch"', html)  # nog geen geschiedenis

    def test_balk_noemt_de_stand_van_de_review(self):
        self.maak_concept()
        self.assertIn("Review: nog niet ter inzage", self.client.get(self.url).content.decode())
        self.ter_inzage()
        self.assertIn("Ter inzage bij Team Water", self.client.get(self.url).content.decode())
        i = Inzage.objects.get(artikel=self.a)
        self.als(self.wim).post(f"/review/{i.pk}/", {"actie": "oppakken"})
        self.client.force_login(self.anna)
        self.assertIn("Ter inzage bij Team Water · ligt bij Wim", self.client.get(self.url).content.decode())
        self.als(self.wim).post(f"/review/{i.pk}/", {"actie": "teruggeven", "tekst": "Klopt niet"})
        self.client.force_login(self.anna)
        self.assertIn("Teruggegeven door Team Water · 1 opmerking", self.client.get(self.url).content.decode())

    def test_balk_akkoord_en_vervallen(self):
        c = self.maak_concept()
        self.ter_inzage()
        i = Inzage.objects.get(artikel=self.a)
        self.als(self.wim).post(f"/review/{i.pk}/", {"actie": "akkoord"})
        self.client.force_login(self.anna)
        self.assertIn("Akkoord: Team Water", self.client.get(self.url).content.decode())
        self.post(
            self.url,
            beheerdata(self.a, inhoud="<p>Anders.</p>", wijzigingstoelichting="", geladen_concept=c.stempel),
            _conceptversie="1",
        )
        self.assertIn("Akkoord vervallen: tekst gewijzigd", self.client.get(self.url).content.decode())

    def test_balk_teruggeroepen(self):
        self.maak_concept()
        self.ter_inzage()
        self.post(f"/beheer/kennisbank/artikel/{self.a.pk}/terugroepen/", {})
        self.assertIn(">Teruggeroepen<", self.client.get(self.url).content.decode())


class GeenFlits(ReviewBasis):
    """1.24.0: de server zet elk veld meteen op zijn plek; er is geen oud formulier dat eerst verschijnt."""

    def plek(self, html, naam):
        m = re.search(rf'data-kb-plek="{naam}".*?</div>', html, re.S)
        self.assertIsNotNone(m, naam)
        return m.group(0)

    def test_velden_staan_meteen_op_het_blad(self):
        self.maak_concept()
        html = self.client.get(self.url).content.decode()
        self.assertNotIn("kb-bezig", html)
        self.assertIn('name="titel"', self.plek(html, "titel"))
        self.assertIn('name="samenvatting"', self.plek(html, "samenvatting"))
        self.assertIn('name="inhoud"', self.plek(html, "inhoud"))
        # Het veld staat er één keer, niet ook nog in een oude groep.
        self.assertEqual(html.count('name="titel"'), 1)
        self.assertEqual(html.count('name="inhoud"'), 1)
        # Eigenschappen in hun paneel, versie en geschiedenis in het paneel Geschiedenis.
        eig = html[html.index('id="kb-p-eig"') : html.index('id="kb-p-gesch"')]
        self.assertIn('name="soort"', eig)
        self.assertNotIn("field-versie", eig)
        gesch = html[html.index('id="kb-p-gesch"') :]
        self.assertIn("field-versie", gesch)
        # Geen kop, kruimelpad of zijmenu van Django meer.
        self.assertNotIn('id="header"', html)
        self.assertNotIn('class="breadcrumbs"', html)
        # Afronden staat in de balk, één keer.
        balk = html[html.index('<header class="kb-balk"') : html.index("</header>")]
        self.assertIn("kb-afronden-knop", balk)
        self.assertEqual(html.count('class="kb-afronden-knop"'), 1)

    def test_nieuw_artikel_opslaan_in_de_balk(self):
        self.client.force_login(self.anna)
        r = self.client.get("/beheer/kennisbank/artikel/add/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        balk = html[html.index('<header class="kb-balk"') : html.index("</header>")]
        # Sinds 1.25.0 Afronden in de balk; de gewone knoppen staan één keer (verborgen) in het formulier.
        self.assertIn("kb-afronden-knop", balk)
        self.assertEqual(html.count('name="_save"'), 1)

    def test_nieuwsbericht_op_het_blad(self):
        self.client.force_login(self.anna)
        html = self.client.get("/beheer/kennisbank/bericht/add/").content.decode()
        self.assertNotIn("kb-bezig", html)
        self.assertIn('name="titel"', self.plek(html, "titel"))
        self.assertIn('name="tekst"', self.plek(html, "tekst"))
        self.assertIn('placeholder="Titel van het bericht: wat is er nieuw?"', html)
        eig = html[html.index('id="kb-p-eig"') :]
        self.assertIn('name="omgeving"', eig)
        self.assertEqual(html.count('name="_save"'), 1)

    def test_melding_onder_de_balk(self):
        self.maak_concept()
        html = self.client.get(self.url).content.decode()  # na opslaan: "opgeslagen als conceptversie"
        self.assertEqual(html.count('class="messagelist"'), 1)
        self.assertGreater(html.index('class="messagelist"'), html.index("</header>"))

    def test_melding_en_fout_onder_de_balk(self):
        self.client.force_login(self.anna)
        r = self.post(self.url, beheerdata(self.a, titel=""))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        balk_eind = html.index("</header>")
        self.assertGreater(html.index("errornote"), balk_eind)
