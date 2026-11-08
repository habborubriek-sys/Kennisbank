"""Terugkoppeling wordt afgeleid uit de berichten, en bestaande terugkoppelingen worden een bericht.

Vóór 1.10.0 was `Verbetervoorstel.terugkoppeling` een los veld dat de redacteur zelf typte. Sinds
1.10.0 toont de kennisbank alleen de berichten, en wordt `terugkoppeling` afgeleid uit het laatste
bericht van procesmanagement. Zonder deze migratie zou een medewerker die vóór de upgrade antwoord
kreeg, daarna een leeg gesprek zien terwijl zijn antwoord nog wel in de database staat.
"""

from django.db import migrations, models


def terugkoppelingen_naar_berichten(apps, schema_editor):
    Verbetervoorstel = apps.get_model("kennisbank", "Verbetervoorstel")
    VoorstelBericht = apps.get_model("kennisbank", "VoorstelBericht")
    rijen = []
    for v in Verbetervoorstel.objects.exclude(terugkoppeling="").filter(berichten__isnull=True):
        rijen.append(
            VoorstelBericht(
                voorstel=v,
                auteur=v.behandeld_door,
                van_redactie=True,
                tekst=v.terugkoppeling[:5000],
                moment=v.behandeld_op or v.ingediend_op,
            )
        )
    VoorstelBericht.objects.bulk_create(rijen)


class Migration(migrations.Migration):
    dependencies = [
        ("kennisbank", "0016_voorstelgesprek"),
    ]

    operations = [
        migrations.AlterField(
            model_name="verbetervoorstel",
            name="terugkoppeling",
            field=models.TextField(blank=True, editable=False),
        ),
        migrations.AlterField(
            model_name="voorstelbericht",
            name="tekst",
            field=models.TextField(max_length=5000),
        ),
        migrations.AlterField(
            model_name="voorstelbericht",
            name="van_redactie",
            field=models.BooleanField(
                default=True,
                help_text="Van procesmanagement (aan) of van de indiener (uit; komt niet meer voor).",
            ),
        ),
        # Terug draaien hoeft niet: het veld terugkoppeling blijft staan, dus er gaat niets verloren.
        migrations.RunPython(terugkoppelingen_naar_berichten, migrations.RunPython.noop),
    ]
