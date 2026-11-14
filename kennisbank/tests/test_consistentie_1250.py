"""1.25.0: één uitstraling voor review, beheer en bewerkschermen (bouwlijst `bouwlijst-1.25.0-consistentie.md`).

De opmaak zelf is in de browser nagelopen; hier wat de server meegeeft: dezelfde bovenbalk, de namen, het menu
Meer en de knop Afronden bij nieuwe artikelen en nieuwsberichten.
"""

import html as htmllib
import re

from kennisbank import review
from kennisbank.models import Artikel, Bericht, BerichtStatus, Conceptversie, Inzage, Status
from kennisbank.tests.test_review_c1 import ReviewBasis


def balk_van(html):
    return html[html.index('<header class="kb-balk"') : html.index("</header>", html.index('<header class="kb-balk"'))]


def formulier_velden(html, form_id):
    """De velden zoals de browser ze zou versturen (zonder knoppen en vinkjes)."""
    form = html[html.index(f'id="{form_id}"') :]
    data = {}
    for m in re.finditer(r"<(input|textarea)\b([^>]*)>(.*?)(?=<)", form, re.S):
        tag, attrs = m.group(1), m.group(2)
        naam = re.search(r'name="([^"]+)"', attrs)
        if not naam:
            continue
        if tag == "input":
            soort = re.search(r'type="([^"]+)"', attrs)
            if soort and soort.group(1) in ("submit", "button", "checkbox"):
                continue
            waarde = re.search(r'value="([^"]*)"', attrs)
            data[naam.group(1)] = htmllib.unescape(waarde.group(1)) if waarde else ""
        else:
            data[naam.group(1)] = htmllib.unescape(m.group(3)).lstrip("\n")
    return data


class Bovenbalk(ReviewBasis):
    def test_reviewpagina_heet_review_en_heeft_de_balk_van_de_site(self):
        self.client.force_login(self.wim)
        html = self.client.get("/review/").content.decode()
        self.assertIn("<h1>Review</h1>", html)
        self.assertNotIn("<h1>Ter inzage</h1>", html)
        self.assertIn('class="top kb-top"', html)
        self.assertRegex(html, r'<a class="tb on-accent" href="/review/" aria-current="page">Review</a>')
        self.assertIn("Naar de kennisbank", html)
        self.assertIn(">Uitloggen</button>", html)
        # Wim is geen redacteur: geen knop Werkplek.
        self.assertNotIn(">Werkplek</a>", html)

    def test_alle_beheerpaginas_hebben_dezelfde_balk(self):
        self.client.force_login(self.anna)
        for url in ("/beheer/", "/beheer/kennisbank/artikel/", "/beheer/kennisbank/"):
            html = self.client.get(url).content.decode()
            self.assertIn('class="top kb-top"', html, url)
            self.assertIn('aria-current="page">Werkplek</a>', html, url)
            self.assertNotIn('id="site-name"', html, url)
            self.assertNotIn('id="user-tools"', html, url)

    def test_werkplek_een_hoofdknop(self):
        from kennisbank.models import Verbetervoorstel

        Verbetervoorstel.objects.create(artikel=self.a, artikel_versie=self.a.versie, tekst="De termijn klopt niet.")
        self.client.force_login(self.anna)
        html = self.client.get(f"/beheer/?bak=cluster-{self.water.pk}").content.decode()
        # Sinds 1.26.0 een lijst zonder knoppen per regel; de selectiebalk heeft gewone (omrande) knoppen.
        self.assertIn('name="actie" value="toewijzen" class="button">', html)
        self.assertNotIn("button default", html[html.index('id="kb-selectie"') :])


class OnlangsAfgerond(ReviewBasis):
    def test_een_regel_per_artikel_met_eerdere_rondes(self):
        for _ in range(3):
            self.maak_concept()
            self.ter_inzage()
            review.terugroepen(self.a, self.anna)
        self.assertEqual(Inzage.objects.filter(artikel=self.a).count(), 3)
        self.client.force_login(self.wim)
        html = self.client.get("/review/").content.decode()
        afgerond = html[html.index("Onlangs afgerond") :]
        self.assertEqual(afgerond.count('<span class="rv-titel">Rappel versturen</span>'), 1)
        self.assertIn("Eerdere rondes (2)", afgerond)


class BalkMetMeer(ReviewBasis):
    def test_het_menu_meer_is_weg(self):
        # 1.33.0 (L4): Meer bestaat niet meer. Weggooien zit in Afronden, de live versie bekijk je via de infobalk.
        self.maak_concept()
        html = self.client.get(self.url).content.decode()
        balk = balk_van(html)
        self.assertNotIn("kb-meer", html)
        self.assertNotIn("Corrigeer de gepubliceerde versie", html)
        self.assertNotIn("Conceptversie weggooien", balk)
        sub = balk[balk.index("kb-balk-sub") : balk.index("kb-balk-terug")]
        self.assertIn("Conceptversie</span>", sub)
        self.assertIn(f'Medewerkers zien <a href="{self.a.get_absolute_url()}"', sub)

    def test_reviewstand_naast_de_conceptversie(self):
        self.maak_concept()
        self.ter_inzage()
        balk = balk_van(self.client.get(self.url).content.decode())
        sub = balk[balk.index("kb-balk-sub") : balk.index("kb-balk-terug")]
        self.assertIn("kb-stand", sub)
        self.assertIn("Ter inzage bij Team Water", sub)


class AfrondenOveral(ReviewBasis):
    def test_nieuw_artikel_opslaan_met_het_formulier_zoals_de_browser_het_stuurt(self):
        # Fout uit 1.24.0: bij een nieuw artikel ontbrak de (lege) versielijst in het formulier, waardoor opslaan
        # altijd mislukte met "Corrigeer de onderstaande fout".
        self.client.force_login(self.anna)
        html = self.client.get("/beheer/kennisbank/artikel/add/").content.decode()
        self.assertIn('name="versies-TOTAL_FORMS"', html)
        data = formulier_velden(html, "artikel_form")
        data.update(
            {
                "titel": "Een nieuw artikel uit de test",
                "samenvatting": "Hoe je in een test een nieuw artikel aanmaakt en opslaat.",
                "inhoud": "<p>Tekst.</p>",
                "soort": "werkinstructie",
                "omgeving": self.noord.pk,
                "status": "concept",
                "_continue": "1",
            }
        )
        r = self.client.post("/beheer/kennisbank/artikel/add/", data)
        self.assertEqual(r.status_code, 302, r.content.decode()[:200] if r.status_code == 200 else "")
        self.assertTrue(Artikel.objects.filter(titel="Een nieuw artikel uit de test", status=Status.CONCEPT).exists())

    def test_nog_niet_gepubliceerd_artikel_eenvoudige_afronden(self):
        a = Artikel.objects.create(omgeving=self.noord, titel="Nog niet live", samenvatting="x", inhoud="<p>x</p>")
        self.client.force_login(self.anna)
        html = self.client.get(f"/beheer/kennisbank/artikel/{a.pk}/change/").content.decode()
        self.assertIn("kb-afronden-knop", balk_van(html))
        self.assertIn('"eenvoudig": true', html)
        self.assertIn('"nieuw": false', html)

    def test_gepubliceerd_artikel_houdt_de_volledige_afronden(self):
        self.maak_concept()
        html = self.client.get(self.url).content.decode()
        self.assertNotIn('"eenvoudig"', html)
        self.assertTrue(Conceptversie.objects.filter(artikel=self.a).exists())

    def test_nieuwsbericht_afronden(self):
        self.client.force_login(self.anna)
        html = self.client.get("/beheer/kennisbank/bericht/add/").content.decode()
        self.assertIn("kb-afronden-knop", balk_van(html))
        self.assertIn('"eenvoudig": true', html)
        self.assertIn('"gepubliceerd": false', html)
        self.assertEqual(html.count('name="_continue"'), 1)
        b = Bericht.objects.create(
            omgeving=self.noord, titel="Live", tekst="<p>x</p>", status=BerichtStatus.GEPUBLICEERD
        )
        html = self.client.get(f"/beheer/kennisbank/bericht/{b.pk}/change/").content.decode()
        self.assertIn('"gepubliceerd": true', html)
