"""Icônes de l'appli : pastille rouge, éclair jaune « BUZZ ». python outils/icones.py"""
import os
from PIL import Image, ImageDraw, ImageFont

ICI = os.path.dirname(os.path.abspath(__file__)); DOCS = os.path.join(ICI, "..", "docs")
GRAS = os.path.join(ICI, "..", "polices", "Poppins-Bold.ttf")


def icone(taille, marge=0.0, coins=0.22):
    im = Image.new("RGBA", (taille, taille), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, taille - 1, taille - 1], int(taille * coins), fill=(232, 40, 60))
    s = taille * (1 - 2 * marge); o = taille * marge
    eclair = [(0.56, 0.12), (0.30, 0.52), (0.47, 0.52), (0.40, 0.88), (0.72, 0.42), (0.54, 0.42), (0.62, 0.12)]
    d.polygon([(o + x * s, o + y * s * 0.82) for x, y in eclair], fill=(255, 214, 0))
    f = ImageFont.truetype(GRAS, int(s * 0.2)); w = d.textlength("BUZZ", font=f)
    d.text(((taille - w) / 2, o + s * 0.74), "BUZZ", font=f, fill=(255, 255, 255))
    return im


for nom, t, m, c in (("logo-192.png", 192, 0.06, 0.22), ("logo-512.png", 512, 0.06, 0.22),
                     ("logo-512-maskable.png", 512, 0.16, 0), ("logo-apple.png", 180, 0.08, 0)):
    icone(t, m, c).save(os.path.join(DOCS, nom))
