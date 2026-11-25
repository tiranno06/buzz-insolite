"""Outils d'image (demande de l'auteur du 25/11, améliorations 2, 3 et 4), tous gratuits et sur le processeur :
- `scenes` : changements de plan d'une vidéo (PySceneDetect ; sinon ffmpeg) → les extraits commencent et finissent sur un plan ;
- `centre_visages` : où sont les visages (OpenCV YuNet) → une vidéo ou une photo HORIZONTALE est recadrée sur eux au lieu
  du milieu (MediaPipe ne détecte plus les visages sans modèle à part depuis ses dernières versions : YuNet, plus léger) ;
- `agrandir` : une petite photo (moins de 1000 px de large) est agrandie ×2 par un réseau de neurones léger (OpenCV
  dnn_superres, FSRCNN). Real-ESRGAN demande une carte graphique, absente des machines gratuites de GitHub.
Les modèles (quelques centaines de Ko) sont téléchargés une fois puis gardés en cache (creer.yml).
Tout échec renvoie une valeur neutre : la vidéo se fait quand même, comme avant.
"""
import os
import re
import subprocess
import urllib.request

MODELES = os.environ.get("BUZZ_MODELES", os.path.expanduser("~/.cache/buzz-modeles"))
URLS = {
    "yunet.onnx": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "FSRCNN_x2.pb": "https://raw.githubusercontent.com/Saafke/FSRCNN_Tensorflow/master/models/FSRCNN_x2.pb",
}


def modele(nom):
    chemin = os.path.join(MODELES, nom)
    if not os.path.exists(chemin) or os.path.getsize(chemin) < 10000:
        os.makedirs(MODELES, exist_ok=True)
        req = urllib.request.Request(URLS[nom], headers={"User-Agent": "buzz-insolite-robot"})
        with urllib.request.urlopen(req, timeout=60) as r, open(chemin + ".tmp", "wb") as f:
            f.write(r.read())
        if os.path.getsize(chemin + ".tmp") < 10000:
            os.remove(chemin + ".tmp")
            raise OSError(f"modèle {nom} illisible")
        os.replace(chemin + ".tmp", chemin)
    return chemin


# ------------------------------------------------------------------ 3. changements de plan
def scenes(fichier, seuil=27.0):
    """Instants (s) des changements de plan. PySceneDetect si installé, sinon le filtre « scene » de ffmpeg."""
    try:
        from scenedetect import ContentDetector, detect
        return [round(a.get_seconds(), 2) for a, _ in detect(fichier, ContentDetector(threshold=seuil))[1:]]
    except Exception:
        r = subprocess.run(["ffmpeg", "-v", "info", "-i", fichier, "-vf", "select='gt(scene,0.25)',showinfo", "-an", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=300)
        return [round(float(x), 2) for x in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def caler_sur_plans(debut, lg, plans, d, mini=10.0, ecart=2.0):
    """Début et longueur d'un extrait recalés sur les changements de plan : il commence au début d'un plan (si un
    changement est à moins de 2 s) et s'arrête à la fin d'un plan (sans descendre sous `mini` secondes)."""
    apres = [t for t in plans if debut <= t <= debut + ecart and t + mini <= d]
    if apres:
        debut = apres[0]
    fins = [t for t in plans if debut + mini <= t <= debut + lg]
    if fins:
        lg = fins[-1] - debut
    return round(debut, 2), round(min(lg, d - debut), 2)


# ------------------------------------------------------------------ 2. recadrage sur les visages
def _image(fichier, t=None):
    import cv2
    if t is None:
        return cv2.imread(fichier)
    cap = cv2.VideoCapture(fichier)
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, img = cap.read()
    cap.release()
    return img if ok else None


def centre_visages(fichier, debut=0.0, duree=10.0, video=True):
    """Position horizontale (0 = gauche, 1 = droite) du plus grand visage, moyenne sur 4 images ; None si aucun visage."""
    try:
        import cv2
        det = None
        xs = []
        for k in range(4 if video else 1):
            img = _image(fichier, debut + duree * (k + 0.5) / 4 if video else None)
            if img is None:
                continue
            h, w = img.shape[:2]
            if w > 1280:
                img = cv2.resize(img, (1280, int(h * 1280 / w))); h, w = img.shape[:2]
            if det is None:
                det = cv2.FaceDetectorYN.create(modele("yunet.onnx"), "", (w, h), 0.7)
            det.setInputSize((w, h))
            _, faces = det.detect(img)
            if faces is not None and len(faces):
                x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])[:4]
                xs.append((x + fw / 2) / w)
        return round(sum(xs) / len(xs), 3) if xs else None
    except Exception:
        return None


# ------------------------------------------------------------------ 4. petites photos agrandies
def agrandir(chemin, largeur_min=1000):
    """Photo de moins de 1000 px de large : agrandie ×2 (FSRCNN, rapide sur processeur). Renvoie le chemin (inchangé si
    rien à faire ou en cas d'échec)."""
    try:
        import cv2
        img = cv2.imread(chemin)
        if img is None or img.shape[1] >= largeur_min:
            return chemin
        sr = cv2.dnn_superres.DnnSuperResImpl_create()
        sr.readModel(modele("FSRCNN_x2.pb"))
        sr.setModel("fsrcnn", 2)
        grand = sr.upsample(img)
        sortie = os.path.splitext(chemin)[0] + "-x2.jpg"
        cv2.imwrite(sortie, grand, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return sortie
    except Exception:
        return chemin
