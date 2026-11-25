"""Règles vérifiées sur CHAQUE vidéo finie (demande de l'auteur du 25/11 : « que ça n'arrive plus »).

Chaque règle vient d'un défaut déjà vu sur une vraie vidéo. `verifier` les passe toutes sur la vidéo entière ; `reparer`
ne corrige QUE les passages fautifs (une phrase, un écran) ; la vidéo est ensuite remontée (seuls les écrans changés sont
refaits) et TOUTES les règles sont revérifiées, pour qu'une correction ne casse rien ailleurs. Une règle encore cassée après
2 tours = problème grave : la vidéo n'est jamais publiée (controle.avant_publication) et la santé de la nuit la refait.

Règles : extraits perdus ; écran sans image ; même passage montré deux fois ; vidéo de plus d'1 minute ; plus de 70 %
d'écrans illustrés ; hashtags (3 à 10, mots entiers) ; tutoiement ; dates et années présentes dans les articles ; caractères
que la police n'affiche pas (« 1☒0 », vidéo CAN r11) ; question finale ; description.
"""
import re

from . import controle, ecrire, ia, nombres

MOIS = "janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre"
_VOUS = re.compile(r"\b(vous|votre|vos|imaginez|découvrez|regardez|dites|pensez-vous|saviez-vous)\b", re.I)


class _Vouvoiement:
    """« vous » adressé au spectateur ; les CITATIONS entre guillemets (« merci pour votre soutien ») ne comptent pas."""
    @staticmethod
    def search(t):
        return _VOUS.search(re.sub(r"«[^»]*»|\"[^\"]*\"", " ", t or ""))


VOUVOIEMENT = _Vouvoiement()


def _texte_articles(articles):
    return " ".join(f"{a.get('titre', '')} {a.get('resume', '')} {a.get('texte', '')}" for a in articles or []).lower()


def dates_douteuses(phrase, articles_bas):
    """Dates complètes (« 18 janvier 2025 ») et années (« 2025 ») de la phrase qui n'apparaissent dans AUCUN article."""
    out = []
    for d in re.findall(rf"\b\d{{1,2}}(?:er)? (?:{MOIS}) \d{{4}}\b", phrase, re.I):
        if d.lower() not in articles_bas:
            out.append(d)
    for an in re.findall(r"\b(?:19|20)\d{2}\b", phrase):
        if an not in articles_bas and not any(an in d for d in out):
            out.append(an)
    return out


def verifier(script, articles, hashtags=None, duree=None, description=None, question=None):
    """Toutes les règles sur la vidéo entière. Renvoie [{regle, ecran (indice ou None), message}] ; [] = tout est bon."""
    ph = script["phrases"]
    pb = []
    if controle.extraits_perdus(script):
        pb.append(dict(regle="extraits_perdus", ecran=None,
                       message=f"{len(controle.extraits_perdus(script))} extrait(s) de l'événement perdu(s)"))
    for i, p in enumerate(ph[:-1]):
        if not p.get("media"):
            pb.append(dict(regle="ecran_vide", ecran=i, message=f"écran {i + 1} sans image (écran de texte)"))
    vus = {}
    for i, p in enumerate(ph[:-1]):
        m = p.get("media") or {}
        if not m or m.get("suite") or m.get("type") == "carte":
            continue
        cle = (controle._base(m), round(float(m.get("debut") or 0), 1))
        if cle in vus:
            pb.append(dict(regle="doublon", ecran=i, message=f"écran {i + 1} : même passage que l'écran {vus[cle] + 1}"))
        else:
            vus[cle] = i
    if duree is not None and duree < 61:
        pb.append(dict(regle="duree", ecran=None, message=f"vidéo de {duree:.0f} s : il faut PLUS d'1 minute"))
    illustres, total = controle.part_illustree(script)
    if total and illustres < 0.7 * total:
        pb.append(dict(regle="illustration", ecran=None, message=f"{illustres} écran(s) illustré(s) sur {total}"))
    if hashtags is not None:
        mauvais = [h for h in hashtags if not re.fullmatch(r"#[\wÀ-ÿ]{3,}", h)]
        if mauvais or not 3 <= len(hashtags) <= 10 or len(set(hashtags)) != len(hashtags):
            pb.append(dict(regle="hashtags", ecran=None, message=f"hashtags incorrects : {' '.join(hashtags)}"))
    for i, p in enumerate(ph):
        if VOUVOIEMENT.search(p.get("ecrit") or ""):
            pb.append(dict(regle="tutoiement", ecran=i, message=f"écran {i + 1} : « vous » au lieu de « tu »"))
    for nom, t in (("question", question), ("description", description)):
        if t and VOUVOIEMENT.search(t):
            pb.append(dict(regle="tutoiement", ecran=None, champ=nom, message=f"{nom} : « vous » au lieu de « tu »"))
    bas = _texte_articles(articles)
    if bas.strip():
        for i, p in enumerate(ph):
            douteuses = dates_douteuses(p.get("ecrit") or "", bas)
            if douteuses:
                pb.append(dict(regle="date", ecran=i, dates=douteuses,
                               message=f"écran {i + 1} : date absente des articles ({', '.join(douteuses)})"))
    from .montage import REMPLACER
    for i, p in enumerate(ph):
        if any(c in REMPLACER for c in (p.get("ecrit") or "") + (p.get("ecran") or "")):
            pb.append(dict(regle="caracteres", ecran=i, message=f"écran {i + 1} : caractère que la police n'affiche pas"))
    fin = (ph[-1].get("ecrit") or "") if ph else ""
    if "?" not in fin and "commentaire" not in fin.lower():
        pb.append(dict(regle="question_finale", ecran=len(ph) - 1, message="la dernière phrase ne pose pas de question"))
    if description is not None and not str(description).strip():
        pb.append(dict(regle="description", ecran=None, message="description vide"))
    return pb


CONSIGNE_TUTOIEMENT = """Réécris cette phrase d'une vidéo TikTok en TUTOYANT le spectateur (« tu », « imagine », « et toi ? »),
sans changer le sens ni les faits, même longueur. Réponds uniquement en JSON : {"ecrit": "phrase (nombres en chiffres)"}"""

CONSIGNE_DATE = """Cette phrase d'une vidéo TikTok contient une date qui n'apparaît dans aucun article. Corrige-la d'après les
extraits d'articles donnés (la date exacte qu'ils citent). Si les articles ne donnent pas la date, retire seulement la date
douteuse. Ne change rien d'autre. Réponds uniquement en JSON : {"ecrit": "phrase corrigée (nombres en chiffres)"}"""


def _contexte(articles, phrase, n=1500):
    """Passages des articles qui parlent de la même chose que la phrase (mots en commun), pour corriger une date."""
    mots = {m for m in re.findall(r"\w{5,}", phrase.lower())}
    morceaux = []
    for a in articles or []:
        for bout in re.split(r"(?<=[.!?])\s+", a.get("texte") or a.get("resume") or ""):
            if len(mots & set(re.findall(r"\w{5,}", bout.lower()))) >= 2:
                morceaux.append(bout)
    return " ".join(morceaux)[:n]


def _sans_date(phrase, douteuses):
    """Dernier recours sûr : la date douteuse est retirée (« le 18 janvier 2025 » → « le 18 janvier »)."""
    for d in douteuses:
        if re.fullmatch(r"(?:19|20)\d{2}", d):
            phrase = re.sub(rf"\s*\b{d}\b", "", phrase)
        else:
            phrase = phrase.replace(d, re.sub(r"\s+\d{4}$", "", d))
    return re.sub(r"\s{2,}", " ", phrase).replace(" ,", ",").strip()


def reparer(script, problemes, articles, R, journal=print, sujet=None):
    """Corrige SEULEMENT les passages fautifs. Renvoie (phrases dont le TEXTE a changé → voix à refaire, écrans dont l'IMAGE
    a changé, champs changés {"hashtags", "question", "description"})."""
    ph = script["phrases"]
    textes, images_, champs = set(), set(), set()
    for pb in problemes:
        r, i = pb["regle"], pb.get("ecran")
        if r == "extraits_perdus":
            avant = [dict(p.get("media") or {}) for p in ph]
            controle.reposer_extraits(script, journal)
            images_ |= {k for k, p in enumerate(ph) if (p.get("media") or {}) != avant[k]}
        elif r in ("ecran_vide", "doublon") and i is not None:
            m = _media_de_secours(script, i)
            if m:
                ph[i]["media"] = m; ph[i].pop("_sig", None); images_.add(i)
                journal(f"  règle « {r} », écran {i + 1} : {('suite de la vidéo d’avant' if m.get('suite') else 'image de l’événement non montrée')}")
        elif r == "tutoiement" and i is not None:
            nouveau = _demander(CONSIGNE_TUTOIEMENT, ph[i]["ecrit"], journal)
            if nouveau and not VOUVOIEMENT.search(nouveau):
                _changer(ph[i], nouveau); textes.add(i)
        elif r == "tutoiement" and pb.get("champ"):
            nouveau = _demander(CONSIGNE_TUTOIEMENT, script.get(pb["champ"]) or "", journal)
            if nouveau and not VOUVOIEMENT.search(nouveau):
                script[pb["champ"]] = nouveau; champs.add(pb["champ"])
        elif r == "date" and i is not None:
            texte = f"PHRASE : {ph[i]['ecrit']}\nDATE DOUTEUSE : {', '.join(pb['dates'])}\nARTICLES : {_contexte(articles, ph[i]['ecrit'])}"
            nouveau = _demander(CONSIGNE_DATE, texte, journal)
            if not nouveau or dates_douteuses(nouveau, _texte_articles(articles)):
                nouveau = _sans_date(ph[i]["ecrit"], pb["dates"])          # sûr : la date douteuse est retirée
            if nouveau != ph[i]["ecrit"]:
                journal(f"  règle « date », écran {i + 1} : « {ph[i]['ecrit']} » → « {nouveau} »")
                _changer(ph[i], nouveau); textes.add(i)
        elif r == "caracteres" and i is not None:            # remplacés à l'affichage aussi : seul l'écran est refait
            from .montage import affichable
            for k in ("ecrit", "ecran"):
                if ph[i].get(k):
                    ph[i][k] = affichable(ph[i][k])
            ph[i].pop("_sig", None); images_.add(i)
        elif r == "question_finale" and i is not None:
            _changer(ph[i], ph[i]["ecrit"].rstrip(" .!") + " ? Dis-le en commentaire !"); textes.add(i)
        elif r == "description":
            script["description"] = f"{script.get('titre', '')} 👀".strip(); champs.add("description")
        elif r == "hashtags":
            champs.add("hashtags")                              # recalculés par l'appelant (ecrire.hashtags, déjà corrigé)
    return textes, images_, champs


def _changer(p, ecrit):
    p["ecrit"] = ecrit
    p["voix"] = nombres.dire_les_nombres(ecrit)
    for k in ("mots", "duree", "_sig"):
        p.pop(k, None)


def _demander(consigne, texte, journal):
    try:
        d, _ = ia.demander_json(consigne, texte, temperature=0.2, journal=journal)
        return str(d.get("ecrit") or "").strip()
    except Exception:
        return ""


def _media_de_secours(script, i):
    """Image pour un écran vide ou en double, SANS doublon : une image de l'événement pas encore montrée (extrait, image
    fixe), sinon la suite de la vraie vidéo de l'écran d'avant."""
    ph = script["phrases"]
    montres = {(controle._base(p.get("media")), round(float((p.get("media") or {}).get("debut") or 0), 1))
               for p in ph if p.get("media")}
    for m in script.get("_citations_toutes") or []:
        if (controle._base(m), round(float(m.get("debut") or 0), 1)) not in montres and m.get("chemin"):
            import os
            if os.path.exists(m["chemin"]):
                return dict(m, suite=False, reelle=True)
    return controle._image_deja_bonne(script, i)


def hashtags_corriges(script, sujet, R):
    return ecrire.hashtags(script, sujet or {}, R)
