"""Équipe de contrôle par plusieurs IA (demande de l'auteur du 27/11 : « plusieurs contrôles et garde-fous, un quadruple
contrôle, toute une équipe d'agents IA »). Chaque agent est une IA DIFFÉRENTE de celle qui a fait le travail qu'il juge
(quand plusieurs fournisseurs gratuits répondent), comme dans une rédaction où l'on ne relit jamais son propre texte.

L'équipe complète d'une vidéo :
  1. le rédacteur (ecrire.ecrire) écrit ;
  2. le vérificateur des faits (ecrire.verifier, autre fournisseur) corrige ce qui n'est pas dans les articles ;
  3. le RÉALISATEUR CRITIQUE (ici, `critique_storyboard`) relit la reconstitution 3D AVANT le rendu : chronologie, physique
     (un camion ne vole pas), objets absents, personnes qui n'étaient pas sur place, étapes oubliées ;
  4. le contrôle de la voix (voix.preparer : Whisper réécoute chaque phrase) ;
  5. le regard sur la 3D rendue (controle._regarder_anime : objet qui flotte, caméra dans un mur…) ;
  6. les règles (regles.py) ;
  7. le RÉDACTEUR EN CHEF (ici, `redacteur_en_chef`) : dernier avis sur la vidéo finie (texte + 6 images), comme un humain qui
     la regarde avant publication ; un défaut grave = « à vérifier » (jamais publiée seule).
Toutes les corrections d'un agent sont des RETRAITS ou des DÉPLACEMENTS sûrs (jamais d'invention) ; un agent indisponible
n'arrête jamais la fabrication (il est noté « sauté » dans le bulletin).
"""
import json
import os
import re
import subprocess

from . import ia

CONSIGNE_REALISATEUR = """Tu es réalisateur de reconstitutions 3D d'actualité. On te donne le texte de la vidéo (phrases numérotées)
et le plan de la reconstitution : objets (type, place) et actions (phrase, objet, action, cible). Trouve UNIQUEMENT les vraies
erreurs :
- physique : un véhicule, un bâtiment ou une personne qui vole, monte en l'air ou tombe du ciel (seuls avion et hélico volent) ;
- chronologie : une conséquence montrée AVANT sa cause (feu avant le choc qui l'a provoqué), un choc sur une cible déjà détruite ;
- présence : une personne qui n'était PAS sur place (président, ministre, porte-parole qui réagit de loin) ;
- contresens : une action qui contredit la phrase qu'elle illustre.
Pour chaque erreur, propose UNE correction parmi : {"retirer": n° de l'action}, {"deplacer": n° de l'action, "phrase": nouvelle
phrase}, {"retirer_objet": "id"}. Réponds uniquement en JSON : {"erreurs": [{"explication": "...", "correction": {...}}]}
Liste vide s'il n'y a rien à corriger."""

CONSIGNE_CHEF = """Tu es rédacteur en chef d'une chaîne TikTok d'actualité. Voici le texte dit dans une vidéo et 6 images prises
dans l'ordre. Dis s'il y a un défaut GRAVE qui empêche de publier : fait faux ou absurde dans le texte, image vide / noire / cassée,
objet qui flotte en l'air, image qui contredit clairement le texte, texte illisible ou qui cache tout, contenu choquant (corps,
sang). Une maquette 3D simple et colorée est NORMALE. Réponds uniquement en JSON :
{"verdict": "publiable" | "a_revoir", "defauts": [{"gravite": "grave" | "mineur", "explication": "..."}]}"""


def _resume_storyboard(anim):
    lignes, n = [], 0
    for sc in anim.get("scenes") or []:
        if sc.get("type") != "3d" or sc.get("accroche"):
            continue
        for o in sc.get("objets") or []:
            lignes.append(f"objet {o['id']} : {o['type']} (position {o.get('position', o.get('x', 0))}, altitude {o.get('altitude', 0)})")
        for a in sc.get("actions") or []:
            lignes.append(f"action {n} : phrase {a.get('phrase')} · {a['objet']} {a['faire']}" + (f" → {a['cible']}" if a.get("cible") else ""))
            a["_n"] = n; n += 1
    return "\n".join(lignes)


def critique_storyboard(script, anim, journal=print, exclure=()):
    """Agent 3 : relit la reconstitution AVANT le rendu et applique les corrections sûres. Renvoie le nombre de corrections."""
    plan = _resume_storyboard(anim)
    if not plan:
        return 0
    phrases = "\n".join(f"{i}. {p['ecrit']}" for i, p in enumerate(script["phrases"]))
    try:
        d, qui = ia.demander_json(CONSIGNE_REALISATEUR, f"TEXTE :\n{phrases}\n\nPLAN :\n{plan}", temperature=0.1, max_tokens=1500,
                                  exclure=exclure, journal=lambda *a: None)
    except Exception as e:
        journal(f"  🎬 réalisateur critique indisponible ({str(e)[:60]}) : reconstitution non relue")
        return 0
    n_phrases, faites = len(script["phrases"]), 0
    for err in d.get("erreurs") or []:
        c = (err or {}).get("correction") or {}
        for sc in anim.get("scenes") or []:
            if sc.get("type") != "3d" or sc.get("accroche"):
                continue
            acts = sc.get("actions") or []
            if "retirer" in c:
                avant = len(acts)
                sc["actions"] = [a for a in acts if a.get("_n") != c.get("retirer")]
                faites += avant != len(sc["actions"])
            elif "deplacer" in c and str(c.get("phrase", "")).isdigit() and 0 < int(c["phrase"]) < n_phrases - 1:
                for a in acts:
                    if a.get("_n") == c.get("deplacer") and int(c["phrase"]) in sc.get("phrases", []) + [a.get("phrase")]:
                        a["phrase"] = int(c["phrase"]); faites += 1
            elif "retirer_objet" in c:
                ob = c.get("retirer_objet")
                if any(o["id"] == ob for o in sc.get("objets") or []) and not any(a.get("objet") == ob and a.get("faire") in ("bruler", "exploser", "heurter") for a in acts):
                    sc["objets"] = [o for o in sc["objets"] if o["id"] != ob]
                    sc["actions"] = [a for a in acts if a.get("objet") != ob and a.get("cible") != ob]
                    faites += 1
        if faites:
            journal(f"  🎬 réalisateur critique ({qui}) : {err.get('explication', '')[:120]}")
    for sc in anim.get("scenes") or []:
        for a in sc.get("actions") or []:
            a.pop("_n", None)
    return faites


def redacteur_en_chef(fichier, script, dossier, B, journal=print):
    """Agent 7 : dernier avis sur la vidéo finie. Défaut grave = problème grave au bulletin (« à vérifier »)."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", fichier],
                           capture_output=True, text=True)
        duree = float(r.stdout.strip() or 0)
    except Exception:
        duree = 0
    if duree <= 0:
        return None
    images = []
    for k in range(6):
        img = os.path.join(dossier, f"chef{k}.jpg")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{duree * (k + 0.5) / 6:.2f}", "-i", fichier, "-frames:v", "1",
                        "-vf", "scale=480:-2", "-q:v", "5", img], check=False)
        if os.path.exists(img) and os.path.getsize(img) > 0:
            images.append(img)
    texte = " ".join(p["ecrit"] for p in script["phrases"])
    try:
        d, qui = ia.regarder_json(CONSIGNE_CHEF, "TEXTE DIT :\n" + texte, images[:5], journal=lambda *a: None)
        if len(images) > 5:
            d2, _ = ia.regarder_json(CONSIGNE_CHEF, "TEXTE DIT :\n" + texte, images[5:], journal=lambda *a: None)
            d["defauts"] = (d.get("defauts") or []) + (d2.get("defauts") or [])
            if d2.get("verdict") == "a_revoir":
                d["verdict"] = "a_revoir"
    except Exception as e:
        B.saute(f"avis du rédacteur en chef (IA indisponible : {str(e)[:80]})")
        return None
    graves = [x for x in d.get("defauts") or [] if isinstance(x, dict) and x.get("gravite") == "grave"]
    for x in d.get("defauts") or []:
        if isinstance(x, dict):
            journal(f"  🧑‍💼 rédacteur en chef ({qui}) : {x.get('gravite')} — {str(x.get('explication'))[:140]}")
    if graves and d.get("verdict") == "a_revoir":
        B.ouvrir("video", "Rédacteur en chef : " + " ; ".join(str(x.get("explication"))[:100] for x in graves), "redacteur_en_chef", "grave")
    else:
        B.fermer("video", "redacteur_en_chef")
    return d
