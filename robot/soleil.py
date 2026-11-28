"""LA VRAIE LUMIÈRE DU MOMENT (28/11, choix de l'auteur dans la recherche d'outils : « 3 »).

D'après la date, l'heure locale et le lieu de l'événement, on calcule la position RÉELLE du soleil (formules de la NOAA,
sans internet) : sa hauteur au-dessus de l'horizon et sa direction. La reconstitution 3D prend alors la vraie lumière :
plein jour, soleil bas et orangé du coucher, crépuscule bleu, nuit — et des ombres longues ou courtes au bon angle.
(Avant : « jour » ou « soir » deviné par l'IA ; un accident à 17 h 40 en novembre au Caire était filmé en plein soleil.)

Fuseau horaire du lieu : timezonefinder (MIT, sans internet), heure d'été comprise (zoneinfo).
Sans heure dite dans le texte : l'heure typique du moment cité (« matin » 8 h, « soir » 19 h, « nuit » 23 h…), sinon midi.
"""
import datetime as dt
import math
import re

MOIS = {"janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
        "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12, "décembre": 12}
MOMENTS = ((r"\bà l'aube|au petit matin|lever du jour", 6.5), (r"\bmatin(?:ée)?\b", 9.0), (r"\bmidi\b", 12.5),
           (r"après-midi|apres-midi", 15.5), (r"\bfin de journée|crépuscule|coucher du soleil", 18.0),
           (r"\bsoir(?:ée)?\b", 20.0), (r"\bnuit\b|\bminuit\b|nocturne", 23.5))


def position(lat, lon, quand_utc):
    """(hauteur en degrés, azimut en degrés depuis le nord, sens des aiguilles) du soleil à cet instant UTC."""
    j = quand_utc.timetuple().tm_yday
    h = quand_utc.hour + quand_utc.minute / 60 + quand_utc.second / 3600
    g = 2 * math.pi / 365 * (j - 1 + (h - 12) / 24)                      # année fractionnaire
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g)
                    - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
            + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    tst = (h * 60 + eqt + 4 * lon) % 1440                                 # temps solaire vrai (minutes)
    ha = math.radians(tst / 4 - 180)
    la = math.radians(lat)
    cz = math.sin(la) * math.sin(decl) + math.cos(la) * math.cos(decl) * math.cos(ha)
    zen = math.acos(max(-1.0, min(1.0, cz)))
    haut = 90 - math.degrees(zen)
    # azimut depuis le nord, vers l'est (formule de l'angle horaire)
    az = (math.degrees(math.atan2(math.sin(ha), math.cos(ha) * math.sin(la) - math.tan(decl) * math.cos(la))) + 180) % 360
    return round(haut, 2), round(az, 1)


def fuseau(lat, lon):
    try:
        from timezonefinder import TimezoneFinder
        return TimezoneFinder().timezone_at(lng=lon, lat=lat)
    except Exception:                                                     # outil absent : décalage approximatif
        return None


def heure_du_texte(texte, heures=None):
    """Heure locale (décimale) : la 1re heure précise dite (« 21 h 40 »), sinon le moment cité, sinon None."""
    for h in heures or []:
        m = re.match(r"(\d{1,2})\s*[h:]\s*(\d{2})?", str(h.get("heure") if isinstance(h, dict) else h))
        if m and int(m.group(1)) < 24:
            return int(m.group(1)) + int(m.group(2) or 0) / 60
    t = (texte or "").lower()
    m = re.search(r"\b(\d{1,2})\s*h\s*(\d{2})?\b", t)
    if m and int(m.group(1)) < 24:
        return int(m.group(1)) + int(m.group(2) or 0) / 60
    return next((h for motif, h in MOMENTS if re.search(motif, t)), None)


def date_du_texte(texte, date=None, annee=None):
    """Date de l'événement : celle extraite par l'IA ({jour, mois}), sinon « 25 novembre » dans le texte, sinon aujourd'hui."""
    annee = annee or dt.date.today().year
    j = m = None
    if isinstance(date, dict) and str(date.get("jour") or "").isdigit():
        j, m = int(date["jour"]), MOIS.get(str(date.get("mois") or "").lower().strip())
    if not (j and m):
        r = re.search(r"\b(\d{1,2})\s+(" + "|".join(MOIS) + r")\b", (texte or "").lower())
        if r:
            j, m = int(r.group(1)), MOIS[r.group(2)]
    try:
        return dt.date(annee, m, j) if j and m else dt.date.today()
    except ValueError:
        return dt.date.today()


def lumiere(lat, lon, texte="", date=None, heures=None, annee=None):
    """Lumière réelle de l'événement : {hauteur, azimut, moment, heure, fuseau, sure} ; sure = une heure a été dite."""
    h = heure_du_texte(texte, heures)
    sure = h is not None
    if h is None:
        h = 13.0
    jour = date_du_texte(texte, date, annee)
    nom = fuseau(lat, lon)
    local = dt.datetime.combine(jour, dt.time(int(h) % 24, int(round((h % 1) * 60)) % 60))
    try:
        from zoneinfo import ZoneInfo
        utc = local.replace(tzinfo=ZoneInfo(nom)).astimezone(dt.timezone.utc) if nom else None
    except Exception:
        utc = None
    if utc is None:                                                       # sans fuseau : d'après la longitude
        utc = (local - dt.timedelta(hours=round(lon / 15))).replace(tzinfo=dt.timezone.utc)
    haut, az = position(lat, lon, utc)
    moment = "jour" if haut > 8 else "soir" if haut > -8 else "nuit"     # soir = soleil bas, coucher, crépuscule
    return dict(hauteur=haut, azimut=az, moment=moment, heure=round(h, 2), fuseau=nom or "", date=jour.isoformat(), sure=sure)
