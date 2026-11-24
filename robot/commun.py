"""Outils partagés : chemins, lecture/écriture des fichiers de données, heure de Paris, journal."""
import datetime
import json
import os
from zoneinfo import ZoneInfo

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.environ.get("ROBOT_DOCS") or os.path.join(RACINE, "docs")   # ROBOT_DOCS : dossier de test
DONNEES = os.path.join(DOCS, "donnees")                      # lues aussi par le site (GitHub Pages)
MINIATURES = os.path.join(DOCS, "miniatures")
SORTIE = os.environ.get("ROBOT_SORTIE") or os.path.join(RACINE, "sortie")   # fichiers de travail (jamais enregistrés)
POLICES = os.path.join(RACINE, "polices")
CACHE = os.environ.get("ROBOT_CACHE") or os.path.expanduser("~/.cache/buzz-insolite")   # voix et modèles téléchargés
PARIS = ZoneInfo("Europe/Paris")
NAVIGATEUR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/131.0 Safari/537.36")
ROBOT_UA = "buzz-insolite-robot/1.0 (+https://github.com/tiranno06/buzz-insolite)"


def maintenant():
    """Heure de Paris. ROBOT_MAINTENANT (format ISO) permet aux tests de fixer l'heure."""
    fixe = os.environ.get("ROBOT_MAINTENANT")
    if fixe:
        d = datetime.datetime.fromisoformat(fixe)
        return d if d.tzinfo else d.replace(tzinfo=PARIS)
    return datetime.datetime.now(PARIS)


def iso(d=None):
    return (d or maintenant()).isoformat(timespec="seconds")


def lire(nom, defaut=None):
    try:
        with open(os.path.join(DONNEES, nom), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def ecrire(nom, contenu):
    os.makedirs(DONNEES, exist_ok=True)
    chemin = os.path.join(DONNEES, nom)
    with open(chemin + ".tmp", "w", encoding="utf-8") as f:
        json.dump(contenu, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(chemin + ".tmp", chemin)


REGLAGES_DEFAUT = {
    "buzz": {
        "comptes": ["hugodecrypte", "brut", "franceinfo", "leparisien", "20minutesfrance", "euronews.fr", "bfmtv",
                    "lemondefr", "konbini", "tf1info", "loopsider", "ouestfrance", "lefigarofr", "le.huffpost"],
        "vues_min": 500000, "jaime_min": 10000, "commentaires_min": 1000,
        "heures": 72,                                 # âge maximum d'une vidéo virale prise en compte
    },
    "video": {"voix": "fr_FR-tom-medium", "vitesse": 0.80, "duree_min": 62, "musique": True},
    "publication": {"mode": "cocher",                 # cocher = tu coches « À publier » ; auto = tout part sans toi
                    "auto": True, "heures": ["12:30", "19:00"], "compte": ""},
    "creation": {"auto": False, "par_jour": 2, "heures": ["07:15", "16:15"]},
    "hashtags": {"fixes": ["#insolite", "#actu", "#buzz"], "nombre": 6},
}


def reglages():
    """Réglages du site, complétés par les valeurs par défaut (un réglage ajouté plus tard ne manque jamais)."""
    R = lire("reglages.json") or {}
    for k, v in REGLAGES_DEFAUT.items():
        R.setdefault(k, {})
        for k2, v2 in v.items():
            R[k].setdefault(k2, v2)
    return R


def noter(texte, niveau="info"):
    """Ajoute une ligne au journal affiché sur le site (200 dernières gardées)."""
    j = lire("journal.json", {"evenements": []})
    j["evenements"].insert(0, {"date": iso(), "niveau": niveau, "texte": texte})
    del j["evenements"][200:]
    ecrire("journal.json", j)
    print(f"[{niveau}] {texte}", flush=True)


def simulation():
    return os.environ.get("SIMULATION", "0") == "1"
