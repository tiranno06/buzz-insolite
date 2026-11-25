"""Avancement en temps réel de la vidéo en cours de création, affiché par le site (barre de progression).

Le robot écrit un petit fichier avancement.json sur une branche à part du dépôt (« avancement »), remplacée à chaque mise
à jour (aucun historique, la branche main n'est jamais touchée). Pendant le montage, le pourcentage est relayé :
une mise à jour toutes les 10 s environ. Le site relit ce fichier toutes les 8 s.
"""
import json
import os
import subprocess
import threading
import time

from .commun import RACINE, SORTIE, iso, maintenant

BRANCHE = "avancement"
INTERVALLE = 10                 # secondes entre deux envois (sauf changement d'étape, envoyé tout de suite)

_etat = {}
_dernier_envoi = 0.0


def demarrer(vid, format_, titre=""):
    global _dernier_envoi
    _etat.clear()
    _etat.update(id=vid, format=format_, titre=titre, etat="en_cours", etape="Démarrage du robot", detail="", pourcent=1,
                 machine=os.environ.get("MACHINE", "1"),
                 debut=iso(), debut_s=time.time(), run=os.environ.get("GITHUB_RUN_ID", ""))
    _dernier_envoi = 0.0
    _envoyer(force=True)


def etape(texte, pourcent, detail="", titre=None):
    """Nouvelle étape (envoyée tout de suite)."""
    if not _etat:
        return
    if titre:
        _etat["titre"] = titre
    _etat.update(etape=texte, detail=detail, pourcent=max(_etat.get("pourcent", 0), min(99, round(pourcent, 1))))
    _envoyer(force=True)


def progres(pourcent, detail=None):
    """Progrès à l'intérieur d'une étape (envoyé au plus toutes les 10 s)."""
    if not _etat:
        return
    _etat["pourcent"] = max(_etat.get("pourcent", 0), min(99, round(pourcent, 1)))
    if detail is not None:
        _etat["detail"] = detail
    _envoyer()


def finir(ok, texte):
    if not _etat:
        return
    _etat.update(etat="fini" if ok else "erreur", etape=texte, detail="", pourcent=100 if ok else _etat.get("pourcent", 0))
    _envoyer(force=True)


def duree_typique():
    """Durée moyenne réelle d'une vidéo (10 dernières, page Santé), sinon 40 min."""
    try:
        from .commun import lire
        return int(((lire("sante.json") or {}).get("durees") or {}).get("total") or 40 * 60)
    except Exception:
        return 40 * 60


def contenu():
    """Ce que lit le site, avec l'heure de fin estimée (d'après le temps déjà passé et le pourcentage)."""
    ecoule = time.time() - _etat["debut_s"]
    p = _etat["pourcent"]
    typique = duree_typique()
    if _etat["etat"] == "en_attente":
        reste = typique
    elif _etat["etat"] != "en_cours":
        reste = 0
    elif p < 12:                                        # début : on se fie à la durée habituelle
        reste = max(60, typique - ecoule)
    else:                                               # ensuite : au rythme réel de cette création
        reste = max(20, ecoule * (100 - p) / p)
    d = {k: v for k, v in _etat.items() if k != "debut_s"}
    d.update(maj=iso(), ecoule_s=round(ecoule), reste_s=round(reste))
    return d


_VERROU = threading.Lock()                      # voix et images avancent en même temps (deux fils d'exécution)


def publier_medias(ids):
    """Vidéos et images déjà prises par CETTE vidéo : les autres machines ne les reprennent pas (jamais deux vidéos en
    construction avec les mêmes passages)."""
    if _etat:
        _etat["medias"] = sorted({str(i).rsplit("-", 1)[0] for i in ids if i})[-300:]
        _envoyer(force=True)


def medias_des_autres():
    """Médias pris par les autres vidéos en construction en ce moment."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return set()
    moi = _nom()
    return {m for f, (_, d) in _lire_branche().items() if f != moi and d.get("etat") == "en_cours" and _age_min(d) < 30
            for m in d.get("medias") or []}


def _envoyer(force=False):
    with _VERROU:
        _envoyer_seul(force)


def _envoyer_seul(force=False):
    global _dernier_envoi
    if not force and time.time() - _dernier_envoi < INTERVALLE:
        return
    _dernier_envoi = time.time()
    texte = json.dumps(contenu(), ensure_ascii=False)
    try:
        os.makedirs(SORTIE, exist_ok=True)
        with open(os.path.join(SORTIE, "avancement.json"), "w", encoding="utf-8") as f:
            f.write(texte)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            _pousser_sur(texte)
    except Exception as e:                              # l'avancement ne doit jamais gêner la création de la vidéo
        print(f"  (avancement non envoyé : {e})", flush=True)


def _git(*args, entree=None):
    return subprocess.run(["git", *args], cwd=RACINE, input=entree, capture_output=True, text=True, check=True,
                          timeout=30).stdout.strip()


def _nom():
    """Un fichier par machine (séries en parallèle) : av-<run>-<machine>.json."""
    return f"av-{os.environ.get('GITHUB_RUN_ID', 'local')}-{os.environ.get('MACHINE', '1')}.json"


def _lire_branche():
    """{fichier: (sha, contenu)} des fichiers d'avancement de toutes les machines ({} si la branche n'existe pas)."""
    out = {}
    if subprocess.run(["git", "fetch", "-q", "origin", BRANCHE], cwd=RACINE, capture_output=True, timeout=30).returncode != 0:
        return out
    for ligne in _git("ls-tree", "FETCH_HEAD").splitlines():
        mode_type_sha, fichier = ligne.split("\t", 1)
        if fichier.endswith(".json"):
            sha = mode_type_sha.split()[2]
            try:
                out[fichier] = (sha, json.loads(_git("cat-file", "-p", sha)))
            except Exception:
                pass
    return out


def _age_min(d):
    import datetime
    try:
        return (maintenant() - datetime.datetime.fromisoformat(d["maj"])).total_seconds() / 60
    except Exception:
        return 1e9


def attendre_son_tour(limite, journal=print, attente_max_min=200):
    """File d'attente commune à TOUTES les séries : au plus `limite` vidéos dans la partie lourde (voix, images, montage) en
    même temps. Appelée APRÈS l'écriture du texte (préparé pendant l'attente). Une machine qui attend porte file="attente"
    (avec l'heure de sa demande) ; celles qui fabriquent portent file="active". Une machine muette depuis 30 min (active) ou
    3 min (en attente) ne compte plus. Au-delà de `attente_max_min`, elle part quand même (jamais bloquée pour toujours)."""
    if os.environ.get("GITHUB_ACTIONS") != "true" or not _etat:
        return
    moi = _nom(); debut = time.time()
    _etat.update(file="attente", demande=_etat.get("debut") or iso())
    etape_avant = (_etat.get("etape"), _etat.get("detail"))
    deja_dit = None
    while True:
        autres = {f: d for f, (_, d) in _lire_branche().items() if f != moi}
        actifs = [d for d in autres.values() if d.get("etat") == "en_cours" and _age_min(d) < 30
                  and d.get("file", "active") == "active"]                     # (anciennes versions : sans « file »)
        attente = [d for d in autres.values() if d.get("file") == "attente" and _age_min(d) < 3] + [dict(_etat, nom=moi)]
        attente.sort(key=lambda d: (d.get("demande", ""), d.get("run", ""), str(d.get("machine", ""))))
        rang = next(k for k, d in enumerate(attente) if d.get("nom") == moi)
        places = limite - len(actifs)
        if rang < places or time.time() - debut > attente_max_min * 60:
            _etat.update(file="active", etape=etape_avant[0], detail=etape_avant[1] or "")
            _envoyer(force=True)
            return
        avant = rang - places + 1
        _etat["etape"] = "En file d'attente (texte prêt)"
        _etat["detail"] = f"{avant} vidéo(s) avant celle-ci ({len(actifs)} en fabrication, {limite} au plus en même temps)"
        if _etat["detail"] != deja_dit:
            journal(f"⏳ File d'attente : {_etat['detail']}")
            deja_dit = _etat["detail"]
        _envoyer(force=True)
        time.sleep(30)


def _pousser(texte):
    """Remplace la branche « avancement » par un seul commit : notre fichier + ceux des autres machines encore actives
    (mis à jour il y a moins de 2 h). Deux machines qui envoient en même temps : l'une perd sa mise à jour pour 10 s."""
    import datetime
    nom = _nom()
    garde = []
    if subprocess.run(["git", "fetch", "-q", "origin", BRANCHE], cwd=RACINE, capture_output=True, timeout=30).returncode == 0:
        for ligne in _git("ls-tree", "FETCH_HEAD").splitlines():
            mode_type_sha, fichier = ligne.split("\t", 1)
            sha = mode_type_sha.split()[2]
            if fichier == nom or not fichier.endswith(".json"):
                continue
            try:
                d = json.loads(_git("cat-file", "-p", sha))
                maj = datetime.datetime.fromisoformat(d["maj"])
                # vidéo finie ou en erreur : affichée 30 min puis effacée ; en cours / en attente : 2 h sans nouvelles = plantée
                duree = (datetime.timedelta(minutes=1) if d.get("etat") == "annulee" else
                         datetime.timedelta(minutes=30) if d.get("etat") in ("fini", "erreur") else datetime.timedelta(hours=2))
                if maintenant() - maj < duree:
                    garde.append(f"100644 blob {sha}\t{fichier}")
            except Exception:
                pass
    blob = _git("hash-object", "-w", "--stdin", entree=texte)
    arbre = _git("mktree", entree="\n".join(garde + [f"100644 blob {blob}\t{nom}"]) + "\n")
    env = dict(os.environ, GIT_AUTHOR_NAME="robot-buzz", GIT_AUTHOR_EMAIL="robot-buzz@users.noreply.github.com",
               GIT_COMMITTER_NAME="robot-buzz", GIT_COMMITTER_EMAIL="robot-buzz@users.noreply.github.com")
    commit = subprocess.run(["git", "commit-tree", arbre, "-m", f"avancement {maintenant():%H:%M:%S}"], cwd=RACINE,
                            capture_output=True, text=True, check=True, env=env, timeout=30).stdout.strip()
    _git("push", "-q", "--force", "origin", f"{commit}:refs/heads/{BRANCHE}")


def _pousser_sur(texte):
    """Deux machines qui écrivent au même instant : un 2e essai après 2 s (au lieu de perdre la mise à jour)."""
    try:
        _pousser(texte)
    except subprocess.CalledProcessError:
        time.sleep(2)
        _pousser(texte)


def annuler():
    """Fabrication annulée sur GitHub (étape « if: cancelled() » de creer.yml) : la barre de cette machine disparaît."""
    moi = _nom()
    for f, (_, d) in _lire_branche().items():
        if f == moi:
            _etat.clear(); _etat.update(d)
            _etat["debut_s"] = time.time()
            _etat.update(etat="annulee", etape="Fabrication annulée", detail="")
            _envoyer(force=True)
            return


if __name__ == "__main__":
    import sys
    if "--annuler" in sys.argv:
        annuler()

