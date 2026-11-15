"""1.34.0: de review in drie standen, één woord (concept), Verbergen naar de bak, en wanneer een kladversie vervalt.

Bouwlijst `bouwlijst-1.34.0-drie-standen-en-termen.md`, punten N1 t/m N3 en keuze 3.
"""

import re
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from kennisbank import review
from kennisbank.models import Conceptversie, Inzage, Kladversie
from kennisbank.tests.test_consistentie_1250 import balk_van
from kennisbank.tests.test_kennisbank import beheerdata
from kennisbank.tests.test_review_c1 import ReviewBasis

SELECTIE = "/beheer/werkplek/selectie/"


class StandBasis(ReviewBasis):
    def inzage(self, team=None):
        rijen = Inzage.objects.filter(artikel=self.a, afgesloten=False, team=team or self.team_water)
        return rijen.order_by("-ronde").first()

    def drie(self):
        self.a.refresh_from_db()
        return review.stand(self.a)["drie"]

    def wijzig_concept(self):
        c = Conceptversie.objects.get(artikel=self.a)
        self.client.force_login(self.anna)
        data = beheerdata(self.a, inhoud="<p>Toch anders.</p>", wijzigingstoelichting="", geladen_concept=c.stempel)
        self.post(self.url, data, _conceptversie="1")


# --- N1: elke toestand komt in de goede stand -------------------------------------------------------------------


class DrieStanden(StandBasis):
    def test_nog_niet_ter_inzage_is_bij_de_redactie(self):
        self.maak_concept()
        self.assertEqual(
            self.drie(),
            {"sleutel": "redactie", "naam": "Bij de redactie", "regel": "Nog niet ter inzage gegeven", "soort": "niet"},
        )

    def test_ter_inzage_en_opgepakt_is_bij_het_reviewteam(self):
        self.maak_concept()
        self.ter_inzage()
        d = self.drie()
        self.assertEqual((d["sleutel"], d["naam"], d["soort"]), ("team", "Bij het reviewteam", "inzage"))
        self.assertEqual(d["regel"], "Team Water: nog niet opgepakt")
        review.oppakken(self.inzage(), self.wim)
        d = self.drie()
        self.assertEqual((d["sleutel"], d["regel"]), ("team", "Team Water: ligt bij Wim"))

    def test_teruggegeven_is_bij_de_redactie_met_het_aantal_opmerkingen(self):
        self.maak_concept()
        self.ter_inzage()
        review.oppakken(self.inzage(), self.wim)
        review.opmerking_toevoegen(self.inzage(), self.wim, "Eerste")
        review.teruggeven(self.inzage(), self.wim, "Tweede")
        d = self.drie()
        self.assertEqual((d["sleutel"], d["soort"]), ("redactie", "terug"))
        self.assertEqual(d["regel"], "Teruggegeven door Team Water met 2 opmerkingen")

    def test_akkoord_en_daarna_gewijzigd(self):
        self.maak_concept()
        self.ter_inzage()
        review.oppakken(self.inzage(), self.wim)
        review.akkoord_geven(self.inzage(), self.wim)
        d = self.drie()
        self.assertEqual((d["sleutel"], d["naam"], d["soort"]), ("akkoord", "Akkoord", "akkoord"))
        self.assertRegex(d["regel"], r"^Akkoord van Team Water op \d{1,2} \w+$")
        self.wijzig_concept()
        d = self.drie()
        self.assertEqual((d["sleutel"], d["soort"]), ("redactie", "niet"))
        self.assertEqual(d["regel"], "Het akkoord is vervallen: de tekst is daarna gewijzigd")

    def test_teruggeroepen_is_bij_de_redactie(self):
        self.maak_concept()
        self.ter_inzage()
        self.post(f"/beheer/kennisbank/artikel/{self.a.pk}/terugroepen/", {})
        d = self.drie()
        self.assertEqual((d["sleutel"], d["soort"]), ("redactie", "niet"))
        self.assertRegex(d["regel"], r"^Teruggeroepen op \d{1,2} \w+$")

    def test_twee_teams_zolang_er_een_bezig_is_ligt_het_bij_het_reviewteam(self):
        self.maak_concept()
        self.ter_inzage(self.team_water, self.team_weg)
        review.oppakken(self.inzage(), self.wim)
        review.akkoord_geven(self.inzage(), self.wim)
        d = self.drie()
        self.assertEqual(d["sleutel"], "team", "één akkoord is nog geen akkoord")
        self.assertEqual(d["regel"], "Team Weg: nog niet opgepakt · Team Water: akkoord")
        review.oppakken(self.inzage(self.team_weg), self.willem)
        review.akkoord_geven(self.inzage(self.team_weg), self.willem)
        d = self.drie()
        self.assertEqual(d["sleutel"], "akkoord")
        self.assertIn("Akkoord van Team Water, Team Weg op ", d["regel"])

    def test_twee_teams_een_akkoord_en_een_teruggegeven_is_bij_de_redactie(self):
        self.maak_concept()
        self.ter_inzage(self.team_water, self.team_weg)
        review.oppakken(self.inzage(), self.wim)
        review.akkoord_geven(self.inzage(), self.wim)
        review.oppakken(self.inzage(self.team_weg), self.willem)
        review.teruggeven(self.inzage(self.team_weg), self.willem, "Nee")
        d = self.drie()
        self.assertEqual((d["sleutel"], d["soort"]), ("redactie", "terug"))
        self.assertEqual(d["regel"], "Teruggegeven door Team Weg met 1 opmerking · akkoord van Team Water")

    def test_een_nieuwe_ronde_telt_alleen_de_laatste(self):
        self.maak_concept()
        self.ter_inzage()
        review.oppakken(self.inzage(), self.wim)
        review.teruggeven(self.inzage(), self.wim, "Nee")
        self.ter_inzage()
        d = self.drie()
        self.assertEqual((d["sleutel"], d["regel"]), ("team", "Team Water: nog niet opgepakt"))
        self.assertEqual(review.standen_voor([self.a.pk])[self.a.pk], d, "de bak telt ook alleen de laatste ronde")

    def test_de_bak_rekent_hetzelfde_als_het_bewerkscherm_met_een_vast_aantal_vragen(self):
        self.maak_concept()
        self.ter_inzage(self.team_water, self.team_weg)
        review.oppakken(self.inzage(), self.wim)
        review.opmerking_toevoegen(self.inzage(), self.wim, "Eerste")
        review.teruggeven(self.inzage(), self.wim, "Tweede")
        review.oppakken(self.inzage(self.team_weg), self.willem)
        review.akkoord_geven(self.inzage(self.team_weg), self.willem)
        with self.assertNumQueries(2):
            standen = review.standen_voor([self.a.pk, 999999])
        self.assertEqual(standen[self.a.pk], self.drie())
        self.assertEqual(standen[999999]["regel"], "Nog niet ter inzage gegeven")


class StandInDeSchermen(StandBasis):
    def test_infobalk_en_paneel(self):
        self.maak_concept()
        html = self.client.get(self.url).content.decode()
        sub = balk_van(html)
        self.assertIn('<span class="kb-pil">Concept</span>', sub)
        self.assertIn(
            '<span class="kb-stand kb-stand-niet">Bij de redactie</span>'
            '<span class="kb-stand-regel">Nog niet ter inzage gegeven</span>',
            sub,
        )
        self.assertIn('kb-stand-niet">Bij de redactie</span> Je kunt de tekst wijzigen.', html)
        self.ter_inzage()
        html = self.client.get(self.url).content.decode()
        self.assertIn('kb-stand-inzage">Bij het reviewteam</span> De tekst staat op slot', html)
        review.oppakken(self.inzage(), self.wim)
        review.akkoord_geven(self.inzage(), self.wim)
        html = self.als(self.anna).get(self.url).content.decode()
        self.assertIn('kb-stand-akkoord">Akkoord</span> Je kunt publiceren.', html)

    def test_zonder_concept_geen_stand(self):
        self.assertNotIn("kb-stand-regel", self.als(self.anna).get(self.url).content.decode())

    def test_bak_concepten_toont_de_stand(self):
        self.maak_concept()
        self.ter_inzage()
        html = self.client.get("/beheer/?bak=concepten").content.decode()
        self.assertIn('<th scope="col">Review</th>', html)
        self.assertIn('<span class="kb-vstatus kb-stand-inzage">Bij het reviewteam</span>', html)
        self.assertIn('<span class="kb-label">concept</span>', html)

    def test_bak_concepten_zonder_reviewproces_heeft_geen_kolom(self):
        self.maak_concept()
        self.noord.reviewproces = False
        self.noord.save()
        try:
            html = self.client.get("/beheer/?bak=concepten").content.decode()
        finally:
            self.noord.reviewproces = True
            self.noord.save()
        self.assertNotIn('<th scope="col">Review</th>', html)
        self.assertNotIn("kb-stand-", html.split("<table", 1)[1])

    def test_bak_review_teruggegeven_staat_bovenaan(self):
        from kennisbank.models import Artikel, Status

        # Een tweede artikel dat nog bij het team ligt; alfabetisch zou het vóór "Rappel versturen" staan.
        tweede = Artikel.objects.create(
            omgeving=self.noord, titel="Aardig artikel", inhoud="<p>x</p>", status=Status.GEPUBLICEERD, versie=1
        )
        Conceptversie.objects.create(artikel=tweede, velden={"titel": "Aardig artikel"}, gestart_door=self.anna)
        Inzage.objects.create(artikel=tweede, team=self.team_weg, gestart_door=self.anna)
        self.maak_concept()
        self.ter_inzage()
        review.oppakken(self.inzage(), self.wim)
        review.teruggeven(self.inzage(), self.wim, "Nee")
        html = self.als(self.anna).get("/beheer/?bak=ter_inzage").content.decode()
        self.assertLess(html.index("Rappel versturen</a>"), html.index("Aardig artikel</a>"))
        self.assertEqual(html.count('<tr class="kb-rij-let-op">'), 1)
        self.assertIn("Teruggegeven door Team Water met 1 opmerking", html)
        self.assertIn("Team Weg: nog niet opgepakt", html)
        self.assertIn(">Review<", html.split('class="kb-bakkenkolom"', 1)[1], "de bak heet Review")


# --- N3: Verbergen voor collega's in de bak --------------------------------------------------------------------


class VerbergenInDeBak(StandBasis):
    def test_meer_voorstellen_tegelijk_verbergen_en_weer_tonen(self):
        een, twee = self.voorstel(artikel=self.a), self.voorstel(artikel=self.a, tekst="Tweede")
        c = self.als(self.anna)
        r = c.post(SELECTIE, {"actie": "verbergen", "voorstel": [f"{een.pk}-0", f"{twee.pk}-0"], "terug": "algemeen"})
        self.assertEqual(r.status_code, 302)
        een.refresh_from_db()
        twee.refresh_from_db()
        self.assertTrue(een.verborgen and twee.verborgen)
        self.assertEqual(LogEntry.objects.filter(change_message="Verborgen voor collega's.").count(), 2)
        html = c.get(f"/beheer/?bak=cluster-{self.water.pk}").content.decode()
        self.assertIn("2 voorstellen verborgen voor collega", html)
        self.assertEqual(html.count('<span class="kb-label">verborgen voor collega\'s</span>'), 2)
        c.post(SELECTIE, {"actie": "tonen", "voorstel": [f"{een.pk}-0"], "terug": "algemeen"})
        een.refresh_from_db()
        twee.refresh_from_db()
        self.assertEqual((een.verborgen, twee.verborgen), (False, True))

    def test_de_knoppen_staan_in_de_selectiebalk(self):
        self.voorstel(artikel=self.a)
        html = self.als(self.anna).get(f"/beheer/?bak=cluster-{self.water.pk}").content.decode()
        balk = html[html.index('id="kb-selectie"') : html.index("</form>", html.index('id="kb-selectie"'))]
        self.assertIn('name="actie" value="verbergen"', balk)
        self.assertIn('name="actie" value="tonen"', balk)

    def test_alleen_de_redactie_van_die_omgeving(self):
        v = self.voorstel(artikel=self.a)
        for wie in (self.zoe, self.lies):
            self.als(wie).post(SELECTIE, {"actie": "verbergen", "voorstel": [f"{v.pk}-0"]})
            v.refresh_from_db()
            self.assertFalse(v.verborgen, wie.username)

    def test_de_lade_kan_het_niet_meer_en_zegt_waar_het_wel_kan(self):
        v = self.voorstel(artikel=self.a, verborgen=True)
        r = self.als(self.anna).post(f"/beheer/voorstel/{v.pk}/lade/", {"actie": "verbergen", "waarde": "0"})
        self.assertEqual(r.status_code, 400)
        v.refresh_from_db()
        self.assertTrue(v.verborgen)
        js = (Path(settings.BASE_DIR) / "kennisbank/static/kennisbank/voorstellen-lade.js").read_text(encoding="utf-8")
        self.assertNotIn('"verbergen"', js)
        self.assertNotIn("Verbergen voor collega", js)
        self.assertIn("Dat wijzig je in de bak op je werkplek.", js)


# --- N2: één woord -----------------------------------------------------------------------------------------------

OUD = re.compile(r"onceptversie|poedcorrectie|leine correctie|epubliceerde versie|erkbak|erugkoppeling")
#: Namen in de code die blijven: het adres, het formulierveld, het veld op een voorstel en sjabloonvariabelen.
NAMEN = re.compile(
    r"/conceptversie/|_conceptversie|in_conceptversie|heeft_conceptversie|inhoud\.conceptversies|laatste_terugkoppeling"
    r"|name=\"terugkoppeling\"|id_terugkoppeling|for=\"id_terugkoppeling\""
)


def oude_woorden(tekst: str) -> list[str]:
    return sorted({m.group(0) for m in OUD.finditer(NAMEN.sub("", tekst))})


class EenWoord(StandBasis):
    def schoon(self, naam, html):
        self.assertEqual(oude_woorden(html), [], naam)

    def test_bewerkscherm_in_elke_stand(self):
        self.maak_concept()
        self.schoon("concept", self.client.get(self.url).content.decode())
        self.schoon("live versie", self.client.get(self.url + "?live=1").content.decode())
        self.ter_inzage()
        self.schoon("bij het reviewteam", self.client.get(self.url).content.decode())
        review.oppakken(self.inzage(), self.wim)
        review.teruggeven(self.inzage(), self.wim, "Nee")
        self.schoon("teruggegeven", self.als(self.anna).get(self.url).content.decode())

    def test_meldingen_bij_opslaan_ter_inzage_terugroepen_en_weggooien(self):
        self.maak_concept()
        self.ter_inzage()
        self.post(f"/beheer/kennisbank/artikel/{self.a.pk}/terugroepen/", {})
        self.post(f"/beheer/kennisbank/artikel/{self.a.pk}/conceptversie/weggooien/", {})
        html = self.client.get("/beheer/").content.decode()
        self.assertIn("Het concept is weggegooid. Je ziet weer de live versie.", html)
        self.schoon("meldingen", html)
        self.assertFalse(Conceptversie.objects.filter(artikel=self.a).exists())
        berichten = " | ".join(LogEntry.objects.values_list("change_message", flat=True))
        self.assertIn("Concept ter inzage gegeven aan Team Water.", berichten)
        self.assertIn("Concept teruggeroepen uit de review.", berichten)
        self.assertEqual(oude_woorden(berichten), [])

    def test_werkplek_review_en_voorstelscherm(self):
        self.maak_concept()
        self.ter_inzage()
        v = self.voorstel(artikel=self.a)
        for bak in ("concepten", "ter_inzage", "algemeen", "kladversies", "afgehandeld"):
            self.schoon(bak, self.als(self.anna).get(f"/beheer/?bak={bak}").content.decode())
        self.schoon("voorstel", self.client.get(f"/beheer/voorstel/{v.pk}/").content.decode())
        self.schoon("review lijst", self.als(self.wim).get("/review/").content.decode())
        self.schoon("review stuk", self.client.get(f"/review/{self.inzage().pk}/").content.decode())

    @override_settings(KB_EMAIL_AAN=True)
    def test_emails(self):
        self.maak_concept()
        self.ter_inzage()
        review.oppakken(self.inzage(), self.wim)
        with self.captureOnCommitCallbacks(execute=True):
            self.post(f"/beheer/kennisbank/artikel/{self.a.pk}/terugroepen/", {})
        self.ter_inzage()
        review.oppakken(self.inzage(), self.wim)
        with self.captureOnCommitCallbacks(execute=True):
            review.teruggeven(self.inzage(), self.wim, "Nee")
        review.verstuur_reviewmail()
        self.assertGreaterEqual(len(mail.outbox), 2)
        for m in mail.outbox:
            self.assertEqual(oude_woorden(m.subject + "\n" + m.body), [], m.subject)
        self.assertIn("het concept van", " ".join(m.body for m in mail.outbox))

    def test_scripts_en_sjablonen(self):
        wortel = Path(settings.BASE_DIR)
        bestanden = [
            p
            for map_, patroon in (("kennisbank/static/kennisbank", "*.js"), ("templates", "**/*.html"))
            for p in (wortel / map_).glob(patroon)
        ]
        self.assertGreater(len(bestanden), 15)
        for p in bestanden:
            self.assertEqual(oude_woorden(p.read_text(encoding="utf-8")), [], p.name)


# --- Keuze 3: wanneer een kladversie vervalt ----------------------------------------------------------------------


class KladversieVervalt(StandBasis):
    def klad(self, dagen_oud, titel):
        from kennisbank.models import Artikel

        artikel = Artikel.objects.create(omgeving=self.noord, titel=titel, inhoud="<p>x</p>")
        k = Kladversie.objects.create(gebruiker=self.anna, artikel=artikel, velden={"titel": titel})
        Kladversie.objects.filter(pk=k.pk).update(bijgewerkt_op=timezone.now() - timedelta(days=dagen_oud))
        return k

    @override_settings(KB_KLADVERSIE_DAGEN=30)
    def test_de_bak_zegt_wanneer(self):
        self.klad(0, "Vers")
        self.klad(25, "Bijna")
        self.klad(29, "Morgen")
        html = self.als(self.anna).get("/beheer/?bak=kladversies").content.decode()
        self.assertIn('<th scope="col">Vervalt</th>', html)
        self.assertIn("<td>over 30 dagen</td>", html)
        self.assertIn('<td class="kb-vervalt-snel">over 5 dagen</td>', html)
        self.assertIn('<td class="kb-vervalt-snel">morgen</td>', html)
        self.assertIn("Een kladversie blijft 30 dagen staan na de laatste wijziging", html)

    @override_settings(KB_KLADVERSIE_DAGEN=14)
    def test_de_termijn_volgt_de_instelling(self):
        self.klad(0, "Vers")
        html = self.als(self.anna).get("/beheer/?bak=kladversies").content.decode()
        self.assertIn("<td>over 14 dagen</td>", html)
        self.assertIn("blijft 14 dagen staan", html)
