"""Opgeslagen zoekdocumenten met GIN-index (1.6.0), voor zoeken dat meeschaalt met het aantal artikelen.

De vulling gebeurt met vaste SQL (dezelfde als in diensten.werk_zoekvectoren_bij op dit moment), zodat
deze migratie niet meebeweegt met latere wijzigingen in de applicatiecode.
"""

import django.contrib.postgres.indexes
import django.contrib.postgres.search

from django.db import migrations


VUL_SECTIES = """
UPDATE kennisbank_sectie s SET zoekvector =
    setweight(to_tsvector('dutch', a.titel), 'A')
 || setweight(to_tsvector('dutch', coalesce(s.kop, '')), 'A')
 || setweight(to_tsvector('dutch', coalesce(s.inhoud, '')), 'B')
 || setweight(to_tsvector('dutch', coalesce(a.samenvatting, '')), 'D')
FROM kennisbank_artikel a WHERE a.id = s.artikel_id
"""
VUL_ARTIKELEN = """
UPDATE kennisbank_artikel a SET zoekvector =
    setweight(to_tsvector('dutch', a.titel), 'A')
 || setweight(to_tsvector('dutch', coalesce((SELECT string_agg(t.naam, ' ') FROM kennisbank_artikel_tags at
        JOIN kennisbank_tag t ON t.id = at.tag_id WHERE at.artikel_id = a.id), '')), 'A')
 || setweight(to_tsvector('dutch', coalesce(a.samenvatting, '')), 'B')
 || setweight(to_tsvector('dutch', coalesce((SELECT string_agg(coalesce(s.kop, '') || ' ' || coalesce(s.inhoud, ''),
        ' ') FROM kennisbank_sectie s WHERE s.artikel_id = a.id), '')), 'C')
"""


class Migration(migrations.Migration):

    dependencies = [
        ("kennisbank", "0006_tellingen_per_omgeving"),
    ]

    operations = [
        migrations.AddField(
            model_name="artikel",
            name="zoekvector",
            field=django.contrib.postgres.search.SearchVectorField(
                editable=False, null=True
            ),
        ),
        migrations.AddField(
            model_name="sectie",
            name="zoekvector",
            field=django.contrib.postgres.search.SearchVectorField(
                editable=False, null=True
            ),
        ),
        migrations.AddIndex(
            model_name="artikel",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["zoekvector"], name="artikel_zoekvector_gin"
            ),
        ),
        migrations.AddIndex(
            model_name="sectie",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["zoekvector"], name="sectie_zoekvector_gin"
            ),
        ),
        migrations.RunSQL(VUL_SECTIES, migrations.RunSQL.noop),
        migrations.RunSQL(VUL_ARTIKELEN, migrations.RunSQL.noop),
    ]
