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

    def test_doublons_fusionnes(self):
        S = [{"id": "a", "titre": "Policier vole vélo à cycliste à Toulouse", "score": 79, "statut": "nouveau",
              "videos": [{"id": "1", "vues": 10, "jaime": 1, "commentaires": 1}]},
             {"id": "b", "titre": "Policier vole vélo cycliste Toulouse : vidéo choque", "score": 76, "statut": "utilise",
              "videos": [{"id": "2", "vues": 20, "jaime": 2, "commentaires": 2}]},
             {"id": "c", "titre": "Macron inaugure une ligne Airbus à Toulouse", "score": 50, "statut": "nouveau", "videos": []}]
        out = buzz.sans_doublons(S)
        self.assertEqual(len(out), 2); self.assertEqual(out[0]["vues"], 30)
        self.assertEqual(out[0]["statut"], "utilise")                  # déjà traité sous l'autre titre : pas refait

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


class TestNouveautes(unittest.TestCase):
    def test_bruitages(self):
        from robot import sons
        ph = [{"ecran": "TITRE"}, {"ecran": "378 JOURS", "media": None}, {"ecran": "", "media": {"type": "video"}},
              {"ecran": "3… 2… 1…"}, {"ecran": "", "reponse": "faux"}]
        b = sons.bruitages(ph, [0, 2, 4, 6, 8])
        noms = [x[0] for x in b]
        self.assertNotIn("woosh.wav", noms)                                    # coupé par défaut (choix de l'auteur)
        self.assertIn("woosh.wav", [x[0] for x in sons.bruitages(ph, [0, 2, 4, 6, 8], transitions=True)])
        self.assertEqual(noms.count("dun_dun.wav"), 1)
        self.assertIn("ding.wav", noms)

    def test_images_pertinentes(self):
        from robot import images
        self.assertTrue(images.pertinent("rapper microphone stage", "microphone, music, singer"))
        self.assertFalse(images.pertinent("rapper microphone stage", "thistle, flower, insect"))
        self.assertFalse(images.pertinent("angry face", "emoji, green screen, angry"))

    def test_musique_existe(self):
        from robot import sons
        for h in sons.HUMEURS:
            self.assertTrue(sons.musique(h), h)

    def test_carte_point_dans_pays(self):
        from robot import carte
        carre = [(0, 0), (10, 0), (10, 10), (0, 10)]
        self.assertTrue(carte._dedans(5, 5, carre)); self.assertFalse(carte._dedans(15, 5, carre))
        self.assertGreater(carte._merc(60), carte._merc(40))

    def test_carte_secours_ia(self):
        from robot import carte
        carte._photon = carte._nominatim = lambda lieu: (_ for _ in ()).throw(OSError("hors ligne"))
        r = carte.trouver_lieu("Lieu imaginaire de test", [48.6, -2.0])
        self.assertEqual((r["lat"], r["lon"], r["genre"]), (48.6, -2.0, "ia"))

    def test_stats(self):
        from robot import stats
        now = datetime.datetime(2026, 12, 10, 12, 0, tzinfo=PARIS)
        vids = []
        for i, (h, vues) in enumerate([(12, 1000), (12, 3000), (19, 9000), (19, 7000), (8, 500)]):
            vids.append({"id": str(i), "titre": f"v{i}", "statut": "publiee", "format": "vrai_faux" if vues > 5000 else "buzz",
                         "hashtags": ["#insolite"], "publiee_le": datetime.datetime(2026, 12, 1, h, 0, tzinfo=PARIS).isoformat(),
                         "stats": {"vues": vues, "jaime": 1, "commentaires": 1, "partages": 0}})
        S = stats.analyser(vids, now)
        self.assertEqual(S["meilleures_heures"], ["12:00", "19:00"])
        self.assertEqual(S["formats"][0]["nom"], "vrai_faux")
        tiktok = [{"id": "99", "date": datetime.datetime(2026, 12, 1, 19, 5, tzinfo=PARIS).timestamp(), "texte": "fausse base martienne #insolite"}]
        nos = [{"id": "a", "statut": "publiee", "publiee_le": datetime.datetime(2026, 12, 1, 19, 0, tzinfo=PARIS).isoformat(),
                "description": "Ils ont vécu dans une fausse base martienne", "hashtags": ["#insolite"]}]
        self.assertEqual(stats.rapprocher(nos, tiktok)["a"]["id"], "99")

    def test_format_auto(self):
        R = reglages()
        dimanche = datetime.datetime(2026, 11, 29, 16, 20, tzinfo=PARIS)
        self.assertEqual(publication_auto.format_auto(R, dimanche, "16:15"), "semaine")
        self.assertIn(publication_auto.format_auto(R, dimanche, "07:15"), ("buzz", "vrai_faux"))


class TestControleQualite(unittest.TestCase):
    def script(self, n=14, mots=16):
        ph = [dict(voix=" ".join(["mot"] * mots) + ".", ecrit=" ".join(["mot"] * mots) + f" {k}.", ecran="", image="x")
              for k in range(n)]
        ph[-1]["ecrit"] += " Et toi ?"; ph[0]["voix"] = "Accroche courte et choc."
        return {"phrases": ph}

    def test_nombres_en_lettres(self):
        from robot.nombres import dire_les_nombres, en_lettres
        self.assertEqual(en_lettres(378), "trois cent soixante-dix-huit")
        self.assertEqual(en_lettres(2027), "deux mille vingt-sept")
        self.assertEqual(en_lettres(80), "quatre-vingts")
        self.assertEqual(dire_les_nombres("16 000 km"), "seize mille kilomètres")

    def test_regles_texte(self):
        from robot import controle
        s = self.script()
        self.assertEqual(controle.regles_texte(s), [])
        s["phrases"][3]["voix"] = "Il y a 378 jours."; s["phrases"][4]["ecran"] = "UN TITRE BEAUCOUP TROP LONG POUR L'ÉCRAN"
        pb = controle.regles_texte(s)
        controle.corriger_sans_ia(s, pb)
        self.assertEqual(s["phrases"][3]["voix"], "Il y a trois cent soixante-dix-huit jours.")
        self.assertLessEqual(len(s["phrases"][4]["ecran"]), 24)
        self.assertTrue(any(i is None for i, _, _ in controle.regles_texte(self.script(n=6))))   # trop court

    def test_note(self):
        from robot import controle
        B = controle.Bulletin()
        B.ouvrir("images", "hors sujet", 2); B.ouvrir("images", "toujours hors sujet", 2)   # même passage : un 2e essai
        self.assertEqual(len(B.ouverts()), 1); self.assertEqual(B.ouverts()[0]["essais"], 2)
        self.assertEqual(B.note(), 90)
        B.fermer("images", 2, "écran de texte")
        self.assertEqual(B.note(), 100); self.assertEqual(B.resume()["graves_restants"], 0)
        B.saute("regard de l'IA")
        self.assertEqual(B.resume()["graves_restants"], 1)                                 # contrôle non fait : pas publiée seule

    def test_solutions_garanties(self):
        from robot import controle
        s = {"phrases": [dict(voix="Accroche.", ecrit="Accroche.", ecran="", image="x"),
                         dict(voix="un, " * 20 + "deux trois quatre cinq six sept huit neuf dix onze douze treize.",
                              ecrit="phrase longue", ecran="", image="x"),
                         dict(voix="Fin.", ecrit="Fin.", ecran="", image="x")]}
        pb = [(1, "phrase trop longue (plus de 32 mots)", False), (2, "la dernière phrase n'est pas une question au spectateur", False)]
        controle.solutions_garanties(s, pb)
        self.assertTrue(s["phrases"][-1]["ecrit"].endswith("?") or "?" in s["phrases"][-1]["ecrit"])
        self.assertEqual(len(s["phrases"]), 5)                                              # coupée en deux + question ajoutée

    def test_image_noire(self):
        from robot import controle
        from PIL import Image
        noir = os.path.join(TMP, "noir.jpg"); Image.new("RGB", (64, 64), (3, 3, 3)).save(noir)
        self.assertLess(controle.mesures_image(noir)[0], 20)

    def test_avant_publication(self):
        from robot import controle
        v = {"duree": 70, "description": "ok", "hashtags": ["#a", "#b", "#c"], "url": "file:///x", "controles": {"graves_restants": 1}}
        pb = controle.avant_publication(v, {"publication": {"compte": "buzz.insolite"}})
        self.assertTrue(any("grave" in p for p in pb)); self.assertTrue(any("adresse" in p for p in pb))
        self.assertFalse(any("grave" in p for p in controle.avant_publication(v, {"publication": {"compte": "x"}}, forcer=True)))

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg absent")
    def test_image_d_une_video_trop_courte(self):
        from robot import controle
        f = os.path.join(TMP, "court.mp4")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=320x240:d=1", f], check=True)
        img = controle._image_de({"type": "video", "chemin": f, "debut": 5}, TMP, "court.jpg")    # 5 s demandées sur 1 s
        self.assertTrue(os.path.getsize(img) > 0)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg absent")
    def test_ecran_noir_detecte(self):
        from robot import controle
        f = os.path.join(TMP, "noir.mp4")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=320x240:d=2", "-f", "lavfi",
                        "-i", "color=c=black:s=320x240:d=2", "-filter_complex", "[0][1]concat=n=2:v=1", f], check=True)
        self.assertEqual(controle.ecrans_noirs(f, [0, 2]), {1})


class TestAnalyseDesErreurs(unittest.TestCase):
    def test_journal_garde_les_erreurs(self):
        from robot import commun
        commun.noter("⚠️ « Sujet » abandonné : essai", "erreur")
        commun.ecrire("journal.json", {"evenements": []})          # comme un retour à la version en ligne
        commun.rejouer_journal()
        self.assertIn("abandonné", lire("journal.json")["evenements"][0]["texte"])
        commun.A_ENVOYER.clear()

    def test_verification_seulement_phrases_nouvelles(self):
        from robot import ia
        vu = {}
        def fausse_ia(consigne, texte, **k):
            vu["texte"] = texte
            return {"problemes": [{"phrase": 0, "correction": ""}, {"phrase": 2, "correction": "Il y a 3 chats."}]}, "test:modele"
        garde, ia.demander_json = ia.demander_json, fausse_ia
        try:
            s = {"phrases": [dict(voix="a", ecrit="Accroche."), dict(voix="b", ecrit="Fait vérifié."),
                             dict(voix="c", ecrit="Nouvelle phrase."), dict(voix="d", ecrit="Question ?")]}
            ecrire.verifier(s, [], seulement=[2])
        finally:
            ia.demander_json = garde
        self.assertIn("[À JUGER] Nouvelle", vu["texte"]); self.assertNotIn("[À JUGER] Accroche", vu["texte"])
        self.assertEqual(len(s["phrases"]), 4)                                  # la phrase 0 (non jugée) reste
        self.assertEqual(s["phrases"][2]["voix"], "Il y a trois chats.")        # corrigée, nombres en lettres

    def test_modele_retire_oublie(self):
        from robot import ia
        ia._mort("groq", "vieux-modele", 404, '{"message": "The model does not exist"}')
        self.assertIn(("groq", "vieux-modele"), ia._MORTS)


class TestJamaisAbandonnee(unittest.TestCase):
    def test_reprise_sur_le_meme_sujet(self):
        from robot import principal
        appels = []
        def fausse_fabrique(s, R, n, total, journal, format_, secours=False, etat=None):
            appels.append(secours)
            if len(appels) < 3:
                raise RuntimeError("panne passagère")
            return dict(id="v1", titre="t", duree=70, ecrans_illustres=5, statut="nouvelle")
        garde, principal.fabriquer = principal.fabriquer, fausse_fabrique
        dort, principal.time.sleep = principal.time.sleep, lambda s: None
        try:
            faites = principal.creer(1, libre="Un sujet libre")
        finally:
            principal.fabriquer = garde; principal.time.sleep = dort
        self.assertEqual(len(faites), 1); self.assertEqual(appels, [False, False, False])   # même sujet, 3e essai réussi
        self.assertEqual(lire("file.json")["videos"][0]["id"], "v1")                        # et sur le site

    def test_etape_ratee_reprise_seule(self):
        """Une étape qui plante recommence seule : les étapes d'avant ne sont jamais refaites."""
        from robot import principal, montage
        os.environ["SIMULATION"] = "1"
        comptes = {"ecrire": 0, "monter": 0}
        vrai_script, vrai_monter = principal.script_simulation, montage.monter
        def script(s):
            comptes["ecrire"] += 1; return vrai_script(s)
        def monter(*a, **k):
            comptes["monter"] += 1
            if comptes["monter"] <= 4:                    # 3 essais dans l'étape + 1 dans la 1re reprise : puis ça passe
                raise RuntimeError("montage planté")
            return 70.0
        principal.script_simulation, montage.monter = script, monter
        dort, principal.time.sleep = principal.time.sleep, lambda s: None
        verif = principal.controle.controle_video
        principal.controle.controle_video = lambda *a, **k: {}
        mini, principal.montage.miniature = principal.montage.miniature, lambda *a: None
        try:
            faites = principal.creer(1, libre="Un sujet qui plante au montage")
        finally:
            principal.script_simulation, montage.monter, principal.time.sleep = vrai_script, vrai_monter, dort
            principal.controle.controle_video, principal.montage.miniature = verif, mini
            os.environ.pop("SIMULATION", None)
        self.assertEqual(len(faites), 1)
        self.assertEqual(comptes["ecrire"], 1)            # le texte n'a été écrit qu'une fois
        self.assertEqual(comptes["monter"], 5)
        self.assertEqual(faites[0]["reprises"], 1)

    def test_texte_court_ne_bloque_pas(self):
        from robot import controle
        s = {"phrases": [dict(voix="Accroche courte.", ecrit="Accroche courte.", ecran="", image="x"),
                         dict(voix="Et toi ?", ecrit="Et toi ?", ecran="", image="x")]}
        garde, controle.ia.demander_json = controle.ia.demander_json, lambda *a, **k: (_ for _ in ()).throw(controle.ia.AucuneIA("x"))
        try:
            controle.controle_texte(s, [], controle.Bulletin())                                # plus de LookupError
        finally:
            controle.ia.demander_json = garde


class TestSujetsRiches(unittest.TestCase):
    def test_richesse(self):
        from robot import sources
        arts = [dict(media=m, titre="t", texte="x" * 2000) for m in ("ladepeche.fr", "ici.fr", "leparisien.fr")]
        self.assertTrue(sources.assez_riche(arts))
        self.assertFalse(sources.assez_riche(arts[:2]))                                   # 2 médias seulement
        self.assertFalse(sources.assez_riche(arts[:2] + [dict(media="Google Actualités", titre="t", texte="x" * 9000)]))

    def test_sujet_maigre_ecarte(self):
        """Un sujet trop maigre n'est jamais commencé : le robot passe au suivant, riche en articles."""
        from robot import principal
        from robot.commun import ecrire
        ecrire("buzz.json", {"sujets": [{"id": "maigre", "titre": "Sujet maigre", "statut": "nouveau", "score": 9},
                                        {"id": "riche", "titre": "Sujet riche", "statut": "nouveau", "score": 5}]})
        riche = [dict(media=m, titre="t", lien="", texte="x" * 2000) for m in ("a.fr", "b.fr", "c.fr")]
        faits = []
        def fabrique(s, R, n, total, journal, format_, secours=False, etat=None):
            faits.append((s["id"], len(etat.get("articles") or [])))
            return dict(id="v-" + s["id"], titre="t", duree=70, ecrans_illustres=5, statut="nouveau")
        garde = (principal.fabriquer, principal.sources.chercher_large)
        principal.fabriquer = fabrique
        principal.sources.chercher_large = lambda t, *a, **k: riche if "riche" in t else riche[:1]
        try:
            principal.creer(1)
        finally:
            principal.fabriquer, principal.sources.chercher_large = garde
        self.assertEqual(faits, [("riche", 3)])                                          # articles déjà lus, gardés
        self.assertEqual({s["id"]: s["statut"] for s in lire("buzz.json")["sujets"]}["maigre"], "sans_source")

    def test_videos_du_sujet_licence(self):
        """Seules les vidéos sous licence Creative Commons, avec au moins 2 mots du sujet dans le titre, sont reprises."""
        from robot import images
        import json as J
        appels = []
        def faux(args, timeout=120):
            appels.append(args)
            if "--flat-playlist" in args:
                return J.dumps({"entries": [dict(id="A", title="Policier vole un vélo à Toulouse", duration=60),
                                            dict(id="B", title="Policier vélo Toulouse caméra", duration=60),
                                            dict(id="C", title="Recette de crêpes", duration=60)]})
            if "-J" in args:
                return J.dumps(dict(license="Creative Commons Attribution license (reuse allowed)" if "v=A" in args[-1]
                                    else "", channel="Auteur", title="x", duration=60))
            open(args[args.index("-o") + 1], "wb").close(); return ""
        garde = (images._ytdlp, images.shutil_which, images.subprocess.check_output)
        images._ytdlp, images.shutil_which = faux, lambda n: "/x"
        images.subprocess.check_output = lambda *a, **k: b"30.0"
        try:
            clips = images.videos_du_sujet("Policier vole vélo cycliste Toulouse", [], TMP, journal=lambda *a: None)
        finally:
            images._ytdlp, images.shutil_which, images.subprocess.check_output = garde
        self.assertEqual({c["id"].split("-")[1] for c in clips}, {"A"})                 # B : licence non libre ; C : hors sujet
        self.assertEqual([c["debut"] for c in clips], [0, 6, 12, 18, 24])
        self.assertIn("CC BY", clips[0]["credit"])


class TestParallele(unittest.TestCase):
    def test_sujets_differents_par_machine(self):
        from robot import principal
        from robot.commun import ecrire
        ecrire("buzz.json", {"sujets": [{"id": f"s{k}", "titre": f"Sujet {k}", "statut": "nouveau", "score": 10 - k} for k in range(8)]})
        plan = principal.planifier(3)
        ids = [i for m in plan for i in m["sujets"].split(",")]
        self.assertEqual(len(plan), 3); self.assertEqual(len(ids), len(set(ids)))       # jamais deux fois le même sujet
        self.assertEqual([m["sujets"].split(",")[0] for m in plan], ["s0", "s1", "s2"])
        B = lire("buzz.json")
        self.assertEqual({s["id"] for s in B["sujets"] if s["statut"] == "en_cours"}, set(ids))
        deuxieme = {i for m in principal.planifier(3) for i in m["sujets"].split(",") if i}
        self.assertFalse(deuxieme & set(ids))                                            # une 2e série ne reprend pas les mêmes


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg absent")
class TestVideoComplete(unittest.TestCase):
    def test_essai_sans_reseau(self):
        env = dict(os.environ, SIMULATION="1")
        env.pop("GITHUB_ACTIONS", None)                  # sur GitHub aussi : ni Release, ni envoi dans le dépôt
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
            with open(f, encoding="utf-8") as fh:
                d = yaml.safe_load(fh)
            self.assertIn("jobs", d, f); self.assertTrue(d.get("name"), f)

    def test_donnees_valides(self):
        for f in glob.glob(os.path.join(RACINE, "docs", "donnees", "*.json")):
            json.load(open(f, encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
