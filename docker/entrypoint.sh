#!/bin/sh
# Startpunt van de container.
#   web                 database migreren (tenzij KB_MIGREER_BIJ_START=nee) en webserver starten
#   migreer             alleen database migreren (bijv. als Kubernetes Job)
#   opschonen           bewaartermijnen uitvoeren (dagelijks inplannen)
#   beheer <commando>   willekeurig beheercommando, bijv.: beheer kennisbank_import /data/artikelen.json
set -e

is_aan() { case "$(echo "$1" | tr '[:upper:]' '[:lower:]')" in 1|ja|aan|true|yes|on) return 0;; *) return 1;; esac; }

case "$1" in
  web)
    if ! is_aan "${KB_MIGREER_BIJ_START:-ja}"; then :; else python manage.py migrate --noinput; fi
    if is_aan "${KB_DEMO_MODUS:-nee}"; then python manage.py kennisbank_demo; fi
    exec gunicorn config.wsgi:application \
      --bind "0.0.0.0:${KB_POORT:-8000}" \
      --workers "${KB_WORKERS:-3}" \
      --timeout "${KB_TIMEOUT_SECONDEN:-60}" \
      --worker-tmp-dir /dev/shm \
      --no-control-socket \
      --forwarded-allow-ips="${KB_FORWARDED_ALLOW_IPS:-*}" \
      --access-logfile - \
      --access-logformat '{"tijd":"%(t)s","methode":"%(m)s","pad":"%(U)s","status":%(s)s,"duur_ms":%(M)s}'
    ;;
  migreer) exec python manage.py migrate --noinput ;;
  opschonen) exec python manage.py kennisbank_opschonen ;;
  beheer) shift; exec python manage.py "$@" ;;
  *) exec "$@" ;;
esac
