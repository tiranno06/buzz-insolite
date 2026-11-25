"""Plus de musiques, classées par ambiance et par rythme (amélioration 9 du 25/11).

Source : FreePD.com (Kevin MacLeod), musiques versées au DOMAINE PUBLIC (CC0) : usage commercial et montage permis, sans
obligation de crédit (le crédit est quand même écrit dans sons/LICENCES.md). Lancé à la main par musiques.yml (sur GitHub :
le site n'est pas joignable depuis toutes les machines) : chaque page de catégorie est lue, les morceaux sont téléchargés,
coupés à 2 min, mis au même niveau sonore, et leur tempo est mesuré (sons.battements). Résultat : sons/musique/<ambiance>_fp_*.mp3
et sons/musique/catalogue.json (titre, ambiance, tempo, adresse d'origine), lus par sons.musique.
"""
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

from .commun import RACINE

DOSSIER = os.path.join(RACINE, "sons", "musique")
# catégorie de FreePD → ambiance de nos vidéos
CATEGORIES = {"upbeat": "joie", "comedy": "joie", "epic": "epique", "scoring": "tension", "horror": "tension",
              "electronic": "neutre", "misc": "neutre", "romantic": "emotion", "world": "neutre"}
PAR_CATEGORIE = 4


def _lire(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "buzz-insolite-robot (musique CC0)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def morceaux(categorie):
    page = _lire(f"https://freepd.com/{categorie}.php").decode("utf-8", "ignore")
    liens = []
    for lien in re.findall(r'href=["\']([^"\']+\.mp3)["\']', page, re.I):
        url = urllib.parse.urljoin(f"https://freepd.com/{categorie}.php", lien)
        if url not in liens:
            liens.append(url)
    return liens


def tempo(fichier):
    from . import sons
    t = sons.battements(fichier)
    if len(t) < 4:
        return 0
    ecart = (t[-1] - t[0]) / (len(t) - 1) * 2                # demi-temps → temps
    return round(60 / ecart) if ecart else 0


def main():
    os.makedirs(DOSSIER, exist_ok=True)
    chemin_cat = os.path.join(DOSSIER, "catalogue.json")
    catalogue = json.load(open(chemin_cat, encoding="utf-8")) if os.path.exists(chemin_cat) else []
    deja = {m["origine"] for m in catalogue}
    for cat, humeur in CATEGORIES.items():
        try:
            liens = morceaux(cat)
        except Exception as e:
            print(f"{cat} : page illisible ({e})"); continue
        pris = 0
        for url in liens:
            if pris >= PAR_CATEGORIE:
                break
            if url in deja:
                pris += 1; continue
            titre = urllib.parse.unquote(url.rsplit("/", 1)[1])[:-4]
            nom = f"{humeur}_fp_{re.sub(r'[^a-z0-9]+', '_', titre.lower()).strip('_')[:40]}.mp3"
            brut = os.path.join(DOSSIER, "brut.mp3")
            try:
                with open(brut, "wb") as f:
                    f.write(_lire(url, 120))
                sortie = os.path.join(DOSSIER, nom)
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", brut, "-t", "120", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                                "-ac", "2", "-ar", "44100", "-b:a", "128k", sortie], check=True, timeout=300)
                catalogue.append(dict(fichier=nom, titre=titre, humeur=humeur, categorie=cat, tempo=tempo(sortie), origine=url,
                                      licence="domaine public (CC0), FreePD.com — Kevin MacLeod"))
                deja.add(url); pris += 1
                print(f"✓ {nom} ({humeur}, {catalogue[-1]['tempo']} bpm)")
            except Exception as e:
                print(f"✗ {titre} : {e}")
            finally:
                if os.path.exists(brut):
                    os.remove(brut)
    for f in sorted(os.listdir(DOSSIER)):                     # les boucles d'origine (ACE-Step) aussi, avec leur tempo
        if f.endswith(".mp3") and "_fp_" not in f and not any(m["fichier"] == f for m in catalogue):
            catalogue.append(dict(fichier=f, titre=f[:-4], humeur=f.split("_")[0], categorie="ace-step",
                                  tempo=tempo(os.path.join(DOSSIER, f)), origine="jt-auto (ACE-Step, Apache 2.0)",
                                  licence="Apache 2.0"))
    with open(chemin_cat, "w", encoding="utf-8") as f:
        json.dump(catalogue, f, ensure_ascii=False, indent=1)
    print(f"{len(catalogue)} musiques au catalogue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
