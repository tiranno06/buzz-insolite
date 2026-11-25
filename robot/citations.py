"""Courtes citations des vidéos d'origine (demande de l'auteur du 25/11, après explication des risques).

Le sujet d'une vidéo vient de vidéos TikTok virales (Brut, HugoDécrypte…). On en montre de COURTS EXTRAITS, comme le
permet le droit de citation, aux conditions expliquées à l'auteur :
- extraits de 10 à 15 s (40 % de la vidéo au plus, 10 s au moins ; vidéo de moins de 20 s non citée) ; d'abord un par
  vidéo d'origine, puis d'autres passages des mêmes vidéos (autorisé par l'auteur le 25/11) sans que l'ensemble repris
  d'une vidéo dépasse la MOITIÉ de sa durée (`PART_TOTALE`) ;
- la source reste VISIBLE : le logo n'est jamais flouté, un bandeau « Images : @compte (TikTok) » est affiché pendant
  l'extrait, et la source est citée dans les crédits et la description ;
- l'extrait illustre NOTRE vidéo (notre texte, notre voix ; le son d'origine est coupé) ;
- le moment choisi est celui où l'image bouge le plus (changements de plan), hors début et fin (titres, génériques).
Le risque (retrait demandé par un média, vidéo jugée « pas assez originale » par TikTok) est connu de l'auteur.
"""
import os
import re
import subprocess

from . import images

DUREE_MIN, DUREE_MAX, PART_MAX, ORIGINE_MIN = 10.0, 15.0, 0.4, 20.0
PART_TOTALE = 0.5                                        # ensemble repris d'une même vidéo : la moitié au plus


def duree_extrait(d):
    """Longueur de l'extrait pour une vidéo d'origine de d secondes (0 = trop courte pour un extrait de 10 s)."""
    if not d or d < ORIGINE_MIN:
        return 0
    return round(max(DUREE_MIN, min(DUREE_MAX, d * PART_MAX)), 2)


def meilleur_moment(changements, d, lg):
    """Début de la fenêtre de `lg` s qui contient le plus de changements de plan, entre 10 % et 90 % de la vidéo."""
    a, b = d * 0.1, max(d * 0.1, d * 0.9 - lg)
    if b <= a:
        return max(0.0, (d - lg) / 2)
    debuts = [a + k * (b - a) / 20 for k in range(21)]
    return round(max(debuts, key=lambda x: (sum(1 for t in changements if x <= t < x + lg), -abs(x - d * 0.3))), 2)


def _changements(fichier):
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", fichier, "-vf", "select='gt(scene,0.25)',showinfo", "-an", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=300)
    return [float(x) for x in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def _duree(fichier):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", fichier],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def moments(changements, d, lg, nombre):
    """Jusqu'à `nombre` fenêtres de `lg` s qui ne se chevauchent pas, celles où l'image bouge le plus d'abord, entre 10 % et
    90 % de la vidéo ; renvoyées dans l'ordre de la vidéo d'origine."""
    a, b = d * 0.1, d * 0.9 - lg
    if b <= a:
        return [max(0.0, (d - lg) / 2)][:nombre]
    debuts = [a + k * (b - a) / 40 for k in range(41)]
    score = lambda x: (sum(1 for t in changements if x <= t < x + lg), -abs(x - d * 0.3))
    pris = []
    for x in sorted(debuts, key=score, reverse=True):
        if len(pris) >= nombre:
            break
        if all(abs(x - y) >= lg for y in pris):
            pris.append(round(x, 2))
    return sorted(pris)


def extraits(sujet, dossier, journal=print, nombre=5, deja=None):
    """Extraits de 10 à 15 s des vidéos d'origine du sujet (les plus vues d'abord), `nombre` au plus : d'abord un par vidéo,
    puis d'autres passages des mêmes vidéos (autorisé par l'auteur le 25/11) tant que l'ensemble repris d'une vidéo reste
    sous la MOITIÉ de sa durée (une vidéo de 24 s ne donne donc qu'un extrait)."""
    deja = deja if deja is not None else set()
    videos = [v for v in sujet.get("videos") or [] if v.get("url") and not v.get("indisponible")]
    videos.sort(key=lambda v: -(v.get("vues") or 0))
    plans = []                                                # (vidéo, fichier, durée, longueur, [débuts])
    for v in videos[:8]:
        brut = os.path.join(dossier, f"origine-{v.get('id', len(plans))}.mp4")
        try:
            if not os.path.exists(brut):
                images._ytdlp(["-f", "mp4/best", "--max-filesize", "300M", "--no-playlist", "-o", brut, v["url"]], timeout=240)
            d = _duree(brut)
            lg = duree_extrait(d)
            if not lg:
                journal(f"  citation @{v.get('compte')} : vidéo de {d:.0f} s, trop courte pour un extrait de 10 s")
                os.remove(brut); continue
            n_max = max(1, int(d * PART_TOTALE // lg))
            plans.append((v, brut, d, lg, moments(_changements(brut), d, lg, n_max)))
        except Exception as e:
            journal(f"  citation @{v.get('compte')} impossible ({str(e)[:100]})")
    ordre = [(p, k) for k in range(max((len(p[4]) for p in plans), default=0)) for p in plans if k < len(p[4])]
    out = []
    for (v, brut, d, lg, debuts), k in ordre:                 # un par vidéo d'abord, puis les passages suivants
        if len(out) >= nombre:
            break
        cle = f"citation-{v.get('id', 'x')}-{k}"
        if cle in deja:
            continue
        debut = debuts[k]
        chemin = os.path.join(dossier, f"{cle}.mp4")
        try:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(debut), "-i", brut, "-t", str(lg), "-an",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", chemin],
                           check=True, timeout=300)
            raison = images.lisible(chemin)
            if raison:
                raise OSError(f"extrait illisible : {raison}")
        except Exception as e:
            journal(f"  citation @{v.get('compte')} ({debut:.0f} s) impossible ({str(e)[:100]})"); continue
        compte = v.get("compte") or "source"
        out.append(dict(type="video", chemin=chemin, duree=lg, debut=0, id=cle, citation=True, compte=compte,
                        credit=f"@{compte} (TikTok, extrait cité)", page=v["url"], auteur=f"@{compte}",
                        licence="courte citation (source visible, logo non flouté)",
                        origine=dict(duree=round(d, 1), debut=debut, longueur=lg)))
        deja.add(cle)
        journal(f"  ✓ citation @{compte} : {lg:.0f} s à partir de {debut:.0f} s (vidéo de {d:.0f} s)")
    for p in plans:                                           # la vidéo entière n'est jamais gardée
        try:
            os.remove(p[1])
        except OSError:
            pass
    return out
