"""Kleine hulpfuncties om omgevingsvariabelen te lezen. Geen extra afhankelijkheid nodig."""

import os

from django.core.exceptions import ImproperlyConfigured


def env(naam, standaard=None, required=False):
    waarde = os.environ.get(naam)
    if waarde is None or waarde == "":
        # Ondersteuning voor secrets als bestand (Docker/Kubernetes): KB_X_FILE=/pad
        pad = os.environ.get(f"{naam}_FILE")
        if pad:
            with open(pad, encoding="utf-8") as f:
                return f.read().strip()
        if required:
            raise ImproperlyConfigured(f"Omgevingsvariabele {naam} is verplicht.")
        return standaard
    return waarde


def env_bool(naam, standaard=False):
    waarde = env(naam)
    if waarde is None:
        return standaard
    return waarde.strip().lower() in {"1", "true", "ja", "yes", "on", "aan"}


def env_int(naam, standaard):
    waarde = env(naam)
    return standaard if waarde is None else int(waarde)


def env_list(naam, standaard):
    waarde = env(naam)
    if waarde is None:
        return standaard
    return [deel.strip() for deel in waarde.split(",") if deel.strip()]
