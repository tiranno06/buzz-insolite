"""Logos de la chaîne (photo de profil TikTok, 1080 × 1080, contenu dans le rond central). python outils/logos.py"""
import math
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ICI = os.path.dirname(os.path.abspath(__file__)); SORTIE = os.path.join(ICI, "..", "docs", "marque")
GRAS = os.path.join(ICI, "..", "polices", "Poppins-Bold.ttf")
T = 1080; ROUGE = (232, 40, 60); JAUNE = (255, 214, 0); BLANC = (255, 255, 255); NOIR = (18, 17, 16)


def degrade(haut, bas):
    im = Image.new("RGB", (T, T)); d = ImageDraw.Draw(im)
    for y in range(T):
        a = y / T; d.line([(0, y), (T, y)], fill=tuple(int(haut[i] * (1 - a) + bas[i] * a) for i in range(3)))
    return im


def texte(d, xy_centre, t, taille, coul, contour=10):
    f = ImageFont.truetype(GRAS, taille); w = d.textlength(t, font=f)
    d.text((xy_centre[0] - w / 2, xy_centre[1]), t, font=f, fill=coul, stroke_width=contour, stroke_fill=NOIR)


def eclair(d, cx, cy, h, coul, ombre=True):
    pts = [(0.10, -0.50), (-0.28, 0.06), (-0.02, 0.06), (-0.14, 0.50), (0.30, -0.10), (0.04, -0.10), (0.16, -0.50)]
    if ombre:
        d.polygon([(cx + x * h + 14, cy + y * h + 14) for x, y in pts], fill=NOIR)
    d.polygon([(cx + x * h, cy + y * h) for x, y in pts], fill=coul, outline=NOIR, width=8)


def rayons(im, coul, n=18):
    d = ImageDraw.Draw(im, "RGBA")
    for k in range(n):
        a0 = 2 * math.pi * k / n; a1 = a0 + math.pi / n
        d.polygon([(T / 2, T / 2), (T / 2 + 900 * math.cos(a0), T / 2 + 900 * math.sin(a0)),
                   (T / 2 + 900 * math.cos(a1), T / 2 + 900 * math.sin(a1))], fill=coul)


def logo_a():
    """Rouge, rayons, éclair jaune, BUZZ / INSOLITE."""
    im = degrade((245, 60, 75), (170, 18, 38)); rayons(im, (255, 255, 255, 28)); d = ImageDraw.Draw(im)
    eclair(d, T / 2, 400, 520, JAUNE)
    texte(d, (T / 2, 610), "BUZZ", 220, BLANC, 14)
    texte(d, (T / 2, 845), "INSOLITE", 96, JAUNE, 9)
    return im


def logo_b():
    """Fond sombre, bulle rouge avec un « ! » jaune géant (l'alerte info)."""
    im = degrade((30, 28, 26), (8, 8, 8)); d = ImageDraw.Draw(im)
    d.ellipse([200, 150, 880, 830], fill=ROUGE, outline=BLANC, width=14)
    d.polygon([(360, 760), (300, 900), (470, 800)], fill=ROUGE)
    f = ImageFont.truetype(GRAS, 560); w = d.textlength("!", font=f)
    d.text(((T - w) / 2, 150), "!", font=f, fill=JAUNE, stroke_width=12, stroke_fill=NOIR)
    texte(d, (T / 2, 860), "BUZZ INSOLITE", 92, BLANC, 8)
    return im


def logo_c():
    """Monogramme « BI » blanc sur rouge, éclair jaune entre les lettres."""
    im = Image.new("RGB", (T, T), ROUGE); rayons(im, (0, 0, 0, 30), 12); d = ImageDraw.Draw(im)
    d.ellipse([110, 110, 970, 970], outline=JAUNE, width=26)
    f = ImageFont.truetype(GRAS, 470)
    wb, wi = d.textlength("B", font=f), d.textlength("I", font=f); ecart = 190
    x0 = (T - (wb + ecart + wi)) / 2
    d.text((x0, 200), "B", font=f, fill=BLANC, stroke_width=14, stroke_fill=NOIR)
    d.text((x0 + wb + ecart, 200), "I", font=f, fill=BLANC, stroke_width=14, stroke_fill=NOIR)
    eclair(d, x0 + wb + ecart / 2, 540, 420, JAUNE)
    return im


def apercu(ims):
    """Planche : chaque logo coupé en rond comme sur TikTok."""
    planche = Image.new("RGB", (3 * 400 + 80, 460), (240, 240, 240)); d = ImageDraw.Draw(planche)
    for k, im in enumerate(ims):
        petit = im.resize((360, 360), Image.LANCZOS); masque = Image.new("L", (360, 360), 0)
        ImageDraw.Draw(masque).ellipse([0, 0, 359, 359], fill=255)
        planche.paste(petit, (40 + k * 400, 30), masque)
        f = ImageFont.truetype(GRAS, 30); t = "ABC"[k]; w = d.textlength(t, font=f)
        d.text((40 + k * 400 + 180 - w / 2, 405), t, font=f, fill=NOIR)
    return planche


if __name__ == "__main__":
    os.makedirs(SORTIE, exist_ok=True)
    ims = [logo_a(), logo_b(), logo_c()]
    for k, im in zip("abc", ims):
        im.save(os.path.join(SORTIE, f"logo-{k}.png"))
    apercu(ims).save(os.path.join(SORTIE, "logos-apercu.png"))
