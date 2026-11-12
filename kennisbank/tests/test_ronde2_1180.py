"""1.18.0: ronde 2 uit de functionele review van 11 november, met de besluiten c, d en e van Alex.

- het eigen behandelscherm /beheer/voorstel/<id>/ (bericht, verwerkt, afwijzen, dubbel, notities, bak);
- zoeken in Afgehandeld;
- archiveren sluit open voorstellen af ("het artikel is ingetrokken", status Vervallen);
- de dagelijkse samenvatting in plaats van een e-mail per nieuw voorstel.
"""

from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from kennisbank import diensten
from kennisbank.behandelen import citaat_in_context
from kennisbank.models import (
    Artikel,
    Status,
    Steun,
    Systeemstand,
    Verbetervoorstel,
    VoorstelNotitie,
    VoorstelStatus,
)
from kennisbank.tests.test_bakken import Basis, wijzig_url


def scherm(v):
    return f"/beheer/voorstel/{v.pk}/"


class Scherm(Basis):
    def post(self, v, actie, **velden):
        data = {
            "actie": actie,
            "geladen_status": v.status,
            "geladen_eigenaar": str(v.eigenaar_id or ""),
            "geladen_bericht": str(v.berichten.order_by("-pk").values_list("pk", flat=True).first() or 0),
            **velden,
        }
        return self.client.post(scherm(v), data)


class BehandelschermTests(Scherm):
    def test_scherm_toont_voorstel_gesprek_en_steun(self):
        v = self.voorstel(tekst="De termijn klopt niet")
        diensten.voorstelbericht_toevoegen(v, self.bram, "We kijken ernaar.", van_redactie=True, melden=False)
        diensten.steun_geven(v, self.piet)
        # Sinds 1.26.0 opent een open voorstel in de editor; de lade krijgt alles mee als gegevens.
        html = self.als(self.anna).get(scherm(v), follow=True).content.decode()
        self.assertIn('"indiener": "Lies"', html)
        self.assertIn('"tekst": "De termijn klopt niet"', html)
        self.assertIn("We kijken ernaar.", html)
        self.assertIn('"steuners": ["Piet', html)

    def test_alleen_de_eigen_omgeving(self):
        v = self.voorstel()
        self.assertEqual(self.als(self.zoe).get(scherm(v)).status_code, 404)
        self.assertNotEqual(self.als(self.lies).get(scherm(v)).status_code, 200)
        self.assertEqual(self.als(self.zoe).post(scherm(v), {"actie": "notitie", "notitie": "x"}).status_code, 404)

    def test_oude_beheerlink_komt_hier_uit(self):
        v = self.voorstel()
        r = self.als(self.anna).get(wijzig_url(v) + "?terug=algemeen")
        self.assertEqual(r["Location"], f"{scherm(v)}?terug=algemeen")

    @override_settings(KB_EMAIL_AAN=True)
    def test_bericht_versturen(self):
        v = self.voorstel()
        self.als(self.anna)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.post(v, "bericht", bericht="Opgepakt, we bellen je.")
        self.assertEqual(r.status_code, 302)
        self.assertEqual([b.tekst for b in v.berichten.all()], ["Opgepakt, we bellen je."])
        self.assertEqual([m.to for m in mail.outbox], [["lies@example.org"]])
        v.refresh_from_db()
        self.assertEqual((v.eigenaar, v.status), (self.anna, VoorstelStatus.IN_BEHANDELING))

    def test_leeg_bericht_verstuurt_niets(self):
        v = self.voorstel()
        r = self.als(self.anna).post(scherm(v), {"actie": "bericht", "bericht": "  "})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(v.berichten.exists())

    def test_verwerkt_alleen_met_bericht(self):
        v = self.voorstel()
        self.als(self.anna)
        r = self.post(v, "verwerkt", bericht="")
        self.assertEqual(r.status_code, 200)
        v.refresh_from_db()
        self.assertEqual(v.status, VoorstelStatus.NIEUW)
        r = self.post(v, "verwerkt", bericht="Aangepast in versie 2.", terug="algemeen")
        self.assertEqual(r["Location"], "/beheer/?bak=algemeen")
        v.refresh_from_db()
        self.assertEqual((v.status, v.eigenaar, v.behandeld_door), (VoorstelStatus.VERWERKT, self.anna, self.anna))
        self.assertEqual(v.terugkoppeling, "Aangepast in versie 2.")

    @override_settings(KB_EMAIL_AAN=True)
    def test_afhandelen_uit_de_bak_van_een_collega_meldt_dat_aan_hem(self):
        v = diensten.voorstel_naar_bak(self.voorstel(), self.bram, self.bram)
        self.als(self.anna)
        with self.captureOnCommitCallbacks(execute=True):
            self.post(v, "afwijzen", bericht="Staat al zo in de wet.")
        aan_bram = [m for m in mail.outbox if m.to == ["bram@example.org"]]
        self.assertEqual(len(aan_bram), 1)
        self.assertIn("uit jouw bak", aan_bram[0].body)

    def test_afwijzen_als_dubbel_neemt_de_steun_niet_mee(self):
        eerste = self.voorstel(tekst="Termijn klopt niet")
        tweede = self.voorstel(tekst="Termijn is fout", door=self.piet)
        diensten.steun_geven(tweede, self.lies)
        self.als(self.anna)
        r = self.post(tweede, "afwijzen", bericht="Dubbel; zie het andere voorstel.", dubbel_van=str(eerste.pk))
        self.assertEqual(r.status_code, 302)
        tweede.refresh_from_db()
        self.assertEqual((tweede.status, tweede.dubbel_van), (VoorstelStatus.AFGEWEZEN, eerste))
        self.assertEqual(Steun.objects.filter(voorstel=eerste).count(), 0)
        self.assertEqual(Steun.objects.filter(voorstel=tweede).count(), 1)
        self.assertIn("dubbel van", self.client.get(scherm(tweede)).content.decode())

    def test_dubbel_van_een_andere_omgeving_kan_niet(self):
        zuid = Artikel.objects.create(
            omgeving=self.zuid, titel="Z", samenvatting="z", inhoud="<p>z</p>", status=Status.GEPUBLICEERD, versie=1
        )
        ander = self.voorstel(artikel=zuid, door=self.zoe)
        v = self.voorstel()
        r = self.als(self.anna).post(scherm(v), {"actie": "afwijzen", "bericht": "x", "dubbel_van": str(ander.pk)})
        self.assertEqual(r.status_code, 404)
        v.refresh_from_db()
        self.assertEqual(v.status, VoorstelStatus.NIEUW)

    def test_nieuw_bericht_van_een_collega_houdt_versturen_tegen(self):
        v = self.voorstel()
        self.als(self.anna)
        geladen = {"geladen_bericht": "0", "geladen_status": v.status, "geladen_eigenaar": ""}
        diensten.voorstelbericht_toevoegen(v, self.bram, "Ik kijk ernaar.", van_redactie=True, melden=False)
        r = self.client.post(scherm(v), {"actie": "afwijzen", "bericht": "Afgewezen, sorry.", **geladen})
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("Er is niets verstuurd", html)
        self.assertIn("Bram stuurde intussen een bericht", html)
        self.assertIn("Afgewezen, sorry.", html, "de getypte tekst blijft staan")
        v.refresh_from_db()
        self.assertEqual(v.status, VoorstelStatus.NIEUW)
        self.assertEqual(v.berichten.count(), 1)

    def test_status_intussen_veranderd_houdt_afhandelen_tegen(self):
        v = self.voorstel()
        self.als(self.anna)
        Verbetervoorstel.objects.filter(pk=v.pk).update(status=VoorstelStatus.IN_BEHANDELING)
        r = self.client.post(
            scherm(v), {"actie": "verwerkt", "bericht": "Klaar.", "geladen_status": "nieuw", "geladen_bericht": "0"}
        )
        self.assertIn("Er is niets verstuurd", r.content.decode())
        v.refresh_from_db()
        self.assertEqual(v.status, VoorstelStatus.IN_BEHANDELING)

    def test_afgehandeld_blijft_afgehandeld(self):
        v = self.voorstel()
        self.als(self.anna)
        self.post(v, "verwerkt", bericht="Klaar.")
        v.refresh_from_db()
        html = self.client.get(scherm(v)).content.decode()
        self.assertNotIn("Versturen en verwerkt", html)
        self.post(v, "afwijzen", bericht="Toch niet.")
        v.refresh_from_db()
        self.assertEqual(v.status, VoorstelStatus.VERWERKT)
        self.post(v, "bericht", bericht="Nog een aanvulling.")
        self.assertEqual(v.berichten.count(), 2, "een bericht kan nog wel")

    def test_interne_notitie_alleen_voor_de_redactie(self):
        v = self.voorstel()
        self.als(self.anna)
        self.post(v, "notitie", notitie="Gebeld met Toezicht.")
        self.assertEqual(list(v.notities.values_list("tekst", flat=True)), ["Gebeld met Toezicht."])
        self.assertIn("Gebeld met Toezicht.", self.client.get(scherm(v), follow=True).content.decode())
        eigen = self.als(self.lies).get("/api/v1/voorstellen?lijst=mijn").content.decode()
        self.assertNotIn("Gebeld met Toezicht", eigen)
        alle = self.als(self.piet).get("/api/v1/voorstellen?lijst=alle").content.decode()
        self.assertNotIn("Gebeld met Toezicht", alle)

    def test_notities_verdwijnen_bij_het_anonimiseren(self):
        v = self.voorstel()
        diensten.notitie_toevoegen(v, self.anna, "Naam van een collega")
        Verbetervoorstel.objects.filter(pk=v.pk).update(
            status=VoorstelStatus.VERWERKT, behandeld_op=timezone.now() - timedelta(days=400)
        )
        call_command("kennisbank_opschonen", stdout=open("/dev/null", "w"))
        self.assertFalse(VoorstelNotitie.objects.filter(voorstel=v).exists())

    def test_verbergen_en_weer_tonen(self):
        v = self.voorstel()
        self.als(self.anna).post(scherm(v), {"actie": "verbergen"})
        v.refresh_from_db()
        self.assertTrue(v.verborgen)
        self.client.post(scherm(v), {"actie": "verbergen"})
        v.refresh_from_db()
        self.assertFalse(v.verborgen)

    def test_bakactie_vanaf_het_scherm_komt_terug_op_het_scherm(self):
        v = self.voorstel()
        r = self.als(self.anna).post(
            "/beheer/werkplek/actie/", {"voorstel": v.pk, "actie": "oppakken", "na": "scherm", "terug": "algemeen"}
        )
        self.assertEqual(r["Location"], f"{scherm(v)}?terug=algemeen")

    def test_werkplek_linkt_naar_het_scherm(self):
        v = self.voorstel()
        # Sinds 1.26.0 opent de regel de editor van het artikel met de lade op dit voorstel.
        self.assertIn(
            f"/artikel/{v.artikel_id}/change/?voorstel={v.pk}", self.als(self.anna).get("/beheer/").content.decode()
        )


class AfhandelenDienstTests(Basis):
    """De tweede laag: de dienst zelf, los van het scherm."""

    def test_zonder_bericht_kan_niet(self):
        v = self.voorstel()
        with self.assertRaises(diensten.VoorstelFout):
            diensten.voorstel_afhandelen(v, self.anna, VoorstelStatus.VERWERKT, "  ")

    def test_dubbel_uit_een_andere_omgeving_kan_niet(self):
        zuid = Artikel.objects.create(
            omgeving=self.zuid, titel="Z", samenvatting="z", inhoud="<p>z</p>", status=Status.GEPUBLICEERD, versie=1
        )
        with self.assertRaises(diensten.VoorstelFout):
            diensten.voorstel_afhandelen(
                self.voorstel(), self.anna, VoorstelStatus.AFGEWEZEN, "x", dubbel_van=self.voorstel(artikel=zuid)
            )


class CitaatTests(Basis):
    def test_citaat_in_de_tekst_gemarkeerd(self):
        html, gevonden = citaat_in_context("<p>Stap 1. Stuur na <b>twee</b> weken een rappel.</p>", "twee weken")
        self.assertTrue(gevonden)
        self.assertIn("<mark>twee weken</mark>", html)
        self.assertIn("Stuur na", html)

    def test_citaat_niet_meer_gevonden(self):
        self.assertEqual(citaat_in_context("<p>Andere tekst</p>", "twee weken"), ("", False))

    def test_geen_html_uit_het_artikel_of_het_citaat(self):
        html, gevonden = citaat_in_context("<p>a &lt;script&gt;x&lt;/script&gt; b</p>", "<script>x</script>")
        self.assertTrue(gevonden)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


class ArchiefZoekenTests(Basis):
    def test_zoeken_op_bericht_en_notitie(self):
        a = self.voorstel(tekst="Over termijnen")
        b = self.voorstel(tekst="Over formulieren")
        for v, tekst in ((a, "Afgehandeld met Toezicht"), (b, "Nee")):
            diensten.voorstel_afhandelen(v, self.anna, VoorstelStatus.VERWERKT, tekst)
        diensten.notitie_toevoegen(b, self.anna, "zie ook zaak 2026-17")
        c = self.als(self.anna)
        ids = lambda q: {
            r["v"].pk for r in c.get(f"/beheer/?bak=afgehandeld&q={q}").context["werkplek"]["inhoud"]["rijen"]
        }  # noqa: E731
        self.assertEqual(ids("toezicht"), {a.pk})
        self.assertEqual(ids("2026-17"), {b.pk})
        self.assertEqual(ids("formulier"), {b.pk})
        self.assertEqual(ids("niets-hiervan"), set())
        self.assertIn("Niets gevonden", c.get("/beheer/?bak=afgehandeld&q=niets-hiervan").content.decode())

    def test_zoeken_blijft_in_de_eigen_omgeving(self):
        zuid = Artikel.objects.create(
            omgeving=self.zuid,
            titel="Geheim",
            samenvatting="z",
            inhoud="<p>z</p>",
            status=Status.GEPUBLICEERD,
            versie=1,
        )
        v = self.voorstel(artikel=zuid, door=self.zoe)
        diensten.voorstel_afhandelen(v, self.zoe, VoorstelStatus.VERWERKT, "Klaar")
        rijen = self.als(self.anna).get("/beheer/?bak=afgehandeld&q=Geheim").context["werkplek"]["inhoud"]["rijen"]
        self.assertEqual(rijen, [])


class ArchiverenTests(Basis):
    @override_settings(KB_EMAIL_AAN=True)
    def test_archiveren_sluit_open_voorstellen_af(self):
        open_ = self.voorstel()
        klaar = self.voorstel(door=self.piet)
        diensten.voorstel_afhandelen(klaar, self.anna, VoorstelStatus.VERWERKT, "Klaar")
        mail.outbox.clear()
        self.als(self.anna)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                "/beheer/kennisbank/artikel/", {"action": "archiveren", "_selected_action": [self.artikel.pk]}
            )
        open_.refresh_from_db()
        klaar.refresh_from_db()
        self.assertEqual(open_.status, VoorstelStatus.VERVALLEN)
        self.assertIn("is ingetrokken", open_.terugkoppeling)
        self.assertEqual(klaar.status, VoorstelStatus.VERWERKT, "afgehandeld blijft zoals het was")
        self.assertEqual([m.to for m in mail.outbox], [["lies@example.org"]])

    def test_opnieuw_opslaan_van_een_gearchiveerd_artikel_doet_niets_meer(self):
        self.artikel.status = Status.GEARCHIVEERD
        self.artikel.save()
        v = self.voorstel()  # (kan via de API niet meer, maar het model laat het toe)
        self.artikel.save()
        v.refresh_from_db()
        self.assertEqual(v.status, VoorstelStatus.NIEUW)

    def test_vervallen_in_de_lijst_van_de_indiener(self):
        v = self.voorstel()
        diensten.voorstellen_vervallen(self.artikel)
        rij = self.als(self.lies).get("/api/v1/voorstellen?lijst=mijn").json()[0]
        self.assertEqual((rij["id"], rij["status"]), (v.pk, "vervallen"))


@override_settings(KB_EMAIL_AAN=True)
class SamenvattingTests(Basis):
    def test_geen_mail_per_voorstel_meer(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.als(self.lies).post(
                "/api/v1/voorstellen",
                {"artikel": self.artikel.pk, "tekst": "Graag aanvullen"},
                content_type="application/json",
            )
        self.assertEqual(mail.outbox, [])

    def test_een_mail_per_redacteur_met_de_nieuwe_voorstellen(self):
        self.voorstel(tekst="Eerste punt")
        self.voorstel(tekst="Tweede punt", door=self.piet)
        diensten.voorstel_naar_bak(self.voorstel(tekst="Derde"), self.bram, self.anna)
        mail.outbox.clear()
        self.assertEqual(diensten.verstuur_voorstellenmail(), 2)
        per = {m.to[0]: m for m in mail.outbox}
        self.assertEqual(set(per), {"anna@example.org", "bram@example.org"}, "niet aan Zuid of aan lezers")
        self.assertIn("3 nieuwe verbetervoorstellen", per["anna@example.org"].body)
        self.assertIn("Eerste punt", per["anna@example.org"].body)
        self.assertIn(
            "In jouw bak liggen 1 open voorstel(len), waarvan 1 nog niet geopend", per["anna@example.org"].body
        )
        self.assertNotIn("In jouw bak", per["bram@example.org"].body)

    def test_niets_nieuw_geen_mail_en_niet_dubbel(self):
        self.voorstel()
        self.assertEqual(diensten.verstuur_voorstellenmail(), 2)
        self.assertEqual(diensten.verstuur_voorstellenmail(), 0)
        self.assertTrue(Systeemstand.objects.filter(sleutel="voorstellenmail").exists())

    def test_opschonen_verstuurt_de_samenvatting(self):
        self.voorstel()
        call_command("kennisbank_opschonen", stdout=open("/dev/null", "w"))
        self.assertEqual(len([m for m in mail.outbox if "verbetervoorstel" in m.subject]), 2)


class KeuzevakVertaaldTests(Basis):
    def test_dubbel_keuzevak_spreekt_nederlands(self):
        """Bij zaaktypen stond 'Choose all zaaktypen': Django 5.2 vertaalt dat niet (kennisbank/locale)."""
        js = self.als(self.anna).get("/beheer/jsi18n/").content.decode()
        self.assertIn("Alle %s kiezen", js)
        self.assertIn("Alle %s verwijderen", js)
