"""1.17.0 stap A: werkbakken per cluster en een algemene bak (ontwerp 11 november, Alex)."""

from django.contrib.admin.models import LogEntry

from kennisbank import diensten
from kennisbank.models import Artikel, Cluster, Status, Verbetervoorstel
from kennisbank.tests.test_bakken import Basis


class ClusterbakkenTests(Basis):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.water = Cluster.objects.create(naam="Water")
        cls.weg = Cluster.objects.create(naam="Weg")
        cls.lucht = Cluster.objects.create(naam="Lucht")  # alleen in Zuid
        cls.art_water = cls._artikel("Waterbodem", [cls.water])
        cls.art_twee = cls._artikel("Brug over water", [cls.water, cls.weg])
        cls.art_zuid = cls._artikel("Zuidelijk lucht", [cls.lucht], omgeving=cls.zuid)

    @classmethod
    def _artikel(cls, titel, clusters, omgeving=None):
        a = Artikel.objects.create(
            omgeving=omgeving or cls.noord,
            titel=titel,
            samenvatting="x",
            inhoud="<p>x</p>",
            status=Status.GEPUBLICEERD,
            versie=1,
        )
        a.clusters.set(clusters)
        return a

    def test_binnenkomst_volgens_de_regel(self):
        self.assertEqual(self.voorstel(artikel=self.art_water).cluster, self.water, "één cluster: die clusterbak")
        self.assertIsNone(self.voorstel(artikel=self.art_twee).cluster, "twee clusters: de algemene bak")
        self.assertIsNone(self.voorstel(artikel=self.artikel).cluster, "geen cluster: de algemene bak")

    def test_binnenkomst_via_de_api(self):
        r = self.als(self.lies).post(
            "/api/v1/voorstellen", {"artikel": self.art_water.pk, "tekst": "x"}, content_type="application/json"
        )
        self.assertEqual(Verbetervoorstel.objects.get(pk=r.json()["id"]).cluster, self.water)

    def test_werkplek_toont_algemeen_en_de_clusters_van_mijn_omgeving(self):
        self.voorstel(artikel=self.art_water)
        self.voorstel(artikel=self.art_water)
        self.voorstel(artikel=self.art_twee)
        m = self.als(self.anna).get("/beheer/").context["werkplek"]["menu"]
        bakken = [(b["naam"], b["aantal"]) for b in m["bakken"]]
        self.assertEqual(bakken, [("Algemeen", 1), ("Water", 2), ("Weg", 0)])
        r = self.client.get(f"/beheer/?bak=cluster-{self.water.pk}")
        self.assertEqual(len(r.context["werkplek"]["inhoud"]["rijen"]), 2)

    def test_cluster_van_een_andere_omgeving_is_onzichtbaar(self):
        self.voorstel(artikel=self.art_zuid, door=self.zoe)
        m = self.als(self.anna).get("/beheer/").context["werkplek"]["menu"]
        self.assertNotIn("Lucht", [b["naam"] for b in m["bakken"]])
        self.assertEqual(self.client.get(f"/beheer/?bak=cluster-{self.lucht.pk}").status_code, 404)

    def test_verplaatsen_tussen_bakken(self):
        v = self.voorstel(artikel=self.art_water)
        c = self.als(self.anna)
        self.assertEqual(v.cluster, self.water)
        # Zonder keuze gebeurt er niets (eerder verhuisde hij stilletjes naar Algemeen).
        for leeg in ({}, {"cluster": ""}):
            r = c.post("/beheer/werkplek/actie/", {"voorstel": v.pk, "actie": "naar_bak", **leeg}, follow=True)
            v.refresh_from_db()
            self.assertEqual(v.cluster, self.water)
            self.assertContains(r, "Kies eerst een bak")
        r = c.post(
            "/beheer/werkplek/actie/", {"voorstel": v.pk, "actie": "naar_bak", "cluster": "algemeen"}, follow=True
        )
        v.refresh_from_db()
        self.assertIsNone(v.cluster)
        self.assertContains(r, "ligt nu in de bak Algemeen")
        c.post("/beheer/werkplek/actie/", {"voorstel": v.pk, "actie": "naar_bak", "cluster": self.weg.pk})
        v.refresh_from_db()
        self.assertEqual(v.cluster, self.weg)
        log = LogEntry.objects.filter(object_id=str(v.pk)).latest("action_time")
        self.assertIn("Verplaatst naar de bak Weg", log.get_change_message())
        # Een cluster van een andere omgeving kan niet.
        r = c.post("/beheer/werkplek/actie/", {"voorstel": v.pk, "actie": "naar_bak", "cluster": self.lucht.pk})
        self.assertEqual(r.status_code, 404)

    def test_terugleggen_komt_in_de_eigen_clusterbak(self):
        v = diensten.voorstel_naar_bak(self.voorstel(artikel=self.art_water), self.anna, self.anna)
        diensten.voorstel_naar_bak(v, self.anna, None)
        v.refresh_from_db()
        self.assertEqual((v.eigenaar, v.cluster), (None, self.water))

    def test_aantal_databasevragen_met_clusters(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.voorstel(artikel=self.art_water)
        c = self.als(self.anna)

        def tel():
            c.get(f"/beheer/?bak=cluster-{self.water.pk}")
            with CaptureQueriesContext(connection) as q:
                c.get(f"/beheer/?bak=cluster-{self.water.pk}")
            return len(q)

        weinig = tel()
        for i in range(8):
            a = self._artikel(f"Extra {i}", [Cluster.objects.create(naam=f"C{i}")])
            self.voorstel(artikel=a)
            self.voorstel(artikel=self.art_water, tekst=f"w{i}")
        self.assertEqual(tel(), weinig)
