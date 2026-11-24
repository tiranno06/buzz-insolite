"""Analyse du STYLE d'un profil TikTok (demande de l'auteur du 24/11 : « c'est ce genre de vidéo que je voudrais »).

Pour les vidéos les plus vues du profil : durée, chiffres, texte dit (Whisper), plans (coupes d'images), et description par
une IA qui voit de 6 images (type d'images, textes à l'écran, sous-titres, mise en page). Tout est écrit dans le journal en
TEXTE seulement : les vidéos sont effacées tout de suite, jamais gardées ni reprises.

    python outils/analyser_profil.py storynewsfm 3       (workflow « Analyser un profil TikTok », analyser.yml)
"""
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from robot import ia, voix  # noqa: E402

CONSIGNE = """Tu analyses le STYLE d'une vidéo TikTok d'actualité à partir de 6 images prises dans l'ordre. Décris, en français :
- "images" : que voit-on (vraie vidéo de la scène filmée au téléphone, caméra de surveillance, images de télé, photos, images
  d'illustration, face caméra, écran de texte…) ;
- "textes_ecran" : textes incrustés (titre en haut, bandeau, chiffres, sous-titres mot à mot…), leur couleur, leur place ;
- "mise_en_page" : cadre (plein écran, flou derrière, bandes), logo, couleurs dominantes ;
- "accroche" : ce qui attire l'œil dans les 2 premières secondes ;
- "resume" : en 2 phrases, la recette de la vidéo.
Réponds uniquement en JSON : {"images": "…", "textes_ecran": "…", "mise_en_page": "…", "accroche": "…", "resume": "…"}"""


def liste(profil, n=30):
    r = subprocess.run([sys.executable, "-m", "yt_dlp", "--flat-playlist", "--no-warnings", "--impersonate", "chrome",
                        "--playlist-end", str(n), "-J", f"https://www.tiktok.com/@{profil}"], capture_output=True, text=True, timeout=300)
    return json.loads(r.stdout).get("entries") or []


def plans(chemin):
    """Nombre de coupes d'image (changements de plan)."""
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", chemin, "-vf", "select='gt(scene,0.35)',showinfo", "-f", "null", "-"],
                       capture_output=True, text=True)
    return r.stderr.count("pts_time:")


def analyser(profil, combien=3):
    E = sorted(liste(profil), key=lambda e: -(e.get("view_count") or 0))
    print(f"@{profil} : {len(E)} vidéos lues")
    for e in E:
        print(f"  {e.get('duration')} s — {e.get('view_count'):,} vues — {e.get('like_count'):,} j'aime — "
              f"{(e.get('description') or '')[:120]}".replace("\n", " "))
    for e in E[:combien]:
        with tempfile.TemporaryDirectory() as d:
            chemin = os.path.join(d, "v.mp4")
            r = subprocess.run([sys.executable, "-m", "yt_dlp", "-q", "--no-warnings", "--impersonate", "chrome", "-o", chemin,
                                f"https://www.tiktok.com/@{profil}/video/{e['id']}"], capture_output=True, text=True, timeout=300)
            if r.returncode or not os.path.exists(chemin):
                print(f"\n=== vidéo {e['id']} : illisible ({(r.stderr or '')[-150:]})"); continue
            duree = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", chemin]))
            print(f"\n=== {e.get('view_count'):,} vues, {duree:.0f} s, {plans(chemin)} coupes d'image")
            try:
                mots = voix.mots_entendus(chemin)
                texte = " ".join(m for m, _, _ in mots)
                print(f"  débit : {len(mots) / max(1, duree):.1f} mots/s")
                print(f"  TEXTE DIT : {texte[:2500]}")
            except Exception as x:
                print(f"  texte dit : impossible ({x})")
            imgs = []
            for k in range(6):
                img = os.path.join(d, f"i{k}.jpg")
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{duree * (0.02 + 0.19 * k):.2f}", "-i", chemin,
                                "-frames:v", "1", "-vf", "scale=540:-2", img])
                if os.path.exists(img):
                    imgs.append(img)
            try:
                avis, qui = ia.regarder_json(CONSIGNE, "Décris le style de cette vidéo TikTok.", imgs[:5])
                for k, v in avis.items():
                    print(f"  {k} : {v}")
            except Exception as x:
                print(f"  regard de l'IA impossible ({x})")


if __name__ == "__main__":
    analyser(sys.argv[1].lstrip("@"), int(sys.argv[2]) if len(sys.argv) > 2 else 3)
