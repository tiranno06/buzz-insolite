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

    def test_reponse_en_liste(self):
        """Bug du 25/11 : l'IA répondait par une liste et le contrôle des images plantait."""
        from robot import ia
        self.assertEqual(ia._objet([{"n": 1}])["images"], [{"n": 1}])
        self.assertEqual(ia._objet({"images": []}), {"images": []})

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

    def test_jamais_une_video_sans_images(self):
        """Cas de la vidéo des étoiles du 24/11 : toutes les recherches échouent. Les écrans gardent une vraie image (prise
        sur un autre écran, à un autre moment) au lieu de devenir des écrans de texte."""
        from robot import controle
        video = dict(type="video", chemin="x.mp4", debut=0, duree=40, id="yt-A-0", credit="c")
        s = {"titre": "Étoiles", "phrases": [dict(ecrit=f"phrase {k}", image="stars", entite="") for k in range(6)]}
        s["phrases"][0]["media"] = video
        s["phrases"][0]["_valide"] = True                                                # validée par l'IA des images
        garde = (controle.images.trouver, controle.images.videos_du_sujet)
        controle.images.trouver = lambda *a, **k: None
        controle.images.videos_du_sujet = lambda *a, **k: []
        try:
            for i in range(1, 5):
                controle.nouvelle_image(s, i, TMP, set(), lambda *a: None)
        finally:
            controle.images.trouver, controle.images.videos_du_sujet = garde
        self.assertTrue(all(p.get("media") for p in s["phrases"][:5]))
        self.assertEqual(len({p["media"]["id"] for p in s["phrases"][:5]}), 5)          # chacun son passage
        self.assertEqual(controle.part_illustree(s), (5, 5))

    def test_titres_de_presse_ne_comptent_pas(self):
        """Demande de l'auteur du 24/11 : un titre de journal n'est pas une vraie image, et n'est jamais recopié ailleurs."""
        from robot import controle
        presse = dict(type="photo", chemin="p.png", id="presse-x", presse=True)
        s = {"phrases": [dict(media=presse, _valide=True), dict(media=None), dict(media=None)]}
        self.assertEqual(controle.part_illustree(s), (0, 2))
        self.assertIsNone(controle._image_deja_bonne(s, 1))

    def test_tri_des_mots(self):
        from robot import images
        self.assertEqual(images._mots_sujet("CAN 2025 : Sénégal vainqueur, you can't, the"), {"sénégal", "vainqueur"})

    def test_peu_d_images_jamais_100(self):
        from robot import controle
        s = {"phrases": [dict(ecrit=f"p{k}", media=None) for k in range(8)]}
        B = controle.Bulletin()
        garde = controle.juger_images; controle.juger_images = lambda *a, **k: {}
        try:
            controle.controle_images(s, TMP, B, lambda *a: None, set(), "Sujet")
        finally:
            controle.juger_images = garde
        r = B.resume()
        self.assertLess(r["note"], 100); self.assertTrue(r["graves_restants"])            # « à vérifier », jamais publiée seule

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
        def fausse_fabrique(s, R, n, total, journal, format_, secours=False, etat=None, attendre=None):
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
    def test_presse_anglaise(self):
        """Actu du monde : la presse en anglais est cherchée quand l'IA a donné des mots-clés anglais."""
        from robot import sources
        demandes = []
        def faux_bing(q, n=12, langue="fr"):
            demandes.append(langue)
            return [("Tokyo robot waiter goes viral", "https://www.bbc.com/news/1", "A robot waiter in Tokyo")] if langue == "en" else []
        garde = (sources.bing, sources.lire_flux, sources.texte_article)
        sources.bing, sources.lire_flux, sources.texte_article = faux_bing, lambda u: [], lambda u: "x" * 900
        try:
            arts = sources.chercher("Tokyo : un robot serveur", ["robot", "Tokyo"], mots_en=["Tokyo", "robot", "waiter"])
            nb = sources.nombre_de_medias("Tokyo : un robot serveur", ["robot", "Tokyo"], ["Tokyo", "robot", "waiter"])
        finally:
            sources.bing, sources.lire_flux, sources.texte_article = garde
        self.assertIn("en", demandes); self.assertEqual(arts[0]["media"], "bbc.com"); self.assertEqual(nb, 1)

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
        def fabrique(s, R, n, total, journal, format_, secours=False, etat=None, attendre=None):
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
        def faux_json(url, *a, **k):
            if "sepiasearch" in url:
                return {"data": [dict(url="https://pt.fr/w/1", uuid="P1", name="Toulouse : le policier et le vélo volé",
                                      duration=40, licence={"id": 1}, account={"displayName": "Témoin"}),
                                 dict(url="https://pt.fr/w/2", uuid="P2", name="BFM : policier vélo Toulouse",
                                      duration=40, licence={"id": 1}, account={"displayName": "BFMTV"})]}
            raise OSError("hors ligne")
        garde = (images._ytdlp, images.shutil_which, images.subprocess.check_output, images._json, images.commons_video)
        images._ytdlp, images.shutil_which, images._json = faux, lambda n: "/x", faux_json
        images.subprocess.check_output = lambda *a, **k: b"30.0"
        images.commons_video = lambda *a: None
        try:
            clips = images.videos_du_sujet("Policier vole vélo cycliste Toulouse", [], TMP, journal=lambda *a: None)
        finally:
            (images._ytdlp, images.shutil_which, images.subprocess.check_output, images._json, images.commons_video) = garde
        self.assertEqual({c["id"].split("-")[1] for c in clips}, {"A", "P1"})          # B : licence non libre ; C : hors
        self.assertTrue(any("PeerTube" in c["credit"] for c in clips))                  # sujet ; P2 : chaîne de télé
        self.assertEqual(clips[0]["id"].split("-")[0] != clips[1]["id"].split("-")[0], True)   # passages alternés
        clips = [c for c in clips if c["id"].startswith("yt-")]
        self.assertEqual([c["debut"] for c in clips], [0, 10, 20])                    # morceaux de 10 s
        self.assertIn("CC BY", clips[0]["credit"])

    def test_vimeo_licences_libres(self):
        from robot import images
        def faux(url, entetes=None, *a):
            self.assertIn("bearer", entetes["Authorization"])
            dl = [dict(link="https://dl/1.mp4", height=540, size=9e6), dict(link="https://dl/0.mp4", height=240, size=2e6)]
            return {"data": [dict(link="https://vimeo.com/1", name="n", duration=30, user={"name": "A"}, license="by", download=dl),
                             dict(link="https://vimeo.com/2", name="n", duration=30, user={"name": "B"}, license="by-nc", download=dl),
                             dict(link="https://vimeo.com/3", name="n", duration=30, user={"name": "C"}, license="by")]}
        garde = images._json; images._json = faux
        os.environ["VIMEO_TOKEN"] = "essai"
        try:
            c = images._cand_vimeo("Sujet", print)
        finally:
            images._json = garde; os.environ.pop("VIMEO_TOKEN")
        self.assertEqual({x["page"] for x in c}, {"https://vimeo.com/1"})               # « by-nc » jamais repris ; sans lien
        self.assertEqual(c[0]["fichier"], "https://dl/1.mp4")                            # de téléchargement : écartée
        self.assertEqual(images._cand_vimeo("Sujet", print), [])                          # sans clé : Vimeo sauté

    def test_preuves_et_mention_ia(self):
        from robot import principal, publier
        s = {"phrases": [dict(media=dict(type="video", id="yt-A-0", page="https://y/A", licence="CC BY", auteur="X", credit="c")),
                         dict(media=dict(type="video", id="yt-A-0-bis1", page="https://y/A", licence="CC BY", auteur="X", credit="c")),
                         dict(media=dict(type="carte")), dict(media=None)]}
        p = principal.preuves_licences(s)
        self.assertEqual(len(p), 1); self.assertEqual(p[0]["page"], "https://y/A")
        v = dict(description="d", question="q", hashtags=["#a"])
        self.assertIn("IA", publier.texte(v, mention_ia=True)); self.assertNotIn("IA", publier.texte(v))

    def test_extension_selon_le_contenu(self):
        """Bug du 25/11 : un PNG enregistré en « .jpg » ne s'ouvrait pas sur GitHub ; il est renommé selon son contenu."""
        from robot import images
        from PIL import Image
        c = os.path.join(TMP, "faux.jpg")
        Image.new("RGB", (40, 40), (200, 30, 30)).save(c, format="PNG")
        bon = images.bonne_extension(c)
        self.assertTrue(bon.endswith(".png")); self.assertTrue(os.path.exists(bon)); self.assertFalse(os.path.exists(c))

    def test_photo_standard(self):
        """JPEG CMYK (refusé par ffmpeg) → JPEG RGB standard, lisible."""
        from robot import images
        from PIL import Image
        import random
        c = os.path.join(TMP, "cmyk.jpg")
        im = Image.new("CMYK", (400, 300))
        im.putdata([tuple(random.randrange(256) for _ in range(4)) for _ in range(400 * 300)])
        im.save(c, "JPEG")
        std = images.photo_standard(c)
        with Image.open(std) as x:
            self.assertEqual(x.mode, "RGB")
        self.assertEqual(images.lisible(std), "")

    def test_image_d_un_autre_aspect_du_sujet_acceptee(self):
        from robot import controle
        s = {"phrases": [dict(ecrit="La chaîne de montage de l'A320", media=dict(type="photo", chemin="x", id="a")), dict(ecrit="Et toi ?")]}
        garde = (controle._image_de, controle.mesures_image, controle.juger_images)
        controle._image_de = lambda *a, **k: "x.jpg"; controle.mesures_image = lambda c: (120, 40)
        controle.juger_images = lambda *a, **k: {0: {"rapport": "sujet", "colle": False, "probleme": "avion en vol"}}
        B = controle.Bulletin()
        try:
            controle.controle_images(s, TMP, B, lambda *a: None, set(), "Airbus A320")
        finally:
            controle._image_de, controle.mesures_image, controle.juger_images = garde
        self.assertFalse([l for l in B.ouverts() if l["niveau"] == "images" and l["ecran"] is not None])

    def test_licences(self):
        from robot import images
        self.assertTrue(images.licence_ok("https://creativecommons.org/licenses/by/3.0/"))
        self.assertTrue(images.licence_ok("https://creativecommons.org/publicdomain/zero/1.0/"))
        self.assertFalse(images.licence_ok("http://creativecommons.org/licenses/by-nc-sa/2.0/"))
        self.assertFalse(images.licence_ok("https://creativecommons.org/licenses/by-nd/4.0/"))
        self.assertTrue(images._interdit("Reportage BFMTV", "") or images._interdit("reportage BFM", ""))


class TestQualite(unittest.TestCase):
    def test_coupes_sur_le_rythme(self):
        from robot import sons
        temps = sons.battements(sorted(glob.glob(os.path.join(RACINE, "sons", "musique", "neutre_*.mp3")))[0])
        self.assertGreater(len(temps), 20)
        ph = [dict(duree=2.37), dict(duree=3.11), dict(duree=1.9)]
        sons.caler_pauses(ph, temps)
        t = 0.0
        for p in ph[:-1]:
            t += p["duree"] + p["_pause"]
            self.assertTrue(0.08 <= p["_pause"] <= 0.45)
            self.assertLess(min(abs(b - t) for b in temps), 0.002)                 # l'écran suivant tombe sur un temps

    def test_zones_libres_tiktok(self):
        from robot import montage
        x, y = montage.LOGO_XY
        self.assertGreaterEqual(y, montage.ZONE_HAUT)                               # sous la loupe et « Pour toi »
        self.assertLess(montage.H - montage.SOUS_TITRES_MARGE, montage.ZONE_BAS)   # sous-titres au-dessus de la description

    def test_accroche_et_couverture(self):
        from robot import principal
        s = {"phrases": [dict(duree=2, media=dict(type="photo", id="p")), dict(duree=2, media=dict(type="carte")),
                         dict(duree=2, ecran="378 JOURS", media=dict(type="video", id="v", reelle=True)), dict(duree=2)]}
        principal.accroche(s)
        self.assertEqual(s["phrases"][0]["media"]["id"], "v"); self.assertEqual(s["phrases"][2]["media"]["id"], "p")
        self.assertGreater(principal.couverture_ms(s), 4000)                       # écran 3 : vraie image + gros titre


class TestFormatsEtSujets(unittest.TestCase):
    def test_sujet_deja_traite_dans_la_semaine(self):
        from robot import principal
        from robot.commun import ecrire, iso
        ecrire("file.json", {"videos": [dict(id="v", sujet="Policier vole vélo à cycliste à Toulouse", titre="t", cree_le=iso(),
                                             statut="publiee")]})
        self.assertTrue(principal.deja_traite(dict(id="x", titre="Policier vole vélo cycliste Toulouse : vidéo choque")))
        self.assertFalse(principal.deja_traite(dict(id="y", titre="Golden retriever sauve un enfant au Brésil")))
        ecrire("file.json", {"videos": []})

    def test_formats_et_categories(self):
        from robot import ecrire as E, publication_auto, buzz
        from robot.commun import ecrire
        for f in ("chiffre", "monde60", "region"):
            self.assertIn(f, E.FORMATS)
        ecrire("stats.json", {"vues_mediane": 1000, "categories": [{"nom": "animaux", "vues_mediane": 3000}]})
        self.assertEqual(buzz.facteur_categorie("animaux"), 1.8); self.assertEqual(buzz.facteur_categorie("sport"), 1.0)
        ecrire("stats.json", {})


class TestRefaire(unittest.TestCase):
    def test_refaire_les_images_corrige(self):
        """Refaire « images » : seuls les écrans signalés changent, et leurs anciennes images sont interdites."""
        from robot import refaire, commun
        d1 = os.path.join(TMP, "travail1"); os.makedirs(d1, exist_ok=True)
        for k in range(3):
            with open(os.path.join(d1, f"media{k:02d}.jpg"), "wb") as f:
                f.write(b"x")
        script = {"titre": "t", "phrases": [dict(voix=f"phrase {k}", ecrit=f"phrase {k}", uid=k, mots=[["a", 0, 1]], son="s",
                                                 media=dict(type="photo", id=f"wiki-{k}", chemin=os.path.join(d1, f"media{k:02d}.jpg")))
                                            for k in range(3)] + [dict(voix="Et toi ?", ecrit="Et toi ?", uid=3)]}
        bulletin = {"lignes": [dict(niveau="images", ecran=1, probleme="image hors sujet", corrige=False)]}
        arch = refaire.archiver(script, [dict(media="a.fr", titre="t", texte="x")], bulletin, d1, "v1")
        vrai = refaire.urllib.request.urlopen
        refaire.urllib.request.urlopen = lambda req, timeout=0: open(arch, "rb")
        try:
            v = dict(id="v1", tag="v-v1", titre="t", _nouvel_id="v1-r1", controles=bulletin)
            etat, etape = refaire.preparer(v, dict(id="s", titre="t"), "auto", "et l'écran 3 aussi", os.path.join(TMP, "r1"),
                                           "x/y", commun.REGLAGES_DEFAUT, journal=lambda *a: None)
        finally:
            refaire.urllib.request.urlopen = vrai
        ph = etat["script"]["phrases"]
        self.assertEqual(etape, "images")
        self.assertIn("media", ph[0]); self.assertNotIn("media", ph[1]); self.assertNotIn("media", ph[2])   # écrans 2 et 3
        self.assertTrue({"wiki-1", "wiki-2"} <= etat["deja"]); self.assertNotIn("wiki-0", etat["deja"])
        self.assertTrue(os.path.exists(ph[0]["media"]["chemin"]))                                       # fichier gardé
        self.assertNotIn("mots", ph[0])                                                                  # voix : mémoire
        self.assertEqual(refaire.ecrans_cites("écrans 2, 4 et 5", 6), {1, 3, 4})


class TestJamaisSansImages(unittest.TestCase):
    def test_publication_refusee_sans_images_meme_forcee(self):
        from robot import controle
        v = dict(ecrans_illustres=1, ecrans_total=14, duree=70, description="d", hashtags=["#a", "#b", "#c"], url="")
        self.assertTrue(any("vraies images" in x for x in controle.avant_publication(v, {"publication": {}}, forcer=True)))

    def test_peertube_essaye_quand_youtube_refuse(self):
        """Essai du 24/11 : les 8 premiers candidats étaient des YouTube refusés ; PeerTube doit être essayé quand même."""
        from robot import images
        import json as J
        def faux(args, timeout=120):
            if "--flat-playlist" in args:
                return J.dumps({"entries": [dict(id=f"Y{k}", title="Macron malaise Toulouse étudiant", duration=60) for k in range(9)]})
            if "-J" in args:
                raise RuntimeError("ERROR: Sign in to confirm you're not a bot")
            open(args[args.index("-o") + 1], "wb").close(); return ""
        def faux_json(url, *a, **k):
            if "sepiasearch" in url:
                return {"data": [dict(url="https://pt.fr/w/9", uuid="P9", name="Macron à Toulouse : malaise d'un étudiant",
                                      duration=40, licence={"id": 1}, account={"displayName": "Témoin"})]}
            raise OSError("hors ligne")
        garde = (images._ytdlp, images.shutil_which, images.subprocess.check_output, images._json, images.commons_video)
        images._ytdlp, images.shutil_which, images._json = faux, lambda n: "/x", faux_json
        images.subprocess.check_output = lambda *a, **k: b"30.0"
        images.commons_video = lambda *a: None
        images.YOUTUBE["refuse"] = False
        try:
            clips = images.videos_du_sujet("Malaise étudiant devant Macron à Toulouse", [], TMP, journal=lambda *a: None)
        finally:
            (images._ytdlp, images.shutil_which, images.subprocess.check_output, images._json, images.commons_video) = garde
            images.YOUTUBE["refuse"] = False
        self.assertTrue(clips); self.assertTrue(all("PeerTube" in c["credit"] for c in clips))


class TestComposition(unittest.TestCase):
    def test_morceaux_continus(self):
        """Un morceau de 10 s couvre deux phrases : la 2e reprend la vidéo là où la 1re s'arrête."""
        from robot import montage
        clip = dict(type="video", chemin="c.mp4", debut=20, id="pt-x-2")
        ph = [dict(media=clip), dict(media=dict(clip, id="pt-x-2-suite", suite=True)), dict(media=None)]
        montage.enchainer(ph, [0.0, 4.3, 8.9])
        self.assertEqual(ph[1]["media"]["debut"], 24.3)

    def test_scenes_de_5_a_10_secondes(self):
        from robot import principal
        mots = lambda n: " ".join(["mot"] * n)
        ph = [dict(voix=mots(n)) for n in (8, 10, 30, 6, 7, 9, 12)] + [dict(voix="Et toi ?")]
        scenes = principal.scenes_de(ph)
        self.assertEqual(sum(scenes, []), list(range(7)))                            # chaque phrase dans une scène, dans l'ordre
        for sc in scenes:
            d = sum(len(ph[j]["voix"].split()) / 3.5 + 0.18 for j in sc)
            self.assertTrue(len(sc) == 1 or 5 <= d <= 10.2, (sc, d))                 # 5 à 10 s (une longue phrase reste seule)

    def test_jamais_deux_fois_le_meme_passage(self):
        from robot import controle
        v = dict(type="video", chemin="c.mp4", debut=0, duree=60, id="pt-a-0")
        s = {"phrases": [dict(media=v, _valide=True), dict(media=None), dict(media=dict(v, debut=10, id="pt-a-1")), dict(media=None)]}
        m = controle._image_deja_bonne(s, 1)
        self.assertTrue(m["suite"])                                                  # la scène d'avant continue
        s["phrases"][2]["_valide"] = False
        m = controle._image_deja_bonne(s, 3)
        self.assertEqual(m["debut"], 20)                                             # passage jamais montré (20 s → 30 s)

    def test_articles_sans_doublons(self):
        from robot import sources
        texte = "Le président a inauguré la nouvelle ligne d'assemblage de l'avion à Toulouse devant les ouvriers " * 5
        A = [dict(media="a.fr", titre="Macron à Toulouse", lien="u1", texte=texte),
             dict(media="b.fr", titre="Inauguration chez Airbus", lien="u2", texte=texte + " Une phrase de plus."),
             dict(media="c.fr", titre="Autre angle", lien="u3", texte="Les syndicats dénoncent les cadences et les salaires " * 8)]
        garde = sources.sans_doublons(A, journal=lambda *a: None)
        self.assertEqual(sorted(a["media"] for a in garde), ["b.fr", "c.fr"])     # copie d'agence écartée, la plus complète gardée


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


class TestDeuxiemeAvis(unittest.TestCase):
    def test_image_gardee_ou_ecran_de_texte(self):
        import tempfile
        from robot import controle, ia
        d = tempfile.mkdtemp()
        img = os.path.join(d, "r.jpg"); vid = os.path.join(d, "v.mp4")
        for f in (img, vid):
            open(f, "wb").write(b"x")
        m = dict(type="video", chemin=vid, id="a", debut=0)
        script = {"titre": "CAN", "phrases": [dict(ecrit="Le Sénégal gagne.", _rejetees=[dict(media=m, img=img)]),
                                              dict(ecrit="Et toi ?")]}
        ancien = ia.regarder_json
        try:
            ia.regarder_json = lambda *a, **k: ({"garder": True, "raison": "même équipe"}, "x")
            self.assertTrue(controle.deuxieme_avis(script, 0, "CAN", journal=lambda *_: None))
            self.assertEqual(script["phrases"][0]["media"]["chemin"], vid)
            script["phrases"][0].pop("media")
            ia.regarder_json = lambda *a, **k: ({"garder": False}, "x")
            self.assertFalse(controle.deuxieme_avis(script, 0, "CAN", journal=lambda *_: None))
        finally:
            ia.regarder_json = ancien


class TestCitations(unittest.TestCase):
    def test_longueur_et_moment(self):
        from robot import citations as C
        self.assertEqual(C.duree_extrait(15), 0)            # moins de 20 s : pas citée
        self.assertEqual(C.duree_extrait(24), 10.0)
        self.assertEqual(C.duree_extrait(30), 12.0)
        self.assertEqual(C.duree_extrait(120), 15.0)
        d = C.meilleur_moment([50, 51, 52, 53, 54], 100, 10)
        self.assertTrue(44 <= d <= 50)

    def test_placement(self):
        from robot import principal as P, citations as C
        ph = [dict(ecrit="un deux trois quatre cinq six sept huit neuf dix onze douze") for _ in range(12)] + [dict(ecrit="Et toi ?")]
        script = {"phrases": ph}
        scenes = P.scenes_de(ph)
        ext = [dict(type="video", chemin="x.mp4", duree=12, debut=0, id=f"citation-{k}", citation=True, compte=f"c{k}",
                    credit="c") for k in range(4)]
        ancien, ancien_sim = C.extraits, P.simulation
        try:
            C.extraits = lambda *a, **k: ext
            P.simulation = lambda: False
            P.placer_citations(script, scenes, {"videos": []}, "/tmp", set(), lambda *_: None,
                               {"video": {"citations": True}}, {}, "buzz")
        finally:
            C.extraits, P.simulation = ancien, ancien_sim
        cites = [p for p in ph if (p.get("media") or {}).get("citation")]
        self.assertTrue(ph[0]["media"]["citation"])         # l'accroche est une citation
        self.assertEqual(len({p["media"]["chemin"] + p["media"]["id"].split("-suite")[0] for p in cites}), 4)

    def test_bandeau_source(self):
        from robot import montage
        import tempfile
        f = os.path.join(tempfile.mkdtemp(), "c.png")
        montage.calque(f, titre="TEST", source="Images : @brutofficiel (TikTok)")
        self.assertTrue(os.path.getsize(f) > 0)


class TestPlusieursExtraits(unittest.TestCase):
    def test_moments_sans_chevauchement(self):
        from robot import citations as C
        m = C.moments([20, 21, 60, 61, 62, 90], 120, 15, int(120 * C.PART_TOTALE // 15))
        self.assertEqual(len(m), 4)
        self.assertTrue(all(b - a >= 15 for a, b in zip(m, m[1:])))
        self.assertEqual(len(C.moments([], 24, 10, max(1, int(24 * C.PART_TOTALE // 10)))), 1)   # vidéo de 24 s : 1 seul


class TestVideosLues(unittest.TestCase):
    def test_stock_et_meme_evenement(self):
        from robot import buzz, citations as C
        ancien_b, ancien_c = buzz.lire, C.lire
        try:
            buzz.lire = lambda n: {"videos": [dict(id="1", compte="a", url="u1", date=time.time(), texte="vieux")]}
            lues = buzz.garder_videos_lues([dict(id="2", compte="b", url="u2", date=time.time(), texte="Sénégal TAS titre CAN")])
            self.assertEqual({v["id"] for v in lues}, {"1", "2"})
            C.lire = lambda n: {"videos": lues + [dict(id="3", compte="c", url="u3", texte="Sénégal vainqueur, récupère son titre")]}
            def sans_ia(*a, **k):
                raise RuntimeError("pas d'IA")
            ancien_ia = C.ia.demander_json; C.ia.demander_json = sans_ia
            try:
                v = C.videos_du_meme_evenement({"titre": "CAN : Sénégal vainqueur après TAS", "mots_cles": ["Sénégal", "TAS", "titre"],
                                                "videos": [dict(id="9", url="u9", vues=5)]}, journal=lambda *_: None)
            finally:
                C.ia.demander_json = ancien_ia
            self.assertEqual([x["id"] for x in v][0], "9")
            self.assertIn("3", [x["id"] for x in v])
        finally:
            buzz.lire, C.lire = ancien_b, ancien_c


class TestPhotosPresse(unittest.TestCase):
    def test_images_de_page(self):
        from robot import sources
        page = ('<meta property="og:image" content="https://ex.fr/photo-senegal.jpg">'
                '<article><img src="/logo.png"><img src="/img/joueurs.jpg" width="900"><img src="/mini.jpg" width="80"></article>')
        self.assertEqual(sources.images_de_page(page, "https://ex.fr/article"),
                         ["https://ex.fr/photo-senegal.jpg", "https://ex.fr/img/joueurs.jpg"])

    def test_empreinte_doublon(self):
        from robot import citations as C
        from PIL import Image
        d = tempfile.mkdtemp()
        a, b = os.path.join(d, "a.jpg"), os.path.join(d, "b.jpg")
        im = Image.new("RGB", (800, 600), (200, 30, 30)); im.paste((10, 10, 200), (0, 0, 400, 600)); im.save(a)
        im.resize((1200, 900)).save(b)
        self.assertLessEqual(bin(C._empreinte(a) ^ C._empreinte(b)).count("1"), 6)


class TestAuditCAN(unittest.TestCase):
    def test_hashtags_en_chaine(self):
        from robot import ecrire
        self.assertEqual(ecrire.liste_hashtags("#can2025 #senegal"), ["can2025", "senegal"])
        self.assertEqual(ecrire.liste_hashtags(["", "c", "a", "can2025"]), ["can2025"])


class TestVision(unittest.TestCase):
    def test_caler_sur_plans(self):
        from robot import vision
        self.assertEqual(vision.caler_sur_plans(3.0, 15, [4.2, 9.0, 16.5, 17.8], 40), (4.2, 13.6))
        self.assertEqual(vision.caler_sur_plans(3.0, 12, [], 40), (3.0, 12))

    def test_moments_notes_ia(self):
        from robot import citations as C
        # l'IA voit l'action vers 80 s, un présentateur au début : le passage choisi est celui de l'action
        m = C.moments([], 120, 15, 1, notes=[(15, 1), (30, 2), (80, 9), (85, 10)])
        self.assertTrue(70 <= m[0] <= 85)

    def test_agrandir_sans_modele(self):
        from robot import vision
        self.assertEqual(vision.agrandir("/inexistant.jpg"), "/inexistant.jpg")


class TestVoixParallele(unittest.TestCase):
    def test_emotion_et_processus(self):
        from robot import voix
        self.assertEqual(voix.emotion("Imagine un titre volé.", premiere=True), 0.7)
        self.assertEqual(voix.emotion("Et toi, tu en penses quoi ?"), 0.62)
        self.assertEqual(voix.emotion("Le TAS a rendu sa décision."), 0.5)
        os.environ["CHATTERBOX_PROCESSUS"] = "3"
        try:
            self.assertEqual(voix.processus_voix(2), 2)
            self.assertEqual(voix.processus_voix(10), 3)
        finally:
            del os.environ["CHATTERBOX_PROCESSUS"]


class TestAudienceSecurite(unittest.TestCase):
    def test_tendance_google(self):
        from robot import sources
        t = [("grève eurostar", "FR", "200+", ["Le trafic des trains Eurostar perturbé par une grève"])]
        self.assertEqual(sources.en_tendance({"titre": "Grève surprise chez Eurostar", "mots_cles": ["Eurostar", "grève"]}, t)["pays"], "FR")
        self.assertIsNone(sources.en_tendance({"titre": "CAN 2025 : Sénégal", "mots_cles": ["Sénégal"]}, t))

    def test_series(self):
        import datetime
        from robot import publication_auto as P
        R = {"creation": {"heures": ["07:15", "16:15"], "series": True, "formats": {}}}
        lundi = datetime.datetime(2026, 11, 23, 7, 15)
        self.assertEqual(P.format_auto(R, lundi, "07:15"), "chiffre")
        vendredi = datetime.datetime(2026, 11, 27, 7, 15)
        self.assertEqual(P.serie_du_jour(R, vendredi, "07:15")[1], "VRAI OU FAUX DU VENDREDI")
        self.assertIsNone(P.serie_du_jour(R, vendredi, "16:15"))


class TestExtraitsPerdus(unittest.TestCase):
    def test_extraits_perdus_remis(self):
        from robot import controle
        d = tempfile.mkdtemp()
        f = [os.path.join(d, f"c{k}.mp4") for k in range(3)]
        for x in f:
            open(x, "wb").write(b"x")
        ext = [dict(type="video", chemin=f[k], id=f"citation-{k}-0", citation=True, compte=f"c{k}") for k in range(3)]
        script = {"_citations_toutes": ext, "phrases": [
            dict(ecrit="a", media=dict(ext[0])), dict(ecrit="b", media=None), dict(ecrit="c", media=dict(type="carte")),
            dict(ecrit="d", media=dict(type="photo", chemin="p.jpg", id="wiki")), dict(ecrit="e", media=dict(ext[0], id="citation-0-0-suite4", suite=True)),
            dict(ecrit="Et toi ?", media=None)]}
        self.assertEqual([m["compte"] for m in controle.extraits_perdus(script)], ["c1", "c2"])
        self.assertEqual(controle.reposer_extraits(script, journal=lambda *_: None), 2)
        self.assertEqual(controle.extraits_perdus(script), [])
        self.assertEqual(script["phrases"][1]["media"]["compte"], "c1")       # l'écran de texte d'abord
        self.assertEqual(script["phrases"][3]["media"]["compte"], "c2")       # puis la photo Wikipédia
        self.assertEqual(script["phrases"][2]["media"]["type"], "carte")      # la carte jamais

    def test_publication_bloquee(self):
        from robot import controle
        v = dict(extraits_perdus=2, duree=70, description="x", hashtags=["#a", "#b", "#c"], url="", ecrans_illustres=10, ecrans_total=10)
        self.assertTrue(any("extrait" in p for p in controle.avant_publication(v, {}, forcer=True)))


class TestAccrocheMeilleurExtrait(unittest.TestCase):
    def test_meilleur_extrait_en_premier_et_comptes_espaces(self):
        from robot import principal as P, citations as C
        ph = [dict(ecrit="un deux trois quatre cinq six sept huit neuf dix onze douze") for _ in range(10)] + [dict(ecrit="Et toi ?")]
        ext = [dict(type="video", chemin="x.mp4", duree=12, debut=0, id=f"citation-{k}", citation=True, compte=c, note_ia=n, credit="c")
               for k, (c, n) in enumerate([("aljazeera", 3), ("aljazeera", 4), ("brut", 9), ("franceinfo", 6), ("bfmtv", 5)])]
        ancien, ancien_sim, ancien_pp = C.extraits, P.simulation, C.photos_presse
        try:
            C.extraits = lambda *a, **k: ext; C.photos_presse = lambda *a, **k: []
            P.simulation = lambda: False
            script = {"phrases": ph}
            P.placer_citations(script, P.scenes_de(ph), {"videos": []}, "/tmp", set(), lambda *_: None,
                               {"video": {"citations": True}}, {"articles": []}, "buzz")
        finally:
            C.extraits, P.simulation, C.photos_presse = ancien, ancien_sim, ancien_pp
        self.assertEqual(ph[0]["media"]["compte"], "brut")                    # le mieux noté ouvre la vidéo
        comptes = [p["media"]["compte"] for p in ph[:-1] if p.get("media") and not p["media"].get("suite")]
        self.assertFalse(any(a == b for a, b in zip(comptes, comptes[1:])), comptes)


class TestPhraseAbsurde(unittest.TestCase):
    def test_simplification_et_regle(self):
        from robot import controle, regles
        self.assertTrue(controle.phrase_absurde("18 7 18"))
        self.assertFalse(controle.phrase_absurde("Le Maroc peut encore faire appel."))
        avant = "Le Maroc peut encore saisir le Tribunal fédéral suisse pour contester le verdict."
        self.assertFalse(controle.simplification_valable(avant, "18 7 18"))
        self.assertFalse(controle.simplification_valable(avant, "Il fait beau aujourd'hui à Paris."))
        self.assertTrue(controle.simplification_valable(avant, "Le Maroc peut encore contester ce verdict en Suisse."))
        script = {"phrases": [dict(ecrit="Le titre revient au Sénégal !", media={"type": "photo"}),
                              dict(ecrit="18 7 18", media={"type": "photo"}),
                              dict(ecrit="Et toi, tu en penses quoi ? Dis-le en commentaire !")]}
        pbs = regles.verifier(script, [], None, None, "desc", "Et toi ?")
        self.assertIn("phrase_absurde", {p["regle"] for p in pbs})
        regles.reparer(script, [p for p in pbs if p["regle"] == "phrase_absurde"], [], {}, journal=lambda *_: None)
        self.assertEqual(len(script["phrases"]), 2)
        self.assertNotIn("phrase_absurde", {p["regle"] for p in regles.verifier(script, [], None, None, "desc", "Et toi ?")})


class TestReglesMarees(unittest.TestCase):
    def test_unites_et_titres(self):
        from robot import regles
        self.assertEqual(regles.convertir_unites("Le niveau sera de 2,8 ft au-dessus."), "Le niveau sera de 0,9 m au-dessus.")
        self.assertEqual(regles.convertir_unites("Des vagues de 20-30 ft."), "Des vagues de 6 à 9 m.")
        self.assertEqual(regles.titre_hors_phrase("CLOSED BEACHES", "Les autorités ferment les plages."), ["closed", "beaches"])
        self.assertEqual(regles.titre_hors_phrase("GAVIN NEWSOM", "Le gouverneur Gavin Newsom a parlé."), [])
        script = {"phrases": [dict(ecrit="Des vagues de 20-30 ft menacent les baigneurs.", ecran="20-30 FT", media={"type": "photo"}),
                              dict(ecrit="Les autorités ferment les plages.", ecran="CLOSED BEACHES", media={"type": "photo"}),
                              dict(ecrit="Et toi, tu ferais quoi ? Dis-le en commentaire !")]}
        pbs = [p for p in regles.verifier(script, [], None, None, "d", "Et toi ?") if p["regle"] in ("unites", "titre")]
        self.assertEqual({p["regle"] for p in pbs}, {"unites", "titre"})
        regles.reparer(script, pbs, [], {}, journal=lambda *_: None)
        self.assertEqual(script["phrases"][0]["ecrit"], "Des vagues de 6 à 9 m menacent les baigneurs.")
        self.assertEqual(script["phrases"][1]["ecran"], "")

    def test_une_image_fixe_par_phrase(self):
        from robot import principal as P, citations as C
        ph = [dict(ecrit="un deux trois quatre cinq six sept huit neuf dix") for _ in range(8)] + [dict(ecrit="Et toi ?")]
        fixes = [dict(type="photo", chemin=f"p{k}.jpg", id=f"presse-{k}", citation=True, compte="m", credit="c") for k in range(8)]
        ancien, ancien_sim, ancien_pp = C.extraits, P.simulation, C.photos_presse
        try:
            C.extraits = lambda *a, **k: []; C.photos_presse = lambda *a, **k: fixes; P.simulation = lambda: False
            P.placer_citations({"phrases": ph}, P.scenes_de(ph), {"videos": []}, "/tmp", set(), lambda *_: None,
                               {"video": {"citations": True}}, {"articles": []}, "buzz")
        finally:
            C.extraits, P.simulation, C.photos_presse = ancien, ancien_sim, ancien_pp
        ids = [p["media"]["id"] for p in ph[:-1]]
        self.assertEqual(len(set(ids)), len(ids), f"la même photo sur plusieurs écrans : {ids}")


class TestProblemeDePhraseRetiree(unittest.TestCase):
    def test_probleme_clos_quand_la_phrase_est_retiree(self):
        """Une vidéo en simulation dont une phrase absurde est retirée par les règles : son problème de voix est clos."""
        from robot import principal, controle
        os.environ["SIMULATION"] = "1"
        vrai = principal.script_simulation
        def script(s):
            d = vrai(s)
            d["phrases"].insert(5, dict(voix="18 7 18", ecrit="18 7 18", ecran="", image=""))
            return d
        verif = controle.controle_video
        def faux_controle(fichier, sc, dossier, B, *a, **k):     # la voix de la phrase absurde est jugée mauvaise
            i = next((n for n, p in enumerate(sc["phrases"]) if p["ecrit"] == "18 7 18"), None)
            if i is not None:
                B.ouvrir("voix", "voix et sous-titres ne correspondent pas (0%)", controle.uid(sc, i))
            return {}
        principal.script_simulation, controle.controle_video = script, faux_controle
        try:
            faites = principal.creer(1, libre="Sujet avec une phrase absurde")
        finally:
            principal.script_simulation, controle.controle_video = vrai, verif
            os.environ.pop("SIMULATION", None)
        v = faites[0]
        self.assertNotIn("18 7 18", v["texte"])
        self.assertFalse([l for l in v["controles"]["lignes"] if not l["corrige"] and "0%" in l["probleme"]])


class TestCreditsIA(unittest.TestCase):
    def _avec(self, reponses):
        """reponses : {fournisseur: exception ou None (= répond)}"""
        from robot import credits, ia
        import urllib.error, io
        def appel(fourn, modele, messages, t, m):
            e = reponses.get(fourn)
            if e:
                raise urllib.error.HTTPError("u", e[0], "x", {}, io.BytesIO(e[1].encode()))
            return '{"ok": true}'
        ancien, env = ia._appel, dict(os.environ)
        ia._appel = appel
        for f in ia.ORDRE:
            os.environ[ia.FOURNISSEURS[f]["cle"]] = "x"
        avant_or = ia._modeles_openrouter
        ia._modeles_openrouter = lambda vision=False: ("m:free",)
        try:
            return credits.verifier(1, 0, journal=lambda *_: None)
        finally:
            ia._appel, ia._modeles_openrouter = ancien, avant_or
            os.environ.clear(); os.environ.update(env)

    def test_saturees_mise_en_attente(self):
        ok, resume, detail = self._avec({"mistral": (402, "You need a subscription"), "groq": (429, "Rate limit (RPD) per day"),
                                         "gemini": (429, "quota per day"), "openrouter": (429, "free-models-per-day")})
        self.assertFalse(ok)
        self.assertIn("abonnement", detail["mistral"]["raison"])
        self.assertIn("limite du jour", detail["openrouter"]["raison"])

    def test_assez_d_ia(self):
        ok, resume, detail = self._avec({"mistral": (402, "You need a subscription")})
        self.assertTrue(ok, resume)

    def test_places(self):
        from robot import credits
        self.assertEqual(credits.places(0), credits.MAX_EN_MEME_TEMPS)
        self.assertEqual(credits.places(5), 0)

    def test_fournisseur_sans_abonnement_plus_essaye(self):
        from robot import ia
        ia._SAUTES.discard("mistral")
        ia._mort("mistral", "m", 402, '{"message":"You need a subscription to access this API."}')
        self.assertIn("mistral", ia._SAUTES)
        ia._SAUTES.discard("mistral")


class TestPhrasesNombres(unittest.TestCase):
    def test_normaliser_et_ajouts_refusent_les_nombres(self):
        from robot import controle, ecrire, ia
        d = {"titre": "t", "accroche": "A", "phrases": [dict(voix=f"Phrase numéro {k} avec assez de mots ici.") for k in range(9)]
             + [dict(voix="74"), dict(voix="2026"), dict(voix="Et toi, tu en penses quoi ?")]}
        n = ecrire.normaliser(d, {"titre": "t"}, "buzz", "x")
        self.assertFalse([p for p in n["phrases"] if p["ecrit"] in ("74", "2026")])
        script = {"phrases": [dict(voix="Une phrase.", ecrit="Une phrase.") for _ in range(3)] + [dict(voix="Et toi ?", ecrit="Et toi ?")]}
        ancien = ia.demander_json
        ia.demander_json = lambda *a, **k: ({"phrases": {}, "ajouts": [{"voix": "74"}, {"voix": "2"},
                                             {"voix": "Les avocats ont tenté de reporter la peine."}]}, "x")
        try:
            B = controle.Bulletin()
            texte_court = controle.regles_texte
            controle.regles_texte = lambda s: [(None, "trop court", False)] if len(s["phrases"]) < 5 else []
            controle.controle_texte(script, [], B, journal=lambda *_: None)
        finally:
            ia.demander_json = ancien; controle.regles_texte = texte_court
        ecrits = [p["ecrit"] for p in script["phrases"]]
        self.assertNotIn("74", ecrits); self.assertNotIn("2", ecrits)
        self.assertIn("Les avocats ont tenté de reporter la peine.", ecrits)
