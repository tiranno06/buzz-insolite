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


def _chatterbox(textes, bruts):
    """Fabrique toutes les phrases d'un coup avec Chatterbox (modèle chargé une seule fois)."""
    import json
    from .commun import RACINE
    travail = bruts[0] + ".travail.json"
    with open(travail, "w", encoding="utf-8") as f:
        json.dump({"reference": os.path.join(RACINE, "sons", "voix", REFERENCES["chatterbox-bernard"]),
                   "phrases": [{"texte": t, "chemin": b} for t, b in zip(textes, bruts)]}, f, ensure_ascii=False)
    py = os.environ.get("CHATTERBOX_PYTHON") or os.path.expanduser("~/venv-chatterbox/bin/python")
    subprocess.run([py, os.path.join(RACINE, "robot", "chatterbox_voix.py"), travail], check=True, timeout=3600)


def ressemblance(texte, entendus):
    """Part des mots du texte retrouvés dans ce que Whisper a entendu (1 = tout est compris)."""
    A = [norm(m) for m in texte.split() if norm(m)]; E = [norm(m) for m, _, _ in entendus if norm(m)]
    return difflib.SequenceMatcher(None, A, E, autojunk=False).ratio() if A else 1.0


def preparer(phrases, nom_voix, vitesse, journal=print, suivi=None):
    """Voix de toutes les phrases : p["son"] doit être donné ; remplit p["duree"] et p["mots"].
    Chatterbox (un peu au hasard d'un essai à l'autre) : une phrase mal comprise par Whisper (< 75 % des mots) est refaite
    une fois. Si Chatterbox est en panne, la voix Kokoro (femme) prend le relais pour toute la vidéo."""
    if nom_voix in CHATTERBOX:
        a_faire = list(range(len(phrases)))
        for essai in range(2):
            bruts = [phrases[i]["son"] + f".cb{essai}.wav" for i in a_faire]
            try:
                _chatterbox([phrases[i]["voix"] for i in a_faire], bruts)
            except Exception as e:
                journal(f"  ⚠️ voix Chatterbox en panne ({str(e)[:120]}) : voix Kokoro à la place")
                return preparer(phrases, "kokoro-ff_siwis", vitesse, journal, suivi)
            refaire = []
            for i, b in zip(a_faire, bruts):
                p = phrases[i]
                p["duree"] = dire(p["voix"], p["son"], nom_voix, vitesse, brut=b)
                p["mots"] = mots_entendus(p["son"])
                # Whisper écrit « 31 » quand la voix dit « trente et un » : on compare aux deux versions du texte
                if max(ressemblance(p["voix"], p["mots"]), ressemblance(p.get("ecrit", p["voix"]), p["mots"])) < 0.75:
                    refaire.append(i)
                if suivi:
                    suivi(len([q for q in phrases if "mots" in q]), len(phrases))
            if not refaire:
                break
            journal(f"  {len(refaire)} phrase(s) mal prononcée(s) : refaite(s)" if essai == 0 else
                    f"  {len(refaire)} phrase(s) encore imparfaite(s) : gardée(s) telles quelles")
            a_faire = refaire
        return nom_voix
    for k, p in enumerate(phrases):
        p["duree"] = dire(p["voix"], p["son"], nom_voix, vitesse)
        p["mots"] = mots_entendus(p["son"])
        if suivi:
            suivi(k + 1, len(phrases))
    return nom_voix


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


def mots_entendus(chemin):
    """[(mot, début, fin)] réellement prononcés dans le fichier."""
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
