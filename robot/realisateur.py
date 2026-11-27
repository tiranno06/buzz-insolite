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

BASES = ("carte", "3d", "photo")                    # décors qui restent à l'écran (le moteur pose le reste par-dessus)
TYPES = ("suite", "carte", "chiffre", "frise", "citation", "barres", "3d", "question", "mot", "icone", "document", "calendrier", "personnes", "jauge")
UNITES_FORTES = ("millions", "million", "milliards", "milliard", "mille", "%", "pour cent")
OBJETS_3D = ("voiture", "camion", "citerne", "bus", "moto", "avion", "helico", "bateau", "train", "batiment", "arbre", "personne",
             "muret", "mur", "cube_eau", "foule", "police", "pompiers", "ambulance", "batiment_officiel",
             # vrais modèles Kenney (CC0) depuis le 27/11
             "taxi", "camionnette", "tracteur", "debris", "plot", "soldat", "vedette", "barque", "voilier", "conteneur", "tgv",
             "wagon_citerne", "palmier", "rocher", "maison", "immeuble", "gratte_ciel", "entrepot",
             "hopital", "banque", "magasin", "residence", "feu_tricolore", "panneau")
ACTIONS_3D = ("avancer", "heurter", "changer_voie", "tourner", "se_coucher", "bruler", "exploser", "tomber", "voler", "couler",
              "apparaitre", "disparaitre", "deverser", "freiner", "deraper", "tonneau", "effondrer", "arroser", "fuir",
              "inonder", "trembler", "tempete")
DECORS = ("autoroute", "route", "ville", "place", "usine", "foret", "mer", "port", "plage", "piste", "voie_ferree", "campagne", "studio")
COULEURS = ("orange", "rouge", "jaune", "bleu", "vert", "violet", "gris")

CONSIGNE = """Tu es le réalisateur d'une vidéo TikTok d'actualité où TOUT est fabriqué en animation, comme les chaînes
curioverse.actu et vudenhaut.fr : la Terre vue du ciel (carte satellite), petites reconstitutions 3D style maquette, avec
des chiffres et étiquettes posés PAR-DESSUS. AUCUNE photo ni vidéo réelle.
PRINCIPE : un DÉCOR reste toujours à l'écran et bouge en continu ("carte" ou "3d") ; les autres scènes (chiffre, icone,
document, calendrier, personnes, frise, barres, citation, mot) s'affichent PAR-DESSUS le dernier décor, qui continue derrière.
Donc : la 1re scène est un DÉCOR (la carte qui zoome sur le lieu, ou la reconstitution 3D) ; change de décor 1 à 3 fois dans
la vidéo (ex. carte du lieu → reconstitution 3D de l'événement → carte du bilan) ; entre deux décors, 1 à 3 encadrés.
Un événement physique (accident, incendie, crash, naufrage, déraillement, tempête sur une route) = une reconstitution "3d"
quand les articles décrivent ce qui s'est passé. Une alerte météo, un pays, une région = "carte" (avec "nuit": true si les
faits se passent la nuit : on voit alors les lumières des villes).
On te donne les phrases numérotées de la voix off (déjà vérifiées) et les faits des articles.
Découpe TOUTES les phrases en SCÈNES qui se suivent (CHAQUE numéro de phrase dans une scène, dans l'ordre, 1 ou 2 phrases par
scène, donc environ autant de scènes que de phrases divisées par 1,5 ;
change d'image souvent : une scène dure 3 à 8 secondes). Types de scènes :
- "carte" (DÉCOR) : {"zone": "france"|"europe"|"monde"|"usa", "nuit": false, "departements": [{"code": "39", "couleur": "orange", "etiquette": "JURA"}],
  "pays": [{"iso": "EGY", "couleur": "rouge", "etiquette": "ÉGYPTE"}], "lieux": ["Saint-Claude"], "effet": "pluie"|"neige"|"orage"|null,
  "fleche": {"de": "Brest", "vers": "Strasbourg"}} — pour situer l'événement, une alerte météo, un trajet ;
- "chiffre" : {"valeur": "31", "unite": "morts", "texte": "selon le ministère"} — UN chiffre clé tiré du texte ;
- "icone" : {"emoji": "🏥", "valeur": "HÔPITAL", "texte": "4 mots au plus"} — un pictogramme géant (UN emoji adapté) ;
- "document" : {"entete": "Décret des talibans", "titre": "PRÉNOMS INTERDITS", "tampon": "OFFICIEL", "texte": "..."} — une loi,
  un décret, un rapport, une plainte, un jugement ;
- "calendrier" : {"jour": "22", "mois": "NOVEMBRE", "annee": "2026", "texte": "..."} — une date clé ;
- "personnes" : {"total": 10, "colores": 3, "texte": "3 femmes sur 10"} — une proportion (« 1 sur 2 », « 3 sur 10 ») ;
- "mot" : {"valeur": "ARRÊTÉ", "emoji": "🚔", "texte": "..."} — 1 à 3 mots forts (2 fois AU PLUS par vidéo) ;
- "frise" : {"etapes": [{"heure": "18 h", "texte": "..."}]} — chronologie (3 étapes au plus) ;
- "citation" : {"texte": "phrase EXACTE prononcée, copiée des articles", "auteur": "qui l'a dite"} ;
- "barres" : {"barres": [{"texte": "Hier", "valeur": 9, "unite": "départements"}, {"texte": "Demain", "valeur": 60}]} ;
- "3d" (DÉCOR) : reconstitution d'un accident ou d'un événement décrit PRÉCISÉMENT par les articles (sinon n'en fais pas) :
  {"decor": "autoroute"|"route"|"ville"|"mer"|"port"|"piste"|"voie_ferree"|"campagne", "moment": "jour"|"soir"|"nuit",
   "objets": [{"id": "camion", "type": "citerne", "voie": 2, "position": 0, "couleur": "#ffffff"}],
   "actions": [{"objet": "camion", "faire": "avancer", "phrase": 3, "duree": 3, "vers_position": 60},
               {"objet": "voiture", "faire": "heurter", "cible": "camion", "phrase": 4, "duree": 1.5},
               {"objet": "camion", "faire": "se_coucher", "phrase": 5}, {"objet": "camion", "faire": "bruler", "phrase": 6}],
   "reperes": [{"objet": "voiture", "texte": "une voiture", "phrase": 4}]}
  types d'objets : voiture, camion, citerne, bus, moto, avion, helico, bateau, train, batiment, arbre, personne, muret, mur,
  foule ({"nombre": 60}), police, pompiers, ambulance, batiment_officiel (ministère, parlement, tribunal), taxi,
  camionnette, tracteur, debris (morceaux après un choc), plot (cône de chantier), soldat, vedette, barque, voilier,
  conteneur, tgv, wagon_citerne, palmier, rocher, maison, immeuble, gratte_ciel ;
  décor "place" = grande place de ville : pour une MANIFESTATION, un rassemblement, une intervention de police, un procès
  (foule + police + batiment_officiel), en illustration ;
  actions : avancer, heurter, changer_voie, tourner, se_coucher, bruler, exploser, tomber, voler, couler, apparaitre, disparaitre ;
  "voie" = numéro de voie (1 à 6), "position" = mètres le long de la route ; "phrase" = numéro de la phrase où l'action commence ;
- "question" : {"texte": "la question finale"} — OBLIGATOIRE pour la dernière phrase.
Les DÉCORS doivent occuper la moitié de la vidéo au moins (les encadrés sont des moments courts, pas l'essentiel).
"icone" / "mot" : "valeur" = 1 ou 2 NOMS (jamais un verbe, jamais « d'… » ni « le … ») ; chaque emoji UNE fois par vidéo.
VARIE les scènes (au moins 5 types différents) comme une vraie infographie animée ; un "texte" sous un visuel fait 8 mots
au plus (les sous-titres disent déjà tout). "chiffre" : "unite" reprend EXACTEMENT les mots après le nombre dans la phrase
(« 21,7 millions » → valeur "21,7", unite "millions"). Un "emoji" peut s'ajouter à "chiffre" et "mot".
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


def _unite_du_texte(valeur, phrase, unite):
    """« 21,7 millions de femmes » : l'unité « millions » ne doit jamais disparaître (vidéo Afghanistan du 27/11 : « 21,70 »)."""
    m = re.search(re.escape(valeur.strip()).replace(r"\,", "[.,]").replace(r"\.", "[.,]") + r"\s+([A-Za-zÀ-ÿ%]+)", phrase or "")
    suivant = (m.group(1) if m else "").lower()
    if suivant in UNITES_FORTES and suivant not in unite.lower():
        return f"{suivant} {unite}".strip()
    return unite


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
    mois = "janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre"
    m = next((x for x in re.finditer(r"(\d[\d  ]*(?:[.,]\d+)?)\s*(%|mm|km/h|km|kg|m|°C|°|ans|morts|blessés|euros|€|dollars|millions|milliards|personnes|habitants)?", t)
              if not re.match(rf"\s*(?:{mois}|h\b)", t[x.end(1):]) and not (re.fullmatch(r"(19|20)\d\d", x.group(1).strip()) and not x.group(2))), None)
    if m:
        reste = t[m.end():].strip(" ,.").split()
        return dict(type="chiffre", valeur=m.group(1).strip(), unite=m.group(2) or (reste[0] if reste and len(reste[0]) < 12 else ""),
                    texte="")
    tous = re.findall(r"[A-Za-zÀ-ÿ'-]{3,}", t)
    # d'abord les noms propres et sigles (NBC, Instagram, Mario), sinon le plus long mot qui n'est pas un verbe conjugué
    propres = [w for k, w in enumerate(tous) if (w.isupper() and len(w) >= 2) or (k and w[0].isupper())]
    noms = sorted([w for w in tous if len(w) >= 5 and w.lower() not in MOTS_VIDES
                   and not re.search(r"(era|erait|ait|aient|ent|ons|ez|ra|é|és|ée|ées)$", w.lower())], key=len, reverse=True)
    mots = (propres or noms)[:2]
    bas = t.lower()
    emoji = next((e for cles, e in PICTOS if any(re.search(r"(?<![a-zà-ÿ])" + re.escape(c.strip()), bas) for c in cles)), "📰")
    return dict(type="icone", emoji=emoji, valeur=(mots[0] if mots else "").upper(), texte="")


PICTOS = [(("police", "gendarm", "arrêt", "interpell"), "🚔"), (("hôpital", "médec", "santé", "malade", "soin"), "🏥"),
          (("tribunal", "juge", "procès", "condamn", "justice"), "⚖️"), (("pluie", "orage", "inond"), "🌧️"), (("vent", "tempête", "rafale"), "💨"), (("défilé", "parade", "fête", "ballon"), "🎈"), (("neige", "froid", "gel"), "❄️"),
          (("feu", "incendie", "brûl", "flamme"), "🔥"), (("voiture", "route", "accident", "camion"), "🚗"), (("avion", "vol ", "aéroport"), "✈️"),
          (("bateau", "navire", "mer ", "cargo"), "🚢"), (("argent", "euro", "prix", "dollar", "coût"), "💶"), (("école", "élève", "université", "étud"), "🎓"),
          (("femme", "fille"), "👩"), (("enfant", "bébé"), "👶"), (("loi", "décret", "règle", "interdi"), "📜"), (("téléphone", "message", "réseau"), "📱"),
          (("jeu vidéo", "jeux vidéo", "console", "gta"), "🎮"), (("animal", "chien", "chat"), "🐾"), (("guerre", "armée", "soldat", "militaire"), "🪖"),
          (("vote", "élection", "président", "gouvernement"), "🏛️"), (("question", "et toi"), "💬")]


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
        elif t == "jauge" and not (_chiffres(str(sc.get("valeur"))) <= connus and _chiffres(str(sc.get("valeur")))):
            raison = f"vitesse « {sc.get('valeur')} » absente du texte et des articles"
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
                # « Middletown, Iowa » : la ville doit être dans le texte, mais on cherche le nom COMPLET (vidéo de l'Iowa du
                # 27/11 : « Middletown » seul → une autre Middletown, dans le nord-est des États-Unis)
                court = nom.split(",")[0].strip()
                if court and court.lower() in (dits + " " + bas).lower():
                    l = (_lieu(nom, cache) if court != nom else None) or _lieu(court, cache)
                    if l:
                        points.append(dict(nom=court, lat=l["lat"], lon=l["lon"]))
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
        elif t in ("calendrier",) and not str(sc.get("jour") or "").strip().isdigit():
            raison = "calendrier sans jour"
        elif t == "calendrier" and not (_chiffres(str(sc.get("jour"))) <= connus):
            raison = "date absente du texte et des articles"
        elif t == "personnes":
            try:
                sc["total"], sc["colores"] = max(2, min(20, int(sc.get("total")))), max(0, min(20, int(sc.get("colores"))))
                sc["colores"] = min(sc["colores"], sc["total"])
            except (TypeError, ValueError):
                raison = "proportion illisible"
        elif t == "icone" and not str(sc.get("emoji") or "").strip():
            raison = "pictogramme sans emoji"
        if t in ("icone", "mot") and re.match(r"(?i)^(d'|l'|de |du |des |le |la |les |un |une |à |au |et )", str(sc.get("valeur") or "")):
            if t == "icone":
                sc["valeur"] = ""                        # « D'ALIMENTER » (27/11) : le pictogramme seul vaut mieux
            else:
                raison = "mot mal choisi"
        if not raison and t == "chiffre":                # unité reprise du texte : « 21,7 » + « millions »
            sc["unite"] = _unite_du_texte(str(sc.get("valeur")), " ".join(script["phrases"][x]["ecrit"] for x in sc["phrases"]),
                                          str(sc.get("unite") or ""))
        for cle, n_ in (("texte", 60), ("valeur", 24), ("titre", 40), ("entete", 40), ("tampon", 14), ("emoji", 8)):
            if isinstance(sc.get(cle), str) and len(sc[cle]) > n_:
                sc[cle] = sc[cle][:n_].rsplit(" ", 1)[0] + ("…" if cle == "texte" else "")
        if not raison and t == "mot" and sum(1 for x in scenes if x["type"] == "mot") >= 2:
            raison = "déjà 2 mots seuls"
        if raison:
            journal(f"  réalisation, phrases {i}-{j} : {raison} → scène de secours")
            for x in range(i, j + 1):                    # une scène sûre par phrase
                scenes.append(dict(_secours(script, x, x), phrases=[x], etiquettes=sc.get("etiquettes") if x == i else None))
            couvertes = j + 1
            continue
        scenes.append(sc)
        couvertes = j + 1
    while couvertes < n:                                # phrases restées sans scène : une scène sûre par phrase
        j = couvertes
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
    lieu = None
    for nom in [str(script.get("lieu") or "").strip(), str(script.get("lieu") or "").split(",")[0].strip()]:   # nom COMPLET d'abord
        if nom and not lieu:
            l_ = _lieu(nom, cache)
            lieu = dict(nom=nom.split(",")[0].strip(), lat=l_["lat"], lon=l_["lon"]) if l_ else None
    nuit = any(sc.get("nuit") for sc in scenes if sc["type"] == "carte") or bool(
        re.search(r"\b(nuit|soir|soirée|minuit|nocturne)\b", " ".join(p["ecrit"] for p in script["phrases"][:4]).lower()))
    return dict(titre=titre, lieu_date=str(d.get("lieu_date") or "")[:40].upper(), source=str(d.get("source") or "")[:110],
                cles=cles, scenes=scenes, lieu=lieu, nuit=nuit)


def _couvre(d, n):
    return len({int(x) for sc in d.get("scenes") or [] if isinstance(sc, dict) for x in sc.get("phrases") or []
                if str(x).isdigit() and int(x) < n})


def realiser(script, articles, journal=print):
    """Storyboard validé (l'IA, sinon uniquement des scènes sûres). L'IA qui oublie des phrases refait une fois (vidéo
    Macy's du 27/11 : 5 scènes pour 15 phrases)."""
    n = len(script["phrases"])
    try:
        d = storyboard(script, articles, journal)
        if _couvre(d, n) < 0.8 * n:
            journal(f"  réalisation : {_couvre(d, n)} phrase(s) sur {n} placées, l'IA recommence")
            d2 = storyboard(script, articles, journal)
            if _couvre(d2, n) > _couvre(d, n):
                d = d2
    except Exception as e:
        journal(f"  réalisation par l'IA impossible ({str(e)[:100]}) : scènes simples")
        d = {}
    return valider(d, script, articles, journal)


# ------------------------------------------------------------------ numéros de phrases → secondes (après la voix)
def _voie_z(voie, voies=6):
    return round(-voies * 3.6 / 2 + (min(max(int(voie or 1), 1), voies) - 0.5) * 3.6, 2)


# un PLAN par étape de l'événement, comme un vrai montage (bonnequestion.tv, curioverse) : la caméra COUPE vers le bon
# angle juste avant chaque action, puis se rapproche doucement. Positions relatives à l'objet suivi (x, hauteur, z).
PLANS = {"avancer": ([-16, 6, 18], [-11, 4.5, 13]), "heurter": ([-20, 5, 17], [-13, 3.5, 11]),
         "se_coucher": ([12, 7, 20], [8, 5, 15]), "deverser": ([-6, 24, 16], [-4, 18, 12]), "bruler": ([-28, 15, 30], [-20, 11, 23]),
         "exploser": ([-48, 26, 52], [-40, 22, 44]), "tomber": ([-34, 12, 32], [-24, 8, 24]), "couler": ([-30, 12, 30], [-22, 9, 22]),
         "secours": ([-30, 16, 30], [-22, 12, 22]), "large": ([-55, 42, 52], [-40, 32, 42]),
         # catastrophes (27/11) : de haut pour voir l'eau monter, la ville trembler, le vent dans les arbres
         "inonder": ([-46, 30, 46], [-36, 24, 38]), "trembler": ([-60, 34, 56], [-50, 28, 48]), "effondrer": ([-48, 26, 50], [-40, 22, 42]),
         "tempete": ([-40, 18, 40], [-32, 15, 32]), "fuir": ([-24, 10, 26], [-18, 8, 20])}
SECOURS_3D = ("police", "ambulance", "pompiers")
GRANDS = {"citerne": 1.7, "camion": 1.6, "bus": 1.6, "train": 2.2, "avion": 2.4, "bateau": 2.4, "batiment": 2.0, "immeuble": 2.4, "entrepot": 2.6,
          "foule": 2.0, "personne": 1.4}


# angles choisis par le scénario (reconstitution.py) → plans de la bibliothèque
CADRES = {"large": "large", "cote": "heurter", "face": "se_coucher", "dessus": "deverser", "suivi": "avancer", "maquette": "maquette",
          "interieur": "interieur"}
PLANS_PLUS = {"maquette": ([-48, 52, 48], [-40, 44, 40]), "interieur": ([1.2, 2.1, 0], [1.2, 2.1, 0])}


def plans_camera(actions, objets, principal, duree, cadres=None, dense=False):
    """Découpage en plans : (début, action) → 2 points de caméra ; plan de 1,4 s au moins, sinon le suivant attend.
    `cadres` = [(début, angle du scénario, objet suivi)] : ces plans-là passent avant les plans automatiques."""
    types = {o["id"]: o.get("type") for o in objets}
    feux = {}
    for x in actions:
        if x["faire"] in ("bruler", "exploser"):
            feux[x["objet"]] = min(feux.get(x["objet"], 1e9), x["a"])
    if cadres:
        imposes = sorted((max(0.0, a - 0.1), CADRES.get(c, c), s) for a, c, s in cadres if c in CADRES or c in PLANS)
        auto = [x for x in plans_camera(actions, objets, principal, duree)[::2] if all(abs(x["a"] - i[0]) > 1.4 for i in imposes)]
        coupes = sorted(imposes + [(x["a"], x["_cle"], x["suivre"]) for x in auto])
        return _cam(coupes, types, duree, dense, feux, principal)
    premier = min((x["a"] for x in actions), default=9.0)
    coupes, dernier = ([(0.0, "large", principal)], 0.0) if premier > 1.4 else ([], -9.0)
    force = {"exploser": 9, "heurter": 8, "tomber": 8, "couler": 7, "bruler": 6, "se_coucher": 5, "deverser": 4}
    # à moments presque égaux, le plus fort d'abord (le choc plutôt que le camion qui roule)
    for x in sorted(actions, key=lambda x: (round(x["a"] / 1.4), -force.get(x["faire"], 0), x["a"])):
        if str(x["objet"]).startswith("bouchon") and x["faire"] == "avancer":
            continue                                    # la file qui se forme se voit dans le plan large / du feu
        cle = "secours" if types.get(x["objet"]) in SECOURS_3D and x["faire"] == "avancer" else x["faire"]
        if cle not in PLANS:
            continue
        if str(x["objet"]).startswith("bouchon"):
            cle, suivre = "bruler", principal
        else:
            suivre = x.get("cible") if x["faire"] == "heurter" and x.get("cible") else x["objet"]
        debut = max(0.0, x["a"] - 0.35)
        if debut - dernier < 1.4 or (coupes and coupes[-1][1:] == (cle, suivre)):
            continue
        coupes.append((debut, cle, suivre)); dernier = debut
    coupes.sort(key=lambda c: c[0])
    return _cam(coupes, types, duree, dense, feux, principal)


def _cam(coupes, types, duree, dense=False, feux=None, principal=None):
    # un objet DÉJÀ en feu n'est jamais filmé de près (Gizeh, 27/11 : plans de la fin au ras du brasier, illisibles)
    feux = feux or {}
    coupes = [(d, "bruler" if c in ("avancer", "heurter", "se_coucher", "interieur", "deraper", "tonneau") and s in feux
               and feux[s] < d - 0.5 else c, s) for d, c, s in coupes]
    if not coupes:                                      # jamais sans caméra (inondation du 27/11 : rendu planté)
        coupes = [(0.0, "large", principal or next(iter(types), None))]
    # jamais plus de 6 s sur le même plan (Gizeh r2, 27/11 : 16 s figées) : on varie l'angle sur ce qu'on filmait
    variantes, plein, k = ("large", "deverser", "secours"), [], 0   # (large, vu de dessus, rapproché)
    for i, (d, c, s_) in enumerate(coupes):
        plein.append((d, c, s_))
        fin = coupes[i + 1][0] if i + 1 < len(coupes) else max(duree, d)
        x = d + 6.0
        while fin - x > 2.0:
            plein.append((round(x, 2), variantes[k % 3] if variantes[k % 3] != c else variantes[(k + 1) % 3], s_)); k += 1; x += 6.0
    coupes = plein
    cam = []
    for k, (debut, cle, suivre) in enumerate(coupes):
        fin = coupes[k + 1][0] - 0.04 if k + 1 < len(coupes) else max(debut + 1.5, duree)
        p0, p1 = PLANS.get(cle) or PLANS_PLUS[cle]
        e = 1.0 if cle == "interieur" else GRANDS.get(types.get(suivre), 1.0)   # un camion-citerne de 12 m : la caméra recule
        if cle != "interieur" and dense:       # usine, ville : on recule et on monte (sinon la caméra entre dans un hangar)
            e *= 1.4
        extra = dict(regard=[30, -0.6, 0]) if cle == "interieur" else {}          # de l'intérieur : on regarde la route devant
        cam.append(dict(a=round(debut, 2), pos=[round(v * e, 1) for v in p0], suivre=suivre, _cle=cle, **extra))
        cam.append(dict(a=round(max(fin, debut + 0.05), 2), pos=[round(v * e, 1) for v in p1], suivre=suivre, _cle=cle, **extra))
    return cam


# ------------------------------------------------------------------ bruitages des reconstitutions (sons/reconstitution, CC0)
EFFETS = {"choc": ("choc.mp3", 0.85), "explosion": ("explosion.mp3", 1.0), "debris": ("debris.mp3", 0.5),
          "feu": ("feu.mp3", 0.30), "sirene": ("sirene.mp3", 0.22)}


def evenements_sonores(sb):
    """Instants des sons de la 3D (en secondes depuis le début de la vidéo) : choc à l'impact, explosion + débris qui
    retombent, feu qui crépite tant que la reconstitution est à l'écran, sirène quand les secours arrivent."""
    scenes, total, out = sb["scenes"], sb["duree"], []
    for k, sc in enumerate(scenes):
        if sc["type"] != "3d":
            continue
        fin_decor = next((x["debut"] for x in scenes[k + 1:] if x["type"] in BASES), total)   # le décor reste jusqu'au suivant
        types = {o["id"]: o.get("type") for o in sc.get("objets") or []}
        feux = []
        for a in sc.get("actions") or []:
            t = sc["debut"] + float(a.get("a") or 0)
            if t >= fin_decor:
                continue
            if a["faire"] == "heurter":
                out.append(dict(son="choc", t=round(t + float(a.get("d") or 1), 2)))
            elif a["faire"] == "exploser":
                out += [dict(son="explosion", t=round(t, 2)), dict(son="debris", t=round(t + 0.9, 2))]
            elif a["faire"] in ("bruler", "deverser") and not str(a["objet"]).startswith("bouchon"):
                feux.append(t)
            elif a["faire"] == "avancer" and types.get(a["objet"]) in ("police", "ambulance", "pompiers") \
                    and not any(e["son"] == "sirene" and abs(e["t"] - t) < 4 for e in out):
                out.append(dict(son="sirene", t=round(t, 2), duree=round(min(8.0, fin_decor - t), 2)))
        if feux:
            out.append(dict(son="feu", t=round(min(feux), 2), duree=round(fin_decor - min(feux), 2)))
    return [e for e in out if 0 <= e["t"] < total and e.get("duree", 1) > 0.3]


def pour_rendu(anim, script, debuts, mots, total, mention_source=""):
    """Storyboard pour rendre.mjs : `debuts` = début de chaque phrase (s), `mots` = [{m, d, f, cle}] de toute la vidéo."""
    scenes = []
    for k, sc in enumerate(anim["scenes"]):
        a = debuts[sc["phrases"][0]]
        b = debuts[sc["phrases"][-1] + 1] if sc["phrases"][-1] + 1 < len(debuts) else total
        s = {k2: v for k2, v in sc.items() if k2 not in ("phrases",)}
        s.update(debut=round(a, 3), fin=round(b, 3))
        quand = lambda x, defaut=0.3: round(max(0.0, debuts[int(x)] - a), 2) if str(x).isdigit() and int(x) < len(debuts) else defaut
        s["etiquettes"] = [dict(texte=str(e if isinstance(e, str) else e.get("texte", ""))[:28].upper(),
                                a=quand(e["phrase"]) + 0.2 if isinstance(e, dict) and "phrase" in e else 0.25 + 0.45 * n,
                                style=(e.get("style") if isinstance(e, dict) else None) or ("rouge" if n == 0 and sc["type"] == "carte" else ""))
                           for n, e in enumerate((sc.get("etiquettes") or [])[:3]) if e]
        if sc["type"] == "carte":
            s["departements"] = [dict(x, a=0.4 + 0.25 * n) for n, x in enumerate(sc.get("departements") or [])]
            s["pays"] = [dict(x, a=0.4 + 0.25 * n) for n, x in enumerate(sc.get("pays") or [])]
            s["points"] = [dict(p, a=1.0 + 0.4 * n) for n, p in enumerate(sc.get("points") or [])]
            s["mention"] = "Images : NASA · Carte : Natural Earth, IGN" + (f" · {mention_source}" if mention_source else "")
            s["nuit"] = bool(sc.get("nuit")) or bool(anim.get("nuit"))
        if sc["type"] == "3d":
            voies = 6 if sc.get("decor") == "autoroute" else 2
            objets = []
            for o in sc["objets"]:
                z = float(o["z"]) if "z" in o else (_voie_z(o.get("voie"), voies) if o.get("type") not in ("batiment", "arbre") else 25.0)
                objets.append(dict(o, x=float(o.get("position") or 0), z=z, y=float(o.get("altitude") or 0)))
            actions = []
            for x in sc["actions"]:
                act = dict(x, a=round(quand(x.get("phrase"), 0.2) + float(x.get("retard") or 0), 2), d=float(x.get("duree") or 1.2))
                o = next((o for o in objets if o["id"] == x["objet"]), {})
                if x["faire"] in ("avancer", "changer_voie", "voler", "tomber") or (x["faire"] in ("freiner", "deraper", "tonneau", "fuir")
                                                                                    and x.get("vers_position") is not None):
                    vx = float(x.get("vers_position", o.get("x", 0) + 40))
                    vz = _voie_z(x.get("vers_voie"), voies) if x.get("vers_voie") else o.get("z", 0)
                    act["vers"] = [vx, vz] + ([float(x.get("altitude", 0))] if x["faire"] in ("voler", "tomber") else [])
                actions.append(act)
            for o in objets:                                # « apparaitre » : invisible jusqu'à sa phrase (barrières, renforts)
                ap = next((x["a"] for x in actions if x["objet"] == o["id"] and x["faire"] == "apparaitre"), None)
                if ap is not None:
                    o["a"] = ap
            s.update(objets=objets, actions=actions, voies=voies)
            s["reperes"] = [dict(objet=r.get("objet"), texte=str(r.get("texte", ""))[:30], a=quand(r.get("phrase"), 0.4))
                            for r in sc.get("reperes") or [] if any(o["id"] == r.get("objet") for o in objets)][:4]
            principal = next((a_["objet"] for a_ in actions if a_["faire"] in ("avancer", "voler", "tomber")), objets[0]["id"])
            forts = ("exploser", "heurter", "bruler", "effondrer", "se_coucher", "tomber", "couler", "deraper", "tonneau")
            cadres = []
            for ph, c in sorted((sc.get("cadres") or {}).items(), key=lambda kv: int(kv[0])):
                if not str(ph).isdigit():
                    continue
                ici = [x for x in actions if str(x.get("phrase")) == str(ph)]
                fort = next((x for f_ in forts for x in ici if x["faire"] == f_), None)   # le moment fort impose son plan
                x = fort or (ici[0] if ici else None)
                suivre = (x.get("cible") if x and x["faire"] == "heurter" else x["objet"]) if x else principal
                cadres.append((quand(ph), fort["faire"] if fort else c, suivre))
            s["camera"] = plans_camera(actions, objets, principal, total - a, cadres, dense=sc.get("decor") in ("usine", "ville", "port"))
            s["mention"] = "Reconstitution · plan simplifié · positions approximatives"   # la source est déjà en bas
        scenes.append(s)
    if scenes and scenes[0]["type"] not in BASES:        # jamais un encadré sur du vide : la carte du lieu dessous
        fin_ = next((x["debut"] for x in scenes if x["type"] in BASES), total)
        lieu = anim.get("lieu")
        scenes.insert(0, dict(type="carte", debut=0, fin=round(fin_, 3), implicite=True, nuit=bool(anim.get("nuit")),
                              zone="monde" if not lieu else None, points=[dict(lieu, a=1.0)] if lieu else [],
                              depart_zoom=8 if lieu else 1.4, zoom_duree=4.0, marge=6 if lieu else 1.2,
                              mention="Images : NASA (Blue Marble)"))
    sb = dict(ips=30, duree=round(total, 3), titre=anim["titre"], lieu_date=anim["lieu_date"], source=anim["source"],
              etiquette=script.get("etiquette") or "BUZZ INSOLITE", mots=mots, scenes=scenes)
    # horloge des faits et chapitres (d'après bonnequestion.tv) : l'heure s'affiche quand la phrase qui la dit commence
    chrono = [dict(a=round(debuts[c["phrase"]], 3), heure=c["heure"], chapitre=c.get("chapitre") or "")
              for c in anim.get("chrono") or [] if isinstance(c.get("phrase"), int) and c["phrase"] < len(debuts)]
    if len(chrono) >= 2:
        sb["chrono"] = chrono
    if anim.get("viseur"):
        sb["viseur"] = anim["viseur"]
        h = re.match(r"(\d{1,2})\s*[h:]\s*(\d{2})?", chrono[0]["heure"]) if chrono else None
        if h:
            sb["viseur_heure"] = int(h.group(1)) * 3600 + int(h.group(2) or 0) * 60
    return sb


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
