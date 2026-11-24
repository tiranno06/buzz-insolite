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
GENERIQUES = (pexels_video, pixabay_video, pexels_photo, pixabay_photo)   # banques d'images « pour meubler » : coupées par défaut


# ------------------------------------------------------------------ vraies images du sujet (demande de l'auteur du 24/11)
def _wiki(url, essais=4):
    """Wikipédia / Wikimedia, avec pauses si le site demande de ralentir (erreur 429)."""
    for k in range(essais):
        try:
            return _json(url)
        except urllib.error.HTTPError as e:
            if e.code != 429 or k == essais - 1:
                raise
            time.sleep(3 * (k + 1))


def wikipedia_media(entite, deja):
    """Vraies photos de la personne, du lieu ou de l'objet dont parle la phrase : galerie de son article Wikipédia en
    français (qui n'accepte QUE des images libres de droits), dans l'ordre de l'article. Jamais deux fois la même."""
    q = urllib.parse.urlencode({"action": "query", "list": "search", "srsearch": entite, "srlimit": 1, "format": "json"})
    res = (_wiki(f"https://fr.wikipedia.org/w/api.php?{q}").get("query") or {}).get("search") or []
    if not res:
        return None
    titre = res[0]["title"]
    galerie = _wiki("https://fr.wikipedia.org/api/rest_v1/page/media-list/" + urllib.parse.quote(titre.replace(" ", "_")))
    for it in galerie.get("items") or []:
        nom = str(it.get("title") or "")
        if it.get("type") != "image" or not re.search(r"\.(jpe?g|png|webp)$", nom, re.I) or re.search(r"logo|carte|map|blason|signature|drapeau|flag", nom, re.I):
            continue
        cle = f"wiki-{nom}"
        if cle in deja:
            continue
        src = (it.get("srcset") or [{}])[-1].get("src") or ""
        if not src:
            continue
        return dict(type="photo", url=("https:" + src) if src.startswith("//") else src, id=cle, entite=titre,
                    credit=credit_commons(nom) or f"Wikipédia, article « {titre} »")
    return None


def credit_commons(fichier):
    """« Auteur / Wikimedia Commons, licence » d'un fichier (vide si illisible)."""
    try:
        q = urllib.parse.urlencode({"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "extmetadata",
                                    "titles": fichier if fichier.startswith(("File:", "Fichier:")) else "File:" + fichier,
                                    "iiextmetadatafilter": "Artist|LicenseShortName"})
        page = next(iter(_wiki(f"https://commons.wikimedia.org/w/api.php?{q}", 2)["query"]["pages"].values()))
        m = page["imageinfo"][0]["extmetadata"]
        auteur = re.sub("<[^>]+>", "", m.get("Artist", {}).get("value", "")).strip()[:40] or "Wikimedia Commons"
        return f"{auteur} / Wikimedia Commons, {m.get('LicenseShortName', {}).get('value', '')}".strip(", ")
    except Exception:
        return ""


def carte_presse(article, chemin):
    """Écran « LA PRESSE EN PARLE » : le vrai titre de l'article et le nom du média (citation avec sa source)."""
    from PIL import Image, ImageDraw, ImageFont
    from .commun import POLICES
    W, H = 1080, 982                                       # même format que l'image nette au milieu de l'écran
    im = Image.new("RGB", (W, H), (242, 238, 230)); d = ImageDraw.Draw(im)
    gras = os.path.join(POLICES, "Poppins-Bold.ttf"); moyen = os.path.join(POLICES, "Poppins-Medium.ttf")
    d.rectangle([0, 0, W, 130], fill=(25, 25, 28))
    d.text((60, 34), "LA PRESSE EN PARLE", font=ImageFont.truetype(gras, 56), fill=(255, 214, 0))
    d.text((60, 170), str(article.get("media", ""))[:40].upper(), font=ImageFont.truetype(gras, 48), fill=(232, 40, 60))
    mots = str(article.get("titre", "")).split()
    for taille in (76, 68, 60, 52, 46, 40):               # le plus gros texte qui tient
        f = ImageFont.truetype(gras, taille); lignes, ligne = [], ""
        for m in mots:
            essai = (ligne + " " + m).strip()
            if d.textlength(essai, font=f) > W - 120 and ligne:
                lignes.append(ligne); ligne = m
            else:
                ligne = essai
        lignes.append(ligne)
        if 250 + len(lignes) * taille * 1.3 < H - 110:
            break
    y = 250
    for l in lignes:
        d.text((60, y), l, font=f, fill=(20, 20, 22)); y += int(taille * 1.3)
    d.text((60, H - 80), "Source : " + str(article.get("media", ""))[:60], font=ImageFont.truetype(moyen, 38), fill=(90, 90, 95))
    im.save(chemin)
    return dict(type="photo", chemin=chemin, id=f"presse-{article.get('titre', '')[:40]}", credit=f"Titre : {article.get('media', '')}",
                presse=True)



# ------------------------------------------------------------------ vraies vidéos du sujet (demande de l'auteur du 24/11)
YT_CC = "https://www.youtube.com/results?search_query={q}&sp=EgIwAQ%253D%253D"      # filtre « Creative Commons » de YouTube
MOTS_VIDES = {"le", "la", "les", "un", "une", "des", "du", "de", "et", "en", "à", "au", "aux", "pour", "sur", "dans", "par", "avec",
              "son", "sa", "ses", "qui", "que", "est", "ce", "cette", "plus", "après", "vidéo", "video", "fou", "folle", "choc"}


def _mots_sujet(t):
    t = re.sub(r"[^\wÀ-ÿ]+", " ", str(t).lower())
    return {m for m in t.split() if len(m) > 2 and m not in MOTS_VIDES}


def _ytdlp(args, timeout=120):
    r = subprocess.run(["yt-dlp", "--no-warnings", "--js-runtimes", "deno", *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1][:160] if (r.stderr or r.stdout).strip() else "yt-dlp")
    return r.stdout


def videos_du_sujet(sujet, mots_cles, dossier, journal=print, maxi=2, ecrans=8):
    """VRAIES vidéos du sujet : celles que leur auteur a publiées sur YouTube sous licence Creative Commons BY (réutilisation
    permise en citant l'auteur, ce que font les crédits). La licence est relue sur la page de chaque vidéo ; il faut au moins
    2 mots du sujet dans son titre. Chaque vidéo est découpée en passages de 6 s (un par écran). YouTube qui refuse le serveur
    = on s'en passe (jamais de contournement). Renvoie une liste de médias d'écran."""
    if not shutil_which("yt-dlp"):
        return []
    voulus = _mots_sujet(sujet + " " + " ".join(mots_cles or []))
    try:
        d = json.loads(_ytdlp(["--flat-playlist", "-J", "--playlist-end", "20",
                               YT_CC.format(q=urllib.parse.quote_plus(sujet[:80]))], 90))
    except Exception as e:
        journal(f"  vidéos du sujet (YouTube) : recherche impossible ({str(e)[:100]})")
        return []
    candidats = []
    for e in d.get("entries") or []:
        commun = len(voulus & _mots_sujet(e.get("title", "")))
        if commun >= 2 and 15 <= (e.get("duration") or 0) <= 1800:
            candidats.append((commun, e))
    candidats.sort(key=lambda c: -c[0])
    out = []
    for _, e in candidats[:5]:
        if len([m for m in out if m["id"].endswith("-0")]) >= maxi:
            break
        url = f"https://www.youtube.com/watch?v={e['id']}"
        try:
            info = json.loads(_ytdlp(["-J", url], 90))
        except Exception as x:
            journal(f"  vidéo YouTube {e['id']} illisible ({str(x)[:80]})")
            if "429" in str(x) or "Sign in" in str(x) or "bot" in str(x):
                break                                      # YouTube refuse ce serveur : on n'insiste pas
            continue
        if "creative commons" not in str(info.get("license") or "").lower():
            continue                                       # licence non libre : jamais reprise
        duree = float(info.get("duration") or 0)
        debut = 3 if duree > 40 else 0
        fin = min(duree, debut + 6 * ecrans + 2)
        chemin = os.path.join(dossier, f"sujet-{e['id']}.mp4")
        try:
            _ytdlp(["-q", "-f", "bv*[height<=720][ext=mp4]/b[height<=720]/b", "--download-sections", f"*{debut}-{fin}",
                    "--force-keyframes-at-cuts", "--merge-output-format", "mp4", "-o", chemin, url], 300)
            reelle = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                                    "csv=p=0", chemin]))
        except Exception as x:
            journal(f"  vidéo YouTube {e['id']} : téléchargement refusé ({str(x)[:80]})")
            continue
        auteur = info.get("channel") or info.get("uploader") or "auteur YouTube"
        for k in range(max(1, int(reelle // 6))):
            out.append(dict(type="video", chemin=chemin, debut=6 * k, duree=reelle, id=f"yt-{e['id']}-{k}",
                            url=url, credit=f"Vidéo : {auteur} (YouTube, CC BY)", reelle=True))
        journal(f"  vraie vidéo du sujet : « {info.get('title', '')[:70]} » de {auteur} (CC BY, {int(reelle // 6)} passages)")
    if not out:
        journal("  aucune vraie vidéo du sujet sous licence libre sur YouTube")
    return out


def shutil_which(nom):
    import shutil
    return shutil.which(nom)


def trouver(requete, dossier, n, deja, journal=print, theme="", entite="", generiques=False):
    """Média de l'écran : d'abord une VRAIE photo de ce dont parle la phrase (`entite`, galerie Wikipédia), puis les sources
    publiques (NASA, Wikimedia) ; les banques d'images génériques seulement si l'auteur les a autorisées (`generiques`).
    None = écran de texte, plutôt qu'une image sans rapport. `deja` : identifiants déjà utilisés."""
    if entite:
        try:
            m = wikipedia_media(entite, deja)
            if m and _recuperer(m, dossier, n, deja, journal):
                return m
        except Exception as e:
            journal(f"    Wikipédia « {entite} » : {str(e)[:80]}")
    m = _trouver(requete, dossier, n, deja, journal, generiques)
    if not m and theme and theme.lower() != requete.lower():
        m = _trouver(theme, dossier, n, deja, journal, generiques)
    return m


def _recuperer(m, dossier, n, deja, journal):
    chemin = os.path.join(dossier, f"media{n:02d}.jpg")
    try:
        _telecharger(m["url"], chemin)
    except Exception as e:
        journal(f"    téléchargement refusé ({str(e)[:60]})")
        return False
    deja.add(m["id"]); m["chemin"] = chemin
    return True


def _trouver(requete, dossier, n, deja, journal=print, generiques=False):
    for chercheur in CHERCHEURS:
        if chercheur in GENERIQUES and not generiques:
            continue
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
