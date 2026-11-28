"""FAMILLES DE SUJETS et TRAMES DE RÉCIT (28/11, demande de l'auteur : « une liste complète de règles appliquées
automatiquement à toutes les futures vidéos, même des événements totalement différents, avec d'autres scènes, une autre
narration, une autre histoire »).

Avant : le robot ne savait vraiment raconter que les accidents et les catastrophes (reconstitution 3D) ; tout le reste
devenait une carte avec des encadrés. Maintenant, chaque sujet est rangé dans une FAMILLE (accident, crime, sauvetage,
animal, record, science, procès, décision, économie…). Chaque famille a :
  - une TRAME de récit en 5 temps (accroche → contexte → déroulé → conséquences → question), écrite pour l'IA qui rédige ;
  - un TON (drame, neutre, léger, épique) qui choisit l'étiquette en haut de l'écran et la musique ;
  - une RECETTE d'images : reconstitution 3D (événement physique) ou scènes d'explication (échelle, avant / après,
    courbe, objet en vitrine, chiffres, carte) pour les sujets sans action à reconstituer.

La famille vient du texte (`famille_du_texte`), et le type d'événement extrait par l'IA ne la contredit jamais sans
raison : si l'IA dit « autre » ou un type sans rapport avec les mots du texte, ce sont les mots qui l'emportent.
"""
import re

# récits : les 5 temps de chaque modèle d'histoire
RECITS = {
    "minute": ("le moment le plus fort, tout de suite (« 8 000 mètres en une minute. »)",
               "le contexte : où, quand, qui (lieu et jour dans la même phrase)",
               "le déroulé DANS L'ORDRE, étape par étape, avec les heures précises des articles en début de phrase",
               "les conséquences : bilan, secours, enquête, ce qui se passe maintenant",
               "une question au spectateur + « Dis-le en commentaire ! »"),
    "avant_apres": ("le changement en une phrase choc (« À partir de lundi, c'est fini. »)",
                    "AVANT : comment c'était jusqu'ici (un fait concret, un chiffre)",
                    "ce qui change exactement, qui l'a décidé, à partir de quand",
                    "APRÈS : ce que ça change concrètement pour toi ou pour les gens concernés",
                    "une question au spectateur (« pour ou contre ? ») + « Dis-le en commentaire ! »"),
    "enquete": ("le mystère ou la question que tout le monde se pose",
                "ce qu'on sait déjà : lieu, date, personnes concernées (sans nom de victime ni de mineur)",
                "les indices et les étapes, dans l'ordre où ils ont été découverts",
                "ce qu'on ne sait pas encore, ce qui va se passer ensuite (la personne mise en cause reste « suspectée »)",
                "une question au spectateur + « Dis-le en commentaire ! »"),
    "portrait": ("le détail le plus fou sur ce personnage (personne, animal, objet)",
                 "qui c'est : nom (sauf victime ou mineur), âge, lieu, ce qu'il fait",
                 "ce qu'il a fait, raconté comme une petite histoire avec un début et une fin",
                 "pourquoi ça buzze : les réactions, les chiffres de vues, ce qui étonne",
                 "une question au spectateur + « Dis-le en commentaire ! »"),
    "chiffre_fou": ("le chiffre étonnant, tout de suite (« 4,2 milliards. »)",
                    "à quoi correspond ce chiffre : qui, quoi, où",
                    "une COMPARAISON concrète pour se rendre compte (« c'est 3 fois la tour Eiffel », « autant que la Belgique »)",
                    "pourquoi c'est important ou ce que ça change",
                    "une question au spectateur + « Dis-le en commentaire ! »"),
    "explication": ("la découverte ou la nouveauté en une phrase choc",
                    "de quoi il s'agit, en mots simples (comme à un ami de 15 ans)",
                    "comment ça marche ou comment on l'a découvert, étape par étape, avec une comparaison concrète",
                    "ce que ça change pour nous, la suite",
                    "une question au spectateur + « Dis-le en commentaire ! »"),
}

# famille → mots du texte, récit, ton, étiquette, musique, recette d'images ("3d" = reconstitution, "explication" sinon)
# (l'ordre compte : la 1re famille dont les mots apparaissent l'emporte ; les drames physiques d'abord)
FAMILLES = {
    "catastrophe": dict(mots=r"s[ée]isme|tremblement de terre|inond|crue|ouragan|cyclone|tornade|temp[êe]te|typhon|tsunami|"
                             r"[ée]ruption|glissement de terrain|feux? de for[êe]t|incendie de for[êe]t|avalanche|canicule|vigilance",
                        recit="minute", ton="drame", etiquette="ALERTE", humeur="tension", images="3d"),
    "accident": dict(mots=r"accident|collision|carambolage|percut|renvers|crash|s'est [ée]cras|naufrag|chavir|d[ée]raill",
                     recit="minute", ton="drame", etiquette="ACTUALITÉ", humeur="tension", images="3d"),
    "incendie_explosion": dict(mots=r"explos|d[ée]flagration|d[ée]tonation|incendi|en feu|brasier|flammes",
                               recit="minute", ton="drame", etiquette="ACTUALITÉ", humeur="tension", images="3d"),
    "sauvetage": dict(mots=r"sauv[ée]|secouru|rescap|h[ée]ro[sï]|sauvetage|tir[ée] d'affaire|r[ée]chapp",
                      recit="minute", ton="epique", etiquette="SAUVETAGE", humeur="epique", images="3d"),
    "crime": dict(mots=r"braquage|braqu|cambriol|vol[ée]? (?:de|d'|à)|vol\b|voleur|agress|fusillade|attaque au couteau|"
                       r"meurtr|tu[ée] par balle|enl[èe]v|kidnapp|escroc|arnaque|trafic de|dealer|fraude",
                  recit="enquete", ton="drame", etiquette="FAIT DIVERS", humeur="tension", images="3d"),
    "proces": dict(mots=r"proc[èe]s|tribunal|condamn|jug[ée]|verdict|peine de|prison ferme|cour d'assises|mis en examen|plaid",
                   recit="enquete", ton="neutre", etiquette="JUSTICE", humeur="tension", images="explication"),
    "disparition": dict(mots=r"dispar|introuvable|avis de recherche|recherches? (?:se poursuiv|pour retrouver|activement)|toujours pas retrouv",
                        recit="enquete", ton="drame", etiquette="ALERTE", humeur="tension", images="explication"),
    "manifestation": dict(mots=r"manifest|cort[èe]ge|[ée]meute|gr[èe]ve|rassemblement|blocage",
                          recit="minute", ton="neutre", etiquette="ACTUALITÉ", humeur="tension", images="3d"),
    "decouverte": dict(mots=r"d[ée]couv|tr[ée]sor|fossile|arch[ée]olog|[ée]pave|vestige|tombe|momie|dinosaure",
                       recit="enquete", ton="neutre", etiquette="DÉCOUVERTE", humeur="tension", images="explication"),
    "science_espace": dict(mots=r"nasa|esa\b|espace|fus[ée]e|plan[èe]te|galaxie|ast[ée]ro[ïi]de|com[èe]te|satellite|"
                                r"t[ée]lescope|scientifi|chercheurs?|[ée]tude|physique|climat|oc[ée]an",
                           recit="explication", ton="neutre", etiquette="SCIENCE", humeur="epique", images="explication"),
    "sante": dict(mots=r"sant[ée]|m[ée]decin|h[ôo]pital|virus|[ée]pid[ée]mie|vaccin|maladie|cancer|patient|traitement",
                  recit="explication", ton="neutre", etiquette="SANTÉ", humeur="neutre", images="explication"),
    "record": dict(mots=r"record|le plus (?:grand|petit|vieux|long|rapide|cher|haut)|la plus (?:grande|petite|vieille|longue|rapide|ch[èe]re|haute)|"
                        r"jamais vu|historique|premi[èe]re fois|guinness|exploit",
                   recit="chiffre_fou", ton="epique", etiquette="RECORD", humeur="epique", images="explication"),
    "sport": dict(mots=r"match|but\b|buts\b|finale|champion|coupe du monde|ligue|joueur|[ée]quipe de|m[ée]daille|jeux olympiques|"
                       r"tournoi|sprint|marathon|football|rugby|tennis|basket|f1|formule 1",
                  recit="minute", ton="epique", etiquette="SPORT", humeur="epique", images="explication"),
    "economie": dict(mots=r"prix|euros?|dollars?|salaire|faillite|bourse|entreprise|licenci|inflation|imp[ôo]t|taxe|milliard",
                     recit="chiffre_fou", ton="neutre", etiquette="ÉCONOMIE", humeur="neutre", images="explication"),
    "decision": dict(mots=r"loi\b|interdi|d[ée]cret|gouvernement|ministre|vote|parlement|r[ée]forme|obligatoire|amende|r[èe]gle",
                     recit="avant_apres", ton="neutre", etiquette="ÇA CHANGE", humeur="neutre", images="explication"),
    "techno": dict(mots=r"intelligence artificielle|\bia\b|robot|appli|smartphone|iphone|internet|cyber|piratage|hacker|"
                        r"r[ée]seau social|tiktok|algorithme|jeu vid[ée]o",
                   recit="explication", ton="neutre", etiquette="TECH", humeur="neutre", images="explication"),
    "animal": dict(mots=r"chien|chat|ours|requin|baleine|dauphin|oiseau|cheval|vache|serpent|crocodile|lion|tigre|singe|"
                         r"loup|renard|animal|animaux|chiot|chaton|pingouin|manchot|aigle|poisson",
                   recit="portrait", ton="leger", etiquette="ANIMAUX", humeur="joie", images="explication"),
    "celebrite": dict(mots=r"star|chanteu|acteur|actrice|influenceu|rappeu|youtubeu|c[ée]l[ée]brit|concert|film|s[ée]rie",
                      recit="portrait", ton="leger", etiquette="PEOPLE", humeur="joie", images="explication"),
    "insolite": dict(mots=r"", recit="portrait", ton="leger", etiquette="INSOLITE", humeur="joie", images="explication"),
}
# type d'événement extrait par l'IA (gabarits.TYPES_EVENEMENT) → famille
TYPE_VERS_FAMILLE = {"accident_route": "accident", "crash_avion": "accident", "naufrage": "accident", "deraillement": "accident",
                     "incendie": "incendie_explosion", "explosion": "incendie_explosion", "manifestation": "manifestation",
                     "meteo": "catastrophe", "catastrophe_naturelle": "catastrophe", "inondation": "catastrophe",
                     "seisme": "catastrophe", "feu_foret": "catastrophe", "tempete": "catastrophe",
                     "police_justice": "proces", "politique": "decision"}
# un drame (des morts, des victimes) : ton grave quelle que soit la famille (jamais de musique joyeuse sur un deuil)
DRAME = r"\bmorts?\b|\bmortes?\b|tu[ée]s?\b|tu[ée]es\b|d[ée]c[èe]s|d[ée]c[ée]d|victimes?|bless[ée]s? graves?|p[ée]ri|noy[ée]"


def famille_du_texte(texte):
    """Famille d'un sujet d'après ses mots. Plus de mots qui correspondent = plus de poids ; à égalité, l'ordre de FAMILLES."""
    t = (texte or "").lower()
    scores = []
    for k, (nom, f) in enumerate(FAMILLES.items()):
        if not f["mots"]:
            continue
        n = len(re.findall(f["mots"], t))
        if n:
            scores.append((n + (0.5 if f["images"] == "3d" else 0), -k, nom))
    return max(scores)[2] if scores else "insolite"


def famille_de(script_ou_sujet, type_ia=None):
    """Famille d'une vidéo (texte écrit, ou sujet + résumé). Le type extrait par l'IA ne l'emporte que s'il est cohérent."""
    d = script_ou_sujet or {}
    texte = " ".join([str(d.get("titre") or ""), str(d.get("resume") or "")] +
                     [str(p.get("ecrit") or "") for p in d.get("phrases") or [] if isinstance(p, dict)])
    par_mots = famille_du_texte(texte)
    par_ia = TYPE_VERS_FAMILLE.get(type_ia or "")
    if par_ia and (par_ia == par_mots or re.search(FAMILLES[par_ia]["mots"], texte.lower())):
        return par_ia
    return par_mots


def info(famille):
    return FAMILLES.get(famille) or FAMILLES["insolite"]


def est_drame(texte):
    return bool(re.search(DRAME, (texte or "").lower()))


def consigne(famille):
    """Paragraphe ajouté à la consigne d'écriture : la trame de récit de la famille, en 5 temps."""
    f = info(famille)
    temps = RECITS[f["recit"]]
    ton = {"drame": "grave et sobre (jamais de blague, jamais « incroyable » sur un drame)",
           "neutre": "clair et étonné, comme quand on explique une info surprenante à un ami",
           "leger": "léger et amusé (on peut sourire, jamais se moquer d'une personne réelle)",
           "epique": "enthousiaste, on sent l'exploit"}[f["ton"]]
    return ("\nTRAME DE CE SUJET (famille « " + famille + " », récit « " + f["recit"] + " ») : raconte en 5 temps, dans cet ordre :\n" +
            "\n".join(f"{i + 1}. {t}" for i, t in enumerate(temps)) +
            f"\nTon : {ton}. Ne force jamais la trame : si les articles ne donnent pas un temps, passe au suivant.\n")


def humeur(famille, texte, humeur_ia=None):
    """Musique : celle de la famille, sauf drame (toujours « emotion » ou « tension ») ; l'IA garde la main si elle est cohérente."""
    f = info(famille)
    if est_drame(texte):
        return humeur_ia if humeur_ia in ("tension", "emotion") else "tension"
    if f["ton"] == "drame":
        return humeur_ia if humeur_ia in ("tension", "emotion", "neutre") else f["humeur"]
    return humeur_ia if humeur_ia in ("neutre", "tension", "joie", "epique", "emotion") else f["humeur"]


def etiquette(famille, texte):
    """Étiquette en haut de l'écran : celle de la famille ; un drame (morts, victimes) est toujours « ACTUALITÉ » au minimum."""
    e = info(famille)["etiquette"]
    if est_drame(texte) and e in ("INSOLITE", "ANIMAUX", "PEOPLE", "RECORD", "TECH", "SPORT"):
        return "ACTUALITÉ"
    return e


# références connues pour les scènes « échelle » (« c'est 3 fois la tour Eiffel ») : c'est le ROBOT qui donne leur taille,
# jamais l'IA (elle choisit seulement la référence ; la valeur du sujet doit venir du texte ou des articles)
REFERENCES = {
    # hauteurs / longueurs (m)
    "humain": dict(nom="un adulte", valeur=1.75, unite="m", emoji="🧍"),
    "girafe": dict(nom="une girafe", valeur=5.5, unite="m", emoji="🦒"),
    "bus": dict(nom="un bus", valeur=12, unite="m", emoji="🚌"),
    "immeuble": dict(nom="un immeuble", valeur=30, unite="m", emoji="🏢"),
    "statue_liberte": dict(nom="statue de la Liberté", valeur=93, unite="m", emoji="🗽"),
    "terrain_foot": dict(nom="terrain de foot", valeur=105, unite="m", emoji="⚽"),
    "tour_eiffel": dict(nom="tour Eiffel", valeur=330, unite="m", emoji="🗼"),
    "burj_khalifa": dict(nom="Burj Khalifa", valeur=828, unite="m", emoji="🏙️"),
    "everest": dict(nom="l'Everest", valeur=8849, unite="m", emoji="🏔️"),
    # masses (tonnes)
    "voiture_t": dict(nom="une voiture", valeur=1.5, unite="t", emoji="🚗"),
    "elephant": dict(nom="un éléphant", valeur=6, unite="t", emoji="🐘"),
    "baleine_bleue": dict(nom="baleine bleue", valeur=150, unite="t", emoji="🐋"),
    "tour_eiffel_t": dict(nom="tour Eiffel", valeur=10100, unite="t", emoji="🗼"),
    # surfaces (km²)
    "paris": dict(nom="Paris", valeur=105, unite="km²", emoji="🗺️"),
    "corse": dict(nom="la Corse", valeur=8680, unite="km²", emoji="🏝️"),
    "belgique": dict(nom="la Belgique", valeur=30689, unite="km²", emoji="🇧🇪"),
    "france": dict(nom="la France", valeur=551695, unite="km²", emoji="🇫🇷"),
    # vitesses (km/h)
    "guepard": dict(nom="un guépard", valeur=110, unite="km/h", emoji="🐆"),
    "voiture_autoroute": dict(nom="sur autoroute", valeur=130, unite="km/h", emoji="🚗"),
    "tgv": dict(nom="un TGV", valeur=320, unite="km/h", emoji="🚄"),
    "avion_ligne": dict(nom="avion de ligne", valeur=900, unite="km/h", emoji="✈️"),
}
