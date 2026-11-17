#!/usr/bin/env bash
# Maakt de schermafbeeldingen voor de hulpartikelen opnieuw (kennisbank/static/kennisbank/hulp/*.png).
#
# Draai dit als een scherm is veranderd dat in de hulp staat, en in elk geval voor een release:
#     scripts/browsertests/hulpbeelden.sh
# Daarna de gewijzigde bestanden vastleggen. Nodig: hetzelfde als voor draai.sh, plus Pillow (zit in de
# ontwikkelpakketten) om de bestanden te verkleinen.
set -u
hier="$(cd "$(dirname "$0")" && pwd)"
wortel="$(cd "$hier/../.." && pwd)"
poort="${KB_BROWSERTEST_POORT:-8766}"
export KB_DEMO_MODUS=aan KB_DEBUG="${KB_DEBUG:-1}" KB_LOG_NIVEAU="${KB_LOG_NIVEAU:-WARNING}"
export KB_ALLOWED_HOSTS="${KB_ALLOWED_HOSTS:-localhost,127.0.0.1}"
export KB_URL="http://127.0.0.1:$poort" KB_OPZET="$hier/.opzet-hulp.json"
doel="$wortel/kennisbank/static/kennisbank/hulp"
mkdir -p "$doel"
rm -f "$KB_OPZET"
(cd "$wortel" && exec python manage.py kennisbank_browsertest --voor-hulp --poort "$poort" --opzet "$KB_OPZET") >"$hier/.server-hulp.log" 2>&1 &
server=$!
for _ in $(seq 1 90); do
  [ -s "$KB_OPZET" ] && curl -fs -o /dev/null "$KB_URL/readyz" && break
  kill -0 "$server" 2>/dev/null || break
  sleep 1
done
if ! curl -fs -o /dev/null "$KB_URL/readyz"; then
  echo "De testserver start niet. Laatste regels van het logboek:"; tail -20 "$hier/.server-hulp.log"
  kill "$server" 2>/dev/null; exit 1
fi
uit=0
(cd "$hier" && node hulpbeelden.js) || uit=1
kill "$server" 2>/dev/null; wait "$server" 2>/dev/null
# Verkleinen: minder kleuren is voor een schermafbeelding niet te zien en scheelt driekwart van de omvang.
python - "$doel" <<'PY' || uit=1
import sys
from pathlib import Path
from PIL import Image
totaal = 0
for pad in sorted(Path(sys.argv[1]).glob("*.png")):
    beeld = Image.open(pad).convert("RGB").quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    beeld.save(pad, optimize=True)
    totaal += pad.stat().st_size
print(f"Verkleind; samen {totaal // 1024} kB.")
PY
exit $uit
