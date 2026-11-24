"""Écriture du texte de la vidéo par une IA gratuite, puis vérification par une 2e IA d'un autre fournisseur.

Le texte est écrit UNIQUEMENT à partir des articles trouvés (sources.py). Chaque phrase devient un écran de la vidéo :
"voix" (ce que dit la voix, nombres en lettres), "ecrit" (le même texte avec des chiffres, pour les sous-titres),
"ecran" (gros titre ou chiffre à afficher), "image" (ce qu'il faut montrer, en anglais, pour chercher des vidéos libres).
"""
import re

from . import ia

REGLES_SUJET = """Règles à respecter quel que soit le sujet :
- uniquement des faits présents dans les articles ; si un point n'est pas sûr, ne le dis pas ;
- jamais le nom d'une victime ni d'un mineur ; une personne accusée reste « suspectée » tant qu'elle n'est pas jugée ;
- pas d'insulte, pas de moquerie d'une personne réelle, pas de conseil médical ou financier ;
- ton neutre et étonné, jamais d'opinion politique."""

CONSIGNE = """Tu écris le texte d'une vidéo TikTok de 60 à 75 secondes pour la chaîne française « Buzz et insolite ».
Public : francophones de 15 à 40 ans. Style : rythmé, phrases courtes, langage simple, effet « tu savais ? ».
Reste centré sur le SUJET qui buzze : chaque phrase doit en parler (pas de digression sur un autre thème).
Structure :
1. Accroche choc dans la 1re phrase (moins de 12 mots) qui donne envie de rester.
2. Les faits, du plus étonnant au plus précis (lieu, date, chiffres).
3. Un détail surprenant ou un chiffre fort vers la fin.
4. Dernière phrase : une question au spectateur + « Dis-le en commentaire ! ».
""" + REGLES_SUJET + """
Donne 13 à 17 phrases (20 à 24 pour les 3 actus de la semaine). Pour chaque phrase :
- "voix" : la phrase dite (nombres ÉCRITS EN LETTRES, sigles épelés avec des points, ex. « U.L.R. ») ;
- "ecrit" : la même phrase pour les sous-titres, avec les nombres en chiffres ;
- "ecran" : SEULEMENT pour un chiffre fort, une date, un nom propre ou un mot-clé de la phrase (3 mots max, ex. « 378 JOURS »,
  « LETO », « 99/100 ») ; sinon "" (jamais un mot abstrait comme « contradiction » ou « détails ») ;
- "entite" : la VRAIE personne, le lieu, l'objet, l'organisation ou l'événement dont parle la phrase, écrit comme le titre de
  son article Wikipédia en français (ex. « Emmanuel Macron », « Airbus A320 », « Toulouse », « Grand Theft Auto VI »), ou "" ;
  on montrera SA vraie photo ;
- "image" : ce qu'on VOIT à l'écran pendant cette phrase, en 2 à 4 mots ANGLAIS concrets et filmables, qui collent au sujet
  (personnes, objets, lieux : « rapper microphone stage », « gamer playing console », « storm waves lighthouse ») ;
  jamais de mot abstrait (controversy, details, contradiction, realism).
Aussi :
- "titre" : titre court de la vidéo (6 mots max) ;
- "accroche" : texte de couverture (4 mots max, en majuscules) ;
- "description" : 1 à 2 phrases pour la description TikTok, avec un émoji ;
- "question" : la question à poser en commentaire ;
- "hashtags" : 4 hashtags précis sur le sujet (sans #) ;
- "theme_image" : 2 ou 3 mots ANGLAIS concrets qui illustrent tout le sujet (ex. « video game controller », « Mars habitat ») ;
- "lieu" : le lieu où l'actu se PASSE, cité dans les articles (« Saint-Malo, France »), sinon "" (jamais un siège social) ;
- "coordonnees" : [latitude, longitude] de ce lieu, ou [] ;
- "humeur" : l'ambiance de la musique : "neutre", "tension" (mystère, danger, suspense) ou "joie" (drôle, heureux) ;
- "sources" : les médias utilisés.
Réponds uniquement en JSON : {"titre":…, "accroche":…, "phrases":[{"voix":…,"ecrit":…,"ecran":…,"image":…}], …}"""

CONSIGNE_VERIF = """Tu es vérificateur des faits. On te donne des articles de presse et le texte d'une vidéo TikTok.
Juge SEULEMENT les phrases marquées « À JUGER ». Une phrase est BONNE si :
- son fait est confirmé par les articles (même dit autrement) ;
- ou c'est une transition, une accroche, une question au spectateur, ou une explication générale évidente et sans risque
  (« L'A320 est un avion d'Airbus », « Toulouse est la ville de l'aéronautique »).
Une phrase est à CORRIGER si un fait est faux, exagéré ou absent des articles : donne alors une CORRECTION fidèle aux articles
(même longueur, même style). Ne retire une phrase (correction "") que si aucune correction honnête n'est possible.
Signale aussi toute phrase qui ne respecte pas ces règles :
""" + REGLES_SUJET + """
Ne signale PAS les phrases bonnes. Réponds uniquement en JSON :
{"problemes": [{"phrase": numéro, "raison": "…", "correction": "phrase corrigée (nombres en chiffres) ou vide pour la retirer"}]}"""


def _articles_texte(articles):
    return "\n\n".join(f"[{a['media']}] {a['titre']}\n{a.get('texte') or a.get('resume')}" for a in articles)[:14000]


def nettoyer_hashtag(h):
    return re.sub(r"[^\wÀ-ÿ]", "", str(h)).lower()


FORMATS = {
    "buzz": "",
    "vrai_faux": """
FORMAT « VRAI OU FAUX ? » (il fait énormément commenter) :
- 1re phrase : « Vrai ou faux ? » suivi de l'affirmation la plus étonnante du sujet (vraie OU fausse d'après les articles) ;
- 2e phrase : « Réponds en commentaire avant la fin ! » ;
- puis une phrase « Trois… deux… un… » (ecran : "3… 2… 1…") ;
- puis LA RÉPONSE : une phrase « C'est vrai ! » ou « C'est faux ! » avec le champ "reponse" : "vrai" ou "faux" (une seule phrase
  porte ce champ) ;
- puis l'explication avec les faits, et la question finale habituelle.""",
    "semaine": """
FORMAT « LES 3 ACTUS LES PLUS FOLLES DE LA SEMAINE » : on te donne TROIS sujets. Présente-les du 3e au 1er (le plus fou en
dernier), 4 à 5 phrases chacun ; la 1re phrase de chaque sujet a pour "ecran" « N°3 », « N°2 » puis « N°1 ». Accroche du
début : « Les 3 actus les plus folles de la semaine ! ». Question finale : laquelle est la plus folle ?""",
}


def ecrire(sujet, articles, journal=print, format_="buzz"):
    """Texte de la vidéo (dict) ; lève ia.AucuneIA si aucune IA ne répond."""
    texte = f"SUJET : {sujet['titre']}\nCE QU'ON SAIT : {sujet.get('resume', '')}\n\nARTICLES :\n{_articles_texte(articles)}"
    d, qui = ia.demander_json(CONSIGNE + FORMATS.get(format_, ""), texte, temperature=0.8, max_tokens=6000, journal=journal)
    phrases = [p for p in d.get("phrases") or [] if str(p.get("voix") or "").strip()]
    if len(phrases) < 8:
        raise ValueError(f"texte trop court ({len(phrases)} phrases)")
    for p in phrases:
        p["voix"] = str(p["voix"]).strip()
        p["ecrit"] = str(p.get("ecrit") or p["voix"]).strip()
        p["ecran"] = str(p.get("ecran") or "").strip()[:24]
        p["image"] = str(p.get("image") or sujet["titre"]).strip()[:60]
        p["entite"] = str(p.get("entite") or "").strip()[:80]
        p["reponse"] = str(p.get("reponse") or "").strip().lower() if format_ == "vrai_faux" else ""
        if p["reponse"] not in ("vrai", "faux"):
            p["reponse"] = ""
    if format_ == "vrai_faux" and not any(p["reponse"] for p in phrases):
        for p in phrases:                                # réponse non marquée par l'IA : on la retrouve dans le texte
            m = re.match(r"\W*c'est (vrai|faux)", p["voix"].lower().replace("’", "'"))
            if m:
                p["reponse"] = m.group(1); break
    d["phrases"] = phrases
    d["format"] = format_
    d["humeur"] = d.get("humeur") if d.get("humeur") in ("neutre", "tension", "joie") else "neutre"
    d["auteur_ia"] = qui
    d["hashtags"] = [nettoyer_hashtag(h) for h in d.get("hashtags") or [] if nettoyer_hashtag(h)]
    journal(f"  texte écrit par {qui} : {len(phrases)} phrases")
    return d


def verifier(script, articles, journal=print, seulement=None):
    """2e avis par une IA d'un autre fournisseur. Les phrases non confirmées sont CORRIGÉES (retirées seulement si aucune
    correction n'est possible). `seulement` : numéros des phrases à juger (les autres, déjà vérifiées, ne bougent plus)."""
    from . import nombres
    fourn = script.get("auteur_ia", ":").split(":")[0]
    a_juger = set(range(len(script["phrases"]))) if seulement is None else set(seulement)
    if not a_juger:
        return script
    lignes = "\n".join(f"{i}. {'[À JUGER] ' if i in a_juger else ''}{p['ecrit']}" for i, p in enumerate(script["phrases"]))
    try:
        d, qui = ia.demander_json(CONSIGNE_VERIF, f"ARTICLES :\n{_articles_texte(articles)}\n\nTEXTE :\n{lignes}",
                                  temperature=0.1, exclure=(fourn,), journal=journal)
    except ia.AucuneIA:
        journal("  aucune 2e IA disponible : texte non vérifié")
        script["verifie"] = False
        return script
    retirees = corrigees = 0
    for pb in sorted(d.get("problemes") or [], key=lambda x: -int(x.get("phrase", -1) if str(x.get("phrase", "")).isdigit() else -1)):
        try:
            i = int(pb.get("phrase"))
        except (TypeError, ValueError):
            continue
        if not 0 <= i < len(script["phrases"]) or i not in a_juger:
            continue
        corr = str(pb.get("correction") or "").strip()
        if corr and i != len(script["phrases"]) - 1:
            script["phrases"][i].update(voix=nombres.dire_les_nombres(corr), ecrit=corr); corrigees += 1
        elif i not in (0, len(script["phrases"]) - 1) and not script["phrases"][i].get("reponse"):
            script["phrases"].pop(i); retirees += 1
    script["verifie"] = True
    avant = script.get("verification") or {"corrigees": 0, "retirees": 0, "problemes": []}
    script["verification"] = {"par": qui, "corrigees": avant["corrigees"] + corrigees, "retirees": avant["retirees"] + retirees,
                              "problemes": (avant["problemes"] + [str(p.get("raison", ""))[:160] for p in d.get("problemes") or []])[:10]}
    journal(f"  vérifié par {qui} : {corrigees} phrase(s) corrigée(s), {retirees} retirée(s)")
    return script


def hashtags(script, sujet, R):
    """4 à 6 hashtags : sujet, ceux des vidéos virales du même sujet, puis ceux de la chaîne."""
    nb = int(R["hashtags"].get("nombre", 6))
    tags = [nettoyer_hashtag(h) for h in (script.get("hashtags") or [])[:2]]
    tags += [nettoyer_hashtag(h) for h in (sujet.get("hashtags_viraux") or []) if h not in ("fyp", "pourtoi", "foryou", "viral")][:2]
    tags += [nettoyer_hashtag(h) for h in (sujet.get("hashtags") or [])]
    fixes = [nettoyer_hashtag(h) for h in R["hashtags"].get("fixes") or []]
    garde = []
    for t in tags:
        if t and t not in garde and t not in fixes and len(garde) < nb - len(fixes[:2]):
            garde.append(t)
    garde += [f for f in fixes if f not in garde][:max(0, nb - len(garde))]
    return ["#" + t for t in garde[:nb]]
