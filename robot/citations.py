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

from . import ia, images
from .commun import lire

DUREE_MIN, DUREE_MAX, PART_MAX, ORIGINE_MIN = 10.0, 15.0, 0.4, 20.0
PARCOMPTE_MAX = 3                                          # extraits d'un même compte au plus (variété des sources)
COMPTES_FR = {"hugodecrypte", "brutofficiel", "franceinfo", "leparisien", "20minutesfrance", "euronewsfr", "bfmtv", "lemondefr",
              "konbini", "tf1info", "loopsider", "ouestfrance", "lefigaro", "le.huffpost"}
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


CONSIGNE_MEME_EVENEMENT = """On te donne un événement d'actualité précis et une liste numérotée de descriptions de vidéos TikTok
de médias. Garde SEULEMENT les vidéos qui parlent de CE MÊME événement précis (même fait, même lieu, mêmes personnes, même
moment) ; écarte celles qui parlent d'un autre événement, même proche (autre match, autre affaire, autre discours).
Réponds uniquement en JSON : {"garder": [numéros]}"""


def videos_du_meme_evenement(sujet, journal=print, maxi=12):
    """Vidéos de l'événement sur TOUS les comptes suivis (demande de l'auteur du 25/11) : les vidéos virales du sujet, puis
    toutes les autres vidéos lues ces 7 jours (videos_lues.json, même sous les seuils) qui parlent du MÊME événement
    (mots en commun, puis confirmation par l'IA)."""
    connues = [v for v in sujet.get("videos") or [] if v.get("url") and not v.get("indisponible")]
    ids = {str(v.get("id")) for v in connues}
    voulus = images._mots_sujet(" ".join([sujet.get("titre", "")] + list(sujet.get("mots_cles") or [])
                                         + list(sujet.get("mots_cles_en") or [])))
    stock = (lire("videos_lues.json") or {}).get("videos") or []
    cand = []
    for v in stock:
        if str(v.get("id")) in ids or not v.get("url"):
            continue
        commun = len(voulus & images._mots_sujet(v.get("texte") or ""))
        if commun >= 2:
            cand.append((commun, v))
    cand = [v for _, v in sorted(cand, key=lambda x: (-x[0], -(x[1].get("vues") or 0)))[:25]]
    autres = []
    if cand:
        texte = f"ÉVÉNEMENT : {sujet.get('titre', '')} — {sujet.get('resume', '')}\n" + "\n".join(
            f"{i}. @{v.get('compte')} : {(v.get('texte') or '')[:250]}" for i, v in enumerate(cand))
        try:
            d, _ = ia.demander_json(CONSIGNE_MEME_EVENEMENT, texte, temperature=0.1, journal=journal)
            garder = d.get("garder") if isinstance(d, dict) else d
            autres = [cand[int(n)] for n in garder or [] if str(n).isdigit() and int(n) < len(cand)]
        except Exception as e:                                # IA indisponible : seulement les vidéos très proches
            journal(f"  tri des autres vidéos par l'IA impossible ({str(e)[:80]}) : mots en commun seulement")
            autres = [v for v in cand if len(voulus & images._mots_sujet(v.get("texte") or "")) >= 3]
    # comptes FRANÇAIS d'abord (la vidéo est en français), puis les plus vues (vidéo CAN du 25/11 : 7 extraits sur 10 d'Al
    # Jazeera, en anglais)
    francais = lambda v: 0 if v.get("compte") in COMPTES_FR else 1
    connues.sort(key=lambda v: (francais(v), -(v.get("vues") or 0)))
    autres.sort(key=lambda v: (francais(v), -(v.get("vues") or 0)))
    journal(f"  vidéos de l'événement : {len(connues)} du sujet + {len(autres)} d'autres comptes suivis"
            + (f" ({', '.join('@' + str(v.get('compte')) for v in autres[:8])})" if autres else ""))
    return (connues + autres)[:maxi]


def telecharger(url, chemin, essais=3):
    """TikTok répond parfois « Unexpected response from webpage request » (vidéo CAN du 25/11 : Brut, BFM, HugoDécrypte
    perdus) : 3 essais simples espacés (10 s, 20 s). Jamais de contournement : un refus qui dure = vidéo passée."""
    import time
    for n in range(essais):
        try:
            return images._ytdlp(["-f", "mp4/best", "--max-filesize", "300M", "--no-playlist", "-o", chemin, url], timeout=240)
        except Exception:
            if n == essais - 1:
                raise
            time.sleep(10 * (n + 1))


def images_fixes(brut, d, pris, lg, nombre, dossier, base):
    """Images fixes de l'événement tirées de la vidéo d'origine, à des moments qui ne sont PAS dans les extraits."""
    out, t = [], d * 0.15
    pas = max(1.0, d * 0.7 / (nombre + 1))
    while len(out) < nombre and t < d * 0.9:
        if all(not (a - 1 <= t <= a + lg + 1) for a in pris):
            chemin = os.path.join(dossier, f"{base}-image{len(out)}.jpg")
            r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", brut, "-frames:v", "1", "-q:v", "2", chemin],
                               capture_output=True, timeout=120)
            if r.returncode == 0 and not images.lisible(chemin):
                out.append((t, chemin))
        t += pas
    return out


def extraits(sujet, dossier, journal=print, nombre=5, deja=None, photos=3):
    """Extraits de 10 à 15 s des vidéos d'origine du sujet (les plus vues d'abord), `nombre` au plus : d'abord un par vidéo,
    puis d'autres passages des mêmes vidéos (autorisé par l'auteur le 25/11) tant que l'ensemble repris d'une vidéo reste
    sous la MOITIÉ de sa durée (une vidéo de 24 s ne donne donc qu'un extrait)."""
    deja = deja if deja is not None else set()
    videos = videos_du_meme_evenement(sujet, journal)
    plans = []                                                # (vidéo, fichier, durée, longueur, [débuts])
    for v in videos:
        brut = os.path.join(dossier, f"origine-{v.get('id', len(plans))}.mp4")
        try:
            if not os.path.exists(brut):
                telecharger(v["url"], brut)
            d = _duree(brut)
            lg = duree_extrait(d)
            if not lg:                                        # trop courte pour un extrait : images fixes seulement
                journal(f"  citation @{v.get('compte')} : vidéo de {d:.0f} s, trop courte pour un extrait de 10 s (images fixes seulement)")
                plans.append((v, brut, d, 0, [])); continue
            n_max = max(1, int(d * PART_TOTALE // lg))
            plans.append((v, brut, d, lg, moments(_changements(brut), d, lg, n_max)))
        except Exception as e:
            journal(f"  citation @{v.get('compte')} impossible ({str(e)[:100]})")
    ordre = [(p, k) for k in range(max((len(p[4]) for p in plans), default=0)) for p in plans if k < len(p[4])]
    out, par_compte = [], {}
    for (v, brut, d, lg, debuts), k in ordre:                 # un par vidéo d'abord, puis les passages suivants
        if len(out) >= nombre:
            break
        if par_compte.get(v.get("compte"), 0) >= PARCOMPTE_MAX:
            continue
        par_compte[v.get("compte")] = par_compte.get(v.get("compte"), 0) + 1
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
    # images fixes de l'événement (« photos »), tirées des vidéos d'origine hors des extraits, une vidéo après l'autre
    fixes = []
    for v, brut, d, lg, debuts in sorted(plans, key=lambda p: bool(p[4])):   # vidéos sans extrait d'abord
        if len(fixes) >= photos:
            break
        pris = [m["origine"]["debut"] for m in out if m["page"] == v["url"]]
        for t, chemin in images_fixes(brut, d, pris, lg, min(2, photos - len(fixes)), dossier, f"citation-{v.get('id', 'x')}"):
            compte = v.get("compte") or "source"
            fixes.append(dict(type="photo", chemin=chemin, id=os.path.basename(chemin)[:-4], citation=True, compte=compte,
                              credit=f"@{compte} (TikTok, image citée)", page=v["url"], auteur=f"@{compte}",
                              licence="courte citation (source visible, logo non flouté)", origine=dict(duree=round(d, 1), image_a=round(t, 1))))
    if fixes:
        journal(f"  {len(fixes)} image(s) fixe(s) de l'événement tirée(s) des vidéos d'origine")
    out += fixes
    for p in plans:                                           # la vidéo entière n'est jamais gardée
        try:
            os.remove(p[1])
        except OSError:
            pass
    return out


CONSIGNE_PHOTOS_PRESSE = """On te montre des photos tirées d'articles de presse sur un événement précis. Pour CHAQUE photo, dis si
elle montre CET événement (le lieu, les personnes, le moment) : "evenement" true ; false pour un logo, une publicité, un
dessin, un graphique, une photo d'archive sans lien avec ce jour-là, ou un autre événement.
Réponds uniquement en JSON : {"images": [{"n": numéro, "evenement": true/false}]}"""


def _empreinte(chemin):
    """Empreinte de l'image (8 × 8 gris) : la même photo d'agence reprise par plusieurs médias n'est gardée qu'une fois."""
    from PIL import Image
    with Image.open(chemin) as im:
        petit = im.convert("L").resize((8, 8))
        px = list(petit.getdata())
    moy = sum(px) / len(px)
    return sum(1 << k for k, p in enumerate(px) if p > moy)


def photos_presse(articles, sujet, dossier, journal=print, maxi=6):
    """Photos de l'événement prises dans les articles de presse (demande de l'auteur du 25/11) : photo principale et photos
    du corps de chaque article, téléchargées, réenregistrées, sans doublon (même photo d'agence chez plusieurs médias), de
    600 px de large au moins, puis confirmées par l'IA qui voit (montre bien CET événement). Crédit « Photo : média »."""
    from PIL import Image
    from . import sources
    cand, vues = [], []
    for k, a in enumerate(articles):
        if len(cand) >= maxi * 2:
            break
        media, lien = a.get("media") or "presse", a.get("lien") or ""
        if not lien.startswith("http") or "news.google.com" in lien or media in ("Wikipédia (contexte)", "Sujet du buzz"):
            continue
        urls = a.get("photos")
        if urls is None:
            try:
                urls = sources.texte_article(lien, avec_images=True)[1]
            except Exception:
                urls = []
        for j, u in enumerate(urls[:3]):
            chemin = os.path.join(dossier, f"presse-photo-{k}-{j}")
            try:
                with open(chemin, "wb") as f:
                    f.write(sources._ouvrir(u, timeout=30))
                chemin = images.photo_standard(chemin)
                with Image.open(chemin) as im:
                    larg, haut = im.size
                if larg < 600 or haut < 300:
                    continue
                e = _empreinte(chemin)
                if any(bin(e ^ x).count("1") <= 6 for x in vues):
                    continue
                vues.append(e)
                cand.append(dict(type="photo", chemin=chemin, id=f"presse-photo-{k}-{j}", citation=True, compte=media,
                                 bandeau=f"Photo : {media}", credit=f"Photo : {media} (article cité)", page=lien,
                                 auteur=media, licence="photo d'article de presse, source citée", origine=dict(image=u)))
            except Exception as ex:
                journal(f"  photo de {media} illisible ({str(ex)[:60]})")
    if not cand:
        return []
    garder = {i for i in range(len(cand))}
    try:
        avis = {}
        for k in range(0, len(cand), 5):
            paquet = cand[k:k + 5]
            d, _ = ia.regarder_json(CONSIGNE_PHOTOS_PRESSE, f"ÉVÉNEMENT : {sujet.get('titre', '')} — {sujet.get('resume', '')}",
                                    [m["chemin"] for m in paquet], journal=journal)
            for r in d.get("images") or []:
                try:
                    avis[k + int(r.get("n")) - 1] = r.get("evenement")
                except (TypeError, ValueError):
                    pass
        garder = {i for i in garder if avis.get(i) is not False}
    except Exception as ex:
        journal(f"  photos de presse non regardées par l'IA ({str(ex)[:60]}) : toutes gardées")
    out = [m for i, m in enumerate(cand) if i in garder][:maxi]
    journal(f"  {len(out)} photo(s) de l'événement prises dans les articles ({', '.join(sorted({m['compte'] for m in out}))})")
    return out
