"""Courtes citations des vidéos d'origine (demande de l'auteur du 25/11, après explication des risques).

Le sujet d'une vidéo vient de vidéos TikTok virales (Brut, HugoDécrypte…). On en montre de COURTS EXTRAITS, comme le
permet le droit de citation, aux conditions expliquées à l'auteur :
- UN seul extrait par vidéo d'origine (jamais deux passages de la même vidéo), 10 à 15 s : 40 % de la vidéo au plus,
  10 s au moins (donc la moitié d'une vidéo de 20 s au plus) ; une vidéo de moins de 20 s n'est pas citée ; 4 ou 5
  extraits viennent donc de 4 ou 5 vidéos DIFFÉRENTES ;
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


def extraits(sujet, dossier, journal=print, nombre=5, deja=None):
    """Un extrait de 10 à 15 s de chaque vidéo d'origine du sujet (les plus vues d'abord), `nombre` au plus."""
    deja = deja if deja is not None else set()
    videos = [v for v in sujet.get("videos") or [] if v.get("url") and not v.get("indisponible")]
    videos.sort(key=lambda v: -(v.get("vues") or 0))
    out, comptes = [], set()
    for v in videos:
        if len(out) >= nombre:
            break
        cle = f"citation-{v.get('id') or len(out)}"
        if cle in deja:
            continue
        brut = os.path.join(dossier, f"origine-{v.get('id', len(out))}.mp4")
        try:
            if not os.path.exists(brut):
                images._ytdlp(["-f", "mp4/best", "--max-filesize", "300M", "--no-playlist", "-o", brut, v["url"]], timeout=240)
            d = _duree(brut)
            lg = duree_extrait(d)
            if not lg:
                journal(f"  citation @{v.get('compte')} : vidéo de {d:.0f} s, trop courte pour un extrait de 10 s")
                os.remove(brut); continue
            debut = meilleur_moment(_changements(brut), d, lg)
            chemin = os.path.join(dossier, f"citation-{v.get('id', len(out))}.mp4")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(debut), "-i", brut, "-t", str(lg), "-an",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", chemin],
                           check=True, timeout=300)
            raison = images.lisible(chemin)
            if raison:
                raise OSError(f"extrait illisible : {raison}")
        except Exception as e:
            journal(f"  citation @{v.get('compte')} impossible ({str(e)[:100]})"); continue
        compte = v.get("compte") or "source"
        comptes.add(compte)
        out.append(dict(type="video", chemin=chemin, duree=lg, debut=0, id=cle, citation=True, compte=compte,
                        credit=f"@{compte} (TikTok, extrait cité)", page=v["url"], auteur=f"@{compte}",
                        licence="courte citation (source visible, logo non flouté)",
                        origine=dict(duree=round(d, 1), debut=debut, longueur=lg)))
        deja.add(cle)
        journal(f"  ✓ citation @{compte} : {lg:.0f} s à partir de {debut:.0f} s (sur {d:.0f} s, soit {100 * lg / d:.0f} %)")
        try:
            os.remove(brut)                                    # la vidéo entière n'est jamais gardée
        except OSError:
            pass
    return out
