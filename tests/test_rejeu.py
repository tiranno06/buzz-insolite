"""Rejeu d'une VRAIE vidéo (point 2 demandé par l'auteur le 25/11) : la vidéo de la CAN du 25/11 (texte, articles, choix
des images : tests/donnees/rejeu_can) est remise en scène SANS réseau ni IA (réponses de l'IA simulées, vidéos et photos
remplacées par de petites images de test), avec les défauts réellement vus ce jour-là. Chaque modification du code doit
garder ces garanties :
- les règles trouvent chaque défaut (extraits perdus, écrans vides, « vous », date inventée, hashtags en lettres) ;
- la réparation ne touche QUE les passages fautifs, puis tout est revérifié sans nouveau problème ;
- refaire le texte ne perd aucun extrait ;
- un montage refait seulement les écrans changés.
Lancé par tests.yml à chaque envoi (quelques dizaines de secondes).
"""
import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest

ICI = os.path.join(os.path.dirname(__file__), "donnees", "rejeu_can")


def _video(chemin, secondes=14):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=s=180x320:d={secondes}:r=15",
                    "-pix_fmt", "yuv420p", chemin], check=True)


def _photo(chemin):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=s=320x200:d=1", "-frames:v", "1", chemin],
                   check=True)


def _silence(chemin, secondes=0.8):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(secondes), chemin],
                   check=True)


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg nécessaire")
class RejeuVideoCAN(unittest.TestCase):
    def setUp(self):
        from robot import ia
        self.d = tempfile.mkdtemp()
        self.script = json.load(open(os.path.join(ICI, "script.json"), encoding="utf-8"))
        self.articles = json.load(open(os.path.join(ICI, "articles.json"), encoding="utf-8"))
        faits = set()
        for p in self.script["phrases"]:
            m = p.get("media")
            if m:
                m["chemin"] = os.path.join(self.d, m["chemin"])
                if m["chemin"] not in faits:
                    (_video if m["type"] == "video" else _photo)(m["chemin"]); faits.add(m["chemin"])
        # tous les extraits trouvés ce jour-là : les 2 d'Al Jazeera montrés + 4 qui avaient été PERDUS (BBC, franceinfo…)
        self.extraits = []
        for k, compte in enumerate(["aljazeeraenglish", "aljazeeraenglish", "bbcnews", "franceinfo", "brutofficiel", "tf1info"]):
            ident = ["citation-7711946839339191583-0", "citation-7711946839339191583-2"][k] if k < 2 else f"citation-perdu{k}-0"
            chemin = os.path.join(self.d, ident + ".mp4")
            if not os.path.exists(chemin):
                _video(chemin)
            self.extraits.append(dict(type="video", chemin=chemin, id=ident, citation=True, compte=compte, duree=12, debut=0))
        self.script["_citations_toutes"] = copy.deepcopy(self.extraits)
        self.ia_avant = ia.demander_json

        def fausse_ia(consigne, texte, **k):            # réponses de l'IA simulées (aucun appel réseau)
            if "TUTOYANT" in consigne:
                return {"ecrit": "Imagine un titre de champion volé, puis rendu."}, "faux:ia"
            if "date" in consigne.lower():
                return {"ecrit": ""}, "faux:ia"           # l'IA ne sait pas : la date douteuse est retirée
            return {}, "faux:ia"
        ia.demander_json = fausse_ia

    def tearDown(self):
        from robot import ia
        ia.demander_json = self.ia_avant
        shutil.rmtree(self.d, ignore_errors=True)

    def test_regles_trouvent_et_reparent_seulement_les_passages_fautifs(self):
        from robot import regles
        ph = self.script["phrases"]
        ph[0]["ecrit"] = "Imaginez un titre de champion volé, puis rendu."        # défaut vu : « vous »
        ph[2]["ecran"] = "1\u20110"                                              # défaut vu (r11) : « 1☒0 »
        avant = copy.deepcopy(ph)
        pbs = regles.verifier(self.script, self.articles, ["#c", "#a", "#n", "#2"], 73, "desc", "Et toi ?")
        trouves = {p["regle"] for p in pbs}
        for r in ("extraits_perdus", "ecran_vide", "tutoiement", "date", "hashtags", "caracteres"):
            self.assertIn(r, trouves, f"la règle « {r} » n'a pas vu le défaut réel de la vidéo CAN")
        textes, images_, _ = regles.reparer(self.script, pbs, self.articles, {}, journal=lambda *_: None)
        # la date inventée « 18 janvier 2025 » (les articles disent « 18 janvier ») : l'année est retirée
        self.assertIn("18 janvier", ph[1]["ecrit"]); self.assertNotIn("2025", ph[1]["ecrit"])
        self.assertTrue(ph[0]["ecrit"].startswith("Imagine "))
        self.assertEqual(ph[2]["ecran"], "1-0")
        # seuls les passages fautifs ont changé
        for i, (a, b) in enumerate(zip(avant, ph)):
            if i not in textes:
                self.assertEqual(a["ecrit"], b["ecrit"], f"écran {i + 1} changé sans raison")
            if i not in images_ and (a.get("media") or {}).get("citation"):
                self.assertEqual(a["media"], b["media"], f"extrait de l'écran {i + 1} remplacé sans raison")
        reste = {p["regle"] for p in regles.verifier(self.script, self.articles, ["#can2025", "#senegal", "#insolite"], 73,
                                                      "desc", "Et toi ?")}
        self.assertNotIn("extraits_perdus", reste)
        self.assertNotIn("tutoiement", reste)
        self.assertNotIn("caracteres", reste)
        self.assertNotIn("doublon", reste, "une réparation a créé un doublon")

    def test_refaire_le_texte_ne_perd_aucun_extrait(self):
        from robot import controle, principal, refaire, citations
        ancien = self.script["phrases"]
        reserve = refaire.reserve_extraits(ancien)
        # le texte est refait : presque toutes les phrases changent et perdent leur image (ce qui s'est passé sur r10)
        nouveau = {"phrases": [dict(ecrit=p["ecrit"] + " (réécrite)", voix=p["voix"], uid=100 + i) for i, p in enumerate(ancien)],
                   "_citations_reserve": reserve, "_citations_toutes": self.script["_citations_toutes"]}
        scenes = principal.scenes_de(nouveau["phrases"])
        extraits_avant, sim_avant = citations.extraits, principal.simulation
        citations.extraits = lambda *a, **k: []           # plus aucune vidéo d'origine téléchargeable (pire cas)
        principal.simulation = lambda: False
        citations_photos = citations.photos_presse
        citations.photos_presse = lambda *a, **k: []
        try:
            principal.placer_citations(nouveau, scenes, {"titre": "CAN", "videos": []}, self.d, set(), lambda *_: None,
                                       {"video": {"citations": True}}, {"articles": []}, "buzz")
        finally:
            citations.extraits, principal.simulation, citations.photos_presse = extraits_avant, sim_avant, citations_photos
        controle.reposer_extraits(nouveau, journal=lambda *_: None)
        self.assertEqual(controle.extraits_perdus(nouveau), [], "des extraits ont été perdus en refaisant le texte")
        sans_extrait = [i + 1 for i, p in enumerate(nouveau["phrases"][:-1]) if not (p.get("media") or {}).get("citation")]
        self.assertEqual(sans_extrait, [], f"écrans sans extrait alors que des extraits existent : {sans_extrait}")
        montres = {controle._base(p.get("media")) for p in nouveau["phrases"] if (p.get("media") or {}).get("citation")}
        for ident in ("citation-perdu2-0", "citation-perdu3-0", "citation-perdu4-0"):   # BBC, franceinfo, Brut : retrouvés
            self.assertIn(ident, montres)

    def test_montage_ne_refait_que_les_ecrans_changes(self):
        from robot import montage
        ph = self.script["phrases"]
        for k, p in enumerate(ph):
            p["son"] = os.path.join(self.d, f"voix{k}.wav"); _silence(p["son"])
            p["duree"], p["mots"] = 0.8, []
        self.script.update(musique=False, bruitages=False, transitions=False)
        sortie = os.path.join(self.d, "v.mp4")
        montage.monter(self.script, self.d, sortie)
        self.assertEqual(self.script["_ecrans_refaits"], len(ph))
        ph[4]["media"] = dict(self.extraits[3])           # un seul écran change (extrait perdu remis)
        montage.monter(self.script, self.d, sortie)
        self.assertEqual(self.script["_ecrans_refaits"], 1, "le montage a refait des écrans qui n'avaient pas changé")
        self.assertTrue(os.path.getsize(sortie) > 0)


if __name__ == "__main__":
    unittest.main()
