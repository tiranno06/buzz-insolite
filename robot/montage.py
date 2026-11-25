"""Montage de la vidéo verticale (1080 × 1920, 30 images/s), validé par l'auteur sur l'essai « 1 an sur Mars » (24/11/2026).

Chaque phrase = un écran : vraie vidéo (nette au milieu, la même floutée derrière), photo (léger zoom) ou écran de texte.
En haut : étiquette « INSOLITE » + gros titre de l'écran. En bas : sous-titres karaoké (3 mots, le mot dit en jaune et un peu
plus gros, calé sur la voix par Whisper), placés au-dessus de la zone où TikTok affiche le pseudo et la description.
"""
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

from . import carte, sons
from . import voix as V
from .commun import POLICES

W, H, IPS = 1080, 1920, 30
GRAS = os.path.join(POLICES, "Poppins-Bold.ttf"); MOYEN = os.path.join(POLICES, "Poppins-Medium.ttf")
JAUNE, ROUGE, BLANC = (255, 214, 0), (235, 40, 60), (255, 255, 255)
PAUSE, FIN = 0.18, 1.6                  # silence entre deux phrases ; dernier écran un peu plus long
SOUS_TITRES_MARGE = 470                 # distance du bas : au-dessus du pseudo et de la description de TikTok


def police(t, gras=True):
    return ImageFont.truetype(GRAS if gras else MOYEN, t)


def _centre(d, y, texte, f, coul=BLANC):
    w = d.textlength(texte, font=f)
    d.text(((W - w) / 2, y), texte, font=f, fill=coul, stroke_width=6, stroke_fill=(0, 0, 0))


def _ajuste(d, texte, depart, largeur):
    t = depart
    while d.textlength(texte, font=police(t)) > largeur and t > 30:
        t -= 4
    return t


LOGO = os.path.join(os.path.dirname(POLICES), "docs", "marque", "logo-a.png")   # logo de la chaîne choisi par l'auteur (24/11)
# Zones libres de TikTok (1080×1920) : en haut, la barre « Pour toi » et la loupe (jusqu'à ~160 px) ; à droite, la colonne
# des boutons (x > ~940, de y ~700 à ~1600) ; en bas, le pseudo et la description (y > ~1540). Rien d'important n'y va.
ZONE_HAUT, ZONE_DROITE, ZONE_BAS, MARGE_COTES = 160, 140, 1540, 130
LOGO_TAILLE, LOGO_XY = 130, (W - 60 - 130, 175)      # en haut à droite, SOUS la loupe de TikTok
_logo = []


def logo_rond():
    """Logo A en petit, rond, avec un liseré blanc (préparé une seule fois)."""
    if not _logo:
        t = LOGO_TAILLE
        if not os.path.exists(LOGO):
            _logo.append(None); return None
        im = Image.open(LOGO).convert("RGBA").resize((t, t), Image.LANCZOS)
        masque = Image.new("L", (t, t), 0); ImageDraw.Draw(masque).ellipse([0, 0, t - 1, t - 1], fill=255)
        rond = Image.new("RGBA", (t + 8, t + 8), (0, 0, 0, 0)); ImageDraw.Draw(rond).ellipse([0, 0, t + 7, t + 7], fill=BLANC)
        rond.paste(im, (4, 4), masque)
        _logo.append(rond)
    return _logo[0]


def calque(chemin, titre="", grand="", petit="", etiquette="INSOLITE", coul=JAUNE, bas="", source=""):
    """Textes posés sur l'image (fond transparent), et le logo de la chaîne en haut à droite. `source` : bandeau
    « @compte » (court, demande de l'auteur du 25/11) bien visible pendant une courte citation (la source n'est jamais cachée)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); f = police(46)
    lg = logo_rond()
    if lg:
        im.alpha_composite(lg, LOGO_XY)
    if etiquette:
        d.rounded_rectangle([60, 185, 60 + d.textlength(etiquette, font=f) + 60, 265], 22, fill=ROUGE, outline=BLANC, width=3)
        d.text((90, 189), etiquette, font=f, fill=BLANC)
    if source:
        fs = police(28)
        larg = min(W - 2 * MARGE_COTES, d.textlength(source, font=fs) + 40)
        y = 470 if titre else 300                       # sous le gros titre, loin des textes de la vidéo d'origine
        d.rounded_rectangle([60, y, 60 + larg, y + 48], 12, fill=(0, 0, 0, 190), outline=BLANC, width=2)
        d.text((80, y + 6), source, font=fs, fill=BLANC)
    larg = W - 2 * MARGE_COTES                         # jamais sous la colonne de boutons de TikTok
    if titre:
        _centre(d, 330, titre, police(_ajuste(d, titre, 104, larg)), coul)
    if grand:
        t = _ajuste(d, grand, 230, larg)
        _centre(d, 560, grand, police(t), coul)
        if petit:
            _centre(d, 600 + t, petit, police(_ajuste(d, petit, 72, larg)))
    if bas:                                            # sources de l'actu, sur le dernier écran
        _centre(d, 1080, bas, police(_ajuste(d, bas, 40, larg), gras=False), (230, 230, 230))
    im.save(chemin)
    return chemin


def fond_texte(chemin, haut=(12, 20, 48), bas=(40, 8, 60)):
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    for y in range(H):
        a = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(haut[i] * (1 - a) + bas[i] * a) for i in range(3)))
    im.save(chemin)
    return chemin


def centre_cadrage(media):
    """Vidéo ou photo HORIZONTALE (hors citation, montrée en entier) : position des visages (0 à 1) pour la recadrer sur eux
    (amélioration 2 du 25/11) ; 0,5 = le milieu, comme avant."""
    if not media or media.get("type") not in ("video", "photo") or media.get("citation") or not media.get("chemin"):
        return 0.5
    if "cx" not in media:
        from . import vision
        try:
            r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                                "-of", "csv=p=0", media["chemin"]], capture_output=True, text=True, timeout=30)
            w, h = [int(x) for x in r.stdout.strip().split(",")[:2]]
        except Exception:
            w, h = 1, 1
        media["cx"] = (vision.centre_visages(media["chemin"], media.get("debut", 0), 10, media["type"] == "video")
                       if w > h * 1.15 else None) or 0.5
    return media["cx"]


def ecran(media, duree, png, sortie, dossier):
    """Un écran de `duree` secondes (sans son)."""
    commun = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(IPS), "-an"]
    if media and media["type"] == "carte":
        try:
            return carte.video(media, duree, png, sortie, dossier)
        except Exception as e:                            # carte impossible (frontières injoignables…) : écran de texte
            print(f"    carte impossible ({str(e)[:80]}) : écran de texte", flush=True)
            media = None
    haut_net = int(W / 1.1) // 2 * 2
    cx = centre_cadrage(media)
    xcrop = f"max(0,min(iw-min(iw,ih*1.1),{cx}*iw-min(iw,ih*1.1)/2))"    # recadré sur les visages (sinon le milieu)
    if media and media["type"] == "photo" and media.get("citation"):
        # image fixe tirée d'une vidéo d'origine : montrée en ENTIER (logo visible), sur fond flou
        vf = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:2,"
              f"eq=brightness=-0.2,fps={IPS}[fond];[b]scale={W}:{H - 120}:force_original_aspect_ratio=decrease,fps={IPS}[net];"
              f"[fond][net]overlay=(W-w)/2:(H-h)/2[v];[v][1:v]overlay=0:0,format=yuv420p[s]")
        entree = ["-loop", "1", "-i", media["chemin"]]
    elif media and media["type"] == "video" and media.get("citation"):
        # courte citation : la vidéo d'origine ENTIÈRE à l'écran (ni recadrée ni floutée : son logo reste visible),
        # sur un fond flou de la même vidéo
        debut = media.get("debut", 0) if (media.get("duree") or 99) > duree + media.get("debut", 0) else 0
        vf = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=25:2,"
              f"eq=brightness=-0.18,fps={IPS}[fond];[b]scale={W}:{H - 120}:force_original_aspect_ratio=decrease,fps={IPS}[net];"
              f"[fond][net]overlay=(W-w)/2:(H-h)/2[v];[v][1:v]overlay=0:0,format=yuv420p[s]")
        entree = ["-stream_loop", "-1", "-ss", str(debut), "-i", media["chemin"]]
    elif media and media["type"] == "video":
        debut = media.get("debut", 0) if (media.get("duree") or 99) > duree + media.get("debut", 0) else 0
        vf = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=25:2,"
              f"eq=brightness=-0.18,fps={IPS}[fond];[b]crop=w='min(iw,ih*1.1)':h=ih:x='{xcrop}':y=0,scale={W}:{haut_net},"
              f"fps={IPS},zoompan=z='1+0.0015*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{haut_net}:fps={IPS}[net];"
              f"[fond][net]overlay=0:(H-h)/2-40[v];[v][1:v]overlay=0:0,format=yuv420p[s]")
        entree = ["-stream_loop", "-1", "-ss", str(debut), "-i", media["chemin"]]
    elif media and media["type"] == "photo":
        n = int(duree * IPS) + 1
        vf = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:2,"
              f"eq=brightness=-0.2[fond];[b]scale={W*2}:-2,crop=w='min(iw,ih*1.1)':h=ih:x='{xcrop}':y=0,"
              f"zoompan=z='1+0.07*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{haut_net}:fps={IPS}[net];"
              f"[fond]fps={IPS}[f2];[f2][net]overlay=0:(H-h)/2-40[v];[v][1:v]overlay=0:0,format=yuv420p[s]")
        entree = ["-loop", "1", "-i", media["chemin"]]
    else:
        fond = fond_texte(os.path.join(dossier, "fond_texte.png"))
        vf = f"[0:v]fps={IPS}[f];[f][1:v]overlay=0:0,format=yuv420p[s]"
        entree = ["-loop", "1", "-i", fond]
    subprocess.run(["ffmpeg", "-y", "-v", "error", *entree, "-loop", "1", "-i", png, "-filter_complex", vf, "-map", "[s]",
                    "-t", f"{duree:.3f}", *commun, sortie], check=True)
    return sortie


def _hms(x):
    return f"{int(x // 3600)}:{int(x % 3600 // 60):02d}:{x % 60:05.2f}"


def karaoke(phrases, debuts, credits_texte):
    """Sous-titres ASS : groupes de 3 mots, le mot dit passe en jaune et grossit un peu, pile au bon moment."""
    ass = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "", "[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
           "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
           f"Style: S,Poppins,100,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,9,4,2,"
           f"{MARGE_COTES},{MARGE_COTES + 10},{SOUS_TITRES_MARGE},1",
           # écran d'une vidéo d'origine (citation) : ses propres sous-titres incrustés sont souvent au même endroit que les
           # nôtres (vidéo CAN du 25/11) → nos sous-titres sur un BANDEAU NOIR opaque, toujours lisibles
           f"Style: B,Poppins,92,&H00FFFFFF,&H00FFFFFF,&H28000000,&H28000000,-1,0,0,0,100,100,0,0,3,18,0,2,"
           f"{MARGE_COTES},{MARGE_COTES + 10},{SOUS_TITRES_MARGE},1",
           # crédits juste sous les sous-titres, AU-DESSUS de la description de TikTok (sinon cachés : licence CC BY)
           f"Style: C,Poppins,26,&H00DDDDDD,&H00DDDDDD,&H60000000,&H60000000,0,0,0,0,100,100,0,0,3,4,0,2,"
           f"{MARGE_COTES},{MARGE_COTES + 10},{H - ZONE_BAS + 8},1", "",
           "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for i, p in enumerate(phrases):
        style = "B" if (p.get("media") or {}).get("citation") else "S"
        aff = V.mots_affiches(p["ecrit"]); tm = V.caler(aff, p["mots"], p["duree"])
        paquets, cur = [], []
        for k, m in enumerate(aff):
            cur.append(k)
            if len(cur) >= 3 or m[-1] in ",.:;?!…":
                paquets.append(cur); cur = []
        if cur:
            paquets.append(cur)
        for j, paq in enumerate(paquets):
            fin_p = tm[paquets[j + 1][0]][0] if j + 1 < len(paquets) else p["duree"] + p.get("_pause", PAUSE)
            for q, k in enumerate(paq):
                a = 0.0 if (q == 0 and j == 0) else tm[k][0]
                b = tm[paq[q + 1]][0] if q + 1 < len(paq) else fin_p
                txt = " ".join(("{\\c&H00D6FF&\\fscx112\\fscy112}" + aff[x].upper() + "{\\c&HFFFFFF&\\fscx100\\fscy100}")
                               if x == k else aff[x].upper() for x in paq)
                if b > a:
                    ass.append(f"Dialogue: 0,{_hms(debuts[i] + a)},{_hms(debuts[i] + b)},{style},,0,0,0,,{txt}")
    total = debuts[-1] + phrases[-1]["duree"] + phrases[-1].get("_pause", PAUSE) + FIN
    if credits_texte:
        ass.append(f"Dialogue: 0,{_hms(0)},{_hms(total)},C,,0,0,0,,{credits_texte}")
    return "\n".join(ass) + "\n"


def miniature(chemin_video, chemin_jpg, instant=1.0):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(instant), "-i", chemin_video, "-frames:v", "1",
                    "-vf", "scale=360:-2", "-q:v", "4", chemin_jpg], check=True)


def debuts_et_total(ph):
    debuts, t = [], 0.0
    for p in ph:
        debuts.append(t); t += p["duree"] + p.get("_pause", PAUSE)
    return debuts, t + FIN


def faire_ecran(script, i, d, dossier):
    """Fabrique l'écran n° i (durée d). Renvoie le fichier."""
    ph = script["phrases"]; p = ph[i]
    png = os.path.join(dossier, f"calque{i:02d}.png")
    derniere = i == len(ph) - 1
    if p.get("reponse"):                                  # « Vrai ou faux ? » : la réponse en grand, vert ou rouge
        vrai = p["reponse"] == "vrai"
        calque(png, etiquette=script.get("etiquette") or "INSOLITE", grand="VRAI !" if vrai else "FAUX !", petit=(p.get("ecran") or "").upper(),
               coul=(80, 220, 120) if vrai else (255, 80, 90))
    elif p.get("media") and not derniere:
        m = p["media"]
        titre = (p.get("ecran") or "").upper()
        if i > 0 and titre and titre == (ph[i - 1].get("ecran") or "").upper():
            titre = ""                                        # même titre que l'écran d'avant (« INCIDENT » 2 fois de suite)
        calque(png, etiquette=script.get("etiquette") or "INSOLITE", titre=titre,
               source=(m.get("bandeau") or f"@{m.get('compte', 'source')}") if m.get("citation") else "")
    else:
        grand = "ET TOI ?" if derniere else (p.get("ecran") or "").upper()
        petit = "dis-le en commentaire" if derniere else ""
        calque(png, etiquette=script.get("etiquette") or "INSOLITE", grand=grand, petit=petit, bas=script.get("sources_ecran", "") if derniere else "")
    m = os.path.join(dossier, f"ecran{i:02d}.mp4")
    ecran(p.get("media"), d, png, m, dossier)
    return m


def _signature(script, i, d):
    p = script["phrases"][i]; m = p.get("media") or {}
    return f"{d:.3f}|{m.get('id') or m.get('type') or ''}|{m.get('debut', '')}|{p.get('ecran', '')}|{p.get('reponse', '')}|{i == len(script['phrases']) - 1}"


def enchainer(ph, debuts):
    """Un morceau de vidéo qui CONTINUE sur la phrase suivante (5 à 10 s d'affilée) : l'écran suivant reprend la vidéo là où
    le précédent s'est arrêté (pas de saut en arrière)."""
    for i in range(1, len(ph)):
        m, avant = ph[i].get("media") or {}, ph[i - 1].get("media") or {}
        if m.get("suite") and avant.get("chemin") == m.get("chemin"):
            m["debut"] = round(avant.get("debut", 0) + (debuts[i] - debuts[i - 1]), 2)


def monter(script, dossier, sortie, suivi=None):
    """script["phrases"][i] doit avoir : son, duree, mots, media (ou None), ecran. Renvoie la durée de la vidéo.
    Un écran déjà fabriqué dont rien n'a changé (durée, image, titre) est gardé tel quel : une correction ne refait que les
    écrans touchés, puis la vidéo est réassemblée (voix, sous-titres et musique sont refaits en entier, c'est rapide)."""
    ph = script["phrases"]
    if script.get("musique", True) and not script.get("_musique"):     # une seule musique par vidéo (même après corrections)
        script["_musique"] = sons.musique(script.get("humeur", "neutre")) or ""
    # coupes d'écran PILE sur le rythme de la musique : le silence entre deux phrases varie de 0,08 à 0,45 s
    sons.caler_pauses(ph, sons.battements(script["_musique"]) if script.get("_musique") else [], PAUSE)
    debuts, total = debuts_et_total(ph)
    enchainer(ph, debuts)
    silences = {}
    for p in ph:
        cle = f"{p['_pause']:.3f}"
        if cle not in silences:
            silences[cle] = os.path.join(dossier, f"pause{cle}.wav")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", cle,
                            silences[cle]], check=True)
    with open(os.path.join(dossier, "voix.txt"), "w") as f:
        for p in ph:
            f.write(f"file '{p['son']}'\nfile '{silences[format(p['_pause'], '.3f')]}'\n")
    voix = os.path.join(dossier, "voix.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", os.path.join(dossier, "voix.txt"), voix], check=True)

    morceaux, refaits = [], 0
    for i, p in enumerate(ph):
        d = (debuts[i + 1] if i + 1 < len(debuts) else total) - debuts[i]
        sig = _signature(script, i, d)
        fichier = os.path.join(dossier, f"ecran{i:02d}.mp4")
        if p.get("_sig") != sig or not os.path.exists(fichier):
            faire_ecran(script, i, d, dossier); p["_sig"] = sig; refaits += 1
        morceaux.append(fichier)
        if suivi:
            suivi(i + 1, len(ph))
    script["_ecrans_refaits"] = refaits
    with open(os.path.join(dossier, "ecrans.txt"), "w") as f:
        f.write("".join(f"file '{m}'\n" for m in morceaux))
    images = os.path.join(dossier, "images.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", os.path.join(dossier, "ecrans.txt"),
                    "-c", "copy", images], check=True)

    credits_ = sorted({p["media"]["credit"] for p in ph if p.get("media")})
    texte_credits = ("Images : " + " · ".join(credits_))[:150] if credits_ else ""
    ass = os.path.join(dossier, "st.ass")
    with open(ass, "w", encoding="utf-8") as f:
        f.write(karaoke(ph, debuts, texte_credits))
    bande = sons.mixer(voix, ph, debuts, total, script.get("humeur", "neutre"), os.path.join(dossier, "bande.wav"),
                       (script.get("_musique") or False) if script.get("musique", True) else False, script.get("format", ""),
                       script.get("bruitages", True),
                       script.get("transitions", False))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", images, "-i", bande,
                    "-filter_complex", f"[0:v]subtitles={ass}:fontsdir={POLICES}[v]",
                    "-map", "[v]", "-map", "1:a", "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-movflags", "+faststart", sortie],
                   check=True)
    return total
