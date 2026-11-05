"""Eén tekst per artikel (met sectiekoppen) en links op nummer in plaats van slug."""

from django.db import migrations, models


def secties_naar_inhoud(apps, schema_editor):
    from kennisbank.inhoud import sectiekop

    Artikel = apps.get_model("kennisbank", "Artikel")
    ArtikelVersie = apps.get_model("kennisbank", "ArtikelVersie")
    for a in Artikel.objects.all().iterator():
        delen = []
        for s in a.secties.order_by("volgorde", "id"):
            delen.append(sectiekop(s.kop) + s.inhoud)
        a.inhoud = "".join(delen)
        a.save(update_fields=["inhoud"])
        # Afgeleide secties: inleiding (leeg) + de bestaande secties, volgorde vanaf 1.
        oud = list(a.secties.order_by("volgorde", "id").values("kop", "inhoud"))
        a.secties.all().delete()
        Sectie = apps.get_model("kennisbank", "Sectie")
        Sectie.objects.create(artikel=a, volgorde=0, kop="", inhoud="")
        for i, s in enumerate(oud):
            Sectie.objects.create(artikel=a, volgorde=i + 1, kop=s["kop"], inhoud=s["inhoud"])
    for v in ArtikelVersie.objects.all().iterator():
        if "secties" in v.inhoud and "inhoud" not in v.inhoud:
            v.inhoud["inhoud"] = "".join(sectiekop(s.get("kop", "")) + s.get("inhoud", "") for s in v.inhoud["secties"])
            v.inhoud.pop("secties", None)
            v.inhoud["formaat"] = "artikel-html"
            v.save(update_fields=["inhoud"])


class Migration(migrations.Migration):
    dependencies = [("kennisbank", "0002_inhoud_html")]

    operations = [
        migrations.AddField(
            model_name="artikel",
            name="inhoud",
            field=models.TextField(
                blank=True,
                help_text="De tekst van het artikel. Markeer een regel als 'Sectiekop' om een in- en uitklapbare "
                "sectie te beginnen; markeer alinea's als 'Onboarding' om ze alleen aan nieuwe collega's te tonen.",
            ),
        ),
        migrations.AlterField(
            model_name="artikel",
            name="slug",
            field=models.SlugField(
                db_index=True,
                editable=False,
                help_text="Leesbaar deel van de link; wordt uit de titel afgeleid. De link werkt op het nummer.",
                max_length=120,
            ),
        ),
        migrations.AlterField(model_name="sectie", name="kop", field=models.CharField(blank=True, max_length=200)),
        migrations.AlterField(model_name="sectie", name="inhoud", field=models.TextField(blank=True)),
        migrations.RunPython(secties_naar_inhoud, migrations.RunPython.noop),
    ]
