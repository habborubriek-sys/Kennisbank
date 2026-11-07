"""Rechten actueel houden zonder opnieuw in te loggen.

Of iemand het beheerscherm in mag (is_staff) volgt uit zijn groepen en de rol van die groepen per
omgeving. Verandert een van beide, dan wordt is_staff direct bijgewerkt:
- groepen van een gebruiker wijzigen (via OIDC-login of handmatig in het beheer);
- een regel onder 'Toegang' wordt toegevoegd, gewijzigd of verwijderd.
Vóór versie 1.5 gebeurde dat alleen bij het inloggen.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Toegang
from .rechten import werk_staf_status_bij

User = get_user_model()


@receiver(m2m_changed, sender=User.groups.through)
def groepen_gewijzigd(sender, instance, action, reverse, pk_set, **kwargs):
    if reverse and action == "pre_clear":
        # Group.user_set.clear(): na het wissen zijn de leden niet meer op te vragen, dus nu onthouden.
        instance._kb_leden_voor_clear = list(instance.user_set.all())
        return
    if action not in ("post_add", "post_remove", "post_clear"):
        return
    if not reverse:
        gebruikers = [instance]
    elif action == "post_clear":
        gebruikers = getattr(instance, "_kb_leden_voor_clear", [])
    else:  # Group.user_set.add/remove(...): instance is de groep
        gebruikers = User.objects.filter(pk__in=pk_set or [])
    for gebruiker in gebruikers:
        werk_staf_status_bij(gebruiker)


def _werk_groep_bij(groep_id):
    for gebruiker in User.objects.filter(groups__id=groep_id).distinct():
        werk_staf_status_bij(gebruiker)


@receiver(pre_save, sender=Toegang)
def toegang_wordt_opgeslagen(sender, instance, **kwargs):
    # Wordt een regel naar een andere groep verplaatst, dan moeten ook de leden van de oude groep bijgewerkt.
    if instance.pk:
        oude = Toegang.objects.filter(pk=instance.pk).values_list("groep_id", flat=True).first()
        instance._kb_oude_groep = oude if oude != instance.groep_id else None


@receiver(post_save, sender=Toegang)
def toegang_opgeslagen(sender, instance, **kwargs):
    _werk_groep_bij(instance.groep_id)
    oude = getattr(instance, "_kb_oude_groep", None)
    if oude:
        _werk_groep_bij(oude)


@receiver(post_delete, sender=Toegang)
def toegang_verwijderd(sender, instance, **kwargs):
    _werk_groep_bij(instance.groep_id)


@receiver(post_delete, sender=Group)
def groep_verwijderd(sender, instance, **kwargs):
    # De koppelingen zijn al weg; wie nergens meer redacteur is, verliest het beheer.
    for gebruiker in User.objects.filter(is_staff=True, is_superuser=False):
        werk_staf_status_bij(gebruiker)
