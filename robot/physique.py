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

ROUTIERS = ("voiture", "camion", "citerne", "bus", "moto", "camionnette", "taxi", "police", "ambulance", "pompiers")
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
# encombrement au sol (m) : longueur d'un véhicule, largeur d'un bâtiment (règles E1, E2)
TAILLE = {"voiture": 4.5, "taxi": 4.5, "police": 4.8, "moto": 2.2, "camionnette": 5.5, "ambulance": 6, "pompiers": 9, "camion": 10,
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
    ("E1", "Deux véhicules ne se chevauchent jamais au départ sur la même voie (selon leur longueur réelle, 1,5 m d'écart)."),
    ("E2", "Deux bâtiments ne se chevauchent jamais (selon leur largeur réelle) ; un bâtiment n'est jamais sur la chaussée."),
    ("E3", "Un piéton ou une foule n'est pas sur la chaussée au départ (trottoir), sauf s'il traverse."),
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
]


def _t(a):
    """Moment relatif d'une action (phrase, puis retard)."""
    return (int(a.get("phrase") or 0), float(a.get("retard") or 0))


def _fin(a):
    p, r = _t(a)
    return (p, r + float(a.get("duree") or 1.0))


def appliquer(sc, journal=print, texte=""):
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

    # ---- L1 / L4 : rythme
    par_phrase = {}
    for a in sorted(actions, key=_t):
        par_phrase.setdefault(a.get("phrase"), []).append(a)
    for p, liste in ([] if sc.get("accroche") else par_phrase.items()):   # (l'accroche a son propre rythme serré)
        debuts, etalees = [], 0
        for a in sorted([a for a in liste if a["faire"] != "avancer"], key=_t):
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
        elif t in HUMAINS and o.get("z") is None and o.get("voie") is not None:
            if not any(a["objet"] == o["id"] and a["faire"] in ("avancer",) for a in actions):
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
    danger_pos = [float(o.get("position") or 0) for o in objets
                  if any(a["objet"] == o["id"] and a["faire"] in ("exploser", "bruler") for a in actions) and o.get("type") not in SECOURS]
    for a in actions:                                                    # E5
        if types[a["objet"]] in SECOURS and a["faire"] == "avancer" and a.get("vers_position") is not None and danger_pos:
            vp = float(a["vers_position"])
            proche = min(danger_pos, key=lambda x: abs(x - vp))
            if abs(vp - proche) < 16:
                a["vers_position"] = proche - 18; note("E5", f"{a['objet']} s'arrête à distance du feu")

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
    texte = " ".join(p.get("ecrit", "") for p in (script or {}).get("phrases") or [])
    n = 0
    for sc in (anim or {}).get("scenes") or []:
        n += len(appliquer(sc, journal, texte))
    return n
