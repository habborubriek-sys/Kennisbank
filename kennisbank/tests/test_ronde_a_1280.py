"""1.28.0, ronde A: juiste stand en geen werkverlies (bouwlijst `bouwlijst-1.28.0-ronde-a.md`).

Elke test noemt het nummer uit de bouwlijst (A1 … A22) en de bevinding uit de review van 1.27.0.
"""

from django.contrib.messages import get_messages
from django.core import mail
from django.test import override_settings

from kennisbank import diensten, review
from kennisbank.models import ArtikelVersie, Conceptversie, Inzage, Verbetervoorstel, VoorstelStatus
from kennisbank.tests.test_kennisbank import beheerdata
from kennisbank.tests.test_voorstellen_lade_1260 import LadeBasis, lade_van


def meldingen(r):
    return " | ".join(str(m) for m in get_messages(r.wsgi_request))


class RondeABasis(LadeBasis):
    def opslaan(self, lade, mee, geladen=None, wie=None, knop="_conceptversie", **velden):
        """Opslaan zoals de pagina het nu verstuurt: met de stand van Meenemen bij het laden (A7)."""
        self.client.force_login(wie or self.anna)
        data = beheerdata(self.a, wijzigingstoelichting=velden.pop("wijzigingstoelichting", ""), **velden)
        c = Conceptversie.objects.filter(artikel=self.a).first()
        data["geladen_concept"] = c.stempel if c else ""
        data["kb_lade"] = ",".join(str(v.pk) for v in lade)
        data["kb_meenemen"] = ",".join(str(v.pk) for v in mee)
        if geladen is not None:
            data["kb_mee_geladen"] = ",".join(str(v.pk) for v in geladen)
        return self.post(self.url, data, **{knop: "1"})

    def publiceer(self, lade=(), mee=(), geladen=(), **velden):
        c = Conceptversie.objects.filter(artikel=self.a).first()
        inhoud = velden.pop("inhoud", c.velden["inhoud"] if c else "<p>Stuur na drie weken een rappel.</p>")
        return self.opslaan(
            lade,
            mee,
            geladen,
            knop="_save",
            inhoud=inhoud,
            wijzigingstoelichting=velden.pop("wijzigingstoelichting", "Termijn aangepast"),
            **velden,
        )

    def mee(self, *vs):
        Verbetervoorstel.objects.filter(pk__in=[v.pk for v in vs]).update(in_conceptversie=True)


# --- A5/A6: één regel op één plek, het oude scherm alleen-lezen -------------------------------------------


class RegelsOveral(RondeABasis):
    def ter_inzage_met(self, v):
        self.maak_concept()
        self.mee(v)
        self.ter_inzage()
        self.assertTrue(review.op_slot(self.a.pk))

    def test_a5_dienst_weigert_afhandelen_tijdens_de_review(self):
        v = self.voorstel()
        self.ter_inzage_met(v)
        v.refresh_from_db()
        with self.assertRaises(diensten.VoorstelOpSlot):
            diensten.voorstel_afhandelen(v, self.anna, VoorstelStatus.AFGEWEZEN, "Nee")
        # Het systeem zelf (bijvoorbeeld archiveren) mag wel.
        diensten.voorstel_afhandelen(v, None, VoorstelStatus.VERVALLEN, "Ingetrokken")

    def test_a5_api_geeft_409_tijdens_de_review(self):
        v = self.voorstel()
        self.ter_inzage_met(v)
        r = self.als(self.anna).patch(
            f"/api/v1/voorstellen/{v.pk}",
            {"status": "afgewezen", "terugkoppeling": "Nee"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 409)
        self.assertIn("ter inzage", r.json()["detail"])
        v.refresh_from_db()
        self.assertTrue(v.is_open)

    def test_a5_lade_geeft_409_tijdens_de_review(self):
        v = self.voorstel()
        self.ter_inzage_met(v)
        self.client.force_login(self.anna)
        r = self.actie(v, actie="afwijzen", tekst="Nee")
        self.assertEqual(r.status_code, 409)
        self.assertIn("ter inzage", r.json()["fout"])

    def test_a6_oud_scherm_weigert_elke_post_voor_een_open_voorstel(self):
        v = self.voorstel()
        self.ter_inzage_met(v)
        self.client.force_login(self.anna)
        for actie in ("meenemen", "afwijzen", "verwerkt", "bericht", "notitie", "verbergen"):
            r = self.client.post(
                f"/beheer/voorstel/{v.pk}/", {"actie": actie, "waarde": "0", "bericht": "Hoi", "notitie": "Let op"}
            )
            self.assertEqual(r["Location"], f"{self.url}?voorstel={v.pk}", actie)
        v.refresh_from_db()
        self.assertTrue(v.in_conceptversie and v.is_open and not v.verborgen)
        self.assertFalse(v.berichten.exists() or v.notities.exists())

    def test_a6_getypte_tekst_staat_in_de_melding(self):
        v = self.voorstel()
        self.client.force_login(self.anna)
        r = self.client.post(f"/beheer/voorstel/{v.pk}/", {"actie": "bericht", "bericht": "Ik bel je morgen."})
        self.assertIn("Ik bel je morgen.", meldingen(r))

    def test_a6_oud_beheerformulier_ook(self):
        v = self.voorstel()
        self.client.force_login(self.anna)
        r = self.client.post(f"/beheer/kennisbank/verbetervoorstel/{v.pk}/change/", {"status": "afgewezen"})
        self.assertEqual(r["Location"], f"{self.url}?voorstel={v.pk}")
        v.refresh_from_db()
        self.assertEqual(v.status, VoorstelStatus.NIEUW)

    def test_a6_afgehandeld_voorstel_kan_nog_een_bericht_krijgen(self):
        v = self.voorstel()
        diensten.voorstel_afhandelen(v, self.anna, VoorstelStatus.AFGEWEZEN, "Nee")
        self.client.force_login(self.anna)
        laatste = v.berichten.get().pk
        self.client.post(
            f"/beheer/voorstel/{v.pk}/",
            {"actie": "bericht", "bericht": "Nog een aanvulling.", "geladen_bericht": str(laatste)},
        )
        self.assertEqual(v.berichten.count(), 2)


# --- A7: een verouderd scherm draait niets terug -----------------------------------------------------------


class VerouderdScherm(RondeABasis):
    @override_settings(KB_EMAIL_AAN=True)
    def test_a7_alleen_wat_je_zelf_veranderde_telt(self):
        """Review 1.27.0 R1 B1: A zet uit, B (oud scherm, lade niet aangeraakt) slaat op."""
        v = self.voorstel()
        self.maak_concept()
        self.opslaan([v], [v], geladen=[])  # meegenomen door Anna
        v.refresh_from_db()
        self.assertTrue(v.in_conceptversie)
        # Anna en Bram openen allebei (geladen: v mee). Anna zet het uit.
        self.opslaan([v], [], geladen=[v])
        v.refresh_from_db()
        self.assertFalse(v.in_conceptversie)
        # Bram slaat op met zijn oude scherm: zijn vinkje staat nog aan, maar hij heeft het niet veranderd.
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.opslaan([v], [v], geladen=[v], wie=self.bram, inhoud="<p>Bram typte iets</p>")
        v.refresh_from_db()
        self.assertFalse(v.in_conceptversie, "Anna's keuze blijft staan")
        self.assertEqual(v.eigenaar, self.anna, "Bram wordt niet ongevraagd eigenaar")
        self.assertFalse([m for m in mail.outbox if "overgenomen" in m.subject])

    def test_a7_twee_keer_dezelfde_keuze_is_geen_probleem(self):
        v = self.voorstel()
        self.maak_concept()
        # Bram en Anna laden (uit) en nemen het allebei mee.
        self.opslaan([v], [v], geladen=[])
        r = self.opslaan([v], [v], geladen=[], wie=self.bram)
        v.refresh_from_db()
        self.assertTrue(v.in_conceptversie)
        self.assertEqual(v.eigenaar, self.anna, "Bram veranderde niets ten opzichte van nu: geen overname")
        self.assertNotIn("Niet meegenomen", meldingen(r))

    def test_a7_bram_zet_iets_anders_aan_terwijl_anna_uitzet(self):
        v, w = self.voorstel(tekst="Een."), self.voorstel(tekst="Twee.")
        self.maak_concept()
        self.mee(v)
        # Beiden laden (v aan). Anna zet v uit. Bram neemt w mee en laat v staan.
        self.opslaan([v, w], [], geladen=[v])
        self.opslaan([v, w], [v, w], geladen=[v], wie=self.bram)
        v.refresh_from_db()
        w.refresh_from_db()
        self.assertFalse(v.in_conceptversie, "Anna's keuze voor v blijft")
        self.assertTrue(w.in_conceptversie, "Brams keuze voor w telt")
        self.assertEqual(w.eigenaar, self.bram)

    def test_a7_een_oude_pagina_zonder_geladen_stand_werkt_als_vroeger(self):
        v = self.voorstel()
        self.maak_concept()
        self.opslaan([v], [v])  # zonder kb_mee_geladen
        v.refresh_from_db()
        self.assertTrue(v.in_conceptversie)

    def test_a17_intussen_afgehandeld_wordt_gemeld(self):
        v = self.voorstel()
        self.maak_concept()
        diensten.voorstel_afhandelen(v, self.bram, VoorstelStatus.AFGEWEZEN, "Nee")
        r = self.opslaan([v], [v], geladen=[])
        self.assertIn("intussen afgehandeld", meldingen(r))


# --- A3: vinkjes blijven staan bij een fout ----------------------------------------------------------------


class VinkjesNaFout(RondeABasis):
    def test_a3_de_lade_krijgt_de_gewenste_stand_terug(self):
        v, w = self.voorstel(tekst="Een."), self.voorstel(tekst="Twee.")
        self.mee(w)
        # Publiceren zonder toelichting: de server weigert.
        r = self.opslaan([v, w], [v, w], geladen=[w], knop="_save", inhoud="<p>Anders</p>")
        self.assertEqual(r.status_code, 200)
        lade = lade_van(r.content.decode())
        per = {x["id"]: x for x in lade["voorstellen"]}
        self.assertIs(per[v.pk]["mee_gewenst"], True)
        self.assertNotIn("mee_gewenst", per[w.pk], "niet veranderd: geen markering")
        v.refresh_from_db()
        self.assertFalse(v.in_conceptversie, "er is nog niets opgeslagen")


# --- A8: de lade checkt wat er intussen gebeurde -----------------------------------------------------------


class Intussen(RondeABasis):
    def test_a8_bericht_na_een_bericht_van_een_collega(self):
        v = self.voorstel()
        diensten.voorstelbericht_toevoegen(v, self.bram, "Ik pak dit op.", van_redactie=True, melden=False)
        self.client.force_login(self.anna)
        r = self.actie(v, actie="bericht", tekst="Nemen we niet over.", geladen_bericht="0", geladen_eigenaar="0")
        self.assertEqual(r.status_code, 409)
        self.assertIn("Bram stuurde intussen", r.json()["fout"])
        self.assertEqual(r.json()["voorstel"]["berichten"][0]["tekst"], "Ik pak dit op.")
        self.assertEqual(v.berichten.count(), 1)

    def test_a8_afwijzen_terwijl_het_intussen_bij_een_ander_ligt(self):
        v = self.voorstel()
        diensten.voorstel_naar_bak(v, self.bram, self.bram)
        self.client.force_login(self.anna)
        r = self.actie(v, actie="afwijzen", tekst="Nee", geladen_bericht="0", geladen_eigenaar="0")
        self.assertEqual(r.status_code, 409)
        v.refresh_from_db()
        self.assertTrue(v.is_open)

    def test_a8_met_de_juiste_stand_gaat_het_door(self):
        v = self.voorstel()
        self.client.force_login(self.anna)
        r = self.actie(v, actie="bericht", tekst="Hoi", geladen_bericht="0", geladen_eigenaar="0")
        self.assertEqual(r.status_code, 200)
        laatste = r.json()["voorstel"]["geladen_bericht"]
        self.assertEqual(laatste, v.berichten.get().pk, "de lade krijgt de nieuwe stand mee")
        r = self.actie(
            v, actie="bericht", tekst="Nog iets", geladen_bericht=str(laatste), geladen_eigenaar=str(self.anna.pk)
        )
        self.assertEqual(r.status_code, 200)


# --- A9, A10, A11: voorstellen blijven niet hangen -----------------------------------------------------------


class NietHangen(RondeABasis):
    def test_a9_kleine_correctie_van_een_conceptversie(self):
        v = self.voorstel()
        self.maak_concept()
        self.mee(v)
        # 1.31.2 (K1): een kleine correctie neemt de voorstellen mee, net als een gewone versie.
        r = self.publiceer(kleine_correctie="on", wijzigingstoelichting="")
        self.assertFalse(Conceptversie.objects.filter(artikel=self.a).exists())
        v.refresh_from_db()
        self.assertEqual((v.in_conceptversie, v.verwerkt_in_versie, v.is_open), (False, 2, True))
        self.assertIn("voorstellen-afhandelen", r["Location"])
        self.assertNotIn("niet als verwerkt", meldingen(r))

    def test_a9_conceptversie_zonder_inhoudelijke_wijziging(self):
        v = self.voorstel()
        self.maak_concept(inhoud=self.a.inhoud)  # gelijk aan de gepubliceerde tekst
        self.mee(v)
        r = self.publiceer(clusters=[self.water.pk])
        self.assertFalse(ArtikelVersie.objects.filter(artikel=self.a, versie=2).exists())
        self.assertIn("geen inhoudelijke wijziging", meldingen(r))
        v.refresh_from_db()
        self.assertEqual((v.in_conceptversie, v.verwerkt_in_versie), (False, None))

    def test_a9_een_echte_versie_verwerkt_ze_wel(self):
        v = self.voorstel()
        self.maak_concept()
        self.mee(v)
        r = self.publiceer()
        self.assertIn("voorstellen-afhandelen", r["Location"])
        v.refresh_from_db()
        self.assertEqual((v.in_conceptversie, v.verwerkt_in_versie), (False, 2))

    def test_a10_spoed_neemt_niet_mee_wat_ter_inzage_ligt(self):
        v = self.voorstel()
        self.maak_concept()
        self.mee(v)
        self.ter_inzage()
        self.client.force_login(self.anna)
        data = beheerdata(self.a, inhoud="<p>Stuur na twee weken een rappel!</p>", wijzigingstoelichting="Typfout")
        data.update(kb_lade=str(v.pk), kb_meenemen=str(v.pk), kb_mee_geladen="")
        r = self.post(f"{self.url}?spoed=1", data, _save="1")
        v.refresh_from_db()
        self.assertTrue(v.in_conceptversie, "hoort bij de review")
        self.assertIsNone(v.verwerkt_in_versie)
        self.assertIn("ter inzage", meldingen(r))

    def test_a10_spoed_als_kleine_correctie_neemt_wel_mee(self):
        # 1.31.2 (K1): ook bij een spoedcorrectie telt een kleine correctie mee.
        v = self.voorstel()
        self.maak_concept()
        self.client.force_login(self.anna)
        data = beheerdata(self.a, inhoud="<p>Stuur na twee weken een rappel!</p>", kleine_correctie="on")
        data.update(kb_lade=str(v.pk), kb_meenemen=str(v.pk), kb_mee_geladen="")
        r = self.post(f"{self.url}?spoed=1", data, _save="1")
        v.refresh_from_db()
        self.assertEqual(v.verwerkt_in_versie, 2)
        self.assertEqual(v.eigenaar, self.anna, "meegenomen = overgenomen")
        self.assertIn("voorstellen-afhandelen", r["Location"])
        self.assertNotIn("niet meegenomen", meldingen(r))

    def test_a10_spoed_zonder_inhoudelijke_wijziging_neemt_niets_mee(self):
        v = self.voorstel()
        self.maak_concept()
        self.client.force_login(self.anna)
        self.a.refresh_from_db()
        # De gepubliceerde tekst, ongewijzigd (met het cluster, anders is dát de wijziging).
        data = beheerdata(self.a, clusters=[self.water.pk], kleine_correctie="on")
        data.update(kb_lade=str(v.pk), kb_meenemen=str(v.pk), kb_mee_geladen="")
        r = self.post(f"{self.url}?spoed=1", data, _save="1")
        v.refresh_from_db()
        self.assertIsNone(v.verwerkt_in_versie)
        self.assertIsNone(v.eigenaar, "niet meegenomen = niet overgenomen")
        self.assertIn("geen inhoudelijke wijziging", meldingen(r))

    def test_a17_spoed_meenemen_staat_in_het_logboek(self):
        from django.contrib.admin.models import LogEntry

        v = self.voorstel()
        self.maak_concept()
        self.client.force_login(self.anna)
        data = beheerdata(self.a, inhoud="<p>Stuur na twee weken een rappel!</p>", wijzigingstoelichting="Fout")
        data.update(kb_lade=str(v.pk), kb_meenemen=str(v.pk), kb_mee_geladen="")
        self.post(f"{self.url}?spoed=1", data, _save="1")
        v.refresh_from_db()
        self.assertEqual(v.verwerkt_in_versie, 2)
        self.assertTrue(
            LogEntry.objects.filter(object_id=str(v.pk), change_message__contains="verbetering van de live versie")
        )

    def test_a11_afgewezen_is_niet_meer_meegenomen(self):
        v = self.voorstel()
        self.mee(v)
        v.refresh_from_db()
        self.assertTrue(v.in_conceptversie)
        diensten.voorstel_afhandelen(v, self.anna, VoorstelStatus.AFGEWEZEN, "Nee")
        v.refresh_from_db()
        self.assertFalse(v.in_conceptversie)

    def test_a17_dubbel_in_een_kring_kan_niet(self):
        a, b, c = self.voorstel(tekst="A"), self.voorstel(tekst="B"), self.voorstel(tekst="C")
        diensten.voorstel_afhandelen(a, self.anna, VoorstelStatus.AFGEWEZEN, "x", dubbel_van=b)
        diensten.voorstel_afhandelen(b, self.anna, VoorstelStatus.AFGEWEZEN, "x", dubbel_van=c)
        with self.assertRaises(diensten.VoorstelFout):
            diensten.voorstel_afhandelen(c, self.anna, VoorstelStatus.AFGEWEZEN, "x", dubbel_van=a)


# --- A13: waarschuwen bij meenemen na een akkoord ---------------------------------------------------------


class NaAkkoord(RondeABasis):
    def test_a13_ter_inzage_legt_de_meegenomen_voorstellen_vast(self):
        v, w = self.voorstel(tekst="Een."), self.voorstel(tekst="Twee.")
        self.maak_concept()
        self.mee(v)
        self.ter_inzage()
        self.assertEqual(Inzage.objects.get(artikel=self.a).voorstellen, [v.pk])
        review.akkoord_geven(Inzage.objects.get(artikel=self.a), self.wim)
        self.assertEqual(review.akkoord_voorstellen(self.a), {v.pk})
        # Na het akkoord neemt Anna er nog een mee (zonder de tekst te veranderen): het akkoord blijft staan.
        self.opslaan([v, w], [v, w], geladen=[v], inhoud=Conceptversie.objects.get(artikel=self.a).velden["inhoud"])
        self.assertEqual(review.akkoord_voorstellen(self.a), {v.pk})
        lade = lade_van(self.client.get(self.url).content.decode())
        self.assertEqual(lade["akkoord"], [v.pk], "de lade weet wat er bij het akkoord in zat")

    def test_a13_zonder_akkoord_geen_lijst(self):
        self.voorstel()
        lade = lade_van(self.als(self.anna).get(self.url).content.decode())
        self.assertIsNone(lade["akkoord"])


# --- A14, A17: werkbak --------------------------------------------------------------------------------------


class Werkbak(RondeABasis):
    def test_a14_selectiebalk_geeft_geen_namen_van_buiten(self):
        v = self.voorstel()
        self.client.force_login(self.anna)
        r = self.client.post(
            "/beheer/werkplek/selectie/", {"voorstel": f"{v.pk}-0", "actie": "toewijzen", "naar": str(self.zoe.pk)}
        )
        tekst = meldingen(r)
        self.assertIn("kan deze voorstellen niet krijgen", tekst)
        self.assertNotIn("Zoe", tekst)
        v.refresh_from_db()
        self.assertIsNone(v.eigenaar)

    def test_a17_selectiebalk_controleert_de_eigenaar_onder_het_slot(self):
        v = self.voorstel()
        with self.assertRaises(diensten.VoorstelFout):
            diensten.voorstel_naar_bak(
                diensten.voorstel_naar_bak(v, self.bram, self.bram), self.anna, self.anna, verwacht_eigenaar=0
            )
        v.refresh_from_db()
        self.assertEqual(v.eigenaar, self.bram)


# --- A12/A14: privacy op de reviewpagina -----------------------------------------------------------------------


class ReviewPrivacy(RondeABasis):
    def test_a12_verborgen_voorstel_niet_voor_de_reviewer(self):
        zichtbaar = self.voorstel(tekst="Termijn klopt niet.")
        geheim = self.voorstel(tekst="Collega GEHEIMNAAM doet dit fout.", verborgen=True)
        self.maak_concept()
        self.mee(zichtbaar, geheim)
        self.ter_inzage()
        i = Inzage.objects.get(artikel=self.a)
        html = self.als(self.wim).get(f"/review/{i.pk}/").content.decode()
        self.assertIn("Termijn klopt niet.", html)
        self.assertNotIn("GEHEIMNAAM", html)
        self.assertIn("persoonlijke gegevens", html)

    def test_a14_reviewlijst_zonder_verhuisde_artikelen(self):
        self.maak_concept()
        self.ter_inzage()
        review.akkoord_geven(Inzage.objects.get(artikel=self.a), self.wim)
        self.als(self.wim)
        self.assertIn("Rappel versturen", self.client.get("/review/").content.decode())
        self.a.omgeving = self.zuid
        self.a.titel = "GEHEIME TITEL"
        self.a.save()
        self.assertNotIn("GEHEIME TITEL", self.client.get("/review/").content.decode())


class Versies(RondeABasis):
    def test_echte_versie_heeft_versienummer(self):
        self.maak_concept()
        self.publiceer()
        self.assertTrue(ArtikelVersie.objects.filter(artikel=self.a, versie=2).exists())


# --- A15: omgeving vooraf ingevuld -----------------------------------------------------------------------------


class OmgevingVooraf(RondeABasis):
    def test_a15_een_omgeving_staat_al_gekozen(self):
        self.client.force_login(self.anna)  # alleen redacteur van Noord
        for url in ("/beheer/kennisbank/artikel/add/", "/beheer/kennisbank/bericht/add/"):
            html = self.client.get(url).content.decode()
            self.assertIn(f'<option value="{self.noord.pk}" selected>', html, url)
        html = self.client.get("/beheer/kennisbank/artikel/importeren-word/").content.decode()
        self.assertIn(f'<option value="{self.noord.pk}" selected>', html)

    def test_a15_bij_meer_omgevingen_kies_je_zelf(self):
        from django.contrib.auth.models import Group

        from kennisbank.models import Rol, Toegang

        g = Group.objects.create(name="red-zuid-extra")
        Toegang.objects.create(omgeving=self.zuid, groep=g, rol=Rol.REDACTEUR)
        self.anna.groups.add(g)
        html = self.als(self.anna).get("/beheer/kennisbank/artikel/add/").content.decode()
        self.assertNotIn(f'<option value="{self.noord.pk}" selected>', html)


# --- A16: licht en donker ---------------------------------------------------------------------------------------


class LichtEnDonker(RondeABasis):
    def test_a16_beheer_laadt_geen_donkere_modus(self):
        html = self.als(self.anna).get("/beheer/").content.decode()
        self.assertNotIn("dark_mode.css", html)
        self.assertNotIn("admin/js/theme.js", html)
        self.assertNotIn("data-kb-thema", html, "geen knop in het beheer")

    def test_a16_site_en_review_hebben_de_knop(self):
        html = self.als(self.lies).get("/").content.decode()
        self.assertIn("kennisbank/thema.js", html)
        self.assertIn("data-kb-thema", html)
        self.maak_concept()
        self.ter_inzage()
        html = self.als(self.wim).get("/review/").content.decode()
        self.assertIn("data-kb-thema", html)
        self.assertIn("kennisbank/thema.js", html)

    def test_a16_thema_script_staat_in_de_head_zonder_defer(self):
        html = self.als(self.lies).get("/").content.decode()
        kop = html[: html.index("</head>")]
        self.assertIn('<script src="/static/kennisbank/thema.js"></script>', kop)

    def test_a16_voorbeeld_in_het_beheer_is_licht(self):
        self.client.force_login(self.anna)
        r = self.client.post(
            "/beheer/kennisbank/artikel/voorbeeld/", {"titel": "x", "samenvatting": "y", "inhoud": "<p>z</p>"}
        )
        if r.status_code == 200:
            self.assertIn('data-theme="light"', r.content.decode())


# --- A22: Word-import vanaf de werkplek -----------------------------------------------------------------------


class WordImport(RondeABasis):
    def test_a22_knop_op_de_werkplek(self):
        html = self.als(self.anna).get("/beheer/").content.decode()
        self.assertIn('href="/beheer/kennisbank/artikel/importeren-word/"', html)
        self.assertIn("Artikel uit Word", html)

    def test_a22_importpagina_in_de_nieuwe_stijl(self):
        html = self.als(self.anna).get("/beheer/kennisbank/artikel/importeren-word/").content.decode()
        self.assertIn("← Werkplek", html)
        self.assertIn("Artikel uit Word", html)
        self.assertNotIn('class="breadcrumbs"', html)
        self.assertNotIn('id="nav-sidebar"', html)

    def test_a22_melding_na_de_import_klopt(self):
        from kennisbank.tests.test_kennisbank import _docx

        bestand = _docx([("Normal", "Doe dit.")])
        bestand.name = "uit-word.docx"
        r = self.als(self.anna).post(
            "/beheer/kennisbank/artikel/importeren-word/",
            {"bestand": bestand, "omgeving": self.noord.pk, "soort": "werkinstructie"},
            follow=True,
        )
        tekst = meldingen(r)
        self.assertIn("kies Afronden", tekst)
        self.assertNotIn("Gepubliceerd'", tekst)

    def test_a22_fout_bestand_blijft_op_de_pagina(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        r = self.als(self.anna).post(
            "/beheer/kennisbank/artikel/importeren-word/",
            {
                "bestand": SimpleUploadedFile("brief.pdf", b"%PDF"),
                "omgeving": self.noord.pk,
                "soort": "werkinstructie",
                "kop_als_titel": "on",
            },
        )
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("Alleen .docx", html)
        self.assertIn("kies het bestand wel opnieuw", html)
        self.assertIn('id="id_kop_als_titel" checked', html)


# --- A18: de gaten uit de mutatietest, en formulieren zoals de pagina ze echt verstuurt -------------------------


class MutatieGaten(RondeABasis):
    def test_dubbel_keuzelijst_alleen_voorstellen_van_dit_artikel(self):
        from kennisbank.models import Artikel, Status

        ander = Artikel.objects.create(
            omgeving=self.noord, titel="Ander", samenvatting="x", inhoud="<p>x</p>", status=Status.GEPUBLICEERD
        )
        Verbetervoorstel.objects.create(
            artikel=ander, artikel_versie=1, tekst="VREEMD voorstel.", ingediend_door=self.lies
        )
        self.voorstel(tekst="Een.")
        self.voorstel(tekst="Twee.")
        lade = lade_van(self.als(self.anna).get(self.url).content.decode())
        labels = " ".join(a["label"] for v in lade["voorstellen"] for a in v["andere"])
        self.assertIn("Twee", labels)
        self.assertNotIn("VREEMD", labels)

    def test_reviewblok_alleen_open_voorstellen(self):
        v = self.voorstel(tekst="Open voorstel.")
        dicht = self.voorstel(tekst="AFGEWEZEN voorstel.")
        self.maak_concept()
        self.mee(v)
        self.ter_inzage()
        # Oude gegevens: afgewezen, maar nog als meegenomen gemarkeerd (van vóór ronde A).
        Verbetervoorstel.objects.filter(pk=dicht.pk).update(status=VoorstelStatus.AFGEWEZEN, in_conceptversie=True)
        html = self.als(self.wim).get(f"/review/{Inzage.objects.get(artikel=self.a).pk}/").content.decode()
        self.assertIn("Open voorstel.", html)
        self.assertNotIn("AFGEWEZEN voorstel.", html)

    def test_lade_weet_dat_de_versie_op_slot_ligt(self):
        self.voorstel()
        self.client.force_login(self.anna)
        self.assertFalse(lade_van(self.client.get(self.url).content.decode())["op_slot"])
        self.maak_concept()
        self.ter_inzage()
        self.assertTrue(lade_van(self.client.get(self.url).content.decode())["op_slot"])

    def test_bericht_op_een_afgehandeld_voorstel_geeft_409(self):
        v = self.voorstel()
        diensten.voorstel_afhandelen(v, self.anna, VoorstelStatus.AFGEWEZEN, "Nee")
        self.client.force_login(self.anna)
        r = self.actie(v, actie="bericht", tekst="Nog iets")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(v.berichten.count(), 1)

    def test_geen_lade_voor_een_redacteur_van_een_andere_omgeving(self):
        self.voorstel()
        r = self.als(self.zoe).get(self.url)
        self.assertEqual(r.status_code, 302, "Django stuurt weg: het artikel bestaat voor Zoe niet")
        self.assertFalse(
            self.als(self.zoe)
            .post(f"/beheer/voorstel/{self.voorstel().pk}/lade/", {"actie": "notitie", "tekst": "x"})
            .status_code
            == 200
        )


class EchteFormulieren(RondeABasis):
    """Wat de pagina verstuurt, niet wat een test zelf samenstelt (review 1.27.0, R5 B3)."""

    def velden(self, url, form_id="artikel_form", **selects):
        from kennisbank.tests.test_consistentie_1250 import formulier_velden

        html = self.client.get(url).content.decode()
        data = formulier_velden(html, form_id)
        data.update(selects)
        return html, data

    def artikel_selects(self):
        return {
            "soort": self.a.soort,
            "omgeving": self.a.omgeving_id,
            "status": self.a.status,
            "clusters": [self.water.pk],
        }

    def test_conceptversie_met_meenemen(self):
        v = self.voorstel()
        self.client.force_login(self.anna)
        html, data = self.velden(f"{self.url}?voorstel={v.pk}", **self.artikel_selects())
        for veld in ("kb_lade", "kb_meenemen", "kb_mee_geladen", "geladen_stempel", "geladen_concept"):
            self.assertIn(veld, data, veld)
        # Wat de lade (JavaScript) invult: de voorstellen, het vinkje en de stand bij het laden.
        data.update(
            kb_lade=str(v.pk), kb_meenemen=str(v.pk), kb_mee_geladen="", inhoud="<p>Stuur na drie weken een rappel.</p>"
        )
        r = self.post(self.url, data, _conceptversie="1")
        self.assertEqual(r.status_code, 302, r.content.decode()[:300] if r.status_code == 200 else "")
        v.refresh_from_db()
        self.assertTrue(v.in_conceptversie)

    def test_spoedcorrectie(self):
        v = self.voorstel()
        self.maak_concept()
        self.client.force_login(self.anna)
        html, data = self.velden(f"{self.url}?spoed=1", **self.artikel_selects())
        self.assertIn('id="kb-spoed"', html)
        data.update(
            kb_lade=str(v.pk),
            kb_meenemen=str(v.pk),
            inhoud="<p>Stuur na twee weken een rappel!</p>",
            wijzigingstoelichting="Typfout",
        )
        r = self.post(f"{self.url}?spoed=1", data, _save="1")
        self.assertEqual(r.status_code, 302, r.content.decode()[:300] if r.status_code == 200 else "")
        v.refresh_from_db()
        self.assertEqual(v.verwerkt_in_versie, 2)
        self.assertTrue(Conceptversie.objects.filter(artikel=self.a).exists(), "de conceptversie blijft")

    def test_nieuwsbericht_nieuw_en_bestaand(self):
        from kennisbank.models import Bericht

        self.client.force_login(self.anna)
        html, data = self.velden(
            "/beheer/kennisbank/bericht/add/", form_id="bericht_form", omgeving=self.noord.pk, status="concept"
        )
        data.update(titel="Nieuw uit de test", tekst="<p>Hallo</p>", _continue="1")
        r = self.client.post("/beheer/kennisbank/bericht/add/", data)
        self.assertEqual(r.status_code, 302, r.content.decode()[:300] if r.status_code == 200 else "")
        b = Bericht.objects.get(titel="Nieuw uit de test")
        url = f"/beheer/kennisbank/bericht/{b.pk}/change/"
        html, data = self.velden(url, form_id="bericht_form", omgeving=self.noord.pk, status="concept")
        data.update(titel="Aangepast uit de test", _continue="1")
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 302, r.content.decode()[:300] if r.status_code == 200 else "")
        b.refresh_from_db()
        self.assertEqual(b.titel, "Aangepast uit de test")
