"""L'IA « réalisatrice » du nouveau style (demande de l'auteur du 26/11, d'après curioverse.actu et vudenhaut.fr).

Toutes les images de la vidéo sont FABRIQUÉES (cartes, gros chiffres, frises, reconstitutions 3D, étiquettes) : plus aucune
image ni vidéo d'un autre compte ou média, donc plus de « contenu non original » pour TikTok (nos vidéos restaient à 0 vue).

1. `storyboard(script, articles)` : l'IA lit le texte vérifié et choisit, pour chaque groupe de phrases, la scène à montrer ;
2. `valider(...)` : le robot contrôle tout ce qu'elle propose (types connus, chiffres présents dans le texte ou les articles,
   citations réelles, objets 3D de la bibliothèque, villes trouvées sur la carte) et remplace ce qui ne va pas par une scène
   sûre (chiffre ou mot-clé géant) ; aucune phrase n'est oubliée ;
3. `pour_rendu(...)` : quand la voix est faite, les numéros de phrases deviennent des secondes → storyboard pour
   robot/rendu/rendre.mjs (rendu image par image, 30 images par seconde).
"""
import json
import os
import re
import subprocess

from . import ia
from .commun import RACINE

TYPES = ("carte", "chiffre", "frise", "citation", "barres", "3d", "question", "mot")
OBJETS_3D = ("voiture", "camion", "citerne", "bus", "moto", "avion", "helico", "bateau", "train", "batiment", "arbre", "personne",
             "muret", "mur", "cube_eau")
ACTIONS_3D = ("avancer", "heurter", "changer_voie", "tourner", "se_coucher", "bruler", "exploser", "tomber", "voler", "couler",
              "apparaitre", "disparaitre")
DECORS = ("autoroute", "route", "ville", "mer", "port", "plage", "piste", "voie_ferree", "campagne", "studio")
COULEURS = ("orange", "rouge", "jaune", "bleu", "vert", "violet", "gris")

CONSIGNE = """Tu es le réalisateur d'une vidéo TikTok d'actualité où TOUT est fabriqué en animation (comme une infographie
animée) : cartes, gros chiffres, frises, petites reconstitutions 3D style maquette. AUCUNE photo ni vidéo réelle.
On te donne les phrases numérotées de la voix off (déjà vérifiées) et les faits des articles.
Découpe les phrases en SCÈNES qui se suivent (chaque phrase dans une seule scène, dans l'ordre, 1 à 3 phrases par scène ;
change d'image souvent : une scène dure 3 à 8 secondes). Types de scènes :
- "carte" : {"zone": "france"|"europe"|"monde"|"usa", "departements": [{"code": "39", "couleur": "orange", "etiquette": "JURA"}],
  "pays": [{"iso": "EGY", "couleur": "rouge", "etiquette": "ÉGYPTE"}], "lieux": ["Saint-Claude"], "effet": "pluie"|"neige"|"orage"|null,
  "fleche": {"de": "Brest", "vers": "Strasbourg"}} — pour situer l'événement, une alerte météo, un trajet ;
- "chiffre" : {"valeur": "31", "unite": "morts", "texte": "selon le ministère"} — UN chiffre clé tiré du texte ;
- "mot" : {"valeur": "ARRÊTÉ", "texte": "le conducteur de la voiture"} — 1 à 3 mots forts ;
- "frise" : {"etapes": [{"heure": "18 h", "texte": "..."}]} — chronologie (3 étapes au plus) ;
- "citation" : {"texte": "phrase EXACTE prononcée, copiée des articles", "auteur": "qui l'a dite"} ;
- "barres" : {"barres": [{"texte": "Hier", "valeur": 9, "unite": "départements"}, {"texte": "Demain", "valeur": 60}]} ;
- "3d" : reconstitution d'un accident ou d'un événement décrit PRÉCISÉMENT par les articles (sinon n'en fais pas) :
  {"decor": "autoroute"|"route"|"ville"|"mer"|"port"|"piste"|"voie_ferree"|"campagne", "moment": "jour"|"soir"|"nuit",
   "objets": [{"id": "camion", "type": "citerne", "voie": 2, "position": 0, "couleur": "#ffffff"}],
   "actions": [{"objet": "camion", "faire": "avancer", "phrase": 3, "duree": 3, "vers_position": 60},
               {"objet": "voiture", "faire": "heurter", "cible": "camion", "phrase": 4, "duree": 1.5},
               {"objet": "camion", "faire": "se_coucher", "phrase": 5}, {"objet": "camion", "faire": "bruler", "phrase": 6}],
   "reperes": [{"objet": "voiture", "texte": "une voiture", "phrase": 4}]}
  types d'objets : voiture, camion, citerne, bus, moto, avion, helico, bateau, train, batiment, arbre, personne, muret, mur ;
  actions : avancer, heurter, changer_voie, tourner, se_coucher, bruler, exploser, tomber, voler, couler, apparaitre, disparaitre ;
  "voie" = numéro de voie (1 à 6), "position" = mètres le long de la route ; "phrase" = numéro de la phrase où l'action commence ;
- "question" : {"texte": "la question finale"} — OBLIGATOIRE pour la dernière phrase.
Chaque scène peut avoir "etiquettes": ["SELON LE PARQUET"] (1 ou 2 étiquettes courtes en MAJUSCULES : qui le dit, le moment).
N'invente RIEN : chiffres, lieux, heures, citations et déroulé viennent du texte ou des articles.
Donne aussi : "titre" (le titre affiché en haut, 45 signes au plus, le mot le plus fort entre **astérisques**), "lieu_date"
(ex. "LE CAIRE · MERCREDI SOIR"), "source" (ex. "Source : parquet égyptien, ministère de la Santé"), et "cles" : pour chaque
numéro de phrase, 1 ou 2 mots importants à surligner dans les sous-titres (copiés tels quels de la phrase).
Réponds uniquement en JSON : {"titre": "", "lieu_date": "", "source": "", "cles": {"0": ["mot"]}, "scenes": [{"phrases": [0, 1], "type": "carte", ...}]}"""


def _texte_articles(articles):
    return " ".join(f"{a.get('titre', '')} {a.get('texte') or ''}" for a in articles or [])


def _chiffres(t):
    return {c.replace(" ", "").replace(",", ".") for c in re.findall(r"\d[\d  ]*(?:[.,]\d+)?", t or "")}


def storyboard(script, articles, journal=print):
    phrases = "\n".join(f"{i}. {p['ecrit']}" for i, p in enumerate(script["phrases"]))
    faits = _texte_articles(articles)[:9000]
    d, qui = ia.demander_json(CONSIGNE, f"TITRE DU SUJET : {script.get('titre', '')}\nLIEU : {script.get('lieu', '')}\n\nPHRASES :\n{phrases}"
                              f"\n\nARTICLES :\n{faits}", temperature=0.4, max_tokens=5000, journal=journal)
    journal(f"  réalisation proposée par {qui} : {len(d.get('scenes') or [])} scène(s)")
    return d


def _lieu(nom, cache):
    from . import carte
    if nom not in cache:
        try:
            cache[nom] = carte.trouver_lieu(nom)
        except Exception:
            cache[nom] = None
    return cache[nom]


def _secours(script, i, j):
    """Scène sûre pour les phrases i..j : le 1er chiffre dit, sinon 1 à 3 mots forts de la phrase."""
    t = " ".join(p["ecrit"] for p in script["phrases"][i:j + 1])
    m = re.search(r"(\d[\d  ]*(?:[.,]\d+)?)\s*(%|mm|km/h|km|kg|m|°C|°|ans|morts|blessés|euros|€|millions|milliards)?", t)
    if m:
        reste = t[m.end():].strip(" ,.").split()
        return dict(type="chiffre", valeur=m.group(1).strip(), unite=m.group(2) or (reste[0] if reste and len(reste[0]) < 12 else ""),
                    texte="")
    mots = [w for w in re.findall(r"[A-Za-zÀ-ÿ'-]{4,}", t) if w.lower() not in MOTS_VIDES][:3]
    return dict(type="mot", valeur=" ".join(mots[:2]).upper() or "…", texte="")


MOTS_VIDES = {"dans", "pour", "avec", "sans", "cette", "comme", "mais", "plus", "très", "tout", "tous", "leur", "elle", "elles",
              "ils", "sont", "était", "être", "avoir", "fait", "aussi", "alors", "encore", "depuis", "quand", "après", "avant"}


def valider(d, script, articles, journal=print):
    """Storyboard propre : toutes les phrases couvertes, dans l'ordre ; ce qui est douteux est remplacé par une scène sûre."""
    n = len(script["phrases"])
    bas = _texte_articles(articles).lower()
    dits = " ".join(p["ecrit"] for p in script["phrases"])
    connus = _chiffres(dits) | _chiffres(bas)
    cache, scenes, couvertes = {}, [], 0
    for sc in d.get("scenes") or []:
        if not isinstance(sc, dict):
            continue
        ph = sorted({int(x) for x in sc.get("phrases") or [] if str(x).lstrip("-").isdigit() and 0 <= int(x) < n})
        ph = [x for x in ph if x >= couvertes]
        if not ph:
            continue
        i, j = couvertes, max(ph)                       # rien n'est sauté : les phrases oubliées vont dans cette scène
        if j - i > 3:                                   # scène trop longue : coupée
            j = i + 2
        sc = dict(sc, phrases=list(range(i, j + 1)))
        t = sc.get("type")
        raison = None
        if t not in TYPES:
            raison = f"type inconnu « {t} »"
        elif t in ("chiffre",) and not (_chiffres(str(sc.get("valeur"))) <= connus and _chiffres(str(sc.get("valeur")))):
            raison = f"chiffre « {sc.get('valeur')} » absent du texte et des articles"
        elif t == "citation" and (len(str(sc.get("texte") or "")) < 8 or str(sc.get("texte")).lower().strip(" «»\"") not in bas):
            raison = "citation introuvable dans les articles"
        elif t == "barres" and not all(_chiffres(str(b.get("valeur"))) <= connus for b in sc.get("barres") or [{}]):
            raison = "barres : chiffre inventé"
        elif t == "3d":
            sc["objets"] = [o for o in sc.get("objets") or [] if isinstance(o, dict) and o.get("type") in OBJETS_3D and o.get("id")][:12]
            ids = {o["id"] for o in sc["objets"]}
            sc["actions"] = [a for a in sc.get("actions") or [] if isinstance(a, dict) and a.get("faire") in ACTIONS_3D
                             and a.get("objet") in ids and (a.get("faire") != "heurter" or a.get("cible") in ids)][:20]
            sc["decor"] = sc.get("decor") if sc.get("decor") in DECORS else "route"
            if not sc["objets"]:
                raison = "reconstitution sans objet"
        elif t == "carte":
            for cle in ("departements", "pays"):
                sc[cle] = [x if isinstance(x, dict) else {"code" if cle == "departements" else "iso": x} for x in sc.get(cle) or []][:12]
                for x in sc[cle]:
                    x["couleur"] = x.get("couleur") if x.get("couleur") in COULEURS else None
            points = []
            for nom in [x if isinstance(x, str) else (x or {}).get("nom", "") for x in sc.get("lieux") or []][:5]:
                if nom and nom.lower() in (dits + " " + bas).lower():
                    l = _lieu(nom, cache)
                    if l:
                        points.append(dict(nom=nom, lat=l["lat"], lon=l["lon"]))
            sc["points"] = points
            f = sc.get("fleche") or {}
            if isinstance(f, dict) and f.get("de") and f.get("vers"):
                a, b = _lieu(str(f["de"]), cache), _lieu(str(f["vers"]), cache)
                sc["fleches"] = [dict(de=[a["lat"], a["lon"]], vers=[b["lat"], b["lon"]])] if a and b else []
            if not (sc["departements"] or sc["pays"] or sc["points"]):
                l = _lieu(str(script.get("lieu") or "").split(",")[0], cache) if script.get("lieu") else None
                if l:
                    sc["points"] = [dict(nom=l["nom"], lat=l["lat"], lon=l["lon"])]
                else:
                    raison = "carte sans lieu trouvé"
            if sc.get("effet") not in ("pluie", "neige", "orage"):
                sc["effet"] = None
        if raison:
            journal(f"  réalisation, phrases {i}-{j} : {raison} → scène de secours")
            sc = dict(_secours(script, i, j), phrases=sc["phrases"], etiquettes=sc.get("etiquettes"))
        scenes.append(sc)
        couvertes = j + 1
    while couvertes < n:                                # phrases restées sans scène
        j = min(n - 1, couvertes + 1)
        scenes.append(dict(_secours(script, couvertes, j), phrases=list(range(couvertes, j + 1))))
        couvertes = j + 1
    der = scenes[-1]                                    # la dernière phrase : toujours la question, seule
    if der["type"] != "question":
        if len(der["phrases"]) > 1:
            der["phrases"] = der["phrases"][:-1]
            scenes.append(dict(type="question", phrases=[n - 1]))
        else:
            der["type"] = "question"
    scenes[-1]["texte"] = script.get("question") or script["phrases"][-1]["ecrit"]
    titre = str(d.get("titre") or script.get("titre") or "")[:60]
    if "**" not in titre:
        mots = titre.split()
        if mots:
            k = max(range(len(mots)), key=lambda x: (bool(re.search(r"\d", mots[x])), len(mots[x])))
            mots[k] = f"**{mots[k]}**"; titre = " ".join(mots)
    cles = {}
    for k, v in (d.get("cles") or {}).items():
        if str(k).isdigit() and int(k) < n:
            cles[int(k)] = [str(m) for m in (v if isinstance(v, list) else [v]) if str(m).lower() in script["phrases"][int(k)]["ecrit"].lower()][:2]
    return dict(titre=titre, lieu_date=str(d.get("lieu_date") or "")[:40].upper(), source=str(d.get("source") or "")[:110],
                cles=cles, scenes=scenes)


def realiser(script, articles, journal=print):
    """Storyboard validé (l'IA, sinon uniquement des scènes sûres)."""
    try:
        d = storyboard(script, articles, journal)
    except Exception as e:
        journal(f"  réalisation par l'IA impossible ({str(e)[:100]}) : scènes simples")
        d = {}
    return valider(d, script, articles, journal)


# ------------------------------------------------------------------ numéros de phrases → secondes (après la voix)
def _voie_z(voie, voies=6):
    return round(-voies * 3.6 / 2 + (min(max(int(voie or 1), 1), voies) - 0.5) * 3.6, 2)


def pour_rendu(anim, script, debuts, mots, total, mention_source=""):
    """Storyboard pour rendre.mjs : `debuts` = début de chaque phrase (s), `mots` = [{m, d, f, cle}] de toute la vidéo."""
    scenes = []
    for k, sc in enumerate(anim["scenes"]):
        a = debuts[sc["phrases"][0]]
        b = debuts[sc["phrases"][-1] + 1] if sc["phrases"][-1] + 1 < len(debuts) else total
        s = {k2: v for k2, v in sc.items() if k2 not in ("phrases",)}
        s.update(debut=round(a, 3), fin=round(b, 3))
        quand = lambda x, defaut=0.3: round(max(0.0, debuts[int(x)] - a), 2) if str(x).isdigit() and int(x) < len(debuts) else defaut
        s["etiquettes"] = [dict(texte=str(e if isinstance(e, str) else e.get("texte", ""))[:28].upper(), a=0.25 + 0.45 * n,
                                style="rouge" if n == 0 and sc["type"] == "carte" else "")
                           for n, e in enumerate((sc.get("etiquettes") or [])[:2]) if e]
        if sc["type"] == "carte":
            s["departements"] = [dict(x, a=0.4 + 0.25 * n) for n, x in enumerate(sc.get("departements") or [])]
            s["pays"] = [dict(x, a=0.4 + 0.25 * n) for n, x in enumerate(sc.get("pays") or [])]
            s["points"] = [dict(p, a=1.0 + 0.4 * n) for n, p in enumerate(sc.get("points") or [])]
            s["mention"] = "Carte : Natural Earth, IGN" + (f" · {mention_source}" if mention_source else "")
        if sc["type"] == "mot":
            s["type"] = "chiffre"
        if sc["type"] == "3d":
            voies = 6 if sc.get("decor") == "autoroute" else 2
            objets = []
            for o in sc["objets"]:
                objets.append(dict(o, x=float(o.get("position") or 0), z=_voie_z(o.get("voie"), voies) if o.get("type") not in ("batiment", "arbre") else float(o.get("z") or 25)))
            actions = []
            for x in sc["actions"]:
                act = dict(x, a=quand(x.get("phrase"), 0.2), d=float(x.get("duree") or 1.2))
                o = next((o for o in objets if o["id"] == x["objet"]), {})
                if x["faire"] in ("avancer", "changer_voie", "voler", "tomber"):
                    vx = float(x.get("vers_position", o.get("x", 0) + 40))
                    vz = _voie_z(x.get("vers_voie"), voies) if x.get("vers_voie") else o.get("z", 0)
                    act["vers"] = [vx, vz] + ([float(x.get("altitude", 0))] if x["faire"] in ("voler", "tomber") else [])
                actions.append(act)
            s.update(objets=objets, actions=actions, voies=voies)
            s["reperes"] = [dict(objet=r.get("objet"), texte=str(r.get("texte", ""))[:30], a=quand(r.get("phrase"), 0.4))
                            for r in sc.get("reperes") or [] if any(o["id"] == r.get("objet") for o in objets)][:4]
            principal = next((a_["objet"] for a_ in actions if a_["faire"] in ("avancer", "voler", "tomber")), objets[0]["id"])
            d_ = b - a                                      # caméra : vue en hauteur qui suit l'objet principal et se rapproche
            s["camera"] = [dict(a=0, pos=[-55, 42, 52], suivre=principal), dict(a=max(1.0, d_ * 0.55), pos=[-32, 30, 40], suivre=principal),
                           dict(a=max(2.0, d_), pos=[-24, 24, 32], suivre=principal)]
            s["mention"] = "Reconstitution 3D · illustration" + (f" d'après {mention_source}" if mention_source else "")
        scenes.append(s)
    return dict(ips=30, duree=round(total, 3), titre=anim["titre"], lieu_date=anim["lieu_date"], source=anim["source"],
                etiquette=script.get("etiquette") or "BUZZ INSOLITE", mots=mots, scenes=scenes)


def rendre(sb, sortie, journal=print):
    """Lance le rendu (Chromium + ffmpeg) ; vidéo SANS son, 30 images par seconde."""
    fichier = sortie + ".json"
    with open(fichier, "w", encoding="utf-8") as f:
        json.dump(sb, f, ensure_ascii=False)
    r = subprocess.run(["node", os.path.join(RACINE, "robot", "rendu", "rendre.mjs"), fichier, sortie],
                       capture_output=True, text=True, timeout=3 * 3600)
    for ligne in (r.stdout or "").splitlines():
        if "terminé" in ligne:
            journal(f"  {ligne}")
    if r.returncode or not os.path.exists(sortie):
        raise RuntimeError(f"rendu animé impossible : {(r.stderr or r.stdout)[-400:]}")
    return sortie
