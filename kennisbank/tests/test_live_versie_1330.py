"""1.33.0: de live versie verbeteren buiten het concept, en in het concept overnemen wat er live veranderde.

Bouwlijst `bouwlijst-1.33.0-live-versie-bijgewerkt.md`, punten L1 t/m L4.
"""

import json
from pathlib import Path

from django.conf import settings
from django.contrib.messages import get_messages

from kennisbank import diensten, livewijzigingen, review
from kennisbank.livewijzigingen import besluiten_bijwerken, neem_over, telling, vergelijk
from kennisbank.models import ArtikelVersie, Conceptversie
from kennisbank.tests.test_consistentie_1250 import balk_van
from kennisbank.tests.test_kennisbank import beheerdata
from kennisbank.tests.test_review_c1 import ReviewBasis


def P(tekst):
    return f"<p>{tekst}</p>"


def S(kop, *alineas):
    return f'<section class="sectie"><h2 class="sectie-kop">{kop}</h2>{"".join(alineas)}</section>'


WANNEER = "Het eerste rappel gaat uit na de reactietermijn. Het tweede rappel volgt 2 weken later."
LOGBOEK = "Leg elke verzending vast in het logboek van de zaak, met het kenmerk van de brief."
PDF = "Sla de brief op als PDF in de zaak."
SPOED = "Bel bij spoed de meldkamer op 088 555 01 00 en noteer het gesprek."
OVERLEG = "Overleg bij twijfel met de coördinator over een last onder dwangsom."
LIJST = "<ul><li><p>een</p></li><li><p>twee</p></li></ul>"

BASIS = (
    P("Inleiding bij het rappel.")
    + S("Wanneer", P(WANNEER))
    + S("Vastleggen", P(LOGBOEK), P(PDF))
    + S("Bij spoed", P(SPOED), LIJST)
    + S("Geen reactie", P("Komt er geen reactie, dan volgt overleg."), P(OVERLEG))
)


def velden(inhoud, titel="Rappel versturen", samenvatting="Hoe je een rappel verstuurt."):
    return {"titel": titel, "samenvatting": samenvatting, "inhoud": inhoud}


def per_soort(v):
    return {(w["soort"], w["sectie"]): w for w in v.wijzigingen}


# --- De vergelijking zelf (livewijzigingen.py) ----------------------------------------------------------------


class Vergelijken(ReviewBasis):
    def test_veilig_de_alinea_is_in_het_concept_niet_aangeraakt(self):
        live = BASIS.replace("01 00", "01 42")
        v = vergelijk(velden(BASIS), velden(live), velden(BASIS))
        self.assertEqual(len(v.wijzigingen), 1)
        w = v.wijzigingen[0]
        self.assertEqual(
            (w["soort"], w["auto"], w["stand"], w["sectie"], w["plek"]), ("veilig", True, "open", "Bij spoed", "alinea")
        )
        self.assertIn("<del>00</del><ins>42</ins>", w["live"])
        nieuw, gedaan = neem_over(velden(BASIS), velden(live), velden(BASIS), [w["id"]])
        self.assertEqual(gedaan, [w["id"]])
        self.assertEqual(nieuw["inhoud"], live)

    def test_veilig_laat_ander_werk_in_het_concept_staan(self):
        live = BASIS.replace("01 00", "01 42")
        concept = BASIS.replace(PDF, "Sla de brief op als PDF in de zaak, niet in je mailbox.")
        nieuw, _ = neem_over(velden(BASIS), velden(live), velden(concept), "veilig")
        self.assertIn("01 42", nieuw["inhoud"])
        self.assertIn("niet in je mailbox", nieuw["inhoud"])
        self.assertEqual(vergelijk(velden(BASIS), velden(live), nieuw).wijzigingen[0]["stand"], "overgenomen")

    def test_zelf_dezelfde_alinea_is_in_het_concept_ook_gewijzigd(self):
        live = BASIS.replace("2 weken", "3 weken")
        concept = BASIS.replace("volgt 2 weken later.", "volgt 2 weken later, tenzij de zaak spoed heeft.")
        v = vergelijk(velden(BASIS), velden(live), velden(concept))
        w = v.wijzigingen[0]
        self.assertEqual((w["soort"], w["auto"], w["stand"]), ("zelf", False, "open"))
        self.assertIn("tenzij de zaak spoed heeft", w["concept"])
        self.assertFalse(v.kan_overnemen(w["id"]))
        # "Alles veilig" blijft van deze alinea af: de tekst van de redacteur wordt nooit vervangen.
        nieuw, gedaan = neem_over(velden(BASIS), velden(live), velden(concept), "veilig")
        self.assertEqual((gedaan, nieuw["inhoud"]), ([], concept))
        # Ook als iemand het id rechtstreeks opgeeft.
        nieuw, gedaan = neem_over(velden(BASIS), velden(live), velden(concept), [w["id"]])
        self.assertEqual((gedaan, nieuw["inhoud"]), ([], concept))

    def test_zelf_overgetikt_telt_als_overgenomen(self):
        live = BASIS.replace("2 weken", "3 weken")
        v = vergelijk(velden(BASIS), velden(live), velden(live.replace("01 00", "01 99")))
        self.assertEqual([w["stand"] for w in v.wijzigingen], ["overgenomen"])

    def test_weg_de_alinea_staat_niet_meer_in_het_concept(self):
        live = BASIS.replace("coördinator", "teamleider")
        concept = BASIS.replace(P(OVERLEG), "")
        w = vergelijk(velden(BASIS), velden(live), velden(concept)).wijzigingen[0]
        self.assertEqual((w["soort"], w["auto"], w["stand"], w["anker"]), ("weg", False, "open", None))

    def test_nieuw_een_alinea_komt_na_zijn_buurman(self):
        live = BASIS.replace(P(PDF), P(PDF) + P("Stuur een kopie naar de mailbox."))
        v = vergelijk(velden(BASIS), velden(live), velden(BASIS))
        w = v.wijzigingen[0]
        self.assertEqual((w["soort"], w["auto"], w["sectie"]), ("nieuw", True, "Vastleggen"))
        self.assertEqual((w["anker"]["sleutel"], w["anker"]["na"]), (PDF.replace(" ", ""), True))
        nieuw, _ = neem_over(velden(BASIS), velden(live), velden(BASIS), [w["id"]])
        self.assertEqual(nieuw["inhoud"], live)

    def test_nieuw_als_eerste_komt_voor_zijn_buurman(self):
        live = BASIS.replace(P(LOGBOEK), P("Eerst dit.") + P(LOGBOEK))
        w = vergelijk(velden(BASIS), velden(live), velden(BASIS)).wijzigingen[0]
        self.assertTrue(w["anker"]["na"] or w["anker"]["voor"])
        nieuw, _ = neem_over(velden(BASIS), velden(live), velden(BASIS), "veilig")
        self.assertEqual(nieuw["inhoud"], live)

    def test_nieuw_opsommingspunt_komt_in_de_lijst(self):
        live = BASIS.replace("<li><p>twee</p></li>", "<li><p>twee</p></li><li><p>drie</p></li>")
        v = vergelijk(velden(BASIS), velden(live), velden(BASIS))
        self.assertEqual(v.wijzigingen[0]["plek"], "opsommingspunt")
        nieuw, _ = neem_over(velden(BASIS), velden(live), velden(BASIS), "veilig")
        self.assertIn("<ul><li><p>een</p></li><li><p>twee</p></li><li><p>drie</p></li></ul>", nieuw["inhoud"])

    def test_nieuwe_sectie_is_een_wijziging_en_komt_op_zijn_plek(self):
        nieuw_stuk = S(
            "Uitzonderingen",
            P("Bij een overtreder in het buitenland gelden langere termijnen."),
            P("Is de overtreder failliet, stuur het rappel dan aan de curator."),
        )
        live = BASIS + nieuw_stuk
        # In het concept is de laatste alinea van de sectie ervoor weggehaald: de plek wordt toch gevonden.
        concept = BASIS.replace(P(OVERLEG), "")
        v = vergelijk(velden(BASIS), velden(live), velden(concept))
        nieuwe = [w for w in v.wijzigingen if w["soort"] == "nieuw"]
        self.assertEqual(len(nieuwe), 1, "kop en twee alinea's horen bij elkaar")
        self.assertEqual(nieuwe[0]["live"].count("<ins>"), 3)
        nieuw, _ = neem_over(velden(BASIS), velden(live), velden(concept), [nieuwe[0]["id"]])
        self.assertTrue(nieuw["inhoud"].endswith(nieuw_stuk))

    def test_nieuw_zonder_plek_gaat_met_de_hand(self):
        live = P("Helemaal nieuw.") + BASIS
        concept = P("Het concept is helemaal anders.")
        nieuwe = [
            w for w in vergelijk(velden(BASIS), velden(live), velden(concept)).wijzigingen if w["soort"] == "nieuw"
        ]
        self.assertEqual((nieuwe[0]["auto"], nieuwe[0]["anker"]), (False, None))

    def test_twee_nieuwe_alineas_houden_hun_volgorde_wat_je_ook_eerst_overneemt(self):
        live = BASIS.replace(P(PDF), P(PDF) + P("Nieuw één.") + P("Nieuw twee."))
        v = vergelijk(velden(BASIS), velden(live), velden(BASIS))
        een, twee = [w["id"] for w in v.wijzigingen]
        for volgorde in ([een, twee], [twee, een]):
            mijn = velden(BASIS)
            for wid in volgorde:
                mijn, gedaan = neem_over(velden(BASIS), velden(live), mijn, [wid])
                self.assertEqual(gedaan, [wid])
            self.assertEqual(mijn["inhoud"], live, volgorde)

    def test_verwijderd_weghalen_uit_het_concept(self):
        live = BASIS.replace(P("Inleiding bij het rappel."), "").replace("<li><p>twee</p></li>", "")
        v = vergelijk(velden(BASIS), velden(live), velden(BASIS))
        self.assertEqual([(w["soort"], w["auto"]) for w in v.wijzigingen], [("verwijderd", True)] * 2)
        self.assertIn("<del>Inleiding bij het rappel.</del>", v.wijzigingen[0]["live"])
        nieuw, gedaan = neem_over(velden(BASIS), velden(live), velden(BASIS), "veilig")
        self.assertEqual(len(gedaan), 2)
        self.assertEqual(nieuw["inhoud"], live, "ook de <li> om de alinea is weg, niet alleen de <p>")

    def test_verwijderd_maar_in_het_concept_herschreven_is_handwerk(self):
        live = BASIS.replace(P(PDF), "")
        concept = BASIS.replace(PDF, "Sla de brief altijd op als PDF in de zaak.")
        w = vergelijk(velden(BASIS), velden(live), velden(concept)).wijzigingen[0]
        self.assertEqual((w["soort"], w["auto"]), ("zelf", False))

    def test_verwijderd_al_weg_in_het_concept_is_klaar(self):
        live = BASIS.replace(P(PDF), "")
        w = vergelijk(velden(BASIS), velden(live), velden(live)).wijzigingen[0]
        self.assertEqual(w["stand"], "overgenomen")

    def test_sectiekop_en_tabelcel_haalt_de_kennisbank_niet_zelf_weg(self):
        tabel = "<table><tbody><tr><td><p>links</p></td><td><p>rechts</p></td></tr></tbody></table>"
        basis = BASIS + tabel
        live = BASIS.replace('<h2 class="sectie-kop">Vastleggen</h2>', "") + tabel.replace("<td><p>rechts</p></td>", "")
        v = vergelijk(velden(basis), velden(live), velden(basis))
        self.assertEqual([(w["soort"], w["auto"]) for w in v.wijzigingen], [("verwijderd", False)] * 2)
        nieuw, gedaan = neem_over(velden(basis), velden(live), velden(basis), "veilig")
        self.assertEqual((gedaan, nieuw["inhoud"]), ([], basis))

    def test_titel_en_samenvatting(self):
        basis, live = velden(BASIS), velden(BASIS, titel="Rappel sturen", samenvatting="Nieuwe samenvatting.")
        v = vergelijk(basis, live, velden(BASIS, samenvatting="Eigen samenvatting."))
        titel, samen = v.wijzigingen
        self.assertEqual(
            (titel["sectie"], titel["soort"], titel["auto"], titel["anker"]),
            ("Titel", "veilig", True, {"veld": "titel"}),
        )
        self.assertEqual((samen["sectie"], samen["soort"], samen["auto"]), ("Samenvatting", "zelf", False))
        nieuw, gedaan = neem_over(basis, live, velden(BASIS, samenvatting="Eigen samenvatting."), "veilig")
        self.assertEqual(
            (nieuw["titel"], nieuw["samenvatting"], len(gedaan)), ("Rappel sturen", "Eigen samenvatting.", 1)
        )

    def test_alles_veilig_in_een_keer_bij_veel_wijzigingen(self):
        live = (
            BASIS.replace("01 00", "01 42")
            .replace("het kenmerk van", "het kenmerk en de datum van")
            .replace(P(PDF), P(PDF) + P("Stuur een kopie naar de mailbox."))
            .replace("2 weken", "3 weken")
            .replace("coördinator", "teamleider")
        )
        concept = BASIS.replace("volgt 2 weken later.", "volgt 2 weken later, tenzij spoed.").replace(P(OVERLEG), "")
        v = vergelijk(velden(BASIS), velden(live), velden(concept))
        self.assertEqual(sorted(w["soort"] for w in v.wijzigingen), ["nieuw", "veilig", "veilig", "weg", "zelf"])
        self.assertEqual(
            [w["sectie"] for w in v.wijzigingen], ["Wanneer", "Vastleggen", "Vastleggen", "Bij spoed", "Geen reactie"]
        )
        self.assertEqual(telling(v.wijzigingen), {"totaal": 5, "open": 5, "niet": 0, "vervalt": 5})
        nieuw, gedaan = neem_over(velden(BASIS), velden(live), velden(concept), "veilig")
        self.assertEqual(len(gedaan), 3)
        na = vergelijk(velden(BASIS), velden(live), nieuw)
        self.assertEqual(
            sorted(w["stand"] for w in na.wijzigingen), ["open", "open", "overgenomen", "overgenomen", "overgenomen"]
        )
        self.assertIn("tenzij spoed", nieuw["inhoud"])
        # De ids veranderen niet door het overnemen: zo blijven de besluiten bij de goede wijziging.
        self.assertEqual([w["id"] for w in v.wijzigingen], [w["id"] for w in na.wijzigingen])

    def test_dubbele_alinea_de_goede_wordt_aangewezen(self):
        basis = P("Zie de bijlage.") + S("A", P("Tekst a.")) + P("Zie de bijlage.") + S("B", P("Tekst b."))
        live = basis.replace("Tekst b.", "Tekst b, verbeterd.")
        concept = basis
        w = vergelijk(velden(basis), velden(live), velden(concept)).wijzigingen[0]
        self.assertEqual(w["anker"], {"sleutel": "Tekstb.", "nr": 0})
        live2 = P("Zie de bijlage.") + S("A", P("Tekst a.")) + P("Zie de bijlage, pagina 2.") + S("B", P("Tekst b."))
        w = vergelijk(velden(basis), velden(live2), velden(concept)).wijzigingen[0]
        self.assertEqual(w["anker"], {"sleutel": "Ziedebijlage.", "nr": 1})
        nieuw, _ = neem_over(velden(basis), velden(live2), velden(concept), "veilig")
        self.assertEqual(nieuw["inhoud"], live2)

    def test_tekst_uit_het_artikel_komt_ge_escaped_in_het_paneel(self):
        basis = P("Gebruik &lt;b&gt; niet.")
        live = P("Gebruik &lt;script&gt;alert(1)&lt;/script&gt; niet.") + P("Nieuw &lt;img src=x&gt;.")
        v = vergelijk(velden(basis), velden(live), velden(basis))
        for w in v.wijzigingen:
            self.assertNotIn("<script", w["live"])
            self.assertNotIn("<img", w["live"])
        self.assertIn("&lt;script&gt;", v.wijzigingen[0]["live"])

    def test_alleen_opmaak_is_geen_wijziging(self):
        live = BASIS.replace("meldkamer", "<strong>meldkamer</strong>")
        self.assertEqual(vergelijk(velden(BASIS), velden(live), velden(BASIS)).wijzigingen, [])


class Besluiten(ReviewBasis):
    def test_besluit_bepaalt_de_stand_en_de_telling(self):
        live = BASIS.replace("01 00", "01 42").replace("2 weken", "3 weken")
        v = vergelijk(velden(BASIS), velden(live), velden(BASIS))
        a, b = [w["id"] for w in v.wijzigingen]
        besluiten = {a: {"besluit": "niet", "door": "Anna", "op": "2026-11-14T10:00:00"}}
        v = vergelijk(velden(BASIS), velden(live), velden(BASIS), besluiten)
        self.assertEqual([(w["stand"], w["door"]) for w in v.wijzigingen], [("niet", "Anna"), ("open", "")])
        self.assertEqual(telling(v.wijzigingen), {"totaal": 2, "open": 1, "niet": 1, "vervalt": 2})
        # "Alles veilig" slaat over wat bewust niet is overgenomen; uitdrukkelijk overnemen kan nog wel.
        _, gedaan = neem_over(velden(BASIS), velden(live), velden(BASIS), "veilig", besluiten)
        self.assertEqual(gedaan, [b])
        _, gedaan = neem_over(velden(BASIS), velden(live), velden(BASIS), [a], besluiten)
        self.assertEqual(gedaan, [a])

    def test_naam_en_tijd_komen_van_de_server(self):
        a, b, c = "a" * 16, "b" * 16, "c" * 16
        oud = {
            a: {"besluit": "niet", "door": "Bram", "op": "gisteren"},
            c: {"besluit": "gezien", "door": "Bram", "op": "gisteren"},
        }
        nieuw = besluiten_bijwerken(
            oud,
            {
                a: "niet",
                b: {"besluit": "aangepast", "door": "Iemand Anders", "op": "1900"},
                "kort": "niet",
                "d" * 16: "overgenomen",
                c: "aangepast",
            },
            "Anna",
            "nu",
        )
        self.assertEqual(
            nieuw[a], {"besluit": "niet", "door": "Bram", "op": "gisteren"}, "ongewijzigd: blijft van Bram"
        )
        self.assertEqual(
            nieuw[b], {"besluit": "aangepast", "door": "Anna", "op": "nu"}, "de naam uit het verzoek telt niet"
        )
        self.assertEqual(nieuw[c]["door"], "Anna", "een ander besluit is van wie het nu neemt")
        self.assertEqual(set(nieuw), {a, b, c}, "een ongeldig id of onbekend besluit valt weg")
        self.assertEqual(besluiten_bijwerken(oud, "onzin", "Anna", "nu"), oud)


# --- In het bewerkscherm (L2) ---------------------------------------------------------------------------------


class LiveBasis(ReviewBasis):
    """Een artikel met secties, een concept van Anna, en daarna een verbetering van de live versie door Bram."""

    CONCEPT = BASIS.replace("volgt 2 weken later.", "volgt 2 weken later, tenzij de zaak spoed heeft.")
    LIVE = BASIS.replace("01 00", "01 42").replace("2 weken", "3 weken")

    def setUp(self):
        super().setUp()
        self.a.inhoud = BASIS
        self.a.save()
        diensten.herbouw_secties(self.a)
        diensten.registreer_publicatie(self.a, self.anna, "Secties")
        self.a.refresh_from_db()
        self.maak_concept(inhoud=self.CONCEPT)
        self.live_url = f"/beheer/kennisbank/artikel/{self.a.pk}/live-wijzigingen/"

    def verbeter_live(self, inhoud=None, wie=None, **extra):
        self.client.force_login(wie or self.bram)
        self.a.refresh_from_db()
        data = beheerdata(
            self.a, inhoud=inhoud or self.LIVE, wijzigingstoelichting="Nummer verbeterd", clusters=[self.water.pk]
        )
        data.update(extra)
        r = self.post(self.url + "?live=1", data, _save="1")
        self.assertEqual(r.status_code, 302, r.content[:800])
        self.a.refresh_from_db()
        return r

    def gegevens(self, html):
        start = html.index('<script id="kb-live-gegevens" type="application/json">') + 54
        return json.loads(html[start : html.index("</script>", start)])

    def vraag(self, wie=None, **data):
        self.client.force_login(wie or self.anna)
        c = Conceptversie.objects.get(artikel=self.a)
        basis = {"titel": c.velden["titel"], "samenvatting": c.velden["samenvatting"], "inhoud": c.velden["inhoud"]}
        basis.update(data)
        return self.client.post(self.live_url, basis)

    def sla_concept_op(self, wie=None, besluiten=None, **velden_):
        self.client.force_login(wie or self.anna)
        c = Conceptversie.objects.get(artikel=self.a)
        data = beheerdata(self.a, inhoud=velden_.pop("inhoud", c.velden["inhoud"]), wijzigingstoelichting="")
        data["geladen_concept"] = c.stempel
        if besluiten is not None:
            data["kb_live_besluiten"] = json.dumps(besluiten)
        data.update(velden_)
        return self.post(self.url, data, _conceptversie="1")


class InHetConcept(LiveBasis):
    def test_zonder_live_wijziging_geen_melding_en_geen_paneel(self):
        html = self.client.get(self.url).content.decode()
        self.assertNotIn("kb-live-gegevens", html)
        self.assertNotIn('id="kb-p-live"', html)
        self.assertNotIn("de live versie is bijgewerkt", html)
        self.assertNotIn('name="kb_live_besluiten"', html)

    def test_melding_paneel_en_knop_na_een_verbetering_van_de_live_versie(self):
        self.verbeter_live()
        html = self.als(self.anna).get(self.url).content.decode()
        self.assertIn("Let op: de live versie is bijgewerkt.", html)
        self.assertIn("Dit concept komt niet meer overeen met de publicatie. Er zijn 2 wijzigingen.", html)
        self.assertIn("Loop de wijzigingen langs (2)", html)
        self.assertIn("Live wijzigingen (2)", balk_van(html))
        self.assertIn('id="kb-p-live"', html)
        self.assertIn("Van versie 2 naar versie 3, door Bram", html)
        self.assertIn(
            f'<a href="{self.a.get_absolute_url()}" target="_blank" rel="noopener">Bekijk de live versie</a>', html
        )
        self.assertNotIn("poedcorrectie", html)
        g = self.gegevens(html)
        self.assertEqual(
            [(w["soort"], w["sectie"], w["stand"]) for w in g["wijzigingen"]],
            [("zelf", "Wanneer", "open"), ("veilig", "Bij spoed", "open")],
        )
        self.assertEqual(g["telling"], {"totaal": 2, "open": 2, "niet": 0, "vervalt": 2})
        self.assertFalse(g["op_slot"])
        # Het formulier opent nog steeds het concept, niet de live tekst.
        self.assertIn("tenzij de zaak spoed heeft", html)

    def test_de_publicatie_zegt_dat_het_concept_het_laat_zien(self):
        r = self.verbeter_live()
        self.assertIn("Er ligt een concept van dit artikel", " | ".join(str(m) for m in get_messages(r.wsgi_request)))
        self.assertEqual(
            Conceptversie.objects.get(artikel=self.a).velden["inhoud"], self.CONCEPT, "het concept is niet geraakt"
        )
        self.assertIn("Verbetering van de live versie", ArtikelVersie.objects.get(artikel=self.a, versie=3).review)

    def test_overnemen_geeft_de_nieuwe_tekst_en_slaat_niets_op(self):
        self.verbeter_live()
        g = self.gegevens(self.als(self.anna).get(self.url).content.decode())
        veilig = next(w for w in g["wijzigingen"] if w["soort"] == "veilig")
        voor = Conceptversie.objects.get(artikel=self.a)
        r = self.vraag(overnemen=veilig["id"])
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertEqual(j["gedaan"], [veilig["id"]])
        self.assertIn("01 42", j["velden"]["inhoud"])
        self.assertIn("tenzij de zaak spoed heeft", j["velden"]["inhoud"])
        self.assertEqual([w["stand"] for w in j["wijzigingen"]], ["open", "overgenomen"])
        na = Conceptversie.objects.get(artikel=self.a)
        self.assertEqual((na.velden, na.stempel, na.live_besluiten), (voor.velden, voor.stempel, {}))
        # Pas na Opslaan als concept staat het erin; de melding telt dan nog één wijziging.
        self.sla_concept_op(inhoud=j["velden"]["inhoud"])
        html = self.client.get(self.url).content.decode()
        self.assertIn("Live wijzigingen (1)", balk_van(html))
        self.assertIn("waarvan nog 1 te doen", html)

    def test_alles_veilig_rekent_met_wat_er_nu_in_de_editor_staat(self):
        self.verbeter_live()
        # De redacteur heeft de alinea van het nummer net zelf veranderd, nog niet opgeslagen.
        nu = self.CONCEPT.replace("noteer het gesprek", "noteer het gesprek in de zaak")
        j = self.vraag(inhoud=nu, overnemen="veilig").json()
        self.assertEqual(j["gedaan"], [])
        self.assertNotIn("velden", j)
        self.assertEqual([w["soort"] for w in j["wijzigingen"]], ["zelf", "zelf"])

    def test_besluiten_worden_per_concept_bewaard_met_naam(self):
        self.verbeter_live()
        g = self.gegevens(self.als(self.anna).get(self.url).content.decode())
        zelf, veilig = [w["id"] for w in g["wijzigingen"]]
        self.sla_concept_op(besluiten={zelf: "aangepast", veilig: "niet"})
        c = Conceptversie.objects.get(artikel=self.a)
        self.assertEqual(
            {k: (b["besluit"], b["door"]) for k, b in c.live_besluiten.items()},
            {zelf: ("aangepast", "Anna"), veilig: ("niet", "Anna")},
        )
        # Bram opent hetzelfde concept en ziet wat Anna besloot.
        html = self.als(self.bram).get(self.url).content.decode()
        g = self.gegevens(html)
        self.assertEqual([(w["stand"], w["door"]) for w in g["wijzigingen"]], [("aangepast", "Anna"), ("niet", "Anna")])
        self.assertEqual(g["telling"], {"totaal": 2, "open": 0, "niet": 1, "vervalt": 1})
        self.assertIn("Live wijzigingen ✓", balk_van(html))
        self.assertIn("De wijzigingen van de live versie zijn verwerkt.", html)
        self.assertIn("1 bewust niet overgenomen", html)
        self.assertIn(f"&quot;{veilig}&quot;: &quot;niet&quot;", html, "het verborgen veld draagt de besluiten mee")
        # Bram draait er één terug; het andere blijft van Anna.
        self.sla_concept_op(wie=self.bram, besluiten={zelf: "aangepast"})
        c.refresh_from_db()
        self.assertEqual({k: b["door"] for k, b in c.live_besluiten.items()}, {zelf: "Anna"})

    def test_besluiten_opslaan_zonder_tekstwijziging_laat_de_stempel_en_het_akkoord_staan(self):
        self.verbeter_live()
        g = self.gegevens(self.als(self.anna).get(self.url).content.decode())
        voor = Conceptversie.objects.get(artikel=self.a).stempel
        self.sla_concept_op(besluiten={g["wijzigingen"][0]["id"]: "niet"})
        c = Conceptversie.objects.get(artikel=self.a)
        self.assertEqual(c.stempel, voor)
        self.assertEqual(len(c.live_besluiten), 1)

    def test_opslaan_zonder_het_veld_laat_de_besluiten_staan(self):
        self.verbeter_live()
        g = self.gegevens(self.als(self.anna).get(self.url).content.decode())
        self.sla_concept_op(besluiten={g["wijzigingen"][0]["id"]: "niet"})
        self.sla_concept_op(inhoud=self.CONCEPT + P("Meer."))
        self.assertEqual(len(Conceptversie.objects.get(artikel=self.a).live_besluiten), 1)

    def test_na_een_mislukte_opslag_blijven_de_keuzes_in_het_scherm(self):
        self.verbeter_live()
        g = self.gegevens(self.als(self.anna).get(self.url).content.decode())
        wid = g["wijzigingen"][0]["id"]
        # Publiceren zonder toelichting mislukt: het formulier komt terug.
        c = Conceptversie.objects.get(artikel=self.a)
        self.a.refresh_from_db()
        data = beheerdata(self.a, inhoud=c.velden["inhoud"], wijzigingstoelichting="", clusters=[self.water.pk])
        data.update(geladen_concept=c.stempel, kb_live_besluiten=json.dumps({wid: "niet"}))
        r = self.post(self.url, data, _save="1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.gegevens(r.content.decode())["besluiten"], {wid: "niet"})
        self.assertEqual(Conceptversie.objects.get(artikel=self.a).live_besluiten, {}, "nog niets opgeslagen")

    def test_alles_verwerkt_en_niets_geweigerd_dan_verdwijnt_de_melding(self):
        self.verbeter_live()
        g = self.gegevens(self.als(self.anna).get(self.url).content.decode())
        j = self.vraag(overnemen="veilig").json()
        self.sla_concept_op(inhoud=j["velden"]["inhoud"], besluiten={g["wijzigingen"][0]["id"]: "aangepast"})
        html = self.client.get(self.url).content.decode()
        self.assertRegex(html, r'id="kb-live-melding"[^>]* hidden')
        self.assertIn("Live wijzigingen ✓", balk_van(html))

    def test_op_slot_is_het_paneel_alleen_lezen(self):
        self.ter_inzage()
        self.verbeter_live()
        html = self.als(self.anna).get(self.url).content.decode()
        g = self.gegevens(html)
        self.assertTrue(g["op_slot"])
        self.assertIn("overnemen kan na terugroepen", html)
        veilig = next(w for w in g["wijzigingen"] if w["soort"] == "veilig")
        r = self.vraag(overnemen=veilig["id"])
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.vraag().status_code, 200, "bekijken mag wel")
        self.assertTrue(review.op_slot(self.a.pk))

    def test_het_endpoint_is_alleen_voor_wie_het_artikel_mag_redigeren(self):
        self.verbeter_live()
        self.assertEqual(self.vraag(wie=self.lies).status_code, 302)  # geen beheer: naar inloggen
        self.assertEqual(self.vraag(wie=self.zoe).status_code, 403, "redacteur van een andere omgeving")
        self.client.force_login(self.anna)
        self.assertEqual(self.client.get(self.live_url).status_code, 405)
        Conceptversie.objects.filter(artikel=self.a).delete()
        self.assertEqual(self.client.post(self.live_url, {"inhoud": ""}).status_code, 409)

    def test_wat_de_editor_stuurt_wordt_geschoond(self):
        self.verbeter_live()
        j = self.vraag(
            inhoud=self.CONCEPT + '<p onclick="x()">Extra<script>alert(1)</script></p>', overnemen="veilig"
        ).json()
        self.assertNotIn("<script", j["velden"]["inhoud"])
        self.assertNotIn("onclick", j["velden"]["inhoud"])

    def test_eigenschappen_die_live_zijn_gewijzigd_worden_genoemd(self):
        self.verbeter_live(inhoud=BASIS, tags_tekst="rappel, nieuw")
        html = self.als(self.anna).get(self.url).content.decode()
        self.assertIn("Ook live gewijzigd: tags.", html)
        self.assertNotIn("Loop de wijzigingen langs", html)

    def test_basisversie_onvindbaar_dan_de_algemene_waarschuwing(self):
        self.verbeter_live()
        ArtikelVersie.objects.filter(artikel=self.a, versie=2).delete()
        html = self.als(self.anna).get(self.url).content.decode()
        self.assertNotIn("kb-live-gegevens", html)
        self.assertIn("Let op: de live versie is bijgewerkt.", html)
        self.assertIn("Neem de wijziging zelf mee in het concept", html)

    def test_publiceren_van_het_concept_ruimt_alles_op(self):
        self.verbeter_live()
        c = Conceptversie.objects.get(artikel=self.a)
        self.client.force_login(self.anna)
        self.a.refresh_from_db()
        data = beheerdata(
            self.a, inhoud=c.velden["inhoud"], wijzigingstoelichting="Nieuwe versie", clusters=[self.water.pk]
        )
        data["geladen_concept"] = c.stempel
        self.assertEqual(self.post(self.url, data, _save="1").status_code, 302)
        self.assertFalse(Conceptversie.objects.filter(artikel=self.a).exists())
        self.assertNotIn("kb-live", self.client.get(self.url).content.decode())


# --- L1: de ingang ligt buiten het concept ----------------------------------------------------------------------


class Ingang(LiveBasis):
    def test_live_en_de_oude_naam_spoed_openen_hetzelfde_scherm(self):
        for vraag in ("?live=1", "?spoed=1"):
            html = self.client.get(self.url + vraag).content.decode()
            balk = balk_van(html)
            self.assertIn('<span class="kb-pil kb-pil-spoed">Live versie</span>', balk, vraag)
            self.assertIn(f'<a class="kb-bk kb-naar-concept" href="{self.url}">Naar het concept</a>', balk)
            self.assertIn("Je verbetert de live versie", html)
            self.assertIn("volgt 2 weken later.&lt;/p&gt;", html, "de live tekst, niet het concept")
            self.assertNotIn("tenzij de zaak spoed heeft", html)
            self.assertNotIn("poedcorrectie", html)
            self.assertNotIn('id="kb-p-live"', html)

    def test_de_api_meldt_het_concept_alleen_aan_redacteuren(self):
        pad = f"/api/v1/artikelen/{self.a.pk}"
        c = self.als(self.anna).get(pad).json()["bewerk_concept"]
        self.assertEqual((c["door"], c["concept_url"], c["live_url"]), ("Anna", self.url, self.url + "?live=1"))
        self.assertTrue(c["sinds"].startswith(str(Conceptversie.objects.get(artikel=self.a).gestart_op.year)))
        lezer = self.als(self.lies).get(pad).json()
        self.assertEqual((lezer["bewerk_concept"], lezer["bewerk_url"]), (None, None))
        Conceptversie.objects.filter(artikel=self.a).delete()
        self.assertIsNone(self.als(self.anna).get(pad).json()["bewerk_concept"])

    def test_de_site_vraagt_het_bij_bewerken(self):
        js = (Path(settings.BASE_DIR) / "kennisbank/static/kennisbank/app.js").read_text(encoding="utf-8")
        self.assertIn("a.bewerk_url && a.bewerk_concept", js)
        for tekst in (
            "Dit artikel heeft een concept",
            "De live versie verbeteren",
            "Verder met het concept",
            "c.live_url",
            "c.concept_url",
        ):
            self.assertIn(tekst, js)

    def test_vanuit_de_werkplek_ga_je_direct_naar_het_concept(self):
        html = self.als(self.anna).get("/beheer/?bak=concepten").content.decode()
        self.assertIn(f'href="{self.url}"', html)
        self.assertNotIn("live=1", html)


# --- L3 en L4: de vraag bij publiceren, en Meer is weg ----------------------------------------------------------


class Schermen(LiveBasis):
    def bron(self, naam):
        return (Path(settings.BASE_DIR) / "kennisbank/static/kennisbank" / naam).read_text(encoding="utf-8")

    def test_l3_de_vraag_staat_in_het_venster_en_het_vinkje_is_weg(self):
        js = self.bron("beheer-editor.js")
        self.assertIn('titel: "Moeten medewerkers dit weten?"', js)
        self.assertIn('"kb-weten-ja"', js)
        self.assertIn('"kb-weten-nee"', js)
        self.assertIn("klein.checked = nee.checked", js)
        self.assertNotIn("Kleine correctie", js)

    def test_l3_het_woord_kleine_correctie_staat_niet_meer_in_de_schermen(self):
        html = self.als(self.anna).get(self.url).content.decode()
        self.assertNotIn("leine correctie", html)
        self.assertIn("Medewerkers hoeven dit niet te weten", html)
        self.assertIn("Zonder melding", html)
        for naam in ("beheer-editor.js", "voorstellen-lade.js", "artikel-scherm.js", "live-wijzigingen.js", "app.js"):
            self.assertNotIn("leine correctie", self.bron(naam), naam)
            self.assertNotIn("poedcorrectie", self.bron(naam), naam)

    def test_l3_nee_publiceert_stil_en_ja_vraagt_een_toelichting(self):
        Conceptversie.objects.filter(artikel=self.a).delete()
        self.client.force_login(self.anna)
        self.a.refresh_from_db()
        data = beheerdata(
            self.a, inhoud=BASIS.replace("01 00", "01 42"), wijzigingstoelichting="", clusters=[self.water.pk]
        )
        r = self.post(self.url, data, _save="1")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Kies dan bij publiceren &#x27;Nee&#x27;", r.content.decode())
        r = self.post(self.url, {**data, "kleine_correctie": "on"}, _save="1")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(ArtikelVersie.objects.get(artikel=self.a, versie=3).kleine_correctie)
        self.assertIn("zonder melding aan medewerkers", " | ".join(str(m) for m in get_messages(r.wsgi_request)))

    def test_l4_weggooien_zit_in_afronden(self):
        html = self.als(self.anna).get(self.url).content.decode()
        self.assertNotIn("kb-meer", html)
        afronden = json.loads(
            html[html.index('<script id="kb-afronden" type="application/json">') + 49 :].split("</script>")[0]
        )
        self.assertTrue(afronden["weggooien"])
        self.assertIn('name="_weggooien"', html)
        self.assertIn('data-kb-vraag-titel="Conceptversie weggooien?"', html)
        js = self.bron("beheer-editor.js")
        self.assertIn('tekst: "Conceptversie weggooien"', js)
        self.assertIn("if (cfg.weggooien)", js)
        self.assertNotIn("kb-meer", self.bron("artikel-scherm.js") + self.bron("artikel-scherm.css"))

    def test_l4_op_slot_en_bij_de_live_versie_geen_weggooien(self):
        self.ter_inzage()
        html = self.als(self.anna).get(self.url).content.decode()
        self.assertNotIn('name="_weggooien"', html)
        self.assertIn('"weggooien": false', html)
        self.assertIn("De live versie verbeteren", html, "op slot: de weg via de site staat erbij")
        live = self.client.get(self.url + "?live=1").content.decode()
        self.assertNotIn('name="_weggooien"', live)
        self.assertIn('"weggooien": false', live)

    def test_afronden_waarschuwt_voor_wat_vervalt(self):
        js = self.bron("beheer-editor.js")
        self.assertIn("window.kbLive.telling()", js)
        self.assertIn("Eerst de wijzigingen langslopen", js)
        self.assertIn("die live", js)

    def test_het_paneel_voegt_alleen_ge_escapede_tekst_in(self):
        js = self.bron("live-wijzigingen.js")
        self.assertEqual(js.count("innerHTML"), 2, "alleen w.live, dat de server escapet")
        self.assertNotIn("eval(", js)

    def test_migratie_en_veld(self):
        self.assertEqual(Conceptversie._meta.get_field("live_besluiten").default, dict)
        self.assertEqual(livewijzigingen.BESLUITEN, {"niet", "aangepast", "gezien"})
