"""Orthographe et grammaire des sous-titres (amélioration 6 du 25/11) : LanguageTool (service public gratuit, sans clé).

Les fautes de frappe évidentes (une seule correction proposée, mot sans majuscule) sont corrigées directement ; les autres
(accords, conjugaisons…) sont corrigées par l'IA, à qui on donne les remarques de LanguageTool (sa 1re suggestion n'est pas
toujours la bonne : « Les joueur » → « Le joueur »). Les noms propres ne sont jamais touchés. Service injoignable = rien
n'est changé (la vidéo se fait quand même).
"""
import json
import urllib.parse
import urllib.request

from . import ia, nombres

URL = "https://api.languagetool.org/v2/check"
CATEGORIES = {"TYPOS", "GRAMMAR", "AGREEMENT", "CONFUSED_WORDS", "VERB_CONJUGATION"}

CONSIGNE = """Corrige SEULEMENT les fautes d'orthographe et de grammaire signalées dans cette phrase de sous-titre (accords,
conjugaison, mot mal écrit), sans changer le sens, le style ni les noms propres. Réponds uniquement en JSON :
{"ecrit": "phrase corrigée"}"""


def verifier_texte(texte, langue="fr"):
    data = urllib.parse.urlencode({"text": texte, "language": langue, "level": "default"}).encode()
    req = urllib.request.Request(URL, data=data, headers={"User-Agent": "buzz-insolite-robot"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("matches") or []


def corriger(script, journal=print):
    """Relit les sous-titres de toutes les phrases (une seule demande) et corrige. Renvoie le nombre de phrases corrigées."""
    ph = script["phrases"]
    textes = [p.get("ecrit") or "" for p in ph]
    tout, debuts, pos = "", [], 0
    for t in textes:
        debuts.append(pos); tout += t + "\n"; pos += len(t) + 1
    try:
        fautes = verifier_texte(tout[:19000])
    except Exception as e:
        journal(f"  orthographe : LanguageTool injoignable ({str(e)[:60]}), texte non relu")
        return 0
    par_phrase = {}
    for f in fautes:
        if (f.get("rule", {}).get("category", {}).get("id") or "") not in CATEGORIES:
            continue
        i = max(k for k, d in enumerate(debuts) if d <= f["offset"])
        par_phrase.setdefault(i, []).append(f)
    corrigees = 0
    for i, liste in sorted(par_phrase.items()):
        p, ecrit = ph[i], textes[i]
        reste = []
        for f in sorted(liste, key=lambda f: -f["offset"]):          # de la fin vers le début : les positions restent justes
            a = f["offset"] - debuts[i]; b = a + f["length"]
            mot = ecrit[a:b]
            reps = [r["value"] for r in f.get("replacements") or []]
            if f["rule"]["category"]["id"] == "TYPOS":
                if mot[:1].isupper() or not reps:
                    continue                                          # nom propre (Gueye, Mané…) : jamais touché
                if len(reps) == 1 or reps[0].lower().startswith(mot[:3].lower()):
                    ecrit = ecrit[:a] + reps[0] + ecrit[b:]
                    continue
            reste.append(f"« {mot} » : {f.get('message', '')} (suggestions : {', '.join(reps[:3])})")
        if reste:
            try:
                d, _ = ia.demander_json(CONSIGNE, f"PHRASE : {ecrit}\nREMARQUES :\n" + "\n".join(reste), temperature=0.1,
                                        journal=journal)
                if str(d.get("ecrit") or "").strip():
                    ecrit = str(d["ecrit"]).strip()
            except Exception:
                pass
        if ecrit != textes[i]:
            journal(f"  orthographe, écran {i + 1} : « {textes[i]} » → « {ecrit} »")
            p["ecrit"] = ecrit
            p["voix"] = nombres.dire_les_nombres(ecrit)
            corrigees += 1
    return corrigees
