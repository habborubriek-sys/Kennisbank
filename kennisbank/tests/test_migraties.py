"""Upgrade-test: een database met inhoud van versie 1.0 (Markdown-secties, apart onboarding-veld,
versiegeschiedenis als JSON, tellingen zonder omgeving) moet in één keer naar de huidige versie kunnen.

De omzettingen in de migraties zijn bevroren in kennisbank/oud_formaat.py; deze test bewaakt dat ze
blijven doen wat ze deden.
"""

import json

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


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


class UpgradeNaar17Tests(TransactionTestCase):
    """Migratie 0009: tags normaliseren/samenvoegen en bestaande versies als gezien markeren."""

    def _migreer_naar(self, naam):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([("kennisbank", naam)])
        return executor.loader.project_state([("kennisbank", naam)]).apps

    def test_bestaande_gegevens(self):
        oud = self._migreer_naar("0008_wijzigingen_en_nieuws")
        Omgeving = oud.get_model("kennisbank", "Omgeving")
        Artikel = oud.get_model("kennisbank", "Artikel")
        Tag = oud.get_model("kennisbank", "Tag")
        User = oud.get_model("auth", "User")
        o = Omgeving.objects.create(slug="handhaving", naam="Handhaving", beschrijving="")
        a1 = Artikel.objects.create(omgeving=o, slug="a", titel="A", samenvatting="x", versie=3)
        a2 = Artikel.objects.create(omgeving=o, slug="b", titel="B", samenvatting="x", versie=1)
        t_hoofd = Tag.objects.create(naam="Omgevingswet")
        t_klein = Tag.objects.create(naam="omgevingswet")
        t_spatie = Tag.objects.create(naam="  Twee   woorden ")
        a1.tags.add(t_hoofd)
        a2.tags.add(t_klein, t_spatie)
        User.objects.create(username="een")
        User.objects.create(username="twee")

        nieuw = self._migreer_naar("0009_bestaande_gegevens_1_7")
        Tag = nieuw.get_model("kennisbank", "Tag")
        Artikel = nieuw.get_model("kennisbank", "Artikel")
        WijzigingGezien = nieuw.get_model("kennisbank", "WijzigingGezien")
        self.assertEqual(sorted(Tag.objects.values_list("naam", flat=True)), ["omgevingswet", "twee woorden"])
        self.assertEqual(sorted(Artikel.objects.get(slug="a").tags.values_list("naam", flat=True)), ["omgevingswet"])
        self.assertEqual(
            sorted(Artikel.objects.get(slug="b").tags.values_list("naam", flat=True)), ["omgevingswet", "twee woorden"]
        )
        # Alleen het artikel met versie > 1 is afgevinkt, voor beide gebruikers, tot en met de huidige versie.
        self.assertEqual(WijzigingGezien.objects.count(), 2)
        self.assertEqual(set(WijzigingGezien.objects.values_list("artikel__slug", "versie")), {("a", 3)})


class UpgradeNaar110Tests(TransactionTestCase):
    """Migraties 0010 t/m 0017: wat verdwijnt er, en wat blijft er staan?

    Twee dingen die bij een upgrade van een bestaande installatie echt gebeuren en die tot nu toe geen
    test hadden: 0011 verwijdert lege sectierijen, en 0017 maakt van een bestaande terugkoppeling een
    bericht — zonder die laatste zou een medewerker zijn antwoord na de upgrade niet meer zien.
    """

    def _migreer_naar(self, naam):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([("kennisbank", naam)])
        return executor.loader.project_state([("kennisbank", naam)]).apps

    def test_lege_secties_weg_en_terugkoppelingen_worden_berichten(self):
        oud = self._migreer_naar("0010_zacht_slot")
        Omgeving = oud.get_model("kennisbank", "Omgeving")
        Artikel = oud.get_model("kennisbank", "Artikel")
        Sectie = oud.get_model("kennisbank", "Sectie")
        Verbetervoorstel = oud.get_model("kennisbank", "Verbetervoorstel")
        User = oud.get_model("auth", "User")

        o = Omgeving.objects.create(slug="handhaving", naam="Handhaving", beschrijving="")
        a = Artikel.objects.create(omgeving=o, slug="a", titel="A", samenvatting="x", versie=1)
        Sectie.objects.create(artikel=a, volgorde=0, kop="", inhoud="")  # leeg: hoort weg
        Sectie.objects.create(artikel=a, volgorde=0, kop="", inhoud="   ")  # wit: hoort weg
        Sectie.objects.create(artikel=a, volgorde=0, kop="", inhoud="<p>Inleiding</p>")  # hoort te blijven
        Sectie.objects.create(artikel=a, volgorde=1, kop="Stappen", inhoud="<p>Stap 1</p>")

        pm = User.objects.create(username="pm")
        met = Verbetervoorstel.objects.create(
            artikel=a, artikel_versie=1, tekst="Termijn klopt niet",
            terugkoppeling="Aangepast in versie 2.", status="verwerkt",
            behandeld_door=pm, behandeld_op=timezone.now(),
        )
        zonder = Verbetervoorstel.objects.create(
            artikel=a, artikel_versie=1, tekst="Nog niet bekeken", terugkoppeling="", status="nieuw"
        )

        nieuw = self._migreer_naar("0017_voorstel_eenrichting")
        Sectie = nieuw.get_model("kennisbank", "Sectie")
        VoorstelBericht = nieuw.get_model("kennisbank", "VoorstelBericht")

        # 0011: alleen de werkelijk lege vrije-tekstrijen zijn weg.
        overgebleven = sorted(Sectie.objects.filter(artikel_id=a.pk).values_list("volgorde", "inhoud"))
        self.assertEqual(overgebleven, [(0, "<p>Inleiding</p>"), (1, "<p>Stap 1</p>")])

        # 0017: de bestaande terugkoppeling is een bericht geworden, met de juiste auteur en datum.
        bericht = VoorstelBericht.objects.get(voorstel_id=met.pk)
        self.assertEqual(bericht.tekst, "Aangepast in versie 2.")
        self.assertTrue(bericht.van_redactie)
        self.assertEqual(bericht.auteur_id, pm.pk)
        self.assertEqual(bericht.moment, met.behandeld_op)
        # Een voorstel zonder terugkoppeling krijgt niets.
        self.assertFalse(VoorstelBericht.objects.filter(voorstel_id=zonder.pk).exists())
