import json
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from kennisbank import diensten
from kennisbank.auth import KennisbankOIDCBackend
from kennisbank.inhoud import blokken, onboarding_blokken, schoon, zonder_onboarding
from kennisbank.models import (
    Artikel,
    ArtikelVersie,
    Omgeving,
    RecentBezocht,
    Rol,
    Status,
    Toegang,
    Verbetervoorstel,
    WeergaveTelling,
    ZoekTelling,
)
from kennisbank.uitwisseling import exporteer, importeer
from kennisbank.word_import import lees_docx

User = get_user_model()


def pk_van(slug):
    return Artikel.objects.get(slug=slug).pk


DEMO = json.loads((Path(settings.BASE_DIR) / "demo" / "voorbeeldinhoud.json").read_text(encoding="utf-8"))


class Basis(TestCase):
    """Twee omgevingen, een lezer en een redacteur in 'handhaving', een lezer in 'anders'."""

    @classmethod
    def setUpTestData(cls):
        importeer(DEMO)
        cls.hh = Omgeving.objects.get(slug="handhaving")
        cls.anders = Omgeving.objects.create(slug="anders", naam="Ander onderdeel")
        lezers = Group.objects.create(name="lezers")
        redactie = Group.objects.create(name="redactie")
        anderen = Group.objects.create(name="anderen")
        Toegang.objects.create(omgeving=cls.hh, groep=lezers, rol=Rol.LEZER)
        Toegang.objects.create(omgeving=cls.hh, groep=redactie, rol=Rol.REDACTEUR)
        Toegang.objects.create(omgeving=cls.anders, groep=anderen, rol=Rol.LEZER)
        cls.lezer = User.objects.create_user("lezer", password="x")
        cls.lezer.groups.add(lezers)
        cls.redacteur = User.objects.create_user("redacteur", password="x", email="pm@example.org")
        cls.redacteur.groups.add(redactie)
        cls.buitenstaander = User.objects.create_user("buiten", password="x")
        cls.buitenstaander.groups.add(anderen)
        cls.concept = Artikel.objects.create(
            omgeving=cls.hh,
            titel="Geheim concept",
            samenvatting="Nog niet af",
            status=Status.CONCEPT,
        )
        cls.concept.inhoud = (
            '<section class="sectie"><h2 class="sectie-kop">Inhoud</h2><p>Concepttekst over rappel</p></section>'
        )
        cls.concept.save()
        diensten.herbouw_secties(cls.concept)

    def als(self, gebruiker):
        self.client.force_login(gebruiker)
        return self.client


class RechtenTests(Basis):
    def test_lezer_ziet_alleen_gepubliceerde_artikelen(self):
        slugs = [a["slug"] for a in self.als(self.lezer).get("/api/v1/artikelen").json()]
        self.assertEqual(len(slugs), 8)
        self.assertNotIn("geheim-concept", slugs)
        self.assertEqual(self.client.get(f"/api/v1/artikelen/{self.concept.pk}").status_code, 404)

    def test_redacteur_ziet_concepten(self):
        slugs = [a["slug"] for a in self.als(self.redacteur).get("/api/v1/artikelen").json()]
        self.assertIn("geheim-concept", slugs)
        r = self.client.get(f"/api/v1/artikelen/{self.concept.pk}").json()
        self.assertTrue(r["bewerk_url"])

    def test_andere_omgeving_ziet_niets(self):
        self.assertEqual(self.als(self.buitenstaander).get("/api/v1/artikelen").json(), [])
        self.assertEqual(self.client.get(f"/api/v1/artikelen/{pk_van('rappel-versturen')}").status_code, 404)

    def test_niet_ingelogd_geen_toegang(self):
        self.assertIn(self.client.get("/api/v1/artikelen").status_code, (401, 403))
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)

    def test_statistieken_alleen_voor_redacteur(self):
        self.assertEqual(self.als(self.lezer).get("/api/v1/statistieken").status_code, 403)
        self.assertEqual(self.als(self.redacteur).get("/api/v1/statistieken").status_code, 200)

    def test_redacteur_krijgt_toegang_tot_beheer(self):
        from kennisbank.rechten import werk_staf_status_bij

        werk_staf_status_bij(self.redacteur)
        werk_staf_status_bij(self.lezer)
        self.redacteur.refresh_from_db()
        self.lezer.refresh_from_db()
        self.assertTrue(self.redacteur.is_staff)
        self.assertFalse(self.lezer.is_staff)
        self.als(self.redacteur)
        self.assertEqual(self.client.get("/beheer/kennisbank/artikel/").status_code, 200)
        self.assertEqual(self.client.get("/beheer/kennisbank/omgeving/").status_code, 403)


class VersieTests(Basis):
    def test_import_maakt_versie_1(self):
        a = Artikel.objects.get(slug="rappel-versturen")
        self.assertEqual(a.versie, 1)
        self.assertEqual(a.versies.count(), 1)

    def test_wijziging_maakt_nieuwe_versie_en_ongewijzigd_niet(self):
        a = Artikel.objects.get(slug="rappel-versturen")
        self.assertIsNone(diensten.registreer_publicatie(a, self.redacteur))
        a.inhoud += "<p>Extra regel.</p>"
        a.save()
        v = diensten.registreer_publicatie(a, self.redacteur, "Regel toegevoegd")
        self.assertEqual(v.versie, 2)
        a.refresh_from_db()
        self.assertEqual(a.versie, 2)
        oud = ArtikelVersie.objects.get(artikel=a, versie=1)
        self.assertNotIn("Extra regel", json.dumps(oud.inhoud))

    def test_concept_krijgt_geen_versie(self):
        self.assertIsNone(diensten.registreer_publicatie(self.concept))

    def test_versiegeschiedenis_api(self):
        pk = pk_van("rappel-versturen")
        self.assertEqual(self.als(self.lezer).get(f"/api/v1/artikelen/{pk}/versies").status_code, 403)
        r = self.als(self.redacteur).get(f"/api/v1/artikelen/{pk}/versies")
        self.assertEqual(r.json()[0]["versie"], 1)


class ZoekTests(Basis):
    def zoek(self, q, **extra):
        return [a["slug"] for a in self.als(self.lezer).get("/api/v1/artikelen", {"q": q, **extra}).json()]

    def test_zoekt_op_woordstam_en_prefix(self):
        self.assertEqual(self.zoek("zwerfboten"), ["zwerfboot"])
        self.assertIn("rappel-versturen", self.zoek("rapp"))

    def test_alle_termen_moeten_voorkomen(self):
        self.assertEqual(self.zoek("tweede rappel termijn"), ["rappel-versturen"])

    def test_filters(self):
        r = self.als(self.lezer).get("/api/v1/artikelen", {"cluster": "Nautisch"}).json()
        # Artikelen zonder cluster gelden voor alle clusters
        self.assertIn("melding-registreren", [a["slug"] for a in r])
        self.assertNotIn("rappel-versturen", [a["slug"] for a in r])
        r = self.als(self.lezer).get("/api/v1/artikelen", {"soort": "proces"}).json()
        self.assertEqual({a["soort"] for a in r}, {"proces"})

    def test_zoekterm_alleen_geregistreerd_op_verzoek(self):
        self.zoek("rappel")
        self.assertFalse(ZoekTelling.objects.exists())
        self.zoek("rappel", registreer="1")
        self.zoek("bestaatniet", registreer="1")
        self.assertEqual(ZoekTelling.objects.get(term="rappel").aantal, 1)
        self.assertEqual(ZoekTelling.objects.get(term="bestaatniet").zonder_resultaat, 1)


class AssistentTests(Basis):
    def vraag(self, vraag, **extra):
        return (
            self.als(self.lezer)
            .post("/api/v1/assistent", {"vraag": vraag, **extra}, content_type="application/json")
            .json()
        )

    def test_zonder_ai_citeert_best_passende_sectie(self):
        a = self.vraag("Wanneer stuur ik een tweede rappel?")
        self.assertEqual(a["modus"], "zoeken")
        self.assertEqual(a["bronnen"][0]["slug"], "rappel-versturen")
        self.assertEqual(a["bronnen"][0]["sectie"], "Termijnen")
        self.assertEqual(a["bronnen"][0]["sectie_index"], 1)
        self.assertIn("2 weken", a["html"])

    def test_geen_bron_geen_antwoord(self):
        a = self.vraag("Hoeveel verlofdagen heb ik?")
        self.assertEqual(a["bronnen"], [])
        self.assertIn("niets", a["html"])

    def test_concepten_zijn_geen_bron(self):
        a = (
            self.als(self.redacteur)
            .post("/api/v1/assistent", {"vraag": "Concepttekst"}, content_type="application/json")
            .json()
        )
        self.assertNotIn(self.concept.pk, [b["id"] for b in a["bronnen"]])

    @override_settings(KB_AI_PROVIDER="openai", KB_AI_BASE_URL="https://llm.example/v1", KB_AI_MODEL="m")
    def test_met_ai_bronverwijzingen_worden_links(self):
        antwoord = {"choices": [{"message": {"content": "Na **2 weken** [1]. <script>x</script>"}}]}
        with mock.patch("kennisbank.assistent.httpx.post") as post:
            post.return_value = mock.Mock(json=lambda: antwoord, raise_for_status=lambda: None)
            a = self.vraag("Wanneer stuur ik een tweede rappel?")
        self.assertEqual(a["modus"], "ai")
        self.assertIn(f'data-open="{pk_van("rappel-versturen")}"', a["html"])
        self.assertNotIn("<script>", a["html"])
        verstuurd = post.call_args.kwargs["json"]
        self.assertEqual(verstuurd["model"], "m")
        # Er gaat niets over de gebruiker mee naar het taalmodel.
        self.assertNotIn("lezer", json.dumps(verstuurd))

    @override_settings(KB_AI_PROVIDER="azure", KB_AI_BASE_URL="https://x.openai.azure.com", KB_AI_MODEL="dep")
    def test_ai_storing_valt_terug_op_zoeken(self):
        with mock.patch("kennisbank.assistent.httpx.post", side_effect=OSError("down")):
            a = self.vraag("Wanneer stuur ik een tweede rappel?")
        self.assertEqual(a["modus"], "zoeken")
        self.assertTrue(a["melding"])


class VoorstelTests(Basis):
    def test_indienen_en_behandelen(self):
        r = self.als(self.lezer).post(
            "/api/v1/voorstellen",
            {"artikel": pk_van("rappel-versturen"), "citaat": "2 weken", "tekst": "Moet 3 weken zijn"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        vid = r.json()["id"]
        self.assertEqual(r.json()["artikel_versie"], 1)
        # Lezer mag niet behandelen
        self.assertEqual(
            self.client.patch(
                f"/api/v1/voorstellen/{vid}",
                {"status": "verwerkt", "terugkoppeling": "ok"},
                content_type="application/json",
            ).status_code,
            403,
        )
        r = self.als(self.redacteur).patch(
            f"/api/v1/voorstellen/{vid}",
            {"status": "verwerkt", "terugkoppeling": "Aangepast"},
            content_type="application/json",
        )
        self.assertEqual(r.json()["status"], "verwerkt")
        # Indiener ziet de terugkoppeling
        mijn = self.als(self.lezer).get("/api/v1/voorstellen").json()
        self.assertEqual(mijn[0]["terugkoppeling"], "Aangepast")
        self.assertTrue(mijn[0]["van_mij"])

    def test_lezer_ziet_geen_voorstellen_van_anderen(self):
        a = Artikel.objects.get(slug="mailbox")
        Verbetervoorstel.objects.create(artikel=a, artikel_versie=1, tekst="x", ingediend_door=self.redacteur)
        self.assertEqual(self.als(self.lezer).get("/api/v1/voorstellen").json(), [])
        self.assertEqual(len(self.als(self.redacteur).get("/api/v1/voorstellen").json()), 1)

    def test_geen_voorstel_bij_onzichtbaar_artikel(self):
        r = self.als(self.lezer).post(
            "/api/v1/voorstellen", {"artikel": self.concept.pk, "tekst": "x"}, content_type="application/json"
        )
        self.assertEqual(r.status_code, 403)

    @override_settings(KB_EMAIL_AAN=True)
    def test_mail_naar_redacteuren(self):
        from django.core import mail

        self.als(self.lezer).post(
            "/api/v1/voorstellen",
            {"artikel": pk_van("mailbox"), "tekst": "Graag aanvullen"},
            content_type="application/json",
        )
        self.assertEqual(mail.outbox[0].to, ["pm@example.org"])


class GebruikTests(Basis):
    def test_weergave_favoriet_en_onboarding(self):
        c = self.als(self.lezer)
        pk = pk_van("zwerfboot")
        self.assertEqual(c.post(f"/api/v1/artikelen/{pk}/weergave").status_code, 204)
        self.assertEqual(c.put(f"/api/v1/artikelen/{pk}/favoriet").status_code, 204)
        c.patch("/api/v1/ik", {"onboarding": True}, content_type="application/json")
        ik = c.get("/api/v1/ik").json()
        self.assertEqual(ik["favorieten"], [pk])
        self.assertEqual(ik["recent"][0]["id"], pk)
        self.assertTrue(ik["onboarding"])
        self.assertEqual(WeergaveTelling.objects.get().aantal, 1)

    def test_recent_is_begrensd(self):
        for a in Artikel.objects.gepubliceerd():
            diensten.registreer_weergave(self.lezer, a)
        with self.settings(KB_RECENT_MAX=3):
            diensten.registreer_weergave(self.lezer, Artikel.objects.get(slug="mailbox"))
        self.assertEqual(RecentBezocht.objects.filter(gebruiker=self.lezer).count(), 3)

    def test_zaaktype_endpoint(self):
        r = self.als(self.lezer).get("/api/v1/zaaktypen/Object/artikelen").json()
        self.assertEqual([a["slug"] for a in r], ["zwerfboot"])

    def test_opschonen(self):
        diensten.registreer_weergave(self.lezer, Artikel.objects.get(slug="mailbox"))
        RecentBezocht.objects.update(bezocht_op=timezone.now() - timezone.timedelta(days=400))
        v = Verbetervoorstel.objects.create(
            artikel=Artikel.objects.get(slug="mailbox"),
            artikel_versie=1,
            tekst="x",
            ingediend_door=self.lezer,
            status="verwerkt",
            behandeld_op=timezone.now() - timezone.timedelta(days=400),
        )
        call_command("kennisbank_opschonen", stdout=open("/dev/null", "w"))
        self.assertFalse(RecentBezocht.objects.exists())
        v.refresh_from_db()
        self.assertIsNone(v.ingediend_door)


class InhoudTests(TestCase):
    def test_html_wordt_opgeschoond(self):
        html = schoon(
            "<b>vet</b> <u>onder</u> <script>alert(1)</script> <a href='javascript:alert(1)'>x</a> "
            "<img src=x onerror=y> <p onclick='z'>t</p> <div class='onboarding'><p>u</p></div> <div class='x'>v</div>"
        )
        self.assertIn("<strong>vet</strong>", html)
        self.assertIn("<u>onder</u>", html)
        self.assertIn('<div class="onboarding"><p>u</p></div>', html)
        self.assertIn("<div>v</div>", html)
        for verboden in ("<script", "javascript:", "onerror", "onclick", "<img"):
            self.assertNotIn(verboden, html)
        self.assertEqual(schoon(html), html)

    def test_onboarding_blokken(self):
        html = '<p>a</p><div class="onboarding"><p>u1</p></div><p>b</p><div class="onboarding"><p>u2</p></div>'
        self.assertEqual(onboarding_blokken(html), ["<p>u1</p>", "<p>u2</p>"])
        self.assertEqual(zonder_onboarding(html), "<p>a</p><p>b</p>")

    def test_oude_markdown_import_wordt_html(self):
        data = json.loads(json.dumps(DEMO))
        data["versie"] = 1
        data["artikelen"] = [
            {
                "slug": "oud",
                "titel": "Oud",
                "samenvatting": "s",
                "status": "gepubliceerd",
                "secties": [{"kop": "K", "inhoud": "- punt\n- **vet**", "onboarding": "Extra *uitleg*"}],
            }
        ]
        importeer(data)
        a = Artikel.objects.get(slug="oud")
        self.assertIn('<section class="sectie"><h2 class="sectie-kop">K</h2>', a.inhoud)
        self.assertIn("<li><strong>vet</strong></li>", a.inhoud)
        self.assertIn('<div class="onboarding"><p>Extra <em>uitleg</em></p></div>', a.inhoud)
        self.assertEqual([s.kop for s in a.secties.all()], ["", "K"])

    def test_artikel_wordt_bij_opslaan_opgeschoond(self):
        importeer(DEMO)
        a = Artikel.objects.get(slug="mailbox")
        a.inhoud = "<p onclick='a'>t</p><script>1</script>"
        a.save()
        self.assertEqual(a.inhoud, "<p>t</p>")

    def test_blokken_in_leesvolgorde(self):
        html = (
            '<p>Intro</p><section class="sectie"><h2 class="sectie-kop">A</h2><p>a</p><h2>gewone kop</h2></section>'
            '<p>Tussen</p><section class="sectie"><h2 class="sectie-kop"></h2>'
            '<div class="onboarding"><p>u</p></div></section>'
        )
        b = blokken(html)
        self.assertEqual([x["type"] for x in b], ["tekst", "sectie", "tekst", "sectie"])
        self.assertEqual(b[0]["html"], "<p>Intro</p>")
        self.assertEqual((b[1]["nummer"], b[1]["kop"], b[1]["html"]), (1, "A", "<p>a</p><h3>gewone kop</h3>"))
        self.assertEqual(b[3]["kop"], "Sectie 2")

    def test_geneste_sectie_wordt_ontnest(self):
        html = (
            '<section class="sectie"><h2 class="sectie-kop">Buiten</h2><p>a</p>'
            '<section class="sectie"><h2 class="sectie-kop">Binnen</h2><p>b</p></section></section>'
        )
        b = blokken(html)
        self.assertEqual(len(b), 1)
        self.assertEqual(b[0]["html"], "<p>a</p><h3>Binnen</h3><p>b</p>")

    def test_oude_link_wordt_doorverwezen(self):
        importeer(DEMO)
        a = Artikel.objects.get(slug="mailbox")
        r = self.client.get("/artikel/mailbox")
        self.assertEqual(r.status_code, 302)  # eerst inloggen
        self.client.force_login(User.objects.create_user("l2", password="x"))
        self.assertEqual(self.client.get("/artikel/mailbox").status_code, 404)  # geen rechten → niets verraden
        u = User.objects.create_user("l3", password="x")
        g = Group.objects.create(name="g3")
        u.groups.add(g)
        Toegang.objects.create(omgeving=a.omgeving, groep=g, rol=Rol.LEZER)
        self.client.force_login(u)
        r = self.client.get("/artikel/mailbox")
        self.assertEqual((r.status_code, r["Location"]), (301, a.get_absolute_url()))
        self.assertEqual(self.client.get(f"/artikel/{a.pk}/willekeurige-naam").status_code, 200)

    def test_zelfde_titel_in_twee_omgevingen(self):
        importeer(DEMO)
        o2 = Omgeving.objects.create(slug="o2", naam="O2")
        a = Artikel.objects.create(omgeving=o2, titel="Gezamenlijke mailbox: wie pakt wat op", samenvatting="x")
        b = Artikel.objects.get(slug="mailbox")
        self.assertEqual(a.slug, "gezamenlijke-mailbox-wie-pakt-wat-op")
        self.assertNotEqual(a.pk, b.pk)
        self.assertNotEqual(a.get_absolute_url(), b.get_absolute_url())

    def test_import_export_rondgang(self):
        importeer(DEMO)
        uit = exporteer(Omgeving.objects.get(slug="handhaving"))
        self.assertEqual(len(uit["artikelen"]), 8)
        t = importeer(uit)
        self.assertEqual(t["nieuwe_versies"], 0)  # niets gewijzigd → geen nieuwe versies


class OIDCTests(TestCase):
    @override_settings(KB_BEHEERDERS_GROEPEN=["kb-beheer"], KB_OIDC_GROEPEN_CLAIM="groups")
    def test_gebruiker_en_groepen_uit_claims(self):
        o = Omgeving.objects.create(slug="o", naam="O")
        Toegang.objects.create(omgeving=o, groep=Group.objects.create(name="pm-groep"), rol=Rol.REDACTEUR)
        backend = KennisbankOIDCBackend.__new__(KennisbankOIDCBackend)
        backend.UserModel = User
        claims = {"sub": "abc-123", "email": "a@b.nl", "given_name": "An", "family_name": "B", "groups": ["pm-groep"]}
        u = backend.create_user(claims)
        self.assertEqual(u.username, "abc-123")
        self.assertTrue(u.is_staff)
        self.assertFalse(u.is_superuser)
        u = backend.update_user(u, {**claims, "groups": ["kb-beheer"]})
        self.assertTrue(u.is_superuser)
        self.assertEqual(list(u.groups.values_list("name", flat=True)), ["kb-beheer"])
        self.assertEqual(list(backend.filter_users_by_claims(claims)), [u])


class InfraTests(TestCase):
    def test_health(self):
        self.assertEqual(self.client.get("/healthz").status_code, 200)
        self.assertEqual(self.client.get("/readyz").json()["status"], "gereed")

    def test_strenge_csp_en_inbedden(self):
        r = self.client.get("/zaaktype/Melding")
        self.assertEqual(r.status_code, 200)
        self.assertIn("script-src 'self'", r["Content-Security-Policy"])
        self.assertIn("frame-ancestors", r["Content-Security-Policy"])
        self.assertNotIn("X-Frame-Options", r)

    def test_openapi_schema(self):
        r = self.client.get("/api/schema/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"/api/v1/assistent", r.content)


def _docx(paragrafen):
    """Maak in het geheugen een .docx: lijst van (stijl, tekst)."""
    import io

    import docx
    from docx.enum.style import WD_STYLE_TYPE

    d = docx.Document()
    d.styles.add_style("Onboarding", WD_STYLE_TYPE.PARAGRAPH).base_style = d.styles["Normal"]
    d.styles.add_style("Sectie", WD_STYLE_TYPE.PARAGRAPH).base_style = d.styles["Normal"]
    for stijl, tekst in paragrafen:
        if stijl.startswith("Heading"):
            d.add_heading(tekst, level=int(stijl[-1]))
        else:
            d.add_paragraph(tekst, style=stijl)
    buf = io.BytesIO()
    d.save(buf)
    buf.seek(0)
    return buf


class WordImportTests(Basis):
    def test_alleen_tekst_en_opmaak(self):
        a = lees_docx(
            _docx(
                [
                    ("Heading 1", "Rappel versturen"),
                    ("Normal", "Korte samenvatting."),
                    ("Heading 2", "Termijnen"),
                    ("List Bullet", "4 weken"),
                    ("Onboarding", "Geen speciale betekenis meer."),
                    ("Sectie", "Ook niet."),
                ]
            ),
            "Rappel-versturen_v2.docx",
        )
        self.assertEqual(a.titel, "Rappel versturen v2")
        self.assertIn("<h3>Rappel versturen</h3>", a.inhoud)
        self.assertIn("<h3>Termijnen</h3>", a.inhoud)
        self.assertIn("<li>4 weken</li>", a.inhoud)
        self.assertNotIn("sectie", a.inhoud)
        self.assertNotIn("onboarding", a.inhoud)
        self.assertEqual(a.meldingen, [])

    def test_geen_docx(self):
        import io

        from kennisbank.word_import import WordImportFout

        with self.assertRaises(WordImportFout):
            lees_docx(io.BytesIO(b"dit is geen word"), "x.docx")

    def test_import_via_beheer(self):
        from kennisbank.rechten import werk_staf_status_bij

        werk_staf_status_bij(self.redacteur)
        c = self.als(self.redacteur)
        r = c.get("/beheer/kennisbank/artikel/importeren-word/")
        self.assertEqual(r.status_code, 200)
        bestand = _docx(
            [
                ("Heading 1", "Nieuw uit Word"),
                ("Normal", "Samenvatting."),
                ("Sectie", "Stap 1"),
                ("Normal", "Doe dit."),
            ]
        )
        bestand.name = "nieuw-uit-word.docx"
        r = c.post(
            "/beheer/kennisbank/artikel/importeren-word/",
            {"bestand": bestand, "omgeving": self.hh.pk, "soort": "werkinstructie"},
        )
        self.assertEqual(r.status_code, 302)
        a = Artikel.objects.get(slug="nieuw-uit-word")
        self.assertEqual(a.titel, "nieuw uit word")
        self.assertEqual(a.samenvatting, "(vul een samenvatting in)")
        self.assertEqual(a.status, Status.CONCEPT)
        self.assertEqual(a.omgeving, self.hh)
        self.assertEqual([s.kop for s in a.secties.all()], [""])  # nog geen secties: die maak je in de editor
        self.assertIn("<h3>Stap 1</h3>", a.inhoud)
        # Lezers mogen niet importeren
        werk_staf_status_bij(self.lezer)
        self.assertIn(self.als(self.lezer).get("/beheer/kennisbank/artikel/importeren-word/").status_code, (302, 403))

    def test_tags_als_tekst_in_beheer(self):
        from kennisbank.rechten import werk_staf_status_bij

        werk_staf_status_bij(self.redacteur)
        c = self.als(self.redacteur)
        a = Artikel.objects.get(slug="mailbox")
        r = c.get(f"/beheer/kennisbank/artikel/{a.pk}/change/")
        self.assertContains(r, 'value="e-mail, intake, mailbox"')
        data = {
            "titel": a.titel,
            "samenvatting": a.samenvatting,
            "inhoud": a.inhoud,
            "soort": a.soort,
            "omgeving": a.omgeving_id,
            "eigenaar": a.eigenaar,
            "status": a.status,
            "tags_tekst": "Mailbox, Nieuwe Tag , nieuwe tag,",
            "wijzigingstoelichting": "",
            "versies-TOTAL_FORMS": "0",
            "versies-INITIAL_FORMS": "0",
        }
        r = c.post(f"/beheer/kennisbank/artikel/{a.pk}/change/", data)
        self.assertEqual(r.status_code, 302, r.content[:500])
        self.assertEqual(sorted(a.tags.values_list("naam", flat=True)), ["mailbox", "nieuwe tag"])


class VoorbeeldTests(Basis):
    def test_voorbeeld_toont_niet_opgeslagen_tekst(self):
        from kennisbank.rechten import werk_staf_status_bij

        werk_staf_status_bij(self.redacteur)
        c = self.als(self.redacteur)
        r = c.post(
            "/beheer/kennisbank/artikel/voorbeeld/",
            {
                "titel": "Nog niet opgeslagen",
                "samenvatting": "S",
                "soort": "proces",
                "inhoud": '<p>Intro</p><section class="sectie"><h2 class="sectie-kop">Stap 1</h2>'
                "<p>Doe dit</p></section><script>x</script>",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Nog niet opgeslagen")
        self.assertContains(r, "<summary>Stap 1</summary>")
        self.assertContains(r, "Intro")
        self.assertNotContains(r, "<script>x")
        self.assertFalse(Artikel.objects.filter(titel="Nog niet opgeslagen").exists())
        self.assertEqual(c.get("/beheer/kennisbank/artikel/voorbeeld/").status_code, 405)
        werk_staf_status_bij(self.lezer)
        self.assertIn(
            self.als(self.lezer).post("/beheer/kennisbank/artikel/voorbeeld/", {"inhoud": ""}).status_code, (302, 403)
        )
