"""Lege vrije-tekst-secties verwijderen (1.8.0).

Tot nu toe kreeg elk artikel een sectierij met volgorde 0 voor de tekst vóór de eerste sectiekop,
ook als die tekst er niet was. Zo'n lege rij droeg in zijn zoekdocument wél de artikeltitel en won
daardoor regelmatig de zoekopdracht van de assistent, die vervolgens "Dit staat in ..." zei en niets
kon citeren. Nieuwe en opnieuw opgeslagen artikelen krijgen die rij niet meer; deze migratie ruimt op
wat er in bestaande installaties al staat.
"""

from django.db import migrations


def lege_secties_weg(apps, schema_editor):
    Sectie = apps.get_model("kennisbank", "Sectie")
    Sectie.objects.filter(volgorde=0).exclude(inhoud__regex=r"\S").delete()


class Migration(migrations.Migration):
    dependencies = [("kennisbank", "0010_zacht_slot")]
    operations = [migrations.RunPython(lege_secties_weg, migrations.RunPython.noop)]
