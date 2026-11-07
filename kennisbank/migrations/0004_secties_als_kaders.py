"""Secties als kaders (<section>) in plaats van sectiekoppen die de tekst opdelen.

Gebruikt uitsluitend bevroren functies uit kennisbank.oud_formaat (zie de toelichting daar).
"""

from django.db import migrations

from kennisbank.oud_formaat import blokken_bevroren as blokken
from kennisbank.oud_formaat import koppen_naar_kaders


def vooruit(apps, schema_editor):

    Artikel = apps.get_model("kennisbank", "Artikel")
    ArtikelVersie = apps.get_model("kennisbank", "ArtikelVersie")
    Sectie = apps.get_model("kennisbank", "Sectie")
    for a in Artikel.objects.all().iterator():
        a.inhoud = koppen_naar_kaders(a.inhoud)
        a.save(update_fields=["inhoud"])
        alle = blokken(a.inhoud)
        Sectie.objects.filter(artikel=a).delete()
        Sectie.objects.create(artikel=a, volgorde=0, kop="", inhoud="".join(b["html"] for b in alle if b["type"] == "tekst"))
        for b in alle:
            if b["type"] == "sectie":
                Sectie.objects.create(artikel=a, volgorde=b["nummer"], kop=b["kop"], inhoud=b["html"])
    for v in ArtikelVersie.objects.all().iterator():
        if "inhoud" in v.inhoud:
            v.inhoud["inhoud"] = koppen_naar_kaders(v.inhoud["inhoud"])
            v.save(update_fields=["inhoud"])


class Migration(migrations.Migration):
    dependencies = [("kennisbank", "0003_artikel_inhoud_en_nummerlinks")]
    operations = [migrations.RunPython(vooruit, migrations.RunPython.noop)]
