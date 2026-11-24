"""Ordres envoyés par les boutons du site (workflow commande.yml), appliqués aux données puis enregistrés.

    ACTION=a_publier ID=<vidéo> python -m robot.commande
Actions sur une vidéo : a_publier, retirer, ecarter, supprimer, publier_maintenant, publier_force (malgré un défaut grave
signalé par le contrôle qualité : décision de l'auteur), publiee (TEXTE = lien TikTok), texte
(TEXTE = JSON {description, question, hashtags}). Sujets : sujet_ignorer, sujet_remettre. Autres : reglages (TEXTE = JSON),
buffer_test.
"""
import json
import os

from . import depot, publier
from .commun import MINIATURES, REGLAGES_DEFAUT, ecrire, iso, lire, noter, reglages


def _video(file, vid):
    for v in file["videos"]:
        if v["id"] == vid:
            return v
    raise ValueError(f"vidéo {vid} introuvable")


def _liste_textes(x, maxi, long):
    if isinstance(x, str):
        x = x.replace(",", " ").split()
    return [str(e).strip()[:long] for e in x or [] if str(e).strip()][:maxi]


def appliquer_reglages(d):
    """Seuls les réglages connus sont gardés, avec des bornes raisonnables."""
    R = reglages()
    B, Vd, P, C, Hs = (d.get(k) or {} for k in ("buzz", "video", "publication", "creation", "hashtags"))
    if "comptes" in B:
        R["buzz"]["comptes"] = [c.lstrip("@") for c in _liste_textes(B["comptes"], 40, 40)]
    for k, mini, maxi in (("vues_min", 0, 10**9), ("jaime_min", 0, 10**8), ("commentaires_min", 0, 10**7), ("heures", 6, 240)):
        if k in B:
            R["buzz"][k] = max(mini, min(maxi, int(B[k])))
    from .voix import CHATTERBOX, KOKORO, VOIX
    if Vd.get("voix") in VOIX or Vd.get("voix") in KOKORO or Vd.get("voix") in CHATTERBOX:
        R["video"]["voix"] = Vd["voix"]
    if "vitesse" in Vd:
        R["video"]["vitesse"] = max(0.65, min(1.1, float(Vd["vitesse"])))
    if P.get("mode") in ("cocher", "auto"):
        R["publication"]["mode"] = P["mode"]
    for bloc, src in (("publication", P), ("creation", C)):
        if "auto" in src:
            R[bloc]["auto"] = bool(src["auto"])
        if "heures" in src:
            R[bloc]["heures"] = [h for h in _liste_textes(src["heures"], 4, 5) if len(h) == 5 and h[2] == ":"]
    if "compte" in P:
        R["publication"]["compte"] = str(P["compte"]).strip().lstrip("@")[:60]
    if "chaine" in P:
        R["publication"]["chaine"] = str(P["chaine"]).strip().lstrip("@")[:60]
    if "heures_auto" in P:
        R["publication"]["heures_auto"] = bool(P["heures_auto"])
    for k in ("musique", "bruitages", "transitions", "carte", "images_generiques"):
        if k in Vd:
            R["video"][k] = bool(Vd[k])
    if "paralleles" in C:
        R["creation"]["paralleles"] = max(1, min(5, int(C["paralleles"])))
    F = C.get("formats") or {}
    if "vrai_faux" in F:
        R["creation"]["formats"]["vrai_faux"] = max(0, min(10, int(F["vrai_faux"])))
    for k in ("semaine", "monde60"):
        if k in F:
            R["creation"]["formats"][k] = bool(F[k])
    for k in ("chiffre", "region"):
        if k in F:
            R["creation"]["formats"][k] = max(0, min(10, int(F[k])))
    if "fixes" in Hs:
        R["hashtags"]["fixes"] = ["#" + h.lstrip("#") for h in _liste_textes(Hs["fixes"], 5, 30)]
    if "nombre" in Hs:
        R["hashtags"]["nombre"] = max(3, min(10, int(Hs["nombre"])))
    ecrire("reglages.json", {k: R[k] for k in REGLAGES_DEFAUT})
    noter("⚙️ Réglages enregistrés.")


def appliquer(action, vid, texte):
    if action == "reglages":
        return appliquer_reglages(json.loads(texte or "{}"))
    if action == "buffer_test":
        comptes = publier.comptes_tiktok()
        noter("🔌 Buffer répond. Comptes TikTok reliés : " + (", ".join(c["nom"] for c in comptes) or "aucun"))
        return
    if action in ("sujet_ignorer", "sujet_remettre"):
        B = lire("buzz.json") or {"sujets": []}
        for s in B["sujets"]:
            if s["id"] == vid:
                s["statut"] = "ignore" if action == "sujet_ignorer" else "nouveau"
                noter(("🙈 Sujet ignoré : " if action == "sujet_ignorer" else "↩️ Sujet remis : ") + s["titre"])
        return ecrire("buzz.json", B)

    file = publier.mettre_a_jour(lire("file.json") or {"videos": []})
    v = _video(file, vid)
    if action == "a_publier":
        v.update(statut="a_publier", coche_le=iso()); v.pop("echec_publication", None)
        noter(f"✅ « {v['titre']} » ajoutée à la file de publication.")
    elif action == "retirer":
        v["statut"] = "nouvelle"; v.pop("coche_le", None)
        noter(f"↩️ « {v['titre']} » retirée de la file de publication.")
    elif action == "ecarter":
        v["statut"] = "ecartee"
        noter(f"🛑 « {v['titre']} » écartée (ne sera pas publiée).")
    elif action in ("publier_maintenant", "publier_force"):
        rep = ENVOI.get(vid)
        from .controle import Refusee
        if isinstance(rep, Refusee):
            v.update(statut="a_verifier", echec_publication=f"{iso()} : {str(rep)[:300]}")
            noter(f"🛡️ « {v['titre']} » non publiée : {str(rep)[:180]}", "attention")
        elif isinstance(rep, Exception) or rep is None:
            v["echec_publication"] = f"{iso()} : {str(rep)[:200]}"
            noter(f"❌ « {v['titre']} » : publication refusée ({str(rep)[:160]})", "erreur")
        else:
            v.update(statut="publiee", publiee_le=iso(), buffer=rep)
            noter(f"🚀 « {v['titre']} » envoyée sur TikTok" + ("" if rep.get("etiquette_ia") else
                                                                 " — sans l'étiquette IA : coche-la dans l'appli TikTok"))
    elif action == "publiee":
        v.update(statut="publiee", publiee_le=iso())
        if texte.startswith("https://"):
            v["lien_tiktok"] = texte[:300]
        noter(f"🚀 « {v['titre']} » marquée publiée.")
    elif action == "texte":
        d = json.loads(texte or "{}")
        if "description" in d: v["description"] = str(d["description"]).strip()[:600]
        if "question" in d: v["question"] = str(d["question"]).strip()[:200]
        if "hashtags" in d: v["hashtags"] = ["#" + h.lstrip("#") for h in _liste_textes(d["hashtags"], 10, 40)]
        noter(f"✏️ Description de « {v['titre']} » modifiée.")
    elif action == "supprimer":
        depot.supprimer_release(v.get("tag"))
        mini = os.path.join(MINIATURES, f"{v['id']}.jpg")
        if os.path.exists(mini):
            os.remove(mini)
        file["videos"].remove(v)
        noter(f"🗑️ « {v['titre']} » supprimée.")
    else:
        raise ValueError(f"action inconnue : {action}")
    ecrire("file.json", file)


ENVOI = {}                                   # réponse de Buffer, obtenue UNE fois avant l'enregistrement (qui peut se répéter)


def main():
    action, vid, texte = os.environ.get("ACTION", ""), os.environ.get("ID", ""), os.environ.get("TEXTE", "")
    if action in ("publier_maintenant", "publier_force"):
        from . import controle
        v = _video(lire("file.json") or {"videos": []}, vid)
        try:
            ENVOI[vid] = controle.verifier_et_envoyer(v, reglages(), forcer=action == "publier_force")
        except Exception as e:
            ENVOI[vid] = e
    depot.enregistrer(lambda: appliquer(action, vid, texte), f"Ordre du site : {action} {vid}".strip())


if __name__ == "__main__":
    main()
