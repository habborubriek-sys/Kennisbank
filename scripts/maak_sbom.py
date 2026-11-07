#!/usr/bin/env python
"""Maakt sbom.cdx.json: de Python-afhankelijkheden (via cyclonedx-py) plus de meegeleverde
frontend-bibliotheken uit kennisbank/static/kennisbank/vendor/componenten.json.

Gebruik: python scripts/maak_sbom.py [uitvoerbestand]
"""

import json
import pathlib
import subprocess
import sys

WORTEL = pathlib.Path(__file__).resolve().parent.parent
COMPONENTEN = WORTEL / "kennisbank/static/kennisbank/vendor/componenten.json"


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
    pad.write_text(json.dumps(sbom, indent=2, ensure_ascii=False) + "\n")
    print(f"{pad}: {len(sbom['components'])} componenten")


if __name__ == "__main__":
    main(*sys.argv[1:])
