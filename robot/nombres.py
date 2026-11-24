"""Nombres écrits en lettres, en français (pour que la voix les lise bien) : 378 → « trois cent soixante-dix-huit »."""
import re

UNITES = ["zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze", "treize",
          "quatorze", "quinze", "seize"]
DIZAINES = {2: "vingt", 3: "trente", 4: "quarante", 5: "cinquante", 6: "soixante"}


def _moins_de_100(n):
    if n <= 16:
        return UNITES[n]
    if n < 20:
        return "dix-" + UNITES[n - 10]
    d, u = divmod(n, 10)
    if d in (7, 9):                                   # 70-79 = soixante-dix…, 90-99 = quatre-vingt-dix…
        base = "soixante" if d == 7 else "quatre-vingt"
        reste = n - (60 if d == 7 else 80)
        return base + ("-et-" if reste == 11 and d == 7 else "-") + _moins_de_100(reste)
    if d == 8:
        return "quatre-vingts" if u == 0 else "quatre-vingt-" + UNITES[u]
    return DIZAINES[d] + ("" if u == 0 else "-et-un" if u == 1 else "-" + UNITES[u])


def _moins_de_1000(n):
    c, r = divmod(n, 100)
    if c == 0:
        return _moins_de_100(r)
    tete = "cent" if c == 1 else UNITES[c] + " cent" + ("s" if r == 0 else "")
    return tete if r == 0 else tete + " " + _moins_de_100(r)


def en_lettres(n):
    """Entier (jusqu'à 999 999 999 999) en lettres."""
    if n < 0:
        return "moins " + en_lettres(-n)
    if n < 1000:
        return _moins_de_1000(n)
    morceaux = []
    for valeur, nom in ((10**9, "milliard"), (10**6, "million"), (1000, "mille")):
        q, n = divmod(n, valeur)
        if q:
            if nom == "mille":
                morceaux.append("mille" if q == 1 else _moins_de_1000(q).replace("cents", "cent") + " mille")
            else:
                morceaux.append(f"{en_lettres(q)} {nom}{'s' if q > 1 else ''}")
    if n:
        morceaux.append(_moins_de_1000(n))
    return " ".join(morceaux)


def dire_les_nombres(texte):
    """Remplace dans un texte les nombres écrits en chiffres (« 16 000 », « 3,5 », « 99/100 », « 2027 ») par des mots."""
    def un(m):
        brut = m.group(0)
        entier = re.sub(r"[\s  .]", "", m.group(1))
        mots = en_lettres(int(entier))
        if m.group(2):
            mots += " virgule " + " ".join(UNITES[int(c)] for c in m.group(2)) if len(m.group(2)) > 2 else \
                " virgule " + en_lettres(int(m.group(2)))
        return mots if brut else brut
    t = re.sub(r"(\d+)\s?/\s?(\d+)", lambda m: f"{m.group(1)} sur {m.group(2)}", texte)
    t = re.sub(r"(\d+)\s?%", r"\1 pour cent", t)
    for unite, mot in (("km", "kilomètres"), ("kg", "kilos"), ("m²", "mètres carrés"), ("°C", "degrés"), ("€", "euros"),
                       ("M€", "millions d'euros"), ("cm", "centimètres")):
        t = re.sub(r"(\d)\s?" + re.escape(unite) + r"(?![\w²])", r"\1 " + mot, t)
    t = re.sub(r"(\d{1,3}(?:[\s  .]\d{3})+|\d+)(?:,(\d+))?", un, t)
    return t
