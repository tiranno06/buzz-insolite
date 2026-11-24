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


def dire(texte, chemin, nom_voix, vitesse=0.80):
    """Fabrique la phrase dite, sans blanc au début ni à la fin. Renvoie sa durée."""
    brut = chemin + ".brut.wav"
    subprocess.run([sys.executable, "-m", "piper", "-m", modele(nom_voix), "--length-scale", str(vitesse),
                    "--noise-scale", "0.75", "--noise-w", "0.9", "-f", brut], input=texte, text=True, check=True,
                   capture_output=True)
    coupe = "silenceremove=start_periods=1:start_threshold=-45dB"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", brut, "-af", f"{coupe},areverse,{coupe},apad=pad_dur=0.04,areverse",
                    "-ar", "44100", chemin], check=True)
    os.remove(brut)
    return duree(chemin)


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
