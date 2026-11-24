"""Statistiques de la chaîne (workflow stats.yml, toutes les 3 heures) : vues, j'aime, commentaires de nos vidéos publiées.

Le robot lit le compte TikTok de la chaîne (Réglages → Publication → « Pseudo TikTok de la chaîne ») comme il lit les
comptes d'actualité, retrouve chacune de nos vidéos (heure de publication + texte de la description), puis calcule :
- les meilleures heures de publication (vues médianes selon l'heure, 2 vidéos au moins par heure) ;
- ce qui marche le mieux : formats, ambiances, hashtags (vues moyennes, 2 vidéos au moins).
Résultat : `stats` dans chaque vidéo de file.json + docs/donnees/stats.json (onglet « 📊 Stats » du site).
Les meilleures heures servent à la publication automatique si la case « Heures choisies par les statistiques » est cochée.
"""
import datetime
import re
import statistics

from . import buzz, depot
from .commun import PARIS, ecrire, iso, lire, maintenant, noter, reglages

AGE_MIN_H = 24                    # une vidéo n'entre dans les comparaisons qu'après 24 h en ligne


def _mots(t):
    return set(re.findall(r"[a-zà-ÿ0-9]{4,}", (t or "").lower()))


def en_ligne_le(v):
    """Heure de mise en ligne prévue : celle de la programmation Buffer (UTC) si la vidéo a été programmée, sinon l'envoi."""
    quand = (v.get("buffer") or {}).get("quand") if isinstance(v.get("buffer"), dict) else None
    if quand:
        return datetime.datetime.fromisoformat(quand.replace("Z", "+00:00"))
    return datetime.datetime.fromisoformat(v["publiee_le"])


def rapprocher(nos, tiktok):
    """Pour chacune de nos vidéos publiées, la vidéo TikTok correspondante (heure ±3 h et texte commun), ou rien."""
    paires, prises = {}, set()
    for v in nos:
        if v.get("statut") != "publiee" or not v.get("publiee_le"):
            continue
        t = en_ligne_le(v).timestamp()
        mots = _mots(v.get("description", "") + " " + " ".join(v.get("hashtags") or []))
        meilleur, note = None, 0
        for x in tiktok:
            if x["id"] in prises or not x.get("date") or abs(x["date"] - t) > 3 * 3600:
                continue
            n = len(mots & _mots(x["texte"])) + (3 if v.get("lien_tiktok", "").endswith(x["id"]) else 0)
            if n > note:
                meilleur, note = x, n
        if meilleur and note >= 2:
            paires[v["id"]] = meilleur; prises.add(meilleur["id"])
    return paires


def _heure(v):
    return en_ligne_le(v).astimezone(PARIS).strftime("%H:00")


def analyser(videos, now=None):
    now = now or maintenant()
    mures = [v for v in videos if v.get("stats") and v.get("publiee_le")
             and (now - datetime.datetime.fromisoformat(v["publiee_le"])).total_seconds() > AGE_MIN_H * 3600]

    def groupe(cle):
        g = {}
        for v in mures:
            for k in cle(v):
                if k:
                    g.setdefault(k, []).append(v["stats"]["vues"])
        return sorted(({"nom": k, "videos": len(x), "vues_moyennes": round(statistics.mean(x)), "vues_mediane": round(statistics.median(x))}
                       for k, x in g.items() if len(x) >= 2), key=lambda e: -e["vues_mediane"])

    heures = groupe(lambda v: [_heure(v)])
    meilleures = []
    for h in heures:                                      # 2 heures éloignées d'au moins 3 heures
        if all(abs(int(h["nom"][:2]) - int(m[:2])) >= 3 for m in meilleures):
            meilleures.append(h["nom"])
        if len(meilleures) == 2:
            break
    toutes = [v["stats"]["vues"] for v in mures]
    return {"maj": iso(now), "videos_mesurees": len(mures), "vues_total": sum(v["stats"]["vues"] for v in videos if v.get("stats")),
            "vues_mediane": round(statistics.median(toutes)) if toutes else 0,
            "heures": heures, "meilleures_heures": sorted(meilleures) if len(meilleures) == 2 else [],
            "formats": groupe(lambda v: [v.get("format") or "buzz"]),
            "categories": groupe(lambda v: [v.get("categorie") or ""]), "humeurs": groupe(lambda v: [v.get("humeur") or "neutre"]),
            "hashtags": groupe(lambda v: [h.lower() for h in v.get("hashtags") or []])[:15],
            "top": [{"id": v["id"], "titre": v["titre"], **v["stats"]} for v in sorted(mures, key=lambda v: -v["stats"]["vues"])[:5]]}


def main():
    R = reglages()
    pseudo = str(R["publication"].get("chaine") or "").strip().lstrip("@")
    if not pseudo:
        print("Pseudo TikTok de la chaîne non réglé : rien à mesurer.")
        return
    tiktok = buzz.videos_du_compte(pseudo, n=60)
    if not tiktok:
        print(f"@{pseudo} : aucune vidéo lue (compte vide ou TikTok refuse) : on réessaiera.")
        return

    def appliquer():
        file = lire("file.json") or {"videos": []}
        paires = rapprocher(file["videos"], tiktok)
        for v in file["videos"]:
            x = paires.get(v["id"])
            if not x:
                continue
            v["stats"] = {k: x[k] for k in ("vues", "jaime", "commentaires", "partages")}
            v["stats"]["maj"] = iso()
            v["lien_tiktok"] = x["url"]
            hist = v.setdefault("stats_hist", [])
            hist.append([iso(), x["vues"]]); del hist[:-60]
        for v in file["videos"]:                          # envoyée mais introuvable sur TikTok 2 h après l'heure prévue
            if v.get("statut") == "publiee" and v.get("publiee_le") and v["id"] not in paires and not v.get("lien_tiktok") \
                    and not v.get("non_vue_sur_tiktok") and maintenant() - en_ligne_le(v) > datetime.timedelta(hours=2):
                v["non_vue_sur_tiktok"] = iso()
                noter(f"⚠️ « {v['titre']} » : envoyée à Buffer mais introuvable sur TikTok 2 h après l'heure prévue. "
                      "Regarde dans Buffer (publication refusée ?) et sur l'appli TikTok (brouillons, notifications).", "erreur")
        S = analyser(file["videos"])
        S["chaine"] = pseudo; S["lues"] = len(tiktok); S["retrouvees"] = len(paires)
        ecrire("file.json", file); ecrire("stats.json", S)
        if S["meilleures_heures"]:
            print("meilleures heures :", S["meilleures_heures"])
    depot.enregistrer(appliquer, f"Statistiques du {maintenant():%d/%m %Hh}")
    noter(f"📊 Statistiques relevées : {len(tiktok)} vidéos de @{pseudo} lues.")


if __name__ == "__main__":
    main()
