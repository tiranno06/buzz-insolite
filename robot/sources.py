"""Articles de presse sur un sujet : c'est de là que viennent les faits de la vidéo (jamais de la vidéo TikTok d'un autre).

Flux RSS publics de médias français et européens + recherche Google Actualités (titres et résumés). Les sites qui refusent les
robots (erreur 401/403) sont simplement laissés de côté : on ne contourne jamais un refus.
"""
import html
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

from .commun import NAVIGATEUR

FLUX = {
    "franceinfo": "https://www.francetvinfo.fr/titres.rss",
    "20 Minutes": "https://www.20minutes.fr/feeds/rss-une.xml",
    "Le Monde": "https://www.lemonde.fr/rss/une.xml",
    "Euronews": "https://fr.euronews.com/rss",
    "Le Figaro": "https://www.lefigaro.fr/rss/figaro_actualites.xml",
    "BFMTV": "https://www.bfmtv.com/rss/news-24-7/",
    "Le Parisien": "https://feeds.leparisien.fr/leparisien/rss",
    "Libération": "https://www.liberation.fr/arc/outboundfeeds/rss-all/?outputType=xml",
    "RTBF": "https://rss.rtbf.be/article/rss/highlight_rtbf_info.xml",
    "RTS": "https://www.rts.ch/info/?format=rss/news",
}
REFUS = set()                              # sites qui ont refusé pendant ce passage


def _ouvrir(url, timeout=25):
    hote = urllib.parse.urlparse(url).netloc
    if hote in REFUS:
        raise PermissionError(hote)
    req = urllib.request.Request(url, headers={"User-Agent": NAVIGATEUR, "Accept-Language": "fr-FR,fr;q=0.9"})
    try:
        return urllib.request.urlopen(req, timeout=timeout).read()
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 451):
            REFUS.add(hote)
        raise


def _propre(t):
    t = html.unescape(re.sub(r"<[^>]+>", " ", t or ""))
    return re.sub(r"\s+", " ", t).strip()


def lire_flux(url):
    """[(titre, lien, résumé)] d'un flux RSS."""
    racine = ET.fromstring(_ouvrir(url))
    out = []
    for it in racine.iter("item"):
        out.append((_propre(it.findtext("title")), (it.findtext("link") or "").strip(), _propre(it.findtext("description"))[:500]))
    return out


def _mots(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return {m for m in re.findall(r"[a-z0-9]{4,}", t)} - {"cette", "dans", "pour", "avec", "plus", "sont", "apres", "avant",
                                                       "leur", "elle", "nous", "vous", "mais", "tout", "comme"}


class _Paragraphes(HTMLParser):
    def __init__(self):
        super().__init__(); self.dans = 0; self.morceaux = []; self.courant = []

    def handle_starttag(self, tag, attrs):
        if tag == "p": self.dans += 1; self.courant = []

    def handle_endtag(self, tag):
        if tag == "p" and self.dans:
            self.dans -= 1
            t = re.sub(r"\s+", " ", "".join(self.courant)).strip()
            if len(t) > 60: self.morceaux.append(t)

    def handle_data(self, data):
        if self.dans: self.courant.append(data)


def texte_article(url, maxi=6000):
    p = _Paragraphes()
    p.feed(_ouvrir(url).decode("utf-8", "ignore"))
    return "\n".join(p.morceaux)[:maxi]


def bing(requete, n=12):
    """[(titre, adresse réelle de l'article, résumé)] de Bing Actualités (le lien du flux contient l'adresse de l'article)."""
    q = urllib.parse.quote(requete)
    out = []
    for titre, lien, resume in lire_flux(f"https://www.bing.com/news/search?q={q}&format=rss&setlang=fr&cc=FR")[:n]:
        reel = urllib.parse.parse_qs(urllib.parse.urlparse(lien).query).get("url", [lien])[0]
        out.append((titre, reel, resume))
    return out


def chercher(sujet, mots_cles=(), maxi=4, journal=print):
    """Articles qui parlent du sujet : [{media, titre, lien, resume, texte}] (les plus proches d'abord)."""
    voulus = _mots(sujet + " " + " ".join(mots_cles))
    candidats = []
    for media, url in FLUX.items():
        try:
            for titre, lien, resume in lire_flux(url):
                commun = len(voulus & _mots(titre + " " + resume))
                if commun >= 2:
                    candidats.append((commun, media, titre, lien, resume))
        except Exception as e:
            journal(f"  flux {media} illisible ({str(e)[:80]})")
    # Google Actualités : titres et résumés de toute la presse (le lien ne mène pas toujours à l'article)
    try:
        q = urllib.parse.quote(" ".join(list(mots_cles)[:4]) or sujet)
        for titre, lien, resume in lire_flux(f"https://news.google.com/rss/search?q={q}&hl=fr&gl=FR&ceid=FR:fr")[:15]:
            commun = len(voulus & _mots(titre))
            if commun >= 2:
                candidats.append((commun - 0.5, "Google Actualités", titre, lien, resume))
    except Exception as e:
        journal(f"  Google Actualités illisible ({str(e)[:80]})")
    # Bing Actualités : toute la presse, avec l'adresse réelle de chaque article (donc son texte complet)
    try:
        for titre, lien, resume in bing(" ".join(list(mots_cles)[:4]) or sujet):
            commun = len(voulus & _mots(titre + " " + resume))
            if commun >= 1:
                candidats.append((commun + 0.5, urllib.parse.urlparse(lien).netloc.replace("www.", ""), titre, lien, resume))
    except Exception as e:
        journal(f"  Bing Actualités illisible ({str(e)[:80]})")
    candidats.sort(key=lambda c: (c[1] == "Google Actualités", -c[0]))   # vrais articles d'abord, Google (titres seuls) en dernier
    out, vus = [], set()
    for _, media, titre, lien, resume in candidats:
        if titre in vus:
            continue
        vus.add(titre)
        texte = ""
        if "news.google.com" not in lien:
            try:
                texte = texte_article(lien)
            except Exception as e:
                journal(f"  article de {media} illisible ({str(e)[:60]}) : son résumé seulement")
        out.append(dict(media=media, titre=titre, lien=lien, resume=resume, texte=texte))
        if sum(1 for a in out if len(a["texte"]) > 400) >= maxi or len(out) >= maxi + 8:
            break
    out.sort(key=lambda a: -len(a["texte"]))                 # articles complets d'abord
    return out[:maxi + 2]


def a_la_une(n=12, journal=print):
    """Sujets de secours quand TikTok ne répond pas : titres à la une des médias (sans chiffres TikTok)."""
    out = []
    for media, url in list(FLUX.items())[:6]:
        try:
            out += [dict(media=media, titre=t, lien=l, resume=r) for t, l, r in lire_flux(url)[:4]]
        except Exception as e:
            journal(f"  flux {media} illisible ({str(e)[:80]})")
    return out[:n]


def contexte_wikipedia(requete, n=2, journal=print):
    """Résumés Wikipédia (en français) des pages qui correspondent au sujet : contexte vérifiable quand la presse ne suffit pas."""
    import json, time
    out = []
    try:
        q = urllib.parse.urlencode({"action": "query", "list": "search", "srsearch": requete, "srlimit": n, "format": "json"})
        for k in range(3):
            try:
                pages = json.loads(_ouvrir(f"https://fr.wikipedia.org/w/api.php?{q}"))["query"]["search"]; break
            except urllib.error.HTTPError as e:
                if e.code != 429 or k == 2: raise
                time.sleep(3 * (k + 1))
        for p in pages:
            q2 = urllib.parse.urlencode({"action": "query", "prop": "extracts", "explaintext": 1, "exintro": 1,
                                         "titles": p["title"], "format": "json"})
            ext = next(iter(json.loads(_ouvrir(f"https://fr.wikipedia.org/w/api.php?{q2}"))["query"]["pages"].values())).get("extract", "")
            if len(ext) > 200:
                out.append(dict(media="Wikipédia (contexte)", titre=p["title"], lien=f"https://fr.wikipedia.org/wiki/{urllib.parse.quote(p['title'])}",
                                resume=ext[:300], texte=ext[:4000]))
    except Exception as e:
        journal(f"  contexte Wikipédia illisible ({str(e)[:80]})")
    return out


def chercher_large(sujet, mots_cles=(), videos=(), journal=print, minimum=2500):
    """Comme `chercher`, mais n'abandonne jamais (demande de l'auteur du 24/11 : une vidéo commencée va jusqu'au bout) :
    si les articles sont trop maigres, autres recherches (titre seul, mots-clés deux par deux), puis contexte Wikipédia, puis
    descriptions des vidéos TikTok virales du sujet (présentées comme telles)."""
    total = lambda L: sum(len(a.get("texte") or a.get("resume") or "") for a in L)
    articles = chercher(sujet, mots_cles, journal=journal)
    essais = [[]] + [list(mots_cles)[k:k + 2] for k in range(0, len(mots_cles), 2)]
    for mots in essais:
        if total(articles) >= minimum:
            break
        vus = {a["titre"] for a in articles}
        articles += [a for a in chercher(sujet, mots, maxi=3, journal=journal) if a["titre"] not in vus]
    if total(articles) < minimum:
        articles += contexte_wikipedia(" ".join(list(mots_cles)[:3]) or sujet, journal=journal)
    descriptions = [f"@{v.get('compte', '')} : {v.get('texte', '')}" for v in videos if v.get("texte")]
    if total(articles) < minimum and descriptions:
        articles.append(dict(media="Descriptions des vidéos TikTok virales", titre=sujet, lien="", resume=descriptions[0][:300],
                             texte="\n".join(descriptions)[:3000]))
    if not articles:
        articles.append(dict(media="Sujet du buzz", titre=sujet, lien="", resume=sujet, texte=sujet))
    return articles
