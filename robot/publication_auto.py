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
    relancer_attente(E)                                  # créations en attente des IA : lancées dès qu'elles sont prêtes
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
            # les crédits des IA sont vérifiés AVANT (demande de l'auteur du 25/11) : sinon la création attend
            from . import credits
            ok, resume, _ = credits.verifier(1)
            if not ok:
                credits.mettre_en_attente({"nombre": "1", "format": format_, "origine": f"auto {h}"}, resume.lstrip("⏸️ "))
                continue
            subprocess.run(["gh", "workflow", "run", "creer.yml", "-f", "nombre=1", "-f", f"format={format_}",
                            "-f", f"origine=auto {h}"], check=False, env=dict(os.environ))
        noter(f"🤖 Création automatique lancée (créneau de {h}, format {format_}).")


def relancer_attente(E):
    """Créations mises en attente faute d'IA disponibles (`credits.mettre_en_attente`) : la plus ancienne est lancée dès
    que la vérification des crédits passe (une seule par passage de la garde, pour ne pas resaturer les IA)."""
    attente = E.get("en_attente") or []
    if not attente or not depot.en_ligne():
        return
    # une vidéo à refaire qui n'existe plus (déjà refaite entre-temps, par exemple par la santé de la nuit) : oubliée
    ids = {v["id"] for v in (lire("file.json") or {}).get("videos") or []}
    perimees = [x for x in attente if (x.get("inputs") or {}).get("refaire") and x["inputs"]["refaire"] not in ids]
    if perimees:
        def oublier():
            G = lire("garde.json") or {}
            G["en_attente"] = [x for x in G.get("en_attente") or [] if x not in perimees]
            ecrire("garde.json", G)
        depot.enregistrer(oublier, "Créations en attente déjà faites : oubliées")
        attente = [x for x in attente if x not in perimees]
        E["en_attente"] = attente
        if not attente:
            return
    from . import credits
    ok, resume, _ = credits.verifier(1)
    if not ok:
        print(f"{len(attente)} création(s) en attente : {resume}")
        return
    demande = attente[0]

    def appliquer():
        G = lire("garde.json") or {}
        G["en_attente"] = [x for x in G.get("en_attente") or [] if x != demande]
        G["credits"] = {"le": iso(), "resume": resume}
        ecrire("garde.json", G)
        noter(f"▶️ Création en attente lancée : les IA gratuites sont de nouveau disponibles ({resume.lstrip('✅ ')}).")
    depot.enregistrer(appliquer, "Création en attente lancée")
    E["en_attente"] = attente[1:]
    args = ["gh", "workflow", "run", "creer.yml"]
    for k, v in (demande.get("inputs") or {}).items():
        args += ["-f", f"{k}={v}"]
    subprocess.run(args, check=False, env=dict(os.environ))


SERIES = {0: ("chiffre", "LE CHIFFRE DU LUNDI", "lechiffredulundi"),
          4: ("vrai_faux", "VRAI OU FAUX DU VENDREDI", "vraioufauxduvendredi")}


def serie_du_jour(R, now, h):
    """Séries récurrentes (amélioration 23 du 25/11) : le 1er créneau du lundi = « Le chiffre du lundi », du vendredi =
    « Vrai ou faux du vendredi » (les abonnés reviennent pour un rendez-vous). (format, étiquette, hashtag) ou None."""
    if not R["creation"].get("series", True) or h != min(R["creation"]["heures"]):
        return None
    return SERIES.get(now.weekday())


def format_auto(R, now, h):
    """Séries du lundi et du vendredi ; dimanche, dernier créneau : « 3 actus de la semaine » ; samedi soir : « Le monde en
    60 secondes » ; sinon « Vrai ou faux ? » une vidéo sur N ; sinon buzz."""
    serie = serie_du_jour(R, now, h)
    if serie:
        return serie[0]
    F = R["creation"].get("formats") or {}
    if F.get("semaine") and now.weekday() == 6 and h == max(R["creation"]["heures"]):
        return "semaine"
    if F.get("monde60") and now.weekday() == 5 and h == max(R["creation"]["heures"]):
        return "monde60"                                    # samedi soir : « Le monde en 60 secondes »
    deja = sum(len(x) for x in (lire("garde.json") or {}).get("creation", {}).values())
    for nom in ("vrai_faux", "chiffre", "region"):          # 1 vidéo sur N pour chaque format (0 = jamais)
        n = int(F.get(nom) or 0)
        if n and deja % n == n - 1:
            return nom
    return "buzz"


if __name__ == "__main__":
    main()
