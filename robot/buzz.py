"""Repérage des actualités du MONDE ENTIER qui buzzent sur TikTok (comptes d'actualité français et internationaux).

Le robot lit les dernières vidéos des comptes d'actualité suivis (Réglages → Buzz) et ne garde que celles qui dépassent les
seuils (par défaut 500 000 vues, 10 000 j'aime, 1 000 commentaires, publiées ces 72 dernières heures). Une IA gratuite les
regroupe par SUJET (plusieurs comptes parlent souvent de la même actu). Résultat : docs/donnees/buzz.json, affiché dans
l'onglet « 🔥 Buzz » du site.

Important : on ne garde que le SUJET et les chiffres. La vidéo d'un autre compte n'est jamais téléchargée ni reprise.

    python -m robot.buzz            (workflow buzz.yml, toutes les 2 heures)
"""
import hashlib
import json
import re
import subprocess
import sys
import time
import unicodedata

from . import sources, ia
from .commun import ecrire, iso, lire, maintenant, noter, reglages

VARIANTES = (["--impersonate", "chrome"], ["--extractor-args", "tiktok:api_hostname=api16-normal-c-useast1a.tiktokv.com"], [])


def videos_du_compte(pseudo, n=30):
    """Dernières vidéos d'un compte TikTok avec leurs chiffres (liste vide si le compte ne répond pas)."""
    url = f"https://www.tiktok.com/@{pseudo}"
    for v in VARIANTES:
        try:
            r = subprocess.run([sys.executable, "-m", "yt_dlp", "--flat-playlist", "--no-warnings", "--socket-timeout", "30", *v,
                                "--playlist-end", str(n), "-J", url], capture_output=True, text=True, timeout=180)
        except Exception:
            continue
        if r.returncode != 0 or not r.stdout.strip():
            continue
        try:
            d = json.loads(r.stdout)
        except ValueError:
            continue
        out = []
        for e in d.get("entries") or []:
            vid = str(e.get("id") or "")
            if not vid:
                continue
            out.append(dict(id=vid, compte=pseudo, url=f"https://www.tiktok.com/@{pseudo}/video/{vid}",
                            vues=e.get("view_count") or 0, jaime=e.get("like_count") or 0,
                            commentaires=e.get("comment_count") or 0, partages=e.get("repost_count") or 0,
                            date=e.get("timestamp") or e.get("release_timestamp") or 0,
                            texte=str(e.get("description") or e.get("title") or "")[:400]))
        if out:
            return out
    return []


def virales(videos, B, now=None):
    """Vidéos au-dessus des seuils, assez récentes."""
    now = now or time.time()
    age_max = float(B.get("heures", 72)) * 3600
    return [v for v in videos
            if v["vues"] >= B["vues_min"] and v["jaime"] >= B["jaime_min"] and v["commentaires"] >= B["commentaires_min"]
            and (not v["date"] or now - v["date"] <= age_max)]


def hashtags_de(texte):
    return [h.lower() for h in re.findall(r"#([\wÀ-ÿ]{2,40})", texte or "")]


def _sans_accents(t):
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def identifiant(titre):
    mots = sorted(set(m for m in re.findall(r"[a-z0-9]{4,}", _sans_accents(titre))))[:8]
    return hashlib.sha1(" ".join(mots).encode()).hexdigest()[:10]


CONSIGNE = """Tu es rédacteur en chef d'une chaîne TikTok française « Buzz et insolite ».
On te donne des vidéos TikTok d'actualité du MONDE ENTIER (en français, en anglais ou autre) qui font énormément de vues.
Regroupe-les par SUJET d'actualité (plusieurs vidéos, même dans des langues différentes, peuvent parler du même événement).
Pour chaque sujet, donne (toujours EN FRANÇAIS, sauf "mots_cles_en") :
- "titre" : le sujet en 8 mots maximum, factuel (ex. « Tempête Ciarán : rafales record en Bretagne », « Tokyo : un robot
  serveur fait le tour du web ») ;
- "resume" : 2 phrases neutres sur ce qu'on sait ;
- "mots_cles" : 3 à 6 mots-clés en français pour chercher des articles de presse sur ce sujet ;
- "mots_cles_en" : les mêmes 3 à 6 mots-clés en anglais (presse et vidéos internationales) ;
- "hashtags" : 3 à 5 hashtags sans espace, en minuscules, qui décrivent ce sujet ;
- "insolite" : note de 0 à 10 (10 = très surprenant / étonnant, 0 = actualité ordinaire) ;
- "videos" : la liste des numéros des vidéos qui parlent de ce sujet.
Ignore les vidéos qui ne sont pas de l'actualité (publicité, jeu, humeur).
Réponds uniquement en JSON : {"sujets": [ ... ]}"""


def grouper(liste, journal=print):
    """Sujets d'actualité formés par l'IA ; sans IA : une vidéo = un sujet."""
    texte = "\n".join(f"{i}. @{v['compte']} — {v['vues']:,} vues, {v['jaime']:,} j'aime, {v['commentaires']:,} commentaires — "
                      f"{v['texte'][:300]}" for i, v in enumerate(liste))
    try:
        d, qui = ia.demander_json(CONSIGNE, texte, temperature=0.2, journal=journal)
        sujets = []
        for s in d.get("sujets") or []:
            nums = [int(n) for n in s.get("videos") or [] if str(n).isdigit() and int(n) < len(liste)]
            if nums and str(s.get("titre") or "").strip():
                sujets.append(dict(titre=str(s["titre"]).strip()[:90], resume=str(s.get("resume") or "")[:400],
                                   mots_cles=[str(m) for m in s.get("mots_cles") or []][:6],
                                   mots_cles_en=[str(m) for m in s.get("mots_cles_en") or []][:6],
                                   hashtags=[re.sub(r"[^\wÀ-ÿ]", "", str(h)).lower() for h in s.get("hashtags") or []][:5],
                                   insolite=max(0, min(10, int(s.get("insolite") or 0))),
                                   videos=[liste[n] for n in dict.fromkeys(nums)]))
        if sujets:
            journal(f"  sujets formés par {qui}")
            return sujets
    except Exception as e:
        journal(f"  regroupement par l'IA impossible ({str(e)[:120]}) : une vidéo = un sujet")
    return [dict(titre=v["texte"][:90] or f"Vidéo de @{v['compte']}", resume=v["texte"][:400], mots_cles=[],
                 hashtags=hashtags_de(v["texte"])[:5], insolite=5, videos=[v]) for v in liste]


def score(s, now=None):
    """Plus c'est vu, récent, commenté et repris par plusieurs comptes, plus le score est haut."""
    now = now or time.time()
    total = 0.0
    for v in s["videos"]:
        heures = max(1.0, (now - v["date"]) / 3600) if v["date"] else 24.0
        total += (v["vues"] + 20 * v["commentaires"] + 5 * v["jaime"]) / heures ** 0.7
    comptes = len({v["compte"] for v in s["videos"]})
    return round(total / 1000 * (1 + 0.3 * (comptes - 1)) * (1 + 0.04 * s.get("insolite", 5)))


def mots_cles(titre):
    vides = {"avec", "pour", "dans", "apres", "après", "devant", "sans", "sous", "contre", "entre", "chez", "plus", "video", "vidéo"}
    return {m for m in re.findall(r"[a-z0-9]{4,}", _sans_accents(titre)) if m not in vides}


def meme_sujet(a, b):
    """Deux titres qui parlent du même sujet (« Policier vole vélo à cycliste à Toulouse » / « … vidéo choque »)."""
    A, B = mots_cles(a), mots_cles(b)
    return bool(A and B) and len(A & B) / min(len(A), len(B)) >= 0.6


def sans_doublons(sujets):
    """Fusionne les sujets en double : le plus fort garde son titre et reçoit les vidéos de l'autre."""
    out = []
    for s in sorted(sujets, key=lambda s: -s.get("score", 0)):
        double = next((o for o in out if o["id"] == s["id"] or meme_sujet(o["titre"], s["titre"])), None)
        if not double:
            out.append(s); continue
        connues = {v.get("id") for v in double.get("videos") or []}
        double.setdefault("videos", []).extend(v for v in s.get("videos") or [] if v.get("id") not in connues)
        for k in ("vues", "jaime", "commentaires"):
            double[k] = sum(v.get(k, 0) for v in double["videos"])
        if s.get("statut") not in (None, "nouveau") and double.get("statut") == "nouveau":
            double["statut"] = s["statut"]                     # déjà traité sous l'autre titre : on ne le refait pas
    return out


def fusionner(anciens, nouveaux):
    """Garde l'état (déjà utilisé, ignoré) des sujets déjà connus ; les sujets de plus de 4 jours partent."""
    connus = {s["id"]: s for s in anciens}
    limite = time.time() - 4 * 86400
    out = {}
    for s in nouveaux:
        vieux = connus.get(s["id"], {})
        s["statut"] = vieux.get("statut", "nouveau")
        s["vu_le"] = vieux.get("vu_le", iso())
        for k in ("video_id",):
            if k in vieux:
                s[k] = vieux[k]
        out[s["id"]] = s
    for sid, s in connus.items():
        if sid not in out and s.get("derniere_vue", 0) >= limite:
            out[sid] = s                                  # sujet encore récent mais sorti des listes : gardé quelques jours
    return sans_doublons(sorted(out.values(), key=lambda s: -s["score"]))


def verifier_liens(sujets, journal=print):
    """Chaque lien de vidéo TikTok est vérifié auprès du service officiel de TikTok (oEmbed) : une vidéo supprimée, privée ou
    réservée est marquée « indisponible » (le site ne la propose plus) ; le pseudo de l'auteur est corrigé s'il a changé ; le
    lecteur officiel (`lecteur`) permet de la voir sur le site sans l'appli ni compte TikTok."""
    import urllib.error
    import urllib.parse
    import urllib.request
    from concurrent.futures import ThreadPoolExecutor

    def un(v):
        if not v.get("id") or not str(v.get("url", "")).startswith("https://www.tiktok.com/"):
            return
        try:
            r = urllib.request.urlopen(urllib.request.Request(
                "https://www.tiktok.com/oembed?url=" + urllib.parse.quote(v["url"], safe=""), headers={"User-Agent": "Mozilla/5.0"}),
                timeout=20)
            d = json.loads(r.read())
            v["indisponible"] = False
            auteur = str(d.get("author_unique_id") or "").strip()
            if auteur and auteur != v.get("compte"):
                v["url"] = f"https://www.tiktok.com/@{auteur}/video/{v['id']}"
        except urllib.error.HTTPError as e:
            if e.code in (400, 403, 404):
                v["indisponible"] = True                          # supprimée, privée ou réservée
        except Exception:
            pass                                                  # TikTok injoignable : on ne conclut rien
        v["lecteur"] = f"https://www.tiktok.com/player/v1/{v['id']}?description=1&music_info=1"
    toutes = [v for s in sujets for v in s.get("videos") or []]
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(un, toutes))
    morts = sum(1 for v in toutes if v.get("indisponible"))
    if morts:
        journal(f"  {morts} vidéo(s) TikTok devenue(s) indisponible(s) : retirée(s) des liens du site")


def relever(journal=print):
    R = reglages(); B = R["buzz"]
    toutes, etat = [], {}
    for pseudo in B["comptes"]:
        p = str(pseudo).strip().lstrip("@")
        if not p:
            continue
        vids = videos_du_compte(p)
        etat[p] = {"ok": bool(vids), "videos": len(vids), "le": iso()}
        journal(f"  @{p} : {len(vids)} vidéos lues" if vids else f"  @{p} : rien lu (compte introuvable ou TikTok refuse)")
        toutes += vids
        time.sleep(1.5)
    retenues = virales(toutes, B)
    journal(f"{len(toutes)} vidéos lues, {len(retenues)} au-dessus des seuils "
            f"({B['vues_min']:,} vues, {B['jaime_min']:,} j'aime, {B['commentaires_min']:,} commentaires)")
    # Toujours au moins 5 sujets (demande de l'auteur du 24/11) : si les seuils en donnent trop peu, les vidéos récentes les
    # plus vues juste en dessous complètent la liste (marquées « sous les seuils »).
    ids = {v["id"] for v in retenues}
    recentes = [v for v in toutes if v["id"] not in ids and (not v["date"] or time.time() - v["date"] <= float(B.get("heures", 72)) * 3600)]
    complement = sorted(recentes, key=lambda v: -(v["vues"] + 20 * v["commentaires"]))[:max(0, 15 - len(retenues))]
    for v in complement:
        v["sous_seuils"] = True
    sujets = grouper(retenues + complement, journal) if retenues or complement else []
    for s in sujets:
        s["sous_seuils"] = all(v.get("sous_seuils") for v in s["videos"])
    now = time.time()
    for s in sujets:
        s["id"] = identifiant(s["titre"])
        s["score"] = score(s, now) // (2 if s.get("sous_seuils") else 1)     # les vrais gros buzz d'abord
        s["derniere_vue"] = now
        s["vues"] = sum(v["vues"] for v in s["videos"])
        s["jaime"] = sum(v["jaime"] for v in s["videos"])
        s["commentaires"] = sum(v["commentaires"] for v in s["videos"])
        tags = [h for v in s["videos"] for h in hashtags_de(v["texte"])]
        s["hashtags_viraux"] = [h for h, _ in sorted({h: tags.count(h) for h in tags}.items(), key=lambda x: -x[1])][:8]
        # Combien de médias différents en parlent (Bing Actualités) : un sujet repris par 3 médias ou plus donne une vidéo
        # sans problème ; les autres passent après (demande de l'auteur du 24/11).
        s["medias"] = sources.nombre_de_medias(s["titre"], s.get("mots_cles") or [], s.get("mots_cles_en") or [])
        if s["medias"] is not None and s["medias"] < 3:
            s["score"] //= 4
        time.sleep(0.5)
    ancien = lire("buzz.json") or {}
    d = {"maj": iso(), "comptes": etat, "lues": len(toutes), "retenues": len(retenues),
         "sujets": fusionner(ancien.get("sujets") or [], sujets)}
    verifier_liens(d["sujets"], journal)                    # anciens sujets compris (vidéos supprimées depuis)
    return d, (len(toutes) == 0 and len(etat) >= 3)


def main():
    from . import depot
    resultat = {}

    def appliquer():
        d, panne = resultat.get("d") or relever_et_garder()
        ecrire("buzz.json", d)
        nouveaux = [s for s in d["sujets"] if s["statut"] == "nouveau"]
        if panne:
            noter("🔥 Buzz : aucun compte TikTok n'a répondu (lecture en panne ou TikTok refuse les robots).", "erreur")
        else:
            noter(f"🔥 Buzz : {len(nouveaux)} sujet(s) au-dessus des seuils" +
                  (f" — en tête : « {nouveaux[0]['titre']} »" if nouveaux else "."))

    def relever_et_garder():
        resultat["d"] = relever()
        return resultat["d"]
    depot.enregistrer(appliquer, f"Buzz du {maintenant():%d/%m %Hh%M}")


if __name__ == "__main__":
    main()
