"""1.36.0: de knop Hulp en de hulpartikelen per rol.

Wens van Alex (17 november 2026): hulpartikelen los van de kennisartikelen, op een eigen pagina met links een
menu en rechts het artikel. Wat je ziet is een trap: medewerker -> reviewer -> redacteur -> beheerder.
"""

import html as htmllib
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from kennisbank import hulp
from kennisbank.hulp_inhoud import STANDAARD
from kennisbank.models import Hulpartikel, Status
from kennisbank.tests.test_review_c1 import ReviewBasis

LIJST = "/beheer/kennisbank/hulpartikel/"


def menu(html):
    """De koppen van het menu met de titels eronder, in de volgorde van de pagina."""
    nav = html[html.index('<nav class="hulp-menu"') : html.index("</nav>", html.index('<nav class="hulp-menu"'))]
    uit, kop = [], None
    for m in re.finditer(r'hulp-menukop">([^<]+)<|<li><a href="([^"]+)"[^>]*>([^<]+)', nav):
        if m.group(1):
            kop = [htmllib.unescape(m.group(1)), []]
            uit.append(kop)
        else:
            kop[1].append((m.group(2), htmllib.unescape(m.group(3)).strip()))
    return uit


class HulpBasis(ReviewBasis):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.baas = User.objects.create_superuser("baas", password="x")

    def hulp(self, gebruiker, pad="/hulp/", **params):
        r = self.als(gebruiker).get(pad, params)
        self.assertEqual(r.status_code, 200, pad)
        return r, r.content.decode()


# --- H2: wie ziet wat ---------------------------------------------------------------------------------------------


class PerRol(HulpBasis):
    def test_de_trap(self):
        r = hulp.rechten
        self.assertEqual(hulp.niveau_van(self.lies, r(self._verzoek(self.lies))), 1)
        self.assertEqual(hulp.niveau_van(self.wim, r(self._verzoek(self.wim))), 2)
        self.assertEqual(hulp.niveau_van(self.anna, r(self._verzoek(self.anna))), 3)
        self.assertEqual(hulp.niveau_van(self.baas, r(self._verzoek(self.baas))), 4)

    def _verzoek(self, gebruiker):
        from django.test import RequestFactory

        verzoek = RequestFactory().get("/hulp/")
        verzoek.user = gebruiker
        return verzoek

    def test_menu_per_rol_met_de_eigen_rol_bovenaan(self):
        verwacht = {
            self.lies: ["Medewerker"],
            self.wim: ["Reviewer", "Medewerker"],
            self.anna: ["Redacteur", "Reviewer", "Medewerker"],
            self.baas: ["Functioneel beheerder", "Redacteur", "Reviewer", "Medewerker"],
        }
        for gebruiker, koppen in verwacht.items():
            r, html = self.hulp(gebruiker)
            self.assertEqual([k for k, _ in menu(html)], koppen, gebruiker)
            # Zonder herkomst opent het eerste artikel van je eigen rol.
            self.assertEqual(r.context["huidig"].get_doelgroep_display(), koppen[0])

    def test_binnen_een_rol_op_volgorde(self):
        r, html = self.hulp(self.lies)
        titels = [t for _, t in menu(html)[0][1]]
        self.assertEqual(titels, [s["titel"] for s in STANDAARD if s["doelgroep"] == "medewerker"])
        self.assertEqual(titels[0], "Zoeken en lezen")

    def test_een_artikel_boven_je_rol_bestaat_voor_jou_niet(self):
        for gebruiker, slug, code in (
            (self.lies, "zoeken-en-lezen", 200),
            (self.lies, "concept-reviewen", 404),
            (self.lies, "publiceren", 404),
            (self.wim, "concept-reviewen", 200),
            (self.wim, "publiceren", 404),
            (self.anna, "publiceren", 200),
            (self.anna, "concept-reviewen", 200),
            (self.anna, "omgevingen-en-toegang", 404),
            (self.baas, "omgevingen-en-toegang", 200),
            (self.baas, "bestaat-niet", 404),
        ):
            self.assertEqual(self.als(gebruiker).get(f"/hulp/{slug}/").status_code, code, (gebruiker, slug))

    def test_het_gekozen_artikel_staat_rechts_en_is_aangewezen_in_het_menu(self):
        r, html = self.hulp(self.anna, "/hulp/publiceren/")
        self.assertIn("<h1>Publiceren</h1>", html)
        self.assertIn("Moeten medewerkers dit weten?", html)
        self.assertEqual(html.count('aria-current="page"'), 2)  # de knop Hulp in de balk en dit artikel
        self.assertIn('<a href="/hulp/publiceren/" aria-current="page">Publiceren</a>', html)
        self.assertIn("<title>Publiceren – Hulp –", html)

    def test_zonder_inloggen_eerst_inloggen(self):
        self.client.logout()
        r = self.client.get("/hulp/publiceren/")
        self.assertEqual(r.status_code, 302)
        self.assertIn(
            "volgende=/hulp/publiceren/" if "volgende=" in r["Location"] else "next=/hulp/publiceren/", r["Location"]
        )

    def test_herkomst_kiest_het_hoofdstuk_maar_nooit_boven_je_rol(self):
        def eerste(gebruiker, bij):
            return self.hulp(gebruiker, bij=bij)[0].context["huidig"].doelgroep

        self.assertEqual(eerste(self.anna, "kennisbank"), "medewerker")
        self.assertEqual(eerste(self.anna, "review"), "reviewer")
        self.assertEqual(eerste(self.anna, "werkplek"), "redacteur")
        self.assertEqual(eerste(self.anna, "beheer"), "redacteur")  # mag hij niet zien: dan zijn eigen rol
        self.assertEqual(eerste(self.baas, "beheer"), "beheerder")
        self.assertEqual(eerste(self.baas, "kennisbank"), "medewerker")
        self.assertEqual(eerste(self.lies, "werkplek"), "medewerker")
        self.assertEqual(eerste(self.lies, "onzin"), "medewerker")

    def test_een_verborgen_artikel_staat_er_niet(self):
        Hulpartikel.objects.filter(slug="nieuws").update(zichtbaar=False)
        r, html = self.hulp(self.lies)
        self.assertNotIn("/hulp/nieuws/", html)
        self.assertEqual(self.client.get("/hulp/nieuws/").status_code, 404)
        self.assertEqual(self.als(self.baas).get("/hulp/nieuws/").status_code, 404)

    def test_zonder_artikelen_een_nette_lege_pagina(self):
        Hulpartikel.objects.all().delete()
        r, html = self.hulp(self.lies)
        self.assertIn("Er staan nog geen hulpartikelen.", html)

    def test_alleen_de_beheerder_krijgt_de_link_om_aan_te_passen(self):
        self.assertNotIn("Dit hulpartikel aanpassen", self.hulp(self.anna)[1])
        h = Hulpartikel.objects.get(slug="zoeken-en-lezen")
        self.assertIn(
            f'href="{LIJST}{h.pk}/change/">Dit hulpartikel aanpassen', self.hulp(self.baas, "/hulp/zoeken-en-lezen/")[1]
        )


# --- H1: de knop -------------------------------------------------------------------------------------------------


class Knop(HulpBasis):
    def test_op_de_site(self):
        html = self.als(self.lies).get("/").content.decode()
        self.assertIn('<a class="tb on-accent" id="lnkHulp" href="/hulp/?bij=kennisbank">Hulp</a>', html)

    def test_in_het_beheer_voor_de_redacteur_en_de_beheerder(self):
        self.assertIn('href="/hulp/?bij=werkplek">Hulp</a>', self.als(self.anna).get("/beheer/").content.decode())
        self.assertIn('href="/hulp/?bij=beheer">Hulp</a>', self.als(self.baas).get("/beheer/").content.decode())

    def test_op_de_reviewpagina(self):
        self.assertIn('href="/hulp/?bij=review">Hulp</a>', self.als(self.wim).get("/review/").content.decode())

    def test_op_de_hulppagina_zelf_staat_de_knop_aan(self):
        self.assertIn('href="/hulp/" aria-current="page">Hulp</a>', self.hulp(self.lies)[1])

    def test_in_het_bewerkscherm_opent_hulp_in_een_nieuw_tabblad(self):
        html = self.als(self.anna).get(f"/beheer/kennisbank/artikel/{self.artikel.pk}/change/").content.decode()
        self.assertRegex(
            html, r'<a class="kb-bk kb-bk-hulp" href="/hulp/\?bij=werkplek" target="_blank" rel="noopener">Hulp<'
        )
        self.assertIn("(opent in een nieuw tabblad)", html)
        html = self.client.get("/beheer/kennisbank/bericht/add/").content.decode()
        self.assertIn('href="/hulp/nieuwsbericht-plaatsen/" target="_blank"', html)
        self.assertEqual(self.client.get("/hulp/nieuwsbericht-plaatsen/").status_code, 200)

    def test_de_bestemmingen_van_de_knoppen_bestaan(self):
        self.assertEqual(set(hulp.BIJ), {"kennisbank", "review", "werkplek", "beheer"})
        for bij in hulp.BIJ:
            self.assertEqual(self.als(self.baas).get("/hulp/", {"bij": bij}).status_code, 200)


# --- H3: de meegeleverde artikelen --------------------------------------------------------------------------------


class Standaardset(TestCase):
    def test_na_migrate_staat_de_set_er(self):
        self.assertEqual(
            sorted(Hulpartikel.objects.values_list("slug", flat=True)), sorted(s["slug"] for s in STANDAARD)
        )
        self.assertFalse(Hulpartikel.objects.filter(aangepast=True).exists())
        self.assertTrue(all(h.zichtbaar for h in Hulpartikel.objects.all()))
        self.assertGreaterEqual(len(STANDAARD), 18)

    def test_elke_rol_heeft_artikelen_en_de_slugs_zijn_uniek(self):
        self.assertEqual({s["doelgroep"] for s in STANDAARD}, {"medewerker", "reviewer", "redacteur", "beheerder"})
        self.assertEqual(len({s["slug"] for s in STANDAARD}), len(STANDAARD))
        self.assertEqual(len({s["volgorde"] for s in STANDAARD}), len(STANDAARD))

    def test_nog_een_keer_laden_verandert_niets(self):
        voor = list(Hulpartikel.objects.order_by("pk").values("pk", "slug", "titel", "tekst", "volgorde"))
        self.assertEqual(hulp.laad_standaard(), {"nieuw": 0, "bijgewerkt": len(STANDAARD), "overgeslagen": 0})
        call_command("migrate", verbosity=0)
        self.assertEqual(
            list(Hulpartikel.objects.order_by("pk").values("pk", "slug", "titel", "tekst", "volgorde")), voor
        )

    def test_een_nieuwe_versie_werkt_de_tekst_bij_maar_niet_wat_zelf_is_aangepast(self):
        Hulpartikel.objects.filter(slug="nieuws").update(tekst="<p>Oude tekst van het pakket.</p>", titel="Oud")
        Hulpartikel.objects.filter(slug="assistent").update(tekst="<p>Onze eigen uitleg.</p>", aangepast=True)
        uit = hulp.laad_standaard()
        self.assertEqual(uit["overgeslagen"], 1)
        nieuws = Hulpartikel.objects.get(slug="nieuws")
        self.assertEqual(nieuws.titel, "Nieuws")
        self.assertIn("mededelingen van procesmanagement", nieuws.tekst)
        eigen = Hulpartikel.objects.get(slug="assistent")
        self.assertEqual((eigen.tekst, eigen.aangepast), ("<p>Onze eigen uitleg.</p>", True))

    def test_een_verwijderd_meegeleverd_artikel_komt_terug_en_een_eigen_artikel_blijft(self):
        Hulpartikel.objects.filter(slug="nieuws").delete()
        eigen = Hulpartikel.objects.create(slug="onze-uitleg", titel="Onze uitleg", tekst="<p>x</p>", aangepast=True)
        self.assertEqual(hulp.laad_standaard()["nieuw"], 1)
        self.assertTrue(Hulpartikel.objects.filter(slug="nieuws").exists())
        eigen.refresh_from_db()
        self.assertEqual(eigen.tekst, "<p>x</p>")

    def test_de_tekst_wordt_opgeschoond(self):
        h = Hulpartikel.objects.create(
            slug="x", titel="X", tekst='<p onclick="a()">Hoi <b>daar</b></p><script>alert(1)</script>'
        )
        self.assertEqual(h.tekst, "<p>Hoi <strong>daar</strong></p>")


class Woorden(TestCase):
    """De hulp gebruikt de woorden van de schermen. Zo veroudert hij niet stil."""

    VERBODEN = ["conceptversie", "spoedcorrectie", "kleine correctie", "werkbak", "terugkoppeling"]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        basis = Path(settings.BASE_DIR)
        delen = []
        for patroon in ("templates/**/*.html", "kennisbank/static/kennisbank/*.js", "kennisbank/*.py"):
            for pad in basis.glob(patroon):
                if pad.name not in ("hulp_inhoud.py",) and "vendor" not in pad.parts:
                    delen.append(pad.read_text(encoding="utf-8"))
        cls.schermen = htmllib.unescape("\n".join(delen))

    def test_geen_woorden_die_uit_de_schermen_zijn_gehaald(self):
        for s in STANDAARD:
            tekst = (s["titel"] + " " + s["tekst"]).lower()
            for woord in self.VERBODEN:
                self.assertNotIn(woord, tekst, s["slug"])

    def test_elke_vet_gedrukte_naam_staat_zo_op_een_scherm(self):
        mis = []
        for s in STANDAARD:
            for naam in re.findall(r"<strong>(.*?)</strong>", s["tekst"], flags=re.S):
                naam = htmllib.unescape(re.sub(r"\s+", " ", naam))
                if naam not in self.schermen:
                    mis.append((s["slug"], naam))
        self.assertEqual(mis, [])

    def test_elk_artikel_noemt_minstens_een_knop_en_blijft_kort(self):
        for s in STANDAARD:
            woorden = len(re.sub(r"<[^>]+>", " ", s["tekst"]).split())
            self.assertLess(woorden, 230, s["slug"])
            self.assertGreater(woorden, 40, s["slug"])
            self.assertIn("<strong>", s["tekst"], s["slug"])
            self.assertNotIn("<img", s["tekst"])
            self.assertNotIn("<h1", s["tekst"])


# --- Beheer van de hulpartikelen ---------------------------------------------------------------------------------


class Beheer(HulpBasis):
    def data(self, h, **anders):
        return {
            "titel": h.titel,
            "tekst": h.tekst,
            "doelgroep": h.doelgroep,
            "volgorde": h.volgorde,
            "slug": h.slug,
            "zichtbaar": "on" if h.zichtbaar else "",
            **anders,
        }

    def test_alleen_de_functioneel_beheerder(self):
        h = Hulpartikel.objects.get(slug="nieuws")
        for pad in (LIJST, f"{LIJST}add/", f"{LIJST}{h.pk}/change/"):
            self.assertEqual(self.als(self.baas).get(pad).status_code, 200, pad)
            self.assertEqual(self.als(self.anna).get(pad).status_code, 403, pad)
        r = self.als(self.anna).post(f"{LIJST}{h.pk}/change/", self.data(h, titel="Gekaapt"))
        self.assertEqual(r.status_code, 403)
        self.assertNotIn("Hulpartikelen", self.als(self.anna).get("/beheer/", {"bak": "alles"}).content.decode())
        self.assertIn("Hulpartikelen", self.als(self.baas).get("/beheer/", {"bak": "alles"}).content.decode())

    def test_het_bewerkscherm_is_dat_van_een_nieuwsbericht(self):
        h = Hulpartikel.objects.get(slug="nieuws")
        html = self.als(self.baas).get(f"{LIJST}{h.pk}/change/").content.decode()
        self.assertIn('class="kb-editor"', html)
        self.assertIn('<span class="kb-pil">Hulpartikel</span>', html)
        self.assertIn('href="/hulp/nieuws/" target="_blank"', html)
        self.assertNotIn("kb-afronden-knop", html)

    def test_tekst_aanpassen_zet_zelf_aangepast_en_een_nieuwe_versie_blijft_eraf(self):
        h = Hulpartikel.objects.get(slug="nieuws")
        r = self.als(self.baas).post(f"{LIJST}{h.pk}/change/", self.data(h, tekst="<p>Bij ons gaat nieuws anders.</p>"))
        self.assertEqual(r.status_code, 302)
        h.refresh_from_db()
        self.assertTrue(h.aangepast)
        hulp.laad_standaard()
        h.refresh_from_db()
        self.assertEqual(h.tekst, "<p>Bij ons gaat nieuws anders.</p>")
        self.assertIn("Bij ons gaat nieuws anders.", self.hulp(self.lies, "/hulp/nieuws/")[1])

    def test_alleen_volgorde_of_zichtbaarheid_wijzigen_is_geen_aanpassing(self):
        h = Hulpartikel.objects.get(slug="nieuws")
        self.als(self.baas).post(f"{LIJST}{h.pk}/change/", self.data(h, volgorde=5, zichtbaar=""))
        h.refresh_from_db()
        self.assertEqual((h.volgorde, h.zichtbaar, h.aangepast), (5, False, False))

    def test_een_eigen_artikel_toevoegen(self):
        r = self.als(self.baas).post(
            f"{LIJST}add/",
            {
                "titel": "Bellen met de helpdesk",
                "tekst": "<p>Bel 1234.</p>",
                "doelgroep": "medewerker",
                "volgorde": 5,
                "slug": "bellen-met-de-helpdesk",
                "zichtbaar": "on",
            },
        )
        self.assertEqual(r.status_code, 302)
        h = Hulpartikel.objects.get(slug="bellen-met-de-helpdesk")
        self.assertTrue(h.aangepast)
        r, html = self.hulp(self.lies)
        self.assertEqual(menu(html)[0][1][0], ("/hulp/bellen-met-de-helpdesk/", "Bellen met de helpdesk"))
        self.assertIn("eigen artikel", self.als(self.baas).get(LIJST).content.decode())

    def test_standaardtekst_terugzetten(self):
        h = Hulpartikel.objects.get(slug="nieuws")
        Hulpartikel.objects.filter(pk=h.pk).update(tekst="<p>Eigen.</p>", aangepast=True, zichtbaar=False)
        eigen = Hulpartikel.objects.create(slug="eigen", titel="Eigen", tekst="<p>Blijft.</p>", aangepast=True)
        ander = Hulpartikel.objects.get(slug="assistent")
        Hulpartikel.objects.filter(pk=ander.pk).update(tekst="<p>Ook eigen.</p>", aangepast=True)
        r = self.als(self.baas).post(
            LIJST, {"action": "standaardtekst_terugzetten", "_selected_action": [h.pk, eigen.pk]}, follow=True
        )
        meldingen = " ".join(str(m) for m in r.context["messages"])
        self.assertIn("1 hulpartikel(en) teruggezet", meldingen)
        self.assertIn("1 artikel(en) overgeslagen", meldingen)
        h.refresh_from_db()
        self.assertIn("mededelingen van procesmanagement", h.tekst)
        self.assertEqual((h.aangepast, h.zichtbaar), (False, True))
        eigen.refresh_from_db()
        ander.refresh_from_db()
        self.assertEqual((eigen.tekst, ander.tekst), ("<p>Blijft.</p>", "<p>Ook eigen.</p>"))  # niet gekozen: blijft


# --- H4: de eigen werkafspraken van de afdeling -------------------------------------------------------------------


class Werkafspraken(HulpBasis):
    def wijs_aan(self, omgeving, artikel):
        omgeving.werkafspraken_artikel = artikel
        omgeving.save()

    def test_zonder_aangewezen_artikel_geen_kop(self):
        self.assertNotIn("Zo werken wij", self.hulp(self.lies)[1])

    def test_lezers_van_de_omgeving_zien_de_link_bovenaan(self):
        self.wijs_aan(self.noord, self.artikel)
        for gebruiker in (self.lies, self.anna, self.baas):
            r, html = self.hulp(gebruiker)
            self.assertEqual(
                menu(html)[0], ["Zo werken wij", [(f"/artikel/{self.artikel.pk}/{self.artikel.slug}", "Rappel")]]
            )

    def test_wie_de_omgeving_niet_mag_lezen_ziet_niets(self):
        self.wijs_aan(self.noord, self.artikel)
        for gebruiker in (self.zoe, self.wim):  # redacteur van Zuid; reviewer zonder leesrecht
            html = self.hulp(gebruiker)[1]
            self.assertNotIn("Zo werken wij", html)
            self.assertNotIn("Rappel", html.split("<main")[0].split("hulp-menu")[1])

    def test_alleen_een_gepubliceerd_artikel_uit_de_eigen_omgeving(self):
        self.wijs_aan(self.noord, self.concept)
        self.assertNotIn("Zo werken wij", self.hulp(self.lies)[1])
        self.wijs_aan(self.noord, self.artikel)
        type(self.artikel).objects.filter(pk=self.artikel.pk).update(status=Status.GEARCHIVEERD)
        self.assertNotIn("Zo werken wij", self.hulp(self.lies)[1])
        type(self.artikel).objects.filter(pk=self.artikel.pk).update(status=Status.GEPUBLICEERD, omgeving=self.zuid)
        self.assertNotIn("Zo werken wij", self.hulp(self.lies)[1])
        self.assertNotIn("Zo werken wij", self.hulp(self.zoe)[1])  # verhuisd: ook niet bij de nieuwe omgeving

    def test_bij_meer_omgevingen_staat_de_naam_erbij(self):
        self.wijs_aan(self.noord, self.artikel)
        self.wijs_aan(self.zuid, self.artikel_zuid)
        html = self.hulp(self.baas)[1]
        self.assertIn('<span class="hulp-omgeving">(Noord)</span>', html)
        self.assertIn('<span class="hulp-omgeving">(Zuid)</span>', html)
        self.assertNotIn("hulp-omgeving", self.hulp(self.lies)[1])

    def test_de_beheerder_kiest_alleen_uit_gepubliceerde_artikelen_van_die_omgeving(self):
        html = self.als(self.baas).get(f"/beheer/kennisbank/omgeving/{self.noord.pk}/change/").content.decode()
        veld = html[html.index('id="id_werkafspraken_artikel"') :]
        veld = veld[: veld.index("</select>")]
        self.assertIn(f'value="{self.artikel.pk}"', veld)
        self.assertNotIn(f'value="{self.concept.pk}"', veld)
        self.assertNotIn(f'value="{self.artikel_zuid.pk}"', veld)
        nieuw = self.client.get("/beheer/kennisbank/omgeving/add/").content.decode()
        self.assertNotIn(f'value="{self.artikel.pk}"', nieuw)

    def test_een_verwijderd_artikel_laat_de_omgeving_heel(self):
        self.wijs_aan(self.noord, self.artikel_zuid)  # mag weg zonder dat er werk aan hangt
        self.artikel_zuid.delete()
        self.noord.refresh_from_db()
        self.assertIsNone(self.noord.werkafspraken_artikel)
