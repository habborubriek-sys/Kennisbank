"""1.32.0, ronde D van de review van 12 november: strengere CSP in het beheer (M9), SBOM (M27) en de CI-punten.

Bouwlijst `bouwlijst-1.32.0-ronde-d.md`. De browsertests zelf staan in scripts/browsertests/ en draaien in de CI.
"""

import json
import pathlib
import re

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from kennisbank import __version__
from kennisbank.tests.test_kennisbank import Basis, pk_van

WORTEL = pathlib.Path(__file__).resolve().parents[2]
VENDOR = WORTEL / "kennisbank/static/kennisbank/vendor"


def csp(antwoord) -> dict:
    """De Content-Security-Policy als woordenboek: richtlijn -> waarden."""
    delen = [d.strip().split(" ") for d in antwoord["Content-Security-Policy"].split(";") if d.strip()]
    return {d[0]: d[1:] for d in delen}


# --- D2: strengere CSP in het beheer (M9) -----------------------------------------------------------------


class CspBeheer(Basis):
    def test_d2_het_beheer_staat_geen_inline_scripts_toe(self):
        self.als(self.redacteur)
        for pad in (
            "/beheer/",
            "/beheer/kennisbank/artikel/",
            "/beheer/kennisbank/artikel/add/",
            f"/beheer/kennisbank/artikel/{pk_van('rappel-versturen')}/change/",
            "/beheer/kennisbank/bericht/add/",
        ):
            r = self.client.get(pad)
            self.assertEqual(r.status_code, 200, pad)
            regels = csp(r)
            self.assertEqual(regels["script-src"], ["'self'"], pad)
            self.assertEqual(regels["style-src"], ["'self'"], pad)
            self.assertEqual(regels["object-src"], ["'none'"], pad)
            self.assertEqual(regels["base-uri"], ["'self'"], pad)
            # Het beheer wordt nooit ingebed, ook niet door het zaaksysteem.
            self.assertEqual(regels["frame-ancestors"], ["'self'"], pad)

    def test_d2_stijl_attributen_mogen_wel_voor_tabellen_in_de_editor(self):
        """Tiptap zet bij een tabel een style-attribuut op <table> en <col>. Een <style>-element mag niet."""
        self.als(self.redacteur)
        regels = csp(self.client.get("/beheer/"))
        self.assertEqual(regels["style-src-attr"], ["'unsafe-inline'"])
        self.assertNotIn("'unsafe-inline'", regels["style-src"])

    def test_d2_ook_de_inlogpagina_en_een_foutpagina_van_het_beheer(self):
        r = self.client.get("/beheer/login/")
        self.assertEqual(csp(r)["script-src"], ["'self'"])
        self.als(self.redacteur)
        r = self.client.get("/beheer/kennisbank/artikel/999999/change/")
        self.assertEqual(csp(r)["script-src"], ["'self'"])

    def test_d2_alleen_de_api_documentatie_houdt_de_ruime_regel(self):
        self.als(self.lezer)
        r = self.client.get("/api/docs/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("'unsafe-inline'", csp(r)["script-src"])

    def test_d2_de_site_is_niet_veranderd(self):
        self.als(self.lezer)
        regels = csp(self.client.get("/zaaktype/Melding"))
        self.assertEqual(regels["script-src"], ["'self'"])
        self.assertEqual(regels["style-src"], ["'self'"])
        self.assertNotIn("style-src-attr", regels)

    def test_d2_het_bewerkscherm_heeft_geen_inline_stijl_of_script(self):
        self.als(self.redacteur)
        for pad in ("/beheer/kennisbank/artikel/add/", "/beheer/kennisbank/bericht/add/", "/beheer/"):
            html = self.client.get(pad).content.decode()
            self.assertNotRegex(html, r"<style[\s>]", pad)
            self.assertNotRegex(html, r'\sstyle="', pad)
            self.assertNotRegex(html, r'\son[a-z]+="', pad)
            # Een script zonder src mag alleen gegevens zijn (json_script).
            for kop in re.findall(r"<script\b[^>]*>", html):
                self.assertTrue("src=" in kop or 'type="application/json"' in kop, f"{pad}: {kop}")


class GeenInlineInSjablonen(SimpleTestCase):
    """De eigen sjablonen van het beheer hebben niets inline; anders houdt de CSP het tegen."""

    def test_d2_sjablonen_van_het_beheer(self):
        for pad in sorted((WORTEL / "templates/admin").rglob("*.html")):
            tekst = pad.read_text(encoding="utf-8")
            naam = str(pad.relative_to(WORTEL))
            self.assertNotRegex(tekst, r"<style[\s>]", naam)
            self.assertNotRegex(tekst, r'\sstyle="', naam)
            self.assertNotRegex(tekst, r'\son(click|change|submit|load|input)="', naam)
            for kop in re.findall(r"<script\b[^>]*>", tekst):
                self.assertTrue("src=" in kop or "application/json" in kop, f"{naam}: {kop}")

    def test_d2_velden_in_het_formulier_hebben_geen_style_attribuut(self):
        admin_py = (WORTEL / "kennisbank/admin.py").read_text(encoding="utf-8")
        self.assertNotRegex(admin_py, r'attrs=\{[^}]*"style"')

    def test_d2_tiptap_voegt_geen_stijl_in(self):
        js = (WORTEL / "kennisbank/static/kennisbank/artikel-editor.js").read_text(encoding="utf-8")
        self.assertIn("injectCSS: false", js)
        admin_py = (WORTEL / "kennisbank/admin.py").read_text(encoding="utf-8")
        self.assertEqual(admin_py.count("vendor/tiptap/tiptap.css"), 2, "artikelen en nieuwsberichten")

    def test_d2_de_basisstijl_van_tiptap_hoort_bij_de_versie_van_de_bundel(self):
        versie = json.loads((VENDOR / "componenten.json").read_text())["componenten"][0]["versie"]
        css = (VENDOR / "tiptap/tiptap.css").read_text(encoding="utf-8")
        self.assertIn(f"Basisstijl van Tiptap {versie} ", css[:200])
        self.assertIn(".ProseMirror {", css)
        self.assertIn("white-space: pre-wrap", css)


# --- D4: SBOM (M27) en D5: de bundel ----------------------------------------------------------------------


class SbomEnBundel(SimpleTestCase):
    def licenties(self):
        tekst = (VENDOR / "tiptap/LICENSES.txt").read_text(encoding="utf-8")
        return re.findall(r"^==== (\S+) (\S+) \(([^)]+)\) ====$", tekst, re.M)

    def lock(self):
        return json.loads((WORTEL / "frontend/package-lock.json").read_text(encoding="utf-8"))["packages"]

    def test_d4_elk_pakket_uit_de_bundel_staat_in_de_sbom(self):
        sbom = json.loads((WORTEL / "sbom.cdx.json").read_text(encoding="utf-8"))
        purls = {c.get("purl") for c in sbom["components"]}
        pakketten = self.licenties()
        self.assertGreaterEqual(len(pakketten), 30)
        for naam, versie, _licentie in pakketten:
            purl = "pkg:npm/" + naam.replace("@", "%40") + "@" + versie
            self.assertIn(purl, purls, f"{naam} {versie} ontbreekt in sbom.cdx.json; draai scripts/maak_sbom.py")

    def test_d4_de_sbom_noemt_de_kennisbank_zelf_met_de_huidige_versie(self):
        sbom = json.loads((WORTEL / "sbom.cdx.json").read_text(encoding="utf-8"))
        zelf = sbom["metadata"]["component"]
        self.assertEqual((zelf["name"], zelf["type"]), ("kennisbank", "application"))
        self.assertEqual(zelf["version"], __version__, "draai scripts/maak_sbom.py na het ophogen van de versie")

    def test_d5_licentielijst_en_lockbestand_noemen_dezelfde_versies(self):
        lock = self.lock()
        for naam, versie, _licentie in self.licenties():
            self.assertEqual(lock[f"node_modules/{naam}"]["version"], versie, naam)
        # Alles in de licentielijst is een echte afhankelijkheid, geen bouwgereedschap.
        for naam, _versie, _licentie in self.licenties():
            self.assertFalse(lock[f"node_modules/{naam}"].get("dev"), naam)

    def test_d5_de_banner_van_de_bundel_klopt_met_lockbestand_en_bouwopdracht(self):
        """De banner werd met de hand bijgehouden (review 1.27.0). Nu bewaakt een test hem."""
        lock = self.lock()
        kern = lock["node_modules/@tiptap/core"]["version"]
        kop = (VENDOR / "tiptap/tiptap.min.js").read_text(encoding="utf-8", errors="replace")[:300]
        self.assertIn(f"Version: {kern}.", kop)
        pakket = json.loads((WORTEL / "frontend/package.json").read_text(encoding="utf-8"))
        self.assertIn(f"Version: {kern}.", pakket["scripts"]["bouw"])
        self.assertEqual(pakket["dependencies"]["@tiptap/core"], kern)
        # Alle pakketten van Tiptap zelf hebben dezelfde versie.
        for naam, v in lock.items():
            if naam.startswith("node_modules/@tiptap/"):
                self.assertEqual(v["version"], kern, naam)


# --- D1: de opdracht voor de browsertests -----------------------------------------------------------------


class BrowsertestOpdracht(SimpleTestCase):
    @override_settings(KB_DEMO_MODUS=False)
    def test_d1_alleen_in_demo_modus(self):
        """De opdracht maakt een eigen database en demo-accounts; op een echte installatie doet hij niets."""
        with self.assertRaisesMessage(CommandError, "KB_DEMO_MODUS"):
            call_command("kennisbank_browsertest", "--geen-server")

    def test_d1_de_versies_van_playwright_en_axe_liggen_vast(self):
        pakket = json.loads((WORTEL / "scripts/browsertests/package.json").read_text(encoding="utf-8"))
        for naam, versie in pakket["dependencies"].items():
            self.assertRegex(versie, r"^\d+\.\d+\.\d+$", f"{naam}: leg een exacte versie vast")
        self.assertTrue((WORTEL / "scripts/browsertests/package-lock.json").exists())

    def test_d1_de_ci_draait_de_browsertests(self):
        ci = (WORTEL / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/browsertests/draai.sh", ci)


class StilleTests(SimpleTestCase):
    def test_d5_tijdens_de_tests_geen_logregels_in_de_uitvoer(self):
        import logging

        self.assertGreaterEqual(logging.getLogger().level, logging.CRITICAL)


class Documentatie(SimpleTestCase):
    def test_d3_verwijzingen_in_de_documentatie_bestaan(self):
        """Een link naar een bestand dat er niet (meer) is, valt anders pas op als iemand erop klikt."""
        for pad in [
            WORTEL / "README.md",
            WORTEL / "SECURITY.md",
            *sorted((WORTEL / "docs").glob("*.md")),
            WORTEL / "scripts/browsertests/README.md",
            WORTEL / "frontend/README.md",
        ]:
            for doel in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", pad.read_text(encoding="utf-8")):
                if re.match(r"[a-z]+:", doel):
                    continue
                self.assertTrue((pad.parent / doel).exists(), f"{pad.relative_to(WORTEL)} verwijst naar {doel}")

    def test_d3_de_voorbeelden_noemen_de_huidige_versie(self):
        tekst = (WORTEL / "docs/installatie-en-beheer.md").read_text(encoding="utf-8")
        self.assertIn(f"kennisbank:{__version__}", tekst)
        andere = rf"registry\.example\.nl/kennisbank:(?!{re.escape(__version__)})\d"
        self.assertNotRegex(tekst, andere)
        self.assertNotIn("op dit moment 1.", (WORTEL / "SECURITY.md").read_text(encoding="utf-8"))
