"""Fabrication des vidéos (bouton « 🎬 Créer » du site, série de 1 à 10, ou création automatique aux heures choisies).

    python -m robot.principal --nombre 3                  (les 3 meilleurs sujets du buzz pas encore utilisés)
    python -m robot.principal --sujet <id>                (un sujet précis de l'onglet Buzz)
    python -m robot.principal --libre "texte du sujet"    (un sujet écrit à la main)

Pour chaque vidéo : sujet → articles de presse → texte (IA gratuite) → vérification (2e IA) → voix (Piper) → instants des mots
(Whisper) → vraies images libres (Pexels, NASA, Wikimedia) → montage → Release GitHub (adresse publique pour Buffer) → liste.
SIMULATION=1 : essai sans réseau ni IA (écrans de texte, bip à la place de la voix).
"""
import argparse
import os
import re
import shutil
import subprocess
import threading
import urllib.error
import time
import traceback

from . import citations, langue, refaire, regles, avancement, buzz, carte, controle, depot, ecrire, ia, images, montage, sources
from . import voix as V
from .commun import MINIATURES, SORTIE, ecrire as ecrire_donnees, iso, lire, maintenant, noter, reglages, simulation


def sujet_semaine(journal=print):
    """« Les 3 actus les plus folles de la semaine » : les 3 meilleurs sujets des 7 derniers jours (déjà traités ou non)."""
    limite = time.time() - 7 * 86400
    S = [s for s in (lire("buzz.json") or {}).get("sujets") or []
         if s.get("statut") not in ("ignore", "sans_source") and s.get("derniere_vue", time.time()) >= limite]
    S.sort(key=lambda s: -(s.get("score", 0) * (1 + 0.05 * s.get("insolite", 5))))
    if len(S) < 3:
        journal("Moins de 3 sujets cette semaine : pas de vidéo « 3 actus de la semaine »")
        return []
    trois = S[:3]
    return [dict(id=f"semaine-{maintenant():%Y%W}", titre="Les 3 actus les plus folles de la semaine",
                 resume=" / ".join(f"{s['titre']} : {s.get('resume', '')}" for s in trois), mots_cles=[], videos=[],
                 hashtags=[h for s in trois for h in (s.get("hashtags") or [])[:1]], parties=trois,
                 vues=sum(s.get("vues", 0) for s in trois), commentaires=sum(s.get("commentaires", 0) for s in trois))]


MULTI = ("semaine", "monde60")                                # formats qui réunissent plusieurs sujets


def sujet_monde60(journal=print):
    """« Le monde en 60 secondes » : les 4 meilleurs sujets des dernières 24 h, de lieux différents si possible."""
    limite = time.time() - 86400
    S = [s for s in (lire("buzz.json") or {}).get("sujets") or []
         if s.get("statut") not in ("ignore", "sans_source") and s.get("derniere_vue", time.time()) >= limite]
    S.sort(key=lambda s: -s.get("score", 0))
    if len(S) < 4:
        journal("Moins de 4 sujets aujourd'hui : pas de vidéo « Le monde en 60 secondes »")
        return []
    quatre = S[:4]
    return [dict(id=f"monde60-{maintenant():%Y%m%d}", titre="Le monde en 60 secondes",
                 resume=" / ".join(f"{s['titre']} : {s.get('resume', '')}" for s in quatre), mots_cles=[], videos=[],
                 hashtags=[h for s in quatre for h in (s.get("hashtags") or [])[:1]], parties=quatre,
                 vues=sum(s.get("vues", 0) for s in quatre), commentaires=sum(s.get("commentaires", 0) for s in quatre))]


def deja_traite(s, journal=print, jours=7):
    """Sujet déjà mis en vidéo ces 7 derniers jours, même sous un autre titre (60 % des mots en commun) : jamais refait."""
    import datetime
    limite = maintenant() - datetime.timedelta(days=jours)
    for v in (lire("file.json") or {}).get("videos") or []:
        try:
            recente = datetime.datetime.fromisoformat(v.get("cree_le", "")) >= limite
        except ValueError:
            recente = False
        if recente and v.get("statut") not in ("ecartee",) and \
                (v.get("sujet_id") == s["id"] or buzz.meme_sujet(s["titre"], v.get("sujet") or v.get("titre") or "")):
            journal(f"  « {s['titre']} » déjà traité le {v['cree_le'][:10]} (« {v.get('titre', '')} ») : sujet suivant")
            return True
    return False


def libre_pour_moi(s):
    """Sujet pas encore traité (un sujet réservé par une série depuis plus de 3 h est de nouveau libre)."""
    if s.get("statut", "nouveau") == "nouveau":
        return True
    if s.get("statut") == "en_cours" and s.get("reserve_le"):
        import datetime
        return maintenant() - datetime.datetime.fromisoformat(s["reserve_le"]) > datetime.timedelta(hours=3)
    return False


def planifier(nombre, format_="buzz", sujet="", libre="", paralleles=3, journal=print):
    """Répartit une série entre plusieurs machines qui travaillent en même temps (creer.yml, job « plan »).
    Chaque machine reçoit SON sujet + des sujets de réserve à elle seule ; les sujets sont réservés (« en_cours ») pour
    qu'une autre série ne les prenne pas. Renvoie [{"k": n° de machine, "sujets": "id,id,…"}]."""
    if libre.strip() or sujet or format_ in MULTI:
        return [{"k": 1, "sujets": sujet}]
    S = [s for s in (lire("buzz.json") or {}).get("sujets") or [] if libre_pour_moi(s)]
    if not S:
        journal("Aucun sujet du buzz libre : chaque machine prendra un titre à la une de la presse")
        return [{"k": k + 1, "sujets": ""} for k in range(min(nombre, 3))]
    nombre = min(nombre, len(S))
    lots = [[S[k]["id"]] for k in range(nombre)]
    for j, s in enumerate(S[nombre:nombre * 3]):        # réserves, chacune à une seule machine
        lots[j % nombre].append(s["id"])
    reserves = {i for lot in lots for i in lot}

    def appliquer():
        B = lire("buzz.json") or {"sujets": []}
        for s in B.get("sujets", []):
            if s["id"] in reserves and libre_pour_moi(s):
                s.update(statut="en_cours", reserve_le=iso())
        ecrire_donnees("buzz.json", B)
    depot.enregistrer(appliquer, f"Série de {nombre} vidéo(s) : sujets réservés")
    return [{"k": k + 1, "sujets": ",".join(lot)} for k, lot in enumerate(lots)]


def choisir_sujets(n, sujet_id="", libre="", journal=print, format_="buzz"):
    """Sujets à traiter, du meilleur au moins bon. Sans buzz mesuré : titres à la une de la presse."""
    if format_ == "semaine":
        return sujet_semaine(journal)
    if format_ == "monde60":
        return sujet_monde60(journal)
    if libre.strip():
        return [dict(id=buzz.identifiant(libre), titre=libre.strip()[:90], resume=libre.strip(), mots_cles=[], hashtags=[],
                     videos=[], libre=True)]
    B = lire("buzz.json") or {}
    sujets = B.get("sujets") or []
    if sujet_id:                                          # un ou plusieurs sujets imposés (« id1,id2 » : réserves d'une machine)
        ids = [x for x in sujet_id.split(",") if x]
        return [s for i in ids for s in sujets if s["id"] == i]
    frais = [s for s in sujets if libre_pour_moi(s) and not deja_traite(s, journal)]
    if format_ == "region":                                   # une actu d'une ville de France d'abord
        frais.sort(key=lambda s: not s.get("ville_france"))
    if frais:
        return frais[:n + 3]                               # quelques sujets en réserve si l'un n'a pas d'article
    journal("Aucun sujet du buzz disponible : titres à la une de la presse à la place")
    une = sources.a_la_une(journal=journal)
    k = (int(os.environ.get("MACHINE", "1")) - 1) * 4 % max(1, len(une))      # chaque machine part d'un titre différent
    une = une[k:] + une[:k]
    return [dict(id=buzz.identifiant(a["titre"]), titre=a["titre"], resume=a["resume"], mots_cles=[], hashtags=[], videos=[],
                 presse=True) for a in une][:n + 3]


def script_simulation(sujet):
    phrases = [dict(voix=t, ecrit=t, ecran=e, image="") for t, e in (
        ("Ceci est une vidéo d'essai du robot.", "ESSAI"), ("Elle ne contient aucune vraie information.", ""),
        ("Le robot vérifie que le montage fonctionne.", "MONTAGE"), ("Les sous-titres suivent la voix mot à mot.", "SOUS-TITRES"),
        ("Le 24 novembre 2026, tout marche.", "24/11"), ("Les écrans de texte remplacent les images.", ""),
        ("La description et les hashtags sont prêts.", "#"), ("Fin de l'essai.", ""),
        ("Alors, toi, tu aimes ce format ? Dis-le en commentaire !", ""))]
    return dict(titre=f"Essai : {sujet['titre'][:40]}", accroche="ESSAI", phrases=phrases, description="Vidéo d'essai 🧪",
                question="Ça te plaît ?", hashtags=["essai"], sources=[], verifie=True, auteur_ia="simulation")


def voix_simulation(p, chemin):
    d = 0.32 * len(p["ecrit"].split()) + 0.4
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={d}", "-ar", "44100", chemin],
                   check=True)
    mots = V.mots_affiches(p["ecrit"]); pas = d / max(1, len(mots))
    return d, [(m, k * pas, (k + 1) * pas) for k, m in enumerate(mots)]


def avec_ia(fonction, journal, attente_max_min=90):
    """Appelle une étape qui a besoin d'une IA gratuite ; si toutes sont saturées, attend 5 min et réessaie (jamais d'abandon)."""
    debut = time.time()
    while True:
        try:
            return fonction()
        except ia.AucuneIA as e:
            if time.time() - debut > attente_max_min * 60:
                raise
            journal(f"  IA gratuites saturées ({str(e)[:80]}) : nouvel essai dans 5 minutes")
            time.sleep(300)


def fabriquer(sujet, R, n=1, total=1, journal=print, format_="buzz", secours=False, etat=None, attendre=None):
    """Une vidéo complète, découpée en ÉTAPES qui se reprennent (demande de l'auteur du 24/11 : une étape qui plante recommence
    à cette étape, jamais toute la vidéo). Chaque étape réussie est gardée dans `etat` ; une étape qui plante est refaite seule
    (3 essais), et si elle échoue encore, creer rappelle fabriquer avec le même `etat` : on repart de cette étape. À l'intérieur
    d'une étape, ce qui est fait est gardé aussi (voix des phrases déjà dites, images déjà trouvées, écrans déjà montés).
    `secours` (dernière tentative) : voix Kokoro, pas de regard de l'IA sur les images."""
    E = etat if etat is not None else {}
    if "vid" not in E:
        vid = f"{maintenant():%Y%m%d-%H%M%S}" + (f"-{os.environ['MACHINE']}" if os.environ.get("MACHINE") else "")
        E.update(vid=vid, dossier=os.path.join(SORTIE, vid), t0=time.time(), B=controle.Bulletin(), faites=[])
        os.makedirs(E["dossier"], exist_ok=True)
        avancement.demarrer(vid, "video", sujet["titre"])
    else:
        journal(f"  ↪ reprise à l'étape « {next((x for x in ETAPES if x not in E['faites']), 'fin')} » (le reste est gardé)")
    vid, dossier, B = E["vid"], E["dossier"], E["B"]
    pre = f"Vidéo {n}/{total} — " if total > 1 else ""

    def etape(nom, pourcent, fonction):
        if nom in E["faites"]:
            return
        avancement.etape(pre + ETAPES[nom], pourcent, sujet["titre"] if nom == "articles" else "")
        for essai in range(3):
            try:
                t_etape = time.time()
                fonction()
                E.setdefault("durees", {})[nom] = round(time.time() - t_etape)   # durée de chaque étape (page Santé)
                E["faites"].append(nom)
                return
            except Exception as e:
                traceback.print_exc()
                if essai == 2:
                    raise
                journal(f"  ⟳ étape « {ETAPES[nom]} » ratée ({str(e)[:120]}) : elle recommence (essai {essai + 2}/3)")
                time.sleep(15)

    # ---------- 1. articles (déjà lus par creer quand la richesse du sujet a été vérifiée)
    def articles():
        if E.get("articles") is not None:
            pass
        elif simulation():
            E["articles"] = []
        elif sujet.get("parties"):                            # 3 actus de la semaine : 2 articles par sujet
            E["articles"] = [a for s in sujet["parties"] for a in sources.chercher(s["titre"], s.get("mots_cles") or [], maxi=2,
                                                                                    journal=journal)]
        else:                                                 # jamais d'abandon : la recherche s'élargit si besoin
            E["articles"] = sources.chercher_large(sujet["titre"], sujet.get("mots_cles") or [], sujet.get("videos") or [], journal,
                                                   mots_en=sujet.get("mots_cles_en") or [])
        journal(f"  {len(E['articles'])} source(s) : " + ", ".join(f"{a['media']} ({len(a.get('texte') or '')} car.)" for a in E["articles"]))
    etape("articles", 5, articles)

    # ---------- 2. texte (écriture, vérification des faits, contrôle 1/4)
    def ecriture():
        E["script"] = script_simulation(sujet) if simulation() else \
            avec_ia(lambda: ecrire.ecrire(sujet, E["articles"], journal, format_), journal)
    etape("ecriture", 12, ecriture)

    def texte():
        if simulation():
            return
        script, articles_ = E["script"], E["articles"]
        if not script.get("verifie"):
            E["script"] = script = ecrire.verifier(script, articles_, journal)
        for tour in range(5):
            if tour == 3 and not any(a["media"] == "Wikipédia (contexte)" for a in articles_):
                articles_ += sources.contexte_wikipedia(sujet["titre"], journal=journal)
            deja_vues = {p["ecrit"] for p in script["phrases"]}
            script = controle.controle_texte(script, articles_, B, journal)
            nouvelles = [i for i, p in enumerate(script["phrases"]) if p["ecrit"] not in deja_vues]
            if nouvelles:                                     # seules les phrases nouvelles ou réécrites sont revérifiées
                script = ecrire.verifier(script, articles_, journal, seulement=nouvelles)
            if len(script["phrases"]) >= 9 and controle.duree_estimee(script["phrases"]) >= 62 and not controle.regles_texte(script):
                break
        n = langue.corriger(script, journal)                  # orthographe et grammaire des sous-titres (LanguageTool)
        if n:
            B.ajouter("texte", f"{n} faute(s) d'orthographe ou de grammaire corrigée(s)", corrige=True,
                      solution="LanguageTool + IA")
        if controle.duree_estimee(script["phrases"]) < 60:    # jamais d'abandon : signalé, la vidéo va au bout
            B.ouvrir("texte", f"texte un peu court (environ {controle.duree_estimee(script['phrases']):.0f} s)", None, "grave")
        E["script"] = script
    etape("texte", 22, texte)
    script = E["script"]
    for i in range(len(script["phrases"])):
        controle.uid(script, i)                               # numéro fixe de chaque phrase (noms des fichiers)

    # ---------- 3. voix (contrôle 2/4) : seules les phrases pas encore dites
    def voix():
        if secours and not E.get("voix_kokoro"):              # mode secours : toute la voix en Kokoro (jamais deux voix mêlées)
            for p in script["phrases"]:
                p.pop("mots", None)
            E["voix_kokoro"] = True
        E["nom_voix"] = "kokoro-ff_siwis" if E.get("voix_kokoro") else R["video"]["voix"]
        E["vitesse"] = float(R["video"]["vitesse"])
        script["phrases"][0]["_premiere"] = True              # accroche : voix plus vivante (voix.emotion)
        a_dire = [p for p in script["phrases"] if not p.get("mots") or not os.path.exists(p.get("son", ""))]
        for p in a_dire:
            p["son"] = os.path.join(dossier, f"voix{p['uid']:03d}.wav")
        if simulation():
            for p in a_dire:
                p["duree"], p["mots"] = voix_simulation(p, p["son"])
        elif a_dire:
            script["voix_utilisee"] = V.preparer(a_dire, E["nom_voix"], E["vitesse"], journal,
                                                 suivi=lambda k, nb: avancement.progres(30 + 20 * k / nb, f"phrase {k}/{nb}"),
                                                 memoire=os.path.join(dossier, "memoire_voix"))
        for i, p in enumerate(script["phrases"]):
            if p.get("_voix_defaut"):                         # repris par la boucle de la vidéo finie
                B.ouvrir("voix", p["_voix_defaut"], p["uid"])

    # ---------- 4. images : seules les phrases sans image cherchée
    def images_():
        deja = E.setdefault("deja", set())
        deja |= avancement.medias_des_autres()               # jamais les mêmes passages que les autres vidéos en construction
        script["images_generiques"] = R["video"].get("images_generiques", False)
        if "clips" not in E:                                  # VRAIES vidéos du sujet (licence libre), de TOUTES les sources
            E["clips"] = [] if simulation() or format_ in MULTI else \
                images.videos_du_sujet(sujet["titre"], sujet.get("mots_cles") or [], dossier, journal, maxi=5,
                                       ecrans=len(script["phrases"]), mots_en=sujet.get("mots_cles_en") or [])
        ph = script["phrases"]
        # Composition voulue par l'auteur (24/11) : SURTOUT des morceaux de vraies vidéos de 5 à 10 s (un passage de 10 s
        # couvre 1 ou 2 phrases, `suite`), et AUSSI quelques images fixes (1 écran sur 4 : vraie photo de la personne / du
        # lieu cité). Chaque écran reçoit sa recherche (bug corrigé le 24/11 : seule la dernière phrase était cherchée).
        # SCÈNES de 5 à 10 s (demande de l'auteur du 25/11) : les phrases qui se suivent sont regroupées ; une scène = UN
        # morceau de vraie vidéo (qui continue d'une phrase à l'autre) ou une vraie photo ; jamais deux fois le même morceau.
        scenes = E.get("scenes") or scenes_de(ph)
        E["scenes"] = scenes
        placer_citations(script, scenes, sujet, dossier, deja, journal, R, E, format_)

        def donner(scene, m):
            ph[scene[0]]["media"] = m; deja.add(m["id"])
            for j in scene[1:]:
                if "media" not in ph[j]:
                    ph[j]["media"] = dict(m, id=f"{m['id']}-suite{j}", suite=True)

        libres = lambda: [sc for sc in scenes if "media" not in ph[sc[0]]]
        for k, sc in enumerate(libres()):
            entite = next((ph[j].get("entite") for j in sc if ph[j].get("entite")), "")
            if k % 4 == 3 and entite and not simulation():   # 1 scène sur 4 : vraie photo fixe de la personne / du lieu
                m = images.trouver_photo(entite, dossier, ph[sc[0]]["uid"], deja, journal)
                if m:
                    donner(sc, m); continue
            if E["clips"]:
                donner(sc, E["clips"].pop(0))
        if not simulation():                                  # puis des vidéos libres de chaque personne / lieu / objet cité
            entites = E.setdefault("entites_faites", [])
            for sc in libres():
                nom = next((ph[j].get("entite") for j in sc if ph[j].get("entite")), "")
                if not nom or nom in entites or len(entites) >= 6:
                    continue
                besoin = [x for x in libres() if any(ph[j].get("entite") == nom for j in x)]
                clips = images.videos_du_sujet(nom, [], dossier, journal, maxi=1, ecrans=2 * len(besoin),
                                               prefixe=f"entite{len(entites)}", deja=deja)
                entites.append(nom)
                for x in besoin:
                    if clips and "media" not in ph[x[0]]:
                        donner(x, clips.pop(0))
        for n, sc in enumerate(scenes):                       # scènes restantes : chacune sa recherche (photo, vidéo libre)
            if "media" not in ph[sc[0]]:
                p = ph[sc[0]]
                entite = next((ph[j].get("entite") for j in sc if ph[j].get("entite")), "")
                m = None if simulation() else images.trouver(
                    p["image"], dossier, p["uid"], deja, journal, script.get("theme_image", ""),
                    entite=entite, generiques=script["images_generiques"])
                if m:
                    donner(sc, m)
                else:
                    for j in sc:
                        ph[j].setdefault("media", None)
            avancement.progres(52 + 10 * (n + 1) / len(scenes))
        for sc in scenes:                                     # (vidéo refaite) phrase d'une scène sans image : elle continue la scène
            for a, j in zip(sc, sc[1:]):
                if "media" not in ph[j] and (ph[a].get("media") or {}).get("type") in ("video", "photo"):
                    ph[j]["media"] = dict(ph[a]["media"], id=f"{ph[a]['media']['id']}-suite{j}", suite=True)
        for p in ph[:-1]:                                     # dernier filet : aucune phrase sans recherche
            if "media" not in p:
                p["media"] = None if simulation() else images.trouver(
                    p["image"], dossier, p["uid"], deja, journal, script.get("theme_image", ""),
                    entite=p.get("entite", ""), generiques=script["images_generiques"])
        script.setdefault("_reserve", []).extend(E["clips"]); E["clips"] = []   # passages de réserve pour le contrôle
        noms = [p.get("entite") for p in script["phrases"] if p.get("entite")]
        script["entite_sujet"] = max(set(noms), key=noms.count) if noms else ""
        if not E.get("presse_faite"):                         # « La presse en parle » : vrais titres sur des écrans sans image
            titres = [a for a in E["articles"] if a.get("titre") and a.get("media") and a["media"] not in
                      ("Google Actualités", "Wikipédia (contexte)", "Descriptions des vidéos TikTok virales", "Sujet du buzz")]
            libres = [i for i, p in enumerate(script["phrases"][:-1]) if not p.get("media") and i > 0][:min(2, len(titres))]
            for k, i in enumerate(libres):
                script["phrases"][i]["media"] = images.carte_presse(titres[k], os.path.join(dossier, f"presse{k}.png"))
            E["presse_faite"] = True
        script["phrases"][-1]["media"] = None
        serie = serie_de(format_)                             # « LE CHIFFRE DU LUNDI », « VRAI OU FAUX DU VENDREDI »
        if serie:
            script["etiquette"], script["serie_hashtag"] = serie[1], serie[2]
        script["musique"] = R["video"].get("musique", True); script["bruitages"] = R["video"].get("bruitages", True)
        script["transitions"] = R["video"].get("transitions", False)
        if not E.get("carte_faite"):
            lieu_cite = str(script.get("lieu") or "").split(",")[0].split("(")[0].strip()
            texte_articles = " ".join((a.get("texte") or "") + " " + a.get("titre", "") for a in E["articles"]).lower()
            if lieu_cite and lieu_cite.lower() not in texte_articles:
                journal(f"  carte écartée : « {lieu_cite} » n'est pas cité dans les articles")
                script["lieu"] = ""
            if not simulation() and R["video"].get("carte", True) and format_ not in MULTI and script.get("lieu") \
                    and len(script["phrases"]) > 3:
                lieu = carte.trouver_lieu(script["lieu"], script.get("coordonnees"))
                if lieu:                                      # 2e écran : la carte qui zoome sur le lieu de l'actu
                    script["phrases"][1]["media"] = dict(type="carte", credit="Carte : Natural Earth, OpenStreetMap", **lieu)
                    if not script["phrases"][1].get("ecran"):
                        script["phrases"][1]["ecran"] = str(script["lieu"]).split(",")[0][:22]
                    journal(f"  carte : {lieu['nom']}")
            E["carte_faite"] = True
    def controle_images():
        if not simulation():
            controle.controle_images(script, dossier, B, journal, E.setdefault("deja", set()), sujet["titre"], sans_ia=secours)
        avancement.publier_medias(E.get("deja") or ())

    # File d'attente APRÈS le texte (demande de l'auteur du 24/11) : articles et texte se préparent pendant l'attente, la partie
    # lourde (voix, images, montage) démarre dès que la place se libère.
    if attendre and not E.get("file_passee"):
        attendre()
        E["file_passee"] = True
    # Voix (processeur) et images (réseau) EN MÊME TEMPS : chaque vidéo a son propre dossier, et les médias pris par les autres
    # vidéos en construction sont écartés (aucun chevauchement).
    erreurs = []

    def fil_images():
        try:
            etape("images", 52, images_)
            etape("controle_images", 62, controle_images)
        except Exception as e:
            erreurs.append(e)
    fil = threading.Thread(target=fil_images, daemon=True)
    fil.start()
    try:
        etape("voix", 30, voix)
    finally:
        fil.join()
    if erreurs:
        raise erreurs[0]

    # ---------- 5. montage (les écrans déjà fabriqués sont gardés)
    E["fichier"] = fichier = os.path.join(dossier, f"buzz-{vid}.mp4")
    def montage_():
        if not E.get("accroche_faite"):
            accroche(script)                                  # la plus belle vraie vidéo sur les 2 premières secondes
            noms = [a["media"] for a in E["articles"] if a.get("media") and len(a.get("texte") or "") >= 400 and a["media"] not in
                    ("Google Actualités", "Wikipédia (contexte)", "Descriptions des vidéos TikTok virales", "Sujet du buzz")]
            noms = list(dict.fromkeys(noms))[:4]
            script["sources_ecran"] = ("Sources : " + ", ".join(noms)) if noms else ""
            E["accroche_faite"] = True
        E["duree"] = montage.monter(script, dossier, fichier, suivi=lambda k, nb: avancement.progres(68 + 18 * k / nb, f"écran {k}/{nb}"))
    etape("montage", 68, montage_)

    # ---------- 6. contrôle 4/4 : la vidéo finie (boucle jusqu'à zéro problème ; le tour en cours est gardé)
    def controle_final():
        # 4 tours au plus (amélioration 13 du 25/11 : la vidéo CAN avait fait 12 tours, 56 min) ; à partir du 2e tour, l'IA
        # ne regarde de nouveau que les écrans REFAITS (les autres ont déjà été jugés bons)
        a_revoir = None
        for tour in range(E.get("tour_video", 0), 4):
            E["tour_video"] = tour
            if tour >= 2 and time.time() - E["t0"] > 70 * 60:  # limite de temps : la vidéo arrive sur le site, « à vérifier »
                journal(f"  contrôle de la vidéo finie arrêté après {tour} tours (plus de 70 min de fabrication) : "
                        "les problèmes restants sont signalés dans le bulletin")
                return
            avancement.etape(pre + f"Contrôle 4/4 : la vidéo finie (tour {tour + 1})", min(94, 87 + tour))
            fautifs = controle.controle_video(fichier, script, dossier, B, journal, leger=simulation(), sans_ia=secours,
                                              seulement=a_revoir)
            trouves_ici = {(("voix" if a == "voix" else "video"), (None if i is None else controle.uid(script, i)))
                           for i, (_, a) in fautifs.items()}
            for l in B.ouverts():                             # revérifié : passage réglé
                if l["niveau"] in ("video", "voix") and (l["niveau"], l["ecran"]) not in trouves_ici:
                    B.fermer(l["niveau"], l["ecran"])
            if not fautifs:
                return
            journal(f"  vidéo finie (tour {tour + 1}) : {len(fautifs)} passage(s) à corriger : "
                    + ", ".join(f"{'vidéo' if i is None else f'écran {i + 1}'} ({p})" for i, (p, _) in fautifs.items()))
            controle.corriger_ecrans(script, fautifs, dossier, B, journal, E.get("nom_voix", R["video"]["voix"]),
                                     E.get("vitesse", 0.8), E["articles"])
            avant = {p.get("uid"): p.get("_sig") for p in script["phrases"]}
            E["duree"] = montage.monter(script, dossier, fichier)
            a_revoir = {i for i, p in enumerate(script["phrases"]) if avant.get(p.get("uid")) != p.get("_sig")}
            journal(f"  {script.get('_ecrans_refaits', 0)} écran(s) refait(s), le reste de la vidéo est inchangé")
    etape("controle_final", 87, controle_final)

    # ---------- 6 bis. AUCUN extrait perdu (exigence de l'auteur du 25/11) : remis à l'écran, vidéo remontée, revérifiée
    def extraits():
        for essai in range(2):
            if not controle.reposer_extraits(script, journal):
                break
            E["duree"] = montage.monter(script, dossier, fichier)
        perdus = controle.extraits_perdus(script)
        E["extraits_perdus"] = len(perdus)
        if perdus:
            B.ouvrir("video", f"{len(perdus)} extrait(s) de l'événement perdu(s) : " + ", ".join("@" + str(m.get("compte")) for m in perdus),
                     None, "grave")
        else:
            B.fermer("video", None)
    if not simulation():
        etape("extraits", 93, extraits)

    # ---------- 6 ter. RÈGLES vérifiées sur la vidéo entière (demande de l'auteur du 25/11) : seuls les passages fautifs
    # sont corrigés (voix refaite pour les seules phrases changées, seuls les écrans changés remontés), puis TOUT est
    # revérifié pour qu'une correction ne casse rien ailleurs ; il reste une règle cassée = « à vérifier », jamais publiée
    def regles_():
        def etat_regles():
            tags = ([f"#{script['serie_hashtag']}"] if script.get("serie_hashtag") else []) + ecrire.hashtags(script, sujet, R)
            return regles.verifier(script, E["articles"], tags, E.get("duree"), script.get("description"), script.get("question"))
        pbs = etat_regles()
        for tour in range(2):
            if not pbs:
                break
            journal(f"  règles (tour {tour + 1}) : " + " ; ".join(x["message"] for x in pbs))
            textes, images_, champs = regles.reparer(script, pbs, E["articles"], R, journal, sujet)
            if textes:                                       # voix refaite pour ces phrases SEULEMENT (mémoire des voix)
                a_dire = [script["phrases"][i] for i in sorted(textes)]
                if simulation():
                    for q in a_dire:
                        q["duree"], q["mots"] = voix_simulation(q, q["son"])
                else:
                    V.preparer(a_dire, E.get("nom_voix", R["video"]["voix"]), E.get("vitesse", 0.8), journal,
                               memoire=os.path.join(dossier, "memoire_voix"))
            if textes or images_:
                E["duree"] = montage.monter(script, dossier, fichier)
                journal(f"  {script.get('_ecrans_refaits', 0)} écran(s) refait(s) seulement")
            pbs = etat_regles()
        # problème ouvert sur une phrase qui n'existe plus (retirée par une règle) : clos (vidéo CAN r14 du 25/11 : phrase
        # absurde retirée, mais son problème de voix restait ouvert et bloquait la vidéo)
        uids = {q.get("uid") for q in script["phrases"]}
        for l in B.lignes:
            if not l["corrige"] and l.get("ecran") is not None and l["ecran"] not in uids:
                l.update(corrige=True, solution="phrase retirée")
        E["regles"] = [x["message"] for x in pbs]
        for x in pbs:
            B.ouvrir("regles", x["message"], None if x.get("ecran") is None else controle.uid(script, x["ecran"]), "grave")
        if not pbs:
            journal("  ✅ toutes les règles sont respectées")
    etape("regles", 94, regles_)
    bulletin = B.resume()
    journal(f"  bulletin : note {bulletin['note']}/100, {bulletin['corriges']} correction(s), "
            f"{bulletin['restants']} problème(s) restant(s), {len(bulletin['sautes'])} contrôle(s) non fait(s)")

    # ---------- 7. rangement (Release GitHub = adresse publique pour Buffer)
    def rangement():
        os.makedirs(MINIATURES, exist_ok=True)
        montage.miniature(fichier, os.path.join(MINIATURES, f"{vid}.jpg"))
        try:                                                  # tout le travail, pour pouvoir REFAIRE en corrigeant
            travail = [refaire.archiver(script, E["articles"], B.resume(), dossier, vid)]
        except Exception as e:
            journal(f"  travail non archivé ({str(e)[:80]}) : « refaire » repartira de zéro")
            travail = []
        E["url"] = depot.publier_release(f"v-{vid}", script["titre"], [fichier] + travail)
    etape("rangement", 95, rangement)

    mode = R["publication"]["mode"]
    articles_ = E["articles"]
    return dict(id=vid, tag=f"v-{vid}", url=E["url"], titre=script["titre"], accroche=script.get("accroche", ""),
                sujet_id=sujet["id"], sujet=sujet["titre"], buzz={k: sujet.get(k) for k in ("vues", "jaime", "commentaires", "score")},
                description=montage.affichable(script.get("description", "")), question=montage.affichable(script.get("question", "")),
                hashtags=([f"#{script['serie_hashtag']}"] if script.get("serie_hashtag") else []) + ecrire.hashtags(script, sujet, R), duree=round(E["duree"], 1),
                sources=[dict(media=a["media"], titre=a["titre"], lien=a["lien"]) for a in articles_],
                verification=script.get("verification"), verifie=script.get("verifie", False),
                credits=sorted({p["media"]["credit"] for p in script["phrases"] if p.get("media")}),
                extraits_perdus=E.get("extraits_perdus", 0), regles_non_respectees=E.get("regles", []),
                ecrans_illustres=controle.part_illustree(script)[0], ecrans_total=controle.part_illustree(script)[1], format=format_, voix=script.get("voix_utilisee", ""), lieu=script.get("lieu", ""),
                humeur=script.get("humeur", ""), categorie=sujet.get("categorie") or script.get("categorie") or "actualite", texte=[p["ecrit"] for p in script["phrases"]],
                essai=simulation(), cree_le=iso(), ia_quotas={k: dict(v) for k, v in ia.QUOTAS.items()}, fabrication_s=round(time.time() - E["t0"]), controles=bulletin,
                reprises=E.get("reprises", 0), preuves=preuves_licences(script), couverture_ms=couverture_ms(script),
                durees=E.get("durees", {}), refaite=E.get("refaite"),
                statut="a_verifier" if bulletin["graves_restants"] else
                       "a_publier" if (mode == "auto" and script.get("verifie")) else "nouvelle")


def scenes_de(ph, mini=5.0, maxi=10.0):
    """Phrases regroupées en SCÈNES de 5 à 10 s (durée estimée à 3,5 mots/s) : [[0, 1], [2], [3, 4], …] (sans la question
    finale). Une phrase seule plus longue que 10 s reste seule."""
    scenes, cur, t = [], [], 0.0
    for i, p in enumerate(ph[:-1]):
        d = len(re.findall(r"\w+", p.get("voix") or p.get("ecrit") or "")) / 3.5 + 0.18
        if cur and (t >= mini or t + d > maxi):
            scenes.append(cur); cur, t = [], 0.0
        cur.append(i); t += d
    if cur:
        scenes.append(cur)
    return scenes


def serie_de(format_):
    """Série récurrente du jour (heure de Paris) si le format correspond : (format, étiquette, hashtag) ou None."""
    from .publication_auto import SERIES
    s = SERIES.get(maintenant().weekday())
    return s if s and s[0] == format_ and reglages()["creation"].get("series", True) else None


def _duree_estimee(p):
    return len(re.findall(r"\w+", p.get("voix") or p.get("ecrit") or "")) / 3.5 + 0.18


def placer_citations(script, scenes, sujet, dossier, deja, journal, R, E, format_):
    """Courtes citations des vidéos d'origine (voir robot/citations.py) : 4 ou 5 extraits de 10 à 15 s, un par vidéo
    d'origine, répartis dans la vidéo (le 1er sur l'accroche). Une scène trop courte est prolongée par la suivante pour
    montrer au moins 10 s d'affilée (sans dépasser la longueur de l'extrait)."""
    if E.get("citations_faites") or simulation() or format_ in MULTI or not R["video"].get("citations", True):
        return
    E["citations_faites"] = True
    ph = script["phrases"]
    nombre = int(R["video"].get("citations_nombre", 12))
    libres = [k for k, sc in enumerate(scenes) if "media" not in ph[sc[0]]]
    if not libres:
        return
    # (vidéo refaite) les extraits de l'ancienne version qui ne sont plus montrés sont REPOSÉS d'abord sur les phrases
    # nouvelles (vidéo CAN r10 du 25/11 : texte refait, extraits BBC / franceinfo perdus, remplacés par des timbres)
    montres = {str((p.get("media") or {}).get("id", "")).split("-suite")[0] for p in ph if (p.get("media") or {}).get("citation")}
    reserve = [m for m in script.pop("_citations_reserve", []) if m.get("chemin") and os.path.exists(m["chemin"])
               and str(m.get("id")) not in montres]
    # le MAXIMUM d'extraits vidéo de l'événement (demande de l'auteur du 25/11), puis des images fixes de l'événement
    # (tirées des vidéos d'origine et des articles de presse) pour meubler les scènes restantes
    extraits = reserve if len(reserve) >= len(libres) else reserve + citations.extraits(
        sujet, dossier, journal, min(nombre, len(libres)) - len([m for m in reserve if m["type"] == "video"]),
        deja | {m["id"] for m in reserve} | montres, photos=int(R["video"].get("citations_photos", 6)))
    if reserve:
        journal(f"  {len(reserve)} extrait(s) de l'ancienne version reposé(s) sur les phrases nouvelles")
    vids = [m for m in extraits if m["type"] == "video"]
    fixes = [m for m in extraits if m["type"] == "photo"]
    # ACCROCHE : l'extrait le mieux noté par l'IA (l'action, la foule, le moment fort) ouvre la vidéo (vidéo CAN r12 du
    # 25/11 : elle s'ouvrait sur un homme de dos sur une plage) ; les extraits d'un même compte sont espacés
    if vids:
        meilleur = max(vids, key=lambda m: m.get("note_ia") if m.get("note_ia") is not None else -1)
        vids.remove(meilleur)
        espaces, reste = [], vids[:]
        while reste:                                          # jamais deux extraits du même compte à la suite, si possible
            dernier = (espaces or [meilleur])[-1].get("compte")
            k = next((j for j, m in enumerate(reste) if m.get("compte") != dernier), 0)
            espaces.append(reste.pop(k))
        vids = [meilleur] + espaces
    if len(vids) < len(libres):
        fixes += citations.photos_presse(E.get("articles") or [], sujet, dossier, journal,
                                         maxi=max(0, len(libres) - len(vids) - len(fixes) + 2))
    if not vids and not fixes:
        journal("  aucune vidéo ni photo de l'événement trouvée (vidéos d'origine, articles)")
        return
    pas = max(1, len(libres) / len(vids)) if vids else 1
    choix_v = []
    for n in range(len(vids)):                                # extraits vidéo répartis dans toute la vidéo (le 1er en accroche)
        k = libres[min(len(libres) - 1, int(n * pas))]
        if k not in choix_v:
            choix_v.append(k)
    reste = [k for k in libres if k not in choix_v]
    choix_f = reste[:len(fixes)]                              # images fixes : les scènes restantes
    extraits = vids[:len(choix_v)] + fixes[:len(choix_f)]
    choix = choix_v + choix_f
    # tous les extraits trouvés sont NOTÉS : la fin de la fabrication vérifie qu'aucun n'a été perdu en route
    connus = {controle._base(m) for m in script.get("_citations_toutes") or []}
    script.setdefault("_citations_toutes", []).extend(dict(m, suite=False) for m in vids + fixes + reserve
                                                      if controle._base(m) not in connus)
    for m, k in zip(extraits, choix):
        sc = list(scenes[k])
        total = sum(_duree_estimee(ph[j]) for j in sc)
        suivante = scenes[k + 1] if k + 1 < len(scenes) and k + 1 not in choix else []
        if total < 10 and suivante and "media" not in ph[suivante[0]] and 1 not in suivante \
                and m["type"] == "video" and total + sum(_duree_estimee(ph[j]) for j in suivante) <= m.get("duree", 0):
            sc += suivante                                    # au moins 10 s d'affilée
        ph[sc[0]]["media"] = dict(m, reelle=True); ph[sc[0]]["_valide"] = True
        if m["type"] == "photo":
            continue                                          # une image FIXE ne couvre qu'une phrase (voir plus bas)
        for j in sc[1:]:
            ph[j]["media"] = dict(m, id=f"{m['id']}-suite{j}", suite=True, reelle=True); ph[j]["_valide"] = True
    # images fixes : une par phrase (vidéo des marées du 25/11 : la même photo sur 3 écrans de suite, 15 s figées) ; les
    # phrases restantes d'une scène photo prennent d'autres images fixes de l'événement, sinon la même photo continue
    restantes = [m for m in fixes if m not in extraits]
    for k in choix_f:
        for j in scenes[k][1:]:
            if "media" in ph[j]:
                continue
            if restantes:
                m = restantes.pop(0)
                ph[j]["media"] = dict(m, reelle=True); ph[j]["_valide"] = True; extraits.append(m)
            else:
                prec = ph[j - 1]["media"]
                ph[j]["media"] = dict(prec, id=f"{prec['id']}-suite{j}", suite=True); ph[j]["_valide"] = True
    journal(f"  {len(choix)} courte(s) citation(s) placée(s) (vidéos et images de l'événement) : "
            + ", ".join(m.get("bandeau") or f"@{m['compte']}" for m in extraits[:len(choix)]))


def accroche(script):
    """Accroche (2 premières secondes) : si le 1er écran n'a pas de vraie vidéo, il prend celle d'un autre écran (échange)."""
    ph = script["phrases"]
    m0 = ph[0].get("media") or {}
    if m0.get("type") == "video" and m0.get("reelle"):
        return
    for k in range(2, len(ph) - 1):                           # l'écran 2 est souvent la carte : on ne la déplace pas
        mk = ph[k].get("media") or {}
        if mk.get("type") == "video" and (mk.get("reelle") or not m0):
            ph[0]["media"], ph[k]["media"] = mk, (m0 or None)
            return


def couverture_ms(script):
    """Instant de la couverture TikTok : le 1er écran avec une vraie image ET un gros titre (sinon le début)."""
    debuts, _ = montage.debuts_et_total(script["phrases"])
    for i, p in enumerate(script["phrases"][:-1]):
        if p.get("media") and (p["media"].get("type") in ("video", "photo")) and p.get("ecran"):
            return int((debuts[i] + 0.8) * 1000)
    return 800


def preuves_licences(script):
    """Preuve de chaque vraie vidéo ou image reprise (page d'origine, licence, auteur, date) : à montrer en cas de réclamation."""
    out, vus = [], set()
    for i, p in enumerate(script["phrases"]):
        m = p.get("media") or {}
        if m.get("type") not in ("video", "photo") or m.get("presse"):
            continue
        cle = str(m.get("id", "")).rsplit("-bis", 1)[0]
        page = m.get("page") or m.get("url") or ""
        if (page, cle) in vus:
            continue
        vus.add((page, cle))
        out.append(dict(ecran=i + 1, page=page, licence=m.get("licence", ""), auteur=m.get("auteur", ""),
                        titre=m.get("titre_source", ""), credit=m.get("credit", ""), releve_le=iso()))
    return out


ETAPES = {"articles": "Lecture des articles de presse", "ecriture": "Écriture du texte",
          "texte": "Contrôle 1/4 : vérification des faits et du texte", "voix": "Voix et calage des mots (contrôle 2/4)",
          "images": "Recherche des vraies images", "controle_images": "Contrôle 3/4 : les images", "montage": "Montage",
          "controle_final": "Contrôle 4/4 : la vidéo finie", "extraits": "Contrôle : aucun extrait de l'événement perdu",
          "regles": "Contrôle : toutes les règles de la vidéo",
          "rangement": "Rangement de la vidéo"}


def creer(nombre=1, sujet_id="", libre="", journal=print, format_="buzz", attendre=None):
    R = reglages()
    sujets = choisir_sujets(nombre, sujet_id, libre, journal, format_)
    if not sujets:
        noter("🎬 Aucun sujet à traiter (onglet Buzz vide).", "erreur")
        return []
    faites, essais, traites, maigres = [], 0, set(), []
    a_faire = [(s, None) for s in sujets]
    while a_faire:
        s, etat = a_faire.pop(0)
        if len(faites) >= nombre or essais >= nombre + 3:
            break
        traites.add(s["id"])
        journal(f"▶ Sujet : {s['titre']}")
        if etat is None:
            etat = {}
            if not (s.get("libre") or format_ in MULTI or simulation()):
                # Seulement des sujets SANS problème (demande de l'auteur du 24/11) : au moins 3 médias différents avec un
                # vrai article, réunis dans une seule vidéo. Un sujet trop maigre n'est pas commencé : sujet suivant.
                arts = sources.chercher_large(s["titre"], s.get("mots_cles") or [], s.get("videos") or [], journal,
                                              mots_en=s.get("mots_cles_en") or [])
                nb, car = sources.richesse(arts)
                if not sources.assez_riche(arts):
                    journal(f"  ✗ sujet écarté : {nb} média(s), {car} caractères d'articles (il en faut 3 et 5 000)")
                    maigres.append((nb, car, s, arts))
                    _marquer_sujet(s["id"], "sans_source")
                    if not a_faire and not faites and essais == 0:   # aucun sujet assez riche : le plus riche quand même
                        nb, car, s2, arts2 = max(maigres, key=lambda x: (x[0], x[1]))
                        journal(f"  aucun sujet assez riche : « {s2['titre']} » (le plus riche) est traité quand même")
                        a_faire.append((s2, {"articles": arts2}))
                    continue
                journal(f"  ✓ {nb} médias différents, {car} caractères d'articles : réunis dans une seule vidéo")
                etat["articles"] = arts
        essais += 1
        v = None
        for tentative in range(4):                            # une vidéo commencée va au bout : reprise à l'étape ratée
            secours = tentative == 3
            try:
                v = fabriquer(s, R, len(faites) + 1, nombre, journal, format_, secours=secours, etat=etat, attendre=attendre)
                break
            except Exception as e:
                traceback.print_exc()
                if tentative < 3:
                    etat["reprises"] = etat.get("reprises", 0) + 1
                    noter(f"🔁 « {s['titre']} » : étape ratée ({str(e)[:140]}) — reprise {tentative + 2}/4 à cette étape"
                          + (" en mode secours" if tentative == 2 else ""), "attention")
                    time.sleep(20)
        if v is None:
            avancement.finir(False, "Vidéo impossible après 4 tentatives")
            noter(f"❌ « {s['titre']} » : vidéo impossible après 4 tentatives (sujet suivant)", "erreur")
            _marquer_sujet(s["id"], "echec")
            continue

        def appliquer(v=v, s=s):
            file = lire("file.json") or {"videos": []}
            file["videos"].insert(0, v)
            ecrire_donnees("file.json", file)
            _marquer_sujet(s["id"], "utilise", v["id"], ecrire_seul=True)
            noter(f"🎬 Nouvelle vidéo « {v['titre']} » ({v['duree']:.0f} s, {v['ecrans_illustres']} écrans illustrés)"
                  + (" — à publier automatiquement" if v["statut"] == "a_publier" else " — à regarder puis cocher « À publier »"))
        depot.enregistrer(appliquer, f"Nouvelle vidéo : {v['titre']}")
        avancement.finir(True, f"Vidéo prête : {v['titre']}")
        reparer_tout_de_suite(v, journal)
        faites.append(v)
        if depot.en_ligne():                                  # sur GitHub : place libérée (la vidéo est dans la Release)
            shutil.rmtree(os.path.join(SORTIE, v["id"]), ignore_errors=True)
    rendre = {x["id"] for x in sujets} - traites               # réserves pas utilisées : rendues aux autres séries
    if rendre and not libre.strip():
        def liberer():
            B = lire("buzz.json") or {"sujets": []}
            for x in B.get("sujets", []):
                if x["id"] in rendre and x.get("statut") == "en_cours":
                    x["statut"] = "nouveau"; x.pop("reserve_le", None)
            ecrire_donnees("buzz.json", B)
        depot.enregistrer(liberer, "Sujets de réserve rendus")
    return faites


def reparer_tout_de_suite(v, journal=print):
    """Vidéo avec trop peu de vraies images : refaite TOUT DE SUITE en corrigeant (autres images), sans attendre la nuit."""
    if v.get("essai") or not depot.en_ligne() or (v.get("ecrans_illustres") or 0) >= 0.7 * (v.get("ecrans_total") or 1):
        return
    remarque = f"Réparation automatique : seulement {v.get('ecrans_illustres')} écran(s) illustré(s) sur {v.get('ecrans_total')}"
    r = subprocess.run(["gh", "workflow", "run", "creer.yml", "-f", f"refaire={v['id']}", "-f", "etape=images",
                        "-f", f"remarque={remarque}", "-f", "origine=reparation"], capture_output=True, text=True)
    journal(f"  🔧 {remarque} : la vidéo est refaite tout de suite" if r.returncode == 0 else
            f"  réparation non lancée ({r.stderr[-120:]}) : la santé du robot la refera cette nuit")


def refaire_video(vid, etape="auto", remarque="", journal=print):
    """Refait la vidéo `vid` EN CORRIGEANT ce qui n'allait pas (robot/refaire.py) ; la nouvelle remplace l'ancienne."""
    import re
    R = reglages()
    file = lire("file.json") or {"videos": []}
    v = next((x for x in file["videos"] if x["id"] == vid), None)
    if not v:
        noter(f"🔁 Vidéo {vid} introuvable : rien à refaire.", "erreur")
        return None
    base = re.sub(r"-r\d+$", "", vid)
    n = 1 + max([int(m.group(1)) for x in file["videos"] for m in [re.match(re.escape(base) + r"-r(\d+)$", x["id"])] if m] or [0])
    v["_nouvel_id"] = f"{base}-r{n}"
    sujet = next((s for s in (lire("buzz.json") or {}).get("sujets") or [] if s["id"] == v.get("sujet_id")), None) or \
        dict(id=v.get("sujet_id") or base, titre=v.get("sujet") or v["titre"], resume="", mots_cles=[], videos=[])
    dossier = os.path.join(SORTIE, v["_nouvel_id"])
    avancement.demarrer(v["_nouvel_id"], "video", f"On refait : {v['titre']}")
    try:
        etat, etape = refaire.preparer(v, sujet, etape, remarque, dossier, depot.depot(), R, journal)
    except urllib.error.HTTPError as e:                       # vidéo de l'ancien code : pas d'archive de travail
        if e.code != 404:
            raise
        journal("  pas d'archive de travail (vidéo faite avant le 24/11 au soir) : le sujet est refait en entier")
        etat, etape = {}, "tout"
    nv = None
    for tentative in range(4):                                # comme une création : reprise à l'étape ratée
        try:
            nv = fabriquer(sujet, R, 1, 1, journal, v.get("format") or "buzz", secours=tentative == 3, etat=etat)
            break
        except Exception as e:
            traceback.print_exc()
            if tentative < 3:
                noter(f"🔁 Refaire « {v['titre']} » : étape ratée ({str(e)[:120]}) — reprise {tentative + 2}/4", "attention")
                time.sleep(20)
    if nv is None:
        avancement.finir(False, "Vidéo non refaite après 4 tentatives")
        noter(f"❌ « {v['titre']} » n'a pas pu être refaite (l'ancienne est gardée).", "erreur")
        return None
    nv["refaite_de"] = vid

    def appliquer():
        F = lire("file.json") or {"videos": []}
        k = next((i for i, x in enumerate(F["videos"]) if x["id"] == vid), 0)
        F["videos"] = [x for x in F["videos"] if x["id"] != vid]
        F["videos"].insert(k, nv)
        ecrire_donnees("file.json", F)
        vieille = os.path.join(MINIATURES, f"{vid}.jpg")
        if os.path.exists(vieille):
            os.remove(vieille)
        noter(f"🔁 « {nv['titre']} » refaite ({etape}) : note {nv['controles']['note']}/100"
              + (f", corrige : « {remarque} »" if remarque else "") + " — l'ancienne version est remplacée")
    depot.enregistrer(appliquer, f"Vidéo refaite : {nv['titre']}")
    depot.supprimer_release(v.get("tag"))
    avancement.finir(True, f"Vidéo refaite : {nv['titre']}")
    return nv


def _marquer_sujet(sid, statut, video_id=None, ecrire_seul=False):
    def appliquer():
        B = lire("buzz.json") or {"sujets": []}
        for s in B.get("sujets", []):
            if s["id"] == sid:
                s["statut"] = statut
                if video_id:
                    s["video_id"] = video_id
        ecrire_donnees("buzz.json", B)
    if ecrire_seul:
        appliquer()
    else:
        depot.enregistrer(appliquer, f"Sujet {statut}")


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--nombre", type=int, default=1)
    a.add_argument("--sujet", default="")
    a.add_argument("--libre", default="")
    a.add_argument("--format", default="buzz", choices=("buzz", "vrai_faux", "semaine", "chiffre", "monde60", "region"))
    a.add_argument("--auto", action="store_true", help="création automatique : seulement si activée dans les réglages")
    a.add_argument("--plan", action="store_true", help="répartir une série entre plusieurs machines (sortie GitHub « plan »)")
    a.add_argument("--paralleles", type=int, default=0)
    a.add_argument("--refaire", default="", help="identifiant de la vidéo à refaire en corrigeant")
    a.add_argument("--etape", default="auto", help="auto, texte, voix, images ou tout")
    a.add_argument("--remarque", default="", help="ce qui ne va pas (écrit par l'auteur)")
    a.add_argument("--origine", default="")
    o = a.parse_args()
    if o.plan and depot.en_ligne() and not simulation():
        # VÉRIFICATION DES CRÉDITS DES IA AVANT DE CRÉER (demande de l'auteur du 25/11) : pas assez d'IA gratuites
        # disponibles = la création est mise en attente (la garde la lancera d'elle-même), aucune machine ne démarre
        from . import credits
        n = 1 if o.refaire else max(1, min(10, o.nombre))
        en_cours = max(0, credits.en_fabrication() - 1)          # (- 1 : cette tâche-ci)
        ok, resume, _ = credits.verifier(n, en_cours)
        libres = credits.places(en_cours) if ok else 0
        if libres < n:                                         # ce qui ne peut pas partir attend (une vidéo à la fois)
            demande = {k: v for k, v in dict(sujet=o.sujet, libre=o.libre, format=o.format, refaire=o.refaire,
                                             etape=o.etape, remarque=o.remarque, origine=o.origine or "attente").items() if v}
            for _ in range(n - libres):
                credits.mettre_en_attente(dict(demande, nombre="1"), resume.lstrip("⏸️ "))
            if not libres:
                if os.environ.get("GITHUB_OUTPUT"):
                    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                        f.write("plan=[]\nparalleles=1\n")
                return
            o.nombre = libres
    if o.refaire and o.plan:
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write('plan=[{"k": 1, "sujets": ""}]\nparalleles=1\n')
        return
    if o.refaire:
        if not refaire_video(o.refaire, o.etape, o.remarque):
            raise SystemExit(1)
        return
    if o.plan:
        import json
        n_par = max(1, min(5, o.paralleles or int(reglages()["creation"].get("paralleles", 5))))
        plan = planifier(max(1, min(10, o.nombre)), o.format, o.sujet, o.libre, n_par)
        print(f"Plan : {len(plan)} vidéo(s), {n_par} machine(s) en même temps : {plan}")
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                # toutes les machines démarrent (articles et texte préparés pendant l'attente) ; la file commune limite
                # la partie lourde à `n_par` vidéos en même temps
                f.write(f"plan={json.dumps(plan)}\nparalleles={min(10, max(n_par, len(plan)))}\n")
        return
    if o.auto and not reglages()["creation"].get("auto"):
        print("Création automatique coupée dans les réglages : rien à faire.")
        return
    limite = max(1, min(5, int(reglages()["creation"].get("paralleles", 5))))
    attendre = None if simulation() else (lambda: avancement.attendre_son_tour(limite))   # file commune, après le texte
    faites = creer(max(1, min(10, o.nombre)), o.sujet, o.libre, format_=o.format, attendre=attendre)
    if not faites:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
