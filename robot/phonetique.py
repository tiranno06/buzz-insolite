"""Dictionnaires de prononciation FRANÇAISE libres (demande de l'auteur du 27/11 : « toute la phonétique des mots du
dictionnaire français »).

- WikiPron (CUNY-CL, données du Wiktionnaire, CC BY-SA) : ~97 000 mots avec leur prononciation EN FRANÇAIS en alphabet
  phonétique, noms propres étrangers compris (« Washington » → w a ʃ i ŋ t ɔ n, « Seattle » → s j a t œ l).
  https://github.com/CUNY-CL/wikipron (fichier data/scrape/tsv/fra_latn_broad.tsv)
- Lexique 3.83 (lexique.org, New & Pallier, CC BY-SA 4.0) : ~142 000 formes du français courant. Sert à reconnaître un mot
  français ordinaire, qu'on ne « corrige » jamais.
Téléchargés une fois puis gardés en cache (~/.cache/buzz-phonetique, mis en cache par les workflows). Hors ligne ou en
panne : dictionnaires vides, et la prononciation revient à eSpeak-NG + IA comme avant.
"""
import io
import os
import re
import urllib.request
import zipfile

CACHE = os.path.expanduser("~/.cache/buzz-phonetique")
WIKIPRON = "https://raw.githubusercontent.com/CUNY-CL/wikipron/master/data/scrape/tsv/fra_latn_broad.tsv"
LEXIQUE = "http://www.lexique.org/databases/Lexique383/Lexique383.zip"
_PRON, _MOTS = None, None


def _telecharger(url, chemin):
    if os.path.exists(chemin) and os.path.getsize(chemin) > 1000:
        return True
    try:
        os.makedirs(CACHE, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "buzz-insolite"})
        with urllib.request.urlopen(req, timeout=90) as r:
            donnees = r.read()
        if url.endswith(".zip"):                       # on garde : mot, genre des noms (m / f / vide), nature
            with zipfile.ZipFile(io.BytesIO(donnees)) as z:
                nom = next(n for n in z.namelist() if n.endswith("Lexique383.tsv"))
                lignes = z.read(nom).decode("utf-8").splitlines()[1:]
            vus = {}
            for l in lignes:
                c = l.split("\t")
                if len(c) > 7 and c[0]:
                    mot, genre, nature, freq = c[0].lower(), c[4], c[3], float(c[7] or 0) + float(c[6] or 0)
                    if mot not in vus or (nature == "NOM" and (vus[mot][1] != "NOM" or freq > vus[mot][2])):
                        vus[mot] = (genre if nature == "NOM" else "", nature, freq)
            donnees = "\n".join(f"{m}\t{g}\t{n}" for m, (g, n, _) in sorted(vus.items())).encode("utf-8")
        with open(chemin, "wb") as f:
            f.write(donnees)
        return True
    except Exception:
        return False


def charger():
    """(prononciations {mot: [api…]}, mots français courants {mot en minuscules})."""
    global _PRON, _MOTS
    if _PRON is None:
        _PRON, _MOTS = {}, set()
        p = os.path.join(CACHE, "wikipron_fra.tsv")
        if _telecharger(WIKIPRON, p):
            with open(p, encoding="utf-8") as f:
                for ligne in f:
                    mot, _, api = ligne.rstrip("\n").partition("\t")
                    if mot and api:
                        _PRON.setdefault(mot, []).append(api.replace(" ", ""))
        m = os.path.join(CACHE, "lexique383_genres.tsv")
        if _telecharger(LEXIQUE, m):
            with open(m, encoding="utf-8") as f:
                for l in f:
                    c = l.rstrip("\n").split("\t")
                    if c and c[0]:
                        _MOTS.add(c[0]); GENRES[c[0]] = c[1] if len(c) > 1 else ""
    return _PRON, _MOTS


GENRES = {}


def genre(mot):
    """Genre d'un NOM d'après Lexique 3.83 : « m », « f » ou « » (inconnu). « morts » → m, « victimes » → f."""
    charger()
    m = mot.lower()
    return GENRES.get(m) or GENRES.get(m[:-1] if m.endswith(("s", "x")) else m) or ""


def api_fr(mot):
    """Prononciation française de référence (Wiktionnaire), « » si le mot n'y est pas."""
    pron, _ = charger()
    v = pron.get(mot) or pron.get(mot.capitalize()) or pron.get(mot.lower())
    return v[0] if v else ""


def mot_courant(mot):
    """Mot français ordinaire (Lexique) : la voix le lit bien, on ne le réécrit jamais."""
    _, mots = charger()
    return mot.lower() in mots


# alphabet phonétique FRANÇAIS → lettres qu'une voix française lit comme il faut (les plus longs d'abord)
_API_FR = [("ɑ̃", "an"), ("ɛ̃", "in"), ("ɔ̃", "on"), ("œ̃", "un"), ("ʃ", "ch"), ("ʒ", "j"), ("ɲ", "gn"), ("ŋ", "ng"), ("ʁ", "r"),
           ("ɥ", "u"), ("ø", "eu"), ("œ", "eu"), ("ə", "e"), ("ɛ", "è"), ("e", "é"), ("ɔ", "o"), ("o", "o"), ("u", "ou"),
           ("y", "u"), ("j", "y"), ("w", "ou"), ("ɡ", "g"), ("ɑ", "a"), ("‿", ""), ("ˈ", ""), ("ˌ", ""), ("ː", ""), (".", "")]


def api_fr_vers_ecrit(api):
    """« w a ʃ i ŋ t ɔ n » → « ouachingtonne » (lisible par la voix française)."""
    api = api.replace(" ", "")
    sons = sorted(_API_FR, key=lambda x: -len(x[0]))
    out, i = [], 0
    while i < len(api):
        for a, b in sons:
            if api.startswith(a, i):
                out.append(b); i += len(a); break
        else:
            out.append(api[i]); i += 1
    t = "".join(out)
    t = re.sub(r"g(?=[eéèiy])", "gu", t)                       # « g » dur devant e, i
    t = re.sub(r"(?<=[aeiouéèy])s(?=[aeiouéèy])", "ss", t)     # « s » sourd entre deux voyelles
    t = re.sub(r"(?<=[aeiouéèy])c(?=[eéèiy])", "ss", t)
    if api.endswith(("n", "m")) and re.search(r"[aeiouéè][nm]$", t):
        t += t[-1] + "e"                                # « …tɔn » → « …tonne » (sinon la voix dirait un son nasal « on »)
    return t
