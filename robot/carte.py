"""Carte animée du lieu de l'actu : zoom de la région jusqu'au point, pays en rouge, épingle qui apparaît.

Données gratuites : frontières Natural Earth (domaine public, téléchargées une fois puis gardées en cache) ; position du lieu
par Photon puis OpenStreetMap (gratuits ; résultats gardés en cache), sinon coordonnées données par l'IA.
"""
import json
import math
import os
import subprocess
import time
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw

from .commun import CACHE, ROBOT_UA

FRONTIERES = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson"
W, H, IPS = 1080, 1920, 30
MER, TERRE, BORD, PAYS = (13, 27, 42), (43, 47, 54), (82, 92, 108), (128, 28, 42)
_dernier = [0.0]


def _cache(nom):
    os.makedirs(CACHE, exist_ok=True)
    return os.path.join(CACHE, nom)


def _photon(lieu):
    q = urllib.parse.urlencode({"q": lieu, "limit": 1, "lang": "fr"})
    req = urllib.request.Request(f"https://photon.komoot.io/api/?{q}", headers={"User-Agent": ROBOT_UA})
    f = json.loads(urllib.request.urlopen(req, timeout=20).read())["features"]
    if f:
        lon, lat = f[0]["geometry"]["coordinates"]
        return dict(lat=float(lat), lon=float(lon), nom=f[0]["properties"].get("name") or lieu, genre=f[0]["properties"].get("type", ""))


def _nominatim(lieu):
    attente = 1.1 - (time.time() - _dernier[0])
    if attente > 0:
        time.sleep(attente)
    _dernier[0] = time.time()
    q = urllib.parse.urlencode({"q": lieu, "format": "json", "limit": 1, "accept-language": "fr"})
    req = urllib.request.Request(f"https://nominatim.openstreetmap.org/search?{q}", headers={"User-Agent": ROBOT_UA})
    d = json.loads(urllib.request.urlopen(req, timeout=20).read())
    if d:
        return dict(lat=float(d[0]["lat"]), lon=float(d[0]["lon"]), nom=d[0].get("name") or lieu,
                    genre=d[0].get("addresstype") or d[0].get("type", ""))


def trouver_lieu(lieu, secours=None):
    """{lat, lon, nom} du lieu (ville, région ou pays), ou None. Photon puis OpenStreetMap (gratuits, ils limitent parfois
    les serveurs partagés), puis `secours` = coordonnées données par l'IA qui a écrit le texte."""
    lieu = (lieu or "").strip()
    if not lieu:
        return None
    fichier = _cache("lieux.json")
    try:
        connus = json.load(open(fichier, encoding="utf-8"))
    except (OSError, ValueError):
        connus = {}
    if connus.get(lieu):
        return connus[lieu]
    r = None
    for chercheur in (_photon, _nominatim):
        try:
            r = chercheur(lieu)
        except Exception:
            r = None
        if r:
            break
    if not r and secours:
        try:
            r = dict(lat=float(secours[0]), lon=float(secours[1]), nom=lieu, genre="ia")
        except (TypeError, ValueError, IndexError):
            r = None
    if r and r["genre"] != "ia":
        connus[lieu] = r
        json.dump(connus, open(fichier, "w", encoding="utf-8"), ensure_ascii=False)
    return r


def pays_du_monde():
    """[(nom, [anneaux de (lon, lat)])] (téléchargé une fois)."""
    fichier = _cache("frontieres.geojson")
    if not os.path.exists(fichier):
        req = urllib.request.Request(FRONTIERES, headers={"User-Agent": ROBOT_UA})
        with open(fichier + ".part", "wb") as f:
            f.write(urllib.request.urlopen(req, timeout=120).read())
        os.replace(fichier + ".part", fichier)
    out = []
    for f in json.load(open(fichier, encoding="utf-8"))["features"]:
        g = f["geometry"]; nom = f["properties"].get("NAME_FR") or f["properties"].get("NAME", "")
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        out.append((nom, [p[0] for p in polys]))
    return out


def _dedans(lon, lat, anneau):
    dedans = False
    for (x1, y1), (x2, y2) in zip(anneau, anneau[1:] + anneau[:1]):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1 + 1e-12) + x1:
            dedans = not dedans
    return dedans


def _merc(lat):
    lat = max(-85.0, min(85.0, lat))
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def image_carte(lat, lon, chemin, largeur_deg=36.0, echelle=2):
    """Grande carte centrée sur le point (2 fois la taille de l'écran) ; renvoie le nom du pays trouvé."""
    w, h = W * echelle, H * echelle
    x_par_deg = w / largeur_deg
    k = x_par_deg * 180 / math.pi                    # pixels par unité de Mercator
    yc = _merc(lat)
    proj = lambda lo, la: ((lo - lon) * x_par_deg + w / 2, (yc - _merc(la)) * k + h / 2)
    im = Image.new("RGB", (w, h), MER); d = ImageDraw.Draw(im)
    pays_point = ""
    lon_min, lon_max = lon - largeur_deg, lon + largeur_deg
    for nom, anneaux in pays_du_monde():
        for a in anneaux:
            if max(p[0] for p in a) < lon_min or min(p[0] for p in a) > lon_max:
                continue
            if _dedans(lon, lat, a):
                pays_point = nom
    for nom, anneaux in pays_du_monde():
        for a in anneaux:
            if max(p[0] for p in a) < lon_min or min(p[0] for p in a) > lon_max or len(a) < 3:
                continue
            pts = [proj(lo, la) for lo, la in a]
            d.polygon(pts, fill=PAYS if nom == pays_point else TERRE, outline=BORD)
            d.line(pts + pts[:1], fill=BORD, width=2 * echelle)
    im.save(chemin)
    return pays_point


def epingle(chemin):
    """Épingle rouge au centre de l'écran (fond transparent)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    cx, cy = W / 2, H / 2
    for r, a in ((70, 40), (48, 70)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 214, 0, a))
    d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=(255, 255, 255, 255))
    d.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], fill=(232, 40, 60, 255))
    im.save(chemin)
    return chemin


def video(media, duree, calque_png, sortie, dossier):
    """Écran « carte » : zoom ×1 → ×4 sur le lieu (doux au début et à la fin), épingle qui apparaît à mi-chemin."""
    carte_png = os.path.join(dossier, "carte.png"); pin = epingle(os.path.join(dossier, "epingle.png"))
    image_carte(media["lat"], media["lon"], carte_png)
    n = max(2, int(duree * IPS))
    z = f"1+3*(1-cos(PI*min(on/{n * 0.8:.1f}\\,1)))/2"
    vf = (f"[0:v]zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps={IPS}[c];"
          f"[2:v]format=rgba,fade=t=in:st={duree * 0.45:.2f}:d=0.3:alpha=1[p];"
          f"[c][p]overlay=0:0[cp];[cp][1:v]overlay=0:0,format=yuv420p[s]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", carte_png, "-loop", "1", "-i", calque_png,
                    "-loop", "1", "-i", pin, "-filter_complex", vf, "-map", "[s]", "-t", f"{duree:.3f}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(IPS), "-an", sortie],
                   check=True)
    return sortie
