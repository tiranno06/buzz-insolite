"""Plus de musiques, classées par ambiance et par rythme (amélioration 9 du 25/11).

Source : Openverse (moteur de recherche de médias libres de la fondation WordPress, sans clé), musiques sous licence CC0
(domaine public, surtout de Freesound) : usage commercial et montage permis sans obligation de crédit (auteur et page
d'origine gardés quand même dans catalogue.json). FreePD, prévu d'abord, a fermé en 2025. Lancé à la main par musiques.yml :
recherches par ambiance, morceaux de 40 s à 5 min sans voix ni bruitage, coupés à 2 min, mis au même niveau sonore, tempo
mesuré (sons.battements). Résultat : sons/musique/<ambiance>_ov_*.mp3 + catalogue.json, lus par sons.musique.
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
# recherches Openverse (moteur de médias libres de la fondation WordPress) → ambiance de nos vidéos
RECHERCHES = {"joie": ["upbeat music loop", "happy background music"], "tension": ["suspense music", "tension music loop"],
              "epique": ["epic orchestral music", "cinematic music"], "emotion": ["sad piano music", "emotional piano"],
              "neutre": ["background music loop", "lofi music"]}
PAR_AMBIANCE = 5
MOTS_INTERDITS = ("whoosh", "horn", "hit", "sfx", "effect", "impact", "riser", "stinger", "voice", "vocal", "speech", "jingle")


def _lire(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "buzz-insolite-robot (musique CC0)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def morceaux(recherche):
    """Musiques CC0 trouvées par Openverse (surtout Freesound) : 40 s à 5 min, sans voix ni bruitage."""
    q = urllib.parse.urlencode({"q": recherche, "license": "cc0", "page_size": 20})
    d = json.loads(_lire(f"https://api.openverse.org/v1/audio/?{q}"))
    out = []
    for r in d.get("results") or []:
        titre = str(r.get("title") or "")
        duree = (r.get("duration") or 0) / 1000
        if r.get("license") != "cc0" or not 40 <= duree <= 300 or any(x in titre.lower() for x in MOTS_INTERDITS):
            continue
        out.append(dict(url=r["url"], titre=titre, page=r.get("foreign_landing_url") or r["url"],
                        auteur=r.get("creator") or "", source=r.get("source") or ""))
    return out


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
    for humeur, recherches in RECHERCHES.items():
        pris = sum(1 for m in catalogue if m["humeur"] == humeur and m.get("categorie") == "openverse")
        for recherche in recherches:
            try:
                liste = morceaux(recherche)
            except Exception as e:
                print(f"{recherche} : recherche impossible ({e})"); continue
            for x in liste:
                if pris >= PAR_AMBIANCE:
                    break
                if x["url"] in deja:
                    continue
                nom = f"{humeur}_ov_{re.sub(r'[^a-z0-9]+', '_', x['titre'].lower()).strip('_')[:40]}.mp3"
                brut = os.path.join(DOSSIER, "brut.mp3")
                try:
                    with open(brut, "wb") as f:
                        f.write(_lire(x["url"], 120))
                    sortie = os.path.join(DOSSIER, nom)
                    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", brut, "-t", "120", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                                    "-ac", "2", "-ar", "44100", "-b:a", "128k", sortie], check=True, timeout=300)
                    catalogue.append(dict(fichier=nom, titre=x["titre"], humeur=humeur, categorie="openverse", recherche=recherche,
                                          tempo=tempo(sortie), origine=x["url"], page=x["page"], auteur=x["auteur"],
                                          licence=f"CC0 (domaine public), {x['source']} via Openverse"))
                    deja.add(x["url"]); pris += 1
                    print(f"✓ {nom} ({humeur}, {catalogue[-1]['tempo']} bpm)")
                except Exception as e:
                    print(f"✗ {x['titre']} : {e}")
                finally:
                    if os.path.exists(brut):
                        os.remove(brut)
    for f in sorted(os.listdir(DOSSIER)):                     # les boucles d'origine (ACE-Step) aussi, avec leur tempo
        if f.endswith(".mp3") and "_ov_" not in f and not any(m["fichier"] == f for m in catalogue):
            catalogue.append(dict(fichier=f, titre=f[:-4], humeur=f.split("_")[0], categorie="ace-step",
                                  tempo=tempo(os.path.join(DOSSIER, f)), origine="jt-auto (ACE-Step, Apache 2.0)",
                                  licence="Apache 2.0"))
    with open(chemin_cat, "w", encoding="utf-8") as f:
        json.dump(catalogue, f, ensure_ascii=False, indent=1)
    print(f"{len(catalogue)} musiques au catalogue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
