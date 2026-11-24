"""Images de chaque écran : vraies vidéos libres de droits d'abord, sinon photos libres, sinon écran de texte.

Ordre : Pexels vidéos → Pexels photos (clé gratuite PEXELS_API_KEY ; usage commercial permis) → NASA (domaine public) →
Wikimedia Commons (licences libres, auteur crédité). Une même vidéo n'est jamais montrée deux fois dans la même vidéo.
"""
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

from .commun import ROBOT_UA

PEXELS = "https://api.pexels.com"


def _json(url, entetes=None, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": ROBOT_UA, **(entetes or {})})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def _telecharger(url, chemin):
    url = urllib.parse.quote(url, safe=":/?&=%~+@,;!$*'()#")   # adresses avec « – », accents… (Wikimedia)
    req = urllib.request.Request(url, headers={"User-Agent": ROBOT_UA})
    with urllib.request.urlopen(req, timeout=120) as r, open(chemin, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    return chemin


def pexels_video(requete, deja):
    cle = os.environ.get("PEXELS_API_KEY", "").strip()
    if not cle:
        return None
    q = urllib.parse.urlencode({"query": requete, "per_page": 12, "size": "medium"})
    d = _json(f"{PEXELS}/videos/search?{q}", {"Authorization": cle})
    for v in d.get("videos") or []:
        if f"pexels-v{v['id']}" in deja or (v.get("duration") or 0) < 4 or not pertinent(requete, v.get("url", "").replace("-", " ")):
            continue
        fichiers = [f for f in v.get("video_files") or [] if f.get("file_type") == "video/mp4" and (f.get("height") or 0) >= 720]
        if not fichiers:
            continue
        f = min(fichiers, key=lambda f: abs((f.get("height") or 0) - 1080))   # assez net, pas trop lourd
        return dict(type="video", url=f["link"], id=f"pexels-v{v['id']}", duree=v.get("duration"),
                    credit=f"{(v.get('user') or {}).get('name', 'Pexels')} / Pexels")
    return None


def pexels_photo(requete, deja):
    cle = os.environ.get("PEXELS_API_KEY", "").strip()
    if not cle:
        return None
    q = urllib.parse.urlencode({"query": requete, "per_page": 10, "orientation": "portrait"})
    d = _json(f"{PEXELS}/v1/search?{q}", {"Authorization": cle})
    for p in d.get("photos") or []:
        if f"pexels-p{p['id']}" not in deja:
            return dict(type="photo", url=p["src"].get("large2x") or p["src"]["original"], id=f"pexels-p{p['id']}",
                        credit=f"{p.get('photographer', 'Pexels')} / Pexels")
    return None


A_EVITER = ("green screen", "greenscreen", "chroma", "emoji", "background", "abstract", "animation", "cartoon", "loop", "particles")


def pertinent(requete, etiquettes):
    """Le média parle-t-il de ce qu'on cherche ? (un mot de la recherche dans ses mots-clés, aucun mot « à éviter »)."""
    e = str(etiquettes).lower()
    if any(m in e for m in A_EVITER):
        return False
    mots = [m for m in re.findall(r"[a-z]+", requete.lower()) if len(m) > 3]
    return not mots or any(m.rstrip("s") in e for m in mots)


def pixabay_video(requete, deja):
    """Pixabay (clé gratuite PIXABAY_API_KEY ; usage commercial permis, vidéos téléchargées, jamais liées)."""
    cle = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not cle:
        return None
    q = urllib.parse.urlencode({"key": cle, "q": requete[:100], "per_page": 12, "safesearch": "true"})
    for v in _json(f"https://pixabay.com/api/videos/?{q}").get("hits") or []:
        if f"pixabay-v{v['id']}" in deja or (v.get("duration") or 0) < 4 or not pertinent(requete, v.get("tags", "")):
            continue
        tailles = v.get("videos") or {}
        f = next((tailles[t] for t in ("medium", "large", "small") if (tailles.get(t) or {}).get("url")), None)
        if f:
            return dict(type="video", url=f["url"], id=f"pixabay-v{v['id']}", duree=v.get("duration"),
                        credit=f"{v.get('user', 'Pixabay')} / Pixabay")
    return None


def pixabay_photo(requete, deja):
    cle = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not cle:
        return None
    q = urllib.parse.urlencode({"key": cle, "q": requete[:100], "per_page": 10, "image_type": "photo", "safesearch": "true"})
    for p in _json(f"https://pixabay.com/api/?{q}").get("hits") or []:
        if f"pixabay-p{p['id']}" not in deja and p.get("largeImageURL") and pertinent(requete, p.get("tags", "")):
            return dict(type="photo", url=p["largeImageURL"], id=f"pixabay-p{p['id']}", credit=f"{p.get('user', 'Pixabay')} / Pixabay")
    return None


def nasa_video(requete, deja):
    q = urllib.parse.urlencode({"q": requete, "media_type": "video", "page_size": 10})
    d = _json(f"https://images-api.nasa.gov/search?{q}")
    for it in d["collection"]["items"]:
        nid = it["data"][0]["nasa_id"]
        if f"nasa-{nid}" in deja:
            continue
        liens = _json(f"https://images-api.nasa.gov/asset/{urllib.parse.quote(nid)}")["collection"]["items"]
        mp4 = [l["href"] for l in liens if l["href"].endswith("~medium.mp4") or l["href"].endswith("~mobile.mp4")]
        if mp4:
            return dict(type="video", url=mp4[0].replace("http://", "https://").replace(" ", "%20"), id=f"nasa-{nid}",
                        credit="NASA (domaine public)")
    return None


_COMMONS = {"refus": 0, "dernier": 0.0}


def commons_video(requete, deja):
    """Vraies vidéos de Wikimedia Commons (sans clé) : licences libres seulement, auteur crédité."""
    return commons_photo(requete, deja, video=True)


def commons_photo(requete, deja, video=False):
    """Wikimedia limite les demandes rapides (erreur 429) : 4 s entre deux recherches, arrêt après 2 refus."""
    if _COMMONS["refus"] >= 2:
        return None
    attente = 4 - (time.time() - _COMMONS["dernier"])
    if attente > 0:
        time.sleep(attente)
    _COMMONS["dernier"] = time.time()
    try:
        return _commons(requete, deja, video)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            _COMMONS["refus"] += 1
        raise


def _commons(requete, deja, video=False):
    q = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 8,
                                "gsrsearch": f"filetype:{'video' if video else 'bitmap'} {requete}", "prop": "imageinfo",
                                "iiprop": "url|extmetadata", "iiurlwidth": 1280, "iiextmetadatafilter": "Artist|LicenseShortName"})
    d = _json(f"https://commons.wikimedia.org/w/api.php?{q}")
    for p in (d.get("query") or {}).get("pages", {}).values():
        ii = p["imageinfo"][0]; m = ii.get("extmetadata") or {}
        lic = (m.get("LicenseShortName") or {}).get("value", "")
        if f"commons-{p['pageid']}" in deja or not any(x in lic for x in ("CC BY", "CC0", "Public domain", "domaine public")) \
                or "NC" in lic or "ND" in lic:
            continue
        nom = re.sub(r"[^a-z]", " ", p["title"].lower())
        if not any(len(m) > 3 and m in nom for m in requete.lower().split()):
            continue                                     # nom du fichier sans rapport avec la recherche : écarté
        auteur = re.sub("<[^>]+>", "", (m.get("Artist") or {}).get("value", "")).strip()[:40] or "Wikimedia Commons"
        if video:                                    # version transcodée en 480p (plus légère que l'original)
            url = ii["url"]
            nom = url.rsplit("/", 1)[1]
            url = url.replace("/commons/", "/commons/transcoded/", 1) + f"/{nom}.480p.vp9.webm"
            return dict(type="video", url=url, secours=ii["url"], id=f"commons-{p['pageid']}", credit=f"{auteur} / Wikimedia Commons, {lic}")
        return dict(type="photo", url=ii.get("thumburl") or ii["url"], id=f"commons-{p['pageid']}",
                    credit=f"{auteur} / Wikimedia Commons, {lic}")
    return None


CHERCHEURS = (pexels_video, pixabay_video, nasa_video, commons_video, pexels_photo, pixabay_photo, commons_photo)


def trouver(requete, dossier, n, deja, journal=print, theme=""):
    """Télécharge un média pour la requête (puis pour le thème de la vidéo) ; None = écran de texte, plutôt qu'une image
    sans rapport. `deja` : identifiants déjà utilisés."""
    m = _trouver(requete, dossier, n, deja, journal)
    if not m and theme and theme.lower() != requete.lower():
        m = _trouver(theme, dossier, n, deja, journal)
    return m


def _trouver(requete, dossier, n, deja, journal=print):
    for chercheur in CHERCHEURS:
        if chercheur is nasa_video and not any(m in requete.lower() for m in ("space", "nasa", "mars", "moon", "rocket",
                                                                               "astronaut", "planet", "satellite", "earth from")):
            continue                                       # NASA seulement pour les sujets d'espace
        try:
            m = chercheur(requete, deja)
        except Exception as e:
            journal(f"    {chercheur.__name__} : {str(e)[:80]}")
            continue
        if not m:
            continue
        ext = (".webm" if m["url"].endswith(".webm") else ".mp4") if m["type"] == "video" else ".jpg"
        chemin = os.path.join(dossier, f"media{n:02d}{ext}")
        try:
            _telecharger(m["url"], chemin)
        except Exception as e:
            try:
                if not m.get("secours"):
                    raise
                chemin = chemin.rsplit(".", 1)[0] + "." + m["secours"].rsplit(".", 1)[-1].lower()
                _telecharger(m["secours"], chemin)             # Wikimedia : fichier d'origine
            except Exception:
                journal(f"    téléchargement refusé ({str(e)[:60]})")
                continue
        deja.add(m["id"]); m["chemin"] = chemin
        if m["type"] == "video":
            try:
                m["duree"] = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                                            "-of", "csv=p=0", chemin]))
            except Exception:
                pass
            if m["id"].startswith("nasa-") and m.get("duree"):
                m["debut"] = round(m["duree"] * 0.3)    # vidéos NASA : écran noir et panneau de présentation au début
        time.sleep(0.5)
        return m
    return None
