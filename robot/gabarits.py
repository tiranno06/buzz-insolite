"""Modèles de vidéo FIXES par type d'actualité (demande de l'auteur du 27/11 : « exactement le même type de vidéo » que
curioverse.actu et vudenhaut.fr).

Les 4 premières vidéos du nouveau style l'ont montré : une petite IA gratuite ne sait pas inventer une bonne mise en scène
(10 pictogrammes sur 15 scènes, jamais de 3D). Ici l'IA ne fait plus qu'une tâche SIMPLE et vérifiable : extraire les faits
(type d'événement, lieu, qui fait quoi dans l'ordre, 3 chiffres clés). C'est le ROBOT qui compose la vidéo, toujours avec
la même recette soignée :
  1. accroche : la Terre vue du ciel qui plonge sur le lieu (carte satellite NASA, de nuit si les faits sont de nuit) ;
  2. reconstitution 3D de l'événement avec les vrais modèles (accident, incendie, crash, naufrage, manifestation…),
     chaque action calée sur la phrase qui la raconte, repères « une voiture », « le camion-citerne » ;
  3. les chiffres clés en ENCADRÉS par-dessus le décor qui continue de bouger ; la date en calendrier ;
  4. retour sur la carte pour le bilan, puis la question finale.
Une alerte météo ou une catastrophe naturelle reste sur la carte (départements ou pays colorés, pluie, neige, orage).
Le résultat a la même forme que celui de l'IA réalisatrice : `realisateur.valider` le contrôle de la même façon.
"""
import copy
import re

from . import ia

TYPES_EVENEMENT = ("accident_route", "incendie", "explosion", "crash_avion", "naufrage", "deraillement", "manifestation",
                   "meteo", "catastrophe_naturelle", "police_justice", "politique", "autre")
ACTEURS = ("voiture", "camion", "citerne", "bus", "moto", "camionnette", "police", "ambulance", "pompiers", "avion", "helico",
           "bateau", "train", "personne", "foule", "batiment", "maison", "immeuble")
ACTIONS = {"avancer": "avancer", "rouler": "avancer", "arriver": "avancer", "heurter": "heurter", "percuter": "heurter",
           "se_coucher": "se_coucher", "renverser": "se_coucher", "bruler": "bruler", "bruler_feu": "bruler", "exploser": "exploser",
           "tomber": "tomber", "s_ecraser": "tomber", "couler": "couler", "sombrer": "couler", "derailler": "se_coucher"}

CONSIGNE = """On te donne le texte d'une vidéo d'actualité (phrases numérotées) et les articles. EXTRAIS SEULEMENT les faits,
sans rien inventer. Réponds uniquement en JSON :
{"type": "accident_route" | "incendie" | "explosion" | "crash_avion" | "naufrage" | "deraillement" | "manifestation" | "meteo" |
          "catastrophe_naturelle" | "police_justice" | "politique" | "autre",
 "lieu": "ville, pays (le lieu où ça se passe)",
 "nuit": true si les faits se passent la nuit ou le soir,
 "departements": ["39"] (seulement pour la France : numéros des départements concernés, sinon []),
 "pays": ["EGY"] (codes à 3 lettres des pays concernés),
 "acteurs": [{"id": "camion", "type": "citerne", "role": "le camion-citerne"}],
 "deroule": [{"phrase": 3, "qui": "voiture", "action": "heurter", "cible": "camion"}],
 "chiffres": [{"phrase": 1, "valeur": "31", "unite": "morts", "texte": "selon le ministère"}],
 "date": {"phrase": 0, "jour": "22", "mois": "NOVEMBRE"},
 "heures": [{"phrase": 2, "heure": "21 h 40", "etape": "L'ATTAQUE"}],
 "titre": "titre court, 40 signes au plus, le mot le plus fort entre **astérisques**",
 "lieu_date": "LE CAIRE · MERCREDI SOIR",
 "source": "Source : qui l'a annoncé (parquet, préfecture, Météo-France…)"}
"acteurs" : les véhicules, bâtiments ou personnes qui AGISSENT dans l'événement (types : voiture, camion, citerne, bus, moto,
camionnette, police, ambulance, pompiers, avion, helico, bateau, train, personne, foule, batiment, maison, immeuble) ; "role" =
comment le texte l'appelle (5 mots au plus). "deroule" : ce qui se passe, DANS L'ORDRE, avec le numéro de la phrase qui le
raconte (actions : avancer, arriver, heurter, se_coucher, bruler, exploser, tomber, couler, derailler). "chiffres" : 3 au
plus, les plus frappants, copiés tels quels du texte. "heures" : chaque heure précise DITE dans une phrase (copiée telle
quelle), dans l'ordre, avec un nom d'étape court (2 mots, en majuscules : « LE DÉPART », « L'ALERTE », « LES SECOURS ») ;
plusieurs heures peuvent avoir la même étape. Mets [] ou {} quand tu ne sais pas."""


def extraire(script, articles, journal=print):
    phrases = "\n".join(f"{i}. {p['ecrit']}" for i, p in enumerate(script["phrases"]))
    faits = " ".join(f"{a.get('titre', '')} {a.get('texte') or ''}" for a in articles or [])[:6000]
    d, qui = ia.demander_json(CONSIGNE, f"PHRASES :\n{phrases}\n\nARTICLES :\n{faits}", temperature=0.2, max_tokens=2500, journal=journal)
    journal(f"  faits extraits par {qui} : {d.get('type')} · {len(d.get('acteurs') or [])} acteur(s) · "
            f"{len(d.get('deroule') or [])} étape(s) · {len(d.get('chiffres') or [])} chiffre(s)")
    return d


def _phrase(x, n):
    try:
        k = int(x)
    except (TypeError, ValueError):
        return None
    return k if 0 <= k < n else None


# décor 3D de chaque type d'événement
DECOR = {"accident_route": "autoroute", "incendie": "ville", "explosion": "ville", "crash_avion": "campagne", "naufrage": "mer",
         "deraillement": "voie_ferree", "manifestation": "place", "police_justice": "place"}


# vue « maquette » vue d'en haut (bonnequestion.tv, Bataclan : 1,1 million de vues) : lieux, foules, bâtiments
VUE_MAQUETTE = ("manifestation", "police_justice", "incendie", "explosion")
# moment le plus fort, montré dès la 1re phrase (« 8 000 mètres en une minute. ») avant de revenir au début
FORTS = ("heurter", "exploser", "bruler", "tomber", "couler", "se_coucher")


def _accroche(scene3d):
    """Copie de la reconstitution où le moment fort se passe dès la 1re phrase (viseur « ● RECONSTITUTION »)."""
    forts = [a for a in scene3d.get("actions") or [] if a["faire"] in FORTS]
    if not forts:
        return None
    acc = copy.deepcopy(scene3d)
    garde = {a["objet"] for a in forts} | {a.get("cible") for a in forts if a.get("cible")}
    acc["actions"] = [dict(a, phrase=0, duree=min(float(a.get("duree") or 1.2), 1.6)) for a in acc["actions"]
                      if a["faire"] in FORTS or (a["faire"] == "avancer" and a["objet"] in garde)]
    acc["reperes"], acc["etiquettes"], acc["accroche"] = [], [], True
    return acc


def _heures(f, n, dits):
    """Heures vraiment dites dans le texte, dans l'ordre (horloge et chapitres en haut de l'écran)."""
    out, vu = [], -1
    for h in f.get("heures") or []:
        if not isinstance(h, dict):
            continue
        ph, heure = _phrase(h.get("phrase"), n), str(h.get("heure") or "").strip()
        m = re.match(r"^(\d{1,2})\s*(?:h|:)\s*(\d{2})?$", heure)
        if ph is None or ph <= vu or not m or int(m.group(1)) > 23:
            continue
        if not re.search(rf"\b{int(m.group(1))}\s*(?:h|heures?|:)\s*{m.group(2) or ''}", dits[ph].lower()):
            continue                                                    # heure absente de SA phrase : jamais inventée
        etape = re.sub(r"[^\w' -]", "", str(h.get("etape") or "")).strip().upper()[:18]
        out.append(dict(phrase=ph, heure=f"{int(m.group(1))}:{m.group(2) or '00'}", chapitre=etape))
        vu = ph
    return out if len(out) >= 2 else []


def _scene_3d(f, phrases_3d, script):
    """Reconstitution : les acteurs placés selon le type d'événement, chaque action calée sur sa phrase."""
    typ = f["type"]
    acteurs = [a for a in f.get("acteurs") or [] if isinstance(a, dict) and a.get("type") in ACTEURS and a.get("id")][:6]
    texte = " ".join(p["ecrit"] for p in script["phrases"]).lower()
    if typ in ("manifestation", "police_justice"):
        if not any(a["type"] == "foule" for a in acteurs) and typ == "manifestation":
            acteurs.append(dict(id="foule", type="foule", role="les manifestants"))
        if re.search(r"\bpolic|gendarm|forces de l'ordre", texte) and not any(a["type"] == "police" for a in acteurs):
            acteurs.append(dict(id="police", type="police", role="la police"))
        acteurs.append(dict(id="siege", type="batiment_officiel", role=""))
    objets, places = [], {}
    for k, a in enumerate(acteurs):
        o = dict(id=a["id"], type=a["type"])
        if typ == "accident_route" or (typ in ("incendie", "explosion") and a["type"] in ("voiture", "camion", "citerne", "bus", "moto", "camionnette")):
            o.update(voie=2 + (k % 2), position=-45 - 14 * k)                  # sur la route, l'un derrière l'autre
        elif a["type"] in ("police", "ambulance", "pompiers"):
            o.update(voie=1, position=-80 - 12 * k)                            # les secours arrivent de loin
        elif typ == "crash_avion" and a["type"] in ("avion", "helico"):
            o.update(position=-120, voie=1, altitude=60)
        elif typ == "naufrage":
            o.update(position=-20 * k, voie=1)
        elif a["type"] == "foule":
            o.update(position=0, z=8, nombre=70)
        elif a["type"] == "batiment_officiel":
            o.update(position=0, z=-32)
        elif a["type"] == "police" and typ in ("manifestation", "police_justice"):
            o.update(position=-14 + 28 * (k % 2), z=16)
        else:
            o.update(position=-10 + 12 * k, voie=1)
        objets.append(o); places[a["id"]] = o
    actions, n = [], len(script["phrases"])
    for e in f.get("deroule") or []:
        if not isinstance(e, dict):
            continue
        faire, qui, ph = ACTIONS.get(str(e.get("action") or "").lower()), e.get("qui"), _phrase(e.get("phrase"), n)
        if not faire or qui not in places or ph is None or ph not in phrases_3d:
            continue
        act = dict(objet=qui, faire=faire, phrase=ph, duree=2.2 if faire in ("avancer", "heurter", "tomber", "couler") else 1.0)
        if faire == "avancer":
            act["vers_position"] = 0 if places[qui]["type"] not in ("police", "ambulance", "pompiers") else -22
        if faire == "heurter":
            cible = e.get("cible") if e.get("cible") in places else next((x for x in places if x != qui), None)
            if not cible:
                continue
            act["cible"] = cible
            if not any(x["objet"] == cible and x["faire"] == "avancer" for x in actions):   # la cible roule déjà
                actions.append(dict(objet=cible, faire="avancer", phrase=phrases_3d[0], duree=3.0, vers_position=0))
        if faire == "tomber":
            act.update(vers_position=0, altitude=0)
        actions.append(act)
    if typ in ("accident_route", "incendie", "explosion", "crash_avion") and not actions and objets:
        principal = objets[0]["id"]                                            # sans déroulé clair : l'objet principal avance
        actions.append(dict(objet=principal, faire="avancer", phrase=phrases_3d[0], duree=3.0, vers_position=0))
    reperes = []
    for a in acteurs:
        role = str(a.get("role") or "").strip()
        if role and a["type"] not in ("batiment_officiel",):
            premiere = next((x["phrase"] for x in actions if x["objet"] == a["id"]), phrases_3d[0])
            reperes.append(dict(objet=a["id"], texte=role[:28], phrase=premiere))
    moment = "nuit" if f.get("nuit") else "jour"
    vue = {"vue": "iso"} if typ in VUE_MAQUETTE else {}
    return dict(type="3d", **vue, decor=DECOR.get(typ, "ville"), moment=moment, objets=objets, actions=actions, reperes=reperes[:3],
                etiquettes=[f"D'après {m.strip()}" for m in re.findall(r"(?i)source\s*:\s*([^,.;]{3,30})", f.get("source") or "")][:1])


def composer(f, script):
    """Storyboard complet (même forme que l'IA réalisatrice) selon la recette du type d'événement."""
    n = len(script["phrases"])
    typ = f.get("type") if f.get("type") in TYPES_EVENEMENT else "autre"
    f["type"] = typ
    # encadrés : chiffres clés (3 au plus) et date ; jamais sur la 1re ni la dernière phrase
    encadres = {}
    for c in (f.get("chiffres") or [])[:3]:
        ph = _phrase((c or {}).get("phrase"), n)
        if ph not in (None, 0, n - 1) and ph not in encadres and str(c.get("valeur") or "").strip():
            encadres[ph] = dict(type="chiffre", valeur=str(c["valeur"]).strip(), unite=str(c.get("unite") or "")[:20],
                                texte=str(c.get("texte") or "")[:50])
            if re.search(r"km\s*/?\s*h|kilomètres?[- ]heure|nœuds", str(c.get("unite") or "").lower()):
                encadres[ph].update(type="jauge", unite="km/h" if "km" in str(c.get("unite")).lower() else "nœuds")
    d = f.get("date") or {}
    ph = _phrase(d.get("phrase"), n) if isinstance(d, dict) else None
    if ph not in (None, 0, n - 1) and ph not in encadres and str(d.get("jour") or "").isdigit():
        encadres[ph] = dict(type="calendrier", jour=str(d["jour"]), mois=str(d.get("mois") or "").upper()[:12], annee="")
    # décors : carte d'accroche → 3D de l'événement → carte du bilan (météo / catastrophe : la carte tout du long)
    deroule = sorted(p for p in (_phrase((e or {}).get("phrase"), n) for e in f.get("deroule") or []) if p is not None)
    avec_3d = typ in DECOR and (deroule or typ in ("manifestation", "police_justice")) and n >= 6
    debut_3d = min(max(1, deroule[0] if deroule else 2), 3) if avec_3d else n
    fin_3d = min(n - 2, max((deroule[-1] if deroule else debut_3d) + 2, debut_3d + 3)) if avec_3d else n
    forts = avec_3d and n >= 8 and any(str((e or {}).get("action") or "").lower() in ACTIONS and
                                       ACTIONS[str(e.get("action")).lower()] in FORTS for e in f.get("deroule") or [])
    if forts:                                                         # phrase 0 = moment fort ; la carte garde la phrase 1
        debut_3d = max(debut_3d, 2)
        fin_3d = max(fin_3d, min(n - 2, debut_3d + 3))
    phrases_3d = list(range(debut_3d, fin_3d + 1))
    carte = dict(type="carte", zone="france" if f.get("departements") else None, nuit=bool(f.get("nuit")),
                 departements=[dict(code=str(c).zfill(2), couleur="orange" if typ == "meteo" else "rouge") for c in (f.get("departements") or [])[:8]],
                 pays=[] if f.get("departements") else [dict(iso=str(p)[:3].upper(), couleur="rouge") for p in (f.get("pays") or [])[:3]],
                 lieux=[str(f.get("lieu") or "").split(",")[0].strip()] if f.get("lieu") else [],
                 effet={"meteo": "pluie", "catastrophe_naturelle": "orage"}.get(typ),
                 etiquettes=[str(f.get("lieu") or "").split(",")[0].upper()[:24]] if f.get("lieu") else [])
    if typ == "meteo" and re.search(r"neige|verglas|froid|gel", " ".join(p["ecrit"] for p in script["phrases"]).lower()):
        carte["effet"] = "neige"
    role = {}
    for i in range(n - 1):
        role[i] = "encadre" if i in encadres else ("3d" if i in phrases_3d else ("carte" if i < debut_3d else "bilan"))
    role[n - 1] = "question"
    scenes, i = [], 0
    while i < n:
        r = role[i]
        j = i
        while j + 1 < n and role[j + 1] == r and r not in ("encadre", "question"):
            j += 1
        ph = list(range(i, j + 1))
        if r == "encadre":
            scenes.append(dict(encadres[i], phrases=ph))
        elif r == "question":
            scenes.append(dict(type="question", phrases=ph))
        elif r == "3d":
            if not any(s.get("type") == "3d" and not s.get("accroche") for s in scenes):
                scenes.append(dict(_scene_3d(f, phrases_3d, script), phrases=ph))
            else:                                                             # 3D coupée par un encadré : elle continue dessous
                scenes.append(dict(type="suite", phrases=ph))             # (rien par-dessus : on revoit la 3D)
        elif r == "bilan" and avec_3d:
            scenes.append(dict(carte, phrases=ph, etiquettes=["LE BILAN"]))
        else:
            if scenes and scenes[-1].get("type") == "carte" and r == "carte":
                scenes[-1]["phrases"] += ph
            else:
                scenes.append(dict(carte, phrases=ph))
        i = j + 1
    if forts and scenes and scenes[0].get("type") == "carte" and 0 in scenes[0]["phrases"]:
        principale = next((x for x in scenes if x.get("type") == "3d"), None)
        acc = _accroche({k: v for k, v in principale.items() if k != "phrases"}) if principale else None
        if acc:                                                       # la 1re phrase passe sur le moment fort
            scenes[0]["phrases"] = scenes[0]["phrases"][1:]
            scenes.insert(0, dict(acc, phrases=[0]))
            if not scenes[1]["phrases"]:
                scenes.pop(1)
    propres = scenes
    return dict(titre=f.get("titre") or script.get("titre") or "", lieu_date=f.get("lieu_date") or "", source=f.get("source") or "",
                cles={}, scenes=propres)


def realiser(script, articles, journal=print):
    """Storyboard par modèle fixe, contrôlé par `realisateur.valider` ; IA indisponible ou faits inutilisables → None."""
    from . import realisateur
    try:
        f = extraire(script, articles, journal)
    except Exception as e:
        journal(f"  extraction des faits impossible ({str(e)[:80]})")
        return None
    if not isinstance(f, dict) or not (f.get("lieu") or f.get("pays") or f.get("departements")):
        journal("  faits sans lieu : modèle fixe impossible")
        return None
    brut = composer(f, script)
    anim = realisateur.valider(brut, script, articles, journal)
    anim["gabarit"] = f["type"]
    anim["chrono"] = _heures(f, len(script["phrases"]), [p["ecrit"] for p in script["phrases"]])
    if any(sc.get("accroche") for sc in anim["scenes"]):
        anim["viseur"] = ", ".join(x.strip() for x in str(f.get("lieu") or "").split(",")[:2]).upper()[:40]
    journal(f"  modèle « {f['type']} » : " + " · ".join(f"{s['type']} ({len(s['phrases'])} ph.)" for s in anim["scenes"]))
    return anim
