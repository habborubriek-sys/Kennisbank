"""1.37.1 (melding Alex): de demoserver stond op internet met het wachtwoord "demo", ook voor de beheerder.

`KB_DEMO_WACHTWOORD` geeft de demo-accounts een eigen wachtwoord, ook de accounts die er al waren, zodat een
draaiende demo met één instelling en een herstart dicht is. De statuspagina waarschuwt zolang het
standaardwachtwoord er nog op zit.
"""

from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings

from kennisbank import status

NAMEN = ["medewerker", "redacteur", "reviewer", "beheerder"]


def demo(**opties):
    call_command("kennisbank_demo", stdout=StringIO(), **opties)


def rij():
    return next(
        (
            r
            for g in status.overzicht()["groepen"]
            for r in g["rijen"]
            if r["naam"] == "Wachtwoord van de demo-accounts"
        ),
        None,
    )


@override_settings(KB_DEMO_MODUS=True, KB_DEMO_WACHTWOORD="")
class DemoWachtwoord(TestCase):
    def kan(self, naam, wachtwoord):
        return User.objects.get(username=naam).check_password(wachtwoord)

    def test_zonder_instelling_blijft_het_demo(self):
        demo()
        self.assertTrue(all(self.kan(n, "demo") for n in NAMEN))

    def test_de_instelling_geldt_voor_nieuwe_accounts(self):
        with override_settings(KB_DEMO_WACHTWOORD="Zeeschelp-47"):
            demo()
        self.assertTrue(all(self.kan(n, "Zeeschelp-47") for n in NAMEN))
        self.assertFalse(any(self.kan(n, "demo") for n in NAMEN))

    def test_de_instelling_zet_ook_bestaande_accounts_om(self):
        """Dit is het geval van de demoserver: de accounts bestonden al met "demo"."""
        demo()
        with override_settings(KB_DEMO_WACHTWOORD="Zeeschelp-47"):
            demo()
        self.assertTrue(all(self.kan(n, "Zeeschelp-47") for n in NAMEN))
        self.assertFalse(any(self.kan(n, "demo") for n in NAMEN))
        self.assertEqual(self.client.post("/inloggen/", {"username": "beheerder", "password": "demo"}).status_code, 200)

    def test_zonder_instelling_blijft_een_eigen_wachtwoord_met_rust(self):
        demo()
        u = User.objects.get(username="redacteur")
        u.set_password("eigen-keuze")
        u.save()
        demo()
        self.assertTrue(self.kan("redacteur", "eigen-keuze"))

    def test_het_wachtwoord_wordt_niet_bij_elke_start_opnieuw_gezet(self):
        """Anders zou elke herstart iedereen uitloggen."""
        with override_settings(KB_DEMO_WACHTWOORD="Zeeschelp-47"):
            demo()
            voor = User.objects.get(username="medewerker").password
            demo()
        self.assertEqual(User.objects.get(username="medewerker").password, voor)

    def test_de_optie_op_de_opdrachtregel_gaat_voor(self):
        with override_settings(KB_DEMO_WACHTWOORD="Zeeschelp-47"):
            demo(wachtwoord="Anders-12")
        self.assertTrue(self.kan("beheerder", "Anders-12"))

    def test_statuspagina_waarschuwt_bij_het_standaardwachtwoord(self):
        demo()
        with override_settings(DEBUG=False):
            r = rij()
            self.assertEqual((r["stand"], r["waarde"]), (status.FOUT, "het standaardwachtwoord"))
            self.assertIn("KB_DEMO_WACHTWOORD", r["advies"])
            self.assertEqual(status.overzicht()["totaal"], status.FOUT)
        with override_settings(DEBUG=True):
            self.assertEqual(rij()["stand"], status.LET_OP)  # op de eigen computer is het een aandachtspunt

    def test_statuspagina_zwijgt_met_een_eigen_wachtwoord_en_buiten_de_demo(self):
        with override_settings(KB_DEMO_WACHTWOORD="Zeeschelp-47"):
            demo()
        self.assertIsNone(rij())
        User.objects.filter(username="beheerder").delete()
        User.objects.create_superuser("beheerder", password="demo")
        with override_settings(KB_DEMO_MODUS=False):
            self.assertIsNone(rij())
