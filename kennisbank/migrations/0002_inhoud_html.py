"""Secties: van Markdown + apart onboarding-veld naar HTML met onboarding-blokken in de inhoud."""

from django.db import migrations, models


def naar_html(apps, schema_editor):
    from kennisbank.inhoud import markdown_naar_html, onboarding_blok

    Sectie = apps.get_model("kennisbank", "Sectie")
    for s in Sectie.objects.all().iterator():
        html = markdown_naar_html(s.inhoud)
        if s.onboarding:
            html = onboarding_blok(markdown_naar_html(s.onboarding)) + html
        s.inhoud = html
        s.save(update_fields=["inhoud"])

    # Ook de versiegeschiedenis omzetten, zodat oude versies leesbaar blijven.
    ArtikelVersie = apps.get_model("kennisbank", "ArtikelVersie")
    for v in ArtikelVersie.objects.all().iterator():
        secties = v.inhoud.get("secties", [])
        for sec in secties:
            html = markdown_naar_html(sec.get("inhoud", ""))
            if sec.get("onboarding"):
                html = onboarding_blok(markdown_naar_html(sec["onboarding"])) + html
            sec["inhoud"] = html
            sec.pop("onboarding", None)
        v.inhoud["formaat"] = "html"
        v.save(update_fields=["inhoud"])


class Migration(migrations.Migration):
    dependencies = [("kennisbank", "0001_initial")]

    operations = [
        migrations.RunPython(naar_html, migrations.RunPython.noop),
        migrations.RemoveField(model_name="sectie", name="onboarding"),
        migrations.AlterField(
            model_name="sectie",
            name="inhoud",
            field=models.TextField(
                blank=True,
                help_text="Markeer alinea's met de knop 'Onboarding' om ze alleen aan nieuwe collega's te tonen.",
            ),
        ),
    ]
