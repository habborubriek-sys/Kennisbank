"""1.29.0, ronde B: toegankelijkheid (bouwlijst `bouwlijst-1.29.0-ronde-b.md`).

Het gedrag (focus, Escape, Tab in een venster) zit in JavaScript en is in de browser nagelopen met Playwright en
axe (`scripts/browsertests/`). Hier wat de server meegeeft: de opbouw en de teksten voor de schermlezer.
"""

import re

from django.conf import settings

from kennisbank import diensten
from kennisbank.models import Inzage
from kennisbank.tests.test_voorstellen_lade_1260 import LadeBasis


def statisch(pad):
    return (settings.BASE_DIR / "kennisbank" / "static" / "kennisbank" / pad).read_text(encoding="utf-8")


class Bewerkscherm(LadeBasis):
    def test_panelknoppen_hebben_expanded_en_controls(self):
        html = self.als(self.anna).get(self.url).content.decode()
        for naam in ("eig", "gesch"):
            self.assertIn(f'data-kb-paneel="{naam}" aria-expanded="false" aria-controls="kb-p-{naam}"', html)
        self.assertIn('aria-label="Eigenschappen sluiten"', html)

    def test_lade_tabblad_staat_voor_de_lade_met_live_regio_en_sluitknop(self):
        self.voorstel()
        html = self.als(self.anna).get(self.url).content.decode()
        self.assertLess(html.index('id="kb-lip"'), html.index('id="kb-lade"'), "tabblad vóór de lade in de volgorde")
        self.assertIn('id="kb-lade-live" class="kb-sr" role="status" aria-live="polite"', html)
        self.assertIn('class="kb-lade-sluit" aria-label="Lade sluiten"', html)

    def test_geen_dode_verwijzing_naar_hulptekst(self):
        html = self.als(self.anna).get(self.url).content.decode()
        for ref in set(re.findall(r'aria-describedby="([^"]+)"', html)):
            for i in ref.split():
                self.assertIn(f'id="{i}"', html, f"aria-describedby verwijst naar {i}, dat niet bestaat")

    def test_nieuwsbericht_ook(self):
        html = self.als(self.anna).get("/beheer/kennisbank/bericht/add/").content.decode()
        self.assertIn('aria-controls="kb-p-eig"', html)
        for ref in set(re.findall(r'aria-describedby="([^"]+)"', html)):
            for i in ref.split():
                self.assertIn(f'id="{i}"', html, i)


class Werkbak(LadeBasis):
    def test_vinkje_noemt_het_voorstel_en_de_stip_heeft_tekst(self):
        from kennisbank.models import Verbetervoorstel

        v = self.voorstel(tekst="Termijn klopt niet. Graag aanpassen.")
        diensten.voorstel_naar_bak(v, self.bram, self.anna)
        Verbetervoorstel.objects.filter(pk=v.pk).update(eigenaar_gezien_op=None)
        html = self.als(self.anna).get(f"/beheer/?bak=u{self.anna.pk}").content.decode()
        self.assertIn('aria-label="Selecteer: Termijn klopt niet (bij Rappel versturen)"', html)
        self.assertIn('<span class="visually-hidden">Nog niet geopend</span>', html)
        self.assertIn('id="kb-selectie-teller" role="status"', html)
        self.assertIn("kennisbank/werkplek.js", html)


class Reviewpagina(LadeBasis):
    def test_citaat_ook_te_typen(self):
        self.maak_concept()
        self.ter_inzage()
        i = Inzage.objects.get(artikel=self.a)
        html = self.als(self.wim).get(f"/review/{i.pk}/").content.decode()
        self.assertIn('id="rv-citaat-invoer"', html)
        self.assertIn('<label for="rv-citaat-invoer"', html)

    def test_citaat_getypt_komt_bij_de_opmerking(self):
        self.maak_concept()
        self.ter_inzage()
        i = Inzage.objects.get(artikel=self.a)
        data = {"actie": "opmerking", "tekst": "Klopt dit?", "citaat": "drie weken"}
        self.als(self.wim).post(f"/review/{i.pk}/", data)
        self.assertEqual(i.opmerkingen.get().citaat, "drie weken")


class Scripts(LadeBasis):
    """Het gedrag zelf staat in JavaScript; deze tests bewaken dat de basis er niet stil uit verdwijnt."""

    def test_vensters_zijn_dialogen(self):
        js = statisch("beheer-editor.js")
        self.assertIn('document.createElement("dialog")', js)
        self.assertIn("showModal()", js)
        self.assertIn('"aria-labelledby"', js)
        self.assertIn('addEventListener("cancel"', js)

    def test_bekijk_als_medewerker_is_een_dialoog_en_escape_werkt_vanuit_het_voorbeeld(self):
        self.assertIn('document.createElement("dialog")', statisch("artikel-scherm.js"))
        self.assertIn("kb-voorbeeld-esc", statisch("artikel-scherm.js"))
        self.assertIn("kb-voorbeeld-esc", statisch("voorbeeld.js"))

    def test_lade_dicht_is_inert_en_focus_blijft(self):
        js = statisch("voorstellen-lade.js")
        self.assertIn("lade.inert = !aan", js)
        self.assertIn("data-kb-focus", js)
        self.assertIn('setAttribute("aria-pressed"', js)
        self.assertNotIn('"role", "tab"', js)

    def test_nummers_in_de_tekst_niet_als_getal_voorgelezen(self):
        js = statisch("artikel-editor.js")
        self.assertIn('s.setAttribute("aria-hidden", "true")', js)
        self.assertIn('"begin verbetervoorstel "', js)
        self.assertIn('"begin opmerking "', js)

    def test_werkbalk_namen_kloppen_met_wat_je_ziet(self):
        js = statisch("artikel-editor.js")
        self.assertIn('"x2 superscript"', js)
        self.assertIn('"1. Genummerde lijst"', js)

    def test_opmerking_van_de_review_is_groen_met_een_lijn(self):
        css = statisch("artikel-scherm.css")
        self.assertRegex(css, r"\.kb-ae-opm \{ background: #dcf1e2; border-bottom: 2px solid #1d6b3a;")
        self.assertIn("background: #1d6b3a; color: #fff", css)
        self.assertNotIn("#b58500", statisch("opmerkingen.css"))
        self.assertIn("border-bottom:2px solid #1d6b3a", statisch("opmerkingen.css"))
