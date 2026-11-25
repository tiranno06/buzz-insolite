"""Bande son : la voix devant, une musique libre très discrète derrière, et des bruitages.

- « woosh » à chaque changement d'écran (sauf le premier), très court et bas ;
- « ding » quand un écran affiche un chiffre fort (« 378 JOURS », « 22 MIN ») ;
- « dun dun dun » au moment de la réponse d'un « Vrai ou faux ? ».
Musique : boucles de sons/musique (« neutre », « tension », « joie » choisie par l'IA d'après le sujet), à -26 dB environ,
qui baisse encore pendant la voix (compression « sidechain ») et s'efface à la fin. Licences : sons/LICENCES.md.
"""
import glob
import os
import random
import re
import subprocess

from .commun import RACINE

SONS = os.path.join(RACINE, "sons")
HUMEURS = ("neutre", "tension", "joie", "epique", "emotion")
# rythme voulu pour chaque ambiance (battements par minute) : la musique est choisie d'abord dans cette plage
TEMPOS = {"joie": (110, 150), "tension": (70, 110), "epique": (90, 140), "emotion": (55, 95), "neutre": (85, 125)}


def musique(humeur):
    """Musique de l'ambiance demandée (amélioration 9 du 25/11 : ambiance ET rythme, catalogue sons/musique/catalogue.json
    rempli par robot/musiques.py) ; sans catalogue : les boucles d'origine, comme avant."""
    humeur = humeur if humeur in HUMEURS else "neutre"
    dossier = os.path.join(SONS, "musique")
    try:
        import json
        cat = [m for m in json.load(open(os.path.join(dossier, "catalogue.json"), encoding="utf-8"))
               if os.path.exists(os.path.join(dossier, m["fichier"]))]
    except Exception:
        cat = []
    if cat:
        lo, hi = TEMPOS[humeur]
        meme = [m for m in cat if m["humeur"] == humeur]
        bons = [m for m in meme if lo <= (m.get("tempo") or 0) <= hi] or meme or [m for m in cat if m["humeur"] == "neutre"]
        if bons:
            return os.path.join(dossier, random.choice(bons)["fichier"])
    choix = sorted(glob.glob(os.path.join(dossier, f"{humeur}_*.mp3"))) or sorted(glob.glob(os.path.join(dossier, "neutre_*.mp3")))
    return random.choice(choix) if choix else None


_BATTEMENTS = {}


def battements(fichier):
    """Instants des temps forts de la musique (et des demi-temps) : tempo trouvé par autocorrélation de l'énergie (musique à
    tempo régulier). Sert à couper les écrans PILE sur le rythme (demande de l'auteur du 24/11). [] si illisible."""
    if fichier in _BATTEMENTS:
        return _BATTEMENTS[fichier]
    try:
        import numpy as np
        brut = subprocess.check_output(["ffmpeg", "-v", "error", "-i", fichier, "-t", "120", "-f", "f32le", "-ac", "1",
                                        "-ar", "11025", "-"])
        x = np.frombuffer(brut, np.float32)
        pas = 256                                             # ~23 ms
        e = np.sqrt(np.add.reduceat(x[: len(x) // pas * pas] ** 2, np.arange(0, len(x) // pas * pas, pas)) / pas)
        o = np.maximum(0, np.diff(e, prepend=e[0]))           # montée d'énergie = attaque d'une note
        o = o - o.mean()
        hz = 11025 / pas
        ac = np.correlate(o, o, "full")[len(o) - 1:]
        lo, hi = int(0.33 * hz), int(1.0 * hz)                # 60 à 180 battements par minute
        periode = (lo + int(np.argmax(ac[lo:hi]))) / hz
        phases = np.arange(0, periode, 1 / hz)
        score = [o[np.clip((np.arange(ph, len(o) / hz, periode) * hz).astype(int), 0, len(o) - 1)].sum() for ph in phases]
        depart = phases[int(np.argmax(score))]
        temps = np.arange(depart, len(o) / hz, periode / 2)   # temps et demi-temps
        _BATTEMENTS[fichier] = [round(float(t), 3) for t in temps]
    except Exception:
        _BATTEMENTS[fichier] = []
    return _BATTEMENTS[fichier]


def caler_pauses(phrases, temps, pause=0.18, mini=0.08, maxi=0.45):
    """Durée du silence après chaque phrase pour que l'écran suivant commence sur un temps de la musique (entre `mini` et
    `maxi` s de silence ; sinon la pause habituelle). Écrit p["_pause"]."""
    t = 0.0
    for p in phrases:
        fin = t + p["duree"]
        p["_pause"] = pause
        if temps:
            bons = [b - fin for b in temps if mini <= b - fin <= maxi]
            if bons:
                p["_pause"] = round(min(bons, key=lambda x: abs(x - pause)), 3)
        t = fin + p["_pause"]


def bruitages(phrases, debuts, format_="", transitions=False):
    """[(fichier, instant, volume)] à placer sur la vidéo. Le « woosh » entre les écrans est coupé par défaut (l'auteur ne
    l'aime pas, 24/11/2026 ; réglage video.transitions)."""
    out = []
    for i, p in enumerate(phrases):
        if transitions and i and (p.get("media") or p.get("ecran")):
            out.append(("woosh.wav", max(0.0, debuts[i] - 0.12), 0.35))
        if re.search(r"\d", p.get("ecran") or "") and not p.get("reponse"):
            out.append(("ding.wav", debuts[i] + 0.05, 0.30))
        if p.get("reponse"):
            out.append(("dun_dun.wav", max(0.0, debuts[i] - 0.2), 0.55))
    return out


def mixer(voix, phrases, debuts, total, humeur, sortie, avec_musique=True, format_="", avec_bruitages=True, transitions=False):
    """Fabrique la bande son complète (wav stéréo 44,1 kHz)."""
    entrees = ["-i", voix]
    filtres = ["[0:a]aformat=channel_layouts=stereo,aresample=44100,apad,volume=1.5,asplit=2[vx][cle]"]
    melange = ["[vx]"]
    n = 1
    m = (avec_musique if isinstance(avec_musique, str) else musique(humeur)) if avec_musique else None
    if m:
        entrees += ["-stream_loop", "-1", "-i", m]
        filtres.append(f"[{n}:a]aformat=channel_layouts=stereo,aresample=44100,volume=0.10,"
                       f"afade=t=in:d=1.0,afade=t=out:st={max(0, total - 2.0):.2f}:d=2.0[mus0]")
        filtres.append("[mus0][cle]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=400[mus]")
        melange.append("[mus]"); n += 1
    else:
        filtres[0] = filtres[0].replace(",asplit=2[vx][cle]", "[vx]")
    for fichier, t, vol in (bruitages(phrases, debuts, format_, transitions) if avec_bruitages else []):
        chemin = os.path.join(SONS, fichier)
        if not os.path.exists(chemin):
            continue
        entrees += ["-i", chemin]
        ms = int(t * 1000)
        filtres.append(f"[{n}:a]aformat=channel_layouts=stereo,aresample=44100,volume={vol},adelay={ms}|{ms}[b{n}]")
        melange.append(f"[b{n}]"); n += 1
    filtres.append(f"{''.join(melange)}amix=inputs={len(melange)}:duration=first:normalize=0,atrim=0:{total:.3f}[a]")
    brut = sortie + ".brut.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *entrees, "-filter_complex", ";".join(filtres), "-map", "[a]",
                    "-ar", "44100", "-ac", "2", brut], check=True)
    niveau(brut, sortie)
    os.remove(brut)
    return sortie


def niveau(entree, sortie, cible=-14.0):
    """Volume réglé comme TikTok le conseille (-14 LUFS, crêtes à -1,5 dB) en DEUX passages : mesure, puis réglage exact et
    sans « pompage » (le même volume pour toutes nos vidéos)."""
    import json
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", entree, "-af", f"loudnorm=I={cible}:TP=-1.5:LRA=11:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    try:
        m = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
        if "inf" in str(m.get("input_i", "")).lower() or "inf" in str(m.get("target_offset", "")).lower():
            # son entièrement silencieux (trouvé par le rejeu de la vidéo CAN le 25/11 : ffmpeg plantait) : copié tel quel
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", entree, "-ar", "44100", "-ac", "2", sortie], check=True)
            return
        filtre = (f"loudnorm=I={cible}:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
                  f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    except (ValueError, KeyError):
        filtre = f"loudnorm=I={cible}:TP=-1.5:LRA=11"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", entree, "-af", filtre, "-ar", "44100", "-ac", "2", sortie], check=True)
