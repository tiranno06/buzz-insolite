"""Essai complet de chaque nuit (amélioration 16 du 25/11) : chaque maillon de la fabrication est essayé pour de vrai,
SANS publier ni ajouter de vidéo sur le site, pour qu'une panne soit trouvée avant les vraies vidéos.

Maillons essayés : tests du code (montage complet compris), voix d'homme (Chatterbox, 1 phrase), calage des mots
(Whisper), téléchargement d'une vidéo TikTok d'origine, recadrage et agrandissement (OpenCV), orthographe (LanguageTool),
IA qui écrit, IA qui voit. Résultat : sante.json → « essai_nuit » (onglet Santé) ; une panne est écrite dans le journal.
"""
import os
import subprocess
import sys
import tempfile
import time

from . import depot
from .commun import RACINE, ecrire, iso, lire, noter


def _essai(nom, fonction):
    t = time.time()
    try:
        detail = fonction() or "ok"
        return {"nom": nom, "ok": True, "detail": str(detail)[:120], "duree_s": round(time.time() - t, 1)}
    except Exception as e:
        return {"nom": nom, "ok": False, "detail": str(e)[:160], "duree_s": round(time.time() - t, 1)}


def main():
    from . import citations, ia, langue, vision, voix
    d = tempfile.mkdtemp()
    res = []

    def tests():
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_ACTIONS"}   # les tests n'envoient jamais rien sur GitHub
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=RACINE, capture_output=True,
                           text=True, timeout=1200, env=env)
        fin = (r.stderr or "").strip().splitlines()[-3:]
        if r.returncode:
            raise RuntimeError(" ".join(fin))
        return " ".join(fin)
    res.append(_essai("Tests du code (montage compris)", tests))

    wav = os.path.join(d, "voix.wav")

    def voix_homme():
        voix._chatterbox(["Bonsoir, ceci est l'essai de la nuit."], [wav], [0.5])
        return f"{voix.duree(wav):.1f} s de voix"
    res.append(_essai("Voix d'homme (Chatterbox)", voix_homme))
    res.append(_essai("Calage des mots (Whisper)", lambda: f"{len(voix.mots_entendus(wav))} mots entendus"))

    video = os.path.join(d, "tiktok.mp4")

    def tiktok():
        stock = (lire("videos_lues.json") or {}).get("videos") or []
        if not stock:
            raise RuntimeError("aucune vidéo lue par le relevé du buzz")
        derniere = None
        for v in stock[:3]:
            try:
                citations.telecharger(v["url"], video)
                return f"@{v.get('compte')} : {citations._duree(video):.0f} s"
            except Exception as e:
                derniere = e
        raise derniere
    res.append(_essai("Téléchargement d'une vidéo TikTok d'origine", tiktok))

    image = os.path.join(d, "image.jpg")

    def opencv():
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "2", "-i", video, "-frames:v", "1", "-vf", "scale=600:-2", image],
                       check=True, timeout=60)
        cx = vision.centre_visages(image, video=False)
        grand = vision.agrandir(image)
        if grand == image:
            raise RuntimeError("agrandissement impossible (modèle FSRCNN ou OpenCV)")
        return f"visage : {cx}, photo agrandie"
    res.append(_essai("Recadrage et agrandissement (OpenCV)", opencv))
    res.append(_essai("Orthographe (LanguageTool)", lambda: f"{len(langue.verifier_texte('Les joueur sont rentrés.'))} faute(s) vue(s)"))
    res.append(_essai("IA qui écrit", lambda: ia.demander_json('Réponds en JSON : {"ok": true}', "Essai, réponds en json.",
                                                               max_tokens=200, journal=lambda *a: None)[1]))
    res.append(_essai("IA qui voit", lambda: ia.regarder_json('Réponds en JSON : {"images": [{"n": 1, "decris": "…"}]}',
                                                              "Décris l'image en 3 mots.", [image], journal=lambda *a: None)[1]))
    pannes = [r["nom"] for r in res if not r["ok"]]
    E = {"le": iso(), "resultats": res, "ok": not pannes}
    for r in res:
        print(("✅ " if r["ok"] else "❌ ") + f"{r['nom']} : {r['detail']} ({r['duree_s']} s)", flush=True)

    def appliquer():
        S = lire("sante.json") or {}
        S["essai_nuit"] = E
        ecrire("sante.json", S)
        noter("🧪 Essai de la nuit : " + ("tout fonctionne" if not pannes else "en panne : " + ", ".join(pannes)),
              "info" if not pannes else "erreur")
    depot.enregistrer(appliquer, "Essai de la nuit")
    return 0 if not pannes else 1


if __name__ == "__main__":
    sys.exit(main())
