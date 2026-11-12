"""1.26.0: verbetervoorstellen behandelen in de editor (ontwerp `ontwerp-voorstellen-in-editor.md`).

- de lade krijgt de open voorstellen bij het artikel mee;
- meenemen telt pas bij opslaan, en wie meeneemt wordt eigenaar (de vorige krijgt een e-mail);
- bij een spoedcorrectie hoort het meenemen bij de versie die dan wordt gepubliceerd;
- bericht, notitie, afwijzen, dubbel en verbergen gaan los van het artikel, meteen;
- een meegenomen voorstel kun je niet afwijzen zolang de versie ter inzage ligt;
- de werkbak is een lijst; toewijzen en verplaatsen via de selectiebalk;
- het oude behandelscherm verwijst een open voorstel door naar de editor.
"""

import json
import re

from django.core import mail
from django.test import override_settings

from kennisbank import diensten
from kennisbank.lade import titel_van
from kennisbank.models import Artikel, Conceptversie, Status, Verbetervoorstel, VoorstelStatus
from kennisbank.tests.test_kennisbank import beheerdata
from kennisbank.tests.test_review_c1 import ReviewBasis


def lade_van(html):
    m = re.search(r'<script id="kb-lade-gegevens" type="application/json">(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else None


class LadeBasis(ReviewBasis):
    def voorstel(self, tekst="De termijn klopt niet.", citaat="twee weken", **kw):
        return Verbetervoorstel.objects.create(
            artikel=self.a, artikel_versie=self.a.versie, tekst=tekst, citaat=citaat, ingediend_door=self.lies, **kw
        )

    def opslaan_als_concept(self, lade, mee, wie=None):
        self.client.force_login(wie or self.anna)
        data = beheerdata(self.a, wijzigingstoelichting="")
        c = Conceptversie.objects.filter(artikel=self.a).first()
        data["geladen_concept"] = c.stempel if c else ""
        data["kb_lade"] = ",".join(str(v.pk) for v in lade)
        data["kb_meenemen"] = ",".join(str(v.pk) for v in mee)
        return self.post(self.url, data, _conceptversie="1")

    def actie(self, v, **data):
        return self.client.post(f"/beheer/voorstel/{v.pk}/lade/", data)


class Gegevens(LadeBasis):
    def test_titel_is_de_eerste_zin_ingekort(self):
        self.assertEqual(
            titel_van("Spelfout: goedgekeurd met een d. Graag aanpassen."), "Spelfout: goedgekeurd met een d"
        )
        lang = titel_van("Dit is een heel lange eerste zin zonder punt die maar doorgaat en doorgaat en doorgaat")
        self.assertLessEqual(len(lang), 60)
        self.assertTrue(lang.endswith("…"))

    def test_de_lade_krijgt_de_open_voorstellen_mee(self):
        eerste = self.voorstel(tekst="Eerste.")
        tweede = self.voorstel(tekst="Tweede.")
        Verbetervoorstel.objects.create(
            artikel=self.a, artikel_versie=1, tekst="Klaar.", status=VoorstelStatus.AFGEWEZEN, ingediend_door=self.lies
        )
        self.client.force_login(self.anna)
        lade = lade_van(self.client.get(f"{self.url}?voorstel={tweede.pk}").content.decode())
        self.assertEqual([v["id"] for v in lade["voorstellen"]], [eerste.pk, tweede.pk])  # oudste eerst: vaste nummers
        self.assertEqual(lade["open"], tweede.pk)
        self.assertEqual(lade["voorstellen"][0]["indiener"], "Lies")
        self.assertFalse(lade["op_slot"])

    def test_geen_lade_voor_wie_niet_mag_redigeren(self):
        self.voorstel()
        self.client.force_login(self.zoe)
        r = self.client.get(self.url)
        self.assertIsNone(lade_van(r.content.decode()) if r.status_code == 200 else None)

    def test_openen_als_eigenaar_telt_als_gezien(self):
        v = diensten.voorstel_naar_bak(self.voorstel(), self.bram, self.bram)
        Verbetervoorstel.objects.filter(pk=v.pk).update(eigenaar_gezien_op=None)
        self.client.force_login(self.anna)
        self.client.get(f"{self.url}?voorstel={v.pk}")
        v.refresh_from_db()
        self.assertIsNone(v.eigenaar_gezien_op)  # Anna is niet de eigenaar
        self.client.force_login(self.bram)
        self.client.get(f"{self.url}?voorstel={v.pk}")
        v.refresh_from_db()
        self.assertIsNotNone(v.eigenaar_gezien_op)


class Meenemen(LadeBasis):
    def test_telt_pas_bij_opslaan(self):
        v = self.voorstel()
        self.client.force_login(self.anna)
        self.client.get(f"{self.url}?voorstel={v.pk}")  # alleen openen
        v.refresh_from_db()
        self.assertFalse(v.in_conceptversie)
        self.assertIsNone(v.eigenaar)
        self.opslaan_als_concept([v], [v])
        v.refresh_from_db()
        self.assertTrue(v.in_conceptversie)
        self.assertEqual(v.eigenaar, self.anna)
        self.assertEqual(v.status, VoorstelStatus.IN_BEHANDELING)

    @override_settings(KB_EMAIL_AAN=True)
    def test_overnemen_mailt_de_vorige_eigenaar(self):
        v = diensten.voorstel_naar_bak(self.voorstel(), self.bram, self.bram)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.opslaan_als_concept([v], [v])
        v.refresh_from_db()
        self.assertEqual(v.eigenaar, self.anna)
        self.assertEqual([m.to for m in mail.outbox if "overgenomen" in m.subject], [[self.bram.email]])

    def test_uitvinken_ontkoppelt(self):
        v = self.voorstel()
        self.opslaan_als_concept([v], [v])
        self.opslaan_als_concept([v], [])
        v.refresh_from_db()
        self.assertFalse(v.in_conceptversie)

    def test_alleen_wat_in_de_lade_stond(self):
        # Een voorstel dat binnenkwam na het openen van het scherm, raakt het formulier niet.
        oud = self.voorstel(tekst="Oud.")
        self.opslaan_als_concept([oud], [oud])
        nieuw = self.voorstel(tekst="Nieuw binnengekomen.")
        Verbetervoorstel.objects.filter(pk=nieuw.pk).update(in_conceptversie=True)
        self.opslaan_als_concept([oud], [oud])
        nieuw.refresh_from_db()
        self.assertTrue(nieuw.in_conceptversie)

    def test_zonder_lade_velden_verandert_er_niets(self):
        v = self.voorstel()
        Verbetervoorstel.objects.filter(pk=v.pk).update(in_conceptversie=True)
        self.client.force_login(self.anna)
        self.post(self.url, beheerdata(self.a, wijzigingstoelichting=""), _conceptversie="1")
        v.refresh_from_db()
        self.assertTrue(v.in_conceptversie)

    def test_publiceren_vraagt_daarna_om_af_te_handelen(self):
        v = self.voorstel()
        self.opslaan_als_concept([v], [v])
        data = beheerdata(self.a, wijzigingstoelichting="Termijn aangepast")
        data["geladen_concept"] = Conceptversie.objects.get(artikel=self.a).stempel
        data["kb_lade"] = str(v.pk)
        data["kb_meenemen"] = str(v.pk)
        r = self.post(self.url, data, _save="1")
        self.assertIn("voorstellen-afhandelen", r["Location"])
        v.refresh_from_db()
        self.assertEqual(v.verwerkt_in_versie, 2)

    def test_spoedcorrectie_neemt_mee_voor_de_correctie(self):
        self.maak_concept()
        v = self.voorstel(citaat="")
        self.client.force_login(self.anna)
        self.a.refresh_from_db()
        data = beheerdata(self.a, inhoud="<p>Stuur na twee weken een rappel. (spelfout hersteld)</p>")
        data["kb_lade"] = str(v.pk)
        data["kb_meenemen"] = str(v.pk)
        r = self.post(f"{self.url}?spoed=1", data, _save="1")
        self.assertEqual(r.status_code, 302, r.content.decode()[:300] if r.status_code == 200 else "")
        self.assertIn("voorstellen-afhandelen", r["Location"])
        v.refresh_from_db()
        self.assertFalse(v.in_conceptversie)
        self.assertEqual(v.verwerkt_in_versie, 2)
        self.assertEqual(v.eigenaar, self.anna)


class Acties(LadeBasis):
    @override_settings(KB_EMAIL_AAN=True)
    def test_bericht_gaat_naar_de_indiener_en_pakt_op(self):
        v = self.voorstel()
        self.client.force_login(self.anna)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            r = self.actie(v, actie="bericht", tekst="Ik pak dit op.")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["voorstel"]["berichten"][0]["tekst"], "Ik pak dit op.")
        v.refresh_from_db()
        self.assertEqual(v.eigenaar, self.anna)
        self.assertTrue(any(self.lies.email in m.to for m in mail.outbox))

    def test_notitie_blijft_intern(self):
        v = self.voorstel()
        self.client.force_login(self.anna)
        r = self.actie(v, actie="notitie", tekst="Gebeld met HR.")
        self.assertEqual(r.json()["voorstel"]["notities"][0]["tekst"], "Gebeld met HR.")
        self.assertFalse(v.berichten.exists())
        self.client.force_login(self.lies)
        self.assertNotIn("Gebeld met HR", self.client.get("/api/v1/voorstellen?lijst=mijn").content.decode())

    def test_lege_tekst_kan_niet(self):
        v = self.voorstel()
        self.client.force_login(self.anna)
        self.assertEqual(self.actie(v, actie="afwijzen", tekst="  ").status_code, 400)
        v.refresh_from_db()
        self.assertTrue(v.is_open)

    def test_afwijzen_en_dubbel(self):
        v = self.voorstel(tekst="Eerste.")
        w = self.voorstel(tekst="Tweede, hetzelfde.")
        self.client.force_login(self.anna)
        r = self.actie(w, actie="dubbel", tekst="Al gemeld.", dubbel_van=str(v.pk))
        self.assertTrue(r.json()["weg"])
        w.refresh_from_db()
        self.assertEqual((w.status, w.dubbel_van_id), (VoorstelStatus.AFGEWEZEN, v.pk))
        r = self.actie(v, actie="afwijzen", tekst="Klopt al.")
        v.refresh_from_db()
        self.assertEqual(v.status, VoorstelStatus.AFGEWEZEN)

    def test_dubbel_alleen_van_hetzelfde_artikel(self):
        ander = Artikel.objects.create(
            omgeving=self.noord, titel="Ander", samenvatting="x", inhoud="<p>y</p>", status=Status.GEPUBLICEERD
        )
        v = self.voorstel()
        w = Verbetervoorstel.objects.create(artikel=ander, artikel_versie=1, tekst="Elders.", ingediend_door=self.lies)
        self.client.force_login(self.anna)
        self.assertEqual(self.actie(v, actie="dubbel", tekst="x", dubbel_van=str(w.pk)).status_code, 400)

    def test_meegenomen_en_ter_inzage_niet_afwijzen(self):
        v = self.voorstel()
        self.maak_concept()
        self.opslaan_als_concept([v], [v])
        self.ter_inzage()
        self.client.force_login(self.anna)
        r = self.actie(v, actie="afwijzen", tekst="Toch niet.")
        self.assertEqual(r.status_code, 409)
        v.refresh_from_db()
        self.assertTrue(v.is_open)
        # Een voorstel dat niet is meegenomen, kan wel.
        w = self.voorstel(tekst="Los.")
        self.assertEqual(self.actie(w, actie="afwijzen", tekst="Niet nodig.").status_code, 200)

    def test_andere_omgeving_ziet_niets(self):
        v = self.voorstel()
        self.client.force_login(self.zoe)
        self.assertEqual(self.actie(v, actie="notitie", tekst="x").status_code, 404)
        self.client.force_login(self.lies)
        self.assertIn(self.actie(v, actie="notitie", tekst="x").status_code, (302, 403, 404))


class Werkbak(LadeBasis):
    def test_selectie_toewijzen_en_overslaan_als_het_intussen_veranderde(self):
        v = self.voorstel(tekst="Een.")
        w = self.voorstel(tekst="Twee.")
        diensten.voorstel_naar_bak(w, self.bram, self.bram)  # intussen opgepakt door Bram
        self.client.force_login(self.anna)
        r = self.client.post(
            "/beheer/werkplek/selectie/",
            {"voorstel": [f"{v.pk}-0", f"{w.pk}-0"], "actie": "toewijzen", "naar": str(self.anna.pk)},
            follow=True,
        )
        v.refresh_from_db()
        w.refresh_from_db()
        self.assertEqual((v.eigenaar, w.eigenaar), (self.anna, self.bram))
        self.assertContains(r, "intussen bij Bram")

    def test_selectie_verplaatsen(self):
        v = self.voorstel()
        self.client.force_login(self.anna)
        self.client.post(
            "/beheer/werkplek/selectie/", {"voorstel": [f"{v.pk}-0"], "actie": "naar_bak", "cluster": "algemeen"}
        )
        v.refresh_from_db()
        self.assertIsNone(v.cluster)

    def test_selectie_alleen_eigen_omgeving(self):
        v = self.voorstel()
        self.client.force_login(self.zoe)
        self.client.post(
            "/beheer/werkplek/selectie/", {"voorstel": [f"{v.pk}-0"], "actie": "toewijzen", "naar": "terug"}
        )
        v.refresh_from_db()
        self.assertIsNone(v.eigenaar)

    def test_regel_opent_de_editor_en_het_oude_scherm_verwijst_door(self):
        v = self.voorstel()
        self.client.force_login(self.anna)
        html = self.client.get(f"/beheer/?bak=cluster-{self.water.pk}").content.decode()
        self.assertIn(f"/beheer/kennisbank/artikel/{self.a.pk}/change/?voorstel={v.pk}", html)
        self.assertNotIn("Openen</a>", html)
        r = self.client.get(f"/beheer/voorstel/{v.pk}/")
        self.assertEqual(r["Location"], f"/beheer/kennisbank/artikel/{self.a.pk}/change/?voorstel={v.pk}")
        diensten.voorstel_afhandelen(v, self.anna, VoorstelStatus.AFGEWEZEN, "Niet nodig.")
        self.assertEqual(self.client.get(f"/beheer/voorstel/{v.pk}/").status_code, 200)  # afgehandeld: alleen-lezen


class Reviewer(LadeBasis):
    """1.27.0: de reviewer ziet de meegenomen voorstellen als context, zonder de naam van de indiener."""

    def test_meegenomen_voorstel_zonder_naam(self):
        from kennisbank.models import Inzage

        mee = self.voorstel(tekst="De termijn is drie weken geworden.", citaat="twee weken")
        los = self.voorstel(tekst="Iets anders, niet meegenomen.")
        diensten.notitie_toevoegen(mee, self.anna, "Interne notitie over Lies")
        self.maak_concept()
        self.opslaan_als_concept([mee, los], [mee])
        self.ter_inzage()
        i = Inzage.objects.get(artikel=self.a, team=self.team_water)
        self.client.force_login(self.wim)
        html = self.client.get(f"/review/{i.pk}/").content.decode()
        blok = html[html.index('class="rv-voorstellen"') : html.index('class="rv-verschil"')]
        self.assertIn("De termijn is drie weken geworden.", blok)
        self.assertNotIn("Iets anders", blok)
        self.assertNotIn("Lies", html)
        self.assertNotIn("Interne notitie", html)

    def test_zonder_meegenomen_voorstellen_geen_blok(self):
        from kennisbank.models import Inzage

        self.maak_concept()
        self.ter_inzage()
        i = Inzage.objects.get(artikel=self.a, team=self.team_water)
        self.client.force_login(self.wim)
        self.assertNotIn('class="rv-voorstellen"', self.client.get(f"/review/{i.pk}/").content.decode())
