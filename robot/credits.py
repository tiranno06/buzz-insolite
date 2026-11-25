"""Vérification des crédits des IA gratuites AVANT de créer une vidéo (demande de l'auteur du 25/11).

Le 25/11, 5 vidéos lancées en même temps ont épuisé les IA gratuites (Mistral « abonnement nécessaire », OpenRouter
« limite du jour », Groq et Gemini saturées) : textes écrits et vérifiés par de petites IA de secours, phrases réduites à des
nombres, titres en anglais, vidéos à 0/100. Désormais :
- `verifier()` essaie chaque IA avec une toute petite question (texte, puis image) ; il faut au moins DEUX IA qui écrivent
  (une qui écrit, une AUTRE qui vérifie les faits) et UNE IA qui voit les images ;
- il compte aussi les vidéos déjà en fabrication : au plus `MAX_EN_MEME_TEMPS` à la fois avec les IA gratuites ;
- si ce n'est pas bon, la création est MISE EN ATTENTE (garde.json → « en_attente ») au lieu de partir : la garde (toutes les
  15 min) refait la vérification et la lance d'elle-même dès que les IA sont de nouveau disponibles (une à la fois).
"""
import base64
import json
import os
import urllib.request

from . import ia
from .commun import ROBOT_UA, iso, lire, maintenant

MAX_EN_MEME_TEMPS = 2                     # vidéos fabriquées en même temps avec les IA gratuites


def _pixel():
    """Petite image (16 × 16, rouge) pour vérifier les IA qui voient, en JPEG base64."""
    import io
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (16, 16), (200, 30, 30)).save(b, "JPEG")
    return base64.b64encode(b.getvalue()).decode()


def _essai_texte(fourn):
    F = ia.FOURNISSEURS[fourn]
    modeles = ia._modeles_openrouter() if fourn == "openrouter" else F["modeles"]
    derniere = "aucun modèle"
    for modele in [m for m in modeles if (fourn, m) not in ia._MORTS][:2]:
        try:
            ia._appel(fourn, modele, [{"role": "user", "content": 'Réponds en json : {"ok": true}'}], 0, 20)
            return True, modele
        except Exception as e:
            derniere = _raison(e)
    return False, derniere


def _essai_image(fourn):
    modeles = ia._modeles_openrouter(vision=True) if fourn == "openrouter" else ia.VISION.get(fourn, ())
    contenu = [{"type": "text", "text": 'Réponds en json : {"ok": true}'},
               {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + _pixel()}}]
    derniere = "aucun modèle"
    for modele in [m for m in modeles if (fourn, m) not in ia._MORTS][:2]:
        try:
            ia._appel(fourn, modele, [{"role": "user", "content": contenu}], 0, 20)
            return True, modele
        except Exception as e:
            derniere = _raison(e)
    return False, derniere


def _raison(e):
    """Raison lisible d'un refus (pour le journal et la page Santé)."""
    corps = ""
    try:
        corps = e.read()[:300].decode("utf-8", "ignore") if hasattr(e, "read") else str(e)
    except Exception:
        corps = str(e)
    bas = corps.lower()
    code = getattr(e, "code", None)
    if code == 402 or "subscription" in bas or "billing" in bas:
        return "abonnement nécessaire (clé à renouveler)"
    if code in (401, 403):
        return "clé refusée"
    if code == 429 and ("per-day" in bas or "per day" in bas or "(rpd)" in bas or "daily" in bas):
        return "limite du jour atteinte"
    if code == 429:
        return "trop de demandes en ce moment"
    return f"erreur {code or ''} {corps[:60]}".strip()


def en_fabrication():
    """Vidéos en fabrication en ce moment (tâches « Créer » qui tournent sur GitHub)."""
    try:
        import subprocess
        n = 0
        for st in ("in_progress", "queued"):
            r = subprocess.run(["gh", "run", "list", "--workflow", "creer.yml", "--status", st, "--json", "databaseId"],
                               capture_output=True, text=True, timeout=60)
            n += len(json.loads(r.stdout or "[]"))
        return n
    except Exception:
        return 0


def verifier(nombre=1, deja_en_cours=None, journal=print):
    """(ok, résumé, détail par IA). ok = assez d'IA disponibles et au moins une place libre (voir `places`)."""
    texte, vision = {}, {}
    for f in ia.ORDRE:
        if not os.environ.get(ia.FOURNISSEURS[f]["cle"]):
            texte[f] = (False, "pas de clé"); continue
        texte[f] = _essai_texte(f)
    for f in ("gemini", "mistral", "groq", "openrouter"):
        if not os.environ.get(ia.FOURNISSEURS[f]["cle"]) or not texte.get(f, (False,))[0]:
            vision[f] = (False, texte.get(f, (False, "pas de clé"))[1]); continue
        vision[f] = _essai_image(f)
    ecrivent = [f for f, (ok, _) in texte.items() if ok]
    voient = [f for f, (ok, _) in vision.items() if ok]
    en_cours = en_fabrication() if deja_en_cours is None else deja_en_cours
    raisons = []
    if len(ecrivent) < 2:
        raisons.append(f"{len(ecrivent)} IA qui écrit disponible (il en faut 2 : une écrit, une autre vérifie)")
    if not voient:
        raisons.append("aucune IA qui voit les images disponible")
    if en_cours >= MAX_EN_MEME_TEMPS:
        raisons.append(f"déjà {en_cours} vidéo(s) en fabrication (au plus {MAX_EN_MEME_TEMPS} à la fois avec les IA gratuites)")
    detail = {f: {"ecrit": texte[f][0], "voit": vision.get(f, (False,))[0],
                  "raison": "" if texte[f][0] else texte[f][1]} for f in texte}
    resume = ("✅ IA disponibles : " + ", ".join(ecrivent) + (" ; voient : " + ", ".join(voient) if voient else "")) \
        if not raisons else "⏸️ " + " ; ".join(raisons)
    journal(f"  vérification des IA avant création : {resume}")
    for f, d in detail.items():
        if not d["ecrit"]:
            journal(f"    {f} : {d['raison']}")
    return not raisons, resume, detail


def mettre_en_attente(inputs, raison):
    """Création demandée mais IA insuffisantes : rangée dans garde.json (« en_attente ») pour la garde."""
    from . import depot
    from .commun import ecrire, noter

    def appliquer():
        G = lire("garde.json") or {}
        attente = G.setdefault("en_attente", [])
        ref = inputs.get("refaire")
        if ref and any((x.get("inputs") or {}).get("refaire") == ref for x in attente):
            return                                            # même vidéo déjà en attente : pas deux fois
        attente.append({"inputs": inputs, "demande_le": iso(), "raison": raison})
        G["credits"] = {"le": iso(), "resume": raison}
        ecrire("garde.json", G)
        noter(f"⏸️ Création mise en attente : {raison}. Elle partira toute seule dès que les IA gratuites seront de nouveau "
              "disponibles (vérifié toutes les 15 min).", "attention")
    depot.enregistrer(appliquer, "Création mise en attente (IA gratuites saturées)")


def places(deja_en_cours=None):
    """Nombre de vidéos qui peuvent partir maintenant (au plus `MAX_EN_MEME_TEMPS` en fabrication)."""
    en_cours = en_fabrication() if deja_en_cours is None else deja_en_cours
    return max(0, MAX_EN_MEME_TEMPS - en_cours)
