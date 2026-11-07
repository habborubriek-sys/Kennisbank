"""Zoek- en assistenttellingen per omgeving, plus dagtotaal voor het kostenplafond (1.5.0).

Bestaande tellingen hebben geen omgeving. Is er precies één omgeving, dan horen ze daar
vanzelfsprekend bij en worden ze daaraan gekoppeld; anders blijven ze zonder omgeving en
tellen ze nergens meer mee (het gaat om statistiek van hooguit de bewaartermijn oud).
Terugdraaien zet het omgeving-veld weer weg; tellingen blijven bewaard.
"""

import django.db.models.deletion
from django.db import migrations, models


def koppel_aan_enige_omgeving(apps, schema_editor):
    Omgeving = apps.get_model("kennisbank", "Omgeving")
    if Omgeving.objects.count() != 1:
        return
    enige = Omgeving.objects.get()
    for naam in ("ZoekTelling", "AssistentTelling"):
        apps.get_model("kennisbank", naam).objects.filter(omgeving__isnull=True).update(omgeving=enige)


class Migration(migrations.Migration):

    dependencies = [
        ("kennisbank", "0005_helptekst_inhoud"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssistentDagTotaal",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("datum", models.DateField(unique=True)),
                ("modelaanroepen", models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.RemoveConstraint(
            model_name="zoektelling",
            name="uniek_zoekterm_per_dag",
        ),
        migrations.AddField(
            model_name="assistenttelling",
            name="omgeving",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="assistenttellingen",
                to="kennisbank.omgeving",
            ),
        ),
        migrations.AddField(
            model_name="zoektelling",
            name="omgeving",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="zoektellingen",
                to="kennisbank.omgeving",
            ),
        ),
        migrations.AlterField(
            model_name="assistenttelling",
            name="datum",
            field=models.DateField(),
        ),
        migrations.RunPython(koppel_aan_enige_omgeving, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="assistenttelling",
            constraint=models.UniqueConstraint(
                fields=("omgeving", "datum"), name="uniek_assistent_per_dag_omgeving"
            ),
        ),
        migrations.AddConstraint(
            model_name="zoektelling",
            constraint=models.UniqueConstraint(
                fields=("omgeving", "term", "datum"),
                name="uniek_zoekterm_per_dag_omgeving",
            ),
        ),
    ]
