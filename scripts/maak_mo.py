"""Zet de .po-bestanden in kennisbank/locale om naar .mo, zonder dat GNU gettext nodig is.

Alleen voor eenvoudige bestanden zonder meervoudsvormen of context (zoals djangojs.po hier).
Gebruik: python scripts/maak_mo.py
"""

import ast
import struct
from pathlib import Path

BASIS = Path(__file__).resolve().parent.parent / "kennisbank" / "locale"


def lees_po(pad: Path) -> dict[str, str]:
    paren, sleutel, waarde, huidig = {}, None, None, None
    for regel in pad.read_text(encoding="utf-8").splitlines() + [""]:
        regel = regel.strip()
        if regel.startswith("msgid "):
            if sleutel is not None:
                paren[sleutel] = waarde
            sleutel, waarde, huidig = ast.literal_eval(regel[6:]), "", "id"
        elif regel.startswith("msgstr "):
            waarde, huidig = ast.literal_eval(regel[7:]), "str"
        elif regel.startswith('"'):
            stuk = ast.literal_eval(regel)
            if huidig == "id":
                sleutel += stuk
            else:
                waarde += stuk
    if sleutel is not None:
        paren[sleutel] = waarde
    return paren


def schrijf_mo(paren: dict[str, str], pad: Path) -> None:
    sleutels = sorted(paren)
    ids = [k.encode("utf-8") for k in sleutels]
    strs = [paren[k].encode("utf-8") for k in sleutels]
    n = len(sleutels)
    begin_ids = 7 * 4 + 16 * n
    tabel_ids, tabel_strs, data = [], [], b""
    for b in ids:
        tabel_ids.append((len(b), begin_ids + len(data)))
        data += b + b"\0"
    for b in strs:
        tabel_strs.append((len(b), begin_ids + len(data)))
        data += b + b"\0"
    kop = struct.pack("<7I", 0x950412DE, 0, n, 7 * 4, 7 * 4 + 8 * n, 0, 0)
    inhoud = kop + b"".join(struct.pack("<2I", *t) for t in tabel_ids)
    inhoud += b"".join(struct.pack("<2I", *t) for t in tabel_strs) + data
    pad.write_bytes(inhoud)


if __name__ == "__main__":
    for po in BASIS.glob("*/LC_MESSAGES/*.po"):
        schrijf_mo(lees_po(po), po.with_suffix(".mo"))
        print(f"{po.with_suffix('.mo')} geschreven")
