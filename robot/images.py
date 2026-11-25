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
            return dict(type="video", url=url, secours=ii["url"], id=f"commons-{p['pageid']}", credit=f"{auteur} / Wikimedia Commons, {lic}",
                        page=f"https://commons.wikimedia.org/?curid={p['pageid']}", licence=lic, auteur=auteur)
        return dict(type="photo", url=ii.get("thumburl") or ii["url"], id=f"commons-{p['pageid']}",
                    credit=f"{auteur} / Wikimedia Commons, {lic}", page=f"https://commons.wikimedia.org/?curid={p['pageid']}",
                    licence=lic, auteur=auteur)
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
    if not (_mots_sujet(titre) & _mots_sujet(entite)) and titre.lower() not in entite.lower():
        return None                                       # mauvaise page (essai du 24/11 : « Yosemite » pour Franco)
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
                    credit=credit_commons(nom) or f"Wikipédia, article « {titre} »",
                    page="https://commons.wikimedia.org/wiki/" + urllib.parse.quote(nom.replace(" ", "_")))
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
PASSAGE = 10                                          # morceaux de vraie vidéo de 10 s (un écran en prend 5 à 10 s)
YT_CC = "https://www.youtube.com/results?search_query={q}&sp=EgIwAQ%253D%253D"      # filtre « Creative Commons » de YouTube
MOTS_VIDES = {"le", "la", "les", "un", "une", "des", "du", "de", "et", "en", "à", "au", "aux", "pour", "sur", "dans", "par", "avec",
              "son", "sa", "ses", "qui", "que", "est", "ce", "cette", "plus", "après", "vidéo", "video", "fou", "folle", "choc"}


MOTS_VIDES_EN = {"the", "and", "for", "with", "can", "will", "you", "your", "this", "that", "from", "have", "has", "are", "was",
                 "were", "but", "not", "all", "new", "how", "why", "what", "who", "after", "over", "into", "out", "our", "they",
                 "their", "its", "get", "got", "one", "two", "day", "live", "news", "official", "full", "part", "first", "best",
                 "about", "just", "more", "most", "make", "made", "time", "year", "years", "world", "people", "watch", "here",
                 "there", "when", "where", "which", "than", "then", "them", "these", "those", "some", "very", "only", "also"}


def _mots_sujet(t):
    """Mots qui désignent VRAIMENT le sujet : sans nombres (« 2025 »), ni petits mots français ou anglais (« can », « the ») —
    essai du 24/11 : « CAN 2025 » prenait une conférence sur Musk parce que son titre contenait « can't »."""
    t = re.sub(r"[^\wÀ-ÿ]+", " ", str(t).lower())
    return {m for m in t.split() if len(m) > 3 and not m.isdigit() and m not in MOTS_VIDES and m not in MOTS_VIDES_EN}


def _ytdlp(args, timeout=120):
    r = subprocess.run(["yt-dlp", "--no-warnings", "--js-runtimes", "deno", *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1][:160] if (r.stderr or r.stdout).strip() else "yt-dlp")
    return r.stdout


# Licences qui permettent de reprendre et de monter la vidéo sur une chaîne monétisée : CC BY, CC BY-SA, CC0, domaine public.
# Jamais NC (pas d'usage commercial) ni ND (pas de modification). Une vidéo de télé ou d'agence est écartée même si elle porte
# une licence libre (souvent remise en ligne par quelqu'un qui n'en a pas le droit).
MEDIAS_INTERDITS = ("bfm", "bfmtv", "bfm tv", "tf1", "france 2", "france 3", "france 24", "france24", "franceinfo", "france info", "m6", "cnews",
                    "lci", "afp", "reuters", "associated press", "euronews", "arte", "canal+", "rmc", "c8", "tmc", "le monde",
                    "le figaro", "le parisien", "brut", "konbini", "hugodécrypte", "hugo décrypte", "20 minutes", "ouest-france",
                    "bbc", "cnn", "nbc", "abc news", "cbs", "sky news", "fox news", "al jazeera", "new york times", "nytimes",
                    "washington post", "daily mail", "unilad", "ladbible", "insider", "dw news", "usa today", "ny post")


def licence_ok(texte):
    t = str(texte or "").lower()
    if "-nc" in t or "noncommercial" in t or "non commercial" in t or "-nd" in t or "noderiv" in t:
        return False
    return any(x in t for x in ("creative commons attribution", "licenses/by/", "licenses/by-sa/", "publicdomain", "cc0",
                                "public domain", "domaine public", "attribution", "cc by"))


def _interdit(*textes):
    t = " ".join(str(x or "") for x in textes).lower()
    return any(re.search(r"(^|\W)" + re.escape(m) + r"(\W|$)", t) for m in MEDIAS_INTERDITS)


def _cand_youtube(sujet, journal):
    d = json.loads(_ytdlp(["--flat-playlist", "-J", "--playlist-end", "20", YT_CC.format(q=urllib.parse.quote_plus(sujet[:80]))], 90))
    return [dict(source="YouTube", page=f"https://www.youtube.com/watch?v={e['id']}", cle=f"yt-{e['id']}", titre=e.get("title", ""),
                 auteur=e.get("channel") or "", duree=e.get("duration") or 0, licence=None) for e in d.get("entries") or []]


def _cand_peertube(sujet, journal):
    q = urllib.parse.urlencode([("search", sujet[:80]), ("count", 20), ("licenceOneOf", 1), ("licenceOneOf", 2), ("licenceOneOf", 7)])
    d = _json(f"https://sepiasearch.org/api/v1/search/videos?{q}")
    lic = {1: "CC BY", 2: "CC BY-SA", 7: "domaine public"}
    return [dict(source="PeerTube", page=v["url"], cle=f"pt-{v.get('uuid') or v['url'][-12:]}", titre=v.get("name", ""),
                 auteur=(v.get("account") or {}).get("displayName", ""), duree=v.get("duration") or 0,
                 licence=lic.get((v.get("licence") or {}).get("id"))) for v in d.get("data") or [] if not v.get("isLive")]


def _cand_archive(sujet, journal):
    q = urllib.parse.urlencode([("q", f"({sujet[:80]}) AND mediatype:movies AND licenseurl:[* TO *]"), ("fl[]", "identifier"),
                                ("fl[]", "title"), ("fl[]", "licenseurl"), ("fl[]", "creator"), ("rows", 20), ("output", "json")])
    d = _json(f"https://archive.org/advancedsearch.php?{q}")
    out = []
    for v in (d.get("response") or {}).get("docs") or []:
        if licence_ok(v.get("licenseurl")):
            out.append(dict(source="Internet Archive", page=f"https://archive.org/details/{v['identifier']}", cle=f"ia-{v['identifier']}",
                            titre=v.get("title", ""), auteur=v.get("creator") if isinstance(v.get("creator"), str) else "",
                            duree=0, licence=v["licenseurl"].rstrip("/").split("/licenses/")[-1].replace("/", " ").upper()
                            if "/licenses/" in v["licenseurl"] else "domaine public"))
    return out


def _cand_vimeo(sujet, journal):
    """Vimeo : seules les vidéos que l'auteur a mises sous CC BY, CC BY-SA ou CC0 (clé gratuite facultative VIMEO_TOKEN)."""
    jeton = os.environ.get("VIMEO_TOKEN")
    if not jeton:
        return []
    out = []
    for filtre in ("CC-BY", "CC-BY-SA", "CC0"):
        q = urllib.parse.urlencode({"query": sujet[:80], "filter": filtre, "per_page": 15,
                                    "fields": "link,name,duration,user.name,license"})
        d = _json(f"https://api.vimeo.com/videos?{q}", {"Authorization": f"bearer {jeton}",
                                                       "Accept": "application/vnd.vimeo.*+json;version=3.4"})
        for v in d.get("data") or []:
            lic = {"by": "CC BY", "by-sa": "CC BY-SA", "cc0": "CC0"}.get(str(v.get("license") or "").lower())
            if lic:
                out.append(dict(source="Vimeo", page=v["link"], cle=f"vm-{v['link'].rstrip('/').rsplit('/', 1)[-1]}",
                                titre=v.get("name", ""), auteur=(v.get("user") or {}).get("name", ""),
                                duree=v.get("duration") or 0, licence=lic))
    return out


YOUTUBE = {"refuse": False}                            # YouTube a refusé ce serveur pendant le passage


SOURCES_VIDEO = (("YouTube (Creative Commons)", _cand_youtube), ("PeerTube", _cand_peertube), ("Internet Archive", _cand_archive), ("Vimeo", _cand_vimeo))


CONSIGNE_TRI = """Tu tries des vidéos pour illustrer une actualité. On te donne le SUJET et une liste de titres de vidéos
(numérotés, avec leur chaîne). Garde SEULEMENT celles qui montrent VRAIMENT ce sujet : le même événement, la même personne,
le même lieu ou l'objet précis dont il parle. Écarte tout le reste (autre sujet, vlog, conférence, jeu vidéo, tutoriel, mot en
commun par hasard). Réponds uniquement en JSON : {"garder": [numéros]}"""


def filtrer_par_ia(sujet, mots_en, candidats, journal=print):
    """Une IA relit les titres des vidéos candidates et ne garde que celles qui parlent vraiment du sujet (les mots en commun
    ne suffisent pas). IA indisponible : on garde le tri par les mots."""
    if not candidats:
        return candidats
    from . import ia
    liste = "\n".join(f"{k}. {c['titre'][:110]} (chaîne : {c['auteur'][:40]})" for k, (_, c) in enumerate(candidats[:40]))
    try:
        d, _ = ia.demander_json(CONSIGNE_TRI, f"SUJET : {sujet} ({' '.join(mots_en or [])})\n\nVIDÉOS :\n{liste}",
                                temperature=0.1, max_tokens=600, journal=journal)
    except Exception as e:
        journal(f"  tri des vidéos par l'IA impossible ({str(e)[:60]}) : tri par les mots seulement")
        return candidats
    garder = {int(n) for n in d.get("garder") or [] if str(n).isdigit()}
    gardes = [x for k, x in enumerate(candidats[:40]) if k in garder]
    journal(f"  l'IA garde {len(gardes)} vidéo(s) sur {min(40, len(candidats))} qui parlent vraiment du sujet")
    return gardes


def telecharger_peertube(page, debut, fin, chemin):
    """PeerTube : le fichier vidéo direct donné par l'API de l'instance (le téléchargement « normal » est refusé (403) par
    beaucoup d'instances, essai du 24/11) ; ffmpeg ne lit que le passage voulu."""
    hote = urllib.parse.urlparse(page).netloc
    uuid = page.rstrip("/").rsplit("/", 1)[-1]
    d = _json(f"https://{hote}/api/v1/videos/{uuid}")
    fichiers = list(d.get("files") or []) + [f for p in d.get("streamingPlaylists") or [] for f in p.get("files") or []]
    fichiers = [f for f in fichiers if f.get("fileUrl")]
    if not fichiers:
        raise OSError("aucun fichier vidéo public")
    f = min(fichiers, key=lambda f: abs(((f.get("resolution") or {}).get("id") or 0) - 480))
    # Seul le DÉBUT du fichier est téléchargé (assez pour [debut, fin] + marge) : rapide même pour une vidéo d'une heure ;
    # un mp4 « fragmenté » de PeerTube se lit très bien en partie (ffmpeg qui le lit à distance est, lui, très lent).
    duree = float(d.get("duration") or 0)
    taille = int(f.get("size") or 0)
    octets = int(taille * min(1.0, (fin + 8) / duree) * 1.3) + 2_000_000 if duree and taille else 60_000_000
    partiel = chemin + ".partiel.mp4"
    req = urllib.request.Request(f["fileUrl"], headers={"User-Agent": "Mozilla/5.0", "Range": f"bytes=0-{octets}"})
    with urllib.request.urlopen(req, timeout=120) as r, open(partiel, "wb") as sortie:
        while True:
            bloc = r.read(1 << 20)
            if not bloc:
                break
            sortie.write(bloc)
            if sortie.tell() > octets + (1 << 20):
                break
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(debut), "-i", partiel, "-t", str(max(6, fin - debut)),
                        "-vf", "scale=-2:'min(720,ih)'", "-c:v", "libx264", "-preset", "veryfast", "-an", chemin],
                       check=True, timeout=300)
    finally:
        os.remove(partiel)


def _telecharger_passage(c, debut, fin, duree, chemin, journal=print):
    """Le passage [debut, fin] de la vidéo candidate `c` dans `chemin` (mp4)."""
    if c["source"] == "PeerTube":
        try:
            telecharger_peertube(c["page"], debut, fin, chemin)
            if os.path.exists(chemin) and os.path.getsize(chemin) > 50000:
                return
        except Exception as x:
            journal(f"  PeerTube direct impossible ({str(x)[:60]}) : autre méthode")
    try:
        _ytdlp(["-q", "-f", "bv*[height<=720][ext=mp4]/b[height<=720]/b", "--download-sections", f"*{debut}-{fin}",
                "--force-keyframes-at-cuts", "--merge-output-format", "mp4", "-o", chemin, c["page"]], 300)
    except Exception:                                      # découpe refusée : vidéo entière (si courte), coupée par ffmpeg
        if duree > 900:
            raise
        entier = chemin[:-4] + "-entier.mp4"
        _ytdlp(["-q", "-f", "b[height<=720]/bv*[height<=720]+ba/b", "--merge-output-format", "mp4", "-o", entier, c["page"]], 400)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(debut), "-t", str(fin - debut), "-i", entier,
                        "-c:v", "libx264", "-preset", "veryfast", "-an", chemin], check=True, timeout=300)
        os.remove(entier)


def videos_du_sujet(sujet, mots_cles, dossier, journal=print, maxi=3, ecrans=8, prefixe="sujet", deja=None, mots_en=()):
    """VRAIES vidéos du sujet, publiées par leur auteur sous licence libre (CC BY, CC BY-SA, CC0, domaine public) : YouTube
    (filtre Creative Commons, licence relue sur la page), PeerTube (Sepia Search), Internet Archive, Wikimedia Commons.
    Au moins 2 mots du sujet dans le titre ; télé et agences écartées ; auteur et licence crédités. Chaque vidéo est découpée
    en passages de 6 s (un par écran). Un site qui refuse le serveur = on s'en passe (jamais de contournement)."""
    voulus = _mots_sujet(sujet + " " + " ".join(mots_cles or []) + " " + " ".join(mots_en or []))
    seuil = min(2, len(voulus)) or 1                    # « Toulouse » seul : 1 mot suffit ; sinon 2 mots du sujet
    vus = {d.rsplit("-", 1)[0] for d in (deja or ())}    # vidéos déjà prises pour cette vidéo : jamais deux fois
    candidats = []
    for nom, chercher in SOURCES_VIDEO:
        if chercher is _cand_youtube and (not shutil_which("yt-dlp") or YOUTUBE["refuse"]):
            continue
        trouves = []
        for requete in [sujet] + ([" ".join(list(mots_en)[:4])] if mots_en else []):   # en français, puis en anglais
            try:
                trouves += chercher(requete, journal)
            except Exception as e:
                journal(f"  vidéos du sujet ({nom}) : recherche impossible ({str(e)[:90]})")
        bons = 0
        for c in trouves:
            commun = len(voulus & _mots_sujet(c["titre"]))
            if commun >= seuil and c["cle"] not in vus and not vus.add(c["cle"]) and (not c["duree"] or 10 <= c["duree"] <= 3600) and not _interdit(c["titre"], c["auteur"]):
                candidats.append((commun, c)); bons += 1
        journal(f"  vidéos du sujet ({nom}) : {len(trouves)} trouvée(s), {bons} sur le sujet")
    candidats = filtrer_par_ia(sujet, mots_en, candidats, journal)
    candidats.sort(key=lambda x: -x[0])
    # TOUTES les sources mélangées (demande de l'auteur du 24/11) : à tour de rôle, la meilleure de chaque source, et le même
    # titre trouvé sur deux sources (copie) n'est gardé qu'une fois
    par_source, titres_vus, copies = {}, set(), []
    for x in candidats:
        cle_titre = " ".join(sorted(_mots_sujet(x[1]["titre"])))[:80]
        if cle_titre and cle_titre in titres_vus:
            copies.append(x); continue                     # copie : essayée seulement si l'original est refusé
        titres_vus.add(cle_titre)
        par_source.setdefault(x[1]["source"], []).append(x)
    candidats = [L[k] for k in range(max(map(len, par_source.values()), default=0)) for L in par_source.values() if k < len(L)]
    candidats += copies
    out, prises, youtube_refuse = [], 0, False
    essais = 0
    for _, c in candidats:                                 # TOUS les candidats (essai du 24/11 : les 8 premiers étaient
        if prises >= maxi or essais >= 14:                 # des YouTube refusés, PeerTube n'était jamais essayé)
            break
        if c["source"] == "YouTube":
            if youtube_refuse or YOUTUBE["refuse"]:
                continue
            essais += 1
            try:
                info = json.loads(_ytdlp(["-J", c["page"]], 90))
            except Exception as x:
                journal(f"  vidéo YouTube illisible ({str(x)[:80]})")
                if any(m in str(x) for m in ("429", "Sign in", "bot")):   # YouTube refuse ce serveur : plus essayé
                    youtube_refuse = YOUTUBE["refuse"] = True                # de tout le passage (jamais contourné)
                    journal("  YouTube refuse les serveurs de GitHub : autres sources seulement pour cette vidéo")
                continue
            if "creative commons" not in str(info.get("license") or "").lower():
                continue                                   # licence relue : non libre = jamais reprise
            c["licence"] = "CC BY"; c["duree"] = info.get("duration") or c["duree"]
            c["auteur"] = info.get("channel") or c["auteur"]
        if not c.get("licence"):
            continue
        if c["source"] != "YouTube":
            essais += 1
        duree = float(c["duree"] or 0)
        debut = 3 if duree > 40 else 0
        longueur = PASSAGE * max(3, ecrans // max(1, maxi)) + 2      # assez de morceaux de 10 s pour cette vidéo
        fin = debut + longueur if not duree else min(duree, debut + longueur)
        chemin = os.path.join(dossier, f"{prefixe}-{prises}.mp4")
        try:
            _telecharger_passage(c, debut, fin, duree, chemin, journal)
            reelle = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                                    "csv=p=0", chemin]))
        except Exception as x:
            journal(f"  vidéo {c['source']} : téléchargement refusé ({str(x)[:80]})")
            continue
        prises += 1
        auteur = (c["auteur"] or c["source"])[:40]
        for k in range(max(1, int(reelle // PASSAGE))):
            out.append(dict(type="video", chemin=chemin, debut=PASSAGE * k, duree=reelle, id=f"{c['cle']}-{k}", url=c["page"],
                            page=c["page"], licence=c["licence"], auteur=auteur, titre_source=c["titre"][:120],
                            credit=f"Vidéo : {auteur} ({c['source']}, {c['licence']})", reelle=True))
        journal(f"  vraie vidéo du sujet : « {c['titre'][:70]} » de {auteur} ({c['source']}, {c['licence']}, {int(reelle // PASSAGE)} morceaux de {PASSAGE} s)")
    try:                                                   # Wikimedia Commons : vidéos libres, recherche en français
        m = commons_video(" ".join(sorted(voulus, key=len, reverse=True)[:3]), set(deja or ()))
        if m and m["id"] not in vus:
            chemin = os.path.join(dossier, f"{prefixe}-commons.webm")
            try:
                _telecharger(m["url"], chemin)
            except Exception:
                chemin = chemin[:-5] + "." + m["secours"].rsplit(".", 1)[-1].lower(); _telecharger(m["secours"], chemin)
            reelle = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", chemin]))
            for k in range(max(1, min(4, int(reelle // PASSAGE)))):
                out.append(dict(m, chemin=chemin, debut=PASSAGE * k, duree=reelle, id=f"{m['id']}-{k}", reelle=True))
            journal(f"  vraie vidéo du sujet : Wikimedia Commons ({m['credit'][:60]})")
    except Exception as e:
        journal(f"  vidéos du sujet (Wikimedia Commons) : {str(e)[:80]}")
    if not out:
        journal("  aucune vraie vidéo du sujet sous licence libre (photos Wikipédia à la place)")
    par_video = {}
    for m in out:                                          # passages alternés entre les vidéos (plus varié à l'écran)
        par_video.setdefault(m["chemin"], []).append(m)
    listes = list(par_video.values())
    return [L[k] for k in range(max(map(len, listes), default=0)) for L in listes if k < len(L)]


def shutil_which(nom):
    import shutil
    return shutil.which(nom)


def trouver_photo(entite, dossier, n, deja, journal=print):
    """Vraie photo FIXE de la personne / du lieu / de l'objet (galerie de son article Wikipédia), ou None."""
    try:
        m = wikipedia_media(entite, deja)
        if m and _recuperer(m, dossier, n, deja, journal):
            return m
    except Exception as e:
        journal(f"    photo de « {entite} » : {str(e)[:80]}")
    return None


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
