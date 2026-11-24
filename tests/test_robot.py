"""Tests du robot (aucun appel réseau ni IA) : python -m unittest discover -s tests"""
import datetime
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
TMP = tempfile.mkdtemp()
os.environ.update(ROBOT_DOCS=os.path.join(TMP, "docs"), ROBOT_SORTIE=os.path.join(TMP, "sortie"), ROBOT_CACHE=os.path.join(TMP, "cache"))
shutil.copytree(os.path.join(RACINE, "docs"), os.environ["ROBOT_DOCS"])

from robot import buzz, commande, ecrire, publication_auto, voix  # noqa: E402
from robot.commun import PARIS, lire, reglages  # noqa: E402


class TestCalage(unittest.TestCase):
    def test_nombre_en_chiffres(self):
        aff = voix.mots_affiches("378 jours, sans sortir.")
        ent = [("Trois", 0.0, 0.2), ("cent", 0.2, 0.4), ("soixante-dix-huit", 0.4, 1.0), ("jours,", 1.0, 1.3),
               ("sans", 1.4, 1.6), ("sortir.", 1.6, 2.0)]
        t = voix.caler(aff, ent, 2.0)
        self.assertAlmostEqual(t[0][0], 0.0); self.assertAlmostEqual(t[0][1], 1.0)
        self.assertAlmostEqual(t[1][0], 1.0); self.assertAlmostEqual(t[3][1], 2.0)

    def test_ponctuation_collee(self):
        self.assertEqual(voix.mots_affiches("Et James : quatre ?"), ["Et", "James :", "quatre ?"])

    def test_mot_absent(self):
        t = voix.caler(["un", "deux", "trois"], [("un", 0, 0.3), ("trois", 0.6, 0.9)], 1.0)
        self.assertTrue(t[0][1] <= t[1][0] <= t[2][0])


class TestBuzz(unittest.TestCase):
    B = {"vues_min": 500000, "jaime_min": 10000, "commentaires_min": 1000, "heures": 72}

    def video(self, **k):
        v = dict(id="1", compte="a", url="", vues=600000, jaime=20000, commentaires=2000, partages=0, date=time.time() - 3600, texte="")
        v.update(k); return v

    def test_seuils(self):
        ok = buzz.virales([self.video(), self.video(vues=400000), self.video(commentaires=50),
                           self.video(date=time.time() - 100 * 3600)], self.B)
        self.assertEqual(len(ok), 1)

    def test_score_plusieurs_comptes(self):
        un = {"videos": [self.video()], "insolite": 5}
        deux = {"videos": [self.video(), self.video(compte="b")], "insolite": 5}
        self.assertGreater(buzz.score(deux), 2 * buzz.score(un))

    def test_identifiant_stable(self):
        self.assertEqual(buzz.identifiant("Tempête : rafales record !"), buzz.identifiant("rafales record tempête"))

    def test_statut_garde(self):
        anciens = [{"id": "x", "statut": "utilise", "score": 1, "derniere_vue": time.time()}]
        nouveaux = [{"id": "x", "score": 5, "titre": "t"}]
        self.assertEqual(buzz.fusionner(anciens, nouveaux)[0]["statut"], "utilise")


class TestTextes(unittest.TestCase):
    def test_hashtags(self):
        R = reglages()
        h = ecrire.hashtags({"hashtags": ["NASA", "mars planète"]}, {"hashtags_viraux": ["fyp", "espace"], "hashtags": []}, R)
        self.assertEqual(h[:3], ["#nasa", "#marsplanète", "#espace"])
        self.assertIn("#insolite", h)
        self.assertLessEqual(len(h), R["hashtags"]["nombre"])

    def test_json_entoure(self):
        from robot import ia
        self.assertEqual(ia.lire_json('Voici : ```json\n{"a": {"b": 1}}\n``` voilà'), {"a": {"b": 1}})


class TestPublication(unittest.TestCase):
    def test_creneaux(self):
        now = datetime.datetime(2026, 11, 24, 13, 0, tzinfo=PARIS)
        self.assertEqual(publication_auto.creneaux_dus(["12:30", "19:00"], [], now), ["12:30"])
        self.assertEqual(publication_auto.creneaux_dus(["12:30"], ["12:30"], now), [])
        self.assertEqual(publication_auto.creneaux_dus(["08:00"], [], now), [])      # plus de 3 h : trop tard

    def test_ordre_de_coche(self):
        f = {"videos": [{"id": "a", "statut": "a_publier", "coche_le": "2026-11-24T10:00"},
                        {"id": "b", "statut": "a_publier", "coche_le": "2026-11-24T09:00"},
                        {"id": "c", "statut": "a_publier", "coche_le": "2026-11-24T08:00", "essai": True}]}
        self.assertEqual(publication_auto.prochaine(f)["id"], "b")

    def test_reglages_bornes(self):
        commande.appliquer_reglages({"buzz": {"vues_min": -5, "comptes": "@brut, hugodecrypte"}, "video": {"vitesse": 5},
                                     "publication": {"heures": ["12:30", "nimp"], "mode": "auto"}})
        R = reglages()
        self.assertEqual(R["buzz"]["vues_min"], 0); self.assertEqual(R["buzz"]["comptes"], ["brut", "hugodecrypte"])
        self.assertEqual(R["video"]["vitesse"], 1.1); self.assertEqual(R["publication"]["heures"], ["12:30"])


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg absent")
class TestVideoComplete(unittest.TestCase):
    def test_essai_sans_reseau(self):
        env = dict(os.environ, SIMULATION="1")
        r = subprocess.run([sys.executable, "-m", "robot.principal", "--libre", "Essai"], cwd=RACINE, env=env,
                           capture_output=True, text=True, timeout=900)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
        v = lire("file.json")["videos"][0]
        self.assertTrue(v["essai"]); self.assertGreater(v["duree"], 15)
        mp4 = glob.glob(os.path.join(TMP, "sortie", v["id"], "*.mp4"))
        self.assertTrue(mp4)
        dims = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height",
                                        "-of", "csv=p=0", mp4[0]], text=True).strip()
        self.assertEqual(dims, "1080,1920")


class TestFichiers(unittest.TestCase):
    def test_workflows_lisibles(self):
        import yaml
        for f in glob.glob(os.path.join(RACINE, ".github", "workflows", "*.yml")):
            d = yaml.safe_load(open(f, encoding="utf-8"))
            self.assertIn("jobs", d, f); self.assertTrue(d.get("name"), f)

    def test_donnees_valides(self):
        for f in glob.glob(os.path.join(RACINE, "docs", "donnees", "*.json")):
            json.load(open(f, encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
