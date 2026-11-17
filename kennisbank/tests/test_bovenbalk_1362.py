"""1.36.2 (wens Alex): de knoppen in de bovenbalk staan overal in dezelfde volgorde.

Kennisbank, Review, Werkplek, Hulp. De plek waar je bent licht op; een knop die niet voor jou is, ontbreekt
zonder dat de rest van plaats wisselt. De site bouwt zijn balk in `app.html` en toont Review en Werkplek via
het script; de andere pagina's gebruiken `kennisbank_balk.py`. Deze test houdt die twee gelijk.
"""

import re

from django.contrib.auth.models import User

from kennisbank.tests.test_review_c1 import ReviewBasis

VOLGORDE = ["Kennisbank", "Review", "Werkplek", "Hulp"]


def knoppen(html):
    """De links in de bovenbalk: (tekst, aan?, verborgen?) in de volgorde van de pagina."""
    balk = html[html.index('class="topbtns"') :]
    balk = balk[: balk.index("</header>")]
    uit = []
    for m in re.finditer(r'<a class="tb on-accent[^"]*"([^>]*)>([^<]+)</a>', balk):
        uit.append((m.group(2), 'aria-current="page"' in m.group(1), " hidden" in m.group(1)))
    return uit


class Volgorde(ReviewBasis):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.baas = User.objects.create_superuser("baas", password="x")
        # Redacteur die ook reviewer is: die ziet alle vier de knoppen.
        cls.anna.groups.add(cls.wim.groups.first())

    PAGINAS = {"/review/": "Review", "/hulp/": "Hulp", "/beheer/": "Werkplek"}

    def test_de_site_heeft_alle_vier_in_de_vaste_volgorde(self):
        k = knoppen(self.als(self.lies).get("/").content.decode())
        self.assertEqual([t for t, _, _ in k], VOLGORDE)
        self.assertEqual([t for t, aan, _ in k if aan], ["Kennisbank"])
        # Review en Werkplek staan er verborgen; het script toont ze aan wie ze mag gebruiken.
        self.assertEqual([t for t, _, weg in k if weg], ["Review", "Werkplek"])

    def test_elke_andere_pagina_dezelfde_volgorde_met_de_eigen_plek_aan(self):
        for pad, aan in self.PAGINAS.items():
            k = knoppen(self.als(self.anna).get(pad).content.decode())
            self.assertEqual([t for t, _, _ in k], VOLGORDE, pad)
            self.assertEqual([t for t, a, _ in k if a], [aan], pad)

    def test_een_knop_die_niet_voor_jou_is_ontbreekt_en_de_rest_blijft_op_volgorde(self):
        gevallen = [
            (self.lies, "/hulp/", ["Kennisbank", "Hulp"]),
            (self.wim, "/review/", ["Kennisbank", "Review", "Hulp"]),
            (self.wim, "/hulp/", ["Kennisbank", "Review", "Hulp"]),
            (self.bram, "/beheer/", ["Kennisbank", "Werkplek", "Hulp"]),
            (self.baas, "/beheer/", ["Kennisbank", "Werkplek", "Hulp"]),
        ]
        for gebruiker, pad, verwacht in gevallen:
            k = knoppen(self.als(gebruiker).get(pad).content.decode())
            self.assertEqual([t for t, _, _ in k], verwacht, (gebruiker, pad))

    def test_de_knop_heet_kennisbank_en_gaat_naar_de_site(self):
        for pad in self.PAGINAS:
            html = self.als(self.anna).get(pad).content.decode()
            self.assertIn('<a class="tb on-accent" href="/">Kennisbank</a>', html, pad)
            self.assertNotIn("Naar de kennisbank", html, pad)

    def test_hulp_staat_als_laatste_voor_de_naam(self):
        for pad in ["/", *self.PAGINAS]:
            html = self.als(self.anna).get(pad).content.decode()
            balk = html[html.index('class="topbtns"') :]
            self.assertLess(balk.index(">Hulp</a>"), balk.index('class="user"'), pad)
            self.assertLess(balk.index("Werkplek</a>"), balk.index(">Hulp</a>"), pad)
