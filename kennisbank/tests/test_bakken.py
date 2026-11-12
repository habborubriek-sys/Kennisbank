"""Ronde 1.15.0: bakken voor verbetervoorstellen, steun van collega's, de startpagina van het beheer
en de Nederlandse foutpagina's (S8).

Opzet: twee omgevingen (Noord en Zuid). In Noord twee redacteuren (Anna en Bram) en twee lezers; in Zuid
één redacteur. Zuid mag niets van Noord zien, ook niet via de nieuwe routes.
"""

from urllib.parse import urlencode

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from kennisbank import diensten, views
from kennisbank.models import (
    Artikel,
    Omgeving,
    Rol,
    Status,
    Steun,
    Toegang,
    Verbetervoorstel,
    VoorstelStatus,
)

User = get_user_model()
LIJST = "/beheer/kennisbank/verbetervoorstel/"


def wijzig_url(v):
    return f"{LIJST}{v.pk}/change/"


class Basis(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.noord = Omgeving.objects.create(slug="noord", naam="Noord")
        cls.zuid = Omgeving.objects.create(slug="zuid", naam="Zuid")
        g_red = Group.objects.create(name="noord-redactie")
        g_lez = Group.objects.create(name="noord-lezers")
        g_zuid = Group.objects.create(name="zuid-redactie")
        Toegang.objects.create(omgeving=cls.noord, groep=g_red, rol=Rol.REDACTEUR)
        Toegang.objects.create(omgeving=cls.noord, groep=g_lez, rol=Rol.LEZER)
        Toegang.objects.create(omgeving=cls.zuid, groep=g_zuid, rol=Rol.REDACTEUR)

        def maak(naam, groep, staf=False):
            u = User.objects.create_user(naam, email=f"{naam}@example.org", password="x", first_name=naam.title())
            u.groups.add(groep)
            if staf:
                u.is_staff = True
                u.save()
            return u

        cls.anna = maak("anna", g_red, staf=True)
        cls.bram = maak("bram", g_red, staf=True)
        cls.lies = maak("lies", g_lez)
        cls.piet = maak("piet", g_lez)
        cls.zoe = maak("zoe", g_zuid, staf=True)

        cls.artikel = Artikel.objects.create(
            omgeving=cls.noord,
            titel="Rappel",
            samenvatting="Over rappels",
            inhoud="<p>x</p>",
            status=Status.GEPUBLICEERD,
            versie=1,
        )
        cls.concept = Artikel.objects.create(
            omgeving=cls.noord,
            titel="Concept",
            samenvatting="Nog niet af",
            inhoud="<p>x</p>",
            status=Status.CONCEPT,
        )
        cls.artikel_zuid = Artikel.objects.create(
            omgeving=cls.zuid,
            titel="Zuidelijk",
            samenvatting="Van Zuid",
            inhoud="<p>x</p>",
            status=Status.GEPUBLICEERD,
            versie=1,
        )

    def voorstel(self, door=None, artikel=None, **kw):
        return Verbetervoorstel.objects.create(
            artikel=artikel or self.artikel,
            artikel_versie=1,
            tekst=kw.pop("tekst", "Termijn klopt niet"),
            ingediend_door=door or self.lies,
            **kw,
        )

    def als(self, u):
        self.client.force_login(u)
        return self.client


class BakkenDienstTests(Basis):
    def test_nieuw_voorstel_ligt_in_de_gezamenlijke_bak(self):
        r = self.als(self.lies).post(
            "/api/v1/voorstellen", {"artikel": self.artikel.pk, "tekst": "Nieuw"}, content_type="application/json"
        )
        self.assertEqual(r.status_code, 201)
        v = Verbetervoorstel.objects.get(pk=r.json()["id"])
        self.assertIsNone(v.eigenaar)
        self.assertEqual(v.status, VoorstelStatus.NIEUW)

    @override_settings(KB_EMAIL_AAN=True)
    def test_oppakken_zet_in_behandeling_zonder_mail(self):
        v = self.voorstel()
        with self.captureOnCommitCallbacks(execute=True):
            v = diensten.voorstel_naar_bak(v, self.anna, self.anna)
        self.assertEqual(v.eigenaar, self.anna)
        self.assertEqual(v.status, VoorstelStatus.IN_BEHANDELING)
        self.assertIsNotNone(v.eigenaar_gezien_op, "wie zelf oppakt, heeft het al gezien")
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(KB_EMAIL_AAN=True)
    def test_toewijzen_aan_collega_stuurt_hem_een_mail(self):
        v = self.voorstel()
        with self.captureOnCommitCallbacks(execute=True):
            v = diensten.voorstel_naar_bak(v, self.anna, self.bram)
        self.assertEqual(v.eigenaar, self.bram)
        self.assertIsNone(v.eigenaar_gezien_op, "voor Bram is het nieuw in zijn bak")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["bram@example.org"])
        self.assertIn("Anna", mail.outbox[0].body)
        self.assertIn(f"/beheer/voorstel/{v.pk}/", mail.outbox[0].body)

    def test_toewijzen_aan_iemand_buiten_de_redactie_kan_niet(self):
        v = self.voorstel()
        for wie in (self.piet, self.zoe):  # lezer van Noord, redacteur van Zuid
            with self.assertRaises(diensten.VoorstelFout):
                diensten.voorstel_naar_bak(v, self.anna, wie)
        v.refresh_from_db()
        self.assertIsNone(v.eigenaar)

    def test_terugleggen_zonder_bericht_zet_terug_op_nieuw(self):
        v = diensten.voorstel_naar_bak(self.voorstel(), self.anna, self.anna)
        v = diensten.voorstel_naar_bak(v, self.anna, None)
        self.assertIsNone(v.eigenaar)
        self.assertEqual(v.status, VoorstelStatus.NIEUW)
        self.assertIsNone(v.behandeld_door)

    def test_terugleggen_na_een_bericht_blijft_in_behandeling(self):
        v = diensten.voorstel_naar_bak(self.voorstel(), self.anna, self.anna)
        diensten.voorstelbericht_toevoegen(v, self.anna, "We kijken ernaar", van_redactie=True, melden=False)
        v = diensten.voorstel_naar_bak(v, self.anna, None)
        self.assertIsNone(v.eigenaar)
        self.assertEqual(v.status, VoorstelStatus.IN_BEHANDELING)

    def test_afgehandeld_voorstel_blijft_waar_het_is(self):
        v = self.voorstel(status=VoorstelStatus.VERWERKT, eigenaar=self.anna)
        with self.assertRaises(diensten.VoorstelFout):
            diensten.voorstel_naar_bak(v, self.anna, None)
        with self.assertRaises(diensten.VoorstelFout):
            diensten.voorstel_naar_bak(v, self.anna, self.bram)

    def test_api_statuswijziging_neemt_het_voorstel_in_de_eigen_bak(self):
        v = self.voorstel()
        r = self.als(self.anna).patch(
            f"/api/v1/voorstellen/{v.pk}",
            {"status": "verwerkt", "terugkoppeling": "Aangepast."},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        v.refresh_from_db()
        self.assertEqual(v.eigenaar, self.anna, "een afgehandeld voorstel mag niet eigenaarloos blijven")


class BakkenBeheerTests(Basis):
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
        }
        # Verstuurd zoals een browser het doet.
        return self.client.post(wijzig_url(v), urlencode(data), content_type="application/x-www-form-urlencoded")

    def test_oud_beheerformulier_verwerkt_niets_voor_een_open_voorstel(self):
        # Ronde A (review 1.27.0, M1): het oude formulier omzeilde de regels van de lade. Voor een open
        # voorstel verandert het niets meer; je gaat naar de editor.
        v = self.voorstel()
        self.als(self.anna)
        r = self.post_formulier(v, naar_bak=str(self.bram.pk), status="afgewezen", bericht="Staat al zo in de wet.")
        self.assertEqual(r["Location"], f"/beheer/kennisbank/artikel/{v.artikel_id}/change/?voorstel={v.pk}")
        v.refresh_from_db()
        self.assertEqual((v.eigenaar, v.status), (None, VoorstelStatus.NIEUW))
        self.assertFalse(v.berichten.exists())

    def test_keuzelijst_bevat_alleen_redacteuren_van_de_omgeving(self):
        # Sinds 1.26.0 wijs je toe in de werkbak (de selectiebalk).
        self.voorstel()
        html = self.als(self.anna).get("/beheer/?bak=algemeen").content.decode()
        sel = html[html.index('id="kb-sel-naar"') : html.index("</select>", html.index('id="kb-sel-naar"'))]
        self.assertIn("Bram", sel)
        html = sel
        self.assertNotIn(">Zoe<", html)
        self.assertNotIn(">Piet<", html)

    def test_overnemen_uit_de_bak_van_een_collega_wordt_vastgelegd(self):
        v = diensten.voorstel_naar_bak(self.voorstel(), self.bram, self.bram)
        r = self.als(self.anna).post(LIJST, {"action": "oppakken", "_selected_action": [v.pk]})
        self.assertEqual(r.status_code, 302)
        v.refresh_from_db()
        self.assertEqual(v.eigenaar, self.anna)
        log = LogEntry.objects.filter(object_id=str(v.pk)).latest("action_time")
        self.assertIn("Overgenomen uit de bak van Bram", log.get_change_message())

    def test_terugleggen_via_de_lijst(self):
        v = diensten.voorstel_naar_bak(self.voorstel(), self.anna, self.anna)
        self.als(self.anna).post(LIJST, {"action": "terugleggen", "_selected_action": [v.pk]})
        v.refresh_from_db()
        self.assertIsNone(v.eigenaar)
        self.assertEqual(v.status, VoorstelStatus.NIEUW)

    def test_bakfilter(self):
        gezamenlijk = self.voorstel(tekst="gezamenlijk")
        mijn = diensten.voorstel_naar_bak(self.voorstel(tekst="mijn"), self.anna, self.anna)
        van_bram = diensten.voorstel_naar_bak(self.voorstel(tekst="bram"), self.bram, self.bram)
        c = self.als(self.anna)

        def ids(param):
            return {v.pk for v in c.get(LIJST + "?bak=" + param).context["cl"].result_list}

        self.assertEqual(ids("gezamenlijk"), {gezamenlijk.pk})
        self.assertEqual(ids("mijn"), {mijn.pk})
        self.assertEqual(ids(f"u{self.bram.pk}"), {van_bram.pk})
        self.assertIn("Bak van Bram", c.get(LIJST).content.decode())

    def test_openen_door_de_eigenaar_haalt_het_nieuw_label_weg(self):
        v = diensten.voorstel_naar_bak(self.voorstel(), self.anna, self.bram)
        self.assertIn("nog niet geopend", self.als(self.anna).get(LIJST).content.decode())
        self.als(self.anna).get(wijzig_url(v), follow=True)  # Anna is niet de eigenaar: verandert niets
        v.refresh_from_db()
        self.assertIsNone(v.eigenaar_gezien_op)
        self.als(self.bram).get(wijzig_url(v), follow=True)
        v.refresh_from_db()
        self.assertIsNotNone(v.eigenaar_gezien_op)

    def test_redactie_ziet_wie_steunt(self):
        v = self.voorstel()
        diensten.steun_geven(v, self.piet)
        # Sinds 1.26.0 in de lade van het bewerkscherm: de namen staan in de gegevens van de lade.
        html = self.als(self.anna).get(wijzig_url(v), follow=True).content.decode()
        self.assertIn('"steuners": ["Piet', html)

    def test_redacteur_van_zuid_ziet_niets_van_noord(self):
        v = self.voorstel()
        self.assertEqual(self.als(self.zoe).get(wijzig_url(v)).status_code, 302)  # admin: niet gevonden
        self.assertNotIn("Termijn klopt niet", self.als(self.zoe).get(LIJST).content.decode())


class WerkplekTests(Basis):
    """De startpagina van het beheer: links de bakken, rechts de inhoud."""

    def werkplek(self, wie, bak=""):
        r = self.als(wie).get("/beheer/" + (f"?bak={bak}" if bak else ""))
        self.assertEqual(r.status_code, 200)
        return r

    def test_kolom_toont_werkvoorraad_en_alle_procesmanagers_met_aantallen(self):
        self.voorstel()
        diensten.voorstel_naar_bak(self.voorstel(), self.anna, self.anna)
        diensten.voorstel_naar_bak(self.voorstel(), self.bram, self.bram)
        diensten.voorstel_naar_bak(self.voorstel(), self.bram, self.bram)
        m = self.werkplek(self.anna).context["werkplek"]["menu"]
        self.assertEqual([(b["naam"], b["aantal"]) for b in m["bakken"]], [("Algemeen", 1)])
        personen = [(p["naam"], p["aantal"], p["ik"]) for p in m["personen"]]
        self.assertEqual(personen, [("Anna", 1, True), ("Bram", 2, False)])
        artikelkant = {b["sleutel"]: b["aantal"] for b in m["artikelkant"]}
        self.assertEqual(artikelkant, {"concepten": 1, "kladversies": 0, "nakijken": 0})

    def test_procesmanager_met_lege_bak_staat_er_ook(self):
        m = self.werkplek(self.anna).context["werkplek"]["menu"]
        self.assertEqual([p["naam"] for p in m["personen"]], ["Anna", "Bram"])

    def test_bak_aanklikken_toont_de_inhoud(self):
        v = diensten.voorstel_naar_bak(self.voorstel(tekst="Bij Bram"), self.bram, self.bram)
        self.voorstel(tekst="In de werkvoorraad")
        r = self.werkplek(self.anna, f"u{self.bram.pk}")
        self.assertEqual([x["v"].pk for x in r.context["werkplek"]["inhoud"]["rijen"]], [v.pk])
        html = r.content.decode()
        self.assertIn("Bak van Bram", html)
        # Sinds 1.26.0 een rustige lijst: een regel die de editor opent, en de selectiebalk erboven.
        self.assertIn(f"?voorstel={v.pk}", html)
        self.assertIn('id="kb-selectie"', html)
        self.assertNotIn("Overnemen", html)
        r = self.werkplek(self.anna)  # standaard: de werkvoorraad
        self.assertEqual([x["v"].tekst for x in r.context["werkplek"]["inhoud"]["rijen"]], ["In de werkvoorraad"])

    def test_afgehandeld_is_het_archief(self):
        self.voorstel(tekst="klaar", status=VoorstelStatus.VERWERKT, eigenaar=self.anna)
        self.voorstel(tekst="open")
        r = self.werkplek(self.anna, "afgehandeld")
        self.assertEqual([x["v"].tekst for x in r.context["werkplek"]["inhoud"]["rijen"]], ["klaar"])
        self.assertNotIn("Toewijzen", r.content.decode(), "een afgehandeld voorstel verplaats je niet meer")

    def test_artikelkant(self):
        r = self.werkplek(self.anna, "concepten")
        self.assertEqual([a["titel"] for a in r.context["werkplek"]["inhoud"]["artikelen"]], ["Concept"])
        verleden = timezone.localdate() - timezone.timedelta(days=3)
        Artikel.objects.filter(pk=self.artikel.pk).update(herzien_voor=verleden)
        r = self.werkplek(self.anna, "nakijken")
        self.assertEqual([a["titel"] for a in r.context["werkplek"]["inhoud"]["artikelen"]], ["Rappel"])
        self.werkplek(self.anna, "kladversies")
        r = self.werkplek(self.anna, "alles")
        self.assertIn("Artikelen", r.content.decode())

    def test_oude_voorstellenlijst_staat_niet_meer_bij_alle_onderdelen(self):
        html = self.werkplek(self.anna, "alles").content.decode()
        self.assertNotIn('href="/beheer/kennisbank/verbetervoorstel/"', html)

    def test_acties_vanuit_de_werkplek(self):
        v = self.voorstel()
        c = self.als(self.anna)
        r = c.post("/beheer/werkplek/actie/", {"voorstel": v.pk, "actie": "oppakken", "terug": "werkvoorraad"})
        self.assertRedirects(r, "/beheer/?bak=werkvoorraad", fetch_redirect_response=False)
        v.refresh_from_db()
        self.assertEqual(v.eigenaar, self.anna)
        c.post("/beheer/werkplek/actie/", {"voorstel": v.pk, "actie": "toewijzen", "naar": self.bram.pk})
        v.refresh_from_db()
        self.assertEqual(v.eigenaar, self.bram)
        c.post("/beheer/werkplek/actie/", {"voorstel": v.pk, "actie": "oppakken"})  # overnemen
        v.refresh_from_db()
        self.assertEqual(v.eigenaar, self.anna)
        log = LogEntry.objects.filter(object_id=str(v.pk)).latest("action_time")
        self.assertIn("Overgenomen uit de bak van Bram", log.get_change_message())
        c.post("/beheer/werkplek/actie/", {"voorstel": v.pk, "actie": "terugleggen"})
        v.refresh_from_db()
        self.assertIsNone(v.eigenaar)

    def test_toewijzen_aan_iemand_van_buiten_kan_niet(self):
        v = self.voorstel()
        data = {"voorstel": v.pk, "actie": "toewijzen", "naar": self.zoe.pk}
        self.als(self.anna).post("/beheer/werkplek/actie/", data)
        v.refresh_from_db()
        self.assertIsNone(v.eigenaar)

    def test_redacteur_van_zuid_ziet_en_raakt_niets_van_noord(self):
        v = self.voorstel()
        m = self.werkplek(self.zoe).context["werkplek"]["menu"]
        self.assertEqual([(b["naam"], b["aantal"]) for b in m["bakken"]], [("Algemeen", 0)])
        self.assertEqual([p["naam"] for p in m["personen"]], ["Zoe"])
        self.assertEqual(self.als(self.zoe).get(f"/beheer/?bak=u{self.anna.pk}").status_code, 404)
        r = self.als(self.zoe).post("/beheer/werkplek/actie/", {"voorstel": v.pk, "actie": "oppakken"})
        self.assertEqual(r.status_code, 404)
        v.refresh_from_db()
        self.assertIsNone(v.eigenaar)

    def test_medewerker_komt_niet_op_de_werkplek(self):
        r = self.als(self.lies).get("/beheer/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("login", r["Location"])

    def test_aantal_databasevragen_groeit_niet_mee(self):
        c = self.als(self.anna)

        def tel(bak):
            c.get("/beheer/?bak=" + bak)
            with CaptureQueriesContext(connection) as q:
                self.assertEqual(c.get("/beheer/?bak=" + bak).status_code, 200)
            return len(q)

        bakken = ["werkvoorraad", f"u{self.anna.pk}", "afgehandeld", "concepten"]
        # Elke bak begint met één regel: een lege lijst kost geen databasevraag, en dat is niet wat we meten.
        self.voorstel(tekst="eerste")
        diensten.voorstel_naar_bak(self.voorstel(tekst="mijn eerste"), self.anna, self.anna)
        self.voorstel(tekst="eerste klaar", status=VoorstelStatus.VERWERKT, eigenaar=self.anna)
        weinig = {b: tel(b) for b in bakken}
        for i in range(12):
            v = self.voorstel(tekst=f"v{i}")
            if i % 3:
                diensten.voorstel_naar_bak(v, self.anna, self.bram if i % 2 else self.anna)
            diensten.steun_geven(v, self.piet)
            Artikel.objects.create(omgeving=self.noord, titel=f"Concept {i}", samenvatting="x", inhoud="<p>x</p>")
        self.voorstel(tekst="klaar", status=VoorstelStatus.AFGEWEZEN, eigenaar=self.anna)
        self.assertEqual({b: tel(b) for b in bakken}, weinig)


class SteunTests(Basis):
    def steun(self, wie, v, methode="put"):
        return getattr(self.als(wie), methode)(f"/api/v1/voorstellen/{v.pk}/steun")

    def test_steunen_en_intrekken(self):
        v = self.voorstel()
        self.assertEqual(self.steun(self.piet, v).status_code, 204)
        self.assertEqual(self.steun(self.piet, v).status_code, 204, "twee keer klikken mag, het telt één keer")
        self.assertEqual(Steun.objects.filter(voorstel=v).count(), 1)
        self.assertEqual(self.steun(self.piet, v, "delete").status_code, 204)
        self.assertEqual(Steun.objects.filter(voorstel=v).count(), 0)

    def test_eigen_voorstel_steunen_kan_niet(self):
        r = self.steun(self.lies, self.voorstel())
        self.assertEqual(r.status_code, 409)
        self.assertIn("eigen voorstel", r.json()["detail"])

    def test_afgehandeld_voorstel_steunen_kan_niet(self):
        r = self.steun(self.piet, self.voorstel(status=VoorstelStatus.VERWERKT))
        self.assertEqual(r.status_code, 409)

    def test_voorstel_bij_een_artikel_dat_je_niet_mag_lezen_bestaat_niet(self):
        bij_concept = self.voorstel(artikel=self.concept, door=self.anna)
        bij_zuid = self.voorstel(artikel=self.artikel_zuid, door=self.zoe)
        self.assertEqual(self.steun(self.piet, bij_concept).status_code, 404)
        self.assertEqual(self.steun(self.piet, bij_zuid).status_code, 404)

    def test_lijst_van_collegas_is_anoniem_en_alleen_open(self):
        open_ = self.voorstel(tekst="Open punt")
        self.voorstel(tekst="Al klaar", status=VoorstelStatus.VERWERKT)
        self.voorstel(artikel=self.concept, tekst="Bij een concept")
        self.voorstel(artikel=self.artikel_zuid, door=self.zoe, tekst="Uit Zuid")
        diensten.steun_geven(open_, self.anna)
        r = self.als(self.piet).get("/api/v1/voorstellen?lijst=alle")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual([p["tekst"] for p in data], ["Open punt"])
        self.assertEqual(data[0]["steun"], 1)
        self.assertFalse(data[0]["ik_steun"])
        self.assertFalse(data[0]["van_mij"])
        tekst = r.content.decode()
        for naam in ("lies", "Lies", "anna", "Anna"):
            self.assertNotIn(naam, tekst, "collega's horen geen namen te zien")
        self.assertNotIn("berichten", data[0])

    def test_lijst_per_artikel(self):
        self.voorstel(tekst="Hier")
        ander = Artikel.objects.create(
            omgeving=self.noord,
            titel="Ander",
            samenvatting="x",
            inhoud="<p>x</p>",
            status=Status.GEPUBLICEERD,
            versie=1,
        )
        self.voorstel(artikel=ander, tekst="Daar")
        r = self.als(self.piet).get(f"/api/v1/voorstellen?lijst=alle&artikel={self.artikel.pk}")
        self.assertEqual([p["tekst"] for p in r.json()], ["Hier"])
        self.assertEqual(self.client.get("/api/v1/voorstellen?lijst=alle&artikel=x").status_code, 400)

    def test_mijn_voorstellen_voor_een_redacteur_alleen_zijn_eigen(self):
        self.voorstel(tekst="van Lies")
        self.voorstel(door=self.anna, tekst="van Anna")
        r = self.als(self.anna).get("/api/v1/voorstellen?lijst=mijn")
        self.assertEqual([p["tekst"] for p in r.json()], ["van Anna"])
        # Zonder 'lijst' blijft de API werken zoals hij deed: de redacteur ziet de hele omgeving.
        r = self.client.get("/api/v1/voorstellen")
        self.assertEqual({p["tekst"] for p in r.json()}, {"van Lies", "van Anna"})

    def test_indiener_ziet_hoeveel_steun_zijn_voorstel_heeft(self):
        v = self.voorstel()
        diensten.steun_geven(v, self.piet)
        r = self.als(self.lies).get("/api/v1/voorstellen?lijst=mijn")
        self.assertEqual(r.json()[0]["steun"], 1)

    def test_anonimisering_haalt_de_namen_weg_maar_houdt_het_aantal(self):
        v = self.voorstel()
        diensten.steun_geven(v, self.piet)
        Verbetervoorstel.objects.filter(pk=v.pk).update(
            status=VoorstelStatus.VERWERKT, behandeld_op=timezone.now() - timezone.timedelta(days=3650)
        )
        call_command("kennisbank_opschonen", stdout=open("/dev/null", "w"))  # noqa: SIM115
        self.assertEqual(Steun.objects.filter(voorstel=v).count(), 1)
        self.assertFalse(Steun.objects.filter(voorstel=v, gebruiker__isnull=False).exists())

    def test_lijst_van_collegas_doet_een_vast_aantal_vragen(self):
        c = self.als(self.piet)
        c.get("/api/v1/voorstellen?lijst=alle")

        def tel():
            with CaptureQueriesContext(connection) as q:
                c.get("/api/v1/voorstellen?lijst=alle")
            return len(q)

        weinig = tel()
        for i in range(10):
            diensten.steun_geven(self.voorstel(tekst=f"v{i}"), self.anna)
        self.assertEqual(tel(), weinig)


class FoutpaginaTests(Basis):
    def test_onbekend_adres_geeft_een_nederlandse_pagina(self):
        r = self.als(self.lies).get("/bestaat-niet/echt-niet")
        self.assertEqual(r.status_code, 404)
        html = r.content.decode()
        self.assertIn("Deze pagina bestaat niet", html)
        self.assertIn('href="/"', html)
        self.assertNotIn("Not Found", html)

    def test_onbekend_adres_in_het_beheer(self):
        r = self.als(self.anna).get("/beheer/kennisbank/bestaatniet/")
        self.assertIn(r.status_code, (302, 404))
        if r.status_code == 404:
            self.assertIn("Deze pagina bestaat niet", r.content.decode())

    def test_api_blijft_json(self):
        r = self.als(self.lies).get("/api/schema/bestaat-niet")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r["Content-Type"], "application/json")

    def test_serverfout(self):
        request = RequestFactory().get("/ergens")
        r = views.fout_500(request)
        self.assertEqual(r.status_code, 500)
        self.assertIn("Er ging iets mis", r.content.decode())

    @override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=1000)
    def test_te_groot_verzoek_geeft_een_nederlandse_400(self):
        c = self.als(self.anna)
        r = c.post(
            "/beheer/kennisbank/artikel/add/",
            urlencode({"titel": "x", "inhoud": "y" * 5000}),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("Dit verzoek kon niet worden verwerkt", r.content.decode())


class MigratieNaarBakkenTests(TransactionTestCase):
    """Bestaande voorstellen komen na de update in de bak van wie ze al had opgepakt."""

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_bestaande_voorstellen_krijgen_een_bak(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([("kennisbank", "0022_kladversie")])
        oud = executor.loader.project_state([("kennisbank", "0022_kladversie")]).apps
        Gebruiker = oud.get_model("auth", "User")
        Omg = oud.get_model("kennisbank", "Omgeving")
        A = oud.get_model("kennisbank", "Artikel")
        V = oud.get_model("kennisbank", "Verbetervoorstel")
        jan = Gebruiker.objects.create(username="jan")
        o = Omg.objects.create(slug="x", naam="X")
        a = A.objects.create(omgeving=o, slug="a", titel="A", samenvatting="x", versie=1)
        nu = timezone.now()
        nieuw = V.objects.create(artikel=a, artikel_versie=1, tekst="nieuw")
        bezig = V.objects.create(
            artikel=a, artikel_versie=1, tekst="bezig", status="in_behandeling", behandeld_door=jan, behandeld_op=nu
        )
        klaar = V.objects.create(
            artikel=a, artikel_versie=1, tekst="klaar", status="verwerkt", behandeld_door=jan, behandeld_op=nu
        )

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([("kennisbank", "0023_voorstel_bakken_en_steun")])
        nieuw_apps = executor.loader.project_state([("kennisbank", "0023_voorstel_bakken_en_steun")]).apps
        V2 = nieuw_apps.get_model("kennisbank", "Verbetervoorstel")
        self.assertIsNone(V2.objects.get(pk=nieuw.pk).eigenaar_id)
        self.assertEqual(V2.objects.get(pk=bezig.pk).eigenaar_id, jan.pk)
        self.assertEqual(V2.objects.get(pk=klaar.pk).eigenaar_id, jan.pk)
