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
    "Ring Road": "rinng rôde",                     # (périphérique du Caire, vidéo de Gizeh du 27/11 : mal dit 2 fois)
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


ANGLAIS = re.compile(r"oa|ee|oo|th|sh|ck|igh|ough|w|(?<=[^aeiouy])y$|ing$|ight", re.I)


def _anglais(t):
    """Mots à l'allure ANGLAISE absents du dictionnaire français (« Road », « Highway », « Smith ») : écrits comme un
    Français les dit AVANT la 1re prise (Wiktionnaire, sinon eSpeak anglais). Les mots français et les noms déjà connus
    du dictionnaire de prononciation ne sont jamais touchés."""
    from . import phonetique
    def un(m):
        w = m.group(0)
        if len(w) < 3 or w.isupper() or phonetique.mot_courant(w) or not ANGLAIS.search(w):
            return w
        if phonetique.api_fr(w):
            return w                                    # nom connu du Wiktionnaire (Washington…) : la voix le connaît aussi
        api = ipa(w)
        return ipa_vers_francais(api) if api else w
    # un NOM ANGLAIS de plusieurs mots (« Ring Road », « Main Street ») se dit en entier à l'anglaise, même le mot qui
    # existe aussi en français (« ring ») — sinon « ringue rôde »
    def groupe(m):
        mots = m.group(0).split()
        if not any(len(w) >= 3 and ANGLAIS.search(w) and not phonetique.mot_courant(w) and not phonetique.api_fr(w) for w in mots):
            return m.group(0)
        out = []
        for w in mots:
            api = None if phonetique.api_fr(w) else ipa(w)
            out.append(ipa_vers_francais(api) if api else w)
        return " ".join(out)
    t = re.sub(r"(?<![\wÀ-ÿ'])[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+(?![\wÀ-ÿ'])", groupe, t)
    return re.sub(r"(?<![\wÀ-ÿ'])[A-Z][a-z]+(?![\wÀ-ÿ'])", un, t)


def pour_voix(texte, dico=None):
    """Texte tel qu'il doit être DIT (sous-titres inchangés) : mise en forme, dictionnaire, sigles, noms anglais."""
    dico = charger() if dico is None else dico
    t = mise_en_forme(texte or "")
    # « 1,5 million » → « un million et demi » ; « 2-1 », « 20-30 » → « deux à un », « vingt à trente »
    t = re.sub(r"\b(\d+),5\s+(million|milliard)s?\b", lambda m: f"{m.group(1)} {m.group(2)}{'s' if m.group(1) != '1' else ''} et demi", t)
    t = re.sub(r"(?<![\d,.])(\d+)\s?-\s?(\d+)(?![\d,.])", r"\1 à \2", t)
    for mot, dire in sorted(dico.items(), key=lambda x: -len(x[0])):     # expressions longues d'abord
        t = re.sub(rf"(?<![\wÀ-ÿ]){re.escape(mot)}(?![\wÀ-ÿ])", dire, t,
                   flags=0 if mot.isupper() else re.I)
    def sigle(m):
        s = m.group(0)
        if re.fullmatch(r"[IVXLCDM]+", s):                    # chiffres romains (Louis XIV) : laissés tels quels
            return s
        return s.lower() if s in COMME_UN_MOT else epeler(s)
    t = re.sub(r"\b[A-Z]{2,6}\b", sigle, t)
    t = _anglais(t)
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
           ("ɡ", "g"), ("ˈ", ""), ("ˌ", ""), ("ː", ""),
           # autres langues (arabe, espagnol, allemand, russe…) : sons rapprochés de ce qu'un Français dirait
           ("x", "kh"), ("χ", "kh"), ("ɣ", "gh"), ("ħ", "h"), ("ʕ", ""), ("ʔ", ""), ("ç", "ch"), ("ʎ", "ly"), ("ɲ", "gn"),
           ("ʁ", "r"), ("β", "b"), ("ʝ", "y"), ("ø", "eu"), ("œ", "eu"), ("y", "u"), ("ɨ", "i"), ("ɯ", "ou"), ("ɕ", "ch"),
           ("ʂ", "ch"), ("ʐ", "j"), ("ts", "ts"), ("ʰ", ""), ("ʲ", ""), ("̃", "n")]


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


# ------------------------------------------------------------------ noms étrangers de TOUTES les langues, avant la 1re prise
# (27/11, l'auteur : « Ring Road a une mauvaise phonétique… la bonne prononciation pour toutes les langues principales ») :
# l'IA dit pour chaque nom sa langue et comment un journaliste français le prononce ; eSpeak-NG (100+ langues) en secours.
CONSIGNE_ETRANGERS = """Une voix de synthèse FRANÇAISE va lire ce texte d'actualité. Repère chaque nom propre ou mot qui n'est pas
français (lieux, personnes, organisations, expressions anglaises, arabes, espagnoles, chinoises…). Pour chacun, donne sa langue
(code ISO : en, ar, es, de, it, pt, ru, zh, ja, tr, nl, pl, uk, hi…) et comment un journaliste FRANÇAIS le prononce à la radio,
écrit en lettres françaises qu'une voix française lira juste (ex. « Ring Road » → « Rinng Rôde », « Mostafa Madbouly » →
« Moustafa Madbouli », « Shenzhen » → « Chènn-djeun », « Würzburg » → « Vurtz-bourg »). Garde les mots tels quels quand un
Français les lit déjà correctement (Paris, Washington, Trump, Madrid). Réponds uniquement en JSON :
{"mots": [{"mot": "Ring Road", "langue": "en", "dire": "Rinng Rôde"}]}"""

ESPEAK_LANGUES = {"en": "en-us", "ar": "ar", "es": "es", "de": "de", "it": "it", "pt": "pt", "ru": "ru", "zh": "cmn", "ja": "ja",
                  "tr": "tr", "nl": "nl", "pl": "pl", "uk": "uk", "hi": "hi", "fa": "fa", "he": "he", "ko": "ko", "el": "el",
                  "sv": "sv", "da": "da", "no": "nb", "fi": "fi", "cs": "cs", "hu": "hu", "ro": "ro", "id": "id", "vi": "vi"}


def noms_etrangers(texte):
    """Groupes de mots à majuscule (« Ring Road », « Mostafa Madbouly ») ou mots isolés absents du dictionnaire français."""
    from . import phonetique
    out = []
    for m in re.finditer(r"(?<![\wÀ-ÿ])([A-ZÀ-Ý][\wÀ-ÿ'-]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ'-]+)*)", texte or ""):
        groupe = m.group(1)
        mots = groupe.split()
        debut = m.start() == 0 or re.search(r"[.!?]\s*$", texte[:m.start()])
        if len(mots) == 1 and (debut or groupe.isupper() or phonetique.mot_courant(groupe)):
            continue
        if all(phonetique.mot_courant(w) for w in mots):
            continue
        if groupe not in out:
            out.append(groupe)
    return out


def preparer_etrangers(textes, journal=print):
    """À appeler AVANT la voix : les noms étrangers de la vidéo reçoivent leur prononciation française (APPRIS)."""
    dico = charger()
    noms = []
    for t in textes:
        noms += [n for n in noms_etrangers(t) if n not in dico and n not in noms]
    if not noms:
        return {}
    trouves = {}
    try:
        from . import ia
        d, qui = ia.demander_json(CONSIGNE_ETRANGERS, "TEXTE :\n" + "\n".join(textes) + "\n\nNOMS À VÉRIFIER : " + ", ".join(noms),
                                  temperature=0.1, max_tokens=1500, journal=lambda *a: None)
        for x in d.get("mots") or []:
            mot, dire = str(x.get("mot") or "").strip(), str(x.get("dire") or "").strip()
            if mot and dire and dire.lower() != mot.lower() and re.fullmatch(r"[\wÀ-ÿ' -]+", dire) and len(dire) < 3 * len(mot) + 10:
                trouves[mot] = dire
    except Exception as e:
        journal(f"  prononciation des noms étrangers : IA indisponible ({str(e)[:60]}), eSpeak seul")
    for n in noms:                                      # secours : eSpeak-NG dans la langue la plus probable (anglais)
        if n not in trouves and ANGLAIS.search(n):
            api = ipa(n)
            if api:
                trouves[n] = ipa_vers_francais(api)
    APPRIS.update(trouves)
    if trouves:
        journal("  🌍 noms étrangers prononcés à la française : " + ", ".join(f"{m} → {d}" for m, d in trouves.items()))
    return trouves


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
