"""Upgrade-test: een database met inhoud van versie 1.0 (Markdown-secties, apart onboarding-veld,
versiegeschiedenis als JSON, tellingen zonder omgeving) moet in één keer naar de huidige versie kunnen.

De omzettingen in de migraties zijn bevroren in kennisbank/oud_formaat.py; deze test bewaakt dat ze
blijven doen wat ze deden.
"""

import json

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class UpgradeVanaf10Tests(TransactionTestCase):
    def _migreer_naar(self, naam):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([("kennisbank", naam)])
        return executor.loader.project_state([("kennisbank", naam)]).apps

    def test_inhoud_van_1_0_komt_heel_over(self):
        oud = self._migreer_naar("0001_initial")
        Omgeving = oud.get_model("kennisbank", "Omgeving")
        Artikel = oud.get_model("kennisbank", "Artikel")
        Sectie = oud.get_model("kennisbank", "Sectie")
        ArtikelVersie = oud.get_model("kennisbank", "ArtikelVersie")
        ZoekTelling = oud.get_model("kennisbank", "ZoekTelling")
        o = Omgeving.objects.create(slug="handhaving", naam="Handhaving", beschrijving="")
        a = Artikel.objects.create(omgeving=o, slug="rappel", titel="Rappel versturen", samenvatting="x", versie=1)
        Sectie.objects.create(
            artikel=a,
            volgorde=1,
            kop="Eerste rappel",
            inhoud="# Kop uit Markdown\n\nStuur **direct** een rappel.\n\n- punt 1\n- punt 2",
            onboarding="Nieuw? Vraag je *buddy*. <script>x</script>",
        )
        Sectie.objects.create(artikel=a, volgorde=2, kop="Tweede rappel", inhoud="Na 2 weken.", onboarding="")
        ArtikelVersie.objects.create(
            artikel=a,
            versie=1,
            inhoud={
                "secties": [{"kop": "Eerste rappel", "inhoud": "Stuur **direct**.", "onboarding": "Vraag je buddy."}]
            },
        )
        ZoekTelling.objects.create(term="rappel", datum="2026-01-01", aantal=5, zonder_resultaat=0)

        nieuw = self._migreer_naar("0007_zoekvectoren")
        Artikel = nieuw.get_model("kennisbank", "Artikel")
        Sectie = nieuw.get_model("kennisbank", "Sectie")
        ArtikelVersie = nieuw.get_model("kennisbank", "ArtikelVersie")
        ZoekTelling = nieuw.get_model("kennisbank", "ZoekTelling")
        a = Artikel.objects.get(slug="rappel")
        self.assertEqual(
            a.inhoud,
            '<section class="sectie"><h2 class="sectie-kop">Eerste rappel</h2>'
            '<div class="onboarding"><p>Nieuw? Vraag je <em>buddy</em>. </p></div>'
            "<h3>Kop uit Markdown</h3>\n<p>Stuur <strong>direct</strong> een rappel.</p>\n"
            "<ul>\n<li>punt 1</li>\n<li>punt 2</li>\n</ul>"
            '</section><section class="sectie"><h2 class="sectie-kop">Tweede rappel</h2><p>Na 2 weken.</p></section>',
        )
        self.assertEqual(
            [(s.volgorde, s.kop) for s in Sectie.objects.filter(artikel=a).order_by("volgorde")],
            [(0, ""), (1, "Eerste rappel"), (2, "Tweede rappel")],
        )
        v = ArtikelVersie.objects.get(artikel=a)
        self.assertEqual(v.inhoud["formaat"], "artikel-html")
        verwacht = '<div class="onboarding"><p>Vraag je buddy.</p></div><p>Stuur <strong>direct</strong>.</p>'
        self.assertIn(verwacht, v.inhoud["inhoud"])
        self.assertEqual(ZoekTelling.objects.get(term="rappel").omgeving.slug, "handhaving")  # enige omgeving
        self.assertNotIn("<script>", json.dumps(a.inhoud))
        # De zoekdocumenten zijn gevuld door de migratie, zodat zoeken direct na de upgrade werkt.
        from django.contrib.postgres.search import SearchQuery

        self.assertTrue(Artikel.objects.filter(zoekvector=SearchQuery("rappel", config="dutch")).exists())
        self.assertTrue(Sectie.objects.filter(zoekvector=SearchQuery("buddy", config="dutch")).exists())
