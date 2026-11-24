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

from . import avancement, buzz, carte, depot, ecrire, images, montage, sources
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


def choisir_sujets(n, sujet_id="", libre="", journal=print, format_="buzz"):
    """Sujets à traiter, du meilleur au moins bon. Sans buzz mesuré : titres à la une de la presse."""
    if format_ == "semaine":
        return sujet_semaine(journal)
    if libre.strip():
        return [dict(id=buzz.identifiant(libre), titre=libre.strip()[:90], resume=libre.strip(), mots_cles=[], hashtags=[],
                     videos=[], libre=True)]
    B = lire("buzz.json") or {}
    sujets = B.get("sujets") or []
    if sujet_id:
        return [s for s in sujets if s["id"] == sujet_id][:1]
    frais = [s for s in sujets if s.get("statut", "nouveau") == "nouveau"]
    if frais:
        return frais[:n + 3]                               # quelques sujets en réserve si l'un n'a pas d'article
    journal("Aucun sujet du buzz disponible : titres à la une de la presse à la place")
    return [dict(id=buzz.identifiant(a["titre"]), titre=a["titre"], resume=a["resume"], mots_cles=[], hashtags=[], videos=[],
                 presse=True) for a in sources.a_la_une(journal=journal)][:n + 3]


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


def fabriquer(sujet, R, n=1, total=1, journal=print, format_="buzz"):
    """Une vidéo complète. Renvoie l'entrée de la liste (file.json) ou lève une exception."""
    vid = f"{maintenant():%Y%m%d-%H%M%S}"
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
    else:
        articles = sources.chercher(sujet["titre"], sujet.get("mots_cles") or [], journal=journal)
    if not simulation() and not articles:
        raise LookupError("aucun article de presse trouvé sur ce sujet")
    journal(f"  {len(articles)} article(s) : " + ", ".join(f"{a['media']} ({len(a.get('texte') or '')} car.)" for a in articles))
    if not simulation() and sum(len(a.get("texte") or "") for a in articles) < 1200:
        raise LookupError("pas assez d'articles complets pour vérifier les faits")
    journal("  images : " + ", ".join(f"{n} {'✓' if os.environ.get(c) else '✗ (pas de clé)'}"
                                     for n, c in (("Pexels", "PEXELS_API_KEY"), ("Pixabay", "PIXABAY_API_KEY")))
            + ", NASA ✓, Wikimedia ✓")

    avancement.etape(pre + "Écriture du texte", 12)
    script = script_simulation(sujet) if simulation() else ecrire.ecrire(sujet, articles, journal, format_)
    avancement.etape(pre + "Vérification des faits par une 2e IA", 22)
    if not simulation():
        script = ecrire.verifier(script, articles, journal)
        if len(script["phrases"]) < 9:
            raise LookupError(f"seulement {len(script['phrases'])} phrases vérifiées : trop court pour une vidéo d'1 minute")

    avancement.etape(pre + "Voix et calage des mots", 30)
    nom_voix, vitesse = R["video"]["voix"], float(R["video"]["vitesse"])
    for i, p in enumerate(script["phrases"]):
        p["son"] = os.path.join(dossier, f"voix{i:02d}.wav")
    if simulation():
        for p in script["phrases"]:
            p["duree"], p["mots"] = voix_simulation(p, p["son"])
    else:
        script["voix_utilisee"] = V.preparer(script["phrases"], nom_voix, vitesse, journal,
                                             suivi=lambda k, n: avancement.progres(30 + 20 * k / n, f"phrase {k}/{n}"))
    parole = sum(p["duree"] for p in script["phrases"]) + montage.PAUSE * len(script["phrases"]) + montage.FIN
    if parole < 60:
        journal(f"  ⚠️ vidéo de {parole:.0f} s : moins d'1 minute (TikTok ne paie qu'au-delà)")

    avancement.etape(pre + "Recherche des vraies images libres", 52)
    deja = set()
    for i, p in enumerate(script["phrases"][:-1]):
        p["media"] = None if simulation() else images.trouver(p["image"], dossier, i, deja, journal)
        avancement.progres(52 + 15 * (i + 1) / len(script["phrases"]))
    script["phrases"][-1]["media"] = None
    script["musique"] = R["video"].get("musique", True); script["bruitages"] = R["video"].get("bruitages", True)
    script["transitions"] = R["video"].get("transitions", False)
    if not simulation() and R["video"].get("carte", True) and format_ != "semaine" and script.get("lieu") and len(script["phrases"]) > 3:
        lieu = carte.trouver_lieu(script["lieu"], script.get("coordonnees"))
        if lieu:                                              # 2e écran : la carte qui zoome sur le lieu de l'actu
            script["phrases"][1]["media"] = dict(type="carte", credit="Carte : Natural Earth, OpenStreetMap", **lieu)
            if not script["phrases"][1].get("ecran"):
                script["phrases"][1]["ecran"] = str(script["lieu"]).split(",")[0][:22]
            journal(f"  carte : {lieu['nom']}")
    trouves = sum(1 for p in script["phrases"] if p.get("media"))
    journal(f"  images : {trouves} écran(s) illustré(s) sur {len(script['phrases'])}")

    avancement.etape(pre + "Montage", 68)
    fichier = os.path.join(dossier, f"buzz-{vid}.mp4")
    duree = montage.monter(script, dossier, fichier,
                           suivi=lambda k, nb: avancement.progres(68 + 25 * k / nb, f"écran {k}/{nb}"))

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
                essai=simulation(), cree_le=iso(), fabrication_s=round(time.time() - t0),
                statut="a_publier" if (mode == "auto" and script.get("verifie")) else "nouvelle")


def creer(nombre=1, sujet_id="", libre="", journal=print, format_="buzz"):
    R = reglages()
    sujets = choisir_sujets(nombre, sujet_id, libre, journal, format_)
    if not sujets:
        noter("🎬 Aucun sujet à traiter (onglet Buzz vide).", "erreur")
        return []
    faites, essais = [], 0
    for s in sujets:
        if len(faites) >= nombre or essais >= nombre + 3:
            break
        essais += 1
        journal(f"▶ Sujet : {s['titre']}")
        try:
            v = fabriquer(s, R, len(faites) + 1, nombre, journal, format_)
        except Exception as e:
            traceback.print_exc()
            avancement.finir(False, f"Sujet abandonné : {str(e)[:120]}")
            noter(f"⚠️ « {s['titre']} » abandonné : {str(e)[:160]}", "erreur")
            _marquer_sujet(s["id"], "sans_source" if isinstance(e, LookupError) else "echec")
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
    o = a.parse_args()
    if o.auto and not reglages()["creation"].get("auto"):
        print("Création automatique coupée dans les réglages : rien à faire.")
        return
    faites = creer(max(1, min(10, o.nombre)), o.sujet, o.libre, format_=o.format)
    if not faites:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
