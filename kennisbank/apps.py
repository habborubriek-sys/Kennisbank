from django.apps import AppConfig


class KennisbankConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "kennisbank"

    def ready(self):
        from . import signalen  # noqa: F401 - registreert de signaalontvangers
