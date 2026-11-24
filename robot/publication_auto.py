"""Garde (workflow garde.yml, toutes les 15 minutes) : publication automatique et création automatique aux heures choisies.

- Publication : à chaque heure de Réglages → Publication (2 par jour par défaut), la vidéo « À publier » cochée la première part
  sur TikTok par Buffer. Une vidéo en échec est notée et sautée (la suivante part au créneau suivant).
- Création : si elle est activée, une vidéo est lancée (workflow creer.yml) à chaque heure de Réglages → Création.
Un créneau compte s'il est passé depuis moins de 3 heures (GitHub saute parfois des réveils) et pas encore fait aujourd'hui.
"""
import datetime
import os
import subprocess

from . import depot, publier
from .commun import ecrire, iso, lire, maintenant, noter, reglages

FENETRE = datetime.timedelta(hours=3)


def creneaux_dus(heures, faits, now):
    """Heures « HH:MM » passées aujourd'hui depuis moins de 3 h et pas encore faites."""
    out = []
    for h in heures:
        try:
            hh, mm = (int(x) for x in str(h).split(":"))
        except ValueError:
            continue
        t = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if t <= now < t + FENETRE and h not in faits:
            out.append(h)
    return out


def prochaine(file):
    """Vidéo à publier : cochée « À publier » la première (ordre de coche)."""
    attente = [v for v in file.get("videos", []) if v.get("statut") == "a_publier" and not v.get("essai")]
    return min(attente, key=lambda v: v.get("coche_le") or v.get("cree_le") or "") if attente else None


def main():
    R = reglages(); now = maintenant(); jour = f"{now:%Y-%m-%d}"
    E = lire("garde.json") or {}
    pub_dus = creneaux_dus(R["publication"]["heures"], (E.get("publication") or {}).get(jour, []), now) \
        if R["publication"].get("auto") else []
    cre_dus = creneaux_dus(R["creation"]["heures"], (E.get("creation") or {}).get(jour, []), now) \
        if R["creation"].get("auto") else []
    if not pub_dus and not cre_dus:
        print("Rien à faire maintenant.")
        return
    lancer = []
    # Buffer appelé UNE seule fois, avant l'enregistrement (qui peut se répéter si quelqu'un écrit en même temps)
    file = publier.mettre_a_jour(lire("file.json") or {"videos": []})
    resultats = {}                                       # créneau → (id de la vidéo, réponse Buffer ou erreur)
    deja = set()
    for h in pub_dus:
        v = prochaine({"videos": [x for x in file["videos"] if x["id"] not in deja]})
        if not v:
            resultats[h] = (None, None); continue
        deja.add(v["id"])
        try:
            resultats[h] = (v["id"], publier.envoyer(v, R))
        except Exception as e:
            resultats[h] = (v["id"], e)

    def appliquer():
        E = lire("garde.json") or {}
        file = publier.mettre_a_jour(lire("file.json") or {"videos": []})
        par_id = {x["id"]: x for x in file["videos"]}
        for h in pub_dus:
            E.setdefault("publication", {}).setdefault(jour, []).append(h)
            vid, rep = resultats[h]
            v = par_id.get(vid)
            if not vid:
                noter(f"📤 Créneau de {h} : aucune vidéo « À publier » (coche des vidéos sur le site).", "attention")
            elif v is None:
                continue
            elif isinstance(rep, Exception):
                v.update(statut="echec", echec_publication=f"{iso()} : {str(rep)[:200]}")
                noter(f"❌ « {v['titre']} » : publication refusée ({str(rep)[:160]})", "erreur")
            else:
                v.update(statut="publiee", publiee_le=iso(), buffer=rep)
                noter(f"📤 « {v['titre']} » publiée sur TikTok (créneau de {h})."
                      + ("" if rep.get("etiquette_ia") else " Étiquette IA refusée par Buffer : coche-la dans l'appli TikTok."))
        for h in cre_dus:
            E.setdefault("creation", {}).setdefault(jour, []).append(h)
            if h not in lancer:
                lancer.append(h)
        for cle in ("publication", "creation"):            # on ne garde que la dernière semaine
            for j in sorted(E.get(cle, {}))[:-7]:
                del E[cle][j]
        ecrire("garde.json", E)
        ecrire("file.json", file)
    depot.enregistrer(appliquer, f"Garde de {now:%H:%M}")
    for h in lancer:
        if depot.en_ligne():
            subprocess.run(["gh", "workflow", "run", "creer.yml", "-f", "nombre=1", "-f", f"origine=auto {h}"],
                           check=False, env=dict(os.environ))
        noter(f"🤖 Création automatique lancée (créneau de {h}).")


if __name__ == "__main__":
    main()
