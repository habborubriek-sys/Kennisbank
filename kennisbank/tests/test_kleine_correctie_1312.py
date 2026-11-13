"""1.31.2: een kleine correctie neemt voorstellen mee (K1), en *Afhandelen als verwerkt* in de lade (K2).

Bouwlijst `bouwlijst-1.31.2-kleine-correctie-en-afhandelen.md`. Aanleiding: Alex publiceerde een tikfout
als kleine correctie met het voorstel aangevinkt, en het scherm *Meegenomen voorstellen afhandelen* kwam niet.
"""

from django.contrib.admin.models import LogEntry
from django.contrib.messages import get_messages
from django.core import mail
from django.test import override_settings

from kennisbank import diensten, review
from kennisbank.models import (
    ArtikelVersie,
    Favoriet,
    FavorietenMail,
    Status,
    Verbetervoorstel,
    VoorstelStatus,
)
from kennisbank.tests.test_ronde_a_1280 import RondeABasis
from kennisbank.tests.test_voorstellen_lade_1260 import lade_van


def meldingen(r):
    return " | ".join(str(m) for m in get_messages(r.wsgi_request))


# --- K1: een kleine correctie neemt aangevinkte voorstellen mee ---------------------------------------------


class KleineCorrectieNeemtMee(RondeABasis):
    def test_k1_gewone_weg_aangevinkt_in_de_lade(self):
        """Wat Alex deed: tekst aanpassen, voorstel aanvinken, publiceren als kleine correctie."""
        v = self.voorstel()
        r = self.publiceer(
            [v],
            [v],
            [],
            inhoud="<p>Stuur na drie weken een rappel.</p>",
            kleine_correctie="on",
            wijzigingstoelichting="",
        )
        self.assertEqual(r.status_code, 302)
        self.assertIn("voorstellen-afhandelen", r["Location"])
        v.refresh_from_db()
        self.assertEqual((v.in_conceptversie, v.verwerkt_in_versie, v.is_open), (False, 2, True))
        self.assertEqual(v.eigenaar, self.anna)
        self.assertTrue(ArtikelVersie.objects.get(artikel=self.a, versie=2).kleine_correctie)
        self.assertNotIn("niet als verwerkt", meldingen(r))

    def test_k1_het_afhandelscherm_toont_het_voorgevulde_bericht(self):
        v = self.voorstel()
        r = self.publiceer([v], [v], [], kleine_correctie="on", wijzigingstoelichting="")
        html = self.client.get(r["Location"]).content.decode()
        self.assertIn("We hebben het verwerkt in versie 2", html)
        self.assertIn(f'name="bericht-{v.pk}"', html)

    def test_k1_medewerkers_krijgen_geen_mail_en_geen_melding(self):
        Favoriet.objects.create(gebruiker=self.lies, artikel=self.a)
        v = self.voorstel()
        self.publiceer([v], [v], [], kleine_correctie="on", wijzigingstoelichting="")
        self.assertFalse(FavorietenMail.objects.filter(artikel=self.a).exists())
        self.assertEqual(diensten.wijzigingen_voor(self.lies, [self.a]), {})

    def test_k1_spoedcorrectie_als_kleine_correctie(self):
        v = self.voorstel()
        self.client.force_login(self.anna)
        data = self.beheerdata_spoed(v, inhoud="<p>Stuur na twee weken een rappel!</p>", kleine_correctie="on")
        r = self.post(f"{self.url}?spoed=1", data, _save="1")
        self.assertIn("voorstellen-afhandelen", r["Location"])
        v.refresh_from_db()
        self.assertEqual(v.verwerkt_in_versie, 2)

    def test_k1_zonder_nieuwe_versie_telt_het_nog_steeds_niet(self):
        v = self.voorstel()
        self.a.refresh_from_db()
        r = self.publiceer(
            [v],
            [v],
            [],
            inhoud=self.a.inhoud,
            clusters=[self.water.pk],
            kleine_correctie="on",
            wijzigingstoelichting="",
        )
        self.assertFalse(ArtikelVersie.objects.filter(artikel=self.a, versie=2).exists())
        self.assertNotIn("voorstellen-afhandelen", r.get("Location", ""))
        v.refresh_from_db()
        self.assertIsNone(v.verwerkt_in_versie)
        self.assertTrue(v.is_open)
        self.assertIn("geen inhoudelijke wijziging", meldingen(r))

    def test_k1_niet_aangevinkt_blijft_gewoon_open(self):
        v = self.voorstel()
        r = self.publiceer([v], [], [], kleine_correctie="on", wijzigingstoelichting="")
        self.assertNotIn("voorstellen-afhandelen", r.get("Location", ""))
        v.refresh_from_db()
        self.assertEqual((v.in_conceptversie, v.verwerkt_in_versie), (False, None))

    def beheerdata_spoed(self, v, **velden):
        from kennisbank.tests.test_kennisbank import beheerdata

        data = beheerdata(self.a, **velden)
        data.update(kb_lade=str(v.pk), kb_meenemen=str(v.pk), kb_mee_geladen="")
        return data


# --- K2: Afhandelen als verwerkt in de lade ---------------------------------------------------------------


class AfhandelenAlsVerwerkt(RondeABasis):
    def tekst_aangepast(self):
        """De tekst is al aangepast in een gepubliceerde versie, zonder dat het voorstel is meegenomen."""
        self.publiceer(inhoud="<p>Stuur na drie weken een rappel.</p>", kleine_correctie="on", wijzigingstoelichting="")
        self.a.refresh_from_db()
        self.assertEqual(self.a.versie, 2)

    def verwerkt(self, v, tekst="Dank je wel, het is verwerkt.", **extra):
        self.client.force_login(extra.pop("wie", self.anna))
        return self.actie(v, actie="verwerkt", tekst=tekst, **extra)

    def test_k2_de_lade_krijgt_de_versie_en_het_voorgevulde_bericht(self):
        v = self.voorstel()
        self.tekst_aangepast()
        self.client.force_login(self.anna)
        item = lade_van(self.client.get(self.url).content.decode())["voorstellen"][0]
        self.assertEqual(item["id"], v.pk)
        self.assertEqual(item["verwerkt_versie"], 2)
        self.assertIn("verwerkt in versie 2 van 'Rappel versturen'", item["verwerkt_bericht"])
        self.assertFalse(item["citaat_gepubliceerd"], "'twee weken' staat niet meer in de gepubliceerde tekst")

    @override_settings(KB_EMAIL_AAN=True)
    def test_k2_afhandelen_zet_verwerkt_met_de_huidige_versie(self):
        v = self.voorstel()
        self.tekst_aangepast()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            r = self.verwerkt(v)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["weg"])
        self.assertIn("verwerkt in versie 2", r.json()["melding"])
        v.refresh_from_db()
        self.assertEqual(v.status, VoorstelStatus.VERWERKT)
        self.assertEqual(v.verwerkt_in_versie, 2)
        self.assertEqual(v.behandeld_door, self.anna)
        self.assertEqual(v.eigenaar, self.anna)
        # De indiener krijgt het bericht: bij het voorstel en per e-mail.
        self.assertEqual(v.berichten.get().tekst, "Dank je wel, het is verwerkt.")
        self.assertIn([self.lies.email], [m.to for m in mail.outbox])
        self.assertTrue(LogEntry.objects.filter(object_id=str(v.pk), change_message__contains="Verwerkt in versie 2"))

    def test_k2_het_bericht_is_verplicht(self):
        v = self.voorstel()
        self.tekst_aangepast()
        r = self.verwerkt(v, tekst="  ")
        self.assertEqual(r.status_code, 400)
        v.refresh_from_db()
        self.assertTrue(v.is_open)

    def test_k2_staat_het_citaat_er_nog_dan_eerst_bevestigen(self):
        v = self.voorstel()  # het citaat 'twee weken' staat nog in versie 1
        self.client.force_login(self.anna)
        item = lade_van(self.client.get(self.url).content.decode())["voorstellen"][0]
        self.assertTrue(item["citaat_gepubliceerd"])
        r = self.verwerkt(v)
        self.assertEqual(r.status_code, 409)
        self.assertIn("staat nog letterlijk", r.json()["fout"])
        self.assertTrue(r.json()["voorstel"]["citaat_gepubliceerd"], "de lade krijgt de stand en kan het vragen")
        v.refresh_from_db()
        self.assertTrue(v.is_open)
        self.assertEqual(v.berichten.count(), 0, "er is niets verstuurd")
        r = self.verwerkt(v, zeker="1")
        self.assertEqual(r.status_code, 200)
        v.refresh_from_db()
        self.assertEqual((v.status, v.verwerkt_in_versie), (VoorstelStatus.VERWERKT, 1))

    def test_k2_het_citaat_wordt_in_de_gepubliceerde_tekst_gezocht_niet_in_de_conceptversie(self):
        v = self.voorstel()
        self.maak_concept()  # in de conceptversie staat 'drie weken'; medewerkers zien nog 'twee weken'
        self.client.force_login(self.anna)
        item = lade_van(self.client.get(self.url).content.decode())["voorstellen"][0]
        self.assertTrue(item["citaat_gepubliceerd"])
        self.assertEqual(self.verwerkt(v).status_code, 409)

    def test_k2_zonder_citaat_geen_vraag(self):
        v = self.voorstel(citaat="")
        r = self.verwerkt(v)
        self.assertEqual(r.status_code, 200)
        v.refresh_from_db()
        self.assertEqual(v.status, VoorstelStatus.VERWERKT)

    def test_k2_op_slot_tijdens_de_review(self):
        v = self.voorstel()
        self.maak_concept()
        self.mee(v)
        self.ter_inzage()
        self.assertTrue(review.op_slot(self.a.pk))
        # Ook zonder bevestiging gaat het slot voor: eerst vragen of je het zeker weet, heeft dan geen zin.
        self.assertIn("ter inzage", self.verwerkt(v).json()["fout"])
        r = self.verwerkt(v, zeker="1")
        self.assertEqual(r.status_code, 409)
        self.assertIn("ter inzage", r.json()["fout"])
        v.refresh_from_db()
        self.assertTrue(v.is_open)
        self.assertIsNone(v.verwerkt_in_versie)
        self.assertEqual(v.berichten.count(), 0)

    def test_k2_een_ander_voorstel_bij_een_artikel_ter_inzage_kan_wel(self):
        v = self.voorstel(citaat="")
        self.maak_concept()
        self.ter_inzage()
        self.assertEqual(self.verwerkt(v).status_code, 200)

    def test_k2_409_als_het_intussen_bij_een_collega_ligt(self):
        v = self.voorstel()
        self.tekst_aangepast()
        diensten.voorstel_naar_bak(v, self.bram, self.bram)
        r = self.verwerkt(v, geladen_bericht="0", geladen_eigenaar="0")
        self.assertEqual(r.status_code, 409)
        self.assertIn("ligt intussen bij Bram", r.json()["fout"])
        v.refresh_from_db()
        self.assertTrue(v.is_open)

    def test_k2_409_als_een_collega_intussen_een_bericht_stuurde(self):
        v = self.voorstel()
        self.tekst_aangepast()
        diensten.voorstelbericht_toevoegen(v, self.bram, "Ik pak dit op.", van_redactie=True, melden=False)
        r = self.verwerkt(v, geladen_bericht="0", geladen_eigenaar="0")
        self.assertEqual(r.status_code, 409)
        self.assertIn("Bram stuurde intussen", r.json()["fout"])
        v.refresh_from_db()
        self.assertTrue(v.is_open)

    def test_k2_al_afgehandeld_door_een_collega(self):
        v = self.voorstel()
        self.tekst_aangepast()
        diensten.voorstel_afhandelen(v, self.bram, VoorstelStatus.AFGEWEZEN, "Nee")
        r = self.verwerkt(v)
        self.assertEqual(r.status_code, 409)
        v.refresh_from_db()
        self.assertEqual(v.status, VoorstelStatus.AFGEWEZEN)

    def test_k2_niet_bij_een_artikel_dat_niet_gepubliceerd_is(self):
        v = self.voorstel(citaat="")
        type(self.a).objects.filter(pk=self.a.pk).update(status=Status.CONCEPT)
        self.client.force_login(self.anna)
        r = self.verwerkt(v)
        self.assertEqual(r.status_code, 409)
        self.assertIn("niet gepubliceerd", r.json()["fout"])
        v.refresh_from_db()
        self.assertTrue(v.is_open)

    def test_k2_een_al_meegenomen_versie_blijft_staan(self):
        """Het scherm na publiceren is overgeslagen: het voorstel houdt de versie waarin het is verwerkt."""
        v = self.voorstel()
        r = self.publiceer([v], [v], [], kleine_correctie="on", wijzigingstoelichting="")
        self.assertIn("voorstellen-afhandelen", r["Location"])
        self.a.refresh_from_db()  # het formulier stuurt de stand van het artikel mee
        self.publiceer(inhoud="<p>Stuur na vier weken een rappel.</p>")  # versie 3, zonder het voorstel
        self.a.refresh_from_db()
        self.assertEqual(self.a.versie, 3)
        v.refresh_from_db()
        self.assertEqual(v.verwerkt_in_versie, 2)
        self.assertEqual(self.verwerkt(v).status_code, 200)
        v.refresh_from_db()
        self.assertEqual((v.status, v.verwerkt_in_versie), (VoorstelStatus.VERWERKT, 2))

    def test_k2_alleen_voor_de_redactie_van_die_omgeving(self):
        v = self.voorstel(citaat="")
        r = self.verwerkt(v, wie=self.zoe)
        self.assertEqual(r.status_code, 404)
        r = self.verwerkt(v, wie=self.lies)
        self.assertIn(r.status_code, (302, 403, 404))
        v.refresh_from_db()
        self.assertTrue(v.is_open)

    def test_k2_afgehandeld_is_definitief(self):
        v = self.voorstel(citaat="")
        self.assertEqual(self.verwerkt(v).status_code, 200)
        r = self.verwerkt(v)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(Verbetervoorstel.objects.get(pk=v.pk).berichten.count(), 1)
