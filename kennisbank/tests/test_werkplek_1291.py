"""1.29.1: werkplek en lade na feedback van Alex (bouwlijst `bouwlijst-1.29.1-werkplek-en-lade.md`)."""

import datetime

from django.conf import settings
from django.utils import timezone

from kennisbank import diensten
from kennisbank.models import Verbetervoorstel
from kennisbank.tests.test_bakken import Basis
from kennisbank.werkoverzicht import LANG_GELEDEN_DAGEN


def kolom(html):
    begin = html.index('<nav class="kb-bakkenkolom"')
    return html[begin : html.index("</nav>", begin)]


class Kolom(Basis):
    def test_knoppen_bovenaan_en_koppen_gelijk(self):
        k = kolom(self.als(self.anna).get("/beheer/").content.decode())
        self.assertLess(k.index("Nieuw artikel"), k.index("Werkvoorraad"))
        self.assertLess(k.index("Artikel uit Word"), k.index("Werkvoorraad"))
        for kop in ("Werkvoorraad", "Procesmanagers", "Artikelen"):
            self.assertIn(f'<h2 class="kb-kolomkop">{kop}</h2>', k)

    def test_eigen_bak_altijd_zichtbaar_collegas_inklapbaar(self):
        k = kolom(self.als(self.anna).get("/beheer/").content.decode())
        details = k.index('<details class="kb-collegas"')
        self.assertLess(k.index("(jij)"), details, "je eigen bak staat buiten de uitklaplijst")
        self.assertGreater(k.index("Bram"), details)
        self.assertNotIn('id="kb-collegas" open', k, "standaard dicht (de browser onthoudt de keuze)")

    def test_open_bij_de_bak_van_een_collega(self):
        k = kolom(self.als(self.anna).get(f"/beheer/?bak=u{self.bram.pk}").content.decode())
        self.assertIn('id="kb-collegas" open data-kb-vast="1"', k)

    def test_open_als_er_bij_een_collega_iets_te_lang_ligt(self):
        v = diensten.voorstel_naar_bak(self.voorstel(), self.bram, self.bram)
        oud = timezone.now() - datetime.timedelta(days=LANG_GELEDEN_DAGEN + 5)
        Verbetervoorstel.objects.filter(pk=v.pk).update(ingediend_op=oud, eigenaar_sinds=oud)
        k = kolom(self.als(self.anna).get("/beheer/").content.decode())
        self.assertIn("kb-aantal vol oud", k[k.index('<details class="kb-collegas"') :])
        self.assertIn('id="kb-collegas" open data-kb-vast="1"', k)


class Lade(Basis):
    def test_titel_en_geen_uitleg(self):
        html = self.als(self.anna).get(f"/beheer/kennisbank/artikel/{self.artikel.pk}/change/").content.decode()
        self.assertIn("<h2>Open verbetervoorstellen</h2>", html)
        self.assertNotIn("Klik op een voorstel om het te lezen", html)

    def test_teksten_in_het_script(self):
        js = (settings.BASE_DIR / "kennisbank/static/kennisbank/voorstellen-lade.js").read_text(encoding="utf-8")
        self.assertNotIn("anders telt het niet", js)
        self.assertIn("Kies Afronden om op te slaan", js)
        self.assertIn('"✉ Bericht"', js)
        self.assertNotIn("taB.placeholder", js)
        self.assertIn('"En nog " + (v.steuners.length - 5) + " meer"', js)
        self.assertNotIn('"tekst nog ongewijzigd – al aangepast?"', js)
