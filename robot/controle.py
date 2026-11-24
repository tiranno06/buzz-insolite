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
    def __init__(self):
        self.lignes = []; self.sautes = []

    def ajouter(self, niveau, probleme, ecran=None, gravite="moyen", corrige=False):
        self.lignes.append(dict(niveau=niveau, ecran=ecran, gravite=gravite, probleme=str(probleme)[:200], corrige=corrige))

    def saute(self, controle):
        self.sautes.append(controle)

    def restants(self, gravite=None):
        return [l for l in self.lignes if not l["corrige"] and (gravite is None or l["gravite"] == gravite)]

    def note(self):
        n = 100
        for l in self.lignes:
            n -= 1 if l["corrige"] else {"grave": 25, "moyen": 7, "info": 1}[l["gravite"]]
        return max(0, n - 5 * len(self.sautes))

    def resume(self):
        return dict(note=self.note(), lignes=self.lignes, sautes=self.sautes,
                    corriges=sum(1 for l in self.lignes if l["corrige"]),
                    graves_restants=len(self.restants("grave")))


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


def controle_texte(script, articles, B, journal=print, tours=2):
    """Niveau 1. Corrige le texte sur place ; seules les phrases en défaut sont réécrites."""
    for tour in range(tours):
        pb = regles_texte(script)
        if not pb:
            return script
        corriger_sans_ia(script, pb)
        for i, probleme, simple in pb:
            if simple:
                B.ajouter("texte", probleme, i, "info", corrige=True)
        dur = [x for x in pb if not x[2]]
        if not dur:
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
            for i, probleme, _ in dur:
                B.ajouter("texte", probleme, i, "grave" if i is None else "moyen")
            B.saute("réécriture du texte (aucune IA)")
            return script
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
        for i, probleme, _ in dur:
            B.ajouter("texte", probleme, i, "moyen", corrige=refaites > 0)
        journal(f"  contrôle du texte (tour {tour + 1}) : {len(pb)} problème(s), {refaites} phrase(s) réécrite(s) par {qui}")
    for i, probleme, _ in regles_texte(script):
        B.ajouter("texte", probleme, i, "grave" if i is None else "moyen")
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


def controle_images(script, dossier, B, journal=print, deja=None, sujet=""):
    """Niveau 3. Remplace uniquement les images fautives (2 essais, sinon écran de texte)."""
    deja = deja if deja is not None else {p["media"]["id"] for p in script["phrases"] if p.get("media") and p["media"].get("id")}
    for tour in range(2):
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
        try:
            avis = juger_images(lots, sujet, journal) if lots else {}
        except ia.AucuneIA:
            if tour == 0:
                B.saute("regard de l'IA sur les images")
            avis = {}
        for i, a in avis.items():
            if not a.get("colle", True) or a.get("texte_etranger") or a.get("logo"):
                fautifs[i] = (a.get("probleme") or "image qui ne colle pas", a.get("recherche") or "")
        if not fautifs:
            return script
        journal(f"  contrôle des images (tour {tour + 1}) : {len(fautifs)} écran(s) à changer")
        for i, (probleme, recherche) in fautifs.items():
            p = script["phrases"][i]
            nouv = images.trouver(recherche or p.get("image", ""), dossier, 50 + 10 * tour + i % 10, deja, journal,
                                  script.get("theme_image", "")) if (recherche or p.get("image")) else None
            p["media"] = nouv                       # None = écran de texte (jamais une image hors sujet)
            B.ajouter("images", probleme, i, "moyen", corrige=True)
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
    """Niveau 4. Renvoie {n° d'écran: (problème, action)} ; action = "image", "titre" ou "voix"."""
    from . import montage
    ph = script["phrases"]; debuts, total = montage.debuts_et_total(ph)
    fautifs = {}
    duree, w, h, son = _probe(fichier)
    if (w, h) != (1080, 1920):
        B.ajouter("video", f"format {w}×{h} au lieu de 1080×1920", None, "grave")
    if not son:
        B.ajouter("video", "pas de son", None, "grave")
    if duree < 60:
        B.ajouter("video", f"vidéo de {duree:.0f} s : moins d'1 minute (pas payée par TikTok)", None, "grave")
    for i in ecrans_noirs(fichier, debuts):
        if ph[i].get("media"):
            fautifs[i] = ("écran noir dans la vidéo finie", "image")
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
    except ia.AucuneIA:
        B.saute("regard de l'IA sur la vidéo finie")
    return fautifs


def corriger_ecrans(script, fautifs, dossier, B, journal=print, nom_voix="", vitesse=0.8):
    """Applique les corrections aux seuls écrans fautifs (le montage ne refera que ceux-là)."""
    deja = {p["media"]["id"] for p in script["phrases"] if p.get("media") and p["media"].get("id")}
    for i, (probleme, action) in fautifs.items():
        p = script["phrases"][i]
        if action == "image":
            p["media"] = images.trouver(p.get("image", ""), dossier, 80 + i, deja, journal, script.get("theme_image", ""))
        elif action == "titre":
            p["ecran"] = " ".join((p.get("ecran") or "").split()[:2])[:14]
        elif action == "voix":
            p.pop("mots", None)
            V.preparer([p], nom_voix, vitesse, journal)
        B.ajouter("video", probleme, i, "grave" if action == "voix" else "moyen", corrige=True)


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
