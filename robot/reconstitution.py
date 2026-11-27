"""Reconstitution 3D PLAN PAR PLAN de l'événement, de A à Z (demande de l'auteur du 27/11 : « reconstitue les scènes
exactement comme elles se sont déroulées, de A à Z, comme les chaînes qu'on a vues »).

Avant : la petite IA donnait 1 ou 2 actions ; le robot complétait avec des mots-clés. Maintenant une IA écrit le SCÉNARIO de
la reconstitution comme un story-board de cinéma : le décor exact (autoroute, usine, port…), chaque véhicule / bâtiment /
personne avec sa place de départ (voie, distance), puis UN PLAN PAR PHRASE : qui fait quoi (avancer, freiner, déraper,
percuter, se renverser, déverser, brûler, exploser, s'effondrer, arroser, fuir…), d'où on le filme (large, de côté, de
face, du dessus, en suivant, de l'intérieur) et l'étiquette à l'écran. Le robot vérifie TOUT :
  - chaque objet, action, décor et angle existe dans la bibliothèque 3D ;
  - chaque action vient d'une phrase qui la raconte (pas d'action sans phrase, phrases dans l'ordre) ;
  - une étiquette ne contient pas de chiffre absent du texte ;
  - les étapes que le texte raconte et que l'IA aurait oubliées sont ajoutées (`gabarits._completer`).
Ce qui n'est pas dit par les articles (la voie exacte, la couleur) reste simple et la vidéo l'annonce : « positions
approximatives ».
"""
import re

from . import ia

OBJETS = ("voiture", "camion", "citerne", "bus", "moto", "camionnette", "taxi", "police", "ambulance", "pompiers", "avion",
          "helico", "bateau", "train", "personne", "foule", "batiment", "entrepot", "immeuble", "maison", "batiment_officiel", "arbre",
          "hopital", "banque", "magasin", "residence", "feu_tricolore", "panneau",
          "muret", "mur")
ACTIONS = ("avancer", "freiner", "changer_voie", "deraper", "tonneau", "heurter", "se_coucher", "deverser", "bruler",
           "exploser", "effondrer", "tomber", "voler", "couler", "arroser", "fuir", "apparaitre", "disparaitre")
DECORS = ("autoroute", "route", "ville", "place", "usine", "mer", "port", "plage", "piste", "voie_ferree", "campagne")
CADRES = ("large", "cote", "face", "dessus", "suivi", "interieur", "maquette")
MOMENTS = ("jour", "soir", "nuit")

CONSIGNE = """Tu es le réalisateur d'une RECONSTITUTION 3D d'un fait divers (comme les reconstitutions des journaux télévisés).
On te donne les phrases numérotées de la vidéo et les articles. Écris le scénario de la reconstitution, de A à Z, PLAN PAR
PLAN, en suivant EXACTEMENT les faits des articles (ordre, qui fait quoi, où). N'invente aucun fait : si un détail n'est pas
dit (voie, couleur), choisis le plus simple. Réponds uniquement en JSON :
{"decor": "autoroute" | "route" | "ville" | "place" | "usine" | "mer" | "port" | "plage" | "piste" | "voie_ferree" | "campagne",
 "moment": "jour" | "soir" | "nuit",
 "objets": [{"id": "citerne", "type": "citerne", "role": "le camion-citerne", "voie": 2, "position": -40}],
 "plans": [{"phrase": 2, "cadre": "suivi", "actions": [{"objet": "citerne", "faire": "avancer", "vers_position": 0}],
            "etiquette": "PÉRIPHÉRIQUE DU CAIRE"}]}
Règles :
- "objets" : TOUT ce qui est PHYSIQUEMENT sur place et joue un rôle (véhicules, bâtiments, personnes, secours) ; jamais une
  personne qui en parle de loin (président, ministre, agence, journaliste). Deux objets ne sont jamais au même endroit. Types : voiture, camion, citerne, bus, moto,
  camionnette, taxi, police, ambulance, pompiers, avion, helico, bateau, train, personne, foule, batiment, entrepot (dépôt,
  hangar, usine), immeuble, maison, hopital, banque, magasin, residence, feu_tricolore, panneau,
  batiment_officiel, arbre, muret, mur. "voie" : 1 à 3 (sens de circulation de la caméra), "position" : mètres le long de la
  route (l'événement se passe vers 0 ; ce qui arrive plus tard part de -80 ou plus loin). Bâtiment, usine : "position" 0.
- "plans" : un plan pour CHAQUE phrase qui raconte l'événement (du début à la fin des faits, dans l'ordre), avec l'action
  que cette phrase raconte. Actions : avancer {vers_position}, freiner {vers_position}, changer_voie {vers_voie}, deraper,
  tonneau, heurter {cible}, se_coucher, deverser (fuite de carburant), bruler, exploser, effondrer, tomber, voler
  {altitude}, couler, arroser {cible} (pompiers), fuir (personnes qui s'enfuient), apparaitre, disparaitre.
  Un véhicule qui percute un autre : "heurter" avec "cible". Les secours qui arrivent : "avancer" vers -20.
- "cadre" : large (vue d'ensemble), cote (au ras du sol, de côté : un choc), face (un véhicule qui se renverse), dessus
  (vu du ciel : une fuite, une foule), suivi (on suit un véhicule qui roule), interieur (vue du conducteur), maquette (vue
  d'en haut, en biais, d'un bâtiment ou d'un quartier).
- "etiquette" : 3 à 24 signes en majuscules, un fait de la phrase (« 120 KM/H », « LA FUITE », « 22 H 40 ») ou "".
Exemple (accident) : objets citerne (voie 2, -40) et voiture (voie 3, -60) ; plans : phrase 2 suivi avancer citerne ;
phrase 3 cote voiture heurter citerne ; phrase 4 face citerne se_coucher ; phrase 5 dessus citerne deverser ; phrase 6
large citerne bruler ; phrase 8 large ambulance avancer vers -20."""


def _num(x, defaut=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return defaut


def _chiffres(t):
    return set(re.findall(r"\d+", str(t)))


def valider(d, script, journal=print):
    """Scénario propre et sûr, ou None s'il n'en reste rien d'utilisable."""
    if not isinstance(d, dict):
        return None
    n = len(script["phrases"])
    dits = [p["ecrit"] for p in script["phrases"]]
    connus = _chiffres(" ".join(dits))
    objets, vus = [], set()
    for o in d.get("objets") or []:
        if not isinstance(o, dict) or o.get("type") not in OBJETS or not o.get("id") or str(o["id"]) in vus:
            continue
        vus.add(str(o["id"]))
        objets.append(dict(id=str(o["id"])[:20], type=o["type"], role=str(o.get("role") or "")[:28],
                           voie=int(min(3, max(1, _num(o.get("voie"), 1)))), position=max(-400.0, min(200.0, _num(o.get("position"), 0)))))
    # ni les personnes qui ne sont PAS sur place (président qui « salue », agence qui annonce : Iowa du 27/11)…
    objets = [o for o in objets if not (o["type"] in ("personne", "foule") and re.search(
        r"pr[ée]sident|ministre|gouvernement|agence|porte-parole|epa\b|trump|biden|macron|maire|pr[ée]fet|journalist|t[ée]l[ée]spect",
        f"{o['id']} {o['role']}".lower()))]
    # … ni deux objets au même endroit (4 entrepôts empilés à la position 0, Iowa du 27/11 : débris coincés dans les murs)
    BATI = ("batiment", "entrepot", "immeuble", "maison", "batiment_officiel", "hopital", "banque", "magasin", "residence")
    batis, voies = [], {}
    for o in objets:
        if o["type"] in BATI:                           # bâtiments côte à côte, 46 m d'écart
            while any(abs(o["position"] - x) < 46 for x in batis):
                o["position"] += 46
            batis.append(o["position"])
        elif o["type"] not in ("personne", "foule", "arbre", "muret", "mur"):   # véhicules : l'un derrière l'autre sur leur voie
            prises = voies.setdefault(o["voie"], [])
            while any(abs(o["position"] - x) < 9 for x in prises):
                o["position"] -= 11
            prises.append(o["position"])
    if not objets:
        return None
    ids = {o["id"] for o in objets}
    plans, derniere = [], 0
    for p in sorted([p for p in d.get("plans") or [] if isinstance(p, dict)], key=lambda p: _num(p.get("phrase"), 99)):
        ph = int(_num(p.get("phrase"), -1))
        if not 1 <= ph < n - 1 or ph < derniere:            # ni l'accroche (gérée à part), ni la question, et dans l'ordre
            continue
        acts = []
        for a in p.get("actions") or []:
            if not isinstance(a, dict) or a.get("faire") not in ACTIONS or a.get("objet") not in ids:
                continue
            if a["faire"] in ("heurter", "arroser") and a.get("cible") not in ids - {a["objet"]}:
                continue
            x = dict(objet=a["objet"], faire=a["faire"], phrase=ph)
            for cle in ("vers_position", "altitude"):
                if _num(a.get(cle)) is not None:
                    x[cle] = max(-400.0, min(200.0, _num(a[cle])))
            if a.get("vers_voie") is not None:
                x["vers_voie"] = int(min(3, max(1, _num(a.get("vers_voie"), 1))))
            if a.get("cible"):
                x["cible"] = a["cible"]
            acts.append(x)
        etiq = re.sub(r"\s+", " ", re.sub(r"[^\w' /:.,%-]", "", str(p.get("etiquette") or "").replace("_", " "))).strip().upper()[:24]
        if etiq and (not re.search(r"[AEIOUYÀÂÉÈÊËÎÏÔÙÛ]", etiq) or re.search(r"\b[A-Z]{2,}_", etiq)):
            etiq = ""                                   # (« PAS_DE_LEAD », Iowa du 27/11 : étiquette en anglais / code)
        if etiq and not _chiffres(etiq) <= connus:
            journal(f"  reconstitution, phrase {ph} : étiquette « {etiq} » avec un chiffre inventé → retirée")
            etiq = ""
        cadre = p.get("cadre") if p.get("cadre") in CADRES else None
        types = {o["id"]: o["type"] for o in objets}
        if cadre == "interieur" and not any(types.get(a["objet"]) in ("voiture", "camion", "citerne", "bus", "camionnette", "taxi", "train", "moto")
                                            for a in acts):
            cadre = "suivi"                             # vue du conducteur : seulement depuis un véhicule (drone de l'Iowa, 27/11)
        if acts or etiq:
            plans.append(dict(phrase=ph, actions=acts, cadre=cadre, etiquette=etiq))
            derniere = ph
    if not any(p["actions"] for p in plans):
        return None
    return dict(decor=d.get("decor") if d.get("decor") in DECORS else None, moment=d.get("moment") if d.get("moment") in MOMENTS else None,
                objets=objets, plans=plans)


def ecrire(script, articles, journal=print):
    """Scénario de reconstitution validé, ou None (IA indisponible, rien d'utilisable)."""
    phrases = "\n".join(f"{i}. {p['ecrit']}" for i, p in enumerate(script["phrases"]))
    faits = " ".join(f"{a.get('titre', '')} {a.get('texte') or ''}" for a in articles or [])[:7000]
    try:
        d, qui = ia.demander_json(CONSIGNE, f"PHRASES :\n{phrases}\n\nARTICLES :\n{faits}", temperature=0.3, max_tokens=3500, journal=journal)
    except Exception as e:
        journal(f"  scénario de reconstitution impossible ({str(e)[:80]})")
        return None
    r = valider(d, script, journal)
    if r:
        journal(f"  scénario de reconstitution par {qui} : décor {r['decor']} · {len(r['objets'])} objet(s) · "
                f"{len(r['plans'])} plan(s) · {sum(len(p['actions']) for p in r['plans'])} action(s)")
    else:
        journal(f"  scénario de reconstitution de {qui} inutilisable : recette automatique")
    return r
