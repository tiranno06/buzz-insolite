"""Voix de synthèse gratuite (Piper, voix françaises libres) et instant exact de chaque mot (Whisper, gratuit).

Une phrase = un fichier son, débarrassé de ses silences de début et de fin. Whisper réécoute ensuite chaque phrase pour
savoir quand chaque mot est dit : c'est ce qui permet le surlignage jaune « karaoké » des sous-titres.
"""
import difflib
import os
import re
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.request

from .commun import CACHE

VOIX = {"fr_FR-tom-medium": "tom", "fr_FR-siwis-medium": "siwis", "fr_FR-upmc-medium": "upmc", "fr_FR-gilles-low": "gilles"}
# Voix Kokoro (Apache 2.0), bien plus naturelles que Piper (avis de l'auteur, 24/11/2026). Une seule voix française (femme) ;
# les voix d'homme viennent d'autres langues et parlent français : seules celles que Whisper comprend aussi bien que la voix
# française ont été gardées (essai du 24/11 : pm_alex, em_alex, am_fenrir).
KOKORO = {"kokoro-ff_siwis": "femme", "kokoro-pm_alex": "homme (Alex)", "kokoro-em_alex": "homme (Alex 2)",
          "kokoro-am_fenrir": "homme (Fenrir)"}
# Voix choisie par l'auteur le 24/11/2026 : homme français sans accent, Chatterbox Multilingual (MIT) qui imite « Bernard »
# (lecteur LibriVox, domaine public). Tourne dans son propre espace Python (robot/chatterbox_voix.py, CHATTERBOX_PYTHON).
CHATTERBOX = {"chatterbox-bernard": "homme français (Bernard)"}
REFERENCES = {"chatterbox-bernard": "bernard.wav"}
KOKORO_FICHIERS = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
_KOKORO = None


def modele(nom):
    """Chemin du fichier de voix (téléchargé une fois depuis Hugging Face, puis gardé en cache)."""
    nom = nom if nom in VOIX else "fr_FR-tom-medium"
    dossier = os.path.join(CACHE, "voix"); os.makedirs(dossier, exist_ok=True)
    qualite = nom.rsplit("-", 1)[1]
    for ext in (".onnx", ".onnx.json"):
        chemin = os.path.join(dossier, nom + ext)
        if not os.path.exists(chemin):
            url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/{VOIX[nom]}/{qualite}/{nom}{ext}"
            urllib.request.urlretrieve(url, chemin + ".part"); os.replace(chemin + ".part", chemin)
    return os.path.join(dossier, nom + ".onnx")


def duree(f):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]))


def _kokoro():
    global _KOKORO
    if _KOKORO is None:
        from kokoro_onnx import Kokoro
        dossier = os.path.join(CACHE, "kokoro"); os.makedirs(dossier, exist_ok=True)
        for nom in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
            chemin = os.path.join(dossier, nom)
            if not os.path.exists(chemin):
                urllib.request.urlretrieve(KOKORO_FICHIERS + nom, chemin + ".part"); os.replace(chemin + ".part", chemin)
        _KOKORO = Kokoro(os.path.join(dossier, "kokoro-v1.0.onnx"), os.path.join(dossier, "voices-v1.0.bin"))
    return _KOKORO


def _dire_kokoro(texte, brut, vitesse, nom_voix):
    import wave
    import numpy as np
    son, sr = _kokoro().create(texte, voice=nom_voix.split("-", 1)[1], speed=max(0.8, min(1.4, 0.92 / vitesse)), lang="fr-fr")
    with wave.open(brut, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(son, -1, 1) * 32767).astype(np.int16).tobytes())


def dire(texte, chemin, nom_voix, vitesse=0.80, brut=None):
    """Fabrique la phrase dite, sans blanc au début ni à la fin. Renvoie sa durée. `brut` : son déjà fabriqué (Chatterbox)."""
    tempo = ""
    if brut:
        tempo = f",atempo={max(0.8, min(1.4, 0.92 / vitesse)):.3f}"   # Chatterbox parle lentement : même rythme que validé
    else:
        brut = chemin + ".brut.wav"
    if tempo:
        pass                                              # son déjà fabriqué (Chatterbox)
    elif nom_voix in KOKORO:
        _dire_kokoro(texte, brut, vitesse, nom_voix)
    else:
        subprocess.run([sys.executable, "-m", "piper", "-m", modele(nom_voix), "--length-scale", str(vitesse),
                        "--noise-scale", "0.75", "--noise-w", "0.9", "-f", brut], input=texte, text=True, check=True,
                       capture_output=True)
    coupe = "silenceremove=start_periods=1:start_threshold=-45dB"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", brut, "-af", f"{coupe},areverse,{coupe},apad=pad_dur=0.04,areverse{tempo}",
                    "-ar", "44100", chemin], check=True)
    os.remove(brut)
    return duree(chemin)


def emotion(texte, premiere=False):
    """Intensité de la voix Chatterbox (« exaggeration », amélioration 5 du 25/11) : accroche et phrases qui s'exclament ou
    questionnent plus vivantes ; les explications restent posées (0,5 = la voix choisie par l'auteur)."""
    t = texte.strip()
    if premiere:
        return 0.7
    if t.endswith(("!", "?")):
        return 0.62
    return 0.5


def processus_voix(nb_phrases):
    """Nombre de calculs de voix EN MÊME TEMPS (amélioration 10 : tous les cœurs) : un par paire de cœurs, 2 au moins sur une
    machine de 4 cœurs ; jamais plus que de phrases. Réglable par CHATTERBOX_PROCESSUS."""
    n = int(os.environ.get("CHATTERBOX_PROCESSUS") or max(1, (os.cpu_count() or 2) // 2))
    return max(1, min(n, nb_phrases))


def _chatterbox(textes, bruts, emotions=None):
    """Fabrique toutes les phrases avec Chatterbox. Les phrases sont réparties entre plusieurs calculs qui tournent EN MÊME
    TEMPS (chacun charge le modèle une fois et prend sa part des cœurs du processeur)."""
    import json
    from .commun import RACINE
    emotions = emotions or [0.5] * len(textes)
    n = processus_voix(len(textes))
    coeurs = max(1, (os.cpu_count() or 2) // n)
    ordre = sorted(range(len(textes)), key=lambda i: -len(textes[i]))   # longues phrases réparties équitablement
    groupes = [ordre[k::n] for k in range(n)]
    py = os.environ.get("CHATTERBOX_PYTHON") or os.path.expanduser("~/venv-chatterbox/bin/python")
    procs = []
    for k, g in enumerate(groupes):
        travail = bruts[0] + f".travail{k}.json"
        with open(travail, "w", encoding="utf-8") as f:
            json.dump({"reference": os.path.join(RACINE, "sons", "voix", REFERENCES["chatterbox-bernard"]),
                       "phrases": [{"texte": textes[i], "chemin": bruts[i], "emotion": emotions[i]} for i in g]},
                      f, ensure_ascii=False)
        env = dict(os.environ, OMP_NUM_THREADS=str(coeurs), MKL_NUM_THREADS=str(coeurs), CHATTERBOX_COEURS=str(coeurs))
        procs.append(subprocess.Popen([py, os.path.join(RACINE, "robot", "chatterbox_voix.py"), travail], env=env))
    erreurs = []
    for p in procs:
        try:
            if p.wait(timeout=3600) != 0:
                erreurs.append(p.returncode)
        except subprocess.TimeoutExpired:
            p.kill(); erreurs.append("trop long")
    if erreurs:
        raise RuntimeError(f"Chatterbox : {len(erreurs)} calcul(s) en échec ({erreurs})")


def ressemblance(texte, entendus):
    """Part des mots du texte retrouvés dans ce que Whisper a entendu (1 = tout est compris)."""
    A = [norm(m) for m in texte.split() if norm(m)]; E = [norm(m) for m, _, _ in entendus if norm(m)]
    return difflib.SequenceMatcher(None, A, E, autojunk=False).ratio() if A else 1.0


def _cle_voix(texte, nom_voix, vitesse):
    import hashlib
    from .prononciation import pour_voix                   # un mot mieux prononcé = voix refaite (clé différente)
    return hashlib.sha1(f"{nom_voix}|{float(vitesse):.3f}|{pour_voix(texte).strip()}".encode()).hexdigest()[:20]


def depuis_memoire(p, nom_voix, vitesse, memoire):
    """Phrase déjà dite à l'identique ET réussie (même voix, même vitesse) : reprise telle quelle, jamais recalculée."""
    import json
    import shutil
    if not memoire:
        return False
    base = os.path.join(memoire, _cle_voix(p["voix"], nom_voix, vitesse))
    if not (os.path.exists(base + ".wav") and os.path.exists(base + ".json")):
        return False
    with open(base + ".json", encoding="utf-8") as f:
        d = json.load(f)
    shutil.copyfile(base + ".wav", p["son"])
    p["duree"], p["mots"], p["_voix_defaut"] = d["duree"], [tuple(m) for m in d["mots"]], ""
    return True


def oublier(p, nom_voix, vitesse, memoire):
    """Phrase jugée mauvaise par le contrôle final : sa voix en mémoire est effacée (sinon on la reprendrait à l'identique)."""
    if memoire:
        base = os.path.join(memoire, _cle_voix(p["voix"], nom_voix, vitesse))
        for ext in (".wav", ".json"):
            if os.path.exists(base + ext):
                os.remove(base + ext)


def en_memoire(p, nom_voix, vitesse, memoire):
    import json
    import shutil
    if not memoire or p.get("_voix_defaut") or not p.get("mots"):
        return
    os.makedirs(memoire, exist_ok=True)
    base = os.path.join(memoire, _cle_voix(p["voix"], nom_voix, vitesse))
    shutil.copyfile(p["son"], base + ".wav")
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump({"duree": p["duree"], "mots": p["mots"], "texte": p["voix"]}, f, ensure_ascii=False)


def preparer(phrases, nom_voix, vitesse, journal=print, suivi=None, memoire=None):
    """`memoire` : dossier des voix déjà réussies (même texte, même voix) : jamais refaites (demande de l'auteur du 24/11)."""
    gardees = [p for p in phrases if depuis_memoire(p, nom_voix, vitesse, memoire)]
    if gardees:
        journal(f"  {len(gardees)} phrase(s) déjà dite(s) à l'identique : voix reprise sans la refaire")
    reste = [p for p in phrases if p not in gardees]
    if reste:
        nom_voix = _preparer(reste, nom_voix, vitesse, journal, suivi)
        for p in reste:
            en_memoire(p, nom_voix, vitesse, memoire)
    return nom_voix


def _preparer(phrases, nom_voix, vitesse, journal=print, suivi=None):
    """Voix de toutes les phrases : p["son"] doit être donné ; remplit p["duree"] et p["mots"].
    Chatterbox (un peu au hasard d'un essai à l'autre) : une phrase mal comprise par Whisper (< 75 % des mots) est refaite
    une fois. Si Chatterbox est en panne, la voix Kokoro (femme) prend le relais pour toute la vidéo."""
    from . import prononciation as PR
    essayes = {}                                            # mot → écriture phonétique essayée (point 2 : apprentissage)
    if nom_voix in CHATTERBOX:
        a_faire = list(range(len(phrases)))
        for essai in range(2):
            bruts = [phrases[i]["son"] + f".cb{essai}.wav" for i in a_faire]
            try:
                _chatterbox([PR.pour_voix(phrases[i]["voix"]) for i in a_faire], bruts,
                            [emotion(phrases[i]["voix"], phrases[i].get("_premiere", False)) for i in a_faire])
            except Exception as e:
                journal(f"  ⚠️ voix Chatterbox en panne ({str(e)[:120]}) : voix Kokoro à la place")
                return _preparer(phrases, "kokoro-ff_siwis", vitesse, journal, suivi)
            refaire = []
            for i, b in zip(a_faire, bruts):
                p = phrases[i]
                p["duree"] = dire(p["voix"], p["son"], nom_voix, vitesse, brut=b)
                p["mots"] = mots_entendus(p["son"])
                # Whisper écrit « 31 » quand la voix dit « trente et un » : on compare aux deux versions du texte
                compris = max(ressemblance(p["voix"], p["mots"]), ressemblance(p.get("ecrit", p["voix"]), p["mots"]))
                bafouille = p["duree"] > 0.7 * len(p["voix"].split()) + 1.5      # voix qui traîne ou répète
                p["_voix_defaut"] = ("mots mal prononcés" if compris < 0.75 else "voix qui traîne" if bafouille else "")
                if p["_voix_defaut"]:
                    refaire.append(i)
                if suivi:
                    suivi(len([q for q in phrases if "mots" in q]), len(phrases))
            if essai == 1:
                _garder_appris(phrases, essayes, journal)
            if not refaire:
                break
            if essai == 0:
                _essayer_mots(phrases, refaire, essayes, journal)
            journal(f"  {len(refaire)} phrase(s) mal prononcée(s) : refaite(s)" if essai == 0 else
                    f"  {len(refaire)} phrase(s) encore imparfaite(s) : gardée(s) telles quelles")
            a_faire = refaire
        return nom_voix
    a_faire = list(range(len(phrases)))                    # Kokoro (voix de femme) : même apprentissage
    for essai in range(2):
        refaire = []
        for k in a_faire:
            p = phrases[k]
            p["duree"] = dire(PR.pour_voix(p["voix"]), p["son"], nom_voix, vitesse)
            p["mots"] = mots_entendus(p["son"])
            compris = max(ressemblance(p["voix"], p["mots"]), ressemblance(p.get("ecrit", p["voix"]), p["mots"]))
            if compris < 0.75 and PR.candidats(p.get("ecrit") or p["voix"], p["mots"]):
                refaire.append(k)
            if suivi:
                suivi(len([q for q in phrases if "mots" in q]), len(phrases))
        if essai == 1:
            _garder_appris(phrases, essayes, journal)
        if not refaire or essai == 1:
            break
        _essayer_mots(phrases, refaire, essayes, journal)
        if not essayes:
            break
        a_faire = refaire
    return nom_voix


def _essayer_mots(phrases, indices, essayes, journal):
    """Point 2 : mots que Whisper n'a pas retrouvés → écriture phonétique (IA + eSpeak-NG), essayée au prochain passage."""
    from . import prononciation as PR
    dico = PR.charger()
    for i in indices:
        p = phrases[i]
        for mot in PR.candidats(p.get("ecrit") or p["voix"], p.get("mots")):
            if mot in essayes or mot in dico:
                continue
            dire = PR.respeller(mot, p.get("ecrit") or p["voix"], journal)
            if dire:
                PR.apprendre(mot, dire); essayes[mot] = dire
                journal(f"  🗣️ « {mot} » mal compris : essai avec « {dire} »")


def _garder_appris(phrases, essayes, journal):
    """Les écritures essayées qui ont rendu la phrase compréhensible sont gardées pour les vidéos suivantes."""
    from . import prononciation as PR
    valides = {}
    for mot, dire in essayes.items():
        concernees = [p for p in phrases if mot in (p.get("ecrit") or p["voix"]) and p.get("mots") is not None]
        if concernees and all(max(ressemblance(p["voix"], p["mots"]), ressemblance(p.get("ecrit", p["voix"]), p["mots"])) >= 0.75
                              for p in concernees):
            valides[mot] = dire
        else:
            PR.APPRIS.pop(mot, None)
    try:
        PR.enregistrer_appris(valides, journal)
    except Exception as e:
        journal(f"  prononciation non enregistrée ({str(e)[:60]})")


# ------------------------------------------------------------------ instants des mots
_MODELE = None


def _whisper():
    global _MODELE
    if _MODELE is None:
        from faster_whisper import WhisperModel
        _MODELE = WhisperModel("small", device="cpu", compute_type="int8", download_root=os.path.join(CACHE, "whisper"))
    return _MODELE


def norm(m):
    m = "".join(c for c in unicodedata.normalize("NFD", m.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", m)


GROQ_WHISPER = {"refus": 0}


def _groq_mots(chemin):
    """Whisper de Groq (gratuit, clé GROQ_API_KEY déjà utilisée par les IA) : quelques secondes au lieu de plusieurs minutes
    sur le processeur de GitHub. None si indisponible (quota, panne) : Whisper local prend le relais."""
    import json
    import time
    import uuid
    cle = os.environ.get("GROQ_API_KEY")
    if not cle or GROQ_WHISPER["refus"] >= 3:
        return None
    son = subprocess.check_output(["ffmpeg", "-v", "error", "-i", chemin, "-ac", "1", "-ar", "16000", "-f", "flac", "-"])
    borne = uuid.uuid4().hex
    champs = [("model", "whisper-large-v3-turbo"), ("language", "fr"), ("response_format", "verbose_json"),
              ("timestamp_granularities[]", "word"), ("temperature", "0")]
    corps = b"".join(f"--{borne}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k, v in champs)
    corps += (f"--{borne}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"voix.flac\"\r\n"
              "Content-Type: audio/flac\r\n\r\n").encode() + son + f"\r\n--{borne}--\r\n".encode()
    for essai in range(2):
        try:
            req = urllib.request.Request("https://api.groq.com/openai/v1/audio/transcriptions", data=corps, method="POST",
                                         headers={"Authorization": f"Bearer {cle}", "User-Agent": "buzz-insolite-robot",
                                                  "Content-Type": f"multipart/form-data; boundary={borne}"})
            d = json.loads(urllib.request.urlopen(req, timeout=60).read())
            return [(str(w["word"]).strip(), float(w["start"]), float(w["end"])) for w in d.get("words") or []]
        except urllib.error.HTTPError as e:
            if e.code == 429 and essai == 0:
                time.sleep(8); continue
            GROQ_WHISPER["refus"] += 1
            return None
        except Exception:
            GROQ_WHISPER["refus"] += 1
            return None
    return None


def mots_entendus(chemin):
    """[(mot, début, fin)] réellement prononcés dans le fichier : Whisper de Groq d'abord (rapide), sinon Whisper local."""
    mots = _groq_mots(chemin)
    if mots is not None and (mots or os.path.getsize(chemin) < 20000):
        return mots
    import numpy as np
    brut = subprocess.check_output(["ffmpeg", "-v", "error", "-i", chemin, "-f", "f32le", "-ac", "1", "-ar", "16000", "-"])
    segs, _ = _whisper().transcribe(np.frombuffer(brut, np.float32), language="fr", word_timestamps=True, beam_size=5)
    return [(w.word.strip(), w.start, w.end) for s in segs for w in s.words]


def mots_affiches(texte):
    """Mots des sous-titres ; « : », « ? », « ! » restent collés au mot d'avant."""
    out = []
    for m in texte.replace(" m²", " m²").split():
        if out and not norm(m):
            out[-1] += " " + m
        else:
            out.append(m)
    return out


def caler(affiches, entendus, d_phrase):
    """(début, fin) de chaque mot affiché, rapproché des mots entendus (« 378 » affiché = « trois cent… » entendu)."""
    A = [norm(m) for m in affiches]; E = [norm(m) for m, _, _ in entendus]
    t = [None] * len(affiches)
    for op, a0, a1, e0, e1 in difflib.SequenceMatcher(None, A, E, autojunk=False).get_opcodes():
        if op == "equal":
            for k in range(a1 - a0):
                t[a0 + k] = (entendus[e0 + k][1], entendus[e0 + k][2])
        elif op == "replace" or (op == "delete" and entendus):
            d0 = entendus[e0][1] if e0 < len(entendus) else entendus[-1][2]
            d1 = entendus[e1 - 1][2] if e1 > e0 else d0
            n = sum(len(affiches[k]) for k in range(a0, a1)) or 1; x = d0
            for k in range(a0, a1):
                y = x + (d1 - d0) * len(affiches[k]) / n; t[k] = (x, y); x = y
    for k in range(len(t)):                              # mots restés sans heure : entre leurs voisins
        if t[k] is None:
            av = t[k - 1][1] if k and t[k - 1] else 0.0
            ap = next((t[j][0] for j in range(k + 1, len(t)) if t[j]), d_phrase)
            t[k] = (av, max(av, ap))
    return t
