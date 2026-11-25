"""IA gratuites (mêmes clés que jt-auto) : Mistral, Groq, Gemini, puis OpenRouter (modèles « :free »).

Chaque fournisseur a un quota gratuit : quand l'un refuse (quota, panne, modèle retiré), on passe au modèle suivant, puis au
fournisseur suivant. `demander_json(consigne, texte)` renvoie toujours un objet JSON (lu même s'il est entouré de texte).
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

from .commun import ROBOT_UA

FOURNISSEURS = {
    "mistral": dict(cle="MISTRAL_API_KEY", url="https://api.mistral.ai/v1/chat/completions",
                    modeles=("mistral-small-latest", "mistral-medium-latest", "ministral-14b-2512", "ministral-8b-latest",
                             "open-mistral-nemo")),
    "groq": dict(cle="GROQ_API_KEY", url="https://api.groq.com/openai/v1/chat/completions",
                 modeles=("llama-3.3-70b-versatile", "openai/gpt-oss-120b", "moonshotai/kimi-k2-instruct-0905", "qwen/qwen3-32b",
                          "openai/gpt-oss-20b", "llama-3.1-8b-instant")),
    "gemini": dict(cle="GEMINI_API_KEY", url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                   modeles=("gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-2.5-flash-lite")),
    "openrouter": dict(cle="OPENROUTER_API_KEY", url="https://openrouter.ai/api/v1/chat/completions", modeles=()),
}
ORDRE = ("mistral", "groq", "gemini", "openrouter")
UTILISES = {}                          # fournisseur → nombre d'appels réussis (affiché dans le journal)
_SAUTES = set()                        # fournisseurs à quota épuisé pendant ce passage du robot
_MORTS = set()                         # (fournisseur, modèle) retirés par le fournisseur : plus jamais essayés pendant ce passage
RETIRE = ("does not exist", "no longer available", "not found", "decommissioned", "deprecated", "is not supported")


def _mort(fourn, modele, code, corps):
    if code in (400, 404) and any(m in corps.lower() for m in RETIRE):
        _MORTS.add((fourn, modele))
    bas = corps.lower()
    # fournisseur entier hors service pour ce passage (25/11 : Mistral « You need a subscription » 402 à CHAQUE appel,
    # 111 essais perdus par vidéo ; OpenRouter « free-models-per-day » : plus rien jusqu'au lendemain) : plus essayé
    par_jour = "per-day" in bas or "per day" in bas or "perday" in bas
    if code in (401, 402, 403) or "billing" in bas or "subscription" in bas:
        _SAUTES.add(fourn)
    elif par_jour:
        # Gemini et Groq comptent la limite du jour PAR MODÈLE (25/11 au soir : Gemini entier mis de côté alors que ses
        # autres modèles restaient libres) : seul ce modèle est écarté ; OpenRouter : limite commune à tous ses modèles
        if fourn in ("gemini", "groq"):
            _MORTS.add((fourn, modele))
        else:
            _SAUTES.add(fourn)


class AucuneIA(Exception):
    pass


def disponibles():
    return [f for f in ORDRE if os.environ.get(FOURNISSEURS[f]["cle"]) and f not in _SAUTES]


def _modeles_openrouter(vision=False):
    """Modèles gratuits du moment (ils changent souvent) : les plus grands d'abord. vision=True : seulement ceux qui voient
    les images (4e fournisseur pour le contrôle des images, 25/11)."""
    try:
        req = urllib.request.Request("https://openrouter.ai/api/v1/models", headers={"User-Agent": ROBOT_UA})
        d = json.loads(urllib.request.urlopen(req, timeout=20).read())
        libres = [m for m in d.get("data", []) if str(m.get("id", "")).endswith(":free")
                  and (not vision or "image" in ((m.get("architecture") or {}).get("input_modalities") or []))]
        libres.sort(key=lambda m: -(m.get("context_length") or 0))
        return tuple(m["id"] for m in libres[:8])
    except Exception:
        return ()


# ------------------------------------------------------------------ modèles de secours trouvés en ligne (25/11)
# Les fournisseurs retirent des modèles sans prévenir (Groq : llama-4-maverick, 25/11 → plus aucune IA qui voit). On lit
# donc la liste OFFICIELLE des modèles de chaque fournisseur (avec la clé) : les modèles préférés qui n'existent plus sont
# sautés, et d'autres modèles gratuits du même fournisseur sont ajoutés derrière, en secours.
_EN_LIGNE = {}
LISTES = {"mistral": "https://api.mistral.ai/v1/models", "groq": "https://api.groq.com/openai/v1/models",
          "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/models"}
EXCLUS = ("embed", "tts", "whisper", "audio", "guard", "moderation", "ocr", "image-generation", "live", "native",
          "transcri", "realtime", "-image", "image-preview", "codestral", "devstral", "compound", "prompt-guard", "safeguard", "orpheus", "veo",
          "imagen", "learnlm", "gemma-3n", "robotics", "computer-use", "nano")
SECOURS_MAX = 4


def _liste_en_ligne(fourn):
    """{modèle: infos} publiés par le fournisseur, ou None (inconnu : alors on essaie la liste préférée telle quelle)."""
    if fourn not in _EN_LIGNE:
        _EN_LIGNE[fourn] = None
        cle = os.environ.get(FOURNISSEURS[fourn]["cle"], "")
        if fourn in LISTES and len(cle) >= 16 and not os.environ.get("SIMULATION"):
            try:
                req = urllib.request.Request(LISTES[fourn], headers={"Authorization": f"Bearer {cle}", "User-Agent": ROBOT_UA})
                d = json.loads(urllib.request.urlopen(req, timeout=20).read())
                out = {}
                for m in d.get("data") or []:
                    if m.get("active") is False or m.get("deprecation"):
                        continue
                    out[str(m.get("id", "")).removeprefix("models/")] = m
                _EN_LIGNE[fourn] = out or None
            except Exception:
                pass
    return _EN_LIGNE[fourn]


def _secours_ok(fourn, mid, info, vision):
    bas = mid.lower()
    if any(x in bas for x in EXCLUS):
        return False
    if fourn == "gemini":
        return "gemini" in bas and "flash" in bas and "preview" not in bas and "exp" not in bas
    if fourn == "mistral":
        cap = info.get("capabilities") or {}
        return bool(cap.get("completion_chat", True)) and (not vision or bool(cap.get("vision")))
    if fourn == "groq":
        if vision:
            return "llama-4" in bas or "vision" in bas or "-vl" in bas
        return (info.get("context_window") or 0) >= 8000
    return False


def modeles(fourn, vision=False):
    """Modèles à essayer, dans l'ordre : les préférés encore publiés, puis des modèles de secours du même fournisseur."""
    if fourn == "openrouter":
        return _modeles_openrouter(vision=vision)
    prefs = tuple(VISION.get(fourn, ())) if vision else tuple(FOURNISSEURS[fourn]["modeles"])
    en_ligne = _liste_en_ligne(fourn)
    if not en_ligne:
        return prefs
    garde = [m for m in prefs if m in en_ligne]
    secours = sorted((m for m, i in en_ligne.items() if m not in garde and _secours_ok(fourn, m, i, vision)),
                     key=lambda m: (-(en_ligne[m].get("context_window") or en_ligne[m].get("max_context_length") or 0), m))
    return tuple(garde + secours[:SECOURS_MAX])


def _objet(x):
    """Une IA répond parfois par une LISTE au lieu de l'objet demandé ({"images": [...]}) : le robot plantait
    (« 'list' object has no attribute 'get' », 25/11). La liste est rangée sous toutes les clés habituelles."""
    if isinstance(x, list):
        return {k: x for k in ("images", "problemes", "sujets", "garder", "phrases", "liste")}
    return x if isinstance(x, dict) else {}


def lire_json(texte):
    """Objet JSON trouvé dans une réponse (même entourée de ```json … ``` ou de phrases)."""
    t = re.sub(r"^```(?:json)?|```$", "", str(texte).strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except ValueError:
        pass
    debut = t.find("{")
    while debut >= 0:
        niveau = 0
        for i in range(debut, len(t)):
            niveau += {"{": 1, "}": -1}.get(t[i], 0)
            if niveau == 0:
                try:
                    return json.loads(t[debut:i + 1])
                except ValueError:
                    break
        debut = t.find("{", debut + 1)
    raise ValueError("pas de JSON dans la réponse")


def _appel(fourn, modele, messages, temperature, max_tokens):
    F = FOURNISSEURS[fourn]
    corps = {"model": modele, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    if fourn in ("mistral", "groq", "gemini"):
        corps["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(F["url"], data=json.dumps(corps).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {os.environ[F['cle']]}", "Content-Type": "application/json",
                                          "User-Agent": ROBOT_UA, "X-Title": "buzz-insolite-robot"})
    st = QUOTAS.setdefault(fourn, {"appels": 0, "refus": 0, "erreurs": 0})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            _noter_restant(st, r.headers)
            d = json.loads(r.read())
        st["appels"] += 1
    except urllib.error.HTTPError as e:
        _noter_restant(st, e.headers or {})
        st["refus" if e.code == 429 else "erreurs"] += 1
        raise
    return ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""


# Quotas des IA gratuites pendant ce passage du robot (amélioration 18 du 25/11) : appels réussis, refus « trop de
# demandes » (429), autres erreurs, et ce qu'il reste quand le fournisseur le dit (en-têtes x-ratelimit-…). Rangé dans la
# fiche de chaque vidéo (« ia_quotas ») et résumé dans l'onglet Santé.
QUOTAS = {}


def _noter_restant(st, entetes):
    try:
        for cle, nom in (("x-ratelimit-remaining-requests", "restant_demandes"), ("x-ratelimit-limit-requests", "limite_demandes"),
                         ("x-ratelimit-remaining-tokens", "restant_mots"), ("x-ratelimit-remaining-requests-day", "restant_jour"),
                         ("x-ratelimit-remaining-req-minute", "restant_minute")):
            val = entetes.get(cle)
            if val not in (None, ""):
                st[nom] = val
    except Exception:
        pass


def demander_json(consigne, texte, temperature=0.7, max_tokens=4000, exclure=(), journal=print):
    """Pose la question à la première IA gratuite qui répond. Renvoie (objet JSON, « fournisseur:modèle »)."""
    messages = [{"role": "system", "content": consigne}, {"role": "user", "content": texte}]
    derniere = "aucune clé d'IA gratuite (secrets MISTRAL_API_KEY, GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY)"
    for fourn in [f for f in disponibles() if f not in exclure]:
        for modele in [m for m in modeles(fourn) if (fourn, m) not in _MORTS]:
            for essai in range(3):
                try:
                    rep = _appel(fourn, modele, messages, temperature, max_tokens)
                    UTILISES[fourn] = UTILISES.get(fourn, 0) + 1
                    return _objet(lire_json(rep)), f"{fourn}:{modele}"
                except urllib.error.HTTPError as e:
                    corps = e.read()[:400].decode("utf-8", "ignore"); bas = corps.lower()
                    derniere = f"{fourn} {modele} {e.code} : {corps[:200]}"
                    _mort(fourn, modele, e.code, corps)
                    if e.code == 429 and not any(m in bas for m in ("quota", "per day", "exhausted", "(tpd)", "(rpd)")) and essai < 2:
                        time.sleep(10 * (essai + 1)); continue               # trop de demandes à la minute : on patiente
                    if e.code in (500, 502, 503, 504) and essai < 2:
                        time.sleep(5 * (essai + 1)); continue                # serveur saturé un instant
                    break                                                    # quota du jour, modèle retiré… : modèle suivant
                except ValueError as e:                                      # réponse sans JSON : un 2e essai, puis modèle suivant
                    derniere = f"{fourn} {modele} : {e}"
                    if essai < 1: continue
                    break
                except (urllib.error.URLError, TimeoutError, OSError) as e:
                    derniere = f"{fourn} {modele} injoignable : {e}"
                    break
        journal(f"  IA {fourn} indisponible ({derniere[:160]}) : IA suivante")
    raise AucuneIA(derniere)


# ------------------------------------------------------------------ IA qui voit les images (contrôle qualité)
VISION = {"gemini": ("gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-2.5-flash-lite"),
          "mistral": ("mistral-small-latest", "mistral-medium-latest", "pixtral-12b-latest", "ministral-14b-2512"),
          "groq": ("meta-llama/llama-4-scout-17b-16e-instruct",)}      # maverick retiré par Groq le 25/11


def _image_b64(chemin):
    import base64
    with open(chemin, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()


def regarder_json(consigne, texte, images, journal=print, exclure=()):
    """Montre des images (5 au plus, fichiers .jpg) à une IA gratuite qui voit, et renvoie (objet JSON, « fournisseur:modèle »)."""
    contenu = [{"type": "text", "text": texte}] + [{"type": "image_url", "image_url": {"url": _image_b64(c)}} for c in images[:5]]
    messages = [{"role": "system", "content": consigne}, {"role": "user", "content": contenu}]
    derniere = "aucune IA qui voit les images (GEMINI_API_KEY, MISTRAL_API_KEY, GROQ_API_KEY)"
    for fourn in [f for f in ("gemini", "mistral", "groq", "openrouter") if os.environ.get(FOURNISSEURS[f]["cle"])
                  and f not in exclure and f not in _SAUTES]:
        for modele in [m for m in modeles(fourn, vision=True) if (fourn, m) not in _MORTS]:
            for essai in range(2):
                try:
                    rep = _appel(fourn, modele, messages, 0.1, 2500)
                    UTILISES[fourn] = UTILISES.get(fourn, 0) + 1
                    return _objet(lire_json(rep)), f"{fourn}:{modele}"
                except urllib.error.HTTPError as e:
                    corps = e.read()[:300].decode("utf-8", "ignore"); derniere = f"{fourn} {modele} {e.code} : {corps[:160]}"
                    _mort(fourn, modele, e.code, corps)
                    if e.code in (429, 500, 502, 503, 504) and essai == 0 and "per day" not in corps.lower():
                        time.sleep(15); continue
                    break
                except (ValueError, urllib.error.URLError, TimeoutError, OSError) as e:
                    derniere = f"{fourn} {modele} : {str(e)[:120]}"
                    break
    journal(f"    ⚠️ aucune IA qui voit n'a répondu (dernière erreur : {derniere[:200]})")
    raise AucuneIA(derniere)
