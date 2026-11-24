"""Garde (workflow garde.yml, toutes les 15 minutes) : publication automatique et création automatique aux heures choisies.

- Publication : à chaque heure de Réglages → Publication (2 par jour par défaut), la vidéo « À publier » cochée la première part
  sur TikTok par Buffer. Une vidéo en échec est notée et sautée (la suivante part au créneau suivant).
- Création : si elle est activée, une vidéo est lancée (workflow creer.yml) à chaque heure de Réglages → Création.
Un créneau compte s'il est passé depuis moins de 3 heures (GitHub saute parfois des réveils) et pas encore fait aujourd'hui.
"""
import datetime
import os
import subprocess

from . import controle, depot, publier
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
    heures_pub = R["publication"]["heures"]
    S = lire("stats.json") or {}
    if R["publication"].get("heures_auto") and len(S.get("meilleures_heures") or []) == 2:
        heures_pub = S["meilleures_heures"]                  # heures où nos vidéos font le plus de vues
    pub_dus = creneaux_dus(heures_pub, (E.get("publication") or {}).get(jour, []), now) \
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
    refusees = {}                                        # vidéos bloquées par le contrôle avant publication
    for h in pub_dus:
        resultats[h] = (None, None)
        while True:                                      # une vidéo refusée par le contrôle : la suivante tente sa chance
            v = prochaine({"videos": [x for x in file["videos"] if x["id"] not in deja]})
            if not v:
                break
            deja.add(v["id"])
            try:
                resultats[h] = (v["id"], controle.verifier_et_envoyer(v, R))
                break
            except controle.Refusee as e:
                refusees[v["id"]] = str(e)
            except Exception as e:
                resultats[h] = (v["id"], e)
                break

    def appliquer():
        E = lire("garde.json") or {}
        file = publier.mettre_a_jour(lire("file.json") or {"videos": []})
        par_id = {x["id"]: x for x in file["videos"]}
        for vid, raison in refusees.items():
            if vid in par_id:
                par_id[vid].update(statut="a_verifier", echec_publication=f"{iso()} : {raison}")
                noter(f"🛡️ « {par_id[vid]['titre']} » non publiée : {raison[:180]}", "attention")
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
        format_ = format_auto(R, now, h)
        if depot.en_ligne():
            subprocess.run(["gh", "workflow", "run", "creer.yml", "-f", "nombre=1", "-f", f"format={format_}",
                            "-f", f"origine=auto {h}"], check=False, env=dict(os.environ))
        noter(f"🤖 Création automatique lancée (créneau de {h}, format {format_}).")


def format_auto(R, now, h):
    """Dimanche, dernier créneau : « 3 actus de la semaine » ; sinon « Vrai ou faux ? » une vidéo sur N ; sinon buzz."""
    F = R["creation"].get("formats") or {}
    if F.get("semaine") and now.weekday() == 6 and h == max(R["creation"]["heures"]):
        return "semaine"
    n = int(F.get("vrai_faux") or 0)
    deja = sum(len(x) for x in (lire("garde.json") or {}).get("creation", {}).values())
    return "vrai_faux" if n and deja % n == n - 1 else "buzz"


if __name__ == "__main__":
    main()
