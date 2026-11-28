"""Orthographe et grammaire des sous-titres (amélioration 6 du 25/11) : LanguageTool (service public gratuit, sans clé).

Les fautes de frappe évidentes (une seule correction proposée, mot sans majuscule) sont corrigées directement ; les autres
(accords, conjugaisons…) sont corrigées par l'IA, à qui on donne les remarques de LanguageTool (sa 1re suggestion n'est pas
toujours la bonne : « Les joueur » → « Le joueur »). Les noms propres ne sont jamais touchés. Service injoignable = rien
n'est changé (la vidéo se fait quand même).
"""
import json
import re
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


# verbes qui, employés SANS complément (suivis d'un lieu : « sur », « dans »…), sont pronominaux : « le camion renverse sur
# le périphérique » → « le camion SE renverse » (vidéo de Gizeh r4 du 28/11 : LanguageTool ne l'a pas vu)
PRONOMINAUX = r"renvers|retourn|[ée]cras|effondr|embras|enflamm|propag|d[ée]vers|abatt|encastr"
_MOT_AVANT = r"(?:se|s'|s’|me|m'|te|t'|nous|vous|le|la|les|l'|l’|lui|leur|en|y|un|une|des|du|de|d'|d’|au|aux)"


def pronominaux(ecrit):
    """Ajoute « se » / « s' » devant ces verbes quand il manque. Renvoie la phrase (inchangée si rien à faire)."""
    def rep(m):
        avant, verbe = m.group(1), m.group(2)
        if re.fullmatch(_MOT_AVANT, avant.lower().strip()):
            return m.group(0)                                   # déjà pronominal, ou c'est un nom (« une couche sur »)
        se = "s'" if verbe[:1].lower() in "aeéèêiouy" else "se "
        return f"{avant}{se}{verbe}"
    motif = rf"(\b[\w'’-]+\s+)((?:{PRONOMINAUX})(?:e|ent)\b)(?=\s+(?:sur|dans|au|aux|à|en|contre|près|sous|devant|derrière)\b)"
    return re.sub(motif, rep, ecrit, flags=re.I)


def corriger(script, journal=print):
    """Relit les sous-titres de toutes les phrases (une seule demande) et corrige. Renvoie le nombre de phrases corrigées."""
    ph = script["phrases"]
    for p in ph:                                            # verbes pronominaux sans « se » (sans réseau, avant LanguageTool)
        avant = p.get("ecrit") or ""
        apres = pronominaux(avant)
        if apres != avant:
            p["ecrit"] = apres
            if p.get("voix") == avant:
                p["voix"] = apres
            journal(f"  orthographe : « {avant[:50]} » → « {apres[:50]} »")
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
        citations_ = [(m.start(), m.end()) for m in re.finditer(r"«[^»]*»|\"[^\"]*\"", ecrit)]
        for f in sorted(liste, key=lambda f: -f["offset"]):          # de la fin vers le début : les positions restent justes
            a = f["offset"] - debuts[i]; b = a + f["length"]
            mot = ecrit[a:b]
            if any(x <= a < y for x, y in citations_):
                continue                                      # CITATION entre guillemets : jamais touchée (« racli » 25/11)
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
