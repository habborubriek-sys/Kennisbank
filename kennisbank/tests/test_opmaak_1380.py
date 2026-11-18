"""1.38.0 – de opmaak is compact en overal gelijk: één vaste set maten in fonts.css.

Wat er op het scherm staat, meet de browsertest (rook.js). Hier staat vast dat de stijlbestanden zelf geen
losse maten meer bevatten, zodat een nieuwe regel niet ongemerkt een zesde lettergrootte toevoegt.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

STATIC = Path(settings.BASE_DIR) / "kennisbank" / "static" / "kennisbank"
EIGEN = sorted(p for p in STATIC.glob("*.css") if p.name != "fonts.css")


def zonder_commentaar(tekst):
    return re.sub(r"/\*.*?\*/", "", tekst, flags=re.S)


class VasteSetMaten(SimpleTestCase):
    def test_de_set_staat_op_een_plek(self):
        fonts = zonder_commentaar((STATIC / "fonts.css").read_text(encoding="utf-8"))
        gevonden = dict(re.findall(r"(--kb-fs-\w+):\s*([^;]+);", fonts))
        self.assertEqual(
            gevonden,
            {
                "--kb-fs-xs": ".75rem",
                "--kb-fs-s": ".875rem",
                "--kb-fs-m": "1rem",
                "--kb-fs-l": "1.125rem",
                "--kb-fs-xl": "1.5rem",
            },
        )
        self.assertIn("--kb-knop-h:32px", fonts)
        self.assertIn("--kb-balk-h:52px", fonts)

    def test_niets_kleiner_dan_twaalf_pixels(self):
        fonts = zonder_commentaar((STATIC / "fonts.css").read_text(encoding="utf-8"))
        for naam, waarde in re.findall(r"(--kb-fs-\w+):\s*([\d.]+)rem", fonts):
            self.assertGreaterEqual(float(waarde) * 16, 12, naam)

    def test_op_een_aanraakscherm_blijven_knoppen_groot(self):
        fonts = zonder_commentaar((STATIC / "fonts.css").read_text(encoding="utf-8"))
        blok = re.search(r"@media \(pointer:coarse\)\{(.*?)\}\s*\}", fonts, flags=re.S)
        self.assertIsNotNone(blok, "fonts.css mist het blok voor aanraakschermen")
        hoogte = re.search(r"--kb-knop-h:(\d+)px", blok.group(1))
        self.assertIsNotNone(hoogte)
        self.assertGreaterEqual(int(hoogte.group(1)), 44)

    def test_geen_losse_lettergrootte_in_de_stijlbestanden(self):
        self.assertGreaterEqual(len(EIGEN), 9)
        for pad in EIGEN:
            tekst = zonder_commentaar(pad.read_text(encoding="utf-8"))
            # De afdrukopmaak rekent in punten; dat is papier, geen scherm.
            tekst = re.sub(r"@media print\s*\{.*?\n\}", "", tekst, flags=re.S)
            for waarde in re.findall(r"font-size:\s*([^;}!]+)", tekst):
                waarde = waarde.strip()
                relatief = waarde.endswith("em") and not waarde.endswith("rem")
                self.assertTrue(
                    waarde.startswith("var(--kb-fs-") or relatief or waarde == "inherit",
                    f"{pad.name}: font-size:{waarde} — gebruik een van de vijf maten uit fonts.css",
                )
            for waarde in re.findall(r"font:\s*([^;}]+)", tekst):
                melding = f"{pad.name}: font:{waarde} — gebruik var(--kb-fs-…)"
                self.assertNotRegex(waarde, r"\d(px|rem)\b(?!\))", melding)

    def test_de_balk_en_de_knoppen_gebruiken_de_vaste_hoogte(self):
        for naam in ("app.css", "bovenbalk.css"):
            tekst = zonder_commentaar((STATIC / naam).read_text(encoding="utf-8"))
            self.assertIn("min-height:var(--kb-balk-h)", tekst.replace(" ", ""), naam)
            self.assertIn("min-height:var(--kb-knop-h)", tekst.replace(" ", ""), naam)

    def test_elke_pagina_laadt_de_vaste_set(self):
        sjablonen = Path(settings.BASE_DIR) / "templates"
        gezien = 0
        for pad in sjablonen.rglob("*.html"):
            tekst = pad.read_text(encoding="utf-8")
            if re.search(r"kennisbank/(app|bovenbalk|beheer|hulp|review)\.css", tekst):
                gezien += 1
                self.assertIn("kennisbank/fonts.css", tekst, f"{pad.name} laadt fonts.css niet")
        self.assertGreaterEqual(gezien, 8)

    def test_het_beheer_heeft_het_lettertype_van_de_site(self):
        beheer = zonder_commentaar((STATIC / "beheer.css").read_text(encoding="utf-8"))
        self.assertRegex(beheer, r'--font-family-primary:"Source Sans 3"')
