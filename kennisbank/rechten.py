"""Wie mag wat. Alle autorisatie loopt via deze module.

Regels:
- Een gebruiker heeft per omgeving de hoogste rol uit al zijn groepen (lezer < redacteur).
- Superusers (functioneel beheerders) zijn redacteur in elke omgeving.
- Lezers zien alleen gepubliceerde artikelen. Redacteuren zien ook concepten en archief,
  behandelen verbetervoorstellen en zien statistieken van hun omgeving(en).
"""

from functools import cached_property

from .models import Artikel, Omgeving, Rol, Status, Toegang


class Rechten:
    def __init__(self, gebruiker):
        self.gebruiker = gebruiker

    @cached_property
    def rollen(self):
        """{omgeving_id: rol}"""
        if not self.gebruiker or not self.gebruiker.is_authenticated:
            return {}
        if self.gebruiker.is_superuser:
            return {oid: Rol.REDACTEUR for oid in Omgeving.objects.values_list("id", flat=True)}
        rollen = {}
        rijen = Toegang.objects.filter(groep__user=self.gebruiker).values_list("omgeving_id", "rol")
        for omgeving_id, rol in rijen:
            if rollen.get(omgeving_id) != Rol.REDACTEUR:
                rollen[omgeving_id] = rol
        return rollen

    @property
    def leesbare_omgevingen(self):
        return set(self.rollen)

    @property
    def redactie_omgevingen(self):
        return {oid for oid, rol in self.rollen.items() if rol == Rol.REDACTEUR}

    @property
    def is_redacteur(self):
        return bool(self.redactie_omgevingen)

    def mag_lezen(self, artikel):
        if artikel.omgeving_id in self.redactie_omgevingen:
            return True
        return artikel.omgeving_id in self.leesbare_omgevingen and artikel.status == Status.GEPUBLICEERD

    def mag_redigeren(self, artikel):
        return artikel.omgeving_id in self.redactie_omgevingen

    def artikelen(self):
        """Alle artikelen die deze gebruiker mag zien."""
        from django.db.models import Q

        return Artikel.objects.filter(
            Q(omgeving_id__in=self.redactie_omgevingen)
            | Q(omgeving_id__in=self.leesbare_omgevingen, status=Status.GEPUBLICEERD)
        )

    def gepubliceerde_artikelen(self):
        return Artikel.objects.gepubliceerd().filter(omgeving_id__in=self.leesbare_omgevingen)


def rechten(request_of_gebruiker):
    gebruiker = getattr(request_of_gebruiker, "user", request_of_gebruiker)
    cache = getattr(request_of_gebruiker, "_kb_rechten", None)
    if cache is not None:
        return cache
    r = Rechten(gebruiker)
    if hasattr(request_of_gebruiker, "user"):
        request_of_gebruiker._kb_rechten = r
    return r


def werk_staf_status_bij(gebruiker):
    """Redacteuren hebben toegang tot het beheerscherm nodig om artikelen te bewerken."""
    staf = gebruiker.is_superuser or Rechten(gebruiker).is_redacteur
    if gebruiker.is_staff != staf:
        gebruiker.is_staff = staf
        gebruiker.save(update_fields=["is_staff"])
    # Wie (ergens) geen redacteur meer is, kan daar ook geen voorstellen meer in zijn bak hebben.
    from .diensten import bakken_rechtzetten

    bakken_rechtzetten(gebruiker=gebruiker)
