"""Contrôle qualité en 4 niveaux (+ contrôle avant publication), demandé par l'auteur le 24/11/2026.

1. TEXTE (avant toute fabrication) : faits vérifiés par une 2e IA (ecrire.verifier) + règles : nombres écrits en lettres pour
   la voix, accroche courte, question finale, titres d'écran courts, phrases trop longues, doublons, durée d'au moins 1 minute.
   Seules les phrases en défaut sont réécrites (IA), puis revérifiées.
2. VOIX (phrase par phrase, voix.preparer) : mots compris par Whisper, durée normale pour le nombre de mots (une voix qui
   « bafouille » parle trop longtemps). Seule la phrase fautive est refaite.
3. IMAGES (écran par écran) : écran noir, uni ou flou (mesuré), puis une IA qui VOIT l'image juge si elle colle à la phrase,
   sans texte incrusté en langue étrangère (un logo n'est pas un défaut : choix de l'auteur du 24/11). Seul l'écran fautif reçoit une nouvelle image (sinon un écran de texte).
4. VIDÉO FINIE : format, durée, son, écrans noirs ; sous-titres réécoutés (Whisper sur la vidéo finie, phrase par phrase) ;
   l'IA regarde une image de chaque écran terminé (titres coupés, textes qui se chevauchent, image hors sujet). Seuls les
   écrans fautifs sont refaits (montage.monter garde les autres), puis la vidéo est réassemblée et recontrôlée (2 tours).
5. AVANT PUBLICATION (publication_auto, commande) : vidéo en ligne, description et hashtags, aucun défaut grave restant.

Chaque vidéo a un bulletin (problèmes trouvés, corrigés ou non) et une note de confiance /100. Un défaut grave non corrigé =
statut « a_verifier » : jamais publiée automatiquement.
"""
import json
import os
import re
import shutil
import subprocess
import urllib.request

from . import ia, images, nombres
from . import voix as V

NIVEAUX = ("texte", "voix", "images", "video", "publication")


class Bulletin:
    """Problèmes trouvés. Un problème reste OUVERT jusqu'à ce que la revérification du passage le trouve réglé ;
    la vidéo n'est gardée qu'avec zéro problème ouvert (consigne de l'auteur du 24/11)."""
    def __init__(self):
        self.lignes = []; self.sautes = []

    def ouvrir(self, niveau, probleme, ecran=None, gravite="moyen"):
        for l in self.lignes:                         # même passage, même niveau : on compte un essai de plus
            if not l["corrige"] and l["niveau"] == niveau and l["ecran"] == ecran:
                l.update(probleme=str(probleme)[:200], essais=l.get("essais", 1) + 1)
                return l
        l = dict(niveau=niveau, ecran=ecran, gravite=gravite, probleme=str(probleme)[:200], corrige=False, essais=1)
        self.lignes.append(l)
        return l

    def fermer(self, niveau, ecran, solution=""):
        for l in self.lignes:
            if not l["corrige"] and l["niveau"] == niveau and l["ecran"] == ecran:
                l.update(corrige=True, solution=solution or l.get("solution", ""))

    def ajouter(self, niveau, probleme, ecran=None, gravite="moyen", corrige=False, solution=""):
        """Problème trouvé et (si corrige) déjà réglé sur place."""
        self.lignes.append(dict(niveau=niveau, ecran=ecran, gravite=gravite, probleme=str(probleme)[:200], corrige=corrige,
                                essais=1, solution=solution))

    def ouverts(self, niveau=None):
        return [l for l in self.lignes if not l["corrige"] and (niveau is None or l["niveau"] == niveau)]

    def saute(self, controle):
        if controle not in self.sautes:
            self.sautes.append(controle)

    def restants(self, gravite=None):
        return [l for l in self.ouverts() if gravite is None or l["gravite"] == gravite]

    def note(self):
        """100 = aucun problème restant et tous les contrôles faits."""
        return max(0, 100 - sum(25 if l["gravite"] == "grave" else 10 for l in self.ouverts()) - 10 * len(self.sautes))

    def resume(self):
        return dict(note=self.note(), lignes=self.lignes, sautes=self.sautes,
                    corriges=sum(1 for l in self.lignes if l["corrige"]), restants=len(self.ouverts()),
                    graves_restants=len(self.ouverts()) + len(self.sautes))     # tout reste bloque la publication auto


# ------------------------------------------------------------------ 1. texte
CONSIGNE_REECRIRE = """Tu corriges certaines phrases d'un texte de vidéo TikTok (chaîne « Buzz et insolite »). On te donne le
texte complet numéroté, les articles de presse, et pour chaque phrase à corriger le problème. Réécris SEULEMENT ces phrases,
avec des faits présents dans les articles. Pour chacune : "voix" (nombres en lettres), "ecrit" (nombres en chiffres),
"ecran" (chiffre fort ou nom, 3 mots max, ou ""), "image" (2 à 4 mots anglais concrets et filmables), "entite" (la vraie
personne / le lieu / l'objet dont parle la phrase, comme le titre de son article Wikipédia, ou "").
Si on te demande d'AJOUTER des phrases, donne-les dans "ajouts" (même format), à placer avant la question finale.
Réponds uniquement en JSON : {"phrases": {"numéro": {...}}, "ajouts": [{...}]}"""


def _mots(t):
    return len(re.findall(r"\w+", t))


def duree_estimee(phrases, mots_par_seconde=3.5):      # mesuré sur la vidéo GTA VI du 24/11 (voix Chatterbox)
    return sum(_mots(p["voix"]) for p in phrases) / mots_par_seconde + 0.18 * len(phrases) + 1.6


def regles_texte(script):
    """Problèmes du texte : [(n° de phrase ou None, problème, corrigeable sans IA)]."""
    ph = script["phrases"]; pb = []
    vus = set()
    for i, p in enumerate(ph):
        if re.search(r"\d", p["voix"]):
            pb.append((i, "chiffres dans la phrase dite (la voix les lit mal)", True))
        cle = re.sub(r"\W", "", p["ecrit"].lower())
        if cle in vus:
            pb.append((i, "phrase en double", True))
        vus.add(cle)
        if len(p.get("ecran") or "") > 24 or len((p.get("ecran") or "").split()) > 4:
            pb.append((i, "titre d'écran trop long", True))
        if _mots(p["voix"]) > 32:
            pb.append((i, "phrase trop longue (plus de 32 mots)", False))
    if ph and _mots(ph[0]["voix"]) > 15:
        pb.append((0, "accroche trop longue (plus de 15 mots) : on perd le spectateur", False))
    if ph and "?" not in ph[-1]["ecrit"]:
        pb.append((len(ph) - 1, "la dernière phrase n'est pas une question au spectateur", False))
    if duree_estimee(ph) < 62:
        pb.append((None, f"texte trop court (environ {duree_estimee(ph):.0f} s, il faut plus d'1 minute)", False))
    return pb


def corriger_sans_ia(script, pb):
    ph = script["phrases"]
    for i, probleme, simple in sorted(pb, key=lambda x: -(x[0] or 0)):
        if not simple or i is None:
            continue
        if probleme.startswith("chiffres"):
            ph[i]["voix"] = nombres.dire_les_nombres(ph[i]["voix"])
        elif probleme == "titre d'écran trop long":
            ph[i]["ecran"] = " ".join(ph[i]["ecran"].split()[:3])[:24]
        elif probleme == "phrase en double" and 0 < i < len(ph) - 1:
            ph.pop(i)


def couper_en_deux(phrase):
    """Coupe une phrase trop longue à la virgule la plus proche du milieu (sinon au milieu) : deux phrases."""
    mots = phrase["voix"].split(); ecrits = phrase["ecrit"].split()
    def coupe(m):
        virgules = [k for k, x in enumerate(m[:-1]) if x.endswith(",")]
        k = min(virgules, key=lambda k: abs(k - len(m) / 2)) + 1 if virgules else len(m) // 2
        return " ".join(m[:k]).rstrip(",") + ".", " ".join(m[k:])
    v1, v2 = coupe(mots); e1, e2 = coupe(ecrits)
    return [dict(phrase, voix=v1, ecrit=e1), dict(phrase, voix=v2[:1].upper() + v2[1:], ecrit=e2[:1].upper() + e2[1:], ecran="")]


QUESTION_TYPE = "Et toi, tu en penses quoi ? Dis-le en commentaire !"


def solutions_garanties(script, pb):
    """Dernier recours sans IA, qui règle à coup sûr chaque problème (sauf « trop court »)."""
    ph = script["phrases"]
    for i, probleme, _ in sorted(pb, key=lambda x: -(x[0] if x[0] is not None else -1)):
        if i is None:
            continue
        if probleme.startswith("la dernière phrase"):
            q = str(script.get("question") or "").strip()
            q = q if q.endswith("?") else QUESTION_TYPE
            ph.append(dict(voix=nombres.dire_les_nombres(q), ecrit=q, ecran="", image=ph[-1].get("image", "")))
        elif probleme.startswith(("phrase trop longue", "accroche trop longue")) and i < len(ph):
            ph[i:i + 1] = couper_en_deux(ph[i])


def controle_texte(script, articles, B, journal=print, tours=3):
    """Niveau 1. Corrige le texte sur place jusqu'à ce qu'AUCUNE règle ne soit enfreinte : d'abord les corrections simples,
    puis l'IA réécrit seulement les phrases en défaut, puis des solutions sans IA qui marchent toujours. Un texte qui reste
    trop court (pas assez de faits dans les articles) : LookupError = sujet abandonné, jamais une vidéo trop courte."""
    for tour in range(tours + 1):
        pb = regles_texte(script)
        if not pb:
            break
        corriger_sans_ia(script, pb)
        for i, probleme, simple in pb:
            if simple:
                B.ajouter("texte", probleme, i, "info", corrige=True, solution="corrigé automatiquement")
        dur = [x for x in pb if not x[2]]
        if not dur:
            continue
        for i, probleme, _ in dur:
            B.ouvrir("texte", probleme, i)
        if tour == tours:                                  # l'IA n'a pas suffi : solutions qui marchent à coup sûr
            solutions_garanties(script, dur)
            continue
        ph = script["phrases"]
        texte = "TEXTE :\n" + "\n".join(f"{k}. {p['ecrit']}" for k, p in enumerate(ph))
        texte += "\n\nÀ CORRIGER :\n" + "\n".join(f"- phrase {i} : {probleme}" if i is not None else
                                                  f"- AJOUTER 2 à 4 phrases de faits : {probleme}" for i, probleme, _ in dur)
        texte += "\n\nARTICLES :\n" + "\n\n".join(f"[{a['media']}] {a['titre']}\n{a.get('texte') or a.get('resume')}"
                                                  for a in articles)[:12000]
        try:
            d, qui = ia.demander_json(CONSIGNE_REECRIRE, texte, temperature=0.5, journal=journal)
        except ia.AucuneIA:
            B.saute("réécriture du texte par l'IA (aucune IA disponible)")
            solutions_garanties(script, dur)
            continue
        refaites = 0
        signalees = {i for i, _, _ in dur if i is not None}
        for k, nouv in (d.get("phrases") or {}).items():
            try:
                k = int(k)
            except ValueError:
                continue
            if k in signalees and 0 <= k < len(ph) and str(nouv.get("voix") or "").strip() \
                    and not phrase_absurde(str(nouv.get("ecrit") or nouv["voix"])):   # jamais une phrase saine ni absurde
                garde = {c: ph[k][c] for c in ("reponse",) if ph[k].get(c)}
                ph[k] = dict(voix=nombres.dire_les_nombres(str(nouv["voix"])), ecrit=str(nouv.get("ecrit") or nouv["voix"]),
                             ecran=str(nouv.get("ecran") or "")[:24], image=str(nouv.get("image") or ph[k].get("image", "")), **garde)
                refaites += 1
        for a in d.get("ajouts") or []:
            # phrase ajoutée par l'IA : une VRAIE phrase seulement (25/11, IA de secours saturée : « 74 », « 2 », « 2026 »
            # ajoutés comme phrases → vidéos à 0/100)
            if isinstance(a, dict) and str(a.get("voix") or "").strip() and not phrase_absurde(str(a.get("ecrit") or a["voix"])) \
                    and len(re.findall(r"[A-Za-zÀ-ÿ]{2,}", str(a.get("ecrit") or a["voix"]))) >= 5:
                ph.insert(len(ph) - 1, dict(voix=nombres.dire_les_nombres(str(a["voix"])), ecrit=str(a.get("ecrit") or a["voix"]),
                                            ecran=str(a.get("ecran") or "")[:24], image=str(a.get("image") or script.get("theme_image", ""))))
                refaites += 1
        journal(f"  contrôle du texte (tour {tour + 1}) : {len(pb)} problème(s), {refaites} phrase(s) réécrite(s) par {qui}")
    restant = regles_texte(script)
    if any(i is None for i, _, _ in restant):              # trop court : la fabrication complétera avec du contexte
        return script
    for l in B.ouverts("texte"):                            # tout est réglé : les problèmes ouverts sont fermés
        B.fermer("texte", l["ecran"], "phrase réécrite et revérifiée")
    return script


# ------------------------------------------------------------------ 3. images
def _image_de(media, dossier, nom, instant=1.0):
    """Une image .jpg (512 px de large) du média, pour la montrer à l'IA."""
    sortie = os.path.join(dossier, nom)
    entree = media["chemin"]
    if not os.path.exists(entree):
        raise OSError(f"{os.path.basename(entree)} : fichier absent")
    if media["type"] == "photo":                         # photo : Pillow directement (ffmpeg n'en tirait rien sur GitHub, 25/11)
        from PIL import Image
        with Image.open(entree) as im:
            im = im.convert("RGB"); im.thumbnail((512, 2048)); im.save(sortie, "JPEG", quality=85)
        return sortie
    t = media.get("debut", 0) + instant
    erreur = ""
    for essai_t in (t, 0):                               # vidéo plus courte que prévu : on prend sa toute première image
        if os.path.exists(sortie):
            os.remove(sortie)
        r = subprocess.run(["ffmpeg", "-y", "-v", "warning", "-ss", str(essai_t), "-i", entree, "-frames:v", "1",
                            "-vf", "scale=512:-2", "-q:v", "4", sortie], check=False, capture_output=True, text=True)
        if os.path.exists(sortie) and os.path.getsize(sortie) > 0:
            return sortie
        erreur = (r.stderr or "").strip().splitlines()[-1:] or [f"code {r.returncode}, aucune image produite"]
    raise OSError(f"{os.path.basename(entree)} ({os.path.getsize(entree)} octets) : {erreur[0][:90]}")


def mesures_image(chemin):
    """(luminosité moyenne 0-255, netteté) d'une image : noire < 20, unie / floue si la netteté est très basse."""
    from PIL import Image, ImageFilter, ImageStat
    im = Image.open(chemin).convert("L")
    lum = ImageStat.Stat(im).mean[0]
    nettete = ImageStat.Stat(im.filter(ImageFilter.FIND_EDGES)).stddev[0]
    return lum, nettete


CONSIGNE_IMAGES = """Tu contrôles les images d'une vidéo TikTok d'actualité. Pour chaque image numérotée, on te donne la phrase
dite pendant qu'elle s'affiche et le sujet de la vidéo. Réponds pour CHAQUE image :
- "rapport" : le lien entre l'image et la vidéo : "exact" (montre ce que dit la phrase), "sujet" (montre le sujet de la
  vidéo : la même personne, le même lieu, le même objet, même pour une autre partie de l'histoire — ex. un A320 en vol pour
  une phrase sur sa chaîne de montage), "domaine" (même domaine : stade et supporters pour un sujet de football) ou "aucun"
  (rien à voir : chevaux pour une élève qui fait un malaise, paysage au hasard, sujet sans aucun lien) ;
- une photo d'ARCHIVE ou ANCIENNE de la même personne, équipe, pays ou lieu = "sujet" ; un autre match de la même équipe,
  une autre manifestation sur le même thème, un autre discours de la même personne = "sujet" ou "domaine", JAMAIS "aucun" ;
- en cas de doute entre "domaine" et "aucun", choisis "domaine" : un spectateur doit pouvoir voir un lien, même lointain ;
- "colle" : false SEULEMENT si "rapport" vaut "aucun" ;
- "texte_etranger" : true si un texte incrusté en langue étrangère ou des sous-titres sont visibles ;
- un logo ou un filigrane visible n'est PAS un problème : ne le signale pas ;
- "probleme" : en quelques mots, sinon "" ;
- "recherche" : si l'image ne va pas, 2 à 4 mots ANGLAIS concrets pour trouver une meilleure vidéo, sinon "".
Réponds uniquement en JSON : {"images": [{"n": numéro, "rapport": "…", "colle": …, "texte_etranger": …, "probleme": "…", "recherche": "…"}]}"""


def juger_images(lots, sujet, journal=print):
    """lots = [(n° d'écran, image .jpg, phrase)] → {n: avis} ; {} si aucune IA qui voit n'est disponible."""
    avis = {}
    for k in range(0, len(lots), 5):
        paquet = lots[k:k + 5]
        texte = f"SUJET : {sujet}\n" + "\n".join(f"Image {j + 1} (écran {n}) : « {phrase} »" for j, (n, _, phrase) in enumerate(paquet))
        d, qui = ia.regarder_json(CONSIGNE_IMAGES, texte, [c for _, c, _ in paquet], journal=journal)
        for r in d.get("images") or []:
            try:
                j = int(r.get("n")) - 1
            except (TypeError, ValueError):
                continue
            if 0 <= j < len(paquet):
                avis[paquet[j][0]] = r
    return avis


def uid(script, i):
    """Numéro fixe d'une phrase (il ne change pas quand une phrase est ajoutée ou retirée) : sert au suivi des problèmes."""
    p = script["phrases"][i]
    if "uid" not in p:
        p["uid"] = max([q.get("uid", -1) for q in script["phrases"]] + [len(script["phrases"]) - 1]) + 1
    return p["uid"]


def _image_deja_bonne(script, i):
    """Dernier recours avant l'écran de texte, SANS doublon (demande de l'auteur du 25/11) : 1) la scène d'avant CONTINUE
    (même vraie vidéo, la suite des images) ; 2) un passage PAS ENCORE MONTRÉ d'une vraie vidéo déjà validée par l'IA."""
    ph = script["phrases"]
    avant = (ph[i - 1].get("media") or {}) if i > 0 else {}
    if avant.get("type") == "video" and ph[i - 1].get("_valide") and not avant.get("presse"):
        return dict(avant, id=f"{str(avant.get('id', 'media')).split('-suite')[0]}-suite{i}", suite=True)
    for q in ph[:-1]:
        m = q.get("media") or {}
        if m.get("type") != "video" or not q.get("_valide") or not m.get("chemin"):
            continue
        fin_vue = max((x["media"].get("debut", 0) for x in ph if (x.get("media") or {}).get("chemin") == m["chemin"]), default=0) + 10
        if fin_vue + 5 <= (m.get("duree") or 0):          # il reste au moins 5 s jamais montrées dans cette vidéo
            return dict(m, debut=fin_vue, id=f"{str(m.get('id', 'media')).split('-suite')[0]}-p{int(fin_vue)}", suite=False)
    return None


CONSIGNE_DEUXIEME_AVIS = """Une vidéo TikTok d'actualité n'a trouvé AUCUNE autre image pour un écran. Sans cette image, l'écran
sera un simple fond de couleur avec du texte. On te montre l'image refusée, la phrase dite et le sujet. Question : un
spectateur peut-il voir un lien, même lointain, entre l'image et le sujet (même personne, équipe, pays, lieu, thème, époque) ?
Réponds "garder" : true si oui ; false seulement si l'image n'a vraiment rien à voir (ex. des chevaux pour un malaise
d'élève) ou si elle est choquante ou trompeuse. Réponds uniquement en JSON : {"garder": true/false, "raison": "…"}"""


def deuxieme_avis(script, i, sujet, journal=print):
    """Dernier recours avant l'écran de texte : l'image refusée la plus récente est montrée de nouveau à une IA avec une
    question plus large (lien même lointain). Si elle est gardée, l'écran garde une vraie image. Renvoie True si gardée."""
    p = script["phrases"][i]
    for r in reversed(p.get("_rejetees") or []):
        m, img = r.get("media") or {}, r.get("img")
        if not img or not os.path.exists(img) or not m.get("chemin") or not os.path.exists(m["chemin"]):
            continue
        if any(q is not p and (q.get("media") or {}).get("chemin") == m["chemin"]
               and (q.get("media") or {}).get("debut", 0) == m.get("debut", 0) for q in script["phrases"]):
            continue                                       # déjà montrée ailleurs : jamais de doublon
        try:
            d, _ = ia.regarder_json(CONSIGNE_DEUXIEME_AVIS, f"SUJET : {sujet}\nPHRASE : « {p['ecrit']} »", [img], journal=journal)
        except ia.AucuneIA:
            return False
        if d.get("garder") is True:
            p["media"] = m; p["_garde_2e_avis"] = True; p["_valide"] = True
            journal(f"    écran {i + 1} : image gardée après un 2e avis ({str(d.get('raison') or '')[:60]})")
            return True
    return False


def nouvelle_image(script, i, dossier, deja, journal, recherche="", sujet=""):
    """Échelle de solutions pour une image fautive (demande de l'auteur du 24/11 : plus jamais une vidéo sans images) :
    1) recherche proposée par l'IA ; 2) vraies vidéos libres de ce dont parle la phrase ; 3) passages de réserve des vidéos du
    sujet ; 4) le thème général du sujet ; 5) une vraie image déjà acceptée sur un autre écran (autre moment de la vidéo) ;
    6) écran de texte, seulement s'il n'existe vraiment aucune image dans toute la vidéo."""
    p = script["phrases"][i]
    p["_essais_image"] = p.get("_essais_image", 0) + 1
    n = p["_essais_image"]
    m = None
    try:
        if n == 1:
            requete = recherche or p.get("image", "")
            m = images.trouver(requete, dossier, 50 + i, deja, journal, "", entite=p.get("entite", ""),
                               generiques=script.get("images_generiques", False)) if (requete or p.get("entite")) else None
            quoi = f"nouvelle image (« {requete} »)"
        elif n == 2:
            cible = p.get("entite") or script.get("titre", "")
            clips = images.videos_du_sujet(cible, [], dossier, journal, maxi=1, ecrans=2, prefixe=f"remplace{i}", deja=deja)
            m = clips[0] if clips else None
            script.setdefault("_reserve", []).extend(clips[1:])
            quoi = f"vraie vidéo de « {cible} »"
        elif n == 3:
            reserve = script.get("_reserve") or []
            m = reserve.pop(0) if reserve else None
            quoi = "autre passage d'une vraie vidéo du sujet"
        elif n == 4:
            requete = script.get("theme_image") or p.get("image", "")
            m = images.trouver(requete, dossier, 80 + i, deja, journal, "", entite=script.get("entite_sujet", ""),
                               generiques=script.get("images_generiques", False)) if requete else None
            quoi = f"image du thème (« {requete} »)"
        else:
            m = _image_deja_bonne(script, i)
            quoi = "vraie image d'un autre écran, à un autre moment"
    except Exception as e:
        journal(f"    écran {i + 1} : solution {n} impossible ({str(e)[:80]})")
    if m:
        deja.add(m.get("id", ""))
        p["media"] = m
        return quoi
    if n >= 5:
        if deuxieme_avis(script, i, sujet or script.get("titre", ""), journal):
            return "image refusée gardée après un 2e avis (lien avec le sujet confirmé)"
        p["media"] = None
        return "écran de texte (aucune autre image trouvée)"
    return nouvelle_image(script, i, dossier, deja, journal, recherche, sujet)       # solution suivante tout de suite


def part_illustree(script):
    """(écrans avec une VRAIE image ou vidéo, écrans à illustrer) : la dernière question et la carte ne comptent pas, et un
    titre de presse n'est PAS une vraie image (demande de l'auteur du 24/11 : « pas seulement des titres de journaux »)."""
    ecrans = [p for p in script["phrases"][:-1] if not (p.get("media") or {}).get("type") == "carte"]
    return sum(1 for p in ecrans if p.get("media") and not p["media"].get("presse")), len(ecrans)


def controle_images(script, dossier, B, journal=print, deja=None, sujet="", sans_ia=False):
    """Niveau 3. Boucle jusqu'à ce qu'AUCUNE image ne pose problème ; seuls les écrans fautifs changent d'image."""
    deja = deja if deja is not None else {p["media"]["id"] for p in script["phrases"] if p.get("media") and p["media"].get("id")}
    for tour in range(5):
        lots, fautifs = [], {}
        for i, p in enumerate(script["phrases"]):
            m = p.get("media")
            if not m or m["type"] == "carte" or m.get("presse"):      # carte et titre de presse : écrans fabriqués par nous
                continue
            try:
                img = _image_de(m, dossier, f"controle{i:02d}.jpg")
                lum, net = mesures_image(img)
            except Exception as e:
                fautifs[i] = (f"image illisible ({str(e)[:70]})", ""); continue
            if lum < 20:
                fautifs[i] = ("écran presque noir", "")
            elif net < 6:
                fautifs[i] = ("image unie ou floue", "")
            elif m.get("citation"):                        # extrait de la vidéo d'origine : c'est l'événement lui-même
                p["_valide"] = True
            else:
                lots.append((i, img, p["ecrit"]))
        avis = {}
        if sans_ia and tour == 0:
            B.saute("regard de l'IA sur les images (mode secours)")
        for essai in range(0 if sans_ia else 5):          # IA occupée (5 vidéos à la fois) : on attend de plus en plus
            try:
                avis = juger_images(lots, sujet, journal) if lots else {}
                break
            except ia.AucuneIA as e:
                if essai == 4:
                    B.saute(f"regard de l'IA sur les images (IA indisponible : {str(e)[:120]})")
                else:
                    import time; time.sleep(60 * (essai + 1))
        for i, a in avis.items():
            rapport = str(a.get("rapport") or "").lower()
            hors_sujet = rapport == "aucun" or (not rapport and a.get("colle") is False)   # « autre aspect du sujet » = bon
            if script["phrases"][i].get("_garde_2e_avis") and not a.get("texte_etranger"):
                continue                                   # déjà jugée deux fois : gardée (sinon boucle sans fin)
            if hors_sujet or a.get("texte_etranger"):
                fautifs[i] = (a.get("probleme") or "image qui ne colle pas", a.get("recherche") or "")
        for i, _, _ in lots:                               # validée par l'IA : peut servir sur un autre écran
            if i not in fautifs and (avis or sans_ia):
                script["phrases"][i]["_valide"] = True
        regles = {uid(script, i) for i in fautifs}
        for l in B.ouverts("images"):                      # revérifié : plus de problème sur ce passage
            if l["ecran"] not in regles:
                B.fermer("images", l["ecran"])
        if not fautifs:
            break
        journal(f"  contrôle des images (tour {tour + 1}) : {len(fautifs)} écran(s) à changer : "
                + ", ".join(f"écran {i + 1} ({str(pb)[:50]})" for i, (pb, _) in fautifs.items()))
        images_lues = {i: img for i, img, _ in lots}
        for i, (probleme, recherche) in fautifs.items():
            p = script["phrases"][i]
            if p.get("media") and i in images_lues:         # gardée en mémoire pour un éventuel 2e avis
                copie = os.path.join(dossier, f"rejetee{i:02d}-{len(p.get('_rejetees') or [])}.jpg")
                shutil.copyfile(images_lues[i], copie)       # l'image du contrôle est réécrite au tour suivant
                p.setdefault("_rejetees", []).append(dict(media=p["media"], img=copie))
            l = B.ouvrir("images", probleme, uid(script, i))
            l["solution"] = nouvelle_image(script, i, dossier, deja, journal, recherche, sujet)
            if p.get("_garde_2e_avis"):
                B.fermer("images", uid(script, i))
    illustres, total = part_illustree(script)              # une vidéo presque sans images n'a JAMAIS 100/100
    journal(f"  écrans illustrés : {illustres}/{total}")
    if total and illustres < 0.7 * total:
        B.ouvrir("images", f"trop peu d'images : {illustres} écran(s) illustré(s) sur {total}", None, "grave")
    else:
        B.fermer("images", None)
    return script


# ------------------------------------------------------------------ 4. vidéo finie
def _probe(fichier):
    d = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
                                            "-of", "json", fichier]))
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), {})
    return float(d["format"]["duration"]), v.get("width"), v.get("height"), any(s["codec_type"] == "audio" for s in d["streams"])


def ecrans_noirs(fichier, debuts):
    """Écrans où la vidéo est noire plus d'une demi-seconde."""
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", fichier, "-vf", "blackdetect=d=0.5:pix_th=0.08", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    out = set()
    for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", r.stderr):
        milieu = (float(a) + float(b)) / 2
        out.add(max(k for k, d in enumerate(debuts) if d <= milieu))
    return out


def sous_titres_ecoutes(fichier, phrases, debuts):
    """Écrans où la vidéo finie, réécoutée par Whisper, ne dit pas la phrase prévue (moins de 60 % des mots)."""
    entendus = V.mots_entendus(fichier)
    out = {}
    for i, p in enumerate(phrases):
        a, b = debuts[i] - 0.2, debuts[i] + p["duree"] + 0.3
        mots = [m for m in entendus if a <= (m[1] + m[2]) / 2 <= b]
        r = max(V.ressemblance(p["voix"], mots), V.ressemblance(p["ecrit"], mots))
        if r < 0.6:
            out[i] = r
    return out


CONSIGNE_FINALE = """Tu contrôles des images d'une vidéo TikTok TERMINÉE (textes et sous-titres incrustés compris). Pour chaque
image, réponds : "titre_coupe" (un texte coupé au bord ou qui dépasse), "chevauchement" (deux textes AJOUTÉS l'un sur l'autre :
gros titre, étiquette, sous-titres ; ou un texte sur un visage), "illisible" (sous-titre ou titre impossible à lire),
"probleme" (quelques mots, sinon ""). Un texte qui fait partie de l'IMAGE de fond (article de presse, panneau, affiche) n'est
PAS un chevauchement tant que les sous-titres restent lisibles. Sur un extrait d'une vidéo d'un média (logo, bandeau
« @compte » en haut), les textes et sous-titres de CETTE vidéo d'origine font partie de l'image : seuls NOS sous-titres (gros,
sur bandeau noir) et NOTRE titre jaune comptent.
Réponds uniquement en JSON : {"images": [{"n": numéro, "titre_coupe": …, "chevauchement": …, "illisible": …, "probleme": "…"}]}"""


def controle_video(fichier, script, dossier, B, journal=print, leger=False, sans_ia=False, seulement=None):
    """Niveau 4. Renvoie {n° d'écran (ou None = toute la vidéo): (problème, action)} ;
    action = "image", "titre", "voix", "allonger" (trop court) ou "refaire" (format, son)."""
    from . import montage
    ph = script["phrases"]; debuts, total = montage.debuts_et_total(ph)
    fautifs = {}
    duree, w, h, son = _probe(fichier)
    if (w, h) != (1080, 1920) or not son:
        fautifs[None] = (f"format {w}×{h}" + ("" if son else ", pas de son"), "refaire")
    if duree < 61 and not leger and not script.get("_allonger_impossible"):     # (l'essai sans réseau est court)
        # TikTok ne paie que les vidéos de PLUS d'1 minute : 61 s au moins, avec une marge (texte visé : 62 s)
        fautifs[None] = (f"vidéo de {duree:.0f} s : pas plus d'1 minute (pas payée par TikTok)", "allonger")
    for i in ecrans_noirs(fichier, debuts):
        if ph[i].get("media"):
            fautifs[i] = ("écran noir dans la vidéo finie", "image")
    for i, p in enumerate(ph):
        if p.get("_voix_defaut"):
            fautifs[i] = (p["_voix_defaut"], "voix")
    if leger:                                             # essai sans réseau : contrôles techniques seulement
        return fautifs
    try:
        for i, r in sous_titres_ecoutes(fichier, ph, debuts).items():
            fautifs[i] = (f"voix et sous-titres ne correspondent pas ({r:.0%})", "voix")
    except Exception as e:
        B.saute(f"réécoute des sous-titres ({str(e)[:60]})")
    lots = []
    for i in range(len(ph)):
        if i in fautifs or (seulement is not None and i not in seulement):
            continue                                       # (tours suivants) seuls les écrans refaits sont regardés de nouveau
        img = os.path.join(dossier, f"final{i:02d}.jpg")
        t = debuts[i] + min(1.2, ph[i]["duree"] / 2)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", fichier, "-frames:v", "1", "-vf", "scale=540:-2",
                        "-q:v", "4", img], check=False)
        if os.path.exists(img) and os.path.getsize(img) > 0:
            lots.append((i, img))
    if sans_ia:
        B.saute("regard de l'IA sur la vidéo finie (mode secours)")
    for essai in range(0 if sans_ia else 3):
        try:
            for k in range(0, len(lots), 5):
                paquet = lots[k:k + 5]
                d, _ = ia.regarder_json(CONSIGNE_FINALE, "\n".join(f"Image {j + 1} = écran {n}" for j, (n, _) in enumerate(paquet)),
                                        [c for _, c in paquet], journal=journal)
                for r in d.get("images") or []:
                    try:
                        n = paquet[int(r.get("n")) - 1][0]
                    except (TypeError, ValueError, IndexError):
                        continue
                    if r.get("titre_coupe") or r.get("chevauchement") or r.get("illisible"):
                        # titre déjà raccourci puis retiré et toujours un problème : c'est l'IMAGE qui gêne, on la change
                        # (la vidéo du GTA du 24/11 a tourné 7 tours de suite sur un titre déjà retiré)
                        deja_vu = next((l for l in B.ouverts("video") if l["ecran"] == uid(script, n)), None)
                        citation = (script["phrases"][n].get("media") or {}).get("citation")
                        if citation and deja_vu and (deja_vu.get("essais", 1) >= 2 or not script["phrases"][n].get("ecran")):
                            # extrait de l'événement : JAMAIS remplacé pour un texte de la vidéo d'origine (vidéo CAN du
                            # 25/11 : l'accroche d'Al Jazeera remplacée par une photo Wikipédia, 12 tours, 56 min) ;
                            # nos sous-titres sont sur bandeau noir, donc lisibles
                            continue
                        action = "image" if deja_vu and deja_vu.get("essais", 1) >= 2 else "titre"
                        fautifs[n] = (r.get("probleme") or "texte mal placé", action)
            break
        except ia.AucuneIA as e:
            if essai == 2:
                B.saute(f"regard de l'IA sur la vidéo finie (IA indisponible : {str(e)[:120]})")
            else:
                import time; time.sleep(60 * (essai + 1))
    return fautifs


def phrase_absurde(t):
    """Phrase qui n'en est pas une : moins de 3 vrais mots, ou surtout des chiffres (« 18 7 18 », vidéo CAN r13 du 25/11)."""
    mots = re.findall(r"[A-Za-zÀ-ÿ]{2,}", t or "")
    chiffres = re.findall(r"\d+", t or "")
    return len(mots) < 3 or len(chiffres) > len(mots)


def simplification_valable(avant, apres):
    """Une phrase simplifiée par l'IA doit rester une vraie phrase et parler de la même chose (au moins 1 mot sur 3 de
    l'ancienne phrase, sans compter les petits mots)."""
    if not apres.strip() or phrase_absurde(apres):
        return False
    a = {m.lower() for m in re.findall(r"[A-Za-zÀ-ÿ]{4,}", avant)}
    b = {m.lower() for m in re.findall(r"[A-Za-zÀ-ÿ]{4,}", apres)}
    return not a or len(a & b) >= max(1, len(a) // 3)


CONSIGNE_SIMPLIFIER = """Réécris cette phrase d'une vidéo TikTok avec des mots plus simples et plus courts, faciles à prononcer
pour une voix de synthèse (pas de sigle, pas de nom étranger difficile si on peut l'éviter), en gardant exactement le même fait.
Réponds uniquement en JSON : {"voix": "nombres en lettres", "ecrit": "nombres en chiffres"}"""


def corriger_ecrans(script, fautifs, dossier, B, journal=print, nom_voix="", vitesse=0.8, articles=()):  # noqa: C901
    """Corrige les seuls passages fautifs, avec une échelle de solutions (la dernière marche à coup sûr) ; le montage ne
    refera que ces écrans. Lève LookupError si la vidéo reste trop courte (sujet abandonné, jamais de vidéo trop courte)."""
    deja = {p["media"]["id"] for p in script["phrases"] if p.get("media") and p["media"].get("id")}
    ph = script["phrases"]
    for i, (probleme, action) in sorted(fautifs.items(), key=lambda x: -(x[0] if x[0] is not None else -1)):
        if i is None:
            l = B.ouvrir("video", probleme, None, "grave")
            if action == "allonger":
                if l["essais"] > 3:                         # jamais d'abandon : la vidéo reste marquée « à vérifier »
                    script["_allonger_impossible"] = True
                    continue
                avant = len(ph)
                try:
                    controle_texte_ajout(script, articles, journal)
                except ia.AucuneIA:
                    continue
                for k in range(len(ph)):
                    if "duree" not in ph[k]:                # phrases ajoutées : voix et image
                        ph[k]["son"] = os.path.join(dossier, f"voix_ajout{uid(script, k):02d}.wav")
                        V.preparer([ph[k]], nom_voix, vitesse, journal, memoire=os.path.join(dossier, "memoire_voix"))
                        ph[k]["media"] = images.trouver(ph[k].get("image", ""), dossier, 70 + k, deja, journal,
                                                        script.get("theme_image", ""), entite=ph[k].get("entite", ""),
                                                        generiques=script.get("images_generiques", False))
                l["solution"] = f"{len(ph) - avant} phrase(s) de faits ajoutée(s)"
            else:
                for q in ph:
                    q.pop("_sig", None)                     # tout l'écran est refait
                l["solution"] = "vidéo refaite"
            continue
        p = ph[i]; cle = uid(script, i)
        niveau = "voix" if action == "voix" else "video"
        l = B.ouvrir(niveau, probleme, cle, "grave" if action == "voix" else "moyen")
        if action == "image":
            l["solution"] = nouvelle_image(script, i, dossier, deja, journal)
        elif action == "titre":
            p["ecran"] = " ".join((p.get("ecran") or "").split()[:2])[:14] if l["essais"] == 1 else ""
            l["solution"] = "titre raccourci" if p["ecran"] else "titre retiré"
        elif action == "voix":
            n = l["essais"]
            # Chatterbox coûte ~1 min par phrase : la phrase a DÉJÀ été refaite 2 fois à l'étape de la voix, donc on passe tout de
            # suite à des mots plus simples (avant : 2 essais de plus à l'identique, puis encore 2… la vidéo GTA a pris 99 min).
            if n in (1, 3) or n > 4:
                try:
                    d, _ = ia.demander_json(CONSIGNE_SIMPLIFIER, p["ecrit"], temperature=0.6, journal=journal)
                    if simplification_valable(p["ecrit"], str(d.get("ecrit") or d.get("voix") or "")):
                        p["voix"] = nombres.dire_les_nombres(str(d["voix"])); p["ecrit"] = str(d.get("ecrit") or d["voix"])
                        l["solution"] = "phrase simplifiée puis refaite"
                    else:                                  # réponse absurde de l'IA (« 18 7 18 », vidéo CAN r13) : refusée
                        journal(f"  écran {i + 1} : simplification refusée (« {str(d.get('ecrit') or d.get('voix'))[:40]} »)")
                except ia.AucuneIA:
                    pass
            if n >= 3 and 0 < i < len(ph) - 1 and duree_estimee(ph[:i] + ph[i + 1:]) >= 62:
                ph.pop(i)                                  # dernier recours : la phrase est retirée (vidéo assez longue)
                l.update(solution="phrase retirée", corrige=True)
                continue
            p.pop("mots", None); p.pop("_voix_defaut", None)
            V.oublier(p, nom_voix, vitesse, os.path.join(dossier, "memoire_voix"))
            V.preparer([p], nom_voix, vitesse, journal, memoire=os.path.join(dossier, "memoire_voix"))
            l.setdefault("solution", "voix refaite")


def controle_texte_ajout(script, articles, journal=print):
    """Ajoute 2 à 4 phrases de faits (pour une vidéo trop courte), sans toucher aux autres."""
    ph = script["phrases"]
    texte = "TEXTE :\n" + "\n".join(f"{k}. {p['ecrit']}" for k, p in enumerate(ph))
    texte += "\n\nÀ CORRIGER :\n- AJOUTER 2 à 4 phrases de faits : la vidéo fait moins d'1 minute"
    texte += "\n\nARTICLES :\n" + "\n\n".join(f"[{a['media']}] {a['titre']}\n{a.get('texte') or a.get('resume')}"
                                              for a in articles)[:12000]
    d, _ = ia.demander_json(CONSIGNE_REECRIRE, texte, temperature=0.5, journal=journal)
    for a in d.get("ajouts") or []:
        if isinstance(a, dict) and str(a.get("voix") or "").strip() and not phrase_absurde(str(a.get("ecrit") or a["voix"])) \
                and len(re.findall(r"[A-Za-zÀ-ÿ]{2,}", str(a.get("ecrit") or a["voix"]))) >= 5:
            ph.insert(len(ph) - 1, dict(voix=nombres.dire_les_nombres(str(a["voix"])), ecrit=str(a.get("ecrit") or a["voix"]),
                                        ecran=str(a.get("ecran") or "")[:24], image=str(a.get("image") or script.get("theme_image", "")),
                                        entite=str(a.get("entite") or "")[:80]))


# ------------------------------------------------------------------ 5. avant publication
class Refusee(Exception):
    """Le contrôle avant publication a trouvé un problème : la vidéo n'est pas envoyée."""


def verifier_et_envoyer(v, R, forcer=False):
    """Contrôle avant publication, puis envoi par Buffer. Lève Refusee si un problème bloque."""
    from . import publier
    description_secours(v)
    pb = avant_publication(v, R, forcer)
    if pb:
        raise Refusee("contrôle avant publication : " + " ; ".join(pb))
    return publier.envoyer(v, R)


# ------------------------------------------------------------------ extraits perdus (exigence de l'auteur du 25/11)
def _base(m):
    return str((m or {}).get("id", "")).split("-suite")[0]


def extraits_perdus(script):
    """Extraits VIDÉO de l'événement trouvés pour cette vidéo (`script["_citations_toutes"]`) qui ne sont PLUS à l'écran
    alors qu'un écran montre autre chose qu'un extrait (photo, titre de presse, écran de texte…) : ils ont été « perdus »
    en route (vidéo CAN r10 du 25/11 : texte refait, extraits BBC / franceinfo remplacés par des timbres)."""
    ph = script["phrases"]
    montres = {_base(p.get("media")) for p in ph if (p.get("media") or {}).get("citation")}
    places = [i for i, p in enumerate(ph[:-1]) if not (p.get("media") or {}).get("citation")
              and (p.get("media") or {}).get("type") != "carte"]
    perdus = [m for m in script.get("_citations_toutes") or [] if m.get("type") == "video" and _base(m) not in montres
              and m.get("chemin") and os.path.exists(m["chemin"])]
    return perdus[:len(places)]


def reposer_extraits(script, journal=print):
    """Remet chaque extrait perdu à l'écran, à la place de ce qui montre le moins l'événement : écran de texte d'abord,
    puis titre de presse, puis photo ou vidéo qui n'est pas de l'événement (jamais la carte ni la question finale).
    Renvoie le nombre d'extraits remis."""
    perdus = extraits_perdus(script)
    if not perdus:
        return 0
    ph = script["phrases"]

    def rang(i):
        m = ph[i].get("media") or {}
        return 0 if not m else 1 if m.get("presse") else 2 if m.get("type") == "photo" else 3
    places = sorted([i for i, p in enumerate(ph[:-1]) if not (p.get("media") or {}).get("citation")
                     and (p.get("media") or {}).get("type") != "carte"], key=lambda i: (rang(i), i))
    for m, i in zip(perdus, places):
        ph[i]["media"] = dict(m, suite=False, reelle=True); ph[i]["_valide"] = True; ph[i].pop("_sig", None)
        journal(f"  extrait perdu remis à l'écran {i + 1} : @{m.get('compte')} ({_base(m)})")
    return min(len(perdus), len(places))


def description_secours(v):
    """Description vide (vidéo de l'arche du 25/11) : écrite à partir du titre et de la question, au lieu de bloquer."""
    if not str(v.get("description") or "").strip():
        q = str(v.get("question") or "").strip()
        v["description"] = (f"{v.get('titre', '').strip()} 👀" + (f"\n{q}" if q else "")).strip()
    return v["description"]


def lien_en_ligne(url):
    """La vidéo se télécharge-t-elle ? (début du fichier seulement : GitHub répond 401 à une demande HEAD, 25/11)"""
    req = urllib.request.Request(url, headers={"User-Agent": "buzz-insolite-robot/1.0", "Range": "bytes=0-1023"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status < 400 and bool(r.read(1024))


def avant_publication(v, R, forcer=False):
    """Liste des problèmes qui empêchent la publication (vide = on peut publier)."""
    pb = []
    if v.get("essai"):
        pb.append("vidéo d'essai")
    if (v.get("controles") or {}).get("graves_restants") and not forcer:
        pb.append("défaut grave non corrigé (voir le bulletin)")
    # JAMAIS publiée sans vraies images (exigence de l'auteur du 24/11 : « pas un simple écran bleu ou violet »), même avec
    # « Publier quand même » : au moins 70 % des écrans avec une vraie vidéo ou image.
    total = v.get("ecrans_total") or max(1, len(v.get("texte") or []) - 1)
    if (v.get("ecrans_illustres") or 0) < 0.7 * total:
        pb.append(f"trop peu de vraies images ({v.get('ecrans_illustres') or 0} écran(s) illustré(s) sur {total}) : à refaire")
    if v.get("regles_non_respectees"):                    # règles de la vidéo (robot/regles.py) : jamais publiée sans elles
        pb.append("règle(s) non respectée(s) : " + " ; ".join(v["regles_non_respectees"])[:200])
    if v.get("extraits_perdus"):                          # JAMAIS publiée avec des extraits perdus, même « quand même »
        pb.append(f"{v['extraits_perdus']} extrait(s) de l'événement perdu(s) : à refaire")
    if (v.get("duree") or 0) < 58:
        pb.append(f"vidéo trop courte ({v.get('duree', 0):.0f} s)")
    if not str(v.get("description") or "").strip():
        pb.append("description vide")
    tags = v.get("hashtags") or []
    if not 3 <= len(tags) <= 10:
        pb.append(f"{len(tags)} hashtag(s) (il en faut 3 à 10)")
    if not str(v.get("url", "")).startswith("https://"):
        pb.append("vidéo sans adresse publique")
    else:
        try:
            if not lien_en_ligne(v["url"]):
                pb.append("vidéo introuvable en ligne")
        except Exception as e:
            pb.append(f"vidéo injoignable ({str(e)[:60]})")
    if not str((R.get("publication") or {}).get("compte") or "").strip():
        pb.append("compte TikTok de Buffer non choisi (Réglages)")
    return pb
