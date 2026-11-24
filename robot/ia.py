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
                    modeles=("mistral-small-latest", "ministral-14b-2512", "ministral-8b-latest")),
    "groq": dict(cle="GROQ_API_KEY", url="https://api.groq.com/openai/v1/chat/completions",
                 modeles=("llama-3.3-70b-versatile", "openai/gpt-oss-120b", "openai/gpt-oss-20b")),
    "gemini": dict(cle="GEMINI_API_KEY", url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                   modeles=("gemini-flash-latest", "gemini-flash-lite-latest", "gemini-2.5-flash")),
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


class AucuneIA(Exception):
    pass


def disponibles():
    return [f for f in ORDRE if os.environ.get(FOURNISSEURS[f]["cle"]) and f not in _SAUTES]


def _modeles_openrouter():
    """Modèles gratuits du moment (ils changent souvent) : les plus grands d'abord."""
    try:
        req = urllib.request.Request("https://openrouter.ai/api/v1/models", headers={"User-Agent": ROBOT_UA})
        d = json.loads(urllib.request.urlopen(req, timeout=20).read())
        libres = [m for m in d.get("data", []) if str(m.get("id", "")).endswith(":free")]
        libres.sort(key=lambda m: -(m.get("context_length") or 0))
        return tuple(m["id"] for m in libres[:6])
    except Exception:
        return ()


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
    d = json.loads(urllib.request.urlopen(req, timeout=180).read())
    return ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""


def demander_json(consigne, texte, temperature=0.7, max_tokens=4000, exclure=(), journal=print):
    """Pose la question à la première IA gratuite qui répond. Renvoie (objet JSON, « fournisseur:modèle »)."""
    messages = [{"role": "system", "content": consigne}, {"role": "user", "content": texte}]
    derniere = "aucune clé d'IA gratuite (secrets MISTRAL_API_KEY, GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY)"
    for fourn in [f for f in disponibles() if f not in exclure]:
        modeles = _modeles_openrouter() if fourn == "openrouter" else FOURNISSEURS[fourn]["modeles"]
        for modele in [m for m in modeles if (fourn, m) not in _MORTS]:
            for essai in range(3):
                try:
                    rep = _appel(fourn, modele, messages, temperature, max_tokens)
                    UTILISES[fourn] = UTILISES.get(fourn, 0) + 1
                    return lire_json(rep), f"{fourn}:{modele}"
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
VISION = {"gemini": ("gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest"),
          "mistral": ("mistral-small-latest", "ministral-14b-2512"),
          "groq": ("meta-llama/llama-4-scout-17b-16e-instruct", "meta-llama/llama-4-maverick-17b-128e-instruct")}


def _image_b64(chemin):
    import base64
    with open(chemin, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()


def regarder_json(consigne, texte, images, journal=print, exclure=()):
    """Montre des images (5 au plus, fichiers .jpg) à une IA gratuite qui voit, et renvoie (objet JSON, « fournisseur:modèle »)."""
    contenu = [{"type": "text", "text": texte}] + [{"type": "image_url", "image_url": {"url": _image_b64(c)}} for c in images[:5]]
    messages = [{"role": "system", "content": consigne}, {"role": "user", "content": contenu}]
    derniere = "aucune IA qui voit les images (GEMINI_API_KEY, MISTRAL_API_KEY, GROQ_API_KEY)"
    for fourn in [f for f in ("gemini", "mistral", "groq") if os.environ.get(FOURNISSEURS[f]["cle"]) and f not in exclure
                  and f not in _SAUTES]:
        for modele in [m for m in VISION[fourn] if (fourn, m) not in _MORTS]:
            for essai in range(2):
                try:
                    rep = _appel(fourn, modele, messages, 0.1, 2500)
                    UTILISES[fourn] = UTILISES.get(fourn, 0) + 1
                    return lire_json(rep), f"{fourn}:{modele}"
                except urllib.error.HTTPError as e:
                    corps = e.read()[:300].decode("utf-8", "ignore"); derniere = f"{fourn} {modele} {e.code} : {corps[:160]}"
                    _mort(fourn, modele, e.code, corps)
                    if e.code in (429, 500, 502, 503, 504) and essai == 0 and "per day" not in corps.lower():
                        time.sleep(15); continue
                    break
                except (ValueError, urllib.error.URLError, TimeoutError, OSError) as e:
                    derniere = f"{fourn} {modele} : {str(e)[:120]}"
                    break
    raise AucuneIA(derniere)
