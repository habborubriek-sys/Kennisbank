"""Bestaande gegevens gereedmaken voor 1.7.0.

1. Tags krijgen overal dezelfde schrijfwijze (kleine letters, enkele spaties). Tags die daardoor samenvallen
   ('Omgevingswet' en 'omgevingswet') worden één tag; de artikelen gaan mee. Zonder dit zou het beheerformulier
   een geïmporteerd artikel met een hoofdletter-tag bij de eerste opslag als 'inhoudelijk gewijzigd' zien.
2. Wijzigingsmeldingen gelden alleen voor wijzigingen vanaf deze versie: voor elke bestaande gebruiker wordt
   elk artikel met versie > 1 alvast afgevinkt. Anders zou iedereen na de upgrade alle historische versies als
   openstaande melding krijgen.
"""

from django.conf import settings
from django.db import migrations


def normaliseer(naam):
    return " ".join((naam or "").split()).strip().lower()[:60]


def tags_normaliseren(apps, schema_editor):
    Tag = apps.get_model("kennisbank", "Tag")
    Artikel = apps.get_model("kennisbank", "Artikel")
    groepen = {}
    for tag in Tag.objects.order_by("id"):
        nieuw = normaliseer(tag.naam)
        if not nieuw:
            tag.delete()
            continue
        groepen.setdefault(nieuw, []).append(tag)
    for nieuw, tags in groepen.items():
        # Bewaar bij voorkeur de tag die al goed geschreven is (anders de oudste); de rest gaat erin op.
        doel = next((t for t in tags if t.naam == nieuw), tags[0])
        for dubbel in tags:
            if dubbel.pk == doel.pk:
                continue
            for artikel in Artikel.objects.filter(tags=dubbel):
                artikel.tags.add(doel)
            dubbel.delete()
        if doel.naam != nieuw:
            Tag.objects.filter(pk=doel.pk).update(naam=nieuw)


def wijzigingen_afvinken(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Artikel = apps.get_model("kennisbank", "Artikel")
    WijzigingGezien = apps.get_model("kennisbank", "WijzigingGezien")
    artikelen = list(Artikel.objects.filter(versie__gt=1).values_list("id", "versie"))
    if not artikelen:
        return
    rijen = [
        WijzigingGezien(gebruiker_id=gid, artikel_id=aid, versie=versie)
        for gid in User.objects.values_list("id", flat=True)
        for aid, versie in artikelen
    ]
    WijzigingGezien.objects.bulk_create(rijen, batch_size=2000, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        ("kennisbank", "0008_wijzigingen_en_nieuws"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(tags_normaliseren, migrations.RunPython.noop),
        migrations.RunPython(wijzigingen_afvinken, migrations.RunPython.noop),
    ]
