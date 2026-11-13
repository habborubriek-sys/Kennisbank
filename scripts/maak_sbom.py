#!/usr/bin/env python
"""Maakt sbom.cdx.json: de Python-afhankelijkheden (via cyclonedx-py) plus de meegeleverde frontend.

De frontend is één bundel (kennisbank/static/kennisbank/vendor/tiptap/tiptap.min.js). Sinds 1.32.0 staat elk
pakket dat in die bundel zit apart in de SBOM, zodat een scanner een kwetsbaarheid in bijvoorbeeld
prosemirror-view ook vindt. Welke pakketten erin zitten, staat in vendor/tiptap/LICENSES.txt; de versies
komen uit frontend/package-lock.json. De kennisbank zelf staat in metadata.component.

Gebruik: python scripts/maak_sbom.py [uitvoerbestand]
"""

import json
import pathlib
import re
import subprocess
import sys

WORTEL = pathlib.Path(__file__).resolve().parent.parent
VENDOR = WORTEL / "kennisbank/static/kennisbank/vendor"
COMPONENTEN = VENDOR / "componenten.json"
LICENTIES = VENDOR / "tiptap/LICENSES.txt"
LOCK = WORTEL / "frontend/package-lock.json"


def versie() -> str:
    tekst = (WORTEL / "kennisbank/__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__ = "([^"]+)"', tekst).group(1)


def bundelpakketten() -> list[dict]:
    """De pakketten in de Tiptap-bundel: naam en licentie uit LICENSES.txt, versie uit het lockbestand."""
    lock = json.loads(LOCK.read_text(encoding="utf-8"))["packages"]
    pakketten = []
    koppen = re.findall(r"^==== (\S+) (\S+) \(([^)]+)\) ====$", LICENTIES.read_text(encoding="utf-8"), re.M)
    for naam, v, licentie in koppen:
        in_lock = lock.get(f"node_modules/{naam}", {}).get("version")
        if in_lock != v:
            raise SystemExit(f"{naam}: LICENSES.txt zegt {v}, package-lock.json zegt {in_lock}. Werk LICENSES.txt bij.")
        pakketten.append({"naam": naam, "versie": v, "licentie": licentie})
    return pakketten


def purl(naam: str, v: str) -> str:
    return "pkg:npm/" + naam.replace("@", "%40") + "@" + v


def main(uit: str = "sbom.cdx.json") -> None:
    pad = WORTEL / uit
    subprocess.run(  # noqa: S603 - vaste argumenten, geen gebruikersinvoer
        [sys.executable, "-m", "cyclonedx_py", "requirements", str(WORTEL / "requirements.txt"), "-o", str(pad)],
        check=True,
    )
    sbom = json.loads(pad.read_text())
    for c in json.loads(COMPONENTEN.read_text())["componenten"]:
        sbom["components"].append(
            {
                "bom-ref": f"vendor-{c['naam']}",
                "type": "library",
                "name": c["naam"],
                "version": c["versie"],
                "purl": c["purl"],
                "description": c["doel"],
                "licenses": [{"license": {"id": c["licentie"]}}],
                "externalReferences": [{"type": "website", "url": c["bron"].split(" ")[0]}],
            }
        )
    # Elk pakket in de bundel apart. Het pakket dat componenten.json al noemt (de bundel zelf, @tiptap/core),
    # komt er niet dubbel in.
    al = {c.get("purl") for c in sbom["components"]}
    in_bundel = []
    for p in bundelpakketten():
        ref = purl(p["naam"], p["versie"])
        if ref in al:
            continue
        in_bundel.append(f"npm-{p['naam']}")
        sbom["components"].append(
            {
                "bom-ref": f"npm-{p['naam']}",
                "type": "library",
                "name": p["naam"],
                "version": p["versie"],
                "purl": ref,
                "licenses": [{"license": {"id": p["licentie"]}}],
                "properties": [{"name": "kennisbank:bundel", "value": "vendor/tiptap/tiptap.min.js"}],
            }
        )
    sbom.setdefault("dependencies", []).append({"ref": "vendor-tiptap", "dependsOn": sorted(in_bundel)})
    sbom.setdefault("metadata", {})["component"] = {
        "bom-ref": "kennisbank",
        "type": "application",
        "name": "kennisbank",
        "version": versie(),
        "licenses": [{"license": {"id": "EUPL-1.2"}}],
    }
    pad.write_text(json.dumps(sbom, indent=2, ensure_ascii=False) + "\n")
    print(f"{pad}: {len(sbom['components'])} componenten")


if __name__ == "__main__":
    main(*sys.argv[1:])
