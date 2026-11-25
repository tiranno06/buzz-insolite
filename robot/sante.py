"""Santé du robot ET réparation automatique, sans l'aide de l'auteur (workflow sante.yml : chaque nuit, ou bouton du site).

Vérifie : IA gratuites (texte et regard), sources de vidéos libres (YouTube CC, PeerTube, Internet Archive, Wikimedia,
Vimeo), presse (Bing), Buffer, comptes TikTok suivis, créations des dernières 24 h, durée de chaque étape.
Répare tout seul :
- comptes TikTok muets 3 contrôles de suite → mis en pause 7 jours (`buzz.en_pause`), puis réessayés ;
- sujets restés « en_cours » plus de 6 h ou « echec » (création plantée) → remis en « nouveau » une fois ;
- vidéos pas encore publiées : l'IA revoit des images de la vidéo ; trop d'images hors sujet, ou vidéo « à vérifier » →
  REFAITE en corrigeant (robot/refaire.py), 2 fois au plus par vidéo, 3 réparations par nuit au plus.
Résultat : docs/donnees/sante.json (onglet « 🩺 Santé » du site) + journal.
"""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

from . import depot, ia
from .commun import ROBOT_UA, ecrire, iso, lire, maintenant, noter, reglages

REPARATIONS_PAR_NUIT = 3
REPARATIONS_PAR_VIDEO = 2


def _ok(nom, fonction):
    try:
        detail = fonction()
        return {"nom": nom, "ok": True, "detail": str(detail or "")[:120]}
    except Exception as e:
        return {"nom": nom, "ok": False, "detail": str(e)[:160]}


def _json(url, entetes=None):
    req = urllib.request.Request(url, headers={"User-Agent": ROBOT_UA, **(entetes or {})})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def verifier_ia():
    out = []
    for f in ia.ORDRE:
        F = ia.FOURNISSEURS[f]
        if not os.environ.get(F["cle"]):
            out.append({"nom": f, "ok": False, "detail": "pas de clé"}); continue
        out.append(_ok(f, lambda f=f: ia.demander_json('Réponds uniquement en JSON : {"ok": true}', "Petit test, réponds en json.",
                                                       max_tokens=300,
                                                       exclure=[x for x in ia.ORDRE if x != f], journal=lambda *a: None)[1]))
    return out


def quotas_ia(videos):
    """Tableau des quotas des IA gratuites (amélioration 18 du 25/11) : appels et refus des vidéos des 24 dernières heures,
    plus ce qu'il reste chez chaque fournisseur d'après le test de cette nuit (quand il le dit)."""
    import datetime
    limite = maintenant() - datetime.timedelta(hours=24)
    out = {f: {"appels": 0, "refus": 0, "erreurs": 0} for f in ia.ORDRE}
    for v in videos:
        try:
            if datetime.datetime.fromisoformat(v.get("cree_le", "")) < limite:
                continue
        except ValueError:
            continue
        for f, st in (v.get("ia_quotas") or {}).items():
            o = out.setdefault(f, {"appels": 0, "refus": 0, "erreurs": 0})
            for k in ("appels", "refus", "erreurs"):
                o[k] += int(st.get(k) or 0)
    for f, st in ia.QUOTAS.items():                           # restes annoncés lors du test de santé
        for k, val in st.items():
            if k.startswith("restant") or k.startswith("limite"):
                out.setdefault(f, {})[k] = val
    for f, o in out.items():
        total = o.get("appels", 0) + o.get("refus", 0)
        o["sature"] = bool(total) and o.get("refus", 0) / total > 0.3
    return out


def verifier_sources():
    from . import images, sources
    tests = [
        ("Presse (Bing Actualités)", lambda: f"{len(sources.bing('France', n=5))} articles"),
        ("PeerTube (vidéos libres)", lambda: f"{len(images._cand_peertube('Paris', print))} vidéos"),
        ("Internet Archive (vidéos libres)", lambda: f"{len(images._cand_archive('Paris', print))} vidéos"),
        ("Wikimedia Commons", lambda: _json("https://commons.wikimedia.org/w/api.php?action=query&format=json&list=search&srsearch=Paris&srlimit=1")["query"]["search"][0]["title"]),
        ("YouTube Creative Commons", lambda: f"{len(images._cand_youtube('Paris', print))} vidéos"),
    ]
    if os.environ.get("VIMEO_TOKEN"):
        tests.append(("Vimeo (vidéos libres)", lambda: f"{len(images._cand_vimeo('Paris', print))} vidéos"))
    return [_ok(n, f) for n, f in tests]


def verifier_buffer():
    from . import publier
    if not os.environ.get("BUFFER_API_KEY"):
        return {"nom": "Buffer", "ok": False, "detail": "pas de clé"}
    return _ok("Buffer", lambda: ", ".join(c["nom"] for c in publier.comptes_tiktok()))


def comptes_et_pauses(precedent):
    """Comptes TikTok : muets à 3 contrôles de suite = pause de 7 jours (réessayés ensuite)."""
    B = lire("buzz.json") or {}
    R = reglages()
    series = dict((precedent or {}).get("comptes_muets") or {})
    pauses = dict(R["buzz"].get("en_pause") or {})
    for pseudo, e in (B.get("comptes") or {}).items():
        series[pseudo] = 0 if e.get("ok") else series.get(pseudo, 0) + 1
        if series[pseudo] >= 3 and pseudo not in pauses:
            pauses[pseudo] = iso()
            noter(f"🩺 Compte @{pseudo} muet 3 fois de suite : mis en pause 7 jours (réessayé ensuite).", "attention")
    limite = maintenant() - datetime.timedelta(days=7)
    for pseudo, quand in list(pauses.items()):
        if datetime.datetime.fromisoformat(quand) < limite:
            pauses.pop(pseudo); series[pseudo] = 0
    return series, pauses


def durees_moyennes(videos):
    recentes = [v for v in videos if v.get("durees")][:10]
    if not recentes:
        return {}
    etapes = {k for v in recentes for k in v["durees"]}
    out = {k: round(sum(v["durees"].get(k, 0) for v in recentes) / len(recentes)) for k in etapes}
    out["total"] = round(sum(v.get("fabrication_s", 0) for v in recentes) / len(recentes))
    return out


def creations_24h():
    """Créations des dernières 24 h (réussies / ratées), lues sur GitHub."""
    try:
        r = subprocess.run(["gh", "api", f"repos/{depot.depot()}/actions/workflows/creer.yml/runs?per_page=30"],
                           capture_output=True, text=True, timeout=60)
        runs = json.loads(r.stdout).get("workflow_runs") or []
    except Exception:
        return {}
    limite = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
    recents = [x for x in runs if datetime.datetime.fromisoformat(x["created_at"].replace("Z", "+00:00")) > limite]
    return {"reussies": sum(1 for x in recents if x.get("conclusion") == "success"),
            "ratees": sum(1 for x in recents if x.get("conclusion") == "failure"),
            "en_cours": sum(1 for x in recents if x.get("status") != "completed")}


CONSIGNE_AUDIT = """On te montre des images d'une vidéo TikTok d'actualité sur le SUJET donné. Pour chaque image numérotée,
dis si elle a un rapport avec le sujet (le sujet lui-même, son lieu, ses personnes, son domaine) : "colle" true / false.
Une image de titre ou de texte compte comme « colle ». Réponds uniquement en JSON :
{"images": [{"n": numéro, "colle": true/false, "probleme": "…"}]}"""


def audit_video(v, journal=print):
    """Revoit 8 images de la vidéo finie : renvoie la liste des problèmes trouvés (vide = rien à redire)."""
    with tempfile.TemporaryDirectory() as d:
        mp4 = os.path.join(d, "v.mp4")
        req = urllib.request.Request(v["url"], headers={"User-Agent": ROBOT_UA})
        with urllib.request.urlopen(req, timeout=300) as r, open(mp4, "wb") as f:
            f.write(r.read())
        duree = float(v.get("duree") or 60)
        imgs = []
        for k in range(8):
            img = os.path.join(d, f"i{k}.jpg")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{duree * (0.06 + 0.11 * k):.2f}", "-i", mp4,
                            "-frames:v", "1", "-vf", "scale=432:-2", img])
            if os.path.exists(img):
                imgs.append(img)
        problemes = []
        for k in range(0, len(imgs), 5):
            paquet = imgs[k:k + 5]
            avis, _ = ia.regarder_json(CONSIGNE_AUDIT, f"SUJET : {v.get('sujet') or v['titre']}", paquet, journal=journal)
            for a in avis.get("images") or []:
                if a.get("colle") is False:
                    problemes.append(str(a.get("probleme") or "image hors sujet")[:80])
        return problemes if len(problemes) >= 2 else []


def deja_en_refaire():
    """Identifiants des vidéos qu'une création « Refaire <id> » est déjà en train de refaire (jamais deux fois en même temps :
    le 24/11, la santé lancée à la main a refait une vidéo déjà en cours de refaire)."""
    ids = set()
    for statut in ("in_progress", "queued"):
        try:
            r = subprocess.run(["gh", "api", f"repos/{depot.depot()}/actions/workflows/creer.yml/runs?status={statut}&per_page=50"],
                               capture_output=True, text=True, timeout=60)
            for x in json.loads(r.stdout).get("workflow_runs") or []:
                titre = str(x.get("display_title") or "")
                if titre.startswith("Refaire "):
                    ids.add(titre.split()[1])
        except Exception:
            pass
    # … ou qui attend déjà son tour faute d'IA disponibles (garde.json → en_attente) : pas une 2e fois (25/11)
    ids |= {str((x.get("inputs") or {}).get("refaire")) for x in (lire("garde.json") or {}).get("en_attente") or []
            if (x.get("inputs") or {}).get("refaire")}
    return ids


def reparer(journal=print):
    """Vidéos pas encore publiées qui ont un problème → refaites en corrigeant (sans l'aide de l'auteur)."""
    file = lire("file.json") or {"videos": []}
    occupees = deja_en_refaire()
    limite = maintenant() - datetime.timedelta(days=7)
    faites = []
    for v in file["videos"]:
        if len(faites) >= REPARATIONS_PAR_NUIT:
            break
        if v.get("essai") or v.get("statut") not in ("nouvelle", "a_publier", "a_verifier") or not v.get("url", "").startswith("https"):
            continue
        try:
            if datetime.datetime.fromisoformat(v.get("cree_le", "")) < limite:
                continue
        except ValueError:
            continue
        if int(v.get("reparations", 0)) >= REPARATIONS_PAR_VIDEO or v["id"] in occupees:
            continue
        raisons = []
        if v.get("statut") == "a_verifier":
            raisons = [l["probleme"] for l in (v.get("controles") or {}).get("lignes") or [] if not l.get("corrige")][:3] or ["à vérifier"]
            etape = "auto"
        else:
            try:
                raisons = audit_video(v, journal)
            except Exception as e:
                journal(f"  audit de « {v['titre']} » impossible ({str(e)[:80]})")
            etape = "images"
        if not raisons:
            continue
        remarque = "Réparation automatique : " + " ; ".join(raisons)[:250]
        r = subprocess.run(["gh", "workflow", "run", "creer.yml", "-f", f"refaire={v['id']}", "-f", f"etape={etape}",
                            "-f", f"remarque={remarque}", "-f", "origine=reparation"], capture_output=True, text=True)
        if r.returncode == 0:
            faites.append({"id": v["id"], "titre": v["titre"], "etape": etape, "raison": remarque, "le": iso()})
            journal(f"  🔧 « {v['titre']} » sera refaite ({etape}) : {remarque}")
        else:
            journal(f"  réparation de « {v['titre']} » non lancée : {r.stderr[-160:]}")
    return faites


def debloquer_sujets():
    """Sujets restés réservés plus de 6 h, ou en échec : remis en jeu (une seule fois pour un échec)."""
    B = lire("buzz.json") or {"sujets": []}
    remis = 0
    for s in B.get("sujets") or []:
        vieux = False
        if s.get("statut") == "en_cours" and s.get("reserve_le"):
            vieux = maintenant() - datetime.datetime.fromisoformat(s["reserve_le"]) > datetime.timedelta(hours=6)
        if vieux or (s.get("statut") == "echec" and not s.get("deja_remis")):
            s["statut"] = "nouveau"; s.pop("reserve_le", None)
            s["deja_remis"] = s.get("deja_remis", False) or not vieux
            remis += 1
    return B, remis


def reparer_brouillons(journal=print):
    """Vidéos dont la Release est restée en brouillon (invisibles sur le site et pour Buffer) : rendues publiques."""
    if not depot.en_ligne():
        return []
    faites = []
    for tag in depot.releases_brouillon():
        try:
            depot.rendre_publique(tag)
            faites.append(tag)
        except Exception as e:
            journal(f"  {tag} toujours en brouillon ({str(e)[:80]})")
    if faites:
        noter(f"🩺 {len(faites)} vidéo(s) rendue(s) de nouveau visible(s) sur le site (restées en brouillon sur GitHub).", "attention")
    return faites


def main():
    precedent = lire("sante.json") or {}
    journal = print
    reparer_brouillons(journal)
    for f in ia.ORDRE:                     # modèles réellement disponibles (préférés encore publiés + secours trouvés en ligne)
        if os.environ.get(ia.FOURNISSEURS[f]["cle"]):
            journal(f"  modèles {f} : texte {', '.join(ia.modeles(f)) or 'aucun'} ; images {', '.join(ia.modeles(f, vision=True)) or 'aucun'}")
    ias, sources_, buffer_ = verifier_ia(), verifier_sources(), verifier_buffer()
    series, pauses = comptes_et_pauses(precedent)
    videos = (lire("file.json") or {}).get("videos") or []
    reparations = [] if "--sans-reparation" in sys.argv else reparer(journal)
    B, remis = debloquer_sujets()
    B_comptes = (lire("buzz.json") or {}).get("comptes") or {}
    pannes = [x["nom"] for x in ias + sources_ + [buffer_] if not x["ok"]]
    S = {"maj": iso(), "ia": ias, "sources": sources_, "buffer": buffer_,
         "comptes": {"lus": sum(1 for e in B_comptes.values() if e.get("ok")), "total": len(B_comptes),
                     "en_pause": sorted(pauses)},
         "comptes_muets": series, "durees": durees_moyennes(videos), "creations_24h": creations_24h(),
         "quotas": quotas_ia(videos),
         "reparations": (reparations + (precedent.get("reparations") or []))[:20], "sujets_remis": remis,
         "resume": "✅ Tout fonctionne" if not pannes else "⚠️ En panne : " + ", ".join(pannes)}

    def appliquer():
        ecrire("sante.json", S)
        R = reglages(); R["buzz"]["en_pause"] = pauses; ecrire("reglages.json", R)
        if remis:
            B2, _ = debloquer_sujets(); ecrire("buzz.json", B2)
        F = lire("file.json") or {"videos": []}
        for v in F["videos"]:
            if any(r["id"] == v["id"] for r in reparations):
                v["reparations"] = int(v.get("reparations", 0)) + 1
        ecrire("file.json", F)
        noter(f"🩺 Santé du robot : {S['resume']}" + (f" ; {len(reparations)} vidéo(s) en réparation" if reparations else "")
              + (f" ; {remis} sujet(s) débloqué(s)" if remis else ""), "info" if not pannes else "attention")
    depot.enregistrer(appliquer, "Santé du robot")


if __name__ == "__main__":
    main()
