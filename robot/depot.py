"""Enregistrement dans le dépôt GitHub et rangement des vidéos dans les « Releases ».

Plusieurs tâches peuvent écrire en même temps (robot du matin, boutons du site) : chaque écriture repart de la
dernière version en ligne, applique son changement, puis envoie. Si quelqu'un est passé entre-temps, on recommence.
"""
import os
import subprocess
import time

from .commun import RACINE


def en_ligne():
    return os.environ.get("GITHUB_ACTIONS") == "true"


def _git(*args, verifier=True):
    return subprocess.run(["git", *args], cwd=RACINE, capture_output=True, text=True, check=verifier)


def enregistrer(appliquer, message, essais=10):
    """Applique `appliquer()` sur la dernière version du dépôt puis l'envoie. Hors GitHub : applique seulement."""
    if not en_ligne():
        return appliquer()
    branche = os.environ.get("GITHUB_REF_NAME", "main")
    _git("config", "user.name", "robot-buzz")
    _git("config", "user.email", "robot-buzz@users.noreply.github.com")
    for n in range(essais):
        _git("fetch", "-q", "origin", branche)
        _git("reset", "-q", "--hard", f"origin/{branche}")
        resultat = appliquer()
        from .commun import A_ENVOYER, rejouer_journal
        rejouer_journal()                                  # lignes du journal notées avant (erreurs, abandons…)
        _git("add", "-A", "docs")
        if _git("diff", "--cached", "--quiet", verifier=False).returncode == 0:
            A_ENVOYER.clear()
            return resultat
        _git("commit", "-q", "-m", message)
        if _git("push", "-q", "origin", f"HEAD:{branche}", verifier=False).returncode == 0:
            A_ENVOYER.clear()
            return resultat
        time.sleep(min(60, 3 + 5 * n))                     # plusieurs machines écrivent : on laisse passer les autres
    raise RuntimeError("impossible d'enregistrer dans le dépôt après plusieurs essais")


def depot():
    return os.environ.get("GITHUB_REPOSITORY", "")


def publier_release(tag, titre, fichiers):
    """Range la vidéo dans une Release du dépôt. Renvoie l'adresse de téléchargement du premier fichier."""
    if not en_ligne():
        return "file://" + fichiers[0]
    for essai in range(3):                                # 30 min de travail : jamais perdues pour un raté passager
        r = subprocess.run(["gh", "release", "create", tag, *fichiers, "--title", titre[:120],
                            "--notes", "Vidéo fabriquée par le robot (contenu généré par IA)."], cwd=RACINE)
        if r.returncode == 0:
            break
        if subprocess.run(["gh", "release", "view", tag], cwd=RACINE, capture_output=True).returncode == 0:
            break                                         # créée malgré le message d'erreur
        if essai == 2:
            raise RuntimeError(f"impossible de ranger la vidéo dans la Release {tag}")
        time.sleep(15 * (essai + 1))
    return f"https://github.com/{depot()}/releases/download/{tag}/{os.path.basename(fichiers[0])}"


def supprimer_release(tag):
    if en_ligne() and tag:
        subprocess.run(["gh", "release", "delete", tag, "--yes", "--cleanup-tag"], cwd=RACINE)
