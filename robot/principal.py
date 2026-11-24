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
import shutil
import subprocess
import time
import traceback

from . import avancement, buzz, carte, controle, depot, ecrire, ia, images, montage, sources
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
    if libre.strip() or sujet or format_ == "semaine":
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
    if libre.strip():
        return [dict(id=buzz.identifiant(libre), titre=libre.strip()[:90], resume=libre.strip(), mots_cles=[], hashtags=[],
                     videos=[], libre=True)]
    B = lire("buzz.json") or {}
    sujets = B.get("sujets") or []
    if sujet_id:                                          # un ou plusieurs sujets imposés (« id1,id2 » : réserves d'une machine)
        ids = [x for x in sujet_id.split(",") if x]
        return [s for i in ids for s in sujets if s["id"] == i]
    frais = [s for s in sujets if libre_pour_moi(s)]
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
        ("Le robot vérifie que le montage fonctionne.", "MONTAGE"), ("Les sous-titres suivent la voix mot à mot.", "KARAOKÉ"),
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


def fabriquer(sujet, R, n=1, total=1, journal=print, format_="buzz", secours=False, etat=None):
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
                fonction()
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
            E["articles"] = sources.chercher_large(sujet["titre"], sujet.get("mots_cles") or [], sujet.get("videos") or [], journal)
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
        a_dire = [p for p in script["phrases"] if not p.get("mots") or not os.path.exists(p.get("son", ""))]
        for p in a_dire:
            p["son"] = os.path.join(dossier, f"voix{p['uid']:03d}.wav")
        if simulation():
            for p in a_dire:
                p["duree"], p["mots"] = voix_simulation(p, p["son"])
        elif a_dire:
            script["voix_utilisee"] = V.preparer(a_dire, E["nom_voix"], E["vitesse"], journal,
                                                 suivi=lambda k, nb: avancement.progres(30 + 20 * k / nb, f"phrase {k}/{nb}"))
        for i, p in enumerate(script["phrases"]):
            if p.get("_voix_defaut"):                         # repris par la boucle de la vidéo finie
                B.ouvrir("voix", p["_voix_defaut"], p["uid"])
    etape("voix", 30, voix)

    # ---------- 4. images : seules les phrases sans image cherchée
    def images_():
        deja = E.setdefault("deja", set())
        script["images_generiques"] = R["video"].get("images_generiques", False)
        if "clips" not in E:                                  # VRAIES vidéos du sujet (licence libre), avant tout le reste
            E["clips"] = [] if simulation() or format_ == "semaine" else \
                images.videos_du_sujet(sujet["titre"], sujet.get("mots_cles") or [], dossier, journal, ecrans=len(script["phrases"]))
        for i, p in enumerate(script["phrases"][:-1]):
            if "media" not in p and E["clips"]:
                p["media"] = E["clips"].pop(0); deja.add(p["media"]["id"])
        # Puis des vidéos libres de CHAQUE personne / lieu / objet cité (demande de l'auteur du 24/11 : des bouts de vraies
        # vidéos collés l'un après l'autre ; les photos ne servent qu'en dernier recours).
        if not simulation() and format_ != "semaine":
            entites = E.setdefault("entites_faites", [])
            restantes = [p for p in script["phrases"][:-1] if "media" not in p and p.get("entite")]
            for k, nom in enumerate(dict.fromkeys(p["entite"] for p in restantes)):
                if nom in entites or len(entites) >= 6:
                    continue
                besoin = [p for p in restantes if p["entite"] == nom and "media" not in p]
                clips = images.videos_du_sujet(nom, [], dossier, journal, maxi=1, ecrans=len(besoin),
                                               prefixe=f"entite{len(entites)}", deja=deja)
                entites.append(nom)
                for p in besoin:
                    if clips:
                        p["media"] = clips.pop(0); deja.add(p["media"]["id"])
            if "media" not in p:
                p["media"] = None if simulation() else images.trouver(
                    p["image"], dossier, p["uid"], deja, journal, script.get("theme_image", ""),
                    entite=p.get("entite", ""), generiques=script["images_generiques"])
                avancement.progres(52 + 10 * (i + 1) / len(script["phrases"]))
        script.setdefault("_reserve", []).extend(E["clips"]); E["clips"] = []   # passages de réserve pour le contrôle
        noms = [p.get("entite") for p in script["phrases"] if p.get("entite")]
        script["entite_sujet"] = max(set(noms), key=noms.count) if noms else ""
        if not E.get("presse_faite"):                         # « La presse en parle » : vrais titres sur des écrans sans image
            titres = [a for a in E["articles"] if a.get("titre") and a.get("media") and a["media"] not in
                      ("Google Actualités", "Wikipédia (contexte)", "Descriptions des vidéos TikTok virales", "Sujet du buzz")]
            libres = [i for i, p in enumerate(script["phrases"][:-1]) if not p.get("media") and i > 0][:min(3, len(titres))]
            for k, i in enumerate(libres):
                script["phrases"][i]["media"] = images.carte_presse(titres[k], os.path.join(dossier, f"presse{k}.png"))
            E["presse_faite"] = True
        script["phrases"][-1]["media"] = None
        script["musique"] = R["video"].get("musique", True); script["bruitages"] = R["video"].get("bruitages", True)
        script["transitions"] = R["video"].get("transitions", False)
        if not E.get("carte_faite"):
            lieu_cite = str(script.get("lieu") or "").split(",")[0].split("(")[0].strip()
            texte_articles = " ".join((a.get("texte") or "") + " " + a.get("titre", "") for a in E["articles"]).lower()
            if lieu_cite and lieu_cite.lower() not in texte_articles:
                journal(f"  carte écartée : « {lieu_cite} » n'est pas cité dans les articles")
                script["lieu"] = ""
            if not simulation() and R["video"].get("carte", True) and format_ != "semaine" and script.get("lieu") \
                    and len(script["phrases"]) > 3:
                lieu = carte.trouver_lieu(script["lieu"], script.get("coordonnees"))
                if lieu:                                      # 2e écran : la carte qui zoome sur le lieu de l'actu
                    script["phrases"][1]["media"] = dict(type="carte", credit="Carte : Natural Earth, OpenStreetMap", **lieu)
                    if not script["phrases"][1].get("ecran"):
                        script["phrases"][1]["ecran"] = str(script["lieu"]).split(",")[0][:22]
                    journal(f"  carte : {lieu['nom']}")
            E["carte_faite"] = True
    etape("images", 52, images_)

    def controle_images():
        if not simulation():
            controle.controle_images(script, dossier, B, journal, E.setdefault("deja", set()), sujet["titre"], sans_ia=secours)
    etape("controle_images", 62, controle_images)
    trouves = sum(1 for p in script["phrases"] if p.get("media"))

    # ---------- 5. montage (les écrans déjà fabriqués sont gardés)
    E["fichier"] = fichier = os.path.join(dossier, f"buzz-{vid}.mp4")
    def montage_():
        E["duree"] = montage.monter(script, dossier, fichier, suivi=lambda k, nb: avancement.progres(68 + 18 * k / nb, f"écran {k}/{nb}"))
    etape("montage", 68, montage_)

    # ---------- 6. contrôle 4/4 : la vidéo finie (boucle jusqu'à zéro problème ; le tour en cours est gardé)
    def controle_final():
        for tour in range(E.get("tour_video", 0), 12):
            E["tour_video"] = tour
            avancement.etape(pre + f"Contrôle 4/4 : la vidéo finie (tour {tour + 1})", min(94, 87 + tour))
            fautifs = controle.controle_video(fichier, script, dossier, B, journal, leger=simulation(), sans_ia=secours)
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
            E["duree"] = montage.monter(script, dossier, fichier)
            journal(f"  {script.get('_ecrans_refaits', 0)} écran(s) refait(s), le reste de la vidéo est inchangé")
    etape("controle_final", 87, controle_final)
    bulletin = B.resume()
    journal(f"  bulletin : note {bulletin['note']}/100, {bulletin['corriges']} correction(s), "
            f"{bulletin['restants']} problème(s) restant(s), {len(bulletin['sautes'])} contrôle(s) non fait(s)")

    # ---------- 7. rangement (Release GitHub = adresse publique pour Buffer)
    def rangement():
        os.makedirs(MINIATURES, exist_ok=True)
        montage.miniature(fichier, os.path.join(MINIATURES, f"{vid}.jpg"))
        E["url"] = depot.publier_release(f"v-{vid}", script["titre"], [fichier])
    etape("rangement", 95, rangement)

    mode = R["publication"]["mode"]
    articles_ = E["articles"]
    return dict(id=vid, tag=f"v-{vid}", url=E["url"], titre=script["titre"], accroche=script.get("accroche", ""),
                sujet_id=sujet["id"], sujet=sujet["titre"], buzz={k: sujet.get(k) for k in ("vues", "jaime", "commentaires", "score")},
                description=script.get("description", ""), question=script.get("question", ""),
                hashtags=ecrire.hashtags(script, sujet, R), duree=round(E["duree"], 1),
                sources=[dict(media=a["media"], titre=a["titre"], lien=a["lien"]) for a in articles_],
                verification=script.get("verification"), verifie=script.get("verifie", False),
                credits=sorted({p["media"]["credit"] for p in script["phrases"] if p.get("media")}),
                ecrans_illustres=trouves, format=format_, voix=script.get("voix_utilisee", ""), lieu=script.get("lieu", ""),
                humeur=script.get("humeur", ""), texte=[p["ecrit"] for p in script["phrases"]],
                essai=simulation(), cree_le=iso(), fabrication_s=round(time.time() - E["t0"]), controles=bulletin,
                reprises=E.get("reprises", 0),
                statut="a_verifier" if bulletin["graves_restants"] else
                       "a_publier" if (mode == "auto" and script.get("verifie")) else "nouvelle")


ETAPES = {"articles": "Lecture des articles de presse", "ecriture": "Écriture du texte",
          "texte": "Contrôle 1/4 : vérification des faits et du texte", "voix": "Voix et calage des mots (contrôle 2/4)",
          "images": "Recherche des vraies images", "controle_images": "Contrôle 3/4 : les images", "montage": "Montage",
          "controle_final": "Contrôle 4/4 : la vidéo finie", "rangement": "Rangement de la vidéo"}


def creer(nombre=1, sujet_id="", libre="", journal=print, format_="buzz"):
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
            if not (s.get("libre") or format_ == "semaine" or simulation()):
                # Seulement des sujets SANS problème (demande de l'auteur du 24/11) : au moins 3 médias différents avec un
                # vrai article, réunis dans une seule vidéo. Un sujet trop maigre n'est pas commencé : sujet suivant.
                arts = sources.chercher_large(s["titre"], s.get("mots_cles") or [], s.get("videos") or [], journal)
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
                v = fabriquer(s, R, len(faites) + 1, nombre, journal, format_, secours=secours, etat=etat)
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
    a.add_argument("--format", default="buzz", choices=("buzz", "vrai_faux", "semaine"))
    a.add_argument("--auto", action="store_true", help="création automatique : seulement si activée dans les réglages")
    a.add_argument("--plan", action="store_true", help="répartir une série entre plusieurs machines (sortie GitHub « plan »)")
    a.add_argument("--paralleles", type=int, default=0)
    o = a.parse_args()
    if o.plan:
        import json
        n_par = max(1, min(5, o.paralleles or int(reglages()["creation"].get("paralleles", 3))))
        plan = planifier(max(1, min(10, o.nombre)), o.format, o.sujet, o.libre, n_par)
        print(f"Plan : {len(plan)} vidéo(s), {n_par} machine(s) en même temps : {plan}")
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"plan={json.dumps(plan)}\nparalleles={n_par}\n")
        return
    if o.auto and not reglages()["creation"].get("auto"):
        print("Création automatique coupée dans les réglages : rien à faire.")
        return
    if not simulation():                                      # file d'attente commune à toutes les séries
        avancement.attendre_son_tour(max(1, min(5, int(reglages()["creation"].get("paralleles", 3)))))
    faites = creer(max(1, min(10, o.nombre)), o.sujet, o.libre, format_=o.format)
    if not faites:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
