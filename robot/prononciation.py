"""Prononciation des voix homme (Chatterbox) et femme (Kokoro) — demande de l'auteur du 25/11 (points 1, 2, 3, 4, 6).

Le texte DIT est adapté juste avant la voix (les sous-titres, eux, restent bien écrits) :
4. mise en forme pour la voix : abréviations (M., Mme, n°, 1er, 2e…), symboles (%, €, $, km/h, °C, &…), heures (18h30),
   sigles épelés à la française (« ICE » → « i cé eu ») sauf ceux qui se lisent comme un mot (NASA, OTAN, FIFA…) ;
1. dictionnaire de prononciation (`docs/donnees/prononciation.json` + `BASE`) : « mot écrit → comment le dire » ;
3. l'auteur ajoute ou retire un mot depuis le site (Réglages → 🗣️ Prononciation ; ordre `prononciation`), et ses mots
   passent toujours avant ceux du robot ;
2. le dictionnaire APPREND tout seul : quand Whisper, à la réécoute, ne retrouve pas un mot, `respeller` propose une écriture
   phonétique (6. eSpeak-NG donne la prononciation de référence, l'IA en fait une écriture française), la phrase est refaite,
   et l'écriture est gardée pour toutes les vidéos suivantes si la phrase est alors bien comprise ;
6. eSpeak-NG : déjà installé avec la voix Kokoro (espeakng-loader + phonemizer), aucune installation en plus.
"""
import re

from . import nombres

FICHIER = "prononciation.json"

# Mots dont la prononciation est sûre (le reste vient de l'auteur et de l'apprentissage du robot)
BASE = {
    "Mme": "madame", "Mlle": "mademoiselle", "Dr": "docteur", "Pr": "professeur",
}
# Sigles qui se lisent comme un mot (les autres sont épelés)
COMME_UN_MOT = {"NASA", "OTAN", "ONU", "UNESCO", "UNICEF", "FIFA", "UEFA", "CAF", "OPEP", "SIDA", "COVID", "OVNI", "NATO",
                "CNIL", "INSEE", "ONG", "SAMU", "SMIC", "CAC", "DAECH", "ISIS", "LGBT", "UNEF", "IFOP", "INSERM", "CNRS"}
LETTRES = {"A": "a", "B": "bé", "C": "cé", "D": "dé", "E": "eu", "F": "èf", "G": "gé", "H": "ache", "I": "i", "J": "ji",
           "K": "ka", "L": "èl", "M": "èm", "N": "èn", "O": "o", "P": "pé", "Q": "ku", "R": "èr", "S": "èss", "T": "té",
           "U": "u", "V": "vé", "W": "double vé", "X": "iks", "Y": "i grec", "Z": "zèd"}

APPRIS = {}                 # mots appris pendant cette vidéo (gardés dans le fichier s'ils ont marché)
_DICO = {"charge": None}


def charger():
    """Dictionnaire complet : BASE, puis mots appris par le robot, puis mots de l'auteur (prioritaires)."""
    if _DICO["charge"] is None:
        d = dict(BASE)
        try:
            from .commun import lire
            f = lire(FICHIER) or {}
            for source in ("robot", "auteur"):
                d.update({m: x["dire"] for m, x in (f.get("mots") or {}).items() if x.get("source") == source and x.get("dire")})
        except Exception:
            pass
        _DICO["charge"] = d
    return {**_DICO["charge"], **APPRIS}


def oublier_cache():
    _DICO["charge"] = None


def _ordinal(n):
    if n == 1:
        return "premier"
    mot = nombres.en_lettres(n)
    mot = re.sub(r"cinq$", "cinqu", mot)
    mot = re.sub(r"neuf$", "neuv", mot)
    mot = re.sub(r"e$", "", mot)
    return mot + "ième"


def epeler(sigle):
    return " ".join(LETTRES.get(c, c) for c in sigle)


def mise_en_forme(t):
    """Point 4 : abréviations, symboles, heures, ordinaux (avant que les nombres soient écrits en lettres)."""
    t = re.sub(r"\bM\.\s+(?=[A-ZÀ-Ý])", "monsieur ", t)
    t = re.sub(r"\bMM\.\s+", "messieurs ", t)
    t = re.sub(r"\bn°\s*", "numéro ", t, flags=re.I)
    t = re.sub(r"\b1(?:er|re|ère)\b", lambda m: "premier" if m.group(0).endswith("er") else "première", t)
    t = re.sub(r"\b(\d+)(?:e|ème)\b", lambda m: _ordinal(int(m.group(1))), t)
    t = re.sub(r"\b(\d{1,2})\s*h\s*(\d{2})\b", r"\1 heures \2", t)
    t = re.sub(r"\b(\d{1,2})\s*h\b", r"\1 heures", t)
    t = re.sub(r"\$\s*(\d[\d\s.,]*)", r"\1 dollars", t)
    remplacements = [(r"\s*%", " pour cent"), (r"\s*€", " euros"), (r"\bkm/h\b", "kilomètres-heure"), (r"\bm²", "mètres carrés"),
                     (r"\s*°C\b", " degrés"), (r"\s*°", " degrés"), (r"\s&\s", " et "), (r"\bvs\.?\s", "contre "),
                     (r"\betc\.", "et cetera"), (r"\bkm\b", "kilomètres"), (r"\bkg\b", "kilos"), (r"\bcm\b", "centimètres"),
                     (r"(?<=\d)\s?m\b", " mètres"), (r"\s\+\s", " plus ")]
    for motif, rep in remplacements:
        t = re.sub(motif, rep, t)
    return t


def pour_voix(texte, dico=None):
    """Texte tel qu'il doit être DIT (sous-titres inchangés) : mise en forme, dictionnaire, sigles."""
    dico = charger() if dico is None else dico
    t = mise_en_forme(texte or "")
    for mot, dire in sorted(dico.items(), key=lambda x: -len(x[0])):     # expressions longues d'abord
        t = re.sub(rf"(?<![\wÀ-ÿ]){re.escape(mot)}(?![\wÀ-ÿ])", dire, t,
                   flags=0 if mot.isupper() else re.I)
    def sigle(m):
        s = m.group(0)
        if re.fullmatch(r"[IVXLCDM]+", s):                    # chiffres romains (Louis XIV) : laissés tels quels
            return s
        return s.lower() if s in COMME_UN_MOT else epeler(s)
    t = re.sub(r"\b[A-Z]{2,6}\b", sigle, t)
    return nombres.dire_les_nombres(t)


# ------------------------------------------------------------------ 6. eSpeak-NG et 2. apprentissage
def ipa(mot, langue="en-us"):
    """Prononciation de référence d'eSpeak-NG (alphabet phonétique), « » si indisponible."""
    try:
        import os
        import espeakng_loader
        os.environ.setdefault("ESPEAK_DATA_PATH", espeakng_loader.get_data_path())
        from phonemizer.backend.espeak.wrapper import EspeakWrapper
        EspeakWrapper.set_library(espeakng_loader.get_library_path())
        EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
        from phonemizer import phonemize
        return phonemize([mot], language=langue, backend="espeak", njobs=1)[0].strip()
    except Exception:
        return ""


_IPA_FR = [("tʃ", "tch"), ("dʒ", "dj"), ("eɪ", "é"), ("aɪ", "aï"), ("aʊ", "aou"), ("ɔɪ", "oï"), ("oʊ", "o"), ("ɪə", "ieu"),
           ("ɜː", "eu"), ("iː", "i"), ("uː", "ou"), ("ɑː", "a"), ("ɔː", "o"), ("ʃ", "ch"), ("ʒ", "j"), ("θ", "ss"), ("ð", "z"),
           ("ŋ", "ng"), ("ɹ", "r"), ("ɾ", "t"), ("j", "y"), ("w", "ou"), ("ɪ", "i"), ("ɛ", "è"), ("æ", "a"), ("ɑ", "a"),
           ("ɒ", "o"), ("ɔ", "o"), ("ʊ", "ou"), ("ʌ", "eu"), ("ə", "eu"), ("ɐ", "a"), ("e", "é"), ("u", "ou"), ("h", ""),
           ("ɡ", "g"), ("ˈ", ""), ("ˌ", ""), ("ː", "")]


def ipa_vers_francais(phon):
    """Écriture française approximative d'une prononciation eSpeak (secours quand l'IA ne répond pas)."""
    sons = sorted(_IPA_FR, key=lambda x: -len(x[0]))       # chaque son lu UNE fois (jamais reconverti), le plus long d'abord
    out, i = [], 0
    while i < len(phon):
        for a, b in sons:
            if phon.startswith(a, i):
                out.append(b); i += len(a); break
        else:
            out.append(phon[i]); i += 1
    t = "".join(out)
    t = re.sub(r"g(?=[eéèiy])", "gu", t)
    t = re.sub(r"(?<=[aeiouéèy])s(?=[aeiouéèy])", "ss", t)
    return t


CONSIGNE = """Une voix de synthèse FRANÇAISE prononce mal ce mot dans une vidéo. Donne une écriture phonétique en lettres
françaises, qu'une voix française lira correctement (ex. « Ferguson » → « Feurgueusonne », « Newsom » → « Niouzeum »,
« Gueye » → « Guèye »). On te donne la prononciation de référence en alphabet phonétique quand elle existe.
Réponds uniquement en JSON : {"dire": "écriture phonétique"}"""


def respeller(mot, phrase="", journal=print):
    """Écriture phonétique d'un mot mal prononcé : l'IA, aidée par la prononciation FRANÇAISE du Wiktionnaire (WikiPron,
    27/11) ou, à défaut, par eSpeak-NG ; sans IA, la conversion de cette prononciation."""
    from . import phonetique
    ref_fr = phonetique.api_fr(mot)                    # comment un Français le dit (noms étrangers compris)
    ref = ref_fr or (ipa(mot) if not re.search(r"[éèêàùç]", mot) else ipa(mot, "fr-fr"))
    origine = "française (Wiktionnaire)" if ref_fr else "eSpeak"
    try:
        from . import ia
        d, _ = ia.demander_json(CONSIGNE, f"MOT : {mot}\nPHRASE : {phrase}\nPRONONCIATION DE RÉFÉRENCE {origine} : {ref or 'inconnue'}",
                                temperature=0.2, max_tokens=200, journal=lambda *a: None)
        dire = str(d.get("dire") or "").strip()
        if dire and dire.lower() != mot.lower() and len(dire) < 3 * len(mot) + 10:
            return dire
    except Exception:
        pass
    if ref_fr:
        return phonetique.api_fr_vers_ecrit(ref_fr)
    return ipa_vers_francais(ref) if ref else ""


def mots_rates(texte, entendus):
    """Mots du texte (4 lettres au moins) que Whisper n'a PAS retrouvés : les candidats à mieux prononcer."""
    from .voix import norm
    vus = {norm(m) for m, *_ in entendus or []}
    out = []
    for m in re.findall(r"[A-Za-zÀ-ÿ'-]{4,}", texte or ""):
        if norm(m) not in vus and m not in out:
            out.append(m)
    return out


def apprendre(mot, dire):
    APPRIS[mot] = dire


def enregistrer_appris(valides, journal=print):
    """Les mots appris QUI ONT MARCHÉ sont gardés pour toutes les vidéos suivantes (source « robot »)."""
    if not valides:
        return
    from . import depot
    from .commun import ecrire, iso, lire

    def appliquer():
        f = lire(FICHIER) or {"mots": {}}
        for mot, dire in valides.items():
            if (f["mots"].get(mot) or {}).get("source") != "auteur":     # un mot de l'auteur n'est jamais remplacé
                f["mots"][mot] = {"dire": dire, "source": "robot", "le": iso()}
        ecrire(FICHIER, f)
    depot.enregistrer(appliquer, f"Prononciation : {len(valides)} mot(s) appris")
    journal("  🗣️ prononciation apprise : " + ", ".join(f"{m} → {d}" for m, d in valides.items()))


def candidats(texte, entendus):
    """Mots mal compris qui valent la peine d'être réécrits : noms propres (majuscule, hors début de phrase), sigles, mots
    à l'allure étrangère (w, k, th, sh, ee, oo…). Jamais un mot français courant (l'IA l'abîmerait)."""
    rates = mots_rates(texte, entendus)
    premiers = {m.group(0) for m in re.finditer(r"(?:^|[.!?]\s+)([A-Za-zÀ-ÿ'-]+)", texte or "")}
    from . import phonetique
    out = []
    for m in rates:
        if not m.isupper() and phonetique.mot_courant(m) and not phonetique.api_fr(m[:1].upper() + m[1:]) \
                and not (m[:1].isupper() and m not in premiers):
            continue                                    # mot français ordinaire (Lexique 3.83) : jamais réécrit
        etranger = re.search(r"w|k|th|sh|ee|oo|[^aeiouyéèêàâîôûœ]{4}", m.lower())
        if (m[:1].isupper() and m not in premiers) or m.isupper() or etranger:
            out.append(m)
    return out[:2]
