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
HUMEURS = ("neutre", "tension", "joie")


def musique(humeur):
    choix = sorted(glob.glob(os.path.join(SONS, "musique", f"{humeur if humeur in HUMEURS else 'neutre'}_*.mp3")))
    return random.choice(choix) if choix else None


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
    m = musique(humeur) if avec_musique else None
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
    filtres.append(f"{''.join(melange)}amix=inputs={len(melange)}:duration=first:normalize=0,"
                   f"atrim=0:{total:.3f},loudnorm=I=-14:TP=-1.5[a]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *entrees, "-filter_complex", ";".join(filtres), "-map", "[a]",
                    "-ar", "44100", "-ac", "2", sortie], check=True)
    return sortie
