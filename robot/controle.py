"""Contrôle qualité en 4 niveaux (+ contrôle avant publication), demandé par l'auteur le 24/11/2026.

1. TEXTE (avant toute fabrication) : faits vérifiés par une 2e IA (ecrire.verifier) + règles : nombres écrits en lettres pour
   la voix, accroche courte, question finale, titres d'écran courts, phrases trop longues, doublons, durée d'au moins 1 minute.
   Seules les phrases en défaut sont réécrites (IA), puis revérifiées.
2. VOIX (phrase par phrase, voix.preparer) : mots compris par Whisper, durée normale pour le nombre de mots (une voix qui
   « bafouille » parle trop longtemps). Seule la phrase fautive est refaite.
3. IMAGES (écran par écran) : écran noir, uni ou flou (mesuré), puis une IA qui VOIT l'image juge si elle colle à la phrase,
   sans texte incrusté, logo ni filigrane. Seul l'écran fautif reçoit une nouvelle image (sinon un écran de texte).
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
"ecran" (chiffre fort ou nom, 3 mots max, ou ""), "image" (2 à 4 mots anglais concrets et filmables).
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
        for k, nouv in (d.get("phrases") or {}).items():
            try:
                k = int(k)
            except ValueError:
                continue
            if 0 <= k < len(ph) and str(nouv.get("voix") or "").strip():
                garde = {c: ph[k][c] for c in ("reponse",) if ph[k].get(c)}
                ph[k] = dict(voix=nombres.dire_les_nombres(str(nouv["voix"])), ecrit=str(nouv.get("ecrit") or nouv["voix"]),
                             ecran=str(nouv.get("ecran") or "")[:24], image=str(nouv.get("image") or ph[k].get("image", "")), **garde)
                refaites += 1
        for a in d.get("ajouts") or []:
            if str(a.get("voix") or "").strip():
                ph.insert(len(ph) - 1, dict(voix=nombres.dire_les_nombres(str(a["voix"])), ecrit=str(a.get("ecrit") or a["voix"]),
                                            ecran=str(a.get("ecran") or "")[:24], image=str(a.get("image") or script.get("theme_image", ""))))
                refaites += 1
        journal(f"  contrôle du texte (tour {tour + 1}) : {len(pb)} problème(s), {refaites} phrase(s) réécrite(s) par {qui}")
    restant = regles_texte(script)
    if any(i is None for i, _, _ in restant):
        raise LookupError("pas assez de faits pour une vidéo d'1 minute, même après ajouts : sujet abandonné")
    for l in B.ouverts("texte"):                            # tout est réglé : les problèmes ouverts sont fermés
        B.fermer("texte", l["ecran"], "phrase réécrite et revérifiée")
    return script


# ------------------------------------------------------------------ 3. images
def _image_de(media, dossier, nom, instant=1.0):
    """Une image .jpg (512 px de large) du média, pour la montrer à l'IA."""
    sortie = os.path.join(dossier, nom)
    entree = media["chemin"]
    t = media.get("debut", 0) + instant if media["type"] == "video" else 0
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", entree, "-frames:v", "1", "-vf", "scale=512:-2",
                    "-q:v", "4", sortie], check=True)
    return sortie


def mesures_image(chemin):
    """(luminosité moyenne 0-255, netteté) d'une image : noire < 20, unie / floue si la netteté est très basse."""
    from PIL import Image, ImageFilter, ImageStat
    im = Image.open(chemin).convert("L")
    lum = ImageStat.Stat(im).mean[0]
    nettete = ImageStat.Stat(im.filter(ImageFilter.FIND_EDGES)).stddev[0]
    return lum, nettete


CONSIGNE_IMAGES = """Tu contrôles les images d'une vidéo TikTok d'actualité. Pour chaque image numérotée, on te donne la phrase
dite pendant qu'elle s'affiche et le sujet de la vidéo. Réponds pour CHAQUE image :
- "colle" : true si l'image illustre bien la phrase ou au moins le sujet (même de façon générale), false si elle est hors sujet ;
- "texte_etranger" : true si un texte incrusté en langue étrangère ou des sous-titres sont visibles ;
- "logo" : true si un logo de marque, de chaîne télé ou un filigrane est visible ;
- "probleme" : en quelques mots, sinon "" ;
- "recherche" : si l'image ne va pas, 2 à 4 mots ANGLAIS concrets pour trouver une meilleure vidéo, sinon "".
Réponds uniquement en JSON : {"images": [{"n": numéro, "colle": …, "texte_etranger": …, "logo": …, "probleme": "…", "recherche": "…"}]}"""


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


def nouvelle_image(script, i, dossier, deja, journal, recherche=""):
    """Échelle de solutions pour une image fautive : 1) nouvelle recherche (celle proposée par l'IA, sinon la phrase),
    2) le thème général du sujet, 3) écran de texte — qui ne peut pas être hors sujet : le problème est réglé à coup sûr."""
    p = script["phrases"][i]
    p["_essais_image"] = p.get("_essais_image", 0) + 1
    n = p["_essais_image"]
    if n >= 3:
        p["media"] = None
        return "écran de texte à la place de l'image"
    requete = (recherche or p.get("image", "")) if n == 1 else (script.get("theme_image") or p.get("image", ""))
    p["media"] = images.trouver(requete, dossier, 50 + 10 * n + i % 10, deja, journal, "") if requete else None
    return f"nouvelle image (« {requete} »)" if p["media"] else "écran de texte à la place de l'image"


def controle_images(script, dossier, B, journal=print, deja=None, sujet=""):
    """Niveau 3. Boucle jusqu'à ce qu'AUCUNE image ne pose problème ; seuls les écrans fautifs changent d'image."""
    deja = deja if deja is not None else {p["media"]["id"] for p in script["phrases"] if p.get("media") and p["media"].get("id")}
    for tour in range(5):
        lots, fautifs = [], {}
        for i, p in enumerate(script["phrases"]):
            m = p.get("media")
            if not m or m["type"] == "carte":
                continue
            try:
                img = _image_de(m, dossier, f"controle{i:02d}.jpg")
            except Exception:
                fautifs[i] = ("image illisible", ""); continue
            lum, net = mesures_image(img)
            if lum < 20:
                fautifs[i] = ("écran presque noir", "")
            elif net < 6:
                fautifs[i] = ("image unie ou floue", "")
            else:
                lots.append((i, img, p["ecrit"]))
        avis = {}
        for essai in range(3):                            # IA occupée : on attend et on réessaie avant d'abandonner
            try:
                avis = juger_images(lots, sujet, journal) if lots else {}
                break
            except ia.AucuneIA:
                if essai == 2:
                    B.saute("regard de l'IA sur les images (IA indisponible)")
                else:
                    import time; time.sleep(60)
        for i, a in avis.items():
            if not a.get("colle", True) or a.get("texte_etranger") or a.get("logo"):
                fautifs[i] = (a.get("probleme") or "image qui ne colle pas", a.get("recherche") or "")
        regles = {uid(script, i) for i in fautifs}
        for l in B.ouverts("images"):                      # revérifié : plus de problème sur ce passage
            if l["ecran"] not in regles:
                B.fermer("images", l["ecran"])
        if not fautifs:
            return script
        journal(f"  contrôle des images (tour {tour + 1}) : {len(fautifs)} écran(s) à changer")
        for i, (probleme, recherche) in fautifs.items():
            l = B.ouvrir("images", probleme, uid(script, i))
            l["solution"] = nouvelle_image(script, i, dossier, deja, journal, recherche)
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
image, réponds : "titre_coupe" (un texte coupé au bord ou qui dépasse), "chevauchement" (deux textes l'un sur l'autre ou un texte
sur un visage), "illisible" (texte illisible), "probleme" (quelques mots, sinon "").
Réponds uniquement en JSON : {"images": [{"n": numéro, "titre_coupe": …, "chevauchement": …, "illisible": …, "probleme": "…"}]}"""


def controle_video(fichier, script, dossier, B, journal=print, leger=False):
    """Niveau 4. Renvoie {n° d'écran (ou None = toute la vidéo): (problème, action)} ;
    action = "image", "titre", "voix", "allonger" (trop court) ou "refaire" (format, son)."""
    from . import montage
    ph = script["phrases"]; debuts, total = montage.debuts_et_total(ph)
    fautifs = {}
    duree, w, h, son = _probe(fichier)
    if (w, h) != (1080, 1920) or not son:
        fautifs[None] = (f"format {w}×{h}" + ("" if son else ", pas de son"), "refaire")
    if duree < 60 and not leger:                          # (l'essai sans réseau est volontairement court)
        fautifs[None] = (f"vidéo de {duree:.0f} s : moins d'1 minute (pas payée par TikTok)", "allonger")
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
        if i in fautifs:
            continue
        img = os.path.join(dossier, f"final{i:02d}.jpg")
        t = debuts[i] + min(1.2, ph[i]["duree"] / 2)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", fichier, "-frames:v", "1", "-vf", "scale=540:-2",
                        "-q:v", "4", img], check=True)
        lots.append((i, img))
    for essai in range(3):
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
                        fautifs[n] = (r.get("probleme") or "texte mal placé", "titre")
            break
        except ia.AucuneIA:
            if essai == 2:
                B.saute("regard de l'IA sur la vidéo finie (IA indisponible)")
            else:
                import time; time.sleep(60)
    return fautifs


CONSIGNE_SIMPLIFIER = """Réécris cette phrase d'une vidéo TikTok avec des mots plus simples et plus courts, faciles à prononcer
pour une voix de synthèse (pas de sigle, pas de nom étranger difficile si on peut l'éviter), en gardant exactement le même fait.
Réponds uniquement en JSON : {"voix": "nombres en lettres", "ecrit": "nombres en chiffres"}"""


def corriger_ecrans(script, fautifs, dossier, B, journal=print, nom_voix="", vitesse=0.8, articles=()):
    """Corrige les seuls passages fautifs, avec une échelle de solutions (la dernière marche à coup sûr) ; le montage ne
    refera que ces écrans. Lève LookupError si la vidéo reste trop courte (sujet abandonné, jamais de vidéo trop courte)."""
    deja = {p["media"]["id"] for p in script["phrases"] if p.get("media") and p["media"].get("id")}
    ph = script["phrases"]
    for i, (probleme, action) in sorted(fautifs.items(), key=lambda x: -(x[0] if x[0] is not None else -1)):
        if i is None:
            l = B.ouvrir("video", probleme, None, "grave")
            if action == "allonger":
                if l["essais"] > 2:
                    raise LookupError("vidéo trop courte même après ajouts : sujet abandonné")
                avant = len(ph)
                controle_texte_ajout(script, articles, journal)
                for k in range(len(ph)):
                    if "duree" not in ph[k]:                # phrases ajoutées : voix et image
                        ph[k]["son"] = os.path.join(dossier, f"voix_ajout{uid(script, k):02d}.wav")
                        V.preparer([ph[k]], nom_voix, vitesse, journal)
                        ph[k]["media"] = images.trouver(ph[k].get("image", ""), dossier, 70 + k, deja, journal,
                                                        script.get("theme_image", ""))
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
            if n in (3, 6) or n > 7:                      # refaite plusieurs fois sans succès : mots plus simples
                try:
                    d, _ = ia.demander_json(CONSIGNE_SIMPLIFIER, p["ecrit"], temperature=0.6, journal=journal)
                    if str(d.get("voix") or "").strip():
                        p["voix"] = nombres.dire_les_nombres(str(d["voix"])); p["ecrit"] = str(d.get("ecrit") or d["voix"])
                        l["solution"] = "phrase simplifiée puis refaite"
                except ia.AucuneIA:
                    pass
            if n >= 5 and 0 < i < len(ph) - 1 and duree_estimee(ph[:i] + ph[i + 1:]) >= 62:
                ph.pop(i)                                  # dernier recours : la phrase est retirée (vidéo assez longue)
                l.update(solution="phrase retirée", corrige=True)
                continue
            p.pop("mots", None); p.pop("_voix_defaut", None)
            V.preparer([p], nom_voix, vitesse, journal)
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
        if str(a.get("voix") or "").strip():
            ph.insert(len(ph) - 1, dict(voix=nombres.dire_les_nombres(str(a["voix"])), ecrit=str(a.get("ecrit") or a["voix"]),
                                        ecran=str(a.get("ecran") or "")[:24], image=str(a.get("image") or script.get("theme_image", ""))))


# ------------------------------------------------------------------ 5. avant publication
class Refusee(Exception):
    """Le contrôle avant publication a trouvé un problème : la vidéo n'est pas envoyée."""


def verifier_et_envoyer(v, R, forcer=False):
    """Contrôle avant publication, puis envoi par Buffer. Lève Refusee si un problème bloque."""
    from . import publier
    pb = avant_publication(v, R, forcer)
    if pb:
        raise Refusee("contrôle avant publication : " + " ; ".join(pb))
    return publier.envoyer(v, R)


def avant_publication(v, R, forcer=False):
    """Liste des problèmes qui empêchent la publication (vide = on peut publier)."""
    pb = []
    if v.get("essai"):
        pb.append("vidéo d'essai")
    if (v.get("controles") or {}).get("graves_restants") and not forcer:
        pb.append("défaut grave non corrigé (voir le bulletin)")
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
            req = urllib.request.Request(v["url"], method="HEAD", headers={"User-Agent": "buzz-insolite-robot/1.0"})
            if urllib.request.urlopen(req, timeout=30).status >= 400:
                pb.append("vidéo introuvable en ligne")
        except Exception as e:
            pb.append(f"vidéo injoignable ({str(e)[:60]})")
    if not str((R.get("publication") or {}).get("compte") or "").strip():
        pb.append("compte TikTok de Buffer non choisi (Réglages)")
    return pb
