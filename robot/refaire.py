"""Refaire une vidéo EN CORRIGEANT ce qui n'allait pas (demande de l'auteur du 24/11 : jamais une copie à l'identique).

À la fin de chaque création, tout le travail est rangé dans la Release de la vidéo (`travail-<id>.tar.gz` : texte complet,
articles, bulletin, voix réussies, images et passages de vidéos). « Refaire » le reprend et ne refait que la partie fautive :
- « images » : les écrans signalés (bulletin, ou « écran 3, 5 » dans la remarque ; sinon tous) reçoivent d'AUTRES images
  (les anciennes sont interdites) ; texte et voix gardés ;
- « voix » : les phrases signalées sont dites avec des mots plus simples (sinon toutes redites, nouvelle prise) ;
- « texte » : l'IA réécrit les phrases fautives en tenant compte des problèmes et de la remarque ; les phrases inchangées
  gardent leur voix et leur image ;
- « tout » : nouvelle version (autre accroche, autre angle), autres images ;
- « auto » : choisi d'après les problèmes du bulletin.
Puis toutes les vérifications habituelles ; la nouvelle vidéo remplace l'ancienne sur le site.
"""
import json
import os
import re
import shutil
import tarfile
import time
import urllib.request

from . import controle, ecrire, ia, nombres
from . import voix as V
from .commun import ROBOT_UA

ETAPES_REFAIRE = ("auto", "controle", "texte", "voix", "images", "tout")
TAILLE_MAX_MEDIAS = 400 * 1024 * 1024               # au-delà, les images ne sont pas gardées (elles seront recherchées)


def archiver(script, articles, bulletin, dossier, vid):
    """Archive du travail (rangée dans la Release). Renvoie son chemin."""
    chemin = os.path.join(dossier, f"travail-{vid}.tar.gz")
    with open(os.path.join(dossier, "script.json"), "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in script.items() if not k.startswith("_") or k in ("_musique", "_reserve", "_citations_reserve", "_citations_toutes")}, f,
                  ensure_ascii=False, default=str)
    with open(os.path.join(dossier, "articles.json"), "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False)
    with open(os.path.join(dossier, "bulletin.json"), "w", encoding="utf-8") as f:
        json.dump(bulletin, f, ensure_ascii=False)
    medias = {os.path.basename(p["media"]["chemin"]) for p in script["phrases"]
              if (p.get("media") or {}).get("chemin") and os.path.exists(p["media"]["chemin"])}
    medias |= {os.path.basename(m["chemin"]) for m in (script.get("_citations_toutes") or []) + (script.get("_citations_reserve") or [])
               if m.get("chemin") and os.path.exists(m["chemin"])}    # extraits non montrés : gardés pour les refaire
    taille = sum(os.path.getsize(os.path.join(dossier, m)) for m in medias if os.path.exists(os.path.join(dossier, m)))
    with tarfile.open(chemin, "w:gz") as t:
        for nom in ("script.json", "articles.json", "bulletin.json"):
            t.add(os.path.join(dossier, nom), nom)
        if os.path.isdir(os.path.join(dossier, "memoire_voix")):
            t.add(os.path.join(dossier, "memoire_voix"), "memoire_voix")
        if taille <= TAILLE_MAX_MEDIAS:
            for m in sorted(medias):
                if os.path.exists(os.path.join(dossier, m)):
                    t.add(os.path.join(dossier, m), m)
    return chemin


def restaurer(v, dossier, repo):
    """Télécharge et ouvre l'archive de la vidéo `v`. Renvoie (script, articles, lignes du bulletin)."""
    os.makedirs(dossier, exist_ok=True)
    url = f"https://github.com/{repo}/releases/download/{v['tag']}/travail-{v['id']}.tar.gz"
    arch = os.path.join(dossier, "travail.tar.gz")
    req = urllib.request.Request(url, headers={"User-Agent": ROBOT_UA})
    with urllib.request.urlopen(req, timeout=300) as r, open(arch, "wb") as f:
        shutil.copyfileobj(r, f)
    with tarfile.open(arch) as t:
        t.extractall(dossier, filter="data")
    with open(os.path.join(dossier, "script.json"), encoding="utf-8") as f:
        script = json.load(f)
    with open(os.path.join(dossier, "articles.json"), encoding="utf-8") as f:
        articles = json.load(f)
    with open(os.path.join(dossier, "bulletin.json"), encoding="utf-8") as f:
        lignes = json.load(f).get("lignes") or []
    for cle in ("_citations_toutes", "_citations_reserve"):  # extraits de l'événement : dans le nouveau dossier aussi
        for m in script.get(cle) or []:
            if m.get("chemin"):
                m["chemin"] = os.path.join(dossier, os.path.basename(m["chemin"]))
    for p in script["phrases"]:                       # les fichiers sont maintenant dans le nouveau dossier
        if not p.get("media"):
            p.pop("media", None)                      # écran de texte : une image sera cherchée
        m = p.get("media")
        if m and m.get("chemin"):
            nouveau = os.path.join(dossier, os.path.basename(m["chemin"]))
            if os.path.exists(nouveau):
                m["chemin"] = nouveau
            else:
                p.pop("media")                         # image non gardée : elle sera recherchée de nouveau
        for k in ("mots", "son", "duree", "_sig", "_essais_image", "_voix_defaut", "_rejetees", "_garde_2e_avis"):
            p.pop(k, None)
    return script, articles, lignes


def reserve_extraits(ph):
    """Extraits des vidéos d'origine montrés dans l'ancienne version (un par extrait), gardés en réserve pour les phrases
    nouvelles quand le texte est refait (aucun extrait perdu)."""
    vus, reserve = set(), []
    for p in ph:
        m = p.get("media") or {}
        base = str(m.get("id", "")).split("-suite")[0]
        if m.get("citation") and base not in vus:
            vus.add(base); reserve.append(dict(m, id=base, suite=False))
    return reserve


def etape_auto(v):
    """Ce qu'il faut refaire d'après les problèmes restés ouverts dans le bulletin."""
    ouverts = [l for l in (v.get("controles") or {}).get("lignes") or [] if not l.get("corrige")]
    niveaux = {l.get("niveau") for l in ouverts}
    if "texte" in niveaux:
        return "texte"
    if niveaux & {"images", "video"}:
        return "images"
    if "voix" in niveaux:
        return "voix"
    if (v.get("controles") or {}).get("sautes"):         # seul un contrôle n'a pas pu se faire : on le refait, rien d'autre
        return "controle"
    return "tout"


def ecrans_cites(remarque, nb):
    """« écran 3 et 5 », « écrans 2, 4 » dans la remarque de l'auteur → indices (0, 1…)."""
    out = set()
    for groupe in re.findall(r"[ée]crans?\s*((?:\d+\s*(?:,|et|&|\s)\s*)*\d+)", remarque or "", re.I):
        out |= {int(n) - 1 for n in re.findall(r"\d+", groupe) if 0 < int(n) <= nb}
    return out


def indices_signales(script, lignes, niveaux):
    uids = {l.get("ecran") for l in lignes if not l.get("corrige") and l.get("niveau") in niveaux and l.get("ecran") is not None}
    return {i for i, p in enumerate(script["phrases"]) if p.get("uid") in uids}


def preparer(v, sujet, etape, remarque, dossier, repo, R, journal=print):
    """État de départ de `principal.fabriquer` pour refaire la vidéo `v` en corrigeant. Renvoie (etat, etape choisie)."""
    script, articles, lignes = restaurer(v, dossier, repo)
    if etape not in ETAPES_REFAIRE or etape == "auto":
        etape = etape_auto(v)
    journal(f"🔁 On refait « {v['titre']} » : {etape}" + (f" (remarque : « {remarque} »)" if remarque else ""))
    ph = script["phrases"]
    deja = set()
    nom_voix = script.get("voix_utilisee") or R["video"]["voix"]
    vitesse = float(R["video"]["vitesse"])
    memoire = os.path.join(dossier, "memoire_voix")
    problemes = [f"écran {i + 1} : {l['probleme']}" if l.get("ecran") is not None else l["probleme"]
                 for l in lignes if not l.get("corrige")
                 for i in [next((k for k, p in enumerate(ph) if p.get("uid") == l.get("ecran")), -1)]]
    faites = ["articles", "ecriture", "texte"]

    if etape == "controle":                               # tout est gardé ; écrans vides complétés ; contrôles refaits
        journal("  vidéo gardée telle quelle : seuls les contrôles sont refaits (et les écrans vides complétés)")
    elif etape == "images":
        cibles = ecrans_cites(remarque, len(ph)) | indices_signales(script, lignes, ("images", "video"))
        cibles = cibles or set(range(len(ph) - 1))          # rien de précis : toutes les images changent
        # + tous les écrans SANS vraie image (écran de texte, titre de presse) : ils reçoivent enfin une vraie vidéo
        cibles |= {i for i, p in enumerate(ph[:-1]) if not p.get("media") or (p.get("media") or {}).get("presse")}
        for i in cibles:
            m = ph[i].get("media") or {}
            if m.get("type") == "carte" or (m.get("citation") and i not in ecrans_cites(remarque, len(ph))):
                continue                                    # carte et courtes citations gardées
            if m.get("id"):
                deja.add(m["id"]); deja.add(str(m["id"]).rsplit("-", 1)[0])   # l'ancienne image est interdite
            ph[i].pop("media", None)
        script.pop("_reserve", None)
        script.pop("animation", None); script.pop("_sig_anime", None)   # nouveau style : nouvelle réalisation des scènes
        journal(f"  {len(cibles)} écran(s) recevront d'autres images")
    elif etape == "voix":
        cibles = ecrans_cites(remarque, len(ph)) | indices_signales(script, lignes, ("voix",))
        for i in (cibles or range(len(ph))):
            p = ph[i]
            V.oublier(p, nom_voix, vitesse, memoire)        # jamais la même prise
            if cibles:                                      # phrase signalée : mots plus simples
                try:
                    d, _ = ia.demander_json(controle.CONSIGNE_SIMPLIFIER, p["ecrit"], temperature=0.6, journal=journal)
                    if controle.simplification_valable(p["ecrit"], str(d.get("ecrit") or d.get("voix") or "")):
                        p["voix"] = nombres.dire_les_nombres(str(d["voix"])); p["ecrit"] = str(d.get("ecrit") or d["voix"])
                except ia.AucuneIA:
                    pass
        journal(f"  {len(cibles) or len(ph)} phrase(s) redite(s)")
    else:                                                   # texte ou tout : l'IA corrige le texte
        reserve = reserve_extraits(ph) if etape == "texte" else []
        nouveau = ecrire.refaire_texte(sujet, articles, script, problemes, remarque, tout=etape == "tout",
                                       journal=journal, format_=v.get("format") or "buzz")
        anciens = {p["ecrit"]: p for p in ph}
        for p in nouveau["phrases"]:
            vieux = anciens.get(p["ecrit"])
            if vieux and etape == "texte":                  # phrase inchangée : même voix (mémoire) et même image
                for k in ("media", "uid"):
                    if k in vieux:
                        p[k] = vieux[k]
        if etape == "tout":
            deja |= {str(p["media"]["id"]) for p in ph if (p.get("media") or {}).get("id")}
        for k in ("voix_utilisee", "_musique"):
            if k in script:
                nouveau[k] = script[k]
        if reserve:
            nouveau["_citations_reserve"] = reserve
        if script.get("_citations_toutes"):
            nouveau["_citations_toutes"] = script["_citations_toutes"]
        script = nouveau
        faites = ["articles", "ecriture"]                   # le texte corrigé repasse le contrôle des faits
    etat = dict(vid=v["_nouvel_id"], dossier=dossier, t0=time.time(), B=controle.Bulletin(), faites=faites,
                articles=articles, script=script, deja=deja, refaite=dict(de=v["id"], etape=etape, remarque=remarque))
    if etape not in ("images", "tout", "controle"):         # images gardées : pas de nouvelle recherche de vidéos du sujet
        etat.update(clips=[], presse_faite=True, carte_faite=True)
    return etat, etape
