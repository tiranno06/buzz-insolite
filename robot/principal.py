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


def fabriquer(sujet, R, n=1, total=1, journal=print, format_="buzz", secours=False):
    """Une vidéo complète. Renvoie l'entrée de la liste (file.json) ou lève une exception (creer la reprend alors sur le MÊME
    sujet). `secours` (dernière tentative) : voix Kokoro, pas de regard de l'IA sur les images, attente si les IA sont saturées."""
    vid = f"{maintenant():%Y%m%d-%H%M%S}" + (f"-{os.environ['MACHINE']}" if os.environ.get("MACHINE") else "")
    dossier = os.path.join(SORTIE, vid); os.makedirs(dossier, exist_ok=True)
    pre = f"Vidéo {n}/{total} — " if total > 1 else ""
    avancement.demarrer(vid, "video", sujet["titre"])
    t0 = time.time()

    avancement.etape(pre + "Lecture des articles de presse", 5, sujet["titre"])
    if simulation():
        articles = []
    elif sujet.get("parties"):                                # 3 actus de la semaine : 2 articles par sujet
        articles = [a for s in sujet["parties"] for a in sources.chercher(s["titre"], s.get("mots_cles") or [], maxi=2,
                                                                          journal=journal)]
    else:                                                     # jamais d'abandon : la recherche s'élargit si besoin
        articles = sources.chercher_large(sujet["titre"], sujet.get("mots_cles") or [], sujet.get("videos") or [], journal)
    journal(f"  {len(articles)} source(s) : " + ", ".join(f"{a['media']} ({len(a.get('texte') or '')} car.)" for a in articles))
    journal("  images : " + ", ".join(f"{n} {'✓' if os.environ.get(c) else '✗ (pas de clé)'}"
                                     for n, c in (("Pexels", "PEXELS_API_KEY"), ("Pixabay", "PIXABAY_API_KEY")))
            + ", NASA ✓, Wikimedia ✓")

    avancement.etape(pre + "Écriture du texte", 12)
    script = script_simulation(sujet) if simulation() else avec_ia(lambda: ecrire.ecrire(sujet, articles, journal, format_), journal)
    avancement.etape(pre + "Vérification des faits par une 2e IA", 22)
    B = controle.Bulletin()
    if not simulation():
        script = ecrire.verifier(script, articles, journal)
        avancement.etape(pre + "Contrôle 1/4 : le texte", 26)
        # Compléter / corriger puis revérifier SEULEMENT les phrases nouvelles ou réécrites (une phrase déjà vérifiée ne
        # repasse jamais : l'IA ne juge pas deux fois pareil), 3 allers-retours avant d'abandonner le sujet.
        for tour in range(5):
            if tour == 3 and not any(a["media"] == "Wikipédia (contexte)" for a in articles):
                articles += sources.contexte_wikipedia(sujet["titre"], journal=journal)    # plus de matière pour compléter
            deja_vues = {p["ecrit"] for p in script["phrases"]}
            script = controle.controle_texte(script, articles, B, journal)
            nouvelles = [i for i, p in enumerate(script["phrases"]) if p["ecrit"] not in deja_vues]
            if nouvelles:
                script = ecrire.verifier(script, articles, journal, seulement=nouvelles)
            if len(script["phrases"]) >= 9 and controle.duree_estimee(script["phrases"]) >= 62 and not controle.regles_texte(script):
                break
        if controle.duree_estimee(script["phrases"]) < 60:          # jamais d'abandon : signalé, la vidéo va au bout
            B.ouvrir("texte", f"texte un peu court (environ {controle.duree_estimee(script['phrases']):.0f} s)", None, "grave")

    avancement.etape(pre + "Voix et calage des mots", 30)
    nom_voix, vitesse = ("kokoro-ff_siwis" if secours else R["video"]["voix"]), float(R["video"]["vitesse"])
    for i, p in enumerate(script["phrases"]):
        p["son"] = os.path.join(dossier, f"voix{i:02d}.wav")
    if simulation():
        for p in script["phrases"]:
            p["duree"], p["mots"] = voix_simulation(p, p["son"])
    else:
        script["voix_utilisee"] = V.preparer(script["phrases"], nom_voix, vitesse, journal,
                                             suivi=lambda k, n: avancement.progres(30 + 20 * k / n, f"phrase {k}/{n}"))
        for i, p in enumerate(script["phrases"]):                    # contrôle 2/4 : la voix (déjà refaite une fois ;
            if p.get("_voix_defaut"):                                 # ce qui reste est repris par la boucle de la vidéo finie)
                B.ouvrir("voix", p["_voix_defaut"], controle.uid(script, i))
    parole = sum(p["duree"] for p in script["phrases"]) + montage.PAUSE * len(script["phrases"]) + montage.FIN
    if parole < 60:
        journal(f"  ⚠️ vidéo de {parole:.0f} s : moins d'1 minute (TikTok ne paie qu'au-delà)")

    avancement.etape(pre + "Recherche des vraies images libres", 52)
    deja = set()
    script["images_generiques"] = R["video"].get("images_generiques", False)
    for i, p in enumerate(script["phrases"][:-1]):
        p["media"] = None if simulation() else images.trouver(p["image"], dossier, i, deja, journal, script.get("theme_image", ""),
                                                              entite=p.get("entite", ""), generiques=script["images_generiques"])
    # « La presse en parle » : les vrais titres des articles (avec leur média), sur des écrans restés sans vraie image
    titres = [a for a in articles if a.get("titre") and a.get("media") and a["media"] != "Google Actualités"]
    for k, i in enumerate([i for i, p in enumerate(script["phrases"][:-1]) if not p.get("media") and i > 0][:min(3, len(titres))]):
        script["phrases"][i]["media"] = images.carte_presse(titres[k], os.path.join(dossier, f"presse{k}.png"))
        avancement.progres(52 + 15 * (i + 1) / len(script["phrases"]))
    script["phrases"][-1]["media"] = None
    script["musique"] = R["video"].get("musique", True); script["bruitages"] = R["video"].get("bruitages", True)
    script["transitions"] = R["video"].get("transitions", False)
    lieu_cite = str(script.get("lieu") or "").split(",")[0].split("(")[0].strip()
    texte_articles = " ".join((a.get("texte") or "") + " " + a.get("titre", "") for a in articles).lower()
    if lieu_cite and lieu_cite.lower() not in texte_articles:
        journal(f"  carte écartée : « {lieu_cite} » n'est pas cité dans les articles")
        script["lieu"] = ""
    if not simulation() and R["video"].get("carte", True) and format_ != "semaine" and script.get("lieu") and len(script["phrases"]) > 3:
        lieu = carte.trouver_lieu(script["lieu"], script.get("coordonnees"))
        if lieu:                                              # 2e écran : la carte qui zoome sur le lieu de l'actu
            script["phrases"][1]["media"] = dict(type="carte", credit="Carte : Natural Earth, OpenStreetMap", **lieu)
            if not script["phrases"][1].get("ecran"):
                script["phrases"][1]["ecran"] = str(script["lieu"]).split(",")[0][:22]
            journal(f"  carte : {lieu['nom']}")
    if not simulation():
        avancement.etape(pre + "Contrôle 3/4 : les images", 62)
        script = controle.controle_images(script, dossier, B, journal, deja, sujet["titre"], sans_ia=secours)
    trouves = sum(1 for p in script["phrases"] if p.get("media"))
    journal(f"  images : {trouves} écran(s) illustré(s) sur {len(script['phrases'])}")

    avancement.etape(pre + "Montage", 68)
    fichier = os.path.join(dossier, f"buzz-{vid}.mp4")
    duree = montage.monter(script, dossier, fichier,
                           suivi=lambda k, nb: avancement.progres(68 + 18 * k / nb, f"écran {k}/{nb}"))
    # Contrôle 4/4 : la vidéo finie. Tant qu'un problème est trouvé, seuls les passages fautifs sont corrigés (échelle de
    # solutions dont la dernière marche à coup sûr), puis TOUTE la vidéo est recontrôlée. Zéro problème restant exigé.
    for tour in range(12):
        avancement.etape(pre + f"Contrôle 4/4 : la vidéo finie (tour {tour + 1})", min(94, 87 + tour))
        fautifs = controle.controle_video(fichier, script, dossier, B, journal, leger=simulation(), sans_ia=secours)
        trouves_ici = {(("voix" if a == "voix" else "video"), (None if i is None else controle.uid(script, i)))
                       for i, (_, a) in fautifs.items()}
        for l in B.ouverts():                                         # revérifié : passage réglé
            if l["niveau"] in ("video", "voix") and (l["niveau"], l["ecran"]) not in trouves_ici:
                B.fermer(l["niveau"], l["ecran"])
        if not fautifs:
            break
        journal(f"  vidéo finie (tour {tour + 1}) : {len(fautifs)} passage(s) à corriger : "
                + ", ".join(f"{'vidéo' if i is None else f'écran {i + 1}'} ({p})" for i, (p, _) in fautifs.items()))
        controle.corriger_ecrans(script, fautifs, dossier, B, journal, nom_voix, vitesse, articles)
        duree = montage.monter(script, dossier, fichier)
        journal(f"  {script.get('_ecrans_refaits', 0)} écran(s) refait(s), le reste de la vidéo est inchangé")
    bulletin = B.resume()
    journal(f"  bulletin : note {bulletin['note']}/100, {bulletin['corriges']} correction(s), "
            f"{bulletin['graves_restants']} défaut(s) grave(s) restant(s)")

    avancement.etape(pre + "Rangement de la vidéo", 95)
    os.makedirs(MINIATURES, exist_ok=True)
    montage.miniature(fichier, os.path.join(MINIATURES, f"{vid}.jpg"))
    tag = f"v-{vid}"
    url = depot.publier_release(tag, script["titre"], [fichier])
    mode = R["publication"]["mode"]
    return dict(id=vid, tag=tag, url=url, titre=script["titre"], accroche=script.get("accroche", ""),
                sujet_id=sujet["id"], sujet=sujet["titre"], buzz={k: sujet.get(k) for k in ("vues", "jaime", "commentaires", "score")},
                description=script.get("description", ""), question=script.get("question", ""),
                hashtags=ecrire.hashtags(script, sujet, R), duree=round(duree, 1),
                sources=[dict(media=a["media"], titre=a["titre"], lien=a["lien"]) for a in articles],
                verification=script.get("verification"), verifie=script.get("verifie", False),
                credits=sorted({p["media"]["credit"] for p in script["phrases"] if p.get("media")}),
                ecrans_illustres=trouves, format=format_, voix=script.get("voix_utilisee", ""), lieu=script.get("lieu", ""), humeur=script.get("humeur", ""), texte=[p["ecrit"] for p in script["phrases"]],
                essai=simulation(), cree_le=iso(), fabrication_s=round(time.time() - t0), controles=bulletin,
                statut="a_verifier" if bulletin["graves_restants"] else
                       "a_publier" if (mode == "auto" and script.get("verifie")) else "nouvelle")


def creer(nombre=1, sujet_id="", libre="", journal=print, format_="buzz"):
    R = reglages()
    sujets = choisir_sujets(nombre, sujet_id, libre, journal, format_)
    if not sujets:
        noter("🎬 Aucun sujet à traiter (onglet Buzz vide).", "erreur")
        return []
    faites, essais, traites = [], 0, set()
    for s in sujets:
        if len(faites) >= nombre or essais >= nombre + 3:
            break
        essais += 1; traites.add(s["id"])
        journal(f"▶ Sujet : {s['titre']}")
        v = None
        for tentative in range(4):                            # une vidéo commencée va au bout : reprise sur le MÊME sujet
            secours = tentative == 3
            try:
                v = fabriquer(s, R, len(faites) + 1, nombre, journal, format_, secours=secours)
                break
            except Exception as e:
                traceback.print_exc()
                if tentative < 3:
                    noter(f"🔁 « {s['titre']} » : étape ratée ({str(e)[:140]}) — reprise {tentative + 2}/4"
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
