#!/usr/bin/env bash
# Draait de browsertests: start een server op een wegwerpdatabase met vaste testgegevens, meet de
# toegankelijkheid (axe.js) en loopt daarna de belangrijkste paden af (rook.js).
#
# Gebruik, vanuit de hoofdmap van de repository:   scripts/browsertests/draai.sh
# Nodig: PostgreSQL (KB_DATABASE_URL), de Python-pakketten, en in deze map `npm ci` + een Chromium
# (`npx playwright install chromium`, of KB_CHROME=<pad naar Chrome>).
#
# Mislukt een ronde, dan volgt één herhaling op een verse database (keuze van Alex, 13 november 2026:
# de browsertests houden een push tegen, met één herhaling tegen toevallige storingen).
set -u
hier="$(cd "$(dirname "$0")" && pwd)"
wortel="$(cd "$hier/../.." && pwd)"
poort="${KB_BROWSERTEST_POORT:-8765}"
export KB_DEMO_MODUS=aan KB_DEBUG="${KB_DEBUG:-1}" KB_LOG_NIVEAU="${KB_LOG_NIVEAU:-WARNING}"
export KB_ALLOWED_HOSTS="${KB_ALLOWED_HOSTS:-localhost,127.0.0.1}"
export KB_URL="http://127.0.0.1:$poort" KB_OPZET="$hier/.opzet.json"

ronde() {
  rm -f "$KB_OPZET"
  (cd "$wortel" && exec python manage.py kennisbank_browsertest --poort "$poort" --opzet "$KB_OPZET") >"$hier/.server.log" 2>&1 &
  server=$!
  for _ in $(seq 1 90); do
    [ -s "$KB_OPZET" ] && curl -fs -o /dev/null "$KB_URL/readyz" && break
    kill -0 "$server" 2>/dev/null || break
    sleep 1
  done
  if ! curl -fs -o /dev/null "$KB_URL/readyz"; then
    echo "De testserver start niet. Laatste regels van het logboek:"; tail -20 "$hier/.server.log"
    kill "$server" 2>/dev/null; return 1
  fi
  uit=0
  (cd "$hier" && node axe.js) || uit=1
  (cd "$hier" && node rook.js) || uit=1
  kill "$server" 2>/dev/null; wait "$server" 2>/dev/null
  return $uit
}

if ronde; then echo "Browsertests geslaagd."; exit 0; fi
echo; echo "=== Een ronde mislukte; één herhaling op een verse database ==="; echo
if ronde; then echo "Browsertests geslaagd bij de herhaling. Kijk hierboven wat de eerste keer misging."; exit 0; fi
echo "Browsertests mislukt, ook bij de herhaling."; exit 1
