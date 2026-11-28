"""CODE DE LA RECONSTITUTION (27/11, demande de l'auteur : « invente toutes les règles possibles et inimaginables pour tous les
événements futurs »). Appliqué à CHAQUE scène 3D de CHAQUE vidéo, quelle que soit la façon dont elle a été écrite (modèle fixe,
scénario de l'IA, IA réalisatrice, accroche), AVANT le rendu et avant le réalisateur critique, puis une 2e fois après lui.

Principe : une règle ne fait que des corrections SÛRES (retirer une action impossible, remettre une cause avant sa conséquence,
écarter deux objets qui se chevauchent). Les 4 règles de « décence » (D1 à D4) ont été RETIRÉES à la demande de
l'auteur (27/11). Une règle n'invente jamais un fait.
Chaque correction est écrite dans le journal (« 📐 règle P3 : … »).

Les familles de règles :
  P = physique (ce que chaque objet sait faire)      C = chronologie et causalité (cause avant conséquence, rien après la fin)
  E = espace (personne dans un mur, bateau sur l'autoroute)
  L = lisibilité (pas trop de choses à la fois)      V = vraisemblance des secours, du feu et des dégâts
La liste complète, numérotée, est dans REGLES (en bas) : c'est elle que lisent les tests et le site.
"""
import re

ROUTIERS = ("voiture", "camion", "citerne", "bus", "moto", "camionnette", "taxi", "police", "ambulance", "pompiers", "bulldozer")
VEHICULES = ROUTIERS + ("train", "avion", "helico", "bateau")
AERIENS = ("avion", "helico")
BATIS = ("batiment", "entrepot", "immeuble", "maison", "batiment_officiel", "hopital", "banque", "magasin", "residence")
FIXES = BATIS + ("arbre", "muret", "mur", "feu_tricolore", "panneau")
HUMAINS = ("personne", "foule")
LIQUIDES = ("citerne", "camion", "bateau", "train", "entrepot")          # ce qui peut perdre un liquide (fuite, flaque)
SECOURS = ("police", "ambulance", "pompiers")
BOUGER = ("avancer", "freiner", "deraper", "changer_voie", "tonneau", "fuir", "voler", "heurter")
DETRUIT = ("exploser", "couler", "effondrer")                            # après : l'objet ne fait plus rien (sauf brûler)
FORTS = ("heurter", "exploser", "bruler", "tomber", "couler", "se_coucher", "effondrer", "deverser")
DECORS_EAU = ("mer", "port", "plage")
DECORS_ROUTE = ("autoroute", "route", "ville")
# ce que le texte dit des témoins / de la foule (règle C11), et de la route qui rouvre (règle V9)
FOULE = r"foule|rassembl|badaud|t[ée]moin|passant|curieux|spectateur|habitant|riverain|famille|proche|personnes? (?:pr[ée]sentes|sur place)"
REOUVERT = r"rouvert|r[ée]ouvert|r[ée]ouverture|circulation (?:a |)(?:repris|reprend|r[ée]tablie)|trafic (?:a |)(?:repris|reprend|r[ée]tabli)"
# encombrement au sol (m) : longueur d'un véhicule, largeur d'un bâtiment (règles E1, E2)
TAILLE = {"voiture": 4.5, "taxi": 4.5, "police": 4.8, "moto": 2.2, "camionnette": 5.5, "bulldozer": 6.2, "ambulance": 6, "pompiers": 9, "camion": 10,
          "citerne": 12, "bus": 12, "train": 40, "bateau": 20, "batiment": 30, "entrepot": 46, "immeuble": 24, "residence": 24,
          "hopital": 30, "banque": 20, "magasin": 18, "maison": 14, "batiment_officiel": 34}

# qui peut faire quoi (règles P1 à P11)
PEUT = {
    "voler": lambda t: t in AERIENS,
    "tomber": lambda t: t in AERIENS or t in HUMAINS or t in ("arbre", "panneau", "feu_tricolore"),
    "couler": lambda t: t == "bateau",
    "fuir": lambda t: t in HUMAINS,
    "arroser": lambda t: t in ("pompiers", "helico"),
    "freiner": lambda t: t in ROUTIERS or t == "train",
    "deraper": lambda t: t in ROUTIERS,
    "changer_voie": lambda t: t in ROUTIERS,
    "tonneau": lambda t: t in ROUTIERS,
    "avancer": lambda t: t not in FIXES,
    "heurter": lambda t: t in VEHICULES,
    "deverser": lambda t: t in LIQUIDES,
    "effondrer": lambda t: t in BATIS,
    "se_coucher": lambda t: t in VEHICULES or t in HUMAINS or t in ("arbre", "panneau", "feu_tricolore"),
}
REMPLACE = {("effondrer", "v"): "se_coucher", ("se_coucher", "b"): "effondrer", ("tomber", "v"): "se_coucher",
            ("effondrer", "h"): "se_coucher"}

REGLES = [
    ("P1", "Seuls l'avion et l'hélicoptère volent ; aucun véhicule, bâtiment ou personne ne monte en l'air."),
    ("P2", "Seul un bateau coule ; une voiture emportée par l'eau flotte (inondation), elle ne « coule » pas."),
    ("P3", "Seules les personnes et la foule s'enfuient en courant."),
    ("P4", "Seuls les pompiers (ou un hélicoptère bombardier d'eau) arrosent."),
    ("P5", "Freiner, déraper, changer de voie, faire des tonneaux : seulement les véhicules de la route (freiner : le train aussi)."),
    ("P6", "Un bâtiment, un arbre, un mur, un panneau ne se déplacent jamais."),
    ("P7", "Seul un véhicule en percute un autre ; un bâtiment ou un arbre ne « percute » rien (c'est le véhicule qui le heurte)."),
    ("P8", "Seul ce qui transporte un liquide fuit (citerne, camion, bateau, train, dépôt)."),
    ("P9", "Un bâtiment s'effondre, un véhicule se renverse : l'action est convertie si elle est donnée à l'autre."),
    ("P10", "L'altitude d'un objet au sol est toujours 0 ; un avion ou un hélicoptère qui vole est au-dessus de 15 m."),
    ("P11", "Un objet ne se percute pas lui-même ; une cible doit exister dans la scène."),
    ("C1", "Rien n'agit après sa destruction : un objet explosé, coulé ou effondré ne roule plus, ne freine plus, ne percute plus."),
    ("C2", "Un objet renversé ne roule plus (il peut encore fuir, brûler ou exploser)."),
    ("C3", "Une cause avant sa conséquence : un choc raconté après que sa cible a brûlé, fui, s'est renversée ou a été détruite est remis juste avant."),
    ("C4", "Dans la même phrase, la conséquence (renversement, fuite, feu, explosion) commence APRÈS l'impact."),
    ("C5", "Un objet n'explose qu'une fois, ne coule qu'une fois, ne s'effondre qu'une fois."),
    ("C6", "Les secours n'arrivent pas avant l'événement : ils arrivent au moment du premier fait marquant, ou après."),
    ("C7", "Les pompiers arrosent un feu qui existe : l'arrosage commence quand le feu a pris."),
    ("C8", "La foule s'enfuit après le danger (choc, feu, explosion, effondrement), jamais avant."),
    ("C9", "Une même action n'est pas répétée par le même objet dans la même phrase."),
    ("C10", "Un véhicule accidenté (qui a percuté ou été percuté) ne repart plus : ni avancer, ni freiner, ni déraper ensuite."),
    ("E1", "Deux véhicules ne se chevauchent jamais au départ sur la même voie (selon leur longueur réelle, 1,5 m d'écart)."),
    ("E2", "Deux bâtiments ne se chevauchent jamais (selon leur largeur réelle) ; un bâtiment n'est jamais sur la chaussée."),
    ("E3", "Un piéton ou une foule n'est jamais sur la chaussée (trottoir, foule resserrée au bord de la route), sauf s'il traverse."),
    ("E4", "Un bateau seul sur une route : le décor devient un port ; un train : la voie ferrée ; un avion qui s'écrase : la campagne."),
    ("E5", "Les secours se garent sur la voie de droite, à distance du feu ou de l'explosion (jamais dedans)."),
    ("E6", "Les positions restent dans la scène filmée (entre -400 m et +200 m)."),
    ("L1", "Au plus 4 actions fortes en même temps dans une phrase : les autres sont étalées d'une demi-seconde chacune."),
    ("L2", "Au plus 3 explosions par scène (les autres deviennent des feux), au plus 12 grands feux (les autres ont des flammes simples)."),
    ("L3", "Au plus 14 objets à l'écran ; on retire d'abord ceux qui ne font rien et n'ont pas de rôle."),
    ("L4", "Chaque action dure entre 0,6 et 8 s et commence au plus 4 s après le début de sa phrase."),
    ("L5", "Au plus 3 repères écrits, seulement pour des objets présents."),
    ("V1", "Un objet qui explose brûle ensuite (l'épave fume) ; un feu suit toujours une explosion."),
    ("V2", "Une citerne percutée se déchire et perd son carburant juste après l'impact."),
    ("V3", "Une citerne qui brûle a d'abord perdu son carburant (flaque qui s'enflamme)."),
    ("V4", "Les dégâts d'un choc dépendent du poids : le plus léger encaisse le plus (moteur 3D, MASSES)."),
    ("V5", "Un objet dans le souffle d'une explosion (18 m) est repoussé et prend feu (moteur 3D)."),
    ("V6", "Un feu s'ÉTEINT quand le texte le dit (feu maîtrisé, éteint, carcasses retirées, route rouverte) : flammes qui baissent, épave qui fume."),
    ("V7", "Un véhicule qui se renverse ne prend feu qu'une fois couché : on voit le renversement, puis le feu."),
    ("C11", "Une foule, un témoin, un engin de chantier n'apparaissent qu'au moment où le texte en parle (jamais dans l'accroche)."),
    ("V8", "Un bulldozer qui dégage les carcasses va jusqu'à l'épave principale."),
    ("V9", "Route ROUVERTE (quand le texte le dit) : épaves, foule, engins et secours sont enlevés, la circulation reprend sur toutes les voies."),
]


def _t(a):
    """Moment relatif d'une action (phrase, puis retard)."""
    return (int(a.get("phrase") or 0), float(a.get("retard") or 0))


def _fin(a):
    p, r = _t(a)
    return (p, r + float(a.get("duree") or 1.0))


EXTINCTION = (r"ma[îi]tris|[ée]teint|extinction|carcasses?|calcin[ée]+s? (?:sont|ont été|des)|d[ée]blay|bulldozer|d[ée]panneu"
              r"|rouvert|r[ée]ouvert|circulation (?:a repris|reprend|r[ée]tablie)|trafic (?:a repris|reprend|r[ée]tabli)")


def appliquer(sc, journal=print, texte="", phrases=None):
    """Applique toutes les règles à une scène 3D (modifiée sur place). Renvoie la liste des corrections faites."""
    if not isinstance(sc, dict) or sc.get("type") != "3d":
        return []
    faits = []

    def note(code, msg):
        faits.append(f"{code} : {msg}")

    objets = [o for o in sc.get("objets") or [] if isinstance(o, dict) and o.get("id")]
    types = {o["id"]: o.get("type", "") for o in objets}
    actions = [a for a in sc.get("actions") or [] if isinstance(a, dict) and a.get("objet") in types]

    # ---- P : ce que chaque objet sait faire
    propres = []
    for a in actions:
        t, f = types[a["objet"]], a.get("faire")
        if f in ("heurter", "arroser") and (a.get("cible") not in types or a.get("cible") == a["objet"]):
            note("P11", f"{a['objet']} {f} sans cible valable → retiré"); continue
        if f in PEUT and not PEUT[f](t):
            nouveau = REMPLACE.get((f, "v" if t in VEHICULES else "b" if t in BATIS else "h" if t in HUMAINS else ""))
            if nouveau and PEUT[nouveau](t):
                note("P9", f"{t} « {f} » → « {nouveau} »"); a["faire"] = nouveau
            else:
                code = {"voler": "P1", "tomber": "P1", "couler": "P2", "fuir": "P3", "arroser": "P4", "heurter": "P7",
                        "deverser": "P8", "avancer": "P6"}.get(f, "P5")
                note(code, f"{t} ne peut pas « {f} » → retiré"); continue
        propres.append(a)
    actions = propres
    for o in objets:                                                     # P10
        t = o.get("type")
        if t not in AERIENS and float(o.get("altitude") or 0) != 0:
            note("P10", f"{t} posé au sol (altitude {o.get('altitude')})"); o["altitude"] = 0
    for a in actions:
        if a.get("faire") == "voler" and a.get("altitude") is not None and float(a["altitude"]) < 15:
            a["altitude"] = 15

    # ---- C5 / C9 : pas de doublon
    vus, uniques = set(), []
    for a in sorted(actions, key=_t):
        cle_vie = (a["objet"], a["faire"]) if a["faire"] in DETRUIT + ("se_coucher", "bruler") else None
        cle = (a["objet"], a["faire"], a.get("phrase"), a.get("cible"))
        if cle in vus or (cle_vie and cle_vie in vus):
            note("C5" if cle_vie else "C9", f"{a['objet']} « {a['faire']} » en double → retiré"); continue
        vus.add(cle)
        if cle_vie:
            vus.add(cle_vie)
        uniques.append(a)
    actions = uniques

    # ---- C3 / C4 : la cause avant la conséquence
    for h in [a for a in actions if a["faire"] == "heurter"]:
        fin_cible = [a for a in actions if a["objet"] == h["cible"] and a["faire"] in DETRUIT + ("se_coucher", "bruler", "deverser")
                     and _t(a) < _t(h)]                   # (Gizeh r3 : collision racontée à la fin, citerne déjà en feu)
        if fin_cible:
            premier = min(fin_cible, key=_t)
            note("C3", f"choc de {h['objet']} remis avant « {premier['faire']} » de {h['cible']}")
            h["phrase"], h["retard"] = premier["phrase"], max(0.0, float(premier.get("retard") or 0) - float(h.get("duree") or 2.2) - 0.3)
        for a in actions:
            if a["objet"] == h["cible"] and a.get("phrase") == h.get("phrase") and a["faire"] in ("se_coucher", "bruler", "exploser", "deverser",
                                                                                                 "tonneau", "deraper") and _t(a) < _fin(h):
                a["retard"] = round(_fin(h)[1] + 0.3, 2)
                note("C4", f"{a['objet']} « {a['faire']} » après l'impact")

    # ---- C1 / C2 : rien après la fin
    gardees = []
    for a in actions:
        fins = [x for x in actions if x["objet"] == a["objet"] and x is not a and _t(x) < _t(a)]
        if a["faire"] in BOUGER and any(x["faire"] in DETRUIT for x in fins):
            note("C1", f"{a['objet']} « {a['faire']} » après sa destruction → retiré"); continue
        if a["faire"] in BOUGER and a["faire"] != "fuir" and any(x["faire"] == "se_coucher" for x in fins):
            note("C2", f"{a['objet']} « {a['faire']} » une fois renversé → retiré"); continue
        if a["faire"] in BOUGER and a["faire"] != "heurter" and not sc.get("accroche") and any(
                x["faire"] == "heurter" and (x["objet"] == a["objet"] or x.get("cible") == a["objet"]) and _fin(x) <= _t(a)
                for x in actions):            # (Gizeh r4 : la voiture du choc « repartait » pendant les aveux du conducteur)
            note("C10", f"{a['objet']} « {a['faire']} » après l'accident → retiré"); continue
        gardees.append(a)
    actions = gardees

    # ---- C6 / C7 / C8 : secours, arrosage et fuite après le danger
    danger = [a for a in actions if a["faire"] in FORTS and types[a["objet"]] not in SECOURS]
    t0 = min((_t(a) for a in danger), default=None)
    for a in actions:
        t = types[a["objet"]]
        if t0 and t in SECOURS and a["faire"] in ("avancer", "arroser") and _t(a) < t0:
            note("C6", f"{t} arrive au moment de l'événement, pas avant")
            a["phrase"], a["retard"] = t0[0], t0[1] + 1.5
        if t0 and t in HUMAINS and a["faire"] == "fuir" and _t(a) < t0:
            note("C8", f"{a['objet']} s'enfuit après le danger")
            a["phrase"], a["retard"] = t0[0], t0[1] + 0.8
        if a["faire"] == "arroser":
            feu = [x for x in actions if x["objet"] == a.get("cible") and x["faire"] in ("bruler", "exploser")]
            if feu and _t(a) < min(_t(x) for x in feu):
                f0 = min(feu, key=_t)
                note("C7", "les pompiers arrosent une fois le feu pris")
                a["phrase"], a["retard"] = f0["phrase"], float(f0.get("retard") or 0) + 1.5

    # ---- V1 / V3 : feu après explosion, fuite avant le feu d'une citerne
    for a in [x for x in actions if x["faire"] == "exploser"]:
        if not any(x["objet"] == a["objet"] and x["faire"] == "bruler" for x in actions):
            actions.append(dict(objet=a["objet"], faire="bruler", phrase=a["phrase"], duree=1.0, retard=float(a.get("retard") or 0) + 0.4))
            note("V1", f"{a['objet']} brûle après son explosion")
    for a in [x for x in actions if x["faire"] == "bruler" and types[x["objet"]] == "citerne"]:
        if not any(x["objet"] == a["objet"] and x["faire"] == "deverser" for x in actions):
            actions.append(dict(objet=a["objet"], faire="deverser", phrase=a["phrase"], duree=2.0, retard=max(0.0, float(a.get("retard") or 0) - 0.2)))
            note("V3", "la citerne perd son carburant avant de brûler")

    # ---- L2 : pas trop d'explosions ni de feux
    expl = sorted([a for a in actions if a["faire"] == "exploser"], key=_t)
    if len(expl) > 3:
        for a in expl[3:]:
            a["faire"] = "bruler"
        note("L2", f"{len(expl) - 3} explosion(s) de trop → feu")

    # ---- V7 : le renversement se voit AVANT le feu (Gizeh r4 du 28/11 : feu et renversement au même instant, la boule de
    # feu cachait la citerne qui bascule)
    for c in [x for x in actions if x["faire"] == "se_coucher"]:
        for a in actions:
            if a["objet"] == c["objet"] and a["faire"] in ("bruler", "exploser") and a.get("phrase") == c.get("phrase"):
                apres = float(c.get("retard") or 0) + float(c.get("duree") or 1.0) * (0.7 if sc.get("accroche") else 1.0) \
                        + (0.1 if sc.get("accroche") else 0.8)
                if float(a.get("retard") or 0) < apres:
                    a["retard"] = round(apres, 2); note("V7", f"{a['objet']} prend feu une fois renversé")

    # ---- V6 : le feu s'éteint quand le texte le dit (Gizeh r4 : « la route est rouverte » sur une épave toujours en flammes)
    if phrases and not sc.get("accroche") and not any(a["faire"] == "eteindre" for a in actions):
        feux = [a for a in actions if a["faire"] in ("bruler", "exploser")]
        dernier = max((int(a.get("phrase") or 0) for a in feux), default=None)
        ph = None if dernier is None else next((i for i, p in enumerate(phrases) if i > dernier
                                                and re.search(EXTINCTION, str(p).lower())), None)
        if ph is not None:
            for k, oid in enumerate(sorted({a["objet"] for a in feux})):
                actions.append(dict(objet=oid, faire="eteindre", phrase=ph, duree=3.0, retard=round(0.15 * k, 2)))
            note("V6", f"feu éteint à la phrase {ph}")

    # ---- C11 : la foule, les témoins, le bulldozer n'apparaissent qu'à leur phrase (Gizeh r5 du 28/11 : la « foule rassemblée »
    # de la phrase 9 était sur l'autoroute dès la 1re seconde, pendant le choc)
    danger = [a for a in actions if a["faire"] in FORTS and types[a["objet"]] not in SECOURS]
    if danger and not re.search(r"manifest|rassemblement de|cort[èe]ge|marche", texte.lower()):
        ph_danger = min(int(a.get("phrase") or 0) for a in danger)
        acteurs_drame = {a["objet"] for a in danger} | {a.get("cible") for a in danger if a.get("cible")} | \
                        {a["objet"] for a in actions if a["faire"] == "fuir"}
        for o in list(objets):
            if o.get("type") not in HUMAINS + ("bulldozer",) or o["id"] in acteurs_drame:
                continue
            if any(a["objet"] == o["id"] and a["faire"] == "apparaitre" for a in actions):
                continue
            if sc.get("accroche"):
                objets.remove(o); actions = [a for a in actions if a["objet"] != o["id"]]
                note("C11", f"{o['id']} retiré de l'accroche"); continue
            motif = FOULE if o.get("type") in HUMAINS else r"bulldozer|engin|pelleteuse|d[ée]blai|d[ée]gag|carcasse|grue"
            parle = next((i for i, p in enumerate(phrases or []) if i >= ph_danger and re.search(motif, str(p).lower())), None)
            siennes = [int(a.get("phrase") or 0) for a in actions if a["objet"] == o["id"]]
            # sa propre 1re action d'abord (les techniciens arrivent à LEUR phrase), sinon la phrase qui en parle
            ph = min(siennes) if siennes else (parle if parle is not None else ph_danger + 1)
            actions.append(dict(objet=o["id"], faire="apparaitre", phrase=ph, duree=0.6, retard=0.0))
            note("C11", f"{o['id']} apparaît à la phrase {ph}")

    # ---- V8 : le bulldozer va jusqu'à l'épave principale (r5 : il « dégageait » une carcasse à 30 m de lui)
    par_id = {o["id"]: o for o in objets}

    def fin_x(o):
        x = float(o.get("position") or 0)
        for a in sorted(actions, key=_t):
            if a["objet"] == o["id"] and a["faire"] == "avancer" and a.get("vers_position") is not None:
                x = float(a["vers_position"])
        return x
    # l'épave la plus en arrière sur la voie de l'accident : celui qui a percuté (collé derrière sa cible), sinon la 1re touchée
    choc = next((a for a in sorted(danger, key=_t) if a["faire"] == "heurter" and a.get("cible") in par_id and a["objet"] in par_id), None)
    if choc:
        c, f = par_id[choc["cible"]], par_id[choc["objet"]]
        epave, pos = f, fin_x(c) - (TAILLE.get(c.get("type"), 6) + TAILLE.get(f.get("type"), 6)) / 2 - 1.5
        voie = c.get("voie")
    else:
        e = next((par_id[a["objet"]] for a in sorted(danger, key=_t) if types[a["objet"]] in VEHICULES + BATIS), None)
        epave, pos, voie = e, fin_x(e) if e else 0.0, (e or {}).get("voie")
    if epave and voie is not None and epave.get("z") is None:
        # places prises à la fin (véhicules de la route) : l'engin apparaît sur une place LIBRE près de l'épave, puis avance
        # doucement de 4 m vers elle (r5 : il traversait les voitures du bouchon pour venir de loin)
        prises = [(voie, pos, TAILLE.get(o.get("type"), 6)) if o is epave and choc else (o.get("voie"), fin_x(o), TAILLE.get(o.get("type"), 6))
                  for o in objets if o.get("type") in ROUTIERS and o.get("type") != "bulldozer" and o.get("z") is None]
        libre = lambda v, x: not any(vo == v and abs(x - xo) < (6.2 + lo) / 2 + 1 for vo, xo, lo in prises)
        bout = pos - TAILLE.get(epave.get("type"), 6) / 2
        candidats = [(voie, bout - 3.2 - d) for d in (0, 2, 4)] + [(v, pos - d) for d in range(0, 16, 3) for v in (1, 2, 3) if v != voie] + \
                    [(voie, bout - 3.2 - d) for d in range(6, 40, 3)]
        for o in [o for o in objets if o.get("type") == "bulldozer"]:
            mes = [a for a in actions if a["objet"] == o["id"] and a["faire"] == "avancer"]
            v, x = next(((v, x) for v, x in candidats if libre(v, x)), (voie, bout - 3.2))
            o.update(voie=v, position=round(x - 4, 1))
            if mes:
                mes[0].update(vers_position=round(x, 1), duree=4.0); mes[0].pop("vers_voie", None)
                for a in mes[1:]:
                    actions.remove(a)
            prises.append((v, x, 6.2))
            note("V8", f"{o['id']} près de l'épave {epave['id']} (voie {v})")

    # ---- V9 : la route ROUVERTE (r5 : épaves, foule et secours toujours sur la chaussée, aucune circulation)
    if phrases and not sc.get("accroche") and danger and sc.get("decor") in DECORS_ROUTE:
        dernier = max(int(a.get("phrase") or 0) for a in danger)
        ph = next((i for i, p in enumerate(phrases) if i > dernier and re.search(REOUVERT, str(p).lower())), None)
        if ph is not None:
            nouveaux = []
            for o in objets:
                mes = [a for a in actions if a["objet"] == o["id"]]
                if o.get("type") in FIXES or any(int(a.get("phrase") or 0) >= ph for a in mes):
                    continue                     # bâtiments, ou ce qui agit encore (la circulation qui reprend)
                if mes or o.get("type") in HUMAINS + SECOURS + ("bulldozer",):
                    nouveaux.append(dict(objet=o["id"], faire="disparaitre", phrase=ph, duree=0.6, retard=0.05))
            if nouveaux:
                actions += nouveaux; sc["rouvert"] = ph
                note("V9", f"route rouverte à la phrase {ph} : {len(nouveaux)} objet(s) enlevé(s), la circulation reprend")

    # ---- L1 / L4 : rythme
    par_phrase = {}
    for a in sorted(actions, key=_t):
        par_phrase.setdefault(a.get("phrase"), []).append(a)
    for p, liste in ([] if sc.get("accroche") else par_phrase.items()):   # (l'accroche a son propre rythme serré)
        debuts, etalees = [], 0
        for a in sorted([a for a in liste if a["faire"] not in ("avancer", "eteindre", "apparaitre", "disparaitre")], key=_t):
            r = float(a.get("retard") or 0)
            while sum(1 for d in debuts if abs(d - r) < 0.3) >= 4:          # 4 débuts au plus dans la même demi-seconde
                r += 0.5; etalees += 1
            if r != float(a.get("retard") or 0):
                a["retard"] = min(4.5, r)
            debuts.append(r)
        if etalees:
            note("L1", f"phrase {p} : trop d'actions au même instant → étalées")
    for a in actions:
        d = float(a.get("duree") or 1.0)
        if not 0.6 <= d <= 8:
            a["duree"] = min(8.0, max(0.6, d))
        if float(a.get("retard") or 0) > 4.5:
            a["retard"] = 4.5

    # ---- E : l'espace
    voies, batis = {}, []
    taille = lambda t: TAILLE.get(t, 6)
    for o in objets:
        t = o.get("type")
        if o.get("position") is not None:
            o["position"] = max(-400.0, min(200.0, float(o["position"])))
        if t in BATIS:
            if o.get("z") is not None and abs(float(o["z"])) < 12 and sc.get("decor") not in ("usine", "place"):
                o["z"] = -26; note("E2", f"{o['id']} retiré de la chaussée")
            pos, z, l = float(o.get("position") or 0), float(o.get("z") or 0), taille(t)
            while any(abs(pos - x) < (l + lx) / 2 + 2 and abs(z - zx) < 20 for x, zx, lx in batis):
                pos += l / 2 + 4
            if pos != float(o.get("position") or 0):
                note("E2", f"{o['id']} écarté des autres bâtiments"); o["position"] = pos
            batis.append((pos, z, l))
        elif t in VEHICULES and t not in AERIENS and o.get("z") is None:
            prises = voies.setdefault(o.get("voie", 1), [])
            pos, l = float(o.get("position") or 0), taille(t)
            while any(abs(pos - x) < (l + lx) / 2 + 1.5 for x, lx in prises):
                pos -= 2
            if pos != float(o.get("position") or 0):
                note("E1", f"{o['id']} n'est plus sur un autre véhicule"); o["position"] = pos
            prises.append((pos, l))
        elif t in HUMAINS and not any(a["objet"] == o["id"] and a["faire"] in ("avancer", "fuir") for a in actions):
            if sc.get("decor") in DECORS_ROUTE:
                # (Gizeh r5 du 28/11 : une foule de 9 m de rayon au milieu de l'autoroute pendant toute la vidéo)
                demi = (6 if sc.get("decor") == "autoroute" else 2) * 3.6 / 2
                if t == "foule":
                    o["rayon"] = min(float(o.get("rayon") or 9), 4.5); o["nombre"] = min(int(o.get("nombre") or 50), 40)
                bord = demi + 1.8 + (o["rayon"] if t == "foule" else 0)
                z = o.get("z")
                if z is None or abs(float(z)) < bord:
                    o["z"] = round(bord if z is None or float(z) >= 0 else -bord, 1); note("E3", f"{o['id']} au bord de la route")
            elif o.get("z") is None and o.get("voie") is not None:
                o["z"] = 9 if t == "personne" else 10; note("E3", f"{o['id']} sur le trottoir")
    present = set(types.values())
    decor = sc.get("decor")
    principal = next((types[a["objet"]] for a in sorted(actions, key=_t) if a["faire"] in FORTS), None)
    if "bateau" in present and decor not in DECORS_EAU and principal == "bateau":
        sc["decor"] = "port"; note("E4", "bateau : décor du port")
    elif "train" in present and decor != "voie_ferree" and principal == "train":
        sc["decor"] = "voie_ferree"; note("E4", "train : voie ferrée")
    elif principal == "avion" and decor in ("autoroute", "route", "ville") and any(a["faire"] == "tomber" for a in actions):
        sc["decor"] = "campagne"; note("E4", "avion qui s'écrase : campagne")
    def place_finale(o):                 # (Gizeh r5 du 28/11 : le bouchon partait de -160 mais brûlait vers -20 → les
        x = float(o.get("position") or 0)  # ambulances s'arrêtaient en plein feu)
        for a in sorted(actions, key=_t):
            if a["objet"] == o["id"] and a["faire"] == "avancer" and a.get("vers_position") is not None:
                x = float(a["vers_position"])
        return x
    danger_pos = [place_finale(o) for o in objets
                  if any(a["objet"] == o["id"] and a["faire"] in ("exploser", "bruler") for a in actions) and o.get("type") not in SECOURS]
    for a in actions:                                                    # E5
        if types[a["objet"]] in SECOURS and a["faire"] == "avancer" and a.get("vers_position") is not None and danger_pos:
            vp, depart = float(a["vers_position"]), float(next(o for o in objets if o["id"] == a["objet"]).get("position") or 0)
            # les secours arrivent de derrière : ils s'arrêtent 18 m avant le PREMIER feu qu'ils rencontrent
            devant = [x for x in danger_pos if x > depart]
            limite = (min(devant) if devant else min(danger_pos, key=lambda x: abs(x - vp))) - 18
            if vp > limite or any(abs(vp - x) < 16 for x in danger_pos):
                a["vers_position"] = round(limite, 1); note("E5", f"{a['objet']} s'arrête à distance du feu")

    # ---- L3 / L5 : pas trop d'objets, repères utiles
    actifs = {a["objet"] for a in actions} | {a.get("cible") for a in actions if a.get("cible")}
    if len(objets) > 14:
        inutiles = [o for o in objets if o["id"] not in actifs and not str(o.get("role") or "")][:len(objets) - 14]
        for o in inutiles:
            objets.remove(o)
        if inutiles:
            note("L3", f"{len(inutiles)} objet(s) inutile(s) retiré(s)")
    ids = {o["id"] for o in objets}
    actions = [a for a in actions if a["objet"] in ids and (not a.get("cible") or a["cible"] in ids)]
    sc["reperes"] = [r for r in sc.get("reperes") or [] if isinstance(r, dict) and r.get("objet") in ids][:3]

    sc["objets"], sc["actions"] = objets, sorted(actions, key=_t)
    for x in faits:
        journal(f"  📐 règle {x}")
    return faits


def appliquer_storyboard(anim, script, journal=print):
    """Toutes les scènes 3D d'un storyboard. Renvoie le nombre de corrections."""
    phrases = [p.get("ecrit", "") for p in (script or {}).get("phrases") or []]
    texte = " ".join(phrases)
    n = 0
    for sc in (anim or {}).get("scenes") or []:
        n += len(appliquer(sc, journal, texte, phrases))
    return n
